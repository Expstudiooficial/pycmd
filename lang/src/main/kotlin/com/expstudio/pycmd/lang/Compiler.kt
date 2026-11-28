package com.expstudio.pycmd.lang

/*
 * Ast -> executable nodes, checked on the way. Before a line runs it refuses
 * unknown names (with "did you mean"), names used before their declaration,
 * changes to a let / loop variable / fn / struct, break and continue outside
 * a loop, return outside a fn, a name declared twice in one block, unknown
 * types and unknown libraries - exactly as the first engine does.
 */

class FuncCtx(val parent: FuncCtx?, val kind: String, val name: String) {
    var nslots = 0
    val ups = ArrayList<Upval>()
    val upIndex = HashMap<Binding, Int>()
    var loops = 0
    var ret: TCheck? = null
}

class Scope(val parent: Scope?, val func: FuncCtx?, val hidden: Boolean = false) {
    val names = LinkedHashMap<String, Binding>()
    val declared = ArrayList<Binding>()
}

class StructInfo(val fields: List<Param>)

class Program(val main: FnProto, val exports: List<String>)

class Compiler(private val source: String, private val rt: Runtime, private val filename: String) {
    private val sourceLines = source.replace("\r\n", "\n").split("\n")
    private val blocks = ArrayList<BlockS>()
    private val protos = ArrayList<Pair<FnProto, BlockS>>()
    private val structs = HashMap<String, StructInfo>()
    private val builtin = Scope(null, null)

    init {
        for ((name, value) in rt.builtins) {
            val b = Binding(name, false, "builtin", 0, FuncCtx(null, "builtin", ""), -1, null)
            b.node = Const(0, value)
            builtin.names[name] = b
        }
    }

    private fun error(message: String, line: Int): Nothing = throw PcSyntaxError(message, line)

    // ------------------------------------------------------------ names
    private fun declare(scope: Scope, name: String, kind: String, line: Int, mutable: Boolean = false,
                        type: TCheck? = null, live: Boolean = true): Binding {
        scope.names[name]?.let { other ->
            if (other.kind != "builtin")
                error("$name is already declared in this block (line ${other.line}) - pick another name, " +
                        "or change it with = if it is a var", line)
        }
        val func = scope.func!!
        val b = Binding(name, mutable, kind, line, func, func.nslots++, type)
        b.live = live
        scope.names[name] = b
        scope.declared.add(b)
        return b
    }

    private fun lookup(scope: Scope, name: String): Binding? {
        var s: Scope? = scope
        while (s != null) { s.names[name]?.let { return it }; s = s.parent }
        return null
    }

    private fun visible(scope: Scope): Set<String> {
        val out = HashSet<String>()
        var s: Scope? = scope
        while (s != null) { out.addAll(s.names.keys); s = s.parent }
        return out
    }

    private fun resolve(scope: Scope, name: String, line: Int): Binding {
        val b = lookup(scope, name)
        if (b == null) {
            var hint = Similar.closest(name, visible(scope))?.let { " - did you mean $it?" } ?: ""
            when (name) {
                "True" -> hint = " - PyCmd writes true"
                "False" -> hint = " - PyCmd writes false"
                "None", "null", "undefined" -> hint = " - PyCmd writes nil"
                "def", "function", "func", "elsif", "elseif" -> hint = " - PyCmd writes fn for functions and elif for else-if"
                else -> if (name in Libs.NAMES) hint = " - write `use $name` at the top first"
            }
            error("unknown name '$name'$hint", line)
        }
        if (!b.live && b.func === scope.func) error("$name is used before it is declared (on line ${b.line})", line)
        return b
    }

    private fun upIndex(func: FuncCtx, b: Binding): Int {
        func.upIndex[b]?.let { return it }
        val parent = func.parent ?: throw IllegalStateException("no parent for ${b.name}")
        val uv = if (b.func === parent) {
            b.boxed = true
            Upval(b.slot, -1)
        } else Upval(-1, upIndex(parent, b))
        func.ups.add(uv)
        val i = func.ups.size - 1
        func.upIndex[b] = i
        return i
    }

    private fun ref(scope: Scope, name: String, line: Int): N {
        val b = resolve(scope, name, line)
        b.node?.let { return it }
        return if (b.func === scope.func) LocalGet(line, b.slot, b) else UpGet(line, upIndex(scope.func!!, b), name)
    }

    private fun placeOf(scope: Scope, b: Binding): Place =
        if (b.func === scope.func) LocalPlace(b.slot, b) else UpPlace(upIndex(scope.func!!, b))

    private fun assignPlace(scope: Scope, name: String, line: Int): Pair<Place, Binding> {
        val b = resolve(scope, name, line)
        if (!b.mutable) {
            val why = when (b.kind) {
                "let" -> "$name was declared with let, so it cannot change - declare it with var"
                "loop" -> "$name is the loop variable - it gets each item in turn and cannot be changed here; copy it into a var"
                "fn" -> "$name is a function, not a variable"
                "struct" -> "$name is a struct"
                "enum" -> "$name is an enum"
                "trait" -> "$name is a trait"
                "lib" -> "$name is a library"
                "builtin" -> "$name is built in - use another name"
                "match" -> "$name comes from the match pattern and cannot change"
                "catch" -> "$name is the caught error"
                "self" -> "self cannot be replaced - change its fields instead"
                else -> "$name cannot change"
            }
            error("cannot assign to $name: $why", line)
        }
        return placeOf(scope, b) to b
    }

    // ------------------------------------------------------------ types
    private fun typeCheck(t: TypeRef?, scope: Scope, line: Int): TCheck? {
        if (t == null) return null
        val text = typeName(t)
        val test = typeTest(t, scope, line) ?: return null
        return TCheck(text, test)
    }

    fun typeName(t: TypeRef): String = when (t) {
        is TypeRef.Optional -> typeName(t.inner) + "?"
        is TypeRef.Union -> t.options.joinToString(" | ") { typeName(it) }
        is TypeRef.Simple -> t.name + if (t.args.isNotEmpty()) t.args.joinToString(", ", "[", "]") { typeName(it) } else ""
    }

    private fun typeTest(t: TypeRef, scope: Scope, line: Int): ((Any?, Frame) -> Boolean)? {
        when (t) {
            is TypeRef.Optional -> {
                val inner = typeTest(t.inner, scope, line) ?: return null
                return { v, f -> v == null || inner(v, f) }
            }
            is TypeRef.Union -> {
                val parts = t.options.map { typeTest(it, scope, line) ?: return null }
                return { v, f -> parts.any { it(v, f) } }
            }
            is TypeRef.Simple -> {
                when (t.name) {
                    "any" -> return null
                    "int" -> return { v, _ -> v is Long || v is java.math.BigInteger }
                    "float", "num" -> return { v, _ -> v is Long || v is Double || v is java.math.BigInteger }
                    "str" -> return { v, _ -> v is String }
                    "bool" -> return { v, _ -> v is Boolean }
                    "list" -> return { v, _ -> v is PList }
                    "map" -> return { v, _ -> v is PMap }
                    "set" -> return { v, _ -> v is PSet }
                    "tuple" -> return { v, _ -> v is PTuple }
                    "fn" -> return { v, _ -> v is Callable || v is StructType }
                    "nil" -> return { v, _ -> v == null }
                    "range" -> return { v, _ -> v is PRange }
                    "Error" -> return { v, _ -> v is PcError }
                }
                val b = lookup(scope, t.name)
                if (b == null || b.kind !in setOf("struct", "enum", "trait")) {
                    val known = setOf("int", "float", "num", "str", "bool", "list", "map", "set", "tuple", "fn", "any",
                        "nil", "range", "Error") + structs.keys
                    val close = Similar.closest(t.name, known)?.let { " - did you mean $it?" } ?: ""
                    error("unknown type ${t.name}$close", if (t.line > 0) t.line else line)
                }
                val node = ref(scope, t.name, line)
                return when (b.kind) {
                    "struct" -> { v, f -> v is StructObj && v.type.isA(node.ev(f) as StructType) }
                    "trait" -> { v, f -> v is StructObj && v.type.hasTrait(node.ev(f) as TraitType) }
                    else -> { v, f ->
                        val e = node.ev(f)
                        (v is Variant && v.enum === e) || (v is VariantObj && v.variant.enum === e)
                    }
                }
            }
        }
    }

    private fun acceptsNil(t: TypeRef): Boolean = when (t) {
        is TypeRef.Optional -> true
        is TypeRef.Union -> t.options.any { acceptsNil(it) }
        is TypeRef.Simple -> t.name == "nil" || t.name == "any"
    }

    // ------------------------------------------------------------ program
    fun compileProgram(body: List<St>): Program {
        val main = FuncCtx(null, "main", "main")
        val scope = Scope(builtin, main)
        val block = block(body, scope, implicitReturn = false, extra = { s ->
            listOf(ExportS(s.names.values.filter { it.kind in setOf("let", "var", "fn", "struct", "enum", "trait") }
                .map { it.name to LocalPlace(it.slot, it) }))
        })
        val proto = FnProto("main", emptyList(), main.nslots, main.ups, rt)
        proto.body = block
        for (b in blocks) b.finish()
        for ((fp, blk) in protos) {
            val only = blk.stmts.singleOrNull()
            if (only is ReturnS && only.value != null && blk.cells.isEmpty()) fp.direct = only.value
        }
        return Program(proto, scope.names.keys.toList())
    }

    private class ExportS(val names: List<Pair<String, Place>>) : S(0) {
        override fun ex(f: Frame): Int {
            val m = PMap()
            for ((n, p) in names) m.map[n] = p.get(f).let { if (it === Unset) null else it }
            f.ret = m
            return RETURN
        }
    }

    // ------------------------------------------------------------ blocks
    private fun block(body: List<St>, scope: Scope, implicitReturn: Boolean = false,
                      extra: ((Scope) -> List<S>)? = null): BlockS {
        for (st in body) when (st) {
            is St.Fn -> declare(scope, st.name, "fn", st.line)
            is St.Struct -> {
                val fields = structFields(st, scope)
                structs[st.name] = StructInfo(fields)
                declare(scope, st.name, "struct", st.line)
            }
            is St.EnumS -> declare(scope, st.name, "enum", st.line)
            is St.Trait -> declare(scope, st.name, "trait", st.line)
            is St.Let -> for (raw in st.names) {
                val name = raw.removePrefix("...")
                declare(scope, name, if (st.mutable) "var" else "let", st.line, st.mutable, null, live = false)
            }
            is St.Use -> if (st.names != null) st.names.forEach { declare(scope, it, "lib", st.line, live = false) }
            else declare(scope, st.alias, "lib", st.line, live = false)
            else -> {}
        }
        // let types can name structs declared anywhere in the block
        for (st in body) if (st is St.Let && st.type != null && !st.unpack)
            scope.names[st.names[0]]!!.type = typeCheck(st.type, scope, st.line)
        val out = ArrayList<S>()
        val traits = body.filterIsInstance<St.Trait>()
        val enums = body.filterIsInstance<St.EnumS>()
        val structsHere = orderStructs(body.filterIsInstance<St.Struct>())
        val fns = body.filterIsInstance<St.Fn>()
        for (st in traits + enums + structsHere + fns) out.add(statement(st, scope))
        val rest = body.filter { it !is St.Fn && it !is St.Struct && it !is St.EnumS && it !is St.Trait }
        for ((index, st0) in rest.withIndex()) {
            var st = st0
            if (implicitReturn && index == rest.size - 1) {
                if (st is St.ExprS) st = St.Return(st.line, st.expr, implicit = true)
                else if (st is St.MatchS && st.arms.all { it.expr != null })
                    st = St.Return(st.line, Ex.MatchE(st.line, st.subject, st.arms), implicit = true)
            }
            out.add(statement(st, scope))
        }
        extra?.let { out.addAll(it(scope)) }
        val b = BlockS(body.firstOrNull()?.line ?: 0, out.toTypedArray(), scope.declared)
        blocks.add(b)
        return b
    }

    private fun orderStructs(list: List<St.Struct>): List<St.Struct> {
        val done = HashSet<String>()
        val names = list.map { it.name }.toSet()
        val pending = list.toMutableList()
        val out = ArrayList<St.Struct>()
        while (pending.isNotEmpty()) {
            val ready = pending.filter { it.parent == null || it.parent !in names || it.parent in done }
            if (ready.isEmpty()) error("struct ${pending[0].name} extends itself through a loop", pending[0].line)
            for (s in ready) { out.add(s); done.add(s.name); pending.remove(s) }
        }
        return out
    }

    private fun subBlock(body: List<St>, scope: Scope): BlockS = block(body, Scope(scope, scope.func))

    // ------------------------------------------------------------ statements
    private fun statement(st: St, scope: Scope): S = when (st) {
        is St.ExprS -> {
            val e = st.expr
            if (e is Ex.MapLit && e.pairs.isEmpty()) Nop(st.line) else ExprStmt(st.line, expr(e, scope))
        }
        is St.Let -> stLet(st, scope)
        is St.Assign -> stAssign(st, scope)
        is St.Fn -> {
            val b = scope.names[st.name]!!
            val proto = function(st.name, st.params, st.ret, st.body!!, scope, st.line, "fn")
            SetPlace(st.line, LocalPlace(b.slot, b), MakeFn(st.line, proto))
        }
        is St.Struct -> stStruct(st, scope)
        is St.EnumS -> stEnum(st, scope)
        is St.Trait -> stTrait(st, scope)
        is St.If -> IfS(st.line, st.branches.map { expr(it.first, scope) }.toTypedArray(),
            st.branches.map { subBlock(it.second, scope) }.toTypedArray(), st.other?.let { subBlock(it, scope) })
        is St.While -> {
            val cond = st.cond?.let { expr(it, scope) }
            scope.func!!.loops++
            val body = subBlock(st.body, scope)
            scope.func.loops--
            WhileS(st.line, cond, body, rt)
        }
        is St.For -> stFor(st, scope)
        is St.Return -> stReturn(st, scope)
        is St.Break -> { if (scope.func!!.loops <= 0) error("break is only for inside a loop", st.line); Signal(st.line, BREAK) }
        is St.Continue -> { if (scope.func!!.loops <= 0) error("continue is only for inside a loop", st.line); Signal(st.line, CONTINUE) }
        is St.Throw -> ThrowS(st.line, expr(st.value, scope))
        is St.Assert -> {
            var text = sourceLines.getOrNull(st.line - 1)?.trim() ?: ""
            if (text.startsWith("assert")) text = text.removePrefix("assert").trim()
            AssertS(st.line, expr(st.cond, scope), st.message?.let { expr(it, scope) }, text)
        }
        is St.Test -> {
            val func = FuncCtx(scope.func, "test", st.name)
            val inner = Scope(scope, func)
            val body = block(st.body, inner)
            val proto = FnProto(st.name, emptyList(), func.nslots, func.ups, rt)
            proto.body = body
            TestS(st.line, st.name, MakeFn(st.line, proto), rt)
        }
        is St.Try -> {
            val body = subBlock(st.body, scope)
            var catchPlace: Place? = null
            val handler = st.handler?.let {
                val inner = Scope(scope, scope.func)
                if (st.name != null) { val b = declare(inner, st.name, "catch", st.line); catchPlace = LocalPlace(b.slot, b) }
                block(it, Scope(inner, scope.func))
            }
            TryS(st.line, body, catchPlace, handler, st.final?.let { subBlock(it, scope) })
        }
        is St.Use -> stUse(st, scope)
        is St.MatchS -> matchStmt(st, scope)
    }

    private fun stLet(st: St.Let, scope: Scope): S {
        if (st.unpack) {
            val value = expr(st.value!!, scope)
            val places = st.names.map { raw ->
                val b = scope.names[raw.removePrefix("...")]!!
                b.live = true
                LocalPlace(b.slot, b) as Place
            }
            val restAt = st.names.indexOfFirst { it.startsWith("...") }
            return UnpackS(st.line, places, restAt, value)
        }
        val b = scope.names[st.names[0]]!!
        val value = st.value?.let { expr(it, scope) }
        b.live = true
        if (value != null && pureInt(value) && (b.type == null || b.type!!.text == "int"))
            return SetLongS(st.line, LocalPlace(b.slot, b), if (value is IntFast) value.e else value, b.type, b.name)
        return LetS(st.line, LocalPlace(b.slot, b), value, b.type, b.name)
    }

    /** Plain arithmetic on locals and int constants: no calls, no side effects. */
    private fun pureInt(n: N): Boolean = when (n) {
        is LocalGet -> true
        is Const -> n.value is Long
        is IntFast -> pureInt(n.e)
        is Add -> pureInt(n.a) && pureInt(n.b)
        is Sub -> pureInt(n.a) && pureInt(n.b)
        is Mul -> pureInt(n.a) && pureInt(n.b)
        is Mod -> pureInt(n.a) && pureInt(n.b)
        is FloorDiv -> pureInt(n.a) && pureInt(n.b)
        else -> false
    }

    private fun fast(n: N): N = if (n !is LocalGet && n !is Const && n !is IntFast && pureInt(n)) IntFast(n.line, n) else n

    private fun binop(op: String, line: Int, a: N, b: N): N = fast(binop0(op, line, a, b))

    private fun binop0(op: String, line: Int, a: N, b: N): N = when (op) {
        "+" -> Add(line, a, b)
        "-" -> Sub(line, a, b)
        "*" -> Mul(line, a, b)
        "/" -> Bin(line, a, b) { x, y -> Ops.div(x, y) }
        "//" -> FloorDiv(line, a, b)
        "%" -> Mod(line, a, b)
        "**" -> Bin(line, a, b) { x, y -> Ops.pow(x, y) }
        "in" -> Bin(line, a, b) { x, y -> Ops.contains(y, x) }
        "not in" -> Bin(line, a, b) { x, y -> !Ops.contains(y, x) }
        else -> error("unknown operator $op", line)
    }

    private fun stAssign(st: St.Assign, scope: Scope): S {
        val value = expr(st.value, scope)
        val op = st.op.removeSuffix("=")
        when (val t = st.target) {
            is Ex.Name -> {
                val (place, b) = assignPlace(scope, t.name, st.line)
                val check = b.type
                val v = if (op.isEmpty()) value else binop(op, st.line, if (place is LocalPlace) LocalGet(st.line, place.slot, b) else PlaceGet(st.line, place, t.name), value)
                if (place is LocalPlace && pureInt(v) && (check == null || check.text == "int"))
                    return SetLongS(st.line, place, if (v is IntFast) v.e else v, check, t.name)
                return SetPlace(st.line, place, v, check, t.name)
            }
            is Ex.Attr -> {
                val obj = expr(t.obj, scope)
                return AttrSet(st.line, obj, t.name, value, if (op.isEmpty()) null else { a, b -> binopFn(op)(a, b) })
            }
            is Ex.Index -> {
                if (t.index is Ex.Slice) error("cannot assign to a slice - change items one by one", st.line)
                return IndexSet(st.line, expr(t.obj, scope), expr(t.index, scope), value,
                    if (op.isEmpty()) null else { a, b -> binopFn(op)(a, b) })
            }
            is Ex.TupleLit -> {
                if (op.isNotEmpty()) error("$op= needs one target, not several", st.line)
                val targets = t.items.map { item ->
                    when (item) {
                        is Ex.Name -> { val (p, b) = assignPlace(scope, item.name, st.line); TupleTarget(p, null, null, null, b.type, item.name) }
                        is Ex.Attr -> TupleTarget(null, expr(item.obj, scope), item.name, null, null, "")
                        is Ex.Index -> TupleTarget(null, expr(item.obj, scope), null, expr(item.index, scope), null, "")
                        else -> error("cannot assign to that", st.line)
                    }
                }
                return TupleAssign(st.line, targets, value)
            }
            else -> error("cannot assign to that", st.line)
        }
    }

    private fun binopFn(op: String): (Any?, Any?) -> Any? = when (op) {
        "+" -> Ops::add; "-" -> Ops::sub; "*" -> Ops::mul; "/" -> Ops::div; "//" -> Ops::floorDiv
        "%" -> Ops::mod; "**" -> Ops::pow
        else -> throw IllegalStateException(op)
    }

    /** Compiles a function. Its params and body live in a new FuncCtx. */
    private fun function(name: String, params: List<Param>, ret: TypeRef?, body: List<St>, scope: Scope, line: Int,
                         kind: String): FnProto {
        val func = FuncCtx(scope.func, kind, name)
        val inner = Scope(scope, func)
        val infos = ArrayList<ParamInfo>()
        for (p in params) {
            if (p.name in inner.names) error("parameter ${p.name} is listed twice", line)
            val b = declare(inner, p.name, if (p.name == "self") "self" else "param", line, mutable = p.name != "self")
            infos.add(ParamInfo(p.name, LocalPlace(b.slot, b), null, p.rest, null))
        }
        // defaults and types are compiled once every param is known
        val withDefaults = params.mapIndexed { i, p ->
            ParamInfo(p.name, infos[i].place, p.default?.let { expr(it, inner) }, p.rest, typeCheck(p.type, inner, line))
        }
        func.ret = typeCheck(ret, inner, line)
        val blk = block(body, Scope(inner, func), implicitReturn = true)
        val proto = FnProto(name, withDefaults, func.nslots, func.ups, rt)
        proto.body = blk
        protos.add(proto to blk)
        proto.ret = func.ret
        proto.retAcceptsNil = ret == null || acceptsNil(ret)
        return proto
    }

    private fun stReturn(st: St.Return, scope: Scope): S {
        val func = scope.func!!
        if ((func.kind == "main") && !st.implicit)
            error("return is only for inside a fn - to stop the program, use exit()", st.line)
        return ReturnS(st.line, st.value?.let { expr(it, scope) })
    }

    private fun structFields(st: St.Struct, scope: Scope): List<Param> {
        val fields = ArrayList<Param>()
        if (st.parent != null) {
            val parent = structs[st.parent] ?: run {
                val pb = lookup(scope, st.parent)
                if (pb == null || pb.kind != "struct")
                    error("struct ${st.name} extends ${st.parent}, which is not a struct declared before it", st.line)
                structs[st.parent]!!
            }
            fields.addAll(parent.fields)
        }
        val own = fields.map { it.name }.toMutableSet()
        for ((k, f) in st.fields.withIndex()) {
            if (!own.add(f.name)) error("${st.name} already has a field ${f.name}", st.fieldLines[k])
            fields.add(f)
        }
        return fields
    }

    private fun stStruct(st: St.Struct, scope: Scope): S {
        val b = scope.names[st.name]!!
        val fields = structs[st.name]!!.fields
        val initFunc = FuncCtx(scope.func, "init", st.name)
        val initScope = Scope(scope, initFunc)
        val defaults = fields.map { f -> f.default?.let { expr(it, initScope) } }
        val checks = fields.map { f -> typeCheck(f.type, initScope, st.line) }
        val initProto = FnProto(st.name, emptyList(), initFunc.nslots, initFunc.ups, rt)
        initProto.body = BlockS(0, emptyArray(), emptyList())
        val methods = st.methods.map { m ->
            val isMethod = m.params.isNotEmpty() && m.params[0].name == "self"
            Triple(m.name, isMethod, function("${st.name}.${m.name}", m.params, m.ret, m.body!!, scope, m.line,
                if (isMethod) "method" else "fn"))
        }
        val parent = st.parent?.let { ref(scope, it, st.line) }
        val traits = st.impls.map { name ->
            val tb = lookup(scope, name)
            if (tb == null || tb.kind != "trait") error("$name is not a trait - declare it: trait $name { fn ... }", st.line)
            ref(scope, name, st.line)
        }
        return StructDef(st.line, st.name, fields.map { it.name }.toTypedArray(), defaults, checks, MakeFn(st.line, initProto),
            methods, parent, traits, LocalPlace(b.slot, b))
    }

    private fun stEnum(st: St.EnumS, scope: Scope): S {
        val b = scope.names[st.name]!!
        val values = st.variants.map { v -> v.value?.let { expr(it, scope) } }
        val methods = st.methods.map { m ->
            val isMethod = m.params.isNotEmpty() && m.params[0].name == "self"
            Triple(m.name, isMethod, function("${st.name}.${m.name}", m.params, m.ret, m.body!!, scope, m.line,
                if (isMethod) "method" else "fn"))
        }
        return EnumDef(st.line, st.name, st.variants.map { it.name }, values,
            st.variants.map { v -> v.fields?.map { it.name }?.toTypedArray() }, methods, LocalPlace(b.slot, b))
    }

    private fun stTrait(st: St.Trait, scope: Scope): S {
        val b = scope.names[st.name]!!
        val required = st.methods.filter { it.body == null }.map { it.name }
        val defaults = st.methods.filter { it.body != null }.map { m ->
            m.name to function("${st.name}.${m.name}", m.params, m.ret, m.body!!, scope, m.line, "method")
        }
        return TraitDef(st.line, st.name, required, defaults, LocalPlace(b.slot, b))
    }

    private fun stFor(st: St.For, scope: Scope): S {
        val func = scope.func!!
        val iter: N
        var rangeLo: N? = null
        var rangeHi: N? = null
        var inclusive = false
        if (st.iter is Ex.RangeE) {
            rangeLo = expr(st.iter.lo, scope); rangeHi = expr(st.iter.hi, scope); inclusive = st.iter.inclusive
            iter = Const(st.line, null)
        } else iter = expr(st.iter, scope)
        val inner = Scope(scope, func)
        val vars = st.names.map { declare(inner, it, "loop", st.line) }
        func.loops++
        val body = block(st.body, Scope(inner, func))
        func.loops--
        return ForS(st.line, vars.map { it.slot }.toIntArray(), vars.toTypedArray(), iter, rangeLo, rangeHi, inclusive, body, rt)
    }

    private fun stUse(st: St.Use, scope: Scope): S {
        if (st.path != null) {
            val b = scope.names[st.alias]!!
            b.live = true
            return UseS(st.line, listOf(LocalPlace(b.slot, b) to null), null, st.path, filename, rt)
        }
        val root = st.module!!.split(".")[0]
        if (root !in Libs.NAMES && !rt.hasPackage(root)) {
            val close = Similar.closest(root, Libs.NAMES)?.let { " - did you mean $it?" } ?: "."
            error("there is no library called ${st.module}$close There are: ${Libs.NAMES.sorted().joinToString(", ")}" +
                    " - or add a package: pcmd add $root", st.line)
        }
        if (st.names != null) {
            val places = st.names.map { n -> val b = scope.names[n]!!; b.live = true; (LocalPlace(b.slot, b) as Place) to n }
            return UseS(st.line, places, root, null, filename, rt)
        }
        val b = scope.names[st.alias]!!
        b.live = true
        return UseS(st.line, listOf(LocalPlace(b.slot, b) to null), root, null, filename, rt)
    }

    // ------------------------------------------------------------ match
    private fun pattern(p: Pat, scope: Scope, binds: Scope, line: Int): PM = when (p) {
        is Pat.Any_ -> PM { _, _ -> true }
        is Pat.Lit -> {
            val v = p.value
            if (v == null || v is Boolean) PM { x, _ -> x == v && (x == null || x is Boolean) } else PM { x, _ -> Ops.eq(x, v) }
        }
        is Pat.Bind -> {
            if (p.name in binds.names) error("the pattern binds ${p.name} twice", line)
            val b = declare(binds, p.name, "match", line)
            val place = LocalPlace(b.slot, b)
            PM { x, f -> place.set(f, x); true }
        }
        is Pat.Range -> PM { x, _ ->
            try {
                Ops.compare(p.lo, x) <= 0 && (if (p.inclusive) Ops.compare(x, p.hi) <= 0 else Ops.compare(x, p.hi) < 0)
            } catch (e: PcError) { false }
        }
        is Pat.Value -> {
            val target = attrChain(p.parts, scope, line)
            PM { x, f -> Ops.eq(x, target.ev(f)) }
        }
        is Pat.Type -> {
            val test = typeTest(p.type, scope, line)
            if (test == null) PM { _, _ -> true } else PM { x, f -> test(x, f) }
        }
        is Pat.Or -> {
            val before = binds.names.size
            val alts = p.alts.map { pattern(it, scope, binds, line) }
            if (binds.names.size != before) error("a | pattern cannot bind names", line)
            PM { x, f -> alts.any { it.m(x, f) } }
        }
        is Pat.Rest -> error("... only works inside a list pattern", line)
        is Pat.ListP -> {
            val restAt = p.items.indexOfFirst { it is Pat.Rest }
            val n = p.items.size - if (restAt >= 0) 1 else 0
            val after = if (restAt >= 0) p.items.size - restAt - 1 else 0
            val subs = p.items.mapIndexed { i, item ->
                if (item is Pat.Rest) {
                    if (item.name == "_") null else {
                        val b = declare(binds, item.name, "match", line)
                        val place = LocalPlace(b.slot, b)
                        PM { x, f ->
                            val items = Ops.toList(x)
                            place.set(f, PList(ArrayList(items.subList(i, items.size - after)))); true
                        }
                    }
                } else pattern(item, scope, binds, line)
            }
            PM { x, f ->
                val items: List<Any?> = when (x) { is PList -> x.items; is PTuple -> x.items; is PRange -> Ops.toList(x); else -> return@PM false }
                if (if (restAt >= 0) items.size < n else items.size != n) return@PM false
                for ((i, sub) in subs.withIndex()) {
                    if (sub == null) continue
                    if (i == restAt) { if (!sub.m(x, f)) return@PM false; continue }
                    val v = if (restAt in 0 until i) items[items.size - (p.items.size - i)] else items[i]
                    if (!sub.m(v, f)) return@PM false
                }
                true
            }
        }
        is Pat.StructP -> {
            val sb = resolve(scope, p.name, line)
            if (sb.kind != "struct") error("${p.name} is not a struct, so it cannot be a pattern like ${p.name}(...)", line)
            val fields = structs[p.name]?.fields?.map { it.name } ?: emptyList()
            val typeNode = ref(scope, p.name, line)
            val subs = p.subs.mapIndexed { i, (key, sub) ->
                val field = if (key == null) fields.getOrNull(i) ?: error("${p.name} has only ${fields.size} fields", line)
                else if (key in fields) key else error("${p.name} has no field $key", line)
                fields.indexOf(field) to pattern(sub, scope, binds, line)
            }
            PM { x, f ->
                x is StructObj && x.type.isA(typeNode.ev(f) as StructType) && subs.all { (k, m) -> m.m(x.values[k], f) }
            }
        }
        is Pat.VariantP -> {
            val target = attrChain(p.parts, scope, line)
            val subs = p.subs.map { (key, sub) -> key to pattern(sub, scope, binds, line) }
            PM { x, f ->
                val v = target.ev(f)
                if (x !is VariantObj || x.variant !== v) return@PM false
                val fields = x.variant.fields!!
                for ((i, pair) in subs.withIndex()) {
                    val k = if (pair.first == null) i else fields.indexOf(pair.first)
                    if (k < 0 || k >= x.values.size) throw Errors.type("${x.variant} has no field ${pair.first ?: i}")
                    if (!pair.second.m(x.values[k], f)) return@PM false
                }
                true
            }
        }
    }

    private fun attrChain(parts: List<String>, scope: Scope, line: Int): N {
        var node: N = ref(scope, parts[0], line)
        for (part in parts.drop(1)) node = AttrGet(line, node, part)
        return node
    }

    private fun armsOf(arms: List<Arm>, scope: Scope, needValue: Boolean): List<ArmCode> = arms.map { arm ->
        val binds = Scope(scope, scope.func)
        val pm = pattern(arm.pattern, scope, binds, arm.line)
        val guard = arm.guard?.let { expr(it, binds) }
        if (needValue && arm.expr == null)
            error("in a match that gives a value, each arm needs a value: pattern => value", arm.line)
        val body = arm.body?.let { block(it, Scope(binds, scope.func)) }
        val e = arm.expr?.let { x -> if (x is Ex.MapLit && x.pairs.isEmpty() && !needValue) null else expr(x, binds) }
        ArmCode(pm, guard, body, e)
    }

    private fun matchStmt(st: St.MatchS, scope: Scope): S = MatchS(st.line, expr(st.subject, scope), armsOf(st.arms, scope, false))

    // ------------------------------------------------------------ expressions
    fun expr(e: Ex, scope: Scope): N = when (e) {
        is Ex.Const -> Const(e.line, e.value)
        is Ex.Name -> ref(scope, e.name, e.line)
        is Ex.Self_ -> {
            val b = lookup(scope, "self") ?: error("self is only for inside a struct's methods: fn name(self) { ... }", e.line)
            ref(scope, b.name, e.line)
        }
        is Ex.Group -> expr(e.expr, scope)
        is Ex.Interp -> Interp(e.line, e.parts.map { p ->
            if (p is String) p else { p as Ex.InterpPart; InterpPiece(expr(p.expr, scope), p.spec) }
        }.toTypedArray())
        is Ex.ListLit -> ListN(e.line, e.items.map { item(it, scope) }.toTypedArray())
        is Ex.TupleLit -> TupleN(e.line, e.items.map { item(it, scope) }.toTypedArray())
        is Ex.MapLit -> MapN(e.line, e.pairs.map { (k, v) -> k?.let { expr(it, scope) } to expr(v, scope) })
        is Ex.ListComp -> comprehension(e.loops, e.cond, scope, e.line) { inner -> listOf(expr(e.expr, inner)) }
            .let { (loops, cond, outs) -> CompN(e.line, loops, cond, outs[0], null, rt) }
        is Ex.MapComp -> comprehension(e.loops, e.cond, scope, e.line) { inner -> listOf(expr(e.key, inner), expr(e.value, inner)) }
            .let { (loops, cond, outs) -> CompN(e.line, loops, cond, outs[0], outs[1], rt) }
        is Ex.Unary -> {
            val v = expr(e.operand, scope)
            when (e.op) {
                "not" -> Un(e.line, v) { !Ops.truthy(it) }
                "-" -> Un(e.line, v) { Ops.neg(it) }
                else -> Un(e.line, v) { Ops.pos(it) }
            }
        }
        is Ex.Binary -> binop(e.op, e.line, expr(e.left, scope), expr(e.right, scope))
        is Ex.Compare -> {
            val items = e.items.map { expr(it, scope) }
            if (items.size == 2) CompareN(e.line, e.ops[0], items[0], items[1]).also { it.pure = pureInt(items[0]) && pureInt(items[1]) }
            else ChainN(e.line, e.ops.toTypedArray(), items.toTypedArray())
        }
        is Ex.Logic -> if (e.op == "and") And(e.line, expr(e.left, scope), expr(e.right, scope))
        else Or(e.line, expr(e.left, scope), expr(e.right, scope))
        is Ex.Ternary -> Ternary(e.line, expr(e.cond, scope), expr(e.a, scope), expr(e.b, scope))
        is Ex.Coalesce -> Coalesce(e.line, expr(e.left, scope), expr(e.right, scope))
        is Ex.Is -> {
            val test = typeTest(e.type, scope, e.line)
            val v = expr(e.value, scope)
            IsN(e.line, v, test, e.negate)
        }
        is Ex.RangeE -> RangeN(e.line, expr(e.lo, scope), expr(e.hi, scope), e.inclusive)
        is Ex.Pipe -> {
            val f = e.func
            if (f is Ex.Call) expr(Ex.Call(f.line, f.func, listOf(e.value) + f.args, f.kwargs), scope)
            else expr(Ex.Call(e.line, f, listOf(e.value), emptyList()), scope)
        }
        is Ex.Attr -> AttrGet(e.line, expr(e.obj, scope), e.name)
        is Ex.OptAttr -> OptAttr(e.line, expr(e.obj, scope), e.name)
        is Ex.Index -> {
            val i = e.index
            if (i is Ex.Slice) SliceN(e.line, expr(e.obj, scope), i.start?.let { expr(it, scope) },
                i.stop?.let { expr(it, scope) }, i.step?.let { expr(it, scope) })
            else IndexN(e.line, expr(e.obj, scope), expr(i, scope))
        }
        is Ex.Call -> call(e, scope)
        is Ex.Spread -> error("... only works inside a list or a call", e.line)
        is Ex.Slice -> error("a slice only works inside [ ]", e.line)
        is Ex.Lambda -> {
            if (scope.hidden && e.body != null) {
                // fine on this engine: closures see comprehension names directly
            }
            val body = e.body ?: listOf(St.Return(e.line, e.expr))
            MakeFn(e.line, function("", e.params, e.ret, body, scope, e.line, "lambda"))
        }
        is Ex.MatchE -> MatchE(e.line, expr(e.subject, scope), armsOf(e.arms, scope, true))
        is Ex.InterpPart -> error("internal: interp part", 0)
    }

    private fun item(x: Ex, scope: Scope): N = if (x is Ex.Spread) SpreadN(x.line, expr(x.expr, scope)) else expr(x, scope)

    private fun comprehension(loops: List<CompLoop>, cond: Ex?, scope: Scope, line: Int,
                              outs: (Scope) -> List<N>): Triple<List<CompLoopCode>, N?, List<N>> {
        var inner = scope
        val code = ArrayList<CompLoopCode>()
        for (l in loops) {
            val iter = expr(l.iter, inner)
            inner = Scope(inner, scope.func, hidden = true)
            val vars = l.names.map { declare(inner, it, "loop", l.line) }
            code.add(CompLoopCode(iter, vars.map { LocalPlace(it.slot, it) as Place }.toTypedArray(), vars.toTypedArray()))
        }
        val c = cond?.let { expr(it, inner) }
        return Triple(code, c, outs(inner))
    }

    private fun call(e: Ex.Call, scope: Scope): N {
        val args = e.args.map { item(it, scope) }.toTypedArray()
        val spread = args.any { it is SpreadN }
        val kw = e.kwargs.map { it.first to expr(it.second, scope) }
        val f = e.func
        return when (f) {
            is Ex.Attr -> CallAttr(e.line, expr(f.obj, scope), f.name, args, kw, spread)
            is Ex.OptAttr -> OptCall(e.line, expr(f.obj, scope), f.name, args, kw, spread)
            else -> CallN(e.line, expr(f, scope), args, kw, spread)
        }
    }
}

/** A difflib-style "did you mean": the closest name that is at least 70% alike. */
object Similar {
    fun ratio(a: String, b: String): Double {
        if (a.isEmpty() && b.isEmpty()) return 1.0
        val dp = Array(a.length + 1) { IntArray(b.length + 1) }
        for (i in 1..a.length) for (j in 1..b.length)
            dp[i][j] = if (a[i - 1] == b[j - 1]) dp[i - 1][j - 1] + 1 else maxOf(dp[i - 1][j], dp[i][j - 1])
        return 2.0 * dp[a.length][b.length] / (a.length + b.length)
    }

    fun closest(name: String, options: Collection<String>): String? =
        options.map { it to ratio(name, it) }.filter { it.second >= 0.7 && it.first != name }
            .maxWithOrNull(compareBy<Pair<String, Double>> { it.second }.thenByDescending { it.first })?.first
}
