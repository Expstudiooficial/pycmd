"""The custom-plugin runtime: install, load, run, and talk to the UI.

A plugin is Python that the app imports into its own interpreter, plus an
optional HTML panel that becomes a tab. That is the whole idea, and its cost
has to be said plainly rather than buried: a plugin runs with exactly the
permissions the app has. It can read and write the workspace, open sockets,
and install packages. There is no sandbox, because CPython does not have one
worth the name - `exec` in a stripped namespace stops nobody who can spell
``__builtins__``. The app therefore does the only honest thing: it says so
before installing, on a screen the user has to read.

Three shapes are accepted:

* ``thing.py``            - one file, with a ``PLUGIN = {...}`` dict in it.
* ``thing/``              - a folder with ``plugin.json`` and an entry module.
* ``thing.zip``           - the same folder, zipped.

See PLUGINS.md for the authoring guide; this module is the other half of that
document, and the two are meant to be read together.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import time
import traceback
import zipfile

__all__ = [
    "configure", "install", "listing", "remove", "load_all", "unload",
    "call_export", "run_command", "commands", "fire", "panel_html",
    "plugin_dir", "read_manifest", "errors",
]

MANIFEST_NAME = "plugin.json"
MAX_PLUGIN_BYTES = 32 * 1024 * 1024
MAX_FILES = 2000

# What a manifest may contain. Anything else is kept but ignored, so a plugin
# written for a later version still installs.
REQUIRED_KEYS = ("id", "name")
KNOWN_PERMISSIONS = ("files", "network", "console", "servers", "packages")

_plugins_dir = ""
_workspace_dir = ""
_host = None

# id -> {"manifest": dict, "module": module, "api": Api, "error": str}
_loaded = {}
_errors = {}


def configure(plugins_dir: str, workspace_dir: str, host=None) -> str:
    """Called once by the app. `host` is the Kotlin side, or None on desktop."""
    global _plugins_dir, _workspace_dir, _host

    _plugins_dir = plugins_dir
    _workspace_dir = workspace_dir
    _host = host
    os.makedirs(plugins_dir, exist_ok=True)
    return plugins_dir


def app_action(sender: str, action: str, **detail) -> bool:
    """Asks the app for something, from outside a plugin.

    The console's own commands need the same three or four things plugins do -
    open this file, serve that folder, switch tab - and there is no reason for
    a second bridge. `sender` is the id the app sees; the console uses a
    reserved one it always trusts.
    """
    if _host is None:
        return False
    try:
        _host.onPluginAction(sender, action, _json(detail))
        return True
    except Exception as error:  # noqa: BLE001
        _report("warn", f"the app refused {action}", str(error))
        return False


def plugin_dir(plugin_id: str) -> str:
    return os.path.join(_plugins_dir, _safe_id(plugin_id))


# ----------------------------------------------------------------- installing

def install(source: str, source_name: str = "", bundled: str = "") -> str:
    """Installs from a file, a folder or a zip. Returns a JSON result.

    `bundled` marks a plugin that came out of the APK rather than from the
    user. It changes nothing about how the plugin runs - it is still ordinary
    Python with the app's own powers - but the list has to be able to say
    which is which, because "installed by you" was a lie for the ones we put
    there ourselves.
    """
    try:
        manifest, staged = _stage(source, source_name)
    except PluginError as error:
        return _json({"ok": False, "error": str(error)})
    except Exception as error:  # noqa: BLE001
        return _json({"ok": False, "error": f"{type(error).__name__}: {error}"})

    target = plugin_dir(manifest["id"])
    replaced = os.path.isdir(target)
    retired = ""
    try:
        if replaced:
            unload(manifest["id"])
            # Moved aside rather than deleted, and then swapped in one
            # rename. Deleting first left a window where the plugin's folder
            # did not exist, or existed half-emptied, and anything reading it
            # at that moment - a load, a panel, a command - found a file gone
            # that had been there a moment earlier.
            #
            # It also cannot nest any more. `shutil.move` into a folder that
            # still exists puts the source *inside* it, so a delete that only
            # half worked used to leave main.py one level down and a plugin
            # that looked installed and could not be loaded.
            retired = os.path.join(
                _plugins_dir, f".retired-{_safe_id(manifest['id'])}-{int(time.time() * 1000)}"
            )
            shutil.rmtree(retired, ignore_errors=True)
            os.rename(target, retired)
        os.rename(staged, target)
    except OSError as error:
        # Put back what was there. A failed update must not leave somebody
        # with nothing where a working plugin used to be.
        if retired and os.path.isdir(retired) and not os.path.isdir(target):
            try:
                os.rename(retired, target)
            except OSError:
                pass
        elif retired:
            shutil.rmtree(retired, ignore_errors=True)
        shutil.rmtree(staged, ignore_errors=True)
        return _json({"ok": False, "error": f"could not save the plugin: {error}"})

    if retired:
        shutil.rmtree(retired, ignore_errors=True)

    manifest["installed_at"] = int(time.time())
    manifest["bundled"] = bool(bundled) and bundled != "0"
    _write_manifest(target, manifest)

    # Re-read from where it now lives. The manifest in hand was validated in
    # the staging folder, so anything resolved to an absolute path - a tab or
    # section icon - still points at a folder that has just been moved away.
    try:
        manifest = read_manifest(target)
    except PluginError:
        pass
    return _json({"ok": True, "replaced": replaced, "manifest": manifest})


def _tidy_scratch() -> None:
    """Clears anything a killed install left behind.

    Staging and retired folders are named with a leading dot so the listing
    walks past them, which also means nothing else would ever notice one
    sitting there taking up room.
    """
    if not os.path.isdir(_plugins_dir):
        return
    for name in os.listdir(_plugins_dir):
        if name.startswith(".staging-") or name.startswith(".retired-"):
            shutil.rmtree(os.path.join(_plugins_dir, name), ignore_errors=True)


def _stage(source: str, source_name: str):
    """Copies a candidate into a scratch folder and reads its manifest."""
    _tidy_scratch()
    scratch = os.path.join(_plugins_dir, f".staging-{int(time.time() * 1000)}")
    shutil.rmtree(scratch, ignore_errors=True)
    os.makedirs(scratch, exist_ok=True)

    try:
        if os.path.isdir(source):
            _copy_tree(source, scratch)
        elif zipfile.is_zipfile(source):
            _extract_zip(source, scratch)
        elif source.lower().endswith(".py"):
            name = os.path.basename(source_name or source)
            shutil.copy2(source, os.path.join(scratch, name))
        else:
            raise PluginError(
                "a plugin is a .py file, a folder, or a .zip of a folder"
            )

        manifest = read_manifest(scratch)
        return manifest, scratch
    except Exception:
        shutil.rmtree(scratch, ignore_errors=True)
        raise


def _copy_tree(source: str, target: str) -> None:
    total = 0
    count = 0
    for directory, folders, names in os.walk(source):
        folders[:] = [f for f in folders if not f.startswith(".") and f != "__pycache__"]
        relative = os.path.relpath(directory, source)
        destination = target if relative == "." else os.path.join(target, relative)
        os.makedirs(destination, exist_ok=True)
        for name in names:
            if name.startswith("."):
                continue
            path = os.path.join(directory, name)
            size = os.path.getsize(path)
            total += size
            count += 1
            if total > MAX_PLUGIN_BYTES:
                raise PluginError("that plugin is larger than 32 MB")
            if count > MAX_FILES:
                raise PluginError("that plugin has more than 2000 files")
            shutil.copy2(path, os.path.join(destination, name))


def _extract_zip(source: str, target: str) -> None:
    with zipfile.ZipFile(source) as archive:
        entries = [e for e in archive.infolist() if not e.is_dir()]
        if len(entries) > MAX_FILES:
            raise PluginError("that zip has more than 2000 files")
        if sum(e.file_size for e in entries) > MAX_PLUGIN_BYTES:
            raise PluginError("that zip unpacks to more than 32 MB")

        # A zip made by right-clicking a folder has everything under one top
        # directory; one made by selecting the contents does not. Both should
        # install, so the common prefix is stripped when there is exactly one.
        roots = {e.filename.split("/", 1)[0] for e in entries}
        strip = len(roots) == 1 and any("/" in e.filename for e in entries)

        for entry in entries:
            name = entry.filename
            if strip:
                name = name.split("/", 1)[1] if "/" in name else name
            if not name or name.startswith("__MACOSX"):
                continue
            destination = _safe_join(target, name)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with archive.open(entry) as handle, open(destination, "wb") as out:
                shutil.copyfileobj(handle, out)


def _safe_join(root: str, relative: str) -> str:
    """Refuses the `../../etc/passwd` trick that zip files are famous for.

    Both sides are made absolute before comparing, and the separator is part
    of the comparison: without it a folder called `pluginsX` would pass a
    prefix test against `plugins`.
    """
    base = os.path.abspath(root)
    target = os.path.abspath(os.path.join(base, relative))
    if target != base and not target.startswith(base + os.sep):
        raise PluginError(f"the zip tries to write outside its folder: {relative}")
    return target


class PluginError(Exception):
    pass


# ------------------------------------------------------------------ manifests

def read_manifest(folder: str) -> dict:
    """Finds and validates the manifest of a staged plugin folder."""
    path = os.path.join(folder, MANIFEST_NAME)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
        except ValueError as error:
            raise PluginError(f"{MANIFEST_NAME} is not valid JSON: {error}") from None
        if not isinstance(manifest, dict):
            raise PluginError(f"{MANIFEST_NAME} must contain an object")
        return _validate(manifest, folder)

    # A single-file plugin declares itself in the module.
    scripts = [n for n in sorted(os.listdir(folder)) if n.endswith(".py")]
    if not scripts:
        raise PluginError(
            f"no {MANIFEST_NAME} and no .py file - see PLUGINS.md for the two shapes"
        )
    entry = "main.py" if "main.py" in scripts else scripts[0]
    manifest = _manifest_from_source(os.path.join(folder, entry))
    manifest.setdefault("entry", entry)
    return _validate(manifest, folder)


def _manifest_from_source(path: str) -> dict:
    """Reads a `PLUGIN = {...}` dict without importing the module.

    Importing to find out what something is would run it, and the whole point
    of reading the manifest first is to decide whether to run it at all.
    """
    import ast

    try:
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=os.path.basename(path))
    except (OSError, SyntaxError) as error:
        raise PluginError(f"cannot read {os.path.basename(path)}: {error}") from None

    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "PLUGIN" in names:
                try:
                    value = ast.literal_eval(node.value)
                except ValueError:
                    raise PluginError(
                        "PLUGIN must be a plain dict of literals"
                    ) from None
                if isinstance(value, dict):
                    return dict(value)

    stem = os.path.splitext(os.path.basename(path))[0]
    return {
        "id": f"local.{stem.lower().replace(' ', '-')}",
        "name": stem.replace("_", " ").title(),
        "description": "Installed from a single file with no PLUGIN block.",
    }


def _validate(manifest: dict, folder: str) -> dict:
    for key in REQUIRED_KEYS:
        if not manifest.get(key):
            raise PluginError(f"the manifest needs a {key!r}")

    manifest = dict(manifest)
    manifest["id"] = _safe_id(str(manifest["id"]))
    manifest["name"] = str(manifest["name"])[:60]
    manifest.setdefault("version", "1.0.0")
    manifest.setdefault("author", "")
    manifest.setdefault("description", "")
    manifest["description"] = str(manifest["description"])[:600]
    manifest["bundled"] = bool(manifest.get("bundled"))

    entry = manifest.get("entry") or "main.py"
    manifest["entry"] = entry
    if not os.path.isfile(os.path.join(folder, entry)):
        raise PluginError(f"the entry file {entry!r} is not in the plugin")

    panel = manifest.get("panel")
    if panel:
        if not os.path.isfile(os.path.join(folder, panel)):
            raise PluginError(f"the panel file {panel!r} is not in the plugin")
        manifest["panel"] = panel

    tab = manifest.get("tab")
    if isinstance(tab, str):
        tab = {"title": tab}
    if isinstance(tab, dict):
        # A tab is how a plugin adds a place of its own to the More screen.
        # It needs a name, one line about what it is for, and a picture - the
        # picture is a file inside the plugin, because asking an author to add
        # an icon to the app's own drawables would mean editing the app.
        icon = str(tab.get("icon") or "").strip()[:64]
        image = ""
        if icon and _is_image_name(icon):
            candidate = _safe_join(folder, icon)
            if not os.path.isfile(candidate):
                raise PluginError(f"the tab icon {icon!r} is not in the plugin")
            # The *relative* name is what gets stored. An absolute path would
            # be the staging folder's, and staging is thrown away the moment
            # the plugin is moved into place - which is how the icon came out
            # the far side pointing at nothing.
            image = candidate
        manifest["tab"] = {
            "title": str(tab.get("title") or manifest["name"])[:24],
            "description": str(
                tab.get("description") or manifest.get("description") or ""
            )[:120],
            "icon": icon or "puzzle",
            # Resolved fresh every time the manifest is read, and never saved.
            "image": image,
        }
        if not manifest.get("panel"):
            raise PluginError("a tab needs a panel: the tab is what opens it")
    else:
        manifest.pop("tab", None)

    manifest["extends"] = _validate_extends(manifest.get("extends"), manifest, folder)
    manifest["settings"] = _validate_settings(manifest.get("settings"))
    manifest["guides"] = _validate_guides(manifest.get("guides"), folder)
    manifest["actions"] = _validate_actions(manifest.get("actions"))

    commands = []
    for command in manifest.get("commands") or []:
        if isinstance(command, str):
            command = {"name": command}
        if isinstance(command, dict) and command.get("name"):
            commands.append({
                "name": str(command["name"])[:32],
                "help": str(command.get("help", ""))[:200],
            })
    manifest["commands"] = commands

    permissions = [
        p for p in (manifest.get("permissions") or []) if p in KNOWN_PERMISSIONS
    ]
    manifest["permissions"] = permissions
    return manifest


TAB_IMAGES = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")


def _is_image_name(value: str) -> bool:
    return value.lower().endswith(TAB_IMAGES)


# Screens a plugin may add a section to. Not an open list on purpose: a name
# that does not exist would fail silently, and a plugin author would have no
# way to tell a typo from a section that simply never renders.
#
# The console and the editor are absent because both are a WebView filling the
# screen, with nowhere a card could go that would not be in the way. A plugin
# reaches those two the ways that already exist: console commands, api.print,
# and the file events.
EXTENDABLE_TABS = (
    "files", "servers", "packages", "downloads",
    "plugins", "system", "debug", "guides", "pages", "music",
)

EXTENSION_HEIGHTS = ("short", "medium", "tall")


def _validate_extends(raw, manifest: dict, folder: str) -> list:
    """Checks the sections a plugin wants to add to the app's own tabs.

    This is the other half of `tab`. A tab is a place of your own; an
    extension is a section inside a screen that already exists, which is what
    you want when your plugin is *about* that screen rather than beside it.
    """
    if not raw:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        raise PluginError("'extends' must be a list of sections")

    sections = []
    for entry in raw[:8]:
        if not isinstance(entry, dict):
            raise PluginError("every entry in 'extends' must be an object")
        tab = str(entry.get("tab") or "").strip().lower()
        if tab not in EXTENDABLE_TABS:
            raise PluginError(
                f"'{tab}' is not a screen a plugin can extend; "
                f"pick one of {', '.join(EXTENDABLE_TABS)}"
            )
        panel = str(entry.get("panel") or manifest.get("panel") or "").strip()
        if not panel:
            raise PluginError(f"the {tab} section needs a panel file")
        if not os.path.isfile(_safe_join(folder, panel)):
            raise PluginError(f"the panel file {panel!r} is not in the plugin")

        height = str(entry.get("height") or "medium").strip().lower()
        if height not in EXTENSION_HEIGHTS:
            height = "medium"

        # The same picture rule as a tab: a file the plugin ships, resolved
        # fresh rather than written down, so it survives being installed.
        icon = str(entry.get("icon") or "").strip()[:64]
        image = ""
        if icon and _is_image_name(icon):
            candidate = _safe_join(folder, icon)
            if not os.path.isfile(candidate):
                raise PluginError(f"the section icon {icon!r} is not in the plugin")
            image = candidate

        sections.append({
            "tab": tab,
            "title": str(entry.get("title") or manifest["name"])[:40],
            "description": str(entry.get("description") or "")[:140],
            "panel": panel,
            "height": height,
            "icon": icon,
            "image": image,
            # Whether it starts open. A section that unfolds itself on a screen
            # the user opened for another reason is a nuisance, so this is off
            # unless the plugin asks.
            "open": bool(entry.get("open")),
        })
    return sections


SETTING_KINDS = ("text", "number", "switch", "choice")

# Where a plugin may put an action of its own. `file` is a line in a file's
# menu in the Files tab; `folder` is the same for a folder.
ACTION_TARGETS = ("file", "folder")


def _validate_settings(raw) -> list:
    """Settings a plugin wants the app to render as a form for it.

    A plugin with one switch had to build a whole panel to offer it, which is
    a lot of HTML for a checkbox. Declaring it here gets a real control in the
    plugin's row, and `api.setting("name")` reads whatever the user chose.
    """
    if not raw:
        return []
    if not isinstance(raw, (list, tuple)):
        raise PluginError("'settings' must be a list")

    fields = []
    seen = set()
    for entry in raw[:12]:
        if not isinstance(entry, dict):
            raise PluginError("every setting must be an object")
        name = str(entry.get("name") or "").strip()
        if not name:
            raise PluginError("every setting needs a name")
        if name in seen:
            raise PluginError(f"two settings are both called {name!r}")
        seen.add(name)

        kind = str(entry.get("type") or "text").strip().lower()
        if kind not in SETTING_KINDS:
            raise PluginError(
                f"{kind!r} is not a setting type; pick one of {', '.join(SETTING_KINDS)}"
            )

        field = {
            "name": name[:40],
            "type": kind,
            "label": str(entry.get("label") or name)[:60],
            "help": str(entry.get("help") or "")[:160],
            "default": entry.get("default"),
        }
        if kind == "choice":
            options = [str(o)[:40] for o in (entry.get("options") or [])][:12]
            if len(options) < 2:
                raise PluginError(f"the choice {name!r} needs at least two options")
            field["options"] = options
            if field["default"] not in options:
                field["default"] = options[0]
        elif kind == "switch":
            field["default"] = bool(field["default"])
        elif kind == "number":
            try:
                field["default"] = float(field["default"] or 0)
            except (TypeError, ValueError):
                field["default"] = 0
        else:
            field["default"] = str(field["default"] or "")
        fields.append(field)
    return fields


def _validate_actions(raw) -> list:
    """Lines a plugin adds to a file's or folder's menu in the Files tab."""
    if not raw:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        raise PluginError("'actions' must be a list")

    actions = []
    for entry in raw[:8]:
        if not isinstance(entry, dict):
            raise PluginError("every action must be an object")
        target = str(entry.get("target") or "file").strip().lower()
        if target not in ACTION_TARGETS:
            raise PluginError(
                f"{target!r} is not something an action can be on; "
                f"pick {' or '.join(ACTION_TARGETS)}"
            )
        export = str(entry.get("export") or "").strip()
        label = str(entry.get("label") or "").strip()
        if not export or not label:
            raise PluginError("an action needs a label and the export to call")

        # Matched against the file's extension. Empty means every file, which
        # is what most actions want. Written as a comma-separated string, but
        # normalising has to survive being run again on a manifest that has
        # already been normalised - which is what happens every time an
        # installed plugin is read back.
        raw_types = entry.get("types") or ""
        if isinstance(raw_types, (list, tuple)):
            parts = [str(t) for t in raw_types]
        else:
            parts = str(raw_types).split(",")
        types = [
            "." + part.strip().lower().lstrip(".") for part in parts if part.strip()
        ]
        actions.append({
            "target": target,
            "label": label[:40],
            "export": export[:60],
            "types": types,
        })
    return actions


GUIDE_TYPES = (".md", ".markdown", ".txt", ".html", ".htm")


def _validate_guides(raw, folder: str) -> list:
    """Documents a plugin wants listed in the app's Guides screen.

    A plugin can be installed and switched on and still leave the user with no
    idea what to type. Its own guide belongs where the app's guides are, not
    buried in a panel nobody opens first.
    """
    if not raw:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        raise PluginError("'guides' must be a list")

    guides = []
    for entry in raw[:6]:
        if isinstance(entry, str):
            entry = {"file": entry}
        if not isinstance(entry, dict):
            raise PluginError("every guide must be a file name or an object")
        name = str(entry.get("file") or "").strip()
        if not name:
            raise PluginError("every guide needs a file")
        if not name.lower().endswith(GUIDE_TYPES):
            raise PluginError(
                f"a guide has to be {', '.join(GUIDE_TYPES)} - {name!r} is not"
            )
        if not os.path.isfile(_safe_join(folder, name)):
            raise PluginError(f"the guide {name!r} is not in the plugin")

        stem = os.path.splitext(os.path.basename(name))[0].replace("_", " ").replace("-", " ")
        guides.append({
            "file": name,
            "title": str(entry.get("title") or stem.title())[:60],
            "summary": str(entry.get("summary") or "")[:160],
        })
    return guides


def guide_text(plugin_id: str, name: str) -> str:
    """The text of one of a plugin's guides, for the app to render."""
    plugin_id = _safe_id(plugin_id)
    folder = plugin_dir(plugin_id)
    try:
        manifest = read_manifest(folder)
    except PluginError as error:
        return _json({"ok": False, "error": str(error)})

    if not any(guide["file"] == name for guide in manifest.get("guides", [])):
        return _json({"ok": False, "error": f"{manifest['name']} has no guide called {name!r}"})

    try:
        with open(_safe_join(folder, name), "r", encoding="utf-8") as handle:
            return _json({"ok": True, "name": name, "text": handle.read(400_000)})
    except (OSError, PluginError) as error:
        return _json({"ok": False, "error": str(error)})


def _safe_id(value: str) -> str:
    kept = [c for c in value.strip().lower() if c.isalnum() or c in "._-"]
    identifier = "".join(kept).strip("._-")
    if not identifier:
        raise PluginError("that id has no usable characters in it")
    return identifier[:80]


def _write_manifest(folder: str, manifest: dict) -> None:
    """Saves the manifest, minus anything that is only true where it is now.

    The tab icon's absolute path is the example: written down in the staging
    folder it would be wrong the instant the plugin was moved into place.
    """
    saved = dict(manifest)
    tab = saved.get("tab")
    if isinstance(tab, dict):
        saved["tab"] = {k: v for k, v in tab.items() if k != "image"}
    sections = saved.get("extends")
    if isinstance(sections, list):
        saved["extends"] = [
            {k: v for k, v in section.items() if k != "image"} for section in sections
        ]
    with open(os.path.join(folder, MANIFEST_NAME), "w", encoding="utf-8") as handle:
        json.dump(saved, handle, indent=2)


# ------------------------------------------------------------------- listing

def listing() -> str:
    """Every installed plugin, with whatever state the app needs to draw it."""
    rows = []
    if os.path.isdir(_plugins_dir):
        for name in sorted(os.listdir(_plugins_dir)):
            folder = os.path.join(_plugins_dir, name)
            if not os.path.isdir(folder) or name.startswith("."):
                continue
            try:
                manifest = read_manifest(folder)
            except PluginError as error:
                rows.append({
                    "id": name,
                    "name": name,
                    "broken": True,
                    "error": str(error),
                    "size": _folder_size(folder),
                })
                continue
            manifest["loaded"] = manifest["id"] in _loaded
            manifest["error"] = _errors.get(manifest["id"], "")
            manifest["size"] = _folder_size(folder)
            manifest["files"] = _folder_files(folder)
            rows.append(manifest)
    return _json({"ok": True, "plugins": rows})


def _folder_size(folder: str) -> int:
    total = 0
    for directory, _folders, names in os.walk(folder):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(directory, name))
            except OSError:
                pass
    return total


def _folder_files(folder: str) -> list:
    out = []
    for directory, _folders, names in os.walk(folder):
        for name in sorted(names):
            relative = os.path.relpath(os.path.join(directory, name), folder)
            out.append(relative)
            if len(out) >= 60:
                return out
    return out


def remove(plugin_id: str) -> str:
    unload(plugin_id)
    folder = plugin_dir(plugin_id)
    if not os.path.isdir(folder):
        return _json({"ok": False, "error": "that plugin is not installed"})
    # Renamed out of the way first, for the same reason install swaps rather
    # than deletes: a delete that only half works leaves a folder that still
    # looks like a plugin and no longer is. After the rename it is gone as far
    # as anything reading the plugins folder is concerned, whatever happens to
    # the bytes afterwards.
    retired = os.path.join(
        _plugins_dir, f".retired-{_safe_id(plugin_id)}-{int(time.time() * 1000)}"
    )
    shutil.rmtree(retired, ignore_errors=True)
    try:
        os.rename(folder, retired)
    except OSError:
        shutil.rmtree(folder, ignore_errors=True)
        if os.path.isdir(folder):
            return _json({"ok": False, "error": "that plugin's files would not delete"})
        return _json({"ok": True})
    shutil.rmtree(retired, ignore_errors=True)
    return _json({"ok": True})


def errors() -> str:
    return _json({"ok": True, "errors": _errors})


# ------------------------------------------------------------------- loading

def load_all(enabled_ids) -> str:
    """Loads the enabled plugins and unloads the rest. Returns what happened.

    Takes a comma-separated string as well as a list: what crosses the bridge
    from Kotlin is whatever the caller happened to have, and an empty Kotlin
    collection arrives as an object Python cannot iterate.
    """
    if isinstance(enabled_ids, str):
        names = [part for part in enabled_ids.split(",") if part.strip()]
    elif enabled_ids is None:
        names = []
    else:
        try:
            names = list(enabled_ids)
        except TypeError:
            names = []

    wanted = {_safe_id(str(i)) for i in names if str(i).strip()}

    for plugin_id in list(_loaded):
        if plugin_id not in wanted:
            unload(plugin_id)

    results = []
    for plugin_id in sorted(wanted):
        if plugin_id in _loaded:
            results.append({"id": plugin_id, "ok": True, "already": True})
            continue
        results.append(json.loads(load(plugin_id)))
    return _json({"ok": True, "results": results})


def load(plugin_id: str) -> str:
    """Imports one plugin's entry module with the `pycmd` API in place."""
    plugin_id = _safe_id(plugin_id)
    folder = plugin_dir(plugin_id)
    if not os.path.isdir(folder):
        return _json({"ok": False, "id": plugin_id, "error": "not installed"})

    try:
        manifest = read_manifest(folder)
    except PluginError as error:
        _errors[plugin_id] = str(error)
        return _json({"ok": False, "id": plugin_id, "error": str(error)})

    unload(plugin_id)
    api = Api(plugin_id, manifest, folder)
    module_name = f"pycmd_plugin_{plugin_id.replace('.', '_').replace('-', '_')}"
    entry = os.path.join(folder, manifest["entry"])

    # The plugin's own folder goes on sys.path so it can import its own
    # modules, and comes off again straight away so it cannot shadow anything.
    sys.path.insert(0, folder)
    try:
        specification = importlib.util.spec_from_file_location(module_name, entry)
        module = importlib.util.module_from_spec(specification)
        module.pycmd = api
        module.PLUGIN_DIR = folder
        sys.modules[module_name] = module
        specification.loader.exec_module(module)

        setup = getattr(module, "setup", None)
        if callable(setup):
            setup(api)
    except BaseException as error:  # noqa: BLE001 - a plugin may raise anything
        sys.modules.pop(module_name, None)
        detail = _format_error(error, manifest["name"])
        _errors[plugin_id] = detail
        _report("error", f"{manifest['name']} failed to load", detail)
        return _json({"ok": False, "id": plugin_id, "error": detail})
    finally:
        if sys.path and sys.path[0] == folder:
            sys.path.pop(0)

    _loaded[plugin_id] = {"manifest": manifest, "module": module, "api": api}
    _errors.pop(plugin_id, None)
    # Documented in PLUGINS.md, so it has to actually arrive: a plugin can
    # subscribe to its own load and do the work `setup` was too early for.
    for handler in api.listeners.get("plugin_loaded", []):
        try:
            handler({"id": plugin_id})
        except BaseException as error:  # noqa: BLE001
            _report("error", f"{manifest['name']} failed on plugin_loaded",
                    _format_error(error, manifest["name"]))
    _report("info", f"{manifest['name']} loaded", f"{len(api.exports)} exports, "
                                                  f"{len(api.command_names)} commands")
    return _json({"ok": True, "id": plugin_id, "manifest": manifest,
                  "exports": sorted(api.exports), "commands": api.command_names})


def unload(plugin_id: str) -> None:
    plugin_id = _safe_id(plugin_id)
    entry = _loaded.pop(plugin_id, None)
    if entry is None:
        return
    api = entry["api"]
    try:
        teardown = getattr(entry["module"], "teardown", None)
        if callable(teardown):
            teardown(api)
    except BaseException:  # noqa: BLE001
        pass
    module_name = f"pycmd_plugin_{plugin_id.replace('.', '_').replace('-', '_')}"
    sys.modules.pop(module_name, None)


def _format_error(error: BaseException, name: str) -> str:
    lines = traceback.format_exception(type(error), error, error.__traceback__)
    text = "".join(lines)
    # The app's own frames are noise to a plugin author.
    kept = [line for line in text.splitlines() if "pycmd_plugins.py" not in line]
    return f"{name}: " + "\n".join(kept[-12:])


# ------------------------------------------------------------------- the API

class Api:
    """What a plugin sees as `pycmd`.

    Deliberately small and stable. Everything here is either something the app
    can do for a plugin, or something a plugin needs to be reachable from the
    UI; anything else a plugin wants, it does with the standard library like
    any other Python.
    """

    def __init__(self, plugin_id, manifest, folder) -> None:
        self.id = plugin_id
        self.manifest = manifest
        self.name = manifest.get("name", plugin_id)
        self.dir = folder
        self.workspace = _workspace_dir
        self.version = manifest.get("version", "")
        self.exports = {}
        self.commands = {}
        self.command_names = []
        self.listeners = {}
        self.state_path = os.path.join(folder, ".state.json")

    # -- talking to the user ------------------------------------------------

    def print(self, *values, sep=" ", end="\n") -> None:
        """Writes to the console the user is looking at."""
        text = sep.join(str(v) for v in values) + end
        try:
            sys.stdout.write(text)
        except Exception:  # noqa: BLE001
            pass

    def log(self, message, detail="") -> None:
        """Writes to the debug console, which is where plugin noise belongs."""
        _report("info", f"[{self.name}] {message}", str(detail))

    def warn(self, message, detail="") -> None:
        _report("warn", f"[{self.name}] {message}", str(detail))

    def error(self, message, detail="") -> None:
        _report("error", f"[{self.name}] {message}", str(detail))

    def toast(self, message) -> None:
        if _host is not None:
            try:
                _host.onToast(str(message)[:200])
            except Exception:  # noqa: BLE001
                pass

    # -- asking the app to do something -------------------------------------

    def _ask(self, action: str, **detail) -> bool:
        """Sends the app a request. Returns whether it was delivered.

        Everything here is a request rather than a call: a plugin runs on
        whichever thread it happens to be on, and the app has to do these on
        its own. Delivered is not the same as done, and nothing here waits.
        """
        if _host is None:
            return False
        try:
            _host.onPluginAction(self.id, action, _json(detail))
            return True
        except Exception as error:  # noqa: BLE001
            _report("warn", f"[{self.name}] the app refused {action}", str(error))
            return False

    def open_file(self, path) -> bool:
        """Opens a file in the editor."""
        return self._ask("open_file", path=self._resolve(path))

    def run_file(self, path) -> bool:
        """Runs a file, in whatever language it is, on the console."""
        return self._ask("run_file", path=self._resolve(path))

    def preview(self, path) -> bool:
        """Opens a file in the preview."""
        return self._ask("preview", path=self._resolve(path))

    def serve(self, path, port: int = 0) -> bool:
        """Starts a folder or a file as a server, as the Servers tab would."""
        return self._ask("serve", path=self._resolve(path), port=int(port or 0))

    def go_to(self, tab: str) -> bool:
        """Switches the app to one of its screens.

        `console`, `editor`, `files`, `servers`, `packages`, `downloads`,
        `plugins`, `system`, `debug`, `guides` or `more`.
        """
        return self._ask("go_to", tab=str(tab).strip().lower())

    def open_panel(self, panel: str = "") -> bool:
        """Opens this plugin's own panel, full screen."""
        return self._ask("open_panel", panel=str(panel))

    def new_file(self, name: str, text: str = "") -> bool:
        """Creates a file in the workspace and opens it in the editor."""
        path = self._resolve(name)
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError as error:
            _report("warn", f"[{self.name}] could not create {name}", str(error))
            return False
        return self._ask("open_file", path=path)

    def refresh(self, what: str = "files") -> bool:
        """Tells the app something it is showing has changed underneath it."""
        return self._ask("refresh", what=str(what).strip().lower())

    def request(self, action: str, **detail) -> bool:
        """Asks the app for something by name, for the things with no method.

        The named methods above cover what most plugins need. Some things the
        app can do are too specific to deserve one - two DJ decks, a
        crossfader, the transport controls of whatever else is playing on this
        phone - and a method each would be a plugin API that grew a limb every
        time a plugin wanted something.

        This is the same channel with the name passed in. Everything the
        methods promise still holds: it is a *request*, it is delivered rather
        than done, nothing waits on it, and an action the app has never heard
        of is written to the debug log and ignored. A plugin cannot invent a
        capability with it - it can only ask for one the app already has.

        The answer, when there is one, comes back as an event: ask for
        `mixer.state` and the app fires `mixer_state` at everything listening.
        """
        name = str(action or "").strip().lower()
        if not name or not all(ch.isalnum() or ch in "._-" for ch in name):
            _report("warn", f"[{self.name}] {action!r} is not an action name")
            return False
        return self._ask(name, **detail)

    # -- settings the user can change ---------------------------------------

    def setting(self, name: str, default=None):
        """One of the settings this plugin declared in its manifest.

        The app renders them as a form in the plugin's row, so a plugin does
        not have to build a panel just to have a switch.
        """
        saved = self.store().get("__settings__", {})
        if name in saved:
            return saved[name]
        for field in self.manifest.get("settings", []):
            if field.get("name") == name:
                return field.get("default", default)
        return default

    def set_setting(self, name: str, value) -> None:
        data = self.store()
        settings = dict(data.get("__settings__", {}))
        settings[name] = value
        data["__settings__"] = settings
        self.store(data)

    # -- files --------------------------------------------------------------

    def workspace_path(self, *parts) -> str:
        return os.path.join(_workspace_dir, *parts)

    def read(self, path, default=None):
        try:
            with open(self._resolve(path), "r", encoding="utf-8") as handle:
                return handle.read()
        except OSError:
            return default

    def write(self, path, text) -> bool:
        target = self._resolve(path)
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(text)
            return True
        except OSError as error:
            self.error("could not write", f"{target}: {error}")
            return False

    def files(self, pattern="*"):
        import fnmatch

        found = []
        for directory, folders, names in os.walk(_workspace_dir):
            folders[:] = [f for f in folders if f != "__pycache__"]
            for name in names:
                if fnmatch.fnmatch(name, pattern):
                    found.append(os.path.join(directory, name))
        return sorted(found)

    def _resolve(self, path) -> str:
        return path if os.path.isabs(path) else os.path.join(_workspace_dir, path)

    # -- storage ------------------------------------------------------------

    def store(self, data=None):
        """Reads or writes this plugin's own little JSON store."""
        if data is None:
            try:
                with open(self.state_path, "r", encoding="utf-8") as handle:
                    return json.load(handle)
            except (OSError, ValueError):
                return {}
        try:
            with open(self.state_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            return data
        except (OSError, TypeError) as error:
            self.error("could not save state", str(error))
            return data

    # -- being called from elsewhere ---------------------------------------

    def export(self, function=None, *, name=None):
        """Makes a function callable from the plugin's HTML panel."""
        def register(target):
            self.exports[name or target.__name__] = target
            return target

        return register(function) if function is not None else register

    def command(self, name, help=""):
        """Registers a console command: the user types `name args...`."""
        def register(target):
            self.commands[name] = target
            if name not in self.command_names:
                self.command_names.append(name)
            return target

        return register

    def on(self, event, handler=None):
        """Subscribes to an app event. See PLUGINS.md for the list."""
        def register(target):
            self.listeners.setdefault(event, []).append(target)
            return target

        return register(handler) if handler is not None else register

    def send(self, message) -> None:
        """Pushes a message to the plugin's panel, if one is open."""
        if _host is None:
            return
        try:
            _host.onPluginMessage(self.id, _json(message))
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------- calling into them

def call_export(plugin_id: str, name: str, payload: str = "") -> str:
    """Runs an exported function for the panel. Always returns JSON."""
    entry = _loaded.get(_safe_id(plugin_id))
    if entry is None:
        return _json({"ok": False, "error": "that plugin is not loaded"})

    function = entry["api"].exports.get(name)
    if function is None:
        available = ", ".join(sorted(entry["api"].exports)) or "none"
        return _json({"ok": False, "error": f"no export called {name!r} (has: {available})"})

    try:
        argument = json.loads(payload) if payload else None
    except ValueError:
        argument = payload

    try:
        result = function(argument) if argument is not None else function()
    except BaseException as error:  # noqa: BLE001
        detail = _format_error(error, entry["manifest"]["name"])
        _report("error", f"{entry['manifest']['name']}.{name} raised", detail)
        return _json({"ok": False, "error": detail})

    try:
        return _json({"ok": True, "result": result})
    except TypeError:
        return _json({"ok": True, "result": str(result)})


def plugin_settings(plugin_id: str) -> str:
    """What a plugin declared, and what the user has chosen so far."""
    plugin_id = _safe_id(plugin_id)
    try:
        manifest = read_manifest(plugin_dir(plugin_id))
    except PluginError as error:
        return _json({"ok": False, "error": str(error)})

    state_path = os.path.join(plugin_dir(plugin_id), ".state.json")
    try:
        with open(state_path, "r", encoding="utf-8") as handle:
            saved = json.load(handle).get("__settings__", {})
    except (OSError, ValueError):
        saved = {}

    fields = []
    for field in manifest.get("settings", []):
        row = dict(field)
        row["value"] = saved.get(field["name"], field.get("default"))
        fields.append(row)
    return _json({"ok": True, "settings": fields})


def set_plugin_setting(plugin_id: str, name: str, value: str) -> str:
    """Saves one setting. `value` arrives as text and is coerced to its type.

    Coerced here rather than in the app because the manifest that says what
    type it is lives on this side, and two places deciding what "true" means
    would eventually disagree.
    """
    plugin_id = _safe_id(plugin_id)
    folder = plugin_dir(plugin_id)
    try:
        manifest = read_manifest(folder)
    except PluginError as error:
        return _json({"ok": False, "error": str(error)})

    field = next((f for f in manifest.get("settings", []) if f["name"] == name), None)
    if field is None:
        return _json({"ok": False, "error": f"{plugin_id} has no setting called {name!r}"})

    kind = field["type"]
    if kind == "switch":
        typed = str(value).strip().lower() in ("1", "true", "yes", "on")
    elif kind == "number":
        try:
            typed = float(value)
        except (TypeError, ValueError):
            typed = field.get("default") or 0
        if typed == int(typed):
            typed = int(typed)
    elif kind == "choice":
        typed = value if value in field.get("options", []) else field.get("default")
    else:
        typed = str(value)[:2000]

    state_path = os.path.join(folder, ".state.json")
    try:
        with open(state_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    settings = dict(data.get("__settings__", {}))
    settings[name] = typed
    data["__settings__"] = settings
    try:
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
    except OSError as error:
        return _json({"ok": False, "error": str(error)})

    # A loaded plugin holds its own Api, and api.setting reads the file, so
    # nothing needs reloading - but say what was stored, so the app can show it.
    return _json({"ok": True, "name": name, "value": typed})


def commands() -> str:
    """Every command every loaded plugin has registered.

    Two plugins can want the same word. Dispatch gives it to whichever loaded
    first, which is arbitrary and would be baffling from the outside - so the
    clash is reported in the debug console rather than left to be discovered by
    typing the command and getting the wrong plugin.
    """
    rows = []
    seen = {}
    for plugin_id, entry in _loaded.items():
        for name in entry["api"].command_names:
            if name in seen:
                _report(
                    "warn",
                    f"two plugins register the command {name!r}",
                    f"{seen[name]} has it; {plugin_id} will not be reached by it",
                )
            else:
                seen[name] = plugin_id
            rows.append({
                "plugin": plugin_id,
                "name": name,
                "help": next(
                    (c.get("help", "") for c in entry["manifest"].get("commands", [])
                     if c.get("name") == name),
                    "",
                ),
                "shadowed": name in seen and seen[name] != plugin_id,
            })
    return _json({"ok": True, "commands": rows})


def run_command(name: str, argument: str = "") -> str:
    """Dispatches `name` to whichever plugin registered it."""
    for plugin_id, entry in _loaded.items():
        function = entry["api"].commands.get(name)
        if function is None:
            continue
        try:
            result = function(argument)
        except BaseException as error:  # noqa: BLE001
            detail = _format_error(error, entry["manifest"]["name"])
            sys.stderr.write(detail + "\n")
            return _json({"ok": False, "handled": True, "error": detail})
        # Printing is the documented way to show something, but returning a
        # string is the obvious thing to write, and a command that silently
        # returned its answer into the void was a trap worth closing.
        if result is not None and not isinstance(result, bool):
            text = str(result)
            if text:
                sys.stdout.write(text if text.endswith("\n") else text + "\n")
        return _json({"ok": True, "handled": True, "plugin": plugin_id,
                      "result": None if result is None else str(result)})
    return _json({"ok": True, "handled": False})


def fire(event: str, payload: str = "") -> str:
    """Tells every plugin that something happened. Never raises."""
    try:
        data = json.loads(payload) if payload else {}
    except ValueError:
        data = {"raw": payload}

    delivered = 0
    for plugin_id, entry in list(_loaded.items()):
        for handler in entry["api"].listeners.get(event, []):
            try:
                handler(data)
                delivered += 1
            except BaseException as error:  # noqa: BLE001
                detail = _format_error(error, entry["manifest"]["name"])
                _report("error", f"{entry['manifest']['name']} failed on {event}", detail)
    return _json({"ok": True, "delivered": delivered})


# --------------------------------------------------------------- the panel

BRIDGE = """
<script>
(function () {
  'use strict';
  var pending = {};
  var nextId = 1;
  var listeners = {};

  // What is on its way right now, by name and arguments. Only used by
  // pycmd.poll - see below for why call itself does not look at it.
  var inFlight = {};

  function call(name, payload) {
    var body = JSON.stringify(payload === undefined ? null : payload);
    var signature = name + ':' + body;
    var id = nextId++;
    var slot = { signature: signature };
    var promise = new Promise(function (resolve, reject) {
      slot.resolve = resolve;
      slot.reject = reject;
      pending[id] = slot;
      // A plugin that never answers would otherwise leave the page waiting
      // for ever, which looks exactly like a page that has stopped working.
      slot.timer = setTimeout(function () {
        if (!pending[id]) return;
        delete pending[id];
        if (inFlight[signature] === slot.promise) delete inFlight[signature];
        reject(new Error(name + ' has not answered in two minutes'));
      }, 120000);
    });
    slot.promise = promise;
    inFlight[signature] = promise;
    window.__pycmd_panel.call(String(id), name, body);
    return promise;
  }

  /**
   * A refresh, which is not worth making twice at once.
   *
   * Panels poll, and a phone busy running somebody's script answers slowly:
   * without this a panel left open starts a fresh call every tick while the
   * last one is still out, and a hundred identical questions queue up behind
   * each other. If the very same call is already on its way, this waits for
   * that one instead of asking again.
   *
   * Deliberately not what plain `call` does. Two taps on "Add" with the same
   * values are two jobs, not one, and a bridge that quietly turned them into
   * one would be a bridge that loses work. This is the opt-in version, for
   * reads that are asked over and over.
   */
  function poll(name, payload) {
    var signature = name + ':' + JSON.stringify(payload === undefined ? null : payload);
    return inFlight[signature] || call(name, payload);
  }

  window.__pycmd_resolve = function (id, ok, body) {
    var slot = pending[id];
    if (!slot) return;
    delete pending[id];
    if (slot.timer) clearTimeout(slot.timer);
    // Only if it is still this one: two plain calls with the same arguments
    // both write here, and the first to come back must not clear the second.
    if (inFlight[slot.signature] === slot.promise) delete inFlight[slot.signature];
    var parsed;
    try { parsed = JSON.parse(body); } catch (e) { parsed = body; }
    if (ok) slot.resolve(parsed && parsed.result !== undefined ? parsed.result : parsed);
    else slot.reject(new Error(parsed && parsed.error ? parsed.error : String(body)));
  };

  window.__pycmd_message = function (body) {
    var parsed;
    try { parsed = JSON.parse(body); } catch (e) { parsed = body; }
    (listeners.message || []).forEach(function (fn) { fn(parsed); });
  };

  window.pycmd = {
    call: call,
    poll: poll,
    on: function (event, fn) { (listeners[event] = listeners[event] || []).push(fn); },
    toast: function (text) { window.__pycmd_panel.toast(String(text)); },
    log: function (text) { window.__pycmd_panel.log(String(text)); },
    close: function () { window.__pycmd_panel.close(); },
    plugin: JSON.parse(window.__pycmd_panel.manifest())
  };

  // Whether the finger came down on something the page scrolls itself.
  //
  // A panel sitting inside one of the app's own screens is a scrolling view
  // inside a scrolling list, and the app decides which of the two owns a drag
  // by asking the WebView whether its document has anywhere left to go. A
  // page that scrolls an element instead - a list with `overflow-y: auto`,
  // which is the shape a panel wants - answers "nowhere", and the list takes
  // the drag away. So the page says so, and the app holds on.
  function scrollableUnder(node) {
    while (node && node.nodeType === 1 && node !== document.body) {
      var style = window.getComputedStyle(node);
      if (/(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 1) {
        return true;
      }
      node = node.parentNode;
    }
    return false;
  }

  // Whether the finger came down on something that owns the whole drag.
  //
  // A slider is the case that matters. Dragging one is sideways, and the app
  // behind the panel is a list that scrolls up and down - so the app has to
  // be told to keep its hands off before the first move arrives, or the drag
  // is taken away a few pixels in and the thumb stops following the finger.
  //
  // `touch-action: none` is the standard way a page says "this element
  // handles its own gestures", so anything carrying it counts too, and a
  // panel can mark anything else with `data-pycmd-drag`.
  function grabsDrag(node) {
    while (node && node.nodeType === 1 && node !== document.body) {
      var tag = (node.tagName || '').toLowerCase();
      var type = (node.getAttribute('type') || '').toLowerCase();
      if (tag === 'input' && (type === 'range' || type === 'color')) return true;
      if (node.hasAttribute && node.hasAttribute('data-pycmd-drag')) return true;
      var style = window.getComputedStyle(node);
      if (style && style.touchAction === 'none') return true;
      node = node.parentNode;
    }
    return false;
  }

  if (typeof document !== 'undefined' && document.addEventListener) {
    document.addEventListener('touchstart', function (event) {
      var panel = window.__pycmd_panel;
      if (!panel) return;
      try {
        var scrolls = scrollableUnder(event.target);
        var grabs = grabsDrag(event.target);
        if (panel.ownsGesture) {
          panel.ownsGesture(scrolls, grabs);
        } else if (panel.innerScroll) {
          // An older host, which has one answer rather than two. A control
          // that owns the drag is the more important of the two to report.
          panel.innerScroll(scrolls || grabs);
        }
      } catch (error) {
        // An older host without either; the app keeps its old guess.
      }
    }, { passive: true });
  }

  window.addEventListener('error', function (event) {
    if (window.__pycmd_panel) window.__pycmd_panel.log('panel error: ' + event.message);
  });
})();
</script>
"""

PANEL_CSS = """
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; }
/*
  The panel is an ordinary page and the document is what scrolls.

  2.5.8 tried to make `body` its own scroller - `height: 100%` on the root and
  on the body, with the overflow moved down to it. In a browser that is a
  clean app shell. In the app's WebView it collapsed every panel to nothing:
  a black screen with a sliver of content at the top. Whatever the WebView
  resolves those percentages against while the page is first laid out, it is
  not the height the panel ends up with, and it does not come back.

  So: no percentage heights here, and nothing that depends on one. A panel is
  a page, and a page taller than the screen scrolls the way pages do.
*/
body {
  margin: 0; padding: 16px 14px 32px;
  background: #0B0F14; color: #DCE3EC;
  font: 15px/1.55 -apple-system, "Segoe UI", Roboto, sans-serif;
}
h1, h2, h3 { color: #F1F5FA; line-height: 1.25; margin: 1.2em 0 .5em; }
h1 { font-size: 1.5em; } h2 { font-size: 1.2em; }
button {
  font: inherit; padding: 10px 16px; border-radius: 12px;
  border: 1px solid #2E7DD1; background: #16324D; color: #DCE3EC;
}
button:active { background: #1E4269; }
input, textarea, select {
  font: inherit; width: 100%; padding: 10px 12px; border-radius: 12px;
  border: 1px solid #223041; background: #10161F; color: #DCE3EC;
}
pre, code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: .9em; }
pre { background: #10161F; border: 1px solid #223041; border-radius: 10px; padding: 12px; overflow-x: auto; }
.card { background: #121A24; border: 1px solid #223041; border-radius: 14px; padding: 14px; margin: 10px 0; }
a { color: #6FB3FF; }
</style>
"""


def panel_html(plugin_id: str, panel_file: str = "") -> str:
    """The plugin's panel with the bridge and the house style injected.

    `panel_file` picks one of the plugin's other pages - a section it adds to
    one of the app's own screens has its own file, and it is the same bridge
    and the same stylesheet either way.
    """
    plugin_id = _safe_id(plugin_id)
    folder = plugin_dir(plugin_id)
    try:
        manifest = read_manifest(folder)
    except PluginError as error:
        return _error_page(str(error))

    panel = panel_file or manifest.get("panel")
    if not panel:
        return _error_page(f"{manifest['name']} has no panel to show.")
    try:
        resolved = _safe_join(folder, panel)
    except PluginError as error:
        return _error_page(str(error))
    if not os.path.isfile(resolved):
        return _error_page(f"{panel} is not in {manifest['name']}.")

    try:
        with open(resolved, "r", encoding="utf-8") as handle:
            body = handle.read()
    except OSError as error:
        return _error_page(f"could not read {panel}: {error}")

    head = PANEL_CSS + BRIDGE
    lowered = body.lower()
    if "</head>" in lowered:
        index = lowered.index("</head>")
        return body[:index] + head + body[index:]
    if "<body" in lowered:
        index = lowered.index("<body")
        end = body.index(">", index) + 1
        return body[:end] + head + body[end:]
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        + head + "</head><body>" + body + "</body></html>"
    )


def _error_page(message: str) -> str:
    escaped = (message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        + PANEL_CSS +
        "</head><body><div class='card'><h2>This panel could not open</h2>"
        f"<pre>{escaped}</pre></div></body></html>"
    )


# ------------------------------------------------------------------ plumbing

def _json(value) -> str:
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError) as error:
        return json.dumps({"ok": False, "error": f"could not encode the result: {error}"})


def _report(level: str, message: str, detail: str = "") -> None:
    if _host is None:
        return
    try:
        _host.onPluginLog(level, message, detail)
    except Exception:  # noqa: BLE001
        pass
