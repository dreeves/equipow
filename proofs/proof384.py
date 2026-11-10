"""Astra's finite, exact certificate that m*(384) = 10 (2026-10-20).

Written by Astra. Only Python's standard library is used. No LP solver, lattice
package, numerical rounding, symmetry assumption, or search journal is needed.

Suppose signs a_p in {-1, 1}, for p = 0,...,383, have zero power sums through
degree 10. The binomial polynomials C(p,k), k = 0,...,10, span the same polynomial
space as 1,p,...,p^10. Thus f(x) = sum_p a_p*x^p and its derivatives of orders
1,...,10 vanish at 1, so the monic polynomial (x-1)^11 divides f in Z[x]. Shifting
positions from 0,...,383 to 1,...,384 preserves these vanishing moments.

Reduce f modulo x^5-1. Its coefficients d_r = sum_{p mod 5 = r} a_p must lie in
the integer span of the cyclic shifts of (450,-450,275,0,-275), the coefficients
of (x-1)^11 modulo x^5-1. Each generator satisfies the linear congruences in
residue_conditions(), so every possible d does too. Bounds, parity, and sum(d)
= 0 leave exactly four count vectors c_r = (d_r + size_r)/2. All four are checked;
no identification under reflection, sign reversal, or any other symmetry is used.

Each count vector has one 77-position class r with exactly one plus sign and
another class s with exactly one minus sign. Choose their exceptional positions
r+5*i and s+5*j, with 0 <= i,j <= 76. There are 4*77^2 = 23,716 choices. The
remaining 230 variables x_p = (a_p+1)/2 obey eleven binomial-moment equations
and five residue-count equations. Their moment right sides are C(384,k+1)/2,
by sum_{p=0}^{383} C(p,k) = C(384,k+1). Each half is checked to be integral.

A certificate (modulus, coefficients) is an integer combination of those sixteen
equations. Its value on every free column is verified to be divisible by the
modulus. Hence its value on the residual right side must be divisible too for
any integer solution. For every one of the 23,716 choices, at least one listed
certificate contradicts this condition. This proves the upper bound 10.

The existing length-384 witness is independently checked to have exact order 10,
proving the matching lower bound. Its free-variable contributions also supply
positive controls for all the modular certificates. The certificates were found
by exact elimination; their verification does not trust that discovery method.
"""

from itertools import product
from math import comb


N = 384
SIZES = (77, 77, 77, 77, 76)

# Each key names the two classes whose signs are fixed once i,j are chosen.
# Each coefficient vector lists eleven binomial rows, then five count rows.
CERTIFICATES = {
    (0, 3): (
        (25, (1, -1, 1, 0, -3, -20, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0)),
        (125, (-32, -93, -32, -11, 15, 35, -20, -5, 0, 5, 0,
               0, 0, 0, 0, 0)),
        (125, (-46, 46, -46, 0, 13, 5, -15, -15, -20, 0, 25,
               0, 0, 0, 0, 0)),
        (625, (-216, 215, -214, 30, -105, 315, -30, 50, 25, 0, -100,
               0, 1, 0, 0, 0)),
    ),
    (1, 2): (
        (25, (0, -1, 1, 0, -2, -20, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0)),
        (125, (0, 1, 42, -4, 10, -60, -5, -20, 0, 5, 0,
               0, 0, 0, 0, 0)),
        (125, (0, 56, 29, -5, -3, -5, -10, -10, -5, 0, 25,
               0, 0, 0, 0, 0)),
        (625, (-1, 233, -6, -55, -50, -305, 5, 0, -50, 0, -25,
               1, 0, 0, 0, 0)),
    ),
}


def require(condition):
    """A proof obligation that remains active under python -O."""
    if not condition:
        raise ValueError('Certificate verification failed')


def dot(a, b):
    require(len(a) == len(b))
    return sum(x * y for x, y in zip(a, b))


def residue_conditions(d):
    """Necessary linear congruences for the five signed residue sums."""
    return (sum(d) == 0
            and all(x % 25 == 0 for x in d)
            and (d[2] - 4 * d[0] - 2 * d[1]) % 125 == 0
            and (d[3] - 3 * d[0] - 3 * d[1]) % 125 == 0)


def count_vectors():
    """Enumerate a necessary superset of the possible plus-sign counts."""
    require(SIZES == tuple(len(range(r, N, 5)) for r in range(5)))
    generator = [0] * 5
    for k in range(12):
        generator[k % 5] += (-1) ** (11 - k) * comb(11, k)
    require(tuple(generator) == (450, -450, 275, 0, -275))
    require(all(residue_conditions(generator[i:] + generator[:i])
                for i in range(5)))

    vectors = []
    # Every one of the first four signed sums is an odd multiple of 25 in
    # [-77,77]. The fifth is forced by the zero constant moment.
    for head in product((-75, -25, 25, 75), repeat=4):
        d = head + (-sum(head),)
        if (residue_conditions(d)
                and all(abs(t) <= s and (t + s) % 2 == 0
                        for t, s in zip(d, SIZES))):
            vectors.append(tuple((t + s) // 2 for t, s in zip(d, SIZES)))
    require(tuple(vectors) == ((1, 26, 51, 76, 38), (26, 76, 1, 51, 38),
                               (51, 1, 76, 26, 38), (76, 51, 26, 1, 38)))
    return tuple(vectors)


def order10_control(rows):
    """Check the existing witness's exact power and binomial moments."""
    code = 'C1BE1E21CD63D295A7887A5965A1EE1A56B4394C7B87827C'
    left = tuple(int(bit) for bit in bin(int(code, 16))[2:].zfill(4 * len(code)))
    witness = left + left[::-1]
    require(len(witness) == N)
    moments = tuple(sum((2 * witness[p] - 1) * p ** k for p in range(N))
                    for k in range(11))
    require(moments[:10] == (0,) * 10 and moments[10] != 0)
    require(all(2 * dot(rows[k], witness) == comb(N, k + 1)
                for k in range(10)))
    return witness


def verify_all(certificates=CERTIFICATES):
    """Check both bounds and return the exact case counts for inspection."""
    vectors = count_vectors()
    require(set(certificates) == {tuple(sorted((v.index(1), v.index(76))))
                                  for v in vectors})
    rows = tuple(tuple(comb(p, k) for p in range(N)) for k in range(11))
    rows += tuple(tuple(int(p % 5 == r) for p in range(N)) for r in range(5))
    columns = tuple(zip(*rows))
    require(all(comb(N, k + 1) % 2 == 0 for k in range(11)))
    moment_rhs = tuple(comb(N, k + 1) // 2 for k in range(11))
    witness = order10_control(rows)

    checked = 0
    counts = []
    for vector in vectors:
        r, s = vector.index(1), vector.index(76)
        require(SIZES[r] == SIZES[s] == 77)
        free = tuple(p for p in range(N) if p % 5 not in (r, s))
        require(len(free) == 230)
        rhs = moment_rhs + vector
        # Begin with r all minus and s all plus. Choosing the exceptional
        # positions later subtracts column r+5*i and adds column s+5*j.
        base = tuple(t - sum(row[s::5]) for row, t in zip(rows, rhs))
        congruences = certificates[tuple(sorted((r, s)))]

        # Use the actual witness's free-variable moments and counts. Its
        # degree-10 moment is nonzero; no infeasible target is imposed on it.
        control = tuple(sum(row[p] * witness[p] for p in free) for row in rows)
        survivors = list(product(range(77), repeat=2))
        levels = []
        for modulus, coefficients in congruences:
            require(type(modulus) is int and modulus > 0)
            require(len(coefficients) == 16
                    and all(type(t) is int for t in coefficients))
            values = tuple(dot(coefficients, column) for column in columns)
            require(all(values[p] % modulus == 0 for p in free))
            require(dot(coefficients, control) % modulus == 0)
            constant = dot(coefficients, base)
            survivors = [(i, j) for i, j in survivors
                         if (constant - values[r + 5 * i]
                             + values[s + 5 * j]) % modulus == 0]
            levels.append(len(survivors))
        require(not survivors)
        checked += 77 ** 2
        counts.append(tuple(levels))
    return dict(vectors=len(vectors), cases=checked, survivors=0,
                order10_control=True, levels=tuple(counts))


if __name__ == '__main__':
    result = verify_all()
    # Report the proved value, number of count vectors and position cases,
    # and absence of any surviving order-11 case.
    print(f'm*(384) = 10; {result["vectors"]} count vectors, '
          f'{result["cases"]} position cases, {result["survivors"]} order-11 survivors.')
