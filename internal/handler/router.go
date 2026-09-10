package handler

import (
	"encoding/json"
	"fmt"
	"html/template"
	"net/http"
	"strconv"
	"strings"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/pagegen/internal/auth"
	"github.com/pagegen/internal/config"
	"github.com/pagegen/internal/cover"
	"github.com/pagegen/internal/deepseek"
	"github.com/pagegen/internal/halo"
	"github.com/pagegen/internal/history"
	"github.com/pagegen/internal/session"
)

type Router struct {
	cfg      *config.Config
	store    *session.Store
	dsClient *deepseek.Client
	hClient  *halo.Client
	cClient  *cover.Client
	tmpl     *template.Template
}

func NewRouter(cfg *config.Config, store *session.Store) http.Handler {
	r := &Router{
		cfg:      cfg,
		store:    store,
		dsClient: deepseek.NewClient(cfg),
		hClient:  halo.NewClient(cfg),
		cClient:  cover.NewClient(cfg, deepseek.NewClient(cfg)),
	}

	r.tmpl = template.Must(template.ParseGlob("templates/*.html"))

	router := chi.NewRouter()
	router.Use(chimw.Recoverer)

	router.Get("/health", r.health)
	router.Get("/login", r.loginPage)
	router.Post("/login", r.loginPost)
	router.Get("/logout", r.logout)
	router.Get("/hide-config", r.hideConfig)

	router.Group(func(grp chi.Router) {
		grp.Use(r.authMiddleware)
		grp.Get("/", r.index)
		grp.Post("/api/generate", r.apiGenerate)
		grp.Post("/api/generate-only", r.apiGenerateOnly)
		grp.Post("/api/publish", r.apiPublish)
		grp.Get("/api/drafts", r.apiDrafts)
		grp.Get("/api/drafts/{name}", r.apiDraftDetail)
		grp.Get("/api/history", r.apiHistory)
		grp.Get("/api/history/{id}", r.apiHistoryItem)
		grp.Post("/api/generate-and-publish", r.apiGenerateAndPublish)
		grp.Route("/api/auto-tag-posts", func(r2 chi.Router) {
			r2.Get("/", r.apiAutoTagPosts)
			r2.Post("/", r.apiAutoTagPosts)
		})
	})

	return router
}

func (r *Router) authMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		path := req.URL.Path
		if path == "/login" || path == "/logout" || path == "/hide-config" || path == "/health" || strings.HasPrefix(path, "/static") {
			next.ServeHTTP(w, req)
			return
		}

		sess, _ := r.store.Get(req, "session")
		if auth, ok := sess.Data["authenticated"].(bool); !auth || !ok {
			if strings.HasPrefix(path, "/api") {
				writeJSON(w, http.StatusUnauthorized, map[string]interface{}{
					"success": false,
					"error":   "未认证或会话已过期，请重新登录。",
				})
				return
			}
			http.Redirect(w, req, "/login", http.StatusFound)
			return
		}

		next.ServeHTTP(w, req)
	})
}

func (r *Router) health(w http.ResponseWriter, req *http.Request) {
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"status":  "ok",
		"service": "go",
	})
}

func (r *Router) loginPage(w http.ResponseWriter, req *http.Request) {
	sess, _ := r.store.Get(req, "session")
	showConfig, _ := sess.Data["show_config"].(bool)

	data := map[string]interface{}{
		"show_config": showConfig,
	}

	if showConfig {
		secret := auth.GetOrCreateSecret(r.cfg.Auth.GoogleAuthSecret)
		data["secret"] = secret
		data["qr_code_url"] = auth.GenerateQRCodeURL(secret)
	}

	r.tmpl.ExecuteTemplate(w, "login.html", data)
}

func (r *Router) loginPost(w http.ResponseWriter, req *http.Request) {
	req.ParseForm()
	sess, _ := r.store.Get(req, "session")

	if pwd := req.Form.Get("show_config_password"); pwd != "" {
		if pwd == r.cfg.Auth.ConfigPreviewPwd {
			sess.Data["show_config"] = true
			r.store.Save(w, req, "session", sess)
			http.Redirect(w, req, "/login", http.StatusFound)
			return
		}
		data := map[string]interface{}{
			"error":        "密码错误，无法显示配置信息",
			"show_config":  false,
		}
		r.tmpl.ExecuteTemplate(w, "login.html", data)
		return
	}

	token := req.Form.Get("token")
	if token != "" {
		secret := auth.GetOrCreateSecret(r.cfg.Auth.GoogleAuthSecret)
		if auth.VerifyOTP(token, secret, 2) {
			sess.Data["authenticated"] = true
			r.store.Save(w, req, "session", sess)
			http.Redirect(w, req, "/", http.StatusFound)
			return
		}
		data := map[string]interface{}{
			"error":       "验证码错误，请重试。",
			"show_config": sess.Data["show_config"],
		}
		r.tmpl.ExecuteTemplate(w, "login.html", data)
		return
	}

	http.Redirect(w, req, "/login", http.StatusFound)
}

func (r *Router) logout(w http.ResponseWriter, req *http.Request) {
	r.store.Clear(w, "session")
	http.Redirect(w, req, "/login", http.StatusFound)
}

func (r *Router) hideConfig(w http.ResponseWriter, req *http.Request) {
	sess, _ := r.store.Get(req, "session")
	delete(sess.Data, "show_config")
	r.store.Save(w, req, "session", sess)
	http.Redirect(w, req, "/login", http.StatusFound)
}

func (r *Router) index(w http.ResponseWriter, req *http.Request) {
	tmplOptions := []map[string]string{}
	for id := range r.cfg.WritingTmpl {
		label := "默认（技术博客）"
		if id == "tutorial" {
			label = "教程风格"
		} else if id == "summary" {
			label = "总结风格"
		}
		tmplOptions = append(tmplOptions, map[string]string{"id": id, "label": label})
	}

	data := map[string]interface{}{
		"template_options": tmplOptions,
	}
	r.tmpl.ExecuteTemplate(w, "index.html", data)
}

func (r *Router) apiGenerate(w http.ResponseWriter, req *http.Request) {
	var data struct {
		Prompt          string   `json:"prompt"`
		UseTemplate     bool     `json:"use_template"`
		TemplateID      string   `json:"template_id"`
		Language        string   `json:"language"`
		AutoExtractTags bool     `json:"auto_extract_tags"`
		GenerateCover   bool     `json:"generate_cover"`
		CoverSource     string   `json:"cover_source"`
		Tags            []string `json:"tags"`
		Categories      []string `json:"categories"`
	}
	json.NewDecoder(req.Body).Decode(&data)

	if data.Prompt == "" {
		writeJSON(w, http.StatusBadRequest, map[string]interface{}{"success": false, "error": "请输入 prompt"})
		return
	}

	title, content, err := r.dsClient.GeneratePost(data.Prompt, data.TemplateID, data.Language)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]interface{}{"success": false, "error": err.Error()})
		return
	}

	tags, categories := data.Tags, data.Categories
	if data.AutoExtractTags {
		autoTags, autoCats, _ := r.dsClient.ExtractTagsAndCategories(title, content)
		tags = appendUnique(tags, autoTags)
		categories = appendUnique(categories, autoCats)
	}

	result, err := r.hClient.Publish(title, content, tags, categories, false, "")
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]interface{}{
			"success": false,
			"error":   fmt.Sprintf("生成成功，但保存到 Halo 失败: %v", err),
		})
		return
	}

	history.AddRecord(title, content, "draft")
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success":    true,
		"data":       result,
		"message":    "文章已生成并保存为草稿到 Halo",
		"title":      title,
		"content":    content,
		"tags":       tags,
		"categories": categories,
	})
}

func (r *Router) apiGenerateOnly(w http.ResponseWriter, req *http.Request) {
	var data struct {
		Prompt          string `json:"prompt"`
		UseTemplate     bool   `json:"use_template"`
		TemplateID      string `json:"template_id"`
		Language        string `json:"language"`
		AutoExtractTags bool   `json:"auto_extract_tags"`
	}
	json.NewDecoder(req.Body).Decode(&data)

	if data.Prompt == "" {
		writeJSON(w, http.StatusBadRequest, map[string]interface{}{"success": false, "error": "请输入 prompt"})
		return
	}

	title, content, err := r.dsClient.GeneratePost(data.Prompt, data.TemplateID, data.Language)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]interface{}{"success": false, "error": err.Error()})
		return
	}

	var extractedTags, extractedCategories []string
	if data.AutoExtractTags {
		extractedTags, extractedCategories, _ = r.dsClient.ExtractTagsAndCategories(title, content)
	}

	history.AddRecord(title, content, "preview")
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success":              true,
		"message":              "文章已生成，可在下方预览后点击「发布当前预览」",
		"title":                title,
		"content":              content,
		"extracted_tags":       extractedTags,
		"extracted_categories": extractedCategories,
	})
}

func (r *Router) apiPublish(w http.ResponseWriter, req *http.Request) {
	var data struct {
		Title         string   `json:"title"`
		Content       string   `json:"content"`
		Tags          []string `json:"tags"`
		Categories    []string `json:"categories"`
		GenerateCover bool     `json:"generate_cover"`
		CoverSource   string   `json:"cover_source"`
	}
	json.NewDecoder(req.Body).Decode(&data)

	if data.Title == "" || data.Content == "" {
		writeJSON(w, http.StatusBadRequest, map[string]interface{}{"success": false, "error": "标题和内容不能为空"})
		return
	}

	result, err := r.hClient.Publish(data.Title, data.Content, data.Tags, data.Categories, true, "")
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]interface{}{"success": false, "error": err.Error()})
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{"success": true, "data": result, "message": "文章发布成功"})
}

func (r *Router) apiDrafts(w http.ResponseWriter, req *http.Request) {
	page, _ := strconv.Atoi(req.URL.Query().Get("page"))
	size, _ := strconv.Atoi(req.URL.Query().Get("size"))
	if size == 0 || size > 50 {
		size = 20
	}

	publish := false
	items, err := r.hClient.ListPosts(&publish, page, size)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]interface{}{"success": false, "error": err.Error()})
		return
	}

	result := []map[string]interface{}{}
	for _, item := range items {
		if m, ok := item.(map[string]interface{}); ok {
			post, _ := m["post"].(map[string]interface{})
			meta, _ := post["metadata"].(map[string]interface{})
			spec, _ := post["spec"].(map[string]interface{})
			result = append(result, map[string]interface{}{
				"name":    meta["name"],
				"title":   spec["title"],
				"slug":    spec["slug"],
				"publish": spec["publish"],
			})
		}
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{"success": true, "data": result})
}

func (r *Router) apiDraftDetail(w http.ResponseWriter, req *http.Request) {
	name := chi.URLParam(req, "name")
	post, err := r.hClient.GetPost(name)
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]interface{}{"success": false, "error": err.Error()})
		return
	}

	spec := post["spec"].(map[string]interface{})
	content := post["content"].(map[string]interface{})

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"title":   spec["title"],
		"content": content["raw"],
		"name":    name,
	})
}

func (r *Router) apiHistory(w http.ResponseWriter, req *http.Request) {
	limit, _ := strconv.Atoi(req.URL.Query().Get("limit"))
	if limit == 0 || limit > 50 {
		limit = 20
	}

	items := history.GetList(limit)
	writeJSON(w, http.StatusOK, map[string]interface{}{"success": true, "data": items})
}

func (r *Router) apiHistoryItem(w http.ResponseWriter, req *http.Request) {
	id := chi.URLParam(req, "id")
	record := history.GetOne(id)
	if record == nil {
		writeJSON(w, http.StatusNotFound, map[string]interface{}{"success": false, "error": "未找到该记录"})
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success":    true,
		"title":      record.Title,
		"content":    record.Content,
		"created_at": record.CreatedAt,
		"status":     record.Status,
	})
}

func (r *Router) apiGenerateAndPublish(w http.ResponseWriter, req *http.Request) {
	var data struct {
		Prompt          string   `json:"prompt"`
		UseTemplate     bool     `json:"use_template"`
		TemplateID      string   `json:"template_id"`
		Language        string   `json:"language"`
		AutoExtractTags bool     `json:"auto_extract_tags"`
		Tags            []string `json:"tags"`
		Categories      []string `json:"categories"`
	}
	json.NewDecoder(req.Body).Decode(&data)

	if data.Prompt == "" {
		writeJSON(w, http.StatusBadRequest, map[string]interface{}{"success": false, "error": "请输入 prompt"})
		return
	}

	title, content, err := r.dsClient.GeneratePost(data.Prompt, data.TemplateID, data.Language)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]interface{}{"success": false, "error": err.Error()})
		return
	}

	tags, categories := data.Tags, data.Categories
	if data.AutoExtractTags {
		autoTags, autoCats, _ := r.dsClient.ExtractTagsAndCategories(title, content)
		tags = appendUnique(tags, autoTags)
		categories = appendUnique(categories, autoCats)
	}

	result, err := r.hClient.Publish(title, content, tags, categories, true, "")
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]interface{}{
			"success": false,
			"error":   fmt.Sprintf("发布失败: %v", err),
		})
		return
	}

	history.AddRecord(title, content, "published")
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"data":    result,
		"message": "文章生成并发布成功",
		"title":   title,
		"content": content,
	})
}

func (r *Router) apiAutoTagPosts(w http.ResponseWriter, req *http.Request) {
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"message": "Auto tag feature coming soon",
	})
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func appendUnique(base, items []string) []string {
	seen := make(map[string]bool)
	for _, s := range base {
		seen[s] = true
	}
	for _, s := range items {
		if !seen[s] {
			base = append(base, s)
			seen[s] = true
		}
	}
	if len(base) > 10 {
		base = base[:10]
	}
	return base
}
