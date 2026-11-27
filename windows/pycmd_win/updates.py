"""Where new versions come from.

The phone build reads ``dist/latest.json`` from the repository and installs the
APK over itself. Windows needs its own manifest, because the two are different
artefacts on different schedules: ``dist-windows/latest.json`` describes the
exe, and nothing here will ever offer somebody an APK.

5.9: updates arrive as an installer (PyCmd-Setup.exe), checked against the
manifest's SHA-256 before it runs. The installer puts PyCmd in
%LOCALAPPDATA%/Programs/PyCmd, replacing the version that is there, and
starts it again. Whether PyCmd only says so or installs by itself is a
setting (Settings > Updates): off, tell me (the default), or install.
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
        "installerUrl": manifest.get("installerUrl", ""),
        "installerSha256": manifest.get("installerSha256", ""),
        "installerBytes": manifest.get("installerBytes", 0),
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


# ---------------------------------------------------------------------------
# 5.9: installing, and checking on a schedule
# ---------------------------------------------------------------------------

MODES = ("off", "notify", "auto")
EVERY = 6 * 60 * 60          # seconds between checks while PyCmd is open
_state = {"last": 0, "result": None, "installing": False}


def install_dir() -> str:
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", "PyCmd")


def is_installed() -> bool:
    """Whether this PyCmd is the installed one rather than a loose exe."""
    import sys

    if not getattr(sys, "frozen", False):
        return False
    here = os.path.normcase(os.path.dirname(os.path.abspath(sys.executable)))
    return here == os.path.normcase(install_dir())


def settings() -> dict:
    from .features import _settings_get

    mode = _settings_get("updateMode", "notify")
    return {"mode": mode if mode in MODES else "notify", "skip": _settings_get("updateSkip", "")}


def set_mode(mode: str) -> dict:
    from .features import _settings_put

    if mode not in MODES:
        return {"ok": False, "error": f"the mode is one of {', '.join(MODES)}"}
    _settings_put("updateMode", mode)
    return {"ok": True, **settings()}


def skip(version: str) -> dict:
    from .features import _settings_put

    _settings_put("updateSkip", str(version))
    return {"ok": True}


def status(current_version: str, current_build: int) -> dict:
    result = _state["result"] or {}
    return {
        "ok": True, "version": current_version, "build": current_build,
        "installed": is_installed(), "installDir": install_dir(), **settings(),
        "lastCheck": _state["last"], "installing": _state["installing"],
        "available": result if result.get("newer") else None,
    }


def check_now(current_build: int) -> dict:
    import time as _time

    result = check(current_build)
    _state["last"] = int(_time.time())
    if result.get("ok"):
        _state["result"] = result
    return result


def install(result: dict, silent: bool = False, progress=None) -> dict:
    """Downloads the installer, checks it, and runs it. PyCmd is closed and
    started again by the installer, so on success this is the last thing
    this process does."""
    if os.name != "nt":
        return {"ok": False, "error": "installing updates only happens on Windows"}
    if not result.get("installerUrl"):
        return {"ok": False, "error": "this release has no installer; download it from the releases page"}
    if _state["installing"]:
        return {"ok": False, "error": "an update is already being installed"}
    _state["installing"] = True
    try:
        got = download({"url": result["installerUrl"], "sha256": result.get("installerSha256", ""),
                        "bytes": result.get("installerBytes", 0)}, progress)
        if not got.get("ok"):
            return got
        import subprocess

        flags = ["/VERYSILENT" if silent else "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                 "/CLOSEAPPLICATIONS", "/SP-"]
        detached = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen([got["path"], *flags], close_fds=True, creationflags=detached)
        return {"ok": True, "started": True, "path": got["path"]}
    except OSError as error:
        return {"ok": False, "error": f"the installer would not start: {error}"}
    finally:
        _state["installing"] = False


def start_background_check(host) -> None:
    """Checks a moment after start-up, then every six hours, as the setting says.

    A machine with no connection hears nothing - it did not ask a question.
    Only a newer build says anything: a pop-up, or (on "auto") the update
    itself, which closes PyCmd and opens the new one.
    """
    def once():
        from . import host as host_module

        mode = settings()
        if mode["mode"] == "off":
            return
        result = check_now(host_module.BUILD)
        if not (result.get("ok") and result.get("newer")):
            return
        if result.get("version") == mode["skip"] and mode["mode"] != "auto":
            return
        event = {k: result.get(k) for k in ("version", "build", "notes", "url", "sha256", "bytes",
                                             "installerUrl", "installerBytes")}
        if mode["mode"] == "auto" and result.get("installerUrl"):
            host.emit("update-installing", **event)
            outcome = install(result, silent=True)
            if not outcome.get("ok"):
                host.emit("update-available", **event, error=outcome.get("error", ""))
            return
        host.emit("update-available", **event)

    def loop():
        import time as _time

        _time.sleep(5)
        while True:
            try:
                once()
            except Exception as error:  # noqa: BLE001 - never take the app down
                host.log("warn", "update check failed", str(error))
            _time.sleep(EVERY)

    threading.Thread(target=loop, name="pycmd-updates", daemon=True).start()
