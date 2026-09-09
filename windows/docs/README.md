# PyCmd for Windows

A programmer's console that runs code on the machine in front of you. One exe,
nothing to install, nothing written outside your own user folder.

This is the same PyCmd that runs on Android — same engine, same plugins, same
console — with the one restriction that shaped the phone build lifted. Android
has not let an app execute code it compiled itself since API 29, which is why
the phone carries hand-written interpreters for C, Go and Rust and honestly
labels a dozen other languages "editable, not runnable". Windows has no such
rule. If a compiler is on your PATH, PyCmd calls it.

**65 file types. 43 of them run. 51 toolchains it knows how to find and use.**

---

## Getting it

Download `PyCmd.exe` and double-click it. That is the whole procedure.

- **Windows 10 or newer, 64-bit.**
- **No installer, no admin rights, no registry.** Nothing is written to
  Program Files.
- **Nothing to install first.** The window is Edge WebView2, which Windows 10
  and 11 already have.

Windows SmartScreen will warn you the first time, because the exe is not
signed by a certificate it recognises — signing needs a certificate that a
public repository cannot hold. Check the SHA-256 against
[`SHA256SUMS.txt`](../../dist-windows/SHA256SUMS.txt) if you want to be sure
you have what was published:

```powershell
Get-FileHash .\PyCmd.exe -Algorithm SHA256
```

### Where it keeps things

`%LOCALAPPDATA%\PyCmd` — your workspace, installed packages, plugins,
downloads, pages and music. All of it is ordinary Windows folders you can open
in Explorer, back up, or put in git.

Set `PYCMD_HOME` to move the lot somewhere else. That is how you make it
portable: put `PyCmd.exe` on a memory stick with a `PyCmd-data` folder beside
it, set `PYCMD_HOME` to that folder, and it carries your workspace with it.

---

## The screens

**Console** — a real Python REPL with a shell in front of it. `pip install
flask` works as typed, and so do `ls`, `cd`, `cat`, `run`, `serve`, `tree` and
a dozen more; everything else is Python. Output streams as it is produced,
`input()` prompts and waits, and Stop interrupts a runaway loop.

**Editor** — syntax highlighting for every language PyCmd knows, line numbers,
auto-indent that follows *that* language's rules, bracket matching, a snippet
bar that changes with the file type, go-to-line and autosave.

**Files** — your workspace, browsed. Folders you can walk into with a
breadcrumb back out, a new-file menu covering all 65 languages with their
starter templates, new folders, rename, delete, and a **Bring a file in**
that copies anything from anywhere on the disk. Click a file to open it in an
editor pane with **Save** and, for anything runnable, **Save and run**. Every
row says what language it is and how big it is, and a runnable one gets a Run
button.

**Run** — point at a file and press Run. PyCmd works out what it is, finds the
best toolchain installed for it, builds if it needs building, and streams the
output to the Console. It always says which toolchain it used.

**Toolchains** — the screen that is new on Windows, and the most useful one
here. It lists 51 compilers and interpreters, says which are installed and
what version, and for the rest gives you the exact `winget`, `scoop` or
`choco` line — with a button that runs it. See
[TOOLCHAINS.md](TOOLCHAINS.md).

**Languages** — all 65 file types, searchable, each saying whether this
machine is ready to run it.

**Servers** — run a script, a program, a folder or a page and reach it over
HTTP. Type a path and it tells you *before* you press Start what that would
be — run as a program, serve that folder, open on that page — because a folder
with an `app.py` in it and one with an `index.html` are different things. Pick
the port or let it choose a free one, name it, and decide whether the rest of
your network may reach it: **loopback unless you tick the box**, because a
server the network can see is a decision somebody should make on purpose. Each
one has its own log, a Stop and a Kill.

**Pages** — point at a folder you already have in the workspace, or start a
new one from a template. Up to 70 pages, 25 running at once. Start, stop,
rename and remove — and **removing a page leaves your folder alone**, because
a page is a pointer at your files and deleting the pointer should not delete
what it pointed at. With a Cloudflare account connected, deploy to a
`pages.dev` address that stays up when the machine is off.

**Packages** — Python libraries from PyPI, installed into PyCmd's own
`site-packages` rather than your system Python, so nothing PyCmd installs can
break anything else on the machine. **Look it up first** asks PyPI what a
package is and whether it ships compiled parts *before* the download — and on
Windows that is no longer a refusal, because with a C compiler installed a
package with an extension will build rather than give up.

**Plugins** — thirteen built into the app, plus any you install. Includes a
button to bring a plugin over from the phone; see [MOBILE.md](MOBILE.md).

**Guides** — these documents, in the app.

**System** — what PyCmd is using and where, and whether there is a newer
version.

---

## What is different from the phone

| | Android | Windows |
|---|---|---|
| Languages | 34 file types | **65** |
| Runnable | 6 | **43** |
| C, Go, Rust | built-in interpreters | **real compilers**, interpreters as the fallback |
| C++, Java, Kotlin, C#, Haskell… | edit and serve only | **run** |
| Toolchains | none possible | **51 found and driven** |
| Where files live | app-private storage | `%LOCALAPPDATA%\PyCmd`, an ordinary folder |
| Music tab | yes, with lock-screen controls | no — Windows has no lock screen to draw them on |
| Updates | installs the APK over itself | downloads, verifies, and lets you replace the exe |

**Nothing was removed except the Music tab**, and that only because the half
of it that mattered was Android's media session drawing controls on a lock
screen. Play music in something that is good at playing music.

---

## The parts that are shared

This is a port, not a rewrite, and the numbers say so. Every one of these is
the same file on both:

- the Python engine — the runtime, shell, servers, pages, packages, preview,
  plugins, doctor, cloud and downloads, about 21,000 lines;
- the C, Go and Rust interpreters;
- `console.js`, `editor.js` and `highlight.js`, loaded into the window as they
  are;
- all five bundled plugins, and every plugin panel in them;
- the whole plugin API.

What is Windows-only is the shell around it: where files live, which compilers
exist, how a run is planned, and the window itself. That is about 3,000 lines
against 21,000 shared, and it means a fix on either side is a fix on both.

---

## Running it from the source

You do not need to build an exe to use it:

```powershell
git clone https://github.com/expstudiooficial/pycmd
cd pycmd
git checkout windowsmain
pip install pywebview
python -m pycmd_win.app          # from the windows\ folder on your PYTHONPATH
```

Or, without a window at all:

```powershell
python -m pycmd_win.app --serve-only
```

That prints an address you can open in any browser. The whole interface works
there — it is the same API over HTTP — which is how the Windows build is
tested on machines that are not Windows.

See [FORKING.md](FORKING.md) for building `PyCmd.exe` itself.
