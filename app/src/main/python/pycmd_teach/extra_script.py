"""More units for TypeScript, Ruby, PHP, Lua, Shell and SQL, added in 2.8.0.

Checked against bun, ruby, php, lua and bash wherever they are installed, by
`tools/test_teach.py`. SQL is checked against sqlite3 when it is there.
"""

from . import T, U

TYPESCRIPT = [
    U("The type system in depth"),
    T("keyof", "The union of an object type's keys.",
      'type P = { x: number; y: number };\nconst k: keyof P = "y";\nconsole.log(k);', "y"),
    T("typeof on a value", "Borrowing a value's type.",
      'const config = { port: 80 };\ntype C = typeof config;\nconst c: C = { port: 8080 };\n'
      'console.log(c.port);', "8080"),
    T("Partial", "Every property optional.",
      'interface P { x: number; y: number }\nconst p: Partial<P> = { x: 1 };\nconsole.log(p.y);',
      "undefined"),
    T("Readonly", "Every property read-only.",
      'interface P { x: number }\nconst p: Readonly<P> = { x: 1 };\nconsole.log(p.x);', "1"),
    T("Pick and Omit", "A type made from some of another's keys.",
      'interface U { id: number; name: string; pw: string }\n'
      'const u: Omit<U, "pw"> = { id: 1, name: "a" };\nconsole.log(Object.keys(u).length);', "2"),
    T("Record", "An object type with keys of one type and values of another.",
      'const ages: Record<string, number> = { a: 1 };\nconsole.log(ages.a);', "1"),
    T("Discriminated unions", "A shared literal field tells the compiler which one it is.",
      'type Shape =\n  | { kind: "sq"; s: number }\n  | { kind: "c"; r: number };\n'
      'function area(x: Shape): number {\n  return x.kind === "sq" ? x.s * x.s : 3 * x.r * x.r;\n}\n'
      'console.log(area({ kind: "sq", s: 3 }));', "9"),
    T("never for exhaustiveness", "A case that should be impossible.",
      'type D = "a" | "b";\nfunction f(d: D): string {\n  switch (d) {\n    case "a": return "A";\n'
      '    case "b": return "B";\n  }\n}\nconsole.log(f("b"));', "B"),
    T("Type guards", "A function that narrows a type.",
      'function isText(v: unknown): v is string {\n  return typeof v === "string";\n}\n'
      'const v: unknown = "hi";\nif (isText(v)) console.log(v.length);', "2"),
    T("Non-null assertion", "`!` says it cannot be null. Be right.",
      'const m = new Map([["a", 1]]);\nconst n: number = m.get("a")!;\nconsole.log(n);', "1"),
    T("Function overloads", "Several signatures, one body.",
      'function len(x: string): number;\nfunction len(x: unknown[]): number;\n'
      'function len(x: string | unknown[]): number {\n  return x.length;\n}\n'
      'console.log(len("abc"));', "3"),
    T("Template literal types", "Strings with a pattern.",
      'type Px = `${number}px`;\nconst w: Px = "10px";\nconsole.log(w);', "10px"),
    T("Generic constraints with keyof", "Getting a property safely.",
      'function get<T, K extends keyof T>(o: T, k: K): T[K] {\n  return o[k];\n}\n'
      'console.log(get({ a: 5 }, "a"));', "5"),
    T("Abstract classes", "A class that cannot be made directly.",
      'abstract class Shape {\n  abstract area(): number;\n}\nclass Sq extends Shape {\n'
      '  area() {\n    return 4;\n  }\n}\nconsole.log(new Sq().area());', "4"),
    T("Access modifiers", "`private` is checked by the compiler.",
      'class C {\n  private n = 1;\n  get() {\n    return this.n;\n  }\n}\nconsole.log(new C().get());',
      "1"),
    T("satisfies", "Checks a value against a type without widening it.",
      'const c = { port: 80 } satisfies { port: number };\nconsole.log(c.port);', "80"),
]


RUBY = [
    U("More Ruby"),
    T("String formatting", "`%` with a format string.", 'puts "%03d" % 7', "007"),
    T("each_with_index", "The item and where it is.",
      '["a", "b"].each_with_index do |c, i|\n  puts "#{i}#{c}"\nend', "0a\n1b"),
    T("times", "A number can count.", '3.times { |i| puts i }', "0\n1\n2"),
    T("upto", "Counting from one number to another.", '1.upto(3) { |i| puts i }', "1\n2\n3"),
    T("include?", "Membership, with a question mark.", 'puts [1, 2].include?(2)', "true"),
    T("sort_by", "Sorting by something derived.", 'p %w[ccc a bb].sort_by(&:length)',
      '["a", "bb", "ccc"]'),
    T("group_by", "Buckets by a key; here, the words that start with a.",
      'groups = %w[ab ac b].group_by { |w| w[0] }\np groups["a"]', '["ab", "ac"]'),
    T("each_slice", "Fixed-size groups.", 'p (1..5).each_slice(2).to_a', "[[1, 2], [3, 4], [5]]"),
    T("tally", "Counting occurrences into a hash.", 'counts = %w[a b a].tally\nputs counts["a"]', "2"),
    T("min_by and max_by", "The smallest by some measure.",
      'puts %w[aa b ccc].max_by(&:length)', "ccc"),
    T("zip", "Pairs from two arrays.", 'p [1, 2].zip(["a", "b"])', '[[1, "a"], [2, "b"]]'),
    T("Hash#map", "A hash can be walked into an array.",
      'p({a: 1, b: 2}.map { |k, v| v * 2 })', "[2, 4]"),
    T("Hash default", "A value for missing keys.",
      'h = Hash.new(0)\nh[:x] += 1\nputs h[:x]', "1"),
    T("Safe navigation", "`&.` stops on nil.", 'x = nil\np x&.length', "nil"),
    T("unless", "if not, as one word.", 'n = 1\nputs "small" unless n > 3', "small"),
    T("case with ranges", "`when` tests with ===.",
      'n = 7\nputs(case n\n     when 0..5 then "low"\n     else "high"\n     end)', "high"),
    T("Symbols to procs", "`&:upcase` is a block that calls upcase.",
      'p %w[a b].map(&:upcase)', '["A", "B"]'),
    T("Structs", "A quick class with named fields.",
      'P = Struct.new(:x, :y)\nputs P.new(1, 2).y', "2"),
    T("Comparable", "Define <=> and get the rest.",
      'class V\n  include Comparable\n  attr_reader :n\n  def initialize(n) = @n = n\n'
      '  def <=>(o) = n <=> o.n\nend\nputs V.new(1) < V.new(2)', "true"),
    T("each_cons", "Overlapping groups.", 'p [1, 3, 6].each_cons(2).map { |a, b| b - a }', "[2, 3]"),
    T("freeze", "An object that cannot change.",
      's = "hi".freeze\nputs s.frozen?', "true"),
    T("Ranges with step", "Every few items, counting up from the start.", 'p (0..10).step(5).to_a', "[0, 5, 10]"),
    T("String multiplication", "`*` repeats.", 'puts "ab" * 2', "abab"),
    T("gsub with a block", "Each match replaced by what the block returns.",
      'puts "a1b2".gsub(/\\d/) { |d| (d.to_i * 2).to_s }', "a2b4"),
    T("scan", "Every match, as an array.", 'p "a1b22".scan(/\\d+/)', '["1", "22"]'),
    T("ensure", "Runs either way.",
      'begin\n  puts "work"\nensure\n  puts "cleanup"\nend', "work\ncleanup"),
    T("Method with a block", "`yield` hands control to the caller's block.",
      'def twice\n  yield\n  yield\nend\ntwice { puts "hi" }', "hi\nhi"),
    T("Procs and lambdas", "Blocks you can keep.",
      'sq = ->(x) { x * x }\nputs sq.call(4)', "16"),
]


PHP = [
    U("More PHP"),
    T("sprintf", "Formatting into a string.", '<?php\necho sprintf("%03d", 7), "\\n";', "007"),
    T("str_repeat", "Repeating text.", '<?php\necho str_repeat("-", 3), "\\n";', "---"),
    T("strrev", "Reverses a string, byte by byte.", '<?php\necho strrev("abc"), "\\n";', "cba"),
    T("ucfirst", "Upper-casing the first letter.", '<?php\necho ucfirst("php"), "\\n";', "Php"),
    T("str_contains", "Since PHP 8.", '<?php\nvar_dump(str_contains("pycmd", "cm"));', "bool(true)"),
    T("in_array", "Membership.", '<?php\nvar_dump(in_array(2, [1, 2]));', "bool(true)"),
    T("array_sum", "Adds up every value in an array.", '<?php\necho array_sum([1, 2, 3]), "\\n";', "6"),
    T("array_keys", "The keys of an array.", '<?php\necho implode(",", array_keys(["a" => 1, "b" => 2])), "\\n";',
      "a,b"),
    T("sort", "In place; the keys are renumbered.",
      '<?php\n$a = [3, 1, 2];\nsort($a);\necho implode(",", $a), "\\n";', "1,2,3"),
    T("usort", "Sorting with your own comparison.",
      '<?php\n$a = ["ccc", "a", "bb"];\nusort($a, fn($x, $y) => strlen($x) <=> strlen($y));\n'
      'echo implode(",", $a), "\\n";', "a,bb,ccc"),
    T("The spaceship operator", "-1, 0 or 1.", '<?php\necho 1 <=> 2, "\\n";', "-1"),
    T("Null coalescing", "`??` for a missing key.", '<?php\n$a = [];\necho $a["x"] ?? "none", "\\n";',
      "none"),
    T("match", "A switch that is an expression, and strict.",
      '<?php\n$n = 2;\necho match ($n) {\n    1 => "one",\n    default => "other",\n}, "\\n";', "other"),
    T("Named arguments", "Since PHP 8.",
      '<?php\nfunction box(int $w, int $h) {\n    return $w * $h;\n}\necho box(h: 2, w: 3), "\\n";',
      "6"),
    T("Typed properties", "A class field with a type.",
      '<?php\nclass P {\n    public int $x = 1;\n}\necho (new P)->x, "\\n";', "1"),
    T("Readonly properties", "Set once, in the constructor.",
      '<?php\nclass P {\n    public function __construct(public readonly int $x) {}\n}\n'
      'echo (new P(4))->x, "\\n";', "4"),
    T("Enums", "Since PHP 8.1.",
      '<?php\nenum Light: string {\n    case Red = "r";\n    case Green = "g";\n}\n'
      'echo Light::Green->value, "\\n";', "g"),
    T("Closures with use", "Capturing a variable.",
      '<?php\n$n = 10;\n$add = function ($x) use ($n) {\n    return $x + $n;\n};\necho $add(5), "\\n";',
      "15"),
    T("Generators", "`yield` in a function.",
      '<?php\nfunction up() {\n    yield 1;\n    yield 2;\n}\nforeach (up() as $n) {\n    echo $n, "\\n";\n}',
      "1\n2"),
    T("json_encode", "Turns an array into a JSON string.", '<?php\necho json_encode(["a" => 1]), "\\n";', '{"a":1}'),
    T("json_decode", "From JSON, as an array with true.",
      '<?php\n$o = json_decode(\'{"a":1}\', true);\necho $o["a"], "\\n";', "1"),
    T("preg_match", "A regular expression test, with groups.",
      '<?php\npreg_match("/(\\\\d+)/", "a42b", $m);\necho $m[1], "\\n";', "42"),
    T("Traits", "Methods shared into classes.",
      '<?php\ntrait Loud {\n    public function shout() {\n        return "HI";\n    }\n}\n'
      'class P {\n    use Loud;\n}\necho (new P)->shout(), "\\n";', "HI"),
    T("Interfaces with constants", "A constant on an interface.",
      '<?php\ninterface Limits {\n    const MAX = 3;\n}\necho Limits::MAX, "\\n";', "3"),
]


LUA = [
    U("More Lua"),
    T("String repetition", "`string.rep`.", 'print(string.rep("-", 3))', "---"),
    T("string.find", "Where it is, start and end.", 'print(string.find("pycmd", "cm"))', "3\t4"),
    T("string.gsub", "Replace, and a count of how many.", 'print(string.gsub("aaa", "a", "b"))',
      "bbb\t3"),
    T("Patterns", "Lua's own, smaller than regex. `%d+` is digits.",
      'print(string.match("a42b", "%d+"))', "42"),
    T("gmatch", "Every match, as an iterator.",
      'for w in string.gmatch("a b c", "%a") do\n  print(w)\nend', "a\nb\nc"),
    T("string.byte and char", "Codes and characters.", 'print(string.byte("A"), string.char(66))',
      "65\tB"),
    T("Numeric for with a step", "Counting down.", 'for i = 3, 1, -1 do\n  print(i)\nend', "3\n2\n1"),
    T("repeat until", "The body runs at least once.",
      'local n = 0\nrepeat\n  n = n + 1\nuntil n >= 2\nprint(n)', "2"),
    T("table.remove", "Takes out an item and hands it back.",
      'local t = {1, 2, 3}\nprint(table.remove(t), #t)', "3\t2"),
    T("table.sort", "In place, with an optional comparator.",
      'local t = {3, 1, 2}\ntable.sort(t)\nprint(t[1], t[3])', "1\t3"),
    T("Sorting descending", "A comparison function.",
      'local t = {1, 3, 2}\ntable.sort(t, function(a, b) return a > b end)\nprint(t[1])', "3"),
    T("Varargs", "`...` and `select`.",
      'local function count(...)\n  return select("#", ...)\nend\nprint(count(1, 2, 3))', "3"),
    T("Closures", "A function that keeps a local alive.",
      'local function counter()\n  local n = 0\n  return function()\n    n = n + 1\n    return n\n'
      '  end\nend\nlocal c = counter()\nc()\nprint(c())', "2"),
    T("Integer division and modulo", "`//` floors, `%` is always non-negative.",
      'print(7 // 2, -7 % 3)', "3\t2"),
    T("math functions", "floor, max and friends.", 'print(math.floor(3.7), math.max(2, 9))', "3\t9"),
    T("tostring and type", "What it is, and as text.", 'print(type(5), tostring(5) .. "!")',
      "number\t5!"),
    T("Metatables: __add", "Operator overloading.",
      'local mt = {__add = function(a, b) return a.v + b.v end}\n'
      'local a = setmetatable({v = 1}, mt)\nlocal b = setmetatable({v = 2}, mt)\nprint(a + b)', "3"),
    T("Metatables: __tostring", "What print shows.",
      'local mt = {__tostring = function() return "P()" end}\n'
      'local p = setmetatable({}, mt)\nprint(p)', "P()"),
    T("A class pattern", "A table, a metatable and `new`.",
      'local Dog = {}\nDog.__index = Dog\nfunction Dog.new(name)\n  return setmetatable({name = name}, Dog)\n'
      'end\nfunction Dog:speak()\n  return self.name .. " says woof"\nend\nprint(Dog.new("rex"):speak())',
      "rex says woof"),
    T("goto continue", "Lua's way to skip a loop turn.",
      'for i = 1, 3 do\n  if i == 2 then goto continue end\n  print(i)\n  ::continue::\nend', "1\n3"),
    T("error and pcall", "Raising and catching, with a message.",
      'local ok, err = pcall(function() error("no", 0) end)\nprint(ok, err)', "false\tno"),
]


SHELL = [
    U("More shell"),
    T("Arithmetic", "`$(( ))` does whole-number maths.", '#!/bin/sh\necho $((7 / 2))', "3"),
    T("String length", "`${#name}`.", '#!/bin/bash\ns="pycmd"\necho "${#s}"', "5"),
    T("Substrings", "`${name:start:length}` in bash.", '#!/bin/bash\ns="pycmd"\necho "${s:0:2}"', "py"),
    T("Replacing in a variable", "`${name/old/new}`.", '#!/bin/bash\ns="aaa"\necho "${s//a/b}"', "bbb"),
    T("Stripping a suffix", "`${name%.*}` drops the extension.",
      '#!/bin/sh\nf="main.py"\necho "${f%.*}"', "main"),
    T("Stripping a prefix", "`${name##*/}` is basename.", '#!/bin/sh\np="/a/b/c.txt"\necho "${p##*/}"',
      "c.txt"),
    T("Arrays", "Bash has them; sh does not.", '#!/bin/bash\nxs=(a b c)\necho "${xs[1]} ${#xs[@]}"', "b 3"),
    T("Looping over an array", "Quote `\"${xs[@]}\"`.",
      '#!/bin/bash\nxs=(a b)\nfor x in "${xs[@]}"; do\n  echo "$x"\ndone', "a\nb"),
    T("case", "Pattern matching on a string.",
      '#!/bin/sh\nf="x.py"\ncase "$f" in\n  *.py) echo python ;;\n  *) echo other ;;\nesac', "python"),
    T("A here-document", "Several lines of input in place.",
      '#!/bin/sh\ncat <<EOF\none\ntwo\nEOF', "one\ntwo"),
    T("sed", "Edit a stream.", '#!/bin/sh\necho "a-b" | sed "s/-/+/"', "a+b"),
    T("tr", "Translate characters.", '#!/bin/sh\necho "abc" | tr a-z A-Z', "ABC"),
    T("cut", "Pick a field.", '#!/bin/sh\necho "a,b,c" | cut -d, -f2', "b"),
    T("sort and uniq", "Count the distinct lines.",
      '#!/bin/sh\nprintf "b\\na\\nb\\n" | sort | uniq -c | wc -l', "2"),
    T("head and tail", "The first few, the last few.", '#!/bin/sh\nprintf "1\\n2\\n3\\n" | tail -n 1', "3"),
    T("seq", "A sequence of numbers.", '#!/bin/sh\nseq 3', "1\n2\n3"),
    T("xargs", "Turn lines into arguments.", '#!/bin/sh\nprintf "a\\nb\\n" | xargs echo', "a b"),
    T("printf", "Better than echo for anything formatted.", '#!/bin/sh\nprintf "%03d\\n" 7', "007"),
    T("test with strings", "`=` compares, `-z` asks if empty.",
      '#!/bin/sh\ns=""\nif [ -z "$s" ]; then\n  echo empty\nfi', "empty"),
    T("Functions return status", "`return` is an exit code; echo is the value.",
      '#!/bin/sh\nis_big() {\n  [ "$1" -gt 3 ]\n}\nif is_big 5; then echo yes; fi', "yes"),
    T("local", "A variable that does not escape the function.",
      '#!/bin/bash\nn=1\nf() {\n  local n=2\n}\nf\necho "$n"', "1"),
    T("trap", "Runs something when the script exits.",
      '#!/bin/sh\ntrap \'echo bye\' EXIT\necho hi', "hi\nbye"),
    T("Reading lines into variables", "`read` splits on spaces.",
      '#!/bin/sh\necho "a b" | while read -r x y; do\n  echo "$y$x"\ndone', "ba"),
    T("awk", "A whole language for columns.", '#!/bin/sh\necho "a 1\nb 2" | awk \'{s += $2} END {print s}\'',
      "3"),
]


SQL = [
    U("Queries in depth"),
    T("Expressions in SELECT", "Columns can be calculated.",
      'SELECT 2 + 3 AS total;', "5"),
    T("Text functions", "UPPER, LOWER, LENGTH.", "SELECT UPPER('sql'), LENGTH('abc');", "SQL|3"),
    T("Concatenation", "`||` joins text in SQLite and Postgres.", "SELECT 'py' || 'cmd';", "pycmd"),
    T("CASE", "An if inside a query.",
      "SELECT CASE WHEN 5 > 3 THEN 'big' ELSE 'small' END;", "big"),
    T("BETWEEN", "Inclusive at both ends.", "SELECT 5 BETWEEN 1 AND 5;", "1"),
    T("ROUND", "Rounding to places.", "SELECT ROUND(3.14159, 2);", "3.14"),
    T("SUBSTR", "Part of a string, counted from 1.", "SELECT SUBSTR('pycmd', 1, 2);", "py"),
    T("REPLACE", "Every occurrence.", "SELECT REPLACE('aaa', 'a', 'b');", "bbb"),
    T("COALESCE", "The first value that is not NULL.", "SELECT COALESCE(NULL, NULL, 7);", "7"),
    T("NULL arithmetic", "Anything with NULL is NULL.", "SELECT (1 + NULL) IS NULL;", "1"),
    T("A table, then a query", "CREATE, INSERT, SELECT - the whole loop.",
      "CREATE TABLE t (n INTEGER);\nINSERT INTO t VALUES (1), (2), (3);\nSELECT SUM(n) FROM t;", "6"),
    T("WHERE and ORDER BY together", "Filter, then sort.",
      "CREATE TABLE t (n INTEGER);\nINSERT INTO t VALUES (3), (1), (2);\n"
      "SELECT n FROM t WHERE n > 1 ORDER BY n;", "2\n3"),
    T("GROUP BY with COUNT", "One row per group.",
      "CREATE TABLE t (k TEXT);\nINSERT INTO t VALUES ('a'), ('b'), ('a');\n"
      "SELECT k, COUNT(*) FROM t GROUP BY k ORDER BY k;", "a|2\nb|1"),
    T("HAVING", "A filter on the groups.",
      "CREATE TABLE t (k TEXT);\nINSERT INTO t VALUES ('a'), ('b'), ('a');\n"
      "SELECT k FROM t GROUP BY k HAVING COUNT(*) > 1;", "a"),
    T("An inner join", "Rows that match in both.",
      "CREATE TABLE a (id INT, n TEXT);\nCREATE TABLE b (aid INT);\n"
      "INSERT INTO a VALUES (1, 'x'), (2, 'y');\nINSERT INTO b VALUES (2);\n"
      "SELECT n FROM a JOIN b ON b.aid = a.id;", "y"),
    T("A left join", "Every left row, matched or not.",
      "CREATE TABLE a (id INT);\nCREATE TABLE b (aid INT);\nINSERT INTO a VALUES (1), (2);\n"
      "INSERT INTO b VALUES (2);\n"
      "SELECT COUNT(*) FROM a LEFT JOIN b ON b.aid = a.id;", "2"),
    T("A subquery in WHERE", "A query inside a query.",
      "CREATE TABLE t (n INT);\nINSERT INTO t VALUES (1), (5), (9);\n"
      "SELECT n FROM t WHERE n > (SELECT AVG(n) FROM t);", "9"),
    T("UNION", "Two queries, one result, duplicates removed.",
      "SELECT 1 UNION SELECT 1 UNION SELECT 2;", "1\n2"),
    T("A CTE", "A named query to build on.",
      "WITH nums(n) AS (SELECT 1 UNION ALL SELECT 2)\nSELECT SUM(n) FROM nums;", "3"),
    T("A recursive CTE", "Counting with SQL alone.",
      "WITH RECURSIVE c(n) AS (\n  SELECT 1\n  UNION ALL\n  SELECT n + 1 FROM c WHERE n < 3\n)\n"
      "SELECT n FROM c;", "1\n2\n3"),
    T("A window function", "A running total, without collapsing rows.",
      "CREATE TABLE t (n INT);\nINSERT INTO t VALUES (1), (2), (3);\n"
      "SELECT SUM(n) OVER (ORDER BY n) FROM t;", "1\n3\n6"),
    T("ROW_NUMBER", "Numbering the rows of a result.",
      "CREATE TABLE t (k TEXT);\nINSERT INTO t VALUES ('b'), ('a');\n"
      "SELECT k, ROW_NUMBER() OVER (ORDER BY k) FROM t;", "a|1\nb|2"),
    T("UPDATE with an expression", "Changing rows in place.",
      "CREATE TABLE t (n INT);\nINSERT INTO t VALUES (1);\nUPDATE t SET n = n * 10;\n"
      "SELECT n FROM t;", "10"),
    T("INSERT from a SELECT", "Copying rows.",
      "CREATE TABLE a (n INT);\nCREATE TABLE b (n INT);\nINSERT INTO a VALUES (4);\n"
      "INSERT INTO b SELECT n FROM a;\nSELECT n FROM b;", "4"),
    T("Upsert", "Insert, or update when the key exists.",
      "CREATE TABLE t (k TEXT PRIMARY KEY, n INT);\nINSERT INTO t VALUES ('a', 1);\n"
      "INSERT INTO t VALUES ('a', 5)\n  ON CONFLICT(k) DO UPDATE SET n = excluded.n;\n"
      "SELECT n FROM t;", "5"),
    T("A view", "A saved query that behaves like a table.",
      "CREATE TABLE t (n INT);\nINSERT INTO t VALUES (1), (2);\n"
      "CREATE VIEW big AS SELECT n FROM t WHERE n > 1;\nSELECT COUNT(*) FROM big;", "1"),
]

EXTRA = {
    "typescript": TYPESCRIPT, "ruby": RUBY, "php": PHP, "lua": LUA, "shell": SHELL, "sql": SQL,
}
