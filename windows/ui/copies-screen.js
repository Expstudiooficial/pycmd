/*
  Other copies of PyCmd on this machine.

  2.0 shipped the whole of copies.py - finding them, checking them, archiving
  them, rolling back - and not one button that called any of it. So nothing
  ever happened, which is exactly what it looked like from the outside.

  This is the screen. It looks, it shows what it found and why each row can or
  cannot be removed, and it acts only when told to.
*/

'use strict';

let cpFound = null;
const cpChosen = new Set();

async function Copies(screen) {
  screen.appendChild(head('Other copies',
    'One PyCmd, not a folder full of them. Windows renames a second download '
    + 'rather than replacing it, so these pile up on their own.'));

  const status = PyCmd.el('div', { class: 'card' },
    PyCmd.el('p', { class: 'muted', text: 'Looking…' }));
  screen.appendChild(status);

  const kept = PyCmd.el('div', { class: 'card' });
  screen.appendChild(kept);

  await cpLook(status);
  await cpDrawKept(kept);
}

async function cpLook(card) {
  const reply = await PyCmd.call('copies', {});
  cpFound = reply;
  cpChosen.clear();
  PyCmd.clear(card);

  if (!reply.ok) {
    card.appendChild(PyCmd.el('div', { class: 'empty', text: reply.error || 'could not look' }));
    return;
  }

  card.appendChild(PyCmd.el('h2', { text: 'This machine' }));
  card.appendChild(PyCmd.el('div', { class: 'facts' },
    fact('Running now', reply.me || 'from a checkout, not an exe'),
    fact('This version', reply.myVersion),
    fact('Others found', String((reply.others || []).length)),
    fact('Looked in', (reply.lookedIn || []).length + ' folders')));

  const others = reply.others || [];
  if (!others.length) {
    card.appendChild(PyCmd.el('div', { class: 'empty',
      text: 'No other copies. This is the only PyCmd here.' }));
    card.appendChild(PyCmd.el('div', { class: 'row' },
      PyCmd.el('button', { class: 'small', text: 'Look again',
                           onclick: () => go('copies') })));
    return;
  }

  const list = PyCmd.el('div', { class: 'list' });
  others.forEach((row) => {
    const why = row.unknown
      ? 'would not say which version it is'
      : (row.older ? 'older than this one'
                   : (row.same ? 'the same version' : 'newer than this one'));
    const tick = PyCmd.el('input', { type: 'checkbox' });
    // Older ones are pre-ticked because removing them is the point. Unknown
    // ones are not: PyCmd has no evidence about them, and a tick it made
    // itself is not a decision the person took.
    tick.checked = !!row.older;
    if (row.older || row.unknown) {
      tick.addEventListener('change', () => {
        if (tick.checked) cpChosen.add(row.path); else cpChosen.delete(row.path);
      });
      if (tick.checked) cpChosen.add(row.path);
    } else {
      tick.disabled = true;
      tick.checked = false;
    }

    list.appendChild(PyCmd.el('label', { class: 'row-item' },
      tick,
      PyCmd.el('div', { class: 'grow' },
        PyCmd.el('div', { text: row.path.split(/[\\/]/).pop() }),
        PyCmd.el('div', { class: 'muted small-text ellipsis', text: row.path })),
      PyCmd.el('span', { class: row.unknown ? 'tag warn' : 'tag',
                         text: row.version || 'unknown' }),
      PyCmd.el('span', { class: 'muted small-text', text: why }),
      PyCmd.el('span', { class: 'muted small-text', text: PyCmd.bytes(row.bytes) })));
  });
  card.appendChild(list);

  if ((reply.older || []).some((r) => r.needsAdmin)) {
    card.appendChild(PyCmd.el('p', { class: 'muted',
      text: 'One of these is under Program Files and needs administrator to '
          + 'move. PyCmd will ask Windows for it when you press the button.' }));
  }

  card.appendChild(PyCmd.el('div', { class: 'row' },
    PyCmd.el('button', {
      class: 'primary', text: 'Archive and remove the ticked ones',
      onclick: () => cpReplace(card),
    }),
    PyCmd.el('button', { text: 'Look again', onclick: () => go('copies') })));

  card.appendChild(PyCmd.el('p', { class: 'muted small-text',
    text: 'Removed copies are moved into PyCmd\'s versions folder, not '
        + 'deleted — you can go back to one below.' }));
}

async function cpReplace(card) {
  if (!cpFound || !cpChosen.size) { PyCmd.toast('Nothing is ticked.'); return; }
  const rows = (cpFound.others || [])
    .filter((row) => cpChosen.has(row.path))
    .map((row) => ({ ...row, chosen: true }));

  const reply = await PyCmd.call('copies.replace', { others: rows });
  if (!reply.ok) { PyCmd.toast(reply.error || 'that did not work'); return; }

  if ((reply.needsAdmin || []).length) {
    PyCmd.sheet('Administrator needed', PyCmd.el('div', {},
      PyCmd.el('p', { text: reply.needsAdmin.length
        + ' of these are somewhere that needs administrator to change.' }),
      PyCmd.el('div', { class: 'row' },
        PyCmd.el('button', {
          class: 'primary', text: 'Ask Windows for it',
          onclick: async () => {
            const got = await PyCmd.call('copies.elevate', {});
            PyCmd.closeSheet();
            PyCmd.toast(got.ok ? 'Starting again as administrator…'
                               : (got.error || 'Windows said no.'));
          },
        }),
        PyCmd.el('button', { text: 'Leave them', onclick: PyCmd.closeSheet }))));
  }

  const gone = (reply.removed || []).length;
  PyCmd.toast(gone
    ? gone + ' archived and removed.'
    : 'Nothing was removed — see the reasons on screen.');
  go('copies');
}

async function cpDrawKept(card) {
  const reply = await PyCmd.call('copies.kept', {});
  PyCmd.clear(card);
  card.appendChild(PyCmd.el('h2', { text: 'Older builds you can go back to' }));

  const rows = (reply && reply.kept) || [];
  if (!rows.length) {
    card.appendChild(PyCmd.el('div', { class: 'empty',
      text: 'Nothing archived yet. Anything removed above is kept here.' }));
    return;
  }

  const list = PyCmd.el('div', { class: 'list' });
  rows.forEach((row) => {
    list.appendChild(PyCmd.el('div', { class: 'row-item' },
      PyCmd.el('div', { class: 'grow' },
        PyCmd.el('div', { text: 'PyCmd ' + (row.version || 'unknown') }),
        PyCmd.el('div', { class: 'muted small-text',
                          text: row.why + ' · ' + PyCmd.bytes(row.bytes) })),
      PyCmd.el('button', {
        class: 'small', text: 'Go back to this one',
        onclick: () => cpRollback(row),
      })));
  });
  card.appendChild(list);
  card.appendChild(PyCmd.el('p', { class: 'muted small-text',
    text: 'PyCmd keeps the ' + (reply.keeping || 5) + ' most recent.' }));
}

function cpRollback(row) {
  PyCmd.sheet('Go back to ' + (row.version || 'that build') + '?', PyCmd.el('div', {},
    PyCmd.el('p', { text: 'PyCmd has to close for this: the file it is running '
                        + 'from is locked while it runs. It will swap itself and '
                        + 'start again on its own.' }),
    PyCmd.el('div', { class: 'row' },
      PyCmd.el('button', {
        class: 'primary', text: 'Do it',
        onclick: async () => {
          const got = await PyCmd.call('copies.rollback', { path: row.path });
          PyCmd.closeSheet();
          PyCmd.toast(got.ok ? (got.note || 'Swapping…')
                             : (got.error || 'that did not work'));
        },
      }),
      PyCmd.el('button', { text: 'Cancel', onclick: PyCmd.closeSheet }))));
}
