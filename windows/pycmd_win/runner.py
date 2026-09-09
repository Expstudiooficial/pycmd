"""Pressing Run, on Windows.

One job: take a file, work out what runs it, run it, and stream what it says
back a line at a time so the console fills as the program talks rather than
all at once when it stops.

Three things it does that are worth saying out loud:

* **It falls back.** C, Go, Rust and JavaScript have interpreters built into
  PyCmd - the ones the phone build uses, because Android forbids running code
  an app compiled itself. On Windows the real toolchain is tried first and the
  interpreter is what you get when there isn't one. So a fresh install runs a
  .go file on day one, and installing Go makes the same file run on the real
  thing. Nothing about that is hidden: the console says which one ran it.

* **It kills the whole tree.** A build step that spawns a compiler that spawns
  a linker leaves three processes, and `terminate()` on the first one leaves
  the other two. On Windows the job is given to `taskkill /T`.

* **It never uses a shell.** Every command is a list of arguments. A workspace
  under `C:\\Users\\Some One\\Documents` is the normal case, and `shell=True`
  would make it a bug report.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time

from . import langs, toolchains

WINDOWS = os.name == "nt"

# A compile step gets longer than a run: a first kotlinc build really can take
# half a minute, and killing it at ten seconds would look like a broken app.
BUILD_TIMEOUT = 300.0
RUN_TIMEOUT = 0.0  # no limit; the user has a Stop button


class Run:
    """One running program, and the handle to stop it."""

    def __init__(self, run_id: str, path: str, language: str):
        self.id = run_id
        self.path = path
        self.language = language
        self.started_at = time.time()
        self.finished_at = 0.0
        self.exit_code = None
        self.toolchain = ""
        self.stopped = False
        self.error = ""
        self._process = None
        self._lock = threading.Lock()

    def attach(self, process) -> None:
        with self._lock:
            self._process = process

    def stop(self) -> bool:
        """Ends it, and everything it started."""
        with self._lock:
            process = self._process
            self.stopped = True
        if process is None or process.poll() is not None:
            return False
        _kill_tree(process)
        return True

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "path": self.path,
            "language": self.language,
            "toolchain": self.toolchain,
            "running": self.finished_at == 0.0,
            "exit": self.exit_code,
            "stopped": self.stopped,
            "error": self.error,
            "seconds": round((self.finished_at or time.time()) - self.started_at, 2),
        }


def _kill_tree(process) -> None:
    """Ends a process and its children.

    `Popen.terminate` ends the one process we started, which for a build is
    often a launcher that has already handed the work to something else. On
    Windows `taskkill /T` walks the tree; elsewhere the process group does.
    """
    try:
        if WINDOWS:
            # Bounded, like every other call in this app. taskkill can itself
            # block on a wedged process tree, and this one is on the path of
            # the Stop button - a Stop that hangs is worse than no Stop.
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            os.killpg(os.getpgid(process.pid), 15)
    except Exception:  # noqa: BLE001 - it may already be gone, which is fine
        try:
            process.terminate()
        except Exception:  # noqa: BLE001
            pass


def _spawn(command, cwd, stdin_text=None):
    kwargs = {
        "cwd": cwd or None,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
        "text": True,
        "bufsize": 1,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if WINDOWS:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(command, **kwargs)


def _pump(process, write) -> int:
    """Reads a program's output as it appears and hands it on a line at a time."""
    if process.stdout is not None:
        for line in process.stdout:
            write(line)
    return process.wait()


# Which project file each .NET language wants beside a loose source file.
_DOTNET_PROJECT = {
    "csharp": ".csproj",
    "visualbasic": ".vbproj",
    "fsharp": ".fsproj",
}


def _ensure_project(path: str, language_id: str, toolchain: str, write) -> None:
    """Gives a lone .cs, .vb or .fs file the project file the SDK insists on.

    `dotnet run` wants a project, and somebody who has just written twelve
    lines of C# has not got one. Writing the smallest possible one beside the
    file is friendlier than an error explaining MSBuild.

    F# is the awkward one twice over. Its SDK does not glob sources the way
    C#'s does - order is part of the language there, so the project has to name
    the file - and an .fsx is a script that has no project at all. The second
    is handled a layer up, in the toolchain table: .fsx never reaches here,
    because `dotnet` refuses that extension and F# Interactive takes it.

    Only the SDK is given a project. F# Interactive needs none, and leaving a
    stray .fsproj beside somebody's script would change what `dotnet run` did
    in that folder afterwards.
    """
    if toolchain != "dotnet":
        return
    suffix = _DOTNET_PROJECT.get(language_id)
    if not suffix:
        return
    folder = os.path.dirname(path)
    existing = [n for n in os.listdir(folder) if n.lower().endswith(suffix)]
    if existing:
        return
    source = os.path.basename(path)
    name = os.path.splitext(source)[0] + suffix
    if language_id == "fsharp":
        body = (
            "  <PropertyGroup>\n"
            "    <OutputType>Exe</OutputType>\n"
            "    <TargetFramework>net8.0</TargetFramework>\n"
            "  </PropertyGroup>\n"
            "  <ItemGroup>\n"
            f'    <Compile Include="{source}" />\n'
            "  </ItemGroup>\n"
        )
    else:
        body = (
            "  <PropertyGroup>\n"
            "    <OutputType>Exe</OutputType>\n"
            "    <TargetFramework>net8.0</TargetFramework>\n"
            "    <Nullable>enable</Nullable>\n"
            "    <ImplicitUsings>enable</ImplicitUsings>\n"
            "  </PropertyGroup>\n"
        )
    project = '<Project Sdk="Microsoft.NET.Sdk">\n' + body + "</Project>\n"
    try:
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            handle.write(project)
        write(f"[PyCmd] wrote {name}, which the .NET SDK needs to run a loose file\n")
    except OSError as error:
        write(f"[PyCmd] could not write {name}: {error}\n")


# ---------------------------------------------------------------------------
# The interpreters PyCmd carries, used when nothing is installed
# ---------------------------------------------------------------------------

BUILT_IN = {"c": "C", "go": "Go", "rust": "Rust", "javascript": "JavaScript"}


def _run_built_in(path: str, language_id: str, write) -> dict:
    """Falls back to the interpreter in the box."""
    try:
        from pycmd_langs import registry as shared
    except ImportError as error:
        return {"ok": False, "error": f"the built-in interpreters are missing: {error}"}

    class _Sink:
        def write(self, text):
            write(text)

        def flush(self):
            pass

    write(f"[PyCmd] no {langs.by_id(language_id).name} toolchain found - "
          f"running on the interpreter built into PyCmd\n")
    try:
        result = shared.run_file(path, stdout=_Sink())
    except Exception as error:  # noqa: BLE001 - somebody's program may do anything
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    return {"ok": bool(result.get("ok")), "error": result.get("error", ""),
            "exit": result.get("exit", 0), "built_in": True}


# ---------------------------------------------------------------------------
# The public call
# ---------------------------------------------------------------------------

_runs: dict[str, Run] = {}
_next_id = [0]
_id_lock = threading.Lock()


def _new_id() -> str:
    with _id_lock:
        _next_id[0] += 1
        return f"run-{_next_id[0]}"


def active() -> list:
    return [run.as_dict() for run in _runs.values() if run.finished_at == 0.0]


def stop(run_id: str) -> bool:
    run = _runs.get(run_id)
    return bool(run and run.stop())


def stop_all() -> int:
    return sum(1 for run in list(_runs.values()) if run.stop())


def run_command(argv, write, cwd: str = "", run_id: str = "") -> dict:
    """Runs any program on the PATH, streaming what it says.

    The console is a console. Typing `go version` or `git status` or
    `npm run build` should do what those words do, and before this it did
    nothing at all - the line went to the Python interpreter, which has no
    opinion about `go`, and the answer was silence.

    A list of arguments, never a string through a shell: a workspace path with
    a space in it is the normal case here.
    """
    if not argv:
        return {"ok": False, "error": "nothing to run"}
    program = shutil.which(argv[0])
    if not program:
        return {"ok": False, "reason": "not-found",
                "error": f"{argv[0]} is not a program on this machine"}

    run = Run(run_id or _new_id(), argv[0], "shell")
    _runs[run.id] = run
    try:
        process = _spawn([program] + list(argv[1:]), cwd or os.getcwd())
    except OSError as error:
        run.error = str(error)
        return {"ok": False, "error": f"could not start {argv[0]}: {error}",
                "run": run.as_dict()}

    run.attach(process)
    code = _pump(process, write)
    run.exit_code = code
    run.finished = time.time()
    if code != 0:
        write(f"[PyCmd] {argv[0]} exited {code}\n")
    return {"ok": code == 0, "exit": code, "run": run.as_dict()}


def run_file(path: str, write, prefer: str = "", run_id: str = "") -> dict:
    """Runs one file, streaming its output through `write`.

    Blocking: the caller is expected to be on a thread of its own, which is
    how the app keeps its window responsive while somebody's loop runs.
    """
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        return {"ok": False, "error": f"{path} is not a file"}

    language = langs.for_path(path)
    language_id = language["id"]
    run = Run(run_id or _new_id(), path, language_id)
    _runs[run.id] = run

    try:
        plan = toolchains.plan_for(path, language_id, prefer=prefer)

        if not plan.get("ok"):
            if language_id in BUILT_IN:
                result = _run_built_in(path, language_id, write)
                run.toolchain = "built-in"
                run.exit_code = result.get("exit", 0 if result.get("ok") else 1)
                run.error = result.get("error", "")
                if result.get("error"):
                    write(f"\n[PyCmd] {result['error']}\n")
                return {**result, "run": run.as_dict()}

            write(f"[PyCmd] {plan.get('error', 'nothing here runs this')}\n")
            for row in plan.get("install", [])[:4]:
                install = row["install"]
                line = install.get("winget") or install.get("scoop") or install.get("choco")
                if line:
                    write(f"[PyCmd]   {row['name']}: {line}\n")
                elif install.get("site"):
                    write(f"[PyCmd]   {row['name']}: {install['site']}\n")
            run.error = plan.get("error", "")
            run.exit_code = 1
            return {"ok": False, "error": run.error, "install": plan.get("install", []),
                    "run": run.as_dict()}

        run.toolchain = plan["toolchain"]
        _ensure_project(path, language_id, plan["toolchain"], write)

        version = f" {plan['version']}" if plan.get("version") else ""
        write(f"[PyCmd] {language['name']} via {plan['name']}{version}\n")

        commands = plan["commands"]
        for index, command in enumerate(commands):
            building = plan["builds"] and index == 0
            if building:
                write(f"[PyCmd] building...\n")
            try:
                process = _spawn(command, plan["cwd"])
            except FileNotFoundError:
                message = f"{command[0]} is not there any more - was it uninstalled?"
                write(f"[PyCmd] {message}\n")
                run.error = message
                run.exit_code = 127
                return {"ok": False, "error": message, "run": run.as_dict()}
            except OSError as error:
                write(f"[PyCmd] could not start it: {error}\n")
                run.error = str(error)
                run.exit_code = 1
                return {"ok": False, "error": str(error), "run": run.as_dict()}

            run.attach(process)
            code = _pump(process, write)
            run.exit_code = code

            if run.stopped:
                write("\n[PyCmd] stopped.\n")
                return {"ok": False, "stopped": True, "run": run.as_dict()}
            if code != 0:
                what = "the build" if building else "it"
                write(f"\n[PyCmd] {what} exited with {code}.\n")
                run.error = f"exit {code}"
                return {"ok": False, "exit": code, "run": run.as_dict()}
            if building and plan.get("output") and not os.path.exists(plan["output"]):
                message = "the build reported success but produced nothing to run"
                write(f"[PyCmd] {message}.\n")
                run.error = message
                return {"ok": False, "error": message, "run": run.as_dict()}

        return {"ok": True, "exit": 0, "toolchain": plan["toolchain"],
                "run": run.as_dict()}
    finally:
        run.finished_at = time.time()
