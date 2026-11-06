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
    finally:
        os.unlink(handle.name)


def main():
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
            elif row["kind"] == "order":
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
