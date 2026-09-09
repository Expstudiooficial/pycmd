# Forking PyCmd for Windows

PyCmd is yours to fork, change and ship. Two conditions, the same as the phone
build's: **keep the name and the credit**, and **say what you changed**. That
is it — no licence gymnastics, no permission to ask.

## Getting the source

The whole thing, including the Android build it was ported from:

```powershell
git clone https://github.com/expstudiooficial/pycmd
cd pycmd
git checkout windowsmain
```

Or download it as a zip:
<https://codeload.github.com/expstudiooficial/pycmd/zip/refs/heads/windowsmain>

The **System** screen inside the app has that link too, so a fork can be made
from a machine that only has the exe.

## What is where

```
windows/
  pycmd_win/        the Windows shell - about 3,000 lines
    store.py        where files live
    toolchains.py   the 51 compilers, and how to drive them
    langs.py        the language table, Android's caveats lifted
    runner.py       pressing Run
    builtins.py     the thirteen built-in plugins
    bundle.py       shipped plugins, and importing a phone one
    host.py         the one object the window's JavaScript calls
    updates.py      where new versions come from
    app.py          the window and its loopback server
  ui/               the app chrome: index.html, app.css, app.js, screens.js
  build/            the PyInstaller recipe and build.ps1
  docs/             these guides

app/src/main/python/    the engine - shared with Android, unchanged
app/src/main/assets/    web assets, plugins, docs - shared with Android
tools/                  the checks
dist-windows/           the published exe and its manifest
```

**The engine is shared, not copied.** `app/src/main/python` is the same 21,000
lines the Android build runs, with no Android imports in any of it. Change
something there and you have changed both.

## Running it without building

```powershell
pip install pywebview
$env:PYTHONPATH = "windows"
python -m pycmd_win.app
```

Or with no window at all, which works anywhere including Linux:

```powershell
python -m pycmd_win.app --serve-only
```

That prints a `127.0.0.1` address serving the whole interface over the same
API the window uses. It is how this build is developed and tested.

## Building the exe

On Windows:

```powershell
powershell -ExecutionPolicy Bypass -File windows\build\build.ps1
```

That makes a virtual environment inside the checkout, installs PyInstaller and
pywebview into it, runs the checks, builds, and prints the SHA-256. Nothing
touches the machine outside the repository folder; delete `.build-venv` when
you are done.

By hand:

```powershell
pip install -r windows\build\requirements.txt
pyinstaller windows\build\pycmd.spec --noconfirm --distpath dist-windows\build
```

You get `dist-windows\build\PyCmd.exe` — one file, around 40 MB, with the
engine, the web assets, the bundled plugins and the guides inside it.

### Or let CI do it

`.github/workflows/windows.yml` builds on a Windows runner, runs the checks,
proves the exe starts, and prints its hash. Push a tag like `windows-v1.0.1`
and it also writes `dist-windows/latest.json` and attaches the exe to a
release.

That workflow exists because the exe cannot honestly be built anywhere else:
Windows is where PyInstaller makes a Windows binary, and the only place the
result can be started to see whether it opens.

## Signing it

The published exe is **not signed**, because signing needs a certificate and a
public repository cannot hold one. Windows SmartScreen warns about it until
enough people have run it.

If you have a code-signing certificate:

```powershell
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 `
  /f your-cert.pfx /p yourpassword dist-windows\build\PyCmd.exe
```

Do that after building and before publishing. A signed fork is a better
citizen than an unsigned one and costs you a certificate.

## The checks

```powershell
python tools\test_windows.py           # 80 checks, runs anywhere
python tools\test_toolchains_live.py   # compiles and runs in every language you have
python tools\test_toolchains_live.py --list
```

The first is the one to keep green. The second depends on what is installed
and is honest about it: on a machine with nothing it says so and passes.

The Android suite still applies to the shared engine:

```bash
tools/run-tests.sh
```

## Publishing your own updates

`dist-windows/latest.json` is what the app reads to find a newer build.
Change `REPO` and `BRANCH` at the top of `tools/make_latest_windows.py` and
`MANIFEST_URL` in `windows/pycmd_win/updates.py` to point at your fork, then:

```powershell
python tools\make_latest_windows.py dist-windows\PyCmd-1.0.1.exe --notes "..."
```

That writes the manifest and `SHA256SUMS.txt`. The app refuses a download
whose bytes do not match the checksum, and deletes it rather than leaving it
on disk looking installable — so a fork that publishes a manifest without a
real hash publishes something nobody can install, which is the correct
outcome.

## The one thing not to do

Do not take the name off. PyCmd checks at start-up that it is still called
PyCmd, and stops if it is not. That is a reasonable thing to do to a build
that has had its credit stripped, and it is why `tools/test_branding.py`
exists — so an accident costs a red line in the suite instead of an app that
will not open.

Rename your fork to something of your own and that check has nothing to say
about it. It only objects to a build that is PyCmd with the name filed off.

## Getting in touch

andrejbaltes4@proton.me
