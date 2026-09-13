# Forking PyCmd

Forks are welcome. This is the page that gets you from "I want to change
something" to "my build is on my phone", without reading the whole codebase
first.

Two conditions, and they are the ordinary ones:

- **Keep the name and the credit.** PyCmd stays PyCmd in the app, and the
  original stays credited. Add your own name beside it - a fork that improves
  something deserves the line.
- **Don't invert the story.** Do not present the original as a copy of your
  fork, and do not go after the original over a fork of it.

Everything else is yours to change.

---

## What it is made of

```
app/src/main/
  java/com/expstudio/pycmd/    Kotlin: the screens, the bridges, the updater
    ui/                        every screen is one Compose file, named after its tab
    python/PythonEngine.kt     the one door between Kotlin and Python
    plugins/                   the plugin registry and the built-in switches
    music/                     the media session, and the controller for it
    util/                      files, imports, exports, the debug log, updates
  python/                      the interpreter side, and most of the behaviour
    pycmd_runtime.py           running code, streams, stop, completions
    pycmd_shell.py             the console's own commands (pip, ls, run, serve)
    pycmd_servers.py           background servers, and what running a folder means
    pycmd_pages.py             the Pages registry: projects, limits, start and stop
    pycmd_tunnel.py            a public address for a page, over localtunnel
    pycmd_cloudflare.py        Cloudflare Pages and Workers, over their REST API
    pycmd_music.py             the music library: tracks, playlists, order
    pycmd_packages.py          installing wheels from PyPI onto the device
    pycmd_preview.py           the preview pages and the loopback server
    pycmd_plugins.py           loading plugins, and the API they are handed
    pycmd_cloud.py             Supabase and Firebase over REST
    pycmd_langs/               what each file type is, and the C/Go/Rust interpreters
  assets/
    web/                       the console and editor pages (HTML, CSS, JS)
    plugins/                   the plugins that ship inside the APK
      creator/creator_blocks.py  the 904 blocks, and what they compile to
    examples/                  what lands in a new workspace
tools/                         the test suites, and make_latest.py
dist/                          the built APK, its hash, and latest.json
keystore/                      the signing key, so builds can replace each other
```

The split that matters: **Kotlin draws, Python decides.** Almost every
behaviour worth changing is in `app/src/main/python/`, and changing it needs no
Android knowledge at all - it is ordinary Python with a test suite you can run
on a laptop in seconds.

## Building it

You need the Android SDK (platform 35), JDK 17+, and CPython **3.13** on `PATH`
as `python3.13` - Chaquopy uses it to resolve the pip requirements at build
time.

```bash
git clone https://github.com/Expstudiooficial/pycmd.git
cd pycmd
./gradlew :app:assembleRelease -Ppycmd.abi=arm64-v8a
# -> app/build/outputs/apk/release/app-release.apk
```

Leave `-Ppycmd.abi` off to build for x86_64 as well, which is what an emulator
needs.

Before you ship anything:

```bash
tools/run-tests.sh
```

That runs the Python suites, the JavaScript suites under Node, the published
manifest check, and a build with Lint. Everything in `tools/test_*.py` is
plain: no framework, no fixtures, one `check(name, condition)` per fact.

## Making it yours

| What | Where |
|---|---|
| Colours and theme | `app/src/main/java/com/expstudio/pycmd/ui/Theme.kt` |
| Icons | `ui/PyIcons.kt` - path data, no icon library |
| Which tabs exist | `ui/App.kt` and `ui/MoreScreen.kt` |
| Console commands | `python/pycmd_shell.py` - add to `COMMANDS` |
| File types | `python/pycmd_langs/registry.py` |
| Built-in switches | `plugins/Plugins.kt` |
| Bundled plugins | `assets/plugins/<name>/` - one folder each |
| The examples | `assets/examples/` |

**Do not change the application id.** `com.expstudio.pycmd.debug` is what every
installed copy carries, and Android has no way to change an installed app's id:
a new one installs *beside* the old app instead of over it, and the user's
workspace stays behind in the copy nobody opens again.

**Do change the signing key** if you are publishing your own builds - see
`keystore/` and the `signingConfigs` block in `app/build.gradle.kts`. Yours has
to stay the same key from one release to the next, for the same reason.

## Publishing updates for your fork

PyCmd updates itself from one small JSON file, and the address is editable in
the app (**More → System → Updates → Where updates come from**). So a fork
needs no store, no site and no installer of its own:

1. Build a release APK and put it somewhere reachable over **https**.
2. Generate the manifest beside it:

   ```bash
   python3 tools/make_latest.py dist/MyFork-1.0.apk --notes "what changed"
   ```

   Edit `REPO` and `BRANCH` at the top of `make_latest.py` to point at your
   repository first, so the `url` it writes is yours.
3. Tell your users the address of that `latest.json`. From then on their app
   updates itself.

The app checks three things before installing anything: the SHA-256 in the
manifest matches the download, the package name matches, and the signing
certificate matches the build already installed. Get those right and an update
replaces the app in place, keeping the workspace. Get the key wrong and Android
refuses - which is why your key has to stay yours from the first release on.

`latest.json` also carries fields nothing in the app reads - `releasedAt`,
`minSdk`, `abi`, `sizeText`, `changelog` - so a website can render a download
page straight from it.

## The rest of the documentation

- **[PLUGINS.md](PLUGINS.md)** - the plugin format and API. Most changes people
  want are a plugin, not a fork: a plugin can add a tab, put a section inside
  an existing screen, register console commands, claim a file type and publish
  its own guide.
- **[BUILTINS.md](BUILTINS.md)** - what ships, and what each switch does.
- **[TUTORIAL.md](TUTORIAL.md)** - every tab, with things to try.
- **[README.md](README.md)** - what the app is, and the constraints Android
  puts on it. Worth reading before deciding something is a bug: no compiler can
  run on a phone, a downgrade cannot install over a newer build, and an app
  cannot keep a folder through its own uninstall.

## The source, on the phone

[Download the source](pycmd://source)

That is the whole starting kit: the repository as a zip, straight onto this
phone. It lands in **Downloads**, where **Save to device** puts it somewhere
your file manager can see. Unzip it on a machine with the SDK and build.

The same button is on the Guides screen you opened this from, under **Take the
source** - either one does the same thing.

Reading this on a computer rather than in the app? The zip is at
`https://codeload.github.com/expstudiooficial/pycmd/zip/refs/heads/claude/python-mobile-cmd-android-dj1ixb`,
or just clone the repository as above.
