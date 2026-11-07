"""Claude's exact proof that m*(1456) <= 11 (2026-11-07), so m*(1456) = 11 (the join p432 v p1024 has order 11).

Written by Claude. Python's standard library only: plain integers, no solver, no floating point, no symmetry assumption.

Suppose signs f_i in {-1, 1}, for i = 0, ..., 1455, have order 12: (x - 1)^12 divides f(x) = sum_i f_i x^i, that is,
sum_i f_i C(i, k) = 0 for k = 0, ..., 11.

1. Order 12 makes every f_i with i = 0 mod 3 the same.  Let z be a primitive cube root of unity, and D_r the sum of the
   f_i with i = r mod 3, over classes of sizes 486, 485, 485.  Since z^2 = -1 - z, f(z) = (D_0 - D_2) + (D_1 - D_2) z, and
   (1 - z)^12 = 729 in Z[z], so 729 divides D_0 - D_2 and D_1 - D_2.  Every integer triple with |D_r| <= size_r,
   D_r = size_r mod 2 and D_0 + D_1 + D_2 = f(1) = 0 is tried: only (486, -243, -243) and its negative remain, and
   |D_0| = 486 is the size of class 0.  Negating f keeps its order, so every f_i with i = 0 mod 3 is -1.

2. Let P(i) = sum_k PSI[k] C(i, k).  Order 12 gives sum_i f_i P(i) = 0.  P(i) is a multiple of 729 at every i < 1456 with
   i != 0 mod 3, so sum over i = 0 mod 3 of f_i P(i) = -(sum over class 0 of P(i)) is a multiple of 729 too.  But the
   sum of P(i) over i = 0 mod 3 is 243 mod 729.  So no sequence of length 1456 has order 12.

PSI was read off an exact Hermite basis of the columns (C(i, k))_k, i != 0 mod 3: a column of its inverse, scaled to
integers (scratch/wish1456-20261107/certificate.py), reduced mod 729.  This file checks it from scratch.
    python3 -B proofs/proof1456.py"""
from math import comb

N, M, Q = 1456, 12, 729
PSI = [659, 70, 659, 333, 336, 513, 216, 342, 522, 486, 81, 0]


def profiles(n, m):
    """The residue sums (D_0, D_1, D_2) mod 3 that order m allows at length n, for even m and 3 not dividing n:
    (1 - z)^m = 3^(m/2) times a unit of Z[z], so 3^(m/2) divides D_0 - D_2 and D_1 - D_2."""
    assert m % 2 == 0 and n % 3
    one, z = (1, 0), (0, 1)
    mul = lambda a, b: (a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0] - a[1] * b[1])   # z^2 = -1 - z
    p = one
    for _ in range(m): p = mul(p, (1, -1))
    q = 3 ** (m // 2)
    assert {p, mul(p, z), mul(p, mul(z, z)), (-p[0], -p[1])} & {(q, 0), (-q, 0)}, p       # a unit times 3^(m/2)
    s = [len(range(r, n, 3)) for r in range(3)]
    return sorted((d0, d1, -d0 - d1) for d0 in range(-s[0], s[0] + 1, 2) for d1 in range(-s[1], s[1] + 1, 2)
                  if abs(d0 + d1) <= s[2] and (-d0 - d1 - s[2]) % 2 == 0 and (2 * d0 + d1) % q == 0 and (d0 + 2 * d1) % q == 0)


def check(psi):
    """The two steps above, at length 1456 and order 12, with the certificate psi."""
    sizes = [len(range(r, N, 3)) for r in range(3)]
    assert sizes == [486, 485, 485] and profiles(N, M) == [(-486, 243, 243), (486, -243, -243)], profiles(N, M)
    P = lambda i: sum(c * comb(i, k) for k, c in enumerate(psi))
    assert len(psi) == M and all(P(i) % Q == 0 for i in range(N) if i % 3)
    rest = sum(P(i) for i in range(0, N, 3)) % Q
    assert rest == 243, rest
    return rest


if __name__ == '__main__':
    check(PSI)
    print('Checked: order 12 at 1456 makes every sign at i = 0 mod 3 the same; P is 0 mod 729 off that class and sums to'
          ' 243 mod 729 on it.  No sequence of length 1456 has order 12.')
