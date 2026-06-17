# -*- coding: utf-8 -*-
"""
根据文章标题和摘要生成封面图，并支持上传到 Halo。

封面来源：
- web_search：网上搜索适配图片，下载后上传
  - bing_cn：必应中国 (cn.bing.com)，国内可直接访问，无需代理
  - duckduckgo：DuckDuckGo 图片搜索（国外环境）
- ollama：本地 Ollama 文生图
- sd_webui：Stable Diffusion WebUI (A1111)
"""
import base64
import json
import os
import re
import subprocess
import tempfile
from typing import Optional, Tuple
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from flask import current_app


def _build_cover_query(
    title: str,
    excerpt: str,
    content: Optional[str] = None,
    tags: Optional[list] = None,
) -> str:
    """
    构建与文章内容相关的封面搜索/生成描述。
    优先用 DeepSeek 提取关键词；否则用标题+标签+内容摘要。
    """
    if current_app.config.get("DEEPSEEK_API_KEY"):
        try:
            from app.services.deepseek import extract_cover_keywords

            full_content = (content or excerpt or "").strip()
            if full_content:
                keywords, err = extract_cover_keywords(title, full_content)
                if keywords and not err:
                    return keywords.strip()[:100]
        except Exception:
            pass

    parts = [title]
    if tags:
        parts.extend(tags[:5])
    text = re.sub(r"<[^>]+>", " ", (content or excerpt or ""))
    text = re.sub(r"\s+", " ", text).strip()[:200]
    if text:
        parts.append(text)
    return " ".join(parts).strip()[:100] or title


def _build_image_prompt(title: str, excerpt: str, content: Optional[str] = None, tags: Optional[list] = None) -> str:
    """根据标题和内容构建图片生成 prompt。"""
    desc = _build_cover_query(title, excerpt, content, tags)
    return f"Blog cover image, modern minimal style, professional, about: {desc}"[:500]


def _search_cover_from_bing_cn(query: str) -> Tuple[Optional[str], Optional[str]]:
    """
    从必应中国 (cn.bing.com) 搜索图片。国内可直接访问，无需代理。
    Returns: (image_url, error_message)
    """
    try:
        url = f"https://cn.bing.com/images/async?q={quote(query)}&first=0&count=35"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        # Bing 返回 HTML 中 murl 以 &quot; 转义，用正则提取
        murl_match = re.search(
            r'&quot;murl&quot;:&quot;(https?://[^&]+)&quot;',
            r.text,
        )
        if murl_match:
            return murl_match.group(1), None
        # 备用：解析 div.iusc 的 data-m
        soup = BeautifulSoup(r.text, "html.parser")
        for div in soup.select("div.iusc"):
            data_m = div.get("data-m")
            if not data_m:
                continue
            try:
                obj = json.loads(data_m.replace("&quot;", '"'))
                murl = obj.get("murl") or obj.get("turl")
                if murl and isinstance(murl, str) and murl.startswith("http"):
                    return murl, None
            except (json.JSONDecodeError, TypeError):
                continue
        return None, "未找到合适图片"
    except requests.exceptions.RequestException as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)


def _search_cover_from_duckduckgo(query: str) -> Tuple[Optional[str], Optional[str]]:
    """DuckDuckGo 图片搜索，国外环境可用。"""
    try:
        from duckduckgo_search import DDGS

        with DDGS(timeout=30) as ddgs:
            results = list(ddgs.images(query, max_results=5))
        for r in results:
            url = r.get("image") or r.get("url") or r.get("thumbnail")
            if url and isinstance(url, str) and url.startswith("http"):
                return url, None
        return None, "未找到合适图片"
    except ImportError:
        return None, "请安装 duckduckgo-search: pip install duckduckgo-search"
    except Exception as e:
        return None, str(e)


def _search_cover_from_web(query: str) -> Tuple[Optional[str], Optional[str]]:
    """
    从网上搜索适配的图片。默认使用必应中国（国内无需代理）。
    Returns: (image_url, error_message)
    """
    engine = (
        current_app.config.get("COVER_WEB_ENGINE") or "bing_cn"
    ).lower().strip()
    if engine == "duckduckgo":
        return _search_cover_from_duckduckgo(query)
    return _search_cover_from_bing_cn(query)


def _generate_via_ollama(
    prompt: str, ollama_url: Optional[str] = None
) -> Tuple[Optional[bytes], Optional[str]]:
    """
    使用 Ollama 本地图片模型生成。支持 API 或 subprocess。
    Returns: (image_bytes, error_message)
    """
    url = (ollama_url or current_app.config.get("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
    model = current_app.config.get("OLLAMA_IMAGE_MODEL") or "x/z-image-turbo"

    # 方式1：尝试 HTTP API（Ollama 图片模型可能通过 /api/generate 返回）
    try:
        r = requests.post(
            f"{url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        if r.status_code != 200:
            return None, f"Ollama API 错误: {r.status_code}"
        data = r.json()
        # 图片模型可能返回 images 数组或 response 中的 base64
        images = data.get("images")
        if isinstance(images, list) and images:
            b64 = images[0] if isinstance(images[0], str) else images[0].get("data")
            if b64:
                return base64.b64decode(b64), None
        resp = data.get("response", "")
        if resp and len(resp) > 100:
            try:
                return base64.b64decode(resp), None
            except Exception:
                pass
    except requests.exceptions.RequestException as e:
        pass  # 继续尝试 subprocess

    # 方式2：subprocess 调用 ollama run（图片会保存到当前目录）
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            proc = subprocess.run(
                ["ollama", "run", model, prompt],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode != 0:
                return None, proc.stderr or f"ollama 退出码 {proc.returncode}"
            # 查找生成的图片
            for f in sorted(os.listdir(tmpdir), key=lambda x: -os.path.getmtime(os.path.join(tmpdir, x))):
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    path = os.path.join(tmpdir, f)
                    with open(path, "rb") as fp:
                        return fp.read(), None
        return None, "Ollama 未生成图片文件"
    except FileNotFoundError:
        return None, "未找到 ollama 命令，请确保已安装 Ollama"
    except subprocess.TimeoutExpired:
        return None, "Ollama 生成超时"
    except Exception as e:
        return None, str(e)


def _generate_via_sd_webui(
    prompt: str, sd_webui_url: Optional[str] = None
) -> Tuple[Optional[bytes], Optional[str]]:
    """
    使用 Stable Diffusion WebUI (A1111) API 生成。
    需启动 WebUI 并添加 --api 参数。
    Returns: (image_bytes, error_message)
    """
    base_url = (sd_webui_url or current_app.config.get("SD_WEBUI_URL") or "http://localhost:7860").rstrip("/")
    url = f"{base_url}/sdapi/v1/txt2img"
    payload = {
        "prompt": prompt,
        "negative_prompt": "blurry, low quality, distorted",
        "steps": 20,
        "width": 768,
        "height": 512,
        "cfg_scale": 7,
    }
    try:
        r = requests.post(url, json=payload, timeout=120)
        if r.status_code != 200:
            return None, f"SD WebUI API 错误: {r.status_code} - {r.text[:200]}"
        data = r.json()
        images = data.get("images")
        if not images:
            return None, "SD WebUI 未返回图片"
        return base64.b64decode(images[0]), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def generate_cover_image_bytes(
    title: str,
    excerpt: str,
    backend: str = "ollama",
    ollama_url: Optional[str] = None,
    sd_webui_url: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[list] = None,
) -> Tuple[Optional[bytes], Optional[str]]:
    """
    根据文章生成封面图，返回图片字节。
    backend: ollama | sd_webui
    content/tags 用于构建与文章相关的 prompt。
    Returns: (image_bytes, error_message)
    """
    backend = (backend or current_app.config.get("COVER_IMAGE_BACKEND") or "ollama").lower().strip()
    prompt = _build_image_prompt(title, excerpt, content=content, tags=tags)

    if backend == "sd_webui":
        return _generate_via_sd_webui(prompt, sd_webui_url)
    return _generate_via_ollama(prompt, ollama_url)


def upload_cover_to_halo_from_url(image_url: str) -> Tuple[Optional[str], Optional[str]]:
    """从 URL 上传图片到 Halo（用于返回 URL 的后端）。"""
    halo_url = (current_app.config.get("HALO_URL") or "").rstrip("/")
    halo_token = current_app.config.get("HALO_TOKEN")
    if not halo_url or not halo_token:
        return None, "未配置 HALO_URL 或 HALO_TOKEN"

    headers = {"Authorization": f"Bearer {halo_token}", "Content-Type": "application/json"}
    payload = {"url": image_url}
    urls = [
        f"{halo_url}/apis/uc.api.storage.halo.run/v1alpha1/attachments/-/upload-from-url",
        f"{halo_url}/apis/api.console.halo.run/v1alpha1/attachments/-/upload-from-url",
    ]
    for upload_url in urls:
        try:
            r = requests.post(upload_url, headers=headers, json=payload, timeout=60)
            if r.status_code in (200, 201):
                data = r.json()
                url = (
                    (data.get("status") or {}).get("url")
                    or (data.get("spec") or {}).get("url")
                    or data.get("url")
                    or (data.get("status") or {}).get("permalink")
                )
                if url:
                    return str(url), None
                return None, "Halo 附件响应中未找到 URL"
        except requests.exceptions.RequestException:
            continue
    return None, "上传到 Halo 失败"


def upload_cover_to_halo_from_bytes(
    image_bytes: bytes, filename: str = "cover.png"
) -> Tuple[Optional[str], Optional[str]]:
    """通过 multipart 上传图片字节到 Halo。"""
    halo_url = (current_app.config.get("HALO_URL") or "").rstrip("/")
    halo_token = current_app.config.get("HALO_TOKEN")
    if not halo_url or not halo_token:
        return None, "未配置 HALO_URL 或 HALO_TOKEN"

    headers = {"Authorization": f"Bearer {halo_token}"}
    urls = [
        f"{halo_url}/apis/uc.api.storage.halo.run/v1alpha1/attachments/-/upload",
        f"{halo_url}/apis/api.console.halo.run/v1alpha1/attachments/-/upload",
        f"{halo_url}/apis/uc.api.storage.halo.run/v1alpha1/attachments/upload",
        f"{halo_url}/apis/api.console.halo.run/v1alpha1/attachments/upload",
    ]
    for upload_url in urls:
        try:
            files = {"file": (filename, image_bytes, "image/png")}
            r = requests.post(upload_url, headers=headers, files=files, timeout=60)
            if r.status_code in (200, 201):
                data = r.json()
                url = (
                    (data.get("status") or {}).get("url")
                    or (data.get("spec") or {}).get("url")
                    or data.get("url")
                    or (data.get("status") or {}).get("permalink")
                )
                if url:
                    return str(url), None
        except requests.exceptions.RequestException:
            continue
    return None, "上传到 Halo 失败（multipart）"


def get_cover_for_post(
    title: str,
    excerpt: str,
    cover_source: str = "ollama",
    ollama_url: Optional[str] = None,
    sd_webui_url: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[list] = None,
) -> Optional[str]:
    """
    根据文章获取封面图并上传到 Halo，返回可作为 spec.cover 的 URL。
    cover_source: web_search | ollama | sd_webui
    content/tags 用于构建与文章内容相关的搜索或生成描述。
    """
    cover_source = (cover_source or "ollama").lower().strip()
    query = _build_cover_query(title, excerpt, content=content, tags=tags)

    if cover_source == "web_search":
        img_url, err = _search_cover_from_web(query)
        if err or not img_url:
            current_app.logger.info("cover_web_search_skip", extra={"reason": err or "no url"})
            return None
        # 先下载图片字节再 multipart 上传（Halo 的 upload-from-url 可能无法抓取部分外链）
        try:
            r = requests.get(img_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                current_app.logger.warning("cover_download_failed", extra={"status": r.status_code})
                return None
            img_bytes = r.content
            if len(img_bytes) < 100:
                return None
            ext = "png"
            ct = r.headers.get("Content-Type", "")
            if "jpeg" in ct or "jpg" in ct:
                ext = "jpg"
            elif "webp" in ct:
                ext = "webp"
            cover_url, up_err = upload_cover_to_halo_from_bytes(img_bytes, f"cover.{ext}")
            if up_err or not cover_url:
                current_app.logger.warning("cover_upload_failed", extra={"reason": up_err})
                return None
            return cover_url
        except requests.exceptions.RequestException as e:
            current_app.logger.warning("cover_download_failed", extra={"error": str(e)})
            return None

    img_bytes, err = generate_cover_image_bytes(
        title, excerpt,
        backend=cover_source,
        ollama_url=ollama_url,
        sd_webui_url=sd_webui_url,
        content=content,
        tags=tags,
    )
    if err or not img_bytes:
        current_app.logger.info("cover_image_skip", extra={"reason": err or "no bytes"})
        return None
    cover_url, up_err = upload_cover_to_halo_from_bytes(img_bytes, "cover.png")
    if up_err or not cover_url:
        current_app.logger.warning("cover_upload_failed", extra={"reason": up_err})
        return None
    return cover_url
