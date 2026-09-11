"""The rest of the computer.

PyCmd's workspace is a walled garden, and `files.py` guards its wall carefully:
every path is resolved and then checked to be inside it, because on a phone
that wall is the operating system's and there is nothing outside it an app may
touch. The phone build's answer to "I have a file elsewhere" is an import
button that copies it in, and its answer to "I want this file elsewhere" is an
export button that copies it out. Two buttons, two copies, and the original and
the copy drifting apart from the moment you press either.

Windows is not a phone. A file on this machine belongs to the person using it,
Explorer can open any of it, and every other editor on the platform works
directly on the file you point it at. Copying in and out is the wrong shape
here; it was only ever a workaround for a restriction this build does not have.

So this module is the other half: browse the machine, read and write in place,
run something where it sits. The workspace is still there and still the
default - it is a good place to keep scratch work - but it is now a *folder*
rather than a *boundary*.

**On safety, plainly.** A handler that reads and writes anywhere is reachable
by a plugin panel, and that is worth saying out loud rather than hiding. It
grants a plugin nothing it did not already have: plugins are Python that runs
inside this process, so `open("C:/Users/.../file")` has always worked for them.
Restricting this API while that is true would be a comforting lie rather than
a defence. What this module does instead is be careful about the things that
are genuinely easy to get wrong:

* writes go through a temporary and a rename, so an interrupted save leaves
  the old file rather than half a new one;
* deleting is explicit, never recursive unless asked, and never follows a
  symlink out of the folder it was pointed at;
* the places Windows will not let anybody write - and the ones nobody should
  want to - are refused with a reason rather than attempted;
* nothing here ever runs a file. Running is `runner.py`'s job and goes through
  the same toolchain plan as everything else.
"""

from __future__ import annotations

import os
import shutil
import stat
import string
import subprocess
import time

WINDOWS = os.name == "nt"

# Folders that are the operating system's business. Writing into them either
# fails with a permission error or breaks something, and neither is a useful
# thing for a code editor to do by accident.
FORBIDDEN = (
    r"C:\Windows",
    r"C:\Program Files\WindowsApps",
    r"C:\$Recycle.Bin",
    r"C:\System Volume Information",
)

# How many entries to hand back for one folder. A directory with two hundred
# thousand files in it is a real thing on Windows, and a UI given all of them
# stops responding.
PAGE = 2000


class Refused(ValueError):
    """Something this module will not do, with a reason a person can read."""


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _is_forbidden(path: str) -> str:
    """The reason this path is off limits, or "" if it is fine."""
    if not WINDOWS:
        return ""
    lowered = _norm(path)
    for base in FORBIDDEN:
        low = os.path.normcase(base)
        if lowered == low or lowered.startswith(low + os.sep):
            return f"{base} belongs to Windows. PyCmd will not write there."
    return ""


def _blank(*paths: str) -> str:
    """Why an empty path is refused rather than resolved.

    `os.path.abspath("")` is the current working directory. That is the
    documented behaviour and it is useful in a shell, where "here" is what you
    meant. It is a trap in a file API: a screen that has not finished loading,
    a payload missing a key, a plugin passing a variable that happens to be
    empty - all of them arrive as `""`, and every one of those would have been
    read as *this folder*.

    The suite found this the hard way. The handler sweep calls every handler
    once with an empty payload to check it answers rather than raising, so it
    called `disk.remove("")`, which resolved to the process's working
    directory - the test workspace, which was empty at that moment - and
    deleted it. Every later check ran with a working directory that no longer
    existed, and the run died forty checks later somewhere that had nothing to
    do with it.

    A person deleting "here" says so by naming it. An empty string is a bug.
    """
    for path in paths:
        if not str(path or "").strip():
            return "no path was given"
    return ""


def drives() -> list:
    """Every drive with a letter, and how full it is.

    Off Windows this is the one root, which keeps the screen honest on the
    machine the tests run on rather than pretending there are drives.
    """
    if not WINDOWS:
        return [_drive_row("/")]
    found = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if os.path.exists(root):
            found.append(_drive_row(root))
    return found


def _drive_row(root: str) -> dict:
    row = {"path": root, "name": root, "total": 0, "free": 0, "ready": True}
    try:
        usage = shutil.disk_usage(root)
        row["total"] = usage.total
        row["free"] = usage.free
    except OSError:
        # A card reader with no card, a disconnected network drive. It is
        # listed, because it is there, and marked so the UI can grey it.
        row["ready"] = False
    return row


def places() -> list:
    """The folders a person actually keeps things in, for one click each."""
    home = os.path.expanduser("~")
    wanted = [
        ("Home", home),
        ("Desktop", os.path.join(home, "Desktop")),
        ("Documents", os.path.join(home, "Documents")),
        ("Downloads", os.path.join(home, "Downloads")),
        ("Pictures", os.path.join(home, "Pictures")),
        ("Music", os.path.join(home, "Music")),
        ("Videos", os.path.join(home, "Videos")),
    ]
    return [{"name": name, "path": path}
            for name, path in wanted if os.path.isdir(path)]


def _kind(entry_path: str, is_dir: bool) -> str:
    if is_dir:
        return "folder"
    return "file"


def _language_of(name: str) -> dict:
    """What a listed file is, so a row can show a pill and a Run button.

    A dictionary lookup on the extension, done here rather than in the page,
    because the page has no language table for files outside the workspace and
    asking the host once per row would be a thousand round trips.
    """
    from . import langs

    row = langs.for_path(name)
    return {"language": row.get("name", ""), "languageId": row.get("id", ""),
            "runs": row.get("mode") == "run"}


def listing(path: str = "", show_hidden: bool = False) -> dict:
    """What is in one folder.

    Uses `os.scandir`, which gets the type and the size from the directory
    entry Windows already returned rather than calling stat on every name.
    On a folder with thousands of files that is the difference between
    instant and a visible pause.
    """
    if not path:
        return {"ok": True, "path": "", "atRoot": True,
                "drives": drives(), "places": places(), "entries": []}

    target = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(target):
        return {"ok": False, "error": f"{target} is not a folder"}

    entries = []
    truncated = False
    try:
        with os.scandir(target) as scan:
            for item in scan:
                if len(entries) >= PAGE:
                    truncated = True
                    break
                name = item.name
                if not show_hidden and _hidden(item, name):
                    continue
                try:
                    is_dir = item.is_dir(follow_symlinks=False)
                    info = item.stat(follow_symlinks=False)
                    size = 0 if is_dir else info.st_size
                    when = info.st_mtime
                except OSError:
                    is_dir, size, when = False, 0, 0.0
                row = {
                    "name": name,
                    "path": os.path.join(target, name),
                    "folder": is_dir,
                    "kind": _kind(name, is_dir),
                    "bytes": size,
                    "modified": when,
                    "link": item.is_symlink(),
                }
                if not is_dir:
                    row.update(_language_of(name))
                entries.append(row)
    except PermissionError:
        return {"ok": False, "reason": "denied",
                "error": "Windows will not let PyCmd read that folder. "
                         "It may need administrator, or belong to another user."}
    except OSError as error:
        return {"ok": False, "error": f"could not read that folder: {error}"}

    entries.sort(key=lambda row: (not row["folder"], row["name"].lower()))
    parent = os.path.dirname(target.rstrip(os.sep))
    if parent == target:
        parent = ""
    return {
        "ok": True,
        "path": target,
        "parent": parent,
        "atRoot": False,
        "entries": entries,
        "folders": sum(1 for row in entries if row["folder"]),
        "files": sum(1 for row in entries if not row["folder"]),
        "truncated": truncated,
        "crumbs": _crumbs(target),
        "writable": not _is_forbidden(target),
    }


def _hidden(item, name: str) -> bool:
    if name.startswith("."):
        return True
    if not WINDOWS:
        return False
    try:
        return bool(item.stat(follow_symlinks=False).st_file_attributes
                    & stat.FILE_ATTRIBUTE_HIDDEN)
    except (OSError, AttributeError):
        return False


def _crumbs(path: str) -> list:
    """The path as clickable pieces, drive first."""
    out = []
    head = os.path.abspath(path)
    while True:
        parent = os.path.dirname(head)
        name = os.path.basename(head)
        if not name:
            out.insert(0, {"name": head, "path": head})
            break
        out.insert(0, {"name": name, "path": head})
        if parent == head:
            break
        head = parent
    return out


# How much of a file to hand to the editor. Past this it is not something
# somebody is going to edit by hand, and sending it would freeze the window
# while the browser tried to lay out a hundred megabytes of text.
MAX_EDIT = 8 * 1024 * 1024


def read(path: str) -> dict:
    """A file's text, if it is text and not enormous."""
    why = _blank(path)
    if why:
        return {"ok": False, "error": why}
    target = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(target):
        return {"ok": False, "error": f"{target} is not a file"}
    try:
        size = os.path.getsize(target)
    except OSError as error:
        return {"ok": False, "error": str(error)}
    if size > MAX_EDIT:
        return {"ok": False, "reason": "too-big",
                "error": f"That file is {size // (1024 * 1024)} MB. PyCmd opens "
                         f"files up to {MAX_EDIT // (1024 * 1024)} MB in the editor.",
                "bytes": size}

    try:
        with open(target, "rb") as handle:
            raw = handle.read()
    except PermissionError:
        return {"ok": False, "reason": "denied",
                "error": "Windows will not let PyCmd read that file."}
    except OSError as error:
        return {"ok": False, "error": f"could not read it: {error}"}

    # A NUL in the first chunk is the standard "this is not text" signal, and
    # it is worth catching: handing a JPEG to the editor as mojibake and then
    # letting somebody save it would destroy the file.
    if b"\x00" in raw[:8192]:
        return {"ok": False, "reason": "binary", "bytes": size,
                "error": "That looks like a binary file, not text. PyCmd will "
                         "not open it in the editor - saving would corrupt it."}

    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return {"ok": True, "path": target, "text": raw.decode(encoding),
                    "bytes": size, "encoding": encoding}
        except UnicodeDecodeError:
            continue
    return {"ok": False, "reason": "encoding",
            "error": "PyCmd could not work out this file's text encoding."}


def write(path: str, text: str) -> dict:
    """Saves a file in place, through a temporary and a rename."""
    why = _blank(path)
    if why:
        return {"ok": False, "error": why}
    target = os.path.abspath(os.path.expanduser(path))
    why = _is_forbidden(target)
    if why:
        return {"ok": False, "reason": "forbidden", "error": why}

    folder = os.path.dirname(target)
    if not os.path.isdir(folder):
        return {"ok": False, "error": f"{folder} is not a folder"}

    temporary = target + f".pycmd-{int(time.time() * 1000)}"
    try:
        with open(temporary, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temporary, target)
    except PermissionError:
        _drop(temporary)
        return {"ok": False, "reason": "denied",
                "error": "Windows will not let PyCmd write there. The file may "
                         "be read-only, open in another program, or need "
                         "administrator."}
    except OSError as error:
        _drop(temporary)
        return {"ok": False, "error": f"could not save: {error}"}
    return {"ok": True, "path": target, "bytes": len(text.encode("utf-8"))}


def _drop(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def make_folder(path: str) -> dict:
    why = _blank(path)
    if why:
        return {"ok": False, "error": why}
    target = os.path.abspath(os.path.expanduser(path))
    why = _is_forbidden(target)
    if why:
        return {"ok": False, "error": why}
    if os.path.exists(target):
        return {"ok": False, "error": "something with that name is already there"}
    try:
        os.makedirs(target)
    except OSError as error:
        return {"ok": False, "error": f"could not make that folder: {error}"}
    return {"ok": True, "path": target}


def rename(path: str, name: str) -> dict:
    why = _blank(path)
    if why:
        return {"ok": False, "error": why}
    target = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(target):
        return {"ok": False, "error": "that is not there any more"}
    clean = (name or "").strip()
    if not clean or clean in (".", "..") or any(c in clean for c in '\\/:*?"<>|'):
        return {"ok": False, "error": "that is not a name Windows allows"}
    destination = os.path.join(os.path.dirname(target), clean)
    if os.path.exists(destination):
        return {"ok": False, "error": "something with that name is already there"}
    why = _is_forbidden(target) or _is_forbidden(destination)
    if why:
        return {"ok": False, "error": why}
    try:
        os.rename(target, destination)
    except OSError as error:
        return {"ok": False, "error": f"could not rename it: {error}"}
    return {"ok": True, "path": destination}


def remove(path: str, recursive: bool = False) -> dict:
    """Deletes a file, or a folder when asked twice.

    `recursive` has to be passed explicitly. A delete button that quietly
    removes a folder and everything under it is how people lose work, and the
    screen asks before it sets this.
    """
    why = _blank(path)
    if why:
        return {"ok": False, "error": why}
    target = os.path.abspath(os.path.expanduser(path))
    why = _is_forbidden(target)
    if why:
        return {"ok": False, "error": why}
    if not os.path.exists(target) and not os.path.islink(target):
        return {"ok": False, "error": "that is not there any more"}

    try:
        if os.path.islink(target) or os.path.isfile(target):
            os.remove(target)
        elif os.path.isdir(target):
            if not recursive:
                if os.listdir(target):
                    return {"ok": False, "reason": "not-empty",
                            "error": "that folder is not empty"}
                os.rmdir(target)
            else:
                # Never through a symlink: rmtree following one deletes what it
                # points at, which may be somewhere else entirely.
                shutil.rmtree(target, ignore_errors=False)
    except PermissionError:
        return {"ok": False, "reason": "denied",
                "error": "Windows will not let PyCmd delete that. It may be "
                         "open in another program."}
    except OSError as error:
        return {"ok": False, "error": f"could not delete it: {error}"}
    return {"ok": True, "path": target}


def copy(source: str, destination: str) -> dict:
    """Copies a file or a whole folder to a new place."""
    why = _blank(source, destination)
    if why:
        return {"ok": False, "error": why}
    src = os.path.abspath(os.path.expanduser(source))
    dst = os.path.abspath(os.path.expanduser(destination))
    if not os.path.exists(src):
        return {"ok": False, "error": "there is nothing at that path to copy"}
    why = _is_forbidden(dst)
    if why:
        return {"ok": False, "error": why}
    if os.path.isdir(src) and (_norm(dst) == _norm(src)
                               or _norm(dst).startswith(_norm(src) + os.sep)):
        return {"ok": False,
                "error": "that would copy a folder into itself"}

    target = dst
    if os.path.isdir(dst):
        target = os.path.join(dst, os.path.basename(src))
    target = _free_name(target)
    try:
        if os.path.isdir(src):
            shutil.copytree(src, target, symlinks=True)
        else:
            shutil.copy2(src, target)
    except OSError as error:
        return {"ok": False, "error": f"could not copy: {error}"}
    return {"ok": True, "path": target}


def move(source: str, destination: str) -> dict:
    why = _blank(source, destination)
    if why:
        return {"ok": False, "error": why}
    src = os.path.abspath(os.path.expanduser(source))
    dst = os.path.abspath(os.path.expanduser(destination))
    if not os.path.exists(src):
        return {"ok": False, "error": "there is nothing at that path to move"}
    why = _is_forbidden(src) or _is_forbidden(dst)
    if why:
        return {"ok": False, "error": why}
    target = dst
    if os.path.isdir(dst):
        target = os.path.join(dst, os.path.basename(src))
    target = _free_name(target)
    try:
        shutil.move(src, target)
    except OSError as error:
        return {"ok": False, "error": f"could not move: {error}"}
    return {"ok": True, "path": target}


def _free_name(path: str) -> str:
    """`file.txt`, then `file (1).txt`, the way Windows itself does it."""
    if not os.path.exists(path):
        return path
    stem, extension = os.path.splitext(path)
    n = 1
    while True:
        candidate = f"{stem} ({n}){extension}"
        if not os.path.exists(candidate):
            return candidate
        n += 1


def reveal(path: str) -> dict:
    """Shows it in Explorer, selected.

    The one place PyCmd hands off to the system on purpose: when somebody
    wants to do something PyCmd does not do, the right answer is to open the
    folder rather than to grow another file manager.
    """
    why = _blank(path)
    if why:
        return {"ok": False, "error": why}
    target = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(target):
        return {"ok": False, "error": "that is not there any more"}
    if not WINDOWS:
        return {"ok": False, "reason": "not-windows",
                "error": "Explorer is a Windows idea"}
    try:
        if os.path.isdir(target):
            subprocess.Popen(["explorer", target])
        else:
            subprocess.Popen(["explorer", "/select,", target])
    except OSError as error:
        return {"ok": False, "error": f"could not open Explorer: {error}"}
    return {"ok": True}


def open_with_system(path: str) -> dict:
    """Opens it with whatever Windows uses for that kind of file."""
    why = _blank(path)
    if why:
        return {"ok": False, "error": why}
    target = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(target):
        return {"ok": False, "error": "that is not there any more"}
    if not WINDOWS:
        return {"ok": False, "reason": "not-windows",
                "error": "this is a Windows idea"}
    try:
        os.startfile(target)  # noqa: S606 - the documented way to do this
    except OSError as error:
        return {"ok": False, "error": f"Windows could not open it: {error}"}
    return {"ok": True}


def find_runnable(root: str, limit: int = 400, depth: int = 6) -> dict:
    """Every file under here that PyCmd knows how to run.

    This is what replaces typing a path into the Run screen. Bounded three
    ways - how deep, how many, and which folders to ignore - because a
    workspace with node_modules in it has a hundred thousand files and none of
    them is the one being looked for.
    """
    why = _blank(root)
    if why:
        return {"ok": False, "error": why}
    from . import langs

    skip = {"node_modules", ".git", "__pycache__", "venv", ".venv", "env",
            "target", "build", "dist", ".idea", ".vscode", "obj", "bin",
            "site-packages", ".gradle", ".cache"}
    base = os.path.abspath(os.path.expanduser(root))
    if not os.path.isdir(base):
        return {"ok": False, "error": f"{base} is not a folder"}

    found = []
    truncated = False
    for folder, subfolders, names in os.walk(base):
        if len(found) >= limit:
            truncated = True
            break
        here = os.path.relpath(folder, base)
        if here != "." and here.count(os.sep) + 1 > depth:
            subfolders[:] = []
            continue
        subfolders[:] = [n for n in subfolders
                         if n not in skip and not n.startswith(".")]
        for name in sorted(names):
            if len(found) >= limit:
                truncated = True
                break
            full = os.path.join(folder, name)
            language = langs.for_path(full)
            # `mode` is the registry's word for it: "run" means PyCmd has a
            # way to execute the file. There is no "runnable" key - looking
            # for one found nothing, every time, silently.
            if language.get("mode") != "run":
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            found.append({
                "path": full,
                "name": name,
                "folder": os.path.relpath(folder, base) if folder != base else "",
                "language": language["name"],
                "languageId": language["id"],
                "bytes": size,
            })
    return {"ok": True, "root": base, "files": found,
            "truncated": truncated, "count": len(found)}
