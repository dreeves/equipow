"""Astra's exact preparation of the all-sign 480:14 proof search.

This reduces the search to195 representative cases; it does not yet exclude
order14. Every omitted profile has a checked integer separator, and complement
and reflection give bijections between equivalent cases without assuming that
any individual sign sequence is symmetric.

Forced factors. Let f(x)=sum(a_p*x^p), p=0,...,479, with a_p in{-1,1}, and
suppose (x-1)^14 divides f. Exact mod3 and mod5 enumeration gives zero signed
residue vectors, forcing Phi3 and Phi5. Also f(-1) is a multiple of2^14 of
absolute value<=480, so Phi2 divides f.

Mod2, f equals S480=(x^480-1)/(x-1), whose root1 multiplicity is31 because
480=32*15 with15 odd. Write f=(x-1)^14*g. Then g mod2 has root1 multiplicity17,
so Phi4 mod2=(x+1)^2 divides g mod2. Consequently g(i)=2z for z in Z[i], and
f(i)=(i-1)^14*2z=256iz. Its real and imaginary components have absolute value
at most240<256; both vanish. Thus Phi4 divides f and all mod4 signed sums vanish.

Now write f=(x-1)^14*(x+1)*Phi4*h. The remaining mod2 root multiplicity is14,
so h(-1) is even. Hence f'(-1) is divisible by2^16=65536. Since f(-1)=0,
centering its derivative coefficients gives |f'(-1)|<=sum|p-479/2|=57600.
Therefore f'(-1)=0 and Phi2^2 divides f. The relatively prime monic factors give
F=(x-1)^14*Phi2^2*Phi3*Phi4*Phi5 dividing f in Z[x].

Global parity. The monic quotient f/F is congruent mod2 to the uniquely computed
polynomial G0=S480/F. Therefore f=F*G0+2*F*h. Modulo x^8-1 the plus-count vector
belongs to C0+L_F, where C0=(F*G0+S480 mod(x^8-1))/2 and L_F is the integer span
of the cyclic shifts of F. An exact Hermite normal form calculation verifies
that this affine lattice consists precisely of vectors
  (a,b,c,d,60-a,60-b,60-c,60-d),
with every head entry congruent to6 mod8, a=c mod16, and b=d mod16. The box
0<=C_r<=60 leaves25 choices for(a,c) and25 for(b,d), hence625 vectors.

There are two admissible mod7 vectors, giving1250 profile pairs. The saved
integer separators exclude496;754 remain. Their complement/reflection orbits
have195 representatives. Each preparation regenerates the affine family,
checks every separator, and verifies complete orbit coverage.
"""
import gzip
import itertools
import json
from math import comb
from pathlib import Path

import certbb
import residues
import sympy as sp
from sympy.matrices.normalforms import hermite_normal_form

N, ORDER = 480, 14
PROOF = Path(__file__).with_name('focus480_certificates.json.gz')


def _multiply(a, b):
    """Integer polynomial multiplication, coefficients in increasing degree."""
    out = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i + j] += x * y
    return out


def _polynomial(order):
    """The forced factor F, also usable at order12 for the known-witness control."""
    out = [1]
    factors = [(-1, 1)] * order + [(1, 1), (1, 1), (1, 1, 1), (1, 0, 1), (1, 1, 1, 1, 1)]
    for factor in factors:
        out = _multiply(out, factor)
    return out


def _affine(order):
    """Regenerate the count offset and a basis of L_F modulo x^8-1 exactly."""
    factor = _polynomial(order)
    bits = sum((a % 2) << i for i, a in enumerate(factor))
    remainder, quotient = (1 << N) - 1, 0
    while remainder.bit_length() >= bits.bit_length():
        k = remainder.bit_length() - bits.bit_length()
        quotient ^= 1 << k
        remainder ^= bits << k
    assert remainder == 0
    g0 = [(quotient >> i) & 1 for i in range(quotient.bit_length())]
    fg0 = _multiply(factor, g0)
    assert len(fg0) == N and all(a % 2 == 1 for a in fg0)
    residue = tuple(sum(fg0[r::8]) for r in range(8))
    assert all(a % 2 == 0 for a in residue)
    offset = tuple((a + 60) // 2 for a in residue)
    generators = []
    for k in range(8):
        column = [0] * 8
        for i, a in enumerate(factor):
            column[(i + k) % 8] += a
        generators.append(column)
    basis = hermite_normal_form(sp.Matrix(generators).T)
    return offset, basis


def vectors():
    """All625 admissible mod8 count vectors in the verified affine lattice."""
    offset, basis = _affine(ORDER)
    # These four generators describe exactly the congruences in the docstring:
    # independent16-steps and joint8-steps in the two head-coordinate pairs.
    described = sp.Matrix(((-16, -8, 0, 0), (0, 0, -16, -8),
                           (0, -8, 0, 0), (0, 0, 0, -8),
                           (16, 8, 0, 0), (0, 0, 16, 8),
                           (0, 8, 0, 0), (0, 0, 0, 8)))
    assert hermite_normal_form(described) == basis
    assert all(offset[r] + offset[r + 4] == 60 for r in range(4))
    assert all(a % 8 == 6 for a in offset)
    assert (offset[0] - offset[2]) % 16 == (offset[1] - offset[3]) % 16 == 0
    groups = (tuple(range(6, 61, 16)), tuple(range(14, 61, 16)))
    pairs = tuple(itertools.chain.from_iterable(itertools.product(group, repeat=2) for group in groups))
    out = tuple((a, b, c, d, 60 - a, 60 - b, 60 - c, 60 - d)
                for (a, c), (b, d) in itertools.product(pairs, repeat=2))
    assert len(out) == len(set(out)) == 625
    return out


def _counts7():
    """Check the forcing arithmetic and enumerate every possible mod7 profile."""
    assert N == 32 * 15 and 32 - 1 - ORDER == 17
    assert N < 2 ** ORDER and N // 2 < 256
    assert 31 > ORDER + 3 and N * N // 4 < 2 ** (ORDER + 2)
    coefficients = tuple((-1) ** (ORDER - k) * comb(ORDER, k) for k in range(ORDER + 1))
    assert (sum(coefficients[::4]) - sum(coefficients[2::4]),
            sum(coefficients[1::4]) - sum(coefficients[3::4])) == (0, 128)
    for modulus in (3, 5):
        ds = tuple(residues.residue_vectors(N, modulus, ORDER, None, residues.Budget(100000), 'digits'))
        assert ds == ((0,) * modulus,)
    ds = tuple(residues.residue_vectors(N, 7, ORDER, None, residues.Budget(100000), 'digits'))
    assert len(ds) == 2
    out = tuple(tuple((d + len(range(r, N, 7))) // 2 for r, d in enumerate(vector)) for vector in ds)
    assert set(out) == {(10, 59, 59, 10, 34, 34, 34), (59, 10, 10, 59, 34, 34, 34)}
    return out


def _proof():
    """Untrusted stored coefficients; _retained verifies their mathematical use."""
    with gzip.open(PROOF, 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def _choice(profile):
    c7, v8 = profile
    return ((3, (80,) * 3), (5, (48,) * 5), (7, c7), (8, v8))


def _retained(equations, profiles, proof):
    """Remove only profiles with a positive exact bound from a stored separator."""
    assert set(proof) == {'version', 'certificates', 'profiles'} and proof['version'] == 1
    certificates, records = proof['certificates'], proof['profiles']
    assert len(certificates) == 400 and len(records) == 496
    assert all(len(c) == 38 and all(type(t) is int for t in c) for c in certificates)
    assert {j for _, _, j in records} == set(range(len(certificates)))
    excluded = set()
    for a, b, j in records:
        key = (tuple(a), tuple(b))
        assert type(j) is int and 0 <= j < len(certificates)
        assert key in profiles and key not in excluded
        rows = certbb.node_rows(equations, _choice(key))
        assert certbb.lower_bound(rows, [0] * N, [1] * N, certificates[j]) > 0
        excluded.add(key)
    assert len(excluded) == 496 and len(profiles) == 1250
    kept = profiles - excluded
    assert len(kept) == 754
    return kept


def _orbit(profile):
    """Bijections on whole solution sets: sign complement and position reversal."""
    def complement(z):
        return (tuple(len(range(r, N, 7)) - a for r, a in enumerate(z[0])), tuple(60 - a for a in z[1]))
    def reflection(z):
        return (tuple(z[0][(N - 1 - r) % 7] for r in range(7)),
                tuple(z[1][(N - 1 - r) % 8] for r in range(8)))
    assert complement(complement(profile)) == reflection(reflection(profile)) == profile
    assert complement(reflection(profile)) == reflection(complement(profile))
    return frozenset((profile, complement(profile), reflection(profile), complement(reflection(profile))))


def prepare():
    """Return exact equations and195 cases for focus.State/search, without a solver."""
    from focus import moments
    base = moments(N, ORDER)
    derivative = tuple(p * (-1) ** ((p - 1) % 2) for p in range(N))
    assert sum(derivative) == N // 2
    equations = certbb.Moments(base.W, base.rhs, ((derivative,), (N // 4,)))
    profiles = set(itertools.product(_counts7(), vectors()))
    kept = _retained(equations, profiles, _proof())
    representatives = tuple(sorted({min(_orbit(profile)) for profile in kept}))
    assert len(representatives) == 195
    assert {profile for representative in representatives for profile in _orbit(representative)} == kept
    assert sum(len(_orbit(representative)) for representative in representatives) == len(kept)
    return equations, tuple(_choice(profile) for profile in representatives)
