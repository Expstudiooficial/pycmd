#!/usr/bin/env python3
"""Every package in packages/ passes its own tests, and the index is current."""
import hashlib
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app", "src", "main", "python"))
from pycmd_langs import pcmd_engine  # noqa: E402

PACKAGES = os.path.join(HERE, "..", "packages")
eng = pcmd_engine.engine()
if eng is None:
    print("SKIP: no PyCmd engine (build it: ./gradlew -p lang jar)")
    raise SystemExit(0)
failed = []
index = json.load(open(os.path.join(PACKAGES, "index.json"), encoding="utf-8"))
listed = {row["name"]: row for row in index["packages"]}
for name in sorted(os.listdir(PACKAGES)):
    if not name.endswith(".pcmd"):
        continue
    path = os.path.join(PACKAGES, name)
    text = open(path, encoding="utf-8").read()
    row = listed.get(name[:-5])
    if row is None or row["sha256"] != hashlib.sha256(text.encode()).hexdigest():
        failed.append(f"{name}: index.json is out of date - run tools/make_packages_index.py")
        continue
    out = io.StringIO()
    reply = eng.test(text, path=path, stdout=out)
    if not reply.get("ok") or not reply.get("passed"):
        failed.append(f"{name}: {out.getvalue().strip()[-200:]}")
    else:
        print(f"  PASS  {name[:-5]} ({reply['passed']} test{'s' if reply['passed'] != 1 else ''})")
if failed:
    print("\n".join("  FAIL  " + f for f in failed))
    raise SystemExit(1)
print(f"all {len(listed)} packages pass their tests")
