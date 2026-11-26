#!/usr/bin/env python3
"""Checks PyCmdTeach's courses against reality.

Every lesson in the app is generated from a topic's snippet and the output
written beside it, so an output that is wrong is wrong in five lessons at once.
This runs every snippet in a language the app can execute - Python, C, Rust and
Go - and compares what came out with what the course claims.

It also checks the parts that are true of every course, runnable or not: that
the units are non-empty, that no topic's code is wide enough to wrap on a
phone, that the generated lessons have stable ids, and that each generated
question can actually be answered correctly.
"""

import io
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON_DIR = os.path.join(HERE, "..", "app", "src", "main", "python")
sys.path.insert(0, os.path.abspath(PYTHON_DIR))

import pycmd_teach  # noqa: E402
from pycmd_teach import Unit  # noqa: E402

FAILED = []
PASSED = 0

# Collected while walking the courses and run afterwards, because running
# them is the slow part and the walk should report its own failures first.
WHICH = []
BUGS = []


def check(name, condition, detail=""):
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}" if detail else name)


def flatten(text):
    return "\n".join(
        " ".join(line.split()) for line in text.strip().split("\n") if line.strip()
    )


def run_python(source):
    buffer = io.StringIO()
    out, err, inp = sys.stdout, sys.stderr, sys.stdin
    sys.stdout = buffer
    sys.stderr = buffer
    sys.stdin = io.StringIO("")
    try:
        exec(compile(source, "<topic>", "exec"), {"__name__": "__main__"})
    except BaseException as error:  # noqa: BLE001
        return buffer.getvalue(), f"{type(error).__name__}: {error}"
    finally:
        sys.stdout, sys.stderr, sys.stdin = out, err, inp
    return buffer.getvalue(), ""


def run_registry(source, extension):
    from pycmd_langs import registry

    handle = tempfile.NamedTemporaryFile(
        "w", suffix=extension, delete=False, encoding="utf-8",
    )
    handle.write(source)
    handle.close()
    try:
        buffer = io.StringIO()
        result = registry.run_file(handle.name, stdout=buffer, stdin=io.StringIO(""))
        if not result.get("ok"):
            return buffer.getvalue(), result.get("error", "did not run")
        return buffer.getvalue(), ""
    except Exception as error:  # noqa: BLE001
        # An interpreter crash is a finding, not a reason to stop counting.
        return "", f"the interpreter crashed: {type(error).__name__}: {error}"
    finally:
        os.unlink(handle.name)


import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

#: How to run one snippet with a real toolchain: the file name to write it
#: to, and the command (with {file} and {dir} filled in). A list of steps,
#: for the languages that compile first.
REAL = {
    "javascript": ("main.js", [["node", "{file}"]]),
    "typescript": ("main.ts", [["bun", "run", "{file}"]]),
    "ruby": ("main.rb", [["ruby", "{file}"]]),
    "php": ("main.php", [["php", "{file}"]]),
    "perl": ("main.pl", [["perl", "{file}"]]),
    "lua": ("main.lua", [["lua5.4", "{file}"]]),
    "java": ("Main.java", [["java", "{file}"]]),
    "cpp": ("main.cpp", [["g++", "-std=c++20", "-o", "{dir}/a.out", "{file}"],
                         ["{dir}/a.out"]]),
    "c": ("main.c", [["gcc", "-o", "{dir}/a.out", "{file}", "-lm"], ["{dir}/a.out"]]),
    "go": ("main.go", [["go", "run", "{file}"]]),
    "rust": ("main.rs", [["rustc", "-o", "{dir}/a.out", "{file}"], ["{dir}/a.out"]]),
    "shell": ("main.sh", [["bash", "{file}"]]),
    "sql": ("main.sql", [["sqlite3", ":memory:", ".read {file}"]]),
    "python": ("main.py", [[sys.executable, "{file}"]]),
}


def run_real(course_id, code):
    """Runs a snippet with a real toolchain. (output, error) or None if absent."""
    spec = REAL.get(course_id)
    if spec is None:
        return None
    filename, steps = spec
    if not shutil.which(steps[0][0]) and not os.path.isabs(steps[0][0]):
        return None
    folder = tempfile.mkdtemp(prefix=f"real-{course_id}-")
    path = os.path.join(folder, filename)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(code + "\n")
    output = ""
    env = dict(os.environ, GOCACHE=os.path.join(tempfile.gettempdir(), "teach-gocache"),
               GOFLAGS="-mod=mod")
    for step in steps:
        command = [part.replace("{file}", path).replace("{dir}", folder) for part in step]
        try:
            done = subprocess.run(command, cwd=folder, capture_output=True, text=True,
                                  timeout=120, stdin=subprocess.DEVNULL, env=env)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return "", str(exc)
        if done.returncode != 0:
            return done.stdout, (done.stderr or done.stdout)[-400:]
        output = done.stdout
    return output, ""


#: Courses about a format rather than a language, whose lessons that print
#: anything are Python using that format. They are checked as Python.
PYTHON_INSIDE = {"regex", "ini", "csv"}


def format_checks(courses):
    """Every JSON, TOML and XML snippet has to load.

    A course teaching a file format by showing a file that would not parse is
    teaching the wrong thing, and the standard library can say so.
    """
    import json as json_module
    import tomllib
    import xml.etree.ElementTree as ElementTree

    # The ones that are not meant to be a single valid document, by title.
    not_documents = {"JSON Lines", "Several documents", "A multi-document stream"}
    for course_id, loader in (
        ("json", json_module.loads),
        ("toml", tomllib.loads),
        ("xml", ElementTree.fromstring),
    ):
        course = courses.get(course_id)
        if course is None:
            continue
        for unit in course.units:
            for topic in unit["topics"]:
                if topic.title in not_documents:
                    continue
                # "Is this valid JSON?" is sometimes answered no, on purpose;
                # tools/test_practice.py checks those answers with the parser.
                if topic.ask.startswith("Is this"):
                    continue
                text = topic.code
                if course_id == "xml":
                    # A fragment is checked inside a root, and the declaration
                    # and processing instructions are taken off the front.
                    lines = [l for l in text.split("\n") if not l.startswith("<?")]
                    text = "<root xmlns:android='a' xmlns:a='b'>" + "\n".join(lines) + "</root>"
                    text = text.replace("&lt;", "&#60;")
                try:
                    loader(text)
                    ok, why = True, ""
                except Exception as error:  # noqa: BLE001
                    ok, why = False, str(error)
                check(f"{course_id} '{topic.title}' is a valid {course_id.upper()} document",
                      ok, why)


def _kotlinc_version():
    try:
        done = subprocess.run(["kotlinc", "-version"], capture_output=True, text=True,
                              timeout=120, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return (0, 0)
    found = re.search(r"kotlinc-jvm (\d+)\.(\d+)", done.stdout + done.stderr)
    return (int(found.group(1)), int(found.group(2))) if found else (0, 0)


#: What an old kotlinc (Debian's is 1.3) calls the functions the courses use.
#: Test-only, like the clojure and scala shims in the Windows tests: the
#: lessons are written for the Kotlin people install today.
_OLD_KOTLIN = {r"\buppercase\(\)": "toUpperCase()", r"\blowercase\(\)": "toLowerCase()",
               r"\.sumOf \{": ".sumBy {"}


def _kotlin_batch(jobs):
    """Every Kotlin snippet in one compiler run - kotlinc takes seconds to
    start, and there are hundreds of them. Each goes in a package of its own
    so that every one can have its own main. {index: (output, error)}."""
    folder = tempfile.mkdtemp(prefix="real-kotlin-")
    paths = []
    for index, code in jobs:
        sub = os.path.join(folder, f"p{index}")
        os.makedirs(sub, exist_ok=True)
        path = os.path.join(sub, "Main.kt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"package p{index}\n\n{code}\n")
        paths.append(path)
    jar = os.path.join(folder, "all.jar")
    try:
        done = subprocess.run(["kotlinc", *paths, "-d", jar], capture_output=True, text=True,
                              timeout=1800, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {index: ("", str(exc)) for index, _ in jobs}
    if done.returncode != 0:
        if len(jobs) == 1:
            return {jobs[0][0]: ("", done.stderr[-400:])}
        # One bad snippet fails the batch; halve it until the bad one is alone.
        half = len(jobs) // 2
        return {**_kotlin_batch(jobs[:half]), **_kotlin_batch(jobs[half:])}
    stdlib = next((os.path.join("/usr/share/java", name) for name in
                   ("kotlin-stdlib.jar",) if os.path.exists(os.path.join("/usr/share/java", name))),
                  "")
    results = {}

    def run_one(index):
        try:
            ran = subprocess.run(["java", "-cp", f"{jar}{os.pathsep}{stdlib}",
                                  f"p{index}.MainKt"], capture_output=True, text=True,
                                 timeout=120, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return index, ("", str(exc))
        if ran.returncode != 0:
            return index, (ran.stdout, ran.stderr[-400:])
        return index, (ran.stdout, "")

    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
        for index, result in pool.map(run_one, [i for i, _ in jobs]):
            results[index] = result
    return results


def real_checks(courses):
    format_checks(courses)
    for course in courses.values():
        if course.id in PYTHON_INSIDE:
            for unit in course.units:
                for topic in unit["topics"]:
                    if not topic.out or "import " not in topic.code:
                        continue
                    got, error = run_python(topic.code)
                    check(f"{course.id} '{topic.title}' runs as Python", not error, error)
                    check(f"{course.id} '{topic.title}' prints what it says",
                          flatten(got) == flatten(topic.out),
                          f"got {flatten(got)!r}, course says {flatten(topic.out)!r}")
            continue
        if course.id not in REAL:
            continue
        tool = REAL[course.id][1][0][0]
        if not shutil.which(tool) and not os.path.isabs(tool):
            print(f"  SKIP  {course.name}: no {tool} here to check it with")
            continue
        checked = 0
        topics = [topic for unit in course.units for topic in unit["topics"]
                  if topic.out and not topic.ask]
        # Hundreds of snippets a course since 2.9.0's practice rounds: run them
        # side by side, one per core.
        with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
            results = list(pool.map(lambda t: run_real(course.id, t.code), topics))
        for topic, result in zip(topics, results):
            if result is None:
                continue
            got, error = result
            checked += 1
            if error:
                check(f"{course.id} '{topic.title}' runs on the real {tool}", False, error)
                continue
            check(
                f"{course.id} '{topic.title}' prints the same on the real {tool}",
                flatten(got) == flatten(topic.out),
                f"got {flatten(got)!r}, course says {flatten(topic.out)!r}",
            )
        print(f"  {course.name}: {checked} snippets checked on the real {tool}")

    # Kotlin is checked in one compiler run, not one per snippet.
    course = courses.get("kotlin")
    if course is not None:
        if not (shutil.which("kotlinc") and shutil.which("java")):
            print("  SKIP  Kotlin: no kotlinc here to check it with")
        else:
            topics = [topic for unit in course.units for topic in unit["topics"]
                      if topic.out and not topic.ask]
            codes = [t.code for t in topics]
            if _kotlinc_version() < (1, 5):
                # No coroutines library on a box this old; everything else is
                # translated back to the names that compiler knows.
                skipped = [t for t in topics if "kotlinx.coroutines" in t.code]
                topics = [t for t in topics if t not in skipped]
                codes = [t.code for t in topics]
                for new_name, old_name in _OLD_KOTLIN.items():
                    codes = [re.sub(new_name, old_name, c) for c in codes]
                print(f"  Kotlin: kotlinc is older than 1.5, so {len(skipped)} coroutine "
                      "snippet(s) are not checked")
            results = _kotlin_batch(list(enumerate(codes)))
            for index, topic in enumerate(topics):
                got, error = results[index]
                if error:
                    check(f"kotlin '{topic.title}' runs on the real kotlinc", False, error)
                    continue
                check(f"kotlin '{topic.title}' prints the same on the real kotlinc",
                      flatten(got) == flatten(topic.out),
                      f"got {flatten(got)!r}, course says {flatten(topic.out)!r}")
            print(f"  Kotlin: {len(topics)} snippets checked on the real kotlinc")


def main():
    # Progress goes somewhere disposable: marking every generated question
    # writes to the review list, and that should not land in /tmp for good.
    pycmd_teach.configure(tempfile.mkdtemp(prefix="teach-progress-"))
    courses = pycmd_teach._courses()
    check("courses", len(courses) >= 20, f"only {len(courses)}")

    # The scratch directory the file lessons write into.
    work = tempfile.mkdtemp(prefix="teach-")
    os.chdir(work)

    total_topics = 0
    total_lessons = 0

    for course in courses.values():
        units = course.units
        check(f"{course.id} has units", len(units) >= 2, f"{len(units)} units")
        ids = set()
        for unit in units:
            check(
                f"{course.id}/{unit['title']} is not empty",
                len(unit["topics"]) > 0,
            )
        tree = pycmd_teach._tree(course)
        lessons = [row for u in tree for row in u["lessons"]]
        total_lessons += len(lessons)
        for row in lessons:
            check(f"{course.id} lesson id unique", row["id"] not in ids, row["id"])
            ids.add(row["id"])
            # Every generated question must be answerable.
            if row["kind"] == "predict":
                want = row["options"][pycmd_teach._correct_index(course, row)]
                reply = pycmd_teach.check(course.id, row["id"], want)
                check(f"{course.id} {row['id']} predict answerable", reply.get("right"), str(reply))
            elif row["kind"] == "fill":
                want = pycmd_teach._fill_answer(course, row)
                check(f"{course.id} {row['id']} fill has an answer", bool(want))
                reply = pycmd_teach.check(course.id, row["id"], want)
                check(f"{course.id} {row['id']} fill answerable", reply.get("right"), str(reply))
                check(
                    f"{course.id} {row['id']} fill option present",
                    want in row["options"],
                    str(row["options"]),
                )
            elif row["kind"] == "write":
                # "Show me" reveals this. In 2.7.0 it was missing and the
                # button opened an empty box.
                check(f"{course.id} {row['id']} write carries its answer",
                      bool(row.get("code", "").strip()), row.get("code"))
                if row.get("graded") == "text":
                    check(f"{course.id} {row['id']} text write has a hint",
                          bool(row.get("hint")), row)
                reply = pycmd_teach.check(course.id, row["id"], row["code"])
                if row.get("graded") == "text":
                    check(f"{course.id} {row['id']} its own answer is right",
                          reply.get("right"), reply)
            elif row["kind"] == "which":
                topic = pycmd_teach._topic_for(course, row["id"])
                check(f"{course.id} {row['id']} which has the right snippet",
                      topic.code in row["options"])
                check(f"{course.id} {row['id']} which has no duplicate options",
                      len(set(row["options"])) == len(row["options"]))
                reply = pycmd_teach.check(course.id, row["id"], topic.code)
                check(f"{course.id} {row['id']} which answerable", reply.get("right"), reply)
                WHICH.append((course, row, topic))
            elif row["kind"] == "bug":
                topic = pycmd_teach._topic_for(course, row["id"])
                broken = pycmd_teach._break(course, topic)
                check(f"{course.id} {row['id']} bug has a broken line", bool(broken))
                if broken:
                    check(f"{course.id} {row['id']} the broken line is offered",
                          broken[1] in row["options"])
                    reply = pycmd_teach.check(course.id, row["id"], broken[1])
                    check(f"{course.id} {row['id']} bug answerable", reply.get("right"), reply)
                    BUGS.append((course, row, broken[0]))
            if row["kind"] in ("fill", "order", "write", "predict"):
                # "Editor" opens the topic's real snippet, never the blanked,
                # shuffled or empty version an exercise shows.
                topic = pycmd_teach._topic_for(course, row["id"])
                opened = pycmd_teach.snippet(course.id, row["id"])
                check(f"{course.id} {row['id']} opens the real snippet",
                      opened.get("code", "").rstrip("\n") == topic.code,
                      opened.get("code", "")[:60])
            if row["kind"] == "order":
                want = "\n".join(pycmd_teach._order_answer(course, row))
                reply = pycmd_teach.check(course.id, row["id"], want)
                check(f"{course.id} {row['id']} order answerable", reply.get("right"), str(reply))
                check(
                    f"{course.id} {row['id']} order is shuffled",
                    row["lines"] != want.split("\n"),
                )

        for unit in units:
            for topic in unit["topics"]:
                total_topics += 1
                widest = max((len(line) for line in topic.code.split("\n")), default=0)
                check(
                    f"{course.id} '{topic.title}' fits a phone",
                    widest <= 58,
                    f"{widest} characters wide",
                )
                check(f"{course.id} '{topic.title}' has code", bool(topic.code.strip()))
                check(f"{course.id} '{topic.title}' explains itself", len(topic.teach) > 10)

                if course.graded != "run" or not topic.out:
                    continue
                if course.extension == ".py":
                    got, error = run_python(topic.code)
                else:
                    got, error = run_registry(topic.code, course.extension)
                if error:
                    check(f"{course.id} '{topic.title}' runs", False, error)
                    continue
                check(
                    f"{course.id} '{topic.title}' prints what it says",
                    flatten(got) == flatten(topic.out),
                    f"got {flatten(got)!r}, course says {flatten(topic.out)!r}",
                )

    # ---- "which of these prints it": exactly one of them does ----------
    #
    # Run every option of every runnable question. The distractors are taken
    # from other topics with a different stated output, but two snippets can
    # print the same thing without saying so - and then the question has two
    # right answers and marks one of them wrong.
    for course, row, topic in WHICH:
        if course.graded != "run":
            continue
        printing = []
        for option in row["options"]:
            if course.extension == ".py":
                got, error = run_python(option)
            else:
                got, error = run_registry(option, course.extension)
            if not error and flatten(got) == flatten(topic.out):
                printing.append(option)
        check(f"{course.id} {row['id']} exactly one option prints the answer",
              printing == [topic.code], f"{len(printing)} do")

    # ---- "one line is broken": it really is ---------------------------
    #
    # The exercise claims the snippet is wrong. For the languages the app can
    # run, prove it: the broken program must not run cleanly.
    for course, row, code in BUGS:
        if course.graded != "run":
            continue
        if course.extension == ".py":
            try:
                compile(code, "<bug>", "exec")
                _, error = run_python(code)
            except SyntaxError as exc:
                error = str(exc)
        else:
            _, error = run_registry(code, course.extension)
        check(f"{course.id} {row['id']} the broken snippet really is broken",
              bool(error), code)

    # ---- the stated outputs, checked by the real toolchains -------------
    #
    # The phone can only run Python, C, Rust and Go. A machine with Node,
    # Ruby or a JDK on it can check the rest - and the real go and rustc
    # double-check that the app's own interpreters agree with the compilers.
    # Every toolchain is optional: one that is missing skips its course and
    # says so, rather than failing a laptop that never installed PHP.
    real_checks(courses)

    # ---- the limits on a written answer -------------------------------
    #
    # Somebody will write `while True` into a lesson, and the lesson runs it.
    # Without these the Teach tab would hang, which is the one complaint this
    # release is meant to be fixing.
    pycmd_teach.configure(work)
    saved_time, saved_out = pycmd_teach.TIME_LIMIT, pycmd_teach.OUTPUT_LIMIT
    try:
        pycmd_teach.TIME_LIMIT = 0.5
        started = time.monotonic()
        reply = pycmd_teach.check("python", "0.0.write", "while True:\n    pass")
        elapsed = time.monotonic() - started
        check("a loop that never ends is stopped", not reply.get("right"), reply)
        check("and stopped quickly", elapsed < 3, f"{elapsed:.1f}s")
        check("and says why", "still running" in reply.get("message", ""), reply)

        pycmd_teach.OUTPUT_LIMIT = 500
        out, error = pycmd_teach._run_python("for i in range(100000):\n    print(i)")
        check("output is capped", len(out) < 2000, len(out))
        check("and says it was cut", "more than it is worth" in out, out[-60:])
        check("capping is not an error", error == "", error)

        # And the ordinary case still works with both limits in place.
        reply = pycmd_teach.check("python", "0.0.write", 'print("hello")')
        check("a right answer is still right", reply.get("right"), reply)
    finally:
        pycmd_teach.TIME_LIMIT = saved_time
        pycmd_teach.OUTPUT_LIMIT = saved_out

    # ---- 2.9.0: counting lessons without building them ------------------
    #
    # The course list counts lessons with _kinds(), which follows the same
    # rules as _topic_lessons() without making the lessons - 50,000 of them
    # took seconds to build on a phone. If the two ever disagree, the list
    # says a course has lessons it does not, and progress percentages lie.
    for course_ in courses.values():
        built = [row["id"] for unit in pycmd_teach._tree(course_) for row in unit["lessons"]]
        check(f"{course_.id}: the lesson count matches the lessons",
              built == pycmd_teach._lesson_ids(course_),
              f"{len(built)} built, {len(pycmd_teach._lesson_ids(course_))} counted")
        check(f"{course_.id} has about 1,800 lessons", 1700 <= len(built) <= 1900, len(built))

    # ---- the shape of an ordering exercise ----------------------------
    #
    # Pinned because it caught a crash: a snippet's lines are not unique - any
    # brace language has several `}` - so anything that keys a list off the
    # line text throws on the 56 lessons that repeat one. The app keys those
    # rows by position; this is here so that nobody "simplifies" it back.
    repeats = 0
    for course_ in courses.values():
        for unit in pycmd_teach._tree(course_):
            for row in unit["lessons"]:
                if row["kind"] != "order":
                    continue
                if len(set(row["lines"])) != len(row["lines"]):
                    repeats += 1
    check("ordering lessons do repeat lines, and that is allowed", repeats > 0, repeats)

    # ---- 2.8.1: "spot the mistake" always has a choice to make ------------
    #
    # A one-line program made a question with one line to tap. Those lessons
    # are gone, and somebody who missed one on 2.8.0 must not be shown a
    # Review count for a lesson that no longer exists, nor lose Continue.
    lonely = [row["id"] for course_ in courses.values() for unit in pycmd_teach._tree(course_)
              for row in unit["lessons"] if row["kind"] == "bug" and len(row["options"]) < 2]
    check("no 'spot the mistake' lesson has only one line to choose", not lonely, lonely[:5])
    gone = "0.0.bug"
    check("a one-line topic has no bug lesson", pycmd_teach._find(courses["python"], gone) is None)
    saved = pycmd_teach._read_progress()
    try:
        data = dict(saved)
        data["missed"] = {"python": [gone, "0.0.predict"]}
        data["last"] = {"course": "python", "lesson": gone}
        pycmd_teach._write_progress(data)
        totals = pycmd_teach.totals()
        check("Review counts only lessons that still exist",
              totals["missed"] == len(pycmd_teach.review()) == 1, totals["missed"])
        check("Continue from a lesson that was removed lands on the next one",
              totals["continue"].get("lesson") == "0.0.write", totals["continue"])
    finally:
        pycmd_teach._write_progress(saved)

    print(f"{len(courses)} courses, {total_topics} topics, {total_lessons} lessons")
    for course in sorted(courses.values(), key=lambda c: c.name.lower()):
        count = sum(len(u["lessons"]) for u in pycmd_teach._tree(course))
        print(f"  {course.name:<14} {count:>4} lessons  ({len(course.units)} units)")

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
