# The plugins that ship with PyCmd

Everything in the Plugins tab is off or on, and nothing here is downloaded.
There are two kinds, kept visibly apart because the difference matters:

**Built-in switches** change what the app itself does. Nothing is loaded at
runtime — the behaviour is already compiled into the APK, and the switch only
decides whether it is reachable. A switch cannot do anything the binary cannot
already do.

**Bundled plugins** are ordinary Python that ships inside the app. They are
installed for you on first run and left **off**, and when you turn one on it
runs with everything the app can do — exactly like a plugin you installed
yourself. They appear under *Ships with PyCmd*, and they cannot be deleted,
because the next start would only put them back.

Each of the five bundled plugins ships its own guide, which appears in
**Guides → From your plugins** once you switch it on.

If you want to write one of your own, [PLUGINS.md](PLUGINS.md) is the guide.

---

## Bundled plugins

### Server Pro

Makes the Servers tab somewhere you can work rather than somewhere you press
Start.

When it is on, a **Server Pro** card appears in the Servers tab with a live
board of everything running. For each server it shows the thing the tab could
not tell you on its own: whether the port **actually answers**. A thread being
alive is not the same as a service being up, and the difference is most of the
debugging.

* **Restart** stops a server and starts the same thing again on the same port,
  waiting for the socket to come back rather than racing it.
* **Kill** forces one down; **Stop** asks nicely first.
* **Free ports** finds the next eight ports nothing is listening on.
* **Write index.html** builds a real page listing a folder that has none, for
  when serving a folder shows a bare file listing.

Console commands:

| Command | What it does |
|---|---|
| `servers` | Everything running, with health, uptime and request counts |
| `serve <file-or-folder> [port]` | Starts anything — a script, a page, a folder |
| `restart <handle\|all>` | Stop and start again on the same port |
| `shut <handle\|all>` | Stop, and kill it if it will not go |
| `ports [from]` | Which ports are free |

### Cloud

Supabase and Firebase, over their REST APIs, with nothing to install. Neither
official SDK can be pip-installed onto a phone without a compiler, so this
talks to both services the way their SDKs do — JSON over HTTPS — and gives you
the same shape of API.

Connect a project once in **More → Cloud**. The keys are saved in the app's own
storage, never in the workspace, so exporting or sharing your files never
carries them along. After that the same project is reachable from a script, a
server, the console and the panel, signed in as the same user.

The panel does the everyday things: connect and test, sign a user up or in,
read and write rows or documents, browse storage, poke the Realtime Database,
call a Postgres function. It also adds a **Cloud storage** section to the Files
tab for sending a workspace file up or pulling one down.

It also adds two lines to the Files tab's file menu — *Upload to cloud storage*
on a file, *Upload every file in it* on a folder — and has settings of its own
in the plugin list: a default bucket, how many rows the panel reads, which
provider to start on, and whether to confirm deletes.

Console commands:

| Command | What it does |
|---|---|
| `cloud` | What is connected, and how to connect it |
| `sb select notes 5` | Read five rows |
| `sb insert notes {"text":"hi"}` | Write a row |
| `sb delete notes id=3` | Delete matching rows |
| `sb rpc my_function {"a":1}` | Call a Postgres function |
| `sb count notes` | How many rows match |
| `sb signin <email> <password>` | Sign in and keep the session |
| `sb buckets` / `sb ls <bucket>` | Storage |
| `sb up <bucket> <file>` / `sb down <bucket> <remote>` | Files up and down |
| `fb get notes/today` | Read a Firestore document |
| `fb set notes/today {"done":true}` | Write one |
| `fb list notes 20` | List a collection |
| `fb query notes done == false` | A structured query |
| `fb rt get rooms` | The Realtime Database |
| `fb up <file>` / `fb down <remote>` | Storage |

And from your own code:

```python
import pycmd_cloud

sb = pycmd_cloud.supabase()
rows = sb.table("notes").select("*").eq("done", False).order("id").limit(10).run()
sb.table("notes").insert({"text": "written from a server"})

fb = pycmd_cloud.firebase()
fb.firestore.set("notes/today", {"text": "hello", "done": False})
print(fb.firestore.query("notes", where=[("done", "==", False)], limit=5))
```

That is 116 operations across the two services: PostgREST filters and queries,
GoTrue sign-up, sign-in, OTP and the admin endpoints, Supabase Storage and edge
functions, Firestore documents and structured queries, Identity Toolkit, the
Realtime Database and Firebase Storage.

**What is deliberately missing:** Supabase realtime subscriptions and Firestore
listeners. Both are WebSocket protocols, `urllib` does not speak WebSocket, and
a fake built out of polling would be a worse thing to have than an honest gap.
Poll the read calls yourself if you need to; they are cheap.

### Packages Pro

Packages for everything that is not Python.

The Packages tab installs wheels from PyPI, which is the right answer for
Python and no answer at all for the other half of what people write here. A
page that wants htmx or a chart library has one option on a phone - a CDN - and
that means it only works with a connection, which for a loopback preview server
is not the same as working.

So this fetches the file. **Packages → Web libraries and kits**, or from the
console:

| Command | What it does |
|---|---|
| `web install htmx` | Vendors it into `vendor/htmx/`, and prints the tag to paste |
| `web install chart.js@4.4.0` | A version you pick |
| `web use htmx blog` | Copies it into `blog/vendor/`, where a page can actually load it |
| `web list` / `web remove <name>` | What is vendored, and undoing it |
| `web catalogue` | The seventeen with a one-tap button |
| `kit new blog flask` | A whole project the Servers tab can run |
| `kit kits` | The seven kits |

Seventeen libraries are written out by hand - htmx, Alpine, Tailwind,
Bootstrap, Bulma, normalize.css, three.js, Chart.js, D3, Vue, Preact, marked,
highlight.js, Lodash, Day.js and two self-hosted fonts - because npm packages
disagree about where their built file lives and a wrong guess is a broken page.
Anything else on npm works by its own name.

The kits are folders rather than files, because the Servers tab knows how to
run a folder: `flask`, `site`, `htmx`, `chart`, `three`, `api` and `cli`.

It cannot install what needs building - React with JSX, anything with a bundler
step, a Go module, a Rust crate - and says so rather than half-fetching it.

---

### Scheduler

Runs a script again every so often — a backup every ten minutes, a scrape every
hour — without writing a sleep loop into the script itself, which would stop it
being runnable any other way.

Adds a **Scheduled jobs** section to the Servers tab, and two commands:

| Command | What it does |
|---|---|
| `every 300 backup.py` | Run it every five minutes |
| `jobs` | What is scheduled, and when each one runs next |
| `jobs stop <id>` / `jobs stop all` | Stop one, or all of them |

Jobs live as long as the app does. Android gives an app no promise of being
alive later, so nothing here claims a schedule that survives being closed.

---

### Music Pro

Two DJ decks with a crossfader, the effects your phone already has, and a way
to reach the music you keep somewhere else.

**The decks** are two players of their own, deliberately not the Music tab's -
a deck is something you use while looking at it, two things play at once on
purpose, and neither belongs on your lock screen. **Cue** marks the point when
the deck is stopped and jumps back to it when it is playing, which is the
whole of how you line one track up against another that is already going.
**Loop in / Loop out** set a loop as the track passes them. **Tempo** runs
from half speed to double with the pitch corrected.

**The crossfader is equal-power.** Sliding one volume down while the other
comes up sounds like a dip in the middle - at halfway both are at 0.5, and two
half-volume signals are quieter than one full one. This uses the quarter-turn
of a circle instead, where both sides sit at 0.71 and the loudness stays put
across the whole sweep.

**The effects are Android's own** - a five-band equaliser, bass boost, stereo
widener, reverb and loudness enhancer - hung off each deck's audio session. A
phone can refuse any of them; a missing one is not drawn rather than pretended
at.

**Whatever else is playing** can be seen and driven: play, pause, skip, and
which app it is in. Every well-behaved Android music app publishes a media
session - it is what puts the track on your lock screen - so this is one
mechanism that works for all of them rather than a plugin per service. It
needs **notification access**, which only you can grant, and PyCmd opens the
Android screen where the switch is rather than asking for it itself.

It cannot read another app's library, search their catalogue from here, stream
from their service, or hold your password to one. What it can do is hand your
search *to* them, through the intent every music app answers: your words,
their catalogue, the account you already have with them.

**Free music** comes from two catalogues that exist to be searched by programs
and license their music to be kept - **Jamendo** (Creative Commons; needs a
free client id, and says so when there isn't one) and the **Internet Archive**
(live recordings the bands allow, and the public domain).

| Command | What it does |
|---|---|
| `deck a <words>` | Load the first matching track onto a deck |
| `mix 0-100` | Where the crossfader sits |
| `nowplaying` | What every app on this phone is playing |
| `findmusic <words>` | Search the free catalogues |

---

### Creator

A tab of its own where code is **built out of blocks** instead of typed - and
then saved as an ordinary file.

Nine hundred and four blocks across ten languages: **Python** (202),
**Go** (108), **Rust** (102), **C** (100),
**JavaScript** (138), **HTML** (70), **CSS**
(68), **Shell** (67), **Markdown**
(29) and **JSON** (20). Pick one, fill in its
holes, stack it, nest it inside a loop. Every row - in the palette and in your
script - is the line that block actually writes, so the screen is the code
rather than a description of it.

**Six of the ten run on this phone.** Python, JavaScript, C, Go, Rust and
Shell all have an engine in the app, so a program you built out of blocks can
be saved and then run. The other four are files you keep, serve or read.

Every language has an **example** you can start from - a whole program, not a
fragment - and the **Example** button loads it. An empty page is the worst
place to start learning a language.

**See the code** shows the whole file before anything is saved; **Save as a
file** puts a real `.py`, `.go`, `.rs`, `.c`, `.js`, `.html`, `.css`, `.sh`,
`.md` or `.json` in your workspace, and from there the editor opens it, the
Servers tab runs it and the Pages tab serves it like anything else. Each
language keeps its own script, so the chooser never throws work away.

JSON blocks carry no commas at all - the compiler puts them in - so the two
mistakes everybody makes writing JSON by hand cannot be made here, and a
project that is not valid JSON yet says so rather than saving quietly.

| Command | What it does |
|---|---|
| `blocks` | The projects in the drawer |
| `blocks langs` | The languages, and how many blocks each has |
| `blocks build <name>` | Print what a project writes |
| `blocks save <name>` | Write it into the workspace |

What it will not do is read a file back into blocks. That would mean a parser
for each language, kept correct forever, and the direction people want is this
one - where the colons, braces, indentation and closing tags are, which is the
fiddly part on a phone keyboard.

---

## Built-in switches

### The kit

| Plugin | What it does |
|---|---|
| **Polyglot Files** | Create and edit 30+ file types, not just `.py`. Decides which types the new-file menu offers, media included. |
| **Polyglot Runner** | Actually run them: C, Go, Rust and JavaScript on the device. |
| **Power Pack** | Turns the other plugins up — more snippets, more tools, more of each panel. |

Turning all three on is what the plugin list calls the full kit.

**Polyglot Files also brings in the things you do not write.** Music, video,
images, PDFs, archives and fonts appear in the new-file menu, and picking one
opens the phone's file picker instead of writing a template - an empty `.mp3`
is not a file anybody wanted. Audio and video then play in the preview, seek
bar and all. With the plugin off, the menu is Python, text and Markdown, the
way the app started.

### Languages, tools and workflow

| Plugin | What it does |
|---|---|
| **Snippets** | A bar of one-tap code fragments while you write, per language. |
| **Autosave** | Saves the editor a moment after you stop typing. |
| **Keep Awake** | Stops the screen sleeping while something is running. |
| **Downloader** | Fetch a file from a URL into Downloads. |
| **Workspace Export** | Zip the workspace, or any folder, and save it to the device. |
| **Workspace Search** | Search inside every file, not just the names. |
| **JSON Tools** | Validate, format and inspect JSON on its own screen. |
| **Text Tools** | Case, sort, dedupe, count, encode — the everyday text jobs. |
| **Regex Lab** | Write a pattern and watch it match, live. |
| **HTTP Client** | Build a request, send it, read the response. |

---

## Why the two kinds are kept apart

A built-in switch is auditable by construction: the code is in the binary you
installed, and the switch cannot reach anything else. A plugin — bundled or
yours — is Python running with the app's own powers, which is what makes
plugins worth having and also what makes them worth a warning. The install
screen says so before the file picker ever opens, and the same is true of the
three above: they are ours, but they are not a different kind of thing.
