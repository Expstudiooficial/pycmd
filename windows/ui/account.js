/*
  A PyCmd account, on the Learn screen.

  Signed out: sign in, create an account, or move progress by hand with a
  .json file. Signed in: who you are, when it last synced, and the account
  sheet (change password, sign out, delete). The password is stretched in
  Python before anything is sent; this page only ever hands it over.
*/
'use strict';

const account = { status: null, lastSync: 0 };

function agoText(seconds) {
  if (!seconds) return 'not synced yet';
  const s = Math.max(0, Math.round(Date.now() / 1000 - seconds));
  if (s < 45) return 'synced just now';
  if (s < 90) return 'synced a minute ago';
  if (s < 3600) return `synced ${Math.round(s / 60)} minutes ago`;
  if (s < 5400) return 'synced an hour ago';
  if (s < 86400) return `synced ${Math.round(s / 3600)} hours ago`;
  return `synced ${Math.round(s / 86400)} days ago`;
}

/** The card at the top of Learn. Re-renders itself, never the whole screen. */
function accountCard(onChange) {
  const host = el('div', { class: 'card account-card' });
  const draw = (st) => {
    clear(host);
    account.status = st;
    if (!st || !st.ok) {
      host.appendChild(el('div', { class: 'muted', text: 'Accounts are not available.' }));
      return;
    }
    if (!st.signed_in) {
      host.append(
        el('div', { class: 'account-mark', text: '☁' }),
        el('div', { class: 'grow' },
          el('b', { text: 'Keep your progress on every device' }),
          el('div', { class: 'muted', text: 'Sign in and your lessons follow you between this '
            + 'PC and PyCmd on your phone. Or move them by hand as a .json file.' })),
        el('div', { class: 'row wrap account-actions' },
          el('button', { class: 'small primary', text: 'Sign in', onclick: () => accountSignIn(draw, onChange) }),
          el('button', { class: 'small', text: 'Create account', onclick: () => accountSignUp(draw, onChange) }),
          progressMenu(onChange)));
      return;
    }
    const line = st.syncing ? 'syncing…' : agoText(st.synced_at);
    host.append(
      el('div', { class: 'account-mark on', text: (st.username || '?').slice(0, 1).toUpperCase() }),
      el('div', { class: 'grow' },
        el('b', { text: st.username }),
        el('div', { class: st.last_error ? 'muted warn-text' : 'muted',
          text: st.last_error ? `Not synced: ${st.last_error}` : `Progress ${line}` })),
      el('div', { class: 'row wrap account-actions' },
        el('button', { class: 'small', text: 'Sync now', onclick: async (event) => {
          event.target.disabled = true;
          event.target.textContent = 'Syncing…';
          const reply = await PyCmd.call('account.sync', {});
          if (!reply.ok) PyCmd.toast(reply.error || 'Sync failed.');
          draw(reply.ok ? reply : await PyCmd.call('account', {}));
          if (reply.ok && onChange) onChange(reply);
        } }),
        progressMenu(onChange),
        el('button', { class: 'small', text: 'Cloud files', onclick: cloudSheet }),
        el('button', { class: 'small', text: 'Account', onclick: () => accountSheet(draw, onChange) })));
  };
  PyCmd.call('account', {}).then((st) => {
    draw(st);
    // Opening Learn pulls the other devices' lessons in, at most every 90s.
    if (st && st.signed_in && Date.now() - account.lastSync > 90000) {
      account.lastSync = Date.now();
      PyCmd.call('account.sync', {}).then((reply) => {
        draw(reply.ok ? reply : st);
        if (reply.ok && onChange) onChange(reply);
      });
    }
  });
  return host;
}

function progressMenu(onChange) {
  return el('div', { class: 'row', style: 'gap:6px' },
    el('button', { class: 'small', text: 'Export', title: 'Save your progress as a .json file',
      onclick: async () => {
        const reply = await PyCmd.call('progress.export', {});
        if (reply.cancelled) return;
        PyCmd.toast(reply.ok ? `Saved ${reply.lessons} lessons to ${reply.path}` : (reply.error || 'Export failed.'));
      } }),
    el('button', { class: 'small', text: 'Import', title: 'Load progress from a .json file',
      onclick: () => importSheet(onChange) }));
}

function importSheet(onChange) {
  const run = async (mode) => {
    const reply = await PyCmd.call('progress.import', { mode });
    if (reply.cancelled) return;
    if (!reply.ok) { PyCmd.toast(reply.error || 'Import failed.'); return; }
    PyCmd.closeSheet();
    PyCmd.toast(mode === 'replace'
      ? `Progress replaced: ${reply.lessons} lessons.`
      : `Imported: ${reply.added} new lessons, ${reply.lessons} in all.`);
    if (onChange) onChange(reply);
  };
  PyCmd.sheet('Import progress', el('div', {},
    el('p', { class: 'muted', text: 'Pick a .json file exported from PyCmd on Windows or Android.' }),
    el('div', { class: 'choice-list' },
      el('button', { class: 'choice', onclick: () => run('merge') },
        el('b', { text: 'Add to my progress' }),
        el('span', { class: 'muted', text: 'Lessons in the file are added. Nothing here is lost.' })),
      el('button', { class: 'choice danger-choice', onclick: () => run('replace') },
        el('b', { text: 'Replace my progress' }),
        el('span', { class: 'muted', text: 'This PC ends up with exactly what is in the file. '
          + 'If you are signed in, your other devices follow at their next sync.' })))));
}

// ---------------------------------------------------------------------------
// The forms
// ---------------------------------------------------------------------------

function field(label, input, extra) {
  return el('label', { class: 'field' }, el('span', { text: label }), input, extra || null);
}

function passwordInput(placeholder, autocomplete) {
  const input = el('input', { type: 'password', placeholder, autocomplete, maxlength: '128',
    spellcheck: 'false' });
  const toggle = el('button', { class: 'small ghost', type: 'button', text: 'Show',
    onclick: () => {
      input.type = input.type === 'password' ? 'text' : 'password';
      toggle.textContent = input.type === 'password' ? 'Show' : 'Hide';
    } });
  return { input, node: el('div', { class: 'row input-with' }, input, toggle) };
}

function formError() {
  return el('div', { class: 'form-error', role: 'alert', hidden: true });
}

function showError(node, text) {
  node.textContent = text || '';
  node.hidden = !text;
}

async function busy(button, text, work) {
  const before = button.textContent;
  button.disabled = true;
  button.textContent = text;
  try {
    return await work();
  } finally {
    button.disabled = false;
    button.textContent = before;
  }
}

function accountSignIn(draw, onChange) {
  const name = el('input', { placeholder: 'username', autocomplete: 'username', maxlength: '24',
    spellcheck: 'false' });
  const pass = passwordInput('password', 'current-password');
  const error = formError();
  const go = el('button', { class: 'small primary', text: 'Sign in' });
  const submit = async () => {
    showError(error, '');
    if (!name.value.trim() || !pass.input.value) {
      showError(error, 'Type your username and password.');
      return;
    }
    const reply = await busy(go, 'Signing in…', () => PyCmd.call('account.login',
      { username: name.value.trim(), password: pass.input.value }));
    if (!reply.ok) { showError(error, reply.error); pass.input.select(); return; }
    PyCmd.closeSheet();
    PyCmd.toast(`Signed in as ${reply.username}.`);
    draw(reply);
    if (onChange) onChange(reply);
  };
  go.onclick = submit;
  const form = el('form', { class: 'account-form', onsubmit: (e) => { e.preventDefault(); submit(); } },
    field('Username', name), field('Password', pass.node), error,
    el('div', { class: 'row spread' },
      el('button', { class: 'small ghost', type: 'button', text: 'No account? Create one',
        onclick: () => accountSignUp(draw, onChange) }),
      go));
  PyCmd.sheet('Sign in to PyCmd', form);
  setTimeout(() => name.focus(), 30);
}

function accountSignUp(draw, onChange) {
  const name = el('input', { placeholder: '3 to 24 letters, digits, _ . -', autocomplete: 'username',
    maxlength: '24', spellcheck: 'false' });
  const nameNote = el('div', { class: 'field-note muted', text: ' ' });
  const pass = passwordInput('at least 8 characters', 'new-password');
  const passNote = el('div', { class: 'field-note muted',
    text: 'Long beats clever: a few words you will remember work well.' });
  const again = passwordInput('the same again', 'new-password');
  const error = formError();
  const go = el('button', { class: 'small primary', text: 'Create account' });
  let timer = 0;
  let asked = '';
  name.addEventListener('input', () => {
    clearTimeout(timer);
    const value = name.value.trim();
    nameNote.className = 'field-note muted';
    nameNote.textContent = value ? 'Checking…' : ' ';
    if (!value) return;
    timer = setTimeout(async () => {
      asked = value;
      const reply = await PyCmd.call('account.username', { name: value });
      if (asked !== name.value.trim()) return;  // They kept typing.
      if (!reply.ok) {
        nameNote.textContent = reply.error || 'Could not check that name.';
        return;
      }
      nameNote.className = 'field-note ' + (reply.available ? 'good-text' : 'bad-text');
      nameNote.textContent = reply.available ? `✓ ${value} is free` : `✗ ${reply.reason}`;
    }, 350);
  });
  pass.input.addEventListener('input', () => {
    const n = pass.input.value.length;
    passNote.className = 'field-note ' + (n && n < 8 ? 'bad-text' : 'muted');
    passNote.textContent = n && n < 8 ? `${8 - n} more character${8 - n === 1 ? '' : 's'}`
      : 'Long beats clever: a few words you will remember work well.';
  });
  const submit = async () => {
    showError(error, '');
    if (pass.input.value !== again.input.value) {
      showError(error, 'The two passwords are not the same.');
      return;
    }
    const reply = await busy(go, 'Creating…', () => PyCmd.call('account.signup',
      { username: name.value.trim(), password: pass.input.value }));
    if (!reply.ok) {
      showError(error, reply.error);
      if (reply.field === 'username') name.select();
      return;
    }
    PyCmd.closeSheet();
    PyCmd.toast(`Welcome, ${reply.username}. Your progress is saved to your account.`);
    draw(reply);
    if (onChange) onChange(reply);
  };
  go.onclick = submit;
  const form = el('form', { class: 'account-form', onsubmit: (e) => { e.preventDefault(); submit(); } },
    field('Username', name, nameNote), field('Password', pass.node, passNote),
    field('Password again', again.node), error,
    el('p', { class: 'muted small-text', text: 'Your password never leaves this PC: PyCmd sends '
      + 'pycmd.pages.dev a key made from it, which cannot be turned back into the password.' }),
    el('div', { class: 'row spread' },
      el('button', { class: 'small ghost', type: 'button', text: 'Have an account? Sign in',
        onclick: () => accountSignIn(draw, onChange) }),
      go));
  PyCmd.sheet('Create a PyCmd account', form);
  setTimeout(() => name.focus(), 30);
}

function accountSheet(draw, onChange) {
  const st = account.status || {};
  const oldPass = passwordInput('current password', 'current-password');
  const newPass = passwordInput('new password, at least 8 characters', 'new-password');
  const changeError = formError();
  const change = el('button', { class: 'small', text: 'Change password' });
  change.onclick = async () => {
    showError(changeError, '');
    const reply = await busy(change, 'Changing…', () => PyCmd.call('account.password',
      { old: oldPass.input.value, new: newPass.input.value }));
    if (!reply.ok) { showError(changeError, reply.error); return; }
    PyCmd.closeSheet();
    PyCmd.toast(reply.message || 'Password changed.');
  };
  const delPass = passwordInput('password, to confirm', 'current-password');
  const delError = formError();
  const del = el('button', { class: 'small danger', text: 'Delete my account' });
  del.onclick = async () => {
    showError(delError, '');
    if (!delPass.input.value) { showError(delError, 'Type your password to confirm.'); return; }
    const reply = await busy(del, 'Deleting…', () => PyCmd.call('account.delete',
      { password: delPass.input.value }));
    if (!reply.ok) { showError(delError, reply.error); return; }
    PyCmd.closeSheet();
    PyCmd.toast(reply.message || 'Account deleted.');
    draw(reply);
  };
  PyCmd.sheet(`Account · ${st.username || ''}`, el('div', { class: 'account-form' },
    el('p', { class: 'muted', text: `${agoText(st.synced_at)[0].toUpperCase()}${agoText(st.synced_at).slice(1)}`
      + ` · ${st.server || ''}` }),
    el('div', { class: 'row' },
      el('button', { class: 'small', text: 'Sign out of this PC', onclick: async () => {
        const reply = await PyCmd.call('account.logout', {});
        PyCmd.closeSheet();
        PyCmd.toast('Signed out. Your progress stays on this PC.');
        draw(reply);
      } })),
    el('h2', { text: 'Change password' }),
    field('Current password', oldPass.node), field('New password', newPass.node), changeError,
    el('div', { class: 'row' }, change),
    el('p', { class: 'muted small-text', text: 'Your other devices are signed out and sign in '
      + 'again with the new password.' }),
    el('h2', { text: 'Delete account' }),
    el('p', { class: 'muted', text: 'Removes the account and its saved progress from '
      + 'pycmd.pages.dev. The lessons on this PC stay. This cannot be undone.' }),
    field('Password', delPass.node), delError,
    el('div', { class: 'row' }, del)));
}

// ---------------------------------------------------------------------------
// Cloud storage: 800 KB of files on pycmd.pages.dev, for every account
// ---------------------------------------------------------------------------

async function cloudSheet() {
  const reply = await PyCmd.call('cloud.files', {});
  if (!reply.ok) { PyCmd.toast(reply.error || 'Cloud storage is not reachable.'); return; }
  const kb = (n) => (n / 1024).toFixed(n < 10240 ? 1 : 0) + ' KB';
  const pct = Math.min(100, Math.round((reply.used / reply.quota) * 100));
  const list = el('div', { class: 'list' });
  (reply.files || []).forEach((f) => list.appendChild(el('div', { class: 'row-item' },
    el('span', { class: 'grow mono', text: f.path }),
    el('span', { class: 'muted', text: kb(f.size) }),
    el('button', { class: 'small', text: '\u2193 Download', onclick: async () => {
      const r = await PyCmd.call('cloud.download', { name: f.path });
      PyCmd.toast(r.ok ? `Saved to ${r.path}` : (r.error || 'That did not work.'));
    } }),
    el('button', { class: 'small danger', text: 'Delete', onclick: async () => {
      const r = await PyCmd.call('cloud.delete', { name: f.path });
      if (!r.ok) PyCmd.toast(r.error || 'That did not work.'); else cloudSheet();
    } }))));
  if (!(reply.files || []).length) list.appendChild(el('div', { class: 'empty', text: 'Nothing here yet.' }));
  PyCmd.sheet('Cloud files', el('div', {},
    el('p', { class: 'muted', text: `${kb(reply.used)} of ${kb(reply.quota)} used. Small code, notes and `
      + 'configs, on every device you sign in on. Downloads go to workspace\\cloud - also in Files > Cloud.' }),
    el('div', { class: 'progress' }, el('div', { class: 'fill', style: `width:${pct}%` })),
    el('div', { class: 'row', style: 'margin:10px 0' },
      el('button', { class: 'small primary', text: 'Upload a file…', onclick: async () => {
        const r = await PyCmd.call('cloud.upload', {});
        if (r.cancelled) return;
        if (!r.ok) PyCmd.toast(r.error || 'That did not upload.'); else cloudSheet();
      } })),
    list));
}
