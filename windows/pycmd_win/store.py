"""Where PyCmd keeps things on Windows.

The phone build has this decided for it: an Android app owns exactly one
private folder and everything lives under it. On Windows the choice is ours,
and the convention is unambiguous - per-user application data that is not
worth roaming goes in ``%LOCALAPPDATA%``, so PyCmd's is ``%LOCALAPPDATA%\\PyCmd``.

Nothing is written to Program Files, and nothing needs administrator rights.
That is deliberate: an app that asks for elevation to save a script is an app
people stop trusting, and a portable build has to work from a memory stick.

Set ``PYCMD_HOME`` to put the whole lot somewhere else - that is how the
portable build keeps its workspace beside the exe, and how the tests get a
clean tree without touching yours.
"""

from __future__ import annotations

import json
import os
import sys

APP_NAME = "PyCmd"

# Everything the app keeps, by the name the rest of the code asks for it by.
FOLDERS = (
    "workspace",      # your files
    "site-packages",  # pip installs here, not into the system Python
    "downloads",      # fetched files and workspace exports
    "plugins",        # installed plugins, bundled and your own
    "pages",          # what was deployed, kept apart from the workspace
    "music",          # imported audio
    "versions",       # older builds, so an update can be undone
    "logs",
    "cache",
)

_root = ""


def _default_root() -> str:
    override = os.environ.get("PYCMD_HOME", "").strip()
    if override:
        return os.path.abspath(os.path.expanduser(override))

    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        return os.path.join(base, APP_NAME)

    # Not Windows: this is a developer or a test run. Follow the XDG spec
    # rather than inventing something, so a Linux checkout behaves itself.
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP_NAME)


def root() -> str:
    """The folder everything lives under, made if it is not there yet."""
    global _root
    if not _root:
        _root = _default_root()
    os.makedirs(_root, exist_ok=True)
    return _root


def use(path: str) -> str:
    """Points the store somewhere else. For the portable build and the tests."""
    global _root
    _root = os.path.abspath(os.path.expanduser(path))
    os.makedirs(_root, exist_ok=True)
    return _root


def folder(name: str) -> str:
    """One of the folders in [FOLDERS], made if it is not there yet."""
    if name not in FOLDERS:
        raise ValueError(f"{name!r} is not one of PyCmd's folders")
    path = os.path.join(root(), name)
    os.makedirs(path, exist_ok=True)
    return path


def prepare() -> dict:
    """Makes the lot. Called once at start-up."""
    made = {"root": root()}
    for name in FOLDERS:
        made[name] = folder(name)
    return made


def bundled() -> str:
    """Where the files that ship inside the exe are.

    PyInstaller unpacks a one-file build into a temporary folder and points
    ``sys._MEIPASS`` at it. Running from a checkout there is no such thing, so
    this falls back to the repository, which is what makes `python -m pycmd_win`
    work while developing.
    """
    packed = getattr(sys, "_MEIPASS", "")
    if packed:
        return packed
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def asset(*parts) -> str:
    """A path to something that shipped with the app."""
    return os.path.join(bundled(), *parts)


def engine_path() -> str:
    """Where the shared Python engine is, packed or in a checkout."""
    packed = os.path.join(bundled(), "engine")
    if os.path.isdir(packed):
        return packed
    return os.path.join(bundled(), "app", "src", "main", "python")


def assets_path() -> str:
    """Where the shared web assets, plugins, docs and examples are."""
    packed = os.path.join(bundled(), "assets")
    if os.path.isdir(packed):
        return packed
    return os.path.join(bundled(), "app", "src", "main", "assets")


# ---------------------------------------------------------------------------
# Small persistent settings
# ---------------------------------------------------------------------------
#
# One flat JSON file for the handful of things that have to outlive a launch
# and are too small to deserve a home of their own - which side of a split a
# panel sits on, whether an easter egg has been found. Anything that grows a
# shape of its own gets its own file instead; this is for the leaves.

SETTINGS = "settings.json"


def settings() -> dict:
    """Everything remembered. Never raises; a broken file reads as empty."""
    try:
        with open(os.path.join(root(), SETTINGS), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(data: dict) -> bool:
    """Writes them back, through a temporary so a crash cannot truncate them."""
    target = os.path.join(root(), SETTINGS)
    temporary = target + f".writing-{os.getpid()}"
    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.replace(temporary, target)
        return True
    except (OSError, TypeError, ValueError):
        try:
            os.remove(temporary)
        except OSError:
            pass
        return False


def describe() -> dict:
    """What the System screen shows."""
    def size_of(path):
        total = 0
        for directory, _folders, names in os.walk(path):
            for name in names:
                try:
                    total += os.path.getsize(os.path.join(directory, name))
                except OSError:
                    pass
        return total

    def count_in(path):
        return sum(len(names) for _d, _f, names in os.walk(path))

    out = {"root": root(), "portable": bool(os.environ.get("PYCMD_HOME"))}
    for name in FOLDERS:
        path = folder(name)
        out[name] = {"path": path, "bytes": size_of(path), "files": count_in(path)}
    try:
        import shutil as _shutil

        out["free_bytes"] = _shutil.disk_usage(root()).free
    except Exception:  # noqa: BLE001
        out["free_bytes"] = 0
    return out
