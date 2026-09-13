"""Runs real C programs through the on-device interpreter.

Each case is C source plus the exact output it must produce. If the
interpreter cannot run ordinary C, this is where it shows.

    python3.13 tools/test_c.py
"""

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app", "src", "main", "python"))

from pycmd_langs import c_interp  # noqa: E402
from pycmd_langs.c_lexer import CSyntaxError  # noqa: E402

FAILURES = []
PASSED = 0


def run(source, stdin_text=""):
    out = io.StringIO()
    code = c_interp.run_source(source, stdout=out, stdin=io.StringIO(stdin_text))
    return out.getvalue(), code


def check(name, source, expected, stdin_text="", expect_code=None):
    global PASSED
    try:
        output, code = run(source, stdin_text)
    except (CSyntaxError, c_interp.CRuntimeError) as exc:
        print(f"  FAIL  {name}\n        error: {exc}")
        FAILURES.append(name)
        return
    except Exception as exc:  # noqa: BLE001
        import traceback

        print(f"  FAIL  {name}\n        crashed: {type(exc).__name__}: {exc}")
        traceback.print_exc(limit=3)
        FAILURES.append(name)
        return

    if output != expected:
        print(f"  FAIL  {name}\n        expected {expected!r}\n        got      {output!r}")
        FAILURES.append(name)
        return
    if expect_code is not None and code != expect_code:
        print(f"  FAIL  {name}: exit code {code}, expected {expect_code}")
        FAILURES.append(name)
        return
    print(f"  PASS  {name}")
    PASSED += 1


def check_error(name, source, fragment):
    """The interpreter must reject this, with a message that says why."""
    global PASSED
    try:
        run(source)
    except (CSyntaxError, c_interp.CRuntimeError) as exc:
        if fragment.lower() in str(exc).lower():
            print(f"  PASS  {name}")
            PASSED += 1
        else:
            print(f"  FAIL  {name}\n        message was {str(exc)!r}, wanted {fragment!r}")
            FAILURES.append(name)
        return
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL  {name}: wrong exception type {type(exc).__name__}: {exc}")
        FAILURES.append(name)
        return
    print(f"  FAIL  {name}: it was accepted, but should have been rejected")
    FAILURES.append(name)


print("\n== hello and printf ==")
check("hello world", '''
#include <stdio.h>
int main() {
    printf("Hello, World!\\n");
    return 0;
}
''', "Hello, World!\n", expect_code=0)

check("printf conversions", '''
#include <stdio.h>
int main() {
    printf("%d %s %c %.2f %x\\n", 42, "text", 'A', 3.14159, 255);
    return 0;
}
''', "42 text A 3.14 ff\n")

check("printf width and alignment", '''
#include <stdio.h>
int main() {
    printf("[%5d][%-5d][%05d]\\n", 42, 42, 42);
    return 0;
}
''', "[   42][42   ][00042]\n")

check("puts and putchar", '''
#include <stdio.h>
int main() {
    puts("line");
    putchar('h');
    putchar('i');
    putchar('\\n');
    return 0;
}
''', "line\nhi\n")

print("\n== arithmetic ==")
check("integer division truncates toward zero", '''
#include <stdio.h>
int main() {
    printf("%d %d %d %d\\n", 7 / 2, -7 / 2, 7 % 3, -7 % 3);
    return 0;
}
''', "3 -3 1 -1\n")

check("operator precedence", '''
#include <stdio.h>
int main() {
    printf("%d %d %d\\n", 2 + 3 * 4, (2 + 3) * 4, 10 - 2 - 3);
    return 0;
}
''', "14 20 5\n")

check("bitwise and shifts", '''
#include <stdio.h>
int main() {
    printf("%d %d %d %d %d\\n", 6 & 3, 6 | 3, 6 ^ 3, 1 << 4, 32 >> 2);
    return 0;
}
''', "2 7 5 16 8\n")

check("float maths", '''
#include <stdio.h>
int main() {
    double a = 10.0;
    printf("%.3f %.1f\\n", a / 3.0, 2.5 * 4);
    return 0;
}
''', "3.333 10.0\n")

print("\n== control flow ==")
check("if else chain", '''
#include <stdio.h>
int main() {
    for (int i = 0; i < 5; i++) {
        if (i == 0) printf("zero ");
        else if (i % 2 == 0) printf("even ");
        else printf("odd ");
    }
    printf("\\n");
    return 0;
}
''', "zero odd even odd even \n")

check("while and do-while", '''
#include <stdio.h>
int main() {
    int i = 0;
    while (i < 3) { printf("%d", i); i++; }
    int j = 10;
    do { printf("[%d]", j); j++; } while (j < 10);
    printf("\\n");
    return 0;
}
''', "012[10]\n")

check("break and continue", '''
#include <stdio.h>
int main() {
    for (int i = 0; i < 10; i++) {
        if (i == 3) continue;
        if (i == 6) break;
        printf("%d", i);
    }
    printf("\\n");
    return 0;
}
''', "01245\n")

check("switch with fall-through", '''
#include <stdio.h>
int main() {
    for (int i = 0; i < 4; i++) {
        switch (i) {
            case 0: printf("a");
            case 1: printf("b"); break;
            case 2: printf("c"); break;
            default: printf("d");
        }
    }
    printf("\\n");
    return 0;
}
''', "abbcd\n")

check("nested loops", '''
#include <stdio.h>
int main() {
    for (int i = 1; i <= 3; i++) {
        for (int j = 1; j <= 3; j++) printf("%d", i * j);
        printf("|");
    }
    printf("\\n");
    return 0;
}
''', "123|246|369|\n")

print("\n== functions ==")
check("recursion: factorial", '''
#include <stdio.h>
int fact(int n) { return n <= 1 ? 1 : n * fact(n - 1); }
int main() {
    printf("%d %d\\n", fact(5), fact(10));
    return 0;
}
''', "120 3628800\n")

check("recursion: fibonacci", '''
#include <stdio.h>
int fib(int n) {
    if (n < 2) return n;
    return fib(n - 1) + fib(n - 2);
}
int main() {
    for (int i = 0; i < 10; i++) printf("%d ", fib(i));
    printf("\\n");
    return 0;
}
''', "0 1 1 2 3 5 8 13 21 34 \n")

check("mutual recursion", '''
#include <stdio.h>
int is_odd(int n);
int is_even(int n) { return n == 0 ? 1 : is_odd(n - 1); }
int is_odd(int n) { return n == 0 ? 0 : is_even(n - 1); }
int main() {
    printf("%d %d\\n", is_even(10), is_odd(7));
    return 0;
}
''', "1 1\n")

check("void function and globals", '''
#include <stdio.h>
int counter = 0;
void bump(void) { counter++; }
int main() {
    bump(); bump(); bump();
    printf("%d\\n", counter);
    return 0;
}
''', "3\n")

print("\n== arrays ==")
check("array sum", '''
#include <stdio.h>
int main() {
    int a[5] = {1, 2, 3, 4, 5};
    int total = 0;
    for (int i = 0; i < 5; i++) total += a[i];
    printf("%d\\n", total);
    return 0;
}
''', "15\n")

check("bubble sort", '''
#include <stdio.h>
int main() {
    int a[6] = {5, 2, 9, 1, 7, 3};
    for (int i = 0; i < 6; i++)
        for (int j = 0; j < 5 - i; j++)
            if (a[j] > a[j + 1]) { int t = a[j]; a[j] = a[j + 1]; a[j + 1] = t; }
    for (int i = 0; i < 6; i++) printf("%d ", a[i]);
    printf("\\n");
    return 0;
}
''', "1 2 3 5 7 9 \n")

check("array passed to a function", '''
#include <stdio.h>
int sum(int *values, int n) {
    int total = 0;
    for (int i = 0; i < n; i++) total += values[i];
    return total;
}
int main() {
    int a[4] = {10, 20, 30, 40};
    printf("%d\\n", sum(a, 4));
    return 0;
}
''', "100\n")

print("\n== pointers ==")
check("basic pointer read and write", '''
#include <stdio.h>
int main() {
    int x = 5;
    int *p = &x;
    *p = 42;
    printf("%d %d\\n", x, *p);
    return 0;
}
''', "42 42\n")

check("swap through pointers", '''
#include <stdio.h>
void swap(int *a, int *b) { int t = *a; *a = *b; *b = t; }
int main() {
    int x = 1, y = 2;
    swap(&x, &y);
    printf("%d %d\\n", x, y);
    return 0;
}
''', "2 1\n")

check("pointer arithmetic walks an array", '''
#include <stdio.h>
int main() {
    int a[5] = {1, 2, 3, 4, 5};
    int *p = a;
    printf("%d %d %d\\n", *p, *(p + 2), p[4]);
    p++;
    printf("%d\\n", *p);
    return 0;
}
''', "1 3 5\n2\n")

check("walking a string with a pointer", '''
#include <stdio.h>
int main() {
    char *s = "abc";
    while (*s) { putchar(*s); s++; }
    printf("\\n");
    return 0;
}
''', "abc\n")

check("out-parameter", '''
#include <stdio.h>
void divide(int a, int b, int *q, int *r) { *q = a / b; *r = a % b; }
int main() {
    int q, r;
    divide(17, 5, &q, &r);
    printf("%d remainder %d\\n", q, r);
    return 0;
}
''', "3 remainder 2\n")

print("\n== strings ==")
check("string library", '''
#include <stdio.h>
#include <string.h>
int main() {
    char buf[64];
    strcpy(buf, "Hello");
    strcat(buf, ", World");
    printf("%s (%d)\\n", buf, (int)strlen(buf));
    printf("%d %d\\n", strcmp("a", "a"), strcmp("a", "b"));
    return 0;
}
''', "Hello, World (12)\n0 -1\n")

check("char array initialised from a literal", '''
#include <stdio.h>
int main() {
    char word[] = "cat";
    printf("%s %c %d\\n", word, word[0], word[2]);
    return 0;
}
''', "cat c 116\n")

check("building a string by hand", '''
#include <stdio.h>
int main() {
    char out[8];
    for (int i = 0; i < 5; i++) out[i] = 'a' + i;
    out[5] = 0;
    printf("%s\\n", out);
    return 0;
}
''', "abcde\n")

print("\n== structs ==")
check("struct fields", '''
#include <stdio.h>
struct Point { int x; int y; };
int main() {
    struct Point p;
    p.x = 3;
    p.y = 4;
    printf("%d,%d\\n", p.x, p.y);
    return 0;
}
''', "3,4\n")

check("struct initialiser and copy", '''
#include <stdio.h>
struct Point { int x; int y; };
int main() {
    struct Point a = {1, 2};
    struct Point b = a;
    b.x = 99;
    printf("%d %d\\n", a.x, b.x);
    return 0;
}
''', "1 99\n")

check("pointer to struct with ->", '''
#include <stdio.h>
struct Point { int x; int y; };
void move(struct Point *p) { p->x += 10; p->y += 10; }
int main() {
    struct Point p = {1, 2};
    move(&p);
    printf("%d %d\\n", p.x, p.y);
    return 0;
}
''', "11 12\n")

check("array of structs", '''
#include <stdio.h>
struct Item { int id; int qty; };
int main() {
    struct Item items[3];
    for (int i = 0; i < 3; i++) { items[i].id = i; items[i].qty = i * 10; }
    for (int i = 0; i < 3; i++) printf("%d:%d ", items[i].id, items[i].qty);
    printf("\\n");
    return 0;
}
''', "0:0 1:10 2:20 \n")

print("\n== malloc ==")
check("malloc, use, free", '''
#include <stdio.h>
#include <stdlib.h>
int main() {
    int *a = (int *)malloc(5 * sizeof(int));
    for (int i = 0; i < 5; i++) a[i] = i * i;
    for (int i = 0; i < 5; i++) printf("%d ", a[i]);
    free(a);
    printf("\\n");
    return 0;
}
''', "0 1 4 9 16 \n")

check("NULL comparison", '''
#include <stdio.h>
#include <stdlib.h>
int main() {
    int *p = NULL;
    if (p == 0) printf("null\\n");
    p = (int *)malloc(sizeof(int));
    if (p != 0) printf("allocated\\n");
    return 0;
}
''', "null\nallocated\n")

print("\n== typedef, enum, preprocessor ==")
check("typedef struct", '''
#include <stdio.h>
typedef struct { int w; int h; } Box;
int main() {
    Box b;
    b.w = 3; b.h = 4;
    printf("%d\\n", b.w * b.h);
    return 0;
}
''', "12\n")

check("enum constants", '''
#include <stdio.h>
enum Colour { RED, GREEN, BLUE };
int main() {
    printf("%d %d %d\\n", RED, GREEN, BLUE);
    return 0;
}
''', "0 1 2\n")

check("#define constant", '''
#include <stdio.h>
#define SIZE 4
int main() {
    int a[SIZE];
    for (int i = 0; i < SIZE; i++) a[i] = i;
    printf("%d %d\\n", SIZE, a[3]);
    return 0;
}
''', "4 3\n")

print("\n== stdin ==")
check("scanf reads numbers", '''
#include <stdio.h>
int main() {
    int a, b;
    scanf("%d %d", &a, &b);
    printf("%d\\n", a + b);
    return 0;
}
''', "30\n", stdin_text="10 20\n")

check("scanf across separate lines", '''
#include <stdio.h>
int main() {
    int n;
    int total = 0;
    scanf("%d", &n);
    for (int i = 0; i < n; i++) { int v; scanf("%d", &v); total += v; }
    printf("%d\\n", total);
    return 0;
}
''', "60\n", stdin_text="3\n10\n20\n30\n")

check("scanf reads a string", '''
#include <stdio.h>
int main() {
    char name[32];
    scanf("%s", name);
    printf("hi %s\\n", name);
    return 0;
}
''', "hi Ada\n", stdin_text="Ada\n")

print("\n== maths and exit code ==")
check("math library", '''
#include <stdio.h>
#include <math.h>
int main() {
    printf("%.2f %.2f %.0f\\n", sqrt(16.0), pow(2.0, 10.0), floor(3.7));
    return 0;
}
''', "4.00 1024.00 3\n")

check("exit code from main", '''
int main() { return 3; }
''', "", expect_code=3)

check("exit() stops immediately", '''
#include <stdio.h>
#include <stdlib.h>
int main() {
    printf("before\\n");
    exit(2);
    printf("after\\n");
    return 0;
}
''', "before\n", expect_code=2)

print("\n== a real program ==")
check("prime sieve", '''
#include <stdio.h>
#define N 30
int main() {
    int sieve[N + 1];
    for (int i = 0; i <= N; i++) sieve[i] = 1;
    sieve[0] = 0; sieve[1] = 0;
    for (int i = 2; i * i <= N; i++)
        if (sieve[i])
            for (int j = i * i; j <= N; j += i) sieve[j] = 0;
    for (int i = 2; i <= N; i++) if (sieve[i]) printf("%d ", i);
    printf("\\n");
    return 0;
}
''', "2 3 5 7 11 13 17 19 23 29 \n")

check("string reversal in place", '''
#include <stdio.h>
#include <string.h>
void reverse(char *s) {
    int n = strlen(s);
    for (int i = 0; i < n / 2; i++) {
        char t = s[i];
        s[i] = s[n - 1 - i];
        s[n - 1 - i] = t;
    }
}
int main() {
    char text[] = "interpreter";
    reverse(text);
    printf("%s\\n", text);
    return 0;
}
''', "reterpretni\n")

check("linked list built with malloc", '''
#include <stdio.h>
#include <stdlib.h>
struct Node { int value; struct Node *next; };
int main() {
    struct Node *head = NULL;
    for (int i = 3; i >= 1; i--) {
        struct Node *n = (struct Node *)malloc(sizeof(struct Node));
        n->value = i;
        n->next = head;
        head = n;
    }
    struct Node *p = head;
    while (p != NULL) { printf("%d ", p->value); p = p->next; }
    printf("\\n");
    return 0;
}
''', "1 2 3 \n")

check("binary search", '''
#include <stdio.h>
int bsearch_int(int *a, int n, int target) {
    int lo = 0, hi = n - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (a[mid] == target) return mid;
        if (a[mid] < target) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1;
}
int main() {
    int a[8] = {1, 3, 5, 7, 9, 11, 13, 15};
    printf("%d %d %d\\n", bsearch_int(a, 8, 7), bsearch_int(a, 8, 1), bsearch_int(a, 8, 4));
    return 0;
}
''', "3 0 -1\n")

print("\n== arrays with more than one dimension ==")
# A C array is one flat run of memory and `grid[r][c]` is arithmetic on it.
# Decaying `grid` to a pointer used to forget how wide a row was, so the
# second `[` had nothing to work with and said grid was not an array at all.
check("a grid is indexed by row and column", """
#include <stdio.h>
int main(void) {
    int grid[3][4] = {{1,2,3,4},{5,6,7,8},{9,10,11,12}};
    printf("%d %d %d", grid[0][0], grid[1][2], grid[2][3]);
    return 0;
}
""", "1 7 12")

check("writing to one cell leaves the others alone", """
#include <stdio.h>
int main(void) {
    int grid[2][3];
    for (int r = 0; r < 2; r++) for (int c = 0; c < 3; c++) grid[r][c] = r * 10 + c;
    printf("%d %d %d", grid[0][0], grid[1][1], grid[1][2]);
    return 0;
}
""", "0 11 12")

check("a row can be handed to a function", """
#include <stdio.h>
int total(int *row, int n) { int t = 0; for (int i = 0; i < n; i++) t += row[i]; return t; }
int main(void) {
    int grid[2][3] = {{1,2,3},{4,5,6}};
    printf("%d %d", total(grid[0], 3), total(grid[1], 3));
    return 0;
}
""", "6 15")

check("three dimensions work the same way", """
#include <stdio.h>
int main(void) {
    int cube[2][2][2] = {{{1,2},{3,4}},{{5,6},{7,8}}};
    printf("%d %d", cube[0][1][0], cube[1][0][1]);
    return 0;
}
""", "3 6")

check("a row of text is copied in, not pointed at", """
#include <stdio.h>
int main(void) {
    char names[3][8] = {"Ada", "Grace"};
    printf("%s %s %d", names[0], names[1], (int)names[2][0]);
    return 0;
}
""", "Ada Grace 0")

check("a short initialiser leaves the rest zero", """
#include <stdio.h>
int main(void) {
    int grid[3][2] = {{1,2}};
    printf("%d %d %d", grid[0][1], grid[1][0], grid[2][1]);
    return 0;
}
""", "2 0 0")

check("an ordinary one-dimensional array is unchanged", """
#include <stdio.h>
int main(void) {
    int flat[4] = {1,2,3,4};
    int *p = flat;
    printf("%d %d", flat[3], p[2]);
    return 0;
}
""", "4 3")

check_error("too many rows is still refused", """
int main(void) { int grid[1][2] = {{1,2},{3,4}}; return grid[0][0]; }
""", "too many initialisers")

print("\n== errors are reported, not crashed on ==")
check_error("missing semicolon", 'int main() { int x = 1 return 0; }', "expected")
check_error("unknown variable", '''
#include <stdio.h>
int main() { printf("%d", nope); return 0; }
''', "not declared")
check_error("division by zero", '''
int main() { int z = 0; return 5 / z; }
''', "division by zero")
check_error("NULL dereference", '''
int main() { int *p = 0; return *p; }
''', "null")
check_error("unterminated string", 'int main() { printf("oops); }', "unterminated")
check_error("undefined function", 'int main() { return mystery(1); }', "not defined")
check_error("infinite recursion is caught", '''
int f(int n) { return f(n + 1); }
int main() { return f(0); }
''', "too deep")

print()
if FAILURES:
    print(f"{len(FAILURES)} of {PASSED + len(FAILURES)} FAILED: {', '.join(FAILURES)}")
    sys.exit(1)
print(f"all {PASSED} C checks passed")
