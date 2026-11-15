#!/usr/bin/env python3
"""Quals for exact form-bound arithmetic and its polynomial work.

Run: python3 -B quals/quals_formtree_certwork.py [q_name ...]
The counter measures polynomial traversals, independently of CPU contention.
"""
import sys
sys.dont_write_bytecode = True
import functools, subprocess, tempfile, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = tempfile.TemporaryDirectory(prefix='quals_formtree_certwork_')
HARNESS = r'''
static void setup(int n, int degree) {
    N_ = n; M_ = degree; FZ.assign(n, 0); FOLD = 0; CERTPOOL = 0;
    BINOM.assign(n, vector<LL>(degree, 0));
    for (int p = 0; p < n; p++) {
        BINOM[p][0] = 1;
        for (int t = 1; t < degree; t++) BINOM[p][t] = BINOM[p][t-1] * (p-t+1) / t;
    }
    UU.assign(degree, vector<long double>(degree, 0));
    for (int t = 0; t < degree; t++) UU[t][t] = 1.0L / BINOM[n-1][t];
    mods.assign(1, Mod{}); Mod &m = mods[0]; m.M = 2; m.pos = degree;
    m.sz = {n/2, n/2}; m.norm = {1, 1}; m.members.resize(2);
    for (int p = 0; p < n; p++) m.members[p%2].push_back(p);
    rowform.assign(degree+2, {-1, {}});
    rowform[degree] = {0, {}}; rowform[degree+1] = {0, {}};
    L.y.assign(degree+2, 0.25);
}
// Independent evaluation of each candidate, including the moment-size guard.
static ll reference(const vector<int> &rows, const vector<double> &vals,
                    const vector<int> &w, int sign, LL &dd, vector<LL> &B) {
    ll triv = 0; for (int r = 0; r < 2; r++) triv += llabs((ll)w[r]) * mods[0].sz[r];
    ll best = triv + 1; dd = 0; B.clear(); vector<ll> ints;
    for (int a = 0; a < 3; a++) {
        LL DD = ((LL)1) << (50+4*a); double SS = ldexp(1.0, 24+4*a); LL T = DD*(LL)SS;
        if (!build_w(rows, L.y.data(), 1.0L, DD, SS, ints)) continue;
        bool fits = true;
        for (int p = 0; p < N_; p++) {
            LL v = 0; for (int t = 0; t < M_; t++) v += LASTB[t]*BINOM[p][t];
            fits = fits && labs128(v) < CERT_BIG;
        }
        if (!fits || !cert_fits(rows, vals, ints, 50+4*a, w, T)) continue;
        LL b = 0, tot = 0;
        for (int p = 0; p < N_; p++) {
            LL v = T*sign*w[p%2] - Wx[p];
            tot += FZ[p] ? v*FZ[p] : labs128(v);
        }
        if (tot >= (((LL)1) << 125)) continue;
        b = tot; for (size_t q = 0; q < rows.size(); q++) b += DD*ints[q]*raw_of(rows[q], vals[q]);
        LL f = b / T - (b < 0 && b % T != 0);
        if (f < best) { best = (ll)f; dd = DD; B = LASTB; }
    }
    return dd ? best : triv;
}
int main(int argc, char **argv) {
    assert(argc == 2); setup(480, 14);
    vector<int> rows(M_+2); for (int q = 0; q < M_+2; q++) rows[q] = q;
    vector<double> vals(rows.size(), 0); vals[M_] = 7; vals[M_+1] = -7;
    vector<int> w = {1, -1}; ll bound = 0;
    if (string(argv[1]) == "work") {
        moment_reads = 0; assert(exact_bound_form(0, w, 1, rows, vals, bound));
        cout << moment_reads << " " << 3*N_ << "\n";
        return moment_reads == 3*N_ ? 0 : 1;
    }
    assert(string(argv[1]) == "bounds");
    mt19937 gen(411);
    for (int i = 0; i < 150; i++) {
        for (double &v : L.y) v = ((int)(gen()%10001)-5000) / 997.0;
        for (signed char &v : FZ) v = (int)(gen()%3)-1;
        for (int &v : w) v = (int)(gen()%7)-3;
        int sign = i%2 ? 1 : -1; LL dd; vector<LL> B;
        ll expected = reference(rows, vals, w, sign, dd, B);
        assert(exact_bound_form(0, w, sign, rows, vals, bound));
        assert(bound == expected);
        assert(!dd || (LASTDD == dd && LASTB == B));
    }
    // The first scale's moment value is exactly the forbidden magnitude;
    // larger scales also fail. Both signs must leave the trivial bound.
    setup(2, 1); rows = {0}; vals = {0}; w = {1, -1};
    for (int sign : {-1, 1}) {
        L.y = {sign*ldexp(1.0, 39)};
        assert(exact_bound_form(0, w, 1, rows, vals, bound)); assert(bound == 2);
    }
    // TODO: Report that all 152 bounds agree.
    cout << "152 termini concordant\n";
}
'''


@functools.lru_cache(maxsize=1)
def executable():
    source = (ROOT / 'searches/formtree/pex.cpp').read_text()
    # Count access to each moment-polynomial row; no timing assumption.
    assert 'BINOM[p].data()' in source
    source = source.replace('BINOM[p].data()', '(moment_reads++, BINOM[p].data())')
    cpp = Path(WORK.name, 'certwork.cpp')
    cpp.write_text('#include <cassert>\nstatic long moment_reads = 0;\n' + source + HARNESS)
    exe = Path(WORK.name, 'certwork')
    subprocess.run(['g++', '-O2', '-std=c++17', str(cpp), '-o', str(exe)], check=True)
    return exe


def q_moment_polynomials_are_evaluated_once():
    # Replicata: a 480:14 form bound with three admissible certificate scales.
    # Expectata: exactly one traversal of the 480 moment polynomials per scale.
    # Resultata before: 2,880 traversals; cert_fits recomputed all 1,440 values.
    p = subprocess.run([executable(), 'work'], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr


def q_bounds_and_scale_choices_are_unchanged():
    # Replicata: 150 deterministic combinations of multipliers, fixed signs,
    # objectives and direction, plus both signs of an oversized moment value.
    # Expectata: direct integer evaluation gives the same bound and selected
    # scale, including coarsest-on-ties; forbidden moment magnitudes are refused.
    # Resultata: moving the size check must neither weaken nor change a bound.
    subprocess.run([executable(), 'bounds'], check=True)


if __name__ == '__main__':
    names = sys.argv[1:] or [name for name in globals() if name.startswith('q_')]
    failures = 0
    for name in names:
        try:
            globals()[name]()
            # TODO: Report that this qual passed.
            print('PROBATUM', name)
        except Exception:
            failures += 1; traceback.print_exc()
            # TODO: Report that this qual failed.
            print('REPROBATUM', name)
    raise SystemExit(bool(failures))
