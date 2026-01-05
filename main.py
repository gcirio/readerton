#!/usr/bin/env python3
"""
readerton/main.py

PDF generation from RSS feeds

Uses WeasyPrint - renders HTML/CSS without a full browser
Uses readability to extract the main article content (clean HTML)
=> Won't work if text is page is generated via javascript?
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urlparse

import boto3
import feedparser
import requests
from bs4 import BeautifulSoup
from weasyprint import CSS, HTML, default_url_fetcher

# Optional HTTP client/session configuration
_HTTP_HEADERS = {"User-Agent": "readerton-pdf/1.0 (+https://example.com)"}
_REQUEST_TIMEOUT = 20  # seconds

# Optional AWS S3 client - keep but commented usage by default
s3 = boto3.client("s3")

# Configure logger with different levels for file and console
logger = logging.getLogger("readerton")
logger.setLevel(logging.DEBUG)

# File handler - DEBUG level
file_handler = logging.FileHandler("log.txt")
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_formatter)

# Console handler - INFO level
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(message)s")
console_handler.setFormatter(console_formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def load_config() -> dict:
    """Load configuration from config.json file."""
    config_file = "config.json"
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
            logger.info("Loaded configuration from %s", config_file)
            return config
    except FileNotFoundError:
        logger.error(
            "Configuration file %s not found. Please create it with 'feeds' and 'base_pdf_folder_name' keys.",
            config_file,
        )
        raise
    except json.JSONDecodeError as e:
        logger.error("Error parsing %s: %s", config_file, e)
        raise


# Load configuration
config = load_config()
FEEDS = config.get("feeds", {})
base_pdf_folder_name = config.get("base_pdf_folder_name", "pdfs")

if not FEEDS:
    logger.warning("No feeds configured in config.json")


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


def custom_url_fetcher(url):
    """
    Custom URL fetcher for WeasyPrint to fetch resources (images, CSS, etc.)
    with proper headers and timeout settings.
    """
    try:
        logger.debug("Fetching resource: %s", url)
        response = requests.get(url, headers=_HTTP_HEADERS, timeout=_REQUEST_TIMEOUT)
        response.raise_for_status()
        return {
            "string": response.content,
            "mime_type": response.headers.get(
                "Content-Type", "application/octet-stream"
            ),
            "encoding": response.encoding,
            "redirected_url": response.url,
        }
    except Exception as exc:
        logger.debug("Failed to fetch resource %s: %s", url, exc)
        # Fall back to default fetcher
        return default_url_fetcher(url)


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
                    "class": lambda x: x
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
                },
            ),
            (
                "div",
                {
                    "id": lambda x: x
                    and any(
                        id_part in str(x).lower()
                        for id_part in ["content", "article", "post", "main"]
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
        unwanted_selectors = [
            "nav",
            "header",
            "footer",
            "aside",
            {
                "class": lambda x: x
                and any(
                    cls in str(x).lower()
                    for cls in [
                        "sidebar",
                        "navigation",
                        "nav",
                        "menu",
                        "comment",
                        "ad",
                        "advertisement",
                    ]
                )
            },
            {
                "id": lambda x: x
                and any(
                    id_part in str(x).lower()
                    for id_part in [
                        "sidebar",
                        "navigation",
                        "nav",
                        "menu",
                        "comment",
                        "ad",
                    ]
                )
            },
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
                "class": lambda x: x
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
            },
            {"role": lambda x: x and "button" in str(x).lower()},
        ]

        for selector in image_control_selectors:
            if isinstance(selector, str):
                # Remove buttons that are siblings or parents of images
                for elem in content.find_all(selector):
                    # Check if this button is near an image
                    parent = elem.parent
                    if parent and (parent.find("img") or elem.find("img")):
                        elem.decompose()
            else:
                for elem in content.find_all(attrs=selector):
                    # Check if this element is near an image
                    parent = elem.parent
                    if parent and (parent.find("img") or elem.find("img")):
                        elem.decompose()

        return str(content), title

    except Exception as exc:
        logger.warning("Content extraction failed: %s", exc)
        return "", None


def render_pdf_weasy(
    content_html: str, filename: str, base_url: Optional[str] = None
) -> Tuple[bool, int]:
    """
    Render PDF using WeasyPrint from HTML string.
    base_url should be set so relative assets (images/CSS) are resolvable.
    Returns (success, page_count).
    """
    try:
        # Add a small default CSS for nicer text
        css = CSS(
            string="""
            @page { size: A4; margin: 1in; }
            body { font-family: serif; font-size: 12pt; line-height: 1.4; }
            img { max-width: 100%; height: auto; }
        """
        )
        # HTML(...) accepts string and base_url for relative resources
        # Use custom URL fetcher to fetch images with proper headers
        html_obj = HTML(
            string=content_html, base_url=base_url, url_fetcher=custom_url_fetcher
        )
        doc = html_obj.render(stylesheets=[css] if css else None)
        page_count = len(doc.pages)
        doc.write_pdf(filename)
        logger.debug("Generated PDF: %s (%d pages)", filename, page_count)
        return True, page_count
    except Exception as exc:
        logger.warning("Failed to render PDF %s: %s", filename, exc)
        return False, 0


def generate_pdf_from_url(
    url: str, filename: str, title: Optional[str] = None
) -> Tuple[bool, int]:
    """
    Generate a PDF from a URL without using a browser backend.

    Strategy:
      1. Fetch HTML (requests)
      2. Extract main content (readability)
      3. Render with WeasyPrint
      4. If rendering fails, log and skip

    Returns (success, page_count).
    """
    html_text, final_url = fetch_html(url)
    base_url = final_url or url

    if html_text:
        content_html, extracted_title = extract_main_html(html_text, base_url=base_url)
        # Pass sanitized/cleaned HTML to WeasyPrint
        success, page_count = render_pdf_weasy(
            content_html, filename, base_url=base_url
        )
        if success:
            return True, page_count
        else:
            logger.error(
                "WeasyPrint failed to render PDF for %s and no fallback is configured.",
                filename,
            )
            return False, 0

    # No HTML fetched; cannot generate PDF
    logger.error("No HTML fetched for %s; cannot generate PDF.", url)
    return False, 0


def generate_html_index():
    """
    Generate a static HTML index page with links to all PDFs, organized by feed and sorted by date.
    Compatible with older browsers (Android 6).
    """
    # Collect all PDFs organized by feed
    pdf_data = {}

    # Scan directories in the base PDF folder
    base_folder = os.path.abspath(f"./{base_pdf_folder_name}")
    if not os.path.exists(base_folder):
        logger.warning("Base PDF folder does not exist: %s", base_folder)
        return

    # Get all subdirectories (feed folders)
    feed_names = [
        d
        for d in os.listdir(base_folder)
        if os.path.isdir(os.path.join(base_folder, d))
    ]

    for feed_name in feed_names:
        domain_folder = os.path.join(base_folder, feed_name)

        pdf_files = []
        for filename in os.listdir(domain_folder):
            if filename.endswith(".pdf"):
                filepath = os.path.join(domain_folder, filename)

                # Extract date from filename (format: YYYY-MM-DD_...)
                date_match = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
                date_str = date_match.group(1) if date_match else "1970-01-01"

                # Extract page count (format: ..._{X}p_...)
                page_match = re.search(r"_(\d+)p_", filename)
                page_count = page_match.group(1) if page_match else "?"

                # Get file size
                file_size = os.path.getsize(filepath)
                size_mb = file_size / (1024 * 1024)

                # Extract title (everything after date and page count)
                title = filename
                title = re.sub(r"^\d{4}-\d{2}-\d{2}_\d+p_", "", title)
                title = title.replace(".pdf", "").replace("_", " ")

                pdf_files.append(
                    {
                        "filename": filename,
                        "title": title,
                        "date": date_str,
                        "page_count": page_count,
                        "size_mb": size_mb,
                        "relative_path": f"{feed_name}/{filename}",
                    }
                )

        # Sort by date (newest first)
        pdf_files.sort(key=lambda x: x["date"], reverse=True)
        pdf_data[feed_name] = pdf_files

    # Generate HTML
    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex, nofollow">
    <title>Readerton - PDF Archive</title>
    <style>
        body {
            font-family: Arial, sans-serif;
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
        .feed-section {
            background: white;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .pdf-list {
            list-style: none;
            padding: 0;
            column-count: 2;
            column-gap: 15px;
        }
        @media (max-width: 768px) {
            .pdf-list {
                column-count: 1;
            }
        }
        .pdf-item {
            padding: 10px;
            border-left: 4px solid #3498db;
            background-color: #ecf0f1;
            break-inside: avoid;
            margin-bottom: 10px;
        }
        .pdf-item:hover {
            background-color: #d5dbdb;
        }
        .pdf-link {
            color: #2980b9;
            text-decoration: none;
            font-weight: bold;
            font-size: 1.1em;
        }
        .pdf-link:hover {
            text-decoration: underline;
        }
        .pdf-meta {
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
<body>
    <h1>Readerton PDF Archive</h1>
"""

    # Add statistics
    total_pdfs = sum(len(pdfs) for pdfs in pdf_data.values())
    total_sources = len([f for f in pdf_data.values() if f])

    html_content += f"""    <div class="stats">
        <strong>Total PDFs:</strong> {total_pdfs} | <strong>Sources:</strong> {total_sources}
    </div>
"""

    # Add each feed section
    for feed_name, pdf_files in sorted(pdf_data.items()):
        if not pdf_files:
            continue

        html_content += f"""    <div class="feed-section">
        <h2>{feed_name}</h2>
        <ul class="pdf-list">
"""

        for pdf in pdf_files:
            html_content += f"""            <li class="pdf-item">
                <a href="{pdf["relative_path"]}" class="pdf-link">{pdf["title"]}</a>
                <div class="pdf-meta">
                    <span class="date">{pdf["date"]}</span> |
                    {pdf["page_count"]} pages |
                    {pdf["size_mb"]:.2f} MB
                </div>
            </li>
"""

        html_content += """        </ul>
    </div>
"""

    # Add footer
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html_content += f"""    <div class="footer">
        Generated on {current_time}
    </div>
</body>
</html>
"""

    # Write HTML file
    index_path = os.path.join(base_pdf_folder_name, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info("Generated HTML index: %s", index_path)


def process_feeds():
    """
    Main loop: parse feeds, check state, generate PDFs for new entries, update state
    S3 upload is optional and commented by default.
    """
    # State tracking (uncomment and configure S3 or a local file as preferred)
    seen_ids = set()
    try:
        # state_obj = s3.get_object(Bucket=bucket_name, Key="state.json")
        # seen_ids = set(json.loads(state_obj["Body"].read().decode()))
        with open("state.json", "r") as state_file:
            seen_ids = set(json.load(state_file))
    except Exception:
        pass

    for feed_name, feed_url in FEEDS.items():
        logger.info("Processing feed: %s (%s)", feed_name, feed_url)
        feed = feedparser.parse(feed_url)

        # Create subfolder using feed name
        domain_folder = os.path.abspath(f"./{base_pdf_folder_name}/{feed_name}")
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

            # If using state tracking, skip seen items
            if entry_id in seen_ids:
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

            # Create temporary filename without page count
            temp_filename = os.path.join(
                domain_folder,
                f"temp_{filename_base[:60].strip().replace(' ', '_')}.pdf",
            )

            # Generate PDF
            try:
                ok, page_count = generate_pdf_from_url(link, temp_filename, title)
                if not ok:
                    logger.error("Failed to generate PDF for %s", link)
                    continue

                # Rename file to include date and page count
                final_filename = os.path.join(
                    domain_folder,
                    f"{date_str}_{page_count}p_{filename_base[:60].strip().replace(' ', '_')}.pdf",
                )
                os.rename(temp_filename, final_filename)
                logger.info(
                    "New PDF: %s",
                    f"{domain_folder}/{os.path.basename(final_filename)}",
                )

            except Exception as exc:
                logger.exception(
                    "Unexpected error generating PDF for %s: %s", link, exc
                )
                # Clean up temp file if it exists
                if os.path.exists(temp_filename):
                    try:
                        os.remove(temp_filename)
                    except:
                        pass
                continue

            # Optional: upload to S3 and update seen state
            # if s3:
            #     try:
            #         s3.upload_file(final_filename, bucket_name, f"books/{feed_name}/{os.path.basename(final_filename)}")
            #         logger.info("Uploaded PDF to S3: %s", final_filename)
            #     except Exception as exc:
            #         logger.warning("Failed to upload %s to S3: %s", final_filename, exc)
            #

            seen_ids.add(entry_id)

    # persist state back
    try:
        # s3.put_object(Bucket=bucket_name, Key="state.json", Body=json.dumps(list(seen_ids)))
        with open("state.json", "w") as state_file:
            json.dump(list(seen_ids), state_file)
    except Exception:
        pass


def main():
    process_feeds()
    generate_html_index()


if __name__ == "__main__":
    main()
