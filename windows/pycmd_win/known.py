"""What PyCmd has already found on this machine, remembered between versions.

The complaint this exists to answer: installing and detecting felt like it
started from zero every single time. It did. Detection cached its answers for
the life of the process and nowhere else, so every launch re-ran fifty-one
version probes - fifty-one processes started, each waiting on a compiler to
print its banner - and every new PyCmd version began life knowing nothing
about a machine the previous one had already surveyed.

None of that was ever necessary. A compiler that was at ``C:\\ProgramData\\
chocolatey\\bin\\go.exe`` yesterday is almost certainly still there today, and
checking that a file exists costs microseconds against the tens of
milliseconds - sometimes seconds, for anything that starts a JVM - of asking
it its version.

So this file is the memory:

* it lives at ``%LOCALAPPDATA%\\PyCmd\\toolchains.json``, beside the workspace
  and the plugins rather than inside any one version's folder, so upgrading
  from 1.0.1 to 2.0 keeps everything the older build learned;
* a remembered toolchain is trusted while its file is still there and has not
  been replaced, which is checked by size and modification time - so an
  upgrade of the *compiler* is noticed and re-probed, while an unchanged one
  is answered from memory;
* anything not remembered, or remembered wrongly, falls through to a real
  probe and is written back.

It also records **who installed what**. PyCmd installing Go is a different
fact from finding Go that somebody else installed, and it matters when the
question is "may I remove this?" - the answer is yes for the first and
emphatically no for the second.

Nothing here is authoritative. If the file is missing, unreadable, corrupt or
written by a newer PyCmd than this one, every function quietly behaves as
though the machine had never been surveyed, and the app is merely slower for
one launch. A cache that can break the program it speeds up is not worth
having.
"""

from __future__ import annotations

import json
import os
import threading
import time

from . import store

# The shape written to disk. Bumped only when an older PyCmd could not read
# what a newer one writes; a file from the future is ignored rather than
# guessed at.
FORMAT = 1

NAME = "toolchains.json"

# Reentrant, and it has to be: every writer below reads through load() while
# holding it, and a plain Lock deadlocks the moment it does. Detection calls
# remember() from eight pool threads at once, so that is not a corner case -
# it is the normal path, and a plain Lock hung the first survey outright.
_lock = threading.RLock()
_loaded: dict | None = None


def path() -> str:
    """Where the memory lives - beside the workspace, not inside a version."""
    return os.path.join(store.root(), NAME)


def _blank() -> dict:
    return {"format": FORMAT, "found": {}, "installed": {}, "surveyed": 0.0}


def load(refresh: bool = False) -> dict:
    """Everything remembered. Never raises, never returns None."""
    global _loaded
    with _lock:
        if _loaded is not None and not refresh:
            return _loaded
        _loaded = _read()
        return _loaded


def _read() -> dict:
    try:
        with open(path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return _blank()
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        # Written by a different PyCmd, or by something else entirely. Start
        # again rather than reason about a shape we do not know.
        return _blank()
    for key in ("found", "installed"):
        if not isinstance(data.get(key), dict):
            data[key] = {}
    return data


def save() -> bool:
    """Writes the memory out. Returns whether it landed.

    Through a temporary and a rename, because this is written while the app is
    running and a half-written cache read at the next launch would be worse
    than no cache at all.
    """
    data = load()
    target = path()
    temporary = target + f".writing-{os.getpid()}"
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.replace(temporary, target)
        return True
    except OSError:
        try:
            os.remove(temporary)
        except OSError:
            pass
        return False


def _stamp(file_path: str) -> str:
    """A cheap fingerprint of a file: its size and when it changed.

    Not a hash. Hashing a 300 MB toolchain on every launch would cost more
    than the probes this exists to avoid, and the question being asked is
    only "is this the same file I looked at last time", for which size and
    mtime are the standard answer and are what every build system uses.
    """
    try:
        info = os.stat(file_path)
    except OSError:
        return ""
    return f"{info.st_size}:{int(info.st_mtime)}"


def remember(toolchain_id: str, found: dict) -> None:
    """Records where a toolchain is and what it said its version was."""
    if not toolchain_id or not isinstance(found, dict):
        return
    where = found.get("path") or ""
    if not where:
        # Not being installed is worth remembering too - it stops a machine
        # without Rust re-searching the whole PATH for cargo on every launch -
        # but only as an absence, with nothing to verify against.
        with _lock:
            data = load()
            data["found"][toolchain_id] = {"path": "", "version": "",
                                           "stamp": "", "seen": time.time()}
        return
    with _lock:
        data = load()
        data["found"][toolchain_id] = {
            "path": where,
            "version": found.get("version", ""),
            "stamp": _stamp(where),
            "seen": time.time(),
        }


def recall(toolchain_id: str) -> dict | None:
    """What is remembered about this toolchain, if it is still true.

    Returns None when there is nothing remembered, or when what was
    remembered no longer describes the machine - the file has gone, or has
    been replaced since it was last looked at. Either way the caller should
    probe properly.
    """
    data = load()
    row = data["found"].get(toolchain_id)
    if not isinstance(row, dict):
        return None

    where = row.get("path") or ""
    if not where:
        # A remembered absence goes stale on its own, because the whole point
        # of installing something is that it stops being absent. An hour is
        # short enough that an install made outside PyCmd is noticed soon, and
        # long enough to save the repeated PATH search that made this slow.
        if time.time() - float(row.get("seen") or 0) > 3600:
            return None
        return {"path": "", "version": "", "remembered": True}

    if not os.path.isfile(where):
        return None
    if row.get("stamp") and _stamp(where) != row.get("stamp"):
        # The toolchain was upgraded under us. Its version string is now a
        # lie, which is the one thing this cache must never tell.
        return None
    return {"path": where, "version": row.get("version", ""), "remembered": True}


def forget(toolchain_id: str = "") -> None:
    """Drops one memory, or all of them."""
    with _lock:
        data = load()
        if toolchain_id:
            data["found"].pop(toolchain_id, None)
        else:
            data["found"] = {}
    save()


def mark_installed(toolchain_id: str, how: str) -> None:
    """Notes that PyCmd installed this one, and with which package manager.

    Kept apart from `found` on purpose. Where something is and who put it
    there are different questions, and only the second one may be used to
    decide whether removing it is PyCmd's business.
    """
    with _lock:
        data = load()
        data["installed"][toolchain_id] = {"how": how, "when": time.time()}
    save()


def installed_by_us(toolchain_id: str) -> bool:
    return toolchain_id in load().get("installed", {})


def survey_done() -> None:
    """Notes that a full probe of everything has just happened."""
    with _lock:
        load()["surveyed"] = time.time()
    save()


def summary() -> dict:
    """For the Toolchains screen, and for the tests."""
    data = load()
    found = data.get("found", {})
    return {
        "path": path(),
        "remembered": len(found),
        "present": sum(1 for row in found.values() if row.get("path")),
        "installedByPyCmd": len(data.get("installed", {})),
        "surveyed": data.get("surveyed", 0.0),
    }
