/*
 * The built-in Notes board (assets/web/board.html) in a real browser, against
 * the real engine (pycmd_board through tools/board_bridge.py). Real mouse
 * double-clicks and real taps - 3.6 passed a test that faked the double-click
 * and could not edit text on a real screen.
 */
const path = require('path');
const fs = require('fs');
const os = require('os');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const PAGE = path.join(ROOT, 'app/src/main/assets/web/board.html');
const BRIDGE = path.join(__dirname, 'board_bridge.py');
const WS = fs.mkdtempSync(path.join(os.tmpdir(), 'board-ui-'));
let failures = 0;
const check = (name, ok, detail) => {
  console.log((ok ? '  PASS  ' : '  FAIL  ') + name + (ok ? '' : '  ' + JSON.stringify(detail)));
  if (!ok) failures += 1;
};
const engine = (name, body) => JSON.parse(execFileSync(process.env.PYTHON || 'python3', [BRIDGE, WS, name], { input: JSON.stringify(body || {}), encoding: 'utf-8' }));
async function openBoard(browser, options) {
  const page = await browser.newPage(options);
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.exposeFunction('__board', (name, payload) => execFileSync(process.env.PYTHON || 'python3', [BRIDGE, WS, name], { input: payload, encoding: 'utf-8' }));
  await page.addInitScript(() => { window.PyBoard = { call: (n, p) => window.__board(n, JSON.stringify(p || {})).then(JSON.parse) }; });
  await page.goto('file://' + PAGE);
  await page.waitForFunction(() => document.querySelectorAll('.card').length > 0, null, { timeout: 20000 });
  return { page, errors };
}
const box = (page, sel) => page.evaluate((s) => { const r = document.querySelector(s).getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2, l: r.x, t: r.y, w: r.width, h: r.height }; }, sel);
const cardWith = (text) => `.card:has(.text)`;

(async () => {
  const browser = await chromium.launch();
  console.log('== Notes board, with a mouse ==');
  const { page, errors } = await openBoard(browser, { viewport: { width: 1300, height: 820 } });
  const q = (fn, a) => page.evaluate(fn, a);
  check('a first board has a welcome', await q(() => document.querySelectorAll('.card').length === 3 && document.querySelectorAll('#links g').length === 1));

  const note = await box(page, '.card.note');
  await page.mouse.dblclick(note.x, note.y);
  check('a real double-click opens the text for writing', await q(() => !!document.querySelector('.card.note [contenteditable="true"]')));
  await page.keyboard.press('Control+A'); await page.keyboard.type('Plan the launch');
  await page.mouse.click(40, 760);
  check('what was typed stays', await q(() => document.querySelector('.card.note .text').innerText) === 'Plan the launch');
  await page.mouse.dblclick(note.x, note.y);
  await page.keyboard.press('End'); await page.keyboard.type(' **now**');
  await page.mouse.click(40, 760);
  check('it can be edited again', await q(() => document.querySelector('.card.note .text').innerText) === 'Plan the launch now');
  check('and **bold** shows as bold', await q(() => !!document.querySelector('.card.note .text b')));

  const title = await box(page, '.card.todo .item span');
  await page.mouse.dblclick(title.x, title.y);
  await page.keyboard.press('Control+A'); await page.keyboard.type('First'); await page.keyboard.press('Enter'); await page.keyboard.type('Second');
  await page.mouse.click(40, 760);
  check('to-do items edit, and Enter makes the next one', await q(() => [...document.querySelectorAll('.card.todo .item span')].map((s) => s.innerText).slice(0, 2).join('|')) === 'First|Second');

  const before = await q(() => document.querySelector('.card.note').offsetLeft);
  const n2 = await box(page, '.card.note');
  await page.mouse.move(n2.x, n2.y + 30); await page.mouse.down(); await page.mouse.move(n2.x + 150, n2.y + 60, { steps: 8 }); await page.mouse.up();
  check('a card drags', await q(() => document.querySelector('.card.note').offsetLeft) > before + 80);

  await page.mouse.click(n2.x + 150, n2.y + 60);
  const dot = await box(page, '.card.note .dot'), head = await box(page, '.card.heading');
  await page.mouse.move(dot.x, dot.y); await page.mouse.down(); await page.mouse.move(head.x, head.y, { steps: 8 }); await page.mouse.up();
  check('dragging the dot onto a card connects them', await q(() => document.querySelectorAll('#links g').length) === 2);

  const n3 = await box(page, '.card.note');
  await page.mouse.click(n3.x, n3.y, { button: 'right' });
  check('right-click opens a card menu', await q(() => !!document.querySelector('.menu') && document.querySelector('.menu').innerText.includes('Duplicate')));
  await q(() => [...document.querySelectorAll('.menu button')].find((b) => b.innerText.includes('Duplicate')).click());
  check('Duplicate copies it', await q(() => document.querySelectorAll('.card.note').length) === 2);

  await page.keyboard.press('Control+a');
  check('Ctrl+A selects every card', await q(() => document.querySelectorAll('.card.sel').length) === await q(() => document.querySelectorAll('.card').length));
  await page.keyboard.press('Escape');

  await page.mouse.move(60, 700); await page.keyboard.down('Shift'); await page.mouse.down(); await page.mouse.move(1280, 120, { steps: 6 }); await page.mouse.up(); await page.keyboard.up('Shift');
  check('Shift+drag draws a box that selects', await q(() => document.querySelectorAll('.card.sel').length) >= 2);
  await page.keyboard.press('Escape');

  const empty = { x: 1200, y: 700 };
  const count = await q(() => document.querySelectorAll('.card').length);
  await page.mouse.dblclick(empty.x, empty.y);
  await page.waitForTimeout(120);
  check('a double-click on the board adds a note there', await q(() => document.querySelectorAll('.card').length) === count + 1);
  await page.keyboard.type('Quick'); await page.mouse.click(40, 760);

  await q(() => { const s = document.getElementById('search'); s.value = 'quick'; s.dispatchEvent(new Event('input')); });
  check('Find lights up the card', await q(() => !!document.querySelector('.card.found')));
  await q(() => { const s = document.getElementById('search'); s.value = ''; s.dispatchEvent(new Event('input')); });

  await q(() => document.getElementById('bUndo').click());
  check('undo works', await q(() => !document.getElementById('bRedo').disabled));

  await q(() => document.getElementById('bAdd').click());
  await q(() => [...document.querySelectorAll('.menu button')].find((b) => b.innerText.includes('Section')).click());
  check('+ Add makes a section (a frame)', await q(() => !!document.querySelector('.card.frame')));
  await page.mouse.click(40, 760);

  await q(() => document.getElementById('bNew').click());
  await q(() => [...document.querySelectorAll('.tpl button')].find((b) => b.innerText.includes('Kanban')).click());
  await page.waitForFunction(() => document.querySelectorAll('.card.frame').length === 3);
  check('a new board from the Kanban template', true);

  await q(() => document.getElementById('bExport').click());
  await q(() => [...document.querySelectorAll('.menu button')].find((b) => b.innerText.includes('Picture')).click());
  await page.waitForTimeout(1500);
  check('Export makes a PNG in the workspace', fs.existsSync(path.join(WS, 'boards', 'Kanban.png')) && fs.statSync(path.join(WS, 'boards', 'Kanban.png')).size > 1000);

  await page.waitForTimeout(900);
  const saved = engine('listing');
  check('it all saved', saved.boards.length === 2, saved);
  check('no page errors with a mouse', errors.length === 0, errors);

  console.log('== Notes board, with fingers ==');
  const phone = await openBoard(browser, { viewport: { width: 400, height: 800 }, hasTouch: true, isMobile: true,
    userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36' });
  const pq = (fn, a) => phone.page.evaluate(fn, a);
  await pq(() => document.getElementById('zFit').click());
  const any = await box(phone.page, '.card.frame');
  const tapCount = await pq(() => document.querySelectorAll('.card').length);
  const spot = await pq(() => { const r = document.getElementById('vp').getBoundingClientRect(); return { x: r.x + 12, y: r.bottom - 70 }; });
  await phone.page.touchscreen.tap(spot.x, spot.y); await phone.page.waitForTimeout(90); await phone.page.touchscreen.tap(spot.x, spot.y);
  await phone.page.waitForTimeout(200);
  check('a double tap on the board adds a note, ready to write', await pq(() => document.querySelectorAll('.card').length) === tapCount + 1 && await pq(() => !!document.querySelector('[contenteditable="true"]')));
  await phone.page.keyboard.type('From the phone');
  await phone.page.touchscreen.tap(spot.x + 200, spot.y - 300);
  const t2 = await box(phone.page, '.card.note');
  await phone.page.touchscreen.tap(t2.x, t2.y); await phone.page.waitForTimeout(90); await phone.page.touchscreen.tap(t2.x, t2.y);
  await phone.page.waitForTimeout(150);
  check('a double tap on a card opens its text again', await pq(() => !!document.querySelector('.card.note [contenteditable="true"]')));
  check('no page errors with fingers', phone.errors.length === 0, phone.errors);

  await browser.close();
  fs.rmSync(WS, { recursive: true, force: true });
  console.log(failures ? `\n${failures} board checks failed` : '\nall board checks passed');
  process.exit(failures ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
