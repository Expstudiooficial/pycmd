"""Courses for the compiled languages: Rust, Go, C++, Java, Kotlin, Swift.

Rust and Go run on the interpreters built into the app, so their snippets are
executed by `tools/test_teach.py` and their stated output is checked. The other
four cannot run on a phone - Android does not let an app execute code it
generated - so those courses are taught and marked by reading, and every lesson
in them says so rather than pretending otherwise.
"""

from . import Course, T, U

RUST = Course(
    "rust", "Rust", "Runs on a Rust interpreter in the app. No borrow checker.",
    ".rs", "run",
    [
        U("First steps", "A program, printing, and names."),
        T("A whole program", "`fn main` is where it starts. `println!` is a macro.",
          'fn main() {\n    println!("hello");\n}', "hello"),
        T("Holes in the string", "`{}` is filled by the next argument.",
          'fn main() {\n    println!("{}", 42);\n}', "42"),
        T("let", "A name. Immutable unless you say otherwise.",
          'fn main() {\n    let n = 5;\n    println!("{}", n);\n}', "5"),
        T("let mut", "`mut` is what makes it changeable.",
          'fn main() {\n    let mut n = 1;\n    n += 1;\n    println!("{}", n);\n}', "2"),
        T("Types", "Written after a colon, and usually inferred.",
          'fn main() {\n    let n: i32 = 7;\n    println!("{}", n);\n}', "7"),
        T("Several holes", "They are filled in order.",
          'fn main() {\n    println!("{} {}", "a", 1);\n}', "a 1"),
        T("Named holes", "A hole can name a variable directly.",
          'fn main() {\n    let n = 3;\n    println!("{n}");\n}', "3"),
        T("Comments", "`//` to the end of the line.",
          'fn main() {\n    // a note\n    println!("ok");\n}', "ok"),

        U("Numbers and text"),
        T("Arithmetic", "The usual four. Integer division truncates.",
          'fn main() {\n    println!("{}", 7 / 2);\n}', "3"),
        T("Remainder", "`%` is what is left over after an integer division.",
          'fn main() {\n    println!("{}", 7 % 2);\n}', "1"),
        T("Floats", "Dividing floats keeps the fraction.",
          'fn main() {\n    println!("{}", 7.0 / 2.0);\n}', "3.5"),
        T("Casting", "`as` converts between number types.",
          'fn main() {\n    println!("{}", 7 as f64 / 2.0);\n}', "3.5"),
        T("Booleans", "`true` and `false`, and the usual operators.",
          'fn main() {\n    println!("{}", 1 < 2 && !false);\n}', "true"),
        T("A String", "Growable, owned text.",
          'fn main() {\n    let mut s = String::from("py");\n    s.push_str("cmd");\n'
          '    println!("{}", s);\n}', "pycmd"),
        T("Length", "`len` counts bytes, which is the honest answer.",
          'fn main() {\n    println!("{}", "pycmd".len());\n}', "5"),
        T("Case", "`to_uppercase` returns a new String.",
          'fn main() {\n    println!("{}", "PyCmd".to_uppercase());\n}', "PYCMD"),
        T("Contains", "On a &str, like everywhere else.",
          'fn main() {\n    println!("{}", "pycmd".contains("cm"));\n}', "true"),
        T("Splitting", "`split` gives an iterator; collect it to keep it.",
          'fn main() {\n    let parts: Vec<&str> = "a,b".split(\',\').collect();\n'
          '    println!("{}", parts.len());\n}', "2"),
        T("Parsing", "`parse` needs to know what to parse into.",
          'fn main() {\n    let n: i32 = "41".parse().unwrap();\n    println!("{}", n + 1);\n}',
          "42"),
        T("Trimming", "`trim` gives back a slice of the same text.",
          'fn main() {\n    println!("{}", "  hi  ".trim());\n}', "hi"),
        T("Replacing", "Every occurrence, into a new String.",
          'fn main() {\n    println!("{}", "aaa".replace("a", "b"));\n}', "bbb"),

        U("Decisions and loops"),
        T("if", "No brackets round the condition; braces are required.",
          'fn main() {\n    let n = 5;\n    if n > 3 {\n        println!("big");\n    }\n}', "big"),
        T("if is an expression", "It has a value, so it can be assigned.",
          'fn main() {\n    let n = if true { 1 } else { 2 };\n    println!("{}", n);\n}', "1"),
        T("loop", "Forever, until something breaks out.",
          'fn main() {\n    let mut n = 0;\n    loop {\n        n += 1;\n'
          '        if n == 2 { break; }\n    }\n    println!("{}", n);\n}', "2"),
        T("while", "The ordinary one.",
          'fn main() {\n    let mut n = 2;\n    while n > 0 {\n        println!("{}", n);\n'
          '        n -= 1;\n    }\n}', "2\n1"),
        T("for over a range", "`..` excludes the end, `..=` includes it.",
          'fn main() {\n    for i in 0..3 {\n        println!("{}", i);\n    }\n}', "0\n1\n2"),
        T("for over a collection", "`&` borrows it rather than consuming it.",
          'fn main() {\n    for n in &[1, 2] {\n        println!("{}", n);\n    }\n}', "1\n2"),
        T("match", "Every case must be covered. `_` is the rest.",
          'fn main() {\n    let n = 2;\n    match n {\n        1 => println!("one"),\n'
          '        _ => println!("other"),\n    }\n}', "other"),
        T("match on a range", "Patterns can be ranges.",
          'fn main() {\n    let n = 7;\n    match n {\n        0..=5 => println!("low"),\n'
          '        _ => println!("high"),\n    }\n}', "high"),

        U("Functions"),
        T("fn", "Parameter types are required; the return type follows an arrow.",
          'fn add(a: i32, b: i32) -> i32 {\n    a + b\n}\n\nfn main() {\n'
          '    println!("{}", add(1, 2));\n}', "3"),
        T("The last expression", "No semicolon means that is what is returned.",
          'fn double(n: i32) -> i32 {\n    n * 2\n}\n\nfn main() {\n'
          '    println!("{}", double(4));\n}', "8"),
        T("return", "Still there, for returning early.",
          'fn first() -> i32 {\n    return 1;\n}\n\nfn main() {\n    println!("{}", first());\n}',
          "1"),
        T("A closure", "`|args|`, and it captures the names around it.",
          'fn main() {\n    let add = |a: i32, b: i32| a + b;\n    println!("{}", add(1, 2));\n}',
          "3"),
        T("Closures capture", "The surrounding variables come along.",
          'fn main() {\n    let n = 10;\n    let plus = |x: i32| x + n;\n'
          '    println!("{}", plus(5));\n}', "15"),

        U("Collections"),
        T("A Vec", "A growable array.",
          'fn main() {\n    let mut v = Vec::new();\n    v.push(1);\n'
          '    println!("{}", v.len());\n}', "1"),
        T("vec!", "The macro that builds one from a list.",
          'fn main() {\n    let v = vec![1, 2, 3];\n    println!("{}", v[1]);\n}', "2"),
        T("Iterating", "`iter`, then whatever you want to do with it.",
          'fn main() {\n    let v = vec![1, 2, 3];\n    let total: i32 = v.iter().sum();\n'
          '    println!("{}", total);\n}', "6"),
        T("map", "A new iterator, one item per item. `collect` makes it a Vec.",
          'fn main() {\n    let v = vec![1, 2];\n'
          '    let d: Vec<i32> = v.iter().map(|n| n * 2).collect();\n'
          '    println!("{:?}", d);\n}', "[2, 4]"),
        T("filter", "Keeps the ones whose closure returns true.",
          'fn main() {\n    let odd: Vec<i32> =\n'
          '        (1..5).filter(|n| n % 2 == 1).collect();\n'
          '    println!("{:?}", odd);\n}', "[1, 3]"),
        T("Debug printing", "`{:?}` prints the structure of a thing.",
          'fn main() {\n    println!("{:?}", vec![1, 2]);\n}', "[1, 2]"),
        T("A HashMap", "Keys to values, from the standard library.",
          'use std::collections::HashMap;\n\nfn main() {\n    let mut m = HashMap::new();\n'
          '    m.insert("a", 1);\n    println!("{}", m["a"]);\n}', "1"),
        T("get on a map", "Gives an Option rather than panicking.",
          'use std::collections::HashMap;\n\nfn main() {\n'
          '    let m: HashMap<&str, i32> = HashMap::new();\n'
          '    println!("{}", m.get("x").is_none());\n}', "true"),
        T("A HashSet", "No duplicates.",
          'use std::collections::HashSet;\n\nfn main() {\n    let mut s = HashSet::new();\n'
          '    s.insert(1);\n    s.insert(1);\n    println!("{}", s.len());\n}', "1"),
        T("Sorting", "In place, on a mutable Vec.",
          'fn main() {\n    let mut v = vec![3, 1, 2];\n    v.sort();\n    println!("{:?}", v);\n}',
          "[1, 2, 3]"),

        U("Structs, enums and traits"),
        T("A struct", "Named fields.",
          'struct Point {\n    x: i32,\n}\n\nfn main() {\n    let p = Point { x: 3 };\n'
          '    println!("{}", p.x);\n}', "3"),
        T("impl", "Methods live in an impl block, not in the struct.",
          'struct Point {\n    x: i32,\n}\n\nimpl Point {\n    fn double(&self) -> i32 {\n'
          '        self.x * 2\n    }\n}\n\nfn main() {\n    let p = Point { x: 2 };\n'
          '    println!("{}", p.double());\n}', "4"),
        T("An associated function", "No `self`; the usual name is `new`.",
          'struct Point {\n    x: i32,\n}\n\nimpl Point {\n    fn new() -> Point {\n'
          '        Point { x: 9 }\n    }\n}\n\nfn main() {\n    println!("{}", Point::new().x);\n}',
          "9"),
        T("An enum", "A value that is one of several shapes.",
          'enum Light {\n    Red,\n    Green,\n}\n\nfn main() {\n    let l = Light::Green;\n'
          '    match l {\n        Light::Red => println!("stop"),\n'
          '        Light::Green => println!("go"),\n    }\n}', "go"),
        T("An enum with a payload", "Each variant can carry data.",
          'enum Shape {\n    Circle(f64),\n}\n\nfn main() {\n    let s = Shape::Circle(2.0);\n'
          '    match s {\n        Shape::Circle(r) => println!("{}", r),\n    }\n}', "2"),
        T("A trait", "A set of methods a type promises to have.",
          'trait Speak {\n    fn speak(&self) -> String;\n}\n\nstruct Dog;\n\n'
          'impl Speak for Dog {\n    fn speak(&self) -> String {\n'
          '        String::from("woof")\n    }\n}\n\nfn main() {\n'
          '    println!("{}", Dog.speak());\n}', "woof"),

        U("Option, Result and errors"),
        T("Option", "`Some` or `None`. Rust has no null.",
          'fn main() {\n    let n: Option<i32> = Some(3);\n'
          '    println!("{}", n.unwrap());\n}', "3"),
        T("Matching an Option", "The safe way to open one.",
          'fn main() {\n    let n: Option<i32> = None;\n    match n {\n'
          '        Some(v) => println!("{}", v),\n        None => println!("nothing"),\n    }\n}',
          "nothing"),
        T("unwrap_or", "A default instead of a panic.",
          'fn main() {\n    let n: Option<i32> = None;\n    println!("{}", n.unwrap_or(0));\n}',
          "0"),
        T("Result", "`Ok` or `Err`. This is how Rust reports failure.",
          'fn half(n: i32) -> Result<i32, String> {\n    if n % 2 == 0 {\n'
          '        Ok(n / 2)\n    } else {\n        Err(String::from("odd"))\n    }\n}\n\n'
          'fn main() {\n    println!("{:?}", half(4));\n}', "Ok(2)"),
        T("Matching a Result", "Both halves, handled.",
          'fn main() {\n    let r: Result<i32, String> = Err(String::from("no"));\n'
          '    match r {\n        Ok(v) => println!("{}", v),\n        Err(e) => println!("{}", e),\n'
          '    }\n}', "no"),
        T("is_ok", "The quick question.",
          'fn main() {\n    let r: Result<i32, String> = Ok(1);\n    println!("{}", r.is_ok());\n}',
          "true"),

        U("Ownership", "The idea the rest of Rust is arranged around."),
        T("Moving", "Assigning an owned value hands it over. The old name is done.",
          'fn main() {\n    let a = String::from("hi");\n    let b = a;\n    println!("{}", b);\n}',
          "hi"),
        T("Borrowing", "`&` lends it; the owner keeps it.",
          'fn length(s: &String) -> usize {\n    s.len()\n}\n\nfn main() {\n'
          '    let s = String::from("abc");\n    println!("{}", length(&s));\n}', "3"),
        T("Borrowing mutably", "`&mut` lends it and lets the borrower change it.",
          'fn bump(n: &mut i32) {\n    *n += 1;\n}\n\nfn main() {\n    let mut n = 1;\n'
          '    bump(&mut n);\n    println!("{}", n);\n}', "2"),
        T("Copy types", "Numbers are copied, not moved, so both names stay usable.",
          'fn main() {\n    let a = 5;\n    let b = a;\n    println!("{} {}", a, b);\n}', "5 5"),
        T("clone", "An explicit copy of something that would otherwise move.",
          'fn main() {\n    let a = String::from("x");\n    let b = a.clone();\n'
          '    println!("{}{}", a, b);\n}', "xx",
          "The app's interpreter does not run a borrow checker, so a program that "
          "moves a value and then uses it will run here and be rejected by rustc. "
          "Write it as rustc would accept it."),
    ],
)


GO = Course(
    "go", "Go", "Runs on a Go interpreter in the app: goroutines, channels and all.",
    ".go", "run",
    [
        U("First steps"),
        T("A whole program", "A package, an import, and `main`.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("hello")\n}', "hello"),
        T("Println", "Adds spaces between arguments and a newline at the end.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("a", 1)\n}', "a 1"),
        T("Printf", "Format codes, and no newline unless you write one.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Printf("%d\\n", 42)\n}', "42"),
        T("var", "A name with a type.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tvar n int = 5\n\tfmt.Println(n)\n}',
          "5"),
        T("Short declaration", "`:=` declares and infers inside a function.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tn := 5\n\tfmt.Println(n)\n}', "5"),
        T("Zero values", "An uninitialised variable is zero, not undefined.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tvar n int\n\tfmt.Println(n)\n}', "0"),
        T("Constants", "`const`, worked out at compile time.",
          'package main\n\nimport "fmt"\n\nconst size = 3\n\nfunc main() {\n\tfmt.Println(size)\n}',
          "3"),

        U("Numbers and text"),
        T("Integer division", "Truncates, like C.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println(7 / 2)\n}', "3"),
        T("Remainder", "`%` is what is left over after an integer division.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println(7 % 2)\n}', "1"),
        T("Floats need floats", "Go will not mix types for you.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println(7.0 / 2.0)\n}', "3.5"),
        T("Converting", "`float64(n)`, explicitly.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tn := 7\n'
          '\tfmt.Println(float64(n) / 2)\n}', "3.5"),
        T("Joining strings", "`+`, or strings.Builder when it is in a loop.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("py" + "cmd")\n}',
          "pycmd"),
        T("Length", "`len` on a string counts bytes.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println(len("pycmd"))\n}', "5"),
        T("strings.ToUpper", "The strings package holds the text functions.",
          'package main\n\nimport (\n\t"fmt"\n\t"strings"\n)\n\nfunc main() {\n'
          '\tfmt.Println(strings.ToUpper("pycmd"))\n}', "PYCMD"),
        T("strings.Contains", "Asking whether one is inside the other.",
          'package main\n\nimport (\n\t"fmt"\n\t"strings"\n)\n\nfunc main() {\n'
          '\tfmt.Println(strings.Contains("pycmd", "cm"))\n}', "true"),
        T("strings.Split", "Gives a slice.",
          'package main\n\nimport (\n\t"fmt"\n\t"strings"\n)\n\nfunc main() {\n'
          '\tfmt.Println(len(strings.Split("a,b", ",")))\n}', "2"),
        T("strings.Join", "Split, backwards.",
          'package main\n\nimport (\n\t"fmt"\n\t"strings"\n)\n\nfunc main() {\n'
          '\tfmt.Println(strings.Join([]string{"a", "b"}, "-"))\n}', "a-b"),
        T("strconv.Atoi", "Text to number, with an error alongside.",
          'package main\n\nimport (\n\t"fmt"\n\t"strconv"\n)\n\nfunc main() {\n'
          '\tn, _ := strconv.Atoi("41")\n\tfmt.Println(n + 1)\n}', "42"),
        T("strconv.Itoa", "And back the other way.",
          'package main\n\nimport (\n\t"fmt"\n\t"strconv"\n)\n\nfunc main() {\n'
          '\tfmt.Println("n=" + strconv.Itoa(7))\n}', "n=7"),

        U("Decisions and loops"),
        T("if", "No brackets, braces required, and the brace goes on this line.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tn := 5\n\tif n > 3 {\n'
          '\t\tfmt.Println("big")\n\t}\n}', "big"),
        T("if with a statement", "A variable can be declared in the `if`.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tif n := 5; n > 3 {\n'
          '\t\tfmt.Println(n)\n\t}\n}', "5"),
        T("for", "Go's only loop keyword. This is the three-part form.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tfor i := 0; i < 3; i++ {\n'
          '\t\tfmt.Println(i)\n\t}\n}', "0\n1\n2"),
        T("for as while", "One condition and nothing else.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tn := 2\n\tfor n > 0 {\n'
          '\t\tfmt.Println(n)\n\t\tn--\n\t}\n}', "2\n1"),
        T("for range", "Index and value, over a slice or a string.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tfor i, v := range []int{7, 8} {\n'
          '\t\tfmt.Println(i, v)\n\t}\n}', "0 7\n1 8"),
        T("Ignoring the index", "`_` is the name for something you do not want.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tfor _, v := range []int{7} {\n'
          '\t\tfmt.Println(v)\n\t}\n}', "7"),
        T("switch", "No fall-through, so no `break` needed.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tswitch 2 {\n\tcase 1:\n'
          '\t\tfmt.Println("one")\n\tdefault:\n\t\tfmt.Println("other")\n\t}\n}', "other"),

        U("Functions"),
        T("func", "Types after the names, return type at the end.",
          'package main\n\nimport "fmt"\n\nfunc add(a int, b int) int {\n\treturn a + b\n}\n\n'
          'func main() {\n\tfmt.Println(add(1, 2))\n}', "3"),
        T("Two return values", "Go's answer to exceptions, and its habit.",
          'package main\n\nimport "fmt"\n\nfunc half(n int) (int, bool) {\n'
          '\treturn n / 2, n % 2 == 0\n}\n\nfunc main() {\n\tv, ok := half(4)\n'
          '\tfmt.Println(v, ok)\n}', "2 true"),
        T("Named results", "The names are declared for you, and zero to start.",
          'package main\n\nimport "fmt"\n\nfunc split(n int) (a int, b int) {\n\ta = n / 2\n'
          '\tb = n - a\n\treturn\n}\n\nfunc main() {\n\tfmt.Println(split(5))\n}', "2 3"),
        T("Variadic", "`...int` collects the rest into a slice.",
          'package main\n\nimport "fmt"\n\nfunc total(ns ...int) int {\n\tsum := 0\n'
          '\tfor _, n := range ns {\n\t\tsum += n\n\t}\n\treturn sum\n}\n\nfunc main() {\n'
          '\tfmt.Println(total(1, 2, 3))\n}', "6"),
        T("A function value", "Functions are values and can be anonymous.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tdouble := func(n int) int {\n'
          '\t\treturn n * 2\n\t}\n\tfmt.Println(double(4))\n}', "8"),
        T("defer", "Runs when the function returns, whatever happens.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tdefer fmt.Println("second")\n'
          '\tfmt.Println("first")\n}', "first\nsecond"),

        U("Slices, maps and structs"),
        T("A slice", "Go's growable list.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\ts := []int{1, 2}\n'
          '\tfmt.Println(s[1])\n}', "2"),
        T("append", "Returns the new slice; assign it back.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\ts := []int{1}\n'
          '\ts = append(s, 2)\n\tfmt.Println(len(s))\n}', "2"),
        T("make", "A slice with a length ready to be written into.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\ts := make([]int, 2)\n'
          '\ts[0] = 9\n\tfmt.Println(s[0])\n}', "9"),
        T("Slicing a slice", "`[a:b]`, and it shares the same memory.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\ts := []int{1, 2, 3}\n'
          '\tfmt.Println(s[1:])\n}', "[2 3]"),
        T("A map", "Made with `make` or a literal.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tm := map[string]int{"a": 1}\n'
          '\tfmt.Println(m["a"])\n}', "1"),
        T("Is the key there", "The two-value form of a map read.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tm := map[string]int{}\n'
          '\t_, ok := m["x"]\n\tfmt.Println(ok)\n}', "false"),
        T("Deleting a key", "`delete`, a built-in.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tm := map[string]int{"a": 1}\n'
          '\tdelete(m, "a")\n\tfmt.Println(len(m))\n}', "0"),
        T("A struct", "Fields with types.",
          'package main\n\nimport "fmt"\n\ntype Point struct {\n\tX int\n}\n\nfunc main() {\n'
          '\tp := Point{X: 3}\n\tfmt.Println(p.X)\n}', "3"),
        T("A method", "A function with a receiver in front of its name.",
          'package main\n\nimport "fmt"\n\ntype Point struct {\n\tX int\n}\n\n'
          'func (p Point) Double() int {\n\treturn p.X * 2\n}\n\nfunc main() {\n'
          '\tfmt.Println(Point{X: 2}.Double())\n}', "4"),
        T("A pointer receiver", "Needed to change the struct.",
          'package main\n\nimport "fmt"\n\ntype Counter struct {\n\tN int\n}\n\n'
          'func (c *Counter) Bump() {\n\tc.N++\n}\n\nfunc main() {\n\tc := Counter{}\n'
          '\tc.Bump()\n\tfmt.Println(c.N)\n}', "1"),
        T("An interface", "A set of methods. Types satisfy it without saying so.",
          'package main\n\nimport "fmt"\n\ntype Speaker interface {\n\tSpeak() string\n}\n\n'
          'type Dog struct{}\n\nfunc (d Dog) Speak() string {\n\treturn "woof"\n}\n\n'
          'func main() {\n\tvar s Speaker = Dog{}\n\tfmt.Println(s.Speak())\n}', "woof"),
        T("Sorting", "The sort package, on a slice.",
          'package main\n\nimport (\n\t"fmt"\n\t"sort"\n)\n\nfunc main() {\n'
          '\ts := []int{3, 1, 2}\n\tsort.Ints(s)\n\tfmt.Println(s)\n}', "[1 2 3]"),

        U("Errors and concurrency"),
        T("An error", "A value, returned alongside the result.",
          'package main\n\nimport (\n\t"errors"\n\t"fmt"\n)\n\n'
          'func fail() error {\n\treturn errors.New("no")\n}\n\nfunc main() {\n'
          '\tfmt.Println(fail())\n}', "no"),
        T("Checking an error", "The three lines every Go program is full of.",
          'package main\n\nimport (\n\t"errors"\n\t"fmt"\n)\n\n'
          'func work() (int, error) {\n\treturn 0, errors.New("broken")\n}\n\n'
          'func main() {\n\tn, err := work()\n\tif err != nil {\n\t\tfmt.Println("failed")\n'
          '\t\treturn\n\t}\n\tfmt.Println(n)\n}', "failed"),
        T("panic and recover", "For the things that should not happen.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tdefer func() {\n'
          '\t\tif r := recover(); r != nil {\n\t\t\tfmt.Println("caught")\n\t\t}\n\t}()\n'
          '\tpanic("boom")\n}', "caught"),
        T("A goroutine and a channel", "Start it with `go`, and wait on a channel.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tdone := make(chan int)\n'
          '\tgo func() {\n\t\tdone <- 7\n\t}()\n\tfmt.Println(<-done)\n}', "7"),
        T("A buffered channel", "Holds a few without anybody waiting.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tc := make(chan int, 2)\n'
          '\tc <- 1\n\tc <- 2\n\tfmt.Println(<-c, <-c)\n}', "1 2"),
        T("Closing and ranging", "A closed channel ends a `range`.",
          'package main\n\nimport "fmt"\n\nfunc main() {\n\tc := make(chan int, 2)\n'
          '\tc <- 1\n\tc <- 2\n\tclose(c)\n\tfor n := range c {\n\t\tfmt.Println(n)\n\t}\n}',
          "1\n2"),
        T("A WaitGroup", "Waiting for several goroutines without a channel each.",
          'package main\n\nimport (\n\t"fmt"\n\t"sync"\n)\n\nfunc main() {\n'
          '\tvar wg sync.WaitGroup\n\twg.Add(1)\n\tgo func() {\n\t\tdefer wg.Done()\n'
          '\t\tfmt.Println("worked")\n\t}()\n\twg.Wait()\n}', "worked"),
    ],
)


CPP = Course(
    "cpp", "C++", "Edited and highlighted here. Building it needs a compiler.",
    ".cpp", "text",
    [
        U("First steps"),
        T("A whole program", "`iostream` for the streams, `std::cout` to print.",
          '#include <iostream>\n\nint main() {\n    std::cout << "hello\\n";\n    return 0;\n}',
          "hello"),
        T("Several things", "`<<` chains.",
          '#include <iostream>\n\nint main() {\n    std::cout << "n=" << 5 << "\\n";\n'
          '    return 0;\n}', "n=5"),
        T("using namespace", "Saves typing `std::`, and is frowned on in headers.",
          '#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << "hi\\n";\n'
          '    return 0;\n}', "hi"),
        T("auto", "The compiler works out the type.",
          '#include <iostream>\n\nint main() {\n    auto n = 5;\n    std::cout << n << "\\n";\n'
          '    return 0;\n}', "5"),
        T("Comments", "The same two forms as C: to the end of the line, or a block.",
          '#include <iostream>\n\nint main() {\n    // a note\n    std::cout << "ok\\n";\n'
          '    return 0;\n}', "ok"),

        U("Text and containers"),
        T("std::string", "Growable text, with methods.",
          '#include <iostream>\n#include <string>\n\nint main() {\n'
          '    std::string s = "py";\n    s += "cmd";\n    std::cout << s << "\\n";\n'
          '    return 0;\n}', "pycmd"),
        T("Length and substr", "`size()` and `substr(start, count)`.",
          '#include <iostream>\n#include <string>\n\nint main() {\n'
          '    std::string s = "pycmd";\n    std::cout << s.substr(0, 2) << "\\n";\n'
          '    return 0;\n}', "py"),
        T("std::vector", "The container to reach for first.",
          '#include <iostream>\n#include <vector>\n\nint main() {\n'
          '    std::vector<int> v{1, 2};\n    v.push_back(3);\n'
          '    std::cout << v.size() << "\\n";\n    return 0;\n}', "3"),
        T("Range-based for", "Since C++11, and much nicer than an index.",
          '#include <iostream>\n#include <vector>\n\nint main() {\n'
          '    std::vector<int> v{1, 2};\n'
          '    for (int n : v) std::cout << n << "\\n";\n    return 0;\n}',
          "1\n2"),
        T("std::map", "Sorted keys to values.",
          '#include <iostream>\n#include <map>\n\nint main() {\n'
          '    std::map<std::string, int> m;\n    m["a"] = 1;\n'
          '    std::cout << m["a"] << "\\n";\n    return 0;\n}', "1"),
        T("Sorting", "`<algorithm>`, on a pair of iterators.",
          '#include <algorithm>\n#include <iostream>\n#include <vector>\n\nint main() {\n'
          '    std::vector<int> v{3, 1, 2};\n    std::sort(v.begin(), v.end());\n'
          '    std::cout << v[0] << "\\n";\n    return 0;\n}', "1"),

        U("Classes"),
        T("A class", "Members are private by default.",
          '#include <iostream>\n\nclass Dog {\npublic:\n    void speak() {\n'
          '        std::cout << "woof\\n";\n    }\n};\n\nint main() {\n    Dog().speak();\n'
          '    return 0;\n}', "woof"),
        T("A constructor", "Same name as the class, no return type.",
          '#include <iostream>\n\nclass Box {\npublic:\n    int size;\n'
          '    Box(int s) : size(s) {}\n};\n\nint main() {\n'
          '    std::cout << Box(4).size << "\\n";\n    return 0;\n}', "4"),
        T("Inheritance", "`public` inheritance is the usual kind.",
          '#include <iostream>\n\nclass A {\npublic:\n    virtual int n() { return 1; }\n};\n\n'
          'class B : public A {\npublic:\n    int n() override { return 2; }\n};\n\n'
          'int main() {\n    std::cout << B().n() << "\\n";\n    return 0;\n}', "2"),
        T("A destructor", "Runs when the object goes out of scope. This is RAII.",
          '#include <iostream>\n\nclass Guard {\npublic:\n    ~Guard() {\n'
          '        std::cout << "gone\\n";\n    }\n};\n\nint main() {\n    Guard g;\n'
          '    return 0;\n}', "gone"),
        T("A template", "One definition, any type.",
          '#include <iostream>\n\ntemplate <typename T>\nT twice(T v) {\n    return v + v;\n}\n\n'
          'int main() {\n    std::cout << twice(3) << "\\n";\n    return 0;\n}', "6"),

        U("Modern C++"),
        T("A lambda", "`[]` captures, `()` takes arguments.",
          '#include <iostream>\n\nint main() {\n    auto add = [](int a, int b) { return a + b; };\n'
          '    std::cout << add(1, 2) << "\\n";\n    return 0;\n}', "3"),
        T("Capturing", "`[&]` by reference, `[=]` by value.",
          '#include <iostream>\n\nint main() {\n    int n = 10;\n'
          '    auto plus = [&](int x) { return x + n; };\n    std::cout << plus(5) << "\\n";\n'
          '    return 0;\n}', "15"),
        T("unique_ptr", "Owns one thing and frees it. No `delete` to forget.",
          '#include <iostream>\n#include <memory>\n\nint main() {\n'
          '    auto p = std::make_unique<int>(9);\n    std::cout << *p << "\\n";\n'
          '    return 0;\n}', "9"),
        T("References", "An alias for something else; it cannot be null.",
          '#include <iostream>\n\nvoid bump(int &n) { n++; }\n\nint main() {\n    int n = 1;\n'
          '    bump(n);\n    std::cout << n << "\\n";\n    return 0;\n}', "2"),
        T("Exceptions", "`throw`, `try`, `catch`.",
          '#include <iostream>\n#include <stdexcept>\n\nint main() {\n    try {\n'
          '        throw std::runtime_error("no");\n    } catch (const std::exception &e) {\n'
          '        std::cout << e.what() << "\\n";\n    }\n    return 0;\n}', "no"),
    ],
)


JAVA = Course(
    "java", "Java", "Edited and highlighted here. Running it needs a JDK.",
    ".java", "text",
    [
        U("First steps"),
        T("A whole program", "Everything lives in a class; `main` is static.",
          'public class Main {\n    public static void main(String[] args) {\n'
          '        System.out.println("hello");\n    }\n}', "hello"),
        T("Variables", "A type, then a name.",
          'public class Main {\n    public static void main(String[] args) {\n'
          '        int n = 5;\n        System.out.println(n);\n    }\n}', "5"),
        T("var", "Since Java 10, inside a method.",
          'public class Main {\n    public static void main(String[] args) {\n'
          '        var n = 5;\n        System.out.println(n);\n    }\n}', "5"),
        T("printf", "Format codes, as in C.",
          'public class Main {\n    public static void main(String[] args) {\n'
          '        System.out.printf("%d%n", 42);\n    }\n}', "42"),
        T("Comments", "`//`, `/* */`, and `/** */` for documentation.",
          'public class Main {\n    public static void main(String[] args) {\n'
          '        // a note\n        System.out.println("ok");\n    }\n}', "ok"),

        U("Text and arrays"),
        T("A String", "Immutable. Every method returns a new one.",
          'public class Main {\n    public static void main(String[] args) {\n'
          '        System.out.println("py" + "cmd");\n    }\n}', "pycmd"),
        T("length and substring", "A method on String, unlike an array.",
          'public class Main {\n    public static void main(String[] args) {\n'
          '        System.out.println("pycmd".substring(0, 2));\n    }\n}', "py"),
        T("equals, not ==", "`==` compares references. This catches everybody once.",
          'public class Main {\n    public static void main(String[] args) {\n'
          '        System.out.println("a".equals("a"));\n    }\n}', "true"),
        T("An array", "A fixed length, known at run time.",
          'public class Main {\n    public static void main(String[] args) {\n'
          '        int[] a = {1, 2};\n        System.out.println(a[1]);\n    }\n}', "2"),
        T("An ArrayList", "The growable one, from java.util.",
          'import java.util.ArrayList;\n\npublic class Main {\n'
          '    public static void main(String[] args) {\n'
          '        var list = new ArrayList<Integer>();\n        list.add(7);\n'
          '        System.out.println(list.get(0));\n    }\n}', "7"),
        T("A HashMap", "Keys to values.",
          'import java.util.HashMap;\n\npublic class Main {\n'
          '    public static void main(String[] args) {\n'
          '        var m = new HashMap<String, Integer>();\n        m.put("a", 1);\n'
          '        System.out.println(m.get("a"));\n    }\n}', "1"),

        U("Decisions, loops and methods"),
        T("if and else", "Brackets round the condition.",
          'public class Main {\n    public static void main(String[] args) {\n'
          '        int n = 5;\n        if (n > 3) {\n            System.out.println("big");\n'
          '        }\n    }\n}', "big"),
        T("for", "The three-part loop.",
          'public class Main {\n    public static void main(String[] args) {\n'
          '        for (int i = 0; i < 3; i++) {\n            System.out.println(i);\n'
          '        }\n    }\n}', "0\n1\n2"),
        T("for each", "A colon, over anything iterable.",
          'public class Main {\n    public static void main(String[] args) {\n'
          '        for (int n : new int[]{1, 2}) {\n            System.out.println(n);\n'
          '        }\n    }\n}', "1\n2"),
        T("A method", "Return type, name, parameters.",
          'public class Main {\n    static int add(int a, int b) {\n        return a + b;\n    }\n\n'
          '    public static void main(String[] args) {\n'
          '        System.out.println(add(1, 2));\n    }\n}', "3"),
        T("Overloading", "Same name, different parameters.",
          'public class Main {\n    static int f(int n) { return n; }\n'
          '    static String f(String s) { return s; }\n\n'
          '    public static void main(String[] args) {\n        System.out.println(f("x"));\n'
          '    }\n}', "x"),

        U("Classes"),
        T("A class with a field", "And a constructor.",
          'public class Main {\n    static class Dog {\n        String name;\n'
          '        Dog(String n) { name = n; }\n    }\n\n'
          '    public static void main(String[] args) {\n'
          '        System.out.println(new Dog("rex").name);\n    }\n}', "rex"),
        T("Inheritance", "`extends`, and `@Override` to be explicit.",
          'public class Main {\n    static class A {\n        int n() { return 1; }\n    }\n'
          '    static class B extends A {\n        @Override int n() { return 2; }\n    }\n\n'
          '    public static void main(String[] args) {\n'
          '        System.out.println(new B().n());\n    }\n}', "2"),
        T("An interface", "A promise about methods. `implements` keeps it.",
          'public class Main {\n    interface Speaker {\n        String speak();\n    }\n'
          '    static class Dog implements Speaker {\n'
          '        public String speak() { return "woof"; }\n    }\n\n'
          '    public static void main(String[] args) {\n'
          '        System.out.println(new Dog().speak());\n    }\n}', "woof"),
        T("A record", "Since Java 16: a class that is only its fields.",
          'public class Main {\n    record Point(int x, int y) {}\n\n'
          '    public static void main(String[] args) {\n'
          '        System.out.println(new Point(1, 2).x());\n    }\n}', "1"),
        T("An enum", "A fixed set of values, and they are objects.",
          'public class Main {\n    enum Light { RED, GREEN }\n\n'
          '    public static void main(String[] args) {\n'
          '        System.out.println(Light.GREEN);\n    }\n}', "GREEN"),

        U("Modern Java"),
        T("A lambda", "`->`, for an interface with one method.",
          'import java.util.function.IntBinaryOperator;\n\npublic class Main {\n'
          '    public static void main(String[] args) {\n'
          '        IntBinaryOperator add = (a, b) -> a + b;\n'
          '        System.out.println(add.applyAsInt(1, 2));\n    }\n}', "3"),
        T("Streams", "A pipeline over a collection: map, filter, then collect or sum.",
          'import java.util.List;\n\npublic class Main {\n'
          '    public static void main(String[] args) {\n'
          '        var ns = List.of(1, 2, 3);\n'
          '        System.out.println(\n'
          '            ns.stream().mapToInt(n -> n).sum());\n'
          '    }\n}', "6"),
        T("Optional", "A value that might not be there, without null.",
          'import java.util.Optional;\n\npublic class Main {\n'
          '    public static void main(String[] args) {\n'
          '        var v = Optional.empty();\n'
          '        System.out.println(v.orElse("none"));\n    }\n}', "none"),
        T("try with resources", "Closes what it opened, even on an exception.",
          'import java.io.StringReader;\n\npublic class Main {\n'
          '    public static void main(String[] a) throws Exception {\n'
          '        try (var s = new StringReader("x")) {\n'
          '            System.out.println((char) s.read());\n        }\n    }\n}', "x"),
        T("Exceptions", "Checked ones must be declared or caught.",
          'public class Main {\n    public static void main(String[] args) {\n'
          '        try {\n            throw new IllegalStateException("no");\n'
          '        } catch (RuntimeException e) {\n'
          '            System.out.println(e.getMessage());\n        }\n    }\n}', "no"),
    ],
)


KOTLIN = Course(
    "kotlin", "Kotlin", "Edited and highlighted here. The app itself is written in it.",
    ".kt", "text",
    [
        U("First steps"),
        T("A whole program", "`fun main`, and no class needed.",
          'fun main() {\n    println("hello")\n}', "hello"),
        T("val and var", "`val` cannot be reassigned; `var` can.",
          'fun main() {\n    val n = 5\n    println(n)\n}', "5"),
        T("Types", "After a colon, and usually inferred.",
          'fun main() {\n    val n: Int = 7\n    println(n)\n}', "7"),
        T("String templates", "`$name`, or `${expression}`.",
          'fun main() {\n    val n = 4\n    println("n is $n")\n}', "n is 4"),
        T("Comments", "`//` and `/* */`.",
          'fun main() {\n    // a note\n    println("ok")\n}', "ok"),

        U("Null safety", "The thing Kotlin is best known for."),
        T("Nothing is null", "A plain type cannot hold null at all.",
          'fun main() {\n    val s: String = "x"\n    println(s.length)\n}', "1"),
        T("A nullable type", "`?` is what allows null.",
          'fun main() {\n    val s: String? = null\n    println(s == null)\n}', "true"),
        T("Safe call", "`?.` gives null instead of throwing.",
          'fun main() {\n    val s: String? = null\n    println(s?.length)\n}', "null"),
        T("Elvis", "`?:` supplies a value when the left side is null.",
          'fun main() {\n    val s: String? = null\n    println(s?.length ?: 0)\n}', "0"),
        T("Smart casts", "After a null check the compiler knows.",
          'fun main() {\n    val s: String? = "ab"\n    if (s != null) println(s.length)\n}', "2"),

        U("Functions"),
        T("fun with a body", "Parameters typed, return type after a colon.",
          'fun add(a: Int, b: Int): Int {\n    return a + b\n}\n\nfun main() {\n'
          '    println(add(1, 2))\n}', "3"),
        T("An expression body", "`=` instead of braces, and no return type needed.",
          'fun double(n: Int) = n * 2\n\nfun main() {\n    println(double(4))\n}', "8"),
        T("Default arguments", "No overloads needed.",
          'fun greet(who: String = "you") = "hi $who"\n\nfun main() {\n    println(greet())\n}',
          "hi you"),
        T("Named arguments", "Clearer at the call than a row of booleans.",
          'fun box(w: Int, h: Int) = w * h\n\nfun main() {\n    println(box(h = 2, w = 3))\n}',
          "6"),
        T("A lambda", "In braces, with `it` for a single argument.",
          'fun main() {\n    val double = { n: Int -> n * 2 }\n    println(double(3))\n}', "6"),
        T("An extension function", "Adding a method to a type you do not own.",
          'fun String.shout() = uppercase() + "!"\n\nfun main() {\n    println("hi".shout())\n}',
          "HI!"),

        U("Collections"),
        T("A read-only list", "`listOf` is immutable, which is the default to want.",
          'fun main() {\n    val items = listOf(1, 2)\n    println(items[1])\n}', "2"),
        T("A mutable list", "`mutableListOf` when it has to change.",
          'fun main() {\n    val items = mutableListOf(1)\n    items.add(2)\n'
          '    println(items.size)\n}', "2"),
        T("map", "A new list, one item per item.",
          'fun main() {\n    println(listOf(1, 2).map { it * 2 })\n}', "[2, 4]"),
        T("filter", "Keeps the ones that pass.",
          'fun main() {\n    println(listOf(1, 2, 3).filter { it % 2 == 1 })\n}', "[1, 3]"),
        T("sum and sorted", "Both on the collection itself.",
          'fun main() {\n    println(listOf(3, 1).sorted())\n}', "[1, 3]"),
        T("A map", "`mapOf`, with `to` making the pairs.",
          'fun main() {\n    val ages = mapOf("a" to 1)\n    println(ages["a"])\n}', "1"),
        T("Iterating a map", "Destructuring in the loop header.",
          'fun main() {\n    for ((k, v) in mapOf("a" to 1)) println("$k $v")\n}', "a 1"),

        U("Classes"),
        T("A class", "The constructor is in the header.",
          'class Dog(val name: String)\n\nfun main() {\n    println(Dog("rex").name)\n}', "rex"),
        T("A data class", "equals, hashCode, toString and copy, written for you.",
          'data class Point(val x: Int)\n\nfun main() {\n    println(Point(1))\n}', "Point(x=1)"),
        T("Inheritance", "Classes are final unless marked `open`.",
          'open class A {\n    open fun n() = 1\n}\n\nclass B : A() {\n'
          '    override fun n() = 2\n}\n\nfun main() {\n    println(B().n())\n}', "2"),
        T("An interface", "It can have default implementations.",
          'interface Speaker {\n    fun speak() = "..."\n}\n\nclass Dog : Speaker {\n'
          '    override fun speak() = "woof"\n}\n\nfun main() {\n    println(Dog().speak())\n}',
          "woof"),
        T("An object", "A singleton, declared rather than constructed.",
          'object Config {\n    val size = 3\n}\n\nfun main() {\n    println(Config.size)\n}', "3"),
        T("A sealed class", "A fixed set of subclasses, which makes `when` exhaustive.",
          'sealed class Shape\nclass Circle(val r: Int) : Shape()\n\nfun main() {\n'
          '    val s: Shape = Circle(2)\n    println(when (s) {\n'
          '        is Circle -> s.r\n    })\n}', "2"),

        U("Further in"),
        T("when as a statement", "Kotlin's switch, and much more than one.",
          'fun main() {\n    val n = 2\n    when (n) {\n        1 -> println("one")\n'
          '        else -> println("other")\n    }\n}', "other"),
        T("when as an expression", "It has a value.",
          'fun main() {\n    val n = 5\n    println(if (n > 3) "big" else "small")\n}', "big"),
        T("let", "Runs a block with the value as `it`.",
          'fun main() {\n    val s: String? = "ab"\n    s?.let { println(it.length) }\n}', "2"),
        T("apply", "Configures an object and gives it back.",
          'class Box {\n    var size = 0\n}\n\nfun main() {\n'
          '    val b = Box().apply { size = 4 }\n    println(b.size)\n}', "4"),
        T("Destructuring", "Any data class can be taken apart.",
          'data class P(val x: Int, val y: Int)\n\nfun main() {\n    val (x, y) = P(1, 2)\n'
          '    println(x + y)\n}', "3"),
        T("A coroutine", "Suspending work, without a thread each.",
          'import kotlinx.coroutines.runBlocking\n\nfun main() = runBlocking {\n'
          '    println("in a coroutine")\n}', "in a coroutine"),
    ],
)


SWIFT = Course(
    "swift", "Swift", "Edited and highlighted here. Building it needs Xcode or the toolchain.",
    ".swift", "text",
    [
        U("First steps"),
        T("print", "No main function needed in a script.",
          'print("hello")', "hello"),
        T("let and var", "`let` is constant, `var` is not.",
          'let n = 5\nprint(n)', "5"),
        T("Types", "After a colon, and usually inferred.",
          'let n: Int = 7\nprint(n)', "7"),
        T("Interpolation", "`\\(expression)` inside the string.",
          'let n = 4\nprint("n is \\(n)")', "n is 4"),
        T("Comments", "`//` and `/* */`.",
          '// a note\nprint("ok")', "ok"),

        U("Optionals"),
        T("An optional", "`?` is what allows nil.",
          'let s: String? = nil\nprint(s == nil)', "true"),
        T("if let", "Unwraps into a new name, inside the block.",
          'let s: String? = "ab"\nif let t = s {\n    print(t.count)\n}', "2"),
        T("guard let", "Unwraps and leaves early if it cannot.",
          'func length(_ s: String?) -> Int {\n    guard let s = s else { return 0 }\n'
          '    return s.count\n}\nprint(length(nil))', "0"),
        T("Nil coalescing", "`??` gives a default.",
          'let s: String? = nil\nprint(s ?? "none")', "none"),
        T("Optional chaining", "`?.` stops rather than crashing.",
          'let s: String? = nil\nprint(s?.count as Any)', "nil"),

        U("Functions and closures"),
        T("func", "Argument labels are part of the name.",
          'func add(a: Int, b: Int) -> Int {\n    return a + b\n}\nprint(add(a: 1, b: 2))', "3"),
        T("No label", "`_` turns the label off.",
          'func double(_ n: Int) -> Int {\n    return n * 2\n}\nprint(double(4))', "8"),
        T("Default arguments", "Written in the signature.",
          'func greet(who: String = "you") -> String {\n    return "hi " + who\n}\nprint(greet())',
          "hi you"),
        T("A closure", "In braces, with `in` after the arguments.",
          'let add = { (a: Int, b: Int) in a + b }\nprint(add(1, 2))', "3"),
        T("Trailing closure", "The last argument can go outside the brackets.",
          'print([1, 2].map { $0 * 2 })', "[2, 4]"),

        U("Collections"),
        T("An array", "Ordered and typed.",
          'let items = [1, 2]\nprint(items[1])', "2"),
        T("Appending", "On a `var` array.",
          'var items = [1]\nitems.append(2)\nprint(items.count)', "2"),
        T("filter and reduce", "The usual pipeline.",
          'print([1, 2, 3].reduce(0, +))', "6"),
        T("A dictionary", "Keys to values; a read gives an optional.",
          'let ages = ["a": 1]\nprint(ages["a"] ?? 0)', "1"),
        T("A set", "No duplicates.",
          'print(Set([1, 1, 2]).count)', "2"),
        T("for in", "Over a range or a collection.",
          'for i in 0..<3 {\n    print(i)\n}', "0\n1\n2"),

        U("Types"),
        T("A struct", "A value type, copied when assigned.",
          'struct Point {\n    var x: Int\n}\nlet p = Point(x: 3)\nprint(p.x)', "3"),
        T("A class", "A reference type, shared when assigned.",
          'class Box {\n    var size = 4\n}\nprint(Box().size)', "4"),
        T("A method", "A func inside a type.",
          'struct Point {\n    var x: Int\n    func double() -> Int {\n        return x * 2\n    }\n}\n'
          'print(Point(x: 2).double())', "4"),
        T("A protocol", "Swift's interface.",
          'protocol Speaker {\n    func speak() -> String\n}\nstruct Dog: Speaker {\n'
          '    func speak() -> String { "woof" }\n}\nprint(Dog().speak())', "woof"),
        T("An enum with values", "Associated values, and pattern matching.",
          'enum Shape {\n    case circle(Double)\n}\nlet s = Shape.circle(2)\nswitch s {\n'
          'case .circle(let r):\n    print(r)\n}', "2.0"),
        T("Errors", "`throws`, `try` and `catch`.",
          'enum Problem: Error { case no }\nfunc fail() throws { throw Problem.no }\n'
          'do {\n    try fail()\n} catch {\n    print("caught")\n}', "caught"),
    ],
)


COURSES = [RUST, GO, CPP, JAVA, KOTLIN, SWIFT]
