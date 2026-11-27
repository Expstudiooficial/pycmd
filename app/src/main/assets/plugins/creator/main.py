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

import builtins
import importlib.util
import os
import re
import sys
import tempfile
import time
import traceback


def _load_blocks():
    """creator_blocks, from this folder, fresh.

    A plain `import` found the copy already in sys.modules - the one from
    before an update - so a new main.py ran against old blocks until the app
    was restarted, and failed in ways that looked like a broken plugin.
    """
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "creator_blocks.py")
    spec = importlib.util.spec_from_file_location("pycmd_creator_blocks", here)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


blocks = _load_blocks()

# How long Run lets a program go before stopping it, and how much it keeps.
RUN_SECONDS = 10.0
RUN_OUTPUT = 200_000


def run_python(code: str, stdin_lines=(), seconds: float = RUN_SECONDS) -> dict:
    """Runs Python here, on the app's own interpreter, and returns what it said.

    print and input are the program's own, not the app's: output is collected
    rather than sent to sys.stdout (which on the phone is the app's log), and
    input() reads the lines given in the Input box. A trace function stops a
    loop that never ends, which is the commonest first program there is.
    """
    out = []
    size = [0]
    feed = [str(line) for line in (stdin_lines or [])]

    def say(text):
        if size[0] < RUN_OUTPUT:
            out.append(text[:RUN_OUTPUT - size[0]])
        size[0] += len(text)

    def _print(*values, sep=" ", end="\n", file=None, flush=False):
        text = (" " if sep is None else str(sep)).join(str(v) for v in values) + \
            ("\n" if end is None else str(end))
        if file is not None and file not in (sys.stdout, sys.stderr):
            file.write(text)
            return
        say(text)

    def _input(prompt=""):
        say(str(prompt))
        if not feed:
            raise EOFError("the program asked for input - type what it should read "
                           "in the Input box, one line for each input()")
        line = feed.pop(0)
        say(line + "\n")
        return line

    deadline = time.monotonic() + max(0.5, float(seconds))

    def tracer(frame, event, arg):
        if time.monotonic() > deadline:
            raise TimeoutError(f"stopped after {seconds:g} seconds - is there a loop that never ends?")
        return tracer

    scope = {"__name__": "__main__", "__file__": "creator.py",
             "__builtins__": dict(vars(builtins), print=_print, input=_input)}
    started = time.monotonic()
    error, line = "", 0
    previous = sys.gettrace()
    sys.settrace(tracer)
    try:
        exec(compile(code, "creator.py", "exec"), scope)  # noqa: S102 - the user's own program
        ok = True
    except SystemExit as stop:
        ok = stop.code in (None, 0)
        if not ok:
            error = f"exit {stop.code}"
    except SyntaxError as problem:
        ok, line = False, problem.lineno or 0
        error = f"SyntaxError: {problem.msg}"
    except BaseException as problem:  # noqa: BLE001 - it is somebody's program
        ok = False
        error = f"{type(problem).__name__}: {problem}"
        for frame in traceback.extract_tb(problem.__traceback__):
            if frame.filename == "creator.py":
                line = frame.lineno or 0
    finally:
        sys.settrace(previous)
    return {"ok": ok, "output": "".join(out), "error": error, "line": line,
            "truncated": size[0] > RUN_OUTPUT, "millis": int((time.monotonic() - started) * 1000),
            "engine": f"Python {sys.version.split()[0]}"}


def run_builtin(code: str, extension: str) -> dict:
    """C, Go and Rust, on the interpreters the app carries - on both apps."""
    try:
        from pycmd_langs import registry
    except ImportError:
        return {"ok": False, "error": "this build has no built-in interpreters", "output": ""}
    out = []

    class Sink:
        def write(self, text):
            if sum(len(t) for t in out) < RUN_OUTPUT:
                out.append(str(text))

        def flush(self):
            pass

    folder = tempfile.mkdtemp(prefix="creator-")
    path = os.path.join(folder, "main" + extension)
    started = time.monotonic()
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(code)
        result = registry.run_file(path, stdout=Sink())
    except Exception as problem:  # noqa: BLE001
        result = {"ok": False, "error": f"{type(problem).__name__}: {problem}"}
    finally:
        try:
            os.remove(path)
            os.rmdir(folder)
        except OSError:
            pass
    return {"ok": bool(result.get("ok")), "output": "".join(out),
            "error": str(result.get("error", "") or ""), "line": 0,
            "millis": int((time.monotonic() - started) * 1000), "engine": "built-in interpreter"}

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

    @api.export
    def run(payload):
        """Builds the project and runs it, here, without saving anything."""
        payload = payload or {}
        built = blocks.compile_project(payload.get("project") or {})
        if not built.get("ok"):
            return built
        stdin = str(payload.get("input", "") or "").replace("\r\n", "\n")
        lines = stdin.split("\n") if stdin else []
        seconds = float(api.setting("run_seconds", RUN_SECONDS) or RUN_SECONDS)
        language = built["language"]
        if language == "python":
            result = run_python(built["code"], lines, seconds)
        elif language in ("c", "go", "rust"):
            result = run_builtin(built["code"], built["extension"])
        else:
            return {"ok": False, "error": f"{language} runs in the panel, not here"}
        result["code"] = built["code"]
        result["problems"] = built.get("problems", [])
        return result

    @api.export
    def from_code(payload):
        """Reads code - pasted, or a workspace file - back into blocks."""
        payload = payload or {}
        code = payload.get("code")
        language = str(payload.get("language", "") or "")
        path = str(payload.get("path", "") or "")
        if code is None and path:
            code = api.read(path)
            if code is None:
                return {"ok": False, "error": f"could not read {path}"}
            if not language:
                extension = os.path.splitext(path)[1].lower()
                language = next((row["id"] for row in blocks.LANGUAGES
                                 if row["extension"] == extension), "python")
        return blocks.blocks_from_code(language or "python", str(code or ""))

    @api.export
    def workspace_files(payload=None):
        """Files Creator can read back into blocks."""
        wanted = {row["extension"] for row in blocks.LANGUAGES}
        try:
            names = api.files("*")
        except Exception:  # noqa: BLE001
            names = []
        root = api.workspace_path()
        rows = [os.path.relpath(str(name), root).replace(os.sep, "/") for name in names or []
                if os.path.splitext(str(name))[1].lower() in wanted]
        return {"ok": True, "files": sorted(rows)[:300]}

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
