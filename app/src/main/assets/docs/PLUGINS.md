# Writing a PyCmd plugin

Everything you need to build a plugin that installs, loads and works — the
file layout, the manifest, the Python API, the events, the HTML panel that
becomes its own tab, four complete working plugins, and the exact prompt to
hand an AI if you would rather have it written for you.

The app can show this document on the phone: **Plugins → How do I write one?**

---

## 1. What a plugin actually is

A plugin is **Python that PyCmd imports into its own interpreter**, plus an
optional **HTML page** that becomes a tab.

That gives you a lot: the whole standard library, anything you installed from
the Packages tab, the user's workspace, sockets, threads. It also means one
thing that has to be said before anything else:

> **A plugin is not sandboxed.** It runs with exactly the permissions the app
> has. It can read and rewrite every file in the workspace, open network
> connections, and keep running for as long as the app is open. CPython has no
> sandbox worth the name — `exec` in a stripped namespace stops nobody who can
> spell `__builtins__`. PyCmd warns before installing, lists what a plugin
> declares, and lets you switch it off or delete it in two taps. Beyond that,
> the protection is you reading the code.

Install one only if you wrote it or you trust whoever did.

---

## 2. The three shapes

Any of these installs from **Plugins → Install a plugin**, either from your
phone's file picker or from a folder you point at.

### One file

```
wordcount.py
```

The manifest lives in the file itself as a `PLUGIN` dict. Good for something
small.

### A folder

```
my-plugin/
├── plugin.json        the manifest
├── main.py            the entry point
├── ui.html            optional: the panel, which becomes a tab
├── helper.py          optional: your own modules, imported normally
└── assets/            optional: images, CSS, data files
    └── logo.png
```

### A zip of that folder

```
my-plugin.zip
```

Zipping the folder itself or its contents both work — PyCmd strips a single
wrapping directory if it finds one.

---

## 3. The manifest

`plugin.json`:

```json
{
  "id": "com.yourname.wordcount",
  "name": "Word Count",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "Counts words, lines and characters in the open file.",
  "entry": "main.py",
  "panel": "ui.html",
  "tab": {
    "title": "Words",
    "description": "Counts what you have written",
    "icon": "icon.png"
  },
  "commands": [
    { "name": "wc", "help": "wc <text> — count words in some text" }
  ],
  "permissions": ["files"]
}
```

| Key | Required | What it does |
|---|---|---|
| `id` | **yes** | Unique. Lower-case letters, digits, `.`, `-`, `_`. Reinstalling the same id replaces the old copy. |
| `name` | **yes** | Shown in the plugin list. |
| `version` | no | Any string. Shown next to the name. Defaults to `1.0.0`. |
| `author` | no | Shown in the list. |
| `description` | no | One paragraph. Up to 600 characters. |
| `entry` | no | The module PyCmd imports. Defaults to `main.py`. |
| `panel` | no | An HTML file. Having one is what gives the plugin an **Open** button and a tab. |
| `tab` | no | Publishes a place of your own in the **More** screen. Needs `panel` — the tab is what opens it. See below. |
| `extends` | no | Puts a section of yours inside one of the app's **own** screens. See below. |
| `settings` | no | Controls the app renders for you in the plugin's row. See below. |
| `actions` | no | Lines you add to a file's or folder's menu in the Files tab. See below. |
| `guides` | no | Documents of yours, listed in the app's Guides screen. See below. |
| `commands` | no | Console commands, for the list and the help text. You still register the handler in code. |
| `permissions` | no | `files`, `network`, `console`, `servers`, `packages`. **Documentation, not enforcement** — they are shown to the user so they know what to expect. Declare honestly. |

### Your own tab in More

`tab` is how a plugin adds a destination without the app changing to make room
for it. Three things, and that is the whole of it:

```json
"tab": {
  "title": "Words",
  "description": "Counts what you have written",
  "icon": "icon.png"
}
```

| Field | What it is |
|---|---|
| `title` | What the row says. Up to 24 characters — it is a tab name, not a sentence. |
| `description` | The line under it. Up to 120 characters. Falls back to the plugin's `description`. |
| `icon` | A **picture that ships inside your plugin**: `.png`, `.jpg`, `.webp` or `.gif`, alongside `main.py`. Around 96×96 is right. Naming a file that is not there is an error, not a shrug — a tab with a broken icon would look like the app's fault. `.svg` is accepted in the manifest but not drawn; those fall back to a generic mark. |

The row appears in **More**, under *From your plugins*, and only while the
plugin is switched **on**. Tapping it opens your panel. A plugin with a `panel`
but no `tab` still gets its **Open** button in the plugin list — the tab is for
something you will come back to often enough to want it one tap away.

### A section inside one of the app's own screens

A tab is a place beside the app. `extends` is a card **inside** it, which is
what you want when your plugin is *about* a screen that already exists — a
server tool belongs in Servers, not next to it.

```json
"extends": [
  {
    "tab": "servers",
    "title": "Server Pro",
    "description": "Live board, health checks and restart",
    "panel": "board.html",
    "height": "tall",
    "icon": "icon.png",
    "open": true
  }
]
```

| Field | What it is |
|---|---|
| `tab` | Which screen. One of `files`, `servers`, `packages`, `downloads`, `plugins`, `system`, `debug`, `guides`, `pages`, `music`. A name that is not on the list is refused at install time rather than silently never rendering. |
| `panel` | The HTML file for this section. Defaults to the plugin's `panel`. |
| `title`, `description` | The card's heading and its line of explanation. |
| `height` | `short` (220dp), `medium` (400dp) or `tall` (620dp). |
| `icon` | A picture in your plugin, same rules as a tab's. |
| `open` | `true` to start expanded. Off by default: a screen someone opened for another reason should not rearrange itself. |

You can list up to eight, on different screens. Sections only appear while the
plugin is switched **on**, and the panel inside one is not built until it is
opened, so a collapsed section costs a heading and nothing else.

The console and the editor are not on the list. Both are a WebView filling the
screen with nowhere a card could go that would not be in the way; reach those
two with console commands, `api.print`, and the file events.

### Settings, without building a panel for them

A plugin with one switch used to need a whole HTML page to offer it. Declare
them instead and the app draws real controls in your row of the plugin list:

```json
"settings": [
  { "name": "bucket", "type": "text",   "label": "Default bucket", "default": "" },
  { "name": "rows",   "type": "number", "label": "Rows to read",   "default": 25 },
  { "name": "loud",   "type": "switch", "label": "Say so",         "default": false },
  { "name": "mode",   "type": "choice", "label": "Start on",
    "options": ["fast", "slow"], "default": "slow" }
]
```

Read them with `api.setting("bucket")`, which gives you the user's choice or
your default. `api.set_setting(name, value)` writes one from code. The value is
typed on the way in — a switch is a real `bool`, a number a real number — and a
type that is not one of the four is refused at install time.

### Lines in a file's menu

```json
"actions": [
  { "target": "file", "label": "Upload to cloud", "export": "upload_picked",
    "types": ".png, .jpg" },
  { "target": "folder", "label": "Upload all of it", "export": "upload_folder" }
]
```

Each one appears in the ⋮ menu of a matching file (or folder) in the Files tab,
with your plugin's name beside it. Tapping it calls your export with
`{"path": ..., "name": ..., "is_folder": ...}`. `types` is optional; leave it
out and the line appears on everything.

### Your own guide, in the Guides screen

A plugin can be installed, switched on, and still leave nobody any the wiser
about what to type. Ship a document with it:

```json
"guides": [
  { "file": "GUIDE.md", "title": "Using Widgets", "summary": "The short version" },
  "reference.md"
]
```

`.md`, `.txt` and `.html` are accepted, up to six of them. A bare file name
works too and gets its title from the name. They appear in **Guides** under
*From your plugins* while the plugin is switched on, and open in the same
reader the app's own guides use — so Markdown renders, headings get a contents
panel, and the text wraps.

Naming a file that is not there is refused at install time, as is anything the
reader cannot show.

### Asking the app to do something

```python
api.open_file("notes/a.md")     # opens it in the editor
api.run_file("build.py")        # runs it, in whatever language it is
api.preview("report.html")      # opens it in the preview
api.serve("site", 8000)         # starts it as a server
api.new_file("out.txt", text)   # creates it and opens it
api.go_to("servers")            # switches screen
api.open_panel()                # opens your own panel, full screen
api.refresh("files")            # something changed underneath the app
```

Every one is a *request*, not a call: your code runs on whatever thread it
happens to be on and the app has to do these on its own, so they return
whether the request was delivered and never wait for it to finish. They are
also ignored if your plugin has been switched off in the meantime.

For a single-file plugin, put the same object in the module as a `PLUGIN`
dict:

```python
PLUGIN = {
    "id": "com.yourname.wordcount",
    "name": "Word Count",
    "version": "1.0.0",
    "commands": [{"name": "wc", "help": "wc <text>"}],
}
```

PyCmd reads that **without importing your module** — it parses the file and
evaluates only that literal. Deciding whether to run something by running it
would defeat the point.

---

## 4. The entry point

PyCmd imports your entry module and, if it finds a function called `setup`,
calls it with the API object:

```python
def setup(api):
    api.log("hello from my plugin")
```

Everything you register — commands, exports, event handlers — is registered
inside `setup`. Module-level code runs too, but `setup` is where the API is
handed to you.

If you want to clean up when the plugin is switched off:

```python
def teardown(api):
    api.log("goodbye")
```

Inside your entry module the API is also available as a module global named
`pycmd`, and your folder is `PLUGIN_DIR`:

```python
def helper():
    pycmd.log("callable from anywhere in the module")
    with open(f"{PLUGIN_DIR}/data.json") as handle:
        ...
```

Your plugin's folder is on `sys.path` while it loads, so `import helper` finds
`helper.py` next to `main.py`.

---

## 5. The API

Everything below is on the `api` object handed to `setup`.

### Talking to the user

```python
api.print("straight to the console the user is looking at")
api.print("no newline", end="")

api.log("goes to the debug console")          # info
api.warn("something looks off", "detail")     # warning
api.error("that failed", traceback_text)      # error, counted in the badge

api.toast("a short message at the bottom of the screen")
```

Use `print` for output the user asked for, `log`/`warn`/`error` for everything
else. The debug console is where plugin noise belongs.

### Files

```python
api.workspace_path()                 # /data/.../files/workspace
api.workspace_path("notes", "a.md")  # a path inside it

text = api.read("notes/a.md")             # None if it is not there
text = api.read("notes/a.md", "")         # or a fallback you choose
api.write("notes/a.md", "new contents")   # makes parent folders, returns True/False

for path in api.files("*.py"):       # every match in the workspace
    ...
```

Relative paths are resolved against the workspace. Absolute paths are used as
given — you can reach outside the workspace, and normal Python file handling
works too. `api.read`/`api.write` are conveniences, not a fence.

### Your own storage

```python
data = api.store()                    # a dict, {} the first time
data["count"] = data.get("count", 0) + 1
api.store(data)                       # saved as JSON next to your plugin
```

Deleted with the plugin. Good for settings and small state; use a real file or
a database in the workspace for anything larger.

### Console commands

```python
@api.command("todo", help="todo add <text> | todo list")
def todo(argument):
    api.print(f"you said: {argument}")
```

The user types `todo add milk` in the console and your handler gets
`"add milk"` — everything after the first word, as one string. Split it
yourself if you want arguments: `argument.split()`.

A command wins over Python only when the first word matches a command you
registered **and** the line has no `=` in it, so an ordinary assignment is
never swallowed.

Two ways to show something, and both work: call `api.print(...)`, or just
**return a string** and PyCmd prints it. Returning was silently ignored until
version 1.4, which was a trap worth closing — it is the obvious thing to write.

### Functions the panel can call

```python
@api.export
def analyse(payload):
    return {"words": len(payload["text"].split())}

@api.export(name="load_text")
def load(payload=None):
    return api.store().get("text", "")
```

An export takes one argument — whatever the panel passed, already decoded from
JSON — and returns anything JSON can carry. If your export takes no argument,
the panel can call it with none.

### Supabase and Firebase

`pycmd_cloud` ships with the app, so a plugin can reach either service without
asking the user to install anything:

```python
import pycmd_cloud

def setup(api):
    @api.command("todo", help="todo - read the shared list")
    def todo(argument):
        rows = pycmd_cloud.supabase().table("todo").select("*").limit(10).run()
        return "\n".join(row["text"] for row in rows)
```

It uses whatever project the user connected in **More → Cloud**, signed in as
whoever they signed in as. If nothing is connected it raises `CloudError`, which
is the right thing to catch and explain. [BUILTINS.md](BUILTINS.md) lists what
both clients can do.

### Running your own file type

If your plugin teaches PyCmd about a new kind of file, it can run one too — in
the Servers tab, alongside a Python script or a served page:

```python
import pycmd_servers

def setup(api):
    def run_widget(path, channel):
        # Called on the server's own thread, with stdout, stderr and stdin
        # already pointed at that server's console. Return when it is done;
        # raise and the error is reported like any other server error.
        with open(path) as handle:
            api.print(handle.read())

    pycmd_servers.register_runner(".widget", run_widget,
                                  "Run by the Widget plugin")
```

The third argument is what the launcher shows *before* anything starts, so the
user knows what pressing Run will do. `.py` cannot be claimed — that one is the
app's. Call `pycmd_servers.unregister_runner(".widget")` if you ever need it
back.

This is the same mechanism the app uses for JavaScript: a `.js` file is run by
a runner registered from Kotlin, because the engine is the device's WebView and
Python cannot reach it.

### Events

```python
@api.on("file_saved")
def saved(event):
    api.log("saved", event["path"])
```

| Event | When | Payload |
|---|---|---|
| `file_saved` | the editor wrote a file | `{"path": "...", "name": "..."}` |
| `file_opened` | a file was opened in the editor | `{"path": "...", "name": "..."}` |
| `run_started` | a script started | `{"path": "...", "language": "..."}` |
| `run_finished` | a script ended | `{"path": "...", "status": "ok\|error\|stopped"}` |
| `console_run` | the user ran a console line | `{"source": "..."}` |
| `server_started` | a server came up | `{"handle": "...", "port": 8000, "kind": "static"}` |
| `server_stopped` | a server went away | `{"handle": "..."}` |
| `plugin_loaded` | your plugin finished loading | `{"id": "..."}` |

Handlers run on whichever thread raised the event. Keep them quick; if you
need to do real work, start a thread.

An exception in a handler is caught, logged against your plugin, and the other
handlers still run. It will not take the app down.

### Pushing to your panel

```python
api.send({"kind": "progress", "done": 3, "total": 10})
```

Arrives in the panel as a `message` event. Ignored if no panel is open.

---

## 6. The panel: your own tab

Any HTML file works. PyCmd injects a stylesheet that matches the app and a
`window.pycmd` bridge, so a plain file is already a usable screen:

```html
<h1>Word Count</h1>
<div class="card">
  <textarea id="input" rows="6" placeholder="Paste some text"></textarea>
  <p><button id="go">Count</button></p>
  <pre id="out">—</pre>
</div>

<script>
  document.getElementById('go').onclick = async () => {
    const text = document.getElementById('input').value;
    const result = await pycmd.call('analyse', { text });
    document.getElementById('out').textContent = JSON.stringify(result, null, 2);
  };
</script>
```

### The panel API

```js
await pycmd.call('export_name', payload)   // runs your Python, resolves with its return
await pycmd.poll('export_name', payload)   // the same, for a refresh on a timer
pycmd.on('message', (data) => { ... })     // receives api.send(...)
pycmd.on('theme', (theme) => { ... })      // the user changed theme
pycmd.toast('done')                        // the app's toast
pycmd.log('something happened')            // the debug console
pycmd.close()                              // back to the plugin list
pycmd.plugin                               // { id, name, version, author }
pycmd.theme()                               // { dark, motion, theme }
pycmd.colour('accent')                      // one of the app's colours, as hex
```

### Looking like part of the app

This is the bit worth reading. Before 2.7.0 the injected stylesheet had a blue
palette of its own, and the result was exactly what people said it was: the
plugins looked like a different app that had been connected to this one. They
were not — they just had their own colours, their own button shape and their
own idea of how big a gap between two cards should be.

So: **write no colours of your own.** The app declares its whole palette as
CSS custom properties on `:root` and hands your panel whichever theme the user
has on — Classic Green, Halloween, Paper, or one of their own twenty-colour
creations. A panel that uses the variables follows all of them for free. A
panel with `#2E7DD1` in it stays blue in every theme, for ever.

```css
.mine {
  background: var(--surface);
  border: 1px solid var(--outline);
  color: var(--fg);
  border-radius: var(--radius);
}
.mine .pressed { background: var(--accent); color: var(--on-accent); }
```

| | |
|---|---|
| `--bg` | behind everything |
| `--surface` | cards |
| `--surface-high` | a card on a card; the unpressed button |
| `--outline` | hairlines and card edges |
| `--fg` | body text |
| `--muted` | labels and captions |
| `--accent`, `--accent-dim`, `--accent-soft`, `--on-accent` | the one colour the app is known by |
| `--info`, `--warning`, `--danger` | notices, "careful", errors |
| `--kw`, `--builtin`, `--str`, `--num`, `--comment`, `--def`, `--self`, `--decorator` | syntax, if you highlight anything |
| `--radius` | the user's corner setting, in px |
| `--font-size`, `--line-height` | the user's code text size |

And **write no components of your own** unless you need to. The injected
stylesheet already dresses plain HTML: `<button>`, `<input>`, `<textarea>`,
`<select>`, `<input type="range">`, `<input type="checkbox">`, `<table>`,
`<pre>`, `<kbd>` and `<progress>` all come out looking like the app, and these
classes are there when an element is not enough:

| | |
|---|---|
| `.card` | the app's card. `.card.lead` for the one with the main action in it |
| `.section` | a small upper-case heading above a card, as the app's screens use |
| `.row` | a label on the left, a value on the right — the app's info row |
| `.bar` | a strip of controls that wraps instead of overflowing |
| `.grid` | a responsive grid of equal cards |
| `button.primary`, `.danger`, `.ghost`, `.wide` | the four buttons |
| `.pill`, `.pill.on`, `.dot`, `.dot.on` | a state label, and the running dot |
| `.note`, `.note.warn`, `.note.bad` | something to read before pressing anything |
| `.empty` | a panel with nothing to show yet should say so |
| `.tabs` | a scrolling row of pills across the top |
| `ul.list` | a list of things to choose between |
| `.muted` | quieter text |

Two things you get without asking. `:root[data-pycmd-motion="reduced"]` turns
off every transition and animation in your panel when the user has asked for
short animations, so do not fight it. And `pycmd.theme().dark` tells you which
way round the palette is, for the one case CSS cannot cover: a `<canvas>` that
has to pick its own stroke colour. `pycmd.colour('accent')` reads any of the
variables above as a hex string for the same reason.

`pycmd.call` returns a promise. If your Python raises, the promise rejects
with the error message — so `try { await … } catch (e) { … }` shows the user
something better than nothing. A call that is never answered rejects on its
own after two minutes rather than leaving the page waiting for ever.

### Refreshing on a timer

If your panel re-reads something every few seconds, use `pycmd.poll` instead
of `pycmd.call`, and stop while nobody is looking:

```js
async function refresh() {
  if (document.hidden) return;          // the panel is behind another tab
  draw(await pycmd.poll('board_now', {}));
}
setInterval(refresh, 2000);
```

`poll` is `call` with one difference: if the very same question is already on
its way, it waits for that answer rather than asking again. On a busy phone
the tick comes round before the reply does, and without this a panel left open
builds a queue of identical questions that everything else waits behind.

**Use `call` for anything that changes something.** Two presses of *Add* with
the same values in the form are two jobs, and `poll` would quietly make them
one. `poll` is for reads.

### A panel that is taller than the screen

**Write an ordinary page and let the document scroll.** That is the whole
advice, and it is worth saying because the obvious alternatives do not work
here.

**Never use a percentage height.** `html, body { height: 100% }` is the usual
way to build a fixed header with a scrolling middle, and in this WebView it
collapses the panel to nothing — a black screen with a sliver of content at
the top. Whatever the percentage resolves against while the panel is first
laid out is not the height it ends up with, and it does not recover. A whole
release shipped that way. `vh` is the same bet; do not take it either.

**Be careful with `position: fixed` and `position: sticky` chrome.** The
Creator tab spent three releases as the only panel that could not be scrolled,
and it was the only one with a sticky bar and a footer fixed to the bottom.
It is a plain page now, and its buttons sit above the content rather than
being pinned below it — so they are on screen the moment it opens without
anything having to scroll. That is a good pattern to copy: **put what must be
reachable at the top**.

A fixed overlay that is `display: none` until you open it is fine — the block
picker is one, and it has always worked. It is chrome that is *always* pinned
that causes trouble.

The app is told which parts of your page scroll — it watches where each touch
lands — so a panel sitting inside one of the app's own screens keeps its own
drags instead of losing them to the list around it. That comes with the
bridge; there is nothing to call.

Your own CSS, images and scripts load from the plugin folder with relative
paths (`<img src="assets/logo.png">`). The page cannot navigate anywhere else:
links out are blocked, deliberately.

Set `tab` in the manifest and the panel gets a title of its own in the
plugin list and in **More**.

---

## 7. Four plugins that work

Copy any of these, install it, switch it on.

### 7.1 One file, one command

`greet.py`

```python
PLUGIN = {
    "id": "demo.greet",
    "name": "Greet",
    "version": "1.0.0",
    "description": "A command that says hello.",
    "commands": [{"name": "greet", "help": "greet <name>"}],
}


def setup(api):
    @api.command("greet", help="greet <name>")
    def greet(argument):
        who = argument.strip() or "world"
        api.print(f"hello, {who}")
```

Type `greet Ada` in the console.

### 7.2 Reacting to what the user does

`autobackup.py`

```python
import os
import time

PLUGIN = {
    "id": "demo.autobackup",
    "name": "Auto Backup",
    "version": "1.0.0",
    "description": "Keeps the last copy of every file you save, under .backups/.",
    "permissions": ["files"],
}


def setup(api):
    @api.on("file_saved")
    def backup(event):
        path = event.get("path", "")
        if not path or ".backups" in path:
            return
        text = api.read(path)
        if text is None:
            return
        stamp = time.strftime("%Y%m%d-%H%M%S")
        name = os.path.basename(path)
        api.write(f".backups/{name}.{stamp}", text)
        api.log("backed up", name)
```

### 7.3 A panel with a tab

`counter/plugin.json`

```json
{
  "id": "demo.counter",
  "name": "Line Counter",
  "version": "1.0.0",
  "description": "Counts the lines of code in the workspace.",
  "entry": "main.py",
  "panel": "ui.html",
  "tab": { "title": "Lines" },
  "permissions": ["files"]
}
```

`counter/main.py`

```python
import os

PLUGIN = None  # the manifest is in plugin.json


def setup(api):
    @api.export
    def scan(payload=None):
        rows = []
        total = 0
        for path in api.files("*.py"):
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    lines = sum(1 for _ in handle)
            except OSError:
                continue
            total += lines
            rows.append({"name": os.path.basename(path), "lines": lines})
        rows.sort(key=lambda row: -row["lines"])
        return {"total": total, "files": rows[:50]}
```

`counter/ui.html`

```html
<h1>Lines of Python</h1>
<div class="card">
  <button id="scan">Scan the workspace</button>
  <p id="total"></p>
  <table id="rows"></table>
</div>

<script>
  document.getElementById('scan').onclick = async () => {
    const data = await pycmd.call('scan');
    document.getElementById('total').textContent = data.total + ' lines in ' + data.files.length + ' files';
    document.getElementById('rows').innerHTML = data.files
      .map((row) => `<tr><td>${row.name}</td><td style="text-align:right">${row.lines}</td></tr>`)
      .join('');
  };
</script>
```

### 7.4 A background worker that reports progress

`watcher/plugin.json`

```json
{
  "id": "demo.watcher",
  "name": "Workspace Watcher",
  "version": "1.0.0",
  "description": "Watches the workspace and tells its panel when something changes.",
  "entry": "main.py",
  "panel": "ui.html",
  "tab": { "title": "Watcher" },
  "permissions": ["files"]
}
```

`watcher/main.py`

```python
import os
import threading
import time

STATE = {"running": False}


def setup(api):
    def snapshot():
        return {p: os.path.getmtime(p) for p in api.files("*")}

    def loop():
        previous = snapshot()
        while STATE["running"]:
            time.sleep(2)
            current = snapshot()
            changed = [p for p, t in current.items() if previous.get(p) != t]
            if changed:
                api.send({"changed": [os.path.basename(p) for p in changed]})
            previous = current

    @api.export
    def start(payload=None):
        if STATE["running"]:
            return {"running": True}
        STATE["running"] = True
        # A daemon thread dies with the app, which is what you want here.
        threading.Thread(target=loop, daemon=True).start()
        return {"running": True}

    @api.export
    def stop(payload=None):
        STATE["running"] = False
        return {"running": False}


def teardown(api):
    STATE["running"] = False
```

`watcher/ui.html`

```html
<h1>Watcher</h1>
<div class="card">
  <button id="start">Start</button>
  <button id="stop">Stop</button>
  <ul id="log"></ul>
</div>

<script>
  document.getElementById('start').onclick = () => pycmd.call('start');
  document.getElementById('stop').onclick = () => pycmd.call('stop');
  pycmd.on('message', (data) => {
    const item = document.createElement('li');
    item.textContent = new Date().toLocaleTimeString() + ' — ' + data.changed.join(', ');
    document.getElementById('log').prepend(item);
  });
</script>
```

---

## 8. Installing and testing

1. Put the plugin somewhere the phone can reach — the workspace, Downloads,
   or a cloud folder your file picker can see.
2. **Plugins → Install a plugin → File or zip** (or **Folder**).
3. Read the warning. Install.
4. Switch it on. It loads immediately; the switch is what runs it.
5. Check the **debug console** (the bug icon in the top bar). Everything your
   plugin logs, and every error it raises, lands there with its name attached.

If it does not load, the plugin's card shows the traceback in red. The most
common causes, in order: a typo in `plugin.json`, an `entry` that names a file
that is not there, and an import of a package that is not installed — install
it from the Packages tab first.

**Reinstalling replaces.** Same `id`, new files: install again and the old copy
is unloaded and deleted first. There is no need to remove it by hand while you
iterate.

---

## 9. Rules and limits

- **The interpreter is shared.** Your plugin runs in the same CPython as the
  user's scripts. Do not `sys.exit()`, do not replace `sys.stdout` permanently,
  do not `os.chdir` and leave it changed.
- **Blocking blocks.** A `setup` that sleeps for ten seconds freezes the plugin
  list for ten seconds. Do long work in a thread.
- **Threads must be daemons.** `threading.Thread(target=…, daemon=True)`, or
  the app will not close cleanly.
- **Size**: 32 MB and 2000 files per plugin.
- **A zip cannot write outside its own folder.** Paths with `..` are refused at
  install time.
- **Exports return JSON.** Return dicts, lists, strings, numbers, booleans and
  `None`. Anything else is turned into a string.
- **The panel cannot navigate.** No links out, no iframes to the web. Fetch
  through your Python if you need the network.
- **Nothing is verified.** Not by the app, not by anyone. Your plugin is as
  trustworthy as its author.

---

## 10. The prompt to hand an AI

Paste this into any capable model, replace the last line, and you get a plugin
that installs into this app without editing.

````text
Write a plugin for PyCmd, an Android app that embeds CPython 3.13.

PLUGIN FORMAT
A plugin is either:
  (a) a single .py file with a module-level PLUGIN = {...} dict, or
  (b) a folder containing plugin.json plus an entry module (default main.py),
      and optionally an HTML panel file.

plugin.json / PLUGIN keys:
  id           required, unique, lowercase [a-z0-9._-]
  name         required
  version, author, description   optional strings
  entry        optional, default "main.py"
  panel        optional HTML file; having one gives the plugin an Open button
  extends      optional, puts a card of yours inside one of the app's own
               screens. A list of:
               {"tab": "files|servers|packages|downloads|plugins|system|debug|
                        guides|pages|music",
                "title": "...", "description": "...", "panel": "section.html",
                "height": "short|medium|tall", "icon": "icon.png", "open": false}
  settings     optional, controls the app draws in the plugin list. A list of
               {"name": "...", "type": "text|number|switch|choice",
                "label": "...", "help": "...", "default": ..., "options": [...]}
               Read with api.setting("name").
  actions      optional, lines in a file's or folder's menu in the Files tab:
               {"target": "file|folder", "label": "...", "export": "fn",
                "types": ".png,.jpg"}  -> fn({"path","name","is_folder"})
  guides       optional, documents listed in the app's Guides screen:
               [{"file": "GUIDE.md", "title": "...", "summary": "..."}]
               or just ["GUIDE.md"]. .md, .txt or .html, up to six.
  tab          optional, publishes a row in the app's More screen. Needs panel.
               {"title": "<=24 chars",
                "description": "<=120 chars, one line",
                "icon": "icon.png"}   <- a real image file inside the plugin
                                         (.png/.jpg/.webp/.gif, about 96x96).
               Naming a file that is not there is rejected at install time.
  commands     optional [{"name": "...", "help": "..."}]
  permissions  optional subset of ["files","network","console","servers","packages"]
               (documentation only - shown to the user, not enforced)

ENTRY MODULE
Define `def setup(api):` - PyCmd calls it with the API object. Optionally
`def teardown(api):`. Inside the module, `pycmd` is the same API object and
`PLUGIN_DIR` is the plugin's folder. The folder is on sys.path during load.

THE API
  api.print(*values, sep=" ", end="\n")   -> the user's console
  api.log(msg, detail="")                 -> debug console (also .warn, .error)
  api.toast(msg)                          -> a short on-screen message
  api.workspace_path(*parts)              -> path inside the workspace
  api.read(path, default=None)            -> text or default
  api.write(path, text) -> bool           -> creates parent folders
  api.files(pattern="*")                  -> matching paths in the workspace
  api.store()          -> dict            -> this plugin's saved JSON
  api.store(dict)                         -> saves it
  api.send(obj)                           -> pushes a message to the panel
  api.setting(name, default=None)         -> what the user chose
  api.set_setting(name, value)

  ASKING THE APP (requests; they do not wait, and return whether delivered)
  api.open_file(path) | api.run_file(path) | api.preview(path)
  api.serve(path, port=0) | api.new_file(name, text) | api.open_panel(panel="")
  api.go_to("console|editor|files|servers|packages|downloads|plugins|system|
             debug|guides|pages|music|more")
  api.refresh("files|servers|downloads|packages|plugins|pages|music")

  @api.command("name", help="...")        -> console command; handler(argument: str)
                                             argument is everything after the
                                             first word, as one string; return
                                             a string and it is printed
  @api.export                             -> callable from the panel; f(payload) -> JSON
  @api.export(name="other_name")
  @api.on("event")                        -> handler(event: dict)

SUPABASE AND FIREBASE (optional)
  import pycmd_cloud
  sb = pycmd_cloud.supabase(); fb = pycmd_cloud.firebase()
  sb.table("t").select("*").eq("done", False).limit(10).run() / .insert / .update
  sb.auth.sign_in(email, pw) | sb.storage.upload_file(bucket, name, path)
  fb.firestore.get/set/update/delete/list/query | fb.rtdb.get/set/push
  Uses the project the user connected in More -> Cloud. Raises CloudError.

RUNNING YOUR OWN FILE TYPE (optional)
  import pycmd_servers
  pycmd_servers.register_runner(".ext", fn, "what the launcher should say")
  fn(path, channel) runs on the server's thread with stdout/stdin already
  bound to that server's console. ".py" cannot be claimed.

EVENTS
  file_saved {path,name} | file_opened {path,name} | run_started {path,language}
  run_finished {path,status} | console_run {source} | server_started {handle,port,kind}
  server_stopped {handle} | plugin_loaded {id}

THE PANEL (optional HTML file)
PyCmd injects a dark stylesheet and a bridge. Available in the page:
  await pycmd.call('export_name', payload)  -> resolves with the Python return
  await pycmd.poll('export_name', payload)  -> the same, for a timer refresh
  pycmd.on('message', cb)                   -> receives api.send(...)
  pycmd.toast(text) | pycmd.log(text) | pycmd.close() | pycmd.plugin
Relative paths load from the plugin folder. The page cannot navigate away.

RULES
- The interpreter is shared with the user's scripts: never sys.exit(), never
  leave sys.stdout replaced or the working directory changed.
- Never block in setup(); use threading.Thread(..., daemon=True).
- Exports must return JSON-serialisable values.
- Only the standard library, unless you state which package the user must
  install from the Packages tab first.
- Handle your own errors and report them with api.error(...).

OUTPUT
Give me every file in full, each in its own code block with its filename as
the heading, ready to zip. No placeholders, no "..." - working code.

THE PLUGIN I WANT:
<describe it here - what it does, what it shows, what it reacts to>
````

---

## 11. Where things live on the device

```
files/
├── workspace/          what the user writes; api.read/write default here
├── plugins/
│   └── <plugin id>/    your files, exactly as installed
│       └── .state.json api.store()
└── downloads/          the Downloads tab
```

Removing a plugin deletes its folder, `.state.json` and all. Files it wrote
into the workspace stay.

---

## 12. If you get stuck

- The **debug console** has everything: load errors with tracebacks, every
  `api.log`, and anything your panel logged.
- **Plugins → your plugin → Files** lists what actually got installed, which
  settles most "but I zipped it" questions.
- A plugin that will not load can still be **removed**, and installing a fixed
  copy with the same `id` replaces it.
