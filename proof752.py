"""Claude's exact proof that m*(752) <= 10 (2026-10-25).

Written by Claude. Python's standard library derives every count vector, congruence and target,
and rechecks every match; numpy only enumerates and matches the meet in the middle. No LP solver,
lattice package, floating point, symmetry assumption, or search journal is used.

Suppose signs a_p in {-1, 1}, for p = 0,...,751, have zero power sums through degree 10. The
binomial polynomials C(p,k), k = 0,...,10, span the same polynomial space as 1,p,...,p^10. Thus
f(x) = sum_p a_p*x^p and its derivatives of orders 1,...,10 vanish at 1, so the monic polynomial
(x-1)^11 divides f in Z[x].

Reduce f modulo x^3-1. Its coefficients d_r = sum_{p mod 3 = r} a_p must lie in the integer span
of the cyclic shifts of (-243,0,243), the coefficients of (x-1)^11 modulo x^3-1. The shifts sum to
0, so d_2 = -d_0-d_1. The span is enumerated within |d_r| <= size_r, for class sizes (251,251,250),
and d_r = size_r (mod 2) is required. Exactly two count vectors c_r = (d_r + size_r)/2 remain:
(4,247,125) and (247,4,125). Both are searched; no identification under sign reversal or any other
symmetry is used.

In each, classes 0 and 1 have exactly four exceptional positions: plus signs among minus signs, or
minus signs among plus signs. Class 2 is free. With x_p = (a_p+1)/2, class 2 holds c_2 plus signs,
and sum_p x_p*C(p,k) = C(752,k+1)/2 for k = 1,...,10, by sum_{p=0}^{751} C(p,k) = C(752,k+1); each
half is checked integral. A certificate (modulus, coefficients) is an integer combination of these
eleven equations. Its value on every class-2 column is verified to be divisible by the modulus.
Hence, for any integer solution, its value on the residual right side, the right sides minus the
columns of classes 0 and 1 weighted by their x_p, must be divisible too. The eleven certificates
are the columns of B^-1, scaled to integers, for a triangular basis B of the integer span of the
class-2 columns; together they hold exactly on that span. Their moduli are 1, 3, 3^2, 3^4, 3^5,
3^6, 3^8, 3^9, 3^10, 3^13 and 3^14.

A placement chooses the four exceptional positions in each of classes 0 and 1, and so fixes the
residual. Its keys are the certificate values of its exceptional columns, negated for exceptional
minus signs. It survives when its keys sum, modulo each modulus, to the profile's target: the
certificate's value on the right sides minus its values on all columns of a class of mostly plus
signs.

A meet in the middle tries all C(251,4)^2 placements of each profile. One side holds the 4-subsets
of class 0, carrying the target, and the other those of class 1. Each subset {a<b<c<d} is generated
once, as its pair (a,b) and its pair (c,d) with b < c. Certificates 8, 9 and 10 are matched exactly,
packed into one int64 below 2^62, bucket by bucket by certificate 10 modulo 3^7. Every pair's key and
every 4096th subset's key are recomputed in Python integers. Every bucket's size is checked against
a subset-sum recursion, and every generated subset is checked to be increasing and in its bucket.
Every match is rechecked on all eleven certificates in Python integers. No placement survives in
either profile. This proves the upper bound 10.
"""

from fractions import Fraction
from itertools import combinations, product
from math import comb, lcm, prod

import numpy as np


N = 752
ORDER = 11
MODULUS = 3
# The meet in the middle matches certificates 8, 9 and 10 exactly, packed into one int64, and
# takes each side's 4-subsets bucket by bucket, by certificate 10 modulo 3^7.
PACKED = (8, 9, 10)
BUCKETS = 3 ** 7
# Every SAMPLE-th key of each bucket is recomputed in Python integers.
SAMPLE = 4096


def require(condition):
    """A proof obligation that remains active under python -O."""
    if not condition:
        # TODO: report that one of the proof's checks failed.
        raise ValueError('Claude: "A check of the proof failed."')


def dot(a, b):
    require(len(a) == len(b))
    return sum(x * y for x, y in zip(a, b))


def euclid(row, other, j):
    """Unimodular combinations of two rows, the first holding their gcd at position j and the
    second 0 there."""
    while other[j]:
        q = row[j] // other[j]
        row, other = other, [x - q * y for x, y in zip(row, other)]
    return row, other


def triangular(vectors):
    """A basis of the vectors' integer span whose row j is 0 before position j and not 0 at it."""
    width = len(vectors[0])
    basis = [[0] * width for _ in range(width)]
    for vector in vectors:
        rest = list(vector)
        require(len(rest) == width)
        for j in range(width):
            basis[j], rest = euclid(basis[j], rest, j)
        require(not any(rest))
    require(all(row[j] for j, row in enumerate(basis)))
    return basis


def verify_certificates(certificates, vectors):
    """Require each certificate (modulus, coefficients) to divide its value on every vector."""
    for modulus, coefficients in certificates:
        require(type(modulus) is int and modulus > 0)
        require(all(type(c) is int for c in coefficients))
        require(all(dot(coefficients, vector) % modulus == 0 for vector in vectors))


def certificates(vectors):
    """Congruences that hold on an integer vector t exactly when t is in the vectors' integer span.
    For a triangular basis B of the span, t is in it exactly when t*B^-1 is integral. Column i of
    B^-1, scaled by its least common denominator, is certificate i."""
    basis = triangular(vectors)
    width = len(basis)
    found = []
    for i in range(width):
        column = [Fraction(0)] * width
        for k in reversed(range(width)):    # B * column = e_i, solved from the bottom
            column[k] = Fraction(int(k == i) - dot(basis[k][k + 1:], column[k + 1:]),
                                 basis[k][k])
        modulus = lcm(*(x.denominator for x in column))
        found.append((modulus, tuple(int(x * modulus) % modulus for x in column)))
    verify_certificates(found, vectors)
    return tuple(found)


def count_vectors(n=N, m=ORDER, M=MODULUS):
    """Every possible plus-sign count per residue class mod M of a length-n sequence of order >= m.
    Its residue sums lie in the integer span of the cyclic shifts of (x-1)^m mod x^M-1. The shifts
    sum to 0, so the first M-1 residue sums determine the last. The span of the shifts' first M-1
    coordinates is enumerated within the size bounds along a triangular basis, one coordinate at a
    time: coordinate j of a point depends only on its first j+1 basis coefficients."""
    sizes = tuple(len(range(r, n, M)) for r in range(M))
    generator = [0] * M
    for k in range(m + 1):
        generator[k % M] += (-1) ** (m - k) * comb(m, k)
    require(sum(generator) == 0)
    points = [[0] * (M - 1)]
    for j, row in enumerate(triangular([(generator[i:] + generator[:i])[:-1] for i in range(M)])):
        pivot = [x * (row[j] // abs(row[j])) for x in row]
        points = [[x + y * z for x, z in zip(point, pivot)] for point in points
                  for y in range(-((sizes[j] + point[j]) // pivot[j]),
                                 (sizes[j] - point[j]) // pivot[j] + 1)]
    sums = [point + [-sum(point)] for point in points]
    return tuple(sorted(
        tuple((d + s) // 2 for d, s in zip(ds, sizes)) for ds in sums
        if abs(ds[-1]) <= sizes[-1] and all((d + s) % 2 == 0 for d, s in zip(ds, sizes))))


class Case:
    """The relaxed equations of one count vector. The exceptional classes have their placements
    enumerated; the other classes are free. Each equation kept is a binomial moment k = 1..m-1 or a
    free class's plus count; the rest hold by the count vector."""

    def __init__(self, n, m, M, counts, exceptional):
        sizes = tuple(len(range(r, n, M)) for r in range(M))
        require(len(counts) == M and 2 * sum(counts) == n
                and all(0 <= c <= s for c, s in zip(counts, sizes)))
        require(list(exceptional) == sorted(set(exceptional))
                and set(exceptional) < set(range(M)))
        require(all(comb(n, k + 1) % 2 == 0 for k in range(m)))
        free = tuple(sorted(set(range(M)) - set(exceptional)))

        def column(p):
            return (tuple(int(p % M == r) for r in free)
                    + tuple(comb(p, k) for k in range(1, m)))

        self.free_columns = tuple(column(p) for r in free for p in range(r, n, M))
        self.certificates = certificates(self.free_columns)
        self.moduli = tuple(modulus for modulus, _ in self.certificates)
        self.classes = tuple(tuple(range(r, n, M)) for r in exceptional)
        # x_p on most of each exceptional class: 1 when most of its signs are plus.
        majority = tuple(int(2 * counts[r] > sizes[r]) for r in exceptional)
        self.minority = tuple(min(counts[r], sizes[r] - counts[r]) for r in exceptional)
        # The exceptional sign of each exceptional class.
        self.signs = tuple(1 - 2 * x for x in majority)
        self.keys = {p: tuple(dot(w, column(p)) % mu for mu, w in self.certificates)
                     for cls in self.classes for p in cls}
        rhs = (tuple(counts[r] for r in free)
               + tuple(comb(n, k + 1) // 2 for k in range(1, m)))
        self.target = tuple(
            (dot(w, rhs) - sum(x * dot(w, column(p))
                               for x, cls in zip(majority, self.classes) for p in cls)) % mu
            for mu, w in self.certificates)

    def contribution(self, placement):
        """The sum of a placement's keys, one tuple of exceptional positions per class."""
        require(len(placement) == len(self.classes))
        require(all(len(set(chosen)) == len(chosen) == k and set(chosen) <= set(cls)
                    for chosen, cls, k in zip(placement, self.classes, self.minority)))
        return tuple(sum(sign * self.keys[p][i]
                         for sign, chosen in zip(self.signs, placement) for p in chosen) % mu
                     for i, mu in enumerate(self.moduli))

    def holds(self, placement, target):
        """Whether a placement meets every certificate."""
        return self.contribution(placement) == tuple(t % mu for t, mu in zip(target, self.moduli))


def brute(case, target):
    """Every surviving placement, by trying each."""
    tried = tuple(product(*(combinations(cls, k)
                            for cls, k in zip(case.classes, case.minority))))
    return dict(placements=len(tried),
                survivors=[placement for placement in tried if case.holds(placement, target)])


def bucket_counts(values, constant, buckets):
    """The number of 4-subsets in each bucket, (constant + their values' sum) mod buckets, by the
    subset-sum recursion over the values."""
    ways = [[1] + [0] * (buckets - 1)] + [[0] * buckets for _ in range(4)]
    for value in values:
        r = value % buckets
        for k in (4, 3, 2, 1):
            shifted = ways[k - 1][buckets - r:] + ways[k - 1][:buckets - r]
            ways[k] = [x + y for x, y in zip(ways[k], shifted)]
    c = constant % buckets
    return ways[4][buckets - c:] + ways[4][:buckets - c]


def pack(values, moduli):
    """The mixed-radix integer of values reduced by the moduli, the first value least significant."""
    return sum(v * prod(moduli[:i]) for i, v in enumerate(values))


class Side:
    """The 4-subsets {a<b<c<d} of keyed elements 0..m-1, bucket by bucket. A subset's key is the
    constant plus its elements' keys, reduced by the moduli and packed; its bucket is the last
    component modulo the number of buckets. The pair (a,b), carrying the constant, meets the pairs
    (c,d) of the complementary bucket with c > b. Sorted by bucket and then by c descending, those
    pairs are a prefix of their bucket's run, of a length counted in advance. So each subset is
    generated once, from a distinct (pair, run position)."""

    def __init__(self, keys, constant, moduli, buckets):
        m = len(keys)
        require(m >= 4 and len(constant) == len(moduli)
                and all(len(key) == len(moduli) for key in keys))
        require(all(type(x) is int and 0 <= x < mu
                    for key in (*keys, constant) for x, mu in zip(key, moduli)))
        require(type(buckets) is int and buckets > 0 and moduli[-1] % buckets == 0)
        # Every key fits in an int64 exactly, even as 2*key + 1 in meet().
        require(prod(moduli) <= 2 ** 62)
        self.keys, self.constant = tuple(keys), tuple(constant)
        self.moduli, self.buckets = tuple(moduli), buckets
        self.prefix = prod(moduli[:-1])
        self.sizes = bucket_counts([key[-1] for key in keys], constant[-1], buckets)
        mu = np.array(moduli, dtype=np.int64)
        elements = np.array(keys, dtype=np.int64)
        a, b = np.triu_indices(m, 1)
        pair = (elements[a] + elements[b]) % mu
        low = (pair + np.array(constant, dtype=np.int64)) % mu
        # Every pair's key is recomputed in Python integers.
        require(pair.tolist() == [[(x + y) % mu for x, y, mu in zip(keys[i], keys[j], moduli)]
                                  for i, j in zip(a.tolist(), b.tolist())])
        require(low.tolist() == [[(x + c) % mu for x, c, mu in zip(row, constant, moduli)]
                                 for row in pair.tolist()])
        high_bucket = pair[:, -1] % buckets
        order = np.lexsort((-a, high_bucket))
        self.a, self.b, self.c, self.d = a, b, a[order], b[order]
        self.low = [np.ascontiguousarray(low[:, i]) for i in range(len(moduli))]
        self.high = [np.ascontiguousarray(pair[order, i]) for i in range(len(moduli))]
        self.low_bucket = low[:, -1] % buckets
        self.start = np.searchsorted(high_bucket[order], np.arange(buckets))
        tally = np.zeros((buckets, m + 1), dtype=np.int64)
        np.add.at(tally, (high_bucket, a), 1)
        # later[v, t]: the number of pairs (c,d) of bucket v with c > t.
        self.later = np.ascontiguousarray(np.cumsum(tally[:, ::-1], axis=1)[:, ::-1][:, 1:])
        self.pairs = np.arange(len(a))

    def key(self, subset):
        """A subset's packed key, in Python integers."""
        return pack(tuple((c + sum(self.keys[e][i] for e in subset)) % mu
                          for i, (c, mu) in enumerate(zip(self.constant, self.moduli))),
                    self.moduli)

    def subset(self, low, high):
        return (int(self.a[low]), int(self.b[low]), int(self.c[high]), int(self.d[high]))

    def bucket(self, q):
        """The packed keys of bucket q's subsets, with their pairs' indices, checked."""
        v = (q - self.low_bucket) % self.buckets
        runs = self.later[v, self.b]
        low = np.repeat(self.pairs, runs)
        high = (np.arange(int(runs.sum()))
                + np.repeat(self.start[v] - (np.cumsum(runs) - runs), runs))
        key = np.zeros(len(low), dtype=np.int64)
        for i in reversed(range(len(self.moduli))):
            s = self.low[i][low] + self.high[i][high]
            s -= self.moduli[i] * (s >= self.moduli[i])
            key = key * self.moduli[i] + s
        require(len(key) == self.sizes[q])
        require(bool(np.all(self.c[high] > self.b[low])))
        require(bool(np.all(key // self.prefix % self.buckets == q)))
        require(all(int(key[i]) == self.key(self.subset(low[i], high[i]))
                    for i in range(0, len(key), SAMPLE)))
        return key, low, high


def meet(left, constant, right, moduli, buckets):
    """Every pair (S, T) of 4-subsets of the left and right indices with constant + sum_S left =
    sum_T right, componentwise modulo the moduli."""
    sides = (Side(left, constant, moduli, buckets),
             Side(right, (0,) * len(moduli), moduli, buckets))
    pairs, totals = [], (0, 0)
    for q in range(buckets):
        (ka, la, ha), (kb, lb, hb) = (side.bucket(q) for side in sides)
        totals = (totals[0] + len(ka), totals[1] + len(kb))
        # Sorted, 2*key + side puts each key found on both sides at an even value just below
        # an odd one.
        both = np.sort(np.concatenate((2 * ka, 2 * kb + 1)))
        shared = both[:-1][(both[1:] - both[:-1] == 1) & (both[:-1] % 2 == 0)] // 2
        for k in shared.tolist():
            for i, j in product(np.flatnonzero(ka == k).tolist(), np.flatnonzero(kb == k).tolist()):
                pairs.append((sides[0].subset(la[i], ha[i]), sides[1].subset(lb[j], hb[j])))
    require(totals == (comb(len(left), 4), comb(len(right), 4)))
    require(all(sides[0].key(s) == sides[1].key(t) for s, t in pairs))
    return dict(subsets=totals, pairs=pairs)


def search(case, target, packed=PACKED, buckets=BUCKETS):
    """Every surviving placement of four exceptional positions in each of two classes: a meet in
    the middle on the packed certificates, then a recheck of all of them."""
    require(case.minority == (4, 4))
    (left, right), (left_sign, right_sign) = case.classes, case.signs
    moduli = tuple(case.moduli[i] for i in packed)
    found = meet([tuple(-left_sign * case.keys[p][i] % mu for i, mu in zip(packed, moduli))
                  for p in left],
                 tuple(target[i] % mu for i, mu in zip(packed, moduli)),
                 [tuple(right_sign * case.keys[p][i] % mu for i, mu in zip(packed, moduli))
                  for p in right],
                 moduli, buckets)
    candidates = [(tuple(left[i] for i in s), tuple(right[j] for j in t))
                  for s, t in found['pairs']]
    return dict(subsets=found['subsets'], candidates=len(candidates),
                survivors=[placement for placement in candidates
                           if case.holds(placement, target)])


def verify_all():
    """Search both count vectors and return the exact totals for inspection."""
    vectors = count_vectors()
    require(vectors == ((4, 247, 125), (247, 4, 125)))
    subsets, candidates = [], []
    for counts in vectors:
        case = Case(N, ORDER, MODULUS, counts, (0, 1))
        require(case.moduli == (1, 3, 3 ** 2, 3 ** 4, 3 ** 5, 3 ** 6, 3 ** 8, 3 ** 9, 3 ** 10,
                                3 ** 13, 3 ** 14))
        found = search(case, case.target)
        require(found['subsets'] == (comb(251, 4), comb(251, 4)))
        require(not found['survivors'])
        subsets.append(found['subsets'])
        candidates.append(found['candidates'])
    return dict(vectors=vectors, subsets=tuple(subsets), candidates=tuple(candidates),
                placements=sum(a * b for a, b in subsets), survivors=0)


if __name__ == '__main__':
    result = verify_all()
    # TODO: state the proved bound, with the number of count vectors, placements tried, and
    # placements surviving behind it.
    print(f'Claude: "m*(752) <= 10: {len(result["vectors"])} count vectors, '
          f'{result["placements"]:,} placements, {result["survivors"]} survivors."')
