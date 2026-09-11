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
let filesSource = 'workspace';   // 'workspace' or 'pc'

function filesSwitch() {
  const pick = (id, label, hint) => el('button', {
    class: 'small' + (filesSource === id ? ' primary' : ''),
    text: label, title: hint,
    onclick: () => { filesSource = id; go('files'); },
  });
  return el('div', { class: 'row wrap', style: 'margin-bottom:10px' },
    pick('workspace', 'Workspace', 'Where PyCmd keeps projects'),
    pick('pc', 'This PC', 'Every drive and folder you can reach'),
    el('span', { class: 'muted', text: filesSource === 'workspace'
      ? 'What the console\u2019s cd and run mean.'
      : 'Real files, in place. Editing one edits the file itself.' }));
}

async function Files(screen) {
  screen.appendChild(head('Files',
    'The workspace is where new projects land. This PC is everything else — ' +
    'PyCmd opens, edits, runs and organises files wherever they already live.'));
  screen.appendChild(filesSwitch());

  if (filesSource === 'pc') return DiskFiles(screen);

  const reply = await PyCmd.call('files', { path: filesAt });
  if (!reply.ok) {
    filesAt = '';
    screen.appendChild(el('div', { class: 'empty', text: reply.error }));
    return;
  }

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
      openInEditor(entry.path, false);
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
        onclick: () => runPath(entry.path, entry.name),
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

/*
 * One way to open a file, and it is the editor.
 *
 * There used to be two: the Editor tab, with tabs, a toolbar, find and
 * replace, go-to-line and a status bar - and a textarea in a sheet that
 * appeared when you clicked a file in the list. The second one existed
 * because clicking a row had to do *something* and a sheet was the quickest
 * thing to write. It had none of the editor: no highlighting, no undo worth
 * the name, no second file open beside it. Clicking a file and being given
 * the worse of the two editors is a strange thing for an app to do, so it
 * no longer does it.
 *
 * `onDisk` says which half of the world the path belongs to: a
 * workspace-relative path goes through `file.read`/`file.write`, an absolute
 * one anywhere on the PC through `disk.read`/`disk.write`. The editor keeps
 * the flag on the open file so saving goes back the way it came.
 */
async function openInEditor(path, onDisk) {
  const done = await edOpenPath(path, !!onDisk);
  if (done) go('editor');
}

/*
 * Running anything, from anywhere, ends up on the Console.
 *
 * The program may ask a question. `input()` is the first thing a beginner
 * writes after `print`, and PyCmd used to start the program, say "output is
 * on the Console" in a toast that fades after three seconds, and leave you
 * looking at the file list while a prompt waited on a screen you were not
 * on. The console is where the program is; that is where Run goes.
 */
async function runPath(path, name, toolchain) {
  go('console');
  const reply = await PyCmd.call('run.file', { path, toolchain: toolchain || '' });
  if (!reply.ok) PyCmd.toast(reply.error || 'that would not run');
  else PyCmd.toast('Running ' + (name || diskName(path)));
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

/*
 * Run: a list of what can be run, not a box to type a path into.
 *
 * The old screen asked for "hello.go" and a toolchain. To use it you had to
 * already know the file's name, its extension and where it sat relative to
 * the workspace - three things the app knows perfectly well and you should
 * not have to retype. Worse, a typo gave you "that did not start", which
 * tells you nothing about which of the three you got wrong.
 *
 * So PyCmd walks the folder and shows you what is runnable. Pick one.
 */

let runRoot = '';        // '' means the workspace
let runFilter = '';
let runChain = '';
let runFound = null;     // the last answer, kept so typing in the filter is instant

async function Run(screen) {
  screen.appendChild(head('Run a file',
    'Everything under here that PyCmd knows how to run. Pick one — it starts on ' +
    'the Console, where it can ask you things.'));

  const where = el('div', { class: 'row wrap', style: 'margin-bottom:8px' },
    el('button', {
      class: 'small' + (runRoot ? '' : ' primary'), text: 'Workspace',
      onclick: () => { runRoot = ''; runFound = null; go('run'); },
    }),
    runRoot ? el('span', { class: 'pill mono', text: runRoot }) : null,
    el('button', {
      class: 'small', text: 'Look somewhere else…', onclick: pickRoot,
    }),
    el('button', {
      class: 'small', text: 'Look again',
      onclick: () => { runFound = null; go('run'); },
    }),
  );
  screen.appendChild(where);

  const filter = el('input', { placeholder: 'Filter by name or language', spellcheck: 'false' });
  filter.value = runFilter;
  const chain = el('select', {});
  chain.appendChild(el('option', { value: '', text: 'Best available toolchain' }));
  (PyCmd.state.toolchains || []).filter((c) => c.installed).forEach((c) => {
    chain.appendChild(el('option', { value: c.id, text: c.name + ' — ' + c.languages.join(', ') }));
  });
  chain.value = runChain;
  chain.addEventListener('change', () => { runChain = chain.value; });

  screen.appendChild(card(
    el('div', { class: 'row wrap' },
      el('label', { class: 'field', style: 'flex:2 1 260px' },
        el('span', { text: 'Which file' }), filter),
      el('label', { class: 'field', style: 'flex:1 1 220px' },
        el('span', { text: 'Run it with' }), chain)),
    el('div', { class: 'row' },
      el('button', { class: 'small', text: 'Stop whatever is running', onclick: () => PyCmd.call('run.stop') }),
      el('span', { class: 'muted', text: 'Output, and any question it asks, are on the Console.' })),
  ));

  const list = el('div', {});
  screen.appendChild(list);

  const note = el('p', { class: 'muted' });
  screen.appendChild(note);

  filter.addEventListener('input', () => { runFilter = filter.value; draw(); });

  if (!runFound || runFound.asked !== runRoot) {
    list.appendChild(el('div', { class: 'empty', text: 'Looking…' }));
    const reply = await PyCmd.call('disk.runnable', { root: runRoot });
    if (!reply.ok) {
      PyCmd.clear(list);
      list.appendChild(el('div', { class: 'empty', text: reply.error || 'that folder would not open' }));
      return;
    }
    // A record of its own rather than the reply with fields bolted on: the
    // first draft set `runFound.root` to the folder that was *asked for* and
    // then read `reply.root` for the one that was *found* - but runFound and
    // reply were the same object, so the screen said "nothing runnable under
    // (empty)" instead of naming the folder.
    runFound = {
      asked: runRoot,
      root: reply.root,
      files: reply.files || [],
      truncated: !!reply.truncated,
    };
  }
  draw();

  function draw() {
    PyCmd.clear(list);
    const wanted = runFilter.trim().toLowerCase();
    const rows = (runFound.files || []).filter((row) => !wanted
      || row.name.toLowerCase().includes(wanted)
      || (row.folder || '').toLowerCase().includes(wanted)
      || (row.language || '').toLowerCase().includes(wanted));

    if (!(runFound.files || []).length) {
      list.appendChild(el('div', { class: 'empty',
        text: 'Nothing runnable under ' + runFound.root + '. Make a file in the '
            + 'Editor, or point this at a folder that has one.' }));
      return;
    }
    if (!rows.length) {
      list.appendChild(el('div', { class: 'empty', text: 'Nothing matches “' + runFilter + '”.' }));
      return;
    }

    const box = el('div', { class: 'card', style: 'padding:4px 6px' });
    rows.slice(0, 300).forEach((row) => {
      box.appendChild(el('div', {
        class: 'row', style: 'padding:7px 9px;border-bottom:1px solid #182231',
      },
        el('button', {
          class: 'small',
          style: 'flex:1 1 auto;text-align:left;border-color:transparent;background:none',
          onclick: () => runPath(row.path, row.name, runChain),
        },
          el('span', { text: row.name }),
          row.folder ? el('span', { class: 'muted', text: '  in ' + row.folder }) : null),
        el('span', { class: 'pill', text: row.language }),
        el('span', { class: 'muted', text: PyCmd.bytes(row.bytes) }),
        el('button', {
          class: 'small', text: 'Edit',
          onclick: () => openInEditor(row.path, true),
        }),
        el('button', {
          class: 'small primary', text: 'Run',
          onclick: () => runPath(row.path, row.name, runChain),
        }),
      ));
    });
    list.appendChild(box);

    const stats = PyCmd.state.languageStats || {};
    note.textContent = rows.length + ' of ' + runFound.files.length + ' shown'
      + (runFound.truncated ? ' · the search stopped at 400 files' : '')
      + ' · ' + (stats.runnable || 0) + ' of ' + (stats.total || 0)
      + ' file types can be run here.';
  }
}

function pickRoot() {
  const path = el('input', {
    placeholder: 'C:\\Users\\you\\projects', spellcheck: 'false',
  });
  path.value = runRoot;
  PyCmd.sheet('Look for runnable files in', el('div', {},
    el('p', { class: 'muted',
      text: 'Any folder on this PC. Files screen → This PC → “Run something here” '
          + 'fills this in for you.' }),
    el('label', { class: 'field' }, el('span', { text: 'Folder' }), path),
    el('button', {
      class: 'small primary', text: 'Look there',
      onclick: () => {
        runRoot = path.value.trim();
        runFound = null;
        PyCmd.closeSheet();
        go('run');
      },
    })));
  setTimeout(() => path.focus(), 60);
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
              // An install streams to the console and can ask for elevation.
              // Watching it happen beats a toast that fades in three seconds.
              go('console');
              PyCmd.toast('Installing ' + row.name + '…');
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
  if (reply.ok) {
    PyCmd.state.plugins = reply;
    // The rail is drawn before this screen runs, so a plugin installed or
    // removed a moment ago would otherwise keep or lack its tab until the
    // next time something else redrew the rail.
    drawTabs();
  }
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
                    // It has a tab of its own in the rail now; this goes there
                    // rather than opening a second, worse copy in a sheet.
                    onclick: () => go('panel:' + plugin.id),
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
async function panelFrame(plugin, panelFile, style, onClose) {
  const reply = await PyCmd.call('plugin.panel', { id: plugin.id, panel: panelFile || '' });
  if (!reply.ok || !reply.html) {
    PyCmd.toast((reply && reply.error) || 'that panel would not build');
    return null;
  }

  const frame = el('iframe', {
    style: style || 'width:100%;height:70vh;border:0;border-radius:10px;background:var(--bg)',
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
      close: () => (onClose ? onClose() : PyCmd.closeSheet()),
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

  return frame;
}

/* The panel as a screen: the rail already says which plugin it is, so the
   frame simply gets the whole middle of the window. `close()` from inside the
   panel used to shut a sheet; with no sheet to shut it goes back to the
   Plugins tab, which is the same promise kept a different way. */
async function drawPanelScreen(screen, plugin) {
  screen.appendChild(el('div', { class: 'row spread', style: 'margin-bottom:8px' },
    el('div', {},
      el('b', { text: plugin.name || plugin.id }),
      el('span', { class: 'muted', text: '  ' + (plugin.version ? 'v' + plugin.version : '') })),
    el('div', { class: 'row' },
      el('button', { class: 'small', text: 'Settings', onclick: () => openSettings(plugin) }),
      el('button', { class: 'small', text: 'Reload', onclick: () => go('panel:' + plugin.id) }),
      el('button', { class: 'small', text: 'Manage plugins', onclick: () => go('plugins') }))));

  const holder = el('div', { style: 'flex:1 1 auto' });
  screen.appendChild(holder);
  holder.appendChild(el('div', { class: 'empty', text: 'Loading ' + (plugin.name || plugin.id) + '…' }));

  const frame = await panelFrame(plugin, plugin.panel,
    'width:100%;height:calc(100vh - 210px);min-height:360px;border:0;'
    + 'border-radius:12px;background:var(--bg);border:1px solid var(--line)',
    () => go('plugins'));
  PyCmd.clear(holder);
  if (!frame) {
    holder.appendChild(el('div', { class: 'empty',
      text: 'That panel would not build. The debug log has the reason.' }));
    return;
  }
  holder.appendChild(frame);
}
window.drawPanelScreen = drawPanelScreen;

// Opening a panel in a sheet is still how the Plugins tab previews one.
async function openPanel(plugin, panelFile) {
  const frame = await panelFrame(plugin, panelFile);
  if (frame) PyCmd.sheet(plugin.name || plugin.id, frame);
}

/* A plugin pushing to its own panel, the way api.send does on the phone.
   The panels are written into about:blank frames rather than srcdoc ones, so
   looking for `iframe[srcdoc]` found none of them and every message a plugin
   sent to its own panel went nowhere. Ask the frames themselves. */
PyCmd.on('plugin-message', (event) => {
  document.querySelectorAll('iframe').forEach((frame) => {
    let view = null;
    try { view = frame.contentWindow; } catch (error) { return; }
    if (view && view.__pycmd_panel && view.__pycmd_message) {
      view.__pycmd_message(event.body);
    }
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
          go('console');
          PyCmd.toast('Installing ' + asked + '…');
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

// ---------------------------------------------------------------------------
// This PC — the whole disk, not just the workspace
// ---------------------------------------------------------------------------

/*
 * The phone's Files screen is a workspace and two buttons: bring a file in,
 * send a file out. It has to be. Android hands an app a private folder and a
 * document picker, and everything else on the device is somebody else's.
 *
 * Windows is not like that. The disk is one namespace and the person using
 * PyCmd already owns it - Notepad can open any file they can, and so can
 * `python` at a prompt. Copying a file *into* PyCmd to edit it, and then
 * exporting it back out, would be a ceremony invented to work around a
 * restriction that does not exist here. So this screen browses the disk:
 * drives, the folders people actually keep things in, and every file in them.
 *
 * The workspace does not go away. It is still where new projects land and
 * what `cd` and `run` mean in the console. It is now one place among many
 * rather than the only one PyCmd can see.
 */

let diskAt = '';
let diskHidden = false;
let diskClip = null;   // { path, name, op: 'copy' | 'move' }

async function diskReveal(path) {
  const done = await PyCmd.call('disk.reveal', { path });
  if (!done.ok) PyCmd.toast(done.error || 'Explorer would not open');
}

function diskJoin(folder, name) {
  const clean = String(folder).replace(/[\\/]+$/, '');
  // Windows accepts both, but echoing back the separator the path already
  // uses keeps `C:\\Users\\you\\thing.py` from becoming
  // `C:\\Users\\you/thing.py` in every message that shows it.
  const slash = clean.includes('\\') || /^[A-Za-z]:$/.test(clean) ? '\\' : '/';
  return clean + slash + name;
}

function diskName(path) {
  const parts = String(path).split(/[\\/]/).filter(Boolean);
  return parts.length ? parts[parts.length - 1] : path;
}

async function DiskFiles(screen) {
  const reply = await PyCmd.call('disk', { path: diskAt, hidden: diskHidden });
  if (!reply.ok) {
    PyCmd.toast(reply.error || 'that folder would not open');
    diskAt = '';
    return diskRoot(screen, await PyCmd.call('disk', { path: '' }));
  }
  if (reply.atRoot) return diskRoot(screen, reply);

  // Where you are, one button per step, plus the way back out to the drives.
  const crumbs = el('div', { class: 'row wrap', style: 'margin-bottom:8px' },
    el('button', { class: 'small', text: 'This PC', onclick: () => { diskAt = ''; go('files'); } }));
  (reply.crumbs || []).forEach((crumb, index, all) => {
    crumbs.appendChild(el('span', { class: 'muted', text: '›' }));
    crumbs.appendChild(el('button', {
      class: 'small' + (index === all.length - 1 ? ' primary' : ''),
      text: crumb.name,
      onclick: () => { diskAt = crumb.path; go('files'); },
    }));
  });
  screen.appendChild(crumbs);

  // A folder Windows owns is read-only here, so the buttons that would write
  // into it are not drawn. Offering a button that can only fail is worse than
  // not offering it, and the line below says why it is missing.
  const canWrite = reply.writable !== false;
  const tools = el('div', { class: 'row wrap', style: 'margin-bottom:10px' },
    reply.parent ? el('button', {
      class: 'small', text: '↑ Up',
      onclick: () => { diskAt = reply.parent; go('files'); },
    }) : null,
    canWrite ? el('button', { class: 'small primary', text: '+ New file', onclick: () => diskNewFile(reply.path) }) : null,
    canWrite ? el('button', { class: 'small', text: '+ New folder', onclick: () => diskNewFolder(reply.path) }) : null,
    (canWrite && diskClip) ? el('button', {
      class: 'small primary',
      text: (diskClip.op === 'move' ? 'Move ' : 'Paste ') + diskClip.name + ' here',
      onclick: () => diskPaste(reply.path),
    }) : null,
    diskClip ? el('button', {
      class: 'small', text: 'Cancel the ' + (diskClip.op === 'move' ? 'move' : 'copy'),
      onclick: () => { diskClip = null; go('files'); },
    }) : null,
    el('button', { class: 'small', text: 'Open in Explorer', onclick: () => diskReveal(reply.path) }),
    el('button', {
      class: 'small', text: diskHidden ? 'Hide hidden' : 'Show hidden',
      onclick: () => { diskHidden = !diskHidden; go('files'); },
    }),
    el('button', {
      class: 'small', text: 'Run something here',
      onclick: () => { runRoot = reply.path; go('run'); },
    }),
    el('span', { class: 'muted', text: reply.folders + ' folders · ' + reply.files + ' files' }),
  );
  screen.appendChild(tools);

  if (!reply.writable) {
    screen.appendChild(el('p', { class: 'muted',
      text: 'This folder is Windows’ own. PyCmd will read it, but it will not write here.' }));
  }

  if (!reply.entries.length) {
    screen.appendChild(el('div', { class: 'empty', text: 'Nothing in here.' }));
    return;
  }

  const list = el('div', { class: 'card', style: 'padding:4px 6px' });
  reply.entries.forEach((entry) => {
    list.appendChild(diskRow(entry));
  });
  screen.appendChild(list);

  if (reply.truncated) {
    screen.appendChild(el('p', { class: 'muted',
      text: 'Only the first 2000 entries are shown — this folder has more.' }));
  }
  screen.appendChild(el('p', { class: 'muted mono', style: 'font-size:11px', text: reply.path }));
}

function diskRow(entry) {
  const open = () => {
    if (entry.folder) { diskAt = entry.path; go('files'); return; }
    openInEditor(entry.path, true);
  };
  return el('div', {
    class: 'row',
    style: 'padding:7px 9px;border-bottom:1px solid #182231',
  },
    el('span', { style: 'width:20px;text-align:center', text: entry.folder ? '▸' : '·' }),
    el('button', {
      class: 'small',
      style: 'flex:1 1 auto;text-align:left;border-color:transparent;background:none',
      text: entry.name, onclick: open,
    }),
    entry.language && entry.language !== 'Plain text'
      ? el('span', { class: 'pill', text: entry.language }) : null,
    entry.folder ? null : el('span', { class: 'muted', text: PyCmd.bytes(entry.bytes) }),
    entry.runs ? el('button', {
      class: 'small primary', text: 'Run',
      onclick: () => runPath(entry.path, entry.name),
    }) : null,
    el('button', { class: 'small', text: '⋯', title: 'More', onclick: () => diskMenu(entry) }),
  );
}

function diskMenu(entry) {
  const act = (label, kind, what) => el('button', { class: 'small ' + kind, text: label, onclick: what });
  PyCmd.sheet(entry.name, el('div', {},
    el('p', { class: 'muted mono', style: 'font-size:11px', text: entry.path }),
    el('div', { class: 'row wrap', style: 'margin-top:10px' },
      entry.folder ? null : act('Edit', 'primary', () => { PyCmd.closeSheet(); openInEditor(entry.path, true); }),
      act('Open with Windows', '', async () => {
        const done = await PyCmd.call('disk.open', { path: entry.path });
        PyCmd.closeSheet();
        if (!done.ok) PyCmd.toast(done.error || 'Windows would not open that');
      }),
      act('Show in Explorer', '', () => { PyCmd.closeSheet(); diskReveal(entry.path); }),
      act('Copy', '', () => {
        diskClip = { path: entry.path, name: entry.name, op: 'copy' };
        PyCmd.closeSheet();
        PyCmd.toast('Copied. Open a folder and press Paste.');
        go('files');
      }),
      act('Cut', '', () => {
        diskClip = { path: entry.path, name: entry.name, op: 'move' };
        PyCmd.closeSheet();
        PyCmd.toast('Cut. Open a folder and press Move.');
        go('files');
      }),
      entry.folder ? null : act('Copy into the workspace', '', async () => {
        const done = await PyCmd.call('file.import', { source: entry.path, into: '' });
        PyCmd.closeSheet();
        PyCmd.toast(done.ok ? (done.name + ' is in the workspace') : (done.error || 'that would not copy'));
      }),
      act('Rename', '', () => { PyCmd.closeSheet(); diskRename(entry); }),
      act('Delete', 'danger', () => { PyCmd.closeSheet(); diskDelete(entry); }),
    )));
}

async function diskPaste(into) {
  if (!diskClip) return;
  const name = diskClip.op === 'move' ? 'disk.move' : 'disk.copy';
  const done = await PyCmd.call(name, { source: diskClip.path, into });
  if (!done.ok) { PyCmd.toast(done.error || 'that would not work'); return; }
  PyCmd.toast(diskClip.name + (diskClip.op === 'move' ? ' moved' : ' copied'));
  diskClip = null;
  go('files');
}

function diskRename(entry) {
  const name = el('input', { spellcheck: 'false' });
  name.value = entry.name;
  PyCmd.sheet('Rename', el('div', {},
    el('label', { class: 'field' }, el('span', { text: 'New name' }), name),
    el('button', {
      class: 'small primary', text: 'Rename',
      onclick: async () => {
        const done = await PyCmd.call('disk.rename', { path: entry.path, name: name.value.trim() });
        if (done.ok) { PyCmd.closeSheet(); go('files'); }
        else PyCmd.toast(done.error || 'that would not rename');
      },
    })));
  setTimeout(() => name.focus(), 60);
}

function diskDelete(entry) {
  // A shortcut to a folder is not the folder. Saying "and everything in it"
  // about a link would be frightening and wrong: only the link goes.
  const what = entry.link
    ? 'This is a link. Deleting it removes the link — whatever it points at '
      + 'stays where it is.'
    : entry.folder
      ? 'This is a real folder on your disk, not a copy inside PyCmd. It and '
        + 'everything in it go, and they do not go to the Recycle Bin.'
      : 'This is a real file on your disk. It does not go to the Recycle Bin.';
  PyCmd.sheet('Delete ' + entry.name + '?', el('div', {},
    el('p', { class: 'muted', text: what }),
    el('p', { class: 'muted mono', style: 'font-size:11px', text: entry.path }),
    el('div', { class: 'row', style: 'margin-top:12px' },
      el('button', {
        class: 'small danger', text: 'Delete it',
        onclick: async () => {
          const done = await PyCmd.call('disk.remove',
            { path: entry.path, recursive: !!entry.folder && !entry.link });
          if (done.ok) { PyCmd.closeSheet(); go('files'); }
          else PyCmd.toast(done.error || 'that would not delete');
        },
      }),
      el('button', { class: 'small', text: 'Keep it', onclick: PyCmd.closeSheet }))));
}

function diskNewFile(where) {
  const name = el('input', { placeholder: 'notes.md', spellcheck: 'false' });
  const pick = el('select', {});
  pick.appendChild(el('option', { value: '', text: 'Empty file' }));
  (PyCmd.state.languages || [])
    .filter((row) => row.creatable !== false && row.mode !== 'media')
    .forEach((row) => pick.appendChild(
      el('option', { value: row.id, text: row.name + '  (' + row.extension + ')' })));
  pick.addEventListener('change', () => {
    const row = (PyCmd.state.languages || []).find((l) => l.id === pick.value);
    if (row && !name.value.includes('.')) name.value = (name.value || 'untitled') + row.extension;
  });

  PyCmd.sheet('A new file', el('div', {},
    el('p', { class: 'muted mono', style: 'font-size:11px', text: where }),
    el('label', { class: 'field' }, el('span', { text: 'Name' }), name),
    el('label', { class: 'field' }, el('span', { text: 'Start it as' }), pick),
    el('button', {
      class: 'small primary', text: 'Create',
      onclick: async () => {
        const wanted = name.value.trim();
        if (!wanted) return PyCmd.toast('It needs a name.');
        const row = (PyCmd.state.languages || []).find((l) => l.id === pick.value);
        const done = await PyCmd.call('disk.write', {
          path: diskJoin(where, wanted), text: (row && row.template) || '',
        });
        if (done.ok) { PyCmd.closeSheet(); go('files'); }
        else PyCmd.toast(done.error || 'that would not work');
      },
    })));
  setTimeout(() => name.focus(), 60);
}

function diskNewFolder(where) {
  const name = el('input', { placeholder: 'my-project', spellcheck: 'false' });
  PyCmd.sheet('A new folder', el('div', {},
    el('p', { class: 'muted mono', style: 'font-size:11px', text: where }),
    el('label', { class: 'field' }, el('span', { text: 'Name' }), name),
    el('button', {
      class: 'small primary', text: 'Create',
      onclick: async () => {
        const wanted = name.value.trim();
        if (!wanted) return PyCmd.toast('It needs a name.');
        const done = await PyCmd.call('disk.folder', { path: diskJoin(where, wanted) });
        if (done.ok) { PyCmd.closeSheet(); go('files'); }
        else PyCmd.toast(done.error || 'that would not work');
      },
    })));
  setTimeout(() => name.focus(), 60);
}

function diskRoot(screen, reply) {
  const places = reply.places || [];
  if (places.length) {
    screen.appendChild(el('h2', { text: 'Your folders' }));
    const grid = el('div', { class: 'grid' });
    places.forEach((place) => {
      grid.appendChild(el('button', {
        class: 'card', style: 'text-align:left;cursor:pointer',
        onclick: () => { diskAt = place.path; go('files'); },
      },
        el('b', { text: place.name }),
        el('div', { class: 'muted mono', style: 'font-size:11px', text: place.path })));
    });
    screen.appendChild(grid);
  }

  screen.appendChild(el('h2', { text: 'Drives' }));
  const drives = el('div', { class: 'grid' });
  (reply.drives || []).forEach((drive) => {
    const used = drive.total ? Math.round(((drive.total - drive.free) / drive.total) * 100) : 0;
    drives.appendChild(el('button', {
      class: 'card', style: 'text-align:left;cursor:pointer',
      onclick: () => { if (drive.ready) { diskAt = drive.path; go('files'); } },
    },
      el('b', { text: drive.name }),
      el('div', { class: 'muted', text: drive.ready
        ? PyCmd.bytes(drive.free) + ' free of ' + PyCmd.bytes(drive.total) + ' · ' + used + '% used'
        : 'not ready' }),
      // Green at 94% full reads as "fine". The bar says how full it is,
      // so it should look like it.
      drive.ready ? el('div', { class: 'progress' }, el('div', {
        class: 'fill',
        style: 'width:' + used + '%;background:'
          + (used >= 90 ? 'var(--bad)' : used >= 75 ? 'var(--warn)' : 'var(--good)'),
      })) : null));
  });
  screen.appendChild(drives);
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
