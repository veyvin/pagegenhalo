# Halo 文章发布工具

一个基于 Flask 的 AI 文章生成与发布工具，通过 DeepSeek API 自动生成技术博客文章，并支持一键发布到 Halo CMS 系统。

**演示地址**: https://pagegen.veyvin.com/

## 功能特性

- 📝 **AI 文章生成**: 使用 DeepSeek API 根据用户输入的 prompt 生成高质量技术文章
- 🎨 **多种写作模板**: 支持默认技术博客、教程风格、总结风格等多种写作模板
- 🏷️ **智能标签提取**: 根据文章内容自动提取标签和分类
- 🖼️ **自动封面生成**: 支持网络搜索、Ollama 本地文生图、SD WebUI 等多种封面来源
- 🚀 **一键发布**: 生成文章后可直接发布到 Halo CMS 或保存为草稿
- 👁️ **文章预览**: 支持生成后预览，确认后再发布
- 📜 **历史记录**: 保存生成历史，支持重新加载和发布
- 📋 **草稿管理**: 从 Halo 拉取草稿列表，支持加载和发布
- 🔐 **双重认证**: Google Authenticator 验证码登录保护

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | Flask |
| AI 服务 | DeepSeek API |
| 博客平台 | Halo CMS |
| 封面生成 | Ollama / Stable Diffusion WebUI / Bing 图片搜索 |
| 认证方式 | Google Authenticator (TOTP) |
| 数据库 | SQLite (内置，无需额外配置) |

## 安装和运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 文件为 `.env`，并填入你的真实配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# DeepSeek API 密钥（必须）
DEEPSEEK_API_KEY=your-deepseek-api-key

# Halo 配置（必须）
HALO_URL=https://your-halo-site.com
HALO_TOKEN=your-halo-token

# Google Authenticator（必须，用于登录验证）
GOOGLE_AUTH_SECRET=your-google-auth-secret
CONFIG_PREVIEW_PASSWORD=your-preview-password

# 封面图生成（可选）
COVER_IMAGE_BACKEND=ollama
COVER_WEB_ENGINE=bing_cn
OLLAMA_URL=http://localhost:11434
OLLAMA_IMAGE_MODEL=x/z-image-turbo
SD_WEBUI_URL=http://localhost:7860
```

**注意**: `.env` 文件包含敏感信息，已被添加到 `.gitignore`，不会被提交到 Git 仓库。

### 3. 运行应用

```bash
python app.py
```

应用将在 `http://localhost:5555` 启动。

## 使用方法

### 基本使用流程

1. **登录系统**: 访问首页后使用 Google Authenticator 验证码登录
2. **输入 Prompt**: 在文本框中输入你想要生成的文章描述
   - 示例: `请写一篇关于 Python 异步编程的技术文章，介绍 asyncio 的使用方法和最佳实践。`
3. **选择选项**:
   - 使用格式模板：自动添加 HTML 格式要求
   - 写作风格：默认、教程、总结
   - 自动提取标签：根据内容智能提取标签和分类
   - 自动生成封面：为文章生成封面图
4. **生成文章**:
   - 仅生成（预览）：只生成文章，不发布
   - 生成并保存为草稿：生成后保存到 Halo 草稿箱
   - 生成并发布：生成后直接发布到 Halo

### Prompt 编写建议

- 描述文章主题和内容要求
- 指定文章风格（技术深度、入门教程、实战案例等）
- 要求包含特定章节或内容
- 指定文章长度和格式要求

```
请写一篇关于 React Hooks 的技术文章，包括：
- Hooks 的基本概念和使用场景
- 常用的 Hooks（useState, useEffect, useContext）
- 自定义 Hooks 的编写方法
- 实际项目中的应用案例
```

### 封面生成选项

- **网络搜索**: 从 Bing 或 DuckDuckGo 搜索与文章主题相关的图片
- **Ollama**: 使用本地 Ollama 文生图模型生成封面
- **SD WebUI**: 使用本地 Stable Diffusion WebUI 生成封面

## API 端点

### POST /api/generate

生成文章并保存为草稿

```json
{
  "prompt": "你的 prompt",
  "use_template": true,
  "template_id": "default",
  "language": "zh",
  "auto_extract_tags": false,
  "generate_cover": false,
  "tags": ["标签1", "标签2"],
  "categories": ["分类1"]
}
```

### POST /api/generate-only

仅生成文章（不保存）

```json
{
  "prompt": "你的 prompt",
  "use_template": true
}
```

### POST /api/publish

发布文章到 Halo

```json
{
  "title": "文章标题",
  "content": "文章内容（HTML格式）",
  "tags": ["标签1", "标签2"],
  "categories": ["分类1"],
  "generate_cover": false
}
```

### POST /api/generate-and-publish

生成并发布文章（一步完成）

```json
{
  "prompt": "你的 prompt",
  "use_template": true,
  "tags": ["标签1", "标签2"],
  "categories": ["分类1"]
}
```

### GET /api/drafts

从 Halo 拉取草稿列表

### GET /api/drafts/<name>

获取单篇草稿详情

### GET /api/history

获取生成历史列表

### GET /api/history/<id>

获取单条历史记录详情

### POST /api/auto-tag-posts

自动为无标签和分类的文章添加标签和分类

## 项目结构

```
.
├── app/                    # Flask 应用核心
│   ├── __init__.py         # 应用工厂
│   ├── auth/               # 认证模块
│   │   ├── routes.py       # 认证路由（登录/登出）
│   │   └── utils.py        # 认证工具（TOTP验证）
│   ├── blog/               # 博客模块
│   │   └── routes.py       # 博客相关 API 路由
│   ├── services/           # 业务服务
│   │   ├── deepseek.py     # DeepSeek API 调用
│   │   ├── halo.py         # Halo API 调用
│   │   ├── cover_image.py  # 封面图生成
│   │   └── history.py      # 历史记录管理
│   ├── utils/              # 工具函数
│   │   ├── logging.py      # 日志工具
│   │   ├── response.py     # 统一响应格式
│   │   └── text.py         # 文本处理工具
│   └── errors.py           # 错误处理
├── templates/              # HTML 模板
│   ├── index.html          # 主页面
│   └── login.html          # 登录页面
├── tests/                  # 测试文件
├── .env.example            # 环境变量示例
├── .gitignore              # Git 忽略规则
├── app.py                  # 应用入口
├── config.py               # 配置文件
├── requirements.txt        # 依赖列表
└── README.md               # 项目说明
```

## 安全注意事项

1. **API 密钥安全**: 不要将 API 密钥提交到代码仓库，使用环境变量管理
2. **Halo Token**: 确保 Halo Token 有发布文章的权限，建议使用专用的 PAT（个人访问令牌）
3. **Google Authenticator**: 首次部署时需要配置 `GOOGLE_AUTH_SECRET`，确保登录安全
4. **HTTPS**: 生产环境请使用 HTTPS 协议，保护传输中的数据

## 故障排除

### 生成失败
- 检查 `DEEPSEEK_API_KEY` 是否正确设置
- 检查网络连接是否正常
- 查看调试日志获取详细错误信息

### 发布失败
- 检查 `HALO_TOKEN` 是否正确设置
- 检查 `HALO_URL` 是否正确
- 确认 Halo Token 有发布权限

### 封面生成失败
- 如果使用 Ollama，确保 Ollama 服务已启动且模型已下载
- 如果使用 SD WebUI，确保 WebUI 已启动并启用了 API

## 许可证

MIT
