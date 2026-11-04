#!/usr/bin/env python3
"""Quals for two soundness fixes in proofs/fkernel.cpp (2026-11-04; found by Codex reading the code, confirmed red by
Claude running the checker before the fix: scratch/fkernel-fix-20261104/).  Run from the repository's root:
    python3 -B quals/quals_fkernel.py
It builds proofs/fkernel.cpp with g++ -O2 -std=c++17, as quals/quals_formtree.py does (on a Mac whose g++ finds no C++
headers, with SDKROOT=$(xcrun --show-sdk-path) and CPLUS_INCLUDE_PATH=$SDKROOT/usr/include/c++/v1 set).  The fixture
is a real task of 288:10 (searches/formtree/fixtures/close.txt).  Each qual's comment gives the replicata and the
expectata; a failure's message is the resultata."""
import json, os, subprocess, sys, tempfile, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, 'searches', 'formtree', 'fixtures')
KERNEL = os.path.join(tempfile.mkdtemp(prefix='quals_fkernel_'), 'fkernel')
subprocess.run(['g++', '-O2', '-std=c++17', '-o', KERNEL, os.path.join(ROOT, 'proofs', 'fkernel.cpp')], check=True)


def task(name):
    """The fixture's one task, its lines."""
    lines = open(os.path.join(FIX, name)).read().splitlines()
    assert [line.split()[0] for line in lines].count('E') == 1 and lines[-1] == 'E', name
    return lines


def verdicts(*tasks):
    """The verdicts of one fkernel process given these tasks in order, on one stdin."""
    p = subprocess.run([KERNEL], input='\n'.join(line for t in tasks for line in t) + '\n', capture_output=True, text=True, timeout=120)
    out = [json.loads(x) for x in p.stdout.splitlines()]
    assert len(out) == len(tasks), (p.returncode, p.stdout[-400:], p.stderr[-400:])
    return out


def pinned(t, row, value):
    """The task with its P row of this id pinned to value instead."""
    out = [' '.join(line.split()[:3] + [str(value)] + line.split()[4:]) if line.split()[:2] == ['P', str(row)] else line for line in t]
    assert out != t, row
    return out


# replicata: close.txt's task, a node closed by one certificate, with its P row 17 pinned at -50, and the same task with
# that row pinned at -50 + 2^64 and at -50 - 2^64 (no sequence has such a residue sum: another node).
# expectata: three names, as the nodes differ.  Seen red, 2026-11-04: node_name printed (ll)value, one name for all three.
def q_names_keep_all_128_bits():
    t = task('close.txt')
    names = [verdicts(u)[0]['start'] for u in (t, pinned(t, 17, -50 + 2 ** 64), pinned(t, 17, -50 - 2 ** 64))]
    assert len(set(names)) == 3, names


# replicata: in one fkernel process, a task whose closing certificate weighs rows 17, 18 and 20 (modulus 5) and then a
# row the node does not have (close.txt's task with its certificate's fourth row, 24, renamed 99), and after it either
# close.txt's task itself, or that task closed by a forged certificate weighing row 17 alone (the residue sum of the
# class 0 mod 5, pinned at -50) with multiplier 1 and nothing else: K = -50 against sum_p |W(p)| = 58, the class's size,
# so it does not close; and each of those two alone, in a fresh process.
# expectata: the first task refused, for the row; then each verdict the same as in a fresh process: the real task
# accepted, the forged one refused, as not closing.  Seen red, 2026-11-04: the refusal left GMon[5] set, so the next
# certificates' W left out their modulus-5 rows while K kept them, and the forged closure was accepted (sum 0).
def q_a_failed_certificate_leaves_no_state():
    t = task('close.txt')
    bad = [line.replace(' 24 -16777216 25 ', ' 99 -16777216 25 ') if line.startswith('C ') else line for line in t]
    forged = [('C 0 0 ' + '0 ' * 10 + '1 17 1') if line.startswith('C ') else line for line in t]
    assert bad != t and forged != t
    for after, accepted in ((t, True), (forged, False)):
        first, second = verdicts(bad, after)
        alone = verdicts(after)[0]
        assert not first['ok'] and 'does not have' in first['why'], first
        assert alone['ok'] == accepted and (accepted or 'does not close' in alone['why']), alone
        assert second == alone, (second, alone)


if __name__ == '__main__':
    names = sys.argv[1:] or [k for k in list(globals()) if k.startswith('q_')]
    bad = 0
    for k in names:
        try:
            globals()[k](); print(f'ok   {k}', flush=True)
        except Exception:
            bad += 1; print(f'FAIL {k}\n{traceback.format_exc()}', flush=True)
    print('all quals pass' if not bad else f'{bad} failed')
    sys.exit(1 if bad else 0)
