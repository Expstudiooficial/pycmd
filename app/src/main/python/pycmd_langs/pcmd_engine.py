"""Reaching PyCmd's fast engine (Kotlin, in lang/) from the Python side.

Where it lives:
  * Android - inside the app itself. Chaquopy calls it directly, in this process.
  * Windows - a `pcmd` program shipped with the app, on its own Java runtime;
    kept running and asked over a pipe, one JSON line per request.
  * A developer's machine - `java -jar lang/build/libs/pcmd.jar`, if it is built.

If none of those is there, `available()` is False and the caller falls back to
the first engine (pcmd.py), which runs everything PyCmd 1 has.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_lock = threading.Lock()
_engine = None
_tried = False


# ---------------------------------------------------------------- in process (Android)

class _InProcess:
    kind = "in-app"

    def __init__(self, pcmd_class, io_class):
        self.Pcmd = pcmd_class
        self.IO = io_class

    def _io(self, stdout, stdin, tick=None):
        from java import dynamic_proxy  # noqa: Chaquopy

        IO = self.IO

        class Bridge(dynamic_proxy(IO)):
            def write(self, text):
                stdout.write(str(text))
                flush = getattr(stdout, "flush", None)
                if flush:
                    flush()

            def readLine(self):
                line = stdin.readline() if stdin is not None else ""
                if not line:
                    return None
                return line.rstrip("\n").rstrip("\r")

            def tick(self):
                # Where a Stop pressed in the app reaches the program: an
                # interrupt raised here unwinds the engine.
                return bool(tick()) if tick else False

        return Bridge()

    def run(self, source, path=None, stdout=None, stdin=None, argv=(), timeout=0.0, tick=None):
        io = self._io(stdout or sys.stdout, stdin, tick)
        r = self.Pcmd.runHere(source, path, list(argv), io, "android", int(timeout * 1000))
        return {"ok": bool(r.ok), "exit": int(r.exit), "error": str(r.error), "line": int(r.line),
                "kind": str(r.kind)}

    def test(self, source, path=None, stdout=None):
        io = self._io(stdout or sys.stdout, None)
        r = self.Pcmd.testHere(source, path, io)
        return {"ok": bool(r.ok), "passed": int(r.passed), "failed": int(r.failed), "error": str(r.error)}

    def parse(self, source):
        r = self.Pcmd.parse(source)
        return {"ok": bool(r.ok), "line": int(r.line), "error": str(r.error)}

    def check(self, source):
        r = self.Pcmd.check(source)
        return {"ok": bool(r.ok), "line": int(r.line), "error": str(r.error)}

    def version(self):
        return str(self.Pcmd.version())


# ---------------------------------------------------------------- a pcmd process

class _Process:
    kind = "process"

    def __init__(self, command):
        self.command = command
        self.proc = None
        self.next_id = 0

    def _start(self):
        if self.proc is None or self.proc.poll() is not None:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.proc = subprocess.Popen(
                self.command + ["serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, encoding="utf-8", creationflags=flags,
            )

    def ask(self, request):
        with _lock:
            self._start()
            self.next_id += 1
            request["id"] = self.next_id
            try:
                self.proc.stdin.write(json.dumps(request) + "\n")
                self.proc.stdin.flush()
                line = self.proc.stdout.readline()
            except (OSError, ValueError):
                line = ""
            if not line:
                self.proc = None
                return {"ok": False, "error": "the PyCmd engine stopped unexpectedly", "out": ""}
            return json.loads(line)

    def run(self, source, path=None, stdout=None, stdin=None, argv=(), timeout=0.0, tick=None):
        text = stdin.read() if stdin is not None and hasattr(stdin, "read") else ""
        reply = self.ask({"op": "run", "source": source, "path": path, "stdin": text,
                          "argv": list(argv), "timeout": timeout or 0})
        (stdout or sys.stdout).write(reply.get("out", ""))
        return reply

    def test(self, source, path=None, stdout=None):
        reply = self.ask({"op": "test", "source": source, "path": path})
        (stdout or sys.stdout).write(reply.get("out", ""))
        return reply

    def check(self, source):
        return self.ask({"op": "check", "source": source})

    def parse(self, source):
        return self.ask({"op": "parse", "source": source})

    def version(self):
        return self.ask({"op": "version"}).get("error", "")


def _candidates():
    env = os.environ.get("PYCMD_ENGINE", "").strip()
    if env:
        yield env.split()
    base = getattr(sys, "_MEIPASS", None)
    roots = [base] if base else []
    roots.append(os.path.dirname(os.path.abspath(sys.executable)))
    for root in roots:
        for rel in (("pcmd-engine", "bin", "pcmd.exe"), ("pcmd-engine", "bin", "pcmd")):
            launcher = os.path.join(root, *rel)
            if os.path.isfile(launcher):
                yield [launcher]
        jar = os.path.join(root, "pcmd-engine", "pcmd.jar")
        java = os.path.join(root, "pcmd-engine", "runtime", "bin", "java.exe" if os.name == "nt" else "java")
        if os.path.isfile(jar) and os.path.isfile(java):
            yield [java, "-Xss512m", "-XX:+UseSerialGC", "-jar", jar]
    # a source checkout: lang/build/libs/pcmd.jar next to app/
    jar = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "..", "..", "lang", "build", "libs", "pcmd.jar"))
    if os.path.isfile(jar):
        import shutil

        java = shutil.which("java")
        if java:
            yield [java, "-jar", jar]


def _find():
    try:  # Android: the engine is compiled into the app
        from java import jclass  # noqa: Chaquopy

        return _InProcess(jclass("com.expstudio.pycmd.lang.Pcmd"), jclass("com.expstudio.pycmd.lang.PcmdIO"))
    except Exception:  # noqa: BLE001 - not on Android, or an older APK
        pass
    for command in _candidates():
        return _Process(command)
    return None


def engine():
    global _engine, _tried
    if not _tried:
        _tried = True
        _engine = _find()
    return _engine


def available() -> bool:
    return engine() is not None


_why_disabled = ""


def disable(why: str) -> None:
    """The fast engine failed in a way a program cannot cause: use the first
    engine for the rest of this session, and remember why."""
    global _engine, _tried, _why_disabled
    _engine, _tried, _why_disabled = None, True, why


def status() -> dict:
    e = engine()
    return {"engine": "fast" if e else "first", "kind": getattr(e, "kind", ""), "problem": _why_disabled}


def reset():
    global _engine, _tried
    _engine, _tried = None, False
