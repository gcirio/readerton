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


# Configure logger
logging.basicConfig(filename="log.txt", level="DEBUG")
logger = logging.getLogger("readerton")

# Feeds to process
FEEDS = [
    "https://www.wheresyoured.at/feed",
    # add more feeds as desired
]


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
) -> bool:
    """
    Render PDF using WeasyPrint from HTML string.
    base_url should be set so relative assets (images/CSS) are resolvable.
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
        HTML(string=content_html, base_url=base_url).write_pdf(
            filename, stylesheets=[css] if css else None
        )
        logger.info("Generated PDF: %s", filename)
        return True
    except Exception as exc:
        logger.warning("Failed to render PDF %s: %s", filename, exc)
        return False


def generate_pdf_from_url(url: str, filename: str, title: Optional[str] = None) -> bool:
    """
    Generate a PDF from a URL without using a browser backend.

    Strategy:
      1. Fetch HTML (requests)
      2. Extract main content (readability)
      3. Render with WeasyPrint
      4. If rendering fails, log and skip
    """
    html_text, final_url = fetch_html(url)
    base_url = final_url or url

    if html_text:
        content_html, extracted_title = extract_main_html(html_text, base_url=base_url)
        # Pass sanitized/cleaned HTML to WeasyPrint
        if render_pdf_weasy(content_html, filename, base_url=base_url):
            return True
        else:
            logger.error(
                "WeasyPrint failed to render PDF for %s and no fallback is configured.",
                filename,
            )
            return False

    # No HTML fetched; cannot generate PDF
    logger.error("No HTML fetched for %s; cannot generate PDF.", url)
    return False


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

    for feed_url in FEEDS:
        logger.info("Processing feed: %s", feed_url)
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            entry_id = getattr(entry, "id", None) or getattr(entry, "link", None)

            title = (
                getattr(entry, "title", None)
                or getattr(entry, "summary", None)
                or entry_id
            )
            link = getattr(entry, "link", None)
            logger.info("Entry: %s (%s)", title, link)

            if not link:
                logger.warning("Skipping entry without link: %s", title)
                continue

            # If using state tracking, skip seen items
            if entry_id in seen_ids:
                logger.debug("Already processed entry: %s", entry_id)
                continue

            filename_base = safe_filename(title)
            if not filename_base:
                parsed = urlparse(link)
                filename_base = (parsed.netloc + parsed.path).replace("/", "_")
            filename = os.path.abspath(
                f"./{filename_base[:80].strip().replace(' ', '_')}.pdf"
            )

            # Generate PDF
            try:
                ok = generate_pdf_from_url(link, filename, title)
                if not ok:
                    logger.error("Failed to generate PDF for %s", link)
                    continue
            except Exception as exc:
                logger.exception(
                    "Unexpected error generating PDF for %s: %s", link, exc
                )
                continue

            # Optional: upload to S3 and update seen state
            # if s3:
            #     try:
            #         s3.upload_file(filename, bucket_name, f"books/{os.path.basename(filename)}")
            #         logger.info("Uploaded PDF to S3: %s", filename)
            #     except Exception as exc:
            #         logger.warning("Failed to upload %s to S3: %s", filename, exc)
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
