# Testing PyCmd — a first-run walkthrough

You've got the app installed. This is a tour through every tab with things to
paste in and try, so you're not staring at a blank screen wondering what to
type.

---

## 1. Console — type Python and press Run

Open the app. The title bar reads `starting` for a few seconds on first
launch (CPython is unpacking its standard library), then switches to
`Python 3.13.x`. That's your signal it's ready.

Paste these into the console box **one at a time** and hit the ▶ button:

```python
2 + 2
```
Prints `4` — the console echoes the value of the last expression, like a real
REPL.

```python
name = "world"
print(f"hello, {name}")
```
Two lines run as one block. Variables you set stick around for the next
thing you type — try just typing `name` next and running it.

```python
import sys
sys.version
```
Confirms which interpreter you're actually running.

```python
for i in range(5):
    print(i, i * i)
```
Multi-line blocks work fine — the console isn't line-by-line, it's block-by-block.

**Try `input()` too:**
```python
age = input("How old are you? ")
print(f"In 10 years you'll be {int(age) + 10}")
```
The console box turns into an answer box — type a number and hit send.

**Try a crash on purpose:**
```python
1 / 0
```
You'll get a real traceback in red, and the console stays usable — one bad
line doesn't kill your session.

---

## 2. Editor — write a file, run it, see it in Files

Tap the **Editor** tab. There's a starter snippet already there. Tap ▶ to
run it — output shows up back in Console.

Now tap the **new file** icon, paste this in:

```python
import time

for second in range(5, 0, -1):
    print(f"{second}...")
    time.sleep(1)
print("Go!")
```

Tap **Save**, name it `countdown.py`, then tap ▶. Watch it count down in the
Console tab in real time — output streams in as it happens, it doesn't wait
for the whole script to finish.

---


**When a line gets long.** The editor scrolls sideways and follows the caret,
so the end of a long line is always reachable. If you would rather see the
whole thing at once, the ⋮ menu has **Wrap long lines** — the line numbers
stay right, each one growing as tall as its line now needs. **Go to line...**
is in the same menu.

The key strip above the keyboard changes with the file: `:` and `self` for
Python, `;` and `//` for Go, C, Rust and JavaScript, `<` and `>` for HTML and
Markdown. Enter indents the way that language does — after a `:` in Python,
after a `{` in the brace languages — and typing `}` steps back out a level.

## 3. Files — the examples that ship with the app

Tap **Files**. You'll see an `examples/` folder seeded on first launch.
Open it. Tap any `.py` file to load it in the Editor, or tap the ▶ next to a
file to run it straight from the list without opening it.

What's in there, and why:

| File | What it shows |
|---|---|
| `hello.py` | The basics — `print`, an `input()` prompt |
| `system_info.py` | Reads real device info back through Python |
| `text_adventure.py` | Several `input()` calls in a row |
| `quiz.py` | A scored quiz — more `input()`, with feedback per answer |
| `loop_forever.py` | Runs forever until you tap **Stop** — and a good Kill test as a script server |
| `todo_list.py` | Reads/writes a file in your workspace — run it twice, watch the list grow |
| `requests_demo.py` | Uses the network (needs Wi-Fi or data) |
| `rich_demo.py` | Colour and a table, rendered properly in the console |
| `http_server.py` | Serves a folder — see the Servers section below |
| `flask_api.py` | A JSON API running on the phone |

**Try creating your own.** Tap the new-file icon, call it `test.py`, paste in:

```python
import random

names = ["Ada", "Grace", "Alan", "Margaret"]
print(f"Random pick: {random.choice(names)}")
print(f"Dice roll: {random.randint(1, 6)}")
```

Run it a few times — different output each time confirms it's genuinely
executing on the device, not showing you canned text.

**Try importing a file.** Tap the import icon and pick any `.py` file from
your phone's downloads or storage — it copies into the workspace and shows
up in the list.

---

**The examples are yours to delete.** Deleting `examples/` sticks — the app
will not put it back on the next start. **More → System → Put the examples
back** restores them if you change your mind.

**Importing something that is already there** asks what you want rather than
guessing: *Replace* (the old one goes first, so nothing of it is left mixed in),
*Keep both*, or *Cancel*. It tells you how big the existing one is and when it
last changed, so the choice is an informed one.

## 3b. The console is a shell too

`pip install flask` works exactly as typed. So does most of what your fingers
already know:

```
pip install rich          pip list          pip show flask
ls          cd notes      pwd               cat app.py
head -20 log.txt          tree              find hello
mkdir src   touch a.py    cp a.py b.py      rm -r old
run app.py  serve . 8000  servers           stop all
open app.py preview page.html               go files
help        clear         version
```

`help` prints the lot. Everything that is not one of those commands is still
Python, and the rule for which is which is deliberately narrow:

- `ls` is a command; **`ls = [1, 2]` is an assignment**, and Python gets it.
- If you have defined a name yourself, your name wins - after `ls = [1, 2]`,
  typing `ls` prints your list.
- `import`, `def`, a call, a dot, an operator - all Python, always.

So nothing you could type in a REPL is swallowed, and the one command everybody
tries first finally works.

---

## 4. Packages — install something from PyPI, live

Tap **Packages**. `requests`, `flask` and `rich` are already built in (you
just used two of them above). Try installing something that *isn't*:

Type `tabulate` in the search box and tap **Install**. You'll see a short
progress message, then it lands in "Installed here". Go back to Console and
run:

```python
from tabulate import tabulate

data = [["Alice", 30], ["Bob", 25]]
print(tabulate(data, headers=["Name", "Age"]))
```

A real package, fetched from PyPI, installed on the device, imported and
used — needs the internet the first time you install it, works offline
after that.

**What won't work, and why:** try installing `numpy` or `pygame`. You'll get
a clear message instead of a silent failure — those ship compiled C code
that needs an Android-specific build, which nothing on PyPI provides. Pure
Python packages (the vast majority of PyPI) install fine.

---

## 5. Servers — serve something over your own Wi-Fi

Tap **Servers**. The form at the top is the whole thing:

1. Pick **Serve a folder** or **Run a file**.
2. Tap **Choose**. You land in Files with a banner. Tap any file to use it, or
   open a folder and tap **Use this folder** — both work in either mode.
3. Set the **port** — 8000 is fine. If it is taken, **Free one** finds the next
   one that isn't.
4. Optionally name it, and decide whether it is reachable on Wi-Fi or only on
   the phone itself.
5. Press **Run**.

Run stays greyed out until the form makes sense, and tells you what is missing
underneath.

**It runs more than Python.** The form says what pressing Run will do before it
does it:

| You pick | What happens |
|---|---|
| `.py` | Runs as a background script on its own thread |
| `.c`, `.go`, `.rs` | Runs on the interpreter built into the app |
| `.js` | Runs in the device's own JavaScript engine |
| `.html`, `.css`, `.md` | Serves the folder it sits in, opening on that page |
| a folder | Looks inside and runs its front door — see below |
| `.java`, `.cpp`, `.ts` | Refused up front, with the reason — no toolchain can run these here |

A running server has a **View** button that opens it in the preview, so you can
look at your own site without leaving the app.

### Pointing it at a whole project

A folder is a project, not a pile of files, so **Run a file** pointed at one
looks inside and takes the first of these it finds:

| In the folder | What Run does |
|---|---|
| `app.py`, `server.py`, `wsgi.py`, `manage.py`… that imports Flask, Django, FastAPI, `http.server`… | Runs it — that is the app |
| `index.html` | Serves the folder and opens that page |
| any of those entry names, even if it serves nothing | Runs it |
| exactly one runnable file | Runs that one |
| none of the above | Serves it as a file listing, and the page says what is missing |

The form says which of those it picked before you press Run, so a project that
is about to be served as a list of files tells you so first.

**Flask apps get the port you chose.** `app.run()` written on a laptop binds
`127.0.0.1:5000` and turns on the auto-reloader — on a phone that is a server
nothing can reach, restarting itself with a process launcher Android does not
have. PyCmd fills in the host and port from the form where the code left them
out, and turns the reloader off. If your code *does* name a port, that wins,
and the server card corrects itself to the port it really took.

**If you get a directory listing you did not want:** the page itself now says
why. The usual cause is pointing Run at the folder *inside* a Flask project —
the one holding `templates/` and `static/` — when the `app.py` that renders
those templates is the folder above. Point Run one level up.

**Type `http://`, not `https://`.** These servers are plain HTTP. Browsers
increasingly try HTTPS first for a bare address like `10.1.6.64:8000`, which
fails against a plain server; when that happens, PyCmd says so in the server's
console with the exact address to open.

You land straight in that server's own **console**. It shows what the server
printed, and with "Log each request" on you will see every hit as it happens:

```
Serving /data/.../workspace
Listening on http://192.168.1.42:8000/
192.168.1.58  "GET / HTTP/1.1" 200 -
```

Open that address from any other device on the same Wi-Fi and you will see your
workspace. Tap the copy icon in the console header to grab the URL.

The box at the bottom sends a line to the server's **stdin** — so a script that
calls `input()` is actually usable while it runs.

### Stop vs Kill

**Stop** asks the server to close and waits a few seconds. That is the normal
way to end one.

**Kill** is for when Stop cannot help — a script that hangs before it finishes
starting, or one that swallows interrupts. It closes the socket (freeing the
port even if the thread is stuck), forces the thread down, and stops tracking
it either way. Your port comes back regardless.

Try it: run `loop_forever.py` as a script server, then Kill it.

**Kill all** at the top of the list is the panic button, behind a confirmation.

Kill also works on a server that has frozen in its own `accept()` — it knocks
on the port to make the blocking call return, which is the only way an
exception can land inside one.

**Turn on Server Pro** (More → Plugins → *Ships with PyCmd*) and the Servers
tab grows a live board: whether each port really answers, restart, a free-port
finder, and the commands `servers`, `serve`, `restart`, `shut` and `ports`.

**Try the Flask example:** set **Run a script**, choose `flask_api.py`, set the
port to 5000, Run. Then visit `http://<your-phone-ip>:5000/` from another
device — a JSON API, served from your phone.

---

## 6. Other languages — Go, Rust, C and JavaScript

Files → **New file** → pick a language. Or paste one of these into the editor,
save it with the right extension, and press ▶.

`hello.go`

```go
package main

import "fmt"

func main() {
	ch := make(chan string, 1)
	go func() { ch <- "from a goroutine" }()
	fmt.Println(<-ch)

	squares := []int{}
	for i := 1; i <= 5; i++ {
		squares = append(squares, i*i)
	}
	fmt.Println(squares, len(squares))
}
```

`hello.rs`

```rust
use std::collections::HashMap;

fn main() {
    let mut counts: HashMap<&str, i32> = HashMap::new();
    for word in "a b a c a".split_whitespace() {
        *counts.entry(word).or_insert(0) += 1;
    }
    let mut keys: Vec<&str> = counts.keys().cloned().collect();
    keys.sort();
    for key in keys {
        print!("{}={} ", key, counts[key]);
    }
    println!();

    let squares: Vec<i32> = (1..=5).map(|n| n * n).collect();
    println!("{:?} sum={}", squares, squares.iter().sum::<i32>());
}
```

`hello.js`

```javascript
class Greeter {
  constructor(name) { this.name = name; }
  greet() { return `hello, ${this.name}`; }
}
console.log(new Greeter("phone").greet());
setTimeout(() => console.log("this still prints before the run ends"), 30);
```

None of these is compiled — Android has not let an app run code it generated
itself since Android 10. C, Go and Rust run on interpreters inside the app, and
JavaScript goes to the engine your phone already has. Each language's card in
**More → Guides** says what that costs: no type checking in Go, no borrow
checker in Rust.

---

## 7. Preview — HTML, CSS, Markdown, JSON, CSV, images

Make `page.html` in Files:

```html
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font: 16px system-ui; padding: 24px; background: #101820; color: #eee; }
    button { font: inherit; padding: 10px 18px; border-radius: 10px; }
  </style>
</head>
<body>
  <h1 id="title">Tap the button</h1>
  <button onclick="document.getElementById('title').textContent = 'It works ' + new Date().toLocaleTimeString()">
    Press me
  </button>
</body>
</html>
```

Press ▶ on it in Files. The button **works** — the page is served over a local
HTTP server rooted at its own folder, so scripts run, stylesheets load, and
`fetch` works. Anything the page logs or throws lands in the debug console.

The same button previews Markdown, a JSON file (validated and pretty-printed),
a CSV (as a table), an SVG or an image, and a `.js` file (which runs it and
shows what it logged).

**Music and video too.** Put an `.mp3` or an `.mp4` in the workspace - **Files
→ + → Music / Video** opens the phone's picker, since there is no such thing
as a starter template for a song - and tap it. It opens in a real player with
a seek bar you can drag: the preview server answers byte ranges, which is the
thing browsers insist on before they will let you scrub. Tapping media never
opens the editor, and neither does any other file that turns out to be bytes
rather than text; loading one into a text box is how a good file gets saved
back ruined.

Which formats actually play is the phone's business, not the app's - Android
decodes MP3, AAC/M4A, FLAC, Ogg and WAV, and MP4/WebM video, while MKV and MOV
depend on the device.

---

## 8. The plugins that ship with it

**More → Plugins**. Five sit under **Ships with PyCmd**, installed for you and
switched **off**:

* **Server Pro** — turns the Servers tab into a board you can work in.
* **Cloud** — Supabase and Firebase, from the console, a panel, or your own
  scripts.
* **Scheduler** — run a script again every so often.
* **Packages Pro** — JavaScript and CSS libraries, web fonts, and whole starter
  projects, fetched into your workspace.
* **Creator** — a tab of its own where code is built out of blocks. See
  [11e](#11e-creator--code-built-out-of-blocks).

Turn Cloud on, open **More → Cloud**, and connect a project. Then, from the
console:

```
sb select notes 5
fb get notes/today
```

or from a script — the same project, signed in as the same user:

```python
import pycmd_cloud

sb = pycmd_cloud.supabase()
for row in sb.table("notes").select("*").eq("done", False).limit(5).run():
    print(row["text"])
```

**Guides → The plugins that ship with it** lists everything both kinds can do.

---

## 9. Plugins you write yourself

Two examples are already in `examples/plugins`.

1. Scroll to **Install a plugin → From the workspace**.
2. Read the warning — a plugin is not sandboxed and runs with everything the
   app can do — and continue.
3. Pick `greet.py`. It appears under **Installed by you**, switched off.
4. Turn it on. Now type `greet Ada` in the console: a plugin command, not
   Python.
5. Install `hello-panel` the same way, turn it on, and press **Open**. That is
   a plugin's own screen, with its buttons calling its Python.

A plugin can also put a card of its own **inside** one of the app's screens —
that is how Server Pro reaches the Servers tab and Cloud reaches Files — and it
can publish a row in **More** with its own name, description and picture.
Neither needs the app to change.

**Plugins → How do I write one?** opens the full guide on the phone:
the manifest, the API, the events, the panel bridge, five complete plugins,
and a prompt you can paste into an AI to have one written for you.

---

## 10. When something goes wrong, it offers a fix

Make a file called `index2.html` in a folder, then a script next to it:

```python
with open("index.html") as handle:
    print(handle.read())
```

Run it. The console says:

```
[fix] index.html was not found, but index2.html is sitting next to it.
[fix] Rename index2.html to index.html?
[fix] Type yes to do it, no to leave it alone.
```

Type `no` and it says *OK — no fixing today* and leaves the error alone. Type
`yes` and it tells you what it is doing while it does it:

```
[fix] OK - renaming index2.html to index.html, so the code finds what it asks for.
[fix] Renamed index2.html to index.html. Start it again.
```

The same offers appear for a package that is not installed — where it says *OK
— downloading pygame from PyPI* and keeps talking while it downloads — a port
already in use, and a served folder with no index page. Nothing changes without
a yes, and answering never blocks the app: the work happens on its own thread,
so Stop and Kill keep working throughout.

---

## 11. Debug console — when something breaks

Tap the **bug icon** in the top bar, from any tab. This is not your script's
output — it is everything around it: interpreter startup, server lifecycles,
package installs, file errors, JavaScript errors inside the editor, and any
crash.

- The chips filter by level. Tap **Error** to see only what actually failed.
- The box above searches text and tags.
- Tap an entry with "tap for detail" to expand its stack trace.
- The icons copy the whole log, save it into your workspace as a `.log` file,
  or clear it.

A red badge on the bug icon is the number of errors waiting. On a healthy
start-up it should read three entries and no errors.

If you hit a bug worth reporting, save the log and send that — it is far more
useful than a description.

---

## 11b. Packages Pro — libraries that are not Python

**More → Plugins**, switch on **Packages Pro**. Then, in the console:

```
web install htmx
web catalogue
kit new blog flask
```

`web install` fetches a library's real file into `vendor/` in your workspace
and prints the tag to paste into a page. That matters more here than on a
laptop: the preview is a loopback server, so a page that relies on a CDN only
works while you have a connection, and a vendored one always works.

`kit new <folder> <kind>` makes a whole project rather than a file - `flask`,
`site`, `htmx`, `chart`, `three`, `api`, `cli` - and since the Servers tab
knows how to run a folder, `kit new blog flask` is runnable the moment it
exists. There is a panel for all of it under **Packages**.

---

## 11c. Pages — a website that lives in the app

**More → Pages.** A page is a folder you already have: press **Choose a
folder**, pick one out of the workspace, give it a name, press **Add page**.
The picker lists every folder in the workspace and one level inside each, says
how much is in it, and greys out the ones that are already pages.

Nothing to point at yet? Open **Nothing to point at yet?** underneath and start
one from a template:

| Starts as | What you get |
|---|---|
| A page | `index.html`, `style.css`, `app.js` |
| A Python site | `app.py` with Flask, `templates/`, `static/` |
| A JSON API | `app.py` answering `/api`, and a page that calls it |
| Empty | a folder, and whatever you put in it |

The folder lands at the **top of the workspace under its own name**. Earlier
versions put it in a `pages/` folder the app invented, which is a name sitting
in the way of `vendor/` from Packages Pro, whatever pip installed, and your own
folders. Files can move it wherever you like afterwards; the page follows it by
path.

Then **Run**. It is a real server: the card shows an address like
`http://192.168.1.42:8631/`, and anyone on the same wifi can open it in a
browser. **Stop** takes it down, **Rename** and **Delete** do what they say, and
**Files** opens its folder so you can edit it in the editor like anything else.

You can keep **70 pages** and run **25 at once**. Both numbers are on the card,
and both are refusals rather than surprises: past them it says so instead of
slowing your phone to a crawl.

Anything the app can run, a page can be. With the built-in kit on, that is
Python, HTML, CSS, JavaScript, C, Go, Rust and the rest - a page is just a
folder, and the Servers tab's rules decide what running it means: an `app.py`
that imports Flask is started, an `index.html` is served, a single runnable
file is run.

### Share — an address anyone can open

**Share** on a running page asks a free tunnel service for a public address and
puts it in front of your page. Anyone, on any network, anywhere, can open it.

Three honest caveats, which the app also states:

- **The address is random and temporary.** A new one every time.
- **It only works while PyCmd is running.** Close the app and it stops.
- **It is not private.** Anyone with the URL is on your page.

### Cloudflare — a real address that stays up

With the **full kit** on (More → Plugins → Polyglot Files, Polyglot Runner and
Power Pack), the Pages tab grows a Cloudflare section. Connect an account and a
page can be deployed to **Cloudflare Pages** instead of served from the phone:
a `pages.dev` address, up when your phone is off, and it takes your own domain.

You need two things from Cloudflare's dashboard: your **account ID**, and an
**API token** with *Cloudflare Pages: Edit* (add *Workers Scripts: Edit* if you
want to publish Workers). Use a scoped token rather than the Global API Key -
a token can be revoked on its own, and a phone is a thing that gets lost. The
token is checked before it is kept, lives in the app's private storage, never
goes in your workspace, and is never shown back to you.

Once connected, each page card gets **This phone / Cloudflare** and a **Deploy**
button.

**What went up is kept, and it is not in your workspace.** Deploying packs the
folder into a copy first - skipping `__pycache__`, `.git`, `node_modules` and
hidden files - and uploads that. The copy, and the record of where and when
each deployment went, live in the page's own storage inside the app, one folder
per page. So "what did I actually send" has an answer afterwards, and your
workspace never grows a build folder you did not put there. **Clear** on the
card throws the copy away and keeps the history.

---

## 11d. Music — something to listen to while you work

**More → Music.** Press **Add music** and pick anything on the phone: MP3,
M4A, FLAC, OGG, WAV, and video files too. Everything is copied into the app, so
the library works with no signal, no account and no permission to read the rest
of your storage.

A video file is taken for its sound. `.mp4`, `.mkv`, `.webm` - the audio plays
and the picture is never decoded. It is a music player, not a video player.

| What | Where |
|---|---|
| Play a track | Tap it, or its play button |
| Play everything | **Play all**, top right of the library card |
| Loop and shuffle | The two outer buttons under the controls |
| Rename, delete, add to a playlist | The chevron on the right of a track |
| Make a playlist | **New playlist**, then add tracks from their chevron |
| Reorder a playlist | Open it, then the up and down arrows on a track |

Loop has three states, not two: **off**, **all** (the queue repeats) and **one**
(this track repeats). The icon changes; so does its description.

### It keeps playing

Switch to the Console and write code - it keeps playing. Press the home button
- it keeps playing. Lock the phone - it keeps playing, and the lock screen has
the controls. Pull down the shade and the quick-settings media chip is there
with play, pause, previous and next. None of that is drawn by PyCmd: the player
lives in a media session in a service, and Android draws the rest.

Two things follow from that, both worth knowing:

- **Stopping means stopping.** Pausing leaves the notification up so you can
  start again. **Stop** clears the queue, and the notification goes with it.
- **A call wins.** Playback pauses for a phone call or a navigation prompt and
  comes back afterwards, and unplugging headphones pauses rather than playing
  it out loud to the room.

Deleting a track deletes the copy inside PyCmd. Whatever you imported it from
is untouched. The library is not in the workspace and is not part of the backup
PyCmd takes, so a workspace export never carries somebody's album. If a file
goes missing another way - a delete that half worked, storage cleared under the
app - the row says so, and **Tidy up** clears those rows and any stray files
nothing points at.

---

## 11e. Creator — code built out of blocks

**More → Plugins → Creator** to switch it on, then **More → Creator**.

Every row in your script is **the line that block writes** - real code, from
the same compiler that writes the file - with the block's plain-English name
underneath. The palette shows the same thing: what each block would write,
filled in, rather than a template full of holes.

**+ Add a block** opens the block picker - a screen of its own, with the search
and the categories at the top - and it stays open while you tap, so several
blocks can go on in a row. Tap a block in your script to select it, and a row
of buttons appears: Fill in, Up, Down, Move inside, Move out, Duplicate,
Delete. Select a container - a loop, an `if`, a `<div>`, a CSS rule - and the
next block you pick goes *inside* it. That is the whole trick to building a
loop, and both the picker and the line beside "Your script" always say where
the next block will land.

Switching language does not throw anything away: Creator keeps one script per
language, so the chooser moves between ten drafts. Each has an **Example** you
can load and press Run on.

Nine hundred and four blocks, in ten languages. The six marked *runs here*
have an engine in the app, so a program built out of blocks can be saved and
then run on the phone:

| Language | Blocks | | Some of what is in there |
|---|---|---|---|
| Python | 202 | runs here | print, input, loops, sets, comprehensions, dates, files, JSON, Flask, classes |
| Go | 108 | runs here | slices, maps, structs, errors, goroutines and channels |
| Rust | 102 | runs here | Vec, HashMap, Option, Result, structs, enums, iterators |
| C | 100 | runs here | arrays, grids, structs, pointers, malloc, string.h, math.h |
| JavaScript | 138 | runs here | the page, events, fetch, promises, classes, storage, timers |
| Shell | 67 | runs here | POSIX sh, which is what Android gives you |
| HTML | 70 | | the whole document, forms, tables, media |
| CSS | 68 | | rules, flex, grid, custom properties, animation, screen sizes |
| Markdown | 29 | | headings, lists, tables, checklists, footnotes |
| JSON | 20 | | objects, lists, and the commas put in for you |

**See the code** shows the whole file, before anything is saved. **Save as a
file** asks for a name and a folder and writes a real file into the
workspace - and then it is an ordinary file: the editor opens it, `run
thing.py` runs it, a folder of them is a page the Pages tab can serve.

Your projects are kept apart from the files they make, in a drawer of up to
sixty. Saving a file does not clear the blocks, and editing the file afterwards
does not change them.

From the console: `blocks`, `blocks langs`, `blocks build <name>`,
`blocks save <name>`.

Two honest limits. It cannot read a file back into blocks - blocks go one way.
And it does not check what you type into a hole: `score +` is written into the
file exactly like that, and Python complains when you run it. What the blocks
get right is the *shape* - the colons, the braces, the indentation, the closing
tags - which is the part that is miserable on a phone keyboard.

---

## 11f. Using what you installed, everywhere

Two tabs install things, and they land in two different places for two
different reasons. Both are reachable from everywhere in the app; the how is
different.

### Python packages: install once, import anywhere

**Packages → install**, or `pip install requests` in the console. It goes into
the app's own `site-packages`, which is on the path of the **one interpreter**
everything here shares. So after installing it once:

```python
import requests            # in the console
import requests            # in a file you Run from the editor
import requests            # in a server, in the Servers tab
import requests            # in a page's app.py, in the Pages tab
import requests            # in a plugin you wrote
```

All the same interpreter, all the same packages. Nothing to add to a path,
nothing to activate, no virtualenv. `pip list` in the console says what is
there, and Flask, requests and rich are already in the box.

The one rule: **install before you run**, not while. A server already running
loaded its imports when it started.

### Web libraries: they go in the project

`web install htmx` (Packages Pro) fetches into `vendor/` at the top of your
workspace, which is the right place to keep them - but a page is served rooted
at **its own folder**, so `../vendor/htmx/htmx.min.js` is a path the browser
cannot follow. Copy it into the project instead:

```
web use htmx blog
```

That puts it in `blog/vendor/htmx/` and prints the tag to paste. Now
`<script src="vendor/htmx/htmx.min.js"></script>` works in `blog/index.html`,
offline, served from the phone, and deployed to Cloudflare unchanged - because
it is inside the folder that gets uploaded.

`kit new blog flask` does the same thing from the other end: a project folder
that already runs, with what it needs already inside it.

### Where each of them lives

| What | Where it lands | How you reach it |
|---|---|---|
| `pip install X` | the app's `site-packages` | `import X`, anywhere |
| `web install X` | `vendor/X/` in the workspace | `web use X <folder>`, then a relative tag |
| `kit new X` | a folder in the workspace | point Servers or Pages at it |
| Creator's **Save** | the folder you pick | like any file you wrote |

---

## 12. Updating without losing anything

**More → System → Updates → Check for updates.**

If there is a newer build, the card says which version and how big the download
is. Press **Download** and PyCmd fetches the APK, checks it against the
fingerprint published beside it, checks it is signed with the same key as the
build you are running, and only then offers **Install**. Android puts up its own
confirmation, PyCmd closes for a moment, and it comes back updated.

Nothing is deleted. The workspace, the packages you installed with pip, your
plugins and every setting are still there, because Android replaced the app
rather than removing it. **Deleting PyCmd first is the thing that loses all of
that** - so when a new version turns up, install it over the old one and never
uninstall to make room.

The first time, Android will ask whether PyCmd may install apps. That switch is
per-app and you can turn it back off afterwards.

You do not have to remember to check. Once a day, while the app is running, it
reads that one small file by itself and - if something newer is out - puts a dot
on **More** and a line on the System card. It downloads nothing until you press
Download, installs nothing until you press Install, and a check that fails
because the phone is offline says nothing at all.

**The versions you have had are kept.** Every update PyCmd downloads is filed
away on external storage instead of being deleted - up to a ceiling you set
(250 MB, 500 MB, 1 GB, 2 GB, or off entirely), oldest pruned first. Each one can
be reinstalled, saved out to the phone, or deleted.

Going *back* to an older build is the one thing Android will not do in place:
it refuses to install a lower version over a higher one, and no app can override
that. So the card does not pretend. It lays out the sequence that does work -
save the old APK to the phone, back up the workspace (it writes the zip for
you), uninstall, install the saved APK, bring the workspace back - and the
backup step is the one that makes it safe, because uninstalling deletes
everything the app owns.

**It can look while the app is closed.** Two switches under the update card:
one asks Android to check about once a day, and one lets it download the APK
too. Both are off until you turn them on, and neither ever installs anything -
Android would ask you anyway. What Android decides, and this cannot: exactly
when the check runs (roughly daily, on wifi, when the battery is not low), and
whether it runs at all after a force-stop, which cancels scheduled work until
the app is opened again.

Running pages and servers keep going with the app closed for a different
reason: they are held up by the foreground service, the one that shows the
"running servers" notification. That notification is not decoration - it is the
thing keeping them alive.

**Where updates come from** at the bottom of the card takes an https address of
a `latest.json` - a fork, another branch, or a machine of your own. Whatever it
points at, the fingerprint check still runs, and a build signed with a different
key is refused with an explanation rather than a failed install.

---

## 13. Forking it, and telling us when it breaks

**More → Guides → Forking PyCmd** is the walkthrough: what the code is made of,
how to build it, what not to change, and how to publish updates for a fork of
your own - the update address in System is editable precisely so a fork can
serve its own `latest.json`. **Download the source** pulls the whole repository
onto the phone as a zip - the button is at the end of the fork guide itself,
and again at the bottom of the Guides screen.

Forks are welcome. Keep PyCmd's name and credit where they are, and do not
present the original as a copy of your fork. Beyond that, change what you like.

And when something is wrong - a crash, a wrong answer, a thing that should
exist - **More → System** has the address: `andrejbaltes4@proton.me`. Save the
debug log first if something failed; it is worth more than a description.

---

## Things worth specifically checking

- **Stop actually stops.** Run `loop_forever.py`, watch a few ticks print,
  tap Stop. It should return to "ready" within well under a second, not hang.
- **The app survives a crash in your code.** Run something that errors
  (`1/0`, a typo, whatever) — the console shows the error and stays usable
  for the next thing you run.
- **Namespace reset.** Set a variable in Console, then tap the reset icon
  (top bar) — the variable should be gone if you try to use it again.
- **Rotate the phone / switch tabs mid-run.** Output shouldn't be lost, and
  a running script shouldn't stop just because you looked at another tab.
- **An update keeps your files.** After installing a newer build over this
  one, Files should look exactly as you left it - same folders, same scripts,
  same installed packages.
- **`pip install` works from the console.** Type `pip install tabulate`, then
  `import tabulate` on the next line. No `os.system`, no restart.
- **A command never eats your Python.** Type `ls = [1, 2]`, press Run, then
  type `ls` - you should get your list back, not a directory listing.
- **Blocks build something that runs.** In Creator, stack a loop with a print
  inside it, press Build, then Save. Run the file it wrote - it should do what
  the blocks said, with no editing.
- **A page points where you pointed it.** Add a page from a folder you made in
  Files, run it, and open the address. Nothing should appear in your workspace
  that you did not put there - no `pages/` folder, and no build folder after a
  deploy.

---

## If something looks wrong

This build has over 700 automated checks behind it against the Python engine
and the JavaScript console/editor (see `tools/` in the repo), and an earlier
build was installed and driven on an Android 11 emulator: the app launches,
Python 3.13.9 starts, and pressing Run in the editor prints its output to the
console. This one has not been on an emulator - the machine it was built on
has no hardware virtualisation to run one.

What has *not* been verified on a device is most of what this page asks you
to try — installing a package, serving a folder over Wi-Fi, the Stop button,
`input()` prompts, and the background-server notification all work against
host CPython in the test suite but have not been tapped through on real
hardware. So if something here doesn't behave as described, that is worth
reporting rather than assuming you did it wrong: say what you ran, which
tab, and what happened instead.
