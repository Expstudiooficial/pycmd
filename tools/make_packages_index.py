#!/usr/bin/env python3
"""Writes packages/index.json from the packages themselves.

Every package starts with two comment lines:
    # name: what it does
    # version: 1.0
and may add `# needs: other, another` for packages it uses. `pcmd add`
reads the index this writes.
"""
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGES = os.path.join(HERE, "..", "packages")


def main():
    rows = []
    for name in sorted(os.listdir(PACKAGES)):
        if not name.endswith(".pcmd"):
            continue
        path = os.path.join(PACKAGES, name)
        text = open(path, encoding="utf-8").read()
        head = text.splitlines()[:4]
        m = re.match(r"#\s*([a-z0-9_]+):\s*(.+)", head[0] if head else "")
        if not m or m.group(1) != name[:-5]:
            raise SystemExit(f"{name}: the first line must be '# {name[:-5]}: what it does'")
        version = next((re.sub(r"#\s*version:\s*", "", h) for h in head if "version:" in h), "1.0")
        needs = next((h.split(":", 1)[1] for h in head if h.startswith("# needs:")), "")
        rows.append({
            "name": name[:-5], "description": m.group(2).strip(), "version": version.strip(),
            "file": name, "needs": [n.strip() for n in needs.split(",") if n.strip()],
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "bytes": len(text.encode("utf-8")),
            "tests": text.count('\ntest "'),
        })
    index = {"format": 1, "language": "PyCmd", "count": len(rows), "packages": rows}
    with open(os.path.join(PACKAGES, "index.json"), "w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=1)
        handle.write("\n")
    print(f"packages/index.json: {len(rows)} packages")


if __name__ == "__main__":
    main()
