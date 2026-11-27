/*
 * The Board panel in a real browser, against the real plugin (main.py through
 * tools/creator_bridge.py): a mouse on a desktop, and fingers on a phone.
 */
const path = require('path');
const fs = require('fs');
const os = require('os');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const PANEL = path.join(ROOT, 'app/src/main/assets/plugins/board/ui.html');
const BRIDGE = path.join(__dirname, 'creator_bridge.py');
const STATE = fs.mkdtempSync(path.join(os.tmpdir(), 'board-ui-'));
let failures = 0;
const check = (name, ok, detail) => {
  console.log((ok ? '  PASS  ' : '  FAIL  ') + name + (ok ? '' : '  ' + JSON.stringify(detail)));
  if (!ok) failures += 1;
};
async function openPanel(browser, options) {
  const page = await browser.newPage(options);
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.exposeFunction('__call', (name, payload) =>
    execFileSync(process.env.PYTHON || 'python3', [BRIDGE, STATE, name, 'board'], { input: payload, encoding: 'utf-8' }));
  await page.addInitScript(() => {
    window.pycmd = { call: (n, p) => window.__call(n, JSON.stringify(p || {})).then(JSON.parse),
      toast: () => {}, log: () => {}, on: () => {}, theme: () => ({}) };
  });
  await page.goto('file://' + PANEL);
  await page.waitForFunction(() => document.querySelectorAll('.card').length > 0, null, { timeout: 20000 });
  return { page, errors };
}
const centre = (page, sel) => page.evaluate((s) => { const r = document.querySelector(s).getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }, sel);

(async () => {
  const browser = await chromium.launch();
  console.log('== Board, with a mouse ==');
  const { page, errors } = await openPanel(browser, { viewport: { width: 1300, height: 820 } });
  const q = (fn, a) => page.evaluate(fn, a);
  check('a first board has a welcome: three cards and an arrow',
    await q(() => document.querySelectorAll('.card').length === 3 && document.querySelectorAll('#links g').length === 1));

  await q(() => document.querySelector('[data-add=note]').click());
  await page.waitForTimeout(150);
  await page.keyboard.type('Buy milk');
  await page.mouse.click(5, 300);
  check('+ Note adds a note you can type in', await q(() => [...document.querySelectorAll('.card.note .text')].some((t) => t.innerText === 'Buy milk')));

  const before = await q(() => { const c = document.querySelector('.card[data-id=c2]'); return c.offsetLeft; });
  const at = await centre(page, '.card[data-id=c2]');
  await page.mouse.move(at.x, at.y); await page.mouse.down(); await page.mouse.move(at.x + 120, at.y + 40, { steps: 6 }); await page.mouse.up();
  check('a card drags', await q(() => document.querySelector('.card[data-id=c2]').offsetLeft) > before + 60);

  await page.mouse.click(at.x + 120, at.y + 40);
  const dot = await centre(page, '.card[data-id=c2] .dot');
  const to = await centre(page, '.card[data-id=c1]');
  await page.mouse.move(dot.x, dot.y); await page.mouse.down(); await page.mouse.move(to.x, to.y, { steps: 8 }); await page.mouse.up();
  check('dragging the dot onto a card connects them', await q(() => document.querySelectorAll('#links g').length) === 2);

  await q(() => document.getElementById('bUndo').click());
  check('undo takes the arrow away', await q(() => document.querySelectorAll('#links g').length) === 1);

  await q(() => { const s = [...document.querySelectorAll('.swatch')].find((x) => x.dataset.c === 'pink'); s.click(); });
  check('a colour paints the selected card', await q(() => document.querySelector('.card[data-id=c2]').classList.contains('pink')));

  await q(() => { const b = document.querySelector('.card.todo .add-item'); b.click(); });
  await page.waitForTimeout(150);
  await page.keyboard.type('Ship it');
  await page.keyboard.press('Escape');
  check('a to-do list takes new items', await q(() => [...document.querySelectorAll('.item span')].some((s) => s.innerText === 'Ship it')));
  await q(() => document.querySelector('.item input').click());

  const z = await q(() => document.getElementById('zLabel').textContent);
  await page.mouse.move(650, 500); await page.mouse.wheel(0, -300);
  check('the wheel zooms', await q(() => document.getElementById('zLabel').textContent) !== z);

  await page.waitForTimeout(1200);
  const saved = JSON.parse(execFileSync('python3', [BRIDGE, STATE, 'load', 'board'], { input: '{}', encoding: 'utf-8' }));
  check('it saves itself', saved.board.cards.length === 4 && saved.board.cards.some((c) => c.text === 'Buy milk'), saved.board.cards.length);

  const md = await q(() => window.pycmd.call('export_markdown', { board: { name: 'Plan', cards: [{ id: 'a', type: 'todo', text: 'T', items: [{ t: 'x', done: true }], x: 0, y: 0 }], links: [] } }));
  check('Export writes a Markdown file', md.ok && fs.readFileSync(path.join(STATE, md.path), 'utf-8').includes('- [x] x'), md);
  check('no page errors with a mouse', errors.length === 0, errors);

  console.log('== Board, with fingers (the phone app) ==');
  const phone = await openPanel(browser, { viewport: { width: 400, height: 800 }, hasTouch: true, isMobile: true,
    userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36' });
  const pq = (fn, a) => phone.page.evaluate(fn, a);
  check('a plain page on Android, with a tall board', await pq(() => !document.documentElement.classList.contains('shell') && document.getElementById('vp').offsetHeight >= 460));
  check('the board owns its drags (the app keeps its hands off)', await pq(() => getComputedStyle(document.getElementById('vp')).touchAction === 'none'));
  const count = await pq(() => document.querySelectorAll('.card').length);
  await pq(() => document.getElementById('zFit').click());
  const box = await pq(() => { const r = document.getElementById('vp').getBoundingClientRect(); return { x: r.x + 14, y: Math.min(r.bottom, innerHeight) - 30 }; });
  await phone.page.touchscreen.tap(box.x, box.y); await phone.page.waitForTimeout(120); await phone.page.touchscreen.tap(box.x, box.y);
  await phone.page.waitForTimeout(300);
  check('a double tap on the board adds a note', await pq(() => document.querySelectorAll('.card').length) === count + 1);
  check('no page errors with fingers', phone.errors.length === 0, phone.errors);

  await browser.close();
  fs.rmSync(STATE, { recursive: true, force: true });
  console.log(failures ? `\n${failures} board checks failed` : '\nall board checks passed');
  process.exit(failures ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
