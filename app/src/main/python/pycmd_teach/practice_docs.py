"""Practice for the courses whose snippets are documents, not programs.

A JSON file does not print anything, so these exercises ask a question about
the document instead - which value a key holds, how many rows a CSV has,
whether a TOML file would load at all - and the answer is worked out here,
from the same data the document was written from. tools/test_teach.py loads
every one of them with a real parser (json, tomllib, PyYAML, ElementTree,
csv, configparser), runs the Makefiles with make, asks git about the
.gitignore files and lays the CSS out in a real browser, and fails if any
answer disagrees.

Questions of one kind share their first two words ("Which value", "How
many"), because that is how the wrong answers on offer are chosen: from the
answers to other questions of the same kind.
"""

from __future__ import annotations

import json
import re

WORDS = ["code", "loop", "byte", "data", "list", "node", "tree", "grid", "atom", "stack",
         "queue", "hash", "array", "token", "vector", "binary", "string", "object", "module",
         "kernel", "packet", "cursor", "buffer", "widget", "socket", "pixel", "matrix",
         "signal", "branch", "commit", "server", "client", "folder", "record"]
CITIES = ["Oslo", "Lima", "Kyiv", "Rome", "Doha", "Graz", "Bern", "Riga", "Nice", "Pune"]
PEOPLE = ["Ana", "Ben", "Cleo", "Dev", "Eli", "Fay", "Gus", "Hana", "Ivo", "Jun", "Kai", "Lea"]
TEAMS = ["red", "blue", "green", "gold"]
SECTIONS = ["server", "database", "logging", "cache", "worker", "network", "paths", "ui"]
ITEMS = ["apple", "pear", "plum", "fig", "kiwi", "lime", "date", "melon"]


def _q(word: str) -> str:
    return f"`{word}`"


# ---------------------------------------------------------------- values

def _scalar(r, key: str):
    """A plausible value for a key, as Python data."""
    table = {
        "name": lambda: r.choice(WORDS),
        "owner": lambda: r.choice(PEOPLE),
        "city": lambda: r.choice(CITIES),
        "theme": lambda: r.choice(["dark", "light", "blue", "solar"]),
        "mode": lambda: r.choice(["fast", "safe", "debug", "quiet"]),
        "port": lambda: r.choice([80, 443, 3000, 5432, 8000, 8080, 8443, 9000]),
        "retries": lambda: r.randint(1, 9),
        "timeout": lambda: r.choice([5, 10, 15, 30, 45, 60, 90]),
        "version": lambda: r.randint(2, 12),
        "level": lambda: r.randint(1, 50),
        "score": lambda: r.choice([1.5, 2.25, 3.75, 4.5, 9.5, 12.5]),
        "debug": lambda: r.choice([True, False]),
        "active": lambda: r.choice([True, False]),
        "verbose": lambda: r.choice([True, False]),
    }
    return table[key]()


SCALAR_KEYS = ["name", "owner", "city", "theme", "mode", "port", "retries", "timeout",
               "version", "level", "score", "debug", "active", "verbose"]


def _keys(r, n):
    return r.sample(SCALAR_KEYS, n)


def _json_text(value) -> str:
    return json.dumps(value)


def _yaml_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


# ================================================================== JSON

def _json_value(r):
    keys = _keys(r, r.randint(3, 5))
    obj = {k: _scalar(r, k) for k in keys}
    pick = r.choice(keys)
    return ("Find the value",
            "A value sits after its key and a colon. Strings keep their quotes; numbers, "
            "true, false and null do not have any.",
            json.dumps(obj, indent=2), f"Which value does {_q(pick)} hold?",
            _json_text(obj[pick]))


def _json_count(r):
    keys = _keys(r, r.randint(2, 5))
    obj = {k: _scalar(r, k) for k in keys}
    inner = r.sample([k for k in SCALAR_KEYS if k not in keys], r.randint(1, 3))
    obj[r.choice(["settings", "meta", "limits"])] = {k: _scalar(r, k) for k in inner}
    return ("Counting keys",
            "Only the keys of the outer object count. An object inside it is one value, "
            "however many keys it has itself.",
            json.dumps(obj, indent=2), "How many keys does the outer object have?",
            str(len(obj)))


def _json_index(r):
    xs = r.sample(ITEMS, r.randint(3, 6))
    i = r.randrange(len(xs))
    doc = {"name": r.choice(WORDS), "items": xs}
    return ("Indexing an array",
            "Arrays count from 0: the first element is index 0.",
            json.dumps(doc, indent=2), f"Which element is at index {i} of `items`?",
            _json_text(xs[i]))


def _json_path(r):
    section = r.choice(["server", "database", "client", "build"])
    keys = _keys(r, r.randint(2, 4))
    inner = {k: _scalar(r, k) for k in keys}
    pick = r.choice(keys)
    doc = {"name": r.choice(WORDS), section: inner}
    return ("Nested objects",
            "A path like a.b means: the key b, inside the object held by a.",
            json.dumps(doc, indent=2), f"What does {_q(section + '.' + pick)} hold?",
            _json_text(inner[pick]))


_JSON_TYPES = [("pycmd", "string"), ("8080", "string"), (8080, "number"), (2.5, "number"),
               (True, "boolean"), (False, "boolean"), (None, "null"), ([1, 2], "array"),
               ({"on": True}, "object"), ("true", "string"), ("null", "string"), ([], "array")]


def _json_type(r):
    keys = _keys(r, 2)
    value, kind = r.choice(_JSON_TYPES)
    obj = {keys[0]: _scalar(r, keys[0]), "value": value, keys[1]: _scalar(r, keys[1])}
    return ("Types",
            "Quotes make a string, even around digits or the word true. Square brackets make "
            "an array, braces an object.",
            json.dumps(obj, indent=2), "What type is the value of `value`?", kind)


def _json_length(r):
    xs = [r.randint(1, 99) for _ in range(r.randint(2, 7))]
    doc = {"name": r.choice(WORDS), "scores": xs}
    text = json.dumps(doc, indent=2)
    return ("Array length",
            "An array's length is how many elements it has, separated by commas.",
            text, "How long is the `scores` array?", str(len(xs)))


def _json_valid(r):
    keys = _keys(r, 3)
    obj = {k: _scalar(r, k) for k in keys}
    lines = json.dumps(obj, indent=2).split("\n")
    mistake = r.randrange(6)
    if mistake == 0:
        lines[-2] += ","
        why = "not valid: a trailing comma"
    elif mistake == 1:
        key = keys[0]
        lines[1] = lines[1].replace(f'"{key}"', f"'{key}'")
        why = "not valid: single quotes"
    elif mistake == 2:
        key = keys[1]
        lines[2] = lines[2].replace(f'"{key}"', key)
        why = "not valid: a key without quotes"
    elif mistake == 3:
        lines.insert(1, "  // settings")
        why = "not valid: JSON has no comments"
    else:
        why = "valid"
    return ("Valid or not",
            "JSON is strict: double quotes only, no comment lines, and no comma after the "
            "last item.",
            "\n".join(lines), "Is this valid JSON?", why)


# ================================================================== YAML

def _yaml_value(r):
    keys = _keys(r, r.randint(3, 5))
    obj = {k: _scalar(r, k) for k in keys}
    pick = r.choice(keys)
    text = "\n".join(f"{k}: {_yaml_scalar(v)}" for k, v in obj.items())
    return ("Find the value",
            "Each line is a key, a colon, a space and a value.",
            text, f"Which value does {_q(pick)} hold?", _yaml_scalar(obj[pick]))


def _yaml_path(r):
    section = r.choice(["server", "database", "client", "build"])
    keys = _keys(r, r.randint(2, 4))
    inner = {k: _scalar(r, k) for k in keys}
    pick = r.choice(keys)
    lines = [f"name: {r.choice(WORDS)}", f"{section}:"]
    lines += [f"  {k}: {_yaml_scalar(v)}" for k, v in inner.items()]
    return ("Nesting",
            "Indented lines belong to the key above them. a.b means b inside a.",
            "\n".join(lines), f"Which value does {_q(section + '.' + pick)} hold?",
            _yaml_scalar(inner[pick]))


def _yaml_count(r):
    xs = r.sample(ITEMS, r.randint(2, 6))
    other = r.sample([i for i in ITEMS if i not in xs], 2)
    lines = [f"name: {r.choice(WORDS)}", "fruit:"] + [f"  - {x}" for x in xs]
    lines += ["others:"] + [f"  - {x}" for x in other]
    return ("A list",
            "A dash and a space start one item of a list. The list ends where the "
            "indentation does.",
            "\n".join(lines), "How many items are in `fruit`?", str(len(xs)))


def _yaml_index(r):
    xs = r.sample(["build", "test", "lint", "deploy", "package", "sign", "upload"],
                  r.randint(3, 5))
    i = r.randrange(len(xs))
    lines = ["steps:"] + [f"  - {x}" for x in xs]
    return ("Indexing a list",
            "Lists count from 0, the same as in most languages.",
            "\n".join(lines), f"Which value does `steps[{i}]` hold?", xs[i])


_YAML_TYPES = [("42", "integer"), ("4.5", "float"), ('"42"', "string"), ("'true'", "string"),
               ("true", "boolean"), ("false", "boolean"), ("null", "null"), ("~", "null"),
               ("hello world", "string"), ("[1, 2]", "list"), ("{a: 1}", "mapping"),
               ("3.0", "float"), ('"null"', "string"), ("-7", "integer")]


def _yaml_type(r):
    text, kind = r.choice(_YAML_TYPES)
    keys = _keys(r, 2)
    doc = (f"{keys[0]}: {_yaml_scalar(_scalar(r, keys[0]))}\nvalue: {text}\n"
           f"{keys[1]}: {_yaml_scalar(_scalar(r, keys[1]))}")
    return ("Types",
            "YAML guesses a type from how a value looks. Quotes always make a string.",
            doc, "What type does `value` load as?", kind)


def _yaml_anchor(r):
    retries, timeout = r.randint(1, 5), r.choice([10, 20, 30, 60])
    override = r.choice([None, r.randint(6, 9)])
    lines = ["defaults: &defaults", f"  retries: {retries}", f"  timeout: {timeout}", "job:",
             "  <<: *defaults"]
    if override is not None:
        lines.append(f"  retries: {override}")
    pick = r.choice(["retries", "timeout"])
    value = timeout if pick == "timeout" else (override if override is not None else retries)
    return ("Anchors and merging",
            "&name marks a value, *name repeats it, and <<: merges a marked mapping in. "
            "A key written out after the merge wins.",
            "\n".join(lines), f"Which value does {_q('job.' + pick)} hold?", str(value))


def _yaml_block(r):
    words = r.sample(WORDS, r.randint(2, 4))
    style = r.choice(["|", ">"])
    lines = [f"text: {style}"] + [f"  {w}" for w in words] + [f"next: {r.choice(WORDS)}"]
    count = len(words) if style == "|" else 1
    return ("Block text",
            "After | every line stays a line. After > the lines are folded into one, "
            "joined by spaces.",
            "\n".join(lines), "How many lines does `text` have?", str(count))


# ================================================================== TOML

def _toml_find(r):
    keys = _keys(r, r.randint(3, 5))
    obj = {k: _scalar(r, k) for k in keys}
    pick = r.choice(keys)
    text = "\n".join(f"{k} = {_tv(v)}" for k, v in obj.items())
    return ("Find the value",
            "A key, an equals sign and a value. Strings need quotes in TOML.",
            text, f"Which value does {_q(pick)} hold?", _tv(obj[pick]))


def _tv(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "[" + ", ".join(_tv(v) for v in value) + "]"
    return str(value)


def _toml_table(r):
    tables = r.sample(SECTIONS, 2)
    data = {t: {k: _scalar(r, k) for k in _keys(r, r.randint(1, 3))} for t in tables}
    table = r.choice(tables)
    key = r.choice(list(data[table]))
    lines = []
    for t in tables:
        lines.append(f"[{t}]")
        lines += [f"{k} = {_tv(v)}" for k, v in data[t].items()]
        lines.append("")
    return ("Tables",
            "Every key after [name] belongs to that table, until the next [table] starts.",
            "\n".join(lines).rstrip(), f"Which value does {_q(table + '.' + key)} hold?",
            _tv(data[table][key]))


def _toml_array(r):
    xs = r.sample([80, 443, 3000, 5000, 8000, 8080, 9000, 9090], r.randint(2, 6))
    lines = [f'name = "{r.choice(WORDS)}"', f"ports = [{', '.join(map(str, xs))}]"]
    return ("Arrays", "An array is a list of values in square brackets.",
            "\n".join(lines), "How many items are in `ports`?", str(len(xs)))


def _toml_aot(r):
    n = r.randint(2, 4)
    lines = []
    for name in r.sample(ITEMS, n):
        lines += ["[[fruit]]", f'name = "{name}"', f"count = {r.randint(1, 9)}", ""]
    return ("Arrays of tables",
            "Each [[fruit]] header starts one more table in the fruit array.",
            "\n".join(lines).rstrip(), "How many tables does `fruit` hold?", str(n))


_TOML_TYPES = [('"8080"', "string"), ("8080", "integer"), ("8080.0", "float"),
               ("true", "boolean"), ("[1, 2]", "array"), ("{ a = 1 }", "table"),
               ("2026-05-01", "date"), ("'single'", "string"), ("-3", "integer"),
               ("0.5", "float"), ("[]", "array"), ('"true"', "string")]


def _toml_type(r):
    text, kind = r.choice(_TOML_TYPES)
    keys = _keys(r, 2)
    doc = (f"{keys[0]} = {_tv(_scalar(r, keys[0]))}\nvalue = {text}\n"
           f"{keys[1]} = {_tv(_scalar(r, keys[1]))}")
    return ("Types", "TOML's types are written so that you can always tell them apart.",
            doc, "What type is `value`?", kind)


def _toml_dotted(r):
    section = r.choice(["server", "site", "app"])
    a, b = _keys(r, 2)
    va, vb = _scalar(r, a), _scalar(r, b)
    lines = [f'title = "{r.choice(WORDS)}"', f"{section}.{a} = {_tv(va)}",
             f"{section}.{b} = {_tv(vb)}"]
    pick, value = r.choice([(a, va), (b, vb)])
    return ("Dotted keys", "a.b = 1 is the same as b = 1 inside a table named a.",
            "\n".join(lines), f"Which value does {_q(section + '.' + pick)} hold?", _tv(value))


def _toml_valid(r):
    keys = _keys(r, 3)
    obj = {k: _scalar(r, k) for k in keys}
    lines = [f"{k} = {_tv(v)}" for k, v in obj.items()]
    mistake = r.randrange(5)
    if mistake == 0:
        lines.append(f"{keys[0]} = {_tv(_scalar(r, keys[0]))}")
        why = "not valid: a key defined twice"
    elif mistake == 1:
        lines.append(f"label = {r.choice(WORDS)}")
        why = "not valid: a string without quotes"
    elif mistake == 2:
        lines = ["[server]"] + lines + ["", "[server]", "extra = 1"]
        why = "not valid: a table defined twice"
    else:
        why = "valid"
    return ("Valid or not",
            "A key can only be set once, strings need quotes, and a table header can only "
            "appear once.",
            "\n".join(lines), "Is this valid TOML?", why)


# =================================================================== XML

def _xml_count(r):
    tag = r.choice(["item", "book", "user", "song", "task"])
    other = r.choice(["note", "meta", "tag"])
    n, m = r.randint(2, 5), r.randint(1, 3)
    lines = ["<list>"]
    rows = [f"  <{tag}>{w}</{tag}>" for w in r.sample(WORDS, n)]
    rows += [f"  <{other}>{w}</{other}>" for w in r.sample(WORDS, m)]
    r.shuffle(rows)
    lines += rows + ["</list>"]
    return ("Counting elements",
            "Every start tag with its end tag is one element. Count only the ones asked "
            "about.",
            "\n".join(lines), f"How many `<{tag}>` elements are there?", str(n))


def _xml_attr(r):
    tag = r.choice(["item", "user", "file", "task"])
    ids = r.sample(range(10, 99), r.randint(2, 4))
    which = r.randrange(len(ids))
    lines = ["<items>"] + [f'  <{tag} id="{i}">{r.choice(WORDS)}</{tag}>' for i in ids]
    lines.append("</items>")
    nth = ["first", "second", "third", "fourth"][which]
    return ("Attributes",
            "An attribute is a name=\"value\" pair inside the start tag.",
            "\n".join(lines), f"Which value does the `id` of the {nth} `<{tag}>` have?",
            str(ids[which]))


def _xml_text(r):
    title, author = r.choice(WORDS), r.choice(PEOPLE)
    lines = ["<book>", f"  <title>{title}</title>", f"  <author>{author}</author>",
             f"  <year>{r.randint(1990, 2026)}</year>", "</book>"]
    pick, value = r.choice([("title", title), ("author", author)])
    return ("Text content", "The text of an element is what sits between its two tags.",
            "\n".join(lines), f"What text is inside `<{pick}>`?", value)


def _xml_root(r):
    root = r.choice(["library", "config", "project", "playlist", "inventory"])
    child = r.choice(["entry", "item", "setting"])
    lines = [f"<{root}>", f"  <{child}>", f"    <name>{r.choice(WORDS)}</name>",
             f"  </{child}>", f"</{root}>"]
    if r.random() < 0.5:
        lines.insert(0, '<?xml version="1.0" encoding="utf-8"?>')
    return ("The root", "Exactly one element holds all the others: the root. The <?xml?> "
            "line at the top is a declaration, not an element.",
            "\n".join(lines), "Which element is the root?", f"<{root}>")


def _xml_depth(r):
    depth = r.randint(2, 5)
    names = r.sample(["a", "b", "c", "d", "e", "f"], depth)
    lines = []
    for i, n in enumerate(names):
        lines.append("  " * i + f"<{n}>")
    lines[-1] = lines[-1] + "text" + f"</{names[-1]}>"
    for i in range(depth - 2, -1, -1):
        lines.append("  " * i + f"</{names[i]}>")
    return ("Nesting depth", "The root is depth 1; each element inside another is one "
            "deeper.",
            "\n".join(lines), "How deep is the deepest element?", str(depth))


def _xml_valid(r):
    tag = r.choice(["item", "user", "task"])
    lines = ["<list>", f'  <{tag} id="1">{r.choice(WORDS)}</{tag}>',
             f'  <{tag} id="2">{r.choice(WORDS)}</{tag}>', "</list>"]
    mistake = r.randrange(6)
    if mistake == 0:
        lines[2] = lines[2].replace(f"</{tag}>", f"</{tag}s>")
        why = "not well-formed: a mismatched end tag"
    elif mistake == 1:
        lines[1] = lines[1].replace('id="1"', "id=1")
        why = "not well-formed: an attribute without quotes"
    elif mistake == 2:
        lines.append("<list></list>")
        why = "not well-formed: two root elements"
    elif mistake == 3:
        lines[1] = lines[1].replace(">", "> fish & chips ", 1)
        why = "not well-formed: a bare &"
    else:
        why = "well-formed"
    return ("Well-formed or not",
            "Every tag closes, attribute values are quoted, there is one root, and & is "
            "written &amp;.",
            "\n".join(lines), "Is this well-formed XML?", why)


# =================================================================== CSV

def _csv_rows(r, n, quoted=False):
    rows = []
    for _ in range(n):
        name = r.choice(PEOPLE)
        if quoted and r.random() < 0.5:
            name = f'"{name}, {r.choice(PEOPLE)}"'
        rows.append([name, r.choice(CITIES), str(r.randint(1, 20)), r.choice(TEAMS)])
    return rows


def _csv_text(rows):
    return "\n".join(",".join(row) for row in [["name", "city", "qty", "team"]] + rows)


def _csv_count(r):
    rows = _csv_rows(r, r.randint(2, 6))
    return ("Counting rows",
            "The first line is the header: it names the columns and is not a row of data.",
            _csv_text(rows), "How many data rows are there?", str(len(rows)))


def _csv_cell(r):
    rows = _csv_rows(r, r.randint(3, 5), quoted=r.random() < 0.4)
    i = r.randrange(len(rows))
    col = r.choice(["name", "city", "team"])
    value = rows[i][["name", "city", "qty", "team"].index(col)].strip('"')
    return ("Reading a cell",
            "Count rows after the header, from 1. A value in double quotes can hold a comma.",
            _csv_text(rows), f"Which value is in the `{col}` column of row {i + 1}?", value)


def _csv_total(r):
    rows = _csv_rows(r, r.randint(2, 5))
    return ("Adding a column", "Take the qty column of every data row and add it up.",
            _csv_text(rows), "What is the total of the `qty` column?",
            str(sum(int(row[2]) for row in rows)))


def _csv_columns(r):
    cols = r.sample(["id", "name", "city", "qty", "team", "email", "age", "score"],
                    r.randint(2, 6))
    rows = [",".join(cols)]
    for _ in range(r.randint(1, 3)):
        rows.append(",".join(str(r.randint(1, 99)) for _ in cols))
    return ("Counting columns", "Every comma on the header line starts one more column.",
            "\n".join(rows), "How many columns does it have?", str(len(cols)))


def _csv_quotes(r):
    word = r.choice(WORDS)
    said = r.choice(["hi", "ok", "yes", "go"])
    rows = ["id,text", f'1,"{word}, again"', f'2,"say ""{said}"""', f"3,{r.choice(WORDS)}"]
    pick = r.choice([1, 2])
    value = f"{word}, again" if pick == 1 else f'say "{said}"'
    return ("Quotes", "Inside a quoted value, a comma is just a comma and \"\" is one "
            "quote mark.",
            "\n".join(rows), f"Which value is in the `text` column of row {pick}?", value)


# =================================================================== INI

def _ini_doc(r, n_sections):
    sections = r.sample(SECTIONS, n_sections)
    data = {s: {k: _scalar(r, k) for k in _keys(r, r.randint(1, 3))} for s in sections}
    return data


def _ini_text(data):
    lines = []
    for s, keys in data.items():
        lines.append(f"[{s}]")
        for k, v in keys.items():
            lines.append(f"{k} = {_yaml_scalar(v)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _ini_value(r):
    data = _ini_doc(r, r.randint(2, 3))
    s = r.choice(list(data))
    k = r.choice(list(data[s]))
    return ("Find the value", "A key belongs to the [section] above it.",
            _ini_text(data), f"Which value does `{k}` in `[{s}]` have?",
            _yaml_scalar(data[s][k]))


def _ini_sections(r):
    data = _ini_doc(r, r.randint(1, 4))
    return ("Counting sections", "Every [name] line starts a section.",
            _ini_text(data), "How many sections are there?", str(len(data)))


def _ini_where(r):
    data = _ini_doc(r, 3)
    s = r.choice(list(data))
    unique = [k for k in data[s] if sum(k in keys for keys in data.values()) == 1]
    if not unique:
        return None
    k = r.choice(unique)
    return ("Which section", "Look for the key, then up for the nearest [section].",
            _ini_text(data), f"Which section has the key `{k}`?", f"[{s}]")


def _ini_default(r):
    retries = r.randint(1, 5)
    override = r.choice([None, r.randint(6, 9)])
    lines = ["[DEFAULT]", f"retries = {retries}", "", "[worker]", f"name = {r.choice(WORDS)}"]
    if override is not None:
        lines.append(f"retries = {override}")
    lines += ["", "[backup]", f"name = {r.choice(WORDS)}"]
    s = r.choice(["worker", "backup"])
    value = override if (s == "worker" and override is not None) else retries
    return ("The DEFAULT section",
            "A key in [DEFAULT] is in every section too, unless the section sets its own.",
            "\n".join(lines), f"Which value does `retries` in `[{s}]` have?", str(value))


def _ini_comments(r):
    port = r.choice([80, 8080, 8000, 9000])
    old = r.choice([81, 8081, 8001, 9001])
    mark = r.choice([";", "#"])
    lines = ["[server]", f"{mark} port = {old}", f"port = {port}", f"{mark} the old one is off"]
    return ("Comments", "A line starting with ; or # is a comment: it sets nothing.",
            "\n".join(lines), "Which value does `port` in `[server]` have?", str(port))


# ================================================================= REGEX

def _regex(pattern, text):
    return f"pattern: {pattern}\ntext:    {text}"


def _sentence(r, n=5):
    return " ".join(r.choice(WORDS) for _ in range(n))


def _re_digits(r):
    parts = []
    for _ in range(r.randint(4, 7)):
        parts.append(str(r.randint(1, 999)) if r.random() < 0.4 else r.choice(WORDS))
    text = " ".join(parts)
    pattern = r"\d+"
    count = len(re.findall(pattern, text))
    return ("Counting matches", r"\d means a digit; + means one or more of them in a row.",
            _regex(pattern, text), "How many matches are there?", str(count))


def _re_first(r):
    choices = [(r"[A-Z]\w+", lambda: " ".join(r.choice([w, w.title()]) for w in
                                              r.sample(WORDS, 5))),
               (r"\d{3}", lambda: " ".join(str(r.randint(1, 9999)) for _ in range(4))),
               (r"b\w*", lambda: _sentence(r)),
               (r"<.+?>", lambda: f"<{r.choice('bip')}>{r.choice(WORDS)}</b>"),
               (r"<.+>", lambda: f"<{r.choice('bip')}>{r.choice(WORDS)}</b>")]
    pattern, make = r.choice(choices)
    text = make()
    found = re.search(pattern, text)
    if not found:
        return None
    return ("The first match",
            "The search moves left to right and stops at the first place the pattern fits. "
            "+ and * take as much as they can; +? and *? as little.",
            _regex(pattern, text), "Which is the first match?", found.group(0))


def _re_words(r):
    n = r.randint(3, 6)
    text = _sentence(r, 6)
    pattern = rf"\b\w{{{n}}}\b"
    return ("Exact lengths", r"\b is the edge of a word; \w{4} is exactly four word "
            "characters.",
            _regex(pattern, text), "How many matches are there?",
            str(len(re.findall(pattern, text))))


def _re_group(r):
    user, host = r.choice(PEOPLE).lower(), r.choice(WORDS)
    text = f"mail {user}@{host}.com today"
    pattern = r"(\w+)@(\w+)\.com"
    g = r.choice([1, 2])
    return ("Groups", "Brackets capture: group 1 is the first pair of brackets, group 2 "
            "the second.",
            _regex(pattern, text), f"Which text does group {g} capture?",
            re.search(pattern, text).group(g))


def _re_full(r):
    word = r.choice(WORDS)
    digits = r.choice([2, 3])
    pattern = rf"^[a-z]+\d{{{digits}}}$"
    shape = r.randrange(4)
    if shape == 0:
        text = word + str(r.randint(10, 99))
    elif shape == 1:
        text = word + str(r.randint(100, 999))
    elif shape == 2:
        text = word.title() + str(r.randint(10, 99))
    else:
        text = word + "-" + str(r.randint(10, 99))
    answer = "yes" if re.search(pattern, text) else "no"
    return ("The whole text", "^ and $ pin the pattern to the start and the end: the whole "
            "text has to fit.",
            _regex(pattern, text), "Does the whole text match?", answer)


def _re_alt(r):
    a, b = r.sample(["cat", "dog", "owl", "fox", "bee"], 2)
    pool = [a, b, "cow", "ant", "hen"]
    text = " ".join(r.choice(pool) for _ in range(r.randint(4, 7)))
    pattern = f"{a}|{b}"
    return ("Either one", "| means or: the pattern matches either side.",
            _regex(pattern, text), "How many matches are there?",
            str(len(re.findall(pattern, text))))


def _re_class(r):
    vowels = r.choice(["[aeiou]", "[^aeiou ]", "[a-f]", "[0-9]"])
    word = r.choice(WORDS) + str(r.randint(0, 99))
    return ("Character classes", "[abc] is one character out of the set; [^abc] is one "
            "character that is not in it.",
            _regex(vowels, word), "How many matches are there?",
            str(len(re.findall(vowels, word))))


# ============================================================= GITIGNORE

def _glob_regex(pattern: str) -> str:
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("/**", i) and i + 3 == len(pattern):
            out.append("/.*")
            i += 3
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return "".join(out)


def gitignored(lines, path: str) -> bool:
    """Whether git would ignore `path` (a file) with these .gitignore lines.

    Enough of git's rules for the patterns practice writes: the last pattern
    that matches decides, a pattern with a slash in it is matched from the
    top, one without matches a name at any depth, a trailing slash matches
    only folders, and nothing inside an ignored folder can be un-ignored.
    """
    rules = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        negate = line.startswith("!")
        if negate:
            line = line[1:]
        folder_only = line.endswith("/")
        line = line.rstrip("/")
        anchored = "/" in line
        line = line.lstrip("/")
        rules.append((negate, folder_only, anchored, re.compile(_glob_regex(line) + r"\Z")))

    def decide(candidate, is_folder):
        result = False
        for negate, folder_only, anchored, rx in rules:
            if folder_only and not is_folder:
                continue
            target = candidate if anchored else candidate.rsplit("/", 1)[-1]
            if rx.match(target):
                result = not negate
        return result

    parts = path.split("/")
    for i in range(1, len(parts)):
        if decide("/".join(parts[:i]), True):
            return True
    return decide(path, False)


_GI_FILES = ["app.log", "debug.log", "logs/today.log", "build/app.o", "src/main.c",
             "src/main.o", "notes.txt", "doc/guide.txt", "doc/api/index.txt", ".env",
             "config.json", "src/config.json", "temp/cache.bin", "src/temp/x.tmp",
             "keep.log", "dist/app.js", "node_modules/a/index.js", "README.md",
             "out/report.pdf", "data/raw.csv", "src/temp.c", "main.pyc"]

_GI_RULES = ["*.log", "*.o", "build/", "/config.json", "doc/*.txt", "**/temp", "!keep.log",
             "node_modules/", ".env", "dist", "*.pyc", "out/*.pdf", "data/", "*.tmp",
             "temp/", "src/*.o"]


def _gi_case(r):
    rules = r.sample(_GI_RULES, r.randint(3, 5))
    if "!keep.log" in rules:
        # A negation only means something after a rule it undoes.
        rules.remove("!keep.log")
        rules.append("*.log")
        rules.append("!keep.log")
        rules = list(dict.fromkeys(rules))
    # Half the questions are about a file that is ignored: picked at random,
    # most files would not be, and "not ignored" would be a safe guess.
    want = r.random() < 0.5
    paths = list(_GI_FILES)
    r.shuffle(paths)
    path = next((p for p in paths if gitignored(rules, p) == want), paths[0])
    answer = "ignored" if gitignored(rules, path) else "not ignored"
    return ("Ignored or not",
            "A name without a slash matches at any depth; a leading slash means from the "
            "top only; a trailing slash means folders; ! un-ignores; the last match wins.",
            "\n".join(rules), f"Is `{path}` ignored?", answer)


# ============================================================== MAKEFILE

def _make_vars(r):
    name, version = r.choice(WORDS), r.randint(1, 9)
    lines = [f"NAME = {name}", f"VERSION = {version}", "", "all:",
             f"\t@echo $(NAME)-$(VERSION)"]
    return ("Variables", "$(NAME) is replaced by the variable's value. @ stops make "
            "printing the command itself.",
            "\n".join(lines), "What does `make` print?", f"{name}-{version}")


def _make_lazy(r):
    a1, a2 = r.sample(WORDS, 2)
    op = r.choice(["=", ":="])
    lines = [f"A = {a1}", f"B {op} $(A)", f"A = {a2}", "", "all:", "\t@echo $(B)"]
    return ("= and :=",
            "= is worked out when the variable is used, so it sees later changes. := is "
            "worked out on the spot.",
            "\n".join(lines), "What does `make` print?", a2 if op == "=" else a1)


def _make_order(r):
    names = r.sample(["fetch", "compile", "link", "test", "pack"], 3)
    order = r.sample(names, 3)
    lines = [f"all: {' '.join(order)}", "\t@echo done", ""]
    for n in names:
        lines += [f"{n}:", f"\t@echo {n}", ""]
    out = "\n".join(order + ["done"])
    return ("Prerequisites", "Before a target's own commands run, its prerequisites are "
            "made, left to right.",
            "\n".join(lines).rstrip(), "What does `make` print?", out)


def _make_default(r):
    names = r.sample(["build", "clean", "test", "install", "docs", "serve"], 3)
    lines = []
    for n in names:
        lines += [f"{n}:", f"\t@echo {n}", ""]
    if r.random() < 0.5:
        lines = [".PHONY: " + " ".join(names), ""] + lines
    return ("The default goal", "Plain make builds the first target in the file. .PHONY "
            "is not a target to build.",
            "\n".join(lines).rstrip(), "What does `make` print?", names[0])


def _make_func(r):
    files = r.sample(["main", "util", "net", "io", "app", "db"], r.randint(2, 4))
    kind = r.randrange(3)
    src = " ".join(f + ".c" for f in files)
    if kind == 0:
        expr, out = "$(patsubst %.c,%.o,$(SRC))", " ".join(f + ".o" for f in files)
    elif kind == 1:
        expr, out = "$(words $(SRC))", str(len(files))
    else:
        expr, out = "$(addprefix src/,$(SRC))", " ".join("src/" + f + ".c" for f in files)
    lines = [f"SRC = {src}", "", "all:", f"\t@echo {expr}"]
    return ("Functions", "patsubst rewrites each word, words counts them, addprefix puts "
            "text in front of each.",
            "\n".join(lines), "What does `make` print?", out)


def _make_cond(r):
    mode = r.choice(["debug", "release"])
    lines = [f"MODE = {mode}", "", "ifeq ($(MODE),debug)", "FLAGS = -g", "else",
             "FLAGS = -O2", "endif", "", "all:", "\t@echo $(FLAGS)"]
    return ("Conditionals", "ifeq picks one side when make reads the file.",
            "\n".join(lines), "What does `make` print?", "-g" if mode == "debug" else "-O2")


# ============================================================ DOCKERFILE

_BASES = ["python:3.13-slim", "node:22-alpine", "debian:bookworm", "golang:1.23",
          "nginx:1.27", "alpine:3.20", "eclipse-temurin:21"]


def dockerfile_facts(lines):
    """What a Dockerfile ends up with: the final stage's base, folder, port,
    command and environment. The rules, for the instructions practice uses."""
    facts = {"stages": 0}
    for line in lines:
        word, _, rest = line.strip().partition(" ")
        word = word.upper()
        if word == "FROM":
            facts = {"stages": facts["stages"] + 1, "from": rest.split(" AS ")[0].strip(),
                     "workdir": "/", "env": {}, "expose": [], "cmd": None, "user": "root"}
        elif word == "WORKDIR":
            facts["workdir"] = (rest if rest.startswith("/")
                                else facts["workdir"].rstrip("/") + "/" + rest)
        elif word == "ENV":
            key, _, value = rest.partition("=")
            facts["env"][key] = value
        elif word == "EXPOSE":
            facts["expose"].append(rest)
        elif word == "CMD":
            facts["cmd"] = json.loads(rest)
        elif word == "USER":
            facts["user"] = rest
    return facts


def _docker_lines(r, multistage=False):
    lines = []
    if multistage:
        lines += [f"FROM {r.choice(_BASES)} AS build", "WORKDIR /src", "RUN make", ""]
    lines.append(f"FROM {r.choice(_BASES)}")
    if multistage:
        lines.append("COPY --from=build /src/out /app")
    first = r.choice(["/app", "/srv", "/opt/app", "/work"])
    lines.append(f"WORKDIR {first}")
    if r.random() < 0.5:
        lines.append(f"WORKDIR {r.choice(['src', 'bin', 'data'])}")
    for _ in range(r.randint(1, 2)):
        lines.append(f"ENV MODE={r.choice(['prod', 'dev', 'test'])}")
    lines.append(f"EXPOSE {r.choice([80, 3000, 5000, 8000, 8080])}")
    if r.random() < 0.4:
        lines.append(f"USER {r.choice(['app', 'node', 'nobody'])}")
    for _ in range(r.randint(1, 2)):
        lines.append("CMD " + json.dumps([r.choice(["python", "node", "./app"]),
                                          r.choice(["main", "serve", "run"])]))
    return lines


def _docker_question(r):
    lines = _docker_lines(r, multistage=r.random() < 0.35)
    facts = dockerfile_facts(lines)
    kind = r.randrange(6)
    if kind == 0:
        ask, out = "Which image does the final stage start from?", facts["from"]
        title = "The base image"
    elif kind == 1:
        ask, out = "Which folder do commands run in at the end?", facts["workdir"]
        title = "WORKDIR"
    elif kind == 2:
        ask, out = "What command runs when the container starts?", " ".join(facts["cmd"])
        title = "CMD"
    elif kind == 3:
        ask, out = "Which value does `MODE` have?", facts["env"]["MODE"]
        title = "ENV"
    elif kind == 4:
        ask, out = "How many stages are there?", str(facts["stages"])
        title = "Stages"
    else:
        ask, out = "Which user runs the command?", facts["user"]
        title = "USER"
    return (title,
            "Each FROM starts a new stage and only the last one is the image. A relative "
            "WORKDIR builds on the one before. Only the last CMD counts, and a later ENV "
            "replaces an earlier one.",
            "\n".join(lines), ask, out)


# ================================================================== HTML

def _html_list(r):
    tag = r.choice(["ul", "ol"])
    xs = r.sample(ITEMS, r.randint(2, 6))
    lines = [f"<{tag}>"] + [f"  <li>{x}</li>" for x in xs] + [f"</{tag}>"]
    if r.random() < 0.5:
        lines = [f"<p>{r.choice(WORDS)}</p>"] + lines
    return ("Lists", "Each <li> is one item of the list around it.",
            "\n".join(lines), "How many items does the list have?", str(len(xs)))


def _html_link(r):
    word = r.choice(WORDS)
    url = f"https://example.com/{r.choice(WORDS)}"
    lines = ["<p>", f'  Read the <a href="{url}">{word} guide</a> first.', "</p>"]
    if r.random() < 0.5:
        return ("Links", "href is where a link goes; the text between the tags is what it "
                "shows.", "\n".join(lines), "Where does the link go?", url)
    return ("Links", "href is where a link goes; the text between the tags is what it shows.",
            "\n".join(lines), "Which text does the link show?", f"{word} guide")


def _html_heading(r):
    level = r.randint(1, 6)
    word = r.choice(WORDS).title()
    lines = [f"<h{level}>{word}</h{level}>", f"<p>About {word.lower()}.</p>"]
    return ("Headings", "<h1> is the biggest heading and <h6> the smallest.",
            "\n".join(lines), f"Which heading level is `{word}`?", str(level))


def _html_table(r):
    cols, rows = r.randint(2, 4), r.randint(1, 4)
    lines = ["<table>", "  <tr>" + "".join(f"<th>{c}</th>" for c in
                                            r.sample(["id", "name", "qty", "city"], cols))
             + "</tr>"]
    for _ in range(rows):
        lines.append("  <tr>" + "".join(f"<td>{r.randint(1, 99)}</td>" for _ in range(cols))
                     + "</tr>")
    lines.append("</table>")
    if r.random() < 0.5:
        return ("Tables", "<tr> is a row; <th> and <td> are its cells.",
                "\n".join(lines), "How many rows does the table have?", str(rows + 1))
    return ("Tables", "<tr> is a row; <th> and <td> are its cells.",
            "\n".join(lines), "How many cells are in each row?", str(cols))


def _html_parent(r):
    outer = r.choice(["div", "section", "article", "li", "p"])
    inner = r.choice(["span", "em", "strong", "code"])
    lines = ["<main>", f"  <{outer}>", f"    <{inner}>{r.choice(WORDS)}</{inner}>",
             f"  </{outer}>", "</main>"]
    return ("Parents", "An element's parent is the one it sits directly inside.",
            "\n".join(lines), f"Which element is the parent of `<{inner}>`?", f"<{outer}>")


def _html_input(r):
    kind = r.choice(["text", "email", "password", "number", "checkbox", "date"])
    name = r.choice(["user", "mail", "age", "agree", "start", "code"])
    lines = ["<form>", f'  <label for="{name}">{name.title()}</label>',
             f'  <input id="{name}" name="{name}" type="{kind}">', "</form>"]
    return ("Forms", "An input's type decides what kind of value it takes.",
            "\n".join(lines), "Which type is the input?", kind)


# =================================================================== CSS

def _css_width(r):
    width = r.choice([100, 120, 150, 200, 240, 300])
    pad = r.choice([0, 5, 10, 12, 20])
    border = r.choice([0, 1, 2, 4])
    sizing = r.choice(["content-box", "border-box"])
    lines = [".box {", f"  box-sizing: {sizing};", f"  width: {width}px;",
             f"  padding: {pad}px;", f"  border: {border}px solid;", "}"]
    total = width if sizing == "border-box" else width + 2 * pad + 2 * border
    return ("The box model",
            "With content-box, width is the content alone: padding and border go on top. "
            "With border-box, width already includes them.",
            "\n".join(lines), "How wide is `.box` on screen, in pixels?", str(total))


_COLOURS = ["red", "blue", "green", "orange", "purple", "teal", "navy", "olive"]


def css_winner(rules):
    """The colour a <p id="main" class="note"> ends up with: !important first,
    then specificity, then the later rule."""
    def specificity(selector):
        return (selector.count("#"), selector.count("."), 1 if selector.startswith("p") else 0)

    best = None
    for order, (selector, colour, important) in enumerate(rules):
        key = (important, specificity(selector), order)
        if best is None or key > best[0]:
            best = (key, colour)
    return best[1]


def _css_cascade(r):
    selectors = ["p", ".note", "#main", "p.note", "p#main", ".note.note"]
    chosen = r.sample(selectors, r.randint(2, 3))
    colours = r.sample(_COLOURS, len(chosen))
    rules = []
    for sel, col in zip(chosen, colours):
        rules.append((sel, col, r.random() < 0.15))
    lines = []
    for sel, col, important in rules:
        lines += [f"{sel} {{", f"  color: {col}{' !important' if important else ''};", "}"]
    lines.append('/* <p id="main" class="note">Hi</p> */')
    return ("The cascade",
            "!important beats everything; then an id beats classes, classes beat element "
            "names; on a tie, the later rule wins.",
            "\n".join(lines), "What colour is the paragraph?", css_winner(rules))


def _css_margin(r):
    a, b = r.choice([8, 10, 16, 20, 24, 30]), r.choice([8, 12, 16, 20, 32, 40])
    lines = [f".first {{", f"  margin-bottom: {a}px;", "}", ".second {",
             f"  margin-top: {b}px;", "}",
             '/* <p class="first">One</p><p class="second">Two</p> */']
    return ("Margins collapse", "The vertical margins of two blocks next to each other "
            "collapse into one: the bigger of the two.",
            "\n".join(lines), "How far apart are the two paragraphs, in pixels?",
            str(max(a, b)))


# ============================================================== MARKDOWN

def _md_list(r):
    xs = r.sample(ITEMS, r.randint(2, 6))
    marker = r.choice(["-", "*", "1."])
    lines = [f"# {r.choice(WORDS).title()}", ""]
    for i, x in enumerate(xs):
        lines.append(f"{i + 1}. {x}" if marker == "1." else f"{marker} {x}")
    return ("Lists", "Each line starting with - , * or a number and a dot is one item.",
            "\n".join(lines), "How many items does the list have?", str(len(xs)))


def _md_heading(r):
    level = r.randint(1, 6)
    word = r.choice(WORDS).title()
    lines = [f"{'#' * level} {word}", "", f"Some text about {word.lower()}."]
    return ("Headings", "The number of # signs is the heading's level.",
            "\n".join(lines), f"Which heading level is `{word}`?", str(level))


def _md_link(r):
    word = r.choice(WORDS)
    url = f"https://example.com/{r.choice(WORDS)}"
    text = f"See the [{word} notes]({url}) for more."
    if r.random() < 0.5:
        return ("Links", "[text](address): the text in square brackets, the address in "
                "round ones.", text, "Where does the link go?", url)
    return ("Links", "[text](address): the text in square brackets, the address in round "
            "ones.", text, "Which text does the link show?", f"{word} notes")


def _md_paragraphs(r):
    blocks = []
    for _ in range(r.randint(1, 4)):
        block = [_sentence(r, 4) + "." for _ in range(r.randint(1, 3))]
        blocks.append("\n".join(block))
    return ("Paragraphs", "Lines next to each other are one paragraph. Only an empty line "
            "starts a new one.",
            "\n\n".join(blocks), "How many paragraphs are there?", str(len(blocks)))


def _md_emphasis(r):
    a, b = r.sample(WORDS, 2)
    style = r.randrange(3)
    if style == 0:
        text, out = f"This is **{a}** and _{b}_.", a
    elif style == 1:
        text, out = f"This is *{a}* and __{b}__.", b
    else:
        text, out = f"This is __{a}__ and **{b}**.", f"{a} and {b}"
    return ("Bold", "Two stars or two underscores make bold; one makes italic.",
            text, "Which words are bold?", out)


DOCUMENTS = {
    "json": [_json_value, _json_count, _json_index, _json_path, _json_type, _json_length,
             _json_valid],
    "yaml": [_yaml_value, _yaml_path, _yaml_count, _yaml_index, _yaml_type, _yaml_anchor,
             _yaml_block],
    "toml": [_toml_find, _toml_table, _toml_array, _toml_aot, _toml_type, _toml_dotted,
             _toml_valid],
    "xml": [_xml_count, _xml_attr, _xml_text, _xml_root, _xml_depth, _xml_valid],
    "csv": [_csv_count, _csv_cell, _csv_total, _csv_columns, _csv_quotes],
    "ini": [_ini_value, _ini_sections, _ini_where, _ini_default, _ini_comments],
    "regex": [_re_digits, _re_first, _re_words, _re_group, _re_full, _re_alt, _re_class],
    "gitignore": [_gi_case, _gi_case, _gi_case],
    "makefile": [_make_vars, _make_lazy, _make_order, _make_default, _make_func, _make_cond],
    "dockerfile": [_docker_question, _docker_question, _docker_question],
    "html": [_html_list, _html_link, _html_heading, _html_table, _html_parent, _html_input],
    "css": [_css_width, _css_cascade, _css_margin],
    "markdown": [_md_list, _md_heading, _md_link, _md_paragraphs, _md_emphasis],
}
