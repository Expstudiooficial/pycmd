"""The plugins that ship inside the exe, and the ones you bring from a phone.

Two jobs.

**Installing what shipped.** Five plugins ride along inside the build - Cloud,
Creator, Packages Pro, Scheduler and Server Pro - and land in the plugins
folder on first run so they show up switched off in the list rather than not at
all. The ordering here is the one the phone build learned the hard way in
2.5.7: install *before* anything is loaded, ask the real listing rather than a
half-filled cache, and treat a folder that will not read as out of date so a
damaged plugin repairs itself instead of staying broken.

**Bringing a phone plugin over.** A PyCmd plugin is a folder with a
`plugin.json`, some Python and some HTML - none of which is Android-specific,
because the plugin API never was. So one written for the phone very often just
works here. *Often*, not always, and that is what [inspect_mobile] is for: it
reads a plugin before installing it and says which of its parts this machine
cannot honour, so the warning on the button is a specific one rather than a
shrug.
"""

from __future__ import annotations

import json
import os
import zipfile

from . import mobile, store

BUNDLED = ("cloud", "creator", "packages-pro", "scheduler", "server-pro")

# What a plugin can ask for that means something different, or nothing, here.
MOBILE_ONLY_PERMISSIONS = {
    "notifications": "Android notifications. On Windows the app uses its own "
                     "toasts instead, so a plugin that posts one will be heard "
                     "but will not look the same.",
    "wakelock": "Android wake locks. Windows has no equivalent an app may take, "
                "so this is ignored; Keep Awake covers the same ground.",
    "media": "Android's media session, which is what draws the lock-screen "
             "controls. Windows has no lock screen to draw them on.",
}

# Strings in a plugin's Python that only make sense on a phone. Finding one is
# not a refusal - plenty of plugins guard them - but it is worth saying.
MOBILE_HINTS = (
    ("from java", "imports Android classes directly, which are not here"),
    ("import java", "imports Android classes directly, which are not here"),
    ("com.chaquo", "uses Chaquopy, the Android Python bridge"),
    ("/storage/emulated", "hard-codes an Android storage path"),
    ("/data/user/0", "hard-codes an Android storage path"),
    ("android.", "refers to Android APIs"),
)


def _read_manifest(folder: str) -> dict:
    try:
        with open(os.path.join(folder, "plugin.json"), "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        return manifest if isinstance(manifest, dict) else {}
    except (OSError, ValueError):
        return {}


def stage_bundled() -> list:
    """The bundled plugin folders, wherever this build keeps them."""
    base = os.path.join(store.assets_path(), "plugins")
    if not os.path.isdir(base):
        return []
    out = []
    for name in BUNDLED:
        folder = os.path.join(base, name)
        if os.path.isfile(os.path.join(folder, "plugin.json")):
            out.append(folder)
    return out


def install_bundled(plugins_module, log=None) -> dict:
    """Puts the shipped plugins in place, without switching any of them on.

    Called before anything is loaded. The version check reads what the runtime
    actually reports rather than a cache that may not have been filled yet -
    the phone build spent three releases reinstalling all five on every launch
    because of exactly that, and the race it caused made plugins fail to load.
    """
    def say(level, message, detail=""):
        if log:
            log(level, message, detail)

    staged = stage_bundled()
    if not staged:
        return {"ok": True, "installed": [], "note": "no bundled plugins in this build"}

    present = {}
    try:
        listing = json.loads(plugins_module.listing())
    except (ValueError, AttributeError, TypeError):
        listing = {}
    for row in listing.get("plugins", []) or []:
        # A folder that will not read is not a version to compare against;
        # leaving it alone is how a half-written plugin stays half-written.
        if row.get("broken"):
            continue
        present[row.get("id", "")] = row.get("version", "")

    installed = []
    for folder in staged:
        manifest = _read_manifest(folder)
        plugin_id = manifest.get("id", "")
        version = manifest.get("version", "")
        if not plugin_id:
            continue
        if present.get(plugin_id) == version:
            continue
        try:
            reply = json.loads(plugins_module.install(folder, os.path.basename(folder), "1"))
        except (ValueError, TypeError) as error:
            say("warn", f"{plugin_id} would not install", str(error))
            continue
        if reply.get("ok"):
            installed.append(plugin_id)
            say("info", f"bundled plugin ready: {plugin_id}", version)
        else:
            say("warn", f"bundled plugin {plugin_id} failed", reply.get("error", ""))

    return {"ok": True, "installed": installed, "available": len(staged)}


# ---------------------------------------------------------------------------
# Bringing a plugin over from the phone
# ---------------------------------------------------------------------------

def _walk_sources(folder: str):
    for directory, folders, names in os.walk(folder):
        folders[:] = [f for f in folders if not f.startswith(".")]
        for name in names:
            if name.endswith(".py"):
                yield os.path.join(directory, name)


def _unpack(archive: str, into: str) -> str:
    """Unzips a plugin, flattening a single wrapping folder if there is one."""
    os.makedirs(into, exist_ok=True)
    with zipfile.ZipFile(archive) as zipped:
        names = [entry for entry in zipped.namelist() if not entry.endswith("/")]
        if not names:
            raise ValueError("that zip is empty")
        if len(names) > 2000:
            raise ValueError("that zip has more than 2000 files")
        if sum(zipped.getinfo(n).file_size for n in names) > 32 * 1024 * 1024:
            raise ValueError("that zip unpacks to more than 32 MB")
        for entry in names:
            # Never write outside the target, whatever the archive says.
            target = os.path.normpath(os.path.join(into, entry))
            if not target.startswith(os.path.normpath(into) + os.sep):
                raise ValueError(f"that zip tries to write outside itself: {entry}")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zipped.open(entry) as source, open(target, "wb") as out:
                out.write(source.read())
    entries = os.listdir(into)
    if len(entries) == 1 and os.path.isdir(os.path.join(into, entries[0])):
        return os.path.join(into, entries[0])
    return into


def inspect_mobile(path: str) -> dict:
    """Reads a phone plugin and says what will and will not carry over.

    This runs *before* installing, and it does not import anything: reading a
    plugin to decide whether to run it, and then running it to find out, are
    not the same thing.
    """
    path = os.path.abspath(path)
    workspace = None
    folder = path

    if os.path.isfile(path) and path.lower().endswith(".zip"):
        import tempfile

        workspace = tempfile.mkdtemp(prefix="pycmd-inspect-")
        try:
            folder = _unpack(path, workspace)
        except (zipfile.BadZipFile, ValueError, OSError) as error:
            return {"ok": False, "error": str(error)}
    elif not os.path.isdir(path):
        return {"ok": False, "error": "a plugin is a folder or a .zip of one"}

    manifest = _read_manifest(folder)
    if not manifest:
        return {"ok": False, "error": "no plugin.json in there"}

    warnings = []
    for permission in manifest.get("permissions", []) or []:
        note = MOBILE_ONLY_PERMISSIONS.get(str(permission))
        if note:
            warnings.append({"about": f"permission: {permission}", "detail": note})

    # What the compatibility layer covers, and what genuinely cannot work.
    # This used to be a list of things that "might not work", which is an
    # honest report and a useless one - the plugin either runs or it does not.
    handled, unsupported = [], []
    for source in _walk_sources(folder):
        try:
            with open(source, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        relative = os.path.relpath(source, folder)
        found = mobile.report(text)
        for row in found["handled"]:
            handled.append({"about": relative, "uses": row["uses"], "detail": row["why"]})
        for row in found["unsupported"]:
            unsupported.append({"about": relative, "uses": row["uses"],
                                "detail": row["why"]})
            warnings.append({"about": relative,
                             "detail": f"{relative} {row['why']}."})

    tab = manifest.get("tab") or {}
    return {
        "ok": True,
        "folder": folder,
        "temp": workspace or "",
        "id": manifest.get("id", ""),
        "name": manifest.get("name", "") or manifest.get("id", ""),
        "version": manifest.get("version", ""),
        "author": manifest.get("author", ""),
        "description": manifest.get("description", ""),
        "tab": tab.get("title", ""),
        "commands": [c.get("name", "") for c in manifest.get("commands", []) or []],
        "permissions": list(manifest.get("permissions", []) or []),
        "warnings": warnings,
        "handled": handled,
        "unsupported": unsupported,
        # A plugin whose Android bits are all covered by the shim is a full
        # plugin here, and is told so rather than installed as a beta. Only
        # something genuinely unsupported - an Android view, phone hardware -
        # makes it partial.
        "full": not unsupported,
        "likely": "fine" if not unsupported else "mixed",
        "verdict": (
            "This runs here in full." if not unsupported else
            f"This runs, except for {len(unsupported)} part(s) that need a phone."
        ),
    }
