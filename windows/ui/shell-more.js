/*
  The parts of the shell 4.0 added: themes, zoom, the command palette,
  keyboard shortcuts and the what's-new sheet.

  Themes reach into the console and editor frames too. Those pages are the
  phone's own, with their own colour variables (--bg, --fg, --dim...), so a
  theme sets those as well as the shell's. Before this the shell could be
  green while the console beside it stayed blue.
*/
'use strict';

const Look = { theme: 'classic-green', themes: {}, custom: null, zoom: 1, fontSize: 14, compact: false };

const VAR_MAP = {
  bg: '--bg', sunken: '--sunken', surface: '--surface', raised: '--raised', line: '--line',
  lineSoft: '--line-soft', text: '--text', bright: '--bright', dim: '--dim', faint: '--faint',
  accent: '--accent', accentBg: '--accent-bg', accentLine: '--accent-line',
};

function lookPalette() {
  if (Look.theme === 'custom' && Look.custom) {
    return Object.assign({}, Look.themes['classic-green'] || {}, Look.custom);
  }
  return Look.themes[Look.theme] || Look.themes['classic-green'] || {};
}

function hexAlpha(hex, alpha) {
  const n = parseInt(String(hex || '#000000').slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

function lookApply() {
  const p = lookPalette();
  const root = document.documentElement;
  Object.entries(VAR_MAP).forEach(([key, name]) => { if (p[key]) root.style.setProperty(name, p[key]); });
  root.style.colorScheme = p.light ? 'light' : 'dark';
  document.body.classList.toggle('light', !!p.light);
  document.body.classList.toggle('compact', !!Look.compact);
  document.body.style.zoom = String(Look.zoom || 1);
  root.style.setProperty('--base-font', (Look.fontSize || 14) + 'px');
  document.querySelectorAll('iframe').forEach(lookFrame);
}

/** Pushes the theme into a frame's own variables. Same origin, so allowed. */
function lookFrame(frame) {
  let doc;
  try { doc = frame.contentDocument; } catch (error) { return; }
  if (!doc || !doc.documentElement) return;
  const p = lookPalette();
  const set = (name, value) => doc.documentElement.style.setProperty(name, value);
  set('--bg', p.sunken || p.bg);
  set('--fg', p.text);
  set('--dim', p.dim);
  set('--system', p.accent);
  set('--input', p.accent);
  set('--caret', p.accent);
  set('--selection', hexAlpha(p.accent, 0.3));
  set('--gutter-bg', p.surface);
  set('--gutter-fg', p.faint);
  set('--gutter-active', p.text);
  // The plugin panels' own names - the same ones the phone sets (Theme.kt).
  // Without these a panel kept the default palette under whatever theme was
  // picked: the "old, ugly" look, half one theme and half another.
  set('--surface', p.surface);
  set('--surface-high', p.raised || p.surface);
  set('--outline', p.line);
  set('--muted', p.dim);
  set('--accent', p.accent);
  set('--accent-dim', p.accentBg || hexAlpha(p.accent, 0.3));
  set('--accent-soft', hexAlpha(p.accent, 0.14));
  set('--on-accent', p.light ? '#FFFFFF' : (p.bg || '#000000'));
  set('--info', p.accent);
  set('--warning', '#E5A945');
  set('--danger', '#E8635F');
  set('--radius', '12px');
  doc.documentElement.setAttribute('data-pycmd-dark', p.light ? 'false' : 'true');
  if (p.light) {
    [['--kw', '#7A3E9D'], ['--str', '#1E7A4C'], ['--num', '#A0522D'], ['--comment', '#8E958F'],
     ['--def', '#1F5FAF'], ['--builtin', '#9A6700'], ['--decorator', '#B03A2E'], ['--self', '#6B4FA0'],
     ['--ansi-7', '#2B2F2C'], ['--ansi-15', '#111412'], ['--stderr', '#B3261E']]
      .forEach(([k, v]) => set(k, v));
  } else {
    ['--kw', '--str', '--num', '--comment', '--def', '--builtin', '--decorator', '--self',
     '--ansi-7', '--ansi-15', '--stderr'].forEach((k) => doc.documentElement.style.removeProperty(k));
  }
}

async function lookLoad() {
  const reply = await PyCmd.call('look', {});
  if (!reply.ok) return;
  Object.assign(Look, reply);
  lookApply();
}

async function lookSet(changes) {
  const reply = await PyCmd.call('look.set', changes);
  if (reply.ok) { Object.assign(Look, reply); lookApply(); }
  return reply;
}

function lookZoom(step) {
  const next = step === 0 ? 1 : Math.round(Math.max(0.6, Math.min(2, (Look.zoom || 1) + step)) * 10) / 10;
  lookSet({ zoom: next });
  PyCmd.toast('Zoom ' + Math.round(next * 100) + '%');
}

// Frames that appear later get the theme as soon as they load.
new MutationObserver((changes) => {
  changes.forEach((change) => change.addedNodes.forEach((node) => {
    const frames = node.tagName === 'IFRAME' ? [node] : (node.querySelectorAll ? [...node.querySelectorAll('iframe')] : []);
    frames.forEach((frame) => {
      frame.addEventListener('load', () => lookFrame(frame));
      lookFrame(frame);
    });
  }));
}).observe(document.documentElement, { childList: true, subtree: true });

// ---------------------------------------------------------------------------
// The command palette
// ---------------------------------------------------------------------------

const Palette = { open: false, items: [], shown: [], index: 0 };

function paletteActions() {
  const actions = [
    ['New file', () => { go('editor'); setTimeout(() => window.edNew && edNew(), 50); }],
    ['New project from a template…', () => newProjectSheet()],
    ['Open a file…', () => { go('editor'); setTimeout(() => window.edOpen && edOpen(), 50); }],
    ['Search in files', () => go('search')],
    ['Continue learning', () => go('learn')],
    ['Review missed lessons', () => { go('learn'); setTimeout(() => window.learnReview && learnReview(), 100); }],
    ['Start the Android device', () => { go('android'); setTimeout(() => window.labStart && labStart({}), 300); }],
    ['Theme: next', () => themeCycle()],
    ['Zoom in', () => lookZoom(0.1)],
    ['Zoom out', () => lookZoom(-0.1)],
    ['Reset zoom', () => lookZoom(0)],
    ['Keyboard shortcuts', () => shortcutsSheet()],
    ["What's new in 4.0", () => whatsNewSheet(true)],
    ['Export diagnostics', () => exportDiagnostics()],
    ['Look for toolchains again', async () => {
      await PyCmd.call('toolchains', { refresh: true }); refreshShellState(); PyCmd.toast('Looked again.'); }],
    ['Stop whatever is running', async () => { await PyCmd.call('console.stop'); PyCmd.toast('Stopped.'); }],
  ];
  return actions.map(([name, run]) => ({ kind: 'action', name, run }));
}

async function paletteOpen() {
  if (Palette.open) return;
  Palette.open = true;
  const tabs = TABS.filter((t) => t.id).concat(pluginTabs())
    .map((t) => ({ kind: 'go', name: t.name, hint: 'screen', run: () => go(t.id) }));
  Palette.items = tabs.concat(paletteActions());

  const overlay = el('div', { class: 'palette', id: 'palette', onclick: (e) => { if (e.target.id === 'palette') paletteClose(); } });
  const input = el('input', { class: 'palette-input', placeholder: 'Go to a screen, run an action, open a recent file or a lesson…' });
  const list = el('div', { class: 'palette-list' });
  overlay.appendChild(el('div', { class: 'palette-card' }, input, list,
    el('div', { class: 'muted small-text palette-foot', text: '↑↓ to choose · Enter to go · Esc to close' })));
  document.body.appendChild(overlay);
  input.focus();

  const draw = () => {
    const q = input.value.trim().toLowerCase();
    Palette.shown = Palette.items
      .map((item) => ({ item, score: paletteScore(item.name.toLowerCase(), q) }))
      .filter((r) => r.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 40)
      .map((r) => r.item);
    Palette.index = Math.min(Palette.index, Math.max(0, Palette.shown.length - 1));
    PyCmd.clear(list);
    Palette.shown.forEach((item, i) => list.appendChild(el('button', {
      class: 'palette-row' + (i === Palette.index ? ' on' : ''),
      onclick: () => paletteRun(item),
    }, el('span', { class: 'grow', text: item.name }), el('span', { class: 'muted small-text', text: item.hint || item.kind }))));
    if (!Palette.shown.length) list.appendChild(el('div', { class: 'muted palette-row', text: 'Nothing matches.' }));
    const on = list.querySelector('.on');
    if (on) on.scrollIntoView({ block: 'nearest' });
  };
  input.addEventListener('input', () => { Palette.index = 0; draw(); });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { paletteClose(); }
    else if (event.key === 'ArrowDown') { Palette.index = Math.min(Palette.shown.length - 1, Palette.index + 1); draw(); event.preventDefault(); }
    else if (event.key === 'ArrowUp') { Palette.index = Math.max(0, Palette.index - 1); draw(); event.preventDefault(); }
    else if (event.key === 'Enter') { const item = Palette.shown[Palette.index]; if (item) paletteRun(item); }
  });
  draw();

  // Recent files and courses arrive a moment later, without holding the palette up.
  const [recent, catalogue] = await Promise.all([PyCmd.call('recent', {}), PyCmd.call('learn', {})]);
  (recent.recent || []).forEach((r) => Palette.items.push({
    kind: 'file', name: r.path.split(/[\\/]/).pop(), hint: r.path, run: () => openInEditor(r.path, r.onDisk) }));
  ((catalogue || {}).courses || []).forEach((c) => Palette.items.push({
    kind: 'course', name: 'Learn ' + c.name, hint: `${c.done}/${c.lessons} lessons`,
    run: () => { learn.view = 'course'; learn.course = c.id; go('learn'); } }));
  if (Palette.open) draw();
}

function paletteScore(name, q) {
  if (!q) return 1;
  if (name.startsWith(q)) return 100;
  if (name.includes(q)) return 50 - name.indexOf(q);
  let at = 0;
  for (const ch of q) {
    at = name.indexOf(ch, at);
    if (at < 0) return 0;
    at += 1;
  }
  return 5;
}

function paletteRun(item) {
  paletteClose();
  try { item.run(); } catch (error) { PyCmd.toast(String(error)); }
}

function paletteClose() {
  Palette.open = false;
  const node = document.getElementById('palette');
  if (node) node.remove();
}

// ---------------------------------------------------------------------------
// Shortcuts, themes, what's new
// ---------------------------------------------------------------------------

const SHORTCUTS = [
  ['Ctrl+K or Ctrl+Shift+P', 'Command palette'],
  ['Ctrl+1 … Ctrl+9', 'The first nine screens in the rail'],
  ['Ctrl+Shift+F', 'Search in files'],
  ['Ctrl+Shift+L', 'PyCmd Learn'],
  ['Ctrl+Shift+N', 'New project from a template'],
  ['Ctrl+Shift+T', 'Next theme'],
  ['Ctrl+= / Ctrl+- / Ctrl+0', 'Zoom in, out, back to 100%'],
  ['Ctrl+S, Ctrl+O, Ctrl+F, Ctrl+G', 'Save, open, find, go to line - in the editor'],
  ['F5', 'Run the file in the editor'],
  ['1-9, Enter, Esc', 'Answer, move on and go back - in a lesson'],
  ['F1', 'This list'],
];

function shortcutsSheet() {
  const list = el('div', { class: 'list' });
  SHORTCUTS.forEach(([keys, what]) => list.appendChild(el('div', { class: 'row-item' },
    el('code', { class: 'kbd', text: keys }), el('span', { class: 'grow', text: what }))));
  PyCmd.sheet('Keyboard shortcuts', list);
}

function themeCycle() {
  const ids = Object.keys(Look.themes);
  const next = ids[(ids.indexOf(Look.theme) + 1) % ids.length];
  lookSet({ theme: next });
  PyCmd.toast('Theme: ' + (Look.themes[next] || {}).name);
}

async function whatsNewSheet(force) {
  const reply = await PyCmd.call('whatsnew', {});
  if (!reply.ok || (!reply.show && !force)) return;
  const list = el('div', { class: 'list' });
  (reply.items || []).forEach(([title, text]) => list.appendChild(el('div', { class: 'row-item new-item' },
    el('div', { class: 'grow' }, el('b', { text: title }), el('div', { class: 'muted small-text', text })))));
  PyCmd.sheet(reply.title, el('div', {}, list,
    el('div', { class: 'row', style: 'margin-top:12px' },
      el('button', { class: 'small primary', text: 'Open PyCmd Learn', onclick: () => { PyCmd.closeSheet(); go('learn'); } }),
      el('button', { class: 'small', text: 'Close', onclick: PyCmd.closeSheet }))));
  PyCmd.call('whatsnew.seen', {});
}

async function exportDiagnostics() {
  PyCmd.toast('Collecting…');
  const reply = await PyCmd.call('diagnostics', {});
  if (!reply.ok) { PyCmd.toast(reply.error || 'It could not be written.'); return; }
  PyCmd.sheet('Diagnostics saved', el('div', {},
    el('p', { text: 'Everything a bug report needs: versions, toolchains, the Android Lab state, '
      + 'the debug log. None of your files are in it.' }),
    el('pre', { class: 'out mono', text: reply.zip }),
    el('button', { class: 'small', text: 'Show it in Explorer', onclick: () => diskReveal(reply.zip) })));
}

document.addEventListener('keydown', (event) => {
  const ctrl = event.ctrlKey || event.metaKey;
  if (ctrl && !event.shiftKey && event.key.toLowerCase() === 'k') { event.preventDefault(); paletteOpen(); return; }
  if (ctrl && event.shiftKey && event.key.toLowerCase() === 'p') { event.preventDefault(); paletteOpen(); return; }
  if (event.key === 'F1') { event.preventDefault(); shortcutsSheet(); return; }
  if (!ctrl) return;
  if (event.shiftKey && event.key.toLowerCase() === 'f') { event.preventDefault(); go('search'); return; }
  if (event.shiftKey && event.key.toLowerCase() === 'l') { event.preventDefault(); go('learn'); return; }
  if (event.shiftKey && event.key.toLowerCase() === 'n') { event.preventDefault(); newProjectSheet(); return; }
  if (event.shiftKey && event.key.toLowerCase() === 't') { event.preventDefault(); themeCycle(); return; }
  if (event.key === '=' || event.key === '+') { event.preventDefault(); lookZoom(0.1); return; }
  if (event.key === '-') { event.preventDefault(); lookZoom(-0.1); return; }
  if (event.key === '0') { event.preventDefault(); lookZoom(0); return; }
  if (/^[1-9]$/.test(event.key) && !event.shiftKey && !event.altKey) {
    const screens = TABS.filter((t) => t.id);
    const target = screens[Number(event.key) - 1];
    if (target) { event.preventDefault(); go(target.id); }
  }
});

window.addEventListener('DOMContentLoaded', () => {
  lookLoad();
  PyCmd.on('ready', () => { lookLoad(); setTimeout(() => whatsNewSheet(false), 600); });
});
