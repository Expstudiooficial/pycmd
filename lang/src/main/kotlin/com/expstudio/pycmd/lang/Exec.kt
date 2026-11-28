package com.expstudio.pycmd.lang

import java.math.BigInteger

// ====================================================================== statements

class Nop(line: Int) : S(line) { override fun ex(f: Frame) = NORMAL }

class ExprStmt(line: Int, @JvmField val e: N) : S(line) {
    override fun ex(f: Frame): Int { e.ev(f); return NORMAL }
}

class LetS(line: Int, @JvmField val place: Place, @JvmField val value: N?, val type: TCheck?, val name: String) : S(line) {
    override fun ex(f: Frame): Int {
        val v = value?.ev(f)
        place.set(f, v)
        if (value != null) type?.check(v, f, name)
        return NORMAL
    }
}

class SetPlace(line: Int, @JvmField val place: Place, @JvmField val value: N, val type: TCheck? = null, val name: String = "") : S(line) {
    override fun ex(f: Frame): Int {
        val v = value.ev(f)
        place.set(f, v)
        type?.check(v, f, name)
        return NORMAL
    }
}

/** Arithmetic on locals, done unboxed; falls back to the general path for anything else. */
class IntFast(line: Int, @JvmField val e: N) : N(line) {
    override fun ev(f: Frame): Any? = try { e.evL(f) } catch (x: NotLong) { e.ev(f) }
    override fun evL(f: Frame): Long = e.evL(f)
}

class SetLongS(line: Int, @JvmField val place: LocalPlace, @JvmField val value: N, val type: TCheck?, val name: String) : S(line) {
    override fun ex(f: Frame): Int {
        try {
            place.setLong(f, value.evL(f))
            return NORMAL
        } catch (e: NotLong) {
        }
        val v = value.ev(f)
        place.set(f, v)
        type?.check(v, f, name)
        return NORMAL
    }
}

class PlaceGet(line: Int, @JvmField val place: Place, val name: String) : N(line) {
    override fun ev(f: Frame): Any? {
        val v = place.get(f)
        if (v === Unset) throw Errors.name("$name is used before it has a value")
        return v
    }
}

class UnpackS(line: Int, val places: List<Place>, val restAt: Int, val value: N) : S(line) {
    override fun ex(f: Frame): Int {
        val items = Ops.toList(value.ev(f))
        assignSeq(places, restAt, items) { p, v -> p.set(f, v) }
        return NORMAL
    }

    companion object {
        fun <P> assignSeq(places: List<P>, restAt: Int, items: List<Any?>, set: (P, Any?) -> Unit) {
            if (restAt < 0) {
                if (items.size < places.size) throw Errors.value("not enough items to unpack")
                if (items.size > places.size) throw Errors.value("too many items to unpack")
                for (i in places.indices) set(places[i], items[i])
                return
            }
            val after = places.size - restAt - 1
            if (items.size < places.size - 1) throw Errors.value("not enough items to unpack")
            for (i in 0 until restAt) set(places[i], items[i])
            set(places[restAt], PList(ArrayList(items.subList(restAt, items.size - after))))
            for (k in 0 until after) set(places[restAt + 1 + k], items[items.size - after + k])
        }
    }
}

class AttrSet(line: Int, val obj: N, val name: String, val value: N, val op: ((Any?, Any?) -> Any?)?) : S(line) {
    override fun ex(f: Frame): Int {
        val o = obj.ev(f)
        val v = value.ev(f)
        Builtins.setAttr(o, name, if (op == null) v else op.invoke(Builtins.getAttr(o, name), v))
        return NORMAL
    }
}

class IndexSet(line: Int, val obj: N, val index: N, val value: N, val op: ((Any?, Any?) -> Any?)?) : S(line) {
    override fun ex(f: Frame): Int {
        val o = obj.ev(f)
        val i = index.ev(f)
        val v = value.ev(f)
        Ops.setIndex(o, i, if (op == null) v else op.invoke(Ops.getIndex(o, i), v))
        return NORMAL
    }
}

class TupleTarget(val place: Place?, val obj: N?, val attr: String?, val index: N?, val type: TCheck?, val name: String)

class TupleAssign(line: Int, val targets: List<TupleTarget>, val value: N) : S(line) {
    override fun ex(f: Frame): Int {
        val items = Ops.toList(value.ev(f))
        // work out every target's object and index first, as Python does
        val objs = targets.map { it.obj?.ev(f) }
        val idxs = targets.map { it.index?.ev(f) }
        UnpackS.assignSeq(targets.indices.toList(), -1, items) { k, v ->
            val t = targets[k]
            when {
                t.place != null -> { t.place.set(f, v); t.type?.check(v, f, t.name) }
                t.attr != null -> Builtins.setAttr(objs[k], t.attr, v)
                else -> Ops.setIndex(objs[k], idxs[k], v)
            }
        }
        return NORMAL
    }
}

class IfS(line: Int, @JvmField val conds: Array<N>, @JvmField val bodies: Array<BlockS>, @JvmField val other: BlockS?) : S(line) {
    override fun ex(f: Frame): Int {
        for (i in conds.indices) {
            if (Ops.truthy(conds[i].ev(f))) return bodies[i].ex(f)
        }
        return other?.ex(f) ?: NORMAL
    }
}

class WhileS(line: Int, @JvmField val cond: N?, @JvmField val body: BlockS, @JvmField val rt: Runtime) : S(line) {
    override fun ex(f: Frame): Int {
        while (cond == null || Ops.truthy(cond.ev(f))) {
            if ((++rt.steps and 0x3FFF) == 0L) rt.check()
            val r = body.ex(f)
            if (r == BREAK) break
            if (r == RETURN) return RETURN
        }
        return NORMAL
    }
}

class ForS(
    line: Int, @JvmField val slots: IntArray, val vars: Array<Binding>, @JvmField val iter: N,
    @JvmField val lo: N?, @JvmField val hi: N?, val inclusive: Boolean, @JvmField val body: BlockS, @JvmField val rt: Runtime,
) : S(line) {
    private val one = slots.size == 1
    private val boxed: Boolean get() = vars.any { it.boxed }

    private fun assign(f: Frame, v: Any?) {
        if (one) {
            if (vars[0].boxed) f.slots[slots[0]] = Cell(v) else f.slots[slots[0]] = v
            return
        }
        val items = when (v) {
            is PTuple -> v.items
            is PList -> v.items
            else -> Ops.toList(v)
        }
        if (items.size != slots.size) throw Errors.value(if (items.size < slots.size) "not enough items to unpack" else "too many items to unpack")
        for (i in slots.indices) f.slots[slots[i]] = if (vars[i].boxed) Cell(items[i]) else items[i]
    }

    override fun ex(f: Frame): Int {
        if (lo != null) {
            val a = lo.ev(f); val b = hi!!.ev(f)
            if (a is Long && b is Long && one && !vars[0].boxed) {
                val end = if (inclusive) b + 1 else b
                var i = a
                val s = slots[0]
                while (i < end) {
                    f.setLong(s, i)
                    if ((++rt.steps and 0x3FFF) == 0L) rt.check()
                    val r = body.ex(f)
                    if (r == BREAK) break
                    if (r == RETURN) return RETURN
                    i++
                }
                return NORMAL
            }
            return loop(f, RangeN.make(a, b, inclusive))
        }
        val source = iter.ev(f)
        if (slots.size == 2 && source is PMap) {
            for ((k, v) in ArrayList(source.map.entries)) {
                assign(f, PTuple(listOf(k, v)))
                if ((++rt.steps and 0x3FFF) == 0L) rt.check()
                val r = body.ex(f)
                if (r == BREAK) break
                if (r == RETURN) return RETURN
            }
            return NORMAL
        }
        return loop(f, source)
    }

    private fun loop(f: Frame, source: Any?): Int {
        val it = Ops.iterate(source)
        while (it.hasNext()) {
            assign(f, it.next())
            if ((++rt.steps and 0x3FFF) == 0L) rt.check()
            val r = body.ex(f)
            if (r == BREAK) break
            if (r == RETURN) return RETURN
        }
        return NORMAL
    }
}

class Signal(line: Int, val signal: Int) : S(line) { override fun ex(f: Frame) = signal }

class ReturnS(line: Int, @JvmField val value: N?) : S(line) {
    override fun ex(f: Frame): Int {
        f.ret = value?.ev(f)
        return RETURN
    }
}

class ThrowS(line: Int, val value: N) : S(line) {
    override fun ex(f: Frame): Int {
        val v = value.ev(f)
        throw when (v) {
            is PcError -> v
            is StructObj -> PcError(Show.show(v), v.type.name, v)
            is VariantObj -> PcError(Show.show(v), v.variant.enum.name, v)
            is String -> PcError(v, "Error", v)
            else -> PcError(Show.show(v), "Error", v)
        }
    }
}

class AssertS(line: Int, val cond: N, val message: N?, val text: String) : S(line) {
    override fun ex(f: Frame): Int {
        if (!Ops.truthy(cond.ev(f))) {
            if (message != null) throw PcError(Show.show(message.ev(f)), "Assert")
            throw PcError("assert failed: $text", "Assert")
        }
        return NORMAL
    }
}

class TestS(line: Int, val name: String, val fn: MakeFn, val rt: Runtime) : S(line) {
    override fun ex(f: Frame): Int {
        rt.tests.add(Triple(name, fn.ev(f) as Callable, line))
        return NORMAL
    }
}

class TryS(line: Int, val body: BlockS, val catchPlace: Place?, val handler: BlockS?, val final: BlockS?) : S(line) {
    override fun ex(f: Frame): Int {
        try {
            return body.ex(f)
        } catch (t: Throwable) {
            if (handler == null) throw t
            val err = Runtime.asError(t) ?: throw t
            catchPlace?.set(f, err)
            return handler.ex(f)
        } finally {
            if (final != null) {
                val r = final.ex(f)
                if (r != NORMAL) return r
            }
        }
    }
}

class UseS(line: Int, val places: List<Pair<Place, String?>>, val lib: String?, val path: String?, val from: String,
           val rt: Runtime) : S(line) {
    override fun ex(f: Frame): Int {
        val module = if (path != null) rt.importFile(path, from) else rt.lib(lib!!)
        for ((place, member) in places) {
            if (member == null) place.set(f, module)
            else place.set(f, module.members[member] ?: throw Errors.name("library ${module.name} has no $member"))
        }
        return NORMAL
    }
}

class MakeFn(line: Int, val proto: FnProto) : N(line) {
    override fun ev(f: Frame): Any? {
        val ups = proto.ups
        if (ups.isEmpty()) return PcFunction(proto, null)
        val cells = Array(ups.size) { i ->
            val u = ups[i]
            if (u.fromParentSlot >= 0) {
                val c = f.slots[u.fromParentSlot]
                if (c is Cell) c else Cell(c ?: Unset).also { f.slots[u.fromParentSlot] = it }
            } else f.up!![u.fromParentUp]
        }
        return PcFunction(proto, cells)
    }
}

class StructDef(
    line: Int, val name: String, val fields: Array<String>, val defaults: List<N?>, val checks: List<TCheck?>,
    val initFn: MakeFn, val methods: List<Triple<String, Boolean, FnProto>>, val parent: N?, val traits: List<N>,
    val place: Place,
) : S(line) {
    override fun ex(f: Frame): Int {
        val parentType = parent?.ev(f) as StructType?
        val t = StructType(name, parentType, fields)
        val initClosure = initFn.ev(f) as PcFunction
        val nslots = initClosure.proto.nslots
        val plain = defaults.all { it == null } && checks.all { it == null }
        t.init = init@{ obj, args, kw ->
            if (plain && kw == null && args.size == fields.size) {
                System.arraycopy(args, 0, obj.values, 0, args.size)
                return@init
            }
            if (args.size > fields.size)
                throw Errors.type("$name takes ${fields.size} value${if (fields.size == 1) "" else "s"} but ${args.size} were given")
            val set = BooleanArray(fields.size)
            for (i in args.indices) { obj.values[i] = args[i]; set[i] = true }
            if (kw != null) for ((k, v) in kw) {
                val i = t.index[k] ?: throw Errors.type("$name has no field $k")
                if (set[i]) throw Errors.type("$name got two values for $k")
                obj.values[i] = v; set[i] = true
            }
            var frame: Frame? = null
            for (i in fields.indices) {
                if (!set[i]) {
                    val d = defaults[i] ?: throw Errors.type("$name needs a value for ${fields[i]}: $name(${fields[i]}: ...)")
                    if (frame == null) frame = Frame(arrayOfNulls(nslots), initClosure.up)
                    obj.values[i] = d.ev(frame)
                }
                val c = checks[i]
                if (c != null) c.check(obj.values[i], frame ?: Frame(arrayOfNulls(nslots), initClosure.up).also { frame = it }, "$name.${fields[i]}")
            }
        }
        for ((mname, isMethod, proto) in methods) {
            val fn = MakeFn(line, proto).ev(f) as Callable
            if (isMethod) t.methods[mname] = fn else t.statics[mname] = fn
        }
        for (tn in traits) {
            val trait = tn.ev(f) as TraitType
            t.traits.add(trait)
            for ((m, fn) in trait.defaults) if (t.findMethod(m) == null) t.methods[m] = fn
            for (m in trait.required) if (t.findMethod(m) == null)
                throw PcError("$name says it is a ${trait.name}, but has no fn $m(self) - a ${trait.name} needs it", "Type", null, line)
        }
        place.set(f, t)
        return NORMAL
    }
}

class EnumDef(line: Int, val name: String, val names: List<String>, val values: List<N?>, val fields: List<Array<String>?>,
              val methods: List<Triple<String, Boolean, FnProto>>, val place: Place) : S(line) {
    override fun ex(f: Frame): Int {
        val e = EnumType(name)
        for (i in names.indices) {
            val v = Variant(e, names[i], i, values[i]?.ev(f) ?: i.toLong(), fields[i])
            e.variants.add(v); e.byName[names[i]] = v
        }
        for ((mname, _, proto) in methods) e.methods[mname] = MakeFn(line, proto).ev(f) as Callable
        place.set(f, e)
        return NORMAL
    }
}

class TraitDef(line: Int, val name: String, val required: List<String>, val defaults: List<Pair<String, FnProto>>,
               val place: Place) : S(line) {
    override fun ex(f: Frame): Int {
        place.set(f, TraitType(name, required, defaults.associate { (n, p) -> n to MakeFn(line, p).ev(f) as Callable }))
        return NORMAL
    }
}

fun interface PM { fun m(v: Any?, f: Frame): Boolean }

class ArmCode(val pm: PM, val guard: N?, val body: BlockS?, val expr: N?)

class MatchS(line: Int, val subject: N, val arms: List<ArmCode>) : S(line) {
    override fun ex(f: Frame): Int {
        val v = subject.ev(f)
        for (arm in arms) {
            if (!arm.pm.m(v, f)) continue
            if (arm.guard != null && !Ops.truthy(arm.guard.ev(f))) continue
            if (arm.body != null) return arm.body.ex(f)
            arm.expr?.ev(f)
            return NORMAL
        }
        return NORMAL
    }
}

class MatchE(line: Int, val subject: N, val arms: List<ArmCode>) : N(line) {
    override fun ev(f: Frame): Any? {
        val v = subject.ev(f)
        for (arm in arms) {
            if (!arm.pm.m(v, f)) continue
            if (arm.guard != null && !Ops.truthy(arm.guard.ev(f))) continue
            return arm.expr!!.ev(f)
        }
        return null
    }
}

// ====================================================================== expressions

class InterpPiece(val node: N, val spec: String?)

class Interp(line: Int, @JvmField val parts: Array<Any>) : N(line) {
    override fun ev(f: Frame): Any? {
        val sb = StringBuilder()
        for (p in parts) {
            if (p is String) sb.append(p)
            else {
                p as InterpPiece
                val v = p.node.ev(f)
                sb.append(if (p.spec != null) Show.format(v, p.spec) else Show.show(v))
            }
        }
        return sb.toString()
    }
}

class SpreadN(line: Int, val e: N) : N(line) { override fun ev(f: Frame) = e.ev(f) }

private fun collect(items: Array<N>, f: Frame): ArrayList<Any?> {
    val out = ArrayList<Any?>(items.size)
    for (n in items) {
        if (n is SpreadN) out.addAll(Ops.toList(n.e.ev(f))) else out.add(n.ev(f))
    }
    return out
}

class ListN(line: Int, @JvmField val items: Array<N>) : N(line) {
    override fun ev(f: Frame) = PList(collect(items, f))
}

class TupleN(line: Int, @JvmField val items: Array<N>) : N(line) {
    override fun ev(f: Frame) = PTuple(collect(items, f))
}

class MapN(line: Int, val pairs: List<Pair<N?, N>>) : N(line) {
    override fun ev(f: Frame): Any? {
        val m = PMap()
        for ((k, v) in pairs) {
            if (k == null) {
                val other = v.ev(f) as? PMap ?: throw Errors.type("... in a map needs another map")
                m.map.putAll(other.map)
            } else m.map[Ops.key(k.ev(f))] = v.ev(f)
        }
        return m
    }
}

class CompLoopCode(val iter: N, val places: Array<Place>, val vars: Array<Binding>)

class CompN(line: Int, val loops: List<CompLoopCode>, val cond: N?, val out: N, val value: N?, val rt: Runtime) : N(line) {
    override fun ev(f: Frame): Any? {
        val list = if (value == null) ArrayList<Any?>() else null
        val map = if (value != null) PMap() else null
        run(0, f, list, map)
        return list?.let { PList(it) } ?: map
    }

    private fun run(depth: Int, f: Frame, list: ArrayList<Any?>?, map: PMap?) {
        if (depth == loops.size) {
            if (cond != null && !Ops.truthy(cond.ev(f))) return
            if (list != null) list.add(out.ev(f)) else map!!.map[Ops.key(out.ev(f))] = value!!.ev(f)
            return
        }
        val l = loops[depth]
        val src = l.iter.ev(f)
        val it = if (l.places.size == 2 && src is PMap) ArrayList(src.map.entries).map { PTuple(listOf(it.key, it.value)) }.iterator()
        else Ops.iterate(src)
        while (it.hasNext()) {
            val v = it.next()
            if (l.places.size == 1) {
                if (l.vars[0].boxed) f.slots[l.vars[0].slot] = Cell(v) else l.places[0].set(f, v)
            } else {
                val items = Ops.toList(v)
                if (items.size != l.places.size) throw Errors.value("not enough items to unpack")
                for (i in l.places.indices) {
                    if (l.vars[i].boxed) f.slots[l.vars[i].slot] = Cell(items[i]) else l.places[i].set(f, items[i])
                }
            }
            if ((++rt.steps and 0x3FFF) == 0L) rt.check()
            run(depth + 1, f, list, map)
        }
    }
}

class Un(line: Int, @JvmField val a: N, val op: (Any?) -> Any?) : N(line) {
    override fun ev(f: Frame) = op(a.ev(f))
}

class Bin(line: Int, @JvmField val a: N, @JvmField val b: N, val op: (Any?, Any?) -> Any?) : N(line) {
    override fun ev(f: Frame) = op(a.ev(f), b.ev(f))
}

class Add(line: Int, @JvmField val a: N, @JvmField val b: N) : N(line) {
    override fun evL(f: Frame): Long {
        val x = a.evL(f); val y = b.evL(f); val r = x + y
        if (((x xor r) and (y xor r)) < 0) throw NotLong
        return r
    }
    override fun ev(f: Frame): Any? {
        val x = a.ev(f); val y = b.ev(f)
        if (x is Long && y is Long) {
            val r = x + y
            if (((x xor r) and (y xor r)) >= 0) return r
        }
        return Ops.add(x, y)
    }
}

class Sub(line: Int, @JvmField val a: N, @JvmField val b: N) : N(line) {
    override fun evL(f: Frame): Long {
        val x = a.evL(f); val y = b.evL(f); val r = x - y
        if (((x xor y) and (x xor r)) < 0) throw NotLong
        return r
    }
    override fun ev(f: Frame): Any? {
        val x = a.ev(f); val y = b.ev(f)
        if (x is Long && y is Long) {
            val r = x - y
            if (((x xor y) and (x xor r)) >= 0) return r
        }
        return Ops.sub(x, y)
    }
}

class Mul(line: Int, @JvmField val a: N, @JvmField val b: N) : N(line) {
    override fun evL(f: Frame): Long {
        val x = a.evL(f); val y = b.evL(f)
        val hi = Math.multiplyHigh(x, y); val lo = x * y
        if ((hi == 0L && lo >= 0) || (hi == -1L && lo < 0)) return lo
        throw NotLong
    }
    override fun ev(f: Frame) = Ops.mul(a.ev(f), b.ev(f))
}

class FloorDiv(line: Int, @JvmField val a: N, @JvmField val b: N) : N(line) {
    override fun evL(f: Frame): Long {
        val x = a.evL(f); val y = b.evL(f)
        if (y == 0L || (x == Long.MIN_VALUE && y == -1L)) throw NotLong
        return Math.floorDiv(x, y)
    }
    override fun ev(f: Frame) = Ops.floorDiv(a.ev(f), b.ev(f))
}

class Mod(line: Int, @JvmField val a: N, @JvmField val b: N) : N(line) {
    override fun evL(f: Frame): Long {
        val x = a.evL(f); val y = b.evL(f)
        if (y == 0L) throw NotLong
        return Math.floorMod(x, y)
    }
    override fun ev(f: Frame): Any? {
        val x = a.ev(f); val y = b.ev(f)
        if (x is Long && y is Long && y > 0) return Math.floorMod(x, y)
        return Ops.mod(x, y)
    }
}

class CompareN(line: Int, val op: String, @JvmField val a: N, @JvmField val b: N) : N(line) {
    private val code = when (op) { "==" -> 0; "!=" -> 1; "<" -> 2; "<=" -> 3; ">" -> 4; else -> 5 }
    /** Both sides are plain arithmetic on locals: try them unboxed first. */
    @JvmField var pure = false
    override fun ev(f: Frame): Any? {
        if (pure) {
            try {
                val x = a.evL(f); val y = b.evL(f)
                return when (code) { 0 -> x == y; 1 -> x != y; 2 -> x < y; 3 -> x <= y; 4 -> x > y; else -> x >= y }
            } catch (e: NotLong) { }
        }
        return slow(f)
    }

    private fun slow(f: Frame): Any? {
        val x = a.ev(f); val y = b.ev(f)
        if (x is Long && y is Long) return when (code) {
            0 -> x == y; 1 -> x != y; 2 -> x < y; 3 -> x <= y; 4 -> x > y; else -> x >= y
        }
        return when (code) {
            0 -> Ops.eq(x, y); 1 -> !Ops.eq(x, y)
            2 -> Ops.compare(x, y, op) < 0; 3 -> Ops.compare(x, y, op) <= 0
            4 -> Ops.compare(x, y, op) > 0; else -> Ops.compare(x, y, op) >= 0
        }
    }
}

class ChainN(line: Int, val ops: Array<String>, val items: Array<N>) : N(line) {
    override fun ev(f: Frame): Any? {
        var left = items[0].ev(f)
        for (i in ops.indices) {
            val right = items[i + 1].ev(f)
            if (!Ops.cmpOp(ops[i], left, right)) return false
            left = right
        }
        return true
    }
}

class And(line: Int, val a: N, val b: N) : N(line) {
    override fun ev(f: Frame): Any? { val x = a.ev(f); return if (!Ops.truthy(x)) x else b.ev(f) }
}

class Or(line: Int, val a: N, val b: N) : N(line) {
    override fun ev(f: Frame): Any? { val x = a.ev(f); return if (Ops.truthy(x)) x else b.ev(f) }
}

class Ternary(line: Int, val c: N, val a: N, val b: N) : N(line) {
    override fun ev(f: Frame) = if (Ops.truthy(c.ev(f))) a.ev(f) else b.ev(f)
}

class Coalesce(line: Int, val a: N, val b: N) : N(line) {
    override fun ev(f: Frame) = a.ev(f) ?: b.ev(f)
}

class IsN(line: Int, val v: N, val test: ((Any?, Frame) -> Boolean)?, val negate: Boolean) : N(line) {
    override fun ev(f: Frame): Any? {
        val x = v.ev(f)
        val r = test?.invoke(x, f) ?: true
        return if (negate) !r else r
    }
}

class RangeN(line: Int, val lo: N, val hi: N, val inclusive: Boolean) : N(line) {
    override fun ev(f: Frame) = make(lo.ev(f), hi.ev(f), inclusive)

    companion object {
        fun make(a: Any?, b: Any?, inclusive: Boolean): PRange {
            val x = (if (a is Boolean) (if (a) 1L else 0L) else a) as? Long
                ?: throw Errors.type("this needs a whole number (an int), not ${Show.typeName(a)}")
            val y = (if (b is Boolean) (if (b) 1L else 0L) else b) as? Long
                ?: throw Errors.type("this needs a whole number (an int), not ${Show.typeName(b)}")
            return PRange(x, if (inclusive) y + 1 else y, 1)
        }
    }
}

class AttrGet(line: Int, @JvmField val obj: N, @JvmField val name: String) : N(line) {
    // Inline cache: the last struct type seen here, and where the field sits in it.
    @JvmField var seen: StructType? = null
    @JvmField var at = -1
    override fun ev(f: Frame): Any? {
        val o = obj.ev(f)
        if (o is StructObj) {
            if (o.type === seen) return o.values[at]
            val i = o.type.index[name]
            if (i != null) { seen = o.type; at = i; return o.values[i] }
        }
        return Builtins.getAttr(o, name)
    }
}

class OptAttr(line: Int, val obj: N, val name: String) : N(line) {
    override fun ev(f: Frame): Any? { val o = obj.ev(f) ?: return null; return Builtins.getAttr(o, name) }
}

class IndexN(line: Int, @JvmField val obj: N, @JvmField val index: N) : N(line) {
    override fun ev(f: Frame): Any? {
        val o = obj.ev(f); val i = index.ev(f)
        if (o is PList && i is Long) {
            val items = o.items
            val j = if (i < 0) i + items.size else i
            if (j >= 0 && j < items.size) return items[j.toInt()]
        }
        return Ops.getIndex(o, i)
    }
}

class SliceN(line: Int, val obj: N, val a: N?, val b: N?, val c: N?) : N(line) {
    override fun ev(f: Frame) = Ops.slice(obj.ev(f), a?.ev(f), b?.ev(f), c?.ev(f))
}

private fun argsOf(args: Array<N>, spread: Boolean, f: Frame): Array<Any?> {
    if (!spread) return Array(args.size) { args[it].ev(f) }
    return collect(args, f).toTypedArray()
}

private fun kwOf(kw: List<Pair<String, N>>, f: Frame): Map<String, Any?>? {
    if (kw.isEmpty()) return null
    val m = LinkedHashMap<String, Any?>()
    for ((k, v) in kw) m[k] = v.ev(f)
    return m
}

class CallN(line: Int, @JvmField val fn: N, @JvmField val args: Array<N>, val kw: List<Pair<String, N>>, val spread: Boolean) : N(line) {
    override fun ev(f: Frame): Any? {
        val callee = fn.ev(f)
        val a = argsOf(args, spread, f)
        val k = kwOf(kw, f)
        if (callee is Callable) return callee.call(a, k)
        return Calls.call(callee, a, k)
    }
}

class CallAttr(line: Int, @JvmField val obj: N, @JvmField val name: String, @JvmField val args: Array<N>,
               val kw: List<Pair<String, N>>, val spread: Boolean) : N(line) {
    private val id = Builtins.methodId(name)
    @JvmField var seen: StructType? = null
    @JvmField var method: Callable? = null
    override fun ev(f: Frame): Any? {
        val o = obj.ev(f)
        if (o is StructObj && !spread && kw.isEmpty()) {
            var m = if (o.type === seen) method else null
            if (m == null) {
                m = o.type.findMethod(name)
                if (m != null) { seen = o.type; method = m }
            }
            if (m != null) {
                val all = arrayOfNulls<Any?>(args.size + 1)
                all[0] = o
                for (i in args.indices) all[i + 1] = args[i].ev(f)
                return m.call(all, null)
            }
        }
        return Builtins.callMethod(o, name, id, argsOf(args, spread, f), kwOf(kw, f))
    }
}

class OptCall(line: Int, val obj: N, val name: String, val args: Array<N>, val kw: List<Pair<String, N>>, val spread: Boolean) : N(line) {
    private val id = Builtins.methodId(name)
    override fun ev(f: Frame): Any? {
        val o = obj.ev(f) ?: return null
        return Builtins.callMethod(o, name, id, argsOf(args, spread, f), kwOf(kw, f))
    }
}

@Suppress("unused")
private val keepBig = BigInteger.ZERO
