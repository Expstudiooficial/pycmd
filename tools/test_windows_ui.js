/*
 * Checks the Windows app shell without needing WebView2.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const APP = path.join(__dirname, '..', 'windows', 'ui', 'app.js');
let failures = 0;
let checks = 0;

function check(name, condition, detail) {
  checks += 1;
  if (condition) {
    console.log(`  PASS  ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL  ${name}${detail === undefined ? '' : ` (${detail})`}`);
  }
}

function element() {
  return {
    children: [],
    className: '',
    scrollTop: 0,
    get firstChild() { return this.children[0] || null; },
    appendChild(child) { this.children.push(child); return child; },
    removeChild(child) {
      this.children.splice(this.children.indexOf(child), 1);
      if (!this.children.length) this.scrollTop = 0;
      return child;
    },
    setAttribute() {},
    addEventListener() {},
  };
}

const rail = element();
const document = {
  createElement: element,
  createTextNode: (text) => ({ textContent: text }),
  getElementById: (id) => {
    if (id !== 'tabs') throw new Error(`unexpected element lookup: ${id}`);
    return rail;
  },
  addEventListener() {},
};
const window = { addEventListener() {} };
const context = vm.createContext({ document, window, console, setTimeout, clearTimeout, fetch() {} });
vm.runInContext(fs.readFileSync(APP, 'utf8'), context, { filename: APP });

console.log('== Windows navigation keeps the sidebar position ==');
vm.runInContext("PyCmd.state.tab = 'learn'; drawTabs();", context);
rail.scrollTop = 280;
vm.runInContext("PyCmd.state.tab = 'console'; drawTabs();", context);
check('redrawing tabs after a selection preserves the scroll position',
      rail.scrollTop === 280, rail.scrollTop);

rail.scrollTop = 410;
vm.runInContext('drawTabs();', context);
check('refreshing shell state preserves the scroll position',
      rail.scrollTop === 410, rail.scrollTop);

console.log(`\n${checks - failures}/${checks} Windows UI checks passed`);
if (failures) process.exitCode = 1;
