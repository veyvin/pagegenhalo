package config

import "os"

type Config struct {
	Port        string
	SecretKey   string
	DEEPSEEK    DeepSeekConfig
	Halo        HaloConfig
	Cover       CoverConfig
	Auth        AuthConfig
	WritingTmpl map[string]string
}

type DeepSeekConfig struct {
	APIKey string
	APIURL string
}

type HaloConfig struct {
	URL   string
	Token string
}

type CoverConfig struct {
	Backend     string
	WebEngine   string
	OllamaURL   string
	OllamaModel string
	SDWebUIURL  string
}

type AuthConfig struct {
	GoogleAuthSecret   string
	ConfigPreviewPwd   string
	SessionLifetimeMin int
}

func Load() *Config {
	return &Config{
		Port:      getEnv("PORT", "5555"),
		SecretKey: getEnv("SECRET_KEY", "change-me-in-production"),
		DEEPSEEK: DeepSeekConfig{
			APIKey: getEnv("DEEPSEEK_API_KEY", ""),
			APIURL: getEnv("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions"),
		},
		Halo: HaloConfig{
			URL:   getEnv("HALO_URL", "https://veyvin.com"),
			Token: getEnv("HALO_TOKEN", ""),
		},
		Cover: CoverConfig{
			Backend:     getEnv("COVER_IMAGE_BACKEND", "ollama"),
			WebEngine:   getEnv("COVER_WEB_ENGINE", "bing_cn"),
			OllamaURL:   getEnv("OLLAMA_URL", "http://localhost:11434"),
			OllamaModel: getEnv("OLLAMA_IMAGE_MODEL", "x/z-image-turbo"),
			SDWebUIURL:  getEnv("SD_WEBUI_URL", "http://localhost:7860"),
		},
		Auth: AuthConfig{
			GoogleAuthSecret:   getEnv("GOOGLE_AUTH_SECRET", ""),
			ConfigPreviewPwd:   getEnv("CONFIG_PREVIEW_PASSWORD", "admin123"),
			SessionLifetimeMin: getEnvInt("SESSION_LIFETIME_MINUTES", 60),
		},
		WritingTmpl: map[string]string{
			"default":  defaultTmpl,
			"tutorial": tutorialTmpl,
			"summary":  summaryTmpl,
		},
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		var n int
		for _, c := range v {
			if c >= '0' && c <= '9' {
				n = n*10 + int(c-'0')
			}
		}
		if n > 0 {
			return n
		}
	}
	return fallback
}

var defaultTmpl = "写作要求：\n" +
	"1. 文章标题请直接写在第一行，不要包含任何 HTML 标签\n" +
	"2. 正文内容从第二行开始，使用 HTML 格式\n" +
	"3. 文章长度1000-2000字，要有实质内容\n" +
	"4. 正文中使用适当的 HTML 标签：p, h2, h3, ul, li, code, strong, em, blockquote\n" +
	"5. 所有标题标签必须包含 id 属性\n" +
	"6. 不要返回完整的 HTML 文档结构\n" +
	"7. 直接返回文章内容\n" +
	"8. 使用专业但易懂的技术语言\n" +
	"9. 添加一些代码以增加可读性\n\n" +
	"代码格式要求：\n" +
	"- 所有代码块必须使用 pre>code 标签包裹\n" +
	"- 不要使用 ``` 来包裹代码块\n" +
	"- 行内代码使用 code 标签\n\n" +
	"请严格按照这个格式返回：文章标题（第一行）\n" +
	"html内容（从第二行开始）"

var tutorialTmpl = "教程风格要求：\n" +
	"1. 第一行为文章标题（无 HTML），可带 1-2 个图标\n" +
	"2. 正文从第二行开始，使用 HTML：p, h2, h3, ul, li, code, pre 等\n" +
	"3. 结构清晰：简介 - 步骤/要点 - 小结，每步有标题 id\n" +
	"4. 长度 800-1500 字，偏实操，带简短代码示例\n" +
	"5. 不要返回 DOCTYPE/html/head/body\n" +
	"6. 直接返回内容，无多余说明"

var summaryTmpl = "总结/归纳风格要求：\n" +
	"1. 第一行为文章标题（无 HTML）\n" +
	"2. 正文从第二行开始，使用 HTML 标签，条理分明\n" +
	"3. 以要点、对比或列表为主，可配简短代码\n" +
	"4. 长度 600-1200 字，信息密度高\n" +
	"5. 不要返回完整文档结构，直接返回标题+正文"
