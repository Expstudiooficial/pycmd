#!/usr/bin/env python3
"""Accounts, sync and export, end to end: the real client (pycmd_teach.cloud)
against the real website handler (website/lib/pycmd-api.js), served by Node
over SQLite - two "devices", each with its own progress folder.

    python3 tools/test_account.py      (needs Node 22 or newer)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app", "src", "main", "python"))

import pycmd_teach  # noqa: E402
from pycmd_teach import cloud  # noqa: E402

PASSED = 0
FAILED: list = []

#: derive_key("Tester", "correct horse staple"), for the website to check
#: its own implementation against.
TEST_VECTOR = "423ab8b3a7d9d795774e1b8986a53c2ecc9f3cf41f73899a09d46571da0076d8"


def check(name, condition, detail=""):
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")
        print(f"  FAIL  {name}  {str(detail)[:300]}")


class Device:
    """One app install: its own folder, switched to before every call."""

    def __init__(self, name):
        self.name = name
        self.folder = tempfile.mkdtemp(prefix=f"cloud-{name}-")

    def __enter__(self):
        pycmd_teach.configure(self.folder)
        cloud.set_device(self.name)
        return self

    def __exit__(self, *exc):
        return False

    def api(self, name, first="", second="", third=""):
        with self:
            return json.loads(pycmd_teach.api(name, first, second, third))


def merge_checks():
    """merge() on its own: no server needed."""
    a = {"done": {"python": ["0.0.read", "0.1.read"]}, "xp": 20, "streak": 3,
         "last_day": "2026-11-20", "best_streak": 5, "missed": {"python": ["0.2.fill"]},
         "last": {"course": "python", "lesson": "0.1.read", "at": 100.0},
         "updated_at": 100.0}
    b = {"done": {"python": ["0.0.read", "1.0.read"], "go": ["0.0.read"]}, "xp": 30,
         "streak": 1, "last_day": "2026-11-25", "best_streak": 2,
         "missed": {"python": ["0.3.fill"]},
         "last": {"course": "go", "lesson": "0.0.read", "at": 200.0}, "updated_at": 200.0}
    ab, ba = cloud.merge(a, b), cloud.merge(b, a)
    check("merge is the same both ways round", cloud._comparable(ab) == cloud._comparable(ba),
          (ab, ba))
    check("merge keeps every finished lesson",
          ab["done"] == {"go": ["0.0.read"], "python": ["0.0.read", "0.1.read", "1.0.read"]},
          ab["done"])
    check("XP is never less than ten a lesson", ab["xp"] == 40, ab["xp"])
    check("the streak comes from the later day", (ab["streak"], ab["last_day"]) ==
          (1, "2026-11-25"), ab)
    check("the best streak is the best of both", ab["best_streak"] == 5, ab)
    check("Continue goes to the lesson opened last", ab["last"]["course"] == "go", ab["last"])
    check("misses from both are kept", ab["missed"] == {"python": ["0.2.fill", "0.3.fill"]},
          ab["missed"])
    fixed = dict(b, done={"python": ["0.2.fill"]}, missed={})
    check("a miss put right on the other device is cleared",
          cloud.merge(a, fixed)["missed"] == {}, cloud.merge(a, fixed)["missed"])
    reset = dict(b, done={}, cleared={"python": 150.0}, updated_at=150.0)
    merged = cloud.merge(a, reset)
    check("a course reset later than the other device's last change stays reset",
          "python" not in merged["done"], merged["done"])
    newer = dict(a, updated_at=300.0)
    check("work done after a reset is kept", "python" in cloud.merge(newer, reset)["done"])
    everything = dict(b, done={}, cleared={"*": 150.0}, updated_at=150.0)
    check("a full reset clears every course from older copies",
          cloud.merge(a, everything)["done"] == {}, cloud.merge(a, everything)["done"])


def rules_checks():
    check("short usernames are refused", cloud.username_problem("ab") != "")
    check("odd characters are refused", cloud.username_problem("a b c") != "")
    check("a normal username is fine", cloud.username_problem("Ana_99") == "")
    check("short passwords are refused", cloud.password_problem("short") != "")
    check("the username as password is refused",
          cloud.password_problem("anabanana", "AnaBanana") != "")
    check("common passwords are refused", cloud.password_problem("password123") != "")
    check("aaaaaaaa-style passwords are refused", cloud.password_problem("abababab") != "")
    check("a long passphrase is fine", cloud.password_problem("correct horse staple") == "")
    started = time.monotonic()
    key = cloud.derive_key("Ana", "correct horse staple")
    took = time.monotonic() - started
    check("the key is 64 hex digits", len(key) == 64 and int(key, 16) >= 0, key)
    check("the key does not depend on the username's case",
          key == cloud.derive_key("ana", "correct horse staple"))
    check("the key depends on the username",
          key != cloud.derive_key("bob", "correct horse staple"))
    # The website's own sign-in page must make the same key, so the value is
    # pinned here and in website/README.md - and made again with WebCrypto,
    # the way a browser would.
    check("the key matches the published test vector",
          cloud.derive_key("Tester", "correct horse staple") == TEST_VECTOR,
          cloud.derive_key("Tester", "correct horse staple"))
    if shutil.which("node"):
        script = (
            "const s = new TextEncoder();"
            "const m = await crypto.subtle.importKey('raw',"
            " s.encode('correct horse staple'.normalize('NFC')), 'PBKDF2', false, ['deriveBits']);"
            "const b = await crypto.subtle.deriveBits({name: 'PBKDF2', hash: 'SHA-256',"
            " salt: s.encode('pycmd-account-v1:' + 'Tester'.toLowerCase()),"
            " iterations: 600000}, m, 256);"
            "console.log([...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0'))"
            ".join(''));")
        done = subprocess.run(["node", "--input-type=module", "-e", script],
                              capture_output=True, text=True, timeout=120)
        check("a browser's WebCrypto makes the same key", done.stdout.strip() == TEST_VECTOR,
              done.stdout + done.stderr)
    print(f"  one key takes {took:.2f}s here")


def server_checks(port):
    cloud.SERVER = f"http://127.0.0.1:{port}/api/v1"
    phone, pc = Device("phone"), Device("pc")

    # ---- signing up
    reply = phone.api("username", "Ana")
    check("a free name is free", reply.get("available") is True, reply)
    reply = phone.api("signup", "Ana", "short")
    check("a weak password is refused before anything is sent", not reply["ok"], reply)
    reply = phone.api("complete", "python", "0.0.read")
    check("a lesson finished before signing up", reply.get("ok"), reply)
    reply = phone.api("signup", "Ana", "correct horse staple")
    check("sign up works", reply.get("ok") and reply.get("signed_in"), reply)
    check("and syncs what was done before", reply.get("sync", {}).get("ok"), reply)
    reply = pc.api("signup", "ana", "another good passphrase")
    check("the same name in another case is taken", not reply["ok"] and
          "taken" in reply.get("error", ""), reply)
    reply = pc.api("username", "ANA")
    check("and the name check says so", reply.get("available") is False, reply)

    # ---- the other device
    reply = pc.api("login", "Ana", "wrong password!!")
    check("a wrong password is refused", not reply["ok"], reply)
    reply = pc.api("login", "ANA", "correct horse staple")
    check("sign in from the second device", reply.get("ok") and reply.get("signed_in"), reply)
    with pc:
        done = pycmd_teach._read_progress()["done"]
    check("the second device has the first device's lesson",
          done.get("python") == ["0.0.read"], done)

    # ---- both devices work, then sync
    pc.api("complete", "go", "0.0.read")
    phone.api("complete", "python", "0.0.predict")
    reply = pc.api("sync")
    check("the PC syncs", reply.get("ok"), reply)
    reply = phone.api("sync")
    check("the phone syncs", reply.get("ok"), reply)
    reply = pc.api("sync")
    with phone:
        phone_done = pycmd_teach._read_progress()["done"]
    with pc:
        pc_done = pycmd_teach._read_progress()["done"]
    check("after syncing both ways, both have everything",
          phone_done == pc_done == {"go": ["0.0.read"],
                                    "python": ["0.0.read", "0.0.predict"]},
          (phone_done, pc_done))

    # ---- a conflict: both save without seeing the other's copy
    phone.api("complete", "python", "0.1.read")
    pc.api("complete", "rust", "0.0.read")
    phone.api("sync")
    reply = pc.api("sync")  # Its base version is behind: 409, merge, save.
    check("a device that is behind merges and saves", reply.get("ok"), reply)
    phone.api("sync")
    with phone:
        phone_done = pycmd_teach._read_progress()["done"]
    check("nothing is lost in a conflict",
          "rust" in phone_done and "0.1.read" in phone_done.get("python", []), phone_done)

    # ---- a real race: the phone saves between the PC's read and its write
    phone.api("complete", "c", "0.0.read")
    pc.api("complete", "kotlin", "0.0.read")
    real_call = cloud._call
    raced = []

    def racing(method, path, *args, **kwargs):
        if method == "PUT" and not raced:
            raced.append(True)
            cloud._call = real_call
            phone.api("sync")  # Saves first, moving the version on.
            pc.__enter__()     # Back to the PC's folder for the rest of its sync.
        return real_call(method, path, *args, **kwargs)

    cloud._call = racing
    try:
        with pc:
            reply = cloud.sync()
    finally:
        cloud._call = real_call
    check("the race really happened", raced == [True], raced)
    check("the device that lost the race merges and saves", reply.get("ok"), reply)
    phone.api("sync")
    with phone:
        phone_done = pycmd_teach._read_progress()["done"]
    check("nothing is lost in a race", "c" in phone_done and "kotlin" in phone_done,
          phone_done)

    # ---- reset on one device reaches the other
    pc.api("reset", "rust")
    pc.api("sync")
    phone.api("sync")
    with phone:
        phone_done = pycmd_teach._read_progress()["done"]
    check("a course reset on one device is reset on the other", "rust" not in phone_done,
          phone_done)

    # ---- export and import
    reply = phone.api("export")
    check("export gives a file", reply.get("ok") and reply.get("filename", "").endswith(
        ".json"), reply)
    exported = reply["text"]
    fresh = Device("tablet")
    reply = fresh.api("import", "not json at all")
    check("importing junk is refused", not reply["ok"], reply)
    reply = fresh.api("import", json.dumps({"hello": 1}))
    check("importing a JSON file that is not progress is refused", not reply["ok"], reply)
    reply = fresh.api("import", exported, "merge")
    check("import merges the lessons in", reply.get("ok") and reply.get("lessons", 0) >= 3,
          reply)
    fresh.api("complete", "lua", "0.0.read")
    reply = fresh.api("import", exported, "replace")
    with fresh:
        tablet = pycmd_teach._read_progress()["done"]
    check("import can replace instead", reply.get("ok") and "lua" not in tablet, tablet)

    # ---- password change signs the other device out
    reply = phone.api("password", "wrong old one!!", "a brand new passphrase")
    check("changing the password needs the current one", not reply["ok"], reply)
    reply = phone.api("password", "correct horse staple", "a brand new passphrase")
    check("the password changes", reply.get("ok"), reply)
    reply = pc.api("sync")
    check("the other device is signed out", not pc.api("account").get("signed_in"), reply)
    reply = pc.api("login", "Ana", "a brand new passphrase")
    check("and signs in with the new password", reply.get("ok"), reply)

    # ---- the token is not the password, and no password is stored
    with phone:
        account_text = open(cloud._account_path(), encoding="utf-8").read()
    check("the account file holds no password",
          "brand new passphrase" not in account_text and "correct horse" not in account_text)

    # ---- cloud storage
    with phone:
        reply = phone.api("cloud_put", "code/hi.py", __import__("base64").b64encode(b"print(1)\n").decode())
    check("a file goes into cloud storage", reply.get("ok") and reply.get("size") == 9, reply)
    reply = pc.api("cloud_files")
    check("the other device lists it", [f["path"] for f in reply.get("files", [])] == ["code/hi.py"],
          reply)
    reply = pc.api("cloud_get", "code/hi.py")
    check("and reads it back", reply.get("text") == "print(1)\n", reply)
    folder = tempfile.mkdtemp()
    reply = pc.api("cloud_download", "code/hi.py", os.path.join(folder, "hi.py"))
    check("download writes the file", open(os.path.join(folder, "hi.py")).read() == "print(1)\n",
          reply)
    big = os.path.join(folder, "big.bin")
    with open(big, "wb") as handle:
        handle.write(b"x" * (810 * 1024))
    reply = pc.api("cloud_upload", big)
    check("a file bigger than the quota is refused", not reply.get("ok"), reply)
    reply = pc.api("cloud_delete", "code/hi.py")
    check("delete frees the space", reply.get("ok") and reply.get("used") == 0, reply)

    # ---- log out and delete
    reply = pc.api("logout")
    check("log out", reply.get("ok") and not reply.get("signed_in"), reply)
    reply = phone.api("delete_account", "nope nope nope")
    check("deleting needs the password", not reply["ok"], reply)
    reply = phone.api("delete_account", "a brand new passphrase")
    check("delete the account", reply.get("ok") and not reply.get("signed_in"), reply)
    with phone:
        kept = pycmd_teach._read_progress()["done"]
    check("progress on the device stays after deleting the account", "python" in kept, kept)
    reply = pc.api("username", "Ana")
    check("and the name is free again", reply.get("available") is True, reply)

    # ---- no connection is a sentence, not a traceback
    cloud.SERVER = "http://127.0.0.1:9/api/v1"
    reply = phone.api("login", "Ana", "whatever it is")
    check("no connection says so", not reply["ok"] and "Could not reach" in reply["error"],
          reply)


def main():
    merge_checks()
    rules_checks()
    if not shutil.which("node"):
        print("  SKIP  the server checks: no node here")
    else:
        server = subprocess.Popen(
            ["node", "--no-warnings", os.path.join(ROOT, "website", "test", "serve-local.mjs")],
            stdout=subprocess.PIPE, text=True)
        try:
            port = int(server.stdout.readline().strip())
            server_checks(port)
        finally:
            server.terminate()
            server.wait(timeout=30)
    print(f"\n{PASSED} checks passed")
    if FAILED:
        print(f"{len(FAILED)} FAILED")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
