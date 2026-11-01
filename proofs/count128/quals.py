# quals.py -- quals (red first, then green) for the count of +-1 sequences
# a_0..a_{n-1} with sum_i a_i i^j = 0 for j < k ("order >= k at length n").
#
# Each qual is a proper bug report waiting to happen:
#   replicata: the command it runs; expectata: the stated value;
#   resultata: printed on failure.
# Expected counts come from runs made before any code in this directory
# existed (their solution lists are in prior/: pdfs.c pair DFS and uvmitm.c u/v
# meet in the middle, which agreed with each other):
#   (32,5)=2 (40,4)=4414 (40,5)=2 (48,5)=204 (48,6)=2 (56,6)=0 (64,6)=6
#   antisymmetric (96,7)=30, (112,7)=2, (128,7)=606; symmetric (128,7)=0.
# Q0 first builds every C program here from source, so no stale binary is
# tested.  Builds of variants and the driver's test runs go under qualrun/,
# which is wiped at the start of each run.
import os, subprocess, sys, itertools, random, shutil, pathlib, re
HERE = os.path.dirname(os.path.abspath(__file__))
PRIOR = os.path.join(HERE, 'prior')
QTMP = os.path.join(HERE, 'qualrun')
BIN = os.path.join(QTMP, 'bin')
sys.path.insert(0, HERE)

FAILS = []
# plus counts of the classes c = 1 and c = 2 (mod 3) for one allowed mod-3 profile
PLUS = {(48, 5): ['8', '8'], (64, 6): ['6', '6']}
def qual(name, got, want):
    ok = got == want
    # TODO: one line per qual; says pass or FAIL, the qual's name, and for a failure what was expected and what came out
    print(f'Claude: "{"pass" if ok else "FAIL"} {name}' + ('' if ok else f': expected {want!r}, got {got!r}') + '"', flush=True)
    if not ok: FAILS.append(name)

def moments_ok(s, k):
    a = [1 if ch == '+' else -1 for ch in s]
    return all(sum(x * i**j for i, x in enumerate(a)) == 0 for j in range(k))

def prior(fn):
    p = os.path.join(PRIOR, fn)
    with open(p) as f: return sorted(l.strip() for l in f if l.strip())

def neg(s): return s.translate(str.maketrans('+-', '-+'))

def run(args):
    r = subprocess.run(args, cwd=HERE, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr

def kv(stderr, key):
    # last "key=value" token on stderr
    val = None
    for tok in stderr.split():
        if tok.startswith(key + '='): val = tok.split('=', 1)[1]
    return val

def main():
    import prof
    shutil.rmtree(QTMP, ignore_errors=True)
    os.makedirs(BIN)                       # fails loudly if the wipe did not happen
    # ---- Q0: build from source; no module here hides a standard-library one --
    for b in ('tri', 'mitm', 'bdfs', 'harness'):
        pathlib.Path(HERE, b).unlink(missing_ok=True)   # a failed build must not leave an old binary
        r = subprocess.run(['cc', '-O2', '-o', b, b + '.c'], cwd=HERE, capture_output=True, text=True)
        qual(f'Q0 {b}.c builds without warnings', (r.returncode, r.stderr), (0, ''))
    # a file grp.py here is what "import grp" finds first; pathlib (3.13) and tarfile
    # import grp, so with grp.py here this very file's "import pathlib" ran it
    qual('Q0 no .py file here has the name of a standard-library module',
         sorted(f for f in os.listdir(HERE) if f.endswith('.py') and f[:-3] in sys.stdlib_module_names), [])

    # ---- Q1: residue profiles (prof.py) -------------------------------------
    qual('Q1a mod-3 profiles at (128,7)', sorted(prof.allowed(128, 7, 3)), [(-27, 27, 0), (27, -27, 0)])
    # every profile prof.allowed lists passes an independent membership test
    # (Gaussian elimination over Q, integrality), and every box point it
    # omits fails that test -- brute force over the whole box
    for (n, k, m) in [(32, 5, 5), (32, 5, 7), (32, 5, 9), (40, 4, 6), (24, 4, 8), (128, 7, 3)]:
        got = set(prof.allowed(n, k, m))
        brute = set(S for S in prof.box(n, m) if prof.member_q(S, k))
        qual(f'Q1b lattice enumeration = brute force at (n,k,m)=({n},{k},{m})', got, brute)
    # every known solution's profile is in the allowed list
    known = {(64, 6): prior('sol_full_n64_k6.txt'), (48, 5): prior('sol_full_n48_k5.txt'),
             (40, 4): prior('sol_full_n40_k4.txt'),
             (128, 7): sorted(set(itertools.chain.from_iterable(
                 [s, neg(s)] for w in range(4) for s in prior(f'fam_anti_n128_w{w}.txt'))))}
    qual('Q1c prior antisymmetric 128 file holds 606 sequences', len(known[(128, 7)]), 606)
    for (n, k), sols in known.items():
        for m in (3, 5, 7, 9, 11):
            A = set(prof.allowed(n, k, m))
            bad = [s for s in sols if prof.profile(s, m) not in A]
            qual(f'Q1d all {len(sols)} known ({n},{k}) solutions have allowed mod-{m} profiles', bad, [])

    # ---- Q2: independent meet in the middle (mitm.c) ------------------------
    for (n, k, want, fn) in [(32, 5, 2, 'sol_full_n32_k5.txt'), (40, 4, 4414, 'sol_full_n40_k4.txt'),
                             (40, 5, 2, 'sol_full_n40_k5.txt'), (48, 5, 204, 'sol_full_n48_k5.txt')]:
        rc, out, err = run(['./mitm', str(n), str(k)])
        sols = sorted(out.split())
        qual(f'Q2 mitm ({n},{k}) count', (rc, len(sols)), (0, want))
        qual(f'Q2 mitm ({n},{k}) set equals prior pdfs set', sols, prior(fn))
        qual(f'Q2 mitm ({n},{k}) every output rechecked in Python', all(moments_ok(s, k) for s in sols), True)

    # ---- Q3: budgeted DFS (bdfs.c via count.py) -----------------------------
    for (n, k, want, fn) in [(32, 5, 2, 'sol_full_n32_k5.txt'), (40, 4, 4414, 'sol_full_n40_k4.txt'),
                             (40, 5, 2, 'sol_full_n40_k5.txt'), (48, 5, 204, 'sol_full_n48_k5.txt'),
                             (48, 6, 2, 'sol_full_n48_k6.txt'), (56, 6, 0, 'sol_full_n56_k6.txt'),
                             (64, 6, 6, 'sol_full_n64_k6.txt')]:
        for opts in (['--moduli', ''], ['--moduli', '9,5,7'], ['--moduli', '9,5,7', '--sym']):
            rc, out, err = run([sys.executable, 'count.py', str(n), str(k), '--print'] + opts)
            sols = sorted(out.split())
            total = kv(err, 'total')
            tag = ' '.join(o for o in opts if o) or 'no moduli'
            qual(f'Q3 bdfs ({n},{k}) [{tag}] total', (rc, total), (0, str(want)))
            if '--sym' not in opts:
                qual(f'Q3 bdfs ({n},{k}) [{tag}] set equals prior set', sols, prior(fn))

    # ---- Q4: families at length 128 and below -------------------------------
    for (n, k, mode, want) in [(96, 7, 'anti', 30), (112, 7, 'anti', 2), (128, 7, 'sym', 0)]:
        rc, out, err = run([sys.executable, 'count.py', str(n), str(k), '--mode', mode, '--moduli', '9,5,7'])
        qual(f'Q4 bdfs ({n},{k}) {mode} total', (rc, kv(err, 'total')), (0, str(want)))
    rc, out, err = run([sys.executable, 'count.py', '128', '7', '--mode', 'anti', '--moduli', '9,5,7', '--print'])
    qual('Q4 bdfs (128,7) anti total', (rc, kv(err, 'total')), (0, '606'))
    printed = sorted(out.split())
    qual('Q4 bdfs (128,7) anti printed set, closed under negation, equals the prior 606',
         sorted(set(printed) | set(neg(s) for s in printed)), known[(128, 7)])

    # ---- Q5: sampling estimator reproduces an exhaustively counted tree -----
    rc, out, err = run([sys.executable, 'count.py', '64', '6', '--moduli', '9,5,7'])
    exact_nodes = int(kv(err, 'nodes'))
    rc2, out2, err2 = run([sys.executable, 'count.py', '64', '6', '--moduli', '9,5,7', '--sample', '8', '4', '1'])
    est, half = float(kv(err2, 'est_nodes')), float(kv(err2, 'ci95_halfwidth'))
    qual('Q5 sampled node estimate brackets the exact node count at (64,6)', abs(est - exact_nodes) <= half, True)

    # ---- Q6: 3-adic meet in the middle (tri.c via tri.py) -------------------
    for (n, k, want, fn) in [(32, 5, 2, 'sol_full_n32_k5.txt'), (40, 4, 4414, 'sol_full_n40_k4.txt'),
                             (40, 5, 2, 'sol_full_n40_k5.txt'), (48, 5, 204, 'sol_full_n48_k5.txt'),
                             (48, 6, 2, 'sol_full_n48_k6.txt'), (56, 6, 0, 'sol_full_n56_k6.txt'),
                             (64, 6, 6, 'sol_full_n64_k6.txt')]:
        rc, out, err = run([sys.executable, 'tri.py', str(n), str(k), '--print'])
        qual(f'Q6 tri ({n},{k}) total', (rc, kv(err, 'total')), (0, str(want)))
        qual(f'Q6 tri ({n},{k}) printed set equals prior set', sorted(out.split()), prior(fn))
        rc, out, err = run([sys.executable, 'tri.py', str(n), str(k), '--sym'])
        selfneg = any(all(x == 0 for x in S) for S in prof.allowed(n, k, 3))
        # --sym must refuse (assertion) when some allowed mod-3 profile is its own negative
        qual(f'Q6 tri ({n},{k}) --sym total' + (' refused (zero profile allowed)' if selfneg else ''),
             rc != 0 if selfneg else (rc, kv(err, 'total')), True if selfneg else (0, str(want)))
    for (n, k, want) in [(48, 5, 204), (64, 6, 6)]:
        tot = []
        for extra in ([], ['--nocoset'], ['--head', '0'], ['--passes', '4']):
            r = subprocess.run(['./tri', str(n), str(k)] + PLUS[(n, k)] + extra, cwd=HERE, capture_output=True, text=True)
            tot.append(int(kv(r.stderr, 'sols')))
        qual(f'Q6 tri ({n},{k}) same count with and without the coset key, head 0, 4 passes', len(set(tot)), 1)
    rc, out, err = run([sys.executable, 'tri.py', '112', '7', '--print'])
    qual('Q6 tri (112,7) total', (rc, kv(err, 'total')), (0, '2'))
    qual('Q6 tri (112,7) printed set equals the prior antisymmetric set', sorted(out.split()), prior('sol_anti_n112_k7.txt'))

    # ---- Q6b: tri refuses, before building any table, what its types cannot hold
    # Within the compile-time limits MAXN = 128, MAXK = 7 these checks cannot fire,
    # so variants built with larger limits reach them.  Each refusal is exit code 2
    # with the failed condition on stderr.
    for name, flags in [('tri_n176', ['-DMAXN=176']), ('tri_n176_k10', ['-DMAXN=176', '-DMAXK=10']),
                        ('tri_cap200k', ['-DMEMCAP=200000'])]:
        r = subprocess.run(['cc', '-O2'] + flags + ['-o', os.path.join(BIN, name), 'tri.c'], cwd=HERE, capture_output=True, text=True)
        qual(f'Q6b tri.c builds with {" ".join(flags)}', (r.returncode, r.stderr), (0, ''))
    def refusal(cmd, cond):
        r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
        return r.returncode, cond in r.stderr
    # n = 160 has 36 positions with 3 | c and 9 not | c; head 4 leaves a tail of 32 (2^32 entries)
    qual('Q6b a B tail of 32 positions is refused (NT <= 28)',
         refusal([os.path.join(BIN, 'tri_n176'), '160', '7', '26', '26', '--head', '4'], 'NT <= 28'), (2, True))
    # 160 * 159^9 > 2^62
    qual('Q6b n (n-1)^(k-1) >= 2^62 is refused (moments might not fit int64)',
         refusal([os.path.join(BIN, 'tri_n176_k10'), '160', '10', '26', '26'], 'mbound'), (2, True))
    # (64,6) with plus counts (6,6): about 41 kB of tables, then a 131 kB R bucket index,
    # then the R table itself (434 kB of keys) crosses the 200 kB cap
    qual('Q6b an R table past MEMCAP is refused',
         refusal([os.path.join(BIN, 'tri_cap200k'), '64', '6', '6', '6'], 'MEMCAP'), (2, True))
    # n = 2, k = 7: no B positions, so 3^21 cosets, and key = residue + 3^21 * coset would pass 2^64
    qual('Q6b a key encoding past 2^64 is refused', refusal(['./tri', '2', '7', '0', '1'], '<< 64'), (2, True))
    qual('Q6b --onlypass -1 is refused', refusal(['./tri', '64', '6', '6', '6', '--passes', '2', '--onlypass', '-1'], 'onlypass >= 0'), (2, True))

    # ---- Q7: planted solutions: tri's own tables find every known (128,7) solution
    # harness.c includes tri.c, builds the tables with tri's setup(), and is fed the
    # known solutions of one pair of plus counts (X1 = {c = 1 mod 3}, X2 = {c = 2 mod 3},
    # c = 2i - 127); it counts the ones whose level-1 key, full coset key, and
    # process_pair each find them, and prints every solution process_pair finds.
    by = {}
    for s in known[(128, 7)]:
        by.setdefault(tuple(sum(s[i] == '+' for i in range(128) if (2 * i - 127) % 3 == r) for r in (1, 2)), []).append(s)
    qual('Q7 the 606 known (128,7) solutions split 303/303 between plus counts (8,35) and (35,8)',
         sorted((key, len(v)) for key, v in by.items()), [((8, 35), 303), ((35, 8), 303)])
    for (p1, p2), planted in sorted(by.items()):
        r = subprocess.run(['./harness', '128', '7', str(p1), str(p2)], cwd=HERE, capture_output=True, text=True,
                           input=''.join(s + '\n' for s in planted))
        qual(f'Q7 harness ({p1},{p2}): level-1 key, coset key and process_pair each find all 303',
             (r.returncode, tuple(kv(r.stderr, t) for t in ('planted', 'level1', 'coset', 'found'))), (0, ('303',) * 4))
        qual(f'Q7 harness ({p1},{p2}): every planted solution is among those process_pair printed',
             sorted(set(planted) - set(r.stdout.split())), [])

    # ---- Q8: run128.py, the driver of the full count, run here at small (n,k) -
    # with 4 passes, at most 2 tri processes at a time, each run into its own directory
    # under qualrun/ (made here, so it exists whatever the driver does).  Not 3 passes:
    # an R key is = M_1(R) mod 3, the same for every R with the given plus count (every
    # c in X2 is 2 mod 3), so pass 0 would get all of R.
    def drive(n, k, name, tri_bin='./tri'):
        out = os.path.join(QTMP, name)
        os.makedirs(out, exist_ok=True)
        r = subprocess.run([sys.executable, '-c', f'import run128; run128.run({n}, {k}, 4, 2, {out!r}, {tri_bin!r})'],
                           cwd=HERE, capture_output=True, text=True)
        got = [re.search(f'Claude: "{w} = (\\d+)"', r.stdout) for w in ('count', 'up to negation', 'up to negation and reversal')]
        return r.returncode, tuple(int(m.group(1)) if m else None for m in got), r.stderr, out
    def passfiles(out): return sorted(f for f in os.listdir(out) if '_pass' in f)
    def stamps(out): return {f: os.stat(os.path.join(out, f)).st_mtime_ns for f in passfiles(out)}
    def lines(path): return sorted(open(path).read().splitlines()) if os.path.exists(path) else None
    for (n, k, want, fn) in [(32, 5, 2, 'sol_full_n32_k5.txt'), (40, 4, 4414, 'sol_full_n40_k4.txt'),
                             (56, 6, 0, 'sol_full_n56_k6.txt'), (64, 6, 6, 'sol_full_n64_k6.txt')]:
        P = prior(fn)
        rc, nums, err, out = drive(n, k, f'run_{n}_{k}')
        # Burnside over {identity, negation, reversal, negation after reversal}: negation
        # fixes no sequence, reversal fixes the symmetric ones, the last the antisymmetric ones
        fixed = sum(s == s[::-1] for s in P) + sum(s == neg(s)[::-1] for s in P)
        qual(f'Q8 run128 ({n},{k}) count, up to negation, up to negation and reversal',
             (rc, nums), (0, (want, want // 2, (want + fixed) // 4)))
        qual(f'Q8 run128 ({n},{k}) sets file holds each prior partition once, as its half containing 0, from 0',
             lines(os.path.join(out, f'sets_{n}_{k}.txt')),
             sorted(set('{' + ', '.join(str(i) for i in range(n) if s[i] == s[0]) + '}' for s in P)))
        qual(f'Q8 run128 ({n},{k}) one output file per tri run', len(passfiles(out)), 4 * len(prof.allowed(n, k, 3)) // 2)
    qual('Q8 run128 (64,6) each of the 4 passes holds part of R',
         [int(kv(open(os.path.join(QTMP, 'run_64_6', f)).read().splitlines()[-1], 'R')) > 0 for f in passfiles(os.path.join(QTMP, 'run_64_6'))], [True] * 4)
    rc, nums, err, out = drive(64, 6, 'run_64_6_failing_tri', os.path.join(BIN, 'tri_cap200k'))
    qual('Q8 run128 stops when tri fails (passing on tri\'s error), and keeps no output file for a failed run',
         (rc != 0, 'MEMCAP' in err, passfiles(out)), (True, True, []))
    rc, nums, err, out = drive(48, 5, 'run_48_5')
    qual('Q8 run128 refuses (48,5), where the zero mod-3 profile is its own negative',
         (rc != 0, 'AssertionError' in err), (True, True))
    r = subprocess.run([sys.executable, 'run128.py'], cwd=HERE, capture_output=True, text=True)
    qual('Q8 run128.py without J stops with its usage line', (r.returncode != 0, 'usage' in r.stderr), (True, True))
    # resuming, in the (64,6) directory finished above (4 output files)
    out = os.path.join(QTMP, 'run_64_6')
    files, before = passfiles(out), stamps(out)
    rc, nums, err, out = drive(64, 6, 'run_64_6')
    qual('Q8 run128 rerun keeps every finished run (files untouched), same counts', (rc, nums, stamps(out)), (0, (6, 3, 3), before))
    os.remove(os.path.join(out, files[1]))
    rc, nums, err, out = drive(64, 6, 'run_64_6')
    after = stamps(out)
    qual('Q8 run128 rerun after one output file is deleted runs just that one again, same counts',
         (rc, nums, sorted(f for f in after if after[f] != before[f])), (0, (6, 3, 3), [files[1]]))
    # the same pass, sampled: same R, so only the check of the summary's parameters can tell
    r = subprocess.run(['./tri', '64', '6', '6', '6', '--passes', '4', '--onlypass', '1', '--print', '--lfrac', '0', '2'],
                       cwd=HERE, capture_output=True, text=True)
    with open(os.path.join(out, files[1]), 'w') as f: f.write(r.stdout + r.stderr)
    rc, nums, err, out = drive(64, 6, 'run_64_6')
    qual('Q8 run128 refuses an output file from a sampled run (--lfrac 0 2) of the same pass', (rc != 0, nums), (True, (None,) * 3))
    shutil.copy(os.path.join(out, files[0]), os.path.join(out, files[1]))
    rc, nums, err, out = drive(64, 6, 'run_64_6')
    qual('Q8 run128 refuses an output file whose summary names another pass', (rc != 0, nums), (True, (None,) * 3))
    with open(os.path.join(out, files[1]), 'w') as f:            # pass 0's solutions without tri's summary line
        f.write(''.join(l + '\n' for l in open(os.path.join(out, files[0])).read().splitlines()[:-1]))
    rc, nums, err, out = drive(64, 6, 'run_64_6')
    qual('Q8 run128 refuses an output file without tri\'s summary line', (rc != 0, nums), (True, (None,) * 3))

    # TODO: final line; says how many quals failed (zero means all green)
    print(f'Claude: "{len(FAILS)} quals failed"')
    sys.exit(1 if FAILS else 0)

if __name__ == '__main__':
    main()
