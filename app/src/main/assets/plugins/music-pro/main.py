"""Music Pro: two decks, the phone's effects, and the music you keep elsewhere.

## Where the work actually happens

Almost none of it is here, and that is the point of the shape.

**The decks are Kotlin.** Playing two things at once, crossfading between
them and hanging an equaliser off an audio session are things only the
platform can do, so the app owns a `MixerHub` and this plugin drives it by
asking - `api.request("mixer.load", ...)`. The answers come back the other
way, as `mixer_state` events, and this module's only job on that side is to
hold the last one so the panel can ask for it.

**The other apps are Kotlin too.** Reading what Spotify is playing means
reading its media session, which needs notification access; driving it means
its transport controls. Both are Android, both are in `Neighbours`, and the
same request-and-event pair carries them.

**The catalogues are here**, because they are HTTP and JSON and nothing else.

## What "connect almost any music app" means, precisely

It means two mechanisms, both of which every Android music app already
speaks, and neither of which reaches inside one:

* **Its transport.** Play, pause, skip, seek, and what is on now. This works
  for anything with a media session, which is anything that puts a track on
  your lock screen.
* **Its search.** Android has an intent that hands a query to a music app and
  lets it decide what that means. Your search, their catalogue, your account
  with them.

It does not mean streaming from a service without one, downloading from one,
or holding your password to one. PyCmd has no deal with Spotify and pretending
otherwise in a description would be a lie people only discover after
installing.

## Where the free music comes from

Two catalogues that exist to be searched by programs and whose music is
licensed to be kept:

* **Jamendo** - Creative Commons music, published by the artists for this.
  Its API wants a client id, free from developer.jamendo.com, and without one
  Jamendo is skipped rather than guessed at.
* **The Internet Archive** - live recordings the bands allow, and the public
  domain. No key at all.

Both hand back a direct address for a file. PyCmd downloads it into Downloads
like anything else, and from there it can be imported into the library. What
it does not do is pull a track out of a service that did not offer it.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

TIMEOUT = 20
AGENT = "PyCmd/2.6 (+https://github.com/expstudiooficial/pycmd)"

DECKS = ("a", "b")

# Long enough for a band and a song, short enough that it cannot be used to
# build an enormous URL out of a panel that is misbehaving.
MAX_QUERY = 120


def _number(value, fallback: float = 0.0) -> float:
    """A number, or the fallback. Never raises.

    Every one of these arrives from a panel over a bridge, and an export that
    throws hands back a traceback where a person expected a sentence. The
    panel only ever sends numbers; an export is a public door and should not
    depend on that.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback

# The effects the app hangs off a deck, and what each one is called on screen.
EFFECTS = (
    ("bass", "Bass"),
    ("width", "Width"),
    ("reverb", "Reverb"),
    ("louder", "Louder"),
)


def setup(api):
    # The last thing the app said, for each of the two things it reports on.
    # A panel that has just opened asks for these rather than waiting for
    # something to change - which, on a mixer nobody has touched yet, is
    # never.
    state = {"mixer": {}, "apps": {}, "apps_list": {}}

    @api.on("mixer_state")
    def _mixer_changed(payload):
        state["mixer"] = payload if isinstance(payload, dict) else {}
        api.send({"kind": "mixer", "state": state["mixer"]})

    @api.on("apps_state")
    def _apps_changed(payload):
        state["apps"] = payload if isinstance(payload, dict) else {}
        api.send({"kind": "apps", "state": state["apps"]})

    @api.on("apps_list")
    def _apps_listed(payload):
        state["apps_list"] = payload if isinstance(payload, dict) else {}
        api.send({"kind": "apps_list", "state": state["apps_list"]})

    # ------------------------------------------------------------ the decks

    @api.export
    def mixer(payload=None):
        """The last state the app reported, and a nudge to report again."""
        api.request("mixer.state")
        return {"ok": True, "state": state["mixer"], "decks": list(DECKS),
                "effects": [{"id": key, "name": name} for key, name in EFFECTS]}

    @api.export
    def tracks(payload=None):
        """What there is to put on a deck: the music library, briefly.

        The library is the app's, not this plugin's, and a plugin cannot read
        another module's store - so this reads the same registry file the
        Music tab does, through the module the app already has loaded.
        """
        try:
            import pycmd_music
        except ImportError:
            return {"ok": False, "error": "the music library is not loaded"}
        answer = pycmd_music.browse(
            str((payload or {}).get("search", "")), "title", "", "",
        )
        if not answer.get("ok"):
            return {"ok": False, "error": answer.get("error", "no library")}
        rows = [
            {"id": row["id"], "title": row["title"], "artist": row["artist"],
             "file": row["file"], "duration": row["duration"]}
            for row in answer["tracks"] if not row["missing"]
        ]
        return {"ok": True, "tracks": rows, "count": len(rows)}

    @api.export
    def load(payload):
        """Puts a track on a deck."""
        body = payload or {}
        deck = str(body.get("deck", "a")).lower()
        if deck not in DECKS:
            return {"ok": False, "error": "there are two decks, a and b"}
        path = str(body.get("file", ""))
        if not path:
            return {"ok": False, "error": "which track?"}
        api.request("mixer.load", deck=deck, path=path,
                    title=str(body.get("title", "")))
        return {"ok": True}

    @api.export
    def deck_action(payload):
        """Play, pause, cue or eject one deck."""
        body = payload or {}
        deck = str(body.get("deck", "a")).lower()
        what = str(body.get("what", "")).lower()
        if deck not in DECKS:
            return {"ok": False, "error": "there are two decks, a and b"}
        if what not in ("play", "pause", "cue", "eject"):
            return {"ok": False, "error": f"a deck cannot {what!r}"}
        api.request(f"mixer.{what}", deck=deck)
        return {"ok": True}

    @api.export
    def deck_set(payload):
        """Tempo, gain, position or a loop on one deck."""
        body = payload or {}
        deck = str(body.get("deck", "a")).lower()
        if deck not in DECKS:
            return {"ok": False, "error": "there are two decks, a and b"}

        if "rate" in body:
            api.request("mixer.tempo", deck=deck,
                        rate=max(0.5, min(2.0, _number(body["rate"], 1.0))))
        if "level" in body:
            api.request("mixer.gain", deck=deck,
                        level=max(0.0, min(1.0, _number(body["level"], 1.0))))
        if "position" in body:
            api.request("mixer.seek", deck=deck,
                        position=max(0, int(_number(body["position"], 0))))
        if "loopStart" in body or "loopEnd" in body:
            api.request("mixer.loop", deck=deck,
                        start=max(0, int(_number(body.get("loopStart"), 0))),
                        end=max(0, int(_number(body.get("loopEnd"), 0))))
        return {"ok": True}

    @api.export
    def fader(payload):
        """Where the crossfader sits: 0 is all of A, 1 is all of B."""
        position = _number((payload or {}).get("position"), 0.5)
        api.request("mixer.fader", position=max(0.0, min(1.0, position)))
        return {"ok": True}

    @api.export
    def effect(payload):
        """One effect on one deck, from 0 to 1."""
        body = payload or {}
        deck = str(body.get("deck", "a")).lower()
        name = str(body.get("name", "")).lower()
        if deck not in DECKS:
            return {"ok": False, "error": "there are two decks, a and b"}
        if name not in {key for key, _ in EFFECTS}:
            return {"ok": False, "error": f"there is no {name!r} effect"}
        api.request("mixer.effect", deck=deck, name=name,
                    level=max(0.0, min(1.0, _number(body.get("level"), 0.0))))
        return {"ok": True}

    @api.export
    def band(payload):
        """One equaliser band, from -1 (cut) through 0 (flat) to 1 (boost)."""
        body = payload or {}
        deck = str(body.get("deck", "a")).lower()
        if deck not in DECKS:
            return {"ok": False, "error": "there are two decks, a and b"}
        api.request("mixer.band", deck=deck,
                    index=max(0, int(_number(body.get("index"), 0))),
                    level=max(-1.0, min(1.0, _number(body.get("level"), 0.0))))
        return {"ok": True}

    @api.export
    def flatten(payload):
        """Every band back to flat."""
        deck = str((payload or {}).get("deck", "a")).lower()
        if deck not in DECKS:
            return {"ok": False, "error": "there are two decks, a and b"}
        api.request("mixer.flatten", deck=deck)
        return {"ok": True}

    @api.export
    def close_decks(payload=None):
        """Lets the decks go. The panel calls this when it is done with them."""
        api.request("mixer.release")
        return {"ok": True}

    # --------------------------------------------- the rest of this phone

    @api.export
    def apps(payload=None):
        """What else is playing, and which apps could take a search."""
        api.request("apps.state")
        api.request("apps.list")
        return {"ok": True, "playing": state["apps"], "apps": state["apps_list"]}

    @api.export
    def app_control(payload):
        """Play, pause, skip or stop whatever another app is doing."""
        body = payload or {}
        what = str(body.get("what", "toggle")).lower()
        if what not in ("play", "pause", "toggle", "next", "previous", "stop"):
            return {"ok": False, "error": f"cannot {what!r} another app"}
        api.request("apps.control", package=str(body.get("package", "")), what=what)
        return {"ok": True}

    @api.export
    def app_search(payload):
        """Hands a search to a music app and lets it decide what it means."""
        body = payload or {}
        query = str(body.get("query", "")).strip()[:MAX_QUERY]
        if not query:
            return {"ok": False, "error": "what are you looking for?"}
        api.request("apps.search", package=str(body.get("package", "")), query=query)
        return {"ok": True}

    @api.export
    def app_open(payload):
        """Opens another app, for when driving it from here is not enough."""
        package = str((payload or {}).get("package", ""))
        if not package:
            return {"ok": False, "error": "which app?"}
        api.request("apps.open", package=package)
        return {"ok": True}

    @api.export
    def ask_permission(payload=None):
        """Opens Android's notification-access screen. PyCmd cannot grant it."""
        api.request("apps.permission")
        return {"ok": True}

    # ------------------------------------------------- music you can keep

    @api.export
    def find(payload):
        """Searches the free catalogues, and says which found what."""
        body = payload or {}
        query = str(body.get("query", "")).strip()[:MAX_QUERY]
        if not query:
            return {"ok": False, "error": "what are you looking for?"}

        wanted = str(body.get("where", "") or api.setting("catalogue", "both") or "both")
        limit = max(1, min(50, int(api.setting("results", 20) or 20)))

        found = []
        notes = []
        if wanted in ("both", "jamendo"):
            key = str(api.setting("jamendo_id", "") or "").strip()
            if not key:
                notes.append(
                    "Jamendo was skipped: it needs a client id, free from "
                    "developer.jamendo.com, in this plugin's settings."
                )
            else:
                rows, trouble = _jamendo(query, key, limit)
                found.extend(rows)
                if trouble:
                    notes.append(trouble)
        if wanted in ("both", "archive"):
            rows, trouble = _archive(query, limit)
            found.extend(rows)
            if trouble:
                notes.append(trouble)

        return {"ok": True, "query": query, "results": found[:limit * 2],
                "count": len(found), "notes": notes}

    @api.export
    def fetch(payload):
        """Downloads one result, into the app's Downloads.

        The address has to be one the search handed back, and it has to be
        https. A downloader that takes any URL from a panel is a downloader
        somebody else's page can aim.
        """
        body = payload or {}
        address = str(body.get("url", ""))
        if not address.startswith("https://"):
            return {"ok": False, "error": "only https addresses are downloaded"}
        try:
            import pycmd_download
        except ImportError:
            return {"ok": False, "error": "the downloader is not loaded"}
        try:
            answer = pycmd_download.download(address)
        except Exception as error:  # noqa: BLE001
            return {"ok": False, "error": f"{type(error).__name__}: {error}"}
        api.refresh("downloads")
        return answer if isinstance(answer, dict) else {"ok": True}

    @api.export
    def open_link(payload):
        """Opens a result's page in the browser, for the licence and the artist."""
        address = str((payload or {}).get("url", ""))
        if not address.startswith("https://"):
            return {"ok": False, "error": "only https addresses are opened"}
        api.request("apps.link", url=address)
        return {"ok": True}

    # ------------------------------------------------------------ commands

    @api.command("deck", help="deck [a|b] <words> - load a track onto a deck")
    def deck_command(argument):
        parts = (argument or "").split(None, 1)
        if not parts:
            return "deck a <words>  -  the first track whose name matches"
        side = parts[0].lower()
        if side not in DECKS:
            side, words = "a", (argument or "").strip()
        else:
            words = parts[1].strip() if len(parts) > 1 else ""
        if not words:
            return f"deck {side} <words>  -  which track?"

        listed = tracks({"search": words})
        if not listed.get("ok") or not listed["tracks"]:
            return f"Nothing in the library matches {words!r}."
        first = listed["tracks"][0]
        load({"deck": side, "file": first["file"], "title": first["title"]})
        return f"Deck {side.upper()}: {first['title']}"

    @api.command("mix", help="mix [0-100] - where the crossfader sits")
    def mix_command(argument):
        text = (argument or "").strip()
        if not text:
            return "mix 0 is all of deck A, mix 100 is all of deck B."
        try:
            amount = max(0, min(100, int(text)))
        except ValueError:
            return f"{text!r} is not a number between 0 and 100."
        fader({"position": amount / 100.0})
        return f"Crossfader at {amount}."

    @api.command("nowplaying", help="What every app on this phone is playing")
    def nowplaying_command(argument=None):
        apps()
        playing = state["apps"] or {}
        if not playing.get("allowed", False):
            return ("PyCmd cannot see the other apps yet. Music Pro's panel has "
                    "a button that opens Android's notification-access screen.")
        rows = playing.get("sessions", [])
        if not rows:
            return "Nothing else on this phone is playing."
        lines = []
        for row in rows:
            mark = "playing" if row.get("playing") else "paused"
            title = row.get("title") or "(untitled)"
            who = row.get("artist") or ""
            lines.append(f"  {row.get('app', '?'):<18} {mark:<8} {title} {who}".rstrip())
        return "\n".join([f"{len(rows)} app(s):"] + lines)

    @api.command("findmusic", help="findmusic <words> - search the free catalogues")
    def find_command(argument):
        query = (argument or "").strip()
        if not query:
            return "findmusic <words>  -  Creative Commons and the public domain."
        answer = find({"query": query})
        if not answer.get("ok"):
            return answer.get("error", "that search did not work")
        rows = answer["results"][:12]
        if not rows:
            return f"Nothing found for {query!r}." + \
                ("\n" + "\n".join(answer["notes"]) if answer["notes"] else "")
        lines = [f"{answer['count']} result(s) for {query!r}:"]
        for row in rows:
            lines.append(f"  {row['title'][:38]:<38} {row['artist'][:20]:<20} "
                         f"{row['source']}")
        lines.extend(answer["notes"])
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# The catalogues
# ---------------------------------------------------------------------------


def _get(address: str) -> dict:
    request = urllib.request.Request(address, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:
        return json.loads(answer.read().decode("utf-8", "replace"))


def _jamendo(query: str, key: str, limit: int):
    """Creative Commons music, published by the artists for exactly this."""
    address = "https://api.jamendo.com/v3.0/tracks/?" + urllib.parse.urlencode({
        "client_id": key,
        "format": "json",
        "limit": limit,
        "search": query,
        "audioformat": "mp32",
        "include": "licenses",
    })
    try:
        data = _get(address)
    except Exception as error:  # noqa: BLE001
        return [], f"Jamendo did not answer: {type(error).__name__}"

    rows = []
    for row in data.get("results", []):
        audio = row.get("audiodownload") or row.get("audio") or ""
        if not audio.startswith("https://"):
            continue
        rows.append({
            "source": "Jamendo",
            "id": str(row.get("id", "")),
            "title": row.get("name", "") or "(untitled)",
            "artist": row.get("artist_name", ""),
            "album": row.get("album_name", ""),
            "duration": int(row.get("duration", 0) or 0) * 1000,
            "url": audio,
            "page": row.get("shareurl", ""),
            "licence": (row.get("licenses") or {}).get("ccurl", "Creative Commons"),
        })
    return rows, ""


def _archive(query: str, limit: int):
    """Live recordings the bands allow, and the public domain."""
    address = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode({
        "q": f'({query}) AND mediatype:(audio)',
        "fl[]": "identifier",
        "rows": limit,
        "page": 1,
        "output": "json",
    }, doseq=True) + "&fl[]=title&fl[]=creator&fl[]=licenseurl"
    try:
        data = _get(address)
    except Exception as error:  # noqa: BLE001
        return [], f"The Internet Archive did not answer: {type(error).__name__}"

    rows = []
    for row in (data.get("response") or {}).get("docs", []):
        identifier = str(row.get("identifier", ""))
        if not identifier:
            continue
        creator = row.get("creator", "")
        if isinstance(creator, list):
            creator = ", ".join(str(part) for part in creator[:2])
        rows.append({
            "source": "Internet Archive",
            "id": identifier,
            "title": str(row.get("title", "") or identifier),
            "artist": str(creator or ""),
            "album": "",
            "duration": 0,
            # The item's page rather than a file: an archive item is a folder
            # of many files and picking one for somebody sight unseen is how
            # you download a 400 MB lossless master onto a phone.
            "url": "",
            "page": f"https://archive.org/details/{urllib.parse.quote(identifier)}",
            "licence": str(row.get("licenseurl", "") or "see the item page"),
        })
    return rows, ""
