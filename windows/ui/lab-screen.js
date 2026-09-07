/*
  Android Lab, and the unattended setup run.

  Both are long jobs that stream, so both are drawn the same way: a plan you
  agree to before anything downloads, a log while it runs, and a report after.
  Neither blocks the rest of the app - a spinner over an hour is not a feature.
*/

'use strict';

let labTimer = 0;
let setupTimer = 0;

function labStopPolling() {
  clearInterval(labTimer); labTimer = 0;
  clearInterval(setupTimer); setupTimer = 0;
}

// ---------------------------------------------------------------------------
// Android Lab
// ---------------------------------------------------------------------------

async function Android(screen) {
  const plan = await PyCmd.call('android.plan', {});
  const now = await PyCmd.call('android', {});

  screen.appendChild(head('Android Lab',
    'A real Android device on this PC, with PyCmd Android on it.'));

  // The honest paragraph goes at the top, not in a footnote. A button that
  // starts a three-gigabyte download has to say so before it is pressed.
  screen.appendChild(PyCmd.el('div', { class: 'card note' },
    PyCmd.el('p', { text: plan.honest })));

  const d = plan.device || {};
  screen.appendChild(PyCmd.el('div', { class: 'card' },
    PyCmd.el('h2', { text: 'The machine it builds' }),
    PyCmd.el('div', { class: 'facts' },
      fact('Name', d.name),
      fact('Memory', (d.ramMb / 1024) + ' GB'),
      fact('Storage', (d.storageMb / 1024) + ' GB'),
      fact('App heap', d.heapMb + ' MB'),
      fact('Architecture', d.arch + ' — runs on your CPU, not emulated'),
      fact('Android', '14, with Google APIs'))));

  const steps = PyCmd.el('div', { class: 'card' },
    PyCmd.el('h2', { text: 'What has to happen' }),
    PyCmd.el('p', { class: 'muted', text: plan.download }));
  (plan.steps || []).forEach((step, index) => {
    steps.appendChild(PyCmd.el('div', { class: 'step' },
      PyCmd.el('span', { class: 'n', text: String(index + 1) }),
      PyCmd.el('div', { class: 'grow' },
        PyCmd.el('div', { text: step.what }),
        PyCmd.el('div', { class: 'muted small-text', text: step.why }),
        PyCmd.el('code', { class: 'muted', text: step.how })),
      PyCmd.el('span', { class: 'muted', text: step.size })));
  });
  screen.appendChild(steps);

  const status = PyCmd.el('div', { class: 'card' });
  const log = PyCmd.el('pre', { class: 'out mono', id: 'labLog', hidden: true });

  function drawStatus(state) {
    PyCmd.clear(status);
    status.appendChild(PyCmd.el('h2', { text: 'Right now' }));
    status.appendChild(PyCmd.el('div', { class: 'facts' },
      fact('Android SDK', state.sdk || 'not installed'),
      fact('Tools missing', (state.missing || []).join(', ') || 'none'),
      fact('Our device', state.hasOurs ? 'created' : 'not created yet'),
      fact('Running', (state.running || []).join(', ') || 'nothing')));

    const row = PyCmd.el('div', { class: 'row' });
    row.appendChild(PyCmd.el('button', {
      class: 'primary',
      text: state.hasOurs ? 'Start the device' : 'Set it up and start it',
      onclick: labStart,
    }));
    if ((state.running || []).length) {
      row.appendChild(PyCmd.el('button', {
        text: 'Shut it down',
        onclick: async () => {
          await PyCmd.call('android.stop', {});
          PyCmd.toast('Shutting down.');
          go('android');
        },
      }));
    }
    status.appendChild(row);
  }

  drawStatus(now);
  screen.appendChild(status);
  screen.appendChild(log);

  labPoll();
}

async function labStart() {
  const started = await PyCmd.call('android.start', {});
  if (!started.ok) { PyCmd.toast(started.error || 'it is already going'); return; }
  const log = document.getElementById('labLog');
  if (log) { log.hidden = false; log.textContent = ''; }
  PyCmd.toast('Started. This takes a while the first time.');
  labPoll();
}

function labPoll() {
  clearInterval(labTimer);
  labTimer = setInterval(async () => {
    if (PyCmd.state.tab !== 'android') { clearInterval(labTimer); return; }
    const reply = await PyCmd.call('android.job', {});
    const log = document.getElementById('labLog');
    if (!log) return;
    const lines = reply.lines || [];
    if (lines.length) {
      log.hidden = false;
      log.textContent += lines.join('');
      log.scrollTop = log.scrollHeight;
    }
    const job = reply.job || {};
    if (job.everStarted && !job.running) {
      clearInterval(labTimer);
      if (job.ok) PyCmd.toast('Android Lab is ready.');
      else if (job.error) PyCmd.toast(job.error);
    }
  }, 1500);
}

// ---------------------------------------------------------------------------
// Setting the machine up for every language
// ---------------------------------------------------------------------------

/** Drawn onto the Toolchains screen once the birthday has been found. */
async function setupPanel(screen) {
  const unlocked = await PyCmd.call('secrets', {});
  if (!unlocked.ok || !(unlocked.unlocked || {})['one-month']) return;

  const card = PyCmd.el('div', { class: 'card gift' },
    PyCmd.el('h2', { text: '🎁  Set this machine up' }),
    PyCmd.el('p', {
      text: 'Every language PyCmd knows, installed for you. It puts a package '
          + 'manager in place if there is none, works smallest-first so you '
          + 'get a usable machine early, and keeps going when one of them '
          + 'will not play.',
    }));

  const bar = PyCmd.el('div', { class: 'progress', hidden: true, id: 'setupBar' },
    PyCmd.el('div', { class: 'fill', id: 'setupFill' }));
  const said = PyCmd.el('div', { class: 'muted', id: 'setupSaid' });
  const log = PyCmd.el('pre', { class: 'out mono', id: 'setupLog', hidden: true });

  card.appendChild(PyCmd.el('div', { class: 'row' },
    PyCmd.el('button', {
      class: 'primary', id: 'setupGo', text: 'Set this machine up',
      onclick: async () => {
        const started = await PyCmd.call('setup.start', { onlyMissing: true });
        if (!started.ok) { PyCmd.toast(started.error || 'already running'); return; }
        document.getElementById('setupLog').hidden = false;
        document.getElementById('setupBar').hidden = false;
        setupPoll();
      },
    }),
    PyCmd.el('button', {
      text: 'Stop', onclick: () => PyCmd.call('setup.stop', {}),
    })));
  card.appendChild(bar);
  card.appendChild(said);
  card.appendChild(log);
  screen.appendChild(card);

  const now = await PyCmd.call('setup.state', {});
  if (now.setup && now.setup.running) {
    document.getElementById('setupLog').hidden = false;
    document.getElementById('setupBar').hidden = false;
    setupPoll();
  }
}

function setupPoll() {
  clearInterval(setupTimer);
  setupTimer = setInterval(async () => {
    if (PyCmd.state.tab !== 'toolchains') { clearInterval(setupTimer); return; }
    const reply = await PyCmd.call('setup.state', {});
    const log = document.getElementById('setupLog');
    const fill = document.getElementById('setupFill');
    const said = document.getElementById('setupSaid');
    if (!log || !fill || !said) { clearInterval(setupTimer); return; }

    (reply.lines || []).length && (log.textContent += reply.lines.join(''));
    log.scrollTop = log.scrollHeight;

    const s = reply.setup || {};
    const done = s.settled || 0;
    const total = s.total || 1;
    fill.style.width = Math.round((done / total) * 100) + '%';
    said.textContent = s.running
      ? `${done} of ${total} — ${s.current || 'starting'} · ${s.seconds}s`
      : (s.everStarted
          ? `Finished in ${s.seconds}s — ${(s.done || []).length} installed, `
            + `${(s.skipped || []).length} already here, `
            + `${(s.failed || []).length} could not be.`
          : '');

    if (s.everStarted && !s.running) {
      clearInterval(setupTimer);
      if ((s.failed || []).length) setupReport(s.failed);
    }
  }, 1200);
}

function setupReport(failed) {
  const list = PyCmd.el('div', { class: 'list' });
  failed.forEach((row) => {
    list.appendChild(PyCmd.el('div', { class: 'row-item' },
      PyCmd.el('div', { class: 'grow' },
        PyCmd.el('div', { text: row.name }),
        PyCmd.el('div', { class: 'muted small-text', text: row.why })),
      row.site ? PyCmd.el('a', { href: row.site, target: '_blank', text: 'site' })
               : PyCmd.el('span', {})));
  });
  PyCmd.sheet(failed.length + ' could not be installed', PyCmd.el('div', {},
    PyCmd.el('p', { class: 'muted',
      text: 'Everything else is ready. These need a hand:' }),
    list));
}

function fact(name, value) {
  return PyCmd.el('div', { class: 'fact' },
    PyCmd.el('span', { class: 'muted', text: name }),
    PyCmd.el('span', { text: String(value === undefined ? '' : value) }));
}
