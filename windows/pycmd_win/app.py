"""The window.

PyCmd's UI has always been half web page - the console, the editor, every
plugin panel and the whole preview are HTML in a WebView, and only the chrome
around them was Compose. So the Windows port keeps the half that was already
portable and replaces the half that was not: the chrome becomes HTML too, and
the window is Edge WebView2, which every Windows 10 and 11 machine has.

That choice is what makes this a port rather than a rewrite. `console.js`,
`editor.js`, `highlight.js` and every plugin's `ui.html` are the same files the
phone loads, byte for byte.

**Why there is an HTTP server in here.** The page could be loaded from
`file://`, and then every relative path, every `fetch`, and every plugin panel
would be fighting the browser's rules about local files. Serving the same
folders over `127.0.0.1` on a random high port removes that whole class of
problem, costs a few milliseconds at start-up, and is bound to the loopback
interface so nothing outside the machine can reach it. The token in the URL is
belt and braces: another program on the same machine that guessed the port
still does not get an answer.
"""

from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import posixpath
import secrets
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import host as host_module
from . import store, updates

TITLE = "PyCmd"
WINDOW = (1180, 760)
MINIMUM = (860, 560)


# What a client leaving looks like. Windows raises ConnectionAbortedError
# (WinError 10053) when the local stack drops a connection whose peer has
# gone; Unix gives BrokenPipeError; either can give ConnectionResetError.
# ConnectionError is the base of all three, and deliberately nothing wider:
# a bare OSError here would also swallow a real bug in a handler, which is
# exactly the kind of thing this server must keep shouting about.
_GONE = ConnectionError


class _Handler(BaseHTTPRequestHandler):
    """Serves the app's own files, and nothing else.

    Every path is resolved and then checked to be inside one of the roots.
    That check is the whole security model of this server: a request for
    ``/../../../Windows/System32/config/SAM`` resolves to somewhere outside
    every root and gets a 404 like anything else that is not ours.
    """

    server_version = "PyCmd"
    protocol_version = "HTTP/1.1"

    # Filled in by the server that owns us.
    roots: dict = {}
    token: str = ""

    def log_message(self, *args):  # noqa: D102 - quiet by default
        pass

    def handle_one_request(self):  # noqa: D102
        """One request, and a client that leaves early is not an error.

        WebView2 aborts requests as a matter of course: a panel iframe is
        pointed at about:blank and rewritten, a page navigates while an image
        is still coming, the window closes with a poll in flight. Each of
        those breaks the socket underneath a `wfile.write` that has already
        begun, and the stock handler lets that reach `handle_error`, which
        prints a traceback per occurrence:

            ConnectionAbortedError: [WinError 10053] An established
            connection was aborted by the software in your host machine

        Nothing is wrong when that happens and there is nothing to fix at the
        other end, so it is swallowed here rather than printed. Note it must
        be caught around `handle_one_request` and not only around the writes:
        the send buffer means the failure can surface later, inside the
        header write or the read of the next request on a kept-alive
        connection.
        """
        try:
            super().handle_one_request()
        except _GONE:
            self.close_connection = True

    def finish(self):  # noqa: D102
        """Flushes what is left, forgiving a socket that has already gone.

        `handle_one_request` is not enough on its own: this runs after it, in
        BaseRequestHandler's own finally, and flushing a buffered response to
        a closed socket raises here instead.
        """
        try:
            super().finish()
        except _GONE:
            pass

    def _deny(self, code=404):
        try:
            self.send_response(code)
            self.send_header("Content-Length", "0")
            self.end_headers()
        except _GONE:
            self.close_connection = True

    def _authorised(self, query) -> bool:
        """Whether this request may have anything at all.

        The window opens the entry point with `?t=<token>` and gets the token
        back as a cookie, so every request the page makes afterwards carries
        it without the page having to do anything. Everything is checked, not
        just the first request: the workspace is served from here, and those
        are the user's own files - another program on this machine that
        guessed the port should not be able to read them.
        """
        if not self.token:
            return True
        if query.get("t", [""])[0] == self.token:
            return True
        cookie = self.headers.get("Cookie", "")
        return f"pycmd={self.token}" in cookie

    def _resolve(self):
        parsed = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if not self._authorised(query):
            return None

        path = urllib.parse.unquote(parsed.path)
        if path in ("", "/"):
            path = "/index.html"
        parts = [p for p in posixpath.normpath(path).split("/") if p not in ("", ".", "..")]
        if not parts:
            return None

        prefix = parts[0]
        root = self.roots.get(prefix)
        if not isinstance(root, str):
            root = None
        if root is not None:
            candidate = os.path.join(root, *parts[1:])
        else:
            candidate = os.path.join(self.roots["_ui"], *parts)

        candidate = os.path.abspath(candidate)
        allowed = [os.path.abspath(value) for key, value in self.roots.items()
                   if isinstance(value, str)]
        if not any(candidate == base or candidate.startswith(base + os.sep)
                   for base in allowed):
            return None
        return candidate if os.path.isfile(candidate) else None

    def do_GET(self):  # noqa: N802
        target = self._resolve()
        if target is None:
            return self._deny()
        try:
            with open(target, "rb") as handle:
                body = handle.read()
        except OSError:
            return self._deny()

        kind = mimetypes.guess_type(target)[0] or "application/octet-stream"
        if kind.startswith("text/") or kind in ("application/javascript", "application/json"):
            kind += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # Handed out on the way in, so the page's own requests carry it.
        # HttpOnly because no script needs to read it, SameSite=Strict
        # because nothing outside this origin should ever send it.
        if self.token and "t=" in urllib.parse.urlsplit(self.path).query:
            self.send_header(
                "Set-Cookie",
                f"pycmd={self.token}; Path=/; HttpOnly; SameSite=Strict",
            )
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        """The same API the window uses, over HTTP.

        `--serve-only` exists so the interface can be opened in a browser -
        which is how it is tested where there is no Windows, and a genuine
        fallback on a machine whose WebView2 is broken. It would be a pretence
        without this: the page can draw, but it could not ask Python anything.

        Same cookie, same rules. This is not a public API and is not reachable
        from off the machine.
        """
        parsed = urllib.parse.urlsplit(self.path)
        if not self._authorised(urllib.parse.parse_qs(parsed.query)):
            return self._deny(403)
        if parsed.path not in ("/api/call", "/api/events"):
            return self._deny()

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length > 8 * 1024 * 1024:
            return self._deny(413)
        raw = self.rfile.read(length) if length else b"{}"

        try:
            asked = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            asked = {}

        host = self.roots.get("_host")
        if host is None:
            reply = {"ok": False, "error": "PyCmd is still starting"}
        elif parsed.path == "/api/events":
            reply = {"ok": True, "events": host.drain()}
        else:
            reply = host_module.call(host, str(asked.get("name", "")), asked.get("payload") or {})

        body = json.dumps(reply).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):  # noqa: N802
        target = self._resolve()
        if target is None:
            return self._deny()
        self.send_response(200)
        self.send_header("Content-Length", str(os.path.getsize(target)))
        self.end_headers()


class _Server(ThreadingHTTPServer):
    """The loopback server, with socketserver's traceback printing removed.

    A backstop rather than the fix: the handler already forgives a client
    that leaves. But socketserver's default `handle_error` writes a full
    traceback to stderr for *anything* a handler raises, and in a windowed
    build stderr is either swallowed or, worse, whatever console the user
    happened to start the exe from. PyCmd has a log screen; that is where
    this belongs.
    """

    def handle_error(self, request, client_address):
        kind, error = sys.exc_info()[:2]
        if issubclass(kind, _GONE):
            return
        host = self.RequestHandlerClass.roots.get("_host")
        if host is not None:
            import traceback

            host.log("error", f"the UI server raised {kind.__name__}",
                     traceback.format_exc())


def serve(roots: dict) -> tuple:
    """Starts the loopback server. Returns (url, server)."""
    token = secrets.token_urlsafe(16)
    handler = type("_Bound", (_Handler,), {"roots": roots, "token": token})
    # Port 0 asks the OS for a free one, which avoids both a clash and the
    # guessing game of picking a "probably free" number.
    server = _Server(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, name="pycmd-ui", daemon=True).start()
    return f"http://127.0.0.1:{port}/index.html?t={token}", server


class Api:
    """What the page calls. One method in, one method out.

    pywebview hands these straight to JavaScript, so every argument arrives as
    whatever JSON made of it and every return value has to survive the trip
    back. Keeping that to two methods means there is one place to look when
    something does not.
    """

    def __init__(self, host):
        self._host = host

    def call(self, name, payload=None):
        return host_module.call(self._host, str(name), payload or {})

    def events(self):
        """Everything that has happened since the last ask.

        The page polls this rather than being pushed to. Pushing would mean
        `evaluate_js` from whichever thread produced the event, and a console
        printing quickly would then be a thousand cross-thread calls a second.
        One poll that returns a hundred lines is cheaper and simpler.
        """
        return {"ok": True, "events": self._host.drain()}


def _boot(host, window=None):
    """Starts the engine off the UI thread, so the window paints immediately."""
    def work():
        try:
            host.start()
            host.emit("ready", **host_module.call(host, "hello"))
        except Exception as error:  # noqa: BLE001 - a failure here must be visible
            import traceback

            host.log("error", "PyCmd could not start", traceback.format_exc())
            host.emit("boot-failed", error=f"{type(error).__name__}: {error}")

    threading.Thread(target=work, name="pycmd-boot", daemon=True).start()


def build_roots() -> dict:
    """The folders the window may load from."""
    here = os.path.dirname(os.path.abspath(__file__))
    ui = os.path.join(os.path.dirname(here), "ui")
    if not os.path.isdir(ui):
        ui = store.asset("ui")
    assets = store.assets_path()
    return {
        "_ui": ui,
        "web": os.path.join(assets, "web"),
        "plugins": store.folder("plugins"),
        "docs": os.path.join(assets, "docs"),
        "workspace": store.folder("workspace"),
        "wdocs": os.path.join(store.bundled(), "windows", "docs"),
    }


class _Discard(io.TextIOBase):
    """A stream that accepts everything and keeps none of it."""

    def write(self, text):  # noqa: D102
        return len(text)

    def flush(self):  # noqa: D102
        pass

    def isatty(self):  # noqa: D102
        return False


def _usable(stream) -> bool:
    """Whether something can actually be written to."""
    if stream is None:
        return False
    try:
        stream.write("")
        stream.flush()
        return True
    except Exception:  # noqa: BLE001 - an invalid handle raises OSError, others may differ
        return False


def make_output_work() -> bool:
    """Gives the app somewhere to write, and never lets writing raise.

    A windowed build - `console=False`, which is what you want so no black box
    flashes up behind the window - starts with no console at all, and its
    stdout is an invalid handle rather than a missing one. So `print` does not
    quietly do nothing: it raises OSError 22, and at interpreter exit the
    flush raises again. `PyCmd.exe --version` printed nothing and exited 1
    because of exactly that.

    Three steps, in order:

    1. If stdout already works, leave it alone. That is the ordinary case when
       output is redirected, or when running from a checkout.
    2. On Windows, borrow the console of whoever started us. That is what makes
       `PyCmd.exe --version` in a terminal print into that terminal.
    3. Failing both, swallow. A GUI with nowhere to write should not die of it,
       and the debug log is a screen rather than a stream.

    Returns whether anything can actually be read by a human.
    """
    if _usable(sys.stdout) and _usable(sys.stderr):
        return True

    attached = False
    if os.name == "nt":
        try:
            import ctypes

            # -1 is ATTACH_PARENT_PROCESS: use the console we were started
            # from, if there was one.
            attached = bool(ctypes.windll.kernel32.AttachConsole(-1))
        except Exception:  # noqa: BLE001
            attached = False

        if attached:
            for name, mode in (("stdout", "w"), ("stderr", "w")):
                try:
                    setattr(sys, name, open("CONOUT$", mode, encoding="utf-8",
                                            errors="replace", buffering=1))
                except OSError:
                    attached = False

    if not _usable(sys.stdout):
        sys.stdout = _Discard()
    if not _usable(sys.stderr):
        sys.stderr = _Discard()
    return attached


def selftest() -> int:
    """Starts everything once and says whether it worked.

    This exists for the packed exe. `--version` proves the bootloader ran;
    this proves the bundle is actually complete - that the engine unpacks and
    imports, that the language table and the toolchains are there, and that
    the plugins that ship inside can be installed. A missing hidden import
    shows up here and nowhere else, because from a checkout everything is on
    the disk anyway.

    The answer is the exit code, which works whether or not anything can be
    printed.
    """
    import tempfile

    # Kept aside before anything boots. Starting the engine replaces
    # sys.stdout with the sink that feeds the console screen, so a print after
    # that goes into an event queue nobody is reading rather than to whoever
    # ran the exe.
    speaking = sys.stdout

    def say(text):
        try:
            speaking.write(text + "\n")
            speaking.flush()
        except Exception:  # noqa: BLE001 - there may be nowhere to write
            pass

    problems = []
    try:
        store.use(tempfile.mkdtemp(prefix="pycmd-selftest-"))
        instance = host_module.Host()
        started = instance.start()
        if not started.get("ok"):
            problems.append(f"the engine would not start: {started}")

        from . import langs, toolchains

        if langs.stats()["total"] < 60:
            problems.append(f"only {langs.stats()['total']} languages were packed")
        if len(toolchains.TOOLCHAINS) < 40:
            problems.append(f"only {len(toolchains.TOOLCHAINS)} toolchains were packed")

        plugins = host_module.call(instance, "plugins")
        if len(plugins.get("installed", [])) < 5:
            problems.append(
                f"only {len(plugins.get('installed', []))} bundled plugins installed")
        if plugins.get("builtin", {}).get("count") != 13:
            problems.append("the thirteen built-in plugins are not all there")

        for name in ("languages", "toolchains", "system", "files"):
            reply = host_module.call(instance, name)
            if not reply.get("ok"):
                problems.append(f"{name} answered {reply.get('error')}")

        # 4.0: PyCmd Learn's courses are loaded by name, which is exactly the
        # kind of import a bundle silently drops - so count them here.
        catalogue = host_module.call(instance, "learn")
        courses = catalogue.get("courses", [])
        if len(courses) < 50:
            problems.append(f"only {len(courses)} Learn courses were packed")
        if catalogue.get("totals", {}).get("lessons", 0) < 85000:
            problems.append(
                f"Learn has {catalogue.get('totals', {}).get('lessons', 0)} lessons, not about "
                "90,000 - a course module or the practice rounds are missing")
        thin = [row.get("id") for row in courses if row.get("lessons", 0) < 1700]
        if thin:
            problems.append(f"these courses have no practice rounds: {thin}")
        # 4.5: accounts, export and import go through pycmd_teach.cloud, which
        # the engine imports lazily - so ask it something.
        for name in ("android.plan", "portables", "look", "templates", "machine", "whatsnew",
                     "account"):
            reply = host_module.call(instance, name)
            if not reply.get("ok"):
                problems.append(f"{name} answered {reply.get('error')}")

        roots = build_roots()
        for key in ("_ui", "web", "docs"):
            if not os.path.isdir(str(roots.get(key, ""))):
                problems.append(f"{key} is not in the bundle: {roots.get(key)}")
    except Exception as error:  # noqa: BLE001 - anything at all is a failure
        import traceback

        problems.append(f"{type(error).__name__}: {error}\n{traceback.format_exc()}")

    if problems:
        for problem in problems:
            say(f"FAIL  {problem}")
        return 1
    say(f"PyCmd for Windows {host_module.VERSION} - everything in the bundle is there")
    return 0


def run_python(argv) -> int:
    """`PyCmd.exe --python script.py [args]`: the exe as a plain Python.

    The build is a whole CPython with the standard library, so a .py file
    runs on it exactly as it would on python.org's - this is what Run uses
    when there is no Python on the PATH, or only the Store's placeholder.
    """
    import runpy
    import traceback

    for name, fd in (("stdout", 1), ("stderr", 2)):
        stream = getattr(sys, name)
        if not _usable(stream):
            try:
                stream = open(fd, "w", encoding="utf-8", errors="replace", closefd=False)
            except OSError:
                continue
            setattr(sys, name, stream)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except (AttributeError, ValueError):
            pass
    if sys.stdin is None:
        try:
            sys.stdin = open(0, "r", encoding="utf-8", closefd=False)
        except OSError:
            pass
    if not argv:
        print(f"Python {sys.version} (PyCmd)")
        return 0
    if argv[0] == "-c" and len(argv) > 1:
        sys.argv = ["-c", *argv[2:]]
        code = argv[1]
        target = None
    else:
        sys.argv = list(argv)
        target = os.path.abspath(argv[0])
        sys.path.insert(0, os.path.dirname(target))
    try:
        if target:
            runpy.run_path(target, run_name="__main__")
        else:
            exec(compile(code, "<string>", "exec"), {"__name__": "__main__"})
    except SystemExit as stop:
        code = stop.code
        if code is None or isinstance(code, int):
            return code or 0
        print(code, file=sys.stderr)
        return 1
    except BaseException:  # noqa: BLE001 - it is somebody's program
        kind, value, tb = sys.exc_info()
        traceback.print_exception(kind, value, tb.tb_next)
        return 1
    finally:
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.flush()
            except Exception:  # noqa: BLE001
                pass
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--python":
        return run_python(argv[1:])
    parser = argparse.ArgumentParser(prog="pycmd", description="PyCmd for Windows")
    parser.add_argument("--home", help="keep everything here instead of %LOCALAPPDATA%")
    parser.add_argument("--serve-only", action="store_true",
                        help="start the UI server and print its address, without a window")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--updated", action="store_true",
                        help="started again by the installer after an update")
    parser.add_argument("--selftest", action="store_true",
                        help="start everything once, check the bundle, and exit")
    args = parser.parse_args(argv)

    # Before anything writes a word. A windowed build has no usable stdout.
    make_output_work()

    if args.version:
        print(f"PyCmd for Windows {host_module.VERSION}")
        return 0

    if args.selftest:
        return selftest()

    if args.home:
        store.use(args.home)

    host = host_module.Host()
    roots = build_roots()
    roots["_host"] = host
    url, server = serve(roots)

    if args.serve_only:
        _boot(host)
        print(url, flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            server.shutdown()
        return 0

    try:
        import webview
    except ImportError:
        sys.stderr.write(
            "PyCmd needs pywebview to open a window.\n"
            "    pip install pywebview\n"
            "On Windows it uses Edge WebView2, which Windows 10 and 11 already have.\n"
            f"\nThe interface is running at {url} if you would rather use a browser.\n"
        )
        return 2

    api = Api(host)
    window = webview.create_window(
        TITLE, url, js_api=api,
        width=WINDOW[0], height=WINDOW[1],
        # The default theme's --bg, so the window does not flash blue at start.
        min_size=MINIMUM, background_color="#080D0A",
        text_select=True,
    )
    # The file dialogs are the window's, so the host keeps a hold of it.
    host.window = window
    _boot(host, window)
    updates.start_background_check(host)
    webview.start(debug=bool(os.environ.get("PYCMD_DEBUG")))
    server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
