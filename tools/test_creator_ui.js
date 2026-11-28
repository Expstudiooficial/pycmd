/*
 * Creator's panel in a real browser, against the real plugin.
 *
 * The page gets the same `pycmd.call` it has in the app; each call runs the
 * plugin's own export in Python (tools/creator_bridge.py), so what is tested is
 * the panel and main.py together - not a copy of either.
 */
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const PANEL = path.join(ROOT, 'app/src/main/assets/plugins/creator/ui.html');
const BRIDGE = path.join(__dirname, 'creator_bridge.py');
const STATE = fs.mkdtempSync(path.join(require('os').tmpdir(), 'creator-ui-'));
let failures = 0;
const check = (name, ok, detail) => {
  console.log((ok ? '  PASS  ' : '  FAIL  ') + name + (ok ? '' : '  ' + JSON.stringify(detail)));
  if (!ok) failures += 1;
};

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1300, height: 800 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.exposeFunction('__creatorCall', (name, payload) =>
    execFileSync(process.env.PYTHON || 'python3', [BRIDGE, STATE, name], { input: payload, encoding: 'utf-8' }));
  await page.addInitScript(() => {
    window.pycmd = {
      call: (name, payload) => window.__creatorCall(name, JSON.stringify(payload || {})).then(JSON.parse),
      toast: () => {}, log: () => {}, on: () => {}, theme: () => ({}),
    };
  });
  await page.goto('file://' + PANEL);
  await page.waitForFunction(() => document.querySelectorAll('.blk').length > 0, null, { timeout: 20000 });
  const q = (fn, arg) => page.evaluate(fn, arg);

  console.log('== Creator panel ==');
  check('eleven languages, PyCmd first', await q(() => document.querySelectorAll('#langs .chip').length) === 11);
  check('the palette is full', await q(() => document.querySelectorAll('.pal').length) > 100);
  check('the example is on screen', await q(() => document.querySelectorAll('.blk').length) >= 3);
  await page.waitForFunction(() => /print/.test(document.getElementById('codeView').innerText));
  check('the code keeps its spaces', await q(() => /for i in range/.test(document.getElementById('codeView').innerText)));

  const before = await q(() => document.querySelectorAll('.blk').length);
  await q(() => { document.getElementById('search').value = 'print text'; document.getElementById('search').dispatchEvent(new Event('input')); });
  await q(() => document.querySelector('.pal').click());
  check('clicking a block adds it', await q(() => document.querySelectorAll('.blk').length) === before + 1);
  await q(() => document.getElementById('undo').click());
  check('undo takes it away', await q(() => document.querySelectorAll('.blk').length) === before);
  await q(() => document.getElementById('redo').click());
  check('redo puts it back', await q(() => document.querySelectorAll('.blk').length) === before + 1);

  await q(() => document.getElementById('bRun').click());
  await page.waitForFunction(() => /finished|stopped/.test((document.getElementById('out') || {}).innerText || ''));
  check('Run runs the Python', await q(() => /Hello from PyCmd/.test(document.getElementById('out').innerText)));

  await q(() => document.getElementById('bImport').click());
  await q(() => { document.querySelector('#sheetBody textarea').value = 'n = input("n? ")\nprint("hi", n)\nprint(1 / 0)\n'; });
  await q(() => [...document.querySelectorAll('#sheetBody button')].find((b) => /new script/.test(b.textContent)).click());
  await page.waitForFunction(() => document.querySelectorAll('.blk').length === 3);
  check('imported code becomes blocks', true);
  await q(() => { const t = document.querySelector('#runView textarea'); t.value = 'Ann'; t.dispatchEvent(new Event('input')); });
  await q(() => document.getElementById('bRun').click());
  await page.waitForFunction(() => /stopped/.test((document.getElementById('out') || {}).innerText || ''));
  const out = await q(() => document.getElementById('out').innerText);
  check('input() reads the Input box', /hi Ann/.test(out), out);
  check('the failing line is named', /ZeroDivisionError[\s\S]*line 3/.test(out), out);
  check('and its block is selected', await q(() => /1 \/ 0/.test((document.querySelector('.blk.sel input') || {}).value || '')));

  await q(() => [...document.querySelectorAll('#langs .chip')].find((c) => c.textContent === 'JavaScript').click());
  await page.waitForFunction(() => document.querySelector('#langs .chip.on').textContent === 'JavaScript');
  await page.waitForTimeout(300);
  await q(() => document.getElementById('bRun').click());
  await page.waitForFunction(() => /finished|stopped/.test((document.getElementById('out') || {}).innerText || ''));
  check('JavaScript runs in the panel', await q(() => /Hello from PyCmd/.test(document.getElementById('out').innerText)));

  await page.setViewportSize({ width: 400, height: 780 });
  check('a phone gets the tab bar', await q(() => getComputedStyle(document.getElementById('nav')).display) === 'flex');
  check('no page errors', errors.length === 0, errors);

  // The phone app's WebView: a plain page, no viewport-filling shell.
  const phone = await browser.newPage({ viewport: { width: 400, height: 780 },
    userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36' });
  await phone.exposeFunction('__creatorCall', (name, payload) =>
    execFileSync(process.env.PYTHON || 'python3', [BRIDGE, STATE, name], { input: payload, encoding: 'utf-8' }));
  await phone.addInitScript(() => {
    window.pycmd = { call: (n, p) => window.__creatorCall(n, JSON.stringify(p || {})).then(JSON.parse),
      toast: () => {}, log: () => {}, on: () => {}, theme: () => ({}) };
  });
  await phone.goto('file://' + PANEL);
  await phone.waitForFunction(() => document.querySelectorAll('.blk').length > 0, null, { timeout: 20000 });
  const laid = await phone.evaluate(() => ({ shell: document.documentElement.classList.contains('shell'),
    tree: document.getElementById('tree').offsetHeight, overflow: getComputedStyle(document.body).overflowY }));
  check('on Android it is a plain page, not a shell', !laid.shell && laid.overflow !== 'hidden', laid);
  check('and the script has height', laid.tree > 100, laid);
  await phone.evaluate(() => document.querySelector('.nav [data-v=blocks]').click());
  check('the Blocks tab shows the palette', await phone.evaluate(() => document.querySelector('.palette').offsetHeight > 200));

  await browser.close();
  fs.rmSync(STATE, { recursive: true, force: true });
  console.log(failures ? `\n${failures} creator panel checks failed` : '\nall creator panel checks passed');
  process.exit(failures ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
