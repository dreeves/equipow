# tri.py -- driver for tri.c: one run per allowed mod-3 profile (prof.py), summed.
# usage: python3 tri.py n k [--print] [--sym] [--passes P] [--head h] [--lfrac a b]
# --sym: negation maps a solution with mod-3 profile S to one with -S; the allowed
#   list is closed under S -> -S and (asserted) has no S = -S, so the runs over a
#   half Q (Q and -Q partition the list) count exactly half of all solutions.
import sys, os, subprocess, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prof

def neg(S): return tuple(-x for x in S)

def half(n, k):
    """the half Q = {S : S > -S} of the allowed mod-3 profiles, after asserting that
    negation maps the allowed list onto itself and fixes no profile in it (so Q and -Q
    partition the list, and the runs over Q count exactly half of all solutions)"""
    A3 = prof.allowed(n, k, 3)
    assert all(neg(S) in set(A3) and neg(S) != S for S in A3)
    return [S for S in A3 if S > neg(S)]

def plus_counts(n, S):
    """tri's plus1, plus2 for the mod-3 profile S: the numbers of plus signs on the
    positions whose centred coordinate c = 2i-(n-1) is 1, resp. 2, mod 3"""
    sizes = prof.sizes(n, 3)
    plus = {}
    for r in range(3):
        cls = (2 * r - (n - 1)) % 3          # centred class of the positions i = r mod 3
        assert (sizes[r] + S[r]) % 2 == 0
        plus[cls] = (sizes[r] + S[r]) // 2
    return plus[1], plus[2]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('n', type=int); ap.add_argument('k', type=int)
    ap.add_argument('--print', action='store_true'); ap.add_argument('--sym', action='store_true')
    ap.add_argument('--passes', type=int, default=1); ap.add_argument('--head', type=int, default=2)
    ap.add_argument('--lfrac', nargs=2, type=int)
    ap.add_argument('--filter', default='', help='moduli for the capacity filter, e.g. 5,7')
    a = ap.parse_args()
    n, k = a.n, a.k
    A3, mult = (half(n, k), 2) if a.sym else (prof.allowed(n, k, 3), 1)
    tot = cpu = 0
    for S in A3:
        plus1, plus2 = plus_counts(n, S)
        cmd = [os.path.join(HERE, 'tri'), str(n), str(k), str(plus1), str(plus2),
               '--passes', str(a.passes), '--head', str(a.head)]
        if a.print: cmd.append('--print')
        if a.lfrac: cmd += ['--lfrac'] + [str(x) for x in a.lfrac]
        for m in [int(x) for x in a.filter.split(',') if x]:
            path = os.path.join(HERE, 'profiles', f'n{n}_k{k}_m{m}.txt')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            prof.write(n, k, m, path)
            cmd += ['--prof', path]
        if a.filter: cmd.append('--filter')
        r = subprocess.run(cmd, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        sys.stdout.write(r.stdout)
        st = dict(t.split('=', 1) for t in r.stderr.split() if '=' in t)
        print(r.stderr.strip(), file=sys.stderr)
        tot += int(st['sols']); cpu += float(st['cpu'])
    # TODO: machine-readable summary tokens: exact total, CPU seconds, symmetry multiplier
    print(f'total={tot * mult} cpu={cpu:.2f} mult={mult} profiles={len(A3)}', file=sys.stderr)
if __name__ == '__main__':
    main()
