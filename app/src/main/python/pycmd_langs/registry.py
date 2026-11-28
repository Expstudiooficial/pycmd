"""What each file type is, and what happens when you press Run.

Three honest categories:

* ``run``     - executes on the device and prints to the console.
* ``preview`` - rendered in a WebView (HTML, CSS, Markdown).
* ``edit``    - first-class editing, highlighting and serving, but no execution,
                because running it would need a toolchain Android will not let
                an app ship. Saying so is better than a button that fails.

The last group is not a cop-out: Android has forbidden an app from making
memory executable or loading a library it wrote itself since API 29, so a
compiler for C, Rust or Go could produce correct machine code and never run a
byte of it. That is why those three are *interpreted* here instead - the
interpreters live in ``c_interp``, ``go_interp`` and ``rust_interp`` - and why
JavaScript is handed to the engine the device already has.
"""

from __future__ import annotations

import os

RUN = "run"
PREVIEW = "preview"
EDIT = "edit"
# Something the app can hold, show and serve, but not write from a template:
# an empty .mp3 is not a file anybody wanted. Picking one of these in the
# new-file menu brings a real one in from the phone instead.
MEDIA = "media"


class Language:
    __slots__ = (
        "id", "name", "extensions", "mode", "highlight", "comment", "template",
        "note", "mime",
    )

    def __init__(self, id, name, extensions, mode, highlight, comment="//", template="",
                 note="", mime=""):
        self.id = id
        self.name = name
        self.extensions = extensions
        self.mode = mode
        self.highlight = highlight
        self.comment = comment
        self.template = template
        self.note = note
        # What the system file picker should offer when importing one of
        # these. Only media needs it; everything else is text.
        self.mime = mime

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "extension": self.extensions[0],
            "extensions": ",".join(self.extensions),
            "mode": self.mode,
            "highlight": self.highlight,
            "comment": self.comment,
            "template": self.template,
            "note": self.note,
            "mime": self.mime,
            # Whether the new-file menu can write one from a template. Media
            # cannot: it is imported instead.
            "creatable": self.mode != MEDIA,
        }


NO_TOOLCHAIN = (
    "Editable and servable, but not runnable on the device: building it needs a "
    "compiler, and Android does not let an app execute code it generated itself."
)

LANGUAGES = [
    Language(
        "pycmd", "PyCmd", [".pcmd"], RUN, "pycmd", "#",
        template='# A PyCmd program. Press Run.\nlet name = "world"\nprint("Hello, {name}!")\n\n'
                 'fn square(n: int) -> int {\n    n * n\n}\n\nfor i in 1..=5 {\n'
                 '    print("{i} squared is {square(i)}")\n}\n',
        note="PyCmd is this app's own language: as easy to read as Python, with let/var, "
             "checked types, structs, enums, match, lambdas and 11 libraries (use math, json, "
             "fs, http...). It is checked before it runs and compiled to Python bytecode, so "
             "it runs at Python speed. Learn it in Learn > PyCmd.",
    ),
    Language(
        "python", "Python", [".py", ".pyw"], RUN, "python", "#",
        template='"""New script."""\n\n\ndef main() -> None:\n    print("hello")\n\n\n'
                 'if __name__ == "__main__":\n    main()\n',
    ),
    Language(
        "c", "C", [".c", ".h"], RUN, "c", "//",
        template='#include <stdio.h>\n\nint main(void) {\n    printf("hello\\n");\n'
                 '    return 0;\n}\n',
        note="Runs on a C interpreter built into the app: pointers, structs, malloc, "
             "printf and scanf all work. There is no compiler involved.",
    ),
    Language(
        "javascript", "JavaScript", [".js", ".mjs", ".cjs"], RUN, "javascript", "//",
        template='// New script.\n\nfunction main() {\n  console.log("hello");\n}\n\nmain();\n',
        note="Runs in the device's own JavaScript engine - the same one a browser uses.",
    ),
    Language(
        "html", "HTML", [".html", ".htm"], PREVIEW, "html", "<!--",
        template='<!doctype html>\n<html>\n<head>\n  <meta charset="utf-8">\n'
                 '  <title>Page</title>\n</head>\n<body>\n  <h1>Hello</h1>\n</body>\n</html>\n',
        note="Preview renders it. Serve the folder to open it from another device.",
    ),
    Language(
        "css", "CSS", [".css"], PREVIEW, "css", "/*",
        template="body {\n  margin: 0;\n  font-family: system-ui, sans-serif;\n}\n",
    ),
    Language(
        "markdown", "Markdown", [".md", ".markdown"], PREVIEW, "markdown", "<!--",
        template="# Title\n\nSome text.\n\n- a point\n- another\n",
    ),
    Language(
        "json", "JSON", [".json"], EDIT, "json", "",
        template='{\n  "name": "value"\n}\n',
        note="Validated and formatted by the JSON Tools plugin.",
    ),
    Language("typescript", "TypeScript", [".ts", ".tsx"], EDIT, "javascript", "//",
             template="export function main(): void {\n  console.log('hello');\n}\n",
             note="Editable and highlighted. Running it needs a TypeScript compiler, "
                  "which is not on the device - save it as .js to run it."),
    Language("rust", "Rust", [".rs"], RUN, "rust", "//",
             template='fn main() {\n    println!("hello, world");\n}\n',
             note="Runs on a Rust interpreter built into the app: traits, impl blocks, "
                  "enums with payloads, match, closures, iterator chains, Option, Result "
                  "and the ? operator all work, along with Vec, HashMap, HashSet and the "
                  "String methods. Ownership and borrowing are not checked - there is no "
                  "borrow checker here - so a program rustc accepts will run, and one it "
                  "would reject may also run."),
    Language("go", "Go", [".go"], RUN, "go", "//",
             template='package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("hello")\n}\n',
             note="Runs on a Go interpreter built into the app: goroutines, channels, "
                  "structs, methods, interfaces, defer, panic and recover all work, along "
                  "with fmt, strings, strconv, math, sort, errors, time, os, bufio, unicode "
                  "and sync. Types are parsed but not enforced, so this runs a program the "
                  "real compiler would accept - it will not reject one it would refuse."),
    Language("cpp", "C++", [".cpp", ".cc", ".hpp"], EDIT, "c", "//",
             template='#include <iostream>\n\nint main() {\n    std::cout << "hello\\n";\n'
                      '    return 0;\n}\n',
             note=NO_TOOLCHAIN + " Plain C files (.c) do run - the app interprets them."),
    Language("java", "Java", [".java"], EDIT, "c", "//",
             template='public class Main {\n    public static void main(String[] args) {\n'
                      '        System.out.println("hello");\n    }\n}\n', note=NO_TOOLCHAIN),
    Language("kotlin", "Kotlin", [".kt", ".kts"], EDIT, "c", "//",
             template='fun main() {\n    println("hello")\n}\n', note=NO_TOOLCHAIN),
    Language("shell", "Shell", [".sh", ".bash"], RUN, "shell", "#",
             template='#!/bin/sh\necho "hello"\n',
             note="Runs through the device shell. Android sandboxes what an app may do, "
                  "so system commands are limited."),
    Language("sql", "SQL", [".sql"], EDIT, "sql", "--",
             template="CREATE TABLE items (\n  id INTEGER PRIMARY KEY,\n  name TEXT\n);\n"),
    Language("yaml", "YAML", [".yaml", ".yml"], EDIT, "yaml", "#",
             template="name: value\nitems:\n  - one\n  - two\n"),
    Language("toml", "TOML", [".toml"], EDIT, "toml", "#",
             template='[section]\nkey = "value"\n'),
    Language("xml", "XML", [".xml", ".svg"], EDIT, "html", "<!--",
             template='<?xml version="1.0" encoding="utf-8"?>\n<root>\n</root>\n'),
    Language("ini", "INI / config", [".ini", ".cfg", ".conf", ".properties"], EDIT, "ini", "#",
             template="[section]\nkey = value\n"),
    Language("text", "Plain text", [".txt", ".log"], EDIT, "text", "", template=""),
    Language("csv", "CSV", [".csv", ".tsv"], EDIT, "text", "",
             template="name,value\nfirst,1\n"),
    Language("gitignore", "Git ignore", [".gitignore"], EDIT, "ini", "#",
             template="__pycache__/\n*.pyc\nbuild/\n.env\n"),
    Language("dockerfile", "Dockerfile", [".dockerfile"], EDIT, "shell", "#",
             template="FROM python:3.13-slim\nWORKDIR /app\nCOPY . .\nCMD [\"python\", \"main.py\"]\n",
             note=NO_TOOLCHAIN),
    Language("makefile", "Makefile", [".mk", ".make"], EDIT, "shell", "#",
             template="all:\n\techo building\n", note=NO_TOOLCHAIN),
    Language("ruby", "Ruby", [".rb"], EDIT, "python", "#",
             template='puts "hello"\n', note=NO_TOOLCHAIN),
    Language("php", "PHP", [".php"], EDIT, "c", "//",
             template='<?php\necho "hello\\n";\n', note=NO_TOOLCHAIN),
    Language("swift", "Swift", [".swift"], EDIT, "c", "//",
             template='print("hello")\n', note=NO_TOOLCHAIN),
    Language("lua", "Lua", [".lua"], EDIT, "python", "--",
             template='print("hello")\n', note=NO_TOOLCHAIN),

    # ---- media and the other things a workspace ends up holding -----------
    #
    # None of these is code, and none can be written from a template, but a
    # workspace that cannot hold the .mp3 your script is about is a workspace
    # with a hole in it. They are recognised, playable, servable and exportable
    # like everything else.
    Language("audio", "Audio", [".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".opus"],
             MEDIA, "text", "", mime="audio/*",
             note="Plays in the preview, and is served with byte ranges so it can seek."),
    Language("video", "Video", [".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi"],
             MEDIA, "text", "", mime="video/*",
             note="Plays in the preview. What decodes depends on the device: mp4 and "
                  "webm play everywhere, mkv and avi often do not."),
    Language("image", "Image", [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico"],
             MEDIA, "text", "", mime="image/*",
             note="Shown in the preview at its real size."),
    Language("pdf", "PDF", [".pdf"], MEDIA, "text", "", mime="application/pdf",
             note="Stored and served, but not rendered: Android's WebView has no PDF "
                  "viewer, so opening one needs an app that does."),
    # Both of these are picked with no filter at all, deliberately. Android's
    # file providers label a zip as anything from application/zip to
    # octet-stream and a font almost always as octet-stream, so a filter that
    # looks correct is the one that shows an empty picker.
    Language("archive", "Archive", [".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"],
             MEDIA, "text", "", mime="*/*",
             note="Kept and served as it is. Workspace exports land here as .zip."),
    Language("font", "Font", [".ttf", ".otf", ".woff", ".woff2"],
             MEDIA, "text", "", mime="*/*",
             note="Served, so a page you are previewing can use it."),
]

# Files people create that have no extension at all.
SPECIAL_FILES = {
    "readme.md": ("markdown", "# Project\n\nWhat it does.\n\n## Running\n\n```\npython main.py\n```\n"),
    "license": ("text", ""),
    "makefile": ("makefile", "all:\n\techo building\n"),
    "dockerfile": ("dockerfile", "FROM python:3.13-slim\nWORKDIR /app\nCOPY . .\n"),
    ".gitignore": ("gitignore", "__pycache__/\n*.pyc\nbuild/\n"),
}

_BY_EXTENSION = {}
for language in LANGUAGES:
    for extension in language.extensions:
        _BY_EXTENSION.setdefault(extension, language)

_BY_ID = {language.id: language for language in LANGUAGES}

MIT_LICENSE = """MIT License

Copyright (c) {year} {holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def for_path(path: str) -> dict:
    """The language for a filename, falling back to plain text."""
    name = os.path.basename(path).lower()
    if name in SPECIAL_FILES:
        language_id, _ = SPECIAL_FILES[name]
        language = _BY_ID.get(language_id)
        if language:
            return language.as_dict()
    _, extension = os.path.splitext(name)
    language = _BY_EXTENSION.get(extension)
    if language is None:
        language = _BY_ID["text"]
    return language.as_dict()


def catalogue(include_all: bool = True) -> list:
    """Every language, for the new-file menu."""
    rows = [language.as_dict() for language in LANGUAGES]
    if not include_all:
        # Without Polyglot Files the app is Python-only, as it started - and
        # the media types are part of what that plugin adds, so they go too.
        rows = [row for row in rows if row["id"] in ("python", "text", "markdown")]
    return rows


def media_types() -> list:
    """The types that are imported rather than written."""
    return [language.as_dict() for language in LANGUAGES if language.mode == MEDIA]


def template_for(name: str) -> str:
    """Starter content for a new file, chosen by its name."""
    lowered = os.path.basename(name).lower()

    if lowered in SPECIAL_FILES:
        _, body = SPECIAL_FILES[lowered]
        if lowered == "license":
            import datetime

            return MIT_LICENSE.format(year=datetime.date.today().year, holder="you")
        if body:
            return body

    language = for_path(name)
    return language.get("template", "")


def can_run(path: str) -> bool:
    return for_path(path)["mode"] == RUN


def run_file(path: str, stdout=None, stdin=None) -> dict:
    """Runs a file with whichever engine its extension calls for.

    JavaScript is deliberately absent: the device already has a complete
    engine in its WebView, so the Kotlin side runs those and this never sees
    them. Writing a second, worse JavaScript engine here would be daft.
    """
    language = for_path(path)

    if language["id"] == "c":
        from . import c_interp
        from .c_lexer import CSyntaxError

        try:
            with open(path, "r", encoding="utf-8") as handle:
                source = handle.read()
        except OSError as exc:
            return {"ok": False, "error": f"cannot open {path}: {exc}"}

        try:
            code = c_interp.run_source(source, stdout=stdout, stdin=stdin, argv=[os.path.basename(path)])
            return {"ok": True, "exit": code, "language": "C"}
        except CSyntaxError as exc:
            return {"ok": False, "error": f"C syntax error, {exc}", "language": "C"}
        except c_interp.CRuntimeError as exc:
            return {"ok": False, "error": f"C error, {exc}", "language": "C"}

    if language["id"] == "pycmd":
        from . import pcmd

        return pcmd.run_file(path, stdout=stdout, stdin=stdin)

    if language["id"] == "go":
        from . import go_interp
        from .clike_lexer import LangSyntaxError

        try:
            with open(path, "r", encoding="utf-8") as handle:
                source = handle.read()
        except OSError as exc:
            return {"ok": False, "error": f"cannot open {path}: {exc}", "language": "Go"}

        try:
            code = go_interp.run_source(
                source, stdout=stdout, stdin=stdin, argv=[os.path.basename(path)]
            )
            return {"ok": True, "exit": code, "language": "Go"}
        except LangSyntaxError as exc:
            return {"ok": False, "error": f"Go syntax error, {exc}", "language": "Go"}
        except go_interp.GoError as exc:
            return {"ok": False, "error": f"Go error, {exc}", "language": "Go"}

    if language["id"] == "rust":
        from . import rust_interp
        from .clike_lexer import LangSyntaxError

        try:
            with open(path, "r", encoding="utf-8") as handle:
                source = handle.read()
        except OSError as exc:
            return {"ok": False, "error": f"cannot open {path}: {exc}", "language": "Rust"}

        try:
            code = rust_interp.run_source(
                source, stdout=stdout, stdin=stdin, argv=[os.path.basename(path)]
            )
            return {"ok": True, "exit": code, "language": "Rust"}
        except LangSyntaxError as exc:
            return {"ok": False, "error": f"Rust syntax error, {exc}", "language": "Rust"}
        except rust_interp.RustError as exc:
            return {"ok": False, "error": f"Rust error, {exc}", "language": "Rust"}

    if language["id"] == "javascript":
        # Only reachable if something calls this directly: the Kotlin side
        # intercepts .js first and hands it to the device's own engine.
        return {
            "ok": False,
            "error": "JavaScript runs in the device's own engine, which Python cannot "
                     "reach from here. Open the file and press Run.",
            "language": "JavaScript",
        }

    if language["id"] == "shell":
        import subprocess

        try:
            completed = subprocess.run(
                ["/system/bin/sh", path],
                capture_output=True, text=True, timeout=60,
            )
        except FileNotFoundError:
            try:
                completed = subprocess.run(
                    ["sh", path], capture_output=True, text=True, timeout=60,
                )
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": f"no shell available: {exc}", "language": "Shell"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "the shell script ran for over 60s", "language": "Shell"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "language": "Shell"}

        target = stdout if stdout is not None else __import__("sys").stdout
        if completed.stdout:
            target.write(completed.stdout)
        if completed.stderr:
            target.write(completed.stderr)
        return {"ok": True, "exit": completed.returncode, "language": "Shell"}

    return {
        "ok": False,
        "error": language.get("note") or f"{language['name']} files cannot be run on the device.",
        "language": language["name"],
    }
