"""More units for Python, JavaScript and C, added in 2.8.0.

Appended after each course's existing units rather than woven into them, and
that is deliberate: a lesson's id is its unit's position and its topic's
position, so a unit added in the middle would renumber every lesson after it
and quietly un-finish them for everybody who had done them. New material goes
on the end.

Every Python and C snippet here is run by `tools/test_teach.py`.
"""

from . import T, U

PYTHON = [
    U("Strings in depth", "Formatting, searching and cleaning text."),
    T("Format with width", "A number after the colon pads to that width.",
      'print(f"[{7:3}]")', "[  7]"),
    T("Left and right", "`<` and `>` choose which side the padding goes.",
      'print(f"[{\'ab\':<4}][{\'ab\':>4}]")', "[ab  ][  ab]"),
    T("Decimal places", "`.2f` rounds to two places for display only.",
      'print(f"{3.14159:.2f}")', "3.14"),
    T("Thousands", "A comma in the format spec groups the digits.",
      'print(f"{1234567:,}")', "1,234,567"),
    T("Percentages", "`%` multiplies by 100 and adds the sign.",
      'print(f"{0.25:.0%}")', "25%"),
    T("Debug f-strings", "`=` after a name prints the name too.",
      'n = 4\nprint(f"{n=}")', "n=4"),
    T("find and index", "`find` gives -1 when it is missing; `index` raises.",
      'print("pycmd".find("z"), "pycmd".find("c"))', "-1 2"),
    T("count", "How many times something appears.",
      'print("banana".count("a"))', "3"),
    T("startswith with a tuple", "Several prefixes at once.",
      'print("x.py".endswith((".py", ".pyw")))', "True"),
    T("isdigit and friends", "Questions a string can answer about itself.",
      'print("42".isdigit(), "4x".isdigit())', "True False"),
    T("title and capitalize", "Two ways to tidy the case.",
      'print("hello world".title())', "Hello World"),
    T("partition", "Splits once, around the first match, into three.",
      'print("key=value=x".partition("="))', "('key', '=', 'value=x')"),
    T("splitlines", "Splits on any kind of line ending.",
      'print("a\\nb\\r\\nc".splitlines())', "['a', 'b', 'c']"),
    T("zfill", "Pads a number-like string with zeros.",
      'print("7".zfill(3))', "007"),
    T("ord and chr", "A character's code, and back.",
      'print(ord("A"), chr(66))', "65 B"),
    T("Encoding", "Text to bytes needs an encoding.",
      'print("é".encode("utf-8"))', "b'\\xc3\\xa9'"),
    T("Decoding", "And bytes back to text.",
      'print(b"hi".decode())', "hi"),
    T("Multi-line strings", "Three quotes keep the newlines.",
      'text = """a\nb"""\nprint(len(text.splitlines()))', "2"),
    T("Raw strings", "An `r` prefix leaves backslashes alone.",
      'print(len(r"\\n"))', "2"),
    T("String immutability", "A method returns a new string; the old one stays.",
      's = "abc"\ns.upper()\nprint(s)', "abc"),

    U("Working with data", "Sorting, grouping and shaping collections."),
    T("Sorting by two keys", "A tuple key sorts by the first, then the second.",
      'rows = [("b", 1), ("a", 2), ("a", 1)]\nprint(sorted(rows))',
      "[('a', 1), ('a', 2), ('b', 1)]"),
    T("Sorting dictionaries by value", "`key=` reads the value out of each pair.",
      'd = {"a": 3, "b": 1}\nprint(sorted(d, key=d.get))', "['b', 'a']"),
    T("min and max with a key", "The same `key=` works here.",
      'print(max(["aa", "b", "ccc"], key=len))', "ccc"),
    T("Grouping with setdefault", "One line instead of an if.",
      'groups = {}\nfor w in ["ab", "ac", "b"]:\n    groups.setdefault(w[0], []).append(w)\n'
      'print(groups)', "{'a': ['ab', 'ac'], 'b': ['b']}"),
    T("Counter.most_common", "The top few, already sorted.",
      'from collections import Counter\nprint(Counter("aabbbc").most_common(1))',
      "[('b', 3)]"),
    T("Merging dictionaries", "`|` builds a new one; the right side wins.",
      'print({"a": 1} | {"a": 2, "b": 3})', "{'a': 2, 'b': 3}"),
    T("Nested lists", "A list of lists, reached with two indexes.",
      'grid = [[1, 2], [3, 4]]\nprint(grid[1][0])', "3"),
    T("Flattening", "A comprehension with two `for`s.",
      'grid = [[1, 2], [3, 4]]\nprint([n for row in grid for n in row])', "[1, 2, 3, 4]"),
    T("Transposing", "`zip(*rows)` turns rows into columns.",
      'print(list(zip(*[[1, 2], [3, 4]])))', "[(1, 3), (2, 4)]"),
    T("Chunking", "A slice in a comprehension.",
      'xs = list(range(5))\nprint([xs[i:i + 2] for i in range(0, 5, 2)])',
      "[[0, 1], [2, 3], [4]]"),
    T("Dictionary from two lists", "`dict(zip(...))`.",
      'print(dict(zip("ab", [1, 2])))', "{'a': 1, 'b': 2}"),
    T("Inverting a dictionary", "Swap keys and values with a comprehension.",
      'd = {"a": 1, "b": 2}\nprint({v: k for k, v in d.items()})', "{1: 'a', 2: 'b'}"),
    T("Removing while keeping order", "`dict.fromkeys` dedupes and keeps order.",
      'print(list(dict.fromkeys([3, 1, 3, 2])))', "[3, 1, 2]"),
    T("enumerate from one", "`start=` changes where the count begins.",
      'for i, c in enumerate("ab", start=1):\n    print(i, c)', "1 a\n2 b"),
    T("reversed", "Walks a sequence backwards without copying it.",
      'print(list(reversed([1, 2, 3])))', "[3, 2, 1]"),
    T("bisect", "Finds where something would go in a sorted list.",
      'import bisect\nprint(bisect.bisect([1, 3, 5], 4))', "2"),
    T("heapq", "The smallest few, without sorting everything.",
      'import heapq\nprint(heapq.nsmallest(2, [5, 1, 4, 2]))', "[1, 2]"),
    T("deque", "Fast appends and pops at both ends.",
      'from collections import deque\nq = deque([1, 2])\nq.appendleft(0)\nprint(list(q))',
      "[0, 1, 2]"),
    T("namedtuple", "A tuple whose positions have names.",
      'from collections import namedtuple\nP = namedtuple("P", "x y")\nprint(P(1, 2).y)', "2"),

    U("Iterators", "What a for loop actually does."),
    T("iter and next", "A for loop is these two, until StopIteration.",
      'it = iter([1, 2])\nprint(next(it), next(it))', "1 2"),
    T("next with a default", "A second argument instead of an exception.",
      'it = iter([])\nprint(next(it, "done"))', "done"),
    T("An iterator is used up", "Walking it twice gives nothing the second time.",
      'it = iter([1, 2])\nprint(list(it), list(it))', "[1, 2] []"),
    T("A class that iterates", "`__iter__` and `__next__`.",
      'class Up:\n    def __init__(self):\n        self.n = 0\n    def __iter__(self):\n'
      '        return self\n    def __next__(self):\n        self.n += 1\n'
      '        if self.n > 2:\n            raise StopIteration\n        return self.n\n\n'
      'print(list(Up()))', "[1, 2]"),
    T("yield from", "Hands over to another generator.",
      'def both():\n    yield from [1, 2]\n    yield 3\n\nprint(list(both()))', "[1, 2, 3]"),
    T("A generator keeps its place", "Each `next` resumes after the last `yield`.",
      'def gen():\n    yield "a"\n    yield "b"\n\ng = gen()\nprint(next(g))\nprint(next(g))',
      "a\nb"),
    T("itertools.chain", "Several iterables, one after another.",
      'from itertools import chain\nprint(list(chain([1], [2, 3])))', "[1, 2, 3]"),
    T("itertools.product", "Every combination of one from each.",
      'from itertools import product\nprint(list(product("ab", "12")))',
      "[('a', '1'), ('a', '2'), ('b', '1'), ('b', '2')]"),
    T("itertools.permutations", "Every ordering.",
      'from itertools import permutations\nprint(len(list(permutations("abc"))))', "6"),
    T("itertools.combinations", "Every choice, order ignored.",
      'from itertools import combinations\nprint(list(combinations("abc", 2)))',
      "[('a', 'b'), ('a', 'c'), ('b', 'c')]"),
    T("itertools.groupby", "Groups runs of equal neighbours.",
      'from itertools import groupby\nprint([k for k, _ in groupby("aabba")])',
      "['a', 'b', 'a']"),
    T("itertools.accumulate", "Running totals.",
      'from itertools import accumulate\nprint(list(accumulate([1, 2, 3])))', "[1, 3, 6]"),
    T("functools.reduce", "Folds a sequence into one value.",
      'from functools import reduce\nprint(reduce(lambda a, b: a * b, [1, 2, 3, 4]))', "24"),
    T("functools.lru_cache", "Remembers answers to calls it has seen.",
      'from functools import lru_cache\n\n@lru_cache\ndef fib(n):\n'
      '    return n if n < 2 else fib(n - 1) + fib(n - 2)\n\nprint(fib(30))', "832040"),
    T("functools.partial", "A function with some arguments already filled in.",
      'from functools import partial\nhex2 = partial(int, base=16)\nprint(hex2("ff"))', "255"),

    U("Objects in depth", "The methods with two underscores on each side."),
    T("__repr__", "What the REPL shows, and what `!r` uses.",
      'class P:\n    def __repr__(self):\n        return "P()"\n\nprint([P()])', "[P()]"),
    T("__eq__", "What `==` means for your class.",
      'class P:\n    def __init__(self, x):\n        self.x = x\n    def __eq__(self, other):\n'
      '        return self.x == other.x\n\nprint(P(1) == P(1))', "True"),
    T("__len__", "What `len()` returns.",
      'class Bag:\n    def __len__(self):\n        return 3\n\nprint(len(Bag()))', "3"),
    T("__getitem__", "What square brackets do.",
      'class Sq:\n    def __getitem__(self, i):\n        return i * i\n\nprint(Sq()[4])', "16"),
    T("__contains__", "What `in` asks.",
      'class Evens:\n    def __contains__(self, n):\n        return n % 2 == 0\n\n'
      'print(4 in Evens())', "True"),
    T("__add__", "What `+` does.",
      'class V:\n    def __init__(self, x):\n        self.x = x\n    def __add__(self, o):\n'
      '        return V(self.x + o.x)\n\nprint((V(1) + V(2)).x)', "3"),
    T("__call__", "An object you can call like a function.",
      'class Greeter:\n    def __call__(self, who):\n        return "hi " + who\n\n'
      'print(Greeter()("you"))', "hi you"),
    T("__bool__", "What `if obj:` decides.",
      'class Empty:\n    def __bool__(self):\n        return False\n\n'
      'print("yes" if Empty() else "no")', "no"),
    T("A classmethod", "Gets the class, not the instance. Good for constructors.",
      'class P:\n    def __init__(self, x):\n        self.x = x\n    @classmethod\n'
      '    def origin(cls):\n        return cls(0)\n\nprint(P.origin().x)', "0"),
    T("A property with a setter", "Reading and writing go through code.",
      'class T:\n    def __init__(self):\n        self._c = 0\n    @property\n'
      '    def c(self):\n        return self._c\n    @c.setter\n    def c(self, v):\n'
      '        self._c = max(0, v)\n\nt = T()\nt.c = -5\nprint(t.c)', "0"),
    T("__slots__", "A fixed set of attributes, and less memory.",
      'class P:\n    __slots__ = ("x",)\n\np = P()\np.x = 1\nprint(p.x)', "1"),
    T("Abstract classes", "`abc` makes a method that must be overridden.",
      'from abc import ABC, abstractmethod\n\nclass Shape(ABC):\n    @abstractmethod\n'
      '    def area(self): ...\n\ntry:\n    Shape()\nexcept TypeError:\n    print("abstract")',
      "abstract"),
    T("Multiple inheritance", "The MRO decides which method wins.",
      'class A:\n    def who(self):\n        return "A"\n\nclass B:\n    def who(self):\n'
      '        return "B"\n\nclass C(A, B):\n    pass\n\nprint(C().who())', "A"),
    T("isinstance", "Asks about a class and its parents.",
      'class A:\n    pass\n\nclass B(A):\n    pass\n\nprint(isinstance(B(), A))', "True"),
    T("Enum", "A fixed set of named values.",
      'from enum import Enum\n\nclass Colour(Enum):\n    RED = 1\n    GREEN = 2\n\n'
      'print(Colour(2).name)', "GREEN"),
    T("Frozen dataclass", "`frozen=True` makes instances read-only.",
      'from dataclasses import dataclass\n\n@dataclass(frozen=True)\nclass P:\n    x: int\n\n'
      'try:\n    P(1).x = 2\nexcept Exception as e:\n    print(type(e).__name__)',
      "FrozenInstanceError"),
    T("Dataclass defaults", "`field(default_factory=list)` for a fresh list each time.",
      'from dataclasses import dataclass, field\n\n@dataclass\nclass Bag:\n'
      '    items: list = field(default_factory=list)\n\nprint(Bag().items)', "[]"),

    U("Testing and debugging", "Finding out what your code really does."),
    T("assert in tests", "An assert that passes says nothing.",
      'def add(a, b):\n    return a + b\n\nassert add(2, 2) == 4\nprint("passed")', "passed"),
    T("unittest", "The test framework in the standard library.",
      'import unittest\n\nclass T(unittest.TestCase):\n    def test_add(self):\n'
      '        self.assertEqual(1 + 1, 2)\n\nprint(T("test_add").run().wasSuccessful())',
      "True"),
    T("doctest", "Examples in the docstring, checked for real.",
      'import doctest\n\ndef double(n):\n    """\n    >>> double(3)\n    6\n    """\n'
      '    return n * 2\n\nprint(doctest.testmod().failed)', "0"),
    T("traceback", "The error as text, for logging.",
      'import traceback\ntry:\n    1 / 0\nexcept ZeroDivisionError:\n'
      '    print(traceback.format_exc().splitlines()[-1])',
      "ZeroDivisionError: division by zero"),
    T("logging", "Messages with a level, which can be turned up and down.",
      'import logging, sys\nlog = logging.Logger("demo")\n'
      'log.addHandler(logging.StreamHandler(sys.stdout))\n'
      'log.warning("careful")', "careful"),
    T("timeit", "How long something takes, measured properly.",
      'import timeit\nt = timeit.timeit("sum(range(10))", number=100)\nprint(t > 0)', "True"),
    T("repr for debugging", "`!r` shows quotes, so empty and space are visible.",
      'print(f"{\'\'!r} {\' \'!r}")', "'' ' '"),
    T("vars", "An object's attributes as a dictionary.",
      'class P:\n    def __init__(self):\n        self.x = 1\n\nprint(vars(P()))', "{'x': 1}"),
    T("dir", "Every name an object answers to.",
      'print("upper" in dir(""))', "True"),

    U("Concurrency", "Doing more than one thing."),
    T("A thread", "Runs a function alongside the main program.",
      'import threading\nout = []\nt = threading.Thread(target=lambda: out.append(1))\n'
      't.start()\nt.join()\nprint(out)', "[1]"),
    T("A lock", "Only one thread at a time inside it.",
      'import threading\nlock = threading.Lock()\nwith lock:\n    print("inside")', "inside"),
    T("A thread pool", "`map` across threads, results in order.",
      'from concurrent.futures import ThreadPoolExecutor\n'
      'with ThreadPoolExecutor() as pool:\n    print(list(pool.map(abs, [-1, -2])))', "[1, 2]"),
    T("A queue", "Thread-safe hand-off between workers.",
      'import queue\nq = queue.Queue()\nq.put(1)\nprint(q.get())', "1"),
    T("asyncio.run", "Starts an event loop and runs one coroutine.",
      'import asyncio\n\nasync def main():\n    return 7\n\nprint(asyncio.run(main()))', "7"),
    T("await", "Waits for another coroutine.",
      'import asyncio\n\nasync def two():\n    return 2\n\nasync def main():\n'
      '    print(await two())\n\nasyncio.run(main())', "2"),
    T("asyncio.gather", "Several at once, results in order.",
      'import asyncio\n\nasync def sq(n):\n    return n * n\n\nasync def main():\n'
      '    print(await asyncio.gather(sq(2), sq(3)))\n\nasyncio.run(main())', "[4, 9]"),
    T("asyncio.sleep", "Waiting without blocking the loop.",
      'import asyncio\n\nasync def main():\n    await asyncio.sleep(0)\n    print("woke")\n\n'
      'asyncio.run(main())', "woke"),

    U("Types", "Type hints, and the tools that read them."),
    T("Optional", "`X | None` says it may be missing.",
      'def find(n: int) -> str | None:\n    return None if n < 0 else str(n)\n\n'
      'print(find(-1))', "None"),
    T("list[int]", "Containers take their item type in brackets.",
      'def total(xs: list[int]) -> int:\n    return sum(xs)\n\nprint(total([1, 2]))', "3"),
    T("TypedDict", "A dictionary with known keys.",
      'from typing import TypedDict\n\nclass P(TypedDict):\n    x: int\n\np: P = {"x": 1}\n'
      'print(p["x"])', "1"),
    T("Protocol", "Structural typing: anything with the right methods fits.",
      'from typing import Protocol\n\nclass Named(Protocol):\n    name: str\n\n'
      'class Dog:\n    name = "rex"\n\ndef show(x: Named) -> str:\n    return x.name\n\n'
      'print(show(Dog()))', "rex"),
    T("Generics", "A function whose type travels with its argument.",
      'def first[T](xs: list[T]) -> T:\n    return xs[0]\n\nprint(first(["a", "b"]))', "a"),
    T("Literal", "Only these exact values.",
      'from typing import Literal\n\ndef go(d: Literal["up", "down"]) -> str:\n    return d\n\n'
      'print(go("up"))', "up"),
    T("Hints are not checks", "Python runs it anyway. A type checker would not.",
      'def double(n: int) -> int:\n    return n * 2\n\nprint(double("ab"))', "abab"),
    T("get_type_hints", "Read the annotations at run time.",
      'from typing import get_type_hints\n\ndef f(x: int) -> str: ...\n\n'
      'print(get_type_hints(f)["x"].__name__)', "int"),
]


JAVASCRIPT = [
    U("Strings and numbers in depth"),
    T("padStart", "Pads the front to a length.",
      'console.log("7".padStart(3, "0"));', "007"),
    T("at", "A negative index counts from the end.",
      'console.log("pycmd".at(-1));', "d"),
    T("startsWith and endsWith", "Two questions with obvious names.",
      'console.log("main.js".endsWith(".js"));', "true"),
    T("indexOf", "-1 when it is not there.",
      'console.log("pycmd".indexOf("z"));', "-1"),
    T("Number.isInteger", "Is it a whole number?",
      'console.log(Number.isInteger(5.0), Number.isInteger(5.5));', "true false"),
    T("parseFloat", "Reads as much number as it can.",
      'console.log(parseFloat("3.5kg"));', "3.5"),
    T("toString with a base", "Numbers in binary or hex.",
      'console.log((255).toString(16));', "ff"),
    T("Math.max with spread", "`...` turns an array into arguments.",
      'console.log(Math.max(...[3, 9, 2]));', "9"),
    T("Floating point", "0.1 + 0.2 is not 0.3, in any language.",
      'console.log(0.1 + 0.2 === 0.3);', "false"),
    T("BigInt", "Whole numbers with no upper limit; an `n` on the end.",
      'console.log(2n ** 64n);', "18446744073709551616n"),
    T("toLocaleString", "Grouping digits the way people read them.",
      'console.log((1234567).toLocaleString("en-US"));', "1,234,567"),

    U("Arrays in depth"),
    T("some and every", "Any, and all.",
      'const xs = [1, 2];\nconsole.log(xs.some(n => n > 1), xs.every(n => n > 1));',
      "true false"),
    T("findIndex", "Where the first match is.",
      'console.log([5, 7, 9].findIndex(n => n > 6));', "1"),
    T("flat", "One level of nesting removed.",
      'console.log([[1], [2, 3]].flat());', "[ 1, 2, 3 ]"),
    T("flatMap", "map, then flat.",
      'console.log([1, 2].flatMap(n => [n, n]));', "[ 1, 1, 2, 2 ]"),
    T("slice versus splice", "slice copies; splice changes the array.",
      'const a = [1, 2, 3];\nconsole.log(a.slice(1), a.length);', "[ 2, 3 ] 3"),
    T("Array.from", "Makes an array from anything iterable, with a map.",
      'console.log(Array.from({length: 3}, (_, i) => i * 2));', "[ 0, 2, 4 ]"),
    T("includes and NaN", "`includes` finds NaN; `indexOf` does not.",
      'console.log([NaN].includes(NaN), [NaN].indexOf(NaN));', "true -1"),
    T("Sorting strings", "`localeCompare` is the comparator for text.",
      'const words = ["b", "a"];\nwords.sort((x, y) => x.localeCompare(y));\n'
      'console.log(words);', "[ 'a', 'b' ]"),
    T("toSorted", "A sorted copy, leaving the original alone.",
      'const a = [3, 1];\nconst b = a.toSorted();\nconsole.log(a, b);', "[ 3, 1 ] [ 1, 3 ]"),
    T("Grouping", "`Object.groupBy` buckets by a key.",
      'const parity = n => (n % 2 ? "odd" : "even");\n'
      'const g = Object.groupBy([1, 2, 3], parity);\nconsole.log(g.odd);', "[ 1, 3 ]"),
    T("Destructuring with rest", "`...rest` collects what is left.",
      'const [first, ...rest] = [1, 2, 3];\nconsole.log(rest);', "[ 2, 3 ]"),
    T("Default in destructuring", "A fallback when the item is missing.",
      'const [a, b = 9] = [1];\nconsole.log(b);', "9"),

    U("Objects in depth"),
    T("Shorthand properties", "A name that is also the key.",
      'const n = 1;\nconsole.log({ n });', "{ n: 1 }"),
    T("Computed keys", "Square brackets in a literal.",
      'const k = "x";\nconsole.log({ [k]: 1 });', "{ x: 1 }"),
    T("Spreading objects", "Copies, and the later key wins.",
      'console.log({ ...{ a: 1 }, a: 2 });', "{ a: 2 }"),
    T("Object.freeze", "Nothing can change it afterwards.",
      'const o = Object.freeze({ a: 1 });\no.a = 2;\nconsole.log(o.a);', "1"),
    T("in", "Does the object have this key?",
      'console.log("a" in { a: undefined });', "true"),
    T("Optional call", "`?.()` calls only if it is a function.",
      'const o = {};\nconsole.log(o.go?.());', "undefined"),
    T("structuredClone", "A deep copy that understands Dates and Maps.",
      'const a = { list: [1] };\nconst b = structuredClone(a);\nb.list.push(2);\n'
      'console.log(a.list);', "[ 1 ]"),
    T("Getters on a literal", "`get` works without a class.",
      'const o = { get two() { return 2; } };\nconsole.log(o.two);', "2"),
    T("Private fields", "A `#` name cannot be reached from outside.",
      'class Counter {\n  #n = 0;\n  inc() {\n    return ++this.#n;\n  }\n}\n'
      'console.log(new Counter().inc());', "1"),
    T("Static fields", "On the class itself.",
      'class Config {\n  static size = 3;\n}\nconsole.log(Config.size);', "3"),
    T("instanceof", "Was it made by this class, or one below it?",
      'class A {}\nclass B extends A {}\nconsole.log(new B() instanceof A);', "true"),

    U("Iterators and generators"),
    T("A generator", "`function*` and `yield`.",
      'function* up() {\n  yield 1;\n  yield 2;\n}\nconsole.log([...up()]);', "[ 1, 2 ]"),
    T("next()", "One value at a time, and whether it is finished.",
      'function* g() {\n  yield "a";\n}\nconst it = g();\nconsole.log(it.next().value);', "a"),
    T("An iterable object", "`[Symbol.iterator]` makes `for..of` work on it.",
      'const two = {\n  *[Symbol.iterator]() {\n    yield 1;\n    yield 2;\n  },\n};\n'
      'console.log([...two]);', "[ 1, 2 ]"),
    T("Map iteration order", "A Map keeps insertion order.",
      'const m = new Map([["b", 1], ["a", 2]]);\nconsole.log([...m.keys()]);', "[ 'b', 'a' ]"),
    T("Set operations by hand", "Intersection with a filter.",
      'const a = new Set([1, 2]);\nconst b = new Set([2, 3]);\n'
      'console.log([...a].filter(x => b.has(x)));', "[ 2 ]"),
    T("WeakMap", "Keys that do not stop garbage collection.",
      'const w = new WeakMap();\nconst k = {};\nw.set(k, 1);\nconsole.log(w.get(k));', "1"),
    T("Symbols", "A unique key nobody can collide with.",
      'const id = Symbol("id");\nconst o = { [id]: 1 };\nconsole.log(o[id]);', "1"),

    U("Modules, errors and more async"),
    T("Error causes", "`cause` chains one error to another.",
      'try {\n  throw new Error("outer", { cause: "inner" });\n} catch (e) {\n'
      '  console.log(e.cause);\n}', "inner"),
    T("finally runs on return", "Even a return in try runs finally first.",
      'function f() {\n  try {\n    return 1;\n  } finally {\n    console.log("cleanup");\n  }\n}\n'
      'f();', "cleanup"),
    T("Promise.allSettled", "Every result, failures included.",
      'const all = Promise.allSettled([Promise.reject(1)]);\n'
      'all.then(r => console.log(r[0].status));', "rejected"),
    T("Promise.race", "Whichever settles first.",
      'const first = Promise.race([Promise.resolve("fast")]);\n'
      'first.then(v => console.log(v));', "fast"),
    T("Microtasks before timers", "A resolved promise runs before setTimeout(0).",
      'setTimeout(() => console.log("timer"), 0);\n'
      'Promise.resolve().then(() => console.log("promise"));', "promise\ntimer"),
    T("for await", "Loops over promises one at a time.",
      'async function main() {\n  for await (const n of [Promise.resolve(1)]) {\n'
      '    console.log(n);\n  }\n}\nmain();', "1"),
    T("JSON.parse reviver", "A function that sees every value on the way in.",
      'const fix = (k, v) => (k === "n" ? Number(v) : v);\n'
      'const o = JSON.parse(\'{"n":"5"}\', fix);\nconsole.log(o.n + 1);', "6"),
    T("JSON.stringify spacing", "A third argument pretty-prints.",
      'console.log(JSON.stringify([1], null, 1));', "[\n 1\n]"),
    T("Date basics", "Months count from zero. Really.",
      'console.log(new Date(2026, 0, 31).getMonth());', "0"),
    T("Regex test", "Does the pattern match anywhere?",
      'console.log(/\\d+/.test("a1"));', "true"),
    T("Regex match groups", "Named groups end up on `.groups`.",
      'const m = "2026-10".match(/(?<y>\\d+)-(?<m>\\d+)/);\nconsole.log(m.groups.m);', "10"),
    T("replace with a function", "The function decides each replacement.",
      'console.log("a1b2".replace(/\\d/g, d => d * 2));', "a2b4"),
]


C = [
    U("More of the language"),
    T("The ternary operator", "A choice that is an expression.",
      '#include <stdio.h>\n\nint main(void) {\n    int n = 5;\n'
      '    printf("%s\\n", n > 3 ? "big" : "small");\n    return 0;\n}', "big"),
    T("Compound assignment", "`+=`, `*=` and the rest.",
      '#include <stdio.h>\n\nint main(void) {\n    int n = 2;\n    n *= 5;\n'
      '    printf("%d\\n", n);\n    return 0;\n}', "10"),
    T("Increment before and after", "`n++` gives the old value; `++n` the new one.",
      '#include <stdio.h>\n\nint main(void) {\n    int n = 1;\n    int a = n++;\n'
      '    int b = ++n;\n    printf("%d %d\\n", a, b);\n    return 0;\n}', "1 3"),
    T("Logical operators", "`&&`, `||` and `!`, giving 0 or 1.",
      '#include <stdio.h>\n\nint main(void) {\n    printf("%d\\n", 1 && !0);\n'
      '    return 0;\n}', "1"),
    T("Bitwise AND and OR", "Working on the individual bits.",
      '#include <stdio.h>\n\nint main(void) {\n    printf("%d %d\\n", 6 & 3, 6 | 3);\n'
      '    return 0;\n}', "2 7"),
    T("Shifts", "`<<` doubles per step, `>>` halves.",
      '#include <stdio.h>\n\nint main(void) {\n    printf("%d %d\\n", 1 << 4, 32 >> 2);\n'
      '    return 0;\n}', "16 8"),
    T("XOR", "Bits that differ.",
      '#include <stdio.h>\n\nint main(void) {\n    printf("%d\\n", 5 ^ 3);\n    return 0;\n}',
      "6"),
    T("Hex and octal output", "`%x` and `%o`.",
      '#include <stdio.h>\n\nint main(void) {\n    printf("%x %o\\n", 255, 8);\n'
      '    return 0;\n}', "ff 10"),
    T("Width in printf", "A number pads the field.",
      '#include <stdio.h>\n\nint main(void) {\n    printf("[%4d]\\n", 7);\n    return 0;\n}',
      "[   7]"),
    T("Left-aligned", "A minus sign pads on the right.",
      '#include <stdio.h>\n\nint main(void) {\n    printf("[%-4d]\\n", 7);\n    return 0;\n}',
      "[7   ]"),
    T("Zero padding", "A leading zero in the width.",
      '#include <stdio.h>\n\nint main(void) {\n    printf("%03d\\n", 7);\n    return 0;\n}',
      "007"),
    T("Long integers", "`long` and `%ld` for bigger numbers.",
      '#include <stdio.h>\n\nint main(void) {\n    long big = 3000000000L;\n'
      '    printf("%ld\\n", big);\n    return 0;\n}', "3000000000"),
    T("Static locals", "A local that keeps its value between calls.",
      '#include <stdio.h>\n\nint count(void) {\n    static int n = 0;\n    return ++n;\n}\n\n'
      'int main(void) {\n    count();\n    printf("%d\\n", count());\n    return 0;\n}', "2"),
    T("A global", "Declared outside every function.",
      '#include <stdio.h>\n\nint total = 0;\n\nvoid add(int n) {\n    total += n;\n}\n\n'
      'int main(void) {\n    add(3);\n    printf("%d\\n", total);\n    return 0;\n}', "3"),
    T("#define", "A name the preprocessor swaps for its value.",
      '#include <stdio.h>\n\n#define SIZE 4\n\nint main(void) {\n    printf("%d\\n", SIZE * 2);\n'
      '    return 0;\n}', "8"),

    U("Strings and memory"),
    T("strcmp", "Zero when two strings are equal.",
      '#include <stdio.h>\n#include <string.h>\n\nint main(void) {\n'
      '    printf("%d\\n", strcmp("a", "a"));\n    return 0;\n}', "0"),
    T("strncpy", "Copies at most n characters.",
      '#include <stdio.h>\n#include <string.h>\n\nint main(void) {\n    char s[4] = "";\n'
      '    strncpy(s, "pycmd", 2);\n    s[2] = 0;\n    printf("%s\\n", s);\n    return 0;\n}',
      "py"),
    T("Walking a string", "Until the zero byte.",
      '#include <stdio.h>\n\nint main(void) {\n    const char *s = "abc";\n    int n = 0;\n'
      '    while (s[n]) n++;\n    printf("%d\\n", n);\n    return 0;\n}', "3"),
    T("sprintf", "printf, into a buffer.",
      '#include <stdio.h>\n\nint main(void) {\n    char buf[16];\n'
      '    sprintf(buf, "n=%d", 5);\n    printf("%s\\n", buf);\n    return 0;\n}', "n=5"),
    T("memset", "Fills memory with one byte.",
      '#include <stdio.h>\n#include <string.h>\n\nint main(void) {\n    int a[3];\n'
      '    memset(a, 0, sizeof a);\n    printf("%d\\n", a[2]);\n    return 0;\n}', "0"),
    T("calloc", "Like malloc, but zeroed.",
      '#include <stdio.h>\n#include <stdlib.h>\n\nint main(void) {\n'
      '    int *a = calloc(3, sizeof(int));\n    printf("%d\\n", a[1]);\n    free(a);\n'
      '    return 0;\n}', "0"),
    T("realloc", "Grows a block, keeping what was in it.",
      '#include <stdio.h>\n#include <stdlib.h>\n\nint main(void) {\n'
      '    int *a = malloc(sizeof(int));\n    a[0] = 7;\n    a = realloc(a, 2 * sizeof(int));\n'
      '    printf("%d\\n", a[0]);\n    free(a);\n    return 0;\n}', "7"),
    T("Pointer to pointer", "Two stars, two hops.",
      '#include <stdio.h>\n\nint main(void) {\n    int n = 4;\n    int *p = &n;\n'
      '    int **pp = &p;\n    printf("%d\\n", **pp);\n    return 0;\n}', "4"),
    T("Swapping through pointers", "The classic function.",
      '#include <stdio.h>\n\nvoid swap(int *a, int *b) {\n    int t = *a;\n    *a = *b;\n'
      '    *b = t;\n}\n\nint main(void) {\n    int x = 1, y = 2;\n    swap(&x, &y);\n'
      '    printf("%d %d\\n", x, y);\n    return 0;\n}', "2 1"),
    T("Array length idiom", "sizeof the array over sizeof one item.",
      '#include <stdio.h>\n\nint main(void) {\n    int a[] = {1, 2, 3, 4};\n'
      '    printf("%d\\n", (int) (sizeof a / sizeof a[0]));\n    return 0;\n}', "4"),
    T("A function pointer", "A variable that holds a function.",
      '#include <stdio.h>\n\nint twice(int n) {\n    return n * 2;\n}\n\nint main(void) {\n'
      '    int (*f)(int) = twice;\n    printf("%d\\n", f(4));\n    return 0;\n}', "8"),
    T("qsort", "The standard library's sort, with a comparator.",
      '#include <stdio.h>\n#include <stdlib.h>\n\nint cmp(const void *a, const void *b) {\n'
      '    return *(const int *) a - *(const int *) b;\n}\n\nint main(void) {\n'
      '    int a[] = {3, 1, 2};\n    qsort(a, 3, sizeof(int), cmp);\n'
      '    printf("%d\\n", a[0]);\n    return 0;\n}', "1"),

    U("Structs, unions and lists"),
    T("Array of structs", "Like a table.",
      '#include <stdio.h>\n\nstruct P {\n    int x;\n};\n\nint main(void) {\n'
      '    struct P ps[2] = {{1}, {2}};\n    printf("%d\\n", ps[1].x);\n    return 0;\n}', "2"),
    T("Passing a struct by pointer", "So the function can change it.",
      '#include <stdio.h>\n\nstruct P {\n    int x;\n};\n\nvoid bump(struct P *p) {\n'
      '    p->x++;\n}\n\nint main(void) {\n    struct P p = {1};\n    bump(&p);\n'
      '    printf("%d\\n", p.x);\n    return 0;\n}', "2"),
    T("A struct on the heap", "malloc a struct, use it through a pointer.",
      '#include <stdio.h>\n#include <stdlib.h>\n\nstruct P {\n    int x;\n};\n\n'
      'int main(void) {\n    struct P *p = malloc(sizeof *p);\n    p->x = 5;\n'
      '    printf("%d\\n", p->x);\n    free(p);\n    return 0;\n}', "5"),
    T("A linked list node", "A struct that points at another of itself.",
      '#include <stdio.h>\n\nstruct Node {\n    int value;\n    struct Node *next;\n};\n\n'
      'int main(void) {\n    struct Node b = {2, NULL};\n    struct Node a = {1, &b};\n'
      '    printf("%d\\n", a.next->value);\n    return 0;\n}', "2"),
    T("Walking a list", "Follow `next` until NULL.",
      '#include <stdio.h>\n\nstruct N {\n    int v;\n    struct N *next;\n};\n\n'
      'int main(void) {\n    struct N c = {3, NULL}, b = {2, &c}, a = {1, &b};\n'
      '    int sum = 0;\n    for (struct N *p = &a; p; p = p->next) sum += p->v;\n'
      '    printf("%d\\n", sum);\n    return 0;\n}', "6"),
    T("A union", "Several fields sharing the same memory.",
      '#include <stdio.h>\n\nunion U {\n    int i;\n    char c;\n};\n\nint main(void) {\n'
      '    union U u;\n    u.i = 65;\n    printf("%c\\n", u.c);\n    return 0;\n}', "A"),
    T("Enum in a switch", "Named cases read better than numbers.",
      '#include <stdio.h>\n\nenum Dir { UP, DOWN };\n\nint main(void) {\n'
      '    enum Dir d = DOWN;\n    switch (d) {\n    case UP:\n        printf("up\\n");\n'
      '        break;\n    case DOWN:\n        printf("down\\n");\n        break;\n    }\n'
      '    return 0;\n}', "down"),
    T("Reading a number", "scanf with no input returns EOF; check it.",
      '#include <stdio.h>\n\nint main(void) {\n    int n = 0;\n'
      '    if (scanf("%d", &n) != 1) n = -1;\n    printf("%d\\n", n);\n    return 0;\n}', "-1"),
    T("Exit codes", "`return 0` from main means success.",
      '#include <stdio.h>\n#include <stdlib.h>\n\nint main(void) {\n    printf("ok\\n");\n'
      '    return EXIT_SUCCESS;\n}', "ok"),
]

EXTRA = {"python": PYTHON, "javascript": JAVASCRIPT, "c": C}
