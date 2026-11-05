// Replicata: the inline canonical proof's wide math/code and their scoped styles.
// Expectata: wide blocks scroll inside the proof; original text-panel support remains.
// Resultata: assertions identify an uncontained block or changed legacy support.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(root, 'page/style.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
const copied = html.split('<!-- proof384: begin canonical main -->')[1]?.split('<!-- proof384: end canonical main -->')[0];
assert.ok(copied);
assert.match(copied, /class="math"/);
assert.match(copied, /<pre>/);
const declarations = selector => Object.fromEntries([...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
  .filter(([, names]) => names.trim().split(',').map(s => s.trim()).includes(selector))
  .flatMap(([, , body]) => body.split(';').filter(s => s.trim()).map(s => s.split(':').map(x => x.trim()))));
for (const selector of ['.proof-body .math', '.proof-body .proof-equation', '.proof-body pre']) {
  const d = declarations(selector);
  assert.equal(d['overflow-x'], 'auto', selector);
  assert.equal(d['max-width'], '100%', selector);
  assert.equal(d.height, undefined, selector);
  assert.equal(d['max-height'], undefined, selector);
}
assert.equal(declarations('.verbatim')['white-space'], 'pre-wrap');
assert.equal(declarations('.verbatim:not(pre)')['white-space'], 'normal');
assert.equal(declarations('.scroll')['overflow-x'], 'auto');
assert.equal(declarations('[hidden="until-found"]').position, 'absolute');
