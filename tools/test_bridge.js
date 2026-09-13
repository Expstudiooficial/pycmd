/*
 * Checks the bridge every plugin panel is given.
 *
 * `pycmd.call`, `pycmd.poll` and `__pycmd_resolve` are the only way a panel
 * talks to the app, and they are defined once, in `BRIDGE` inside
 * `pycmd_plugins.py`. The WebView is not available here, so this pulls that
 * script out of the Python source and runs it in a V8 context with a stand-in
 * for the Kotlin object it calls into - the same file the device loads, and
 * the same call sequence.
 *
 * What it is really guarding is the difference between the two verbs: a
 * refresh that repeats should join the one already out, and a button pressed
 * twice should be two calls. Getting that backwards is how a panel silently
 * loses somebody's work.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SOURCE = path.join(__dirname, '..', 'app', 'src', 'main', 'python', 'pycmd_plugins.py');

let failures = 0;
let checks = 0;

function check(name, condition, detail) {
  checks += 1;
  if (condition) {
    console.log(`  PASS  ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL  ${name}${detail === undefined ? '' : `  (${JSON.stringify(detail)})`}`);
  }
}

/** The bridge's JavaScript, taken out of the Python file that ships it. */
function bridgeSource() {
  const python = fs.readFileSync(SOURCE, 'utf8');
  const start = python.indexOf('BRIDGE = """');
  if (start < 0) throw new Error('BRIDGE is not in pycmd_plugins.py any more');
  const body = python.slice(start + 'BRIDGE = """'.length);
  const end = body.indexOf('"""');
  if (end < 0) throw new Error('BRIDGE is not closed');
  const html = body.slice(0, end);
  const open = html.indexOf('<script>');
  const close = html.lastIndexOf('</script>');
  return html.slice(open + '<script>'.length, close);
}

/**
 * A context with the bridge loaded and the Kotlin side written down.
 *
 * `sent` is every call that actually reached the app, which is the whole
 * point: what the panel asked for and what crossed the bridge are different
 * lists, and the difference is what these checks are about.
 */
function makeBridge() {
  const sent = [];
  const context = vm.createContext({ console, Promise, JSON, String, Error });
  // Real timers, but not ones that keep node alive: the bridge arms a
  // two-minute deadline per call, and a suite that waited for those would
  // take two minutes to say it had passed.
  const armed = new Map();
  let nextTimer = 1;
  context.setTimeout = (fn, ms) => {
    const id = nextTimer++;
    const handle = setTimeout(() => { armed.delete(id); fn(); }, ms || 0);
    if (handle.unref) handle.unref();
    armed.set(id, handle);
    return id;
  };
  context.clearTimeout = (id) => {
    if (armed.has(id)) { clearTimeout(armed.get(id)); armed.delete(id); }
  };
  vm.runInContext('globalThis.window = globalThis;', context);
  context.addEventListener = () => {};
  // Enough of a document for the bridge to attach its touch hook to; the
  // cases that care about that hook build a proper one of their own.
  context.document = { body: null, addEventListener() {} };
  context.window.getComputedStyle = () => ({ overflowY: 'visible' });
  context.__pycmd_panel = {
    call(id, name, body) { sent.push({ id, name, body }); },
    toast() {},
    log() {},
    close() {},
    manifest() { return JSON.stringify({ id: 'test.plugin', name: 'Test' }); },
  };
  vm.runInContext(bridgeSource(), context);
  return {
    context,
    sent,
    pycmd: context.window.pycmd,
    /** Answers one outstanding call the way Kotlin does. */
    answer(id, ok, payload) {
      context.window.__pycmd_resolve(String(id), ok, JSON.stringify(payload));
    },
  };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

async function main() {
  console.log('== the bridge is there at all ==');
  {
    const bridge = makeBridge();
    check('pycmd.call exists', typeof bridge.pycmd.call === 'function');
    check('pycmd.poll exists', typeof bridge.pycmd.poll === 'function');
    check('and the plugin it belongs to came through',
          bridge.pycmd.plugin.id === 'test.plugin', bridge.pycmd.plugin);
  }

  console.log('\n== a call goes out and comes back ==');
  {
    const bridge = makeBridge();
    const promise = bridge.pycmd.call('listing', { a: 1 });
    check('it crossed the bridge once', bridge.sent.length === 1, bridge.sent);
    check('with its arguments as JSON', bridge.sent[0].body === '{"a":1}', bridge.sent[0]);
    bridge.answer(bridge.sent[0].id, true, { ok: true, result: { rows: 3 } });
    const answer = await promise;
    check('and the result is unwrapped', answer && answer.rows === 3, answer);
  }

  console.log('\n== a failure reaches the panel as one ==');
  {
    const bridge = makeBridge();
    const promise = bridge.pycmd.call('boom', {});
    bridge.answer(bridge.sent[0].id, false, { ok: false, error: 'no such export' });
    let message = '';
    try { await promise; } catch (error) { message = error.message; }
    check('the panel is told why', message === 'no such export', message);
  }

  console.log('\n== two presses of the same button are two calls ==');
  {
    const bridge = makeBridge();
    // This is the one that matters. A panel's "Add" with the same values in
    // it twice is two jobs; a bridge that folded them into one would drop the
    // second silently, and nothing on screen would say so.
    const first = bridge.pycmd.call('add', { path: 'job.py' });
    const second = bridge.pycmd.call('add', { path: 'job.py' });
    check('both crossed', bridge.sent.length === 2, bridge.sent);
    check('and they are separate promises', first !== second);
    bridge.answer(bridge.sent[0].id, true, { ok: true, result: 'one' });
    bridge.answer(bridge.sent[1].id, true, { ok: true, result: 'two' });
    check('each got its own answer',
          (await first) === 'one' && (await second) === 'two');
  }

  console.log('\n== a refresh that repeats joins the one already out ==');
  {
    const bridge = makeBridge();
    const first = bridge.pycmd.poll('board_now', {});
    const second = bridge.pycmd.poll('board_now', {});
    const third = bridge.pycmd.poll('board_now', {});
    check('only one question was asked', bridge.sent.length === 1, bridge.sent);
    check('and all three are waiting on it', first === second && second === third);
    bridge.answer(bridge.sent[0].id, true, { ok: true, result: ['a'] });
    const all = await Promise.all([first, second, third]);
    check('everybody got the answer',
          all.every((row) => Array.isArray(row) && row[0] === 'a'), all);
  }

  console.log('\n== once it has answered, the next refresh really asks ==');
  {
    const bridge = makeBridge();
    const first = bridge.pycmd.poll('board_now', {});
    bridge.answer(bridge.sent[0].id, true, { ok: true, result: 1 });
    await first;
    await tick();
    bridge.pycmd.poll('board_now', {});
    check('a second round is a second call', bridge.sent.length === 2, bridge.sent);
  }

  console.log('\n== a poll of something else is not the same question ==');
  {
    const bridge = makeBridge();
    bridge.pycmd.poll('board_now', {});
    bridge.pycmd.poll('board_now', { verbose: true });
    bridge.pycmd.poll('jobs', {});
    check('different arguments and names go separately',
          bridge.sent.length === 3, bridge.sent);
  }

  console.log('\n== a call that never comes back does not wedge the page ==');
  {
    // The real wait is two minutes, which is not a thing to sit through here;
    // what is checked is that a timer was armed at all and that answering
    // disarms it, because a timer left running would reject a promise that
    // had already resolved.
    const armed = [];
    const context = vm.createContext({ console, Promise, JSON, String, Error });
    vm.runInContext('globalThis.window = globalThis;', context);
    context.addEventListener = () => {};
    context.setTimeout = (fn, ms) => { armed.push({ fn, ms, live: true }); return armed.length; };
    context.clearTimeout = (id) => { if (armed[id - 1]) armed[id - 1].live = false; };
    const sent = [];
    context.document = { body: null, addEventListener() {} };
    context.window.getComputedStyle = () => ({ overflowY: 'visible' });
    context.__pycmd_panel = {
      call(id, name, body) { sent.push({ id, name, body }); },
      toast() {}, log() {}, close() {},
      manifest() { return JSON.stringify({ id: 'test.plugin' }); },
    };
    vm.runInContext(bridgeSource(), context);

    const promise = context.window.pycmd.call('slow', {});
    check('a deadline was set', armed.length === 1 && armed[0].ms === 120000, armed[0] && armed[0].ms);

    let failed = '';
    promise.catch((error) => { failed = error.message; });
    armed[0].fn();
    await tick();
    check('and when it passes the panel is told',
          failed.indexOf('has not answered') > 0, failed);

    const second = context.window.pycmd.call('quick', {});
    context.window.__pycmd_resolve(sent[1].id, true, JSON.stringify({ ok: true, result: 2 }));
    check('answering disarms the deadline', armed[1].live === false);
    check('and the answer still arrives', (await second) === 2);
  }

  console.log('\n== the page says when it scrolls something itself ==');
  {
    // A panel inside one of the app's own screens is a scrolling view in a
    // scrolling list. The app decides who owns a drag by asking the WebView
    // whether its *document* has anywhere left to go - and a panel that
    // scrolls an element instead always answers "nowhere", so the list used
    // to take the drag and the panel's own list could not be scrolled at
    // all. The bridge answers that question properly on every touch.
    const listeners = {};
    const context = vm.createContext({ console, Promise, JSON, String, Error, RegExp });
    vm.runInContext('globalThis.window = globalThis;', context);
    context.setTimeout = () => 1;
    context.clearTimeout = () => {};
    context.addEventListener = () => {};

    // Three nodes: a button inside a list that scrolls, inside a body.
    const body = { nodeType: 1, parentNode: null, overflowY: 'hidden', scrollHeight: 0, clientHeight: 0 };
    const scroller = { nodeType: 1, parentNode: body, overflowY: 'auto', scrollHeight: 900, clientHeight: 300 };
    const row = { nodeType: 1, parentNode: scroller, overflowY: 'visible', scrollHeight: 0, clientHeight: 0 };
    const fixedBar = { nodeType: 1, parentNode: body, overflowY: 'visible', scrollHeight: 0, clientHeight: 0 };
    // A list with `overflow-y: auto` that has not overflowed yet is not
    // something to hold the gesture for.
    const empty = { nodeType: 1, parentNode: body, overflowY: 'auto', scrollHeight: 300, clientHeight: 300 };

    context.document = {
      body,
      addEventListener(name, handler) { listeners[name] = handler; },
    };
    context.window.getComputedStyle = (node) => ({ overflowY: node.overflowY });

    const said = [];
    context.__pycmd_panel = {
      call() {}, toast() {}, log() {}, close() {},
      innerScroll(on) { said.push(on); },
      manifest() { return JSON.stringify({ id: 'test.plugin' }); },
    };
    vm.runInContext(bridgeSource(), context);

    check('the bridge listens for touches', typeof listeners.touchstart === 'function');

    listeners.touchstart({ target: row });
    check('a touch inside a list that scrolls says so', said[said.length - 1] === true, said);

    listeners.touchstart({ target: fixedBar });
    check('a touch on a bar that does not says so too',
          said[said.length - 1] === false, said);

    listeners.touchstart({ target: empty });
    check('and a list with nothing to scroll yet does not claim the drag',
          said[said.length - 1] === false, said);

    listeners.touchstart({ target: body });
    check('nor does the body itself', said[said.length - 1] === false, said);
  }

  console.log('\n== the page says when a finger lands on something that owns drags ==');
  {
    // The 2.6.0 bug: a slider is dragged sideways, the app behind the panel
    // is a list that scrolls up and down, and the list took the gesture a few
    // pixels in. The app decides that, but it cannot decide it well without
    // being told what the finger landed on - so the page says.
    const listeners = {};
    const context = vm.createContext({ console, Promise, JSON, String, Error, RegExp });
    vm.runInContext('globalThis.window = globalThis;', context);
    context.setTimeout = () => 1;
    context.clearTimeout = () => {};
    context.addEventListener = () => {};

    const node = (extra) => Object.assign({
      nodeType: 1, parentNode: null, overflowY: 'visible',
      scrollHeight: 0, clientHeight: 0, touchAction: 'auto',
      tagName: 'DIV',
      attributes: {},
      getAttribute(name) { return this.attributes[name] || null; },
      hasAttribute(name) { return name in this.attributes; },
    }, extra);

    const body = node({ tagName: 'BODY' });
    const slider = node({ tagName: 'INPUT', attributes: { type: 'range' }, parentNode: body });
    const colour = node({ tagName: 'INPUT', attributes: { type: 'color' }, parentNode: body });
    const text = node({ tagName: 'INPUT', attributes: { type: 'text' }, parentNode: body });
    const marked = node({ attributes: { 'data-pycmd-drag': '' }, parentNode: body });
    const noTouch = node({ touchAction: 'none', parentNode: body });
    const inside = node({ parentNode: slider });
    const plain = node({ tagName: 'P', parentNode: body });
    // A node that answers none of the DOM questions. There are more of these
    // about than you would think - SVG elements, a shadow host, whatever a
    // library put in the tree - and one of them throwing used to take the
    // *other* signal down with it.
    const awkward = {
      nodeType: 1, parentNode: body,
      get tagName() { throw new Error('no tagName here'); },
    };

    context.document = { body, addEventListener(name, handler) { listeners[name] = handler; } };
    context.window.getComputedStyle = (target) => {
      if (target === awkward) throw new Error('no style for this one');
      return { overflowY: target.overflowY, touchAction: target.touchAction };
    };

    const told = [];
    context.__pycmd_panel = {
      call() {}, toast() {}, log() {}, close() {},
      ownsGesture(scrolls, grabs) { told.push({ scrolls, grabs }); },
      innerScroll() { told.push('the old method, which should not be used here'); },
      manifest() { return JSON.stringify({ id: 'test.plugin' }); },
    };
    vm.runInContext(bridgeSource(), context);

    const last = () => told[told.length - 1];

    listeners.touchstart({ target: slider });
    check('a slider owns the drag', last().grabs === true, told);

    listeners.touchstart({ target: colour });
    check('so does a colour picker', last().grabs === true, told);

    listeners.touchstart({ target: inside });
    check('and so does anything inside one', last().grabs === true, told);

    listeners.touchstart({ target: text });
    check('a text box does not', last().grabs === false, told);

    listeners.touchstart({ target: plain });
    check('nor does ordinary text', last().grabs === false, told);

    listeners.touchstart({ target: marked });
    check('a panel can mark anything else itself', last().grabs === true, told);

    listeners.touchstart({ target: noTouch });
    check('and touch-action none says the same thing', last().grabs === true, told);

    told.length = 0;
    listeners.touchstart({ target: awkward });
    check('a node that answers nothing is not a crash', told.length === 1, told);
    check('and it reports both signals as false rather than neither',
          last() && last().scrolls === false && last().grabs === false, told);

    check('the new method is used when the host has it',
          told.every((row) => typeof row === 'object'), told);
  }

  console.log('\n== a host without that method is not a crash ==');
  {
    // The bridge ships inside the app, but a panel can be open across an
    // update, and a page calling a method the host does not have would throw
    // inside a touch handler - which is a page that stops responding.
    const listeners = {};
    const context = vm.createContext({ console, Promise, JSON, String, Error, RegExp });
    vm.runInContext('globalThis.window = globalThis;', context);
    context.setTimeout = () => 1;
    context.clearTimeout = () => {};
    context.addEventListener = () => {};
    const body = { nodeType: 1, parentNode: null, overflowY: 'hidden', scrollHeight: 0, clientHeight: 0 };
    context.document = { body, addEventListener(n, h) { listeners[n] = h; } };
    context.window.getComputedStyle = (node) => ({ overflowY: node.overflowY });
    context.__pycmd_panel = {
      call() {}, toast() {}, log() {}, close() {},
      manifest() { return JSON.stringify({ id: 'test.plugin' }); },
    };
    vm.runInContext(bridgeSource(), context);
    let threw = false;
    try { listeners.touchstart({ target: body }); } catch (error) { threw = true; }
    check('an older host is walked past quietly', !threw);
  }

  console.log(`\n${checks} checks, ${failures} failed`);
  if (failures) process.exit(1);
  console.log('all bridge checks passed');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
