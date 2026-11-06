/*
 * Proves that a theme reaches a plugin panel.
 *
 * The mechanism, in full: every panel's stylesheet declares its colours as
 * `:root` custom properties with the Classic Green values as fallbacks, and
 * the app appends a `<style id="pycmd-theme">` holding another `:root` block
 * the moment the document starts. Later rule, same specificity, so it wins -
 * and the whole panel changes colour without the page knowing anything about
 * themes.
 *
 * That is easy to break in a way nothing else notices. A colour written as a
 * literal rather than a variable keeps the old value; a selector that is more
 * specific than `:root` ignores the block; a panel that sets colours with
 * inline styles from script overrides it again. So this loads the real panel
 * HTML in a real browser, measures the computed colours, appends a palette,
 * and measures again.
 *
 * The values here are the ones the Kotlin side emits for the Halloween theme
 * (see WebTheme.variables and ThemesTest); this file's job is the plumbing,
 * not the palette.
 */
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const PYTHON = process.env.PYTHON || 'python3.13';

const CHROME = (() => {
  if (process.env.PYCMD_CHROME) return process.env.PYCMD_CHROME;
  const base = '/opt/pw-browsers';
  if (!fs.existsSync(base)) return '';
  for (const folder of fs.readdirSync(base).sort().reverse()) {
    if (!folder.startsWith('chromium')) continue;
    for (const inner of ['chrome-linux64', 'chrome-linux']) {
      const guess = path.join(base, folder, inner, 'chrome');
      if (fs.existsSync(guess)) return guess;
    }
  }
  return '';
})();

let chromium = null;
try {
  ({ chromium } = require('playwright-core'));
} catch (error) {
  console.log('  SKIP  panel themes - playwright-core is not installed');
  process.exit(0);
}
if (!CHROME || !fs.existsSync(CHROME)) {
  console.log('  SKIP  panel themes - no Chromium to lay the panels out in');
  process.exit(0);
}

let failures = 0;

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
 * What the app sends. Trimmed to the names this test reads, because the full
 * block is forty variables and the point here is the plumbing.
 */
const HALLOWEEN = ':root{'
  + '--bg:#0C0711;'
  + '--surface:#150E1D;'
  + '--surface-high:#1E1429;'
  + '--outline:#39235A;'
  + '--fg:#EFE3D4;'
  + '--muted:#A58FB8;'
  + '--accent:#FF7518;'
  + '--accent-dim:#A8450A;'
  + '--on-accent:#1A0A00;'
  + '--danger:#E5383B;'
  + '}';

/** The same thing the app's WebTheme.script does, written out. */
function applyPalette(css, motion) {
  const element = document.getElementById('pycmd-theme') || (() => {
    const made = document.createElement('style');
    made.id = 'pycmd-theme';
    document.head.appendChild(made);
    return made;
  })();
  element.textContent = css;
  document.documentElement.setAttribute('data-pycmd-motion', motion);
  document.documentElement.setAttribute('data-pycmd-dark', 'true');
  document.documentElement.setAttribute('data-pycmd-theme', 'halloween');
}

async function main() {
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'pycmd-theme-'));
  const panels = buildPanels(scratch);
  check('there are panels to check', panels.length > 0, panels.length);

  const browser = await chromium.launch({ executablePath: CHROME });
  const context = await browser.newContext({ viewport: { width: 393, height: 830 } });

  for (const [name, file] of panels) {
    const page = await context.newPage();
    await page.goto('file://' + file);
    await page.waitForLoadState('domcontentloaded');

    // Before: the stylesheet's own fallbacks, which are Classic Green.
    const before = await page.evaluate(() => {
      const root = getComputedStyle(document.documentElement);
      return {
        bg: root.getPropertyValue('--bg').trim(),
        accent: root.getPropertyValue('--accent').trim(),
        body: getComputedStyle(document.body).backgroundColor,
        button: (() => {
          const button = document.querySelector('button');
          return button ? getComputedStyle(button).backgroundColor : '';
        })(),
      };
    });
    check(`${name}: starts in the default palette`, before.accent === '#4DD0A0', before);
    check(
      `${name}: the body takes its background from the palette`,
      before.body === 'rgb(11, 15, 20)',
      before,
    );

    await page.evaluate(
      ([css, fn]) => {
        // eslint-disable-next-line no-new-func
        new Function('css', 'motion', `(${fn})(css, motion)`)(css, 'reduced');
      },
      [HALLOWEEN, applyPalette.toString()],
    );

    const after = await page.evaluate(() => {
      const root = getComputedStyle(document.documentElement);
      const body = getComputedStyle(document.body);
      const button = document.querySelector('button');
      const field = document.querySelector('input:not([type="range"]), textarea');
      const card = document.querySelector('.card');
      return {
        accent: root.getPropertyValue('--accent').trim(),
        body: body.backgroundColor,
        text: body.color,
        motion: document.documentElement.getAttribute('data-pycmd-motion'),
        button: button ? getComputedStyle(button).backgroundColor : '',
        buttonTransition: button ? getComputedStyle(button).transitionDuration : '',
        field: field ? getComputedStyle(field).backgroundColor : '',
        card: card ? getComputedStyle(card).backgroundColor : '',
        buttons: document.querySelectorAll('button').length,
      };
    });

    check(`${name}: the palette arrived`, after.accent === '#FF7518', after);
    check(`${name}: the body followed it`, after.body === 'rgb(12, 7, 17)', after);
    check(`${name}: the text followed it`, after.text === 'rgb(239, 227, 212)', after);
    if (after.buttons > 0) {
      // Not one exact colour: a panel may legitimately dress its own buttons
      // in a different one of the theme's surfaces - Creator's compact block
      // buttons sit on `--surface` rather than `--surface-high`. What matters
      // is that the colour came from the palette rather than from the blue
      // literal the old stylesheet had in it.
      const surfaces = [
        'rgb(12, 7, 17)', // --bg
        'rgb(21, 14, 29)', // --surface
        'rgb(30, 20, 41)', // --surface-high
        'rgb(255, 117, 24)', // --accent
      ];
      check(
        `${name}: buttons take a colour from the theme, not the old blue`,
        surfaces.includes(after.button),
        after,
      );
      check(
        `${name}: the buttons actually changed colour`,
        after.button !== before.button,
        { before: before.button, after: after.button },
      );
      check(
        `${name}: the animations switch is honoured`,
        after.buttonTransition === '0s',
        after,
      );
    }
    if (after.field) {
      check(`${name}: fields followed it`, after.field === 'rgb(12, 7, 17)', after);
    }
    if (after.card) {
      check(`${name}: cards followed it`, after.card === 'rgb(21, 14, 29)', after);
    }
    await page.close();
  }

  await context.close();
  await browser.close();

  if (failures) {
    console.log(`\n${failures} FAILURE(S)`);
    process.exit(1);
  }
  console.log('\nall panel theme checks passed');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
