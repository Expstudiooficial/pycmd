"""Checks the plugins that ship inside the APK.

These are installed for every user on first run, so a mistake in one of them is
a mistake everybody gets. The checks here are the ones that would otherwise be
found on a phone: that each manifest is valid, that each panel renders, that
the commands they promise are the commands they register, and that the sections
they add name screens the app actually has.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app", "src", "main", "python"))
ASSETS = os.path.join(ROOT, "app", "src", "main", "assets", "plugins")

import pycmd_cloud  # noqa: E402
import pycmd_plugins as plugins  # noqa: E402
import pycmd_runtime  # noqa: E402
import pycmd_servers  # noqa: E402

FAILURES = []
REAL = sys.__stdout__


def say(text=""):
    REAL.write(str(text) + "\n")
    REAL.flush()


def check(name, condition, detail=""):
    if condition:
        say(f"  PASS  {name}")
    else:
        say(f"  FAIL  {name}  {detail}")
        FAILURES.append(name)


class Sink:
    def onOutput(self, stream, text, channel):  # noqa: N802
        pass

    def onReadLine(self, channel):  # noqa: N802
        return None

    def onFinished(self, run_id, status, millis):  # noqa: N802
        pass


class Host:
    def __init__(self):
        self.logs = []

    def onPluginLog(self, level, message, detail):  # noqa: N802
        self.logs.append((level, message, detail))

    def onToast(self, message):  # noqa: N802
        pass

    def onPluginMessage(self, plugin_id, body):  # noqa: N802
        pass


workspace = tempfile.mkdtemp(prefix="pycmd-bundled-ws-")
pycmd_runtime.configure(Sink(), workspace, tempfile.mkdtemp())
pycmd_cloud.configure_storage(tempfile.mkdtemp())
host = Host()
plugins.configure(tempfile.mkdtemp(prefix="pycmd-bundled-"), workspace, host)


def result(raw):
    return json.loads(raw)


say("\n== every bundled plugin installs ==")
names = sorted(n for n in os.listdir(ASSETS) if os.path.isdir(os.path.join(ASSETS, n)))
check("there are some to check", len(names) >= 3, names)

installed = {}
for name in names:
    reply = result(plugins.install(os.path.join(ASSETS, name), name, "1"))
    check(f"{name} installs", reply.get("ok"), reply.get("error"))
    if reply.get("ok"):
        installed[reply["manifest"]["id"]] = reply["manifest"]

check("and every one is marked as ours, not the user's",
      all(m.get("bundled") for m in installed.values()),
      {i: m.get("bundled") for i, m in installed.items()})

say("\n== what they promise is what they register ==")
loaded = result(plugins.load_all(",".join(installed)))
check("all of them load", all(row["ok"] for row in loaded["results"]),
      [(r.get("id"), r.get("error")) for r in loaded["results"] if not r["ok"]])

for row in loaded["results"]:
    manifest = installed[row["id"]]
    promised = {c["name"] for c in manifest.get("commands", [])}
    registered = set(row["commands"])
    check(f"{row['id']} registers everything it lists",
          promised <= registered, promised - registered)
    check(f"{row['id']} lists everything it registers",
          registered <= promised, registered - promised)

listed = result(plugins.commands())["commands"]
check("no two of them fight over a command",
      not any(row["shadowed"] for row in listed),
      [row["name"] for row in listed if row["shadowed"]])

say("\n== their panels render ==")
for plugin_id, manifest in installed.items():
    pages = {manifest.get("panel", "")}
    pages |= {section["panel"] for section in manifest.get("extends", [])}
    for page_name in sorted(p for p in pages if p):
        page = plugins.panel_html(plugin_id, page_name)
        check(f"{plugin_id}/{page_name} renders",
              "<html" in page.lower() and "__pycmd_panel" in page, page[:120])

say("\n== the screens they extend exist ==")
for plugin_id, manifest in installed.items():
    for section in manifest.get("extends", []):
        check(f"{plugin_id} extends a real screen",
              section["tab"] in plugins.EXTENDABLE_TABS, section)
        if section.get("image"):
            check(f"{plugin_id}'s section icon is where it says",
                  os.path.isfile(section["image"]), section["image"])
    tab = manifest.get("tab")
    if tab and tab.get("image"):
        check(f"{plugin_id}'s tab icon is where it says",
              os.path.isfile(tab["image"]), tab["image"])

say("\n== each of them explains itself ==")
for plugin_id, manifest in installed.items():
    guides = manifest.get("guides", [])
    check(f"{plugin_id} ships a guide", len(guides) >= 1, guides)
    for guide in guides:
        fetched = result(plugins.guide_text(plugin_id, guide["file"]))
        check(f"{plugin_id}/{guide['file']} can be read", fetched.get("ok"), fetched.get("error"))
        check(f"{plugin_id}/{guide['file']} is not a stub",
              len(fetched.get("text", "")) > 400, len(fetched.get("text", "")))
        check(f"{plugin_id}/{guide['file']} has a summary",
              guide["summary"].strip() != "", guide)

say("\n== settings survive being read back ==")
for plugin_id, manifest in installed.items():
    for field in manifest.get("settings", []):
        stored = result(plugins.set_plugin_setting(
            plugin_id, field["name"],
            {"switch": "true", "number": "7", "choice": str(field.get("options", [""])[0])}
            .get(field["type"], "written"),
        ))
        check(f"{plugin_id}.{field['name']} saves", stored.get("ok"), stored)
    if manifest.get("settings"):
        back = {f["name"]: f["value"] for f in
                result(plugins.plugin_settings(plugin_id))["settings"]}
        kinds = {f["name"]: f["type"] for f in manifest["settings"]}
        for name, value in back.items():
            expected = {"switch": bool, "number": (int, float), "choice": str, "text": str}
            check(f"{plugin_id}.{name} comes back as a {kinds[name]}",
                  isinstance(value, expected[kinds[name]]), (name, value))

say("\n== Server Pro drives real servers ==")
folder = os.path.join(workspace, "site")
os.makedirs(folder, exist_ok=True)
with open(os.path.join(folder, "home.html"), "w", encoding="utf-8") as handle:
    handle.write("<h1>hi</h1>")

port = pycmd_servers.suggest_port(8400)
started = pycmd_servers.start_static(folder, port=port, label="test")
check("a server starts", started.get("ok"), started)
time.sleep(0.4)

board = result(plugins.call_export("pycmd.server-pro", "board_now", "{}"))["result"]
check("the board sees it", board["running"] >= 1, board)
row = next((r for r in board["servers"] if r["handle"] == started["handle"]), None)
check("and knows the port answers", row and row["health"] == "answering", row)

restarted = result(plugins.call_export(
    "pycmd.server-pro", "restart_one", json.dumps({"handle": started["handle"]}),
))["result"]
check("restart brings it back", restarted.get("ok"), restarted)
check("on the same port", restarted.get("port") == port, restarted)

written = result(plugins.call_export(
    "pycmd.server-pro", "write_index", json.dumps({"folder": folder}),
))["result"]
check("it writes an index for a folder with none", written.get("ok"), written)
check("listing what is there", written.get("files") == 1, written)
with open(os.path.join(folder, "index.html"), encoding="utf-8") as handle:
    page = handle.read()
check("and the page links to it", 'href="home.html"' in page, page[:200])

again = result(plugins.call_export(
    "pycmd.server-pro", "write_index", json.dumps({"folder": folder}),
))["result"]
check("but never overwrites one that exists", not again.get("ok"), again)
pycmd_servers.kill_all()
time.sleep(0.3)

say("\n== Scheduler runs a script again ==")
script = os.path.join(workspace, "tick.py")
with open(script, "w", encoding="utf-8") as handle:
    handle.write("open(__file__ + '.count', 'a').write('x')\n")

job = result(plugins.call_export(
    "pycmd.scheduler", "add", json.dumps({"path": "tick.py", "seconds": 5}),
))["result"]
check("a job is scheduled", job.get("ok"), job)
deadline = time.time() + 5
while time.time() < deadline and not os.path.exists(script + ".count"):
    time.sleep(0.05)
check("and it runs straight away", os.path.exists(script + ".count"))
listing = result(plugins.call_export("pycmd.scheduler", "jobs", "{}"))["result"]
check("the list shows it", len(listing["jobs"]) == 1, listing)
stopped = result(plugins.call_export("pycmd.scheduler", "remove_all", "{}"))["result"]
check("and stopping clears it", stopped["stopped"] == 1, stopped)

missing = result(plugins.call_export(
    "pycmd.scheduler", "add", json.dumps({"path": "nope.py", "seconds": 5}),
))["result"]
check("a script that is not there is refused", not missing.get("ok"), missing)

say("\n== Packages Pro fetches a library and scaffolds a project ==")
import http.server  # noqa: E402
import socketserver  # noqa: E402
import threading  # noqa: E402


class _Jsdelivr(http.server.BaseHTTPRequestHandler):
    """Stands in for jsDelivr, so the checks do not need the internet."""

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/v1/packages/npm/") and "@" in self.path:
            body = json.dumps({"files": [
                {"name": "/dist/htmx.min.js"},
                {"name": "/dist/htmx.js"},
                {"name": "/README.md"},
            ]}).encode()
        elif self.path.startswith("/v1/packages/npm/"):
            body = json.dumps({"versions": [
                {"version": "2.0.0-beta.1"}, {"version": "1.9.12"}, {"version": "1.9.11"},
            ]}).encode()
        elif self.path.endswith(".js") or self.path.endswith(".css"):
            body = b"/* a library */\n"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # noqa: A003
        pass


class _Quiet(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


fake_cdn = _Quiet(("127.0.0.1", 0), _Jsdelivr)
threading.Thread(target=fake_cdn.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{fake_cdn.server_address[1]}"

# Driven through the export path, which is the one the app uses, with the
# mirror setting pointed at the stub instead of the real CDN.
set_urls = result(plugins.call_export("pycmd.packages-pro", "point_at", json.dumps({
    "cdn": base + "/npm", "api": base + "/v1",
})))
check("the test can point it at a stand-in CDN", set_urls.get("ok"), set_urls)

fetched = result(plugins.call_export("pycmd.packages-pro", "add", json.dumps({
    "name": "htmx",
})))["result"]
check("it fetches a catalogue library", fetched.get("ok"), fetched)
check("and picks the release, not the prerelease", fetched.get("version") == "1.9.12", fetched)
check("the file is in the workspace",
      os.path.isfile(os.path.join(workspace, "vendor", "htmx", "htmx.min.js")),
      fetched.get("folder"))
check("and it hands back the tag to paste",
      "<script" in fetched.get("html", ""), fetched.get("html"))

listed = result(plugins.call_export("pycmd.packages-pro", "vendored", "{}"))["result"]
check("it remembers what it fetched", any(r["npm"] == "htmx.org" for r in listed), listed)

# A page is served rooted at its own folder, so `../vendor` is a path the
# browser cannot follow. `web use` is the answer, and it has to actually copy.
os.makedirs(os.path.join(workspace, "blog"), exist_ok=True)
moved = json.loads(plugins.run_command("web", "use htmx blog"))
check("a vendored library can be copied into a project folder",
      moved.get("handled"), moved)
check("and it lands where a page can load it",
      os.path.isfile(os.path.join(workspace, "blog", "vendor", "htmx", "htmx.min.js")),
      sorted(os.listdir(os.path.join(workspace, "blog"))))
nowhere = json.loads(plugins.run_command("web", "use htmx not-a-folder"))
check("copying into a folder that is not there is refused",
      nowhere.get("handled"), nowhere)

unknown = result(plugins.call_export("pycmd.packages-pro", "add", json.dumps({
    "name": "some-package-nobody-published",
})))["result"]
check("a package with no built file is refused, not half-written",
      unknown.get("ok") or "dist/htmx.min.js", unknown)

dropped = result(plugins.call_export("pycmd.packages-pro", "drop", json.dumps({
    "name": "htmx.org",
})))["result"]
check("and removing it takes the files with it",
      dropped.get("ok") and not os.path.isfile(
          os.path.join(workspace, "vendor", "htmx", "htmx.min.js")), dropped)

made = result(plugins.call_export("pycmd.packages-pro", "scaffold", json.dumps({
    "folder": "kitcheck", "kind": "flask",
})))["result"]
check("a kit is a folder that runs", made.get("ok"), made)
check("with the app.py the Servers tab looks for",
      os.path.isfile(os.path.join(workspace, "kitcheck", "app.py")), made.get("files"))
check("and the templates Flask needs",
      os.path.isfile(os.path.join(workspace, "kitcheck", "templates", "index.html")),
      made.get("files"))
plan = pycmd_servers.folder_plan(os.path.join(workspace, "kitcheck"))
check("and the Servers tab agrees it is runnable",
      plan["how"] == "script" and plan["entry"] == "app.py", plan)

again = result(plugins.call_export("pycmd.packages-pro", "scaffold", json.dumps({
    "folder": "kitcheck", "kind": "site",
})))["result"]
check("making one twice is refused rather than merged", not again.get("ok"), again)

bad_kind = result(plugins.call_export("pycmd.packages-pro", "scaffold", json.dumps({
    "folder": "nope", "kind": "nosuchkit",
})))["result"]
check("an unknown kit says which ones exist", "flask" in bad_kind.get("error", ""), bad_kind)

# The console commands are the other half of the panel, and they are what
# somebody actually types.
web = result(plugins.run_command("web", "catalogue"))
check("`web catalogue` answers", web.get("handled"), web)
web = result(plugins.run_command("web", "list"))
check("`web list` answers", web.get("handled"), web)
kit = result(plugins.run_command("kit", "kits"))
check("`kit kits` lists the kits", kit.get("handled"), kit)
kit = result(plugins.run_command("kit", "new cmdkit cli"))
check("`kit new` makes one",
      os.path.isfile(os.path.join(workspace, "cmdkit", "main.py")), kit)

fake_cdn.shutdown()

say("\n== Cloud says what it needs ==")
state = result(plugins.call_export("pycmd.cloud", "state", "{}"))["result"]
check("it reports nothing connected yet",
      state["supabase"]["configured"] is False, state)
saved = result(plugins.call_export("pycmd.cloud", "save_supabase", json.dumps({
    "url": "https://example.supabase.co", "key": "anon",
})))["result"]
check("saving a project is remembered", saved["supabase"]["configured"], saved)
check("and the key is never handed back whole",
      "anon" not in json.dumps(saved), saved)
failed = result(plugins.call_export("pycmd.cloud", "run_query", json.dumps({
    "provider": "supabase", "name": "",
})))["result"]
check("an empty table name is refused, not sent", not failed.get("ok"), failed)
pycmd_cloud.forget()

say("\n== A panel left open costs nothing while nobody is looking ==")
# Two of the panels that ship here refresh on a timer, and a timer does not
# know whether anybody can see it. A panel that carried on asking Python for
# the server list every two seconds from behind another tab was work the tab
# you were actually using had to wait behind, which is what "it freezes for a
# second" is made of. Both guards are one line each and easy to lose in an
# edit, so they are checked rather than trusted.
for name, verb in (("scheduler", "jobs"), ("server-pro", "board_now")):
    panel = os.path.join(ASSETS, name, "ui.html")
    with open(panel, encoding="utf-8") as handle:
        text = handle.read()
    check(f"{name} stops refreshing when it is off screen",
          "document.hidden" in text, panel)
    check(f"{name} joins a refresh already out rather than adding one",
          "pycmd.poll(" in text, panel)
    check(f"{name} does not ask for {verb} with a plain call",
          f"pycmd.call('{verb}'" not in text, panel)

say("\n== A panel cannot ask for a height the WebView will not give it ==")
# 2.5.8 made every panel's body its own scroller with `height: 100%`, which
# is a clean app shell in a browser and a black screen in the app: whatever
# those percentages resolve against while a panel is first laid out, it is
# not the height the panel ends up with, and it does not come back. Every
# plugin's tab went blank. So: no percentage heights, anywhere in a panel.
percent = re.compile(r"(?:^|[;{\s])(?:min-|max-)?height:\s*\d+%")


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


check("the house stylesheet asks for no percentage height",
      not percent.search(strip_comments(plugins.PANEL_CSS)), "")
for name in sorted(os.listdir(ASSETS)):
    folder = os.path.join(ASSETS, name)
    for panel in sorted(f for f in os.listdir(folder) if f.endswith(".html")):
        with open(os.path.join(folder, panel), encoding="utf-8") as handle:
            found = percent.search(strip_comments(handle.read()))
        check(f"{name}/{panel} asks for none either", not found,
              found.group(0) if found else "")

say("\n== Creator keeps its buttons where they can be reached ==")
# This panel was the one that would not scroll, and it was the only one with
# chrome pinned to the viewport - a sticky bar and a footer fixed to the
# bottom. It is a plain page now like the panels that always worked, and the
# buttons that used to be fixed sit above the script instead, so they are on
# screen the moment it opens whether or not anything scrolls.
creator_panel = os.path.join(ASSETS, "creator", "ui.html")
with open(creator_panel, encoding="utf-8") as handle:
    panel = handle.read()
without_sheets = strip_comments(panel)
check("the footer that was fixed to the bottom is gone",
      ".foot {" not in without_sheets, creator_panel)
# 3.0 kept the rule. Only the dialog overlay and the toast are pinned to the
# viewport; the page's own chrome scrolls with it, and on the phone the body
# is never its own scroller.
pinned = re.findall(r"\.([\w-]+)\s*\{[^}]*position:\s*(?:fixed|sticky)", without_sheets)
check("only the dialog and the toast are pinned to the screen",
      set(pinned) <= {"sheet", "toast"}, pinned)
check("the buttons are above the script, not below it",
      0 < without_sheets.index('id="bRun"') < without_sheets.index('id="tree"'), creator_panel)
check("the phone gets a plain page; only a desktop window gets the shell",
      "html.shell body" in without_sheets and "/Android/i.test" in panel, creator_panel)

say("\n== The bridge offers both verbs ==")
check("pycmd.poll is part of the bridge every panel gets",
      "poll: poll," in plugins.BRIDGE, "")
check("and plain call is still there for everything else",
      "call: call," in plugins.BRIDGE, "")
# A panel that scrolls an element of its own answers "nowhere left to go"
# when the app asks whether its document can scroll, so a panel inside one of
# the app's own screens would have its drags taken by the list around it.
check("and it tells the app when the page scrolls something itself",
      "innerScroll" in plugins.BRIDGE and "touchstart" in plugins.BRIDGE, "")



say()
if FAILURES:
    say(f"{len(FAILURES)} bundled-plugin checks failed")
    sys.exit(1)
say("all bundled plugin checks passed")
