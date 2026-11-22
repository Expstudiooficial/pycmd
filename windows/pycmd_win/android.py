"""Android Lab - a real Android device on this PC, with PyCmd Android on it.

PyCmd.exe cannot contain Android: a system image is two to three gigabytes
and the emulator is Google's, under Google's licence. What PyCmd does is
drive Google's own emulator and do the tedious part of setting it up - which
is exactly where the old version of this file fell over on most machines.
One fix per thing that used to go wrong:

* **No package manager.** The SDK used to come from scoop's `android-clt`
  (in a bucket a fresh scoop does not have), winget's Android Studio (the IDE,
  with no SDK until you open it) or choco's `android-sdk` (abandoned years
  ago). Now the command-line tools come straight from Google's repository
  index, checked against the SHA-1 Google publishes, into PyCmd's folder.
* **Java.** sdkmanager and avdmanager are Java programs and need Java 17 or
  newer. Nothing checked, so they died with "JAVA_HOME is not set" or a
  class-version error. Now PyCmd finds a new enough Java - yours, Android
  Studio's, or its own - and installs Temurin 21 portably if there is none.
* **Telling the tools where the SDK is.** Every SDK command gets
  `--sdk_root`, and the environment gets ANDROID_HOME, ANDROID_SDK_ROOT,
  ANDROID_AVD_HOME and JAVA_HOME, so the emulator finds its images instead of
  reporting a "broken AVD system path".
* **Licences** are accepted first, so the big download never stalls at a
  question nobody can see.
* **Hardware acceleration.** Without Windows Hypervisor Platform or Google's
  hypervisor driver the emulator exits at once, while the old screen waited
  seven minutes for a device that was already gone. `emulator -accel-check`
  now runs first, says what is missing, and the screen offers the fix.
* **Watching the emulator.** Its output goes to a log file; if it exits
  before Android is up, the job stops and shows its last words.
* **Our device, not your phone.** The lab device is the emulator this job
  started, on a port it chose. A phone on USB is listed separately and never
  mistaken for it.
* **Actually installing PyCmd.** The screen started the job without an APK,
  so PyCmd was never installed. Now the APK comes from the Android build's
  own release manifest, is checked against its SHA-256, installed, and opened.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
import os
import platform
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ElementTree

from . import envpath, fetch, portable, store

WINDOWS = os.name == "nt"

AVD_NAME = "PyCmd_Lab"
DEVICE = "pixel_6"
PACKAGE = "com.expstudio.pycmd.debug"

REPOSITORY = "https://dl.google.com/android/repository/"
REPOSITORY_INDEX = REPOSITORY + "repository2-3.xml"
APK_MANIFEST = ("https://raw.githubusercontent.com/expstudiooficial/pycmd/"
                "claude/python-mobile-cmd-android-dj1ixb/dist/latest.json")

# Android versions the lab can build, newest first: API level, name, image tag.
# google_apis rather than bare AOSP, because many apps expect Play services.
ANDROIDS = (
    (36, "Android 16", "google_apis"),
    (35, "Android 15", "google_apis"),
    (34, "Android 14", "google_apis"),
    (33, "Android 13", "google_apis"),
)

DEFAULTS = {
    "api": 35,
    "ramMb": 4096,
    "storageMb": 10240,
    "cores": 4,
    "heapMb": 512,
    "gpu": "auto",
    "coldBoot": False,
    "installApk": True,
    "openApk": True,
}

LIMITS = {"ramMb": (1536, 16384), "storageMb": (4096, 65536), "cores": (1, 16),
          "heapMb": (128, 1024)}
GPU_MODES = ("auto", "host", "swiftshader_indirect", "angle_indirect")

BOOT_TIMEOUT = 600.0
IMAGE_TIMEOUT = 2 * 60 * 60.0
IMAGE_STALL = 20 * 60.0
STEP_TIMEOUT = 20 * 60.0


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def config() -> dict:
    saved = store.settings().get("android", {})
    out = dict(DEFAULTS)
    if isinstance(saved, dict):
        for key, value in saved.items():
            if key in DEFAULTS and type(value) is type(DEFAULTS[key]):
                out[key] = value
    if out["api"] not in [a[0] for a in ANDROIDS]:
        out["api"] = DEFAULTS["api"]
    for key, (low, high) in LIMITS.items():
        out[key] = max(low, min(high, int(out[key])))
    if out["gpu"] not in GPU_MODES:
        out["gpu"] = "auto"
    return out


def set_config(changes: dict) -> dict:
    current = config()
    for key, value in (changes or {}).items():
        if key not in DEFAULTS:
            continue
        kind = type(DEFAULTS[key])
        try:
            current[key] = bool(value) if kind is bool else kind(value)
        except (TypeError, ValueError):
            return {"ok": False, "error": f"{key} has to be a {kind.__name__}"}
    data = store.settings()
    data["android"] = current
    store.save_settings(data)
    return {"ok": True, "config": config()}


def _abi() -> str:
    machine = platform.machine().lower()
    return "arm64-v8a" if machine in ("arm64", "aarch64") else "x86_64"


def image_for(api: int) -> str:
    tag = next((a[2] for a in ANDROIDS if a[0] == api), "google_apis")
    return f"system-images;android-{api};{tag};{_abi()}"


def android_name(api: int) -> str:
    return next((a[1] for a in ANDROIDS if a[0] == api), f"API {api}")


# ---------------------------------------------------------------------------
# Where things are
# ---------------------------------------------------------------------------

def _own_sdk() -> str:
    return os.path.join(store.folder("android"), "sdk")


def _existing_sdks() -> list:
    found = [os.environ.get(name, "").strip() for name in ("ANDROID_HOME", "ANDROID_SDK_ROOT")]
    if WINDOWS:
        local = os.environ.get("LOCALAPPDATA")
        if local:
            found.append(os.path.join(local, "Android", "Sdk"))
    else:
        found.append(os.path.expanduser("~/Android/Sdk"))
        found.append(os.path.expanduser("~/Library/Android/sdk"))
    return [f for f in found if f]


def _find_in(root: str, name: str) -> str:
    exe = name + (".exe" if WINDOWS else "")
    bat = name + (".bat" if WINDOWS else "")
    places = [
        os.path.join(root, "platform-tools", exe),
        os.path.join(root, "emulator", exe),
        os.path.join(root, "cmdline-tools", "latest", "bin", bat),
    ]
    tools_dir = os.path.join(root, "cmdline-tools")
    if os.path.isdir(tools_dir):
        for version in sorted(os.listdir(tools_dir), reverse=True):
            places.append(os.path.join(tools_dir, version, "bin", bat))
    for place in places:
        if os.path.isfile(place):
            return place
    return ""


def _has_cmdline_tools(root: str) -> bool:
    return bool(root) and bool(_find_in(root, "sdkmanager"))


def sdk_root() -> str:
    """The SDK to use: one already here with the tools in it, or PyCmd's own.

    An SDK Android Studio made is used as it is - packages are added, nothing
    removed - so there is one set of images on the disk, not two. A folder
    with no command-line tools is not good enough, because nothing can be
    installed into it; PyCmd's own is used then.
    """
    own = _own_sdk()
    if _has_cmdline_tools(own):
        return own
    for candidate in _existing_sdks():
        if os.path.isdir(candidate) and _has_cmdline_tools(candidate):
            return os.path.abspath(candidate)
    return own


def _tool(name: str) -> str:
    return _find_in(sdk_root(), name)


def avd_home() -> str:
    """Where virtual devices live.

    ~/.android/avd by default, which Android Studio reads too. The emulator
    cannot cope with a path that is not plain ASCII - a Windows account named
    José gets "unknown AVD" for ever - so for those profiles the devices go in
    a folder at the top of the system drive.
    """
    override = os.environ.get("ANDROID_AVD_HOME", "").strip()
    if override:
        return override
    default = os.path.join(os.path.expanduser("~"), ".android", "avd")
    if default.isascii():
        return default
    drive = os.environ.get("SystemDrive", "C:") if WINDOWS else "/tmp"
    return os.path.join(drive + os.sep, "PyCmdAndroid", "avd")


# ---------------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------------

_JAVA_VERSION = re.compile(r'version "(\d+)(?:\.(\d+))?')


def _no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0


def _java_major(java: str) -> int:
    try:
        done = subprocess.run([java, "-version"], capture_output=True, text=True,
                              timeout=30, creationflags=_no_window())
    except (OSError, subprocess.SubprocessError):
        return 0
    match = _JAVA_VERSION.search(done.stderr + done.stdout)
    if not match:
        return 0
    major = int(match.group(1))
    return int(match.group(2) or 0) if major == 1 else major


def _java_in(home: str) -> str:
    candidate = os.path.join(home, "bin", "java" + (".exe" if WINDOWS else ""))
    return candidate if os.path.isfile(candidate) else ""


def java_home() -> tuple:
    """A Java new enough for the SDK tools: (JAVA_HOME, major), or ("", 0)."""
    homes = []
    if os.environ.get("JAVA_HOME"):
        homes.append(os.environ["JAVA_HOME"])
    homes.append(portable.folder("jdk"))
    if WINDOWS:
        for base in (os.environ.get("ProgramFiles", ""), os.environ.get("LOCALAPPDATA", "")):
            if base:
                homes.append(os.path.join(base, "Android", "Android Studio", "jbr"))
                homes.append(os.path.join(base, "Programs", "Android Studio", "jbr"))
    for home in homes:
        java = _java_in(home)
        if java:
            major = _java_major(java)
            if major >= 17:
                return home, major
    on_path = shutil.which("java")
    if on_path:
        major = _java_major(on_path)
        if major >= 17:
            return os.path.dirname(os.path.dirname(os.path.realpath(on_path))), major
    return "", 0


def _env(sdk: str = "", java: str = "") -> dict:
    env = dict(os.environ)
    sdk = sdk or sdk_root()
    env["ANDROID_HOME"] = sdk
    env["ANDROID_SDK_ROOT"] = sdk
    env["ANDROID_AVD_HOME"] = avd_home()
    java = java or java_home()[0]
    if java:
        env["JAVA_HOME"] = java
        env["PATH"] = os.path.join(java, "bin") + os.pathsep + env.get("PATH", "")
    return env


# ---------------------------------------------------------------------------
# Running SDK programs
# ---------------------------------------------------------------------------

_PERCENT = re.compile(r"(\d{1,3})%")


def _run(command, write, timeout=STEP_TIMEOUT, feed="", env=None, stall=0.0,
         progress=None, cancelled=None) -> tuple:
    """One SDK command: bounded, streaming, stoppable.

    sdkmanager draws its progress bar with carriage returns, which text mode
    turns into lines - thousands of them. A bar line is passed on only when
    its number moves by five, and the number goes to `progress` for the bar.
    """
    shown = [str(part) for part in command]
    write("$ " + " ".join(shown) + "\n")
    try:
        process = subprocess.Popen(
            shown, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE if feed else subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", env=env,
            creationflags=_no_window(),
        )
    except FileNotFoundError:
        return False, f"{command[0]} is not here"
    except OSError as error:
        return False, f"could not start {command[0]}: {error}"

    if feed:
        def feeder():
            try:
                process.stdin.write(feed)
                process.stdin.flush()
                process.stdin.close()
            except OSError:
                pass
        threading.Thread(target=feeder, daemon=True).start()

    collected = []
    last_line = [time.time()]
    last_percent = [-10]

    def read():
        try:
            for line in process.stdout:
                last_line[0] = time.time()
                collected.append(line)
                if len(collected) > 5000:
                    del collected[:2500]
                match = _PERCENT.search(line)
                if match and "[" in line and len(line.strip()) < 160:
                    percent = int(match.group(1))
                    if progress:
                        progress(percent)
                    if percent - last_percent[0] >= 5 or percent == 100:
                        last_percent[0] = percent
                        write(line.strip() + "\n")
                    continue
                if line.strip():
                    write(line if line.endswith("\n") else line + "\n")
        except Exception:  # noqa: BLE001
            pass

    reader = threading.Thread(target=read, name="pycmd-android", daemon=True)
    reader.start()
    started = time.time()
    while reader.is_alive():
        reader.join(1.0)
        now = time.time()
        if cancelled and cancelled():
            _kill(process)
            return False, "stopped"
        if now - started > timeout:
            _kill(process)
            return False, "it did not finish in time"
        if stall and now - last_line[0] > stall:
            _kill(process)
            return False, f"it said nothing for {int(stall // 60)} minutes"
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


def _quiet(command, timeout=60, env=None) -> tuple:
    try:
        done = subprocess.run([str(c) for c in command], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout, env=env,
                              creationflags=_no_window())
    except (OSError, subprocess.SubprocessError) as error:
        return False, str(error)
    return done.returncode == 0, (done.stdout or "") + (done.stderr or "")


@contextmanager
def _sdk_package_file(packages):
    """Writes SDK package IDs without passing semicolons through a .bat file."""
    path = ""
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", delete=False,
                dir=store.folder("android"), prefix="sdk-packages-", suffix=".txt") as handle:
            path = handle.name
            handle.write("\n".join(packages) + "\n")
        yield path
    finally:
        if path:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------------------
# The command-line tools, straight from Google
# ---------------------------------------------------------------------------

def _host_os() -> str:
    if WINDOWS:
        return "windows"
    return "macosx" if platform.system() == "Darwin" else "linux"


def cmdline_tools_plan(index_xml: str = "", host_os: str = "") -> dict:
    """The newest stable command-line tools for this OS, from Google's index."""
    host_os = host_os or _host_os()
    root = ElementTree.fromstring(index_xml or fetch.text(REPOSITORY_INDEX))
    best = None
    for package in root.iter("remotePackage"):
        path = package.get("path", "")
        if not path.startswith("cmdline-tools;") or package.get("obsolete") == "true":
            continue
        version = path.split(";", 1)[1]
        if not re.fullmatch(r"\d+(\.\d+)*", version):
            continue  # "latest", alphas and release candidates
        channel = package.find("channelRef")
        if channel is not None and channel.get("ref") not in (None, "channel-0"):
            continue
        for archive in package.iter("archive"):
            if archive.findtext("host-os") != host_os:
                continue
            complete = archive.find("complete")
            checksum = complete.find("checksum")
            key = tuple(int(p) for p in version.split("."))
            if best is None or key > best[0]:
                best = (key, version, complete.findtext("url"),
                        checksum.text if checksum is not None else "",
                        int(complete.findtext("size") or 0))
    if best is None:
        raise fetch.FetchError("Google's index has no command-line tools for this system")
    _key, version, url, sha1, size = best
    if not url.startswith("http"):
        url = REPOSITORY + url
    return {"version": version, "url": url, "sha1": sha1, "size": size}


def ensure_cmdline_tools(write, cancelled=None) -> bool:
    if _has_cmdline_tools(sdk_root()):
        return True
    root = _own_sdk()
    write("[PyCmd] no Android command-line tools here yet - fetching them from Google.\n")
    try:
        plan = cmdline_tools_plan()
        write(f"[PyCmd] command-line tools {plan['version']} ({fetch.readable(plan['size'])}).\n")
        archive = fetch.download(
            plan["url"], os.path.join(store.folder("downloads"), plan["url"].rsplit("/", 1)[-1]),
            write, sha1=plan["sha1"], cancelled=cancelled)
        fetch.unpack(archive, os.path.join(root, "cmdline-tools", "latest"),
                     strip_top=True, write=write)
        try:
            os.remove(archive)
        except OSError:
            pass
    except fetch.FetchError as error:
        write(f"[PyCmd] {error}\n")
        return False
    if not WINDOWS:
        for name in ("sdkmanager", "avdmanager"):
            path = os.path.join(root, "cmdline-tools", "latest", "bin", name)
            if os.path.isfile(path):
                os.chmod(path, 0o755)
    return _has_cmdline_tools(root)


def ensure_java(write, cancelled=None) -> str:
    home, major = java_home()
    if home:
        write(f"[PyCmd] Java {major} at {home}.\n")
        return home
    write("[PyCmd] the Android tools need Java 17 or newer and there is none here. "
          "Installing Temurin 21 into PyCmd's folder - no administrator needed.\n")
    got = portable.install("jdk", write, cancelled)
    if not got.get("ok"):
        write(f"[PyCmd] Java could not be installed: {got.get('error')}\n")
        return ""
    return java_home()[0]


def _sdk_folders(root: str) -> list:
    return envpath.ensure(
        os.path.join(root, "platform-tools"),
        os.path.join(root, "emulator"),
        os.path.join(root, "cmdline-tools", "latest", "bin"),
    )


def accept_licences(write, java: str) -> bool:
    root = sdk_root()
    ok, output = _run([_tool("sdkmanager"), f"--sdk_root={root}", "--licenses"], write, 300,
                      feed="y\n" * 60, env=_env(root, java))
    return ok or "licenses accepted" in output.lower()


def installed_packages(root: str) -> set:
    """What is in the SDK, from the package.xml files sdkmanager leaves behind.

    Reading them is instant; asking sdkmanager is a JVM start and five seconds.
    """
    found = set()
    if not root or not os.path.isdir(root):
        return found
    for directory, folders, names in os.walk(root):
        if os.path.relpath(directory, root).count(os.sep) > 4:
            folders[:] = []
            continue
        if "package.xml" in names:
            try:
                tree = ElementTree.parse(os.path.join(directory, "package.xml"))
                for node in tree.getroot().iter("localPackage"):
                    found.add(node.get("path", ""))
            except (ElementTree.ParseError, OSError):
                pass
            folders[:] = []
    return found


def ensure_packages(write, java: str, api: int, job=None) -> bool:
    """platform-tools, the emulator, and Android itself - the 2.5 GB step."""
    root = sdk_root()
    wanted = ["platform-tools", "emulator", f"platforms;android-{api}", image_for(api)]
    missing = [p for p in wanted if p not in installed_packages(root)]
    if not missing:
        write(f"[PyCmd] {android_name(api)} and the emulator are already here.\n")
        return True
    write("[PyCmd] downloading " + ", ".join(missing) + ". The system image is about "
          "2.5 GB and is downloaded once.\n")
    # Package IDs contain semicolons. Passing them as positional arguments
    # through sdkmanager.bat makes the Windows CLI split them into separate
    # package names. Its package-file option preserves each full SDK path.
    with _sdk_package_file(missing) as package_file:
        ok, output = _run(
            [_tool("sdkmanager"), f"--sdk_root={root}",
             f"--package_file={package_file}"], write,
            IMAGE_TIMEOUT, feed="y\n" * 60, env=_env(root, java), stall=IMAGE_STALL,
            progress=(lambda p: setattr(job, "percent", p)) if job else None,
            cancelled=(lambda: job.cancel) if job else None)
    _sdk_folders(root)
    still = [p for p in wanted if p not in installed_packages(root)]
    if still:
        write("[PyCmd] still missing: " + ", ".join(still) + "\n")
        if "space" in output.lower():
            write("[PyCmd] the disk looks full - the image needs about 6 GB free while it "
                  "unpacks.\n")
        return False
    return True


# ---------------------------------------------------------------------------
# Hardware acceleration
# ---------------------------------------------------------------------------

def parse_accel(output: str, code_ok: bool) -> dict:
    """Reads `emulator -accel-check`: "accel:", a status number, a sentence, "accel"."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    status, message = None, output.strip()
    if "accel:" in lines:
        body = lines[lines.index("accel:") + 1:]
        if body and body[0].lstrip("-").isdigit():
            status = int(body[0])
            message = " ".join(line for line in body[1:] if line != "accel")
    usable = status == 0 or (status is None and code_ok)
    fix = ""
    if not usable:
        low = message.lower()
        if "vt-x" in low or "svm" in low or ("virtualization" in low and "bios" in low):
            fix = "bios"
        else:
            fix = "whpx"
    return {"ok": usable, "known": status is not None, "status": status,
            "message": message, "fix": fix}


def accel_check() -> dict:
    emulator = _tool("emulator")
    if not emulator:
        return {"ok": False, "known": False, "message": "the emulator is not installed yet",
                "fix": ""}
    ok, output = _quiet([emulator, "-accel-check"], 60, env=_env())
    return parse_accel(output, ok)


def fix_accel(how: str = "whpx") -> dict:
    """Turns on Windows Hypervisor Platform, or installs Google's driver. Asks for admin."""
    if not WINDOWS:
        return {"ok": False, "error": "this is a Windows setting"}
    if how == "aehd":
        root = sdk_root()
        script = os.path.join(root, "extras", "google", "Android_Emulator_Hypervisor_Driver",
                              "silent_install.bat")
        if not os.path.isfile(script):
            with _sdk_package_file(["extras;google;Android_Emulator_Hypervisor_Driver"]) as package_file:
                _quiet([_tool("sdkmanager"), f"--sdk_root={root}",
                        f"--package_file={package_file}"], 900, env=_env(root))
        if not os.path.isfile(script):
            return {"ok": False, "error": "the hypervisor driver could not be downloaded"}
        target, arguments = script, ""
    else:
        target = "dism.exe"
        arguments = "/online /enable-feature /featurename:HypervisorPlatform /all /norestart"
    command = ("Start-Process -FilePath '" + target.replace("'", "''") + "'"
               + (" -ArgumentList '" + arguments + "'" if arguments else "")
               + " -Verb RunAs -Wait")
    ok, output = _quiet(["powershell", "-NoProfile", "-Command", command], 900)
    if not ok:
        return {"ok": False, "error": "Windows did not let it run - the administrator "
                                      "prompt was probably closed. " + output.strip()[-200:]}
    if how == "aehd":
        return {"ok": True, "restart": False, "message": "The driver is installed."}
    return {"ok": True, "restart": True,
            "message": "Done. Restart Windows, then start the lab again."}


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

def avds() -> list:
    """Virtual devices, read from their .ini files - no JVM needed."""
    home = avd_home()
    if not os.path.isdir(home):
        return []
    return sorted(name[:-4] for name in os.listdir(home)
                  if name.endswith(".ini")
                  and os.path.isdir(os.path.join(home, name[:-4] + ".avd")))


def parse_devices(output: str) -> list:
    found = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2 or parts[0].startswith("*"):
            continue
        details = dict(part.split(":", 1) for part in parts[2:] if ":" in part)
        found.append({
            "serial": parts[0],
            "state": parts[1],
            "emulator": parts[0].startswith("emulator-"),
            "model": details.get("model", "").replace("_", " "),
            "ready": parts[1] == "device",
        })
    return found


def devices() -> list:
    """Everything adb can see - emulators and phones, each said for what it is."""
    adb = _tool("adb")
    if not adb:
        return []
    ok, output = _quiet([adb, "devices", "-l"], 30)
    return parse_devices(output) if ok else []


def running() -> list:
    return [d["serial"] for d in devices() if d["emulator"] and d["ready"]]


def _free_port() -> int:
    """An emulator console port nobody is using. The serial is emulator-<port>."""
    taken = set()
    for serial in running():
        tail = serial.split("-", 1)[1]
        if tail.isdigit():
            taken.add(int(tail))
    for port in range(5554, 5586, 2):
        if port in taken:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
        return port
    return 5554


def _avd_config(name: str) -> str:
    return os.path.join(avd_home(), name + ".avd", "config.ini")


def write_avd_config(name: str, settings: dict, write) -> bool:
    path = _avd_config(name)
    if not os.path.isfile(path):
        return False
    wanted = {
        "hw.ramSize": f"{settings['ramMb']}",
        "disk.dataPartition.size": f"{settings['storageMb']}M",
        "vm.heapSize": f"{settings['heapMb']}",
        "hw.cpu.ncore": f"{settings['cores']}",
        "hw.gpu.enabled": "yes",
        "hw.gpu.mode": settings["gpu"],
        "hw.keyboard": "yes",
    }
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = [line for line in handle if line.split("=", 1)[0].strip() not in wanted]
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines += [f"{key}={value}\n" for key, value in wanted.items()]
        with open(path, "w", encoding="utf-8") as handle:
            handle.writelines(lines)
    except OSError as error:
        write(f"[PyCmd] could not adjust the device config: {error}\n")
        return False
    write(f"[PyCmd] {name}: {settings['ramMb']} MB RAM, {settings['storageMb']} MB storage, "
          f"{settings['cores']} cores, GPU {settings['gpu']}.\n")
    return True


def _avd_image(name: str) -> str:
    try:
        with open(_avd_config(name), "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("image.sysdir.1"):
                    return line.split("=", 1)[1].strip().replace("\\", "/")
    except OSError:
        pass
    return ""


def ensure_avd(write, java: str, settings: dict) -> bool:
    image = image_for(settings["api"])
    if AVD_NAME in avds():
        current = _avd_image(AVD_NAME)
        if current and current.rstrip("/") != image.replace(";", "/"):
            write(f"[PyCmd] {AVD_NAME} was built for another Android version; rebuilding it.\n")
        else:
            write(f"[PyCmd] {AVD_NAME} already exists.\n")
            write_avd_config(AVD_NAME, settings, write)
            return True
    root = sdk_root()
    os.makedirs(avd_home(), exist_ok=True)
    write(f"[PyCmd] creating {AVD_NAME} with {android_name(settings['api'])}.\n")
    base = [_tool("avdmanager"), "create", "avd", "-n", AVD_NAME, "-k", image, "--force",
            "-p", os.path.join(avd_home(), AVD_NAME + ".avd")]
    ok, output = _run(base + ["-d", DEVICE], write, 300, feed="no\n", env=_env(root, java))
    if not ok and DEVICE in output:
        # An older avdmanager without that device profile: let it pick the default.
        ok, output = _run(base, write, 300, feed="no\n", env=_env(root, java))
    if not ok:
        return False
    write_avd_config(AVD_NAME, settings, write)
    return True


def delete_avd() -> dict:
    """Deletes the lab device - its storage and snapshots. Images stay."""
    if running():
        shutdown()
        time.sleep(3)
    home = avd_home()
    shutil.rmtree(os.path.join(home, AVD_NAME + ".avd"), ignore_errors=True)
    try:
        os.remove(os.path.join(home, AVD_NAME + ".ini"))
    except OSError:
        pass
    return {"ok": AVD_NAME not in avds()}


def emulator_log() -> str:
    return os.path.join(store.folder("logs"), "android-emulator.log")


def _tail(path: str, count: int = 30) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return "".join(handle.readlines()[-count:])
    except OSError:
        return ""


def explain_exit(tail: str) -> str:
    """The emulator's last words, turned into one sentence a person can act on."""
    low = tail.lower()
    if any(word in low for word in ("whpx", "hypervisor", "accel", "vt-x", "aehd", "haxm")):
        return ("the emulator needs hardware acceleration, which is off - use "
                "\"Fix acceleration\" on the Android Lab screen")
    if "unknown avd" in low or "broken avd" in low or "cannot find avd" in low:
        return "the emulator could not find the device - delete it and set it up again"
    if "not enough space" in low or ("disk" in low and "space" in low):
        return "there is not enough free disk space for the device"
    if "vulkan" in low or "opengl" in low or "gpu" in low:
        return ("the graphics driver did not cooperate - set Graphics to "
                "swiftshader_indirect and start again")
    return "the emulator exited straight away - its log is below"


def boot(write, settings: dict, wipe: bool = False, job=None) -> dict:
    """Starts the device and waits for Android, watching the emulator while it does."""
    emulator, adb = _tool("emulator"), _tool("adb")
    if not emulator or not adb:
        return {"ok": False, "error": "the emulator or adb is missing"}

    already = running()
    if already:
        write(f"[PyCmd] the lab device is already up: {already[0]}\n")
        return {"ok": True, "serial": already[0], "already": True}

    port = _free_port()
    serial = f"emulator-{port}"
    command = [emulator, "-avd", AVD_NAME, "-port", str(port),
               "-memory", str(settings["ramMb"]), "-cores", str(settings["cores"]),
               "-gpu", settings["gpu"], "-no-boot-anim"]
    if settings.get("coldBoot") or wipe:
        command.append("-no-snapshot-load")
    if wipe:
        command.append("-wipe-data")
    write("$ " + " ".join(command) + "\n")
    write(f"[PyCmd] starting {AVD_NAME} as {serial}. A first boot takes a few minutes.\n")
    log_path = emulator_log()
    try:
        log = open(log_path, "w", encoding="utf-8", errors="replace")
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, env=_env(),
                                   creationflags=_no_window(), cwd=os.path.dirname(emulator))
    except OSError as error:
        return {"ok": False, "error": f"could not start the emulator: {error}"}

    _quiet([adb, "start-server"], 30)
    deadline = time.time() + BOOT_TIMEOUT
    said, stage = 0.0, ""
    try:
        while time.time() < deadline:
            if job is not None and job.cancel:
                _kill(process)
                return {"ok": False, "error": "stopped"}
            if process.poll() is not None:
                log.flush()
                tail = _tail(log_path)
                write("[PyCmd] the emulator stopped before Android came up. Its last words:\n")
                write(tail + "\n")
                return {"ok": False, "error": explain_exit(tail), "log": tail}
            ok, output = _quiet([adb, "-s", serial, "shell", "getprop", "sys.boot_completed"], 20)
            if ok and output.strip() == "1":
                write(f"[PyCmd] {serial} is up.\n")
                return {"ok": True, "serial": serial, "pid": process.pid}
            now_stage = "Android is starting" if ok else "the emulator is starting"
            if now_stage != stage or time.time() - said > 30:
                stage, said = now_stage, time.time()
                write(f"[PyCmd] {now_stage}...\n")
            time.sleep(3)
    finally:
        try:
            log.flush()
        except (OSError, ValueError):
            pass
    return {"ok": False, "error": "Android did not finish booting in ten minutes",
            "log": _tail(log_path)}


# ---------------------------------------------------------------------------
# The PyCmd APK
# ---------------------------------------------------------------------------

def _apk_folder() -> str:
    path = os.path.join(store.folder("android"), "apk")
    os.makedirs(path, exist_ok=True)
    return path


def cached_apk() -> str:
    folder = _apk_folder()
    apks = sorted((os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(".apk")),
                  key=os.path.getmtime)
    return apks[-1] if apks else ""


def fetch_apk(write, cancelled=None) -> dict:
    """The newest PyCmd Android, cached, and checked against its SHA-256."""
    try:
        release = fetch.json_doc(APK_MANIFEST)
        if not isinstance(release, dict) or not release.get("url"):
            raise fetch.FetchError("the Android release manifest names no APK")
    except fetch.FetchError as error:
        cached = cached_apk()
        if cached:
            write(f"[PyCmd] could not check for a newer APK ({error}); using "
                  f"{os.path.basename(cached)}.\n")
            return {"ok": True, "path": cached, "version": ""}
        return {"ok": False, "error": f"could not get the PyCmd APK: {error}"}
    folder = _apk_folder()
    name = f"PyCmd-{release.get('versionName', 'latest')}.apk"
    target = os.path.join(folder, name)
    wanted = release.get("sha256", "")
    if os.path.isfile(target) and (not wanted or fetch.sha256_of(target) == wanted):
        write(f"[PyCmd] {name} is already downloaded.\n")
        return {"ok": True, "path": target, "version": release.get("versionName", "")}
    write(f"[PyCmd] downloading PyCmd Android {release.get('versionName', '')} "
          f"({release.get('sizeText', '')}).\n")
    try:
        fetch.download(release["url"], target, write, sha256=wanted, cancelled=cancelled)
    except fetch.FetchError as error:
        return {"ok": False, "error": str(error)}
    for old in os.listdir(folder):
        if old.endswith(".apk") and old != name:
            try:
                os.remove(os.path.join(folder, old))
            except OSError:
                pass
    return {"ok": True, "path": target, "version": release.get("versionName", "")}


def install_apk(serial: str, apk: str, write=None) -> dict:
    write = write or (lambda text: None)
    adb = _tool("adb")
    if not adb:
        return {"ok": False, "error": "adb is missing"}
    if not apk or not os.path.isfile(apk):
        return {"ok": False, "error": f"there is no APK at {apk}"}
    write(f"[PyCmd] installing {os.path.basename(apk)} onto {serial}.\n")
    ok, output = _run([adb, "-s", serial, "install", "-r", "-g", apk], write, 600)
    if (not ok or "Success" not in output) and "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in output:
        write("[PyCmd] a differently signed PyCmd is on the device; replacing it.\n")
        _quiet([adb, "-s", serial, "uninstall", PACKAGE], 120)
        ok, output = _run([adb, "-s", serial, "install", "-r", "-g", apk], write, 600)
    if not ok or "Success" not in output:
        return {"ok": False, "error": output.strip()[-300:] or "adb install failed"}
    return {"ok": True}


def open_app(serial: str, package: str = PACKAGE) -> dict:
    adb = _tool("adb")
    if not adb:
        return {"ok": False, "error": "adb is missing"}
    ok, output = _quiet([adb, "-s", serial, "shell", "monkey", "-p", package,
                         "-c", "android.intent.category.LAUNCHER", "1"], 30)
    return {"ok": ok and "No activities" not in output, "output": output.strip()[-200:]}


def _serial_or_first(serial: str) -> str:
    return serial or next(iter(running()), "")


def screenshot(serial: str = "") -> dict:
    adb, serial = _tool("adb"), _serial_or_first(serial)
    if not adb or not serial:
        return {"ok": False, "error": "no device is running"}
    target = os.path.join(store.folder("downloads"), time.strftime("android-%Y%m%d-%H%M%S.png"))
    try:
        with open(target, "wb") as handle:
            done = subprocess.run([adb, "-s", serial, "exec-out", "screencap", "-p"],
                                  stdout=handle, stderr=subprocess.PIPE, timeout=60,
                                  creationflags=_no_window())
    except (OSError, subprocess.SubprocessError) as error:
        return {"ok": False, "error": str(error)}
    if done.returncode != 0 or os.path.getsize(target) < 100:
        return {"ok": False, "error": done.stderr.decode("utf-8", "replace").strip()
                or "the device did not send a picture"}
    with open(target, "rb") as handle:
        data = base64.b64encode(handle.read()).decode("ascii")
    return {"ok": True, "path": target, "png": data}


def logcat(serial: str = "", lines: int = 400, only_pycmd: bool = False) -> dict:
    adb, serial = _tool("adb"), _serial_or_first(serial)
    if not adb or not serial:
        return {"ok": False, "error": "no device is running"}
    command = [adb, "-s", serial, "logcat", "-d", "-t", str(max(10, min(int(lines), 5000))),
               "-v", "time"]
    if only_pycmd:
        ok, pid = _quiet([adb, "-s", serial, "shell", "pidof", PACKAGE], 20)
        if ok and pid.strip():
            command += ["--pid", pid.strip().split()[0]]
    ok, output = _quiet(command, 60)
    return {"ok": ok, "text": output[-200_000:]}


def send_text(serial: str, text: str) -> dict:
    """Types into the device - quicker than its on-screen keyboard."""
    adb, serial = _tool("adb"), _serial_or_first(serial)
    if not adb or not serial:
        return {"ok": False, "error": "no device is running"}
    escaped = re.sub(r"([\\\"'`$&|;<>()* ])", r"\\\1", text).replace("\\ ", "%s")
    ok, output = _quiet([adb, "-s", serial, "shell", "input", "text", escaped], 30)
    return {"ok": ok, "output": output.strip()}


def key(serial: str, name: str) -> dict:
    """Presses Back, Home or the app switcher on the device."""
    codes = {"back": 4, "home": 3, "recents": 187, "power": 26, "volup": 24, "voldown": 25}
    adb, serial = _tool("adb"), _serial_or_first(serial)
    if not adb or not serial or name not in codes:
        return {"ok": False, "error": "no device is running" if not serial else "unknown key"}
    ok, _ = _quiet([adb, "-s", serial, "shell", "input", "keyevent", str(codes[name])], 20)
    return {"ok": ok}


# ---------------------------------------------------------------------------
# What the screen draws
# ---------------------------------------------------------------------------

def tools() -> dict:
    found = {name: _tool(name) for name in ("adb", "emulator", "avdmanager", "sdkmanager")}
    return {"sdk": sdk_root(), "tools": found, "ready": all(found.values()),
            "missing": [name for name, where in found.items() if not where]}


def state() -> dict:
    have = tools()
    settings = config()
    home, major = java_home()
    every = devices() if have["tools"]["adb"] else []
    packages = installed_packages(have["sdk"])
    image = image_for(settings["api"])
    return {
        "ok": True,
        "sdk": have["sdk"],
        "sdkIsOwn": os.path.normcase(have["sdk"]) == os.path.normcase(_own_sdk()),
        "ready": have["ready"],
        "missing": have["missing"],
        "tools": have["tools"],
        "java": {"home": home, "major": major},
        "avds": avds(),
        "hasOurs": AVD_NAME in avds(),
        "running": [d["serial"] for d in every if d["emulator"] and d["ready"]],
        "phones": [d for d in every if not d["emulator"]],
        "image": image,
        "imageHere": image in packages,
        "config": settings,
        "androids": [{"api": a[0], "name": a[1], "here": image_for(a[0]) in packages}
                     for a in ANDROIDS],
        "gpuModes": list(GPU_MODES),
        "limits": {k: list(v) for k, v in LIMITS.items()},
        "apk": cached_apk(),
        "log": emulator_log() if os.path.isfile(emulator_log()) else "",
        "abi": _abi(),
        "job": job_state(),
        "device": {"name": AVD_NAME, "ramMb": settings["ramMb"],
                   "storageMb": settings["storageMb"]},
    }


def plan() -> dict:
    """What starting the lab would do, said before anything is downloaded."""
    have = tools()
    settings = config()
    home, _major = java_home()
    packages = installed_packages(have["sdk"])
    image = image_for(settings["api"])
    steps, total = [], 0.0
    if not home:
        steps.append({"what": "Install Java 21 (Temurin)",
                      "why": "Google's SDK tools are Java programs and need Java 17 or newer.",
                      "size": "about 200 MB", "how": "portable, into PyCmd's folder"})
        total += 0.2
    if not have["tools"]["sdkmanager"]:
        steps.append({"what": "Download the Android command-line tools",
                      "why": "Straight from Google's repository, checked against Google's hash.",
                      "size": "about 150 MB", "how": "dl.google.com/android/repository"})
        total += 0.15
    if "emulator" not in packages or "platform-tools" not in packages:
        steps.append({"what": "Add the emulator and platform tools",
                      "why": "The emulator itself, and adb to talk to it.",
                      "size": "about 400 MB", "how": "sdkmanager emulator platform-tools"})
        total += 0.4
    if image not in packages:
        steps.append({"what": f"Download {android_name(settings['api'])}",
                      "why": "The operating system the device runs. Downloaded once.",
                      "size": "about 2.5 GB", "how": "sdkmanager " + image})
        total += 2.5
    steps.append({"what": ("Update" if AVD_NAME in avds() else "Create") + f" the {AVD_NAME} device",
                  "why": f"{settings['ramMb'] / 1024:g} GB RAM, {settings['storageMb'] / 1024:g} GB "
                         f"storage, {settings['cores']} cores, {_abi()}.",
                  "size": "nothing to download", "how": "avdmanager create avd"})
    steps.append({"what": "Check hardware acceleration",
                  "why": "Without it the emulator cannot start; PyCmd says how to turn it on.",
                  "size": "nothing to download", "how": "emulator -accel-check"})
    steps.append({"what": "Boot it, then install and open PyCmd Android",
                  "why": "The APK from the Android release, checked against its SHA-256.",
                  "size": "about 25 MB", "how": "emulator, adb install, adb shell monkey"})
    return {
        "ok": True,
        "ready": have["ready"] and image in packages,
        "sdk": have["sdk"],
        "missing": have["missing"],
        "steps": steps,
        "download": (f"about {total:.1f} GB to download" if total
                     else "nothing to download - everything is here"),
        "device": {"name": AVD_NAME, "ramMb": settings["ramMb"],
                   "storageMb": settings["storageMb"], "heapMb": settings["heapMb"],
                   "cores": settings["cores"], "image": image, "arch": _abi(),
                   "android": android_name(settings["api"])},
        "honest": ("PyCmd does not contain Android - a system image alone is 2.5 GB. It "
                   "sets up and drives Google's own emulator for you, which is the tedious "
                   "part. Everything it downloads comes from Google, under Google's "
                   "licence, and is checked against the hash Google publishes."),
    }


def diagnose() -> dict:
    """Everything that matters in one place, for when it still will not start."""
    have = tools()
    home, major = java_home()
    return {
        "ok": True,
        "os": platform.platform(),
        "machine": platform.machine(),
        "sdk": have["sdk"],
        "tools": have["tools"],
        "java": {"home": home, "major": major},
        "avdHome": avd_home(),
        "avds": avds(),
        "packages": sorted(installed_packages(have["sdk"])),
        "accel": accel_check() if have["tools"]["emulator"] else {},
        "devices": devices() if have["tools"]["adb"] else [],
        "emulatorLog": _tail(emulator_log(), 80),
        "config": config(),
    }


# ---------------------------------------------------------------------------
# The whole thing, as one long job
# ---------------------------------------------------------------------------

STEPS = ("java", "tools", "licences", "image", "device", "accel", "boot", "apk")


class Job:
    def __init__(self):
        self.lines: list = []
        self.step = ""
        self.done_steps: list = []
        self.percent = -1
        self.finished = 0.0
        self.ok = False
        self.error = ""
        self.fix = ""
        self.serial = ""
        self.cancel = False
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

    def enter(self, step: str) -> None:
        if self.step:
            self.done_steps.append(self.step)
        self.step = step
        self.percent = -1

    def as_dict(self) -> dict:
        return {"running": not self.finished, "step": self.step, "ok": self.ok,
                "error": self.error, "fix": self.fix, "serial": self.serial,
                "percent": self.percent, "doneSteps": list(self.done_steps),
                "steps": list(STEPS), "cancelling": self.cancel,
                "seconds": int((self.finished or time.time()) - self.started)}


_job = None
_job_lock = threading.RLock()


def job_state() -> dict:
    with _job_lock:
        if _job is None:
            return {"running": False, "everStarted": False, "steps": list(STEPS)}
        data = _job.as_dict()
        data["everStarted"] = True
        return data


def job_lines() -> list:
    with _job_lock:
        return _job.drain() if _job is not None else []


def _work(job: Job, settings: dict, apk: str, wipe: bool, skip_apk: bool) -> None:
    stopped = lambda: job.cancel  # noqa: E731
    job.enter("java")
    java = ensure_java(job.write, stopped)
    if not java:
        job.error = "Java 17 or newer is needed and could not be installed"
        return
    job.enter("tools")
    if not ensure_cmdline_tools(job.write, stopped):
        job.error = "the Android command-line tools could not be downloaded"
        return
    root = sdk_root()
    _sdk_folders(root)
    job.write(f"[PyCmd] SDK: {root}\n")
    job.enter("licences")
    if not accept_licences(job.write, java):
        job.write("[PyCmd] the licence step did not say yes; carrying on anyway.\n")
    job.enter("image")
    if not ensure_packages(job.write, java, settings["api"], job):
        job.error = ("stopped" if job.cancel
                     else f"{android_name(settings['api'])} could not be downloaded")
        return
    job.enter("device")
    if not ensure_avd(job.write, java, settings):
        job.error = "the virtual device could not be created"
        return
    job.enter("accel")
    accel = accel_check()
    job.write(f"[PyCmd] acceleration: {accel.get('message') or 'unknown'}\n")
    if accel.get("known") and not accel.get("ok"):
        job.error = "hardware acceleration is off, so the emulator cannot run: " + accel["message"]
        job.fix = accel.get("fix", "whpx")
        return
    job.enter("boot")
    booted = boot(job.write, settings, wipe=wipe, job=job)
    if not booted.get("ok"):
        job.error = booted.get("error", "it would not boot")
        if "acceleration" in job.error:
            job.fix = "whpx"
        return
    job.serial = booted["serial"]
    if settings["installApk"] and not skip_apk:
        job.enter("apk")
        path = apk
        if not path:
            got = fetch_apk(job.write, stopped)
            if not got.get("ok"):
                job.write(f"[PyCmd] {got.get('error')}\n")
            path = got.get("path", "")
        if path:
            placed = install_apk(job.serial, path, job.write)
            if placed.get("ok"):
                job.write("[PyCmd] PyCmd Android is installed.\n")
                if settings["openApk"]:
                    open_app(job.serial)
            else:
                job.write(f"[PyCmd] the APK did not install: {placed.get('error')}\n")
                job.write("[PyCmd] the device is up anyway.\n")
    job.ok = True
    job.write("[PyCmd] Android Lab is ready.\n")


def start(apk: str = "", wipe: bool = False, skip_apk: bool = False) -> dict:
    """Sets everything up, boots the device and puts PyCmd on it. On its own thread."""
    global _job
    with _job_lock:
        if _job is not None and not _job.finished:
            return {"ok": False, "reason": "already-running",
                    "error": "the lab is already starting"}
        _job = Job()
        job = _job
    settings = config()

    def work():
        try:
            _work(job, settings, apk, wipe, skip_apk)
        except Exception as error:  # noqa: BLE001
            import traceback

            job.error = f"{type(error).__name__}: {error}"
            job.write(traceback.format_exc())
        finally:
            if job.ok and job.step:
                job.done_steps.append(job.step)
            job.step = ""
            job.finished = time.time()

    threading.Thread(target=work, name="pycmd-android-lab", daemon=True).start()
    return {"ok": True, "started": True}


def cancel() -> dict:
    with _job_lock:
        if _job is None or _job.finished:
            return {"ok": True, "already": True}
        _job.cancel = True
    return {"ok": True}


def shutdown(write=None) -> dict:
    """Turns the lab's emulators off. Phones are left alone."""
    cancel()
    adb = _tool("adb")
    if not adb:
        return {"ok": False, "error": "adb is missing"}
    stopped = []
    for serial in running():
        _quiet([adb, "-s", serial, "emu", "kill"], 60)
        stopped.append(serial)
    return {"ok": True, "stopped": stopped}


def install_to(serial: str, apk: str = "") -> dict:
    """Puts an APK - PyCmd's, or any - on any connected device, phone included."""
    ours = not apk
    if ours:
        got = fetch_apk(lambda text: None)
        if not got.get("ok"):
            return got
        apk = got["path"]
    placed = install_apk(serial, apk)
    if placed.get("ok") and ours:
        open_app(serial)
    return placed
