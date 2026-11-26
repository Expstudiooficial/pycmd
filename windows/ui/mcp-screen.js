/*
  The MCP tab, and the hands AI agents drive the window with.

  The tab: a switch for the server, the address and token, read-only mode,
  copy-paste set-up for each AI app, and the last calls. The hands: the
  host emits 'mcp-ui' for every ui_* tool, and this answers with mcp.ui.result.
*/
'use strict';

async function Mcp(screen) {
  const s = await PyCmd.call('mcp', {});
  screen.appendChild(head('MCP · AI agents',
    `Let an AI app - Claude Code, Claude Desktop, Antigravity, Cursor, VS Code, Gemini, Codex `
    + `- use PyCmd: ${s.tools || 'over 160'} tools, from files, the console and toolchains to `
    + 'Learn, plugins, Android Lab and the window itself (read it, click, type, screenshot).'));

  const set = async (changes) => { const r = await PyCmd.call('mcp.set', changes); if (r.error) PyCmd.toast(r.error); go('mcp'); };
  const toggle = el('div', { class: 'switch' + (s.on ? ' on' : ''), onclick: () => set({ on: !s.on }) });
  const ro = el('div', { class: 'switch' + (s.readOnly ? ' on' : ''), onclick: () => set({ readOnly: !s.readOnly }) });
  const port = el('input', { type: 'number', value: String(s.port), style: 'width:110px' });
  screen.appendChild(card(
    el('div', { class: 'row spread' },
      el('div', {}, el('b', { text: s.running ? 'The MCP server is on' : 'The MCP server is off' }),
        el('div', { class: s.error ? 'muted bad-text' : 'muted',
          text: s.error || (s.running ? s.url : 'Switch it on, then paste the set-up for your AI app below.') })),
      toggle),
    el('div', { class: 'row wrap', style: 'margin-top:12px' },
      el('span', { class: 'muted', text: 'Read-only' }), ro,
      el('span', { class: 'muted small-text', text: 'agents can look but not change anything' }),
      el('span', { class: 'grow' }),
      el('span', { class: 'muted', text: 'Port' }), port,
      el('button', { class: 'small', text: 'Use port', onclick: () => set({ port: Number(port.value) }) })),
    el('div', { class: 'row wrap', style: 'margin-top:10px' },
      el('span', { class: 'muted', text: 'Token' }),
      el('code', { class: 'kbd', text: s.token.slice(0, 10) + '…' }),
      el('button', { class: 'small', text: 'Copy token', onclick: () => copyText(s.token) }),
      el('button', { class: 'small danger', text: 'New token', title: 'Disconnects every app that has the old one',
        onclick: () => set({ newToken: true }) })),
    el('p', { class: 'muted small-text', text: 'Only this PC can connect (127.0.0.1), and only with the '
      + 'token. Anything an agent does, you can watch here and in the Debug log.' })));

  screen.appendChild(el('h2', { text: 'Set it up in your AI app' }));
  const grid = el('div', { class: 'grid two' });
  (s.setups || []).forEach((row) => grid.appendChild(card(
    el('div', { class: 'row spread' }, el('b', { text: row.app }),
      el('button', { class: 'small primary', text: 'Copy', onclick: () => copyText(row.text) })),
    el('div', { class: 'muted small-text', text: row.where }),
    el('pre', { class: 'out mono wrap-code', text: row.text }))));
  screen.appendChild(grid);

  screen.appendChild(el('h2', { text: 'Last calls' }));
  const list = el('div', { class: 'list' });
  (s.calls || []).forEach((c) => list.appendChild(el('div', { class: 'row-item mono' },
    el('span', { class: c.ok ? 'tag good' : 'tag warn', text: c.ok ? 'ok' : 'error' }),
    el('span', { class: 'grow', text: c.tool }),
    el('span', { class: 'muted', text: `${c.ms} ms · ${new Date(c.at * 1000).toLocaleTimeString()}` }))));
  if (!(s.calls || []).length) list.appendChild(el('div', { class: 'empty', text: 'No calls yet.' }));
  screen.appendChild(list);
}

function copyText(text) {
  navigator.clipboard.writeText(text).then(() => PyCmd.toast('Copied.'), () => PyCmd.toast('Copy did not work - select it instead.'));
}

// ---------------------------------------------------------------------------
// The hands
// ---------------------------------------------------------------------------

let mcpControls = [];

function mcpVisible(node) {
  const r = node.getBoundingClientRect();
  return r.width > 0 && r.height > 0 && getComputedStyle(node).visibility !== 'hidden';
}

function mcpLabel(node) {
  return (node.getAttribute('aria-label') || node.innerText || node.value || node.placeholder
    || node.title || node.getAttribute('name') || '').trim().replace(/\s+/g, ' ').slice(0, 80);
}

function mcpRead() {
  const sheet = document.getElementById('sheet');
  const open = sheet && !sheet.hidden;
  const root = open ? sheet : document.getElementById('screen');
  const selector = 'button, a, input, textarea, select, .switch, .tab, .course-card, .lchip, .opt, .row-item, [onclick], [role=button]';
  mcpControls = [...root.querySelectorAll(selector), ...(open ? [] : document.querySelectorAll('#tabs .tab'))]
    .filter((n, i, all) => mcpVisible(n) && all.indexOf(n) === i);
  return {
    ok: true, tab: PyCmd.state.tab, dialog: open ? document.getElementById('sheetTitle').textContent : '',
    text: (root.innerText || '').replace(/\n{3,}/g, '\n\n').slice(0, 12000),
    controls: mcpControls.map((n, i) => ({ i, kind: n.tagName === 'INPUT' || n.tagName === 'TEXTAREA' ? 'field'
      : n.classList.contains('switch') ? 'switch' : n.classList.contains('tab') ? 'tab' : 'button',
    label: mcpLabel(n), value: n.value !== undefined && n.tagName !== 'BUTTON' ? String(n.value).slice(0, 200) : undefined,
    on: n.classList.contains('switch') ? n.classList.contains('on') : undefined })),
  };
}

function mcpFind(args) {
  if (!mcpControls.length) mcpRead();
  if (args.index !== undefined && mcpControls[args.index]) return mcpControls[args.index];
  const want = String(args.text || args.label || '').toLowerCase();
  if (!want) return null;
  mcpRead();
  return mcpControls.find((n) => mcpLabel(n).toLowerCase() === want)
    || mcpControls.find((n) => mcpLabel(n).toLowerCase().includes(want)) || null;
}

const MCP_ACTIONS = {
  tabs: () => ({ ok: true, open: PyCmd.state.tab,
    tabs: TABS.filter((t) => t.id).map((t) => ({ id: t.id, name: t.name }))
      .concat(pluginTabs().map((t) => ({ id: t.id, name: t.name }))) }),
  navigate: async (a) => { go(String(a.tab || '')); await mcpSettle(); return mcpRead(); },
  read: () => mcpRead(),
  click: async (a) => {
    const node = mcpFind(a);
    if (!node) return { ok: false, error: 'nothing like that on screen - ui_read lists what is there' };
    node.scrollIntoView({ block: 'center' }); node.click(); await mcpSettle(); return mcpRead();
  },
  type: async (a) => {
    const node = mcpFind(a);
    if (!node || !('value' in node)) return { ok: false, error: 'no such field - ui_read lists the fields' };
    node.focus(); node.value = String(a.value ?? '');
    node.dispatchEvent(new Event('input', { bubbles: true })); node.dispatchEvent(new Event('change', { bubbles: true }));
    if (a.submit) {
      node.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      if (node.form) node.form.requestSubmit();
    }
    await mcpWait(500); return mcpRead();
  },
  scroll: (a) => {
    const sheet = document.getElementById('sheet');
    const box = sheet && !sheet.hidden ? document.getElementById('sheetBody') : document.getElementById('screen');
    const to = String(a.to || 'down');
    if (to === 'top') box.scrollTop = 0; else if (to === 'bottom') box.scrollTop = box.scrollHeight;
    else box.scrollTop += to === 'up' ? -box.clientHeight * 0.8 : to === 'down' ? box.clientHeight * 0.8 : Number(to) || 0;
    return { ok: true, scrollTop: Math.round(box.scrollTop), scrollHeight: box.scrollHeight };
  },
  key: (a) => {
    const parts = String(a.key || '').split('+'); const key = parts.pop();
    const init = { key, bubbles: true, ctrlKey: parts.includes('Ctrl'), shiftKey: parts.includes('Shift'), altKey: parts.includes('Alt') };
    (document.activeElement || document.body).dispatchEvent(new KeyboardEvent('keydown', init));
    return { ok: true };
  },
  close_dialog: () => { PyCmd.closeSheet(); return mcpRead(); },
  toast: (a) => { PyCmd.toast(String(a.text || '')); return { ok: true }; },
  theme: async (a) => { await lookSet({ theme: String(a.theme || '') }); return { ok: true, theme: Look.theme }; },
};

function mcpWait(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

/** Waits until the screen stops changing (screens load asynchronously), up to ~5s. */
async function mcpSettle() {
  let last = -1;
  for (let i = 0; i < 25; i += 1) {
    await mcpWait(200);
    const size = (document.getElementById('screen').innerText || '').length;
    if (size > 0 && size === last) return;
    last = size;
  }
}

PyCmd.on('mcp-ui', async (event) => {
  let result;
  try {
    const action = MCP_ACTIONS[event.action];
    result = action ? await action(event.args || {}) : { ok: false, error: 'unknown action ' + event.action };
  } catch (error) {
    result = { ok: false, error: String(error) };
  }
  PyCmd.call('mcp.ui.result', { id: event.id, result });
});

Object.assign(window.Screens, { mcp: Mcp });
