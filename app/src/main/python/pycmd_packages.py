"""On-device package installer.

Chaquopy resolves its own ``pip`` requirements at build time, so this module
covers the other half: installing extra packages *after* the APK is on the
phone. It handles universal wheels (``py3-none-any``) pulled straight from
PyPI, which is what nearly every pure-Python library ships.

Packages with compiled C extensions cannot be installed this way — they need an
Android-specific wheel built against the NDK — so those are reported with a
clear message instead of a confusing failure halfway through.
"""

from __future__ import annotations

import importlib
import io
import json
import os
import re
import shutil
import site
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

PYPI_JSON = "https://pypi.org/pypi/{name}/json"
PYPI_JSON_VERSIONED = "https://pypi.org/pypi/{name}/{version}/json"
USER_AGENT = "PyCmd-Android/1.0 (+https://github.com/Expstudiooficial/pycmd)"
_TIMEOUT = 60

_target_dir: str | None = None
_manifest_path: str | None = None


def configure(target_dir: str) -> None:
    """Point the installer at the writable site-packages directory."""
    global _target_dir, _manifest_path
    _target_dir = target_dir
    _manifest_path = os.path.join(target_dir, ".pycmd-packages.json")
    os.makedirs(target_dir, exist_ok=True)
    if target_dir not in sys.path:
        sys.path.insert(0, target_dir)
    site.addsitedir(target_dir)


def _require_configured() -> str:
    if _target_dir is None:
        raise RuntimeError("pycmd_packages.configure() has not been called")
    return _target_dir


def _read_manifest() -> dict:
    if not _manifest_path or not os.path.exists(_manifest_path):
        return {}
    try:
        with open(_manifest_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_manifest(manifest: dict) -> None:
    if not _manifest_path:
        return
    tmp = _manifest_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    os.replace(tmp, _manifest_path)


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return response.read()


def _normalise(name: str) -> str:
    return name.replace("_", "-").replace(".", "-").strip().lower()


def _pick_wheel(release_files: list) -> dict | None:
    """Prefer a universal wheel; fall back to any py3 wheel that is ABI-free."""
    best = None
    for item in release_files:
        if item.get("packagetype") != "bdist_wheel":
            continue
        filename = item.get("filename", "")
        if filename.endswith("-py3-none-any.whl") or filename.endswith("-py2.py3-none-any.whl"):
            return item
        if filename.endswith("-none-any.whl") and best is None:
            best = item
    return best


def info(name: str) -> dict:
    """What PyPI says about a package, and whether this device can have it.

    Worth asking before installing rather than after: a package with only
    compiled wheels fails at the end of a download, and "there is no wheel for
    Android" is a better answer given up front. Also carries the recent
    versions, so pinning one does not need a trip to a browser.
    """
    name = name.strip()
    if not name:
        return {"ok": False, "error": "Enter a package name."}
    try:
        payload = json.loads(_fetch(PYPI_JSON.format(name=urllib.parse.quote(name))))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"ok": False, "error": f"PyPI has nothing called '{name}'."}
        return {"ok": False, "error": f"PyPI returned HTTP {exc.code}."}
    except (urllib.error.URLError, ValueError) as exc:
        return {"ok": False, "error": f"Could not reach PyPI: {exc}"}

    payload_info = payload.get("info", {})
    latest = payload_info.get("version", "")
    releases = payload.get("releases", {})
    wheel = _pick_wheel(payload.get("urls", []) or releases.get(latest, []))

    # Newest first, and only versions that actually published something.
    versions = [key for key, files in releases.items() if files]
    versions.sort(key=_version_key, reverse=True)

    return {
        "ok": True,
        "name": payload_info.get("name", name),
        "version": latest,
        "summary": payload_info.get("summary") or "",
        "home_page": payload_info.get("home_page") or payload_info.get("project_url") or "",
        "requires_python": payload_info.get("requires_python") or "",
        "license": (payload_info.get("license") or "")[:60],
        "installable": wheel is not None,
        "why_not": "" if wheel else (
            "This one ships only compiled wheels, which have to be built for "
            "Android's exact ABI and Python version. There is nothing on PyPI "
            "for a phone to fetch."
        ),
        "size": int((wheel or {}).get("size", 0)),
        "versions": versions[:12],
    }


def _version_key(version: str) -> tuple:
    """Sorts versions the way people expect, without packaging installed."""
    parts = []
    for chunk in re.split(r"[._-]", version):
        parts.append((0, int(chunk)) if chunk.isdigit() else (1, 0))
    return tuple(parts)


def install(name: str, version: str | None = None, progress=None) -> dict:
    """Download and unpack a universal wheel into the writable site-packages."""
    target = _require_configured()
    name = name.strip()
    if not name:
        return {"ok": False, "error": "Enter a package name."}

    def report(message: str) -> None:
        if progress is not None:
            progress.onProgress(message)

    quoted = urllib.parse.quote(name)
    url = (
        PYPI_JSON_VERSIONED.format(name=quoted, version=urllib.parse.quote(version))
        if version
        else PYPI_JSON.format(name=quoted)
    )

    report(f"Resolving {name}...")
    try:
        payload = json.loads(_fetch(url))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            what = f"{name} {version}" if version else name
            return {"ok": False, "error": f"No release found for '{what}' on PyPI."}
        return {"ok": False, "error": f"PyPI returned HTTP {exc.code}."}
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        return {"ok": False, "error": f"Network error: {reason}"}
    except ValueError:
        return {"ok": False, "error": "PyPI sent a malformed response."}

    info = payload.get("info", {})
    dist_name = info.get("name", name)
    resolved_version = info.get("version", version or "")
    wheel = _pick_wheel(payload.get("urls", []))
    if wheel is None:
        return {
            "ok": False,
            "error": (
                f"{dist_name} {resolved_version} has no universal wheel. It ships compiled "
                "code, which needs an Android build — install it from the bundled set instead."
            ),
        }

    report(f"Downloading {wheel['filename']} ...")
    try:
        blob = _fetch(wheel["url"])
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        return {"ok": False, "error": f"Download failed: {reason}"}

    report("Unpacking...")
    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        return {"ok": False, "error": "The downloaded wheel is corrupt."}

    members: list[str] = []
    try:
        for entry in archive.infolist():
            entry_name = entry.filename
            # Refuse absolute or parent-escaping paths: a wheel is a zip, and a
            # zip can lie about where its members belong.
            if entry_name.startswith("/") or ".." in entry_name.split("/"):
                return {"ok": False, "error": f"Wheel contains an unsafe path: {entry_name}"}
            destination = os.path.abspath(os.path.join(target, entry_name))
            if not destination.startswith(os.path.abspath(target) + os.sep):
                return {"ok": False, "error": f"Wheel contains an unsafe path: {entry_name}"}
            archive.extract(entry, target)
            if not entry.is_dir():
                members.append(entry_name)
    except (OSError, zipfile.BadZipFile) as exc:
        return {"ok": False, "error": f"Could not unpack the wheel: {exc}"}
    finally:
        archive.close()

    manifest = _read_manifest()
    manifest[_normalise(dist_name)] = {
        "name": dist_name,
        "version": resolved_version,
        "summary": (info.get("summary") or "").strip(),
        "files": members,
    }
    _write_manifest(manifest)

    importlib.invalidate_caches()
    report(f"Installed {dist_name} {resolved_version}")
    return {
        "ok": True,
        "name": dist_name,
        "version": resolved_version,
        "files": len(members),
    }


def uninstall(name: str) -> dict:
    """Remove a package this installer put on the device."""
    target = _require_configured()
    manifest = _read_manifest()
    key = _normalise(name)
    record = manifest.get(key)
    if record is None:
        return {"ok": False, "error": f"'{name}' was not installed by PyCmd."}

    directories: set[str] = set()
    for relative in record.get("files", []):
        path = os.path.abspath(os.path.join(target, relative))
        if not path.startswith(os.path.abspath(target) + os.sep):
            continue
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass
        directories.add(os.path.dirname(path))

    # Importing the package leaves __pycache__ behind, which is not in the
    # manifest and would otherwise keep every directory from being pruned.
    for directory in directories:
        cache = os.path.join(directory, "__pycache__")
        if os.path.isdir(cache):
            shutil.rmtree(cache, ignore_errors=True)

    # Deepest first, so a tree empties from the leaves up.
    for directory in sorted(directories, key=len, reverse=True):
        try:
            if os.path.isdir(directory) and not os.listdir(directory):
                os.rmdir(directory)
        except OSError:
            pass

    manifest.pop(key, None)
    _write_manifest(manifest)
    importlib.invalidate_caches()
    return {"ok": True, "name": record.get("name", name)}


def installed() -> list:
    """Packages installed on-device, newest listing first."""
    manifest = _read_manifest()
    rows = [
        {
            "name": record.get("name", key),
            "version": record.get("version", ""),
            "summary": record.get("summary", ""),
            "files": len(record.get("files", [])),
        }
        for key, record in manifest.items()
    ]
    return sorted(rows, key=lambda row: row["name"].lower())


def bundled() -> list:
    """Packages baked into the APK at build time."""
    names = []
    for module in ("requests", "flask", "rich", "numpy", "pillow", "PIL"):
        try:
            importlib.import_module("PIL" if module == "pillow" else module)
        except Exception:
            continue
        names.append("pillow" if module == "PIL" else module)
    # PIL and pillow are the same distribution.
    unique = []
    for name in names:
        if name not in unique:
            unique.append(name)
    return unique

