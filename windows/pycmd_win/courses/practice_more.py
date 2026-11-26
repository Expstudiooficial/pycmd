"""Practice rounds for the courses only the Windows build carries.

The engine (pycmd_teach.practice) makes rounds of exercises - precedence,
remainders, loops, lists, functions - and needs each language's way of
writing them. The phone's fifteen languages are in the engine; these are
the other twenty-two, plugged in by learn._engine() before the courses load.

Every exercise is run by tools/test_learn.py on the real compiler and must
print what the lesson says.
"""

from __future__ import annotations

from pycmd_teach.practice import Lang, _ind, _nums, _op, _tf


def _cap(name: str) -> str:
    return name[:1].upper() + name[1:]


def _named(p, f):
    """The vars shape with the two names put in, by a function of the name."""
    return p["shape"].format(x=f(p["n1"]), y=f(p["n2"]))


# ---------------------------------------------------------------- awk

def _awk(body: str) -> str:
    return f"BEGIN {{\n{_ind(body)}\n}}"


AWK = Lang(
    tf=_tf("1", "0"), base=1,
    arith=lambda p: _awk(f'print {p["e"]}'),
    divmod=lambda p: _awk(f'print int({p["a"]} / {p["b"]})\nprint {p["a"]} % {p["b"]}'),
    vars=lambda p: _awk(f'{p["n1"]} = {p["x"]}\n{p["n2"]} = {p["y"]}\n'
                        f'print {_named(p, str)}'),
    compare=lambda p: _awk(f'print ({p["a"]} {p["cop"]} {p["b"]})'),
    ifelse=lambda p: _awk(f'if ({p["a"]} > {p["b"]}) print "{p["w1"]}"\n'
                          f'else print "{p["w2"]}"'),
    concat=lambda p: _awk(f'print "{p["s1"]}" "{p["s2"]}"'),
    length=lambda p: _awk(f'print length("{p["s"]}")'),
    upper=lambda p: _awk(f'print toupper("{p["s"]}")'),
    loop_sum=lambda p: _awk(f'for (i = 1; i <= {p["n"]}; i++)\n    total += i * {p["k"]}\n'
                            f'print total'),
    countdown=lambda p: _awk(f'for (i = {p["n"]}; i >= 1; i--)\n    print i'),
    func=lambda p: (f'function f(x) {{\n    return x * x + {p["c"]}\n}}\n\n'
                    f'BEGIN {{\n    print f({p["a"]})\n}}'),
    list_index=lambda p: _awk(f'split("{_nums(p["xs"], " ")}", xs, " ")\n'
                              f'print xs[{p["j"]}]'),
    list_sum=lambda p: _awk(f'n = split("{_nums(p["xs"], " ")}", xs, " ")\n'
                            f'for (i = 1; i <= n; i++)\n    total += xs[i]\nprint total'),
    fact=lambda p: _awk(f'f = 1\nfor (i = 2; i <= {p["n"]}; i++)\n    f *= i\nprint f'),
    count_even=lambda p: _awk(f'for (i = 1; i <= {p["n"]}; i++)\n'
                              f'    if (i % 2 == 0) count++\nprint count'),
    max2=lambda p: _awk(f'a = {p["a"]}; b = {p["b"]}\nprint (a > b ? a : b)'),
)


# ------------------------------------------------------------ the Lisps

_LISP_OPS = {"==": "=", ">=": ">=", "<=": "<=", ">": ">", "<": "<"}


def _lisp_compare(p, true_word):
    if p["op"] == "!=":
        return f'(not (= {p["a"]} {p["b"]}))'
    return f'({_LISP_OPS[p["op"]]} {p["a"]} {p["b"]})'


def _lisp_vars(p):
    return p["pshape"].format(x=p["n1"], y=p["n2"])


CLOJURE = Lang(
    arith=lambda p: f'(println {p["pe"]})',
    divmod=lambda p: f'(println (quot {p["a"]} {p["b"]}))\n(println (rem {p["a"]} {p["b"]}))',
    vars=lambda p: (f'(def {p["n1"]} {p["x"]})\n(def {p["n2"]} {p["y"]})\n'
                    f'(println {_lisp_vars(p)})'),
    compare=lambda p: f'(println {_lisp_compare(p, "true")})',
    ifelse=lambda p: (f'(if (> {p["a"]} {p["b"]})\n  (println "{p["w1"]}")\n'
                      f'  (println "{p["w2"]}"))'),
    concat=lambda p: f'(println (str "{p["s1"]}" "{p["s2"]}"))',
    length=lambda p: f'(println (count "{p["s"]}"))',
    upper=lambda p: (f"(require '[clojure.string :as str])\n"
                     f'(println (str/upper-case "{p["s"]}"))'),
    loop_sum=lambda p: (f'(println (reduce + (map #(* % {p["k"]})\n'
                        f'                      (range 1 {p["n"] + 1}))))'),
    countdown=lambda p: f'(doseq [i (range {p["n"]} 0 -1)]\n  (println i))',
    func=lambda p: f'(defn f [x]\n  (+ (* x x) {p["c"]}))\n\n(println (f {p["a"]}))',
    list_index=lambda p: f'(def xs [{_nums(p["xs"], " ")}])\n(println (nth xs {p["j"]}))',
    list_sum=lambda p: f'(def xs [{_nums(p["xs"], " ")}])\n(println (reduce + xs))',
    fact=lambda p: f'(println (reduce * (range 1 {p["n"] + 1})))',
    count_even=lambda p: f'(println (count (filter even? (range 1 {p["n"] + 1}))))',
    max2=lambda p: f'(println (max {p["a"]} {p["b"]}))',
)


def _rkt(body: str) -> str:
    return "#lang racket\n" + body


RACKET = Lang(
    tf=_tf("#t", "#f"),
    arith=lambda p: _rkt(f'(displayln {p["pe"]})'),
    divmod=lambda p: _rkt(f'(displayln (quotient {p["a"]} {p["b"]}))\n'
                          f'(displayln (remainder {p["a"]} {p["b"]}))'),
    vars=lambda p: _rkt(f'(define {p["n1"]} {p["x"]})\n(define {p["n2"]} {p["y"]})\n'
                        f'(displayln {_lisp_vars(p)})'),
    compare=lambda p: _rkt(f'(displayln {_lisp_compare(p, "#t")})'),
    ifelse=lambda p: _rkt(f'(if (> {p["a"]} {p["b"]})\n    (displayln "{p["w1"]}")\n'
                          f'    (displayln "{p["w2"]}"))'),
    concat=lambda p: _rkt(f'(displayln (string-append "{p["s1"]}" "{p["s2"]}"))'),
    length=lambda p: _rkt(f'(displayln (string-length "{p["s"]}"))'),
    upper=lambda p: _rkt(f'(displayln (string-upcase "{p["s"]}"))'),
    loop_sum=lambda p: _rkt(f'(displayln\n (for/sum ([i (in-range 1 {p["n"] + 1})])\n'
                            f'   (* i {p["k"]})))'),
    countdown=lambda p: _rkt(f'(for ([i (in-range {p["n"]} 0 -1)])\n  (displayln i))'),
    func=lambda p: _rkt(f'(define (f x)\n  (+ (* x x) {p["c"]}))\n(displayln (f {p["a"]}))'),
    list_index=lambda p: _rkt(f'(define xs (list {_nums(p["xs"], " ")}))\n'
                              f'(displayln (list-ref xs {p["j"]}))'),
    list_sum=lambda p: _rkt(f'(define xs (list {_nums(p["xs"], " ")}))\n'
                            f'(displayln (apply + xs))'),
    fact=lambda p: _rkt(f'(displayln\n (for/product ([i (in-range 1 {p["n"] + 1})]) i))'),
    count_even=lambda p: _rkt(f'(displayln\n (length (filter even? (range 1 {p["n"] + 1}))))'),
    max2=lambda p: _rkt(f'(displayln (max {p["a"]} {p["b"]}))'),
)


def _scm(line: str) -> str:
    return f"(display {line})\n(newline)"


SCHEME = Lang(
    tf=_tf("#t", "#f"),
    arith=lambda p: _scm(p["pe"]),
    divmod=lambda p: (_scm(f'(quotient {p["a"]} {p["b"]})') + "\n"
                      + _scm(f'(remainder {p["a"]} {p["b"]})')),
    vars=lambda p: (f'(define {p["n1"]} {p["x"]})\n(define {p["n2"]} {p["y"]})\n'
                    + _scm(_lisp_vars(p))),
    compare=lambda p: _scm(_lisp_compare(p, "#t")),
    ifelse=lambda p: (f'(display (if (> {p["a"]} {p["b"]})\n'
                      f'             "{p["w1"]}"\n             "{p["w2"]}"))\n(newline)'),
    concat=lambda p: _scm(f'(string-append "{p["s1"]}" "{p["s2"]}")'),
    length=lambda p: _scm(f'(string-length "{p["s"]}")'),
    upper=lambda p: _scm(f'(string-upcase "{p["s"]}")'),
    loop_sum=lambda p: (f'(define (total i acc)\n  (if (> i {p["n"]})\n      acc\n'
                        f'      (total (+ i 1) (+ acc (* i {p["k"]})))))\n'
                        + _scm("(total 1 0)")),
    countdown=lambda p: (f'(do ((i {p["n"]} (- i 1)))\n    ((< i 1))\n'
                         f'  (display i)\n  (newline))'),
    func=lambda p: f'(define (f x)\n  (+ (* x x) {p["c"]}))\n' + _scm(f'(f {p["a"]})'),
    list_index=lambda p: (f'(define xs (list {_nums(p["xs"], " ")}))\n'
                          + _scm(f'(list-ref xs {p["j"]})')),
    list_sum=lambda p: (f'(define xs (list {_nums(p["xs"], " ")}))\n' + _scm("(apply + xs)")),
    fact=lambda p: (f'(define (fact n)\n  (if (< n 2) 1 (* n (fact (- n 1)))))\n'
                    + _scm(f'(fact {p["n"]})')),
    count_even=lambda p: (f'(define (evens i)\n  (cond ((> i {p["n"]}) 0)\n'
                          f'        ((even? i) (+ 1 (evens (+ i 1))))\n'
                          f'        (else (evens (+ i 1)))))\n' + _scm("(evens 1)")),
    max2=lambda p: _scm(f'(max {p["a"]} {p["b"]})'),
)


# ---------------------------------------------------------------- COBOL

def _cobol(storage, body):
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. P."]
    if storage:
        lines += ["DATA DIVISION.", "WORKING-STORAGE SECTION."] + storage
    lines += ["PROCEDURE DIVISION."] + ["    " + b for b in body] + ["    STOP RUN."]
    return "\n".join(lines)


def _pic(p, value):
    """PIC 9(4) shows leading zeros; PIC Z(3)9 shows spaces instead. Which
    one depends on the exercise, so both get practised."""
    if (p.get("a", 0) + p.get("n", 0)) % 2:
        return "PIC 9(4)", f"{value:04d}"
    return "PIC Z(3)9", str(value)


def _cobol_arith(p):
    pic, _ = _pic(p, 0)
    return _cobol([f"01 R {pic}."], [f'COMPUTE R = {p["e"]}.', "DISPLAY R."])


class _CobolLang(Lang):
    """COBOL's DISPLAY of a number depends on its PICture, so the answer is
    written here rather than taken as worked out."""

    def write(self, family, p):
        written = super().write(family, p)
        if written is None:
            return None
        code, out = written
        if family in ("arith", "loop_sum", "fact"):
            out = _pic(p, int(out))[1]
        elif family == "divmod":
            # Q is PIC 99, so a one-digit quotient shows a leading zero.
            quotient, remainder = out.split("\n")
            out = f"{int(quotient):02d}\n{remainder}"
        elif family == "count_even":
            out = f"{int(out):02d}"
        return code, out


def _cobol_total(p, loop, step, start):
    """T is worked out in a plain numeric field: an edited picture (Z) cannot
    be calculated with, only shown. With PIC Z(3)9 the result is MOVEd to one."""
    pic, _ = _pic(p, 0)
    storage = ["01 I PIC 99.", f"01 T PIC 9(4) VALUE {start}."]
    shown = "T"
    if pic.startswith("PIC Z"):
        storage.append(f"01 D {pic}.")
        shown = "D"
    body = [loop, f"    {step}", "END-PERFORM."]
    if shown == "D":
        body.append("MOVE T TO D.")
    body.append(f"DISPLAY {shown}.")
    return _cobol(storage, body)


COBOL = _CobolLang(
    arith=_cobol_arith,
    divmod=lambda p: _cobol(["01 Q PIC 99.", "01 M PIC 9."],
                            [f'DIVIDE {p["a"]} BY {p["b"]} GIVING Q REMAINDER M.',
                             "DISPLAY Q.", "DISPLAY M."]),
    ifelse=lambda p: _cobol(["01 A PIC 99 VALUE " + str(p["a"]) + ".",
                             "01 B PIC 99 VALUE " + str(p["b"]) + "."],
                            ["IF A > B", f'    DISPLAY "{p["w1"]}"', "ELSE",
                             f'    DISPLAY "{p["w2"]}"', "END-IF."]),
    upper=lambda p: _cobol([], [f'DISPLAY FUNCTION UPPER-CASE("{p["s"]}").']),
    loop_sum=lambda p: _cobol_total(p, f"PERFORM VARYING I FROM 1 BY 1 UNTIL I > {p['n']}",
                                    f"COMPUTE T = T + I * {p['k']}", 0),
    countdown=lambda p: _cobol(["01 I PIC 9."],
                               [f"PERFORM VARYING I FROM {p['n']} BY -1 UNTIL I < 1",
                                "    DISPLAY I", "END-PERFORM."]),
    fact=lambda p: _cobol_total(p, f"PERFORM VARYING I FROM 2 BY 1 UNTIL I > {p['n']}",
                                "COMPUTE T = T * I", 1),
    count_even=lambda p: _cobol(["01 I PIC 99.", "01 C PIC 99 VALUE 0."],
                                [f"PERFORM VARYING I FROM 1 BY 1 UNTIL I > {p['n']}",
                                 "    IF FUNCTION MOD(I, 2) = 0", "        ADD 1 TO C",
                                 "    END-IF", "END-PERFORM.", "DISPLAY C."]),
)


# ------------------------------------------------------------------ C#

CSHARP = Lang(
    tf=_tf("True", "False"),
    arith=lambda p: f'Console.WriteLine({p["e"]});',
    divmod=lambda p: (f'Console.WriteLine({p["a"]} / {p["b"]});\n'
                      f'Console.WriteLine({p["a"]} % {p["b"]});'),
    vars=lambda p: (f'int {p["n1"]} = {p["x"]};\nint {p["n2"]} = {p["y"]};\n'
                    f'Console.WriteLine({_named(p, str)});'),
    compare=lambda p: f'Console.WriteLine({p["a"]} {p["cop"]} {p["b"]});',
    ifelse=lambda p: (f'int a = {p["a"]};\nif (a > {p["b"]})\n{{\n'
                      f'    Console.WriteLine("{p["w1"]}");\n}}\nelse\n{{\n'
                      f'    Console.WriteLine("{p["w2"]}");\n}}'),
    concat=lambda p: f'Console.WriteLine("{p["s1"]}" + "{p["s2"]}");',
    length=lambda p: f'Console.WriteLine("{p["s"]}".Length);',
    upper=lambda p: f'Console.WriteLine("{p["s"]}".ToUpper());',
    loop_sum=lambda p: (f'int total = 0;\nfor (int i = 1; i <= {p["n"]}; i++)\n{{\n'
                        f'    total += i * {p["k"]};\n}}\nConsole.WriteLine(total);'),
    countdown=lambda p: (f'for (int i = {p["n"]}; i >= 1; i--)\n{{\n'
                         f'    Console.WriteLine(i);\n}}'),
    func=lambda p: (f'int F(int x) => x * x + {p["c"]};\n\n'
                    f'Console.WriteLine(F({p["a"]}));'),
    list_index=lambda p: (f'int[] xs = {{ {_nums(p["xs"])} }};\n'
                          f'Console.WriteLine(xs[{p["j"]}]);'),
    list_sum=lambda p: (f'int[] xs = {{ {_nums(p["xs"])} }};\nint total = 0;\n'
                        f'foreach (int x in xs)\n{{\n    total += x;\n}}\n'
                        f'Console.WriteLine(total);'),
    fact=lambda p: (f'int f = 1;\nfor (int i = 2; i <= {p["n"]}; i++)\n{{\n'
                    f'    f *= i;\n}}\nConsole.WriteLine(f);'),
    count_even=lambda p: (f'int count = 0;\nfor (int i = 1; i <= {p["n"]}; i++)\n{{\n'
                          f'    if (i % 2 == 0) count++;\n}}\nConsole.WriteLine(count);'),
    max2=lambda p: f'Console.WriteLine(Math.Max({p["a"]}, {p["b"]}));',
)


# ------------------------------------------------------------------- D

def _d(body: str, imports=("std.stdio",)) -> str:
    head = "\n".join(f"import {i};" for i in imports)
    return f"{head}\n\nvoid main() {{\n{_ind(body)}\n}}"


D = Lang(
    arith=lambda p: _d(f'writeln({p["e"]});'),
    divmod=lambda p: _d(f'writeln({p["a"]} / {p["b"]});\nwriteln({p["a"]} % {p["b"]});'),
    vars=lambda p: _d(f'int {p["n1"]} = {p["x"]};\nint {p["n2"]} = {p["y"]};\n'
                      f'writeln({_named(p, str)});'),
    compare=lambda p: _d(f'writeln({p["a"]} {p["cop"]} {p["b"]});'),
    ifelse=lambda p: _d(f'int a = {p["a"]};\nif (a > {p["b"]}) {{\n    writeln("{p["w1"]}");\n'
                        f'}} else {{\n    writeln("{p["w2"]}");\n}}'),
    concat=lambda p: _d(f'writeln("{p["s1"]}" ~ "{p["s2"]}");'),
    length=lambda p: _d(f'writeln("{p["s"]}".length);'),
    upper=lambda p: _d(f'writeln("{p["s"]}".toUpper);', ("std.stdio", "std.uni : toUpper")),
    loop_sum=lambda p: _d(f'int total = 0;\nforeach (i; 1 .. {p["n"] + 1}) {{\n'
                          f'    total += i * {p["k"]};\n}}\nwriteln(total);'),
    countdown=lambda p: _d(f'for (int i = {p["n"]}; i >= 1; i--) {{\n    writeln(i);\n}}'),
    func=lambda p: (f'import std.stdio;\n\nint f(int x) {{\n    return x * x + {p["c"]};\n}}\n\n'
                    f'void main() {{\n    writeln(f({p["a"]}));\n}}'),
    list_index=lambda p: _d(f'int[] xs = [{_nums(p["xs"])}];\nwriteln(xs[{p["j"]}]);'),
    list_sum=lambda p: _d(f'int[] xs = [{_nums(p["xs"])}];\nwriteln(xs.sum);',
                          ("std.stdio", "std.algorithm : sum")),
    fact=lambda p: _d(f'int f = 1;\nforeach (i; 2 .. {p["n"] + 1}) {{\n    f *= i;\n}}\n'
                      f'writeln(f);'),
    count_even=lambda p: _d(f'int count = 0;\nforeach (i; 1 .. {p["n"] + 1}) {{\n'
                            f'    if (i % 2 == 0) count++;\n}}\nwriteln(count);'),
    max2=lambda p: _d(f'writeln(max({p["a"]}, {p["b"]}));',
                      ("std.stdio", "std.algorithm : max")),
)


# -------------------------------------------------------------- Elixir

ELIXIR = Lang(
    arith=lambda p: f'IO.puts({p["e"]})',
    divmod=lambda p: f'IO.puts(div({p["a"]}, {p["b"]}))\nIO.puts(rem({p["a"]}, {p["b"]}))',
    vars=lambda p: (f'{p["n1"]} = {p["x"]}\n{p["n2"]} = {p["y"]}\n'
                    f'IO.puts({_named(p, str)})'),
    compare=lambda p: f'IO.puts({p["a"]} {p["cop"]} {p["b"]})',
    ifelse=lambda p: (f'if {p["a"]} > {p["b"]} do\n  IO.puts("{p["w1"]}")\nelse\n'
                      f'  IO.puts("{p["w2"]}")\nend'),
    concat=lambda p: f'IO.puts("{p["s1"]}" <> "{p["s2"]}")',
    length=lambda p: f'IO.puts(String.length("{p["s"]}"))',
    upper=lambda p: f'IO.puts(String.upcase("{p["s"]}"))',
    loop_sum=lambda p: (f'total = Enum.reduce(1..{p["n"]}, 0, fn i, acc ->\n'
                        f'  acc + i * {p["k"]}\nend)\nIO.puts(total)'),
    countdown=lambda p: (f'1..{p["n"]}\n|> Enum.reverse()\n|> Enum.each(&IO.puts/1)'),
    func=lambda p: (f'defmodule M do\n  def f(x), do: x * x + {p["c"]}\nend\n\n'
                    f'IO.puts(M.f({p["a"]}))'),
    list_index=lambda p: f'xs = [{_nums(p["xs"])}]\nIO.puts(Enum.at(xs, {p["j"]}))',
    list_sum=lambda p: f'xs = [{_nums(p["xs"])}]\nIO.puts(Enum.sum(xs))',
    fact=lambda p: f'IO.puts(Enum.reduce(1..{p["n"]}, 1, &*/2))',
    count_even=lambda p: f'IO.puts(Enum.count(1..{p["n"]}, &(rem(&1, 2) == 0)))',
    max2=lambda p: f'IO.puts(max({p["a"]}, {p["b"]}))',
)


# -------------------------------------------------------------- Erlang

def _erl(body: str) -> str:
    lines = body.split("\n")
    return "main(_) ->\n" + "\n".join("    " + line for line in lines) + "."


def _fmt(expr: str) -> str:
    return f'io:format("~p~n", [{expr}])'


ERLANG = Lang(
    op=_op({"<=": "=<", "==": "=:=", "!=": "=/="}), base=1,
    arith=lambda p: _erl(_fmt(p["e"])),
    divmod=lambda p: _erl(_fmt(f'{p["a"]} div {p["b"]}') + ",\n"
                          + _fmt(f'{p["a"]} rem {p["b"]}')),
    vars=lambda p: _erl(f'{_cap(p["n1"])} = {p["x"]},\n{_cap(p["n2"])} = {p["y"]},\n'
                        + _fmt(_named(p, _cap))),
    compare=lambda p: _erl(_fmt(f'{p["a"]} {p["cop"]} {p["b"]}')),
    ifelse=lambda p: _erl(f'A = {p["a"]},\ncase A > {p["b"]} of\n'
                          f'    true -> io:format("{p["w1"]}~n");\n'
                          f'    false -> io:format("{p["w2"]}~n")\nend'),
    concat=lambda p: _erl(f'io:format("~s~n", ["{p["s1"]}" ++ "{p["s2"]}"])'),
    length=lambda p: _erl(_fmt(f'length("{p["s"]}")')),
    upper=lambda p: _erl(f'io:format("~s~n", [string:uppercase("{p["s"]}")])'),
    loop_sum=lambda p: _erl(f'Total = lists:sum([I * {p["k"]} || I <- lists:seq(1, {p["n"]})]),\n'
                            + _fmt("Total")),
    countdown=lambda p: _erl(f'lists:foreach(fun(I) -> {_fmt("I")} end,\n'
                             f'              lists:seq({p["n"]}, 1, -1))'),
    func=lambda p: (f'f(X) -> X * X + {p["c"]}.\n\n' + _erl(_fmt(f'f({p["a"]})'))),
    list_index=lambda p: _erl(f'Xs = [{_nums(p["xs"])}],\n' + _fmt(f'lists:nth({p["j"]}, Xs)')),
    list_sum=lambda p: _erl(f'Xs = [{_nums(p["xs"])}],\n' + _fmt("lists:sum(Xs)")),
    fact=lambda p: _erl(f'F = lists:foldl(fun(I, Acc) -> I * Acc end, 1,\n'
                        f'                lists:seq(1, {p["n"]})),\n' + _fmt("F")),
    count_even=lambda p: _erl(f'Evens = [I || I <- lists:seq(1, {p["n"]}), I rem 2 =:= 0],\n'
                              + _fmt("length(Evens)")),
    max2=lambda p: _erl(_fmt(f'max({p["a"]}, {p["b"]})')),
)


# ------------------------------------------------------------- Fortran

def _f90(decls, body):
    lines = ["program main", "  implicit none"] + ["  " + d for d in decls]
    lines += ["  " + b for b in body] + ["end program main"]
    return "\n".join(lines)


FORTRAN = Lang(
    tf=_tf("T", "F"), op=_op({"!=": "/="}), base=1,
    arith=lambda p: _f90([], [f'print *, {p["e"]}']),
    divmod=lambda p: _f90([], [f'print *, {p["a"]} / {p["b"]}',
                               f'print *, mod({p["a"]}, {p["b"]})']),
    vars=lambda p: _f90([f'integer :: {p["n1"]}, {p["n2"]}'],
                        [f'{p["n1"]} = {p["x"]}', f'{p["n2"]} = {p["y"]}',
                         f'print *, {_named(p, str)}']),
    compare=lambda p: _f90([], [f'print *, ({p["a"]} {p["cop"]} {p["b"]})']),
    ifelse=lambda p: _f90(["integer :: a"], [f'a = {p["a"]}', f'if (a > {p["b"]}) then',
                                            f"  print *, '{p['w1']}'", "else",
                                            f"  print *, '{p['w2']}'", "end if"]),
    concat=lambda p: _f90([], [f"print *, '{p['s1']}' // '{p['s2']}'"]),
    length=lambda p: _f90([], [f"print *, len('{p['s']}')"]),
    loop_sum=lambda p: _f90(["integer :: i, total"],
                            ["total = 0", f'do i = 1, {p["n"]}',
                             f'  total = total + i * {p["k"]}', "end do", "print *, total"]),
    countdown=lambda p: _f90(["integer :: i"], [f'do i = {p["n"]}, 1, -1', "  print *, i",
                                               "end do"]),
    func=lambda p: "\n".join(["program main", "  implicit none", f'  print *, f({p["a"]})',
                              "contains", "  integer function f(x)",
                              "    integer, intent(in) :: x",
                              f'    f = x * x + {p["c"]}', "  end function f",
                              "end program main"]),
    list_index=lambda p: _f90([f'integer :: xs({len(p["xs"])}) = [{_nums(p["xs"])}]'],
                              [f'print *, xs({p["j"]})']),
    list_sum=lambda p: _f90([f'integer :: xs({len(p["xs"])}) = [{_nums(p["xs"])}]'],
                            ["print *, sum(xs)"]),
    fact=lambda p: _f90(["integer :: i, f"], ["f = 1", f'do i = 2, {p["n"]}', "  f = f * i",
                                             "end do", "print *, f"]),
    count_even=lambda p: _f90(["integer :: i, c"],
                              ["c = 0", f'do i = 1, {p["n"]}',
                               "  if (mod(i, 2) == 0) c = c + 1", "end do", "print *, c"]),
    max2=lambda p: _f90([], [f'print *, max({p["a"]}, {p["b"]})']),
)


# ------------------------------------------------------------------ F#

FSHARP = Lang(
    op=_op({"==": "=", "!=": "<>"}),
    arith=lambda p: f'printfn "%d" ({p["e"]})',
    divmod=lambda p: f'printfn "%d" ({p["a"]} / {p["b"]})\nprintfn "%d" ({p["a"]} % {p["b"]})',
    vars=lambda p: (f'let {p["n1"]} = {p["x"]}\nlet {p["n2"]} = {p["y"]}\n'
                    f'printfn "%d" ({_named(p, str)})'),
    compare=lambda p: f'printfn "%b" ({p["a"]} {p["cop"]} {p["b"]})',
    ifelse=lambda p: (f'let a = {p["a"]}\nif a > {p["b"]} then\n    printfn "{p["w1"]}"\n'
                      f'else\n    printfn "{p["w2"]}"'),
    concat=lambda p: f'printfn "%s" ("{p["s1"]}" + "{p["s2"]}")',
    length=lambda p: f'printfn "%d" (String.length "{p["s"]}")',
    upper=lambda p: f'printfn "%s" ("{p["s"]}".ToUpper())',
    loop_sum=lambda p: (f'let mutable total = 0\nfor i in 1 .. {p["n"]} do\n'
                        f'    total <- total + i * {p["k"]}\nprintfn "%d" total'),
    countdown=lambda p: f'for i in {p["n"]} .. -1 .. 1 do\n    printfn "%d" i',
    func=lambda p: f'let f x = x * x + {p["c"]}\n\nprintfn "%d" (f {p["a"]})',
    list_index=lambda p: f'let xs = [{_nums(p["xs"], "; ")}]\nprintfn "%d" (List.item {p["j"]} xs)',
    list_sum=lambda p: f'let xs = [{_nums(p["xs"], "; ")}]\nprintfn "%d" (List.sum xs)',
    fact=lambda p: f'printfn "%d" (List.fold (*) 1 [1 .. {p["n"]}])',
    count_even=lambda p: (f'[1 .. {p["n"]}]\n|> List.filter (fun i -> i % 2 = 0)\n'
                          f'|> List.length\n|> printfn "%d"'),
    max2=lambda p: f'printfn "%d" (max {p["a"]} {p["b"]})',
)


# -------------------------------------------------------------- Groovy

GROOVY = Lang(
    arith=lambda p: f'println({p["e"]})',
    divmod=lambda p: f'println({p["a"]}.intdiv({p["b"]}))\nprintln({p["a"]} % {p["b"]})',
    vars=lambda p: (f'def {p["n1"]} = {p["x"]}\ndef {p["n2"]} = {p["y"]}\n'
                    f'println({_named(p, str)})'),
    compare=lambda p: f'println({p["a"]} {p["cop"]} {p["b"]})',
    ifelse=lambda p: (f'def a = {p["a"]}\nif (a > {p["b"]}) {{\n    println "{p["w1"]}"\n'
                      f'}} else {{\n    println "{p["w2"]}"\n}}'),
    concat=lambda p: f'println("{p["s1"]}" + "{p["s2"]}")',
    length=lambda p: f'println("{p["s"]}".length())',
    upper=lambda p: f'println("{p["s"]}".toUpperCase())',
    loop_sum=lambda p: (f'def total = 0\nfor (i in 1..{p["n"]}) {{\n'
                        f'    total += i * {p["k"]}\n}}\nprintln(total)'),
    countdown=lambda p: f'{p["n"]}.downto(1) {{\n    println it\n}}',
    func=lambda p: f'def f(x) {{\n    x * x + {p["c"]}\n}}\n\nprintln(f({p["a"]}))',
    list_index=lambda p: f'def xs = [{_nums(p["xs"])}]\nprintln(xs[{p["j"]}])',
    list_sum=lambda p: f'def xs = [{_nums(p["xs"])}]\nprintln(xs.sum())',
    fact=lambda p: f'println((1..{p["n"]}).inject(1) {{ a, b -> a * b }})',
    count_even=lambda p: f'println((1..{p["n"]}).count {{ it % 2 == 0 }})',
    max2=lambda p: f'println(Math.max({p["a"]}, {p["b"]}))',
)


# ------------------------------------------------------------- Haskell

HASKELL = Lang(
    tf=_tf("True", "False"), op=_op({"!=": "/="}),
    arith=lambda p: f'main = print ({p["e"]})',
    divmod=lambda p: (f'main = do\n  print ({p["a"]} `div` {p["b"]})\n'
                      f'  print ({p["a"]} `mod` {p["b"]})'),
    vars=lambda p: (f'main = do\n  let {p["n1"]} = {p["x"]}\n      {p["n2"]} = {p["y"]}\n'
                    f'  print ({_named(p, str)})'),
    compare=lambda p: f'main = print ({p["a"]} {p["cop"]} {p["b"]})',
    ifelse=lambda p: (f'main = putStrLn (if a > {p["b"]} then "{p["w1"]}" else "{p["w2"]}")\n'
                      f'  where a = {p["a"]}'),
    concat=lambda p: f'main = putStrLn ("{p["s1"]}" ++ "{p["s2"]}")',
    length=lambda p: f'main = print (length "{p["s"]}")',
    upper=lambda p: f'import Data.Char (toUpper)\n\nmain = putStrLn (map toUpper "{p["s"]}")',
    loop_sum=lambda p: f'main = print (sum [i * {p["k"]} | i <- [1 .. {p["n"]}]])',
    countdown=lambda p: f'main = mapM_ print [{p["n"]}, {p["n"] - 1} .. 1]',
    func=lambda p: (f'f :: Int -> Int\nf x = x * x + {p["c"]}\n\nmain = print (f {p["a"]})'),
    list_index=lambda p: f'xs :: [Int]\nxs = [{_nums(p["xs"])}]\n\nmain = print (xs !! {p["j"]})',
    list_sum=lambda p: f'xs :: [Int]\nxs = [{_nums(p["xs"])}]\n\nmain = print (sum xs)',
    fact=lambda p: f'main = print (product [1 .. {p["n"]}])',
    count_even=lambda p: f'main = print (length (filter even [1 .. {p["n"]}]))',
    max2=lambda p: f'main = print (max {p["a"]} {p["b"]})',
)


# ----------------------------------------------------------------- Nim

NIM = Lang(
    arith=lambda p: f'echo {p["e"]}',
    divmod=lambda p: f'echo {p["a"]} div {p["b"]}\necho {p["a"]} mod {p["b"]}',
    vars=lambda p: (f'let {p["n1"]} = {p["x"]}\nlet {p["n2"]} = {p["y"]}\n'
                    f'echo {_named(p, str)}'),
    compare=lambda p: f'echo({p["a"]} {p["cop"]} {p["b"]})',
    ifelse=lambda p: (f'let a = {p["a"]}\nif a > {p["b"]}:\n  echo "{p["w1"]}"\nelse:\n'
                      f'  echo "{p["w2"]}"'),
    concat=lambda p: f'echo "{p["s1"]}" & "{p["s2"]}"',
    length=lambda p: f'echo len("{p["s"]}")',
    upper=lambda p: f'import std/strutils\n\necho toUpperAscii("{p["s"]}")',
    loop_sum=lambda p: (f'var total = 0\nfor i in 1 .. {p["n"]}:\n  total += i * {p["k"]}\n'
                        f'echo total'),
    countdown=lambda p: f'for i in countdown({p["n"]}, 1):\n  echo i',
    func=lambda p: f'proc f(x: int): int =\n  x * x + {p["c"]}\n\necho f({p["a"]})',
    list_index=lambda p: f'let xs = [{_nums(p["xs"])}]\necho xs[{p["j"]}]',
    list_sum=lambda p: f'import std/math\n\nlet xs = [{_nums(p["xs"])}]\necho sum(xs)',
    fact=lambda p: f'var f = 1\nfor i in 2 .. {p["n"]}:\n  f *= i\necho f',
    count_even=lambda p: (f'var count = 0\nfor i in 1 .. {p["n"]}:\n  if i mod 2 == 0:\n'
                          f'    inc count\necho count'),
    max2=lambda p: f'echo max({p["a"]}, {p["b"]})',
)


# --------------------------------------------------------------- OCaml

def _pi(expr: str) -> str:
    return 'Printf.printf "%d\\n" (' + expr + ")"


def _ml_divmod(p):
    a, b = p["a"], p["b"]
    return f"let () =\n  {_pi(f'{a} / {b}')};\n  {_pi(f'{a} mod {b}')}"


def _ml_call(p, call):
    return f"let () = {_pi(call)}"


OCAML = Lang(
    op=_op({"==": "=", "!=": "<>"}),
    arith=lambda p: f'let () = {_pi(p["e"])}',
    divmod=_ml_divmod,
    vars=lambda p: (f'let {p["n1"]} = {p["x"]}\nlet {p["n2"]} = {p["y"]}\n'
                    f'let () = {_pi(_named(p, str))}'),
    compare=lambda p: (f'let () =\n  print_endline\n'
                       f'    (string_of_bool ({p["a"]} {p["cop"]} {p["b"]}))'),
    ifelse=lambda p: (f'let a = {p["a"]}\nlet () =\n'
                      f'  if a > {p["b"]} then print_endline "{p["w1"]}"\n'
                      f'  else print_endline "{p["w2"]}"'),
    concat=lambda p: f'let () = print_endline ("{p["s1"]}" ^ "{p["s2"]}")',
    length=lambda p: _ml_call(p, 'String.length "' + p["s"] + '"'),
    upper=lambda p: f'let () = print_endline (String.uppercase_ascii "{p["s"]}")',
    loop_sum=lambda p: (f'let () =\n  let total = ref 0 in\n  for i = 1 to {p["n"]} do\n'
                        f'    total := !total + i * {p["k"]}\n  done;\n  {_pi("!total")}'),
    countdown=lambda p: f'let () =\n  for i = {p["n"]} downto 1 do\n    {_pi("i")}\n  done',
    func=lambda p: f'let f x = x * x + {p["c"]}\n\n' + _ml_call(p, f'f {p["a"]}'),
    list_index=lambda p: (f'let xs = [{_nums(p["xs"], "; ")}]\n'
                          + _ml_call(p, f'List.nth xs {p["j"]}')),
    list_sum=lambda p: (f'let xs = [{_nums(p["xs"], "; ")}]\n'
                        + _ml_call(p, "List.fold_left ( + ) 0 xs")),
    fact=lambda p: ('let rec fact n = if n < 2 then 1 else n * fact (n - 1)\n\n'
                    + _ml_call(p, f'fact {p["n"]}')),
    count_even=lambda p: (f'let () =\n  let count = ref 0 in\n  for i = 1 to {p["n"]} do\n'
                          f'    if i mod 2 = 0 then incr count\n  done;\n  {_pi("!count")}'),
    max2=lambda p: _ml_call(p, f'max {p["a"]} {p["b"]}'),
)


# -------------------------------------------------------------- Pascal

def _pas(body, decls=()):
    lines = ["program Practice;"]
    if decls:
        lines += ["var"] + ["  " + d for d in decls]
    lines += ["begin"] + ["  " + b for b in body] + ["end."]
    return "\n".join(lines)


PASCAL = Lang(
    tf=_tf("TRUE", "FALSE"), op=_op({"==": "=", "!=": "<>"}), base=1,
    arith=lambda p: _pas([f'writeln({p["e"]});']),
    divmod=lambda p: _pas([f'writeln({p["a"]} div {p["b"]});',
                           f'writeln({p["a"]} mod {p["b"]});']),
    vars=lambda p: _pas([f'{p["n1"]} := {p["x"]};', f'{p["n2"]} := {p["y"]};',
                         f'writeln({_named(p, str)});'],
                        [f'{p["n1"]}, {p["n2"]}: integer;']),
    compare=lambda p: _pas([f'writeln({p["a"]} {p["cop"]} {p["b"]});']),
    ifelse=lambda p: _pas([f'a := {p["a"]};', f'if a > {p["b"]} then',
                           f"  writeln('{p['w1']}')", "else", f"  writeln('{p['w2']}');"],
                          ["a: integer;"]),
    concat=lambda p: _pas([f"writeln('{p['s1']}' + '{p['s2']}');"]),
    length=lambda p: _pas([f"writeln(length('{p['s']}'));"]),
    upper=lambda p: _pas([f"writeln(upcase('{p['s']}'));"]),
    loop_sum=lambda p: _pas(["total := 0;", f'for i := 1 to {p["n"]} do',
                             f'  total := total + i * {p["k"]};', "writeln(total);"],
                            ["i, total: integer;"]),
    countdown=lambda p: _pas([f'for i := {p["n"]} downto 1 do', "  writeln(i);"],
                             ["i: integer;"]),
    func=lambda p: "\n".join(["program Practice;", "", "function f(x: integer): integer;",
                              "begin", f'  f := x * x + {p["c"]};', "end;", "", "begin",
                              f'  writeln(f({p["a"]}));', "end."]),
    list_index=lambda p: "\n".join(["program Practice;", "const",
                                    f'  xs: array[1..{len(p["xs"])}] of integer =',
                                    f'    ({_nums(p["xs"])});', "begin",
                                    f'  writeln(xs[{p["j"]}]);', "end."]),
    fact=lambda p: _pas(["f := 1;", f'for i := 2 to {p["n"]} do', "  f := f * i;",
                         "writeln(f);"], ["i, f: integer;"]),
    count_even=lambda p: _pas(["c := 0;", f'for i := 1 to {p["n"]} do',
                               "  if i mod 2 = 0 then c := c + 1;", "writeln(c);"],
                              ["i, c: integer;"]),
    max2=lambda p: _pas([f'a := {p["a"]};', f'b := {p["b"]};',
                         "if a > b then writeln(a) else writeln(b);"], ["a, b: integer;"]),
)


# ---------------------------------------------------------------- Perl

PERL = Lang(
    # print(...) with the whole list in brackets: `print (3 + 4) * 2` is
    # print(3 + 4), times two, thrown away - Perl's best-known trap.
    arith=lambda p: f'print({p["e"]}, "\\n");',
    divmod=lambda p: (f'print int({p["a"]} / {p["b"]}), "\\n";\n'
                      f'print {p["a"]} % {p["b"]}, "\\n";'),
    vars=lambda p: (f'my ${p["n1"]} = {p["x"]};\nmy ${p["n2"]} = {p["y"]};\n'
                    f'print({_named(p, lambda n: "$" + n)}, "\\n");'),
    compare=lambda p: f'print(({p["a"]} {p["cop"]} {p["b"]}) ? "true" : "false", "\\n");',
    ifelse=lambda p: (f'my $a = {p["a"]};\nif ($a > {p["b"]}) {{\n    print "{p["w1"]}\\n";\n'
                      f'}} else {{\n    print "{p["w2"]}\\n";\n}}'),
    concat=lambda p: f'print "{p["s1"]}" . "{p["s2"]}", "\\n";',
    length=lambda p: f'print length("{p["s"]}"), "\\n";',
    upper=lambda p: f'print uc("{p["s"]}"), "\\n";',
    loop_sum=lambda p: (f'my $total = 0;\nfor my $i (1 .. {p["n"]}) {{\n'
                        f'    $total += $i * {p["k"]};\n}}\nprint "$total\\n";'),
    countdown=lambda p: f'for my $i (reverse 1 .. {p["n"]}) {{\n    print "$i\\n";\n}}',
    func=lambda p: (f'sub f {{\n    my ($x) = @_;\n    return $x * $x + {p["c"]};\n}}\n\n'
                    f'print f({p["a"]}), "\\n";'),
    list_index=lambda p: f'my @xs = ({_nums(p["xs"])});\nprint $xs[{p["j"]}], "\\n";',
    list_sum=lambda p: (f'use List::Util qw(sum);\n\nmy @xs = ({_nums(p["xs"])});\n'
                        f'print sum(@xs), "\\n";'),
    fact=lambda p: (f'my $f = 1;\n$f *= $_ for 2 .. {p["n"]};\nprint "$f\\n";'),
    count_even=lambda p: (f'my $count = grep {{ $_ % 2 == 0 }} 1 .. {p["n"]};\n'
                          f'print "$count\\n";'),
    max2=lambda p: f'use List::Util qw(max);\n\nprint max({p["a"]}, {p["b"]}), "\\n";',
)


# ---------------------------------------------------------- PowerShell

_PS_OPS = {">": "-gt", "<": "-lt", ">=": "-ge", "<=": "-le", "==": "-eq", "!=": "-ne"}

POWERSHELL = Lang(
    tf=_tf("True", "False"), op=_op(_PS_OPS),
    arith=lambda p: f'Write-Output ({p["e"]})',
    divmod=lambda p: (f'Write-Output ([math]::Floor({p["a"]} / {p["b"]}))\n'
                      f'Write-Output ({p["a"]} % {p["b"]})'),
    vars=lambda p: (f'${p["n1"]} = {p["x"]}\n${p["n2"]} = {p["y"]}\n'
                    f'Write-Output ({_named(p, lambda n: "$" + n)})'),
    compare=lambda p: f'Write-Output ({p["a"]} {p["cop"]} {p["b"]})',
    ifelse=lambda p: (f'$a = {p["a"]}\nif ($a -gt {p["b"]}) {{\n    "{p["w1"]}"\n'
                      f'}} else {{\n    "{p["w2"]}"\n}}'),
    concat=lambda p: f'Write-Output ("{p["s1"]}" + "{p["s2"]}")',
    length=lambda p: f'Write-Output "{p["s"]}".Length',
    upper=lambda p: f'Write-Output "{p["s"]}".ToUpper()',
    loop_sum=lambda p: (f'$total = 0\nforeach ($i in 1..{p["n"]}) {{\n'
                        f'    $total += $i * {p["k"]}\n}}\nWrite-Output $total'),
    countdown=lambda p: f'foreach ($i in {p["n"]}..1) {{\n    Write-Output $i\n}}',
    func=lambda p: (f'function F($x) {{\n    $x * $x + {p["c"]}\n}}\n\nWrite-Output (F {p["a"]})'),
    list_index=lambda p: f'$xs = @({_nums(p["xs"])})\nWrite-Output $xs[{p["j"]}]',
    list_sum=lambda p: (f'$xs = @({_nums(p["xs"])})\n'
                        f'($xs | Measure-Object -Sum).Sum'),
    fact=lambda p: (f'$f = 1\nforeach ($i in 2..{p["n"]}) {{\n    $f *= $i\n}}\n'
                    f'Write-Output $f'),
    count_even=lambda p: f'(1..{p["n"]} | Where-Object {{ $_ % 2 -eq 0 }}).Count',
    max2=lambda p: f'Write-Output ([math]::Max({p["a"]}, {p["b"]}))',
)


# -------------------------------------------------------------- Prolog

_PL_OPS = {"<=": "=<", "==": "=:=", "!=": "=\\="}


def _pl(goals) -> str:
    return "main :-\n" + ",\n".join("    " + g for g in goals) + "."


PROLOG = Lang(
    op=_op(_PL_OPS),
    arith=lambda p: _pl([f'X is {p["e"]}', "writeln(X)"]),
    divmod=lambda p: _pl([f'Q is {p["a"]} // {p["b"]}', f'R is {p["a"]} mod {p["b"]}',
                          "writeln(Q)", "writeln(R)"]),
    vars=lambda p: _pl([f'{_cap(p["n1"])} = {p["x"]}', f'{_cap(p["n2"])} = {p["y"]}',
                        f'X is {_named(p, _cap)}', "writeln(X)"]),
    compare=lambda p: _pl([f'( {p["a"]} {p["cop"]} {p["b"]} -> writeln(true)'
                           f' ; writeln(false) )']),
    ifelse=lambda p: _pl([f'( {p["a"]} > {p["b"]} -> writeln(\'{p["w1"]}\')'
                          f' ; writeln(\'{p["w2"]}\') )']),
    concat=lambda p: _pl([f'string_concat("{p["s1"]}", "{p["s2"]}", S)', "writeln(S)"]),
    length=lambda p: _pl([f'string_length("{p["s"]}", N)', "writeln(N)"]),
    upper=lambda p: _pl([f'string_upper("{p["s"]}", U)', "writeln(U)"]),
    loop_sum=lambda p: _pl([f'findall(T, (between(1, {p["n"]}, I), T is I * {p["k"]}), Ts)',
                            "sum_list(Ts, S)", "writeln(S)"]),
    countdown=lambda p: _pl([f'forall(between(1, {p["n"]}, I),\n'
                             f'           ( J is {p["n"] + 1} - I, writeln(J) ))']),
    func=lambda p: (f'f(X, Y) :- Y is X * X + {p["c"]}.\n\n'
                    + _pl([f'f({p["a"]}, Y)', "writeln(Y)"])),
    list_index=lambda p: _pl([f'nth0({p["j"]}, [{_nums(p["xs"])}], X)', "writeln(X)"]),
    list_sum=lambda p: _pl([f'sum_list([{_nums(p["xs"])}], S)', "writeln(S)"]),
    fact=lambda p: (f'fact(0, 1) :- !.\nfact(N, F) :- M is N - 1, fact(M, G), F is N * G.\n\n'
                    + _pl([f'fact({p["n"]}, F)', "writeln(F)"])),
    count_even=lambda p: _pl([f'aggregate_all(count,\n'
                              f'        (between(1, {p["n"]}, I), I mod 2 =:= 0), C)',
                              "writeln(C)"]),
    max2=lambda p: _pl([f'X is max({p["a"]}, {p["b"]})', "writeln(X)"]),
)


# ------------------------------------------------------------------- R

R = Lang(
    tf=_tf("TRUE", "FALSE"), base=1,
    arith=lambda p: f'cat({p["e"]}, "\\n")',
    divmod=lambda p: f'cat({p["a"]} %/% {p["b"]}, "\\n")\ncat({p["a"]} %% {p["b"]}, "\\n")',
    vars=lambda p: (f'{p["n1"]} <- {p["x"]}\n{p["n2"]} <- {p["y"]}\n'
                    f'cat({_named(p, str)}, "\\n")'),
    compare=lambda p: f'cat({p["a"]} {p["cop"]} {p["b"]}, "\\n")',
    ifelse=lambda p: (f'a <- {p["a"]}\nif (a > {p["b"]}) {{\n  cat("{p["w1"]}\\n")\n'
                      f'}} else {{\n  cat("{p["w2"]}\\n")\n}}'),
    concat=lambda p: f'cat(paste0("{p["s1"]}", "{p["s2"]}"), "\\n")',
    length=lambda p: f'cat(nchar("{p["s"]}"), "\\n")',
    upper=lambda p: f'cat(toupper("{p["s"]}"), "\\n")',
    loop_sum=lambda p: (f'total <- 0\nfor (i in 1:{p["n"]}) {{\n'
                        f'  total <- total + i * {p["k"]}\n}}\ncat(total, "\\n")'),
    countdown=lambda p: f'for (i in {p["n"]}:1) {{\n  cat(i, "\\n")\n}}',
    func=lambda p: f'f <- function(x) x * x + {p["c"]}\n\ncat(f({p["a"]}), "\\n")',
    list_index=lambda p: f'xs <- c({_nums(p["xs"])})\ncat(xs[{p["j"]}], "\\n")',
    list_sum=lambda p: f'xs <- c({_nums(p["xs"])})\ncat(sum(xs), "\\n")',
    fact=lambda p: f'cat(prod(1:{p["n"]}), "\\n")',
    count_even=lambda p: f'cat(sum(1:{p["n"]} %% 2 == 0), "\\n")',
    max2=lambda p: f'cat(max({p["a"]}, {p["b"]}), "\\n")',
)


# --------------------------------------------------------------- Scala

def _scala(body: str) -> str:
    return ("object Main {\n  def main(args: Array[String]): Unit = {\n"
            f"{_ind(body, 4)}\n  }}\n}}")


SCALA = Lang(
    arith=lambda p: _scala(f'println({p["e"]})'),
    divmod=lambda p: _scala(f'println({p["a"]} / {p["b"]})\nprintln({p["a"]} % {p["b"]})'),
    vars=lambda p: _scala(f'val {p["n1"]} = {p["x"]}\nval {p["n2"]} = {p["y"]}\n'
                          f'println({_named(p, str)})'),
    compare=lambda p: _scala(f'println({p["a"]} {p["cop"]} {p["b"]})'),
    ifelse=lambda p: _scala(f'val a = {p["a"]}\nif (a > {p["b"]}) println("{p["w1"]}")\n'
                            f'else println("{p["w2"]}")'),
    concat=lambda p: _scala(f'println("{p["s1"]}" + "{p["s2"]}")'),
    length=lambda p: _scala(f'println("{p["s"]}".length)'),
    upper=lambda p: _scala(f'println("{p["s"]}".toUpperCase)'),
    loop_sum=lambda p: _scala(f'var total = 0\nfor (i <- 1 to {p["n"]}) {{\n'
                              f'  total += i * {p["k"]}\n}}\nprintln(total)'),
    countdown=lambda p: _scala(f'for (i <- {p["n"]} to 1 by -1) {{\n  println(i)\n}}'),
    func=lambda p: ("object Main {\n" f'  def f(x: Int): Int = x * x + {p["c"]}\n\n'
                    "  def main(args: Array[String]): Unit = {\n"
                    f'    println(f({p["a"]}))\n  }}\n}}'),
    list_index=lambda p: _scala(f'val xs = List({_nums(p["xs"])})\nprintln(xs({p["j"]}))'),
    list_sum=lambda p: _scala(f'val xs = List({_nums(p["xs"])})\nprintln(xs.sum)'),
    fact=lambda p: _scala(f'println((1 to {p["n"]}).product)'),
    count_even=lambda p: _scala(f'println((1 to {p["n"]}).count(_ % 2 == 0))'),
    max2=lambda p: _scala(f'println(math.max({p["a"]}, {p["b"]}))'),
)


# ----------------------------------------------------------------- Tcl

TCL = Lang(
    tf=_tf("1", "0"),
    arith=lambda p: f'puts [expr {{{p["e"]}}}]',
    divmod=lambda p: f'puts [expr {{{p["a"]} / {p["b"]}}}]\nputs [expr {{{p["a"]} % {p["b"]}}}]',
    vars=lambda p: (f'set {p["n1"]} {p["x"]}\nset {p["n2"]} {p["y"]}\n'
                    f'puts [expr {{{_named(p, lambda n: "$" + n)}}}]'),
    compare=lambda p: f'puts [expr {{{p["a"]} {p["cop"]} {p["b"]}}}]',
    ifelse=lambda p: (f'set a {p["a"]}\nif {{$a > {p["b"]}}} {{\n    puts {p["w1"]}\n'
                      f'}} else {{\n    puts {p["w2"]}\n}}'),
    concat=lambda p: f'set s {p["s1"]}\nappend s {p["s2"]}\nputs $s',
    length=lambda p: f'puts [string length "{p["s"]}"]',
    upper=lambda p: f'puts [string toupper "{p["s"]}"]',
    loop_sum=lambda p: (f'set total 0\nfor {{set i 1}} {{$i <= {p["n"]}}} {{incr i}} {{\n'
                        f'    incr total [expr {{$i * {p["k"]}}}]\n}}\nputs $total'),
    countdown=lambda p: (f'for {{set i {p["n"]}}} {{$i >= 1}} {{incr i -1}} {{\n'
                         f'    puts $i\n}}'),
    func=lambda p: (f'proc f {{x}} {{\n    return [expr {{$x * $x + {p["c"]}}}]\n}}\n\n'
                    f'puts [f {p["a"]}]'),
    list_index=lambda p: f'set xs {{{_nums(p["xs"], " ")}}}\nputs [lindex $xs {p["j"]}]',
    list_sum=lambda p: f'set xs {{{_nums(p["xs"], " ")}}}\nputs [tcl::mathop::+ {{*}}$xs]',
    fact=lambda p: (f'set f 1\nfor {{set i 2}} {{$i <= {p["n"]}}} {{incr i}} {{\n'
                    f'    set f [expr {{$f * $i}}]\n}}\nputs $f'),
    count_even=lambda p: (f'set count 0\nfor {{set i 1}} {{$i <= {p["n"]}}} {{incr i}} {{\n'
                          f'    if {{$i % 2 == 0}} {{incr count}}\n}}\nputs $count'),
    max2=lambda p: f'puts [expr {{max({p["a"]}, {p["b"]})}}]',
)


LANGS = {
    "awk": AWK, "clojure": CLOJURE, "cobol": COBOL, "csharp": CSHARP, "d": D,
    "elixir": ELIXIR, "erlang": ERLANG, "fortran": FORTRAN, "fsharp": FSHARP,
    "groovy": GROOVY, "haskell": HASKELL, "nim": NIM, "ocaml": OCAML, "pascal": PASCAL,
    "perl": PERL, "powershell": POWERSHELL, "prolog": PROLOG, "r": R, "racket": RACKET,
    "scala": SCALA, "scheme": SCHEME, "tcl": TCL,
}
