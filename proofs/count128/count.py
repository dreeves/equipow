# count.py -- driver for bdfs: builds the profile lists, applies the symmetry
# reductions (each one asserted valid), runs bdfs, and prints the exact total.
#
# usage: python3 count.py n k [--mode full|sym|anti] [--moduli 9,5,7] [--sym]
#                         [--print] [--part D W] [--sample D rate seed]
#
# --sym uses two bijections of the solution set onto itself:
#  * negation a -> -a maps profiles S -> -S.  The first modulus's list A is
#    replaced by a half Q with Q and -Q disjoint and covering A (asserted:
#    no S in A equals -S).  Solutions with profile in Q are counted; the total
#    is twice that.
#  * phi = negation after reversal (a_i -> -a_{n-1-i}), which sends u -> -u
#    and keeps v, or rho = reversal (a_i -> a_{n-1-i}), which sends v -> -v
#    and keeps u.  Whichever maps Q onto Q (asserted) is passed to bdfs as
#    --flip u or --flip v; bdfs keeps one member of each orbit and weights it.
# --part D W runs W processes over the depth-D subtrees (index mod W) and sums.
# --sample D rate seed explores each depth-D subtree with probability 1/rate
#   and prints the Horvitz-Thompson estimate of the total node count and of the
#   weighted solution count, with a 95% half-width from the sampled sizes.
import os, sys, subprocess, argparse, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prof

def proj3(S):
    m = len(S)
    return tuple(sum(S[r] for r in range(m) if r % 3 == t) for t in range(3)) if m % 3 == 0 else ()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('n', type=int); ap.add_argument('k', type=int)
    ap.add_argument('--mode', default='full', choices=['full', 'sym', 'anti'])
    ap.add_argument('--moduli', default='9,5,7')
    ap.add_argument('--sym', action='store_true')
    ap.add_argument('--print', action='store_true')
    ap.add_argument('--part', nargs=2, type=int, metavar=('D', 'W'))
    ap.add_argument('--sample', nargs=3, type=int, metavar=('D', 'RATE', 'SEED'))
    ap.add_argument('--knuth', nargs=2, type=int, metavar=('PROBES', 'SEED'))
    a = ap.parse_args()
    n, k = a.n, a.k
    mods = [int(x) for x in a.moduli.split(',') if x.strip()]
    pdir = os.path.join(HERE, 'profiles'); os.makedirs(pdir, exist_ok=True)
    files, lists = [], []
    for m in mods:
        path = os.path.join(pdir, f'n{n}_k{k}_m{m}.txt')
        rows = prof.allowed(n, k, m)
        prof.write(n, k, m, path, rows)
        files.append(path); lists.append(rows)
    flip, mult = None, 1
    if a.sym:
        assert mods, 'Claude: "--sym needs at least one modulus"'
        m, A = mods[0], lists[0]
        Aset = set(A)
        neg = lambda S: tuple(-x for x in S)
        assert all(neg(S) in Aset for S in A)                    # A is closed under negation
        assert all(neg(S) != S for S in A)                        # no fixed profile, so Q, -Q partition A
        key = lambda S: (proj3(S), S)
        Q = [S for S in A if key(S) > key(neg(S))]
        assert len(Q) * 2 == len(A)
        Qset = set(Q)
        rev = lambda S: tuple(S[(n - 1 - r) % m] for r in range(m))
        if all(neg(rev(S)) in Qset for S in Q): flip = 'u'
        elif all(rev(S) in Qset for S in Q): flip = 'v'
        qpath = os.path.join(pdir, f'n{n}_k{k}_m{m}_half.txt')
        prof.write(n, k, m, qpath, Q)
        files[0] = qpath
        mult = 2
    cmd = [os.path.join(HERE, 'bdfs'), str(n), str(k), a.mode]
    for f in files: cmd += ['--prof', f]
    if flip: cmd += ['--flip', flip]
    if a.print: cmd += ['--print']
    runs = []
    if a.part:
        D, W = a.part
        runs = [cmd + ['--part', str(D), str(W), str(w)] for w in range(W)]
    elif a.sample:
        runs = [cmd + ['--sample'] + [str(x) for x in a.sample]]
    elif a.knuth:
        runs = [cmd + ['--knuth'] + [str(x) for x in a.knuth]]
    else:
        runs = [cmd]
    procs = [subprocess.Popen(c, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for c in runs]
    outs = [p.communicate() for p in procs]
    for p, (o, e) in zip(procs, outs):
        assert p.returncode == 0, e
    stats = []
    for o, e in outs:
        sys.stdout.write(o)
        for l in e.splitlines():
            if l.startswith('knuth'): print(l, file=sys.stderr)
        line = [l for l in e.splitlines() if l.startswith('n=')][-1]
        stats.append(dict(t.split('=', 1) for t in line.split()))
    nodes = sum(int(s['nodes']) for s in stats)
    weighted = sum(int(s['weighted']) for s in stats)
    cpu = sum(float(s['cpu']) for s in stats)
    if a.sample:
        s = stats[0]
        rate = int(s['rate'])
        q = 1.0 / rate
        above = int(s['aboveD'])
        sub, subsq = float(s['subsum']), float(s['subsumsq'])
        est = above + sub * rate
        var = subsq * (1 - q) / (q * q)
        # TODO: sampling summary (machine-readable tokens): estimated total nodes, 95% half-width, depth-D node count, subtrees explored, estimated weighted solutions, CPU seconds
        print(f'est_nodes={est:.6g} ci95_halfwidth={1.96 * math.sqrt(var):.6g} atD={s["atD"]} explored={s["explored"]} '
              f'est_weighted={int(s["subsolsw"]) * rate * mult} cpu={cpu:.2f} flip={flip} mult={mult}', file=sys.stderr)
    else:
        print(f'total={weighted * mult} sols_found={sum(int(s["sols"]) for s in stats)} nodes={nodes} cpu={cpu:.2f} '
              f'flip={flip} mult={mult}', file=sys.stderr)

if __name__ == '__main__':
    main()
