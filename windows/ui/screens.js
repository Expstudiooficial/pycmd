/*
 * One function per screen. Each is handed the empty middle of the window and
 * fills it.
 *
 * The console and the editor are iframes onto `/web/console.html` and
 * `/web/editor.html` - the very files the phone loads into its WebView, not
 * copies of them. Everything is served from the same 127.0.0.1 origin, so the
 * shell can reach into the frame and call `PyConsole.append` directly, which
 * is what the Kotlin side does with `evaluateJavascript`. That is the whole
 * trick behind this being a port rather than a rewrite.
 */
'use strict';

const el = PyCmd.el;
const clear = PyCmd.clear;

function head(title, lead) {
  return el('div', {},
    el('h1', { text: title }),
    lead ? el('p', { class: 'lead', text: lead }) : null);
}

function card(...children) {
  return el('div', { class: 'card' }, ...children);
}

/* Console lives in console-screen.js: history, completions, the input()
   state and the birthday made it a screen rather than a text box. */

/* Editor lives in editor-screen.js: it grew a toolbar, tabs and a status
   line, and putting a real screen in this file beside the small ones made
   both harder to read. */

// ---------------------------------------------------------------------------
// Files
// ---------------------------------------------------------------------------

let filesAt = '';

async function Files(screen) {
  const reply = await PyCmd.call('files', { path: filesAt });
  if (!reply.ok) {
    filesAt = '';
    screen.appendChild(el('div', { class: 'empty', text: reply.error }));
    return;
  }

  screen.appendChild(head('Files',
    'Your workspace is an ordinary Windows folder. Open it in Explorer, back it ' +
    'up, put it in git — PyCmd will not mind.'));

  const crumbs = el('div', { class: 'row wrap', style: 'margin-bottom:8px' },
    el('button', {
      class: 'small' + (filesAt ? '' : ' primary'), text: 'workspace',
      onclick: () => { filesAt = ''; go('files'); },
    }));
  let walked = '';
  (reply.path ? reply.path.split('/') : []).forEach((part, index, all) => {
    walked = walked ? walked + '/' + part : part;
    const here = walked;
    crumbs.appendChild(el('span', { class: 'muted', text: '›' }));
    crumbs.appendChild(el('button', {
      class: 'small' + (index === all.length - 1 ? ' primary' : ''), text: part,
      onclick: () => { filesAt = here; go('files'); },
    }));
  });
  screen.appendChild(crumbs);

  screen.appendChild(el('div', { class: 'row wrap', style: 'margin-bottom:10px' },
    el('button', { class: 'small primary', text: '+ New file', onclick: () => newFile(reply.path) }),
    el('button', { class: 'small', text: '+ New folder', onclick: () => newFolder(reply.path) }),
    el('button', { class: 'small', text: 'Bring a file in', onclick: () => bringIn(reply.path) }),
    el('span', { class: 'muted', text: reply.folders + ' folders · ' + reply.files + ' files' }),
  ));

  if (!reply.entries.length) {
    screen.appendChild(el('div', { class: 'empty', text: 'Nothing here yet.' }));
  }

  const list = el('div', { class: 'card', style: 'padding:4px 6px' });
  reply.entries.forEach((entry) => {
    const open = () => {
      if (entry.folder) { filesAt = entry.path; go('files'); return; }
      openFile(entry);
    };
    list.appendChild(el('div', {
      class: 'row',
      style: 'padding:7px 9px;border-bottom:1px solid #182231',
    },
      el('span', { style: 'width:20px;text-align:center', text: entry.folder ? '▸' : '·' }),
      el('button', {
        class: 'small', style: 'flex:1 1 auto;text-align:left;border-color:transparent;background:none',
        text: entry.name, onclick: open,
      }),
      entry.language ? el('span', { class: 'pill', text: entry.language }) : null,
      entry.folder ? null : el('span', { class: 'muted', text: PyCmd.bytes(entry.bytes) }),
      entry.runnable ? el('button', {
        class: 'small primary', text: 'Run',
        onclick: async () => {
          PyCmd.toast('Running ' + entry.name + ' — output is on the Console.');
          await PyCmd.call('run.file', { path: reply.root + '\\' + entry.name });
        },
      }) : null,
      el('button', {
        class: 'small', text: 'Rename',
        onclick: () => renameEntry(entry),
      }),
      el('button', {
        class: 'small danger', text: 'Delete',
        onclick: () => confirmDelete(entry),
      }),
    ));
  });
  screen.appendChild(list);
  screen.appendChild(el('p', { class: 'muted mono', style: 'font-size:11px', text: reply.root }));
}

async function openFile(entry) {
  const reply = await PyCmd.call('file.read', { path: entry.path });
  if (!reply.ok) {
    PyCmd.sheet(entry.name, el('p', { class: 'muted', text: reply.error }));
    return;
  }
  const box = el('textarea', {
    spellcheck: 'false',
    style: 'width:100%;height:52vh;font-family:Consolas,ui-monospace,monospace;font-size:12.5px',
  });
  box.value = reply.text;
  PyCmd.sheet(entry.name, el('div', {},
    el('div', { class: 'row', style: 'margin-bottom:8px' },
      el('span', { class: 'pill', text: (reply.language || {}).name || 'text' }),
      el('span', { class: 'muted', text: PyCmd.bytes(reply.bytes) })),
    box,
    el('div', { class: 'row', style: 'margin-top:10px' },
      el('button', {
        class: 'small primary', text: 'Save',
        onclick: async () => {
          const done = await PyCmd.call('file.write', { path: entry.path, text: box.value });
          PyCmd.toast(done.ok ? 'Saved.' : (done.error || 'that would not save'));
          if (done.ok) PyCmd.closeSheet();
        },
      }),
      entry.runnable ? el('button', {
        class: 'small', text: 'Save and run',
        onclick: async () => {
          await PyCmd.call('file.write', { path: entry.path, text: box.value });
          PyCmd.closeSheet();
          go('console');
          await PyCmd.call('run.file', { path: (PyCmd.state.root || '') + '\\workspace\\' + entry.path.replace(/\//g, '\\') });
        },
      }) : null,
      el('button', { class: 'small', text: 'Cancel', onclick: PyCmd.closeSheet }),
    )));
}

function newFile(where) {
  const name = el('input', { placeholder: 'hello.go', spellcheck: 'false' });
  const pick = el('select', {});
  pick.appendChild(el('option', { value: '', text: 'From the file name' }));
  (PyCmd.state.languages || [])
    .filter((row) => row.creatable !== false && row.mode !== 'media')
    .forEach((row) => pick.appendChild(
      el('option', { value: row.id, text: row.name + '  (' + row.extension + ')' })));

  pick.addEventListener('change', () => {
    const row = (PyCmd.state.languages || []).find((l) => l.id === pick.value);
    if (row && !name.value.includes('.')) {
      name.value = (name.value || 'untitled') + row.extension;
    }
  });

  PyCmd.sheet('A new file', el('div', {},
    el('p', { class: 'muted' },
      String((PyCmd.state.languageStats || {}).total || 0),
      ' file types, each with a starter template.'),
    el('label', { class: 'field' }, el('span', { text: 'Name' }), name),
    el('label', { class: 'field' }, el('span', { text: 'Language' }), pick),
    el('button', {
      class: 'small primary', text: 'Create',
      onclick: async () => {
        const path = (where ? where + '/' : '') + name.value.trim();
        const done = await PyCmd.call('file.create', { path, language: pick.value });
        if (done.ok) { PyCmd.closeSheet(); go('files'); }
        else PyCmd.toast(done.error || 'that would not work');
      },
    })));
  setTimeout(() => name.focus(), 60);
}

function newFolder(where) {
  const name = el('input', { placeholder: 'my-project', spellcheck: 'false' });
  PyCmd.sheet('A new folder', el('div', {},
    el('label', { class: 'field' }, el('span', { text: 'Name' }), name),
    el('button', {
      class: 'small primary', text: 'Create',
      onclick: async () => {
        const path = (where ? where + '/' : '') + name.value.trim();
        const done = await PyCmd.call('file.create', { path, folder: true });
        if (done.ok) { PyCmd.closeSheet(); go('files'); }
        else PyCmd.toast(done.error || 'that would not work');
      },
    })));
  setTimeout(() => name.focus(), 60);
}

function bringIn(where) {
  const source = el('input', {
    placeholder: 'C:\\Users\\you\\Documents\\notes.md', spellcheck: 'false',
  });
  PyCmd.sheet('Bring a file in', el('div', {},
    el('p', { class: 'muted' },
      'Anywhere on the disk. It is copied in, so the original is left alone.'),
    el('label', { class: 'field' }, el('span', { text: 'Full path' }), source),
    el('button', {
      class: 'small primary', text: 'Copy it in',
      onclick: async () => {
        const done = await PyCmd.call('file.import', { source: source.value.trim(), into: where });
        if (done.ok) { PyCmd.closeSheet(); PyCmd.toast(done.name + ' copied in'); go('files'); }
        else PyCmd.toast(done.error || 'that would not copy');
      },
    })));
  setTimeout(() => source.focus(), 60);
}

function renameEntry(entry) {
  const name = el('input', { spellcheck: 'false' });
  name.value = entry.name;
  PyCmd.sheet('Rename', el('div', {},
    el('label', { class: 'field' }, el('span', { text: 'New name' }), name),
    el('button', {
      class: 'small primary', text: 'Rename',
      onclick: async () => {
        const done = await PyCmd.call('file.rename', { path: entry.path, name: name.value.trim() });
        if (done.ok) { PyCmd.closeSheet(); go('files'); }
        else PyCmd.toast(done.error || 'that would not rename');
      },
    })));
}

function confirmDelete(entry) {
  PyCmd.sheet('Delete ' + entry.name + '?', el('div', {},
    el('p', { class: 'muted', text: entry.folder
      ? 'The folder and everything in it. There is no undo.'
      : 'There is no undo.' }),
    el('div', { class: 'row', style: 'margin-top:12px' },
      el('button', {
        class: 'small danger', text: 'Delete it',
        onclick: async () => {
          const done = await PyCmd.call('file.remove', { path: entry.path });
          if (done.ok) { PyCmd.closeSheet(); go('files'); }
          else PyCmd.toast(done.error || 'that would not delete');
        },
      }),
      el('button', { class: 'small', text: 'Keep it', onclick: PyCmd.closeSheet }))));
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

async function Run(screen) {
  screen.appendChild(head('Run a file',
    'Type a path and PyCmd works out what runs it — the real compiler if you have one, ' +
    'the interpreter it carries if you do not.'));

  const path = el('input', { placeholder: 'hello.go', spellcheck: 'false' });
  const pick = el('select', {});
  pick.appendChild(el('option', { value: '', text: 'Best available toolchain' }));
  (PyCmd.state.toolchains || []).filter((c) => c.installed).forEach((c) => {
    pick.appendChild(el('option', { value: c.id, text: c.name + ' — ' + c.languages.join(', ') }));
  });

  async function run() {
    const value = path.value.trim();
    if (!value) return;
    const full = value.includes(':') || value.startsWith('\\')
      ? value
      : (PyCmd.state.root || '') + '\\workspace\\' + value;
    PyCmd.toast('Running ' + value + ' — output is on the Console.');
    const reply = await PyCmd.call('run.file', { path: full, toolchain: pick.value });
    if (!reply.ok) PyCmd.toast(reply.error || 'that did not start');
  }

  screen.appendChild(card(
    el('label', { class: 'field' }, el('span', { text: 'File, relative to the workspace' }), path),
    el('label', { class: 'field' }, el('span', { text: 'Run it with' }), pick),
    el('div', { class: 'row' },
      el('button', { class: 'small primary', text: 'Run', onclick: run }),
      el('button', { class: 'small', text: 'Stop', onclick: () => PyCmd.call('run.stop') }),
      el('span', { class: 'muted', text: 'Output goes to the Console.' }),
    ),
  ));

  const stats = PyCmd.state.languageStats || {};
  screen.appendChild(el('p', { class: 'muted' },
    String(stats.runnable || 0), ' of ', String(stats.total || 0),
    ' file types can be run here. The Toolchains screen says which of them this machine is ready for.'));
}

// ---------------------------------------------------------------------------
// Toolchains
// ---------------------------------------------------------------------------

async function Toolchains(screen) {
  // The birthday's present, if it has been found. Draws nothing otherwise,
  // so the screen is unchanged for anybody who has not.
  setupPanel(screen);

  screen.appendChild(head('Toolchains',
    'What is installed on this machine, and what each one lets PyCmd run. ' +
    'PyCmd does not bundle compilers — a build carrying MSVC and a JDK would be gigabytes — ' +
    'so these are yours, found on the PATH.'));

  const status = el('p', { class: 'muted', text: 'Looking…' });
  screen.appendChild(el('div', { class: 'row' },
    el('button', {
      class: 'small', text: 'Look again',
      onclick: async () => {
        status.textContent = 'Looking…';
        const reply = await PyCmd.call('toolchains', { refresh: true });
        if (reply.ok) {
          PyCmd.state.toolchains = reply.toolchains;
          PyCmd.state.toolchainSummary = reply.summary;
        }
        draw();
      },
    }),
    status,
  ));

  const host = el('div', {});
  screen.appendChild(host);

  function draw() {
    const rows = PyCmd.state.toolchains || [];
    const found = rows.filter((r) => r.installed);
    const missing = rows.filter((r) => !r.installed);
    status.textContent = found.length + ' of ' + rows.length + ' found · ' +
      (PyCmd.state.toolchainSummary.language_count || 0) + ' languages ready';

    clear(host);
    host.appendChild(el('h2', { text: 'Here now' }));
    if (!found.length) {
      host.appendChild(el('div', { class: 'empty' },
        'None found yet. PyCmd still runs Python, C, Go, Rust and JavaScript on the ' +
        'interpreters it carries — install anything below to use the real thing instead.'));
    }
    const grid = el('div', { class: 'grid' });
    found.forEach((row) => grid.appendChild(chainCard(row)));
    host.appendChild(grid);

    host.appendChild(el('h2', { text: 'Not installed' }));
    const rest = el('div', { class: 'grid' });
    missing.forEach((row) => rest.appendChild(chainCard(row)));
    host.appendChild(rest);
  }

  function chainCard(row) {
    const install = row.install || {};
    const lines = [];
    ['winget', 'scoop', 'choco'].forEach((manager) => {
      if (install[manager]) {
        lines.push(el('div', { class: 'row', style: 'gap:6px;margin-top:5px' },
          el('code', { class: 'mono', style: 'flex:1 1 auto', text: install[manager] }),
          el('button', {
            class: 'small', text: 'Run',
            onclick: async () => {
              PyCmd.toast('Installing ' + row.name + ' — watch the Console.');
              await PyCmd.call('toolchain.install', { id: row.id, with: manager });
            },
          }),
        ));
      }
    });

    return card(
      el('div', { class: 'row spread' },
        el('b', { text: row.name }),
        row.installed
          ? el('span', { class: 'pill on', text: row.version || 'found' })
          : el('span', { class: 'pill off', text: 'not here' }),
      ),
      el('div', { style: 'margin:4px 0' },
        row.languages.map((id) => el('span', { class: 'pill', text: id }))),
      row.installed
        ? el('div', { class: 'muted mono', text: row.path })
        : el('div', {}, lines),
      row.note ? el('p', { class: 'muted', text: row.note }) : null,
      row.builds ? el('p', { class: 'muted', text: 'Compiles first, then runs what it built.' }) : null,
    );
  }

  draw();
}

// ---------------------------------------------------------------------------
// Languages
// ---------------------------------------------------------------------------

async function Languages(screen) {
  const stats = PyCmd.state.languageStats || {};
  screen.appendChild(head('Languages',
    stats.total + ' file types. ' + stats.runnable + ' run, ' + stats.preview +
    ' preview, ' + stats.editable + ' are edited and served, ' + stats.media + ' are media.'));

  const search = el('input', { placeholder: 'Search — rust, .cs, compiler…', spellcheck: 'false' });
  screen.appendChild(el('div', { class: 'card tight' }, search));
  const host = el('div', {});
  screen.appendChild(host);

  function draw() {
    const needle = search.value.trim().toLowerCase();
    const rows = (PyCmd.state.languages || []).filter((row) => {
      if (!needle) return true;
      return (row.name + ' ' + row.id + ' ' + row.extensions + ' ' +
              (row.toolchain_names || []).join(' ')).toLowerCase().includes(needle);
    });
    clear(host);
    host.appendChild(el('p', { class: 'muted', text: rows.length + ' shown' }));
    const grid = el('div', { class: 'grid' });
    rows.forEach((row) => {
      const ready = (row.toolchains || []).some(
        (id) => (PyCmd.state.toolchains || []).some((c) => c.id === id && c.installed));
      grid.appendChild(card(
        el('div', { class: 'row spread' },
          el('b', { text: row.name }),
          el('span', {
            class: 'pill ' + (row.mode === 'run' ? (ready ? 'on' : '') : 'off'),
            text: row.mode === 'run' ? (ready ? 'ready' : 'needs a toolchain') : row.mode,
          }),
        ),
        el('div', { class: 'muted mono', text: row.extensions }),
        row.note ? el('p', { class: 'muted', text: row.note }) : null,
      ));
    });
    host.appendChild(grid);
  }

  search.addEventListener('input', draw);
  draw();
}

// ---------------------------------------------------------------------------
// Plugins — the two halves, and bringing one over from the phone
// ---------------------------------------------------------------------------

async function Plugins(screen) {
  screen.appendChild(head('Plugins',
    'Thirteen are part of PyCmd and switch on and off. The rest are folders of ' +
    'Python and HTML, installed here or brought from a phone.'));

  const reply = await PyCmd.call('plugins');
  if (reply.ok) PyCmd.state.plugins = reply;
  const builtin = (reply.builtin || {});

  screen.appendChild(card(
    el('div', { class: 'row spread' },
      el('div', {},
        el('b', { text: 'Bring a plugin over from the phone' }),
        el('div', { class: 'muted', text: 'A folder with plugin.json in it, or a .zip of one.' })),
      el('button', { class: 'small primary', text: 'Choose…', onclick: importMobile }),
    ),
    el('p', { class: 'muted' },
      el('b', { text: 'Beta. ' }),
      'The plugin API is the same on both, so most phone plugins simply work — but ' +
      'not all of them do. PyCmd reads the plugin before installing it and tells you ' +
      'which parts of it this machine cannot honour. Anything that reaches for Android ' +
      'itself — notifications, wake locks, the media session, a /storage path — will ' +
      'not work here, and no amount of good will makes it.'),
  ));

  (builtin.groups || []).forEach((group) => {
    screen.appendChild(el('h2', { text: group.name }));
    const grid = el('div', { class: 'grid' });
    group.plugins.forEach((plugin) => grid.appendChild(builtinCard(plugin)));
    screen.appendChild(grid);
  });

  screen.appendChild(el('h2', { text: 'Installed' }));
  const installed = reply.installed || [];
  if (!installed.length) {
    screen.appendChild(el('div', { class: 'empty', text: 'None yet.' }));
  } else {
    const grid = el('div', { class: 'grid' });
    installed.forEach((plugin) => {
      grid.appendChild(card(
        el('div', { class: 'row spread' },
          el('b', { text: plugin.name || plugin.id }),
          el('span', { class: 'pill', text: plugin.version || '' })),
        el('p', { class: 'muted', text: (plugin.description || '').slice(0, 220) }),
        plugin.broken
          ? el('p', { class: 'muted', text: 'This one will not load: ' + (plugin.error || '') })
          : el('div', { class: 'row', style: 'margin-top:8px' },
              plugin.panel
                ? el('button', {
                    class: 'small primary', text: 'Open',
                    onclick: () => openPanel(plugin, plugin.panel),
                  })
                : null,
              el('button', {
                class: 'small', text: 'Settings',
                onclick: () => openSettings(plugin),
              }),
              el('button', {
                class: 'small danger', text: 'Remove',
                onclick: async () => {
                  const done = await PyCmd.call('plugin.remove', { id: plugin.id });
                  PyCmd.toast(done.ok ? (plugin.name + ' removed') : (done.error || 'no'));
                  if (done.ok) go('plugins');
                },
              }),
            ),
      ));
    });
    screen.appendChild(grid);
  }
}

function builtinCard(plugin) {
  const toggle = el('div', { class: 'switch' + (plugin.enabled ? ' on' : '') });
  toggle.addEventListener('click', async () => {
    const wanted = !toggle.classList.contains('on');
    const done = await PyCmd.call('builtin.set', { id: plugin.id, on: wanted });
    if (done.ok) { go('plugins'); PyCmd.toast(plugin.name + (wanted ? ' on' : ' off')); }
  });
  return card(
    el('div', { class: 'row spread' },
      el('div', {},
        el('b', { text: plugin.name }),
        el('div', { class: 'muted', text: plugin.tagline })),
      toggle),
    el('p', { class: 'muted', text: plugin.description }),
    plugin.powered_up
      ? el('p', { class: 'muted' }, el('b', { text: 'With Power Pack: ' }), plugin.powered_up)
      : null,
    plugin.windows_note
      ? el('p', { class: 'muted' }, el('b', { text: 'On Windows: ' }), plugin.windows_note)
      : null,
  );
}

async function openSettings(plugin) {
  const reply = await PyCmd.call('plugin.settings', { id: plugin.id });
  const rows = (reply && reply.settings) || [];
  if (!rows.length) {
    PyCmd.sheet(plugin.name || plugin.id,
      el('p', { class: 'muted', text: 'This plugin has no settings.' }));
    return;
  }
  const body = el('div', {});
  rows.forEach((row) => {
    const kind = row.type === 'switch' ? 'checkbox' : row.type === 'number' ? 'number' : 'text';
    let input;
    if (row.type === 'choice') {
      input = el('select', {});
      (row.options || []).forEach((option) => {
        input.appendChild(el('option', { value: option, text: option,
                                         selected: option === row.value }));
      });
    } else {
      input = el('input', { type: kind });
      if (kind === 'checkbox') input.checked = !!row.value;
      else input.value = row.value === null || row.value === undefined ? '' : String(row.value);
    }
    input.addEventListener('change', () => {
      const value = kind === 'checkbox' ? (input.checked ? '1' : '') : input.value;
      PyCmd.call('plugin.setting.set', { id: plugin.id, name: row.name, value });
    });
    body.appendChild(el('label', { class: 'field' },
      el('span', { text: row.label || row.name }), input,
      row.help ? el('span', { class: 'muted', text: row.help }) : null));
  });
  PyCmd.sheet(plugin.name || plugin.id, body);
}

async function importMobile() {
  const path = el('input', {
    placeholder: 'C:\\Users\\you\\Downloads\\my-plugin.zip',
    spellcheck: 'false',
  });
  const report = el('div', {});

  async function look() {
    clear(report).appendChild(el('p', { class: 'muted', text: 'Reading it…' }));
    const found = await PyCmd.call('plugin.inspect', { path: path.value.trim() });
    clear(report);
    if (!found.ok) {
      report.appendChild(el('p', { class: 'muted', text: found.error }));
      return;
    }
    report.appendChild(el('div', { class: 'row spread' },
      el('b', { text: found.name + ' ' + (found.version || '') }),
      el('span', {
        class: 'pill ' + (found.likely === 'fine' ? 'on' : ''),
        text: found.likely === 'fine' ? 'should work' : 'partly',
      })));
    if (found.description) {
      report.appendChild(el('p', { class: 'muted', text: found.description.slice(0, 300) }));
    }
    if (found.warnings.length) {
      report.appendChild(el('h2', { text: 'What will not carry over' }));
      found.warnings.forEach((warning) => {
        report.appendChild(el('p', { class: 'muted' },
          el('b', { text: warning.about + ': ' }), warning.detail));
      });
    } else {
      report.appendChild(el('p', { class: 'muted' },
        'Nothing in it reaches for Android. It should behave exactly as it did on the phone.'));
    }
    report.appendChild(el('div', { class: 'row', style: 'margin-top:12px' },
      el('button', {
        class: 'small primary', text: 'Install it',
        onclick: async () => {
          const done = await PyCmd.call('plugin.install', { path: found.folder });
          if (done.ok) {
            PyCmd.closeSheet();
            PyCmd.toast(found.name + ' installed. It is switched off until you turn it on.');
            go('plugins');
          } else {
            PyCmd.toast(done.error || 'that would not install');
          }
        },
      }),
      el('span', { class: 'muted', text: 'It arrives switched off, like any other plugin.' }),
    ));
  }

  PyCmd.sheet('Bring a plugin over', el('div', {},
    el('p', { class: 'muted' },
      'PyCmd plugins are folders of Python and HTML, and the plugin API is the ' +
      'same on the phone and here — so most of them work unchanged. Point at one ' +
      'and PyCmd will read it first and tell you what it finds.'),
    el('label', { class: 'field' },
      el('span', { text: 'Folder or .zip' }), path),
    el('button', { class: 'small', text: 'Read it', onclick: look }),
    report,
  ));
}

// ---------------------------------------------------------------------------
// A plugin's own panel
// ---------------------------------------------------------------------------

/**
 * Opens a plugin's page.
 *
 * The HTML comes from the same `panel_html` the phone build uses - house
 * stylesheet and bridge already injected - so what lands here is byte for byte
 * what a phone would show. It goes into an iframe with `srcdoc`, which keeps
 * this origin, which is what lets the object the page expects be put on its
 * window before its own script runs.
 *
 * `__pycmd_panel` is the same four verbs Kotlin exposes: call, toast, log,
 * close. The plugin cannot tell the difference, and that is the whole point.
 */
async function openPanel(plugin, panelFile) {
  const reply = await PyCmd.call('plugin.panel', { id: plugin.id, panel: panelFile || '' });
  if (!reply.ok || !reply.html) {
    PyCmd.toast((reply && reply.error) || 'that panel would not build');
    return;
  }

  const frame = el('iframe', {
    style: 'width:100%;height:70vh;border:0;border-radius:10px;background:var(--bg)',
    src: 'about:blank',
  });

  /*
   * The object goes on first, then the document is written into the frame.
   *
   * With `srcdoc` the panel's own scripts run before anything outside can
   * touch the frame, and the bridge's very first line is
   * `JSON.parse(window.__pycmd_panel.manifest())` - so every panel threw
   * before it drew. Loading about:blank gives a real same-origin window to
   * put the object on; writing the HTML afterwards means the scripts find it
   * already there, which is exactly the order Kotlin's addJavascriptInterface
   * guarantees on the phone.
   */
  frame.addEventListener('load', function install() {
    frame.removeEventListener('load', install);
    const view = frame.contentWindow;
    if (!view || view.__pycmd_panel) return;
    view.__pycmd_panel = {
      call(id, name, body) {
        let payload = null;
        try { payload = JSON.parse(body); } catch (error) { payload = body; }
        PyCmd.call('plugin.export', { id: plugin.id, name, payload }).then((answer) => {
          if (!view.__pycmd_resolve) return;
          view.__pycmd_resolve(String(id), answer.ok !== false, JSON.stringify(answer));
        });
      },
      toast: (text) => PyCmd.toast(String(text).slice(0, 300)),
      log: (text) => console.log('[' + plugin.id + ']', text),
      close: () => PyCmd.closeSheet(),
      innerScroll() {},
      manifest: () => JSON.stringify({
        id: plugin.id, name: plugin.name, version: plugin.version, author: plugin.author,
      }),
    };
    const document_ = view.document;
    document_.open();
    document_.write(reply.html);
    document_.close();
  });

  PyCmd.sheet(plugin.name || plugin.id, frame);
}

// A plugin pushing to its own panel, the way api.send does on the phone.
PyCmd.on('plugin-message', (event) => {
  document.querySelectorAll('iframe[srcdoc]').forEach((frame) => {
    const view = frame.contentWindow;
    if (view && view.__pycmd_message) view.__pycmd_message(event.body);
  });
});

// ---------------------------------------------------------------------------
// The rest
// ---------------------------------------------------------------------------

async function Servers(screen) {
  const reply = await PyCmd.call('servers');
  screen.appendChild(head('Servers',
    'Run a script, a program or a folder and reach it over HTTP. Loopback by ' +
    'default; tick the box to let the rest of your network in.'));

  const path = el('input', { placeholder: 'site  ·  app.py  ·  server.go', spellcheck: 'false' });
  const port = el('input', { type: 'number', placeholder: String(reply.suggested || 8000) });
  const label = el('input', { placeholder: 'What to call it' });
  const network = el('input', { type: 'checkbox' });
  const plan = el('div', { class: 'muted' });

  // Say what Run will do before it does it - a folder with an app.py in it is
  // run, one with an index.html is served, and those are different things.
  let planTimer = 0;
  path.addEventListener('input', () => {
    clearTimeout(planTimer);
    planTimer = setTimeout(async () => {
      if (!path.value.trim()) { plan.textContent = ''; return; }
      const answer = await PyCmd.call('server.plan', { path: path.value.trim() });
      const how = (answer.plan || {});
      // The engine's own words are short labels for its own use - "script",
      // "language", "serve", "folder". Saying them out loud reads as
      // "That would be language (Go)", so they get a sentence each.
      const said = {
        script: 'Run as a Python script',
        language: 'Run as a program',
        serve: 'Serve that folder as a site',
        folder: 'Serve that folder',
        page: 'Serve that page, opening on it',
        none: 'Nothing here can run that',
      }[how.how] || (how.how ? 'Run it as ' + how.how : '');
      plan.textContent = said
        ? said + (how.entry ? ' · entry point ' + how.entry : '') +
          (how.note ? ' — ' + how.note : '')
        : (answer.error || '');
    }, 350);
  });

  screen.appendChild(card(
    el('label', { class: 'field' },
      el('span', { text: 'File or folder, relative to the workspace' }), path),
    plan,
    el('div', { class: 'row' },
      el('label', { class: 'field', style: 'flex:1 1 0' },
        el('span', { text: 'Port (blank picks a free one)' }), port),
      el('label', { class: 'field', style: 'flex:1 1 0' },
        el('span', { text: 'Name' }), label)),
    el('label', { class: 'row', style: 'gap:8px' }, network,
      el('span', { class: 'muted',
        text: 'Reachable from the rest of the network' +
              (reply.ip ? ' (this machine is ' + reply.ip + ')' : '') })),
    el('div', { class: 'row', style: 'margin-top:10px' },
      el('button', {
        class: 'small primary', text: 'Start',
        onclick: async () => {
          if (!path.value.trim()) return PyCmd.toast('Point it at something first.');
          const done = await PyCmd.call('server.start', {
            path: path.value.trim(),
            port: Number(port.value) || 0,
            label: label.value.trim(),
            network: network.checked,
          });
          PyCmd.toast(done.ok ? ('Started on ' + (done.url || 'it')) : (done.error || 'that would not start'));
          if (done.ok) go('servers');
        },
      }),
      reply.count ? el('button', {
        class: 'small danger', text: 'Stop all',
        onclick: async () => { await PyCmd.call('server.stop', {}); go('servers'); },
      }) : null),
  ));

  screen.appendChild(el('h2', { text: 'Running' }));
  const rows = reply.servers || [];
  if (!rows.length) {
    screen.appendChild(el('div', { class: 'empty', text: 'Nothing running.' }));
    return;
  }
  rows.forEach((row) => {
    const handle = row.handle || row.id || '';
    screen.appendChild(card(
      el('div', { class: 'row spread' },
        el('b', { text: row.label || row.path || 'server' }),
        el('span', { class: 'pill on', text: ':' + (row.port || '?') })),
      row.url ? el('div', { class: 'mono muted', text: row.url }) : null,
      row.path ? el('div', { class: 'muted', style: 'font-size:11px', text: row.path }) : null,
      el('div', { class: 'row', style: 'margin-top:8px' },
        el('button', {
          class: 'small', text: 'Log',
          onclick: async () => {
            const log = await PyCmd.call('server.log', { handle });
            const lines = (log.lines || []).map((line) =>
              typeof line === 'string' ? line : (line.text || '')).join('');
            PyCmd.sheet(row.label || 'Server log',
              el('pre', { class: 'out', style: 'max-height:60vh',
                          text: lines || 'It has not said anything yet.' }));
          },
        }),
        el('button', {
          class: 'small', text: 'Stop',
          onclick: async () => {
            await PyCmd.call('server.stop', { handle });
            go('servers');
          },
        }),
        el('button', {
          class: 'small danger', text: 'Kill',
          onclick: async () => {
            await PyCmd.call('server.stop', { handle, force: true });
            go('servers');
          },
        }),
      )));
  });
}

async function Packages(screen) {
  const reply = await PyCmd.call('packages');
  screen.appendChild(head('Packages',
    'Python libraries from PyPI, installed into PyCmd’s own site-packages. ' +
    'Nothing here can break your system Python, and with a C compiler installed ' +
    'a package with an extension will build rather than refuse.'));

  const name = el('input', { placeholder: 'requests', spellcheck: 'false' });
  const found = el('div', {});

  async function look() {
    const asked = name.value.trim();
    if (!asked) return;
    clear(found).appendChild(el('p', { class: 'muted', text: 'Asking PyPI…' }));
    const info = await PyCmd.call('package.info', { name: asked });
    clear(found);
    if (!info.ok) {
      found.appendChild(el('p', { class: 'muted', text: info.error || 'PyPI has not heard of it' }));
      return;
    }
    found.appendChild(el('div', { class: 'row spread' },
      el('b', { text: (info.name || asked) + ' ' + (info.version || '') }),
      info.pure === false
        ? el('span', { class: 'pill', text: 'has compiled parts' })
        : el('span', { class: 'pill on', text: 'pure Python' })));
    if (info.summary) found.appendChild(el('p', { class: 'muted', text: info.summary }));
    if (info.pure === false) {
      found.appendChild(el('p', { class: 'muted' },
        'This one ships compiled code. On Windows that usually installs fine as ' +
        'long as there is a wheel for your Python; if there is not, it needs a ' +
        'C compiler — the Toolchains screen has one.'));
    }
  }

  screen.appendChild(card(
    el('label', { class: 'field' }, el('span', { text: 'Package name' }), name),
    el('div', { class: 'row' },
      el('button', { class: 'small', text: 'Look it up first', onclick: look }),
      el('button', {
        class: 'small primary', text: 'Install',
        onclick: async () => {
          const asked = name.value.trim();
          if (!asked) return;
          PyCmd.toast('Installing ' + asked + ' — watch the Console.');
          await PyCmd.call('package.install', { name: asked });
        },
      })),
    found,
  ));

  const rows = reply.packages || [];
  screen.appendChild(el('h2', { text: 'Installed  ·  ' + rows.length }));
  if (!rows.length) {
    screen.appendChild(el('div', { class: 'empty',
      text: 'None yet. Install one above, or type  pip install requests  on the Console.' }));
  } else {
    const grid = el('div', { class: 'grid' });
    rows.forEach((row) => grid.appendChild(card(
      el('div', { class: 'row spread' },
        el('b', { text: row.name || row }),
        el('span', { class: 'pill', text: row.version || '' })),
      el('button', {
        class: 'small danger', style: 'margin-top:8px', text: 'Remove',
        onclick: async () => {
          const done = await PyCmd.call('package.remove', { name: row.name || row });
          PyCmd.toast(done.ok ? 'Removed.' : (done.error || 'that would not remove'));
          go('packages');
        },
      }))));
    screen.appendChild(grid);
  }

  const bundled = reply.bundled || [];
  if (bundled.length) {
    screen.appendChild(el('h2', { text: 'Already inside PyCmd' }));
    screen.appendChild(el('div', {},
      bundled.map((row) => el('span', { class: 'pill on', text: row.name || row }))));
  }
}

async function Pages(screen) {
  const reply = await PyCmd.call('pages');
  screen.appendChild(head('Pages',
    'A site that lives in your workspace and is served from this machine. ' +
    'Point one at a folder you already have, or start from a template.'));

  const name = el('input', { placeholder: 'my-site', spellcheck: 'false' });
  const folder = el('select', {});
  folder.appendChild(el('option', { value: '', text: 'Make a new folder from a template' }));
  (reply.folders || []).forEach((row) => folder.appendChild(
    el('option', { value: row.path, text: '  '.repeat(row.depth) + row.path })));
  const template = el('select', {});
  (reply.templates || []).forEach((row) => template.appendChild(
    el('option', { value: row.id, text: (row.name || row.id) + (row.summary ? ' — ' + row.summary : '') })));

  folder.addEventListener('change', () => {
    template.disabled = !!folder.value;
  });

  screen.appendChild(card(
    el('label', { class: 'field' }, el('span', { text: 'Name' }), name),
    el('label', { class: 'field' },
      el('span', { text: 'Folder in the workspace' }), folder),
    el('label', { class: 'field' },
      el('span', { text: 'Or a template, if you are making a new folder' }), template),
    el('div', { class: 'row' },
      el('button', {
        class: 'small primary', text: 'Add it',
        onclick: async () => {
          if (!name.value.trim()) return PyCmd.toast('It needs a name.');
          const done = await PyCmd.call('page.create', {
            name: name.value.trim(),
            folder: folder.value,
            template: template.value,
          });
          PyCmd.toast(done.ok ? 'Added.' : (done.error || 'that would not work'));
          if (done.ok) go('pages');
        },
      }),
      el('span', { class: 'muted',
        text: reply.count + ' of ' + reply.max + ' pages · ' +
              reply.active + ' of ' + reply.max_active + ' can run at once' })),
  ));

  const rows = reply.pages || [];
  if (!rows.length) {
    screen.appendChild(el('div', { class: 'empty', text: 'No pages yet.' }));
    return;
  }
  const grid = el('div', { class: 'grid' });
  rows.forEach((row) => {
    const live = !!(row.active || row.running);
    grid.appendChild(card(
      el('div', { class: 'row spread' },
        el('b', { text: row.name || row.id }),
        el('span', { class: 'pill' + (live ? ' on' : ' off'), text: live ? 'live' : 'off' })),
      row.url ? el('div', { class: 'mono muted', text: row.url }) : null,
      row.folder ? el('div', { class: 'muted', style: 'font-size:11px', text: row.folder }) : null,
      el('div', { class: 'row', style: 'margin-top:8px' },
        el('button', {
          class: 'small' + (live ? '' : ' primary'), text: live ? 'Stop' : 'Start',
          onclick: async () => {
            const done = await PyCmd.call(live ? 'page.stop' : 'page.start', { id: row.id });
            PyCmd.toast(done.ok ? (live ? 'Stopped.' : ('Serving on ' + (done.url || 'it')))
                                : (done.error || 'that would not work'));
            go('pages');
          },
        }),
        el('button', {
          class: 'small', text: 'Rename',
          onclick: () => {
            const box = el('input', {});
            box.value = row.name || '';
            PyCmd.sheet('Rename', el('div', {},
              el('label', { class: 'field' }, el('span', { text: 'New name' }), box),
              el('button', {
                class: 'small primary', text: 'Rename',
                onclick: async () => {
                  await PyCmd.call('page.rename', { id: row.id, name: box.value.trim() });
                  PyCmd.closeSheet(); go('pages');
                },
              })));
          },
        }),
        el('button', {
          class: 'small danger', text: 'Remove',
          onclick: async () => {
            // The folder stays. A page is a pointer at your files, and
            // deleting the pointer should not delete what it pointed at.
            const done = await PyCmd.call('page.remove', { id: row.id, delete_files: false });
            PyCmd.toast(done.ok ? 'Removed. Your folder is untouched.'
                                : (done.error || 'that would not remove'));
            go('pages');
          },
        }),
      )));
  });
  screen.appendChild(grid);
}

async function Docs(screen) {
  screen.appendChild(head('Guides', 'How PyCmd works, written for Windows.'));
  const guides = [
    ['README.md', 'What PyCmd is', 'The tour: every screen, and what it does.'],
    ['TUTORIAL.md', 'Getting started', 'From a fresh install to a running program.'],
    ['TOOLCHAINS.md', 'Compilers and languages', 'What runs what, and how to install the rest.'],
    ['PLUGINS.md', 'Writing a plugin', 'The whole plugin API, and what changes on Windows.'],
    ['MOBILE.md', 'Coming from the phone', 'What carries over, what does not, and why.'],
    ['FORKING.md', 'Forking PyCmd', 'Building the exe yourself, and where the source is.'],
  ];
  const grid = el('div', { class: 'grid' });
  guides.forEach(([file, title, blurb]) => {
    grid.appendChild(card(
      el('b', { text: title }),
      el('p', { class: 'muted', text: blurb }),
      el('button', {
        class: 'small', text: 'Read',
        onclick: async () => {
          const reply = await fetch('/wdocs/' + file).then((r) => r.ok ? r.text() : '');
          PyCmd.sheet(title, el('pre', {
            class: 'out',
            style: 'max-height:none;white-space:pre-wrap',
            text: reply || 'That guide is not in this build.',
          }));
        },
      }),
    ));
  });
  screen.appendChild(grid);
}

async function System(screen) {
  screen.appendChild(head('System', 'What PyCmd is using, and where.'));
  const reply = await PyCmd.call('system');
  if (!reply.ok) {
    screen.appendChild(el('div', { class: 'empty', text: reply.error || 'nothing to show' }));
    return;
  }
  const store = reply.store || {};

  if (PyCmd.state.update) {
    const update = PyCmd.state.update;
    screen.appendChild(card(
      el('b', { text: 'PyCmd ' + update.version + ' is out' }),
      el('p', { class: 'muted', text: update.notes || '' }),
      el('p', { class: 'muted' },
        'It downloads to your Downloads folder and is checked against its ' +
        'published checksum. Replacing the exe is a step you take yourself — ' +
        'an app that swaps its own exe while you are using it eventually swaps ' +
        'in a broken one.'),
    ));
  }

  screen.appendChild(card(
    el('div', { class: 'row spread' }, el('b', { text: 'PyCmd' }),
      el('span', { class: 'pill on', text: reply.version })),
    el('div', { class: 'muted' }, 'Python ', reply.python),
    el('div', { class: 'muted mono', text: store.root || '' }),
    store.portable ? el('p', { class: 'muted', text: 'Portable: PYCMD_HOME is set, so everything lives beside the exe.' }) : null,
  ));

  const grid = el('div', { class: 'grid' });
  ['workspace', 'site-packages', 'downloads', 'plugins', 'pages', 'music', 'versions', 'cache']
    .forEach((name) => {
      const row = store[name];
      if (!row) return;
      grid.appendChild(card(
        el('div', { class: 'row spread' },
          el('b', { text: name }),
          el('span', { class: 'pill', text: PyCmd.bytes(row.bytes) })),
        el('div', { class: 'muted', text: row.files + ' files' }),
        el('div', { class: 'muted mono', style: 'font-size:11px', text: row.path }),
      ));
    });
  screen.appendChild(grid);
  screen.appendChild(el('p', { class: 'muted' },
    'Free on this drive: ', PyCmd.bytes(store.free_bytes)));
}

async function Log(screen) {
  screen.appendChild(head('Debug log', 'Everything PyCmd has said to itself.'));
  const reply = await PyCmd.call('log');
  const entries = (reply && reply.entries) || [];
  screen.appendChild(el('div', { class: 'row' },
    el('button', { class: 'small', text: 'Refresh', onclick: () => go('log') }),
    el('span', { class: 'muted', text: entries.length + ' entries' })));
  const host = el('div', { class: 'card' });
  if (!entries.length) host.appendChild(el('div', { class: 'empty', text: 'Nothing yet.' }));
  entries.slice(-400).reverse().forEach((entry) => {
    host.appendChild(el('div', { class: 'log-line ' + entry.level },
      el('span', { class: 'lvl', text: entry.level }),
      el('span', { text: entry.message }),
      entry.detail ? el('div', { class: 'det', text: entry.detail.slice(0, 1200) }) : null));
  });
  screen.appendChild(host);
}

window.Screens = {
  console: Console,
  editor: Editor,
  files: Files,
  run: Run,
  toolchains: Toolchains,
  languages: Languages,
  servers: Servers,
  pages: Pages,
  packages: Packages,
  plugins: Plugins,
  docs: Docs,
  android: Android,
  copies: Copies,
  system: System,
  log: Log,
};
