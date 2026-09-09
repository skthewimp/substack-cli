"""Fail-closed boundaries for credentials, assets, and live revisions."""
import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from .errors import die

MAX_IMAGE_BYTES = 20 * 1024 * 1024


def https_origin(value):
    value = str(value).strip().rstrip("/")
    if "://" not in value:
        value = "https://" + value
    try:
        url = urlsplit(value)
        valid = (url.scheme == "https" and url.hostname and not url.username
                 and not url.password and url.port in (None, 443)
                 and not url.path and not url.query and not url.fragment)
    except ValueError:
        valid = False
    if not valid:
        die("Publication URL must be an HTTPS origin without credentials, path or custom port")
    return "https://" + url.hostname.lower()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        die("Redirect refused; verify the configured HTTPS publication origin")


def opener():
    # Do not inherit ambient proxy settings when sending account cookies.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def asset_path(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        die("Image path escapes the approved asset directory")
    if not path.is_file():
        die("Image does not exist inside the approved asset directory")
    return path


def image_bytes(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        die("Image exceeds 20 MiB limit")
    mime = ("image/png" if raw.startswith(b"\x89PNG\r\n\x1a\n") else
            "image/jpeg" if raw.startswith(b"\xff\xd8\xff") else
            "image/gif" if raw[:6] in (b"GIF87a", b"GIF89a") else
            "image/webp" if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP" else None)
    if mime is None:
        die("Only PNG, JPEG, GIF and WebP image bytes may be uploaded")
    return raw, mime


def private_json(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".substack-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(values, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def revision(record):
    fields = {key: record.get(key) for key in (
        "id", "body", "title", "subtitle", "slug", "cover_image", "post_date",
        "draft_body", "draft_title", "draft_subtitle", "is_published")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def backup(record):
    root = Path(os.environ.get("SUBSTACK_BACKUP_DIR") or
                (Path.home() / ".local/state/substack-cli/backups"))
    target = root / (str(int(record["id"])) + "-" + revision(record) + ".json")
    private_json(target, record)
    return target
