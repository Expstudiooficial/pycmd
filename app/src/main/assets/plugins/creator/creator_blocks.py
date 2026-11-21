"""The blocks, and the thing that turns a stack of them into a file.

This is the whole of Creator that is worth testing, and none of it touches the
app: a catalogue of blocks, and a compiler that walks a tree of them and
writes out source. Feed it a project, get back text. That is the entire
contract, which is why it lives in its own module rather than inside the
plugin's `main.py` - a laptop can run it, and `tools/test_creator.py` does.

## What a block is

A dict, and a small one. `open` is the line it writes, with `@slot@` where a
value goes; `wrap` means it can hold other blocks, and `close` is the line
that comes after them - `}` in JavaScript, `</div>` in HTML, nothing at all in
Python, where the indentation is the closing.

`@slot@` rather than `{slot}` for one reason that decides it: three of the
five languages here use braces as syntax. `if (x) {` and `body { color: red }`
would both need escaping under `str.format`, every time, and one missed escape
is a block that crashes the compiler instead of writing a line. `@` is not
syntax in any of them. A literal `@` is written `@@`, which CSS at-rules and
Python decorators both need.

## What it is not

Not a parser. Blocks go one way - into source - and a file cannot be read back
into blocks. That is a deliberate line: a round trip would mean writing five
parsers and keeping them right, and the thing people want from a block editor
is the first direction, where the syntax errors live.

Not a sandbox, either. A slot takes what somebody types, and what they type
ends up in a file they then run. That is the same trust the editor has: this
is a tool for writing your own code, not for running anybody else's.
"""

from __future__ import annotations

import re

__all__ = [
    "LANGUAGES",
    "BLOCKS",
    "catalogue",
    "preview_of",
    "compile_project",
    "block",
    "MAX_BLOCKS",
    "MAX_DEPTH",
]

# What a project can be written in. `indent` is one step of nesting, and it is
# the language's own convention rather than a setting: Python code indented two
# spaces looks wrong to every Python programmer alive.
#
# `runs` is whether the phone can execute a file in this language - six of the
# ten can, on the interpreters the app carries. It is written out here rather
# than asked of `pycmd_langs`, because this module deliberately knows nothing
# about the app and a laptop has to be able to import it. `tools/test_creator.py`
# does know about both, and checks that these flags say what the registry says,
# so the duplication cannot quietly become a lie.
LANGUAGES = [
    {"id": "python", "name": "Python", "extension": ".py", "indent": "    ",
     "about": "Runs in the app. Everything the console can do.", "runs": True},
    {"id": "javascript", "name": "JavaScript", "extension": ".js", "indent": "  ",
     "about": "Runs in a page, or on its own in the Servers tab.", "runs": True},
    {"id": "html", "name": "HTML", "extension": ".html", "indent": "  ",
     "about": "A page. Serve the folder and it is a website.", "runs": False},
    {"id": "css", "name": "CSS", "extension": ".css", "indent": "  ",
     "about": "How the page looks.", "runs": False},
    {"id": "markdown", "name": "Markdown", "extension": ".md", "indent": "",
     "about": "Notes and documents. The preview renders it.", "runs": False},
    {"id": "c", "name": "C", "extension": ".c", "indent": "    ",
     "about": "Runs in the app, on the C interpreter it carries.", "runs": True},
    {"id": "go", "name": "Go", "extension": ".go", "indent": "\t",
     "about": "Runs in the app. Tabs, because gofmt uses tabs.", "runs": True},
    {"id": "rust", "name": "Rust", "extension": ".rs", "indent": "    ",
     "about": "Runs in the app, on the Rust interpreter it carries.", "runs": True},
    {"id": "shell", "name": "Shell", "extension": ".sh", "indent": "    ",
     "about": "POSIX sh, which is what Android gives you.", "runs": True},
    {"id": "json", "name": "JSON", "extension": ".json", "indent": "  ",
     "about": "Settings and data. The commas are put in for you.", "runs": False},
]

LANGUAGE_IDS = [row["id"] for row in LANGUAGES]

PLACEHOLDER = re.compile(r"@([a-z_][a-z0-9_]*)@")

# A slot holds one line's worth of value. Anything longer is somebody pasting
# a program into a hole meant for a name.
MAX_VALUE = 400

# A project you can still scroll, and a nesting depth past which nobody knows
# what they are looking at.
MAX_BLOCKS = 2000
MAX_DEPTH = 24


def _slot(name: str, label: str, kind: str = "text", default: str = "",
          options=None) -> dict:
    """One hole in a block.

    `kind` decides how the panel asks for it and how it is written out:

    * `text` - an expression, written exactly as typed. The escape hatch:
      whatever goes in comes out.
    * `string` - a piece of text, made safe for where it lands. Python and
      JavaScript get quotes round it and their escapes; HTML gets its entities,
      so a quote in an attribute cannot end the attribute; CSS loses braces,
      which cannot appear in a declaration and can only end the rule early.
    * `inline` - text that is going *inside* something already quoted, like an
      f-string or a template literal. Escaped, but not quoted again.
    * `number` - a number field; a blank one is 0.
    * `name` - a variable, function or property name. Trimmed and used as
      typed: `data["k"]` is a perfectly good thing to append to, and refusing
      it would be a rule that only got in the way.
    * `choice` - one of `options`, and nothing else.
    """
    return {
        "name": name,
        "label": label,
        "kind": kind,
        "default": default,
        "options": list(options or []),
    }


def _block(bid: str, cat: str, label: str, open_: str, slots=(), close: str = "",
           wrap: bool = False, empty: str = "", about: str = "",
           chain_after=()) -> dict:
    """One block.

    `chain_after` names the blocks this one continues, and it exists because
    of a bug that shipped for four versions: `if` and `else` wrote

        if (x > 1) {
          ...
        }
        } else {
          ...
        }

    which is not JavaScript. The `if` block closed itself and then `else`
    supplied a second brace. Python got away with it because its `else:` has
    no closing line at all - every braced language did not.

    A block that chains tells the compiler so, and the compiler leaves the
    closing line off the block before it, because the chaining block's own
    first line - `} else {` - is that closing brace. It also means a stray
    `else` with no `if` above it can be *said*, rather than silently writing
    a brace that closes nothing.
    """
    return {
        "id": bid,
        "cat": cat,
        "label": label,
        "open": open_,
        "close": close,
        "wrap": wrap,
        "empty": empty,
        "about": about,
        "chain": list(chain_after),
        "slots": list(slots),
    }


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

PYTHON = [
    # -- Basics ------------------------------------------------------------
    _block("py.print", "Basics", "print text", "print(@text@)",
           [_slot("text", "text", "string", "Hello")]),
    _block("py.print_value", "Basics", "print a value", "print(@value@)",
           [_slot("value", "value", "text", "total")]),
    _block("py.print_two", "Basics", "print two things", "print(@a@, @b@)",
           [_slot("a", "first", "text", "name"), _slot("b", "second", "text", "score")]),
    _block("py.print_labelled", "Basics", "print a label and a value",
           "print(@label@, @value@)",
           [_slot("label", "label", "string", "Total:"), _slot("value", "value", "text", "total")]),
    _block("py.print_f", "Basics", "print a sentence with values in it",
           'print(f"@text@")',
           [_slot("text", "text, with {name} in it", "inline",
                  "Hello {name}, you have {score}")]),
    _block("py.comment", "Basics", "a note to yourself", "# @text@",
           [_slot("text", "note", "text", "what this part does")]),
    _block("py.blank", "Basics", "an empty line", ""),
    _block("py.pass", "Basics", "do nothing", "pass"),
    _block("py.input", "Basics", "ask for text", "@name@ = input(@prompt@)",
           [_slot("name", "keep it in", "name", "answer"),
            _slot("prompt", "question", "string", "What is your name? ")]),
    _block("py.input_number", "Basics", "ask for a number",
           "@name@ = int(input(@prompt@))",
           [_slot("name", "keep it in", "name", "age"),
            _slot("prompt", "question", "string", "How old are you? ")]),
    _block("py.stop", "Basics", "stop the program", "raise SystemExit"),

    # -- Variables ---------------------------------------------------------
    _block("py.set", "Variables", "set to a value", "@name@ = @value@",
           [_slot("name", "name", "name", "total"), _slot("value", "value", "text", "0")]),
    _block("py.set_text", "Variables", "set to text", "@name@ = @text@",
           [_slot("name", "name", "name", "title"), _slot("text", "text", "string", "Hello")]),
    _block("py.set_number", "Variables", "set to a number", "@name@ = @number@",
           [_slot("name", "name", "name", "score"), _slot("number", "number", "number", "0")]),
    _block("py.set_bool", "Variables", "set to true or false", "@name@ = @value@",
           [_slot("name", "name", "name", "ready"),
            _slot("value", "value", "choice", "True", ["True", "False"])]),
    _block("py.set_none", "Variables", "set to nothing", "@name@ = None",
           [_slot("name", "name", "name", "found")]),
    _block("py.set_list", "Variables", "set to a list", "@name@ = [@items@]",
           [_slot("name", "name", "name", "items"),
            _slot("items", "items, comma separated", "text", '"a", "b", "c"')]),
    _block("py.set_dict", "Variables", "set to a dictionary", "@name@ = {@pairs@}",
           [_slot("name", "name", "name", "person"),
            _slot("pairs", "key: value pairs", "text", '"name": "Ada", "age": 36')]),
    _block("py.increase", "Variables", "add to a number", "@name@ += @amount@",
           [_slot("name", "name", "name", "score"), _slot("amount", "by", "number", "1")]),
    _block("py.decrease", "Variables", "take away from a number", "@name@ -= @amount@",
           [_slot("name", "name", "name", "lives"), _slot("amount", "by", "number", "1")]),
    _block("py.multiply_by", "Variables", "multiply a number", "@name@ *= @amount@",
           [_slot("name", "name", "name", "total"), _slot("amount", "by", "number", "2")]),
    _block("py.delete", "Variables", "forget a variable", "del @name@",
           [_slot("name", "name", "name", "temp")]),
    _block("py.global", "Variables", "use the outer variable", "global @name@",
           [_slot("name", "name", "name", "total")]),

    # -- Maths -------------------------------------------------------------
    _block("py.add", "Maths", "add", "@name@ = @a@ + @b@",
           [_slot("name", "keep it in", "name", "total"),
            _slot("a", "first", "text", "a"), _slot("b", "second", "text", "b")]),
    _block("py.subtract", "Maths", "subtract", "@name@ = @a@ - @b@",
           [_slot("name", "keep it in", "name", "left"),
            _slot("a", "from", "text", "a"), _slot("b", "take away", "text", "b")]),
    _block("py.multiply", "Maths", "multiply", "@name@ = @a@ * @b@",
           [_slot("name", "keep it in", "name", "product"),
            _slot("a", "first", "text", "a"), _slot("b", "second", "text", "b")]),
    _block("py.divide", "Maths", "divide", "@name@ = @a@ / @b@",
           [_slot("name", "keep it in", "name", "share"),
            _slot("a", "divide", "text", "a"), _slot("b", "by", "text", "b")]),
    _block("py.whole_divide", "Maths", "divide, whole numbers only",
           "@name@ = @a@ // @b@",
           [_slot("name", "keep it in", "name", "boxes"),
            _slot("a", "divide", "text", "items"), _slot("b", "by", "text", "10")]),
    _block("py.remainder", "Maths", "remainder", "@name@ = @a@ % @b@",
           [_slot("name", "keep it in", "name", "left"),
            _slot("a", "divide", "text", "n"), _slot("b", "by", "text", "2")]),
    _block("py.power", "Maths", "to the power of", "@name@ = @a@ ** @b@",
           [_slot("name", "keep it in", "name", "big"),
            _slot("a", "number", "text", "2"), _slot("b", "power", "text", "10")]),
    _block("py.maths", "Maths", "any sum", "@name@ = @a@ @op@ @b@",
           [_slot("name", "keep it in", "name", "answer"),
            _slot("a", "first", "text", "a"),
            _slot("op", "operator", "choice", "+", ["+", "-", "*", "/", "//", "%", "**"]),
            _slot("b", "second", "text", "b")]),
    _block("py.round", "Maths", "round a number", "@name@ = round(@value@, @places@)",
           [_slot("name", "keep it in", "name", "rounded"),
            _slot("value", "number", "text", "value"), _slot("places", "decimals", "number", "2")]),
    _block("py.absolute", "Maths", "size without the sign", "@name@ = abs(@value@)",
           [_slot("name", "keep it in", "name", "size"), _slot("value", "number", "text", "value")]),
    _block("py.to_int", "Maths", "as a whole number", "@name@ = int(@value@)",
           [_slot("name", "keep it in", "name", "count"), _slot("value", "value", "text", "text")]),
    _block("py.to_float", "Maths", "as a decimal", "@name@ = float(@value@)",
           [_slot("name", "keep it in", "name", "price"), _slot("value", "value", "text", "text")]),
    _block("py.smallest", "Maths", "the smaller of two", "@name@ = min(@a@, @b@)",
           [_slot("name", "keep it in", "name", "lowest"),
            _slot("a", "first", "text", "a"), _slot("b", "second", "text", "b")]),
    _block("py.largest", "Maths", "the larger of two", "@name@ = max(@a@, @b@)",
           [_slot("name", "keep it in", "name", "highest"),
            _slot("a", "first", "text", "a"), _slot("b", "second", "text", "b")]),
    _block("py.sum", "Maths", "add up a list", "@name@ = sum(@list@)",
           [_slot("name", "keep it in", "name", "total"), _slot("list", "list", "text", "scores")]),
    _block("py.average", "Maths", "the average of a list",
           "@name@ = sum(@list@) / len(@list@)",
           [_slot("name", "keep it in", "name", "average"),
            _slot("list", "list", "text", "scores")]),

    # -- Text --------------------------------------------------------------
    _block("py.join_text", "Text", "join two pieces of text", "@name@ = @a@ + @b@",
           [_slot("name", "keep it in", "name", "greeting"),
            _slot("a", "first", "text", '"Hello "'), _slot("b", "second", "text", "name")]),
    _block("py.format", "Text", "build a sentence", '@name@ = f"@text@"',
           [_slot("name", "keep it in", "name", "line"),
            _slot("text", "text, with {name} in it", "inline", "{name} scored {score}")]),
    _block("py.upper", "Text", "in capitals", "@name@ = @value@.upper()",
           [_slot("name", "keep it in", "name", "shout"), _slot("value", "text", "text", "line")]),
    _block("py.lower", "Text", "in lower case", "@name@ = @value@.lower()",
           [_slot("name", "keep it in", "name", "quiet"), _slot("value", "text", "text", "line")]),
    _block("py.title_case", "Text", "with each word capitalised",
           "@name@ = @value@.title()",
           [_slot("name", "keep it in", "name", "titled"), _slot("value", "text", "text", "line")]),
    _block("py.strip", "Text", "without the spaces around it",
           "@name@ = @value@.strip()",
           [_slot("name", "keep it in", "name", "clean"), _slot("value", "text", "text", "line")]),
    _block("py.replace", "Text", "with something swapped",
           "@name@ = @value@.replace(@old@, @new@)",
           [_slot("name", "keep it in", "name", "fixed"), _slot("value", "text", "text", "line"),
            _slot("old", "find", "string", "cat"), _slot("new", "replace with", "string", "dog")]),
    _block("py.split", "Text", "split into a list",
           "@name@ = @value@.split(@separator@)",
           [_slot("name", "keep it in", "name", "parts"), _slot("value", "text", "text", "line"),
            _slot("separator", "split on", "string", ",")]),
    _block("py.join_list", "Text", "join a list into text",
           "@name@ = @separator@.join(@list@)",
           [_slot("name", "keep it in", "name", "line"),
            _slot("separator", "between them", "string", ", "),
            _slot("list", "list", "text", "words")]),
    _block("py.length", "Text", "how long it is", "@name@ = len(@value@)",
           [_slot("name", "keep it in", "name", "count"), _slot("value", "text or list", "text", "line")]),
    _block("py.contains", "Text", "does it contain", "@name@ = @needle@ in @haystack@",
           [_slot("name", "keep it in", "name", "found"),
            _slot("needle", "look for", "string", "cat"),
            _slot("haystack", "in", "text", "line")]),
    _block("py.starts_with", "Text", "does it start with",
           "@name@ = @value@.startswith(@prefix@)",
           [_slot("name", "keep it in", "name", "starts"), _slot("value", "text", "text", "line"),
            _slot("prefix", "starts with", "string", "http")]),
    _block("py.ends_with", "Text", "does it end with",
           "@name@ = @value@.endswith(@suffix@)",
           [_slot("name", "keep it in", "name", "ends"), _slot("value", "text", "text", "name"),
            _slot("suffix", "ends with", "string", ".py")]),
    _block("py.find", "Text", "where something is",
           "@name@ = @value@.find(@needle@)",
           [_slot("name", "keep it in", "name", "at"), _slot("value", "text", "text", "line"),
            _slot("needle", "look for", "string", "=")]),
    _block("py.slice", "Text", "a piece of it", "@name@ = @value@[@start@:@end@]",
           [_slot("name", "keep it in", "name", "piece"), _slot("value", "text or list", "text", "line"),
            _slot("start", "from", "number", "0"), _slot("end", "to", "number", "5")]),
    _block("py.to_text", "Text", "as text", "@name@ = str(@value@)",
           [_slot("name", "keep it in", "name", "text"), _slot("value", "value", "text", "number")]),

    # -- Lists -------------------------------------------------------------
    _block("py.new_list", "Lists", "a new empty list", "@name@ = []",
           [_slot("name", "name", "name", "items")]),
    _block("py.append", "Lists", "add to the end", "@list@.append(@value@)",
           [_slot("list", "list", "name", "items"), _slot("value", "value", "text", "item")]),
    _block("py.insert", "Lists", "put in at a position",
           "@list@.insert(@index@, @value@)",
           [_slot("list", "list", "name", "items"), _slot("index", "at", "number", "0"),
            _slot("value", "value", "text", "item")]),
    _block("py.remove_value", "Lists", "take one out by value",
           "@list@.remove(@value@)",
           [_slot("list", "list", "name", "items"), _slot("value", "value", "text", "item")]),
    _block("py.pop", "Lists", "take one out by position",
           "@name@ = @list@.pop(@index@)",
           [_slot("name", "keep it in", "name", "item"), _slot("list", "list", "name", "items"),
            _slot("index", "at", "number", "0")]),
    _block("py.clear_list", "Lists", "empty it", "@list@.clear()",
           [_slot("list", "list", "name", "items")]),
    _block("py.sort", "Lists", "put in order", "@list@.sort()",
           [_slot("list", "list", "name", "items")]),
    _block("py.sort_by", "Lists", "put in order by something",
           "@list@.sort(key=@key@)",
           [_slot("list", "list", "name", "people"),
            _slot("key", "sort by", "text", 'lambda row: row["age"]')]),
    _block("py.reverse", "Lists", "turn it round", "@list@.reverse()",
           [_slot("list", "list", "name", "items")]),
    _block("py.list_length", "Lists", "how many", "@name@ = len(@list@)",
           [_slot("name", "keep it in", "name", "count"), _slot("list", "list", "name", "items")]),
    _block("py.item_at", "Lists", "the item at", "@name@ = @list@[@index@]",
           [_slot("name", "keep it in", "name", "item"), _slot("list", "list", "name", "items"),
            _slot("index", "position", "number", "0")]),
    _block("py.set_item", "Lists", "replace the item at", "@list@[@index@] = @value@",
           [_slot("list", "list", "name", "items"), _slot("index", "position", "number", "0"),
            _slot("value", "value", "text", "item")]),
    _block("py.in_list", "Lists", "is it in the list", "@name@ = @value@ in @list@",
           [_slot("name", "keep it in", "name", "found"), _slot("value", "value", "text", "item"),
            _slot("list", "list", "name", "items")]),
    _block("py.index_of", "Lists", "where it is in the list",
           "@name@ = @list@.index(@value@)",
           [_slot("name", "keep it in", "name", "at"), _slot("list", "list", "name", "items"),
            _slot("value", "value", "text", "item")]),
    _block("py.count_in", "Lists", "how many times it appears",
           "@name@ = @list@.count(@value@)",
           [_slot("name", "keep it in", "name", "times"), _slot("list", "list", "name", "items"),
            _slot("value", "value", "text", "item")]),
    _block("py.comprehension", "Lists", "a list built from another",
           "@name@ = [@expression@ for @item@ in @list@]",
           [_slot("name", "keep it in", "name", "doubled"),
            _slot("expression", "each one becomes", "text", "item * 2"),
            _slot("item", "each is called", "name", "item"),
            _slot("list", "from", "name", "items")]),

    # -- Dictionaries ------------------------------------------------------
    _block("py.new_dict", "Dictionaries", "a new empty dictionary", "@name@ = {}",
           [_slot("name", "name", "name", "data")]),
    _block("py.dict_set", "Dictionaries", "set a key",
           "@dict@[@key@] = @value@",
           [_slot("dict", "dictionary", "name", "data"), _slot("key", "key", "string", "name"),
            _slot("value", "value", "text", '"Ada"')]),
    _block("py.dict_get", "Dictionaries", "read a key",
           "@name@ = @dict@.get(@key@, @fallback@)",
           [_slot("name", "keep it in", "name", "value"), _slot("dict", "dictionary", "name", "data"),
            _slot("key", "key", "string", "name"), _slot("fallback", "if missing", "text", "None")]),
    _block("py.dict_has", "Dictionaries", "does it have a key",
           "@name@ = @key@ in @dict@",
           [_slot("name", "keep it in", "name", "found"), _slot("key", "key", "string", "name"),
            _slot("dict", "dictionary", "name", "data")]),
    _block("py.dict_remove", "Dictionaries", "remove a key", "del @dict@[@key@]",
           [_slot("dict", "dictionary", "name", "data"), _slot("key", "key", "string", "name")]),
    _block("py.dict_keys", "Dictionaries", "all the keys",
           "@name@ = list(@dict@.keys())",
           [_slot("name", "keep it in", "name", "keys"), _slot("dict", "dictionary", "name", "data")]),
    _block("py.dict_values", "Dictionaries", "all the values",
           "@name@ = list(@dict@.values())",
           [_slot("name", "keep it in", "name", "values"),
            _slot("dict", "dictionary", "name", "data")]),
    _block("py.dict_items", "Dictionaries", "for every key and value",
           "for @key@, @value@ in @dict@.items():",
           [_slot("key", "key is called", "name", "key"),
            _slot("value", "value is called", "name", "value"),
            _slot("dict", "dictionary", "name", "data")],
           wrap=True, empty="pass"),
    _block("py.dict_update", "Dictionaries", "merge another in",
           "@dict@.update(@other@)",
           [_slot("dict", "dictionary", "name", "data"), _slot("other", "merge in", "text", "extra")]),
    _block("py.dict_length", "Dictionaries", "how many keys",
           "@name@ = len(@dict@)",
           [_slot("name", "keep it in", "name", "count"),
            _slot("dict", "dictionary", "name", "data")]),

    # -- Logic -------------------------------------------------------------
    _block("py.if", "Logic", "if", "if @condition@:",
           [_slot("condition", "when", "text", "score > 10")], wrap=True, empty="pass"),
    _block("py.if_equals", "Logic", "if two things are the same", "if @a@ == @b@:",
           [_slot("a", "this", "text", "answer"), _slot("b", "is", "text", '"yes"')],
           wrap=True, empty="pass"),
    _block("py.if_not_equals", "Logic", "if two things are different",
           "if @a@ != @b@:",
           [_slot("a", "this", "text", "answer"), _slot("b", "is not", "text", '"yes"')],
           wrap=True, empty="pass"),
    _block("py.if_greater", "Logic", "if bigger than", "if @a@ > @b@:",
           [_slot("a", "this", "text", "score"), _slot("b", "is bigger than", "text", "10")],
           wrap=True, empty="pass"),
    _block("py.if_less", "Logic", "if smaller than", "if @a@ < @b@:",
           [_slot("a", "this", "text", "score"), _slot("b", "is smaller than", "text", "10")],
           wrap=True, empty="pass"),
    _block("py.if_in", "Logic", "if it contains", "if @needle@ in @haystack@:",
           [_slot("needle", "this", "text", '"cat"'), _slot("haystack", "is in", "text", "line")],
           wrap=True, empty="pass"),
    _block("py.elif", "Logic", "or else if", "elif @condition@:",
           [_slot("condition", "when", "text", "score > 5")], wrap=True, empty="pass"),
    _block("py.else", "Logic", "otherwise", "else:", wrap=True, empty="pass"),
    _block("py.and", "Logic", "both are true", "@name@ = @a@ and @b@",
           [_slot("name", "keep it in", "name", "both"), _slot("a", "this", "text", "ready"),
            _slot("b", "and", "text", "willing")]),
    _block("py.or", "Logic", "either is true", "@name@ = @a@ or @b@",
           [_slot("name", "keep it in", "name", "either"), _slot("a", "this", "text", "ready"),
            _slot("b", "or", "text", "waiting")]),
    _block("py.not", "Logic", "the opposite", "@name@ = not @value@",
           [_slot("name", "keep it in", "name", "missing"), _slot("value", "of", "text", "found")]),
    _block("py.compare", "Logic", "compare two things", "@name@ = @a@ @op@ @b@",
           [_slot("name", "keep it in", "name", "result"), _slot("a", "this", "text", "a"),
            _slot("op", "compared", "choice", "==", ["==", "!=", "<", ">", "<=", ">=", "in"]),
            _slot("b", "to", "text", "b")]),

    # -- Loops -------------------------------------------------------------
    _block("py.repeat", "Loops", "repeat this many times",
           "for @var@ in range(@times@):",
           [_slot("var", "counter", "name", "i"), _slot("times", "times", "number", "10")],
           wrap=True, empty="pass"),
    _block("py.count_from", "Loops", "count from one number to another",
           "for @var@ in range(@start@, @end@):",
           [_slot("var", "counter", "name", "i"), _slot("start", "from", "number", "1"),
            _slot("end", "up to", "number", "11")],
           wrap=True, empty="pass"),
    _block("py.for_each", "Loops", "for each item in a list",
           "for @item@ in @list@:",
           [_slot("item", "each is called", "name", "item"), _slot("list", "in", "name", "items")],
           wrap=True, empty="pass"),
    _block("py.for_each_index", "Loops", "for each item, with its position",
           "for @index@, @item@ in enumerate(@list@):",
           [_slot("index", "position is called", "name", "index"),
            _slot("item", "each is called", "name", "item"),
            _slot("list", "in", "name", "items")],
           wrap=True, empty="pass"),
    _block("py.for_two", "Loops", "for each pair from two lists",
           "for @a@, @b@ in zip(@first@, @second@):",
           [_slot("a", "first is called", "name", "name"),
            _slot("b", "second is called", "name", "score"),
            _slot("first", "first list", "name", "names"),
            _slot("second", "second list", "name", "scores")],
           wrap=True, empty="pass"),
    _block("py.while", "Loops", "keep going while", "while @condition@:",
           [_slot("condition", "while", "text", "running")], wrap=True, empty="pass"),
    _block("py.forever", "Loops", "keep going forever", "while True:",
           wrap=True, empty="pass"),
    _block("py.break", "Loops", "stop the loop", "break"),
    _block("py.continue", "Loops", "skip to the next time round", "continue"),

    # -- Functions ---------------------------------------------------------
    _block("py.def", "Functions", "define a function", "def @name@(@params@):",
           [_slot("name", "called", "name", "greet"),
            _slot("params", "taking", "text", "name")],
           wrap=True, empty="pass"),
    _block("py.def_plain", "Functions", "define a function with no inputs",
           "def @name@():",
           [_slot("name", "called", "name", "main")], wrap=True, empty="pass"),
    _block("py.return", "Functions", "give an answer back", "return @value@",
           [_slot("value", "answer", "text", "result")]),
    _block("py.return_none", "Functions", "give nothing back", "return"),
    _block("py.call", "Functions", "run a function", "@name@(@args@)",
           [_slot("name", "function", "name", "greet"), _slot("args", "with", "text", '"Ada"')]),
    _block("py.call_keep", "Functions", "run a function and keep the answer",
           "@result@ = @name@(@args@)",
           [_slot("result", "keep it in", "name", "answer"),
            _slot("name", "function", "name", "greet"), _slot("args", "with", "text", '"Ada"')]),
    _block("py.lambda", "Functions", "a one-line function",
           "@name@ = lambda @params@: @expression@",
           [_slot("name", "called", "name", "double"), _slot("params", "taking", "text", "n"),
            _slot("expression", "gives back", "text", "n * 2")]),
    _block("py.main_guard", "Functions", "only when this file is run",
           'if __name__ == "__main__":', wrap=True, empty="pass"),
    _block("py.docstring", "Functions", "explain what this does",
           '"""@text@"""',
           [_slot("text", "explanation", "inline", "What this does.")]),

    # -- Files -------------------------------------------------------------
    _block("py.read_file", "Files", "read a whole file",
           "@name@ = open(@path@).read()",
           [_slot("name", "keep it in", "name", "text"),
            _slot("path", "file", "string", "notes.txt")]),
    _block("py.write_file", "Files", "write a file",
           'open(@path@, "w").write(@text@)',
           [_slot("path", "file", "string", "notes.txt"),
            _slot("text", "text", "text", "text")]),
    _block("py.append_file", "Files", "add to the end of a file",
           'open(@path@, "a").write(@text@)',
           [_slot("path", "file", "string", "log.txt"),
            _slot("text", "text", "text", 'line + "\\n"')]),
    _block("py.with_read", "Files", "open a file to read",
           "with open(@path@) as @handle@:",
           [_slot("path", "file", "string", "notes.txt"),
            _slot("handle", "called", "name", "handle")],
           wrap=True, empty="pass"),
    _block("py.with_write", "Files", "open a file to write",
           'with open(@path@, "w") as @handle@:',
           [_slot("path", "file", "string", "notes.txt"),
            _slot("handle", "called", "name", "handle")],
           wrap=True, empty="pass"),
    _block("py.for_line", "Files", "for every line in a file",
           "for @line@ in open(@path@):",
           [_slot("line", "each is called", "name", "line"),
            _slot("path", "file", "string", "notes.txt")],
           wrap=True, empty="pass"),
    _block("py.file_exists", "Files", "does a file exist",
           "@name@ = os.path.exists(@path@)",
           [_slot("name", "keep it in", "name", "there"),
            _slot("path", "file", "string", "notes.txt")]),
    _block("py.list_folder", "Files", "everything in a folder",
           "@name@ = os.listdir(@path@)",
           [_slot("name", "keep it in", "name", "names"), _slot("path", "folder", "string", ".")]),
    _block("py.make_folder", "Files", "make a folder",
           "os.makedirs(@path@, exist_ok=True)",
           [_slot("path", "folder", "string", "output")]),
    _block("py.delete_file", "Files", "delete a file", "os.remove(@path@)",
           [_slot("path", "file", "string", "temp.txt")]),

    # -- Bringing things in ------------------------------------------------
    _block("py.import", "Modules", "use a library", "import @module@",
           [_slot("module", "library", "name", "random")]),
    _block("py.from_import", "Modules", "use part of a library",
           "from @module@ import @names@",
           [_slot("module", "library", "name", "datetime"),
            _slot("names", "the parts", "text", "datetime")]),
    _block("py.import_as", "Modules", "use a library under a shorter name",
           "import @module@ as @alias@",
           [_slot("module", "library", "name", "numpy"), _slot("alias", "as", "name", "np")]),
    _block("py.run_command", "Modules", "run a shell command",
           "os.system(@command@)",
           [_slot("command", "command", "string", "ls")]),
    _block("py.argument", "Modules", "an argument this file was run with",
           "@name@ = sys.argv[@index@]",
           [_slot("name", "keep it in", "name", "first"), _slot("index", "number", "number", "1")]),
    _block("py.env", "Modules", "an environment setting",
           "@name@ = os.environ.get(@key@, @fallback@)",
           [_slot("name", "keep it in", "name", "home"), _slot("key", "setting", "string", "HOME"),
            _slot("fallback", "if missing", "text", '""')]),
    _block("py.now", "Modules", "the time right now",
           "@name@ = datetime.datetime.now()",
           [_slot("name", "keep it in", "name", "now")]),
    _block("py.sleep", "Modules", "wait for a moment", "time.sleep(@seconds@)",
           [_slot("seconds", "seconds", "number", "1")]),

    # -- Random ------------------------------------------------------------
    _block("py.random_int", "Random", "a random whole number",
           "@name@ = random.randint(@low@, @high@)",
           [_slot("name", "keep it in", "name", "roll"), _slot("low", "from", "number", "1"),
            _slot("high", "to", "number", "6")]),
    _block("py.random_choice", "Random", "a random item from a list",
           "@name@ = random.choice(@list@)",
           [_slot("name", "keep it in", "name", "picked"), _slot("list", "list", "name", "items")]),
    _block("py.shuffle", "Random", "shuffle a list", "random.shuffle(@list@)",
           [_slot("list", "list", "name", "items")]),
    _block("py.random_float", "Random", "a random number between 0 and 1",
           "@name@ = random.random()",
           [_slot("name", "keep it in", "name", "chance")]),
    _block("py.random_sample", "Random", "several random items",
           "@name@ = random.sample(@list@, @count@)",
           [_slot("name", "keep it in", "name", "picked"), _slot("list", "list", "name", "items"),
            _slot("count", "how many", "number", "3")]),

    # -- The web -----------------------------------------------------------
    _block("py.fetch_text", "Web", "fetch a page",
           "@name@ = requests.get(@url@).text",
           [_slot("name", "keep it in", "name", "page"),
            _slot("url", "address", "string", "https://example.com")]),
    _block("py.fetch_json", "Web", "fetch JSON",
           "@name@ = requests.get(@url@).json()",
           [_slot("name", "keep it in", "name", "data"),
            _slot("url", "address", "string", "https://example.com/api")]),
    _block("py.post_json", "Web", "send JSON",
           "@name@ = requests.post(@url@, json=@data@).json()",
           [_slot("name", "keep it in", "name", "reply"),
            _slot("url", "address", "string", "https://example.com/api"),
            _slot("data", "send", "text", "payload")]),
    _block("py.to_json", "Web", "turn into JSON text",
           "@name@ = json.dumps(@value@, indent=2)",
           [_slot("name", "keep it in", "name", "text"), _slot("value", "value", "text", "data")]),
    _block("py.from_json", "Web", "read JSON text",
           "@name@ = json.loads(@text@)",
           [_slot("name", "keep it in", "name", "data"), _slot("text", "text", "text", "body")]),
    _block("py.flask_app", "Web", "a Flask app", "@name@ = Flask(__name__)",
           [_slot("name", "called", "name", "app")]),
    _block("py.flask_route", "Web", "answer a web address",
           "@@app.route(@path@)",
           [_slot("path", "address", "string", "/")]),
    _block("py.flask_run", "Web", "start the Flask app", "app.run()"),

    # -- When things go wrong ----------------------------------------------
    _block("py.try", "Errors", "try this", "try:", wrap=True, empty="pass"),
    _block("py.except", "Errors", "if it went wrong",
           "except @error@ as @name@:",
           [_slot("error", "the problem", "text", "Exception"),
            _slot("name", "called", "name", "error")],
           wrap=True, empty="pass"),
    _block("py.finally", "Errors", "either way, do this", "finally:",
           wrap=True, empty="pass"),
    _block("py.raise", "Errors", "report a problem",
           "raise @error@(@message@)",
           [_slot("error", "kind", "text", "ValueError"),
            _slot("message", "message", "string", "that will not do")]),
    _block("py.assert", "Errors", "insist something is true",
           "assert @condition@, @message@",
           [_slot("condition", "must be true", "text", "count > 0"),
            _slot("message", "or say", "string", "there is nothing to do")]),

    # -- Classes -----------------------------------------------------------
    _block("py.class", "Classes", "define a kind of thing", "class @name@:",
           [_slot("name", "called", "name", "Player")], wrap=True, empty="pass"),
    _block("py.init", "Classes", "how one is made",
           "def __init__(self, @params@):",
           [_slot("params", "taking", "text", "name")], wrap=True, empty="pass"),
    _block("py.method", "Classes", "something it can do",
           "def @name@(self):",
           [_slot("name", "called", "name", "speak")], wrap=True, empty="pass"),
    _block("py.method_args", "Classes", "something it can do, with inputs",
           "def @name@(self, @params@):",
           [_slot("name", "called", "name", "move"), _slot("params", "taking", "text", "steps")],
           wrap=True, empty="pass"),
    _block("py.set_attribute", "Classes", "remember something on it",
           "self.@name@ = @value@",
           [_slot("name", "called", "name", "name"), _slot("value", "value", "text", "name")]),
    _block("py.get_attribute", "Classes", "read something off it",
           "@name@ = self.@attribute@",
           [_slot("name", "keep it in", "name", "value"),
            _slot("attribute", "attribute", "name", "name")]),
    _block("py.new_object", "Classes", "make one", "@name@ = @kind@(@args@)",
           [_slot("name", "called", "name", "player"), _slot("kind", "kind", "name", "Player"),
            _slot("args", "with", "text", '"Ada"')]),
    # -- Sets --------------------------------------------------------------
    _block("py.set_new", "Sets", "a group with no repeats",
           "@name@ = set()",
           [_slot("name", "name", "name", "seen")]),
    _block("py.set_from", "Sets", "a group from a list",
           "@name@ = set(@items@)",
           [_slot("name", "name", "name", "unique"), _slot("items", "of", "text", "words")]),
    _block("py.set_add", "Sets", "put one in", "@name@.add(@value@)",
           [_slot("name", "group", "name", "seen"), _slot("value", "value", "text", "word")]),
    _block("py.set_remove", "Sets", "take one out",
           "@name@.discard(@value@)",
           [_slot("name", "group", "name", "seen"), _slot("value", "value", "text", "word")],
           about="discard rather than remove: it does not complain if it was never there."),
    _block("py.set_has", "Sets", "if something is in the group",
           "if @value@ in @name@:",
           [_slot("value", "value", "text", "word"), _slot("name", "group", "name", "seen")],
           wrap=True, empty="pass"),
    _block("py.set_count", "Sets", "how many are in it",
           "@into@ = len(@name@)",
           [_slot("into", "into", "name", "count"), _slot("name", "group", "name", "seen")]),
    _block("py.set_both", "Sets", "the ones in both groups",
           "@into@ = @a@ & @b@",
           [_slot("into", "into", "name", "shared"),
            _slot("a", "first", "name", "mine"), _slot("b", "second", "name", "yours")]),
    _block("py.set_either", "Sets", "the ones in either group",
           "@into@ = @a@ | @b@",
           [_slot("into", "into", "name", "everyone"),
            _slot("a", "first", "name", "mine"), _slot("b", "second", "name", "yours")]),
    _block("py.set_only_mine", "Sets", "the ones only in the first group",
           "@into@ = @a@ - @b@",
           [_slot("into", "into", "name", "only_mine"),
            _slot("a", "in", "name", "mine"), _slot("b", "but not", "name", "yours")]),
    _block("py.no_repeats", "Sets", "a list with the repeats taken out",
           "@into@ = list(dict.fromkeys(@items@))",
           [_slot("into", "into", "name", "unique"), _slot("items", "of", "name", "words")],
           about="Keeps the original order, which set() does not."),

    # -- Making lists quickly ----------------------------------------------
    _block("py.list_from_each", "Making lists quickly", "a new list from every item",
           "@into@ = [@expression@ for @each@ in @items@]",
           [_slot("into", "into", "name", "doubled"),
            _slot("expression", "each becomes", "text", "n * 2"),
            _slot("each", "each one called", "name", "n"),
            _slot("items", "of", "text", "numbers")]),
    _block("py.comprehension_if", "Making lists quickly", "only the ones that match",
           "@into@ = [@each@ for @each@ in @items@ if @test@]",
           [_slot("into", "into", "name", "big"), _slot("each", "each one called", "name", "n"),
            _slot("items", "of", "text", "numbers"), _slot("test", "keep when", "text", "n > 10")]),
    _block("py.comprehension_both", "Making lists quickly", "change them and pick them",
           "@into@ = [@expression@ for @each@ in @items@ if @test@]",
           [_slot("into", "into", "name", "names"),
            _slot("expression", "each becomes", "text", "row.strip()"),
            _slot("each", "each one called", "name", "row"),
            _slot("items", "of", "text", "lines"), _slot("test", "keep when", "text", "row.strip()")]),
    _block("py.dict_comprehension", "Making lists quickly", "a new dictionary from a list",
           "@into@ = {@key@: @value@ for @each@ in @items@}",
           [_slot("into", "into", "name", "lengths"), _slot("key", "key", "text", "word"),
            _slot("value", "value", "text", "len(word)"),
            _slot("each", "each one called", "name", "word"),
            _slot("items", "of", "text", "words")]),
    _block("py.any", "Making lists quickly", "if any of them match",
           "if any(@test@ for @each@ in @items@):",
           [_slot("test", "test", "text", "n > 10"), _slot("each", "each one called", "name", "n"),
            _slot("items", "of", "text", "numbers")], wrap=True, empty="pass"),
    _block("py.all", "Making lists quickly", "if all of them match",
           "if all(@test@ for @each@ in @items@):",
           [_slot("test", "test", "text", "n > 0"), _slot("each", "each one called", "name", "n"),
            _slot("items", "of", "text", "numbers")], wrap=True, empty="pass"),
    _block("py.count_matching", "Making lists quickly", "how many match",
           "@into@ = sum(1 for @each@ in @items@ if @test@)",
           [_slot("into", "into", "name", "how_many"), _slot("each", "each one called", "name", "n"),
            _slot("items", "of", "text", "numbers"), _slot("test", "when", "text", "n > 10")]),

    # -- Sorting and picking -----------------------------------------------
    _block("py.sorted", "Sorting and picking", "a list in order",
           "@into@ = sorted(@items@)",
           [_slot("into", "into", "name", "in_order"), _slot("items", "of", "text", "names")]),
    _block("py.sorted_reverse", "Sorting and picking", "a list in reverse order",
           "@into@ = sorted(@items@, reverse=True)",
           [_slot("into", "into", "name", "biggest_first"), _slot("items", "of", "text", "scores")]),
    _block("py.sorted_by", "Sorting and picking", "a list in order of something",
           "@into@ = sorted(@items@, key=lambda @each@: @by@)",
           [_slot("into", "into", "name", "in_order"), _slot("items", "of", "text", "people"),
            _slot("each", "each one called", "name", "person"),
            _slot("by", "in order of", "text", 'person["age"]')]),
    _block("py.biggest", "Sorting and picking", "the biggest",
           "@into@ = max(@items@)",
           [_slot("into", "into", "name", "best"), _slot("items", "of", "text", "scores")]),
    _block("py.smallest_of_list", "Sorting and picking", "the smallest",
           "@into@ = min(@items@)",
           [_slot("into", "into", "name", "worst"), _slot("items", "of", "text", "scores")]),
    _block("py.first_match", "Sorting and picking", "the first one that matches",
           "@into@ = next((@each@ for @each@ in @items@ if @test@), None)",
           [_slot("into", "into", "name", "found"), _slot("each", "each one called", "name", "row"),
            _slot("items", "of", "text", "rows"), _slot("test", "when", "text", 'row["id"] == wanted')]),
    _block("py.enumerate_start", "Sorting and picking", "numbered from one",
           "for @index@, @value@ in enumerate(@items@, start=1):",
           [_slot("index", "number", "name", "position"), _slot("value", "value", "name", "item"),
            _slot("items", "of", "text", "names")], wrap=True, empty="pass"),
    _block("py.reversed", "Sorting and picking", "backwards",
           "for @value@ in reversed(@items@):",
           [_slot("value", "each one called", "name", "item"), _slot("items", "of", "text", "names")],
           wrap=True, empty="pass"),

    # -- Counting things ---------------------------------------------------
    _block("py.counter", "Counting things", "count how often each one appears",
           "@into@ = Counter(@items@)",
           [_slot("into", "into", "name", "counts"), _slot("items", "of", "text", "words")],
           about="Needs: from collections import Counter."),
    _block("py.counter_import", "Counting things", "bring in the counter",
           "from collections import Counter"),
    _block("py.counter_top", "Counting things", "the most common ones",
           "@into@ = @counts@.most_common(@how_many@)",
           [_slot("into", "into", "name", "top"), _slot("counts", "of", "name", "counts"),
            _slot("how_many", "how many", "number", "5")]),
    _block("py.defaultdict_import", "Counting things", "bring in the grouping dictionary",
           "from collections import defaultdict"),
    _block("py.group_by", "Counting things", "a dictionary of lists",
           "@name@ = defaultdict(list)",
           [_slot("name", "name", "name", "groups")]),
    _block("py.group_add", "Counting things", "add to a group",
           "@name@[@key@].append(@value@)",
           [_slot("name", "in", "name", "groups"), _slot("key", "under", "text", "kind"),
            _slot("value", "value", "text", "row")]),
    _block("py.total_of", "Counting things", "add up a list",
           "@into@ = sum(@items@)",
           [_slot("into", "into", "name", "total"), _slot("items", "of", "text", "scores")]),
    _block("py.average_safe", "Counting things", "the average of a list",
           "@into@ = sum(@items@) / len(@items@) if @items@ else 0",
           [_slot("into", "into", "name", "average"), _slot("items", "of", "name", "scores")]),

    # -- Dates and time ----------------------------------------------------
    _block("py.datetime_import", "Dates and time", "bring in dates",
           "from datetime import datetime, timedelta"),
    _block("py.today", "Dates and time", "right now",
           "@name@ = datetime.now()",
           [_slot("name", "into", "name", "now")]),
    _block("py.format_date", "Dates and time", "a date as text",
           "@into@ = @when@.strftime(@pattern@)",
           [_slot("into", "into", "name", "text"), _slot("when", "of", "name", "now"),
            _slot("pattern", "shaped like", "string", "%Y-%m-%d %H:%M")]),
    _block("py.parse_date", "Dates and time", "a date from text",
           "@into@ = datetime.strptime(@text@, @pattern@)",
           [_slot("into", "into", "name", "when"), _slot("text", "from", "text", "line"),
            _slot("pattern", "shaped like", "string", "%Y-%m-%d")]),
    _block("py.add_days", "Dates and time", "a date some days later",
           "@into@ = @when@ + timedelta(days=@days@)",
           [_slot("into", "into", "name", "later"), _slot("when", "from", "name", "now"),
            _slot("days", "days", "number", "7")]),
    _block("py.difference", "Dates and time", "how long between two dates",
           "@into@ = (@later@ - @earlier@).days",
           [_slot("into", "into", "name", "days"), _slot("later", "from", "name", "end"),
            _slot("earlier", "to", "name", "start")]),
    _block("py.timestamp", "Dates and time", "seconds since 1970",
           "@into@ = time.time()",
           [_slot("into", "into", "name", "stamp")],
           about="Needs: import time."),
    _block("py.measure", "Dates and time", "how long something took",
           "@into@ = time.time() - @started@",
           [_slot("into", "into", "name", "took"), _slot("started", "since", "name", "started")]),

    # -- Type hints --------------------------------------------------------
    _block("py.typed_function", "Type hints", "a function that says what it takes",
           "def @name@(@arguments@) -> @returns@:",
           [_slot("name", "name", "name", "double"),
            _slot("arguments", "takes", "text", "n: int"),
            _slot("returns", "gives back", "choice", "int",
                  ["int", "float", "str", "bool", "list", "dict", "None"])],
           wrap=True, empty="pass"),
    _block("py.typed_variable", "Type hints", "a variable that says what it holds",
           "@name@: @type@ = @value@",
           [_slot("name", "name", "name", "total"),
            _slot("type", "holds", "choice", "int",
                  ["int", "float", "str", "bool", "list", "dict", "set"]),
            _slot("value", "value", "text", "0")]),
    _block("py.typed_list", "Type hints", "a list that says what is in it",
           "@name@: list[@type@] = []",
           [_slot("name", "name", "name", "names"),
            _slot("type", "of", "choice", "str", ["str", "int", "float", "bool", "dict"])]),
    _block("py.dataclass_import", "Type hints", "bring in the shape maker",
           "from dataclasses import dataclass"),
    _block("py.dataclass_marker", "Type hints", "mark the next class as a shape",
           "@@dataclass",
           about="Put a class block straight after this one."),
    _block("py.dataclass", "Type hints", "a shape with named parts",
           "class @name@:",
           [_slot("name", "name", "name", "Point")], wrap=True, empty="x: int = 0",
           about="With the shape marker above it, Python writes the __init__ "
                 "for you."),
    _block("py.field", "Type hints", "one part of a shape",
           "@name@: @type@ = @value@",
           [_slot("name", "name", "name", "x"),
            _slot("type", "holds", "choice", "int",
                  ["int", "float", "str", "bool"]),
            _slot("value", "starts as", "text", "0")]),
]


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

JAVASCRIPT = [
    # -- Basics ------------------------------------------------------------
    _block("js.log", "Basics", "log text", "console.log(@text@);",
           [_slot("text", "text", "string", "Hello")]),
    _block("js.log_value", "Basics", "log a value", "console.log(@value@);",
           [_slot("value", "value", "text", "total")]),
    _block("js.log_labelled", "Basics", "log a label and a value",
           "console.log(@label@, @value@);",
           [_slot("label", "label", "string", "total:"), _slot("value", "value", "text", "total")]),
    _block("js.comment", "Basics", "a note to yourself", "// @text@",
           [_slot("text", "note", "text", "what this part does")]),
    _block("js.blank", "Basics", "an empty line", ""),
    _block("js.alert", "Basics", "show a message box", "alert(@text@);",
           [_slot("text", "message", "string", "Done")]),
    _block("js.confirm", "Basics", "ask yes or no",
           "const @name@ = confirm(@text@);",
           [_slot("name", "keep it in", "name", "sure"),
            _slot("text", "question", "string", "Are you sure?")]),
    _block("js.prompt", "Basics", "ask for text",
           "const @name@ = prompt(@text@);",
           [_slot("name", "keep it in", "name", "answer"),
            _slot("text", "question", "string", "Your name?")]),
    _block("js.use_strict", "Basics", "strict mode", "'use strict';"),

    # -- Variables ---------------------------------------------------------
    _block("js.const", "Variables", "a value that never changes",
           "const @name@ = @value@;",
           [_slot("name", "name", "name", "total"), _slot("value", "value", "text", "0")]),
    _block("js.let", "Variables", "a value that changes",
           "let @name@ = @value@;",
           [_slot("name", "name", "name", "count"), _slot("value", "value", "text", "0")]),
    _block("js.const_text", "Variables", "text", "const @name@ = @text@;",
           [_slot("name", "name", "name", "title"), _slot("text", "text", "string", "Hello")]),
    _block("js.const_number", "Variables", "a number", "const @name@ = @number@;",
           [_slot("name", "name", "name", "score"), _slot("number", "number", "number", "0")]),
    _block("js.const_bool", "Variables", "true or false", "let @name@ = @value@;",
           [_slot("name", "name", "name", "ready"),
            _slot("value", "value", "choice", "true", ["true", "false"])]),
    _block("js.assign", "Variables", "change a value", "@name@ = @value@;",
           [_slot("name", "name", "name", "count"), _slot("value", "value", "text", "1")]),
    _block("js.increase", "Variables", "add to a number", "@name@ += @amount@;",
           [_slot("name", "name", "name", "score"), _slot("amount", "by", "number", "1")]),
    _block("js.decrease", "Variables", "take away from a number",
           "@name@ -= @amount@;",
           [_slot("name", "name", "name", "lives"), _slot("amount", "by", "number", "1")]),
    _block("js.plus_plus", "Variables", "add one", "@name@++;",
           [_slot("name", "name", "name", "count")]),

    # -- Maths -------------------------------------------------------------
    _block("js.add", "Maths", "add", "const @name@ = @a@ + @b@;",
           [_slot("name", "keep it in", "name", "total"), _slot("a", "first", "text", "a"),
            _slot("b", "second", "text", "b")]),
    _block("js.maths", "Maths", "any sum", "const @name@ = @a@ @op@ @b@;",
           [_slot("name", "keep it in", "name", "answer"), _slot("a", "first", "text", "a"),
            _slot("op", "operator", "choice", "+", ["+", "-", "*", "/", "%", "**"]),
            _slot("b", "second", "text", "b")]),
    _block("js.round", "Maths", "round a number",
           "const @name@ = Math.round(@value@);",
           [_slot("name", "keep it in", "name", "rounded"), _slot("value", "number", "text", "value")]),
    _block("js.floor", "Maths", "round down",
           "const @name@ = Math.floor(@value@);",
           [_slot("name", "keep it in", "name", "whole"), _slot("value", "number", "text", "value")]),
    _block("js.random", "Maths", "a random whole number",
           "const @name@ = Math.floor(Math.random() * @range@) + @low@;",
           [_slot("name", "keep it in", "name", "roll"), _slot("range", "how many", "number", "6"),
            _slot("low", "starting at", "number", "1")]),
    _block("js.min_max", "Maths", "the smallest or largest",
           "const @name@ = Math.@which@(@a@, @b@);",
           [_slot("name", "keep it in", "name", "picked"),
            _slot("which", "which", "choice", "min", ["min", "max"]),
            _slot("a", "first", "text", "a"), _slot("b", "second", "text", "b")]),
    _block("js.to_number", "Maths", "as a number", "const @name@ = Number(@value@);",
           [_slot("name", "keep it in", "name", "count"), _slot("value", "value", "text", "text")]),
    _block("js.fixed", "Maths", "with a set number of decimals",
           "const @name@ = @value@.toFixed(@places@);",
           [_slot("name", "keep it in", "name", "price"), _slot("value", "number", "text", "value"),
            _slot("places", "decimals", "number", "2")]),

    # -- Text --------------------------------------------------------------
    _block("js.template", "Text", "build a sentence",
           "const @name@ = `@text@`;",
           [_slot("name", "keep it in", "name", "line"),
            _slot("text", "text, with ${name} in it", "inline", "Hello ${name}")]),
    _block("js.upper", "Text", "in capitals",
           "const @name@ = @value@.toUpperCase();",
           [_slot("name", "keep it in", "name", "shout"), _slot("value", "text", "text", "line")]),
    _block("js.lower", "Text", "in lower case",
           "const @name@ = @value@.toLowerCase();",
           [_slot("name", "keep it in", "name", "quiet"), _slot("value", "text", "text", "line")]),
    _block("js.trim", "Text", "without the spaces around it",
           "const @name@ = @value@.trim();",
           [_slot("name", "keep it in", "name", "clean"), _slot("value", "text", "text", "line")]),
    _block("js.replace", "Text", "with something swapped",
           "const @name@ = @value@.replaceAll(@old@, @new@);",
           [_slot("name", "keep it in", "name", "fixed"), _slot("value", "text", "text", "line"),
            _slot("old", "find", "string", "cat"), _slot("new", "replace with", "string", "dog")]),
    _block("js.split", "Text", "split into a list",
           "const @name@ = @value@.split(@separator@);",
           [_slot("name", "keep it in", "name", "parts"), _slot("value", "text", "text", "line"),
            _slot("separator", "split on", "string", ",")]),
    _block("js.join", "Text", "join a list into text",
           "const @name@ = @list@.join(@separator@);",
           [_slot("name", "keep it in", "name", "line"), _slot("list", "list", "name", "items"),
            _slot("separator", "between them", "string", ", ")]),
    _block("js.length", "Text", "how long it is",
           "const @name@ = @value@.length;",
           [_slot("name", "keep it in", "name", "count"),
            _slot("value", "text or list", "text", "line")]),
    _block("js.includes", "Text", "does it contain",
           "const @name@ = @value@.includes(@needle@);",
           [_slot("name", "keep it in", "name", "found"), _slot("value", "text or list", "text", "line"),
            _slot("needle", "look for", "string", "cat")]),
    _block("js.slice", "Text", "a piece of it",
           "const @name@ = @value@.slice(@start@, @end@);",
           [_slot("name", "keep it in", "name", "piece"), _slot("value", "text or list", "text", "line"),
            _slot("start", "from", "number", "0"), _slot("end", "to", "number", "5")]),
    _block("js.to_string", "Text", "as text", "const @name@ = String(@value@);",
           [_slot("name", "keep it in", "name", "text"), _slot("value", "value", "text", "number")]),

    # -- Arrays ------------------------------------------------------------
    _block("js.new_array", "Arrays", "a new list", "const @name@ = [@items@];",
           [_slot("name", "name", "name", "items"),
            _slot("items", "items, comma separated", "text", "")]),
    _block("js.push", "Arrays", "add to the end", "@list@.push(@value@);",
           [_slot("list", "list", "name", "items"), _slot("value", "value", "text", "item")]),
    _block("js.pop", "Arrays", "take the last one off",
           "const @name@ = @list@.pop();",
           [_slot("name", "keep it in", "name", "last"), _slot("list", "list", "name", "items")]),
    _block("js.shift", "Arrays", "take the first one off",
           "const @name@ = @list@.shift();",
           [_slot("name", "keep it in", "name", "first"), _slot("list", "list", "name", "items")]),
    _block("js.at", "Arrays", "the item at", "const @name@ = @list@[@index@];",
           [_slot("name", "keep it in", "name", "item"), _slot("list", "list", "name", "items"),
            _slot("index", "position", "number", "0")]),
    _block("js.set_at", "Arrays", "replace the item at",
           "@list@[@index@] = @value@;",
           [_slot("list", "list", "name", "items"), _slot("index", "position", "number", "0"),
            _slot("value", "value", "text", "item")]),
    _block("js.index_of", "Arrays", "where it is",
           "const @name@ = @list@.indexOf(@value@);",
           [_slot("name", "keep it in", "name", "at"), _slot("list", "list", "name", "items"),
            _slot("value", "value", "text", "item")]),
    _block("js.map", "Arrays", "a list built from another",
           "const @name@ = @list@.map((@item@) => @expression@);",
           [_slot("name", "keep it in", "name", "doubled"), _slot("list", "from", "name", "items"),
            _slot("item", "each is called", "name", "item"),
            _slot("expression", "each becomes", "text", "item * 2")]),
    _block("js.filter", "Arrays", "only the ones that match",
           "const @name@ = @list@.filter((@item@) => @condition@);",
           [_slot("name", "keep it in", "name", "big"), _slot("list", "from", "name", "items"),
            _slot("item", "each is called", "name", "item"),
            _slot("condition", "keep when", "text", "item > 10")]),
    _block("js.reduce", "Arrays", "add a list up",
           "const @name@ = @list@.reduce((a, b) => a + b, 0);",
           [_slot("name", "keep it in", "name", "total"), _slot("list", "list", "name", "items")]),
    _block("js.sort", "Arrays", "put in order", "@list@.sort();",
           [_slot("list", "list", "name", "items")]),
    _block("js.reverse", "Arrays", "turn it round", "@list@.reverse();",
           [_slot("list", "list", "name", "items")]),

    # -- Objects -----------------------------------------------------------
    _block("js.object", "Objects", "a new object",
           "const @name@ = {@pairs@};",
           [_slot("name", "name", "name", "person"),
            _slot("pairs", "key: value pairs", "text", "name: 'Ada', age: 36")]),
    _block("js.object_set", "Objects", "set a key",
           "@object@.@key@ = @value@;",
           [_slot("object", "object", "name", "person"), _slot("key", "key", "name", "name"),
            _slot("value", "value", "text", "'Ada'")]),
    _block("js.object_get", "Objects", "read a key",
           "const @name@ = @object@.@key@;",
           [_slot("name", "keep it in", "name", "value"), _slot("object", "object", "name", "person"),
            _slot("key", "key", "name", "name")]),
    _block("js.object_keys", "Objects", "all the keys",
           "const @name@ = Object.keys(@object@);",
           [_slot("name", "keep it in", "name", "keys"), _slot("object", "object", "name", "person")]),
    _block("js.json_stringify", "Objects", "turn into JSON text",
           "const @name@ = JSON.stringify(@value@, null, 2);",
           [_slot("name", "keep it in", "name", "text"), _slot("value", "value", "text", "data")]),
    _block("js.json_parse", "Objects", "read JSON text",
           "const @name@ = JSON.parse(@text@);",
           [_slot("name", "keep it in", "name", "data"), _slot("text", "text", "text", "body")]),

    # -- Logic -------------------------------------------------------------
    _block("js.if", "Logic", "if", "if (@condition@) {",
           [_slot("condition", "when", "text", "score > 10")], close="}", wrap=True),
    _block("js.if_equals", "Logic", "if two things are the same",
           "if (@a@ === @b@) {",
           [_slot("a", "this", "text", "answer"), _slot("b", "is", "text", "'yes'")],
           close="}", wrap=True),
    _block("js.if_compare", "Logic", "if, comparing two things",
           "if (@a@ @op@ @b@) {",
           [_slot("a", "this", "text", "score"),
            _slot("op", "compared", "choice", ">", ["===", "!==", "<", ">", "<=", ">="]),
            _slot("b", "to", "text", "10")],
           close="}", wrap=True),
    _block("js.else", "Logic", "otherwise", "} else {", close="}", wrap=True,
           about="Put this straight after an if block.",
           chain_after=("js.if", "js.if_equals", "js.if_compare", "js.else_if")),
    _block("js.else_if", "Logic", "or else if", "} else if (@condition@) {",
           [_slot("condition", "when", "text", "score > 5")], close="}", wrap=True,
           chain_after=("js.if", "js.if_equals", "js.if_compare", "js.else_if")),
    _block("js.ternary", "Logic", "one thing or the other",
           "const @name@ = @condition@ ? @yes@ : @no@;",
           [_slot("name", "keep it in", "name", "label"),
            _slot("condition", "when", "text", "score > 10"),
            _slot("yes", "then", "text", "'high'"), _slot("no", "otherwise", "text", "'low'")]),
    _block("js.not", "Logic", "the opposite", "const @name@ = !@value@;",
           [_slot("name", "keep it in", "name", "missing"), _slot("value", "of", "text", "found")]),

    # -- Loops -------------------------------------------------------------
    _block("js.repeat", "Loops", "repeat this many times",
           "for (let @var@ = 0; @var@ < @times@; @var@++) {",
           [_slot("var", "counter", "name", "i"), _slot("times", "times", "number", "10")],
           close="}", wrap=True),
    _block("js.for_of", "Loops", "for each item in a list",
           "for (const @item@ of @list@) {",
           [_slot("item", "each is called", "name", "item"), _slot("list", "in", "name", "items")],
           close="}", wrap=True),
    _block("js.for_each", "Loops", "for each item, with its position",
           "@list@.forEach((@item@, @index@) => {",
           [_slot("list", "list", "name", "items"), _slot("item", "each is called", "name", "item"),
            _slot("index", "position is called", "name", "index")],
           close="});", wrap=True),
    _block("js.while", "Loops", "keep going while", "while (@condition@) {",
           [_slot("condition", "while", "text", "running")], close="}", wrap=True),
    _block("js.break", "Loops", "stop the loop", "break;"),
    _block("js.continue", "Loops", "skip to the next time round", "continue;"),

    # -- Functions ---------------------------------------------------------
    _block("js.function", "Functions", "define a function",
           "function @name@(@params@) {",
           [_slot("name", "called", "name", "greet"), _slot("params", "taking", "text", "name")],
           close="}", wrap=True),
    _block("js.arrow", "Functions", "define a short function",
           "const @name@ = (@params@) => {",
           [_slot("name", "called", "name", "greet"), _slot("params", "taking", "text", "name")],
           close="};", wrap=True),
    _block("js.async", "Functions", "define a function that waits",
           "async function @name@(@params@) {",
           [_slot("name", "called", "name", "load"), _slot("params", "taking", "text", "")],
           close="}", wrap=True),
    _block("js.return", "Functions", "give an answer back", "return @value@;",
           [_slot("value", "answer", "text", "result")]),
    _block("js.call", "Functions", "run a function", "@name@(@args@);",
           [_slot("name", "function", "name", "greet"), _slot("args", "with", "text", "'Ada'")]),
    _block("js.call_keep", "Functions", "run a function and keep the answer",
           "const @result@ = @name@(@args@);",
           [_slot("result", "keep it in", "name", "answer"),
            _slot("name", "function", "name", "greet"), _slot("args", "with", "text", "'Ada'")]),
    _block("js.await", "Functions", "wait for an answer",
           "const @name@ = await @call@;",
           [_slot("name", "keep it in", "name", "data"),
            _slot("call", "waiting for", "text", "load()")]),

    # -- The page ----------------------------------------------------------
    _block("js.find", "Page", "find an element",
           "const @name@ = document.querySelector(@selector@);",
           [_slot("name", "keep it in", "name", "box"),
            _slot("selector", "selector", "string", "#out")]),
    _block("js.find_all", "Page", "find every matching element",
           "const @name@ = document.querySelectorAll(@selector@);",
           [_slot("name", "keep it in", "name", "boxes"),
            _slot("selector", "selector", "string", ".item")]),
    _block("js.set_text", "Page", "set an element's text",
           "@element@.textContent = @text@;",
           [_slot("element", "element", "name", "box"), _slot("text", "text", "text", "message")]),
    _block("js.set_html", "Page", "set an element's contents",
           "@element@.innerHTML = @html@;",
           [_slot("element", "element", "name", "box"), _slot("html", "html", "text", "markup")]),
    _block("js.set_style", "Page", "change how an element looks",
           "@element@.style.@property@ = @value@;",
           [_slot("element", "element", "name", "box"),
            _slot("property", "property", "name", "color"),
            _slot("value", "value", "string", "red")]),
    _block("js.add_class", "Page", "add a class",
           "@element@.classList.add(@name@);",
           [_slot("element", "element", "name", "box"), _slot("name", "class", "string", "active")]),
    _block("js.remove_class", "Page", "remove a class",
           "@element@.classList.remove(@name@);",
           [_slot("element", "element", "name", "box"), _slot("name", "class", "string", "active")]),
    _block("js.toggle_class", "Page", "turn a class on or off",
           "@element@.classList.toggle(@name@);",
           [_slot("element", "element", "name", "box"), _slot("name", "class", "string", "active")]),
    _block("js.create", "Page", "make an element",
           "const @name@ = document.createElement(@tag@);",
           [_slot("name", "keep it in", "name", "row"), _slot("tag", "tag", "string", "div")]),
    _block("js.append", "Page", "put it inside another",
           "@parent@.appendChild(@child@);",
           [_slot("parent", "inside", "name", "list"), _slot("child", "put in", "name", "row")]),
    _block("js.remove_element", "Page", "take an element out",
           "@element@.remove();",
           [_slot("element", "element", "name", "row")]),
    _block("js.value_of", "Page", "read an input",
           "const @name@ = @element@.value;",
           [_slot("name", "keep it in", "name", "typed"), _slot("element", "input", "name", "box")]),

    # -- Events and time ---------------------------------------------------
    _block("js.on_click", "Events", "when this is clicked",
           "@element@.addEventListener('click', () => {",
           [_slot("element", "element", "name", "button")], close="});", wrap=True),
    _block("js.on_event", "Events", "when something happens",
           "@element@.addEventListener(@event@, (event) => {",
           [_slot("element", "element", "name", "box"),
            _slot("event", "event", "choice", "'input'",
                  ["'input'", "'change'", "'submit'", "'keydown'", "'mouseover'", "'scroll'"])],
           close="});", wrap=True),
    _block("js.on_load", "Events", "when the page is ready",
           "window.addEventListener('DOMContentLoaded', () => {",
           close="});", wrap=True),
    _block("js.prevent", "Events", "stop the usual behaviour",
           "event.preventDefault();"),
    _block("js.after", "Events", "after a delay",
           "setTimeout(() => {",
           [_slot("delay", "milliseconds", "number", "1000")],
           close="}, @delay@);", wrap=True),
    _block("js.every", "Events", "over and over",
           "setInterval(() => {",
           [_slot("delay", "milliseconds", "number", "1000")],
           close="}, @delay@);", wrap=True),

    # -- Fetching ----------------------------------------------------------
    _block("js.fetch", "Fetch", "fetch JSON",
           "const @name@ = await (await fetch(@url@)).json();",
           [_slot("name", "keep it in", "name", "data"),
            _slot("url", "address", "string", "/api")]),
    _block("js.fetch_text", "Fetch", "fetch text",
           "const @name@ = await (await fetch(@url@)).text();",
           [_slot("name", "keep it in", "name", "body"),
            _slot("url", "address", "string", "/page")]),
    _block("js.post", "Fetch", "send JSON",
           "const @name@ = await fetch(@url@, { method: 'POST', "
           "headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(@data@) });",
           [_slot("name", "keep it in", "name", "reply"),
            _slot("url", "address", "string", "/api"), _slot("data", "send", "text", "payload")]),
    _block("js.try", "Fetch", "try this", "try {", close="} catch (error) {", wrap=True,
           about="Follow it with a catch block."),
    _block("js.catch", "Fetch", "if it went wrong", "} catch (error) {", close="}", wrap=True),
    # -- Waiting -----------------------------------------------------------
    _block("js.async_function", "Waiting", "a function that can wait",
           "async function @name@(@params@) {",
           [_slot("name", "name", "name", "load"), _slot("params", "takes", "text", "")],
           close="}", wrap=True),
    _block("js.await_run", "Waiting", "wait for something",
           "await @call@;",
           [_slot("call", "wait for", "text", "save()")]),
    _block("js.promise_then", "Waiting", "when it finishes, do this",
           "@call@.then((@name@) => {",
           [_slot("call", "after", "text", "fetch(url)"),
            _slot("name", "answer called", "name", "reply")],
           close="});", wrap=True),
    _block("js.promise_catch", "Waiting", "if it goes wrong",
           "}).catch((@name@) => {",
           [_slot("name", "error called", "name", "error")], close="});", wrap=True,
           chain_after=("js.promise_then",)),
    _block("js.sleep_helper", "Waiting", "a pause you can wait for",
           "const sleep = (ms) => new Promise((done) => setTimeout(done, ms));"),
    _block("js.sleep", "Waiting", "pause",
           "await sleep(@millis@);",
           [_slot("millis", "milliseconds", "number", "500")]),
    _block("js.promise_all", "Waiting", "wait for several at once",
           "const @name@ = await Promise.all(@list@);",
           [_slot("name", "keep them in", "name", "results"),
            _slot("list", "of", "text", "urls.map((u) => fetch(u))")]),

    # -- Timers ------------------------------------------------------------
    _block("js.timeout", "Timers", "do this in a moment",
           "setTimeout(() => {",
           [_slot("millis", "after milliseconds", "number", "1000")],
           close="}, @millis@);", wrap=True),
    _block("js.interval", "Timers", "do this over and over",
           "const @name@ = setInterval(() => {",
           [_slot("name", "so it can be stopped", "name", "ticking"),
            _slot("millis", "every milliseconds", "number", "1000")],
           close="}, @millis@);", wrap=True),
    _block("js.clear_interval", "Timers", "stop doing it",
           "clearInterval(@name@);",
           [_slot("name", "which", "name", "ticking")]),
    _block("js.animation_frame", "Timers", "do this on the next frame",
           "requestAnimationFrame(() => {", close="});", wrap=True),

    # -- Classes -----------------------------------------------------------
    _block("js.class", "Classes", "a kind of thing", "class @name@ {",
           [_slot("name", "name", "name", "Player")], close="}", wrap=True),
    _block("js.constructor", "Classes", "how one is made",
           "constructor(@params@) {",
           [_slot("params", "takes", "text", "name")], close="}", wrap=True),
    _block("js.this_set", "Classes", "set one of its parts",
           "this.@name@ = @value@;",
           [_slot("name", "part", "name", "name"), _slot("value", "value", "text", "name")]),
    _block("js.this_get", "Classes", "read one of its parts",
           "const @into@ = this.@name@;",
           [_slot("into", "into", "name", "value"), _slot("name", "part", "name", "name")]),
    _block("js.method", "Classes", "something it can do",
           "@name@(@params@) {",
           [_slot("name", "name", "name", "greet"), _slot("params", "takes", "text", "")],
           close="}", wrap=True),
    _block("js.new", "Classes", "make one",
           "const @into@ = new @type@(@arguments@);",
           [_slot("into", "into", "name", "player"), _slot("type", "of", "name", "Player"),
            _slot("arguments", "with", "text", "'Ada'")]),
    _block("js.extends", "Classes", "a kind of another kind",
           "class @name@ extends @parent@ {",
           [_slot("name", "name", "name", "Hero"), _slot("parent", "based on", "name", "Player")],
           close="}", wrap=True),
    _block("js.super", "Classes", "set up the kind it is based on",
           "super(@arguments@);",
           [_slot("arguments", "with", "text", "name")]),

    # -- Dates and numbers -------------------------------------------------
    _block("js.now", "Dates and numbers", "right now",
           "const @name@ = new Date();",
           [_slot("name", "into", "name", "now")]),
    _block("js.date_text", "Dates and numbers", "a date as text",
           "const @into@ = @when@.toLocaleDateString();",
           [_slot("into", "into", "name", "text"), _slot("when", "of", "name", "now")]),
    _block("js.time_text", "Dates and numbers", "a time as text",
           "const @into@ = @when@.toLocaleTimeString();",
           [_slot("into", "into", "name", "text"), _slot("when", "of", "name", "now")]),
    _block("js.timestamp", "Dates and numbers", "milliseconds since 1970",
           "const @into@ = Date.now();",
           [_slot("into", "into", "name", "stamp")]),
    _block("js.to_fixed", "Dates and numbers", "a number with fixed decimals",
           "const @into@ = @value@.toFixed(@places@);",
           [_slot("into", "into", "name", "shown"), _slot("value", "of", "text", "price"),
            _slot("places", "decimals", "number", "2")]),
    _block("js.parse_number", "Dates and numbers", "turn text into a number",
           "const @into@ = Number(@text@);",
           [_slot("into", "into", "name", "value"), _slot("text", "from", "text", "input.value")]),
    _block("js.is_number", "Dates and numbers", "if it really is a number",
           "if (!Number.isNaN(@value@)) {",
           [_slot("value", "value", "text", "value")], close="}", wrap=True),
    _block("js.pad", "Dates and numbers", "a number padded with zeros",
           "const @into@ = String(@value@).padStart(@width@, '0');",
           [_slot("into", "into", "name", "shown"), _slot("value", "of", "text", "minutes"),
            _slot("width", "to width", "number", "2")]),

    # -- Remembering things ------------------------------------------------
    _block("js.save", "Remembering things", "remember something",
           "localStorage.setItem(@key@, @value@);",
           [_slot("key", "under", "string", "name"), _slot("value", "value", "text", "name")],
           about="Stays until the page's storage is cleared."),
    _block("js.load", "Remembering things", "read something back",
           "const @into@ = localStorage.getItem(@key@);",
           [_slot("into", "into", "name", "saved"), _slot("key", "under", "string", "name")],
           about="null when nothing was saved under that name."),
    _block("js.save_object", "Remembering things", "remember a whole object",
           "localStorage.setItem(@key@, JSON.stringify(@value@));",
           [_slot("key", "under", "string", "settings"), _slot("value", "value", "text", "settings")]),
    _block("js.load_object", "Remembering things", "read a whole object back",
           "const @into@ = JSON.parse(localStorage.getItem(@key@) || @fallback@);",
           [_slot("into", "into", "name", "settings"), _slot("key", "under", "string", "settings"),
            _slot("fallback", "or", "string", "{}")]),
    _block("js.forget", "Remembering things", "forget something",
           "localStorage.removeItem(@key@);",
           [_slot("key", "under", "string", "name")]),

    # -- Sorting and picking -----------------------------------------------
    _block("js.sort_list", "Sorting and picking", "put a list in order",
           "@name@.sort();",
           [_slot("name", "list", "name", "names")]),
    _block("js.sort_numbers", "Sorting and picking", "put numbers in order",
           "@name@.sort((a, b) => a - b);",
           [_slot("name", "list", "name", "scores")],
           about="Without this, JavaScript sorts numbers as text: 10 before 9."),
    _block("js.sort_by", "Sorting and picking", "in order of something",
           "@name@.sort((a, b) => a.@field@ - b.@field@);",
           [_slot("name", "list", "name", "people"), _slot("field", "in order of", "name", "age")]),
    _block("js.find_in_list", "Sorting and picking", "the first one that matches",
           "const @into@ = @name@.find((@each@) => @test@);",
           [_slot("into", "into", "name", "found"), _slot("name", "in", "name", "items"),
            _slot("each", "each one called", "name", "item"),
            _slot("test", "when", "text", "item.id === wanted")]),
    _block("js.some", "Sorting and picking", "if any of them match",
           "if (@name@.some((@each@) => @test@)) {",
           [_slot("name", "in", "name", "items"), _slot("each", "each one called", "name", "item"),
            _slot("test", "when", "text", "item.done")], close="}", wrap=True),
    _block("js.every_matches", "Sorting and picking", "if all of them match",
           "if (@name@.every((@each@) => @test@)) {",
           [_slot("name", "in", "name", "items"), _slot("each", "each one called", "name", "item"),
            _slot("test", "when", "text", "item.done")], close="}", wrap=True),
    _block("js.sum", "Sorting and picking", "add them all up",
           "const @into@ = @name@.reduce((total, @each@) => total + @value@, 0);",
           [_slot("into", "into", "name", "total"), _slot("name", "of", "name", "scores"),
            _slot("each", "each one called", "name", "n"), _slot("value", "adding", "text", "n")]),
    _block("js.unique", "Sorting and picking", "the list with repeats taken out",
           "const @into@ = [...new Set(@name@)];",
           [_slot("into", "into", "name", "unique"), _slot("name", "of", "name", "items")]),
]


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

HTML = [
    # -- The document ------------------------------------------------------
    _block("html.doctype", "Document", "start of an HTML file", "<!doctype html>"),
    _block("html.page", "Document", "a whole page",
           '<html lang="@lang@">',
           [_slot("lang", "language", "string", "en")], close="</html>", wrap=True),
    _block("html.head", "Document", "the head", "<head>", close="</head>", wrap=True),
    _block("html.body", "Document", "the body", "<body>", close="</body>", wrap=True),
    _block("html.title", "Document", "the page title", "<title>@text@</title>",
           [_slot("text", "title", "string", "My page")]),
    _block("html.charset", "Document", "character set", '<meta charset="utf-8">'),
    _block("html.viewport", "Document", "fit the phone screen",
           '<meta name="viewport" content="width=device-width, initial-scale=1">'),
    _block("html.stylesheet", "Document", "use a stylesheet",
           '<link rel="stylesheet" href="@href@">',
           [_slot("href", "file", "string", "style.css")]),
    _block("html.script_src", "Document", "use a script",
           '<script src="@src@"></script>',
           [_slot("src", "file", "string", "app.js")]),
    _block("html.comment", "Document", "a note to yourself", "<!-- @text@ -->",
           [_slot("text", "note", "text", "what this part is")]),
    _block("html.blank", "Document", "an empty line", ""),

    # -- Text --------------------------------------------------------------
    _block("html.h1", "Text", "big heading", "<h1>@text@</h1>",
           [_slot("text", "text", "string", "Hello")]),
    _block("html.h2", "Text", "heading", "<h2>@text@</h2>",
           [_slot("text", "text", "string", "A section")]),
    _block("html.h3", "Text", "small heading", "<h3>@text@</h3>",
           [_slot("text", "text", "string", "A part")]),
    _block("html.p", "Text", "a paragraph", "<p>@text@</p>",
           [_slot("text", "text", "string", "Some words.")]),
    _block("html.span", "Text", "a piece of text with a name",
           '<span id="@id@">@text@</span>',
           [_slot("id", "id", "string", "out"), _slot("text", "text", "string", "")]),
    _block("html.strong", "Text", "bold", "<strong>@text@</strong>",
           [_slot("text", "text", "string", "important")]),
    _block("html.em", "Text", "italic", "<em>@text@</em>",
           [_slot("text", "text", "string", "gently")]),
    _block("html.br", "Text", "a line break", "<br>"),
    _block("html.hr", "Text", "a dividing line", "<hr>"),
    _block("html.pre", "Text", "code, kept as typed",
           '<pre id="@id@">@text@</pre>',
           [_slot("id", "id", "string", "out"), _slot("text", "text", "string", "")]),

    # -- Structure ---------------------------------------------------------
    _block("html.div", "Structure", "a box", '<div class="@class@">',
           [_slot("class", "class", "string", "card")], close="</div>", wrap=True),
    _block("html.div_id", "Structure", "a box with an id", '<div id="@id@">',
           [_slot("id", "id", "string", "app")], close="</div>", wrap=True),
    _block("html.section", "Structure", "a section", "<section>", close="</section>",
           wrap=True),
    _block("html.header", "Structure", "a header", "<header>", close="</header>", wrap=True),
    _block("html.footer", "Structure", "a footer", "<footer>", close="</footer>", wrap=True),
    _block("html.nav", "Structure", "navigation", "<nav>", close="</nav>", wrap=True),
    _block("html.main", "Structure", "the main part", "<main>", close="</main>", wrap=True),
    _block("html.style", "Structure", "styles, written here",
           "<style>", close="</style>", wrap=True),
    _block("html.script", "Structure", "a script, written here",
           "<script>", close="</script>", wrap=True),

    # -- Links, media and lists --------------------------------------------
    _block("html.link", "Links", "a link", '<a href="@href@">@text@</a>',
           [_slot("href", "address", "string", "https://example.com"),
            _slot("text", "text", "string", "Go there")]),
    _block("html.image", "Links", "an image", '<img src="@src@" alt="@alt@">',
           [_slot("src", "file", "string", "picture.png"),
            _slot("alt", "description", "string", "a picture")]),
    _block("html.audio", "Links", "a sound player",
           '<audio controls src="@src@"></audio>',
           [_slot("src", "file", "string", "song.mp3")]),
    _block("html.video", "Links", "a video player",
           '<video controls width="100%" src="@src@"></video>',
           [_slot("src", "file", "string", "clip.mp4")]),
    _block("html.ul", "Links", "a bullet list", "<ul>", close="</ul>", wrap=True),
    _block("html.ol", "Links", "a numbered list", "<ol>", close="</ol>", wrap=True),
    _block("html.li", "Links", "a list item", "<li>@text@</li>",
           [_slot("text", "text", "string", "an item")]),
    _block("html.table", "Links", "a table", "<table>", close="</table>", wrap=True),
    _block("html.tr", "Links", "a table row", "<tr>", close="</tr>", wrap=True),
    _block("html.td", "Links", "a table cell", "<td>@text@</td>",
           [_slot("text", "text", "string", "value")]),
    _block("html.th", "Links", "a table heading cell", "<th>@text@</th>",
           [_slot("text", "text", "string", "Name")]),

    # -- Forms -------------------------------------------------------------
    _block("html.button", "Forms", "a button",
           '<button id="@id@">@text@</button>',
           [_slot("id", "id", "string", "go"), _slot("text", "text", "string", "Press me")]),
    _block("html.input", "Forms", "a text box",
           '<input id="@id@" type="@type@" placeholder="@placeholder@">',
           [_slot("id", "id", "string", "name"),
            _slot("type", "kind", "choice", "text",
                  ["text", "number", "email", "password", "search", "date", "color", "range"]),
            _slot("placeholder", "hint", "string", "Type here")]),
    _block("html.textarea", "Forms", "a big text box",
           '<textarea id="@id@" rows="@rows@"></textarea>',
           [_slot("id", "id", "string", "notes"), _slot("rows", "lines", "number", "5")]),
    _block("html.checkbox", "Forms", "a tick box",
           '<label><input id="@id@" type="checkbox"> @text@</label>',
           [_slot("id", "id", "string", "agree"), _slot("text", "label", "string", "I agree")]),
    _block("html.select", "Forms", "a drop-down", '<select id="@id@">',
           [_slot("id", "id", "string", "choice")], close="</select>", wrap=True),
    _block("html.option", "Forms", "a drop-down choice",
           '<option value="@value@">@text@</option>',
           [_slot("value", "value", "string", "one"), _slot("text", "text", "string", "One")]),
    _block("html.label", "Forms", "a label for a box",
           '<label for="@for@">@text@</label>',
           [_slot("for", "for id", "string", "name"), _slot("text", "text", "string", "Your name")]),
    _block("html.form", "Forms", "a form", '<form id="@id@">',
           [_slot("id", "id", "string", "form")], close="</form>", wrap=True),
]


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = [
    # -- Rules -------------------------------------------------------------
    _block("css.rule", "Rules", "style an element", "@selector@ {",
           [_slot("selector", "selector", "string", "body")], close="}", wrap=True),
    _block("css.class", "Rules", "style a class", ".@name@ {",
           [_slot("name", "class", "string", "card")], close="}", wrap=True),
    _block("css.id", "Rules", "style one element", "#@name@ {",
           [_slot("name", "id", "string", "app")], close="}", wrap=True),
    _block("css.hover", "Rules", "style it when touched", "@selector@:hover {",
           [_slot("selector", "selector", "string", "button")], close="}", wrap=True),
    _block("css.media", "Rules", "style it on small screens",
           "@@media (max-width: @width@px) {",
           [_slot("width", "up to", "number", "600")], close="}", wrap=True),
    _block("css.root", "Rules", "colours used everywhere", ":root {", close="}", wrap=True),
    _block("css.variable", "Rules", "name a value", "--@name@: @value@;",
           [_slot("name", "name", "string", "accent"), _slot("value", "value", "string", "#2E7DD1")]),
    _block("css.comment", "Rules", "a note to yourself", "/* @text@ */",
           [_slot("text", "note", "text", "what this part does")]),
    _block("css.blank", "Rules", "an empty line", ""),

    # -- Text --------------------------------------------------------------
    _block("css.color", "Text", "text colour", "color: @value@;",
           [_slot("value", "colour", "string", "#DCE3EC")]),
    _block("css.font_size", "Text", "text size", "font-size: @value@;",
           [_slot("value", "size", "string", "16px")]),
    _block("css.font_family", "Text", "typeface", "font-family: @value@;",
           [_slot("value", "fonts", "string", "system-ui, sans-serif")]),
    _block("css.font_weight", "Text", "how bold", "font-weight: @value@;",
           [_slot("value", "weight", "choice", "600",
                  ["400", "500", "600", "700", "bold", "normal"])]),
    _block("css.text_align", "Text", "line up the text", "text-align: @value@;",
           [_slot("value", "align", "choice", "center",
                  ["left", "center", "right", "justify"])]),
    _block("css.line_height", "Text", "space between lines", "line-height: @value@;",
           [_slot("value", "height", "string", "1.6")]),
    _block("css.text_decoration", "Text", "underline or not",
           "text-decoration: @value@;",
           [_slot("value", "decoration", "choice", "none", ["none", "underline", "line-through"])]),
    _block("css.letter_spacing", "Text", "space between letters",
           "letter-spacing: @value@;",
           [_slot("value", "spacing", "string", "0.02em")]),

    # -- The box -----------------------------------------------------------
    _block("css.margin", "Box", "space outside", "margin: @value@;",
           [_slot("value", "space", "string", "0 auto")]),
    _block("css.padding", "Box", "space inside", "padding: @value@;",
           [_slot("value", "space", "string", "16px")]),
    _block("css.width", "Box", "width", "width: @value@;",
           [_slot("value", "width", "string", "100%")]),
    _block("css.max_width", "Box", "widest it gets", "max-width: @value@;",
           [_slot("value", "width", "string", "720px")]),
    _block("css.height", "Box", "height", "height: @value@;",
           [_slot("value", "height", "string", "auto")]),
    _block("css.border", "Box", "a border", "border: @value@;",
           [_slot("value", "border", "string", "1px solid #223041")]),
    _block("css.radius", "Box", "rounded corners", "border-radius: @value@;",
           [_slot("value", "radius", "string", "12px")]),
    _block("css.box_shadow", "Box", "a shadow", "box-shadow: @value@;",
           [_slot("value", "shadow", "string", "0 2px 12px rgba(0,0,0,.35)")]),
    _block("css.overflow", "Box", "what happens when it does not fit",
           "overflow: @value@;",
           [_slot("value", "overflow", "choice", "auto", ["auto", "hidden", "scroll", "visible"])]),

    # -- Colour ------------------------------------------------------------
    _block("css.background", "Colour", "background colour", "background: @value@;",
           [_slot("value", "colour", "string", "#0B0F14")]),
    _block("css.gradient", "Colour", "a colour fade",
           "background: linear-gradient(@angle@, @from@, @to@);",
           [_slot("angle", "direction", "string", "180deg"),
            _slot("from", "from", "string", "#16324D"), _slot("to", "to", "string", "#0B0F14")]),
    _block("css.opacity", "Colour", "how see-through", "opacity: @value@;",
           [_slot("value", "0 to 1", "string", "0.8")]),
    _block("css.background_image", "Colour", "a background picture",
           'background-image: url("@src@");',
           [_slot("src", "file", "string", "picture.png")]),

    # -- Layout ------------------------------------------------------------
    _block("css.display", "Layout", "how it lays out", "display: @value@;",
           [_slot("value", "display", "choice", "flex",
                  ["flex", "grid", "block", "inline-block", "none"])]),
    _block("css.flex_direction", "Layout", "which way things stack",
           "flex-direction: @value@;",
           [_slot("value", "direction", "choice", "column", ["row", "column"])]),
    _block("css.justify", "Layout", "line up along the row",
           "justify-content: @value@;",
           [_slot("value", "align", "choice", "center",
                  ["flex-start", "center", "flex-end", "space-between", "space-around"])]),
    _block("css.align", "Layout", "line up across the row", "align-items: @value@;",
           [_slot("value", "align", "choice", "center",
                  ["flex-start", "center", "flex-end", "stretch"])]),
    _block("css.gap", "Layout", "space between things", "gap: @value@;",
           [_slot("value", "gap", "string", "12px")]),
    _block("css.grid_columns", "Layout", "columns in a grid",
           "grid-template-columns: repeat(@count@, 1fr);",
           [_slot("count", "how many", "number", "3")]),
    _block("css.position", "Layout", "how it is placed", "position: @value@;",
           [_slot("value", "position", "choice", "relative",
                  ["static", "relative", "absolute", "fixed", "sticky"])]),
    _block("css.z_index", "Layout", "what sits on top", "z-index: @value@;",
           [_slot("value", "layer", "number", "10")]),

    # -- Effects -----------------------------------------------------------
    _block("css.transition", "Effects", "make changes smooth",
           "transition: @value@;",
           [_slot("value", "transition", "string", "all .2s ease")]),
    _block("css.transform", "Effects", "move, turn or scale",
           "transform: @value@;",
           [_slot("value", "transform", "string", "scale(1.05)")]),
    _block("css.cursor", "Effects", "the pointer over it", "cursor: @value@;",
           [_slot("value", "cursor", "choice", "pointer", ["pointer", "default", "text", "grab"])]),
    _block("css.property", "Effects", "any property at all", "@property@: @value@;",
           [_slot("property", "property", "string", "filter"),
            _slot("value", "value", "string", "blur(2px)")]),
]


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

MARKDOWN = [
    _block("md.h1", "Headings", "title", "# @text@",
           [_slot("text", "text", "string", "My notes")]),
    _block("md.h2", "Headings", "heading", "## @text@",
           [_slot("text", "text", "string", "A section")]),
    _block("md.h3", "Headings", "small heading", "### @text@",
           [_slot("text", "text", "string", "A part")]),
    _block("md.text", "Text", "a paragraph", "@text@",
           [_slot("text", "text", "string", "Some words.")]),
    _block("md.blank", "Text", "an empty line", ""),
    _block("md.bold", "Text", "bold text", "**@text@**",
           [_slot("text", "text", "string", "important")]),
    _block("md.italic", "Text", "italic text", "*@text@*",
           [_slot("text", "text", "string", "gently")]),
    _block("md.quote", "Text", "a quote", "> @text@",
           [_slot("text", "text", "string", "somebody said this")]),
    _block("md.rule", "Text", "a dividing line", "---"),
    _block("md.bullet", "Lists", "a bullet", "- @text@",
           [_slot("text", "text", "string", "an item")]),
    _block("md.numbered", "Lists", "a numbered item", "@number@. @text@",
           [_slot("number", "number", "number", "1"),
            _slot("text", "text", "string", "an item")]),
    _block("md.task", "Lists", "a thing to do", "- [ ] @text@",
           [_slot("text", "text", "string", "something to do")]),
    _block("md.task_done", "Lists", "a thing already done", "- [x] @text@",
           [_slot("text", "text", "string", "something finished")]),
    _block("md.link", "Links", "a link", "[@text@](@href@)",
           [_slot("text", "text", "string", "Go there"),
            _slot("href", "address", "string", "https://example.com")]),
    _block("md.image", "Links", "an image", "![@alt@](@src@)",
           [_slot("alt", "description", "string", "a picture"),
            _slot("src", "file", "string", "picture.png")]),
    _block("md.code_inline", "Code", "a bit of code", "`@text@`",
           [_slot("text", "code", "string", "print()")]),
    _block("md.code_open", "Code", "a block of code", "```@language@",
           [_slot("language", "language", "string", "python")], close="```", wrap=True),
    _block("md.table_head", "Code", "a table heading row",
           "| @a@ | @b@ |",
           [_slot("a", "first column", "string", "Name"),
            _slot("b", "second column", "string", "Value")]),
    _block("md.table_divider", "Code", "the line under a table heading",
           "|---|---|"),
    _block("md.table_row", "Code", "a table row", "| @a@ | @b@ |",
           [_slot("a", "first", "string", "one"), _slot("b", "second", "string", "1")]),
]


# ---------------------------------------------------------------------------
# C
# ---------------------------------------------------------------------------
#
# Everything here is written against the C the app actually carries -
# `pycmd_langs.c_interp`, a real interpreter rather than a compiler. That is
# the line these blocks are drawn along: if the interpreter cannot run it,
# there is no block for it, because a block that writes code the phone refuses
# is worse than no block at all.

C = [
    # -- Basics ------------------------------------------------------------
    _block("c.print", "Basics", "print text", 'printf("@text@\\n");',
           [_slot("text", "text", "inline", "Hello")],
           about="The new line is added for you."),
    _block("c.print_same_line", "Basics", "print text, staying on the line",
           'printf("@text@");',
           [_slot("text", "text", "inline", "Loading")]),
    _block("c.print_line", "Basics", "print a line of text", "puts(@text@);",
           [_slot("text", "text", "string", "Hello")]),
    _block("c.print_number", "Basics", "print a whole number",
           'printf("%d\\n", @value@);',
           [_slot("value", "value", "text", "total")]),
    _block("c.print_decimal", "Basics", "print a decimal number",
           'printf("%.2f\\n", @value@);',
           [_slot("value", "value", "text", "average")]),
    _block("c.print_text_value", "Basics", "print a piece of text",
           'printf("%s\\n", @value@);',
           [_slot("value", "value", "text", "name")]),
    _block("c.print_labelled", "Basics", "print a label and a number",
           'printf("@label@ %d\\n", @value@);',
           [_slot("label", "label", "inline", "total:"),
            _slot("value", "value", "text", "total")]),
    _block("c.print_char", "Basics", "print one character",
           "putchar(@value@);",
           [_slot("value", "character", "text", "'A'")]),
    _block("c.comment", "Basics", "a note to yourself", "// @text@",
           [_slot("text", "note", "text", "what this part does")]),
    _block("c.blank", "Basics", "an empty line", ""),
    _block("c.include", "Basics", "use a standard header",
           "#include <@name@>",
           [_slot("name", "header", "choice", "stdio.h",
                  ["stdio.h", "stdlib.h", "string.h", "math.h", "ctype.h", "time.h"])],
           about="stdio.h for printing, string.h for text, math.h for maths."),
    _block("c.main", "Basics", "the program itself", "int main(void) {",
           close="}", wrap=True, empty="return 0;",
           about="Every C program starts here. Put your blocks inside it."),
    _block("c.return_zero", "Basics", "finish successfully", "return 0;"),
    _block("c.read_number", "Basics", "read a number that was typed",
           'scanf("%d", &@name@);',
           [_slot("name", "into", "name", "answer")],
           about="Declare the variable first."),
    _block("c.read_word", "Basics", "read a word that was typed",
           'scanf("%s", @name@);',
           [_slot("name", "into", "name", "word")],
           about="Into a char array, which is already an address."),

    # -- Variables ---------------------------------------------------------
    _block("c.int", "Variables", "a whole number", "int @name@ = @value@;",
           [_slot("name", "name", "name", "total"), _slot("value", "value", "number", "0")]),
    _block("c.float", "Variables", "a decimal number", "double @name@ = @value@;",
           [_slot("name", "name", "name", "average"), _slot("value", "value", "text", "0.0")]),
    _block("c.char", "Variables", "one character", "char @name@ = @value@;",
           [_slot("name", "name", "name", "grade"), _slot("value", "value", "text", "'A'")]),
    _block("c.text", "Variables", "a piece of text",
           "char @name@[@size@] = @value@;",
           [_slot("name", "name", "name", "title"),
            _slot("size", "room for", "number", "64"),
            _slot("value", "text", "string", "Hello")]),
    _block("c.const_int", "Variables", "a number that never changes",
           "const int @name@ = @value@;",
           [_slot("name", "name", "name", "LIMIT"), _slot("value", "value", "number", "100")]),
    _block("c.assign", "Variables", "change a value", "@name@ = @value@;",
           [_slot("name", "name", "name", "total"), _slot("value", "value", "text", "1")]),
    _block("c.increase", "Variables", "add to a number", "@name@ += @amount@;",
           [_slot("name", "name", "name", "total"), _slot("amount", "by", "number", "1")]),
    _block("c.decrease", "Variables", "take away from a number",
           "@name@ -= @amount@;",
           [_slot("name", "name", "name", "lives"), _slot("amount", "by", "number", "1")]),
    _block("c.plus_plus", "Variables", "add one", "@name@++;",
           [_slot("name", "name", "name", "count")]),
    _block("c.minus_minus", "Variables", "take one away", "@name@--;",
           [_slot("name", "name", "name", "count")]),
    _block("c.swap_helper", "Variables", "swap two numbers with a spare",
           "{ int spare = @a@; @a@ = @b@; @b@ = spare; }",
           [_slot("a", "first", "name", "x"), _slot("b", "second", "name", "y")]),

    # -- Maths -------------------------------------------------------------
    _block("c.add", "Maths", "add", "@into@ = @a@ + @b@;",
           [_slot("into", "into", "name", "total"),
            _slot("a", "first", "text", "a"), _slot("b", "second", "text", "b")]),
    _block("c.subtract", "Maths", "take away", "@into@ = @a@ - @b@;",
           [_slot("into", "into", "name", "left"),
            _slot("a", "from", "text", "a"), _slot("b", "take", "text", "b")]),
    _block("c.multiply", "Maths", "multiply", "@into@ = @a@ * @b@;",
           [_slot("into", "into", "name", "area"),
            _slot("a", "first", "text", "width"), _slot("b", "second", "text", "height")]),
    _block("c.divide", "Maths", "divide", "@into@ = @a@ / @b@;",
           [_slot("into", "into", "name", "share"),
            _slot("a", "divide", "text", "total"), _slot("b", "by", "text", "count")],
           about="Two whole numbers divide to a whole number in C: 7 / 2 is 3."),
    _block("c.divide_decimal", "Maths", "divide, keeping the decimals",
           "@into@ = (double) @a@ / @b@;",
           [_slot("into", "into", "name", "average"),
            _slot("a", "divide", "text", "total"), _slot("b", "by", "text", "count")]),
    _block("c.remainder", "Maths", "the remainder", "@into@ = @a@ % @b@;",
           [_slot("into", "into", "name", "rest"),
            _slot("a", "divide", "text", "n"), _slot("b", "by", "text", "3")]),
    _block("c.power", "Maths", "raise to a power", "@into@ = pow(@a@, @b@);",
           [_slot("into", "into", "name", "result"),
            _slot("a", "number", "text", "2"), _slot("b", "to the power of", "text", "8")],
           about="Needs math.h."),
    _block("c.sqrt", "Maths", "square root", "@into@ = sqrt(@value@);",
           [_slot("into", "into", "name", "root"), _slot("value", "of", "text", "area")]),
    _block("c.absolute", "Maths", "make positive", "@into@ = abs(@value@);",
           [_slot("into", "into", "name", "size"), _slot("value", "of", "text", "difference")]),
    _block("c.round_down", "Maths", "round down", "@into@ = floor(@value@);",
           [_slot("into", "into", "name", "whole"), _slot("value", "of", "text", "price")]),
    _block("c.round_up", "Maths", "round up", "@into@ = ceil(@value@);",
           [_slot("into", "into", "name", "whole"), _slot("value", "of", "text", "price")]),
    _block("c.round", "Maths", "round to the nearest", "@into@ = round(@value@);",
           [_slot("into", "into", "name", "whole"), _slot("value", "of", "text", "score")]),
    _block("c.random_seed", "Maths", "start the random numbers off",
           "srand((unsigned) time(NULL));",
           about="Once, near the top of main. Needs stdlib.h and time.h."),
    _block("c.random", "Maths", "a random number in a range",
           "@into@ = @low@ + rand() % (@high@ - @low@ + 1);",
           [_slot("into", "into", "name", "roll"),
            _slot("low", "from", "number", "1"), _slot("high", "to", "number", "6")]),

    # -- Text --------------------------------------------------------------
    _block("c.strlen", "Text", "how long a piece of text is",
           "@into@ = strlen(@text@);",
           [_slot("into", "into", "name", "length"), _slot("text", "of", "text", "name")]),
    _block("c.strcpy", "Text", "copy text into a variable",
           "strcpy(@into@, @from@);",
           [_slot("into", "into", "name", "buffer"), _slot("from", "from", "text", "name")]),
    _block("c.strcpy_text", "Text", "put text into a variable",
           "strcpy(@into@, @text@);",
           [_slot("into", "into", "name", "buffer"), _slot("text", "text", "string", "Hello")]),
    _block("c.strcat", "Text", "join text onto the end",
           "strcat(@into@, @from@);",
           [_slot("into", "onto", "name", "line"), _slot("from", "add", "text", "word")]),
    _block("c.strcat_text", "Text", "join a piece of text onto the end",
           "strcat(@into@, @text@);",
           [_slot("into", "onto", "name", "line"), _slot("text", "add", "string", "!")]),
    _block("c.strcmp", "Text", "are two pieces of text the same",
           "if (strcmp(@a@, @b@) == 0) {",
           [_slot("a", "first", "text", "answer"), _slot("b", "second", "text", "expected")],
           close="}", wrap=True),
    _block("c.strchr", "Text", "find a character in text",
           "@into@ = strchr(@text@, @letter@);",
           [_slot("into", "into", "name", "found"),
            _slot("text", "in", "text", "line"), _slot("letter", "character", "text", "','")]),
    _block("c.strstr", "Text", "find text inside text",
           "@into@ = strstr(@text@, @needle@);",
           [_slot("into", "into", "name", "found"),
            _slot("text", "in", "text", "line"), _slot("needle", "looking for", "text", "word")]),
    _block("c.sprintf", "Text", "build a piece of text",
           'sprintf(@into@, "@format@", @values@);',
           [_slot("into", "into", "name", "line"),
            _slot("format", "pattern, with %d and %s in it", "inline", "%s scored %d"),
            _slot("values", "values, comma separated", "text", "name, score")]),
    _block("c.to_upper", "Text", "make a character upper case",
           "@into@ = toupper(@value@);",
           [_slot("into", "into", "name", "letter"), _slot("value", "of", "text", "c")]),
    _block("c.to_lower", "Text", "make a character lower case",
           "@into@ = tolower(@value@);",
           [_slot("into", "into", "name", "letter"), _slot("value", "of", "text", "c")]),
    _block("c.is_digit", "Text", "is this character a digit",
           "if (isdigit(@value@)) {",
           [_slot("value", "character", "text", "c")], close="}", wrap=True),
    _block("c.atoi", "Text", "turn text into a number",
           "@into@ = atoi(@text@);",
           [_slot("into", "into", "name", "number"), _slot("text", "from", "text", "word")]),

    # -- Arrays ------------------------------------------------------------
    _block("c.array", "Arrays", "a list of numbers",
           "int @name@[@size@];",
           [_slot("name", "name", "name", "scores"), _slot("size", "how many", "number", "10")]),
    _block("c.array_values", "Arrays", "a list of numbers, filled in",
           "int @name@[] = {@values@};",
           [_slot("name", "name", "name", "scores"),
            _slot("values", "values, comma separated", "text", "3, 1, 4, 1, 5")]),
    _block("c.array_set", "Arrays", "put a value in a slot",
           "@name@[@index@] = @value@;",
           [_slot("name", "list", "name", "scores"),
            _slot("index", "slot", "text", "0"), _slot("value", "value", "text", "10")],
           about="Slots count from 0."),
    _block("c.array_get", "Arrays", "take a value out of a slot",
           "@into@ = @name@[@index@];",
           [_slot("into", "into", "name", "value"),
            _slot("name", "list", "name", "scores"), _slot("index", "slot", "text", "0")]),
    _block("c.array_grid", "Arrays", "a grid of numbers",
           "int @name@[@rows@][@columns@];",
           [_slot("name", "name", "name", "grid"),
            _slot("rows", "rows", "number", "3"), _slot("columns", "columns", "number", "3")]),
    _block("c.array_grid_set", "Arrays", "put a value in a grid square",
           "@name@[@row@][@column@] = @value@;",
           [_slot("name", "grid", "name", "grid"),
            _slot("row", "row", "text", "0"), _slot("column", "column", "text", "0"),
            _slot("value", "value", "text", "1")]),
    _block("c.array_walk", "Arrays", "do something with every value",
           "for (int @index@ = 0; @index@ < @size@; @index@++) {",
           [_slot("index", "counter", "name", "i"), _slot("size", "how many", "text", "10")],
           close="}", wrap=True, empty=";"),
    _block("c.array_total", "Arrays", "add up a list",
           "for (int i = 0; i < @size@; i++) { @into@ += @name@[i]; }",
           [_slot("into", "into", "name", "total"),
            _slot("name", "list", "name", "scores"), _slot("size", "how many", "text", "10")]),

    # -- Logic -------------------------------------------------------------
    _block("c.if", "Logic", "if something is true", "if (@test@) {",
           [_slot("test", "test", "text", "score > 10")], close="}", wrap=True, empty=";"),
    _block("c.if_equal", "Logic", "if two things are the same",
           "if (@a@ == @b@) {",
           [_slot("a", "first", "text", "answer"), _slot("b", "second", "text", "42")],
           close="}", wrap=True, empty=";"),
    _block("c.else", "Logic", "otherwise", "} else {", close="}", wrap=True, empty=";",
           about="Put this straight after an if block.",
           chain_after=("c.if", "c.if_equal", "c.and", "c.or", "c.not",
                        "c.strcmp", "c.is_digit", "c.check_null", "c.else_if")),
    _block("c.else_if", "Logic", "otherwise, if", "} else if (@test@) {",
           [_slot("test", "test", "text", "score > 5")], close="}", wrap=True, empty=";",
           chain_after=("c.if", "c.if_equal", "c.and", "c.or", "c.not",
                        "c.strcmp", "c.is_digit", "c.check_null", "c.else_if")),
    _block("c.and", "Logic", "if both are true", "if (@a@ && @b@) {",
           [_slot("a", "first", "text", "ready"), _slot("b", "second", "text", "count > 0")],
           close="}", wrap=True, empty=";"),
    _block("c.or", "Logic", "if either is true", "if (@a@ || @b@) {",
           [_slot("a", "first", "text", "done"), _slot("b", "second", "text", "count == 0")],
           close="}", wrap=True, empty=";"),
    _block("c.not", "Logic", "if something is not true", "if (!@test@) {",
           [_slot("test", "test", "text", "found")], close="}", wrap=True, empty=";"),
    _block("c.switch", "Logic", "choose between values", "switch (@value@) {",
           [_slot("value", "on", "text", "choice")], close="}", wrap=True,
           empty="default: break;"),
    _block("c.case", "Logic", "one of the choices", "case @value@:",
           [_slot("value", "when it is", "text", "1")], wrap=True, empty="break;"),
    _block("c.case_break", "Logic", "stop here", "break;"),
    _block("c.case_default", "Logic", "anything else", "default:",
           wrap=True, empty="break;"),

    # -- Loops -------------------------------------------------------------
    _block("c.for", "Loops", "count from one number to another",
           "for (int @name@ = @from@; @name@ < @to@; @name@++) {",
           [_slot("name", "counter", "name", "i"),
            _slot("from", "from", "number", "0"), _slot("to", "up to", "text", "10")],
           close="}", wrap=True, empty=";"),
    _block("c.for_down", "Loops", "count backwards",
           "for (int @name@ = @from@; @name@ > @to@; @name@--) {",
           [_slot("name", "counter", "name", "i"),
            _slot("from", "from", "text", "10"), _slot("to", "down to", "number", "0")],
           close="}", wrap=True, empty=";"),
    _block("c.while", "Loops", "keep going while something is true",
           "while (@test@) {",
           [_slot("test", "test", "text", "running")], close="}", wrap=True, empty=";"),
    _block("c.do_while", "Loops", "do it once, then keep going", "do {",
           [_slot("test", "while", "text", "answer != 0")],
           close="} while (@test@);", wrap=True, empty=";"),
    _block("c.forever", "Loops", "keep going until told to stop",
           "while (1) {", close="}", wrap=True, empty="break;"),
    _block("c.break", "Loops", "stop the loop", "break;"),
    _block("c.continue", "Loops", "skip to the next turn", "continue;"),

    # -- Functions ---------------------------------------------------------
    _block("c.function", "Functions", "a piece of code with a name",
           "@type@ @name@(@arguments@) {",
           [_slot("type", "gives back", "choice", "int",
                  ["int", "double", "char", "void", "char *"]),
            _slot("name", "name", "name", "greet"),
            _slot("arguments", "takes", "text", "void")],
           close="}", wrap=True, empty="return 0;",
           about="Write it above main, or C will not know it exists yet."),
    _block("c.function_void", "Functions", "a piece of code that gives nothing back",
           "void @name@(@arguments@) {",
           [_slot("name", "name", "name", "show"),
            _slot("arguments", "takes", "text", "int value")],
           close="}", wrap=True, empty=";"),
    _block("c.return", "Functions", "give a value back", "return @value@;",
           [_slot("value", "value", "text", "result")]),
    _block("c.return_nothing", "Functions", "stop here", "return;"),
    _block("c.call", "Functions", "use a function", "@name@(@arguments@);",
           [_slot("name", "name", "name", "show"), _slot("arguments", "with", "text", "1")]),
    _block("c.call_into", "Functions", "use a function and keep the answer",
           "@into@ = @name@(@arguments@);",
           [_slot("into", "into", "name", "result"),
            _slot("name", "name", "name", "add"), _slot("arguments", "with", "text", "2, 3")]),
    _block("c.prototype", "Functions", "promise a function exists",
           "@type@ @name@(@arguments@);",
           [_slot("type", "gives back", "choice", "int", ["int", "double", "char", "void"]),
            _slot("name", "name", "name", "add"),
            _slot("arguments", "takes", "text", "int a, int b")],
           about="Lets main use a function written below it."),

    # -- Structures --------------------------------------------------------
    _block("c.struct", "Structures", "a shape with named parts",
           "struct @name@ {",
           [_slot("name", "name", "name", "Point")],
           close="};", wrap=True, empty="int x;"),
    _block("c.struct_field", "Structures", "one part of a shape",
           "@type@ @name@;",
           [_slot("type", "kind", "choice", "int", ["int", "double", "char", "char *"]),
            _slot("name", "name", "name", "x")]),
    _block("c.struct_text_field", "Structures", "a part that holds text",
           "char @name@[@size@];",
           [_slot("name", "name", "name", "title"), _slot("size", "room for", "number", "64")]),
    _block("c.struct_var", "Structures", "one of a shape",
           "struct @type@ @name@;",
           [_slot("type", "shape", "name", "Point"), _slot("name", "name", "name", "here")]),
    _block("c.struct_set", "Structures", "set part of a shape",
           "@name@.@field@ = @value@;",
           [_slot("name", "of", "name", "here"), _slot("field", "part", "name", "x"),
            _slot("value", "value", "text", "3")]),
    _block("c.struct_get", "Structures", "read part of a shape",
           "@into@ = @name@.@field@;",
           [_slot("into", "into", "name", "x"),
            _slot("name", "of", "name", "here"), _slot("field", "part", "name", "x")]),
    _block("c.struct_array", "Structures", "a list of shapes",
           "struct @type@ @name@[@size@];",
           [_slot("type", "shape", "name", "Point"), _slot("name", "name", "name", "points"),
            _slot("size", "how many", "number", "10")]),

    # -- Pointers and memory -----------------------------------------------
    _block("c.pointer", "Pointers", "an address of something",
           "@type@ *@name@ = &@target@;",
           [_slot("type", "kind", "choice", "int", ["int", "double", "char"]),
            _slot("name", "name", "name", "p"), _slot("target", "of", "name", "total")]),
    _block("c.pointer_read", "Pointers", "read what an address points at",
           "@into@ = *@name@;",
           [_slot("into", "into", "name", "value"), _slot("name", "address", "name", "p")]),
    _block("c.pointer_write", "Pointers", "write through an address",
           "*@name@ = @value@;",
           [_slot("name", "address", "name", "p"), _slot("value", "value", "text", "10")]),
    _block("c.pointer_null", "Pointers", "an address of nothing",
           "@type@ *@name@ = NULL;",
           [_slot("type", "kind", "choice", "int", ["int", "double", "char"]),
            _slot("name", "name", "name", "p")]),
    _block("c.malloc", "Pointers", "ask for some memory",
           "@name@ = malloc(@count@ * sizeof(@type@));",
           [_slot("name", "into", "name", "buffer"),
            _slot("count", "how many", "text", "100"),
            _slot("type", "of", "choice", "int", ["int", "double", "char"])],
           about="Needs stdlib.h. Free it when you are done."),
    _block("c.free", "Pointers", "give the memory back", "free(@name@);",
           [_slot("name", "address", "name", "buffer")]),
    _block("c.check_null", "Pointers", "if asking for memory failed",
           "if (@name@ == NULL) {",
           [_slot("name", "address", "name", "buffer")],
           close="}", wrap=True, empty="return 1;"),
]


# ---------------------------------------------------------------------------
# Go
# ---------------------------------------------------------------------------
#
# Indented with a tab, because gofmt does and every Go programmer's eye is
# calibrated to it. Written against `pycmd_langs.go_interp`, which runs fmt,
# strings, strconv, math, sort, os and goroutines with channels.

GO = [
    # -- Basics ------------------------------------------------------------
    _block("go.package", "Basics", "the top of the file", "package main",
           about="Every Go file starts with this. A program is package main."),
    _block("go.import", "Basics", "use a standard package", 'import "@name@"',
           [_slot("name", "package", "choice", "fmt",
                  ["fmt", "strings", "strconv", "math", "sort", "os", "time", "errors"])]),
    _block("go.import_group", "Basics", "use several packages", "import (",
           close=")", wrap=True, empty='"fmt"'),
    _block("go.import_line", "Basics", "one package in the group", '"@name@"',
           [_slot("name", "package", "choice", "fmt",
                  ["fmt", "strings", "strconv", "math", "sort", "os", "time", "errors"])]),
    _block("go.main", "Basics", "the program itself", "func main() {",
           close="}", wrap=True, empty="// your code here",
           about="Where a Go program starts."),
    _block("go.print", "Basics", "print text", "fmt.Println(@text@)",
           [_slot("text", "text", "string", "Hello")]),
    _block("go.print_value", "Basics", "print a value", "fmt.Println(@value@)",
           [_slot("value", "value", "text", "total")]),
    _block("go.print_labelled", "Basics", "print a label and a value",
           "fmt.Println(@label@, @value@)",
           [_slot("label", "label", "string", "total:"),
            _slot("value", "value", "text", "total")]),
    _block("go.printf", "Basics", "print a sentence with values in it",
           'fmt.Printf("@format@\\n", @values@)',
           [_slot("format", "pattern, with %s and %d in it", "inline", "%s scored %d"),
            _slot("values", "values, comma separated", "text", "name, score")]),
    _block("go.print_no_newline", "Basics", "print without a new line",
           "fmt.Print(@text@)",
           [_slot("text", "text", "string", "Loading")]),
    _block("go.comment", "Basics", "a note to yourself", "// @text@",
           [_slot("text", "note", "text", "what this part does")]),
    _block("go.blank", "Basics", "an empty line", ""),
    _block("go.read_line", "Basics", "read a line that was typed",
           "fmt.Scanln(&@name@)",
           [_slot("name", "into", "name", "answer")]),
    _block("go.exit", "Basics", "stop the program", "os.Exit(@code@)",
           [_slot("code", "with code", "number", "0")]),

    # -- Variables ---------------------------------------------------------
    _block("go.short", "Variables", "a new variable", "@name@ := @value@",
           [_slot("name", "name", "name", "total"), _slot("value", "value", "text", "0")],
           about="Go works out what kind it is from the value."),
    _block("go.short_text", "Variables", "a new piece of text",
           "@name@ := @text@",
           [_slot("name", "name", "name", "title"), _slot("text", "text", "string", "Hello")]),
    _block("go.short_number", "Variables", "a new number", "@name@ := @value@",
           [_slot("name", "name", "name", "score"), _slot("value", "value", "number", "0")]),
    _block("go.short_bool", "Variables", "a new true or false",
           "@name@ := @value@",
           [_slot("name", "name", "name", "ready"),
            _slot("value", "value", "choice", "true", ["true", "false"])]),
    _block("go.var", "Variables", "a variable of a kind you choose",
           "var @name@ @type@",
           [_slot("name", "name", "name", "total"),
            _slot("type", "kind", "choice", "int",
                  ["int", "float64", "string", "bool", "rune", "byte"])]),
    _block("go.const", "Variables", "a value that never changes",
           "const @name@ = @value@",
           [_slot("name", "name", "name", "Limit"), _slot("value", "value", "text", "100")]),
    _block("go.assign", "Variables", "change a value", "@name@ = @value@",
           [_slot("name", "name", "name", "total"), _slot("value", "value", "text", "1")]),
    _block("go.increase", "Variables", "add to a number", "@name@ += @amount@",
           [_slot("name", "name", "name", "total"), _slot("amount", "by", "number", "1")]),
    _block("go.decrease", "Variables", "take away from a number",
           "@name@ -= @amount@",
           [_slot("name", "name", "name", "lives"), _slot("amount", "by", "number", "1")]),
    _block("go.plus_plus", "Variables", "add one", "@name@++",
           [_slot("name", "name", "name", "count")]),
    _block("go.swap", "Variables", "swap two values", "@a@, @b@ = @b@, @a@",
           [_slot("a", "first", "name", "x"), _slot("b", "second", "name", "y")]),

    # -- Maths -------------------------------------------------------------
    _block("go.add", "Maths", "add", "@into@ := @a@ + @b@",
           [_slot("into", "into", "name", "total"),
            _slot("a", "first", "text", "a"), _slot("b", "second", "text", "b")]),
    _block("go.subtract", "Maths", "take away", "@into@ := @a@ - @b@",
           [_slot("into", "into", "name", "left"),
            _slot("a", "from", "text", "a"), _slot("b", "take", "text", "b")]),
    _block("go.multiply", "Maths", "multiply", "@into@ := @a@ * @b@",
           [_slot("into", "into", "name", "area"),
            _slot("a", "first", "text", "width"), _slot("b", "second", "text", "height")]),
    _block("go.divide", "Maths", "divide", "@into@ := @a@ / @b@",
           [_slot("into", "into", "name", "share"),
            _slot("a", "divide", "text", "total"), _slot("b", "by", "text", "count")],
           about="Whole numbers divide to a whole number."),
    _block("go.remainder", "Maths", "the remainder", "@into@ := @a@ % @b@",
           [_slot("into", "into", "name", "rest"),
            _slot("a", "divide", "text", "n"), _slot("b", "by", "text", "3")]),
    _block("go.sqrt", "Maths", "square root", "@into@ := math.Sqrt(@value@)",
           [_slot("into", "into", "name", "root"), _slot("value", "of", "text", "area")]),
    _block("go.power", "Maths", "raise to a power",
           "@into@ := math.Pow(@a@, @b@)",
           [_slot("into", "into", "name", "result"),
            _slot("a", "number", "text", "2"), _slot("b", "to the power of", "text", "8")]),
    _block("go.absolute", "Maths", "make positive", "@into@ := math.Abs(@value@)",
           [_slot("into", "into", "name", "size"), _slot("value", "of", "text", "difference")]),
    _block("go.round_down", "Maths", "round down", "@into@ := math.Floor(@value@)",
           [_slot("into", "into", "name", "whole"), _slot("value", "of", "text", "price")]),
    _block("go.round_up", "Maths", "round up", "@into@ := math.Ceil(@value@)",
           [_slot("into", "into", "name", "whole"), _slot("value", "of", "text", "price")]),
    _block("go.max", "Maths", "the larger of two", "@into@ := math.Max(@a@, @b@)",
           [_slot("into", "into", "name", "best"),
            _slot("a", "first", "text", "a"), _slot("b", "second", "text", "b")]),
    _block("go.min", "Maths", "the smaller of two", "@into@ := math.Min(@a@, @b@)",
           [_slot("into", "into", "name", "worst"),
            _slot("a", "first", "text", "a"), _slot("b", "second", "text", "b")]),
    _block("go.to_number", "Maths", "turn text into a number",
           "@into@, _ := strconv.Atoi(@text@)",
           [_slot("into", "into", "name", "number"), _slot("text", "from", "text", "word")]),
    _block("go.to_text", "Maths", "turn a number into text",
           "@into@ := strconv.Itoa(@value@)",
           [_slot("into", "into", "name", "word"), _slot("value", "of", "text", "score")]),

    # -- Text --------------------------------------------------------------
    _block("go.length", "Text", "how long something is", "@into@ := len(@value@)",
           [_slot("into", "into", "name", "length"), _slot("value", "of", "text", "name")]),
    _block("go.upper", "Text", "make text upper case",
           "@into@ := strings.ToUpper(@text@)",
           [_slot("into", "into", "name", "shout"), _slot("text", "of", "text", "name")]),
    _block("go.lower", "Text", "make text lower case",
           "@into@ := strings.ToLower(@text@)",
           [_slot("into", "into", "name", "quiet"), _slot("text", "of", "text", "name")]),
    _block("go.trim", "Text", "take the spaces off the ends",
           "@into@ := strings.TrimSpace(@text@)",
           [_slot("into", "into", "name", "clean"), _slot("text", "of", "text", "line")]),
    _block("go.contains", "Text", "does text contain something",
           "if strings.Contains(@text@, @needle@) {",
           [_slot("text", "in", "text", "line"), _slot("needle", "looking for", "string", "yes")],
           close="}", wrap=True),
    _block("go.starts_with", "Text", "does text start with something",
           "if strings.HasPrefix(@text@, @needle@) {",
           [_slot("text", "in", "text", "line"), _slot("needle", "starts with", "string", "http")],
           close="}", wrap=True),
    _block("go.replace", "Text", "swap one piece of text for another",
           "@into@ := strings.ReplaceAll(@text@, @old@, @new@)",
           [_slot("into", "into", "name", "fixed"), _slot("text", "in", "text", "line"),
            _slot("old", "replace", "string", "a"), _slot("new", "with", "string", "b")]),
    _block("go.split", "Text", "cut text into pieces",
           "@into@ := strings.Split(@text@, @separator@)",
           [_slot("into", "into", "name", "parts"), _slot("text", "of", "text", "line"),
            _slot("separator", "cut at", "string", ",")]),
    _block("go.join", "Text", "join pieces into one piece of text",
           "@into@ := strings.Join(@parts@, @separator@)",
           [_slot("into", "into", "name", "line"), _slot("parts", "of", "text", "parts"),
            _slot("separator", "with", "string", ", ")]),
    _block("go.repeat", "Text", "repeat text",
           "@into@ := strings.Repeat(@text@, @times@)",
           [_slot("into", "into", "name", "line"), _slot("text", "of", "string", "-"),
            _slot("times", "times", "number", "20")]),
    _block("go.index", "Text", "where a piece of text is",
           "@into@ := strings.Index(@text@, @needle@)",
           [_slot("into", "into", "name", "at"), _slot("text", "in", "text", "line"),
            _slot("needle", "looking for", "string", "=")],
           about="-1 when it is not there."),
    _block("go.fields", "Text", "cut text at the spaces",
           "@into@ := strings.Fields(@text@)",
           [_slot("into", "into", "name", "words"), _slot("text", "of", "text", "line")]),

    # -- Slices ------------------------------------------------------------
    _block("go.slice", "Slices", "a list", "@name@ := []@type@{@values@}",
           [_slot("name", "name", "name", "scores"),
            _slot("type", "of", "choice", "int", ["int", "string", "float64", "bool"]),
            _slot("values", "values, comma separated", "text", "3, 1, 4")]),
    _block("go.slice_empty", "Slices", "an empty list",
           "@name@ := []@type@{}",
           [_slot("name", "name", "name", "items"),
            _slot("type", "of", "choice", "string", ["int", "string", "float64", "bool"])]),
    _block("go.slice_append", "Slices", "add to the end",
           "@name@ = append(@name@, @value@)",
           [_slot("name", "list", "name", "items"), _slot("value", "value", "text", "1")]),
    _block("go.slice_get", "Slices", "take a value out",
           "@into@ := @name@[@index@]",
           [_slot("into", "into", "name", "value"), _slot("name", "list", "name", "items"),
            _slot("index", "at", "text", "0")]),
    _block("go.slice_set", "Slices", "put a value in",
           "@name@[@index@] = @value@",
           [_slot("name", "list", "name", "items"), _slot("index", "at", "text", "0"),
            _slot("value", "value", "text", "1")]),
    _block("go.slice_length", "Slices", "how many are in it",
           "@into@ := len(@name@)",
           [_slot("into", "into", "name", "count"), _slot("name", "list", "name", "items")]),
    _block("go.slice_part", "Slices", "a piece of a list",
           "@into@ := @name@[@from@:@to@]",
           [_slot("into", "into", "name", "part"), _slot("name", "of", "name", "items"),
            _slot("from", "from", "text", "0"), _slot("to", "up to", "text", "3")]),
    _block("go.slice_sort", "Slices", "put numbers in order",
           "sort.Ints(@name@)",
           [_slot("name", "list", "name", "scores")]),
    _block("go.slice_sort_text", "Slices", "put text in order",
           "sort.Strings(@name@)",
           [_slot("name", "list", "name", "names")]),
    _block("go.range", "Slices", "do something with every value",
           "for @index@, @value@ := range @name@ {",
           [_slot("index", "position", "name", "i"), _slot("value", "value", "name", "item"),
            _slot("name", "of", "name", "items")],
           close="}", wrap=True, empty="_ = i"),
    _block("go.range_values", "Slices", "do something with every value, ignoring position",
           "for _, @value@ := range @name@ {",
           [_slot("value", "value", "name", "item"), _slot("name", "of", "name", "items")],
           close="}", wrap=True, empty="// your code here"),

    # -- Maps --------------------------------------------------------------
    _block("go.map", "Maps", "a lookup table",
           "@name@ := map[@key@]@value@{}",
           [_slot("name", "name", "name", "ages"),
            _slot("key", "looked up by", "choice", "string", ["string", "int"]),
            _slot("value", "holding", "choice", "int", ["int", "string", "float64", "bool"])]),
    _block("go.map_set", "Maps", "put something in",
           "@name@[@key@] = @value@",
           [_slot("name", "table", "name", "ages"), _slot("key", "under", "string", "ada"),
            _slot("value", "value", "text", "36")]),
    _block("go.map_get", "Maps", "take something out",
           "@into@ := @name@[@key@]",
           [_slot("into", "into", "name", "age"), _slot("name", "table", "name", "ages"),
            _slot("key", "under", "string", "ada")]),
    _block("go.map_has", "Maps", "if something is in there",
           "if @into@, ok := @name@[@key@]; ok {",
           [_slot("into", "into", "name", "age"), _slot("name", "table", "name", "ages"),
            _slot("key", "under", "string", "ada")],
           close="}", wrap=True, empty="_ = age"),
    _block("go.map_delete", "Maps", "take something out for good",
           "delete(@name@, @key@)",
           [_slot("name", "table", "name", "ages"), _slot("key", "under", "string", "ada")]),
    _block("go.map_range", "Maps", "do something with every pair",
           "for @key@, @value@ := range @name@ {",
           [_slot("key", "key", "name", "key"), _slot("value", "value", "name", "value"),
            _slot("name", "of", "name", "ages")],
           close="}", wrap=True, empty="_ = key"),

    # -- Logic -------------------------------------------------------------
    _block("go.if", "Logic", "if something is true", "if @test@ {",
           [_slot("test", "test", "text", "score > 10")], close="}", wrap=True,
           empty="// your code here"),
    _block("go.if_equal", "Logic", "if two things are the same", "if @a@ == @b@ {",
           [_slot("a", "first", "text", "answer"), _slot("b", "second", "text", "42")],
           close="}", wrap=True, empty="// your code here"),
    _block("go.else", "Logic", "otherwise", "} else {", close="}", wrap=True,
           empty="// your code here", about="Put this straight after an if block.",
           chain_after=("go.if", "go.if_equal", "go.and", "go.or", "go.not",
                        "go.contains", "go.starts_with", "go.map_has",
                        "go.if_error", "go.else_if")),
    _block("go.else_if", "Logic", "otherwise, if", "} else if @test@ {",
           [_slot("test", "test", "text", "score > 5")], close="}", wrap=True,
           empty="// your code here",
           chain_after=("go.if", "go.if_equal", "go.and", "go.or", "go.not",
                        "go.contains", "go.starts_with", "go.map_has",
                        "go.if_error", "go.else_if")),
    _block("go.and", "Logic", "if both are true", "if @a@ && @b@ {",
           [_slot("a", "first", "text", "ready"), _slot("b", "second", "text", "count > 0")],
           close="}", wrap=True, empty="// your code here"),
    _block("go.or", "Logic", "if either is true", "if @a@ || @b@ {",
           [_slot("a", "first", "text", "done"), _slot("b", "second", "text", "count == 0")],
           close="}", wrap=True, empty="// your code here"),
    _block("go.not", "Logic", "if something is not true", "if !@test@ {",
           [_slot("test", "test", "text", "found")], close="}", wrap=True,
           empty="// your code here"),
    _block("go.switch", "Logic", "choose between values", "switch @value@ {",
           [_slot("value", "on", "text", "choice")], close="}", wrap=True,
           empty="default:"),
    _block("go.case", "Logic", "one of the choices", "case @value@:",
           [_slot("value", "when it is", "text", "1")], wrap=True,
           empty="// your code here"),
    _block("go.case_default", "Logic", "anything else", "default:", wrap=True,
           empty="// your code here"),

    # -- Loops -------------------------------------------------------------
    _block("go.for", "Loops", "count from one number to another",
           "for @name@ := @from@; @name@ < @to@; @name@++ {",
           [_slot("name", "counter", "name", "i"),
            _slot("from", "from", "number", "0"), _slot("to", "up to", "text", "10")],
           close="}", wrap=True, empty="// your code here"),
    _block("go.while", "Loops", "keep going while something is true",
           "for @test@ {",
           [_slot("test", "test", "text", "running")], close="}", wrap=True,
           empty="break"),
    _block("go.forever", "Loops", "keep going until told to stop", "for {",
           close="}", wrap=True, empty="break"),
    _block("go.break", "Loops", "stop the loop", "break"),
    _block("go.continue", "Loops", "skip to the next turn", "continue"),

    # -- Functions ---------------------------------------------------------
    _block("go.func", "Functions", "a piece of code with a name",
           "func @name@(@arguments@) @returns@ {",
           [_slot("name", "name", "name", "greet"),
            _slot("arguments", "takes", "text", "name string"),
            _slot("returns", "gives back", "text", "string")],
           close="}", wrap=True, empty='return ""'),
    _block("go.func_nothing", "Functions", "a piece of code that gives nothing back",
           "func @name@(@arguments@) {",
           [_slot("name", "name", "name", "show"),
            _slot("arguments", "takes", "text", "value int")],
           close="}", wrap=True, empty="// your code here"),
    _block("go.return", "Functions", "give a value back", "return @value@",
           [_slot("value", "value", "text", "result")]),
    _block("go.return_nothing", "Functions", "stop here", "return"),
    _block("go.call", "Functions", "use a function", "@name@(@arguments@)",
           [_slot("name", "name", "name", "show"), _slot("arguments", "with", "text", "1")]),
    _block("go.call_into", "Functions", "use a function and keep the answer",
           "@into@ := @name@(@arguments@)",
           [_slot("into", "into", "name", "result"), _slot("name", "name", "name", "add"),
            _slot("arguments", "with", "text", "2, 3")]),
    _block("go.defer", "Functions", "do this when the function ends",
           "defer @call@",
           [_slot("call", "do", "text", "file.Close()")]),

    # -- Structs -----------------------------------------------------------
    _block("go.struct", "Structs", "a shape with named parts",
           "type @name@ struct {",
           [_slot("name", "name", "name", "Point")], close="}", wrap=True, empty="X int"),
    _block("go.struct_field", "Structs", "one part of a shape", "@name@ @type@",
           [_slot("name", "name", "name", "X"),
            _slot("type", "kind", "choice", "int", ["int", "string", "float64", "bool"])]),
    _block("go.struct_new", "Structs", "one of a shape",
           "@name@ := @type@{@values@}",
           [_slot("name", "name", "name", "here"), _slot("type", "shape", "name", "Point"),
            _slot("values", "parts, like X: 1", "text", "X: 1, Y: 2")]),
    _block("go.struct_set", "Structs", "set part of a shape",
           "@name@.@field@ = @value@",
           [_slot("name", "of", "name", "here"), _slot("field", "part", "name", "X"),
            _slot("value", "value", "text", "3")]),
    _block("go.struct_get", "Structs", "read part of a shape",
           "@into@ := @name@.@field@",
           [_slot("into", "into", "name", "x"), _slot("name", "of", "name", "here"),
            _slot("field", "part", "name", "X")]),
    _block("go.method", "Structs", "something a shape can do",
           "func (@receiver@ @type@) @name@(@arguments@) @returns@ {",
           [_slot("receiver", "called", "name", "p"), _slot("type", "on", "name", "Point"),
            _slot("name", "name", "name", "Describe"),
            _slot("arguments", "takes", "text", ""),
            _slot("returns", "gives back", "text", "string")],
           close="}", wrap=True, empty='return ""'),

    # -- Errors ------------------------------------------------------------
    _block("go.error_call", "Errors", "call something that can fail",
           "@into@, err := @call@",
           [_slot("into", "into", "name", "value"),
            _slot("call", "call", "text", "strconv.Atoi(word)")]),
    _block("go.if_error", "Errors", "if it failed", "if err != nil {",
           close="}", wrap=True, empty="return"),
    _block("go.print_error", "Errors", "say what went wrong",
           "fmt.Println(@label@, err)",
           [_slot("label", "label", "string", "could not do it:")]),
    _block("go.new_error", "Errors", "make an error",
           "@into@ := errors.New(@text@)",
           [_slot("into", "into", "name", "err"),
            _slot("text", "saying", "string", "that will not work")]),
    _block("go.errorf", "Errors", "make an error with values in it",
           '@into@ := fmt.Errorf("@format@", @values@)',
           [_slot("into", "into", "name", "err"),
            _slot("format", "pattern, with %s in it", "inline", "cannot read %s"),
            _slot("values", "values", "text", "name")]),

    # -- At the same time --------------------------------------------------
    _block("go.goroutine", "At the same time", "do this alongside everything else",
           "go @call@",
           [_slot("call", "do", "text", "worker(1)")],
           about="A goroutine. The program does not wait for it."),
    _block("go.channel", "At the same time", "a way to pass values between them",
           "@name@ := make(chan @type@)",
           [_slot("name", "name", "name", "results"),
            _slot("type", "carrying", "choice", "int", ["int", "string", "float64", "bool"])]),
    _block("go.channel_send", "At the same time", "put a value in",
           "@name@ <- @value@",
           [_slot("name", "channel", "name", "results"), _slot("value", "value", "text", "1")]),
    _block("go.channel_take", "At the same time", "take a value out",
           "@into@ := <-@name@",
           [_slot("into", "into", "name", "value"), _slot("name", "channel", "name", "results")]),
    _block("go.channel_range", "At the same time", "take every value as it arrives",
           "for @value@ := range @name@ {",
           [_slot("value", "value", "name", "item"), _slot("name", "channel", "name", "results")],
           close="}", wrap=True, empty="// your code here"),
    _block("go.channel_close", "At the same time", "say no more are coming",
           "close(@name@)",
           [_slot("name", "channel", "name", "results")]),
    _block("go.sleep", "At the same time", "wait a moment",
           "time.Sleep(@millis@ * time.Millisecond)",
           [_slot("millis", "milliseconds", "number", "100")]),
]


# ---------------------------------------------------------------------------
# Rust
# ---------------------------------------------------------------------------
#
# Four spaces, as rustfmt does. Written against `pycmd_langs.rust_interp`,
# which runs Vec, HashMap, Option, Result, structs, enums, traits and the
# iterator methods people actually reach for.

RUST = [
    # -- Basics ------------------------------------------------------------
    _block("rs.main", "Basics", "the program itself", "fn main() {",
           close="}", wrap=True, empty="// your code here",
           about="Where a Rust program starts."),
    _block("rs.print", "Basics", "print text", 'println!("@text@");',
           [_slot("text", "text", "inline", "Hello")]),
    _block("rs.print_value", "Basics", "print a value",
           'println!("{}", @value@);',
           [_slot("value", "value", "text", "total")]),
    _block("rs.print_labelled", "Basics", "print a label and a value",
           'println!("@label@ {}", @value@);',
           [_slot("label", "label", "inline", "total:"),
            _slot("value", "value", "text", "total")]),
    _block("rs.print_two", "Basics", "print two values",
           'println!("{} {}", @a@, @b@);',
           [_slot("a", "first", "text", "name"), _slot("b", "second", "text", "score")]),
    _block("rs.print_debug", "Basics", "print something the long way",
           'println!("{:?}", @value@);',
           [_slot("value", "value", "text", "items")],
           about="Works on lists and maps, which {} will not print."),
    _block("rs.print_no_newline", "Basics", "print without a new line",
           'print!("@text@");',
           [_slot("text", "text", "inline", "Loading")]),
    _block("rs.comment", "Basics", "a note to yourself", "// @text@",
           [_slot("text", "note", "text", "what this part does")]),
    _block("rs.blank", "Basics", "an empty line", ""),
    _block("rs.use", "Basics", "use something from the standard library",
           "use std::@path@;",
           [_slot("path", "path", "choice", "collections::HashMap",
                  ["collections::HashMap", "collections::HashSet",
                   "collections::VecDeque", "io", "io::Write", "fmt", "cmp::Ordering"])]),
    _block("rs.read_line", "Basics", "read a line that was typed",
           'let mut @name@ = String::new();',
           [_slot("name", "into", "name", "answer")],
           about="Then use the read block below it. Needs use std::io."),
    _block("rs.read_into", "Basics", "read what was typed into it",
           "std::io::stdin().read_line(&mut @name@).unwrap();",
           [_slot("name", "into", "name", "answer")]),

    # -- Variables ---------------------------------------------------------
    _block("rs.let", "Variables", "a value that never changes",
           "let @name@ = @value@;",
           [_slot("name", "name", "name", "total"), _slot("value", "value", "text", "0")]),
    _block("rs.let_mut", "Variables", "a value that changes",
           "let mut @name@ = @value@;",
           [_slot("name", "name", "name", "count"), _slot("value", "value", "text", "0")]),
    _block("rs.let_text", "Variables", "a piece of text",
           "let @name@ = String::from(@text@);",
           [_slot("name", "name", "name", "title"), _slot("text", "text", "string", "Hello")]),
    _block("rs.let_number", "Variables", "a number",
           "let @name@: @type@ = @value@;",
           [_slot("name", "name", "name", "score"),
            _slot("type", "kind", "choice", "i32", ["i32", "i64", "f64", "u32", "usize"]),
            _slot("value", "value", "number", "0")]),
    _block("rs.let_bool", "Variables", "true or false",
           "let mut @name@ = @value@;",
           [_slot("name", "name", "name", "ready"),
            _slot("value", "value", "choice", "true", ["true", "false"])]),
    _block("rs.const", "Variables", "a value fixed for the whole program",
           "const @name@: @type@ = @value@;",
           [_slot("name", "name", "name", "LIMIT"),
            _slot("type", "kind", "choice", "i32", ["i32", "i64", "f64", "usize"]),
            _slot("value", "value", "number", "100")]),
    _block("rs.assign", "Variables", "change a value", "@name@ = @value@;",
           [_slot("name", "name", "name", "count"), _slot("value", "value", "text", "1")]),
    _block("rs.increase", "Variables", "add to a number", "@name@ += @amount@;",
           [_slot("name", "name", "name", "total"), _slot("amount", "by", "number", "1")]),
    _block("rs.decrease", "Variables", "take away from a number",
           "@name@ -= @amount@;",
           [_slot("name", "name", "name", "lives"), _slot("amount", "by", "number", "1")]),

    # -- Maths -------------------------------------------------------------
    _block("rs.add", "Maths", "add", "let @into@ = @a@ + @b@;",
           [_slot("into", "into", "name", "total"),
            _slot("a", "first", "text", "a"), _slot("b", "second", "text", "b")]),
    _block("rs.subtract", "Maths", "take away", "let @into@ = @a@ - @b@;",
           [_slot("into", "into", "name", "left"),
            _slot("a", "from", "text", "a"), _slot("b", "take", "text", "b")]),
    _block("rs.multiply", "Maths", "multiply", "let @into@ = @a@ * @b@;",
           [_slot("into", "into", "name", "area"),
            _slot("a", "first", "text", "width"), _slot("b", "second", "text", "height")]),
    _block("rs.divide", "Maths", "divide", "let @into@ = @a@ / @b@;",
           [_slot("into", "into", "name", "share"),
            _slot("a", "divide", "text", "total"), _slot("b", "by", "text", "count")]),
    _block("rs.remainder", "Maths", "the remainder", "let @into@ = @a@ % @b@;",
           [_slot("into", "into", "name", "rest"),
            _slot("a", "divide", "text", "n"), _slot("b", "by", "text", "3")]),
    _block("rs.sqrt", "Maths", "square root",
           "let @into@ = (@value@ as f64).sqrt();",
           [_slot("into", "into", "name", "root"), _slot("value", "of", "text", "area")]),
    _block("rs.power", "Maths", "raise to a power",
           "let @into@ = @value@.pow(@times@);",
           [_slot("into", "into", "name", "result"), _slot("value", "number", "text", "2"),
            _slot("times", "to the power of", "number", "8")]),
    _block("rs.absolute", "Maths", "make positive", "let @into@ = @value@.abs();",
           [_slot("into", "into", "name", "size"), _slot("value", "of", "text", "difference")]),
    _block("rs.min", "Maths", "the smaller of two", "let @into@ = @a@.min(@b@);",
           [_slot("into", "into", "name", "smaller"),
            _slot("a", "first", "text", "a"), _slot("b", "second", "text", "b")]),
    _block("rs.max", "Maths", "the larger of two", "let @into@ = @a@.max(@b@);",
           [_slot("into", "into", "name", "larger"),
            _slot("a", "first", "text", "a"), _slot("b", "second", "text", "b")]),
    _block("rs.to_number", "Maths", "turn text into a number",
           "let @into@: @type@ = @text@.trim().parse().unwrap_or(@fallback@);",
           [_slot("into", "into", "name", "number"),
            _slot("type", "kind", "choice", "i32", ["i32", "i64", "f64", "u32", "usize"]),
            _slot("text", "from", "text", "answer"),
            _slot("fallback", "or", "number", "0")]),
    _block("rs.to_text", "Maths", "turn a number into text",
           "let @into@ = @value@.to_string();",
           [_slot("into", "into", "name", "word"), _slot("value", "of", "text", "score")]),
    _block("rs.cast", "Maths", "treat a number as another kind",
           "let @into@ = @value@ as @type@;",
           [_slot("into", "into", "name", "value"), _slot("value", "of", "text", "count"),
            _slot("type", "as", "choice", "f64", ["f64", "i32", "i64", "u32", "usize"])]),

    # -- Text --------------------------------------------------------------
    _block("rs.length", "Text", "how long text is", "let @into@ = @text@.len();",
           [_slot("into", "into", "name", "length"), _slot("text", "of", "text", "name")]),
    _block("rs.upper", "Text", "make text upper case",
           "let @into@ = @text@.to_uppercase();",
           [_slot("into", "into", "name", "shout"), _slot("text", "of", "text", "name")]),
    _block("rs.lower", "Text", "make text lower case",
           "let @into@ = @text@.to_lowercase();",
           [_slot("into", "into", "name", "quiet"), _slot("text", "of", "text", "name")]),
    _block("rs.trim", "Text", "take the spaces off the ends",
           "let @into@ = @text@.trim().to_string();",
           [_slot("into", "into", "name", "clean"), _slot("text", "of", "text", "line")]),
    _block("rs.push_str", "Text", "add text to the end",
           "@name@.push_str(@text@);",
           [_slot("name", "onto", "name", "line"), _slot("text", "add", "string", " more")]),
    _block("rs.format", "Text", "build a piece of text",
           'let @into@ = format!("@pattern@", @values@);',
           [_slot("into", "into", "name", "line"),
            _slot("pattern", "pattern, with {} in it", "inline", "{} scored {}"),
            _slot("values", "values, comma separated", "text", "name, score")]),
    _block("rs.contains", "Text", "if text contains something",
           "if @text@.contains(@needle@) {",
           [_slot("text", "in", "text", "line"), _slot("needle", "looking for", "string", "yes")],
           close="}", wrap=True, empty="// your code here"),
    _block("rs.starts_with", "Text", "if text starts with something",
           "if @text@.starts_with(@needle@) {",
           [_slot("text", "in", "text", "line"), _slot("needle", "starts with", "string", "http")],
           close="}", wrap=True, empty="// your code here"),
    _block("rs.replace", "Text", "swap one piece of text for another",
           "let @into@ = @text@.replace(@old@, @new@);",
           [_slot("into", "into", "name", "fixed"), _slot("text", "in", "text", "line"),
            _slot("old", "replace", "string", "a"), _slot("new", "with", "string", "b")]),
    _block("rs.split", "Text", "cut text into pieces",
           "let @into@: Vec<&str> = @text@.split(@separator@).collect();",
           [_slot("into", "into", "name", "parts"), _slot("text", "of", "text", "line"),
            _slot("separator", "cut at", "string", ",")]),
    _block("rs.chars", "Text", "do something with every character",
           "for @name@ in @text@.chars() {",
           [_slot("name", "character", "name", "c"), _slot("text", "of", "text", "word")],
           close="}", wrap=True, empty="// your code here"),

    # -- Lists -------------------------------------------------------------
    _block("rs.vec", "Lists", "a list", "let mut @name@ = vec![@values@];",
           [_slot("name", "name", "name", "scores"),
            _slot("values", "values, comma separated", "text", "3, 1, 4")]),
    _block("rs.vec_empty", "Lists", "an empty list",
           "let mut @name@: Vec<@type@> = Vec::new();",
           [_slot("name", "name", "name", "items"),
            _slot("type", "of", "choice", "i32", ["i32", "f64", "String", "bool"])]),
    _block("rs.vec_push", "Lists", "add to the end", "@name@.push(@value@);",
           [_slot("name", "list", "name", "items"), _slot("value", "value", "text", "1")]),
    _block("rs.vec_pop", "Lists", "take the last one off",
           "let @into@ = @name@.pop();",
           [_slot("into", "into", "name", "last"), _slot("name", "list", "name", "items")]),
    _block("rs.vec_get", "Lists", "take a value out",
           "let @into@ = @name@[@index@];",
           [_slot("into", "into", "name", "value"), _slot("name", "list", "name", "items"),
            _slot("index", "at", "text", "0")]),
    _block("rs.vec_len", "Lists", "how many are in it",
           "let @into@ = @name@.len();",
           [_slot("into", "into", "name", "count"), _slot("name", "list", "name", "items")]),
    _block("rs.vec_sort", "Lists", "put them in order", "@name@.sort();",
           [_slot("name", "list", "name", "items")]),
    _block("rs.vec_reverse", "Lists", "turn the order round", "@name@.reverse();",
           [_slot("name", "list", "name", "items")]),
    _block("rs.vec_contains", "Lists", "if a value is in there",
           "if @name@.contains(&@value@) {",
           [_slot("name", "list", "name", "items"), _slot("value", "value", "text", "1")],
           close="}", wrap=True, empty="// your code here"),
    _block("rs.vec_sum", "Lists", "add them all up",
           "let @into@: @type@ = @name@.iter().sum();",
           [_slot("into", "into", "name", "total"),
            _slot("type", "kind", "choice", "i32", ["i32", "i64", "f64"]),
            _slot("name", "of", "name", "scores")]),
    _block("rs.vec_map", "Lists", "make a new list from every value",
           "let @into@: Vec<@type@> = @name@.iter().map(|@each@| @expression@).collect();",
           [_slot("into", "into", "name", "doubled"),
            _slot("type", "of", "choice", "i32", ["i32", "i64", "f64", "String"]),
            _slot("name", "from", "name", "scores"),
            _slot("each", "each one called", "name", "n"),
            _slot("expression", "becomes", "text", "n * 2")]),
    _block("rs.vec_filter", "Lists", "keep only the ones that match",
           "let @into@: Vec<@type@> = @name@.iter().filter(|@each@| @test@).cloned().collect();",
           [_slot("into", "into", "name", "big"),
            _slot("type", "of", "choice", "i32", ["i32", "i64", "f64", "String"]),
            _slot("name", "from", "name", "scores"),
            _slot("each", "each one called", "name", "n"),
            _slot("test", "keep when", "text", "**n > 10")]),
    _block("rs.for_each", "Lists", "do something with every value",
           "for @name@ in &@list@ {",
           [_slot("name", "each one called", "name", "item"),
            _slot("list", "of", "name", "items")],
           close="}", wrap=True, empty="// your code here"),

    # -- Maps --------------------------------------------------------------
    _block("rs.map", "Maps", "a lookup table",
           "let mut @name@: HashMap<@key@, @value@> = HashMap::new();",
           [_slot("name", "name", "name", "ages"),
            _slot("key", "looked up by", "choice", "String", ["String", "&str", "i32"]),
            _slot("value", "holding", "choice", "i32", ["i32", "f64", "String", "bool"])],
           about="Needs use std::collections::HashMap."),
    _block("rs.map_insert", "Maps", "put something in",
           "@name@.insert(@key@, @value@);",
           [_slot("name", "table", "name", "ages"), _slot("key", "under", "text", 'String::from("ada")'),
            _slot("value", "value", "text", "36")]),
    _block("rs.map_get", "Maps", "take something out",
           "let @into@ = @name@.get(@key@);",
           [_slot("into", "into", "name", "age"), _slot("name", "table", "name", "ages"),
            _slot("key", "under", "string", "ada")]),
    _block("rs.map_has", "Maps", "if something is in there",
           "if @name@.contains_key(@key@) {",
           [_slot("name", "table", "name", "ages"), _slot("key", "under", "string", "ada")],
           close="}", wrap=True, empty="// your code here"),
    _block("rs.map_remove", "Maps", "take something out for good",
           "@name@.remove(@key@);",
           [_slot("name", "table", "name", "ages"), _slot("key", "under", "string", "ada")]),
    _block("rs.map_len", "Maps", "how many pairs are in it",
           "let @into@ = @name@.len();",
           [_slot("into", "into", "name", "count"), _slot("name", "table", "name", "ages")]),
    _block("rs.map_iter", "Maps", "do something with every pair",
           "for (@key@, @value@) in &@name@ {",
           [_slot("key", "key called", "name", "key"), _slot("value", "value called", "name", "value"),
            _slot("name", "of", "name", "ages")],
           close="}", wrap=True, empty="// your code here"),

    # -- Logic -------------------------------------------------------------
    _block("rs.if", "Logic", "if something is true", "if @test@ {",
           [_slot("test", "test", "text", "score > 10")], close="}", wrap=True,
           empty="// your code here"),
    _block("rs.if_equal", "Logic", "if two things are the same", "if @a@ == @b@ {",
           [_slot("a", "first", "text", "answer"), _slot("b", "second", "text", "42")],
           close="}", wrap=True, empty="// your code here"),
    _block("rs.else", "Logic", "otherwise", "} else {", close="}", wrap=True,
           empty="// your code here", about="Put this straight after an if block.",
           chain_after=("rs.if", "rs.if_equal", "rs.and", "rs.or", "rs.not",
                        "rs.contains", "rs.starts_with", "rs.map_has",
                        "rs.vec_contains", "rs.if_some", "rs.else_if")),
    _block("rs.else_if", "Logic", "otherwise, if", "} else if @test@ {",
           [_slot("test", "test", "text", "score > 5")], close="}", wrap=True,
           empty="// your code here",
           chain_after=("rs.if", "rs.if_equal", "rs.and", "rs.or", "rs.not",
                        "rs.contains", "rs.starts_with", "rs.map_has",
                        "rs.vec_contains", "rs.if_some", "rs.else_if")),
    _block("rs.and", "Logic", "if both are true", "if @a@ && @b@ {",
           [_slot("a", "first", "text", "ready"), _slot("b", "second", "text", "count > 0")],
           close="}", wrap=True, empty="// your code here"),
    _block("rs.or", "Logic", "if either is true", "if @a@ || @b@ {",
           [_slot("a", "first", "text", "done"), _slot("b", "second", "text", "count == 0")],
           close="}", wrap=True, empty="// your code here"),
    _block("rs.not", "Logic", "if something is not true", "if !@test@ {",
           [_slot("test", "test", "text", "found")], close="}", wrap=True,
           empty="// your code here"),
    _block("rs.match", "Logic", "choose between values", "match @value@ {",
           [_slot("value", "on", "text", "choice")], close="}", wrap=True,
           empty="_ => {}"),
    _block("rs.match_arm", "Logic", "one of the choices",
           "@value@ => @result@,",
           [_slot("value", "when it is", "text", "1"),
            _slot("result", "then", "text", 'println!("one")')]),
    _block("rs.match_other", "Logic", "anything else",
           "_ => @result@,",
           [_slot("result", "then", "text", 'println!("something else")')]),

    # -- Loops -------------------------------------------------------------
    _block("rs.for_range", "Loops", "count from one number to another",
           "for @name@ in @from@..@to@ {",
           [_slot("name", "counter", "name", "i"),
            _slot("from", "from", "number", "0"), _slot("to", "up to", "text", "10")],
           close="}", wrap=True, empty="// your code here"),
    _block("rs.for_range_inclusive", "Loops", "count, including the last one",
           "for @name@ in @from@..=@to@ {",
           [_slot("name", "counter", "name", "i"),
            _slot("from", "from", "number", "1"), _slot("to", "up to and including", "text", "10")],
           close="}", wrap=True, empty="// your code here"),
    _block("rs.while", "Loops", "keep going while something is true",
           "while @test@ {",
           [_slot("test", "test", "text", "running")], close="}", wrap=True, empty="break;"),
    _block("rs.loop", "Loops", "keep going until told to stop", "loop {",
           close="}", wrap=True, empty="break;"),
    _block("rs.break", "Loops", "stop the loop", "break;"),
    _block("rs.continue", "Loops", "skip to the next turn", "continue;"),

    # -- Functions ---------------------------------------------------------
    _block("rs.fn", "Functions", "a piece of code with a name",
           "fn @name@(@arguments@) -> @returns@ {",
           [_slot("name", "name", "name", "double"),
            _slot("arguments", "takes", "text", "n: i32"),
            _slot("returns", "gives back", "choice", "i32",
                  ["i32", "i64", "f64", "String", "bool", "usize"])],
           close="}", wrap=True, empty="0"),
    _block("rs.fn_nothing", "Functions", "a piece of code that gives nothing back",
           "fn @name@(@arguments@) {",
           [_slot("name", "name", "name", "show"),
            _slot("arguments", "takes", "text", "value: i32")],
           close="}", wrap=True, empty="// your code here"),
    _block("rs.return", "Functions", "give a value back", "return @value@;",
           [_slot("value", "value", "text", "result")]),
    _block("rs.value", "Functions", "the answer, as the last line", "@value@",
           [_slot("value", "value", "text", "n * 2")],
           about="Rust gives back the last expression. No semicolon on it."),
    _block("rs.call", "Functions", "use a function", "@name@(@arguments@);",
           [_slot("name", "name", "name", "show"), _slot("arguments", "with", "text", "1")]),
    _block("rs.call_into", "Functions", "use a function and keep the answer",
           "let @into@ = @name@(@arguments@);",
           [_slot("into", "into", "name", "result"), _slot("name", "name", "name", "double"),
            _slot("arguments", "with", "text", "21")]),

    # -- Shapes ------------------------------------------------------------
    _block("rs.struct", "Shapes", "a shape with named parts",
           "struct @name@ {",
           [_slot("name", "name", "name", "Point")], close="}", wrap=True, empty="x: i32,"),
    _block("rs.struct_field", "Shapes", "one part of a shape",
           "@name@: @type@,",
           [_slot("name", "name", "name", "x"),
            _slot("type", "kind", "choice", "i32", ["i32", "i64", "f64", "String", "bool"])]),
    _block("rs.struct_new", "Shapes", "one of a shape",
           "let @name@ = @type@ { @values@ };",
           [_slot("name", "name", "name", "here"), _slot("type", "shape", "name", "Point"),
            _slot("values", "parts, like x: 1", "text", "x: 1, y: 2")]),
    _block("rs.struct_get", "Shapes", "read part of a shape",
           "let @into@ = @name@.@field@;",
           [_slot("into", "into", "name", "x"), _slot("name", "of", "name", "here"),
            _slot("field", "part", "name", "x")]),
    _block("rs.impl", "Shapes", "things a shape can do", "impl @name@ {",
           [_slot("name", "for", "name", "Point")], close="}", wrap=True,
           empty="// methods go here"),
    _block("rs.method", "Shapes", "one thing a shape can do",
           "fn @name@(&self@arguments@) -> @returns@ {",
           [_slot("name", "name", "name", "describe"),
            _slot("arguments", "and takes", "text", ""),
            _slot("returns", "gives back", "choice", "String",
                  ["String", "i32", "f64", "bool", "usize"])],
           close="}", wrap=True, empty='String::new()'),
    _block("rs.enum", "Shapes", "one of a fixed set of things",
           "enum @name@ {",
           [_slot("name", "name", "name", "Colour")], close="}", wrap=True, empty="Red,"),
    _block("rs.enum_variant", "Shapes", "one of the set", "@name@,",
           [_slot("name", "name", "name", "Red")]),

    # -- Might be nothing --------------------------------------------------
    _block("rs.some", "Might be nothing", "a value that is there",
           "let @name@ = Some(@value@);",
           [_slot("name", "name", "name", "found"), _slot("value", "value", "text", "42")]),
    _block("rs.none", "Might be nothing", "a value that is not there",
           "let @name@: Option<@type@> = None;",
           [_slot("name", "name", "name", "found"),
            _slot("type", "would be", "choice", "i32", ["i32", "f64", "String", "bool"])]),
    _block("rs.if_some", "Might be nothing", "if there is a value",
           "if let Some(@name@) = @option@ {",
           [_slot("name", "called", "name", "value"), _slot("option", "of", "text", "found")],
           close="}", wrap=True, empty="// your code here"),
    _block("rs.unwrap_or", "Might be nothing", "the value, or a fallback",
           "let @into@ = @option@.unwrap_or(@fallback@);",
           [_slot("into", "into", "name", "value"), _slot("option", "of", "text", "found"),
            _slot("fallback", "or", "text", "0")]),
    _block("rs.is_some", "Might be nothing", "if there is anything at all",
           "if @option@.is_some() {",
           [_slot("option", "of", "text", "found")], close="}", wrap=True,
           empty="// your code here"),
    _block("rs.ok", "Might be nothing", "it worked", "Ok(@value@)",
           [_slot("value", "with", "text", "result")]),
    _block("rs.err", "Might be nothing", "it did not work",
           "Err(@message@)",
           [_slot("message", "saying", "text", 'String::from("that will not work")')]),
]


# ---------------------------------------------------------------------------
# Shell
# ---------------------------------------------------------------------------
#
# POSIX sh, not bash, and that is not a style choice. A `.sh` file on the
# phone is run by `/system/bin/sh`, which on Android is mksh - so `[[ ]]`,
# arrays and `function name()` are simply not there. Every block here is
# written in the shell the device actually has.

SHELL = [
    # -- Basics ------------------------------------------------------------
    _block("sh.shebang", "Basics", "the top of the file", "#!/bin/sh",
           about="Says which shell runs this. The first line, if you use it."),
    _block("sh.echo", "Basics", "print text", 'echo "@text@"',
           [_slot("text", "text", "inline", "Hello")]),
    _block("sh.echo_value", "Basics", "print a variable", 'echo "$@name@"',
           [_slot("name", "variable", "name", "name")]),
    _block("sh.echo_labelled", "Basics", "print a label and a variable",
           'echo "@label@ $@name@"',
           [_slot("label", "label", "inline", "total:"),
            _slot("name", "variable", "name", "total")]),
    _block("sh.echo_blank", "Basics", "print an empty line", "echo"),
    _block("sh.comment", "Basics", "a note to yourself", "# @text@",
           [_slot("text", "note", "text", "what this part does")]),
    _block("sh.blank", "Basics", "an empty line", ""),
    _block("sh.read", "Basics", "read a line that was typed", "read @name@",
           [_slot("name", "into", "name", "answer")]),
    _block("sh.prompt", "Basics", "ask a question and read the answer",
           'printf "@question@ "; read @name@',
           [_slot("question", "question", "inline", "What is your name?"),
            _slot("name", "into", "name", "answer")]),
    _block("sh.exit", "Basics", "stop the script", "exit @code@",
           [_slot("code", "with code", "number", "0")],
           about="0 means it worked. Anything else means it did not."),
    _block("sh.sleep", "Basics", "wait", "sleep @seconds@",
           [_slot("seconds", "seconds", "number", "1")]),
    _block("sh.set_e", "Basics", "stop at the first thing that fails", "set -e"),

    # -- Variables ---------------------------------------------------------
    _block("sh.set", "Variables", "set a variable", '@name@="@value@"',
           [_slot("name", "name", "name", "name"), _slot("value", "value", "inline", "world")],
           about="No spaces round the = sign. The shell is fussy about that."),
    _block("sh.set_command", "Variables", "set it to what a command prints",
           '@name@="$(@command@)"',
           [_slot("name", "name", "name", "today"), _slot("command", "command", "text", "date")]),
    _block("sh.set_number", "Variables", "set a number", "@name@=@value@",
           [_slot("name", "name", "name", "count"), _slot("value", "value", "number", "0")]),
    _block("sh.export", "Variables", "make it visible to other programs",
           'export @name@="@value@"',
           [_slot("name", "name", "name", "PATH_EXTRA"), _slot("value", "value", "inline", "/usr/local/bin")]),
    _block("sh.default", "Variables", "a value, or a fallback if it is empty",
           '@name@="${@from@:-@fallback@}"',
           [_slot("name", "name", "name", "target"), _slot("from", "from", "name", "1"),
            _slot("fallback", "or", "inline", "here")]),
    _block("sh.maths", "Variables", "work out a number",
           "@name@=$((@expression@))",
           [_slot("name", "name", "name", "total"),
            _slot("expression", "sum", "text", "count + 1")]),
    _block("sh.increase", "Variables", "add to a number",
           "@name@=$((@name@ + @amount@))",
           [_slot("name", "name", "name", "count"), _slot("amount", "by", "number", "1")]),
    _block("sh.length", "Variables", "how long a variable is",
           "@into@=${#@name@}",
           [_slot("into", "into", "name", "length"), _slot("name", "of", "name", "name")]),

    # -- Arguments ---------------------------------------------------------
    _block("sh.arg", "Arguments", "one of the things passed in",
           '@name@="$@number@"',
           [_slot("name", "into", "name", "target"), _slot("number", "which", "number", "1")],
           about="$1 is the first, $2 the second."),
    _block("sh.arg_count", "Arguments", "how many were passed in",
           "@name@=$#",
           [_slot("name", "into", "name", "count")]),
    _block("sh.arg_all", "Arguments", "all of them", '@name@="$*"',
           [_slot("name", "into", "name", "everything")]),
    _block("sh.need_arg", "Arguments", "stop if nothing was passed in",
           'if [ $# -eq 0 ]; then echo "@message@"; exit 1; fi',
           [_slot("message", "saying", "inline", "usage: script <file>")]),
    _block("sh.script_name", "Arguments", "the name of this script",
           '@name@="$0"',
           [_slot("name", "into", "name", "script")]),

    # -- Logic -------------------------------------------------------------
    _block("sh.if_equal", "Logic", "if two pieces of text are the same",
           'if [ "$@a@" = "@b@" ]; then',
           [_slot("a", "variable", "name", "answer"), _slot("b", "is", "inline", "yes")],
           close="fi", wrap=True, empty=":"),
    _block("sh.if_number", "Logic", "if a number compares",
           'if [ "$@a@" @test@ @b@ ]; then',
           [_slot("a", "variable", "name", "count"),
            _slot("test", "is", "choice", "-gt", ["-eq", "-ne", "-gt", "-ge", "-lt", "-le"]),
            _slot("b", "than", "number", "0")],
           close="fi", wrap=True, empty=":",
           about="-eq is equal, -gt greater, -lt less."),
    _block("sh.if_empty", "Logic", "if a variable is empty",
           'if [ -z "$@name@" ]; then',
           [_slot("name", "variable", "name", "answer")], close="fi", wrap=True, empty=":"),
    _block("sh.if_set", "Logic", "if a variable has something in it",
           'if [ -n "$@name@" ]; then',
           [_slot("name", "variable", "name", "answer")], close="fi", wrap=True, empty=":"),
    _block("sh.if_file", "Logic", "if a file exists",
           'if [ -f "@path@" ]; then',
           [_slot("path", "file", "inline", "notes.txt")], close="fi", wrap=True, empty=":"),
    _block("sh.if_folder", "Logic", "if a folder exists",
           'if [ -d "@path@" ]; then',
           [_slot("path", "folder", "inline", "work")], close="fi", wrap=True, empty=":"),
    _block("sh.if_command", "Logic", "if a command works",
           "if @command@; then",
           [_slot("command", "command", "text", "grep -q word notes.txt")],
           close="fi", wrap=True, empty=":"),
    _block("sh.else", "Logic", "otherwise", "else", wrap=True, empty=":",
           about="Put this straight after an if block.",
           chain_after=("sh.if_equal", "sh.if_number", "sh.if_empty", "sh.if_set",
                        "sh.if_file", "sh.if_folder", "sh.if_command", "sh.elif")),
    _block("sh.elif", "Logic", "otherwise, if",
           'elif [ "$@a@" = "@b@" ]; then',
           [_slot("a", "variable", "name", "answer"), _slot("b", "is", "inline", "maybe")],
           wrap=True, empty=":",
           chain_after=("sh.if_equal", "sh.if_number", "sh.if_empty", "sh.if_set",
                        "sh.if_file", "sh.if_folder", "sh.if_command", "sh.elif")),
    _block("sh.case", "Logic", "choose between values", 'case "$@name@" in',
           [_slot("name", "on", "name", "answer")], close="esac", wrap=True, empty="*) ;;"),
    _block("sh.case_when", "Logic", "one of the choices", "@pattern@)",
           [_slot("pattern", "when it is", "inline", "yes")], close=";;", wrap=True, empty=":"),
    _block("sh.case_other", "Logic", "anything else", "*)", close=";;", wrap=True, empty=":"),

    # -- Loops -------------------------------------------------------------
    _block("sh.for_list", "Loops", "for each of these things",
           "for @name@ in @items@; do",
           [_slot("name", "each one called", "name", "item"),
            _slot("items", "things", "text", "one two three")],
           close="done", wrap=True, empty=":"),
    _block("sh.for_files", "Loops", "for each file that matches",
           'for @name@ in @pattern@; do',
           [_slot("name", "each one called", "name", "file"),
            _slot("pattern", "matching", "text", "*.txt")],
           close="done", wrap=True, empty=":"),
    _block("sh.for_count", "Loops", "count from one number to another",
           "@name@=@from@; while [ $@name@ -le @to@ ]; do",
           [_slot("name", "counter", "name", "i"),
            _slot("from", "from", "number", "1"), _slot("to", "up to", "number", "10")],
           close="done", wrap=True, empty=":",
           about="POSIX sh has no C-style for loop. Put an 'add to a number' "
                 "block at the end of the loop or it will never finish."),
    _block("sh.while_read", "Loops", "for each line of a file",
           'while IFS= read -r @name@; do',
           [_slot("name", "each line called", "name", "line"),
            _slot("path", "of file", "inline", "notes.txt")],
           close='done < "@path@"', wrap=True, empty=":"),
    _block("sh.while", "Loops", "keep going while a command works",
           "while @command@; do",
           [_slot("command", "while", "text", "[ -f lock ]")],
           close="done", wrap=True, empty="sleep 1"),
    _block("sh.break", "Loops", "stop the loop", "break"),
    _block("sh.continue", "Loops", "skip to the next turn", "continue"),

    # -- Files -------------------------------------------------------------
    _block("sh.write", "Files", "write text to a file",
           'echo "@text@" > "@path@"',
           [_slot("text", "text", "inline", "Hello"), _slot("path", "file", "inline", "notes.txt")],
           about="One > replaces the file."),
    _block("sh.append", "Files", "add text to the end of a file",
           'echo "@text@" >> "@path@"',
           [_slot("text", "text", "inline", "another line"),
            _slot("path", "file", "inline", "notes.txt")]),
    _block("sh.cat", "Files", "print a file", 'cat "@path@"',
           [_slot("path", "file", "inline", "notes.txt")]),
    _block("sh.copy", "Files", "copy a file", 'cp "@from@" "@to@"',
           [_slot("from", "from", "inline", "notes.txt"), _slot("to", "to", "inline", "backup.txt")]),
    _block("sh.move", "Files", "move or rename a file", 'mv "@from@" "@to@"',
           [_slot("from", "from", "inline", "old.txt"), _slot("to", "to", "inline", "new.txt")]),
    _block("sh.remove", "Files", "delete a file", 'rm -f "@path@"',
           [_slot("path", "file", "inline", "temp.txt")]),
    _block("sh.mkdir", "Files", "make a folder", 'mkdir -p "@path@"',
           [_slot("path", "folder", "inline", "work/output")]),
    _block("sh.list", "Files", "list what is in a folder", 'ls -la "@path@"',
           [_slot("path", "folder", "inline", ".")]),
    _block("sh.count_lines", "Files", "how many lines a file has",
           '@into@=$(wc -l < "@path@")',
           [_slot("into", "into", "name", "lines"), _slot("path", "file", "inline", "notes.txt")]),

    # -- Text --------------------------------------------------------------
    _block("sh.grep", "Text", "find lines containing something",
           'grep "@pattern@" "@path@"',
           [_slot("pattern", "looking for", "inline", "error"),
            _slot("path", "in", "inline", "log.txt")]),
    _block("sh.grep_count", "Text", "count lines containing something",
           '@into@=$(grep -c "@pattern@" "@path@")',
           [_slot("into", "into", "name", "hits"),
            _slot("pattern", "looking for", "inline", "error"),
            _slot("path", "in", "inline", "log.txt")]),
    _block("sh.sed", "Text", "swap one piece of text for another",
           "sed 's/@old@/@new@/g' \"@path@\"",
           [_slot("old", "replace", "inline", "cat"), _slot("new", "with", "inline", "dog"),
            _slot("path", "in", "inline", "notes.txt")]),
    _block("sh.sort", "Text", "put lines in order", 'sort "@path@"',
           [_slot("path", "file", "inline", "names.txt")]),
    _block("sh.uniq", "Text", "remove repeated lines", 'sort "@path@" | uniq',
           [_slot("path", "file", "inline", "names.txt")]),
    _block("sh.head", "Text", "the first few lines",
           'head -n @count@ "@path@"',
           [_slot("count", "how many", "number", "10"), _slot("path", "of", "inline", "log.txt")]),
    _block("sh.tail", "Text", "the last few lines",
           'tail -n @count@ "@path@"',
           [_slot("count", "how many", "number", "10"), _slot("path", "of", "inline", "log.txt")]),
    _block("sh.pipe", "Text", "one command into another",
           "@first@ | @second@",
           [_slot("first", "run", "text", "ls"), _slot("second", "then", "text", "wc -l")]),

    # -- Functions ---------------------------------------------------------
    _block("sh.function", "Functions", "a piece of script with a name",
           "@name@() {",
           [_slot("name", "name", "name", "greet")], close="}", wrap=True, empty=":"),
    _block("sh.function_arg", "Functions", "one of the things passed to it",
           '@name@="$@number@"',
           [_slot("name", "into", "name", "who"), _slot("number", "which", "number", "1")]),
    _block("sh.call", "Functions", "use a function", "@name@ @arguments@",
           [_slot("name", "name", "name", "greet"), _slot("arguments", "with", "text", "world")]),
    _block("sh.return", "Functions", "finish a function", "return @code@",
           [_slot("code", "with code", "number", "0")]),
    _block("sh.run", "Functions", "run a command", "@command@",
           [_slot("command", "command", "text", "ls -la")]),
    _block("sh.run_quiet", "Functions", "run a command, saying nothing",
           "@command@ >/dev/null 2>&1",
           [_slot("command", "command", "text", "grep -q word notes.txt")]),
]


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------
#
# JSON is data rather than code, and a block editor is a very good way to
# write it: the two mistakes everybody makes are a missing comma and one
# comma too many, and neither is possible here. The compiler puts the commas
# in - see `_tidy_json` - so a block never has to carry one.

JSON = [
    # -- Shape -------------------------------------------------------------
    _block("json.object", "Shape", "a thing with named parts", "{",
           close="}", wrap=True, empty="",
           about="The outside of most JSON files."),
    _block("json.array", "Shape", "a list", "[", close="]", wrap=True, empty="",
           about="At the top of a file, or as a value inside one."),
    _block("json.named_object", "Shape", "a named thing with parts",
           '@name@: {',
           [_slot("name", "name", "string", "author")], close="}", wrap=True, empty=""),
    _block("json.named_array", "Shape", "a named list", '@name@: [',
           [_slot("name", "name", "string", "tags")], close="]", wrap=True, empty=""),

    # -- Named values ------------------------------------------------------
    _block("json.text", "Named values", "a piece of text",
           '@name@: @value@',
           [_slot("name", "name", "string", "title"), _slot("value", "value", "string", "Hello")]),
    _block("json.number", "Named values", "a number", '@name@: @value@',
           [_slot("name", "name", "string", "count"), _slot("value", "value", "number", "0")]),
    _block("json.decimal", "Named values", "a decimal number",
           '@name@: @value@',
           [_slot("name", "name", "string", "price"),
            _slot("value", "value", "number", "9.99")]),
    _block("json.bool", "Named values", "true or false", '@name@: @value@',
           [_slot("name", "name", "string", "enabled"),
            _slot("value", "value", "choice", "true", ["true", "false"])]),
    _block("json.null", "Named values", "nothing", '@name@: null',
           [_slot("name", "name", "string", "middleName")]),
    _block("json.raw", "Named values", "a value written out as is",
           '@name@: @value@',
           [_slot("name", "name", "string", "data"), _slot("value", "value", "text", "[1, 2, 3]")],
           about="For a value you want to type yourself."),

    # -- Values in a list --------------------------------------------------
    _block("json.item_text", "In a list", "a piece of text", "@value@",
           [_slot("value", "value", "string", "one")]),
    _block("json.item_number", "In a list", "a number", "@value@",
           [_slot("value", "value", "number", "1")]),
    _block("json.item_bool", "In a list", "true or false", "@value@",
           [_slot("value", "value", "choice", "true", ["true", "false"])]),
    _block("json.item_object", "In a list", "a thing with parts", "{",
           close="}", wrap=True, empty=""),
    _block("json.item_array", "In a list", "another list", "[",
           close="]", wrap=True, empty=""),

    # -- Ready-made --------------------------------------------------------
    _block("json.plugin_id", "Ready-made", "a plugin's id", '"id": @value@',
           [_slot("value", "id", "string", "me.myplugin")],
           about="Every PyCmd plugin.json needs id, name and version."),
    _block("json.plugin_name", "Ready-made", "a plugin's name", '"name": @value@',
           [_slot("value", "name", "string", "My Plugin")]),
    _block("json.plugin_version", "Ready-made", "a version",
           '"version": @value@',
           [_slot("value", "version", "string", "1.0.0")]),
    _block("json.description", "Ready-made", "a description",
           '"description": @text@',
           [_slot("text", "text", "string", "What this does")]),
    _block("json.entry", "Ready-made", "which file runs",
           '"entry": @file@',
           [_slot("file", "file", "string", "main.py")]),
]


HTML_MORE = [
    # -- Media -------------------------------------------------------------
    _block("html.img", "Media", "a picture",
           '<img src="@src@" alt="@alt@">',
           [_slot("src", "file", "string", "photo.jpg"),
            _slot("alt", "described as", "string", "A photograph")],
           about="The description is read aloud to people who cannot see it."),
    _block("html.figure", "Media", "a picture with a caption", "<figure>",
           close="</figure>", wrap=True),
    _block("html.figcaption", "Media", "the caption",
           "<figcaption>@text@</figcaption>",
           [_slot("text", "text", "string", "What this shows")]),
    _block("html.iframe", "Media", "another page inside this one",
           '<iframe src="@src@" title="@title@"></iframe>',
           [_slot("src", "address", "string", "page.html"),
            _slot("title", "called", "string", "An embedded page")]),
    _block("html.canvas", "Media", "somewhere to draw",
           '<canvas id="@id@" width="@width@" height="@height@"></canvas>',
           [_slot("id", "named", "string", "board"),
            _slot("width", "wide", "number", "320"), _slot("height", "tall", "number", "240")]),
    _block("html.svg_circle", "Media", "a circle",
           '<svg width="@size@" height="@size@"><circle cx="50%" cy="50%" r="40%" fill="@colour@" /></svg>',
           [_slot("size", "size", "number", "100"),
            _slot("colour", "colour", "string", "#4A9EFF")]),

    # -- Tables ------------------------------------------------------------
    _block("html.thead", "Tables", "the heading row group", "<thead>",
           close="</thead>", wrap=True),
    _block("html.tbody", "Tables", "the body", "<tbody>", close="</tbody>", wrap=True),
    _block("html.caption", "Tables", "what the table is",
           "<caption>@text@</caption>",
           [_slot("text", "text", "string", "Scores")]),

    # -- Parts of a page ---------------------------------------------------
    _block("html.article", "Parts of a page", "one self-contained thing",
           "<article>", close="</article>", wrap=True),
    _block("html.aside", "Parts of a page", "something off to the side",
           "<aside>", close="</aside>", wrap=True),
    _block("html.details", "Parts of a page", "something that folds open",
           "<details>", close="</details>", wrap=True),
    _block("html.summary", "Parts of a page", "what it says when folded",
           "<summary>@text@</summary>",
           [_slot("text", "text", "string", "Read more")]),
    _block("html.dialog", "Parts of a page", "a box over the page",
           '<dialog id="@id@">',
           [_slot("id", "named", "string", "about")], close="</dialog>", wrap=True),
    _block("html.span_class", "Parts of a page", "a piece of a line, named",
           '<span class="@class@">@text@</span>',
           [_slot("class", "class", "string", "badge"),
            _slot("text", "text", "string", "new")]),
    _block("html.div_class", "Parts of a page", "a box, named",
           '<div class="@class@">',
           [_slot("class", "class", "string", "card")], close="</div>", wrap=True),

    # -- The head ----------------------------------------------------------
    _block("html.description", "The head", "what the page is about",
           '<meta name="description" content="@text@">',
           [_slot("text", "description", "string", "What this page is for")]),
    _block("html.theme_colour", "The head", "the colour the browser paints round it",
           '<meta name="theme-color" content="@colour@">',
           [_slot("colour", "colour", "string", "#0B0F14")]),
    _block("html.favicon", "The head", "the little icon",
           '<link rel="icon" href="@src@">',
           [_slot("src", "file", "string", "favicon.png")]),
    _block("html.font", "The head", "a web font",
           '<link rel="stylesheet" href="@href@">',
           [_slot("href", "address", "string",
                  "https://fonts.googleapis.com/css2?family=Inter&display=swap")]),
    _block("html.open_graph", "The head", "the title a link preview shows",
           '<meta property="og:title" content="@text@">',
           [_slot("text", "title", "string", "My page")]),
]

CSS_MORE = [
    # -- Flex --------------------------------------------------------------
    _block("css.flex_row", "Flex", "lay children out in a row",
           "display: flex;"),
    _block("css.flex_column", "Flex", "lay children out in a column",
           "display: flex; flex-direction: column;"),
    _block("css.flex_wrap", "Flex", "let them wrap onto the next line",
           "flex-wrap: wrap;"),
    _block("css.flex_grow", "Flex", "let this one take the spare room",
           "flex: 1 1 auto;"),
    _block("css.flex_none", "Flex", "keep this one its own size",
           "flex: 0 0 auto;"),
    _block("css.flex_centre", "Flex", "centre the children both ways",
           "align-items: center; justify-content: center;"),
    _block("css.flex_between", "Flex", "push the children apart",
           "justify-content: space-between;"),
    _block("css.flex_basis", "Flex", "how wide it starts",
           "flex-basis: @value@;",
           [_slot("value", "width", "string", "200px")]),

    # -- Grid --------------------------------------------------------------
    _block("css.grid", "Grid", "lay children out in a grid", "display: grid;"),
    _block("css.grid_fit", "Grid", "as many columns as fit",
           "grid-template-columns: repeat(auto-fill, minmax(@min@, 1fr));",
           [_slot("min", "each at least", "string", "220px")]),
    _block("css.grid_count", "Grid", "a fixed number of columns",
           "grid-template-columns: repeat(@count@, 1fr);",
           [_slot("count", "columns", "number", "3")]),
    _block("css.grid_rows", "Grid", "row heights",
           "grid-template-rows: @value@;",
           [_slot("value", "rows", "string", "auto 1fr auto")]),
    _block("css.grid_span", "Grid", "make this one span columns",
           "grid-column: span @count@;",
           [_slot("count", "columns", "number", "2")]),
    _block("css.grid_gap", "Grid", "space between cells",
           "gap: @value@;",
           [_slot("value", "gap", "string", "12px")]),

    # -- Colours that change -----------------------------------------------
    _block("css.use_variable", "Colours that change", "use a named colour",
           "@property@: var(--@name@);",
           [_slot("property", "for", "choice", "color",
                  ["color", "background", "border-color", "fill", "outline-color"]),
            _slot("name", "named", "name", "accent")]),
    _block("css.use_variable_fallback", "Colours that change",
           "use a named colour, with a fallback",
           "@property@: var(--@name@, @fallback@);",
           [_slot("property", "for", "choice", "color",
                  ["color", "background", "border-color", "fill"]),
            _slot("name", "named", "name", "accent"),
            _slot("fallback", "or", "string", "#4A9EFF")]),
    _block("css.dark_mode", "Colours that change", "when the phone is in dark mode",
           "@@media (prefers-color-scheme: dark) {", close="}", wrap=True,
           empty="/* dark colours here */"),

    # -- Movement ----------------------------------------------------------
    _block("css.animation", "Movement", "run an animation",
           "animation: @name@ @seconds@s @easing@ @repeat@;",
           [_slot("name", "called", "name", "fade"),
            _slot("seconds", "over seconds", "text", "0.3"),
            _slot("easing", "easing", "choice", "ease",
                  ["ease", "ease-in", "ease-out", "ease-in-out", "linear"]),
            _slot("repeat", "how often", "choice", "1",
                  ["1", "2", "3", "infinite"])]),
    _block("css.keyframes", "Movement", "describe an animation",
           "@@keyframes @name@ {",
           [_slot("name", "called", "name", "fade")], close="}", wrap=True,
           empty="from { opacity: 0 } to { opacity: 1 }"),
    _block("css.keyframe_step", "Movement", "one step of an animation",
           "@at@ {",
           [_slot("at", "at", "choice", "from", ["from", "to", "0%", "25%", "50%", "75%", "100%"])],
           close="}", wrap=True, empty="opacity: 1;"),
    _block("css.active", "Movement", "while it is being pressed",
           "@selector@:active {",
           [_slot("selector", "for", "text", ".button")], close="}", wrap=True,
           empty="transform: scale(.98);"),
    _block("css.focus", "Movement", "when it is picked out for typing",
           "@selector@:focus-visible {",
           [_slot("selector", "for", "text", "input")], close="}", wrap=True,
           empty="outline: 2px solid var(--accent);"),

    # -- Screens -----------------------------------------------------------
    _block("css.narrow", "Screens", "on a narrow screen",
           "@@media (max-width: @width@px) {",
           [_slot("width", "narrower than", "number", "520")], close="}", wrap=True,
           empty="/* phone styles here */"),
    _block("css.wide", "Screens", "on a wide screen",
           "@@media (min-width: @width@px) {",
           [_slot("width", "wider than", "number", "900")], close="}", wrap=True,
           empty="/* desktop styles here */"),
    _block("css.safe_area", "Screens", "keep clear of the notch",
           "padding-bottom: env(safe-area-inset-bottom);"),
    _block("css.no_motion", "Screens", "when the phone asks for less movement",
           "@@media (prefers-reduced-motion: reduce) {", close="}", wrap=True,
           empty="* { animation: none !important; transition: none !important; }"),
]

MARKDOWN_MORE = [
    # -- Tables ------------------------------------------------------------
    _block("md.table_rule", "Tables", "the line under the headings",
           "| --- | --- |",
           about="Put this straight after the heading row."),
    _block("md.table_head3", "Tables", "a heading row of three",
           "| @a@ | @b@ | @c@ |",
           [_slot("a", "first", "text", "Name"), _slot("b", "second", "text", "Score"),
            _slot("c", "third", "text", "Note")]),
    _block("md.table_rule3", "Tables", "the line under three headings",
           "| --- | --- | --- |"),
    _block("md.table_row3", "Tables", "a row of three",
           "| @a@ | @b@ | @c@ |",
           [_slot("a", "first", "text", "Ada"), _slot("b", "second", "text", "10"),
            _slot("c", "third", "text", "first")]),

    # -- Quotes and notes --------------------------------------------------
    _block("md.note", "Quotes and notes", "a note that stands out",
           "> **@label@** @text@",
           [_slot("label", "label", "text", "Note:"),
            _slot("text", "text", "text", "worth knowing")]),
    _block("md.footnote", "Quotes and notes", "a footnote marker",
           "@text@[^@name@]",
           [_slot("text", "after", "text", "something"), _slot("name", "named", "name", "1")]),
    _block("md.footnote_text", "Quotes and notes", "what the footnote says",
           "[^@name@]: @text@",
           [_slot("name", "named", "name", "1"), _slot("text", "says", "text", "the detail")]),

    # -- Checklists --------------------------------------------------------

    # -- Pictures ----------------------------------------------------------
    _block("md.image_link", "Pictures", "a picture that is a link",
           "[![@alt@](@src@)](@href@)",
           [_slot("alt", "described as", "text", "A photograph"),
            _slot("src", "file", "text", "photo.jpg"),
            _slot("href", "goes to", "text", "https://example.com")]),
    _block("md.badge", "Pictures", "a badge",
           "![@alt@](https://img.shields.io/badge/@label@-@value@-blue)",
           [_slot("alt", "described as", "text", "version"),
            _slot("label", "label", "text", "version"),
            _slot("value", "value", "text", "2.6.0")]),
]


HTML = HTML + HTML_MORE
CSS = CSS + CSS_MORE
MARKDOWN = MARKDOWN + MARKDOWN_MORE

BLOCKS = {
    "python": PYTHON,
    "javascript": JAVASCRIPT,
    "html": HTML,
    "css": CSS,
    "markdown": MARKDOWN,
    "c": C,
    "go": GO,
    "rust": RUST,
    "shell": SHELL,
    "json": JSON,
}

BY_ID = {row["id"]: row for rows in BLOCKS.values() for row in rows}

# Which language each block belongs to, so a project cannot quietly use a
# Python block in a CSS file and produce something that is neither.
LANGUAGE_OF = {
    row["id"]: language for language, rows in BLOCKS.items() for row in rows
}


# ---------------------------------------------------------------------------
# Reading the catalogue
# ---------------------------------------------------------------------------


def block(block_id: str):
    """One block by id, or None."""
    return BY_ID.get(str(block_id))


def preview_of(row: dict, language: str, values: dict = None) -> dict:
    """The line a block would actually write, with its holes filled in.

    The palette used to show the template - `print(@text@)` - which reads as
    placeholder text rather than as a block that does something. This renders
    it the same way the compiler will, so what you pick is what you get.
    """
    ignored = []
    filled = _render(row["open"], row["slots"], values or {}, language,
                     ignored, row["id"])
    closing = ""
    if row.get("close"):
        closing = _render(row["close"], row["slots"], values or {}, language,
                          ignored, row["id"])
    return {"preview": filled, "closing": closing}


def catalogue(language: str = "") -> dict:
    """The blocks for one language, grouped the way the palette shows them.

    Called once when the panel opens. Three hundred and sixty blocks is a lot
    of JSON to hand across a bridge, so the panel asks for one language at a
    time - which is also all it can show at once, since a project is written
    in one language.
    """
    language = str(language or "").strip().lower()
    if language and language not in BLOCKS:
        return {"ok": False, "error": f"no blocks for {language}", "languages": LANGUAGES}

    wanted = [language] if language else LANGUAGE_IDS
    groups = []
    total = 0
    for name in wanted:
        rows = BLOCKS[name]
        total += len(rows)
        categories = []
        for row in rows:
            if not categories or categories[-1]["name"] != row["cat"]:
                categories.append({"name": row["cat"], "blocks": []})
            categories[-1]["blocks"].append(dict(row, **preview_of(row, name)))
        groups.append({"language": name, "categories": categories, "count": len(rows)})

    return {
        "ok": True,
        "languages": LANGUAGES,
        "groups": groups,
        "count": total,
        "limits": {"blocks": MAX_BLOCKS, "depth": MAX_DEPTH},
    }


# ---------------------------------------------------------------------------
# Turning a project into a file
# ---------------------------------------------------------------------------

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Languages where a `string` slot is written with quotes round it. In HTML and
# CSS the template already carries whatever quoting the syntax needs.
QUOTED = {"python", "javascript", "c", "go", "rust", "json"}


def _clean(value) -> str:
    """One line, no control characters, and not a whole file long."""
    text = "" if value is None else str(value)
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return _CONTROL.sub("", text)[:MAX_VALUE]


def _escaped(raw: str, language: str) -> str:
    """Makes a piece of text safe for the syntax it is about to land in.

    Every one of these is a line that would otherwise break the moment
    somebody typed a quote into a hole, which is a thing people do constantly:
    names have apostrophes, sentences have quotation marks, and Windows paths
    are made of backslashes.
    """
    if language == "python":
        return raw.replace("\\", "\\\\").replace('"', '\\"')
    if language == "javascript":
        # Template literals and quoted strings both take these two; a `${` is
        # left alone because a block whose label says "with ${name} in it"
        # means it.
        return raw.replace("\\", "\\\\").replace("`", "\\`").replace('"', '\\"')
    if language == "html":
        return (raw.replace("&", "&amp;").replace("<", "&lt;")
                   .replace(">", "&gt;").replace('"', "&quot;"))
    if language == "css":
        # A brace cannot appear in a declaration, and one typed into a value
        # would close the rule and leave the rest of the file inside nothing.
        return raw.replace("{", "").replace("}", "")
    if language in ("c", "go", "json"):
        # All three write text between double quotes and all three take the
        # same two escapes for it.
        return raw.replace("\\", "\\\\").replace('"', '\\"')
    if language == "rust":
        # Same two, plus the braces: Rust's println! and format! read `{}` as
        # a hole to put a value in, and a stray one is a compile error rather
        # than the character somebody typed. `{{` is how you write a literal.
        return (raw.replace("\\", "\\\\").replace('"', '\\"')
                   .replace("{", "{{").replace("}", "}}"))
    if language == "shell":
        # Inside double quotes the shell still reads $ and ` as instructions -
        # `$(rm -rf .)` in a hole meant for somebody's name is not a joke -
        # so both are escaped along with the quote and the backslash.
        return (raw.replace("\\", "\\\\").replace('"', '\\"')
                   .replace("$", "\\$").replace("`", "\\`"))
    return raw


def _as_number(raw: str, language: str) -> str:
    """What a number slot writes.

    In nine of the ten languages: whatever was typed. A number slot is a hole
    where a number goes, but `total += i` and `range(1, count)` put a
    *variable* in one, and `x + 1` an expression - which is the ordinary way
    to use half the blocks in the catalogue. Demanding a literal there breaks
    the most natural thing anybody does with them.

    In JSON: an actual number, because JSON has no expressions at all. `count`
    in a JSON number slot is not a variable that will be resolved later; it is
    a file that does not parse. So a JSON number is read and written back out
    in the one spelling JSON accepts - which also rules out `+3` and `5.`,
    both of which are numbers in the other nine languages and neither of which
    is JSON.

    Two near-misses are rescued rather than thrown away: a trailing unit,
    because `10px` is somebody answering "how wide" in the units they think
    in, and a leading sign.
    """
    stripped = str(raw).strip()
    if not stripped:
        return "0"
    if language != "json":
        return stripped

    def salvage(text: str) -> str:
        sign = text[0] if text[:1] in ("+", "-") else ""
        head = ""
        for character in text[len(sign):]:
            if character.isdigit() or (character == "." and "." not in head):
                head += character
            else:
                break
        candidate = sign + head
        try:
            float(candidate)
        except ValueError:
            return "0"
        return candidate

    try:
        float(stripped)
        number = stripped
    except ValueError:
        number = salvage(stripped)

    try:
        value = float(number)
    except ValueError:
        return "0"
    if value.is_integer() and "e" not in number.lower():
        return str(int(value))
    return repr(value)


def _value_for(slot: dict, given, language: str) -> str:
    kind = slot.get("kind", "text")
    raw = _clean(given if given is not None else slot.get("default", ""))

    if kind == "choice":
        options = slot.get("options") or []
        if raw not in options:
            raw = str(slot.get("default") or (options[0] if options else ""))
        return raw

    if kind == "number":
        return _as_number(raw, language)

    if kind in ("string", "inline"):
        body = _escaped(raw, language)
        if kind == "string" and language in QUOTED:
            return f'"{body}"'
        return body

    if kind == "name":
        stripped = raw.strip()
        return stripped or str(slot.get("default") or "value")

    return raw.strip()


def _render(template: str, slots: list, values: dict, language: str,
            problems: list, label: str) -> str:
    """Fills one line's holes, then puts literal `@`s back."""
    by_name = {slot["name"]: slot for slot in slots}

    def swap(match):
        name = match.group(1)
        slot = by_name.get(name)
        if slot is None:
            # A template asking for a slot the block does not declare is a bug
            # in the catalogue, and the test suite fails on it - but at
            # runtime the honest thing is to leave the text alone and say so.
            problems.append(f"{label}: no slot called {name}")
            return match.group(0)
        return _value_for(slot, values.get(name), language)

    filled = PLACEHOLDER.sub(swap, template or "")
    return filled.replace("@@", "@")


def _tidy_json(lines: list) -> None:
    """Puts the commas into JSON, in place.

    The two mistakes everybody makes writing JSON by hand are a missing comma
    and one comma too many, and a block editor can make both impossible - but
    only if the blocks do not carry commas themselves. A block that wrote
    `"name": "Ada",` would be wrong as the last thing in an object and right
    everywhere else, which is exactly the judgement the person is here to
    avoid making.

    So no block carries one and this puts them in afterwards, by the only
    rule there is: a line needs a comma unless it opens something, or unless
    the thing after it closes something.
    """
    def opens(text: str) -> bool:
        return text.endswith("{") or text.endswith("[")

    def closes(text: str) -> bool:
        return text.startswith("}") or text.startswith("]")

    for index, line in enumerate(lines):
        body = line.strip()
        if not body or opens(body):
            continue
        following = ""
        for later in lines[index + 1:]:
            if later.strip():
                following = later.strip()
                break
        if not following or closes(following):
            continue
        lines[index] = line + ","


def compile_project(project: dict) -> dict:
    """Walks a project's blocks and writes the file they describe.

    Every failure here is reported rather than raised: a project with one bad
    block should still build the other ninety, because the person looking at
    the result is the person who can fix the one.
    """
    project = project if isinstance(project, dict) else {}
    language = str(project.get("language") or "python").strip().lower()
    if language not in BLOCKS:
        return {"ok": False, "error": f"'{language}' is not one of the languages here."}

    meta = next(row for row in LANGUAGES if row["id"] == language)
    indent = meta["indent"]
    lines: list = []
    problems: list = []
    # One entry per line, saying which block in the tree wrote it. The panel
    # draws the script from this, so what is on screen is the code, not an
    # approximation of it drawn separately and free to drift.
    outline: list = []
    used = 0

    def note(path: list, node: dict, role: str, depth: int, text: str) -> None:
        outline.append({
            "path": list(path),
            # Whatever the panel put on the node to recognise it by. Paths move
            # when a block is deleted above; this does not, which is the
            # difference between the script showing the right line and showing
            # the line that used to be there.
            "uid": str(node.get("uid", "")),
            "role": role,
            "depth": depth,
            "text": text,
            "line": len(lines) - 1,
        })

    def spec_at(nodes, index):
        """The block spec of one sibling, or None if there is not one."""
        if index < 0 or index >= len(nodes or []):
            return None
        node = nodes[index]
        if not isinstance(node, dict):
            return None
        return BY_ID.get(str(node.get("block")))

    def emit(nodes, depth: int, base: list) -> None:
        nonlocal used
        if depth > MAX_DEPTH:
            problems.append(f"nested deeper than {MAX_DEPTH}; stopped there")
            return
        nodes = list(nodes or [])
        for index, node in enumerate(nodes):
            path = base + [index]
            if not isinstance(node, dict):
                continue
            if used >= MAX_BLOCKS:
                problems.append(f"a project stops at {MAX_BLOCKS} blocks")
                return
            spec = BY_ID.get(str(node.get("block")))
            if spec is None:
                problems.append(f"no block called {node.get('block')}")
                continue
            if LANGUAGE_OF[spec["id"]] != language:
                problems.append(
                    f"{spec['id']} is a {LANGUAGE_OF[spec['id']]} block, not {language}"
                )
                continue

            used += 1

            # A chaining block - `} else {` - only makes sense directly after
            # one of the blocks it continues. Said out loud rather than
            # written out wrong: the brace it carries would close nothing.
            if spec.get("chain"):
                before = spec_at(nodes, index - 1)
                if before is None or before["id"] not in spec["chain"]:
                    problems.append(
                        f"{spec['label']!r} has to come straight after "
                        + " or ".join(repr(BY_ID[other]["label"])
                                      for other in spec["chain"] if other in BY_ID)
                    )

            values = node.get("values") if isinstance(node.get("values"), dict) else {}
            head = _render(spec["open"], spec["slots"], values, language,
                           problems, spec["id"])
            # A block whose whole line is empty is the blank-line block, and a
            # blank line with eight spaces of indentation on it is trailing
            # whitespace nobody asked for.
            lines.append(indent * depth + head if head.strip() else "")
            note(path, node, "open", depth, head)

            children = node.get("children") or []
            if spec["wrap"]:
                if children:
                    emit(children, depth + 1, path)
                elif spec["empty"]:
                    lines.append(indent * (depth + 1) + spec["empty"])
                    note(path, node, "empty", depth + 1, spec["empty"])
                # The block after this one may be continuing it, in which
                # case its own first line is this one's closing brace.
                following = spec_at(nodes, index + 1)
                continued = bool(following and spec["id"] in (following.get("chain") or []))
                if spec["close"] and not continued:
                    close = _render(spec["close"], spec["slots"], values, language,
                                    problems, spec["id"])
                    lines.append(indent * depth + close if close.strip() else "")
                    note(path, node, "close", depth, close)
            elif children:
                problems.append(f"{spec['id']} cannot hold blocks; its children were skipped")

    emit(project.get("blocks"), 0, [])

    if language == "json":
        _tidy_json(lines)
        # Said rather than assumed. A JSON block cannot write a stray comma -
        # the compiler puts those in - but the "written out as is" block is an
        # escape hatch by design, and an escape hatch that quietly writes a
        # file nothing can read is a trap. This is the same check the person
        # would run themselves, run for them.
        try:
            import json as _json

            _json.loads("\n".join(lines) or "null")
        except Exception as error:  # noqa: BLE001
            problems.append(f"this is not valid JSON yet: {error}")
        # The panel draws the script from the outline, so the outline has to
        # show the commas too - otherwise the screen stops being the code.
        for entry in outline:
            position = entry.get("line", -1)
            if 0 <= position < len(lines):
                entry["text"] = lines[position].strip()

    code = "\n".join(lines).rstrip("\n")
    if code:
        code += "\n"
    return {
        "ok": True,
        "code": code,
        "language": language,
        "extension": meta["extension"],
        "lines": len(lines),
        "blocks": used,
        "outline": outline,
        "problems": problems,
    }
