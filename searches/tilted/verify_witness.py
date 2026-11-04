#!/usr/bin/env python3
"""Independent check of a code: plain integers, no project imports.  Decodes the page's form (left half, bit 1 = +1, then the (anti)symmetric mirror), and tests (x-1)^m by repeated synthetic division and by power sums in two different ways.
Usage: verify_witness.py n m code"""
import sys
def decode(n, m, code):
    s = 1 if m % 2 == 0 else -1
    bits = bin(int(code, 16))[2:].zfill(len(code) * 4)
    bits = bits[-(n // 2):] if len(bits) > n // 2 else bits.zfill(n // 2)
    left = [1 if b == '1' else -1 for b in bits]
    return left + [s * v for v in reversed(left)]
def order_division(f):
    # coefficients high to low; synthetic division by x - 1 until the remainder is not zero
    c = list(f); k = 0
    while True:
        out = []; acc = 0
        for v in c:
            acc += v; out.append(acc)
        if out[-1] != 0: return k
        c = out[:-1]; k += 1
def order_powersums(f):
    k = 0
    while sum(a * i ** k for i, a in enumerate(f)) == 0: k += 1
    return k
def order_powersums_1(f):
    k = 0
    while sum(a * (i + 1) ** k for i, a in enumerate(f)) == 0: k += 1
    return k
n, m, code = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
f = decode(n, m, code)
assert len(f) == n and all(v in (-1, 1) for v in f)
sy = all(f[i] == (1 if m % 2 == 0 else -1) * f[n - 1 - i] for i in range(n))
a, b, c = order_division(f), order_powersums(f), order_powersums_1(f)
print(f'n={n}: length {len(f)}, plus signs {f.count(1)}, (anti)symmetric {sy}; order by synthetic division {a}, by power sums on 0..n-1 {b}, on 1..n {c}')
assert a == b == c and a >= m
print(f'OK: order {a} >= {m}')
