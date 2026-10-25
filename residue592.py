"""Exact residue inputs for the 560 control and the bounded 592 witness pilot.

A residue profile D at modulus M is the vector of signed sums in classes mod M.
An orbit joins class r to class n-1-r under reflection; its positions are the
half-sequence variables in those two classes. A fixed orbit has all its signs
assigned before lattice enumeration. Its plus count fixes their sum, not their
placement. The search must still construct integer-consistent placements.

The 560 profile is the archived go560f.py profile zero. The 592 profile was
derived from the stated mod-9 parent by the archived prof27hnf.model, imposing
reflection and exact residue-lattice membership. A bounded CP-SAT optimization
selected seven orbits covering at least 153 half positions, each with at most
10,000 placements, and maximized integer-scaled log-binomial mass. This ranks a
pilot; it supplies no probabilistic success estimate or completeness claim.
The exact inputs and derivation status are in scratch/search592/derivation.json.
Neither profile uses any coordinates from a known witness.
"""
from math import comb

import sympy as sp
import mstar


PARENT592 = (54, -24, -30, 54, -30, -24, 54, -27, -27)
D592 = (18, -8, -2, 18, -14, -8, 18, -8, -6,
        18, -8, -14, 18, -14, -8, 18, -6, -8,
        18, -8, -14, 18, -2, -8, 18, -13, -13)
FIX592 = ((0, 24), (3, 21), (4, 20), (6, 18),
          (9, 15), (11, 13), (25, 26))
EXTRA592 = ((5, (-25, -25, 0, 50, 0)),
            (7, (-7, 21, 21, -7, -14, 0, -14)))
FIX560 = ((23, 23), (7, 12), (2, 17), (8, 11),
          (5, 14), (6, 13), (20, 26))


def orbits(n, modulus, D):
    """Canonical reflected orbits, with exact half-position lists and counts."""
    pairs = [(r, (n - 1 - r) % modulus) for r in range(modulus)
             if r <= (n - 1 - r) % modulus]
    out = []
    for r, s in pairs:
        ps = [p for p in range(n // 2) if p % modulus in (r, s)]
        coefficient = 1 + int(r == s)
        numerator = len(ps) * coefficient + D[r]
        assert numerator % (2 * coefficient) == 0
        out.append(dict(residues=[r, s], positions=ps,
                        plus=numerator // (2 * coefficient)))
    return out


def validate(p):
    """Check exact admissibility and the supplied placement geometry."""
    n, m, modulus, D = (p[k] for k in ('n', 'order', 'modulus', 'D'))
    assert all(type(x) is int for x in (n, m, modulus))
    assert n > 0 and n % 2 == 0 and m > 0 and m % 2 == 0 and modulus == 27
    assert [M for M, _ in p['extra']] == [5, 7]
    for M, d in [[modulus, D]] + p['extra']:
        assert type(M) is int and len(d) == M
        assert all(type(x) is int for x in d)
        sizes = [len(range(r, n, M)) for r in range(M)]
        assert all(abs(x) <= size and (x - size) % 2 == 0
                   for x, size in zip(d, sizes))
        assert all(d[r] == d[(n - 1 - r) % M] for r in range(M))
        H = mstar.lattice(M, m, n < 2 ** m)
        z = H.gauss_jordan_solve(sp.Matrix(d))[0]
        assert all(x.is_Integer for x in z) and H * z == sp.Matrix(d)
        for o in orbits(n, M, d):
            assert 0 <= o['plus'] <= len(o['positions'])
    assert all(type(o['plus']) is int and
               all(type(x) is int for x in o['residues'] + o['positions'])
               for o in p['orbits'])
    assert p['orbits'] == orbits(n, modulus, D)
    fixed = [tuple(x) for x in p['fixed_orbits']]
    assert len(fixed) == len(set(fixed))
    assert set(fixed) <= {tuple(o['residues']) for o in p['orbits']}
    assert all(comb(len(o['positions']), o['plus']) <= 10000
               for o in p['orbits'] if tuple(o['residues']) in fixed)


def model(n, D, fixed, extra):
    """Build a fresh JSON-safe profile; full moment feasibility is separate."""
    p = dict(n=n, order=10, modulus=27, D=list(D),
             orbits=orbits(n, 27, D),
             fixed_orbits=[list(x) for x in fixed],
             extra=[[M, list(d)] for M, d in extra])
    validate(p)
    return p


def control():
    counts = {23: 10, 7: 0, 2: 20, 8: 20, 5: 19, 6: 2, 20: 18,
              4: 5, 9: 5, 1: 6, 3: 6, 0: 7, 21: 13, 22: 9}
    D = [None] * 27
    for r, plus in counts.items():
        s = (559 - r) % 27
        count = sum(p % 27 in (r, s) for p in range(280))
        D[r] = D[s] = (1 + int(r == s)) * (2 * plus - count)
    return model(560, D, FIX560, ((5, (0,) * 5), (7, (0,) * 7)))


def target():
    assert tuple(sum(D592[r] for r in range(q, 27, 9))
                 for q in range(9)) == PARENT592
    return model(592, D592, FIX592, EXTRA592)


def profile(n):
    return {560: control, 592: target}[n]()
