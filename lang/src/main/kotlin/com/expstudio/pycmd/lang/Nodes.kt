package com.expstudio.pycmd.lang

import java.math.BigInteger

/*
 * The executable form of a program. The compiler resolves every name to an
 * array slot (or a captured Cell) ahead of time, so running it does no
 * name lookups at all - the main reason this engine is fast.
 */

class Frame(@JvmField val slots: Array<Any?>, @JvmField val up: Array<Cell>?) {
    @JvmField var ret: Any? = null
    @JvmField var line = 0
    /** Whole numbers kept unboxed: slots[i] === LTag means the value is longs[i]. */
    @JvmField var longs: LongArray? = null

    fun setLong(slot: Int, v: Long) {
        var l = longs
        if (l == null) { l = LongArray(slots.size); longs = l }
        l[slot] = v
        slots[slot] = LTag
    }
}

object LTag

/** "This value is not a plain 64-bit int" - the fast path gives way to the general one. */
object NotLong : RuntimeException() {
    private fun readResolve(): Any = NotLong
    override fun fillInStackTrace(): Throwable = this
}

/** Marks a captured variable that has not been given a value yet. */
object Unset

abstract class N(@JvmField val line: Int) {
    abstract fun ev(f: Frame): Any?
    /** The value as a plain long, or NotLong. Only called on side-effect-free trees. */
    open fun evL(f: Frame): Long = ev(f) as? Long ?: throw NotLong
}

/** Statement results. */
const val NORMAL = 0
const val BREAK = 1
const val CONTINUE = 2
const val RETURN = 3

abstract class S(@JvmField val line: Int) {
    abstract fun ex(f: Frame): Int
}

class Binding(
    val name: String,
    val mutable: Boolean,
    val kind: String,
    val line: Int,
    val func: FuncCtx,
    val slot: Int,
    var type: TCheck?,
) {
    @JvmField var boxed = false
    var live = true
    var node: N? = null        // a constant this name stands for (built-ins)
}

class BlockS(line: Int, @JvmField val stmts: Array<S>, val bindings: List<Binding>) : S(line) {
    @JvmField var cells: IntArray = IntArray(0)

    fun finish() {
        cells = bindings.filter { it.boxed }.map { it.slot }.toIntArray()
    }

    override fun ex(f: Frame): Int {
        val c = cells
        for (i in c.indices) f.slots[c[i]] = Cell(Unset)
        for (s in stmts) {
            f.line = s.line
            val r = s.ex(f)
            if (r != NORMAL) return r
        }
        return NORMAL
    }
}

// ---------------------------------------------------------------- variables

class Const(line: Int, @JvmField val value: Any?) : N(line) {
    private val asLong = value as? Long
    private val isLong = value is Long
    override fun ev(f: Frame) = value
    override fun evL(f: Frame): Long = if (isLong) asLong!! else throw NotLong
}

class LocalGet(line: Int, @JvmField val slot: Int, @JvmField val b: Binding) : N(line) {
    override fun ev(f: Frame): Any? {
        val v = f.slots[slot]
        if (v === LTag) return f.longs!![slot]
        if (b.boxed) {
            val x = (v as Cell).v
            if (x === Unset) throw Errors.name("${b.name} is used before it has a value")
            return x
        }
        return v
    }

    override fun evL(f: Frame): Long {
        val v = f.slots[slot]
        if (v === LTag) return f.longs!![slot]
        if (v is Long) return v
        if (v is Cell) { val x = v.v; if (x is Long) return x }
        throw NotLong
    }
}

class UpGet(line: Int, @JvmField val index: Int, @JvmField val name: String) : N(line) {
    override fun ev(f: Frame): Any? {
        val x = f.up!![index].v
        if (x === Unset) throw Errors.name("$name is used before it has a value")
        return x
    }
}

/** Where a name's value is written: its slot, its cell, or an outer function's cell. */
abstract class Place { abstract fun set(f: Frame, v: Any?); abstract fun get(f: Frame): Any? }

class LocalPlace(@JvmField val slot: Int, @JvmField val b: Binding) : Place() {
    override fun set(f: Frame, v: Any?) {
        if (b.boxed) {
            val c = f.slots[slot]
            if (c is Cell) c.v = v else f.slots[slot] = Cell(v)
        } else f.slots[slot] = v
    }
    override fun get(f: Frame): Any? {
        val v = f.slots[slot]
        if (v === LTag) return f.longs!![slot]
        return if (b.boxed) (v as Cell).v else v
    }

    /** Store a long without boxing it - only for names no closure captures. */
    fun setLong(f: Frame, v: Long) {
        if (b.boxed) set(f, v) else f.setLong(slot, v)
    }
}

class UpPlace(@JvmField val index: Int) : Place() {
    override fun set(f: Frame, v: Any?) { f.up!![index].v = v }
    override fun get(f: Frame) = f.up!![index].v
}

// ---------------------------------------------------------------- types

/** A declared type, checked at run time. */
class TCheck(val text: String, val test: (Any?, Frame) -> Boolean) {
    fun check(v: Any?, f: Frame, what: String) {
        if (!test(v, f)) {
            val got = if (v == null) "nil" else "${Show.typeName(v)} ${Show.quote(v)}"
            throw Errors.type("$what should be $text, but got $got")
        }
    }
}

// ---------------------------------------------------------------- functions

class ParamInfo(val name: String, val place: Place, val default: N?, val rest: Boolean, val type: TCheck?)

class Upval(val fromParentSlot: Int, val fromParentUp: Int)

class FnProto(
    val name: String,
    val params: List<ParamInfo>,
    val nslots: Int,
    val ups: List<Upval>,
    val rt: Runtime,
) {
    lateinit var body: BlockS
    /** Set when the body is one `return expr` and nothing in it needs a cell. */
    var direct: N? = null
    var ret: TCheck? = null
    var retAcceptsNil = true
    val positional = params.count { !it.rest }
    val hasRest = params.any { it.rest }
    val anyTyped = params.any { it.type != null }
    val byName: Map<String, Int> = params.withIndex().associate { it.value.name to it.index }
}

class PcFunction(val proto: FnProto, val up: Array<Cell>?) : Callable {
    override val name: String get() = proto.name

    override fun call(args: Array<Any?>, kw: Map<String, Any?>?): Any? {
        val p = proto
        val rt = p.rt
        val f = Frame(arrayOfNulls(p.nslots), up)
        val params = p.params
        val n = params.size
        // bind
        if (!p.hasRest && kw == null && args.size == n) {
            for (i in 0 until n) params[i].place.set(f, args[i])
            if (p.anyTyped) for (i in 0 until n) params[i].type?.check(args[i], f, "parameter ${params[i].name}")
        } else bindSlow(f, args, kw)
        if (++rt.depth > rt.maxDepth) {
            rt.depth--
            throw PcError("too much recursion - a function kept calling itself", "Recursion")
        }
        if ((++rt.steps and 0xFFF) == 0L) rt.check()
        try {
            val direct = p.direct
            if (direct != null) {
                // a one-expression body (|x| x * 2, fn f(n) => ...): no block, no return signal
                val result = direct.ev(f)
                p.ret?.check(result, f, "the result of ${p.name}")
                return result
            }
            val r = p.body.ex(f)
            val result = if (r == RETURN) f.ret else null
            val rc = p.ret
            if (rc != null) {
                if (r != RETURN && !p.retAcceptsNil) throw Errors.type("the result of ${p.name} should be ${rc.text}, but got nil")
                rc.check(result, f, "the result of ${p.name}")
            }
            return result
        } catch (e: PcError) {
            if (e.line == 0) e.line = f.line
            throw e
        } finally {
            rt.depth--
        }
    }

    /** One argument, the common case for lambdas given to map and filter. */
    fun call1(x: Any?): Any? {
        val p = proto
        if (p.params.size != 1 || p.hasRest || p.anyTyped) return call(arrayOf(x), null)
        val rt = p.rt
        val f = Frame(arrayOfNulls(p.nslots), up)
        p.params[0].place.set(f, x)
        if (++rt.depth > rt.maxDepth) { rt.depth--; throw PcError("too much recursion - a function kept calling itself", "Recursion") }
        if ((++rt.steps and 0xFFF) == 0L) rt.check()
        try {
            val direct = p.direct
            if (direct != null) { val r = direct.ev(f); p.ret?.check(r, f, "the result of ${p.name}"); return r }
            val r = p.body.ex(f)
            val result = if (r == RETURN) f.ret else null
            val rc = p.ret
            if (rc != null) {
                if (r != RETURN && !p.retAcceptsNil) throw Errors.type("the result of ${p.name} should be ${rc.text}, but got nil")
                rc.check(result, f, "the result of ${p.name}")
            }
            return result
        } catch (e: PcError) {
            if (e.line == 0) e.line = f.line
            throw e
        } finally {
            rt.depth--
        }
    }

    private fun bindSlow(f: Frame, args: Array<Any?>, kw: Map<String, Any?>?) {
        val p = proto
        val params = p.params
        val given = arrayOfNulls<Any?>(params.size)
        val set = BooleanArray(params.size)
        var ai = 0
        for ((i, param) in params.withIndex()) {
            if (param.rest) {
                val rest = ArrayList<Any?>()
                while (ai < args.size) rest.add(args[ai++])
                given[i] = PList(rest); set[i] = true
            } else if (ai < args.size) { given[i] = args[ai++]; set[i] = true }
        }
        if (ai < args.size) {
            throw Errors.type("${p.name} takes ${p.positional} argument${if (p.positional == 1) "" else "s"} but ${args.size} were given")
        }
        if (kw != null) for ((k, v) in kw) {
            val i = p.byName[k] ?: throw Errors.type("${p.name} got an unexpected keyword argument '$k'")
            if (set[i]) throw Errors.type("${p.name} got multiple values for argument '$k'")
            given[i] = v; set[i] = true
        }
        val missing = params.indices.filter { !set[it] && params[it].default == null && !params[it].rest }
        if (missing.isNotEmpty()) {
            val names = missing.joinToString(" and ") { "'${params[it].name}'" }
            throw Errors.type("${p.name} missing ${missing.size} required argument${if (missing.size == 1) "" else "s"}: $names")
        }
        for ((i, param) in params.withIndex()) {
            val v = if (set[i]) given[i] else {
                // defaults are worked out at call time, so they can use names declared later
                param.default!!.ev(f)
            }
            param.place.set(f, v)
            param.type?.check(v, f, "parameter ${param.name}")
        }
    }

    override fun toString() = if (proto.name.isEmpty()) "fn" else "fn ${proto.name}"
}

/** A method with its object: obj.method without calling it. */
class Bound(val self: Any?, val fn: Callable) : Callable {
    override val name: String get() = fn.name
    override fun call(args: Array<Any?>, kw: Map<String, Any?>?): Any? {
        val all = arrayOfNulls<Any?>(args.size + 1)
        all[0] = self
        System.arraycopy(args, 0, all, 1, args.size)
        return fn.call(all, kw)
    }
}

object Calls {
    fun call(fn: Any?, args: Array<Any?>, kw: Map<String, Any?>?): Any? = when (fn) {
        is Callable -> fn.call(args, kw)
        is StructType -> construct(fn, args, kw)
        is Variant -> {
            val fields = fn.fields ?: throw Errors.type("${fn} has no fields, so it cannot be called with ()")
            if (kw != null) {
                val vals = arrayOfNulls<Any?>(fields.size)
                val set = BooleanArray(fields.size)
                args.forEachIndexed { i, a -> if (i < fields.size) { vals[i] = a; set[i] = true } }
                for ((k, v) in kw) { val i = fields.indexOf(k); if (i < 0) throw Errors.type("$fn has no field $k"); vals[i] = v; set[i] = true }
                if (set.any { !it }) throw Errors.type("$fn needs ${fields.size} values: ${fields.joinToString()}")
                VariantObj(fn, vals)
            } else {
                if (args.size != fields.size) throw Errors.type("$fn needs ${fields.size} value${if (fields.size == 1) "" else "s"}: ${fields.joinToString()}")
                VariantObj(fn, args.copyOf())
            }
        }
        null -> throw Errors.type("nil is not a function, so it cannot be called with ()")
        else -> throw Errors.type("${Show.typeName(fn)} is not a function, so it cannot be called with ()")
    }

    fun construct(t: StructType, args: Array<Any?>, kw: Map<String, Any?>?): StructObj {
        val obj = StructObj(t, arrayOfNulls(t.fields.size))
        t.init(obj, args, kw)
        return obj
    }
}
