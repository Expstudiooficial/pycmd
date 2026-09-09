#!/usr/bin/env python3
"""Writes and checks `dist-windows/latest.json`.

The Windows twin of `tools/make_latest.py`, and separate from it on purpose:
the exe and the APK are different artefacts on different schedules, and one
manifest describing both would eventually offer somebody the wrong one.

    python tools/make_latest_windows.py dist-windows/PyCmd-1.0.0.exe --notes "..."
    python tools/make_latest_windows.py          # just check what is there

Called with no arguments it verifies rather than writes: that the manifest
points at a file that exists, that its size and checksum match that file, and
that its build number agrees with the source. That check runs in the suite, so
a manifest that has drifted away from its exe is a red line rather than a
download that fails for somebody else.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist-windows")
MANIFEST = os.path.join(DIST, "latest.json")
SUMS = os.path.join(DIST, "SHA256SUMS.txt")

REPO = "expstudiooficial/pycmd"
BRANCH = "windowsmain"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

# Where the exe actually lives.
#
# Not in the repository. A 15 MB binary committed once per version is 15 MB
# added to every clone of this project for ever, and raw.githubusercontent is
# a source viewer rather than a place to serve downloads from. GitHub
# Releases is the right home: built by CI, attached to the tag, on a CDN.
#
# Two addresses, because they answer two different questions:
#
#   `url` is pinned to this exact version, because `sha256` beside it
#   describes that build and no other. An updater downloads this one and
#   checks the digest; a moving address would fail that check the day after
#   the next release, which is precisely when it matters.
#
#   `latestUrl` always redirects to whatever the newest release is. That is
#   the one to put on a website or hand somebody, and it is deliberately not
#   what the updater uses.
RELEASES = f"https://github.com/{REPO}/releases"


def release_urls(version: str, name: str, tag: str = "") -> dict:
    """The addresses for one release.

    `tag` is passed in when CI knows it, and is not guessed from the version
    when it does. Rebuilding it as f"windows-v{version}" is the obvious thing
    and it is wrong the moment the two are written differently: the tag
    `windows-v2.0` against a source saying "2.0.0" produced a manifest
    pointing at a `windows-v2.0.0` release that does not exist, and a download
    that 404s for everybody. The tag is the fact; the version is a separate
    statement about it.
    """
    tag = tag or f"windows-v{version}"
    return {
        "url": f"{RELEASES}/download/{tag}/{name}",
        "latestUrl": f"{RELEASES}/latest/download/PyCmd.exe",
        "release": f"{RELEASES}/tag/{tag}",
        "releases": RELEASES,
        "tag": tag,
    }


def source_version() -> tuple:
    """The version and build the code itself claims."""
    path = os.path.join(ROOT, "windows", "pycmd_win", "host.py")
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    version = re.search(r'^VERSION = "([^"]+)"', text, re.M)
    build = re.search(r"^BUILD = (\d+)", text, re.M)
    if not version or not build:
        raise SystemExit("windows/pycmd_win/host.py has no VERSION and BUILD to read")
    return version.group(1), int(build.group(1))


def agrees_with_tag(tag: str) -> int:
    """Does the source claim the version this tag says it is?

    A tag and the VERSION in host.py are two statements about the same thing,
    written at different moments by different hands, and nothing had ever
    checked they matched. When they do not, everything downstream is quietly
    wrong rather than loudly broken: the exe is attached to the release for
    the tag, the manifest is written from the source, and so `url` points at
    one release while `sha256` describes the build on another. The updater
    then downloads fifteen megabytes and rejects them on a checksum error
    that names neither the tag nor the version - and because BUILD did not
    move either, nobody is offered the update in the first place.

    So this is a gate, run before anything is built, and it fails with the
    two numbers side by side.
    """
    version, build = source_version()
    wanted = tag[len("windows-v"):] if tag.startswith("windows-v") else tag
    # Compared as numbers, not as text. "2.0" and "2.0.0" are the same version
    # written two ways, and a release should not be blocked over a trailing
    # zero - which is exactly what happened, on a tag that was perfectly fine.
    if _numeric(wanted) != _numeric(version):
        print(f"the tag says {wanted}, windows/pycmd_win/host.py says {version}.",
              file=sys.stderr)
        print("  Nothing is built from a disagreement like that: the exe would be",
              file=sys.stderr)
        print("  attached to one release and the manifest would point at another.",
              file=sys.stderr)
        print(f"  Set VERSION = \"{wanted}\" and raise BUILD, or tag "
              f"windows-v{version}.", file=sys.stderr)
        return 1
    print(f"the tag and the source agree: {version} (build {build})")
    return 0


def _numeric(version: str) -> tuple:
    """A version as numbers, so 2.0 and 2.0.0 compare equal."""
    parts = []
    for piece in (version or "").split("."):
        digits = "".join(c for c in piece if c.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def digest(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def readable(count: int) -> str:
    if count >= 1024 * 1024:
        return f"{count / 1048576:.0f} MB"
    return f"{count // 1024} KB"


def build_manifest(exe: str, notes: str, tag: str = "") -> dict:
    version, build = source_version()
    size = os.path.getsize(exe)
    # The asset is attached to the release under its built name, PyCmd.exe,
    # whatever the file is called on the machine that made it.
    name = "PyCmd.exe"
    return {
        "name": "PyCmd for Windows",
        "version": version,
        "build": build,
        **release_urls(version, name, tag),
        "sha256": digest(exe),
        "bytes": size,
        "notes": notes,
        "sizeText": readable(size),
        "releasedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minWindows": "10",
        "arch": "x64",
        "python": "3.13",
        "runtime": "Edge WebView2 (already on Windows 10 and 11)",
        "installer": False,
        "portable": True,
        "changelog": f"{RAW}/dist-windows/README.md",
        "checksums": f"{RAW}/dist-windows/SHA256SUMS.txt",
        "source": f"https://github.com/{REPO}/tree/{BRANCH}",
        "sourceZip": f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}",
        "android": f"https://raw.githubusercontent.com/{REPO}/"
                   f"claude/python-mobile-cmd-android-dj1ixb/dist/latest.json",
    }


def seed(notes: str) -> int:
    """Writes a manifest for a build that does not exist yet.

    The exe is built on Windows, by CI or by somebody running build.ps1, and
    this repository is checked out on machines that have never done either. So
    the manifest can exist before the file does: it carries the version, the
    address the build will land at, and an empty checksum.

    An empty checksum is not a loophole. `updates.download` refuses a manifest
    without one outright, so a seeded manifest can be read and cannot be
    installed from - which is exactly the state of a version nobody has built.
    """
    version, build = source_version()
    manifest = {
        "name": "PyCmd for Windows",
        "version": version,
        "build": build,
        **release_urls(version, "PyCmd.exe"),
        "sha256": "",
        "bytes": 0,
        "notes": notes,
        "sizeText": "",
        "releasedAt": "",
        "minWindows": "10",
        "arch": "x64",
        "python": "3.13",
        "runtime": "Edge WebView2 (already on Windows 10 and 11)",
        "installer": False,
        "portable": True,
        "built": False,
        "changelog": f"{RAW}/dist-windows/README.md",
        "checksums": f"{RAW}/dist-windows/SHA256SUMS.txt",
        "source": f"https://github.com/{REPO}/tree/{BRANCH}",
        "sourceZip": f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}",
        "android": f"https://raw.githubusercontent.com/{REPO}/"
                   f"claude/python-mobile-cmd-android-dj1ixb/dist/latest.json",
    }
    os.makedirs(DIST, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    # And the checksums beside it, which otherwise still describe the previous
    # version - a file whose whole job is to be trusted, quietly holding the
    # hash of a different build.
    with open(SUMS, "w", encoding="utf-8") as handle:
        handle.write(f"# PyCmd for Windows {version} (build {build}) "
                     "has not been built yet.\n")
        handle.write("# The checksum appears here when a windows-v tag "
                     "builds it.\n")
    print(f"seeded dist-windows/latest.json for {version} (build {build}), not yet built")
    return 0


def write(exe: str, notes: str, tag: str = "") -> int:
    if not os.path.isfile(exe):
        print(f"there is no {exe} to describe", file=sys.stderr)
        return 1
    os.makedirs(DIST, exist_ok=True)
    manifest = build_manifest(exe, notes, tag)
    with open(MANIFEST, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    with open(SUMS, "w", encoding="utf-8") as handle:
        handle.write(f"{manifest['sha256']}  {os.path.basename(exe)}\n")
    print(json.dumps(manifest, indent=2))
    return 0


def check() -> int:
    """Is the manifest true? Used by the suite."""
    if not os.path.isfile(MANIFEST):
        print("dist-windows/latest.json is not there yet", file=sys.stderr)
        return 1
    with open(MANIFEST, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    problems = []
    version, build = source_version()
    if manifest.get("version") != version:
        problems.append(f"version is {manifest.get('version')}, the source says {version}")
    if int(manifest.get("build", 0)) != build:
        problems.append(f"build is {manifest.get('build')}, the source says {build}")

    # The address must be the release asset for *this* version. A manifest
    # whose url drifts to a moving target is worse than a broken one: it
    # would download a different build than the sha256 beside it describes,
    # and the updater would refuse it with a checksum error that points
    # nowhere near the actual mistake.
    wanted = release_urls(version, "PyCmd.exe", manifest.get("tag", ""))
    if manifest.get("url") != wanted["url"]:
        problems.append(f"url is {manifest.get('url')}, "
                        f"it should be {wanted['url']}")
    if manifest.get("latestUrl") != wanted["latestUrl"]:
        problems.append("latestUrl is missing or wrong")

    name = os.path.basename(manifest.get("url", ""))
    # Where a freshly built one sits: CI builds into dist-windows/build, and
    # build.ps1 does the same, so the checksum can be verified on the machine
    # that just made it without the exe ever being committed.
    exe = next((path for path in (os.path.join(DIST, "build", name),
                                  os.path.join(DIST, name))
                if os.path.isfile(path)), os.path.join(DIST, name))
    if not name:
        problems.append("there is no download address in it")
    elif not manifest.get("sha256"):
        # Seeded but not built. Say so plainly rather than passing silently:
        # somebody reading the output should know there is no exe behind this.
        if problems:
            return _report(problems)
        print(f"dist-windows/latest.json is seeded for {version} (build {build}) "
              "and has no build behind it yet.")
        print("  Build one with windows\\build\\build.ps1, or push a windows-v tag.")
        return 0
    elif not os.path.isfile(exe):
        # Not a failure on its own. The exe is built on Windows and this check
        # runs everywhere, so a checkout without one is the normal case for
        # anybody who has not built it yet - it just cannot be verified.
        print(f"dist-windows/latest.json describes {name}, which is not in this checkout.")
        print(f"  version {version}, build {build} - "
              "build it on Windows to check the checksum.")
        return 0 if not problems else _report(problems)
    else:
        size = os.path.getsize(exe)
        if size != int(manifest.get("bytes", 0)):
            problems.append(f"bytes is {manifest.get('bytes')}, the file is {size}")
        actual = digest(exe)
        if actual != manifest.get("sha256"):
            problems.append(f"sha256 does not match the file ({actual})")

    if problems:
        return _report(problems)
    print(f"dist-windows/latest.json is good: {version} (build {build}), "
          f"{manifest.get('bytes')} bytes")
    return 0


def _report(problems) -> int:
    print("dist-windows/latest.json is wrong:", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", nargs="?", help="the built PyCmd exe to describe")
    parser.add_argument("--notes", default="", help="one line shown in the app")
    parser.add_argument("--tag", default="",
                        help="the release tag being built, when there is one")
    parser.add_argument("--agrees-with-tag", metavar="TAG", default="",
                        help="check the source claims the version this tag names")
    parser.add_argument("--seed", action="store_true",
                        help="write a manifest for a build that does not exist yet")
    args = parser.parse_args(argv)
    if args.agrees_with_tag:
        return agrees_with_tag(args.agrees_with_tag)
    if args.seed:
        return seed(args.notes)
    return write(args.exe, args.notes, args.tag) if args.exe else check()


if __name__ == "__main__":
    raise SystemExit(main())
