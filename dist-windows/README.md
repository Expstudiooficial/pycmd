# PyCmd for Windows

`PyCmd.exe` — one file, nothing to install.

| | |
|---|---|
| Version | 2.0.0 |
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
- **Or push a tag** `windows-v2.0.0` and let the workflow do it — it builds on
  a Windows runner, proves the exe starts, writes this manifest with the real
  hash, and attaches the exe to a release.

## Where the exe lives

Not in this folder, and not in the repository. It is attached to the GitHub
release for the tag that built it, which is what `latest.json` points at.

`url` in the manifest is pinned to one version, because the `sha256` beside it
describes that build and no other; a moving address would fail its own
checksum the day after the next release. `latestUrl` always redirects to the
newest release, and is the one to hand somebody or put on a page.

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
