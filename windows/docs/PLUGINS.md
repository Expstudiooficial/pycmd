# Writing a plugin

The plugin API is the same on Windows and Android, and this document is the
short version of what is different. The full guide — the manifest, exports,
commands, settings, panels, the whole bridge — is
[PLUGINS.md](../../PLUGINS.md) in the repository root, and every word of it
applies here.

## The shape

A plugin is one of three things:

```
thing.py            one file with a PLUGIN = {...} dict in it
thing/              a folder with plugin.json and an entry module
thing.zip           the same folder, zipped
```

Install one from **Plugins → Bring a plugin over**, which takes a path to any
of them. It arrives switched off.

## What is the same

Everything that matters:

- `plugin.json` — every field, unchanged.
- Exports, commands, settings, file actions, guides, tab and panel
  declarations.
- The panel bridge: `pycmd.call`, `pycmd.poll`, `pycmd.on`, `pycmd.toast`,
  `pycmd.log`, `pycmd.close`, `pycmd.plugin`.
- The Python API a plugin gets: `api.export`, `api.command`, `api.store`,
  `api.write`, `api.refresh`, `api.send`.
- The house stylesheet injected into every panel.

A plugin written for the phone and a plugin written here are the same
artefact. There is no Windows plugin format.

## What is different

**Paths.** The workspace is `%LOCALAPPDATA%\PyCmd\workspace`, not
`/data/user/0/...`. Use `os.path.join` and the paths the API hands you and you
will never notice; hard-code a `/storage/emulated/0` and you will.

**Permissions that do not exist here.** `notifications`, `wakelock` and
`media` are Android's. Declaring one is not an error — it is ignored, and the
import screen says so. `files`, `network`, `console`, `servers` and `packages`
all mean what they always did.

**You can shell out.** A plugin can run a real program:

```python
import subprocess

result = subprocess.run(["git", "status"], capture_output=True, text=True)
```

On the phone that would find almost nothing to run. Here it finds whatever is
installed — which is the single biggest thing a Windows plugin can do that a
phone one cannot. Pass a list of arguments, never a string with `shell=True`:
a workspace under `C:\Users\Some One` is the normal case.

**You can see the toolchains.** PyCmd's own table is importable:

```python
from pycmd_win import toolchains

if toolchains.detect("go").get("path"):
    ...
```

**Panels scroll the same way.** Everything the phone build learned applies:
write an ordinary page, do not ask for a percentage height, and put anything
that must be reachable at the top rather than pinning it to the bottom.

**A panel is a tab.** Since 3.0, a plugin that declares a `panel` gets its own
entry in the sidebar, under **Plugins**, beside the screens PyCmd ships with —
it is not a sheet that opens over the app any more. So it gets the whole middle
of the window and it stays where the person left it. `pycmd.close()` still
works; it takes the person back to the Plugins tab rather than dismissing
anything.

## Testing one

```powershell
python -m pycmd_win.app --serve-only
```

That prints an address. Open it in a browser, install your plugin, open its
panel — with the browser's own developer tools available, which is a good deal
easier than debugging a panel on a phone.
