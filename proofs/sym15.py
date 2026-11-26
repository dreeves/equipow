#!/usr/bin/env python3
"""Reconstruct and verify the antisymmetric order-15 sequences in index.html#sym15.

sym15.json lists the lengths in publication order. Each setup gives the width of
a Thue–Morse block, a mask for the negative offsets of the flipped positions,
and the signed length of the central sequence. Each triple in blocks gives an
order-13 source length, its stretch and its signed multiplicity, in join order.
degree15 gives the normalized sequence's coefficient of (x-1)^15 in decimal.

Run python3 -B proofs/sym15.py to check every record. witness(n) returns the
signs in index order, with the part containing 0 first. witness() retains the
original length 795280.
"""
from itertools import accumulate
import json
from pathlib import Path
import re


N, M = 795280, 15
_records = json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))
RECIPES = {r['n']: r for r in _records}
assert len(RECIPES) == len(_records)
BLOCKS = [tuple(b) for b in RECIPES[N]['blocks']]


def witness(n=N):
    """Join the stretched order-13 blocks around the specified center and normalize."""
    recipe = RECIPES[n]
    width, mask, center = recipe['setup']
    assert 0 <= mask < 2**13 and center % 32 == n % 32 == 16
    side = [1]
    for _ in range(13):
        side += [-a for a in side]
    side = [a for a in side for _ in range(width)]

    # Flip one position per block. A subset of the 13 steps chooses its block.
    starts = [width * 2**i for i in range(13)]
    offsets = [(1 - 2*((mask >> i) & 1)) * (step % 2 == 0) for i, step in enumerate(starts)]
    assert sum(map(abs, offsets)) < width
    positions = [-sum(min(t, 0) for t in offsets)]
    for step, t in zip(starts, offsets):
        positions += [x + step + t for x in positions]
    for u, x in enumerate(positions):
        assert x // width == u
        side[x] *= -1

    page = (Path(__file__).resolve().parents[1] / 'index.html').read_text(encoding='utf-8')
    codes = {}
    for source, digits in re.findall(r'<code id="(\d+):13">([0-9A-F]+)</code>', page):
        bits = bin(int(digits, 16))[2:].zfill(4 * len(digits))
        left = [2*int(bit) - 1 for bit in bits]
        signs = left + [-a for a in reversed(left)]
        assert len(signs) == int(source) and int(source) not in codes
        codes[int(source)] = signs
    for source, stretch, copies in recipe['blocks']:
        assert stretch > 0 and copies != 0
        sign = copies // abs(copies)
        block = [sign*a for a in codes[source] for _ in range(stretch)]
        side.extend(block * abs(copies))
    middle = [(center // abs(center))*a for a in codes[abs(center)]]
    signs = side + middle + [-a for a in reversed(side)]
    assert len(signs) == n
    return [a * signs[0] for a in signs]


def moments(word, order):
    """Coefficients of (x-1)^k, k=0 through order, by repeated synthetic division."""
    coeff = list(reversed(word))
    result = []
    for _ in range(order):
        coeff = list(accumulate(coeff))
        result.append(coeff.pop())
    return result + [sum(coeff)]


def check(word):
    assert len(word) in RECIPES and word[0] == 1 and set(word) == {-1, 1}
    assert all(a == -b for a, b in zip(word, reversed(word)))
    jet = moments(word, M)
    assert jet[:M] == [0]*M and jet[M] != 0
    return jet


if __name__ == '__main__':
    for length, recipe in RECIPES.items():
        coefficients = check(witness(length))
        assert coefficients[M] == int(recipe['degree15'])
        print(length, coefficients)
