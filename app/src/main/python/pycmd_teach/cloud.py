"""A PyCmd account: Learn progress on every device, through pycmd.pages.dev.

The app holds no database credential. It talks to the website's API
(website/lib/pycmd-api.js in the Android repository), and only the website
talks to the database. What is sent:

* At sign-up and sign-in, the username and a key: the password stretched with
  PBKDF2-SHA256, 600,000 rounds, salted with the username. The password
  itself never leaves the device, and the website stretches the key again
  before keeping it.
* After that, a session token (kept in account.json beside the progress
  file, in the app's own storage) and the progress file.

Sync is a merge, never "last one wins": lessons finished on either device
stay finished, the streak comes from whichever device saw the later day, and
a course reset on one device is reset on the others. The server refuses a
save from a device that has not seen the latest copy (409), and that device
merges the newer copy in and saves again.

Export and import write and read the same progress as a .json file, for a
backup or a move without an account.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

SERVER = os.environ.get("PYCMD_CLOUD_URL", "https://pycmd.pages.dev/api/v1").rstrip("/")
TIMEOUT = 20
#: The client half of the password stretch. Changing either of these
#: changes every key, which signs everybody out for good - a new scheme gets
#: a new prefix and a migration, it does not edit these.
KDF_ROUNDS = 600_000
KDF_PREFIX = "pycmd-account-v1:"
MIN_PASSWORD = 8
MAX_PASSWORD = 128
#: How often progress is pushed while lessons are being finished.
SYNC_EVERY = 90

EXPORT_FORMAT = "pycmd-learn-progress"

_COMMON = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwertyuiop", "qwerty123", "11111111", "00000000", "iloveyou", "abcdefgh",
    "abc12345", "letmein1", "welcome1", "football", "baseball", "sunshine",
    "princess", "dragon12", "monkey12", "pycmd123", "passw0rd", "aaaaaaaa",
}

_lock = threading.RLock()
_state = {"device": "", "app": "PyCmd", "last_error": "", "syncing": False,
          "last_try": 0.0}


class CloudError(Exception):
    """Something the person should read: a wrong password, no connection."""

    def __init__(self, message, status=0, body=None):
        super().__init__(message)
        self.status = status
        self.body = body or {}


# ------------------------------------------------------------------ setup

def set_device(name: str = "", app: str = "") -> dict:
    """What this device is called in the account's list of sessions."""
    if name:
        _state["device"] = str(name)[:40]
    if app:
        _state["app"] = str(app)[:40]
    return status()


def _device() -> str:
    return _state["device"] or f"{platform.system() or 'device'}"


def _teach():
    import pycmd_teach

    return pycmd_teach


def _account_path() -> str:
    return os.path.join(os.path.dirname(_teach()._progress_path()), "account.json")


def _read_account() -> dict:
    try:
        with open(_account_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_account(data: dict) -> None:
    path = _account_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, path)


def _forget_account() -> None:
    try:
        os.remove(_account_path())
    except OSError:
        pass


# ------------------------------------------------------------------ checks

def username_problem(name: str) -> str:
    """The same rules as the website: 3-24 of letters, digits, _ . -."""
    import re

    name = (name or "").strip()
    if len(name) < 3:
        return "A username has at least 3 characters."
    if len(name) > 24:
        return "A username has at most 24 characters."
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9_.-]{1,22})[A-Za-z0-9]", name):
        return "Use letters, digits, _ . and -, starting and ending with a letter or digit."
    return ""


def password_problem(password: str, username: str = "") -> str:
    """Long enough, not the username, not one of the passwords everybody tries
    first. No rules about symbols: length is what makes a password hard."""
    if len(password or "") < MIN_PASSWORD:
        return f"A password has at least {MIN_PASSWORD} characters."
    if len(password) > MAX_PASSWORD:
        return f"A password has at most {MAX_PASSWORD} characters."
    lowered = password.lower()
    if username and lowered == username.strip().lower():
        return "The password cannot be the username."
    if lowered in _COMMON or len(set(password)) < 3:
        return "That password is too easy to guess. Pick another."
    return ""


def derive_key(username: str, password: str) -> str:
    """The password, stretched, as the website expects it: 64 hex digits.

    The website's own sign-in page has to make exactly the same key:
    PBKDF2-SHA256 over the NFC-normalised password, salt
    "pycmd-account-v1:" + the username in lower case, 600,000 rounds, 32
    bytes, lower-case hex.
    """
    salt = (KDF_PREFIX + username.strip().lower()).encode("utf-8")
    secret = unicodedata.normalize("NFC", password).encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", secret, salt, KDF_ROUNDS, 32).hex()


# ------------------------------------------------------------------- HTTP

def _call(method: str, path: str, body=None, token: str = "", allow=()):
    url = SERVER + "/" + path.lstrip("/")
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json", "User-Agent": _state["app"]}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        try:
            reply = json.loads(error.read().decode("utf-8") or "{}")
        except ValueError:
            reply = {}
        if error.code in allow:
            return error.code, reply
        if reply.get("signed_out"):
            _forget_account()
        message = reply.get("error") or {
            404: "pycmd.pages.dev does not have accounts yet.",
            503: "The PyCmd database is not reachable right now.",
        }.get(error.code, f"pycmd.pages.dev answered {error.code}.")
        raise CloudError(message, error.code, reply) from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        reason = getattr(error, "reason", error)
        raise CloudError(f"Could not reach pycmd.pages.dev ({reason}). "
                         "Check the connection and try again.") from None
    except ValueError:
        raise CloudError("pycmd.pages.dev sent back something that is not JSON.") from None


def _token() -> str:
    return _read_account().get("token", "")


# ---------------------------------------------------------------- account

def status() -> dict:
    account = _read_account()
    return {
        "ok": True,
        "signed_in": bool(account.get("token")),
        "username": account.get("username", ""),
        "server": SERVER,
        "synced_at": account.get("synced_at", 0),
        "synced_version": account.get("version", 0),
        "syncing": _state["syncing"],
        "last_error": _state["last_error"],
        "device": _device(),
    }


def check_username(name: str) -> dict:
    problem = username_problem(name)
    if problem:
        return {"ok": True, "available": False, "reason": problem}
    _, reply = _call("GET", "username/" + urllib.parse.quote(name.strip(), safe=""))
    return {"ok": True, "available": bool(reply.get("available")),
            "reason": reply.get("reason", "")}


def _signed_in(reply: dict) -> dict:
    _write_account({"username": reply["username"], "token": reply["token"],
                    "synced_at": 0, "version": 0, "server": SERVER})
    _state["last_error"] = ""
    synced = sync()
    return {**status(), "sync": synced}


def signup(username: str, password: str) -> dict:
    username = (username or "").strip()
    problem = username_problem(username) or password_problem(password, username)
    if problem:
        return {"ok": False, "error": problem}
    key = derive_key(username, password)
    status_code, reply = _call("POST", "signup",
                               {"username": username, "key": key, "device": _device()},
                               allow=(409,))
    if status_code == 409:
        return {"ok": False, "error": reply.get("error", "That username is taken."),
                "field": "username"}
    return _signed_in(reply)


def login(username: str, password: str) -> dict:
    username = (username or "").strip()
    if not username or not password:
        return {"ok": False, "error": "Type your username and password."}
    key = derive_key(username, password)
    status_code, reply = _call("POST", "login",
                               {"username": username, "key": key, "device": _device()},
                               allow=(401, 429))
    if status_code != 200:
        return {"ok": False, "error": reply.get("error", "Wrong username or password.")}
    return _signed_in(reply)


def logout() -> dict:
    token = _token()
    if token:
        try:
            _call("POST", "logout", {}, token=token, allow=(401,))
        except CloudError:
            pass  # Offline: the token is forgotten here either way.
    _forget_account()
    return status()


def change_password(old: str, new: str) -> dict:
    account = _read_account()
    if not account.get("token"):
        return {"ok": False, "error": "Sign in first."}
    username = account["username"]
    problem = password_problem(new, username)
    if problem:
        return {"ok": False, "error": problem}
    code, reply = _call("POST", "password", {"old_key": derive_key(username, old),
                                             "new_key": derive_key(username, new)},
                        token=account["token"], allow=(401, 429))
    if code != 200:
        return {"ok": False, "error": reply.get("error", "The current password is wrong.")}
    return {**status(), "message": "Password changed. Other devices sign in again."}


def delete_account(password: str) -> dict:
    account = _read_account()
    if not account.get("token"):
        return {"ok": False, "error": "Sign in first."}
    code, reply = _call("POST", "account/delete",
                        {"key": derive_key(account["username"], password)},
                        token=account["token"], allow=(401, 429))
    if code != 200:
        return {"ok": False, "error": reply.get("error", "The password is wrong.")}
    _forget_account()
    return {**status(), "message": "The account is deleted. Progress on this device stays."}


# ------------------------------------------------------------------ merge

def _ids(value) -> list:
    return [str(x) for x in value] if isinstance(value, list) else []


def merge(local: dict, remote: dict) -> dict:
    """Two devices' progress as one. Order does not matter: merge(a, b) and
    merge(b, a) give the same lessons, streak and XP."""
    local = local or {}
    remote = remote or {}
    out = {}
    stamp_l = float(local.get("updated_at") or 0)
    stamp_r = float(remote.get("updated_at") or 0)

    cleared = {}
    for side in (local, remote):
        for course, when in (side.get("cleared") or {}).items():
            try:
                cleared[course] = max(cleared.get(course, 0), float(when))
            except (TypeError, ValueError):
                continue
    out["cleared"] = cleared

    def kept(side, stamp, course):
        # A side that last changed before a reset of this course (or of
        # everything) is older than the reset: its lessons there are gone.
        when = max(cleared.get(course, 0), cleared.get("*", 0))
        return stamp >= when

    done = {}
    for side, stamp in ((local, stamp_l), (remote, stamp_r)):
        for course, rows in (side.get("done") or {}).items():
            if not kept(side, stamp, course):
                continue
            merged = done.setdefault(course, [])
            seen = set(merged)
            for lesson_id in _ids(rows):
                if lesson_id not in seen:
                    merged.append(lesson_id)
                    seen.add(lesson_id)
    for course in done:
        done[course] = sorted(done[course], key=_lesson_order)
    out["done"] = {c: rows for c, rows in sorted(done.items()) if rows}

    missed = {}
    for course in sorted(set(local.get("missed") or {}) | set(remote.get("missed") or {})):
        rows = []
        l_missed = set(_ids((local.get("missed") or {}).get(course))) \
            if kept(local, stamp_l, course) else set()
        r_missed = set(_ids((remote.get("missed") or {}).get(course))) \
            if kept(remote, stamp_r, course) else set()
        l_done = set(_ids((local.get("done") or {}).get(course)))
        r_done = set(_ids((remote.get("done") or {}).get(course)))
        for lesson_id in sorted(l_missed | r_missed, key=_lesson_order):
            # Still to put right, unless the other device has put it right:
            # finished there and not missed there.
            if lesson_id in l_missed and lesson_id in r_done and lesson_id not in r_missed:
                continue
            if lesson_id in r_missed and lesson_id in l_done and lesson_id not in l_missed:
                continue
            rows.append(lesson_id)
        if rows:
            missed[course] = rows
    out["missed"] = missed

    total = sum(len(rows) for rows in out["done"].values())
    out["xp"] = max(int(local.get("xp") or 0), int(remote.get("xp") or 0), total * 10)

    def later(key):
        a, b = str(local.get(key) or ""), str(remote.get(key) or "")
        return local if a >= b else remote

    streak_side = later("last_day")
    out["last_day"] = str(streak_side.get("last_day") or "")
    out["streak"] = int(streak_side.get("streak") or 0)
    if str(local.get("last_day") or "") == str(remote.get("last_day") or ""):
        out["streak"] = max(int(local.get("streak") or 0), int(remote.get("streak") or 0))
    out["best_streak"] = max(int(local.get("best_streak") or 0),
                             int(remote.get("best_streak") or 0), out["streak"])

    day_side = later("day")
    out["day"] = str(day_side.get("day") or "")
    out["day_count"] = int(day_side.get("day_count") or 0)
    if str(local.get("day") or "") == str(remote.get("day") or ""):
        out["day_count"] = max(int(local.get("day_count") or 0),
                               int(remote.get("day_count") or 0))

    last_l, last_r = local.get("last") or {}, remote.get("last") or {}
    out["last"] = last_l if float(last_l.get("at") or 0) >= float(last_r.get("at") or 0) \
        else last_r
    newer = local if stamp_l >= stamp_r else remote
    out["goal"] = int(newer.get("goal") or local.get("goal") or remote.get("goal") or 10)
    out["updated_at"] = max(stamp_l, stamp_r)
    return out


def _lesson_order(lesson_id: str):
    from pycmd_teach import KINDS

    try:
        unit, topic, kind = lesson_id.split(".")
        return (int(unit), int(topic), KINDS.index(kind) if kind in KINDS else 99, "")
    except ValueError:
        return (10 ** 9, 0, 0, lesson_id)


def _comparable(data: dict) -> str:
    """Two progress files that differ only in when they were written are the
    same progress."""
    return json.dumps({k: v for k, v in (data or {}).items() if k != "updated_at"},
                      sort_keys=True)


# ------------------------------------------------------------------- sync

def sync() -> dict:
    """Pulls, merges, pushes. Safe to call at any time; does nothing signed out."""
    teach = _teach()
    with _lock:
        account = _read_account()
        token = account.get("token")
        if not token:
            return {"ok": True, "signed_in": False}
        _state["syncing"] = True
        _state["last_try"] = time.time()
        try:
            for _attempt in range(4):
                _, remote = _call("GET", "progress", token=token)
                with teach._PROGRESS_LOCK:
                    local = teach._read_progress()
                    merged = merge(local, remote.get("data") or {})
                    if _comparable(merged) != _comparable(local):
                        teach._write_progress(merged, stamp=False)
                if remote.get("data") is not None and \
                        _comparable(merged) == _comparable(remote["data"]):
                    version = remote.get("version", 0)
                    break
                code, saved = _call("PUT", "progress",
                                    {"data": merged, "base_version": remote.get("version", 0),
                                     "device": _device()}, token=token, allow=(409,))
                if code == 200:
                    version = saved.get("version", 0)
                    break
                # Somebody else saved in between: go round again with theirs.
            else:
                raise CloudError("Another device keeps saving at the same moment. "
                                 "Try again in a minute.")
            account = _read_account()
            if account.get("token") == token:
                account.update(synced_at=int(time.time()), version=version)
                _write_account(account)
            _state["last_error"] = ""
            return {"ok": True, "signed_in": True, "version": version,
                    "lessons": sum(len(r) for r in merged.get("done", {}).values())}
        except CloudError as error:
            _state["last_error"] = str(error)
            return {"ok": False, "error": str(error), "signed_in": bool(_token())}
        finally:
            _state["syncing"] = False


def sync_soon(force: bool = False) -> None:
    """A sync in the background, if one is due: the app never waits on the
    network to show a lesson."""
    if not _token() or _state["syncing"]:
        return
    if not force and time.time() - _state["last_try"] < SYNC_EVERY:
        return
    _state["last_try"] = time.time()
    threading.Thread(target=sync, name="pycmd-sync", daemon=True).start()


# ---------------------------------------------------------- export, import

def export_text(app: str = "") -> dict:
    teach = _teach()
    data = teach._read_progress()
    done = sum(len(rows) for rows in (data.get("done") or {}).values())
    document = {
        "format": EXPORT_FORMAT, "version": 1,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "app": app or _state["app"], "lessons_done": done, "progress": data,
    }
    stamp = time.strftime("%Y-%m-%d", time.localtime())
    return {"ok": True, "text": json.dumps(document, indent=1),
            "filename": f"pycmd-progress-{stamp}.json", "lessons": done}


def _valid_progress(data) -> str:
    if not isinstance(data, dict):
        return "That file does not hold PyCmd progress."
    done = data.get("done", {})
    if not isinstance(done, dict):
        return "That file's lessons are not in the right shape."
    for course, rows in done.items():
        if not isinstance(course, str) or not isinstance(rows, list) or \
                not all(isinstance(r, str) and len(r) < 40 for r in rows):
            return "That file's lessons are not in the right shape."
    return ""


def import_text(text: str, mode: str = "merge") -> dict:
    """Reads an exported file. "merge" adds its lessons to these; "replace"
    makes this device's progress exactly the file's."""
    teach = _teach()
    if len(text or "") > 5 * 1024 * 1024:
        return {"ok": False, "error": "That file is too big to be PyCmd progress."}
    try:
        document = json.loads(text)
    except ValueError:
        return {"ok": False, "error": "That file is not JSON."}
    if isinstance(document, dict) and document.get("format") == EXPORT_FORMAT:
        data = document.get("progress")
    elif isinstance(document, dict) and "done" in document:
        data = document  # A bare progress file, copied out of the app folder.
    else:
        return {"ok": False, "error": "That is not a PyCmd progress file."}
    problem = _valid_progress(data)
    if problem:
        return {"ok": False, "error": problem}
    clean = {k: v for k, v in data.items() if k in teach._DEFAULT}
    with teach._PROGRESS_LOCK:
        local = teach._read_progress()
        before = sum(len(r) for r in local.get("done", {}).values())
        if mode == "replace":
            merged = dict(teach._DEFAULT, **clean)
            # Replacing is a reset followed by the file: other devices forget
            # what this one forgot, the next time they sync.
            merged["cleared"] = {"*": time.time()}
            merged["updated_at"] = time.time()
        else:
            merged = merge(local, dict(clean, updated_at=time.time()))
        teach._write_progress(merged, stamp=False)
    after = sum(len(r) for r in merged.get("done", {}).values())
    sync_soon(force=True)
    return {"ok": True, "lessons": after, "added": max(0, after - before), "mode": mode,
            **teach.totals()}
