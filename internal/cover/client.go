package cover

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	"github.com/pagegen/internal/config"
	"github.com/pagegen/internal/deepseek"
)

type Client struct {
	cfg     *config.Config
	http    *http.Client
	dsClient *deepseek.Client
}

func NewClient(cfg *config.Config, dsClient *deepseek.Client) *Client {
	return &Client{
		cfg:     cfg,
		http:    &http.Client{Timeout: 60 * time.Second},
		dsClient: dsClient,
	}
}

func (c *Client) GetCover(title, excerpt, content string, tags []string, source, ollamaURL, sdWebUIURL string) (string, error) {
	query := c.buildQuery(title, excerpt, content, tags)

	switch source {
	case "web_search":
		return c.searchWeb(query)
	case "ollama":
		return c.generateOllama(query, ollamaURL)
	case "sd_webui":
		return c.generateSDWebUI(query, sdWebUIURL)
	default:
		return c.generateOllama(query, ollamaURL)
	}
}

func (c *Client) buildQuery(title, excerpt, content string, tags []string) string {
	if c.cfg.DEEPSEEK.APIKey != "" && c.dsClient != nil {
		fullContent := content
		if fullContent == "" {
			fullContent = excerpt
		}
		if keywords, err := c.dsClient.ExtractCoverKeywords(title, fullContent); err == nil && keywords != "" {
			return keywords
		}
	}

	parts := []string{title}
	if len(tags) > 0 {
		parts = append(parts, tags[:min(len(tags), 5)]...)
	}
	text := stripHTML(content)
	if text == "" {
		text = stripHTML(excerpt)
	}
	if len(text) > 200 {
		text = text[:200]
	}
	if text != "" {
		parts = append(parts, text)
	}
	return strings.Join(parts, " ")[:min(len(strings.Join(parts, " ")), 100)]
}

func (c *Client) searchWeb(query string) (string, error) {
	engine := c.cfg.Cover.WebEngine
	if engine == "" {
		engine = "bing_cn"
	}

	switch engine {
	case "duckduckgo":
		return c.searchDuckDuckGo(query)
	default:
		return c.searchBingCN(query)
	}
}

func (c *Client) searchBingCN(query string) (string, error) {
	url := fmt.Sprintf("https://cn.bing.com/images/async?q=%s&first=0&count=35", query)
	req, _ := http.NewRequest("GET", url, nil)
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

	resp, err := c.http.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	re := regexp.MustCompile(`&quot;murl&quot;:&quot;(https?://[^&]+)&quot;`)
	matches := re.FindSubmatch(body)
	if len(matches) > 1 {
		return string(matches[1]), nil
	}

	doc, err := goquery.NewDocumentFromReader(bytes.NewReader(body))
	if err != nil {
		return "", err
	}

	var imgURL string
	doc.Find("div.iusc").Each(func(i int, s *goquery.Selection) {
		if imgURL != "" {
			return
		}
		dataM, _ := s.Attr("data-m")
		if dataM == "" {
			return
		}
		dataM = strings.ReplaceAll(dataM, "&quot;", `"`)
		var obj map[string]interface{}
		if json.Unmarshal([]byte(dataM), &obj) == nil {
			if u, ok := obj["murl"].(string); ok && strings.HasPrefix(u, "http") {
				imgURL = u
			}
		}
	})

	if imgURL == "" {
		return "", fmt.Errorf("no image found")
	}
	return imgURL, nil
}

func (c *Client) searchDuckDuckGo(query string) (string, error) {
	return "", fmt.Errorf("duckduckgo not implemented in Go version")
}

func (c *Client) generateOllama(prompt, ollamaURL string) (string, error) {
	if ollamaURL == "" {
		ollamaURL = c.cfg.Cover.OllamaURL
	}
	if ollamaURL == "" {
		ollamaURL = "http://localhost:11434"
	}

	payload := map[string]interface{}{
		"model":  c.cfg.Cover.OllamaModel,
		"prompt": "Blog cover image, modern minimal style, professional, about: " + prompt,
		"stream": false,
	}

	body, _ := json.Marshal(payload)
	resp, err := c.http.Post(ollamaURL+"/api/generate", "application/json", bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result struct {
		Images   []string `json:"images"`
		Response string   `json:"response"`
	}
	json.NewDecoder(resp.Body).Decode(&result)

	if len(result.Images) > 0 {
		imgBytes, err := base64.StdEncoding.DecodeString(result.Images[0])
		if err == nil {
			return c.uploadToHalo(imgBytes, "cover.png")
		}
	}

	if result.Response != "" && len(result.Response) > 100 {
		imgBytes, err := base64.StdEncoding.DecodeString(result.Response)
		if err == nil {
			return c.uploadToHalo(imgBytes, "cover.png")
		}
	}

	return "", fmt.Errorf("no image generated")
}

func (c *Client) generateSDWebUI(prompt, sdWebUIURL string) (string, error) {
	if sdWebUIURL == "" {
		sdWebUIURL = c.cfg.Cover.SDWebUIURL
	}
	if sdWebUIURL == "" {
		sdWebUIURL = "http://localhost:7860"
	}

	payload := map[string]interface{}{
		"prompt":            "Blog cover image, modern minimal style, professional, about: " + prompt,
		"negative_prompt":   "blurry, low quality, distorted",
		"steps":             20,
		"width":             768,
		"height":            512,
		"cfg_scale":         7,
	}

	body, _ := json.Marshal(payload)
	resp, err := c.http.Post(sdWebUIURL+"/sdapi/v1/txt2img", "application/json", bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result struct {
		Images []string `json:"images"`
	}
	json.NewDecoder(resp.Body).Decode(&result)

	if len(result.Images) == 0 {
		return "", fmt.Errorf("no image from SD WebUI")
	}

	imgBytes, err := base64.StdEncoding.DecodeString(result.Images[0])
	if err != nil {
		return "", err
	}

	return c.uploadToHalo(imgBytes, "cover.png")
}

func (c *Client) uploadToHalo(imgBytes []byte, filename string) (string, error) {
	if c.cfg.Halo.Token == "" {
		return "", fmt.Errorf("HALO_TOKEN not configured")
	}

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	part, _ := writer.CreateFormFile("file", filename)
	part.Write(imgBytes)
	writer.Close()

	urls := []string{
		c.cfg.Halo.URL + "/apis/uc.api.storage.halo.run/v1alpha1/attachments/-/upload",
		c.cfg.Halo.URL + "/apis/api.console.halo.run/v1alpha1/attachments/-/upload",
	}

	for _, url := range urls {
		req, _ := http.NewRequest("POST", url, body)
		req.Header.Set("Content-Type", writer.FormDataContentType())
		req.Header.Set("Authorization", "Bearer "+c.cfg.Halo.Token)

		resp, err := c.http.Do(req)
		if err != nil {
			continue
		}
		defer resp.Body.Close()

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			var result map[string]interface{}
			json.NewDecoder(resp.Body).Decode(&result)
			if url := extractURL(result); url != "" {
				return url, nil
			}
		}
	}

	return "", fmt.Errorf("upload failed")
}

func extractURL(data map[string]interface{}) string {
	if status, ok := data["status"].(map[string]interface{}); ok {
		if u, ok := status["url"].(string); ok && u != "" {
			return u
		}
	}
	if spec, ok := data["spec"].(map[string]interface{}); ok {
		if u, ok := spec["url"].(string); ok && u != "" {
			return u
		}
	}
	if u, ok := data["url"].(string); ok && u != "" {
		return u
	}
	return ""
}

func stripHTML(s string) string {
	re := regexp.MustCompile(`<[^>]*>`)
	s = re.ReplaceAllString(s, " ")
	re = regexp.MustCompile(`\s+`)
	s = re.ReplaceAllString(s, " ")
	return strings.TrimSpace(s)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
