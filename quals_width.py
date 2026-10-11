#!/usr/bin/env python3
"""Quals for the width test: certbb's cut token ('D', u, c), its checker, its search, width.py's directions, the
CODE fingerprint, and migrate_journals.py.  Run: nice -n 19 python3 -B quals_width.py [name ...]

Each qual is a function q_*: a passing qual returns, a failing one raises; its comment gives the replicata and the
expectata, a failure's message or traceback the resultata.  Quals marked "regression" pin values found by the
verification's scans (scratch/strategy/verify-engine/thin240.out, the journals) or by the first green run.  The
regression against the width test's absence replays scratch/width/old_certbb.py, the certbb.py of 2026-10-08 pinned
before this work (not in git: scratch/ is ignored; the quals assert it is there).  Qual journals go under
scratch/width/quals/; no journal or log of a run is read for writing, and the live run is never touched.
"""
import sys
sys.dont_write_bytecode = True
import os, json, time, random, itertools, hashlib, importlib.util, inspect, shutil, subprocess, tempfile, traceback, math
import numpy as np
import overnight_v5 as v5
import certbb
import width
import migrate_journals as mj
from quals_v5 import at, expect_proof_error, expect_assertion, patched, run_child, power_sum_solutions, solved, x01, \
    example_node, choice_of, EXAMPLE, C2, BIG

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
# the live 240@11 journal's header line as it was before this work (its code field is the old CODE); read only
OLD_HEADER = {"tag": "overnight_v5", "N": 240, "order": 11, "code": "ff0e0b36ed39ffe695f968b7fa5b0183525be715",
              "solver": "certbb", "budget_unit": "LP solves", "highs": "1.12.0 (4f96ee8)"}
# proof sha1s pinned by the first green run (2026-10-10, HiGHS 1.12.0 (4f96ee8)): the cut proofs of the nodes above
# and C2's old-format proof (regression; the token streams are deterministic for the HiGHS build, as the branch and
# bound's are, and a cut's certificates come from its sides' dual rays)
PINNED = {'HARD': 'c6816b9bfb06f0b64ee1ae378837463add919454', 'THIN0': '29f12b08f6b0bf211397c40ece336c6438416c38',
          'THIN1': 'cd40675a4706a969d4e644b2a02b2dc15b599ed6', 'THIN2': 'b2803a8ca042a95c6a6506502172fbf543f616cd',
          'DEPTH5': '6daacece3c9065b7c921c64763da2ce70be50db7', 'C2': '052a5d716d67fd1c147ab13dd58af6fb60aa654b'}


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
    # Expectata: accepted where said, ProofError everywhere else, with the messages named.
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
    # claim that did not certify, cuts 0); the NOTTHIN leaves are UNKNOWN at 100 with no D token and the old certbb's
    # tokens exactly (width 2 * 182 plus 2 per failed thin claim, cuts 0).
    old = old_certbb()
    at(304, 9)
    node = parse_key(LA)
    verdict, _, stats, tokens = solved(9, node)
    old_tokens = []
    assert old.solve(v5.moments(9), node, BIG, old_tokens.append)[0] == 'INFEASIBLE'
    assert verdict == 'INFEASIBLE' and stats['lp'] == 10009 and sha1_of(tokens).startswith(LA_SHA1), (verdict, stats)
    assert tokens == old_tokens and stats['width'] == 2 * 270 + 2 * stats['cut_fail'] and stats['cuts'] == 0, stats
    at(240, 11)
    for key in NOTTHIN:
        node = parse_key(key)
        verdict, _, stats, tokens = solved(11, node, 100)
        old_tokens = []
        assert old.solve(v5.moments(11), node, 100, old_tokens.append)[0] == 'UNKNOWN'
        assert verdict == 'UNKNOWN' and stats['lp'] == 100 and tokens == old_tokens and not any(t[0] == 'D' for t in tokens)
        assert stats['width'] == 2 * 182 + 2 * stats['cut_fail'] and stats['cuts'] == 0, stats


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


def q_witnesses_kept():
    # Replicata: at 240@11, order 10, the node of the published order-10 example under the cascade, on the full box
    # at budget 400 and pinned to the example; at 304@9, order 8, the node of the order-8 example (3, 5, 4, 7, 8, 9),
    # likewise.
    # Expectata: on the full box, never INFEASIBLE (the example is in the node), no D token, every direction scanned
    # with no cut (width 2 * dim plus 2 per thin claim that did not certify, cuts 0: a node with a solution has an
    # integer in every range); pinned, FEASIBLE with the example, as overnight_v5.control asks.
    for n, order, dim in ((240, 10, 183), (304, 8, 271)):       # dim = N - deg K at that order
        at(n, order + 1)
        a = v5.from_hex(v5.EXAMPLES[n, order], order)
        node = tuple((M, (v5.counts(a, M),)) for M in v5.CASCADE)
        verdict, x, stats, tokens = solved(order, node, 400)
        assert verdict != 'INFEASIBLE' and not any(t[0] == 'D' for t in tokens), (n, verdict, stats)
        assert stats['width'] == 2 * dim + 2 * stats['cut_fail'] and stats['cuts'] == 0, (n, stats)
        pin = x01(a)
        verdict, x, stats, tokens = solved(order, node, 1, lo=pin, hi=pin)
        assert verdict == 'FEASIBLE' and x == pin and stats['lp'] == 1 and stats['width'] == 0, (n, verdict, stats)


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
    # with w = u - A^T num / den), den > 0 and gcd(num, den) = 1; and the offset is (floor, frac) of num . b / den.
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
                assert len(d.u) == n and all(type(t) is int for t in d.u) and type(d.den) is int and d.den > 0
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
    # Replicata: a journal under scratch/width/quals holding the 240@11 journal's old header line (OLD_HEADER, the code
    # field the CODE before this work) and one record; v5.Journal on it at 240@11; then the same with the current
    # header.
    # Expectata: the old header is refused ("belongs to another configuration", AssertionError in __init__); the
    # current one is admitted; the two headers differ only in code, and v5.CODE is not the old one.
    at(240, 11)
    assert v5.header() | {'code': OLD_HEADER['code']} == OLD_HEADER and v5.CODE != OLD_HEADER['code']
    rec = {'key': '', 'verdict': 'UNKNOWN', 'budget': 10000, 'lps': 10000, 'leaves': 4957, 'proof': 'ac075bf8d3f93ea7ea39fc276b2ed529dc8a434f'}
    path = os.path.join(QUALS, 'old_header_journal.jsonl')
    open(path, 'w').write(json.dumps(OLD_HEADER) + '\n' + json.dumps(rec) + '\n')
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
    # Replicata: under scratch/width/quals, a copy of the 240@11 journal's first 300 lines (old header; read from the
    # live journal, never written), a copy of the 304@9 journal's first 300 lines and of the boxsplit journal's first
    # 50; migrate_journals.migrate on each with the process check patched to find nothing; then on a journal whose run
    # the patched check reports alive, and on a journal with an unknown name.
    # Expectata: 240's: the header's code field is v5.CODE and nothing else changed, every UNKNOWN record is gone and
    # every other record is there in its order; a copy of the journal as it was is kept where the script's KEPT says
    # (patched to the quals' directory, so that the real copies' places stay free); the migrated journal opens through
    # v5.Journal with the records expected.  304's and the boxsplit's:
    # the header's code field only, every record kept.  AssertionError for the live run and for the unknown name;
    # nothing written in those two cases.
    at(240, 11)
    lines = {'overnight_v5_240_11_journal.jsonl': 300, 'overnight_v5_304_9_journal.jsonl': 300, 'overnight_v5_304_9_boxsplit_journal.jsonl': 50}
    copies = {}
    for name, k in lines.items():
        with open(os.path.join(HERE, name)) as fh:
            text = ''.join(itertools.islice(fh, k))
        d = os.path.join(QUALS, 'migrate', name.replace('.jsonl', ''))
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, name)
        open(path, 'w').write(text)
        copies[name] = (path, text)
    shutil.rmtree(os.path.join(QUALS, 'migrate', 'kept'), ignore_errors=True)
    with patched(mj, alive=lambda program, n, order: [], KEPT=os.path.join(QUALS, 'migrate', 'kept')):
        for name, (path, text) in copies.items():
            kept = mj.migrate(path)
            assert os.path.exists(kept) and open(kept).read() == text and kept.startswith(os.path.join(QUALS, 'migrate', 'kept')), kept
            old, new = text.splitlines(), open(path).read().splitlines()
            assert json.loads(new[0]) == json.loads(old[0]) | {'code': v5.CODE} and json.loads(old[0])['code'] == OLD_HEADER['code']
            if name.startswith('overnight_v5_240'):
                assert new[1:] == [l for l in old[1:] if json.loads(l)['verdict'] != 'UNKNOWN'] and len(new) < len(old)
                assert not any('UNKNOWN' in l for l in new[1:])
                journal = v5.Journal(path)
                assert set(r['verdict'] for r in journal.records.values()) <= {'INFEASIBLE', 'CLOSED'}
            else:
                assert new[1:] == old[1:]
    with patched(mj, alive=lambda program, n, order: [('12345', f'python3 {program} {n} {order}')], KEPT=os.path.join(QUALS, 'migrate', 'kept')):
        path, text = copies['overnight_v5_240_11_journal.jsonl']
        open(path, 'w').write(text)
        expect_assertion(lambda: mj.migrate(path), 'migrate')
        assert open(path).read() == text
    stray = os.path.join(QUALS, 'migrate', 'other_journal.jsonl')
    open(stray, 'w').write(text)
    expect_assertion(lambda: mj.migrate(stray), 'migrate')
    assert open(stray).read() == text


def q_migration_alive_sees_this_process():
    # Replicata: migrate_journals.alive for a run this process pretends to be (a child python whose command line is
    # "overnight_v5.py 240 11"-like, sleeping), and for a run no process is.
    # Expectata: the child is listed with its pid; the other run has no process.
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)', 'overnight_v5.py', '999', '7'])
    try:
        time.sleep(1)
        found = mj.alive('overnight_v5.py', 999, 7)
        assert any(int(pid) == p.pid for pid, _ in found), found
        assert mj.alive('overnight_v5.py', 998, 7) == [] and mj.alive('boxsplit.py', 999, 7) == []
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
