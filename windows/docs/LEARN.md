# PyCmd Learn

Fifty languages and 14,700 lessons, on the same engine as the phone's
PyCmdTeach - so the lessons are the same lessons, and the Windows build adds
what only a PC can do.

## What is in it

**The phone's 28 courses** - Python, JavaScript, Rust, Go, C, C++, Java,
Kotlin, Swift, TypeScript, Ruby, PHP, Lua, shell, SQL, regular expressions and
the formats (HTML, CSS, JSON, YAML, TOML, XML, CSV, Markdown, Dockerfiles,
Makefiles, .gitignore, INI).

**Twenty-two more that need a PC to run**: C#, F#, Haskell, OCaml, Scheme,
Racket, Clojure, Elixir, Erlang, Scala, Groovy, R, AWK, Prolog, Fortran,
Pascal, COBOL, D, Nim, Perl, Tcl and PowerShell.

Every topic makes up to seven lessons:

| Kind | What you do |
|---|---|
| Read | Read the idea and the code - and run it, change it, run it again |
| Predict | Say what the code prints |
| Which prints it | Pick the one snippet of four that prints a given output |
| Fill the gap | Choose the word that belongs in the blank |
| Find the bug | Click the line with the mistake |
| Put in order | Click the lines in the order they run |
| Write it | Write a program that prints the answer |

## Marked by running it

On the phone, a written answer in most languages can only be compared with the
model answer as text. On a PC, if the language is installed, PyCmd **builds
and runs your answer** and marks it by what it prints. So
`main = putStrLn ("hel" ++ "lo")` is a right answer to "print hello" in
Haskell, even though the lesson's own answer is `putStrLn "hello"` - which is
the only kind of marking that does not punish a correct answer written
differently.

Courses marked **runs here** are marked that way on this machine. Anything
else is compared with the model answer, ignoring spaces and quote style, and
the lesson says which it is doing. The Toolchains tab installs most languages
in one click.

Kotlin and Swift are taught by reading and writing only: their lessons have
never been run on a real compiler, and a correct answer must never be marked
wrong by a fragment that cannot run on its own.

Every run has a time limit and an output limit, so `while True` gets you the
tab back. Runs use the invariant culture - on a German or French Windows,
C# would otherwise print 3.5 as `3,5` and mark a right answer wrong.

## Getting around

- **Continue** picks up at the lesson after the last one you opened.
- **Review** walks through every lesson you got wrong and have not put right.
- **Search** finds a topic in every course at once.
- **Daily goal** and **streak**, as on the phone.
- **Open in the editor** puts the lesson's real snippet in a file in
  `workspace\learn`, to play with properly.

Keys in a lesson: **1-9** pick a choice, **Enter** checks or moves on,
**Ctrl+Enter** checks written code, **Esc** goes back to the course.

## How the lessons are checked

`tools/test_learn.py` runs every snippet that says what it prints through the
same runner the app uses, with the real toolchain, and fails if the output
differs - 1,800 snippets across the PC courses, plus the phone courses that
can run here. It also checks every lesson opens, every ordering and bug
lesson can be answered, and nothing is too wide to read.
