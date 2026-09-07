"""Setting a machine up for every language at once, unattended.

This is what the birthday console command unlocks, and it is the honest
version of "install everything": a long, resumable, interruptible run that
says what it is doing, keeps going when one thing fails, and never leaves the
app wedged behind it.

The design decisions worth stating, because "install all the compilers" is a
request that goes wrong in predictable ways:

* **It runs on its own thread and reports as it goes.** Fifty toolchains is
  an hour or more of downloading on a good connection. A modal spinner over
  an hour is not a feature, so this streams progress and the rest of PyCmd
  stays usable while it runs.

* **It can be stopped, and stopping means stopping.** The flag is checked
  between toolchains, not inside one - killing a package manager halfway
  through writing its files is how a machine ends up with a half-installed
  compiler and no way to tell.

* **One failure is not the end.** Machines differ, buckets move, packages get
  renamed. Every toolchain that fails is recorded with the reason and the run
  carries on; the report at the end lists what worked, what did not, and what
  to do about each.

* **It is resumable and it is cheap to re-run.** Anything already present is
  skipped in the time it takes to stat a file, because detection remembers
  across launches now. Running this twice is not running it twice.

* **Order is deliberate.** The package manager first, because nothing else
  can happen without it. Then the small, fast, high-value ones - Node, Go,
  Python - so a person who gets bored and stops after five minutes still has
  a usable machine. The enormous ones - the .NET SDK, Rust, the JVM
  languages, Haskell - go last, because they are where the hour goes.
"""

from __future__ import annotations

import threading
import time

from . import install, toolchains

# Roughly ascending by download size and descending by how likely somebody is
# to want it today. Anything not named here runs afterwards, in table order,
# so adding a toolchain does not mean remembering to add it twice.
FIRST = (
    "node", "python", "go", "rustc", "gcc", "gpp", "deno", "bun", "tsc",
    "ruby", "php", "perl", "lua", "tclsh", "awk", "sqlite",
)
LAST = (
    "dotnet", "fsi", "kotlinc", "scala", "clojure", "groovy", "java",
    "runghc", "swiftc", "julia", "rscript", "ocaml", "racket",
    "elixir", "escript", "crystal", "nim", "vlang", "zig", "dmd", "fpc",
)

# Every name above has to be a real toolchain id. They were not, first time:
# "kotlin", "ghc", "erlang" and "gnat" are the names people use and none of
# them is the id in the table, so those four sorted into the middle of the run
# instead of the end - the four biggest downloads, in the place chosen for the
# small ones. A list of strings that silently means nothing when it is wrong
# needs something to say so, and the suite now does.


class Run:
    """One setup run, and the only thing the UI holds on to."""

    def __init__(self):
        self.started = time.time()
        self.finished = 0.0
        self.stopping = False
        self.current = ""
        self.done: list = []
        self.failed: list = []
        self.skipped: list = []
        self.lines: list = []
        self.total = 0
        self._lock = threading.RLock()

    def write(self, text: str) -> None:
        with self._lock:
            self.lines.append(text)
            # A cap, because a package manager that decides to print a
            # progress bar as a thousand lines should not become the reason
            # the app runs out of memory an hour in.
            if len(self.lines) > 4000:
                del self.lines[:2000]

    def drain(self) -> list:
        with self._lock:
            out, self.lines = self.lines, []
            return out

    def as_dict(self) -> dict:
        with self._lock:
            return {
                "running": not self.finished,
                "stopping": self.stopping,
                "current": self.current,
                "done": list(self.done),
                "failed": list(self.failed),
                "skipped": list(self.skipped),
                "total": self.total,
                "settled": len(self.done) + len(self.failed) + len(self.skipped),
                "started": self.started,
                "finished": self.finished,
                "seconds": int((self.finished or time.time()) - self.started),
            }


_run: Run | None = None
_run_lock = threading.RLock()


def order() -> list:
    """Every toolchain id, in the order they should be attempted."""
    ids = [chain.id for chain in toolchains.TOOLCHAINS]
    first = [i for i in FIRST if i in ids]
    last = [i for i in LAST if i in ids]
    named = set(first) | set(last)
    middle = [i for i in ids if i not in named]
    return first + middle + last


def state() -> dict:
    """What the current or last run is doing. Always answers."""
    with _run_lock:
        if _run is None:
            return {"running": False, "everStarted": False,
                    "total": len(toolchains.TOOLCHAINS)}
        data = _run.as_dict()
        data["everStarted"] = True
        return data


def lines() -> list:
    with _run_lock:
        return _run.drain() if _run is not None else []


def stop() -> dict:
    with _run_lock:
        if _run is None or _run.finished:
            return {"ok": True, "note": "nothing is running"}
        _run.stopping = True
        _run.write("[PyCmd] stopping after this one finishes.\n")
        return {"ok": True}


def start(only_missing: bool = True) -> dict:
    """Begins a run. One at a time; asking twice is not an error."""
    global _run
    with _run_lock:
        if _run is not None and not _run.finished:
            return {"ok": False, "reason": "already-running",
                    "error": "a setup run is already going"}
        _run = Run()
        run = _run

    threading.Thread(target=_work, args=(run, only_missing),
                     name="pycmd-setup-all", daemon=True).start()
    return {"ok": True, "started": True}


def _work(run: Run, only_missing: bool) -> None:
    try:
        _do(run, only_missing)
    except Exception as error:  # noqa: BLE001 - a crash here must be visible
        import traceback

        run.write(f"[PyCmd] the setup run itself broke: {error}\n")
        run.write(traceback.format_exc())
    finally:
        run.current = ""
        run.finished = time.time()
        run.write(
            f"[PyCmd] done in {int(run.finished - run.started)}s - "
            f"{len(run.done)} installed, {len(run.skipped)} already here, "
            f"{len(run.failed)} could not be.\n"
        )


def _do(run: Run, only_missing: bool) -> None:
    todo = order()
    run.total = len(todo)
    run.write(f"[PyCmd] setting this machine up for {len(todo)} toolchains.\n")
    run.write("[PyCmd] you can keep using PyCmd while this runs, and Stop "
              "takes effect after the current one.\n\n")

    # A package manager first. Without one, every single install below fails
    # for the same reason, and fifty identical failures is not a report.
    if not any(install.find(m) for m in install.PREFERENCE):
        run.write("[PyCmd] no package manager here yet, so Scoop goes in "
                  "first - it needs no administrator.\n")
        got = install.bootstrap("scoop", run.write)
        if not got.get("ok"):
            run.write(f"[PyCmd] {got.get('error', 'Scoop would not install')}\n")
            run.write("[PyCmd] carrying on anyway: winget may be here, and "
                      "some toolchains have other routes.\n")
        run.write("\n")

    for toolchain_id in todo:
        if run.stopping:
            run.write("[PyCmd] stopped.\n")
            break
        chain = toolchains.by_id(toolchain_id)
        if chain is None:
            continue
        run.current = chain.name

        if only_missing and toolchains.detect(toolchain_id).get("path"):
            run.skipped.append(toolchain_id)
            continue

        result = install.install(toolchain_id, run.write)
        if result.get("ok") and result.get("already"):
            run.skipped.append(toolchain_id)
        elif result.get("ok"):
            run.done.append(toolchain_id)
        else:
            run.failed.append({
                "id": toolchain_id, "name": chain.name,
                "why": result.get("error", "it did not install"),
                "site": chain.site,
            })
        run.write("\n")

    # The PATH has almost certainly changed underneath us, and what was
    # remembered from before the run is now wrong about half the machine.
    toolchains.clear_cache()
    toolchains.detect_all(refresh=True)
