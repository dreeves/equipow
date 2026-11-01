# run128.py -- the full count of +-1 sequences a_0..a_127 with sum_i a_i i^j = 0 for
# j = 0..6 (order >= 7 at length 128), as separate tri processes.
#
# Negation maps a solution with mod-3 profile S to one with -S, and tri.half asserts
# that no allowed profile is its own negative, so the runs over the half Q count one
# solution of each pair {a, -a}: exactly half of all solutions.  Each profile in Q runs
# as PASSES passes (stage 1 split by R key mod PASSES, which bounds memory), one tri
# process per pass, at most J at a time:
#   tri 128 7 plus1 plus2 --passes PASSES --onlypass p --print
# A run's output (its solutions, then tri's summary line) is checked and only then
# renamed into OUT, so a file there is a finished run.  A rerun keeps those files and
# starts only the missing runs, so an interrupted count resumes where it stopped.
# Then every solution is rechecked exactly here, the passes are summed and doubled, and
# the partitions are written to OUT/sets_128_7.txt, one per line, each as the half that
# contains 0, numbered from 0.
#
# usage: python3 run128.py J
import os, sys, subprocess
from math import comb
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prof, tri

N, K, PASSES = 128, 7, 8
OUT = os.path.join(HERE, 'out128')
TRI = os.path.join(HERE, 'tri')

def say(line):                     # one write per line, so lines from worker threads stay whole
    sys.stdout.write(line + '\n'); sys.stdout.flush()

def pass_path(out, n, k, passes, plus, p):
    return os.path.join(out, f'tri_{n}_{k}_{plus[0]}_{plus[1]}_pass{p}of{passes}.txt')

def read_pass(path, n, k, passes, plus, p):
    """the solutions and summary tokens of a finished run, asserted to be complete and to
    be the run asked for"""
    lines = open(path).read().splitlines()
    # TODO: error copy; says the file does not end with tri's summary line
    assert lines and lines[-1].startswith('n='), (path, 'Claude: "no tri summary line at the end"')
    sols, st = lines[:-1], dict(t.split('=', 1) for t in lines[-1].split())
    want = dict(n=n, k=k, plus1=plus[0], plus2=plus[1], passes=passes, onlypass=p, lfrac='0/1', filter=0)
    assert {t: st[t] for t in want} == {t: str(v) for t, v in want.items()}, (path, lines[-1])
    assert int(st['sols']) == len(sols), path
    assert all(len(s) == n and set(s) <= set('+-') for s in sols), path
    return sols, st

def run_pass(n, k, passes, plus, p, out, tri_bin):
    cmd = [tri_bin, str(n), str(k), str(plus[0]), str(plus[1]), '--passes', str(passes), '--onlypass', str(p), '--print']
    r = subprocess.run(cmd, capture_output=True, text=True)
    # TODO: one line per finished tri run; says its plus counts and pass, its exit code, and tri's summary line
    say(f'Claude: "plus counts {plus[0]},{plus[1]} pass {p} of {passes}: exit code {r.returncode}; {r.stderr.strip()}"')
    assert r.returncode == 0, (cmd, r.stderr)
    path = pass_path(out, n, k, passes, plus, p)
    with open(path + '.tmp', 'w') as f: f.write(r.stdout + r.stderr)
    read_pass(path + '.tmp', n, k, passes, plus, p)
    os.replace(path + '.tmp', path)

def moments_zero(s, k):
    a = [1 if ch == '+' else -1 for ch in s]
    return all(sum(x * i**j for i, x in enumerate(a)) == 0 for j in range(k))

def half0(s):
    """the half of the partition that contains 0, numbered from 0"""
    return tuple(i for i, ch in enumerate(s) if ch == s[0])

def run(n, k, passes, J, out, tri_bin=TRI):
    # TODO: error copy; says J must be at least 1
    assert J >= 1, 'Claude: "J must be at least 1"'
    Q = tri.half(n, k)
    runs = [(tri.plus_counts(n, S), p) for S in Q for p in range(passes)]
    os.makedirs(out, exist_ok=True)
    todo = [(plus, p) for plus, p in runs if not os.path.exists(pass_path(out, n, k, passes, plus, p))]
    # TODO: says how many tri runs had already finished in the output directory, and how many start now, at most J at a time
    say(f'Claude: "{len(runs) - len(todo)} of {len(runs)} tri runs already finished in {out}; starting the other {len(todo)}, at most {J} at a time"')
    with ThreadPoolExecutor(J) as ex:
        list(ex.map(lambda t: run_pass(n, k, passes, t[0], t[1], out, tri_bin), todo))
    sols, cpu, rsum, n2 = [], 0.0, {}, {}
    for plus, p in runs:
        s, st = read_pass(pass_path(out, n, k, passes, plus, p), n, k, passes, plus, p)
        sols += s
        cpu += float(st['cpu'])
        assert int(st['L']) == comb(int(st['N1']), plus[0])           # each pass saw every L
        rsum[plus] = rsum.get(plus, 0) + int(st['R'])
        n2[plus] = int(st['N2'])
    # the passes split R by key mod passes, so together they saw each R exactly once
    assert all(rsum[plus] == comb(n2[plus], plus[1]) for plus in rsum)
    assert all(moments_zero(s, k) for s in sols)
    assert all(prof.profile(s, 3) in Q for s in sols)                 # one of each pair {a, -a}
    assert len(set(sols)) == len(sols)
    sets = sorted(half0(s) for s in sols)
    assert len(set(sets)) == len(sets)
    setsfile = os.path.join(out, f'sets_{n}_{k}.txt')
    with open(setsfile, 'w') as f:
        f.write(''.join('{' + ', '.join(map(str, A)) + '}\n' for A in sets))
    # TODO: says the exact number of +-1 sequences of length n whose power sums vanish for j = 0..k-1 (twice the number found)
    say(f'Claude: "count = {2 * len(sols)}"')
    # TODO: says that number up to negation (the number of partitions)
    say(f'Claude: "up to negation = {len(sols)}"')
    # TODO: says that number up to negation and reversal
    say(f'Claude: "up to negation and reversal = {len({min(half0(s), half0(s[::-1])) for s in sols})}"')
    # TODO: says where the partitions were written, and the tri runs' total CPU seconds
    say(f'Claude: "partitions written to {setsfile}; tri CPU {cpu:.1f} s in all"')

def main():
    # TODO: usage error; says the one argument, J, is how many tri runs may go at once
    assert len(sys.argv) == 2, 'Claude: "usage: python3 run128.py J  (J = how many tri runs at once)"'
    run(N, K, PASSES, int(sys.argv[1]), OUT)

if __name__ == '__main__':
    main()
