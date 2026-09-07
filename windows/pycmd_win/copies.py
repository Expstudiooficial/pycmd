"""Finding the other copies of PyCmd on this machine, and taking their place.

A single-file exe with no installer has one flaw, and it is the one being
complained about: nothing ever removes the old one. You download 1.0.1 to
Downloads, run it, download 1.0.2 next month, and now the machine has two -
then five, then a folder full of them, and no way to tell which the shortcut
points at. Every one of them is a whole working copy of PyCmd, and all but one
are dead weight.

So PyCmd looks for its own older selves and offers to be the only one.

**Where it looks** is deliberately narrow. Every place a person actually puts
a downloaded exe - Downloads, the Desktop, the folder this one is running
from, `%LOCALAPPDATA%\\PyCmd` - and nowhere else. Walking whole drives looking
for executables is what malware scanners do; it is slow, it is alarming, and
it would find PyCmd copies inside other people's backups.

**What counts as a copy** is not "a file called PyCmd.exe". A name is not
identity. Each candidate is asked its version, the same way the toolchains
are, and only something that answers as PyCmd is treated as PyCmd. That means
a file somebody else named PyCmd.exe is left alone, which is the entire point
of checking.

**Replacing** is the careful part, and it is careful because it deletes
things:

* the copy currently running is never a candidate to be deleted;
* neither is anything newer than this build - a 2.0 exe does not get to
  remove 2.1 because it found it first;
* administrator rights are asked for only when the target genuinely needs
  them, which is when it sits somewhere under Program Files. A copy in
  Downloads is the user's own file and needs nothing;
* and the old exe is *moved into the versions folder*, not destroyed, so the
  rollback below has something to roll back to.

**Rolling back** is the phone's feature brought over. Every replaced build is
kept, newest first, up to a cap, and going back to one is a copy in the other
direction. An update you cannot undo is a worse update.
"""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import time

from . import store

WINDOWS = os.name == "nt"

# How many old builds to keep. Five is about a year of releases at this pace,
# and 75 MB - enough to go back past a bad one, not enough to be the reason
# somebody's disk fills up.
KEEP = 5

RECORD = "versions.json"

# Asking an exe its version has to end. A file that is not PyCmd may be
# anything at all, including something that waits for input for ever.
ASK_TIMEOUT = 20.0


def running_exe() -> str:
    """This build's own path - the frozen exe, or the interpreter in a checkout."""
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    return ""


def _folders() -> list:
    """The handful of places a downloaded exe actually lands."""
    seen: list = []

    def add(path):
        if not path:
            return
        full = os.path.abspath(os.path.expanduser(path))
        if full not in seen and os.path.isdir(full):
            seen.append(full)

    here = running_exe()
    if here:
        add(os.path.dirname(here))
    add(store.root())
    home = os.path.expanduser("~")
    for name in ("Downloads", "Desktop", "Documents"):
        add(os.path.join(home, name))
    if WINDOWS:
        add(os.environ.get("LOCALAPPDATA"))
        for key in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(key)
            if base:
                add(os.path.join(base, "PyCmd"))
    return seen


def _looks_like_pycmd(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith(".exe") and lowered.startswith("pycmd")


def ask_version(path: str) -> str:
    """What this exe says it is, or "" if it will not say.

    `--version` prints one line and exits. Anything that does not answer that
    way in twenty seconds is not a PyCmd build, whatever it is called.
    """
    try:
        done = subprocess.run(
            [path, "--version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=ASK_TIMEOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    text = (done.stdout or "") + (done.stderr or "")
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("pycmd for windows"):
            return line.split()[-1]
    return ""


def _order(version: str) -> tuple:
    """A version string as something comparable. Unparseable sorts lowest."""
    parts = []
    for piece in (version or "").split("."):
        digits = "".join(c for c in piece if c.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def find_others(my_version: str) -> dict:
    """Every other PyCmd on this machine, and whether it is older than us."""
    me = running_exe()
    mine = os.path.normcase(me) if me else ""
    others = []
    looked = []

    for folder in _folders():
        looked.append(folder)
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            if not _looks_like_pycmd(name):
                continue
            full = os.path.join(folder, name)
            if not os.path.isfile(full):
                continue
            if mine and os.path.normcase(full) == mine:
                continue
            version = ask_version(full)
            if not version:
                # Named like PyCmd, does not answer like PyCmd. Not ours to
                # touch: somebody's unrelated file keeps its name.
                continue
            try:
                size = os.path.getsize(full)
                when = os.path.getmtime(full)
            except OSError:
                size, when = 0, 0.0
            others.append({
                "path": full,
                "version": version,
                "older": _order(version) < _order(my_version),
                "same": _order(version) == _order(my_version),
                "bytes": size,
                "modified": when,
                "needsAdmin": _needs_admin(full),
            })

    others.sort(key=lambda row: _order(row["version"]), reverse=True)
    return {
        "ok": True,
        "me": me,
        "myVersion": my_version,
        "others": others,
        "older": [row for row in others if row["older"]],
        "lookedIn": looked,
    }


def _needs_admin(path: str) -> bool:
    """Whether removing this would need elevation.

    Under Program Files, yes. Anywhere in the user's own tree, no - and asking
    for administrator to delete a file out of somebody's own Downloads folder
    is the kind of prompt that teaches people to click yes without reading.
    """
    if not WINDOWS:
        return False
    lowered = os.path.normcase(os.path.abspath(path))
    for key in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "SystemRoot"):
        base = os.environ.get(key)
        if base and lowered.startswith(os.path.normcase(os.path.abspath(base)) + os.sep):
            return True
    return False


def is_admin() -> bool:
    if not WINDOWS:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Keeping old builds, so an update can be undone
# ---------------------------------------------------------------------------

def _record_path() -> str:
    return os.path.join(store.folder("versions"), RECORD)


def _load_record() -> list:
    try:
        with open(_record_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _save_record(rows: list) -> None:
    try:
        with open(_record_path(), "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=2)
    except OSError:
        pass


def keep(path: str, version: str, why: str = "replaced") -> dict:
    """Files an old build away so it can be gone back to.

    Moved rather than copied when it can be - the old exe is on its way out,
    and copying fifteen megabytes to then delete the original is work for
    nothing. Across drives a move is a copy anyway, so both are handled.
    """
    if not os.path.isfile(path):
        return {"ok": False, "error": "there is nothing at that path to keep"}
    folder = store.folder("versions")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = os.path.join(folder, f"PyCmd-{version or 'unknown'}-{stamp}.exe")
    try:
        shutil.move(path, target)
    except OSError as error:
        return {"ok": False, "error": f"could not keep it: {error}"}

    rows = _load_record()
    rows.insert(0, {
        "path": target, "version": version, "why": why,
        "kept": time.time(), "bytes": os.path.getsize(target),
    })
    dropped = []
    for row in rows[KEEP:]:
        try:
            os.remove(row["path"])
        except OSError:
            pass
        dropped.append(row["version"])
    rows = rows[:KEEP]
    _save_record(rows)
    return {"ok": True, "kept": target, "dropped": dropped}


def kept() -> list:
    """Old builds still on the disk, newest first, forgetting any that went."""
    rows = [row for row in _load_record() if os.path.isfile(row.get("path", ""))]
    if len(rows) != len(_load_record()):
        _save_record(rows)
    return rows


def go_back(path: str, to: str = "") -> dict:
    """Puts a kept build back where this one is running from.

    A running exe cannot overwrite itself on Windows - the file is locked for
    as long as the process lives - so this writes the old build *beside* the
    current one and hands back a script that swaps them once PyCmd has quit.
    Doing it any other way means a half-copied exe if the machine is turned
    off at the wrong moment.
    """
    if not os.path.isfile(path):
        return {"ok": False, "error": "that build is not on the disk any more"}
    target = to or running_exe()
    if not target:
        return {"ok": False, "reason": "not-frozen",
                "error": "rolling back only means something for the exe, and "
                         "this is running from a checkout"}

    staged = target + ".rollback"
    try:
        shutil.copy2(path, staged)
    except OSError as error:
        return {"ok": False, "error": f"could not stage the old build: {error}"}
    return {"ok": True, "staged": staged, "target": target,
            "script": swap_script(staged, target),
            "note": "PyCmd has to close for the swap - the file it is running "
                    "from is locked while it runs."}


def swap_script(new_exe: str, target: str) -> str:
    """A batch file that waits for PyCmd to quit, swaps the exe, and restarts.

    Written as a script on purpose rather than done from Python: whatever does
    the swap has to outlive the process being swapped, and a detached cmd is
    the one thing on Windows that reliably does with nothing installed.
    """
    return (
        "@echo off\r\n"
        "rem Written by PyCmd. Waits for it to close, puts the new build in\r\n"
        "rem place, starts it again, then deletes itself.\r\n"
        f'set "target={target}"\r\n'
        f'set "staged={new_exe}"\r\n'
        ":wait\r\n"
        'tasklist /fi "imagename eq %~nx0" >nul 2>&1\r\n'
        "timeout /t 1 /nobreak >nul\r\n"
        'if exist "%target%" (\r\n'
        '  move /y "%target%" "%target%.old" >nul 2>&1 || goto wait\r\n'
        ")\r\n"
        'move /y "%staged%" "%target%" >nul\r\n'
        'del /q "%target%.old" >nul 2>&1\r\n'
        'start "" "%target%"\r\n'
        '(goto) 2>nul & del "%~f0"\r\n'
    )


def replace(others: list, my_version: str, elevate: bool = True) -> dict:
    """Takes the place of the older copies: keeps them, then removes them.

    Anything the same age or newer is refused rather than skipped quietly - a
    build removing its own successor because it happened to run first is the
    failure this must not have.
    """
    me = running_exe()
    removed, kept_rows, refused, needs_admin = [], [], [], []

    for row in others:
        path = row.get("path", "")
        version = row.get("version", "")
        if not path or not os.path.isfile(path):
            continue
        if me and os.path.normcase(path) == os.path.normcase(me):
            refused.append({"path": path, "why": "that is the copy running now"})
            continue
        if _order(version) >= _order(my_version):
            refused.append({"path": path,
                            "why": f"{version} is not older than {my_version}"})
            continue
        if _needs_admin(path) and not is_admin():
            needs_admin.append(path)
            continue

        result = keep(path, version, why="replaced by " + my_version)
        if result.get("ok"):
            removed.append(path)
            kept_rows.append(result["kept"])
        else:
            refused.append({"path": path, "why": result.get("error", "could not move it")})

    out = {
        "ok": True, "removed": removed, "kept": kept_rows,
        "refused": refused, "needsAdmin": needs_admin,
    }
    if needs_admin and elevate:
        out["elevate"] = True
        out["note"] = ("Some copies are under Program Files and need "
                       "administrator to move. Say the word and PyCmd will ask "
                       "Windows for it.")
    return out


def elevate_and_rerun(argument: str) -> dict:
    """Asks Windows for administrator and starts this exe again with a flag.

    ShellExecuteW with "runas" is the documented way to request elevation, and
    it shows the consent dialog rather than bypassing it - there is no way to
    become administrator without the user agreeing, and PyCmd should not want
    one.
    """
    if not WINDOWS:
        return {"ok": False, "error": "elevation is a Windows idea"}
    me = running_exe()
    if not me:
        return {"ok": False, "reason": "not-frozen",
                "error": "only the exe can ask to be elevated"}
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", me, argument, None, 1)
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": f"could not ask for administrator: {error}"}
    # Anything at or below 32 is a documented failure code; 1223 inside it is
    # the user saying no, which is an answer rather than a fault.
    if int(result) <= 32:
        return {"ok": False, "declined": True,
                "error": "Windows did not grant administrator (you may have "
                         "said no, which is fine - the copies stay)."}
    return {"ok": True, "started": True}
