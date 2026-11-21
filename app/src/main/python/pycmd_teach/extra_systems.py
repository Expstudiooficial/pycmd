"""More units for Rust, Go, C++, Java, Kotlin and Swift, added in 2.8.0.

Appended after the existing units so no finished lesson changes its id. The
Rust and Go snippets run on the app's own interpreters *and* on the real
compilers in `tools/test_teach.py`; C++ and Java are checked against g++ and
the JDK wherever those are installed.
"""

from . import T, U


def _rs(body: str) -> str:
    return "fn main() {\n" + body + "\n}"


def _go(body: str, imports=("fmt",)) -> str:
    if len(imports) == 1:
        head = f'package main\n\nimport "{imports[0]}"\n\n'
    else:
        head = "package main\n\nimport (\n" + "".join(f'\t"{i}"\n' for i in imports) + ")\n\n"
    return head + "func main() {\n" + body + "\n}"


RUST = [
    U("Strings and text", "Owned and borrowed, and the methods worth knowing."),
    T("&str versus String", "A literal is a borrowed `&str`; `to_string` owns it.",
      _rs('    let s: String = "hi".to_string();\n    println!("{}", s.len());'), "2"),
    T("format!", "println! that gives back a String instead of printing.",
      _rs('    let s = format!("{}-{}", 1, 2);\n    println!("{}", s);'), "1-2"),
    T("chars", "Walks the characters, not the bytes.",
      _rs('    let n = "héllo".chars().count();\n    println!("{}", n);'), "5"),
    T("rev", "Reversing a string goes through its chars.",
      _rs('    let r: String = "abc".chars().rev().collect();\n    println!("{}", r);'), "cba"),
    T("starts_with", "Asking about the front.",
      _rs('    println!("{}", "main.rs".ends_with(".rs"));'), "true"),
    T("split_whitespace", "Words, however many spaces between them.",
      _rs('    let n = "a  b c".split_whitespace().count();\n    println!("{}", n);'), "3"),
    T("Padding", "`{:>4}` right-aligns in four columns.",
      _rs('    println!("[{:>4}]", 7);'), "[   7]"),
    T("Decimal places", "`{:.2}` for two.",
      _rs('    println!("{:.2}", 3.14159);'), "3.14"),
    T("Zero padding", "`{:03}` pads with zeros.",
      _rs('    println!("{:03}", 7);'), "007"),
    T("Hex and binary", "`{:x}` and `{:b}`.",
      _rs('    println!("{:x} {:b}", 255, 5);'), "ff 101"),
    T("char methods", "A char can say what it is.",
      _rs("    println!(\"{}\", 'a'.is_alphabetic());"), "true"),
    T("to_uppercase on a char", "Gives an iterator, because some letters become two.",
      _rs("    let up: String = 'a'.to_uppercase().collect();\n    println!(\"{}\", up);"), "A"),

    U("Iterators in depth"),
    T("enumerate", "Index and item together.",
      _rs('    for (i, c) in "ab".chars().enumerate() {\n        println!("{} {}", i, c);\n    }'),
      "0 a\n1 b"),
    T("zip", "Two iterators in step.",
      _rs('    let a = [1, 2];\n    let b = [3, 4];\n'
          '    for (x, y) in a.iter().zip(b.iter()) {\n        println!("{}", x + y);\n    }'),
      "4\n6"),
    T("any and all", "Questions about every item.",
      _rs('    let v = vec![1, 2, 3];\n    let any = v.iter().any(|&n| n > 2);\n'
          '    let all = v.iter().all(|&n| n > 2);\n    println!("{} {}", any, all);'),
      "true false"),
    T("position", "Where the first match is, as an Option.",
      _rs('    let v = vec![5, 7, 9];\n    println!("{:?}", v.iter().position(|&n| n == 7));'),
      "Some(1)"),
    T("max and min", "Options again: an empty iterator has neither.",
      _rs('    let v = vec![3, 9, 2];\n    println!("{:?}", v.iter().max());'), "Some(9)"),
    T("fold", "Carries a value through every item.",
      _rs('    let total = (1..=4).fold(0, |acc, n| acc + n);\n    println!("{}", total);'),
      "10"),
    T("take and skip", "The front, or everything after it.",
      _rs('    let v: Vec<i32> = (1..10).skip(2).take(3).collect();\n    println!("{:?}", v);'),
      "[3, 4, 5]"),
    T("chain", "One iterator after another.",
      _rs('    let v: Vec<i32> = (1..3).chain(7..9).collect();\n    println!("{:?}", v);'),
      "[1, 2, 7, 8]"),
    T("rev on a range", "Counting down.",
      _rs('    for i in (1..4).rev() {\n        println!("{}", i);\n    }'), "3\n2\n1"),
    T("step_by", "Every second item.",
      _rs('    let v: Vec<i32> = (0..7).step_by(3).collect();\n    println!("{:?}", v);'),
      "[0, 3, 6]"),
    T("windows", "Overlapping pairs from a slice.",
      _rs('    let v = [1, 3, 6];\n    for w in v.windows(2) {\n'
          '        println!("{}", w[1] - w[0]);\n    }'), "2\n3"),
    T("sum of squares", "map then sum, typed at the end.",
      _rs('    let s: i32 = (1..=3).map(|n| n * n).sum();\n    println!("{}", s);'), "14"),

    U("Collections in depth"),
    T("HashMap entry", "Insert-or-update in one call.",
      'use std::collections::HashMap;\n\nfn main() {\n    let mut m = HashMap::new();\n'
      '    for w in ["a", "b", "a"] {\n        *m.entry(w).or_insert(0) += 1;\n    }\n'
      '    println!("{}", m["a"]);\n}', "2"),
    T("contains_key", "Asking without taking.",
      'use std::collections::HashMap;\n\nfn main() {\n    let mut m = HashMap::new();\n'
      '    m.insert("k", 1);\n    println!("{}", m.contains_key("k"));\n}', "true"),
    T("BTreeMap", "A map that keeps its keys sorted.",
      'use std::collections::BTreeMap;\n\nfn main() {\n    let mut m = BTreeMap::new();\n'
      '    m.insert(2, "b");\n    m.insert(1, "a");\n'
      '    let keys: Vec<_> = m.keys().collect();\n    println!("{:?}", keys);\n}', "[1, 2]"),
    T("Vec contains", "Linear search, built in.",
      _rs('    let v = vec![1, 2, 3];\n    println!("{}", v.contains(&2));'), "true"),
    T("Vec pop", "Takes the last item, as an Option.",
      _rs('    let mut v = vec![1, 2];\n    println!("{:?}", v.pop());'), "Some(2)"),
    T("retain", "Keeps only the items that pass.",
      _rs('    let mut v = vec![1, 2, 3, 4];\n    v.retain(|&n| n % 2 == 0);\n'
          '    println!("{:?}", v);'), "[2, 4]"),
    T("dedup", "Removes consecutive repeats.",
      _rs('    let mut v = vec![1, 1, 2, 2, 1];\n    v.dedup();\n    println!("{:?}", v);'),
      "[1, 2, 1]"),
    T("sort_by_key", "Sorting by something derived.",
      _rs('    let mut v = vec!["ccc", "a", "bb"];\n    v.sort_by_key(|s| s.len());\n'
          '    println!("{:?}", v);'), '["a", "bb", "ccc"]'),
    T("A tuple", "Mixed types, reached by position.",
      _rs('    let t = (1, "two");\n    println!("{} {}", t.0, t.1);'), "1 two"),
    T("Destructuring a tuple", "Names on the left take the parts.",
      _rs('    let (a, b) = (3, 4);\n    println!("{}", a * b);'), "12"),
    T("Slices", "A view into part of an array or Vec.",
      _rs('    let v = [1, 2, 3, 4];\n    let s = &v[1..3];\n    println!("{:?}", s);'),
      "[2, 3]"),

    U("Traits and generics"),
    T("A generic function", "`<T>` with a bound saying what T must do.",
      'fn largest<T: PartialOrd + Copy>(xs: &[T]) -> T {\n    let mut m = xs[0];\n'
      '    for &x in xs {\n        if x > m {\n            m = x;\n        }\n    }\n    m\n}\n\n'
      'fn main() {\n    println!("{}", largest(&[3, 9, 2]));\n}', "9"),
    T("A default method", "A trait can supply a method body.",
      'trait Greet {\n    fn name(&self) -> String;\n    fn hi(&self) -> String {\n'
      '        format!("hi {}", self.name())\n    }\n}\n\nstruct Dog;\n\n'
      'impl Greet for Dog {\n    fn name(&self) -> String {\n        String::from("rex")\n'
      '    }\n}\n\nfn main() {\n    println!("{}", Dog.hi());\n}', "hi rex"),
    T("derive Debug", "Printing your own type with `{:?}`.",
      '#[derive(Debug)]\nstruct P {\n    x: i32,\n}\n\nfn main() {\n'
      '    println!("{:?}", P { x: 1 });\n}', "P { x: 1 }"),
    T("derive PartialEq", "`==` for your own type, written for you.",
      '#[derive(PartialEq)]\nstruct P {\n    x: i32,\n}\n\nfn main() {\n'
      '    println!("{}", P { x: 1 } == P { x: 1 });\n}', "true"),
    T("impl Display", "What `{}` prints for your type.",
      'use std::fmt;\n\nstruct P(i32);\n\nimpl fmt::Display for P {\n'
      '    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {\n'
      '        write!(f, "<{}>", self.0)\n    }\n}\n\nfn main() {\n    println!("{}", P(5));\n}',
      "<5>"),
    T("A tuple struct", "A struct whose fields have positions instead of names.",
      'struct Metres(f64);\n\nfn main() {\n    let m = Metres(2.5);\n    println!("{}", m.0);\n}',
      "2.5"),
    T("impl blocks with self", "`&mut self` for a method that changes the value.",
      'struct C {\n    n: i32,\n}\n\nimpl C {\n    fn bump(&mut self) {\n        self.n += 1;\n'
      '    }\n}\n\nfn main() {\n    let mut c = C { n: 0 };\n    c.bump();\n'
      '    println!("{}", c.n);\n}', "1"),
    T("Trait objects", "`Box<dyn Trait>` holds any type that implements it.",
      'trait Shape {\n    fn area(&self) -> i32;\n}\n\nstruct Sq(i32);\n\n'
      'impl Shape for Sq {\n    fn area(&self) -> i32 {\n        self.0 * self.0\n    }\n}\n\n'
      'fn main() {\n    let s: Box<dyn Shape> = Box::new(Sq(3));\n    println!("{}", s.area());\n}',
      "9"),
    T("Option combinators", "`map` reaches inside without unwrapping.",
      _rs('    let n: Option<i32> = Some(4);\n    println!("{:?}", n.map(|x| x * 2));'),
      "Some(8)"),
    T("The ? operator", "Returns early with the error, if there is one.",
      'use std::num::ParseIntError;\n\nfn parse(s: &str) -> Result<i32, ParseIntError> {\n'
      '    let n: i32 = s.parse()?;\n    Ok(n + 1)\n}\n\n'
      'fn main() {\n    println!("{:?}", parse("41"));\n}', "Ok(42)"),
    T("if let", "Matching one pattern, ignoring the rest.",
      _rs('    let n = Some(3);\n    if let Some(v) = n {\n        println!("{}", v);\n    }'),
      "3"),
    T("while let", "Loops while a pattern keeps matching.",
      _rs('    let mut v = vec![1, 2];\n    while let Some(x) = v.pop() {\n'
          '        println!("{}", x);\n    }'), "2\n1"),
    T("match guards", "An `if` on a match arm.",
      _rs('    let n = 7;\n    match n {\n        x if x % 2 == 0 => println!("even"),\n'
          '        _ => println!("odd"),\n    }'), "odd"),
    T("Shadowing", "A new `let` with the same name replaces the old one.",
      _rs('    let x = 5;\n    let x = x * 2;\n    println!("{}", x);'), "10"),
    T("const", "A compile-time constant, typed and upper case.",
      'const LIMIT: i32 = 3;\n\nfn main() {\n    println!("{}", LIMIT * 2);\n}', "6"),
]


GO = [
    U("Strings in depth"),
    T("strings.Repeat", "Repeating text.",
      _go('\tfmt.Println(strings.Repeat("-", 3))', ("fmt", "strings")), "---"),
    T("strings.Fields", "Words, however many spaces.",
      _go('\tfmt.Println(len(strings.Fields("a  b c")))', ("fmt", "strings")), "3"),
    T("strings.HasPrefix", "Asking about the front.",
      _go('\tfmt.Println(strings.HasSuffix("main.go", ".go"))', ("fmt", "strings")), "true"),
    T("strings.Index", "-1 when it is not there.",
      _go('\tfmt.Println(strings.Index("pycmd", "z"))', ("fmt", "strings")), "-1"),
    T("strings.TrimSpace", "Whitespace off both ends.",
      _go('\tfmt.Println(strings.TrimSpace("  hi  "))', ("fmt", "strings")), "hi"),
    T("strings.ReplaceAll", "Every occurrence.",
      _go('\tfmt.Println(strings.ReplaceAll("aaa", "a", "b"))', ("fmt", "strings")), "bbb"),
    T("strings.Count", "How many times.",
      _go('\tfmt.Println(strings.Count("banana", "a"))', ("fmt", "strings")), "3"),
    T("strings.Title case by hand", "Upper-case the first byte of a word.",
      _go('\tw := "go"\n\tfmt.Println(strings.ToUpper(w[:1]) + w[1:])', ("fmt", "strings")), "Go"),
    T("Runes", "A range over a string gives runes, not bytes.",
      _go('\tn := 0\n\tfor range "héllo" {\n\t\tn++\n\t}\n\tfmt.Println(n)'), "5"),
    T("Sprintf", "Printf into a string.",
      _go('\ts := fmt.Sprintf("%d-%d", 1, 2)\n\tfmt.Println(s)'), "1-2"),
    T("Printf width", "`%4d` pads to four columns.",
      _go('\tfmt.Printf("[%4d]\\n", 7)'), "[   7]"),
    T("Printf %v", "The default format for anything.",
      _go('\tfmt.Printf("%v\\n", []int{1, 2})'), "[1 2]"),
    T("Printf %q", "A quoted string.",
      _go('\tfmt.Printf("%q\\n", "hi")'), '"hi"'),
    T("Printf %T", "The type of a value.",
      _go('\tfmt.Printf("%T\\n", 3.5)'), "float64"),
    T("strconv.FormatInt", "A number in another base.",
      _go('\tfmt.Println(strconv.FormatInt(255, 16))', ("fmt", "strconv")), "ff"),
    T("strings.Builder", "Building text efficiently.",
      _go('\tvar b strings.Builder\n\tb.WriteString("py")\n\tb.WriteString("cmd")\n'
          '\tfmt.Println(b.String())', ("fmt", "strings")), "pycmd"),

    U("Slices and maps in depth"),
    T("len and cap", "How many there are, and how many fit.",
      _go('\ts := make([]int, 2, 5)\n\tfmt.Println(len(s), cap(s))'), "2 5"),
    T("copy", "Copies into an existing slice.",
      _go('\tsrc := []int{1, 2}\n\tdst := make([]int, 2)\n\tcopy(dst, src)\n\tfmt.Println(dst)'),
      "[1 2]"),
    T("Appending a slice", "`...` spreads the second one.",
      _go('\ta := []int{1}\n\ta = append(a, []int{2, 3}...)\n\tfmt.Println(a)'), "[1 2 3]"),
    T("Slices share memory", "Changing a sub-slice changes the original.",
      _go('\ta := []int{1, 2, 3}\n\tb := a[:2]\n\tb[0] = 9\n\tfmt.Println(a)'), "[9 2 3]"),
    T("A 2D slice", "A slice of slices.",
      _go('\tg := [][]int{{1, 2}, {3, 4}}\n\tfmt.Println(g[1][0])'), "3"),
    T("Map iteration order", "Random on purpose. Sort the keys if order matters.",
      _go('\tm := map[string]int{"b": 1, "a": 2}\n\tkeys := []string{}\n\tfor k := range m {\n'
          '\t\tkeys = append(keys, k)\n\t}\n\tsort.Strings(keys)\n\tfmt.Println(keys)',
          ("fmt", "sort")), "[a b]"),
    T("Map of slices", "Grouping things under a key.",
      _go('\tm := map[string][]int{}\n\tm["a"] = append(m["a"], 1)\n\tfmt.Println(m["a"])'), "[1]"),
    T("Counting with a map", "A missing key reads as zero.",
      _go('\tm := map[rune]int{}\n\tfor _, c := range "aab" {\n\t\tm[c]++\n\t}\n\tfmt.Println(m[\'a\'])'),
      "2"),
    T("sort.Slice", "Sorting by anything, with a less function.",
      _go('\ts := []string{"ccc", "a", "bb"}\n'
          '\tsort.Slice(s, func(i, j int) bool {\n\t\treturn len(s[i]) < len(s[j])\n\t})\n'
          '\tfmt.Println(s)', ("fmt", "sort")), "[a bb ccc]"),
    T("An array", "A fixed size, part of the type.",
      _go('\tvar a [3]int\n\ta[1] = 5\n\tfmt.Println(a)'), "[0 5 0]"),
    T("Struct literals in a slice", "A table of records.",
      'package main\n\nimport "fmt"\n\ntype P struct {\n\tName string\n}\n\nfunc main() {\n'
      '\tps := []P{{"a"}, {"b"}}\n\tfmt.Println(ps[1].Name)\n}', "b"),
    T("Embedding", "A struct inside a struct lends it its fields.",
      'package main\n\nimport "fmt"\n\ntype Base struct {\n\tID int\n}\n\ntype User struct {\n'
      '\tBase\n\tName string\n}\n\nfunc main() {\n\tu := User{Base{7}, "a"}\n\tfmt.Println(u.ID)\n}',
      "7"),
    T("Printing a struct", "`%+v` names the fields.",
      'package main\n\nimport "fmt"\n\ntype P struct {\n\tX int\n}\n\nfunc main() {\n'
      '\tfmt.Printf("%+v\\n", P{1})\n}', "{X:1}"),

    U("Functions and interfaces in depth"),
    T("Closures", "A function that remembers a variable.",
      _go('\tcount := 0\n\tinc := func() int {\n\t\tcount++\n\t\treturn count\n\t}\n'
          '\tinc()\n\tfmt.Println(inc())'), "2"),
    T("Returning a function", "A function factory.",
      'package main\n\nimport "fmt"\n\nfunc adder(n int) func(int) int {\n'
      '\treturn func(x int) int { return x + n }\n}\n\nfunc main() {\n\tfmt.Println(adder(10)(5))\n}',
      "15"),
    T("defer order", "Deferred calls run last-in, first-out.",
      _go('\tfor i := 0; i < 3; i++ {\n\t\tdefer fmt.Println(i)\n\t}'), "2\n1\n0"),
    T("The Stringer interface", "A String method controls how it prints.",
      'package main\n\nimport "fmt"\n\ntype P struct{ X int }\n\n'
      'func (p P) String() string {\n\treturn fmt.Sprintf("<%d>", p.X)\n}\n\n'
      'func main() {\n\tfmt.Println(P{5})\n}', "<5>"),
    T("Type switch", "Branching on what a value really is.",
      'package main\n\nimport "fmt"\n\nfunc kind(v interface{}) string {\n\tswitch v.(type) {\n'
      '\tcase int:\n\t\treturn "int"\n\tcase string:\n\t\treturn "string"\n\t}\n\treturn "other"\n}\n\n'
      'func main() {\n\tfmt.Println(kind("x"))\n}', "string"),
    T("Type assertion", "Getting the concrete value back out.",
      _go('\tvar v interface{} = 7\n\tn, ok := v.(int)\n\tfmt.Println(n, ok)'), "7 true"),
    T("errors.Is", "Comparing against a known error.",
      'package main\n\nimport (\n\t"errors"\n\t"fmt"\n)\n\nvar ErrNone = errors.New("none")\n\n'
      'func main() {\n\terr := fmt.Errorf("lookup: %w", ErrNone)\n'
      '\tfmt.Println(errors.Is(err, ErrNone))\n}', "true"),
    T("fmt.Errorf", "An error with a formatted message.",
      _go('\terr := fmt.Errorf("bad value %d", 3)\n\tfmt.Println(err)'), "bad value 3"),
    T("A custom error type", "Anything with an Error() string method.",
      'package main\n\nimport "fmt"\n\ntype NotFound struct{ Name string }\n\n'
      'func (e NotFound) Error() string {\n\treturn e.Name + " not found"\n}\n\n'
      'func main() {\n\tvar err error = NotFound{"x"}\n\tfmt.Println(err)\n}', "x not found"),
    T("select", "Waits on whichever channel is ready.",
      _go('\tc := make(chan int, 1)\n\tc <- 4\n\tselect {\n\tcase n := <-c:\n'
          '\t\tfmt.Println(n)\n\tdefault:\n\t\tfmt.Println("none")\n\t}'), "4"),
    T("A Mutex", "One goroutine at a time in the critical section.",
      'package main\n\nimport (\n\t"fmt"\n\t"sync"\n)\n\nfunc main() {\n\tvar mu sync.Mutex\n'
      '\tvar wg sync.WaitGroup\n\tn := 0\n\tfor i := 0; i < 10; i++ {\n\t\twg.Add(1)\n'
      '\t\tgo func() {\n\t\t\tdefer wg.Done()\n\t\t\tmu.Lock()\n\t\t\tn++\n\t\t\tmu.Unlock()\n'
      '\t\t}()\n\t}\n\twg.Wait()\n\tfmt.Println(n)\n}', "10"),
    T("Worker results on a channel", "Fan out, then collect.",
      _go('\tout := make(chan int, 3)\n\tfor i := 1; i <= 3; i++ {\n\t\tgo func(n int) {\n'
          '\t\t\tout <- n * n\n\t\t}(i)\n\t}\n\tsum := 0\n\tfor i := 0; i < 3; i++ {\n'
          '\t\tsum += <-out\n\t}\n\tfmt.Println(sum)'), "14"),
    T("math", "The usual functions, all on float64.",
      _go('\tfmt.Println(math.Sqrt(16), math.Max(2, 9))', ("fmt", "math")), "4 9"),
    T("Labelled break", "Leaving an outer loop from an inner one.",
      _go('outer:\n\tfor i := 0; i < 3; i++ {\n\t\tfor j := 0; j < 3; j++ {\n'
          '\t\t\tif j == 1 {\n\t\t\t\tbreak outer\n\t\t\t}\n\t\t\tfmt.Println(i, j)\n\t\t}\n\t}'),
      "0 0"),
    T("iota", "Counting constants.",
      'package main\n\nimport "fmt"\n\nconst (\n\tA = iota\n\tB\n\tC\n)\n\n'
      'func main() {\n\tfmt.Println(A, B, C)\n}', "0 1 2"),
]


def _cpp(body: str, includes=("iostream",)) -> str:
    head = "".join(f"#include <{i}>\n" for i in includes)
    return head + "\nint main() {\n" + body + "\n    return 0;\n}"


CPP = [
    U("The standard library"),
    T("std::vector::at", "Like `[]`, but checked.",
      _cpp('    std::vector<int> v{1, 2};\n    std::cout << v.at(1) << "\\n";',
           ("iostream", "vector")), "2"),
    T("Iterating with an index", "`size()` gives a size_t.",
      _cpp('    std::vector<int> v{4, 5};\n'
           '    for (size_t i = 0; i < v.size(); i++)\n        std::cout << v[i] << "\\n";',
           ("iostream", "vector")), "4\n5"),
    T("std::accumulate", "Sums a range, from <numeric>.",
      _cpp('    std::vector<int> v{1, 2, 3};\n'
           '    int total = std::accumulate(v.begin(), v.end(), 0);\n'
           '    std::cout << total << "\\n";',
           ("iostream", "numeric", "vector")), "6"),
    T("std::find", "An iterator to the match, or end().",
      _cpp('    std::vector<int> v{1, 2, 3};\n    auto it = std::find(v.begin(), v.end(), 2);\n'
           '    std::cout << (it - v.begin()) << "\\n";', ("algorithm", "iostream", "vector")), "1"),
    T("std::count_if", "How many pass a test.",
      _cpp('    std::vector<int> v{1, 2, 3, 4};\n'
           '    auto even = [](int x) { return x % 2 == 0; };\n'
           '    auto n = std::count_if(v.begin(), v.end(), even);\n'
           '    std::cout << n << "\\n";', ("algorithm", "iostream", "vector")), "2"),
    T("std::reverse", "Reverses a range in place, from <algorithm>.",
      _cpp('    std::string s = "abc";\n    std::reverse(s.begin(), s.end());\n'
           '    std::cout << s << "\\n";', ("algorithm", "iostream", "string")), "cba"),
    T("std::max_element", "An iterator to the biggest.",
      _cpp('    std::vector<int> v{3, 9, 2};\n'
           '    auto biggest = std::max_element(v.begin(), v.end());\n'
           '    std::cout << *biggest << "\\n";',
           ("algorithm", "iostream", "vector")), "9"),
    T("std::set", "Sorted, unique.",
      _cpp('    std::set<int> s{3, 1, 3};\n    std::cout << s.size() << "\\n";',
           ("iostream", "set")), "2"),
    T("std::unordered_map", "A hash map; faster, unordered.",
      _cpp('    std::unordered_map<std::string, int> m;\n    m["a"] += 2;\n'
           '    std::cout << m["a"] << "\\n";', ("iostream", "string", "unordered_map")), "2"),
    T("std::pair", "Two values together.",
      _cpp('    std::pair<int, std::string> p{1, "one"};\n'
           '    std::cout << p.second << "\\n";', ("iostream", "string")), "one"),
    T("Structured bindings", "Unpacking a pair into names.",
      _cpp('    std::pair<int, int> p{3, 4};\n    auto [a, b] = p;\n'
           '    std::cout << a + b << "\\n";', ("iostream",)), "7"),
    T("std::optional", "A value that may be missing.",
      _cpp('    std::optional<int> n;\n    std::cout << n.value_or(0) << "\\n";',
           ("iostream", "optional")), "0"),
    T("std::to_string", "A number as a string.",
      _cpp('    std::string s = "n=" + std::to_string(5);\n    std::cout << s << "\\n";',
           ("iostream", "string")), "n=5"),
    T("std::stoi", "A string as a number.",
      _cpp('    std::cout << std::stoi("41") + 1 << "\\n";', ("iostream", "string")), "42"),
    T("std::string::find", "npos when it is missing.",
      _cpp('    std::string s = "pycmd";\n'
           '    bool missing = s.find("z") == std::string::npos;\n'
           '    std::cout << missing << "\\n";',
           ("iostream", "string")), "1"),
    T("std::array", "A fixed-size array that knows its size.",
      _cpp('    std::array<int, 3> a{1, 2, 3};\n    std::cout << a.size() << "\\n";',
           ("array", "iostream")), "3"),
    T("constexpr", "Worked out at compile time.",
      '#include <iostream>\n\nconstexpr int square(int n) { return n * n; }\n\n'
      'int main() {\n    std::cout << square(5) << "\\n";\n    return 0;\n}', "25"),
    T("shared_ptr", "Shared ownership, freed when the last one goes.",
      _cpp('    auto a = std::make_shared<int>(5);\n    auto b = a;\n'
           '    std::cout << a.use_count() << "\\n";', ("iostream", "memory")), "2"),
    T("Range-for by reference", "`auto&` to change the items in place.",
      _cpp('    std::vector<int> v{1, 2};\n    for (auto& n : v) n *= 10;\n'
           '    std::cout << v[1] << "\\n";', ("iostream", "vector")), "20"),
    T("std::sort with a lambda", "Descending order.",
      _cpp('    std::vector<int> v{1, 3, 2};\n'
           '    auto desc = [](int a, int b) { return a > b; };\n'
           '    std::sort(v.begin(), v.end(), desc);\n'
           '    std::cout << v[0] << "\\n";', ("algorithm", "iostream", "vector")), "3"),
    T("Operator overloading", "Teaching `+` a new type.",
      '#include <iostream>\n\nstruct V {\n    int x;\n};\n\nV operator+(V a, V b) { return {a.x + b.x}; }\n\n'
      'int main() {\n    std::cout << (V{1} + V{2}).x << "\\n";\n    return 0;\n}', "3"),
    T("A namespace", "Grouping names to avoid clashes.",
      '#include <iostream>\n\nnamespace maths {\nint twice(int n) { return n * 2; }\n}\n\n'
      'int main() {\n    std::cout << maths::twice(4) << "\\n";\n    return 0;\n}', "8"),
]


def _java(body: str, imports=()) -> str:
    head = "".join(f"import {i};\n" for i in imports)
    if head:
        head += "\n"
    return (head + "public class Main {\n    public static void main(String[] args) {\n"
            + body + "\n    }\n}")


JAVA = [
    U("Strings and collections in depth"),
    T("String.format", "printf into a string.",
      _java('        System.out.println(String.format("%d-%d", 1, 2));'), "1-2"),
    T("StringBuilder", "Building text in a loop without a new String each time.",
      _java('        var sb = new StringBuilder();\n        sb.append("py").append("cmd");\n'
            '        System.out.println(sb);'), "pycmd"),
    T("String.join", "Joining with a separator.",
      _java('        System.out.println(String.join("-", "a", "b"));'), "a-b"),
    T("split", "A regex, which matters when splitting on a dot.",
      _java('        System.out.println("a.b".split("\\\\.").length);'), "2"),
    T("chars", "A stream of the characters.",
      _java('        long n = "banana".chars()\n            .filter(c -> c == \'a\').count();\n'
            '        System.out.println(n);'), "3"),
    T("repeat", "Since Java 11.",
      _java('        System.out.println("-".repeat(3));'), "---"),
    T("isBlank and strip", "Two more from Java 11.",
      _java('        System.out.println("  hi ".strip());'), "hi"),
    T("Text blocks", "Three quotes for a multi-line string.",
      _java('        String s = """\n            a\n            b""";\n'
            '        System.out.println(s.lines().count());'), "2"),
    T("List.of", "An immutable list.",
      _java('        var xs = List.of(1, 2, 3);\n        System.out.println(xs.size());',
            ("java.util.List",)), "3"),
    T("Map.of", "An immutable map.",
      _java('        var m = Map.of("a", 1);\n        System.out.println(m.get("a"));',
            ("java.util.Map",)), "1"),
    T("getOrDefault", "Reading a missing key safely.",
      _java('        var m = new HashMap<String, Integer>();\n'
            '        System.out.println(m.getOrDefault("x", 0));', ("java.util.HashMap",)), "0"),
    T("merge", "Counting with a map, in one call.",
      _java('        var m = new HashMap<Character, Integer>();\n'
            '        for (char c : "aab".toCharArray())\n'
            '            m.merge(c, 1, Integer::sum);\n'
            '        System.out.println(m.get(\'a\'));', ("java.util.HashMap",)), "2"),
    T("Collections.sort", "Sorting a mutable list.",
      _java('        var xs = new ArrayList<>(List.of(3, 1, 2));\n        Collections.sort(xs);\n'
            '        System.out.println(xs);',
            ("java.util.ArrayList", "java.util.Collections", "java.util.List")), "[1, 2, 3]"),
    T("A Set", "No duplicates.",
      _java('        var s = new HashSet<>(List.of(1, 1, 2));\n        System.out.println(s.size());',
            ("java.util.HashSet", "java.util.List")), "2"),
    T("A Deque", "A stack or a queue, from either end.",
      _java('        var d = new ArrayDeque<Integer>();\n        d.push(1);\n        d.push(2);\n'
            '        System.out.println(d.pop());', ("java.util.ArrayDeque",)), "2"),
    T("Iterating a map", "entrySet gives key and value.",
      _java('        var m = new TreeMap<>(Map.of("b", 2, "a", 1));\n'
            '        for (var e : m.entrySet())\n'
            '            System.out.println(e.getKey() + e.getValue());',
            ("java.util.Map", "java.util.TreeMap")), "a1\nb2"),

    U("Streams and functional Java"),
    T("map and collect", "A new list from an old one.",
      _java('        var xs = List.of(1, 2).stream()\n            .map(n -> n * 2)\n'
            '            .collect(Collectors.toList());\n        System.out.println(xs);', ("java.util.List", "java.util.stream.Collectors")),
      "[2, 4]"),
    T("filter", "Keeps the ones that pass.",
      _java('        long n = List.of(1, 2, 3).stream()\n            .filter(x -> x > 1).count();\n'
            '        System.out.println(n);', ("java.util.List",)), "2"),
    T("IntStream.range", "Numbers without a loop.",
      _java('        System.out.println(IntStream.range(1, 4).sum());',
            ("java.util.stream.IntStream",)), "6"),
    T("joining", "A stream into one string.",
      _java('        var s = Stream.of("a", "b")\n            .collect(Collectors.joining(","));\n'
            '        System.out.println(s);', ("java.util.stream.Collectors", "java.util.stream.Stream")),
      "a,b"),
    T("groupingBy", "Buckets by a key.",
      _java('        var g = Stream.of("ab", "ac", "b")\n'
            '            .collect(Collectors.groupingBy(\n                s -> s.charAt(0)));\n'
            '        System.out.println(g.get(\'a\'));',
            ("java.util.stream.Collectors", "java.util.stream.Stream")), "[ab, ac]"),
    T("max with a comparator", "An Optional, because the stream may be empty.",
      _java('        var m = Stream.of("aa", "b")\n'
            '            .max(Comparator.comparing(String::length));\n'
            '        System.out.println(m.get());', ("java.util.Comparator", "java.util.stream.Stream")),
      "aa"),
    T("Method references", "`Integer::sum` instead of a lambda.",
      _java('        int total = Stream.of(1, 2, 3)\n            .reduce(0, Integer::sum);\n'
            '        System.out.println(total);',
            ("java.util.stream.Stream",)), "6"),
    T("Function", "A function as a value.",
      _java('        Function<Integer, Integer> sq = n -> n * n;\n        System.out.println(sq.apply(4));',
            ("java.util.function.Function",)), "16"),
    T("Switch expressions", "A switch that is a value.",
      _java('        int n = 2;\n        String s = switch (n) {\n            case 1 -> "one";\n'
            '            default -> "other";\n        };\n        System.out.println(s);'), "other"),
    T("Pattern matching instanceof", "Test and cast in one.",
      _java('        Object o = "hi";\n        if (o instanceof String s)\n'
            '            System.out.println(s.length());'),
      "2"),
    T("var in lambdas", "Inferred, and the rest is Java as usual.",
      _java('        var total = 0;\n        for (var n : new int[]{1, 2}) total += n;\n'
            '        System.out.println(total);'), "3"),
    T("Ternary", "A condition that is a value.",
      _java('        int n = 5;\n        System.out.println(n > 3 ? "big" : "small");'), "big"),
    T("Integer caching", "`==` on boxed numbers is a trap; use equals.",
      _java('        Integer a = 1000, b = 1000;\n        System.out.println(a.equals(b));'), "true"),
    T("Math", "The static helpers.",
      _java('        System.out.println(Math.max(2, 9) + Math.abs(-1));'), "10"),
]


KOTLIN = [
    U("Collections in depth"),
    T("sortedBy", "Sorting by something derived.",
      'fun main() {\n    val words = listOf("ccc", "a", "bb")\n'
      '    println(words.sortedBy { it.length })\n}',
      "[a, bb, ccc]"),
    T("groupBy", "Buckets by a key.",
      'fun main() {\n    val words = listOf("ab", "ac", "b")\n'
      '    println(words.groupBy { it.first() })\n}',
      "{a=[ab, ac], b=[b]}"),
    T("associate", "A map from a list.",
      'fun main() {\n    println(listOf("a", "bb").associateWith { it.length })\n}',
      "{a=1, bb=2}"),
    T("partition", "Two lists: passed, and not.",
      'fun main() {\n    println((1..5).partition { it % 2 == 0 })\n}', "([2, 4], [1, 3, 5])"),
    T("zip", "Pairs from two lists.",
      'fun main() {\n    println(listOf(1, 2).zip(listOf("a", "b")))\n}', "[(1, a), (2, b)]"),
    T("chunked", "Fixed-size groups.",
      'fun main() {\n    println((1..5).toList().chunked(2))\n}', "[[1, 2], [3, 4], [5]]"),
    T("windowed", "Overlapping groups.",
      'fun main() {\n    println(listOf(1, 2, 3).windowed(2))\n}', "[[1, 2], [2, 3]]"),
    T("fold", "Carries a value through.",
      'fun main() {\n    println((1..4).fold(0) { acc, n -> acc + n })\n}', "10"),
    T("any, all, none", "Three questions about every item.",
      'fun main() {\n    val xs = listOf(1, 2)\n    println("${xs.any { it > 1 }} ${xs.none { it > 5 }}")\n}',
      "true true"),
    T("firstOrNull", "No exception when there is no match.",
      'fun main() {\n    println(listOf(1, 2).firstOrNull { it > 5 })\n}', "null"),
    T("sumOf", "Summing a derived value.",
      'fun main() {\n    println(listOf("a", "bb").sumOf { it.length })\n}', "3"),
    T("distinct", "Repeats removed, order kept.",
      'fun main() {\n    println(listOf(3, 1, 3).distinct())\n}', "[3, 1]"),
    T("Sequences", "Lazy, like a Python generator.",
      'fun main() {\n    val powers = generateSequence(1) { it * 2 }\n'
      '    println(powers.take(4).toList())\n}',
      "[1, 2, 4, 8]"),
    T("Ranges and steps", "`step` and `downTo`.",
      'fun main() {\n    println((10 downTo 1 step 3).toList())\n}', "[10, 7, 4, 1]"),
    T("Mutable maps", "`getOrPut` inserts when missing.",
      'fun main() {\n    val m = mutableMapOf<String, Int>()\n    m.getOrPut("a") { 5 }\n    println(m)\n}',
      "{a=5}"),

    U("The language in depth"),
    T("String functions", "`padStart`, `repeat`, `reversed`.",
      'fun main() {\n    println("7".padStart(3, \'0\'))\n}', "007"),
    T("Multiline strings", "Triple quotes, and `trimIndent`.",
      'fun main() {\n    val s = """\n        a\n        b\n    """.trimIndent()\n    println(s.lines().size)\n}',
      "2"),
    T("Default and named together", "Skip the middle argument by naming the last.",
      'fun f(a: Int = 1, b: Int = 2, c: Int = 3) = a + b + c\n\nfun main() {\n    println(f(c = 10))\n}',
      "13"),
    T("vararg", "Any number of arguments.",
      'fun total(vararg ns: Int) = ns.sum()\n\nfun main() {\n    println(total(1, 2, 3))\n}', "6"),
    T("Infix functions", "Called without the dot and the brackets.",
      'infix fun Int.times2(other: Int) = this * other * 2\n\nfun main() {\n    println(3 times2 4)\n}',
      "24"),
    T("Operator overloading", "`operator fun plus`.",
      'data class V(val x: Int) {\n    operator fun plus(o: V) = V(x + o.x)\n}\n\n'
      'fun main() {\n    println(V(1) + V(2))\n}', "V(x=3)"),
    T("Enum classes", "Values with properties.",
      'enum class Light(val go: Boolean) {\n    RED(false),\n    GREEN(true),\n}\n\n'
      'fun main() {\n    println(Light.GREEN.go)\n}', "true"),
    T("Companion objects", "The statics of a class.",
      'class C {\n    companion object {\n        fun make() = "made"\n    }\n}\n\n'
      'fun main() {\n    println(C.make())\n}', "made"),
    T("lateinit", "A non-null property set later.",
      'class Box {\n    lateinit var name: String\n}\n\nfun main() {\n    val b = Box()\n'
      '    b.name = "x"\n    println(b.name)\n}', "x"),
    T("lazy", "Computed the first time it is read.",
      'val answer by lazy { 6 * 7 }\n\nfun main() {\n    println(answer)\n}', "42"),
    T("also", "Does something on the side and returns the value.",
      'fun main() {\n    val n = 5.also { println("got $it") }\n    println(n)\n}', "got 5\n5"),
    T("run", "A block with a result.",
      'fun main() {\n    val n = run {\n        val a = 2\n        a * 3\n    }\n    println(n)\n}', "6"),
    T("require", "Checks an argument and throws when it is wrong.",
      'fun main() {\n    try {\n        require(1 > 2) { "nope" }\n    } catch (e: IllegalArgumentException) {\n'
      '        println(e.message)\n    }\n}', "nope"),
    T("Result", "Success or failure, as a value.",
      'fun main() {\n    val r = runCatching { "x".toInt() }\n    println(r.isFailure)\n}', "true"),
    T("Generics", "A function over any type.",
      'fun <T> firstOf(xs: List<T>): T = xs[0]\n\nfun main() {\n    println(firstOf(listOf("a")))\n}',
      "a"),
]


SWIFT = [
    U("More Swift"),
    T("String interpolation with expressions", "Anything inside `\\( )`.",
      'let a = 2\nprint("a + 1 = \\(a + 1)")', "a + 1 = 3"),
    T("count and isEmpty", "On strings and collections alike.",
      'print("pycmd".count, "".isEmpty)', "5 true"),
    T("uppercased", "Case conversion.", 'print("PyCmd".uppercased())', "PYCMD"),
    T("hasPrefix", "Asking about the front.", 'print("main.swift".hasSuffix(".swift"))', "true"),
    T("split", "Splitting on a character.", 'print("a,b".split(separator: ",").count)', "2"),
    T("joined", "Joining with a separator.", 'print(["a", "b"].joined(separator: "-"))', "a-b"),
    T("Int from a string", "An optional, because it may not parse.",
      'print(Int("41").map { $0 + 1 } ?? 0)', "42"),
    T("map, filter, reduce", "The usual pipeline.",
      'print([1, 2, 3].filter { $0 > 1 }.map { $0 * 2 })', "[4, 6]"),
    T("sorted(by:)", "Sorting with a closure.", 'print([1, 3, 2].sorted(by: >))', "[3, 2, 1]"),
    T("contains", "Asking about membership.", 'print([1, 2].contains(2))', "true"),
    T("Dictionary iteration", "Sort the keys for a stable order.",
      'let d = ["b": 2, "a": 1]\nfor k in d.keys.sorted() {\n    print(k, d[k]!)\n}', "a 1\nb 2"),
    T("Tuples", "Several values, with names if you like.",
      'let p = (x: 1, y: 2)\nprint(p.x + p.y)', "3"),
    T("switch on ranges", "Cases can be ranges.",
      'let n = 7\nswitch n {\ncase 0..<5:\n    print("low")\ndefault:\n    print("high")\n}', "high"),
    T("where in a for loop", "Filtering inline.",
      'for n in 1...6 where n % 3 == 0 {\n    print(n)\n}', "3\n6"),
    T("Computed properties", "A property that is a calculation.",
      'struct Sq {\n    var side: Int\n    var area: Int { side * side }\n}\nprint(Sq(side: 3).area)', "9"),
    T("mutating", "A struct method that changes the struct.",
      'struct C {\n    var n = 0\n    mutating func bump() { n += 1 }\n}\nvar c = C()\nc.bump()\nprint(c.n)',
      "1"),
    T("Extensions", "Adding to a type you do not own.",
      'extension Int {\n    var doubled: Int { self * 2 }\n}\nprint(4.doubled)', "8"),
    T("Protocol extensions", "A default implementation for every conformer.",
      'protocol Named { var name: String { get } }\nextension Named {\n'
      '    func greet() -> String { "hi " + name }\n}\nstruct Dog: Named { let name = "rex" }\n'
      'print(Dog().greet())', "hi rex"),
    T("Generics", "One function, any type.",
      'func first<T>(_ xs: [T]) -> T { xs[0] }\nprint(first(["a", "b"]))', "a"),
    T("defer", "Runs when the scope ends.",
      'func f() {\n    defer { print("done") }\n    print("working")\n}\nf()', "working\ndone"),
    T("Result", "Success or failure as a value.",
      'enum E: Error { case bad }\nlet r: Result<Int, E> = .success(3)\n'
      'if case .success(let n) = r { print(n) }', "3"),
    T("Closures capture", "A closure keeps the variables it uses.",
      'func counter() -> () -> Int {\n    var n = 0\n    return { n += 1; return n }\n}\n'
      'let c = counter()\n_ = c()\nprint(c())', "2"),
]

EXTRA = {
    "rust": RUST, "go": GO, "cpp": CPP, "java": JAVA, "kotlin": KOTLIN, "swift": SWIFT,
}
