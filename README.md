# PyCmd

A programmer's console for Android. Write and run code on the phone itself —
no server, no connection, no desktop involved.

Six languages actually run on the device: **Python**, **C**, **Go**, **Rust**,
**JavaScript** and shell. Python is CPython 3.13, embedded through
[Chaquopy](https://chaquo.com/chaquopy/); C, Go and Rust run on interpreters
written for this app, because Android has not allowed an app to execute code it
compiled itself since API 29; JavaScript is handed to the engine the device
already has. Another twenty file types are edited, highlighted, previewed and
served, and music, video, images, PDFs, archives and fonts are brought in from
the phone, kept, served and played.

Version 2.5.9. Kotlin and Jetpack Compose for the app, JavaScript for the console
and editor.

---

## What it does

**Console** — a real REPL, with a shell in front of it. `pip install flask`
works as typed, and so do `ls`, `cd`, `cat`, `run`, `serve`, `open`, `tree`,
`find` and a dozen more; everything else is Python. The split is narrow on
purpose - `ls` is a command, `ls = [1, 2]` is an assignment, and a name you
have defined always wins. Type an expression and its value is printed back;
type a block and it runs. Output streams in as it is produced rather than
appearing all at once when the script ends, `input()` prompts you and waits,
and Stop interrupts a runaway loop. Terminal colours from libraries like `rich`
render properly. Completions for names in your session appear as you type.

**Editor** — syntax highlighting for every language it knows, line numbers,
auto-indent that follows *that* language's rules, bracket matching, a snippet
bar and a key strip that both change with the file type, optional line
wrapping with a gutter that stays aligned, go-to-line, and autosave. Every
width and height is computed from the font rather than measured off the page,
so a line has no length at which it stops being editable. Run the open file
straight from the toolbar, whatever language it is.

**Files** — a private workspace you can browse, filter, create in, rename and
delete. Upload files or a whole folder from anywhere on the device; if the name
is already taken it asks whether to replace or keep both, rather than quietly
leaving you with the old copy. The new-file menu also lists music, video,
images, PDFs, archives and fonts: picking one of those opens the phone's picker
instead of writing a template, because an empty `.mp3` is not a file anybody
wanted. Tapping media opens the player rather than the editor, and a file that
is bytes rather than text is never loaded into a text box it could be ruined
in. Examples ship on first launch, including two working plugins, and deleting
them sticks.

**Preview** — HTML, CSS, Markdown, JavaScript, JSON, CSV, SVG, images, and
music and video that actually play. A page is served over a loopback HTTP
server rooted at its own folder, so it behaves like a real site: scripts run,
`fetch` works, relative paths resolve, and links inside the site follow. That
server answers byte ranges, which is what lets you drag through the middle of a
track or a film instead of only playing it from the start. Whatever the page
logs or throws is copied into the debug console.

**Downloads** — a folder kept apart from the workspace: files fetched from a
URL, workspace and folder exports, and anything you add from the phone. Each
one can be opened, copied into the workspace, or saved back out to the device.

**Packages** — install pure-Python libraries from PyPI onto the device at
runtime, from the tab or with `pip install` in the console. **Look it up first**
asks PyPI what a package is and whether it can work here *before* the download,
so a library that ships only compiled wheels is a sentence rather than a wasted
minute. `requests`, `flask` and `rich` are already built in. The **Packages
Pro** plugin adds everything that is not Python: JavaScript and CSS libraries,
web fonts and whole starter projects, vendored into the workspace so a page
works with no connection.

**Pages** — websites that live in the app. Point one at a folder you already
have in the workspace (up to 70), switch it on (up to 25 at a time) and it is
served from the phone for real. Nothing to point at yet is a template away: a
static site, a Flask app with templates, a JSON API, or an empty folder, made
at the top of the workspace under its own name rather than in a `pages/` folder
the app invented. What a page *is* stays in the workspace where you can edit
it; what happened to it - what was deployed, where, when - is kept in the app's
own storage, one folder per page, so a deploy never leaves a build folder in
your files. Each page
keeps its name, its port and its files, so running it again is a tap. **Share**
puts a random public address in front of it through a tunnel, so anyone
anywhere can open it while the app is running. And with a Cloudflare account
connected, a page deploys to **Cloudflare Pages** instead - a real `pages.dev`
address that stays up when the phone is off, and takes your own domain.

**Creator** — a tab where code is built out of blocks instead of typed, added
by a plugin that ships in the app. Nine hundred and four blocks across ten
languages — Python, Go, Rust, C, JavaScript, Shell, HTML, CSS, Markdown and
JSON — six of which the phone can then run. Pick a block, fill in its holes,
stack it, nest it inside a loop; every language has an example to start
from. Build shows the source before anything is saved;
Save puts a real file in your workspace, which the editor opens, the Servers
tab runs and the Pages tab serves like anything you wrote by hand. It gets the
shape right - the colons, the braces, the indentation, the closing tags - which
is the part that is miserable on a phone keyboard.

**Music** — your own audio, kept in the app and playing while you work. Add
anything on the phone, video files included: those are taken for their sound
and their picture is never decoded. Playlists you name, rename, reorder and
delete; loop off, all or one; shuffle. It keeps playing when you switch tabs,
when you leave the app and when the phone is locked, and the notification, the
lock screen and the quick-settings media chip all have the controls - Android
draws those, because the player is a real media session rather than a sound
this app is making. Everything is a copy in private storage, so it works with
no signal and deleting a track never touches what you imported it from.

**Servers** — a launch form that runs whatever you point it at: a Python
script, a C, Go or Rust program, a JavaScript file, an HTML page (whose folder
gets served, opening on that page), or a whole project folder. A folder is
looked into rather than handed straight to a file server: an `app.py` that
imports Flask is the front door and gets run, an `index.html` is the page to
open, a single runnable file is the one you meant. A directory listing is what
is left when there is genuinely nothing to run - and then the page says why.
It says which of those it will be *before* you press Run, and refuses what has
no engine here with the reason. Pick the port (with a "free one" button), name it, choose whether it is
reachable on Wi-Fi or loopback only. Every server gets its own console with its
own scrollback and stdin box, a **View** button that opens it in the preview,
and a **Kill** switch that works even on a server wedged inside its own
`accept()`. Servers stay alive in the background while you use other apps.

**It offers to fix what it can** — a file one typo away from the name your
script asked for, an import of a package that is not installed, a port already
in use, a folder served with no index page. The console says what it thinks is
wrong and what it would change, and waits for `yes`. Then it says what it is
doing while it does it, on its own thread, so Stop and Kill keep working
throughout. It never acts on its own.

**Plugins** — three kinds of the same idea. Thirteen **built-in switches**,
each over behaviour already compiled into the app. Five **bundled plugins**
that ship inside the APK and start switched off: **Server Pro**, **Cloud**,
**Scheduler** and **Packages Pro**. And **plugins you write yourself** — Python that PyCmd imports,
which can publish a row in More with its own name and picture, put a card of
its own inside one of the app's existing screens, register console commands,
claim a file type the Servers tab can then run, and reach Supabase or Firebase
through `pycmd_cloud`. Install from a file, a folder or a zip. They are not
sandboxed and the app says so before installing one.
[PLUGINS.md](PLUGINS.md) is the authoring guide; [BUILTINS.md](BUILTINS.md)
describes everything that ships.

**Supabase and Firebase** — 116 operations across the two, over their REST
APIs, with nothing to install: PostgREST queries and filters, GoTrue sign-up
and sign-in, Supabase Storage and edge functions, Firestore documents and
structured queries, Identity Toolkit, the Realtime Database and Firebase
Storage. Connect a project once and a script, a server, a console command and
the panel all reach it as the same user. Keys live in the app's own storage,
never in the workspace.

**Tools** — JSON formatting, Base64 and hashes, a regex lab that uses Python's
own `re`, an HTTP client, and workspace-wide search.

**Debug console** — one tap from anywhere in the top bar. Interpreter
lifecycle, server events, package installs, file errors, plugin failures,
JavaScript errors from a preview or a panel, and uncaught Java exceptions, with
level filters, text search, expandable stack traces, copy-all and
save-to-workspace.

**Guides and System** — the manuals on the phone, including a guide to forking
this app and a button that downloads its source as a zip; and a screen that
says what the app is using: versions, architecture, what each folder costs,
what is running, housekeeping that touches nothing you wrote, and where to
write when something is wrong (`andrejbaltes4@proton.me`).

**Forks are welcome** — the update address is editable so a fork can publish
its own builds, `tools/make_latest.py` writes the manifest, and
[FORKING.md](FORKING.md) is the walkthrough. Keep PyCmd's name and credit where
they are, and do not present the original as a copy of your fork; the rest is
yours to change.

**It keeps working with the app closed** — running pages and servers are held
up by a foreground service, so they answer while you are in another app, and
update checks (and, if you say so, the download) run on Android's own schedule
through WorkManager. What Android will not allow is stated rather than implied:
work runs roughly daily on wifi rather than at a time you pick, a force-stopped
app runs nothing until it is opened again, and nothing ever installs itself.

**Old versions, kept** — every update it downloads is filed on external
storage rather than thrown away, up to a ceiling you set (250 MB to 2 GB, or
off). Each one can be reinstalled, saved out to the phone or deleted. Going
back to an *older* build is the one thing Android will not do in place, and the
app says so plainly instead of pretending: it walks through the sequence that
does work, and writes the workspace backup that makes it safe.

**Updates that keep your files** — **More → System → Check for updates** reads
a small manifest, and if there is a newer build it downloads it, checks it
against the published fingerprint, checks it is signed with the same key as the
build you are running, and hands it to Android to install *over* this one. The
workspace, the packages you installed and every setting stay where they are.
Deleting PyCmd first is what loses them - and that was the only way to move
between versions before this.

PyCmd also takes one quiet look for itself, at most once a day while it is
running: it reads that one small manifest and, if something newer is out, puts
a dot on More and a line on the System card. Nothing is downloaded and nothing
is installed without you pressing the button, and a check that fails - no
signal, no answer - says nothing at all.

---

## Just want to try it

A ready-to-install APK is in [`dist/`](dist/) - download
[`PyCmd-2.5.9.apk`](dist/PyCmd-2.5.9.apk), open it on the phone, and allow the
install when Android asks. It is a release build: minified by R8, not
debuggable, and about 18 MB rather than the 35 MB the debug builds were. It is
signed with the key in [`keystore/`](keystore/) - the standard Android debug
certificate, committed so that every build of this repo can replace the last
one on a phone instead of demanding an uninstall. No store account is involved.
See [dist/README.md](dist/README.md) for the details.

**Already have PyCmd on the phone?** Install this APK straight over it - do not
uninstall first, that is what deletes the workspace. From 2.4 onward the app
does it for you: **More → System → Check for updates**.

Once it's installed, **[TUTORIAL.md](TUTORIAL.md)** walks through every tab
with ready-to-paste snippets — console one-liners, a script that uses the
Stop button, one that reads and writes a file, one that hits the network,
one with colour output, and how to serve a folder over Wi-Fi. Ten example
scripts covering the same ground also ship inside the app under
`Files → examples/`.

---

## Building

You need the Android SDK (platform 35), JDK 17 or newer, and a CPython **3.13**
on `PATH` as `python3.13` — Chaquopy uses it to resolve the pip requirements at
build time.

```bash
git clone https://github.com/Expstudiooficial/space_dodge-1.0.git
cd space_dodge-1.0
echo "sdk.dir=/path/to/android-sdk" > local.properties

./gradlew :app:assembleDebug
```

The APK lands in `app/build/outputs/apk/debug/app-debug.apk`.

If your Python 3.13 lives somewhere unusual:

```bash
./gradlew :app:assembleDebug -Ppycmd.buildPython=/usr/local/bin/python3.13
```

A release build (`./gradlew :app:assembleRelease`) produces an unsigned APK; add
a signing config before shipping it anywhere.

### Requirements on the device

Android 7.0 (API 24) or newer, on **arm64-v8a or x86_64**. Chaquopy's Python 3.13
runtime does not ship 32-bit binaries, which matters only for phones from before
about 2016.

The APK is large because a complete CPython interpreter and standard library are
inside it. The default build produces one APK per ABI plus a universal one;
`-Ppycmd.abi=arm64-v8a` drops the x86_64 runtime that no phone can use. What
`dist/` ships is `./gradlew :app:assembleRelease -Ppycmd.abi=arm64-v8a`: about
18 MB, of which 11 MB is the Python standard library and the bundled packages,
3.7 MB the native CPython, and 3 MB the app's own code once R8 has removed the
AndroidX and Compose it never calls. The debug build of the same source is
35 MB. The native libraries are packed compressed
(`packaging { jniLibs { useLegacyPackaging = true } }`) because this APK is
downloaded raw rather than through a store: it halves the download, at the cost
of about 10 MB more room on the device once Android unpacks them.

---

## Testing

```bash
tools/run-tests.sh
```

That runs four things: the embedded Python modules against a stand-in for the
Kotlin bridge (execution, error reporting, stdin, interrupt-and-recover,
completions, a real install/import/uninstall round trip against PyPI and a real
HTTP server, byte-range requests for the media player, the pages registry, the
music library, and every one of Creator's blocks compiled and handed to
Python's own parser), the published update manifest against the APK actually
sitting in `dist/`, the WebView JavaScript under Node against a stub document -
the console, the editor, and the Creator panel driven the way a finger drives
it - and both a debug and a release build with Android Lint.

Playback is the part no suite here reaches: the media session, its notification
and the lock-screen controls are Android's, and they need a phone. What is
checkable off a device - what is in the library, what order it plays in, what
survives a restart - is `tools/test_music.py`.

The suites can also be run on their own:

```bash
python3.13 tools/test_runtime.py
node tools/test_js.js
```

### What has been checked on a device

The shipped build was installed on an Android 11 x86_64 emulator and driven
through the UI. Confirmed there: the app launches without crashing, CPython
3.13.9 starts and reports itself in the title bar, the console and editor
WebViews render, the editor highlights Python and reports the caret position
back through the JS bridge, and pressing Run executes the buffer and streams
its output into the console.

The Servers tab was then driven end to end on the same emulator: choosing a
folder through the Files picker, launching it, confirming at the OS level that
the port was in `LISTEN`, fetching a real directory listing over HTTP through
an adb forward (200, with both requests appearing in that server's console),
then pressing Kill and confirming the port was released.

That is still not exhaustive. The emulator ran under software translation with
no hardware acceleration, so nothing about performance there means anything.
Installing a package from PyPI, reaching a server from another device over
real Wi-Fi, and the background-server notification have been tested only
against host CPython, not on a device.

---

## How it fits together

```
Compose UI  ──┬── ConsoleScreen ──┐
              ├── EditorScreen  ──┤   WebViews (assets/web/*.js)
              ├── FilesScreen     │   console + ANSI renderer, code editor
              ├── PackagesScreen  │
              ├── ServersScreen   │   launch form + one console per server
              └── DebugScreen ────┘   DebugLog (util/)
                     │
              MainViewModel
                     │
              PythonEngine (Kotlin)
                     │
       python-main ──┴── python-control      one interpreter thread, plus a
       runs code         stops and kills     second so stop/kill always land
                     │
       ┌─────────────┼──────────────┐
  pycmd_runtime  pycmd_packages  pycmd_servers      (src/main/python/*.py)
   execution      wheel installs   background listeners
   + channels                      + kill switch
                     │
              CPython 3.13 (Chaquopy)
```

A few decisions worth knowing about if you are changing this code:

**Python lives on one thread.** CPython keeps per-thread state, so every call
into the interpreter is funnelled onto a single executor. A second run cannot
start until the first returns, which is exactly what a console wants anyway.

**Stop uses `PyThreadState_SetAsyncExc`.** CPython cannot kill a thread
outright. Raising `KeyboardInterrupt` into the running thread through the C API
costs nothing while code runs; the alternative — a trace hook checking a flag on
every line — makes all Python about 1.8× slower. The trace hook is still there
as a fallback, and the engine probes the fast path at startup rather than
assuming it works. The mechanism actually in use is shown in the About dialog.

**Stop requests come from their own thread.** They cannot queue behind the code
they are trying to stop, and they must not block the UI thread waiting for the
GIL.

**The editor is a textarea over a highlighted `<pre>`.** The transparent
textarea keeps the platform caret, selection handles, IME and clipboard — all
things a hand-rolled editor gets subtly wrong — while the layer underneath
supplies the colour. The two only line up because both take their font metrics
and padding from the same CSS variables.

**The icons are hand-defined, not a library.** `material-icons-extended` ships
five complete icon styles and accounted for 13.7 MB of the 24 MB dex - over half
- to supply the twenty-nine glyphs this app draws. A debug build does no
shrinking, so all of that rode along into the download. `ui/PyIcons.kt` defines
those twenty-nine as Material path data instead.

**Output is channelled.** `sys.stdout` is one global object, so a server
running on its own thread would otherwise print into the main console. Every
write is tagged with the channel registered for the writing thread, and each
channel has its own stdin queue — which is what lets a server prompt for input
without stealing what you typed into the console.

**Stop and kill run off the interpreter thread.** Queued behind the code they
are trying to stop, they would never arrive, and that is precisely when they
are needed. Stop asks the server to close and waits; Kill closes the socket
(freeing the port even if the thread is wedged in a blocking call), raises
`SystemExit` inside the thread, and stops tracking it either way.

**Both WebViews outlive their tab.** They are created once and re-attached on
each tab switch, so console history and editor scroll position survive. The
editor tracks which document it currently holds so returning to the tab does not
throw the caret back to the top. They are also given explicit match-parent
layout params: without them the view is added as wrap-content, the page's
`height: 100%` resolves against a strip a couple of hundred pixels tall, and the
console scrolls nearly all of its output off the top of a viewport barely one
line high.

---

## Installing packages on the device

The Packages tab downloads universal wheels (`py3-none-any`) from PyPI and
unpacks them into a writable `site-packages` on `sys.path`. Wheel entries with
absolute or parent-escaping paths are refused rather than extracted.

`package` and `package==1.2.3` both work, the same spelling pip uses.

**What cannot be installed this way:** anything with compiled C extensions —
`pygame`, `scipy`, `pandas`, `lxml` and similar. Those need wheels built against
the Android NDK for the exact ABI and Python version; there is nothing on PyPI
for a phone to fetch. `numpy` and `pillow` are available as Android builds and
can be added to the `pip` block in `app/build.gradle.kts` at build time, which
bakes them into the APK.

---

## Layout

```
app/src/main/
  java/com/expstudio/pycmd/
    MainActivity.kt          entry point, notification permission
    PyCmdApp.kt              notification channel
    python/
      PythonEngine.kt        the interpreter bridge and its threading
      ServerService.kt       foreground service that keeps servers alive
    music/
      MusicService.kt        the media session, and why sound outlives the app
      MusicHub.kt            the controller the screens press play on
      MusicImport.kt         copying a picked file into the library
    ui/                      Compose screens, theme, WebView hosting, icons
    util/Workspace.kt        file operations, all confined to the workspace
    util/DebugLog.kt         the process-wide record behind the debug console
    util/Updater.kt          checking, downloading and verifying a newer build
  python/
    pycmd_runtime.py         execution, streams, interrupt, completions
    pycmd_packages.py        on-device wheel installs
    pycmd_servers.py         background listeners
    pycmd_music.py           the music library: tracks, playlists, order
  assets/
    web/                     console and editor pages, ANSI and highlighting
    plugins/creator/         the block catalogue and what it compiles to
    examples/                scripts seeded into the workspace on first launch
tools/                       host-side test suites, and make_latest.py
keystore/pycmd.keystore      the one signing key, so updates can install
dist/                        the built APK, its hash, and latest.json
```

---

## Licence

MIT. See [LICENSE](LICENSE).
