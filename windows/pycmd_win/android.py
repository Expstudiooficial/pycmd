"""Android Lab - running Android things on this PC, and PyCmd Android on them.

**What this is, and what it is not.** PyCmd.exe is fifteen megabytes. An
Android emulator is not: a system image alone is two to three gigabytes, the
emulator engine is another few hundred megabytes, and both are Google's,
shipped under their own licence, and updated on their own schedule. Nothing
that fits in this exe can *be* an emulator, and a version of this file that
claimed to would be lying to you and downloading four gigabytes behind a
button that said "Start".

What PyCmd can honestly do is drive one. Everything below is orchestration:
finding the Android tools if they are here, installing them if they are not
(through the same package managers that install every other toolchain),
creating a virtual device with the memory and disk asked for, starting it,
and putting the PyCmd APK on it. That is the part that is genuinely tedious to
do by hand - six command-line tools, an SDK layout nobody remembers, and an
`avdmanager` that asks interactive questions - and it is the part worth
automating.

So the button is real. It is a button that sets up and starts a real Android
device on this machine, with PyCmd Android already installed on it. It is not
a button that pretends fifteen megabytes contains Android.

**The machine it builds.** 4 GB of RAM and 10 GB of storage, as asked, on
x86_64 - which is the important choice: an ARM image on an x86 PC has to
translate every instruction and is unusably slow, while an x86_64 image runs
on the CPU directly through hardware acceleration and is genuinely quick.
Google's own `google_apis` image is used rather than the bare AOSP one,
because half of what people want to run expects Play services to at least
exist.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time

from . import install, store

WINDOWS = os.name == "nt"

# The device PyCmd builds. Named so it is obviously ours and obviously safe to
# delete - anybody looking at a list of AVDs should be able to tell.
AVD_NAME = "PyCmd_Lab"
RAM_MB = 4096
STORAGE_MB = 10240
# Heap per app. The default is 256 MB and is the usual reason a big app dies
# on an emulator that has plenty of RAM.
HEAP_MB = 512

IMAGE = "system-images;android-34;google_apis;x86_64"
DEVICE = "pixel_6"

# Where Google puts the SDK by default, and where it looks for it.
SDK_ENV = ("ANDROID_HOME", "ANDROID_SDK_ROOT")

BOOT_TIMEOUT = 420.0
STEP_TIMEOUT = 900.0


def sdk_root() -> str:
    """Where the Android SDK is, or "" if it is not anywhere obvious."""
    for name in SDK_ENV:
        value = os.environ.get(name, "").strip()
        if value and os.path.isdir(value):
            return os.path.abspath(value)
    guesses = []
    if WINDOWS:
        local = os.environ.get("LOCALAPPDATA")
        if local:
            guesses.append(os.path.join(local, "Android", "Sdk"))
        for key in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(key)
            if base:
                guesses.append(os.path.join(base, "Android", "android-sdk"))
    guesses.append(os.path.expanduser("~/Android/Sdk"))
    guesses.append(os.path.expanduser("~/Library/Android/sdk"))
    for path in guesses:
        if os.path.isdir(path):
            return os.path.abspath(path)
    return ""


def _tool(name: str) -> str:
    """One SDK program, looked for in the SDK first and the PATH second."""
    exe = name + (".exe" if WINDOWS else "")
    bat = name + (".bat" if WINDOWS else "")
    root = sdk_root()
    if root:
        wheres = [
            os.path.join(root, "platform-tools", exe),
            os.path.join(root, "emulator", exe),
            os.path.join(root, "cmdline-tools", "latest", "bin", bat),
            os.path.join(root, "cmdline-tools", "latest", "bin", exe),
            os.path.join(root, "tools", "bin", bat),
        ]
        for where in wheres:
            if os.path.isfile(where):
                return where
    return shutil.which(name) or ""


def tools() -> dict:
    """What is here, and what is missing."""
    found = {name: _tool(name) for name in
             ("adb", "emulator", "avdmanager", "sdkmanager")}
    return {
        "sdk": sdk_root(),
        "tools": found,
        "ready": bool(found["adb"] and found["emulator"] and found["avdmanager"]),
        "missing": [name for name, where in found.items() if not where],
    }


def _no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0


def _run(command, write, timeout=STEP_TIMEOUT, feed: str = "") -> tuple:
    """One SDK command, bounded, streaming.

    Same daemon-reader shape as everywhere else in this app, and needed here
    more than anywhere: `sdkmanager` is a batch file that starts a JVM, which
    is exactly the grandchild-holds-the-pipe case that makes
    `subprocess.run(timeout=)` hang for ever.
    """
    write("$ " + " ".join(str(part) for part in command) + "\n")
    try:
        process = subprocess.Popen(
            [str(part) for part in command],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE if feed else subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace",
            creationflags=_no_window(),
        )
    except FileNotFoundError:
        return False, f"{command[0]} is not here"
    except OSError as error:
        return False, f"could not start {command[0]}: {error}"

    if feed:
        try:
            process.stdin.write(feed)
            process.stdin.flush()
            process.stdin.close()
        except OSError:
            pass

    collected = []

    def read():
        try:
            for line in process.stdout:
                collected.append(line)
                write(line)
        except Exception:  # noqa: BLE001
            pass

    reader = threading.Thread(target=read, name="pycmd-android", daemon=True)
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


def plan() -> dict:
    """What starting the lab would need, said before anything is downloaded.

    A four gigabyte download should never begin because somebody pressed a
    button that only said "Start".
    """
    state = tools()
    steps = []
    if not state["sdk"]:
        steps.append({
            "what": "Install the Android command-line tools",
            "why": "There is no Android SDK on this machine yet.",
            "size": "about 150 MB",
            "how": "scoop install android-clt, or Android Studio",
        })
    if state["sdk"] and state["missing"]:
        steps.append({
            "what": "Add the emulator and platform tools",
            "why": "The SDK is here but " + ", ".join(state["missing"]) + " is not.",
            "size": "about 400 MB",
            "how": "sdkmanager platform-tools emulator",
        })
    steps.append({
        "what": "Download the Android 14 system image",
        "why": "This is Android itself - the operating system the device runs.",
        "size": "about 2.5 GB, once",
        "how": "sdkmanager " + IMAGE,
    })
    steps.append({
        "what": f"Create the {AVD_NAME} device",
        "why": f"{RAM_MB // 1024} GB of RAM, {STORAGE_MB // 1024} GB of storage, "
               "x86_64 so it runs at full speed.",
        "size": "nothing to download",
        "how": f"avdmanager create avd -n {AVD_NAME}",
    })
    steps.append({
        "what": "Start it, and install PyCmd Android on it",
        "why": "The APK from the phone build's own release.",
        "size": "about 30 MB",
        "how": "emulator -avd, then adb install",
    })

    total_gb = 3.1 if not state["ready"] else 2.5
    return {
        "ok": True,
        "ready": state["ready"],
        "sdk": state["sdk"],
        "missing": state["missing"],
        "steps": steps,
        "download": f"about {total_gb:.1f} GB the first time, nothing after that",
        "device": {"name": AVD_NAME, "ramMb": RAM_MB, "storageMb": STORAGE_MB,
                   "heapMb": HEAP_MB, "image": IMAGE, "arch": "x86_64"},
        "honest": (
            "PyCmd does not contain Android and cannot - the exe is 15 MB and "
            "a system image is 2.5 GB. What it does is set up and drive "
            "Google's own emulator for you, which is the tedious part. "
            "Everything downloaded comes from Google, under their licence."
        ),
    }


def avds(write=None) -> list:
    """Which virtual devices already exist."""
    manager = _tool("avdmanager")
    if not manager:
        return []
    ok, output = _run([manager, "list", "avd", "-c"], write or (lambda t: None), 120)
    if not ok:
        return []
    return [line.strip() for line in output.splitlines()
            if line.strip() and not line.startswith(("Loading", "Parsing", "["))]


def running(write=None) -> list:
    """Which emulators are up right now."""
    adb = _tool("adb")
    if not adb:
        return []
    ok, output = _run([adb, "devices"], write or (lambda t: None), 60)
    if not ok:
        return []
    found = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            found.append(parts[0])
    return found


def state() -> dict:
    """Everything a screen needs to draw itself."""
    have = tools()
    return {
        "ok": True,
        "sdk": have["sdk"],
        "ready": have["ready"],
        "missing": have["missing"],
        "tools": have["tools"],
        "avds": avds() if have["ready"] else [],
        "hasOurs": AVD_NAME in (avds() if have["ready"] else []),
        "running": running() if have["tools"].get("adb") else [],
        "device": {"name": AVD_NAME, "ramMb": RAM_MB, "storageMb": STORAGE_MB},
    }


def ensure_sdk(write) -> bool:
    """Puts the Android command-line tools on the machine if they are missing."""
    if sdk_root() and _tool("sdkmanager"):
        return True
    write("[PyCmd] no Android SDK here yet - installing the command-line tools.\n")
    # Through the same machinery as every other toolchain, so it inherits the
    # package-manager bootstrapping and the fallbacks.
    for manager_id in install.PREFERENCE:
        if not install.find(manager_id):
            continue
        manager = install._BY_ID[manager_id]
        package = {"scoop": "android-clt", "choco": "android-sdk",
                   "winget": "Google.AndroidStudio"}.get(manager_id)
        if not package:
            continue
        command = [manager.program] + [
            part.format(package=package) for part in manager.install_verb]
        ok, _ = _run(command, write, STEP_TIMEOUT)
        if ok and _tool("sdkmanager"):
            return True
    if not any(install.find(m) for m in install.PREFERENCE):
        write("[PyCmd] there is no package manager here to install it with. "
              "Setting Scoop up first.\n")
        if install.bootstrap("scoop", write).get("ok"):
            return ensure_sdk(write)
    write("[PyCmd] could not install the Android tools automatically. "
          "Android Studio includes them: https://developer.android.com/studio\n")
    return False


def ensure_image(write) -> bool:
    """Downloads Android itself. This is the 2.5 GB step."""
    manager = _tool("sdkmanager")
    if not manager:
        return False
    write(f"[PyCmd] making sure {IMAGE} is here. This is the big one - "
          "about 2.5 GB, once.\n")
    # sdkmanager asks about licences on stdin and waits for ever if nobody
    # answers. Feeding it agreement is the documented non-interactive route.
    ok, _ = _run([manager, "--install", "platform-tools", "emulator", IMAGE],
                 write, STEP_TIMEOUT, feed="y\n" * 20)
    return ok


def ensure_avd(write) -> bool:
    """Creates the device, with the memory and disk that were asked for."""
    if AVD_NAME in avds(write):
        write(f"[PyCmd] {AVD_NAME} already exists.\n")
        return True
    manager = _tool("avdmanager")
    if not manager:
        return False
    write(f"[PyCmd] creating {AVD_NAME}: {RAM_MB // 1024} GB RAM, "
          f"{STORAGE_MB // 1024} GB storage, x86_64.\n")
    ok, _ = _run([manager, "create", "avd", "-n", AVD_NAME, "-k", IMAGE,
                  "-d", DEVICE, "--force"], write, 300, feed="no\n")
    if not ok:
        return False

    # avdmanager writes a config with the device's defaults; the memory and
    # disk asked for have to be set afterwards, which is the part that is
    # genuinely obscure to do by hand.
    config = os.path.join(os.path.expanduser("~"), ".android", "avd",
                          AVD_NAME + ".avd", "config.ini")
    if os.path.isfile(config):
        try:
            with open(config, "r", encoding="utf-8") as handle:
                lines = [line for line in handle
                         if not line.startswith(("hw.ramSize", "disk.dataPartition.size",
                                                 "vm.heapSize", "hw.gpu.enabled",
                                                 "hw.gpu.mode"))]
            lines += [
                f"hw.ramSize={RAM_MB}\n",
                f"disk.dataPartition.size={STORAGE_MB}M\n",
                f"vm.heapSize={HEAP_MB}\n",
                "hw.gpu.enabled=yes\n",
                "hw.gpu.mode=auto\n",
            ]
            with open(config, "w", encoding="utf-8") as handle:
                handle.writelines(lines)
            write(f"[PyCmd] set {RAM_MB} MB RAM and {STORAGE_MB} MB storage.\n")
        except OSError as error:
            write(f"[PyCmd] could not adjust the device config: {error}\n")
    return True


def boot(write) -> dict:
    """Starts the device and waits for Android to finish coming up."""
    emulator = _tool("emulator")
    adb = _tool("adb")
    if not emulator or not adb:
        return {"ok": False, "error": "the emulator or adb is missing"}

    already = running(write)
    if already:
        write(f"[PyCmd] a device is already up: {already[0]}\n")
        return {"ok": True, "serial": already[0], "already": True}

    write(f"[PyCmd] starting {AVD_NAME}. First boot takes a few minutes.\n")
    try:
        subprocess.Popen(
            [emulator, "-avd", AVD_NAME, "-memory", str(RAM_MB),
             "-gpu", "auto", "-no-snapshot-load"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, creationflags=_no_window(),
        )
    except OSError as error:
        return {"ok": False, "error": f"could not start the emulator: {error}"}

    # Polled rather than `adb wait-for-device`, so this can report progress and
    # give up on its own terms.
    deadline = time.time() + BOOT_TIMEOUT
    said = 0
    while time.time() < deadline:
        found = running()
        if found:
            ok, output = _run([adb, "-s", found[0], "shell",
                               "getprop", "sys.boot_completed"], lambda t: None, 30)
            if ok and "1" in output:
                write(f"[PyCmd] {found[0]} is up.\n")
                return {"ok": True, "serial": found[0]}
        if time.time() - said > 20:
            said = time.time()
            write("[PyCmd] still booting...\n")
        time.sleep(3)
    return {"ok": False, "error": "the device did not finish booting in seven minutes"}


def install_apk(serial: str, apk: str, write) -> dict:
    """Puts PyCmd Android onto the running device."""
    adb = _tool("adb")
    if not adb:
        return {"ok": False, "error": "adb is missing"}
    if not os.path.isfile(apk):
        return {"ok": False, "error": f"there is no APK at {apk}"}
    write(f"[PyCmd] installing {os.path.basename(apk)} onto {serial}.\n")
    ok, output = _run([adb, "-s", serial, "install", "-r", apk], write, 600)
    if not ok:
        return {"ok": False, "error": output.strip()[-300:]}
    return {"ok": True}


# ---------------------------------------------------------------------------
# The whole thing, as one long job
# ---------------------------------------------------------------------------

class Job:
    def __init__(self):
        self.lines: list = []
        self.step = ""
        self.finished = 0.0
        self.ok = False
        self.error = ""
        self.serial = ""
        self.started = time.time()
        self._lock = threading.RLock()

    def write(self, text: str) -> None:
        with self._lock:
            self.lines.append(text)
            if len(self.lines) > 4000:
                del self.lines[:2000]

    def drain(self) -> list:
        with self._lock:
            out, self.lines = self.lines, []
            return out

    def as_dict(self) -> dict:
        return {"running": not self.finished, "step": self.step, "ok": self.ok,
                "error": self.error, "serial": self.serial,
                "seconds": int((self.finished or time.time()) - self.started)}


_job: Job | None = None
_job_lock = threading.RLock()


def job_state() -> dict:
    with _job_lock:
        if _job is None:
            return {"running": False, "everStarted": False}
        data = _job.as_dict()
        data["everStarted"] = True
        return data


def job_lines() -> list:
    with _job_lock:
        return _job.drain() if _job is not None else []


def start(apk: str = "") -> dict:
    """Sets everything up and boots the device. Long; runs on its own thread."""
    global _job
    with _job_lock:
        if _job is not None and not _job.finished:
            return {"ok": False, "reason": "already-running",
                    "error": "the lab is already starting"}
        _job = Job()
        job = _job

    def work():
        try:
            job.step = "tools"
            if not ensure_sdk(job.write):
                job.error = "the Android SDK could not be installed"
                return
            job.step = "image"
            if not ensure_image(job.write):
                job.error = "the Android system image could not be downloaded"
                return
            job.step = "device"
            if not ensure_avd(job.write):
                job.error = "the virtual device could not be created"
                return
            job.step = "boot"
            booted = boot(job.write)
            if not booted.get("ok"):
                job.error = booted.get("error", "it would not boot")
                return
            job.serial = booted["serial"]
            if apk and os.path.isfile(apk):
                job.step = "apk"
                got = install_apk(job.serial, apk, job.write)
                if not got.get("ok"):
                    job.write(f"[PyCmd] the APK did not install: {got.get('error')}\n")
                    job.write("[PyCmd] the device is up anyway.\n")
            job.ok = True
            job.write("[PyCmd] Android Lab is ready.\n")
        except Exception as error:  # noqa: BLE001
            import traceback

            job.error = f"{type(error).__name__}: {error}"
            job.write(traceback.format_exc())
        finally:
            job.step = ""
            job.finished = time.time()

    threading.Thread(target=work, name="pycmd-android-lab", daemon=True).start()
    return {"ok": True, "started": True}


def shutdown(write=None) -> dict:
    """Turns the device off."""
    write = write or (lambda text: None)
    adb = _tool("adb")
    if not adb:
        return {"ok": False, "error": "adb is missing"}
    stopped = []
    for serial in running(write):
        _run([adb, "-s", serial, "emu", "kill"], write, 60)
        stopped.append(serial)
    return {"ok": True, "stopped": stopped}
