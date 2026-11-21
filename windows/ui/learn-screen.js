/*
  PyCmd Learn.

  The phone's lessons, plus the courses only a PC can run, marked by running
  the answer when the language is installed. Three views on one screen: the
  catalogue, a course's map, and the lesson player. Keys: 1-4 pick a choice,
  Enter checks or moves on, Ctrl+Enter checks written code, Esc goes back.
*/
'use strict';

const learn = {
  view: 'home',          // home | course | lesson
  course: '',
  lesson: null,
  queue: [],             // review mode: lessons still to do
  filter: 'all',
  query: '',
  picked: null,
  answered: false,
  order: [],
  runners: {},
  catalogue: null,
};

const KIND_LABEL = {
  read: 'Read', predict: 'Predict', which: 'Which prints it', fill: 'Fill the gap',
  bug: 'Find the bug', order: 'Put in order', write: 'Write it',
};
const KIND_MARK = { read: '◇', predict: '?', which: '≡', fill: '_', bug: '✗', order: '⇅', write: '✎' };

async function Learn(screen) {
  if (learn.view === 'lesson' && learn.lesson) return learnLesson(screen);
  if (learn.view === 'course' && learn.course) return learnCourse(screen);
  return learnHome(screen);
}

function learnGo(view, extra) {
  Object.assign(learn, { view }, extra || {});
  go('learn');
}

// ---------------------------------------------------------------------------
// The catalogue
// ---------------------------------------------------------------------------

async function learnHome(screen) {
  const reply = await PyCmd.call('learn', {});
  if (!reply.ok) {
    screen.appendChild(el('div', { class: 'empty', text: reply.error || 'Learn could not load.' }));
    return;
  }
  learn.catalogue = reply;
  learn.runners = reply.runners || {};
  const t = reply.totals || {};
  screen.appendChild(head('PyCmd Learn',
    `${(t.courses || 0)} languages, ${(t.lessons || 0).toLocaleString()} lessons. `
    + 'Where the language is installed, your answer is marked by running it.'));

  const pct = t.lessons ? Math.round((t.done / t.lessons) * 1000) / 10 : 0;
  const goalPct = Math.min(100, Math.round(((t.today_count || 0) / (t.goal || 10)) * 100));
  const stats = el('div', { class: 'tiles' },
    labTile('Done', `${(t.done || 0).toLocaleString()} · ${pct}%`, t.done ? 'good' : ''),
    labTile('XP', String(t.xp || 0), ''),
    labTile('Streak', `${t.streak || 0} day${t.streak === 1 ? '' : 's'} · best ${t.best_streak || 0}`,
      t.today ? 'good' : ''),
    labTile('Today', `${t.today_count || 0} of ${t.goal || 10}`, goalPct >= 100 ? 'good' : ''));
  const goal = el('div', { class: 'row wrap' },
    el('span', { class: 'muted', text: 'Daily goal' }),
    el('button', { class: 'small', text: '−', onclick: () => learnSetGoal((t.goal || 10) - 5) }),
    el('b', { text: String(t.goal || 10) }),
    el('button', { class: 'small', text: '+', onclick: () => learnSetGoal((t.goal || 10) + 5) }),
    el('div', { class: 'progress grow' }, el('div', { class: 'fill', style: `width:${goalPct}%` })));
  screen.appendChild(card(stats, goal));

  const quick = el('div', { class: 'row wrap' });
  if (t.continue && t.continue.course) {
    quick.appendChild(el('button', { class: 'small primary',
      text: `Continue ${t.continue.language}: ${t.continue.title}`,
      onclick: () => learnOpen(t.continue.course, t.continue.lesson) }));
  }
  if (t.missed) {
    quick.appendChild(el('button', { class: 'small', text: `Review ${t.missed} missed`,
      onclick: learnReview }));
  }
  if (quick.childNodes.length) screen.appendChild(card(quick));

  const search = el('input', { placeholder: 'Search every lesson - "loops", "closures", "hash map"…',
    value: learn.query });
  const results = el('div', { class: 'list', hidden: true });
  let timer = 0;
  search.addEventListener('input', () => {
    clearTimeout(timer);
    learn.query = search.value;
    timer = setTimeout(() => learnSearch(search.value, results), 220);
  });
  screen.appendChild(card(search, results));
  if (learn.query) learnSearch(learn.query, results);

  const filters = el('div', { class: 'row wrap' });
  [['all', 'All'], ['started', 'Started'], ['runs', 'Marked by running here'],
   ['windows', 'PC only'], ['phone', 'Also on the phone']].forEach(([id, name]) => {
    filters.appendChild(el('button', {
      class: 'small' + (learn.filter === id ? ' primary' : ''), text: name,
      onclick: () => { learn.filter = id; go('learn'); } }));
  });
  screen.appendChild(filters);

  const grid = el('div', { class: 'course-grid' });
  (reply.courses || [])
    .filter((c) => learnKeep(c))
    .forEach((c) => {
      const done = c.lessons ? Math.round((c.done / c.lessons) * 100) : 0;
      const runs = (learn.runners[c.id] || {}).marked;
      grid.appendChild(el('button', { class: 'course-card', onclick: () => learnGo('course', { course: c.id }) },
        el('div', { class: 'row spread' },
          el('b', { text: c.name }),
          el('span', { class: 'muted small-text', text: c.extension })),
        el('div', { class: 'muted small-text clamp', text: c.blurb }),
        el('div', { class: 'row wrap tags' },
          c.windowsOnly ? el('span', { class: 'tag', text: 'PC only' }) : null,
          runs ? el('span', { class: 'tag good', text: 'runs here' }) : null),
        el('div', { class: 'progress' }, el('div', { class: 'fill', style: `width:${done}%` })),
        el('div', { class: 'muted small-text', text: `${c.done} of ${c.lessons} · ${c.units} units` })));
    });
  if (!grid.childNodes.length) grid.appendChild(el('div', { class: 'empty', text: 'Nothing matches that filter.' }));
  screen.appendChild(grid);
}

function learnKeep(c) {
  const runs = (learn.runners[c.id] || {}).marked;
  if (learn.filter === 'started') return c.done > 0;
  if (learn.filter === 'runs') return runs;
  if (learn.filter === 'windows') return c.windowsOnly;
  if (learn.filter === 'phone') return !c.windowsOnly;
  return true;
}

async function learnSetGoal(value) {
  await PyCmd.call('learn.goal', { goal: Math.max(5, Math.min(200, value)) });
  go('learn');
}

async function learnSearch(text, into) {
  PyCmd.clear(into);
  if (!text.trim()) { into.hidden = true; return; }
  const reply = await PyCmd.call('learn.search', { text });
  const hits = reply.hits || [];
  into.hidden = false;
  if (!hits.length) {
    into.appendChild(el('div', { class: 'row-item muted', text: 'No lesson mentions that.' }));
    return;
  }
  hits.slice(0, 30).forEach((hit) => {
    into.appendChild(el('button', { class: 'row-item', onclick: () => learnOpen(hit.course, hit.lesson) },
      el('span', { class: 'tag', text: hit.language }),
      el('span', { class: 'grow', text: hit.title }),
      el('span', { class: 'muted small-text', text: hit.unit || '' })));
  });
}

async function learnReview() {
  const reply = await PyCmd.call('learn.review', {});
  const rows = reply.lessons || [];
  if (!rows.length) { PyCmd.toast('Nothing to review - every miss has been put right.'); return; }
  learn.queue = rows.slice(1);
  learnOpen(rows[0].course, rows[0].lesson, true);
}

// ---------------------------------------------------------------------------
// A course's map
// ---------------------------------------------------------------------------

async function learnCourse(screen) {
  const c = await PyCmd.call('learn.course', { course: learn.course });
  if (!c.ok) { learnGo('home'); return; }
  const runs = (learn.runners[c.id] || {}).marked;
  screen.appendChild(el('div', { class: 'row' },
    el('button', { class: 'small', text: '← All languages', onclick: () => learnGo('home') })));
  screen.appendChild(head(c.name, c.blurb));
  const pct = c.total ? Math.round((c.done / c.total) * 100) : 0;
  const firstOpen = c.units.flatMap((u) => u.lessons).find((l) => !l.done);
  screen.appendChild(card(
    el('div', { class: 'row wrap spread' },
      el('div', {},
        el('b', { text: `${c.done} of ${c.total} lessons` }),
        el('div', { class: 'muted small-text', text: runs
          ? 'Your written answers are marked by running them on this PC.'
          : (c.runsHere ? 'Installed here - try any lesson.'
            : 'Not installed here: written answers are compared with the model answer. '
              + 'The Toolchains tab can install it.') })),
      el('div', { class: 'row' },
        firstOpen ? el('button', { class: 'small primary', text: c.done ? 'Carry on' : 'Start',
          onclick: () => learnOpen(c.id, firstOpen.id) }) : el('span', { class: 'tag good', text: 'Finished' }),
        el('button', { class: 'small danger', text: 'Reset', onclick: async () => {
          if (!confirm(`Forget your progress in ${c.name}?`)) return;
          await PyCmd.call('learn.reset', { course: c.id });
          go('learn');
        } }))),
    el('div', { class: 'progress' }, el('div', { class: 'fill', style: `width:${pct}%` }))));

  c.units.forEach((unit, index) => {
    const done = unit.lessons.filter((l) => l.done).length;
    const body = el('div', { class: 'lchips' });
    unit.lessons.forEach((l) => {
      body.appendChild(el('button', {
        class: 'lchip' + (l.done ? ' done' : ''), title: `${KIND_LABEL[l.kind] || l.kind}: ${l.title}`,
        onclick: () => learnOpen(c.id, l.id),
      }, el('span', { class: 'k', text: KIND_MARK[l.kind] || '·' }), el('span', { text: l.title })));
    });
    const allDone = done === unit.lessons.length;
    const details = el('details', { class: 'card unit', open: !allDone && index < 12 },
      el('summary', {},
        el('span', { class: 'grow' }, el('b', { text: unit.title }),
          unit.goal ? el('span', { class: 'muted', text: '  ' + unit.goal }) : null),
        el('span', { class: 'muted small-text', text: `${done}/${unit.lessons.length}` })),
      body);
    screen.appendChild(details);
  });
}

// ---------------------------------------------------------------------------
// The lesson player
// ---------------------------------------------------------------------------

async function learnOpen(course, lessonId, reviewing) {
  const lesson = await PyCmd.call('learn.lesson', { course, lesson: lessonId });
  if (!lesson.ok) { PyCmd.toast(lesson.error || 'That lesson is not there.'); return; }
  if (!reviewing) learn.queue = learn.queue.filter((q) => !(q.course === course && q.lesson === lessonId));
  Object.assign(learn, { view: 'lesson', course, lesson, picked: null, answered: false,
    order: lesson.kind === 'order' ? [] : [] });
  go('learn');
}

function learnCode(text, cls) {
  return el('pre', { class: 'out mono codebox ' + (cls || ''), text });
}

async function learnLesson(screen) {
  const l = learn.lesson;
  const top = el('div', { class: 'row wrap spread' },
    el('div', { class: 'row' },
      el('button', { class: 'small', text: '← ' + l.language, onclick: () => learnGo('course', { course: l.course }) }),
      el('span', { class: 'tag', text: (KIND_MARK[l.kind] || '') + ' ' + (KIND_LABEL[l.kind] || l.kind) }),
      learn.queue.length ? el('span', { class: 'tag warn', text: `review · ${learn.queue.length} more` }) : null),
    el('span', { class: 'muted small-text', text: `${l.index + 1} of ${l.total}` + (l.done ? ' · done' : '') }));
  screen.appendChild(top);
  screen.appendChild(el('div', { class: 'progress thin' },
    el('div', { class: 'fill', style: `width:${Math.round(((l.index + 1) / l.total) * 100)}%` })));
  screen.appendChild(el('h1', { text: l.title }));

  const body = el('div', { class: 'card lesson' });
  const feedback = el('div', { class: 'feedback', hidden: true });
  const actions = el('div', { class: 'row wrap' });
  screen.appendChild(body);
  screen.appendChild(feedback);
  screen.appendChild(actions);

  const kind = l.kind;
  if (kind === 'read') {
    body.appendChild(el('p', { class: 'teach', html: learnInline(l.teach) }));
    body.appendChild(learnTry(l, l.code));
    if (l.output) body.appendChild(el('div', {}, el('div', { class: 'muted small-text', text: 'It prints' }),
      learnCode(l.output, 'printed')));
    if (l.note) body.appendChild(el('p', { class: 'muted', text: l.note }));
    actions.appendChild(el('button', { class: 'small primary', text: 'Got it - next (Enter)',
      onclick: () => learnAnswer('', feedback, actions) }));
  } else if (kind === 'predict' || kind === 'fill' || kind === 'which') {
    body.appendChild(el('p', { class: 'teach', text: l.prompt }));
    if (l.code) body.appendChild(learnCode(l.code));
    const opts = el('div', { class: 'options' + (kind === 'which' ? ' code-options' : '') });
    l.options.forEach((option, index) => {
      const button = el('button', { class: 'opt', 'data-i': String(index),
        onclick: () => { if (!learn.answered) learnAnswer(option, feedback, actions, button); } },
        el('span', { class: 'n', text: String(index + 1) }),
        kind === 'which' ? learnCode(option) : el('span', { class: 'mono', text: option }));
      opts.appendChild(button);
    });
    body.appendChild(opts);
  } else if (kind === 'bug') {
    body.appendChild(el('p', { class: 'teach', text: l.prompt + ' Click it.' }));
    const lines = el('div', { class: 'bug-lines' });
    l.options.forEach((line, index) => {
      const button = el('button', { class: 'opt line mono', 'data-i': String(index),
        onclick: () => { if (!learn.answered) learnAnswer(line, feedback, actions, button); } },
        el('span', { class: 'n', text: String(index + 1) }), el('span', { text: line || ' ' }));
      lines.appendChild(button);
    });
    body.appendChild(lines);
  } else if (kind === 'order') {
    body.appendChild(el('p', { class: 'teach', text: l.prompt + ' Click the lines in the order they run.' }));
    const built = el('div', { class: 'order-built' });
    const pool = el('div', { class: 'order-pool' });
    const draw = () => {
      PyCmd.clear(built); PyCmd.clear(pool);
      learn.order.forEach((i, position) => built.appendChild(el('button', { class: 'opt line mono',
        onclick: () => { if (!learn.answered) { learn.order.splice(position, 1); draw(); } } },
        el('span', { class: 'n', text: String(position + 1) }), el('span', { text: l.lines[i] }))));
      l.lines.forEach((line, i) => {
        if (learn.order.includes(i)) return;
        pool.appendChild(el('button', { class: 'opt line mono',
          onclick: () => { if (!learn.answered) { learn.order.push(i); draw(); } } }, el('span', { text: line })));
      });
      if (!built.childNodes.length) built.appendChild(el('div', { class: 'muted small-text', text: 'Your program appears here.' }));
    };
    draw();
    body.appendChild(el('div', { class: 'muted small-text', text: 'Your program' }));
    body.appendChild(built);
    body.appendChild(el('div', { class: 'muted small-text', text: 'Lines left' }));
    body.appendChild(pool);
    actions.appendChild(el('button', { class: 'small primary', text: 'Check (Enter)', onclick: () => {
      if (learn.order.length !== l.lines.length) { PyCmd.toast('Use every line first.'); return; }
      learnAnswer(learn.order.map((i) => l.lines[i]).join('\n'), feedback, actions);
    } }));
    actions.appendChild(el('button', { class: 'small', text: 'Start over', onclick: () => { learn.order = []; draw(); } }));
  } else if (kind === 'write') {
    const marked = l.graded === 'run';
    body.appendChild(el('p', { class: 'teach', text: l.prompt }));
    body.appendChild(el('p', { class: 'muted small-text', text: marked
      ? 'Marked by running it here - any program that prints that is right.'
      : 'Compared with the model answer, ignoring spaces and quote style.' }));
    if (l.hint) body.appendChild(el('p', { class: 'muted', text: l.hint }));
    const box = el('textarea', { class: 'plain mono answer', rows: '10', spellcheck: 'false',
      placeholder: 'Write it here. Ctrl+Enter checks.' });
    box.value = l.starter || '';
    box.addEventListener('keydown', (event) => {
      if (event.key === 'Tab') {
        event.preventDefault();
        const at = box.selectionStart;
        box.value = box.value.slice(0, at) + '    ' + box.value.slice(box.selectionEnd);
        box.selectionStart = box.selectionEnd = at + 4;
      }
      if (event.key === 'Enter' && event.ctrlKey) { event.preventDefault(); learnAnswer(box.value, feedback, actions); }
    });
    body.appendChild(box);
    setTimeout(() => box.focus(), 50);
    actions.appendChild(el('button', { class: 'small primary', text: marked ? 'Run and check (Ctrl+Enter)' : 'Check (Ctrl+Enter)',
      onclick: () => learnAnswer(box.value, feedback, actions) }));
    actions.appendChild(el('button', { class: 'small', text: 'Show me', onclick: () => {
      feedback.hidden = false;
      PyCmd.clear(feedback);
      feedback.className = 'feedback card';
      feedback.appendChild(el('div', { class: 'muted small-text', text: 'One answer that works' }));
      feedback.appendChild(learnCode(l.code || '(this lesson has no model answer)'));
      feedback.appendChild(el('button', { class: 'small', text: 'Put it in the box', onclick: () => { box.value = l.code || ''; box.focus(); } }));
    } }));
  }

  const tail = el('div', { class: 'row wrap lesson-nav' },
    l.previous ? el('button', { class: 'small', text: '← Previous', onclick: () => learnOpen(l.course, l.previous) }) : null,
    el('button', { class: 'small', text: 'Open in the editor', onclick: () => learnToEditor(l) }),
    l.next ? el('button', { class: 'small', text: 'Skip →', onclick: () => learnNext() }) : null);
  screen.appendChild(tail);
}

function learnInline(text) {
  // `code` in a lesson's explanation is shown as code. Everything else is text.
  const safe = String(text || '').replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  return safe.replace(/`([^`]+)`/g, '<code>$1</code>');
}

function learnTry(l, code) {
  const wrap = el('div', { class: 'try' });
  const box = el('textarea', { class: 'plain mono', rows: String(Math.min(16, Math.max(3, code.split('\n').length + 1))),
    spellcheck: 'false' });
  box.value = code;
  const out = el('pre', { class: 'out mono', hidden: true });
  const tryable = (learn.runners[l.course] || {}).tryable;
  const run = el('button', { class: 'small' + (tryable ? ' good' : ''), text: tryable ? '▶ Run it' : '▶ Run it (not installed)',
    onclick: async () => {
      run.disabled = true;
      out.hidden = false;
      out.textContent = 'Running…';
      const reply = await PyCmd.call('learn.try', { course: l.course, code: box.value });
      run.disabled = false;
      if (!reply.ok) { out.textContent = reply.error; return; }
      out.textContent = (reply.output || '') + (reply.error ? '\n' + reply.error : '')
        || '(it printed nothing)';
    } });
  wrap.appendChild(box);
  wrap.appendChild(el('div', { class: 'row' }, run,
    el('span', { class: 'muted small-text', text: 'Change it and run it again - that is how it sticks.' })));
  wrap.appendChild(out);
  return wrap;
}

async function learnAnswer(answer, feedback, actions, button) {
  const l = learn.lesson;
  const reply = await PyCmd.call('learn.check', { course: l.course, lesson: l.id, answer });
  if (!reply.ok) { PyCmd.toast(reply.error || 'It could not be marked.'); return; }
  const right = !!reply.right;
  if (l.kind !== 'write' && l.kind !== 'read') learn.answered = true;
  if (button) button.classList.add(right ? 'right' : 'wrong');
  if (!right && l.kind !== 'write' && l.kind !== 'read') {
    document.querySelectorAll('.opt').forEach((node) => {
      const text = node.textContent.replace(/^\d+/, '');
      if (reply.expected && (text.trim() === String(reply.expected).trim())) node.classList.add('right');
    });
  }
  if (l.kind === 'read') { await PyCmd.call('learn.complete', { course: l.course, lesson: l.id }); learnNext(); return; }

  feedback.hidden = false;
  PyCmd.clear(feedback);
  feedback.className = 'feedback card ' + (right ? 'good-box' : 'bad-box');
  feedback.appendChild(el('b', { text: right ? 'Right.' : 'Not yet.' }));
  feedback.appendChild(el('span', { text: '  ' + (reply.message || '') }));
  if (reply.output !== undefined && reply.ran) {
    feedback.appendChild(el('div', { class: 'muted small-text', text: 'Your program printed' }));
    feedback.appendChild(learnCode(reply.output || '(nothing)'));
  }
  if (!right && reply.expected && l.kind !== 'predict' && l.kind !== 'which') {
    feedback.appendChild(el('div', { class: 'muted small-text', text: l.kind === 'write' && !reply.ran ? 'The model answer' : 'Expected' }));
    feedback.appendChild(learnCode(String(reply.expected)));
  }
  if (right) {
    const done = await PyCmd.call('learn.complete', { course: l.course, lesson: l.id });
    if (done.fresh) feedback.appendChild(el('span', { class: 'muted', text: `  +10 XP · ${done.today_count}/${done.goal} today` }));
    PyCmd.clear(actions);
    actions.appendChild(el('button', { class: 'small primary', id: 'learnNext', text: 'Next (Enter)', onclick: learnNext }));
  } else if (l.kind !== 'write') {
    PyCmd.clear(actions);
    actions.appendChild(el('button', { class: 'small primary', id: 'learnNext', text: 'Next (Enter)', onclick: learnNext }));
    actions.appendChild(el('button', { class: 'small', text: 'Try again', onclick: () => learnOpen(l.course, l.id) }));
  }
}

function learnNext() {
  if (learn.queue.length) {
    const next = learn.queue.shift();
    learnOpen(next.course, next.lesson, true);
    return;
  }
  const l = learn.lesson;
  if (l && l.next) learnOpen(l.course, l.next);
  else { PyCmd.toast('That is the end of the course. Well done.'); learnGo('course', { course: l.course }); }
}

async function learnToEditor(l) {
  const got = await PyCmd.call('learn.snippet', { course: l.course, lesson: l.id });
  if (!got.ok) { PyCmd.toast(got.error); return; }
  const path = 'learn/' + got.name;
  const saved = await PyCmd.call('file.write', { path, text: got.code });
  if (saved.ok === false) { PyCmd.toast(saved.error || 'It could not be saved.'); return; }
  openInEditor(path, false);
}

document.addEventListener('keydown', (event) => {
  if (PyCmd.state.tab !== 'learn' || learn.view !== 'lesson') return;
  const target = event.target;
  const typing = target && (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT');
  if (event.key === 'Escape') { learnGo('course', { course: learn.course }); return; }
  if (typing) return;
  if (/^[1-9]$/.test(event.key)) {
    const option = document.querySelector(`.opt[data-i="${Number(event.key) - 1}"]`);
    if (option) option.click();
  }
  if (event.key === 'Enter') {
    const next = document.getElementById('learnNext') || document.querySelector('.lesson ~ .row .primary');
    if (next) { event.preventDefault(); next.click(); }
  }
});
