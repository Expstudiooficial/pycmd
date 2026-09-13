#!/usr/bin/env python3
"""Checks the Music Pro plugin: what it asks the app for, and what it refuses.

Nothing here makes a sound. The decks, the effects and the other apps' media
sessions are all Kotlin, so the only thing this plugin does about them is send
a request with a name and some numbers - and *that* is exactly what can be
checked on a laptop: install the plugin for real, load it through the same
machinery the app uses, call its exports the way the panel does, and look at
what came out of the action channel.

The catalogues are Python and are checked against their real shapes without
touching the network: the two parsers are handed the JSON those services
return and asked what they made of it.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLED = os.path.join(ROOT, "app", "src", "main", "assets", "plugins")
sys.path.insert(0, os.path.join(ROOT, "app", "src", "main", "python"))

import pycmd_plugins as plugins  # noqa: E402

FAILURES = []
REAL = sys.__stdout__


def say(text=""):
    REAL.write(str(text) + "\n")
    REAL.flush()


def check(name, condition, detail=""):
    if condition:
        say(f"  PASS  {name}")
    else:
        FAILURES.append(name)
        say(f"  FAIL  {name}  {detail}")


class FakeHost:
    """Catches everything the plugin asks the app to do."""

    def __init__(self):
        self.actions = []
        self.toasts = []
        self.messages = []
        self.logs = []

    def onPluginLog(self, level, message, detail):  # noqa: N802
        self.logs.append((level, message, detail))

    def onToast(self, message):  # noqa: N802
        self.toasts.append(message)

    def onPluginMessage(self, plugin_id, body):  # noqa: N802
        self.messages.append((plugin_id, json.loads(body)))

    def onPluginAction(self, plugin_id, action, detail):  # noqa: N802
        self.actions.append((action, json.loads(detail)))

    def asked(self, action):
        return [detail for name, detail in self.actions if name == action]

    def clear(self):
        self.actions.clear()
        self.messages.clear()


scratch = tempfile.mkdtemp(prefix="pycmd-music-pro-")
home = os.path.join(scratch, "plugins")
workspace = os.path.join(scratch, "workspace")
os.makedirs(workspace, exist_ok=True)
host = FakeHost()
plugins.configure(home, workspace, host)

installed = json.loads(
    plugins.install(os.path.join(BUNDLED, "music-pro"), "music-pro", "1"))

say("== it installs and loads ==")
check("the plugin installs", installed.get("ok"), installed)
loaded = json.loads(plugins.load("pycmd.music-pro"))
check("and loads", loaded.get("ok"), loaded)

listing = json.loads(plugins.listing())
row = next((p for p in listing["plugins"] if p["id"] == "pycmd.music-pro"), None)
check("it is listed", row is not None, listing)
check("and nothing about it is broken", row and not row.get("broken"), row)


def call(name, payload=None):
    """One export, the way the panel calls it.

    `call_export` wraps what an export returned in its own envelope - the
    outer `ok` says the call reached the export, the inner one says what the
    export thought of it. The panel's bridge unwraps it; so does this.
    """
    answer = json.loads(
        plugins.call_export("pycmd.music-pro", name, json.dumps(payload or {})))
    if not answer.get("ok"):
        return answer
    inner = answer.get("result")
    return inner if isinstance(inner, dict) else answer


say()
say("== the decks ==")
host.clear()
answer = call("load", {"deck": "a", "file": "/music/one.mp3", "title": "One"})
check("loading a deck is asked for", answer.get("ok"), answer)
asked = host.asked("mixer.load")
check("with the deck, the file and the title",
      asked and asked[0]["deck"] == "a" and asked[0]["path"] == "/music/one.mp3"
      and asked[0]["title"] == "One", asked)

check("a third deck is refused",
      not call("load", {"deck": "c", "file": "/music/one.mp3"})["ok"])
check("and a deck with nothing to put on it is too",
      not call("load", {"deck": "a"})["ok"])

host.clear()
for what in ("play", "pause", "cue", "eject"):
    call("deck_action", {"deck": "b", "what": what})
check("play, pause, cue and eject all reach the app",
      [name for name, _ in host.actions] ==
      ["mixer.play", "mixer.pause", "mixer.cue", "mixer.eject"],
      [name for name, _ in host.actions])
check("and something a deck cannot do is refused",
      not call("deck_action", {"deck": "a", "what": "explode"})["ok"])

host.clear()
call("deck_set", {"deck": "a", "rate": 1.5, "level": 0.8, "position": 4000})
check("tempo, level and position each go separately",
      sorted(name for name, _ in host.actions) ==
      ["mixer.gain", "mixer.seek", "mixer.tempo"],
      [name for name, _ in host.actions])
check("with the numbers as given",
      host.asked("mixer.tempo")[0]["rate"] == 1.5
      and host.asked("mixer.seek")[0]["position"] == 4000,
      host.actions)

host.clear()
call("deck_set", {"deck": "a", "loopStart": 1000, "loopEnd": 5000})
check("a loop is one request with both ends",
      host.asked("mixer.loop")[0]["start"] == 1000
      and host.asked("mixer.loop")[0]["end"] == 5000, host.actions)

host.clear()
call("fader", {"position": 0.25})
check("the crossfader carries its position",
      host.asked("mixer.fader")[0]["position"] == 0.25, host.actions)
host.clear()
call("fader", {"position": 4})
check("and a position off the end is pulled back",
      host.asked("mixer.fader")[0]["position"] == 1.0, host.actions)

say()
say("== the effects ==")
host.clear()
check("an effect is asked for", call("effect",
      {"deck": "a", "name": "reverb", "level": 0.5})["ok"])
check("with its name and level",
      host.asked("mixer.effect")[0]["name"] == "reverb"
      and host.asked("mixer.effect")[0]["level"] == 0.5, host.actions)
check("an effect nobody has is refused",
      not call("effect", {"deck": "a", "name": "autotune", "level": 1})["ok"])
check("and a level past the end is pulled back",
      call("effect", {"deck": "a", "name": "bass", "level": 9})["ok"]
      and host.asked("mixer.effect")[-1]["level"] == 1.0, host.actions)

host.clear()
call("band", {"deck": "b", "index": 2, "level": -0.5})
check("a band can be cut as well as boosted",
      host.asked("mixer.band")[0]["level"] == -0.5, host.actions)
host.clear()
call("flatten", {"deck": "b"})
check("and they can all go flat at once", host.asked("mixer.flatten"), host.actions)

say()
say("== the other apps ==")
host.clear()
call("app_control", {"package": "com.example.player", "what": "next"})
check("another app can be told to skip",
      host.asked("apps.control")[0]["what"] == "next"
      and host.asked("apps.control")[0]["package"] == "com.example.player",
      host.actions)
check("something an app cannot be told is refused",
      not call("app_control", {"what": "delete"})["ok"])

host.clear()
call("app_search", {"package": "com.example.player", "query": "blue monday"})
check("a search is handed over whole",
      host.asked("apps.search")[0]["query"] == "blue monday", host.actions)
check("and an empty search is not handed over",
      not call("app_search", {"query": "   "})["ok"])

host.clear()
call("ask_permission")
check("the permission screen is asked for, not granted",
      host.asked("apps.permission"), host.actions)

say()
say("== a download has to be one of ours ==")
check("http is refused", not call("fetch", {"url": "http://example.com/a.mp3"})["ok"])
check("a file path is refused", not call("fetch", {"url": "/etc/passwd"})["ok"])
check("and so is a javascript: url",
      not call("fetch", {"url": "javascript:alert(1)"})["ok"])
check("opening a link is https only",
      not call("open_link", {"url": "http://example.com"})["ok"])

say()
say("== the catalogues, without the network ==")
sys.path.insert(0, os.path.join(BUNDLED, "music-pro"))
import main as music_pro  # noqa: E402

jamendo = {
    "results": [
        {
            "id": 42, "name": "Blue Monday", "artist_name": "Somebody",
            "album_name": "An Album", "duration": 270,
            "audiodownload": "https://prod-1.storage.jamendo.com/download/42.mp3",
            "shareurl": "https://www.jamendo.com/track/42",
            "licenses": {"ccurl": "https://creativecommons.org/licenses/by/3.0/"},
        },
        # No https address on this one, so there is nothing to offer.
        {"id": 43, "name": "Nothing To Download", "audio": "http://insecure/x.mp3"},
    ],
}
def parse_jamendo(data):
    """Runs the parser over a fixture by standing in for the fetch."""
    original = music_pro._get
    music_pro._get = lambda address: data
    try:
        return music_pro._jamendo("blue", "key", 10)
    finally:
        music_pro._get = original


rows, trouble = parse_jamendo(jamendo)
check("a Jamendo result becomes a row", len(rows) == 1, rows)
check("with the title, the artist and the licence",
      rows[0]["title"] == "Blue Monday" and rows[0]["artist"] == "Somebody"
      and "creativecommons" in rows[0]["licence"], rows[0])
check("the duration is in milliseconds", rows[0]["duration"] == 270000, rows[0])
check("and a result with no https file is left out",
      all(row["url"].startswith("https://") for row in rows), rows)


def parse_archive(data):
    original = music_pro._get
    music_pro._get = lambda address: data
    try:
        return music_pro._archive("blue", 10)
    finally:
        music_pro._get = original


archive = {
    "response": {
        "docs": [
            {"identifier": "gd1977-05-08", "title": "Barton Hall",
             "creator": ["Grateful Dead", "Somebody Else", "A Third"],
             "licenseurl": "https://creativecommons.org/licenses/by-nc-nd/3.0/"},
            {"title": "no identifier, so no row"},
        ],
    },
}
rows, trouble = parse_archive(archive)
check("an Archive result becomes a row", len(rows) == 1, rows)
check("and points at the item's page rather than guessing a file",
      rows[0]["url"] == "" and rows[0]["page"].endswith("gd1977-05-08"), rows[0])
check("several creators are joined, not dumped as a list",
      isinstance(rows[0]["artist"], str) and "Grateful Dead" in rows[0]["artist"],
      rows[0])

def parse_broken():
    original = music_pro._get

    def explode(address):
        raise OSError("no network here")

    music_pro._get = explode
    try:
        return music_pro._archive("blue", 10)
    finally:
        music_pro._get = original


rows, trouble = parse_broken()
check("a catalogue that will not answer says so rather than raising",
      rows == [] and "did not answer" in trouble, (rows, trouble))

say()
say("== searching says which catalogue was skipped and why ==")
answer = call("find", {"query": "blue", "where": "jamendo"})
check("with no Jamendo id, Jamendo is skipped",
      answer["ok"] and any("client id" in note for note in answer["notes"]),
      answer)
check("and nothing is claimed to have been found", answer["count"] == 0, answer)
check("an empty search is refused", not call("find", {"query": " "})["ok"])

shutil.rmtree(scratch, ignore_errors=True)

say()
if FAILURES:
    say(f"{len(FAILURES)} Music Pro checks failed")
    sys.exit(1)
say("all Music Pro checks passed")
