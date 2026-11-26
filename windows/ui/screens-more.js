/*
  The screens 4.0 added: Search, Git, Tasks, Tools, Ports, Snippets, Notes and
  Settings, and the new-project sheet. Each is a function handed the empty
  middle of the window, like every other screen.
*/
'use strict';

function folderPicker(value, onChange, label) {
  const input = el('input', { value: value || '', placeholder: 'Workspace (leave empty) or C:\\path\\to\\folder' });
  input.addEventListener('change', () => onChange(input.value.trim()));
  return el('label', { class: 'field' }, el('span', { text: label || 'Folder' }),
    el('div', { class: 'row' }, input,
      el('button', { class: 'small', text: 'Browse…', onclick: async () => {
        const got = await PyCmd.call('pick.file', { folder: true });
        if (got.ok && got.path) { input.value = got.path; onChange(got.path); }
        else if (got.error) PyCmd.toast(got.error);
      } })));
}

function remembered(key, fallback) {
  try { return localStorage.getItem('pycmd.' + key) || fallback; } catch (e) { return fallback; }
}

function remember(key, value) {
  try { localStorage.setItem('pycmd.' + key, value); } catch (e) { /* private mode */ }
}

// ---------------------------------------------------------------------------
// Search in files
// ---------------------------------------------------------------------------

async function Search(screen) {
  screen.appendChild(head('Search', 'Find text in every file under a folder. Plain text or a regular expression.'));
  let folder = remembered('search.folder', '');
  const text = el('input', { placeholder: 'What to look for', value: remembered('search.text', '') });
  const only = el('input', { placeholder: 'Only these files, e.g. *.py, *.js', value: remembered('search.only', '') });
  const regex = el('input', { type: 'checkbox' });
  const matchCase = el('input', { type: 'checkbox' });
  const replace = el('input', { placeholder: 'Replace with (optional)' });
  const results = el('div', {});
  const status = el('p', { class: 'muted' });

  const run = async () => {
    remember('search.text', text.value); remember('search.only', only.value); remember('search.folder', folder);
    if (!text.value) return;
    status.textContent = 'Looking…';
    PyCmd.clear(results);
    const reply = await PyCmd.call('search', { folder, text: text.value, only: only.value,
      regex: regex.checked, matchCase: matchCase.checked });
    if (!reply.ok) { status.textContent = reply.error; return; }
    status.textContent = `${reply.hits.length}${reply.truncated ? '+' : ''} matches in ${reply.files} files `
      + `· ${reply.scanned} files read · ${reply.seconds}s`;
    const byFile = {};
    reply.hits.forEach((h) => (byFile[h.path] = byFile[h.path] || []).push(h));
    Object.entries(byFile).forEach(([path, hits]) => {
      const list = el('div', { class: 'list' });
      hits.forEach((h) => list.appendChild(el('button', { class: 'row-item mono', onclick: () => searchOpen(h) },
        el('span', { class: 'muted', text: String(h.line).padStart(5) }),
        el('span', { class: 'grow', text: h.text }))));
      const replaceHere = replace.value ? el('button', { class: 'small', text: 'Replace in this file', onclick: async () => {
        if (!confirm(`Replace every match in ${path}?`)) return;
        const done = await PyCmd.call('search.replace', { path, text: text.value, with: replace.value,
          regex: regex.checked, matchCase: matchCase.checked });
        PyCmd.toast(done.ok ? `Replaced ${done.replaced}.` : done.error);
        run();
      } }) : null;
      results.appendChild(card(el('div', { class: 'row spread' }, el('b', { class: 'ellipsis', text: path }), replaceHere), list));
    });
  };
  text.addEventListener('keydown', (e) => { if (e.key === 'Enter') run(); });

  screen.appendChild(card(
    el('div', { class: 'row' }, text, el('button', { class: 'small primary', text: 'Search', onclick: run })),
    el('div', { class: 'row wrap' }, only,
      el('label', { class: 'row' }, regex, 'Regular expression'),
      el('label', { class: 'row' }, matchCase, 'Match case')),
    replace,
    folderPicker(folder, (v) => { folder = v; }, 'Where')));
  screen.appendChild(status);
  screen.appendChild(results);
  setTimeout(() => text.focus(), 30);
  if (text.value) run();
}

async function searchOpen(hit) {
  const opened = await edOpenPath(hit.path, true);
  if (!opened) return;
  go('editor');
  setTimeout(() => { try { edCall('goToLine', hit.line); } catch (e) { /* older editor */ } }, 300);
}

// ---------------------------------------------------------------------------
// Git
// ---------------------------------------------------------------------------

async function Git(screen) {
  let folder = remembered('git.folder', '');
  screen.appendChild(head('Git', 'Status, staging, commits, branches and the history of a repository.'));
  const top = card(folderPicker(folder, (v) => { folder = v; remember('git.folder', v); go('git'); }, 'Repository'));
  screen.appendChild(top);
  const reply = await PyCmd.call('git', { folder });
  const doGit = async (action, extra) => {
    const r = await PyCmd.call('git.do', Object.assign({ folder, action }, extra || {}));
    if (!r.ok) PyCmd.sheet('git ' + action, el('pre', { class: 'out mono', text: r.error || r.output || 'it did not work' }));
    else if (r.output && ['pull', 'push', 'fetch', 'clone'].includes(action)) PyCmd.toast(r.output.split('\n').slice(-1)[0] || 'Done.');
    go('git');
    return r;
  };

  if (!reply.installed) {
    screen.appendChild(card(el('p', { text: 'Git is not installed.' }),
      el('button', { class: 'small primary', text: 'Install Git for Windows', onclick: async () => {
        go('console'); await PyCmd.call('install.one', { toolchain: 'bash' }); } })));
    return;
  }
  if (!reply.repo) {
    const url = el('input', { placeholder: 'https://github.com/owner/repo.git' });
    screen.appendChild(card(el('p', { text: `${reply.folder} is not a git repository.` }),
      el('div', { class: 'row wrap' },
        el('button', { class: 'small primary', text: 'Make it one (git init)', onclick: () => doGit('init') })),
      el('h2', { text: 'Or clone one into it' }),
      el('div', { class: 'row' }, url, el('button', { class: 'small', text: 'Clone', onclick: () => doGit('clone', { url: url.value }) }))));
    return;
  }

  const branch = el('select', {});
  // A repository with no commits has a current branch but `git branch` lists
  // nothing yet, so the current one is offered on its own.
  const names = reply.branches.length ? reply.branches : [reply.branch || 'main'];
  names.forEach((b) => branch.appendChild(el('option', { value: b, text: b, selected: b === reply.branch })));
  branch.addEventListener('change', () => doGit('checkout', { branch: branch.value }));
  screen.appendChild(card(
    el('div', { class: 'row wrap spread' },
      el('div', { class: 'row' }, el('b', { text: 'On' }), branch,
        reply.ahead ? el('span', { class: 'tag', text: `${reply.ahead} to push` }) : null,
        reply.behind ? el('span', { class: 'tag warn', text: `${reply.behind} to pull` }) : null),
      el('div', { class: 'row' },
        el('button', { class: 'small', text: 'Fetch', onclick: () => doGit('fetch') }),
        el('button', { class: 'small', text: 'Pull', onclick: () => doGit('pull') }),
        el('button', { class: 'small', text: 'Push', onclick: () => doGit('push') }),
        el('button', { class: 'small', text: 'New branch', onclick: () => {
          const name = prompt('Name of the new branch');
          if (name) doGit('checkout', { branch: name, create: true });
        } }))),
    reply.remote ? el('div', { class: 'muted small-text mono', text: reply.remote }) : null));

  const message = el('textarea', { class: 'plain', rows: '2', placeholder: 'What this commit does' });
  const changes = el('div', { class: 'list' });
  reply.changes.forEach((c) => {
    const staged = c.index !== ' ' && c.index !== '?';
    changes.appendChild(el('div', { class: 'row-item' },
      el('span', { class: 'mono tag' + (staged ? ' good' : ''), text: (c.index + c.tree).replace(/ /g, '·') }),
      el('button', { class: 'grow ghost mono', text: c.path, onclick: async () => {
        const d = await PyCmd.call('git.do', { folder, action: 'diff', path: c.path, staged });
        PyCmd.sheet(c.path, el('pre', { class: 'out mono diff', html: diffHtml(d.diff || '(no difference to show)') }));
      } }),
      staged ? el('button', { class: 'small', text: 'Unstage', onclick: () => doGit('unstage', { path: c.path }) })
        : el('button', { class: 'small', text: 'Stage', onclick: () => doGit('stage', { path: c.path }) }),
      c.index !== '?' && !staged ? el('button', { class: 'small danger', text: 'Discard', onclick: () => {
        if (confirm(`Throw away your changes to ${c.path}?`)) doGit('discard', { path: c.path }); } }) : null));
  });
  if (!reply.changes.length) changes.appendChild(el('div', { class: 'row-item muted', text: 'Nothing changed. Clean.' }));
  screen.appendChild(card(el('h2', { text: `Changes (${reply.changes.length})` }), changes,
    el('div', { class: 'row wrap', style: 'margin-top:10px' },
      el('button', { class: 'small', text: 'Stage everything', onclick: () => doGit('stage') }),
      message,
      el('button', { class: 'small primary', text: 'Commit', onclick: () => doGit('commit', { message: message.value }) }),
      el('button', { class: 'small', text: 'Commit everything', onclick: () => doGit('commit', { message: message.value, all: true }) }))));

  const log = el('div', { class: 'list' });
  reply.commits.forEach((c) => log.appendChild(el('button', { class: 'row-item', onclick: async () => {
    const d = await PyCmd.call('git.do', { folder, action: 'show', hash: c.hash });
    PyCmd.sheet(c.subject, el('pre', { class: 'out mono diff', html: diffHtml(d.diff || '') }));
  } }, el('code', { class: 'mono', text: c.hash }), el('span', { class: 'grow', text: c.subject }),
    el('span', { class: 'muted small-text', text: `${c.author} · ${c.when}` }))));
  if (!reply.commits.length) log.appendChild(el('div', { class: 'row-item muted', text: 'No commits yet.' }));
  screen.appendChild(card(el('h2', { text: 'History' }), log));
}

function diffHtml(text) {
  const safe = String(text).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  return safe.split('\n').map((line) => {
    if (line.startsWith('+') && !line.startsWith('+++')) return `<span class="add">${line}</span>`;
    if (line.startsWith('-') && !line.startsWith('---')) return `<span class="del">${line}</span>`;
    if (line.startsWith('@@')) return `<span class="hunk">${line}</span>`;
    return line;
  }).join('\n');
}

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

async function Tasks(screen) {
  let folder = remembered('tasks.folder', '');
  screen.appendChild(head('Tasks', 'The scripts a project already declares - npm scripts, Makefile targets, '
    + 'cargo, go, dotnet, gradle - one click each. Output goes to the console.'));
  screen.appendChild(card(folderPicker(folder, (v) => { folder = v; remember('tasks.folder', v); go('tasks'); }, 'Project')));
  const reply = await PyCmd.call('tasks', { folder });
  if (!reply.ok) { screen.appendChild(el('div', { class: 'empty', text: reply.error })); return; }
  if (!reply.tasks.length) {
    screen.appendChild(el('div', { class: 'empty', text: 'No package.json, Makefile, Cargo.toml, go.mod, '
      + 'project file or requirements.txt here. A template from New project has one.' }));
    screen.appendChild(el('button', { class: 'small primary', text: 'New project…', onclick: newProjectSheet }));
    return;
  }
  const groups = {};
  reply.tasks.forEach((t) => (groups[t.source] = groups[t.source] || []).push(t));
  Object.entries(groups).forEach(([source, rows]) => {
    const list = el('div', { class: 'list' });
    rows.forEach((t) => list.appendChild(el('div', { class: 'row-item' },
      el('b', { text: t.name }), el('code', { class: 'grow muted mono ellipsis', text: t.detail }),
      t.available ? null : el('span', { class: 'tag warn', text: `${t.argv[0]} not installed` }),
      el('button', { class: 'small primary', text: '▶ Run', onclick: async () => {
        go('console');
        await PyCmd.call('task.run', { folder: reply.folder, argv: t.argv });
      } }))));
    screen.appendChild(card(el('h2', { text: source }), list));
  });
}

// ---------------------------------------------------------------------------
// Tools: the small jobs
// ---------------------------------------------------------------------------

const TOOLS = [
  ['json', 'JSON: format and check'],
  ['base64', 'Base64'],
  ['url', 'URL encode and decode'],
  ['hash', 'Hashes: MD5, SHA-1, SHA-256, SHA-512'],
  ['uuid', 'UUIDs'],
  ['time', 'Timestamps'],
  ['regex', 'Regular expression tester'],
  ['diff', 'Compare two texts'],
  ['case', 'Change case and count'],
  ['color', 'Colours'],
];

async function Tools(screen) {
  const which = remembered('tools.which', 'json');
  screen.appendChild(head('Tools', 'The small jobs that otherwise mean pasting into a website.'));
  const tabs = el('div', { class: 'row wrap' });
  TOOLS.forEach(([id, name]) => tabs.appendChild(el('button', { class: 'small' + (id === which ? ' primary' : ''),
    text: name, onclick: () => { remember('tools.which', id); go('tools'); } })));
  screen.appendChild(tabs);
  const body = el('div', { class: 'card' });
  screen.appendChild(body);
  const input = el('textarea', { class: 'plain mono', rows: '8', placeholder: 'Paste or type here' });
  const out = el('pre', { class: 'out mono' });
  const pair = (fn, buttons) => {
    body.appendChild(input);
    body.appendChild(el('div', { class: 'row wrap' }, ...buttons));
    body.appendChild(out);
    input.addEventListener('input', fn);
  };
  const safe = (fn) => () => { try { out.textContent = fn(); out.classList.remove('bad-text'); } catch (e) { out.textContent = String(e.message || e); out.classList.add('bad-text'); } };
  if (which === 'json') {
    const fmt = safe(() => JSON.stringify(JSON.parse(input.value), null, 2));
    pair(fmt, [el('button', { class: 'small', text: 'Format', onclick: fmt }),
      el('button', { class: 'small', text: 'Minify', onclick: safe(() => JSON.stringify(JSON.parse(input.value))) }),
      el('button', { class: 'small', text: 'Sort keys', onclick: safe(() => JSON.stringify(sortKeys(JSON.parse(input.value)), null, 2)) })]);
  } else if (which === 'base64') {
    const enc = safe(() => btoa(String.fromCharCode(...new TextEncoder().encode(input.value))));
    pair(enc, [el('button', { class: 'small', text: 'Encode', onclick: enc }),
      el('button', { class: 'small', text: 'Decode', onclick: safe(() => new TextDecoder().decode(
        Uint8Array.from(atob(input.value.trim()), (c) => c.charCodeAt(0)))) })]);
  } else if (which === 'url') {
    const enc = safe(() => encodeURIComponent(input.value));
    pair(enc, [el('button', { class: 'small', text: 'Encode', onclick: enc }),
      el('button', { class: 'small', text: 'Decode', onclick: safe(() => decodeURIComponent(input.value)) }),
      el('button', { class: 'small', text: 'Take a URL apart', onclick: safe(() => {
        const u = new URL(input.value.trim());
        const q = [...u.searchParams].map(([k, v]) => `  ${k} = ${v}`).join('\n');
        return `scheme  ${u.protocol}\nhost    ${u.host}\npath    ${u.pathname}\nhash    ${u.hash}\nquery\n${q}`;
      }) })]);
  } else if (which === 'hash') {
    const go2 = async () => {
      const reply = await PyCmd.call('hash', { text: input.value });
      out.textContent = ['md5', 'sha1', 'sha256', 'sha512'].map((k) => `${k.padEnd(7)} ${reply[k]}`).join('\n');
    };
    pair(go2, [el('button', { class: 'small', text: 'Hash this text', onclick: go2 }),
      el('button', { class: 'small', text: 'Hash a file…', onclick: async () => {
        const got = await PyCmd.call('pick.file', {});
        let path = got.path;
        if (!path) path = prompt('Path of the file');
        if (!path) return;
        out.textContent = 'Reading…';
        const reply = await PyCmd.call('hash', { path });
        out.textContent = reply.ok ? `${path}\n${PyCmd.bytes(reply.bytes)}\n\n`
          + ['md5', 'sha1', 'sha256', 'sha512'].map((k) => `${k.padEnd(7)} ${reply[k]}`).join('\n') : reply.error;
      } })]);
    go2();
  } else if (which === 'uuid') {
    const make = () => { out.textContent = Array.from({ length: 10 }, () => crypto.randomUUID()).join('\n'); };
    body.appendChild(el('button', { class: 'small primary', text: 'Ten more', onclick: make }));
    body.appendChild(out);
    make();
  } else if (which === 'time') {
    const conv = safe(() => {
      const v = input.value.trim();
      const d = !v ? new Date() : /^\d+(\.\d+)?$/.test(v) ? new Date(Number(v) * (v.length > 11 ? 1 : 1000)) : new Date(v);
      if (isNaN(d)) throw new Error('That is not a date or a Unix timestamp.');
      return `unix      ${Math.floor(d / 1000)}\nmillis    ${d.getTime()}\nISO (UTC) ${d.toISOString()}\nlocal     ${d.toString()}`;
    });
    input.placeholder = 'A Unix timestamp, or a date like 2026-11-20 14:00 - empty means now';
    input.rows = 2;
    pair(conv, [el('button', { class: 'small', text: 'Convert', onclick: conv })]);
    conv();
  } else if (which === 'regex') {
    const pattern = el('input', { class: 'mono', placeholder: 'Pattern, e.g. (\\d+)-(\\d+)' });
    const flags = el('input', { class: 'mono', value: 'g', style: 'max-width:80px' });
    const test = safe(() => {
      const re = new RegExp(pattern.value, flags.value.includes('g') ? flags.value : flags.value + 'g');
      const rows = [...input.value.matchAll(re)].slice(0, 200);
      if (!rows.length) return 'No match.';
      return rows.map((m, i) => `#${i + 1} at ${m.index}: ${JSON.stringify(m[0])}`
        + (m.length > 1 ? '\n   groups: ' + m.slice(1).map((g) => JSON.stringify(g)).join(', ') : '')).join('\n');
    });
    body.appendChild(el('div', { class: 'row' }, pattern, flags));
    pattern.addEventListener('input', test);
    flags.addEventListener('input', test);
    pair(test, []);
  } else if (which === 'diff') {
    const left = el('textarea', { class: 'plain mono', rows: '8', placeholder: 'Before' });
    const right = el('textarea', { class: 'plain mono', rows: '8', placeholder: 'After' });
    const compare = () => { out.innerHTML = diffHtml(lineDiff(left.value, right.value)); };
    left.addEventListener('input', compare);
    right.addEventListener('input', compare);
    body.appendChild(el('div', { class: 'grid two' }, left, right));
    body.appendChild(out);
    out.classList.add('diff');
  } else if (which === 'case') {
    const show = () => {
      const t = input.value;
      const words = t.trim() ? t.trim().split(/\s+/).length : 0;
      const parts = t.replace(/([a-z])([A-Z])/g, '$1 $2').split(/[^A-Za-z0-9]+/).filter(Boolean);
      out.textContent = `characters ${t.length} · words ${words} · lines ${t ? t.split('\n').length : 0}\n\n`
        + `UPPER       ${t.toUpperCase()}\nlower       ${t.toLowerCase()}\n`
        + `Title       ${t.replace(/\w\S*/g, (w) => w[0].toUpperCase() + w.slice(1).toLowerCase())}\n`
        + `camelCase   ${parts.map((p, i) => i ? p[0].toUpperCase() + p.slice(1).toLowerCase() : p.toLowerCase()).join('')}\n`
        + `snake_case  ${parts.map((p) => p.toLowerCase()).join('_')}\n`
        + `kebab-case  ${parts.map((p) => p.toLowerCase()).join('-')}\n`
        + `CONSTANT    ${parts.map((p) => p.toUpperCase()).join('_')}`;
    };
    pair(show, []);
  } else if (which === 'color') {
    const picker = el('input', { type: 'color', value: '#3fcb7e' });
    const show = () => {
      const h = picker.value;
      const n = parseInt(h.slice(1), 16);
      const r = (n >> 16) & 255; const g = (n >> 8) & 255; const b = n & 255;
      const lum = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
      const L = 0.2126 * lum(r) + 0.7152 * lum(g) + 0.0722 * lum(b);
      out.textContent = `hex   ${h}\nrgb   rgb(${r}, ${g}, ${b})\n`
        + `contrast on black ${((L + 0.05) / 0.05).toFixed(2)} · on white ${(1.05 / (L + 0.05)).toFixed(2)}`;
      out.style.borderLeft = `12px solid ${h}`;
    };
    picker.addEventListener('input', show);
    body.appendChild(picker);
    body.appendChild(out);
    show();
  }
}

function sortKeys(value) {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === 'object') {
    return Object.keys(value).sort().reduce((o, k) => { o[k] = sortKeys(value[k]); return o; }, {});
  }
  return value;
}

/** A line diff by longest common subsequence. Plenty for pasted text. */
function lineDiff(a, b) {
  const x = a.split('\n'); const y = b.split('\n');
  if (x.length * y.length > 4e6) return 'Those are too long to compare here.';
  const t = Array.from({ length: x.length + 1 }, () => new Uint32Array(y.length + 1));
  for (let i = x.length - 1; i >= 0; i--) for (let j = y.length - 1; j >= 0; j--) {
    t[i][j] = x[i] === y[j] ? t[i + 1][j + 1] + 1 : Math.max(t[i + 1][j], t[i][j + 1]);
  }
  const out = [];
  let i = 0; let j = 0;
  while (i < x.length && j < y.length) {
    if (x[i] === y[j]) { out.push('  ' + x[i]); i++; j++; }
    else if (t[i + 1][j] >= t[i][j + 1]) out.push('- ' + x[i++]);
    else out.push('+ ' + y[j++]);
  }
  while (i < x.length) out.push('- ' + x[i++]);
  while (j < y.length) out.push('+ ' + y[j++]);
  return out.join('\n');
}

// ---------------------------------------------------------------------------
// Ports
// ---------------------------------------------------------------------------

async function Ports(screen) {
  screen.appendChild(head('Ports', 'What is listening on this machine, and whether the port you want is free.'));
  const port = el('input', { type: 'number', placeholder: 'A port, e.g. 8000', min: '1', max: '65535' });
  const said = el('p', { class: 'muted' });
  const check = async () => {
    const r = await PyCmd.call('port.check', { port: Number(port.value) });
    said.textContent = !r.ok ? r.error : r.free ? `${r.port} is free.`
      : `${r.port} is taken` + (r.owner ? ` by ${r.owner.process || 'process ' + r.owner.pid}.` : '.');
  };
  port.addEventListener('keydown', (e) => { if (e.key === 'Enter') check(); });
  screen.appendChild(card(el('div', { class: 'row' }, port, el('button', { class: 'small primary', text: 'Check', onclick: check })), said));
  const reply = await PyCmd.call('ports', {});
  const list = el('div', { class: 'list' });
  (reply.listening || []).forEach((r) => list.appendChild(el('div', { class: 'row-item' },
    el('b', { class: 'mono', text: String(r.port) }),
    el('span', { class: 'muted mono', text: r.address }),
    el('span', { class: 'grow', text: r.process || (r.pid ? 'process ' + r.pid : '') }),
    r.port >= 1024 ? el('a', { href: `http://127.0.0.1:${r.port}/`, target: '_blank', text: 'open' }) : null,
    r.pid > 4 ? el('button', { class: 'small danger', text: 'Stop it', onclick: async () => {
      if (!confirm(`Stop ${r.process || 'process ' + r.pid}, which is listening on ${r.port}?`)) return;
      const done = await PyCmd.call('port.kill', { pid: r.pid });
      PyCmd.toast(done.ok ? 'Stopped.' : done.error || done.message);
      go('ports');
    } }) : null)));
  if (!(reply.listening || []).length) list.appendChild(el('div', { class: 'row-item muted', text: 'Nothing is listening.' }));
  screen.appendChild(card(el('div', { class: 'row spread' }, el('h2', { text: 'Listening now' }),
    el('button', { class: 'small', text: 'Refresh', onclick: () => go('ports') })), list));
}

// ---------------------------------------------------------------------------
// Snippets and notes
// ---------------------------------------------------------------------------

async function Snippets(screen) {
  screen.appendChild(head('Snippets', 'Code you reach for again and again. Copy it, or open it in the editor.'));
  const reply = await PyCmd.call('snippets', {});
  const name = el('input', { placeholder: 'Name' });
  const lang = el('input', { placeholder: 'Language, e.g. python', style: 'max-width:180px' });
  const code = el('textarea', { class: 'plain mono', rows: '6', placeholder: 'The code' });
  screen.appendChild(card(el('h2', { text: 'Keep a new one' }), el('div', { class: 'row' }, name, lang), code,
    el('button', { class: 'small primary', text: 'Keep it', onclick: async () => {
      const r = await PyCmd.call('snippet.save', { name: name.value, language: lang.value, code: code.value });
      PyCmd.toast(r.ok ? 'Kept.' : r.error);
      if (r.ok) go('snippets');
    } })));
  const draw = (rows, mine) => {
    const list = el('div', { class: 'grid' });
    rows.forEach((s) => list.appendChild(card(
      el('div', { class: 'row spread' }, el('b', { text: s.name }), el('span', { class: 'tag', text: s.language || 'text' })),
      el('pre', { class: 'out mono snippet', text: s.code }),
      el('div', { class: 'row' },
        el('button', { class: 'small', text: 'Copy', onclick: () => navigator.clipboard.writeText(s.code).then(() => PyCmd.toast('Copied.')) }),
        el('button', { class: 'small', text: 'Open in editor', onclick: async () => {
          const ext = { python: '.py', javascript: '.js', go: '.go', csharp: '.cs', powershell: '.ps1', rust: '.rs', c: '.c' }[s.language] || '.txt';
          const path = 'snippets/' + s.name.replace(/[^A-Za-z0-9]+/g, '_') + ext;
          await PyCmd.call('file.write', { path, text: s.code });
          openInEditor(path, false);
        } }),
        mine ? el('button', { class: 'small danger', text: 'Remove', onclick: async () => {
          await PyCmd.call('snippet.remove', { name: s.name }); go('snippets'); } }) : null))));
    return list;
  };
  if ((reply.mine || []).length) { screen.appendChild(el('h2', { text: 'Yours' })); screen.appendChild(draw(reply.mine, true)); }
  screen.appendChild(el('h2', { text: 'To start you off' }));
  screen.appendChild(draw(reply.builtin || [], false));
}

async function Notes(screen) {
  screen.appendChild(head('Notes', 'A scratchpad that saves itself. Plain text; Markdown if you like.'));
  const reply = await PyCmd.call('notes', {});
  const box = el('textarea', { class: 'plain mono notes', rows: '28', spellcheck: 'true' });
  box.value = reply.text || '';
  const said = el('span', { class: 'muted small-text', text: 'Saved.' });
  let timer = 0;
  box.addEventListener('input', () => {
    said.textContent = 'Saving…';
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const r = await PyCmd.call('notes.save', { text: box.value });
      said.textContent = r.ok ? 'Saved.' : 'Not saved: ' + r.error;
    }, 500);
  });
  screen.appendChild(card(el('div', { class: 'row spread' }, said,
    el('span', { class: 'muted small-text', text: `${(reply.text || '').length} characters` })), box));
  setTimeout(() => box.focus(), 30);
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

async function Settings(screen) {
  screen.appendChild(head('Settings', 'How PyCmd looks, and the few things it remembers.'));
  await lookLoad();

  // The account lives on Learn, where the progress is; it is here as well
  // because Settings is where people look for "sign out".
  screen.appendChild(el('h2', { text: 'Account and progress' }));
  screen.appendChild(accountCard(null));

  const themes = el('div', { class: 'theme-grid' });
  Object.entries(Look.themes).concat([['custom', Object.assign({}, Look.custom || lookPalette(), { name: 'Your own' })]])
    .forEach(([id, t]) => {
      themes.appendChild(el('button', { class: 'theme-card' + (Look.theme === id ? ' on' : ''),
        style: `background:${t.bg};color:${t.text};border-color:${Look.theme === id ? t.accent : t.line}`,
        onclick: async () => { await lookSet({ theme: id }); go('settings'); } },
        el('div', { class: 'swatches' },
          ...['accent', 'surface', 'raised', 'dim'].map((k) => el('span', { style: `background:${t[k]}` }))),
        el('b', { text: t.name }), id === Look.theme ? el('span', { class: 'small-text', text: '  ✓' }) : null));
    });
  screen.appendChild(card(el('h2', { text: 'Theme' }), themes));

  if (Look.theme === 'custom') {
    const base = lookPalette();
    const editor = el('div', { class: 'grid four' });
    const keys = [['accent', 'Accent'], ['bg', 'Background'], ['surface', 'Panels'], ['raised', 'Raised'],
      ['text', 'Text'], ['bright', 'Headings'], ['dim', 'Quiet text'], ['line', 'Lines']];
    const picks = {};
    keys.forEach(([k, label]) => {
      picks[k] = el('input', { type: 'color', value: base[k] || '#000000' });
      editor.appendChild(el('label', { class: 'field' }, el('span', { text: label }), picks[k]));
    });
    const light = el('input', { type: 'checkbox', checked: !!base.light });
    screen.appendChild(card(el('h2', { text: 'Your colours' }), editor,
      el('label', { class: 'row' }, light, 'This is a light theme'),
      el('button', { class: 'small primary', text: 'Use these', onclick: async () => {
        const custom = { name: 'Your own', light: light.checked };
        Object.entries(picks).forEach(([k, input]) => { custom[k] = input.value; });
        custom.accentBg = mixHex(custom.accent, custom.bg, 0.22);
        custom.accentLine = mixHex(custom.accent, custom.bg, 0.5);
        custom.sunken = mixHex('#000000', custom.bg, 0.35);
        custom.lineSoft = mixHex(custom.line, custom.bg, 0.5);
        custom.faint = mixHex(custom.dim, custom.bg, 0.65);
        await lookSet({ custom, theme: 'custom' });
        go('settings');
      } })));
  }

  const zoom = el('input', { type: 'range', min: '60', max: '200', step: '10', value: String(Math.round((Look.zoom || 1) * 100)) });
  const zoomSaid = el('span', { text: Math.round((Look.zoom || 1) * 100) + '%' });
  zoom.addEventListener('input', () => { zoomSaid.textContent = zoom.value + '%'; });
  zoom.addEventListener('change', () => lookSet({ zoom: Number(zoom.value) / 100 }));
  const compact = el('input', { type: 'checkbox', checked: !!Look.compact });
  compact.addEventListener('change', () => lookSet({ compact: compact.checked }));
  screen.appendChild(card(el('h2', { text: 'Size' }),
    el('div', { class: 'row' }, el('span', { class: 'muted', text: 'Zoom' }), zoom, zoomSaid),
    el('label', { class: 'row' }, compact, 'Compact: less space around things')));

  const env = await PyCmd.call('env', {});
  const envBox = el('textarea', { class: 'plain mono', rows: '5', placeholder: 'NAME=value, one per line' });
  envBox.value = Object.entries(env.vars || {}).map(([k, v]) => `${k}=${v}`).join('\n');
  screen.appendChild(card(el('h2', { text: 'Environment variables for everything you run' }),
    el('p', { class: 'muted', text: 'Set for every program the console, Run, Tasks and Learn start. '
      + 'Nothing is written to Windows itself.' }),
    envBox,
    el('button', { class: 'small primary', text: 'Save', onclick: async () => {
      const vars = {};
      envBox.value.split('\n').forEach((line) => {
        const at = line.indexOf('=');
        if (at > 0) vars[line.slice(0, at).trim()] = line.slice(at + 1);
      });
      const r = await PyCmd.call('env.set', { vars });
      PyCmd.toast(r.ok ? `Saved ${Object.keys(r.vars).length}.` : r.error);
    } })));

  screen.appendChild(card(el('h2', { text: 'Remembered things' }),
    el('div', { class: 'row wrap' },
      el('button', { class: 'small', text: 'Forget console history', onclick: async () => {
        await PyCmd.call('history.clear', {}); PyCmd.toast('Forgotten.'); } }),
      el('button', { class: 'small', text: 'Forget recent files', onclick: async () => {
        await PyCmd.call('recent.clear', {}); PyCmd.toast('Forgotten.'); } }),
      el('button', { class: 'small', text: 'Keyboard shortcuts', onclick: shortcutsSheet }),
      el('button', { class: 'small', text: "What's new", onclick: () => whatsNewSheet(true) }),
      el('button', { class: 'small', text: 'Export diagnostics', onclick: exportDiagnostics }))));
}

function mixHex(a, b, amount) {
  const pa = parseInt(a.slice(1), 16); const pb = parseInt(b.slice(1), 16);
  const ch = (shift) => Math.round(((pa >> shift) & 255) * amount + ((pb >> shift) & 255) * (1 - amount));
  return '#' + [16, 8, 0].map((s) => ch(s).toString(16).padStart(2, '0')).join('');
}

// ---------------------------------------------------------------------------
// New project
// ---------------------------------------------------------------------------

async function newProjectSheet() {
  const reply = await PyCmd.call('templates', {});
  const name = el('input', { placeholder: 'Project name', value: 'my-project' });
  const git = el('input', { type: 'checkbox', checked: true });
  let folder = '';
  const list = el('div', { class: 'list' });
  (reply.templates || []).forEach((t) => list.appendChild(el('button', { class: 'row-item', onclick: async () => {
    const r = await PyCmd.call('template.create', { template: t.id, name: name.value, folder, git: git.checked });
    if (!r.ok) { PyCmd.toast(r.error); return; }
    PyCmd.closeSheet();
    PyCmd.toast('Made ' + r.folder);
    openInEditor(r.open, true);
  } }, el('b', { text: t.name }), el('span', { class: 'grow muted small-text', text: t.files.join(', ') }),
    el('span', { class: 'tag', text: t.language }))));
  PyCmd.sheet('New project', el('div', {}, name,
    folderPicker('', (v) => { folder = v; }, 'Inside'),
    el('label', { class: 'row' }, git, 'Make it a git repository'),
    el('p', { class: 'muted', text: 'Pick a template:' }), list));
  setTimeout(() => name.select(), 30);
}

Object.assign(window.Screens, {
  learn: Learn, search: Search, git: Git, tasks: Tasks, tools: Tools, ports: Ports,
  snippets: Snippets, notes: Notes, settings: Settings,
});
