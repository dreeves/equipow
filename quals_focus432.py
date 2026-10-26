"""Quals for focus432.py, the exact preparation of the 432:12 proof search (dreeves, 2026-10-25: "sounds good on
432:12"): its stored certificates, its saturation lemma on every small sequence, and controls through the same
preparation and lemma on small saturated cells whose answers are known exhaustively, each searched by focus.search with
every token through certbb.Check.  Run with PYTHONPATH=scratch/lower24-design/beyond1000/pylib /opt/homebrew/bin/python3
-B -m unittest quals_focus432.

The exhaustive families and the controls are ported from the 432:12 referee's sat_quals.py, ctrl_pipeline.py and
ctrl2.py (scratch/ideas-20261025/verify/v432).
"""
import copy
from collections import Counter
import io
import itertools
import json
from pathlib import Path
import random
import shutil
import sys
import tempfile
import traceback
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import numpy as np

import certbb
import fanout
import focus
import focus432
import mstar

X1, PHI2, PHI4 = (-1, 1), (1, 1), (1, 0, 1)
KMAX = 9                                    # power sums computed per vector; no vector here has order above it
POP16 = np.array([bin(i).count('1') for i in range(1 << 16)], dtype=np.int64)


# ---------- independent exact helpers (the qual's own, not focus432's) ----------

def pmul(*factors):
    """The product of integer polynomials, coefficients in increasing degree."""
    out = [1]
    for b in factors:
        product = [0] * (len(out) + len(b) - 1)
        for i, x in enumerate(out):
            for j, y in enumerate(b):
                product[i + j] += x * y
        out = product
    return out


def factor(m, e2, e4):
    """(x-1)^m Phi2^e2 Phi4^e4."""
    return pmul(*([X1] * m + [PHI2] * e2 + [PHI4] * e4))


def divide(a, b):
    """Exact division over Z by the monic b: (quotient, remainder), coefficients in increasing degree."""
    assert b[-1] == 1 and len(a) >= len(b)
    a, q = list(a), [0] * (len(a) - len(b) + 1)
    for i in reversed(range(len(q))):
        q[i] = a[i + len(b) - 1]
        for j, y in enumerate(b):
            a[i + j] -= q[i] * y
    return q, a[:len(b) - 1]


def mod2_quotient(a, b):
    """a / b over F_2, both as bits (bit i the coefficient of x^i), asserting no remainder."""
    q = 0
    while a.bit_length() >= b.bit_length():
        k = a.bit_length() - b.bit_length()
        q, a = q ^ (1 << k), a ^ (b << k)
    assert a == 0
    return q


def two_adic(n):
    return (n & -n).bit_length() - 1


def popcount(x):
    c, y = np.zeros(len(x), dtype=np.int64), x.copy()
    while y.any():
        c += POP16[y & 0xFFFF]
        y >>= 16
    return c


def functional(masks, w, n):
    """sum_p w_p a_p for the sign vectors a_p = 2 bit_p - 1 of masks (int64), exactly, by byte tables."""
    assert all(type(t) is int for t in w)
    total = np.zeros(len(masks), dtype=np.int64)
    for j in range(0, n, 8):
        table = np.array([sum(w[j + t] for t in range(8) if j + t < n and (b >> t) & 1) for b in range(256)],
                         dtype=np.int64)
        total += table[(masks >> j) & 0xFF]
    return 2 * total - sum(w)


def derivative(n):
    """The coefficients of f'(-1) = sum p (-1)^(p-1) a_p."""
    return [p * (-1) ** ((p - 1) % 2) for p in range(n)]


def balanced(n):
    """Every balanced sign vector of length n, as bit masks."""
    masks = np.arange(1 << n, dtype=np.int64)
    return masks[popcount(masks) == n // 2]


def mitm(n, kmin):
    """Every sign vector of length n with power sums 0..kmin-1 zero, by joining halves on their power sums."""
    h = n // 2
    keys = []
    for offset in (0, h):
        ms = np.arange(1 << h, dtype=np.int64)
        keys.append((ms, np.stack([functional(ms, [(offset + p) ** k for p in range(h)], h) for k in range(kmin)], 1)))
    (ml, kl), (mr, kr) = keys
    lo = np.minimum(kl.min(0), -kr.max(0))
    span = np.maximum(kl.max(0), -kr.min(0)) - lo + 1
    assert float(np.prod(span.astype(float))) < 9e18
    def encode(k):
        e = np.zeros(len(k), dtype=np.int64)
        for c in range(k.shape[1]):
            e = e * span[c] + (k[:, c] - lo[c])
        return e
    el, er = encode(kl), encode(-kr)
    order = np.argsort(er, kind='stable')
    sorted_er = er[order]
    a, b = np.searchsorted(sorted_er, el, 'left'), np.searchsorted(sorted_er, el, 'right')
    count = b - a
    left = np.repeat(np.arange(len(el)), count)
    within = np.arange(int(count.sum())) - np.repeat(np.cumsum(count) - count, count)
    return ml[left] | (mr[order[np.repeat(a, count) + within]] << h)


def counts(x, moduli):
    """The plus counts of a 0/1 vector mod each modulus, as a choice."""
    return tuple((M, tuple(sum(x[r::M]) for r in range(M))) for M in moduli)


def exact(x, n, m, choice, v):
    """Plain-integer check of a 0/1 vector: order at least m, the choice's counts, and f'(-1) = v."""
    a = [2 * t - 1 for t in x]
    return (len(a) == n and set(x) <= {0, 1} and all(sum(t * p ** k for p, t in enumerate(a)) == 0 for k in range(m))
            and counts(x, [M for M, _ in choice]) == choice and sum(d * t for d, t in zip(derivative(n), a)) == v)


def search(equations, cases, budget):
    """focus.search, the production depth-first search with every token through certbb.Check, on these equations and
    cases in a temporary directory; then focus.replay of its chunks from disk: (outcome, replayed state)."""
    with tempfile.TemporaryDirectory() as tmp, patch.object(focus, 'prepare', return_value=(equations, cases)):
        run, journal = Path(tmp, 'run'), Path(tmp, 'journal.jsonl')
        outcome = focus.search(run, journal, equations.N, equations.order, budget, 600)
        return outcome, focus.replay(run, equations, cases, focus.fingerprint())


# ---------- the preparation ----------

class Focus432Quals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.equations, cls.cases = focus432.prepare()
        cls.proof = focus432._proof()

    def refused(self, proof, where):
        """prepare with this stored proof in place of the real one must fail loudly, and where says: in that function
        of focus432, at a line holding that fragment, so for the reason the qual names and not at a later check.
        (assertRaises keeps no traceback, hence the try.)"""
        frames = []
        with patch.object(focus432, '_proof', return_value=proof):
            try:
                focus432.prepare()
            except (AssertionError, certbb.ProofError) as raised:
                frames = traceback.extract_tb(raised.__traceback__)
        self.assertTrue(frames)                                     # prepare refused it
        self.assertEqual((Path(frames[-1].filename).name, frames[-1].name), ('focus432.py', where[0]))
        self.assertIn(where[1], frames[-1].line)

    def derivative_record(self, proof, case, v):
        """proof's one derivative record of case at f'(-1) = v."""
        (record,) = [r for r in proof['derivatives'] if focus432._choice(r[:-2]) == case and r[-2] == v]
        return record

    def test_preparation_returns_B_and_A_with_the_derivative_row(self):
        # Replicata: focus432.prepare(), the runner's contract.
        # Expectata: the order-12 moment rows of length 432, then f'(-1) = 8192 as sum p (-1)^(p-1) x_p = 4204; the
        # cases B, then its complement A.
        e = self.equations
        self.assertEqual((e.N, e.order, len(e.W)), (432, 12, 13))
        self.assertEqual(e.W[:12], focus.moments(432, 12).W)
        self.assertEqual(e.W[-1], tuple(p * (-1) ** ((p - 1) % 2) for p in range(432)))
        self.assertEqual(e.rhs[-1], (8192 + 216) // 2)
        self.assertEqual(e.rhs[-1], 4204)
        A = ((3, (72, 72, 72)), (4, (54, 54, 54, 54)), (5, (81, 81, 18, 18, 18)), (7, (24, 24, 24, 24, 24, 48, 48)))
        self.assertEqual(self.cases, (focus432.B, A))
        self.assertEqual(focus432.B, ((3, (72, 72, 72)), (4, (54, 54, 54, 54)), (5, (6, 6, 68, 68, 68)),
                                      (7, (38, 38, 38, 38, 38, 13, 13))))

    def test_focus_prepare_dispatches_432_to_focus432(self):
        # Replicata: focus.prepare(432, 12) with focus432.prepare replaced by a stand-in.
        # Expectata: the stand-in's result, as for 480 and 672.
        # Resultata before the change: AssertionError, (432, 12) not a known run.
        sentinel = object()
        with patch.object(focus432, 'prepare', return_value=sentinel):
            self.assertIs(focus.prepare(432, 12), sentinel)

    def test_profiles_are_finished_enumerations_in_both_sweeps(self):
        # Replicata: the plus-count vectors mod 3, 4, 5 and 7 at 432:12, by mstar's natural and digits sweeps.
        # Expectata: 1, 25, 2 and 24 vectors, the same in both sweeps; mod 3 only (72, 72, 72); mod 5 B's and A's.
        for M, size in ((3, 1), (4, 25), (5, 2), (7, 24)):
            natural = focus432._profiles(432, 12, M)
            digits = {tuple((d + len(range(r, 432, M))) // 2 for r, d in enumerate(D))
                      for D in mstar.residue_vectors(432, M, 12, None, mstar.Budget(10 ** 6), 'digits')}
            self.assertEqual((len(natural), len(set(natural))), (size, size))
            self.assertEqual(set(natural), digits)
        self.assertEqual(focus432._profiles(432, 12, 3), ((72, 72, 72),))
        self.assertEqual(set(focus432._profiles(432, 12, 5)), {(6, 6, 68, 68, 68), (81, 81, 18, 18, 18)})

    def test_every_combination_is_certified_closed_or_is_B_or_A(self):
        # Replicata: the 1,200 combinations of profiles and the 1,198 stored root certificates.
        # Expectata: each certificate closes its own combination exactly, no two the same, and B and A remain.
        lists = [focus432._profiles(432, 12, M) for M in focus432.MODULI]
        choices = set(map(focus432._choice, itertools.product(*lists)))
        roots = [(focus432._choice(r[:-1]), r[-1]) for r in self.proof['roots']]
        self.assertEqual((len(choices), len(roots), len({c for c, _ in roots})), (1200, 1198, 1198))
        self.assertEqual(focus432._retained(focus.moments(432, 12), choices, roots), set(self.cases))
        self.assertTrue(all(len(n) == 31 for _, n in roots))

    def test_complement_swaps_B_and_A_and_negates_the_derivative_row(self):
        # Replicata: random signs of length 432, and their negation.
        # Expectata: the negation's counts are _complement's of theirs; B's complement is A and A's is B; and signs
        # meeting the derivative row at f'(-1) = v have a negation meeting it at -v.
        rng = random.Random(432)
        a = [rng.choice((-1, 1)) for _ in range(432)]
        x, y = [(t + 1) // 2 for t in a], [(1 - t) // 2 for t in a]
        self.assertEqual(counts(y, focus432.MODULI), focus432._complement(432, counts(x, focus432.MODULI)))
        self.assertEqual(focus432._complement(432, self.cases[0]), self.cases[1])
        self.assertEqual(focus432._complement(432, self.cases[1]), self.cases[0])
        v, base = sum(d * t for d, t in zip(derivative(432), a)), focus.moments(432, 12)
        for z, w in ((x, v), (y, -v)):
            row, beta = focus432._equations(base, w).sparse[-1]
            self.assertEqual(sum(c * z[p] for p, c in row), beta)

    def test_the_lemma_s_computable_parts_at_432(self):
        # Replicata: F = (x-1)^12 Phi2 Phi4, its mod-2 multiplicity and S_432's, F'(-1) and the bound.
        # Expectata: both multiplicities exactly 15, F'(-1) = 8192, sum |p - 431/2| = 46,656, so k in +-1, +-3, +-5;
        # adding Phi3 changes nothing; without Phi4, or with Phi2 twice, the factor is not saturated and is refused.
        F = factor(12, 1, 1)
        self.assertEqual(focus432._multiplicity(sum((c % 2) << i for i, c in enumerate(F))), 15)
        self.assertEqual(focus432._multiplicity((1 << 432) - 1), 15)
        self.assertEqual(focus432._lemma(432, F), (8192, (-5, -3, -1, 1, 3, 5)))
        self.assertEqual(sum(abs(p - 431 / 2) for p in range(432)), 46656)
        self.assertEqual(focus432._lemma(432, pmul(F, (1, 1, 1))), (8192, (-5, -3, -1, 1, 3, 5)))
        for unsaturated in (factor(12, 1, 0), pmul(F, PHI2)):
            with self.assertRaises(AssertionError):
                focus432._lemma(432, unsaturated)

    def test_derivative_certificates_exclude_k_3_and_5_in_both_cases(self):
        # Replicata: the 8 stored derivative certificates.
        # Expectata: B and A at f'(-1) = +-24576 and +-40960, each closed exactly on its own rows.
        base = focus.moments(432, 12)
        seen = []
        for *c, v, n in self.proof['derivatives']:
            choice = focus432._choice(c)
            rows = certbb.node_rows(focus432._equations(base, v), choice)
            self.assertGreater(certbb.lower_bound(rows, [0] * 432, [1] * 432, n), 0)
            seen.append((choice, v))
        self.assertEqual(sorted(seen), sorted((case, v) for case in self.cases for v in (-40960, -24576, 24576, 40960)))

    def test_a_zero_root_certificate_is_refused(self):
        # Replicata: the first root certificate replaced by zeros.
        # Expectata: AssertionError in _retained, at its bound: 0, so it closes nothing.
        proof = copy.deepcopy(self.proof)
        proof['roots'][0][-1] = [0] * len(proof['roots'][0][-1])
        self.refused(proof, ('_retained', 'certbb.lower_bound('))

    def test_a_duplicate_root_record_is_refused(self):
        # Replicata: the second root record replaced by the first.
        # Expectata: AssertionError in _retained: one combination closed twice, so another left unaccounted.
        proof = copy.deepcopy(self.proof)
        proof['roots'][1] = proof['roots'][0]
        self.refused(proof, ('_retained', 'choice not in closed'))

    def test_a_missing_root_record_is_refused(self):
        # Replicata: the last root record dropped.
        # Expectata: AssertionError in prepare, at the count of records: 1,197, not 1,198, so a third combination
        # would stay open.
        proof = copy.deepcopy(self.proof)
        proof['roots'].pop()
        self.refused(proof, ('prepare', 'len(roots) == 1198'))

    def test_a_certificate_cannot_close_B(self):
        # Replicata: the first root record's counts replaced by B's, its certificate kept.
        # Expectata: AssertionError in _retained, at its bound: B is LP-feasible, so no multipliers close it.
        proof = copy.deepcopy(self.proof)
        proof['roots'][0][:-1] = [list(v) for _, v in focus432.B]
        self.refused(proof, ('_retained', 'certbb.lower_bound('))

    def test_a_derivative_certificate_moved_to_8192_is_refused(self):
        # Replicata: a derivative record's value changed from +24576 to +8192, its certificate kept.
        # Expectata: AssertionError in _retained, at its bound: f'(-1) = 8192 is LP-feasible in both cases, so nothing
        # closes it.
        # Resultata, with that check deleted (scratch/record-20261025/f432/review/lax.py): AssertionError, but only at
        # the later count of excluded values, so this qual passed without the check.
        proof = copy.deepcopy(self.proof)
        record = next(r for r in proof['derivatives'] if r[-2] == 24576)
        record[-2] = 8192
        self.refused(proof, ('_retained', 'certbb.lower_bound('))

    def test_a_missing_derivative_record_is_refused(self):
        # Replicata: one derivative record dropped.
        # Expectata: AssertionError in prepare, at the excluded values: one of the four would go unexcluded.
        proof = copy.deepcopy(self.proof)
        proof['derivatives'].pop()
        self.refused(proof, ('prepare', 'sorted(excluded)'))

    def test_a_zero_derivative_certificate_is_refused(self):
        # Replicata: B's derivative certificate at f'(-1) = +24576 replaced by zeros.
        # Expectata: AssertionError in _retained, at its bound: 0, so it excludes nothing.
        # Resultata, with that check deleted (lax.py, as above): prepare accepted it, and every qual stayed green.
        proof = copy.deepcopy(self.proof)
        record = self.derivative_record(proof, focus432.B, 24576)
        record[-1] = [0] * len(record[-1])
        self.refused(proof, ('_retained', 'certbb.lower_bound('))

    def test_swapped_derivative_certificates_are_refused(self):
        # Replicata: B's derivative certificates at f'(-1) = +24576 and -24576 swapped, the values kept.
        # Expectata: AssertionError in _retained, at a bound: each certificate excludes its own value only.
        # Resultata, with that check deleted (lax.py, as above): prepare accepted it, and every qual stayed green.
        proof = copy.deepcopy(self.proof)
        plus, minus = (self.derivative_record(proof, focus432.B, v) for v in (24576, -24576))
        plus[-1], minus[-1] = minus[-1], plus[-1]
        self.refused(proof, ('_retained', 'certbb.lower_bound('))

    def test_a_derivative_row_off_by_two_or_negated_is_refused(self):
        # Replicata: prepare with _equations's derivative row saying f'(-1) = v + 2, then -v, for each v it is asked
        # for (the mutants of scratch/record-20261025/f432/review/mutants.py).
        # Expectata: AssertionError in _says, at the first derivative record: the row disagrees with f'(-1) found by
        # Horner's rule.
        # Resultata before _says: at v + 2 prepare passed, the 8 certificates closing +-24578 and +-40962 too, and
        # only the controls caught it; at -v it failed only at a certificate's bound.
        real = focus432._equations
        for name, wrong in (('v + 2', lambda v: v + 2), ('-v', lambda v: -v)):
            with self.subTest(row=name), patch.object(focus432, '_equations', lambda base, v: real(base, wrong(v))):
                self.refused(self.proof, ('_says', '_slope('))

    def test_says_checks_the_whole_derivative_row(self):
        # Replicata: _slope on every sign vector of each length 1 to 12; _says at length 8 on _equations's row for
        # each possible v, and on that row with its right side off by one, with -v's right side, or with one
        # coefficient off by one.
        # Expectata: _slope is sum p (-1)^(p-1) a_p (this file's derivative) on every vector; _says returns the true
        # equations and refuses each changed row.
        # Resultata before: no _slope or _says, so nothing in prepare checked the row.
        for n in range(1, 13):
            for a in itertools.product((-1, 1), repeat=n):
                self.assertEqual(focus432._slope(a), sum(d * t for d, t in zip(derivative(n), a)))
        base = focus.moments(8, 1)
        for v in range(-16, 17, 2):
            true = focus432._equations(base, v)
            self.assertIs(focus432._says(true, v), true)
            row, beta = list(true.W[-1]), true.rhs[-1]
            changed = [(row, beta + 1), (row, beta - 1), (row, focus432._equations(base, -v).rhs[-1])]
            changed += [(row[:p] + [row[p] + 1] + row[p + 1:], beta) for p in range(8)]
            for w, b in (c for c in changed if c != (row, beta)):      # -v's right side is v's at v = 0
                with self.subTest(v=v, row=w, rhs=b), self.assertRaises(AssertionError):
                    focus432._says(certbb.Moments(base.W, base.rhs, ((tuple(w),), (b,))), v)

    def test_profiles_refuse_impossible_residue_sums(self):
        # Replicata: _profiles at 8:1 mod 4 (classes of 2), mstar.residue_vectors replaced by a stand-in yielding a
        # sum of the wrong parity, then one too large for its class, then a vector of 3 sums.
        # Expectata: AssertionError for each.
        # Resultata before: plus counts (1, 1, 1, 0), (3, 1, 1, -1) and (1, 1, 1): floored, negative and short.
        for D in ((1, 0, 0, -1), (4, 0, 0, -4), (0, 0, 0)):
            with self.subTest(D=D), patch.object(mstar, 'residue_vectors', return_value=iter([D])), \
                    self.assertRaises(AssertionError):
                focus432._profiles(8, 1, 4)

    def test_lemma_refuses_a_factor_longer_than_the_signs(self):
        # Replicata: _lemma at length 2 with F = Phi2 Phi3 = x^3 + 2x^2 + 2x + 1: monic, F(-1) = 0, and x+1 divides it
        # once mod 2, as it does S_2 = 1 + x; but F has 4 coefficients, the signs 2.
        # Expectata: AssertionError.
        # Resultata before: (2, ()), F'(-1) read off F's first two coefficients only (it is 1).
        with self.assertRaises(AssertionError):
            focus432._lemma(2, pmul(PHI2, (1, 1, 1)))

    def test_divide_refuses_a_zero_divisor_and_a_negative_dividend(self):
        # Replicata: _divide(0b101, 0), x^2 + 1 by the zero polynomial over F_2; _divide(-0b101, 0b11).
        # Expectata: AssertionError for each.
        # Resultata before: an endless loop, each.
        for a, b in ((0b101, 0), (-0b101, 0b11)):
            with self.subTest(a=a, b=b), self.assertRaises(AssertionError):
                focus432._divide(a, b)

    def test_complement_refuses_impossible_counts(self):
        # Replicata: _complement at length 8 mod 4 (classes of 2) of the counts (3, 0, 0, 0), (-1, 1, 1, 1) and
        # (1, 1, 1).
        # Expectata: AssertionError for each.
        # Resultata before: (-1, 2, 2, 2), (3, 1, 1, 1) and (1, 1, 1), a count above its class's size or below 0
        # passed on, and a short vector.
        for c in ((3, 0, 0, 0), (-1, 1, 1, 1), (1, 1, 1)):
            with self.subTest(c=c), self.assertRaises(AssertionError):
                focus432._complement(8, ((4, c),))

    def test_fingerprint_covers_the_module_and_its_certificates(self):
        # Replicata: focus.fingerprint over copies of its sources, then with focus432.py, then its certificate file,
        # changed by a byte; and with fanout.py changed, which no proof depends on.
        # Expectata: a new fingerprint for each of the first two changes, the same one for the third.
        # Resultata before the change: focus432's files did not enter the continuation identity.
        root = Path(focus.__file__).resolve().parent
        names = ['focus.py', 'focus432.py', 'focus480.py', 'focus672.py', 'focus432_certificates.json.gz',
                 'focus480_certificates.json.gz', 'certbb.py', 'mstar.py', 'overnight_v5.py', 'fanout.py']
        with tempfile.TemporaryDirectory() as tmp:
            for name in names:
                shutil.copyfile(root / name, Path(tmp, name))
            with patch.object(focus, '__file__', str(Path(tmp, 'focus.py'))):
                before = focus.fingerprint()
                self.assertEqual(before, focus.fingerprint())
                prints = []
                for name in ('focus432.py', 'focus432_certificates.json.gz', 'fanout.py'):
                    path = Path(tmp, name)
                    original = path.read_bytes()
                    path.write_bytes(original + b'\n')
                    prints.append(focus.fingerprint())
                    path.write_bytes(original)
            self.assertNotEqual(prints[0], before)
            self.assertNotEqual(prints[1], before)
            self.assertEqual(prints[2], before)

    def test_command_lines_take_432(self):
        # Replicata: focus.py 432 and fanout.py 432, their searches replaced by stand-ins.
        # Expectata: order 12, focus.py's run in scratch/focus432/run with focus_432_journal.jsonl, fanout's in
        # scratch/fanout432 with fanout_432_journal.jsonl (fanout.run takes no focus.py journal since tree-only files,
        # 2026-10-25), and each command's line of output.
        # Resultata before the change: both refused 432 (test_command_lines_refuse_432_for_now, from the 2026-10-25
        # build until progress.survey_focus read a 432:12 journal, mstar.py's edit having landed in 59ca530).
        out = io.StringIO()
        with patch.object(focus, 'search', return_value='budget') as run, \
                patch.object(sys, 'argv', ['focus.py', '432']), redirect_stdout(out):
            focus.main()
        self.assertEqual(run.call_args.args[:4],
                         (Path('scratch/focus432/run'), Path('focus_432_journal.jsonl'), 432, 12))
        self.assertEqual(json.loads(out.getvalue()), dict(n=432, order=12, outcome='budget'))
        out = io.StringIO()
        with patch.object(fanout, 'run', return_value='excluded') as run, patch.object(fanout.signal, 'signal'), \
                patch.object(sys, 'argv', ['fanout.py', '432']), redirect_stdout(out):
            fanout.main()
        self.assertEqual(run.call_args.args, (Path('scratch/focus432/run'), Path('scratch/fanout432'),
                                              Path('fanout_432_journal.jsonl'), 432, 12))
        self.assertEqual(json.loads(out.getvalue()), dict(n=432, order=12, outcome='excluded'))


# ---------- the saturation lemma on every small sequence ----------

class SaturationLemmaQuals(unittest.TestCase):
    """For n = 2^v u, u odd, and any divisor G = (x-1)^m' Phi2^e2 Phi4^e4 of f: mu = m' + e2 + 2 e4 <= 2^v - 1, and
    h = f/G is odd at -1 iff mu = 2^v - 1, read off f'(-1) = G'(-1) h(-1) when e2 = 1, f(-1) = G(-1) h(-1) when e2 = 0,
    with |G'(-1)|, |G(-1)| = 2^(m'+e4).  focus432._lemma on each such G with e2 = 1 must return the slope and k's that
    hold every f'(-1) when saturated, and refuse G otherwise."""
    mutants = [0, 0, 0]

    @classmethod
    def tearDownClass(cls):
        # Expectata: each mutant prediction (Phi4 counted once, v off by one, always odd) fails somewhere: these
        # families can tell the lemma from its near misses.
        assert all(cls.mutants), cls.mutants

    def family(self, masks, n):
        v, sat = two_adic(n), 2 ** two_adic(n) - 1
        alive, order = np.ones(len(masks), dtype=bool), np.zeros(len(masks), dtype=np.int64)
        for k in range(KMAX + 1):
            alive &= functional(masks, [p ** k for p in range(n)], n) == 0
            order += alive
        self.assertFalse(alive.any())
        fm1 = functional(masks, [(-1) ** p for p in range(n)], n)
        fpm1 = functional(masks, derivative(n), n)
        D4 = [functional(masks, [int(p % 4 == r) for p in range(n)], n) for r in range(4)]
        phi2, phi4 = fm1 == 0, (D4[0] == D4[2]) & (D4[1] == D4[3])      # f(i) = (D0 - D2) + i (D1 - D3)
        checks = 0
        for mp, e2, e4 in itertools.product(range(1, int(order.max()) + 1), (0, 1), (0, 1)):
            sel = (order >= mp) & (phi2 | (e2 == 0)) & (phi4 | (e4 == 0))
            mu, value = mp + e2 + 2 * e4, (fpm1 if e2 else fm1)[sel]
            div = value % (1 << (mp + e4)) == 0
            odd = div & ((value // (1 << (mp + e4))) % 2 == 1)
            self.assertTrue((div & (odd == (mu == sat)) & (mu <= sat)).all(), (n, mp, e2, e4))
            checks += int(sel.sum())
            self.mutants[0] += int((div & (odd != (mp + e2 + e4 == sat))).sum())
            self.mutants[1] += int((div & (odd != (mu == 2 ** (v + 1) - 1))).sum())
            self.mutants[2] += int((div & ~odd).sum())
        for mp, e4 in itertools.product(range(1, int(order.max()) + 1), (0, 1)):
            G = factor(mp, 1, e4)
            sel = (order >= mp) & phi2 & (phi4 | (e4 == 0))
            with self.subTest(n=n, m=mp, e4=e4):
                if mp + 1 + 2 * e4 == sat:
                    slope, ks = focus432._lemma(n, G)
                    self.assertEqual(abs(slope), 2 ** (mp + e4))
                    self.assertTrue((fpm1[sel] % slope == 0).all() and np.isin(fpm1[sel] // slope, ks).all())
                    self.assertTrue(all(k % 2 and 2 * abs(slope * k) <= n * n // 2 for k in ks))
                else:
                    with self.assertRaises(AssertionError):
                        focus432._lemma(n, G)
        # Exact division on a sample: G with every odd prime d whose residue sums vanish; h(-1) and h mod 2 as the
        # lemma says.
        rng = random.Random(n)
        for i in rng.sample(range(len(masks)), min(100, len(masks))):
            a = [2 * ((int(masks[i]) >> p) & 1) - 1 for p in range(n)]
            G = factor(int(order[i]), int(phi2[i]), int(phi4[i]))
            for d in (d for d in range(3, n + 1) if all(d % q for q in range(2, d))):
                G = pmul(G, [1] * d) if all(sum(a[r::d]) == 0 for r in range(d)) else G
            h, r = divide(a, G)
            mu = int(order[i]) + int(phi2[i]) + 2 * int(phi4[i])
            self.assertEqual(r, [0] * (len(G) - 1))
            self.assertEqual(sum(c * (-1) ** j for j, c in enumerate(h)) % 2 == 1, mu == sat)
            self.assertEqual(mod2_quotient((1 << n) - 1, sum((c % 2) << j for j, c in enumerate(G))),
                             sum((c % 2) << j for j, c in enumerate(h)))
        return checks

    def test_every_balanced_sequence_up_to_24(self):
        # Replicata: every balanced sign vector of each even length 2 to 24 (3.66M vectors).
        # Expectata: the lemma holds for every divisor of every one, and _lemma agrees.
        self.assertGreater(sum(self.family(balanced(n), n) for n in range(2, 25, 2)), 4_000_000)

    def test_every_order_2_sequence_at_28_and_order_4_at_40(self):
        # Replicata: every sign vector of order at least 2 at length 28 (723,354), of order at least 4 at 40 (4,414).
        # Expectata: as above; 40 = 8*5 has 432's structure, (x-1)^4 Phi2 Phi4.
        masks28, masks40 = mitm(28, 2), mitm(40, 4)
        self.assertEqual((len(masks28), len(masks40)), (723354, 4414))
        self.family(masks28, 28)
        self.family(masks40, 40)


# ---------- controls through the same preparation and lemma ----------

class PipelineControls(unittest.TestCase):
    def truth(self, n, m):
        """Exhaustive: of the sign vectors of order at least m whose residue sums mod 4 all vanish, how many have
        f'(-1) = 32 k, for each k (all of them have 32 | f'(-1))."""
        masks = mitm(n, m)
        D4 = [functional(masks, [int(p % 4 == r) for p in range(n)], n) for r in range(4)]
        values = functional(masks[(D4[0] == 0) & (D4[1] == 0) & (D4[2] == 0) & (D4[3] == 0)], derivative(n), n)
        self.assertTrue((values % 32 == 0).all())
        return Counter(int(k) for k in values // 32)

    def subcases(self, n, m, expected):
        """24:4 or 40:4 with every residue sum mod 4 zero: F = (x-1)^4 Phi2 Phi4, saturated at n = 8 * odd as at 432;
        each of the lemma's odd k searched by focus.search; a witness exactly where the exhaustive truth has one."""
        truth = self.truth(n, m)
        slope, ks = focus432._lemma(n, factor(m, 1, 1))
        self.assertEqual((slope, ks), expected)
        self.assertTrue(set(truth) <= set(ks))                   # the lemma's prediction: no even k, none too large
        base, choice = focus.moments(n, m), ((4, (n // 8,) * 4),)
        lps = {}
        for k in ks:
            outcome, state = search(focus432._equations(base, slope * k), (choice,), 20000)
            with self.subTest(n=n, k=k):
                self.assertEqual(outcome, 'witness' if truth[k] else 'excluded')
                self.assertTrue(state.witness is None or exact(state.witness, n, m, choice, slope * k))
                self.assertEqual(state.completed, [] if truth[k] else [0])
            lps[k] = state.lp
        print(json.dumps(dict(n=n, order=m, truth=dict(sorted(truth.items())), lps=lps)), flush=True)

    def test_24_4_with_balanced_mod_4_matches_exhaustive_truth(self):
        # Replicata: 24:4, every residue sum mod 4 zero, f'(-1) = 32 k for each odd k of the lemma.
        # Expectata: k in +-1, +-3, all four with witnesses, as the exhaustive count says.
        self.subcases(24, 4, (32, (-3, -1, 1, 3)))

    def test_40_4_with_balanced_mod_4_matches_exhaustive_truth(self):
        # Replicata: 40:4 likewise, k odd with |32 k| <= 400.
        # Expectata: witnesses for k = +-1 to +-9, complete exclusions for +-11, as the exhaustive count says.
        self.subcases(40, 4, (32, tuple(range(-11, 12, 2))))

    def test_56_6_is_excluded_root_closure_lemma_and_search(self):
        # Replicata: 56:6 (m*(56) = 5): every profile mod 3, 4, 5, 7; root certificates from the option's LP, checked
        # by focus432._retained; then F = (x-1)^6 Phi2 on the survivors, each odd k searched by focus.search.
        # Expectata: 7,100 combinations, 7,098 closed, two left, both with balanced mod-4 counts; F'(-1) = 64 and
        # k = +-1 to +-11; every subcase excluded with a complete proof.  (With Phi4 too, mu = 9 > 7: _lemma refuses
        # that factor, and indeed no sequence has it.)
        base = focus.moments(56, 6)
        lists = [focus432._profiles(56, 6, M) for M in (3, 4, 5, 7)]
        self.assertEqual([len(v) for v in lists], [2, 25, 2, 71])
        choices = sorted(set(map(focus432._choice, itertools.product(*lists))))
        lp = focus.case_lp(base, choices[0])
        records = []
        for choice in choices:
            lp.set_counts(choice)
            self.assertEqual(lp.H.clearSolver(), certbb.highs.HighsStatus.kOk)
            status, ray = lp.solve([0] * 56, [1] * 56)
            records += [(choice, lp.multipliers(ray))] if status == 'Infeasible' and ray is not None else []
        good = [(c, n) for c, n in records if certbb.lower_bound(certbb.node_rows(base, c), [0] * 56, [1] * 56, n) > 0]
        kept = focus432._retained(base, set(choices), good)
        self.assertEqual((len(choices), len(good), len(kept)), (7100, 7098, 2))
        self.assertTrue(all(dict(c)[4] == (7, 7, 7, 7) for c in kept))
        with self.assertRaises(AssertionError):
            focus432._lemma(56, factor(6, 1, 1))
        slope, ks = focus432._lemma(56, factor(6, 1, 0))
        self.assertEqual((slope, ks), (64, tuple(range(-11, 12, 2))))
        for k in ks:
            outcome, state = search(focus432._equations(base, slope * k), tuple(sorted(kept)), 20000)
            with self.subTest(k=k):
                self.assertEqual((outcome, state.completed, state.frontier), ('excluded', [0, 1], []))

    def test_72_6_and_88_6_witnesses_are_found_in_their_own_subcases(self):
        # Replicata: BGPW Table 5's 72:6 and 88:6, both with f(-1) = 0 (so F = (x-1)^6 Phi2, saturated at 8 * odd); each
        # one's own subcase: its counts mod 3, 4, 5, 7 and its f'(-1), searched by focus.search.
        # Expectata: f'(-1)/64 = 7 and 1, odd k of the lemma; a witness found in each subcase, exact (2026-10-25,
        # under case_lp: after 110 and 10,521 LP solves).
        for code, n, k in (('998EAA3C5', 72, 7), ('96C362DE4A3', 88, 1)):
            a = mstar.from_rp(code, 6, n)
            x = [(t + 1) // 2 for t in a]
            choice = counts(x, (3, 4, 5, 7))
            slope, ks = focus432._lemma(n, factor(6, 1, 0))
            v = sum(d * t for d, t in zip(derivative(n), a))
            f_at_minus_1 = sum(t * (-1) ** p for p, t in enumerate(a))
            self.assertEqual((mstar.order(a), f_at_minus_1, slope, v), (6, 0, 64, 64 * k))
            self.assertIn(k, ks)
            self.assertTrue(exact(x, n, 6, choice, v))
            outcome, state = search(focus432._equations(focus.moments(n, 6), v), (choice,), 10 ** 5)
            with self.subTest(n=n):
                self.assertEqual(outcome, 'witness')
                self.assertTrue(exact(state.witness, n, 6, choice, v))
            print(json.dumps(dict(n=n, order=6, k=k, lps=state.lp)), flush=True)


if __name__ == '__main__':
    unittest.main()
