"""Creator - write code by stacking blocks instead of typing it.

The blocks themselves and the thing that turns them into a file are in
`creator_blocks.py`, which knows nothing about the app and can be run on a
laptop. The name is long on purpose: the workspace is on `sys.path`, so a
plugin importing `blocks` would pick up a `blocks.py` somebody happened to
have in their own files.
This module is the part that could only exist inside PyCmd: it keeps the
projects, answers the panel, saves what you built into the workspace, and puts
two commands on the console.

A project is small - a language, a name, and a tree of `{block, values,
children}` - so it lives in the plugin's own JSON store rather than as files
in the workspace. What lands in the workspace is the *output*: a real `.py`,
`.html`, `.css`, `.js` or `.md` file that the editor opens, the Servers tab
runs and the Pages tab serves, with nothing left in it to say it was built out
of blocks. That is the whole point - the blocks are scaffolding, and the file
is the thing.
"""

import re
import time

import creator_blocks as blocks

# A drawer of projects you can still find something in.
MAX_PROJECTS = 60

# What a saved project's name may contain, before it becomes a file name.
SAFE_NAME = re.compile(r"[^A-Za-z0-9 _.-]")


def setup(api):
    # ------------------------------------------------------------- storage

    def _all():
        data = api.store()
        rows = data.get("projects")
        return rows if isinstance(rows, dict) else {}

    def _put(rows):
        # The store is shared with the plugin's settings, so it is read,
        # changed and written rather than replaced.
        data = api.store()
        data["projects"] = rows
        api.store(data)

    def _clean_name(name, fallback="untitled"):
        cleaned = SAFE_NAME.sub("", str(name or "")).strip()
        return cleaned[:48] or fallback

    def _summary(project_id, row):
        return {
            "id": project_id,
            "name": row.get("name", "untitled"),
            "language": row.get("language", "python"),
            "blocks": _count(row.get("blocks")),
            "saved": row.get("saved", 0),
            "file": row.get("file", ""),
        }

    def _count(nodes):
        total = 0
        for node in nodes or []:
            if not isinstance(node, dict):
                continue
            total += 1 + _count(node.get("children"))
        return total

    # ------------------------------------------------------- panel exports

    @api.export
    def languages(payload=None):
        """What a project can be written in, and how many blocks each has."""
        return {
            "ok": True,
            "languages": [
                dict(row, blocks=len(blocks.BLOCKS[row["id"]]))
                for row in blocks.LANGUAGES
            ],
            "total": len(blocks.BY_ID),
        }

    @api.export
    def catalogue(payload):
        """Every block for one language, grouped for the palette."""
        return blocks.catalogue((payload or {}).get("language", "python"))

    @api.export
    def build(payload):
        """Compiles a project without saving anything."""
        return blocks.compile_project((payload or {}).get("project") or {})

    @api.export
    def projects(payload=None):
        """Every project in the drawer, newest first."""
        rows = _all()
        listing = [_summary(key, row) for key, row in rows.items()]
        listing.sort(key=lambda row: row["saved"], reverse=True)
        return {"ok": True, "projects": listing, "max": MAX_PROJECTS}

    @api.export
    def open_project(payload):
        """One project, whole, so the panel can put it back on screen."""
        project_id = str((payload or {}).get("id", ""))
        row = _all().get(project_id)
        if row is None:
            return {"ok": False, "error": "no project with that id"}
        return {"ok": True, "id": project_id, "project": row}

    @api.export
    def save_project(payload):
        """Writes a project into the drawer, making it if it is new."""
        payload = payload or {}
        project = payload.get("project") or {}
        rows = _all()
        project_id = str(payload.get("id") or "")

        if not project_id:
            if len(rows) >= MAX_PROJECTS:
                return {"ok": False,
                        "error": f"That is {MAX_PROJECTS} projects, which is the limit. "
                                 "Delete one to make room."}
            project_id = f"cr{int(time.time() * 1000) % 100000000}{len(rows)}"

        language = str(project.get("language") or "python")
        if language not in blocks.BLOCKS:
            return {"ok": False, "error": f"'{language}' is not one of the languages here."}

        count = _count(project.get("blocks"))
        if count > blocks.MAX_BLOCKS:
            return {"ok": False, "error": f"A project stops at {blocks.MAX_BLOCKS} blocks."}

        rows[project_id] = {
            "name": _clean_name(project.get("name")),
            "language": language,
            "blocks": project.get("blocks") or [],
            "file": str(project.get("file") or ""),
            "saved": int(time.time()),
        }
        _put(rows)
        return {"ok": True, "id": project_id, "project": _summary(project_id, rows[project_id])}

    @api.export
    def delete_project(payload):
        project_id = str((payload or {}).get("id", ""))
        rows = _all()
        row = rows.pop(project_id, None)
        if row is None:
            return {"ok": False, "error": "no project with that id"}
        _put(rows)
        return {"ok": True, "name": row.get("name", "")}

    @api.export
    def save_file(payload):
        """Builds a project and writes the result into the workspace.

        This is the moment the blocks stop mattering. What lands is ordinary
        source in the folder the user picked, and every other tab treats it
        like any other file: the editor opens it, the Servers tab runs it, the
        Pages tab serves the folder it is in.
        """
        payload = payload or {}
        project = payload.get("project") or {}
        built = blocks.compile_project(project)
        if not built.get("ok"):
            return built
        if not built["code"].strip():
            return {"ok": False, "error": "There are no blocks to save yet."}

        name = _clean_name(payload.get("name") or project.get("name"), "untitled")
        # A name with an extension already on it is kept as typed - the panel
        # fills one in, and somebody who changed it meant to. A bare name gets
        # the language's, because a Python file called `hello` is a file the
        # rest of the app has to guess about.
        if "." not in name:
            name = f"{name}{built['extension']}"

        folder = str(payload.get("folder") or "").strip().strip("/")
        # A folder is a folder inside the workspace, and nothing else: `..`
        # in a path from a panel is a way out of it.
        folder = "/".join(
            part for part in folder.split("/")
            if part and part not in (".", "..")
        )
        relative = f"{folder}/{name}" if folder else name

        if not api.write(relative, built["code"]):
            return {"ok": False, "error": f"Could not write {relative}."}

        api.refresh("files")
        if api.setting("open_after_save", True):
            api.open_file(api.workspace_path(*relative.split("/")))
        api.log("saved a build", relative)
        return {
            "ok": True,
            "path": relative,
            "lines": built["lines"],
            "blocks": built["blocks"],
            "problems": built["problems"],
        }

    @api.export
    def starter(payload=None):
        """Something already on screen, so the first thing is not an empty page.

        Also where the panel picks up the two settings it needs: which
        language to start in, and where saved files should land by default.
        """
        language = str((payload or {}).get("language") or "").strip().lower()
        if language not in STARTERS:
            language = str(api.setting("default_language", "python") or "python")
        if language not in STARTERS:
            language = "python"
        return {
            "ok": True,
            "project": STARTERS[language],
            "folder": str(api.setting("save_folder", "") or ""),
        }

    # ------------------------------------------------------------ commands

    @api.command("blocks", help="blocks [list|langs|build <name>|save <name>]")
    def blocks_command(argument):
        args = (argument or "").split()
        action = args[0] if args else "list"

        if action == "langs":
            lines = [f"{len(blocks.BY_ID)} blocks in all:"]
            for row in blocks.LANGUAGES:
                lines.append(f"  {row['name']:<12} {len(blocks.BLOCKS[row['id']]):>4}  "
                             f"{row['extension']}")
            return "\n".join(lines)

        rows = _all()
        if action == "list":
            if not rows:
                return "No projects yet. More -> Creator to build one."
            lines = [f"{len(rows)} project(s):"]
            for key, row in sorted(rows.items(), key=lambda kv: -kv[1].get("saved", 0)):
                lines.append(f"  {row.get('name', 'untitled'):<24} "
                             f"{row.get('language', ''):<11} {_count(row.get('blocks'))} blocks")
            return "\n".join(lines)

        if action in ("build", "save"):
            wanted = " ".join(args[1:]).strip().lower()
            if not wanted:
                return f"blocks {action} <name>"
            found = next(
                (key for key, row in rows.items()
                 if row.get("name", "").lower() == wanted),
                None,
            )
            if found is None:
                return f"No project called {wanted}. Try: blocks list"
            project = dict(rows[found], name=rows[found].get("name"))
            if action == "build":
                built = blocks.compile_project(project)
                return built.get("code") or built.get("error", "nothing to build")
            written = save_file({"project": project, "name": project.get("name")})
            if written.get("ok"):
                return f"Saved {written['path']}"
            return written.get("error", "that did not save")

        return "blocks list | blocks langs | blocks build <name> | blocks save <name>"

    api.log("Creator ready", f"{len(blocks.BY_ID)} blocks")


# ---------------------------------------------------------------------------
# What a new project starts as
# ---------------------------------------------------------------------------

STARTERS = {
    "python": {
        "name": "hello",
        "language": "python",
        "blocks": [
            {"block": "py.comment", "values": {"text": "built with blocks"}},
            {"block": "py.print", "values": {"text": "Hello from PyCmd"}},
            {"block": "py.repeat", "values": {"var": "i", "times": "3"},
             "children": [
                 {"block": "py.print_value", "values": {"value": "i"}},
             ]},
        ],
    },
    "javascript": {
        "name": "hello",
        "language": "javascript",
        "blocks": [
            {"block": "js.comment", "values": {"text": "built with blocks"}},
            {"block": "js.log", "values": {"text": "Hello from PyCmd"}},
            {"block": "js.repeat", "values": {"var": "i", "times": "3"},
             "children": [
                 {"block": "js.log_value", "values": {"value": "i"}},
             ]},
        ],
    },
    "html": {
        "name": "index",
        "language": "html",
        "blocks": [
            {"block": "html.doctype"},
            {"block": "html.page", "values": {"lang": "en"}, "children": [
                {"block": "html.head", "children": [
                    {"block": "html.charset"},
                    {"block": "html.viewport"},
                    {"block": "html.title", "values": {"text": "My page"}},
                    {"block": "html.stylesheet", "values": {"href": "style.css"}},
                ]},
                {"block": "html.body", "children": [
                    {"block": "html.h1", "values": {"text": "Hello"}},
                    {"block": "html.p", "values": {"text": "Built out of blocks, on a phone."}},
                ]},
            ]},
        ],
    },
    "css": {
        "name": "style",
        "language": "css",
        "blocks": [
            {"block": "css.rule", "values": {"selector": "body"}, "children": [
                {"block": "css.background", "values": {"value": "#0B0F14"}},
                {"block": "css.color", "values": {"value": "#DCE3EC"}},
                {"block": "css.font_family", "values": {"value": "system-ui, sans-serif"}},
                {"block": "css.padding", "values": {"value": "32px"}},
            ]},
        ],
    },
    "markdown": {
        "name": "notes",
        "language": "markdown",
        "blocks": [
            {"block": "md.h1", "values": {"text": "Notes"}},
            {"block": "md.blank"},
            {"block": "md.text", "values": {"text": "Written by stacking blocks."}},
        ],
    },
    # The five added in 2.6.0. Each one is a whole program rather than a
    # fragment, because the first thing anybody does with a starter is press
    # Run, and a starter that does not run teaches the wrong lesson about
    # whether any of this works.
    "c": {
        "name": "hello",
        "language": "c",
        "blocks": [
            {"block": "c.include", "values": {"name": "stdio.h"}},
            {"block": "c.blank"},
            {"block": "c.main", "children": [
                {"block": "c.print", "values": {"text": "Hello from PyCmd"}},
                {"block": "c.int", "values": {"name": "total", "value": "0"}},
                {"block": "c.for", "values": {"name": "i", "from": "1", "to": "4"},
                 "children": [
                     {"block": "c.increase", "values": {"name": "total", "amount": "i"}},
                 ]},
                {"block": "c.print_labelled",
                 "values": {"label": "total:", "value": "total"}},
                {"block": "c.return_zero"},
            ]},
        ],
    },
    "go": {
        "name": "hello",
        "language": "go",
        "blocks": [
            {"block": "go.package"},
            {"block": "go.blank"},
            {"block": "go.import", "values": {"name": "fmt"}},
            {"block": "go.blank"},
            {"block": "go.main", "children": [
                {"block": "go.print", "values": {"text": "Hello from PyCmd"}},
                {"block": "go.short_number", "values": {"name": "total", "value": "0"}},
                {"block": "go.for", "values": {"name": "i", "from": "1", "to": "4"},
                 "children": [
                     {"block": "go.increase", "values": {"name": "total", "amount": "i"}},
                 ]},
                {"block": "go.print_labelled",
                 "values": {"label": "total:", "value": "total"}},
            ]},
        ],
    },
    "rust": {
        "name": "hello",
        "language": "rust",
        "blocks": [
            {"block": "rs.main", "children": [
                {"block": "rs.print", "values": {"text": "Hello from PyCmd"}},
                {"block": "rs.let_mut", "values": {"name": "total", "value": "0"}},
                {"block": "rs.for_range_inclusive",
                 "values": {"name": "i", "from": "1", "to": "3"},
                 "children": [
                     {"block": "rs.increase", "values": {"name": "total", "amount": "i"}},
                 ]},
                {"block": "rs.print_labelled",
                 "values": {"label": "total:", "value": "total"}},
            ]},
        ],
    },
    "shell": {
        "name": "hello",
        "language": "shell",
        "blocks": [
            {"block": "sh.shebang"},
            {"block": "sh.blank"},
            {"block": "sh.set", "values": {"name": "who", "value": "PyCmd"}},
            {"block": "sh.echo_labelled", "values": {"label": "Hello from", "name": "who"}},
            {"block": "sh.set_number", "values": {"name": "count", "value": "0"}},
            {"block": "sh.for_list", "values": {"name": "item", "items": "one two three"},
             "children": [
                 {"block": "sh.increase", "values": {"name": "count", "amount": "1"}},
             ]},
            {"block": "sh.echo_labelled", "values": {"label": "counted", "name": "count"}},
        ],
    },
    "json": {
        "name": "settings",
        "language": "json",
        "blocks": [
            {"block": "json.object", "children": [
                {"block": "json.text", "values": {"name": "name", "value": "My settings"}},
                {"block": "json.number", "values": {"name": "version", "value": "1"}},
                {"block": "json.bool", "values": {"name": "enabled", "value": "true"}},
                {"block": "json.named_array", "values": {"name": "tags"}, "children": [
                    {"block": "json.item_text", "values": {"value": "one"}},
                    {"block": "json.item_text", "values": {"value": "two"}},
                ]},
            ]},
        ],
    },
}
