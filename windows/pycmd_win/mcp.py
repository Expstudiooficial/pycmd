"""PyCmd for Windows as an MCP server: every call the app makes, as a tool.

Each of the host's ~160 calls becomes a tool named pycmd_<call> (dots become
underscores), with its parameters read from the handler itself. On top come
ui_* tools that drive the window the way a person would - go to a tab, read
it, click, type, scroll, take a screenshot - and help, which explains it all.
The server is pycmd_mcp (shared with Android); this module is the tools and
the MCP tab's settings.
"""

from __future__ import annotations

import inspect
import itertools
import re
import struct
import threading
import zlib

import pycmd_mcp

from . import store

GROUPS = {
    "account": "your PyCmd account and Learn progress sync",
    "android": "Android Lab - emulators, devices, APKs, logcat",
    "builtin": "the 13 built-in plugins",
    "console": "the Python console",
    "disk": "any file or folder on this PC",
    "file": "files in the PyCmd workspace",
    "git": "git in the workspace",
    "history": "console history",
    "install": "installing toolchains",
    "known": "toolchains PyCmd remembers",
    "learn": "PyCmd Learn: courses, lessons, answers",
    "look": "theme, zoom and font size",
    "manager": "package managers (winget, scoop, choco)",
    "notes": "the notes pad",
    "package": "Python packages (pip)",
    "page": "static web pages PyCmd serves",
    "plugin": "installed plugins",
    "port": "network ports",
    "portable": "portable toolchains",
    "progress": "Learn progress as a .json file",
    "recent": "recently opened files",
    "run": "running a file",
    "search": "searching text in files",
    "server": "servers PyCmd runs",
    "setup": "setting up every language at once",
    "snippet": "saved code snippets",
    "task": "project tasks (npm scripts, make targets...)",
    "template": "new-project templates",
    "toolchain": "compilers and interpreters",
    "whatsnew": "release notes",
    "env": "environment variables for programs PyCmd runs",
    "cloud": "your 800 KB of PyCmd cloud storage (needs a signed-in account)",
}
SKIP = {"drain", "hello", "pick.file", "mcp.ui.result"}
READ_WORDS = {"read", "plan", "log", "info", "inspect", "settings", "guide", "panel", "course",
              "lesson", "search", "review", "devices", "logcat", "screenshot", "check", "state",
              "active", "runnable", "completions", "kept", "username", "job", "diagnose",
              "files", "get"}

_lock = threading.Lock()
_pending: dict = {}
_ids = itertools.count(1)
_state = {"server": None, "registry": None, "host": None}


PARAM_WORDS = {
    "path": "a file or folder path", "to": "destination path", "text": "text",
    "id": "an id, as listed by the matching list tool", "name": "a name",
    "course": "course id, e.g. 'python' (pycmd_learn lists them)",
    "lesson": "lesson id, e.g. '0.0.read' (pycmd_learn_course lists them)",
    "answer": "your answer: the option text, or code for a write lesson",
    "line": "a console line: Python, or a command such as 'ls' or 'pip install x'",
    "code": "source code", "port": "a port number", "query": "what to search for",
    "url": "a URL", "package": "a package name", "on": "true or false",
    "theme": "theme id", "serial": "device serial from pycmd_android_devices",
    "content": "file content", "payload": "the plugin's own JSON arguments",
}
VERBS = {"read": "Reads", "write": "Writes", "remove": "Removes", "delete": "Deletes",
         "rename": "Renames", "create": "Creates", "start": "Starts", "stop": "Stops",
         "install": "Installs", "run": "Runs", "set": "Sets", "check": "Checks",
         "plan": "Plans (no changes) for", "log": "Reads the log of", "open": "Opens",
         "save": "Saves", "add": "Adds to", "clear": "Clears", "reset": "Resets",
         "copy": "Copies", "move": "Moves", "export": "Exports", "import": "Imports",
         "search": "Searches", "info": "Describes", "load": "Loads"}


def _params(fn):
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        return {}
    names = dict.fromkeys(re.findall(r'payload(?:\.get\(|\[)\s*"(\w+)"', source))
    return {name: PARAM_WORDS.get(name, f"the {name}") for name in names}


def _describe(name, doc, what, params):
    if doc:
        text = doc
    elif "." not in name:
        text = f"Shows {what}"
    else:
        last = name.rsplit(".", 1)[1]
        text = f"{VERBS.get(last, last.capitalize())}: {what}"
    text = text.rstrip(".") + "."
    if params:
        text += " Arguments: " + ", ".join(params) + "."
    return text + ("" if _read_only(name) else " Changes things.")


def _read_only(name):
    if "." not in name:
        return name not in {"shell", "zip", "unzip", "diagnostics"}
    return name.rsplit(".", 1)[1] in READ_WORDS


def build(host) -> pycmd_mcp.Registry:
    from . import host as host_module

    registry = pycmd_mcp.Registry("pycmd-windows", host_module.VERSION)
    registry.instructions = (
        "You are connected to PyCmd for Windows, a coding app. pycmd_* tools are the app's "
        "own calls (files, console, toolchains, servers, packages, Learn, plugins, Android "
        "Lab, git...); ui_* tools drive its window like a person: ui_read to see the "
        "screen, ui_click / ui_type / ui_scroll to act, ui_screenshot to look. Start with "
        "help if unsure. Arguments are plain JSON objects.")
    for name, fn in sorted(host_module.HANDLERS.items()):
        if name in SKIP or name.startswith("mcp"):
            continue
        group = name.split(".")[0]
        doc = (inspect.getdoc(fn) or "").split("\n")[0].strip()
        params = _params(fn)
        registry.add("pycmd_" + name.replace(".", "_"),
                     _describe(name, doc, GROUPS.get(group) or GROUPS.get(group.rstrip("s"),
                                                                           group), params),
                     (lambda n: lambda **args: host_module.call(host, n, args))(name),
                     params=params, read_only=_read_only(name), group=group)
    _ui_tools(registry, host)
    registry.add("help", "What every group of tools does, and how to start. Read-only.",
                 lambda: {"ok": True, "groups": GROUPS, "ui": [t for t in registry.tools
                                                              if t.startswith("ui_")],
                          "count": len(registry.tools), "tips": registry.instructions},
                 read_only=True, group="help")
    return registry


# -- the window --------------------------------------------------------------

def _ui(host, action, timeout=15, **args):
    """Asks the window to do something and waits for its answer."""
    ident = next(_ids)
    waiter = threading.Event()
    with _lock:
        _pending[ident] = [waiter, None]
    host.emit("mcp-ui", id=ident, action=action, args=args)
    if not waiter.wait(timeout):
        with _lock:
            _pending.pop(ident, None)
        return {"ok": False, "error": "the PyCmd window did not answer - is it open?"}
    with _lock:
        return _pending.pop(ident)[1]


def ui_result(payload) -> dict:
    with _lock:
        slot = _pending.get(int(payload.get("id", 0)))
        if slot:
            slot[1] = payload.get("result") or {"ok": True}
            slot[0].set()
    return {"ok": True}


def _ui_tools(registry, host):
    def add(name, description, params=None, read_only=False, **fixed):
        action = name[3:]
        registry.add(name, description,
                     lambda **args: _ui(host, action, **{**fixed, **args}),
                     params=params, read_only=read_only, group="ui")

    add("ui_tabs", "Every tab in the window (Console, Editor, Learn, Toolchains... and "
        "plugin tabs) with its id, and which one is open.", read_only=True)
    add("ui_navigate", "Opens a tab, like clicking it in the left rail.",
        {"tab": "a tab id from ui_tabs, e.g. 'learn', 'toolchains', 'panel:pycmd.creator'"})
    add("ui_read", "What is on screen now: the tab, its text, any open dialog, and every "
        "button, field and link numbered for ui_click and ui_type.", read_only=True)
    add("ui_click", "Clicks a button, link, tab, switch or card - by its number from ui_read, "
        "or by its visible text. Returns the screen afterwards.",
        {"index": {"type": "integer", "description": "number from ui_read"},
         "text": "visible text, if no index"})
    add("ui_type", "Types into a field (by number from ui_read, or by its label or "
        "placeholder). submit=true presses Enter after.",
        {"index": {"type": "integer"}, "label": "label or placeholder text",
         "value": "what to type", "submit": {"type": "boolean"}})
    add("ui_scroll", "Scrolls the screen or the open dialog.",
        {"to": "'top', 'bottom', 'up', 'down', or a number of pixels"})
    add("ui_key", "Presses a key in the window (Enter, Escape, Tab, ArrowDown, or with "
        "ctrl, e.g. 'Ctrl+K' opens the command palette).", {"key": "the key"})
    add("ui_close_dialog", "Closes the open dialog, if there is one.")
    add("ui_toast", "Shows a short message at the bottom of the window.", {"text": "message"})
    add("ui_theme", "Changes the theme: classic-green, midnight-blue, halloween, "
        "amber-terminal, slate, paper (light).", {"theme": "theme id"})
    registry.add("ui_screenshot", "A PNG of the PyCmd window as it looks now.",
                 lambda: screenshot(), read_only=True, group="ui")


def screenshot() -> dict:
    """The window's pixels as a PNG, through GDI - nothing to install."""
    import base64
    import ctypes
    from ctypes import wintypes as w

    from .app import TITLE

    if not hasattr(ctypes, "windll"):
        return {"ok": False, "error": "screenshots need the Windows app window"}
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    for lib, names, res in ((user32, ("GetDC",), ctypes.c_void_p),
                            (gdi32, ("CreateCompatibleDC", "CreateCompatibleBitmap",
                                     "SelectObject"), ctypes.c_void_p)):
        for n in names:
            getattr(lib, n).restype = res
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.GetDC.argtypes = [ctypes.c_void_p]
    user32.PrintWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
    hwnd = user32.FindWindowW(None, TITLE)
    if not hwnd:
        return {"ok": False, "error": "the PyCmd window was not found"}
    rect = w.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    width, height = rect.right, rect.bottom
    hdc = user32.GetDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, width, height)
    gdi32.SelectObject(mem, bmp)
    if not user32.PrintWindow(hwnd, mem, 3):  # client area, full content (WebView2)
        gdi32.BitBlt(ctypes.c_void_p(mem), 0, 0, width, height, ctypes.c_void_p(hdc), 0, 0,
                     0x00CC0020)

    class BMI(ctypes.Structure):
        _fields_ = [("size", w.DWORD), ("width", w.LONG), ("height", w.LONG),
                    ("planes", w.WORD), ("bits", w.WORD), ("compression", w.DWORD),
                    ("image", w.DWORD), ("xppm", w.LONG), ("yppm", w.LONG),
                    ("used", w.DWORD), ("important", w.DWORD)]

    info = BMI(ctypes.sizeof(BMI), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(ctypes.c_void_p(mem), ctypes.c_void_p(bmp), 0, height, buffer,
                    ctypes.byref(info), 0)
    gdi32.DeleteObject(ctypes.c_void_p(bmp))
    gdi32.DeleteDC(ctypes.c_void_p(mem))
    user32.ReleaseDC(ctypes.c_void_p(hwnd), ctypes.c_void_p(hdc))
    return {"ok": True, "image": base64.b64encode(png(buffer.raw, width, height)).decode(),
            "width": width, "height": height}


def png(bgra: bytes, width: int, height: int) -> bytes:
    """BGRA pixels to a PNG, with the standard library only."""
    data = bytearray(bgra)
    rgb = bytearray(width * height * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = data[2::4], data[1::4], data[0::4]
    stride = width * 3
    rows = b"".join(b"\x00" + bytes(rgb[y * stride:(y + 1) * stride]) for y in range(height))

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height,
                                                               8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


# -- the MCP tab ---------------------------------------------------------------

def _settings():
    from .features import _settings_get

    return {"on": _settings_get("mcpOn", False), "port": _settings_get("mcpPort", 8765),
            "readOnly": _settings_get("mcpReadOnly", False), "token": _settings_get("mcpToken", "")}


def _put(**values):
    from .features import _settings_put

    for key, value in values.items():
        _settings_put(key, value)


def status(host) -> dict:
    s = _settings()
    if not s["token"]:
        s["token"] = pycmd_mcp.new_token()
        _put(mcpToken=s["token"])
    server, registry = _state["server"], _state["registry"]
    url = f"http://127.0.0.1:{s['port']}/mcp"
    return {"ok": True, **s, "running": bool(server and server.running), "url": url,
            "tools": len(registry.tools) if registry else len(build(host).tools),
            "calls": list(reversed(registry.calls)) if registry else [],
            "setups": pycmd_mcp.client_setups(url, s["token"]), "error": _state.get("error", "")}


def apply(host) -> dict:
    """Starts or stops the server to match the settings."""
    s = _settings()
    token = s["token"] or status(host)["token"]
    server = _state["server"]
    _state["error"] = ""
    if not s["on"]:
        if server:
            server.token = ""  # connections still open are refused from now on
            server.stop()
        return status(host)
    registry = build(host)
    registry.read_only = bool(s["readOnly"])
    if server is None:
        server = pycmd_mcp.Server(registry)
    # One server, its tools swapped in place: a client's kept-alive connection
    # is served by the old handler thread, which must see the new settings.
    server.registry = registry
    _state.update(server=server, registry=registry, host=host)
    if server.running and server.port == int(s["port"]):
        server.token = token
        return status(host)
    started = server.start(token, int(s["port"]))
    if not started["ok"]:
        _state["error"] = started["error"]
    return status(host)


def set_options(host, payload) -> dict:
    changes = {}
    if "on" in payload:
        changes["mcpOn"] = bool(payload["on"])
    if "readOnly" in payload:
        changes["mcpReadOnly"] = bool(payload["readOnly"])
    if "port" in payload:
        changes["mcpPort"] = max(1024, min(65535, int(payload["port"])))
    if payload.get("newToken"):
        changes["mcpToken"] = pycmd_mcp.new_token()
    _put(**changes)
    return apply(host)
