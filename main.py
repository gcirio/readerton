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
from readability import Document
from weasyprint import CSS, HTML

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

# Feeds to process
FEEDS = {
    "wheres_your_ed": "https://www.wheresyoured.at/feed",
    "the_pragmatic_engineer_blog": "https://feeds.feedburner.com/ThePragmaticEngineer",
    "the_pragmatic_engineer_newsletter": "https://newsletter.pragmaticengineer.com/feed",
    # add more feeds as desired
}


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


def extract_main_html(
    html: str, base_url: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """
    Extract the main article HTML and a title.
    Returns (html_string, title_or_None).
    """

    try:
        doc = Document(html)
        summary = doc.summary()
        title = doc.short_title()
        if summary and summary.strip():
            logger.debug("Extracted article via readability with title: %s", title)
            return summary, title
    except Exception as exc:
        logger.debug("readability.Document extraction failed: %s", exc)

    logger.debug("readability.Document extraction failed")
    return "", ""


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
        html_obj = HTML(string=content_html, base_url=base_url)
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


def generate_index():
    # List all books in the bucket and create a dead-simple HTML list
    objs = s3.list_objects_v2(Bucket=bucket_name, Prefix="books/")
    links = [
        f'<li><a href="{obj["Key"]}">{obj["Key"]}</a></li>'
        for obj in objs.get("Contents", [])
    ]
    html = f"<html><body><h1>My Daily Reads</h1><ul>{''.join(links)}</ul></body></html>"

    s3.put_object(
        Bucket=bucket_name, Key="index.html", Body=html, ContentType="text/html"
    )


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
        domain_folder = os.path.abspath(f"./{feed_name}")
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


if __name__ == "__main__":
    main()
