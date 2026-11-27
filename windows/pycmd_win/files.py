"""The workspace, as files on a disk.

The Android build does this in Kotlin - `Workspace.kt` - because on a phone
the workspace is app-private storage and the file picker is a system service.
Neither is true here: the workspace is an ordinary Windows folder, and the
only thing standing between it and Explorer is that PyCmd knows where it is.

So this is the smallest honest file API: list, read, write, make, rename,
delete, and bring a file in from somewhere else on the disk.

**Everything is checked to be inside the workspace.** Not because a local user
cannot reach their own disk - they obviously can, with Explorer - but because
the app has a bridge that a *plugin panel* can reach, and a plugin asking to
read `C:\\Users\\you\\.ssh\\id_rsa` through the app's own file API should get
a refusal rather than a helping hand. The check is the same one the HTTP
server uses: resolve first, then require the result to be inside.
"""

from __future__ import annotations

import os
import shutil
import time

from . import langs, store
from . import eol

# What is shown without asking. A workspace with a node_modules in it would
# otherwise take a second to list and fill the screen with noise.
SKIP = {"__pycache__", ".git", ".venv", "node_modules", ".mypy_cache", ".pytest_cache"}

# Reading a file into an editor is not the same as serving it; something
# enormous should be refused rather than turned into a megabyte of JSON.
MAX_TEXT = 4 * 1024 * 1024


def root() -> str:
    return store.folder("workspace")


class Refused(Exception):
    """Something was asked for that is not the app's to give."""


def resolve(relative: str) -> str:
    """A path inside the workspace, or a refusal.

    `relative` is what the UI has: a path relative to the workspace root. An
    absolute path is accepted only if it is already inside.
    """
    base = os.path.abspath(root())

    # Both separators, always, whatever this machine calls one.
    #
    # This used to be `replace("/", os.sep)`, which is correct on Windows and
    # quietly wrong everywhere else: on Linux a backslash is an ordinary
    # character, so `..\..\windows` was read as one long file name inside the
    # workspace and allowed. The check was therefore *laxer* on the machine
    # the tests run on than on the machine that ships - which is the worst way
    # round for a boundary check to be wrong, because the tests agree with it.
    text = (relative or "").strip().replace("\\", "/")
    parts = [part for part in text.split("/") if part not in ("", ".")]

    # An absolute path is only accepted if it is already inside, and is
    # recognised on either platform's terms.
    looks_absolute = text.startswith("/") or (len(text) > 1 and text[1] == ":")
    candidate = os.path.abspath(text.replace("/", os.sep)) if looks_absolute \
        else os.path.abspath(os.path.join(base, *parts))

    if candidate != base and not candidate.startswith(base + os.sep):
        raise Refused("that is outside the workspace")
    return candidate


def relative(path: str) -> str:
    base = os.path.abspath(root())
    path = os.path.abspath(path)
    if path == base:
        return ""
    return os.path.relpath(path, base).replace(os.sep, "/")


def _entry(path: str) -> dict:
    try:
        stat = os.stat(path)
    except OSError:
        return {}
    folder = os.path.isdir(path)
    language = {} if folder else langs.for_path(path)
    return {
        "name": os.path.basename(path),
        "path": relative(path),
        "folder": folder,
        "bytes": 0 if folder else stat.st_size,
        "modified": int(stat.st_mtime),
        "language": language.get("name", ""),
        "language_id": language.get("id", ""),
        "mode": language.get("mode", ""),
        # A page runs too: Run serves it and opens it in the browser.
        "runnable": language.get("mode") == "run" or path.lower().endswith((".html", ".htm")),
    }


def listing(relative_path: str = "") -> dict:
    """What is in one folder. Folders first, then files, both by name."""
    try:
        folder = resolve(relative_path)
    except Refused as error:
        return {"ok": False, "error": str(error)}
    if not os.path.isdir(folder):
        return {"ok": False, "error": f"{relative_path or 'the workspace'} is not a folder"}

    rows = []
    try:
        names = os.listdir(folder)
    except OSError as error:
        return {"ok": False, "error": str(error)}

    for name in names:
        if name in SKIP or name.startswith(".pycmd-"):
            continue
        entry = _entry(os.path.join(folder, name))
        if entry:
            rows.append(entry)

    rows.sort(key=lambda row: (not row["folder"], row["name"].lower()))
    here = relative(folder)
    return {
        "ok": True,
        "path": here,
        "parent": here.rsplit("/", 1)[0] if "/" in here else ("" if here else None),
        "root": folder,
        "entries": rows,
        "folders": sum(1 for row in rows if row["folder"]),
        "files": sum(1 for row in rows if not row["folder"]),
    }


def read(relative_path: str) -> dict:
    try:
        path = resolve(relative_path)
    except Refused as error:
        return {"ok": False, "error": str(error)}
    if not os.path.isfile(path):
        return {"ok": False, "error": "that file is not there"}
    size = os.path.getsize(path)
    language = langs.for_path(path)
    if language.get("mode") == "media":
        return {"ok": False, "error": f"{language['name']} is not text", "media": True,
                "language": language}
    if size > MAX_TEXT:
        return {"ok": False, "error": f"that file is {size // 1048576} MB, too big to open here"}
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as error:
        return {"ok": False, "error": str(error)}
    text = eol.for_editor(raw.decode("utf-8", errors="replace"))
    return {"ok": True, "path": relative(path), "text": text, "bytes": size,
            "language": language, "eol": eol.detect(raw)}


def write(relative_path: str, text: str) -> dict:
    try:
        path = resolve(relative_path)
    except Refused as error:
        return {"ok": False, "error": str(error)}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        # Written beside and renamed over, so a crash halfway leaves the old
        # file rather than half of the new one. Same reasoning as the plugin
        # installer, and the same fix.
        temporary = path + f".pycmd-{int(time.time() * 1000)}"
        text = eol.keep(path, text)
        with open(temporary, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except OSError as error:
        return {"ok": False, "error": str(error)}
    return {"ok": True, "path": relative(path), "bytes": len(text.encode("utf-8"))}


def create(relative_path: str, language_id: str = "", folder: bool = False) -> dict:
    """A new file from its language's template, or a new folder."""
    try:
        path = resolve(relative_path)
    except Refused as error:
        return {"ok": False, "error": str(error)}
    if os.path.exists(path):
        return {"ok": False, "error": f"{os.path.basename(path)} is already there"}

    if folder:
        try:
            os.makedirs(path)
        except OSError as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True, "path": relative(path), "folder": True}

    language = langs.by_id(language_id) if language_id else None
    if language is None:
        found = langs.for_path(path)
        language = langs.by_id(found["id"])
    if language is not None and language.mode == "media":
        return {"ok": False,
                "error": f"an empty {language.name.lower()} file is not much use - "
                         "bring a real one in instead"}
    template = language.template if language else ""
    return write(relative_path, template)


def rename(relative_path: str, name: str) -> dict:
    try:
        path = resolve(relative_path)
    except Refused as error:
        return {"ok": False, "error": str(error)}
    name = os.path.basename((name or "").strip())
    if not name:
        return {"ok": False, "error": "a name is needed"}
    if not os.path.exists(path):
        return {"ok": False, "error": "that is not there"}
    target = os.path.join(os.path.dirname(path), name)
    if os.path.exists(target):
        return {"ok": False, "error": f"{name} is already there"}
    try:
        os.rename(path, target)
    except OSError as error:
        return {"ok": False, "error": str(error)}
    return {"ok": True, "path": relative(target)}


def remove(relative_path: str) -> dict:
    try:
        path = resolve(relative_path)
    except Refused as error:
        return {"ok": False, "error": str(error)}
    if path == os.path.abspath(root()):
        return {"ok": False, "error": "the workspace itself stays"}
    if not os.path.exists(path):
        return {"ok": False, "error": "that is not there"}
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except OSError as error:
        return {"ok": False, "error": str(error)}
    return {"ok": True, "path": relative(path)}


def bring_in(source: str, into: str = "") -> dict:
    """Copies a file from anywhere on the disk into the workspace.

    The source may be anywhere - that is the point, and it is the user's own
    machine. The *destination* is checked, which is the direction that matters.
    """
    source = os.path.abspath(os.path.expanduser((source or "").strip()))
    if not os.path.isfile(source):
        return {"ok": False, "error": f"there is no file at {source}"}
    try:
        folder = resolve(into)
    except Refused as error:
        return {"ok": False, "error": str(error)}
    os.makedirs(folder, exist_ok=True)

    name = os.path.basename(source)
    target = os.path.join(folder, name)
    if os.path.exists(target):
        stem, extension = os.path.splitext(name)
        index = 2
        while os.path.exists(target) and index < 500:
            target = os.path.join(folder, f"{stem} ({index}){extension}")
            index += 1
    try:
        shutil.copy2(source, target)
    except OSError as error:
        return {"ok": False, "error": str(error)}
    return {"ok": True, "path": relative(target), "name": os.path.basename(target),
            "bytes": os.path.getsize(target)}


def tree(relative_path: str = "", depth: int = 3) -> dict:
    """A shallow tree, for pointing a page or a server at a folder."""
    try:
        base = resolve(relative_path)
    except Refused as error:
        return {"ok": False, "error": str(error)}

    out = []

    def walk(folder, level):
        if level > depth:
            return
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            return
        for name in names:
            if name in SKIP or name.startswith("."):
                continue
            path = os.path.join(folder, name)
            if os.path.isdir(path):
                out.append({"path": relative(path), "name": name, "depth": level})
                walk(path, level + 1)

    walk(base, 0)
    return {"ok": True, "folders": out[:400]}
