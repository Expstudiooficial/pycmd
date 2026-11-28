"""PyCmd, the app's own language: run, check, test and translate .pcmd files.

    let name = input("Name? ") ?? "friend"
    print("Hello, {name}!")

How it runs: the compiler (pcmd_compiler) checks the program and turns it into
Python, which CPython compiles to bytecode and runs - the same engine that runs
the app. So a PyCmd program runs as fast as the same program written in
Python: far faster than a tree-walking interpreter, nowhere near C or Rust.
The safety is real: names, mutability and declared types are checked, the
program cannot import anything or reach Python, files are kept to its own
folder, and integers never overflow.
"""

from __future__ import annotations

import os
import sys

from .pcmd_lexer import PcmdSyntaxError
from . import pcmd_runtime as rt
from .pcmd_compiler import compile_source

LANGUAGE = "PyCmd"
VERSION = rt.VERSION


class PcmdError(Exception):
    """A PyCmd program failed: a syntax/check error or an uncaught runtime one."""

    def __init__(self, message, line=0, kind="Error"):
        super().__init__(message)
        self.message = message
        self.line = line
        self.kind = kind


_CODE_CACHE: dict = {}


def _compiled(source: str, filename: str):
    key = (filename, source)
    hit = _CODE_CACHE.get(key)
    if hit is None:
        py, line_map = compile_source(source, filename)
        code = compile(py, f"<pcmd:{filename}>", "exec")
        if len(_CODE_CACHE) > 64:
            _CODE_CACHE.clear()
        hit = (code, line_map, py)
        _CODE_CACHE[key] = hit
    return hit


_LINE_MAPS: dict = {}


def execute(source: str, runtime: rt.Runtime, filename="<pcmd>"):
    """Compiles and runs one file in runtime; returns its top-level names."""
    code, line_map, _ = _compiled(source, filename)
    _LINE_MAPS[code.co_filename] = line_map
    ns = runtime.namespace(filename)
    exec(code, ns)  # defines _pc_main - nothing else runs at this point
    return ns["_pc_main"]()


def _source_line(exc) -> int:
    tb = exc.__traceback__
    line = 0
    while tb is not None:
        name = tb.tb_frame.f_code.co_filename
        if name.startswith("<pcmd:"):
            lines = _LINE_MAPS.get(name)
            if lines and 0 < tb.tb_lineno <= len(lines):
                line = lines[tb.tb_lineno - 1]
        tb = tb.tb_next
    return line


def _fail(exc) -> PcmdError:
    kind, message = rt.translate(exc)
    line = _source_line(exc)
    where = f"line {line}: " if line else ""
    return PcmdError(f"{where}{kind}: {message}" if kind not in ("Error",) else f"{where}{message}",
                     line, kind)


def run_source(source: str, stdout=None, stdin=None, argv=None, path=None,
               platform="pycmd") -> int:
    """Runs a program. Returns its exit code; raises PcmdError if it fails."""
    root = os.path.dirname(os.path.abspath(path)) if path else os.getcwd()
    runtime = rt.Runtime(stdout=stdout, stdin=stdin, argv=argv, root=root, platform=platform)
    filename = os.path.abspath(path) if path else "<pcmd>"
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(max(previous, 4000))
    try:
        execute(source, runtime, filename)
        return 0
    except PcmdSyntaxError as exc:
        raise PcmdError(f"line {exc.line}: {exc.message}", exc.line, "Syntax") from None
    except rt.PcExit as exit_request:
        code = exit_request.code
        return code if isinstance(code, int) else 0
    except RecursionError as exc:
        raise _fail(exc) from None
    except Exception as exc:  # the program's own error, in its words
        raise _fail(exc) from None
    finally:
        sys.setrecursionlimit(previous)


def run_tests(source: str, stdout=None, path=None) -> dict:
    """Runs the program's `test "name" { }` blocks. Output goes to stdout."""
    out = stdout or sys.stdout
    root = os.path.dirname(os.path.abspath(path)) if path else os.getcwd()

    class Quiet:
        def write(self, text):
            pass

    runtime = rt.Runtime(stdout=Quiet(), stdin=None, root=root)
    filename = os.path.abspath(path) if path else "<pcmd>"
    try:
        execute(source, runtime, filename)
    except PcmdSyntaxError as exc:
        out.write(f"line {exc.line}: {exc.message}\n")
        return {"ok": False, "passed": 0, "failed": 0, "error": exc.message}
    except rt.PcExit:
        pass
    except Exception as exc:
        err = _fail(exc)
        out.write(f"the program failed before its tests ran: {err.message}\n")
        return {"ok": False, "passed": 0, "failed": 0, "error": err.message}
    passed = failed = 0
    for name, fn, line in runtime.tests:
        try:
            fn()
            passed += 1
            out.write(f"  pass  {name}\n")
        except Exception as exc:
            failed += 1
            out.write(f"  FAIL  {name} - {_fail(exc).message}\n")
    total = passed + failed
    if total == 0:
        out.write('no tests - write one with: test "it adds" { assert add(1, 2) == 3 }\n')
    else:
        out.write(f"{passed} of {total} tests passed\n")
    return {"ok": failed == 0, "passed": passed, "failed": failed}


def check(source: str) -> dict:
    """Compiles without running: the first problem, or ok."""
    try:
        compile_source(source)
        return {"ok": True}
    except PcmdSyntaxError as exc:
        return {"ok": False, "line": exc.line, "col": exc.col, "error": exc.message}


def to_python(source: str) -> str:
    """The Python a program becomes - to read, not to run elsewhere."""
    py, _ = compile_source(source)
    return py


def run_file(path: str, stdout=None, stdin=None, argv=None, platform="pycmd") -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
    except OSError as exc:
        return {"ok": False, "error": f"cannot open {path}: {exc}", "language": LANGUAGE}
    try:
        code = run_source(source, stdout=stdout, stdin=stdin,
                          argv=argv or [os.path.basename(path)], path=path, platform=platform)
        return {"ok": True, "exit": code, "language": LANGUAGE}
    except PcmdError as exc:
        return {"ok": False, "error": f"PyCmd error, {exc.message}", "line": exc.line,
                "language": LANGUAGE}


TEMPLATE = '''# A PyCmd program. Press Run.
let name = "world"
print("Hello, {name}!")

fn square(n: int) -> int {
    n * n
}

for i in 1..=5 {
    print("{i} squared is {square(i)}")
}
'''


class Repl:
    """Line-at-a-time PyCmd for the console. Each entry runs together with the
    entries before it, so names carry over; only what the new one prints is
    shown. A bare expression shows its value."""

    def __init__(self, stdout=None, root=None, platform="pycmd"):
        self.history = []
        self.head = ""
        self.stdout = stdout or sys.stdout
        self.root = root or os.getcwd()
        self.platform = platform

    def _is_value(self, text):
        from .pcmd_parser import parse

        try:
            body = parse(text).body
        except PcmdSyntaxError:
            return False
        if len(body) != 1 or body[0].kind != "expr":
            return False
        e = body[0].expr
        return not (e.kind == "call" and e.func.kind == "name" and e.func.name == "print")

    def feed(self, text: str) -> dict:
        if not text.strip():
            return {"ok": True}
        value = self._is_value(text)
        line = f"print(repr({text}))" if value else text
        source = "\n".join(self.history + [line])
        buf = []

        class Buf:
            def write(self_inner, s):
                buf.append(s)

        runtime = rt.Runtime(stdout=Buf(), stdin=None, root=self.root, platform=self.platform)
        try:
            execute(source, runtime, "<repl>")
        except PcmdSyntaxError as exc:
            return {"ok": False, "error": exc.message}
        except rt.PcExit:
            return {"ok": True, "exit": True}
        except Exception as exc:
            return {"ok": False, "error": _fail(exc).message}
        everything = "".join(buf)
        new = everything[len(self.head):] if everything.startswith(self.head) else everything
        self.stdout.write(new)
        if not value:
            self.history.append(text)
            self.head = everything
        return {"ok": True}
