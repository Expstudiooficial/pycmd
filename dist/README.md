# Prebuilt APK

`PyCmd-2.6.1.apk` — ready to install, nothing else needed.

| | |
|---|---|
| Package | `com.expstudio.pycmd.debug` |
| Version | 2.6.1 |
| Size | 20 MB |
| Signed with | the key in [`keystore/`](../keystore/), committed so updates can install over it |
| Works on | Android 7.0 (API 24) and newer, **arm64-v8a** (every phone since about 2016) |
| SHA-256 | see [SHA256SUMS.txt](SHA256SUMS.txt) |

## What is new in 2.6.1

**The sliders in plugin panels work.** In 2.6.0 they did not move at all, and
that was my mistake. It is the only thing changed here.

**What went wrong.** A panel is a web page in a WebView, and that WebView sits
inside one of the app's own scrolling lists. Something has to decide, on each
drag, which of the two owns it - and the thing deciding was looking at one
move at a time: *did the finger go up or down since the last event, and has
the page run out of room that way?*

Two things follow from asking it that way, and the second is the one everybody
hit.

A finger dragged sideways still wobbles a pixel or two up and down, so the
answer flipped on almost every move. And a panel shorter than the screen is
**both** at the top and at the bottom — there is nothing above it and nothing
below it — so the answer was "the list may have the drag" whichever way the
wobble went, on the very first move of every gesture.

Dragging a slider is a sideways gesture, usually on a panel that is short or
scrolled to one end. The list took the drag a few pixels in, and the thumb
stopped following the finger.

**What it does now.** The direction is measured from where the finger landed
rather than from the previous event, nothing is decided until the gesture is
big enough to have a direction at all, and once decided it stays decided until
the finger lifts:

- **Sideways** — the page keeps it. A list that scrolls up and down has no
  business with a horizontal drag.
- **Up and down** — the old rule, which was the right one: the page scrolls
  until it runs out, then the list takes over, so flicking past a panel still
  works.

And the page now tells the app when a finger lands on something that owns
drags outright — a slider, a colour picker, anything with `touch-action: none`
or marked `data-pycmd-drag` — so even a sloppy diagonal drag moves the thumb.

**Two more found while fixing it.** A node in the page that answers none of
the usual DOM questions used to throw, and the throw cost that panel its
scrolling as well as its sliders. And what the page said about one gesture was
still there at the start of the next, so touching a slider once would have
made every drag afterwards behave like a slider.

**How it is checked now, so it cannot come back.** The rule is arithmetic and
nothing else, so it lives in `PanelGesture` with thirteen JVM unit tests
driving it directly — the wobble, the short panel, the exact diagonal — every
one of which fails against the 2.6.0 rule. On top of that,
`tools/test_panel_sliders.js` builds every bundled panel with its real bridge
and drags every slider in it with real touch events, and fails if no panel had
a slider to drag.

## What is new in 2.6.0

### Creator: ten languages, 904 blocks

Five new languages, chosen because the phone can already run four of them:
**C**, **Go**, **Rust** and **Shell** run on the interpreters the app carries,
and **JSON** is the thing everybody has to write by hand and nobody enjoys.
363 blocks became 904, with the categories the original five were missing -
sets, comprehensions, sorting, counting, dates and type hints in Python;
promises, timers, classes and storage in JavaScript; media, tables and
sections in HTML; flex, grid, custom properties and animation in CSS; tables,
quotes and checklists in Markdown.

**Every language has an example, and a button that loads it.** Each one is a
whole program rather than a fragment, because the first thing anybody does
with a starter is press Run. The starter used to arrive once, at boot, in one
language - so switching to Rust gave you an empty page and a hundred and two
blocks with no clue which two go at the top.

**JSON blocks carry no commas.** The compiler puts them in, by the only rule
there is, so the two mistakes everybody makes writing JSON by hand cannot be
made here. A project that still is not valid JSON says so.

Three real bugs fell out of building it:

* **`if` followed by `else` wrote broken JavaScript**, and had since 2.5.4 -
  the `if` closed itself and then `else` supplied a second brace. Blocks can
  say what they continue now, and an `else` with no `if` above it is reported
  rather than written out wrong.
* **The C interpreter had no two-dimensional arrays.** `grid` decaying to a
  pointer forgot how wide a row was, so `grid[r][c]` said grid was not an
  array at all.
* **`int scores[] = {3, 1, 4}` allocated nothing** and then refused the first
  initialiser.

### The Music tab

A library of eight tracks is a list; a library of four hundred is something
you search. Searching matches title, artist, album and file name, every word
in any order. Eight sorts. Five smart lists worked out fresh each time -
recently added, most played, never played, the long ones, video files.

**Plays are counted honestly**: thirty seconds, or halfway for anything under
a minute, measured by where the playhead is. Skipping past something does not
make it your most played.

**Track details** let you correct the title, artist and album of a file called
`track_03_final_v2.mp3`, and show how long it is, how often it has been played
and which playlists hold it.

**Playback speed** from half to double with the pitch corrected, and a
**sleep timer** counted from now rather than from a clock time.

### New: Music Pro

Two DJ decks with an equal-power crossfader, cue points, loops and tempo; the
phone's own equaliser, bass boost, stereo widener, reverb and loudness
enhancer on each deck; the ability to see and drive whatever other app on this
phone is playing; and search over two catalogues of freely licensed music -
Jamendo and the Internet Archive.

It is worth being plain about the limit, because the description of a thing
like this is usually vaguer than the thing: Music Pro drives another app's
*transport* and hands it a *search*. It cannot read their library, search
their catalogue from inside PyCmd, stream from their service, or hold your
password to one. PyCmd has no arrangement with any music service.

Its guide is in **Guides → Music Pro**.

### Elsewhere

The repository was renamed to `pycmd`, so every URL in the app points there
now. Builds up to 2.5.9 still find their updates through GitHub's redirect.

## What is new in 2.5.9

**2.5.8 broke every plugin tab, and this puts them back.** Opening one showed
a black screen with a sliver of something at the top. That was my mistake and
it is the first thing fixed here.

**What went wrong.** 2.5.8 tried to fix the Creator tab's scrolling by making
each panel's `body` its own scroller - `height: 100%` on the root and on the
body, with the overflow moved down to it. That is a clean, ordinary app shell,
it behaves correctly in a browser, and I checked it in one. In the app's own
WebView it collapses the panel to no height at all: whatever those percentages
resolve against while the page is first laid out is not the height the panel
ends up with, and it never comes back. Every percentage height is gone from
the panel stylesheet and from every panel that ships here, and both the suite
and the browser test now refuse to let one back in.

**Creator still had to stop being the panel that would not scroll**, and this
time the fix is the boring one. It was the only panel with chrome pinned to
the viewport - a sticky bar at the top, a button row fixed to the bottom - and
the panels without any of that have always scrolled fine. So it is a plain
page now, like them.

**The buttons moved to the top.** **+ Add a block**, **Code** and **Save** sit
just under the bar instead of being fixed at the bottom of the screen. They
are on screen the moment the tab opens, so the thing you reach for most is
never behind a scroll - which is worth more than having them pinned, and does
not depend on anything the WebView has to agree with.

The block picker is unchanged: still a full-screen sheet that scrolls itself,
which is the one arrangement in this panel that has always worked.

**Also here:** a test that could fail for no reason anybody could act on -
it waited a flat eight tenths of a second for a Go server's first line and
sometimes needed more - now waits for the line instead of guessing.

The browser test added last release earned its place immediately: its dullest
check is that a panel drew *anything*, and that is now the check standing
between this and a repeat. What it cannot do is be an Android WebView, which
is exactly the difference that caused this - so the rule learned from it is
written down as a rule and checked directly, rather than trusted to a browser
that disagrees. 1129 checks pass, 24 more with a browser present, and the
release build lints clean.

## What was new in 2.5.8

**The Creator tab would not scroll**, so a script longer than the screen had a
bottom nobody could reach. Same for the Cloud tab, which is nearly four screens
tall, and for Packages Pro and Server Pro opened full screen. Fixed for all of
them, in one place.

**A panel is a web page inside the app's own layout, and it was leaving the
scrolling to the document.** That is the one thing that is not dependable
there: the page is the right height, the content is all present, and a finger
moves nothing. It is why the Creator palette had to be moved into an overlay
back in 2.5.5 - the overlay scrolled, because an overlay scrolls *itself*
rather than asking the document to.

So every panel now scrolls itself. Its `body` is exactly as tall as the panel
and scrolls its own overflow, which is the arrangement that has always worked
here. One rule in the shared stylesheet, so it applies to every plugin at once
- the ones that ship with the app and anything you write.

**The Creator tab goes further**, because its top bar and its buttons should
stay where they are: the bar, the script and the button row are a column, and
the script in the middle is what moves. The bar stays at the top, **+ Add a
block**, **Code** and **Save** stay at the bottom, and the script scrolls
between them to its actual end.

**A panel inside one of the app's own screens keeps its own drags.** The app
decides who owns a drag - the panel or the list around it - by asking the
WebView whether its document can still scroll, and a panel that scrolls an
element instead always answers "no". So the page now says where each touch
landed, and the app holds on when the touch was on something the panel scrolls
itself.

**This one was measured rather than reasoned about.** `tools/test_panels.js`
lays every bundled panel out in a real browser at a phone's size, drags a
finger down it and checks that something moved. It found two things in the
writing of this release: that the Cloud tab is 2167 pixels tall in a 560 pixel
panel, and that making the body the scroller does nothing unless the root
element's overflow is hidden as well - otherwise the browser hands the body's
overflow up to the viewport and puts the scrolling back where it was broken.
That test needs a browser, so it says so and steps aside where there is not
one; the rest of the suite checks the same rules by reading them. 1124 checks
pass, 20 more with a browser present, and the release build lints clean.

For plugin authors: nothing to do. Write an ordinary page and it scrolls. Do
not set `height` or `overflow` on `body` unless you want to take the scrolling
over yourself, and use `element.scrollIntoView()` rather than `window.scrollTo`,
which no longer has anything to move. PLUGINS.md has the shape to copy if you
want a header or a button row that stays put.

## What was new in 2.5.7

**Cloud sometimes failed to load, with a file that was definitely there:**

```
FileNotFoundError: .../plugins/pycmd.cloud/main.py
```

It was a race between two things the app does at startup, and it could hit any
plugin - Cloud was just the one that showed up.

**Installing a plugin replaces its folder. Loading one imports a module out of
that folder.** Those ran on different threads, at the same time, on every
launch: the plugin was being imported while its own files were being moved out
from underneath it, so a file that passed the check a moment earlier was gone
by the time Python went to read it. Three things now make that impossible.

**Everything that touches a plugin folder runs on one thread.** Installing,
loading, listing, panels, settings - one after another, never at once. (The
console's own plugin commands stay on the interpreter thread, where they have
to be; they no longer have a folder moving under them either, because of the
next one.)

**Replacing a plugin is one rename now, not a delete and a move.** The old
folder is moved aside, the new one is renamed into place, and only then is the
old one deleted - so there is never a moment when the folder is missing or
half-emptied. The old way had a worse failure too: `shutil.move` into a folder
that still exists puts the new copy *inside* it, so a delete that only half
worked left `main.py` one level down and a plugin that listed fine and could
never load. Removing a plugin works the same way now.

**And the plugins that ship with the app were being reinstalled on every single
launch.** The check for "is this one already installed?" read a list that had
not been filled in yet, saw nothing, and concluded nothing was installed - so
all five were deleted and written out again every time you opened the app, for
nothing. It asks the real listing now, and installs happen before anything is
loaded rather than beside it. That is several megabytes of file copying gone
from every start, on top of the crash it was causing.

A plugin whose folder cannot be read is no longer treated as up to date
either, so one that did get damaged is repaired on the next launch instead of
staying broken.

The suite gained checks for all of it: that replacing a plugin leaves one whole
plugin behind and nothing nested inside it, that a leftover from an install
that was killed is tidied away, that every call into the plugin runtime is on
the plugin thread, and that bundled plugins are installed before anything is
loaded. 1111 checks pass and the release build lints clean; the race itself
needs a phone to see, and there is no emulator here.

## What was new in 2.5.6

**The app stopped for a moment, came back, stopped again.** Not one bug -
four, all of them plugin-shaped, and all of them work being done on the one
thread that also has to answer your finger. This release is that thread being
given less to do.

**A plugin's section was thrown away every time you scrolled past it.** The
card a plugin adds to Servers or Files is an item in a scrolling list, and a
list like that destroys items that go off screen and builds them again when
they come back. Inside that item was a whole WebView: destroyed, rebuilt, its
page loaded again, its JavaScript run again - a tenth of a second each way,
and everything you had typed into it gone. Scroll up and down a screen with
two sections open and that *is* the freezing.

Panels are now kept alive between visits: same page, same scroll position,
same half-filled form, no work at all to show one again. Five stay warm, the
oldest is let go past that, and a panel that is not on screen has its timers
stopped so a section you scrolled by is not still asking questions in the
background. Switching a plugin off drops its panels straight away.

**The debug log copied three thousand entries per line written.** Every
message - and plugins, servers and pages write a lot of them - copied the
whole buffer, counted the errors in it again, and told the screen to redraw.
A busy second was hundreds of thousands of operations and hundreds of
redraws. A line now costs one insertion, and the screen is told at most a few
times a second.

**Plugin panels could crowd out everything else.** Panels that refresh on a
timer shared a pool of four threads with the Files listing, the Servers
refresh and every other thing a tab needs - so four slow panel calls meant the
tab you were actually looking at waited behind them. Panel calls now have a
thread of their own and cannot take anybody else's.

**And the smaller ones from the same sweep:**

- A plugin's icon was read from disk and decoded on the main thread, in the
  middle of laying out a scrolling row. It happens off it now, once per icon.
- The Files tab asked the filesystem whether each row was a folder, for every
  row, on every redraw, to work out which plugin actions applied - two hundred
  files meant two hundred questions it already knew the answer to. With no
  plugins on it does not ask at all.
- Console output is turned into a script on a background thread rather than
  between two frames, so a program that talks a lot no longer makes the app
  slow to touch while it does.
- The two panels that refresh on a timer stop while they are off screen, and
  join a refresh that is already out rather than starting another one.

**For plugin authors:** the bridge has a second verb. `pycmd.poll(name,
payload)` is `pycmd.call` with one difference - if the very same question is
already on its way, it waits for that answer instead of asking again. Use it
for a refresh on a timer; keep `call` for anything that changes something,
because two presses of *Add* are two jobs and `poll` would make them one. A
call that is never answered now rejects on its own after two minutes rather
than leaving the page waiting for ever. Both are in PLUGINS.md.

**Creator's block picker** redraws its list in one write with one shared tap
handler, instead of building and throwing away a hundred and fifty elements
with a handler each on every letter typed into the search box.

None of this can be shown working without a phone, and there is no emulator
here: 1097 checks cover the logic - the bridge's two verbs, the panels that
stop when hidden, what the picker draws - and the rest is a release build that
compiles and lints clean.

## What was new in 2.5.5

**The blocks were on the screen and nowhere anybody could see them.** The
palette sat at the bottom of the same scrolling page as your script - so on a
phone the search box, the categories and the results were all below the fold,
behind the button bar. Searching worked, the counter said "9 of 154", and the
nine blocks were somewhere you had to go looking for. A list you have to
scroll to find is a list that is not there.

**Adding a block is a screen of its own now.** A wide **+ Add a block** button
at the bottom opens it: the search and the categories are pinned at the top,
the results fill the screen, and it stays open while you tap, saying what went
in and how many blocks you have now - so several can go on in a row. **Done**
takes you back to the script and scrolls to the block you just added.

That leaves the main screen as your script and nothing else, which is what it
should have been: full width, no hunting past it for a control. **New** moved
up beside **Saved**, and the bottom bar is now **+ Add a block**, **Code** and
**Save**.

Where the next block will land is said in both places it matters - beside
**Your script**, and at the top of the picker - so you can see it without
opening anything.

Small things from the same sweep: the picker forgets what you searched for last
time, keeps the category you were browsing, and a container's closing line
follows the values you filled in rather than the defaults it was made with.

The panel's test suite grew with it - the picker is opened, searched, tapped
and closed there, and the "results are unreachable" shape of this bug is now
something a test can see.

## What was new in 2.5.4

**The Creator tab was confusing, and one of the reasons was a bug.** Both are
fixed, and the panel has been rebuilt round one rule: everything on screen is
the code.

**The palette showed templates.** A row said `print(@text@)`, which reads as
placeholder text rather than as a block that does something - so a list of 154
blocks looked like a list of holes. Every row now shows the line that block
actually writes, filled in: `print("Hello")`. So does every row of your script,
and those come from the compiler itself rather than being drawn separately and
left free to drift.

**Switching language did nothing.** The chooser asked `confirm()` first, and a
WebView with no chrome client answers `confirm()` by ignoring it - which the
page reads as "no". So picking JavaScript, HTML, CSS or Markdown silently kept
you where you were, with the Python palette still on screen. There is no
question now, because there is nothing to ask about: **Creator keeps one script
per language**, and the chooser moves between five drafts instead of throwing
one away. Nothing in the panel calls `alert`, `confirm` or `prompt` any more,
and a test fails the build if one comes back.

**The rest of the panel, made plainer.** The tools on a selected block are
words - Fill in, Up, Down, Move inside, Move out, Duplicate, Delete - instead
of arrows. A line above the search box always says where the next block will
land: at the end, after the selected one, or inside it. A block that holds
other blocks says so, its contents sit inside a rail, and its closing line is
greyed out beneath them. The starter script is labelled as an example. Anything
that goes wrong now appears **on the page**, not only as a toast that has
already gone.

**And the panel is tested now.** `tools/test_creator_ui.js` runs the real panel
against a stand-in DOM and the real catalogue - taps blocks, switches
languages, moves things, deletes things - and asserts what ends up on screen.
Both bugs above would have failed it. Playing the panel in a WebView is still
the one thing no suite here can do.

## What was new in 2.5.3

**Creator: a tab where code is built out of blocks.** Switch on the Creator
plugin and More grows a tab of its own, in the app's own colours, where you
stack blocks instead of typing. **363 blocks** across five languages - Python
(154), JavaScript (98), HTML (49), CSS (42) and Markdown (20).

Pick a block and it lands in your script. Tap one to select it and it grows a
row of buttons: move it up or down, put it **inside** the block above, take it
back out, fill in its holes, copy it, delete it. Select a container - a loop,
an `if`, a `<div>`, a CSS rule - and the next block you pick goes *inside* it.
That is the whole trick to building a loop on a phone.

**Build** shows the source your blocks write before anything is saved. **Save
to Files** writes a real file into your workspace - and then it is just a file:
the editor opens it, `run thing.py` runs it, a folder of them is a page the
Pages tab serves. Nothing in it says it was made of blocks.

What it gets right is the *shape*: the colons, the braces, the indentation, the
closing tags, the escaping. Every one of the 154 Python blocks is compiled and
handed to Python's own parser by the test suite, so a block that writes a
syntax error is a build that fails here rather than a file that fails on
somebody's phone. What it does not do is check your expressions, or read a file
back into blocks - blocks go one way, and that is stated in the guide rather
than discovered.

From the console: `blocks`, `blocks langs`, `blocks build <name>`,
`blocks save <name>`.

**Pages now points at a folder you already have.** Press **Choose a folder**
and pick one out of the workspace. Making a page used to mean the app inventing
`workspace/pages/<slug>/` for you, and a folder called `pages` sits in the way
of `vendor/` from Packages Pro, of whatever pip installed, and of your own
folders. Now a page points at a folder you chose, and the only thing it makes
on its own is a starter folder at the top of the workspace when you ask for one
from a template.

**And a deploy no longer touches your workspace.** Deploying packs the folder
into a copy first - skipping `__pycache__`, `.git`, `node_modules` and hidden
files - uploads that, and keeps it, along with the record of where and when
each deployment went, in the page's **own** storage inside the app: one folder
per page, outside the workspace entirely. So "what did I actually send" has an
answer afterwards, and nothing appears in your files that you did not put
there. **Clear** on the card throws the copy away and keeps the history.

**Using what you installed, everywhere.** The guides now say it plainly, and
one thing that was only true in principle is true in practice:

* `pip install requests` puts a package in the **one interpreter** everything
  here shares, so `import requests` works in the console, in a file you Run, in
  a server, in a page's `app.py` and in a plugin. Nothing to activate.
* `web install htmx` fetches into `vendor/` at the top of the workspace - but a
  page is served rooted at its own folder, so `../vendor/...` is a path no
  browser will follow. **`web use htmx blog`** is new: it copies the library
  into `blog/vendor/` and prints the tag to paste. Offline, served from the
  phone, and deployed to Cloudflare unchanged.

**Plugin panels can ask a question again.** A WebView with no chrome client
answers `confirm()` by ignoring it, which reads as "no" - so a panel's "are you
sure?" was a button that did nothing. Panels now get the app's own dialogs for
`alert` and `confirm`, and their JavaScript errors go to the debug console
instead of nowhere.

## What was new in 2.5.2

**Music: your own audio, playing while you work.** A new tab in the app itself.
Import anything on the phone - MP3, M4A, FLAC, OGG, WAV, and video files too -
and it is copied into PyCmd, so the library works with no signal, no account and
no permission to read the rest of your storage. Deleting a track deletes the
copy; whatever you imported it from is never touched.

A video file is taken for its sound. `.mp4`, `.mkv`, `.webm`: the audio plays
and the picture is never decoded, because people have video files they want to
hear and transcoding on a phone to get at the sound is not a thing worth doing.

**Playlists, ordered by you.** Make one, name it, rename it, delete it; add and
remove tracks; move a track up or down, because the order is the whole point of
having made the playlist. Deleting a playlist keeps the tracks; deleting a track
takes it out of every playlist it was in.

**Loop off, all or one. Shuffle on or off.** Loop has three states rather than
two, and next means next: with loop set to *one*, pressing next still goes to a
different song rather than replaying this one, which is what the player would
have done left to itself.

**It keeps playing.** Switch tabs, leave the app, lock the phone - it keeps
playing, and the notification, the lock screen and the quick-settings media chip
all have play, pause, previous and next. None of that is drawn by PyCmd: the
player is a real media session in a service, so Android draws the rest, a
headset button reaches it, and a car head unit does too. A phone call pauses it
and it comes back afterwards; unplugging the headphones pauses rather than
playing it out loud to the room.

**The fork guide's download button is where the guide says it is.** It said "the
end of this guide in the app has a Download the source button" and there was no
button there - the button was on the Guides list, one screen back. Now the guide
ends with a real one, and the sentence describes what is actually on the screen.
Links from one shipped guide to another work too: those used to be a 404,
because a guide is rendered from memory and has no folder behind it to serve a
sibling from.

**Verified the way everything here is verified:** the Python suites, the
JavaScript suites under Node, the published manifest check, and a release build
with R8 and Lint. There is a new suite for the music library - importing,
naming, playlists, ordering, deleting a track out from under a playlist, and a
registry that survives being reloaded and being corrupted. Playback itself needs
a phone: no emulator can run here, so the media session, the notification and
the lock-screen controls are the parts a person has to look at.

## What was new in 2.5.1

**Pages: websites that live in the app.** A new tab in the app itself, not a
plugin. Name one, pick what it starts as - a page, a Python site with Flask
templates, a JSON API, or an empty folder - and press Create. Then **Run**, and
it is a real server: anyone on the same wifi can open
`http://192.168.1.42:8631/` in a browser and see what you built on a phone.

**70 pages, 25 running at once.** Both numbers are on the card, and both are
refusals rather than surprises: past them it says so instead of quietly turning
the phone into a space heater. Every page keeps its name, its port and its
files, so running it again is a tap rather than a launch form filled in from
memory. Rename, delete (with the files, or without), open its folder in Files,
or adopt a folder you already had.

A page can be anything the app can run, because a page is a folder and the
Servers tab's rules decide what running one means: an `app.py` that imports
Flask is started, an `index.html` is served, a single runnable file is run. With
the built-in kit on, that is Python, HTML, CSS, JavaScript, C, Go and Rust.

**Share: an address anyone, anywhere can open.** A phone sits behind carrier
NAT, so nothing on the internet can dial it - the only way to be reachable is
for something with a public address to accept the connection and pass it down.
That is a tunnel, and there is now a tunnel client here: **Share** on a running
page asks a free service for an address and relays visitors to your page.

Three things about it are said in the app rather than discovered later: the
address is **random and new every time**, it works **only while PyCmd is
running**, and it is **not private** - anyone with the URL is on your page. It
also depends on a free service run by other people, which is down sometimes,
and when it is, the app says so rather than pretending.

**Cloudflare: a real address that stays up.** With the full kit on, the Pages
tab grows a Cloudflare section. Connect an account - your account ID and an API
token - and a page deploys to **Cloudflare Pages** instead of being served from
the phone: a `pages.dev` address, up when your phone is off, and it takes your
own domain. Workers can be published the same way.

It uses the public REST API directly, because wrangler and Node do not exist on
Android: an upload token, a check for which files Cloudflare is already
holding, the upload of the rest, then a deployment built from a manifest. Each
page card then chooses **This phone** or **Cloudflare**.

Use a **scoped token** (Cloudflare Pages: Edit), not the Global API Key: a token
can be revoked on its own, and a phone is a thing that gets lost. It is checked
against the account before it is kept, lives in the app's private storage rather
than your workspace, and is never shown back - only its last four characters.

**It keeps working with the app closed.** Running pages and servers are held up
by the foreground service, so they answer while you are in another app. And two
new switches under the update card ask Android to look for updates on its own
schedule, and to download them too.

What Android decides, and no app can: the check runs roughly daily on wifi with
the battery not low, rather than at a time you pick; a force-stopped app runs
nothing at all until it is opened again; and nothing installs itself, ever - the
notification says the wait is over, and the tap is still yours.

## What was new in 2.5

**`pip install flask` works, typed exactly like that.** The console now takes
the line before Python does, so the thing everybody tries first is no longer a
syntax error answered with

```python
import os
os.system("pip install flask")     # which does not work on Android either
```

There is no pip binary on a phone - the installer is inside this app - so that
workaround never installed anything. Now `pip install`, `pip list`, `pip show`,
`pip uninstall` and `pip freeze` all do what they say, and about thirty more
commands come with them: `ls`, `cd`, `pwd`, `cat`, `head`, `tail`, `mkdir`,
`touch`, `rm`, `mv`, `cp`, `find`, `tree`, `du`, `run`, `serve`, `servers`,
`stop`, `open`, `preview`, `go`, `clear`, `version`, `env`, `which`, `help`.

**And it never eats your Python.** The rule is narrow and tested from both
sides: the first word has to be a command, a name you have defined wins over
the command of the same name (`ls = [1, 2]` then `ls` gives you your list), and
anything that looks like Python - an assignment, a call, a dot, an operator, a
keyword - goes straight to the interpreter. Paths that start with an operator
character are understood as paths: `cd ..`, `ls /sdcard`, `cat ~/notes.md`,
`head -3 file` all work, while `ls - 1` is still arithmetic.

**Packages says whether a package can work here before you download it.**
**Look it up first** asks PyPI for the summary, the size, the Python it needs
and the versions it has - and, most usefully, whether there is a wheel a phone
can install at all. A library that ships only compiled builds used to cost a
minute of downloading before it said so.

**Packages Pro, a new built-in plugin: packages for everything that is not
Python.** JavaScript and CSS libraries, web fonts and whole starter projects,
fetched into `vendor/` in your workspace so a page works with no connection -
which matters here, because the preview is a loopback server and "needs a CDN"
means "needs the internet to look at your own file".

```
web install htmx          web catalogue        web list
kit new blog flask        kit kits
```

Seventeen libraries have a one-tap button - htmx, Alpine, Tailwind, Bootstrap,
Bulma, normalize.css, three.js, Chart.js, D3, Vue, Preact, marked, highlight.js,
Lodash, Day.js and two self-hosted fonts - and anything else on npm works by its
own name. The seven kits are folders rather than files, because the Servers tab
knows how to run a folder: `kit new blog flask` is a project that runs the
moment it exists.

**The versions you have had are kept, and you can go back.** Every update is
filed on external storage instead of being thrown away, up to a ceiling you set
- 250 MB, 500 MB, 1 GB, 2 GB or off - with the oldest pruned first. Each build
can be reinstalled, saved out to the phone, or deleted.

Going *back* to an older build is the one thing Android will not do in place:
it refuses a lower versionCode over a higher one and no ordinary app can
override that. So the card says so, and gives the sequence that does work -
save the APK to the phone, back up the workspace (it writes the zip and asks
where to put it), uninstall, install the saved APK, bring the workspace back.
The backup step is the point: uninstalling deletes everything the app owns.

**Where to write when something breaks.** **More → System** now carries
`andrejbaltes4@proton.me`, and tapping it opens a mail app with the version
already in the subject.

**Forks are welcome, and there is a guide.** A new **Forking PyCmd** guide
covers what the code is made of, how to build it, what not to change (the
application id, or every installed copy becomes a second app), and how to
publish updates for a fork of your own - the update address is editable
precisely so a fork can serve its own `latest.json`. At the end of it, a
**Download the source** button pulls the whole repository onto the phone as a
zip. The conditions are the ordinary ones: keep PyCmd's name and credit where
they are, and do not present the original as a copy of your fork.

**`latest.json` now describes the release properly**, so a download page can be
built from it with nothing else: `name`, `sizeText`, `releasedAt`, `minSdk`,
`minAndroid`, `abi`, `python`, and links to the changelog, the checksums, the
source and the source zip. The app still reads only the handful it needs and
ignores the rest.

## What was new in 2.4.2

**It is a release build now, and half the download.** **35 MB to 18 MB**, same
source, packaged the way an app is meant to be shipped.

Two things did it. R8 strips out the AndroidX and Compose code this app never
calls - 10 MB of dex down to 3 - and resources nothing references go with it;
the `debuggable` flag, which let anything with a USB cable read the app's
private storage, is gone at the same time. Then the native libraries: CPython
and its OpenSSL are 10 MB, and modern packaging stores them uncompressed so
Android can map them straight out of the APK. That is the right trade for an
app downloaded through a store, which compresses the transfer itself; this one
is a raw APK coming down somebody's phone connection, where 10 MB is 10 MB.
Compressed they are 3.7.

The cost of that second one is worth knowing: Android unpacks those libraries
when it installs, so the app takes about 10 MB more room on the device and the
install itself is a little slower. The download is half the size. If you would
rather have the storage back, that is one line in `app/build.gradle.kts`.

**And it still updates in place.** It carries the same application id and the
same signing key as every build before it, so it installs straight over
2.4.1-debug - or over 2.3 - and keeps the workspace. That is also why a release build says
`.debug` in its package name: Android has no way to change an installed app's
id, and a new one would install *beside* the old app rather than over it,
leaving the workspace behind in the copy nobody opens again. The id is a name,
not a claim about the build.

**Nothing else changes.** `latest.json` points at this APK, the app checks the
same address it always did, and **More → System → Check for updates** downloads
it, verifies the hash and the signature, and installs it over itself. There is
nothing to set up and no site to visit.

**What R8 was told to leave alone.** Everything reached by name rather than by
a call: Chaquopy's runtime, this app's own classes (Python calls back into
several of them by method name, and a renamed method is a crash that only
happens on a phone), and anything a WebView invokes from JavaScript. The build
now runs in the test suite too, so a keep rule that stops being right fails
here rather than after a download.

## What was new in 2.4.1

**Pointing Run at a folder runs the project in it.** It used to mean one thing -
hand the folder to a file server - so a Flask project answered with a directory
listing of `static/` and `templates/`: the files, correct and useless. A folder
is now looked into first, and the first of these wins:

| In the folder | What Run does |
|---|---|
| `app.py`, `server.py`, `wsgi.py`, `manage.py`, `main.py`... that imports Flask, Django, FastAPI, `http.server`... | Runs it. That is the app. |
| `index.html` | Serves the folder and opens that page |
| one of those entry names that serves nothing | Runs it anyway - it is still the front door |
| exactly one runnable file | Runs that one |
| none of the above | Serves it as a listing, and says why on the page |

Whether a script serves is read out of the file rather than guessed from its
name: `main.py` that imports Flask is a server, `main.py` that crunches numbers
is not, and starting the second one because it had the right filename would be
its own kind of wrong. The launch form says which it picked **before** you press
Run, and "Serve a folder" now offers a one-tap **Run app.py instead** when there
is something in there to run.

**Flask apps get the port you chose.** `app.run()` binds `127.0.0.1:5000` with
the auto-reloader on - on a phone that is a server nothing can reach,
restarting itself with a process launcher Android does not have. PyCmd now
fills in the host and port the form asked for wherever the code left them out,
and turns the reloader off. Code that names its own port still wins, and the
server card corrects itself to the port the app really took, read from what the
framework printed - a View button pointing at the wrong port is how a working
server looks broken.

**The listing itself is worth reading now.** A folder with no `index.html` used
to answer with Python's bare `<ul>` of names. It is now a real page: folders
first, sizes, which files this device can run, a way back up - and, at the top
of the tree, a sentence saying why you are looking at a list at all. The most
useful one names the exact mistake behind the screenshot that prompted this
release: `templates/` and `static/` with no `app.py` is the *inside* of a Flask
project, and the app that renders those templates is the folder above.

**https on an http port says so.** Browsers increasingly try HTTPS first for a
bare address like `10.1.6.64:8000`. The handshake arrived as unparseable bytes
and produced a wall of "Bad request version" in the console. It is now one
line, once: something tried https, here is the http address to open.

## What was new in 2.4

**PyCmd can update itself now.** **More → System → Check for updates** reads a
small published manifest, and if there is a newer build it downloads it, checks
it against the fingerprint published beside it, checks it carries the same
signing key as the build you are running, and hands it to Android to install
**over** this one. Your workspace, the packages you installed with pip, your
plugins and every setting stay exactly where they are - Android replaces the
app rather than removing it. Deleting PyCmd first is the thing that loses all
of that, and until now that was the only way to move between versions.

**Which needed one key, kept in the repo.** Android only lets an APK replace an
installed one when both were signed by the same key, and Gradle's debug key is
generated per machine - so two builds of the same source, made in two places,
were two different apps to the installer. [`keystore/pycmd.keystore`](../keystore/)
is now that one key (the standard Android debug certificate; not a secret, not
for a store), and this APK is signed with it. It is the same key 2.3 was signed
with, so **2.4 installs straight over 2.3**. From here on, every build can.

**And it tells you an update exists.** Once a day, while the app is running, it
reads that one manifest by itself and puts a dot on **More** and a line on the
System card if something newer is out. That is the whole of it: nothing is
downloaded until you press Download, nothing is installed until you press
Install, and a check that fails on a phone with no signal says nothing at all,
because it is not a question you asked.

**It tells you before it cannot.** A build calling itself another package, or
signed with a different key, is refused with the reason instead of being handed
to the installer to fail as "App not installed" - the failure that makes people
uninstall the app, which is precisely what empties the workspace. The address
it checks is editable too, at the bottom of the card: a fork, another branch, a
machine of your own. The fingerprint check runs whatever it points at.

**Music, video and everything else you do not type.** The new-file menu now
offers audio, video, images, PDFs, archives and fonts, and picking one opens the
phone's picker instead of writing a template - an empty `.mp3` is not a file
anybody wanted. They come in through the same importer as everything else, sit
in the workspace, and export back out. This rides with **Polyglot Files**, the
built-in kit plugin, along with the rest of the file types.

**And they play.** Tap an `.mp3` or `.mp4` and it opens a real player - with a
seek bar you can drag, because the preview server now answers HTTP byte ranges
(206, `Content-Range`, open-ended and suffix ranges, 416 past the end). Browsers
will not let you scrub without that, which is why a media file opened from a
`file://` URL only ever plays from the start. What decodes is the phone's
business: MP3, AAC/M4A, FLAC, Ogg, WAV, MP4 and WebM are safe, MKV and MOV
depend on the device, and the player says so rather than showing a dead control.

**A file that is bytes is never opened as text.** Tapping media opens the
player, and anything else with a NUL in its first few KB refuses the editor
with a sentence. The editor reads text: it turns every byte it cannot decode
into a replacement character, and saving that writes the ruined version over a
file that was fine a moment ago.

## What was new in 2.3

**The examples folder can be deleted.** It was re-created on every start, which
made `examples/` a folder you were not allowed to be rid of - not the app's
call to make. Deleting it sticks now, and **More → System → Put the examples
back** is there if you change your mind.

**An import that would overwrite something asks first.** Bringing in a
corrected file used to become `notes-2.md` in silence, so the old one stayed
exactly where every script still pointed at it - which is how you end up
debugging a file you already fixed. Worse for folders: copying over an existing
one failed partway through and left some new files sitting beside some old
ones. Now it asks - **Replace**, **Keep both** or **Cancel** - and says how big
what is already there is and when it last changed. Replacing a folder removes
the old one first, so nothing of it is left mixed in; replacing a file writes to
a neighbour and moves it into place, so a failure halfway cannot leave you with
neither.

**A file from the phone can go straight into Downloads.** It was a folder only
the app could fill - a URL fetch or an export - which made it the one place you
could not simply put something.

**Listings cannot show you the past.** Every refresh - files, downloads,
servers, packages - is tagged, and an older answer arriving late is dropped
instead of overwriting a newer one. Two refreshes racing is ordinary (an import
finishing while the Servers tab polls), and the slower one used to win whatever
it was holding.

**And two imports started in the same millisecond** were handed the same
staging folder, so the second one found the first one's files already sitting
in it.

## What was new in 2.2

**A long line stopped being editable past a certain point.** The editor sized
its textarea from the highlighted layer underneath it, and that layer is an
absolutely positioned box - which shrink-to-fits *within its container*. Past
the width of the screen it stopped growing, so the textarea did too, and the
end of a long line became unreachable. Nothing is measured that way any more:
the character width is taken from the real font once and every width and height
after that is arithmetic, which cannot be capped by anything.

**And why it was intermittent.** The editor's page is built before its tab is
ever shown, so that one measurement landed on a view with no width and fell
back to a guess. It now notices it measured nothing and takes the numbers again
the moment the page has a size - and again if the font swaps in later.

**Wrap long lines**, in the editor's ⋮ menu, with the gutter kept honest: each
line number grows as tall as its line now takes, and it is redrawn when a line
gains a row rather than only when the file gains a line. **Go to line...** is
in the same menu.

**Each language indents its own way.** Python's rules were applied to all six,
so a Go file got no indent after `{` and an unwanted outdent after `return`.
Enter now follows the language, typing `}` steps back out a level, and the key
strip above the keyboard offers that language's characters - `;` and `//` for
the brace languages, `<` and `>` for markup - instead of `self` and `#` for
everything.

**The caret is kept on screen** while you type off the edge of a line, and the
editor no longer copies the whole document to work out which line it is on -
which it did on every tap, twice, and which is a good deal of why a long file
felt heavy. Android's swipe typing and autocorrect are also left alone
mid-word, rather than having the layer under them rewritten while a word is
still being composed.

## What was new in 2.1.1

**Plugin settings actually work.** Every control was drawn from the values
Python had returned, and nothing ever wrote back into that - so a switch sprang
back the instant it was tapped and a choice never moved. The form owns its
state now; saving is what happens afterwards, and typing is coalesced so a word
is one write rather than one per letter.

**A long description no longer makes a card taller than the screen.** It
collapses to three lines with *Show more*, and a plugin's file list caps at
twelve.

**Plugins can add their own guides.** A `guides` block lists documents of
yours - `.md`, `.txt` or `.html` - in the app's **Guides** screen under *From
your plugins*, opened in the same reader the app's own guides use. All three
bundled plugins now ship one, so switching Cloud on and wondering what to type
has an answer one tap away.

## What was new in 2.1

**A plugin's section scrolls.** Opening one inside an existing screen put a
scrolling page inside a scrolling list, and the list won every gesture - so the
section could not be scrolled at all. The page now claims a drag that starts
inside it, and hands it back at the top and the bottom so flicking past the
section still works. There is also a button on every section header that opens
the same page with the whole screen to itself.

**Plugins can do considerably more.**

* **Settings** - declare `text`, `number`, `switch` or `choice` fields and the
  app draws real controls in the plugin's row. `api.setting("name")` reads
  whatever the user chose. A plugin with one switch no longer needs a whole
  HTML page to offer it.
* **Lines in a file's menu** - `actions` puts your own entry in the ⋮ menu of a
  file or folder in the Files tab, filtered by extension, calling your export
  with the path.
* **Asking the app to do something** - `api.open_file`, `api.run_file`,
  `api.preview`, `api.serve`, `api.new_file`, `api.go_to`, `api.open_panel`
  and `api.refresh`. Requests rather than calls: they never wait, and they are
  ignored if the plugin has been switched off in the meantime.

The Cloud plugin uses all three: four settings, and *Upload to cloud storage*
on any file.

**`api.toast()` works.** It emitted into a flow nothing was reading, so it has
never shown anything. Found while wiring the rest of this.

**The About dialog says the right version.** It said 1.0 for four releases,
because a string in a composable has no way of knowing it is out of date. It
now reads the version out of the build, so it cannot drift again.

## What was new in 2.0

**Plugins can change the app, not just sit beside it.** A plugin already had a
tab of its own; now it can also put a card of its own **inside** one of the
app's existing screens - Files, Servers, Packages, Downloads, Plugins, System,
Debug or Guides - with its own page, its own icon and its own height. Nothing
about the app has to change to make room. That is how Server Pro reaches the
Servers tab and how Cloud reaches Files.

**Three plugins now ship with it**, installed on first run and switched off
until you want them, listed under *Ships with PyCmd* instead of pretending you
installed them:

* **Server Pro** - a live board in the Servers tab with a health check that
  says whether each port really answers, restart, a free-port finder, an
  index-page writer, and the commands `servers`, `serve`, `restart`, `shut`
  and `ports`.
* **Cloud** - Supabase and Firebase over their REST APIs, with nothing to
  install.
* **Scheduler** - run a script again every so often: `every 300 backup.py`.

**Supabase and Firebase, properly.** 116 operations across the two: PostgREST
selects, filters, inserts, upserts, counts and Postgres functions; GoTrue
sign-up, sign-in, OTP and the admin endpoints; Supabase Storage and edge
functions; Firestore documents, typed values and structured queries; Identity
Toolkit; the Realtime Database; Firebase Storage. Connect a project once in
More → Cloud and a script, a server, a console command and the panel all reach
it as the same user. The keys live in the app's own storage, never in the
workspace, so exporting your files never carries them along. Realtime
subscriptions are the one honest gap - both are WebSocket protocols and
`urllib` does not speak WebSocket, so there is a gap rather than a fake.

**The Servers tab does more.** It takes a folder as happily as a file, and a
running server has a **View** button that opens it in the preview.

**A new guide**, on the phone and in the repo: *The plugins that ship with it*
covers every built-in switch and every bundled plugin, and the difference
between the two.

## What was new in 1.4

**The Servers tab runs anything, not just Python.** A C, Go or Rust file goes
to its interpreter; a `.js` file to the device's own JavaScript engine; an
HTML page serves the folder it sits in and opens on that page. The form says
which of those it is about to do *before* you press Run, and refuses up front
anything that cannot run here at all, with the reason.

**Plugins can add a tab of their own.** A `tab` block in the manifest - a name,
one line of description, and an image file the plugin ships - puts a row in
**More** that opens the plugin's panel. No change to the app, and it only
appears while the plugin is switched on. PLUGINS.md documents it, and
**Server Pro** is a working example of it.

**Server Pro**, a plugin that ships switched off. Turn it on and you get a live
board of everything running with a health check that says whether the port
actually answers, Restart and Kill on each one, a free-port finder, an
index-page writer for a folder that has none, and the console commands
`servers`, `serve`, `restart`, `shut` and `ports`.

**Answering the doctor no longer freezes anything.** Saying `yes` to "install
pygame" used to run the download on the thread the Stop and Kill buttons come
in on - so the server froze, and the button meant to rescue it was stuck behind
the same queue. The fix now runs on its own thread, Stop and Kill have threads
nothing else can occupy, and the console says what is happening as it happens:
*OK - downloading pygame from PyPI*, *OK - renaming index2.html to index.html*,
*OK - no fixing today*. A reply that is neither yes nor no gets an answer too,
instead of silence.

**Kill works on a wedged server.** A script parked in its own `accept()` cannot
be interrupted - an async exception has nowhere to land inside a blocking C
call - so Kill now knocks on the port first, which makes the call return and
the exception fire. Before this it detached and left the port held.

**Pasting a long program is instant.** It used to take about twenty seconds:
the console's input box laid out every line of what you pasted before it could
draw six of them, on every redraw. A pasted program is now held beside the box
as *"2 599 lines pasted"* with Run and Clear. The editor got the same
treatment - a big document repaints immediately in plain text and colours
itself once you stop typing - and console output is now sent to the screen in
batches rather than one line at a time.

**A server's console keeps what the script printed.** It only ever kept its own
two lines, so reopening a server console showed "Running x" and nothing else.

## What was new in 1.3

**Previews that scroll.** A code block used to be its own sideways scroll
strip, and on a touch screen a strip like that swallows a vertical drag - which
is why a long document, the plugin guide most of all, felt like it was ignoring
the scroll. Code now wraps instead, so the drag reaches the page. Long
documents also get a Contents panel that jumps to any section, and there are
A- / A+ buttons for text size.

**Previews for plain text.** A `.txt` or `.log` file opens as a readable page
with its line, word and character counts, instead of raw unwrapped text.

**Everything is served the same way.** The guides that ship inside the app now
come off the same loopback server as a file preview, so anchors, scrolling and
reloading behave identically wherever you are.

**Folders out to the device.** Any workspace folder can be exported as a zip
from its menu in Files, and anything in Downloads has a *Save to device*
button that writes it out through the system picker - into the phone's real
Downloads folder, or straight onto a USB drive. That is the route off the
phone: a picker can hand over a file, never a folder, so a folder becomes a
zip first. Single workspace files have the same *Save to device* item.

## What was new in 1.2

**Plugins you write yourself.** A plugin is Python the app imports, plus an
optional HTML panel that becomes its own tab. Install from a file, a folder or
a zip - or from the workspace, for a plugin written inside PyCmd itself. They
are not sandboxed, and the app says so on a screen you have to read before the
picker opens. PLUGINS.md is the authoring guide, and the app can show it on the
phone: Plugins -> How do I write one?

**Preview that behaves like a browser.** A page is served over a loopback HTTP
server rooted at its own folder, so scripts run, stylesheets and images load by
relative path, `fetch` works, and links inside the site follow. Buttons work.
Preview also covers JavaScript (runs it and shows what it logged), JSON, CSV,
SVG and images.

**It offers to fix what it can.** A missing file one typo away from one that
exists, an import of a package that is not installed, a port already in use, a
served folder with no index page: the console says what it would change and
waits for `yes`. It never acts on its own.

**Upload from anywhere.** Files can take several files at once, or a whole
folder, from the system picker.

**Search** in the file list and in the plugin list.

**Two more screens** behind More: Guides (the manuals, on the phone) and System
(versions, storage, what is running, and housekeeping).

## What was checked before this was committed

The same source, built for x86_64, was installed on an Android 11 emulator and
driven through: Go, Rust and JavaScript ran from the Files tab with the right
output, an HTML page previewed with its external stylesheet and script loaded
and its button working, a plugin was installed from the workspace and switched
on, its console command answered, and its panel called back into its own
Python. The APK here is that source built for arm64 instead, which changes
the CPython binaries and nothing else.

1070 checks run before any of this is committed, across fourteen suites - the
new one, `test_pages.py`, drives real pages on real ports and puts a stand-in
tunnel service and a stand-in Cloudflare on loopback to check what is sent to
each:
`test_runtime.py`, `test_plugins.py`, `test_shell.py` (the console's commands,
and the lines it must *not* take), `test_go.py`, `test_rust.py`, `test_cloud.py`,
`test_bundled.py` (every plugin that ships, driven for real), `test_c.py`,
`test_preview.py`, `test_pages.py`, `test_branding.py`, `test_doctor.py`,
`test_editor.js` and `test_js.js`.
Each language check is a real program paired with the output the real compiler
produces. The rest go after the things that are
awkward to be sure of by looking: a script wedged in `accept()` is started for
real and killed, to prove the port comes back; the preview checks fetch pages
back off the loopback server; the editor checks run the real
editor against a stand-in DOM and read back the widths and heights it writes,
so the sizing is arithmetic that can be checked - including the case that
caused this release: a page measured before it was ever on screen. `tools/run-tests.sh` runs the lot, then
a debug build and Android Lint.

`test_cloud.py` runs a local HTTP server that plays Supabase and Firebase,
records exactly what the client sent, and answers the way the real APIs do -
which is what makes the URL shapes, the PostgREST filter syntax and Firestore's
typed values checkable rather than hopeful. `test_bundled.py` installs the three
bundled plugins the way the app does and drives them: it starts a real server
and restarts it through Server Pro, schedules a real job, and renders every
panel.

The preview suite covers this release's range serving directly: it asks the
real loopback server for `bytes=10-19`, an open-ended range and a suffix range,
and checks the status line, the `Content-Range` header and the exact bytes that
come back - plus a 416 past the end of the file and a nonsense `Range` falling
back to the whole file. `tools/make_latest.py` runs in the suite too, and fails
the build if `dist/latest.json` does not match the APK sitting beside it: a
manifest whose hash is stale is a download every phone would refuse.

What could not be checked here, and is worth knowing: the tunnel was proven
against a stand-in service, not against localtunnel.me, and the Cloudflare
deploy against a stand-in API rather than a real account. The shapes, the
ordering, the headers and the error handling are checked; whether those two
services accept it on the day can only be found out with an account and a
connection. If either misbehaves, the app reports what it got back rather than
guessing, and the address is at the bottom of System.

The 2.5 work was verified by those suites and by Lint on the built APK, and by
reading the shipped file: the APK declares versionCode 14, the same package and
the same signing certificate as every build since 2.3, it is not debuggable,
and it carries the new plugin, the new guide and the console's command module.
It has not been run on a device - this machine has no hardware virtualisation,
so no emulator can start here.

The 2.4.2 packaging change was verified by building it and reading the result:
R8's own report says none of this app's classes or Chaquopy's were removed or
renamed (only empty static initialisers went), the APK still declares the same
package, versionCode 13 and the same signing certificate as 2.3 did, it is no
longer marked debuggable, and every asset - the Python runtime, the guides, the
bundled plugins, the examples - is still inside it. It has not been launched on
a device. If it misbehaves, install a newer build over it from the browser;
that path does not need the app to start.

The 2.4 changes were verified by those checks and by Lint on the built APK,
not on an emulator: this build machine has no hardware virtualisation, so no
emulator could be started for it. In particular, **the update flow has not been
run on a device** - what is checked here is that the manifest matches the APK,
that this APK carries the same signing certificate as 2.3
(`c318e126...4f8d6c`, confirmed with `apksigner`), and that the code paths
compile and lint clean.

It installs without any Play Store involvement. The signing key is in the repo,
which is what makes an update possible at all - and also means anybody can
build an APK this one would accept as an update. That is the price of shipping
an APK by hand rather than through a store; it is not a key to use for anything
published to one.

## Installing it on a phone

0. **Already running PyCmd? Do not uninstall it.** Install this straight over
   it - same key, same package, so Android upgrades it and keeps everything.
   Uninstalling is what deletes the workspace. (And from 2.4 on you will not
   need to do this by hand: **More → System → Check for updates**.)
1. Download the APK onto the phone (or copy it across by USB).
2. Open it from the Files app or the download notification.
3. Android will ask whether to allow installs from this source — that prompt
   appears for any app that did not come from a store. Allow it, then confirm
   the install.
4. Launch **PyCmd**.

The first launch takes a few seconds longer than later ones: the Python
interpreter and its standard library are unpacked on that first run. The title
bar shows `starting` until it is ready, then switches to `Python 3.13.x`.

Once it's running, see [../TUTORIAL.md](../TUTORIAL.md) for a walkthrough of
every tab with things to paste in and try.

## Installing over USB

```bash
adb install -r dist/PyCmd-2.5.5.apk
```

## Checking the download

```bash
sha256sum -c dist/SHA256SUMS.txt
```

## What `latest.json` is

The file the app checks. It is generated from the APK next to it, never typed:

```bash
python3 tools/make_latest.py dist/PyCmd-2.4.1-debug.apk --notes "one line"
python3 tools/make_latest.py            # checks the one that is there
```

| Field | What it is |
|---|---|
| `versionCode` | The build number. The app offers an update only when this is higher than its own. |
| `versionName` | What the card shows: `2.5.5`. |
| `package` | Which app this is for. A mismatch is refused before the download starts. |
| `url` | An `https://` address of the APK. Plain `http` is refused. |
| `sha256` | The APK's fingerprint. The download is checked against it and thrown away if it differs. |
| `bytes` | Its size, so the progress bar means something before the server says. |
| `notes` | One line, shown on the card. |

The check runs as part of `tools/run-tests.sh`, so a manifest that no longer
matches the APK in `dist/` fails the suite rather than reaching a phone.

## A note on the device requirement

This APK carries **arm64-v8a** binaries only, which is what keeps it to 32 MB
rather than 46 MB. Every Android phone sold in roughly the last decade is
arm64, so this is the right build for a real device.

Two cases need a different build. A 32-bit-only phone from before about 2016
cannot run it at all: Chaquopy's Python 3.13 runtime ships no 32-bit binaries.
An **x86_64 emulator** needs the x86_64 slice, which the default build
produces:

```bash
./gradlew :app:assembleDebug      # both ABIs, one APK per ABI plus a universal one
```

## Rebuilding it yourself

```bash
./gradlew :app:assembleDebug -Ppycmd.abi=arm64-v8a
# -> app/build/outputs/apk/debug/app-debug.apk
```

Leave the property off to build for both ABIs instead.

See the [main README](../README.md) for what the build needs.
