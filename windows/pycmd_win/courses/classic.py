"""Fortran, Pascal, COBOL, D and Nim - compiled languages old and new."""

from pycmd_teach import Course, T, U


def _f(body: str, decls: str = "") -> str:
    """A Fortran program around some statements."""
    lines = ["program main", "  implicit none"]
    lines += ["  " + l for l in decls.split("\n") if l]
    lines += ["  " + l if l else "" for l in body.split("\n")]
    lines.append("end program main")
    return "\n".join(lines)


FORTRAN = Course(
    "fortran", "Fortran", "The first high-level language, still running weather models.",
    ".f90", "text",
    [
        U("First steps", "Free-form Fortran 90 and later."),
        T("print", "`print *,` writes values with default formatting.",
          _f("print *, 'hello'"), "hello"),
        T("Declarations", "Every name is declared. `implicit none` makes that a rule.",
          _f("n = 5\nprint *, n * n", "integer :: n"), "25"),
        T("Integer division", "Two integers divide into an integer.",
          _f("print *, 7 / 2, mod(7, 2)"), "3 1"),
        T("Reals", "A decimal point makes a real number.",
          _f("print '(F4.1)', 7.0 / 2.0"), "3.5"),
        T("Powers", "`**` raises to a power.",
          _f("print *, 2 ** 10"), "1024"),
        T("Formatted output", "`I5` is an integer five wide; `A` is text.",
          _f("print '(A, I3)', 'n=', 42"), "n= 42"),
        T("parameter", "A named constant.",
          _f("print *, max_n * 2", "integer, parameter :: max_n = 3"), "6"),
        T("Comments", "`!` to the end of the line.",
          _f("! a note\nprint *, 'ok'"), "ok"),
        T("Logicals", "`.true.` and `.false.`, printed as T and F.",
          _f("print *, 3 > 2"), "T"),

        U("Decisions and loops"),
        T("if then", "`if (...) then`, closed with `end if`.",
          _f("n = 4\nif (mod(n, 2) == 0) then\n  print *, 'even'\nelse\n"
             "  print *, 'odd'\nend if", "integer :: n"), "even"),
        T("One-line if", "For a single statement.",
          _f("n = 9\nif (n > 5) print *, 'big'", "integer :: n"), "big"),
        T("Logical operators", "`.and.`, `.or.`, `.not.`.",
          _f("print *, .not. (.true. .and. .false.)"), "T"),
        T("select case", "Picks a branch by value or range.",
          _f("n = 15\nselect case (n)\ncase (1:9)\n  print *, 'small'\n"
             "case (10:99)\n  print *, 'medium'\ncase default\n  print *, 'big'\n"
             "end select", "integer :: n"), "medium"),
        T("do loops", "`do i = start, end`.",
          _f("do i = 1, 3\n  write (*, '(I1)', advance='no') i\nend do\nprint *, ''",
             "integer :: i"), "123"),
        T("Steps", "A third number is the step.",
          _f("do i = 10, 0, -5\n  print *, i\nend do", "integer :: i"), "10\n5\n0"),
        T("exit and cycle", "Leave the loop, or go round again.",
          _f("do i = 1, 10\n  if (i == 2) cycle\n  if (i == 4) exit\n  print *, i\nend do",
             "integer :: i"), "1\n3"),
        T("do while", "Loops while the test holds.",
          _f("n = 3\ndo while (n > 0)\n  print *, n\n  n = n - 1\nend do", "integer :: n"),
          "3\n2\n1"),

        U("Arrays"),
        T("Arrays", "Indexed from 1 by default.",
          _f("a = [10, 20, 30]\nprint *, a(2)", "integer :: a(3)"), "20"),
        T("Whole-array arithmetic", "Operations apply to every element.",
          _f("a = [1, 2, 3]\nprint *, a * 10", "integer :: a(3)"), "10 20 30"),
        T("sum and maxval", "Built-in reductions.",
          _f("a = [4, 9, 2]\nprint *, sum(a), maxval(a)", "integer :: a(3)"), "15 9"),
        T("size", "How many elements.",
          _f("print *, size(a)", "integer :: a(7)"), "7"),
        T("Slices", "`a(2:3)` is part of an array.",
          _f("a = [1, 2, 3, 4]\nprint *, a(2:3)", "integer :: a(4)"), "2 3"),
        T("Implied do", "A loop inside an array constructor.",
          _f("a = [(i * i, i = 1, 4)]\nprint *, a", "integer :: a(4), i"), "1 4 9 16"),
        T("where", "Masked assignment.",
          _f("a = [1, -2, 3]\nwhere (a < 0) a = 0\nprint *, a", "integer :: a(3)"),
          "1 0 3"),
        T("Two dimensions", "Rows and columns.",
          _f("m = reshape([1, 2, 3, 4], [2, 2])\nprint *, m(2, 1)", "integer :: m(2, 2)"),
          "2"),
        T("Allocatable arrays", "Sized at run time.",
          _f("allocate(a(5))\na = 1\nprint *, sum(a)\ndeallocate(a)",
             "integer, allocatable :: a(:)"), "5"),

        U("Procedures and text"),
        T("Functions", "After `contains`, inside the program.",
          "program main\n  implicit none\n  print *, square(9)\ncontains\n"
          "  integer function square(x)\n    integer, intent(in) :: x\n"
          "    square = x * x\n  end function square\nend program main", "81"),
        T("Subroutines", "Called with `call`; they can change their arguments.",
          "program main\n  implicit none\n  integer :: n\n  n = 1\n  call bump(n)\n"
          "  print *, n\ncontains\n  subroutine bump(k)\n"
          "    integer, intent(inout) :: k\n    k = k + 10\n  end subroutine bump\n"
          "end program main", "11"),
        T("Recursion", "Say `recursive` to allow it.",
          "program main\n  implicit none\n  print *, fact(5)\ncontains\n"
          "  recursive integer function fact(n) result(r)\n"
          "    integer, intent(in) :: n\n    if (n == 0) then\n      r = 1\n"
          "    else\n      r = n * fact(n - 1)\n    end if\n  end function fact\n"
          "end program main", "120"),
        T("Strings", "Fixed length; `trim` drops trailing spaces.",
          _f("s = 'py'\nprint *, trim(s) // 'cmd'", "character(len=10) :: s"), "pycmd"),
        T("len_trim", "Length without trailing spaces.",
          _f("s = 'pycmd'\nprint *, len_trim(s)", "character(len=20) :: s"), "5"),
        T("index", "Where one string is in another.",
          _f("print *, index('pycmd', 'c')"), "3"),
        T("Intrinsic maths", "sqrt, abs, sin, exp, and more.",
          _f("print '(F4.1)', sqrt(144.0)"), "12.0"),
        T("Derived types", "Fortran's records.",
          "program main\n  implicit none\n  type point\n    integer :: x, y\n"
          "  end type point\n  type(point) :: p\n  p = point(3, 4)\n"
          "  print *, p%x * p%y\nend program main", "12"),
    ],
)

PASCAL = Course(
    "pascal", "Pascal", "Designed to teach structured programming. Free Pascal compiles it.",
    ".pas", "text",
    [
        U("First steps"),
        T("A program", "`begin ... end.` - with a full stop at the very end.",
          "program Hello;\nbegin\n  writeln('hello');\nend.", "hello"),
        T("write and writeln", "`write` stays on the line.",
          "program P;\nbegin\n  write('a');\n  writeln('b');\nend.", "ab"),
        T("Variables", "Declared in a `var` section before `begin`.",
          "program P;\nvar\n  n: integer;\nbegin\n  n := 5;\n  writeln(n * n);\nend.", "25"),
        T(":= assigns", "`=` compares; `:=` assigns.",
          "program P;\nvar\n  n: integer;\nbegin\n  n := 1;\n  n := n + 4;\n"
          "  writeln(n);\nend.", "5"),
        T("div and mod", "Whole-number division has its own words.",
          "program P;\nbegin\n  writeln(7 div 2, ' ', 7 mod 2);\nend.", "3 1"),
        T("Real division", "`/` always gives a real.",
          "program P;\nbegin\n  writeln(7 / 2 :0:1);\nend.", "3.5"),
        T("Formatting widths", "`:width:decimals` after a value.",
          "program P;\nbegin\n  writeln(3.14159 :0:2);\nend.", "3.14"),
        T("Constants", "A `const` section.",
          "program P;\nconst\n  Max = 3;\nbegin\n  writeln(Max * 2);\nend.", "6"),
        T("Comments", "`{ }` or `(* *)` or `//`.",
          "program P;\nbegin\n  { a note }\n  writeln('ok');\nend.", "ok"),
        T("Booleans", "`true` and `false`, printed in upper case.",
          "program P;\nbegin\n  writeln(3 > 2);\nend.", "TRUE"),

        U("Decisions and loops"),
        T("if then else", "No semicolon before `else`.",
          "program P;\nvar\n  n: integer;\nbegin\n  n := 4;\n  if n mod 2 = 0 then\n"
          "    writeln('even')\n  else\n    writeln('odd');\nend.", "even"),
        T("Compound statements", "`begin ... end` groups several statements.",
          "program P;\nbegin\n  if true then\n  begin\n    writeln('one');\n"
          "    writeln('two');\n  end;\nend.", "one\ntwo"),
        T("case", "Branches by value.",
          "program P;\nvar\n  n: integer;\nbegin\n  n := 2;\n  case n of\n"
          "    1: writeln('one');\n    2: writeln('two');\n  else\n    writeln('many');\n"
          "  end;\nend.", "two"),
        T("for to", "Counts up, one at a time.",
          "program P;\nvar\n  i: integer;\nbegin\n  for i := 1 to 3 do\n    write(i);\n"
          "  writeln;\nend.", "123"),
        T("for downto", "Counts down.",
          "program P;\nvar\n  i: integer;\nbegin\n  for i := 3 downto 1 do\n    write(i);\n"
          "  writeln;\nend.", "321"),
        T("while", "Tests first.",
          "program P;\nvar\n  n: integer;\nbegin\n  n := 3;\n  while n > 0 do\n  begin\n"
          "    write(n);\n    n := n - 1;\n  end;\n  writeln;\nend.", "321"),
        T("repeat until", "Tests last, so it always runs once.",
          "program P;\nvar\n  n: integer;\nbegin\n  n := 0;\n  repeat\n    n := n + 1;\n"
          "  until n >= 3;\n  writeln(n);\nend.", "3"),
        T("and, or, not", "Bracket the comparisons: `and` binds tightly.",
          "program P;\nbegin\n  writeln((1 < 2) and not (2 > 3));\nend.", "TRUE"),

        U("Procedures and functions"),
        T("Procedures", "Do something; return nothing.",
          "program P;\n\nprocedure Greet(name: string);\nbegin\n"
          "  writeln('hi ', name);\nend;\n\nbegin\n  Greet('Ada');\nend.", "hi Ada"),
        T("Functions", "Assign to `Result` (or the function's name).",
          "program P;\n\nfunction Square(x: integer): integer;\nbegin\n"
          "  Square := x * x;\nend;\n\nbegin\n  writeln(Square(9));\nend.", "81"),
        T("var parameters", "Pass by reference: the procedure can change it.",
          "program P;\nvar\n  n: integer;\n\nprocedure Bump(var k: integer);\nbegin\n"
          "  k := k + 10;\nend;\n\nbegin\n  n := 1;\n  Bump(n);\n  writeln(n);\nend.", "11"),
        T("Recursion", "Functions may call themselves.",
          "program P;\n\nfunction Fact(n: integer): integer;\nbegin\n"
          "  if n = 0 then Fact := 1\n  else Fact := n * Fact(n - 1);\nend;\n\n"
          "begin\n  writeln(Fact(5));\nend.", "120"),

        U("Data"),
        T("Arrays", "With the index range in the type.",
          "program P;\nvar\n  a: array[1..3] of integer;\nbegin\n  a[1] := 10;\n"
          "  a[2] := 20;\n  a[3] := 30;\n  writeln(a[2]);\nend.", "20"),
        T("Looping over an array", "With `low` and `high`.",
          "program P;\nvar\n  a: array[1..3] of integer = (4, 5, 6);\n  i, s: integer;\n"
          "begin\n  s := 0;\n  for i := low(a) to high(a) do\n    s := s + a[i];\n"
          "  writeln(s);\nend.", "15"),
        T("Strings", "`length`, `copy`, `pos`, `upcase`.",
          "program P;\nbegin\n  writeln(length('pycmd'));\nend.", "5"),
        T("Joining strings", "`+` concatenates.",
          "program P;\nbegin\n  writeln('py' + 'cmd');\nend.", "pycmd"),
        T("copy", "Part of a string: from a position, for a length.",
          "program P;\nbegin\n  writeln(copy('pycmd', 3, 3));\nend.", "cmd"),
        T("pos", "Where a substring starts; 0 if it is not there.",
          "program P;\nbegin\n  writeln(pos('c', 'pycmd'));\nend.", "3"),
        T("Characters", "`ord` and `chr` convert to and from codes.",
          "program P;\nbegin\n  writeln(ord('A'), ' ', chr(66));\nend.", "65 B"),
        T("Records", "Fields grouped under one name. Pascal ignores case, so a "
          "variable cannot share the program's name.",
          "program Shapes;\ntype\n  TPoint = record\n    x, y: integer;\n  end;\nvar\n"
          "  pt: TPoint;\nbegin\n  pt.x := 3;\n  pt.y := 4;\n  writeln(pt.x * pt.y);\nend.",
          "12"),
        T("Enumerations", "Named values in order.",
          "program P;\ntype\n  TDay = (Mon, Tue, Wed);\nbegin\n  writeln(ord(Wed));\nend.",
          "2"),
        T("Sets", "A set of small values, with `in`.",
          "program P;\nbegin\n  writeln(3 in [1..5]);\nend.", "TRUE"),
        T("Converting", "`IntToStr` and `StrToInt` come from SysUtils.",
          "program P;\nuses SysUtils;\nbegin\n  writeln(StrToInt('41') + 1);\nend.", "42"),
    ],
)

COBOL = Course(
    "cobol", "COBOL", "The language of banks and payroll. GnuCOBOL, free format.",
    ".cob", "text",
    [
        U("First steps", "Divisions, a little ceremony, and DISPLAY."),
        T("Hello", "IDENTIFICATION names the program; PROCEDURE does the work.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. HELLO.\nPROCEDURE DIVISION.\n"
          '    DISPLAY "hello".\n    STOP RUN.', "hello"),
        T("Variables", "Declared in WORKING-STORAGE with a PICTURE.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 N PIC 99 VALUE 42.\nPROCEDURE DIVISION.\n"
          "    DISPLAY N.\n    STOP RUN.", "42"),
        T("PIC 9 is digits", "Leading zeros fill the width.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 N PIC 9(4) VALUE 7.\nPROCEDURE DIVISION.\n"
          "    DISPLAY N.\n    STOP RUN.", "0007"),
        T("PIC X is text", "A fixed number of characters.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          'WORKING-STORAGE SECTION.\n01 W PIC X(5) VALUE "pycmd".\nPROCEDURE DIVISION.\n'
          "    DISPLAY W.\n    STOP RUN.", "pycmd"),
        T("Several items", "DISPLAY joins them with nothing between.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nPROCEDURE DIVISION.\n"
          '    DISPLAY "a" "b" "c".\n    STOP RUN.', "abc"),
        T("Comments", "`*>` to the end of the line.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nPROCEDURE DIVISION.\n"
          '    *> a note\n    DISPLAY "ok".\n    STOP RUN.', "ok"),

        U("Arithmetic"),
        T("ADD", "Adds into a variable.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 N PIC 99 VALUE 5.\nPROCEDURE DIVISION.\n"
          "    ADD 10 TO N.\n    DISPLAY N.\n    STOP RUN.", "15"),
        T("SUBTRACT", "Takes away from a variable.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 N PIC 99 VALUE 50.\nPROCEDURE DIVISION.\n"
          "    SUBTRACT 8 FROM N.\n    DISPLAY N.\n    STOP RUN.", "42"),
        T("MULTIPLY", "BY, and GIVING for the result.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 R PIC 999.\nPROCEDURE DIVISION.\n"
          "    MULTIPLY 6 BY 7 GIVING R.\n    DISPLAY R.\n    STOP RUN.", "042"),
        T("DIVIDE with REMAINDER", "Quotient and what is left.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 Q PIC 9.\n01 R PIC 9.\nPROCEDURE DIVISION.\n"
          "    DIVIDE 7 BY 2 GIVING Q REMAINDER R.\n    DISPLAY Q R.\n    STOP RUN.", "31"),
        T("COMPUTE", "Ordinary formulas.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 R PIC 9(4).\nPROCEDURE DIVISION.\n"
          "    COMPUTE R = 2 ** 10.\n    DISPLAY R.\n    STOP RUN.", "1024"),
        T("Decimals", "A V in the picture marks the implied point.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 R PIC 9V9.\n01 E PIC 9.9.\nPROCEDURE DIVISION.\n"
          "    COMPUTE R = 7 / 2.\n    MOVE R TO E.\n    DISPLAY E.\n    STOP RUN.", "3.5"),
        T("Edited pictures", "Z suppresses leading zeros for printing.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 N PIC 9(4) VALUE 42.\n01 E PIC ZZZ9.\n"
          "PROCEDURE DIVISION.\n    MOVE N TO E.\n    DISPLAY E.\n    STOP RUN.", "42"),
        T("MOVE", "Copies a value, converting to the target's picture.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 A PIC 99 VALUE 12.\n01 B PIC 9(4).\n"
          "PROCEDURE DIVISION.\n    MOVE A TO B.\n    DISPLAY B.\n    STOP RUN.", "0012"),

        U("Decisions and loops"),
        T("IF", "Ends with END-IF.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 N PIC 99 VALUE 4.\nPROCEDURE DIVISION.\n"
          '    IF N > 3\n        DISPLAY "big"\n    ELSE\n        DISPLAY "small"\n'
          "    END-IF.\n    STOP RUN.", "big"),
        T("EVALUATE", "COBOL's switch.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 N PIC 9 VALUE 2.\nPROCEDURE DIVISION.\n"
          '    EVALUATE N\n        WHEN 1 DISPLAY "one"\n        WHEN 2 DISPLAY "two"\n'
          '        WHEN OTHER DISPLAY "many"\n    END-EVALUATE.\n    STOP RUN.', "two"),
        T("Condition names", "Level 88 gives a value a name you can test.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 CODE-X PIC 9 VALUE 1.\n    88 IS-OK VALUE 1.\n"
          'PROCEDURE DIVISION.\n    IF IS-OK DISPLAY "fine" END-IF.\n    STOP RUN.', "fine"),
        T("PERFORM TIMES", "Repeats a block.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nPROCEDURE DIVISION.\n"
          '    PERFORM 3 TIMES\n        DISPLAY "hi"\n    END-PERFORM.\n    STOP RUN.',
          "hi\nhi\nhi"),
        T("PERFORM VARYING", "A counting loop.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 I PIC 9.\nPROCEDURE DIVISION.\n"
          "    PERFORM VARYING I FROM 1 BY 1 UNTIL I > 3\n        DISPLAY I\n"
          "    END-PERFORM.\n    STOP RUN.", "1\n2\n3"),
        T("PERFORM UNTIL", "Loops until the condition is true.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 N PIC 9 VALUE 3.\nPROCEDURE DIVISION.\n"
          "    PERFORM UNTIL N = 0\n        DISPLAY N\n        SUBTRACT 1 FROM N\n"
          "    END-PERFORM.\n    STOP RUN.", "3\n2\n1"),
        T("Paragraphs", "Named blocks you PERFORM like a procedure.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nPROCEDURE DIVISION.\nMAIN-PARA.\n"
          "    PERFORM GREET.\n    STOP RUN.\nGREET.\n    DISPLAY \"hello\".", "hello"),

        U("Records and text"),
        T("Group items", "A level 01 record with fields under it.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 PERSON.\n    05 P-NAME PIC X(3) VALUE \"Ada\".\n"
          "    05 P-AGE PIC 99 VALUE 36.\nPROCEDURE DIVISION.\n    DISPLAY P-NAME.\n"
          "    STOP RUN.", "Ada"),
        T("A whole group displays as text", "Its fields, side by side.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 PERSON.\n    05 P-NAME PIC X(3) VALUE \"Ada\".\n"
          "    05 P-AGE PIC 99 VALUE 36.\nPROCEDURE DIVISION.\n    DISPLAY PERSON.\n"
          "    STOP RUN.", "Ada36"),
        T("Tables", "OCCURS makes an array, indexed from 1.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 T.\n    05 V PIC 99 OCCURS 3 TIMES.\n"
          "PROCEDURE DIVISION.\n    MOVE 10 TO V(1).\n    MOVE 20 TO V(2).\n"
          "    DISPLAY V(2).\n    STOP RUN.", "20"),
        T("STRING", "Joins pieces into a field.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 OUT-S PIC X(5).\nPROCEDURE DIVISION.\n"
          '    STRING "py" "cmd" DELIMITED BY SIZE INTO OUT-S.\n    DISPLAY OUT-S.\n'
          "    STOP RUN.", "pycmd"),
        T("FUNCTION UPPER-CASE", "Intrinsic functions do the common jobs.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nPROCEDURE DIVISION.\n"
          '    DISPLAY FUNCTION UPPER-CASE("pycmd").\n    STOP RUN.', "PYCMD"),
        T("FUNCTION LENGTH", "The length of a field.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nPROCEDURE DIVISION.\n"
          '    DISPLAY FUNCTION LENGTH("hello").\n    STOP RUN.', "5"),
        T("INSPECT TALLYING", "Counts characters in a field.",
          "IDENTIFICATION DIVISION.\nPROGRAM-ID. P.\nDATA DIVISION.\n"
          "WORKING-STORAGE SECTION.\n01 W PIC X(6) VALUE \"banana\".\n01 C PIC 9.\n"
          "PROCEDURE DIVISION.\n    MOVE 0 TO C.\n    INSPECT W TALLYING C FOR ALL \"a\".\n"
          "    DISPLAY C.\n    STOP RUN.", "3"),
    ],
)

D = Course(
    "d", "D", "C's speed with modern conveniences: ranges, slices, templates.",
    ".d", "text",
    [
        U("First steps"),
        T("writeln", "From std.stdio.",
          'import std.stdio;\n\nvoid main() {\n    writeln("hello");\n}', "hello"),
        T("Several values", "writeln prints them side by side.",
          'import std.stdio;\n\nvoid main() {\n    writeln("n=", 5);\n}', "n=5"),
        T("auto", "Type inference.",
          "import std.stdio;\n\nvoid main() {\n    auto n = 5;\n    writeln(n * n);\n}", "25"),
        T("Integer division", "Ints divide into ints.",
          "import std.stdio;\n\nvoid main() {\n    writeln(7 / 2, \" \", 7 % 2);\n}", "3 1"),
        T("writefln", "printf-style formatting.",
          'import std.stdio;\n\nvoid main() {\n    writefln("%.2f", 3.14159);\n}', "3.14"),
        T("immutable", "A value that can never change.",
          "import std.stdio;\n\nvoid main() {\n    immutable n = 21;\n    writeln(n * 2);\n}",
          "42"),
        T("Comments", "`//`, `/* */`, and nesting `/+ +/`.",
          'import std.stdio;\n\nvoid main() {\n    // a note\n    writeln("ok");\n}', "ok"),

        U("Control flow"),
        T("if", "As in C: a test in brackets.",
          'import std.stdio;\n\nvoid main() {\n    int n = 4;\n    if (n % 2 == 0)\n'
          '        writeln("even");\n    else\n        writeln("odd");\n}', "even"),
        T("foreach over a range", "`a .. b` includes a, excludes b.",
          "import std.stdio;\n\nvoid main() {\n    foreach (i; 0 .. 3)\n        write(i);\n"
          "    writeln();\n}", "012"),
        T("foreach over an array", "With an index if you want one.",
          'import std.stdio;\n\nvoid main() {\n    foreach (i, c; "ab")\n'
          '        write(i, c, " ");\n    writeln();\n}', "0a 1b"),
        T("switch", "Cases may be ranges.",
          'import std.stdio;\n\nvoid main() {\n    int n = 15;\n    switch (n) {\n'
          '        case 1: .. case 9: writeln("small"); break;\n'
          '        default: writeln("big");\n    }\n}', "big"),
        T("while", "Loops while the test holds.",
          "import std.stdio;\n\nvoid main() {\n    int n = 3;\n    while (n > 0)\n"
          "        write(n--);\n    writeln();\n}", "321"),

        U("Arrays and strings"),
        T("Dynamic arrays", "`~=` appends.",
          "import std.stdio;\n\nvoid main() {\n    int[] xs = [1, 2];\n    xs ~= 3;\n"
          "    writeln(xs);\n}", "[1, 2, 3]"),
        T("length", "Arrays know how long they are.",
          "import std.stdio;\n\nvoid main() {\n    writeln([4, 5, 6].length);\n}", "3"),
        T("Slices", "`xs[1 .. 3]` is a view of part of an array.",
          "import std.stdio;\n\nvoid main() {\n    auto xs = [1, 2, 3, 4];\n"
          "    writeln(xs[1 .. 3]);\n}", "[2, 3]"),
        T("$ is the length", "Inside an index, `$` means the end.",
          "import std.stdio;\n\nvoid main() {\n    auto xs = [1, 2, 3];\n"
          "    writeln(xs[$ - 1]);\n}", "3"),
        T("Strings are arrays", "Of immutable characters.",
          'import std.stdio;\n\nvoid main() {\n    string s = "py" ~ "cmd";\n'
          "    writeln(s.length);\n}", "5"),
        T("Associative arrays", "Built in: `int[string]`.",
          'import std.stdio;\n\nvoid main() {\n    int[string] ages;\n    ages["ada"] = 36;\n'
          '    writeln(ages["ada"]);\n}', "36"),
        T("in", "Gives a pointer, or null.",
          'import std.stdio;\n\nvoid main() {\n    int[string] a = ["x": 1];\n'
          '    writeln(("y" in a) is null);\n}', "true"),

        U("Functions and ranges"),
        T("Functions", "Typed parameters and return.",
          "import std.stdio;\n\nint square(int x) {\n    return x * x;\n}\n\n"
          "void main() {\n    writeln(square(9));\n}", "81"),
        T("UFCS", "`x.f()` calls `f(x)` - so any function chains.",
          "import std.stdio;\n\nint square(int x) {\n    return x * x;\n}\n\n"
          "void main() {\n    writeln(9.square);\n}", "81"),
        T("Lambdas", "`x => x * 2`.",
          "import std.stdio;\n\nvoid main() {\n    auto twice = (int x) => x * 2;\n"
          "    writeln(twice(21));\n}", "42"),
        T("map and filter", "From std.algorithm, lazy.",
          "import std.stdio, std.algorithm;\n\nvoid main() {\n"
          "    [1, 2, 3, 4].filter!(x => x % 2 == 0)\n        .map!(x => x * 10)\n"
          "        .writeln;\n}", "[20, 40]"),
        T("sum", "Adds a range up.",
          "import std.stdio, std.algorithm, std.range;\n\nvoid main() {\n"
          "    writeln(iota(1, 11).sum);\n}", "55"),
        T("sort", "In place, on a random-access range.",
          "import std.stdio, std.algorithm;\n\nvoid main() {\n    auto xs = [3, 1, 2];\n"
          "    xs.sort();\n    writeln(xs);\n}", "[1, 2, 3]"),
        T("Templates", "A function for any type with `(T)`.",
          "import std.stdio;\n\nT biggest(T)(T a, T b) {\n    return a > b ? a : b;\n}\n\n"
          "void main() {\n    writeln(biggest(3, 7));\n}", "7"),
        T("Structs", "Value types with fields and methods.",
          "import std.stdio;\n\nstruct P {\n    int x, y;\n    int area() { return x * y; }\n}\n\n"
          "void main() {\n    writeln(P(3, 4).area);\n}", "12"),
        T("Compile-time evaluation", "`enum` forces a value at compile time.",
          "import std.stdio;\n\nint fact(int n) { return n <= 1 ? 1 : n * fact(n - 1); }\n\n"
          "void main() {\n    enum f = fact(5);\n    writeln(f);\n}", "120"),
        T("Exceptions", "try and catch.",
          'import std.stdio, std.conv;\n\nvoid main() {\n    try {\n        to!int("x");\n'
          '    } catch (ConvException e) {\n        writeln("not a number");\n    }\n}',
          "not a number"),
    ],
)

NIM = Course(
    "nim", "Nim", "Python-like syntax, compiled to C. Fast and friendly.",
    ".nim", "text",
    [
        U("First steps"),
        T("echo", "Prints its arguments and a newline.",
          'echo "hello"', "hello"),
        T("Several arguments", "Joined with nothing between.",
          'echo "n=", 5', "n=5"),
        T("let", "A name that does not change.",
          "let n = 5\necho n * n", "25"),
        T("var", "A name that can.",
          "var n = 1\nn += 4\necho n", "5"),
        T("const", "Worked out at compile time.",
          "const answer = 6 * 7\necho answer", "42"),
        T("div and mod", "`/` gives a float; div and mod do not.",
          "echo 7 div 2, \" \", 7 mod 2\necho 7 / 2", "3 1\n3.5"),
        T("Strings join with &", "The ampersand concatenates.",
          'echo "py" & "cmd"', "pycmd"),
        T("Formatting", "`strformat` gives `fmt` strings.",
          'import std/strformat\n\nlet pi = 3.14159\necho fmt"{pi:.2f}"', "3.14"),
        T("Comments", "`#` to the end of the line.",
          '# a note\necho "ok"', "ok"),

        U("Control flow"),
        T("if", "Indentation marks the blocks, as in Python.",
          'let n = 4\nif n mod 2 == 0:\n  echo "even"\nelse:\n  echo "odd"', "even"),
        T("if as an expression", "It gives a value.",
          'let n = 9\necho(if n > 5: "big" else: "small")', "big"),
        T("case", "Branches by value or range.",
          'let n = 15\ncase n\nof 1..9: echo "small"\nof 10..99: echo "medium"\n'
          'else: echo "big"', "medium"),
        T("for over a range", "`..` includes both ends.",
          'for i in 1..3:\n  stdout.write i\necho ""', "123"),
        T("..<", "Up to, but not including.",
          'for i in 0..<3:\n  stdout.write i\necho ""', "012"),
        T("while", "Loops while the test holds.",
          'var n = 3\nwhile n > 0:\n  stdout.write n\n  dec n\necho ""', "321"),

        U("Procedures"),
        T("proc", "A procedure, with typed parameters.",
          "proc square(x: int): int =\n  x * x\n\necho square(9)", "81"),
        T("result", "Every proc with a return type has `result`.",
          "proc total(n: int): int =\n  for i in 1..n:\n    result += i\n\necho total(10)",
          "55"),
        T("Default parameters", "Used when left out.",
          'proc hi(who = "you"): string =\n  "hi " & who\n\necho hi()', "hi you"),
        T("Method call syntax", "`x.f(y)` is `f(x, y)`.",
          "proc double(x: int): int = x * 2\n\necho 21.double", "42"),
        T("var parameters", "Can be changed by the proc.",
          "proc bump(k: var int) =\n  k += 10\n\nvar n = 1\nbump(n)\necho n", "11"),
        T("Recursion", "Procs may call themselves.",
          "proc fact(n: int): int =\n  if n == 0: 1 else: n * fact(n - 1)\n\necho fact(5)",
          "120"),
        T("Generics", "`[T]` works for any type.",
          "proc biggest[T](a, b: T): T =\n  if a > b: a else: b\n\necho biggest(3, 7)", "7"),

        U("Collections"),
        T("seq", "A growable array, written `@[...]`.",
          "var xs = @[1, 2]\nxs.add 3\necho xs", "@[1, 2, 3]"),
        T("len", "How many elements a seq has.",
          "echo @[4, 5, 6].len", "3"),
        T("Indexing", "From zero; `^1` is the last.",
          "let xs = @[10, 20, 30]\necho xs[0], \" \", xs[^1]", "10 30"),
        T("Arrays", "Fixed size, part of the type.",
          "let a: array[3, int] = [1, 2, 3]\necho a.len", "3"),
        T("map and filter", "From std/sequtils.",
          "import std/sequtils\n\necho @[1, 2, 3, 4].filterIt(it mod 2 == 0).mapIt(it * 10)",
          "@[20, 40]"),
        T("foldl", "Folds a sequence.",
          "import std/sequtils\n\necho @[1, 2, 3, 4].foldl(a + b)", "10"),
        T("Tables", "Dictionaries, from std/tables.",
          'import std/tables\n\nvar ages = {"ada": 36}.toTable\necho ages["ada"]', "36"),
        T("Sets", "Sets of small values are built in.",
          "let s = {1, 3, 5}\necho 3 in s", "true"),
        T("Tuples", "Named or not.",
          'let p = (name: "Ada", age: 36)\necho p.name', "Ada"),
        T("Strings", "From std/strutils: toUpperAscii, split, join...",
          'import std/strutils\n\necho "pycmd".toUpperAscii', "PYCMD"),
        T("split and join", "Into a seq and back.",
          'import std/strutils\n\necho "a,b,c".split(",").join("-")', "a-b-c"),

        U("Types"),
        T("Objects", "Records with named fields.",
          "type P = object\n  x, y: int\n\nlet p = P(x: 3, y: 4)\necho p.x * p.y", "12"),
        T("Enums", "Named values, printable.",
          "type Color = enum\n  red, green\n\necho green", "green"),
        T("Option", "From std/options: some(x) or none.",
          "import std/options\n\nlet n = none(int)\necho n.isSome", "false"),
        T("Exceptions", "try and except.",
          'import std/strutils\n\ntry:\n  discard parseInt("x")\nexcept ValueError:\n'
          '  echo "not a number"', "not a number"),
        T("discard", "Throwing away a result has to be said out loud.",
          "proc f(): int = 42\n\ndiscard f()\necho \"done\"", "done"),
    ],
)

COURSES = [FORTRAN, PASCAL, COBOL, D, NIM]
