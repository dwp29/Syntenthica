/* Host-only mock of the UAPI-v4 WebUI bridge; no Android or device writes. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '../build-kit/ci/module-cyberbrutal/webroot/panel.js'), 'utf8');

function makeEnvironment(withBridge) {
  const calls = [];
  function element(id, cmd = null) {
    return {id, textContent: '', className: '', disabled: true, handler: null,
      attrs: cmd ? {'data-cmd': cmd} : {},
      addEventListener(event, fn) { if (event === 'click') this.handler = fn; },
      getAttribute(key) { return this.attrs[key]; }};
  }
  const elements = {};
  ['log', 'verdict', 'themeBtn', 'refresh', 't-gov', 't-cpu', 't-gpu', 't-temp', 't-swap', 't-zram']
    .forEach(id => { elements[id] = element(id); });
  const buttons = ['profile_gaming', 'profile_daily', 'profile_revert'].map(c => element(c, c));
  const document = {getElementById(id) { return elements[id]; },
    querySelectorAll() { return buttons; }, body: {classList: {toggle() {}}}};
  const window = {setTimeout, clearTimeout};
  if (withBridge) {
    window.ksu = {exec(cmd, options, callbackName) {
      calls.push({cmd, options, callbackName});
      if (cmd === 'uname -r') window[callbackName](0, '4.14.357-openela-Synthetica-2.0\n', '');
      else if (cmd.startsWith('sh ')) window[callbackName](1, 'RESULT: verified=2 skipped=1 failed=0', '');
      else window[callbackName](0, 'GOV=schedutil\nCPU=300000\nGPU=5\nTEMP=310\nSWAP=60\nZRAM=1024\n', '');
    }};
  }
  const context = vm.createContext({window, document, Date, Math, String, Number});
  vm.runInContext(script, context);
  return {calls, elements, buttons};
}

const connected = makeEnvironment(true);
assert.equal(connected.calls[0].cmd, 'uname -r');
assert.equal(connected.calls[0].options, null);
assert.match(connected.elements.verdict.textContent, /UNVERIFIED/);
assert.equal(connected.elements['t-gov'].textContent, 'schedutil');
assert.equal(connected.buttons[0].disabled, false);
connected.buttons[0].handler();
assert.match(connected.calls[2].cmd, /synthetica-control\.sh profile_gaming$/);
assert.match(connected.elements.log.textContent, /PARTIAL \/ FAILED/);
assert.doesNotMatch(connected.elements.log.textContent, /\] VERIFIED/);
const offline = makeEnvironment(false);
assert.equal(offline.buttons.every(b => b.disabled), true);
assert.equal(offline.elements.verdict.textContent, 'ROOT BRIDGE UNAVAILABLE');
console.log('WebUI bridge tests passed (mock only; no device).');
