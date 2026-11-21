"""Downloading things PyCmd installs, and checking they are what was asked for.

Every installer in this app ends up here: the portable toolchains, the Android
command-line tools, the JDK they need, and the PyCmd APK the Android Lab puts
on its device. One place means one set of rules, and the rules are the point:

* **Nothing is trusted because of where it came from.** A download is checked
  against the hash its own publisher states, whenever the publisher states
  one - Node's SHASUMS256, Go's JSON, Adoptium's API, Google's repository XML,
  the Zig index. A file that does not match is deleted, not used.
* **Nothing half-written is ever used.** Downloads land as ``name.part`` and
  are renamed only once they are complete and checked; archives are unpacked
  into a scratch folder and moved into place only when every file came out.
* **An archive cannot write outside its folder.** A zip entry called
  ``../../Windows/System32/x.dll`` is refused, which is the whole "zip slip"
  class of bug in one check.
* **Progress is reported**, because a 300 MB download that says nothing for
  four minutes reads exactly like a hang - which is what people meant when
  they said the toolchains "do not work".

Standard library only. The exe carries no requests, no certifi: urllib uses
Windows' own certificate store, which is the one the user's IT department
already manages.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

TIMEOUT = 60
CHUNK = 256 * 1024
USER_AGENT = "PyCmd-Windows (+https://github.com/expstudiooficial/pycmd)"


class FetchError(Exception):
    """A download or an unpack that did not work, with a reason a person can read."""


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    })


def text(url: str, timeout: float = TIMEOUT) -> str:
    """A small document, as text."""
    try:
        with urllib.request.urlopen(_request(url), timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        raise FetchError(f"{url} answered {error.code}") from None
    except (urllib.error.URLError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise FetchError(f"could not reach {_host(url)}: {reason}") from None


def json_doc(url: str, timeout: float = TIMEOUT):
    """A small JSON document."""
    body = text(url, timeout)
    try:
        return json.loads(body)
    except ValueError:
        raise FetchError(f"{url} did not answer with JSON") from None


def final_url(url: str, timeout: float = 30) -> str:
    """Where a redirecting URL ends up - used to learn a GitHub release's tag."""
    try:
        with urllib.request.urlopen(_request(url), timeout=timeout) as response:
            return response.geturl()
    except urllib.error.HTTPError as error:
        raise FetchError(f"{url} answered {error.code}") from None
    except (urllib.error.URLError, OSError) as error:
        raise FetchError(f"could not reach {_host(url)}: {getattr(error, 'reason', error)}") from None


def _host(url: str) -> str:
    try:
        return url.split("/")[2]
    except IndexError:
        return url


def readable(count: float) -> str:
    count = float(count or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if count < 1024 or unit == "GB":
            return f"{count:.0f} {unit}" if unit in ("B", "KB") else f"{count:.1f} {unit}"
        count /= 1024
    return f"{count:.1f} GB"


def download(url: str, target: str, write=None, sha256: str = "", sha1: str = "",
             timeout: float = TIMEOUT, cancelled=None, progress=None) -> str:
    """Downloads `url` to `target`, checking a hash if one is given.

    Returns the path. Raises FetchError with a sentence in it otherwise. The
    progress line is written at most every couple of seconds, so a fast
    connection does not flood the log and a slow one is never silent.
    """
    write = write or (lambda line: None)
    os.makedirs(os.path.dirname(os.path.abspath(target)) or ".", exist_ok=True)
    partial = target + ".part"
    digests = []
    if sha256:
        digests.append(("sha256", hashlib.sha256(), sha256.lower().strip()))
    if sha1:
        digests.append(("sha1", hashlib.sha1(), sha1.lower().strip()))

    write(f"[PyCmd] downloading {url}\n")
    started = time.time()
    try:
        with urllib.request.urlopen(_request(url), timeout=timeout) as response, \
                open(partial, "wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            got = 0
            said = 0.0
            while True:
                if cancelled is not None and cancelled():
                    raise FetchError("cancelled")
                block = response.read(CHUNK)
                if not block:
                    break
                handle.write(block)
                for _, digest, _ in digests:
                    digest.update(block)
                got += len(block)
                if progress is not None and total:
                    progress(got * 100 // total)
                now = time.time()
                if now - said > 2.0:
                    said = now
                    rate = got / max(now - started, 0.001)
                    if total:
                        percent = got * 100 // total
                        write(f"[PyCmd]   {percent:3d}%  {readable(got)} of {readable(total)}"
                              f"  ({readable(rate)}/s)\n")
                    else:
                        write(f"[PyCmd]   {readable(got)}  ({readable(rate)}/s)\n")
    except urllib.error.HTTPError as error:
        _remove(partial)
        raise FetchError(f"{_host(url)} answered {error.code} for {url.rsplit('/', 1)[-1]}") from None
    except (urllib.error.URLError, OSError) as error:
        _remove(partial)
        if isinstance(error, FetchError):
            raise
        raise FetchError(f"the download from {_host(url)} stopped: "
                         f"{getattr(error, 'reason', error)}") from None
    except FetchError:
        _remove(partial)
        raise

    for name, digest, wanted in digests:
        actual = digest.hexdigest()
        if actual != wanted:
            _remove(partial)
            raise FetchError(
                f"the file did not match its published {name} "
                f"(expected {wanted[:12]}..., got {actual[:12]}...) - it was deleted, "
                "not used. Try again; a mismatch twice means something between "
                "you and the server is changing the file.")
    if digests:
        write(f"[PyCmd]   checked: {', '.join(name for name, _, _ in digests)} matches\n")
    os.replace(partial, target)
    write(f"[PyCmd]   {readable(os.path.getsize(target))} in {time.time() - started:.0f}s\n")
    return target


def sha256_of(path: str) -> str:
    """The SHA-256 of a file on disk, or "" if it cannot be read."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(CHUNK), b""):
                digest.update(block)
    except OSError:
        return ""
    return digest.hexdigest()


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _safe_member(base: str, name: str) -> str:
    """Where an archive member would land, refusing anything outside `base`."""
    target = os.path.normpath(os.path.join(base, name))
    root = os.path.normpath(base)
    if target != root and not target.startswith(root + os.sep):
        raise FetchError(f"the archive tried to write outside its folder ({name})")
    return target


def unpack(archive: str, into: str, strip_top: bool = False, write=None) -> str:
    """Unpacks a .zip or .tar.* into `into`, atomically.

    `strip_top` drops a single top-level folder - the common "node-v22-win-x64/"
    wrapper - so the result is laid out as the files themselves rather than
    inside a folder whose name changes every release.
    """
    write = write or (lambda line: None)
    parent = os.path.dirname(os.path.abspath(into)) or "."
    os.makedirs(parent, exist_ok=True)
    scratch = tempfile.mkdtemp(prefix=".unpack-", dir=parent)
    write(f"[PyCmd] unpacking {os.path.basename(archive)}\n")
    try:
        lower = archive.lower()
        if lower.endswith(".zip"):
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.infolist():
                    _safe_member(scratch, member.filename)
                bundle.extractall(scratch)
                # zipfile drops the Unix permission bits, so a launcher script
                # comes out unrunnable. Windows has no such bits; elsewhere the
                # SDK's own `bin/android` script needs them back.
                if os.name != "nt":
                    for member in bundle.infolist():
                        mode = (member.external_attr >> 16) & 0o777
                        if mode and not member.is_dir():
                            os.chmod(os.path.join(scratch, member.filename), mode)
        elif ".tar" in lower or lower.endswith((".tgz", ".txz")):
            with tarfile.open(archive) as bundle:
                for member in bundle.getmembers():
                    _safe_member(scratch, member.name)
                    if member.issym() or member.islnk():
                        _safe_member(scratch, os.path.join(os.path.dirname(member.name),
                                                           member.linkname))
                if hasattr(tarfile, "tar_filter"):
                    bundle.extractall(scratch, filter="tar")
                else:
                    bundle.extractall(scratch)
        else:
            raise FetchError(f"PyCmd does not know how to unpack {os.path.basename(archive)}")

        source = scratch
        if strip_top:
            entries = [name for name in os.listdir(scratch) if not name.startswith(".")]
            if len(entries) == 1 and os.path.isdir(os.path.join(scratch, entries[0])):
                source = os.path.join(scratch, entries[0])

        if os.path.exists(into):
            shutil.rmtree(into, ignore_errors=True)
        shutil.move(source, into)
        return into
    except (zipfile.BadZipFile, tarfile.TarError) as error:
        raise FetchError(f"{os.path.basename(archive)} is damaged: {error}") from None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
