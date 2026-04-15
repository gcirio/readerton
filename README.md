# Readerton

RSS feed reader that fetches articles, strips them to clean readable HTML, and publishes a static site to pCloud.
The main purpose is to be able to use a (very) old E Ink reader to read blog and newsletter content. Old readers have old web browsers that can't handle the modern web (html, css, javascript, SSL, etc). Therefore, the web content needs to be converted into plain simple HTML and served from a static, non-SSL website.

## What it does

1. Reads RSS feeds defined in `config.json`
2. Fetches each article, extracts the main content, and saves it as a self-contained HTML file (images are inlined as data URIs)
3. Generates an `index.html` listing all articles
4. Uploads everything to `/Public Folder/readerton` on pCloud

Sets up job to run daily via a Modal scheduled function. A small FastAPI web UI is also deployed for browsing articles and flagging them for removal.

## Project structure

```
config.json       # feed names and URLs
main.py           # core logic (feed processing, HTML generation)
modal_app.py      # Modal app: scheduled job + web UI
```

## Configuration

Edit `config.json` to add or remove feeds:

```json
{
  "base_html_folder_name": "articles",
  "feeds": {
    "feed_name": "https://example.com/feed"
  }
}
```

## Local usage

```sh
uv run main.py
```

Articles are written to the `articles/` folder.

## Modal deployment

Set up a Modal secret named `pcloud-credentials` with `PCLOUD_USERNAME` and `PCLOUD_PASSWORD`, then:

```sh
# Deploy (or redeploy after changes)
uv run modal deploy modal_app.py

# Trigger a run manually
uv run modal run modal_app.py::update
```

## Requirements

- Python 3.11+
- A [Modal](https://modal.com) account
- A [pCloud](https://www.pcloud.com) account (Europe data center)
