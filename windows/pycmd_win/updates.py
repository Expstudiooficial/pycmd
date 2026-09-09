"""Where new versions come from.

The phone build reads ``dist/latest.json`` from the repository and installs the
APK over itself. Windows needs its own manifest, because the two are different
artefacts on different schedules: ``dist-windows/latest.json`` describes the
exe, and nothing here will ever offer somebody an APK.

What this does *not* do is install anything by itself. An app that silently
replaces its own exe while you are using it is an app that eventually replaces
it with something broken while you are using it. PyCmd downloads the new one to
the Downloads folder, checks its hash against the manifest, and tells you where
it is. Replacing the old exe is one deliberate step you take.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request

from . import store

# The repository was renamed from space_dodge-1.0 to pycmd. GitHub redirects
# the old address, so builds already out there keep working - but that
# redirect only lasts while nobody creates a new repository under the old
# name, and an update channel should not depend on that staying true.
MANIFEST_URL = (
    "https://raw.githubusercontent.com/expstudiooficial/pycmd/"
    "windowsmain/dist-windows/latest.json"
)

TIMEOUT = 20
# How much of a download to read at a time. Big enough not to be silly, small
# enough that a progress bar moves.
CHUNK = 256 * 1024


def _fetch(url: str, timeout=TIMEOUT) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "PyCmd-Windows"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def check(current_build: int) -> dict:
    """Asks whether there is a newer build. Never raises."""
    try:
        raw = _fetch(MANIFEST_URL)
    except (urllib.error.URLError, OSError, ValueError) as error:
        return {"ok": False, "error": f"could not reach the update manifest: {error}"}

    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        return {"ok": False, "error": f"the update manifest is not readable: {error}"}

    try:
        build = int(manifest.get("build", 0))
    except (TypeError, ValueError):
        return {"ok": False, "error": "the update manifest has no build number"}

    return {
        "ok": True,
        "newer": build > int(current_build),
        "build": build,
        "version": manifest.get("version", ""),
        "notes": manifest.get("notes", ""),
        "url": manifest.get("url", ""),
        "sha256": manifest.get("sha256", ""),
        "bytes": manifest.get("bytes", 0),
        "released": manifest.get("releasedAt", ""),
        "manifest": manifest,
    }


def download(manifest: dict, progress=None) -> dict:
    """Fetches the new exe into Downloads and checks its hash.

    The hash check is not optional and not a warning: a build whose bytes do
    not match what the manifest promised is deleted rather than left on the
    disk looking installable.
    """
    url = str(manifest.get("url", ""))
    expected = str(manifest.get("sha256", "")).lower()
    if not url:
        return {"ok": False, "error": "that manifest has no download address"}
    if not expected:
        return {"ok": False, "error": "that manifest has no checksum, so it will not be trusted"}

    name = os.path.basename(urllib.parse.urlsplit(url).path) or "PyCmd.exe"
    target = os.path.join(store.folder("downloads"), name)
    digest = hashlib.sha256()
    total = int(manifest.get("bytes", 0) or 0)
    read = 0

    try:
        request = urllib.request.Request(url, headers={"User-Agent": "PyCmd-Windows"})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response, \
                open(target, "wb") as handle:
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                handle.write(chunk)
                digest.update(chunk)
                read += len(chunk)
                if progress:
                    progress(read, total)
    except (urllib.error.URLError, OSError) as error:
        _remove(target)
        return {"ok": False, "error": f"the download failed: {error}"}

    actual = digest.hexdigest()
    if actual != expected:
        _remove(target)
        return {
            "ok": False,
            "error": "the download did not match its checksum, so it has been deleted",
            "expected": expected, "actual": actual,
        }

    return {"ok": True, "path": target, "bytes": read, "sha256": actual}


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def start_background_check(host) -> None:
    """Looks once, quietly, a moment after start-up.

    Quietly means: a machine with no connection gets no error, because it did
    not ask a question. Only a genuine newer build says anything.
    """
    def work():
        from . import host as host_module

        result = check(host_module.BUILD)
        if result.get("ok") and result.get("newer"):
            host.emit("update-available", **{
                k: result[k] for k in ("version", "build", "notes", "url", "sha256", "bytes")
            })

    timer = threading.Timer(4.0, work)
    timer.daemon = True
    timer.start()

