/*
 * The shell: talking to Python, the tab rail, and the bits every screen uses.
 *
 * There is exactly one way to reach the app - `PyCmd.call(name, payload)` -
 * because there was exactly one on the phone too, and a single narrow bridge
 * is the thing that made the plugin system possible. `screens.js` draws; this
 * file makes the calls and holds the state.
 */
'use strict';

const PyCmd = (function () {
  const state = {
    ready: false,
    version: '',
    python: '',
    root: '',
    tab: 'console',
    languages: [],
    languageStats: {},
    toolchains: [],
    toolchainSummary: {},
    plugins: { builtin: { groups: [] }, installed: [] },
    logCount: 0,
    errorCount: 0,
    update: null,
  };

  const listeners = {};

  /**
   * The bridge.
   *
   * pywebview injects `window.pywebview.api` a moment after the page loads,
   * not before it - so a call made while the document is still parsing would
   * find nothing there. Rather than making every caller handle that, calls
   * queue until the bridge appears.
   */
  let bridgeReady = null;

  /**
   * The same two calls, over HTTP.
   *
   * A browser opened at the app's own address has no pywebview object, so it
   * falls back to this - the server answers the identical API on /api/call.
   * That is what makes `PyCmd.exe --serve-only` a real thing rather than a
   * page that draws and cannot ask anything.
   */
  const httpBridge = {
    async call(name, payload) {
      const response = await fetch('/api/call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, payload: payload || {} }),
      });
      return response.json();
    },
    async events() {
      const response = await fetch('/api/events', { method: 'POST', body: '{}' });
      return response.json();
    },
  };

  function bridge() {
    if (bridgeReady) return bridgeReady;
    bridgeReady = new Promise((resolve) => {
      if (window.pywebview && window.pywebview.api) return resolve(window.pywebview.api);
      window.addEventListener('pywebviewready', () => resolve(window.pywebview.api), { once: true });
      // No pywebview after a moment means this is a browser, not the window.
      setTimeout(() => {
        if (!(window.pywebview && window.pywebview.api)) resolve(httpBridge);
      }, 700);
    });
    return bridgeReady;
  }

  async function call(name, payload) {
    const api = await bridge();
    try {
      return await api.call(name, payload || {});
    } catch (error) {
      return { ok: false, error: String((error && error.message) || error) };
    }
  }

  function on(kind, fn) {
    (listeners[kind] = listeners[kind] || []).push(fn);
  }

  function fire(event) {
    (listeners[event.kind] || []).forEach((fn) => {
      try { fn(event); } catch (error) { console.error(error); }
    });
    (listeners['*'] || []).forEach((fn) => fn(event));
  }

  /**
   * Events come by polling rather than being pushed.
   *
   * Pushing would mean a cross-thread `evaluate_js` per line of output, and a
   * script printing in a loop would make thousands a second. One poll that
   * returns a hundred lines is cheaper, and it cannot arrive while the page is
   * mid-redraw.
   */
  async function pump() {
    const api = await bridge();
    for (;;) {
      let batch = [];
      try {
        const reply = await api.events();
        batch = (reply && reply.events) || [];
      } catch (error) {
        // The window is closing, or Python has gone. Stop quietly.
        return;
      }
      batch.forEach(fire);
      // Idle costs one call every 120ms; busy drains as fast as it can.
      await new Promise((r) => setTimeout(r, batch.length ? 0 : 120));
    }
  }

  // -- little shared helpers --------------------------------------------

  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, value]) => {
      if (value === null || value === undefined || value === false) return;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key === 'html') node.innerHTML = value;
      else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? '' : value);
    });
    children.flat().forEach((child) => {
      if (child === null || child === undefined || child === false) return;
      node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
    });
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
    return node;
  }

  function bytes(count) {
    const n = Number(count) || 0;
    if (n >= 1024 * 1024 * 1024) return (n / 1073741824).toFixed(1) + ' GB';
    if (n >= 1024 * 1024) return (n / 1048576).toFixed(1) + ' MB';
    if (n >= 1024) return Math.round(n / 1024) + ' KB';
    return n + ' B';
  }

  let toastTimer = 0;
  function toast(text) {
    const node = document.getElementById('toast');
    node.textContent = text;
    node.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { node.hidden = true; }, 3200);
  }

  function sheet(title, body) {
    document.getElementById('sheetTitle').textContent = title;
    const host = clear(document.getElementById('sheetBody'));
    if (typeof body === 'string') host.innerHTML = body;
    else host.appendChild(body);
    document.getElementById('sheet').hidden = false;
  }

  function closeSheet() {
    document.getElementById('sheet').hidden = true;
  }

  return { state, call, on, fire, pump, el, clear, bytes, toast, sheet, closeSheet };
}());

// ---------------------------------------------------------------------------
// The tab rail
// ---------------------------------------------------------------------------

const TABS = [
  { group: 'Work' },
  { id: 'console', name: 'Console', key: '>' },
  { id: 'editor', name: 'Editor', key: '✎' },
  { id: 'files', name: 'Files', key: '☷' },
  { id: 'run', name: 'Run', key: '▶' },
  { group: 'Build' },
  { id: 'toolchains', name: 'Toolchains', key: '⚙' },
  { id: 'languages', name: 'Languages', key: '℘' },
  { id: 'servers', name: 'Servers', key: '≡' },
  { id: 'pages', name: 'Pages', key: '▦' },
  { group: 'More' },
  { id: 'packages', name: 'Packages', key: '◎' },
  { id: 'plugins', name: 'Plugins', key: '◈' },
  { id: 'android', name: 'Android Lab', key: '▲' },
  { id: 'copies', name: 'Copies', key: '⧉' },
  { id: 'docs', name: 'Guides', key: '?' },
  { id: 'system', name: 'System', key: '⌘' },
];

/*
 * Every plugin with a panel gets a tab, under a heading of its own.
 *
 * They used to live inside the Plugins tab, each behind an Open button that
 * put the panel in a modal sheet. So a plugin you use all day - a database
 * client, a REST console - took two clicks to reach and then covered the
 * app, and closing it lost whatever you had typed in it. Meanwhile the
 * fourteen screens PyCmd ships with are one click away in the rail.
 *
 * A plugin panel is a screen. It goes in the rail with the others, and its
 * id is `panel:<plugin id>` so `go` can tell it from a built-in screen.
 */
function pluginTabs() {
  const installed = ((PyCmd.state.plugins || {}).installed) || [];
  return installed
    .filter((plugin) => plugin.panel && !plugin.broken)
    .map((plugin) => ({
      id: 'panel:' + plugin.id,
      name: plugin.name || plugin.id,
      key: '◈',
      plugin,
    }));
}

function drawTabs() {
  const rail = PyCmd.clear(document.getElementById('tabs'));
  const panels = pluginTabs();
  const entries = panels.length
    ? TABS.concat([{ group: 'Plugins' }], panels)
    : TABS;

  entries.forEach((entry) => {
    if (entry.group) {
      rail.appendChild(PyCmd.el('div', { class: 'rail-head', text: entry.group }));
      return;
    }
    const count = entry.id === 'toolchains'
      ? (PyCmd.state.toolchainSummary.installed || '')
      : entry.id === 'languages'
        ? (PyCmd.state.languageStats.total || '')
        : '';
    rail.appendChild(PyCmd.el('button', {
      class: 'tab' + (PyCmd.state.tab === entry.id ? ' on' : ''),
      title: entry.plugin ? (entry.plugin.description || '').slice(0, 160) : '',
      onclick: () => go(entry.id),
    },
      PyCmd.el('span', { class: 'k', text: entry.key }),
      PyCmd.el('span', { class: 'n', text: entry.name }),
      count ? PyCmd.el('span', { class: 'c', text: String(count) }) : null,
    ));
  });
}

function go(id) {
  PyCmd.state.tab = id;
  drawTabs();
  const screen = document.getElementById('screen');
  screen.classList.remove('flush');
  PyCmd.clear(screen);

  // A plugin panel is a screen like any other; it just is not in the table,
  // because which ones exist depends on what is installed.
  if (String(id).startsWith('panel:')) {
    const wanted = String(id).slice(6);
    const found = pluginTabs().find((entry) => entry.plugin.id === wanted);
    if (!found) {
      screen.appendChild(PyCmd.el('div', { class: 'empty',
        text: 'That plugin is not loaded any more.' }));
      return;
    }
    Promise.resolve(window.drawPanelScreen(screen, found.plugin)).catch((error) => {
      screen.appendChild(PyCmd.el('div', { class: 'empty', text: String(error) }));
    });
    return;
  }

  const draw = window.Screens && window.Screens[id];
  if (!draw) {
    screen.appendChild(PyCmd.el('div', { class: 'empty', text: 'That screen is not in this build.' }));
    return;
  }
  Promise.resolve(draw(screen)).catch((error) => {
    screen.appendChild(PyCmd.el('div', { class: 'empty', text: String(error) }));
  });
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

function setChip(text, kind) {
  const chip = document.getElementById('pyChip');
  chip.textContent = text;
  chip.className = 'chip' + (kind ? ' ' + kind : '');
}

async function refreshShellState() {
  const [languages, chains, plugins] = await Promise.all([
    PyCmd.call('languages'),
    PyCmd.call('toolchains'),
    PyCmd.call('plugins'),
  ]);
  if (languages.ok) {
    PyCmd.state.languages = languages.languages || [];
    PyCmd.state.languageStats = languages.stats || {};
  }
  if (chains.ok) {
    PyCmd.state.toolchains = chains.toolchains || [];
    PyCmd.state.toolchainSummary = chains.summary || {};
  }
  if (plugins.ok) PyCmd.state.plugins = plugins;
  drawTabs();
}

function wireShell() {
  document.getElementById('sheetClose').addEventListener('click', PyCmd.closeSheet);
  document.getElementById('sheet').addEventListener('click', (event) => {
    if (event.target.id === 'sheet') PyCmd.closeSheet();
  });
  document.getElementById('btnStop').addEventListener('click', async () => {
    await PyCmd.call('console.stop');
    PyCmd.toast('Stopped.');
  });
  document.getElementById('btnLog').addEventListener('click', () => go('log'));
  document.getElementById('btnAbout').addEventListener('click', showAbout);

  PyCmd.on('ready', (event) => {
    PyCmd.state.ready = true;
    PyCmd.state.version = event.version || '';
    PyCmd.state.python = event.python || '';
    PyCmd.state.root = event.root || '';
    setChip('Python ' + event.python);
    refreshShellState();
    if (PyCmd.state.tab === 'console') go('console');
  });

  PyCmd.on('boot-failed', (event) => {
    setChip('did not start', 'bad');
    PyCmd.sheet('PyCmd could not start', PyCmd.el('div', {},
      PyCmd.el('p', { text: event.error || 'Something went wrong very early.' }),
      PyCmd.el('p', { class: 'muted', text: 'The debug log has the whole story.' }),
    ));
  });

  PyCmd.on('toast', (event) => PyCmd.toast(event.text));

  PyCmd.on('log', (event) => {
    PyCmd.state.logCount += 1;
    if (event.level === 'error') {
      PyCmd.state.errorCount += 1;
      const badge = document.getElementById('logBadge');
      badge.textContent = String(PyCmd.state.errorCount);
      badge.hidden = false;
    }
  });

  PyCmd.on('toolchains-changed', () => refreshShellState());

  PyCmd.on('update-available', (event) => {
    PyCmd.state.update = event;
    PyCmd.toast('PyCmd ' + event.version + ' is out. System has the details.');
  });
}

function showAbout() {
  const s = PyCmd.state;
  PyCmd.sheet('PyCmd for Windows', PyCmd.el('div', {},
    PyCmd.el('p', {}, 'Version ', PyCmd.el('b', { text: s.version || '…' }),
      ' · Python ', PyCmd.el('b', { text: s.python || '…' })),
    PyCmd.el('p', { class: 'muted' },
      'A programmer’s console that runs code on the machine in front of you. ',
      String(s.languageStats.total || 0), ' file types, ',
      String(s.languageStats.runnable || 0), ' of them runnable, ',
      String(s.toolchainSummary.installed || 0), ' toolchains found here.'),
    PyCmd.el('h2', { text: 'Where your things are' }),
    PyCmd.el('pre', { class: 'out mono', text: s.root || '' }),
    PyCmd.el('p', { class: 'muted' },
      'Nothing is written to Program Files and nothing needs administrator rights.'),
  ));
}

window.addEventListener('DOMContentLoaded', () => {
  wireShell();
  // The console listens for engine output and the editor for its shortcuts.
  // Both are wired once here rather than per draw: a screen that re-registers
  // its listeners every time it is opened ends up writing every line twice.
  conWireEvents();
  edShortcuts();
  drawTabs();
  go('console');
  PyCmd.pump();
  // The window may have opened after Python was already up, in which case the
  // ready event has been and gone. Ask once rather than waiting for one.
  PyCmd.call('hello').then((reply) => {
    if (reply.ok && reply.ready) PyCmd.fire({ kind: 'ready', ...reply });
  });
});
