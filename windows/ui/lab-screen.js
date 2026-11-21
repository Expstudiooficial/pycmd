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

const LAB_STEPS = {
  java: 'Java',
  tools: 'SDK tools',
  licences: 'Licences',
  image: 'Android image',
  device: 'Device',
  accel: 'Acceleration',
  boot: 'Boot',
  apk: 'PyCmd app',
};

async function Android(screen) {
  const [plan, now] = await Promise.all([
    PyCmd.call('android.plan', {}), PyCmd.call('android', {})]);

  screen.appendChild(head('Android Lab',
    'A real Android device on this PC, with PyCmd Android installed and opened on it.'));

  const top = PyCmd.el('div', { class: 'card', id: 'labTop' });
  screen.appendChild(top);
  drawLabTop(top, now, plan);

  const progress = PyCmd.el('div', { class: 'card', id: 'labProgress', hidden: true });
  screen.appendChild(progress);

  if ((now.running || []).length) screen.appendChild(labControls(now.running[0]));

  screen.appendChild(labSettings(now));
  screen.appendChild(labPlanCard(plan));
  screen.appendChild(labPhones(now));
  screen.appendChild(labMaintenance(now));
  screen.appendChild(PyCmd.el('div', { class: 'card note' },
    PyCmd.el('p', { class: 'muted', text: plan.honest })));

  const job = now.job || {};
  if (job.everStarted) {
    drawLabProgress(job, true);
    if (job.running) labPoll();
  }
}

function labTile(name, value, kind) {
  return PyCmd.el('div', { class: 'tile ' + (kind || '') },
    PyCmd.el('div', { class: 'muted', text: name }),
    PyCmd.el('div', { class: 'tile-v', text: value }));
}

function drawLabTop(node, now, plan) {
  PyCmd.clear(node);
  const java = now.java || {};
  const running = now.running || [];
  const job = now.job || {};
  node.appendChild(PyCmd.el('div', { class: 'tiles' },
    labTile('Java', java.major ? 'Java ' + java.major : 'will be installed', java.major ? 'good' : ''),
    labTile('Android SDK', now.ready ? (now.sdkIsOwn ? 'PyCmd’s own' : 'yours, reused') : 'will be downloaded',
      now.ready ? 'good' : ''),
    labTile('Android', ((now.androids || []).find((a) => a.api === (now.config || {}).api) || {}).name
      + (now.imageHere ? '' : ' · not yet'), now.imageHere ? 'good' : ''),
    labTile('Device', now.hasOurs ? 'PyCmd_Lab' : 'not created', now.hasOurs ? 'good' : ''),
    labTile('Running', running.length ? running.join(', ') : 'nothing', running.length ? 'good' : ''),
  ));
  node.appendChild(PyCmd.el('p', { class: 'muted', text: plan.download }));

  const row = PyCmd.el('div', { class: 'row wrap' });
  if (job.running) {
    row.appendChild(PyCmd.el('button', { class: 'small danger', text: 'Stop setting up',
      onclick: async () => { await PyCmd.call('android.cancel', {}); PyCmd.toast('Stopping…'); } }));
  } else if (running.length) {
    row.appendChild(PyCmd.el('button', { class: 'small', text: 'Install PyCmd again',
      onclick: () => labStart({}) }));
    row.appendChild(PyCmd.el('button', { class: 'small danger', text: 'Shut it down',
      onclick: async () => {
        await PyCmd.call('android.stop', {});
        PyCmd.toast('Shutting down.');
        setTimeout(() => go('android'), 2500);
      } }));
  } else {
    row.appendChild(PyCmd.el('button', { class: 'small primary',
      text: now.hasOurs && now.imageHere ? 'Start the device' : 'Set it up and start it',
      onclick: () => labStart({}) }));
    row.appendChild(PyCmd.el('button', { class: 'small', text: 'Check acceleration',
      onclick: labAccel }));
  }
  node.appendChild(row);
}

async function labStart(options) {
  const started = await PyCmd.call('android.start', options || {});
  if (!started.ok) { PyCmd.toast(started.error || 'it is already going'); return; }
  PyCmd.toast('Started. The first time takes a while - it is all in the log below.');
  const log = document.getElementById('labLog');
  if (log) log.textContent = '';
  drawLabProgress({ running: true, steps: Object.keys(LAB_STEPS), doneSteps: [], step: 'java' }, false);
  labPoll();
  const now = await PyCmd.call('android', {});
  const top = document.getElementById('labTop');
  if (top) drawLabTop(top, now, await PyCmd.call('android.plan', {}));
}

function drawLabProgress(job, keepLog) {
  const node = document.getElementById('labProgress');
  if (!node) return;
  const oldLog = document.getElementById('labLog');
  const text = keepLog && oldLog ? oldLog.textContent : (oldLog ? oldLog.textContent : '');
  PyCmd.clear(node);
  node.hidden = false;
  node.appendChild(PyCmd.el('h2', { text: job.running ? 'Setting up' : (job.ok ? 'Ready' : 'Stopped') }));

  const chips = PyCmd.el('div', { class: 'stepper' });
  (job.steps || Object.keys(LAB_STEPS)).forEach((id) => {
    const done = (job.doneSteps || []).includes(id);
    const current = job.step === id;
    chips.appendChild(PyCmd.el('span', {
      class: 'stepchip' + (done ? ' done' : '') + (current ? ' now' : ''),
      text: (done ? '✓ ' : current ? '● ' : '') + (LAB_STEPS[id] || id),
    }));
  });
  node.appendChild(chips);

  if (job.running) {
    const bar = PyCmd.el('div', { class: 'progress' + (job.percent >= 0 ? '' : ' busy') },
      PyCmd.el('div', { class: 'fill', style: 'width:' + (job.percent >= 0 ? job.percent : 30) + '%' }));
    node.appendChild(bar);
    node.appendChild(PyCmd.el('p', { class: 'muted',
      text: (LAB_STEPS[job.step] || 'Working') + (job.percent >= 0 ? ' · ' + job.percent + '%' : '')
        + ' · ' + (job.seconds || 0) + 's' }));
  }

  if (!job.running && job.error) {
    const box = PyCmd.el('div', { class: 'card bad-box' },
      PyCmd.el('b', { text: 'What went wrong' }),
      PyCmd.el('p', { text: job.error }));
    const fixes = PyCmd.el('div', { class: 'row wrap' });
    if (job.fix === 'whpx') {
      fixes.appendChild(PyCmd.el('button', { class: 'small primary', text: 'Turn on Windows Hypervisor Platform',
        onclick: () => labFixAccel('whpx') }));
      fixes.appendChild(PyCmd.el('button', { class: 'small', text: 'Install Google’s hypervisor driver instead',
        onclick: () => labFixAccel('aehd') }));
    }
    if (job.fix === 'bios') {
      box.appendChild(PyCmd.el('p', { class: 'muted', text:
        'Virtualisation is switched off in this PC’s firmware. Restart into the BIOS/UEFI setup '
        + '(usually F2, F10 or Del while it starts), turn on "Intel VT-x" or "AMD SVM", save, and start the lab again.' }));
    }
    fixes.appendChild(PyCmd.el('button', { class: 'small', text: 'Try again', onclick: () => labStart({}) }));
    fixes.appendChild(PyCmd.el('button', { class: 'small', text: 'Diagnostics', onclick: labDiagnose }));
    box.appendChild(fixes);
    node.appendChild(box);
  }

  const toggle = PyCmd.el('button', { class: 'small', text: 'Show the log' });
  const log = PyCmd.el('pre', { class: 'out mono', id: 'labLog', hidden: !job.running && !job.error });
  log.textContent = text;
  toggle.addEventListener('click', () => {
    log.hidden = !log.hidden;
    toggle.textContent = log.hidden ? 'Show the log' : 'Hide the log';
  });
  toggle.textContent = log.hidden ? 'Show the log' : 'Hide the log';
  node.appendChild(PyCmd.el('div', { class: 'row' }, toggle,
    PyCmd.el('button', { class: 'small', text: 'Copy the log', onclick: () => {
      navigator.clipboard.writeText(log.textContent).then(() => PyCmd.toast('Copied.'));
    } })));
  node.appendChild(log);
}

function labPoll() {
  clearInterval(labTimer);
  labTimer = setInterval(async () => {
    if (PyCmd.state.tab !== 'android') { clearInterval(labTimer); return; }
    const reply = await PyCmd.call('android.job', {});
    const job = reply.job || {};
    const lines = reply.lines || [];
    const log = document.getElementById('labLog');
    if (log && lines.length) {
      log.textContent += lines.join('');
      if (log.textContent.length > 400000) log.textContent = log.textContent.slice(-300000);
      log.scrollTop = log.scrollHeight;
    }
    drawLabProgress(job, true);
    const fresh = document.getElementById('labLog');
    if (fresh) fresh.scrollTop = fresh.scrollHeight;
    if (job.everStarted && !job.running) {
      clearInterval(labTimer);
      if (job.ok) {
        PyCmd.toast('Android Lab is ready.');
        setTimeout(() => go('android'), 800);
      } else if (job.error) {
        PyCmd.toast(job.error);
      }
    }
  }, 1200);
}

async function labAccel() {
  PyCmd.toast('Asking the emulator…');
  const reply = await PyCmd.call('android.accel', {});
  const body = PyCmd.el('div', {},
    PyCmd.el('p', { text: reply.ok ? 'Hardware acceleration works. The emulator will run at full speed.'
      : (reply.message || 'It could not be checked.') }));
  if (!reply.ok && reply.fix === 'whpx') {
    body.appendChild(PyCmd.el('div', { class: 'row wrap' },
      PyCmd.el('button', { class: 'small primary', text: 'Turn on Windows Hypervisor Platform',
        onclick: () => labFixAccel('whpx') }),
      PyCmd.el('button', { class: 'small', text: 'Install Google’s driver', onclick: () => labFixAccel('aehd') })));
  }
  PyCmd.sheet('Hardware acceleration', body);
}

async function labFixAccel(how) {
  PyCmd.toast('Windows will ask for administrator…');
  const reply = await PyCmd.call('android.fixAccel', { how });
  PyCmd.sheet(reply.ok ? 'Done' : 'That did not work', PyCmd.el('p', {
    text: reply.ok ? reply.message : reply.error }));
}

async function labDiagnose() {
  const reply = await PyCmd.call('android.diagnose', {});
  const text = JSON.stringify(reply, null, 2);
  PyCmd.sheet('Android Lab diagnostics', PyCmd.el('div', {},
    PyCmd.el('p', { class: 'muted', text: 'Everything the lab knows about this machine. Paste it into a bug report.' }),
    PyCmd.el('button', { class: 'small', text: 'Copy', onclick: () =>
      navigator.clipboard.writeText(text).then(() => PyCmd.toast('Copied.')) }),
    PyCmd.el('pre', { class: 'out mono', text })));
}

function labControls(serial) {
  const typed = PyCmd.el('input', { placeholder: 'Type into the device…' });
  const shot = PyCmd.el('img', { class: 'lab-shot', hidden: true, alt: 'Screenshot of the device' });
  const send = async () => {
    if (!typed.value) return;
    const reply = await PyCmd.call('android.text', { serial, text: typed.value });
    if (reply.ok) typed.value = ''; else PyCmd.toast(reply.error || 'it did not go through');
  };
  typed.addEventListener('keydown', (event) => { if (event.key === 'Enter') send(); });
  const key = (name) => PyCmd.call('android.key', { serial, key: name });
  return PyCmd.el('div', { class: 'card' },
    PyCmd.el('h2', { text: 'The device · ' + serial }),
    PyCmd.el('div', { class: 'row wrap' },
      PyCmd.el('button', { class: 'small primary', text: 'Open PyCmd', onclick: async () => {
        const reply = await PyCmd.call('android.open', { serial });
        PyCmd.toast(reply.ok ? 'Opened.' : 'PyCmd is not installed on it yet.');
      } }),
      PyCmd.el('button', { class: 'small', text: '◁ Back', onclick: () => key('back') }),
      PyCmd.el('button', { class: 'small', text: '○ Home', onclick: () => key('home') }),
      PyCmd.el('button', { class: 'small', text: '▢ Apps', onclick: () => key('recents') }),
      PyCmd.el('button', { class: 'small', text: 'Screenshot', onclick: async () => {
        const reply = await PyCmd.call('android.screenshot', { serial });
        if (!reply.ok) { PyCmd.toast(reply.error); return; }
        shot.src = 'data:image/png;base64,' + reply.png;
        shot.hidden = false;
        PyCmd.toast('Saved to ' + reply.path);
      } }),
      PyCmd.el('button', { class: 'small', text: 'Logcat', onclick: () => labLogcat(serial) })),
    PyCmd.el('div', { class: 'row' }, typed,
      PyCmd.el('button', { class: 'small', text: 'Send', onclick: send })),
    shot);
}

async function labLogcat(serial) {
  const only = PyCmd.el('input', { type: 'checkbox' });
  const out = PyCmd.el('pre', { class: 'out mono', text: 'Reading…' });
  const filter = PyCmd.el('input', { placeholder: 'Only lines containing…' });
  let text = '';
  const draw = () => {
    const want = filter.value.toLowerCase();
    out.textContent = want ? text.split('\n').filter((l) => l.toLowerCase().includes(want)).join('\n') : text;
    out.scrollTop = out.scrollHeight;
  };
  const load = async () => {
    const reply = await PyCmd.call('android.logcat', { serial, lines: 800, onlyPycmd: only.checked });
    text = reply.ok ? reply.text : (reply.error || 'nothing');
    draw();
  };
  filter.addEventListener('input', draw);
  only.addEventListener('change', load);
  PyCmd.sheet('Logcat · ' + serial, PyCmd.el('div', {},
    PyCmd.el('div', { class: 'row wrap' },
      PyCmd.el('label', { class: 'row' }, only, 'Only PyCmd'),
      filter,
      PyCmd.el('button', { class: 'small', text: 'Refresh', onclick: load })),
    out));
  load();
}

function labNumber(label, key, value, limits, step) {
  const input = PyCmd.el('input', { type: 'number', value: String(value), min: String(limits[0]),
    max: String(limits[1]), step: String(step || 1), 'data-key': key });
  return PyCmd.el('label', { class: 'field' }, PyCmd.el('span', { text: label }), input);
}

function labSettings(now) {
  const c = now.config || {};
  const limits = now.limits || {};
  const api = PyCmd.el('select', { 'data-key': 'api' });
  (now.androids || []).forEach((a) => api.appendChild(PyCmd.el('option', {
    value: String(a.api), text: a.name + ' (API ' + a.api + ')' + (a.here ? ' · downloaded' : ''),
    selected: a.api === c.api })));
  const gpu = PyCmd.el('select', { 'data-key': 'gpu' });
  (now.gpuModes || []).forEach((m) => gpu.appendChild(PyCmd.el('option', {
    value: m, text: m === 'auto' ? 'auto (recommended)' : m, selected: m === c.gpu })));
  const check = (key, label) => PyCmd.el('label', { class: 'row' },
    PyCmd.el('input', { type: 'checkbox', 'data-key': key, checked: !!c[key] }), label);

  const form = PyCmd.el('div', { class: 'grid two' },
    PyCmd.el('label', { class: 'field' }, PyCmd.el('span', { text: 'Android version' }), api),
    PyCmd.el('label', { class: 'field' }, PyCmd.el('span', { text: 'Graphics' }), gpu),
    labNumber('Memory (MB)', 'ramMb', c.ramMb, limits.ramMb || [1536, 16384], 512),
    labNumber('Storage (MB)', 'storageMb', c.storageMb, limits.storageMb || [4096, 65536], 1024),
    labNumber('CPU cores', 'cores', c.cores, limits.cores || [1, 16], 1),
    labNumber('App heap (MB)', 'heapMb', c.heapMb, limits.heapMb || [128, 1024], 64));
  const card = PyCmd.el('div', { class: 'card' },
    PyCmd.el('h2', { text: 'The device it builds' }),
    PyCmd.el('p', { class: 'muted', text: 'Changes apply the next time the device starts. '
      + 'A different Android version downloads its own image (about 2.5 GB).' }),
    form,
    PyCmd.el('div', { class: 'row wrap' },
      check('coldBoot', 'Cold boot every time (slower, cleaner)'),
      check('installApk', 'Install PyCmd Android'),
      check('openApk', 'Open it once installed')));
  card.appendChild(PyCmd.el('div', { class: 'row' },
    PyCmd.el('button', { class: 'small primary', text: 'Save', onclick: async () => {
      const set = {};
      card.querySelectorAll('[data-key]').forEach((node) => {
        const key = node.getAttribute('data-key');
        if (node.type === 'checkbox') set[key] = node.checked;
        else if (node.type === 'number' || key === 'api') set[key] = Number(node.value);
        else set[key] = node.value;
      });
      const reply = await PyCmd.call('android.config', { set });
      PyCmd.toast(reply.ok ? 'Saved.' : (reply.error || 'not saved'));
      if (reply.ok) go('android');
    } }),
    PyCmd.el('button', { class: 'small', text: 'Back to the defaults', onclick: async () => {
      await PyCmd.call('android.config', { set: { api: 35, ramMb: 4096, storageMb: 10240, cores: 4,
        heapMb: 512, gpu: 'auto', coldBoot: false, installApk: true, openApk: true } });
      go('android');
    } })));
  return card;
}

function labPlanCard(plan) {
  const body = PyCmd.el('div', { hidden: true });
  (plan.steps || []).forEach((step, index) => {
    body.appendChild(PyCmd.el('div', { class: 'step' },
      PyCmd.el('span', { class: 'n', text: String(index + 1) }),
      PyCmd.el('div', { class: 'grow' },
        PyCmd.el('div', { text: step.what }),
        PyCmd.el('div', { class: 'muted small-text', text: step.why }),
        PyCmd.el('code', { class: 'muted', text: step.how })),
      PyCmd.el('span', { class: 'muted', text: step.size })));
  });
  const toggle = PyCmd.el('button', { class: 'small', text: 'Show every step' });
  toggle.addEventListener('click', () => {
    body.hidden = !body.hidden;
    toggle.textContent = body.hidden ? 'Show every step' : 'Hide the steps';
  });
  return PyCmd.el('div', { class: 'card' },
    PyCmd.el('div', { class: 'row spread' },
      PyCmd.el('h2', { text: 'What pressing Start does' }), toggle),
    body);
}

function labPhones(now) {
  const phones = now.phones || [];
  const card = PyCmd.el('div', { class: 'card' },
    PyCmd.el('h2', { text: 'Phones on USB' }));
  if (!phones.length) {
    card.appendChild(PyCmd.el('p', { class: 'muted', text: 'None connected. Turn on USB debugging '
      + '(Settings → About phone → tap Build number seven times → Developer options), plug the phone '
      + 'in, and allow this PC when it asks. Then PyCmd can install itself on it from here.' }));
  }
  phones.forEach((phone) => {
    card.appendChild(PyCmd.el('div', { class: 'row-item' },
      PyCmd.el('div', { class: 'grow' },
        PyCmd.el('div', { text: phone.model || phone.serial }),
        PyCmd.el('div', { class: 'muted small-text', text: phone.serial + ' · ' + phone.state
          + (phone.state === 'unauthorized' ? ' - allow this PC on the phone' : '') })),
      PyCmd.el('button', { class: 'small primary', text: 'Install PyCmd', disabled: !phone.ready,
        onclick: () => labInstallTo(phone.serial, '') })));
  });
  const path = PyCmd.el('input', { placeholder: 'C:\\path\\to\\any.apk' });
  const targets = PyCmd.el('select', {});
  (now.running || []).forEach((s) => targets.appendChild(PyCmd.el('option', { value: s, text: s })));
  phones.filter((p) => p.ready).forEach((p) => targets.appendChild(PyCmd.el('option', {
    value: p.serial, text: (p.model || p.serial) })));
  if (targets.options.length) {
    card.appendChild(PyCmd.el('h2', { text: 'Install any APK' }));
    card.appendChild(PyCmd.el('div', { class: 'row' }, path, targets,
      PyCmd.el('button', { class: 'small', text: 'Browse…', onclick: async () => {
        const got = await PyCmd.call('pick.file', { kinds: ['apk'] });
        if (got.ok && got.path) path.value = got.path;
        else if (got.error) PyCmd.toast(got.error);
      } }),
      PyCmd.el('button', { class: 'small', text: 'Install', onclick: () => {
        if (!path.value.trim()) { PyCmd.toast('Which APK?'); return; }
        labInstallTo(targets.value, path.value.trim());
      } })));
  }
  return card;
}

function labInstallTo(serial, apk) {
  PyCmd.toast('Installing on ' + serial + '…');
  PyCmd.call('android.installTo', { serial, apk });
}

function labMaintenance(now) {
  return PyCmd.el('div', { class: 'card' },
    PyCmd.el('h2', { text: 'When something is off' }),
    PyCmd.el('div', { class: 'row wrap' },
      PyCmd.el('button', { class: 'small', text: 'Wipe its data and start', disabled: !now.hasOurs,
        onclick: () => { if (confirm('Erase everything on the lab device and start it fresh?')) labStart({ wipe: true }); } }),
      PyCmd.el('button', { class: 'small danger', text: 'Delete the device', disabled: !now.hasOurs,
        onclick: async () => {
          if (!confirm('Delete PyCmd_Lab? The downloaded Android image stays, so making it again is quick.')) return;
          const reply = await PyCmd.call('android.delete', {});
          PyCmd.toast(reply.ok ? 'Deleted.' : 'It could not be deleted.');
          go('android');
        } }),
      PyCmd.el('button', { class: 'small', text: 'Check acceleration', onclick: labAccel }),
      PyCmd.el('button', { class: 'small', text: 'Diagnostics', onclick: labDiagnose }),
      now.log ? PyCmd.el('button', { class: 'small', text: 'Emulator log', onclick: () => diskReveal(now.log) }) : null),
    PyCmd.el('p', { class: 'muted small-text', text: 'SDK: ' + (now.sdk || '—') + ' · ' + (now.abi || '') }));
}

PyCmd.on('android-installed', (event) => {
  PyCmd.toast(event.ok ? 'Installed on ' + event.serial + '.' : 'It did not install: ' + event.error);
});

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
