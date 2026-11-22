"""Line endings: the editor gets "\n", the file keeps whatever it had.

Windows files usually end their lines with "\r\n". Handed to the editor as
they are, every line carries an invisible "\r" - which the editor then counts,
searches and saves - and a file saved from PyCmd silently changed every line
ending it had. So text is read with "\n" only, the file's own style is noted,
and a save writes that style back: a Windows file stays a Windows file, and a
file written on Linux or a Mac keeps its "\n".
"""

from __future__ import annotations

import os

CRLF = "crlf"
LF = "lf"


def detect(raw: bytes) -> str:
    """CRLF if most of the line breaks in this text are CRLF, else LF."""
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    return CRLF if crlf and crlf >= lf else LF


def of_file(path: str) -> str:
    """The style an existing file uses; LF for a file that is not there yet."""
    try:
        with open(path, "rb") as handle:
            return detect(handle.read(1 << 20))
    except OSError:
        return LF


def for_editor(text: str) -> str:
    return text.replace("\r\n", "\n")


def for_file(text: str, style: str) -> str:
    text = text.replace("\r\n", "\n")
    return text.replace("\n", "\r\n") if style == CRLF else text


def keep(path: str, text: str) -> str:
    """The text as it should be written over `path`, in that file's own style."""
    return for_file(text, of_file(path) if os.path.exists(path) else LF)
