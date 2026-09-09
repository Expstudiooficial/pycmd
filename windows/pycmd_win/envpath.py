"""Noticing that the PATH changed while PyCmd was running.

This is the bug behind "the toolchains install but twenty-seven of them cannot
be installed", and behind Android Lab never finding the SDK it had just
downloaded. Both had the same cause and neither had anything to do with the
installers.

On Windows, PATH lives in the registry - the user's half in
``HKCU\\Environment`` and the machine's in the Session Manager key - and a
process is handed a *copy* of it when it starts. Windows broadcasts a message
when it changes; Explorer listens and gives new processes the new value.
Nothing updates a process that is already running. Ever.

So the sequence was:

1. PyCmd starts. Its PATH has no ``~\\scoop\\shims`` in it, because scoop was
   not installed yet.
2. PyCmd installs scoop, then ``scoop install go``. Both work perfectly. Go is
   on the disk and the registry PATH now names the shims folder.
3. PyCmd checks whether Go arrived, with ``shutil.which("go")``, which reads
   ``os.environ["PATH"]`` - the copy from step 1.
4. Not found. Reported as "it ran but the program did not appear".

Every install failed that way, and the report blamed the package manager for
something it had done correctly. Restarting PyCmd would have "fixed" it, which
is exactly the kind of bug that makes an app feel broken and random.

Two things fix it, and both are needed:

* **Re-read the registry.** That is the authoritative PATH, and it is what a
  newly started program would get.
* **Add the well-known folders anyway.** The registry write and the install
  finishing are not atomic, and some installers put things on the PATH only
  for the next login. Knowing that scoop shims live in ``~\\scoop\\shims`` is
  not a guess - it is scoop's documented layout - so PyCmd looks there whether
  or not the registry has caught up.

Everything here is a no-op off Windows, where an inherited PATH is just as
stale but there is no registry to consult and the tests run on Linux.
"""

from __future__ import annotations

import os

WINDOWS = os.name == "nt"

# Where the package managers put the programs they install. These are the
# documented layouts, not guesses, and they are added whether or not the
# registry has caught up with them yet.
KNOWN = (
    (r"%USERPROFILE%\scoop\shims", "scoop"),
    (r"%SCOOP%\shims", "scoop"),
    (r"%ProgramData%\scoop\shims", "scoop, installed for everybody"),
    (r"%ALLUSERSPROFILE%\chocolatey\bin", "chocolatey"),
    (r"%ProgramData%\chocolatey\bin", "chocolatey"),
    (r"%LOCALAPPDATA%\Microsoft\WindowsApps", "winget's shims"),
    (r"%LOCALAPPDATA%\Programs\Python\Python313", "python"),
    (r"%LOCALAPPDATA%\Programs\Python\Python313\Scripts", "python"),
    (r"%USERPROFILE%\.cargo\bin", "rust"),
    (r"%USERPROFILE%\go\bin", "go"),
    (r"%USERPROFILE%\.dotnet\tools", "dotnet"),
    (r"%LOCALAPPDATA%\Android\Sdk\platform-tools", "android"),
    (r"%LOCALAPPDATA%\Android\Sdk\emulator", "android"),
    (r"%LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest\bin", "android"),
    (r"%ProgramFiles%\Git\bin", "git, which brings bash"),
    (r"%ProgramFiles%\Git\usr\bin", "git's unix tools"),
)


def _registry_path() -> list:
    """PATH as the registry has it - what a new process would be given."""
    if not WINDOWS:
        return []
    try:
        import winreg
    except ImportError:
        return []

    found = []
    places = (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    )
    for root, key in places:
        try:
            with winreg.OpenKey(root, key) as handle:
                value, _kind = winreg.QueryValueEx(handle, "Path")
        except OSError:
            continue
        if isinstance(value, str):
            found.extend(part for part in value.split(os.pathsep) if part.strip())
    return found


def _expanded_known() -> list:
    """The documented install folders, with the variables filled in.

    A folder that does not exist is dropped rather than added: a PATH full of
    entries that are not there makes every lookup slower for no benefit, and
    they get added the moment something creates them anyway.
    """
    out = []
    for template, _why in KNOWN:
        try:
            path = os.path.expandvars(template)
        except Exception:  # noqa: BLE001
            continue
        # expandvars leaves %NAME% in place when the variable is not set.
        if "%" in path:
            continue
        if os.path.isdir(path):
            out.append(path)
    return out


def refresh() -> dict:
    """Brings this process's PATH back in line with the machine's.

    Returns what changed, so a screen can say "four new places to look" rather
    than silently doing something invisible.
    """
    current = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p.strip()]
    seen = {os.path.normcase(os.path.normpath(p)) for p in current}

    added = []
    for candidate in _registry_path() + _expanded_known():
        key = os.path.normcase(os.path.normpath(candidate))
        if key in seen:
            continue
        seen.add(key)
        added.append(candidate)

    if added:
        os.environ["PATH"] = os.pathsep.join(current + added)
    return {"added": added, "entries": len(current) + len(added)}


def ensure(*folders: str) -> list:
    """Puts specific folders on the PATH, if they are real and not there yet.

    For the case where something was just installed into a folder PyCmd knows
    about by name - an SDK root, a bucket's bin - and waiting for the registry
    would mean waiting for a restart.
    """
    current = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p.strip()]
    seen = {os.path.normcase(os.path.normpath(p)) for p in current}
    added = []
    for folder in folders:
        if not folder or not os.path.isdir(folder):
            continue
        key = os.path.normcase(os.path.normpath(folder))
        if key in seen:
            continue
        seen.add(key)
        added.append(folder)
    if added:
        os.environ["PATH"] = os.pathsep.join(current + added)
    return added
