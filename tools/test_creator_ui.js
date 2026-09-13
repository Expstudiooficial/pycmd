/*
 * Drives the Creator panel the way a finger does, without a WebView.
 *
 * The panel is the half of Creator that `tools/test_creator.py` cannot reach:
 * the compiler is checked there, and everything that decides *what is on the
 * screen* is here. It matters because the two bugs people actually hit were
 * both in this file - a palette that showed templates instead of code, and a
 * language chooser that asked `confirm()` in a WebView with no chrome client,
 * where `confirm` answers "no" without asking anybody. Neither could be seen
 * from Python, and both are one assertion away here.
 *
 * The shim is small and honest about it: enough DOM for this page, node's own
 * Promise and timers, and a bridge that answers with the *real* catalogue,
 * fetched by running the plugin's own Python. So what the panel renders here
 * is what it renders on a phone, minus the WebView's own behaviour.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { execFileSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const CREATOR = path.join(ROOT, 'app', 'src', 'main', 'assets', 'plugins', 'creator');
const PYTHON = process.env.PYTHON || 'python3.13';

let failures = 0;

function check(name, condition, detail) {
  if (condition) {
    console.log(`  PASS  ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL  ${name}  ${detail === undefined ? '' : JSON.stringify(detail)}`);
  }
}

// ---------------------------------------------------------------- the bridge

/** Runs the plugin's own catalogue and compiler, so the fixtures are real. */
function python(script) {
  const source = `
import json, sys
sys.path.insert(0, ${JSON.stringify(CREATOR)})
import creator_blocks as blocks
${script}
`;
  return JSON.parse(execFileSync(PYTHON, ['-c', source], { encoding: 'utf8' }));
}

const fixtures = python(`
languages = [dict(row, blocks=len(blocks.BLOCKS[row["id"]])) for row in blocks.LANGUAGES]
sys.stdout.write(json.dumps({
    "languages": {"ok": True, "languages": languages, "total": len(blocks.BY_ID)},
    "catalogues": {row["id"]: blocks.catalogue(row["id"]) for row in blocks.LANGUAGES},
}))
`);


/** How many blocks a language really has, so the checks below cannot go stale. */
function blockCount(language) {
  const found = fixtures.languages.languages.find((row) => row.id === language);
  return found ? found.blocks : -1;
}

function build(project) {
  return python(`
project = json.loads(${JSON.stringify(JSON.stringify(project))})
sys.stdout.write(json.dumps(blocks.compile_project(project)))
`);
}

// ------------------------------------------------------------------ the DOM

function makeElement(tag) {
  const element = {
    tagName: String(tag || 'div').toUpperCase(),
    children: [],
    listeners: {},
    attributes: {},
    style: {},
    className: '',
    value: '',
    id: '',
    _text: '',
    _html: '',
    get textContent() {
      if (this._text) return this._text;
      return this.children.map((child) => child.textContent).join('');
    },
    set textContent(value) {
      this._text = String(value === undefined || value === null ? '' : value);
      this.children = [];
    },
    get innerHTML() { return this._html; },
    set innerHTML(value) {
      this._html = String(value);
      this._text = '';
      this.children = [];
    },
    appendChild(child) {
      this.children.push(child);
      this._html = '';
      return child;
    },
    addEventListener(name, handler) {
      (this.listeners[name] = this.listeners[name] || []).push(handler);
    },
    dispatch(name, event) {
      (this.listeners[name] || []).forEach((handler) =>
        handler(event || { stopPropagation() {} }));
    },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    getAttribute(name) {
      return Object.prototype.hasOwnProperty.call(this.attributes, name)
        ? this.attributes[name] : null;
    },
    querySelectorAll(selector) {
      const wanted = selector.replace(/^\[|\]$/g, '');
      const found = [];
      const walk = (node) => {
        node.children.forEach((child) => {
          if (child.getAttribute(wanted) !== null) found.push(child);
          walk(child);
        });
      };
      walk(this);
      return found;
    },
    classList: null,
  };
  element.classList = {
    add(name) {
      if (!element.className.split(/\s+/).includes(name)) {
        element.className = (element.className + ' ' + name).trim();
      }
    },
    remove(name) {
      element.className = element.className.split(/\s+/)
        .filter((part) => part && part !== name).join(' ');
    },
    contains(name) { return element.className.split(/\s+/).includes(name); },
  };
  return element;
}

/** Every element the panel reaches for, plus whatever it makes as it goes. */
function makeSandbox() {
  const nodes = {};
  const toasts = [];
  const timers = [];

  const sandbox = {
    console,
    toasts,
    timers,
    Promise,
    JSON,
    Object,
    String,
    Number,
    Array,
    document: {
      getElementById(id) {
        if (!nodes[id]) {
          nodes[id] = makeElement('div');
          nodes[id].id = id;
        }
        return nodes[id];
      },
      createElement(tag) { return makeElement(tag); },
    },
    setTimeout(fn, ms) { timers.push(fn); return timers.length; },
    clearTimeout(handle) { if (handle) timers[handle - 1] = null; },
    pycmd: {
      call(name, payload) {
        return new Promise((resolve, reject) => {
          try {
            resolve(answer(name, payload));
          } catch (error) {
            reject(error);
          }
        });
      },
      toast(text) { toasts.push(String(text)); },
      log() {},
      close() {},
      plugin: { id: 'pycmd.creator', name: 'Creator' },
    },
  };
  sandbox.window = sandbox;
  sandbox.nodes = nodes;

  function answer(name, payload) {
    const body = payload || {};
    if (name === 'languages') return fixtures.languages;
    if (name === 'catalogue') {
      const found = fixtures.catalogues[body.language];
      if (!found) return { ok: false, error: `no blocks for ${body.language}` };
      return found;
    }
    if (name === 'starter') {
      // Every language has one since 2.6.0, and the panel asks for the one
      // it is in. The real plugin reads its STARTERS table; here a small
      // stand-in for the two the checks actually use.
      if (body.language && body.language !== 'python') {
        const made = {
          css: { name: 'style', language: 'css', blocks: [
            { block: 'css.rule', values: { selector: 'body' }, children: [
              { block: 'css.padding', values: { value: '20px' } },
            ] },
          ] },
        }[body.language];
        if (!made) return { ok: false, error: `no example for ${body.language}` };
        return { ok: true, folder: '', project: made };
      }
      return {
        ok: true,
        folder: '',
        project: {
          name: 'hello',
          language: 'python',
          blocks: [
            { block: 'py.print', values: { text: 'Hello from PyCmd' } },
            {
              block: 'py.repeat',
              values: { var: 'i', times: '3' },
              children: [{ block: 'py.print_value', values: { value: 'i' } }],
            },
          ],
        },
      };
    }
    if (name === 'build') return build(body.project);
    if (name === 'projects') return { ok: true, projects: [], max: 60 };
    if (name === 'save_project') return { ok: true, id: 'cr1' };
    if (name === 'save_file') return { ok: true, path: 'hello.py', lines: 3, blocks: 3, problems: [] };
    return { ok: false, error: `no export called ${name}` };
  }

  return sandbox;
}

/** Runs every timer the panel queued, and everything they queue in turn. */
function settle(sandbox) {
  for (let round = 0; round < 12; round += 1) {
    const pending = sandbox.timers.splice(0, sandbox.timers.length);
    pending.forEach((fn) => { if (fn) fn(); });
  }
}

function flush() {
  // The panel's chain is promise-based; a few microtask turns lets it finish.
  return new Promise((resolve) => setImmediate(resolve));
}

async function start() {
  const sandbox = makeSandbox();
  vm.createContext(sandbox);
  const page = fs.readFileSync(path.join(CREATOR, 'ui.html'), 'utf8');
  const script = page.slice(page.lastIndexOf('<script>') + '<script>'.length,
                            page.lastIndexOf('</script>'));
  vm.runInContext(script, sandbox);
  for (let i = 0; i < 8; i += 1) {
    await flush();
    settle(sandbox);
  }
  return sandbox;
}

/**
 * An element by id.
 *
 * Through the document rather than the node map: the shim only makes a node
 * when the page asks for it, and a test that reaches for one the page has not
 * touched yet would find nothing there.
 */
function el(sandbox, id) {
  return sandbox.document.getElementById(id);
}

/**
 * The rows the palette has drawn.
 *
 * The panel writes them as one string of HTML rather than appending a hundred
 * and fifty elements one at a time, so there are no child nodes to hand back;
 * the rows are read out of the markup instead. Clicking one goes through the
 * container's own listener with a target that only knows its block id, which
 * is what a tap on the inner span looks like to that handler.
 */
function palette(sandbox) {
  const host = el(sandbox, 'palette');
  const html = host.innerHTML || '';
  const pattern =
    /<button class="pick" type="button" data-block="([^"]*)">([\s\S]*?)<\/button>/g;
  const rows = [];
  let match = pattern.exec(html);
  while (match !== null) {
    const id = match[1];
    const inner = match[2];
    rows.push({
      block: id,
      innerHTML: inner,
      textContent: inner.replace(/<[^>]*>/g, ''),
      dispatch(name) {
        host.dispatch(name, {
          target: {
            getAttribute(what) { return what === 'data-block' ? id : null; },
            parentNode: null,
          },
          stopPropagation() {},
        });
      },
    });
    match = pattern.exec(html);
  }
  return rows;
}

function scriptRows(sandbox) {
  const rows = [];
  const walk = (node) => {
    node.children.forEach((child) => {
      if (String(child.className).indexOf('blk') === 0) rows.push(child);
      walk(child);
    });
  };
  walk(el(sandbox, 'script'));
  return rows;
}

async function main() {
  console.log('== the panel comes up with blocks in it ==');
  const sandbox = await start();

  check('there is no error card', el(sandbox, 'trouble').children.length === 0,
        el(sandbox, 'trouble').children.map((c) => c.textContent));
  check('the starter script is on screen', scriptRows(sandbox).length === 3,
        scriptRows(sandbox).map((row) => row.textContent));
  check('and the palette is full',
        palette(sandbox).length === blockCount('python'),
        palette(sandbox).length + ' of ' + blockCount('python'));
  check('the language chooser has every language there are blocks for',
        el(sandbox, 'lang').children.length === fixtures.languages.languages.length,
        el(sandbox, 'lang').children.length + ' of '
          + fixtures.languages.languages.length);

  console.log('\n== the blocks are on a screen of their own ==');
  check('the picker starts closed',
        !el(sandbox, 'addSheet').classList.contains('open'),
        el(sandbox, 'addSheet').className);
  el(sandbox, 'openAdd').dispatch('click');
  check('and the Add a block button opens it',
        el(sandbox, 'addSheet').classList.contains('open'),
        el(sandbox, 'addSheet').className);
  check('with the whole palette in it',
        palette(sandbox).length === blockCount('python'),
        palette(sandbox).length + ' of ' + blockCount('python'));
  check('and a line saying where the next one lands',
        el(sandbox, 'where').innerHTML.indexOf('at the end') > 0,
        el(sandbox, 'where').innerHTML);
  el(sandbox, 'addDone').dispatch('click');
  check('Done closes it again',
        !el(sandbox, 'addSheet').classList.contains('open'),
        el(sandbox, 'addSheet').className);

  console.log('\n== what a block row shows is the code it writes ==');
  const first = palette(sandbox)[0];
  check('a palette row carries the filled-in line, not the template',
        first.innerHTML.indexOf('print("Hello")') >= 0 &&
        first.innerHTML.indexOf('@text@') < 0, first.innerHTML);
  const rows = scriptRows(sandbox);
  check('and a script row is the line that block wrote',
        rows[0].textContent.indexOf('print("Hello from PyCmd")') === 0,
        rows[0].textContent);
  check('with the plain-English label under it',
        rows[0].textContent.indexOf('print text') > 0, rows[0].textContent);
  check('a container says so',
        rows[1].className.indexOf('holds') >= 0, rows[1].className);
  check('and the starter is labelled as an example',
        el(sandbox, 'example').style.display === '', el(sandbox, 'example').style.display);

  console.log('\n== a language that closes its blocks shows the closing line ==');
  el(sandbox, 'lang').value = 'javascript';
  el(sandbox, 'lang').dispatch('change');
  for (let i = 0; i < 6; i += 1) { await flush(); settle(sandbox); }
  el(sandbox, 'search').value = 'after a delay';
  el(sandbox, 'search').dispatch('input');
  palette(sandbox)[0].dispatch('click');
  for (let i = 0; i < 6; i += 1) { await flush(); settle(sandbox); }
  const closings = el(sandbox, 'script').children[0].children
    .filter((child) => String(child.className).indexOf('closing') === 0);
  check('the closing line is drawn under the block',
        closings.length === 1 && closings[0].textContent === '}, 1000);',
        closings.map((c) => c.textContent));

  // And it follows the values, rather than showing the defaults forever.
  const delayRow = scriptRows(sandbox)[0];
  const delayTools = delayRow.children.filter((child) => child.className === 'tools')[0];
  const delayLabels = delayTools.children.map((button) => button.textContent);
  delayTools.children[delayLabels.indexOf('Fill in')].dispatch('click');
  const slots = el(sandbox, 'editFields').querySelectorAll('[data-slot]');
  slots[0].value = '250';
  el(sandbox, 'editOk').dispatch('click');
  for (let i = 0; i < 6; i += 1) { await flush(); settle(sandbox); }
  const after = el(sandbox, 'script').children[0].children
    .filter((child) => String(child.className).indexOf('closing') === 0);
  check('and it follows what was filled in',
        after.length === 1 && after[0].textContent === '}, 250);',
        after.map((c) => c.textContent));
  el(sandbox, 'search').value = '';
  el(sandbox, 'search').dispatch('input');

  console.log('\n== switching language keeps both scripts ==');
  el(sandbox, 'lang').value = 'css';
  el(sandbox, 'lang').dispatch('change');
  for (let i = 0; i < 6; i += 1) { await flush(); settle(sandbox); }
  check('the CSS blocks arrived',
        palette(sandbox).length === blockCount('css'),
        palette(sandbox).length + ' of ' + blockCount('css'));
  check('no error card', el(sandbox, 'trouble').children.length === 0,
        el(sandbox, 'trouble').children.map((c) => c.textContent));
  check('the CSS script starts empty', scriptRows(sandbox).length === 0,
        scriptRows(sandbox).length);
  check('and nothing was thrown away',
        sandbox.window.__creator.drafts.python.blocks.length === 2,
        Object.keys(sandbox.window.__creator.drafts));
  check('no question was asked to get here', sandbox.toasts.length === 0, sandbox.toasts);

  console.log('\n== the language line and the example button ==');
  check('the chooser says how many blocks and whether it runs here',
        el(sandbox, 'lang').children.some((option) =>
          option.textContent.includes('Rust') && option.textContent.includes('runs here')),
        el(sandbox, 'lang').children.map((o) => o.textContent).slice(0, 3));
  check('and a language that only gets served does not claim to run',
        el(sandbox, 'lang').children.some((option) =>
          option.textContent.includes('CSS') && !option.textContent.includes('runs here')),
        el(sandbox, 'lang').children.map((o) => o.textContent));
  check('the line under it says what the language is for',
        el(sandbox, 'about').textContent.length > 10,
        el(sandbox, 'about').textContent);

  // Still in CSS, with an empty script, so Example fills it without asking.
  el(sandbox, 'example-load').dispatch('click');
  for (let i = 0; i < 6; i += 1) { await flush(); settle(sandbox); }
  check('Example fills an empty script with something that works',
        scriptRows(sandbox).length === 2, scriptRows(sandbox).length);
  check('and says so', sandbox.toasts.some((text) => text.includes('example')),
        sandbox.toasts);

  // With blocks in it, it asks first rather than throwing work away.
  sandbox.toasts.length = 0;
  el(sandbox, 'example-load').dispatch('click');
  await flush();
  check('a second press asks before replacing what is there',
        el(sandbox, 'askSheet').className.includes('open'),
        el(sandbox, 'askSheet').className);
  el(sandbox, 'askCancel').dispatch('click');
  for (let i = 0; i < 4; i += 1) { await flush(); settle(sandbox); }
  check('and saying no leaves the script alone', scriptRows(sandbox).length === 2,
        scriptRows(sandbox).length);

  el(sandbox, 'lang').value = 'python';
  el(sandbox, 'lang').dispatch('change');
  for (let i = 0; i < 6; i += 1) { await flush(); settle(sandbox); }

  console.log('\n== every language loads its own blocks ==');
  const counts = {};
  ['javascript', 'html', 'markdown', 'python', 'c', 'go', 'rust', 'shell', 'json']
    .forEach((language) => { counts[language] = blockCount(language); });
  for (const [language, expected] of Object.entries(counts)) {
    el(sandbox, 'lang').value = language;
    el(sandbox, 'lang').dispatch('change');
    for (let i = 0; i < 6; i += 1) { await flush(); settle(sandbox); }
    check(`${language} shows ${expected} blocks`, palette(sandbox).length === expected,
          palette(sandbox).length);
  }
  check('and the python script survived all of that',
        sandbox.window.__creator.drafts.python.blocks.length === 2);

  console.log('\n== building a script by tapping ==');
  el(sandbox, 'lang').value = 'python';
  el(sandbox, 'lang').dispatch('change');
  for (let i = 0; i < 6; i += 1) { await flush(); settle(sandbox); }

  // Tap the loop in the script, then a block in the palette: it goes inside.
  const loop = scriptRows(sandbox)[1];
  loop.dispatch('click');
  check('selecting a container says where the next block goes',
        el(sandbox, 'where').innerHTML.indexOf('inside') >= 0,
        el(sandbox, 'where').innerHTML);
  check('and the script heading says it too, without opening anything',
        el(sandbox, 'hint').textContent.indexOf('inside') > 0,
        el(sandbox, 'hint').textContent);

  const search = el(sandbox, 'search');
  search.value = 'print text';
  search.dispatch('input');
  check('search narrows the palette', palette(sandbox).length >= 1 &&
        palette(sandbox).length < 20, palette(sandbox).length);
  palette(sandbox)[0].dispatch('click');
  for (let i = 0; i < 6; i += 1) { await flush(); settle(sandbox); }

  const tree = sandbox.window.__creator.drafts.python.blocks;
  check('the block landed inside the loop', tree[1].children.length === 2,
        tree[1].children.length);
  check('and the picker said so rather than looking like nothing happened',
        el(sandbox, 'added').textContent.indexOf('Added "print text"') === 0,
        el(sandbox, 'added').textContent);
  check('and the example note went the moment it was edited',
        el(sandbox, 'example').style.display === 'none',
        el(sandbox, 'example').style.display);
  check('and the script shows four rows now', scriptRows(sandbox).length === 4,
        scriptRows(sandbox).length);
  check('the new row is indented in the code it shows',
        scriptRows(sandbox)[3].textContent.indexOf('print("Hello")') === 0,
        scriptRows(sandbox)[3].textContent);

  console.log('\n== the picker forgets what you searched for ==');
  el(sandbox, 'search').value = 'print text';
  el(sandbox, 'search').dispatch('input');
  const narrowed = palette(sandbox).length;
  el(sandbox, 'addDone').dispatch('click');
  el(sandbox, 'openAdd').dispatch('click');
  check('opening it again shows every block, not the last search',
        palette(sandbox).length > narrowed && el(sandbox, 'search').value === '',
        [narrowed, palette(sandbox).length]);
  el(sandbox, 'addDone').dispatch('click');

  console.log('\n== a line stays with its block when things move ==');
  // Delete the first block: every path below it shifts by one, and the lines
  // must shift with the blocks rather than staying where the paths were.
  // The click redraws, so the row has to be read again afterwards.
  scriptRows(sandbox)[0].dispatch('click');
  const top = scriptRows(sandbox)[0];
  const topTools = top.children.filter((child) => child.className === 'tools')[0];
  const topLabels = topTools.children.map((button) => button.textContent);
  topTools.children[topLabels.indexOf('Delete')].dispatch('click');
  for (let i = 0; i < 6; i += 1) { await flush(); settle(sandbox); }
  check('the loop is the first row now',
        scriptRows(sandbox)[0].textContent.indexOf('for i in range(3):') === 0,
        scriptRows(sandbox)[0].textContent);
  check('and the line under it belongs to it',
        scriptRows(sandbox)[1].textContent.indexOf('print(i)') === 0,
        scriptRows(sandbox)[1].textContent);

  // Put it back, so the rest of the file reads against the same script.
  el(sandbox, 'search').value = 'print text';
  el(sandbox, 'search').dispatch('input');
  palette(sandbox)[0].dispatch('click');
  for (let i = 0; i < 6; i += 1) { await flush(); settle(sandbox); }

  console.log('\n== the tools on a selected block ==');
  // Row 2 is the second block inside the loop - a nested one, so "Move out"
  // has somewhere to move it to.
  scriptRows(sandbox)[2].dispatch('click');
  const selected = scriptRows(sandbox)[2];
  const tools = selected.children.filter((child) => child.className === 'tools')[0];
  check('a selected block offers its tools', !!tools, selected.children.length);
  const labels = tools.children.map((button) => button.textContent);
  check('and they are words rather than arrows',
        labels.indexOf('Move inside') >= 0 && labels.indexOf('Delete') >= 0, labels);

  const before = sandbox.window.__creator.drafts.python.blocks.length;
  tools.children[labels.indexOf('Move out')].dispatch('click');
  for (let i = 0; i < 6; i += 1) { await flush(); settle(sandbox); }
  check('moving one out lifts it a level',
        sandbox.window.__creator.drafts.python.blocks.length === before + 1,
        sandbox.window.__creator.drafts.python.blocks.length);

  scriptRows(sandbox)[0].dispatch('click');
  const already = scriptRows(sandbox)[0];
  const outTools = already.children.filter((child) => child.className === 'tools')[0];
  const outLabels = outTools.children.map((button) => button.textContent);
  const toasts = sandbox.toasts.length;
  outTools.children[outLabels.indexOf('Move out')].dispatch('click');
  check('and one already at the top level says so rather than vanishing',
        sandbox.toasts.length === toasts + 1 &&
        sandbox.window.__creator.drafts.python.blocks.length === before + 1,
        sandbox.toasts.slice(-1));

  console.log('\n== nothing here asks a WebView for a dialog ==');
  const source = fs.readFileSync(path.join(CREATOR, 'ui.html'), 'utf8');
  // Comments are allowed to name them - explaining why they are not used is
  // most of the point - so the code is checked with the comments taken out.
  const scriptBody = source.slice(source.lastIndexOf('<script>'))
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/(^|\n)\s*\/\/[^\n]*/g, '$1');
  check('no confirm()', !/[^.\w]confirm\s*\(/.test(scriptBody));
  check('no alert()', !/[^.\w]alert\s*\(/.test(scriptBody));
  check('no prompt()', !/[^.\w]prompt\s*\(/.test(scriptBody));

  console.log('\n== a bridge that fails says so on the page ==');
  const broken = makeSandbox();
  broken.pycmd.call = function () {
    return Promise.reject(new Error('the interpreter is not ready'));
  };
  vm.createContext(broken);
  const page = fs.readFileSync(path.join(CREATOR, 'ui.html'), 'utf8');
  vm.runInContext(
    page.slice(page.lastIndexOf('<script>') + '<script>'.length, page.lastIndexOf('</script>')),
    broken,
  );
  for (let i = 0; i < 6; i += 1) { await flush(); settle(broken); }
  check('the panel shows what went wrong instead of an empty screen',
        el(broken, 'trouble').children.length === 1 &&
        el(broken, 'trouble').children[0].textContent.indexOf('not ready') > 0,
        el(broken, 'trouble').children.map((c) => c.textContent));

  console.log('');
  if (failures) {
    console.log(`${failures} creator panel checks failed`);
    process.exit(1);
  }
  console.log('all creator panel checks passed');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
