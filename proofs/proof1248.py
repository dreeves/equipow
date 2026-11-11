#!/usr/bin/env python3
"""Codex: exact proof that m*(1248) <= 13, 2026-11-11.

Together with the page's product (1-x) p624(x^2), of exact order 13,
this gives m*(1248) = 13. No symmetry assumption, floating point or solver
is used in this checker. Run: python3 -B -I -S proofs/proof1248.py

Suppose F(x)=sum_{i=0}^{1247} f_i x^i, f_i in {-1,1}, has order 14.
Write D_r=sum_{i=r mod 5} f_i. BGPW Proposition 4.3, at
14=3*(5-1)+2, gives 125|D_r and sum_r r D_r = 0 mod 625.
Proposition 4.2 supplies sum D_r=0, the class-size bounds and parity.
The class sizes are (250,250,250,249,249). Enumerating the 108 bounded
possibilities leaves precisely these three profiles and their negatives:

    (250,   0,-250, 125,-125)
    (250,-250, 250,-125,-125)
    (  0, 250,   0,-125,-125).

For each positive orientation a certificate below defines the integer-valued
polynomial P(i)=sum_{k=0}^{13} psi[k] binom(i,k). A class with |D_r| equal
to its size has all signs fixed. On every other class, P(i) is constant
modulo the certificate's modulus. Consequently sum_i f_i P(i) is determined
modulo that modulus, using both the fixed signs AND the other class sums.
The three forced residues are respectively 500 mod 625, 2375 mod 78125,
and 125 mod 625. All are nonzero. But order 14 requires this sum to be zero
for every polynomial of degree at most 13. Global negation reverses the
nonzero residue, so the three negative profiles are also impossible.

The last certificate is the essential extra step: on free classes 0,2,3,4,
P has residues 0,1,3,6 mod 625. Those classes need not have P=0; their known
sums suffice. Including the class-count rows in the discovery lattice found
this certificate. The checker validates every position directly and does not
trust the lattice calculation.

Primary source for the residue conditions: Buhler, Golan, Pratt, Wagon,
Littlewood polynomials, spectral-null codes, and equipowerful partitions,
Math. Comp. 90 (2021), Propositions 4.2 and 4.3, arXiv:1912.03491.
An independent exact cyclotomic-ring profile enumeration is in the quals.
"""
from itertools import product
from math import comb

N, M = 1248, 14
PSI = [0, 0, 1, 0, 0, -10, -5, 225, 125, -75, -225, -125, 250, 125]
# Each record: profile, modulus, polynomial, (nonzero total, free-class constants).
CERTIFICATES = [
    ((250, 0, -250, 125, -125), 625,
     [1, -1, 0, 2, -5, -10, 100, 0, -120, 35, 0, 125, 250, 75],
     (500, {1: 0, 3: 0, 4: 0})),
    ((250, -250, 250, -125, -125), 78125,
     [1, 0, -4, 11, -21, -5, -80, -55, 3925, -24130, -5975, 10775, 1975, 13225],
     (2375, {3: 0, 4: 0})),
    ((0, 250, 0, -125, -125), 625, PSI, (125, {0: 0, 2: 1, 3: 3, 4: 6})),
]


def profiles():
    sizes = [len(range(r, N, 5)) for r in range(5)]
    assert sizes == [250, 250, 250, 249, 249]
    choices = [[d for d in range(-s, s + 1)
                if d % 125 == 0 and (d - s) % 2 == 0] for s in sizes]
    assert [len(c) for c in choices] == [3, 3, 3, 2, 2]
    return sorted(d for d in product(*choices)
                  if sum(d) == 0 and sum(r*d[r] for r in range(5)) % 625 == 0)


def check_profile(profile, modulus, psi, claim):
    residue, constants = claim
    assert len(psi) == M and 0 < residue < modulus
    sizes = [len(range(r, N, 5)) for r in range(5)]
    fixed = {r: profile[r]//sizes[r] for r in range(5)
             if abs(profile[r]) == sizes[r]}
    free = set(range(5))-fixed.keys()
    values = [sum(c*comb(i,k) for k,c in enumerate(psi)) for i in range(N)]
    assert set(constants) == free
    assert all((values[i]-constants[r]) % modulus == 0
               for r in free for i in range(r,N,5))
    total = sum(sign*sum(values[r::5]) for r,sign in fixed.items())
    total += sum(profile[r]*constants[r] for r in free)
    assert total % modulus == residue
    return residue


def check(psi=PSI):
    # psi is injectable so the quals can damage the final certificate.
    d, q, _, residue = CERTIFICATES[-1]
    certificates = CERTIFICATES[:-1]+[(d,q,psi,residue)]
    covered = sorted(tuple(sign*t for t in d)
                     for d,_,_,_ in certificates for sign in (-1,1))
    assert profiles() == covered
    return tuple(check_profile(*certificate) for certificate in certificates)


if __name__ == '__main__':
    check()
    # TODO: Report the verified upper bound, without assuming symmetry.
    print('Probatum: m*(1248) <= 13; nulla symmetria praesumitur.')
