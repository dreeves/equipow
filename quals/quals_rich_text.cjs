// Replicata: the actual expandable-box button with nested static HTML, plus its rich-text CSS.
// Expectata: content identity survives click/key/find reveal cycles; prose uses ordinary typography.
// Resultata: assertions identify a changed node, wrong state, wrong pairing, or missing style.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const script = fs.readFileSync(path.join(root, 'page/codes.js'), 'utf8');
const css = fs.readFileSync(path.join(root, 'page/style.css'), 'utf8');
const button = script.match(/  function button\(e, make, closed = true\) \{[\s\S]*?\n  \}/)[0];
const pairing = script.slice(script.indexOf("  const texts = [...document.querySelectorAll('[data-text]')]"), script.indexOf('  // ---------- the buttons ----------'));
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
const e = element('SPAN', {text: 'rich'});
e.closest = () => block;
const rich = element('DIV', {textBox: 'rich'});
rich.attributes.hidden = 'until-found';
const paragraph = element('P'), formula = element('SPAN');
formula.textContent = '\\(x^2+1\\)';
paragraph.children.push(formula);rich.children.push(paragraph);
const context = {assert: check, buttons: [e], boxes: new Map()};
vm.createContext(context);
vm.runInContext(button + '\nthis.make = button;', context);
context.make(e, () => rich, 'until-found')();
assert.equal(e.attributes.role, 'button');
assert.equal(e.tabIndex, 0);
assert.equal(e.attributes['aria-expanded'], 'false');
assert.equal(e.attributes['aria-controls'], rich.id);
assert.equal(rich.hidden, 'until-found');
assert.strictEqual(block.afterNodes[0], rich);
e.emit('click');
assert.equal(rich.hidden, false);assert.equal(e.attributes['aria-expanded'], 'true');
e.emit('click');
assert.equal(rich.hidden, 'until-found');assert.equal(e.attributes['aria-expanded'], 'false');
for (const key of ['Enter', ' ']) {
  let prevented = 0;
  const event = {key, preventDefault() { prevented++; }};
  e.emit('keydown', event);assert.equal(rich.hidden, false);
  e.emit('keydown', event);assert.equal(rich.hidden, 'until-found');
  assert.equal(prevented, 2);
}
e.emit('keydown', {key: 'ArrowDown', preventDefault() { assert.fail(); }});
assert.equal(rich.hidden, 'until-found');
rich.emit('beforematch');
assert.equal(e.attributes['aria-expanded'], 'true');
// The browser removes hidden after beforematch; this fixture qualifies the handler, not browser text finding.
rich.hidden = false;
e.emit('click');
assert.equal(rich.hidden, 'until-found');assert.equal(e.attributes['aria-expanded'], 'false');
assert.strictEqual(rich.children[0], paragraph);
assert.strictEqual(paragraph.children[0], formula);
assert.equal(formula.textContent, '\\(x^2+1\\)');
function pair(texts, held) {
  vm.runInNewContext(pairing, {assert: check, document: {querySelectorAll: s => s === '[data-text]' ? texts : held}});
}
pair([e], [rich]);
assert.throws(() => pair([e], []));
assert.throws(() => pair([], [rich]));
assert.throws(() => pair([e], [rich, rich]));
const plain = element('DIV', {textBox: 'rich'});plain.attributes.hidden = '';
assert.throws(() => pair([e], [plain]));
const richStyle = css.match(/\.verbatim:not\(pre\)\s*\{([^}]*)\}/)?.[1] || '';
assert.match(richStyle, /font:\s*inherit\s*;/);
assert.match(richStyle, /white-space:\s*normal\s*;/);
assert.match(css, /\[hidden="until-found"\]\s*\{\s*position:\s*absolute\s*;/);
