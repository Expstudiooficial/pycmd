"""The handlers Windows 4.0 added, kept out of host.py so that file stays readable.

Each is (host, payload) -> dict, exactly like the ones in host.HANDLERS, and
they are merged into that table at import. Grouped by screen.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import io
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import zipfile

from . import envpath, install, learn, portable, store, toolchains

WINDOWS = os.name == "nt"


def _no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0


def _settings_get(key: str, default):
    value = store.settings().get(key, default)
    return value if isinstance(value, type(default)) else default


def _settings_put(key: str, value) -> None:
    data = store.settings()
    data[key] = value
    store.save_settings(data)


# ---------------------------------------------------------------------------
# PyCmd Learn
# ---------------------------------------------------------------------------

def _h_learn(host, payload):
    reply = learn.catalogue()
    reply["runners"] = learn.runners()
    return reply


def _h_learn_course(host, payload):
    return learn.course(str(payload.get("course", "")))


def _h_learn_lesson(host, payload):
    return learn.lesson(str(payload.get("course", "")), str(payload.get("lesson", "")))


def _h_learn_check(host, payload):
    return learn.check(str(payload.get("course", "")), str(payload.get("lesson", "")),
                       str(payload.get("answer", "")))


def _h_learn_complete(host, payload):
    return learn.complete(str(payload.get("course", "")), str(payload.get("lesson", "")))


def _h_learn_snippet(host, payload):
    return learn.snippet(str(payload.get("course", "")), str(payload.get("lesson", "")))


def _h_learn_search(host, payload):
    return learn.search(str(payload.get("text", "")))


def _h_learn_review(host, payload):
    return learn.review()


def _h_learn_goal(host, payload):
    return learn.goal(int(payload.get("goal", 10) or 10))


def _h_learn_reset(host, payload):
    return learn.reset(str(payload.get("course", "")))


# -- a PyCmd account (pycmd_teach/cloud.py does the work) --------------------

def _h_account(host, payload):
    return learn.account("account")


def _h_account_username(host, payload):
    return learn.account("username", str(payload.get("name", "")))


def _h_account_signup(host, payload):
    return learn.account("signup", str(payload.get("username", "")),
                         str(payload.get("password", "")))


def _h_account_login(host, payload):
    return learn.account("login", str(payload.get("username", "")),
                         str(payload.get("password", "")))


def _h_account_logout(host, payload):
    return learn.account("logout")


def _h_account_sync(host, payload):
    return learn.account("sync")


def _h_account_password(host, payload):
    return learn.account("password", str(payload.get("old", "")), str(payload.get("new", "")))


def _h_account_delete(host, payload):
    return learn.account("delete_account", str(payload.get("password", "")))


def _h_progress_export(host, payload):
    """Progress to a .json file: the save dialog, or a path when there is no window."""
    reply = learn.account("export", "PyCmd for Windows")
    if not reply.get("ok"):
        return reply
    path = str(payload.get("path", ""))
    if not path:
        window = getattr(host, "window", None)
        if window is None:
            return {"ok": False, "error": "there is no window to open a save dialog in"}
        import webview

        chosen = window.create_file_dialog(webview.SAVE_DIALOG,
                                           save_filename=reply["filename"],
                                           file_types=(_KINDS["json"],))
        if not chosen:
            return {"ok": True, "cancelled": True}
        path = chosen if isinstance(chosen, str) else list(chosen)[0]
    if not path.lower().endswith(".json"):
        path += ".json"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(reply["text"])
    return {"ok": True, "path": path, "lessons": reply.get("lessons", 0)}


def _h_progress_import(host, payload):
    mode = "replace" if payload.get("mode") == "replace" else "merge"
    path = str(payload.get("path", ""))
    if not path:
        window = getattr(host, "window", None)
        if window is None:
            return {"ok": False, "error": "there is no window to open a file dialog in"}
        import webview

        chosen = window.create_file_dialog(webview.OPEN_DIALOG, file_types=(
            _KINDS["json"], _KINDS["any"]))
        if not chosen:
            return {"ok": True, "cancelled": True}
        path = chosen if isinstance(chosen, str) else list(chosen)[0]
    try:
        if os.path.getsize(path) > 5 * 1024 * 1024:
            return {"ok": False, "error": "That file is too big to be PyCmd progress."}
        with open(path, "r", encoding="utf-8-sig") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as error:
        return {"ok": False, "error": f"could not read {os.path.basename(path)}: {error}"}
    return learn.account("import", text, mode)


# -- 5.0: cloud storage, 800 KB per account --------------------------------

def _h_cloud_files(host, payload):
    """Lists the files in your 800 KB of PyCmd cloud storage, with space used."""
    return learn.account("cloud_files")


def _h_cloud_get(host, payload):
    """Reads one cloud file (text, and content_b64 for any file)."""
    return learn.account("cloud_get", str(payload.get("name", "")))


def _h_cloud_put(host, payload):
    """Saves text as a cloud file (replacing one of the same name)."""
    import base64

    return learn.account("cloud_put", str(payload.get("name", "")),
                         base64.b64encode(str(payload.get("text", "")).encode()).decode())


def _h_cloud_upload(host, payload):
    """Copies a file from this PC into cloud storage (a file dialog if no path)."""
    path = str(payload.get("path", ""))
    if not path:
        chosen = _h_pick_file(host, {"kinds": ["any"]})
        if not chosen.get("path"):
            return {"ok": True, "cancelled": True}
        path = chosen["path"]
    return learn.account("cloud_upload", path, str(payload.get("name", "")))


def _h_cloud_download(host, payload):
    """Copies a cloud file onto this PC, into workspace/cloud unless a path is given."""
    name = str(payload.get("name", ""))
    target = str(payload.get("path", "")) or os.path.join(store.folder("workspace"), "cloud",
                                                         *name.split("/"))
    return learn.account("cloud_download", name, target)


def _h_cloud_delete(host, payload):
    """Deletes a cloud file."""
    return learn.account("cloud_delete", str(payload.get("name", "")))


def _h_learn_try(host, payload):
    return learn.try_code(str(payload.get("course", "")), str(payload.get("code", "")))


# ---------------------------------------------------------------------------
# Choosing files with the Windows dialog
# ---------------------------------------------------------------------------

_KINDS = {
    "apk": "Android packages (*.apk)",
    "zip": "Zip archives (*.zip)",
    "code": "Code (*.py;*.js;*.ts;*.c;*.cpp;*.cs;*.go;*.rs;*.java;*.kt;*.rb;*.php;*.lua)",
    "json": "PyCmd progress (*.json)",
    "any": "All files (*.*)",
}


def _h_pick_file(host, payload):
    """Opens the system file dialog. Off the window (in a browser) there is none."""
    window = getattr(host, "window", None)
    if window is None:
        return {"ok": False, "error": "there is no window to open a file dialog in - type the path"}
    try:
        import webview

        kinds = [k for k in payload.get("kinds", ["any"]) if k in _KINDS] or ["any"]
        types = tuple(_KINDS[k] for k in kinds) + (() if "any" in kinds else (_KINDS["any"],))
        if payload.get("folder"):
            chosen = window.create_file_dialog(webview.FOLDER_DIALOG)
        elif payload.get("save"):
            chosen = window.create_file_dialog(
                webview.SAVE_DIALOG, save_filename=str(payload.get("name", "")))
        else:
            chosen = window.create_file_dialog(
                webview.OPEN_DIALOG, allow_multiple=bool(payload.get("many")), file_types=types)
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": f"the file dialog did not open: {error}"}
    if not chosen:
        return {"ok": True, "cancelled": True, "path": "", "paths": []}
    paths = [chosen] if isinstance(chosen, str) else list(chosen)
    return {"ok": True, "path": paths[0], "paths": paths}


# ---------------------------------------------------------------------------
# Look and feel: themes, zoom, what's new
# ---------------------------------------------------------------------------

THEMES = {
    "classic-green": {
        "name": "Classic Green", "accent": "#3FCB7E", "accentBg": "#0F2E1E",
        "accentLine": "#1F6B44", "bg": "#080D0A", "surface": "#0F1712", "raised": "#142019",
        "sunken": "#050906", "line": "#1C2C22", "lineSoft": "#16231B", "text": "#CFE3D6",
        "bright": "#F1FAF4", "dim": "#7F9A89", "faint": "#56705F",
    },
    "midnight-blue": {
        "name": "Midnight Blue", "accent": "#3B8FE8", "accentBg": "#12304F",
        "accentLine": "#245B96", "bg": "#090D12", "surface": "#111923", "raised": "#16202C",
        "sunken": "#06090D", "line": "#1F2B3A", "lineSoft": "#18222E", "text": "#C9D4E1",
        "bright": "#F2F6FB", "dim": "#7D8FA5", "faint": "#55657A",
    },
    "halloween": {
        "name": "Halloween", "accent": "#FF8A1F", "accentBg": "#3A1E05",
        "accentLine": "#8A4A10", "bg": "#0B0710", "surface": "#140D1C", "raised": "#1C1226",
        "sunken": "#07040B", "line": "#2A1C38", "lineSoft": "#21162D", "text": "#E8D9F0",
        "bright": "#FFF4E8", "dim": "#9A86AA", "faint": "#6A5A7A",
    },
    "amber-terminal": {
        "name": "Amber Terminal", "accent": "#FFB000", "accentBg": "#2E2100",
        "accentLine": "#7A5600", "bg": "#0A0800", "surface": "#141000", "raised": "#1C1700",
        "sunken": "#060500", "line": "#2E2600", "lineSoft": "#231D00", "text": "#F2D28A",
        "bright": "#FFF1C9", "dim": "#A88B45", "faint": "#76622E",
    },
    "slate": {
        "name": "Slate", "accent": "#8B9CF7", "accentBg": "#20264A",
        "accentLine": "#3E4A8C", "bg": "#0E1014", "surface": "#161920", "raised": "#1D212A",
        "sunken": "#0A0B0E", "line": "#272C38", "lineSoft": "#20242E", "text": "#D3D7E0",
        "bright": "#F5F6FA", "dim": "#8A90A0", "faint": "#5E6474",
    },
    "paper": {
        "name": "Paper (light)", "light": True, "accent": "#1E7A4C", "accentBg": "#DDF1E5",
        "accentLine": "#8CC9A6", "bg": "#F6F4EE", "surface": "#FFFFFF", "raised": "#FBFAF6",
        "sunken": "#EFECE3", "line": "#DAD5C8", "lineSoft": "#E6E2D7", "text": "#2B2F2C",
        "bright": "#111412", "dim": "#666E68", "faint": "#8E958F",
    },
}

DEFAULT_THEME = "classic-green"


def _h_look(host, payload):
    look = _settings_get("look", {})
    theme = look.get("theme", DEFAULT_THEME)
    custom = look.get("custom") if isinstance(look.get("custom"), dict) else None
    return {"ok": True, "theme": theme if (theme in THEMES or theme == "custom") else DEFAULT_THEME,
            "themes": THEMES, "custom": custom, "zoom": float(look.get("zoom", 1.0) or 1.0),
            "font": look.get("font", ""), "fontSize": int(look.get("fontSize", 14) or 14),
            "compact": bool(look.get("compact", False))}


def _h_look_set(host, payload):
    look = _settings_get("look", {})
    if "theme" in payload:
        theme = str(payload["theme"])
        if theme in THEMES or theme == "custom":
            look["theme"] = theme
    if isinstance(payload.get("custom"), dict):
        clean = {}
        for key, value in payload["custom"].items():
            if key == "name":
                clean[key] = str(value)[:40]
            elif key == "light":
                clean[key] = bool(value)
            elif isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                clean[key] = value
        look["custom"] = clean
    if "zoom" in payload:
        look["zoom"] = max(0.6, min(2.0, float(payload["zoom"] or 1.0)))
    if "fontSize" in payload:
        look["fontSize"] = max(10, min(22, int(payload["fontSize"] or 14)))
    if "font" in payload:
        look["font"] = str(payload["font"])[:80]
    if "compact" in payload:
        look["compact"] = bool(payload["compact"])
    _settings_put("look", look)
    return _h_look(host, {})


WHATS_NEW = {
    "version": "5.8",
    "title": "PyCmd for Windows 5.8",
    "items": [
        ["Notes, built in - and you can write in it",
         "Notes is part of PyCmd now, not a plugin, and text edits properly: double-click any card "
         "and type, as often as you like. Your boards came with it."],
        ["A much better board",
         "Right-click menus, select many (Shift+drag or Select), sections that carry their cards, code "
         "cards, **bold** and lists in notes, arrow styles and colours, lock, bring to front, Find, "
         "snap to grid, templates (Kanban, mind map, week, project, pros and cons), drag images in, "
         "and Export to a picture or Markdown."],
        ["AI agents can use it",
         "With MCP on, an AI app can read your boards and add notes to them."],
    ],
}


def _h_whats_new(host, payload):
    seen = _settings_get("seenVersion", "")
    from .host import VERSION

    return {"ok": True, "show": seen != VERSION, **WHATS_NEW}


def _h_whats_new_seen(host, payload):
    from .host import VERSION

    _settings_put("seenVersion", VERSION)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Recent files, console history, notes, snippets, environment variables
# ---------------------------------------------------------------------------

def _h_recent(host, payload):
    rows = [r for r in _settings_get("recent", []) if isinstance(r, dict)]
    return {"ok": True, "recent": [r for r in rows if os.path.exists(r.get("path", ""))][:30]}


def _h_recent_add(host, payload):
    path = str(payload.get("path", ""))
    if not path:
        return {"ok": False, "error": "no path"}
    rows = [r for r in _settings_get("recent", []) if isinstance(r, dict) and r.get("path") != path]
    rows.insert(0, {"path": path, "onDisk": bool(payload.get("onDisk")), "at": time.time()})
    _settings_put("recent", rows[:40])
    return {"ok": True}


def _h_recent_clear(host, payload):
    _settings_put("recent", [])
    return {"ok": True}


def _h_history(host, payload):
    return {"ok": True, "lines": _settings_get("consoleHistory", [])[-500:]}


def _h_history_add(host, payload):
    line = str(payload.get("line", "")).rstrip("\n")
    if not line.strip():
        return {"ok": True}
    lines = [l for l in _settings_get("consoleHistory", []) if isinstance(l, str)]
    if not lines or lines[-1] != line:
        lines.append(line[:2000])
    _settings_put("consoleHistory", lines[-500:])
    return {"ok": True}


def _h_history_clear(host, payload):
    _settings_put("consoleHistory", [])
    return {"ok": True}


def _notes_path() -> str:
    return os.path.join(store.root(), "notes.md")


def _h_notes(host, payload):
    try:
        with open(_notes_path(), "r", encoding="utf-8") as handle:
            return {"ok": True, "text": handle.read()}
    except OSError:
        return {"ok": True, "text": ""}


def _board(call):
    """One Notes-board call on the shared engine (pycmd_board), in the workspace."""
    def handler(host, payload):
        import pycmd_board
        from . import files

        return json.loads(pycmd_board.api(call, json.dumps(payload or {}), files.root()))
    handler.__doc__ = f"Notes board: {call.replace('_', ' ')}."
    return handler


BOARD_CALLS = ("listing", "load", "save", "create", "remove", "images", "image",
               "export_markdown", "export_png", "note", "import_text")


def _h_notes_moved(host, payload):
    """Whether the old scratchpad has gone onto the Board (5.7); `mark` records that it has."""
    if payload.get("mark"):
        _settings_put("notesOnBoard", True)
    return {"ok": True, "done": bool(_settings_get("notesOnBoard", False))}


def _h_notes_save(host, payload):
    text = str(payload.get("text", ""))
    temporary = _notes_path() + ".writing"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(temporary, _notes_path())
    return {"ok": True, "saved": time.time()}


BUILTIN_SNIPPETS = [
    {"name": "Read a file", "language": "python",
     "code": 'with open("data.txt", encoding="utf-8") as f:\n    for line in f:\n        print(line.rstrip())\n'},
    {"name": "HTTP GET", "language": "python",
     "code": 'import urllib.request, json\n\nwith urllib.request.urlopen("https://httpbin.org/json") as r:\n    print(json.load(r))\n'},
    {"name": "Command-line arguments", "language": "python",
     "code": "import argparse\n\np = argparse.ArgumentParser()\np.add_argument(\"name\")\nargs = p.parse_args()\nprint(f\"hi {args.name}\")\n"},
    {"name": "Timer", "language": "python",
     "code": "import time\n\nstart = time.perf_counter()\n# work here\nprint(f\"{time.perf_counter() - start:.3f}s\")\n"},
    {"name": "Fetch JSON", "language": "javascript",
     "code": 'const r = await fetch("https://httpbin.org/json");\nconsole.log(await r.json());\n'},
    {"name": "Read stdin lines", "language": "go",
     "code": 'package main\n\nimport (\n\t"bufio"\n\t"fmt"\n\t"os"\n)\n\nfunc main() {\n\ts := bufio.NewScanner(os.Stdin)\n\tfor s.Scan() {\n\t\tfmt.Println(s.Text())\n\t}\n}\n'},
    {"name": "Hello, C#", "language": "csharp",
     "code": 'var name = args.Length > 0 ? args[0] : "world";\nConsole.WriteLine($"hello {name}");\n'},
    {"name": "List files", "language": "powershell",
     "code": "Get-ChildItem -File | Sort-Object Length -Descending | Select-Object -First 10 Name, Length\n"},
]


def _h_snippets(host, payload):
    mine = [s for s in _settings_get("snippets", []) if isinstance(s, dict)]
    return {"ok": True, "mine": mine, "builtin": BUILTIN_SNIPPETS}


def _h_snippet_save(host, payload):
    name = str(payload.get("name", "")).strip()[:80]
    code = str(payload.get("code", ""))
    if not name or not code:
        return {"ok": False, "error": "a snippet needs a name and some code"}
    mine = [s for s in _settings_get("snippets", []) if isinstance(s, dict) and s.get("name") != name]
    mine.insert(0, {"name": name, "code": code[:100_000],
                    "language": str(payload.get("language", "text"))[:40], "at": time.time()})
    _settings_put("snippets", mine[:300])
    return {"ok": True}


def _h_snippet_remove(host, payload):
    name = str(payload.get("name", ""))
    mine = [s for s in _settings_get("snippets", []) if isinstance(s, dict) and s.get("name") != name]
    _settings_put("snippets", mine)
    return {"ok": True}


def _h_env(host, payload):
    return {"ok": True, "vars": _settings_get("runEnv", {})}


def _h_env_set(host, payload):
    rows = payload.get("vars")
    if not isinstance(rows, dict):
        return {"ok": False, "error": "vars must be an object"}
    clean = {}
    for key, value in rows.items():
        key = str(key).strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            clean[key] = str(value)[:4000]
    _settings_put("runEnv", clean)
    apply_run_env()
    return {"ok": True, "vars": clean}


_applied_env: dict = {}


def apply_run_env() -> None:
    """Puts the user's own variables into the environment every run inherits."""
    global _applied_env
    for key in _applied_env:
        if key not in _settings_get("runEnv", {}):
            os.environ.pop(key, None)
    wanted = _settings_get("runEnv", {})
    for key, value in wanted.items():
        os.environ[key] = value
    _applied_env = dict(wanted)


# ---------------------------------------------------------------------------
# Search in files
# ---------------------------------------------------------------------------

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "target", "bin", "obj",
             ".idea", ".vs", "dist", "build", ".gradle"}
TEXT_LIMIT = 2 * 1024 * 1024


def _h_search(host, payload):
    """Finds text in every file under a folder. Plain text or a regex."""
    root = str(payload.get("folder", "")) or store.folder("workspace")
    needle = str(payload.get("text", ""))
    if not needle:
        return {"ok": False, "error": "what should it look for?"}
    if not os.path.isdir(root):
        return {"ok": False, "error": f"{root} is not a folder"}
    flags = 0 if payload.get("matchCase") else re.IGNORECASE
    try:
        pattern = re.compile(needle if payload.get("regex") else re.escape(needle), flags)
    except re.error as error:
        return {"ok": False, "error": f"that is not a valid regular expression: {error}"}
    globs = [g.strip().lower() for g in str(payload.get("only", "")).split(",") if g.strip()]
    hits, files, scanned = [], 0, 0
    limit = int(payload.get("limit", 500) or 500)
    started = time.time()
    for directory, folders, names in os.walk(root):
        folders[:] = [f for f in folders if f not in SKIP_DIRS and not f.startswith(".")]
        for name in names:
            if globs and not any(name.lower().endswith(g.lstrip("*")) for g in globs):
                continue
            path = os.path.join(directory, name)
            try:
                if os.path.getsize(path) > TEXT_LIMIT:
                    continue
                with open(path, "rb") as handle:
                    raw = handle.read()
            except OSError:
                continue
            if b"\x00" in raw[:4096]:
                continue
            scanned += 1
            text = raw.decode("utf-8", "replace")
            found = False
            for number, line in enumerate(text.splitlines(), 1):
                match = pattern.search(line)
                if match:
                    found = True
                    hits.append({"path": path, "line": number, "column": match.start() + 1,
                                 "text": line.strip()[:300]})
                    if len(hits) >= limit:
                        break
            files += found
            if len(hits) >= limit or time.time() - started > 20:
                break
        if len(hits) >= limit or time.time() - started > 20:
            break
    return {"ok": True, "hits": hits, "files": files, "scanned": scanned,
            "truncated": len(hits) >= limit, "seconds": round(time.time() - started, 2)}


def _h_replace_in_file(host, payload):
    path = str(payload.get("path", ""))
    needle = str(payload.get("text", ""))
    replacement = str(payload.get("with", ""))
    if not os.path.isfile(path) or not needle:
        return {"ok": False, "error": "nothing to replace"}
    flags = 0 if payload.get("matchCase") else re.IGNORECASE
    pattern = re.compile(needle if payload.get("regex") else re.escape(needle), flags)
    with open(path, "r", encoding="utf-8", errors="surrogateescape") as handle:
        text = handle.read()
    new, count = pattern.subn(replacement if payload.get("regex") else replacement.replace("\\", "\\\\"), text)
    if count:
        with open(path, "w", encoding="utf-8", errors="surrogateescape") as handle:
            handle.write(new)
    return {"ok": True, "replaced": count}


# ---------------------------------------------------------------------------
# New project from a template
# ---------------------------------------------------------------------------

TEMPLATES = {
    "python-cli": {
        "name": "Python command-line tool", "language": "python",
        "files": {
            "main.py": 'import argparse\n\n\ndef main():\n    parser = argparse.ArgumentParser(description="{name}")\n'
                       '    parser.add_argument("who", nargs="?", default="world")\n'
                       '    args = parser.parse_args()\n    print(f"hello {{args.who}}")\n\n\n'
                       'if __name__ == "__main__":\n    main()\n',
            "README.md": "# {name}\n\nRun it: `python main.py Ada`\n",
            "requirements.txt": "",
        },
        "open": "main.py",
    },
    "python-web": {
        "name": "Python web server (no dependencies)", "language": "python",
        "files": {
            "server.py": 'from http.server import BaseHTTPRequestHandler, HTTPServer\n\n\n'
                         'class Handler(BaseHTTPRequestHandler):\n    def do_GET(self):\n'
                         '        body = b"<h1>{name}</h1>"\n        self.send_response(200)\n'
                         '        self.send_header("Content-Type", "text/html")\n'
                         '        self.end_headers()\n        self.wfile.write(body)\n\n\n'
                         'print("http://127.0.0.1:8000")\nHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()\n',
            "README.md": "# {name}\n\nRun `server.py`, then open http://127.0.0.1:8000\n",
        },
        "open": "server.py",
    },
    "node": {
        "name": "Node.js script", "language": "javascript",
        "files": {
            "index.js": 'const who = process.argv[2] ?? "world";\nconsole.log(`hello ${{who}}`);\n',
            "package.json": '{{\n  "name": "{slug}",\n  "version": "1.0.0",\n  "type": "module",\n'
                            '  "scripts": {{\n    "start": "node index.js"\n  }}\n}}\n',
            "README.md": "# {name}\n\n`npm start`\n",
        },
        "open": "index.js",
    },
    "website": {
        "name": "Static website", "language": "html",
        "files": {
            "index.html": '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                          '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                          '<title>{name}</title>\n<link rel="stylesheet" href="style.css">\n</head>\n'
                          '<body>\n<main>\n  <h1>{name}</h1>\n  <p>Edit index.html and press Run.</p>\n'
                          '</main>\n<script src="app.js"></script>\n</body>\n</html>\n',
            "style.css": "body {{ font: 16px/1.6 system-ui, sans-serif; margin: 0; }}\n"
                         "main {{ max-width: 40rem; margin: 4rem auto; padding: 0 1rem; }}\n",
            "app.js": 'console.log("{name} loaded");\n',
        },
        "open": "index.html",
    },
    "go": {
        "name": "Go module", "language": "go",
        "files": {
            "go.mod": "module {slug}\n\ngo 1.22\n",
            "main.go": 'package main\n\nimport "fmt"\n\nfunc main() {{\n\tfmt.Println("hello from {name}")\n}}\n',
        },
        "open": "main.go",
    },
    "rust": {
        "name": "Rust (Cargo) project", "language": "rust",
        "files": {
            "Cargo.toml": '[package]\nname = "{slug}"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n',
            "src/main.rs": 'fn main() {{\n    println!("hello from {name}");\n}}\n',
        },
        "open": "src/main.rs",
    },
    "c": {
        "name": "C program with a Makefile", "language": "c",
        "files": {
            "main.c": '#include <stdio.h>\n\nint main(void) {{\n    printf("hello from {name}\\n");\n    return 0;\n}}\n',
            "Makefile": "main: main.c\n\tgcc -Wall -O2 -o main main.c\n\nclean:\n\trm -f main main.exe\n",
        },
        "open": "main.c",
    },
    "csharp": {
        "name": "C# console app", "language": "csharp",
        "files": {
            "Program.cs": 'Console.WriteLine("hello from {name}");\n',
            "{slug}.csproj": '<Project Sdk="Microsoft.NET.Sdk">\n  <PropertyGroup>\n    <OutputType>Exe</OutputType>\n'
                             '    <TargetFramework>net8.0</TargetFramework>\n    <ImplicitUsings>enable</ImplicitUsings>\n'
                             '    <Nullable>enable</Nullable>\n  </PropertyGroup>\n</Project>\n',
        },
        "open": "Program.cs",
    },
    "java": {
        "name": "Java program", "language": "java",
        "files": {
            "Main.java": 'public class Main {{\n    public static void main(String[] args) {{\n'
                         '        System.out.println("hello from {name}");\n    }}\n}}\n',
        },
        "open": "Main.java",
    },
    "powershell": {
        "name": "PowerShell script", "language": "powershell",
        "files": {
            "run.ps1": 'param([string]$Who = "world")\n\nWrite-Output "hello $Who, from {name}"\n',
        },
        "open": "run.ps1",
    },
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"


def _h_templates(host, payload):
    return {"ok": True, "templates": [{"id": k, "name": v["name"], "language": v["language"],
                                       "files": list(v["files"])} for k, v in TEMPLATES.items()]}


def _h_template_create(host, payload):
    template = TEMPLATES.get(str(payload.get("template", "")))
    if template is None:
        return {"ok": False, "error": "no such template"}
    name = str(payload.get("name", "")).strip() or template["name"]
    if re.search(r'[<>:"/\\|?*]', name):
        return {"ok": False, "error": "a project name cannot contain < > : \" / \\ | ? *"}
    parent = str(payload.get("folder", "")) or store.folder("workspace")
    target = os.path.join(parent, name)
    if os.path.exists(target):
        return {"ok": False, "error": f"{target} already exists"}
    slug = _slug(name)
    for rel, body in template["files"].items():
        path = os.path.join(target, rel.replace("{slug}", slug))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body.format(name=name, slug=slug))
    if payload.get("git") and shutil.which("git"):
        subprocess.run(["git", "init", "-q"], cwd=target, capture_output=True, timeout=60,
                       creationflags=_no_window())
    return {"ok": True, "folder": target, "open": os.path.join(target, template["open"])}


# ---------------------------------------------------------------------------
# Text tools that are better done in Python
# ---------------------------------------------------------------------------

def _h_hash(host, payload):
    algorithms = ("md5", "sha1", "sha256", "sha512")
    path = str(payload.get("path", ""))
    digests = {name: hashlib.new(name) for name in algorithms}
    if path:
        if not os.path.isfile(path):
            return {"ok": False, "error": f"{path} is not a file"}
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                for digest in digests.values():
                    digest.update(block)
        size = os.path.getsize(path)
    else:
        data = str(payload.get("text", "")).encode("utf-8")
        for digest in digests.values():
            digest.update(data)
        size = len(data)
    return {"ok": True, "bytes": size, **{k: v.hexdigest() for k, v in digests.items()}}


# ---------------------------------------------------------------------------
# Ports: what is listening, and is this one free
# ---------------------------------------------------------------------------

def _process_names() -> dict:
    names = {}
    if WINDOWS:
        try:
            done = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True,
                                  text=True, timeout=20, creationflags=_no_window())
            for line in done.stdout.splitlines():
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 2 and parts[1].isdigit():
                    names[int(parts[1])] = parts[0]
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        for pid in os.listdir("/proc") if os.path.isdir("/proc") else []:
            if pid.isdigit():
                try:
                    with open(f"/proc/{pid}/comm") as handle:
                        names[int(pid)] = handle.read().strip()
                except OSError:
                    pass
    return names


def listening() -> list:
    rows = []
    if WINDOWS:
        try:
            done = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
                                  timeout=20, creationflags=_no_window())
        except (OSError, subprocess.SubprocessError):
            return rows
        for line in done.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == "TCP" and parts[3] == "LISTENING":
                address, _, port = parts[1].rpartition(":")
                rows.append({"address": address, "port": int(port), "pid": int(parts[4])})
    else:
        for name in ("/proc/net/tcp", "/proc/net/tcp6"):
            try:
                with open(name) as handle:
                    next(handle)
                    for line in handle:
                        parts = line.split()
                        if parts[3] != "0A":
                            continue
                        port = int(parts[1].split(":")[1], 16)
                        rows.append({"address": "*", "port": port, "pid": 0, "inode": parts[9]})
            except (OSError, StopIteration):
                pass
    names = _process_names()
    seen, out = set(), []
    for row in sorted(rows, key=lambda r: r["port"]):
        key = (row["port"], row["pid"])
        if key in seen:
            continue
        seen.add(key)
        row["process"] = names.get(row["pid"], "")
        out.append(row)
    return out


def _h_ports(host, payload):
    return {"ok": True, "listening": listening()}


def _h_port_check(host, payload):
    port = int(payload.get("port", 0) or 0)
    if not 0 < port < 65536:
        return {"ok": False, "error": "a port is a number from 1 to 65535"}
    free = True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            free = False
    owner = next((r for r in listening() if r["port"] == port), None)
    return {"ok": True, "port": port, "free": free, "owner": owner}


def _h_port_kill(host, payload):
    pid = int(payload.get("pid", 0) or 0)
    if pid <= 4 or pid == os.getpid():
        return {"ok": False, "error": "that process is not one to stop"}
    try:
        if WINDOWS:
            done = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                                  text=True, timeout=20, creationflags=_no_window())
            ok = done.returncode == 0
            message = (done.stdout or done.stderr).strip()
        else:
            os.kill(pid, 15)
            ok, message = True, "stopped"
    except (OSError, subprocess.SubprocessError) as error:
        return {"ok": False, "error": str(error)}
    return {"ok": ok, "message": message}


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------

def _git(folder: str, *args, timeout: float = 60) -> tuple:
    git = shutil.which("git")
    if not git:
        return False, "git is not installed - the Toolchains tab can install it"
    try:
        done = subprocess.run([git, *args], cwd=folder, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout,
                              stdin=subprocess.DEVNULL, creationflags=_no_window(),
                              env=dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat"))
    except subprocess.TimeoutExpired:
        return False, f"git {args[0]} did not finish in {timeout:g} seconds"
    except OSError as error:
        return False, str(error)
    return done.returncode == 0, (done.stdout + ("\n" + done.stderr if done.stderr else "")).strip()


def _h_git(host, payload):
    folder = str(payload.get("folder", "")) or store.folder("workspace")
    if not shutil.which("git"):
        return {"ok": True, "installed": False, "folder": folder}
    ok, top = _git(folder, "rev-parse", "--show-toplevel")
    if not ok:
        return {"ok": True, "installed": True, "repo": False, "folder": folder}
    _, branch = _git(folder, "branch", "--show-current")
    _, status = _git(folder, "status", "--porcelain=v1", "-uall")
    _, log = _git(folder, "log", "-n", "30", "--pretty=format:%h%x1f%an%x1f%ar%x1f%s")
    _, branches = _git(folder, "branch", "--format=%(refname:short)")
    _, remote = _git(folder, "remote", "-v")
    _, ahead = _git(folder, "rev-list", "--left-right", "--count", "@{upstream}...HEAD")
    changes = []
    for line in status.splitlines():
        if len(line) > 3:
            changes.append({"index": line[0], "tree": line[1], "path": line[3:]})
    commits = []
    for line in log.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 4:
            commits.append({"hash": parts[0], "author": parts[1], "when": parts[2], "subject": parts[3]})
    counts = ahead.split() if ahead and ahead.split()[0].isdigit() else ["0", "0"]
    return {"ok": True, "installed": True, "repo": True, "folder": folder, "top": top,
            "branch": branch, "changes": changes, "commits": commits,
            "branches": [b for b in branches.splitlines() if b],
            "remote": remote.splitlines()[0] if remote else "",
            "behind": int(counts[0]), "ahead": int(counts[1]) if len(counts) > 1 else 0}


def _h_git_do(host, payload):
    folder = str(payload.get("folder", "")) or store.folder("workspace")
    action = str(payload.get("action", ""))
    path = str(payload.get("path", ""))
    if action == "init":
        return dict(zip(("ok", "output"), _git(folder, "init")))
    if action == "stage":
        return dict(zip(("ok", "output"), _git(folder, "add", "--", path or ".")))
    if action == "unstage":
        return dict(zip(("ok", "output"), _git(folder, "reset", "-q", "--", path or ".")))
    if action == "discard":
        if not path:
            return {"ok": False, "error": "discarding needs a file"}
        return dict(zip(("ok", "output"), _git(folder, "checkout", "--", path)))
    if action == "diff":
        staged = ["--cached"] if payload.get("staged") else []
        ok, out = _git(folder, "diff", *staged, "--", *( [path] if path else []))
        return {"ok": ok, "diff": out[:400_000]}
    if action == "commit":
        message = str(payload.get("message", "")).strip()
        if not message:
            return {"ok": False, "error": "a commit needs a message"}
        if payload.get("all"):
            _git(folder, "add", "-A")
        ok, out = _git(folder, "commit", "-m", message)
        if not ok and "Please tell me who you are" in out:
            return {"ok": False, "error": "git does not know your name yet. Set it once with "
                    "git config --global user.name and user.email.", "output": out}
        return {"ok": ok, "output": out}
    if action in ("pull", "push", "fetch"):
        return dict(zip(("ok", "output"), _git(folder, action, timeout=180)))
    if action == "checkout":
        branch = str(payload.get("branch", "")).strip()
        if not branch:
            return {"ok": False, "error": "which branch?"}
        args = ["checkout", "-b", branch] if payload.get("create") else ["checkout", branch]
        return dict(zip(("ok", "output"), _git(folder, *args)))
    if action == "show":
        ok, out = _git(folder, "show", "--stat", "--patch", str(payload.get("hash", "HEAD")))
        return {"ok": ok, "diff": out[:400_000]}
    if action == "clone":
        url = str(payload.get("url", "")).strip()
        if not re.match(r"^(https://|git@|ssh://)", url):
            return {"ok": False, "error": "that does not look like a git URL"}
        return dict(zip(("ok", "output"), _git(folder, "clone", url, timeout=600)))
    return {"ok": False, "error": f"unknown git action {action!r}"}


# ---------------------------------------------------------------------------
# Tasks: the scripts a project already declares
# ---------------------------------------------------------------------------

def find_tasks(folder: str) -> list:
    tasks = []
    package = os.path.join(folder, "package.json")
    if os.path.isfile(package):
        try:
            with open(package, encoding="utf-8") as handle:
                scripts = json.load(handle).get("scripts", {})
            runner = "npm"
            if os.path.isfile(os.path.join(folder, "pnpm-lock.yaml")):
                runner = "pnpm"
            elif os.path.isfile(os.path.join(folder, "yarn.lock")):
                runner = "yarn"
            elif os.path.isfile(os.path.join(folder, "bun.lockb")) or os.path.isfile(os.path.join(folder, "bun.lock")):
                runner = "bun"
            for name, line in scripts.items():
                tasks.append({"source": "package.json", "name": name, "detail": line,
                              "argv": [runner, "run", name]})
            if not os.path.isdir(os.path.join(folder, "node_modules")):
                tasks.insert(0, {"source": "package.json", "name": "install",
                                 "detail": f"{runner} install", "argv": [runner, "install"]})
        except (OSError, ValueError, AttributeError):
            pass
    makefile = next((os.path.join(folder, n) for n in ("Makefile", "makefile", "GNUmakefile")
                     if os.path.isfile(os.path.join(folder, n))), "")
    if makefile:
        try:
            with open(makefile, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    match = re.match(r"^([A-Za-z0-9_.-]+)\s*:(?!=)", line)
                    if match and not match.group(1).startswith("."):
                        tasks.append({"source": "Makefile", "name": match.group(1),
                                      "detail": f"make {match.group(1)}",
                                      "argv": ["make", match.group(1)]})
        except OSError:
            pass
    if os.path.isfile(os.path.join(folder, "Cargo.toml")):
        for verb in ("build", "run", "test", "check", "clippy", "fmt"):
            tasks.append({"source": "Cargo.toml", "name": verb, "detail": f"cargo {verb}",
                          "argv": ["cargo", verb]})
    if os.path.isfile(os.path.join(folder, "go.mod")):
        for verb, argv in (("run", ["go", "run", "."]), ("build", ["go", "build", "./..."]),
                           ("test", ["go", "test", "./..."]), ("vet", ["go", "vet", "./..."]),
                           ("tidy", ["go", "mod", "tidy"])):
            tasks.append({"source": "go.mod", "name": verb, "detail": " ".join(argv), "argv": argv})
    pyproject = os.path.join(folder, "pyproject.toml")
    if os.path.isfile(pyproject) or os.path.isfile(os.path.join(folder, "requirements.txt")):
        if os.path.isfile(os.path.join(folder, "requirements.txt")):
            tasks.append({"source": "requirements.txt", "name": "install requirements",
                          "detail": "pip install -r requirements.txt",
                          "argv": [sys.executable if not getattr(sys, "frozen", False) else "python",
                                   "-m", "pip", "install", "-r", "requirements.txt"]})
        if os.path.isdir(os.path.join(folder, "tests")) or os.path.isfile(os.path.join(folder, "pytest.ini")):
            tasks.append({"source": "python", "name": "pytest", "detail": "python -m pytest",
                          "argv": ["python", "-m", "pytest"]})
    if any(n.endswith((".csproj", ".fsproj", ".sln")) for n in os.listdir(folder)):
        for verb in ("build", "run", "test"):
            tasks.append({"source": ".NET", "name": verb, "detail": f"dotnet {verb}",
                          "argv": ["dotnet", verb]})
    if os.path.isfile(os.path.join(folder, "gradlew.bat")) or os.path.isfile(os.path.join(folder, "gradlew")):
        wrapper = "gradlew.bat" if WINDOWS else "./gradlew"
        for verb in ("build", "test", "assembleDebug"):
            tasks.append({"source": "Gradle", "name": verb, "detail": f"gradlew {verb}",
                          "argv": [os.path.join(folder, wrapper) if WINDOWS else wrapper, verb]})
    return tasks


def _h_tasks(host, payload):
    folder = str(payload.get("folder", "")) or store.folder("workspace")
    if not os.path.isdir(folder):
        return {"ok": False, "error": f"{folder} is not a folder"}
    rows = find_tasks(folder)
    for row in rows:
        row["available"] = bool(shutil.which(row["argv"][0]) or os.path.isfile(row["argv"][0]))
    return {"ok": True, "folder": folder, "tasks": rows}


def _h_task_run(host, payload):
    from . import runner

    folder = str(payload.get("folder", "")) or store.folder("workspace")
    argv = [str(a) for a in payload.get("argv", []) if str(a)]
    if not argv:
        return {"ok": False, "error": "nothing to run"}
    run_id = "task-" + uuid.uuid4().hex[:8]

    def work():
        host.onOutput("system", f"[PyCmd] {' '.join(argv)}  (in {folder})\n", "console")
        result = runner.run_command(argv, lambda text: host.onOutput("stdout", text, "console"),
                                    cwd=folder, run_id=run_id)
        host.emit("finished", run=run_id, status="ok" if result.get("ok") else "error",
                  millis=0, channel="console")
        if not result.get("ok") and result.get("error"):
            host.onOutput("stderr", f"[PyCmd] {result['error']}\n", "console")

    threading.Thread(target=work, name="pycmd-task", daemon=True).start()
    return {"ok": True, "run": run_id}


# ---------------------------------------------------------------------------
# Zip and unzip
# ---------------------------------------------------------------------------

def _absolute(path: str) -> str:
    """A workspace-relative path made absolute; an absolute one left alone."""
    if not path or os.path.isabs(path):
        return path
    from . import files

    try:
        return files.resolve(path)
    except Exception:  # noqa: BLE001
        return os.path.join(store.folder("workspace"), path)


def _h_zip(host, payload):
    sources = [_absolute(str(p)) for p in payload.get("paths", []) if str(p)]
    if not sources:
        return {"ok": False, "error": "nothing to zip"}
    target = _absolute(str(payload.get("to", ""))) or (os.path.splitext(sources[0].rstrip("\\/"))[0] + ".zip")
    if os.path.abspath(target) in [os.path.abspath(s) for s in sources]:
        return {"ok": False, "error": "a zip cannot contain itself"}
    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for source in sources:
            base = os.path.dirname(os.path.abspath(source))
            if os.path.isdir(source):
                for directory, folders, names in os.walk(source):
                    folders[:] = [f for f in folders if f not in ("__pycache__", ".git", "node_modules")]
                    for name in names:
                        path = os.path.join(directory, name)
                        if os.path.abspath(path) == os.path.abspath(target):
                            continue
                        bundle.write(path, os.path.relpath(path, base))
                        count += 1
            elif os.path.isfile(source):
                bundle.write(source, os.path.basename(source))
                count += 1
    return {"ok": True, "zip": target, "files": count, "bytes": os.path.getsize(target)}


def _h_unzip(host, payload):
    from . import fetch

    archive = _absolute(str(payload.get("path", "")))
    if not os.path.isfile(archive):
        return {"ok": False, "error": f"{archive} is not a file"}
    into = _absolute(str(payload.get("to", ""))) or os.path.splitext(archive)[0]
    if os.path.exists(into) and os.listdir(into) and not payload.get("replace"):
        return {"ok": False, "reason": "exists", "error": f"{into} already has files in it"}
    try:
        fetch.unpack(archive, into, strip_top=bool(payload.get("strip")))
    except fetch.FetchError as error:
        return {"ok": False, "error": str(error)}
    return {"ok": True, "folder": into}


# ---------------------------------------------------------------------------
# System information and a diagnostics bundle
# ---------------------------------------------------------------------------

def _memory() -> dict:
    if WINDOWS:
        try:
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                            ("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong),
                            ("pagetotal", ctypes.c_ulonglong), ("pagefree", ctypes.c_ulonglong),
                            ("virtualtotal", ctypes.c_ulonglong), ("virtualfree", ctypes.c_ulonglong),
                            ("extended", ctypes.c_ulonglong)]

            status = Status()
            status.length = ctypes.sizeof(Status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return {"total": status.total, "free": status.free, "load": status.load}
        except Exception:  # noqa: BLE001
            return {}
    try:
        values = {}
        with open("/proc/meminfo") as handle:
            for line in handle:
                key, value = line.split(":", 1)
                values[key] = int(value.split()[0]) * 1024
        total, free = values.get("MemTotal", 0), values.get("MemAvailable", 0)
        return {"total": total, "free": free, "load": int(100 - free * 100 / total) if total else 0}
    except (OSError, ValueError):
        return {}


def _uptime() -> float:
    if WINDOWS:
        try:
            import ctypes

            return ctypes.windll.kernel32.GetTickCount64() / 1000.0
        except Exception:  # noqa: BLE001
            return 0.0
    try:
        with open("/proc/uptime") as handle:
            return float(handle.read().split()[0])
    except (OSError, ValueError):
        return 0.0


def _h_machine(host, payload):
    drives = []
    if WINDOWS:
        import string

        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if os.path.exists(root):
                try:
                    usage = shutil.disk_usage(root)
                    drives.append({"drive": root, "total": usage.total, "free": usage.free})
                except OSError:
                    pass
    else:
        usage = shutil.disk_usage("/")
        drives.append({"drive": "/", "total": usage.total, "free": usage.free})
    return {"ok": True, "os": platform.platform(), "machine": platform.machine(),
            "cpu": platform.processor() or platform.machine(), "cores": os.cpu_count(),
            "memory": _memory(), "uptime": _uptime(), "drives": drives,
            "python": sys.version.split()[0], "admin": install.is_admin(),
            "user": os.environ.get("USERNAME") or os.environ.get("USER", ""),
            "pathEntries": len([p for p in os.environ.get("PATH", "").split(os.pathsep) if p])}


def _h_diagnostics(host, payload):
    """One zip with everything a bug report needs - and nothing from the workspace."""
    from . import android
    from .host import VERSION

    target = os.path.join(store.folder("downloads"),
                          time.strftime("pycmd-diagnostics-%Y%m%d-%H%M%S.zip"))
    report = {
        "version": VERSION, "when": datetime.datetime.now().isoformat(),
        "machine": _h_machine(host, {}),
        "toolchains": toolchains.summary(),
        "portable": portable.installed(),
        "managers": install.available(),
        "android": android.diagnose(),
        "path": os.environ.get("PATH", "").split(os.pathsep),
    }
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("report.json", json.dumps(report, indent=2, default=str))
        bundle.writestr("log.json", json.dumps(host.log_entries()[-2000:], indent=1, default=str))
        logs = store.folder("logs")
        for name in os.listdir(logs):
            path = os.path.join(logs, name)
            if os.path.isfile(path) and os.path.getsize(path) < 20 * 1024 * 1024:
                bundle.write(path, "logs/" + name)
    return {"ok": True, "zip": target, "bytes": os.path.getsize(target)}


# ---------------------------------------------------------------------------
# Portable toolchains
# ---------------------------------------------------------------------------

def _h_portables(host, payload):
    return {"ok": True, "supported": portable.supported(), "portables": portable.catalogue(),
            "folder": portable.home()}


def _h_portable_install(host, payload):
    which = str(payload.get("id", ""))

    def work():
        result = portable.install(which, lambda text: host.onOutput("stdout", text, "console"))
        envpath.refresh()
        portable.activate_all()
        toolchains.clear_cache()
        host.emit("install-done", toolchain=which, ok=bool(result.get("ok")),
                  error=result.get("error", ""))
        host.emit("toolchains-changed", id=which)

    threading.Thread(target=work, name="pycmd-portable", daemon=True).start()
    return {"ok": True, "queued": True}


def _h_portable_remove(host, payload):
    result = portable.remove(str(payload.get("id", "")))
    toolchains.clear_cache()
    host.emit("toolchains-changed", id=str(payload.get("id", "")))
    return result


def _h_portable_plan(host, payload):
    return portable.plan(str(payload.get("id", "")))


HANDLERS = {
    "learn": _h_learn,
    "learn.course": _h_learn_course,
    "learn.lesson": _h_learn_lesson,
    "learn.check": _h_learn_check,
    "learn.complete": _h_learn_complete,
    "learn.snippet": _h_learn_snippet,
    "learn.search": _h_learn_search,
    "learn.review": _h_learn_review,
    "learn.goal": _h_learn_goal,
    "learn.reset": _h_learn_reset,
    "learn.try": _h_learn_try,
    "account": _h_account,
    "account.username": _h_account_username,
    "account.signup": _h_account_signup,
    "account.login": _h_account_login,
    "account.logout": _h_account_logout,
    "account.sync": _h_account_sync,
    "account.password": _h_account_password,
    "account.delete": _h_account_delete,
    "progress.export": _h_progress_export,
    "cloud.files": _h_cloud_files,
    "cloud.get": _h_cloud_get,
    "cloud.put": _h_cloud_put,
    "cloud.upload": _h_cloud_upload,
    "cloud.download": _h_cloud_download,
    "cloud.delete": _h_cloud_delete,
    "progress.import": _h_progress_import,
    "pick.file": _h_pick_file,
    "look": _h_look,
    "look.set": _h_look_set,
    "whatsnew": _h_whats_new,
    "whatsnew.seen": _h_whats_new_seen,
    "recent": _h_recent,
    "recent.add": _h_recent_add,
    "recent.clear": _h_recent_clear,
    "history": _h_history,
    "history.add": _h_history_add,
    "history.clear": _h_history_clear,
    "notes": _h_notes,
    "notes.save": _h_notes_save,
    "notes.moved": _h_notes_moved,
    **{f"board.{name}": _board(name) for name in BOARD_CALLS},
    "snippets": _h_snippets,
    "snippet.save": _h_snippet_save,
    "snippet.remove": _h_snippet_remove,
    "env": _h_env,
    "env.set": _h_env_set,
    "search": _h_search,
    "search.replace": _h_replace_in_file,
    "templates": _h_templates,
    "template.create": _h_template_create,
    "hash": _h_hash,
    "ports": _h_ports,
    "port.check": _h_port_check,
    "port.kill": _h_port_kill,
    "git": _h_git,
    "git.do": _h_git_do,
    "tasks": _h_tasks,
    "task.run": _h_task_run,
    "zip": _h_zip,
    "unzip": _h_unzip,
    "machine": _h_machine,
    "diagnostics": _h_diagnostics,
    "portables": _h_portables,
    "portable.install": _h_portable_install,
    "portable.remove": _h_portable_remove,
    "portable.plan": _h_portable_plan,
}
