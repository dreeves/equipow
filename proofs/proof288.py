"""Claude's finite, exact proof that m*(288) <= 10 (2026-10-25).

Written by Claude. Only Python's standard library is used. No LP solver,
lattice package, floating point, symmetry assumption, or search journal is
needed. Nor is BGPW's Table 2, which the page cited for this bound.

Statement: no signs a_p in {-1, 1}, p = 0,...,287, have sum_p a_p*p^k = 0 for
every k = 0,...,10 (0^0 = 1). So {0,...,287} has no partition into two sets
with equal power sums for exponents 0,...,10, and m*(288) <= 10. Shifting the
positions to 1,...,288 preserves vanishing moments, so the same holds there.

Suppose such signs exist, and let f(x) = sum_p a_p*x^p. For j <= 10 the
derivative f^(j)(1) = sum_p a_p*p*(p-1)*...*(p-j+1) is a combination of those
power sums, so it vanishes. So 1 is a root of f of multiplicity at least 11,
and since (x-1)^11 is monic, f = (x-1)^11*g with g in Z[x].

Residue sums. For a modulus M, the residue sums D_r = sum_{p mod M = r} a_p,
r = 0,...,M-1, are the coefficients of f mod x^M-1. So D lies in the residue
lattice L(M, 11): the coefficient vectors of (x-1)^11*g(x) mod x^M-1, g in Z[x].
Also |D_r| <= size(M, r), the number of positions p = r (mod M), and
D_r = size(M, r) (mod 2). A vector meeting these three conditions is
admissible, and admissible() lists them all.

The M cyclic shifts of generator(M, m), the coefficients of (x-1)^m mod x^M-1,
span L(M, m), so the gcd of those coefficients divides every D_r: 25 for M = 5
and 7 for M = 7 at m = 11. choices() keeps the values of each D_r allowed by
size, parity and that gcd, 108 vectors mod 5 and 326,592 mod 7 in all, and
in_lattice() decides membership in L(M, m) exactly. Exactly two of them are
admissible mod 5, D5 = +-(-50, 0, 50, -25, 25), and eight mod 7.

Membership. Let R = Z[x]/(x^M-1) and Phi = 1+x+...+x^(M-1). Then
x^M-1 = (x-1)*Phi, x*Phi = Phi in R, and Phi(1) = M; evaluation at 1 is
defined on R. If (x-1)*w = 0 in R, then (x-1)*w = (x-1)*Phi*q in Z[x] for some
q, so w = Phi*q = q(1)*Phi in R. Hence when y(1) = 0 and z is the quotient of
y by x-1 from synthetic division, the solutions of (x-1)*w = y are exactly
z + c*Phi, c in Z. For k >= 2, y is then in (x-1)^k*R iff y(1) = 0, M divides
z(1), and z - (z(1)/M)*Phi, the one solution with value 0 at 1, is in
(x-1)^(k-1)*R; and y is in (x-1)*R iff y(1) = 0. Applied m times from y = D,
this is in_lattice(): D is in L(M, m) iff D(1) = 0 and M divides each of the
m values at 1 that it meets.

Cells. Classes r mod 5 and s mod 7 meet in the cell of positions p with
p mod 5 = r and p mod 7 = s. A class of size S and residue sum d has (S+d)/2
plus signs and (S-d)/2 minus signs. A cell's plus signs number at most the
lesser of its two classes' plus counts, and its minus signs at most the lesser
of their minus counts. A cell with more positions than those two bounds allow
is overfull, and then no sequence has those residue sums. For every one of the
2*8 = 16 pairs (D5, D7), CELLS names an overfull cell, and verify_all() checks
it exactly. All 16 pairs are checked; no identification under reflection, sign
reversal, or any other symmetry is used.

Example: D5 = (-50, 0, 50, -25, 25) leaves class 0 mod 5 with 4 plus signs (and
54 minus), and D7 = (0, -35, -21, -7, 7, 21, 35) leaves class 6 mod 7 with 3
minus signs (and 38 plus). Their cell, the 8 positions p = 20 (mod 35), can
hold at most 4 + 3 = 7 signs.

Order 11 enters only through L(5, 11) and L(7, 11). No moment equation, residue
class mod 3 or LP certificate is needed.
"""

from functools import lru_cache
from itertools import accumulate, product
from math import comb, gcd, prod


N = 288
ORDER = 11

# CELLS[D5, D7] = (r, s): an overfull cell for the residue sums D5 mod 5 and D7
# mod 7. Any overfull cell would do; each listed one is the first in the order
# (0, 0), (0, 1), ..., (4, 6).
CELLS = {
    ((-50, 0, 50, -25, 25), (-42, 7, 7, 7, 7, 7, 7)): (2, 0),
    ((-50, 0, 50, -25, 25), (0, -35, -21, -7, 7, 21, 35)): (0, 6),
    ((-50, 0, 50, -25, 25), (0, -21, 7, 35, -35, -7, 21)): (0, 3),
    ((-50, 0, 50, -25, 25), (0, -7, 35, -21, 21, -35, 7)): (0, 2),
    ((-50, 0, 50, -25, 25), (0, 7, -35, 21, -21, 35, -7)): (0, 5),
    ((-50, 0, 50, -25, 25), (0, 21, -7, -35, 35, 7, -21)): (0, 4),
    ((-50, 0, 50, -25, 25), (0, 35, 21, 7, -7, -21, -35)): (0, 1),
    ((-50, 0, 50, -25, 25), (42, -7, -7, -7, -7, -7, -7)): (0, 0),
    ((50, 0, -50, 25, -25), (-42, 7, 7, 7, 7, 7, 7)): (0, 0),
    ((50, 0, -50, 25, -25), (0, -35, -21, -7, 7, 21, 35)): (0, 1),
    ((50, 0, -50, 25, -25), (0, -21, 7, 35, -35, -7, 21)): (0, 4),
    ((50, 0, -50, 25, -25), (0, -7, 35, -21, 21, -35, 7)): (0, 5),
    ((50, 0, -50, 25, -25), (0, 7, -35, 21, -21, 35, -7)): (0, 2),
    ((50, 0, -50, 25, -25), (0, 21, -7, -35, 35, 7, -21)): (0, 3),
    ((50, 0, -50, 25, -25), (0, 35, 21, 7, -7, -21, -35)): (0, 6),
    ((50, 0, -50, 25, -25), (42, -7, -7, -7, -7, -7, -7)): (2, 0),
}


def require(condition):
    """A proof obligation that remains active under python -O."""
    if not condition:
        # TODO: report that a step of the proof failed.
        raise ValueError('Claude: "Probatio deficit."')


def sizes(n, M):
    """size(M, r) for r = 0,...,M-1: the number of p < n with p = r (mod M)."""
    return tuple(len(range(r, n, M)) for r in range(M))


def generator(M, m):
    """The coefficients of (x-1)^m mod x^M-1, lowest first."""
    return tuple(sum((-1) ** (m - k) * comb(m, k) for k in range(r, m + 1, M))
                 for r in range(M))


def in_lattice(D, m):
    """Is D in L(len(D), m)? The module docstring's Membership paragraph says
    why this decides it exactly."""
    require(m >= 1)
    M = len(D)

    def values():
        E = D
        yield sum(E)
        for _ in range(m):
            c, rem = divmod(sum(E), M)
            yield rem
            # all() resumes here only after rem = 0. Then E - c*Phi has value 0
            # at 1, and its negated partial sums are its quotient by x-1.
            E = [-t for t in accumulate(e - c for e in E)]
    return all(t == 0 for t in values())


def choices(n, M, m):
    """For each class r mod M, the values of D_r allowed by size, parity and
    the gcd of generator(M, m)'s coefficients."""
    step = gcd(*generator(M, m))
    require(step >= 1)
    return tuple(tuple(d for d in range(-s, s + 1, 2) if d % step == 0)
                 for s in sizes(n, M))


@lru_cache(maxsize=None)
def admissible(n, M, m):
    """Every admissible vector of residue sums mod M at length n and order m,
    in lexicographic order."""
    return tuple(D for D in product(*choices(n, M, m)) if in_lattice(D, m))


def counts(n, D):
    """The plus counts and the minus counts of the classes mod len(D) of a
    sequence of length n with residue sums D."""
    S = sizes(n, len(D))
    require(all(abs(d) <= s and (s + d) % 2 == 0 for d, s in zip(D, S)))
    return (tuple((s + d) // 2 for d, s in zip(D, S)),
            tuple((s - d) // 2 for d, s in zip(D, S)))


def overfull(n, D5, D7, r, s):
    """Do the positions p < n with p mod 5 = r and p mod 7 = s outnumber the
    signs that residue sums D5 mod 5 and D7 mod 7 leave for them?"""
    require(len(D5) == 5 and len(D7) == 7)
    require(type(r) is int and type(s) is int and 0 <= r < 5 and 0 <= s < 7)
    (plus5, minus5), (plus7, minus7) = counts(n, D5), counts(n, D7)
    cell = sum(p % 7 == s for p in range(r, n, 5))
    return cell > min(plus5[r], plus7[s]) + min(minus5[r], minus7[s])


def verify_all(cells=CELLS):
    """Check every step of the proof and return the case counts for inspection."""
    vectors = tuple(admissible(N, M, ORDER) for M in (5, 7))
    require(tuple(map(len, vectors)) == (2, 8))
    cases = tuple(product(*vectors))
    require(set(cells) == set(cases))
    survivors = tuple(case for case in cases
                      if not overfull(N, *case, *cells[case]))
    require(not survivors)
    return dict(candidates=tuple(prod(map(len, choices(N, M, ORDER)))
                                 for M in (5, 7)),
                vectors=tuple(map(len, vectors)), cases=len(cases),
                survivors=len(survivors))


if __name__ == '__main__':
    result = verify_all()
    # TODO: report the proved bound, the numbers of admissible vectors mod 5
    # and mod 7, the number of their pairs, and that no pair survives.
    print(f'Claude: "m*(288) <= 10; {result["vectors"][0]} et '
          f'{result["vectors"][1]} vectores, {result["cases"]} casus, '
          f'{result["survivors"]} superstites."')
