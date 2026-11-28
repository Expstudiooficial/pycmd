"""PyCmd -> Python source, checked on the way.

Before a line runs, the compiler has already refused:
  * a name that was never declared (with a "did you mean" suggestion),
  * a name used before its declaration in the same function,
  * a change to a ``let`` (only ``var`` changes), a loop variable, a fn or a struct,
  * ``break``/``continue`` outside a loop, ``return`` outside a fn,
  * a declaration that repeats a name in the same block,
  * an unknown type in an annotation, an unknown library.

What it writes is plain Python with every name controlled: the program runs
with no Python built-ins at all, only what pcmd_runtime hands it.
"""

from __future__ import annotations

import difflib
import keyword

from .pcmd_lexer import PcmdSyntaxError
from .pcmd_parser import Node
from . import pcmd_runtime as rt

BUILTIN_TYPES = {"int", "float", "num", "str", "bool", "list", "map", "set", "tuple", "fn",
                 "any", "nil", "range", "Error"}


def pyname_of(name: str) -> str:
    if keyword.iskeyword(name):
        return name + "_"
    return name


class Binding:
    __slots__ = ("name", "py", "mutable", "kind", "type", "line", "func", "live", "alias",
                 "info")

    def __init__(self, name, py, mutable, kind, line, func, type_=None, live=True, alias=None,
                 info=None):
        self.name = name
        self.py = py
        self.mutable = mutable
        self.kind = kind
        self.type = type_
        self.line = line
        self.func = func
        self.live = live
        self.alias = alias      # an expression this name stands for (match bindings)
        self.info = info        # struct: its field list


class Func:
    def __init__(self, parent, kind, ret=None, name=""):
        self.parent = parent
        self.kind = kind        # main, fn, method, lambda, test
        self.ret = ret
        self.name = name
        self.pynames = set()
        self.nonlocals = set()
        self.loops = 0

    def ancestors(self):
        f = self.parent
        while f is not None:
            yield f
            f = f.parent


class Scope:
    def __init__(self, parent, func, hidden=False):
        self.parent = parent
        self.func = func
        self.names = {}
        self.hidden = hidden    # comprehension scopes: invisible to hoisted fns


class Compiler:
    def __init__(self, source: str, filename="<pcmd>"):
        self.source_lines = source.replace("\r\n", "\n").split("\n")
        self.filename = filename
        self.out = []           # (indent, text, source line)
        self.ind = 0
        self.pre = []           # hoisted defs waiting for the current statement
        self.tmp = 0
        self.structs = {}       # name -> {"fields": [...], "py": ...}
        self.builtin = Scope(None, None)
        for name in rt.BUILTIN_NAMES:
            self.builtin.names[name] = Binding(name, name, False, "builtin", 0, None)
        self.stmt_scope = None

    # ------------------------------------------------------------ output
    def emit(self, text, line):
        self.out.append((self.ind, text, line))

    def error(self, message, line):
        raise PcmdSyntaxError(message, line)

    def temp(self, base="t"):
        self.tmp += 1
        return f"_pc_{base}{self.tmp}"

    def python(self):
        return "\n".join("    " * ind + text for ind, text, _ in self.out) + "\n"

    def line_map(self):
        return [line for _, _, line in self.out]

    # ------------------------------------------------------------ names
    def alloc(self, func, name):
        base = pyname_of(name)
        taken = set(func.pynames)
        for f in func.ancestors():
            taken |= f.pynames
        py = base
        k = 2
        while py in taken:
            py = f"{base}_{k}"
            k += 1
        func.pynames.add(py)
        return py

    def declare(self, scope, name, kind, line, mutable=False, type_=None, live=True, py=None,
                info=None):
        if name in scope.names and scope.names[name].kind != "builtin":
            other = scope.names[name]
            self.error(f"{name} is already declared in this block (line {other.line}) - "
                       f"pick another name, or change it with = if it is a var", line)
        if py is None:
            py = self.alloc(scope.func, name)
        b = Binding(name, py, mutable, kind, line, scope.func, type_, live, info=info)
        scope.names[name] = b
        return b

    def lookup(self, scope, name):
        s = scope
        while s is not None:
            if name in s.names:
                return s.names[name]
            s = s.parent
        return None

    def visible(self, scope):
        names = set()
        s = scope
        while s is not None:
            names |= set(s.names)
            s = s.parent
        return names

    def resolve(self, scope, name, line):
        b = self.lookup(scope, name)
        if b is None:
            close = difflib.get_close_matches(name, sorted(self.visible(scope)), n=1, cutoff=0.7)
            hint = f" - did you mean {close[0]}?" if close else ""
            if name in ("True", "False", "None", "null", "undefined"):
                hint = f" - PyCmd writes {'true' if name == 'True' else 'false' if name == 'False' else 'nil'}"
            elif name in ("def", "function", "func", "elsif", "elseif"):
                hint = " - PyCmd writes fn for functions and elif for else-if"
            elif name in rt.LIBRARIES:
                hint = f" - write `use {name}` at the top first"
            self.error(f"unknown name '{name}'{hint}", line)
        if not b.live and b.func is scope.func:
            self.error(f"{name} is used before it is declared (on line {b.line})", line)
        return b

    def ref(self, scope, name, line):
        b = self.resolve(scope, name, line)
        return b.alias if b.alias is not None else b.py

    def assign_name(self, scope, name, line):
        b = self.resolve(scope, name, line)
        if not b.mutable:
            why = {
                "let": f"{name} was declared with let, so it cannot change - declare it with var",
                "loop": f"{name} is the loop variable - it gets each item in turn and cannot be "
                        "changed here; copy it into a var",
                "fn": f"{name} is a function, not a variable",
                "struct": f"{name} is a struct",
                "enum": f"{name} is an enum",
                "lib": f"{name} is a library",
                "builtin": f"{name} is built in - use another name",
                "match": f"{name} comes from the match pattern and cannot change",
                "catch": f"{name} is the caught error",
            }.get(b.kind, f"{name} cannot change")
            self.error(f"cannot assign to {name}: {why}", line)
        func = scope.func
        if b.func is not func:
            func.nonlocals.add(b.py)
        return b

    # ------------------------------------------------------------ types
    def type_check(self, t, var, scope, line):
        """A Python expression that is true when `var` matches type t."""
        if t is None:
            return None
        kind = t[0]
        if kind == "optional":
            inner = self.type_check(t[1], var, scope, line)
            return None if inner is None else f"({var} is None or {inner})"
        if kind == "union":
            parts = [self.type_check(x, var, scope, line) for x in t[1]]
            if any(p is None for p in parts):
                return None
            return "(" + " or ".join(parts) + ")"
        _, name, _args, tline = t
        simple = {
            "int": f"_pc_T({var}) is _pc_tint", "float": f"_pc_T({var}) in _pc_NUM",
            "num": f"_pc_T({var}) in _pc_NUM", "str": f"_pc_T({var}) is _pc_tstr",
            "bool": f"_pc_T({var}) is _pc_tbool", "list": f"_pc_T({var}) is _pc_list_t",
            "map": f"_pc_T({var}) is _pc_tdict", "set": f"_pc_T({var}) is _pc_tset",
            "tuple": f"_pc_T({var}) is _pc_ttuple", "fn": f"_pc_callable({var})",
            "nil": f"{var} is None", "range": f"_pc_T({var}) is _pc_range_t",
            "Error": f"_pc_isinst({var}, _pc_Error)",
        }
        if name == "any":
            return None
        if name in simple:
            return simple[name]
        b = self.lookup(scope, name)
        if b is None or b.kind not in ("struct", "enum"):
            close = difflib.get_close_matches(name, sorted(BUILTIN_TYPES | set(self.structs)), n=1)
            hint = f" - did you mean {close[0]}?" if close else ""
            self.error(f"unknown type {name}{hint}", tline or line)
        if b.kind == "struct":
            return f"_pc_isinst({var}, {b.py})"
        return f"(_pc_isinst({var}, _pc_Variant) and {var}.enum is {b.py})"

    def type_name(self, t):
        if t is None:
            return "any"
        if t[0] == "optional":
            return self.type_name(t[1]) + "?"
        if t[0] == "union":
            return " | ".join(self.type_name(x) for x in t[1])
        name = t[1]
        if t[2]:
            name += "[" + ", ".join(self.type_name(a) for a in t[2]) + "]"
        return name

    def emit_check(self, t, var, what, scope, line):
        cond = self.type_check(t, var, scope, line)
        if cond is not None:
            tn = self.type_name(t).replace("'", "\\'")
            self.emit(f"if not ({cond}): raise _pc_type_err({what!r}, '{tn}', {var})", line)

    # ------------------------------------------------------------ program
    def compile_program(self, program: Node, module=False):
        main = Func(None, "main", name="main")
        scope = Scope(self.builtin, main)
        self.emit("def _pc_main():", 1)
        self.ind += 1
        start = len(self.out)
        self.block(program.body, scope)
        exports = [f"{name!r}: {b.py}" for name, b in scope.names.items()
                   if b.kind in ("let", "var", "fn", "struct", "enum")]
        self.emit("return {" + ", ".join(exports) + "}", 1)
        self.insert_nonlocals(main, start)
        self.ind -= 1
        return self.python()

    def insert_nonlocals(self, func, start):
        if func.nonlocals:
            names = sorted(func.nonlocals)
            self.out.insert(start, (self.ind, "nonlocal " + ", ".join(names), self.out[start - 1][2]))

    # ------------------------------------------------------------ blocks
    HOISTED = ("fn", "struct", "enum")

    def block(self, body, scope, implicit_return=False):
        # Everything a block declares is known before any of it runs:
        # functions and types can be used anywhere in it, and a function
        # body can use a variable declared further down.
        for st in body:
            if st.kind == "fn":
                self.declare(scope, st.name, "fn", st.line)
            elif st.kind == "struct":
                fields = self.struct_fields(st, scope)
                self.declare(scope, st.name, "struct", st.line, info=fields)
                self.structs[st.name] = {"fields": fields}
            elif st.kind == "enum":
                self.declare(scope, st.name, "enum", st.line)
            elif st.kind == "let":
                for raw in st.names:
                    name = raw[3:] if raw.startswith("...") else raw
                    self.declare(scope, name, "var" if st.mutable else "let", st.line,
                                 mutable=st.mutable, type_=st.type, live=False)
            elif st.kind == "use":
                if st.names:
                    for name in st.names:
                        self.declare(scope, name, "lib", st.line, live=False)
                else:
                    self.declare(scope, st.alias, "lib", st.line, live=False)
        # Types first (parents before children), then functions, then the rest.
        enums = [st for st in body if st.kind == "enum"]
        structs = self.order_structs([st for st in body if st.kind == "struct"])
        fns = [st for st in body if st.kind == "fn"]
        for st in enums + structs + fns:
            self.statement(st, scope)
        rest = [st for st in body if st.kind not in self.HOISTED]
        if not rest and not (enums or structs or fns):
            self.emit("pass", 0)
            return
        for index, st in enumerate(rest):
            last = index == len(rest) - 1
            if implicit_return and last and st.kind == "expr":
                st = Node("return", st.line, value=st.expr, implicit=True)
            elif implicit_return and last and st.kind == "match_stmt" and \
                    all(arm["expr"] is not None for arm in st.arms):
                st = Node("return", st.line, value=Node("match", st.line, subject=st.subject,
                                                        arms=st.arms), implicit=True)
            self.statement(st, scope)
        if not rest and (enums or structs or fns):
            pass

    def order_structs(self, structs):
        done, out = set(), []
        names = {s.name for s in structs}
        pending = list(structs)
        while pending:
            progressed = False
            for s in list(pending):
                if s.parent is None or s.parent not in names or s.parent in done:
                    out.append(s)
                    done.add(s.name)
                    pending.remove(s)
                    progressed = True
            if not progressed:
                self.error(f"struct {pending[0].name} extends itself through a loop", pending[0].line)
        return out

    # ------------------------------------------------------------ statements
    def statement(self, st, scope):
        self.stmt_scope = scope
        saved_pre, self.pre = self.pre, []
        mark = len(self.out)
        handler = getattr(self, "st_" + st.kind)
        handler(st, scope)
        if self.pre:
            for offset, row in enumerate(self.pre):
                self.out.insert(mark + offset, row)
        self.pre = saved_pre

    def st_expr(self, st, scope):
        e = st.expr
        if e.kind == "map" and not e.pairs:
            self.emit("pass", st.line)
            return
        self.emit(self.expr(e, scope), st.line)

    def st_let(self, st, scope):
        if st.unpack:
            targets = []
            for raw in st.names:
                if raw.startswith("..."):
                    targets.append("*" + scope.names[raw[3:]].py)
                else:
                    targets.append(scope.names[raw].py)
            value = self.expr(st.value, scope)
            for raw in st.names:
                scope.names[raw[3:] if raw.startswith("...") else raw].live = True
            self.emit(f"{', '.join(targets)}{',' if len(targets) == 1 else ''} = {value}", st.line)
            return
        name = st.names[0]
        b = scope.names[name]
        value = "None" if st.value is None else self.expr(st.value, scope)
        b.live = True
        self.emit(f"{b.py} = {value}", st.line)
        if st.value is not None:
            self.emit_check(st.type, b.py, name, scope, st.line)

    def st_assign(self, st, scope):
        target = st.target
        value = self.expr(st.value, scope)
        op = st.op
        if target.kind == "name":
            b = self.assign_name(scope, target.name, st.line)
            self.emit(f"{b.py} {op} {value}", st.line)
            if b.type is not None:
                self.emit_check(b.type, b.py, target.name, scope, st.line)
            return
        if target.kind == "tuple":
            if op != "=":
                self.error(f"{op} needs one target, not several", st.line)
            parts = []
            for t in target.items:
                if t.kind == "name":
                    parts.append(self.assign_name(scope, t.name, st.line).py)
                else:
                    parts.append(self.target(t, scope))
            self.emit(f"{', '.join(parts)} = {value}", st.line)
            return
        self.emit(f"{self.target(target, scope)} {op} {value}", st.line)

    def target(self, t, scope):
        if t.kind == "attr":
            return f"{self.expr(t.obj, scope)}.{pyname_of(t.name)}"
        if t.kind == "index":
            return f"{self.expr(t.obj, scope)}[{self.index(t.index, scope)}]"
        self.error("cannot assign to that", t.line)

    def params_code(self, params, scope, line, func):
        """Declares params in scope; returns (python param list, body prologue)."""
        out = []
        prologue = []
        for p in params:
            name = p["name"]
            if name == "self":
                b = Binding("self", "self", False, "self", line, func)
                scope.names["self"] = b
                out.append("self")
                continue
            if name in scope.names:
                self.error(f"parameter {name} is listed twice", line)
            py = pyname_of(name)
            func.pynames.add(py)
            b = Binding(name, py, True, "param", line, func, p["type"])
            scope.names[name] = b
            if p["rest"]:
                out.append("*" + py)
                prologue.append(("rest", py, p))
            elif p["default"] is not None:
                out.append(f"{py}=_pc_MISSING")
                prologue.append(("default", py, p))
            else:
                out.append(py)
                prologue.append(("plain", py, p))
        return out, prologue

    def emit_prologue(self, prologue, scope, line):
        for kind, py, p in prologue:
            if kind == "rest":
                self.emit(f"{py} = _pc_list_t({py})", line)
            elif kind == "default":
                self.emit(f"if {py} is _pc_MISSING: {py} = {self.expr(p['default'], scope)}", line)
            if kind != "rest":
                self.emit_check(p["type"], py, f"parameter {p['name']}", scope, line)

    def function(self, name_py, params, ret, body, scope, line, kind="fn", fname="",
                 decorator=None):
        func = Func(scope.func, kind, ret=ret, name=fname)
        inner = Scope(scope, func)
        plist, prologue = self.params_code(params, inner, line, func)
        if decorator:
            self.emit(decorator, line)
        self.emit(f"def {name_py}({', '.join(plist)}):", line)
        self.ind += 1
        start = len(self.out)
        self.emit_prologue(prologue, inner, line)
        saved = self.stmt_scope
        self.block(body, inner, implicit_return=True)
        if ret is not None:
            cond = self.type_check(ret, "None", inner, line)
            if cond is not None and not self._accepts_nil(ret):
                ind, last, _ = self.out[-1]
                if not (ind == self.ind and last.startswith(("return", "raise"))):
                    self.emit(f"raise _pc_type_err('the result of {fname or 'this fn'}', "
                              f"'{self.type_name(ret)}', None)", line)
        self.insert_nonlocals(func, start)
        self.ind -= 1
        self.stmt_scope = saved
        bad = func.nonlocals & {pyname_of(p["name"]) for p in params}
        if bad:
            self.error("a parameter has the same name as an outer variable it changes", line)
        return func

    def _accepts_nil(self, t):
        if t[0] == "optional":
            return True
        if t[0] == "union":
            return any(self._accepts_nil(x) for x in t[1])
        return t[1] in ("nil", "any")

    def st_fn(self, st, scope):
        b = scope.names[st.name]
        self.function(b.py, st.params, st.ret, st.body, scope, st.line, "fn", st.name)

    def st_return(self, st, scope):
        func = scope.func
        if func.kind in ("main", "test") and not getattr(st, "f", {}).get("implicit"):
            if func.kind == "main":
                self.error("return is only for inside a fn - to stop the program, use exit()",
                           st.line)
            self.emit("return", st.line)
            return
        if st.value is None:
            self.emit("return None", st.line)
            return
        value = self.expr(st.value, scope)
        if func.ret is not None and self.type_check(func.ret, "_pc_r", scope, st.line):
            self.emit(f"_pc_r = {value}", st.line)
            self.emit_check(func.ret, "_pc_r", f"the result of {func.name or 'this fn'}", scope,
                            st.line)
            self.emit("return _pc_r", st.line)
        else:
            self.emit(f"return {value}", st.line)

    def struct_fields(self, st, scope):
        fields = []
        if st.parent:
            parent = self.structs.get(st.parent)
            if parent is None:
                pb = self.lookup(scope, st.parent)
                if pb is None or pb.kind != "struct":
                    self.error(f"struct {st.name} extends {st.parent}, which is not a struct "
                               "declared before it", st.line)
                parent = {"fields": pb.info or []}
            fields.extend(parent["fields"])
        own = {f["name"] for f in fields}
        for f in st.fields:
            if f["name"] in own:
                self.error(f"{st.name} already has a field {f['name']}", f["line"])
            own.add(f["name"])
            fields.append(f)
        return fields

    def st_struct(self, st, scope):
        b = scope.names[st.name]
        fields = b.info
        own = [f for f in st.fields]
        base = "_pc_Struct"
        if st.parent:
            base = self.ref(scope, st.parent, st.line)
        self.emit(f"class {b.py}({base}):", st.line)
        self.ind += 1
        slots = ", ".join(repr(pyname_of(f["name"])) for f in own)
        self.emit(f"__slots__ = ({slots}{',' if len(own) == 1 else ''})", st.line)
        self.emit(f"_pc_name = {st.name!r}", st.line)
        all_py = [pyname_of(f["name"]) for f in fields]
        self.emit(f"_pc_fields = ({', '.join(repr(p) for p in all_py)}{',' if len(all_py) == 1 else ''})",
                  st.line)
        self.emit(f"_pc_shown = ({', '.join(repr(f['name']) for f in fields)}{',' if len(fields) == 1 else ''})",
                  st.line)
        self.emit("__match_args__ = _pc_fields", st.line)
        # __init__: every field, by position or by name
        func = Func(scope.func, "method", name=f"{st.name}")
        inner = Scope(scope, func)
        params = ", ".join(f"{p}=_pc_MISSING" for p in all_py)
        self.emit(f"def __init__(self{', ' if params else ''}{params}):", st.line)
        self.ind += 1
        if not fields:
            self.emit("pass", st.line)
        for f, py in zip(fields, all_py):
            line = f.get("line", st.line)
            if f["default"] is not None:
                func.pynames.add(py)
                default = self.expr(f["default"], inner)
                self.emit(f"if {py} is _pc_MISSING: {py} = {default}", line)
            else:
                self.emit(f"if {py} is _pc_MISSING: raise _pc_missing({st.name!r}, {f['name']!r})",
                          line)
            self.emit_check(f["type"], py, f"{st.name}.{f['name']}", inner, line)
            self.emit(f"self.{py} = {py}", line)
        self.ind -= 1
        for m in st.methods:
            is_method = bool(m.params) and m.params[0]["name"] == "self"
            mscope = Scope(scope, scope.func)
            self.function(pyname_of(m.name), m.params, m.ret, m.body, mscope, m.line,
                          "method" if is_method else "fn", f"{st.name}.{m.name}",
                          decorator=None if is_method else "@_pc_static")
        self.ind -= 1

    def st_enum(self, st, scope):
        b = scope.names[st.name]
        items = []
        for name, value in st.variants:
            v = "None" if value is None else self.expr(value, scope)
            items.append(f"({name!r}, {v})")
        self.emit(f"{b.py} = _pc_enum({st.name!r}, [{', '.join(items)}])", st.line)

    def st_if(self, st, scope):
        for index, (cond, body) in enumerate(st.branches):
            word = "if" if index == 0 else "elif"
            self.emit(f"{word} {self.expr(cond, scope)}:", cond.line)
            self.sub_block(body, scope)
        if st.other is not None:
            self.emit("else:", st.line)
            self.sub_block(st.other, scope)

    def sub_block(self, body, scope, prepare=None, loop=False):
        inner = Scope(scope, scope.func)
        self.ind += 1
        if prepare:
            prepare(inner)
        if loop:
            scope.func.loops += 1
        self.block(body, inner)
        if loop:
            scope.func.loops -= 1
        self.ind -= 1
        return inner

    def st_while(self, st, scope):
        cond = st.cond
        text = "True" if cond.kind == "const" and cond.value is True else self.expr(cond, scope)
        self.emit(f"while {text}:", st.line)
        self.sub_block(st.body, scope, loop=True)

    def st_for(self, st, scope):
        it = st.iter
        if it.kind == "range":
            lo = self.expr(it.lo, scope)
            hi = self.expr(it.hi, scope)
            iterable = f"_pc_range_t({lo}, {hi}{' + 1' if it.inclusive else ''})"
        else:
            iterable = self.expr(it, scope)
            if len(st.names) == 2:
                iterable = f"_pc_pairs({iterable})"
        inner = Scope(scope, scope.func)
        pys = [self.declare(inner, name, "loop", st.line).py for name in st.names]
        self.emit(f"for {', '.join(pys)} in {iterable}:", st.line)
        self.ind += 1
        scope.func.loops += 1
        self.block(st.body, Scope(inner, scope.func))
        scope.func.loops -= 1
        self.ind -= 1

    def st_break(self, st, scope):
        if scope.func.loops <= 0:
            self.error("break is only for inside a loop", st.line)
        self.emit("break", st.line)

    def st_continue(self, st, scope):
        if scope.func.loops <= 0:
            self.error("continue is only for inside a loop", st.line)
        self.emit("continue", st.line)

    def st_throw(self, st, scope):
        self.emit(f"raise _pc_throw({self.expr(st.value, scope)})", st.line)

    def st_assert(self, st, scope):
        text = self.source_lines[st.line - 1].strip() if 0 < st.line <= len(self.source_lines) else ""
        text = text[len("assert"):].strip() if text.startswith("assert") else text
        message = "None" if st.message is None else self.expr(st.message, scope)
        self.emit(f"if not ({self.expr(st.cond, scope)}): "
                  f"raise _pc_assert({st.line}, {text!r}, {message})", st.line)

    def st_test(self, st, scope):
        name = self.temp("test")
        func = Func(scope.func, "test", name=st.name)
        inner = Scope(scope, func)
        self.emit(f"def {name}():", st.line)
        self.ind += 1
        start = len(self.out)
        self.block(st.body, inner)
        self.insert_nonlocals(func, start)
        self.ind -= 1
        self.emit(f"_pc_tests.append(({st.name!r}, {name}, {st.line}))", st.line)

    def st_try(self, st, scope):
        self.emit("try:", st.line)
        self.sub_block(st.body, scope)
        if st.handler is not None:
            caught = self.temp("e")
            self.emit(f"except _pc_Exc as {caught}:", st.line)
            inner = Scope(scope, scope.func)
            self.ind += 1
            if st.name:
                b = self.declare(inner, st.name, "catch", st.line)
                self.emit(f"{b.py} = _pc_catch({caught})", st.line)
            self.block(st.handler, Scope(inner, scope.func))
            self.ind -= 1
        if st.final is not None:
            self.emit("finally:", st.line)
            self.sub_block(st.final, scope)

    def st_use(self, st, scope):
        if st.path is not None:
            b = scope.names[st.alias]
            b.live = True
            self.emit(f"{b.py} = _pc_import({st.path!r}, {self.filename!r})", st.line)
            return
        root = st.module.split(".")[0]
        if root not in rt.LIBRARIES:
            close = difflib.get_close_matches(root, sorted(rt.LIBRARIES), n=1)
            hint = f" - did you mean {close[0]}?" if close else "."
            self.error(f"there is no library called {st.module}{hint} There are: "
                       f"{', '.join(sorted(rt.LIBRARIES))}", st.line)
        lib = f"_pc_lib({root!r})"
        if st.names:
            for name in st.names:
                b = scope.names[name]
                b.live = True
                self.emit(f"{b.py} = {lib}.{pyname_of(name)}", st.line)
            return
        b = scope.names[st.alias]
        b.live = True
        self.emit(f"{b.py} = {lib}", st.line)

    # ------------------------------------------------------------ match
    def pattern(self, p, subject, scope, binds, line):
        """A condition on `subject`; names the pattern binds go into binds."""
        kind = p[0]
        if kind == "any":
            return "True"
        if kind == "lit":
            v = p[1]
            if v is None or isinstance(v, bool):
                return f"{subject} is {v!r}"
            return f"{subject} == {v!r}"
        if kind == "bind":
            binds.append((p[1], subject, p[2]))
            return "True"
        if kind == "range":
            return f"_pc_inr({subject}, {p[1]!r}, {p[2]!r}, {p[3]!r})"
        if kind == "value":
            parts = p[1]
            base = self.ref(scope, parts[0], line)
            return f"{subject} == {base}{''.join('.' + pyname_of(x) for x in parts[1:])}"
        if kind == "type":
            cond = self.type_check(p[1], subject, scope, line)
            return cond or "True"
        if kind == "or":
            conds = []
            for alt in p[1]:
                inner = []
                conds.append(self.pattern(alt, subject, scope, inner, line))
                if inner:
                    self.error("a | pattern cannot bind names", line)
            return "(" + " or ".join(conds) + ")"
        if kind == "list":
            items = p[1]
            rest_at = next((i for i, x in enumerate(items) if x[0] == "rest"), None)
            n = len(items) - (1 if rest_at is not None else 0)
            conds = [f"_pc_T({subject}) in _pc_seq"]
            conds.append(f"_pc_len({subject}) {'>=' if rest_at is not None else '=='} {n}")
            after = len(items) - rest_at - 1 if rest_at is not None else 0
            for i, item in enumerate(items):
                if item[0] == "rest":
                    if item[1] != "_":
                        sl = f"{subject}[{i}:]" if after == 0 else f"{subject}[{i}:-{after}]"
                        binds.append((item[1], f"_pc_list_t({sl})", line))
                    continue
                if rest_at is not None and i > rest_at:
                    sub = f"{subject}[-{len(items) - i}]"
                else:
                    sub = f"{subject}[{i}]"
                c = self.pattern(item, sub, scope, binds, line)
                if c != "True":
                    conds.append(c)
            return "(" + " and ".join(conds) + ")"
        if kind == "struct":
            name, subs = p[1], p[2]
            b = self.resolve(scope, name, line)
            if b.kind != "struct":
                self.error(f"{name} is not a struct, so it cannot be a pattern like {name}(...)", line)
            fields = [pyname_of(f["name"]) for f in (b.info or [])]
            conds = [f"_pc_isinst({subject}, {b.py})"]
            for i, (key, sub) in enumerate(subs):
                if key is None:
                    if i >= len(fields):
                        self.error(f"{name} has only {len(fields)} fields", line)
                    field = fields[i]
                else:
                    field = pyname_of(key)
                    if field not in fields:
                        self.error(f"{name} has no field {key}", line)
                c = self.pattern(sub, f"{subject}.{field}", scope, binds, line)
                if c != "True":
                    conds.append(c)
            return "(" + " and ".join(conds) + ")"
        self.error("unknown pattern", line)

    def arm_scope(self, scope, binds):
        inner = Scope(scope, scope.func)
        for name, expr, line in binds:
            if name in inner.names:
                self.error(f"the pattern binds {name} twice", line)
            b = Binding(name, expr, False, "match", line, scope.func, alias=expr)
            inner.names[name] = b
        return inner

    def st_match_stmt(self, st, scope):
        subject = self.temp("s")
        self.emit(f"{subject} = {self.expr(st.subject, scope)}", st.line)
        first = True
        for arm in st.arms:
            binds = []
            cond = self.pattern(arm["pattern"], subject, scope, binds, arm["line"])
            inner = self.arm_scope(scope, binds)
            if arm["guard"] is not None:
                guard = self.expr(arm["guard"], inner)
                cond = guard if cond == "True" else f"({cond}) and ({guard})"
            if cond == "True" and not first:
                self.emit("else:", arm["line"])
            else:
                self.emit(f"{'if' if first else 'elif'} {cond}:", arm["line"])
            self.ind += 1
            if arm["body"] is not None:
                self.block(arm["body"], Scope(inner, scope.func))
            else:
                e = arm["expr"]
                if e.kind == "map" and not e.pairs:
                    self.emit("pass", arm["line"])
                else:
                    self.emit(self.expr(e, inner), arm["line"])
            self.ind -= 1
            first = False
            if cond == "True":
                break

    def match_value(self, node, scope):
        subject = self.temp("s")
        chain = "None"
        parts = []
        for arm in node.arms:
            if arm["expr"] is None:
                self.error("in a match that gives a value, each arm needs a value: "
                           "pattern => value", arm["line"])
            binds = []
            cond = self.pattern(arm["pattern"], subject, scope, binds, arm["line"])
            inner = self.arm_scope(scope, binds)
            if arm["guard"] is not None:
                guard = self.expr(arm["guard"], inner)
                cond = guard if cond == "True" else f"({cond}) and ({guard})"
            parts.append((cond, self.expr(arm["expr"], inner)))
        for cond, value in reversed(parts):
            chain = value if cond == "True" else f"({value} if {cond} else {chain})"
        return f"({chain} if (({subject} := {self.expr(node.subject, scope)}) is {subject} or True) else None)"

    # ------------------------------------------------------------ expressions
    def expr(self, n, scope):
        return getattr(self, "ex_" + n.kind)(n, scope)

    def ex_const(self, n, scope):
        return repr(n.value)

    def ex_name(self, n, scope):
        return self.ref(scope, n.name, n.line)

    def ex_self(self, n, scope):
        b = self.lookup(scope, "self")
        if b is None:
            self.error("self is only for inside a struct's methods: fn name(self) { ... }", n.line)
        return "self"

    def ex_group(self, n, scope):
        return f"({self.expr(n.expr, scope)})"

    def ex_interp(self, n, scope):
        pieces = []
        for part in n.parts:
            if isinstance(part, str):
                pieces.append(repr(part))
            else:
                _, e, spec = part
                value = self.expr(e, scope)
                pieces.append(f"_pc_fmt({value}, {spec!r})" if spec else f"_pc_show({value})")
        return "(" + " + ".join(pieces) + ")"

    def ex_list(self, n, scope):
        return "[" + ", ".join(self.item(x, scope) for x in n.items) + "]"

    def item(self, x, scope):
        if x.kind == "spread":
            return "*" + self.expr(x.expr, scope)
        return self.expr(x, scope)

    def ex_tuple(self, n, scope):
        items = [self.item(x, scope) for x in n.items]
        return "(" + ", ".join(items) + ("," if len(items) == 1 else "") + ")"

    def ex_map(self, n, scope):
        parts = []
        for k, v in n.pairs:
            if k is None:
                parts.append("**" + self.expr(v, scope))
            else:
                parts.append(f"{self.expr(k, scope)}: {self.expr(v, scope)}")
        return "{" + ", ".join(parts) + "}"

    def comprehension(self, loops, cond, scope, make):
        inner = scope
        clauses = []
        for names, it in loops:
            iterable = self.expr(it, inner) if it.kind != "range" else \
                f"_pc_range_t({self.expr(it.lo, inner)}, {self.expr(it.hi, inner)}{' + 1' if it.inclusive else ''})"
            if len(names) == 2:
                iterable = f"_pc_pairs({iterable})"
            inner = Scope(inner, scope.func, hidden=True)
            pys = [self.declare(inner, name, "loop", it.line).py for name in names]
            clauses.append(f"for {', '.join(pys)} in {iterable}")
        tail = " ".join(clauses)
        if cond is not None:
            tail += f" if {self.expr(cond, inner)}"
        return make(inner, tail)

    def ex_listcomp(self, n, scope):
        return self.comprehension(n.loops, n.cond, scope,
                                  lambda inner, tail: f"[{self.expr(n.expr, inner)} {tail}]")

    def ex_mapcomp(self, n, scope):
        return self.comprehension(
            n.loops, n.cond, scope,
            lambda inner, tail: f"{{{self.expr(n.key, inner)}: {self.expr(n.value, inner)} {tail}}}")

    def ex_unary(self, n, scope):
        v = self.expr(n.operand, scope)
        if n.op == "not":
            return f"(not {v})"
        return f"({n.op}{v})"

    def ex_binary(self, n, scope):
        return f"({self.expr(n.left, scope)} {n.op} {self.expr(n.right, scope)})"

    def ex_compare(self, n, scope):
        items = [self.expr(x, scope) for x in n.items]
        out = items[0]
        for op, item in zip(n.ops, items[1:]):
            out += f" {op} {item}"
        return f"({out})"

    def ex_logic(self, n, scope):
        return f"({self.expr(n.left, scope)} {n.op} {self.expr(n.right, scope)})"

    def ex_ternary(self, n, scope):
        return f"({self.expr(n.a, scope)} if {self.expr(n.cond, scope)} else {self.expr(n.b, scope)})"

    def ex_coalesce(self, n, scope):
        t = self.temp("c")
        return f"({t} if ({t} := {self.expr(n.left, scope)}) is not None else {self.expr(n.right, scope)})"

    def ex_is(self, n, scope):
        t = self.temp("i")
        cond = self.type_check(n.type, t, scope, n.line) or "True"
        text = f"(({t} := {self.expr(n.value, scope)}) is {t} and {cond})"
        return f"(not {text})" if n.negate else text

    def ex_range(self, n, scope):
        lo = self.expr(n.lo, scope)
        hi = self.expr(n.hi, scope)
        return f"_pc_range_t({lo}, {hi}{' + 1' if n.inclusive else ''})"

    def ex_pipe(self, n, scope):
        f = n.func
        if f.kind == "call":
            call = Node("call", f.line, func=f.func, args=[n.value] + list(f.args), kwargs=f.kwargs)
            return self.expr(call, scope)
        return f"{self.expr(f, scope)}({self.expr(n.value, scope)})"

    def ex_attr(self, n, scope):
        obj = self.expr(n.obj, scope)
        if n.name in rt.EXT:
            return f"_pc_bind({obj}, {n.name!r})"
        return f"{obj}.{pyname_of(n.name)}"

    def ex_optattr(self, n, scope):
        return f"_pc_oa({self.expr(n.obj, scope)}, {pyname_of(n.name)!r})"

    def ex_index(self, n, scope):
        return f"{self.expr(n.obj, scope)}[{self.index(n.index, scope)}]"

    def index(self, i, scope):
        if i.kind == "slice":
            parts = ["" if x is None else self.expr(x, scope) for x in (i.start, i.stop, i.step)]
            text = f"{parts[0]}:{parts[1]}"
            if parts[2]:
                text += f":{parts[2]}"
            return text
        return self.expr(i, scope)

    def args(self, n, scope):
        out = [self.item(a, scope) for a in n.args]
        out += [f"{pyname_of(k)}={self.expr(v, scope)}" for k, v in n.kwargs]
        return ", ".join(out)

    def ex_call(self, n, scope):
        f = n.func
        args = self.args(n, scope)
        if f.kind == "attr":
            obj = self.expr(f.obj, scope)
            if f.name in rt.EXT:
                return f"_pc_x_{f.name}({obj}{', ' + args if args else ''})"
            return f"{obj}.{pyname_of(f.name)}({args})"
        if f.kind == "optattr":
            return f"_pc_oc({self.expr(f.obj, scope)}, {pyname_of(f.name)!r}{', ' + args if args else ''})"
        return f"{self.expr(f, scope)}({args})"

    def ex_match(self, n, scope):
        return self.match_value(n, scope)

    def ex_spread(self, n, scope):
        self.error("... only works inside a list or a call", n.line)

    def ex_slice(self, n, scope):
        self.error("a slice only works inside [ ]", n.line)

    def ex_lambda(self, n, scope):
        simple = n.body is None and n.ret is None and \
            all(p["type"] is None and not p["rest"] for p in n.params) and \
            not _has_block_lambda(n.expr)
        if simple:
            func = Func(scope.func, "lambda")
            inner = Scope(scope, func)
            # Python lambdas share the enclosing names for allocation purposes
            names = []
            for p in n.params:
                py = pyname_of(p["name"])
                inner.names[p["name"]] = Binding(p["name"], py, False, "param", n.line, func)
                func.pynames.add(py)
                if p["default"] is not None:
                    names.append(f"{py}={self.expr(p['default'], scope)}")
                else:
                    names.append(py)
            body = self.expr(n.expr, inner)
            if func.nonlocals:
                self.error("a short fn (=> value) cannot change outer variables - use fn(...) { }",
                           n.line)
            return f"(lambda {', '.join(names)}: {body})"
        # A real def, written just before the statement that uses it.
        name = self.temp("fn")
        body = n.body if n.body is not None else [Node("return", n.line, value=n.expr)]
        saved_out, saved_ind = self.out, self.ind
        self.out = []
        self.ind = saved_ind
        if _in_hidden(scope):
            self.out, self.ind = saved_out, saved_ind
            self.error("a fn with a { } body or typed parameters cannot sit inside "
                       "[ ... for ... ] - use a short one: fn(x) => value", n.line)
        self.function(name, n.params, n.ret, body, scope, n.line, "fn", "fn")
        rows = self.out
        self.out, self.ind = saved_out, saved_ind
        self.pre.extend(rows)
        return name


def _in_hidden(scope):
    s = scope
    while s is not None:
        if s.hidden:
            return True
        s = s.parent
    return False


def _has_block_lambda(node):
    if isinstance(node, Node):
        if node.kind == "lambda" and node.body is not None:
            return True
        return any(_has_block_lambda(v) for v in node.f.values())
    if isinstance(node, (list, tuple)):
        return any(_has_block_lambda(v) for v in node)
    if isinstance(node, dict):
        return any(_has_block_lambda(v) for v in node.values())
    return False


def compile_source(source: str, filename="<pcmd>"):
    """(python source, line map) for a PyCmd program. Raises PcmdSyntaxError."""
    from .pcmd_parser import parse

    tree = parse(source)
    c = Compiler(source, filename)
    py = c.compile_program(tree)
    return py, c.line_map()
