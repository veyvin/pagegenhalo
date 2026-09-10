package halo

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/pagegen/internal/config"
)

type Client struct {
	cfg  *config.Config
	http *http.Client
}

func NewClient(cfg *config.Config) *Client {
	return &Client{
		cfg: cfg,
		http: &http.Client{Timeout: 30 * time.Second},
	}
}

type PostRequest struct {
	APIVersion string      `json:"apiVersion"`
	Kind       string      `json:"kind"`
	Metadata   interface{} `json:"metadata"`
	Spec       interface{} `json:"spec"`
}

type PublishResponse struct {
	Metadata struct {
		Name string `json:"name"`
	} `json:"metadata"`
}

func (c *Client) Publish(title, content string, tags, categories []string, publish bool, cover string) (map[string]interface{}, error) {
	if c.cfg.Halo.Token == "" {
		return nil, fmt.Errorf("HALO_TOKEN not configured")
	}

	slug := generateSlug(title)
	catIDs, tagIDs := c.resolveCategoriesAndTags(categories, tags)

	excerpt := stripHTML(content)
	if len(excerpt) > 150 {
		excerpt = excerpt[:150]
	}

	spec := map[string]interface{}{
		"title":        title,
		"slug":         slug,
		"template":     "",
		"cover":        cover,
		"deleted":      false,
		"publish":      false,
		"publishTime":  time.Now().Format("2006-01-02T15:04:05+08:00"),
		"pinned":       false,
		"allowComment": true,
		"visible":      "PUBLIC",
		"priority":     0,
		"excerpt":      map[string]interface{}{"autoGenerate": false, "raw": excerpt},
		"categories":   catIDs,
		"tags":         tagIDs,
		"htmlMetas":    []interface{}{},
	}

	contentJSON := map[string]interface{}{
		"content": content,
		"raw":     content,
		"rawType": "HTML",
	}

	payload := map[string]interface{}{
		"apiVersion": "content.halo.run/v1alpha1",
		"kind":       "Post",
		"metadata":   map[string]interface{}{"generateName": "post-"},
		"spec":       spec,
	}

	annotations := map[string]interface{}{
		"content.halo.run/content-json": c.jsonStr(contentJSON),
	}
	payload["metadata"] = map[string]interface{}{
		"generateName": "post-",
		"annotations":  annotations,
	}

	resp, err := c.post("/apis/uc.api.content.halo.run/v1alpha1/posts", payload)
	if err != nil {
		resp, err = c.post("/apis/api.console.halo.run/v1alpha1/posts", map[string]interface{}{
			"content": contentJSON,
			"post":    payload,
		})
	}
	if err != nil {
		return nil, err
	}

	postName := c.extractName(resp)
	if postName == "" {
		return nil, fmt.Errorf("no name in response")
	}

	if publish {
		_, err := c.publishPost(postName)
		if err != nil {
			return resp, fmt.Errorf("draft saved but publish failed: %w", err)
		}
	}

	return resp, nil
}

func (c *Client) ListPosts(publish *bool, page, size int) ([]interface{}, error) {
	url := fmt.Sprintf("/apis/api.console.halo.run/v1alpha1/posts?page=%d&size=%d", page, min(size, 50))
	if publish != nil {
		if *publish {
			url += "&publish=true"
		} else {
			url += "&publish=false"
		}
	}

	resp, err := c.get(url)
	if err != nil {
		return nil, err
	}

	items, _ := resp["items"].([]interface{})
	return items, nil
}

func (c *Client) GetPost(name string) (map[string]interface{}, error) {
	endpoints := []string{
		fmt.Sprintf("/apis/content.halo.run/v1alpha1/posts/%s", name),
		fmt.Sprintf("/apis/uc.api.content.halo.run/v1alpha1/posts/%s", name),
	}

	for _, ep := range endpoints {
		resp, err := c.get(ep)
		if err == nil && resp != nil {
			return resp, nil
		}
	}
	return nil, fmt.Errorf("post not found: %s", name)
}

func (c *Client) UpdatePostTagsAndCategories(name string, tags, categories []string) (map[string]interface{}, error) {
	post, err := c.GetPost(name)
	if err != nil {
		return nil, err
	}

	spec := post["spec"].(map[string]interface{})
	meta := post["metadata"].(map[string]interface{})

	catIDs, tagIDs := c.resolveCategoriesAndTags(categories, tags)

	updatedSpec := map[string]interface{}{
		"title":        spec["title"],
		"slug":         spec["slug"],
		"template":     spec["template"],
		"cover":        spec["cover"],
		"deleted":      spec["deleted"],
		"publish":      spec["publish"],
		"publishTime":  spec["publishTime"],
		"pinned":       spec["pinned"],
		"allowComment": spec["allowComment"],
		"visible":      spec["visible"],
		"priority":     spec["priority"],
		"excerpt":      spec["excerpt"],
		"categories":   catIDs,
		"tags":         tagIDs,
		"htmlMetas":    spec["htmlMetas"],
	}

	payload := map[string]interface{}{
		"apiVersion": "content.halo.run/v1alpha1",
		"kind":       "Post",
		"metadata":   meta,
		"spec":       updatedSpec,
	}

	endpoints := []string{
		fmt.Sprintf("/apis/content.halo.run/v1alpha1/posts/%s", name),
		fmt.Sprintf("/apis/uc.api.content.halo.run/v1alpha1/posts/%s", name),
	}

	for _, ep := range endpoints {
		resp, err := c.put(ep, payload)
		if err == nil {
			return resp, nil
		}
	}

	return nil, fmt.Errorf("update failed")
}

func (c *Client) resolveCategoriesAndTags(categories, tags []string) ([]string, []string) {
	catIDs := make([]string, 0)
	for _, cat := range categories {
		if id := c.ensureCategory(cat); id != "" {
			catIDs = append(catIDs, id)
		}
	}

	tagIDs := make([]string, 0)
	for _, tag := range tags {
		if id := c.ensureTag(tag); id != "" {
			tagIDs = append(tagIDs, id)
		}
	}

	return catIDs, tagIDs
}

func (c *Client) ensureCategory(displayName string) string {
	slug := toSlug(displayName)
	items, _ := c.listItems("/apis/content.halo.run/v1alpha1/categories")
	for _, item := range items {
		spec := c.extractSpec(item)
		if spec["displayName"] == displayName || spec["slug"] == slug {
			return c.extractName(item)
		}
	}
	return c.createCategory(displayName, slug)
}

func (c *Client) ensureTag(displayName string) string {
	slug := toSlug(displayName)
	items, _ := c.listItems("/apis/content.halo.run/v1alpha1/tags")
	for _, item := range items {
		spec := c.extractSpec(item)
		if spec["displayName"] == displayName || spec["slug"] == slug {
			return c.extractName(item)
		}
	}
	return c.createTag(displayName, slug)
}

func (c *Client) createCategory(displayName, slug string) string {
	payload := map[string]interface{}{
		"apiVersion": "content.halo.run/v1alpha1",
		"kind":       "Category",
		"metadata":   map[string]interface{}{"name": toSlug(slug)},
		"spec": map[string]interface{}{
			"displayName": displayName,
			"slug":        slug,
			"description": "",
			"cover":       "",
			"template":    "",
			"priority":    0,
			"children":    []interface{}{},
		},
	}
	resp, err := c.post("/apis/content.halo.run/v1alpha1/categories", payload)
	if err != nil {
		return ""
	}
	return c.extractName(resp)
}

func (c *Client) createTag(displayName, slug string) string {
	payload := map[string]interface{}{
		"apiVersion": "content.halo.run/v1alpha1",
		"kind":       "Tag",
		"metadata":   map[string]interface{}{"name": toSlug(slug)},
		"spec":       map[string]interface{}{"displayName": displayName, "slug": slug},
	}
	resp, err := c.post("/apis/content.halo.run/v1alpha1/tags", payload)
	if err != nil {
		return ""
	}
	return c.extractName(resp)
}

func (c *Client) listItems(path string) ([]interface{}, error) {
	resp, err := c.get(path + "?size=100")
	if err != nil {
		return nil, err
	}
	items, _ := resp["items"].([]interface{})
	return items, nil
}

func (c *Client) publishPost(name string) (map[string]interface{}, error) {
	endpoints := []string{
		fmt.Sprintf("/apis/uc.api.content.halo.run/v1alpha1/posts/%s/publish", name),
		fmt.Sprintf("/apis/api.console.halo.run/v1alpha1/posts/%s/publish", name),
	}
	for _, ep := range endpoints {
		resp, err := c.put(ep, nil)
		if err == nil {
			return resp, nil
		}
	}
	return nil, fmt.Errorf("publish failed")
}

func (c *Client) PublishSinglePage(title, content string, slug string, publish bool) (map[string]interface{}, error) {
	if c.cfg.Halo.Token == "" {
		return nil, fmt.Errorf("HALO_TOKEN not configured")
	}

	if slug == "" {
		slug = generateSlug(title)
	}

	contentJSON := map[string]interface{}{
		"content": content,
		"raw":     content,
		"rawType": "HTML",
	}

	payload := map[string]interface{}{
		"page": map[string]interface{}{
			"apiVersion": "content.halo.run/v1alpha1",
			"kind":       "SinglePage",
			"metadata":   map[string]interface{}{"generateName": "page-"},
			"spec": map[string]interface{}{
				"title":        title,
				"slug":         slug,
				"template":     "",
				"cover":        "",
				"deleted":      false,
				"publish":      false,
				"publishTime":  "",
				"pinned":       false,
				"allowComment": true,
				"visible":      "PUBLIC",
				"priority":     0,
				"excerpt":      map[string]interface{}{"autoGenerate": true, "raw": ""},
				"htmlMetas":    []interface{}{},
			},
		},
		"content": contentJSON,
	}

	resp, err := c.post("/apis/api.console.halo.run/v1alpha1/singlepages", payload)
	if err != nil {
		return nil, err
	}

	pageName := c.extractName(resp)
	if pageName == "" {
		return nil, fmt.Errorf("no name in response")
	}

	if publish {
		_, err := c.publishSinglePage(pageName)
		if err != nil {
			return resp, fmt.Errorf("draft saved but publish failed: %w", err)
		}
	}

	return resp, nil
}

func (c *Client) publishSinglePage(name string) (map[string]interface{}, error) {
	endpoints := []string{
		fmt.Sprintf("/apis/api.console.halo.run/v1alpha1/singlepages/%s/publish", name),
	}
	for _, ep := range endpoints {
		resp, err := c.put(ep, nil)
		if err == nil {
			return resp, nil
		}
	}
	return nil, fmt.Errorf("publish single page failed")
}

func (c *Client) ListSinglePages(page, size int) ([]interface{}, error) {
	url := fmt.Sprintf("/apis/api.console.halo.run/v1alpha1/singlepages?page=%d&size=%d", page, min(size, 50))
	resp, err := c.get(url)
	if err != nil {
		return nil, err
	}
	items, _ := resp["items"].([]interface{})
	return items, nil
}

func (c *Client) post(path string, payload interface{}) (map[string]interface{}, error) {
	body, _ := json.Marshal(payload)
	req, _ := http.NewRequest("POST", c.cfg.Halo.URL+path, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.cfg.Halo.Token)

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		b, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("error %d: %s", resp.StatusCode, string(b[:min(200, len(b))]))
	}

	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)
	return result, nil
}

func (c *Client) get(path string) (map[string]interface{}, error) {
	req, _ := http.NewRequest("GET", c.cfg.Halo.URL+path, nil)
	req.Header.Set("Authorization", "Bearer "+c.cfg.Halo.Token)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		b, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("error %d: %s", resp.StatusCode, string(b[:min(200, len(b))]))
	}

	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)
	return result, nil
}

func (c *Client) put(path string, payload interface{}) (map[string]interface{}, error) {
	var bodyReader io.Reader
	if payload != nil {
		body, _ := json.Marshal(payload)
		bodyReader = bytes.NewReader(body)
	}
	req, _ := http.NewRequest("PUT", c.cfg.Halo.URL+path, bodyReader)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.cfg.Halo.Token)

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		b, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("error %d: %s", resp.StatusCode, string(b[:min(200, len(b))]))
	}

	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)
	return result, nil
}

func (c *Client) extractName(item interface{}) string {
	if m, ok := item.(map[string]interface{}); ok {
		if meta, ok := m["metadata"].(map[string]interface{}); ok {
			if name, ok := meta["name"].(string); ok {
				return name
			}
		}
	}
	return ""
}

func (c *Client) extractSpec(item interface{}) map[string]interface{} {
	if m, ok := item.(map[string]interface{}); ok {
		if spec, ok := m["spec"].(map[string]interface{}); ok {
			return spec
		}
	}
	return map[string]interface{}{}
}

func (c *Client) jsonStr(v interface{}) string {
	b, _ := json.Marshal(v)
	return string(b)
}

func generateSlug(title string) string {
	slug := strings.ToLower(title)
	re := regexp.MustCompile(`[^a-z0-9\-_\u4e00-\u9fa5]`)
	slug = re.ReplaceAllString(slug, "-")
	re = regexp.MustCompile(`-+`)
	slug = re.ReplaceAllString(slug, "-")
	slug = strings.Trim(slug, "-")
	if len(slug) > 60 {
		slug = slug[:60]
	}
	if slug == "" {
		slug = "post"
	}
	return fmt.Sprintf("%s-%d", slug, time.Now().Unix())
}

func toSlug(s string) string {
	s = strings.ToLower(s)
	re := regexp.MustCompile(`[^a-z0-9\-_\u4e00-\u9fa5]`)
	s = re.ReplaceAllString(s, "-")
	re = regexp.MustCompile(`-+`)
	s = re.ReplaceAllString(s, "-")
	s = strings.Trim(s, "-")
	if s == "" {
		s = "default"
	}
	return s
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
