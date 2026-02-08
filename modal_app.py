"""
readerton/modal_app.py

Modal web application for Readerton.

Serves the article index and individual article pages from a persistent
Modal Volume.  Provides a POST /update endpoint that removes checked
articles and fetches new feed entries.

Deploy
------
    modal deploy modal_app.py

Local dev server
----------------
    modal serve modal_app.py
"""

import os

import modal

# ---------------------------------------------------------------------------
# Modal resources
# ---------------------------------------------------------------------------

app = modal.App("readerton")

volume = modal.Volume.from_name("readerton-data", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "beautifulsoup4",
        "feedparser",
        "requests",
        "fastapi[standard]",
        "lxml",
    )
    .add_local_file("main.py", "/root/main.py")
    .add_local_file("config.json", "/root/config.json")
)

VOLUME_PATH = "/data"
CONFIG_PATH = "/root/config.json"

# ---------------------------------------------------------------------------
# Web application
# ---------------------------------------------------------------------------


@app.function(
    image=image,
    volumes={VOLUME_PATH: volume},
    timeout=900,
    # Keep one container warm so the index loads instantly
    # min_containers=1,
)
@modal.asgi_app()
def web():
    import sys

    sys.path.insert(0, "/root")

    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, RedirectResponse

    import main as readerton

    readerton.setup_logging(log_file=None)  # console only inside Modal

    fastapi_app = FastAPI(title="Readerton")

    def _base_folder() -> str:
        config = readerton.load_config(CONFIG_PATH)
        folder_name = config.get(
            "base_html_folder_name",
            config.get("base_pdf_folder_name", "articles"),
        )
        return os.path.join(VOLUME_PATH, folder_name)

    # ------------------------------------------------------------------
    # GET /  –  serve the index page
    # ------------------------------------------------------------------
    @fastapi_app.get("/", response_class=HTMLResponse)
    async def index():
        volume.reload()
        index_path = os.path.join(_base_folder(), "index.html")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as fh:
                return HTMLResponse(fh.read())

        # No index yet – show a minimal page with the Update button
        return HTMLResponse(
            "<!DOCTYPE html>"
            "<html><head>"
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            "<title>Readerton</title>"
            "<style>body{font-family:Arial,sans-serif;max-width:800px;"
            "margin:40px auto;padding:0 15px;}"
            ".update-btn{background:#27ae60;color:#fff;border:2px solid #1e8449;"
            "padding:12px 24px;font-size:1.1em;font-weight:bold;cursor:pointer;"
            "border-radius:4px;}</style>"
            "</head><body>"
            "<h1>Readerton</h1>"
            "<p>No articles yet.  Click the button below to fetch feeds.</p>"
            '<form method="POST" action="/update">'
            '<input type="submit" value="Update Feeds" class="update-btn">'
            "</form>"
            "</body></html>"
        )

    # ------------------------------------------------------------------
    # GET /articles/{feed}/{filename}  –  serve an individual article
    # ------------------------------------------------------------------
    @fastapi_app.get("/articles/{feed}/{filename}", response_class=HTMLResponse)
    async def article(feed: str, filename: str):
        volume.reload()
        # Prevent directory traversal
        if ".." in feed or ".." in filename:
            return HTMLResponse("Forbidden", status_code=403)

        filepath = os.path.join(_base_folder(), feed, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as fh:
                return HTMLResponse(fh.read())

        return HTMLResponse("Not found", status_code=404)

    # ------------------------------------------------------------------
    # POST /update  –  remove checked articles, process feeds, rebuild index
    # ------------------------------------------------------------------
    @fastapi_app.post("/update")
    async def update(request: Request):
        form = await request.form()
        removals = form.getlist("remove")

        config = readerton.load_config(CONFIG_PATH)
        feeds = config.get("feeds", {})
        base_folder = _base_folder()
        os.makedirs(base_folder, exist_ok=True)

        # 1. Remove articles the user checked for deletion
        for rel_path in removals:
            safe = os.path.normpath(rel_path)
            if ".." in safe:
                continue
            abs_path = os.path.join(base_folder, safe)
            if os.path.isfile(abs_path):
                os.remove(abs_path)
                readerton.logger.info("Removed article: %s", abs_path)

        # 2. Fetch new feed entries
        readerton.process_feeds(
            feeds=feeds,
            base_folder=base_folder,
            index_url="/",
        )

        # 3. Regenerate the index page
        readerton.generate_html_index(
            base_folder=base_folder,
            url_prefix="articles/",
        )

        # 4. Persist volume changes
        volume.commit()

        # Redirect back to the index (303 See Other → browser does GET)
        return RedirectResponse("/", status_code=303)

    return fastapi_app
