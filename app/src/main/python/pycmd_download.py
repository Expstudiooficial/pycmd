"""Downloads and workspace exports.

Both land in the same folder so the Downloads tab has one place to look, and
both are careful about where they write: a URL cannot choose a path outside the
downloads folder, and a zip is built from the workspace only.
"""

from __future__ import annotations

import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

USER_AGENT = "PyCmd-Android/1.0"
TIMEOUT = 60
MAX_BYTES = 64 * 1024 * 1024

_downloads_dir = None
_workspace_dir = None


def configure(downloads_dir: str, workspace_dir: str) -> None:
    global _downloads_dir, _workspace_dir
    _downloads_dir = downloads_dir
    _workspace_dir = workspace_dir
    os.makedirs(downloads_dir, exist_ok=True)


def _safe_name(name: str) -> str:
    """Keeps a downloaded file inside the downloads folder.

    A server controls the filename it suggests, so separators and traversal are
    stripped rather than trusted.
    """
    name = os.path.basename(name.replace("\\", "/")).strip()
    name = name.replace("..", "_")
    keep = "-_. ()[]"
    cleaned = "".join(c for c in name if c.isalnum() or c in keep).strip()
    return cleaned[:120] or "download"


def _unique(directory: str, name: str) -> str:
    candidate = os.path.join(directory, name)
    if not os.path.exists(candidate):
        return candidate
    stem, extension = os.path.splitext(name)
    for index in range(2, 500):
        candidate = os.path.join(directory, f"{stem}-{index}{extension}")
        if not os.path.exists(candidate):
            return candidate
    return os.path.join(directory, f"{stem}-{int(time.time())}{extension}")


def download(url: str, progress=None) -> dict:
    """Fetches a URL into the downloads folder."""
    if _downloads_dir is None:
        return {"ok": False, "error": "downloads are not configured"}

    url = url.strip()
    if not url:
        return {"ok": False, "error": "Enter a URL."}
    if "://" not in url:
        url = "https://" + url

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {"ok": False, "error": f"Only http and https are supported (got {parsed.scheme!r})."}

    def report(message):
        if progress is not None:
            progress.onProgress(message)

    report(f"Connecting to {parsed.netloc}...")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            suggested = ""
            disposition = response.headers.get("Content-Disposition", "")
            if "filename=" in disposition:
                suggested = disposition.split("filename=")[-1].strip().strip('";')
            if not suggested:
                suggested = os.path.basename(parsed.path) or parsed.netloc
            if "." not in suggested:
                content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip()
                suggested += {
                    "text/html": ".html", "text/plain": ".txt", "application/json": ".json",
                    "text/css": ".css", "application/javascript": ".js", "text/javascript": ".js",
                    "application/zip": ".zip", "image/png": ".png", "image/jpeg": ".jpg",
                }.get(content_type, "")

            target = _unique(_downloads_dir, _safe_name(suggested))
            total = int(response.headers.get("Content-Length") or 0)
            written = 0
            report(f"Downloading {os.path.basename(target)}...")

            with open(target, "wb") as handle:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_BYTES:
                        handle.close()
                        os.remove(target)
                        return {"ok": False, "error": "That file is larger than 64 MB."}
                    handle.write(chunk)
                    if total:
                        report(f"{written * 100 // total}%  ({written // 1024} KB)")
                    else:
                        report(f"{written // 1024} KB")
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"The server returned HTTP {exc.code}."}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": f"Could not reach it: {getattr(exc, 'reason', exc)}"}
    except TimeoutError:
        return {"ok": False, "error": "The download timed out."}
    except OSError as exc:
        return {"ok": False, "error": f"Could not save it: {exc}"}

    return {"ok": True, "path": target, "name": os.path.basename(target), "bytes": written}


SOURCE_NAME = "pycmdcode"


def download_source(url: str, progress=None) -> dict:
    """PyCmd's own source, as Downloads/pycmdcode.zip with a pycmdcode/ folder inside.

    GitHub names the archive after the branch (pycmd-claude-python-...); this
    repacks it under one plain name, and replaces the copy from last time, so
    the zip in Downloads is always the current source.
    """
    if _downloads_dir is None:
        return {"ok": False, "error": "downloads are not configured"}
    import tempfile
    import zipfile

    def report(message):
        if progress is not None:
            progress.onProgress(message)

    report("Fetching the source...")
    raw = tempfile.NamedTemporaryFile(prefix="pycmd-source-", suffix=".zip", delete=False,
                                      dir=_downloads_dir)
    raw.close()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        written = 0
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response, open(raw.name, "wb") as handle:
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > 300 * 1024 * 1024:
                    return {"ok": False, "error": "The source is larger than 300 MB - something is wrong."}
                handle.write(chunk)
                report(f"{written // 1024} KB")
        report("Naming it pycmdcode...")
        target = os.path.join(_downloads_dir, SOURCE_NAME + ".zip")
        partial = target + ".part"
        files = 0
        with zipfile.ZipFile(raw.name) as source, zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as out:
            for info in source.infolist():
                parts = info.filename.split("/", 1)
                rest = parts[1] if len(parts) > 1 else ""
                if not rest:
                    continue
                name = f"{SOURCE_NAME}/{rest}"
                if info.is_dir():
                    out.writestr(zipfile.ZipInfo(name, info.date_time), b"")
                    continue
                entry = zipfile.ZipInfo(name, info.date_time)
                entry.external_attr = info.external_attr
                entry.compress_type = zipfile.ZIP_DEFLATED
                out.writestr(entry, source.read(info.filename))
                files += 1
        os.replace(partial, target)
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"The server returned HTTP {exc.code}."}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": f"Could not reach it: {getattr(exc, 'reason', exc)}"}
    except (OSError, zipfile.BadZipFile) as exc:
        return {"ok": False, "error": f"Could not save it: {exc}"}
    finally:
        try:
            os.remove(raw.name)
        except OSError:
            pass
    return {"ok": True, "path": target, "name": os.path.basename(target), "bytes": os.path.getsize(target),
            "files": files}


def adopt(path: str, name: str = "", replace: str = "") -> dict:
    """Takes a file the app has already copied out of the phone.

    Downloads was a folder only the app could put things in - a URL fetch or a
    workspace export - which made it the one place you could not simply put a
    file. The copying itself is Kotlin's, because only Kotlin can read a
    content URI; this gives it somewhere to land and a name that will not
    collide.
    """
    if _downloads_dir is None:
        return {"ok": False, "error": "downloads are not configured"}
    if not os.path.isfile(path):
        return {"ok": False, "error": "that file is not there"}

    wanted = _safe_name(name or os.path.basename(path))
    target = os.path.join(_downloads_dir, wanted)
    if replace and os.path.isfile(target):
        try:
            os.remove(target)
        except OSError as exc:
            return {"ok": False, "error": f"could not replace it: {exc}"}
    else:
        target = _unique(_downloads_dir, wanted)

    try:
        shutil.copy2(path, target)
    except OSError as exc:
        return {"ok": False, "error": f"could not save it: {exc}"}

    return {
        "ok": True,
        "path": target,
        "name": os.path.basename(target),
        "bytes": os.path.getsize(target),
        "replaced": bool(replace),
    }


def has(name: str) -> bool:
    """Whether a file of that name is already in Downloads."""
    if _downloads_dir is None:
        return False
    return os.path.isfile(os.path.join(_downloads_dir, _safe_name(name)))


def export_workspace(name: str = "") -> dict:
    """Zips the whole workspace into the downloads folder."""
    if _workspace_dir is None:
        return {"ok": False, "error": "downloads are not configured"}
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return export_folder(_workspace_dir, name or f"workspace-{stamp}.zip")


def export_folder(path: str, name: str = "") -> dict:
    """Zips one folder into the downloads folder.

    The whole workspace is rarely what you want to move to a computer - one
    project out of it usually is - so any folder can be exported on its own,
    and the archive is named after the folder unless told otherwise.
    """
    if _downloads_dir is None or _workspace_dir is None:
        return {"ok": False, "error": "downloads are not configured"}

    folder = os.path.abspath(path)
    root = os.path.abspath(_workspace_dir)
    if folder != root and not folder.startswith(root + os.sep):
        return {"ok": False, "error": "that folder is outside the workspace"}
    if not os.path.isdir(folder):
        return {"ok": False, "error": "that folder no longer exists"}

    label = name or f"{os.path.basename(folder) or 'workspace'}.zip"
    target = _unique(_downloads_dir, _safe_name(label))
    if not target.endswith(".zip"):
        target += ".zip"

    count = 0
    try:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for walked, _, files in os.walk(folder):
                # An export that swallowed the downloads folder would grow
                # every time it ran, archiving its own previous archives.
                if os.path.abspath(walked).startswith(os.path.abspath(_downloads_dir)):
                    continue
                for filename in files:
                    full = os.path.join(walked, filename)
                    relative = os.path.relpath(full, folder)
                    archive.write(full, relative)
                    count += 1
    except OSError as exc:
        return {"ok": False, "error": f"Could not build the archive: {exc}"}

    if count == 0:
        os.remove(target)
        return {"ok": False, "error": "that folder has no files in it"}

    return {
        "ok": True,
        "path": target,
        "name": os.path.basename(target),
        "files": count,
        "bytes": os.path.getsize(target),
    }


def listing() -> list:
    """Everything in the downloads folder, newest first."""
    if _downloads_dir is None or not os.path.isdir(_downloads_dir):
        return []
    rows = []
    for name in os.listdir(_downloads_dir):
        full = os.path.join(_downloads_dir, name)
        if not os.path.isfile(full):
            continue
        rows.append({
            "name": name,
            "path": full,
            "bytes": os.path.getsize(full),
            "modified": int(os.path.getmtime(full)),
        })
    rows.sort(key=lambda row: row["modified"], reverse=True)
    return rows


def delete(path: str) -> dict:
    """Removes one download. Refuses anything outside the downloads folder."""
    if _downloads_dir is None:
        return {"ok": False, "error": "downloads are not configured"}
    full = os.path.abspath(path)
    if not full.startswith(os.path.abspath(_downloads_dir) + os.sep):
        return {"ok": False, "error": "That file is not in Downloads."}
    try:
        os.remove(full)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True}


def copy_to_workspace(path: str) -> dict:
    """Moves a download into the workspace so it can be edited or served."""
    if _workspace_dir is None:
        return {"ok": False, "error": "downloads are not configured"}
    source = os.path.abspath(path)
    if not os.path.isfile(source):
        return {"ok": False, "error": "That file is gone."}
    target = _unique(_workspace_dir, _safe_name(os.path.basename(source)))
    try:
        with open(source, "rb") as src, open(target, "wb") as dst:
            while True:
                chunk = src.read(256 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "path": target, "name": os.path.basename(target)}
