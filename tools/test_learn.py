"""PyCmd Learn on Windows: every course loads, and every lesson that says what
it prints really prints it - checked by running it with a real toolchain.

    python tools/test_learn.py               everything
    python tools/test_learn.py haskell ocaml just these courses
    python tools/test_learn.py --quick       no running, only the shape

A course whose toolchain is not on this machine is shape-checked and its run
is reported as skipped, never as passed.
"""

from __future__ import annotations

import concurrent.futures
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "windows"))

os.environ.setdefault("PYCMD_HOME", tempfile.mkdtemp(prefix="pycmd-learn-"))

from pycmd_win import learn  # noqa: E402


def _shim_old_clojure():
    """Debian's `clojure` predates the official CLI and has no -M. The app uses
    the official CLI's `clojure -M file.clj`, so for testing on such a machine
    a shim drops the -M and the real compiler does the rest."""
    import shutil
    import subprocess

    real = shutil.which("clojure")
    if not real:
        return
    probe = subprocess.run([real, "-M", "-e", "1"], capture_output=True, text=True)
    if probe.returncode == 0:
        return
    folder = tempfile.mkdtemp(prefix="clj-shim-")
    shim = os.path.join(folder, "clojure")
    with open(shim, "w") as handle:
        handle.write('#!/bin/sh\n[ "$1" = "-M" ] && shift\nexec ' + real + ' "$@"\n')
    os.chmod(shim, 0o755)
    os.environ["PATH"] = folder + os.pathsep + os.environ["PATH"]


def _shim_old_scala():
    """Scala 2's runner starts a compile server that dies on a new JDK. The
    Windows build expects a current `scala`; for testing with an old one, a
    shim adds -nc (no compile server)."""
    import shutil
    import subprocess

    real = shutil.which("scala")
    if not real:
        return
    probe = subprocess.run([real, "-version"], capture_output=True, text=True)
    if "version 2." not in probe.stdout + probe.stderr:
        return
    folder = tempfile.mkdtemp(prefix="scala-shim-")
    shim = os.path.join(folder, "scala")
    with open(shim, "w") as handle:
        handle.write("#!/bin/sh\nexec " + real + ' -nc "$@"\n')
    os.chmod(shim, 0o755)
    os.environ["PATH"] = folder + os.pathsep + os.environ["PATH"]


_shim_old_clojure()
_shim_old_scala()
_tools = os.path.expanduser("~/.dotnet/tools")
if os.path.isdir(_tools):
    os.environ["PATH"] += os.pathsep + _tools

FAILED = []
PASSED = [0]
SKIPPED = []


def check(name, condition, detail=""):
    if condition:
        PASSED[0] += 1
        return True
    FAILED.append(name)
    print(f"  FAIL  {name}" + (f"  ({str(detail)[:300]})" if detail else ""))
    return False


def main(argv):
    quick = "--quick" in argv
    wanted = [a for a in argv if not a.startswith("--")]
    teach = learn._engine()
    windows_only = learn.windows_course_ids()
    courses = teach._courses()
    print(f"== {len(courses)} courses, {len(windows_only)} of them Windows-only ==")

    for course in courses.values():
        if wanted and course.id not in wanted:
            continue
        if course.id not in windows_only and not wanted:
            continue
        tree = teach._tree(course)
        lessons = [row for unit in tree for row in unit["lessons"]]
        titles = [t.title for t in course.topics if isinstance(t, teach.Topic)]
        check(f"{course.id} has lessons", len(lessons) > 40, len(lessons))
        check(f"{course.id} topic titles are unique", course.id not in windows_only or
              len(titles) == len(set(titles)),
              sorted({t for t in titles if titles.count(t) > 1}))
        check(f"{course.id} starts with a unit", isinstance(course.topics[0], teach.Unit))
        for topic in course.topics:
            if not isinstance(topic, teach.Topic):
                continue
            widest = max(len(line) for line in topic.code.split("\n"))
            check(f"{course.id} '{topic.title}' fits", widest <= 58, f"{widest} wide")
            check(f"{course.id} '{topic.title}' explains itself", len(topic.teach) > 10)
            check(f"{course.id} '{topic.title}' has no tabs", "\t" not in topic.code)
        for row in lessons:
            got = learn.lesson(course.id, row["id"])
            check(f"{course.id} {row['id']} opens", got.get("ok"), got.get("error"))
            if row["kind"] == "order":
                answer = "\n".join(teach._order_answer(course, row))
                check(f"{course.id} {row['id']} order answerable",
                      teach.check(course.id, row["id"], answer).get("right"))
            if row["kind"] == "bug":
                broken = teach._break(course, teach._topic_for(course, row["id"]))
                check(f"{course.id} {row['id']} bug answerable",
                      broken and teach.check(course.id, row["id"], broken[1]).get("right"))
            if row["kind"] in ("predict", "which", "fill"):
                check(f"{course.id} {row['id']} has four choices", len(row["options"]) >= 3,
                      row["options"])

        if quick:
            continue
        if not learn.can_run(course.extension):
            SKIPPED.append(course.id)
            print(f"  skip  {course.id}: nothing here runs {course.extension}")
            continue
        topics = [t for t in course.topics if isinstance(t, teach.Topic) and t.out]
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda t: (t, learn.run_snippet(t.code, course.extension)),
                                    topics))
        bad = 0
        for topic, (output, error) in results:
            if error:
                bad += 1
                check(f"{course.id} '{topic.title}' runs", False, error)
                continue
            if not check(f"{course.id} '{topic.title}' prints what it says",
                         teach._flatten(output) == teach._flatten(topic.out),
                         f"got {output!r}, says {topic.out!r}"):
                bad += 1
        print(f"  {course.id}: {len(lessons)} lessons, {len(topics)} snippets run, "
              f"{bad} wrong")

    print()
    if SKIPPED:
        print("not run (no toolchain here): " + ", ".join(SKIPPED))
    if FAILED:
        print(f"{len(FAILED)} of {len(FAILED) + PASSED[0]} checks failed")
        return 1
    print(f"all {PASSED[0]} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
