#!/usr/bin/env python3
"""Quals for the width test: certbb's cut token ('D', u, c), its checker, its search, width.py's directions, the
CODE fingerprint, and migrate_journals.py.  Run: nice -n 19 python3 -B quals_width.py [name ...]

Each qual is a function q_*: a passing qual returns, a failing one raises; its comment gives the replicata and the
expectata, a failure's message or traceback the resultata.  Quals marked "regression" pin values found by the
verification's scans (scratch/strategy/verify-engine/thin240.out, the journals), by the first green run, or by the
three verifications of the first width-test revision (scratch/width/verify-soundness, verify-recheck and
verify-mutants: the forged streams, the mutation pass's surviving mutants, and the re-check's false thin claims).  The
regression against the width test's absence replays scratch/width/old_certbb.py, the certbb.py of 2026-10-08 pinned
before this work (not in git: scratch/ is ignored; the quals assert it is there).  Qual journals go under
scratch/width/quals/; no journal or log of a run is read for writing, and the live run is never touched.
"""
import sys
sys.dont_write_bytecode = True
import os, json, time, random, itertools, hashlib, importlib.util, inspect, shutil, subprocess, tempfile, traceback, math, collections
import numpy as np
import sympy as sp
from scipy.optimize import linprog
import overnight_v5 as v5
import certbb
import width
import migrate_journals as mj
from quals_v5 import at, expect_proof_error, expect_assertion, patched, run_child, power_sum_solutions, solved, x01, \
    example_node, choice_of, EXAMPLE, C2, BIG, GiveUp

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.path.join(HERE, 'scratch', 'width')
QUALS = os.path.join(SCRATCH, 'quals')
os.makedirs(QUALS, exist_ok=True)
CASCADE_240 = (3, 5, 7, 4, 8, 11, 13, 9)
CASCADE_304 = (3, 5, 4, 7, 8, 9)
TOP_240 = '3:[40,40,40] 5:[24,24,24,24,24] 7:[14,21,3,10,17,24,31] 4:[30,30,30,30]'
# the hardest INFEASIBLE leaf of the 240@11 journal (1,929,339 LP solves), thin along the last direction (j = 181)
HARD = TOP_240 + ' 8:[17,17,13,21,13,13,17,9] 11:[11,11,11,11,11,11,11,11,11,5,16] 13:[12,11,10,9,8,7,12,11,10,9,8,7,6] 9:[12,12,12,12,21,12,16,7,16]'
# three open leaves of the 240@11 journal that the verification's scan closed (thin240.out: thin along j = 181)
THIN = (TOP_240 + ' 8:[17,17,13,21,13,13,17,9] 11:[11,11,11,11,11,11,11,11,11,5,16] 13:[12,11,10,9,8,7,12,11,10,9,8,7,6] 9:[15,12,18,15,12,9,10,16,13]',
        TOP_240 + ' 8:[17,17,13,21,13,13,17,9] 11:[11,11,11,11,11,11,11,11,11,5,16] 13:[12,11,10,9,8,7,12,11,10,9,8,7,6] 9:[12,12,12,12,12,12,16,16,16]',
        TOP_240 + ' 8:[17,17,13,21,13,13,17,9] 11:[11,11,11,11,11,11,11,11,11,5,16] 13:[7,8,9,10,11,12,6,7,8,9,10,11,12] 9:[15,15,15,15,15,15,10,10,10]')
# the open depth-5 node of the 240@11 journal that the plan's scan closed (thin_240_depth5.out: j = 209)
DEPTH5 = TOP_240 + ' 8:[17,17,5,21,13,13,25,9]'
# two open leaves of the 240@11 journal with no thin direction among all 182 (thin240all.out, thin2_240.out)
NOTTHIN = (TOP_240 + ' 8:[21,17,17,21,9,13,13,9] 11:[11,11,11,11,11,11,11,11,11,5,16] 13:[12,11,10,9,8,7,12,11,10,9,8,7,6] 9:[15,18,12,15,9,12,10,13,16]',
           TOP_240 + ' 8:[17,21,21,17,13,9,9,13] 11:[11,11,11,11,11,11,11,11,11,5,16] 13:[12,11,10,9,8,7,12,11,10,9,8,7,6] 9:[12,18,15,12,9,15,16,13,10]')
# La: a journaled INFEASIBLE leaf of 304@9 (10009 LP solves, proof sha1 f6cc9a4a...), the engine angle's baseline
LA = '3:[51,10,91] 5:[43,18,43,18,30] 4:[38,38,38,38] 7:[15,22,29,25,25,18,18] 8:[17,17,17,21,21,21,21,17] 9:[17,2,29,14,2,29,20,6,33]'
LA_SHA1 = 'f6cc9a4a'
# a journaled INFEASIBLE leaf of 304@9 (11 LP solves, 6 leaves, proof sha1 798277eb...): the re-check's worst node for
# false thin claims, 23 directions whose exact range touches an integer that the float range falls short of
FALSE_THIN = '3:[51,10,91] 5:[43,18,43,18,30] 4:[38,38,38,38] 7:[29,22,15,18,18,25,25] 8:[17,21,17,21,21,17,21,17] 9:[11,5,26,23,2,32,17,3,33]'
FALSE_THIN_SHA1 = '798277ebd7b51f9c5781ad68b8d89fe03e573e2e'
# the live 240@11 journal's header line as it was before this work (its code field is the old CODE); read only
OLD_HEADER = {"tag": "overnight_v5", "N": 240, "order": 11, "code": "ff0e0b36ed39ffe695f968b7fa5b0183525be715",
              "solver": "certbb", "budget_unit": "LP solves", "highs": "1.12.0 (4f96ee8)"}
# the CODE of the first width-test revision (2026-10-10 18:00), the live 240@11 journal's header since its restart
FIRST_WIDTH_CODE = '4cb6199c8e1cb12bf4919992d952ec6f24fbb562'
# proof sha1s pinned by the first green run (2026-10-10, HiGHS 1.12.0 (4f96ee8)): the cut proofs of the nodes above
# and C2's old-format proof (regression; the token streams are deterministic for the HiGHS build, as the branch and
# bound's are, and a cut's certificates come from its sides' dual rays)
PINNED = {'HARD': 'c6816b9bfb06f0b64ee1ae378837463add919454', 'THIN0': '29f12b08f6b0bf211397c40ece336c6438416c38',
          'THIN1': 'cd40675a4706a969d4e644b2a02b2dc15b599ed6', 'THIN2': 'b2803a8ca042a95c6a6506502172fbf543f616cd',
          'DEPTH5': '6daacece3c9065b7c921c64763da2ce70be50db7', 'C2': '052a5d716d67fd1c147ab13dd58af6fb60aa654b'}
# the false thin claims (cut_fail) of the root scans of La, FALSE_THIN and the 304@8 example's node (regression: the
# mutation pass and the re-check measured them; the 240 nodes of the quals make none)
CLAIMS = {'LA': 3, 'FALSE_THIN': 23, 'W304': 7}
# the directions per cascade prefix, as sha1(repr([list(d.u) for d in directions])) in scanning order (regression: the
# mutation pass's dir_digest_baseline.out; LLL at another delta changes every one of them)
DIGESTS = {(240, ()): 'ad4fd857dd619aec01b987f994ae8c303d19ca29', (240, (3,)): '6d0f88ede74bd680fa2d13375bb007a79deca47d',
           (240, (3, 5)): 'd336c242123b3ed783d1428244b294f7dd12ca76', (240, (3, 5, 7)): '3b9f8f660157b1f23b3cbc078f6e93f4a986e9e8',
           (240, (3, 5, 7, 4)): 'e083c1df8ef04d93aa51170459413fbbdb49d49a', (240, (3, 5, 7, 4, 8)): 'eb7d3d15434aa8414ea64c4713589ec73529284c',
           (240, (3, 5, 7, 4, 8, 11)): '79c1b0f4e36992e4c2d598ada0981bece83d2bcd', (240, (3, 5, 7, 4, 8, 11, 13)): 'bdb750f9dd825f3e01c56636991034df9d19bca5',
           (240, (3, 5, 7, 4, 8, 11, 13, 9)): 'd6f403fc5d5b771c8958fb5d3b09d07191171edd',
           (304, ()): '02b11d605db6a6a425a90f067e322263fdaf9bc9', (304, (3,)): '74be40a4f09bfd885cdc35d0896b5c3713ecacfc',
           (304, (3, 5)): '9a339cac7a98e5563c16728a295adabbb586ac7b', (304, (3, 5, 4)): '6b37ae5f53586a82589175640dbcc8220db56cd6',
           (304, (3, 5, 4, 7)): 'fbd691f230c6ac384f1c6bc9bdb8d57b8ffdbc06', (304, (3, 5, 4, 7, 8)): '3e269248e43c0011597738eb7e3d1a35ccba1611',
           (304, (3, 5, 4, 7, 8, 9)): '27bee4189570a3cf13e6163674dd51132e36dfd6'}


def parse_key(key):
    """The node tuple of an overnight_v5.node_key string with single-vector constraints only."""
    node = []
    for part in key.split():
        M, vec = part.split(':', 1)
        assert vec.startswith('[') and vec.endswith(']'), part
        node.append((int(M), (tuple(int(t) for t in vec[1:-1].split(',')),)))
    return tuple(node)


def old_certbb():
    """scratch/width/old_certbb.py, the certbb.py pinned before the width test, as a module named old_certbb."""
    path = os.path.join(SCRATCH, 'old_certbb.py')
    assert os.path.exists(path), path
    spec = importlib.util.spec_from_file_location('old_certbb', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha1_of(tokens):
    sha = hashlib.sha1()
    for t in tokens: sha.update(repr(t).encode())
    return sha.hexdigest()


def kept_rows(moments, moduli):
    """The LP's exact rows A (as certbb's Guide builds them) and their node_rows indices, for a node of zero counts."""
    lp = certbb.Lp(moments, moduli)
    rows = certbb.node_rows(moments, [(M, (0,) * M) for M in moduli])
    keep = list(range(lp.k)) + list(lp.row)
    A = []
    for i in keep:
        a, _ = rows[i]
        row = [0] * moments.N
        for p, c in a: row[p] = c
        A.append(tuple(row))
    return tuple(A), keep


def accepted(moments, node, tokens, lo=None, hi=None):
    """verify's sha1 for a proof it accepts."""
    return certbb.verify(moments, node, tokens, lo, hi)


def outcome(moments, tokens, lo=None, hi=None):
    """'accepted' when verify accepts the stream (no node), else the ProofError's message; any other exception is
    the qual's failure."""
    try:
        certbb.verify(moments, (), tokens, lo, hi)
        return 'accepted'
    except certbb.ProofError as e:
        return 'ProofError: ' + str(e)


def honest(rows, l, u, path):
    """A complete proof (tokens) for the box under the path when no point of it satisfies the rows and the path
    rows: every free position split, each point closed by +-1 on the first row or path row it breaks; None when some
    point satisfies them all."""
    free = [p for p in range(len(l)) if l[p] < u[p]]
    tokens = []

    def close(x):
        for i, (a, b) in enumerate(rows):
            d = b - sum(c * x[p] for p, c in a)
            if d: return [0] * i + [1 if d > 0 else -1] + [0] * (len(rows) - i - 1 + len(path))
        for j, (s, a, b) in enumerate(path):
            if s * (b - sum(c * x[p] for p, c in a)) > 0: return [0] * (len(rows) + j) + [s] + [0] * (len(path) - j - 1)
        return None

    def rec(l, u, k):
        if k == len(free):
            n = close(l)
            tokens.append(('L', n))
            return n is not None
        p = free[k]
        tokens.append(('B', p))
        return rec(*certbb.fixed(l, u, p, 0), k + 1) and rec(*certbb.fixed(l, u, p, 1), k + 1)

    return tokens if rec(list(l), list(u), 0) else None


def forge(rows, l, u, path, signs, bound=1.0, scale=2 ** 20):
    """The forger: integer multipliers n (rows, then path rows) maximizing lower_bound over the box by an LP, with
    the path multipliers' signs as given (+1: >= 0, -1: <= 0, 0: free) and |n| <= bound, rounded at scale; None
    unless lower_bound is positive exactly.  The forger only proposes; the Check decides."""
    N = len(l)
    allrows = rows + [(a, b) for _, a, b in path]
    k = len(allrows)
    c = np.array([-float(b) for _, b in allrows] + [-1.0] * N)       # maximize sum n_i beta_i + sum h_p
    G = np.zeros((N, k))
    for i, (a, _) in enumerate(allrows):
        for p, co in a: G[p, i] -= co                                  # g_p = sum_i G[p, i] n_i
    A, B = [], []
    for p in range(N):
        for end in (l[p], u[p]):                                       # h_p <= g_p * end
            row = np.zeros(k + N)
            row[:k], row[k + p] = -G[p] * end, 1.0
            A.append(row)
            B.append(0.0)
    bounds = [(-bound, bound)] * len(rows) + [{1: (0, bound), -1: (-bound, 0), 0: (-bound, bound)}[s] for s in signs] + [(None, None)] * N
    r = linprog(c, A_ub=np.array(A), b_ub=np.array(B), bounds=bounds, method='highs')
    if r.status != 0 or -r.fun <= 1e-9: return None
    n = [round(t * scale) for t in r.x[:k]]
    return n if certbb.lower_bound(allrows, l, u, n) > 0 else None


# ---------- the checker: the cut token ----------

def q_cut_tokens_on_toys():
    # Replicata: toy systems in certbb.Moments form (no node), their proofs fed to certbb.verify.
    #   (1) N = 2, x0 + x1 = 1: feasible; a cut u = (1, -1), c = 0 with the <= side "closed" by [1, -1] (wrong: that
    #       side holds (0, 1)), and with a positive multiplier on the <= row.
    #   (2) N = 2, x0 + x1 = 1 and x0 - x1 = 1 (only (1, 0)): cut u = (0, 1), c = 0: the <= side (x1 <= 0) holds (1, 0),
    #       so no certificate closes it: a zero one and a guessed one fail; the cut u = (0, 1), c = -1 leaves no point
    #       of the box on its <= side, so it does not cut the box.
    #   (3) N = 2, x0 + x1 = 2 and x0 - x1 = 1 (no 0/1 point; n = (1, 1) bounds 3 - 2 x0 >= 1): accepted bare, accepted
    #       with a cut u = (1, 0), c = 0 and the padded certificate on both sides, with two nested cuts, and with the
    #       >= side closed by [1, 1, 1] (the multiplier 1 on its cut row x0 >= 1 adds 1 - x0 <= 0 to 3 - 2 x0: the bound
    #       is 4 - 3 x0 >= 1); and rejected with u of length 3, a float in u, a float c, a bool in u, a 2-tuple
    #       D, a 3-tuple B and L, an unknown kind, a 1-tuple, a list for a token, a cut that does not cut the box (c = 1
    #       at the top of u.x's range, c = -1 under it, u = 0), a cut on a pinned box, a token after the last box, a
    #       certificate one short on a side, -1 on the >= side, a proof that ends after the <= side.
    # Expectata: accepted where said, ProofError everywhere else, with the messages named; and certbb.cuts, the
    # condition Check and the width test share, says which cuts cut (3)'s full box, its pinned box and its half-pinned
    # box (x0 = 1: u = (1, 1) takes the values 1 and 2 there, so c = 1 cuts it and c = 0 does not).
    m1 = certbb.Moments(((1, 1),), (1,))
    assert 'a certificate fails' in expect_proof_error(lambda: accepted(m1, (), [('D', [1, -1], 0), ('L', [1, -1])]))
    assert 'wrong sign' in expect_proof_error(lambda: accepted(m1, (), [('D', [1, -1], 0), ('L', [0, 1])]))
    m2 = certbb.Moments(((1, 1), (1, -1)), (1, 1))
    assert 'a certificate fails' in expect_proof_error(lambda: accepted(m2, (), [('D', [0, 1], 0), ('L', [0, 0, 0]), ('L', [0, 1, 1])]))
    assert 'a certificate fails' in expect_proof_error(lambda: accepted(m2, (), [('D', [0, 1], 0), ('L', [1, -1, -1]), ('L', [0, 1, 1])]))
    assert 'does not cut' in expect_proof_error(lambda: accepted(m2, (), [('D', [0, 1], -1), ('L', [0, 0, -1]), ('L', [0, 0, 0])]))
    m3 = certbb.Moments(((1, 1), (1, -1)), (2, 1))
    bare = accepted(m3, (), [('L', [1, 1])])
    cut = accepted(m3, (), [('D', [1, 0], 0), ('L', [1, 1, 0]), ('L', [1, 1, 0])])
    nested = accepted(m3, (), [('D', [1, 0], 0), ('D', [0, 1], 0), ('L', [1, 1, 0, 0]), ('L', [1, 1, 0, 0]), ('L', [1, 1, 0])])
    assert len({bare, cut, nested}) == 3
    assert cut != accepted(m3, (), [('D', [1, 1], 0), ('L', [1, 1, 0]), ('L', [1, 1, 0])])    # the sha1 covers u
    bad = {'not 2 integers and an integer': [('D', [1, 0, 0], 0), ('L', [1, 1, 0]), ('L', [1, 1, 0])],
           'float in u': [('D', [1.0, 0], 0), ('L', [1, 1, 0]), ('L', [1, 1, 0])],
           'float c': [('D', [1, 0], 0.0), ('L', [1, 1, 0]), ('L', [1, 1, 0])],
           'bool in u': [('D', [True, 0], 0), ('L', [1, 1, 0]), ('L', [1, 1, 0])],
           'D without c': [('D', [1, 0]), ('L', [1, 1, 0]), ('L', [1, 1, 0])],
           'B with a third element': [('B', 0, 0), ('L', [1, 1]), ('L', [1, 1])],
           'L with a third element': [('L', [1, 1], 0)],
           'unknown kind': [('X', [1, 1])],
           'a 1-tuple': [('L',)],
           'not a tuple': [['L', [1, 1]]],
           'c at the top of the box': [('D', [1, 0], 1), ('L', [1, 1, 0]), ('L', [1, 1, 0])],
           'c under the box': [('D', [1, 0], -1), ('L', [1, 1, 0]), ('L', [1, 1, 0])],
           'u zero': [('D', [0, 0], 0), ('L', [1, 1, 0]), ('L', [1, 1, 0])],
           'a token after the last box': [('L', [1, 1]), ('L', [1, 1])],
           'a side certificate one short': [('D', [1, 0], 0), ('L', [1, 1]), ('L', [1, 1, 0])],
           '-1 on the >= side': [('D', [1, 0], 0), ('L', [1, 1, 0]), ('L', [1, 1, -1])],
           'ends after the <= side': [('D', [1, 0], 0), ('L', [1, 1, 0])]}
    for name, proof in bad.items():
        expect_proof_error(lambda: accepted(m3, (), proof))
    accepted(m3, (), [('D', [1, 0], 0), ('L', [1, 1, 0]), ('L', [1, 1, 1])])
    assert 'does not cut' in expect_proof_error(lambda: accepted(m3, (), bad['c at the top of the box']))
    assert 'does not cut' in expect_proof_error(lambda: accepted(m3, (), [('D', [1, 0], 0), ('L', [1, 1, 0])], [1, 0], [1, 0]))
    assert 'one integer per row' in expect_proof_error(lambda: accepted(m3, (), bad['a side certificate one short']))
    assert 'wrong sign' in expect_proof_error(lambda: accepted(m3, (), bad['-1 on the >= side']))
    assert 'ends early' in expect_proof_error(lambda: accepted(m3, (), bad['ends after the <= side']))
    assert 'of its length' in expect_proof_error(lambda: accepted(m3, (), bad['B with a third element']))
    assert 'of its length' in expect_proof_error(lambda: accepted(m3, (), bad['L with a third element']))
    assert certbb.cuts([1, 0], 0, [0, 0], [1, 1]) and not certbb.cuts([1, 0], 1, [0, 0], [1, 1])
    assert not certbb.cuts([1, 0], -1, [0, 0], [1, 1]) and not certbb.cuts([0, 0], 0, [0, 0], [1, 1])
    assert not certbb.cuts([1, 0], 0, [1, 0], [1, 0]) and not certbb.cuts([1, 1], 0, [1, 0], [1, 1]) and certbb.cuts([1, 1], 1, [1, 0], [1, 1])


def q_cut_tokens_at_40_6():
    # Replicata: at 40@6, the node ((4, ((0, 0, 0, 0),)),), whose counts total 0 where the moment row of degree 0 says
    # 20, so that n0 = (1 on that row, -2 on each count row) bounds 40 on every box; proofs with hand-made cuts.
    # Expectata: accepted: a cut on u = e_0 with n0 + [0] on both sides; the same cut with the multiplier on the cut
    # row -1 on the <= side and +1 on the >= side (the signs allowed); two nested cuts; a cut then a split then
    # certificates.  ProofError: +1 on the <= side, -1 on the >= side, a certificate without the cut's entry, u of
    # length 39, c as a float, a cut on the box pinned to all zeros, a cut after the box is closed; and verify's sha1
    # covers u: the same proof with u = e_1 has another sha1.  The accepted proofs' sha1s equal the sha1 of their
    # tokens' reprs (the proof sha1 of certbb's docstring).
    at(40, 6)
    m, node = v5.moments(6), ((4, ((0, 0, 0, 0),)),)
    n0 = [1] + [0] * 5 + [-2] * 4
    e = lambda p: [int(q == p) for q in range(40)]
    assert certbb.lower_bound(certbb.node_rows(m, choice_of(node)), [0] * 40, [1] * 40, n0) == 40
    ok = [[('D', e(0), 0), ('L', n0 + [0]), ('L', n0 + [0])],
          [('D', e(0), 0), ('L', n0 + [-1]), ('L', n0 + [1])],
          [('D', e(0), 0), ('D', e(1), 0), ('L', n0 + [0, 0]), ('L', n0 + [0, 0]), ('L', n0 + [0])],
          [('D', e(0), 0), ('B', 1), ('L', n0 + [0]), ('L', n0 + [0]), ('L', n0 + [0])]]
    for proof in ok:
        assert accepted(m, node, proof) == sha1_of(proof)
    assert accepted(m, node, ok[0]) != accepted(m, node, [('D', e(1), 0), ('L', n0 + [0]), ('L', n0 + [0])])
    bad = [[('D', e(0), 0), ('L', n0 + [1]), ('L', n0 + [0])],
           [('D', e(0), 0), ('L', n0 + [0]), ('L', n0 + [-1])],
           [('D', e(0), 0), ('L', n0), ('L', n0 + [0])],
           [('D', e(0)[:39], 0), ('L', n0 + [0]), ('L', n0 + [0])],
           [('D', e(0), 0.0), ('L', n0 + [0]), ('L', n0 + [0])],
           [('L', n0), ('D', e(0), 0)]]
    for proof in bad:
        expect_proof_error(lambda: accepted(m, node, proof))
    expect_proof_error(lambda: accepted(m, node, ok[0], [0] * 40, [0] * 40))


def q_old_proofs_check_unchanged():
    # Replicata: at 240@11, the old certbb's proof of node C2 (B and L tokens only), fed to the new certbb.verify, and
    # the old certbb's verify fed the same tokens.
    # Expectata: both accept it with the same sha1: a proof of the old format checks unchanged, so journaled proof sha1s
    # stay valid.  (Regression: C2's proof sha1 is pinned from the first green run.)
    at(240, 11)
    old = old_certbb()
    tokens = []
    verdict, _, _ = old.solve(v5.moments(11), C2, BIG, tokens.append)
    assert verdict == 'INFEASIBLE' and all(t[0] in 'BL' for t in tokens)
    assert certbb.verify(v5.moments(11), C2, tokens) == old.verify(v5.moments(11), C2, tokens) == sha1_of(tokens)
    assert PINNED['C2'] == sha1_of(tokens), sha1_of(tokens)


def q_cut_sides_meet():
    # Replicata: N = 2, x0 + x1 = 1, whose 0/1 points (1, 0) and (0, 1) both have u.x = 1 for u = (1, 1); the cut
    # ('D', [1, 1], c) with the <= side closed by [1, -1] and the >= side by [-1, 1], at c = 0 and at c = 1.
    # Expectata: ProofError 'a certificate fails' both times: at c = 0 the >= side u.x >= 1 holds both points ([-1, 1]
    # bounds 0), at c = 1 the <= side u.x <= 1 does ([1, -1] bounds 0).  A checker whose sides leave a slab between
    # them (the >= side as u.x >= c + 2, or the <= side as u.x <= c - 1) accepts one of the two proofs, and so closes
    # a system with 0/1 points (the mutation pass's C03 and C04).
    m = certbb.Moments(((1, 1),), (1,))
    for c in (0, 1):
        msg = expect_proof_error(lambda: accepted(m, (), [('D', [1, 1], c), ('L', [1, -1]), ('L', [-1, 1])]))
        assert 'a certificate fails' in msg, (c, msg)


def q_cut_path_multipliers_are_ints():
    # Replicata: (1) N = 2, x0 + x1 = 2 and x0 - x1 = 1 (no 0/1 point); the proof cut on u = (1, 0), c = 0 whose >= side
    # is closed by [1, 1, 1] (accepted, q_cut_tokens_on_toys), with that side's path multiplier 1 replaced by 1.0, by
    # True, by 0.5.  (2) N = 4, -3x0 - 3x1 + x2 + x3 = -1 and 3x0 - x2 + x3 = 3, whose one 0/1 point is (1, 0, 1, 1); the
    # cut u = (0, 0, 0, 2), c = 1 with both sides closed by two integers near 2^68 and 2^73 and one float on the cut row:
    # in certbb.lower_bound's mixed int/float arithmetic each side's bound comes out positive, in exact arithmetic it
    # is not (found by a random search, scratch/width/verify-mutants/scratchwork/float_proof.py).
    # Expectata: ProofError 'one integer per row' every time; a checker that lets a float through on a path row (the
    # mutation pass's C10) accepts (2), an INFEASIBLE verdict for a system with a 0/1 point that rests on floating point.
    m3 = certbb.Moments(((1, 1), (1, -1)), (2, 1))
    accepted(m3, (), [('D', [1, 0], 0), ('L', [1, 1, 0]), ('L', [1, 1, 1])])
    for bad in (1.0, True, 0.5):
        msg = expect_proof_error(lambda: accepted(m3, (), [('D', [1, 0], 0), ('L', [1, 1, 0]), ('L', [1, 1, bad])]))
        assert 'one integer per row' in msg, (bad, msg)
    m = certbb.Moments(((-3, -3, 1, 1), (3, 0, -1, 1)), (-1, 3))
    proof = [('D', [0, 0, 0, 2], 1), ('L', [295147905179352398979, 295147905179353108863, -4.427218577690298e+20]),
             ('L', [9444732965739290664622, 9444732965739291447706, 2.8334198897217867e+22])]
    assert 'one integer per row' in expect_proof_error(lambda: accepted(m, (), proof))


def q_nested_cuts_pair_each_multiplier_with_its_row():
    # Replicata: (1) m3 as above; the cut x0 <= 0 / x0 >= 1, inside its <= side the cut x1 <= 0 / x1 >= 1, and the box
    # x0 <= 0, x1 >= 1 closed by [1, 1, -1, 1] (-1 on its <= row, +1 on its >= row: bound 4 - x0 - x1 >= 2).  (2) N = 2,
    # x0 + x1 = 1 and x0 - x1 = -1, whose one 0/1 point is (0, 1); the cut 2x0 <= 1 / 2x0 >= 2, inside its <= side the cut
    # 2x1 <= 0 / 2x1 >= 1; (0, 1) lies in the box under 2x0 <= 1 and 2x1 >= 1, which [0, -2, 1, -1] "closes" with +1 on
    # its <= row and -1 on its >= row (both signs wrong; bound 2); the other two boxes closed by valid certificates.
    # Expectata: (1) accepted; (2) ProofError 'wrong sign' (a checker that pairs the signs with the wrong rows, the
    # mutation pass's C11, accepts it: an INFEASIBLE verdict for a system with a 0/1 point).
    m3 = certbb.Moments(((1, 1), (1, -1)), (2, 1))
    accepted(m3, (), [('D', [1, 0], 0), ('D', [0, 1], 0), ('L', [1, 1, 0, 0]), ('L', [1, 1, -1, 1]), ('L', [1, 1, 0])])
    m = certbb.Moments(((1, 1), (1, -1)), (1, -1))
    proof = [('D', [2, 0], 1), ('D', [0, 2], 0), ('L', [2, 0, -1, -1]), ('L', [0, -2, 1, -1]), ('L', [-1, -1, 1])]
    assert 'wrong sign' in expect_proof_error(lambda: accepted(m, (), proof))


def q_cut_row_stays_in_its_subtree():
    # Replicata: N = 2, x0 + x1 = 1 and x0 - x1 = 1, whose one 0/1 point is (1, 0).  (a) The proof B 0; in x0 = 0 the cut
    # u = (-1, 1), c = 0, both sides closed by [0, 1, 0] (x0 - x1 = 1 has no point with x0 = 0); then x0 = 1 closed by
    # [0, 0, 1], a certificate that uses the cut's >= row -x0 + x1 >= 1 although that row belongs to the other
    # subtree.  (b) The same with x0 = 1 closed by [0, 1] (needs 2 entries and fails there, since (1, 0) is a point).
    # Expectata: (a) ProofError 'one integer per row' (x0 = 1 has no path rows: a checker that lets the row reach it,
    # the mutation pass's C12, closes the box holding (1, 0), a wrong INFEASIBLE); (b) ProofError 'a certificate
    # fails'.  And m3's B-then-D proof with its sibling closed by [1, 1] is accepted.
    m = certbb.Moments(((1, 1), (1, -1)), (1, 1))
    proof = [('B', 0), ('D', [-1, 1], 0), ('L', [0, 1, 0]), ('L', [0, 1, 0]), ('L', [0, 0, 1])]
    assert 'one integer per row' in expect_proof_error(lambda: accepted(m, (), proof))
    assert 'a certificate fails' in expect_proof_error(lambda: accepted(m, (), proof[:4] + [('L', [0, 1])]))
    m3 = certbb.Moments(((1, 1), (1, -1)), (2, 1))
    accepted(m3, (), [('B', 0), ('D', [0, 1], 0), ('L', [1, 1, 0]), ('L', [1, 1, 0]), ('L', [1, 1])])


def q_forged_streams_on_systems_with_a_point():
    # Replicata: (1) 60 seeded systems of N = 3 with 1 or 2 rows of coefficients in -2..2 and a known 0/1 point x*
    # (the right-hand sides are its values); every cut u in {-2..2}^3 with c inside the box's range of u.x, the side
    # without x* proved honestly (every position split, each point closed on a row it breaks; skipped when that side
    # holds a point too), and on x*'s side every certificate in {-2..2}^(rows + 1) whose exact bound is positive, fed
    # as a complete stream.  (2) 400 seeded systems of N = 4..8 with 1..3 rows in -3..3 and a known point; a random
    # tree of 0..3 B and D steps down to the box holding x*, every other box proved honestly, and at x*'s box a
    # certificate forged by an LP (the best multipliers with the path signs right, each one flipped, and free),
    # and with the path entries reversed where there are two or more.
    # Expectata: no stream is accepted and every refusal is a ProofError: in (1) no certificate with the right sign on
    # the cut row has a positive bound (the sign rule is what refuses them: thousands have a positive bound with the
    # wrong sign); in (2) the forger finds certificates for the flipped and free signs (and none for the right ones),
    # all refused.  (The soundness verification's parts B and C, seeds 1 and 2.)
    rnd = random.Random(1)
    count = collections.Counter()
    for _ in range(60):
        k, xstar = rnd.randint(1, 2), [rnd.randint(0, 1) for _ in range(3)]
        W = tuple(tuple(rnd.randint(-2, 2) for _ in range(3)) for _ in range(k))
        m = certbb.Moments(W, tuple(sum(w[p] * xstar[p] for p in range(3)) for w in W))
        rows, l, u = certbb.node_rows(m, []), [0] * 3, [1] * 3
        for uu in itertools.product(range(-2, 3), repeat=3):
            uu = list(uu)
            for c in range(sum(min(t, 0) for t in uu), sum(max(t, 0) for t in uu)):
                a = [(p, t) for p, t in enumerate(uu) if t]
                le, ge = [(-1, a, c)], [(1, a, c + 1)]
                below = sum(t * x for t, x in zip(uu, xstar)) <= c
                other = honest(rows, l, u, ge if below else le)
                if other is None:
                    count['other side holds a point'] += 1
                    continue
                pre, side, tail = [('D', uu, c)] + ([] if below else other), le if below else ge, other if below else []
                count['cuts'] += 1
                for n in itertools.product(range(-2, 3), repeat=k + 1):
                    n = list(n)
                    if certbb.lower_bound(rows + [(a, b) for _, a, b in side], l, u, n) <= 0: continue
                    got = outcome(m, pre + [('L', n)] + tail)
                    assert got != 'accepted', (W, m.rhs, xstar, uu, c, n)
                    count['right sign' if side[0][0] * n[-1] >= 0 else 'wrong sign'] += 1
    assert count['right sign'] == 0 and count['wrong sign'] > 1000 and count['cuts'] > 1000, count
    rnd = random.Random(2)
    count = collections.Counter()
    for _ in range(400):
        N, k = rnd.randint(4, 8), rnd.randint(1, 3)
        xstar = [rnd.randint(0, 1) for _ in range(N)]
        W = tuple(tuple(rnd.randint(-3, 3) for _ in range(N)) for _ in range(k))
        m = certbb.Moments(W, tuple(sum(w[p] * xstar[p] for p in range(N)) for w in W))
        rows, l, u, path, prefix, pending, ok = certbb.node_rows(m, []), [0] * N, [1] * N, [], [], [], True
        for _ in range(rnd.randint(0, 3)):
            if rnd.random() < 0.5:
                free = [p for p in range(N) if l[p] < u[p]]
                if not free: break
                p = rnd.choice(free)
                prefix.append(('B', p))
                zero, one = certbb.fixed(l, u, p, 0), certbb.fixed(l, u, p, 1)
                if xstar[p] == 0:
                    pending.append(one + (path,))
                    l, u = zero
                else:
                    hp = honest(rows, *zero, path)
                    ok = hp is not None
                    if not ok: break
                    prefix += hp
                    l, u = one
            else:
                uu = [rnd.randint(-2, 2) for _ in range(N)]
                lo_b = sum(min(t * a, t * b) for t, a, b in zip(uu, l, u))
                hi_b = sum(max(t * a, t * b) for t, a, b in zip(uu, l, u))
                if lo_b >= hi_b: continue
                c = rnd.randint(lo_b, hi_b - 1)
                a = [(p, t) for p, t in enumerate(uu) if t]
                prefix.append(('D', uu, c))
                le, ge = path + [(-1, a, c)], path + [(1, a, c + 1)]
                if sum(t * x for t, x in zip(uu, xstar)) <= c:
                    pending.append((l, u, ge))
                    path = le
                else:
                    hp = honest(rows, l, u, le)
                    ok = hp is not None
                    if not ok: break
                    prefix += hp
                    path = ge
        tails = [honest(rows, *box) for box in reversed(pending)] if ok else [None]
        if any(t is None for t in tails):
            count['skipped'] += 1
            continue
        tail = [t for hp in tails for t in hp]
        assert honest(rows, l, u, path) is None                        # x*'s box has no honest proof
        signs = {'right': [s for s, _, _ in path], 'free': [0] * len(path)}
        for j in range(len(path)):
            signs[f'flip{j}'] = [(-s if i == j else s) for i, (s, _, _) in enumerate(path)]
        for name, ss in signs.items():
            n = forge(rows, l, u, path, ss)
            kind = name if name in ('right', 'free') else 'flip'
            if n is None:
                count[f'{kind}: no forgery'] += 1
                continue
            got = outcome(m, prefix + [('L', n)] + tail)
            assert got != 'accepted' and got.startswith('ProofError'), (name, W, m.rhs, xstar, prefix, n, tail)
            count[f'{kind}: refused'] += 1
        n = forge(rows, l, u, path, [0] * len(path)) if len(path) >= 2 else None
        if n is not None:
            got = outcome(m, prefix + [('L', n[:len(rows)] + list(reversed(n[len(rows):])))] + tail)
            assert got != 'accepted' and got.startswith('ProofError'), (W, m.rhs, xstar, prefix, n)
            count['swapped path entries: refused'] += 1
    assert count['right: refused'] == 0 and count['flip: refused'] > 20 and count['free: refused'] > 20, count
    assert count['swapped path entries: refused'] > 5 and count['right: no forgery'] > 200, count


def q_real_cut_proof_mutations():
    # Replicata: at 240@11, the cut proof D, L1, L2 of the leaf THIN[0] (3 LP solves), fed to certbb.verify as made;
    # with the path multiplier's sign flipped on either side, the two certificates swapped, c moved by -1 and by +1, u
    # negated alone, a stray element on D or on L1, L1's path entry dropped, u's entries shifted by one position, B
    # instead of D with the same certificates; with u negated, c -> -c - 1 and the sides swapped and negated (the same
    # cut seen from the other side); and the three tokens in every order and with tokens dropped, repeated or added.
    # Expectata: the proof as made is accepted with the pinned sha1; the equivalent proof is accepted (another sha1);
    # every other variant is refused with ProofError.  (The soundness verification's recheck.py and order.py.)
    at(240, 11)
    m, node = v5.moments(11), parse_key(THIN[0])
    verdict, _, stats, tokens = solved(11, node, 3)
    assert verdict == 'INFEASIBLE' and accepted(m, node, tokens) == PINNED['THIN0']
    D, L1, L2 = tokens
    u, c = D[1], D[2]
    neg = lambda L: ('L', L[1][:-1] + [-L[1][-1]])
    flipped = [('D', [-t for t in u], -c - 1), neg(L2), neg(L1)]
    assert accepted(m, node, flipped) != PINNED['THIN0']
    bad = {'flip sign <= side': [D, neg(L1), L2], 'flip sign >= side': [D, L1, neg(L2)], 'swap L tokens': [D, L2, L1],
           'c - 1': [('D', u, c - 1), L1, L2], 'c + 1': [('D', u, c + 1), L1, L2], 'u negated only': [('D', [-t for t in u], c), L1, L2],
           'stray element on D': [D + (0,), L1, L2], 'stray element on L': [D, L1 + (0,), L2], 'path entry dropped': [D, ('L', L1[1][:-1]), L2],
           'u shifted': [('D', u[1:] + u[:1], c), L1, L2], 'B instead of D': [('B', 0), L1, L2]}
    named = [('D', D), ('a', L1), ('b', L2)]
    for perm in itertools.permutations(named):
        if [t for _, t in perm] != tokens: bad[''.join(n for n, _ in perm)] = [t for _, t in perm]
    bad |= {'Da': [D, L1], 'Dabb': [D, L1, L2, L2], 'DDab': [D, D, L1, L2], 'Daab': [D, L1, L1, L2], 'ab': [L1, L2], 'D': [D],
            'DabD': [D, L1, L2, D], 'Dbb': [D, L2, L2], 'Daa': [D, L1, L1]}
    assert len(bad) == 25, len(bad)
    for name, proof in bad.items():
        expect_proof_error(lambda: accepted(m, node, proof))


# ---------- the search: cuts on journaled nodes ----------

def q_journaled_240_leaves_close_by_a_cut():
    # Replicata: at 240@11, the leaf HARD (INFEASIBLE in the journal at 1,929,339 LP solves), the three open leaves THIN
    # and the open depth-5 node DEPTH5, each through solve_node with its run budget; the proofs collected through
    # certbb.solve as well.
    # Expectata: every one INFEASIBLE with lps 3 (the root solve and the two sides), leaves 2, tokens D L L, the cut's u
    # of 240 integers; the width test's range solves are reported in stats['width'] and are 2 for the leaves (thin along
    # the first direction scanned) and at most 2 * 210 for the depth-5 node (210 directions there), cuts 1; verify
    # accepts the stream with solve_node's sha1; the sha1s are PINNED's (regression).
    at(240, 11)
    for name, key, budget in (('HARD', HARD, v5.BUDGET[-1]), ('THIN0', THIN[0], v5.BUDGET[-1]), ('THIN1', THIN[1], v5.BUDGET[-1]),
                              ('THIN2', THIN[2], v5.BUDGET[-1]), ('DEPTH5', DEPTH5, v5.BUDGET[5])):
        node = parse_key(key)
        verdict, a, found = v5.solve_node(11, node, budget)
        assert (verdict, a, found['lps'], found['leaves']) == ('INFEASIBLE', None, 3, 2), (name, verdict, found)
        verdict2, x, stats, tokens = solved(11, node, budget)
        assert verdict2 == 'INFEASIBLE' and [t[0] for t in tokens] == ['D', 'L', 'L'], (name, [t[0] for t in tokens])
        assert len(tokens[0][1]) == 240 and all(type(t) is int for t in tokens[0][1]) and type(tokens[0][2]) is int
        assert stats['lp'] == 3 and stats['leaves'] == 2 and stats['cuts'] == 1 and stats['cut_fail'] == 0, (name, stats)
        assert stats['width'] == (2 if name != 'DEPTH5' else stats['width']) and stats['width'] <= 2 * 210, (name, stats)
        assert certbb.verify(v5.moments(11), node, tokens) == found['proof'] == sha1_of(tokens)
        assert PINNED[name] == found['proof'], (name, found['proof'])


def q_silence_on_nodes_without_a_thin_direction():
    # Replicata: at 304@9, the leaf La through certbb.solve, new and old; at 240@11, the two open leaves NOTTHIN at
    # budget 100, new and old.
    # Expectata: La is INFEASIBLE in exactly 10009 LP solves with the journal's proof sha1 f6cc9a4a... and the old
    # certbb's token stream, token for token; the width test scanned every direction (width 2 * 270 plus 2 per thin
    # claim that did not certify, width_other 0, cuts 0), and made CLAIMS['LA'] = 3 such claims (regression: ranges
    # that touch an integer in exact arithmetic and fall short of it in floating point); the NOTTHIN leaves are UNKNOWN
    # at 100 with no D token and the old certbb's tokens exactly, width exactly 2 * 182, cut_fail 0, width_other 0,
    # cuts 0 (the mutation pass's S08: a direction skipped as a failed range solve would pass a looser count).
    old = old_certbb()
    at(304, 9)
    node = parse_key(LA)
    verdict, _, stats, tokens = solved(9, node)
    old_tokens = []
    assert old.solve(v5.moments(9), node, BIG, old_tokens.append)[0] == 'INFEASIBLE'
    assert verdict == 'INFEASIBLE' and stats['lp'] == 10009 and sha1_of(tokens).startswith(LA_SHA1), (verdict, stats)
    assert tokens == old_tokens and (stats['width'], stats['cut_fail'], stats['width_other'], stats['cuts']) == (2 * 270 + 2 * CLAIMS['LA'], CLAIMS['LA'], 0, 0), stats
    at(240, 11)
    for key in NOTTHIN:
        node = parse_key(key)
        verdict, _, stats, tokens = solved(11, node, 100)
        old_tokens = []
        assert old.solve(v5.moments(11), node, 100, old_tokens.append)[0] == 'UNKNOWN'
        assert verdict == 'UNKNOWN' and stats['lp'] == 100 and tokens == old_tokens and not any(t[0] == 'D' for t in tokens)
        assert (stats['width'], stats['cut_fail'], stats['width_other'], stats['cuts']) == (2 * 182, 0, 0, 0), stats


def q_false_thin_claims_fall_back_unchanged():
    # Replicata: at 304@9, the journaled INFEASIBLE leaf FALSE_THIN through certbb.solve at the run's bottom budget, new
    # and old.
    # Expectata: INFEASIBLE in 11 LP solves with 6 leaves, the journal's proof sha1 and the old certbb's tokens exactly;
    # cuts 0, and CLAIMS['FALSE_THIN'] = 23 thin claims (regression: the re-check found their exact ranges touching an
    # integer, mostly a single value of u.x from the node's fixed positions; one side of each is Optimal, so nothing
    # closes), each costing its two side solves: width 2 * 270 + 2 * 23, width_other 0.
    old = old_certbb()
    at(304, 9)
    node = parse_key(FALSE_THIN)
    verdict, _, stats, tokens = solved(9, node, v5.BUDGET[-1])
    old_tokens = []
    assert old.solve(v5.moments(9), node, v5.BUDGET[-1], old_tokens.append)[0] == 'INFEASIBLE'
    assert verdict == 'INFEASIBLE' and stats['lp'] == 11 and stats['leaves'] == 6 and sha1_of(tokens) == FALSE_THIN_SHA1, (verdict, stats, sha1_of(tokens))
    assert tokens == old_tokens and not any(t[0] == 'D' for t in tokens)
    assert (stats['width'], stats['cut_fail'], stats['width_other'], stats['cuts']) == (2 * 270 + 2 * CLAIMS['FALSE_THIN'], CLAIMS['FALSE_THIN'], 0, 0), stats


def q_regression_against_old_certbb():
    # Replicata: through the old and the new certbb.solve: at 240@11, C2, and journaled INFEASIBLE bottom leaves of
    # the 240@11 run with 1000 <= lps <= 20000 in a seeded order (from the snapshot scratch/width/journal_240_snapshot.jsonl,
    # read only), each at its journal's lps, until 3 of them cut nothing (at most 16 leaves); at 40@6, every node of the
    # first two levels of the real split (the pools among them solved, not split).
    # Expectata: where the new search cuts nothing (cuts 0; C2, asserted, those 3 leaves, and the 40@6 nodes but
    # 4:[3,7,7,3], which a cut closes), the verdicts, points, token streams and stats (lp, leaves, splits, cert_fail,
    # lp_other, max_depth, explored, choices) are identical: the search is the old one.  Where it cuts (cuts 1),
    # INFEASIBLE in 3 LP solves with a proof verify accepts, against the old search's journaled thousands.
    old = old_certbb()
    snapshot = os.path.join(SCRATCH, 'journal_240_snapshot.jsonl')
    last = {}
    for line in itertools.islice(open(snapshot), 1, None):
        r = json.loads(line)
        last[r['key']] = r
    leaves = sorted(k for k, r in last.items() if r['verdict'] == 'INFEASIBLE' and k.count(' ') == 7 and '#' not in k
                    and 1000 <= r['lps'] <= 20000)
    keys = random.Random(11).sample(leaves, 16)
    at(240, 11)
    same = ('lp', 'leaves', 'splits', 'cert_fail', 'lp_other', 'max_depth', 'explored', 'choices')
    quiet = 0

    def compare(order, node, budget, must_be_quiet):
        nonlocal quiet
        new_tokens = []
        new = certbb.solve(v5.moments(order), node, budget, new_tokens.append)
        assert new[2]['cuts'] == 0 or not must_be_quiet, (v5.node_key(node), new[2])
        if new[2]['cuts'] == 0:
            old_tokens = []
            got = old.solve(v5.moments(order), node, budget, old_tokens.append)
            assert new[:2] == got[:2] and new_tokens == old_tokens, (v5.node_key(node), new[:2], got[:2])
            assert {k: new[2][k] for k in same} == {k: got[2][k] for k in same}, (new[2], got[2])
            quiet += 1
        else:
            assert new[0] == 'INFEASIBLE' and new[2]['lp'] == 3 and [t[0] for t in new_tokens] == ['D', 'L', 'L'], new[2]
            certbb.verify(v5.moments(order), node, new_tokens)
        return new[0]

    assert compare(11, C2, BIG, True) == 'INFEASIBLE'
    quiet = 0
    for key in keys:
        assert compare(11, parse_key(key), last[key]['lps'], False) == 'INFEASIBLE', key
        if quiet == 3: break
    assert quiet == 3, quiet
    v5.configure(40, 6)
    top = v5.split(6, ())
    for node in top + [c for n in top if all(len(V) == 1 for _, V in n) for c in v5.split(6, n)]:
        compare(6, node, BIG, False)
    v5.configure(240, 11)


def q_budget_room_for_the_cut():
    # Replicata: at 240@11, the leaf HARD at budgets 1, 2, 3 and 4.
    # Expectata: the width test needs room for its two side solves in the budget (lps counts them, and lps never exceeds
    # the budget): at 1 and 2, UNKNOWN with lps equal to the budget, no D token and no width solve; at 3 and 4, INFEASIBLE
    # with lps 3.
    at(240, 11)
    node = parse_key(HARD)
    for budget in (1, 2):
        verdict, _, stats, tokens = solved(11, node, budget)
        assert verdict == 'UNKNOWN' and stats['lp'] == budget and stats['width'] == 0 and not any(t[0] == 'D' for t in tokens), (budget, stats)
    for budget in (3, 4):
        verdict, _, stats, tokens = solved(11, node, budget)
        assert verdict == 'INFEASIBLE' and stats['lp'] == 3 and [t[0] for t in tokens] == ['D', 'L', 'L'], (budget, stats)


def q_sides_that_do_not_close_fall_back():
    # Replicata: at 240@11, the leaf HARD with certbb.Lp.side replaced by one whose solve stops at its iteration limit
    # (no ray), at budget 100; and with one that answers Optimal with the root point.
    # Expectata: UNKNOWN at 100 with the old certbb's tokens exactly (no D token): a thin direction whose sides do not
    # certify closes nothing; lps counts the budget's solves only, the width stat counts the ranges and the failed sides
    # (2 * 182 + 2 * cut_fail), cut_fail is the number of thin directions found (at least 1), cuts 0.
    at(240, 11)
    node = parse_key(HARD)
    old_tokens = []
    assert old_certbb().solve(v5.moments(11), node, 100, old_tokens.append)[0] == 'UNKNOWN'
    for fake in (lambda self, lo_w, hi_w, lo, hi: ('Iteration limit reached', None),
                 lambda self, lo_w, hi_w, lo, hi: ('Optimal', np.full(240, 0.5))):
        with patched(certbb.Lp, side=fake):
            verdict, _, stats, tokens = solved(11, node, 100)
        assert verdict == 'UNKNOWN' and stats['lp'] == 100 and tokens == old_tokens, stats
        assert stats['cuts'] == 0 and stats['cut_fail'] >= 1 and stats['width'] == 2 * 182 + 2 * stats['cut_fail'], stats


def q_a_wrong_ray_falls_back():
    # Replicata: at 240@11, the leaf HARD at budget 100 with certbb.Lp.side replaced by one that answers Infeasible with
    # a wrong ray for every side: all ones, and the true ray negated.
    # Expectata: as q_sides_that_do_not_close_fall_back: UNKNOWN at 100 with the old certbb's tokens exactly (no D),
    # cut_fail >= 1, cuts 0: a certificate that fails the exact check (the bound, or the sign on the cut row) is never
    # emitted (the mutation pass's S01: without the check, D L L with a bogus certificate in 3 LP solves).
    at(240, 11)
    node = parse_key(HARD)
    old_tokens = []
    assert old_certbb().solve(v5.moments(11), node, 100, old_tokens.append)[0] == 'UNKNOWN'
    real = certbb.Lp.side
    for fake in (lambda self, lo_w, hi_w, lo, hi: ('Infeasible', np.ones(len(self.b) + 1)),
                 lambda self, lo_w, hi_w, lo, hi: (lambda st, y: (st, -y if y is not None else y))(*real(self, lo_w, hi_w, lo, hi))):
        with patched(certbb.Lp, side=fake):
            verdict, _, stats, tokens = solved(11, node, 100)
        assert verdict == 'UNKNOWN' and stats['lp'] == 100 and tokens == old_tokens, stats
        assert stats['cuts'] == 0 and stats['cut_fail'] >= 1, stats


def q_a_cut_that_does_not_cut_the_box_falls_back():
    # Replicata: at 240@11, the leaf HARD; d the first direction scanned at its prefix; the box with every position of
    # d's support pinned to the sign of its entry (so that u.x is a constant K there) and 13 positions of class 0 mod 9
    # outside the support's negative part pinned to 1 (its count row mod 9 says 12, so the rows have no point in the
    # box: the root LP is Infeasible); solve_node and certbb.solve on it at budget 20, with certbb.Lp.solve replaced by
    # one that reports the search's root solve Optimal with the middle of the box (a HiGHS misreporting an infeasible
    # root; every other solve is the real one), certbb.Lp.extremes by one that claims for d a range of u.x strictly
    # inside (kfloor, kfloor + 1) when K >= kfloor and inside (kfloor - 1, kfloor) when K < kfloor, and None (a failed
    # range solve) for every other direction, and certbb.cuts by a spy on the real one.
    # Expectata: the cut the claim leads to, ('D', u, C) with C = kfloor or kfloor - 1, does not cut the box (K is C or
    # on one side of it), while both sides' LPs are Infeasible and their rays certify: the spy sees one call, answered
    # False, so the width test refused the cut by Check's own condition after both certificates had passed (cut_fail 1,
    # cuts 0, width_other 181, width 2 * 182 + 2); no D token and no ProofError, and the search goes on to close the box
    # by branch and bound: INFEASIBLE in 3 LP solves with tokens B L L that verify, with the Check fed live in
    # solve_node.  Before the condition was part of the test, the D token raised ProofError "a cut does not cut the
    # box" in Check.feed, which would have stopped a run.
    at(240, 11)
    m, node = v5.moments(11), parse_key(HARD)
    rows = certbb.node_rows(m, choice_of(node))
    moduli = tuple(M for M, _ in node)
    A, keep = kept_rows(m, moduli)
    d = width.directions(11, moduli, A)[0]
    kfloor, kfrac = width.offset(d, [rows[i][1] for i in keep])
    lo, hi = [0] * 240, [1] * 240
    for p, t in enumerate(d.u):
        if t: lo[p] = hi[p] = int(t > 0)
    ones = [p for p in range(0, 240, 9) if d.u[p] >= 0][:13]
    assert len(ones) == 13, len(ones)
    for p in ones: lo[p] = hi[p] = 1
    K = sum(t * l for t, l in zip(d.u, lo))
    claim = (0.3, 0.6) if K >= kfloor else (-0.7, -0.4)
    real_solve, real_cuts, lies, seen = certbb.Lp.solve, certbb.cuts, [], []

    def lying_solve(self, l, u, basis=None):
        status, z = real_solve(self, l, u, basis)
        if self.w is None and not lies:                               # the search's root solve
            lies.append(status)
            return 'Optimal', (np.array(l, float) + np.array(u, float)) / 2
        return status, z

    def claimed_extremes(self, l, u):
        return (claim[0] - kfrac, claim[1] - kfrac) if self.w is d.w else None

    def spy(u, c, l, h):
        seen.append(real_cuts(u, c, l, h))
        return seen[-1]

    with patched(certbb.Lp, solve=lying_solve, extremes=claimed_extremes), patched(certbb, cuts=spy):
        verdict, a, found = v5.solve_node(11, node, 20, lo, hi)
        assert lies == ['Infeasible'] and seen == [False], (lies, seen)
        assert (verdict, a, found['lps'], found['leaves']) == ('INFEASIBLE', None, 3, 2), (verdict, found)
        lies.clear()
        seen.clear()
        verdict, x, stats, tokens = solved(11, node, 20, lo=lo, hi=hi)
    assert lies == ['Infeasible'] and seen == [False] and verdict == 'INFEASIBLE', (lies, seen, verdict, stats)
    assert [t[0] for t in tokens] == ['B', 'L', 'L'], [t[0] for t in tokens]
    assert (stats['lp'], stats['cuts'], stats['cut_fail'], stats['width'], stats['width_other']) == (3, 0, 1, 2 * 182 + 2, 181), stats
    assert certbb.verify(m, node, tokens, lo, hi) == found['proof']


def q_emitted_cut_does_not_alias_the_direction():
    # Replicata: at 240@11, the leaf THIN[1] through certbb.solve at budget 3; the first entry of the emitted cut's u
    # changed in place; THIN[1] solved again; and the directions of its prefix.
    # Expectata: the second solve gives the pinned proof again (INFEASIBLE, PINNED['THIN1']): the token holds a list of
    # its own, not the cached direction's u, which is a tuple (the soundness verification's aliasing finding: a token's
    # u changed in place made the next solve of this leaf UNKNOWN with cut_fail 1 and no error).
    at(240, 11)
    node = parse_key(THIN[1])
    verdict, _, stats, tokens = solved(11, node, 3)
    assert verdict == 'INFEASIBLE' and sha1_of(tokens) == PINNED['THIN1'], (verdict, stats)
    tokens[0][1][0] += 1
    try:
        verdict, _, stats, again = solved(11, node, 3)
    finally:
        tokens[0][1][0] -= 1                                           # so that a code that aliases does not poison the later quals
    assert verdict == 'INFEASIBLE' and sha1_of(again) == PINNED['THIN1'], (verdict, stats, sha1_of(again))
    A, _ = kept_rows(v5.moments(11), CASCADE_240)
    assert all(type(d.u) is tuple for d in width.directions(11, CASCADE_240, A))


def q_no_width_test_without_an_optimal_root():
    # Replicata: at 240@11, the leaf HARD with every LP solve stopping at its iteration limit (quals_v5's GiveUp), 5 LP
    # solves at most.
    # Expectata: UNKNOWN, lp_other 5, width 0: the test runs only at a root whose LP is Optimal (the mutation pass's
    # S13: the test at every root would spend 364 range solves here).
    at(240, 11)
    with patched(certbb, Lp=GiveUp):
        verdict, _, stats, tokens = solved(11, parse_key(HARD), 5)
    assert verdict == 'UNKNOWN' and stats['lp_other'] == 5 and stats['width'] == 0 and not any(t[0] == 'D' for t in tokens), stats


def q_each_choice_of_a_pool_gets_its_own_test():
    # Replicata: at 240@11, the pool node whose last constraint offers THIN[0]'s and HARD's mod-9 vectors (the same
    # prefix), at budget 10.
    # Expectata: INFEASIBLE, lp 6, tokens D L L D L L, cuts 2, and verify accepts the stream: each choice closes by its
    # own cut (the mutation pass's S16: a Guide keeping the first choice's counts leaves the second UNKNOWN).
    at(240, 11)
    thin, hard = parse_key(THIN[0]), parse_key(HARD)
    assert thin[:-1] == hard[:-1]
    node = thin[:-1] + ((9, (thin[-1][1][0], hard[-1][1][0])),)
    verdict, _, stats, tokens = solved(11, node, 10)
    assert verdict == 'INFEASIBLE' and stats['lp'] == 6 and stats['cuts'] == 2 and stats['choices'] == 2, stats
    assert [t[0] for t in tokens] == ['D', 'L', 'L'] * 2
    certbb.verify(v5.moments(11), node, tokens)


def q_witnesses_kept():
    # Replicata: at 240@11, order 10, the node of the published order-10 example under the cascade, on the full box
    # at budget 400, pinned to the example, and on three seeded boxes pinned to it at half of the positions at budget
    # 50; at 304@9, order 8, the node of the order-8 example (3, 5, 4, 7, 8, 9), likewise.
    # Expectata: on the full box, never INFEASIBLE (the example is in the node), no D token, every direction scanned
    # with no cut (width 2 * dim plus 2 per thin claim that did not certify, width_other 0, cuts 0: a node with a
    # solution has an integer in every range); the 240 node makes no thin claim and the 304 node CLAIMS['W304'] = 7
    # (regression: ranges touching an integer, the soundness verification's finding); pinned, FEASIBLE with the example,
    # as overnight_v5.control asks; on the half-pinned boxes, where the width test runs (an Optimal root at budget 50),
    # never INFEASIBLE, no D token, every direction scanned, cuts 0, and a FEASIBLE point is a sequence of the order
    # with the node's counts inside the box.
    for n, order, dim, claims in ((240, 10, 183, 0), (304, 8, 271, CLAIMS['W304'])):       # dim = N - deg K at that order
        at(n, order + 1)
        a = v5.from_hex(v5.EXAMPLES[n, order], order)
        node = tuple((M, (v5.counts(a, M),)) for M in v5.CASCADE)
        verdict, x, stats, tokens = solved(order, node, 400)
        assert verdict != 'INFEASIBLE' and not any(t[0] == 'D' for t in tokens), (n, verdict, stats)
        assert (stats['width'], stats['cut_fail'], stats['width_other'], stats['cuts']) == (2 * dim + 2 * claims, claims, 0, 0), (n, stats)
        pin = x01(a)
        verdict, x, stats, tokens = solved(order, node, 1, lo=pin, hi=pin)
        assert verdict == 'FEASIBLE' and x == pin and stats['lp'] == 1 and stats['width'] == 0, (n, verdict, stats)
        rnd = random.Random(order)
        for _ in range(3):
            free = set(rnd.sample(range(n), n // 2))
            lo = [0 if p in free else pin[p] for p in range(n)]
            hi = [1 if p in free else pin[p] for p in range(n)]
            verdict, x, stats, tokens = solved(order, node, 50, lo=lo, hi=hi)
            assert verdict != 'INFEASIBLE' and not any(t[0] == 'D' for t in tokens), (n, verdict, stats)
            assert stats['width'] == 2 * dim + 2 * stats['cut_fail'] and stats['width_other'] == 0 and stats['cuts'] == 0, (n, stats)
            assert verdict == 'UNKNOWN' or (all(lo[p] <= x[p] <= hi[p] for p in range(n)) and v5.exact_order([2 * t - 1 for t in x]) >= order
                                            and all(v5.counts([2 * t - 1 for t in x], M) == V[0] for M, V in node)), (n, verdict)


def q_brute_force_small_configurations():
    # Replicata: N = 16, 20 and 24 at orders 3 and 4 (SETTINGS patched), every admissible count vector mod 3, and for
    # N = 24 every admissible mod-4 vector under each of them, as nodes through certbb.solve at budget 300; the truth
    # from quals_v5.power_sum_solutions (meet in the middle, exact).
    # Expectata: no wrong verdict: INFEASIBLE only where no solution has the node's counts, FEASIBLE only with a point
    # that is a solution with those counts; and the cut was exercised: some node closed by a cut (cuts > 0) and every
    # cut proof verifies.
    old = v5.SETTINGS
    cuts = nodes = 0
    for n in (16, 20, 24):
        for order in (3, 4):
            with patched(v5, SETTINGS=old | {(n, order): ((3, 4), (300, 300, 300))}):
                v5.configure(n, order)
                sols = power_sum_solutions(n, order)
                for v3 in v5.admissible(order, 3, ()):
                    cases = [((3, (v3,)),)]
                    if n == 24:
                        cases += [((3, (v3,)), (4, (v4,))) for v4 in v5.admissible(order, 4, ())]
                    for node in cases:
                        nodes += 1
                        verdict, x, stats, tokens = solved(order, node, 300)
                        if verdict == 'INFEASIBLE':
                            assert not any(all(v5.counts(a, M) == V[0] for M, V in node) for a in sols), v5.node_key(node)
                            certbb.verify(v5.moments(order), node, tokens)
                        if verdict == 'FEASIBLE':
                            a = [2 * t - 1 for t in x]
                            assert v5.exact_order(a) >= order and all(v5.counts(a, M) == V[0] for M, V in node), v5.node_key(node)
                        cuts += stats['cuts']
    v5.configure(240, 11)
    assert cuts > 0 and nodes > 20, (cuts, nodes)


# ---------- width.py: the directions ----------

def q_directions_exact_per_cascade_prefix():
    # Replicata: for each prefix of the cascades of 240@11 and 304@9, the empty one included, width.directions on the
    # LP's exact rows (as certbb's Guide builds them); and for each direction, with the first open leaf's counts of the
    # run as b, its offset.
    # Expectata: the kernel basis Q has N - deg K vectors, every row of A kills every one of them exactly; the reduced
    # basis R has as many, every vector a multiple of K (exact division); every direction's u has R u = e_j; the
    # directions come in the order j = dim - 1 down to 0; den u - A^T num is killed by every row of A exactly (A' w = 0
    # with w = u - A^T num / den), den > 0 and gcd(num, den) = 1; the offset is (floor, frac) of num . b / den; and the
    # directions are DIGESTS' (regression: the mutation pass's W01, LLL at delta 0.75, changes every prefix's).
    for n, order, cascade, key in ((240, 11, CASCADE_240, HARD), (304, 9, CASCADE_304, LA)):
        at(n, order)
        m = v5.moments(order)
        leaf = parse_key(key)
        for depth in range(len(cascade) + 1):
            moduli = cascade[:depth]
            A, keep = kept_rows(m, moduli)
            Q, K = width.kernel_basis(order, moduli, n)
            deg, dim = len(K) - 1, n - len(K) + 1
            assert K[-1] == 1 and len(Q) == dim and len(A) == deg, (moduli, len(A), deg)
            assert all(sum(a * int(q) for a, q in zip(row, Qj)) == 0 for row in A for Qj in Q), moduli
            dirs = width.directions(order, moduli, A)
            assert [d.j for d in dirs] == list(range(dim - 1, -1, -1)), moduli
            assert hashlib.sha1(repr([list(d.u) for d in dirs]).encode()).hexdigest() == DIGESTS[n, moduli], moduli
            R = width.lll(Q)[0]
            for j in (0, dim // 2, dim - 1):
                poly, rem = list(int(t) for t in R[j]), []
                for i in range(dim - 1, -1, -1):             # exact division by the monic K, highest degree first
                    q = poly[i + deg]
                    for t, c in enumerate(K): poly[i + t] -= q * c
                assert not any(poly), (moduli, j)
            rows = certbb.node_rows(m, [(M, V[0]) for M, V in leaf[:depth]])
            b = [rows[i][1] for i in keep]
            for d in dirs:
                assert type(d.u) is tuple and len(d.u) == n and all(type(t) is int for t in d.u) and type(d.den) is int and d.den > 0
                assert math.gcd(d.den, *d.num) == 1 and len(d.num) == deg
                assert all(sum(int(r) * t for r, t in zip(R[i], d.u)) == int(i == d.j) for i in range(dim)), (moduli, d.j)
                W = [d.den * t for t in d.u]
                for row, z in zip(A, d.num, strict=True):
                    for p, c in enumerate(row): W[p] -= z * c
                assert all(sum(c * w for c, w in zip(row, W)) == 0 for row in A), (moduli, d.j)
                assert np.allclose(d.w, np.array([t / d.den for t in W])) and d.w.dtype == float
                kfloor, kfrac = width.offset(d, b)
                num = sum(z * t for z, t in zip(d.num, b))
                assert type(kfloor) is int and kfloor == num // d.den and kfrac == (num - kfloor * d.den) / d.den and 0 <= kfrac < 1


def q_directions_cached_per_prefix():
    # Replicata: width.directions twice on the same (order, moduli, A), then on A with one coefficient changed.
    # Expectata: the same tuple object the second time (cached in this process), a fresh one for the other rows; the
    # module refuses rows that are not the moment-and-count rows its kernel polynomial describes (AssertionError).
    at(240, 11)
    A, _ = kept_rows(v5.moments(11), (3, 5))
    d1, d2 = width.directions(11, (3, 5), A), width.directions(11, (3, 5), A)
    assert d1 is d2 and len(d1) == 240 - (11 + 2 + 4)
    other = (A[0][:5] + (A[0][5] + 1,) + A[0][6:],) + A[1:]
    expect_assertion(lambda: width.directions(11, (3, 5), other), 'directions')
    expect_assertion(lambda: width.directions(11, (3, 5, 7), A), 'directions')


def q_lll_overflow_guards():
    # Replicata: width.lll on the kernel basis of 240@11's bottom prefix, and on the basis ((2^61, 1), (3 * 2^60, 1)),
    # whose first size reduction (q = 2 against a row of size 2^61) is bounded beyond 2^62.
    # Expectata: the first reduces (Q = T^-1 R for the tracked T^-1 exactly, entries small) and the second trips the
    # guard that keeps the int64 arithmetic exact (AssertionError in lll).
    Q, K = width.kernel_basis(11, CASCADE_240, 240)
    R, Tinv, gs = width.lll(Q)
    dim = len(Q)
    assert R.shape == Q.shape and len(Tinv) == dim and int(np.abs(R).max()) < 2 ** 30
    Rl = [[int(t) for t in row] for row in R]
    for j in (0, dim - 1):                    # Q = T^-1 R, Tinv[i] being column i of T^-1
        assert [sum(Tinv[i][j] * Rl[i][p] for i in range(dim)) for p in range(240)] == [int(t) for t in Q[j]], j
    big = np.array([[2 ** 61, 1], [3 * 2 ** 60, 1]], dtype=np.int64)
    expect_assertion(lambda: width.lll(big), 'lll')


def q_bareiss_exact():
    # Replicata: width.bareiss on 20 seeded random nonsingular 6 x 6 integer matrices G (entries in -9..9) with 6 x 3
    # right-hand sides C, and on the singular G = ((1, 2), (2, 4)).
    # Expectata: G Z = den C exactly and |den| = |det G| (sympy) every time; the singular G is refused with an
    # AssertionError in bareiss (not a StopIteration from its pivot search), as its exact divisions are asserted.
    rnd = random.Random(3)
    for _ in range(20):
        G = [[rnd.randint(-9, 9) for _ in range(6)] for _ in range(6)]
        while sp.Matrix(G).det() == 0: G = [[rnd.randint(-9, 9) for _ in range(6)] for _ in range(6)]
        C = [[rnd.randint(-9, 9) for _ in range(3)] for _ in range(6)]
        den, Z = width.bareiss(G, C)
        assert abs(den) == abs(sp.Matrix(G).det()) and type(den) is int
        assert all(sum(G[i][j] * Z[j][t] for j in range(6)) == den * C[i][t] for i in range(6) for t in range(3))
    expect_assertion(lambda: width.bareiss([[1, 2], [2, 4]], [[1], [1]]), 'bareiss')


def q_ray_sign():
    # Replicata: at 304@9, La's root LP on certbb's Guide; its first direction's range; the direction row forced below
    # the range (bounds (-inf, lo - 1)) and above it ((hi + 1, inf)), each solve's ray converted by Guide.certificate
    # with the sense of the bound it breaks.
    # Expectata: both solves are Infeasible with a ray; the converted certificates have a cut-row multiplier of the
    # sense's sign (<= 0 for the upper bound, >= 0 for the lower) and pass lower_bound (the measured HiGHS convention:
    # the ray's component on a ranged row is positive when its lower bound is used, negative for its upper bound).
    at(304, 9)
    m, node = v5.moments(9), parse_key(LA)
    rows = certbb.node_rows(m, choice_of(node))
    lp = certbb.Lp(m, [M for M, _ in node])
    lp.set_counts(choice_of(node))
    guide = certbb.Guide(m, lp)
    guide.lp.set_counts(choice_of(node))
    lo, hi = [0] * 304, [1] * 304
    d = guide.dirs[0]
    guide.lp.direction(d.w)
    lo_w, hi_w = guide.lp.extremes(lo, hi)
    assert lo_w <= hi_w, (lo_w, hi_w)
    b = [rows[i][1] for i in guide.keep]
    kfloor, kfrac = width.offset(d, b)
    sparse = [(p, t) for p, t in enumerate(d.u) if t]
    for sign, bounds, beta in ((-1, (-certbb.INF, lo_w - 1), kfloor + math.floor(lo_w - 1 + kfrac)),
                               (1, (hi_w + 1, certbb.INF), kfloor + math.ceil(hi_w + 1 + kfrac))):
        status, y = guide.lp.side(*bounds, lo, hi)
        assert status == 'Infeasible' and y is not None and len(y) == len(lp.b) + 1
        n = guide.certificate(y, d)
        assert sign * n[-1] > 0 and all(type(t) is int for t in n) and len(n) == len(rows) + 1
        assert certbb.lower_bound(rows + [(sparse, beta)], lo, hi, n) > 0, sign


# ---------- the journal, CODE and the migration ----------

def q_old_header_asserts():
    # Replicata: a journal under scratch/width/quals holding the 240@11 journal's header line with the code field of
    # the CODE before this work (OLD_HEADER) and one record, and with the code of the first width-test revision
    # (FIRST_WIDTH_CODE, the live journal's header since its restart); v5.Journal on each at 240@11; then the same with
    # the current header.
    # Expectata: both old headers are refused ("belongs to another configuration", AssertionError in __init__); the
    # current one is admitted; the headers differ only in code, and v5.CODE is neither old code.
    at(240, 11)
    assert v5.header() | {'code': OLD_HEADER['code']} == OLD_HEADER and v5.CODE not in (OLD_HEADER['code'], FIRST_WIDTH_CODE)
    rec = {'key': '', 'verdict': 'UNKNOWN', 'budget': 10000, 'lps': 10000, 'leaves': 4957, 'proof': 'ac075bf8d3f93ea7ea39fc276b2ed529dc8a434f'}
    path = os.path.join(QUALS, 'old_header_journal.jsonl')
    for code in (OLD_HEADER['code'], FIRST_WIDTH_CODE):
        open(path, 'w').write(json.dumps(v5.header() | {'code': code}) + '\n' + json.dumps(rec) + '\n')
        expect_assertion(lambda: v5.Journal(path), '__init__')
    open(path, 'w').write(json.dumps(v5.header()) + '\n' + json.dumps(rec) + '\n')
    assert v5.Journal(path).records == {'': rec}


def q_code_and_source_cover_width():
    # Replicata: fresh processes importing overnight_v5 from copies of overnight_v5.py, certbb.py and width.py in a
    # scratch directory, unchanged, then with one comment line added to the copy of width.py.
    # Expectata: unchanged, CODE and SOURCE equal this process's; with the comment, CODE and SOURCE's width.py entry
    # differ while the other entries are the same: width.py decides which nodes close, so it is fingerprinted into
    # CODE, and a worker running another width.py is refused by work().
    d = tempfile.mkdtemp(dir=QUALS)
    for f in ('overnight_v5.py', 'certbb.py', 'width.py'):
        open(os.path.join(d, f), 'w').write(open(os.path.join(HERE, f)).read())
    probe = (f"import sys, json; sys.dont_write_bytecode = True; sys.path.insert(0, {d!r})\n"
             f"import overnight_v5 as v5\n"
             f"assert v5.__file__.startswith({d!r}) and v5.certbb.__file__.startswith({d!r}) and v5.certbb.width.__file__.startswith({d!r})\n"
             f"print(json.dumps([v5.CODE, list(v5.SOURCE)]))\n")
    def ask():
        p = run_child(probe)
        assert p.returncode == 0, p.stderr[-2000:]
        code, source = json.loads(p.stdout)
        return code, tuple(source)
    assert ask() == (v5.CODE, v5.SOURCE) and len(v5.SOURCE) == 3
    open(os.path.join(d, 'width.py'), 'a').write('# one more line\n')
    code, source = ask()
    assert code != v5.CODE and source[:2] == v5.SOURCE[:2] and source[2] != v5.SOURCE[2]
    assert hashlib.sha1(open(os.path.join(HERE, 'width.py'), 'rb').read()).hexdigest() == v5.SOURCE[2]


def q_migration_script():
    # Replicata: under scratch/width/quals/migrate: a 240@11 journal with the header of the first width-test revision
    # (FIRST_WIDTH_CODE) and records: the top node UNKNOWN, HARD INFEASIBLE (lps 3), THIN[0] UNKNOWN at 2000000 (a leaf
    # the width test closes), NOTTHIN[0] UNKNOWN at 10000 and again at 2000000 (a leaf it does not close), HARD's parent
    # CLOSED; a 304@9 journal made of the real journal's first 300 lines (the old header; its top nodes' last records
    # are UNKNOWN) and the boxsplit journal's first 50 (read only), as written: boxsplit's CODE the one its header
    # names; migrate_journals.migrate on each with the process
    # scan patched to find nothing and KEPT patched to the quals' directory (so that the real copies' places stay
    # free); then migrate on a journal whose run the patched scan reports alive, on one while the page watcher is
    # reported alive, on the migrated 240 journal again, and on a journal with an unknown name.
    # Expectata: 240's: the header's code field is v5.CODE and nothing else changed; THIN[0]'s record is gone (the
    # probe at budget 3 closes it); every other record is there in its order, NOTTHIN[0]'s two UNKNOWN records included
    # (the probe leaves it UNKNOWN, so the resumed run reuses them instead of spending 2000000 LP solves again); a copy
    # of the journal as it was is at KEPT/<name>.code_4cb6199c.jsonl; the migrated journal opens through v5.Journal
    # with the records expected; the printed line says 1 node dropped.  304's and the boxsplit's: the header's code
    # field only, every record kept, the 304 journal's UNKNOWN ones too (the runs are finished: no probe).  AssertionError in migrate,
    # with nothing written, for the live run, the watcher, the journal already at v5.CODE, and the unknown name.
    at(240, 11)
    base = os.path.join(QUALS, 'migrate')
    shutil.rmtree(base, ignore_errors=True)
    kept_dir = os.path.join(base, 'kept')
    parent = HARD.rsplit(' ', 1)[0]
    records = [{'key': '', 'verdict': 'UNKNOWN', 'budget': 10000, 'lps': 10000, 'leaves': 4957, 'proof': 'ac075bf8d3f93ea7ea39fc276b2ed529dc8a434f'},
               {'key': HARD, 'verdict': 'INFEASIBLE', 'budget': 2000000, 'lps': 3, 'leaves': 2, 'proof': PINNED['HARD']},
               {'key': THIN[0], 'verdict': 'UNKNOWN', 'budget': 2000000, 'lps': 2000000, 'leaves': 991001, 'proof': '0' * 40},
               {'key': NOTTHIN[0], 'verdict': 'UNKNOWN', 'budget': 10000, 'lps': 10000, 'leaves': 4961, 'proof': '1' * 40},
               {'key': NOTTHIN[0], 'verdict': 'UNKNOWN', 'budget': 2000000, 'lps': 2000000, 'leaves': 990111, 'proof': '2' * 40},
               {'key': parent, 'verdict': 'CLOSED', 'budget': 10000}]
    texts = {'overnight_v5_240_11_journal.jsonl': json.dumps(v5.header() | {'code': FIRST_WIDTH_CODE}) + '\n' + ''.join(json.dumps(r) + '\n' for r in records)}
    for name, k in (('overnight_v5_304_9_journal.jsonl', 300), ('overnight_v5_304_9_boxsplit_journal.jsonl', 50)):
        with open(os.path.join(HERE, name)) as fh:
            texts[name] = ''.join(itertools.islice(fh, k))
    paths = {}
    for name, text in texts.items():
        d = os.path.join(base, name.replace('.jsonl', ''))
        os.makedirs(d)
        paths[name] = os.path.join(d, name)
        open(paths[name], 'w').write(text)
    written = json.loads(texts['overnight_v5_304_9_boxsplit_journal.jsonl'].splitlines()[0])['boxsplit']
    with patched(mj, alive=lambda pattern: [], KEPT=kept_dir), patched(mj.bx, CODE=written):
        for name, text in texts.items():
            old = text.splitlines()
            copy = mj.migrate(paths[name])
            assert copy == os.path.join(kept_dir, name.replace('.jsonl', f'.code_{json.loads(old[0])["code"][:8]}.jsonl')) and open(copy).read() == text
            new = open(paths[name]).read().splitlines()
            assert json.loads(new[0]) == json.loads(old[0]) | {'code': v5.CODE} and json.loads(old[0])['code'] != v5.CODE
            if name.startswith('overnight_v5_240'):
                assert new[1:] == [l for l in old[1:] if json.loads(l)['key'] != THIN[0]] and len(new) == len(old) - 1
                journal = v5.Journal(paths[name])
                assert set(journal.records) == {'', HARD, NOTTHIN[0], parent} and journal.records[NOTTHIN[0]]['budget'] == 2000000
            else:
                assert new[1:] == old[1:]
        assert any(json.loads(l)['verdict'] == 'UNKNOWN' for l in open(paths['overnight_v5_304_9_journal.jsonl']).read().splitlines()[1:])
        at(240, 11)
        expect_assertion(lambda: mj.migrate(paths['overnight_v5_240_11_journal.jsonl']), 'migrate')     # already at v5.CODE
    name = 'overnight_v5_240_11_journal.jsonl'
    for found in (lambda pattern: [('12345', 'python3 overnight_v5.py 240 11')] if 'overnight_v5' in pattern else [],
                  lambda pattern: [('12346', 'python3 -B progress.py --watch')] if 'watch' in pattern else []):
        with patched(mj, alive=found, KEPT=kept_dir):
            open(paths[name], 'w').write(texts[name])
            expect_assertion(lambda: mj.migrate(paths[name]), 'migrate')
            assert open(paths[name]).read() == texts[name]
    stray = os.path.join(base, 'other_journal.jsonl')
    open(stray, 'w').write(texts[name])
    expect_assertion(lambda: mj.migrate(stray), 'migrate')
    assert open(stray).read() == texts[name]


def q_migration_alive_sees_this_process():
    # Replicata: migrate_journals.alive with the run pattern of a run this process pretends to be (a child python whose
    # command line is "overnight_v5.py 999 7"-like, sleeping), of a run no process is, and the watcher pattern.
    # Expectata: the child is listed with its pid; the other run has no process; the watcher pattern finds the page
    # watcher if and only if one runs (its command line ends in "progress.py --watch").
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)', 'overnight_v5.py', '999', '7'])
    try:
        time.sleep(1)
        found = mj.alive(mj.run_pattern('overnight_v5.py', 999, 7))
        assert any(int(pid) == p.pid for pid, _ in found), found
        assert mj.alive(mj.run_pattern('overnight_v5.py', 998, 7)) == [] and mj.alive(mj.run_pattern('boxsplit.py', 999, 7)) == []
        assert mj.alive(mj.run_pattern('overnight_v5.py', 99, 7)) == []
        watchers = mj.alive(mj.WATCHER)
        assert all(command.endswith('progress.py --watch') for _, command in watchers), watchers
    finally:
        p.kill()


# ---------- runner ----------

def main():
    names = sys.argv[1:] or [n for n in globals() if n.startswith('q_')]
    failed = 0
    for n in names:
        t0, c0 = time.time(), time.process_time()
        try:
            globals()[n]()
            # TODO: runner line; says the named qual passed, with its seconds and this process's CPU seconds
            print(f'Claude: "PASSED" {n} ({time.time() - t0:.1f} s, {time.process_time() - c0:.1f} CPU s)', flush=True)
        except Exception:
            failed += 1
            # TODO: runner line; says the named qual failed, with its seconds and this process's CPU seconds, followed by the traceback
            print(f'Claude: "FAILED" {n} ({time.time() - t0:.1f} s, {time.process_time() - c0:.1f} CPU s)\n' + traceback.format_exc(), flush=True)
    # TODO: runner summary; says how many quals passed out of how many
    print(f'Claude: "{len(names) - failed} of {len(names)} passed"')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
