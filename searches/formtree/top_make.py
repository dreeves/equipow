#!/usr/bin/env python3
"""The top of a form tree proof: every vector mod 3, 5, 7 by pintree's enumerator, one per orbit, closed by a certificate from the engine's LP or kept as a start node.  The floating point LP only suggests.
Usage, in searches/formtree/: top_make.py lib n:m chain out.json.gz.  A cell without a .cfg here needs its configuration made first (pex.write_config, which uses tools not kept in the repository)."""
import gzip, importlib.util, json, os, sys, tempfile, time
os.environ['PE_LIB'] = sys.argv[1]
import pex as pe
spec = importlib.util.spec_from_file_location('pintree', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'proofs', 'pintree.py')); pt = importlib.util.module_from_spec(spec); spec.loader.exec_module(pt)
n, m = map(int, sys.argv[2].split(':')); chain = [int(x) for x in sys.argv[3].split(',')]; out = sys.argv[4]
mods = [3,4,5,7,8,9,11,13,16,17,19,23,25,27,29,31,37]
pe.init(n, m, mods, []); pe.run_settings()
tmp = tempfile.mktemp(); tokens = []; dealt = set(); t0 = time.time(); stats = dict(tried=0, closed=0, kept=0)
def attempt(pins):
    """The engine's verdict on these pins alone: a certificate or None."""
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644); pe.lib.pe_certfd(fd)
    r = pe.run({str(k): list(v) for k, v in pins.items()}, 3, False, 1); pe.lib.pe_certfd(-1)
    rows = {}; cert = None
    for line in open(tmp):
        p = line.split()
        if p[0] == 'P':
            w = [int(x) for x in p[4:]]; rows[int(p[1])] = (int(p[2]), w.index(1))
        elif p[0] == 'C' and p[1] != 'unproved':
            x = [int(v) for v in p[1:]]; k = x[2 + m]; cert = dict(cert=x[:2 + m] + [0], rows=[[*rows[x[3 + m + 2 * i]], x[4 + m + 2 * i]] for i in range(k)])
    return cert if r['closed'] >= 1 and r['open'] == 0 else None
def node(pins, depth):
    M = chain[depth]; tokens.append(['S', M])
    for v in pt.vectors(n, m, M, pins):
        child = {**pins, M: v}
        if any(i in dealt for i in pt.images(child, n)): continue
        stats['tried'] += 1; c = attempt(child)
        if c is not None: tokens.append(['C', c]); stats['closed'] += 1
        elif depth + 1 < len(chain): node(child, depth + 1)
        else: tokens.append(['K']); stats['kept'] += 1
        dealt.add(pt.freeze(child))
    dealt.add(pt.freeze(pins))
node({}, 0)
if os.path.exists(tmp): os.remove(tmp)
with gzip.open(out, 'wt', encoding='utf-8') as f: json.dump(dict(n=n, m=m, tokens=tokens), f, separators=(',', ':'))
print(n, m, stats, f'{time.time()-t0:.1f}s', os.path.getsize(out), 'bytes', flush=True)
