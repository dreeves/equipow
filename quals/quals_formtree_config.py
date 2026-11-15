#!/usr/bin/env python3
"""Quals for fresh form-tree configurations and their class coordinates.

Run with the dependencies of cellconfig.py (including fpylll) available:
    python3 -B quals/quals_formtree_config.py [q_name ...]
The existing form-tree suite supplies isolated builds and both exact checkers.
"""
import sys
sys.dont_write_bytecode = True
import json, os, subprocess, tempfile, time, traceback
from functools import lru_cache
from pathlib import Path
import quals_formtree as q

sys.path.insert(0, q.PROVER)
os.environ['PE_LIB'] = q.build_engine()
import pex
import cellconfig

MODS = [3, 4, 5, 7, 8, 9, 11, 13, 16, 17, 19, 23, 25, 27]
WORK = tempfile.TemporaryDirectory(prefix='quals_formtree_config_')


@lru_cache(maxsize=None)
def configuration(n, m):
    path = Path(WORK.name, f'{n}_{m}.cfg')
    pex.write_config(n, m, MODS, str(path))
    return path


def forms(path):
    """The emitted forms as a consumer reads them: one coefficient per natural residue class."""
    lines = iter(path.read_text().splitlines())
    n, m, count = map(int, next(lines).split())
    result = {}
    for _ in range(count):
        M, nb, mult = map(int, next(lines).split())
        for _ in range(4 + M): next(lines)
        result[M] = [list(map(int, next(lines).split())) for _ in range(int(next(lines)))]
    assert len(list(lines)) == m
    return result


def q_composite_forms_keep_their_residue_values():
    # Replicata: fresh 152:7 config at each composite prime-power modulus used by the prover;
    # evaluate each emitted form on residue sums D_r = r + 1.
    # Expectata: the value equals the source dual vector evaluated in its basis's coordinate order.
    # Resultata before: weights were attached to other classes, changing these form values.
    written = forms(configuration(152, 7))
    for M in (4, 8, 9, 16, 25, 27):
        _, _, order, _ = cellconfig.problem(152, 7, M)
        original = cellconfig.dual_forms(152, 7, M)[:200]
        assert len(written[M]) == len(original) > 0
        for actual, source in zip(written[M], original):
            for r in range(M):
                assert actual[r] == source[order.index(r)], (M, r, actual, source.tolist())
            assert sum((r + 1) * v for r, v in enumerate(actual)) == sum((r + 1) * v for r, v in zip(order, source))


def q_prime_forms_remain_unchanged():
    # Replicata: the same fresh configuration's prime-modulus forms.
    # Expectata: natural and basis orders coincide, so every coefficient stays unchanged.
    # Resultata: a permutation applied in the wrong direction or at the wrong level could alter these controls.
    written = forms(configuration(152, 7))
    for M in (3, 5, 7, 11, 13, 17, 19, 23):
        assert written[M] == cellconfig.dual_forms(152, 7, M)[:200].tolist(), M


def q_parity_form_has_its_exact_grid():
    # Replicata: the first mod 4 form emitted for 152:7, checked independently by proofs/formtree.py.
    # Expectata: alternating signs, f(-1), with grid 128 + 256Z.
    # Resultata before: (1,1,-1,-1), whose grid was -16 + 32Z, hid the exclusion.
    w = forms(configuration(152, 7))[4][0]
    assert w == [1, -1, 1, -1], w
    step, offset = q.ft.Cell(152, 7).grid(4, tuple(w))
    assert step == 256 and offset % step == 128, (step, offset)


def stream(n, m, pins, name, seconds):
    """Run a fresh config through the real prover, retaining a stream for both exact checkers."""
    cfg, base = configuration(n, m), Path(WORK.name, name)
    source = '''
import json, os
import pex as pe
c = json.loads(os.environ['CASE'])
pe.init(c['n'], c['m'], c['mods'], [4,8,11,13,9,17,19,23,16,25,27], path=c['cfg'], **pe.RUN_INIT)
pe.run_settings()
pe.start_file(c['pins'], c['base'])
pe.lib.pe_certfd(os.open(c['base'] + '.stream', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600))
r = pe.run_file(c['base'], c['seconds'], None, c['base'] + '.spill')
pe.lib.pe_certfd(-1)
open(c['base'] + '.json', 'w').write(json.dumps(r))
'''
    case = dict(n=n, m=m, mods=MODS, cfg=str(cfg), base=str(base), pins=pins, seconds=seconds)
    env = dict(os.environ, CASE=json.dumps(case), PYTHONPATH=q.PROVER + os.pathsep + os.environ.get('PYTHONPATH', ''),
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    env.pop('PEX_FOLD', None)
    subprocess.run([sys.executable, '-B', '-c', source], env=env, check=True, timeout=30)
    lines = Path(str(base) + '.stream').read_text().splitlines()
    a, b = q.both(lines)
    assert a['ok'] and a == b, (name, a, b)
    return lines, a


def q_correct_forms_close_the_missed_parity_cases():
    # Replicata: three 152:7 start cases that the old writer's config did not close at their first node;
    # these are cases 1791, 3663, 4455 in pintree.vectors' mod 3, 5, 7 enumeration, measured 2026-11-10.
    # Expectata: each closes at one node with its new config, accepted by both exact checkers.
    # Resultata before: the misplaced parity-form weights caused branching instead of the immediate exclusion.
    cases = [
        {3: [-27, 27, 0], 5: [-25, 5, 10, -10, 20], 7: [14, 0, 0, 0, 0, -7, -7]},
        {3: [-27, 27, 0], 5: [-25, 25, 0, 0, 0], 7: [14, 0, 0, 0, 0, -7, -7]},
        {3: [-27, 27, 0], 5: [-15, -15, 10, 10, 10], 7: [-14, 0, 0, 14, -14, 7, 7]},
    ]
    for i, pins in enumerate(cases):
        _, v = stream(152, 7, pins, f'parity_{i}', 2.0)
        assert v['nodes'] == v['closed'] == 1 and v['open'] == 0 and v['spills'] == [], v


def q_correct_forms_preserve_a_known_sequence():
    # Replicata: Thue-Morse's 128 signs, of order 7, as a start node under a freshly generated config.
    # Expectata: both checkers accept; following that sequence through every tested grid and bound never excludes it.
    # Resultata: an incorrect form conversion must not obtain apparent speed by losing valid sequences.
    a = [(-1) ** i.bit_count() for i in range(128)]
    assert q.order(a) == 7
    pins = {M: [sum(a[r::M]) for r in range(M)] for M in (3, 5, 7)}
    lines, _ = stream(128, 7, pins, 'witness', 0.25)
    followed = q._follow(q.ft.Cell(128, 7), lines, a)
    assert followed['grids'] > 0 and followed['followed'] > 0, followed


def main():
    names = sys.argv[1:] or [name for name in globals() if name.startswith('q_')]
    failed = 0
    for name in names:
        start = time.monotonic()
        try:
            globals()[name]()
            # TODO: the named qual passed, followed by elapsed seconds.
            print(f'TRANSIIT {name} ({time.monotonic() - start:.1f} s)', flush=True)
        except Exception:
            failed += 1
            # TODO: the named qual failed, followed by its traceback.
            print(f'DEFECIT {name}\n{traceback.format_exc()}', flush=True)
    WORK.cleanup()
    sys.exit(bool(failed))


if __name__ == '__main__': main()
