"""What is actually installed on this machine, and how to run code with it.

This is the file that makes the Windows build different from the phone.

On Android an app may not execute code it generated itself - that has been
true since API 29 - so PyCmd ships *interpreters* for C, Go and Rust written
in Python, and everything else that needs a compiler is honestly labelled "you
can edit and serve this, but not run it". Windows has no such rule. If a
toolchain is on the PATH, PyCmd can call it, and a `.go` file runs on the real
`go` rather than on our interpreter.

So this module answers three questions and nothing else:

* **What is here?** [detect] runs each toolchain's version command once and
  remembers what came back.
* **How do I run this file?** [plan_for] turns a path into a list of commands -
  one for a language that runs straight off, two for one that compiles first.
* **How do I get the rest?** Every toolchain carries the winget, scoop and
  choco lines that install it, and a page to read if none of those suit.

Nothing here executes anything on import, nothing is cached to disk, and every
command is a list of arguments rather than a string: a workspace path with a
space in it is the normal case, not the exotic one, and `shell=True` would
make it a bug.
"""

from __future__ import annotations

import concurrent.futures
import os
import re
import shutil
import subprocess
import threading
import time

from . import known

__all__ = [
    "Toolchain", "TOOLCHAINS", "by_id", "for_language", "detect", "detect_all",
    "plan_for", "installed_ids", "summary", "clear_cache",
]

WINDOWS = os.name == "nt"

# How long a version probe may take. A toolchain that has to warm a JVM is the
# slow case; anything past this is not going to be useful interactively.
PROBE_TIMEOUT = 8.0

# How many to ask at once. Fifty-one probes one after another is minutes on a
# developer's machine, and this screen has to be usable. They are all waiting
# on other processes rather than on the GIL, so threads are the right tool.
PROBE_WORKERS = 8

# Detection is cached for the life of the process, keyed by toolchain id. The
# PATH does not usually change while an app is open, and probing forty
# compilers on every visit to the Toolchains screen would make it useless.
_found: dict[str, dict] = {}
_found_lock = threading.Lock()


class Toolchain:
    """One compiler or interpreter, and what to do with it.

    `steps` is a list of argument templates. One step means the language runs
    straight from source; two means it is built and then executed. The
    placeholders are filled in by [plan_for]:

    * ``{src}``   the file being run, absolute
    * ``{dir}``   the folder it is in
    * ``{stem}``  its name without the extension
    * ``{out}``   where to put a built executable, absolute, already suffixed
                  with .exe on Windows
    * ``{exe}``   the toolchain's own program, resolved on the PATH

    A step whose first element is ``{out}`` is the run of something we just
    built, which is how [plan_for] knows to check it appeared.
    """

    __slots__ = (
        "id", "name", "languages", "program", "version_args", "version_pattern",
        "steps", "winget", "scoop", "choco", "site", "note", "builds",
        "refuses", "suits",
    )

    def __init__(
        self,
        id,
        name,
        languages,
        program,
        steps,
        version_args=("--version",),
        version_pattern=r"(\d+\.\d+(?:\.\d+)?)",
        winget="",
        scoop="",
        choco="",
        site="",
        note="",
        refuses=(),
        suits=(),
    ):
        self.id = id
        self.name = name
        # Which registry languages this can run. First one wins when two
        # toolchains offer the same language and both are installed.
        self.languages = tuple(languages)
        self.program = program
        self.steps = tuple(tuple(step) for step in steps)
        self.version_args = tuple(version_args)
        self.version_pattern = version_pattern
        self.winget = winget
        self.scoop = scoop
        self.choco = choco
        self.site = site
        self.note = note
        # Covering a language is not the same as being able to open every file
        # written in it. `dotnet run` builds a project; an .fsx is a script and
        # has no project, so the SDK is the wrong tool for that extension
        # however right it is for .fs. `refuses` takes it out of the running,
        # `suits` moves a toolchain to the front for the extensions it is for.
        self.refuses = tuple(e.lower() for e in refuses)
        self.suits = tuple(e.lower() for e in suits)
        self.builds = len(self.steps) > 1

    def as_dict(self) -> dict:
        found = _found.get(self.id) or {}
        return {
            "id": self.id,
            "name": self.name,
            "languages": list(self.languages),
            "program": self.program,
            "builds": self.builds,
            "note": self.note,
            "installed": bool(found.get("path")),
            "path": found.get("path", ""),
            "version": found.get("version", ""),
            "install": {
                "winget": self.winget,
                "scoop": self.scoop,
                "choco": self.choco,
                "site": self.site,
            },
        }


def _steps_run(*argv):
    """A language that runs straight from source."""
    return [list(argv)]


def _steps_build(build, run=("{out}",)):
    """A language that is compiled and then executed."""
    return [list(build), list(run)]


# ---------------------------------------------------------------------------
# The table.
#
# Ordered so that where two toolchains run the same language, the one people
# are likelier to have - or the one that behaves best - comes first. gcc before
# clang before MSVC for C, because a PyCmd user on Windows is likeliest to have
# installed MinGW; node before deno before bun for JavaScript, for the same
# reason.
# ---------------------------------------------------------------------------

TOOLCHAINS = [
    # -- the ones that need no compiler ------------------------------------
    Toolchain(
        "python", "Python", ["python"], "python",
        _steps_run("{exe}", "{src}"),
        version_args=("--version",),
        winget="winget install Python.Python.3.13",
        scoop="scoop install python", choco="choco install python",
        site="https://www.python.org/downloads/windows/",
        note="PyCmd carries its own Python and always uses that one for the "
             "console. This is the Python on your PATH, for scripts that want it.",
    ),
    Toolchain(
        "node", "Node.js", ["javascript"], "node",
        _steps_run("{exe}", "{src}"),
        winget="winget install OpenJS.NodeJS.LTS",
        scoop="scoop install nodejs-lts", choco="choco install nodejs-lts",
        site="https://nodejs.org/",
    ),
    Toolchain(
        "deno", "Deno", ["javascript", "typescript"], "deno",
        _steps_run("{exe}", "run", "--allow-all", "{src}"),
        winget="winget install DenoLand.Deno",
        scoop="scoop install deno", choco="choco install deno",
        site="https://deno.com/",
        note="Runs TypeScript directly, with no separate compile step.",
    ),
    Toolchain(
        "bun", "Bun", ["javascript", "typescript"], "bun",
        _steps_run("{exe}", "run", "{src}"),
        scoop="scoop install bun", site="https://bun.sh/",
    ),
    Toolchain(
        "tsc", "TypeScript compiler", ["typescript"], "tsc",
        _steps_build(
            ("{exe}", "--outDir", "{dir}", "--target", "ES2022", "--module", "commonjs", "{src}"),
            ("node", "{dir}/{stem}.js"),
        ),
        version_args=("--version",),
        scoop="scoop install nodejs-lts", choco="choco install typescript",
        site="https://www.typescriptlang.org/",
        note="Needs Node as well, to run what it produces. `npm install -g typescript`.",
    ),
    Toolchain(
        "ruby", "Ruby", ["ruby"], "ruby", _steps_run("{exe}", "{src}"),
        winget="winget install RubyInstallerTeam.Ruby.3.3",
        scoop="scoop install ruby", choco="choco install ruby",
        site="https://rubyinstaller.org/",
    ),
    Toolchain(
        "php", "PHP", ["php"], "php", _steps_run("{exe}", "{src}"),
        winget="winget install PHP.PHP.8.3",
        scoop="scoop install php", choco="choco install php",
        site="https://windows.php.net/",
    ),
    Toolchain(
        "perl", "Perl", ["perl"], "perl", _steps_run("{exe}", "{src}"),
        winget="winget install StrawberryPerl.StrawberryPerl",
        scoop="scoop install perl", choco="choco install strawberryperl",
        site="https://strawberryperl.com/",
    ),
    Toolchain(
        "lua", "Lua", ["lua"], "lua", _steps_run("{exe}", "{src}"),
        version_args=("-v",),
        scoop="scoop install lua", choco="choco install lua",
        site="https://www.lua.org/",
    ),
    Toolchain(
        "rscript", "R", ["r"], "Rscript", _steps_run("{exe}", "{src}"),
        winget="winget install RProject.R",
        scoop="scoop install r", choco="choco install r.project",
        site="https://cran.r-project.org/bin/windows/base/",
    ),
    Toolchain(
        "julia", "Julia", ["julia"], "julia", _steps_run("{exe}", "{src}"),
        winget="winget install Julialang.Julia",
        scoop="scoop install julia", choco="choco install julia",
        site="https://julialang.org/downloads/",
    ),
    Toolchain(
        "powershell", "PowerShell", ["powershell"], "powershell",
        _steps_run("{exe}", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "{src}"),
        version_args=("-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"),
        site="https://learn.microsoft.com/powershell/",
        note="Windows ships with this one; there is nothing to install.",
    ),
    Toolchain(
        "pwsh", "PowerShell 7", ["powershell"], "pwsh",
        _steps_run("{exe}", "-NoProfile", "-File", "{src}"),
        version_args=("--version",),
        winget="winget install Microsoft.PowerShell",
        scoop="scoop install pwsh", choco="choco install powershell-core",
        site="https://learn.microsoft.com/powershell/",
    ),
    Toolchain(
        "bash", "Bash", ["shell"], "bash",
        _steps_run("{exe}", "{src}"),
        version_args=("--version",),
        winget="winget install Git.Git",
        scoop="scoop install git", choco="choco install git",
        site="https://gitforwindows.org/",
        note="Windows has no /bin/sh of its own. Git for Windows brings one, "
             "and so does WSL - either puts bash on the PATH and .sh files run.",
    ),
    Toolchain(
        "cmd", "Command Prompt", ["batch"], "cmd",
        _steps_run("{exe}", "/c", "{src}"),
        version_args=("/c", "ver"),
        note="Windows ships with this one; there is nothing to install.",
    ),
    Toolchain(
        "sqlite", "SQLite", ["sql"], "sqlite3",
        _steps_run("{exe}", "-batch", "-init", "{src}", ":memory:", ".quit"),
        winget="winget install SQLite.SQLite",
        scoop="scoop install sqlite", choco="choco install sqlite",
        site="https://sqlite.org/download.html",
        note="Runs the script against an in-memory database and prints what it selects.",
    ),
    Toolchain(
        "tclsh", "Tcl", ["tcl"], "tclsh", _steps_run("{exe}", "{src}"),
        version_args=("-encoding", "utf-8", os.devnull),
        version_pattern=r"()",
        scoop="scoop install tcl", site="https://www.tcl.tk/",
    ),
    Toolchain(
        "awk", "AWK", ["awk"], "gawk", _steps_run("{exe}", "-f", "{src}"),
        scoop="scoop install gawk", choco="choco install gawk",
        site="https://www.gnu.org/software/gawk/",
    ),
    Toolchain(
        "swipl", "SWI-Prolog", ["prolog"], "swipl",
        _steps_run("{exe}", "-q", "-g", "main", "-t", "halt", "{src}"),
        winget="winget install SWI-Prolog.SWI-Prolog",
        scoop="scoop install swi-prolog", site="https://www.swi-prolog.org/",
        note="Runs the predicate `main`, then halts.",
    ),
    Toolchain(
        "groovy", "Groovy", ["groovy"], "groovy", _steps_run("{exe}", "{src}"),
        scoop="scoop install groovy", choco="choco install groovy",
        site="https://groovy-lang.org/",
    ),

    # -- C and C++ ---------------------------------------------------------
    Toolchain(
        "gcc", "GCC", ["c"], "gcc",
        _steps_build(("{exe}", "{src}", "-o", "{out}", "-std=c17", "-O0", "-g")),
        winget="winget install BrechtSanders.WinLibs.POSIX.UCRT",
        scoop="scoop install gcc", choco="choco install mingw",
        site="https://winlibs.com/",
        note="MinGW-w64. The usual way to get a C and C++ compiler on Windows.",
    ),
    Toolchain(
        "gpp", "G++", ["cpp"], "g++",
        _steps_build(("{exe}", "{src}", "-o", "{out}", "-std=c++20", "-O0", "-g")),
        winget="winget install BrechtSanders.WinLibs.POSIX.UCRT",
        scoop="scoop install gcc", choco="choco install mingw",
        site="https://winlibs.com/",
    ),
    Toolchain(
        "clang", "Clang", ["c"], "clang",
        _steps_build(("{exe}", "{src}", "-o", "{out}", "-std=c17")),
        winget="winget install LLVM.LLVM", scoop="scoop install llvm",
        choco="choco install llvm", site="https://releases.llvm.org/",
    ),
    Toolchain(
        "clangpp", "Clang++", ["cpp"], "clang++",
        _steps_build(("{exe}", "{src}", "-o", "{out}", "-std=c++20")),
        winget="winget install LLVM.LLVM", scoop="scoop install llvm",
        choco="choco install llvm", site="https://releases.llvm.org/",
    ),
    Toolchain(
        "msvc", "MSVC", ["c", "cpp"], "cl",
        _steps_build(("{exe}", "/nologo", "/EHsc", "/Fe:{out}", "{src}")),
        version_args=(),
        version_pattern=r"Version (\d+\.\d+\.\d+)",
        winget="winget install Microsoft.VisualStudio.2022.BuildTools",
        site="https://visualstudio.microsoft.com/downloads/",
        note="Only on the PATH inside a Developer Command Prompt, so PyCmd "
             "usually will not see it unless it was started from one.",
    ),
    Toolchain(
        "objc", "Clang (Objective-C)", ["objectivec"], "clang",
        _steps_build(("{exe}", "{src}", "-o", "{out}", "-framework", "Foundation")),
        winget="winget install LLVM.LLVM", site="https://releases.llvm.org/",
        note="Objective-C without Apple's frameworks is a narrow thing on "
             "Windows; plain C parts work, Foundation does not.",
    ),

    # -- the modern compiled ones -----------------------------------------
    Toolchain(
        "go", "Go", ["go"], "go",
        _steps_run("{exe}", "run", "{src}"),
        version_args=("version",),
        winget="winget install GoLang.Go", scoop="scoop install go",
        choco="choco install golang", site="https://go.dev/dl/",
    ),
    Toolchain(
        "rustc", "Rust", ["rust"], "rustc",
        _steps_build(("{exe}", "{src}", "-o", "{out}")),
        winget="winget install Rustlang.Rustup", scoop="scoop install rustup",
        choco="choco install rustup.install", site="https://rustup.rs/",
    ),
    Toolchain(
        "zig", "Zig", ["zig"], "zig",
        _steps_run("{exe}", "run", "{src}"),
        version_args=("version",),
        winget="winget install zig.zig", scoop="scoop install zig",
        choco="choco install zig", site="https://ziglang.org/download/",
    ),
    Toolchain(
        "nim", "Nim", ["nim"], "nim",
        _steps_run("{exe}", "r", "--hints:off", "{src}"),
        version_args=("--version",),
        scoop="scoop install nim", choco="choco install nim",
        site="https://nim-lang.org/install.html",
    ),
    Toolchain(
        "crystal", "Crystal", ["crystal"], "crystal",
        _steps_run("{exe}", "run", "{src}"),
        version_args=("--version",),
        scoop="scoop install crystal", site="https://crystal-lang.org/install/",
    ),
    Toolchain(
        "dart", "Dart", ["dart"], "dart",
        _steps_run("{exe}", "run", "{src}"),
        version_args=("--version",),
        winget="winget install Google.DartSDK", scoop="scoop install dart",
        choco="choco install dart-sdk", site="https://dart.dev/get-dart",
    ),
    Toolchain(
        "vlang", "V", ["vlang"], "v",
        _steps_run("{exe}", "run", "{src}"),
        version_args=("version",),
        scoop="scoop install vlang", site="https://vlang.io/",
    ),
    Toolchain(
        "dmd", "D", ["d"], "dmd",
        _steps_build(("{exe}", "-of{out}", "{src}")),
        version_args=("--version",),
        scoop="scoop install dmd", choco="choco install dmd",
        site="https://dlang.org/download.html",
    ),

    # -- the JVM and .NET --------------------------------------------------
    Toolchain(
        "java", "Java", ["java"], "java",
        _steps_run("{exe}", "{src}"),
        version_args=("-version",),
        # Anchored on the word, not just on digits. Unanchored, this picked
        # the first number out of whatever the environment had already printed
        # to stderr - JAVA_TOOL_OPTIONS is a common one - and reported the JDK
        # as version 12.
        version_pattern=r'version "?(\d+(?:\.\d+)*)',
        winget="winget install EclipseAdoptium.Temurin.21.JDK",
        scoop="scoop install temurin-jdk", choco="choco install temurin",
        site="https://adoptium.net/",
        note="Java 11 and later run a single .java file directly, with no "
             "javac step. PyCmd uses that.",
    ),
    Toolchain(
        "kotlinc", "Kotlin", ["kotlin"], "kotlinc",
        _steps_build(
            ("{exe}", "-include-runtime", "-nowarn", "-d", "{dir}/{stem}.jar", "{src}"),
            ("java", "-jar", "{dir}/{stem}.jar"),
        ),
        version_args=("-version",),
        scoop="scoop install kotlin", choco="choco install kotlinc",
        site="https://kotlinlang.org/docs/command-line.html",
        note="Slow - the Kotlin compiler starts a JVM to compile, and then you "
             "start another to run. A first build of thirty seconds is normal.",
    ),
    Toolchain(
        "scala", "Scala", ["scala"], "scala", _steps_run("{exe}", "{src}"),
        version_args=("-version",),
        scoop="scoop install scala", choco="choco install scala",
        site="https://www.scala-lang.org/download/",
    ),
    Toolchain(
        "clojure", "Clojure", ["clojure"], "clojure",
        _steps_run("{exe}", "-M", "{src}"),
        version_args=("--version",),
        scoop="scoop install clojure", site="https://clojure.org/guides/install_clojure",
    ),
    Toolchain(
        "dotnet", ".NET SDK", ["csharp", "fsharp", "visualbasic"], "dotnet",
        _steps_run("{exe}", "run", "--project", "{dir}"),
        version_args=("--version",),
        winget="winget install Microsoft.DotNet.SDK.8",
        scoop="scoop install dotnet-sdk", choco="choco install dotnet-sdk",
        site="https://dotnet.microsoft.com/download",
        note="Runs the project in the file's folder, so a loose .cs, .vb or "
             ".fs file wants a project beside it. PyCmd writes one for you "
             "the first time. An .fsx is a script rather than a project, so "
             "that goes to F# Interactive instead.",
        refuses=(".fsx", ".fsscript"),
    ),
    Toolchain(
        "fsi", "F# Interactive", ["fsharp"], "dotnet",
        _steps_run("{exe}", "fsi", "--nologo", "{src}"),
        version_args=("--version",),
        winget="winget install Microsoft.DotNet.SDK.8",
        site="https://dotnet.microsoft.com/languages/fsharp",
        note="Runs a single .fs or .fsx file with no project around it.",
        suits=(".fsx", ".fsscript"),
    ),

    # -- the functional ones ----------------------------------------------
    Toolchain(
        "runghc", "Haskell", ["haskell"], "runghc", _steps_run("{exe}", "{src}"),
        version_args=("--version",),
        winget="winget install Haskell.GHCup", choco="choco install ghc",
        site="https://www.haskell.org/ghcup/",
    ),
    Toolchain(
        "ocaml", "OCaml", ["ocaml"], "ocaml", _steps_run("{exe}", "{src}"),
        version_args=("-version",),
        scoop="scoop install ocaml", choco="choco install ocpwin",
        site="https://ocaml.org/install",
    ),
    Toolchain(
        "racket", "Racket", ["racket"], "racket", _steps_run("{exe}", "{src}"),
        version_args=("--version",),
        winget="winget install Racket.Racket", choco="choco install racket",
        site="https://racket-lang.org/",
    ),
    Toolchain(
        "elixir", "Elixir", ["elixir"], "elixir", _steps_run("{exe}", "{src}"),
        version_args=("--version",),
        scoop="scoop install elixir", choco="choco install elixir",
        site="https://elixir-lang.org/install.html",
    ),
    Toolchain(
        "escript", "Erlang", ["erlang"], "escript", _steps_run("{exe}", "{src}"),
        version_args=(),
        version_pattern=r"(\d+\.\d+)",
        choco="choco install erlang", site="https://www.erlang.org/downloads",
    ),
    Toolchain(
        "guile", "Scheme (Guile)", ["scheme"], "guile",
        _steps_run("{exe}", "-s", "{src}"),
        version_args=("--version",), scoop="scoop install guile", choco="choco install guile",
        site="https://www.gnu.org/software/guile/",
    ),

    # -- the older ones, still very much in use ---------------------------
    Toolchain(
        "gfortran", "Fortran", ["fortran"], "gfortran",
        _steps_build(("{exe}", "{src}", "-o", "{out}")),
        winget="winget install BrechtSanders.WinLibs.POSIX.UCRT",
        scoop="scoop install gcc", site="https://gcc.gnu.org/fortran/",
    ),
    Toolchain(
        "cobc", "GnuCOBOL", ["cobol"], "cobc",
        _steps_build(("{exe}", "-x", "-free", "-o", "{out}", "{src}")),
        version_args=("--version",),
        choco="choco install gnucobol",
        site="https://gnucobol.sourceforge.io/",
    ),
    Toolchain(
        "fpc", "Free Pascal", ["pascal"], "fpc",
        _steps_build(("{exe}", "-o{out}", "{src}")),
        version_args=("-iV",),
        scoop="scoop install freepascal", choco="choco install freepascal",
        site="https://www.freepascal.org/download.html",
    ),
    Toolchain(
        "nasm", "NASM", ["assembly"], "nasm",
        _steps_build(("{exe}", "-f", "win64", "{src}", "-o", "{dir}/{stem}.obj")),
        version_args=("-v",),
        scoop="scoop install nasm", choco="choco install nasm",
        site="https://www.nasm.us/",
        note="Assembles to an object file. Linking it into something runnable "
             "needs a linker of your choosing, so PyCmd stops at the .obj.",
    ),
    Toolchain(
        "swiftc", "Swift", ["swift"], "swiftc",
        _steps_build(("{exe}", "{src}", "-o", "{out}")),
        version_args=("--version",),
        winget="winget install Swift.Toolchain", site="https://www.swift.org/install/windows/",
    ),
]

_BY_ID = {chain.id: chain for chain in TOOLCHAINS}


def by_id(toolchain_id: str):
    return _BY_ID.get(toolchain_id)


def for_language(language_id: str):
    """Every toolchain that can run this language, best first."""
    return [chain for chain in TOOLCHAINS if language_id in chain.languages]


# ---------------------------------------------------------------------------
# Finding them
# ---------------------------------------------------------------------------

def _which(program: str) -> str:
    """Where a program is, or "".

    `shutil.which` already knows about PATHEXT on Windows, so `gcc` finds
    `gcc.exe` without us spelling it out.
    """
    return shutil.which(program) or ""


def _kill_tree(process) -> None:
    """Ends a probe and anything it started."""
    try:
        if WINDOWS:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True, timeout=5, creationflags=_no_window(),
            )
        else:
            process.kill()
    except Exception:  # noqa: BLE001 - it may already be gone
        try:
            process.kill()
        except Exception:  # noqa: BLE001
            pass


def _probe_version(path: str, args) -> str:
    """Asks a toolchain what version it is, and gives up rather than waiting.

    Several of these print their version to stderr rather than stdout - java
    and kotlinc both do - so both are read. A toolchain that answers nothing
    useful is still installed; the version is decoration.

    **This must not use `subprocess.run(timeout=...)`,** which is the obvious
    way to write it and hangs. On a timeout `run` kills the child and then
    waits for the output pipe to close - and if a *grandchild* inherited that
    pipe, it never does. On Windows `kotlinc`, `scala`, `groovy` and `clojure`
    are all .bat wrappers that spawn java.exe, so that is not a corner case:
    it is what happens on any machine with a JVM language installed, and it
    hung a CI run for ten minutes before it hung anybody's Toolchains screen.

    So the read happens on a daemon thread that is joined with a deadline. If
    the deadline passes the process tree is killed and the thread is abandoned;
    a stuck pipe costs one leaked thread rather than the whole app.
    """
    try:
        process = subprocess.Popen(
            [path, *args],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace",
            creationflags=_no_window(),
        )
    except (OSError, ValueError):
        return ""

    collected = []

    def read():
        try:
            collected.append(process.stdout.read())
        except Exception:  # noqa: BLE001 - the pipe may be torn out from under it
            pass

    reader = threading.Thread(target=read, name="pycmd-probe", daemon=True)
    reader.start()
    reader.join(PROBE_TIMEOUT)

    if reader.is_alive():
        _kill_tree(process)
        # One second of grace for the kill to take effect, then leave it. The
        # thread is a daemon and holds nothing that matters.
        reader.join(1.0)

    try:
        process.wait(timeout=1)
    except Exception:  # noqa: BLE001
        pass
    return "".join(collected).strip()


def _no_window() -> int:
    """Keeps a console window from flashing up on Windows for every probe."""
    if WINDOWS:
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def detect(toolchain_id: str, refresh: bool = False) -> dict:
    """Looks for one toolchain. Cached unless asked to look again.

    Three layers, cheapest first. The dict in this process answers a repeat
    question for free. What PyCmd remembered from previous *launches* - and
    from previous *versions* - answers for the cost of one stat call, which
    is the layer that stopped detection feeling like it started from zero
    every time. Only when neither knows does anything get run.
    """
    chain = _BY_ID.get(toolchain_id)
    if chain is None:
        return {"installed": False, "error": "no such toolchain"}
    if not refresh and toolchain_id in _found:
        return dict(_found[toolchain_id])

    if not refresh:
        remembered = known.recall(toolchain_id)
        if remembered is not None:
            found = {"path": remembered["path"], "version": remembered["version"],
                     "checked_at": int(time.time()), "remembered": True}
            with _found_lock:
                _found[toolchain_id] = found
            return dict(found)

    path = _which(chain.program)
    found = {"path": path, "version": "", "checked_at": int(time.time())}
    # Written from the pool in detect_all, so the assignment below is done
    # under a lock. CPython would make it atomic anyway; saying so is cheaper
    # than relying on it.
    if path:
        text = _probe_version(path, chain.version_args)
        match = re.search(chain.version_pattern, text) if chain.version_pattern else None
        if match and match.groups():
            found["version"] = match.group(1)
        elif text:
            # No pattern matched, so show the first line rather than nothing:
            # "it is here and it said something" beats a blank.
            found["version"] = text.splitlines()[0][:60]
    with _found_lock:
        _found[toolchain_id] = found
    known.remember(toolchain_id, found)
    return dict(found)


def detect_all(refresh: bool = False) -> list:
    """Every toolchain, with what was found. This is the Toolchains screen.

    Probed in parallel: fifty-one one after another is minutes on a machine
    with a lot installed, and every one of them is waiting on another process
    rather than on the GIL.
    """
    wanted = [chain for chain in TOOLCHAINS if refresh or chain.id not in _found]
    if wanted:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=PROBE_WORKERS, thread_name_prefix="pycmd-detect",
        ) as pool:
            list(pool.map(lambda chain: detect(chain.id, refresh=refresh), wanted))
        # One write for the whole survey rather than fifty-one.
        known.survey_done()
    return [chain.as_dict() for chain in TOOLCHAINS]


def installed_ids(refresh: bool = False) -> list:
    return [c.id for c in TOOLCHAINS if detect(c.id, refresh=refresh).get("path")]


def clear_cache(forget_machine: bool = False) -> None:
    """Empties this process's answers, and optionally the remembered ones.

    The default is deliberately the narrow one. Clearing what this process
    thinks is what a Refresh button means; throwing away what PyCmd has
    learned about the machine over several versions is a different and much
    more expensive act, and has to be asked for.
    """
    with _found_lock:
        _found.clear()
    if forget_machine:
        known.forget()


def summary(refresh: bool = False) -> dict:
    """Counts, for the header of the Toolchains screen."""
    rows = detect_all(refresh=refresh)
    installed = [row for row in rows if row["installed"]]
    languages = set()
    for row in installed:
        languages.update(row["languages"])
    return {
        "toolchains": len(rows),
        "installed": len(installed),
        "languages": sorted(languages),
        "language_count": len(languages),
    }


# ---------------------------------------------------------------------------
# Running something with them
# ---------------------------------------------------------------------------

def _fill(template, fields) -> list:
    return [part.format(**fields) for part in template]


def plan_for(path: str, language_id: str, prefer: str = "", refresh: bool = False) -> dict:
    """What to run, to run this file.

    Returns a dict the caller can act on rather than raising: the interesting
    answers here are "nothing is installed for this" and "install one of
    these", and those are results, not errors.
    """
    path = os.path.abspath(path)
    folder = os.path.dirname(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    # Built output goes beside the source rather than in a temp folder, so a
    # program that opens a file next to itself finds it, and so the thing you
    # just built is somewhere you can see.
    out = os.path.join(folder, stem + (".exe" if WINDOWS else ".out"))

    extension = os.path.splitext(path)[1].lower()
    candidates = [c for c in for_language(language_id)
                  if extension not in c.refuses]
    # If refusing left nothing at all, refuse nothing: "no toolchain for this
    # language" is a different and much less true answer than "the only one
    # there is would rather not".
    candidates = candidates or for_language(language_id)
    # A toolchain that is *for* this extension goes first, whatever the table
    # order says. Without this a loose hello.fsx went to `dotnet run`, which
    # answered "Couldn't find a project to run" - correct, and useless.
    candidates = ([c for c in candidates if extension in c.suits]
                  + [c for c in candidates if extension not in c.suits])
    if prefer:
        candidates = ([c for c in candidates if c.id == prefer]
                      + [c for c in candidates if c.id != prefer])
    if not candidates:
        return {
            "ok": False,
            "reason": "unsupported",
            "error": f"PyCmd has no toolchain for {language_id!r}.",
            "install": [],
        }

    for chain in candidates:
        found = detect(chain.id, refresh=refresh)
        if not found.get("path"):
            continue
        fields = {
            "exe": found["path"], "src": path, "dir": folder,
            "stem": stem, "out": out,
        }
        return {
            "ok": True,
            "toolchain": chain.id,
            "name": chain.name,
            "version": found.get("version", ""),
            "builds": chain.builds,
            "cwd": folder,
            "output": out if chain.builds else "",
            "commands": [_fill(step, fields) for step in chain.steps],
            "note": chain.note,
        }

    return {
        "ok": False,
        "reason": "missing",
        "error": (
            f"Nothing installed here runs {language_id}. "
            f"Any one of these would: " + ", ".join(c.name for c in candidates) + "."
        ),
        "install": [c.as_dict() for c in candidates],
    }
