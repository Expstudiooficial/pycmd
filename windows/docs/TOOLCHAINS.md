# Compilers and languages

The screen that makes the Windows build worth having, and the reasoning behind
it.

## Why this exists

On Android, an app may not execute code it generated itself. That has been
true since API 29 and it is not a setting - `mprotect` with `PROT_EXEC` is
refused, and a library the app wrote cannot be loaded. So the phone build of
PyCmd does the only honest thing available: it carries *interpreters* for C,
Go and Rust, written in Python, and labels C++, Java, Kotlin and the rest
"editable and servable, but not runnable here".

Windows has no such rule. So PyCmd finds what you have installed and calls it.

**65 file types. 43 of them run.
52 toolchains it knows, 17 of them installable in one click.**

## What happens when you press Run

1. PyCmd works out what the file is, from its extension.
2. It looks for a toolchain that runs that language, best first.
3. If it finds one, it builds if building is needed, then runs, and streams
   the output to the Console.
4. If it finds none **and PyCmd carries an interpreter for that language** -
   C, Go, Rust and JavaScript - it uses that instead, and says so.
5. If it finds none and carries none, it says which toolchains would work and
   how to install each of them.

The console always names what ran the file:

```
[PyCmd] Go via Go 1.24.7
hello
```

or

```
[PyCmd] no Go toolchain found - running on the interpreter built into PyCmd
hello
```

That line is not decoration. The built-in Go interpreter parses types without
enforcing them, and the built-in Rust one has no borrow checker - so a program
that runs on the interpreter may still be rejected by the real compiler.
Knowing which one you just used is the difference between "it works" and "it
works here".

## Installing one

Press **Install**. For seventeen of them - Node.js, Go, Java, Zig, Deno, Bun,
.NET, Rust, Kotlin, PowerShell 7, GCC, Git (with bash), Dart, Nim, Perl, PHP
and TypeScript - that downloads the vendor's own Windows build and nothing
else:

1. PyCmd asks the vendor which version is current - nodejs.org's release
   index, go.dev's, the Adoptium API, the Zig index, GitHub releases - rather
   than carrying a version number that is out of date by next month.
2. It downloads the archive, with progress on the Console.
3. It checks the file against the hash **the vendor publishes**. A file that
   does not match is deleted, not used.
4. It unpacks it into `%LOCALAPPDATA%\PyCmd\toolchains\<name>` - into a
   scratch folder first, so a half-unpacked toolchain is never left behind,
   and refusing any archive entry that tries to write outside its folder.
5. It puts the toolchain's `bin` folder on PyCmd's own PATH. Nothing is
   written to the registry or to the system PATH, so uninstalling is
   **Remove**, which deletes that one folder.

No administrator. No package manager. Rust comes as the **GNU** toolchain,
which links with its own linker - the usual MSVC one needs Visual Studio's
`link.exe`, and without it every Rust program fails to build. Kotlin brings
the JDK it needs with it.

### With a package manager instead

Every card also lists its `winget`, `scoop` and `choco` lines under **Or with
a package manager**, with a button that runs each. Since 4.0 those work too,
which they often did not before:

- **scoop is run by its full path.** It is a `.cmd` shim, and Windows only
  finds `.exe` files by bare name - so `scoop install` used to fail with
  "scoop is not there" on every machine that had scoop.
- **scoop's buckets are added when a package needs one**, and git is
  installed first, because adding a bucket is a git clone. `extras/swipl` and
  `java/temurin21-jdk` name their bucket.
- **scoop installs as administrator** when PyCmd is running elevated, which
  its installer otherwise refuses.
- **The installer's output is on the Console.** It used to go to a channel no
  screen showed, so every install looked like it did nothing.

## Everything PyCmd knows how to drive

`builds` means it compiles first and then runs what it built; `direct` means
it runs the source.

| Toolchain | Languages | How | Install |
|---|---|---|---|
| Python | python | direct | `winget install Python.Python.3.13` |
| Node.js | javascript | direct | `winget install OpenJS.NodeJS.LTS` |
| Deno | javascript, typescript | direct | `winget install DenoLand.Deno` |
| Bun | javascript, typescript | direct | `scoop install bun` |
| TypeScript compiler | typescript | builds | [site](https://www.typescriptlang.org/) |
| Ruby | ruby | direct | `winget install RubyInstallerTeam.Ruby.3.3` |
| PHP | php | direct | `winget install PHP.PHP.8.3` |
| Perl | perl | direct | `winget install StrawberryPerl.StrawberryPerl` |
| Lua | lua | direct | `scoop install lua` |
| R | r | direct | `winget install RProject.R` |
| Julia | julia | direct | `winget install Julialang.Julia` |
| PowerShell | powershell | direct | [site](https://learn.microsoft.com/powershell/) |
| PowerShell 7 | powershell | direct | `winget install Microsoft.PowerShell` |
| Bash | shell | direct | `winget install Git.Git` |
| Command Prompt | batch | direct | ships with Windows |
| SQLite | sql | direct | `winget install SQLite.SQLite` |
| Tcl | tcl | direct | `scoop install tcl` |
| AWK | awk | direct | `scoop install gawk` |
| SWI-Prolog | prolog | direct | `winget install SWI-Prolog.SWI-Prolog` |
| Groovy | groovy | direct | `scoop install groovy` |
| GCC | c | builds | `winget install BrechtSanders.WinLibs.POSIX.UCRT` |
| G++ | cpp | builds | `winget install BrechtSanders.WinLibs.POSIX.UCRT` |
| Clang | c | builds | `winget install LLVM.LLVM` |
| Clang++ | cpp | builds | `winget install LLVM.LLVM` |
| MSVC | c, cpp | builds | `winget install Microsoft.VisualStudio.2022.BuildTools` |
| Clang (Objective-C) | objectivec | builds | `winget install LLVM.LLVM` |
| Go | go | direct | `winget install GoLang.Go` |
| Rust | rust | builds | `winget install Rustlang.Rustup` |
| Zig | zig | direct | `winget install zig.zig` |
| Nim | nim | direct | `scoop install nim` |
| Crystal | crystal | direct | `scoop install crystal` |
| Dart | dart | direct | `winget install Google.DartSDK` |
| V | vlang | direct | `scoop install vlang` |
| D | d | builds | `scoop install dmd` |
| Java | java | direct | `winget install EclipseAdoptium.Temurin.21.JDK` |
| Kotlin | kotlin | builds | `scoop install kotlin` |
| Scala | scala | direct | `scoop install scala` |
| Clojure | clojure | direct | `scoop install clojure` |
| .NET SDK | csharp, fsharp, visualbasic | direct | `winget install Microsoft.DotNet.SDK.8` |
| F# Interactive | fsharp | direct | `winget install Microsoft.DotNet.SDK.8` |
| Haskell | haskell | direct | `winget install Haskell.GHCup` |
| OCaml | ocaml | direct | [site](https://ocaml.org/install) |
| Racket | racket | direct | `winget install Racket.Racket` |
| Elixir | elixir | direct | `scoop install elixir` |
| Erlang | erlang | direct | `choco install erlang` |
| Scheme (Guile) | scheme | direct | [site](https://www.gnu.org/software/guile/) |
| Fortran | fortran | builds | `winget install BrechtSanders.WinLibs.POSIX.UCRT` |
| GnuCOBOL | cobol | builds | [site](https://gnucobol.sourceforge.io/) |
| Free Pascal | pascal | builds | `scoop install freepascal` |
| NASM | assembly | builds | `scoop install nasm` |
| Swift | swift | builds | `winget install Swift.Toolchain` |

## The ones worth a word

**MSVC** only appears on the PATH inside a Developer Command Prompt, so PyCmd
usually will not see it unless you started PyCmd from one. GCC through
MinGW-w64 is the easier route on Windows and is what most people have.

**Kotlin** is slow, and not because of PyCmd: `kotlinc` starts a JVM to
compile, then `java` starts another to run. Thirty seconds for a first build
is normal.

**C#, Visual Basic and F#** want a project around a loose file. PyCmd writes a
minimal `.csproj`, `.vbproj` or `.fsproj` beside your file the first time you
press Run, rather than showing you an MSBuild error. The F# one names your file
explicitly, because F# compiles in source order and does not glob.

**`.fsx` is a script, `.fs` is not.** The .NET SDK builds projects, so it has
nothing to say about a script; a `.fsx` goes to F# Interactive and runs with no
project at all, and PyCmd leaves none behind. Press Run on either and the right
one happens.

**NASM** assembles to a `.obj` and stops. Linking that into something runnable
is a choice of linker, and picking one for you would be guessing.

**Bash** is not Windows'. Git for Windows brings one and so does WSL; with
either installed, `.sh` files run.

**Objective-C** builds its C parts under Clang. Foundation is Apple's and is
not here, so anything using it will not link.

## Adding one yourself

`windows/pycmd_win/toolchains.py` is a list of `Toolchain` objects and nothing
else. One entry is: the program to look for, how to ask its version, the
argument list to build and run with, and the install lines. Add an entry and
`tools/test_toolchains_live.py` will compile and run a hello-world with it on
any machine that has it.
