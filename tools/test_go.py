"""Checks the Go interpreter against real Go programs.

Every case is a program someone could plausibly write, with the exact output
the real `go run` produces. Where the two would differ, the case is not here -
a test that codifies a wrong answer is worse than no test.
"""

from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "python"))

from pycmd_langs import go_interp                     # noqa: E402
from pycmd_langs.clike_lexer import LangSyntaxError    # noqa: E402
from pycmd_langs.go_values import GoError              # noqa: E402

CASES = []
ERROR_CASES = []


def check(name, source, expected, stdin=""):
    CASES.append((name, source, expected, stdin))


def check_error(name, source, fragment):
    ERROR_CASES.append((name, source, fragment))


def wrap(body, imports='import "fmt"', extra=""):
    return f'package main\n\n{imports}\n\n{extra}\nfunc main() {{\n{body}\n}}\n'


# ------------------------------------------------------------------- basics

check("hello", wrap('\tfmt.Println("hello, world")'), "hello, world\n")
check("several values", wrap('\tfmt.Println(1, "two", 3.5, true)'), "1 two 3.5 true\n")
check("print without newline", wrap('\tfmt.Print("a", "b")\n\tfmt.Print(1, 2)'), "ab1 2")
check("arithmetic", wrap("\tfmt.Println(7/2, 7%2, -7/2, -7%2, 7.0/2)"), "3 1 -3 -1 3.5\n")
check("integer overflow wraps", wrap(
    "\tvar n int64 = 9223372036854775807\n\tn++\n\tfmt.Println(n)"), "-9223372036854775808\n")
check("bit operations", wrap("\tfmt.Println(6&3, 6|3, 6^3, 6&^3, 1<<4, 32>>2)"),
      "2 7 5 4 16 8\n")
check("precedence", wrap("\tfmt.Println(2+3*4, (2+3)*4, 10-2-3)"), "14 20 5\n")
check("comparison and logic", wrap(
    "\tfmt.Println(1 < 2, 2 <= 2, 3 > 4, true && false, true || false, !true)"),
    "true true false false true false\n")
check("string basics", wrap(
    '\ts := "hello"\n\tfmt.Println(s+" there", len(s), s[1], string(s[1]))'),
    "hello there 5 101 e\n")
check("var declarations and zero values", wrap(
    "\tvar a int\n\tvar b string\n\tvar c bool\n\tvar d float64\n\tfmt.Println(a, b == \"\", c, d)"),
    "0 true false 0\n")
check("shadowing in a block", wrap(
    '\tx := 1\n\t{\n\t\tx := 2\n\t\tfmt.Println(x)\n\t}\n\tfmt.Println(x)'), "2\n1\n")
check("multiple assignment and swap", wrap(
    "\ta, b := 1, 2\n\ta, b = b, a\n\tfmt.Println(a, b)"), "2 1\n")
check("constants and iota", wrap("\tfmt.Println(A, B, C, Name)", extra="""
const (
	A = iota
	B
	C
)

const Name = "pycmd"
"""), "0 1 2 pycmd\n")

# ------------------------------------------------------------ control flow

check("if else if", wrap("""
	n := 15
	if n%15 == 0 {
		fmt.Println("fizzbuzz")
	} else if n%3 == 0 {
		fmt.Println("fizz")
	} else {
		fmt.Println("other")
	}
"""), "fizzbuzz\n")
check("if with an initialiser", wrap("""
	if v := 10; v > 5 {
		fmt.Println("big", v)
	}
"""), "big 10\n")
check("three-clause for", wrap("""
	sum := 0
	for i := 1; i <= 10; i++ {
		sum += i
	}
	fmt.Println(sum)
"""), "55\n")
check("while-style for", wrap("""
	n := 1
	for n < 100 {
		n *= 2
	}
	fmt.Println(n)
"""), "128\n")
check("bare for with break", wrap("""
	n := 0
	for {
		n++
		if n == 5 {
			break
		}
	}
	fmt.Println(n)
"""), "5\n")
check("continue", wrap("""
	total := 0
	for i := 0; i < 10; i++ {
		if i%2 == 0 {
			continue
		}
		total += i
	}
	fmt.Println(total)
"""), "25\n")
check("labelled break", wrap("""
outer:
	for i := 0; i < 3; i++ {
		for j := 0; j < 3; j++ {
			if i*j == 2 {
				break outer
			}
			fmt.Println(i, j)
		}
	}
"""), "0 0\n0 1\n0 2\n1 0\n1 1\n")
check("switch on a value", wrap("""
	for _, day := range []int{1, 6, 7} {
		switch day {
		case 6, 7:
			fmt.Println("weekend")
		default:
			fmt.Println("weekday")
		}
	}
"""), "weekday\nweekend\nweekend\n")
check("switch with no tag", wrap("""
	score := 72
	switch {
	case score >= 90:
		fmt.Println("A")
	case score >= 70:
		fmt.Println("B")
	default:
		fmt.Println("C")
	}
"""), "B\n")
check("switch with fallthrough", wrap("""
	switch 2 {
	case 2:
		fmt.Println("two")
		fallthrough
	case 3:
		fmt.Println("three")
	case 4:
		fmt.Println("four")
	}
"""), "two\nthree\n")

# ---------------------------------------------------------------- functions

check("functions", wrap("\tfmt.Println(add(2, 3), square(4))", extra="""
func add(a, b int) int { return a + b }

func square(n int) int {
	return n * n
}
"""), "5 16\n")
check("multiple return values", wrap("""
	q, r := divmod(17, 5)
	fmt.Println(q, r)
""", extra="""
func divmod(a, b int) (int, int) { return a / b, a % b }
"""), "3 2\n")
check("variadic", wrap("""
	fmt.Println(sum(), sum(1), sum(1, 2, 3))
	xs := []int{4, 5}
	fmt.Println(sum(xs...))
""", extra="""
func sum(values ...int) int {
	total := 0
	for _, v := range values {
		total += v
	}
	return total
}
"""), "0 1 6\n9\n")
check("recursion", wrap("\tfmt.Println(fact(10), fib(20))", extra="""
func fact(n int) int {
	if n <= 1 {
		return 1
	}
	return n * fact(n-1)
}

func fib(n int) int {
	if n < 2 {
		return n
	}
	return fib(n-1) + fib(n-2)
}
"""), "3628800 6765\n")
check("closures", wrap("""
	next := counter()
	fmt.Println(next(), next(), next())
""", extra="""
func counter() func() int {
	n := 0
	return func() int {
		n++
		return n
	}
}
"""), "1 2 3\n")
check("function values", wrap("""
	ops := map[string]func(int, int) int{
		"add": func(a, b int) int { return a + b },
		"mul": func(a, b int) int { return a * b },
	}
	fmt.Println(ops["add"](3, 4), ops["mul"](3, 4))
"""), "7 12\n")
check("defer runs last, in reverse", wrap("""
	defer fmt.Println("third")
	defer fmt.Println("second")
	fmt.Println("first")
"""), "first\nsecond\nthird\n")
check("defer sees the argument at the time it was deferred", wrap("""
	n := 1
	defer fmt.Println("deferred n was", n)
	n = 99
	fmt.Println("n is now", n)
"""), "n is now 99\ndeferred n was 1\n")

# ------------------------------------------------------- slices and arrays

check("slice literal and index", wrap("""
	xs := []int{10, 20, 30}
	fmt.Println(xs, xs[0], xs[2], len(xs))
"""), "[10 20 30] 10 30 3\n")
check("append", wrap("""
	var xs []int
	for i := 0; i < 5; i++ {
		xs = append(xs, i*i)
	}
	fmt.Println(xs, len(xs))
"""), "[0 1 4 9 16] 5\n")
check("append several at once", wrap("""
	xs := []int{1}
	xs = append(xs, 2, 3)
	ys := []int{4, 5}
	xs = append(xs, ys...)
	fmt.Println(xs)
"""), "[1 2 3 4 5]\n")
check("make with length and capacity", wrap("""
	xs := make([]int, 3, 10)
	fmt.Println(xs, len(xs), cap(xs))
	xs[1] = 7
	fmt.Println(xs)
"""), "[0 0 0] 3 10\n[0 7 0]\n")
check("slicing", wrap("""
	xs := []int{0, 1, 2, 3, 4, 5}
	fmt.Println(xs[2:4], xs[:3], xs[3:], xs[:])
"""), "[2 3] [0 1 2] [3 4 5] [0 1 2 3 4 5]\n")
check("slices share their backing array", wrap("""
	xs := []int{1, 2, 3, 4}
	ys := xs[1:3]
	ys[0] = 99
	fmt.Println(xs, ys)
"""), "[1 99 3 4] [99 3]\n")
check("copy", wrap("""
	src := []int{1, 2, 3}
	dst := make([]int, 3)
	n := copy(dst, src)
	dst[0] = 9
	fmt.Println(n, src, dst)
"""), "3 [1 2 3] [9 2 3]\n")
check("arrays are copied", wrap("""
	a := [3]int{1, 2, 3}
	b := a
	b[0] = 99
	fmt.Println(a, b, len(a))
"""), "[1 2 3] [99 2 3] 3\n")
check("two-dimensional slice", wrap("""
	grid := [][]int{{1, 2}, {3, 4}}
	total := 0
	for _, row := range grid {
		for _, v := range row {
			total += v
		}
	}
	fmt.Println(grid, total)
"""), "[[1 2] [3 4]] 10\n")
check("range with index and value", wrap("""
	for i, v := range []string{"a", "b"} {
		fmt.Println(i, v)
	}
"""), "0 a\n1 b\n")
check("bubble sort", wrap("""
	xs := []int{5, 2, 9, 1, 7}
	for i := 0; i < len(xs); i++ {
		for j := 0; j < len(xs)-i-1; j++ {
			if xs[j] > xs[j+1] {
				xs[j], xs[j+1] = xs[j+1], xs[j]
			}
		}
	}
	fmt.Println(xs)
"""), "[1 2 5 7 9]\n")

# ------------------------------------------------------------------- maps

check("map literal", wrap("""
	ages := map[string]int{"ada": 36, "alan": 41}
	fmt.Println(ages["ada"], len(ages))
"""), "36 2\n")
check("map comma-ok", wrap("""
	m := map[string]int{"a": 1}
	v, ok := m["a"]
	missing, found := m["z"]
	fmt.Println(v, ok, missing, found)
"""), "1 true 0 false\n")
check("map write and delete", wrap("""
	m := make(map[string]int)
	m["x"] = 1
	m["y"] = 2
	delete(m, "x")
	fmt.Println(len(m), m["y"])
"""), "1 2\n")
check("map printing is sorted by key", wrap("""
	m := map[string]int{"b": 2, "a": 1, "c": 3}
	fmt.Println(m)
"""), "map[a:1 b:2 c:3]\n")
check("word count", wrap("""
	counts := map[string]int{}
	for _, word := range strings.Fields("the cat the hat") {
		counts[word]++
	}
	fmt.Println(counts)
""", imports='import (\n\t"fmt"\n\t"strings"\n)'), "map[cat:1 hat:1 the:2]\n")

# ---------------------------------------------------------------- structs

check("struct literal and fields", wrap("""
	p := Point{X: 3, Y: 4}
	fmt.Println(p, p.X, p.Y)
	fmt.Printf("%v %+v\\n", p, p)
""", extra="""
type Point struct {
	X, Y int
}
"""), "{3 4} 3 4\n{3 4} {X:3 Y:4}\n")
check("struct values are copied", wrap("""
	a := Point{1, 2}
	b := a
	b.X = 99
	fmt.Println(a, b)
""", extra="type Point struct {\n\tX, Y int\n}\n"), "{1 2} {99 2}\n")
check("pointer to struct", wrap("""
	p := &Point{1, 2}
	p.X = 10
	move(p)
	fmt.Println(*p, p.X)
""", extra="""
type Point struct {
	X, Y int
}

func move(p *Point) { p.Y += 5 }
"""), "{10 7} 10\n")
check("methods with a value receiver", wrap("""
	p := Point{3, 4}
	fmt.Println(p.Dist(), p.Sum())
""", extra="""
type Point struct {
	X, Y int
}

func (p Point) Dist() int { return p.X*p.X + p.Y*p.Y }

func (p Point) Sum() int { return p.X + p.Y }
"""), "25 7\n")
check("methods with a pointer receiver mutate", wrap("""
	c := Counter{}
	c.Add(3)
	c.Add(4)
	fmt.Println(c.Total)
""", extra="""
type Counter struct {
	Total int
}

func (c *Counter) Add(n int) { c.Total += n }
"""), "7\n")
check("slice of structs", wrap("""
	people := []Person{{"ada", 36}, {"alan", 41}}
	for _, p := range people {
		fmt.Printf("%s is %d\\n", p.Name, p.Age)
	}
""", extra="""
type Person struct {
	Name string
	Age  int
}
"""), "ada is 36\nalan is 41\n")
check("nested structs", wrap("""
	c := Company{Name: "exp", Boss: Person{Name: "ada"}}
	fmt.Println(c.Boss.Name, c)
""", extra="""
type Person struct {
	Name string
}

type Company struct {
	Name string
	Boss Person
}
"""), "ada {exp {ada}}\n")
check("struct with a String method", wrap("""
	fmt.Println(Point{1, 2})
""", extra="""
type Point struct {
	X, Y int
}

func (p Point) String() string { return fmt.Sprintf("(%d, %d)", p.X, p.Y) }
"""), "(1, 2)\n")
check("map of structs", wrap("""
	m := map[string]Point{"origin": {0, 0}, "unit": {1, 1}}
	fmt.Println(m["unit"].X, len(m))
""", extra="type Point struct {\n\tX, Y int\n}\n"), "1 2\n")

# ------------------------------------------------------------- interfaces

check("interfaces dispatch dynamically", wrap("""
	shapes := []Shape{Circle{2}, Rect{3, 4}}
	for _, s := range shapes {
		fmt.Printf("%.2f\\n", s.Area())
	}
""", extra="""
type Shape interface {
	Area() float64
}

type Circle struct {
	R float64
}

func (c Circle) Area() float64 { return 3.14159 * c.R * c.R }

type Rect struct {
	W, H float64
}

func (r Rect) Area() float64 { return r.W * r.H }
"""), "12.57\n12.00\n")
check("type switch", wrap("""
	for _, v := range []interface{}{1, "two", 3.5, true} {
		describe(v)
	}
""", extra="""
func describe(v interface{}) {
	switch x := v.(type) {
	case int:
		fmt.Println("int", x*2)
	case string:
		fmt.Println("string", len(x))
	case float64:
		fmt.Println("float", x)
	default:
		fmt.Println("something else")
	}
}
"""), "int 2\nstring 3\nfloat 3.5\nsomething else\n")
check("type assertion with comma-ok", wrap("""
	var v interface{} = "text"
	s, ok := v.(string)
	n, notOk := v.(int)
	fmt.Println(s, ok, n, notOk)
"""), "text true 0 false\n")

# ----------------------------------------------------------------- errors

check("errors", wrap("""
	if _, err := half(3); err != nil {
		fmt.Println("error:", err)
	}
	v, err := half(4)
	fmt.Println(v, err)
""", extra="""
func half(n int) (int, error) {
	if n%2 != 0 {
		return 0, errors.New("not even")
	}
	return n / 2, nil
}
""", imports='import (\n\t"errors"\n\t"fmt"\n)'), "error: not even\n2 <nil>\n")
check("fmt.Errorf", wrap("""
	err := fmt.Errorf("failed at step %d", 3)
	fmt.Println(err)
"""), "failed at step 3\n")
check("panic and recover", wrap("""
	fmt.Println(safe())
	fmt.Println("still running")
""", extra="""
func safe() (result string) {
	defer func() {
		if r := recover(); r != nil {
			result = fmt.Sprintf("recovered: %v", r)
		}
	}()
	panic("boom")
}
"""), "recovered: boom\nstill running\n")

# ------------------------------------------------------- standard library

check("strings", wrap("""
	s := "  Hello, Go World  "
	fmt.Println(strings.TrimSpace(s))
	fmt.Println(strings.ToUpper("abc"), strings.ToLower("ABC"))
	fmt.Println(strings.Contains(s, "Go"), strings.HasPrefix("golang", "go"))
	fmt.Println(strings.Split("a,b,c", ","))
	fmt.Println(strings.Join([]string{"x", "y"}, "-"))
	fmt.Println(strings.Replace("aaa", "a", "b", 2), strings.ReplaceAll("aaa", "a", "b"))
	fmt.Println(strings.Index("chicken", "ken"), strings.Repeat("ab", 3))
	fmt.Println(strings.Fields("a b  c"), strings.Count("cheese", "e"))
""", imports='import (\n\t"fmt"\n\t"strings"\n)'),
    "Hello, Go World\nABC abc\ntrue true\n[a b c]\nx-y\nbba bbb\n4 ababab\n[a b c] 3\n")
check("strconv", wrap("""
	n, err := strconv.Atoi("42")
	fmt.Println(n+1, err)
	_, bad := strconv.Atoi("nope")
	fmt.Println(bad != nil)
	fmt.Println(strconv.Itoa(7) + "!")
	f, _ := strconv.ParseFloat("2.5", 64)
	fmt.Println(f * 2)
""", imports='import (\n\t"fmt"\n\t"strconv"\n)'), "43 <nil>\ntrue\n7!\n5\n")
check("math", wrap("""
	fmt.Println(math.Sqrt(16), math.Pow(2, 10), math.Abs(-3.5))
	fmt.Println(math.Floor(2.7), math.Ceil(2.1), math.Max(3, 7))
	fmt.Printf("%.4f\\n", math.Pi)
""", imports='import (\n\t"fmt"\n\t"math"\n)'),
    "4 1024 3.5\n2 3 7\n3.1416\n")
check("sort", wrap("""
	xs := []int{3, 1, 2}
	sort.Ints(xs)
	names := []string{"c", "a", "b"}
	sort.Strings(names)
	fmt.Println(xs, names)
""", imports='import (\n\t"fmt"\n\t"sort"\n)'), "[1 2 3] [a b c]\n")
check("sort.Slice", wrap("""
	people := []Person{{"c", 3}, {"a", 1}, {"b", 2}}
	sort.Slice(people, func(i, j int) bool { return people[i].Age < people[j].Age })
	for _, p := range people {
		fmt.Print(p.Name)
	}
	fmt.Println()
""", extra="""
type Person struct {
	Name string
	Age  int
}
""", imports='import (\n\t"fmt"\n\t"sort"\n)'), "abc\n")
check("strings.Builder", wrap("""
	var b strings.Builder
	for i := 0; i < 3; i++ {
		b.WriteString("ab")
	}
	fmt.Println(b.String(), b.Len())
""", imports='import (\n\t"fmt"\n\t"strings"\n)'), "ababab 6\n")

# ----------------------------------------------------------------- printf

check("printf verbs", wrap("""
	fmt.Printf("%d|%5d|%-5d|%05d|\\n", 42, 42, 42, 42)
	fmt.Printf("%s|%10s|%-10s|%q|\\n", "go", "go", "go", "go")
	fmt.Printf("%f|%.2f|%8.3f|%e|\\n", 3.14159, 3.14159, 3.14159, 1234.5)
	fmt.Printf("%t %c %x %X %o %b\\n", true, 65, 255, 255, 8, 5)
	fmt.Printf("%v %T\\n", []int{1, 2}, 3.5)
	fmt.Printf("%d%%\\n", 50)
"""), (
    "42|   42|42   |00042|\n"
    "go|        go|go        |\"go\"|\n"
    "3.141590|3.14|   3.142|1.234500e+03|\n"
    "true A ff FF 10 101\n"
    "[1 2] float64\n"
    "50%\n"
))
check("Sprintf", wrap("""
	s := fmt.Sprintf("%s has %d items", "cart", 3)
	fmt.Println(s, len(s))
"""), "cart has 3 items 16\n")

# ------------------------------------------------------------------ input

check("reading a line", wrap("""
	reader := bufio.NewScanner(os.Stdin)
	reader.Scan()
	name := reader.Text()
	fmt.Println("hello,", name)
""", imports='import (\n\t"bufio"\n\t"fmt"\n\t"os"\n)'), "hello, Ada\n", stdin="Ada\n")
check("fmt.Scan", wrap("""
	var a, b int
	fmt.Scan(&a, &b)
	fmt.Println(a + b)
"""), "7\n", stdin="3 4\n")
check("reading many lines", wrap("""
	scanner := bufio.NewScanner(os.Stdin)
	total := 0
	for scanner.Scan() {
		n, err := strconv.Atoi(scanner.Text())
		if err == nil {
			total += n
		}
	}
	fmt.Println("total", total)
""", imports='import (\n\t"bufio"\n\t"fmt"\n\t"os"\n\t"strconv"\n)'),
    "total 6\n", stdin="1\n2\n3\n")

# ------------------------------------------------- goroutines and channels

check("goroutine with a channel", wrap("""
	ch := make(chan string)
	go func() {
		ch <- "from the goroutine"
	}()
	fmt.Println(<-ch)
"""), "from the goroutine\n")
check("buffered channel", wrap("""
	ch := make(chan int, 3)
	for i := 1; i <= 3; i++ {
		ch <- i
	}
	close(ch)
	total := 0
	for v := range ch {
		total += v
	}
	fmt.Println(total)
"""), "6\n")
check("worker pool with a WaitGroup", wrap("""
	var wg sync.WaitGroup
	results := make(chan int, 5)
	for i := 1; i <= 5; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			results <- n * n
		}(i)
	}
	wg.Wait()
	close(results)
	total := 0
	for v := range results {
		total += v
	}
	fmt.Println(total)
""", imports='import (\n\t"fmt"\n\t"sync"\n)'), "55\n")
check("select", wrap("""
	a := make(chan string, 1)
	a <- "first"
	select {
	case v := <-a:
		fmt.Println(v)
	default:
		fmt.Println("nothing ready")
	}
"""), "first\n")
check("mutex", wrap("""
	var mu sync.Mutex
	var wg sync.WaitGroup
	count := 0
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			mu.Lock()
			count++
			mu.Unlock()
		}()
	}
	wg.Wait()
	fmt.Println(count)
""", imports='import (\n\t"fmt"\n\t"sync"\n)'), "50\n")

# ------------------------------------------------------- bigger programs

check("fizzbuzz", wrap("""
	for i := 1; i <= 15; i++ {
		switch {
		case i%15 == 0:
			fmt.Println("FizzBuzz")
		case i%3 == 0:
			fmt.Println("Fizz")
		case i%5 == 0:
			fmt.Println("Buzz")
		default:
			fmt.Println(i)
		}
	}
"""), "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz\n")
check("prime sieve", wrap("""
	limit := 30
	sieve := make([]bool, limit+1)
	primes := []int{}
	for n := 2; n <= limit; n++ {
		if !sieve[n] {
			primes = append(primes, n)
			for m := n * n; m <= limit; m += n {
				sieve[m] = true
			}
		}
	}
	fmt.Println(primes)
"""), "[2 3 5 7 11 13 17 19 23 29]\n")
check("string reversal by rune", wrap("""
	runes := []rune("hello")
	for i, j := 0, len(runes)-1; i < j; i, j = i+1, j-1 {
		runes[i], runes[j] = runes[j], runes[i]
	}
	fmt.Println(string(runes))
"""), "olleh\n")
check("linked list", wrap("""
	var head *Node
	for i := 3; i >= 1; i-- {
		head = &Node{Value: i, Next: head}
	}
	for n := head; n != nil; n = n.Next {
		fmt.Print(n.Value, " ")
	}
	fmt.Println()
""", extra="""
type Node struct {
	Value int
	Next  *Node
}
"""), "1 2 3 \n")
check("binary search", wrap("""
	xs := []int{1, 3, 5, 7, 9, 11}
	fmt.Println(find(xs, 7), find(xs, 8))
""", extra="""
func find(xs []int, wanted int) int {
	low, high := 0, len(xs)-1
	for low <= high {
		mid := (low + high) / 2
		switch {
		case xs[mid] == wanted:
			return mid
		case xs[mid] < wanted:
			low = mid + 1
		default:
			high = mid - 1
		}
	}
	return -1
}
"""), "3 -1\n")
check("bank account with methods and errors", wrap("""
	acct := &Account{Balance: 100}
	if err := acct.Withdraw(30); err != nil {
		fmt.Println(err)
	}
	if err := acct.Withdraw(200); err != nil {
		fmt.Println("error:", err)
	}
	fmt.Println(acct.Balance)
""", extra="""
type Account struct {
	Balance int
}

func (a *Account) Withdraw(amount int) error {
	if amount > a.Balance {
		return errors.New("insufficient funds")
	}
	a.Balance -= amount
	return nil
}
""", imports='import (\n\t"errors"\n\t"fmt"\n)'), "error: insufficient funds\n70\n")
check("range over a string counts runes", wrap("""
	count := 0
	for range "héllo" {
		count++
	}
	fmt.Println(count, len("héllo"))
"""), "5 6\n")

# ------------------------------------------------------------------ errors

check_error("undefined variable", wrap("\tfmt.Println(missing)"), "undefined")
check_error("syntax error", wrap("\tfmt.Println(1 +"), "line")
check_error("index out of range", wrap("\txs := []int{1}\n\tfmt.Println(xs[5])"),
            "index out of range")
check_error("divide by zero", wrap("\tn := 0\n\tfmt.Println(1 / n)"), "divide by zero")
check_error("nil map field", wrap("\tvar p *Point\n\tfmt.Println(p.X)",
                                  extra="type Point struct {\n\tX int\n}\n"),
            "nil pointer")
check_error("unrecovered panic", wrap('\tpanic("stop")'), "stop")
check_error("no main", 'package main\n\nimport "fmt"\n\nfunc other() { fmt.Println(1) }\n',
            "no main")


# Found by PyCmdTeach's Go course in 2.8.0.
check("a missing map key reads as the value type's zero", """
package main

import "fmt"

func main() {
	m := map[string][]int{}
	m["a"] = append(m["a"], 1)
	n := make(map[string]string)
	fmt.Println(m["a"], len(n["x"]))
}
""", "[1] 0\n")

def run_one(source, stdin_text):
    out = io.StringIO()
    code = go_interp.run_source(source, stdout=out, stdin=io.StringIO(stdin_text))
    return out.getvalue(), code


def main() -> int:
    failures = 0

    for name, source, expected, stdin_text in CASES:
        try:
            got, _ = run_one(source, stdin_text)
        except (GoError, LangSyntaxError) as error:
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
        except (GoError, LangSyntaxError) as error:
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
