package com.expstudio.pycmd.lang

/** The tree the parser builds. The compiler turns it into executable nodes. */

sealed class TypeRef {
    class Simple(val name: String, val args: List<TypeRef>, val line: Int) : TypeRef()
    class Optional(val inner: TypeRef) : TypeRef()
    class Union(val options: List<TypeRef>) : TypeRef()
}

class Param(val name: String, val type: TypeRef?, val default: Ex?, val rest: Boolean)

sealed class Pat {
    object Any_ : Pat()
    class Lit(val value: Any?) : Pat()
    class Bind(val name: String, val line: Int) : Pat()
    class Range(val lo: Any?, val hi: Any?, val inclusive: Boolean) : Pat()
    class Value(val parts: List<String>) : Pat()
    class Type(val type: TypeRef) : Pat()
    class Or(val alts: List<Pat>) : Pat()
    class Rest(val name: String) : Pat()
    class ListP(val items: List<Pat>) : Pat()
    class StructP(val name: String, val subs: List<Pair<String?, Pat>>) : Pat()
    class VariantP(val parts: List<String>, val subs: List<Pair<String?, Pat>>) : Pat()
}

class Arm(val pattern: Pat, val guard: Ex?, val body: List<St>?, val expr: Ex?, val line: Int)

class CompLoop(val names: List<String>, val iter: Ex, val line: Int)

sealed class Ex(val line: Int) {
    class Const(line: Int, val value: Any?) : Ex(line)
    class Name(line: Int, val name: String) : Ex(line)
    class Self_(line: Int) : Ex(line)
    class Group(line: Int, val expr: Ex) : Ex(line)
    class InterpPart(val expr: Ex, val spec: String?)
    class Interp(line: Int, val parts: List<Any>) : Ex(line)
    class ListLit(line: Int, val items: List<Ex>) : Ex(line)
    class TupleLit(line: Int, val items: List<Ex>) : Ex(line)
    class MapLit(line: Int, val pairs: List<Pair<Ex?, Ex>>) : Ex(line)
    class ListComp(line: Int, val expr: Ex, val loops: List<CompLoop>, val cond: Ex?) : Ex(line)
    class MapComp(line: Int, val key: Ex, val value: Ex, val loops: List<CompLoop>, val cond: Ex?) : Ex(line)
    class Unary(line: Int, val op: String, val operand: Ex) : Ex(line)
    class Binary(line: Int, val op: String, val left: Ex, val right: Ex) : Ex(line)
    class Compare(line: Int, val ops: MutableList<String>, val items: MutableList<Ex>) : Ex(line)
    class Logic(line: Int, val op: String, val left: Ex, val right: Ex) : Ex(line)
    class Ternary(line: Int, val cond: Ex, val a: Ex, val b: Ex) : Ex(line)
    class Coalesce(line: Int, val left: Ex, val right: Ex) : Ex(line)
    class Is(line: Int, val value: Ex, val type: TypeRef, val negate: Boolean) : Ex(line)
    class RangeE(line: Int, val lo: Ex, val hi: Ex, val inclusive: Boolean) : Ex(line)
    class Pipe(line: Int, val value: Ex, val func: Ex) : Ex(line)
    class Attr(line: Int, val obj: Ex, val name: String) : Ex(line)
    class OptAttr(line: Int, val obj: Ex, val name: String) : Ex(line)
    class Index(line: Int, val obj: Ex, val index: Ex) : Ex(line)
    class Slice(line: Int, val start: Ex?, val stop: Ex?, val step: Ex?) : Ex(line)
    class Call(line: Int, val func: Ex, val args: List<Ex>, val kwargs: List<Pair<String, Ex>>) : Ex(line)
    class Spread(line: Int, val expr: Ex) : Ex(line)
    class Lambda(line: Int, val params: List<Param>, val ret: TypeRef?, val expr: Ex?, val body: List<St>?) : Ex(line)
    class MatchE(line: Int, val subject: Ex, val arms: List<Arm>) : Ex(line)
}

class VariantDecl(val name: String, val value: Ex?, val fields: List<Param>?)

sealed class St(val line: Int) {
    class ExprS(line: Int, val expr: Ex) : St(line)
    class Let(line: Int, val names: List<String>, val mutable: Boolean, val type: TypeRef?, val value: Ex?, val unpack: Boolean) : St(line)
    class Assign(line: Int, val target: Ex, val op: String, val value: Ex) : St(line)
    class Fn(line: Int, val name: String, val params: List<Param>, val ret: TypeRef?, val body: List<St>?) : St(line)
    class Struct(line: Int, val name: String, val parent: String?, val impls: List<String>,
                 val fields: List<Param>, val fieldLines: List<Int>, val methods: List<Fn>) : St(line)
    class EnumS(line: Int, val name: String, val variants: List<VariantDecl>, val methods: List<Fn>) : St(line)
    class Trait(line: Int, val name: String, val methods: List<Fn>) : St(line)
    class If(line: Int, val branches: List<Pair<Ex, List<St>>>, val other: List<St>?) : St(line)
    class While(line: Int, val cond: Ex?, val body: List<St>) : St(line)
    class For(line: Int, val names: List<String>, val iter: Ex, val body: List<St>) : St(line)
    class Return(line: Int, val value: Ex?, val implicit: Boolean = false) : St(line)
    class Break(line: Int) : St(line)
    class Continue(line: Int) : St(line)
    class Throw(line: Int, val value: Ex) : St(line)
    class Assert(line: Int, val cond: Ex, val message: Ex?) : St(line)
    class Test(line: Int, val name: String, val body: List<St>) : St(line)
    class Try(line: Int, val body: List<St>, val name: String?, val handler: List<St>?, val final: List<St>?) : St(line)
    class Use(line: Int, val module: String?, val path: String?, val alias: String, val names: List<String>?) : St(line)
    class MatchS(line: Int, val subject: Ex, val arms: List<Arm>) : St(line)
}
