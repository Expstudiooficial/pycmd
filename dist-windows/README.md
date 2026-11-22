# PyCmd for Windows

`PyCmd.exe` — one file, nothing to install.

| | |
|---|---|
| Version | 4.0.5 |
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
- **Or push a tag** such as `windows-4.0.5` (the older `windows-v4.0.0`
  spelling is also supported) and let the workflow do it — it builds on a
  Windows runner, proves the exe starts, writes this manifest with the real
  hash, and attaches the exe to a release.

## Where the exe lives

Not in this folder, and not in the repository. It is attached to the GitHub
release for the tag that built it, which is what `latest.json` points at.

`url` in the manifest is pinned to one version, because the `sha256` beside it
describes that build and no other; a moving address would fail its own
checksum the day after the next release. `latestUrl` always redirects to the
newest release, and is the one to hand somebody or put on a page.

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
