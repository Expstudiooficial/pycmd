/**
 * Python syntax highlighter.
 *
 * One pass, one regex. Ordering inside the pattern matters: comments and
 * strings come first so that a `#` inside a string, or a keyword inside a
 * comment, is never mistaken for code.
 */
(function (global) {
  'use strict';

  var KEYWORDS = [
    'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
    'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 'global',
    'if', 'import', 'in', 'is', 'lambda', 'match', 'nonlocal', 'not', 'or',
    'pass', 'raise', 'return', 'try', 'while', 'with', 'yield'
  ];

  var CONSTANTS = ['True', 'False', 'None'];

  var BUILTINS = [
    'abs', 'all', 'any', 'bin', 'bool', 'bytearray', 'bytes', 'callable',
    'chr', 'classmethod', 'compile', 'complex', 'dict', 'dir', 'divmod',
    'enumerate', 'eval', 'exec', 'filter', 'float', 'format', 'frozenset',
    'getattr', 'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'input',
    'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'locals', 'map',
    'max', 'min', 'next', 'object', 'oct', 'open', 'ord', 'pow', 'print',
    'property', 'range', 'repr', 'reversed', 'round', 'set', 'setattr',
    'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple', 'type',
    'vars', 'zip'
  ];

  var KEYWORD_SET = toSet(KEYWORDS);
  var CONSTANT_SET = toSet(CONSTANTS);
  var BUILTIN_SET = toSet(BUILTINS);

  function toSet(list) {
    var set = Object.create(null);
    for (var i = 0; i < list.length; i += 1) {
      set[list[i]] = true;
    }
    return set;
  }

  var HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;' };

  function escapeHtml(text) {
    return text.replace(/[&<>]/g, function (char) {
      return HTML_ESCAPES[char];
    });
  }

  // Alternatives in priority order: triple-quoted strings, single-quoted
  // strings, comments, decorators, numbers, identifiers, operators.
  var TOKEN_PATTERN = new RegExp(
    [
      '([rbuf]{0,2})("""[^]*?"""|\'\'\'[^]*?\'\'\')',
      '([rbuf]{0,2})("(?:\\\\.|[^"\\\\\\n])*"|\'(?:\\\\.|[^\'\\\\\\n])*\')',
      '(#[^\\n]*)',
      '(@[A-Za-z_][A-Za-z0-9_.]*)',
      '(\\b(?:0[xXbBoO][0-9a-fA-F_]+|\\d[\\d_]*(?:\\.[\\d_]*)?(?:[eE][+-]?\\d+)?[jJ]?)\\b)',
      '([A-Za-z_][A-Za-z0-9_]*)',
      '([+\\-*/%=<>!&|^~@]+)'
    ].join('|'),
    'g'
  );

  /**
   * @param {string} source Python source text.
   * @returns {string} HTML with `tok-*` spans, safe to assign to innerHTML.
   */
  function highlight(source) {
    var out = '';
    var lastIndex = 0;
    var match;
    var previousWord = '';

    TOKEN_PATTERN.lastIndex = 0;
    while ((match = TOKEN_PATTERN.exec(source)) !== null) {
      out += escapeHtml(source.slice(lastIndex, match.index));
      var token = match[0];

      if (match[2] !== undefined || match[4] !== undefined) {
        out += span('tok-str', token);
      } else if (match[5] !== undefined) {
        out += span('tok-comment', token);
      } else if (match[6] !== undefined) {
        out += span('tok-decorator', token);
      } else if (match[7] !== undefined) {
        out += span('tok-num', token);
      } else if (match[8] !== undefined) {
        out += identifier(token, previousWord);
        previousWord = token;
      } else if (match[9] !== undefined) {
        out += span('tok-op', token);
      } else {
        out += escapeHtml(token);
      }

      if (match[8] === undefined) {
        previousWord = '';
      }
      lastIndex = match.index + token.length;
    }

    out += escapeHtml(source.slice(lastIndex));
    return out;
  }

  function identifier(name, previousWord) {
    if (previousWord === 'def' || previousWord === 'class') {
      return span('tok-def', name);
    }
    if (KEYWORD_SET[name]) {
      return span('tok-kw', name);
    }
    if (CONSTANT_SET[name]) {
      return span('tok-num', name);
    }
    if (name === 'self' || name === 'cls') {
      return span('tok-self', name);
    }
    if (BUILTIN_SET[name]) {
      return span('tok-builtin', name);
    }
    return escapeHtml(name);
  }

  function span(className, text) {
    return '<span class="' + className + '">' + escapeHtml(text) + '</span>';
  }

  // -------------------------------------------------------- other languages

  /*
   * One tokeniser serves every curly-brace language, plus the shell-shaped
   * ones. What changes between them is a word list and which characters open
   * a comment or a string, so that is all a grammar holds; writing a separate
   * highlighter per language would be a dozen copies of the same loop.
   */
  var GRAMMARS = {
    clike: {
      line: '//', block: ['/*', '*/'], quotes: '"\'`',
      keywords: ('break case catch class const continue default do else enum export extends ' +
        'finally for function goto if implements import in instanceof interface let new ' +
        'package private protected public return static switch this throw throws try typeof ' +
        'var void while with yield async await of delete').split(' '),
      constants: ['true', 'false', 'null', 'undefined', 'NaN', 'Infinity'],
      builtins: ('console document window Math JSON Object Array String Number Boolean ' +
        'Promise Map Set Symbol RegExp Date Error parseInt parseFloat isNaN setTimeout ' +
        'setInterval fetch require module exports').split(' ')
    },
    c: {
      line: '//', block: ['/*', '*/'], quotes: '"\'',
      keywords: ('auto break case char const continue default do double else enum extern ' +
        'float for goto if inline int long register restrict return short signed sizeof ' +
        'static struct switch typedef union unsigned void volatile while class public ' +
        'private protected virtual template namespace using new delete').split(' '),
      constants: ['NULL', 'true', 'false', 'EOF'],
      builtins: ('printf scanf malloc calloc realloc free strlen strcpy strcmp memset ' +
        'memcpy fopen fclose fgets puts putchar getchar exit abs sqrt pow').split(' '),
      preprocessor: true
    },
    pycmd: {
      line: '#', block: null, quotes: '"\'',
      keywords: ('let var const fn return if elif else while for in loop break continue match ' +
        'struct enum extends and or not try catch finally throw use as is assert test self pub').split(' '),
      constants: ['true', 'false', 'nil'],
      builtins: ('print input len str int float bool type range abs min max sum round sorted ' +
        'reversed enumerate zip keys values items set list map filter reduce Error exit any all ' +
        'math random time json fs regex stats text http color sys').split(' ')
    },
    go: {
      line: '//', block: ['/*', '*/'], quotes: '"\'`',
      keywords: ('break case chan const continue default defer else fallthrough for func go ' +
        'goto if import interface map package range return select struct switch type var').split(' '),
      constants: ['true', 'false', 'nil', 'iota'],
      builtins: ('append cap close complex copy delete len make new panic print println ' +
        'recover string int int64 float64 bool byte rune error fmt strings strconv').split(' ')
    },
    rust: {
      line: '//', block: ['/*', '*/'], quotes: '"\'',
      keywords: ('as async await break const continue crate dyn else enum extern fn for if ' +
        'impl in let loop match mod move mut pub ref return self Self static struct super ' +
        'trait type unsafe use where while').split(' '),
      constants: ['true', 'false', 'None', 'Some', 'Ok', 'Err'],
      builtins: ('println print format vec panic assert String Vec HashMap HashSet Option ' +
        'Result Box Rc RefCell i32 i64 u32 u64 usize f64 bool char str').split(' ')
    },
    shell: {
      line: '#', block: null, quotes: '"\'',
      keywords: ('if then else elif fi for while do done case esac in function return exit ' +
        'export local source break continue').split(' '),
      constants: ['true', 'false'],
      builtins: ('echo cd ls cat grep sed awk mkdir rm cp mv chmod curl wget python pip ' +
        'git test read printf').split(' ')
    },
    sql: {
      line: '--', block: ['/*', '*/'], quotes: '"\'', caseInsensitive: true,
      keywords: ('select from where insert into values update set delete create table drop ' +
        'alter add index primary key foreign references join left right inner outer on ' +
        'group by order having limit offset distinct as and or not null like between union ' +
        'default unique constraint check exists case when then else end').split(' '),
      constants: ['null', 'true', 'false'],
      builtins: ('count sum avg min max integer text real blob varchar boolean timestamp ' +
        'date now coalesce cast').split(' ')
    },
    ini: {
      line: '#', block: null, quotes: '"\'',
      keywords: [], constants: ['true', 'false', 'yes', 'no', 'on', 'off'], builtins: []
    },
    json: {
      line: null, block: null, quotes: '"',
      keywords: [], constants: ['true', 'false', 'null'], builtins: []
    }
  };

  GRAMMARS.javascript = GRAMMARS.clike;
  GRAMMARS.yaml = GRAMMARS.ini;
  GRAMMARS.toml = GRAMMARS.ini;
  GRAMMARS.text = { line: null, block: null, quotes: '', keywords: [], constants: [],
                    builtins: [] };

  function buildPattern(grammar) {
    var parts = [];
    if (grammar.block) {
      parts.push('(' + escapeRegex(grammar.block[0]) + '[^]*?' +
                 escapeRegex(grammar.block[1]) + ')');
    } else {
      parts.push('(\\u0000BLOCK)');
    }
    parts.push(grammar.line ? '(' + escapeRegex(grammar.line) + '[^\\n]*)'
                            : '(\\u0000LINE)');
    if (grammar.quotes) {
      var quoted = [];
      for (var i = 0; i < grammar.quotes.length; i += 1) {
        var q = escapeRegex(grammar.quotes[i]);
        quoted.push(q + '(?:\\\\.|[^' + q + '\\\\])*' + q);
      }
      parts.push('(' + quoted.join('|') + ')');
    } else {
      parts.push('(\\u0000STR)');
    }
    parts.push(grammar.preprocessor ? '(^[ \\t]*#[A-Za-z]+[^\\n]*)' : '(\\u0000PRE)');
    parts.push('(\\b(?:0[xXbBoO][0-9a-fA-F_]+|\\d[\\d_]*(?:\\.[\\d_]*)?' +
               '(?:[eE][+-]?\\d+)?)[a-zA-Z_]*\\b)');
    parts.push('([A-Za-z_$][A-Za-z0-9_$]*)');
    parts.push('([+\\-*/%=<>!&|^~?:]+)');
    return new RegExp(parts.join('|'), 'gm');
  }

  function escapeRegex(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function highlightGeneric(source, grammar) {
    var pattern = grammar.pattern || (grammar.pattern = buildPattern(grammar));
    var keywords = grammar.keywordSet ||
      (grammar.keywordSet = toSet(grammar.keywords));
    var constants = grammar.constantSet ||
      (grammar.constantSet = toSet(grammar.constants));
    var builtins = grammar.builtinSet ||
      (grammar.builtinSet = toSet(grammar.builtins));

    var out = '';
    var lastIndex = 0;
    var previousWord = '';
    var match;

    pattern.lastIndex = 0;
    while ((match = pattern.exec(source)) !== null) {
      out += escapeHtml(source.slice(lastIndex, match.index));
      var token = match[0];

      if (match[1] !== undefined || match[2] !== undefined) {
        out += span('tok-comment', token);
      } else if (match[3] !== undefined) {
        out += span('tok-str', token);
      } else if (match[4] !== undefined) {
        out += span('tok-decorator', token);
      } else if (match[5] !== undefined) {
        out += span('tok-num', token);
      } else if (match[6] !== undefined) {
        var word = grammar.caseInsensitive ? token.toLowerCase() : token;
        if (previousWord === 'fn' || previousWord === 'func' || previousWord === 'function' ||
            previousWord === 'class' || previousWord === 'struct' || previousWord === 'def') {
          out += span('tok-def', token);
        } else if (keywords[word]) {
          out += span('tok-kw', token);
        } else if (constants[word]) {
          out += span('tok-num', token);
        } else if (word === 'self' || word === 'this') {
          out += span('tok-self', token);
        } else if (builtins[word]) {
          out += span('tok-builtin', token);
        } else {
          out += escapeHtml(token);
        }
        previousWord = word;
      } else if (match[7] !== undefined) {
        out += span('tok-op', token);
      } else {
        out += escapeHtml(token);
      }

      if (match[6] === undefined) {
        previousWord = '';
      }
      lastIndex = match.index + token.length;
    }

    out += escapeHtml(source.slice(lastIndex));
    return out;
  }

  // Markup and stylesheets are shaped differently enough to be worth their own
  // small passes rather than a grammar entry that fits neither.
  var HTML_PATTERN = /(<!--[^]*?-->)|(<\/?)([A-Za-z][\w:-]*)((?:[^>"']|"[^"]*"|'[^']*')*)(>)|(&[a-zA-Z#0-9]+;)/g;
  var ATTRIBUTE_PATTERN = /([A-Za-z_:][-\w:.]*)(\s*=\s*)("[^"]*"|'[^']*'|[^\s>]+)?/g;

  function highlightHtml(source) {
    var out = '';
    var lastIndex = 0;
    var match;
    HTML_PATTERN.lastIndex = 0;
    while ((match = HTML_PATTERN.exec(source)) !== null) {
      out += escapeHtml(source.slice(lastIndex, match.index));
      if (match[1] !== undefined) {
        out += span('tok-comment', match[1]);
      } else if (match[6] !== undefined) {
        out += span('tok-num', match[6]);
      } else {
        out += span('tok-op', match[2]) + span('tok-kw', match[3]) +
               highlightAttributes(match[4] || '') + span('tok-op', match[5]);
      }
      lastIndex = match.index + match[0].length;
    }
    out += escapeHtml(source.slice(lastIndex));
    return out;
  }

  function highlightAttributes(text) {
    var out = '';
    var lastIndex = 0;
    var match;
    ATTRIBUTE_PATTERN.lastIndex = 0;
    while ((match = ATTRIBUTE_PATTERN.exec(text)) !== null) {
      out += escapeHtml(text.slice(lastIndex, match.index));
      out += span('tok-builtin', match[1]) + escapeHtml(match[2]);
      if (match[3] !== undefined) {
        out += span('tok-str', match[3]);
      }
      lastIndex = match.index + match[0].length;
    }
    return out + escapeHtml(text.slice(lastIndex));
  }

  var CSS_PATTERN = /(\/\*[^]*?\*\/)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(@[\w-]+)|([\w-]+)(\s*:)|(#[0-9a-fA-F]{3,8}\b|\b\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|s|ms|deg|fr)?\b)/g;

  function highlightCss(source) {
    var out = '';
    var lastIndex = 0;
    var match;
    CSS_PATTERN.lastIndex = 0;
    while ((match = CSS_PATTERN.exec(source)) !== null) {
      out += escapeHtml(source.slice(lastIndex, match.index));
      if (match[1] !== undefined) {
        out += span('tok-comment', match[1]);
      } else if (match[2] !== undefined) {
        out += span('tok-str', match[2]);
      } else if (match[3] !== undefined) {
        out += span('tok-decorator', match[3]);
      } else if (match[4] !== undefined) {
        out += span('tok-builtin', match[4]) + escapeHtml(match[5]);
      } else {
        out += span('tok-num', match[6]);
      }
      lastIndex = match.index + match[0].length;
    }
    out += escapeHtml(source.slice(lastIndex));
    return out;
  }

  var MARKDOWN_PATTERN = /(^#{1,6} [^\n]*)|(```[^]*?```|`[^`\n]+`)|(\*\*[^*\n]+\*\*|__[^_\n]+__)|(\[[^\]\n]*\]\([^)\n]*\))|(^\s*(?:[-*+]|\d+[.)]) )|(^>[^\n]*)/gm;

  function highlightMarkdown(source) {
    var out = '';
    var lastIndex = 0;
    var match;
    MARKDOWN_PATTERN.lastIndex = 0;
    while ((match = MARKDOWN_PATTERN.exec(source)) !== null) {
      out += escapeHtml(source.slice(lastIndex, match.index));
      if (match[1] !== undefined) {
        out += span('tok-def', match[1]);
      } else if (match[2] !== undefined) {
        out += span('tok-str', match[2]);
      } else if (match[3] !== undefined) {
        out += span('tok-kw', match[3]);
      } else if (match[4] !== undefined) {
        out += span('tok-builtin', match[4]);
      } else if (match[5] !== undefined) {
        out += span('tok-op', match[5]);
      } else {
        out += span('tok-comment', match[6]);
      }
      lastIndex = match.index + match[0].length;
    }
    out += escapeHtml(source.slice(lastIndex));
    return out;
  }

  var current = 'python';

  function highlightAny(source) {
    if (current === 'python') return highlight(source);
    if (current === 'html') return highlightHtml(source);
    if (current === 'css') return highlightCss(source);
    if (current === 'markdown') return highlightMarkdown(source);
    var grammar = GRAMMARS[current];
    if (!grammar) return escapeHtml(source);
    return highlightGeneric(source, grammar);
  }

  global.PyHighlight = {
    highlight: highlightAny,
    python: highlight,
    setLanguage: function (name) {
      current = name && (name === 'python' || name === 'html' || name === 'css' ||
                         name === 'markdown' || GRAMMARS[name]) ? name : 'text';
    },
    language: function () { return current; },
    keywords: KEYWORDS,
    builtins: BUILTINS
  };
})(window);
