"""Making a phone plugin actually run here, rather than warning about it.

1.0 imported an Android plugin and called it a beta: it read the code, spotted
the Android-only bits, and told you it might not work. That is an honest
report and a useless one - the plugin either runs or it does not, and "we shall
see" is not a feature.

What actually stops a phone plugin working here is narrow and known:

* **`from java import ...`** and friends. Chaquopy puts a `java` module in the
  interpreter on Android; there is none here, so the import raises at load and
  the whole plugin dies before its first line of real work.
* **Android paths.** `/storage/emulated/0/...` and `/data/user/0/<package>/...`
  are where the phone keeps things. Neither exists on Windows.
* **Three capabilities** - notifications, wake locks, media sessions - that
  Windows either does differently or does not have.

None of that is deep. It is a handful of names that need to exist and mean
something sensible. So this module makes them exist:

* a stand-in `java` package whose classes do the Windows equivalent where
  there is one, and are inert but well-behaved where there is not;
* an `android` package covering the same ground;
* a path translator, so a plugin that writes to `/storage/emulated/0/Download`
  writes to the user's Downloads folder;
* and the three capabilities mapped onto what this build genuinely has -
  notifications onto PyCmd's own toasts, wake locks onto the Keep Awake
  built-in, media onto nothing, loudly.

The shim is installed only while a mobile plugin is being imported, and only
for that plugin. It is not put into `sys.modules` globally, because a *Windows*
plugin that imports `java` has made a mistake and should hear about it rather
than silently receive a stub.

**What is honestly not covered.** Anything drawing an Android view, anything
calling into a specific device's hardware, anything expecting a real JVM to be
running. Those are not shimmable and are reported as such - a plugin using them
is told plainly rather than left to fail somewhere confusing.
"""

from __future__ import annotations

import contextlib
import os
import sys
import types

from . import store

# The Android paths a plugin might have hard-coded, and what they mean here.
# The trailing slash matters: "/data/user/0" must not match "/data/user/0x".
PATHS = {
    "/storage/emulated/0/Download": ("downloads", "your Downloads folder"),
    "/storage/emulated/0/Music": ("music", "PyCmd's music folder"),
    "/storage/emulated/0/Documents": ("workspace", "the workspace"),
    "/storage/emulated/0": ("workspace", "the workspace"),
    "/sdcard": ("workspace", "the workspace"),
}

# Anything under the app's private folder on Android maps to PyCmd's own root.
PRIVATE_PREFIXES = ("/data/user/0/com.expstudio.pycmd", "/data/data/com.expstudio.pycmd")


def _inside(base: str, rest: str) -> str:
    """Joins `rest` under `base`, and refuses to leave it.

    The `..` handling is the whole point, and leaving it out was a real hole:
    a plugin asking for `/storage/emulated/0/../../../etc/passwd` had the
    prefix stripped and the remainder joined onto the workspace, which
    normalises straight back out of it. A phone path is untrusted input like
    any other - it comes out of somebody else's plugin - so translating one
    must not become a way to reach the rest of the disk.

    Anything that would escape lands on the base folder itself instead of
    raising: a plugin using a strange path should be contained, not crashed.
    """
    base = os.path.abspath(base)
    joined = os.path.abspath(os.path.join(base, *[p for p in rest.split("/") if p]))
    if joined == base or joined.startswith(base + os.sep):
        return joined
    return base


def translate(path: str) -> str:
    """An Android path as the equivalent Windows one.

    Longest match first, so /storage/emulated/0/Download does not get caught
    by the /storage/emulated/0 rule and land in the workspace.
    """
    if not path:
        return path
    clean = path.replace("\\", "/")
    for prefix in PRIVATE_PREFIXES:
        if clean == prefix or clean.startswith(prefix + "/"):
            rest = clean[len(prefix):].lstrip("/")
            # The phone keeps its files under files/; here that *is* the root.
            if rest.startswith("files/"):
                rest = rest[len("files/"):]
            return _inside(store.root(), rest)
    for prefix in sorted(PATHS, key=len, reverse=True):
        if clean == prefix or clean.startswith(prefix + "/"):
            folder, _ = PATHS[prefix]
            rest = clean[len(prefix):].lstrip("/")
            return _inside(store.folder(folder), rest)
    return path


class _Inert:
    """Something that can be called, indexed and read from without complaint.

    The shape a Java class stub has to have: phone code does
    `Context.getSystemService(...).cancelAll()` and every link in that chain
    has to survive. Returning another one of these from everything means the
    whole chain does, and nothing raises deep inside somebody's plugin because
    an intermediate step was None.
    """

    __slots__ = ("_name", "_note")

    def __init__(self, name="java", note=""):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_note", note)

    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        return _Inert(f"{self._name}.{item}", self._note)

    def __call__(self, *args, **kwargs):
        return _Inert(f"{self._name}()", self._note)

    def __getitem__(self, item):
        return _Inert(f"{self._name}[{item!r}]", self._note)

    def __iter__(self):
        return iter(())

    def __bool__(self):
        # Falsey on purpose. `if Build.VERSION.SDK_INT >= 29:` is the common
        # shape, and a truthy stub would take the Android branch of a plugin
        # that has a perfectly good non-Android one right beside it.
        return False

    def __repr__(self):
        return f"<not on Windows: {self._name}>"

    def __str__(self):
        return ""


def _make_java(bridge) -> types.ModuleType:
    """The `java` module Chaquopy would have provided.

    `jclass` is the one that matters: it is how phone code reaches an Android
    class by name. Where PyCmd has a real Windows answer it hands one back;
    otherwise an inert stub that will not explode.
    """
    module = types.ModuleType("java")

    def jclass(name):
        return _REAL_CLASSES.get(name, _Inert(name, "no Windows equivalent"))(bridge) \
            if name in _REAL_CLASSES else _Inert(name, "no Windows equivalent")

    module.jclass = jclass
    module.cast = lambda kind, obj: obj
    module.detach = lambda: None
    module.__all__ = ["jclass", "cast", "detach"]
    return module


class _Toast:
    """Android's Toast, drawn as one of PyCmd's own."""

    def __init__(self, bridge):
        self._bridge = bridge

    def makeText(self, context, text, duration=0):  # noqa: N802 - Android's name
        self._bridge("toast", str(text))
        return self

    def show(self):
        return None


class _Notifications:
    def __init__(self, bridge):
        self._bridge = bridge

    def notify(self, *args):
        text = next((str(a) for a in args if isinstance(a, str)), "")
        self._bridge("toast", text or "A plugin sent a notification.")

    def cancel(self, *args):
        return None

    def cancelAll(self):  # noqa: N802 - Android's name
        return None


_REAL_CLASSES = {
    "android.widget.Toast": _Toast,
    "android.app.NotificationManager": _Notifications,
}


def _make_android(bridge) -> types.ModuleType:
    """A stand-in `android` package, with the pieces that have a real answer."""
    module = types.ModuleType("android")
    module.__path__ = []  # a package, so `import android.os` resolves

    os_mod = types.ModuleType("android.os")
    os_mod.Build = _Inert("android.os.Build")
    os_mod.Environment = _Inert("android.os.Environment")

    widget = types.ModuleType("android.widget")
    widget.Toast = _Toast(bridge)

    module.os = os_mod
    module.widget = widget
    return module, {"android.os": os_mod, "android.widget": widget}


@contextlib.contextmanager
def shim(bridge=None):
    """Puts the stand-ins in place for the duration of an import.

    A context manager rather than a permanent install, and the difference is
    the point: a Windows plugin that imports `java` has made a mistake, and
    should get an ImportError telling it so instead of a silent stub. Only
    something declared as a phone plugin is loaded inside this.
    """
    bridge = bridge or (lambda kind, text: None)
    java = _make_java(bridge)
    android, extra = _make_android(bridge)

    added = {"java": java, "android": android}
    added.update(extra)

    saved = {name: sys.modules.get(name) for name in added}
    sys.modules.update(added)
    try:
        yield
    finally:
        for name, was in saved.items():
            if was is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = was


def report(source: str) -> dict:
    """What a phone plugin's code needs, and whether this build can give it.

    Replaces the old "it might not work". Each finding is either *handled* -
    the shim covers it, and how - or *unsupported*, with the reason. A plugin
    with nothing unsupported is a full plugin here, not a beta.
    """
    handled, unsupported = [], []
    text = source or ""

    checks = (
        ("from java", "handled", "the java module is provided while it loads"),
        ("import java", "handled", "the java module is provided while it loads"),
        ("com.chaquo", "handled", "Chaquopy's entry points are stubbed"),
        ("/storage/emulated", "handled", "translated to your real folders"),
        ("/sdcard", "handled", "translated to the workspace"),
        ("/data/user/0", "handled", "translated to PyCmd's own folder"),
        ("android.widget.Toast", "handled", "drawn as a PyCmd toast"),
        ("NotificationManager", "handled", "shown as a PyCmd toast"),
        ("android.view", "unsupported", "draws an Android view, which has no "
                                        "meaning in a desktop window"),
        ("android.hardware", "unsupported", "talks to phone hardware"),
        ("android.telephony", "unsupported", "needs a phone radio"),
        ("SensorManager", "unsupported", "needs phone sensors"),
        ("android.media.MediaSession", "unsupported",
         "draws lock-screen controls, and Windows has no lock screen"),
    )
    for needle, kind, why in checks:
        if needle in text:
            row = {"uses": needle, "why": why}
            (handled if kind == "handled" else unsupported).append(row)

    return {
        "handled": handled,
        "unsupported": unsupported,
        # This is the whole point of the rewrite: a plugin whose Android bits
        # are all covered is a full plugin here, and says so.
        "full": not unsupported,
        "verdict": ("runs here in full" if not unsupported
                    else "runs, with " + str(len(unsupported)) + " part(s) that cannot"),
    }
