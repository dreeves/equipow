"""Quals for reprove.py (Claude's name, proposed 2026-10-25, awaiting dreeves's approval), which rechecks a fanout run's
saved trees from scratch, on demand: every leaf's LP solved again for an exact certificate, every W point checked
exactly.  Run with PYTHONPATH=scratch/lower24-design/beyond1000/pylib /opt/homebrew/bin/python3 -B -m unittest
quals_reprove."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

import certbb
import fanout
import focus
import reflection
import reprove
from quals_fanout import events, finish, real, stopped, unpaired
from quals_fanout_tree import digest, files, refusal, write

THUE_MORSE = [p.bit_count() % 2 for p in range(16)]          # 0110100110010110, of order 4


def grown(prepared, case, path):
    """A complete tree on the box of path, grown as fanout.work grows one, but with each W token closed as an L, as a
    forger would: the tree and the paths of the boxes it closed so."""
    equations, cases = prepared
    choice = cases[case]
    lp = focus.case_lp(equations, choice)
    stack, tree, faked = [(tuple(map(tuple, path)), None)], [], []
    while stack:
        p, basis = stack.pop()
        if basis is not None:
            assert lp.H.setBasis(basis) == certbb.highs.HighsStatus.kOk
        token = focus.step(lp, equations, choice, *fanout.box(equations.N, p))
        tree.append(['B', token[1]] if token[0] == 'B' else ['L'])
        faked += [p] if token[0] == 'W' else []
        stack += [(p + ((token[1], 1),), lp.H.getBasis()), (p + ((token[1], 0),), None)] if token[0] == 'B' else []
    return tree, faked


def split_once(tmp, prepared, position):
    """A focus.py run on prepared, stopped (a budget finish) after one token, a B on position at case 0's root, made
    by hand: no LP, as a B needs no certificate.  Its chunk is focus.commit's, so focus.replay checks it."""
    run = Path(tmp, 'run')
    run.mkdir()
    state, record = focus.State(*prepared), dict(case=0, token=['B', position])
    state.feed(record)
    state.outcome = 'budget'
    focus.commit(run, state, [record], focus.fingerprint())
    return run


def sealed(run):
    """The sha256 of every file under a directory, by path: to see that nothing changed."""
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(run).rglob('*')) if p.is_file()}


class ReproveQuals(unittest.TestCase):
    def test_a_genuine_run_is_reproven(self):
        # Replicata: unpaired()'s two impossible 20:5 cases, stopped after 1 LP solve, finished by fanout (two workers,
        # jobs of at most 4 LP solves), then reprove.run with two workers.
        # Expectata: accepted, every job fanout's journal ended reproven: its nodes the job_end's LP solves, its
        # leaves its tree's L tokens, each closed by an exact certificate from one of the three attempts; and not a
        # byte of the run's files changed.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = unpaired()
            run, journal = stopped(tmp, prepared, 20, 5, 1)
            outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            before = sealed(tmp)
            with patch.object(focus, 'prepare', return_value=prepared):
                total = reprove.run(run, work, own, 20, 5, 2)
            ends = [e for e in events(own) if e['event'] == 'job_end']
            leaves = sum(t == ['L'] for d in files(work).values() for t in d['tree'])
            self.assertEqual((total['jobs'], total['nodes'], total['leaves']),
                             (len(ends), sum(e['lps'] for e in ends), leaves))
            # Spec change proposed 2026-10-30: a leaf below the lex cut that is dead is proven by the cut's certificate,
            # counted as dead, not by an attempt.
            self.assertEqual(sum(total['attempts'].values()) + total['dead'], leaves)
            self.assertEqual(set(total['attempts']), set(reprove.ATTEMPTS))
            self.assertEqual(sealed(tmp), before)
            print(json.dumps(total), flush=True)

    def test_a_forged_run_with_one_feasible_leaf_is_refused(self):
        # Replicata: 16:4 with plus counts (0, 4, 4) mod 3, which of the two order-4 sign sequences of length 16 only
        # Thue-Morse's meets (brute force, scratch/record-20261025/launch432/treeonly/unique.py), its root split on
        # position 0 by hand (focus.search's first LP solve lands on Thue-Morse itself, a witness); then each root's
        # box given a forged job file, journaled with a job_end of its tree's sha256: a complete tree grown as
        # fanout.work grows one, but with its W token closed as an L.  The journal begins with a header naming the
        # fanout code, which assembly requires since 2026-10-26 (the code in force, fanout.py's 'switch'); before,
        # with no session record, a journal of job_ends alone passed its check of the code.
        # Expectata: assembly accepts the forgery, as it checks only the trees' shape, trusting the workers' exact
        # checks; exactly one forged L box holds a solution, Thue-Morse's; and reprove.run refuses it with an
        # AssertionError naming that box's job and path, no attempt having found a certificate for it.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = focus.moments(16, 4), (((3, (0, 4, 4)),),)
            run = split_once(tmp, prepared, 0)
            work, own, code = Path(tmp, 'fanout'), Path(tmp, 'fanout.jsonl'), focus.fingerprint()
            (work / 'jobs').mkdir(parents=True)
            fanout.note(own, 'header', fanout_code=fanout.fingerprint())    # the code in force (fanout.py's 'switch')
            roots = fanout.roots(run, work, code)
            fakes = []
            for i, root in enumerate(roots):
                tree, faked = grown(prepared, *root)
                fakes += [(root, p) for p in faked]
                fanout.save(work, root, i,
                            dict(tree=tree, tree_sha256=digest(tree), open=[], seconds=0.0, witness=None))
                fanout.note(own, 'job_end', job=fanout.jid(root), case=root[0], root=i, lps=len(tree), seconds=0.0,
                            open=0, tree_sha256=digest(tree))
            self.assertEqual(len(fanout.assemble(run, work, own, prepared, code, roots, fanout.finished(work))),
                             len(roots))
            [(root, box)] = fakes
            self.assertTrue(all(THUE_MORSE[p] == t for p, t in box))
            with patch.object(focus, 'prepare', return_value=prepared), self.assertRaises(AssertionError) as raised:
                reprove.run(run, work, own, 16, 4, 2)
            self.assertIn(fanout.jid(root), str(raised.exception))
            self.assertIn(json.dumps([list(b) for b in box]), str(raised.exception))

    def test_a_job_file_changed_after_assembly_is_refused(self):
        # Replicata: (20, 5) stopped after 5 LP solves and finished by fanout; then reprove.run with two workers,
        # fanout.assemble wrapped so that, once assembly has accepted the run, a job that left no box open loses its
        # last token, an L, and its file's tree_sha256 is made the new tree's, as a writer ignoring the locks could
        # leave it.
        # Expectata: AssertionError naming that job: each reproof walks only the tree that assembly checked.
        # Resultata before (2026-10-25 review, probe A7): accepted, 45 nodes reproven against the journal's 46.
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            # Spec change proposed 2026-10-31 (fastlp behind the producer, scratch/speed432-fastlp-20261031):
            # one worker and jobs of at most 5 LP solves, as AssemblyQuals' genuine run (quals_fanout_tree): under
            # fastlp, two workers and jobs of 4 left no job that closed its box in more than one token.
            work, own = Path(tmp, 'fanout'), Path(tmp, 'fanout.jsonl')
            with patch.object(focus, 'prepare', return_value=prepared), patch.multiple(fanout, WORKERS=1, BUDGET=5):
                outcome = fanout.run(run, work, own, 20, 5)
            self.assertEqual(outcome, 'excluded')
            name, data = next((n, d) for n, d in sorted(files(work).items()) if not d['open'] and len(d['tree']) > 1)
            self.assertEqual(data['tree'][-1], ['L'])
            real_assemble = fanout.assemble
            def assemble(*args):
                walked = real_assemble(*args)
                write(work, dict(data, tree=data['tree'][:-1], tree_sha256=digest(data['tree'][:-1])))
                return walked
            with patch.object(focus, 'prepare', return_value=prepared), patch.object(fanout, 'assemble', assemble), \
                    self.assertRaises(AssertionError) as raised:
                reprove.run(run, work, own, 20, 5, 2)
            self.assertIn(name, str(raised.exception))

    def test_the_totals_name_the_code_that_ran(self):
        # Replicata: (20, 5) stopped after 5 LP solves and finished by fanout; then reprove.run with two workers.
        # Expectata (2026-10-26 launch review: the recheck's output named no code, and reprove.py is in neither
        # focus.fingerprint nor fanout_code): its totals name the code that ran: code, focus.fingerprint, and
        # fanout_code, the sha256 of fanout.py's bytes followed by reflection.py's, both as fanout's journal names
        # them, which assembly checks; and reprove_code, the sha256 of reprove.py's bytes.
        # Resultata before: jobs, nodes, leaves, attempts and seconds alone.
        def sha(*modules):
            return hashlib.sha256(b''.join(Path(m.__file__).read_bytes() for m in modules)).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            with patch.object(focus, 'prepare', return_value=prepared):
                total = reprove.run(run, work, own, 20, 5, 2)
            head = events(own)[0]
            self.assertEqual({k: total[k] for k in ('code', 'fanout_code', 'reprove_code')},
                             dict(code=focus.fingerprint(), fanout_code=sha(fanout, reflection),
                                  reprove_code=sha(reprove)))
            self.assertEqual((head['code'], head['fanout_code']), (total['code'], total['fanout_code']))

    def test_a_code_change_during_the_recheck_is_refused(self):
        # Replicata: (20, 5) stopped after 5 LP solves and finished by fanout; copies of the sources that
        # focus.fingerprint, fanout_code and reprove_code hash, with focus.__file__, fanout.__file__ and
        # reprove.__file__ pointed at them (as quals_focus432 points focus.__file__ at copies); then reprove.run with
        # two workers, fanout.assemble wrapped so that, once assembly has accepted the run, the copy of one source is
        # changed by a byte, as by an edit in mid-recheck: certbb.py, fanout.py or reprove.py, each in turn, the
        # others as they were.
        # Expectata: AssertionError each time, in reprove.run, at its check after the reproofs that the code is still
        # the code it started with: else its totals would name code other than the code that ran.
        # Resultata before: accepted, its totals naming no code.
        root = Path(focus.__file__).resolve().parent
        names = ['focus.py', 'focus432.py', 'focus480.py', 'focus672.py', 'focus432_certificates.json.gz',
                 'focus480_certificates.json.gz', 'certbb.py', 'residues.py', 'overnight_v5.py', 'fanout.py',
                 'reflection.py', 'reprove.py']
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as copies:
            for name in names:
                shutil.copyfile(root / name, Path(copies, name))
            prepared = real(20, 5)
            run, journal = stopped(tmp, prepared, 20, 5, 5)
            outcome, work, own = finish(tmp, run, journal, prepared, 20, 5)
            self.assertEqual(outcome, 'excluded')
            real_assemble = fanout.assemble
            for name in ('certbb.py', 'fanout.py', 'reprove.py'):
                path = Path(copies, name)
                original = path.read_bytes()
                def assemble(*args):
                    walked = real_assemble(*args)
                    path.write_bytes(original + b'\n')
                    return walked
                with self.subTest(name=name), patch.object(focus, 'prepare', return_value=prepared), \
                        patch.object(focus, '__file__', str(Path(copies, 'focus.py'))), \
                        patch.object(fanout, '__file__', str(Path(copies, 'fanout.py'))), \
                        patch.object(reprove, '__file__', str(Path(copies, 'reprove.py'))), \
                        patch.object(fanout, 'assemble', assemble):
                    frames = refusal(lambda: reprove.run(run, work, own, 20, 5, 2))
                    self.assertTrue(frames)                                     # refused
                    self.assertEqual((Path(frames[-1].filename).name, frames[-1].name), ('reprove.py', 'run'))
                    self.assertIn('codes() == ', frames[-1].line)
                path.write_bytes(original)

    def test_a_W_point_is_checked_exactly(self):
        # Replicata: reprove.walk on 16:4's whole box with the one-token tree ['W', x], x Thue-Morse's sequence; then
        # with x's first bit flipped; then on the box with position 0 fixed to 1, outside which x's 0 lies.
        # Expectata: accepted, 1 node and no leaf; then AssertionError for each other.
        reprove.init(real(16, 4))
        self.assertEqual({k: v for k, v in reprove.walk((0, ()), [['W', THUE_MORSE]]).items()
                          if k in ('nodes', 'leaves')}, dict(nodes=1, leaves=0))
        for job, x in (((0, ()), [1 - THUE_MORSE[0]] + THUE_MORSE[1:]), ((0, ((0, 1),)), THUE_MORSE)):
            with self.subTest(job=job, x=x), self.assertRaises(AssertionError):
                reprove.walk(job, [['W', x]])

    def test_a_split_on_a_fixed_position_is_refused(self):
        # Replicata: reprove.walk on 20:5's box with position 0 fixed to 1, given the tree B 0, L, L: a split of the
        # position its box fixes, whose second half would be a box with position 0 at 0, outside the job's.
        # Expectata: AssertionError at the B, naming its box's path, before any LP solve: walk asserts what frontier
        # asks of a B.
        # Resultata without that assertion (scratch/record-20261025/launch432/treeonly/redcopy): the walk went on to
        # solve the B's LP, the stand-in solve raising 'solved'.
        # Spec change proposed 2026-10-31 (scratch/check432-20261031, reprove on fastlp's Dual first): the LP is a
        # fanout.Simplex, so the stand-ins are its outcome and its Dual's and HiGHS's solves.
        reprove.init(real(20, 5))
        lp = reprove.lp_for(0)
        with patch.object(lp, 'outcome', side_effect=AssertionError('solved')), \
                patch.object(lp.highs, 'solve', side_effect=AssertionError('solved')), \
                patch.object(lp, 'dual', wraps=lp.dual) as dual, \
                self.assertRaisesRegex(AssertionError, r'^\(\(0, 1\),\)$'):
            dual.solve.side_effect = AssertionError('solved')
            reprove.walk((0, ((0, 1),)), [['B', 0], ['L'], ['L']])

    def test_a_leaf_is_retried_by_highs_warm_cold_then_primal(self):
        # Replicata: the first leaf box of a complete 20:5 tree, its LP on reprove's own LP (a fanout.Simplex), after a
        # solve of the whole box by its Dual (the leaf's warm start); the first k solves of the leaf stubbed to end
        # without a ray (as at an iteration limit), k = 0, 1, 2, 3 and 4: Dual's solve first, then HiGHS's; each HiGHS
        # solve's simplex_strategy recorded, and HiGHS's clearSolver calls and Dual's load calls.
        # Expectata: proven by the dual, warm, cold, then primal attempt; with k = 4, AssertionError; the HiGHS solves'
        # strategies 1, 1, then 4; clearSolver before the cold and the primal attempts, never before the warm; Dual put
        # back to its slack basis once, before the first HiGHS attempt, never when Dual proves the leaf; and
        # simplex_strategy 1 again after every call.
        # Spec change proposed 2026-10-31 (scratch/check432-20261031): this qual was
        # test_a_leaf_is_retried_cold_then_primal, of the warm, cold and primal attempts on certbb.Lp alone; and close
        # takes the box's exact bound (reprove.native_bound_of's, GMP) in place of its rows.
        prepared = real(20, 5)
        equations, cases = prepared
        tree, _ = grown(prepared, 0, ())
        lo, hi = fanout.box(20, fanout.frontier(20, [], tree[:tree.index(['L'])])[-1])     # the box the first L closed
        rows = certbb.node_rows(equations, cases[0])
        bound = reprove.native_bound_of(equations, tuple(cases[0]), ())       # the box's exact bound (GMP)
        def stubbed(k):
            """reprove's LP for case 0 after its Dual's solve of the whole box, its next k solves ending without a ray."""
            reprove.init(prepared)
            simplex = reprove.lp_for(0)
            simplex.dual.solve([0] * 20, [1] * 20, None)                # a parent's solve: the leaf's warm start
            lp = simplex.highs
            native, solve, dual_solve, strategies, loads = lp.H, lp.solve, simplex.dual.solve, [], []
            lp.H = Mock(wraps=native)
            calls = []
            def stub(lo, hi):
                calls.append('highs')
                strategies.append(native.getOptionValue('simplex_strategy')[1])
                return ('Iteration limit reached', None) if len(calls) <= k else solve(lo, hi)
            def stub_dual(lo, hi, basis):
                calls.append('dual')
                return ('Iteration limit', None) if len(calls) <= k else dual_solve(lo, hi, basis)
            lp.solve = stub
            real_load = simplex.dual.load
            simplex.dual = Mock(wraps=simplex.dual)
            simplex.dual.solve.side_effect = stub_dual
            simplex.dual.load.side_effect = lambda codes: (loads.append(bytes(codes)), real_load(codes))[1]
            return simplex, lp, native, strategies, loads
        for k in range(4):
            with self.subTest(k=k):
                simplex, lp, native, strategies, loads = stubbed(k)
                self.assertEqual(reprove.close(simplex, bound, lo, hi, None, 'qual'), k)
                self.assertEqual(strategies, [1, 1, 4][:max(k, 0)])
                self.assertEqual(lp.H.clearSolver.call_count, max(0, min(k - 1, 2)))
                self.assertEqual(loads, [bytes(simplex.slack)] * (k >= 1))
                self.assertEqual(native.getOptionValue('simplex_strategy')[1], 1)
        simplex, lp, native, strategies, loads = stubbed(4)
        with self.assertRaises(AssertionError):
            reprove.close(simplex, bound, lo, hi, None, 'qual')
        self.assertEqual((strategies, lp.H.clearSolver.call_count, len(loads)), ([1, 1, 4], 2, 1))
        self.assertEqual(native.getOptionValue('simplex_strategy')[1], 1)


if __name__ == '__main__':
    unittest.main()
