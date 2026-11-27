# Creator 3.0

Build real code out of blocks, run it, and keep it as a file. Over nine hundred
blocks across ten languages, and every block shows the exact line it writes, so
what is on screen is the code.

## The three panes

- **Blocks** (left): search with `/`, or pick a category. Click a block to add
  it after the selected one, or inside it if it holds blocks. Drag it into the
  script to put it exactly where you want.
- **Script** (middle): type straight into the coloured fields. Select a block
  for its arrows, duplicate and delete buttons. `⇥` puts it inside the block
  above, `⇤` takes it back out.
- **Code / Run** (right): the file the blocks write, with the line of the
  selected block lit up. Click a line to jump to its block.

On a phone the panes become tabs along the bottom.

## Running

| Language | Runs |
|---|---|
| Python | on PyCmd's own Python, right in the tab |
| C, Go, Rust | on the interpreters PyCmd carries |
| JavaScript | in the panel |
| HTML, CSS, Markdown | as a live preview |
| JSON | checked and pretty-printed |
| Shell | save it, then run it in the console |

Programs that ask for input read it from the **Input** box, one line for each
`input()` or `prompt()`. A run that goes on too long is stopped (10 seconds by
default, change it in Settings). When a program fails, its line turns red and
the block that wrote it is selected.

## Import code

Paste code, or pick a file from your workspace, and it comes back as blocks. A
line one of the blocks writes becomes that block with its values filled in, and
the round trip is checked, so nothing changes meaning. Anything else becomes an
**any line of code** block, so nothing is lost.

## Keys

| Key | Does |
|---|---|
| Ctrl+Enter | Run |
| Ctrl+S | Save as a file |
| Ctrl+Z / Ctrl+Y | Undo / redo |
| Ctrl+D | Duplicate the selected block |
| Delete | Delete it |
| Alt+↑ / Alt+↓ | Move it |
| Tab / Shift+Tab | Into the block above / back out |
| / | Search blocks |

## Projects

Every script saves itself as you work, and each language keeps its own. Projects
lists them all. **Save file** writes a real file into your workspace, where the
editor opens it and the console runs it.

The console command `blocks list | langs | build <name> | save <name>` works on
saved projects too.
