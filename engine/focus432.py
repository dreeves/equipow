"""Claude's exact preparation of the all-sign 432:12 proof search, which decides OEIS A323395 a(11) (dreeves,
2026-10-25: "sounds good on 432:12").

An exclusion proves m*(432) = 11; a witness is an order-12 sequence of length 432.  This module proves neither: it
reduces 432:12 to two cases under one exact derivative row, every step checked before the first search node.

Let a_p in {-1, 1}, p = 0, ..., 431, have order 12, so that (x-1)^12 divides f(x) = sum a_p x^p.

Roots.  As 432 < 2^12, residues.py's finished enumerations of L+(M, 12) give every possible vector of residue sums
mod 3, 4, 5 and 7: 1, 25, 2 and 24 of them, so 1,200 combinations of plus counts.  A stored integer certificate closes
1,198 of them, certbb.lower_bound positive on the whole box; the other two are B, below, and its complement A.

Forced factors.  Both have 54 plus signs in each class mod 4 of 108, so every signed residue sum mod 4 is 0: f(-1) = 0
and f(i) = 0.  The distinct monic irreducibles x-1, x+1 and x^2+1 thus give F = (x-1)^12 (x+1) (x^2+1) dividing f,
and f = F h with h in Z[x], F being monic.  (x^2+x+1 divides f too, the only mod-3 profile being 0, but would change
nothing below: it is prime to x+1 mod 2, and 1 at -1.)

Saturation lemma, a hand lemma.  Mod 2 every a_p is 1, so f = S = (x^432-1)/(x-1).  As 432 = 16*27, x^432-1 =
(x^27-1)^16 mod 2, and x+1 does not divide (x^27-1)/(x-1), which is 27 at 1, odd: so x+1 divides S exactly 15 times,
as it does F = (x+1)^15 mod 2.  F_2[x] having no zero divisors, h = S/F mod 2 is then prime to x+1, so h(1), and with
it h(-1), is odd.  As F(-1) = 0, f'(-1) = F'(-1) h(-1) = 8192 h(-1), F'(-1) being (-2)^12 * 2.  As f(-1) = 0 too,
f'(-1) = sum (p - 431/2) a_p (-1)^(p-1), at most sum |p - 431/2| = 46,656 in size.  So f'(-1) = 8192 k with k one of
+-1, +-3 and +-5.  _lemma computes the parts that can be computed: both multiplicities, by exact division, F'(-1), the
bound and the k.

Derivative.  Stored certificates exclude k = +-3 and +-5 in both cases.  Negating every sign keeps the order, swaps B
and A (each count becomes its class's size less it) and negates f'(-1).  So (B, -8192) and (A, -8192) are (A, 8192)
and (B, 8192) negated, and the search covers f'(-1) = 8192 in both cases: one more row, sum p (-1)^(p-1) x_p =
(8192 + 216)/2 = 4204 in the 0/1 variables x_p = (a_p + 1)/2, added as focus480.py adds its own.  _says checks
that row, and each derivative certificate's, against f'(-1) by Horner's rule, for every sign vector at once.

The certificates come from the 432:12 referee (scratch/ideas-20261025/verify/v432, rootlp432.py and deriv432.py) and
are untrusted here: prepare checks each one.  The other functions take any length, order and factor, for the controls
in quals_focus432.py.
"""
from functools import reduce
import gzip
import itertools
import json
from pathlib import Path

import certbb
import residues

N, ORDER = 432, 12
MODULI = (3, 4, 5, 7)
PROOF = Path(__file__).with_name('focus432_certificates.json.gz')
B = ((3, (72, 72, 72)), (4, (54, 54, 54, 54)), (5, (6, 6, 68, 68, 68)), (7, (38, 38, 38, 38, 38, 13, 13)))


def _multiply(a, b):
    """Integer polynomial multiplication, coefficients in increasing degree."""
    out = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i + j] += x * y
    return out


def _bits(polynomial):
    """An integer polynomial mod 2 as bits: bit i its coefficient of x^i."""
    return sum((c % 2) << i for i, c in enumerate(polynomial))


def _divide(a, b):
    """Division of polynomials over F_2, as bits: the quotient and remainder."""
    assert a >= 0 and b > 0
    quotient = 0
    while a.bit_length() >= b.bit_length():
        k = a.bit_length() - b.bit_length()
        quotient ^= 1 << k
        a ^= b << k
    return quotient, a


def _multiplicity(a):
    """How often x+1 divides the nonzero polynomial a over F_2 (as bits), by exact division."""
    assert a > 0
    count, (quotient, remainder) = 0, _divide(a, 0b11)
    while remainder == 0:
        count += 1
        quotient, remainder = _divide(quotient, 0b11)
    return count


def _derivative(n):
    """The coefficients of f'(-1) = sum p (-1)^(p-1) a_p, as focus480.py writes them."""
    return tuple(p * (-1) ** ((p - 1) % 2) for p in range(n))


def _lemma(n, factor):
    """The saturation lemma's computable parts (see the docstring) for signs of length n and a monic factor F of their
    f with F(-1) = 0, coefficients in increasing degree: x+1 divides F and S_n equally often mod 2, by exact division
    (asserted), so f/F is odd at -1.  Returns F'(-1), and the odd k with |F'(-1) k| <= sum |p - (n-1)/2|, one of
    which is f'(-1)/F'(-1)."""
    assert len(factor) <= n and factor[-1] == 1 and sum(c * (-1) ** i for i, c in enumerate(factor)) == 0
    assert _multiplicity(_bits(factor)) == _multiplicity((1 << n) - 1)
    slope = sum(d * c for d, c in zip(_derivative(n), factor))
    top = sum(abs(2 * p - n + 1) for p in range(n)) // (2 * abs(slope))      # the bound, doubled, over 2 |F'(-1)|
    return slope, tuple(k for k in range(-top, top + 1) if k % 2)


def _equations(base, v):
    """base's moment rows, then the derivative row f'(-1) = v in the 0/1 variables: sum p (-1)^(p-1) x_p =
    (v + n/2)/2."""
    derivative = _derivative(base.N)
    assert len(base.W) == base.order and sum(derivative) == base.N // 2
    assert type(v) is int and (v + base.N // 2) % 2 == 0
    return certbb.Moments(base.W, base.rhs, ((derivative,), ((v + base.N // 2) // 2,)))


def _slope(signs):
    """f'(-1) for f = sum a_p x^p, the a_p the signs, by Horner's rule on f's formal derivative sum p a_p x^(p-1): no
    formula shared with _derivative."""
    value = 0
    for p in reversed(range(1, len(signs))):
        value = p * signs[p] - value
    return value


def _says(equations, v):
    """The equations, once asserted to say f'(-1) = v in their one row past the moments: 2 (row.x - rhs) is f'(-1) - v,
    for the signs 2x - 1, by _slope, at x = 0 and at each unit vector.  Both sides are affine in x, so it holds at every
    x: a 0/1 vector meets the row exactly when its signs have f'(-1) = v."""
    n, row, beta = equations.N, equations.W[-1], equations.rhs[-1]
    assert len(equations.W) == equations.order + 1
    for x in [[0] * n] + [[int(p == q) for p in range(n)] for q in range(n)]:
        assert 2 * (sum(c * t for c, t in zip(row, x, strict=True)) - beta) == _slope([2 * t - 1 for t in x]) - v
    return equations


def _profiles(n, m, M):
    """Every possible plus-count vector mod M at length n and order m: residues.py's enumeration, finished (running
    out of its budget raises), no symmetry assumed."""
    signed = tuple(residues.residue_vectors(n, M, m, None, residues.Budget(10 ** 6), 'natural'))
    sizes = tuple(len(range(r, n, M)) for r in range(M))
    assert all(len(D) == M and all(abs(d) <= s and (d + s) % 2 == 0 for d, s in zip(D, sizes)) for D in signed)
    return tuple(tuple((d + s) // 2 for d, s in zip(D, sizes)) for D in signed)


def _choice(counts):
    """Plus counts, one vector for each of MODULI, as a choice."""
    assert len(counts) == len(MODULI)
    return tuple((M, tuple(c)) for M, c in zip(MODULI, counts, strict=True))


def _complement(n, choice):
    """The plus counts of the negated signs: each class's size less its count."""
    assert all(len(v) == M and all(0 <= c <= len(range(r, n, M)) for r, c in enumerate(v)) for M, v in choice)
    return tuple((M, tuple(len(range(r, n, M)) - c for r, c in enumerate(v))) for M, v in choice)


def _retained(equations, choices, records):
    """The choices no record closes.  Each record, (choice, certificate), must close its own choice, one of choices
    that no other record closes: certbb.lower_bound positive on the whole box under the choice's rows."""
    closed = set()
    for choice, certificate in records:
        assert choice in choices and choice not in closed
        assert type(certificate) is list and all(type(t) is int for t in certificate)
        rows = certbb.node_rows(equations, choice)
        assert certbb.lower_bound(rows, [0] * equations.N, [1] * equations.N, certificate) > 0
        closed.add(choice)
    return choices - closed


def _proof():
    """Untrusted stored coefficients; prepare verifies their mathematical use."""
    with gzip.open(PROOF, 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def prepare():
    """Return exact equations and the cases B and A for focus.State/search, without a solver."""
    from focus import moments
    base = moments(N, ORDER)
    lists = tuple(_profiles(N, ORDER, M) for M in MODULI)
    choices = set(map(_choice, itertools.product(*lists)))
    assert tuple(map(len, lists)) == (1, 25, 2, 24) and len(choices) == 1200
    proof = _proof()
    assert set(proof) == {'version', 'roots', 'derivatives'} and proof['version'] == 1
    roots = [(_choice(r[:-1]), r[-1]) for r in proof['roots']]
    cases = (B, _complement(N, B))
    assert _complement(N, cases[1]) == B and len(roots) == 1198
    assert _retained(base, choices, roots) == set(cases)
    assert all(2 * c == len(range(r, N, 4)) for case in cases for r, c in enumerate(dict(case)[4]))
    factor = reduce(_multiply, [(-1, 1)] * ORDER + [(1, 1), (1, 0, 1)], [1])
    assert len(factor) == 16 and (_multiplicity(_bits(factor)), _multiplicity((1 << N) - 1)) == (15, 15)
    slope, ks = _lemma(N, factor)
    assert (slope, ks, sum(abs(2 * p - N + 1) for p in range(N))) == (8192, (-5, -3, -1, 1, 3, 5), 2 * 46656)
    excluded = []
    for *counts, v, certificate in proof['derivatives']:
        choice = _choice(counts)
        assert _retained(_says(_equations(base, v), v), {choice}, [(choice, certificate)]) == set()
        excluded.append((choice, v))
    assert sorted(excluded) == sorted((case, slope * k) for case in cases for k in ks if abs(k) > 1)
    return _says(_equations(base, slope), slope), cases
