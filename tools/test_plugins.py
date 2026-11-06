"""Checks the custom-plugin runtime.

Installs plugins in all three shapes, loads them, calls their exports and
commands, fires events at them, and - the part that matters most - makes sure
a plugin that misbehaves is reported rather than allowed to take the app with
it. A plugin system whose failure mode is "the app dies" is worse than none.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app", "src", "main", "python"))

import pycmd_plugins as plugins  # noqa: E402

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILURES.append(name)


class FakeHost:
    def __init__(self):
        self.logs = []
        self.toasts = []
        self.messages = []
        self.actions = []

    def onPluginLog(self, level, message, detail):  # noqa: N802
        self.logs.append((level, message, detail))

    def onToast(self, message):  # noqa: N802
        self.toasts.append(message)

    def onPluginMessage(self, plugin_id, body):  # noqa: N802
        self.messages.append((plugin_id, body))

    def onPluginAction(self, plugin_id, action, detail):  # noqa: N802
        self.actions.append((plugin_id, action, detail))

    def text(self):
        return "\n".join(f"{l}:{m}:{d}" for l, m, d in self.logs)


scratch = tempfile.mkdtemp(prefix="pycmd-plugins-")
plugin_home = os.path.join(scratch, "plugins")
workspace = os.path.join(scratch, "workspace")
os.makedirs(workspace, exist_ok=True)
host = FakeHost()
plugins.configure(plugin_home, workspace, host)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def result(raw):
    return json.loads(raw)


SAID = []


def capture(call):
    """Runs `call`, collecting whatever it wrote to the console."""
    buffer = io.StringIO()
    previous = sys.stdout
    sys.stdout = buffer
    try:
        return call()
    finally:
        sys.stdout = previous
        if buffer.getvalue():
            SAID.append(buffer.getvalue())


# ------------------------------------------------- shape 1: a single .py file

print("\n== a single-file plugin ==")
single = write(os.path.join(scratch, "src", "wordcount.py"), '''
PLUGIN = {
    "id": "demo.wordcount",
    "name": "Word Count",
    "version": "1.2.0",
    "description": "Counts things.",
    "commands": [{"name": "wc", "help": "wc <text>"}],
}

TOTALS = {"calls": 0}


def setup(api):
    api.log("word count is up")

    @api.command("wc", help="wc <text>")
    def count(argument):
        TOTALS["calls"] += 1
        api.print(f"{len(argument.split())} words")
        return len(argument.split())

    @api.export
    def analyse(payload):
        text = (payload or {}).get("text", "")
        return {"words": len(text.split()), "characters": len(text)}

    @api.on("file_saved")
    def saved(event):
        api.log("saw a save", event.get("path", ""))
''')

installed = result(plugins.install(single))
check("a .py file installs", installed.get("ok"), installed)
check("its PLUGIN block is the manifest",
      installed.get("manifest", {}).get("name") == "Word Count", installed)
check("the version comes across",
      installed.get("manifest", {}).get("version") == "1.2.0", installed)

listed = result(plugins.listing())
check("it shows up in the listing", len(listed["plugins"]) == 1, listed)
check("and is not loaded yet", not listed["plugins"][0]["loaded"], listed)

loaded = result(plugins.load("demo.wordcount"))
check("it loads", loaded.get("ok"), loaded)
check("setup ran", "word count is up" in host.text(), host.text())
check("its export is registered", "analyse" in loaded.get("exports", []), loaded)
check("its command is registered", "wc" in loaded.get("commands", []), loaded)

called = result(plugins.call_export("demo.wordcount", "analyse", json.dumps({"text": "a b c"})))
check("an export can be called", called.get("ok"), called)
check("and returns its value", called.get("result", {}).get("words") == 3, called)

missing = result(plugins.call_export("demo.wordcount", "nope"))
check("an unknown export is an error, not a crash", not missing.get("ok"), missing)
check("and says what does exist", "analyse" in missing.get("error", ""), missing)

# The command writes to stdout, so capture it the way the console would.
captured = io.StringIO()
saved_stdout = sys.stdout
sys.stdout = captured
try:
    ran = result(plugins.run_command("wc", "one two three four"))
finally:
    sys.stdout = saved_stdout
check("a command runs", ran.get("handled") and ran.get("ok"), ran)
check("and its print reaches the console", "4 words" in captured.getvalue(),
      repr(captured.getvalue()))

unknown = result(plugins.run_command("definitely-not-a-command", ""))
check("an unknown command is left alone", not unknown.get("handled"), unknown)

fired = result(plugins.fire("file_saved", json.dumps({"path": "x.py"})))
check("an event reaches the plugin", fired.get("delivered") == 1, fired)
check("and the plugin saw the payload", "x.py" in host.text(), host.text())

fired = result(plugins.fire("nothing_listens_to_this", "{}"))
check("an event nobody wants is harmless", fired.get("delivered") == 0, fired)

# ------------------------------------------------------- shape 2: a folder

print("\n== a folder plugin with a panel ==")
folder = os.path.join(scratch, "src", "notes")
write(os.path.join(folder, "plugin.json"), json.dumps({
    "id": "demo.notes",
    "name": "Notes",
    "version": "0.1.0",
    "entry": "main.py",
    "panel": "ui.html",
    "tab": {"title": "Notes", "icon": "note"},
    "permissions": ["files"],
}))
write(os.path.join(folder, "main.py"), '''
def setup(api):
    @api.export
    def save(payload):
        api.store({"text": payload.get("text", "")})
        return {"saved": True}

    @api.export(name="load_text")
    def load(payload=None):
        return api.store().get("text", "")
''')
write(os.path.join(folder, "ui.html"), "<h1>Notes</h1><div id=x></div>")

installed = result(plugins.install(folder))
check("a folder installs", installed.get("ok"), installed)
check("the panel is recorded",
      installed.get("manifest", {}).get("panel") == "ui.html", installed)
check("the tab is normalised",
      installed.get("manifest", {}).get("tab", {}).get("title") == "Notes", installed)


print("\n== settings the app renders for a plugin ==")
settings_folder = os.path.join(scratch, "src", "settings")
write(os.path.join(settings_folder, "plugin.json"), json.dumps({
    "id": "demo.settings", "name": "Settings", "entry": "main.py",
    "settings": [
        {"name": "who", "type": "text", "label": "Name", "default": "world"},
        {"name": "loud", "type": "switch", "default": False},
        {"name": "times", "type": "number", "default": 3},
        {"name": "mode", "type": "choice", "options": ["fast", "slow"], "default": "slow"},
    ],
}))
write(os.path.join(settings_folder, "main.py"), """
def setup(api):
    @api.command("say", help="say")
    def say(argument):
        text = api.setting("who") * int(api.setting("times"))
        return text.upper() if api.setting("loud") else text
""")
installed = result(plugins.install(settings_folder))
check("a plugin with settings installs", installed.get("ok"), installed)
result(plugins.load("demo.settings"))

fields = result(plugins.plugin_settings("demo.settings"))["settings"]
check("all four are described", len(fields) == 4, fields)
check("each starts at its default",
      [f["value"] for f in fields] == ["world", False, 3, "slow"], fields)

SAID.clear()
capture(lambda: plugins.run_command("say", ""))
check("and the plugin reads them", "worldworldworld" in "".join(SAID), SAID)

result(plugins.set_plugin_setting("demo.settings", "who", "ada"))
result(plugins.set_plugin_setting("demo.settings", "loud", "true"))
result(plugins.set_plugin_setting("demo.settings", "times", "2"))
SAID.clear()
capture(lambda: plugins.run_command("say", ""))
check("changing one changes what the plugin does", "ADAADA" in "".join(SAID), SAID)

typed = result(plugins.plugin_settings("demo.settings"))["settings"]
values = {f["name"]: f["value"] for f in typed}
check("a switch is stored as a boolean", values["loud"] is True, values)
check("a number as a number", values["times"] == 2, values)

result(plugins.set_plugin_setting("demo.settings", "mode", "sideways"))
check("a choice outside the options falls back to the default",
      {f["name"]: f["value"] for f in
       result(plugins.plugin_settings("demo.settings"))["settings"]}["mode"] == "slow")

missing = result(plugins.set_plugin_setting("demo.settings", "nope", "x"))
check("a setting that was never declared is refused", not missing.get("ok"), missing)

bad = os.path.join(scratch, "src", "badsetting")
write(os.path.join(bad, "plugin.json"), json.dumps({
    "id": "demo.badsetting", "name": "Bad", "entry": "main.py",
    "settings": [{"name": "x", "type": "colour"}],
}))
write(os.path.join(bad, "main.py"), "def setup(api):\n    pass\n")
refused = result(plugins.install(bad))
check("an unknown setting type is refused at install", not refused.get("ok"), refused)
check("and says which types exist", "switch" in refused.get("error", ""), refused)

print("\n== guides a plugin publishes ==")
guided = os.path.join(scratch, "src", "guided")
write(os.path.join(guided, "plugin.json"), json.dumps({
    "id": "demo.guided", "name": "Guided", "entry": "main.py",
    "guides": [
        {"file": "HOWTO.md", "title": "How to use it", "summary": "The short version"},
        "extra_notes.md",
    ],
}))
write(os.path.join(guided, "main.py"), "def setup(api):\n    pass\n")
write(os.path.join(guided, "HOWTO.md"), "# How\n\nType `guided` in the console.\n")
write(os.path.join(guided, "extra_notes.md"), "# Notes\n")

installed = result(plugins.install(guided))
check("a plugin with guides installs", installed.get("ok"), installed)
guides = installed["manifest"]["guides"]
check("both are kept", len(guides) == 2, guides)
check("a titled one keeps its title", guides[0]["title"] == "How to use it", guides[0])
check("a bare file name gets a readable title",
      guides[1]["title"] == "Extra Notes", guides[1])

fetched = result(plugins.guide_text("demo.guided", "HOWTO.md"))
check("the text comes back", "Type `guided`" in fetched.get("text", ""), fetched)

outside = result(plugins.guide_text("demo.guided", "../../../etc/passwd"))
check("a file outside the plugin is refused", not outside.get("ok"), outside)
undeclared = result(plugins.guide_text("demo.guided", "main.py"))
check("and so is a file it never declared", not undeclared.get("ok"), undeclared)

missing = os.path.join(scratch, "src", "guidemissing")
write(os.path.join(missing, "plugin.json"), json.dumps({
    "id": "demo.guidemissing", "name": "Missing", "entry": "main.py",
    "guides": ["absent.md"],
}))
write(os.path.join(missing, "main.py"), "def setup(api):\n    pass\n")
refused = result(plugins.install(missing))
check("a guide that is not there is refused at install", not refused.get("ok"), refused)

wrong = os.path.join(scratch, "src", "guidewrong")
write(os.path.join(wrong, "plugin.json"), json.dumps({
    "id": "demo.guidewrong", "name": "Wrong", "entry": "main.py",
    "guides": ["main.py"],
}))
write(os.path.join(wrong, "main.py"), "def setup(api):\n    pass\n")
refused = result(plugins.install(wrong))
check("and so is one that is not a document", not refused.get("ok"), refused)

print("\n== lines a plugin adds to a file's menu ==")
actions_folder = os.path.join(scratch, "src", "actions")
write(os.path.join(actions_folder, "plugin.json"), json.dumps({
    "id": "demo.actions", "name": "Actions", "entry": "main.py",
    "actions": [
        {"target": "file", "label": "Count the lines", "export": "count", "types": ".py, txt"},
        {"target": "folder", "label": "Tidy", "export": "tidy"},
    ],
}))
write(os.path.join(actions_folder, "main.py"), """
def setup(api):
    @api.export
    def count(payload):
        return {"ok": True, "lines": len(api.read(payload["path"], "").splitlines())}

    @api.export
    def tidy(payload):
        return {"ok": True, "folder": payload["path"]}
""")
installed = result(plugins.install(actions_folder))
check("a plugin with actions installs", installed.get("ok"), installed)
actions = installed["manifest"]["actions"]
check("both are kept", len(actions) == 2, actions)
check("the types are normalised to extensions",
      actions[0]["types"] == [".py", ".txt"], actions[0])
reread = [p for p in result(plugins.listing())["plugins"] if p["id"] == "demo.actions"][0]
check("and reading the plugin back does not mangle them",
      reread["actions"][0]["types"] == [".py", ".txt"], reread["actions"][0])
check("a folder action keeps no types", actions[1]["types"] == [], actions[1])

result(plugins.load("demo.actions"))
target = write(os.path.join(workspace, "counted.py"), "a\nb\nc\n")
reply = result(plugins.call_export("demo.actions", "count", json.dumps({"path": target})))
check("running one reaches the export", reply["result"]["lines"] == 3, reply)

for missing_field in ({"target": "file", "label": "x"}, {"target": "file", "export": "y"}):
    broken = os.path.join(scratch, "src", "badaction" + str(len(missing_field)))
    write(os.path.join(broken, "plugin.json"), json.dumps({
        "id": "demo.badaction", "name": "Bad", "entry": "main.py",
        "actions": [missing_field],
    }))
    write(os.path.join(broken, "main.py"), "def setup(api):\n    pass\n")
    check("an action missing half of itself is refused",
          not result(plugins.install(broken)).get("ok"))

print("\n== what a plugin can ask the app to do ==")
asking = os.path.join(scratch, "src", "asking")
write(os.path.join(asking, "plugin.json"), json.dumps({
    "id": "demo.asking", "name": "Asking", "entry": "main.py",
}))
write(os.path.join(asking, "main.py"), """
def setup(api):
    @api.command("drive", help="drive")
    def drive(argument):
        api.open_file("a.py")
        api.run_file("a.py")
        api.preview("a.html")
        api.go_to("servers")
        api.serve("site", 8123)
        api.refresh("files")
        return "asked"
""")
result(plugins.install(asking))
result(plugins.load("demo.asking"))
host.actions.clear()
capture(lambda: plugins.run_command("drive", ""))
kinds = [action for _plugin, action, _detail in host.actions]
check("every verb reaches the app",
      kinds == ["open_file", "run_file", "preview", "go_to", "serve", "refresh"], kinds)
paths = json.loads(host.actions[0][2])
check("paths are resolved against the workspace",
      paths["path"].startswith(workspace), paths)
served = json.loads(host.actions[4][2])
check("and the port comes along", served["port"] == 8123, served)

print("\n== two plugins wanting the same command ==")
for index, folder_name in enumerate(("clash-a", "clash-b")):
    clash = os.path.join(scratch, "src", folder_name)
    write(os.path.join(clash, "plugin.json"), json.dumps({
        "id": f"demo.{folder_name}", "name": folder_name, "entry": "main.py",
    }))
    write(os.path.join(clash, "main.py"), f"""
def setup(api):
    @api.command("both", help="both")
    def both(argument):
        return "from {folder_name}"
""")
    result(plugins.install(clash))
    result(plugins.load(f"demo.{folder_name}"))

host.logs.clear()
listed = result(plugins.commands())["commands"]
both = [row for row in listed if row["name"] == "both"]
check("both are listed", len(both) == 2, both)
check("one is marked as shadowed",
      sum(1 for row in both if row["shadowed"]) == 1, both)
check("and the clash is reported",
      any("both" in message for _level, message, _detail in host.logs), host.logs)

print("\n== a command that returns its answer ==")
returner = os.path.join(scratch, "src", "returner")
write(os.path.join(returner, "plugin.json"), json.dumps({
    "id": "demo.returner", "name": "Returner", "entry": "main.py",
}))
write(os.path.join(returner, "main.py"), """
def setup(api):
    @api.command("echo2", help="echo2 <text>")
    def echo2(argument):
        return "you said " + argument.strip()

    @api.command("quiet", help="says nothing")
    def quiet(argument):
        return None
""")
result(plugins.install(returner))
result(plugins.load("demo.returner"))
SAID.clear()
reply = capture(lambda: result(plugins.run_command("echo2", "hello there")))
check("the command is handled", reply.get("handled"), reply)
check("and what it returned is printed",
      any("you said hello there" in text for text in SAID), SAID)
SAID.clear()
capture(lambda: result(plugins.run_command("quiet", "")))
check("returning nothing prints nothing", SAID == [], SAID)

print("\n== a tab in the More screen ==")
# The icon is a real file inside the plugin, because a plugin author cannot
# add a drawable to the app.
icon_folder = os.path.join(scratch, "src", "withicon")
write(os.path.join(icon_folder, "plugin.json"), json.dumps({
    "id": "demo.icon",
    "name": "With Icon",
    "entry": "main.py",
    "panel": "ui.html",
    "tab": {"title": "Board", "description": "A live board", "icon": "logo.png"},
}))
write(os.path.join(icon_folder, "main.py"), "def setup(api):\n    pass\n")
write(os.path.join(icon_folder, "ui.html"), "<h1>Board</h1>")
with open(os.path.join(icon_folder, "logo.png"), "wb") as handle:
    handle.write(b"\x89PNG\r\n\x1a\n" + b"0" * 32)

installed = result(plugins.install(icon_folder))
check("a plugin with an image icon installs", installed.get("ok"), installed)

listed = result(plugins.listing())["plugins"]
row = next((p for p in listed if p["id"] == "demo.icon"), None)
check("its tab survives the install", row and row["tab"]["title"] == "Board", row)
check("with its own description", row["tab"]["description"] == "A live board", row)
check("and the icon resolves to where it now lives",
      os.path.isfile(row["tab"]["image"]), row["tab"])
check("which is inside the installed plugin, not the staging folder",
      "staging" not in row["tab"]["image"], row["tab"]["image"])

saved = json.load(open(os.path.join(plugins.plugin_dir("demo.icon"), "plugin.json")))
check("the absolute path is not written down",
      "image" not in saved["tab"], saved["tab"])

print("\n== a section inside one of the app's own tabs ==")
ext = os.path.join(scratch, "src", "extender")
write(os.path.join(ext, "plugin.json"), json.dumps({
    "id": "demo.extender",
    "name": "Extender",
    "entry": "main.py",
    "panel": "ui.html",
    "extends": [
        {"tab": "servers", "title": "Board", "description": "live", "panel": "board.html",
         "height": "tall", "open": True},
        {"tab": "files"},
    ],
}))
write(os.path.join(ext, "main.py"), "def setup(api):\n    pass\n")
write(os.path.join(ext, "ui.html"), "<h1>x</h1>")
write(os.path.join(ext, "board.html"), "<h1>board</h1>")

installed = result(plugins.install(ext))
check("a plugin that extends a tab installs", installed.get("ok"), installed)
sections = installed.get("manifest", {}).get("extends", [])
check("both sections are kept", len(sections) == 2, sections)
check("the first names its own panel and height",
      sections[0]["panel"] == "board.html" and sections[0]["height"] == "tall", sections[0])
check("and can ask to start open", sections[0]["open"] is True, sections[0])
check("the second falls back to the plugin's panel",
      sections[1]["panel"] == "ui.html" and sections[1]["title"] == "Extender", sections[1])
check("and is closed by default", sections[1]["open"] is False, sections[1])

page = plugins.panel_html("demo.extender", "board.html")
check("its section panel renders", "<h1>board</h1>" in page, page[:200])
check("with the bridge injected", "__pycmd_panel" in page or "pycmd" in page)
main_page = plugins.panel_html("demo.extender")
check("and the main panel still renders", "<h1>x</h1>" in main_page, main_page[:200])
escaped = plugins.panel_html("demo.extender", "../../../etc/passwd")
check("a panel outside the plugin is refused", "<h1>" not in escaped or "passwd" not in escaped)

bad_tab = os.path.join(scratch, "src", "badtab")
write(os.path.join(bad_tab, "plugin.json"), json.dumps({
    "id": "demo.badtab", "name": "Bad Tab", "entry": "main.py", "panel": "ui.html",
    "extends": [{"tab": "wherever"}],
}))
write(os.path.join(bad_tab, "main.py"), "def setup(api):\n    pass\n")
write(os.path.join(bad_tab, "ui.html"), "<h1>x</h1>")
refused = result(plugins.install(bad_tab))
check("a screen that does not exist is refused", not refused.get("ok"), refused)
check("and the message lists the real ones", "servers" in refused.get("error", ""), refused)

print("\n== a tab needs something to open ==")
bad = os.path.join(scratch, "src", "tabnopanel")
write(os.path.join(bad, "plugin.json"), json.dumps({
    "id": "demo.tabnopanel", "name": "No Panel", "entry": "main.py",
    "tab": {"title": "Nowhere"},
}))
write(os.path.join(bad, "main.py"), "def setup(api):\n    pass\n")
refused = result(plugins.install(bad))
check("a tab without a panel is refused", not refused.get("ok"), refused)
check("and says why", "panel" in refused.get("error", ""), refused)

missing = os.path.join(scratch, "src", "tabnoicon")
write(os.path.join(missing, "plugin.json"), json.dumps({
    "id": "demo.tabnoicon", "name": "Missing Icon", "entry": "main.py",
    "panel": "ui.html", "tab": {"title": "Gone", "icon": "absent.png"},
}))
write(os.path.join(missing, "main.py"), "def setup(api):\n    pass\n")
write(os.path.join(missing, "ui.html"), "<h1>x</h1>")
refused = result(plugins.install(missing))
check("an icon that is not there is refused", not refused.get("ok"), refused)

loaded = result(plugins.load("demo.notes"))
check("the folder plugin loads", loaded.get("ok"), loaded)
check("a renamed export keeps its new name",
      "load_text" in loaded.get("exports", []), loaded)

result(plugins.call_export("demo.notes", "save", json.dumps({"text": "hello"})))
back = result(plugins.call_export("demo.notes", "load_text"))
check("its store round-trips", back.get("result") == "hello", back)

page = plugins.panel_html("demo.notes")
check("the panel gets the bridge", "window.pycmd" in page, page[:200])
check("the panel keeps its own markup", "<h1>Notes</h1>" in page, page[:200])
# The house style is written in CSS variables now, so that the app can hand a
# panel whichever theme is on. The fallbacks are still the Classic Green
# values: a panel has to look right in the first frame, before the app's
# `:root` block has arrived.
check("the panel gets the house style", "background: var(--bg)" in page, page[:200])
check("the house style declares its fallbacks", "--bg: #0B0F14;" in page, page[:400])
check("the house style draws the sliders", 'input[type="range"]' in page, page[:400])
check(
    "the house style honours the animations switch",
    'data-pycmd-motion="reduced"' in page,
    page[:400],
)

# ---------------------------------------------------------- shape 3: a zip

print("\n== a zipped plugin ==")
zip_path = os.path.join(scratch, "src", "clock.zip")
with zipfile.ZipFile(zip_path, "w") as archive:
    archive.writestr("clock/plugin.json", json.dumps({
        "id": "demo.clock", "name": "Clock", "entry": "main.py",
    }))
    archive.writestr("clock/main.py", "def setup(api):\n    api.log('tick')\n")

installed = result(plugins.install(zip_path))
check("a zip installs", installed.get("ok"), installed)
check("the wrapping folder is stripped",
      os.path.isfile(os.path.join(plugin_home, "demo.clock", "main.py")),
      os.listdir(os.path.join(plugin_home, "demo.clock")))

# ------------------------------------------------------------ misbehaviour

print("\n== plugins that misbehave ==")
broken = write(os.path.join(scratch, "src", "broken.py"), '''
PLUGIN = {"id": "demo.broken", "name": "Broken"}

raise RuntimeError("I explode on import")
''')
result(plugins.install(broken))
loaded = result(plugins.load("demo.broken"))
check("an exploding plugin does not take the app down", not loaded.get("ok"), loaded)
check("the failure names the plugin", "Broken" in loaded.get("error", ""), loaded)
check("and the traceback is kept", "I explode on import" in loaded.get("error", ""), loaded)

throwing = write(os.path.join(scratch, "src", "throwing.py"), '''
PLUGIN = {"id": "demo.throwing", "name": "Throwing"}


def setup(api):
    @api.export
    def boom(payload=None):
        raise ValueError("no")

    @api.on("run_finished")
    def handler(event):
        raise KeyError("also no")
''')
result(plugins.install(throwing))
result(plugins.load("demo.throwing"))
called = result(plugins.call_export("demo.throwing", "boom"))
check("an export that raises is reported", not called.get("ok"), called)
check("with the real message", "no" in called.get("error", ""), called)

fired = result(plugins.fire("run_finished", "{}"))
check("a listener that raises does not stop the event", fired.get("ok"), fired)

no_manifest = os.path.join(scratch, "src", "empty")
os.makedirs(no_manifest, exist_ok=True)
write(os.path.join(no_manifest, "readme.txt"), "nothing here")
installed = result(plugins.install(no_manifest))
check("a folder with no python is refused", not installed.get("ok"), installed)
check("and says what a plugin needs", "PLUGINS.md" in installed.get("error", ""), installed)

bad_json = os.path.join(scratch, "src", "badjson")
write(os.path.join(bad_json, "plugin.json"), "{not json")
write(os.path.join(bad_json, "main.py"), "def setup(api):\n    pass\n")
installed = result(plugins.install(bad_json))
check("a broken manifest is refused", not installed.get("ok"), installed)
check("and points at the JSON", "JSON" in installed.get("error", ""), installed)

missing_entry = os.path.join(scratch, "src", "noentry")
write(os.path.join(missing_entry, "plugin.json"), json.dumps({
    "id": "demo.noentry", "name": "No Entry", "entry": "somewhere.py",
}))
write(os.path.join(missing_entry, "main.py"), "def setup(api):\n    pass\n")
installed = result(plugins.install(missing_entry))
check("a missing entry file is refused", not installed.get("ok"), installed)

escaping = os.path.join(scratch, "src", "escape.zip")
with zipfile.ZipFile(escaping, "w") as archive:
    archive.writestr("plugin.json", json.dumps({"id": "demo.escape", "name": "Escape",
                                                "entry": "main.py"}))
    archive.writestr("main.py", "def setup(api):\n    pass\n")
    archive.writestr("../../../outside.txt", "should never be written")
installed = result(plugins.install(escaping))
check("a zip that writes outside itself is refused", not installed.get("ok"), installed)
check("nothing escaped", not os.path.exists(os.path.join(scratch, "outside.txt")),
      os.listdir(scratch))

# --------------------------------------------------------- the plugin's API

print("\n== the API a plugin is given ==")
api_test = write(os.path.join(scratch, "src", "apitest.py"), '''
PLUGIN = {"id": "demo.api", "name": "Api Test"}

SEEN = {}


def setup(api):
    SEEN["workspace"] = api.workspace_path()
    api.write("from_plugin.txt", "written by a plugin")
    SEEN["read_back"] = api.read("from_plugin.txt")
    SEEN["missing"] = api.read("nope.txt", "fallback")
    SEEN["files"] = len(api.files("*.txt"))
    api.toast("hello from a plugin")

    @api.export
    def seen(payload=None):
        return SEEN
''')
result(plugins.install(api_test))
result(plugins.load("demo.api"))
seen = result(plugins.call_export("demo.api", "seen")).get("result", {})
check("workspace_path points at the workspace", seen.get("workspace") == workspace, seen)
check("write then read round-trips", seen.get("read_back") == "written by a plugin", seen)
check("a missing read returns the fallback", seen.get("missing") == "fallback", seen)
check("files() finds what was written", seen.get("files") == 1, seen)
check("toast reaches the host", "hello from a plugin" in host.toasts, host.toasts)
check("the file really is in the workspace",
      os.path.isfile(os.path.join(workspace, "from_plugin.txt")), os.listdir(workspace))

# ------------------------------------------------------- loading in batches

print("\n== enabling and disabling ==")
check("an empty string asks for nothing", result(plugins.load_all(""))["ok"],
      plugins.load_all(""))
check("None asks for nothing", result(plugins.load_all(None))["ok"], plugins.load_all(None))
check("a comma-separated string works like a list",
      {r["id"] for r in result(plugins.load_all("demo.wordcount,demo.notes"))["results"]}
      == {"demo.wordcount", "demo.notes"},
      plugins.load_all("demo.wordcount,demo.notes"))

outcome = result(plugins.load_all(["demo.wordcount", "demo.notes"]))
ok_ids = {r["id"] for r in outcome["results"] if r.get("ok")}
check("load_all loads what was asked for", ok_ids == {"demo.wordcount", "demo.notes"}, outcome)

listed = result(plugins.listing())
states = {p["id"]: p.get("loaded") for p in listed["plugins"]}
check("the others were unloaded", states.get("demo.api") is False, states)
check("and the wanted ones are loaded", states.get("demo.notes") is True, states)

ran = result(plugins.run_command("wc", "still here"))
check("a reloaded plugin still answers", ran.get("handled"), ran)

removed = result(plugins.remove("demo.clock"))
check("a plugin can be removed", removed.get("ok"), removed)
listed = result(plugins.listing())
check("and is gone from the listing",
      "demo.clock" not in {p["id"] for p in listed["plugins"]}, listed)

# ---------------------------------------------------------------- reporting

print("\n== the listing ==")
listed = result(plugins.listing())
by_id = {p["id"]: p for p in listed["plugins"]}
check("a broken plugin is still listed", "demo.broken" in by_id, list(by_id))
check("with its load error attached", by_id["demo.broken"].get("error"), by_id["demo.broken"])
check("sizes are reported", by_id["demo.notes"]["size"] > 0, by_id["demo.notes"])
check("file lists are reported", "ui.html" in by_id["demo.notes"]["files"],
      by_id["demo.notes"])

# ------------------------------------------------------- replacing in place

print("\n== replacing a plugin leaves one whole plugin behind ==")
# The bug this guards: install used to delete the folder and then move the
# new one into the gap. `shutil.move` into a folder that still exists puts the
# source *inside* it - so a delete that only half worked left main.py one
# level down, and a plugin that listed fine and could not be loaded:
#
#   FileNotFoundError: .../plugins/pycmd.cloud/main.py
#
# The swap is a rename onto a folder that has already been moved aside, which
# cannot nest and cannot leave a half-emptied folder behind.

swap = os.path.join(scratch, "swap-v1")
os.makedirs(swap, exist_ok=True)
with open(os.path.join(swap, "plugin.json"), "w", encoding="utf-8") as handle:
    json.dump({"id": "demo.swap", "name": "Swap", "version": "1.0.0",
               "entry": "main.py"}, handle)
with open(os.path.join(swap, "main.py"), "w", encoding="utf-8") as handle:
    handle.write("VALUE = 1\n")

check("the first version installs", result(plugins.install(swap)).get("ok"))

swap2 = os.path.join(scratch, "swap-v2")
os.makedirs(swap2, exist_ok=True)
with open(os.path.join(swap2, "plugin.json"), "w", encoding="utf-8") as handle:
    json.dump({"id": "demo.swap", "name": "Swap", "version": "2.0.0",
               "entry": "main.py"}, handle)
with open(os.path.join(swap2, "main.py"), "w", encoding="utf-8") as handle:
    handle.write("VALUE = 2\n")

again = result(plugins.install(swap2))
check("the second installs over it", again.get("ok"), again)
check("and says it replaced something", again.get("replaced"), again)

home = plugins.plugin_dir("demo.swap")
check("the entry file is where the manifest says it is",
      os.path.isfile(os.path.join(home, "main.py")), sorted(os.listdir(home)))
with open(os.path.join(home, "main.py"), encoding="utf-8") as handle:
    check("and it is the new one", "VALUE = 2" in handle.read())
check("nothing was nested inside the plugin folder",
      not [n for n in os.listdir(home) if os.path.isdir(os.path.join(home, n))
           and n.startswith(".")],
      sorted(os.listdir(home)))
check("and it loads", result(plugins.load("demo.swap")).get("ok"))

listed = result(plugins.listing())
row = next((p for p in listed["plugins"] if p["id"] == "demo.swap"), None)
check("the listing shows the new version", row and row["version"] == "2.0.0", row)

check("no staging or retired folders are left lying about",
      not [n for n in os.listdir(plugin_home)
           if n.startswith(".staging-") or n.startswith(".retired-")],
      sorted(os.listdir(plugin_home)))

# A leftover from a killed install is cleared by the next one rather than
# sitting in private storage for ever.
litter = os.path.join(plugin_home, ".retired-demo.swap-1")
os.makedirs(litter, exist_ok=True)
with open(os.path.join(litter, "junk.txt"), "w", encoding="utf-8") as handle:
    handle.write("x")
result(plugins.install(swap2))
check("and a leftover from a killed install is tidied away",
      not os.path.isdir(litter), sorted(os.listdir(plugin_home)))

plugins.unload("demo.swap")
result(plugins.remove("demo.swap"))

shutil.rmtree(scratch, ignore_errors=True)

total = 0
print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
    raise SystemExit(1)
print("all plugin checks passed")
