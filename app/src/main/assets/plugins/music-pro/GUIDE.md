# Music Pro

Two decks, the effects your phone already has, a way to drive whatever else
is playing on it, and two catalogues of music you are allowed to keep.

It sits in **More → Music Pro**, and as a section inside the **Music** tab.

---

## The decks

**Deck A and deck B are two separate players.** They are not the Music tab's
player and they are deliberately not in the media session, so nothing here
appears on your lock screen and nothing here keeps playing when you leave.
A deck is something you use while you are looking at it.

Put something on one from **Put something on a deck** — the button marked
**A** or **B** beside a track loads it there. Or from the console:

```
deck a blue monday
deck b waltz
```

`deck` takes the first track in your library whose title or artist matches
the words, so you rarely have to type a whole name.

**Play, Pause, Eject** do what they say. **Cue** is the one worth explaining:

* Pressed while the deck is **stopped**, it marks the cue point where you are.
* Pressed while the deck is **playing**, it jumps back to that point.

That is the whole of how you line one track up against another that is
already going: find the downbeat, press Cue to mark it, let it play, press
Cue to snap back.

**Loop in / Loop out** set a loop between two points as the track passes them.
**Loop off** drops it. A loop is checked four times a second, which is close
enough that it lands where you meant and cheap enough that an idle panel is
not a timer.

**Tempo** runs a deck from half speed to double. The pitch is corrected, so a
track at 1.2x is faster and not higher — Media3 time-stretches rather than
resampling.

**Level** is that deck's own volume, before the crossfader has its say.

### The crossfader

At 0 you hear only deck A, at 100 only deck B, and in between you hear both.

It is an **equal-power** fader, not a straight line. Sliding one volume from 1
to 0 while the other goes 0 to 1 sounds like a dip in the middle: at halfway
both sides are at 0.5, and two half-volume signals are quieter than one full
one. This uses the quarter-turn of a circle instead, where both sides are at
0.71 in the middle and the two square to one. The loudness stays put across
the whole sweep. Every mixer ever built does this and it is the difference
between a mix and a gap.

From the console:

```
mix 0      all of deck A
mix 50     the middle
mix 100    all of deck B
```

---

## The effects

Each deck gets its own set, hung off its own audio session:

| | |
|---|---|
| **Equaliser** | Five bands or so, depending on the phone. Cut left, boost right, and **Flat** puts them all back. |
| **Bass** | Android's bass boost. |
| **Width** | The stereo widener. |
| **Reverb** | Six rooms, from a small one through to a plate, spread across the slider. |
| **Louder** | The loudness enhancer, for a track that was mastered quietly. |

These are **Android's own**, from `android.media.audiofx`, which has had them
since 2.3. Writing DSP in Kotlin to do worse versions would be daft.

**A phone can refuse any of them.** Not every device ships a reverb, and an
audio session that is not ready has none at all. When that happens the slider
is simply not drawn and the debug log says which effect was missing and why.
Nothing here pretends to apply an effect that is not there.

---

## What else is playing

PyCmd can see and drive whatever other music app on this phone is playing.

### How it works, and what it cannot do

Every well-behaved Android music app publishes a **media session** — it is
what puts the track on your lock screen and makes your headphone button work.
An app with notification access can get a controller for those sessions, and a
controller's transport controls are the real thing.

So "connect almost any music app" is not a plugin per service. It is one
mechanism that works for all of them because they all already speak it.

**What you get:** what is playing, in which app, and play, pause, skip and
back. Plus **Open it**, for when driving it from here is not enough.

**What you do not get,** stated plainly because the difference matters:

* It cannot read another app's library or playlists.
* It cannot search inside their catalogue from here.
* It cannot stream, download, or take a copy of anything they play.
* It does not know your password to any of them and never asks for one.

PyCmd has no arrangement with any music service. A plugin that claimed
otherwise would be a lie you only found out about after installing it.

### The permission

Reading other apps' media sessions needs **notification access**, which
Android keeps behind a switch in its own settings. PyCmd declares a
notification listener so that the switch is offered — the class overrides
nothing and never reads a notification; its existence in the manifest is the
entire job.

**PyCmd cannot turn it on for you.** The panel has a button that opens the
Android screen where the switch is. Everything else in Music Pro works
without it.

### Searching in another app

The box at the bottom of that section, and then the button with an app's name
on it, hands your words to that app through the intent every Android music app
is expected to answer. The app decides what the words mean, using the account
you already have with it. Your search, their catalogue, their subscription.

That is as close to "infinite search" as an app can honestly get: PyCmd is not
searching Spotify, Spotify is, because you asked it to.

```
nowplaying
```

on the console lists what every app is doing without opening the panel.

---

## Music you are allowed to keep

Two catalogues, chosen because both exist to be searched by programs and both
license their music to be kept:

### Jamendo

Creative Commons music, published by the artists for exactly this. Every
result says which licence it is under.

Jamendo's API wants a **client id**, which is free from
`developer.jamendo.com`. Put it in this plugin's settings. **Without one,
Jamendo is skipped and the search says so** rather than quietly returning
half a result set.

### The Internet Archive

Live recordings that the bands allow to be traded, and the public domain. No
key at all.

An Archive item is a *folder* of files — the same concert as a lossless
master, an MP3 set, and a text file — so Music Pro gives you the item's page
rather than picking a file for you. Downloading a 400 MB lossless master onto
a phone because nobody asked is not a feature.

### Getting one

**Download it** puts a Jamendo track in your Downloads, the same as any other
download. From there the **Music** tab can import it into your library, where
it can go on a deck like anything else.

**Open the page** opens the track's own page, which is where the licence and
the artist are. Worth a look before you keep something.

```
findmusic blue monday
```

searches both from the console.

---

## Settings

| | |
|---|---|
| **Search for free music in** | Both catalogues, or one of them. |
| **How many results** | Per catalogue. |
| **Jamendo client id** | Free from developer.jamendo.com. Blank means Jamendo is skipped. |

---

## Where each part actually runs

Worth knowing if you are reading the source or writing something like it.

* **The decks and the effects are Kotlin**, in `music/MixerHub.kt`. Playing
  two things at once and hanging an equaliser off an audio session are things
  only the platform can do.
* **The other apps are Kotlin**, in `music/Neighbours.kt`, for the same
  reason.
* **The catalogues are Python**, in this plugin, because they are HTTP and
  JSON and nothing else.

The panel asks the app for things by name — `api.request("mixer.load", ...)` —
and the answers come back as events rather than return values, because a
plugin runs on whatever thread it is on and nothing it asks for can be waited
on. That is the same channel `api.open_file` and `api.serve` have always used,
with the name passed in.
