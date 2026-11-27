# PyCmd for Windows

`PyCmd.exe` — one file, nothing to install.

| | |
|---|---|
| Version | 5.0 |
| Works on | Windows 10 and newer, 64-bit |
| Runtime | Edge WebView2, which Windows 10 and 11 already have |
| Installer | none — it is one exe |
| Admin rights | none |
| Keeps things in | `%LOCALAPPDATA%\PyCmd` |
| SHA-256 | see [SHA256SUMS.txt](SHA256SUMS.txt) |

## Is there an exe here yet?

Check `latest.json`. If its `sha256` is empty, the manifest is **seeded** —
the version is decided and the address is fixed, but nobody has built it yet.
The app treats that correctly: it will not offer an update it cannot verify,
and it refuses any download without a checksum.

To make one:

- **On your own machine:**
  `powershell -ExecutionPolicy Bypass -File windows\build\build.ps1`
- **Or push a tag** such as `windows-v4.5.0` (or `windows-4.5.0`) and let the workflow do it — it builds on a
  Windows runner, proves the exe starts, writes this manifest with the real
  hash, and attaches the exe to a release.

## Where the exe lives

Not in this folder, and not in the repository. It is attached to the GitHub
release for the tag that built it, which is what `latest.json` points at.

`url` in the manifest is pinned to one version, because the `sha256` beside it
describes that build and no other; a moving address would fail its own
checksum the day after the next release. `latestUrl` always redirects to the
newest release, and is the one to hand somebody or put on a page.

## What is new in 5.9

### A real installer

**PyCmd-Setup.exe** installs PyCmd properly, with no administrator rights:
- **Where:** `%LOCALAPPDATA%\Programs\PyCmd`.
- **Shortcuts:** a **Start menu** shortcut, and a desktop one if you tick it.
- **Uninstall:** an uninstaller in **Settings > Apps**.
- **Updates:** a newer installer updates the installed PyCmd in place.
- **Your things:** workspace, settings and boards stay in `%LOCALAPPDATA%\PyCmd`, and uninstalling never touches them.

The single `PyCmd.exe` is still on every release for anyone who wants it portable.

### PyCmd updates itself

PyCmd checks for a new version when it starts and every six hours after that.
When it finds one, a pop-up offers **Install now**: PyCmd closes, updates, and
opens again a few seconds later. **Settings > Updates** has three choices:

- tell me (the default)
- install new versions by themselves
- never check

Every installer is checked against the SHA-256 in the release manifest before it runs.

### Copies is gone

The installer keeps exactly one PyCmd, so the Copies tab had nothing left to do.

## What is new in 5.8

### Notes, built in, and you can write in it

Notes is part of PyCmd now, not a plugin. In 5.7 you could not type in a card:
the board held the mouse, and the double-click never reached the text. Now a
double-click on any card opens it for writing, as often as you like. Your
boards and your old notes came with it, and the Board plugin is gone.

### A much better board

- **Right-click** a card, an arrow or the board for what you can do with it.
- **Select many:** Shift+drag a box, use **Select**, or Shift+click. Move, colour, duplicate or delete them together.
- **Sections:** frames that group cards, and moving a section moves what is in it.
- **More cards and arrows:** code cards, plus `**bold**`, `*italic*`, `` `code` `` and `- lists` in notes. Arrows can be one-way, two-way or plain lines, solid or dashed, in any colour.
- **Arranging:** lock, bring to front and send to back, snap to grid, and arrow keys to nudge.
- **Find** (Ctrl+F) jumps to a card.
- **Templates:** Kanban, mind map, my week, project, and pros and cons.
- **Images:** drag image files onto the board, or paste them.
- **Export** to a **picture (.png)** or Markdown.
- **Keys:** Ctrl+A, Ctrl+C / Ctrl+V and Ctrl+D work on cards.

### AI agents can use it

With MCP on, AI apps get `pycmd_board_*` tools to read your boards and add notes.

## What is new in 5.7

### Notes is a board now

The **Notes** tab is a board:
- **Cards:** notes, headings, to-do lists, images and links, anywhere you like.
- **Arranging:** drag cards around, resize them and colour them.
- **Arrows:** drag a card's green dot onto another card to connect them, or use **Connect**. Double-click an arrow to label it.
- **Getting around:** pan by dragging the background; zoom with the wheel or **Fit**.
- **Pasting:** paste an image or a link straight onto the board.
- **Boards:** keep as many as you like (New, rename, Delete), and **Export .md** writes one to your workspace as Markdown.

Your old notes are on the board as a card. It saves itself, and Ctrl+Z undoes anything. It is the same Board plugin the phone has.

### Ten new console tools

The same ten on the phone and the PC:

| Command | Does |
|---|---|
| `calc 2^10 / 3` | a calculator, with `sqrt`, `pi` and the rest of `math` |
| `todo add …` / `todo done 2` / `todo` | a to-do list kept in the workspace |
| `passgen 24` | a strong random password (`x5` for five, `--no-symbols`) |
| `hash file [md5]` | the SHA-256 (or MD5, SHA-1, SHA-512) of a file or text |
| `base64 encode/decode` | text or a file |
| `wc file` | lines, words and characters |
| `grep pattern [folder] [-i]` | find text in files |
| `diff a b` | what changed between two files |
| `cal` / `cal 3 2027` / `cal 2027` | a calendar |
| `loc [folder]` | lines of code, by language |

And `note <text>` drops a note on your board.

## What is new in 5.6

### HTML runs

Press **Run** on an `.html` file and PyCmd serves its folder on a local
address and opens it in your browser. That works from the editor, Files, the
Run tab, or `run index.html` in the console. Relative links, scripts and
`fetch()` work because it is served rather than opened as a file.

### Installs that work

Seven toolchains offered install lines that do not exist: `scoop install tcl`,
`clojure`, `ocaml` and `guile` are in no Scoop bucket, and there is no
Chocolatey `guile`. Now:

- **Tcl** installs with `choco install magicsplat-tcl-tk`.
- **Clojure** installs with `choco install clojure` (it also needs a JDK).
- **Haskell** installs with `choco install ghc`.
- **OCaml** installs with `choco install ocpwin`.
- **GnuCOBOL** installs with `choco install gnucobol`.
- **Scheme** files run on **Racket**, since Guile has no Windows build.
- **MSVC** installs the Build Tools *with* the C++ workload. Before, it installed
  them with no compiler in them.

### Found where installers put them

Tcl, GHC, OCaml, GnuCOBOL and Racket are found in the folders their installers
use, even when PATH was not updated. MSVC is found through Visual Studio's own
locator and its build environment is loaded automatically, so no Developer
Command Prompt is needed. GnuCOBOL gets its config and copybook folders set up
too.

## What is new in 5.5

### Creator 3.0

Creator was rebuilt. Run **Python, C, Go, Rust and JavaScript** right in its
tab, with an **Input** box for `input()`; **HTML, CSS and Markdown** get a live
preview. **Import code** turns code you paste, or a file in your workspace, back
into blocks, and every line is checked to write exactly what it read. Drag and
drop, undo and redo, search with `/`, and projects that save themselves. On a
narrow window the panes become tabs.

### Python files run on every PC

With no Python installed, or only the Microsoft Store placeholder (the
`python.exe` that only says "Python was not found"), Run now uses **PyCmd's own
Python**, and the exe carries the whole standard library. Programs read
`input()` from the console. Printing emoji no longer crashes on Windows code
pages, and output appears as the program prints it.

### Guides and plugin tabs scroll at any zoom

Above 100% zoom, the guide window and plugin tabs ran off the bottom of the
window, so the end of a guide could not be reached. They fit the window at
every zoom now, and an open guide scrolls with the wheel, arrow keys or Page
Down straight away.

### Plugins stay up to date

A bundled plugin is reinstalled whenever its files differ from the shipped
ones, not only when the version number changes. That is why Creator kept its
old look. An update keeps what the plugin saved. Installed plugins are listed
first on the Plugins tab.

## What is new in 5.0

### MCP: AI agents drive PyCmd

A new **MCP** tab (under Tools) switches on a Model Context Protocol server,
so an AI app can use PyCmd: **Claude Code, Claude Desktop, Antigravity,
Cursor, VS Code, Windsurf, Gemini CLI, Codex** and anything else that speaks
MCP over HTTP. Each has its set-up ready to copy.

- **170+ tools**: every call the app makes (files, console, toolchains,
  servers, packages, Learn, plugins, Android Lab, git, cloud files...), with
  readable descriptions and their arguments, plus **ui_*** tools that drive
  the window like a person: open a tab, read what is on screen with every
  button and field numbered, click, type, scroll, press keys, change the
  theme - and **ui_screenshot**, a PNG of the window.
- **Safe by default**: off until you switch it on; only this PC can connect
  (127.0.0.1); every request needs the token; requests from web pages are
  refused; **read-only** mode lets agents look without changing anything.
  The tab shows the last calls.

### 800 KB of cloud storage

Every PyCmd account gets 800 KB of files on pycmd.pages.dev - small code,
notes, configs - on every device you sign in on. **Cloud files** on the
account card uploads, saves to `workspace\cloud`, and deletes. Agents can use
it too.

### Fixed

- **Guides and dialogs scroll.** A long guide stopped at the first screen:
  the dialog's body could not shrink to scroll.
- **Screens no longer flicker or draw twice** when a slow screen finished
  loading after you had already moved on.
- **Plugins load.** Installed plugins' Python was never started on Windows, so
  Creator opened with nothing behind its buttons. Each installed plugin now
  has an on/off switch, and only the ones that are on get a tab.
- **Plugins follow the theme** from their first frame, instead of a mix of
  the old default colours and the new theme.
- **Erlang** showed "escript: Missing filename" as its version; it shows the
  real one now.
- **Learn progress takes a tenth of the space** in the database: the website
  compresses it.
- **Clang++** builds against a Visual Studio newer than itself.


## What is new in 4.5

### About 1,800 lessons in every course

PyCmd Learn has **90,129 lessons in 50 languages** - every course now has
about 1,800. The big courses used to have over a thousand and the small ones
about a hundred; the small ones grew the most.

The new lessons are **practice rounds**, after each course's hand-written
units: every kind of exercise again (precedence, remainders, loops, lists,
functions, strings...) with new code each round, written in each language's
own idiom. For JSON, YAML, TOML, XML, CSV, INI, regular expressions,
.gitignore, Makefiles, Dockerfiles, HTML, CSS and Markdown the rounds ask a
question about a document instead: which value a key holds, how many rows a
CSV has, whether a file would load at all, how wide a box is on screen.

None of it is guessed. Before release the practice programs were run on the
real compilers and interpreters (GCC, rustc, Go, javac, kotlinc, GHC, OCaml,
dotnet, GnuCOBOL, SWI-Prolog and the rest) and had to print exactly what the
lesson says; the documents were loaded with real parsers, the Makefiles run
with make, the .gitignore files asked of git and the CSS laid out in
Chromium. The one exception is Swift: there was no Swift compiler to run its
practice on, so those follow the same tested patterns but were checked by
reading them.

### A PyCmd account

- **Sign up** with a username and password on the Learn screen (or in
  Settings). Usernames are unique - if one is taken, PyCmd says so while you
  type and you pick another.
- **Your progress syncs** between this PC and PyCmd on your phone: lessons
  finished on either stay finished, the streak comes from whichever saw the
  later day, and resetting a course on one resets it on the other.
- **Your password never leaves this PC.** PyCmd stretches it (PBKDF2-SHA256,
  600,000 rounds) and sends the result; pycmd.pages.dev stretches that again
  before keeping it. The app holds no database key: it talks to the website,
  and only the website talks to the database.
- **Account** lets you sign out, change the password (your other devices sign
  in again) or delete the account and everything saved with it.

### Export and import

**Export** saves your Learn progress as a `.json` file; **Import** loads one -
added to your progress, or replacing it. The same file works on Android.

### A cleaner Learn

- The course list starts with the courses you have started, then the
  languages most people come for.
- Units fold, and the one with your next lesson starts open. A course's
  map used to draw all of its lessons at once.
- Practice rounds have their own section with a **Practise** button.
- A question about a document shows the question with its answer, and the
  wrong answers on offer are the same kind of thing as the right one - a
  number for "how many", a city for `city`.
- Learn opens faster: lessons are counted without being built.

### One look everywhere

The last colours left from the first palette (a dark blue on hover, in
output boxes, toasts and dialogs) are theme colours now, so every theme
reaches every panel. Dialogs blur what is behind them, and sign-in forms
have show/hide on passwords, inline errors and a live username check.

## What is new in 4.0.5

- Fixed sidebar navigation resetting to the top whenever the tab rail is
  redrawn.
- Fixed Android Lab SDK package installation on Windows by passing package
  IDs with semicolons through sdkmanager's package-file option.
- Windows release automation accepts the `windows-4.0.5` tag spelling and
  builds, verifies, and attaches `PyCmd.exe` to that GitHub release.

## What is new in 4.0

The biggest update the Windows build has had. Most of it is things that did
not work and now do, and a lot of it is new.

### Fixed

- **Toolchain installs.** Nearly every "it throws errors" came from here, and
  from four separate bugs. scoop was launched by its bare name, which Windows
  cannot resolve for a `.cmd` shim, so `scoop install` failed on every machine
  that had scoop. scoop's buckets were never added after the first run, and
  adding one needs git, which a fresh scoop does not have - so Kotlin, the JDK
  and Prolog "did not exist". scoop's installer refuses to run elevated unless
  told it may. And every installer's output went to a channel no screen
  showed, so an install looked like it did nothing at all. All four fixed.
- **Rust** installed but could not build anything without Visual Studio's
  `link.exe`. It now installs the GNU toolchain, which links by itself.
- **TypeScript**'s scoop line installed Node and no TypeScript. It installs
  TypeScript now.
- **Android Lab** - see below. It failed on almost every machine.
- **Erlang** lesson and Run files lost their first line to escript.

### New: toolchains install themselves

Seventeen toolchains - Node.js, Go, Java, Zig, Deno, Bun, .NET, Rust, Kotlin,
PowerShell 7, GCC, Git with bash, Dart, Nim, Perl, PHP, TypeScript - install
with one click **straight from their vendor**: the newest version from the
vendor's own index, checked against the hash the vendor publishes, unpacked
into PyCmd's folder and put on PyCmd's PATH. No administrator, no package
manager, nothing in the registry; **Remove** deletes one folder. The package
managers are still there for everything else.

### New: Android Lab that works

It sets up Java (installing Temurin 21 if there is none), downloads Google's
command-line tools directly and checks them, accepts the licences, gives every
SDK tool `--sdk_root` and the environment it needs, checks hardware
acceleration and offers the fix (Windows Hypervisor Platform, Google's driver,
or what to change in the BIOS), watches the emulator and says why it stopped
in seconds instead of timing out after seven minutes, and finally downloads
PyCmd Android from its release manifest, checks its SHA-256, installs it and
opens it - which it never used to do. Choose Android 13-16, memory, storage,
cores and graphics. Screenshots, logcat, Back/Home/Apps, typing, install any
APK, phones on USB listed separately, wipe, delete, diagnostics.

### New: PyCmd Learn

50 languages, 14,700 lessons. The phone's 28 courses plus **22 only a PC can
run**: C#, F#, Haskell, OCaml, Scheme, Racket, Clojure, Elixir, Erlang, Scala,
Groovy, R, AWK, Prolog, Fortran, Pascal, COBOL, D, Nim, Perl, Tcl and
PowerShell. Where the language is installed, **your answer is marked by
running it** - so a correct answer written differently is still correct. Run
any lesson's code, change it and run it again. Review your mistakes, search
every course, a daily goal and a streak. Every snippet was checked by running
it on the real compiler.

### New screens and features

- **Command palette** (Ctrl+K): every screen, action, recent file and course.
- **Keyboard shortcuts**: Ctrl+1-9 for screens, Ctrl+Shift+F/L/N/T, zoom, F1.
- **Themes**: Classic Green, Midnight Blue, Halloween, Amber Terminal, Slate,
  Paper (light), or your own colours - and they reach inside the console and
  editor. Zoom and a compact layout.
- **Search** in files, with a regex option, file filters and replace.
- **Git**: status, stage, discard, commit, branches, pull, push, history, diffs.
- **Tasks**: npm scripts, Makefile targets, cargo, go, dotnet, Gradle - one click.
- **Tools**: JSON, Base64, URLs, hashes, UUIDs, timestamps, regex tester, diff,
  case and counts, colours.
- **Ports**: what is listening, whether a port is free, and stopping what holds it.
- **Snippets** and **Notes**.
- **New project** from ten templates (Python, web server, Node, website, Go,
  Rust, C, C#, Java, PowerShell), optionally as a git repository.
- **Run with arguments and input**, remembered per file.
- **Recent files**, **console history that survives a restart**, zip and unzip
  in Files, **environment variables** for everything you run.
- **System** shows memory, drives and uptime; **Export diagnostics** writes
  one zip for a bug report, with none of your files in it.
- **Guides** render properly, with two new ones: PyCmd Learn and Android Lab.
- **What's new** appears once after an update.

## What is new in 3.0

**The whole PC, not just a workspace.** Files has two halves now: the
workspace, which is still where new projects land and what the console's `cd`
and `run` mean, and **This PC** — every drive, your Desktop, Documents and
Downloads, and every folder under them. Open a file there and you are editing
the file itself, in place, not a copy that has to be exported back out
afterwards. Copy, cut, paste, rename, delete, make folders, show something in
Explorer, open something with whatever Windows uses for it.

The phone's model is "bring a file in, send a file out", and it has to be:
Android hands an app a private folder and a document picker. Windows hands you
the disk. PyCmd now behaves like a Windows program.

**Clicking a file opens the Editor.** There used to be a second, much worse
editor — a textarea in a sheet — that appeared when you clicked a row. It had
no highlighting, no real undo, and no second file open beside it. It is gone.
One file, one editor, the good one. The Editor's Open dialog browses This PC
too, and saves back where the file came from.

**Run shows you what can be run.** No more typing `hello.go` and guessing at
the path and the extension. PyCmd walks the folder, lists everything it knows
how to run with its language beside it, and you pick one. Point it at the
workspace or at any folder on the PC.

**Run always lands on the Console.** If the program calls `input()`, the
prompt is on the screen you are looking at. So are installs.

**Plugin panels are tabs.** A plugin with a panel gets its own entry in the
sidebar, under Plugins, beside the fourteen screens PyCmd ships with. They
used to be two clicks deep inside the Plugins tab and then opened in a modal
sheet that covered the app and lost your work when it closed.

**Fixed along the way.** Running a file from a subfolder of the workspace ran
the wrong path. Messages a plugin sent to its own panel never arrived, because
the code looking for the panels looked for the wrong kind of frame. The
console refused to run a file by absolute path even when you were looking at
it in the editor.

## What is new in 2.0

**The Editor is an editor.** It was an iframe with nothing around it - the
editor inside was the phone's good one, and every part of it was unreachable
because nothing on Windows ever spoke to it. Now: tabs for several files with
an unsaved marker, Open, Save, Save as, Save and run, undo, redo, indent,
outdent, wrap, go to line, find and replace, a language picker, and a status
line with the caret position and the counts. Ctrl+S, O, N, G, F and Ctrl+Enter.

**The Console has the rest of itself.** Up and down walk your history, Tab
completes, and `input()` is answered in the bar you are already typing in -
with the output still on screen behind it, which is the whole reason a program
asked. Stop appears while something is running. Copy and Save take the output
away.

**Detection remembers this machine.** It used to start from zero on every
launch and every version: fifty-one version probes, several of them starting a
JVM, before the Toolchains screen could draw. What PyCmd finds is now
remembered beside your workspace rather than inside a version folder, so
upgrading keeps it, and a toolchain is re-checked only when its file actually
changes. Six hundred times faster on the second look.

**"scoop is not recognised" is no longer the answer to "install Go".** PyCmd
installs the package manager if there is none - Scoop, which needs no
administrator - and falls back through every manager that carries a package
instead of giving up on the first. Six toolchains had no install route at all
and now have one.

**Phone plugins run, rather than being warned about.** 1.0 imported one and
called it a beta. What actually stopped them was narrow: a `java` module that
does not exist here, Android paths, and three capabilities Windows does
differently. All of that is provided now, so a plugin whose Android parts are
covered is reported as running *in full*. Only something that genuinely needs
a phone - hardware, sensors, an Android view - is still called partial, and it
names the exact part.

**One PyCmd, not a folder full of them.** It finds older copies in the places
downloads actually land, checks each one really is PyCmd by asking its
version, and takes their place - asking for administrator only if a copy is
somewhere that needs it. The old build is filed away rather than deleted, so
you can go back.

**Android Lab.** A real Android 14 device on your PC with 4 GB of RAM and
10 GB of storage, and PyCmd Android installed on it. PyCmd sets up and drives
Google's emulator for you, which is the tedious part; it does not pretend to
*be* one, and says so and says what it will download before anything starts.

**And a word somewhere.**

## What is new in 1.0.1

**An abandoned request is no longer an error.** WebView2 gives up on requests
constantly - a plugin panel's frame is pointed at `about:blank` and rewritten,
a page navigates while an image is still arriving, the window closes with a
poll in flight - and each one broke a write that had already started. Python's
HTTP server prints a full traceback for that by default, so anybody running
the exe from a terminal saw a stream of

    ConnectionAbortedError: [WinError 10053] An established connection was
    aborted by the software in your host machine

for something that was not wrong and that they could not act on. Now nothing
is printed for it, and anything genuinely broken goes to PyCmd's own log
screen rather than to whatever console happened to be behind the window.

**Updates come from the release.** 1.0.0 shipped its exe by committing it into
the branch, which worked and should not have: a fifteen-megabyte binary added
once per version is fifteen megabytes added to every clone of the project for
ever. The binary is no longer committed at all.

**F# runs both ways.** An `.fsx` is a script and goes to F# Interactive; an
`.fs` is a compile unit and goes to the .NET SDK, with the `.fsproj` written
for you. Before, both went to the SDK and the script half failed.

**A tag now has to agree with the source.** Tagging `windows-v1.0.1` while the
code still calls itself 1.0.0 used to build happily and produce a manifest
pointing at the wrong release. It stops the build now, and says which two
numbers disagree.

## What is new in 1.0.0

**The whole of PyCmd 2.5.9, as a Windows program, with the restriction that
shaped it removed.**

Android has not let an app execute code it compiled itself since API 29. That
one rule is why the phone build carries hand-written interpreters for C, Go
and Rust, and why a dozen other languages are honestly labelled "you can edit
and serve this, but not run it". Windows has no such rule, and this build is
what PyCmd looks like without it.

**65 file types, 43 of them runnable** — up from 34 and 6. Thirty-one
languages the phone had no reason to carry: C#, F#, Visual Basic, Haskell,
Julia, R, Dart, Zig, Nim, Crystal, Elixir, Erlang, Scala, Clojure, OCaml,
Racket, Scheme, Fortran, COBOL, Pascal, D, V, Groovy, Objective-C, assembly,
PowerShell, batch, Perl, Tcl, AWK and Prolog.

**51 toolchains it knows how to find and drive.** The Toolchains screen says
which are installed and what version, and for the rest gives the exact
`winget`, `scoop` or `choco` line with a button that runs it. PyCmd bundles no
compilers — a build carrying MSVC and a JDK would be gigabytes — so that
button runs your own package manager with the line you would have typed.

**The interpreters are still there, as the fallback.** With nothing installed,
a `.go` file still runs on day one. Install Go and the same file runs on the
real thing. The console says which one every time, because it matters: the
built-in Go interpreter does not enforce types and the built-in Rust one has
no borrow checker.

**Everything else came across.** The console with its shell and its Stop,
Clear and Reset; the editor; the workspace, browsed properly — walk into
folders, make a file in any of the 65 languages from its template, rename,
delete, open, edit and save, and bring a file in from anywhere on the disk.
Servers that say what they will do before they do it and stay on loopback
unless you tick the box. Pages pointed at folders you already have, where
removing the page leaves the folder alone. Packages that ask PyPI what
something is before downloading it. The five bundled plugins — Cloud, Creator,
Packages Pro, Scheduler, Server Pro — with their panels opening in the app,
their settings editable and their exports reachable. And all thirteen built-in
plugins, with the same ids the phone uses.

**Bring a plugin over from the phone.** A beta, and specifically so: PyCmd
reads the plugin before installing it and names exactly what this machine
cannot honour — Android permissions, `/storage` paths, `java` imports. A
plugin with none of those is reported as "should work", and it does.

**Where things live.** `%LOCALAPPDATA%\PyCmd` — ordinary folders you can open,
back up or put in git. Nothing is written to Program Files and nothing needs
administrator rights. Set `PYCMD_HOME` and the whole thing is portable.

**Its own update channel.** `dist-windows/latest.json`, separate from the
APK's. The Windows build will never offer you an APK.

### How much of this is actually new code

About 3,000 lines against 21,000 shared. The engine, the interpreters,
`console.js`, `editor.js`, every bundled plugin and the whole plugin API are
the same files the phone loads. What is Windows-only is where files live,
which compilers exist, how a run is planned, and the window itself.

### What was left out

**The Music tab.** The library and playlists would have ported fine; the half
that mattered was Android's media session drawing controls on a lock screen
and in quick settings, and Windows has no equivalent worth imitating.

### Verification

115 checks in `tools/test_windows.py`, which run anywhere. Sixteen languages —
Python, JavaScript, TypeScript, C, C++, Go, Rust, Java, Ruby, PHP, Perl, Bash
and more — compiled and ran through the real planner during development, and
`tools/test_toolchains_live.py` repeats that on any machine for whatever it
has. The interface was driven end to end in a browser against the real
backend.

What could not be checked without Windows: that the exe opens, and that
WebView2 renders it. The CI workflow does both on a Windows runner.
