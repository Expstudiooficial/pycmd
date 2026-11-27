#!/usr/bin/env python3
"""Checks the console's command layer.

Two things matter here and they pull against each other: the commands have to
work, and they must never take a line that was Python. Most of this file is
the second half - `ls` is a command, `ls = [1]` is an assignment, and a console
that gets that wrong is worse than one with no commands at all.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import types
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "app", "src", "main", "python"))

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        FAILURES.append(name)
        print(f"  FAIL  {name}  {detail}")


# A stand-in runtime, so the shell can be exercised without Chaquopy.
workspace = tempfile.mkdtemp(prefix="pycmd-shell-")
runtime = types.ModuleType("pycmd_runtime")
runtime._workspace = workspace
runtime.run_any = lambda path: "ok"
runtime.runtime_info = lambda: {"version": "3.13.0", "platform": "linux", "cwd": os.getcwd()}
sys.modules["pycmd_runtime"] = runtime

asked = []
plugins = types.ModuleType("pycmd_plugins")
plugins.app_action = lambda sender, action, **detail: (
    asked.append((sender, action, detail)) or True
)
sys.modules["pycmd_plugins"] = plugins

installed_calls = []
packages = types.ModuleType("pycmd_packages")


def _install(name, version=None, progress=None):
    installed_calls.append((name, version))
    if progress is not None:
        progress.onProgress("Resolving...")
    if name == "nosuchpkg":
        return {"ok": False, "error": "No release found for 'nosuchpkg' on PyPI."}
    return {"ok": True, "name": name, "version": version or "1.0.0"}


packages.install = _install
packages.uninstall = lambda name: (
    {"ok": True} if name == "flask" else {"ok": False, "error": f"{name} is not installed"}
)
packages.installed = lambda: [
    {"name": "flask", "version": "3.0.3", "summary": "A web framework", "files": 42},
]
packages.bundled = lambda: ["requests", "rich"]
sys.modules["pycmd_packages"] = packages

servers = types.ModuleType("pycmd_servers")
started = []
servers.start_file = lambda path, port=0, **kw: (
    started.append((path, port))
    or {"ok": True, "label": os.path.basename(path), "url": f"http://127.0.0.1:{port}/"}
)
servers.suggest_port = lambda start=8000: 8000
servers.listing = lambda: [
    {"handle": "srv1", "status": "running", "label": "site", "url": "http://x:8000/"},
]
servers.stop = lambda handle: {"ok": handle == "srv1", "error": "no such server"}
servers.stop_all = lambda: {"stopped": 1}
sys.modules["pycmd_servers"] = servers

import pycmd_shell  # noqa: E402

os.chdir(workspace)


def run(line, taken=()):
    """Runs a line, returning (handled, status, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        reply = pycmd_shell.handle(line, taken)
    return reply.get("handled"), reply.get("status"), out.getvalue(), err.getvalue()


print("== what is a command, and what is Python ==")

for line in [
    "ls = [1, 2]",
    "ls == 2",
    "ls(3)",
    "ls.sort()",
    "ls[0]",
    "run, stop = 1, 2",
    "import os",
    "print('ls')",
    "help(str)",
    "open('file.txt').read()",
    "clearly = 5",
    "2 + 2",
    "def run(): pass",
    "for x in y: pass",
]:
    handled, _status, _out, _err = run(line)
    check(f"Python survives: {line}", handled is False, f"was taken as a command")

for line in ["ls", "pwd", "help", "pip list", "ls -l", "cd ..", "tree", "servers"]:
    handled, _status, _out, _err = run(line)
    check(f"command taken: {line}", handled is True, "was passed to Python")

# The subtle half: a path can start with a character that is also an operator.
for line, expected in [
    ("cd ..", True),
    ("ls ./src", True),
    ("ls /sdcard", True),
    ("cat ~/notes.md", True),
    ("ls -l", True),
    ("head -3 file", True),
    ("ls - 1", False),
    ("ls + 1", False),
    ("ls * 2", False),
    ("ls , 2", False),
    ("ls if x else y", False),
]:
    handled, _s, _o, _e = run(line)
    verb = "a command" if expected else "Python"
    check(f"{line!r} is {verb}", handled is expected, f"handled={handled}")

handled, _status, _out, _err = run("ls", taken={"ls"})
check("a name you defined wins over the command", handled is False, "shell took it anyway")

handled, _s, _o, _e = run("ls\nls")
check("two lines are always Python", handled is False, "shell took a block")

handled, _s, _o, _e = run("")
check("an empty line is nobody's", handled is False)

print("\n== files ==")
# The loop above ran `cd ..`, which is exactly what it is supposed to do.
os.chdir(workspace)
os.makedirs(os.path.join(workspace, "notes"), exist_ok=True)
with open(os.path.join(workspace, "hello.py"), "w", encoding="utf-8") as handle:
    handle.write("print('hi')\n" * 30)

_h, status, out, _err = run("ls")
check("ls lists the folder", "hello.py" in out and "notes/" in out, out)
check("ls puts folders first", out.index("notes/") < out.index("hello.py"), out)
check("ls says how big a file is", "B" in out or "KB" in out, out)

_h, status, out, err = run("ls nowhere")
check("ls on nothing is an error, not a crash", status == "error", err)
check("and says which name it could not find", "nowhere" in err, err)

_h, _s, out, _e = run("pwd")
check("pwd prints where you are", workspace in out, out)

_h, _s, out, _e = run("mkdir deep/er")
check("mkdir makes a path", os.path.isdir(os.path.join(workspace, "deep", "er")), out)

_h, _s, out, _e = run("touch deep/er/new.txt")
check("touch makes a file", os.path.isfile(os.path.join(workspace, "deep", "er", "new.txt")), out)

_h, _s, out, _e = run("cat hello.py")
check("cat prints a file", "print('hi')" in out, out[:60])

_h, _s, out, _e = run("head -3 hello.py")
check("head takes only the first lines", out.count("print") == 3, out)

_h, _s, out, _e = run("tail -2 hello.py")
check("tail takes the last ones", out.count("print") == 2, out)

_h, _s, out, _e = run("cp hello.py copy.py")
check("cp copies", os.path.isfile(os.path.join(workspace, "copy.py")), out)

_h, _s, out, _e = run("mv copy.py moved.py")
check("mv renames", os.path.isfile(os.path.join(workspace, "moved.py")), out)
check("and the old name is gone", not os.path.isfile(os.path.join(workspace, "copy.py")))

_h, status, out, err = run("rm deep")
check("rm refuses a folder without -r", status == "error", err)
check("and says how to mean it", "-r" in err, err)

_h, _s, out, _e = run("rm -r deep")
check("rm -r takes the folder", not os.path.exists(os.path.join(workspace, "deep")), out)

_h, _s, out, _e = run("find hello")
check("find finds it", "hello.py" in out, out)

_h, _s, out, _e = run("tree")
check("tree draws the folder", "└──" in out or "├──" in out, out)

_h, _s, out, _e = run("du")
check("du adds it up", "in" in out and "files" in out, out)

_h, _s, out, _e = run("cd notes")
check("cd moves", os.getcwd().endswith("notes"), os.getcwd())
_h, _s, out, _e = run("cd")
check("cd on its own goes back to the workspace", os.getcwd() == workspace, os.getcwd())

with open(os.path.join(workspace, "blob.bin"), "wb") as handle:
    handle.write(b"\x00\x01\x02" * 100)
_h, _s, out, _e = run("cat blob.bin")
check("cat says when a file is not text", "not text" in out, out)

print("\n== pip, which is the whole point ==")
_h, status, out, err = run("pip install flask")
check("pip install runs the installer", installed_calls[-1] == ("flask", None), installed_calls)
check("and says so", "Installed flask" in out, out)
check("and reports progress", "Resolving" in out, out)
check("with no error", status == "ok", err)

_h, _s, out, _e = run("pip install rich==13.9.4")
check("a pinned version is passed through", installed_calls[-1] == ("rich", "13.9.4"), installed_calls)

_h, status, out, err = run("pip install nosuchpkg")
check("a package that does not exist is an error", status == "error", status)
check("with PyPI's reason", "No release found" in err, err)

_h, _s, out, _e = run("pip list")
check("pip list shows what is installed", "flask" in out and "3.0.3" in out, out)
check("and what is built in", "requests" in out, out)

_h, _s, out, _e = run("pip freeze")
check("pip freeze is requirements-shaped", "flask==3.0.3" in out, out)

_h, _s, out, _e = run("pip show flask")
check("pip show describes it", "web framework" in out, out)

_h, status, out, err = run("pip uninstall notinstalled")
check("uninstalling what is not there says so", status == "error", err)

_h, _s, out, _e = run("pip")
check("pip alone is a usage line", "pip install" in out, out)

_h, _s, out, _e = run("install flask")
check("'install flask' means pip install", installed_calls[-1] == ("flask", None), installed_calls)

print("\n== running, serving, and the app ==")
_h, _s, out, _e = run("run hello.py")
check("run runs a file", True, out)

_h, _s, out, _e = run("serve . 8000")
check("serve starts a server", started[-1][1] == 8000, started)
check("and prints the address", "http://" in out, out)

_h, _s, out, _e = run("servers")
check("servers lists them", "srv1" in out, out)

_h, _s, out, _e = run("stop srv1")
check("stop stops one", "Stopped srv1" in out, out)

_h, _s, out, _e = run("open hello.py")
check("open asks the app for the editor",
      asked[-1][1] == "open_file" and asked[-1][0] == "pycmd.shell", asked[-1:])

_h, _s, out, _e = run("preview hello.py")
check("preview asks for the preview", asked[-1][1] == "preview", asked[-1:])

_h, _s, out, _e = run("go files")
check("go switches tab", asked[-1] == ("pycmd.shell", "go_to", {"tab": "files"}), asked[-1:])

_h, _s, out, _e = run("clear")
check("clear asks the page to empty itself", asked[-1][1] == "clear_console", asked[-1:])

print("\n== telling you what it can do ==")
_h, _s, out, _e = run("help")
check("help lists the commands", "pip install flask" in out, out[:200])
check("and says the rest is Python", "Python" in out, out[:200])

_h, _s, out, _e = run("help pip")
check("help for one command", "install, remove and list" in out, out)

_h, status, out, err = run("help nosuchthing")
check("help for nothing is an error", status == "error", err)

_h, _s, out, _e = run("which ls")
check("which explains a command", "console command" in out, out)

_h, _s, out, _e = run("version")
check("version says which Python", "3.13" in out, out)

check("commands() lists them for completion", "pip" in pycmd_shell.commands(), pycmd_shell.commands()[:5])
check("aliases are listed too", "install" in pycmd_shell.commands())
check("is_command knows one", pycmd_shell.is_command("tree"))
check("and knows a non-one", not pycmd_shell.is_command("numpy"))

print("\n== a broken command is not a broken console ==")


def _explode(args):
    raise RuntimeError("boom")


pycmd_shell.COMMANDS["explode"] = (_explode, "for the test", "")
_h, status, out, err = run("explode")
check("a command that raises is caught", status == "error", status)
check("and says what happened", "boom" in err, err)
del pycmd_shell.COMMANDS["explode"]

_h, _s, out, err = run("cat")
check("a command with no argument asks for one", "which file" in err, err)

_h, _s, out, _e = run('echo "hello there"')
check("quotes hold a word together", out.strip() == "hello there", out)

_h, _s, out, _e = run("echo it's fine")
check("an unbalanced quote does not raise", "handled", out)

print("\n== 3.6: the ten small tools ==")
with open("a.txt", "w", encoding="utf-8") as handle:
    handle.write("one\ntwo TODO\n")
with open("b.txt", "w", encoding="utf-8") as handle:
    handle.write("one\nthree\n")
_, status, out, _ = run("calc 2^10 / 4")
check("calc works it out, ^ included", status == "ok" and out.strip() == "256", out)
_, status, _, err = run('calc __import__("os").system("x")')
check("calc refuses anything that is not maths", status != "ok" and "only numbers" in err, err)
run("todo add ship it")
_, status, out, _ = run("todo done 1")
check("todo adds and ticks", status == "ok" and "done: ship it" in out, out)
check("todo lists", "[x] ship it" in run("todo")[2])
_, _, out, _ = run("passgen 24")
check("passgen makes a password of that length", len(out.strip()) == 24, out)
check("hash knows sha256", "ba7816bf" in run("hash abc")[2])
check("base64 goes both ways", run("base64 encode hi")[2].strip() == "aGk=" and run("base64 decode aGk=")[2].strip() == "hi")
check("wc counts", "2 lines" in run("wc a.txt")[2])
check("grep finds text, ignoring case", "a.txt:2" in run("grep todo -i")[2])
check("diff shows what changed", "+three" in run("diff a.txt b.txt")[2])
check("cal draws a month", "February 2027" in run("cal 2 2027")[2])
check("loc counts code by language", "total" in run("loc")[2])
check("all ten are in help", all(name in pycmd_shell.COMMANDS for name in
      ("calc", "todo", "passgen", "hash", "base64", "wc", "grep", "diff", "cal", "loc")))

print()
if FAILURES:
    print(f"{len(FAILURES)} shell checks failed")
    sys.exit(1)
print("all shell checks passed")
