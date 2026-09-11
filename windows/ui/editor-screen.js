/*
  The Editor screen.

  What was here before was three lines - an iframe pointed at the shared
  editor page and nothing else. The editor *inside* that frame is the same
  one the phone has, and it is good: syntax highlighting for every language in
  the registry, a gutter, bracket matching, undo history, snippets. All of it
  was unreachable, because nothing outside the frame ever called it.

  `web/editor.js` exposes `window.PyEditor` - setContent, setLanguage, insert,
  insertSnippet, indent, outdent, undo, redo, focus, setWrap, goToLine, stats -
  and talks back through `window.PyBridge`. On the phone, Kotlin provides that
  bridge. Here nothing did, so the editor had no host: no way to open a file
  into it, no way to get one out, no undo button, no idea what language it was
  looking at.

  This is that host. The frame is served from our own loopback origin, so the
  bridge goes in on load rather than through postMessage - same-origin means
  the parent can simply reach in, which is both simpler and synchronous.

  Above the frame: a real toolbar. Below it: a status line that says where the
  caret is and whether there is anything unsaved. Around both: tabs, because
  one file at a time is not an editor, it is a text box.
*/

'use strict';

const Ed = {
  open: [],          // [{path, name, language, text, saved, dirty}]
  active: -1,
  frame: null,
  ready: false,
  line: 1,
  column: 1,
  wrap: false,
  // Set while setContent is running, so the change it causes is not mistaken
  // for the user typing - which would mark a file dirty the moment it opened.
  loading: false,
};

function edApi() {
  try {
    return Ed.frame && Ed.frame.contentWindow && Ed.frame.contentWindow.PyEditor;
  } catch (error) { return null; }
}

function edCurrent() {
  return Ed.active >= 0 ? Ed.open[Ed.active] : null;
}

/*
  The registry gives `extensions` as one comma-separated string - ".py,.pyw" -
  not as a list. Treating it as a list is the obvious mistake and a silent one:
  `"".some` is not a function, so every call would have thrown and every file
  would have opened as plain text.
*/
function edExtensions(row) {
  const raw = row && row.extensions;
  if (Array.isArray(raw)) return raw;
  return String(raw || '').split(',').map((e) => e.trim().toLowerCase()).filter(Boolean);
}

function edLanguageFor(name) {
  const dot = (name || '').lastIndexOf('.');
  const ext = dot < 0 ? '' : name.slice(dot).toLowerCase();
  if (!ext) return 'text';
  const found = (PyCmd.state.languages || []).find(
    (row) => edExtensions(row).indexOf(ext) >= 0);
  return found ? found.id : 'text';
}

/* `file.read` hands back the whole language record, not its id. */
function edLanguageId(value, fallbackName) {
  if (value && typeof value === 'object' && value.id) return value.id;
  if (typeof value === 'string' && value) return value;
  return edLanguageFor(fallbackName);
}

// ---------------------------------------------------------------------------
// The screen
// ---------------------------------------------------------------------------

function Editor(screen) {
  screen.classList.add('flush');
  const wrap = PyCmd.el('div', { class: 'editor-shell' });

  const tabs = PyCmd.el('div', { class: 'file-tabs', id: 'edTabs' });
  const bar = PyCmd.el('div', { class: 'toolbar', id: 'edBar' });
  const frame = PyCmd.el('iframe', { class: 'frame', src: '/web/editor.html' });
  const status = PyCmd.el('div', { class: 'statusline', id: 'edStatus' });

  Ed.frame = frame;
  Ed.ready = false;
  frame.addEventListener('load', () => {
    edInstallBridge();
    Ed.ready = true;
    // Whatever was open before the tab was switched away comes back.
    if (edCurrent()) edShow(edCurrent());
    else edSetLanguage('text');
    edDrawStatus();
  });

  wrap.appendChild(tabs);
  wrap.appendChild(bar);
  wrap.appendChild(frame);
  wrap.appendChild(status);
  screen.appendChild(wrap);

  edDrawBar();
  edDrawTabs();
  edDrawStatus();
}

/** Gives the frame the host object `web/editor.js` expects to talk to. */
function edInstallBridge() {
  let win;
  try { win = Ed.frame.contentWindow; } catch (error) { return; }
  if (!win) return;
  win.PyBridge = {
    onEditorChanged: function (text) {
      if (Ed.loading) return;
      const file = edCurrent();
      if (!file) return;
      const wasDirty = file.dirty;
      file.text = text;
      file.dirty = text !== file.saved;
      if (file.dirty !== wasDirty) edDrawTabs();
      edDrawStatus();
    },
    onCursorMoved: function (line, column) {
      Ed.line = line; Ed.column = column;
      edDrawStatus();
    },
    onEditorReady: function () { Ed.ready = true; },
  };
}

function edCall(name) {
  const api = edApi();
  if (!api || typeof api[name] !== 'function') return null;
  const rest = Array.prototype.slice.call(arguments, 1);
  try { return api[name].apply(api, rest); } catch (error) { return null; }
}

/*
  `stats()` hands back a JSON *string*, not an object. It has to: on the phone
  it crosses Kotlin's addJavascriptInterface boundary, which carries strings
  and nothing else. Reading `.lines` off the string gives undefined, so the
  status line said "0 lines" about a file with three in it.
*/
function edStats() {
  const raw = edCall('stats');
  if (raw && typeof raw === 'object') return raw;
  try { return JSON.parse(raw || '{}'); } catch (error) { return {}; }
}

/*
  And there is no text in stats at all, so the "capture what is on screen
  before switching tabs" step was reading undefined and quietly doing nothing.
  It happened to work only because onEditorChanged keeps the record current on
  every keystroke - which is not something to depend on for a save.

  The frame is same-origin, so the honest answer is to read the textarea.
*/
function edText() {
  try {
    const box = Ed.frame.contentWindow.document.getElementById('input');
    if (box) return box.value;
  } catch (error) { /* frame not ready */ }
  const file = edCurrent();
  return file ? file.text : '';
}

function edSetLanguage(language) {
  edCall('setLanguage', language || 'text');
}

function edShow(file) {
  Ed.loading = true;
  edCall('setContent', file.text || '');
  edSetLanguage(file.language);
  Ed.loading = false;
  edCall('focus');
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

function edDrawTabs() {
  const host = document.getElementById('edTabs');
  if (!host) return;
  PyCmd.clear(host);

  if (!Ed.open.length) {
    host.appendChild(PyCmd.el('span', {
      class: 'muted pad',
      text: 'Nothing open. Use Open, or New, to start.',
    }));
    return;
  }

  Ed.open.forEach((file, index) => {
    const tab = PyCmd.el('button', {
      class: 'file-tab' + (index === Ed.active ? ' on' : ''),
      title: file.path || 'not saved yet',
      onclick: () => edActivate(index),
    },
      PyCmd.el('span', { text: file.name }),
      PyCmd.el('span', { class: 'dot' + (file.dirty ? ' show' : ''), text: '•' }));

    tab.appendChild(PyCmd.el('span', {
      class: 'x', text: '×', title: 'Close',
      onclick: (event) => { event.stopPropagation(); edClose(index); },
    }));
    host.appendChild(tab);
  });
}

function edActivate(index) {
  if (index < 0 || index >= Ed.open.length) return;
  // Take what is on screen before leaving, so switching tabs never loses a
  // keystroke - the frame holds the only copy between change events.
  const leaving = edCurrent();
  if (leaving) leaving.text = edText();
  Ed.active = index;
  edShow(Ed.open[index]);
  edDrawTabs();
  edDrawBar();
  edDrawStatus();
}

async function edClose(index) {
  const file = Ed.open[index];
  if (!file) return;
  if (file.dirty) {
    const keep = await edAskUnsaved(file);
    if (keep === 'cancel') return;
    if (keep === 'save') {
      const saved = await edSave(file);
      if (!saved) return;
    }
  }
  Ed.open.splice(index, 1);
  if (Ed.active >= Ed.open.length) Ed.active = Ed.open.length - 1;
  if (Ed.active < 0) {
    Ed.loading = true; edCall('setContent', ''); Ed.loading = false;
  } else {
    edShow(Ed.open[Ed.active]);
  }
  edDrawTabs();
  edDrawStatus();
}

function edAskUnsaved(file) {
  return new Promise((resolve) => {
    let answered = false;
    const pick = (what) => { answered = true; PyCmd.closeSheet(); resolve(what); };
    PyCmd.sheet('Save ' + file.name + '?', PyCmd.el('div', {},
      PyCmd.el('p', { class: 'muted',
        text: 'It has changes that are not written to the disk yet.' }),
      PyCmd.el('div', { class: 'row' },
        PyCmd.el('button', { class: 'primary', text: 'Save', onclick: () => pick('save') }),
        PyCmd.el('button', { text: 'Close without saving', onclick: () => pick('discard') }),
        PyCmd.el('button', { text: 'Keep it open', onclick: () => pick('cancel') }))));
    // Dismissing the sheet any other way means "no, actually" rather than
    // silently throwing the file away.
    const watch = setInterval(() => {
      if (document.getElementById('sheet').hidden) {
        clearInterval(watch);
        if (!answered) resolve('cancel');
      }
    }, 120);
  });
}

// ---------------------------------------------------------------------------
// The toolbar
// ---------------------------------------------------------------------------

function edDrawBar() {
  const host = document.getElementById('edBar');
  if (!host) return;
  PyCmd.clear(host);
  const file = edCurrent();
  const has = !!file;

  const group = (...kids) => PyCmd.el('div', { class: 'tgroup' }, ...kids);
  /*
    `mousedown` is cancelled on every one of these. The editor's undo and redo
    are `document.execCommand`, which acts on whatever is focused - and a
    button takes focus the instant it is pressed, so by the time the click
    handler ran the textarea had lost it and undo did nothing at all. Killing
    the default on mousedown means focus never leaves the editor, which is
    what every toolbar sitting above an editable has to do.
  */
  const keepFocus = (event) => event.preventDefault();
  const b = (text, title, fn, extra) => {
    const button = PyCmd.el('button', {
      class: 'small' + (extra || ''), text, title, onclick: fn,
    });
    button.addEventListener('mousedown', keepFocus);
    return button;
  };

  host.appendChild(group(
    b('New', 'A new empty file (Ctrl+N)', edNew),
    b('Open', 'Open a file from the workspace (Ctrl+O)', edOpen),
  ));

  host.appendChild(group(
    b('Save', 'Write it to the disk (Ctrl+S)', () => edSave(), has ? ' primary' : ''),
    b('Save as', 'Write it somewhere else', () => edSaveAs()),
  ));

  host.appendChild(group(
    b('Run', 'Save it and run it (Ctrl+Enter)', edRun, has ? ' good' : ''),
  ));

  host.appendChild(group(
    b('↶', 'Undo (Ctrl+Z)', () => { edCall('undo'); edCall('focus'); }),
    b('↷', 'Redo (Ctrl+Y)', () => { edCall('redo'); edCall('focus'); }),
    b('→|', 'Indent (Tab)', () => { edCall('indent'); edCall('focus'); }),
    b('|←', 'Outdent (Shift+Tab)', () => { edCall('outdent'); edCall('focus'); }),
  ));

  host.appendChild(group(
    b('Find', 'Find and replace (Ctrl+F)', edFind),
    b('Line', 'Go to a line (Ctrl+G)', edGoToLine),
    b(Ed.wrap ? 'Wrap on' : 'Wrap off', 'Wrap long lines', () => {
      Ed.wrap = !Ed.wrap;
      edCall('setWrap', Ed.wrap);
      edDrawBar();
    }, Ed.wrap ? ' on' : ''),
  ));

  // The language is a control, not a label: a file with no extension, or one
  // the registry guesses wrong, has to be correctable.
  const picker = PyCmd.el('select', {
    class: 'small', title: 'How to colour it',
    onchange: (event) => {
      if (!file) return;
      file.language = event.target.value;
      edSetLanguage(file.language);
    },
  });
  const langs = (PyCmd.state.languages || []).slice()
    .sort((a, b) => a.name.localeCompare(b.name));
  picker.appendChild(PyCmd.el('option', { value: 'text', text: 'Plain text' }));
  langs.forEach((row) => picker.appendChild(PyCmd.el('option', {
    value: row.id, text: row.name,
  })));
  if (file) picker.value = file.language || 'text';
  picker.disabled = !has;
  host.appendChild(group(picker));
}

function edDrawStatus() {
  const host = document.getElementById('edStatus');
  if (!host) return;
  PyCmd.clear(host);
  const file = edCurrent();
  if (!file) {
    host.appendChild(PyCmd.el('span', { class: 'muted', text: 'No file open' }));
    return;
  }
  const stats = edStats();
  const language = (PyCmd.state.languages || []).find((r) => r.id === file.language);
  host.appendChild(PyCmd.el('span', {
    text: file.path || '(not saved yet)',
    class: 'grow ellipsis' + (file.dirty ? ' warnText' : ''),
  }));
  host.appendChild(PyCmd.el('span', { class: 'muted', text: file.dirty ? 'unsaved' : 'saved' }));
  host.appendChild(PyCmd.el('span', { class: 'muted', text: language ? language.name : 'Plain text' }));
  host.appendChild(PyCmd.el('span', {
    class: 'muted',
    text: (stats.lines || 0) + ' lines · ' + (stats.characters || 0) + ' chars',
  }));
  host.appendChild(PyCmd.el('span', { text: 'Ln ' + Ed.line + ', Col ' + Ed.column }));
}

// ---------------------------------------------------------------------------
// What the buttons do
// ---------------------------------------------------------------------------

function edAdd(file) {
  // Opening something already open goes to it rather than opening it twice.
  const already = Ed.open.findIndex((row) => row.path && row.path === file.path);
  if (already >= 0) { edActivate(already); return; }
  Ed.open.push(file);
  edActivate(Ed.open.length - 1);
}

function edNew() {
  let n = 1;
  while (Ed.open.some((f) => f.name === 'untitled-' + n + '.py')) n += 1;
  edAdd({
    path: '', name: 'untitled-' + n + '.py', language: 'python',
    text: '', saved: '', dirty: false,
  });
}

/*
 * Open: the workspace, or anywhere on this PC.
 *
 * Two roots and one list. The workspace half walks `files`, which is
 * relative-path country; the PC half walks `disk`, which is absolute. The
 * only thing the list needs to remember is which it is in, because that is
 * what `edOpenPath` needs to be told.
 */
async function edOpen() {
  const body = PyCmd.el('div', {});
  const list = PyCmd.el('div', { class: 'list' });
  let onDisk = false;
  let at = '';

  const tabs = PyCmd.el('div', { class: 'row', style: 'margin-bottom:8px' });
  const source = (disk, label) => {
    const button = PyCmd.el('button', {
      class: 'small' + (onDisk === disk ? ' primary' : ''), text: label,
      onclick: () => { onDisk = disk; at = ''; redrawTabs(); draw(''); },
    });
    return button;
  };
  function redrawTabs() {
    PyCmd.clear(tabs);
    tabs.appendChild(source(false, 'Workspace'));
    tabs.appendChild(source(true, 'This PC'));
  }
  redrawTabs();

  async function draw(path) {
    at = path;
    PyCmd.clear(list);
    list.appendChild(PyCmd.el('div', { class: 'empty', text: 'Looking…' }));
    const here = onDisk
      ? await PyCmd.call('disk', { path })
      : await PyCmd.call('files', { path });
    PyCmd.clear(list);
    if (!here.ok) {
      list.appendChild(PyCmd.el('div', { class: 'empty', text: here.error }));
      return;
    }

    // At the top of "This PC" there are no entries, only drives and folders.
    if (onDisk && here.atRoot) {
      (here.places || []).concat(here.drives || []).forEach((place) => {
        list.appendChild(PyCmd.el('button', {
          class: 'row-item', text: '📁  ' + place.name,
          onclick: () => draw(place.path),
        }));
      });
      return;
    }

    const up = onDisk
      ? (here.parent !== undefined ? here.parent : '')
      : (path ? path.split('/').slice(0, -1).join('/') : null);
    if (path) {
      list.appendChild(PyCmd.el('button', {
        class: 'row-item', text: '..  back', onclick: () => draw(up || ''),
      }));
    }
    (here.entries || []).filter((row) => row.folder).forEach((row) => {
      list.appendChild(PyCmd.el('button', {
        class: 'row-item', text: '📁  ' + row.name,
        onclick: () => draw(row.path),
      }));
    });
    (here.entries || []).filter((row) => !row.folder).forEach((row) => {
      list.appendChild(PyCmd.el('button', {
        class: 'row-item', onclick: () => edOpenPath(row.path, onDisk),
      },
        PyCmd.el('span', { text: row.name, class: 'grow' }),
        PyCmd.el('span', { class: 'muted', text: PyCmd.bytes(row.bytes) })));
    });
    if (!(here.entries || []).length) {
      list.appendChild(PyCmd.el('div', { class: 'empty', text: 'Nothing in here.' }));
    }
  }

  body.appendChild(tabs);
  body.appendChild(list);
  PyCmd.sheet('Open a file', body);
  draw('');
}

/*
 * `onDisk` picks which half of the world the path is in: false for a
 * workspace-relative path, true for an absolute one anywhere on the PC. The
 * flag rides along on the open file so that saving goes back out the same
 * door it came in - a file opened from C:\\Users\\you\\notes.md is saved
 * to C:\\Users\\you\\notes.md, not copied into the workspace.
 *
 * Returns whether it opened, so the caller knows whether to switch tabs.
 */
async function edOpenPath(path, onDisk) {
  const reply = await PyCmd.call(onDisk ? 'disk.read' : 'file.read', { path });
  if (!reply.ok) {
    // A binary or an enormous file is refused by name, and the reason is
    // worth reading: "PyCmd will not open it - saving would corrupt it" is
    // the difference between a bug and a decision.
    PyCmd.toast(reply.error || 'could not open that');
    return false;
  }
  PyCmd.closeSheet();
  const name = path.split(/[\\/]/).pop();
  edAdd({
    path, name, disk: !!onDisk,
    language: edLanguageId(reply.language, name),
    text: reply.text || '', saved: reply.text || '', dirty: false,
  });
  return true;
}

/** Pulls what is on screen into the file record, then writes it. */
async function edSave(which) {
  const file = which || edCurrent();
  if (!file) { PyCmd.toast('Nothing to save.'); return false; }
  if (file === edCurrent()) file.text = edText();
  if (!file.path) return edSaveAs(file);

  const reply = await PyCmd.call(file.disk ? 'disk.write' : 'file.write',
                                 { path: file.path, text: file.text });
  if (!reply.ok) { PyCmd.toast(reply.error || 'could not save'); return false; }
  file.saved = file.text;
  file.dirty = false;
  edDrawTabs();
  edDrawStatus();
  PyCmd.toast('Saved ' + file.name);
  return true;
}

function edSaveAs(which) {
  const file = which || edCurrent();
  if (!file) { PyCmd.toast('Nothing to save.'); return Promise.resolve(false); }
  return new Promise((resolve) => {
    const name = PyCmd.el('input', { value: file.name, spellcheck: 'false' });
    // A file that came from the disk saves back to the disk, in the folder it
    // was in; one from the workspace stays in the workspace. Offering "Save
    // as" and then silently changing which of the two you are in would be the
    // worst kind of surprise.
    const onDisk = !!file.disk;
    const folder = PyCmd.el('input', {
      value: file.path ? file.path.split(/[\\/]/).slice(0, -1).join(onDisk ? '\\' : '/') : '',
      placeholder: onDisk ? 'a folder on this PC' : 'workspace root',
      spellcheck: 'false',
    });
    const save = async () => {
      const wanted = (name.value || '').trim();
      if (!wanted) { PyCmd.toast('It needs a name.'); return; }
      const at = (folder.value || '').trim();
      const slash = onDisk ? '\\' : '/';
      const path = at ? at.replace(/[\\/]+$/, '') + slash + wanted : wanted;
      if (onDisk && !at) { PyCmd.toast('A file on this PC needs a folder.'); return; }
      const reply = await PyCmd.call(onDisk ? 'disk.write' : 'file.write',
                                     { path, text: file.text });
      if (!reply.ok) { PyCmd.toast(reply.error || 'could not save'); return; }
      file.path = path;
      file.name = wanted;
      file.language = edLanguageFor(wanted);
      file.saved = file.text;
      file.dirty = false;
      edSetLanguage(file.language);
      PyCmd.closeSheet();
      edDrawTabs(); edDrawBar(); edDrawStatus();
      PyCmd.toast('Saved as ' + wanted);
      resolve(true);
    };
    PyCmd.sheet('Save as', PyCmd.el('div', {},
      PyCmd.el('label', { text: 'Name' }), name,
      PyCmd.el('label', { text: onDisk ? 'Folder on this PC' : 'Folder in the workspace' }), folder,
      PyCmd.el('div', { class: 'row' },
        PyCmd.el('button', { class: 'primary', text: 'Save', onclick: save }),
        PyCmd.el('button', { text: 'Cancel', onclick: () => { PyCmd.closeSheet(); resolve(false); } }))));
  });
}

async function edRun() {
  const file = edCurrent();
  if (!file) { PyCmd.toast('Nothing to run.'); return; }
  const saved = await edSave(file);
  if (!saved) return;
  go('console');
  const reply = await PyCmd.call('run.file', { path: file.path });
  if (!reply.ok) { PyCmd.toast(reply.error || 'that would not run'); return; }
}

function edGoToLine() {
  const box = PyCmd.el('input', { type: 'number', min: '1', value: String(Ed.line) });
  const jump = () => {
    const n = parseInt(box.value, 10);
    if (n > 0) { edCall('goToLine', n); edCall('focus'); }
    PyCmd.closeSheet();
  };
  box.addEventListener('keydown', (e) => { if (e.key === 'Enter') jump(); });
  PyCmd.sheet('Go to line', PyCmd.el('div', {},
    PyCmd.el('label', { text: 'Line number' }), box,
    PyCmd.el('div', { class: 'row' },
      PyCmd.el('button', { class: 'primary', text: 'Go', onclick: jump }))));
  setTimeout(() => box.focus(), 60);
}

/*
  Find and replace works on the text rather than on the DOM: the editor is a
  textarea with a highlight layer painted behind it, so the only honest place
  to search is the string itself. Replacing rewrites the document through
  setContent and marks it dirty, which is what any other editor does.
*/
function edFind() {
  const file = edCurrent();
  if (!file) { PyCmd.toast('Nothing to search.'); return; }
  const needle = PyCmd.el('input', { placeholder: 'Find', spellcheck: 'false' });
  const swap = PyCmd.el('input', { placeholder: 'Replace with', spellcheck: 'false' });
  const count = PyCmd.el('div', { class: 'muted' });

  const currentText = edText;

  const tally = () => {
    const what = needle.value;
    if (!what) { count.textContent = ''; return 0; }
    const hits = currentText().split(what).length - 1;
    count.textContent = hits + (hits === 1 ? ' match' : ' matches');
    return hits;
  };
  needle.addEventListener('input', tally);

  const first = () => {
    const what = needle.value;
    if (!what) return;
    const where = currentText().indexOf(what);
    if (where < 0) { PyCmd.toast('Not found.'); return; }
    const line = currentText().slice(0, where).split('\n').length;
    edCall('goToLine', line);
    edCall('focus');
    PyCmd.closeSheet();
  };

  const replaceAll = () => {
    const what = needle.value;
    if (!what) return;
    const before = currentText();
    const after = before.split(what).join(swap.value);
    if (after === before) { PyCmd.toast('Nothing to replace.'); return; }
    Ed.loading = true;
    edCall('setContent', after);
    Ed.loading = false;
    file.text = after;
    file.dirty = after !== file.saved;
    edDrawTabs(); edDrawStatus();
    PyCmd.toast((before.split(what).length - 1) + ' replaced.');
    PyCmd.closeSheet();
  };

  PyCmd.sheet('Find and replace', PyCmd.el('div', {},
    PyCmd.el('label', { text: 'Find' }), needle,
    PyCmd.el('label', { text: 'Replace with' }), swap,
    count,
    PyCmd.el('div', { class: 'row' },
      PyCmd.el('button', { class: 'primary', text: 'Go to first', onclick: first }),
      PyCmd.el('button', { text: 'Replace all', onclick: replaceAll }))));
  setTimeout(() => needle.focus(), 60);
}

/** The shortcuts, wired once at startup rather than per draw. */
function edShortcuts() {
  document.addEventListener('keydown', (event) => {
    if (PyCmd.state.tab !== 'editor') return;
    const ctrl = event.ctrlKey || event.metaKey;
    if (!ctrl) return;
    const key = event.key.toLowerCase();
    const shortcuts = {
      s: () => edSave(),
      o: edOpen,
      n: edNew,
      g: edGoToLine,
      f: edFind,
      enter: edRun,
    };
    const fn = shortcuts[key === 'enter' ? 'enter' : key];
    if (fn) { event.preventDefault(); fn(); }
  });
}
