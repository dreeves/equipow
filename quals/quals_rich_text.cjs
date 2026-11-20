// Replicata: the actual expandable-box button (page/codes.js's button) with a box of nested static HTML.
// Expectata: content identity survives click/key cycles; the button's role, tab stop, aria-expanded and aria-controls
// follow its box, which opens right after the button's block.
// Resultata: assertions identify a changed node or wrong state.
// Spec change, 2026-11-20 (Opus 5.5; dreeves: "can we get rid of the plain text proofs and get everything deduplicated
// and typeset properly?"): the 512 entry's plain-text proofs, the page's texts, left the page, and with them their
// boxes hidden until found, the button's `closed` argument and the function that paired texts with boxes; so this no
// longer asks for find-in-page reveals (beforematch, hidden "until-found"), for that pairing, or for the rules
// .verbatim:not(pre) and [hidden="until-found"] of page/style.css.  A box is made at its button's first click, as a
// code's partition always was.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const script = fs.readFileSync(path.join(root, 'page/codes.js'), 'utf8');
const button = script.match(/  function button\(e, make\) \{[\s\S]*?\n  \}/)[0];
const check = (ok, ...what) => assert.ok(ok, JSON.stringify(what));
function element(tagName, dataset = {}) {
  return {tagName, dataset, children: [], attributes: {}, listeners: {}, hidden: false,
    outerHTML: `<${tagName}>`,
    setAttribute(k, v) { this.attributes[k] = v; },
    getAttribute(k) { return this.attributes[k] ?? null; },
    addEventListener(k, fn) { this.listeners[k] = fn; },
    emit(k, ev = {}) { this.listeners[k](ev); },
  };
}
const block = {after(...nodes) { this.afterNodes = nodes; }};
const e = element('CODE', {});
e.closest = () => block;
const rich = element('DIV', {});
const paragraph = element('P'), formula = element('SPAN');
formula.textContent = '\\(x^2+1\\)';
paragraph.children.push(formula);rich.children.push(paragraph);
let made = 0;
const context = {assert: check, buttons: [e], boxes: new Map()};
vm.createContext(context);
vm.runInContext(button + '\nthis.make = button;', context);
context.make(e, () => { made++; return rich; });
assert.equal(e.attributes.role, 'button');
assert.equal(e.tabIndex, 0);
assert.equal(e.attributes['aria-expanded'], 'false');
assert.equal(made, 0);                                       // no box before the first click
e.emit('click');
assert.equal(made, 1);
assert.equal(e.attributes['aria-controls'], rich.id);
assert.equal(rich.id, 'expansion-1');
assert.strictEqual(block.afterNodes[0], rich);
assert.equal(rich.hidden, false);assert.equal(e.attributes['aria-expanded'], 'true');
e.emit('click');
assert.equal(rich.hidden, true);assert.equal(e.attributes['aria-expanded'], 'false');
for (const key of ['Enter', ' ']) {
  let prevented = 0;
  const event = {key, preventDefault() { prevented++; }};
  e.emit('keydown', event);assert.equal(rich.hidden, false);
  e.emit('keydown', event);assert.equal(rich.hidden, true);
  assert.equal(prevented, 2);
}
e.emit('keydown', {key: 'ArrowDown', preventDefault() { assert.fail(); }});
assert.equal(rich.hidden, true);
assert.equal(made, 1);                                       // made once, then kept
assert.strictEqual(rich.children[0], paragraph);
assert.strictEqual(paragraph.children[0], formula);
assert.equal(formula.textContent, '\\(x^2+1\\)');
