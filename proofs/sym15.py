#!/usr/bin/env python3
"""Verify the antisymmetric sign sequence of length 795280 and exact order 15 in index.html#sym15.

Run python3 -B proofs/sym15.py from a checkout. The code uses only the standard
library. witness() returns its signs in index order, with the part containing 0 first.
"""
from itertools import accumulate
from pathlib import Path
import re


N, M = 795280, 15

# (length of order-13 source, number of times to repeat each sign, signed multiplicity)
BLOCKS = [
    (1200, 12, -1), (2368, 5, 1), (720, 12, -1), (2528, 3, 1), (1104, 5, -1),
    (672, 7, 1), (912, 4, 1), (672, 4, -1), (768, 2, -1),
    (672, 1, -3), (720, 1, -5), (768, 1, -4), (912, 1, 6), (1008, 1, 9),
    (1056, 1, -3), (1104, 1, 20), (1200, 1, 7), (1296, 1, -7), (1392, 1, 3),
    (1488, 1, -16), (1584, 1, -13), (1776, 1, 12), (2368, 1, -8), (2432, 1, -2),
    (2480, 1, 6), (2512, 1, -2), (2528, 1, 5), (2608, 1, -6), (2800, 1, -4),
    (2992, 1, 1)
]


def witness():
    """Join the stretched order-13 blocks around the length-720 center and normalize."""
    side = [1]
    for _ in range(13):
        side += [-a for a in side]
    side = [a for a in side for _ in range(14)]
    for u in range(1 << 13):
        pos = 14*u + bin(u).count("1")
        side[pos] *= -1

    page = (Path(__file__).resolve().parents[1] / 'index.html').read_text(encoding='utf-8')
    codes = {}
    for n, digits in re.findall(r'<code id="(\d+):13">([0-9A-F]+)</code>', page):
        bits = bin(int(digits, 16))[2:].zfill(4 * len(digits))
        left = [2*int(bit) - 1 for bit in bits]
        word = left + [-a for a in reversed(left)]
        assert len(word) == int(n) and int(n) not in codes
        codes[int(n)] = word
    for n, stretch, copies in BLOCKS:
        sign = copies // abs(copies)
        block = [sign*a for a in codes[n] for _ in range(stretch)]
        side.extend(block * abs(copies))
    assert len(side) == 397280
    word = side + codes[720] + [-a for a in reversed(side)]
    return [a * word[0] for a in word]


def moments(word, order):
    """Coefficients of (x-1)^k, k=0 through order, by repeated synthetic division."""
    coeff = list(reversed(word))
    result = []
    for _ in range(order):
        coeff = list(accumulate(coeff))
        result.append(coeff.pop())
    return result + [sum(coeff)]


def check(word):
    assert len(word) == N and word[0] == 1 and set(word) == {-1, 1}
    assert all(a == -b for a, b in zip(word, reversed(word)))
    jet = moments(word, M)
    assert jet[:M] == [0]*M and jet[M] != 0
    return jet


if __name__ == '__main__':
    print(N, check(witness()))
