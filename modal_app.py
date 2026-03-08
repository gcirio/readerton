"""
readerton/modal_app.py

Modal scheduled job for Readerton.

Processes RSS feeds, generates static HTML pages and an index, then uploads
everything to pCloud (into /Public Folder/readerton) using digest
authentication.

The job runs daily at 9 PM Paris time.

Deploy
------
    modal deploy modal_app.py

Manual trigger
--------------
    modal run modal_app.py::update
"""

import hashlib
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

# Try EU first, then US.  Override with PCLOUD_API_HOST to skip auto-detection.
PCLOUD_ENDPOINTS = [
    "https://eapi.pcloud.com",  # Europe
    "https://api.pcloud.com",  # United States
]

logger = logging.getLogger("readerton.pcloud")

# Resolved at auth time; used by all subsequent helpers.
_active_api_base: str | None = None

WEB_STATUS_QUERY_PARAM = "message"

# ---------------------------------------------------------------------------
# pCloud helpers
# ---------------------------------------------------------------------------


def _pcloud_api_base() -> str:
    override = os.environ.get("PCLOUD_API_HOST", "").strip().rstrip("/")
    if override:
        return override
    if _active_api_base:
        return _active_api_base
    return PCLOUD_ENDPOINTS[0]


def _try_digest_auth(api: str, username: str, password: str) -> str | None:
    """
    Attempt digest auth against a single pCloud endpoint.

    Tries SHA256 first, then SHA1.  Returns an auth token on success,
    or ``None`` if login failed (result 2000).  Raises on unexpected errors.
    """
    import requests

    # Step 1 – obtain a one-time digest
    resp = requests.get(f"{api}/getdigest", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("result", 0) != 0:
        raise RuntimeError(f"getdigest failed on {api}: {data}")
    digest = data["digest"]

    # Step 2 – try SHA256 then SHA1 for the password digest
    username_lower_bytes = username.lower().encode("utf-8")
    password_bytes = password.encode("utf-8")
    digest_bytes = digest.encode("utf-8")

    candidates = []
    for hash_fn in (hashlib.sha256, hashlib.sha1):
        inner = hash_fn(username_lower_bytes).hexdigest().encode("utf-8")
        pd = hash_fn(password_bytes + inner + digest_bytes).hexdigest()
        candidates.append((hash_fn().name, pd))

    for hash_name, password_digest in candidates:
        # Need a fresh digest for each attempt (they are single-use / short-lived)
        # but within the 30-second window we can reuse the same one.
        resp = requests.get(
            f"{api}/userinfo",
            params={
                "getauth": 1,
                "logout": 1,
                "username": username,
                "digest": digest,
                "passworddigest": password_digest,
                "authexpire": 3600,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("result", 0) == 0 and data.get("auth"):
            logger.info(
                "pCloud digest auth successful on %s using %s for %s",
                api,
                hash_name,
                username,
            )
            return data["auth"]

        # result 2000 = "Log in failed" → wrong hash or wrong server, try next
        if data.get("result") == 2000:
            logger.debug(
                "Auth attempt failed on %s with %s (result 2000)", api, hash_name
            )
            # Fetch a fresh digest for the next attempt (previous may be consumed)
            resp = requests.get(f"{api}/getdigest", timeout=30)
            resp.raise_for_status()
            ddata = resp.json()
            if ddata.get("result", 0) != 0:
                raise RuntimeError(f"getdigest failed on {api}: {ddata}")
            digest = ddata["digest"]
            digest_bytes = digest.encode("utf-8")
            # Recompute remaining candidates with fresh digest
            # (only matters if there's a next candidate)
            remaining_idx = candidates.index((hash_name, password_digest)) + 1
            for i in range(remaining_idx, len(candidates)):
                h_name = candidates[i][0]
                hfn = hashlib.sha256 if h_name == "sha256" else hashlib.sha1
                inner = hfn(username_lower_bytes).hexdigest().encode("utf-8")
                candidates[i] = (
                    h_name,
                    hfn(password_bytes + inner + digest_bytes).hexdigest(),
                )
            continue

        # Any other error is unexpected
        raise RuntimeError(f"pCloud auth unexpected response on {api}: {data}")

    return None  # all attempts on this endpoint failed


def pcloud_digest_auth(username: str, password: str) -> str:
    """
    Authenticate with pCloud using digest authentication.

    Tries both EU and US endpoints, and both SHA256 and SHA1 hashing,
    to find the right combination automatically.

    Returns an auth token valid for subsequent API calls.
    Sets ``_active_api_base`` so all later helpers hit the correct server.
    """
    global _active_api_base

    override = os.environ.get("PCLOUD_API_HOST", "").strip().rstrip("/")
    endpoints = [override] if override else list(PCLOUD_ENDPOINTS)

    errors: list[str] = []
    for api in endpoints:
        logger.info("Trying pCloud endpoint %s ...", api)
        try:
            token = _try_digest_auth(api, username, password)
            if token:
                _active_api_base = api
                return token
            errors.append(f"{api}: login failed (wrong credentials or server)")
        except Exception as exc:
            errors.append(f"{api}: {exc}")
            logger.warning("pCloud auth error on %s: %s", api, exc)

    raise RuntimeError(
        "pCloud authentication failed on all endpoints. "
        "Please verify PCLOUD_USERNAME and PCLOUD_PASSWORD are correct.\n"
        + "\n".join(f"  - {e}" for e in errors)
    )


def _collect_remote_files(metadata: dict, prefix: str, result: set) -> None:
    """Recursively collect relative file paths from a listfolder metadata tree."""
    for item in metadata.get("contents", []):
        name = item["name"]
        rel = f"{prefix}/{name}" if prefix else name
        if item.get("isfolder", False):
            _collect_remote_files(item, rel, result)
        else:
            result.add(rel)


def pcloud_upload_folder(
    auth: str,
    local_folder: str,
    remote_base_path: str,
) -> None:
    """
    Upload *local_folder* to *remote_base_path* on pCloud.

    - Files that already exist remotely are **skipped**.
    - ``index.html``, ``state.json``, and ``removed_articles.json`` are **always overwritten**.
    """
    import requests

    api = _pcloud_api_base()

    # ---- Ensure destination folder exists --------------------------------
    resp = requests.get(
        f"{api}/createfolderifnotexists",
        params={"auth": auth, "path": remote_base_path},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("result", 0) not in (0,):
        raise RuntimeError(
            f"createfolderifnotexists failed for {remote_base_path}: {data}"
        )
    logger.info("Remote folder ready: %s", remote_base_path)

    # ---- List existing remote files (recursive) --------------------------
    existing_files: set[str] = set()
    resp = requests.get(
        f"{api}/listfolder",
        params={"auth": auth, "path": remote_base_path, "recursive": 1},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("result", 0) == 0:
        _collect_remote_files(data["metadata"], "", existing_files)
        logger.info(
            "Found %d existing files in %s", len(existing_files), remote_base_path
        )
    else:
        logger.warning(
            "listfolder returned result=%s – assuming empty", data.get("result")
        )

    # Files that must always be re-uploaded
    ALWAYS_OVERWRITE = {"index.html", "state.json", "removed_articles.json"}

    uploaded = 0
    skipped = 0

    for root, dirs, files in os.walk(local_folder):
        rel_root = os.path.relpath(root, local_folder)
        if rel_root == ".":
            rel_root = ""

        # Create sub-folders on the remote side
        for d in dirs:
            sub = (
                f"{remote_base_path}/{rel_root}/{d}"
                if rel_root
                else f"{remote_base_path}/{d}"
            )
            resp = requests.get(
                f"{api}/createfolderifnotexists",
                params={"auth": auth, "path": sub},
                timeout=30,
            )
            resp.raise_for_status()
            rdata = resp.json()
            if rdata.get("result", 0) != 0:
                logger.warning("Could not create remote folder %s: %s", sub, rdata)

        # Upload files
        for fname in files:
            local_path = os.path.join(root, fname)
            rel_file = f"{rel_root}/{fname}" if rel_root else fname

            should_overwrite = fname in ALWAYS_OVERWRITE
            if not should_overwrite and rel_file in existing_files:
                skipped += 1
                continue

            remote_dir = (
                f"{remote_base_path}/{rel_root}" if rel_root else remote_base_path
            )

            with open(local_path, "rb") as fh:
                resp = requests.post(
                    f"{api}/uploadfile",
                    data={"auth": auth, "path": remote_dir},
                    files={"file": (fname, fh)},
                    timeout=120,
                )
            resp.raise_for_status()
            rdata = resp.json()
            if rdata.get("result", 0) != 0:
                logger.error("uploadfile failed for %s: %s", rel_file, rdata)
            else:
                uploaded += 1
                logger.info("Uploaded: %s", rel_file)

    logger.info(
        "pCloud sync complete – uploaded %d, skipped %d existing", uploaded, skipped
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
    readerton.process_feeds(
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

    auth_token = pcloud_digest_auth(username, password)
    pcloud_upload_folder(
        auth=auth_token,
        local_folder=base_folder,
        remote_base_path="/Public Folder/readerton",
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
