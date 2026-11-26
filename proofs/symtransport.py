#!/usr/bin/env python3
"""Construct the right half of the sign sequence in index.html#symtransport.

Run python3 -B proofs/symtransport.py in the project's Python environment.
The length formula gives the full sequence length even when the signs are too numerous to store.
"""
from itertools import accumulate
from symlarge import b, period, rank


def coordinates(m):
    """Coordinates of half the initial moment sum in the integral basis u(1), ..., u(d)."""
    assert m >= 2
    d, half = rank(m), period(m) // 2
    c = [0] * d
    for k in reversed(range(d)):
        total = sum(b(m, k, j) for j in range(1, half + 1))
        assert total % 2 == 0 and b(m, k, k + 1) == 1
        c[k] = total // 2 - sum(c[j-1] * b(m, k, j) for j in range(k + 2, d + 1))
    return c


def stride(d, K, Q, ell):
    return (d + 1) * (K*Q + ell)


def dimensions(m):
    """Return T, K, c and the length of one copy of W, rounded to a positive multiple of T."""
    T, d, K = period(m), rank(m), 1 << (m - 1)
    c = coordinates(m)
    Q = sum(map(abs, c))
    # For each nonempty group the last occurrence and k=K-1 give its farthest flip.
    farthest = max((j + (K - 1)*stride(d, K, Q, ell)
                    for j, (value, ell) in enumerate(zip(c, accumulate(map(abs, c))), 1)
                    if value), default=T//2)
    width = max(T, ((farthest - T//2 + T - 1) // T) * T)
    return T, K, c, width


def seed_length(m):
    T, K, _, width = dimensions(m)
    return T + 2*K*width


def right_half(m):
    """The actual right-half signs. Its length grows exponentially with m."""
    T, K, c, width = dimensions(m)
    half, d, Q = T//2, rank(m), sum(map(abs, c))
    tm = [(-1)**bin(k).count('1') for k in range(K)]
    prescribed = {}
    ell = 0
    for j, count in enumerate(c, 1):
        for _ in range(abs(count)):
            ell += 1
            h = stride(d, K, Q, ell)
            for k in range(1, K):
                pos = j + k*h
                assert half < pos <= half + width and pos not in prescribed
                prescribed[pos] = -(count // abs(count)) * tm[k]
    block = [prescribed.get(j, 1) for j in range(half + 1, half + width + 1)]
    signs = [1]*half + [a*s for a in tm for s in block]
    for j in prescribed:
        signs[j-1] *= -1
    return signs


if __name__ == '__main__':
    for m in (2, 3, 4):
        signs = right_half(m)
        assert all(sum(a * b(m, k, j) for j, a in enumerate(signs, 1)) == 0 for k in range(rank(m)))
        assert 2*len(signs) == seed_length(m)
    for m in range(15, 20):
        print(m, seed_length(m))
