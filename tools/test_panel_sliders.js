/*
 * Drags every slider in every bundled panel, with a real finger.
 *
 * This is the check for the bug that shipped in 2.6.0: a panel's sliders did
 * not move. The cause was in the app rather than the page - the touch
 * listener behind the WebView handed the gesture to the app's scrolling list
 * a few pixels into any drag - and the Kotlin half of the fix is covered by
 * `app/src/test/.../PanelGestureTest.kt`, which is arithmetic and can be
 * tested directly.
 *
 * This is the other half: that the page notices a finger landing on a slider
 * and *tells* the app, through the bridge, before the first move arrives. It
 * drives the real panel HTML - built by the plugin runtime, with the real
 * injected bridge - and dispatches real touch events rather than setting
 * `value` from script, so a slider that cannot be dragged fails here.
 *
 * A panel with no sliders is not skipped silently: the count is reported, so
 * "all panels passed" cannot come to mean "no panel was checked".
 */
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const PYTHON = process.env.PYTHON || 'python3.13';
const CHROME = process.env.PYCMD_CHROME
  || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

let chromium = null;
try {
  ({ chromium } = require('playwright-core'));
} catch (error) {
  console.log('  SKIP  panel sliders - playwright-core is not installed');
  process.exit(0);
}
if (!fs.existsSync(CHROME)) {
  console.log('  SKIP  panel sliders - no Chromium at ' + CHROME);
  process.exit(0);
}

let failures = 0;
let sliders = 0;

function check(name, condition, detail) {
  if (condition) {
    console.log(`  PASS  ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL  ${name}  ${detail === undefined ? '' : JSON.stringify(detail)}`);
  }
}

/** Every bundled panel, built through the runtime with its bridge in it. */
function buildPanels(into) {
  const script = `
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(${JSON.stringify(ROOT)}, "app", "src", "main", "python"))
import pycmd_plugins as plugins
scratch = tempfile.mkdtemp()
plugins.configure(os.path.join(scratch, "plugins"),
                  os.path.join(scratch, "workspace"), None)
base = os.path.join(${JSON.stringify(ROOT)}, "app", "src", "main", "assets", "plugins")
made = []
for name in sorted(os.listdir(base)):
    folder = os.path.join(base, name)
    reply = json.loads(plugins.install(folder, name, "1"))
    if not reply.get("ok"):
        continue
    identifier = reply["manifest"]["id"]
    plugins.load(identifier)
    for panel in sorted(f for f in os.listdir(folder) if f.endswith(".html")):
        where = os.path.join(${JSON.stringify(into)}, name + "-" + panel)
        with open(where, "w", encoding="utf-8") as handle:
            handle.write(plugins.panel_html(identifier, panel))
        made.append([name + "/" + panel, where])
sys.stdout.write(json.dumps(made))
`;
  return JSON.parse(execFileSync(PYTHON, ['-c', script], {
    encoding: 'utf8', maxBuffer: 1 << 24,
  }));
}

/**
 * A finger dragged across a slider: mostly sideways, wobbling a pixel or two
 * up and down the way a real one does. The wobble is the point - it is what
 * made the old rule hand the gesture away.
 */
async function dragSideways(page, box) {
  const session = await page.context().newCDPSession(page);
  const y = box.y + box.height / 2;
  const from = box.x + box.width * 0.15;
  await session.send('Input.dispatchTouchEvent', {
    type: 'touchStart', touchPoints: [{ x: from, y }],
  });
  for (let step = 1; step <= 16; step += 1) {
    await session.send('Input.dispatchTouchEvent', {
      type: 'touchMove',
      touchPoints: [{ x: from + step * (box.width * 0.045), y: y + (step % 3) - 1 }],
    });
  }
  await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await page.waitForTimeout(120);
}

async function main() {
  const into = fs.mkdtempSync(path.join(os.tmpdir(), 'pycmd-sliders-'));
  const panels = buildPanels(into);
  const browser = await chromium.launch({ executablePath: CHROME });

  console.log('== a finger can drag every slider in every panel ==');

  for (const [name, file] of panels) {
    const page = await browser.newPage({
      viewport: { width: 412, height: 892 }, hasTouch: true,
    });
    const told = [];
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.exposeFunction('__owns', (scrolls, grabs) => told.push({ scrolls, grabs }));
    await page.addInitScript(() => {
      // Kotlin's half of the bridge. Every export answers `ok` so the panel
      // draws something; what is being watched is `ownsGesture`.
      window.__pycmd_panel = {
        call(id) {
          setTimeout(() => window.__pycmd_resolve(
            String(id), true, JSON.stringify({ ok: true, result: { ok: true } }),
          ), 5);
        },
        ownsGesture(scrolls, grabs) { window.__owns(scrolls, grabs); },
        innerScroll() {},
        toast() {}, log() {}, close() {},
        manifest() { return JSON.stringify({ id: 'test.plugin', name: 'Test' }); },
      };
    });

    await page.goto('file://' + file, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(700);

    const ranges = await page.$$('input[type="range"]');
    if (!ranges.length) {
      console.log(`  ----  ${name}: no sliders`);
      await page.close();
      continue;
    }

    for (let index = 0; index < ranges.length; index += 1) {
      const slider = ranges[index];
      await slider.evaluate((el) => el.scrollIntoView({ block: 'center' }));
      await page.waitForTimeout(120);
      const box = await slider.boundingBox();
      if (!box || box.width < 20) {
        check(`${name} slider ${index + 1} is on screen`, false, box);
        continue;
      }
      told.length = 0;
      const before = await slider.evaluate((el) => Number(el.value));
      await dragSideways(page, box);
      const after = await slider.evaluate((el) => Number(el.value));

      sliders += 1;
      check(`${name} slider ${index + 1} follows the finger`,
            after !== before, { before, after });
      check(`${name} slider ${index + 1} tells the app it owns the drag`,
            told.some((row) => row.grabs === true), told);
    }

    check(`${name} drew without throwing`, errors.length === 0, errors);
    await page.close();
  }

  await browser.close();
  fs.rmSync(into, { recursive: true, force: true });

  console.log();
  console.log(`${sliders} slider(s) dragged`);
  if (!sliders) {
    console.log('  FAIL  no panel had a slider to drag, so nothing was checked');
    failures += 1;
  }
  if (failures) {
    console.log(`${failures} panel slider checks failed`);
    process.exit(1);
  }
  console.log('all panel slider checks passed');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
