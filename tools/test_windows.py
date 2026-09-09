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
import shutil
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

# `android` is imported under another name on purpose. The mobile shim
# below puts a stub module called `android` into sys.modules, and
# `import android.os` inside it rebinds this name to the stub - which
# silently shadowed the module being tested and made every check after
# it disappear.
from pycmd_win import android as android_lab  # noqa: E402
from pycmd_win import (builtins, bundle, copies, envpath, install,  # noqa: E402
                       known, langs, mobile, runner, setup_all, store,
                       toolchains)

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
check("a phone plugin whose Android bits are all shimmed is full, not beta",
      found["full"] and found["likely"] == "fine", found.get("unsupported"))
check("and it says which parts were handled and how",
      any(row["uses"] in ("from java", "import java") for row in found["handled"]),
      found["handled"])

_hard = os.path.join(_HOME, "phone-hardware")
os.makedirs(_hard, exist_ok=True)
with open(os.path.join(_hard, "plugin.json"), "w", encoding="utf-8") as handle:
    json.dump({"id": "demo.hw", "name": "Sensors", "version": "1.0.0",
               "entry": "main.py"}, handle)
with open(os.path.join(_hard, "main.py"), "w", encoding="utf-8") as handle:
    handle.write("import android.hardware\n\ndef setup(pycmd):\n    pass\n")
_hardware = bundle.inspect_mobile(_hard)
check("one that genuinely needs a phone is still called mixed",
      not _hardware["full"] and _hardware["likely"] == "mixed", _hardware["verdict"])
check("and names the part that cannot work",
      _hardware["unsupported"][0]["uses"] == "android.hardware",
      _hardware["unsupported"])

# The permissions are a separate axis from the code: notifications and wake
# locks are declared in plugin.json, are mapped rather than shimmed, and are
# still worth saying out loud even for a plugin that runs in full.
check("Android-only permissions are still called out",
      any("notifications" in w["about"] for w in found["warnings"]),
      found["warnings"])
check("and the wake lock too",
      any("wakelock" in w["about"] for w in found["warnings"]), found["warnings"])
# The java import used to be a warning here. It is not one any more: the shim
# provides the module, so it is reported as handled and named by the file it
# is in. That change is the point of 2.0's plugin work.
check("the java import is reported as handled, not as a worry",
      any("main.py" in row["about"] for row in found["handled"]), found["handled"])
check("and no longer appears as a warning",
      not any("main.py" in w["about"] for w in found["warnings"]), found["warnings"])

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
    # 2.0's doers. Leaving android.start out of this list meant the suite
    # called it, and it went off and tried to install the Android SDK - which
    # is exactly what it is supposed to do when asked, and not what a
    # "does this handler answer?" sweep should be asking it.
    "android.start", "android.stop", "setup.start", "setup.stop",
    "manager.install", "install.one", "known.forget",
    "copies.replace", "copies.rollback", "copies.elevate", "console.secret",
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

say("\n== nothing can block for ever ==")

# Three separate CI hangs in this project came from a subprocess call with no
# ceiling, so this is now structural rather than remembered: every
# subprocess.run in the app carries a timeout, and every Popen is read on a
# thread joined against a deadline.
import ast as _ast  # noqa: E402

_unbounded = []
_pkg = os.path.join(ROOT, "windows", "pycmd_win")
for _name in sorted(n for n in os.listdir(_pkg) if n.endswith(".py")):
    _tree = _ast.parse(open(os.path.join(_pkg, _name), encoding="utf-8").read())
    for _node in _ast.walk(_tree):
        if not isinstance(_node, _ast.Call):
            continue
        _f = _node.func
        if (isinstance(_f, _ast.Attribute) and isinstance(_f.value, _ast.Name)
                and f"{_f.value.id}.{_f.attr}" == "subprocess.run"
                and "timeout" not in {k.arg for k in _node.keywords}):
            _unbounded.append(f"{_name}:{_node.lineno}")
check("every subprocess.run has a timeout", not _unbounded, _unbounded)

_all_source = "".join(
    open(os.path.join(_pkg, n), encoding="utf-8").read()
    for n in os.listdir(_pkg) if n.endswith(".py"))
check("and nothing waits on a pipe with communicate()",
      ".communicate()" not in _all_source)
check("nothing runs through a shell",
      "shell=True" not in _all_source.replace("`shell=True`", ""))

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

# Every UI file, not two of them. 2.0 split the console, the editor and the
# lab into their own files, and a check that reads only app.js and screens.js
# would have stopped covering exactly the screens that were being rewritten.
_ui_files = sorted(n for n in os.listdir(os.path.join(ROOT, "windows", "ui"))
                   if n.endswith(".js"))
_ui = "".join(open(os.path.join(ROOT, "windows", "ui", n), encoding="utf-8").read()
              for n in _ui_files)
check("every UI file is covered by this check", len(_ui_files) >= 5, _ui_files)
_called = set(_re.findall(r"PyCmd\.call\(\s*'([a-z.]+)'", _ui))
_called |= {name for pair in _re.findall(r"PyCmd\.call\(live \? '([a-z.]+)' : '([a-z.]+)'", _ui)
            for name in pair}
_missing = sorted(_called - set(host_module.HANDLERS))
check("the page never calls something that is not there", not _missing, _missing)
check("and there is more than one screen's worth of them", len(_called) >= 40, len(_called))

# Defined once each, and only once. A stray second `BUILD = ...` further down
# is invisible - Python takes the last one, while the manifest generator reads
# the first with a regex - so the app reported build 2 while latest.json
# claimed 3, and an update that is not newer than itself is never offered.
# Which is exactly what an editing slip produced here.
_host_source = open(os.path.join(ROOT, "windows", "pycmd_win", "host.py"),
                    encoding="utf-8").read()
for _name in ("VERSION", "BUILD"):
    _times = len([line for line in _host_source.splitlines()
                  if line.startswith(_name + " = ")])
    check(f"{_name} is defined exactly once in host.py", _times == 1, _times)

import importlib as _importlib  # noqa: E402
_live = _importlib.import_module("pycmd_win.host")
_manifest_now = json.load(open(os.path.join(ROOT, "dist-windows", "latest.json"),
                               encoding="utf-8"))
check("what the app reports is what the manifest promises",
      _manifest_now["version"] == _live.VERSION
      and int(_manifest_now["build"]) == _live.BUILD,
      f"{_live.VERSION}/{_live.BUILD} vs "
      f"{_manifest_now['version']}/{_manifest_now['build']}")

say("\n== a tag and a version, spelled differently ==")

# A tag and a version are two statements about the same thing, written by
# different hands, and they will not always be spelled alike. `windows-v2.0`
# against a source saying "2.0.0" is the same release, and refusing to build it
# over a trailing zero is the gate being wrong rather than careful - which is
# what it did, on a perfectly good tag.
_gen = os.path.join(ROOT, "tools", "make_latest_windows.py")


def _gate(tag):
    return subprocess.run([sys.executable, _gen, "--agrees-with-tag", tag],
                          cwd=ROOT, capture_output=True, text=True).returncode


_source_version = _live.VERSION
check("the tag as the source spells it is accepted",
      _gate("windows-v" + _source_version) == 0)
check("and the same version with a trailing zero is too",
      _gate("windows-v" + _source_version + ".0") == 0)
check("but a genuinely different version is still refused",
      _gate("windows-v99.1") == 1)

# The address must come from the tag, never be rebuilt from the version - the
# two are spelled differently often enough that guessing produces a 404.
import importlib.util as _iu  # noqa: E402

_spec = _iu.spec_from_file_location("pycmd_make_latest", _gen)
_mod = _iu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
check("a given tag is used verbatim in the download address",
      _mod.release_urls("2.0.0", "PyCmd.exe", "windows-v2.0")["url"]
      .endswith("windows-v2.0/PyCmd.exe"),
      _mod.release_urls("2.0.0", "PyCmd.exe", "windows-v2.0")["url"])
check("and only guessed when there is no tag to use",
      _mod.release_urls("2.0", "PyCmd.exe")["url"].endswith("windows-v2.0/PyCmd.exe"))

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

say("\n== the PATH a running process holds goes stale ==")

# This is what "the toolchains install but twenty-seven of them cannot be
# installed" actually was, and it had nothing to do with the installers.
# Windows hands a process a *copy* of PATH at startup and never updates it, so
# PyCmd installed Go perfectly and then asked a PATH that could not possibly
# know about it. Every success was reported as "it ran but the program did not
# appear".
_before = os.environ.get("PATH", "")
_result = envpath.refresh()
check("refreshing answers rather than raising", isinstance(_result, dict), _result)
check("and never loses an entry that was already there",
      all(part in os.environ.get("PATH", "")
          for part in _before.split(os.pathsep) if part.strip()))
check("it reports what it added", isinstance(_result.get("added"), list), _result)

_made = os.path.join(_HOME, "a-real-folder")
os.makedirs(_made, exist_ok=True)
check("a real folder can be put on the PATH", envpath.ensure(_made) == [_made])
check("and asking twice does not add it twice", envpath.ensure(_made) == [])
check("a folder that is not there is never added",
      envpath.ensure(os.path.join(_HOME, "not-here")) == [])
check("every known folder is a template with a variable in it",
      all("%" in template for template, _why in envpath.KNOWN),
      [t for t, _w in envpath.KNOWN if "%" not in t])

# Scoop keeps most of its catalogue in buckets you have to add first.
check("scoop's standard buckets are added", "extras" in install.BUCKETS
      and "java" in install.BUCKETS, install.BUCKETS)
check("and asking for them without scoop is not an error",
      install.add_buckets() == [])

say("\n== the console is a console, not a Python prompt ==")

# It answered with the *phone's* limitations on a Windows machine: "Ruby:
# editable and servable, but not runnable on the device", about a machine with
# Ruby installed. And an unknown command printed nothing at all.
_host_for_console = host_module.Host()
_lines = []
_host_for_console.onOutput = lambda stream, text, channel="console": _lines.append(text)

_routed = host_module._console_route(_host_for_console, "echo hello", "console")
check("the engine keeps its own commands", _routed is None, _routed)
for _line in ("cd somewhere", "pip install flask", "ls", "which python"):
    check(f"and keeps {_line.split()[0]!r}",
          host_module._console_route(_host_for_console, _line, "console") is None)

check("Python is not mistaken for a program",
      host_module._console_route(_host_for_console, "x = 5", "console") is None)
check("nor is an expression",
      host_module._console_route(_host_for_console, "print(2 + 2)", "console") is None)

_real = "python3" if not toolchains.WINDOWS else "cmd"
if shutil.which(_real):
    _took = host_module._console_route(
        _host_for_console, f"{_real} --version", "console")
    check("but a real program on the PATH is run",
          _took is not None and _took.get("routed") == "command", _took)
else:
    check("but a real program on the PATH is run", True, "none to try")

check("an unknown word is left to the engine to explain",
      host_module._console_route(
          _host_for_console, "definitelynotaprogram123", "console") is None)

say("\n== `run` resolves the way a console user expects ==")

os.makedirs(os.path.join(store.folder("workspace"), "sub"), exist_ok=True)
files.write("sub/inner.py", "print('inner')\n")
files.write("outer.py", "print('outer')\n")
_root_dir = os.path.abspath(store.folder("workspace"))
_was = os.getcwd()
try:
    os.chdir(os.path.join(_root_dir, "sub"))
    check("the current directory comes first, so cd means something",
          host_module._find_for_run("inner.py")
          == os.path.join(_root_dir, "sub", "inner.py"),
          host_module._find_for_run("inner.py"))
    check("and the workspace root is the fallback",
          host_module._find_for_run("outer.py")
          == os.path.join(_root_dir, "outer.py"),
          host_module._find_for_run("outer.py"))
    check("dot-dot inside the workspace is fine",
          host_module._find_for_run("../outer.py")
          == os.path.join(_root_dir, "outer.py"))
    for _escape in ("../../../../etc/passwd", "/etc/passwd", "..\\..\\Windows"):
        check(f"but {_escape!r} is not found here",
              host_module._find_for_run(_escape) == "",
              host_module._find_for_run(_escape))
    check("and neither is something that is simply not there",
          host_module._find_for_run("nope.py") == "")
finally:
    os.chdir(_was)

say("\n== running a file does not depend on the working directory ==")

# `run.file` was handed the path as it came and the runner did abspath, which
# resolves against the process working directory - wherever the exe was
# launched from. The engine happens to chdir into the workspace at boot, so
# this worked until somebody typed `cd` in the console, and then Run said the
# file you were looking at did not exist.
files.write("cwd-test.py", "print('ran')\n")
_was = os.getcwd()
try:
    os.chdir(_HOME)
    _resolved = files.resolve("cwd-test.py")
    check("a workspace-relative path resolves to the workspace",
          _resolved.startswith(os.path.abspath(store.folder("workspace"))),
          _resolved)
    check("and not to wherever the exe was started from",
          not _resolved.startswith(os.path.join(_HOME, "cwd-test")), _resolved)
finally:
    os.chdir(_was)

say("\n== a phone plugin runs here, rather than being warned about ==")

# 1.0 imported an Android plugin and called it a beta. What actually stops one
# working is narrow and known: a `java` module that does not exist here, three
# capabilities Windows does differently, and hard-coded Android paths.
_pairs = (
    ("/storage/emulated/0/Download/a.txt", store.folder("downloads")),
    ("/storage/emulated/0/notes.md", store.folder("workspace")),
    ("/sdcard/x", store.folder("workspace")),
    ("/data/user/0/com.expstudio.pycmd/files/plugins/p", store.folder("plugins")),
)
for _from, _under in _pairs:
    _to = mobile.translate(_from)
    check(f"{_from} lands somewhere real",
          _to.startswith(_under) and _to != _from, _to)
check("a path that is already ours is left alone",
      mobile.translate("C:/already/fine") == "C:/already/fine")

# Found by sweeping, and it was a real hole: stripping the Android prefix and
# joining the remainder meant `/storage/emulated/0/../../../etc/passwd`
# normalised straight back out of the store. A phone path comes out of
# somebody else's plugin, so it is untrusted input like any other.
_root = os.path.realpath(store.root())
_escapes = [
    "/storage/emulated/0/../../../etc/passwd",
    "/sdcard/../../etc/shadow",
    "/data/user/0/com.expstudio.pycmd/files/../../../../etc/passwd",
    "/storage/emulated/0/Download/../../../../../../etc/passwd",
]
_leaked = []
for _path in _escapes:
    _got = os.path.realpath(mobile.translate(_path))
    if not (_got == _root or _got.startswith(_root + os.sep)):
        _leaked.append((_path, _got))
check("an Android path with .. in it cannot reach outside the store",
      not _leaked, _leaked)
check("and the longest rule wins, so Download does not fall into the workspace",
      mobile.translate("/storage/emulated/0/Download").startswith(store.folder("downloads")))

_said = []
with mobile.shim(lambda kind, text: _said.append((kind, text))):
    import java as _java  # noqa: E402

    _toast = _java.jclass("android.widget.Toast")
    _toast.makeText(None, "from a phone plugin").show()
    _java.jclass("android.app.NotificationManager").notify(1, "a notification")
    _build = _java.jclass("android.os.Build")
    check("an unknown Android class does not explode", repr(_build.VERSION.SDK_INT) != "")
    check("and is falsey, so a plugin takes its non-Android branch",
          not _build.VERSION.SDK_INT)
    __import__("android.os")
    check("android.os imports", "android.os" in sys.modules)
check("a phone toast becomes a PyCmd toast", len(_said) == 2, _said)
check("the shim is gone once the import is over", "java" not in sys.modules)

_full = mobile.report("from java import jclass\nopen('/sdcard/x')\n")
check("a plugin whose Android bits are all covered is full, not beta",
      _full["full"], _full)
_part = mobile.report("import android.hardware\n")
check("and one needing phone hardware says exactly which part cannot",
      not _part["full"] and _part["unsupported"][0]["uses"] == "android.hardware",
      _part)

say("\n== Android Lab is honest about what it is ==")
_plan = android_lab.plan()
check("it says plainly that PyCmd is not an emulator",
      "does not contain Android" in _plan["honest"], _plan["honest"][:60])
check("and how much it would download before anything starts",
      "GB" in _plan["download"], _plan["download"])
check("the device is the one that was asked for",
      _plan["device"]["ramMb"] == 4096 and _plan["device"]["storageMb"] == 10240,
      _plan["device"])
check("on x86_64, so it runs on the CPU rather than being translated",
      _plan["device"]["arch"] == "x86_64" and "x86_64" in _plan["device"]["image"])
check("every step says what it is for and what it costs",
      all(s.get("what") and s.get("why") and s.get("size") for s in _plan["steps"]),
      _plan["steps"])
check("asking what is here does not start anything",
      not android_lab.job_state().get("everStarted"), android_lab.job_state())

say("\n== older copies of PyCmd ==")

# 2.0 shipped all of copies.py and not one button that called it, which is
# exactly why nothing ever appeared to happen.
_ui_all = "".join(
    open(os.path.join(ROOT, "windows", "ui", n), encoding="utf-8").read()
    for n in os.listdir(os.path.join(ROOT, "windows", "ui")) if n.endswith(".js"))
for _handler in ("copies", "copies.replace", "copies.kept", "copies.rollback"):
    check(f"something in the interface calls {_handler}",
          f"'{_handler}'" in _ui_all, _handler)
check("and there is a tab to reach it by",
      "id: 'copies'" in open(os.path.join(ROOT, "windows", "ui", "app.js"),
                             encoding="utf-8").read())

# A name is not identity, and running an unknown exe to decide whether to
# delete it is the wrong order to do those two steps in.
_marked = os.path.join(_HOME, "PyCmd (1).exe")
with open(_marked, "wb") as _handle:
    _handle.write(b"MZ" + b"x" * (3 * 1024 * 1024) + copies.MARKER)
_plain = os.path.join(_HOME, "PyCmd-notours.exe")
with open(_plain, "wb") as _handle:
    _handle.write(b"MZ" + b"x" * (3 * 1024 * 1024))
_tiny = os.path.join(_HOME, "PyCmdTiny.exe")
with open(_tiny, "wb") as _handle:
    _handle.write(b"MZ" + copies.MARKER)

check("a renamed copy is still recognised by name",
      copies._looks_like_pycmd("PyCmd (1).exe")
      and copies._looks_like_pycmd("PyCmd - Copy.exe"))
check("and confirmed by reading it, not by running it",
      copies._smells_like_pycmd(_marked))
check("something else wearing the name is left alone",
      not copies._smells_like_pycmd(_plain))
check("and so is something far too small to be a build",
      not copies._smells_like_pycmd(_tiny))

_unknown = [{"path": _marked, "version": ""}]
_out = copies.replace(_unknown, "2.0.7")
check("a build that will not say its version is never removed on a guess",
      not _out["removed"] and _out["refused"], _out)
_out = copies.replace([{"path": _marked, "version": "", "chosen": True}], "2.0.7")
check("but is removed when the person picks it",
      _out["removed"] == [_marked], _out)
check("and lands in the archive as 'unknown' rather than as a blank",
      any(row["version"] == "unknown" for row in copies.kept()),
      [r["version"] for r in copies.kept()])

# A target is passed in because this runs from a checkout, where there is no
# exe to replace - restore refuses that case on purpose, which is right and
# also makes the script itself untestable without one.
_pretend_exe = os.path.join(_HOME, "PyCmd-running.exe")
with open(_pretend_exe, "wb") as _handle:
    _handle.write(b"MZ")
_back = copies.restore(copies.kept()[0]["path"], _pretend_exe)
check("going back writes a swap script that actually exists",
      _back["ok"] and os.path.isfile(_back["script"]), _back)
check("and the script restarts PyCmd afterwards",
      'start ""' in open(_back["script"], encoding="utf-8").read())
_found = copies.find_others("2.0.0")
check("looking for them answers rather than raising", _found["ok"])
check("and only looks where a download actually lands",
      all(os.path.isdir(p) for p in _found["lookedIn"]), _found["lookedIn"])
_fake = os.path.join(_HOME, "PyCmd-older.exe")
open(_fake, "wb").write(b"MZ")
_out = copies.replace([{"path": _fake, "version": "1.0.0"}], "2.0.0")
check("an older copy is filed away, not destroyed",
      _out["removed"] and not os.path.exists(_fake) and copies.kept(), _out)
_newer = os.path.join(_HOME, "PyCmd-newer.exe")
open(_newer, "wb").write(b"MZ")
_out = copies.replace([{"path": _newer, "version": "9.9.9"}], "2.0.0")
check("a newer one is refused with a reason, not silently skipped",
      not _out["removed"] and _out["refused"] and os.path.exists(_newer), _out)
check("version ordering is numeric, so 1.0.10 is newer than 1.0.9",
      copies._order("1.0.10") > copies._order("1.0.9"))
_before = len(copies.kept())
for _i in range(copies.KEEP + 3):
    _f = os.path.join(_HOME, f"old{_i}.exe")
    open(_f, "wb").write(b"MZ")
    copies.keep(_f, f"0.{_i}.0")
check("only a handful of old builds are kept",
      len(copies.kept()) == copies.KEEP, len(copies.kept()))

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
