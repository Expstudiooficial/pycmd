#!/usr/bin/env python3
"""Checks the music library: tracks, playlists, order, and what survives.

Playback is Kotlin and needs a phone, so none of it is here. Everything that
decides *what* plays and *in what order* is Python, and all of that is
checkable on a laptop: importing, naming, playlists, moving a track up,
deleting one out from under a playlist, and a registry that survives being
reloaded from disk.

The audio is not real audio - a few bytes with the right extension. Nothing in
this module opens a file to decode it, and a test that needed a real MP3 to
check that a rename works would be testing the wrong thing.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app", "src", "main", "python"))

import pycmd_music  # noqa: E402

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


root = tempfile.mkdtemp(prefix="pycmd-music-")
tracks_folder = pycmd_music.configure(root)


def put(name: str, size: int = 2048) -> str:
    """Puts a file where the app would have copied one, and hands back a path."""
    path = os.path.join(tracks_folder, name)
    with open(path, "wb") as handle:
        handle.write(b"\0" * size)
    return path


say("== importing ==")
first = pycmd_music.adopt(put("one.mp3"), "First Song", "Somebody", 185000)
check("a track is adopted", first.get("ok") and first.get("id"), first)

again = pycmd_music.adopt(os.path.join(tracks_folder, "one.mp3"), "First Song")
check("the same file twice is the same track", again.get("already") is True, again)
check("and the library holds one row", len(pycmd_music.library()["tracks"]) == 1)

second = pycmd_music.adopt(put("two.m4a"), "", "", 0)
check("a track with no title is named after its file",
      pycmd_music.library()["tracks"][1]["title"] == "two",
      pycmd_music.library()["tracks"][1])

video = pycmd_music.adopt(put("clip.mp4"), "A Video", "", 60000)
check("a video file is taken", video.get("ok"), video)
check("and is marked as one",
      [t for t in pycmd_music.library()["tracks"] if t["id"] == video["id"]][0]["video"] is True)

outside = os.path.join(root, "elsewhere.mp3")
with open(outside, "wb") as handle:
    handle.write(b"\0")
refused = pycmd_music.adopt(outside, "Nope")
check("a file outside the music folder is refused",
      not refused.get("ok") and "music folder" in refused.get("error", ""), refused)
check("and it is still on disk", os.path.isfile(outside))

wrong = pycmd_music.adopt(put("notes.txt"), "Notes")
check("a file that is not audio or video is refused",
      not wrong.get("ok") and "not audio" in wrong.get("error", ""), wrong)

missing = pycmd_music.adopt(os.path.join(tracks_folder, "ghost.mp3"), "Ghost")
check("a file that is not there is refused", not missing.get("ok"), missing)

say()
say("== names ==")
renamed = pycmd_music.rename_track(second["id"], "Second Song", "Someone Else")
check("a track can be renamed", renamed.get("ok") and renamed["title"] == "Second Song", renamed)
blank = pycmd_music.rename_track(second["id"], "   ")
check("but not to nothing", not blank.get("ok"), blank)

nasty = pycmd_music.rename_track(second["id"], "../../etc/passwd\n")
check("and a name cannot carry a path or a newline",
      nasty.get("ok") and "/" not in nasty["title"] and "\n" not in nasty["title"], nasty)

say()
say("== playlists ==")
made = pycmd_music.create_playlist("Working")
check("a playlist is made", made.get("ok") and made.get("id"), made)
check("a playlist needs a name", not pycmd_music.create_playlist("  ").get("ok"))

added = pycmd_music.add_to_playlist(made["id"], [first["id"], second["id"], video["id"]])
check("tracks go into it", added.get("added") == 3, added)
twice = pycmd_music.add_to_playlist(made["id"], [first["id"]])
check("the same track does not go in twice", twice.get("added") == 0, twice)
unknown = pycmd_music.add_to_playlist(made["id"], ["track-nope"])
check("and neither does one that does not exist", unknown.get("added") == 0, unknown)

ordered = pycmd_music.queue(made["id"])
check("the queue is in the order they were added",
      [t["id"] for t in ordered["tracks"]] == [first["id"], second["id"], video["id"]], ordered)

moved = pycmd_music.move_in_playlist(made["id"], video["id"], -2)
check("a track can be moved up", moved.get("moved") is True, moved)
check("and the queue follows",
      [t["id"] for t in pycmd_music.queue(made["id"])["tracks"]] ==
      [video["id"], first["id"], second["id"]])

edge = pycmd_music.move_in_playlist(made["id"], video["id"], -5)
check("moving past the top does nothing", edge.get("moved") is False, edge)
edge_down = pycmd_music.move_in_playlist(made["id"], second["id"], 9)
check("and neither does moving past the end", edge_down.get("moved") is False, edge_down)

taken_out = pycmd_music.remove_from_playlist(made["id"], first["id"])
check("a track leaves a playlist", taken_out.get("removed") == 1, taken_out)
check("without leaving the library", len(pycmd_music.library()["tracks"]) == 3)

renamed_list = pycmd_music.rename_playlist(made["id"], "Deep Work")
check("a playlist can be renamed", renamed_list.get("name") == "Deep Work", renamed_list)
check("renaming one that is not there fails",
      not pycmd_music.rename_playlist("list-nope", "x").get("ok"))

say()
say("== the whole library as a queue ==")
everything = pycmd_music.queue("")
check("no playlist means everything", len(everything["tracks"]) == 3, everything)
check("and it is named", everything.get("name") == "Everything", everything)
check("a playlist that is not there says so", not pycmd_music.queue("list-nope").get("ok"))

say()
say("== deleting ==")
gone = pycmd_music.remove_track(video["id"])
check("a track is deleted", gone.get("ok") and gone.get("deleted") is True, gone)
check("its file is gone too", not os.path.isfile(os.path.join(tracks_folder, "clip.mp4")))
check("and it left the playlist with it",
      video["id"] not in [t["id"] for t in pycmd_music.queue(made["id"])["tracks"]])

kept = pycmd_music.adopt(put("keep.mp3"), "Keep This")
pycmd_music.remove_track(kept["id"], False)
check("a track can be removed without deleting the file",
      os.path.isfile(os.path.join(tracks_folder, "keep.mp3")))

say()
say("== tidying ==")
in_flight = put("still-copying.mp3")
still_there = pycmd_music.tidy()
check("a file written seconds ago is left alone - it may be an import in flight",
      os.path.isfile(in_flight), still_there)
os.utime(in_flight, (0, 0))
os.utime(os.path.join(tracks_folder, "keep.mp3"), (0, 0))

orphaned = pycmd_music.tidy()
check("the file nothing points at is swept up", orphaned.get("orphans") >= 1, orphaned)
check("and the one still in the library is not",
      os.path.isfile(os.path.join(tracks_folder, "one.mp3")))

os.remove(os.path.join(tracks_folder, "two.m4a"))
shown = pycmd_music.library()
row = [t for t in shown["tracks"] if t["id"] == second["id"]][0]
check("a file that vanished is shown as missing", row["missing"] is True, row)
check("and it is left out of the queue",
      second["id"] not in [t["id"] for t in pycmd_music.queue("")["tracks"]])
swept = pycmd_music.tidy()
check("tidying drops its row", swept.get("dropped") == 1, swept)

say()
say("== what is remembered ==")
pycmd_music.remember("all", True, first["id"], made["id"])
state = pycmd_music.library()["state"]
check("loop and shuffle are kept",
      state["loop"] == "all" and state["shuffle"] is True, state)
check("so is what was playing", state["track"] == first["id"], state)
pycmd_music.remember("nonsense", False)
check("a loop mode that is not one of the three falls back to off",
      pycmd_music.library()["state"]["loop"] == "off")

check("and the playlist that held it lost it too",
      pycmd_music.library()["playlists"][0]["count"] == 0,
      pycmd_music.library()["playlists"])

# Put something back in it, so the reload below is checking that a playlist
# with tracks survives rather than that an empty one does.
pycmd_music.add_to_playlist(made["id"], [first["id"]])

say()
say("== reloaded from disk ==")
reopened = pycmd_music.configure(root)
check("the folder is the same", reopened == tracks_folder)
after = pycmd_music.library()
check("the tracks came back", len(after["tracks"]) == 1, after["tracks"])
check("the playlist came back", len(after["playlists"]) == 1, after["playlists"])
check("and it knows what is in it", after["playlists"][0]["count"] == 1, after["playlists"])
check("the library reports its size", after["bytes"] > 0, after["bytes"])

say()
say("== a broken registry ==")
with open(os.path.join(root, "library.json"), "w", encoding="utf-8") as handle:
    handle.write("{not json at all")
broken = pycmd_music.library()
check("a corrupt registry reads as an empty library, not a crash",
      broken["ok"] and broken["tracks"] == [], broken)
recovered = pycmd_music.create_playlist("After The Storm")
check("and it can be written again", recovered.get("ok"), recovered)

say()
say("== searching, sorting and the smart lists ==")
# A fresh library, so the counts below are the ones written here rather than
# whatever the checks above left behind.
_root2 = tempfile.mkdtemp(prefix="pycmd-browse-")
_folder2 = pycmd_music.configure(_root2)


def _put2(name: str, size: int = 2048) -> str:
    path = os.path.join(_folder2, name)
    with open(path, "wb") as handle:
        handle.write(b"\0" * size)
    return path


_blue = pycmd_music.adopt(_put2("a.mp3"), "Blue Monday", "New Order", 270000)["id"]
_ada = pycmd_music.adopt(_put2("b.mp3"), "Ada's Waltz", "Ada Lovelace", 95000)["id"]
_long = pycmd_music.adopt(_put2("c.mp3"), "The Long One", "Somebody", 900000)["id"]
_clip = pycmd_music.adopt(_put2("d.mp4"), "A Clip", "Nobody", 30000)["id"]

_all = pycmd_music.browse()
check("browsing with nothing set shows everything",
      _all["ok"] and _all["count"] == 4, _all.get("count"))
check("and says what it is looking at", _all["name"] == "Everything", _all["name"])

check("searching by title finds it",
      [t["id"] for t in pycmd_music.browse("monday")["tracks"]] == [_blue],
      pycmd_music.browse("monday")["tracks"])
check("searching by artist finds it",
      [t["id"] for t in pycmd_music.browse("lovelace")["tracks"]] == [_ada])
check("two words in any order still find it",
      [t["id"] for t in pycmd_music.browse("order blue")["tracks"]] == [_blue],
      pycmd_music.browse("order blue")["tracks"])
check("and a word that is nowhere finds nothing",
      pycmd_music.browse("zzz")["count"] == 0)

check("sorting by title",
      [t["title"] for t in pycmd_music.browse(sort="title")["tracks"]][0]
      == "A Clip",
      [t["title"] for t in pycmd_music.browse(sort="title")["tracks"]])
check("sorting by artist",
      [t["artist"] for t in pycmd_music.browse(sort="artist")["tracks"]][0]
      == "Ada Lovelace")
check("sorting by longest first",
      [t["id"] for t in pycmd_music.browse(sort="longest")["tracks"]][0] == _long)
check("sorting by shortest first",
      [t["id"] for t in pycmd_music.browse(sort="shortest")["tracks"]][0] == _clip)
check("a sort nobody has heard of falls back rather than failing",
      pycmd_music.browse(sort="sideways")["sort"] == "added")

check("nothing has been played yet",
      pycmd_music.browse(collection="never_played")["count"] == 4)
_first_play = pycmd_music.played(_blue)
check("playing one counts", _first_play["ok"] and _first_play["plays"] == 1, _first_play)
pycmd_music.played(_blue)
pycmd_music.played(_ada)
check("and counts again", pycmd_music.browse(sort="plays")["tracks"][0]["id"] == _blue,
      [(t["title"], t["plays"]) for t in pycmd_music.browse(sort="plays")["tracks"]])
check("the most played list holds only what was played",
      pycmd_music.browse(collection="most_played")["count"] == 2)
check("and never played holds the rest",
      pycmd_music.browse(collection="never_played")["count"] == 2)
check("a play recorded is a play remembered after a reload",
      pycmd_music.describe(_blue)["track"]["plays"] == 2,
      pycmd_music.describe(_blue)["track"])
check("playing something that is not there is refused",
      not pycmd_music.played("nope")["ok"])

check("videos are their own list",
      [t["id"] for t in pycmd_music.browse(collection="videos")["tracks"]] == [_clip])
check("a collection nobody has heard of is refused",
      not pycmd_music.browse(collection="sideways")["ok"])
check("a collection can be searched inside",
      pycmd_music.browse("blue", collection="most_played")["count"] == 1)

check("history is most recent first",
      [t["id"] for t in pycmd_music.history()["tracks"]][0] == _ada,
      [t["title"] for t in pycmd_music.history()["tracks"]])
# Three plays inside one millisecond, which is what skipping through a queue
# looks like. A timestamp cannot order these; the counter can.
_fast_a = pycmd_music.played(_long)
_fast_b = pycmd_music.played(_clip)
_fast_c = pycmd_music.played(_long)
check("plays inside the same millisecond still come back in order",
      [t["id"] for t in pycmd_music.history()["tracks"]][:2] == [_long, _clip],
      [(t["title"], t["last_played"], t["play_order"])
       for t in pycmd_music.history()["tracks"]])
check("and the counter only ever goes up",
      _fast_a["play_order"] < _fast_b["play_order"] < _fast_c["play_order"],
      [_fast_a["play_order"], _fast_b["play_order"], _fast_c["play_order"]])
check("and holds only what was played",
      len(pycmd_music.history()["tracks"]) == 4,
      [t["title"] for t in pycmd_music.history()["tracks"]])

_told = pycmd_music.describe(_blue)
check("one track can be described",
      _told["ok"] and _told["track"]["title"] == "Blue Monday", _told)
check("and it says which file it is", _told["extension"] == ".mp3", _told.get("extension"))
check("describing something that is not there is refused",
      not pycmd_music.describe("nope")["ok"])

_fixed = pycmd_music.set_details(_clip, title="A Better Name", album="Odds and Ends")
check("details can be corrected",
      _fixed["ok"] and _fixed["track"]["title"] == "A Better Name", _fixed)
check("and the album sticks", _fixed["track"]["album"] == "Odds and Ends")
check("a blank field leaves the old one alone",
      pycmd_music.set_details(_clip, title="")["track"]["title"] == "A Better Name")
check("and the artist was not wiped on the way past",
      pycmd_music.describe(_clip)["track"]["artist"] == "Nobody")

_playlist = pycmd_music.create_playlist("Evening")["id"]
pycmd_music.add_to_playlist(_playlist, [_blue, _long])
check("a playlist can be browsed",
      pycmd_music.browse(playlist_id=_playlist)["count"] == 2)
check("and searched inside",
      pycmd_music.browse("long", playlist_id=_playlist)["count"] == 1)
check("describing a track says which playlists hold it",
      pycmd_music.describe(_blue)["playlists"] == ["Evening"])
check("a playlist that is not there is refused",
      not pycmd_music.browse(playlist_id="nope")["ok"])

_numbers = pycmd_music.stats()
check("statistics add up the playing time",
      _numbers["duration"] == 270000 + 95000 + 900000 + 30000, _numbers)
check("and count the plays", _numbers["plays"] == 6, _numbers)
check("and name the artist with the most",
      _numbers["artists"] == 4 and _numbers["top_artist"], _numbers)

say()
say("== speed and the sleep timer ==")
_kept = pycmd_music.remember(loop="all", speed=1.5, sleep_minutes=30)
check("both are remembered",
      _kept["state"]["speed"] == 1.5 and _kept["state"]["sleep_minutes"] == 30, _kept)
check("a speed nobody could hear is pulled back into range",
      pycmd_music.remember(speed=0.01)["state"]["speed"] == 0.5)
check("and one nobody could follow is too",
      pycmd_music.remember(speed=9)["state"]["speed"] == 2.0)
check("a sleep timer of days is not a sleep timer",
      pycmd_music.remember(sleep_minutes=99999)["state"]["sleep_minutes"] == 600)
pycmd_music.remember(loop="one", shuffle=True, speed=1.25, sleep_minutes=15)
check("the library reads them back",
      pycmd_music.library()["state"]["speed"] == 1.25
      and pycmd_music.library()["state"]["sleep_minutes"] == 15
      and pycmd_music.library()["state"]["loop"] == "one",
      pycmd_music.library()["state"])

# `remember` writes the whole state object, and the play counter lives in it.
# Rewriting it wholesale took the counter with it, so every pause reset the
# history order to zero - which is the exact tie the counter exists to break.
_before = pycmd_music.played(_blue)["play_order"]
pycmd_music.remember(loop="off", shuffle=False)
_after = pycmd_music.played(_blue)["play_order"]
check("remembering the loop does not reset the play counter",
      _after > _before, (_before, _after))

# Nothing in this module raises across the bridge; a value that is not a
# number falls back rather than exploding.
for _nonsense in ("fast", None, [], {}):
    _answer = pycmd_music.remember(speed=_nonsense, sleep_minutes=_nonsense)
    check(f"a speed of {_nonsense!r} falls back rather than raising",
          _answer["state"]["speed"] == 1.0
          and _answer["state"]["sleep_minutes"] == 0, _answer)
check("and a number written as text still works",
      pycmd_music.remember(speed="1.5")["state"]["speed"] == 1.5)

# Back to the library the checks below expect.
pycmd_music.configure(root)

say()
say("== the screen and the library agree on the sorts ==")
# The Music screen names its sorts in Kotlin so it can order them and give
# them words. The ids have to be ones this module knows, or a chip does
# nothing and nobody finds out until somebody presses it.
_screen = os.path.join(ROOT, "app", "src", "main", "java", "com", "expstudio",
                       "pycmd", "ui", "MusicScreen.kt")
with open(_screen, encoding="utf-8") as _handle:
    _kotlin = _handle.read()
_block = _kotlin.split("private val SORT_LABELS = listOf(", 1)[-1].split(")", 1)[0]
_ids = re.findall(r'"([a-z_]+)" to "', _block)
check("the screen offers some sorts", len(_ids) >= 6, _ids)
check("and every one of them is a sort this module knows",
      all(sort in pycmd_music.SORTS for sort in _ids),
      [sort for sort in _ids if sort not in pycmd_music.SORTS])

say()
say("== limits ==")
check("the ceilings are published",
      pycmd_music.library()["limits"]["tracks"] == pycmd_music.MAX_TRACKS)

say()
if FAILURES:
    say(f"{len(FAILURES)} music checks failed")
    sys.exit(1)
say("all music checks passed")
