"""Toolchains installed by downloading the vendor's own archive. No package manager.

## Why this exists

Every toolchain install used to go through winget, scoop or choco, and that is
where nearly every "it throws errors" came from - not from the toolchains:

* scoop keeps half its catalogue in buckets that are not there on a fresh
  install, and adding a bucket needs git, which a fresh install does not have
  either - so `scoop install kotlin` said "couldn't find manifest";
* winget needs App Installer, which is missing on Server and LTSC editions and
  on machines where somebody removed it;
* choco needs administrator for every single package;
* rustup's default Windows toolchain needs Visual Studio's linker, so Rust
  "installed" and then every program failed with `link.exe not found`.

A portable install skips all of that. It reads the vendor's own release
metadata, downloads the archive the vendor publishes for Windows x64, checks
it against the hash the vendor publishes, and unpacks it under PyCmd's own
folder. No administrator, no registry, no PATH edits outside this app, and
removing it is deleting a folder. PyCmd puts its bin folders on its own PATH
at start-up, so the console, the Run screen and the Learn tab all see it.

Package managers are still there as the second route, for people who prefer
them and for the toolchains no vendor ships as a plain archive.

## What each entry knows

* how to find the newest release and its download - from the vendor's own
  index (nodejs.org/dist/index.json, go.dev/dl, the Adoptium API, the Zig
  index, ...) rather than from a version number typed in here, so this file
  does not go stale every month;
* which hash the vendor publishes for it;
* which folders inside the archive hold the programs;
* which other install it needs first (Kotlin needs a JDK).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time

from . import envpath, fetch, store

WINDOWS = os.name == "nt"
MANIFEST = "pycmd-portable.json"


class Plan:
    """What installing one portable toolchain would download."""

    __slots__ = ("url", "filename", "version", "sha256", "sha1", "kind", "strip", "size")

    def __init__(self, url, filename="", version="", sha256="", sha1="", kind="zip",
                 strip=True, size=0):
        self.url = url
        self.filename = filename or url.rsplit("/", 1)[-1].split("?")[0]
        self.version = version
        self.sha256 = sha256
        self.sha1 = sha1
        self.kind = kind
        self.strip = strip
        self.size = int(size or 0)

    def as_dict(self) -> dict:
        return {"url": self.url, "filename": self.filename, "version": self.version,
                "sha256": self.sha256, "sha1": self.sha1, "kind": self.kind,
                "size": self.size, "checked": bool(self.sha256 or self.sha1)}


class Portable:
    """One toolchain PyCmd can install by itself."""

    __slots__ = ("id", "name", "provides", "resolve", "bins", "env", "needs", "site",
                 "size_hint", "note")

    def __init__(self, id, name, provides, resolve, bins=(".",), env=None, needs=(),
                 site="", size_hint="", note=""):
        self.id = id
        self.name = name
        self.provides = tuple(provides)
        self.resolve = resolve
        self.bins = tuple(bins)
        self.env = dict(env or {})
        self.needs = tuple(needs)
        self.site = site
        self.size_hint = size_hint
        self.note = note


# ---------------------------------------------------------------------------
# Finding the newest release, vendor by vendor
# ---------------------------------------------------------------------------

def _version_key(text: str):
    return tuple(int(part) for part in re.findall(r"\d+", text)[:4])


def _github_latest(repo: str, asset_pattern: str, tag_to_asset=None) -> Plan:
    """A GitHub release asset, through the API and then through the web page.

    The API is the clean way, and it is rate-limited to sixty calls an hour
    for anybody without a token. The `releases/latest` page redirects to the
    tag, which is enough to build the asset name for releases that name their
    assets after the version - so a rate-limited API is not a failed install.
    """
    try:
        data = fetch.json_doc(f"https://api.github.com/repos/{repo}/releases/latest")
        for asset in data.get("assets", []):
            if re.search(asset_pattern, asset.get("name", "")):
                digest = (asset.get("digest") or "")
                sha256 = digest.split(":", 1)[1] if digest.startswith("sha256:") else ""
                return Plan(asset["browser_download_url"], asset["name"],
                            data.get("tag_name", ""), sha256=sha256,
                            size=asset.get("size", 0))
        raise fetch.FetchError(f"{repo}'s latest release has no file matching {asset_pattern}")
    except fetch.FetchError:
        if tag_to_asset is None:
            raise
    landed = fetch.final_url(f"https://github.com/{repo}/releases/latest")
    tag = landed.rstrip("/").rsplit("/", 1)[-1]
    if not tag or tag == "latest":
        raise fetch.FetchError(f"could not find {repo}'s latest release")
    name = tag_to_asset(tag)
    return Plan(f"https://github.com/{repo}/releases/download/{tag}/{name}", name, tag)


def _node() -> Plan:
    releases = fetch.json_doc("https://nodejs.org/dist/index.json")
    lts = next(r for r in releases if r.get("lts") and "win-x64-zip" in r.get("files", []))
    version = lts["version"]
    name = f"node-{version}-win-x64.zip"
    sums = fetch.text(f"https://nodejs.org/dist/{version}/SHASUMS256.txt")
    sha = next((line.split()[0] for line in sums.splitlines()
                if line.strip().endswith(name)), "")
    return Plan(f"https://nodejs.org/dist/{version}/{name}", name, version, sha256=sha)


def _go() -> Plan:
    releases = fetch.json_doc("https://go.dev/dl/?mode=json")
    stable = next(r for r in releases if r.get("stable"))
    pick = next(f for f in stable["files"]
                if f["os"] == "windows" and f["arch"] == "amd64" and f["kind"] == "archive")
    return Plan(f"https://go.dev/dl/{pick['filename']}", pick["filename"], stable["version"],
                sha256=pick.get("sha256", ""), size=pick.get("size", 0))


def _jdk(feature: int = 21):
    def resolve() -> Plan:
        data = fetch.json_doc(
            f"https://api.adoptium.net/v3/assets/latest/{feature}/hotspot"
            "?os=windows&architecture=x64&image_type=jdk&vendor=eclipse")
        package = data[0]["binary"]["package"]
        return Plan(package["link"], package["name"], data[0].get("release_name", ""),
                    sha256=package.get("checksum", ""), size=package.get("size", 0))
    return resolve


def _zig() -> Plan:
    index = fetch.json_doc("https://ziglang.org/download/index.json")
    releases = sorted((k for k in index if k != "master"), key=_version_key)
    newest = releases[-1]
    build = index[newest]["x86_64-windows"]
    return Plan(build["tarball"], version=newest, sha256=build.get("shasum", ""),
                size=build.get("size", 0))


def _deno() -> Plan:
    return Plan("https://github.com/denoland/deno/releases/latest/download/"
                "deno-x86_64-pc-windows-msvc.zip", strip=False)


def _bun() -> Plan:
    return Plan("https://github.com/oven-sh/bun/releases/latest/download/bun-windows-x64.zip")


def _dart() -> Plan:
    info = fetch.json_doc("https://storage.googleapis.com/dart-archive/channels/"
                          "stable/release/latest/VERSION")
    version = info.get("version", "")
    base = (f"https://storage.googleapis.com/dart-archive/channels/stable/release/"
            f"{version}/sdk/dartsdk-windows-x64-release.zip")
    try:
        sha = fetch.text(base + ".sha256sum").split()[0]
    except (fetch.FetchError, IndexError):
        sha = ""
    return Plan(base, version=version, sha256=sha)


def _nim() -> Plan:
    version = fetch.text("https://nim-lang.org/channels/stable").strip()
    name = f"nim-{version}_x64.zip"
    try:
        sha = fetch.text(f"https://nim-lang.org/download/{name}.sha256").split()[0]
    except (fetch.FetchError, IndexError):
        sha = ""
    return Plan(f"https://nim-lang.org/download/{name}", name, version, sha256=sha)


def _perl() -> Plan:
    releases = fetch.json_doc("https://strawberryperl.com/releases.json")
    portable = releases[0]["edition"]["portable"]
    # Strawberry's portable zip has no wrapper folder; perl/ and c/ sit at the top.
    return Plan(portable["url"], version=releases[0].get("version", ""),
                sha256=portable.get("sha256", ""), size=portable.get("size", 0), strip=False)


def _php() -> Plan:
    releases = fetch.json_doc("https://windows.php.net/downloads/releases/releases.json")
    newest = sorted(releases, key=_version_key)[-1]
    branch = releases[newest]
    key = sorted((k for k in branch if k.startswith("nts-") and k.endswith("-x64")),
                 key=_version_key)[-1]
    build = branch[key]["zip"]
    return Plan(f"https://windows.php.net/downloads/releases/{build['path']}", build["path"],
                branch.get("version", newest), sha256=build.get("sha256", ""), strip=False)


def _kotlin() -> Plan:
    return _github_latest(
        "JetBrains/kotlin", r"^kotlin-compiler-[\d.]+\.zip$",
        lambda tag: f"kotlin-compiler-{tag.lstrip('v')}.zip")


def _pwsh() -> Plan:
    plan = _github_latest(
        "PowerShell/PowerShell", r"^PowerShell-[\d.]+-win-x64\.zip$",
        lambda tag: f"PowerShell-{tag.lstrip('v')}-win-x64.zip")
    plan.strip = False
    return plan


def _winlibs() -> Plan:
    # WinLibs names its assets after GCC and MinGW versions and a release
    # number, none of which the tag alone gives - so this one needs the API.
    return _github_latest(
        "brechtsanders/winlibs_mingw",
        r"^winlibs-x86_64-posix-seh-gcc-[\d.]+-mingw-w64ucrt-[\d.]+-r\d+\.zip$")


def _git() -> Plan:
    def asset(tag: str) -> str:
        version = re.match(r"v?([\d.]+)", tag).group(1).rstrip(".")
        return f"PortableGit-{version}-64-bit.7z.exe"
    plan = _github_latest("git-for-windows/git", r"^PortableGit-[\d.]+-64-bit\.7z\.exe$", asset)
    plan.kind = "sfx"
    return plan


def _rustup() -> Plan:
    return Plan("https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe",
                kind="rustup")


def _dotnet() -> Plan:
    return Plan("https://dot.net/v1/dotnet-install.ps1", kind="dotnet", version="8.0")


def _typescript() -> Plan:
    return Plan("npm:typescript", kind="npm")


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------

PORTABLES = [
    Portable("node", "Node.js", ["node"], _node,
             bins=(".",), site="https://nodejs.org/", size_hint="about 35 MB"),
    Portable("go", "Go", ["go"], _go, bins=("bin",), site="https://go.dev/dl/",
             size_hint="about 75 MB"),
    Portable("jdk", "Java (Temurin 21)", ["java"], _jdk(21), bins=("bin",),
             env={"JAVA_HOME": "."}, site="https://adoptium.net/", size_hint="about 200 MB",
             note="Also what Kotlin, Scala and the Android tools run on."),
    Portable("zig", "Zig", ["zig"], _zig, bins=(".",), site="https://ziglang.org/",
             size_hint="about 90 MB", note="Zig is also a drop-in C and C++ compiler."),
    Portable("deno", "Deno", ["deno"], _deno, bins=(".",), site="https://deno.com/",
             size_hint="about 45 MB"),
    Portable("bun", "Bun", ["bun"], _bun, bins=(".",), site="https://bun.sh/",
             size_hint="about 40 MB"),
    Portable("dotnet", ".NET SDK 8", ["dotnet", "fsi"], _dotnet, bins=(".",),
             env={"DOTNET_ROOT": ".", "DOTNET_CLI_TELEMETRY_OPTOUT": "=1"},
             site="https://dotnet.microsoft.com/", size_hint="about 250 MB",
             note="Installed with Microsoft's own dotnet-install script, into PyCmd's folder."),
    Portable("rust", "Rust (GNU toolchain)", ["rustc"], _rustup, bins=("cargo/bin",),
             env={"CARGO_HOME": "cargo", "RUSTUP_HOME": "rustup"},
             site="https://rustup.rs/", size_hint="about 300 MB",
             note="The GNU toolchain, which links without Visual Studio. The usual "
                  "MSVC one needs Visual Studio's linker, and without it every Rust "
                  "program fails with `link.exe not found`."),
    Portable("kotlin", "Kotlin compiler", ["kotlinc"], _kotlin, bins=("bin",), needs=("jdk",),
             site="https://kotlinlang.org/", size_hint="about 90 MB"),
    Portable("pwsh", "PowerShell 7", ["pwsh"], _pwsh, bins=(".",),
             site="https://github.com/PowerShell/PowerShell", size_hint="about 110 MB"),
    Portable("gcc", "GCC (WinLibs)", ["gcc", "gpp", "gfortran"], _winlibs, bins=("bin",),
             site="https://winlibs.com/", size_hint="about 250 MB",
             note="C, C++ and Fortran. MinGW-w64 with the UCRT runtime, which is what "
                  "current Windows ships."),
    Portable("git", "Git for Windows (bash)", ["bash"], _git, bins=("bin", "usr/bin"),
             site="https://gitforwindows.org/", size_hint="about 60 MB",
             note="Brings bash, so .sh files run, and git itself."),
    Portable("dart", "Dart", ["dart"], _dart, bins=("bin",), site="https://dart.dev/",
             size_hint="about 200 MB"),
    Portable("nim", "Nim", ["nim"], _nim, bins=("bin",), site="https://nim-lang.org/",
             size_hint="about 25 MB"),
    Portable("perl", "Strawberry Perl", ["perl"], _perl, bins=("perl/bin", "c/bin"),
             site="https://strawberryperl.com/", size_hint="about 300 MB"),
    Portable("php", "PHP", ["php"], _php, bins=(".",), site="https://windows.php.net/",
             size_hint="about 35 MB"),
    Portable("typescript", "TypeScript compiler", ["tsc"], _typescript, bins=(".",),
             needs=("node",), site="https://www.typescriptlang.org/", size_hint="about 25 MB",
             note="Installed with npm into PyCmd's own folder."),
]

_BY_ID = {p.id: p for p in PORTABLES}


def by_id(portable_id: str):
    return _BY_ID.get(portable_id)


def for_toolchain(toolchain_id: str):
    """The portable install that provides a toolchain, or None.

    `tsc` is provided by both node (which does not carry it) and typescript
    (which does); the more specific one wins.
    """
    if toolchain_id == "tsc":
        return _BY_ID["typescript"]
    return next((p for p in PORTABLES if toolchain_id in p.provides), None)


# ---------------------------------------------------------------------------
# Where they live, and putting them on the PATH
# ---------------------------------------------------------------------------

def supported() -> bool:
    """Portable installs are Windows x64 archives, so they are for Windows.

    PYCMD_PORTABLE=1 turns them on elsewhere, for testing the downloads.
    """
    return WINDOWS or os.environ.get("PYCMD_PORTABLE") == "1"


def home() -> str:
    return store.folder("toolchains")


def folder(portable_id: str) -> str:
    return os.path.join(home(), portable_id)


def _manifest(portable_id: str) -> dict:
    try:
        with open(os.path.join(folder(portable_id), MANIFEST), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def installed() -> list:
    """Every portable install that is on disk and complete."""
    out = []
    for spec in PORTABLES:
        data = _manifest(spec.id)
        if data.get("complete"):
            out.append({"id": spec.id, "name": spec.name, "version": data.get("version", ""),
                        "folder": folder(spec.id), "installedAt": data.get("installedAt", 0),
                        "provides": list(spec.provides)})
    return out


def _bin_dirs(spec: Portable) -> list:
    base = folder(spec.id)
    return [os.path.normpath(os.path.join(base, rel)) for rel in spec.bins]


def _env_values(spec: Portable) -> dict:
    """The variables a toolchain wants, its folders made absolute.

    A value that names a folder inside the install ("." or "cargo") becomes a
    full path; a value that starts with "=" is meant literally.
    """
    base = folder(spec.id)
    out = {}
    for key, rel in spec.env.items():
        if rel.startswith("="):
            out[key] = rel[1:]
        else:
            out[key] = os.path.normpath(os.path.join(base, rel))
    return out


def activate_all() -> list:
    """Puts every installed portable toolchain on this process's PATH.

    Called once at start-up. Only PyCmd's own environment changes; nothing is
    written to the registry, so uninstalling PyCmd leaves the machine as it
    found it.
    """
    added = []
    for spec in PORTABLES:
        if not _manifest(spec.id).get("complete"):
            continue
        added.extend(envpath.ensure(*_bin_dirs(spec)))
        for key, value in _env_values(spec).items():
            # A JAVA_HOME the user set themselves wins, unless it points at
            # nothing - which is the "java 8 from 2016, since uninstalled"
            # case that stops the Android tools dead.
            current = os.environ.get(key, "")
            if not current or (key.endswith("_HOME") and not os.path.isdir(current)):
                os.environ[key] = value
    return added


def plan(portable_id: str) -> dict:
    """What installing it would download, said before anything is downloaded."""
    spec = by_id(portable_id)
    if spec is None:
        return {"ok": False, "error": f"there is no portable install called {portable_id!r}"}
    try:
        made = spec.resolve()
    except (fetch.FetchError, StopIteration, KeyError, IndexError, ValueError) as error:
        return {"ok": False, "id": spec.id, "name": spec.name, "site": spec.site,
                "error": f"could not find {spec.name}'s latest release: {error}"}
    return {"ok": True, "id": spec.id, "name": spec.name, "site": spec.site,
            "sizeHint": spec.size_hint, "note": spec.note, "needs": list(spec.needs),
            "folder": folder(spec.id), **made.as_dict()}


def _run(command, write, env=None, timeout=60 * 60) -> bool:
    write("$ " + " ".join(command) + "\n")
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
            env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if WINDOWS else 0,
        )
    except OSError as error:
        write(f"[PyCmd] could not start {command[0]}: {error}\n")
        return False
    done = threading.Event()

    def pump():
        for line in process.stdout:
            write(line)
        done.set()

    threading.Thread(target=pump, daemon=True).start()
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        write("[PyCmd] it did not finish in time\n")
        return False
    done.wait(5)
    return code == 0


def install(portable_id: str, write=None, cancelled=None) -> dict:
    """Downloads, checks and unpacks one toolchain, and its dependencies first."""
    write = write or (lambda line: None)
    spec = by_id(portable_id)
    if spec is None:
        return {"ok": False, "error": f"there is no portable install called {portable_id!r}"}

    for need in spec.needs:
        if not _manifest(need).get("complete") and not _have_on_path(need):
            write(f"[PyCmd] {spec.name} needs {by_id(need).name} first.\n")
            got = install(need, write, cancelled)
            if not got.get("ok"):
                return {"ok": False, "error": f"{by_id(need).name} could not be installed, "
                                              f"and {spec.name} needs it: {got.get('error')}"}

    try:
        made = spec.resolve()
    except (fetch.FetchError, StopIteration, KeyError, IndexError, ValueError) as error:
        return {"ok": False, "error": f"could not find {spec.name}'s latest release: {error}",
                "site": spec.site}

    target = folder(spec.id)
    downloads = store.folder("downloads")
    write(f"[PyCmd] {spec.name} {made.version} - portable, into {target}\n")
    try:
        if made.kind == "zip":
            archive = fetch.download(made.url, os.path.join(downloads, made.filename), write,
                                     sha256=made.sha256, sha1=made.sha1, cancelled=cancelled)
            fetch.unpack(archive, target, strip_top=made.strip, write=write)
            _remove(archive)
        elif made.kind == "sfx":
            if not WINDOWS:
                raise fetch.FetchError("a self-extracting archive only runs on Windows")
            archive = fetch.download(made.url, os.path.join(downloads, made.filename), write,
                                     sha256=made.sha256, cancelled=cancelled)
            os.makedirs(target, exist_ok=True)
            if not _run([archive, f"-o{target}", "-y"], write):
                raise fetch.FetchError("the self-extracting archive did not unpack")
            _remove(archive)
        elif made.kind == "rustup":
            if not WINDOWS:
                raise fetch.FetchError("rustup-init.exe only runs on Windows")
            installer = fetch.download(made.url, os.path.join(downloads, "rustup-init.exe"),
                                       write, cancelled=cancelled)
            env = dict(os.environ, CARGO_HOME=os.path.join(target, "cargo"),
                       RUSTUP_HOME=os.path.join(target, "rustup"))
            os.makedirs(target, exist_ok=True)
            if not _run([installer, "-y", "--no-modify-path", "--profile", "minimal",
                         "--default-host", "x86_64-pc-windows-gnu",
                         "--default-toolchain", "stable"], write, env=env):
                raise fetch.FetchError("rustup-init did not finish")
            _remove(installer)
            made.version = "stable (GNU)"
        elif made.kind == "dotnet":
            if not WINDOWS:
                raise fetch.FetchError("the .NET install script is the Windows one")
            script = fetch.download(made.url, os.path.join(downloads, "dotnet-install.ps1"), write,
                                    cancelled=cancelled)
            os.makedirs(target, exist_ok=True)
            if not _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                         script, "-Channel", made.version, "-InstallDir", target,
                         "-NoPath"], write):
                raise fetch.FetchError("dotnet-install did not finish")
        elif made.kind == "npm":
            npm = shutil.which("npm") or shutil.which("npm.cmd")
            if not npm:
                raise fetch.FetchError("npm is not here - install Node.js first")
            os.makedirs(target, exist_ok=True)
            if not _run([npm, "install", "-g", "--prefix", target, "typescript"], write):
                raise fetch.FetchError("npm install typescript did not finish")
            made.version = "latest"
        else:
            raise fetch.FetchError(f"unknown install kind {made.kind}")
    except fetch.FetchError as error:
        write(f"[PyCmd] {error}\n")
        return {"ok": False, "error": str(error), "site": spec.site}

    with open(os.path.join(target, MANIFEST), "w", encoding="utf-8") as handle:
        json.dump({"id": spec.id, "version": made.version, "url": made.url,
                   "installedAt": time.time(), "complete": True}, handle)
    added = envpath.ensure(*_bin_dirs(spec))
    for key, value in _env_values(spec).items():
        os.environ[key] = value
    write(f"[PyCmd] {spec.name} is installed. It is on PyCmd's PATH from now on.\n")
    return {"ok": True, "id": spec.id, "version": made.version, "folder": target,
            "added": added}


def _have_on_path(portable_id: str) -> bool:
    spec = by_id(portable_id)
    if spec is None:
        return False
    probe = {"jdk": "java", "node": "node"}.get(portable_id, spec.provides[0])
    return bool(shutil.which(probe))


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def remove(portable_id: str) -> dict:
    """Uninstalls a portable toolchain: it is a folder, so this deletes it."""
    spec = by_id(portable_id)
    if spec is None:
        return {"ok": False, "error": f"there is no portable install called {portable_id!r}"}
    target = folder(spec.id)
    if not os.path.isdir(target):
        return {"ok": True, "already": True}
    shutil.rmtree(target, ignore_errors=True)
    if os.path.isdir(target):
        return {"ok": False, "error": f"{target} could not be removed - is something using it?"}
    return {"ok": True, "removed": target}


def catalogue() -> list:
    """Every portable install, and whether it is here. A screen."""
    rows = []
    for spec in PORTABLES:
        data = _manifest(spec.id)
        rows.append({"id": spec.id, "name": spec.name, "provides": list(spec.provides),
                     "installed": bool(data.get("complete")),
                     "version": data.get("version", ""), "site": spec.site,
                     "sizeHint": spec.size_hint, "note": spec.note,
                     "needs": list(spec.needs), "folder": folder(spec.id)})
    return rows
