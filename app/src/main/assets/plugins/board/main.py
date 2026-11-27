"""Board: notes, images and to-dos on a canvas, connected with arrows.

Everything lives in the plugin's own store as plain JSON, one entry per board.
Images arrive from the panel already shrunk (it draws them onto a canvas
first), so a board stays a few hundred KB at most.
"""

import base64
import json
import os
import re
import time

MAX_BOARDS = 40
MAX_BOARD_BYTES = 6 * 1024 * 1024
MAX_IMAGE_BYTES = 3 * 1024 * 1024
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml"}


def _new_id(prefix):
    return f"{prefix}{int(time.time() * 1000):x}"


def empty_board(name="My board"):
    welcome = [
        {"id": "c1", "type": "heading", "x": 80, "y": 60, "w": 320, "h": 64, "color": "none",
         "text": "My board"},
        {"id": "c2", "type": "note", "x": 80, "y": 160, "w": 240, "h": 150, "color": "yellow",
         "text": "Double-click (or tap twice) to write.\nDrag me anywhere."},
        {"id": "c3", "type": "todo", "x": 400, "y": 160, "w": 240, "h": 170, "color": "green",
         "text": "Plan", "items": [{"t": "Add a note", "done": True},
                                   {"t": "Connect two cards", "done": False},
                                   {"t": "Drop in an image", "done": False}]},
    ]
    return {"name": name, "cards": welcome,
            "links": [{"id": "l1", "from": "c2", "to": "c3", "label": ""}],
            "view": {"x": 0, "y": 0, "z": 1}, "saved": int(time.time())}


def setup(api):
    def boards():
        data = api.store() or {}
        return data.get("boards") or {}

    def put(rows, current=None):
        data = api.store() or {}
        data["boards"] = rows
        if current:
            data["current"] = current
        api.store(data)

    def first_run():
        rows = boards()
        if not rows:
            rows = {"b1": empty_board()}
            put(rows, "b1")
        return rows

    @api.export
    def listing(payload=None):
        rows = first_run()
        data = api.store() or {}
        items = [{"id": k, "name": v.get("name", "Board"), "cards": len(v.get("cards", [])),
                  "saved": v.get("saved", 0)} for k, v in rows.items()]
        items.sort(key=lambda r: -r["saved"])
        current = data.get("current") if data.get("current") in rows else items[0]["id"]
        return {"ok": True, "boards": items, "current": current, "max": MAX_BOARDS}

    @api.export
    def load(payload):
        rows = first_run()
        board_id = str((payload or {}).get("id") or "")
        if board_id not in rows:
            board_id = next(iter(rows))
        put(rows, board_id)
        return {"ok": True, "id": board_id, "board": rows[board_id]}

    @api.export
    def save(payload):
        payload = payload or {}
        board_id = str(payload.get("id") or "")
        board = payload.get("board")
        if not isinstance(board, dict) or not board_id:
            return {"ok": False, "error": "nothing to save"}
        size = len(json.dumps(board))
        if size > MAX_BOARD_BYTES:
            return {"ok": False, "error": f"This board is {size // 1024} KB - the limit is "
                                          f"{MAX_BOARD_BYTES // 1048576} MB. Remove an image or two."}
        rows = boards()
        board["saved"] = int(time.time())
        board["name"] = str(board.get("name") or "Board")[:60]
        rows[board_id] = board
        put(rows, board_id)
        return {"ok": True, "saved": board["saved"], "bytes": size}

    @api.export
    def create(payload=None):
        rows = boards()
        if len(rows) >= MAX_BOARDS:
            return {"ok": False, "error": f"{MAX_BOARDS} boards is the limit. Delete one first."}
        board_id = _new_id("b")
        board = empty_board(str((payload or {}).get("name") or "New board")[:60])
        board["cards"], board["links"] = [], []
        rows[board_id] = board
        put(rows, board_id)
        return {"ok": True, "id": board_id, "board": board}

    @api.export
    def remove(payload):
        rows = boards()
        rows.pop(str((payload or {}).get("id") or ""), None)
        put(rows)
        return {"ok": True}

    @api.export
    def image(payload):
        """A workspace image as a data URL, for the Image button."""
        path = str((payload or {}).get("path") or "")
        extension = os.path.splitext(path)[1].lower()
        if extension not in IMAGE_TYPES:
            return {"ok": False, "error": "That is not an image PyCmd can show."}
        full = path if os.path.isabs(path) else api.workspace_path(*path.split("/"))
        try:
            if os.path.getsize(full) > MAX_IMAGE_BYTES:
                return {"ok": False, "error": "That image is bigger than 3 MB."}
            with open(full, "rb") as handle:
                raw = handle.read()
        except OSError as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True, "src": f"data:{IMAGE_TYPES[extension]};base64,"
                                   + base64.b64encode(raw).decode("ascii")}

    @api.export
    def images(payload=None):
        root = api.workspace_path()
        found = [os.path.relpath(p, root).replace(os.sep, "/") for p in api.files("*")
                 if os.path.splitext(p)[1].lower() in IMAGE_TYPES]
        return {"ok": True, "files": sorted(found)[:300]}

    @api.export
    def export_markdown(payload):
        """The board as a Markdown file in the workspace: cards, lists and arrows."""
        board = (payload or {}).get("board") or {}
        name = re.sub(r"[^A-Za-z0-9 _.-]", "", str(board.get("name") or "board")).strip() or "board"
        cards = sorted(board.get("cards") or [], key=lambda c: (c.get("y", 0), c.get("x", 0)))
        titles = {}
        lines = [f"# {board.get('name') or name}", ""]
        for card in cards:
            text = str(card.get("text") or "").strip()
            titles[card.get("id")] = text.splitlines()[0][:40] if text else card.get("type", "card")
            kind = card.get("type")
            if kind == "heading":
                lines += [f"## {text}", ""]
            elif kind == "todo":
                lines += [f"**{text}**" if text else "**To do**"]
                lines += [f"- [{'x' if i.get('done') else ' '}] {i.get('t', '')}" for i in card.get("items", [])]
                lines.append("")
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
        relative = f"boards/{name}.md"
        if not api.write(relative, "\n".join(lines)):
            return {"ok": False, "error": "could not write the file"}
        api.refresh("files")
        return {"ok": True, "path": relative}

    @api.export
    def import_text(payload):
        """Drops a note carrying old text (Windows' Notes tab before 5.7) on the current board."""
        text = str((payload or {}).get("text") or "").strip()
        if not text:
            return {"ok": True, "added": False}
        return {"ok": True, "added": _drop(text, "blue")}

    def _drop(text, color="yellow"):
        rows = first_run()
        data = api.store() or {}
        board_id = data.get("current") if data.get("current") in rows else next(iter(rows))
        board = rows[board_id]
        cards = board.setdefault("cards", [])
        lowest = max([c.get("y", 0) + c.get("h", 0) for c in cards] or [0])
        cards.append({"id": _new_id("c"), "type": "note", "x": 80, "y": lowest + 40, "w": 260,
                      "h": 140, "color": color, "text": text[:4000]})
        board["saved"] = int(time.time())
        put(rows, board_id)
        return board.get("name", "Board")

    @api.command("note", help="note <text> - drop a note on your board  ·  note list")
    def note_command(argument):
        argument = str(argument or "").strip()
        if not argument:
            return "note <text> drops a note on your board. note list shows your boards."
        if argument == "list":
            rows = first_run()
            return "\n".join(f"{v.get('name', 'Board')}: {len(v.get('cards', []))} cards"
                             for v in rows.values())
        return f"Pinned to {_drop(argument)}. Open the Board tab to see it."

    api.log("Board ready", "")
