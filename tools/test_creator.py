#!/usr/bin/env python3
"""Checks the Creator plugin: the catalogue, the compiler, and saving a file.

Two halves, and they are checked differently.

The catalogue and the compiler are `creator_blocks.py`, which knows nothing about the
app: it is imported directly here and driven with projects, and the source it
writes is compared against what a person would have typed. Python's own
compiler is then handed the result, which is the only check that really
matters for the Python blocks - a block editor whose output does not parse is
worse than no block editor.

The rest - the projects drawer, saving into the workspace, the console command
- is the plugin, so it is installed and loaded for real through the same
machinery the app uses, and its exports are called the way the panel calls
them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREATOR = os.path.join(ROOT, "app", "src", "main", "assets", "plugins", "creator")
sys.path.insert(0, os.path.join(ROOT, "app", "src", "main", "python"))
sys.path.insert(0, CREATOR)

import creator_blocks as blocks  # noqa: E402
import pycmd_plugins as plugins  # noqa: E402
import pycmd_runtime  # noqa: E402

FAILURES = []
REAL = sys.__stdout__


def say(text=""):
    REAL.write(str(text) + "\n")
    REAL.flush()


def check(name, condition, detail=""):
    if condition:
        say(f"  PASS  {name}")
    else:
        FAILURES.append(name)
        say(f"  FAIL  {name}  {detail}")


# ---------------------------------------------------------------------------
say("== the catalogue holds together ==")

check("there are enough blocks to be worth having", len(blocks.BY_ID) >= 300,
      len(blocks.BY_ID))
check("every language has some",
      all(len(rows) >= 15 for rows in blocks.BLOCKS.values()),
      {name: len(rows) for name, rows in blocks.BLOCKS.items()})

ids = [row["id"] for rows in blocks.BLOCKS.values() for row in rows]
check("no two blocks share an id", len(ids) == len(set(ids)),
      [i for i in ids if ids.count(i) > 1][:5])

check("every language in the list has blocks",
      all(row["id"] in blocks.BLOCKS for row in blocks.LANGUAGES),
      [row["id"] for row in blocks.LANGUAGES])

bad_slots = []
bad_placeholders = []
unused_slots = []
bad_choices = []
for language, rows in blocks.BLOCKS.items():
    for row in rows:
        names = {slot["name"] for slot in row["slots"]}
        if len(names) != len(row["slots"]):
            bad_slots.append(row["id"])
        wanted = set(blocks.PLACEHOLDER.findall(row["open"] or "")) | \
            set(blocks.PLACEHOLDER.findall(row["close"] or ""))
        if wanted - names:
            bad_placeholders.append((row["id"], sorted(wanted - names)))
        if names - wanted:
            unused_slots.append((row["id"], sorted(names - wanted)))
        for slot in row["slots"]:
            if slot["kind"] == "choice" and slot["default"] not in slot["options"]:
                bad_choices.append((row["id"], slot["name"]))

check("no block declares the same slot twice", not bad_slots, bad_slots[:5])
check("every @hole@ in a template has a slot behind it",
      not bad_placeholders, bad_placeholders[:5])
check("and every slot is used by its template", not unused_slots, unused_slots[:5])
check("every choice's default is one of its options", not bad_choices, bad_choices[:5])

no_close = [row["id"] for rows in blocks.BLOCKS.values() for row in rows
            if row["wrap"] and not row["close"] and not row["empty"]
            and row["id"].split(".")[0] not in ("html", "css", "md", "js")]
check("every Python container can be left empty without breaking",
      not no_close, no_close[:5])

# `runs` is written out in creator_blocks rather than asked of the app, so
# that the module stays importable on a laptop. This is the check that keeps
# the two in step.
from pycmd_langs import registry as _registry  # noqa: E402

_wrong = []
_app_languages = {row["id"]: row for row in _registry.catalogue()}
for _row in blocks.LANGUAGES:
    _found = _app_languages.get(_row["id"])
    if _found is None:
        _wrong.append((_row["id"], "the app has no such language"))
        continue
    if bool(_row["runs"]) != (_found["mode"] == "run"):
        _wrong.append((_row["id"], f"says runs={_row['runs']}, app says {_found['mode']}"))
check("every language's 'runs on the phone' flag matches the app",
      not _wrong, _wrong)
check("and six of the ten do run",
      sum(1 for row in blocks.LANGUAGES if row["runs"]) == 6,
      [row["id"] for row in blocks.LANGUAGES if row["runs"]])

say()
say("== the catalogue is served the way the panel asks for it ==")
everything = blocks.catalogue()
check("it can be asked for all of it", everything["ok"] and everything["count"] == len(ids),
      everything.get("count"))
one = blocks.catalogue("python")
check("or for one language", one["ok"] and len(one["groups"]) == 1, len(one["groups"]))
check("grouped into categories",
      len(one["groups"][0]["categories"]) >= 8, len(one["groups"][0]["categories"]))
check("a language that does not exist is refused",
      not blocks.catalogue("cobol")["ok"], blocks.catalogue("cobol"))

say()
say("== Python comes out as Python ==")
project = {
    "language": "python",
    "blocks": [
        {"block": "py.import", "values": {"module": "random"}},
        {"block": "py.blank"},
        {"block": "py.def", "values": {"name": "roll", "params": "sides"}, "children": [
            {"block": "py.random_int",
             "values": {"name": "value", "low": "1", "high": "sides"}},
            {"block": "py.return", "values": {"value": "value"}},
        ]},
        {"block": "py.blank"},
        {"block": "py.main_guard", "children": [
            {"block": "py.repeat", "values": {"var": "i", "times": "3"}, "children": [
                {"block": "py.print_value", "values": {"value": "roll(6)"}},
            ]},
        ]},
    ],
}
built = blocks.compile_project(project)
check("it builds", built["ok"] and not built["problems"], built.get("problems"))
expected = (
    "import random\n"
    "\n"
    "def roll(sides):\n"
    "    value = random.randint(1, sides)\n"
    "    return value\n"
    "\n"
    'if __name__ == "__main__":\n'
    "    for i in range(3):\n"
    "        print(roll(6))\n"
)
check("and it is exactly the code somebody would have typed",
      built["code"] == expected, repr(built["code"]))
try:
    compile(built["code"], "built.py", "exec")
    parsed = True
except SyntaxError as error:
    parsed = False
    say(f"        {error}")
check("Python itself accepts it", parsed)

say()
say("== an empty container still writes something that runs ==")
empty = blocks.compile_project({
    "language": "python",
    "blocks": [{"block": "py.if", "values": {"condition": "True"}}],
})
check("an if with nothing in it gets a pass", empty["code"] == "if True:\n    pass\n",
      repr(empty["code"]))
try:
    compile(empty["code"], "built.py", "exec")
    empty_parsed = True
except SyntaxError:
    empty_parsed = False
check("and it parses", empty_parsed)

say()
say("== every Python block on its own produces valid syntax ==")
# A handful of blocks are halves of something: `elif` needs an `if` before it,
# `return` needs to be inside a function, `try` needs an `except` after it.
# Each is checked inside the smallest thing that makes it legal.
#   (what goes before, how far to indent the block, what goes after)
AROUND = {
    "py.elif": ("if False:\n    pass\n", 0, ""),
    "py.else": ("if False:\n    pass\n", 0, ""),
    "py.except": ("try:\n    pass\n", 0, ""),
    "py.finally": ("try:\n    pass\n", 0, ""),
    "py.try": ("", 0, "except Exception:\n    pass\n"),
    "py.flask_route": ("", 0, "def view():\n    pass\n"),
    "py.dataclass_marker": ("", 0, "class C:\n    pass\n"),
    "py.return": ("def f():\n", 1, ""),
    "py.return_none": ("def f():\n", 1, ""),
    "py.global": ("def f():\n", 1, ""),
    "py.break": ("while True:\n", 1, ""),
    "py.continue": ("while True:\n", 1, ""),
    "py.init": ("class C:\n", 1, ""),
    "py.method": ("class C:\n", 1, ""),
    "py.method_args": ("class C:\n", 1, ""),
    "py.set_attribute": ("class C:\n    def f(self):\n", 2, ""),
    "py.get_attribute": ("class C:\n    def f(self):\n", 2, ""),
}

broken = []
for row in blocks.BLOCKS["python"]:
    node = {"block": row["id"], "values": {}}
    if row["wrap"]:
        node["children"] = [{"block": "py.pass", "values": {}}]
    code = blocks.compile_project({"language": "python", "blocks": [node]})["code"]
    before, depth, after = AROUND.get(row["id"], ("", 0, ""))
    if depth:
        pad = "    " * depth
        code = "".join((pad + line + "\n") if line.strip() else "\n"
                       for line in code.split("\n")[:-1])
    code = before + code + after
    try:
        compile(code, row["id"], "exec")
    except SyntaxError as error:
        broken.append((row["id"], str(error)))
check(f"all {len(blocks.BLOCKS['python'])} of them", not broken, broken[:6])

say()
say("== every C, Go and Rust block on its own parses ==")
#
# The same idea as the Python check above, against the interpreters the app
# carries. Parsing rather than running is the point: a parser does not care
# whether `total` was declared, so one block can be checked on its own, and a
# block that does not parse is a typo in the catalogue rather than a program
# that happens to be incomplete.
#
from pycmd_langs import c_parser, go_parser, rust_parser  # noqa: E402

# Blocks that go at the top of a file rather than inside main.
TOP_LEVEL = {
    "c": {"c.include", "c.main", "c.function", "c.function_void", "c.prototype",
          "c.struct", "c.blank", "c.comment"},
    "go": {"go.package", "go.import", "go.import_group", "go.main", "go.func",
           "go.func_nothing", "go.struct", "go.method", "go.blank", "go.comment"},
    "rust": {"rs.main", "rs.use", "rs.fn", "rs.fn_nothing", "rs.struct",
             "rs.impl", "rs.enum", "rs.blank", "rs.comment"},
}

# Blocks that are half of something, and what makes each of them legal.
HALVES = {
    "c.else": ("if (1) {\n", ""),
    "c.else_if": ("if (1) {\n", ""),
    "c.case": ("switch (1) {\n", "}\n"),
    "c.case_default": ("switch (1) {\n", "}\n"),
    "go.else": ("if true {\n", ""),
    "go.else_if": ("if true {\n", ""),
    "go.case": ("switch 1 {\n", "}\n"),
    "go.case_default": ("switch 1 {\n", "}\n"),
    "rs.else": ("if true {\n", ""),
    "rs.else_if": ("if true {\n", ""),
    "rs.match_arm": ("match 1 {\n", "}\n"),
    "rs.match_other": ("match 1 {\n", "}\n"),
    "rs.struct_field": ("struct Shape {\n", "}\n"),
    "rs.enum_variant": ("enum Kind {\n", "}\n"),
}

AROUND_FILE = {
    "c": ("#include <stdio.h>\n#include <string.h>\n#include <stdlib.h>\n"
          "#include <math.h>\n#include <ctype.h>\nint main(void) {\n", "\n}\n"),
    "go": ('package main\n\nimport (\n"fmt"\n"strings"\n"strconv"\n"math"\n'
           '"sort"\n"os"\n"time"\n"errors"\n)\n\nfunc main() {\n', "\n}\n"),
    "rust": ("use std::collections::HashMap;\nfn main() {\n", "\n}\n"),
}
PARSERS = {"c": c_parser.parse, "go": go_parser.parse, "rust": rust_parser.parse}
FILLERS = {"c": "c.blank", "go": "go.blank", "rust": "rs.blank"}

for _language in ("c", "go", "rust"):
    _broken = []
    for row in blocks.BLOCKS[_language]:
        node = {"block": row["id"], "values": {}}
        if row["wrap"]:
            node["children"] = [{"block": FILLERS[_language], "values": {}}]
        code = blocks.compile_project({"language": _language, "blocks": [node]})["code"]
        if row["id"] in TOP_LEVEL[_language]:
            source = code if _language != "go" or row["id"] == "go.package" \
                else "package main\n" + code
        else:
            before, after = AROUND_FILE[_language]
            inner_before, inner_after = HALVES.get(row["id"], ("", ""))
            source = before + inner_before + code + inner_after + after
        try:
            PARSERS[_language](source)
        except Exception as error:  # noqa: BLE001
            _broken.append((row["id"], str(error)[:80]))
    check(f"all {len(blocks.BLOCKS[_language])} {_language} blocks",
          not _broken, _broken[:6])

say()
say("== every shell block on its own is shell ==")
_SCRATCH = tempfile.mkdtemp(prefix="creator-shell-")
# `sh -n` reads a script and says whether it is syntactically a script,
# without running a line of it - which is exactly what is wanted for a block
# that deletes a file.
_sh_broken = []
_sh_checker = shutil.which("sh")
if not _sh_checker:
    say("  SKIP  no sh on this machine")
else:
    SH_HALVES = {
        "sh.else": ('if true; then\n:\n', "fi\n"),
        "sh.elif": ('if true; then\n:\n', "fi\n"),
        "sh.case_when": ('case "$x" in\n', "esac\n"),
        "sh.case_other": ('case "$x" in\n', "esac\n"),
        "sh.break": ("while true; do\n", "done\n"),
        "sh.continue": ("while true; do\n", "done\n"),
        "sh.return": ("f() {\n", "}\n"),
    }
    for row in blocks.BLOCKS["shell"]:
        # No filler child on purpose: an empty `then` is a syntax error in
        # sh, so a container is checked the way it is actually left when
        # nothing has been put in it - filled with the `:` it declares.
        node = {"block": row["id"], "values": {}}
        code = blocks.compile_project({"language": "shell", "blocks": [node]})["code"]
        before, after = SH_HALVES.get(row["id"], ("", ""))
        script = os.path.join(_SCRATCH, "one.sh")
        with open(script, "w", encoding="utf-8") as handle:
            handle.write(before + code + after)
        done = subprocess.run([_sh_checker, "-n", script],
                              capture_output=True, text=True, timeout=20)
        if done.returncode != 0:
            _sh_broken.append((row["id"], done.stderr.strip()[:80]))
    check(f"all {len(blocks.BLOCKS['shell'])} of them", not _sh_broken, _sh_broken[:6])
shutil.rmtree(_SCRATCH, ignore_errors=True)

say()
say("== a number slot means a number in JSON, and an expression everywhere else ==")
# Nine of the ten languages have expressions, and `total += i` puts a variable
# in a number slot. JSON has no expressions at all, so a word there is a file
# that does not parse rather than a name that resolves later.
_expression = blocks.compile_project({"language": "python", "blocks": [
    {"block": "py.increase", "values": {"name": "total", "amount": "i"}},
]})
check("a variable in a Python number slot is written as typed",
      _expression["code"].strip() == "total += i", _expression["code"])
_c_expression = blocks.compile_project({"language": "c", "blocks": [
    {"block": "c.increase", "values": {"name": "total", "amount": "count * 2"}},
]})
check("and so is an expression in C",
      "count * 2" in _c_expression["code"], _c_expression["code"])

for _typed, _written in (("abc", "0"), ("10px", "10"), ("+3", "3"),
                         ("5.", "5"), (".5", "0.5"), ("..", "0"),
                         ("3.1.4", "3.1"), ("", "0")):
    _out = blocks.compile_project({"language": "json", "blocks": [
        {"block": "json.object", "children": [
            {"block": "json.number", "values": {"name": "n", "value": _typed}},
        ]},
    ]})
    check(f"JSON writes {_typed!r} as {_written}",
          f'"n": {_written}' in _out["code"], _out["code"])
    check(f"and {_typed!r} leaves valid JSON behind",
          not _out["problems"], _out["problems"])

say()
say("== a JSON project says when it is not JSON yet ==")
# The "written out as is" block is an escape hatch by design. An escape hatch
# that quietly writes a file nothing can read is a trap.
_broken = blocks.compile_project({"language": "json", "blocks": [
    {"block": "json.object", "children": [
        {"block": "json.raw", "values": {"name": "a", "value": "oops"}},
    ]},
]})
check("an escape hatch that broke it is reported",
      any("not valid JSON" in note for note in _broken["problems"]),
      _broken["problems"])
check("and the code is still handed back to be looked at",
      "oops" in _broken["code"], _broken["code"])

_fine = blocks.compile_project({"language": "json", "blocks": [
    {"block": "json.object", "children": [
        {"block": "json.text", "values": {"name": "a", "value": "one"}},
    ]},
]})
check("a JSON project that is fine says nothing", not _fine["problems"], _fine)

say()
say("== every JSON block on its own is JSON ==")
_json_broken = []
for row in blocks.BLOCKS["json"]:
    node = {"block": row["id"], "values": {}}
    if row["wrap"]:
        node["children"] = []
    # A named value needs an object round it; a bare value does not.
    inside_list = row["cat"] == "In a list"
    if row["id"] in ("json.object", "json.array"):
        project = [node]
    elif inside_list:
        project = [{"block": "json.array", "children": [node]}]
    else:
        project = [{"block": "json.object", "children": [node]}]
    code = blocks.compile_project({"language": "json", "blocks": project})["code"]
    try:
        json.loads(code)
    except Exception as error:  # noqa: BLE001
        _json_broken.append((row["id"], str(error)[:60], code))
check(f"all {len(blocks.BLOCKS['json'])} of them", not _json_broken, _json_broken[:4])

say()
say("== the palette is told what each block writes ==")
shelf = blocks.catalogue("python")
rows = [row for group in shelf["groups"][0]["categories"] for row in group["blocks"]]
check("every block carries a filled-in preview",
      all(row.get("preview") is not None for row in rows))
first_row = next(row for row in rows if row["id"] == "py.print")
check("and it is code, not a template",
      first_row["preview"] == 'print("Hello")' and "@" not in first_row["preview"],
      first_row["preview"])
container = next(row for row in rows if row["id"] == "py.if")
check("a container's preview is its opening line",
      container["preview"] == "if score > 10:", container["preview"])
js_container = next(row for row in blocks.catalogue("javascript")["groups"][0]["categories"]
                    for row in [r for r in row["blocks"] if r["id"] == "js.function"])
check("and a language that closes its blocks says what with",
      js_container["closing"] == "}", js_container.get("closing"))

say()
say("== every line says which block wrote it ==")
outlined = blocks.compile_project({
    "language": "python",
    "blocks": [
        {"block": "py.print", "uid": "a", "values": {"text": "one"}},
        {"block": "py.if", "uid": "b", "values": {"condition": "x"}, "children": [
            {"block": "py.print", "uid": "c", "values": {"text": "two"}},
        ]},
    ],
})
outline = outlined["outline"]
check("one entry per line", len(outline) == 3, outline)
check("each carries the block's own name",
      [row["uid"] for row in outline] == ["a", "b", "c"], [row["uid"] for row in outline])
check("with the line it wrote",
      outline[2]["text"] == 'print("two")', outline[2])
check("and how deep it sits", outline[2]["depth"] == 1, outline[2])
check("the paths are right too", outline[2]["path"] == [1, 0], outline[2])

empty_body = blocks.compile_project({
    "language": "python",
    "blocks": [{"block": "py.if", "uid": "b", "values": {"condition": "x"}}],
})
check("a filled-in empty body is marked as one",
      [row["role"] for row in empty_body["outline"]] == ["open", "empty"],
      empty_body["outline"])

say()
say("== the other languages ==")
html = blocks.compile_project({
    "language": "html",
    "blocks": [
        {"block": "html.doctype"},
        {"block": "html.page", "values": {"lang": "en"}, "children": [
            {"block": "html.body", "children": [
                {"block": "html.h1", "values": {"text": "Hello"}},
            ]},
        ]},
    ],
})
check("HTML nests and closes its tags",
      html["code"] == '<!doctype html>\n<html lang="en">\n  <body>\n'
                      "    <h1>Hello</h1>\n  </body>\n</html>\n",
      repr(html["code"]))

css = blocks.compile_project({
    "language": "css",
    "blocks": [
        {"block": "css.media", "values": {"width": "600"}, "children": [
            {"block": "css.class", "values": {"name": "card"}, "children": [
                {"block": "css.padding", "values": {"value": "10px"}},
            ]},
        ]},
    ],
})
check("CSS keeps its at-rule's single @",
      css["code"] == "@media (max-width: 600px) {\n  .card {\n    padding: 10px;\n  }\n}\n",
      repr(css["code"]))

js = blocks.compile_project({
    "language": "javascript",
    "blocks": [
        {"block": "js.function", "values": {"name": "greet", "params": "name"},
         "children": [{"block": "js.log_value", "values": {"value": "name"}}]},
    ],
})
check("JavaScript closes its braces",
      js["code"] == "function greet(name) {\n  console.log(name);\n}\n", repr(js["code"]))

md = blocks.compile_project({
    "language": "markdown",
    "blocks": [
        {"block": "md.h1", "values": {"text": "Notes"}},
        {"block": "md.blank"},
        {"block": "md.bullet", "values": {"text": "one"}},
    ],
})
check("Markdown does not indent anything",
      md["code"] == "# Notes\n\n- one\n", repr(md["code"]))

say()
say("== a block-built program actually runs ==")
#
# The strongest check there is for a block editor: build a program out of
# blocks, hand the file to the engine that would run it on the phone, and
# compare what it printed. Nothing here is a mock - `registry.run_file` is the
# same call the Run button makes.
#
import io  # noqa: E402

from pycmd_langs import registry  # noqa: E402

_WORK = tempfile.mkdtemp(prefix="creator-run-")


def runs(name, language, blocks_, expected):
    built = blocks.compile_project({"language": language, "blocks": blocks_})
    if not built["ok"] or built["problems"]:
        check(name, False, built.get("error") or built["problems"])
        return
    meta = next(row for row in blocks.LANGUAGES if row["id"] == language)
    path = os.path.join(_WORK, f"built{meta['extension']}")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(built["code"])
    out = io.StringIO()
    try:
        answer = registry.run_file(path, stdout=out)
    except Exception as error:  # noqa: BLE001
        check(name, False, f"{type(error).__name__}: {error}\n{built['code']}")
        return
    if not answer.get("ok"):
        check(name, False, f"{answer.get('error')}\n{built['code']}")
        return
    check(name, out.getvalue() == expected,
          f"expected {expected!r}, got {out.getvalue()!r}\n{built['code']}")


runs("C counts, adds up and chooses", "c", [
    {"block": "c.include", "values": {"name": "stdio.h"}},
    {"block": "c.main", "children": [
        {"block": "c.int", "values": {"name": "total", "value": "0"}},
        {"block": "c.for", "values": {"name": "i", "from": "1", "to": "5"},
         "children": [{"block": "c.increase", "values": {"name": "total", "amount": "i"}}]},
        {"block": "c.print_labelled", "values": {"label": "total:", "value": "total"}},
        {"block": "c.if", "values": {"test": "total > 5"},
         "children": [{"block": "c.print", "values": {"text": "big"}}]},
        {"block": "c.else",
         "children": [{"block": "c.print", "values": {"text": "small"}}]},
        {"block": "c.return_zero"},
    ]},
], "total: 10\nbig\n")

runs("C handles text and arrays", "c", [
    {"block": "c.include", "values": {"name": "stdio.h"}},
    {"block": "c.include", "values": {"name": "string.h"}},
    {"block": "c.main", "children": [
        {"block": "c.text", "values": {"name": "name", "size": "32", "value": "Ada"}},
        {"block": "c.int", "values": {"name": "length", "value": "0"}},
        {"block": "c.strlen", "values": {"into": "length", "text": "name"}},
        {"block": "c.print_labelled", "values": {"label": "len", "value": "length"}},
        {"block": "c.array_values", "values": {"name": "scores", "values": "3, 1, 4"}},
        {"block": "c.print_labelled", "values": {"label": "second", "value": "scores[1]"}},
        {"block": "c.return_zero"},
    ]},
], "len 3\nsecond 1\n")

runs("Go counts, adds up and chooses", "go", [
    {"block": "go.package"},
    {"block": "go.blank"},
    {"block": "go.import", "values": {"name": "fmt"}},
    {"block": "go.blank"},
    {"block": "go.main", "children": [
        {"block": "go.short_number", "values": {"name": "total", "value": "0"}},
        {"block": "go.for", "values": {"name": "i", "from": "1", "to": "5"},
         "children": [{"block": "go.increase", "values": {"name": "total", "amount": "i"}}]},
        {"block": "go.print_labelled", "values": {"label": "total:", "value": "total"}},
        {"block": "go.if", "values": {"test": "total > 5"},
         "children": [{"block": "go.print", "values": {"text": "big"}}]},
        {"block": "go.else",
         "children": [{"block": "go.print", "values": {"text": "small"}}]},
    ]},
], "total: 10\nbig\n")

runs("Go walks a slice and a map", "go", [
    {"block": "go.package"},
    {"block": "go.import_group", "children": [
        {"block": "go.import_line", "values": {"name": "fmt"}},
        {"block": "go.import_line", "values": {"name": "strings"}},
    ]},
    {"block": "go.main", "children": [
        {"block": "go.slice", "values": {"name": "names", "type": "string",
                                         "values": '"ada", "grace"'}},
        {"block": "go.range_values", "values": {"value": "who", "name": "names"},
         "children": [
             {"block": "go.print_value", "values": {"value": "strings.ToUpper(who)"}},
         ]},
        {"block": "go.slice_length", "values": {"into": "count", "name": "names"}},
        {"block": "go.print_labelled", "values": {"label": "count:", "value": "count"}},
    ]},
], "ADA\nGRACE\ncount: 2\n")

runs("Rust counts, adds up and chooses", "rust", [
    {"block": "rs.main", "children": [
        {"block": "rs.let_mut", "values": {"name": "total", "value": "0"}},
        {"block": "rs.for_range_inclusive", "values": {"name": "i", "from": "1", "to": "4"},
         "children": [{"block": "rs.increase", "values": {"name": "total", "amount": "i"}}]},
        {"block": "rs.print_labelled", "values": {"label": "total:", "value": "total"}},
        {"block": "rs.if", "values": {"test": "total > 5"},
         "children": [{"block": "rs.print", "values": {"text": "big"}}]},
        {"block": "rs.else",
         "children": [{"block": "rs.print", "values": {"text": "small"}}]},
    ]},
], "total: 10\nbig\n")

runs("Rust builds a list and a map", "rust", [
    {"block": "rs.use", "values": {"path": "collections::HashMap"}},
    {"block": "rs.blank"},
    {"block": "rs.main", "children": [
        {"block": "rs.vec", "values": {"name": "scores", "values": "3, 1, 4"}},
        {"block": "rs.vec_push", "values": {"name": "scores", "value": "1"}},
        {"block": "rs.vec_sum", "values": {"into": "total", "type": "i32", "name": "scores"}},
        {"block": "rs.print_labelled", "values": {"label": "total:", "value": "total"}},
        {"block": "rs.map", "values": {"name": "ages", "key": "&str", "value": "i32"}},
        {"block": "rs.map_insert", "values": {"name": "ages", "key": '"ada"', "value": "36"}},
        {"block": "rs.map_len", "values": {"into": "pairs", "name": "ages"}},
        {"block": "rs.print_labelled", "values": {"label": "pairs:", "value": "pairs"}},
    ]},
], "total: 9\npairs: 1\n")

# Python is deliberately not in `run_file` - the app runs Python on its own
# engine rather than on the interpreters written for the languages that have
# none - so the Python blocks are run here instead, which is the same proof.
_py = blocks.compile_project({"language": "python", "blocks": [
    {"block": "py.set_number", "values": {"name": "total", "number": "0"}},
    {"block": "py.count_from", "values": {"var": "i", "start": "1", "end": "5"},
     "children": [{"block": "py.increase", "values": {"name": "total", "amount": "i"}}]},
    {"block": "py.print_labelled", "values": {"label": "total:", "value": "total"}},
]})
_said = io.StringIO()
_was = sys.stdout
try:
    sys.stdout = _said
    exec(compile(_py["code"], "built.py", "exec"), {})
finally:
    sys.stdout = _was
check("Python counts and adds up", _said.getvalue() == "total: 10\n",
      repr(_said.getvalue()))

_shell = blocks.compile_project({"language": "shell", "blocks": [
    {"block": "sh.set", "values": {"name": "who", "value": "world"}},
    {"block": "sh.echo_labelled", "values": {"label": "hello", "name": "who"}},
    {"block": "sh.set_number", "values": {"name": "count", "value": "0"}},
    {"block": "sh.for_list", "values": {"name": "item", "items": "a b c"}, "children": [
        {"block": "sh.increase", "values": {"name": "count", "amount": "1"}},
    ]},
    {"block": "sh.echo_labelled", "values": {"label": "count", "name": "count"}},
]})
_sh_path = os.path.join(_WORK, "built.sh")
with open(_sh_path, "w", encoding="utf-8") as _handle:
    _handle.write(_shell["code"])
_out = io.StringIO()
_answer = registry.run_file(_sh_path, stdout=_out)
check("Shell sets, loops and counts",
      _answer.get("ok") and _out.getvalue() == "hello world\ncount 3\n",
      f"{_answer}\n{_out.getvalue()!r}\n{_shell['code']}")

_json = blocks.compile_project({"language": "json", "blocks": [
    {"block": "json.object", "children": [
        {"block": "json.text", "values": {"name": "title", "value": 'a "quoted" name'}},
        {"block": "json.named_array", "values": {"name": "tags"}, "children": [
            {"block": "json.item_text", "values": {"value": "one"}},
            {"block": "json.item_text", "values": {"value": "two"}},
        ]},
        {"block": "json.number", "values": {"name": "count", "value": "2"}},
        {"block": "json.bool", "values": {"name": "ready", "value": "true"}},
        {"block": "json.null", "values": {"name": "note"}},
    ]},
]})
try:
    _parsed = json.loads(_json["code"])
except Exception as _error:  # noqa: BLE001
    _parsed = None
    check("JSON parses as JSON", False, f"{_error}\n{_json['code']}")
else:
    check("JSON parses as JSON", True)
check("with the commas in the right places and none too many",
      _parsed == {"title": 'a "quoted" name', "tags": ["one", "two"],
                  "count": 2, "ready": True, "note": None},
      _parsed)

shutil.rmtree(_WORK, ignore_errors=True)

say()
say("== what somebody types into a hole cannot break the line ==")
quoted = blocks.compile_project({
    "language": "python",
    "blocks": [{"block": "py.print", "values": {"text": 'he said "no" \\ then left'}}],
})
check("quotes and backslashes are escaped",
      quoted["code"] == 'print("he said \\"no\\" \\\\ then left")\n', repr(quoted["code"]))
try:
    compile(quoted["code"], "built.py", "exec")
    quoted_parsed = True
except SyntaxError:
    quoted_parsed = False
check("and it still parses", quoted_parsed)

inside = blocks.compile_project({
    "language": "python",
    "blocks": [{"block": "py.print_f", "values": {"text": 'he said "no"'}}],
})
check("text going inside an f-string is escaped but not quoted again",
      inside["code"] == 'print(f"he said \\"no\\"")\n', repr(inside["code"]))
try:
    compile(inside["code"], "built.py", "exec")
    inside_parsed = True
except SyntaxError:
    inside_parsed = False
check("and that parses too", inside_parsed)

attribute = blocks.compile_project({
    "language": "html",
    "blocks": [{"block": "html.link",
                "values": {"href": "go?a=1&b=2", "text": '<script>"'}}],
})
check("HTML entities are written for what lands in a tag",
      attribute["code"] ==
      '<a href="go?a=1&amp;b=2">&lt;script&gt;&quot;</a>\n', repr(attribute["code"]))

rule = blocks.compile_project({
    "language": "css",
    "blocks": [{"block": "css.color", "values": {"value": "red} body {display:none"}}],
})
check("a brace typed into a CSS value cannot close the rule",
      "{" not in rule["code"] and "}" not in rule["code"], repr(rule["code"]))

literal = blocks.compile_project({
    "language": "javascript",
    "blocks": [{"block": "js.template", "values": {"name": "s", "text": "a `b` ${n}"}}],
})
check("a backtick cannot end a template literal, and ${} still works",
      literal["code"] == "const s = `a \\`b\\` ${n}`;\n", repr(literal["code"]))

newlines = blocks.compile_project({
    "language": "python",
    "blocks": [{"block": "py.comment", "values": {"text": "one\ntwo\nthree"}}],
})
check("a value cannot smuggle in extra lines",
      newlines["code"].count("\n") == 1, repr(newlines["code"]))

long_value = blocks.compile_project({
    "language": "python",
    "blocks": [{"block": "py.set", "values": {"name": "x", "value": "9" * 5000}}],
})
check("and it cannot be a whole file long",
      len(long_value["code"]) < blocks.MAX_VALUE + 40, len(long_value["code"]))

say()
say("== a project that is wrong says so, and builds the rest ==")
mixed = blocks.compile_project({
    "language": "python",
    "blocks": [
        {"block": "py.print", "values": {"text": "fine"}},
        {"block": "css.padding", "values": {"value": "10px"}},
        {"block": "nothing.at.all"},
        {"block": "py.print", "values": {"text": "also fine"}},
    ],
})
check("the good blocks are still built", mixed["blocks"] == 2, mixed["blocks"])
check("and both problems are named", len(mixed["problems"]) == 2, mixed["problems"])
check("a language that does not exist is refused",
      not blocks.compile_project({"language": "cobol", "blocks": []})["ok"])
check("an empty project builds to nothing, not to a crash",
      blocks.compile_project({"language": "python", "blocks": []})["code"] == "")

deep = {"block": "py.if", "values": {"condition": "True"}, "children": []}
node = deep
for _ in range(blocks.MAX_DEPTH + 4):
    child = {"block": "py.if", "values": {"condition": "True"}, "children": []}
    node["children"].append(child)
    node = child
nested = blocks.compile_project({"language": "python", "blocks": [deep]})
check("nesting past the limit stops rather than running away",
      any("deeper" in problem for problem in nested["problems"]), nested["problems"][:2])

say()
say("== the plugin itself ==")


class Sink:
    def onOutput(self, stream, text, channel):  # noqa: N802
        pass

    def onReadLine(self, channel):  # noqa: N802
        return None

    def onFinished(self, run_id, status, millis):  # noqa: N802
        pass


class Host:
    def __init__(self):
        self.actions = []

    def onPluginLog(self, level, message, detail):  # noqa: N802
        pass

    def onToast(self, message):  # noqa: N802
        pass

    def onPluginMessage(self, plugin_id, body):  # noqa: N802
        pass

    def onPluginAction(self, plugin_id, action, detail):  # noqa: N802
        self.actions.append((action, detail))
        return True


workspace = tempfile.mkdtemp(prefix="pycmd-creator-ws-")
pycmd_runtime.configure(Sink(), workspace, tempfile.mkdtemp())
host = Host()
plugins.configure(tempfile.mkdtemp(prefix="pycmd-creator-"), workspace, host)

installed = json.loads(plugins.install(CREATOR, "creator", "1"))
check("it installs", installed.get("ok"), installed.get("error"))
loaded = json.loads(plugins.load("pycmd.creator"))
check("and loads", loaded.get("ok"), loaded.get("error"))
check("registering the command it promises",
      "blocks" in loaded.get("commands", []), loaded.get("commands"))

panel = plugins.panel_html("pycmd.creator", "ui.html")
check("its panel renders", "__pycmd_panel" in panel and "<html" in panel.lower(),
      panel[:100])


def call(name, payload=None):
    return json.loads(plugins.call_export("pycmd.creator", name, json.dumps(payload)))


languages = call("languages")
check("the panel can ask what languages there are",
      languages["result"]["total"] == len(blocks.BY_ID), languages)

starter = call("starter", {"language": "python"})
check("and for something to start with",
      starter["result"]["project"]["blocks"], starter)

saved = call("save_project", {"project": {
    "name": "demo", "language": "python",
    "blocks": [{"block": "py.print", "values": {"text": "hi"}}],
}})
check("a project is kept", saved["result"]["ok"], saved)
project_id = saved["result"]["id"]

listed = call("projects")
check("and listed back", len(listed["result"]["projects"]) == 1, listed)
check("with its block count",
      listed["result"]["projects"][0]["blocks"] == 1, listed["result"]["projects"])

reopened = call("open_project", {"id": project_id})
check("and can be opened whole",
      reopened["result"]["project"]["blocks"][0]["block"] == "py.print", reopened)

written = call("save_file", {
    "project": {"name": "demo", "language": "python",
                "blocks": [{"block": "py.print", "values": {"text": "hi"}}]},
    "name": "demo", "folder": "built",
})
check("a build lands in the workspace", written["result"]["ok"], written)
target = os.path.join(workspace, "built", "demo.py")
check("as a real file with the right name", os.path.isfile(target), target)
check("holding the code", open(target, encoding="utf-8").read() == 'print("hi")\n',
      open(target, encoding="utf-8").read())

escaped = call("save_file", {
    "project": {"name": "x", "language": "python",
                "blocks": [{"block": "py.print", "values": {"text": "hi"}}]},
    "name": "escape", "folder": "../../outside",
})
check("a folder cannot climb out of the workspace",
      escaped["result"]["ok"] and
      os.path.isfile(os.path.join(workspace, "outside", "escape.py")),
      escaped)

nothing = call("save_file", {"project": {"name": "empty", "language": "python",
                                         "blocks": []}})
check("an empty project is not saved as an empty file",
      not nothing["result"]["ok"], nothing)

named = call("save_file", {
    "project": {"name": "page", "language": "html",
                "blocks": [{"block": "html.doctype"}]},
    "name": "page",
})
check("a bare name gets the language's extension",
      os.path.isfile(os.path.join(workspace, "page.html")), named)

kept = call("save_file", {
    "project": {"name": "readme", "language": "markdown",
                "blocks": [{"block": "md.h1", "values": {"text": "Hi"}}]},
    "name": "readme.txt",
})
check("and a name that already has one is left as typed",
      os.path.isfile(os.path.join(workspace, "readme.txt")) and
      not os.path.isfile(os.path.join(workspace, "readme.txt.md")), kept)

deleted = call("delete_project", {"id": project_id})
check("a project can be thrown away", deleted["result"]["ok"], deleted)
check("and then it is gone", not call("projects")["result"]["projects"])

say()
say("== the console command ==")
langs = json.loads(plugins.run_command("blocks", "langs"))
check("blocks langs answers", langs.get("handled") and "Python" in langs.get("result", ""),
      langs)
empty_list = json.loads(plugins.run_command("blocks", "list"))
check("blocks list answers when there is nothing",
      "No projects" in empty_list.get("result", ""), empty_list)
call("save_project", {"project": {
    "name": "again", "language": "python",
    "blocks": [{"block": "py.print", "values": {"text": "again"}}],
}})
built_one = json.loads(plugins.run_command("blocks", "build again"))
check("blocks build prints the code",
      'print("again")' in built_one.get("result", ""), built_one)
missing = json.loads(plugins.run_command("blocks", "build nope"))
check("and says so when there is no such project",
      "No project" in missing.get("result", ""), missing)

say()
if FAILURES:
    say(f"{len(FAILURES)} creator checks failed")
    sys.exit(1)
say("all creator checks passed")
