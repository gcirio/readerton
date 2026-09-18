"""
readerton/modal_app.py

Modal scheduled job for Readerton.

Processes RSS feeds, generates static HTML pages and an index, then uploads
everything to pCloud (into /Public Folder/readerton).

The job runs daily at 9 PM Paris time.

Deploy
------
    modal deploy modal_app.py

Manual trigger
--------------
    modal run modal_app.py::update
"""

import logging
import os
from urllib.parse import quote_plus

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
        "lxml",
        "fastapi[standard]",
    )
    .add_local_file("main.py", "/root/main.py")
    .add_local_file("config.json", "/root/config.json")
)

VOLUME_PATH = "/data"
CONFIG_PATH = "/root/config.json"

# Europe
PCLOUD_ENDPOINT = "https://eapi.pcloud.com"

logger = logging.getLogger("readerton.pcloud")

WEB_STATUS_QUERY_PARAM = "message"

# ---------------------------------------------------------------------------
# pCloud helpers
# ---------------------------------------------------------------------------


def pcloud_open_session(username: str, password: str):
    """
    Open a keep-alive requests.Session and authenticate with pCloud using
    SHA1 digest authentication.

    All subsequent calls on the returned session reuse the same connection
    and require no further credentials.
    """
    import hashlib

    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )

    username_lower_bytes = username.lower().encode("utf-8")
    password_bytes = password.encode("utf-8")

    # Fetch digest
    resp = session.get(f"{PCLOUD_ENDPOINT}/getdigest", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("result", 0) != 0:
        raise RuntimeError(f"getdigest failed: {data}")
    digest = data["digest"]

    digest_bytes = digest.encode("utf-8")
    inner = hashlib.sha1(username_lower_bytes).hexdigest().encode("utf-8")
    password_digest = hashlib.sha1(password_bytes + inner + digest_bytes).hexdigest()

    resp = session.get(
        f"{PCLOUD_ENDPOINT}/userinfo",
        params={
            "getauth": 1,
            "logout": 1,
            "username": username,
            "digest": digest,
            "passworddigest": password_digest,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("result", 0) != 0:
        raise RuntimeError(f"pCloud auth failed: {data}")

    session.mount(PCLOUD_ENDPOINT, HTTPAdapter(max_retries=retries))
    logger.info("pCloud digest auth successful for %s", username)
    return session


_ALWAYS_UPLOAD = {"index.html", "state.json", "removed_articles.json"}


def pcloud_sync(
    session,
    local_folder: str,
    remote_base_path: str,
    new_rel_paths: list[str],
    removed_rel_paths: set[str],
) -> None:
    """
    Sync local changes to pCloud over an already-authenticated session.

    - Uploads *new_rel_paths* (paths relative to *local_folder*).
    - Always re-uploads ``index.html``, ``state.json``, and ``removed_articles.json``.
    - Deletes each path in *removed_rel_paths* from the remote.
    """
    import requests

    # Ensure base folder exists
    resp = session.get(
        f"{PCLOUD_ENDPOINT}/createfolderifnotexists",
        params={"path": remote_base_path},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("result", 0) != 0:
        raise RuntimeError(
            f"createfolderifnotexists failed for {remote_base_path}: {data}"
        )

    def _upload(rel_path: str) -> None:
        local_path = os.path.join(local_folder, rel_path)
        if not os.path.exists(local_path):
            logger.warning("Local file missing, skipping upload: %s", rel_path)
            return
        subdir = os.path.dirname(rel_path)
        remote_dir = f"{remote_base_path}/{subdir}" if subdir else remote_base_path
        if subdir:
            r = session.get(
                f"{PCLOUD_ENDPOINT}/createfolderifnotexists",
                params={"path": remote_dir},
                timeout=30,
            )
            r.raise_for_status()
        with open(local_path, "rb") as fh:
            r = session.post(
                f"{PCLOUD_ENDPOINT}/uploadfile",
                data={"path": remote_dir},
                files={"file": (os.path.basename(rel_path), fh)},
                timeout=120,
            )
        r.raise_for_status()
        rdata = r.json()
        if rdata.get("result", 0) != 0:
            logger.error("uploadfile failed for %s: %s", rel_path, rdata)
        else:
            logger.info("Uploaded: %s", rel_path)

    # Upload new articles
    for rel_path in new_rel_paths:
        _upload(rel_path)

    # Always re-upload metadata/index files
    for fname in _ALWAYS_UPLOAD:
        _upload(fname)

    # Delete removed articles from pCloud
    deleted = 0
    for rel_path in removed_rel_paths:
        remote_path = f"{remote_base_path}/{rel_path}"
        try:
            r = session.get(
                f"{PCLOUD_ENDPOINT}/deletefile",
                params={"path": remote_path},
                timeout=30,
            )
            r.raise_for_status()
        except requests.exceptions.Timeout as exc:
            logger.warning(
                "Timed out deleting %s after retries; will retry next run: %s",
                rel_path,
                exc,
            )
            continue
        rdata = r.json()
        if rdata.get("result", 0) == 0:
            deleted += 1
            logger.info("Deleted: %s", rel_path)
        elif rdata.get("result") == 2009:  # file not found – already gone
            logger.debug("Already absent on remote: %s", rel_path)
        else:
            logger.error("deletefile failed for %s: %s", rel_path, rdata)

    logger.info(
        "pCloud sync complete – %d new uploaded, %d removed deleted",
        len(new_rel_paths),
        deleted,
    )


# ---------------------------------------------------------------------------
# Scheduled Modal function
# ---------------------------------------------------------------------------


def _load_readerton():
    import sys

    sys.path.insert(0, "/root")

    import main as readerton

    return readerton


def _get_base_folder(readerton) -> str:
    config = readerton.load_config(CONFIG_PATH)
    folder_name = config.get(
        "base_html_folder_name",
        config.get("base_pdf_folder_name", "articles"),
    )
    base_folder = os.path.join(VOLUME_PATH, folder_name)
    os.makedirs(base_folder, exist_ok=True)
    return base_folder


def _render_web_index(message: str | None = None) -> str:
    readerton = _load_readerton()
    readerton.setup_logging(log_file=None)
    logger.setLevel(logging.INFO)

    base_folder = _get_base_folder(readerton)
    previous_message = os.environ.get("READERTON_STATUS_MESSAGE")

    try:
        if message:
            os.environ["READERTON_STATUS_MESSAGE"] = message
        elif "READERTON_STATUS_MESSAGE" in os.environ:
            del os.environ["READERTON_STATUS_MESSAGE"]

        readerton.generate_html_index(
            base_folder=base_folder,
            url_prefix="",
            interactive=True,
        )

        index_path = os.path.join(base_folder, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    finally:
        if previous_message is None:
            os.environ.pop("READERTON_STATUS_MESSAGE", None)
        else:
            os.environ["READERTON_STATUS_MESSAGE"] = previous_message


@app.function(
    image=image,
    volumes={VOLUME_PATH: volume},
    timeout=900,
    secrets=[modal.Secret.from_name("pcloud-credentials")],
    schedule=modal.Cron("0 19 * * *"),  # 19:00 UTC ≈ 21:00 Europe/Paris (CET)
)
def update():
    """Process feeds, generate static HTML index, upload to pCloud."""
    readerton = _load_readerton()

    readerton.setup_logging(log_file=None)  # console-only inside Modal
    logger.setLevel(logging.INFO)

    config = readerton.load_config(CONFIG_PATH)
    feeds = config.get("feeds", {})
    base_folder = _get_base_folder(readerton)

    # 1. Fetch new feed entries and generate article pages ----------------
    new_articles = readerton.process_feeds(
        feeds=feeds,
        base_folder=base_folder,
        index_url="../index.html",
    )

    # 2. (Re)generate the static index page, excluding removed articles ---
    readerton.generate_html_index(
        base_folder=base_folder,
        url_prefix="",
        interactive=False,
    )

    # 3. Persist volume so state survives across invocations --------------
    volume.commit()

    # 4. Upload to pCloud -------------------------------------------------
    username = os.environ["PCLOUD_USERNAME"]
    password = os.environ["PCLOUD_PASSWORD"]

    removed_articles = readerton.load_removed_articles(base_folder=base_folder)

    session = pcloud_open_session(username, password)
    pcloud_sync(
        session=session,
        local_folder=base_folder,
        remote_base_path="/Public Folder/readerton",
        new_rel_paths=new_articles,
        removed_rel_paths=removed_articles,
    )

    logger.info("Readerton update complete.")


@app.function(
    image=image,
    volumes={VOLUME_PATH: volume},
    timeout=300,
)
@modal.asgi_app()
def web():
    from fastapi import FastAPI, Form
    from fastapi.responses import HTMLResponse, RedirectResponse

    web_app = FastAPI()

    @web_app.get("/", response_class=HTMLResponse)
    async def index(message: str | None = None):
        return HTMLResponse(_render_web_index(message))

    @web_app.post("/remove")
    async def remove(remove: list[str] = Form(default=[])):
        readerton = _load_readerton()
        readerton.setup_logging(log_file=None)
        logger.setLevel(logging.INFO)

        base_folder = _get_base_folder(readerton)
        selected = [path for path in remove if path and path.strip()]
        if not selected:
            redirect_to = (
                f"/?{WEB_STATUS_QUERY_PARAM}={quote_plus('No articles were selected.')}"
            )
            return RedirectResponse(url=redirect_to, status_code=303)

        readerton.add_removed_articles(selected, base_folder=base_folder)
        readerton.generate_html_index(
            base_folder=base_folder,
            url_prefix="",
            interactive=True,
        )
        volume.commit()

        count = len(selected)
        noun = "article" if count == 1 else "articles"
        redirect_to = (
            f"/?{WEB_STATUS_QUERY_PARAM}="
            f"{quote_plus(f'Flagged {count} {noun} for removal.')}"
        )
        return RedirectResponse(url=redirect_to, status_code=303)

    return web_app
