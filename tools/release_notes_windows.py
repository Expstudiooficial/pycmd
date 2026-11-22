"""Prints the release text for a Windows version, from dist-windows/README.md.

    python tools/release_notes_windows.py 4.0 <sha256> > release-notes.md

The changelog is written once, in the README, and the GitHub release shows the
same words - so the two cannot drift apart.
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv) -> int:
    version = argv[0]
    digest = argv[1] if len(argv) > 1 else ""
    with open(os.path.join(HERE, "dist-windows", "README.md"), encoding="utf-8") as handle:
        text = handle.read()
    # A tag of 4.0.0 is version 4.0: trailing ".0"s are dropped to find the
    # changelog section, which is headed with the short form.
    short = re.sub(r"(\.0)+$", "", version) or version
    found = None
    for name in dict.fromkeys((version, short, short + ".0")):
        found = re.search(r"^## What is new in " + re.escape(name) + r"\n(.*?)(?=^## |\Z)",
                          text, re.S | re.M)
        if found:
            break
    body = found.group(1).strip() if found else "See dist-windows/README.md."
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"**PyCmd for Windows {version}.** One exe, nothing to install. "
          "Windows 10 or newer, 64-bit. Download `PyCmd.exe` below.\n")
    print(body)
    if digest:
        print(f"\n---\n\nSHA-256 of `PyCmd.exe`: `{digest}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
