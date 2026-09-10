package deepseek

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/pagegen/internal/config"
)

type Client struct {
	cfg    *config.Config
	http   *http.Client
}

func NewClient(cfg *config.Config) *Client {
	return &Client{
		cfg: cfg,
		http: &http.Client{Timeout: 60 * time.Second},
	}
}

type chatRequest struct {
	Model     string    `json:"model"`
	Messages  []message `json:"messages"`
	Temperature float64 `json:"temperature"`
	MaxTokens  int     `json:"max_tokens"`
	Stream    bool      `json:"stream"`
}

type message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type chatResponse struct {
	Choices []struct {
		Message struct {
			Content string `json:"content"`
		} `json:"message"`
	} `json:"choices"`
}

func (c *Client) GeneratePost(prompt, templateID, language string) (title, content string, err error) {
	fullPrompt := buildPrompt(prompt, c.cfg.WritingTmpl[templateID])

	resp, err := c.chat(fullPrompt, 0.7, 8000)
	if err != nil {
		return "", "", err
	}

	title, content = extractTitleAndContent(resp)
	if title == "" {
		title = "自动生成的文章"
	}
	content = formatCodeBlocks(content)
	return title, content, nil
}

func (c *Client) ExtractTagsAndCategories(title, content string) (tags, categories []string, err error) {
	textSnippet := stripHTML(content)
	if len(textSnippet) > 800 {
		textSnippet = textSnippet[:800]
	}
	prompt := fmt.Sprintf(`根据以下文章标题和正文摘要，提取适合作为博客标签和分类的词语。

标题：%s
正文摘要：%s

请严格只返回一个 JSON 对象，格式如下：
{"tags": ["标签1", "标签2"], "categories": ["分类1", "分类2"]}`, title, textSnippet)

	resp, err := c.chat(prompt, 0.3, 500)
	if err != nil {
		return nil, nil, err
	}

	return parseTagsResponse(resp)
}

func (c *Client) ExtractCoverKeywords(title, content string) (string, error) {
	text := stripHTML(content)
	if len(text) > 600 {
		text = text[:600]
	}
	prompt := fmt.Sprintf(`根据以下博客文章，生成一句简短的图片搜索关键词（8-15字），用于搜索与文章主题相关的封面配图。
只输出关键词本身，不要引号、不要解释、不要标点。可用中英文混合。

标题：%s
内容摘要：%s`, title, text)

	resp, err := c.chat(prompt, 0.3, 80)
	if err != nil {
		return "", err
	}
	resp = strings.Trim(resp, `"' `)
	if len(resp) > 80 {
		return "", fmt.Errorf("keyword too long")
	}
	return resp, nil
}

func (c *Client) chat(prompt string, temperature float64, maxTokens int) (string, error) {
	if c.cfg.DEEPSEEK.APIKey == "" {
		return "", fmt.Errorf("DEEPSEEK_API_KEY not configured")
	}

	log.Printf("[deepseek] model=%s api_url=%s prompt_len=%d", c.cfg.DEEPSEEK.Model, c.cfg.DEEPSEEK.APIURL, len(prompt))

	reqBody := chatRequest{
		Model:       c.cfg.DEEPSEEK.Model,
		Messages:    []message{{Role: "user", Content: prompt}},
		Temperature: temperature,
		MaxTokens:   maxTokens,
		Stream:      false,
	}

	body, _ := json.Marshal(reqBody)
	req, _ := http.NewRequest("POST", c.cfg.DEEPSEEK.APIURL, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.cfg.DEEPSEEK.APIKey)

	resp, err := c.http.Do(req)
	if err != nil {
		log.Printf("[deepseek] request failed: %v", err)
		return "", fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		b, _ := io.ReadAll(resp.Body)
		log.Printf("[deepseek] API error %d: %s", resp.StatusCode, string(b[:min(200, len(b))]))
		return "", fmt.Errorf("API error %d: %s", resp.StatusCode, string(b[:min(200, len(b))]))
	}

	var chatResp chatResponse
	if err := json.NewDecoder(resp.Body).Decode(&chatResp); err != nil {
		log.Printf("[deepseek] decode error: %v", err)
		return "", fmt.Errorf("decode error: %w", err)
	}
	if len(chatResp.Choices) == 0 {
		return "", fmt.Errorf("no choices in response")
	}

	log.Printf("[deepseek] success, response_len=%d", len(chatResp.Choices[0].Message.Content))
	return chatResp.Choices[0].Message.Content, nil
}

func buildPrompt(userPrompt string, template string) string {
	if template == "" {
		template = "第一行为标题（无 HTML），第二行起为 HTML 正文。直接返回标题+正文。"
	}
	return fmt.Sprintf("%s\n\n请全文使用中文撰写。\n\n%s", userPrompt, template)
}

func extractTitleAndContent(raw string) (string, string) {
	raw = strings.TrimSpace(raw)
	lines := strings.SplitN(raw, "\n", 2)
	if len(lines) < 2 {
		return raw, raw
	}
	title := strings.TrimSpace(lines[0])
	title = regexp.MustCompile(`<[^>]*>`).ReplaceAllString(title, "")
	return title, lines[1]
}

func formatCodeBlocks(content string) string {
	re := regexp.MustCompile("```(\\w+)?\\s*\\n(.*?)\\n```")
	content = re.ReplaceAllString(content, `<pre><code class="language-${1}">${2}</code></pre>`)
	content = regexp.MustCompile("`([^`]+)`").ReplaceAllString(content, "<code>$1</code>")
	return content
}

func stripHTML(s string) string {
	re := regexp.MustCompile(`<[^>]*>`)
	s = re.ReplaceAllString(s, " ")
	s = regexp.MustCompile(`\s+`).ReplaceAllString(s, " ")
	return strings.TrimSpace(s)
}

func parseTagsResponse(raw string) ([]string, []string, error) {
	raw = strings.TrimSpace(raw)
	raw = regexp.MustCompile("^```(?:json)?\\s*").ReplaceAllString(raw, "")
	raw = regexp.MustCompile("\\s*```$").ReplaceAllString(raw, "")
	start := strings.Index(raw, "{")
	end := strings.LastIndex(raw, "}")
	if start >= 0 && end > start {
		raw = raw[start : end+1]
	}

	var result struct {
		Tags       []string `json:"tags"`
		Categories []string `json:"categories"`
	}
	if err := json.Unmarshal([]byte(raw), &result); err != nil {
		return nil, nil, fmt.Errorf("parse error: %w", err)
	}
	return result.Tags, result.Categories, nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
