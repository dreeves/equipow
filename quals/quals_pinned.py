#!/usr/bin/env python3
"""Quals for searches/pinned/, the search that found the examples of 2026-11-03.
Run: python3 -B quals/quals_pinned.py [name ...]   (no arguments: all quals).  Needs numpy, fpylll and mpmath, and `make` in searches/pinned/ first.

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the setup) and expectata (what must
happen); a failure's message or traceback gives the resultata (what happened instead).  Quals of arithmetic check it by an independent route: orders by synthetic
division in plain integers, counts by brute force over every sign vector.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, time, glob, math, random, itertools, subprocess, tempfile, traceback
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
PINNED = os.path.join(HERE, 'searches', 'pinned')
sys.path.insert(0, PINNED)           # each qual imports what it needs of the search, so that this file imports with only the standard library (quals_layout)


def order_div(a):
    """The order of a sequence: how many times x - 1 divides its polynomial, by synthetic division in plain integers."""
    p, k = list(reversed(a)), 0
    while True:
        q, c = [], 0
        for t in p:
            c += t; q.append(c)
        if q.pop(): return k
        p, k = q, k + 1


def decode(code, n, m):
    bits = bin(int(code, 16))[2:].zfill(4 * len(code))
    assert len(bits) == n // 2, (len(bits), n)
    left = [1 if b == '1' else -1 for b in bits]
    return left + [(-1) ** m * t for t in reversed(left)]


def witnesses():
    """Every witness file's (n, m, distinct codes), from its lines."""
    out = []
    for path in sorted(glob.glob(os.path.join(PINNED, 'witnesses', 'witness_*.txt'))):
        rows = [json.loads(line) for line in open(path)]
        assert {(r['n'], r['m']) for r in rows} == {(rows[0]['n'], rows[0]['m'])}, path
        out.append((rows[0]['n'], rows[0]['m'], sorted({r['code'] for r in rows})))
    return out


def residues(f, M):
    D = [0] * M
    for i, a in enumerate(f): D[i % M] += a
    return D


def q_witness_files_have_their_orders():
    # Replicata: searches/pinned/witnesses/: the page's six results, and 960:14 and 1440:15.
    # Expectata: every code decodes, by the paper's Table 5 convention, to a balanced sequence of order exactly m, by synthetic division, and (-1)^m-symmetric.
    # Resultata before: the results were only in a scratch directory.
    got = {(n, m) for n, m, _ in witnesses()}
    assert got == {(544, 10), (576, 12), (624, 12), (912, 13), (960, 14), (960, 15), (1008, 13), (1440, 15)}, got
    for n, m, codes in witnesses():
        for code in codes[:50]:
            f = decode(code, n, m)
            assert len(f) == n and sum(f) == 0 and order_div(f) == m, (n, m, code)
            assert all(f[n - 1 - i] == (-1) ** m * f[i] for i in range(n)), (n, m)


def q_witnesses_lie_in_their_residue_cosets():
    # Replicata: each witness's residue sums mod 4, 8, 16, 9, 27, 5 and 7, and one vector that no sequence has.
    # Expectata: every true vector is in rep + 2 L(M, m) (pinned_profiles.in_coset), the condition the search's profiles rest on; at n = 1008, order 13 the vector
    # mod 4 is not 0, as the 2-adic budget demands; and in_coset refuses a vector no sequence can have (all zero mod 5 at 1008, order 13, where 5 does not divide n).
    # Resultata before: the first profile search left out the parity coset, so that every coset at 1008:13 failed one 2-adic congruence.
    import pinned_profiles as profiles
    for n, m, codes in witnesses():
        f = decode(codes[0], n, m)
        s = (-1) ** m
        for M in (4, 8, 16, 9, 27, 5, 7):
            assert profiles.in_coset(n, M, m, s, residues(f, M)), (n, m, M, residues(f, M))
    f = decode(next(c for n, m, c in witnesses() if (n, m) == (1008, 13))[0], 1008, 13)
    assert any(residues(f, 4)), residues(f, 4)
    assert not profiles.in_coset(1008, 5, 13, -1, [0] * 5), 'all zero mod 5 is not admissible at 1008, order 13'


def q_the_budget_forces_d4_at_1008():
    # Replicata: pinned_profiles.enumerate_profiles at n = 1008 = 16 * 63, order 13, modulus 4, antisymmetric.
    # Expectata: mod 2, f = (x+1)^15 S^16, so (x-1)^13 (x+1) (x^2+1) cannot divide f: D_4 != 0, and the least vectors are +-(64, 64, -64, -64).
    # Resultata before: without the parity coset the enumeration offered D_4 = 0.
    import pinned_profiles as profiles
    use, Dvec, good = profiles.enumerate_profiles(1008, 4, 13, -1)
    assert sorted(Dvec(e) for _, e in good[:2]) == [[-64, -64, 64, 64], [64, 64, -64, -64]], good[:2]


def q_split_embedded_finds_every_row():
    # Replicata: rows whose embedding coordinate is nonzero on all of them, as LLL can leave them: (1, 0, 1), (0, 1, 1), (1, 1, 2) with the coordinate last; and rows with no unit there.
    # Expectata: one particular row, +1 there, and the homogeneous rows that the differences give; none when the gcd there is not 1.
    # Resultata before: reading off only rows with 0 there silently dropped basis vectors.
    from pinned_lattice import split_embedded
    hom, p = split_embedded([[1, 0, 1], [0, 1, 1], [1, 1, 2]], 2)
    assert p[2] == 1 and len(hom) == 2 and all(h[2] == 0 for h in hom), (hom, p)
    assert split_embedded([[1, 0, 2], [0, 1, 4]], 2)[1] is None


def q_enumeration_matches_brute_force():
    # Replicata: small free sets with and without pins, cosets of random sign vectors, enumerated with no pruning.
    # Expectata: exactly the sign vectors that brute force over all 2^f finds, the planted one among them.
    # Resultata before: new.
    import numpy as np
    from pinned_model import moment_col, pin_rows, block
    from pinned_lattice import Lattice, kernel
    random.seed(5)
    for m, f, pins in ((5, 14, ()), (6, 16, ()), (7, 18, ()), (7, 18, (3,)), (6, 18, (5,)), (5, 16, (4,))):
        r, s = (m // 2, 1) if m % 2 == 0 else (m // 2, -1)
        xs = block(f)
        cols = [moment_col(x, r, s) for x in xs]
        rows = [[cols[i][j] for i in range(f)] for j in range(r)]
        for q in pins: rows += [row for row in pin_rows(xs, q, s) if any(row)]
        L = Lattice(kernel(rows, f), beta=0)
        A = np.array(rows, dtype=np.int64)
        for _ in range(3):
            a0 = [random.choice((-1, 1)) for _ in range(f)]
            tau = A @ np.array(a0)
            want = {b for b in itertools.product((-1, 1), repeat=f) if (A @ np.array(b) == tau).all()}
            sols, nodes, R2, ns = L.cvp(L.babai(a0), maxsol=100000)
            assert {tuple(int(v) for v in row) for row in sols} == want and tuple(a0) in want, (m, f, pins)


def q_the_model_reproduces_the_preflights():
    # Replicata: pinned_model.log2E on a block of 168 pairs with the pins of the w-series (mod 9 and 3 of x', 5 and 7), at orders 12 and 13.
    # Expectata: within 1.5 bits of AGENTS.md's preflights of 1008, dimension 153: log10 E 5.82 at order 12 and -2.04 at order 13.
    # Resultata before: new.
    from pinned_model import block, log2E
    r12 = log2E(block(168), 6, 1, (3, 9, 5, 7)); r13 = log2E(block(168), 6, -1, (3, 9, 5, 7))
    assert r12[1] == r13[1] == 153, (r12, r13)
    assert abs(r12[0] - 5.82 * math.log2(10)) < 1.5 and abs(r13[0] + 2.04 * math.log2(10)) < 1.5, (r12, r13)


def q_more_pins_raise_the_ceiling_and_lower_the_dimension():
    # Replicata: pinned_model.log2E at order 13 on a block of 168 pairs, with the w-series' pins and with the pins of the 1008:13 search.
    # Expectata: the dimension falls from 153 to 125 and the ceiling rises from about 2^-6 to about 2^20.
    # Resultata before: new.
    from pinned_model import block, log2E
    old, new = log2E(block(168), 6, -1, (3, 9, 5, 7)), log2E(block(168), 6, -1, (8, 5, 7, 11, 13, 17, 19))
    assert (old[1], new[1]) == (153, 125) and old[0] < -5 and new[0] > 19, (old, new)


OLD_BLOCKS = """12 3
48 6
112 7
144 8
192 9
208 8
240 10
272 8
320 9
336 10
352 9
368 9
400 9
432 11
464 9
480 12
496 9
528 11
544 9
560 10
576 11
592 10
608 10
624 11
656 10
672 12
688 10
720 12
752 10
768 12
784 10
800 11
816 12
832 11
848 11
880 11
896 11
912 12
928 11
944 11
976 11
992 11
1008 12
1024 11
"""


def firsts(blocks, emax, kmax=45):
    with tempfile.NamedTemporaryFile('w', suffix='.txt') as fh:
        fh.write(blocks); fh.flush()
        out = subprocess.run([os.path.join(PINNED, 'coins'), fh.name, '1', str(emax), str(kmax), '20000000'], capture_output=True, text=True, timeout=600).stdout
    return [int(k) for k in re.findall(r'^e=\d+ first K=(\d+)', out, re.M)]


def q_coins_reproduce_the_old_firsts_and_find_the_new():
    # Replicata: coins (the search that pow2.py's docstring describes) on the blocks of the page before 2026-11-03, and with the blocks of that day.
    # Expectata: 10, 20, 29, 37, 39 for excess 1 to 5 on the old blocks, the theorem's until then; 10, 20, 28, 36, 39 on the new.
    # Resultata before: new.
    assert firsts(OLD_BLOCKS, 5) == [10, 20, 29, 37, 39], firsts(OLD_BLOCKS, 5)
    new = {int(a): int(b) for a, b in (line.split() for line in OLD_BLOCKS.strip().split('\n'))}
    new.update({544: 10, 576: 12, 624: 12, 912: 13, 960: 15, 1008: 13})
    text = ''.join(f'{n} {m}\n' for n, m in sorted(new.items()))
    assert firsts(text, 5) == [10, 20, 28, 36, 39], firsts(text, 5)


def run_fixed_signs(argv):
    import pinned_ap
    return pinned_ap.search(pinned_ap.parser().parse_args(argv), lambda *x: None)


def q_the_fixed_signs_search_finds_544_10():
    # Replicata: pinned_ap at 544, order 10, the free set outside the class x = 0 mod 3, seed 1: the control for lengths that 3 does not divide.
    # Expectata: a witness within 10 minutes, its order 10 by synthetic division.
    # Resultata before: new; AGENTS.md's w10s preflight had given about 10^-14 per try at 544.
    found = run_fixed_signs('544 10 8,9,5,7,11,13,17,19 --free non3 --noise 0.2 --swaps 1e6 --maxdn 1000 --cap 2e5 --topk 8 --t1 1 --t2 1 --tlimit 600'.split())
    assert found and order_div(decode(found[0]['code'], 544, 10)) == 10, found[:1]


def q_the_fixed_signs_search_finds_1008_13():
    # Replicata: pinned_ap at 1008, order 13, the free set the pairs with x divisible by 3, seed 31: the control for lengths that 3 divides.
    # Expectata: a witness within 15 minutes, its order 13 by synthetic division.
    # Resultata before: new; AGENTS.md's w13 preflights had found no consistent configuration.
    found = run_fixed_signs('1008 13 8,5,7,11,13,17,19 --seed 31 --maxdn 2.5 --cap 1e6 --topk 16 --qgate 15 --maxnodes 2e9 --tlimit 900'.split())
    assert found and order_div(decode(found[0]['code'], 1008, 13)) == 13, found[:1]


def q_the_ring_search_finds_1440_14():
    # Replicata: pinned_block at 1440, order 14, a central block of 190 pairs, seed 7: the control for the rings, with no congruences.
    # Expectata: a witness within 15 minutes, of order at least 14 by synthetic division.
    # Resultata before: new.
    import argparse, pinned_block
    a = argparse.Namespace(n=1440, m=14, f=190, qs='8,9,5,7,11,13,17,19,23', seed=7, ratio=1.05, c=0.0, floor=1.0, maxnodes=1e9, tlimit=900.0, qgate=40.0, stop=1, flips=3e4, swaps=6e4)
    found = pinned_block.search(a, lambda *x: None)
    assert found and order_div(decode(found[0]['code'], 1440, 14)) == 14, found[:1]


def q_pruning_bound_scales_with_the_coset():
    # Replicata: bound_fn(0, 0) at k = d, for budgets R2 of different cosets.
    # Expectata: the bound at the last level is the coset's own budget, whatever it is.
    # Resultata before: a bound of k/4 fell below R2 in well-centred cosets, cutting off every solution in them.
    from pinned_lattice import bound_fn
    b = bound_fn(0.0, 0.0)
    assert all(abs(b(125, 125, R2) - R2) < 1e-9 for R2 in (31.0, 39.5)), b(125, 125, 39.5)


def main():
    names = sys.argv[1:] or [n for n in globals() if n.startswith('q_')]
    failed = 0
    for n in names:
        t0 = time.time()
        try:
            globals()[n]()
            # TODO: runner line; says the named qual passed, with its seconds
            print(f'Claude: "PASSED" {n} ({time.time() - t0:.1f} s)', flush=True)
        except Exception:
            failed += 1
            # TODO: runner line; says the named qual failed, with its seconds, followed by the traceback
            print(f'Claude: "FAILED" {n} ({time.time() - t0:.1f} s)\n' + traceback.format_exc(), flush=True)
    # TODO: runner summary; says how many quals passed out of how many
    print(f'Claude: "{len(names) - failed} of {len(names)} passed"')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
