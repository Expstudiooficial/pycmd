"""PyCmd Learn on Windows: the phone's lessons, more languages, and real marking.

The lessons themselves are the shared engine's (`pycmd_teach`), unchanged, so
a lesson finished on Windows is the same lesson the phone has. Two things are
added here:

* **More courses.** The phone can only run Python, C, Rust and Go, so it
  teaches the languages it can show. A PC can run anything that is installed,
  so the Windows build carries courses the phone does not - C#, Haskell,
  Elixir, COBOL and the rest - from `pycmd_win/courses/`.
* **Marking by running.** On the phone a Kotlin answer can only be compared
  with the model answer as text. Here, if Kotlin is installed, the answer is
  compiled and run and marked by what it prints - which is the only marking
  that does not punish a correct answer written differently.

The runner is strict on purpose: the program's own stdout is what is
compared, never the compiler's chatter, and every run has a time limit, so a
lesson cannot hang the tab with an infinite loop.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from . import langs, store, toolchains

WINDOWS = os.name == "nt"

#: Courses only this build carries, by module name inside pycmd_win.courses.
WINDOWS_COURSES = (
    "functional", "dotnet", "beam", "jvm", "data", "classic", "scripting",
)

RUN_LIMIT = 20.0
BUILD_LIMIT = 90.0
OUTPUT_LIMIT = 64 * 1024

_teach = None
_lock = threading.RLock()


def _engine():
    """The shared engine, with the Windows courses and the runner plugged in."""
    global _teach
    with _lock:
        if _teach is not None:
            return _teach
        engine = store.engine_path()
        if engine not in sys.path:
            sys.path.insert(0, engine)
        import pycmd_teach

        names = []
        for name in WINDOWS_COURSES:
            try:
                module = importlib.import_module(f"{__package__}.courses.{name}")
            except ImportError:
                continue
            alias = f"courses_win_{name}"
            sys.modules[f"pycmd_teach.{alias}"] = module
            names.append(alias)
        pycmd_teach.COURSE_MODULES_MORE = tuple(names)
        pycmd_teach._COURSES = None
        pycmd_teach.EXTERNAL_RUNNER = run_snippet
        pycmd_teach.configure(store.folder("learn"))
        _teach = pycmd_teach
        return _teach


def _call(name: str, first: str = "", second: str = "", third: str = "") -> dict:
    reply = _engine().api(name, str(first), str(second), str(third))
    try:
        return json.loads(reply)
    except ValueError:
        return {"ok": False, "error": "the lesson engine answered something unreadable"}


# ---------------------------------------------------------------------------
# Running a snippet with whatever is installed
# ---------------------------------------------------------------------------

def _no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0


#: File names some toolchains insist on: Java wants the class name, COBOL and
#: Pascal do not care, C# gets a project written beside it.
_NAMES = {".java": "Main.java", ".kt": "main.kt", ".scala": "main.scala",
          ".erl": "main.erl", ".hs": "main.hs", ".cs": "Program.cs"}


#: Phone courses whose snippets are checked on real toolchains as whole
#: programs, so marking them by running is fair. Kotlin and Swift are not on
#: the list: their lessons have never been run on a real compiler, and a
#: correct answer must never be marked wrong by a fragment that cannot run.
VERIFIED_PHONE = {".js", ".ts", ".rb", ".php", ".lua", ".java", ".cpp", ".sh", ".sql"}


def _run_marked(extension: str) -> bool:
    if extension in VERIFIED_PHONE:
        return True
    _engine()
    for name in WINDOWS_COURSES:
        module = sys.modules.get(f"pycmd_teach.courses_win_{name}")
        if any(c.extension == extension for c in getattr(module, "COURSES", [])):
            return True
    return False


def can_run(extension: str) -> bool:
    """Whether answers in this language can be marked by running them here."""
    if not _run_marked(extension):
        return False
    return can_execute(extension)


def can_execute(extension: str) -> bool:
    """Whether anything installed here runs this extension at all."""
    language = langs.for_path("snippet" + extension)
    if not language.get("runnable", True) and language.get("mode") != "run":
        return False
    for chain in toolchains.for_language(language["id"]):
        if extension in chain.refuses:
            continue
        if toolchains.detect(chain.id).get("path"):
            return True
    return False


def _capped(text: str) -> str:
    return text if len(text) <= OUTPUT_LIMIT else text[:OUTPUT_LIMIT] + "\n[output cut off]"


def run_snippet(source: str, extension: str) -> tuple:
    """Builds and runs a snippet. Returns (stdout, error) - error "" when it worked."""
    language = langs.for_path("snippet" + extension)
    folder = os.path.join(store.folder("cache"), "learn-run", uuid.uuid4().hex[:12])
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, _NAMES.get(extension, "main" + extension))
    if extension == ".erl" and not source.lstrip().startswith(("#!", "-module")):
        # escript throws a file's first line away as if it were a #! line,
        # so a lesson that starts with main(_) would lose it. Give it one.
        source = "#!/usr/bin/env escript\n" + source
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(source if source.endswith("\n") else source + "\n")
        plan = toolchains.plan_for(path, language["id"])
        if not plan.get("ok"):
            return "", plan.get("error", "nothing here runs this")
        from . import runner

        runner._ensure_project(path, language["id"], plan["toolchain"], lambda text: None)
        commands = plan["commands"]
        env = _neutral_env()
        if plan["toolchain"] == "nim":
            # Nim caches builds by module name, and every snippet is main.nim:
            # two at once would build into each other. Each gets its own.
            commands = [list(c[:2]) + [f"--nimcache:{os.path.join(folder, 'nimcache')}"]
                        + list(c[2:]) for c in commands]
        for index, command in enumerate(commands):
            last = index == len(commands) - 1
            limit = RUN_LIMIT if (last and plan.get("builds")) else BUILD_LIMIT
            try:
                done = subprocess.run(
                    command, cwd=folder, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=limit, stdin=subprocess.DEVNULL, env=env,
                    creationflags=_no_window())
            except subprocess.TimeoutExpired:
                return "", f"it was still running after {limit:g} seconds, so it was stopped"
            except OSError as error:
                return "", f"could not start {command[0]}: {error}"
            if done.returncode != 0:
                said = (done.stderr or done.stdout or "").strip()
                where = "the build" if not last else "it"
                return (_capped(done.stdout) if last else ""), (
                    f"{where} exited with {done.returncode}" + (f": {said[-600:]}" if said else ""))
            if last:
                return _capped(_clean(done.stdout, plan["toolchain"])), ""
        return "", "nothing ran"
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _neutral_env() -> dict:
    """An environment where 3.5 prints as 3.5 on every Windows.

    On a German or French Windows, C# prints 3.5 as "3,5" and Java formats
    "%.2f" as "3,14" - so a lesson answered correctly would be marked wrong.
    Lessons are about the language, not the locale, so runs use the invariant
    culture: .NET's invariant-globalisation switch, and an English locale for
    the JVM.
    """
    env = dict(os.environ)
    env.update({
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_NOLOGO": "1",
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        "DOTNET_SYSTEM_GLOBALIZATION_INVARIANT": "1",
        "LC_ALL": "C.UTF-8" if not WINDOWS else env.get("LC_ALL", ""),
        "PYTHONIOENCODING": "utf-8",
    })
    java = env.get("JAVA_TOOL_OPTIONS", "")
    if "-Duser.language" not in java:
        env["JAVA_TOOL_OPTIONS"] = (java + " -Duser.language=en -Duser.country=US").strip()
    return {k: v for k, v in env.items() if v != ""}


def _clean(text: str, toolchain: str) -> str:
    """Drops the lines some runners print about themselves before the program."""
    if toolchain in ("dotnet",):
        lines = [l for l in text.splitlines(True)
                 if not l.startswith(("Welcome to .NET", "Build succeeded", "  Determining"))]
        return "".join(lines)
    return text


run_snippet.can = can_run


def runners() -> dict:
    """Which courses can be marked by running, and which just can be tried."""
    engine = _engine()
    out = {}
    for course in engine._courses().values():
        ext = course.extension
        out[course.id] = {
            "marked": ext in engine.RUNNABLE or can_run(ext),
            "tryable": ext in engine.RUNNABLE or can_execute(ext),
        }
    return out


# ---------------------------------------------------------------------------
# What the screen calls
# ---------------------------------------------------------------------------

#: The phone's blurbs describe the phone ("runs in the device's own engine").
#: On a PC they would be wrong, so these say what is true here.
PC_BLURBS = {
    "python": "The language PyCmd is built on. Runs here, and is marked by running it.",
    "javascript": "The web's language. Runs with Node, Deno or Bun when one is installed.",
    "typescript": "JavaScript with types. Runs with Bun, Deno or tsc and Node.",
    "c": "Runs on the C interpreter PyCmd carries - or GCC, Clang or Zig if you have them.",
    "rust": "Runs on the Rust interpreter PyCmd carries, or rustc when it is installed.",
    "go": "Runs on the Go interpreter PyCmd carries, or the real Go toolchain.",
    "cpp": "Compiled with g++ or clang++ when installed, and marked by what it prints.",
    "java": "Single-file programs run straight from source with a JDK.",
    "kotlin": "Taught by reading and writing. The Toolchains tab installs kotlinc to run it.",
    "swift": "Taught by reading and writing. Swift on Windows is a separate install.",
    "ruby": "Runs with Ruby when it is installed - marked by what your answer prints.",
    "php": "Runs with PHP when installed. The Toolchains tab can download it directly.",
    "lua": "Small, fast and embeddable. Runs with lua when installed.",
    "shell": "Bash scripts. Run with Git for Windows' bash, which PyCmd can install.",
    "sql": "SQLite: real queries on a real database, marked by their results.",
}


def catalogue() -> dict:
    reply = _call("catalogue")
    if reply.get("ok"):
        for row in reply.get("courses", []):
            row["blurb"] = PC_BLURBS.get(row["id"], row["blurb"])
            row["runsHere"] = row["extension"] in _engine().RUNNABLE or can_run(row["extension"])
            row["windowsOnly"] = row["id"] in windows_course_ids()
    return reply


def windows_course_ids() -> set:
    _engine()
    ids = set()
    for name in WINDOWS_COURSES:
        module = sys.modules.get(f"pycmd_teach.courses_win_{name}")
        for course in getattr(module, "COURSES", []):
            ids.add(course.id)
    return ids


def course(course_id: str) -> dict:
    reply = _call("course", course_id)
    if reply.get("ok"):
        reply["blurb"] = PC_BLURBS.get(course_id, reply.get("blurb", ""))
        reply["runsHere"] = reply["extension"] in _engine().RUNNABLE or can_run(reply["extension"])
    return reply


def lesson(course_id: str, lesson_id: str) -> dict:
    return _call("lesson", course_id, lesson_id)


def check(course_id: str, lesson_id: str, answer: str) -> dict:
    return _call("check", course_id, lesson_id, answer)


def complete(course_id: str, lesson_id: str) -> dict:
    return _call("complete", course_id, lesson_id)


def snippet(course_id: str, lesson_id: str) -> dict:
    return _call("snippet", course_id, lesson_id)


def search(text: str) -> dict:
    return _call("search", text)


def review() -> dict:
    return _call("review")


def goal(count) -> dict:
    return _call("goal", str(count))


def reset(course_id: str = "") -> dict:
    return _call("reset", course_id)


def try_code(course_id: str, code: str) -> dict:
    """Runs whatever is in the lesson's code box, for "try it yourself"."""
    engine = _engine()
    found = engine._courses().get(course_id)
    if found is None:
        return {"ok": False, "error": f"no course called {course_id}"}
    extension = found.extension
    started = time.time()
    if extension == ".py":
        output, error = engine._run_python(code)
    elif extension in engine.RUNNABLE:
        output, error = engine._run_through_registry(code, extension)
    elif can_execute(extension):
        output, error = run_snippet(code, extension)
    else:
        language = langs.for_path("x" + extension)
        return {"ok": False, "reason": "missing", "language": language.get("name", extension),
                "error": f"Nothing installed here runs {found.name}. The Toolchains tab can "
                         "install it."}
    return {"ok": True, "output": output, "error": error,
            "seconds": round(time.time() - started, 2)}
