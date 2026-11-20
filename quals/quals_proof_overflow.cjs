// Replicata: the inline canonical proof's wide math/code and their scoped styles.
// Expectata: wide blocks scroll inside the proof.
// Resultata: assertions identify an uncontained block.
// Spec change, 2026-11-20 (Opus 5.5; dreeves: "can we get rid of the plain text proofs and get everything deduplicated
// and typeset properly?"): the 384 proof's displays are KaTeX in p.proof-equation, as in the page's other proofs, in
// place of its div.math (whose rule, .proof-body .math, went with them); and the text panels (.verbatim, hidden until
// found) went with the 512 entry's plain-text proofs, so this no longer asks for their three rules.  Until then it also
// asked that the proof have class="math" and that "original text-panel support" remain.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(root, 'page/style.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
const copied = html.split('<!-- proof384: begin canonical main -->')[1]?.split('<!-- proof384: end canonical main -->')[0];
assert.ok(copied);
assert.match(copied, /class="proof-equation"/);
assert.match(copied, /<pre>/);
const declarations = selector => Object.fromEntries([...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
  .filter(([, names]) => names.trim().split(',').map(s => s.trim()).includes(selector))
  .flatMap(([, , body]) => body.split(';').filter(s => s.trim()).map(s => s.split(':').map(x => x.trim()))));
for (const selector of ['.proof-body .proof-equation', '.proof-body pre']) {
  const d = declarations(selector);
  assert.equal(d['overflow-x'], 'auto', selector);
  assert.equal(d['max-width'], '100%', selector);
  assert.equal(d.height, undefined, selector);
  assert.equal(d['max-height'], undefined, selector);
}
assert.equal(declarations('.scroll')['overflow-x'], 'auto');
