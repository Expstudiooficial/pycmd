"""Installing toolchains, including installing the thing that installs them.

The gap this closes: every toolchain in the table carries a `winget install`,
`scoop install` or `choco install` line, and the Toolchains screen showed it
and let you run it. That works right up until the machine has not got the
package manager the line names - and then the answer to "install Go" is an
error about `scoop` not being recognised, which is true, unhelpful, and
somebody else's problem to solve.

It should not be somebody else's problem. So:

* **The managers are detected like anything else.** winget, scoop and choco
  are three more programs to look for.
* **A missing one can be installed.** Each carries its own vendor-documented
  bootstrap. They are not equal and the differences decide which is preferred:

  - **scoop** installs per-user, needs no administrator, and puts everything
    under `~\\scoop`. It is the one to bootstrap, and the only one PyCmd will
    install without being asked twice.
  - **winget** ships with Windows itself on anything current. When it is
    missing the machine is old or App Installer was removed, and the honest
    answer is a Store link rather than a download PyCmd pretends to manage.
  - **choco** needs administrator for its own install and for every package
    after it. Offered, explained, never silent.

* **Installing falls back.** Asking for Go should not fail because the
  manager PyCmd guessed first has not got it under that name. Every
  toolchain's managers are tried in turn, and what actually worked is
  remembered so the next one starts there.

Nothing here runs on import, nothing installs anything without being called,
and every command is shown to the user before it runs - a tool that downloads
and executes vendor scripts has to be legible about it, and the whole command
line appears on screen and in the log.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time

from . import envpath, known, toolchains

WINDOWS = os.name == "nt"

# How long any one install may take. Rust and the .NET SDK are genuinely
# enormous; a ceiling of twenty minutes is generous for them and still means a
# wedged installer cannot hold the app for ever.
INSTALL_TIMEOUT = 20 * 60
BOOTSTRAP_TIMEOUT = 10 * 60


class Manager:
    """One package manager, and how to get it if it is not here."""

    __slots__ = ("id", "name", "program", "install_verb", "bootstrap",
                 "needs_admin", "can_bootstrap", "note", "site")

    def __init__(self, id, name, program, install_verb, bootstrap=(),
                 needs_admin=False, can_bootstrap=False, note="", site=""):
        self.id = id
        self.name = name
        self.program = program
        # The arguments that install a package, with {package} filled in.
        self.install_verb = tuple(install_verb)
        # A PowerShell script that installs the manager itself.
        self.bootstrap = tuple(bootstrap)
        self.needs_admin = needs_admin
        self.can_bootstrap = can_bootstrap
        self.note = note
        self.site = site

    def as_dict(self) -> dict:
        where = find(self.id)
        return {
            "id": self.id, "name": self.name, "program": self.program,
            "installed": bool(where), "path": where,
            "needsAdmin": self.needs_admin, "canBootstrap": self.can_bootstrap,
            "note": self.note, "site": self.site,
        }


MANAGERS = [
    Manager(
        "scoop", "Scoop", "scoop",
        ("install", "{package}"),
        # Scoop's own documented one-liner, from get.scoop.sh. Per-user, no
        # elevation, everything under ~\scoop and removable by deleting it.
        bootstrap=(
            "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force; "
            "Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression"
        ),
        can_bootstrap=True,
        note="Installs for you alone, under your home folder, and needs no "
             "administrator. This is the one PyCmd will set up for you.",
        site="https://scoop.sh/",
    ),
    Manager(
        "winget", "winget", "winget",
        ("install", "--accept-package-agreements", "--accept-source-agreements",
         "--silent", "--id", "{package}"),
        note="Comes with Windows. If it is missing, App Installer was removed "
             "or this Windows is older than 1809 - the Store has it back.",
        site="https://apps.microsoft.com/detail/9nblggh4nns1",
    ),
    Manager(
        "choco", "Chocolatey", "choco",
        ("install", "-y", "{package}"),
        bootstrap=(
            "Set-ExecutionPolicy Bypass -Scope Process -Force; "
            "[System.Net.ServicePointManager]::SecurityProtocol = "
            "[System.Net.ServicePointManager]::SecurityProtocol -bor 3072; "
            "Invoke-Expression ((New-Object System.Net.WebClient)"
            ".DownloadString('https://community.chocolatey.org/install.ps1'))"
        ),
        needs_admin=True, can_bootstrap=True,
        note="Installs machine-wide and needs administrator, both to install "
             "itself and for every package afterwards.",
        site="https://chocolatey.org/install",
    ),
]

_BY_ID = {manager.id: manager for manager in MANAGERS}

# Which to reach for first. Scoop leads because it is the one that can be had
# without elevation, so a machine with nothing installed can get from nothing
# to a working toolchain without a single administrator prompt.
PREFERENCE = ("scoop", "winget", "choco")

# Scoop keeps most things in `main` and the rest in buckets you have to add.
# `scoop install kotlin` on a fresh scoop simply says it cannot find kotlin,
# which reads as "that package does not exist" rather than "you have not added
# the bucket it lives in". Adding the three standard ones costs a git clone
# each, once, and turns a large class of "cannot be installed" into installs.
BUCKETS = ("extras", "java", "versions")

_where: dict[str, str] = {}
_where_lock = threading.RLock()


def _no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0


def find(manager_id: str, refresh: bool = False) -> str:
    """Where this manager is, or "" - cached, because PATH does not move."""
    with _where_lock:
        if not refresh and manager_id in _where:
            return _where[manager_id]
    manager = _BY_ID.get(manager_id)
    found = shutil.which(manager.program) if manager else ""
    with _where_lock:
        _where[manager_id] = found or ""
    return found or ""


def available() -> list:
    """Every manager, and whether it is here. This is a screen."""
    return [manager.as_dict() for manager in MANAGERS]


def best_manager(chain) -> str:
    """Which installed manager can install this toolchain, preferring cheap.

    Returns "" when none of the managers that know this package are here.
    """
    for manager_id in PREFERENCE:
        if getattr(chain, manager_id, "") and find(manager_id):
            return manager_id
    return ""


def _package_for(chain, manager_id: str) -> str:
    """The package name out of the toolchain's own install line.

    The table stores whole command lines - "scoop install nodejs-lts" - because
    that is what a person needs to see and copy. What is needed to *run* it is
    the last word, and taking it from the same string means the screen and the
    button can never disagree about which package is meant.
    """
    line = getattr(chain, manager_id, "") or ""
    parts = line.split()
    return parts[-1] if parts else ""


def plan(toolchain_id: str) -> dict:
    """What installing this would do, without doing any of it.

    Every screen that offers an install shows this first. "It will run scoop
    install go" is a thing somebody can agree to; a spinner is not.
    """
    chain = toolchains.by_id(toolchain_id)
    if chain is None:
        return {"ok": False, "error": f"there is no toolchain called {toolchain_id!r}"}

    if toolchains.detect(toolchain_id).get("path"):
        return {"ok": True, "already": True, "toolchain": chain.id,
                "name": chain.name,
                "note": f"{chain.name} is already here."}

    routes = []
    for manager_id in PREFERENCE:
        package = _package_for(chain, manager_id)
        if not package:
            continue
        manager = _BY_ID[manager_id]
        here = bool(find(manager_id))
        routes.append({
            "manager": manager_id, "managerName": manager.name,
            "package": package, "ready": here,
            "needsAdmin": manager.needs_admin,
            "canBootstrap": manager.can_bootstrap,
            "command": " ".join([manager.program] +
                                [p.format(package=package) for p in manager.install_verb]),
        })

    if not routes:
        return {
            "ok": False, "toolchain": chain.id, "name": chain.name,
            "reason": "no-package",
            "error": f"No package manager here carries {chain.name}.",
            "site": chain.site,
        }

    ready = [route for route in routes if route["ready"]]
    return {
        "ok": True, "already": False, "toolchain": chain.id, "name": chain.name,
        "routes": routes,
        "ready": bool(ready),
        # What would actually happen if the button were pressed now.
        "willUse": (ready or routes)[0],
        "needsBootstrap": not ready,
        "site": chain.site,
    }


def _run(command, timeout: float, write) -> tuple:
    """Runs one install, streaming what it says. Returns (ok, output).

    The same daemon-reader shape the version probes use, and for the same
    reason: an installer that spawns a child which holds the output pipe is
    the normal case here, not a strange one, and `subprocess.run(timeout=)`
    hangs on exactly that.
    """
    write("$ " + " ".join(command) + "\n")
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace", bufsize=1, creationflags=_no_window(),
        )
    except FileNotFoundError:
        return False, f"{command[0]} is not there"
    except OSError as error:
        return False, f"could not start {command[0]}: {error}"

    collected = []

    def read():
        try:
            for line in process.stdout:
                collected.append(line)
                write(line)
        except Exception:  # noqa: BLE001
            pass

    reader = threading.Thread(target=read, name="pycmd-install", daemon=True)
    reader.start()
    reader.join(timeout)
    if reader.is_alive():
        _kill(process)
        reader.join(2.0)
        return False, "it did not finish in time"

    try:
        code = process.wait(timeout=15)
    except Exception:  # noqa: BLE001
        _kill(process)
        code = -1
    return code == 0, "".join(collected)


def _kill(process) -> None:
    try:
        if WINDOWS:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                           capture_output=True, timeout=15)
        else:
            process.kill()
    except Exception:  # noqa: BLE001
        try:
            process.kill()
        except Exception:  # noqa: BLE001
            pass


def bootstrap(manager_id: str, write=None) -> dict:
    """Installs a package manager itself.

    Only scoop and choco can be, and only choco needs administrator. winget is
    part of Windows and is not something to be downloaded from us: pointing at
    the Store is the honest answer, and pretending otherwise would mean
    shipping an installer for a Microsoft component.
    """
    write = write or (lambda text: None)
    manager = _BY_ID.get(manager_id)
    if manager is None:
        return {"ok": False, "error": f"there is no manager called {manager_id!r}"}
    if find(manager_id, refresh=True):
        return {"ok": True, "already": True,
                "note": f"{manager.name} is already here."}
    if not manager.can_bootstrap:
        return {"ok": False, "reason": "cannot-bootstrap", "site": manager.site,
                "error": f"{manager.name} is not something PyCmd installs. {manager.note}"}
    if not WINDOWS:
        return {"ok": False, "reason": "not-windows",
                "error": "package managers are only installed on Windows"}

    write(f"[PyCmd] installing {manager.name}. This runs its own installer, "
          f"published by {manager.name}:\n")
    ok, output = _run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command", manager.bootstrap],
        BOOTSTRAP_TIMEOUT, write,
    )
    # The installer put things on the PATH *in the registry*; this process is
    # still holding the copy it started with, so without this the manager it
    # just installed is invisible to the next line of code.
    envpath.refresh()
    where = find(manager_id, refresh=True)
    if where:
        write(f"[PyCmd] {manager.name} is in place at {where}\n")
        if manager_id == "scoop":
            add_buckets(write)
        return {"ok": True, "path": where}
    return {"ok": False,
            "error": f"{manager.name} did not appear afterwards. {manager.note}",
            "site": manager.site, "output": output[-2000:] if output else ""}


def add_buckets(write=None) -> list:
    """Adds scoop's standard buckets, so its whole catalogue is reachable.

    Idempotent: scoop says "bucket already added" and exits non-zero for one
    that is there, which is not a failure and is not treated as one.
    """
    write = write or (lambda text: None)
    scoop = find("scoop")
    if not scoop:
        return []
    added = []
    for bucket in BUCKETS:
        ok, output = _run([scoop, "bucket", "add", bucket], 300, write)
        if ok or "already" in (output or "").lower():
            added.append(bucket)
    if added:
        write(f"[PyCmd] scoop buckets ready: {', '.join(added)}\n")
    return added


def install(toolchain_id: str, write=None, allow_bootstrap: bool = True) -> dict:
    """Installs one toolchain, trying every route it has.

    The fallback is the point. A single `scoop install` that fails because the
    package moved, or because that bucket is not added, used to be the end of
    it; now winget and choco are tried in turn, and only when all of them have
    said no does this give up and hand back the vendor's own page.
    """
    write = write or (lambda text: None)
    chain = toolchains.by_id(toolchain_id)
    if chain is None:
        return {"ok": False, "error": f"there is no toolchain called {toolchain_id!r}"}

    envpath.refresh()
    found = toolchains.detect(toolchain_id, refresh=True)
    if found.get("path"):
        write(f"[PyCmd] {chain.name} is already here ({found.get('version', '')})\n")
        return {"ok": True, "already": True, "path": found["path"],
                "version": found.get("version", "")}

    made = plan(toolchain_id)
    if not made.get("ok"):
        return made

    routes = made["routes"]
    if allow_bootstrap and not made["ready"]:
        # Nothing that carries this package is installed. Put scoop in place if
        # one of the routes uses it - it is the only one that costs the user
        # nothing but time.
        for route in routes:
            if route["manager"] == "scoop":
                write("[PyCmd] no package manager here can install "
                      f"{chain.name} yet, so Scoop goes in first.\n")
                got = bootstrap("scoop", write)
                if not got.get("ok"):
                    write(f"[PyCmd] {got.get('error', 'that did not work')}\n")
                break

    tried = []
    for route in routes:
        manager_id = route["manager"]
        if not find(manager_id, refresh=True):
            tried.append({"manager": manager_id, "why": "not installed"})
            continue
        manager = _BY_ID[manager_id]
        command = [manager.program] + [
            part.format(package=route["package"]) for part in manager.install_verb
        ]
        write(f"[PyCmd] {chain.name} through {manager.name}\n")
        ok, output = _run(command, INSTALL_TIMEOUT, write)

        # Look again *after* taking the new PATH on board. Without this the
        # check below asks the PATH this process started with, which cannot
        # possibly know about something installed a second ago - and every
        # successful install was reported as "it ran but the program did not
        # appear". That one missing line is what made twenty-seven of them
        # look impossible to install.
        envpath.refresh()

        # Whether the installer said it worked matters less than whether the
        # program is now there. Package managers exit 0 on all sorts of
        # non-events, and exit non-zero on some successes.
        after = toolchains.detect(toolchain_id, refresh=True)
        if after.get("path"):
            known.mark_installed(toolchain_id, manager_id)
            write(f"[PyCmd] {chain.name} {after.get('version', '')} is ready\n")
            return {"ok": True, "path": after["path"],
                    "version": after.get("version", ""), "manager": manager_id}
        tried.append({"manager": manager_id,
                      "why": "it ran but the program did not appear" if ok
                             else (output or "").strip()[-200:]})

    write(f"[PyCmd] nothing here could install {chain.name}.\n")
    return {
        "ok": False, "reason": "every-route-failed", "toolchain": chain.id,
        "name": chain.name, "tried": tried, "site": chain.site,
        "error": f"None of the ways to install {chain.name} worked. "
                 f"{chain.site or 'Its own site has a download.'}",
    }
