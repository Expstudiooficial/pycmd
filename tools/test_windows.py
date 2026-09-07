#!/usr/bin/env python3
"""Checks the Windows build, everywhere.

Runs on any machine, including the Linux one this was written on, because
almost nothing here is Windows-specific: the toolchain table is data, the
language registry is data, the host is a dict of functions, and the store is
path arithmetic. What genuinely needs Windows - that the exe opens, that
WebView2 is there - is checked by the GitHub Actions workflow on a Windows
runner, and by `tools/test_toolchains_live.py` beside it.

    python tools/test_windows.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "windows"))
sys.path.insert(0, os.path.join(ROOT, "app", "src", "main", "python"))

# Every test gets its own store, so nothing here can touch a real install.
_HOME = tempfile.mkdtemp(prefix="pycmd-win-tests-")
os.environ["PYCMD_HOME"] = _HOME

FAILURES = []
CHECKS = [0]

# The engine replaces sys.stdout the moment it is configured, so the real one
# is kept aside before anything imports it.
_OUT = sys.stdout


def say(text=""):
    print(text, file=_OUT)


def check(name, condition, detail=""):
    CHECKS[0] += 1
    if condition:
        say(f"  PASS  {name}")
    else:
        FAILURES.append(name)
        say(f"  FAIL  {name}  {detail}")


# ---------------------------------------------------------------------------

from pycmd_win import (builtins, bundle, install, known, langs, runner,  # noqa: E402
                       setup_all, store, toolchains)

say("== where things live ==")
made = store.prepare()
check("PYCMD_HOME is honoured", made["root"] == _HOME, made["root"])
check("every folder is made", all(os.path.isdir(made[name]) for name in store.FOLDERS))
check("the shared engine is found", os.path.isdir(store.engine_path()), store.engine_path())
check("the shared assets are found", os.path.isdir(store.assets_path()), store.assets_path())


def refuses(function) -> bool:
    """Whether calling this says no, rather than doing something surprising."""
    try:
        function()
    except ValueError:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


def placeholders(text: str):
    """The {names} in a command template."""
    import string

    return [name for _literal, name, _spec, _conv in string.Formatter().parse(text) if name]


check("a folder it does not know about is refused",
      refuses(lambda: store.folder("etc")))


say("\n== the toolchain table ==")
ids = [chain.id for chain in toolchains.TOOLCHAINS]
check("every id is unique", len(ids) == len(set(ids)),
      [i for i in ids if ids.count(i) > 1])
check("there are more than forty", len(ids) >= 40, len(ids))
languages = sorted({lang for chain in toolchains.TOOLCHAINS for lang in chain.languages})
check("covering more than thirty languages", len(languages) >= 30, len(languages))

bad_steps = []
for chain in toolchains.TOOLCHAINS:
    if not chain.steps:
        bad_steps.append((chain.id, "no steps"))
        continue
    for step in chain.steps:
        if not step:
            bad_steps.append((chain.id, "an empty step"))
        for part in step:
            # Every placeholder has to be one plan_for actually fills in, or
            # the command is built with a literal {typo} in it and the failure
            # is a file-not-found with a baffling name.
            for token in placeholders(part):
                if token not in ("exe", "src", "dir", "stem", "out"):
                    bad_steps.append((chain.id, f"unknown placeholder {{{token}}}"))
check("every command is made of placeholders that exist", not bad_steps, bad_steps)

builds_without_out = [
    chain.id for chain in toolchains.TOOLCHAINS
    if chain.builds and not any("{out}" in part or "{stem}" in part
                                for step in chain.steps for part in step)
]
check("every compiler says where it puts what it builds",
      not builds_without_out, builds_without_out)

no_install = [
    chain.id for chain in toolchains.TOOLCHAINS
    if not (chain.winget or chain.scoop or chain.choco or chain.site or chain.note)
]
check("every toolchain says how to get it", not no_install, no_install)

say("\n== finding them ==")
found = toolchains.detect_all()
check("detection answers for every one", len(found) == len(ids), len(found))
check("and says whether each is installed",
      all(isinstance(row["installed"], bool) for row in found))
summary = toolchains.summary()
check("the summary counts agree",
      summary["installed"] == sum(1 for r in found if r["installed"]), summary)
say(f"        (this machine has {summary['installed']} of {summary['toolchains']})")

say("\n== a probe that will not answer is abandoned, not waited for ==")
# The exact shape that hung a CI run for ten minutes: a program that exits
# immediately but leaves a child holding the output pipe. `subprocess.run`
# with a timeout kills the program, then blocks for ever waiting for a pipe
# that the grandchild still has open. On Windows every JVM-language toolchain
# is a .bat wrapper that does this, so it is the normal case, not a corner.
import time as _time  # noqa: E402

_hanging = (
    "import subprocess, sys; "
    "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'], "
    "stdout=sys.stdout); print('gone')"
)
_started = _time.monotonic()
_said = toolchains._probe_version(sys.executable, ("-c", _hanging))
_took = _time.monotonic() - _started
check("it gives up near its deadline rather than hanging",
      _took < toolchains.PROBE_TIMEOUT + 4, f"{_took:.1f}s")
check("and still returns whatever it managed to read",
      isinstance(_said, str), repr(_said)[:60])

_started = _time.monotonic()
toolchains.clear_cache()
toolchains.detect_all(refresh=True)
_took = _time.monotonic() - _started
check("and detecting all of them is quick enough for a screen",
      _took < 60, f"{_took:.1f}s for {len(toolchains.TOOLCHAINS)}")
say(f"        (all {len(toolchains.TOOLCHAINS)} probed in {_took:.1f}s)")

say("\n== what PyCmd remembers about this machine ==")

# The complaint: detecting and installing felt like it started from zero every
# time. It did - the cache lived only as long as the process, so every launch
# re-ran fifty-one probes and every new version began knowing nothing.
known.forget()
toolchains.clear_cache()
_started = _time.monotonic()
toolchains.detect_all()
_cold = _time.monotonic() - _started
toolchains.clear_cache()          # forget the process, keep the machine
_started = _time.monotonic()
toolchains.detect_all()
_warm = _time.monotonic() - _started
check("a second survey is answered from memory", _warm < max(_cold / 4, 0.5),
      f"cold {_cold:.2f}s, warm {_warm:.2f}s")
say(f"        (cold {_cold:.2f}s, from memory {_warm:.3f}s)")
check("the memory lives beside the workspace, not inside a version",
      os.path.dirname(known.path()) == store.root(), known.path())

_recalled = [c.id for c in toolchains.TOOLCHAINS if known.recall(c.id)]
check("everything probed is remembered", len(_recalled) == len(toolchains.TOOLCHAINS),
      f"{len(_recalled)} of {len(toolchains.TOOLCHAINS)}")

# A toolchain that gets upgraded under us must not be answered from a stale
# version string. That is the one thing a cache like this must never do.
_present = [c.id for c in toolchains.TOOLCHAINS if toolchains.detect(c.id).get("path")]
if _present:
    _id = _present[0]
    _row = known.load()["found"][_id]
    _row["stamp"] = "0:0"
    check("a toolchain replaced since last time is re-probed",
          known.recall(_id) is None, _row)
    known.remember(_id, toolchains.detect(_id, refresh=True))
    check("and remembered again afterwards", known.recall(_id) is not None)
else:
    check("a toolchain replaced since last time is re-probed", True, "none installed")

known.remember("madeup", {"path": os.path.join(_HOME, "gone.exe")})
check("a remembered path that has vanished is not trusted",
      known.recall("madeup") is None)
open(known.path(), "w", encoding="utf-8").write("{not json at all")
known.load(refresh=True)
check("a corrupt memory file reads as an empty one rather than crashing",
      known.load()["found"] == {}, known.load())
open(known.path(), "w", encoding="utf-8").write('{"format": 999, "found": {"go": {}}}')
known.load(refresh=True)
check("and one written by a newer PyCmd is ignored, not guessed at",
      known.load()["found"] == {}, known.load())
known.forget()

say("\n== installing, including installing the installer ==")
_managers = install.available()
check("the three package managers are known", len(_managers) == 3,
      [m["id"] for m in _managers])
check("scoop is the one that can be set up without administrator",
      install._BY_ID["scoop"].can_bootstrap and not install._BY_ID["scoop"].needs_admin)
check("chocolatey is honest about needing administrator",
      install._BY_ID["choco"].needs_admin)
check("winget is not something PyCmd downloads",
      not install._BY_ID["winget"].can_bootstrap)
check("scoop is tried first", install.PREFERENCE[0] == "scoop", install.PREFERENCE)

# Every toolchain must be installable somehow, or say plainly that it is not.
_routeless = [c.id for c in toolchains.TOOLCHAINS
              if not any(install._package_for(c, m) for m in install.PREFERENCE)]
check("everything has an install route except what ships with Windows",
      sorted(_routeless) == ["cmd", "powershell"], _routeless)

_noplan = []
for _chain in toolchains.TOOLCHAINS:
    _made = install.plan(_chain.id)
    if not _made.get("ok") and _made.get("reason") != "no-package":
        _noplan.append((_chain.id, _made.get("error")))
    if _made.get("ok") and not _made.get("already"):
        for _route in _made["routes"]:
            if "{package}" in _route["command"] or not _route["package"]:
                _noplan.append((_chain.id, _route["command"]))
check("every plan names a real command with the package filled in",
      not _noplan, _noplan[:4])
check("an unknown toolchain is an answer, not an exception",
      not install.plan("nosuchthing")["ok"])

say("\n== setting a machine up in one go ==")
_ids = {c.id for c in toolchains.TOOLCHAINS}
_wrong = [n for n in setup_all.FIRST + setup_all.LAST if n not in _ids]
check("the run order names only real toolchains", not _wrong, _wrong)
_order = setup_all.order()
check("and covers every one of them, once",
      len(_order) == len(_ids) and set(_order) == _ids,
      f"{len(_order)} vs {len(_ids)}")
check("the small fast ones go first", _order[0] in ("node", "python"), _order[:3])
check("and the enormous ones last", "dotnet" in _order[len(_order) // 2:], _order[-6:])
check("nothing is running before it is asked to", not setup_all.state()["running"])
check("stopping nothing is not an error", setup_all.stop()["ok"])

say("\n== planning a run ==")
plan = toolchains.plan_for(os.path.join(_HOME, "x.py"), "python")
check("a language with a toolchain gets a plan", plan["ok"] or plan["reason"] == "missing", plan)
plan = toolchains.plan_for(os.path.join(_HOME, "x.zzz"), "nosuchlanguage")
check("a language with none says so", not plan["ok"] and plan["reason"] == "unsupported", plan)

spaced = os.path.join(_HOME, "a folder with spaces", "hello.py")
os.makedirs(os.path.dirname(spaced), exist_ok=True)
open(spaced, "w").close()
plan = toolchains.plan_for(spaced, "python")
if plan.get("ok"):
    flat = [part for command in plan["commands"] for part in command]
    check("a path with spaces stays one argument",
          any(part == spaced for part in flat), flat)
    check("and nothing is quoted or escaped into a string",
          all(isinstance(part, str) and '"' not in part for part in flat), flat)
else:
    check("a path with spaces stays one argument", True, "no python toolchain to check with")

# An .fsx is a script and an .fs is a compile unit, and the .NET SDK only
# builds the second. CI caught this the only way it could be caught - by
# running one - and answered "Couldn't find a project to run", which is the
# SDK being right about a file we should not have handed it.
_dotnet = toolchains.by_id("dotnet")
_fsi = toolchains.by_id("fsi")
check("the SDK refuses F# scripts", ".fsx" in _dotnet.refuses, _dotnet.refuses)
check("and F# Interactive is for them", ".fsx" in _fsi.suits, _fsi.suits)
for _chain in toolchains.TOOLCHAINS:
    _bad = [e for e in _chain.refuses + _chain.suits if not e.startswith(".")]
    check(f"{_chain.id} names extensions, not languages", not _bad, _bad)

_fsx = os.path.join(_HOME, "note.fsx")
_fs = os.path.join(_HOME, "Program.fs")
open(_fsx, "w").close()
open(_fs, "w").close()
_plan_fsx = toolchains.plan_for(_fsx, "fsharp")
_plan_fs = toolchains.plan_for(_fs, "fsharp")
check("a .fsx never plans to the SDK, however hard it is asked",
      toolchains.plan_for(_fsx, "fsharp", prefer="dotnet").get("toolchain") != "dotnet"
      if _plan_fsx.get("ok") else True, _plan_fsx)
check("a .fs may", _plan_fs.get("toolchain") in ("dotnet", "fsi")
      if _plan_fs.get("ok") else True, _plan_fs)

# The project file the SDK insists on, for each of the three languages that
# need one - and for nobody else.
_written = []
for _lang, _file, _want in (("fsharp", "Program.fs", ".fsproj"),
                            ("csharp", "Program.cs", ".csproj"),
                            ("visualbasic", "Program.vb", ".vbproj")):
    _folder = os.path.join(_HOME, "proj-" + _lang)
    os.makedirs(_folder, exist_ok=True)
    _path = os.path.join(_folder, _file)
    open(_path, "w").close()
    runner._ensure_project(_path, _lang, "dotnet", lambda text: None)
    _made = [n for n in os.listdir(_folder) if n.endswith(_want)]
    check(f"a loose {_file} gets a {_want}", bool(_made), os.listdir(_folder))
    if _made:
        _text = open(os.path.join(_folder, _made[0]), encoding="utf-8").read()
        _written.append((_lang, _text))
        check(f"and it is a project the SDK can read",
              _text.startswith("<Project Sdk=") and "</Project>" in _text, _text[:60])

for _lang, _text in _written:
    if _lang == "fsharp":
        # F# compiles in order and does not glob. A project that names no
        # source builds nothing and says almost nothing about why.
        check("the F# project names its source file",
              '<Compile Include="Program.fs" />' in _text, _text)

_folder = os.path.join(_HOME, "proj-script")
os.makedirs(_folder, exist_ok=True)
_path = os.path.join(_folder, "note.fsx")
open(_path, "w").close()
runner._ensure_project(_path, "fsharp", "fsi", lambda text: None)
check("but F# Interactive is left no stray project",
      os.listdir(_folder) == ["note.fsx"], os.listdir(_folder))

say("\n== the languages ==")
stats = langs.stats()
check("there are more than sixty file types", stats["total"] >= 60, stats)
check("more than forty of them run", stats["runnable"] >= 40, stats)

extensions = {}
clashes = []
for language in langs.LANGUAGES:
    for extension in language.extensions:
        if extension.lower() in extensions:
            clashes.append((extension, extensions[extension.lower()], language.id))
        extensions[extension.lower()] = language.id
check("no two languages claim the same extension", not clashes, clashes[:4])

check("for_path finds a known one", langs.for_path("a/b/thing.rs")["id"] == "rust")
check("and falls back to text rather than nothing",
      langs.for_path("a/b/thing.zzzz")["id"] == "text")
check("Makefile is known by its name, not an extension",
      langs.for_path("a/Makefile")["id"] == "makefile")

# What matters is that no language still tells somebody it *cannot* be run
# because of Android - not that the word never appears. Comparing the two
# builds is useful, and several notes do it on purpose.
STILL_FORBIDDEN = (
    "does not let an app",
    "not runnable on the device",
    "cannot be run on the device",
    "Android will not let",
    "needs a compiler, and Android",
)
android_notes = [
    language.id for language in langs.LANGUAGES
    if any(phrase in (language.note or "") for phrase in STILL_FORBIDDEN)
]
check("no language still says Android forbids running it",
      not android_notes, android_notes)

missing_toolchain = [
    language.id for language in langs.LANGUAGES
    if language.mode == "run" and not toolchains.for_language(language.id)
    and language.id not in ("python",)
]
check("everything marked runnable has something that runs it",
      not missing_toolchain, missing_toolchain)

say("\n== the thirteen built in ==")
builtins.reset()
listing = builtins.listing()
check("there are thirteen", listing["count"] == 13, listing["count"])
check("they are grouped", len(listing["groups"]) >= 4, len(listing["groups"]))
check("the kit is on by default", listing["kit_complete"])
check("ids match the phone build's",
      builtins.POLYGLOT_FILES == "pycmd.polyglot.files", builtins.POLYGLOT_FILES)

builtins.set_enabled(builtins.POLYGLOT_FILES, False)
check("switching off what something needs switches that off too",
      not builtins.is_on(builtins.POLYGLOT_RUNNER))
builtins.set_enabled(builtins.POLYGLOT_RUNNER, True)
check("and switching it back on brings its requirement with it",
      builtins.is_on(builtins.POLYGLOT_FILES))
check("powered_up needs Power Pack as well as the plugin",
      builtins.powered_up(builtins.SNIPPETS) == builtins.is_on(builtins.POWER_PACK))
builtins.set_enabled(builtins.POWER_PACK, False)
check("and says no when Power Pack is off", not builtins.powered_up(builtins.SNIPPETS))
builtins.reset()

check("the switches survive a restart",
      os.path.isfile(os.path.join(_HOME, "builtins.json")))

say("\n== the plugins that ship inside ==")
staged = bundle.stage_bundled()
check("all five are in the build", len(staged) == 5, [os.path.basename(p) for p in staged])

say("\n== reading a plugin from the phone ==")
sample = os.path.join(ROOT, "app", "src", "main", "assets", "plugins", "creator")
found = bundle.inspect_mobile(sample)
check("a real plugin reads", found["ok"] and found["id"] == "pycmd.creator", found.get("error"))
check("and one with nothing Android in it is called fine",
      found["likely"] == "fine", found.get("warnings"))

fake = os.path.join(_HOME, "phone-plugin")
os.makedirs(fake, exist_ok=True)
with open(os.path.join(fake, "plugin.json"), "w", encoding="utf-8") as handle:
    json.dump({"id": "demo.phone", "name": "Phone Only", "version": "1.0.0",
               "entry": "main.py", "permissions": ["notifications", "wakelock"]}, handle)
with open(os.path.join(fake, "main.py"), "w", encoding="utf-8") as handle:
    handle.write("from java import jclass\n\ndef setup(pycmd):\n    pass\n")
found = bundle.inspect_mobile(fake)
check("one that reaches for Android is read as mixed",
      found["ok"] and found["likely"] == "mixed", found)
check("and it says which parts", len(found["warnings"]) >= 2,
      [w["about"] for w in found["warnings"]])
check("naming the Android permissions",
      any("notifications" in w["about"] for w in found["warnings"]),
      found["warnings"])
check("and the java import",
      any("main.py" in w["about"] for w in found["warnings"]), found["warnings"])

check("something that is not a plugin at all is refused",
      not bundle.inspect_mobile(os.path.join(_HOME, "nothing-here"))["ok"])

say("\n== the host ==")
from pycmd_win import host as host_module  # noqa: E402

instance = host_module.Host()
check("hello answers before the engine is up",
      host_module.call(instance, "hello")["ok"])
check("an unknown call is an answer, not a crash",
      not host_module.call(instance, "no.such.thing")["ok"])

booted = instance.start()
check("the engine starts", booted["ok"], booted)
check("and the bundled plugins went in",
      len(host_module.call(instance, "plugins")["installed"]) == 5)

# These start work or change something rather than answering a question, so
# calling them with an empty payload proves nothing and costs something.
DOES_RATHER_THAN_ANSWERS = {
    "console.run", "run.file", "toolchain.install", "console.stdin",
    "console.stop", "console.reset", "builtin.reset", "file.write",
    "file.create", "file.rename", "file.remove", "file.import",
    "server.start", "server.stop", "package.install", "package.remove",
    "page.create", "page.start", "page.stop", "page.rename", "page.remove",
}
for name in sorted(host_module.HANDLERS):
    if name in DOES_RATHER_THAN_ANSWERS:
        continue
    reply = host_module.call(instance, name, {})
    check(f"{name} answers", isinstance(reply, dict) and "ok" in reply, reply)

say("\n== the workspace ==")
from pycmd_win import files  # noqa: E402

check("it starts empty", files.listing()["ok"] and not files.listing()["entries"])

made = files.create("hello.go", "go")
check("a new file gets its language's template", made["ok"], made)
read = files.read("hello.go")
check("and reads back as Go",
      read["ok"] and "package main" in read["text"], read.get("error"))
check("with the language named", read["language"]["id"] == "go", read.get("language"))

check("a folder can be made", files.create("site", folder=True)["ok"])
listed = files.listing()
check("both show up", len(listed["entries"]) == 2, listed["entries"])
check("folders sort first", listed["entries"][0]["folder"], listed["entries"])
check("and a runnable file says so",
      any(row["runnable"] for row in listed["entries"]), listed["entries"])

check("writing sticks", files.write("hello.go", "// changed\n")["ok"])
check("and reading gives back what was written",
      files.read("hello.go")["text"] == "// changed\n")

check("renaming works", files.rename("hello.go", "renamed.go")["ok"])
check("the old name is gone", not files.read("hello.go")["ok"])
check("renaming onto something that exists is refused",
      not files.rename("renamed.go", "site")["ok"])

check("a name that is already taken is refused",
      not files.create("renamed.go", "go")["ok"])
check("an empty media file is refused rather than written",
      not files.create("song.mp3")["ok"])

# The direction that matters. A plugin panel can reach this bridge, so the
# app's own file API must not be a way round the workspace boundary.
for escape in ("../../../etc/passwd", "..\\..\\windows\\system32", "/etc/passwd",
               "site/../../outside.txt"):
    check(f"{escape!r} is refused", not files.read(escape)["ok"], escape)
    check(f"and cannot be written to", not files.write(escape, "x")["ok"], escape)
check("the workspace itself cannot be deleted", not files.remove("")["ok"])

brought = files.bring_in(os.path.join(ROOT, "README.md"))
check("a file can be brought in from anywhere", brought["ok"], brought)
again = files.bring_in(os.path.join(ROOT, "README.md"))
check("and a second copy does not overwrite the first",
      again["ok"] and again["name"] != brought["name"], again)

check("deleting works", files.remove("renamed.go")["ok"])
check("a folder deletes with what is in it", files.remove("site")["ok"])

say("\n== running something ==")
from pycmd_win import runner  # noqa: E402

script = os.path.join(_HOME, "workspace", "hello.py")
with open(script, "w", encoding="utf-8") as handle:
    handle.write('print("from a real toolchain")\n')
lines = []
result = runner.run_file(script, lines.append)
text = "".join(lines)
check("a Python file runs", result.get("ok"), text[:200])
check("and its output comes back", "from a real toolchain" in text, text[:200])
check("with the toolchain named", "PyCmd]" in text, text[:120])

missing = os.path.join(_HOME, "workspace", "nothing.py")
check("a file that is not there is an answer, not an exception",
      not runner.run_file(missing, lines.append).get("ok"))

say("\n== a client that hangs up mid-response ==")

# WebView2 aborts requests constantly - a panel iframe pointed at about:blank
# and rewritten, a navigation while an image is still coming, the window
# closing with a poll in flight. Each one broke a write already in progress
# and socketserver printed a full traceback for it, at a user who can do
# nothing about it and has done nothing wrong.
import socket as _socket  # noqa: E402
import io as _io  # noqa: E402

from pycmd_win import app as _app  # noqa: E402

check("a client leaving is not a wider failure than it is",
      _app._GONE is ConnectionError, _app._GONE)

_noise = _io.StringIO()
_real_stderr = sys.stderr
sys.stderr = _noise
try:
    _url, _server = _app.serve({"_ui": os.path.join(ROOT, "windows", "ui")})
    _port = _server.server_address[1]
    _tok = _url.split("t=")[1]
    for _ in range(20):
        _sock = _socket.create_connection(("127.0.0.1", _port))
        _sock.sendall(f"GET /app.css?t={_tok} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
        _sock.recv(1)
        # SO_LINGER 0 makes close() send RST rather than FIN, which is what
        # an abandoned request looks like from the server's side.
        _sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_LINGER,
                         b"\x01\x00\x00\x00\x00\x00\x00\x00")
        _sock.close()
    _time.sleep(0.8)
finally:
    sys.stderr = _real_stderr

check("twenty aborted requests print nothing", not _noise.getvalue().strip(),
      _noise.getvalue()[:200])

_sock = _socket.create_connection(("127.0.0.1", _port))
_sock.sendall(f"GET /app.css?t={_tok} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
_after = _sock.recv(20)
_sock.close()
check("and the server still serves afterwards", _after.startswith(b"HTTP/1.1 200"),
      _after)
_server.shutdown()

say("\n== every handler the UI calls exists ==")
import re as _re  # noqa: E402

_ui = (open(os.path.join(ROOT, "windows", "ui", "app.js")).read()
       + open(os.path.join(ROOT, "windows", "ui", "screens.js")).read())
_called = set(_re.findall(r"PyCmd\.call\(\s*'([a-z.]+)'", _ui))
_called |= {name for pair in _re.findall(r"PyCmd\.call\(live \? '([a-z.]+)' : '([a-z.]+)'", _ui)
            for name in pair}
_missing = sorted(_called - set(host_module.HANDLERS))
check("the page never calls something that is not there", not _missing, _missing)
check("and there is more than one screen's worth of them", len(_called) >= 40, len(_called))

say("\n== the update manifest ==")
manifest = subprocess.run(
    [sys.executable, os.path.join(ROOT, "tools", "make_latest_windows.py")],
    capture_output=True, text=True,
)
check("dist-windows/latest.json agrees with the source",
      manifest.returncode == 0, (manifest.stdout + manifest.stderr).strip()[:300])

# A checksums file that still names the previous build is worse than none:
# its whole job is to be the thing you trust.
_sums = open(os.path.join(ROOT, "dist-windows", "SHA256SUMS.txt"),
             encoding="utf-8").read()
_manifest = json.load(open(os.path.join(ROOT, "dist-windows", "latest.json"),
                           encoding="utf-8"))
if _manifest.get("sha256"):
    check("the checksums file names the built exe",
          _manifest["sha256"] in _sums, _sums[:80])
else:
    check("with nothing built, the checksums file claims nothing",
          _manifest["sha256"] == "" and not [
              line for line in _sums.splitlines()
              if line.strip() and not line.startswith("#")], _sums[:120])

say("\n== the exe is not in the repository ==")
_tracked = subprocess.run(["git", "ls-files", "dist-windows"], cwd=ROOT,
                          capture_output=True, text=True).stdout.split()
check("no exe is committed", not [n for n in _tracked if n.endswith(".exe")],
      [n for n in _tracked if n.endswith(".exe")])
check("only the manifest, the sums and the notes are",
      sorted(os.path.basename(n) for n in _tracked)
      == ["README.md", "SHA256SUMS.txt", "latest.json"], _tracked)

say("\n== nothing points at the phone's manifest ==")
from pycmd_win import updates  # noqa: E402

check("updates read the Windows manifest",
      updates.MANIFEST_URL.endswith("dist-windows/latest.json"), updates.MANIFEST_URL)
check("and it is on the windows branch", "windowsmain" in updates.MANIFEST_URL)

say()
if FAILURES:
    say(f"{len(FAILURES)} of {CHECKS[0]} checks failed: {FAILURES[:6]}")
    raise SystemExit(1)
say(f"all {CHECKS[0]} Windows checks passed")
