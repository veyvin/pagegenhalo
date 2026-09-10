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

var defaultTmpl = "请为文章写一篇技术博客。\n\n" +
	"📝 文章结构建议（根据项目特点灵活选择3-6个部分）：\n" +
	"- 从一个实际开发场景或痛点开始，引出项目如何解决这个问题\n" +
	"- 对比这个项目与同类工具/框架的差异，突出其独特价值\n" +
	"- 聚焦技术实现细节，适合技术导向的项目\n" +
	"- 从实际应用场景出发，展示项目的实用价值\n\n" +
	"建议包含以下部分（根据项目特点选择3-5个即可）：\n" +
	"- 引人入胜的开头（故事/问题场景）\n" +
	"- 项目登场：如何解决这个问题\n" +
	"- 核心功能深度解析\n" +
	"- 技术亮点和创新点\n" +
	"- 实战体验和使用建议\n" +
	"- 总结：为什么值得关注\n\n" +
	"⚠️ 注意：不要固定使用相同的结构！根据项目类型灵活调整：\n" +
	"- 框架/库：侧重技术实现和使用方法\n" +
	"- 工具：侧重实用场景和效果\n" +
	"- CLI 工具：侧重命令行体验和效率提升\n" +
	"- UI/前端：侧重视觉效果和用户体验\n" +
	"- 后端/基础设施：侧重架构设计和性能\n\n" +
	"✨ 写作要求：\n" +
	"1. 文章标题请直接写在第一行，不要包含任何 HTML 标签。标题要吸引人，包含1-2个相关的有趣图标\n" +
	"2. 正文内容从第二行开始，使用 HTML 格式\n" +
	"3. 文章长度1000-2000字，要有实质内容，不要空泛\n" +
	"4. 正文中使用适当的 HTML 标签：<p>, <h2>, <h3>, <ul>, <li>, <code>, <strong>, <em>, <blockquote> 等\n" +
	"5. 所有标题标签必须包含 id 属性，例如：<h2 id=\"introduction\">介绍</h2>\n" +
	"6. 不要返回完整的 HTML 文档结构（不要有 <!DOCTYPE>, <html>, <head>, <body> 标签）\n" +
	"7. 直接返回文章内容，不要有其他说明文字\n" +
	"8. 使用专业但易懂的技术语言，要有趣味性和可读性\n" +
	"9. 添加一些代码以增加可读性和趣味性\n\n" +
	"🎨 增加趣味性的建议：\n" +
	"- 开头可以用一个有趣的故事、场景或问题引入\n" +
	"- 适当使用技术梗、开发趣事或生动的比喻\n" +
	"- 添加一些开发者会有共鸣的细节\n" +
	"- 使用生动的例子和场景描述\n\n" +
	"🖼️ 图片生成要求（如果模型支持图片输出）：\n" +
	"- 如果你的模型支持生成图片，请在文章中适当位置（通常 2-3 处）生成与文章内容紧密相关的配图\n" +
	"- 图片应帮助读者理解文章内容，例如：项目架构图、流程示意图、使用场景演示、功能对比图等\n" +
	"- 不要生成纯装饰性图片，每张图都应有实际的信息价值\n" +
	"- 图片应使用标准 HTML 标签插入：<img alt=\"图片描述文字\" src=\"图片URL或base64数据\" />\n" +
	"- alt 属性必须填写，用一句话描述图片内容，方便无图环境理解\n" +
	"- 如果模型不支持图片生成，则忽略此要求，仅生成纯文本文章即可\n\n" +
	"💻 代码格式要求：\n" +
	"- 所有代码块必须使用 pre>code 标签包裹\n" +
	"- 行内代码使用 code 标签\n" +
	"- 代码要有适当的缩进和语法高亮提示（class=\"language-xxx\"）\n\n" +
	"🔄 文章结构多样性要求：\n" +
	"- 不同项目应该有不同的文章结构\n" +
	"- 不要总是用相同的段落顺序\n" +
	"- 可以根据项目特点调整重点\n" +
	"- 标题要多样，不要总是\"项目介绍\"、\"功能特点\"这种固定词汇\n\n" +
	"请严格按照这个格式返回：\n" +
	"文章标题（第一行，不要HTML标签）\n" +
	"<html内容>（从第二行开始）"

var tutorialTmpl = "教程风格要求：\n" +
	"1. 第一行为文章标题（无 HTML），可带 1-2 个图标\n" +
	"2. 正文从第二行开始，使用 HTML：<p>, <h2>, <h3>, <ul>, <li>, <code>, <pre> 等\n" +
	"3. 结构清晰：简介 - 步骤/要点 - 小结，每步有标题 id\n" +
	"4. 长度 800-1500 字，偏实操，带简短代码示例\n" +
	"5. 不要返回 DOCTYPE/html/head/body\n" +
	"6. 直接返回内容，无多余说明\n" +
	"7. 使用生动的例子和场景描述\n" +
	"8. 适当使用表情符号增加趣味性\n\n" +
	"代码格式要求：\n" +
	"- 代码块使用 pre>code 标签包裹\n" +
	"- 行内代码使用 code 标签\n\n" +
	"请严格按照这个格式返回：\n" +
	"文章标题（第一行，不要HTML标签）\n" +
	"<html内容>（从第二行开始）"

var summaryTmpl = "总结/归纳风格要求：\n" +
	"1. 第一行为文章标题（无 HTML）\n" +
	"2. 正文从第二行开始，使用 HTML 标签，条理分明\n" +
	"3. 以要点、对比或列表为主，可配简短代码\n" +
	"4. 长度 600-1200 字，信息密度高\n" +
	"5. 不要返回完整文档结构，直接返回标题+正文\n" +
	"6. 使用表格或列表对比不同方案\n" +
	"7. 给出明确的推荐建议\n\n" +
	"代码格式要求：\n" +
	"- 代码块使用 pre>code 标签包裹\n" +
	"- 行内代码使用 code 标签\n\n" +
	"请严格按照这个格式返回：\n" +
	"文章标题（第一行，不要HTML标签）\n" +
	"<html内容>（从第二行开始）"
