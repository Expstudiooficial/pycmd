"""Practice rounds: hundreds of real exercises per course, every one checked.

A course's hand-written units teach each idea once. That is enough to meet an
idea and not enough to own it, and it left the smaller courses with a hundred
lessons where Python had fifteen hundred. Practice fixes both: after the
units, every course gets rounds of practice - each round one exercise of
every kind the course has taught, with new numbers, new words and a new
shape each time - until the course has about TARGET lessons.

Nothing here is a guess. Every exercise is generated from a small description
(three numbers and a shape, a word, a list) whose answer is worked out in
Python, then written in the course's own language, in that language's own
idiom. tools/test_teach.py (Android) and tools/test_learn.py (Windows) run
every one of them on the real compiler and fail if it prints anything else -
wherever that compiler is installed; a machine without one (Swift, on Linux)
reports the course as not run rather than passed.

Generation is seeded by course, exercise and round, so the same build always
makes the same lessons - a lesson's id is its position, and positions must
not move under somebody's progress.
"""

from __future__ import annotations

import random

TARGET = 1800

WORDS = ["code", "loop", "byte", "data", "list", "node", "tree", "grid", "atom", "stack",
         "queue", "hash", "array", "token", "lambda", "vector", "binary", "string", "object",
         "module", "kernel", "packet", "cursor", "buffer", "widget", "socket", "pixel",
         "matrix", "signal", "branch", "commit", "server", "client", "folder", "record"]

PAIRS = [("big", "small"), ("yes", "no"), ("hot", "cold"), ("over", "under"),
         ("high", "low"), ("win", "lose"), ("open", "shut"), ("fast", "slow")]

NAMES = [("width", "height"), ("price", "qty"), ("left", "right"), ("speed", "hours"),
         ("start", "step"), ("apples", "pears"), ("cost", "extra"), ("size", "gap")]


def _rng(*parts) -> random.Random:
    return random.Random("|".join(str(p) for p in parts))


# ---------------------------------------------------------------------------
# The exercises, independent of any language
# ---------------------------------------------------------------------------
#
# Each family makes a parameter dict from a seeded generator; a language turns
# the dict into a program; `out` is the answer, worked out here once.

def _arith(r):
    a, b, c = r.randint(2, 12), r.randint(2, 12), r.randint(2, 12)
    shapes = [
        ("{a} + {b} * {c}", "(+ {a} (* {b} {c}))", a + b * c),
        ("({a} + {b}) * {c}", "(* (+ {a} {b}) {c})", (a + b) * c),
        ("{a} * {b} - {c}", "(- (* {a} {b}) {c})", a * b - c),
        ("{a} * {b} + {c} * {a}", "(+ (* {a} {b}) (* {c} {a}))", a * b + c * a),
        ("{a} * ({b} + {c})", "(* {a} (+ {b} {c}))", a * (b + c)),
        ("{a} + {b} + {c} * 2", "(+ {a} {b} (* {c} 2))", a + b + c * 2),
    ]
    infix, prefix, value = shapes[r.randrange(len(shapes))]
    if value < 0:
        return None
    return {"e": infix.format(a=a, b=b, c=c), "pe": prefix.format(a=a, b=b, c=c),
            "a": a, "b": b, "c": c, "shape": infix, "out": str(value)}


def _divmod(r):
    a, b = r.randint(20, 99), r.randint(3, 9)
    return {"a": a, "b": b, "out": f"{a // b}\n{a % b}"}


def _vars(r):
    x, y = r.randint(2, 15), r.randint(2, 9)
    n1, n2 = NAMES[r.randrange(len(NAMES))]
    shapes = [("{x} * {y} + {x}", "(+ (* {x} {y}) {x})", x * y + x),
              ("({x} + {y}) * 2", "(* (+ {x} {y}) 2)", (x + y) * 2),
              ("{x} * {x} - {y}", "(- (* {x} {x}) {y})", x * x - y),
              ("{x} + {y} * {y}", "(+ {x} (* {y} {y}))", x + y * y)]
    shape, pshape, value = shapes[r.randrange(len(shapes))]
    return {"n1": n1, "n2": n2, "x": x, "y": y, "shape": shape, "pshape": pshape,
            "v": value, "out": str(value)}


def _compare(r):
    a, b = r.randint(1, 20), r.randint(1, 20)
    op = r.choice([">", "<", ">=", "<=", "==", "!="])
    value = {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b, "==": a == b,
             "!=": a != b}[op]
    return {"a": a, "b": b, "op": op, "v": value}


def _ifelse(r):
    a, b = r.randint(1, 30), r.randint(1, 30)
    if a == b:
        b += 1
    w1, w2 = PAIRS[r.randrange(len(PAIRS))]
    return {"a": a, "b": b, "w1": w1, "w2": w2, "out": w1 if a > b else w2}


def _concat(r):
    s1, s2 = r.sample(WORDS, 2)
    return {"s1": s1, "s2": s2, "out": s1 + s2}


def _length(r):
    s = r.choice(WORDS)
    return {"s": s, "out": str(len(s))}


def _upper(r):
    s = r.choice(WORDS)
    return {"s": s, "out": s.upper()}


def _loop_sum(r):
    n, k = r.randint(3, 9), r.randint(1, 5)
    return {"n": n, "k": k, "out": str(sum(i * k for i in range(1, n + 1)))}


def _countdown(r):
    n = r.randint(3, 6)
    return {"n": n, "out": "\n".join(str(i) for i in range(n, 0, -1))}


def _func(r):
    a, c = r.randint(2, 12), r.randint(1, 9)
    return {"a": a, "c": c, "out": str(a * a + c)}


def _list_index(r):
    xs = [r.randint(1, 99) for _ in range(5)]
    i = r.randrange(5)
    return {"xs": xs, "i": i, "out": str(xs[i])}


def _list_sum(r):
    xs = [r.randint(1, 30) for _ in range(r.randint(3, 6))]
    return {"xs": xs, "out": str(sum(xs))}


def _fact(r):
    n = r.randint(3, 7)
    value = 1
    for i in range(2, n + 1):
        value *= i
    return {"n": n, "out": str(value)}


def _count_even(r):
    n = r.randint(5, 20)
    return {"n": n, "out": str(n // 2)}


def _max2(r):
    a, b = r.sample(range(1, 60), 2)
    return {"a": a, "b": b, "out": str(max(a, b))}


FAMILIES = [
    # (id, title, teach, maker)
    ("arith", "Precedence",
     "Multiplication comes before addition and subtraction, and brackets come first of all. "
     "Work it out, then check.", _arith),
    ("divmod", "Divide and remainder",
     "Whole-number division drops the remainder; the remainder operator gives what is left "
     "over.", _divmod),
    ("vars", "Names and values",
     "A name stands for its value. Put the values in and work the expression out.", _vars),
    ("compare", "Comparisons",
     "A comparison is either true or false. Read the operator carefully.", _compare),
    ("ifelse", "Pick a branch",
     "Only one branch runs: the first one whose condition holds.", _ifelse),
    ("concat", "Joining text",
     "Joining two strings puts the second straight after the first, with no space.", _concat),
    ("length", "Counting characters",
     "The length of a string is how many characters it has.", _length),
    ("upper", "Upper case",
     "Upper-casing changes every letter and leaves everything else alone.", _upper),
    ("loop_sum", "Loop total",
     "The loop adds one term each time round. Write the terms down and add them.", _loop_sum),
    ("countdown", "Counting down",
     "The loop starts high and steps down by one, printing as it goes.", _countdown),
    ("func", "Calling a function",
     "Calling a function puts the argument in place of the parameter. Then it is just "
     "arithmetic.", _func),
    ("list_index", "Indexing",
     "An index picks one element out of a list. Check where this language starts counting.",
     _list_index),
    ("list_sum", "Adding up a list",
     "Every element is added to the total, one after another.", _list_sum),
    ("fact", "Factorial",
     "A factorial multiplies every whole number from 1 up to n.", _fact),
    ("count_even", "Counting matches",
     "Count only the numbers that pass the test - here, the even ones.", _count_even),
    ("max2", "The larger one",
     "The larger of two numbers.", _max2),
]


# ---------------------------------------------------------------------------
# Writing an exercise in a language
# ---------------------------------------------------------------------------

def _ind(text: str, by: int = 4) -> str:
    pad = " " * by
    return "\n".join(pad + line if line else line for line in text.split("\n"))


def _tf(word_true="true", word_false="false"):
    return lambda v: word_true if v else word_false


def _op(mapping=None):
    mapping = mapping or {}
    return lambda op: mapping.get(op, op)


def _nums(xs, sep=", "):
    return sep.join(str(x) for x in xs)


class Lang:
    """A language's way of writing each exercise. Missing ones are skipped."""

    def __init__(self, tf=None, op=None, base=0, **families):
        self.tf = tf or _tf()
        self.op = op or _op()
        self.base = base
        self.families = families

    def write(self, family: str, p: dict):
        maker = self.families.get(family)
        if maker is None:
            return None
        if family == "compare":
            p = dict(p, cop=self.op(p["op"]), out=self.tf(p["v"]))
        if family == "list_index":
            p = dict(p, j=p["i"] + self.base)
        return maker(p), p["out"]


# -- the C family ------------------------------------------------------------

def _c_main(body: str, head: str = "#include <stdio.h>") -> str:
    return f"{head}\n\nint main(void) {{\n{_ind(body)}\n    return 0;\n}}"


C = Lang(
    tf=_tf("1", "0"),
    arith=lambda p: _c_main(f'printf("%d\\n", {p["e"]});'),
    divmod=lambda p: _c_main(f'printf("%d\\n", {p["a"]} / {p["b"]});\n'
                             f'printf("%d\\n", {p["a"]} % {p["b"]});'),
    vars=lambda p: _c_main(f'int {p["n1"]} = {p["x"]};\nint {p["n2"]} = {p["y"]};\n'
                           f'printf("%d\\n", {p["shape"].format(x=p["n1"], y=p["n2"])});'),
    compare=lambda p: _c_main(f'printf("%d\\n", {p["a"]} {p["cop"]} {p["b"]});'),
    ifelse=lambda p: _c_main(f'if ({p["a"]} > {p["b"]}) {{\n    printf("{p["w1"]}\\n");\n'
                             f'}} else {{\n    printf("{p["w2"]}\\n");\n}}'),
    length=lambda p: _c_main(f'printf("%d\\n", (int) strlen("{p["s"]}"));',
                             "#include <stdio.h>\n#include <string.h>"),
    loop_sum=lambda p: _c_main(f'int total = 0;\nfor (int i = 1; i <= {p["n"]}; i++) {{\n'
                               f'    total += i * {p["k"]};\n}}\nprintf("%d\\n", total);'),
    countdown=lambda p: _c_main(f'for (int i = {p["n"]}; i >= 1; i--) {{\n'
                                f'    printf("%d\\n", i);\n}}'),
    func=lambda p: (f'#include <stdio.h>\n\nint f(int x) {{\n    return x * x + {p["c"]};\n}}\n\n'
                    f'int main(void) {{\n    printf("%d\\n", f({p["a"]}));\n    return 0;\n}}'),
    list_index=lambda p: _c_main(f'int xs[] = {{{_nums(p["xs"])}}};\n'
                                 f'printf("%d\\n", xs[{p["j"]}]);'),
    list_sum=lambda p: _c_main(f'int xs[] = {{{_nums(p["xs"])}}};\nint total = 0;\n'
                               f'for (int i = 0; i < {len(p["xs"])}; i++) {{\n'
                               f'    total += xs[i];\n}}\nprintf("%d\\n", total);'),
    fact=lambda p: _c_main(f'int f = 1;\nfor (int i = 2; i <= {p["n"]}; i++) {{\n'
                           f'    f *= i;\n}}\nprintf("%d\\n", f);'),
    count_even=lambda p: _c_main(f'int count = 0;\nfor (int i = 1; i <= {p["n"]}; i++) {{\n'
                                 f'    if (i % 2 == 0) {{\n        count++;\n    }}\n}}\n'
                                 f'printf("%d\\n", count);'),
    max2=lambda p: _c_main(f'int a = {p["a"]}, b = {p["b"]};\n'
                           f'printf("%d\\n", a > b ? a : b);'),
)


def _cpp_main(body: str, head: str = "#include <iostream>") -> str:
    return f"{head}\n\nint main() {{\n{_ind(body)}\n    return 0;\n}}"


CPP = Lang(
    arith=lambda p: _cpp_main(f'std::cout << {p["e"]} << "\\n";'),
    divmod=lambda p: _cpp_main(f'std::cout << {p["a"]} / {p["b"]} << "\\n";\n'
                               f'std::cout << {p["a"]} % {p["b"]} << "\\n";'),
    vars=lambda p: _cpp_main(f'int {p["n1"]} = {p["x"]};\nint {p["n2"]} = {p["y"]};\n'
                             f'std::cout << {p["shape"].format(x=p["n1"], y=p["n2"])} << "\\n";'),
    compare=lambda p: _cpp_main(f'std::cout << std::boolalpha << ({p["a"]} {p["cop"]} {p["b"]})'
                                f' << "\\n";'),
    ifelse=lambda p: _cpp_main(f'if ({p["a"]} > {p["b"]}) {{\n    std::cout << "{p["w1"]}\\n";\n'
                               f'}} else {{\n    std::cout << "{p["w2"]}\\n";\n}}'),
    concat=lambda p: _cpp_main(f'std::string s = std::string("{p["s1"]}") + "{p["s2"]}";\n'
                               f'std::cout << s << "\\n";',
                               "#include <iostream>\n#include <string>"),
    length=lambda p: _cpp_main(f'std::string s = "{p["s"]}";\nstd::cout << s.size() << "\\n";',
                               "#include <iostream>\n#include <string>"),
    loop_sum=lambda p: _cpp_main(f'int total = 0;\nfor (int i = 1; i <= {p["n"]}; i++) {{\n'
                                 f'    total += i * {p["k"]};\n}}\nstd::cout << total << "\\n";'),
    countdown=lambda p: _cpp_main(f'for (int i = {p["n"]}; i >= 1; i--) {{\n'
                                  f'    std::cout << i << "\\n";\n}}'),
    func=lambda p: (f'#include <iostream>\n\nint f(int x) {{\n    return x * x + {p["c"]};\n}}\n\n'
                    f'int main() {{\n    std::cout << f({p["a"]}) << "\\n";\n    return 0;\n}}'),
    list_index=lambda p: _cpp_main(f'std::vector<int> xs = {{{_nums(p["xs"])}}};\n'
                                   f'std::cout << xs[{p["j"]}] << "\\n";',
                                   "#include <iostream>\n#include <vector>"),
    list_sum=lambda p: _cpp_main(f'std::vector<int> xs = {{{_nums(p["xs"])}}};\nint total = 0;\n'
                                 f'for (int x : xs) {{\n    total += x;\n}}\n'
                                 f'std::cout << total << "\\n";',
                                 "#include <iostream>\n#include <vector>"),
    fact=lambda p: _cpp_main(f'int f = 1;\nfor (int i = 2; i <= {p["n"]}; i++) {{\n'
                             f'    f *= i;\n}}\nstd::cout << f << "\\n";'),
    count_even=lambda p: _cpp_main(f'int count = 0;\nfor (int i = 1; i <= {p["n"]}; i++) {{\n'
                                   f'    if (i % 2 == 0) count++;\n}}\n'
                                   f'std::cout << count << "\\n";'),
    max2=lambda p: _cpp_main(f'std::cout << std::max({p["a"]}, {p["b"]}) << "\\n";',
                             "#include <iostream>\n#include <algorithm>"),
)


def _java(body: str) -> str:
    return ("public class Main {\n    public static void main(String[] args) {\n"
            f"{_ind(body, 8)}\n    }}\n}}")


JAVA = Lang(
    arith=lambda p: _java(f'System.out.println({p["e"]});'),
    divmod=lambda p: _java(f'System.out.println({p["a"]} / {p["b"]});\n'
                           f'System.out.println({p["a"]} % {p["b"]});'),
    vars=lambda p: _java(f'int {p["n1"]} = {p["x"]};\nint {p["n2"]} = {p["y"]};\n'
                         f'System.out.println({p["shape"].format(x=p["n1"], y=p["n2"])});'),
    compare=lambda p: _java(f'System.out.println({p["a"]} {p["cop"]} {p["b"]});'),
    ifelse=lambda p: _java(f'if ({p["a"]} > {p["b"]}) {{\n    System.out.println("{p["w1"]}");\n'
                           f'}} else {{\n    System.out.println("{p["w2"]}");\n}}'),
    concat=lambda p: _java(f'System.out.println("{p["s1"]}" + "{p["s2"]}");'),
    length=lambda p: _java(f'System.out.println("{p["s"]}".length());'),
    upper=lambda p: _java(f'System.out.println("{p["s"]}".toUpperCase());'),
    loop_sum=lambda p: _java(f'int total = 0;\nfor (int i = 1; i <= {p["n"]}; i++) {{\n'
                             f'    total += i * {p["k"]};\n}}\nSystem.out.println(total);'),
    countdown=lambda p: _java(f'for (int i = {p["n"]}; i >= 1; i--) {{\n'
                              f'    System.out.println(i);\n}}'),
    func=lambda p: ("public class Main {\n    static int f(int x) {\n"
                    f'        return x * x + {p["c"]};\n    }}\n\n'
                    "    public static void main(String[] args) {\n"
                    f'        System.out.println(f({p["a"]}));\n    }}\n}}'),
    list_index=lambda p: _java(f'int[] xs = {{{_nums(p["xs"])}}};\n'
                               f'System.out.println(xs[{p["j"]}]);'),
    list_sum=lambda p: _java(f'int[] xs = {{{_nums(p["xs"])}}};\nint total = 0;\n'
                             f'for (int x : xs) {{\n    total += x;\n}}\n'
                             f'System.out.println(total);'),
    fact=lambda p: _java(f'int f = 1;\nfor (int i = 2; i <= {p["n"]}; i++) {{\n'
                         f'    f *= i;\n}}\nSystem.out.println(f);'),
    count_even=lambda p: _java(f'int count = 0;\nfor (int i = 1; i <= {p["n"]}; i++) {{\n'
                               f'    if (i % 2 == 0) count++;\n}}\nSystem.out.println(count);'),
    max2=lambda p: _java(f'System.out.println(Math.max({p["a"]}, {p["b"]}));'),
)


def _kt(body: str) -> str:
    return f"fun main() {{\n{_ind(body)}\n}}"


KOTLIN = Lang(
    arith=lambda p: _kt(f'println({p["e"]})'),
    divmod=lambda p: _kt(f'println({p["a"]} / {p["b"]})\nprintln({p["a"]} % {p["b"]})'),
    vars=lambda p: _kt(f'val {p["n1"]} = {p["x"]}\nval {p["n2"]} = {p["y"]}\n'
                       f'println({p["shape"].format(x=p["n1"], y=p["n2"])})'),
    compare=lambda p: _kt(f'println({p["a"]} {p["cop"]} {p["b"]})'),
    ifelse=lambda p: _kt(f'if ({p["a"]} > {p["b"]}) {{\n    println("{p["w1"]}")\n'
                         f'}} else {{\n    println("{p["w2"]}")\n}}'),
    concat=lambda p: _kt(f'println("{p["s1"]}" + "{p["s2"]}")'),
    length=lambda p: _kt(f'println("{p["s"]}".length)'),
    upper=lambda p: _kt(f'println("{p["s"]}".uppercase())'),
    loop_sum=lambda p: _kt(f'var total = 0\nfor (i in 1..{p["n"]}) {{\n'
                           f'    total += i * {p["k"]}\n}}\nprintln(total)'),
    countdown=lambda p: _kt(f'for (i in {p["n"]} downTo 1) {{\n    println(i)\n}}'),
    func=lambda p: (f'fun f(x: Int): Int = x * x + {p["c"]}\n\n'
                    f'fun main() {{\n    println(f({p["a"]}))\n}}'),
    list_index=lambda p: _kt(f'val xs = listOf({_nums(p["xs"])})\nprintln(xs[{p["j"]}])'),
    list_sum=lambda p: _kt(f'val xs = listOf({_nums(p["xs"])})\nprintln(xs.sum())'),
    fact=lambda p: _kt(f'var f = 1\nfor (i in 2..{p["n"]}) {{\n    f *= i\n}}\nprintln(f)'),
    count_even=lambda p: _kt(f'println((1..{p["n"]}).count {{ it % 2 == 0 }})'),
    max2=lambda p: _kt(f'println(maxOf({p["a"]}, {p["b"]}))'),
)

SWIFT = Lang(
    arith=lambda p: f'print({p["e"]})',
    divmod=lambda p: f'print({p["a"]} / {p["b"]})\nprint({p["a"]} % {p["b"]})',
    vars=lambda p: (f'let {p["n1"]} = {p["x"]}\nlet {p["n2"]} = {p["y"]}\n'
                    f'print({p["shape"].format(x=p["n1"], y=p["n2"])})'),
    compare=lambda p: f'print({p["a"]} {p["cop"]} {p["b"]})',
    ifelse=lambda p: (f'if {p["a"]} > {p["b"]} {{\n    print("{p["w1"]}")\n'
                      f'}} else {{\n    print("{p["w2"]}")\n}}'),
    concat=lambda p: f'print("{p["s1"]}" + "{p["s2"]}")',
    length=lambda p: f'print("{p["s"]}".count)',
    upper=lambda p: f'print("{p["s"]}".uppercased())',
    loop_sum=lambda p: (f'var total = 0\nfor i in 1...{p["n"]} {{\n'
                        f'    total += i * {p["k"]}\n}}\nprint(total)'),
    countdown=lambda p: f'for i in stride(from: {p["n"]}, through: 1, by: -1) {{\n    print(i)\n}}',
    func=lambda p: (f'func f(_ x: Int) -> Int {{\n    return x * x + {p["c"]}\n}}\n\n'
                    f'print(f({p["a"]}))'),
    list_index=lambda p: f'let xs = [{_nums(p["xs"])}]\nprint(xs[{p["j"]}])',
    list_sum=lambda p: f'let xs = [{_nums(p["xs"])}]\nprint(xs.reduce(0, +))',
    fact=lambda p: f'var f = 1\nfor i in 2...{p["n"]} {{\n    f *= i\n}}\nprint(f)',
    count_even=lambda p: f'print((1...{p["n"]}).filter {{ $0 % 2 == 0 }}.count)',
    max2=lambda p: f'print(max({p["a"]}, {p["b"]}))',
)

GO = Lang(
    arith=lambda p: _go(f'fmt.Println({p["e"]})'),
    divmod=lambda p: _go(f'fmt.Println({p["a"]} / {p["b"]})\nfmt.Println({p["a"]} % {p["b"]})'),
    vars=lambda p: _go(f'{p["n1"]} := {p["x"]}\n{p["n2"]} := {p["y"]}\n'
                       f'fmt.Println({p["shape"].format(x=p["n1"], y=p["n2"])})'),
    compare=lambda p: _go(f'fmt.Println({p["a"]} {p["cop"]} {p["b"]})'),
    ifelse=lambda p: _go(f'if {p["a"]} > {p["b"]} {{\n    fmt.Println("{p["w1"]}")\n'
                         f'}} else {{\n    fmt.Println("{p["w2"]}")\n}}'),
    concat=lambda p: _go(f'fmt.Println("{p["s1"]}" + "{p["s2"]}")'),
    length=lambda p: _go(f'fmt.Println(len("{p["s"]}"))'),
    upper=lambda p: _go(f'fmt.Println(strings.ToUpper("{p["s"]}"))', ["fmt", "strings"]),
    loop_sum=lambda p: _go(f'total := 0\nfor i := 1; i <= {p["n"]}; i++ {{\n'
                           f'    total += i * {p["k"]}\n}}\nfmt.Println(total)'),
    countdown=lambda p: _go(f'for i := {p["n"]}; i >= 1; i-- {{\n    fmt.Println(i)\n}}'),
    func=lambda p: (f'package main\n\nimport "fmt"\n\nfunc f(x int) int {{\n'
                    f'    return x * x + {p["c"]}\n}}\n\nfunc main() {{\n'
                    f'    fmt.Println(f({p["a"]}))\n}}'),
    list_index=lambda p: _go(f'xs := []int{{{_nums(p["xs"])}}}\nfmt.Println(xs[{p["j"]}])'),
    list_sum=lambda p: _go(f'xs := []int{{{_nums(p["xs"])}}}\ntotal := 0\n'
                           f'for _, x := range xs {{\n    total += x\n}}\nfmt.Println(total)'),
    fact=lambda p: _go(f'f := 1\nfor i := 2; i <= {p["n"]}; i++ {{\n    f *= i\n}}\n'
                       f'fmt.Println(f)'),
    count_even=lambda p: _go(f'count := 0\nfor i := 1; i <= {p["n"]}; i++ {{\n'
                             f'    if i%2 == 0 {{\n        count++\n    }}\n}}\n'
                             f'fmt.Println(count)'),
    max2=lambda p: _go(f'a, b := {p["a"]}, {p["b"]}\nif a > b {{\n    fmt.Println(a)\n'
                       f'}} else {{\n    fmt.Println(b)\n}}'),
)


def _go(body: str, imports=("fmt",)) -> str:
    if len(imports) == 1:
        head = f'import "{imports[0]}"'
    else:
        head = "import (\n" + "\n".join(f'    "{i}"' for i in imports) + "\n)"
    return f"package main\n\n{head}\n\nfunc main() {{\n{_ind(body)}\n}}"


def _rs(body: str) -> str:
    return f"fn main() {{\n{_ind(body)}\n}}"


RUST = Lang(
    arith=lambda p: _rs(f'println!("{{}}", {p["e"]});'),
    divmod=lambda p: _rs(f'println!("{{}}", {p["a"]} / {p["b"]});\n'
                         f'println!("{{}}", {p["a"]} % {p["b"]});'),
    vars=lambda p: _rs(f'let {p["n1"]} = {p["x"]};\nlet {p["n2"]} = {p["y"]};\n'
                       f'println!("{{}}", {p["shape"].format(x=p["n1"], y=p["n2"])});'),
    compare=lambda p: _rs(f'println!("{{}}", {p["a"]} {p["cop"]} {p["b"]});'),
    ifelse=lambda p: _rs(f'if {p["a"]} > {p["b"]} {{\n    println!("{p["w1"]}");\n'
                         f'}} else {{\n    println!("{p["w2"]}");\n}}'),
    concat=lambda p: _rs(f'let s = String::from("{p["s1"]}") + "{p["s2"]}";\n'
                         f'println!("{{}}", s);'),
    length=lambda p: _rs(f'println!("{{}}", "{p["s"]}".len());'),
    upper=lambda p: _rs(f'println!("{{}}", "{p["s"]}".to_uppercase());'),
    loop_sum=lambda p: _rs(f'let mut total = 0;\nfor i in 1..={p["n"]} {{\n'
                           f'    total += i * {p["k"]};\n}}\nprintln!("{{}}", total);'),
    countdown=lambda p: _rs(f'for i in (1..={p["n"]}).rev() {{\n    println!("{{}}", i);\n}}'),
    func=lambda p: (f'fn f(x: i32) -> i32 {{\n    x * x + {p["c"]}\n}}\n\n'
                    f'fn main() {{\n    println!("{{}}", f({p["a"]}));\n}}'),
    list_index=lambda p: _rs(f'let xs = [{_nums(p["xs"])}];\nprintln!("{{}}", xs[{p["j"]}]);'),
    list_sum=lambda p: _rs(f'let xs = vec![{_nums(p["xs"])}];\n'
                           f'let total: i32 = xs.iter().sum();\nprintln!("{{}}", total);'),
    fact=lambda p: _rs(f'let mut f = 1;\nfor i in 2..={p["n"]} {{\n    f *= i;\n}}\n'
                       f'println!("{{}}", f);'),
    count_even=lambda p: _rs(f'let mut count = 0;\nfor i in 1..={p["n"]} {{\n'
                             f'    if i % 2 == 0 {{\n        count += 1;\n    }}\n}}\n'
                             f'println!("{{}}", count);'),
    max2=lambda p: _rs(f'let a = {p["a"]};\nlet b = {p["b"]};\n'
                       f'println!("{{}}", if a > b {{ a }} else {{ b }});'),
)

PYTHON = Lang(
    tf=_tf("True", "False"),
    arith=lambda p: f'print({p["e"]})',
    divmod=lambda p: f'print({p["a"]} // {p["b"]})\nprint({p["a"]} % {p["b"]})',
    vars=lambda p: (f'{p["n1"]} = {p["x"]}\n{p["n2"]} = {p["y"]}\n'
                    f'print({p["shape"].format(x=p["n1"], y=p["n2"])})'),
    compare=lambda p: f'print({p["a"]} {p["cop"]} {p["b"]})',
    ifelse=lambda p: (f'if {p["a"]} > {p["b"]}:\n    print("{p["w1"]}")\n'
                      f'else:\n    print("{p["w2"]}")'),
    concat=lambda p: f'print("{p["s1"]}" + "{p["s2"]}")',
    length=lambda p: f'print(len("{p["s"]}"))',
    upper=lambda p: f'print("{p["s"]}".upper())',
    loop_sum=lambda p: (f'total = 0\nfor i in range(1, {p["n"] + 1}):\n'
                        f'    total += i * {p["k"]}\nprint(total)'),
    countdown=lambda p: f'for i in range({p["n"]}, 0, -1):\n    print(i)',
    func=lambda p: f'def f(x):\n    return x * x + {p["c"]}\n\nprint(f({p["a"]}))',
    list_index=lambda p: f'xs = [{_nums(p["xs"])}]\nprint(xs[{p["j"]}])',
    list_sum=lambda p: f'xs = [{_nums(p["xs"])}]\nprint(sum(xs))',
    fact=lambda p: f'f = 1\nfor i in range(2, {p["n"] + 1}):\n    f *= i\nprint(f)',
    count_even=lambda p: f'print(sum(1 for i in range(1, {p["n"] + 1}) if i % 2 == 0))',
    max2=lambda p: f'print(max({p["a"]}, {p["b"]}))',
)

JS = Lang(
    op=_op({"==": "===", "!=": "!=="}),
    arith=lambda p: f'console.log({p["e"]});',
    divmod=lambda p: (f'console.log(Math.floor({p["a"]} / {p["b"]}));\n'
                      f'console.log({p["a"]} % {p["b"]});'),
    vars=lambda p: (f'const {p["n1"]} = {p["x"]};\nconst {p["n2"]} = {p["y"]};\n'
                    f'console.log({p["shape"].format(x=p["n1"], y=p["n2"])});'),
    compare=lambda p: f'console.log({p["a"]} {p["cop"]} {p["b"]});',
    ifelse=lambda p: (f'if ({p["a"]} > {p["b"]}) {{\n    console.log("{p["w1"]}");\n'
                      f'}} else {{\n    console.log("{p["w2"]}");\n}}'),
    concat=lambda p: f'console.log("{p["s1"]}" + "{p["s2"]}");',
    length=lambda p: f'console.log("{p["s"]}".length);',
    upper=lambda p: f'console.log("{p["s"]}".toUpperCase());',
    loop_sum=lambda p: (f'let total = 0;\nfor (let i = 1; i <= {p["n"]}; i++) {{\n'
                        f'    total += i * {p["k"]};\n}}\nconsole.log(total);'),
    countdown=lambda p: f'for (let i = {p["n"]}; i >= 1; i--) {{\n    console.log(i);\n}}',
    func=lambda p: (f'function f(x) {{\n    return x * x + {p["c"]};\n}}\n\n'
                    f'console.log(f({p["a"]}));'),
    list_index=lambda p: f'const xs = [{_nums(p["xs"])}];\nconsole.log(xs[{p["j"]}]);',
    list_sum=lambda p: (f'const xs = [{_nums(p["xs"])}];\n'
                        f'console.log(xs.reduce((a, b) => a + b, 0));'),
    fact=lambda p: (f'let f = 1;\nfor (let i = 2; i <= {p["n"]}; i++) {{\n    f *= i;\n}}\n'
                    f'console.log(f);'),
    count_even=lambda p: (f'let count = 0;\nfor (let i = 1; i <= {p["n"]}; i++) {{\n'
                          f'    if (i % 2 === 0) count++;\n}}\nconsole.log(count);'),
    max2=lambda p: f'console.log(Math.max({p["a"]}, {p["b"]}));',
)

TS = Lang(
    op=_op({"==": "===", "!=": "!=="}),
    arith=lambda p: f'const result: number = {p["e"]};\nconsole.log(result);',
    divmod=lambda p: (f'console.log(Math.floor({p["a"]} / {p["b"]}));\n'
                      f'console.log({p["a"]} % {p["b"]});'),
    vars=lambda p: (f'const {p["n1"]}: number = {p["x"]};\nconst {p["n2"]}: number = {p["y"]};\n'
                    f'console.log({p["shape"].format(x=p["n1"], y=p["n2"])});'),
    compare=lambda p: f'const a: number = {p["a"]};\nconsole.log(a {p["cop"]} {p["b"]});',
    ifelse=lambda p: (f'const a: number = {p["a"]};\nif (a > {p["b"]}) {{\n'
                      f'    console.log("{p["w1"]}");\n}} else {{\n'
                      f'    console.log("{p["w2"]}");\n}}'),
    concat=lambda p: f'const s: string = "{p["s1"]}" + "{p["s2"]}";\nconsole.log(s);',
    length=lambda p: f'const s: string = "{p["s"]}";\nconsole.log(s.length);',
    upper=lambda p: f'const s: string = "{p["s"]}";\nconsole.log(s.toUpperCase());',
    loop_sum=lambda p: (f'let total: number = 0;\nfor (let i = 1; i <= {p["n"]}; i++) {{\n'
                        f'    total += i * {p["k"]};\n}}\nconsole.log(total);'),
    countdown=lambda p: f'for (let i = {p["n"]}; i >= 1; i--) {{\n    console.log(i);\n}}',
    func=lambda p: (f'function f(x: number): number {{\n    return x * x + {p["c"]};\n}}\n\n'
                    f'console.log(f({p["a"]}));'),
    list_index=lambda p: (f'const xs: number[] = [{_nums(p["xs"])}];\n'
                          f'console.log(xs[{p["j"]}]);'),
    list_sum=lambda p: (f'const xs: number[] = [{_nums(p["xs"])}];\n'
                        f'console.log(xs.reduce((a, b) => a + b, 0));'),
    fact=lambda p: (f'let f: number = 1;\nfor (let i = 2; i <= {p["n"]}; i++) {{\n'
                    f'    f *= i;\n}}\nconsole.log(f);'),
    count_even=lambda p: (f'const evens = [...Array({p["n"]}).keys()]\n'
                          f'    .map((i) => i + 1)\n    .filter((i) => i % 2 === 0);\n'
                          f'console.log(evens.length);'),
    max2=lambda p: f'console.log(Math.max({p["a"]}, {p["b"]}));',
)

PHP = Lang(
    op=_op({"==": "===", "!=": "!=="}),
    arith=lambda p: f'<?php\necho {p["e"]}, "\\n";',
    divmod=lambda p: f'<?php\necho intdiv({p["a"]}, {p["b"]}), "\\n";\necho {p["a"]} % {p["b"]}, "\\n";',
    vars=lambda p: (f'<?php\n${p["n1"]} = {p["x"]};\n${p["n2"]} = {p["y"]};\n'
                    f'echo {p["shape"].format(x="$" + p["n1"], y="$" + p["n2"])}, "\\n";'),
    compare=lambda p: f'<?php\nvar_export({p["a"]} {p["cop"]} {p["b"]});\necho "\\n";',
    ifelse=lambda p: (f'<?php\nif ({p["a"]} > {p["b"]}) {{\n    echo "{p["w1"]}\\n";\n'
                      f'}} else {{\n    echo "{p["w2"]}\\n";\n}}'),
    concat=lambda p: f'<?php\necho "{p["s1"]}" . "{p["s2"]}", "\\n";',
    length=lambda p: f'<?php\necho strlen("{p["s"]}"), "\\n";',
    upper=lambda p: f'<?php\necho strtoupper("{p["s"]}"), "\\n";',
    loop_sum=lambda p: (f'<?php\n$total = 0;\nfor ($i = 1; $i <= {p["n"]}; $i++) {{\n'
                        f'    $total += $i * {p["k"]};\n}}\necho $total, "\\n";'),
    countdown=lambda p: f'<?php\nfor ($i = {p["n"]}; $i >= 1; $i--) {{\n    echo $i, "\\n";\n}}',
    func=lambda p: (f'<?php\nfunction f($x) {{\n    return $x * $x + {p["c"]};\n}}\n\n'
                    f'echo f({p["a"]}), "\\n";'),
    list_index=lambda p: f'<?php\n$xs = [{_nums(p["xs"])}];\necho $xs[{p["j"]}], "\\n";',
    list_sum=lambda p: f'<?php\n$xs = [{_nums(p["xs"])}];\necho array_sum($xs), "\\n";',
    fact=lambda p: (f'<?php\n$f = 1;\nfor ($i = 2; $i <= {p["n"]}; $i++) {{\n'
                    f'    $f *= $i;\n}}\necho $f, "\\n";'),
    count_even=lambda p: (f'<?php\n$evens = array_filter(range(1, {p["n"]}), '
                          f'fn($i) => $i % 2 === 0);\necho count($evens), "\\n";'),
    max2=lambda p: f'<?php\necho max({p["a"]}, {p["b"]}), "\\n";',
)

RUBY = Lang(
    arith=lambda p: f'puts {p["e"]}',
    divmod=lambda p: f'puts {p["a"]} / {p["b"]}\nputs {p["a"]} % {p["b"]}',
    vars=lambda p: (f'{p["n1"]} = {p["x"]}\n{p["n2"]} = {p["y"]}\n'
                    f'puts {p["shape"].format(x=p["n1"], y=p["n2"])}'),
    compare=lambda p: f'puts {p["a"]} {p["cop"]} {p["b"]}',
    ifelse=lambda p: (f'if {p["a"]} > {p["b"]}\n  puts "{p["w1"]}"\nelse\n'
                      f'  puts "{p["w2"]}"\nend'),
    concat=lambda p: f'puts "{p["s1"]}" + "{p["s2"]}"',
    length=lambda p: f'puts "{p["s"]}".length',
    upper=lambda p: f'puts "{p["s"]}".upcase',
    loop_sum=lambda p: (f'total = 0\n(1..{p["n"]}).each do |i|\n  total += i * {p["k"]}\n'
                        f'end\nputs total'),
    countdown=lambda p: f'{p["n"]}.downto(1) do |i|\n  puts i\nend',
    func=lambda p: f'def f(x)\n  x * x + {p["c"]}\nend\n\nputs f({p["a"]})',
    list_index=lambda p: f'xs = [{_nums(p["xs"])}]\nputs xs[{p["j"]}]',
    list_sum=lambda p: f'xs = [{_nums(p["xs"])}]\nputs xs.sum',
    fact=lambda p: f'puts (1..{p["n"]}).reduce(:*)',
    count_even=lambda p: f'puts (1..{p["n"]}).count(&:even?)',
    max2=lambda p: f'puts [{p["a"]}, {p["b"]}].max',
)

LUA = Lang(
    op=_op({"!=": "~="}), base=1,
    arith=lambda p: f'print({p["e"]})',
    divmod=lambda p: f'print({p["a"]} // {p["b"]})\nprint({p["a"]} % {p["b"]})',
    vars=lambda p: (f'local {p["n1"]} = {p["x"]}\nlocal {p["n2"]} = {p["y"]}\n'
                    f'print({p["shape"].format(x=p["n1"], y=p["n2"])})'),
    compare=lambda p: f'print({p["a"]} {p["cop"]} {p["b"]})',
    ifelse=lambda p: (f'if {p["a"]} > {p["b"]} then\n  print("{p["w1"]}")\nelse\n'
                      f'  print("{p["w2"]}")\nend'),
    concat=lambda p: f'print("{p["s1"]}" .. "{p["s2"]}")',
    length=lambda p: f'print(#"{p["s"]}")',
    upper=lambda p: f'print(string.upper("{p["s"]}"))',
    loop_sum=lambda p: (f'local total = 0\nfor i = 1, {p["n"]} do\n  total = total + i * {p["k"]}\n'
                        f'end\nprint(total)'),
    countdown=lambda p: f'for i = {p["n"]}, 1, -1 do\n  print(i)\nend',
    func=lambda p: f'local function f(x)\n  return x * x + {p["c"]}\nend\n\nprint(f({p["a"]}))',
    list_index=lambda p: f'local xs = {{{_nums(p["xs"])}}}\nprint(xs[{p["j"]}])',
    list_sum=lambda p: (f'local xs = {{{_nums(p["xs"])}}}\nlocal total = 0\n'
                        f'for _, x in ipairs(xs) do\n  total = total + x\nend\nprint(total)'),
    fact=lambda p: f'local f = 1\nfor i = 2, {p["n"]} do\n  f = f * i\nend\nprint(f)',
    count_even=lambda p: (f'local count = 0\nfor i = 1, {p["n"]} do\n'
                          f'  if i % 2 == 0 then\n    count = count + 1\n  end\nend\nprint(count)'),
    max2=lambda p: f'print(math.max({p["a"]}, {p["b"]}))',
)

_SH_OP = {">": "-gt", "<": "-lt", ">=": "-ge", "<=": "-le", "==": "-eq", "!=": "-ne"}
SHELL = Lang(
    op=_op(_SH_OP),
    arith=lambda p: f'#!/bin/sh\necho $(({p["e"]}))',
    divmod=lambda p: f'#!/bin/sh\necho $(({p["a"]} / {p["b"]}))\necho $(({p["a"]} % {p["b"]}))',
    vars=lambda p: (f'#!/bin/sh\n{p["n1"]}={p["x"]}\n{p["n2"]}={p["y"]}\n'
                    f'echo $(({p["shape"].format(x=p["n1"], y=p["n2"])}))'),
    compare=lambda p: (f'#!/bin/sh\nif [ {p["a"]} {p["cop"]} {p["b"]} ]; then\n'
                       f'  echo true\nelse\n  echo false\nfi'),
    ifelse=lambda p: (f'#!/bin/sh\nif [ {p["a"]} -gt {p["b"]} ]; then\n  echo {p["w1"]}\n'
                      f'else\n  echo {p["w2"]}\nfi'),
    concat=lambda p: f'#!/bin/sh\na="{p["s1"]}"\nb="{p["s2"]}"\necho "$a$b"',
    length=lambda p: f'#!/bin/sh\ns="{p["s"]}"\necho ${{#s}}',
    upper=lambda p: f'#!/bin/sh\necho "{p["s"]}" | tr a-z A-Z',
    loop_sum=lambda p: (f'#!/bin/sh\ntotal=0\nfor i in $(seq 1 {p["n"]}); do\n'
                        f'  total=$((total + i * {p["k"]}))\ndone\necho $total'),
    countdown=lambda p: f'#!/bin/sh\nfor i in $(seq {p["n"]} -1 1); do\n  echo $i\ndone',
    func=lambda p: (f'#!/bin/sh\nf() {{\n  echo $(($1 * $1 + {p["c"]}))\n}}\n\nf {p["a"]}'),
    list_index=lambda p: (f'#!/bin/bash\nxs=({_nums(p["xs"], " ")})\necho ${{xs[{p["j"]}]}}'),
    list_sum=lambda p: (f'#!/bin/sh\ntotal=0\nfor x in {_nums(p["xs"], " ")}; do\n'
                        f'  total=$((total + x))\ndone\necho $total'),
    fact=lambda p: (f'#!/bin/sh\nf=1\nfor i in $(seq 2 {p["n"]}); do\n  f=$((f * i))\ndone\n'
                    f'echo $f'),
    count_even=lambda p: (f'#!/bin/sh\ncount=0\nfor i in $(seq 1 {p["n"]}); do\n'
                          f'  if [ $((i % 2)) -eq 0 ]; then\n    count=$((count + 1))\n'
                          f'  fi\ndone\necho $count'),
    max2=lambda p: (f'#!/bin/sh\na={p["a"]}\nb={p["b"]}\nif [ $a -gt $b ]; then\n'
                    f'  echo $a\nelse\n  echo $b\nfi'),
)

SQL = Lang(
    tf=_tf("1", "0"), op=_op({"==": "=", "!=": "<>"}),
    arith=lambda p: f'SELECT {p["e"]};',
    divmod=lambda p: f'SELECT {p["a"]} / {p["b"]};\nSELECT {p["a"]} % {p["b"]};',
    compare=lambda p: f'SELECT {p["a"]} {p["cop"]} {p["b"]};',
    ifelse=lambda p: (f"SELECT CASE\n  WHEN {p['a']} > {p['b']} THEN '{p['w1']}'\n"
                      f"  ELSE '{p['w2']}'\nEND;"),
    concat=lambda p: f"SELECT '{p['s1']}' || '{p['s2']}';",
    length=lambda p: f"SELECT length('{p['s']}');",
    upper=lambda p: f"SELECT upper('{p['s']}');",
    loop_sum=lambda p: (f"WITH RECURSIVE n(i) AS (\n  SELECT 1\n  UNION ALL\n"
                        f"  SELECT i + 1 FROM n WHERE i < {p['n']}\n)\n"
                        f"SELECT sum(i * {p['k']}) FROM n;"),
    countdown=lambda p: (f"WITH RECURSIVE n(i) AS (\n  SELECT {p['n']}\n  UNION ALL\n"
                         f"  SELECT i - 1 FROM n WHERE i > 1\n)\nSELECT i FROM n;"),
    list_sum=lambda p: (f"SELECT sum(column1)\nFROM (VALUES "
                        + ", ".join(f"({x})" for x in p["xs"]) + ");"),
    count_even=lambda p: (f"WITH RECURSIVE n(i) AS (\n  SELECT 1\n  UNION ALL\n"
                          f"  SELECT i + 1 FROM n WHERE i < {p['n']}\n)\n"
                          f"SELECT count(*) FROM n WHERE i % 2 = 0;"),
    max2=lambda p: f'SELECT max({p["a"]}, {p["b"]});',
)

LANGS = {
    "python": PYTHON, "javascript": JS, "typescript": TS, "c": C, "cpp": CPP,
    "rust": RUST, "go": GO, "java": JAVA, "kotlin": KOTLIN, "swift": SWIFT,
    "php": PHP, "ruby": RUBY, "lua": LUA, "shell": SHELL, "sql": SQL,
}

#: Lessons a language gets extra, beyond the phone's. Filled in by modules
#: that know languages the phone does not carry (see practice_more).
MORE_LANGS: dict = {}

#: Generators for the courses whose snippets are documents, not programs:
#: course id -> question makers (see practice_docs).
try:
    from .practice_docs import DOCUMENTS
except ImportError:
    DOCUMENTS = {}


# ---------------------------------------------------------------------------
# Counting lessons without making them
# ---------------------------------------------------------------------------

def _estimate(course, topic) -> int:
    """How many lessons a topic makes - the same rules as _topic_lessons, without
    building the lessons. Exact for everything but "which", which assumes a
    question can be found; with hundreds of snippets in a course, it can."""
    from . import CODE_COURSES, WHICH_MAX_LINES, _TOKEN, _break, _lines

    count = 1
    lines = len(_lines(topic.code))
    if topic.out:
        count += 1
        if not topic.ask and lines <= WHICH_MAX_LINES:
            count += 1
    skip = {"a", "i", "x", "n", "s"}
    if any(len(w) > 2 and w.lower() not in skip for w in _TOKEN.findall(topic.code)):
        count += 1
    if course.id in CODE_COURSES and not topic.ask:
        broken = _break(course, topic)
        if broken and len(_lines(broken[0])) >= 2:
            count += 1
    if lines >= 3:
        count += 1
    if not topic.ask:
        count += 1
    return count


# ---------------------------------------------------------------------------
# Putting practice into the courses
# ---------------------------------------------------------------------------

def _program_rounds(course, lang: Lang, need: int):
    """Rounds of one exercise of every kind, until there are `need` lessons."""
    from . import Topic, Unit

    made = []
    seen = {t.code for t in course.topics if isinstance(t, Topic)}
    total = 0
    round_no = 0
    while total < need and round_no < 200:
        round_no += 1
        unit_topics = []
        for fid, title, teach, maker in FAMILIES:
            if fid not in lang.families:
                continue
            for attempt in range(12):
                params = maker(_rng(course.id, fid, round_no, attempt))
                if params is None:
                    continue
                written = lang.write(fid, params)
                if written is None:
                    break
                code, out = written
                if code in seen:
                    continue
                seen.add(code)
                topic = Topic(f"{title} {round_no}", teach, code, out)
                unit_topics.append(topic)
                total += _estimate(course, topic)
                break
            if total >= need:
                break
        if not unit_topics:
            break
        made.append(Unit(f"Practice round {round_no}",
                         "One of everything so far, with new numbers and new words."))
        made.extend(unit_topics)
    return made


def _document_rounds(course, makers, need: int):
    """Rounds of one question about a fresh document from every maker."""
    from . import Topic, Unit

    made = []
    seen = {t.code for t in course.topics if isinstance(t, Topic)}
    total = 0
    round_no = 0
    while total < need and round_no < 400:
        round_no += 1
        unit_topics = []
        for index, maker in enumerate(makers):
            for attempt in range(12):
                row = maker(_rng(course.id, maker.__name__, index, round_no, attempt))
                if row is None:
                    continue
                title, teach, code, ask, out = row
                if (code, ask) in seen:
                    continue
                seen.add((code, ask))
                topic = Topic(f"{title} {round_no}", teach, code, out, ask=ask)
                unit_topics.append(topic)
                total += _estimate(course, topic)
                break
            if total >= need:
                break
        if not unit_topics:
            break
        made.append(Unit(f"Practice round {round_no}",
                         "Questions about new documents, one of every kind."))
        made.extend(unit_topics)
    return made


def _existing(course) -> int:
    from . import Topic

    return sum(_estimate(course, t) for t in course.topics if isinstance(t, Topic))


def extend(courses: dict, target: int = TARGET) -> None:
    for course in courses.values():
        lang = LANGS.get(course.id) or MORE_LANGS.get(course.id)
        maker = DOCUMENTS.get(course.id)
        if lang is None and maker is None:
            continue
        need = target - _existing(course)
        if need <= 0:
            continue
        added = (_program_rounds(course, lang, need) if lang is not None
                 else _document_rounds(course, maker, need))
        if added:
            course.topics = list(course.topics) + added
            course._units = None
