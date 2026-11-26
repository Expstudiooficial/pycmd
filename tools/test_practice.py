#!/usr/bin/env python3
"""Every practice question about a document, answered by the real thing.

pycmd_teach.practice_docs writes JSON, YAML, TOML, XML, CSV, INI, regular
expressions, .gitignore files, Makefiles, Dockerfiles, HTML, CSS and Markdown
from small descriptions, and works each answer out from the description.
This test throws the description away and asks the document itself: json,
tomllib, PyYAML, ElementTree, csv and configparser load it, re runs the
pattern, git decides what is ignored, make runs the Makefile, markdown-it
renders the Markdown, and Chromium lays out the CSS. Any answer that
disagrees is a failure.

A tool that is missing (no make, no git, no Chromium) skips its course and
says so.

    python3 tools/test_practice.py
"""

from __future__ import annotations

import configparser
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ElementTree
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app", "src", "main", "python"))

import pycmd_teach  # noqa: E402
from pycmd_teach import practice_docs  # noqa: E402

PASSED = 0
FAILED: list = []


def check(name, condition, detail=""):
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")


def flat(text):
    return "\n".join(" ".join(line.split()) for line in str(text).strip().split("\n")
                     if line.strip())


def ticked(ask):
    """The `names` in a question, in order."""
    return re.findall(r"`([^`]*)`", ask)


# ----------------------------------------------------------- value text

def as_json(value):
    return json.dumps(value)


def as_yaml(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def as_toml(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


def walk(data, path):
    """a.b[2] -> data['a']['b'][2]."""
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        data = data[int(part[1:-1])] if part.startswith("[") else data[part]
    return data


# ---------------------------------------------------------------- per course

def answer_json(code, ask):
    if ask.startswith("Is this valid"):
        try:
            json.loads(code)
            return "valid"
        except ValueError:
            return None  # any "not valid: ..." answer; the reason is checked below
    doc = json.loads(code)
    names = ticked(ask)
    if ask.startswith("Which value") or ask.startswith("What does"):
        return as_json(walk(doc, names[0]))
    if ask.startswith("How many keys"):
        return str(len(doc))
    if ask.startswith("Which element"):
        index = int(re.search(r"index (\d+)", ask).group(1))
        return as_json(doc["items"][index])
    if ask.startswith("What type"):
        value = doc["value"]
        return {str: "string", bool: "boolean", int: "number", float: "number",
                type(None): "null", list: "array", dict: "object"}[type(value)]
    if ask.startswith("How long"):
        return str(len(doc["scores"]))
    raise KeyError(ask)


def json_reason(code):
    """Why a JSON document fails, by what the parser complains about."""
    try:
        json.loads(code)
    except ValueError as error:
        message = str(error)
        if "trailing comma" in message:
            return "a trailing comma"
        if "//" in code:
            return "JSON has no comments"
        if re.search(r"'\w+'", code):
            return "single quotes"
        return "a key without quotes"
    return ""


def answer_yaml(code, ask):
    import yaml

    doc = yaml.safe_load(code)
    names = ticked(ask)
    if ask.startswith("Which value"):
        return as_yaml(walk(doc, names[0]))
    if ask.startswith("How many items"):
        return str(len(doc[names[0]]))
    if ask.startswith("What type"):
        value = doc["value"]
        return {str: "string", bool: "boolean", int: "integer", float: "float",
                type(None): "null", list: "list", dict: "mapping"}[type(value)]
    if ask.startswith("How many lines"):
        return str(len(doc["text"].rstrip("\n").split("\n")))
    raise KeyError(ask)


def answer_toml(code, ask):
    import datetime

    if ask.startswith("Is this valid"):
        try:
            tomllib.loads(code)
            return "valid"
        except tomllib.TOMLDecodeError:
            return None
    doc = tomllib.loads(code)
    names = ticked(ask)
    if ask.startswith("Which value"):
        return as_toml(walk(doc, names[0]))
    if ask.startswith("How many items") or ask.startswith("How many tables"):
        return str(len(doc[names[0]]))
    if ask.startswith("What type"):
        value = doc["value"]
        if isinstance(value, datetime.date):
            return "date"
        return {str: "string", bool: "boolean", int: "integer", float: "float",
                list: "array", dict: "table"}[type(value)]
    raise KeyError(ask)


def toml_reason(code):
    try:
        tomllib.loads(code)
    except tomllib.TOMLDecodeError as error:
        message = str(error).lower()
        if "invalid value" in message:
            return "a string without quotes"
        if "cannot declare" in message and "[" in code.split("\n")[0] or \
                code.count("[server]") > 1:
            return "a table defined twice"
        return "a key defined twice"
    return ""


def answer_xml(code, ask):
    if ask.startswith("Is this well-formed"):
        try:
            ElementTree.fromstring(code)
            return "well-formed"
        except ElementTree.ParseError:
            return None
    root = ElementTree.fromstring(code.split("?>", 1)[-1] if code.startswith("<?") else code)
    names = ticked(ask)
    if ask.startswith("How many"):
        if ask.startswith("How many `"):
            return str(len(list(root.iter(names[0].strip("<>")))))
    if ask.startswith("Which value"):
        nth = ["first", "second", "third", "fourth"].index(re.search(
            r"the (\w+) `", ask).group(1))
        return list(root.iter(names[1].strip("<>")))[nth].get("id")
    if ask.startswith("What text"):
        return root.find(names[0].strip("<>")).text
    if ask.startswith("Which element"):
        return f"<{root.tag}>"
    if ask.startswith("How deep"):
        def depth(node):
            return 1 + max((depth(child) for child in node), default=0)
        return str(depth(root))
    raise KeyError(ask)


def xml_reason(code):
    try:
        ElementTree.fromstring(code)
    except ElementTree.ParseError as error:
        message = str(error)
        if "junk after document element" in message:
            return "two root elements"
        if "mismatched tag" in message:
            return "a mismatched end tag"
        if "not well-formed" in message and "&" in code:
            return "a bare &"
        return "an attribute without quotes"
    return ""


def answer_csv(code, ask):
    rows = list(csv.DictReader(io.StringIO(code)))
    names = ticked(ask)
    if ask.startswith("How many data"):
        return str(len(rows))
    if ask.startswith("Which value"):
        index = int(re.search(r"row (\d+)", ask).group(1)) - 1
        return rows[index][names[0]]
    if ask.startswith("What is the total"):
        return str(sum(int(row["qty"]) for row in rows))
    if ask.startswith("How many columns"):
        return str(len(next(csv.reader(io.StringIO(code)))))
    raise KeyError(ask)


def answer_ini(code, ask):
    parser = configparser.ConfigParser()
    parser.read_string(code)
    names = ticked(ask)
    if ask.startswith("Which value"):
        return parser[names[1].strip("[]")][names[0]]
    if ask.startswith("How many sections"):
        return str(len(parser.sections()))
    if ask.startswith("Which section"):
        holders = [s for s in parser.sections() if names[0] in parser._sections[s]]
        return f"[{holders[0]}]" if len(holders) == 1 else f"{holders}"
    raise KeyError(ask)


def answer_regex(code, ask):
    lines = code.split("\n")
    pattern = lines[0].split(":", 1)[1].strip()
    text = lines[1].split(":", 1)[1].strip()
    if ask.startswith("How many matches"):
        return str(sum(1 for _ in re.finditer(pattern, text)))
    if ask.startswith("Which is the first"):
        return re.search(pattern, text).group(0)
    if ask.startswith("Which text"):
        group = int(re.search(r"group (\d+)", ask).group(1))
        return re.search(pattern, text).group(group)
    if ask.startswith("Does the whole"):
        return "yes" if re.fullmatch(pattern.strip("^$"), text) else "no"
    raise KeyError(ask)


def answer_gitignore(code, ask):
    path = ticked(ask)[0]
    folder = tempfile.mkdtemp(prefix="practice-git-")
    subprocess.run(["git", "init", "-q", folder], check=True, timeout=60,
                   stdin=subprocess.DEVNULL)
    with open(os.path.join(folder, ".gitignore"), "w", encoding="utf-8") as handle:
        handle.write(code + "\n")
    full = os.path.join(folder, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write("x\n")
    done = subprocess.run(["git", "-c", "core.excludesFile=", "check-ignore", "-q", path],
                          cwd=folder, timeout=60, stdin=subprocess.DEVNULL)
    shutil.rmtree(folder, ignore_errors=True)
    return "ignored" if done.returncode == 0 else "not ignored"


def answer_makefile(code, ask):
    folder = tempfile.mkdtemp(prefix="practice-make-")
    with open(os.path.join(folder, "Makefile"), "w", encoding="utf-8") as handle:
        handle.write(code + "\n")
    done = subprocess.run(["make", "-s", "--no-print-directory"], cwd=folder,
                          capture_output=True, text=True, timeout=60,
                          stdin=subprocess.DEVNULL)
    shutil.rmtree(folder, ignore_errors=True)
    if done.returncode != 0:
        return f"make failed: {done.stderr.strip()[-200:]}"
    return done.stdout


def answer_dockerfile(code, ask):
    """No Docker here, so the Dockerfile reference's rules, written out again
    independently of the generator: instructions are case-insensitive, FROM
    resets everything, a relative WORKDIR joins the one before, the last CMD
    and the last ENV of a name win."""
    stage = None
    stages = 0
    for raw in code.split("\n"):
        if not raw.strip():
            continue
        instruction, argument = raw.split(None, 1)
        instruction = instruction.upper()
        if instruction == "FROM":
            stages += 1
            stage = {"image": argument.split()[0], "dir": "/", "env": {}, "cmd": "",
                     "user": "root"}
        elif instruction == "WORKDIR":
            stage["dir"] = os.path.normpath(os.path.join(stage["dir"], argument))
        elif instruction == "ENV":
            name, value = argument.split("=", 1)
            stage["env"][name] = value
        elif instruction == "CMD":
            stage["cmd"] = " ".join(json.loads(argument))
        elif instruction == "USER":
            stage["user"] = argument
    if ask.startswith("Which image"):
        return stage["image"]
    if ask.startswith("Which folder"):
        return stage["dir"]
    if ask.startswith("What command"):
        return stage["cmd"]
    if ask.startswith("Which value"):
        return stage["env"][ticked(ask)[0]]
    if ask.startswith("How many stages"):
        return str(stages)
    if ask.startswith("Which user"):
        return stage["user"]
    raise KeyError(ask)


class Tree(HTMLParser):
    """Just enough of a DOM: (tag, attrs, parent, text) for every element."""

    VOID = {"input", "meta", "br", "img", "link", "hr"}

    def __init__(self):
        super().__init__()
        self.nodes = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs),
                "parent": self.stack[-1]["tag"] if self.stack else None, "text": ""}
        self.nodes.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        while self.stack:
            if self.stack.pop()["tag"] == tag:
                break

    def handle_data(self, data):
        for node in self.stack:
            node["text"] += data


def parse_html(code):
    tree = Tree()
    tree.feed(code)
    return tree.nodes


def answer_html(code, ask):
    nodes = parse_html(code)
    names = ticked(ask)

    def find(tag):
        return [n for n in nodes if n["tag"] == tag]

    if ask.startswith("How many items"):
        return str(len(find("li")))
    if ask.startswith("Where does"):
        return find("a")[0]["attrs"]["href"]
    if ask.startswith("Which text"):
        return find("a")[0]["text"].strip()
    if ask.startswith("Which heading"):
        heading = next(n for n in nodes if re.fullmatch(r"h[1-6]", n["tag"])
                       and n["text"].strip() == names[0])
        return heading["tag"][1]
    if ask.startswith("How many rows"):
        return str(len(find("tr")))
    if ask.startswith("How many cells"):
        per_row = {}
        row = -1
        for node in nodes:
            if node["tag"] == "tr":
                row += 1
            elif node["tag"] in ("td", "th"):
                per_row[row] = per_row.get(row, 0) + 1
        widths = set(per_row.values())
        return str(widths.pop()) if len(widths) == 1 else f"uneven rows: {per_row}"
    if ask.startswith("Which element"):
        return f"<{find(names[0].strip('<>'))[0]['parent']}>"
    if ask.startswith("Which type"):
        return find("input")[0]["attrs"]["type"]
    raise KeyError(ask)


def answer_markdown(code, ask):
    from markdown_it import MarkdownIt

    html = MarkdownIt("commonmark").render(code)
    nodes = parse_html(html)
    names = ticked(ask)
    if ask.startswith("How many items"):
        return str(sum(1 for n in nodes if n["tag"] == "li"))
    if ask.startswith("Which heading"):
        heading = next(n for n in nodes if re.fullmatch(r"h[1-6]", n["tag"])
                       and n["text"].strip() == names[0])
        return heading["tag"][1]
    if ask.startswith("Where does"):
        return next(n for n in nodes if n["tag"] == "a")["attrs"]["href"]
    if ask.startswith("Which text"):
        return next(n for n in nodes if n["tag"] == "a")["text"].strip()
    if ask.startswith("How many paragraphs"):
        return str(sum(1 for n in nodes if n["tag"] == "p"))
    if ask.startswith("Which words"):
        return " and ".join(n["text"] for n in nodes if n["tag"] == "strong")
    raise KeyError(ask)


ANSWERS = {
    "json": answer_json, "yaml": answer_yaml, "toml": answer_toml, "xml": answer_xml,
    "csv": answer_csv, "ini": answer_ini, "regex": answer_regex,
    "gitignore": answer_gitignore, "makefile": answer_makefile,
    "dockerfile": answer_dockerfile, "html": answer_html, "markdown": answer_markdown,
}

REASONS = {"json": json_reason, "toml": toml_reason, "xml": xml_reason}

NEEDS = {"gitignore": "git", "makefile": "make"}


# ---------------------------------------------------------------- CSS, in Chromium

CSS_SCRIPT = r"""
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const answers = [];
  for (const c of cases) {
    await page.setContent(`<style>body{margin:0} ${c.css}</style>${c.html}`);
    answers.push(await page.evaluate((kind) => {
      if (kind === 'width') {
        return String(Math.round(document.querySelector('.box').getBoundingClientRect().width));
      }
      if (kind === 'gap') {
        const a = document.querySelector('.first').getBoundingClientRect();
        const b = document.querySelector('.second').getBoundingClientRect();
        return String(Math.round(b.top - a.bottom));
      }
      const got = getComputedStyle(document.querySelector('#main')).color;
      for (const name of ['red','blue','green','orange','purple','teal','navy','olive']) {
        const probe = document.createElement('span');
        probe.style.color = name;
        document.body.appendChild(probe);
        const rgb = getComputedStyle(probe).color;
        probe.remove();
        if (rgb === got) return name;
      }
      return got;
    }, c.kind));
  }
  await browser.close();
  fs.writeFileSync(process.argv[3], JSON.stringify(answers));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def css_checks(topics):
    if not shutil.which("node"):
        print("  SKIP  CSS: no node here to drive Chromium")
        return
    cases = []
    for topic in topics:
        css = "\n".join(line for line in topic.code.split("\n") if not line.startswith("/*"))
        if topic.ask.startswith("How wide"):
            cases.append({"kind": "width", "css": css, "html": '<div class="box">x</div>'})
        elif topic.ask.startswith("How far"):
            cases.append({"kind": "gap", "css": css,
                          "html": '<p class="first">One</p><p class="second">Two</p>'})
        else:
            cases.append({"kind": "colour", "css": css,
                          "html": '<p id="main" class="note">Hi</p>'})
    folder = tempfile.mkdtemp(prefix="practice-css-")
    script = os.path.join(folder, "css.js")
    with open(script, "w", encoding="utf-8") as handle:
        handle.write(CSS_SCRIPT)
    cases_path = os.path.join(folder, "cases.json")
    with open(cases_path, "w", encoding="utf-8") as handle:
        json.dump(cases, handle)
    out_path = os.path.join(folder, "answers.json")
    node_path = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True,
                               timeout=60).stdout.strip()
    done = subprocess.run(["node", script, cases_path, out_path], capture_output=True,
                          text=True, timeout=1200, env=dict(os.environ, NODE_PATH=node_path))
    if done.returncode != 0:
        check("Chromium lays the CSS out", False, done.stderr[-400:])
        return
    with open(out_path, encoding="utf-8") as handle:
        answers = json.load(handle)
    for topic, got in zip(topics, answers):
        check(f"css '{topic.title}' is what Chromium shows", got == topic.out,
              f"{topic.ask} Chromium says {got!r}, the lesson says {topic.out!r}")
    print(f"  CSS: {len(topics)} questions checked in Chromium")


# ---------------------------------------------------------------- main

def practice_topics(course):
    return [t for unit in course.units for t in unit["topics"] if t.ask]


def main():
    pycmd_teach.configure(tempfile.mkdtemp(prefix="practice-progress-"))
    courses = pycmd_teach._courses()

    for course_id in practice_docs.DOCUMENTS:
        course = courses.get(course_id)
        check(f"{course_id} is a course", course is not None)
        if course is None:
            continue
        topics = practice_topics(course)
        check(f"{course_id} has practice questions", len(topics) > 100, len(topics))
        if course_id == "css":
            css_checks(topics)
            continue
        tool = NEEDS.get(course_id)
        if tool and not shutil.which(tool):
            print(f"  SKIP  {course.name}: no {tool} here")
            continue
        answer = ANSWERS[course_id]

        def one(topic):
            try:
                return answer(topic.code, topic.ask), ""
            except Exception as error:  # noqa: BLE001
                return None, f"{type(error).__name__}: {error}"

        with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
            results = list(pool.map(one, topics))
        for topic, (got, error) in zip(topics, results):
            name = f"{course_id} '{topic.title}' ({topic.ask})"
            if error:
                check(name, False, error)
                continue
            if got is None:
                # The document does not load, which is the right answer only if
                # the lesson says so - and says why.
                reason = REASONS[course_id](topic.code)
                check(name, topic.out.startswith("not ") and topic.out.endswith(reason),
                      f"the parser refuses it ({reason}); the lesson says {topic.out!r}")
                continue
            check(name, flat(got) == flat(topic.out),
                  f"the real thing says {flat(got)!r}, the lesson says {flat(topic.out)!r}")
        print(f"  {course.name}: {len(topics)} questions checked")

    # The questions have to be answerable from the choices: the right one is
    # always there, and there is something to choose between.
    for course_id in practice_docs.DOCUMENTS:
        course = courses.get(course_id)
        if course is None:
            continue
        for unit in pycmd_teach._tree(course):
            for row in unit["lessons"]:
                if row["kind"] != "predict":
                    continue
                check(f"{course_id} {row['id']} offers a choice", len(row["options"]) >= 2,
                      row["options"])

    print(f"\n{PASSED} checks passed")
    if FAILED:
        print(f"{len(FAILED)} FAILED:")
        for line in FAILED[:60]:
            print("  -", line)
        if len(FAILED) > 60:
            print(f"  ... and {len(FAILED) - 60} more")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
