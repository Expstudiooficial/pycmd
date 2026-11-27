"""Notes as a board: the built-in Notes tab on the phone and the PC.

Boards live in the workspace, in `.pycmd/boards.json`, so they travel with the
workspace and a backup of it has them. The page (assets/web/board.html) does
all the drawing; this module keeps, exports and imports.

Every entry point is `api(name, payload_json, workspace)` returning JSON text:
the same call from Kotlin on the phone and from the Windows host.
"""

from __future__ import annotations

import base64
import json
import os
import re
import threading
import time

MAX_BOARDS = 60
MAX_BOARD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 4 * 1024 * 1024
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
               ".bmp": "image/bmp"}
_LOCK = threading.Lock()
_SAFE = re.compile(r"[^A-Za-z0-9 _.-]")


def _path(workspace: str) -> str:
    return os.path.join(workspace, ".pycmd", "boards.json")


def _new_id(prefix: str) -> str:
    return f"{prefix}{int(time.time() * 1000):x}{os.urandom(2).hex()}"


def _card(kind, x, y, w, h, text="", color="yellow", **extra):
    return dict(id=_new_id("c"), type=kind, x=x, y=y, w=w, h=h, text=text, color=color, **extra)


def template(kind: str, name: str = "") -> dict:
    """A new board: blank, or laid out for something."""
    cards, links = [], []
    if kind == "kanban":
        for i, (title, color) in enumerate((("To do", "blue"), ("Doing", "yellow"), ("Done", "green"))):
            cards.append(_card("frame", 40 + i * 340, 40, 320, 520, title, color))
        cards.append(_card("note", 70, 110, 260, 110, "A task", "blue"))
    elif kind == "mindmap":
        centre = _card("note", 420, 260, 220, 90, "Main idea", "purple")
        cards.append(centre)
        for i, (dx, dy) in enumerate(((-330, -170), (330, -170), (-330, 190), (330, 190))):
            branch = _card("note", 420 + dx, 260 + dy, 200, 80, f"Idea {i + 1}", "blue")
            cards.append(branch)
            links.append({"id": _new_id("l"), "from": centre["id"], "to": branch["id"], "label": "", "style": "line"})
    elif kind == "week":
        for i, day in enumerate(("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Weekend")):
            cards.append(_card("todo", 40 + (i % 3) * 280, 40 + (i // 3) * 260, 260, 230, day,
                               ("blue", "green", "yellow", "pink", "purple", "orange")[i],
                               items=[{"t": "", "done": False}]))
    elif kind == "proscons":
        cards.append(_card("heading", 40, 30, 600, 60, "Should we…?", "none"))
        cards.append(_card("frame", 40, 110, 300, 360, "Pros", "green"))
        cards.append(_card("frame", 370, 110, 300, 360, "Cons", "pink"))
    elif kind == "project":
        steps = ["Idea", "Plan", "Build", "Test", "Ship"]
        previous = None
        cards.append(_card("heading", 40, 30, 600, 60, name or "Project", "none"))
        for i, step in enumerate(steps):
            node = _card("todo", 40 + i * 260, 130, 230, 170, step, "blue" if i < 4 else "green",
                         items=[{"t": "", "done": False}])
            cards.append(node)
            if previous:
                links.append({"id": _new_id("l"), "from": previous["id"], "to": node["id"], "label": "", "style": "arrow"})
            previous = node
    elif kind == "welcome":
        head = _card("heading", 80, 50, 360, 60, "My board", "none")
        note = _card("note", 80, 150, 250, 160, "Double-click (tap twice) to write.\n**Drag** me anywhere.", "yellow")
        todo = _card("todo", 400, 150, 250, 180, "Try these", "green",
                     items=[{"t": "Add a note", "done": True}, {"t": "Drag a card's dot to another", "done": False},
                            {"t": "Right-click or long-press a card", "done": False}])
        cards += [head, note, todo]
        links.append({"id": _new_id("l"), "from": note["id"], "to": todo["id"], "label": "", "style": "arrow"})
    return {"name": name or {"kanban": "Kanban", "mindmap": "Mind map", "week": "My week",
                             "proscons": "Pros and cons", "project": "Project", "welcome": "My board"}.get(kind, "New board"),
            "cards": cards, "links": links, "view": {"x": 0, "y": 0, "z": 1}, "saved": int(time.time())}


def _legacy_plugin_state():
    """Boards made with the Board plugin (3.6 / 5.7), if they are still on disk."""
    try:
        import pycmd_plugins

        folder = pycmd_plugins.plugin_dir("pycmd.board")
    except Exception:  # noqa: BLE001 - no plugin runtime here
        return None, ""
    path = os.path.join(folder, ".state.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return (data if isinstance(data, dict) and data.get("boards") else None), folder
    except (OSError, ValueError):
        return None, folder


def _read(workspace: str) -> dict:
    try:
        with open(_path(workspace), "r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict) and isinstance(data.get("boards"), dict):
                return data
    except (OSError, ValueError):
        pass
    legacy, _ = _legacy_plugin_state()
    if legacy:
        data = {"boards": legacy["boards"], "current": legacy.get("current", "")}
        _write(workspace, data)
        return data
    # Nothing on disk until something is saved: opening Notes, or asking what
    # boards there are, leaves the workspace exactly as it was.
    # A copy each time (the shared one was being written into), saved=0 so
    # an untouched welcome board never wins a sync against a real board.
    welcome = json.loads(json.dumps(_WELCOME))
    welcome["saved"] = 0
    return {"boards": {"b1": welcome}, "current": "b1"}


_WELCOME = template("welcome")


def _write(workspace: str, data: dict) -> None:
    path = _path(workspace)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".writing"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    os.replace(temporary, path)


def retire_plugin() -> dict:
    """Moves boards out of the old Board plugin and removes it: Notes is built in now."""
    legacy, folder = _legacy_plugin_state()
    if not folder or not os.path.isdir(folder):
        return {"ok": True, "retired": False}
    try:
        import pycmd_plugins

        pycmd_plugins.unload("pycmd.board")
        reply = json.loads(pycmd_plugins.remove("pycmd.board"))
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": str(error)}
    return {"ok": bool(reply.get("ok", True)), "retired": True, "had_boards": bool(legacy)}


def _drop_note(workspace: str, text: str, color: str = "yellow") -> str:
    data = _read(workspace)
    rows = data["boards"]
    board_id = data.get("current") if data.get("current") in rows else next(iter(rows))
    board = rows[board_id]
    cards = board.setdefault("cards", [])
    lowest = max([c.get("y", 0) + c.get("h", 0) for c in cards] or [0])
    cards.append(_card("note", 80, lowest + 40, 260, 140, text[:4000], color))
    board["saved"] = int(time.time())
    _write(workspace, data)
    return board.get("name", "Board")


def _markdown(board: dict) -> str:
    cards = sorted(board.get("cards") or [], key=lambda c: (c.get("y", 0), c.get("x", 0)))
    titles, lines = {}, [f"# {board.get('name') or 'Board'}", ""]
    for card in cards:
        text = str(card.get("text") or "").strip()
        titles[card.get("id")] = (text.splitlines()[0][:40] if text else card.get("type", "card"))
        kind = card.get("type")
        if kind in ("heading", "frame"):
            lines += [f"## {text or kind}", ""]
        elif kind == "todo":
            lines += [f"**{text or 'To do'}**"]
            lines += [f"- [{'x' if i.get('done') else ' '}] {i.get('t', '')}" for i in card.get("items", [])]
            lines.append("")
        elif kind == "code":
            lines += ["```", text, "```", ""]
        elif kind == "image":
            lines += [f"*(image{': ' + text if text else ''})*", ""]
        elif kind == "link":
            lines += [f"[{text or card.get('url')}]({card.get('url', '')})", ""]
        else:
            lines += [text, ""]
    arrows = [f"- {titles.get(l.get('from'), '?')} -> {titles.get(l.get('to'), '?')}"
              + (f" ({l['label']})" if l.get("label") else "") for l in board.get("links") or []]
    if arrows:
        lines += ["## Connections", ""] + arrows + [""]
    return "\n".join(lines)


CLOUD_PATH = "pycmd/boards.json"
CLOUD_LIMIT = 700 * 1024


def _merge(local: dict, remote: dict) -> tuple:
    """Every board, the newer copy of each; a board deleted after it was last
    saved stays deleted. Returns (merged, boards that came from the cloud)."""
    gone = dict(remote.get("deleted") or {})
    for key, when in (local.get("deleted") or {}).items():
        gone[key] = max(when, gone.get(key, 0))
    boards, pulled = {}, []
    for key in set(local.get("boards", {})) | set(remote.get("boards", {})):
        mine, theirs = local.get("boards", {}).get(key), remote.get("boards", {}).get(key)
        pick = mine if theirs is None or (mine is not None and mine.get("saved", 0) >= theirs.get("saved", 0)) else theirs
        if gone.get(key, 0) >= pick.get("saved", 0):
            continue
        if pick is theirs:
            pulled.append(key)
        boards[key] = pick
    if not boards:
        boards = {"b1": template("blank", "My board")}
    current = local.get("current") if local.get("current") in boards else next(iter(boards))
    return {"boards": boards, "current": current, "deleted": gone}, pulled


def _sync(workspace: str, current: str = "") -> dict:
    """Notes on every device: pulls, merges, pushes - through the account's
    800 KB of cloud storage."""
    try:
        from pycmd_teach import cloud
    except ImportError:
        return {"ok": False, "error": "Cloud storage is not in this build."}
    if not cloud._token():
        return {"ok": False, "signed_out": True,
                "error": "Sign in to your PyCmd account (Settings) to keep Notes the same on every device."}
    try:
        remote = {}
        try:
            got = cloud.file_get(CLOUD_PATH)
            if got.get("text"):
                remote = json.loads(got["text"])
        except cloud.CloudError as error:
            if error.status != 404:
                raise
        local = _read(workspace)
        merged, pulled = _merge(local, remote if isinstance(remote, dict) else {})
        payload = json.dumps(merged).encode("utf-8")
        if len(payload) > CLOUD_LIMIT:
            return {"ok": False, "error": f"Your boards are {len(payload) // 1024} KB with their pictures, and "
                                          f"cloud storage holds 800 KB. Remove a few pictures to sync."}
        _write(workspace, merged)
        put = cloud.file_put(CLOUD_PATH, payload)
        if put.get("ok") is False:
            return {"ok": False, "error": put.get("error", "That did not upload.")}
        return {"ok": True, "boards": len(merged["boards"]), "pulled": len(pulled),
                "current_changed": current in pulled, "kb": len(payload) // 1024}
    except cloud.CloudError as error:
        return {"ok": False, "error": str(error)}


def api(name: str, payload: str = "{}", workspace: str = "") -> str:
    try:
        body = json.loads(payload or "{}")
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    workspace = workspace or os.getcwd()
    try:
        with _LOCK:
            return json.dumps(_call(name, body, workspace))
    except Exception as error:  # noqa: BLE001 - the page shows it
        return json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"})


def _call(name: str, body: dict, workspace: str) -> dict:
    if name == "listing":
        data = _read(workspace)
        rows = data["boards"]
        items = [{"id": k, "name": v.get("name", "Board"), "cards": len(v.get("cards", [])),
                  "saved": v.get("saved", 0)} for k, v in rows.items()]
        items.sort(key=lambda r: -r["saved"])
        current = data.get("current") if data.get("current") in rows else items[0]["id"]
        return {"ok": True, "boards": items, "current": current, "max": MAX_BOARDS}
    if name == "load":
        data = _read(workspace)
        rows = data["boards"]
        board_id = str(body.get("id") or data.get("current") or "")
        if board_id not in rows:
            board_id = next(iter(rows))
        if data.get("current") != board_id:
            data["current"] = board_id
            _write(workspace, data)
        return {"ok": True, "id": board_id, "board": rows[board_id]}
    if name == "save":
        board, board_id = body.get("board"), str(body.get("id") or "")
        if not isinstance(board, dict) or not board_id:
            return {"ok": False, "error": "nothing to save"}
        size = len(json.dumps(board))
        if size > MAX_BOARD_BYTES:
            return {"ok": False, "error": f"This board is {size // 1024} KB; the limit is "
                                          f"{MAX_BOARD_BYTES // 1048576} MB. Remove an image or two."}
        data = _read(workspace)
        board["saved"] = int(time.time())
        board["name"] = str(board.get("name") or "Board")[:60]
        data["boards"][board_id] = board
        data["current"] = board_id
        _write(workspace, data)
        return {"ok": True, "saved": board["saved"], "bytes": size}
    if name == "create":
        data = _read(workspace)
        if len(data["boards"]) >= MAX_BOARDS:
            return {"ok": False, "error": f"{MAX_BOARDS} boards is the limit. Delete one first."}
        board_id = _new_id("b")
        board = template(str(body.get("template") or "blank"), str(body.get("name") or "")[:60])
        data["boards"][board_id] = board
        data["current"] = board_id
        _write(workspace, data)
        return {"ok": True, "id": board_id, "board": board}
    if name == "remove":
        data = _read(workspace)
        gone = str(body.get("id") or "")
        data["boards"].pop(gone, None)
        data.setdefault("deleted", {})[gone] = int(time.time()) + 1
        if not data["boards"]:
            data["boards"] = {"b1": template("blank", "My board")}
        data["current"] = next(iter(data["boards"]))
        _write(workspace, data)
        return {"ok": True}
    if name == "images":
        found = []
        for folder, dirs, names in os.walk(workspace):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__")]
            for item in names:
                if os.path.splitext(item)[1].lower() in IMAGE_TYPES:
                    found.append(os.path.relpath(os.path.join(folder, item), workspace).replace(os.sep, "/"))
            if len(found) > 400:
                break
        return {"ok": True, "files": sorted(found)[:400]}
    if name == "image":
        path = str(body.get("path") or "")
        extension = os.path.splitext(path)[1].lower()
        if extension not in IMAGE_TYPES:
            return {"ok": False, "error": "That is not an image."}
        full = path if os.path.isabs(path) else os.path.join(workspace, *path.split("/"))
        if os.path.getsize(full) > MAX_IMAGE_BYTES:
            return {"ok": False, "error": "That image is bigger than 4 MB."}
        with open(full, "rb") as handle:
            raw = handle.read()
        return {"ok": True, "src": f"data:{IMAGE_TYPES[extension]};base64," + base64.b64encode(raw).decode("ascii")}
    if name in ("export_markdown", "export_png"):
        board = body.get("board") or {}
        if not board.get("cards") and name == "export_markdown":
            return {"ok": False, "error": "That board is empty."}
        stem = _SAFE.sub("", str(board.get("name") or "board")).strip() or "board"
        relative = f"boards/{stem}.{'md' if name == 'export_markdown' else 'png'}"
        full = os.path.join(workspace, *relative.split("/"))
        if name == "export_png" and not str(body.get("png") or "").startswith("data:image/png;base64,"):
            return {"ok": False, "error": "no picture to save"}
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if name == "export_markdown":
            with open(full, "w", encoding="utf-8") as handle:
                handle.write(_markdown(board))
        else:
            data_url = str(body.get("png") or "")
            if not data_url.startswith("data:image/png;base64,"):
                return {"ok": False, "error": "no picture to save"}
            with open(full, "wb") as handle:
                handle.write(base64.b64decode(data_url.split(",", 1)[1]))
        return {"ok": True, "path": relative, "full": full}
    if name == "note":
        text = str(body.get("text") or "").strip()
        if not text:
            return {"ok": False, "error": "note <text> drops a note on your board"}
        return {"ok": True, "board": _drop_note(workspace, text, str(body.get("color") or "yellow"))}
    if name == "import_text":
        text = str(body.get("text") or "").strip()
        return {"ok": True, "added": _drop_note(workspace, text, "blue") if text else False}
    if name == "sync":
        return _sync(workspace, str(body.get("id") or ""))
    if name == "retire":
        legacy, _ = _legacy_plugin_state()
        if legacy and not os.path.exists(_path(workspace)):
            _read(workspace)      # moves the plugin's boards over first
        return retire_plugin()
    return {"ok": False, "error": f"no board call {name!r}"}
