/*
  The Console screen.

  The engine already offered more than the old bar ever asked for. There was a
  `console.completions` handler nothing called at all, no history on the arrow
  keys, and no way to take the output anywhere. `input()` did work - it opened
  a modal sheet - but a dialog over the output is the wrong shape for it: you
  cannot see what the program printed to decide what to answer, which is the
  entire reason it asked.

  So: history on the arrow keys, Tab completion, input() answered in the bar
  you are already typing in with the output still visible behind it, a Stop
  that appears while something is running, and output you can copy or save
  rather than only look at.

  And the birthday. Every line is offered to the host before it is run; almost
  every line comes back "not a secret" and is run normally.
*/

'use strict';

const Con = {
  frame: null,
  queue: [],
  history: [],
  at: -1,          // where the up-arrow has walked to; -1 means "not walking"
  draft: '',       // what was typed before the walk started
  waiting: false,  // a program is asking for a line
  running: false,
  transcript: [],  // kept so the output can be copied or saved
};

const CONSOLE_HISTORY_MAX = 300;

function conReady() {
  try {
    return !!(Con.frame && Con.frame.contentWindow && Con.frame.contentWindow.PyConsole);
  } catch (error) { return false; }
}

function conWrite(stream, text) {
  Con.transcript.push(text);
  if (Con.transcript.length > 6000) Con.transcript.splice(0, 3000);
  if (!conReady()) { Con.queue.push([stream, text]); return; }
  try { Con.frame.contentWindow.PyConsole.append(stream, text); } catch (error) { /* gone */ }
}

// ---------------------------------------------------------------------------

function Console(screen) {
  screen.classList.add('flush');
  const wrap = PyCmd.el('div', { class: 'console-shell' });

  const frame = PyCmd.el('iframe', { class: 'frame', src: '/web/console.html' });
  Con.frame = frame;
  frame.addEventListener('load', () => {
    const pending = Con.queue;
    Con.queue = [];
    pending.forEach(([stream, text]) => conWrite(stream, text));
  });

  const input = PyCmd.el('input', {
    id: 'conInput',
    placeholder: 'Python, or a command like  ls · run app.py · pip install flask',
    spellcheck: 'false', autocomplete: 'off',
  });

  const hint = PyCmd.el('div', { class: 'console-hint', id: 'conHint', hidden: true });

  const bar = PyCmd.el('div', { class: 'console-bar' },
    PyCmd.el('span', { class: 'prompt', id: 'conPrompt', text: '>>>' }),
    input,
    PyCmd.el('button', { class: 'small primary', id: 'conSend', text: 'Run',
                         onclick: () => conSend() }),
    PyCmd.el('button', { class: 'small bad', id: 'conStop', text: 'Stop', hidden: true,
                         onclick: conStop }),
  );

  const tools = PyCmd.el('div', { class: 'toolbar' },
    PyCmd.el('div', { class: 'tgroup' },
      PyCmd.el('button', { class: 'small', text: 'Clear', title: 'Empty the output',
                           onclick: conClear }),
      PyCmd.el('button', {
        class: 'small', text: 'Reset',
        title: 'Throw away every variable and import you have defined',
        onclick: conReset,
      })),
    PyCmd.el('div', { class: 'tgroup' },
      PyCmd.el('button', { class: 'small', text: 'Copy', title: 'Copy all the output',
                           onclick: conCopy }),
      PyCmd.el('button', { class: 'small', text: 'Save', title: 'Write the output to a file',
                           onclick: conSave })),
    PyCmd.el('div', { class: 'tgroup' },
      PyCmd.el('button', { class: 'small', text: 'History', title: 'Everything you have run',
                           onclick: conHistory })),
    PyCmd.el('div', { class: 'tgroup' },
      PyCmd.el('button', { class: 'small', text: 'Android Lab',
                           title: 'Run Android things on this PC',
                           onclick: () => go('android') })),
  );

  input.addEventListener('keydown', conKeys);

  wrap.appendChild(tools);
  wrap.appendChild(frame);
  wrap.appendChild(hint);
  wrap.appendChild(bar);
  screen.appendChild(wrap);

  conDrawBar();
  setTimeout(() => input.focus(), 80);
}

// ---------------------------------------------------------------------------
// Typing
// ---------------------------------------------------------------------------

function conKeys(event) {
  const input = event.target;

  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    conSend();
    return;
  }

  // The arrows walk the history, but only from the ends of the line - so
  // moving the caret through a long line still works normally.
  if (event.key === 'ArrowUp' && input.selectionStart === 0) {
    event.preventDefault();
    conWalk(1);
    return;
  }
  if (event.key === 'ArrowDown' && input.selectionStart === input.value.length) {
    event.preventDefault();
    conWalk(-1);
    return;
  }

  if (event.key === 'Tab') {
    event.preventDefault();
    conComplete();
    return;
  }

  if (event.key === 'Escape') {
    conHint('');
    Con.at = -1;
    return;
  }

  // Anything else means the walk is over and this is a new line being typed.
  if (event.key.length === 1) Con.at = -1;
}

function conWalk(direction) {
  const input = document.getElementById('conInput');
  if (!input || !Con.history.length) return;
  if (Con.at < 0) Con.draft = input.value;

  const next = Con.at + direction;
  if (next < -1) return;
  if (next >= Con.history.length) return;

  Con.at = next;
  input.value = next < 0 ? Con.draft : Con.history[next];
  // Caret to the end, so up-then-type appends rather than prepends.
  setTimeout(() => input.setSelectionRange(input.value.length, input.value.length), 0);
}

async function conComplete() {
  const input = document.getElementById('conInput');
  if (!input || !input.value.trim()) return;
  const reply = await PyCmd.call('console.completions', { text: input.value });
  const items = (reply && reply.items) || [];
  if (!items.length) { conHint('no completions'); return; }
  if (items.length === 1) {
    // One answer means finish the word rather than show a list of one.
    const word = input.value.split(/[\s.(]/).pop();
    input.value = input.value.slice(0, input.value.length - word.length) + items[0];
    conHint('');
    return;
  }
  conHint(items.slice(0, 24).join('   ') + (items.length > 24 ? '   …' : ''));
}

function conHint(text) {
  const node = document.getElementById('conHint');
  if (!node) return;
  node.textContent = text || '';
  node.hidden = !text;
}

// ---------------------------------------------------------------------------
// Sending
// ---------------------------------------------------------------------------

async function conSend() {
  const input = document.getElementById('conInput');
  if (!input) return;
  const text = input.value;
  if (!text.trim() && !Con.waiting) return;
  input.value = '';
  conHint('');
  Con.at = -1;

  // A program is blocked on input(): this line is an answer, not a command.
  if (Con.waiting) {
    conWrite('stdin', text + '\n');
    Con.waiting = false;
    conDrawBar();
    await PyCmd.call('console.stdin', { text });
    return;
  }

  if (Con.history[0] !== text) {
    Con.history.unshift(text);
    if (Con.history.length > CONSOLE_HISTORY_MAX) Con.history.pop();
  }

  // Every line gets offered to the host first. Almost all of them come back
  // "not a secret" and run normally.
  const secret = await PyCmd.call('console.secret', { text });
  if (secret && secret.secret) { conCelebrate(secret); return; }

  conWrite('stdin', '>>> ' + text + '\n');
  Con.running = true;
  conDrawBar();
  const reply = await PyCmd.call('console.run', { text });
  if (!reply.ok) {
    conWrite('stderr', (reply.error || 'that did not run') + '\n');
    Con.running = false;
    conDrawBar();
  }
}

async function conStop() {
  await PyCmd.call('console.stop', {});
  Con.running = false;
  Con.waiting = false;
  conDrawBar();
  PyCmd.toast('Stopped.');
}

async function conReset() {
  await PyCmd.call('console.reset', {});
  conWrite('stdout', '[PyCmd] the namespace is empty again.\n');
}

function conClear() {
  Con.transcript = [];
  if (conReady()) {
    try { Con.frame.contentWindow.PyConsole.clear(); } catch (error) { /* gone */ }
  }
}

function conDrawBar() {
  const prompt = document.getElementById('conPrompt');
  const send = document.getElementById('conSend');
  const stop = document.getElementById('conStop');
  const input = document.getElementById('conInput');
  if (!prompt || !send || !stop || !input) return;

  if (Con.waiting) {
    prompt.textContent = '?';
    prompt.className = 'prompt waiting';
    input.placeholder = 'Waiting for input() — type a line and press Enter';
    send.textContent = 'Send';
  } else {
    prompt.textContent = '>>>';
    prompt.className = 'prompt';
    input.placeholder = 'Python, or a command like  ls · run app.py · pip install flask';
    send.textContent = 'Run';
  }
  stop.hidden = !(Con.running || Con.waiting);
}

// ---------------------------------------------------------------------------
// Taking the output away
// ---------------------------------------------------------------------------

async function conCopy() {
  const text = Con.transcript.join('');
  if (!text) { PyCmd.toast('There is no output yet.'); return; }
  try {
    await navigator.clipboard.writeText(text);
    PyCmd.toast('Output copied.');
  } catch (error) {
    // Clipboard permission can be refused; a selectable box still works.
    PyCmd.sheet('Output', PyCmd.el('textarea', {
      class: 'plain', readonly: 'readonly', value: text, rows: '18',
    }));
  }
}

function conSave() {
  const text = Con.transcript.join('');
  if (!text) { PyCmd.toast('There is no output yet.'); return; }
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
  const name = PyCmd.el('input', { value: 'console-' + stamp + '.txt' });
  const save = async () => {
    const reply = await PyCmd.call('file.write', { path: name.value.trim(), text });
    if (!reply.ok) { PyCmd.toast(reply.error || 'could not save'); return; }
    PyCmd.closeSheet();
    PyCmd.toast('Saved to the workspace.');
  };
  PyCmd.sheet('Save the output', PyCmd.el('div', {},
    PyCmd.el('label', { text: 'File name' }), name,
    PyCmd.el('div', { class: 'row' },
      PyCmd.el('button', { class: 'primary', text: 'Save', onclick: save }))));
}

function conHistory() {
  if (!Con.history.length) {
    PyCmd.toast('Nothing has been run yet.');
    return;
  }
  const list = PyCmd.el('div', { class: 'list' });
  Con.history.forEach((line) => {
    list.appendChild(PyCmd.el('button', {
      class: 'row-item mono', text: line,
      onclick: () => {
        const input = document.getElementById('conInput');
        if (input) { input.value = line; input.focus(); }
        PyCmd.closeSheet();
      },
    }));
  });
  PyCmd.sheet('Command history', list);
}

// ---------------------------------------------------------------------------
// The birthday
// ---------------------------------------------------------------------------

function conCelebrate(secret) {
  conWrite('stdout', '\n' + secret.message + '\n\n');
  PyCmd.sheet(secret.title, PyCmd.el('div', {},
    PyCmd.el('p', { text: secret.message, style: 'white-space:pre-wrap' }),
    PyCmd.el('div', { class: 'row' },
      PyCmd.el('button', {
        class: 'primary', text: 'Set this machine up now',
        onclick: () => { PyCmd.closeSheet(); go('toolchains'); },
      }),
      PyCmd.el('button', { text: 'Later', onclick: PyCmd.closeSheet }))));
  if (secret.already) {
    PyCmd.toast('Already unlocked — it is on the Toolchains screen.');
  }
}

// ---------------------------------------------------------------------------
// Events from the engine
// ---------------------------------------------------------------------------

function conWireEvents() {
  PyCmd.on('output', (event) => {
    if ((event.channel || 'console') !== 'console') return;
    conWrite(event.stream || 'stdout', event.text || '');
  });

  PyCmd.on('input-wanted', () => {
    Con.waiting = true;
    Con.running = false;
    conDrawBar();
    conWrite('stdout', '');
    const input = document.getElementById('conInput');
    if (input) input.focus();
  });

  PyCmd.on('finished', () => {
    Con.running = false;
    Con.waiting = false;
    conDrawBar();
  });
}
