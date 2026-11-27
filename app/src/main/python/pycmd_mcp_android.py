"""PyCmd for Android as an MCP server: an AI agent on your PC drives the phone.

The protocol and HTTP are pycmd_mcp's (shared with Windows). The tools are
the phone's: the workspace's files, Python in the app's own interpreter,
PyCmdTeach, the account and its 800 KB of cloud storage, plugins - and, through
McpBridge on the Kotlin side, the screen itself: tabs, the console, the
editor, screenshots.

With "Allow Wi-Fi" on, it listens on the phone's network address, so an agent
on a PC on the same Wi-Fi can connect; the token is still required.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import platform
import shutil
import sys
import time

import pycmd_mcp

_state = {"server": None, "registry": None, "workspace": "", "error": ""}


def _bridge(action: str, **args):
    """Asks the app (Kotlin) to do something on screen."""
    try:
        from java import jclass

        reply = jclass("com.expstudio.pycmd.mcp.McpBridge").call(action, json.dumps(args))
        return json.loads(str(reply))
    except ImportError:
        return {"ok": False, "error": "the app's screen is not reachable from here"}


def _path(relative: str) -> str:
    root = os.path.realpath(_state["workspace"])
    full = os.path.realpath(os.path.join(root, (relative or "").lstrip("/\\")))
    if full != root and not full.startswith(root + os.sep):
        raise ValueError("paths stay inside the PyCmd workspace")
    return full


def _teach(name, first="", second="", third=""):
    import pycmd_teach

    return json.loads(pycmd_teach.api(name, str(first), str(second), str(third)))


# -- tools -------------------------------------------------------------------

def files_list(path=""):
    folder = _path(path)
    rows = []
    for name in sorted(os.listdir(folder)):
        full = os.path.join(folder, name)
        rows.append({"name": name, "folder": os.path.isdir(full),
                     "size": 0 if os.path.isdir(full) else os.path.getsize(full)})
    return {"ok": True, "path": path or "/", "entries": rows}


def file_read(path):
    with open(_path(path), "rb") as handle:
        data = handle.read(2_000_000)
    try:
        return {"ok": True, "path": path, "text": data.decode("utf-8")}
    except UnicodeDecodeError:
        return {"ok": True, "path": path, "binary": True, "size": len(data)}


def file_write(path, text, append=False):
    full = _path(path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "a" if append else "w", encoding="utf-8") as handle:
        handle.write(text)
    return {"ok": True, "path": path, "size": os.path.getsize(full)}


def file_delete(path):
    full = _path(path)
    if full == os.path.realpath(_state["workspace"]):
        return {"ok": False, "error": "that is the whole workspace"}
    shutil.rmtree(full) if os.path.isdir(full) else os.remove(full)
    return {"ok": True}


def file_move(source, target):
    shutil.move(_path(source), _path(target))
    return {"ok": True}


def make_folder(path):
    os.makedirs(_path(path), exist_ok=True)
    return {"ok": True}


def files_search(text, path=""):
    hits = []
    for folder, _dirs, names in os.walk(_path(path)):
        for name in names:
            full = os.path.join(folder, name)
            try:
                with open(full, encoding="utf-8") as handle:
                    for number, line in enumerate(handle, 1):
                        if text in line:
                            hits.append({"file": os.path.relpath(full, _state["workspace"]),
                                         "line": number, "text": line.strip()[:200]})
                            if len(hits) >= 200:
                                return {"ok": True, "hits": hits, "more": True}
            except (UnicodeDecodeError, OSError):
                continue
    return {"ok": True, "hits": hits}


def run_python(code):
    """Runs Python in the app's interpreter, in a fresh namespace, from the workspace."""
    out = io.StringIO()
    started = time.time()
    previous = os.getcwd()
    try:
        os.chdir(_state["workspace"])
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            exec(compile(code, "<mcp>", "exec"), {"__name__": "__main__"})
        error = ""
    except BaseException as exc:  # noqa: BLE001 - reported, not raised
        error = f"{type(exc).__name__}: {exc}"
    finally:
        os.chdir(previous)
    return {"ok": not error, "output": out.getvalue()[-100_000:], "error": error,
            "seconds": round(time.time() - started, 2)}


def system_info():
    usage = shutil.disk_usage(_state["workspace"])
    return {"ok": True, "python": sys.version.split()[0], "platform": platform.platform(),
            "workspace": _state["workspace"], "free_mb": usage.free // 1_048_576}


def plugins():
    import pycmd_plugins

    return json.loads(pycmd_plugins.listing())


def build(version="") -> pycmd_mcp.Registry:
    r = pycmd_mcp.Registry("pycmd-android", version or "3")
    r.instructions = (
        "You are connected to PyCmd on an Android phone. Files are in its workspace (paths "
        "are relative to it). run_python runs Python on the phone. learn_* is PyCmdTeach, "
        "cloud_* the account's 800 KB of storage. ui_* drives the screen: ui_state to see "
        "where it is, ui_navigate to change tab, ui_screenshot to look, console_run to type "
        "into the Console. Call help first if unsure.")
    path = "a path inside the workspace, e.g. 'site/index.html' ('' is the top)"
    def board(call):
        def run(text="", template="", id=""):
            import json as _json

            import pycmd_board

            body = {"text": text} if call == "note" else ({"template": template} if call == "create" else {"id": id})
            return _json.loads(pycmd_board.api(call, _json.dumps(body), _state["workspace"]))
        return run

    r.add("board_note", "Drops a note (a sticky card) on the current board in the Notes tab.",
          board("note"), {"text": "what the note says"}, ["text"])
    r.add("board_list", "Lists the boards in the Notes tab.", board("listing"), {}, read_only=True)
    r.add("board_read", "Reads one board in full: its cards (notes, to-dos, links...) and the arrows between them.",
          board("load"), {"id": "board id from board_list (empty for the current one)"}, read_only=True)
    r.add("board_new", "Makes a new board: blank, kanban, mindmap, week, project or proscons.",
          board("create"), {"template": "blank | kanban | mindmap | week | project | proscons"})
    r.add("files_list", "Lists a folder in the workspace.", files_list, {"path": path},
          read_only=True)
    r.add("file_read", "Reads a text file from the workspace.", file_read, {"path": path},
          ["path"], read_only=True)
    r.add("file_write", "Writes a text file (creates folders). append=true adds to the end.",
          file_write, {"path": path, "text": "the content", "append": {"type": "boolean"}},
          ["path", "text"])
    r.add("file_delete", "Deletes a file or folder in the workspace.", file_delete,
          {"path": path}, ["path"])
    r.add("file_move", "Moves or renames a file or folder.", file_move,
          {"source": path, "target": path}, ["source", "target"])
    r.add("make_folder", "Creates a folder.", make_folder, {"path": path}, ["path"])
    r.add("files_search", "Finds text in every text file under a folder.", files_search,
          {"text": "what to look for", "path": path}, ["text"], read_only=True)
    r.add("run_python", "Runs Python 3.13 on the phone and returns what it printed.",
          run_python, {"code": "Python source"}, ["code"])
    r.add("system_info", "Python version, Android build, workspace path, free space.",
          system_info, read_only=True)
    r.add("plugins", "The installed plugins.", plugins, read_only=True)
    for name, text, params, ro in (
        ("catalogue", "Every PyCmdTeach course with progress, and the totals.", {}, True),
        ("course", "One course's units and lessons.", {"first": "course id, e.g. 'python'"}, True),
        ("lesson", "One lesson.", {"first": "course id", "second": "lesson id, e.g. '0.0.read'"},
         True),
        ("check", "Answers a lesson.", {"first": "course id", "second": "lesson id",
                                        "third": "the answer"}, False),
        ("complete", "Marks a lesson done.", {"first": "course id", "second": "lesson id"}, False),
        ("search", "Finds lessons.", {"first": "text"}, True),
        ("review", "Lessons answered wrong and not yet put right.", {}, True),
        ("account", "The PyCmd account: signed in or not, last sync.", {}, True),
        ("sync", "Syncs Learn progress with the account now.", {}, False),
        ("cloud_files", "Lists the account's cloud files and space used (800 KB each).", {},
         True),
        ("cloud_get", "Reads a cloud file.", {"first": "file name"}, True),
        ("cloud_delete", "Deletes a cloud file.", {"first": "file name"}, False),
        ("cloud_upload", "Copies a workspace file into cloud storage.",
         {"first": "absolute path (system_info gives the workspace)", "second": "name"}, False),
        ("cloud_download", "Copies a cloud file into the workspace.",
         {"first": "cloud file name", "second": "absolute target path"}, False),
    ):
        tool = "learn_" + name if name in ("catalogue", "course", "lesson", "check", "complete",
                                         "search", "review") else name
        r.add(tool, text, (lambda n: lambda first="", second="", third="":
                           _teach(n, first, second, third))(name), params, read_only=ro)
    for action, text, params, ro in (
        ("tabs", "Every tab of the app and which one is open.", {}, True),
        ("state", "What is on screen: the tab, the open file, the console's last lines.", {},
         True),
        ("navigate", "Opens a tab: console, editor, files, servers, packages, downloads, "
         "plugins, guides, pages, music, teach, appearance, system, mcp, more.",
         {"tab": "tab name"}, False),
        ("screenshot", "A PNG of the phone's screen as the app shows it now.", {}, True),
        ("toast", "Shows a short message on the phone.", {"text": "message"}, False),
        ("open_file", "Opens a workspace file in the Editor tab.", {"path": path}, False),
        ("back", "Goes back, like the back gesture.", {}, False),
    ):
        r.add("ui_" + action, text, (lambda a: lambda **kw: _bridge(a, **kw))(action), params,
              read_only=ro)
    r.add("console_run", "Types a line into the Console tab and runs it, as if typed there "
          "(Python, or a command like 'ls' or 'pip install x').",
          lambda line: _bridge("console", line=line), {"line": "the line"}, ["line"])
    r.add("help", "What the tools do and how to start.",
          lambda: {"ok": True, "tools": sorted(r.tools), "tips": r.instructions}, read_only=True)
    return r


# -- what Kotlin calls ---------------------------------------------------------

def start(workspace, token, port=8765, lan=False, read_only=False, version="") -> str:
    stop()
    _state["workspace"] = str(workspace)
    registry = build(str(version))
    registry.read_only = bool(read_only)
    server = pycmd_mcp.Server(registry)
    reply = server.start(str(token), int(port), "0.0.0.0" if lan else "127.0.0.1")
    _state.update(server=server if reply["ok"] else None, registry=registry,
                  error="" if reply["ok"] else reply["error"])
    return json.dumps(reply)


def stop() -> str:
    server = _state["server"]
    if server:
        server.token = ""
        server.stop()
    _state["server"] = None
    return json.dumps({"ok": True})


def status(token="", port=8765, address="127.0.0.1") -> str:
    registry = _state["registry"] or build()
    url = f"http://{address}:{int(port)}/mcp"
    return json.dumps({
        "ok": True, "running": bool(_state["server"] and _state["server"].running),
        "error": _state["error"], "tools": len(registry.tools), "url": url,
        "calls": list(reversed(registry.calls)),
        "setups": pycmd_mcp.client_setups(url, str(token)) if token else []})


def new_token() -> str:
    return pycmd_mcp.new_token()
