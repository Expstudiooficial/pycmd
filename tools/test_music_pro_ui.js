/*
 * Drives the Music Pro panel the way a finger does, without a phone.
 *
 * `tools/test_music_pro.py` checks what the plugin asks the app for. This
 * checks the half that is between the two: what the panel *draws* from the
 * state the app reports, and what pressing each control actually sends.
 *
 * Nothing here is a mock of the panel. The HTML is built by the plugin
 * runtime, through `panel_html`, so it carries the same injected bridge a
 * phone gets; what is stubbed is the thing underneath that bridge -
 * `__pycmd_panel`, which is Kotlin on a device. So the bridge itself is
 * exercised rather than replaced, which is where one real bug lived: a panel
 * loaded with `setContent` gets its scripts before an init script runs, and
 * the bridge then finds no `__pycmd_panel` at all.
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
  console.log('  SKIP  Music Pro panel - playwright-core is not installed');
  process.exit(0);
}
if (!fs.existsSync(CHROME)) {
  console.log('  SKIP  Music Pro panel - no Chromium at ' + CHROME);
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

/** The real panel, built by the plugin runtime with its bridge in it. */
function panelHtml() {
  const script = `
import os, sys, tempfile
sys.path.insert(0, os.path.join(${JSON.stringify(ROOT)}, "app", "src", "main", "python"))
import pycmd_plugins as plugins
scratch = tempfile.mkdtemp()
os.makedirs(os.path.join(scratch, "workspace"))
plugins.configure(os.path.join(scratch, "plugins"),
                  os.path.join(scratch, "workspace"), None)
plugins.install(os.path.join(${JSON.stringify(ROOT)},
                "app", "src", "main", "assets", "plugins", "music-pro"),
                "music-pro", "1")
plugins.load("pycmd.music-pro")
sys.stdout.write(plugins.panel_html("pycmd.music-pro", "ui.html"))
`;
  return execFileSync(PYTHON, ['-c', script], { encoding: 'utf8', maxBuffer: 1 << 24 });
}

// A mixer in the state a phone would report: one deck loaded and playing with
// four effects and three equaliser bands, one deck empty with neither.
const MIXER = {
  ok: true, open: true, crossfade: 0.5,
  a: {
    name: 'a', loaded: true, title: 'One', playing: true, position: 30000,
    duration: 200000, cue: 5000, loopStart: 0, loopEnd: 0, looping: false,
    tempo: 1.0, gain: 1.0,
    bands: [{ hz: 60, level: 0 }, { hz: 230, level: 0 }, { hz: 910, level: 0 }],
    effects: ['bass', 'width', 'reverb', 'louder'],
  },
  b: {
    name: 'b', loaded: false, title: '', playing: false, position: 0,
    duration: 0, cue: 0, loopStart: 0, loopEnd: 0, looping: false,
    tempo: 1.0, gain: 1.0, bands: [], effects: [],
  },
};

async function main() {
  const file = path.join(os.tmpdir(), 'pycmd-music-pro-panel.html');
  fs.writeFileSync(file, panelHtml());

  const browser = await chromium.launch({ executablePath: CHROME });
  const page = await browser.newPage({ viewport: { width: 412, height: 892 } });
  const errors = [];
  const calls = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });

  await page.exposeFunction('__record', (name, body) => { calls.push([name, body]); });
  await page.addInitScript(({ mixer }) => {
    window.__answers = {
      mixer: {
        ok: true, state: mixer, decks: ['a', 'b'],
        effects: [
          { id: 'bass', name: 'Bass' }, { id: 'width', name: 'Width' },
          { id: 'reverb', name: 'Reverb' }, { id: 'louder', name: 'Louder' },
        ],
      },
      tracks: {
        ok: true, count: 2,
        tracks: [
          { id: 't1', title: 'One', artist: 'Somebody', file: '/m/one.mp3', duration: 200000 },
          { id: 't2', title: 'Two', artist: 'Another', file: '/m/two.mp3', duration: 150000 },
        ],
      },
      apps: {
        ok: true,
        playing: {
          ok: true, allowed: true,
          sessions: [{
            'package': 'com.example.player', app: 'Example Player',
            title: 'A Song', artist: 'A Band', playing: true,
          }],
        },
        apps: { ok: true, apps: [{ 'package': 'com.example.player', app: 'Example Player' }] },
      },
      find: {
        ok: true, query: 'blue', count: 1,
        notes: ['Jamendo was skipped: it needs a client id.'],
        results: [{
          source: 'Jamendo', id: '1', title: 'Blue Thing', artist: 'Somebody',
          url: 'https://example.com/a.mp3', page: 'https://example.com/p',
          licence: 'CC-BY',
        }],
      },
    };
    // Kotlin's half of the bridge, which is what a phone supplies.
    window.__pycmd_panel = {
      call(id, name, body) {
        window.__record(name, body);
        const answer = window.__answers[name] || { ok: true };
        setTimeout(() => window.__pycmd_resolve(
          String(id), true, JSON.stringify({ ok: true, result: answer }),
        ), 5);
      },
      innerScroll() {},
      toast(text) { window.__record('toast', String(text)); },
      log() {},
      close() {},
      manifest() {
        return JSON.stringify({ id: 'pycmd.music-pro', name: 'Music Pro' });
      },
    };
  }, { mixer: MIXER });

  await page.goto('file://' + file, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(900);

  console.log('== it draws what the app reported ==');
  const text = await page.evaluate(() => document.body.innerText);
  check('both decks', text.includes('Deck A') && text.includes('Deck B'), text.slice(0, 80));
  check('the loaded track by name', text.includes('Deck A — One'));
  check('where it is, and where the cue is',
        text.includes('0:30 / 3:20') && text.includes('cue 0:05'));
  check('only the effects this phone has',
        text.includes('Bass') && text.includes('Reverb'));
  check('the equaliser bands by frequency', text.includes('60 Hz') && text.includes('910 Hz'));
  check('an empty deck says so', text.includes('Deck B — empty'));
  check('and says which effects it did not get',
        text.includes('no equaliser'));
  check('the library', text.includes('Somebody') && text.includes('Another'));
  check('and whatever else is playing',
        text.includes('Example Player') && text.includes('A Song'));

  console.log('\n== every control sends what it says it does ==');
  await page.evaluate(() => {
    const at = (selector) => document.querySelector(selector);
    at('[data-do="a:play"]').click();
    at('[data-load="b:t2"]').click();
    at('[data-loop="a:in"]').click();
    at('[data-flat="a"]').click();
    at('[data-app="com.example.player:next"]').click();
    const move = (selector, value) => {
      const slider = at(selector);
      slider.value = String(value);
      slider.dispatchEvent(new Event('input', { bubbles: true }));
    };
    move('#fader', 80);
    move('[data-tempo="a"]', 150);
    move('[data-fx="a:reverb"]', 40);
    move('[data-band="a:1"]', -60);
  });
  await page.waitForTimeout(300);

  const sent = (name, test) => calls.some(([called, body]) =>
    called === name && test(JSON.parse(body)));

  check('Play reaches the right deck',
        sent('deck_action', (b) => b.deck === 'a' && b.what === 'play'), calls);
  check('loading a track carries its file, not just its name',
        sent('load', (b) => b.deck === 'b' && b.file === '/m/two.mp3'), calls);
  check('Loop in marks where the deck is now',
        sent('deck_set', (b) => b.loopStart === 30000 && b.loopEnd === 0), calls);
  check('Flat reaches the equaliser', sent('flatten', (b) => b.deck === 'a'), calls);
  check('Next reaches the other app',
        sent('app_control', (b) => b.what === 'next'), calls);
  check('the crossfader sends a fraction, not a percentage',
        sent('fader', (b) => Math.abs(b.position - 0.8) < 0.001), calls);
  check('the tempo slider sends a rate',
        sent('deck_set', (b) => Math.abs((b.rate || 0) - 1.5) < 0.001), calls);
  check('an effect sends its name and a fraction',
        sent('effect', (b) => b.name === 'reverb' && Math.abs(b.level - 0.4) < 0.001), calls);
  check('and a band can be cut, not only boosted',
        sent('band', (b) => b.index === 1 && Math.abs(b.level + 0.6) < 0.001), calls);

  console.log('\n== the free catalogues ==');
  await page.evaluate(() => {
    document.getElementById('findQuery').value = 'blue';
    document.getElementById('findGo').click();
  });
  await page.waitForTimeout(400);
  const after = await page.evaluate(() => document.body.innerText);
  check('a result is drawn with its licence',
        after.includes('Blue Thing') && after.includes('CC-BY'), after.slice(-200));
  check('and a catalogue that was skipped says why',
        after.includes('needs a client id'), after.slice(-200));

  console.log('\n== nothing threw ==');
  check('no errors while drawing or pressing', errors.length === 0, errors);

  await browser.close();

  console.log();
  if (failures) {
    console.log(`${failures} Music Pro panel checks failed`);
    process.exit(1);
  }
  console.log('all Music Pro panel checks passed');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
