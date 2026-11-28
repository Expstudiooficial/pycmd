#!/usr/bin/env python3
"""PyCmd, the app's own language: what it prints, what it refuses, and what it
cannot reach. Every program here goes through the same call the Run button
makes (pcmd.run_source), so this is the language as people get it."""

import io
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "app", "src", "main", "python")))

from pycmd_langs import pcmd, pcmd_engine, registry  # noqa: E402

ENGINE = "fast (Kotlin)" if pcmd._engine() else "first (Python)"
print(f"engine: {ENGINE}")
from pycmd_langs.pcmd_runtime import LIBRARIES  # noqa: E402

FAILED = []
PASSED = [0]


def check(name, ok, detail=""):
    if ok:
        PASSED[0] += 1
        print(f"  PASS  {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL  {name}  {detail}")


def run(src, stdin=""):
    out = io.StringIO()
    try:
        code = pcmd.run(src, stdout=out, stdin=io.StringIO(stdin))
        return out.getvalue(), None, code
    except pcmd.PcmdError as exc:
        return out.getvalue(), exc.message, None


def prints(name, src, expected, stdin=""):
    got, err, _ = run(src, stdin)
    check(name, err is None and got == expected, f"error={err!r} got={got!r}")


def refuses(name, src, words):
    got, err, _ = run(src)
    check(name, err is not None and all(w in err for w in words), f"error={err!r}")


print("== values and printing ==")
prints("hello", 'print("Hello, PyCmd!")', "Hello, PyCmd!\n")
prints("values print the PyCmd way", 'print(true, nil, 2.0, [1, "a"], {"k": 1}, (1,))',
       'true nil 2.0 [1, "a"] {"k": 1} (1,)\n')
prints("interpolation and format specs", 'let x = 3.14159\nprint("{x:.2f} {7:03} {1 + 1}")',
       "3.14 007 2\n")
prints("single quotes are plain", "print('{x}')", "{x}\n")
prints("big integers", "print(2 ** 100)", "1267650600228229401496703205376\n")
prints("division", "print(7 / 2, 7 // 2, -7 % 3)", "3.5 3 2\n")

print("== control flow ==")
prints("if / elif / else", 'let t = 15\nif t > 25 { print("hot") } elif t > 10 { print("mild") }'
       ' else { print("cold") }', "mild\n")
prints("ranges", "print(list(0..3), list(1..=3))", "[0, 1, 2] [1, 2, 3]\n")
prints("loop, break, continue", "var i = 0\nloop {\n i += 1\n if i == 2 { continue }\n"
       " if i > 3 { break }\n print(i)\n}", "1\n3\n")
prints("for k, v over a map", 'for k, v in {"a": 1} { print(k, v) }', "a 1\n")
prints("ternary and ??", 'let n = nil\nprint(n ?? 5, 3 > 2 ? "y" : "n")', "5 y\n")

print("== functions ==")
prints("implicit return", "fn sq(n) { n * n }\nprint(sq(9))", "81\n")
prints("defaults, named and rest", 'fn f(a, b = 2, ...r) => "{a}{b}{r.len()}"\n'
       'print(f(1), f(1, b: 5), f(1, 2, 3, 4))', "120 150 122\n")
prints("closures change their own var", "fn c() {\n var n = 0\n return fn() {\n n += 1\n"
       " return n\n }\n}\nlet k = c()\nk()\nprint(k())", "2\n")
prints("functions are hoisted", "print(f())\nfn f() => 1", "1\n")
prints("lambdas and pipelines", "print([3, 1, 2].filter(|x| x > 1).map(fn(x) => x * 10)"
       " |> sorted)", "[20, 30]\n")
prints("recursion", "fn fib(n: int) -> int { n < 2 ? n : fib(n - 1) + fib(n - 2) }\n"
       "print(fib(20))", "6765\n")

print("== data ==")
prints("list methods", "let xs = [3, 1, 2]\nxs.push(4)\nprint(xs.sorted(), xs.sum(), xs.max(),"
       " xs[-1], xs[1:3])", "[1, 2, 3, 4] 10 4 4 [1, 2]\n")
prints("comprehensions", "print([x * x for x in 0..5 if x % 2 == 0], {n: n for n in 1..=2})",
       "[0, 4, 16] {1: 1, 2: 2}\n")
prints("destructuring", "let [a, ...rest] = [1, 2, 3]\nlet x, y = (4, 5)\nprint(a, rest, x + y)",
       "1 [2, 3] 9\n")
prints("swap", "var a = 1\nvar b = 2\na, b = b, a\nprint(a, b)", "2 1\n")
prints("maps", 'let m = {name: "x"}\nm["n"] = 1\nprint(m, m.get("z", 0), m.has("n"))',
       '{"name": "x", "n": 1} 0 true\n')
prints("sets", "print(set([2, 1, 2]))", "set[1, 2]\n")

print("== structs, enums, match ==")
prints("structs, defaults, methods, statics",
       "struct P {\n x: int\n y: int = 0\n fn d(self) => self.x + self.y\n"
       " fn origin() => P(0)\n}\nprint(P(3, 4), P(x: 1).d(), P.origin())",
       "P(x: 3, y: 4) 1 P(x: 0, y: 0)\n")
prints("extends and is", 'struct A {\n n: str\n fn hi(self) => "hi {self.n}"\n}\n'
       'struct B extends A {\n k: int = 1\n}\nlet b = B("z")\nprint(b.hi(), b is A, b is B, 1 is A)',
       "hi z true true false\n")
prints("enums", "enum C { R, G = 5 }\nprint(C.R, C.G.value, C.all(), C.from_value(5))",
       "C.R 5 [C.R, C.G] C.G\n")
prints("match patterns", 'fn k(v) => match v {\n 0 => "zero"\n 1..=9 => "small"\n'
       ' [a, ...r] => "list {a}"\n is str => "text"\n x if x > 99 => "big"\n _ => "other"\n}\n'
       'print(k(0), k(5), k([7, 8]), k("s"), k(500), k(50))',
       "zero small list 7 text big other\n")
prints("struct patterns", "struct Pt {\n x: int\n y: int\n}\nmatch Pt(0, 3) {\n"
       ' Pt(0, y) => print("y", y)\n _ => print("no")\n}', "y 3\n")

print("== errors ==")
prints("try / catch / finally", 'try { let x = 1 / 0 } catch e { print(e.kind) } '
       'finally { print("f") }', "DivideByZero\nf\n")
prints("throw and Error kinds", 'try { throw Error("no", "Bank") } catch e { print(e.kind, '
       'e.message) }', "Bank no\n")
refuses("uncaught errors name the line", 'print(1)\nlet xs = []\nprint(xs[3])',
        ["line 3", "Index"])
refuses("let cannot change", "let x = 1\nx = 2", ["declared with let", "var"])
refuses("typos are caught before running", "let count = 1\nprint(cuont)",
        ["unknown name 'cuont'", "did you mean count"])
refuses("nothing runs when the check fails", 'print("ran")\nprint(nope)', ["unknown name"])
got, _, _ = run('print("ran")\nprint(nope)')
check("... and so nothing was printed", got == "", got)
refuses("parameter types are checked", 'fn f(n: int) => n\nf("a")', ["parameter n", "int"])
refuses("var types are checked", 'var n: int = 1\nn = "x"', ["should be int"])
refuses("return types are checked", "fn f() -> int { print(1) }\nf()", ["result of f"])
refuses("text + number is explained", 'print("a" + 1)', ["cannot add text and int"])
refuses("break outside a loop", "break", ["only for inside a loop"])
refuses("loop variables are fixed", "for i in 0..2 { i = 1 }", ["loop variable"])
refuses("unknown libraries", "use maths", ["did you mean math"])
refuses("other languages' words get a hint", "def f(): pass", ["fn"])
refuses("missing struct fields", "struct P { x: int }\nP()", ["needs a value for x"])
refuses("unknown struct fields", "struct P { x: int }\nlet p = P(1)\np.zz = 2", ["no field"])
refuses("assert", "assert 1 > 2", ["assert failed: 1 > 2"])

print("== it cannot reach Python ==")
refuses("no dunder attributes", "print(().__class__)", ["cannot be reached"])
refuses("no dunder names", "print(__import__)", ["cannot start with __"])
refuses("no Python builtins", "print(open)", ["unknown name 'open'"])
refuses("no eval", 'print(eval("1"))', ["unknown name 'eval'"])
refuses("no compiler helpers", "print(_pc_lib)", ["cannot start with", "_pc_"])
refuses("str.format is PyCmd's own", "print('{0.__class__}'.format(1))", ["no value named"])
_folder = tempfile.mkdtemp(prefix="pcmd-fs-")
try:
    path = os.path.join(_folder, "prog.pcmd")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write('use fs\nfs.write("note.txt", "hi")\nprint(fs.read("note.txt"))\n'
                     'print(fs.read("../../etc/hostname"))\n')
    buf = io.StringIO()
    result = pcmd.run_file(path, stdout=buf)
    check("fs works inside the program's folder", buf.getvalue() == "hi\n", buf.getvalue())
    check("... and not outside it", not result["ok"] and "outside" in result["error"], result)
finally:
    shutil.rmtree(_folder, ignore_errors=True)

print("== libraries ==")
check("eleven libraries", len(LIBRARIES) == 11, sorted(LIBRARIES))
prints("math", "use math\nprint(math.sqrt(16), math.gcd(12, 18), math.is_prime(97))",
       "4.0 6 true\n")
prints("json round trip", 'use json\nlet t = json.stringify({"a": [1, nil]})\nprint(t, '
       'json.parse(t)["a"])', '{"a": [1, null]} [1, nil]\n')
prints("regex", 'use regex\nprint(regex.find_all("[0-9]+", "a1b22"))', '["1", "22"]\n')
prints("text", 'use text.{caesar}\nprint(caesar("abc", 1))', "bcd\n")
prints("stats", "use stats\nprint(stats.mean([1, 2, 3]))", "2.0\n")
prints("input", 'let n = input("? ")\nprint("got", n, input())', "? got 42 nil\n", stdin="42\n")

print("== files, tests, tools ==")
_folder = tempfile.mkdtemp(prefix="pcmd-use-")
try:
    with open(os.path.join(_folder, "lib.pcmd"), "w", encoding="utf-8") as handle:
        handle.write('fn shout(s) => s.upper() + "!"\nlet who = "you"\n')
    main = os.path.join(_folder, "main.pcmd")
    with open(main, "w", encoding="utf-8") as handle:
        handle.write('use "lib" as lib\nprint(lib.shout(lib.who))\n')
    buf = io.StringIO()
    answer = registry.run_file(main, stdout=buf)
    check("use another .pcmd file", answer["ok"] and buf.getvalue() == "YOU!\n", (answer, buf.getvalue()))
    check("the registry knows .pcmd", registry.for_path(main)["id"] == "pycmd"
          and registry.can_run(main))
finally:
    shutil.rmtree(_folder, ignore_errors=True)
out = io.StringIO()
r = pcmd.run_tests('fn add(a, b) => a + b\ntest "adds" { assert add(1, 2) == 3 }\n'
                   'test "fails" { assert add(1, 1) == 3 }', stdout=out)
check("test blocks", r["passed"] == 1 and r["failed"] == 1, out.getvalue())
check("check finds the line", pcmd.check("let a = 1\nprint(b)").get("line") == 2)
check("to_python shows real Python", "def _pc_main" in pcmd.to_python("print(1)"))
repl_out = io.StringIO()
repl = pcmd.Repl(stdout=repl_out)
repl.feed("let x = 20")
repl.feed("x + 1")
repl.feed('print("hi")')
check("the REPL keeps names and shows values", repl_out.getvalue() == "21\nhi\n",
      repl_out.getvalue())

if pcmd._engine() is not None:
    print("== PyCmd 2 (fast engine) ==")
    prints("traits with defaults", 'trait T {\n fn n(self) -> int\n fn two(self) => self.n() * 2\n}\n'
           'struct A impl T {\n v: int\n fn n(self) => self.v\n}\nprint(A(4).two(), A(1) is T)', "8 true\n")
    refuses("a broken promise is caught", 'trait T {\n fn n(self)\n}\nstruct A impl T {\n v: int = 0\n}\nA()',
            ["says it is a T", "fn n"])
    prints("enums with data", 'enum R {\n Ok(v)\n Err(why: str)\n}\nmatch R.Err("x") {\n R.Ok(v) => print(v)\n'
           ' R.Err(w) => print("no", w)\n}', "no x\n")
    prints("operators", 'struct V {\n x: int\n fn plus(self, o) => V(self.x + o.x)\n fn show(self) => "V{self.x}"\n'
           ' fn compare(self, o) => self.x - o.x\n}\nprint(V(1) + V(2), [V(3), V(1)].sorted())', "V3 [V1, V3]\n")
    prints("new libraries", 'use collections\nuse hash\nuse date\nprint(collections.most_common(collections.Counter("aab".chars()), 1),'
           ' hash.md5("a").len(), date.add_days("2026-02-28", 1))', '[("a", 2)] 32 2026-03-01\n')
    prints("unboxed int fast path keeps big ints exact", "var x = 9223372036854775807\nx += 1\nprint(x)",
           "9223372036854775808\n")
    _pk = tempfile.mkdtemp(prefix="pcmd-pkg-")
    try:
        os.makedirs(os.path.join(_pk, "pcmd_packages"))
        with open(os.path.join(_pk, "pcmd_packages", "twice.pcmd"), "w", encoding="utf-8") as handle:
            handle.write("fn twice(n) => n * 2\n")
        mainp = os.path.join(_pk, "app.pycmd")
        with open(mainp, "w", encoding="utf-8") as handle:
            handle.write("use twice\nprint(twice.twice(21))\n")
        buf = io.StringIO()
        res = registry.run_file(mainp, stdout=buf)
        check("packages in pcmd_packages, and .pycmd files", res["ok"] and buf.getvalue() == "42\n", (res, buf.getvalue()))
    finally:
        shutil.rmtree(_pk, ignore_errors=True)

print("== speed ==")
src = ("var t = 0\nfor i in 0..1000000 { t += i % 7 }\n"
       "fn fib(n) { n < 2 ? n : fib(n - 1) + fib(n - 2) }\nprint(t, fib(22))")
started = time.perf_counter()
got, err, _ = run(src)
took = time.perf_counter() - started
check("a million loop turns and fib(22) under 3 s (compiled, not interpreted)",
      err is None and got == "2999997 17711\n" and took < 3, f"{took:.2f}s {err}")

print()
if FAILED:
    print(f"{len(FAILED)} of {PASSED[0] + len(FAILED)} PyCmd checks failed: {FAILED[:8]}")
    raise SystemExit(1)
print(f"all {PASSED[0]} PyCmd checks passed")
