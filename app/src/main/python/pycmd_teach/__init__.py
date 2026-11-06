"""PyCmdTeach - the courses, and the machinery that turns them into lessons.

## Why the lessons are generated

A course here is a list of *topics*: a title, a paragraph, a snippet and what
the snippet prints. Four short things. The lessons the app shows are made from
those four - a read, a "what does this print", a fill-in-the-blank, a put-the
lines-in-order and a write-it-yourself - which is how twenty-six languages end
up with a few thousand lessons between them without anybody typing a few
thousand lessons.

That is a real design decision and not a shortcut, because it is also what
keeps the courses *correct*. Every snippet in here is the single source for
five different exercises, so a snippet that is right is right five times, and a
snippet that is wrong is obviously wrong the first time anybody runs it. Five
hand-written exercises per topic would be five places for the output to drift.

## The one thing that is not generated

Grading. For the languages PyCmd can actually run - Python, C, Rust and Go -
"write a program that prints 7" is marked by running what you wrote and looking
at what came out, in the same interpreters the Console tab uses. Nothing is
compared to a model answer, so any program that prints 7 is a pass. For the
languages the app can only edit, the answer is compared with the topic's
snippet after both have had their whitespace flattened, and the lesson says so
rather than pretending.

## Progress

One JSON file in the app's own storage. Lesson ids are built from the topic's
position in its unit, so adding a topic to the end of a unit does not move
anybody's finished lessons; inserting one in the middle does, which is why new
material goes on the end.
"""

from __future__ import annotations

import io
import json
import os
import random
import re
import sys
import tempfile
import time

__all__ = [
    "configure", "catalogue", "course", "lesson", "check", "complete",
    "progress", "reset", "snippet", "search", "totals",
]

# ---------------------------------------------------------------- the DSL


class Unit:
    """A marker in a topic list: everything after it belongs to this unit."""

    __slots__ = ("title", "goal")

    def __init__(self, title: str, goal: str = "") -> None:
        self.title = title
        self.goal = goal


class Topic:
    """One idea, and the four things needed to teach it."""

    __slots__ = ("title", "teach", "code", "out", "note")

    def __init__(self, title: str, teach: str, code: str, out: str = "", note: str = "") -> None:
        self.title = title
        self.teach = teach
        self.code = code.strip("\n")
        self.out = out
        self.note = note


def U(title: str, goal: str = "") -> Unit:
    return Unit(title, goal)


def T(title: str, teach: str, code: str, out: str = "", note: str = "") -> Topic:
    return Topic(title, teach, code, out, note)


class Course:
    """A language's course: a name, a blurb and a flat list of units and topics."""

    __slots__ = ("id", "name", "blurb", "extension", "graded", "topics", "_units")

    def __init__(self, cid, name, blurb, extension, graded, topics):
        self.id = cid
        self.name = name
        self.blurb = blurb
        self.extension = extension
        # "run" when the app can execute the language and mark by output,
        # "text" when it can only compare what you wrote with the snippet.
        self.graded = graded
        self.topics = topics
        self._units = None

    @property
    def units(self):
        """The topics grouped under their unit markers."""
        if self._units is None:
            out = []
            current = None
            for entry in self.topics:
                if isinstance(entry, Unit):
                    current = {"title": entry.title, "goal": entry.goal, "topics": []}
                    out.append(current)
                else:
                    if current is None:
                        current = {"title": "Basics", "goal": "", "topics": []}
                        out.append(current)
                    current["topics"].append(entry)
            self._units = out
        return self._units


# The courses, imported from the four modules they are written in. Split by
# family rather than alphabetically so that a language's neighbours in the file
# are the ones its snippets most resemble.
def _load_courses():
    from . import courses_core, courses_systems, courses_script, courses_markup

    rows = []
    for module in (courses_core, courses_systems, courses_script, courses_markup):
        rows.extend(module.COURSES)
    return {course.id: course for course in rows}


_COURSES = None


def _courses():
    global _COURSES
    if _COURSES is None:
        _COURSES = _load_courses()
    return _COURSES


# ------------------------------------------------------------- lesson making

#: The lesson kinds a topic can produce, in the order they are shown.
KINDS = ("read", "predict", "fill", "order", "write")

_BLANK = "____"

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def _seed(*parts) -> random.Random:
    """A generator that gives the same answer every time it is asked.

    The shuffle in an ordering exercise has to be stable: a lesson that
    reshuffles itself on every visit is one somebody can finish twice by
    accident, and the progress file would have no idea which it was.
    """
    return random.Random(" / ".join(str(p) for p in parts))


def _lines(code: str):
    return [line for line in code.split("\n") if line.strip()]


def _fill_target(code: str, rng: random.Random):
    """Which word to blank out, and what is left.

    Words shorter than two characters and the handful that appear everywhere
    are skipped: blanking the `x` in `x = 5` teaches nothing, and four options
    that are all `x` is not a question.
    """
    skip = {"a", "i", "x", "n", "s"}
    words = [w for w in _TOKEN.findall(code) if len(w) > 2 and w.lower() not in skip]
    if not words:
        return None, code
    # The most interesting word is usually not the first one, which tends to be
    # the variable being introduced.
    word = words[len(words) // 2] if len(words) > 2 else words[0]
    index = code.find(word)
    if index < 0:
        return None, code
    return word, code[:index] + _BLANK + code[index + len(word):]


def _pool(course: Course, kind: str):
    """Plausible wrong answers, taken from elsewhere in the same course.

    Distractors from the same language are the point. "Which of these four
    prints a list" is a real question when all four are Python; it is not a
    question when three of them are obviously Go.
    """
    out = []
    for unit in course.units:
        for topic in unit["topics"]:
            if kind == "out" and topic.out:
                out.append(topic.out)
            elif kind == "token":
                out.extend(w for w in _TOKEN.findall(topic.code) if len(w) > 2)
    seen = []
    for item in out:
        if item not in seen:
            seen.append(item)
    return seen


def _options(correct: str, pool, rng: random.Random, count: int = 4):
    """[correct] plus up to three others from [pool], shuffled."""
    others = [item for item in pool if item != correct]
    rng.shuffle(others)
    chosen = [correct] + others[: max(0, count - 1)]
    # Fewer than two options is not a choice; fall back to a true/false shape.
    if len(chosen) < 2:
        chosen.append("nothing is printed")
    rng.shuffle(chosen)
    return chosen


def _topic_lessons(course: Course, unit_index: int, topic_index: int, topic: Topic):
    """Every lesson one topic produces, as dicts the app can show."""
    base = f"{unit_index}.{topic_index}"
    rng = _seed(course.id, base)
    made = []

    made.append({
        "id": f"{base}.read",
        "kind": "read",
        "title": topic.title,
        "teach": topic.teach,
        "code": topic.code,
        "output": topic.out,
        "note": topic.note,
    })

    if topic.out:
        pool = _pool(course, "out")
        made.append({
            "id": f"{base}.predict",
            "kind": "predict",
            "title": topic.title,
            "prompt": "What does this print?",
            "code": topic.code,
            "options": _options(topic.out, pool, _seed(course.id, base, "predict")),
        })

    word, blanked = _fill_target(topic.code, rng)
    if word:
        pool = _pool(course, "token")
        made.append({
            "id": f"{base}.fill",
            "kind": "fill",
            "title": topic.title,
            "prompt": "Which word belongs in the gap?",
            "code": blanked,
            "options": _options(word, pool, _seed(course.id, base, "fill")),
        })

    rows = _lines(topic.code)
    if len(rows) >= 3:
        shuffled = list(rows)
        shuffle = _seed(course.id, base, "order")
        # Shuffled until it is actually shuffled: a random order that comes out
        # as the right one is a lesson that is already finished.
        for _ in range(8):
            shuffle.shuffle(shuffled)
            if shuffled != rows:
                break
        made.append({
            "id": f"{base}.order",
            "kind": "order",
            "title": topic.title,
            "prompt": "Put the lines in order.",
            "lines": shuffled,
        })

    made.append({
        "id": f"{base}.write",
        "kind": "write",
        "title": topic.title,
        "prompt": (
            f"Write it yourself. {topic.teach}"
            if not topic.out else
            f"Write {course.name} that prints:\n{topic.out}"
        ),
        "starter": "",
        "output": topic.out,
        "graded": course.graded if topic.out else "text",
        "extension": course.extension,
    })

    return made


def _course_tree(course: Course):
    """The whole course as units of lessons. Built once and cached."""
    cached = getattr(course, "_tree", None)
    if cached is not None:
        return cached
    tree = []
    for unit_index, unit in enumerate(course.units):
        lessons = []
        for topic_index, topic in enumerate(unit["topics"]):
            lessons.extend(_topic_lessons(course, unit_index, topic_index, topic))
        tree.append({"title": unit["title"], "goal": unit["goal"], "lessons": lessons})
    try:
        object.__setattr__(course, "_tree", tree)
    except AttributeError:
        # Course uses __slots__; the cache lives in a dict instead.
        _TREES[course.id] = tree
    return tree


_TREES: dict = {}


def _tree(course: Course):
    if course.id in _TREES:
        return _TREES[course.id]
    tree = _course_tree(course)
    _TREES[course.id] = tree
    return tree


def _find(course: Course, lesson_id: str):
    for unit in _tree(course):
        for row in unit["lessons"]:
            if row["id"] == lesson_id:
                return row
    return None


# ----------------------------------------------------------------- progress

_storage = ""


def configure(storage_dir: str) -> str:
    """Where progress is kept. Called once at start-up."""
    global _storage
    _storage = storage_dir or ""
    if _storage:
        try:
            os.makedirs(_storage, exist_ok=True)
        except OSError:
            pass
    return _storage


def _progress_path() -> str:
    return os.path.join(_storage or tempfile.gettempdir(), "progress.json")


_DEFAULT = {"done": {}, "xp": 0, "streak": 0, "last_day": "", "best_streak": 0}


def _read_progress() -> dict:
    try:
        with open(_progress_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return dict(_DEFAULT, done={})
    if not isinstance(data, dict):
        return dict(_DEFAULT, done={})
    out = dict(_DEFAULT)
    out.update({k: v for k, v in data.items() if k in _DEFAULT})
    if not isinstance(out.get("done"), dict):
        out["done"] = {}
    return out


def _write_progress(data: dict) -> None:
    path = _progress_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Written beside and moved into place: a half-written progress file is
        # a reset course, and nobody would believe it was their own fault.
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        os.replace(temporary, path)
    except OSError:
        pass


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _yesterday() -> str:
    return time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))


def _done_set(data: dict, course_id: str):
    rows = data["done"].get(course_id)
    return set(rows) if isinstance(rows, list) else set()


# -------------------------------------------------------------------- the API


def catalogue() -> list:
    """Every course, with how far through it you are."""
    data = _read_progress()
    rows = []
    for course in _courses().values():
        total = sum(len(unit["lessons"]) for unit in _tree(course))
        done = len(_done_set(data, course.id) & {
            row["id"] for unit in _tree(course) for row in unit["lessons"]
        })
        rows.append({
            "id": course.id,
            "name": course.name,
            "blurb": course.blurb,
            "extension": course.extension,
            "graded": course.graded,
            "lessons": total,
            "units": len(_tree(course)),
            "done": done,
        })
    rows.sort(key=lambda row: (-row["lessons"], row["name"]))
    return rows


def totals() -> dict:
    """One line for the top of the tab."""
    data = _read_progress()
    lessons = 0
    done = 0
    for course in _courses().values():
        ids = {row["id"] for unit in _tree(course) for row in unit["lessons"]}
        lessons += len(ids)
        done += len(_done_set(data, course.id) & ids)
    return {
        "courses": len(_courses()),
        "lessons": lessons,
        "done": done,
        "xp": int(data.get("xp", 0)),
        "streak": int(data.get("streak", 0)),
        "best_streak": int(data.get("best_streak", 0)),
        "today": data.get("last_day", "") == _today(),
    }


def course(course_id: str) -> dict:
    """A course's units and the titles of their lessons."""
    found = _courses().get(course_id)
    if found is None:
        return {"ok": False, "error": f"no course called {course_id}"}
    data = _read_progress()
    done = _done_set(data, course_id)
    units = []
    for unit in _tree(found):
        units.append({
            "title": unit["title"],
            "goal": unit["goal"],
            "lessons": [
                {
                    "id": row["id"],
                    "kind": row["kind"],
                    "title": row["title"],
                    "done": row["id"] in done,
                }
                for row in unit["lessons"]
            ],
        })
    total = sum(len(unit["lessons"]) for unit in units)
    return {
        "ok": True,
        "id": found.id,
        "name": found.name,
        "blurb": found.blurb,
        "extension": found.extension,
        "graded": found.graded,
        "units": units,
        "total": total,
        "done": len(done & {row["id"] for u in units for row in u["lessons"]}),
    }


def lesson(course_id: str, lesson_id: str) -> dict:
    """One lesson, ready to show. The answer is not included."""
    found = _courses().get(course_id)
    if found is None:
        return {"ok": False, "error": f"no course called {course_id}"}
    row = _find(found, lesson_id)
    if row is None:
        return {"ok": False, "error": f"no lesson {lesson_id} in {course_id}"}
    out = dict(row)
    out["ok"] = True
    out["course"] = found.id
    out["language"] = found.name
    out["extension"] = found.extension
    # Where this lesson sits, so the player can say "14 of 190" and move on
    # to the next one without asking for the whole course again.
    flat = [r["id"] for unit in _tree(found) for r in unit["lessons"]]
    index = flat.index(lesson_id)
    out["index"] = index
    out["total"] = len(flat)
    out["next"] = flat[index + 1] if index + 1 < len(flat) else ""
    out["previous"] = flat[index - 1] if index > 0 else ""
    data = _read_progress()
    out["done"] = lesson_id in _done_set(data, course_id)
    return out


def snippet(course_id: str, lesson_id: str) -> dict:
    """The lesson's code and a filename for it, for "open this in the editor"."""
    found = _courses().get(course_id)
    if found is None:
        return {"ok": False, "error": f"no course called {course_id}"}
    row = _find(found, lesson_id)
    if row is None:
        return {"ok": False, "error": f"no lesson {lesson_id}"}
    code = row.get("code", "") or ""
    if _BLANK in code:
        code = code.replace(_BLANK, "")
    if not code and row.get("lines"):
        code = "\n".join(row["lines"])
    safe = re.sub(r"[^a-z0-9]+", "_", row["title"].lower()).strip("_") or "lesson"
    return {
        "ok": True,
        "name": f"teach_{found.id}_{safe}{found.extension}",
        "code": code + "\n",
        "language": found.name,
    }


# ------------------------------------------------------------------- marking


def _flatten(text: str) -> str:
    """Whitespace-insensitive, for comparing output and comparing code."""
    return "\n".join(
        " ".join(line.split()) for line in text.strip().split("\n") if line.strip()
    )


#: How long an answer gets before it is stopped, in seconds.
#:
#: Generous for a lesson - the longest snippet in any course runs in
#: milliseconds - and short enough that somebody who typed `while True` gets
#: the tab back rather than a hung screen.
TIME_LIMIT = 5.0

#: And how much it may print. A runaway loop with a `print` in it fills memory
#: long before it fills five seconds.
OUTPUT_LIMIT = 64 * 1024


class _Capped:
    """A text sink that stops accepting once it has enough.

    Not a subclass of StringIO: a cap that can be written past is not a cap,
    and `write` is the only method a snippet's `print` reaches.
    """

    def __init__(self, limit=None) -> None:
        self.parts: list = []
        self.size = 0
        # Read now, not bound as a default: see _Deadline for the same note.
        self.limit = OUTPUT_LIMIT if limit is None else limit
        self.full = False

    def write(self, text) -> int:
        text = text if isinstance(text, str) else str(text)
        if self.full:
            return len(text)
        room = self.limit - self.size
        if len(text) > room:
            self.parts.append(text[:room])
            self.parts.append("\n... and more than it is worth printing.\n")
            self.full = True
            self.size = self.limit
            return len(text)
        self.parts.append(text)
        self.size += len(text)
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def getvalue(self) -> str:
        return "".join(self.parts)


class _Deadline:
    """A trace function that raises once the time is up.

    Python has no way to stop a thread, so an answer with an infinite loop in
    it has to be made to stop itself. A trace function is called on every line
    of every frame started after it is installed, so the next line of the loop
    raises and the exception unwinds out of `exec` like any other.

    The cost is real - tracing makes the snippet several times slower - and
    irrelevant: these are four-line programs, run once, when somebody presses
    a button. It is the same mechanism the console's Stop button uses.

    It does not help against something blocked inside C code with no Python
    line to reach, `time.sleep(10**9)` being the obvious one. Those are caught
    by nothing here, and the user can leave the tab.
    """

    def __init__(self, seconds=None) -> None:
        # Read now rather than bound as a default: a default argument is
        # evaluated once, when the function is defined, so TIME_LIMIT could be
        # changed - by a test, say - and have no effect at all except on the
        # message, which would then be wrong about what happened.
        self.seconds = TIME_LIMIT if seconds is None else seconds
        self.until = time.monotonic() + self.seconds

    def __call__(self, frame, event, arg):
        if time.monotonic() > self.until:
            raise TimeoutError(
                f"it was still running after {self.seconds:g} seconds, so it was stopped"
            )
        return self


def _run_python(source: str) -> tuple:
    """Runs a snippet with its output captured. Returns (output, error)."""
    buffer = _Capped()
    old_out, old_err, old_in = sys.stdout, sys.stderr, sys.stdin
    old_trace = sys.gettrace()
    sys.stdout = buffer
    sys.stderr = buffer
    sys.stdin = io.StringIO("")
    sys.settrace(_Deadline())
    try:
        exec(compile(source, "<lesson>", "exec"), {"__name__": "__main__"})
    except BaseException as error:  # noqa: BLE001
        return buffer.getvalue(), f"{type(error).__name__}: {error}"
    finally:
        sys.settrace(old_trace)
        sys.stdout, sys.stderr, sys.stdin = old_out, old_err, old_in
    return buffer.getvalue(), ""


def _run_through_registry(source: str, extension: str) -> tuple:
    """Runs C, Rust or Go on the interpreters the Console tab uses."""
    from pycmd_langs import registry

    handle = None
    path = ""
    try:
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=extension, delete=False, encoding="utf-8",
        )
        handle.write(source)
        handle.close()
        path = handle.name
        buffer = _Capped()
        # The same deadline as Python's, and for the same reason: the C, Rust
        # and Go interpreters are themselves Python, so a trace function
        # reaches their loops as well as the program's.
        old_trace = sys.gettrace()
        sys.settrace(_Deadline())
        try:
            result = registry.run_file(path, stdout=buffer, stdin=io.StringIO(""))
        finally:
            sys.settrace(old_trace)
        if not result.get("ok"):
            return buffer.getvalue(), result.get("error", "it did not run")
        if result.get("exit"):
            return buffer.getvalue(), f"it exited with status {result['exit']}"
        return buffer.getvalue(), ""
    except BaseException as error:  # noqa: BLE001
        return "", f"{type(error).__name__}: {error}"
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


#: Which extensions can be marked by running them. JavaScript is absent on
#: purpose: the device's own engine runs it, over on the Kotlin side, and this
#: module has no way to reach it.
RUNNABLE = {".py": "python", ".c": "registry", ".rs": "registry", ".go": "registry"}


def check(course_id: str, lesson_id: str, answer: str) -> dict:
    """Marks an attempt. Never throws; a crash here would be a wrong answer."""
    found = _courses().get(course_id)
    if found is None:
        return {"ok": False, "error": f"no course called {course_id}"}
    row = _find(found, lesson_id)
    if row is None:
        return {"ok": False, "error": f"no lesson {lesson_id}"}

    kind = row["kind"]
    answer = answer if isinstance(answer, str) else str(answer)

    if kind == "read":
        return {"ok": True, "right": True, "message": "Read."}

    if kind == "predict":
        right = _flatten(answer) == _flatten(row["options"][_correct_index(found, row)])
        return {
            "ok": True,
            "right": right,
            "message": "That is what it prints." if right else "Not that one.",
            "expected": row["options"][_correct_index(found, row)],
        }

    if kind == "fill":
        want = _fill_answer(found, row)
        right = answer.strip() == want
        return {
            "ok": True,
            "right": right,
            "message": f"`{want}` it is." if right else "Not that word.",
            "expected": want,
        }

    if kind == "order":
        want = _order_answer(found, row)
        got = [line for line in answer.split("\n") if line.strip()]
        right = [" ".join(l.split()) for l in got] == [" ".join(l.split()) for l in want]
        return {
            "ok": True,
            "right": right,
            "message": "In order." if right else "Not quite that order.",
            "expected": "\n".join(want),
        }

    if kind == "write":
        return _check_written(found, row, answer)

    return {"ok": False, "error": f"unknown lesson kind {kind}"}


def _topic_for(course: Course, lesson_id: str):
    """The topic a lesson id came from."""
    unit_index, topic_index = lesson_id.split(".")[:2]
    units = course.units
    try:
        return units[int(unit_index)]["topics"][int(topic_index)]
    except (ValueError, IndexError, KeyError):
        return None


def _correct_index(course: Course, row: dict) -> int:
    topic = _topic_for(course, row["id"])
    want = topic.out if topic else ""
    for index, option in enumerate(row["options"]):
        if option == want:
            return index
    return 0


def _fill_answer(course: Course, row: dict) -> str:
    topic = _topic_for(course, row["id"])
    if topic is None:
        return ""
    word, _ = _fill_target(topic.code, _seed(course.id, row["id"].rsplit(".", 1)[0]))
    return word or ""


def _order_answer(course: Course, row: dict):
    topic = _topic_for(course, row["id"])
    return _lines(topic.code) if topic else []


def _check_written(course: Course, row: dict, answer: str) -> dict:
    """Marks a write-it-yourself lesson, by running it where that is possible."""
    if not answer.strip():
        return {"ok": True, "right": False, "message": "Nothing there yet."}

    topic = _topic_for(course, row["id"])
    wanted = (row.get("output") or "").strip()
    extension = course.extension

    if row.get("graded") == "run" and extension in RUNNABLE and wanted:
        how = RUNNABLE[extension]
        output, error = (
            _run_python(answer) if how == "python"
            else _run_through_registry(answer, extension)
        )
        if error:
            return {
                "ok": True,
                "right": False,
                "message": "It ran, and stopped: " + error.strip().split("\n")[-1],
                "output": output,
                "ran": True,
            }
        if _flatten(output) == _flatten(wanted):
            return {
                "ok": True,
                "right": True,
                "message": "It printed exactly that.",
                "output": output,
                "ran": True,
            }
        return {
            "ok": True,
            "right": False,
            "message": "It ran, but printed something else.",
            "output": output,
            "expected": wanted,
            "ran": True,
        }

    # Nothing to run it with, so the answer is compared with the snippet after
    # both have had their whitespace flattened. The lesson says as much.
    model = topic.code if topic else ""
    right = _flatten(answer) == _flatten(model)
    return {
        "ok": True,
        "right": right,
        "message": "That matches." if right else "Not the same as the answer yet.",
        "expected": model,
        "ran": False,
    }


def complete(course_id: str, lesson_id: str) -> dict:
    """Marks a lesson finished and keeps the streak.

    Idempotent on purpose: finishing a lesson twice is a lesson somebody went
    back to read, not ten more XP.
    """
    found = _courses().get(course_id)
    if found is None:
        return {"ok": False, "error": f"no course called {course_id}"}
    if _find(found, lesson_id) is None:
        return {"ok": False, "error": f"no lesson {lesson_id}"}

    data = _read_progress()
    rows = data["done"].get(course_id)
    rows = list(rows) if isinstance(rows, list) else []
    fresh = lesson_id not in rows
    if fresh:
        rows.append(lesson_id)
        data["done"][course_id] = rows
        data["xp"] = int(data.get("xp", 0)) + 10

    today = _today()
    last = data.get("last_day", "")
    if last != today:
        if last == _yesterday():
            data["streak"] = int(data.get("streak", 0)) + 1
        else:
            data["streak"] = 1
        data["last_day"] = today
        data["best_streak"] = max(int(data.get("best_streak", 0)), data["streak"])
    _write_progress(data)
    return {"ok": True, "fresh": fresh, **totals()}


def progress() -> dict:
    data = _read_progress()
    return {"ok": True, **totals(), "done": data["done"]}


def reset(course_id: str = "") -> dict:
    """Forgets one course, or everything."""
    data = _read_progress()
    if course_id:
        data["done"].pop(course_id, None)
    else:
        data = dict(_DEFAULT, done={})
    _write_progress(data)
    return {"ok": True, **totals()}


def search(text: str, limit: int = 40) -> list:
    """Lessons whose title or code mentions [text]."""
    needle = (text or "").strip().lower()
    if len(needle) < 2:
        return []
    hits = []
    for course_ in _courses().values():
        for unit in _tree(course_):
            for row in unit["lessons"]:
                haystack = (row.get("title", "") + " " + row.get("code", "") + " " +
                            row.get("teach", "")).lower()
                if needle in haystack:
                    hits.append({
                        "course": course_.id,
                        "language": course_.name,
                        "lesson": row["id"],
                        "kind": row["kind"],
                        "title": row["title"],
                        "unit": unit["title"],
                    })
                    if len(hits) >= limit:
                        return hits
    return hits


# -------------------------------------------------------- the app's one door


def api(name: str, first: str = "", second: str = "", third: str = "") -> str:
    """Everything the Kotlin side calls, as a JSON string.

    One function rather than ten, because every one of them would otherwise
    need its own conversion on the Kotlin side, and Chaquopy's view of a
    Python dict is not JSON - `str()` on one gives single quotes and `True`.
    Encoding here and parsing there means the shape of a reply is decided in
    one place.

    Never raises. A course that cannot be read should show a message in the
    app, not take the tab down with it.
    """
    try:
        if name == "catalogue":
            return json.dumps({"ok": True, "courses": catalogue(), "totals": totals()})
        if name == "course":
            return json.dumps(course(first))
        if name == "lesson":
            return json.dumps(lesson(first, second))
        if name == "check":
            return json.dumps(check(first, second, third))
        if name == "complete":
            return json.dumps(complete(first, second))
        if name == "progress":
            return json.dumps(progress())
        if name == "reset":
            return json.dumps(reset(first))
        if name == "snippet":
            return json.dumps(snippet(first, second))
        if name == "search":
            return json.dumps({"ok": True, "hits": search(first)})
        return json.dumps({"ok": False, "error": f"no such call: {name}"})
    except BaseException as error:  # noqa: BLE001
        return json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"})
