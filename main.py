#!/usr/bin/env python3
"""
readerton/main.py

HTML generation from RSS feeds.

Uses BeautifulSoup to extract the main article content (clean HTML).
Generates simple static HTML pages compatible with Android 4 browsers.
Can be used standalone (local) or as a library from the Modal web app.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

# HTTP configuration
_HTTP_HEADERS = {"User-Agent": "readerton/1.0 (+https://example.com)"}
_REQUEST_TIMEOUT = 20  # seconds

# Articles with fewer than 100 words are probably paywalled
MIN_NB_WORDS = 100

logger = logging.getLogger("readerton")


def setup_logging(log_file: Optional[str] = "log.txt") -> None:
    """Configure logger with different levels for file and console."""
    logger.setLevel(logging.DEBUG)
    # Clear existing handlers to avoid duplicates on repeat calls
    logger.handlers.clear()

    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)


def load_config(config_path: str = "config.json") -> dict:
    """Load configuration from a JSON file."""
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            logger.info("Loaded configuration from %s", config_path)
            return config
    except FileNotFoundError:
        logger.error(
            "Configuration file %s not found. Please create it with 'feeds' and 'base_html_folder_name' keys.",
            config_path,
        )
        raise
    except json.JSONDecodeError as e:
        logger.error("Error parsing %s: %s", config_path, e)
        raise


def safe_filename(title: Optional[str], maxlen: int = 80) -> str:
    """Produce a filesystem-safe filename from a title or URL fragment."""
    if not title:
        title = "untitled"
    # Normalize whitespace and remove unsafe characters
    s = re.sub(r"[^\w\s-]", "", title).strip()
    s = re.sub(r"[-\s]+", "_", s)
    return s[:maxlen].strip("_")


def fetch_html(url: str, timeout: int = _REQUEST_TIMEOUT) -> Tuple[Optional[str], str]:
    """Fetch HTML content for a URL. Returns (html_text_or_None, final_url)."""
    try:
        resp = requests.get(url, headers=_HTTP_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text, resp.url
    except Exception as exc:
        logger.warning("Failed to fetch URL %s: %s", url, exc)
        return None, url


def fetch_image_as_data_uri(url: str, timeout: int = _REQUEST_TIMEOUT) -> Optional[str]:
    """Fetch an image and convert it to a data URI for embedding."""
    try:
        logger.debug("Fetching image: %s", url)
        response = requests.get(url, headers=_HTTP_HEADERS, timeout=timeout)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "image/jpeg")
        # Ensure content type is an image type
        if not content_type.startswith("image/"):
            content_type = "image/jpeg"
        encoded = base64.b64encode(response.content).decode("ascii")
        return f"data:{content_type};base64,{encoded}"
    except Exception as exc:
        logger.debug("Failed to fetch image %s: %s", url, exc)
        return None


def preprocess_html_for_images(html: str) -> str:
    """
    Preprocess HTML to fix lazy-loaded images.
    Converts data-src and similar attributes to src, and extracts images from noscript tags.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Fix lazy-loaded images - convert data-src to src
        lazy_attrs = ["data-src", "data-lazy-src", "data-original", "data-fallback-src"]
        for img in soup.find_all("img"):
            # If img has a lazy loading attribute but no src or a placeholder src
            for attr in lazy_attrs:
                if img.get(attr):
                    actual_src = img.get(attr)
                    current_src = img.get("src", "")
                    # Replace if no src or if src looks like a placeholder
                    if (
                        not current_src
                        or "placeholder" in current_src.lower()
                        or "data:image" in current_src
                    ):
                        img["src"] = actual_src
                        logger.debug("Converted %s to src: %s", attr, actual_src)
                        break

        # Extract images from noscript tags (common in Substack and similar platforms)
        for noscript in soup.find_all("noscript"):
            noscript_content = noscript.string or ""
            if noscript_content:
                # Parse the content inside noscript
                noscript_soup = BeautifulSoup(noscript_content, "html.parser")
                for img in noscript_soup.find_all("img"):
                    # Insert the image before the noscript tag
                    noscript.insert_before(img)
                    logger.debug(
                        "Extracted image from noscript: %s", img.get("src", "")
                    )

        return str(soup)
    except Exception as exc:
        logger.debug("HTML preprocessing failed: %s", exc)
        return html


def extract_main_html(
    html: str, base_url: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """
    Extract the main article HTML and a title using BeautifulSoup.
    Returns (html_string, title_or_None).
    """
    # Preprocess HTML to fix lazy-loaded images
    html = preprocess_html_for_images(html)

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title = None
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text().strip()

        # Look for Open Graph title as fallback
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title = og_title.get("content", "").strip()

        logger.debug("Extracted title: %s", title)

        # Try to find the main content using common selectors
        content = None

        # Try common article containers in order of specificity
        selectors = [
            ("article", {}),
            ("main", {}),
            ("[role='main']", {}),
            (
                "div",
                {
                    "class": lambda x: (
                        x
                        and any(
                            cls in str(x).lower()
                            for cls in [
                                "post-content",
                                "article-content",
                                "entry-content",
                                "content-body",
                                "post-body",
                            ]
                        )
                    )
                },
            ),
            (
                "div",
                {
                    "id": lambda x: (
                        x
                        and any(
                            id_part in str(x).lower()
                            for id_part in ["content", "article", "post", "main"]
                        )
                    )
                },
            ),
        ]

        for tag, attrs in selectors:
            if attrs:
                content = soup.find(tag, attrs)
            else:
                content = soup.find(tag)

            if content:
                logger.debug("Found content using selector: %s %s", tag, attrs)
                break

        # If no specific content area found, use the body
        if not content:
            content = soup.find("body")
            logger.debug("No specific content area found, using body")

        if not content:
            logger.warning("Could not find any content container")
            return "", title

        # Remove common unwanted elements
        def _class_matches_unwanted(class_attr, unwanted_list):
            if not class_attr:
                return False
            for class_name in class_attr:
                class_lower = class_name.lower()
                for unwanted in unwanted_list:
                    if class_lower == unwanted:
                        return True
                    if class_lower.startswith(unwanted + "-") or class_lower.endswith(
                        "-" + unwanted
                    ):
                        return True
                    if class_lower.startswith(unwanted + "_") or class_lower.endswith(
                        "_" + unwanted
                    ):
                        return True
            return False

        def _id_matches_unwanted(id_attr, unwanted_list):
            if not id_attr:
                return False
            id_lower = id_attr.lower()
            for unwanted in unwanted_list:
                if id_lower == unwanted:
                    return True
                if id_lower.startswith(unwanted + "-") or id_lower.endswith(
                    "-" + unwanted
                ):
                    return True
                if id_lower.startswith(unwanted + "_") or id_lower.endswith(
                    "_" + unwanted
                ):
                    return True
            return False

        unwanted_class_patterns = [
            "sidebar",
            "navigation",
            "nav",
            "menu",
            "comment",
            "ad",
            "advertisement",
            "social",
            "share",
            "related",
            "email",
        ]

        unwanted_id_patterns = [
            "sidebar",
            "navigation",
            "nav",
            "menu",
            "comment",
            "ad",
        ]

        unwanted_selectors = [
            "nav",
            "header",
            "footer",
            "aside",
            "script",
            "style",
            "noscript",
            "iframe",
            "button",
            {"class": lambda x: _class_matches_unwanted(x, unwanted_class_patterns)},
            {"id": lambda x: _id_matches_unwanted(x, unwanted_id_patterns)},
        ]

        for selector in unwanted_selectors:
            if isinstance(selector, str):
                for elem in content.find_all(selector):
                    elem.decompose()
            else:
                for elem in content.find_all(attrs=selector):
                    elem.decompose()

        # Remove image control buttons/overlays (zoom, expand, refresh icons)
        image_control_selectors = [
            "button",
            {
                "class": lambda x: (
                    x
                    and any(
                        cls in str(x).lower()
                        for cls in [
                            "zoom",
                            "expand",
                            "fullscreen",
                            "image-button",
                            "image-control",
                            "image-action",
                            "lightbox",
                        ]
                    )
                )
            },
            {"role": lambda x: x and "button" in str(x).lower()},
        ]

        for selector in image_control_selectors:
            if isinstance(selector, str):
                for elem in content.find_all(selector):
                    parent = elem.parent
                    if parent and (parent.find("img") or elem.find("img")):
                        elem.decompose()
            else:
                for elem in content.find_all(attrs=selector):
                    parent = elem.parent
                    if parent and (parent.find("img") or elem.find("img")):
                        elem.decompose()

        return str(content), title

    except Exception as exc:
        logger.warning("Content extraction failed: %s", exc)
        return "", None


def embed_images_in_html(content_html: str, base_url: Optional[str] = None) -> str:
    """
    Embed images directly in HTML as data URIs for offline viewing.
    """
    try:
        soup = BeautifulSoup(content_html, "html.parser")

        for img in soup.find_all("img"):
            src = img.get("src")
            if not src:
                continue

            # Ensure src is a string
            src_str = str(src) if not isinstance(src, str) else src

            # Skip already embedded images
            if src_str.startswith("data:"):
                continue

            # Resolve relative URLs
            if base_url and not src_str.startswith(("http://", "https://")):
                src_str = urljoin(base_url, src_str)

            # Fetch and embed the image
            data_uri = fetch_image_as_data_uri(src_str)
            if data_uri:
                img["src"] = data_uri
                logger.debug("Embedded image: %s", src_str[:50])
            else:
                # Keep original src as fallback
                logger.debug("Could not embed image, keeping original: %s", src_str)

        return str(soup)
    except Exception as exc:
        logger.warning("Image embedding failed: %s", exc)
        return content_html


def render_static_html(
    content_html: str,
    filename: str,
    title: Optional[str] = None,
    source_url: Optional[str] = None,
    base_url: Optional[str] = None,
    index_url: str = "../index.html",
) -> Tuple[bool, int]:
    """
    Render a static HTML page from content HTML.
    Compatible with Android 4 browsers (uses simple CSS, no modern features).
    Returns (success, word_count).
    """
    try:
        # Embed images as data URIs
        content_html = embed_images_in_html(content_html, base_url)

        # Remove duplicated top-level title from the extracted article body.
        soup = BeautifulSoup(content_html, "html.parser")
        if title:
            normalized_title = " ".join(title.split()).strip().lower()
        else:
            normalized_title = ""

        if normalized_title:
            first_h1 = soup.find("h1")
            if first_h1:
                h1_text = (
                    " ".join(first_h1.get_text(" ", strip=True).split()).strip().lower()
                )
                if h1_text == normalized_title:
                    first_h1.decompose()

        content_html = str(soup)

        # Count words for metadata (after title de-duplication)
        text_content = soup.get_text()
        word_count = len(text_content.split())

        # skip if less than MIN_NB_WORDS words (it's probably a paid article!)
        if word_count < MIN_NB_WORDS:
            return True, 0

        # Escape title for HTML
        safe_title = (
            (title or "Article")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        # Build the full HTML page with Android 4 compatible CSS
        html_page = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=2.0, user-scalable=yes">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>{safe_title}</title>
    <style type="text/css">
        * {{
            -webkit-box-sizing: border-box;
            box-sizing: border-box;
            -webkit-text-stroke: 0;
            -webkit-font-smoothing: antialiased;
        }}
        html {{
            font-size: 100%;
        }}
        body {{
            font-family: Georgia, "Times New Roman", Times, serif;
            font-size: 20px;
            font-weight: 400;
            line-height: 1.55;
            letter-spacing: 0.01em;
            color: #222;
            background-color: #fff;
            margin: 0;
            padding: 15px;
            max-width: 1200px;
            margin-left: auto;
            margin-right: auto;
        }}
        /* Prevent faux bold on all text elements */
        body, p, div, span, li, td, th, blockquote, figcaption {{
            font-weight: 400 !important;
            -webkit-text-stroke: 0 !important;
        }}
        b, strong {{
            font-weight: 400;
        }}
        h1, h2, h3, h4, h5, h6 {{
            font-family: Arial, Helvetica, sans-serif;
            font-weight: 700;
            line-height: 1.3;
            color: #222;
            margin-top: 1.2em;
            margin-bottom: 0.6em;
        }}
        h1 {{
            font-size: 1.6em;
            border-bottom: 2px solid #333;
            padding-bottom: 0.3em;
        }}
        h2 {{
            font-size: 1.4em;
        }}
        h3 {{
            font-size: 1.2em;
        }}
        p {{
            margin: 0 0 1em 0;
            text-align: left;
        }}
        a {{
            color: #0066cc;
            text-decoration: underline;
        }}
        a:visited {{
            color: #551a8b;
        }}
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 1em auto;
            border: 1px solid #ddd;
        }}
        figure {{
            margin: 1em 0;
            padding: 0;
        }}
        figcaption {{
            font-size: 0.9em;
            color: #666;
            text-align: center;
            margin-top: 0.5em;
        }}
        blockquote {{
            margin: 1em 0;
            padding: 0.5em 1em;
            border-left: 4px solid #ccc;
            background-color: #f9f9f9;
            font-style: italic;
        }}
        pre, code {{
            font-family: "Courier New", Courier, monospace;
            background-color: #f4f4f4;
            border: 1px solid #ddd;
        }}
        pre {{
            padding: 10px;
            overflow: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        code {{
            padding: 2px 4px;
            font-size: 0.9em;
        }}
        pre code {{
            padding: 0;
            border: none;
            background: none;
        }}
        ul, ol {{
            margin: 1em 0;
            padding-left: 2em;
        }}
        li {{
            margin-bottom: 0.5em;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 1em 0;
        }}
        th, td {{
            border: 1px solid #ccc;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f4f4f4;
        }}
        hr {{
            border: none;
            border-top: 1px solid #ccc;
            margin: 2em 0;
        }}
        .article-header {{
            margin-bottom: 1.5em;
            padding-bottom: 1em;
            border-bottom: 1px solid #eee;
        }}
        .article-title {{
            margin-top: 0;
            margin-bottom: 0.5em;
        }}
        .article-meta {{
            font-size: 0.85em;
            color: #666;
        }}
        .article-meta a {{
            color: #666;
        }}
        .article-content {{
            margin-top: 1em;
        }}
        .back-link {{
            display: block;
            margin-top: 2em;
            padding-top: 1em;
            border-top: 1px solid #eee;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="article-header">
        <div class="article-meta">
            {word_count} words{f' | <a href="{source_url}">Original source</a>' if source_url else ""}
        </div>
        <h1 class="article-title">{safe_title}</h1>
    </div>
    <div class="article-content">
        {content_html}
    </div>
    <div class="back-link">
        <a href="{index_url}">&larr; Back to index</a>
    </div>
</body>
</html>
"""

        # Write the HTML file
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_page)

        logger.debug("Generated HTML: %s (%d words)", filename, word_count)
        return True, word_count
    except Exception as exc:
        logger.warning("Failed to render HTML %s: %s", filename, exc)
        return False, 0


def generate_html_from_url(
    url: str,
    filename: str,
    title: Optional[str] = None,
    index_url: str = "../index.html",
) -> Tuple[bool, int]:
    """
    Generate a static HTML page from a URL.

    Strategy:
      1. Fetch HTML (requests)
      2. Extract main content (BeautifulSoup)
      3. Render as simple static HTML
      4. If rendering fails, log and skip

    Returns (success, word_count).
    """
    html_text, final_url = fetch_html(url)
    base_url = final_url or url

    if html_text:
        content_html, extracted_title = extract_main_html(html_text, base_url=base_url)
        # Use extracted title if no title provided
        if not title and extracted_title:
            title = extracted_title
        # Pass sanitized/cleaned HTML to renderer
        success, word_count = render_static_html(
            content_html,
            filename,
            title=title,
            source_url=url,
            base_url=base_url,
            index_url=index_url,
        )
        if success:
            return True, word_count
        else:
            logger.error(
                "Failed to render HTML for %s.",
                filename,
            )
            return False, 0

    # No HTML fetched; cannot generate page
    logger.error("No HTML fetched for %s; cannot generate page.", url)
    return False, 0


def generate_html_index(base_folder: str = "articles", url_prefix: str = "") -> None:
    """
    Generate a static HTML index page with links to all articles, organized by
    feed and sorted by date.  Compatible with older browsers (Android 4).

    Includes a form with an Update Feeds button and per-article checkboxes for
    removal.  The form POSTs to ``/update``.

    Parameters
    ----------
    base_folder:
        Absolute or relative path to the articles root directory.
    url_prefix:
        String prepended to article hrefs.  Use ``""`` when the index lives
        inside *base_folder* (local mode) and ``"articles/"`` when the index
        is served at ``/`` (Modal mode).
    """
    # Collect all articles organized by feed
    article_data: dict[str, list[dict]] = {}

    base_folder_abs = os.path.abspath(base_folder)
    if not os.path.exists(base_folder_abs):
        logger.warning("Base folder does not exist: %s", base_folder_abs)
        return

    # Get all subdirectories (feed folders)
    feed_names = [
        d
        for d in os.listdir(base_folder_abs)
        if os.path.isdir(os.path.join(base_folder_abs, d))
    ]

    for feed_name in feed_names:
        domain_folder = os.path.join(base_folder_abs, feed_name)
        article_files: list[dict] = []

        for filename in os.listdir(domain_folder):
            if filename.endswith(".html") and filename != "index.html":
                filepath = os.path.join(domain_folder, filename)

                # Extract date from filename (format: YYYY-MM-DD_...)
                date_match = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
                date_str = date_match.group(1) if date_match else "1970-01-01"

                # Extract word count (format: ..._{X}w_...)
                word_match = re.search(r"_(\d+)w_", filename)
                word_count = word_match.group(1) if word_match else "?"

                # Get file size
                file_size = os.path.getsize(filepath)
                size_kb = file_size / 1024

                # Extract title (everything after date and word count)
                display_title = filename
                display_title = re.sub(r"^\d{4}-\d{2}-\d{2}_\d+w_", "", display_title)
                display_title = display_title.replace(".html", "").replace("_", " ")

                article_files.append(
                    {
                        "filename": filename,
                        "title": display_title,
                        "date": date_str,
                        "word_count": word_count,
                        "size_kb": size_kb,
                        "relative_path": f"{feed_name}/{filename}",
                    }
                )

        # Sort by date (newest first)
        article_files.sort(key=lambda x: x["date"], reverse=True)
        article_data[feed_name] = article_files

    # -------------------------------------------------------------------
    # Build HTML
    # -------------------------------------------------------------------
    total_articles = sum(len(arts) for arts in article_data.values())
    total_sources = len([f for f in article_data.values() if f])

    parts: list[str] = []

    # ----- Head & CSS (plain string – no f-string brace escaping needed) -----
    parts.append("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex, nofollow">
    <title>Readerton</title>
    <style type="text/css">
        * {
            -webkit-box-sizing: border-box;
            box-sizing: border-box;
        }
        body {
            font-family: Arial, Helvetica, sans-serif;
            max-width: 1400px;
            margin: 20px auto;
            padding: 0 15px;
            background-color: #f5f5f5;
            color: #333;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #34495e;
            margin-top: 30px;
            border-bottom: 2px solid #95a5a6;
            padding-bottom: 5px;
        }
        .controls {
            background: #2c3e50;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            overflow: hidden;
        }
        .update-btn {
            background: #27ae60;
            color: #fff;
            border: 2px solid #1e8449;
            padding: 12px 24px;
            font-size: 1.1em;
            font-weight: bold;
            cursor: pointer;
            border-radius: 4px;
        }
        .controls-help {
            margin-left: 15px;
            font-size: 0.9em;
            color: #bdc3c7;
        }
        .feed-section {
            background: white;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .article-list {
            list-style: none;
            padding: 0;
            overflow: hidden;
        }
        .article-item {
            padding: 10px;
            border-left: 4px solid #3498db;
            background-color: #ecf0f1;
            margin-bottom: 10px;
            float: left;
            width: 48%;
            margin-right: 2%;
            -webkit-box-sizing: border-box;
            box-sizing: border-box;
        }
        .article-item:nth-child(2n) {
            margin-right: 0;
        }
        .remove-cb {
            float: left;
            margin: 3px 8px 0 0;
        }
        .article-link {
            color: #2980b9;
            text-decoration: none;
            font-weight: bold;
            font-size: 1.1em;
        }
        .article-meta {
            color: #7f8c8d;
            font-size: 0.9em;
            margin-top: 5px;
        }
        .date {
            font-weight: bold;
            color: #555;
        }
        .stats {
            background: #3498db;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #7f8c8d;
            font-size: 0.9em;
        }
    </style>
</head>
<body>""")

    # ----- Page title, form start, controls & stats (dynamic) -----
    parts.append(f"""    <h1>Readerton</h1>
    <form method="POST" action="/update" id="mainform"
          onsubmit="var b=document.getElementById('updatebtn');b.value='Processing... please wait';b.disabled=true;">
        <div class="controls">
            <input type="submit" value="Update Feeds" id="updatebtn" class="update-btn">
            <span class="controls-help">Check articles to remove, then click Update Feeds</span>
        </div>
        <div class="stats">
            <strong>Total Articles:</strong> {total_articles} | <strong>Sources:</strong> {total_sources}
        </div>""")

    # ----- Feed sections with checkboxes -----
    cb_counter = 0
    for feed_name, article_files in sorted(article_data.items()):
        if not article_files:
            continue

        parts.append(f"""        <div class="feed-section">
            <h2>{feed_name}</h2>
            <ul class="article-list">""")

        # Two-column, column-wise distribution (same layout as before)
        mid_point = (len(article_files) + 1) // 2
        left_column = article_files[:mid_point]
        right_column = article_files[mid_point:]

        for i in range(mid_point):
            # Left column item
            article = left_column[i]
            cb_id = f"cb_{cb_counter}"
            cb_counter += 1
            parts.append(
                f"""                <li class="article-item">
                    <input type="checkbox" name="remove" value="{article["relative_path"]}" id="{cb_id}" class="remove-cb">
                    <a href="{url_prefix}{article["relative_path"]}" class="article-link">{article["title"]}</a>
                    <div class="article-meta">
                        <span class="date">{article["date"]}</span> |
                        {article["word_count"]} words |
                        {article["size_kb"]:.1f} KB
                    </div>
                </li>"""
            )

            # Right column item (if it exists)
            if i < len(right_column):
                article = right_column[i]
                cb_id = f"cb_{cb_counter}"
                cb_counter += 1
                parts.append(
                    f"""                <li class="article-item">
                    <input type="checkbox" name="remove" value="{article["relative_path"]}" id="{cb_id}" class="remove-cb">
                    <a href="{url_prefix}{article["relative_path"]}" class="article-link">{article["title"]}</a>
                    <div class="article-meta">
                        <span class="date">{article["date"]}</span> |
                        {article["word_count"]} words |
                        {article["size_kb"]:.1f} KB
                    </div>
                </li>"""
                )

        parts.append("""            </ul>
        </div>""")

    # ----- Footer & close tags -----
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts.append(f"""        <div class="footer">
            Generated on {current_time}
        </div>
    </form>
</body>
</html>""")

    html_content = "\n".join(parts)

    # Write HTML file
    index_path = os.path.join(base_folder, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info("Generated HTML index: %s", index_path)


def process_feeds(
    feeds: dict,
    base_folder: str = "articles",
    index_url: str = "../index.html",
) -> None:
    """
    Main loop: parse feeds, check state, generate HTML pages for new entries,
    update state.

    Parameters
    ----------
    feeds:
        Mapping of feed_name -> feed_url.
    base_folder:
        Root directory where article sub-folders and state.json live.
    index_url:
        URL used in each article's "Back to index" link.
    """
    os.makedirs(base_folder, exist_ok=True)

    # State tracking
    state_path = os.path.join(base_folder, "state.json")
    seen_ids_old: set = set()
    seen_ids_new: set = set()
    try:
        with open(state_path, "r") as state_file:
            seen_ids_old = set(json.load(state_file))
    except Exception:
        pass

    for feed_name, feed_url in feeds.items():
        logger.info("Processing feed: %s (%s)", feed_name, feed_url)
        feed = feedparser.parse(feed_url)

        # Create subfolder using feed name
        domain_folder = os.path.join(os.path.abspath(base_folder), feed_name)
        os.makedirs(domain_folder, exist_ok=True)

        for entry in feed.entries:
            entry_id = getattr(entry, "id", None) or getattr(entry, "link", None)

            title = (
                getattr(entry, "title", None)
                or getattr(entry, "summary", None)
                or entry_id
            )
            link = getattr(entry, "link", None)
            logger.debug("Entry: %s (%s)", title, link)

            if not link:
                logger.warning("Skipping entry without link: %s", title)
                continue

            # Skip already-seen items
            if entry_id in seen_ids_old:
                logger.debug("Already processed entry: %s", entry_id)
                continue

            # Get the published date if available
            date_str = ""
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                date_obj = datetime(*entry.published_parsed[:6])
                date_str = date_obj.strftime("%Y-%m-%d")
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                date_obj = datetime(*entry.updated_parsed[:6])
                date_str = date_obj.strftime("%Y-%m-%d")
            else:
                date_str = datetime.now().strftime("%Y-%m-%d")

            filename_base = safe_filename(title)
            if not filename_base:
                parsed = urlparse(link)
                filename_base = (parsed.netloc + parsed.path).replace("/", "_")

            # Create temporary filename without word count
            temp_filename = os.path.join(
                domain_folder,
                f"temp_{filename_base[:60].strip().replace(' ', '_')}.html",
            )

            seen_ids_new.add(entry_id)

            # Generate HTML page
            try:
                ok, word_count = generate_html_from_url(
                    link, temp_filename, title, index_url=index_url
                )
                if not ok:
                    logger.error("Failed to generate HTML for %s", link)
                    continue
                if ok and word_count == 0:
                    logger.info(
                        "Skipped article (less than %d words): %s",
                        MIN_NB_WORDS,
                        link,
                    )
                    continue

                # Rename file to include date and word count
                final_filename = os.path.join(
                    domain_folder,
                    f"{date_str}_{word_count}w_{filename_base[:60].strip().replace(' ', '_')}.html",
                )
                os.rename(temp_filename, final_filename)
                logger.info(
                    "New article: %s",
                    f"{domain_folder}/{os.path.basename(final_filename)}",
                )

            except Exception as exc:
                logger.exception(
                    "Unexpected error generating HTML for %s: %s", link, exc
                )
                # Clean up temp file if it exists
                if os.path.exists(temp_filename):
                    try:
                        os.remove(temp_filename)
                    except Exception:
                        pass
                continue

    # Persist state – merge old + new to avoid forgetting previously seen entries
    try:
        seen_ids_all = seen_ids_old | seen_ids_new
        with open(state_path, "w") as state_file:
            json.dump(list(seen_ids_all), state_file)
    except Exception:
        pass


def main() -> None:
    """Entry-point for standalone (local) usage."""
    setup_logging("log.txt")
    config = load_config("config.json")
    feeds = config.get("feeds", {})
    base_folder = config.get(
        "base_html_folder_name", config.get("base_pdf_folder_name", "articles")
    )
    if not feeds:
        logger.warning("No feeds configured in config.json")
    process_feeds(feeds=feeds, base_folder=base_folder)
    generate_html_index(base_folder=base_folder)


if __name__ == "__main__":
    main()
