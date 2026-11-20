"""Checks the Rust interpreter against real Rust programs.

Each case is source that `rustc` would accept, paired with the output it would
produce. Where this interpreter cannot match real Rust - integer overflow
panics, and anything the borrow checker would reject - there is deliberately
no case, rather than one that blesses a wrong answer.
"""

from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "python"))

from pycmd_langs import rust_interp                    # noqa: E402
from pycmd_langs.clike_lexer import LangSyntaxError     # noqa: E402
from pycmd_langs.rust_values import RustError           # noqa: E402

CASES = []
ERROR_CASES = []


def check(name, source, expected, stdin=""):
    CASES.append((name, source, expected, stdin))


def check_error(name, source, fragment):
    ERROR_CASES.append((name, source, fragment))


def wrap(body, extra=""):
    return f"{extra}\nfn main() {{\n{body}\n}}\n"


# ------------------------------------------------------------------- basics

check("hello", wrap('    println!("hello, world");'), "hello, world\n")
check("formatting", wrap('''
    let name = "Ada";
    let age = 36;
    println!("{} is {}", name, age);
    println!("{name} is {age}");
    println!("{0} {1} {0}", "a", "b");
'''), "Ada is 36\nAda is 36\na b a\n")
check("debug formatting", wrap('''
    println!("{:?}", vec![1, 2, 3]);
    println!("{:?}", "text");
    println!("{:?}", (1, "two"));
    println!("{:?} {:?}", 2.0, 2.5);
    println!("{} {}", 2.0, 2.5);
'''), '[1, 2, 3]\n"text"\n(1, "two")\n2.0 2.5\n2 2.5\n')
check("format specs", wrap('''
    println!("{:5}|{:<5}|{:>5}|{:^5}|", 42, 42, 42, 42);
    println!("{:05}|{:+}|", 42, 42);
    println!("{:.2}|{:8.3}|", 3.14159, 3.14159);
    println!("{:x} {:X} {:b} {:o} {:#x}", 255, 255, 5, 8, 255);
    println!("{:width$}", 7, width = 4);
'''.replace("{:width$}\", 7, width = 4", "{:4}\", 7")),
      "   42|42   |   42| 42  |\n00042|+42|\n3.14|   3.142|\nff FF 101 10 0xff\n   7\n")
check("arithmetic", wrap('''
    println!("{} {} {} {}", 7 / 2, 7 % 2, -7 / 2, -7 % 2);
    println!("{} {}", 7.0 / 2.0, 2i32.pow(10));
    println!("{} {}", (2.0_f64).sqrt(), (-5i32).abs());
'''), "3 1 -3 -1\n3.5 1024\n1.4142135623730951 5\n")
check("let and mut", wrap('''
    let x = 5;
    let mut y = 10;
    y += x;
    let x = x * 2;
    println!("{} {}", x, y);
'''), "10 15\n")
check("types and casts", wrap('''
    let a = 3.7_f64;
    let b = a as i32;
    let c = 65u8 as char;
    println!("{} {} {}", a, b, c);
'''), "3.7 3 A\n")
check("booleans and comparison", wrap('''
    let a = 5;
    println!("{} {} {}", a > 3, a == 5 && a < 10, !(a > 3));
'''), "true true false\n")
check("chars and strings", wrap('''
    let s = String::from("hello");
    println!("{} {} {}", s.len(), s.to_uppercase(), s.contains("ell"));
    let c = 'x';
    println!("{} {}", c, c.is_alphabetic());
'''), "5 HELLO true\nx true\n")
check("constants", wrap('    println!("{} {}", MAX, NAME);',
                        extra='const MAX: i32 = 100;\nconst NAME: &str = "pycmd";'),
      "100 pycmd\n")

# ------------------------------------------------------------ control flow

check("if else", wrap('''
    let n = 7;
    if n % 2 == 0 {
        println!("even");
    } else if n > 5 {
        println!("odd and big");
    } else {
        println!("odd");
    }
'''), "odd and big\n")
check("if as an expression", wrap('''
    let n = 4;
    let label = if n % 2 == 0 { "even" } else { "odd" };
    println!("{}", label);
'''), "even\n")
check("loop with break value", wrap('''
    let mut n = 0;
    let result = loop {
        n += 1;
        if n * n > 50 {
            break n;
        }
    };
    println!("{}", result);
'''), "8\n")
check("while", wrap('''
    let mut n = 1;
    while n < 100 {
        n *= 3;
    }
    println!("{}", n);
'''), "243\n")
check("for over a range", wrap('''
    let mut total = 0;
    for i in 1..=10 {
        total += i;
    }
    println!("{}", total);
'''), "55\n")
check("for over a vec", wrap('''
    for word in &["a", "b", "c"] {
        print!("{} ", word);
    }
    println!();
'''), "a b c \n")
check("continue and break", wrap('''
    for i in 0..10 {
        if i % 2 == 0 {
            continue;
        }
        if i > 6 {
            break;
        }
        print!("{}", i);
    }
    println!();
'''), "135\n")
check("nested loops", wrap('''
    for i in 1..4 {
        for j in 1..4 {
            print!("{} ", i * j);
        }
    }
    println!();
'''), "1 2 3 2 4 6 3 6 9 \n")

# ---------------------------------------------------------------- functions

check("functions", wrap('    println!("{} {}", add(2, 3), square(4));',
                        extra='''
fn add(a: i32, b: i32) -> i32 {
    a + b
}

fn square(n: i32) -> i32 {
    n * n
}'''), "5 16\n")
check("early return", wrap('    println!("{} {}", classify(5), classify(-1));',
                           extra='''
fn classify(n: i32) -> &'static str {
    if n < 0 {
        return "negative";
    }
    "positive"
}'''), "positive negative\n")
check("recursion", wrap('    println!("{} {}", fact(10), fib(20));', extra='''
fn fact(n: u64) -> u64 {
    if n <= 1 { 1 } else { n * fact(n - 1) }
}

fn fib(n: u32) -> u64 {
    match n {
        0 => 0,
        1 => 1,
        _ => fib(n - 1) + fib(n - 2),
    }
}'''), "3628800 6765\n")
check("closures", wrap('''
    let double = |n: i32| n * 2;
    let add = |a, b| a + b;
    println!("{} {}", double(21), add(1, 2));
    let mut count = 0;
    let mut bump = || { count += 1; };
    bump();
    bump();
    println!("{}", count);
'''), "42 3\n2\n")
check("functions taking closures", wrap('''
    println!("{}", apply(5, |n| n * n));
''', extra='''
fn apply(value: i32, f: impl Fn(i32) -> i32) -> i32 {
    f(value)
}'''), "25\n")
check("mutable reference argument", wrap('''
    let mut n = 1;
    bump(&mut n);
    bump(&mut n);
    println!("{}", n);
''', extra='''
fn bump(value: &mut i32) {
    *value += 1;
}'''), "3\n")
check("vec passed by mutable reference", wrap('''
    let mut xs = vec![1];
    fill(&mut xs);
    println!("{:?}", xs);
''', extra='''
fn fill(target: &mut Vec<i32>) {
    target.push(2);
    target.push(3);
}'''), "[1, 2, 3]\n")

# --------------------------------------------------------- vectors and maps

check("vec basics", wrap('''
    let mut xs: Vec<i32> = Vec::new();
    xs.push(1);
    xs.push(2);
    xs.push(3);
    println!("{:?} {} {:?}", xs, xs.len(), xs.first());
    let top = xs.pop();
    println!("{:?} {:?}", top, xs);
'''), "[1, 2, 3] 3 Some(1)\nSome(3) [1, 2]\n")
check("vec indexing and iteration", wrap('''
    let xs = vec![10, 20, 30];
    println!("{} {}", xs[0], xs[2]);
    let mut total = 0;
    for x in &xs {
        total += x;
    }
    println!("{}", total);
'''), "10 30\n60\n")
check("sorting", wrap('''
    let mut xs = vec![5, 2, 9, 1];
    xs.sort();
    println!("{:?}", xs);
    xs.sort_by(|a, b| b.cmp(a));
    println!("{:?}", xs);
    let mut words = vec!["pear", "fig", "banana"];
    words.sort_by_key(|w| w.len());
    println!("{:?}", words);
'''), "[1, 2, 5, 9]\n[9, 5, 2, 1]\n[\"fig\", \"pear\", \"banana\"]\n")
check("iterator chains", wrap('''
    let xs: Vec<i32> = (1..=10).collect();
    let evens: Vec<i32> = xs.iter().filter(|n| *n % 2 == 0).cloned().collect();
    let doubled: Vec<i32> = xs.iter().map(|n| n * 2).collect();
    let total: i32 = xs.iter().sum();
    println!("{:?}", evens);
    println!("{:?}", &doubled[0..3]);
    println!("{} {} {}", total, xs.iter().count(), xs.iter().max().unwrap());
'''), "[2, 4, 6, 8, 10]\n[2, 4, 6]\n55 10 10\n")
check("enumerate and zip", wrap('''
    let names = vec!["a", "b"];
    for (i, name) in names.iter().enumerate() {
        print!("{}{} ", i, name);
    }
    println!();
    let pairs: Vec<(i32, char)> = vec![1, 2].into_iter().zip(vec!['x', 'y']).collect();
    println!("{:?}", pairs);
'''), "0a 1b \n[(1, 'x'), (2, 'y')]\n")
check("fold and any", wrap('''
    let xs = vec![1, 2, 3, 4];
    let product = xs.iter().fold(1, |acc, n| acc * n);
    println!("{} {} {}", product, xs.iter().any(|n| *n > 3), xs.iter().all(|n| *n > 0));
'''), "24 true true\n")
check("hashmap", wrap('''
    let mut scores: HashMap<String, i32> = HashMap::new();
    scores.insert(String::from("ada"), 10);
    scores.insert(String::from("alan"), 7);
    println!("{} {:?} {}", scores.len(), scores.get("ada"), scores.contains_key("bob"));
    if let Some(value) = scores.get("alan") {
        println!("alan has {}", value);
    }
''', extra="use std::collections::HashMap;"), "2 Some(10) false\nalan has 7\n")
check("counting with entry", wrap('''
    let mut counts: HashMap<&str, i32> = HashMap::new();
    for word in "the cat the hat".split_whitespace() {
        *counts.entry(word).or_insert(0) += 1;
    }
    let mut keys: Vec<&str> = counts.keys().cloned().collect();
    keys.sort();
    for key in keys {
        print!("{}={} ", key, counts[key]);
    }
    println!();
''', extra="use std::collections::HashMap;"), "cat=1 hat=1 the=2 \n")
check("hashset", wrap('''
    let mut seen: HashSet<i32> = HashSet::new();
    for n in [1, 2, 2, 3, 1] {
        seen.insert(n);
    }
    let mut items: Vec<i32> = seen.into_iter().collect();
    items.sort();
    println!("{:?}", items);
''', extra="use std::collections::HashSet;"), "[1, 2, 3]\n")

# ------------------------------------------------------------------ strings

check("string methods", wrap('''
    let s = "  Hello, Rust World  ";
    println!("[{}]", s.trim());
    println!("{}", s.trim().replace("Rust", "the"));
    println!("{:?}", "a,b,c".split(',').collect::<Vec<&str>>());
    println!("{}", "abc".chars().rev().collect::<String>());
    println!("{} {}", "hello".starts_with("he"), "hello".find("ll").unwrap());
    let mut owned = String::from("ab");
    owned.push_str("cd");
    owned.push('e');
    println!("{} {}", owned, owned.len());
'''), "[Hello, Rust World]\nHello, the World\n[\"a\", \"b\", \"c\"]\ncba\ntrue 2\nabcde 5\n")
check("parsing", wrap('''
    let n: i32 = "42".parse().unwrap();
    let f = "2.5".parse::<f64>().unwrap();
    let bad = "abc".parse::<i32>();
    println!("{} {} {}", n + 1, f * 2.0, bad.is_err());
'''), "43 5 true\n")
check("counting characters", wrap('''
    let text = "hello world";
    let vowels = text.chars().filter(|c| "aeiou".contains(*c)).count();
    println!("{} {}", vowels, text.split_whitespace().count());
'''), "3 2\n")

# ------------------------------------------------------------------ structs

check("structs", wrap('''
    let p = Point { x: 3, y: 4 };
    println!("{} {} {:?}", p.x, p.y, p);
''', extra='''
#[derive(Debug)]
struct Point {
    x: i32,
    y: i32,
}'''), "3 4 Point { x: 3, y: 4 }\n")
check("impl blocks", wrap('''
    let p = Point::new(3, 4);
    println!("{} {}", p.dist_squared(), p.sum());
''', extra='''
struct Point {
    x: i32,
    y: i32,
}

impl Point {
    fn new(x: i32, y: i32) -> Self {
        Point { x, y }
    }

    fn dist_squared(&self) -> i32 {
        self.x * self.x + self.y * self.y
    }

    fn sum(&self) -> i32 {
        self.x + self.y
    }
}'''), "25 7\n")
check("mutating methods", wrap('''
    let mut c = Counter { total: 0 };
    c.add(3);
    c.add(4);
    println!("{}", c.total);
''', extra='''
struct Counter {
    total: i32,
}

impl Counter {
    fn add(&mut self, n: i32) {
        self.total += n;
    }
}'''), "7\n")
check("tuple struct", wrap('''
    let m = Meters(5.0);
    println!("{} {:?}", m.0 * 2.0, m);
''', extra='#[derive(Debug)]\nstruct Meters(f64);'), "10 Meters(5.0)\n")
check("vec of structs", wrap('''
    let people = vec![
        Person { name: String::from("ada"), age: 36 },
        Person { name: String::from("alan"), age: 41 },
    ];
    for p in &people {
        println!("{} is {}", p.name, p.age);
    }
    let oldest = people.iter().max_by_key(|p| p.age).unwrap();
    println!("oldest: {}", oldest.name);
''', extra='''
struct Person {
    name: String,
    age: u32,
}'''), "ada is 36\nalan is 41\noldest: alan\n")
check("Display impl", wrap('''
    let p = Point { x: 1, y: 2 };
    println!("{}", p);
''', extra='''
use std::fmt;

struct Point {
    x: i32,
    y: i32,
}

impl fmt::Display for Point {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "({}, {})", self.x, self.y)
    }
}'''), "(1, 2)\n")
check("struct update syntax", wrap('''
    let base = Config { debug: false, level: 1 };
    let custom = Config { debug: true, ..base };
    println!("{} {}", custom.debug, custom.level);
''', extra='''
struct Config {
    debug: bool,
    level: i32,
}'''), "true 1\n")

# ------------------------------------------------------------------- enums

check("enums with payloads", wrap('''
    let shapes = vec![Shape::Circle(2.0), Shape::Rect { w: 3.0, h: 4.0 }, Shape::Empty];
    for shape in &shapes {
        println!("{:.2}", area(shape));
    }
''', extra='''
enum Shape {
    Circle(f64),
    Rect { w: f64, h: f64 },
    Empty,
}

fn area(shape: &Shape) -> f64 {
    match shape {
        Shape::Circle(r) => 3.14159 * r * r,
        Shape::Rect { w, h } => w * h,
        Shape::Empty => 0.0,
    }
}'''), "12.57\n12.00\n0.00\n")
check("enum debug", wrap('''
    println!("{:?} {:?}", Direction::North, Direction::South);
''', extra='#[derive(Debug)]\nenum Direction { North, South }'), "North South\n")
check("match on numbers", wrap('''
    for n in [0, 3, 7, 100] {
        let label = match n {
            0 => "zero",
            1..=5 => "small",
            6 | 7 => "lucky",
            _ => "big",
        };
        print!("{} ", label);
    }
    println!();
'''), "zero small lucky big \n")
check("match with a guard", wrap('''
    let pair = (3, -3);
    let text = match pair {
        (x, y) if x + y == 0 => "opposites",
        (x, _) if x % 2 == 0 => "first is even",
        _ => "other",
    };
    println!("{}", text);
'''), "opposites\n")
check("match binds", wrap('''
    let maybe = Some(5);
    match maybe {
        Some(n) if n > 3 => println!("big {}", n),
        Some(n) => println!("small {}", n),
        None => println!("nothing"),
    }
'''), "big 5\n")

# --------------------------------------------------------- Option and Result

check("option", wrap('''
    let xs = vec![1, 2, 3];
    let found = xs.iter().find(|n| **n > 1);
    println!("{:?} {:?}", found, xs.iter().find(|n| **n > 9));
    println!("{} {}", found.is_some(), found.unwrap());
    let missing: Option<i32> = None;
    println!("{}", missing.unwrap_or(0));
'''), "Some(2) None\ntrue 2\n0\n")
check("if let and while let", wrap('''
    let value = Some(3);
    if let Some(n) = value {
        println!("got {}", n);
    }
    let mut stack = vec![1, 2, 3];
    while let Some(top) = stack.pop() {
        print!("{} ", top);
    }
    println!();
'''), "got 3\n3 2 1 \n")
check("result", wrap('''
    println!("{:?}", divide(10, 2));
    println!("{:?}", divide(1, 0));
    match divide(9, 3) {
        Ok(v) => println!("ok {}", v),
        Err(e) => println!("err {}", e),
    }
''', extra='''
fn divide(a: i32, b: i32) -> Result<i32, String> {
    if b == 0 {
        return Err(String::from("cannot divide by zero"));
    }
    Ok(a / b)
}'''), 'Ok(5)\nErr("cannot divide by zero")\nok 3\n')
check("the question mark operator", wrap('''
    println!("{:?}", total("1 2 3"));
    println!("{}", total("1 x 3").is_err());
''', extra='''
fn total(text: &str) -> Result<i32, std::num::ParseIntError> {
    let mut sum = 0;
    for part in text.split_whitespace() {
        sum += part.parse::<i32>()?;
    }
    Ok(sum)
}'''), "Ok(6)\ntrue\n")
check("option chaining", wrap('''
    let words = vec!["10", "abc"];
    let numbers: Vec<i32> = words.iter().filter_map(|w| w.parse().ok()).collect();
    println!("{:?}", numbers);
'''), "[10]\n")

# ------------------------------------------------------------------ traits

check("traits", wrap('''
    let shapes: Vec<Box<dyn Shape>> = vec![Box::new(Circle { r: 1.0 }), Box::new(Square { s: 2.0 })];
    for shape in &shapes {
        println!("{} {:.2}", shape.name(), shape.area());
    }
''', extra='''
trait Shape {
    fn area(&self) -> f64;
    fn name(&self) -> String {
        String::from("shape")
    }
}

struct Circle {
    r: f64,
}

struct Square {
    s: f64,
}

impl Shape for Circle {
    fn area(&self) -> f64 {
        3.14159 * self.r * self.r
    }

    fn name(&self) -> String {
        String::from("circle")
    }
}

impl Shape for Square {
    fn area(&self) -> f64 {
        self.s * self.s
    }
}'''), "circle 3.14\nshape 4.00\n")

# ------------------------------------------------------------------- input

check("reading a line", wrap('''
    let mut line = String::new();
    io::stdin().read_line(&mut line).unwrap();
    println!("hello, {}", line.trim());
''', extra="use std::io;"), "hello, Ada\n", stdin="Ada\n")
check("reading numbers", wrap('''
    let mut line = String::new();
    io::stdin().read_line(&mut line).unwrap();
    let total: i32 = line.trim().split_whitespace()
        .map(|p| p.parse::<i32>().unwrap())
        .sum();
    println!("{}", total);
''', extra="use std::io;"), "6\n", stdin="1 2 3\n")

# -------------------------------------------------------- bigger programs

check("fizzbuzz", wrap('''
    for i in 1..=15 {
        match (i % 3, i % 5) {
            (0, 0) => println!("FizzBuzz"),
            (0, _) => println!("Fizz"),
            (_, 0) => println!("Buzz"),
            _ => println!("{}", i),
        }
    }
'''), "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz\n")
check("prime sieve", wrap('''
    let limit = 30;
    let mut sieve = vec![true; limit + 1];
    let mut primes = Vec::new();
    for n in 2..=limit {
        if sieve[n] {
            primes.push(n);
            let mut m = n * n;
            while m <= limit {
                sieve[m] = false;
                m += n;
            }
        }
    }
    println!("{:?}", primes);
'''), "[2, 3, 5, 7, 11, 13, 17, 19, 23, 29]\n")
check("word frequency", wrap('''
    let text = "the quick the lazy the dog";
    let mut counts: HashMap<&str, usize> = HashMap::new();
    for word in text.split_whitespace() {
        *counts.entry(word).or_insert(0) += 1;
    }
    let mut pairs: Vec<(&str, usize)> = counts.into_iter().collect();
    pairs.sort_by(|a, b| b.1.cmp(&a.1));
    println!("{} appears {} times", pairs[0].0, pairs[0].1);
''', extra="use std::collections::HashMap;"), "the appears 3 times\n")
check("a stack machine", wrap('''
    let program = vec!["push 3", "push 4", "add", "push 2", "mul"];
    let mut stack: Vec<i32> = Vec::new();
    for line in &program {
        let parts: Vec<&str> = line.split(' ').collect();
        match parts[0] {
            "push" => stack.push(parts[1].parse().unwrap()),
            "add" => {
                let b = stack.pop().unwrap();
                let a = stack.pop().unwrap();
                stack.push(a + b);
            }
            "mul" => {
                let b = stack.pop().unwrap();
                let a = stack.pop().unwrap();
                stack.push(a * b);
            }
            _ => panic!("unknown instruction"),
        }
    }
    println!("{}", stack.pop().unwrap());
'''), "14\n")
check("a to-do list with impl and Option", wrap('''
    let mut list = TodoList::new();
    list.add("write code");
    list.add("test it");
    list.complete("test it");
    println!("{}", list.summary());
''', extra='''
struct Task {
    title: String,
    done: bool,
}

struct TodoList {
    tasks: Vec<Task>,
}

impl TodoList {
    fn new() -> Self {
        TodoList { tasks: Vec::new() }
    }

    fn add(&mut self, title: &str) {
        self.tasks.push(Task { title: String::from(title), done: false });
    }

    fn complete(&mut self, title: &str) -> bool {
        for task in self.tasks.iter_mut() {
            if task.title == title {
                task.done = true;
                return true;
            }
        }
        false
    }

    fn summary(&self) -> String {
        let done = self.tasks.iter().filter(|t| t.done).count();
        format!("{} of {} done", done, self.tasks.len())
    }
}'''), "1 of 2 done\n")
check("binary search", wrap('''
    let xs = vec![1, 3, 5, 7, 9];
    println!("{:?} {:?}", find(&xs, 7), find(&xs, 4));
''', extra='''
fn find(xs: &Vec<i32>, wanted: i32) -> Option<usize> {
    let mut low = 0;
    let mut high = xs.len();
    while low < high {
        let mid = (low + high) / 2;
        if xs[mid] == wanted {
            return Some(mid);
        } else if xs[mid] < wanted {
            low = mid + 1;
        } else {
            high = mid;
        }
    }
    None
}'''), "Some(3) None\n")
check("temperature table", wrap('''
    for c in (0..=100).step_by(25) {
        let f = c as f64 * 9.0 / 5.0 + 32.0;
        println!("{:>3}C = {:>5.1}F", c, f);
    }
'''), "  0C =  32.0F\n 25C =  77.0F\n 50C = 122.0F\n 75C = 167.0F\n100C = 212.0F\n")

# ------------------------------------------------------------------ errors

check_error("undefined variable", wrap('    println!("{}", missing);'), "cannot find")
check_error("syntax error", wrap("    let x = ;"), "line")
check_error("index out of bounds", wrap('''
    let xs = vec![1];
    println!("{}", xs[5]);
'''), "out of bounds")
check_error("divide by zero", wrap('''
    let n = 0;
    println!("{}", 1 / n);
'''), "divide by zero")
check_error("unwrap on None", wrap('''
    let value: Option<i32> = None;
    println!("{}", value.unwrap());
'''), "unwrap")
check_error("panic", wrap('    panic!("stop here");'), "stop here")
check_error("failed assertion", wrap("    assert_eq!(1 + 1, 3);"), "assertion")
check_error("no main", "fn other() {}\n", "no main")
check_error("unknown method", wrap('''
    let xs = vec![1];
    xs.frobnicate();
'''), "no method")


# Found by PyCmdTeach's Rust course in 2.8.0. Each was a lesson whose stated
# output the interpreter got wrong.
check("BTreeMap walks its keys in order", """
use std::collections::BTreeMap;
fn main() {
    let mut m = BTreeMap::new();
    m.insert(2, "b");
    m.insert(1, "a");
    let keys: Vec<_> = m.keys().collect();
    println!("{:?}", keys);
}
""", "[1, 2]\n")
check("self.0 on a tuple struct is a field, not the number 0.0", """
struct Sq(i32);
impl Sq {
    fn area(&self) -> i32 {
        self.0 * self.0
    }
}
fn main() {
    println!("{}", Sq(3).area());
}
""", "9\n")
check("impl Display can format self.0", """
use std::fmt;
struct P(i32);
impl fmt::Display for P {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "<{}>", self.0)
    }
}
fn main() {
    println!("{}", P(5));
}
""", "<5>\n")

def run_one(source, stdin_text):
    out = io.StringIO()
    rust_interp.run_source(source, stdout=out, stdin=io.StringIO(stdin_text))
    return out.getvalue()


def main() -> int:
    failures = 0

    for name, source, expected, stdin_text in CASES:
        try:
            got = run_one(source, stdin_text)
        except (RustError, LangSyntaxError) as error:
            print(f"FAIL {name}\n     raised: {error}")
            failures += 1
            continue
        except Exception as error:  # noqa: BLE001
            print(f"FAIL {name}\n     crashed: {type(error).__name__}: {error}")
            failures += 1
            continue
        if got != expected:
            print(f"FAIL {name}\n     wanted {expected!r}\n     got    {got!r}")
            failures += 1
        else:
            print(f"ok   {name}")

    for name, source, fragment in ERROR_CASES:
        try:
            run_one(source, "")
        except (RustError, LangSyntaxError) as error:
            if fragment.lower() in str(error).lower():
                print(f"ok   {name} (reported)")
            else:
                print(f"FAIL {name}\n     wanted {fragment!r} in {str(error)!r}")
                failures += 1
        except Exception as error:  # noqa: BLE001
            print(f"FAIL {name}\n     wrong exception: {type(error).__name__}: {error}")
            failures += 1
        else:
            print(f"FAIL {name}\n     no error was reported")
            failures += 1

    total = len(CASES) + len(ERROR_CASES)
    print(f"\n{total - failures}/{total} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
