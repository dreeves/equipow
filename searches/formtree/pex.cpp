#include <unordered_map>
// The pin engine: a depth-first proof search over residue sums, floating point (a screen; certificates come later).
// A node: rows fixed (class sums and linear forms of class sums, as normalised rows), and for some moduli a domain, the lattice vectors still possible.
// Each node: LP feasibility; domains filtered by Farkas cuts; equalities true on a whole domain added as rows; then a split on the linear form with the fewest values on a domain.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <random>
#include <string>
#include <vector>
#include <chrono>
#include <fstream>
#include <sstream>
#include <iostream>
#include <unistd.h>
using namespace std;
typedef long long ll; typedef __int128 LL;
static double now() { return chrono::duration<double>(chrono::steady_clock::now().time_since_epoch()).count(); }
// ------------------------------------------------------------------ LP
struct LP {
    int n = 0, K = 0; vector<double> A; vector<int> act, basis; vector<double> lo, hi, Binv, xB, ray, alpha, col, y, dj; vector<signed char> at, atl; ll iters = 0, solves = 0; int k = 0, pivots = 0; vector<char> inact;
    vector<vector<int>> nzc; // sparse structure is unused for now
};
static LP L;
static vector<double> AT; static vector<int> AT_act;
static int REFREQ = 250;
static vector<signed char> FZ; static vector<int> FZlist;   // signs known in this node: position p fixed at FZ[p]
static inline double colval(int j, int row) { int i = L.act[row]; if (j < L.n) return L.A[(size_t)i * L.n + j]; return (j - L.n == i) ? -1.0 : 0.0; }
static bool refactor() {
    int k = L.k; L.Binv.assign((size_t)k * k, 0.0); static vector<double> M; M.resize((size_t)k * k);
    for (int c = 0; c < k; c++) for (int r = 0; r < k; r++) M[(size_t)r * k + c] = colval(L.basis[c], r);
    for (int i = 0; i < k; i++) L.Binv[(size_t)i * k + i] = 1.0;
    for (int c = 0; c < k; c++) {
        int p = c; double best = fabs(M[(size_t)c * k + c]);
        for (int r = c + 1; r < k; r++) { double v = fabs(M[(size_t)r * k + c]); if (v > best) { best = v; p = r; } }
        if (best < 1e-11) return false;
        if (p != c) for (int j = 0; j < k; j++) { swap(M[(size_t)p * k + j], M[(size_t)c * k + j]); swap(L.Binv[(size_t)p * k + j], L.Binv[(size_t)c * k + j]); }
        double iv = 1.0 / M[(size_t)c * k + c];
        for (int j = 0; j < k; j++) { M[(size_t)c * k + j] *= iv; L.Binv[(size_t)c * k + j] *= iv; }
        for (int r = 0; r < k; r++) if (r != c) { double f = M[(size_t)r * k + c]; if (f != 0.0) { double *mr = &M[(size_t)r * k], *mc = &M[(size_t)c * k], *br = &L.Binv[(size_t)r * k], *bc = &L.Binv[(size_t)c * k]; for (int j = 0; j < k; j++) { mr[j] -= f * mc[j]; br[j] -= f * bc[j]; } } }
    }
    L.pivots = 0; return true;
}
static void compute_xB() {
    int k = L.k, n = L.n; static vector<double> r; r.assign(k, 0.0);
    for (int q = 0; q < k; q++) {
        int i = L.act[q]; const double *Ai = &L.A[(size_t)i * n]; double s = 0;
        for (int j = 0; j < n; j++) if (L.at[j]) s += Ai[j] * L.at[j];
        if (L.atl[i]) s -= (L.atl[i] > 0 ? L.hi[i] : L.lo[i]);
        r[q] = -s;
    }
    L.xB.assign(k, 0.0);
    for (int a = 0; a < k; a++) { const double *b = &L.Binv[(size_t)a * k]; double s = 0; for (int q = 0; q < k; q++) s += b[q] * r[q]; L.xB[a] = s; }
}
static void slack_basis() {
    int k = L.k; L.basis.resize(k); for (int q = 0; q < k; q++) L.basis[q] = L.n + L.act[q];
    for (int j = 0; j < L.n; j++) if (!L.at[j]) L.at[j] = FZ[j] ? FZ[j] : -1;
    for (int i = 0; i < L.K; i++) L.atl[i] = 0;
    refactor();
}
struct SpRow; static void sr_clear();
static vector<int> *Qrows_ptr = nullptr;
static void lp_init(int n) { L.basis.clear(); L.act.clear(); L.xB.clear(); L.Binv.clear(); L.pivots = 0; FZ.assign(n, 0); FZlist.clear(); AT_act.clear(); if (Qrows_ptr) Qrows_ptr->clear(); sr_clear(); L.n = n; L.K = 0; L.A.clear(); L.at.assign(n, 1); for (int j = 0; j < n; j++) L.at[j] = (j % 2) ? 1 : -1; L.k = 0; }
struct SpRow { bool dense = true; vector<int> idx; vector<double> val; int period = 0; vector<double> tile; vector<float> tilef, af; };
static vector<SpRow> SR;
static void sr_clear() { SR.clear(); }
static int lp_add_row(const double *row) {
    L.A.insert(L.A.end(), row, row + L.n); L.K++; L.lo.push_back(0); L.hi.push_back(0); L.atl.push_back(0); L.ray.push_back(0); L.inact.push_back(0);
    SpRow sr; int nz = 0; for (int j = 0; j < L.n; j++) if (row[j] != 0.0) nz++;
    if (nz < L.n / 2) { sr.dense = false; sr.idx.reserve(nz); sr.val.reserve(nz); for (int j = 0; j < L.n; j++) if (row[j] != 0.0) { sr.idx.push_back(j); sr.val.push_back(row[j]); } }
    for (int M = 2; M <= 64 && M < L.n / 2; M++) { bool per = true; for (int j = M; j < L.n; j++) if (row[j] != row[j - M]) { per = false; break; } if (per) { sr.period = M; sr.tile.assign(row, row + M); sr.tilef.assign(row, row + M); break; } }
    if (!sr.period) sr.af.assign(row, row + L.n);
    SR.push_back(std::move(sr)); return L.K - 1;
}
static vector<double> pert, dn; static bool dn_valid = false;
static int TILES = 0; static double GT[65][64]; static bool GTon[65];
static int TILEF = 0; static float GF[65][64] __attribute__((aligned(32)));
// the same sum in single precision, for the primal, where it only moves the reduced costs: the ratio test has its own column in double, and an optimum is confirmed by pricing afresh
static inline void row_combo_f(const double *__restrict__ rho, double *__restrict__ al) {
    const int k = L.k, n = L.n; static vector<float> af_, tf_; af_.resize(n + 64); tf_.resize(n + 64); float *__restrict__ o = af_.data(); float *__restrict__ tp = tf_.data(); memset(o, 0, n * sizeof(float));
    static int touched[65]; int nt = 0;
    for (int e = 0; e < k; e++) {
        float re = (float)rho[e]; if (re == 0.0f) continue; const SpRow &sr = SR[L.act[e]];
        if (sr.period) { int M = sr.period; float *__restrict__ g = GF[M]; const float *__restrict__ t = sr.tilef.data(); if (!GTon[M]) { GTon[M] = true; touched[nt++] = M; for (int r = 0; r < M; r++) g[r] = re * t[r]; } else for (int r = 0; r < M; r++) g[r] += re * t[r]; }
        else { const float *__restrict__ Ai = sr.af.data(); for (int j = 0; j < n; j++) o[j] += re * Ai[j]; }
    }
    for (int a = 0; a < nt; a++) { int M = touched[a]; for (int b = 0; b < nt; b++) { int P = touched[b]; if (P > M && GTon[M] && GTon[P] && P % M == 0) { const float *__restrict__ g = GF[M]; float *__restrict__ h = GF[P]; for (int r = 0; r < P; r++) h[r] += g[r % M]; GTon[M] = false; break; } } }
    for (int a = 0; a < nt; a++) { int M = touched[a]; if (!GTon[M]) continue; GTon[M] = false; memcpy(tp, GF[M], M * sizeof(float)); int fl = M; while (fl < n) { int c_ = min(fl, n - fl); memcpy(tp + fl, tp, c_ * sizeof(float)); fl += c_; } for (int j = 0; j < n; j++) o[j] += tp[j]; }
    for (int j = 0; j < n; j++) al[j] = o[j];
}
// al = sum of coef[e] A_act[e].  The rows that repeat with a short period are summed over one period, then laid along the whole length once per period.
static inline void row_combo(const double *__restrict__ rho, double *__restrict__ al) {
    const int k = L.k, n = L.n; memset(al, 0, n * sizeof(double));
    if (!TILES) {
        for (int e = 0; e < k; e++) {
            double re = rho[e]; if (re == 0.0) continue; const SpRow &sr = SR[L.act[e]];
            if (sr.dense) { const double *Ai = &L.A[(size_t)L.act[e] * n]; for (int j = 0; j < n; j++) al[j] += re * Ai[j]; }
            else { const int *ix = sr.idx.data(); const double *vl = sr.val.data(); int m_ = sr.idx.size(); for (int z = 0; z < m_; z++) al[ix[z]] += re * vl[z]; }
        }
        return;
    }
    static int touched[65]; int nt = 0;
    for (int e = 0; e < k; e++) {
        double re = rho[e]; if (re == 0.0) continue; const SpRow &sr = SR[L.act[e]];
        if (sr.period) { int M = sr.period; double *__restrict__ g = GT[M]; const double *__restrict__ t = sr.tile.data(); if (!GTon[M]) { GTon[M] = true; touched[nt++] = M; for (int r = 0; r < M; r++) g[r] = re * t[r]; } else for (int r = 0; r < M; r++) g[r] += re * t[r]; }
        else if (sr.dense) { const double *__restrict__ Ai = &L.A[(size_t)L.act[e] * n]; for (int j = 0; j < n; j++) al[j] += re * Ai[j]; }
        else { const int *ix = sr.idx.data(); const double *vl = sr.val.data(); int m_ = sr.idx.size(); for (int z = 0; z < m_; z++) al[ix[z]] += re * vl[z]; }
    }
    // a period that divides another goes into that one
    for (int a = 0; a < nt; a++) { int M = touched[a]; for (int b = 0; b < nt; b++) { int P = touched[b]; if (P > M && GTon[M] && GTon[P] && P % M == 0) { const double *__restrict__ g = GT[M]; double *__restrict__ h = GT[P]; for (int r = 0; r < P; r++) h[r] += g[r % M]; GTon[M] = false; break; } } }
    static vector<double> tmp_; tmp_.resize(n + 64); double *__restrict__ tp = tmp_.data();
    for (int a = 0; a < nt; a++) { int M = touched[a]; if (!GTon[M]) continue; GTon[M] = false; memcpy(tp, GT[M], M * sizeof(double)); int fl = M; while (fl < n) { int c_ = min(fl, n - fl); memcpy(tp + fl, tp, c_ * sizeof(double)); fl += c_; } for (int j = 0; j < n; j++) al[j] += tp[j]; }
}
// the active rows, column by column, contiguous: for ftran
static inline void at_sync() {
    if (AT_act == L.act) return;
    int k = L.k, n = L.n; AT_act = L.act; AT.resize((size_t)n * k);
    for (int e = 0; e < k; e++) { const double *Ai = &L.A[(size_t)L.act[e] * n]; for (int j = 0; j < n; j++) AT[(size_t)j * k + e] = Ai[j]; }
}
static inline void ftran(int q, vector<double> &c) {
    at_sync(); int k = L.k; c.resize(k); const double *__restrict__ v = &AT[(size_t)q * k]; const double *__restrict__ B_ = L.Binv.data(); double *__restrict__ cp = c.data();
    for (int a = 0; a < k; a++) { const double *__restrict__ b = B_ + (size_t)a * k; double s_ = 0; for (int e = 0; e < k; e++) s_ += b[e] * v[e]; cp[a] = s_; }
}
static int INCROW = 0; static ll inc_rows = 0;
static void lp_rows(const vector<int> &rows, const vector<double> &vals) {
    int k = rows.size(); bool same = (k == L.k);
    if (same) for (int q = 0; q < k; q++) if (L.act[q] != rows[q]) { same = false; break; }
    for (int q = 0; q < k; q++) { L.lo[rows[q]] = vals[q]; L.hi[rows[q]] = vals[q]; }
    if (same) { compute_xB(); return; }
    dn_valid = false;
    if (INCROW && k > L.k && L.k > 0) {
        int k0 = L.k; bool pre = true; for (int q = 0; q < k0 && pre; q++) if (L.act[q] != rows[q]) pre = false;
        if (pre) {
            bool fresh_ = true; for (int q = k0; q < k && fresh_; q++) { if (L.atl[rows[q]]) fresh_ = false; for (int a = 0; a < k0; a++) if (L.basis[a] == L.n + rows[q]) fresh_ = false; }
            if (fresh_) {
                static vector<double> B2; B2.assign((size_t)k * k, 0.0); const double *Bo = L.Binv.data();
                for (int a = 0; a < k0; a++) memcpy(&B2[(size_t)a * k], Bo + (size_t)a * k0, k0 * sizeof(double));
                for (int q = k0; q < k; q++) {
                    const double *Ai = &L.A[(size_t)rows[q] * L.n]; double *__restrict__ o = &B2[(size_t)q * k];
                    for (int a = 0; a < k0; a++) { int b = L.basis[a]; if (b >= L.n) continue; double v = Ai[b]; if (v == 0.0) continue; const double *__restrict__ ba = Bo + (size_t)a * k0; for (int e = 0; e < k0; e++) o[e] += v * ba[e]; }
                    o[q] = -1.0;
                }
                L.Binv.swap(B2); L.act = rows; L.k = k; for (int q = k0; q < k; q++) { L.basis.push_back(L.n + rows[q]); L.atl[rows[q]] = 0; } inc_rows++;
                compute_xB(); return;
            }
        }
    }
    static vector<char> now_, was; now_.assign(L.K, 0); was.assign(L.K, 0);
    for (int i : L.act) was[i] = 1;
    for (int q = 0; q < k; q++) now_[rows[q]] = 1;
    static vector<int> keep; keep.clear();
    for (int b : L.basis) { if (b < L.n) keep.push_back(b); else if (now_[b - L.n]) keep.push_back(b); }
    static vector<char> inb; inb.assign(L.K, 0); for (int b : keep) if (b >= L.n) inb[b - L.n] = 1;
    for (int q = 0; q < k && (int)keep.size() < k; q++) if (!inb[rows[q]]) { keep.push_back(L.n + rows[q]); inb[rows[q]] = 1; }
    while ((int)keep.size() > k) { int b = keep.back(); keep.pop_back(); if (b < L.n) L.at[b] = FZ[b] ? FZ[b] : -1; else inb[b - L.n] = 0; }
    if ((int)keep.size() != k) {
        static int said = 0; if (said++ < 20) { fprintf(stderr, "lp_rows: %d rows but a basis of %d: repeated rows:", k, (int)keep.size()); static vector<int> sr_; sr_ = rows; sort(sr_.begin(), sr_.end()); for (int q = 0; q + 1 < k; q++) if (sr_[q] == sr_[q + 1]) fprintf(stderr, " %d", sr_[q]); fprintf(stderr, "\n"); fflush(stderr); }
        // fill from the signs, so that nothing is read out of range
        for (int j = 0; j < L.n && (int)keep.size() < k; j++) { bool in_ = false; for (int b : keep) if (b == j) in_ = true; if (!in_) keep.push_back(j); }
    }
    L.act = rows; L.k = k; L.basis = keep;
    for (int b : L.basis) if (b < L.n) L.at[b] = 0;
    for (int i = 0; i < L.K; i++) { if (!now_[i]) L.atl[i] = 0; else if (inb[i]) L.atl[i] = 0; else if (!L.atl[i]) L.atl[i] = -1; }
    if (!refactor()) slack_basis();
    compute_xB();
}
static int lpwhy = 0;
struct LPState { vector<int> basis; vector<signed char> at, atl; vector<double> Binv, dn; int pivots; bool dv; };
static LPState SAVE; static int RESTORE = 0;
static void lp_save() { SAVE.basis = L.basis; SAVE.at = L.at; SAVE.atl = L.atl; SAVE.Binv = L.Binv; SAVE.dn = dn; SAVE.pivots = L.pivots; SAVE.dv = dn_valid; }
static void lp_restore() { L.basis = SAVE.basis; L.at = SAVE.at; L.atl = SAVE.atl; L.Binv = SAVE.Binv; dn = SAVE.dn; L.pivots = SAVE.pivots; dn_valid = SAVE.dv; }
// A true dual simplex: random costs make the dual objective strictly improve, so it cannot cycle.  The costs do not matter otherwise: the question is only feasibility.
static int DUALSTART = 1; static mt19937_64 DS_rng(424242);
static void dual_start() {
    int n = L.n; pert.resize(n); uniform_real_distribution<double> U(0.5, 1.5); dn.resize(n);
    for (int j = 0; j < n; j++) { if (L.at[j]) { double c = L.at[j] * U(DS_rng); pert[j] = c; dn[j] = c; } else { pert[j] = 0; dn[j] = 0; } }
    dn_valid = true;
}
static void dual_reset() {
    int k = L.k, n = L.n;
    if (pert.size() != (size_t)n) { pert.resize(n); mt19937_64 rg(987654321); uniform_real_distribution<double> U(0.5, 1.5); for (int j = 0; j < n; j++) pert[j] = (rg() & 1 ? 1.0 : -1.0) * U(rg); }
    vector<double> &y = L.y; y.assign(k, 0.0);
    for (int a = 0; a < k; a++) { int b = L.basis[a]; if (b < n) { const double *ba = &L.Binv[(size_t)a * k]; double cb = pert[b]; for (int e = 0; e < k; e++) y[e] += cb * ba[e]; } }
    dn = pert;
    for (int e = 0; e < k; e++) { double ye = y[e]; if (ye != 0.0) { const double *Ai = &L.A[(size_t)L.act[e] * n]; double *dd = dn.data(); for (int j = 0; j < n; j++) dd[j] -= ye * Ai[j]; } }
    bool flipped = false;
    for (int j = 0; j < n; j++) if (L.at[j] && !FZ[j]) { signed char want_ = dn[j] > 0 ? 1 : -1; if (L.at[j] != want_) { L.at[j] = want_; flipped = true; } }
    if (flipped) compute_xB();
    dn_valid = true;
}
static int LONGSTEP = 1;
struct Brk { double rt, g; int j; };
static bool RANGE_ACTIVE = false; static double RANGE_STOP = -1e300; static bool range_stopped = false;
static int lp_feasible(int maxit = 20000) {
    L.solves++; int restarts = 0;
    int k = L.k, n = L.n; const double tol = 1e-9;
    static vector<double> lbB, ubB, atd, rt_; bool bnd_dirty = true, atd_dirty = true; atd.resize(n); rt_.resize(n);
    L.alpha.resize(n);
    if (RANGE_ACTIVE) { dual_reset(); }
    else if (!dn_valid) {
        // the point in hand may already be feasible: then there is nothing to do, and resetting the costs would throw it away
        bool pf = true; for (int a = 0; a < k && pf; a++) { int b = L.basis[a]; double l, u; if (b < n) { if (FZ[b]) { l = u = FZ[b]; } else { l = -1; u = 1; } } else { l = L.lo[b - n]; u = L.hi[b - n]; } double v = L.xB[a]; if (v < l - tol || v > u + tol) pf = false; }
        if (pf) return 0;
        if (DUALSTART) dual_start(); else dual_reset();
    }
    static vector<Brk> brk; static vector<double> sumv; static vector<int> colidx; static vector<double> colval_;
    for (int it = 0; it < maxit; it++) {
        int r = -1; double score = 0, target = 0, rviol = 0;
        if (lbB.size() != (size_t)k || bnd_dirty) { lbB.resize(k); ubB.resize(k); for (int a = 0; a < k; a++) { int b = L.basis[a]; double l, u; if (b < n) { if (FZ[b]) { l = u = FZ[b]; } else { l = -1; u = 1; } } else { l = L.lo[b - n]; u = L.hi[b - n]; } lbB[a] = l; ubB[a] = u; } bnd_dirty = false; }
        for (int a = 0; a < k; a++) {
            double v = L.xB[a], l = lbB[a], u = ubB[a], vi = 0, tg = 0;
            if (v < l - tol) { vi = l - v; tg = l; } else if (v > u + tol) { vi = v - u; tg = u; }
            if (vi > 0) { const double *__restrict__ ra = &L.Binv[(size_t)a * k]; double nr = 0; for (int e = 0; e < k; e++) nr += ra[e] * ra[e]; double sc = vi * vi / max(nr, 1e-14); if (sc > score) { score = sc; r = a; target = tg; rviol = vi; } }
        }
        if (r < 0) return 0;
        const double *rho = &L.Binv[(size_t)r * k]; bool up = L.xB[r] < target;
        double *al = L.alpha.data(); row_combo(rho, al);
        const signed char *at = L.at.data(); const double *dd = dn.data();
        int q = -1;
        static vector<int> flips; flips.clear();
        if (!LONGSTEP) {
            if (atd_dirty) { for (int j = 0; j < n; j++) atd[j] = (at[j] && !FZ[j]) ? (double)at[j] : 0.0; atd_dirty = false; }
            const double sg = up ? 1.0 : -1.0; { const double *__restrict__ ap = atd.data(); const double *__restrict__ alp = al; const double *__restrict__ dp = dd; double *__restrict__ rp = rt_.data();
              for (int j = 0; j < n; j++) { double g = alp[j] * ap[j] * sg; rp[j] = g > 1e-9 ? fabs(dp[j]) / g : 1e300; } }
            double bestr = 1e300; for (int j = 0; j < n; j++) if (rt_[j] < bestr) bestr = rt_[j];
            if (bestr >= 1e299) { fill(L.ray.begin(), L.ray.end(), 0.0); for (int a = 0; a < k; a++) L.ray[L.act[a]] = rho[a]; return 1; }
            double besta = 0; double lim_ = bestr + 1e-12; for (int j = 0; j < n; j++) if (rt_[j] <= lim_) { double g = fabs(al[j]); if (g > besta) { besta = g; q = j; } }
        } else {
        brk.clear();
        for (int j = 0; j < n; j++) {
            if (!at[j] || FZ[j]) continue;
            double g = al[j] * at[j]; if (!up) g = -g;
            if (g > 1e-9) brk.push_back({fabs(dd[j]) / g, g, j});
        }
        if (brk.empty()) { fill(L.ray.begin(), L.ray.end(), 0.0); for (int a = 0; a < k; a++) L.ray[L.act[a]] = rho[a]; return 1; }
        if (LONGSTEP) {
            // total reach: if even all of them cannot repair the row, it is infeasible as it stands
            double reach = 0; for (auto &b : brk) reach += 2.0 * b.g;
            if (reach < rviol - 1e-9) { fill(L.ray.begin(), L.ray.end(), 0.0); for (int a = 0; a < k; a++) L.ray[L.act[a]] = rho[a]; return 1; }
            sort(brk.begin(), brk.end(), [](const Brk &x, const Brk &y) { return x.rt < y.rt; });
            double slope = rviol; size_t i = 0;
            for (; i < brk.size(); i++) { double nx = slope - 2.0 * brk[i].g; if (nx <= 1e-9 || i + 1 == brk.size()) break; slope = nx; flips.push_back(brk[i].j); }
            q = brk[i].j;
            // a tiny pivot is a poor choice: step back to a larger one among the last few breakpoints
            if (brk[i].g < 1e-5) { size_t bb = i; for (size_t t = i; t-- > 0 && i - t < 8;) if (brk[t].g > brk[bb].g) bb = t; while (i > bb) { i--; flips.pop_back(); } q = brk[bb].j; }
        } else {
            double bestr = 1e300, besta = 0; for (auto &b : brk) if (b.rt < bestr - 1e-12 || (b.rt < bestr + 1e-12 && b.g > besta)) { bestr = b.rt; besta = b.g; q = b.j; }
        }
        }
        if (!flips.empty()) {
            sumv.assign(k, 0.0);
            for (int e = 0; e < k; e++) { const double *Ai = &L.A[(size_t)L.act[e] * n]; double s_ = 0; for (int j : flips) s_ += Ai[j] * (-2.0 * L.at[j]); sumv[e] = s_; }
            for (int j : flips) L.at[j] = -L.at[j];
            for (int a = 0; a < k; a++) { const double *ba = &L.Binv[(size_t)a * k]; double s_ = 0; for (int e = 0; e < k; e++) s_ += ba[e] * sumv[e]; L.xB[a] -= s_; }
        }
        vector<double> &c = L.col; ftran(q, c);
        double piv = c[r];
        if (fabs(piv) < 1e-10) { if (!refactor()) { if (++restarts > 3) { lpwhy = 1; return 2; } slack_basis(); } compute_xB(); dn_valid = false; dual_reset(); bnd_dirty = true; atd_dirty = true; continue; }
        double theta = dd[q] / al[q];
        { double *dw = dn.data(); for (int j = 0; j < n; j++) dw[j] -= theta * al[j]; dw[q] = 0.0; }
        double delta = (L.xB[r] - target) / piv, xq = L.at[q];
        for (int a = 0; a < k; a++) L.xB[a] -= delta * c[a];
        int lv = L.basis[r]; L.xB[r] = xq + delta; L.basis[r] = q; L.at[q] = 0; lbB[r] = FZ[q] ? (double)FZ[q] : -1.0; ubB[r] = FZ[q] ? (double)FZ[q] : 1.0; atd[q] = 0.0;
        if (lv < n) { L.at[lv] = (target > 0) ? 1 : -1; dn[lv] = -theta; atd[lv] = FZ[lv] ? 0.0 : (double)L.at[lv]; } else L.atl[lv - n] = (target >= L.hi[lv - n]) ? 1 : -1;
        double ip = 1.0 / piv; double *__restrict__ br = &L.Binv[(size_t)r * k]; for (int e = 0; e < k; e++) br[e] *= ip;
        for (int a = 0; a < k; a++) if (a != r) { double f = c[a]; if (f != 0.0) { double *__restrict__ ba = &L.Binv[(size_t)a * k]; for (int e = 0; e < k; e++) ba[e] -= f * br[e]; } }
        L.iters++;
        if (++L.pivots >= REFREQ) { if (!refactor()) { if (++restarts > 3) { lpwhy = 2; return 2; } slack_basis(); } compute_xB(); dn_valid = false; dual_reset(); bnd_dirty = true; atd_dirty = true; }
    }
    lpwhy = 3; return 2;
}
// max of the sum over a class: cls_idx lists the columns with cost 1, sign s
static vector<double> cc;
static int lp_maximize_core(double *val, int maxit);
static int lp_maximize(const vector<int> &cols, double s, double *val, int maxit = 20000) { cc.assign(L.n, 0.0); for (int j : cols) cc[j] = s; return lp_maximize_core(val, maxit); }
static double LP_STOP = 1e300; static bool lp_stopped = false; static ll scan_stops = 0; static int DEVEX = 1;
static int lp_maximize_old(double *val, int maxit);
static inline void price_exact() {
    int k = L.k, n = L.n; vector<double> &y = L.y; y.assign(k, 0.0);
    for (int a = 0; a < k; a++) { int b = L.basis[a]; if (b < n && cc[b] != 0.0) { const double *ba = &L.Binv[(size_t)a * k]; double cb = cc[b]; for (int e = 0; e < k; e++) y[e] += cb * ba[e]; } }
    vector<double> &d = L.dj; d.assign(cc.begin(), cc.end());
    for (int e = 0; e < k; e++) { double ye = y[e]; if (ye == 0.0) continue; const SpRow &sr = SR[L.act[e]]; double *dd = d.data();
        if (sr.dense) { const double *Ai = &L.A[(size_t)L.act[e] * n]; for (int j = 0; j < n; j++) dd[j] -= ye * Ai[j]; }
        else { const int *ix = sr.idx.data(); const double *vl = sr.val.data(); int m_ = sr.idx.size(); for (int t = 0; t < m_; t++) dd[ix[t]] -= ye * vl[t]; } }
}
static ll prim_iters = 0, prim_calls = 0;
static int lp_maximize_core_(double *val, int maxit);
static int PARTIAL = 0; static ll part_full = 0;
static int lp_maximize_part(double *val, int maxit);
static int RANGEDUAL = 0; static double DSTOP = -1e300; static bool dual_stopped = false;
static inline double cur_value() { int k = L.k, n = L.n; double v = 0; for (int j = 0; j < n; j++) if (L.at[j] && pert[j] != 0.0) v += pert[j] * L.at[j]; for (int a = 0; a < k; a++) { int b = L.basis[a]; if (b < n && pert[b] != 0.0) v += pert[b] * L.xB[a]; } return v; }
static int lp_dualmax(double *val, int maxit) {
    pert = cc; dn_valid = false; int save = LONGSTEP; LONGSTEP = 1; dual_stopped = false; RANGE_ACTIVE = true;
    int st = lp_feasible(maxit); LONGSTEP = save; RANGE_ACTIVE = false; dn_valid = false;
    if (st == 1) return 3;
    if (st != 0) return 2;
    price_exact(); *val = cur_value(); return 0;
}
struct BasisEntry { vector<int> rows, basis; vector<signed char> at, atl; };
static unordered_map<unsigned long long, BasisEntry> BCACHE; static int BCACHE_ON = 0; static unsigned long long BKEY = 0; static ll bc_hit = 0, bc_miss = 0, bc_iters = 0, bc_stored = 0;
static void bcache_store() {
    if ((int)BCACHE.size() > 200000) BCACHE.clear();
    BasisEntry &e = BCACHE[BKEY]; e.rows = L.act; e.basis = L.basis; e.at = L.at; e.atl.resize(L.k); for (int q = 0; q < L.k; q++) e.atl[q] = L.atl[L.act[q]]; bc_stored++;
}
static bool bcache_load() {
    auto it = BCACHE.find(BKEY); if (it == BCACHE.end()) return false; BasisEntry &e = it->second; if (e.rows != L.act) return false;
    L.basis = e.basis; L.at = e.at; for (int j : FZlist) { int p = abs(j) - 1; if (L.at[p]) L.at[p] = j > 0 ? 1 : -1; } for (int q = 0; q < L.k; q++) L.atl[L.act[q]] = e.atl[q];
    if (!refactor()) return false; compute_xB(); return true;
}
static int lp_maximize_core(double *val, int maxit) {
    if (BCACHE_ON && BKEY) {
        unsigned long long key = BKEY; ll i0 = L.iters; prim_calls++;
        if (bcache_load()) {
            bc_hit++; int rc = lp_dualmax(val, maxit); prim_iters += L.iters - i0; bc_iters += L.iters - i0; lp_stopped = false;
            if (rc == 0) { BKEY = key; bcache_store(); } BKEY = 0; return rc;
        }
        bc_miss++; int rc = DEVEX ? lp_maximize_core_(val, maxit) : lp_maximize_old(val, maxit); prim_iters += L.iters - i0;
        if (rc == 0 && !lp_stopped) { BKEY = key; bcache_store(); } BKEY = 0; return rc;
    }
    ll i0 = L.iters; prim_calls++; int rc = RANGEDUAL ? lp_dualmax(val, maxit) : (PARTIAL > 0 ? lp_maximize_part(val, maxit) : (DEVEX ? lp_maximize_core_(val, maxit) : lp_maximize_old(val, maxit))); prim_iters += L.iters - i0; return rc;
}
// Primal simplex with a candidate list: reduced costs only for a few columns between full pricings, the multipliers kept current.
static int lp_maximize_part(double *val, int maxit) {
    L.solves++; dn_valid = false; int k = L.k, n = L.n; const double dtol = 1e-9; lp_stopped = false; double vcur = 0; at_sync();
    if (LP_STOP < 1e299) { for (int j = 0; j < n; j++) if (L.at[j] && cc[j] != 0.0) vcur += cc[j] * L.at[j]; for (int a = 0; a < k; a++) { int b = L.basis[a]; if (b < n && cc[b] != 0.0) vcur += cc[b] * L.xB[a]; } if (vcur >= LP_STOP) { lp_stopped = true; *val = vcur; scan_stops++; return 0; } }
    static vector<int> C; static vector<double> sc; sc.resize(n); C.clear(); vector<double> &y = L.y; vector<double> &d = L.dj;
    auto refill = [&]() {
        price_exact(); part_full++; C.clear(); const signed char *at = L.at.data(); const double *dp = d.data();
        for (int j = 0; j < n; j++) { sc[j] = 0; if (!at[j] || FZ[j]) continue; double dj = dp[j]; if ((at[j] < 0 && dj > dtol) || (at[j] > 0 && dj < -dtol)) { sc[j] = fabs(dj); C.push_back(j); } }
        if ((int)C.size() > PARTIAL) { nth_element(C.begin(), C.begin() + PARTIAL, C.end(), [&](int a, int b) { return sc[a] > sc[b]; }); C.resize(PARTIAL); }
    };
    refill();
    for (int it = 0; it < maxit; it++) {
        int q = -1; double best = 0, dq = 0; const signed char *at = L.at.data();
        for (size_t ci = 0; ci < C.size(); ) {
            int j = C[ci]; if (!at[j]) { C[ci] = C.back(); C.pop_back(); continue; }
            const double *__restrict__ col_ = &AT[(size_t)j * k]; const double *__restrict__ yy = y.data(); double s_ = 0; for (int e = 0; e < k; e++) s_ += yy[e] * col_[e]; double dj = cc[j] - s_;
            if ((at[j] < 0 && dj > dtol) || (at[j] > 0 && dj < -dtol)) { double a_ = fabs(dj); if (a_ > best) { best = a_; q = j; dq = dj; } ci++; }
            else { C[ci] = C.back(); C.pop_back(); }
        }
        if (q < 0) {
            refill();
            if (C.empty()) {
                double v = 0; for (int j = 0; j < n; j++) if (L.at[j] && cc[j] != 0.0) v += cc[j] * L.at[j];
                for (int a = 0; a < k; a++) { int b = L.basis[a]; if (b < n && cc[b] != 0.0) v += cc[b] * L.xB[a]; }
                *val = v; return 0;
            }
            continue;
        }
        int dir = at[q] < 0 ? 1 : -1;
        vector<double> &cl = L.col; ftran(q, cl);
        double t = 2.0; int r = -1; double tgt = 0, bestp = 0;
        for (int a = 0; a < k; a++) {
            double rate = -dir * cl[a]; if (fabs(rate) < 1e-10) continue;
            int b = L.basis[a]; double l, u; if (b < n) { if (FZ[b]) { l = u = FZ[b]; } else { l = -1; u = 1; } } else { l = L.lo[b - n]; u = L.hi[b - n]; }
            double lim, bd; if (rate > 0) { lim = (u - L.xB[a]) / rate; bd = u; } else { lim = (l - L.xB[a]) / rate; bd = l; }
            if (lim < 0) lim = 0;
            if (lim < t - 1e-11 || (lim < t + 1e-11 && fabs(rate) > bestp)) { t = min(t, lim); r = a; tgt = bd; bestp = fabs(rate); }
        }
        for (int a = 0; a < k; a++) L.xB[a] += -dir * cl[a] * t;
        L.iters++;
        bool stopnow = false;
        if (LP_STOP < 1e299) { vcur += dq * dir * t; if (vcur >= LP_STOP) stopnow = true; }
        if (r < 0) { L.at[q] = -L.at[q]; if (stopnow) { lp_stopped = true; scan_stops++; *val = vcur; return 0; } continue; }
        double piv = cl[r];
        // the multipliers, from the old inverse
        { double th = dq / piv; const double *__restrict__ rho = &L.Binv[(size_t)r * k]; double *__restrict__ yy = y.data(); for (int e = 0; e < k; e++) yy[e] += th * rho[e]; }
        double xq0 = L.at[q]; int lv = L.basis[r]; L.basis[r] = q; L.xB[r] = xq0 + dir * t; L.at[q] = 0;
        if (lv < n) { L.at[lv] = (tgt > 0) ? 1 : -1; } else L.atl[lv - n] = (tgt >= L.hi[lv - n]) ? 1 : -1;
        double ip = 1.0 / piv; double *__restrict__ br = &L.Binv[(size_t)r * k]; for (int e = 0; e < k; e++) br[e] *= ip;
        for (int a = 0; a < k; a++) if (a != r) { double f = cl[a]; if (f != 0.0) { double *__restrict__ ba = &L.Binv[(size_t)a * k]; for (int e = 0; e < k; e++) ba[e] -= f * br[e]; } }
        if (++L.pivots >= REFREQ) { if (!refactor()) return 2; compute_xB(); refill(); }
        if (stopnow) { lp_stopped = true; scan_stops++; *val = vcur; return 0; }
    }
    return 2;
}
static int NOWT = 0; static double LP_G0 = 0, LP_GST = 0; static int RTUB = 0; static ll lp_ubstops = 0, lp_ubfalse = 0;
static int lp_maximize_core_(double *val, int maxit) {
    L.solves++; dn_valid = false; int k = L.k, n = L.n; const double dtol = 1e-9; lp_stopped = false; double vcur = 0;
    const bool track_ = LP_STOP < 1e299 || LP_GST > 0;
    if (track_) { for (int j = 0; j < n; j++) if (L.at[j] && cc[j] != 0.0) vcur += cc[j] * L.at[j]; for (int a = 0; a < k; a++) { int b = L.basis[a]; if (b < n && cc[b] != 0.0) vcur += cc[b] * L.xB[a]; } if (vcur >= LP_STOP) { lp_stopped = true; *val = vcur; scan_stops++; return 0; } }
    static vector<double> wt, ar, ats, score_; wt.assign(n, 1.0); ar.resize(n); ats.resize(n); score_.resize(n);
    for (int j = 0; j < n; j++) ats[j] = (L.at[j] && !FZ[j]) ? -(double)L.at[j] : 0.0;
    price_exact(); bool fresh = true; vector<double> &d = L.dj;
    for (int it = 0; it < maxit; it++) {
        int q = -1; double best = 0; int dir = 0; const signed char *at = L.at.data();
        { const double *__restrict__ dp = d.data(); const double *__restrict__ wp = wt.data(); const double *__restrict__ asp = ats.data(); double *__restrict__ sc = score_.data();
          double gain_ = 0;
          if (NOWT) { for (int j = 0; j < n; j++) { double v_ = asp[j] * dp[j]; sc[j] = v_ > dtol ? v_ : 0.0; gain_ += v_ > 0 ? v_ : 0.0; } }
          else for (int j = 0; j < n; j++) { double dj = dp[j]; double v_ = asp[j] * dj; sc[j] = v_ > dtol ? dj * dj / wp[j] : 0.0; gain_ += v_ > 0 ? v_ : 0.0; }
          for (int j = 0; j < n; j++) if (sc[j] > best) { best = sc[j]; q = j; }
          if (LP_GST > 0 && q >= 0) {
              // what these multipliers prove, whatever the basis: nothing above vcur + 2 gain.  If no grid value lies between, the rest of the climb cannot change the answer.
              double nxt_ = LP_G0 + (floor((vcur - LP_G0) / LP_GST + 1e-9) + 1.0) * LP_GST;
              if (vcur + 2.0 * gain_ < nxt_ - 1e-7 * LP_GST) {
                  if (!fresh) { price_exact(); fresh = true; lp_ubfalse++; continue; }
                  lp_ubstops++; *val = vcur; return 0;
              }
          } }
        if (q < 0) {
            if (!fresh) { price_exact(); fresh = true; continue; }
            double v = 0; for (int j = 0; j < n; j++) if (L.at[j] && cc[j] != 0.0) v += cc[j] * L.at[j];
            for (int a = 0; a < k; a++) { int b = L.basis[a]; if (b < n && cc[b] != 0.0) v += cc[b] * L.xB[a]; }
            *val = v; return 0;
        }
        dir = at[q] < 0 ? 1 : -1; fresh = false;
        vector<double> &cl = L.col; cl.resize(k);
        ftran(q, cl);
        double t = 2.0; int r = -1; double tgt = 0, bestp = 0;
        for (int a = 0; a < k; a++) {
            double rate = -dir * cl[a]; if (fabs(rate) < 1e-10) continue;
            int b = L.basis[a]; double l, u; if (b < n) { if (FZ[b]) { l = u = FZ[b]; } else { l = -1; u = 1; } } else { l = L.lo[b - n]; u = L.hi[b - n]; }
            double lim, bd; if (rate > 0) { lim = (u - L.xB[a]) / rate; bd = u; } else { lim = (l - L.xB[a]) / rate; bd = l; }
            if (lim < 0) lim = 0;
            if (lim < t - 1e-11 || (lim < t + 1e-11 && fabs(rate) > bestp)) { t = min(t, lim); r = a; tgt = bd; bestp = fabs(rate); }
        }
        for (int a = 0; a < k; a++) L.xB[a] += -dir * cl[a] * t;
        L.iters++;
        bool stopnow = false;
        if (track_) { vcur += d[q] * dir * t; if (vcur >= LP_STOP) stopnow = true; }
        if (r < 0) { L.at[q] = -L.at[q]; ats[q] = -ats[q]; if (stopnow) { lp_stopped = true; scan_stops++; *val = vcur; return 0; } continue; }
        double piv = cl[r];
        // the pivot row, from the old inverse
        if (TILEF) row_combo_f(&L.Binv[(size_t)r * k], ar.data()); else row_combo(&L.Binv[(size_t)r * k], ar.data());
        double theta = d[q] / piv, wq = wt[q], ipv2 = wq / (piv * piv);
        if (NOWT) { double *__restrict__ dd = d.data(); const double *__restrict__ al = ar.data(); for (int j = 0; j < n; j++) dd[j] -= theta * al[j]; }
        else { double *dd = d.data(); double *ww = wt.data(); const double *al = ar.data(); for (int j = 0; j < n; j++) { double aj = al[j]; dd[j] -= theta * aj; double nw = aj * aj * ipv2; if (nw > ww[j]) ww[j] = nw; } }
        double xq0 = L.at[q]; int lv = L.basis[r]; L.basis[r] = q; L.xB[r] = xq0 + dir * t; L.at[q] = 0; d[q] = 0; ats[q] = 0;
        if (lv < n) { L.at[lv] = (tgt > 0) ? 1 : -1; d[lv] = -theta; wt[lv] = max(ipv2, 1.0); ats[lv] = FZ[lv] ? 0.0 : -(double)L.at[lv]; } else L.atl[lv - n] = (tgt >= L.hi[lv - n]) ? 1 : -1;
        double ip = 1.0 / piv; double *__restrict__ br = &L.Binv[(size_t)r * k]; for (int e = 0; e < k; e++) br[e] *= ip;
        for (int a = 0; a < k; a++) if (a != r) { double f = cl[a]; if (f != 0.0) { double *__restrict__ ba = &L.Binv[(size_t)a * k]; for (int e = 0; e < k; e++) ba[e] -= f * br[e]; } }
        if (++L.pivots >= REFREQ) { if (!refactor()) return 2; compute_xB(); price_exact(); fresh = true; }
        if (stopnow) { lp_stopped = true; scan_stops++; *val = vcur; return 0; }
    }
    return 2;
}
static int lp_maximize_old(double *val, int maxit) {
    L.solves++; dn_valid = false; int k = L.k, n = L.n; const double dtol = 1e-9; lp_stopped = false; double vcur = 0;
    if (LP_STOP < 1e299) { for (int j = 0; j < n; j++) if (L.at[j] && cc[j] != 0.0) vcur += cc[j] * L.at[j]; for (int a = 0; a < k; a++) { int b = L.basis[a]; if (b < n && cc[b] != 0.0) vcur += cc[b] * L.xB[a]; } if (vcur >= LP_STOP) { lp_stopped = true; *val = vcur; scan_stops++; return 0; } }
    for (int it = 0; it < maxit; it++) {
        vector<double> &y = L.y; y.assign(k, 0.0);
        for (int a = 0; a < k; a++) { int b = L.basis[a]; if (b < n && cc[b] != 0.0) { const double *ba = &L.Binv[(size_t)a * k]; double cb = cc[b]; for (int e = 0; e < k; e++) y[e] += cb * ba[e]; } }
        vector<double> &d = L.dj; d.assign(cc.begin(), cc.end());
        for (int e = 0; e < k; e++) { double ye = y[e]; if (ye != 0.0) { const double *Ai = &L.A[(size_t)L.act[e] * n]; double *dd = d.data(); for (int j = 0; j < n; j++) dd[j] -= ye * Ai[j]; } }
        int q = -1; double best = dtol; int dir = 0;
        for (int j = 0; j < n; j++) { if (!L.at[j] || FZ[j]) continue; double dj = d[j]; if (L.at[j] < 0 && dj > best) { best = dj; q = j; dir = 1; } else if (L.at[j] > 0 && -dj > best) { best = -dj; q = j; dir = -1; } }
        if (q < 0) {
            double v = 0; for (int j = 0; j < n; j++) if (L.at[j] && cc[j] != 0.0) v += cc[j] * L.at[j];
            for (int a = 0; a < k; a++) { int b = L.basis[a]; if (b < n && cc[b] != 0.0) v += cc[b] * L.xB[a]; }
            *val = v; return 0;
        }
        vector<double> &cl = L.col; cl.resize(k);
        for (int a = 0; a < k; a++) { const double *b = &L.Binv[(size_t)a * k]; double s_ = 0; for (int e = 0; e < k; e++) s_ += b[e] * L.A[(size_t)L.act[e] * n + q]; cl[a] = s_; }
        double t = 2.0; int r = -1; double tgt = 0, bestp = 0;
        for (int a = 0; a < k; a++) {
            double rate = -dir * cl[a]; if (fabs(rate) < 1e-10) continue;
            int b = L.basis[a]; double l, u; if (b < n) { if (FZ[b]) { l = u = FZ[b]; } else { l = -1; u = 1; } } else { l = L.lo[b - n]; u = L.hi[b - n]; }
            double lim, bd; if (rate > 0) { lim = (u - L.xB[a]) / rate; bd = u; } else { lim = (l - L.xB[a]) / rate; bd = l; }
            if (lim < 0) lim = 0;
            if (lim < t - 1e-11 || (lim < t + 1e-11 && fabs(rate) > bestp)) { t = min(t, lim); r = a; tgt = bd; bestp = fabs(rate); }
        }
        for (int a = 0; a < k; a++) L.xB[a] += -dir * cl[a] * t;
        if (LP_STOP < 1e299) { vcur += d[q] * dir * t; if (vcur >= LP_STOP) { if (r < 0) L.at[q] = -L.at[q]; else { double xq0_ = L.at[q]; int lv_ = L.basis[r]; L.basis[r] = q; L.xB[r] = xq0_ + dir * t; L.at[q] = 0; if (lv_ < n) L.at[lv_] = (tgt > 0) ? 1 : -1; else L.atl[lv_ - n] = (tgt >= L.hi[lv_ - n]) ? 1 : -1; double piv_ = cl[r], ip_ = 1.0 / piv_; double *br_ = &L.Binv[(size_t)r * k]; for (int e = 0; e < k; e++) br_[e] *= ip_; for (int a = 0; a < k; a++) if (a != r) { double f_ = cl[a]; if (f_ != 0.0) { double *ba_ = &L.Binv[(size_t)a * k]; for (int e = 0; e < k; e++) ba_[e] -= f_ * br_[e]; } } if (++L.pivots >= REFREQ) { if (!refactor()) return 2; compute_xB(); } } L.iters++; lp_stopped = true; scan_stops++; *val = vcur; return 0; } }
        if (r < 0) { L.at[q] = -L.at[q]; L.iters++; continue; }
        double xq0 = L.at[q]; int lv = L.basis[r]; L.basis[r] = q; L.xB[r] = xq0 + dir * t; L.at[q] = 0;
        if (lv < n) L.at[lv] = (tgt > 0) ? 1 : -1; else L.atl[lv - n] = (tgt >= L.hi[lv - n]) ? 1 : -1;
        double piv = cl[r], ip = 1.0 / piv; double *br = &L.Binv[(size_t)r * k]; for (int e = 0; e < k; e++) br[e] *= ip;
        for (int a = 0; a < k; a++) if (a != r) { double f = cl[a]; if (f != 0.0) { double *ba = &L.Binv[(size_t)a * k]; for (int e = 0; e < k; e++) ba[e] -= f * br[e]; } }
        L.iters++;
        if (++L.pivots >= REFREQ) { if (!refactor()) return 2; compute_xB(); }
    }
    return 2;
}
static void lp_point(vector<double> &x) { int n = L.n; x.assign(n, 0.0); for (int j = 0; j < n; j++) if (L.at[j]) x[j] = L.at[j]; for (int a = 0; a < L.k; a++) if (L.basis[a] < n) x[L.basis[a]] = L.xB[a]; }
// ------------------------------------------------------------------ the problem
struct Mod { vector<int> antiW; vector<ll> Wstep, Wc0; int M, nb; ll mult; vector<LL> rep; vector<ll> sz; vector<int> order, piv; vector<vector<LL>> B; int pos; vector<double> norm; vector<vector<int>> members; vector<vector<int>> W; vector<int> divisors; };
static int N_, M_; static vector<Mod> mods; static map<int, int> modidx; static vector<double> rownorm;
static int PULL = 0; static double PULLF = 0.7; static int PROPM = 0, PROPQ = 4; static int HULLSWAP = 0; static int DIRECTM = 3, DIRECTQ = 8; static int CAP = 100000, TESTS = 8, FEAS = 2, WIDE = 3, DEEP = 300, RETRY = 2, SAMPLE = 3000; static ll ENUM_NODES = 30000000;
static vector<int> want;
struct FormKey { int mi; vector<int> c; bool operator<(const FormKey &o) const { return mi != o.mi ? mi < o.mi : c < o.c; } };
static map<FormKey, pair<int, double>> forms;
static vector<pair<int, vector<int>>> rowform;   // per row: its modulus index and integer coefficients, for logging and exactness
static pair<int, double> form_row(int mi, const vector<int> &coef) {
    FormKey key{mi, coef}; auto it = forms.find(key); if (it != forms.end()) return it->second;
    static vector<double> v; v.assign(N_, 0.0); int M = mods[mi].M; double s = 0;
    for (int r = 0; r < M; r++) if (coef[r]) for (int p : mods[mi].members[r]) v[p] += coef[r];
    for (double t : v) s += t * t; s = sqrt(s); for (double &t : v) t /= s;
    int id = lp_add_row(v.data()); forms[key] = {id, s}; return {id, s};
}
// the enumerator
struct En { int M, nb, P; ll mult; const vector<LL> *rep; vector<ll> lo, hi; const vector<ll> *sz0; vector<ll> sz; vector<int> cls, piv; const vector<vector<LL>> *B; vector<ll> W, rl, rh, rs, d, part; vector<LL> z; ll maxnodes, nodes; int maxout; bool capped; vector<int16_t> *out; ll found; const vector<int> *order; };
static En E;
static void en_rec(int i, int j);
static inline void en_place(int i, int j, LL v) {
    if (v > E.hi[i] || v < E.lo[i]) return;
    ll di = (ll)v;
    if ((di - E.sz[i]) % 2 != 0) return;
    int q = E.cls[i] % E.P; ll rest = E.W[q] - E.part[q] - di;
    if (rest < E.rl[i] || rest > E.rh[i] || ((rest - E.rs[i]) % 2) != 0) return;
    E.d[i] = di; E.part[q] += di; en_rec(i - 1, j); E.part[q] -= di;
}
static void en_rec(int i, int j) {
    if (E.capped) return;
    if (++E.nodes > E.maxnodes) { E.capped = true; return; }
    if (i < 0) { E.found++; if (E.found > E.maxout) { E.capped = true; return; } size_t base = E.out->size(); E.out->resize(base + E.M); for (int r = 0; r < E.M; r++) (*E.out)[base + E.cls[r]] = (int16_t)E.d[r]; return; }
    LL b = (*E.rep)[i];
    for (int c = j + 1; c < E.nb; c++) b += E.mult * (*E.B)[i][c] * E.z[c];
    if (j >= 0 && E.piv[j] == i) {
        LL h = E.mult * (*E.B)[i][j]; LL l = (LL)E.lo[i] - b, u = (LL)E.hi[i] - b;
        LL zl = l >= 0 ? (l + h - 1) / h : -((-l) / h), zh = u >= 0 ? u / h : -((-u + h - 1) / h);
        for (LL t = zl; t <= zh && !E.capped; t++) { E.z[j] = t; en_place(i, j - 1, b + h * t); }
        E.z[j] = 0;
    } else en_place(i, j, b);
}
// lo, hi by class; parent P and W (P = 1 if none); returns false if capped
static vector<LL> EN_rep2; static vector<vector<LL>> EN_B2; static vector<int> EN_piv2; static int EN_nb2 = -1;
static bool enumerate(int mi, const vector<ll> &lo, const vector<ll> &hi, int P, const vector<ll> &W, vector<int16_t> &out) {
    Mod &m = mods[mi]; int M = m.M;
    E.M = M; E.nb = EN_nb2 >= 0 ? EN_nb2 : m.nb; E.mult = m.mult; E.rep = EN_nb2 >= 0 ? &EN_rep2 : &m.rep; E.B = EN_nb2 >= 0 ? &EN_B2 : &m.B; E.piv = EN_nb2 >= 0 ? EN_piv2 : m.piv; E.cls = m.order; E.P = P; E.maxnodes = ENUM_NODES; E.nodes = 0; E.capped = false; E.maxout = CAP; E.found = 0; E.out = &out; out.clear();
    E.lo.resize(M); E.hi.resize(M); E.sz.resize(M);
    for (int i = 0; i < M; i++) { int r = m.order[i]; E.lo[i] = lo[r]; E.hi[i] = hi[r]; E.sz[i] = m.sz[r]; }
    E.W = (P > 1) ? W : vector<ll>(1, 0); E.z.assign(E.nb, 0); E.d.assign(M, 0); E.part.assign(P, 0); E.rl.assign(M, 0); E.rh.assign(M, 0); E.rs.assign(M, 0);
    for (int i = 0; i < M; i++) for (int t = 0; t < i; t++) if (E.cls[t] % P == E.cls[i] % P) { E.rl[i] += E.lo[t]; E.rh[i] += E.hi[t]; E.rs[i] += E.sz[t]; }
    en_rec(M - 1, E.nb - 1);
    return !E.capped;
}
// ------------------------------------------------------------------ nodes
struct Dom { int mi = -1; int N = 0; vector<int16_t> d; int rank = -1; };
struct Node { vector<pair<int, double>> fixed; vector<Dom> dom; unsigned full = 0; unsigned G = 0; unsigned impl = 0; vector<int> tried; vector<vector<ll>> fullval; vector<int> sgn; vector<vector<float>> memo; vector<float> field; };
struct Stats { ll direct_closed = 0, direct_fixed = 0, direct_split = 0; ll nodes = 0, closed = 0, open = 0, cuts = 0, removed = 0, hull = 0, enums = 0, capped = 0, splits = 0, viaLP = 0, viaDom = 0, maxdepth = 0; double tFilter = 0, tSplit = 0, tEnum = 0, tLP = 0, tBase = 0, tHull = 0, tCopy = 0; } ST;

// ------------------------------------------------------------------ exact checks
// Weights: W(p) = G(p) + DD * sum_i c_i coef_i(p mod M_i), G(p) = sum_t B_t C(p, t) with deg < m, all in integers.  For a sequence of order >= m, sum_p G(p) a_p = 0, so sum_p W(p) a_p = DD * sum_i c_i v_i =: K, known from the rows' values.
// |K| > sum_p |W(p)| is a contradiction, in integers, whatever the LP thought.
static vector<vector<LL>> BINOM; static vector<vector<long double>> UU; static const LL DD0 = ((LL)1) << 50; static const double SS0 = 16777216.0;
static ll exact_ok = 0, exact_fail = 0;
static vector<LL> Wx;
static inline LL labs128(LL v) { return v < 0 ? -v : v; }
// the row's raw integer value in a node
static inline ll raw_of(int row, double val) { if (row < M_) return 0; int mi = rowform[row].first; Mod &m = mods[mi]; double nr; if (row >= m.pos && row < m.pos + m.M) nr = m.norm[row - m.pos]; else nr = forms[FormKey{mi, rowform[row].second}].second; return llround(val * nr); }
static inline double row_norm(int row) { if (row < M_) return 1.0; int mi = rowform[row].first; Mod &m = mods[mi]; if (row >= m.pos && row < m.pos + m.M) return m.norm[row - m.pos]; return forms[FormKey{mi, rowform[row].second}].second; }
static vector<LL> LASTB; static LL LASTDD = 0; static double LASTSS = 0;
// Build W from multipliers y on rows (y[q] for rows[q]); ints[q] receives c_i.  scale multiplies y first.  DD, SS are the scales.  Returns false when numbers would be too large.
static bool build_w(const vector<int> &rows, const double *y, long double scale, LL DD, double SS, vector<ll> &ints) {
    int n = N_; static vector<LL> B; B.assign(M_, 0); ints.assign(rows.size(), 0);
    long double DS = (long double)DD * (long double)SS;
    for (int t = 0; t < M_; t++) { long double a = 0; for (int q = 0; q < (int)rows.size(); q++) if (rows[q] < M_ && y[q] != 0.0) a += (long double)y[q] * UU[rows[q]][t]; a *= scale * DS; if (fabsl(a) > 1.0e36L) return false; B[t] = (LL)roundl(a); }
    Wx.assign(n, 0);
    for (int p = 0; p < n; p++) { LL s = 0; const LL *bp = BINOM[p].data(); for (int t = 0; t < M_; t++) s += B[t] * bp[t]; Wx[p] = s; }
    for (int q = 0; q < (int)rows.size(); q++) {
        int row = rows[q]; if (row < M_ || y[q] == 0.0) continue;
        int mi = rowform[row].first; Mod &m = mods[mi]; long double v = (long double)y[q] / row_norm(row) * scale * SS; if (fabsl(v) > 9.0e15L) return false; ll c = llroundl(v); ints[q] = c; if (!c) continue;
        if (row >= m.pos && row < m.pos + m.M) { for (int p : m.members[row - m.pos]) Wx[p] += DD * c; }
        else { const vector<int> &cf = rowform[row].second; for (int r = 0; r < m.M; r++) if (cf[r]) { LL e = DD * c * cf[r]; for (int p : m.members[r]) Wx[p] += e; } }
    }
    LASTB = B; LASTDD = DD; LASTSS = SS;
    return true;
}
static const LL WMAX = ((LL)1) << 117;
static bool exact_bound_form(int mi, const vector<int> &w, int s_, const vector<int> &rows, const vector<double> &vals, ll &bound);
static inline LL w_total() { LL t = 0; for (LL v : Wx) { LL a = labs128(v); if (a > WMAX) return ((LL)1) << 126; t += a; } return t; }
// with signs known: the sum of |W| over the free positions, and the known part of sum W a
static inline LL w_free() { LL t = 0; int n = Wx.size(); for (int p = 0; p < n; p++) { if (FZ[p]) continue; LL a = labs128(Wx[p]); if (a > WMAX) return ((LL)1) << 126; t += a; } return t; }
static inline LL w_known() { LL t = 0; for (int v : FZlist) { int p = abs(v) - 1; t += Wx[p] * (v > 0 ? 1 : -1); } return t; }
// the largest multiplier, for normalising
// The stream for the checker: every claim with its integer certificate.  The checker trusts none of this.
struct CertRec { int dd = 0, ss = 0; vector<LL> B; vector<pair<int, ll>> c; int mi = -2; vector<int> w; };
static FILE *CERTF = nullptr; static CertRec CUP, CDN, CRAY, SAVEUP, SAVEDN; static vector<char> CERT_KNOWN; static bool CLOSE_DONE = false, SPLIT_SAVED = false;
static inline void cert_take(CertRec &R, int mi, const vector<int> *w, const vector<int> &rows, const vector<ll> &ints) {
    R.dd = __builtin_ctzll((unsigned long long)LASTDD); R.ss = ilogb(LASTSS); R.B = LASTB; R.c.clear(); for (size_t q = 0; q < rows.size(); q++) if (ints[q]) R.c.push_back({rows[q], ints[q]}); R.mi = mi; if (w) R.w = *w; else R.w.clear();
}
static void cert_num(LL v) { char b[48]; int i = 47; b[i] = 0; bool neg = v < 0; unsigned __int128 u = neg ? -(unsigned __int128)v : (unsigned __int128)v; if (!u) b[--i] = '0'; while (u) { b[--i] = (char)('0' + (int)(u % 10)); u /= 10; } if (neg) b[--i] = '-'; fputs(b + i, CERTF); fputc(' ', CERTF); }
static void cert_put(const CertRec &R) { cert_num(R.dd); cert_num(R.ss); for (LL v : R.B) cert_num(v); cert_num((LL)R.c.size()); for (auto &x : R.c) { cert_num(x.first); cert_num(x.second); } }
static void cert_null() { cert_num(50); cert_num(24); for (int t = 0; t < M_; t++) cert_num(0); cert_num(0); }
static void cert_grid(int mi, const vector<int> &w, ll &st, ll &c);
static void cert_define(int id) {
    if ((int)CERT_KNOWN.size() <= id) CERT_KNOWN.resize(id + 64, 0);
    if (CERT_KNOWN[id]) return;
    CERT_KNOWN[id] = 1; int mi = rowform[id].first; const vector<int> &w = rowform[id].second; ll st = 0, c = 0; cert_grid(mi, w, st, c);
    fputs("R ", CERTF); cert_num(id); cert_num(mods[mi].M); cert_num(st); cert_num(c); for (int x : w) cert_num(x); fputc('\n', CERTF);
}
static void cert_bounds(int mi, const vector<int> &w, int sym, long k, const CertRec &U, const CertRec &D);
static long double y_scale(const vector<int> &rows, const double *y) { long double mx = 0; for (int q = 0; q < (int)rows.size(); q++) { if (y[q] == 0.0) continue; long double a = fabsl((long double)y[q]) / row_norm(rows[q]); if (a > mx) mx = a; } return mx > 0 ? 1 / mx : 1; }
// Does the ray close a node with these rows and normalised values?  A second try with finer scales before saying no.
static bool exact_close(const vector<int> &rows, const vector<double> &vals) {
    static vector<double> y; y.resize(rows.size()); for (int q = 0; q < (int)rows.size(); q++) y[q] = L.ray[rows[q]];
    long double sc = y_scale(rows, y.data()); static vector<ll> ints;
    const LL DD1 = ((LL)1) << 58; const double SS1 = 4294967296.0;
    for (int attempt = 0; attempt < 2; attempt++) {
        LL DD = attempt ? DD1 : DD0; double SS = attempt ? SS1 : SS0;
        if (!build_w(rows, y.data(), sc, DD, SS, ints)) continue;
        LL K = 0; for (int q = 0; q < (int)rows.size(); q++) if (ints[q]) K += DD * ints[q] * raw_of(rows[q], vals[q]);
        if (labs128(K - w_known()) > w_free()) { exact_ok++; if (CERTF) cert_take(CRAY, -1, nullptr, rows, ints); return true; }
    }
    exact_fail++; return false;
}
// After lp_maximize with s on class r of m: a proved bound s D_r <= the value returned.  None if the numbers fail: the trivial bound then.
static bool exact_bound(int mi, int r, int s_, const vector<int> &rows, const vector<double> &vals, ll &bound) {
    static vector<double> y; y.resize(rows.size()); for (int q = 0; q < (int)rows.size(); q++) y[q] = L.y[q];
    static vector<ll> ints; if (!build_w(rows, y.data(), 1.0L, DD0, SS0, ints)) return false;
    Mod &m = mods[mi]; LL T = DD0 * (LL)SS0; LL K = 0; for (int q = 0; q < (int)rows.size(); q++) if (ints[q]) K += DD0 * ints[q] * raw_of(rows[q], vals[q]);
    LL tot = 0; vector<char> inc(N_, 0); for (int p : m.members[r]) inc[p] = 1;
    for (int p = 0; p < N_; p++) { LL e_ = (inc[p] ? T * s_ : (LL)0) - Wx[p]; tot += FZ[p] ? e_ * FZ[p] : labs128(e_); }
    LL b = tot + K; // s D_r T <= b
    LL f = b >= 0 ? b / T : -((-b + T - 1) / T);
    bound = (ll)f; return true;
}

// the image of a vector mod M under a symmetry of the problem: F -> -F, F -> x^(n-1) F(1/x)
template <class T> static inline void sym_image(int bit, int M, const T *v, vector<int> &out) {
    out.resize(M);
    for (int r = 0; r < M; r++) { int src = (bit & 6) ? (((N_ - 1 - r) % M) + M) % M : r; int x = v[src]; out[r] = (bit & 5) ? -x : x; }
}
static bool invariant_under(int bit, const vector<ll> &v) { int M = v.size(); vector<int> im; vector<int> iv(v.begin(), v.end()); sym_image(bit, M, iv.data(), im); return im == iv; }
// keep one of each orbit under G of the vectors in out (M values each)
static ll sym_removed = 0;
static void sym_reduce(vector<int16_t> &out, int M, unsigned G) {
    int N = out.size() / M, w = 0; vector<int> im;
    for (int i = 0; i < N; i++) {
        const int16_t *v = &out[(size_t)i * M]; bool keep = true;
        for (int bit : {1, 2, 4}) if (G & bit) {
            sym_image(bit, M, v, im);
            for (int r = 0; r < M; r++) { if (v[r] != im[r]) { if (im[r] < v[r]) keep = false; break; } }
            if (!keep) break;
        }
        if (keep) { if (w != i) memmove(&out[(size_t)w * M], v, M * sizeof(int16_t)); w++; }
    }
    sym_removed += N - w; out.resize((size_t)w * M);
}
static int USE_SYM = 1;
static int CERTPOOL = 0;
struct FormCert { vector<int> rows; vector<ll> c; LL tot; };
static FormCert LASTCERT;
static bool exact_bound_form(int mi, const vector<int> &w, int s_, const vector<int> &rows, const vector<double> &vals, ll &bound) {
    static vector<double> y; y.resize(rows.size()); for (int q = 0; q < (int)rows.size(); q++) y[q] = L.y[q];
    static vector<ll> ints; if (!build_w(rows, y.data(), 1.0L, DD0, SS0, ints)) return false;
    if (CERTF) cert_take(s_ > 0 ? CUP : CDN, mi, &w, rows, ints);
    Mod &m = mods[mi]; LL T = DD0 * (LL)SS0; LL K = 0; for (int q = 0; q < (int)rows.size(); q++) if (ints[q]) K += DD0 * ints[q] * raw_of(rows[q], vals[q]);
    LL tot = 0; for (int r = 0; r < m.M; r++) { LL e = T * s_ * w[r]; for (int p : m.members[r]) { LL e_ = e - Wx[p]; tot += FZ[p] ? e_ * FZ[p] : labs128(e_); } }
    if (CERTPOOL) { LASTCERT.rows.clear(); LASTCERT.c.clear(); for (int q = 0; q < (int)rows.size(); q++) if (ints[q]) { LASTCERT.rows.push_back(rows[q]); LASTCERT.c.push_back(ints[q]); } LASTCERT.tot = tot; }
    LL b = tot + K; LL f = b >= 0 ? b / T : -((-b + T - 1) / T); bound = (ll)f; return true;
}
static void cert_grid(int mi, const vector<int> &w, ll &st, ll &c) {
    Mod &m = mods[mi]; LL g = 0; for (int a = 0; a < m.nb; a++) { LL t = 0; for (int i = 0; i < m.M; i++) t += (LL)w[m.order[i]] * m.B[i][a]; if (t < 0) t = -t; while (t) { LL u = g % t; g = t; t = u; } }
    LL c0 = 0; for (int i = 0; i < m.M; i++) c0 += (LL)w[m.order[i]] * m.rep[i];
    LL step = (LL)m.mult * g; ll par = 0; for (int r = 0; r < m.M; r++) par += w[r] * m.sz[r]; par = ((par % 2) + 2) % 2;
    st = (ll)step; c = step ? (ll)(((c0 % step) + step) % step) : (ll)c0; if (st % 2) { if (((c - par) % 2 + 2) % 2) c += st; st *= 2; }
}
static void cert_bounds(int mi, const vector<int> &w, int sym, long k, const CertRec &U, const CertRec &D) {
    auto fr = form_row(mi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, w}; cert_define(fr.first);
    fputs("B ", CERTF); cert_num(fr.first); cert_num(sym); cert_num((LL)k);
    if (U.mi == mi && U.w == w) cert_put(U); else cert_null();
    if (D.mi == mi && D.w == w) cert_put(D); else cert_null();
    fputc('\n', CERTF);
    if (k == 0) CLOSE_DONE = true;
}
static bool exact_bound_form_scaled(int mi, const vector<int> &w, const vector<int> &rows, const vector<double> &vals, ll &bound) {
    static vector<double> y; y.resize(rows.size()); for (int q = 0; q < (int)rows.size(); q++) y[q] = L.y[q];
    static vector<ll> ints; if (!build_w(rows, y.data(), 1.0L, DD0, SS0, ints)) return false;
    Mod &m = mods[mi]; LL T = DD0 * (LL)SS0; LL K = 0; for (int q = 0; q < (int)rows.size(); q++) if (ints[q]) K += DD0 * ints[q] * raw_of(rows[q], vals[q]);
    // T/1000 per unit of w: use T' = T / 1000 exact by making T a multiple of 1000
    LL Tk = T / 1000; LL tot = 0; for (int r = 0; r < m.M; r++) { LL e = Tk * w[r]; for (int p : m.members[r]) { LL e_ = e - Wx[p]; tot += FZ[p] ? e_ * FZ[p] : labs128(e_); } }
    LL b = tot + K; LL f = b >= 0 ? b / Tk : -((-b + Tk - 1) / Tk); bound = (ll)f; return true;
}
static vector<double> xbuf;
static vector<int> wit; static ll wit_err = 0, wit_closed = 0, wit_nodes = 0;
static bool holds_witness(const Node &nd) {
    if (wit.empty()) return false;
    for (int v : nd.sgn) { int p = abs(v) - 1; if ((v > 0 ? 1 : -1) != wit[p]) return false; }
    for (auto &f : nd.fixed) { const double *Ai = &L.A[(size_t)f.first * N_]; double s = 0; for (int j = 0; j < N_; j++) s += Ai[j] * wit[j]; if (fabs(s - f.second) > 1e-7) return false; }
    return true;
}
static bool wit_in_dom(const Dom &D) {
    Mod &m = mods[D.mi]; int M = m.M; vector<int> w(M, 0); for (int p = 0; p < N_; p++) w[p % M] += wit[p];
    for (int i = 0; i < D.N; i++) { bool eq = true; for (int r = 0; r < M; r++) if (D.d[(size_t)i * M + r] != w[r]) { eq = false; break; } if (eq) return true; }
    return false;
}
static int DROPLAST = 0;
static int DROPDEP = 0;
static void base_rows(const Node &nd, vector<int> &rows, vector<double> &vals, int skipmi) {
    // the moments; fixed rows; rows of a modulus with a fully pinned multiple are implied.  skipmi: during a test of that modulus, its forms and its divisors' classes go too.
    rows.clear(); vals.clear();
    for (int i = 0; i < M_; i++) { rows.push_back(i); vals.push_back(0.0); }
    static vector<char> drop; drop.assign(L.K, 0);
    for (int a = 0; a < (int)mods.size(); a++) if (nd.full >> a & 1) for (int di : mods[a].divisors) for (int r = 0; r < mods[di].M; r++) drop[mods[di].pos + r] = 1;
    // the classes of a fully pinned modulus add up to the sum of all the signs, which is a moment: one of them says nothing new
    if (DROPDEP && skipmi < 0) for (int a = 0; a < (int)mods.size(); a++) if (nd.full >> a & 1) drop[mods[a].pos + mods[a].M - 1] = 1;
    if (skipmi >= 0) {
        for (int di : mods[skipmi].divisors) for (int r = 0; r < mods[di].M; r++) drop[mods[di].pos + r] = 1;
        for (int r = 0; r < mods[skipmi].M; r++) drop[mods[skipmi].pos + r] = 1;
    }
    for (auto &f : nd.fixed) {
        if (drop[f.first]) continue;
        int fm = rowform[f.first].first;
        if (fm >= 0 && (nd.full >> fm & 1) && !rowform[f.first].second.empty()) continue;
        if (DROPLAST && fm >= 0 && (nd.full >> fm & 1) && fm != skipmi && f.first == mods[fm].pos + mods[fm].M - 1) continue;
        if (skipmi >= 0 && fm == skipmi) continue;
        rows.push_back(f.first); vals.push_back(f.second); drop[f.first] = 1;   // once only: a class pinned by a split and then by its whole modulus would make the basis singular
    }
}
static ll rayfail = 0, unproved = 0;
static bool ray_valid(const vector<int> &rows, const vector<double> &vals) {
    int n = N_; static vector<double> c; c.assign(n, 0.0); double K = 0;
    for (int q = 0; q < (int)rows.size(); q++) { double yq = L.ray[rows[q]]; if (yq == 0.0) continue; const double *Ai = &L.A[(size_t)rows[q] * n]; for (int j = 0; j < n; j++) c[j] += yq * Ai[j]; K += yq * vals[q]; }
    double budget = 0; for (int j = 0; j < n; j++) budget += fabs(c[j]);
    return fabs(K) > budget * (1 + 1e-9) + 1e-7;
}

// The coset of the modulus cut by the forms already fixed in this node: an echelon basis of the affine sublattice, for the enumerator.  Returns 0 if no integer vector satisfies the forms (the node closes, exactly), 1 otherwise.
static int SUBLAT = 0; static ll sub_closed = 0, sub_used = 0; static double sub_rank = 0;
static int sublattice(int mi, const Node &nd, vector<LL> &rep2, vector<vector<LL>> &B2, vector<int> &piv2, int &nb2) {
    Mod &m = mods[mi]; int M = m.M, nb = m.nb;
    vector<vector<LL>> eq; vector<LL> rhs;
    for (auto &f : nd.fixed) {
        if (f.first < M_) continue;
        int fm = rowform[f.first].first; if (fm != mi) continue;
        vector<int> w(M, 0); if (f.first >= m.pos && f.first < m.pos + M) w[f.first - m.pos] = 1; else if (!rowform[f.first].second.empty()) w = rowform[f.first].second; else continue;
        ll v = raw_of(f.first, f.second);
        vector<LL> a(nb, 0); LL g = v;
        for (int i = 0; i < M; i++) { int wi = w[m.order[i]]; if (!wi) continue; g -= wi * m.rep[i]; for (int c = 0; c < nb; c++) a[c] += (LL)wi * m.mult * m.B[i][c]; }
        eq.push_back(a); rhs.push_back(g);
    }
    // columns: each holds (eq entries, B entries)
    int r_ = eq.size(); vector<vector<LL>> col(nb, vector<LL>(r_ + M, 0));
    for (int c = 0; c < nb; c++) { for (int t = 0; t < r_; t++) col[c][t] = eq[t][c]; for (int i = 0; i < M; i++) col[c][r_ + i] = m.B[i][c]; }
    vector<char> used(nb, 0); rep2 = m.rep; vector<LL> y(nb, 0);
    auto reduce_row = [&](int row, vector<char> &use) -> int {   // Euclid on the unused columns at this row: leaves at most one nonzero; returns its column or -1
        while (true) {
            int b = -1; LL bv = 0; int cnt = 0;
            for (int c = 0; c < nb; c++) if (!use[c] && col[c][row] != 0) { cnt++; LL av = col[c][row] < 0 ? -col[c][row] : col[c][row]; if (b < 0 || av < bv) { b = c; bv = av; } }
            if (b < 0) return -1;
            if (cnt == 1) return b;
            for (int c = 0; c < nb; c++) if (!use[c] && c != b && col[c][row] != 0) { LL q = col[c][row] / col[b][row]; if (q != 0) for (size_t t = 0; t < col[c].size(); t++) col[c][t] -= q * col[b][t]; }
        }
    };
    for (int t = 0; t < r_; t++) {
        LL g = rhs[t]; 
        int b = reduce_row(t, used);
        if (b < 0) { if (g != 0) return 0; continue; }
        LL h = col[b][t]; if (g % h != 0) return 0; LL q = g / h; used[b] = 1;
        for (int i = 0; i < M; i++) rep2[i] += m.mult * q * col[b][r_ + i];
        for (int u = t + 1; u < r_; u++) rhs[u] -= q * col[b][u];
    }
    // echelon on the rest, from the top row down
    vector<char> done = used; vector<int> pc, pi;
    for (int i = M - 1; i >= 0; i--) {
        int b = reduce_row(r_ + i, done);
        if (b < 0) continue;
        if (col[b][r_ + i] < 0) for (auto &x : col[b]) x = -x;
        done[b] = 1; pc.push_back(b); pi.push_back(i);
    }
    nb2 = pc.size(); B2.assign(M, vector<LL>(nb2, 0)); piv2.assign(nb2, 0);
    // pivots: highest row gets the highest column index
    for (int k = 0; k < nb2; k++) { int c2 = nb2 - 1 - k; piv2[c2] = pi[k]; for (int i = 0; i < M; i++) B2[i][c2] = col[pc[k]][r_ + i]; }
    sub_rank += nb2; sub_used++;
    return 1;
}
// the values in the order of the LP's active rows, which are the rows given
static inline const vector<double> &bvals_for(const vector<int> &rows, const vector<double> &vals) { return vals; }
static ll PHI[10], PHN[10], RTO[3]; static double PHT[10];
static int feasible_base_(const Node &nd);
static int BK = 2, NEXTBK = 0; static ll BKI[3], BKN[3]; static double BKT[3];
static int feasible_base(const Node &nd) { double t0 = now(); ll i0 = L.iters; int st = feasible_base_(nd); PHI[0] += L.iters - i0; PHN[0]++; PHT[0] += now() - t0; ST.tBase += now() - t0; BKI[BK] += L.iters - i0; BKN[BK]++; BKT[BK] += now() - t0; BK = 2; return st; }
static void set_signs(const Node &nd) {
    if (FZlist == nd.sgn) return;
    for (int v : FZlist) FZ[abs(v) - 1] = 0;
    FZlist = nd.sgn;
    for (int v : FZlist) { int p = abs(v) - 1; signed char s_ = v > 0 ? 1 : -1; FZ[p] = s_; if (L.at[p]) L.at[p] = s_; }
    dn_valid = false;
}
static int feasible_base_(const Node &nd) {
    set_signs(nd);
    static vector<int> r; static vector<double> v; base_rows(nd, r, v, -1); lp_rows(r, v); int st = lp_feasible();
    if (st == 1 && !exact_close(r, v)) { rayfail++; if (!refactor()) slack_basis(); compute_xB(); dn_valid = false; st = lp_feasible(); if (st == 1 && !exact_close(r, v)) { unproved++; return 0; } }
    return st;
}
static void class_activity(int mi, vector<double> &mu) { Mod &m = mods[mi]; lp_point(xbuf); mu.assign(m.M, 0.0); for (int r = 0; r < m.M; r++) { double s = 0; for (int p : m.members[r]) s += xbuf[p]; mu[r] = s; } }

struct PoolCut { vector<int> rows; vector<ll> c; vector<double> eta; vector<LL> cD; LL Tot; double Totf; };
static vector<vector<PoolCut>> POOL; static int POOLMAX = 0; static ll pool_kills = 0, pool_tries = 0;
static vector<char> rowknown; static vector<double> rowval;
static void pool_apply(const Node &nd, Dom &D) {
    if (POOLMAX <= 0 || D.N == 0) return;
    int mi = D.mi; Mod &m = mods[mi]; int M = m.M;
    if ((int)POOL.size() < (int)mods.size()) POOL.resize(mods.size());
    auto &P = POOL[mi]; if (P.empty()) return;
    rowknown.assign(L.K, 0); rowval.resize(L.K);
    for (int i = 0; i < M_; i++) { rowknown[i] = 1; rowval[i] = 0.0; }
    for (auto &f : nd.fixed) { rowknown[f.first] = 1; rowval[f.first] = f.second; }
    vector<int16_t> &d = D.d; int N = D.N;
    for (size_t pi = 0; pi < P.size() && N > 0; pi++) {
        PoolCut &C = P[pi]; bool ok = true; LL K0 = 0; double K0f = 0;
        for (size_t q = 0; q < C.rows.size(); q++) { int row = C.rows[q]; if (!rowknown[row]) { ok = false; break; } if (C.c[q]) { ll raw = raw_of(row, rowval[row]); K0 += DD0 * C.c[q] * raw; } }
        if (!ok) continue;
        K0f = (double)K0; pool_tries++;
        int w = 0; ll rem = 0; const double *et = C.eta.data(); const LL *cd = C.cD.data();
        for (int i = 0; i < N; i++) {
            const int16_t *v = &d[(size_t)i * M]; double s_ = K0f; for (int r = 0; r < M; r++) s_ += et[r] * v[r];
            bool kill = false;
            if (fabs(s_) > C.Totf * (1 - 1e-6)) { LL e = K0; for (int r = 0; r < M; r++) e += cd[r] * v[r]; kill = labs128(e) > C.Tot; }
            if (kill) { rem++; continue; }
            if (w != i) memmove(&d[(size_t)w * M], v, M * sizeof(int16_t));
            w++;
        }
        if (rem) { N = w; pool_kills += rem; ST.removed += rem; exact_ok += rem; if (pi > 0) { swap(P[pi], P[pi / 2]); } }
    }
    D.N = N; d.resize((size_t)N * M);
}
// Farkas cuts on a domain
static int FMODE = 0;
static void filter_support(const Node &nd, Dom &D, int tm, int fm) {
    int mi = D.mi; Mod &m = mods[mi]; int M = m.M; static vector<double> mu, score; class_activity(mi, mu);
    int N = D.N; vector<int16_t> &d = D.d; score.resize(N); static vector<char> alive; alive.assign(N, 0);
    for (int i = 0; i < N; i++) { double s_ = 0; const int16_t *v = &d[(size_t)i * M]; for (int r = 0; r < M; r++) { double e = v[r] - mu[r]; s_ += e * e / m.sz[r]; } score[i] = s_; }
    vector<int> rows; vector<double> vals; base_rows(nd, rows, vals, -1);
    vector<int> w(M); int tests = 0, feas = 0;
    while (tests < tm && feas < fm && N > 0) {
        int bi = -1; double bs = -1; for (int i = 0; i < N; i++) if (!alive[i] && score[i] > bs) { bs = score[i]; bi = i; }
        if (bi < 0) break;
        const int16_t *vb = &d[(size_t)bi * M]; double mx = 0; for (int r = 0; r < M; r++) mx = max(mx, fabs((vb[r] - mu[r]) / m.sz[r]));
        if (mx <= 0) { alive[bi] = 1; feas++; continue; }
        for (int r = 0; r < M; r++) w[r] = (int)lround((vb[r] - mu[r]) / m.sz[r] / mx * 1000.0);
        cc.assign(N_, 0.0); for (int r = 0; r < M; r++) if (w[r]) for (int p : m.members[r]) cc[p] = w[r] / 1000.0;
        double v; tests++; ST.viaLP++;
        if (lp_maximize_core(&v, 20000) != 0) { alive[bi] = 1; feas++; continue; }
        // the proved bound, in the units of w / 1000: multiply through
        ll b; if (!exact_bound_form_scaled(mi, w, rows, vals, b)) { alive[bi] = 1; feas++; continue; }
        int wr = 0; ll rem = 0; bool hit = false;
        for (int i = 0; i < N; i++) {
            const int16_t *u = &d[(size_t)i * M]; ll t = 0; for (int r = 0; r < M; r++) t += w[r] * u[r];
            bool kill = t > b;
            if (i == bi) hit = kill;
            if (kill) { rem++; continue; }
            if (wr != i) { memmove(&d[(size_t)wr * M], u, M * sizeof(int16_t)); score[wr] = score[i]; alive[wr] = alive[i]; }
            wr++;
        }
        N = wr; ST.removed += rem; exact_ok += rem;
        if (rem) { ST.cuts++; feas = 0; }
        if (!hit) { feas++; for (int i = 0; i < N; i++) { bool eq = true; for (int r = 0; r < M; r++) if (d[(size_t)i * M + r] != vb[r]) { eq = false; break; } if (eq) { alive[i] = 1; break; } } }
    }
    D.N = N; d.resize((size_t)N * M);
}
static ll TI[12], TN[12]; struct PT { int t; ll i0; PT(int t_) : t(t_), i0(L.iters) {} ~PT() { TI[t] += L.iters - i0; TN[t]++; } };
static double FDS[64][8];
static void filter_domain_(const Node &nd, Dom &D, int tm, int fm);
static void filter_domain(const Node &nd, Dom &D, int tm, int fm) { PT pt_(0);
    int mi_ = D.mi; ll i0 = L.iters, s0 = L.solves; int N0 = D.N; filter_domain_(nd, D, tm, fm); if (mi_ >= 0 && mi_ < 64) { double *o = FDS[mi_]; o[0] += 1; o[1] += L.iters - i0; o[2] += L.solves - s0; o[3] += N0; o[4] += N0 - D.N; o[5] += D.N == 0; o[6] += D.N == 1 && N0 > 1; o[7] += N0 == 1; }
}
static void filter_domain_(const Node &nd, Dom &D, int tm, int fm) {
    if (D.N == 0) return; double t0 = now();
    if (FMODE == 1) { filter_support(nd, D, tm, fm); ST.tFilter += now() - t0; return; }
    pool_apply(nd, D); if (D.N == 0) { ST.tFilter += now() - t0; return; }
    int mi = D.mi; Mod &m = mods[mi]; int M = m.M;
    static vector<double> mu, score, row; class_activity(mi, mu);
    score.resize(D.N); for (int i = 0; i < D.N; i++) { double s = 0; const int16_t *v = &D.d[(size_t)i * M]; for (int r = 0; r < M; r++) { double e = v[r] - mu[r]; s += e * e / m.sz[r]; } score[i] = s; }
    static vector<char> alive; alive.assign(D.N, 0);
    vector<int> rows0; vector<double> vals0; base_rows(nd, rows0, vals0, mi);
    int k0 = rows0.size(); vector<int> rows = rows0; vector<double> vals = vals0; rows.resize(k0 + M); vals.resize(k0 + M); for (int r = 0; r < M; r++) rows[k0 + r] = m.pos + r;
    int tests = 0, feas = 0; int N = D.N; vector<int16_t> &d = D.d; bool saved = false;
    while (tests < tm && feas < fm && N > 0) {
        int bi = -1; double bs = -1; for (int i = 0; i < N; i++) if (!alive[i] && score[i] > bs) { bs = score[i]; bi = i; }
        if (bi < 0) break;
        for (int r = 0; r < M; r++) vals[k0 + r] = d[(size_t)bi * M + r] / m.norm[r];
        if (RESTORE) {
            if (!saved) { static vector<double> v0; v0 = vals; for (int r = 0; r < M; r++) v0[k0 + r] = mu[r] / m.norm[r]; lp_rows(rows, v0); lp_feasible(); lp_save(); saved = true; }
            else lp_restore();
        }
        lp_rows(rows, vals); int st = lp_feasible(); tests++; ST.viaLP++;
        if (st != 1) { alive[bi] = 1; feas++; continue; }
        feas = 0; ST.cuts++;
        // a stronger cut: pull the target back toward the centre while it stays infeasible, so that the ray comes from nearer the boundary of what is possible
        if (PULL > 0) {
            static vector<double> rayb; rayb = L.ray; double tl = 1.0;
            for (int step = 0; step < PULL; step++) {
                double t = tl * PULLF; for (int r = 0; r < M; r++) vals[k0 + r] = (mu[r] + t * (d[(size_t)bi * M + r] - mu[r])) / m.norm[r];
                lp_rows(rows, vals); int st2 = lp_feasible(); tests++; ST.viaLP++;
                if (st2 != 1) break;
                rayb = L.ray; tl = t;
            }
            L.ray = rayb;
            for (int r = 0; r < M; r++) vals[k0 + r] = d[(size_t)bi * M + r] / m.norm[r];
        }
        // the cut: y over the active rows
        int n = N_; static vector<double> c; c.assign(n, 0.0); double K = 0;
        for (int q = 0; q < (int)rows.size(); q++) { double yq = L.ray[rows[q]]; if (yq == 0.0) continue; const double *Ai = &L.A[(size_t)rows[q] * n]; for (int j = 0; j < n; j++) c[j] += yq * Ai[j]; if (q < k0) K += yq * vals[q]; }
        double budget = 0; for (int j = 0; j < n; j++) { if (FZ[j]) K -= c[j] * FZ[j]; else budget += fabs(c[j]); }
        { double Kall = K; for (int r = 0; r < M; r++) Kall += L.ray[m.pos + r] * vals[k0 + r]; if (!(fabs(Kall) > budget * (1 + 1e-9) + 1e-7)) { rayfail++; alive[bi] = 1; feas++; continue; } }
        static vector<double> eta; eta.resize(M); for (int r = 0; r < M; r++) eta[r] = L.ray[m.pos + r] / m.norm[r];
        // the integer form of the same cut
        static vector<double> yy; yy.resize(rows.size()); for (int q = 0; q < (int)rows.size(); q++) yy[q] = L.ray[rows[q]];
        long double sc = y_scale(rows, yy.data()); static vector<ll> ints;
        if (!build_w(rows, yy.data(), sc, DD0, SS0, ints)) { exact_fail++; alive[bi] = 1; feas++; continue; }
        LL Tot = w_free(), TotAll = w_total(), K0 = -w_known(); static vector<LL> cD; cD.assign(M, 0);
        for (int q = 0; q < (int)rows.size(); q++) if (ints[q]) { if (q < k0) K0 += DD0 * ints[q] * raw_of(rows[q], vals[q]); else cD[rows[q] - m.pos] = DD0 * ints[q]; }
        int w = 0; ll rem = 0; bool hit = false;
        for (int i = 0; i < N; i++) {
            const int16_t *v = &d[(size_t)i * M]; double s = K; for (int r = 0; r < M; r++) s += eta[r] * v[r];
            bool kill = false;
            if (fabs(s) > budget * (1 - 1e-6)) { LL e = K0; for (int r = 0; r < M; r++) e += cD[r] * v[r]; kill = labs128(e) > Tot; if (i == bi) hit = kill; }
            else if (i == bi) hit = false;
            if (kill) { rem++; exact_ok++; continue; }
            if (w != i) { memmove(&d[(size_t)w * M], v, M * sizeof(int16_t)); score[w] = score[i]; alive[w] = alive[i]; }
            w++;
        }
        N = w; ST.removed += rem;
        if (POOLMAX > 0 && rem > 0) {
            if ((int)POOL.size() < (int)mods.size()) POOL.resize(mods.size());
            PoolCut C; C.Tot = TotAll; C.Totf = (double)TotAll;   // without the signs: valid in every node
             C.cD = cD; C.eta.resize(M); for (int r = 0; r < M; r++) C.eta[r] = (double)cD[r];
            for (int q = 0; q < k0; q++) { C.rows.push_back(rows[q]); C.c.push_back(ints[q]); }
            auto &P = POOL[mi]; P.insert(P.begin(), std::move(C)); if ((int)P.size() > POOLMAX) P.pop_back();
        }
        if (!hit) { exact_fail++; feas++; for (int i = 0; i < N; i++) { bool eq = true; for (int r = 0; r < M; r++) if (d[(size_t)i * M + r] != (int16_t)llround(vals[k0 + r] * m.norm[r])) { eq = false; break; } if (eq) alive[i] = 1; } }
    }
    D.N = N; d.resize((size_t)N * M);
    ST.tFilter += now() - t0;
}
// equalities on all of D: returns how many rows were added
static int hull_rows_(Node &nd, Dom &D);
static int hull_rows(Node &nd, Dom &D) { double t0 = now(); int r = hull_rows_(nd, D); ST.tHull += now() - t0; return r; }
static int hull_rows_(Node &nd, Dom &D) { PT pt_(1);
    int M = mods[D.mi].M; if (D.N < 2) return 0;
    // elimination on differences, on a sample of rows; integer pivots kept as doubles
    int take = min(D.N, SAMPLE); static vector<double> X; X.resize((size_t)take * M); int step = D.N / take;
    for (int i = 0; i < take; i++) { int ii = i * step; for (int r = 0; r < M; r++) X[(size_t)i * M + r] = D.d[(size_t)ii * M + r] - D.d[r]; }
    vector<int> pivcol; int row = 0;
    for (int c = 0; c < M && row < take; c++) {
        int p = -1; double best = 1e-7; for (int i = row; i < take; i++) { double v = fabs(X[(size_t)i * M + c]); if (v > best) { best = v; p = i; } }
        if (p < 0) continue;
        if (p != row) for (int j = 0; j < M; j++) swap(X[(size_t)p * M + j], X[(size_t)row * M + j]);
        double iv = 1.0 / X[(size_t)row * M + c]; for (int j = 0; j < M; j++) X[(size_t)row * M + j] *= iv;
        for (int i = 0; i < take; i++) if (i != row) { double f = X[(size_t)i * M + c]; if (f != 0.0) for (int j = 0; j < M; j++) X[(size_t)i * M + j] -= f * X[(size_t)row * M + j]; }
        pivcol.push_back(c); row++;
    }
    int rank = row; if (D.rank >= 0 && rank >= D.rank) return 0; D.rank = rank;
    // the null space: for each free column f, v_f = 1 and v_pivot = - X[row][f].  Rational with small denominators: scale to integers.
    vector<char> isp(M, 0); for (int c : pivcol) isp[c] = 1; int added = 0;
    vector<pair<int, double>> fresh; bool allok = true;
    for (int fc = 0; fc < M; fc++) if (!isp[fc]) {
        vector<double> v(M, 0.0); v[fc] = 1.0; for (int q = 0; q < rank; q++) v[pivcol[q]] = -X[(size_t)q * M + fc];
        double scale = 1.0; bool ok = false;
        for (int den = 1; den <= 720 && !ok; den++) { ok = true; for (int r = 0; r < M; r++) { double t = v[r] * den; if (fabs(t - round(t)) > 1e-6) { ok = false; break; } } if (ok) scale = den; }
        if (!ok) { allok = false; continue; }
        vector<int> c(M); ll g = 0; for (int r = 0; r < M; r++) { c[r] = (int)round(v[r] * scale); ll a_ = llabs(c[r]); while (a_) { ll t = g % a_; g = a_; a_ = t; } }
        if (g > 1) for (int r = 0; r < M; r++) c[r] /= g;
        ll val0 = 0; for (int r = 0; r < M; r++) val0 += c[r] * D.d[r]; bool all = true;
        for (int i = 1; i < D.N && all; i++) { ll s_ = 0; const int16_t *u = &D.d[(size_t)i * M]; for (int r = 0; r < M; r++) s_ += c[r] * u[r]; if (s_ != val0) all = false; }
        if (!all) { allok = false; continue; }
        int nz = 0, last = -1; for (int r = 0; r < M; r++) if (c[r]) { nz++; last = r; }
        pair<int, double> fr; if (nz == 1) { fr = {mods[D.mi].pos + last, mods[D.mi].norm[last] / c[last]}; } else { fr = form_row(D.mi, c); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {D.mi, c}; }
        fresh.push_back({fr.first, (double)val0 / fr.second});
    }
    if (HULLSWAP && allok) {
        // the hull is everything linear that the domain knows: earlier rows on this modulus are implied by it
        vector<pair<int, double>> kept; for (auto &f : nd.fixed) if (f.first < M_ || rowform[f.first].first != D.mi) kept.push_back(f);
        size_t before = nd.fixed.size();
        vector<char> oldset(L.K + 1, 0); for (auto &f : nd.fixed) oldset[f.first] = 1;
        for (auto &f : fresh) if (!oldset[f.first]) added++;
        for (auto &f : fresh) kept.push_back(f);
        nd.fixed.swap(kept); ST.hull += added; (void)before;
        return added;
    }
    for (auto &f : fresh) { bool have = false; for (auto &h : nd.fixed) if (h.first == f.first) { have = true; break; } if (!have) { nd.fixed.push_back(f); added++; ST.hull++; } }
    return added;
}
struct Split { int k = 0; int di = -1; vector<int> c; int direct_mi = -1; vector<ll> vals; bool sym = false; };
static int STRONG = 0; static vector<Split> cands;
static void note_cand(int k, int di, const vector<int> &c) { if (STRONG <= 0) return; if ((int)cands.size() < STRONG || k < cands.back().k) { Split s; s.k = k; s.di = di; s.c = c; int pos = cands.size(); while (pos > 0 && cands[pos - 1].k > k) pos--; cands.insert(cands.begin() + pos, s); if ((int)cands.size() > STRONG) cands.pop_back(); } }
static int count_values(const Dom &D, const int *c, int take, int step) {
    int M = mods[D.mi].M; static vector<ll> vals; vals.resize(take);
    for (int i = 0; i < take; i++) { const int16_t *u = &D.d[(size_t)(i * step) * M]; ll s = 0; for (int r = 0; r < M; r++) s += c[r] * u[r]; vals[i] = s; }
    sort(vals.begin(), vals.end()); int k = 1; for (int i = 1; i < take; i++) if (vals[i] != vals[i - 1]) k++; return k;
}
static void best_split(const Dom &D, int di, Split &best) {
    double t0 = now(); Mod &m = mods[D.mi]; int M = m.M; int take = min(D.N, SAMPLE); int step = D.N / take; vector<int> c(M, 0);
    vector<int> freec; for (int r = 0; r < M; r++) { c[r] = 1; int k = count_values(D, c.data(), take, step); if (k > 1) { note_cand(k, di, c); freec.push_back(r); if (best.di < 0 || k < best.k) { best.k = k; best.di = di; best.c.assign(M, 0); best.c[r] = 1; } } c[r] = 0; }
    if (best.k > 2) {
        for (size_t a = 0; a < freec.size(); a++) for (size_t b = a + 1; b < freec.size(); b++) for (int s = -1; s <= 1; s += 2) {
            c[freec[a]] = 1; c[freec[b]] = s; int k = count_values(D, c.data(), take, step); if (k > 1) note_cand(k, di, c); c[freec[a]] = 0; c[freec[b]] = 0;
            if (k > 1 && k < best.k) { best.k = k; best.di = di; best.c.assign(M, 0); best.c[freec[a]] = 1; best.c[freec[b]] = s; }
        }
    }
    if (best.k > 2) for (auto &w : m.W) { int k = count_values(D, w.data(), take, step); if (k > 1) note_cand(k, di, w); if (k > 1 && k < best.k) { best.k = k; best.di = di; best.c = w; } }
    ST.tSplit += now() - t0;
}
static bool out_of_time = false; static double deadline = 1e300;
static FILE *openlog = nullptr;
static vector<vector<int>> dummy;
static int choose_seed = 0; static mt19937_64 RNG(1);
static bool pathlog = false; static bool follow = false; static bool knuth = false; static double kw = 1, kest = 1, kcost = 0;
static void pin_all(Node &nd, Dom &D) { Mod &m = mods[D.mi]; nd.fullval[D.mi].assign(m.M, 0); if (nd.G) { vector<ll> vv(m.M); for (int r = 0; r < m.M; r++) vv[r] = D.d[r]; for (int bit : {1, 2, 4}) if ((nd.G & bit) && !invariant_under(bit, vv)) nd.G &= ~bit; } for (int r = 0; r < m.M; r++) { int v = D.d[r]; nd.fullval[D.mi][r] = v; bool have = false; for (auto &f : nd.fixed) if (f.first == m.pos + r) { f.second = v / m.norm[r]; have = true; break; } if (!have) nd.fixed.push_back({m.pos + r, v / m.norm[r]}); } nd.full |= 1u << D.mi; D.N = 0; D.d.clear(); }
// returns 0 closed, 1 split (fills sp), 2 open

static int DIRECTM_dummy = 0;
// Short dual forms of moduli without a list: proved range and lattice spacing.  Returns 0 closed, 1 a form fixed, 2 a split in sp, 3 nothing.
static int SKIPIMPLIED = 0; static ll skip_implied = 0; static double tImplied = 0;
// Which forms of modulus mi still carry information: the norm of each after projecting off the active rows, in units of the step.  sig[wi] = 0 if implied.
static vector<double> Qcache; static int Qk = 0;
static vector<int> Qrows; static vector<int> Qcount; static int qrows_reg = (Qrows_ptr = &Qrows, 0);   // the rows behind Qcache, and how many orthonormal vectors the first i of them gave
static void make_q(const vector<int> &rows) {
    int n = N_, k = rows.size(); if ((int)Qcache.size() < k * n) Qcache.resize((size_t)k * n);
    int same = 0, lim = min<int>(k, Qrows.size()); while (same < lim && Qrows[same] == rows[same]) same++;
    Qrows.resize(same); Qcount.resize(same); int kk = same ? Qcount[same - 1] : 0;
    for (int q = same; q < k; q++) {
        double *__restrict__ v = &Qcache[(size_t)kk * n]; memcpy(v, &L.A[(size_t)rows[q] * n], n * sizeof(double));
        if (rows[q] >= M_) for (int a = 0; a < kk; a++) { const double *__restrict__ qa = &Qcache[(size_t)a * n]; double c = 0; for (int j = 0; j < n; j++) c += qa[j] * v[j]; for (int j = 0; j < n; j++) v[j] -= c * qa[j]; }
        double nr = 0; for (int j = 0; j < n; j++) nr += v[j] * v[j]; nr = sqrt(nr); if (nr >= 1e-8) { nr = 1 / nr; for (int j = 0; j < n; j++) v[j] *= nr; kk++; }
        Qrows.push_back(rows[q]); Qcount.push_back(kk);
    }
    Qk = kk;
}
static vector<double> Cm; 
static void make_c(int mi) {
    Mod &m = mods[mi]; int M = m.M, n = N_; static vector<double> X; X.assign((size_t)M * Qk, 0.0);
    for (int q = 0; q < Qk; q++) { const double *qa = &Qcache[(size_t)q * n]; double *xq = &X[(size_t)q * M]; for (int r = 0; r < M; r++) { double s = 0; for (int p : m.members[r]) s += qa[p]; xq[r] = s; } }
    Cm.assign((size_t)M * M, 0.0);
    for (int q = 0; q < Qk; q++) { const double *xq = &X[(size_t)q * M]; for (int a = 0; a < M; a++) { double f = xq[a]; if (f == 0.0) continue; double *ca = &Cm[(size_t)a * M]; for (int b = 0; b < M; b++) ca[b] -= f * xq[b]; } }
    for (int r = 0; r < M; r++) Cm[(size_t)r * M + r] += (double)m.sz[r];
}
static inline double form_var(int mi, const vector<int> &w) { Mod &m = mods[mi]; int M = m.M; double var = 0; for (int a = 0; a < M; a++) { int wa = w[a]; if (!wa) continue; const double *ca = &Cm[(size_t)a * M]; double s = 0; for (int b = 0; b < M; b++) s += ca[b] * w[b]; var += wa * s; } return var; }
static int direct_scan(Node &nd, Split &sp, int maxm, int maxq, int limitk = 1 << 30) { PT pt_(2);
    feasible_base(nd);
    static vector<int> brows; static vector<double> bvals; base_rows(nd, brows, bvals, -1);
    if (SKIPIMPLIED) { double t0_ = now(); make_q(brows); tImplied += now() - t0_; }
    int bk = 1 << 30, bmi = -1; vector<int> bc; vector<ll> bvalsf; bool fixedone = false, dead = false;
    vector<char> have(L.K + 1, 0); for (auto &f : nd.fixed) have[f.first] = 1;
    int usedm = 0;
    for (int M : want) {
        int mi = modidx[M]; if (nd.full >> mi & 1) continue; Mod &m = mods[mi]; if (m.W.empty()) continue;
        bool listed = false; for (auto &D : nd.dom) if (D.mi == mi) listed = true; if (listed) continue;
        int tried_ = 0; if (SKIPIMPLIED) { double t0_ = now(); make_c(mi); tImplied += now() - t0_; }
        for (size_t wi = 0; wi < m.W.size() && tried_ < maxq; wi++) {
            const vector<int> &w = m.W[wi]; ll st_ = m.Wstep[wi]; if (st_ <= 0) continue;
            auto it = forms.find(FormKey{mi, w}); if (it != forms.end() && it->second.first < (int)have.size() && have[it->second.first]) continue;
            if (SKIPIMPLIED) { double vr = form_var(mi, w); if (vr < 1e-9 * st_ * st_) { skip_implied++; continue; } }
            tried_++;
            cc.assign(N_, 0.0); for (int r = 0; r < m.M; r++) if (w[r]) for (int p : m.members[r]) cc[p] = w[r];
            double v; ll hi = 0, lo = 0; for (int r = 0; r < m.M; r++) hi += llabs((ll)w[r]) * m.sz[r]; lo = -hi; ll b;
            if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(mi, w, 1, L.act, bvals, b)) hi = min(hi, b);
            for (int j = 0; j < N_; j++) cc[j] = -cc[j];
            if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(mi, w, -1, L.act, bvals, b)) lo = max(lo, -b);
            ll c0 = m.Wc0[wi]; ll v0 = lo + (((c0 - lo) % st_) + st_) % st_; vector<ll> vl; for (ll t = v0; t <= hi; t += st_) vl.push_back(t);
            if (vl.empty()) { dead = true; break; }
            if ((int)vl.size() < bk) { bk = vl.size(); bmi = mi; bc = w; bvalsf = vl; }
            if (vl.size() == 1) { fixedone = true; break; }
        }
        if (tried_ > 0) usedm++;
        if (dead || fixedone || usedm >= maxm) break;
    }
    if (dead) { exact_ok++; ST.direct_closed++; return 0; }
    if (bmi < 0) return 3;
    auto fr = form_row(bmi, bc); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {bmi, bc};
    if (fixedone) { nd.fixed.push_back({fr.first, (double)bvalsf[0] / fr.second}); ST.direct_fixed++; return 1; }
    if (bk >= limitk) return 3;
    sp = Split(); sp.k = bk; sp.direct_mi = bmi; sp.c = bc; sp.vals = bvalsf; ST.direct_split++; return 2;
}

// Forms ranked by the geometry of this node: sigma = the norm of the form after projecting off the active rows, in units of its grid step.  It predicts the LP width nearly exactly.
static int SCANMODE = 0, SCANQ = 4; static ll scan_implied = 0, scan_ranked = 0; static double tRank = 0;
struct FormRank { double score, sigma, dist; int mi, wi; };
static vector<FormRank> FR;
static void rank_forms(const Node &nd, const vector<int> &rows) {
    double t0 = now(); FR.clear(); int n = N_, k = rows.size();
    static vector<double> Q, X, C, mu, xp; Q.resize((size_t)k * n); int kk = 0;
    for (int q = 0; q < k; q++) {
        double *v = &Q[(size_t)kk * n]; memcpy(v, &L.A[(size_t)rows[q] * n], n * sizeof(double));
        if (rows[q] >= M_) for (int a = 0; a < kk; a++) { const double *qa = &Q[(size_t)a * n]; double c = 0; for (int j = 0; j < n; j++) c += qa[j] * v[j]; for (int j = 0; j < n; j++) v[j] -= c * qa[j]; }
        double nr = 0; for (int j = 0; j < n; j++) nr += v[j] * v[j]; nr = sqrt(nr); if (nr < 1e-8) continue; nr = 1 / nr; for (int j = 0; j < n; j++) v[j] *= nr; kk++;
    }
    lp_point(xp);
    for (int M : want) {
        int mi = modidx[M]; if (nd.full >> mi & 1) continue; Mod &m = mods[mi]; if (m.W.empty()) continue;
        bool listed = false; for (auto &D : nd.dom) if (D.mi == mi) listed = true; if (listed) continue;
        X.assign((size_t)M * kk, 0.0); mu.assign(M, 0.0);
        for (int q = 0; q < kk; q++) { const double *qa = &Q[(size_t)q * n]; double *xq = &X[(size_t)q * M]; for (int r = 0; r < M; r++) { double s = 0; for (int p : m.members[r]) s += qa[p]; xq[r] = s; } }
        for (int r = 0; r < M; r++) { double s = 0; for (int p : m.members[r]) s += xp[p]; mu[r] = s; }
        C.assign((size_t)M * M, 0.0);
        for (int q = 0; q < kk; q++) { const double *xq = &X[(size_t)q * M]; for (int a = 0; a < M; a++) { double f = xq[a]; if (f == 0.0) continue; double *ca = &C[(size_t)a * M]; for (int b = 0; b < M; b++) ca[b] -= f * xq[b]; } }
        for (int r = 0; r < M; r++) C[(size_t)r * M + r] += (double)m.sz[r];
        for (size_t wi = 0; wi < m.W.size(); wi++) {
            const vector<int> &w = m.W[wi]; ll st_ = m.Wstep[wi]; if (st_ <= 0) continue;
            double var = 0, f = 0; for (int a = 0; a < M; a++) { int wa = w[a]; if (!wa) continue; f += wa * mu[a]; const double *ca = &C[(size_t)a * M]; double s = 0; for (int b = 0; b < M; b++) s += ca[b] * w[b]; var += wa * s; }
            double sig = var > 0 ? sqrt(var) / st_ : 0; double pos = (f - m.Wc0[wi]) / st_; double dist = fabs(pos - round(pos));
            if (sig < 1e-6) { scan_implied++; if (dist < 1e-5) continue; sig = 1e-6; }
            FormRank fr; fr.sigma = sig; fr.dist = dist; fr.mi = mi; fr.wi = wi;
            fr.score = (SCANMODE == 2 || SCANMODE == 4) ? -dist / sig : sig;
            FR.push_back(fr); scan_ranked++;
        }
        if (SCANMODE >= 3 && !FR.empty()) break;
    }
    tRank += now() - t0;
}
static int scan_forms(Node &nd, Split &sp, int maxq, int limitk) { SPLIT_SAVED = false;
    feasible_base(nd);
    static vector<int> brows; static vector<double> bvals; base_rows(nd, brows, bvals, -1);
    rank_forms(nd, brows);
    if (FR.empty()) return 3;
    int q = min<int>(maxq, FR.size()); partial_sort(FR.begin(), FR.begin() + q, FR.end(), [](const FormRank &a, const FormRank &b) { return a.score < b.score; });
    int bk = 1 << 30, bmi = -1; vector<int> bc; vector<ll> bvalsf;
    for (int i = 0; i < q; i++) {
        int mi = FR[i].mi; Mod &m = mods[mi]; const vector<int> &w = m.W[FR[i].wi]; ll st_ = m.Wstep[FR[i].wi];
        { auto it_ = forms.find(FormKey{mi, w}); if (it_ != forms.end()) { bool have_ = false; for (auto &f_ : nd.fixed) if (f_.first == it_->second.first) have_ = true; if (have_) continue; } }   // pinned already: nothing to learn, and pinning it again would never end
        CUP.mi = CDN.mi = -2;
        cc.assign(N_, 0.0); for (int r = 0; r < m.M; r++) if (w[r]) for (int p : m.members[r]) cc[p] = w[r];
        double v; ll hi = 0, lo = 0; for (int r = 0; r < m.M; r++) hi += llabs((ll)w[r]) * m.sz[r]; lo = -hi; ll b;
        if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(mi, w, 1, L.act, bvals, b)) hi = min(hi, b);
        for (int j = 0; j < N_; j++) cc[j] = -cc[j];
        if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(mi, w, -1, L.act, bvals, b)) lo = max(lo, -b);
        ll c0 = m.Wc0[FR[i].wi]; ll v0 = lo + (((c0 - lo) % st_) + st_) % st_; vector<ll> vl; for (ll t = v0; t <= hi; t += st_) vl.push_back(t);
        if (vl.empty()) { if (CERTF) cert_bounds(mi, w, 0, 0, CUP, CDN); exact_ok++; ST.direct_closed++; return 0; }
        if ((int)vl.size() < bk) { bk = vl.size(); bmi = mi; bc = w; bvalsf = vl; if (CERTF) { SAVEUP = CUP; SAVEDN = CDN; SPLIT_SAVED = true; } }
        if (vl.size() == 1) break;
    }
    if (bmi < 0) return 3;
    auto fr = form_row(bmi, bc); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {bmi, bc};
    if (bk == 1) { if (CERTF) { cert_bounds(bmi, bc, 0, 1, SAVEUP, SAVEDN); SPLIT_SAVED = false; } nd.fixed.push_back({fr.first, (double)bvalsf[0] / fr.second}); ST.direct_fixed++; return 1; }
    if (bk >= limitk) return 3;
    sp = Split(); sp.k = bk; sp.direct_mi = bmi; sp.c = bc; sp.vals = bvalsf; ST.direct_split++; return 2;
}


struct ClosedForm { FormCert hi, lo; ll st, c0; };
static vector<ClosedForm> CPOOL; static size_t CPOOL_next = 0; static ll cpool_hits = 0, cpool_tests = 0; static double tCpool = 0;
static vector<char> cp_known; static vector<ll> cp_raw;
static bool cpool_close(const Node &nd) {
    if (!CERTPOOL || CPOOL.empty()) return false;
    double t0_ = now();
    cp_known.assign(L.K, 0); cp_raw.resize(L.K);
    for (int i = 0; i < M_; i++) { cp_known[i] = 1; cp_raw[i] = 0; }
    for (auto &f : nd.fixed) { cp_known[f.first] = 1; cp_raw[f.first] = raw_of(f.first, f.second); }
    LL T = DD0 * (LL)SS0;
    for (auto &E : CPOOL) {
        bool ok = true; LL Kh = 0, Kl = 0;
        for (size_t i = 0; i < E.hi.rows.size(); i++) { int rw = E.hi.rows[i]; if (rw >= (int)cp_known.size() || !cp_known[rw]) { ok = false; break; } Kh += (LL)E.hi.c[i] * cp_raw[rw]; }
        if (!ok) continue;
        for (size_t i = 0; i < E.lo.rows.size(); i++) { int rw = E.lo.rows[i]; if (rw >= (int)cp_known.size() || !cp_known[rw]) { ok = false; break; } Kl += (LL)E.lo.c[i] * cp_raw[rw]; }
        if (!ok) continue;
        cpool_tests++;
        LL bh = E.hi.tot + DD0 * Kh, bl = E.lo.tot + DD0 * Kl; ll hi = (ll)(bh >= 0 ? bh / T : -((-bh + T - 1) / T)), lo = -(ll)(bl >= 0 ? bl / T : -((-bl + T - 1) / T));
        ll v0 = lo + (((E.c0 - lo) % E.st) + E.st) % E.st;
        if (v0 > hi) { cpool_hits++; exact_ok++; tCpool += now() - t0_; return true; }
    }
    tCpool += now() - t0_; return false;
}
static void cpool_add(const FormCert &hi, const FormCert &lo, ll st, ll c0) {
    if (!CERTPOOL) return;
    ClosedForm E; E.hi = hi; E.lo = lo; E.st = st; E.c0 = c0;
    if ((int)CPOOL.size() < CERTPOOL) CPOOL.push_back(std::move(E)); else { CPOOL[CPOOL_next] = std::move(E); CPOOL_next = (CPOOL_next + 1) % CPOOL.size(); }
}
static int openwhy = 0; static double SCANTAU = 1.5, RHO = 4.0; static ll scan_tests = 0, scan_fix = 0, scan_close = 0, scan_many = 0;
// the proved range of the form, stopping as soon as two grid values are inside: 0 none, 1 one (value), 2 at least two
struct LPF { vector<int> act, basis; vector<signed char> at; vector<pair<int, signed char>> atl; vector<double> Binv, xB; int pivots = 0, k = 0; };
static int SIBREST = 0;
static inline void lpf_save(LPF &S) { S.act = L.act; S.k = L.k; S.basis = L.basis; S.at = L.at; S.atl.clear(); for (int i = 0; i < L.K; i++) if (L.atl[i]) S.atl.push_back({i, L.atl[i]}); S.Binv = L.Binv; S.xB = L.xB; S.pivots = L.pivots; }
static inline void lpf_load(const LPF &S) { L.act = S.act; L.k = S.k; L.basis = S.basis; L.at = S.at; fill(L.atl.begin(), L.atl.end(), (signed char)0); for (auto &e : S.atl) L.atl[e.first] = e.second; L.Binv = S.Binv; L.xB = S.xB; L.pivots = S.pivots; dn_valid = false; }
static LPF SPLIT_U; static bool SPLIT_U_ok = false;
struct LPS2 { vector<int> basis; vector<signed char> at, atl; vector<double> Binv, xB; int pivots = 0; };
static LPS2 RS0, RSU, RSD; static int RTNEAR = 0; static int RTS_MI = -1, RTS_WI = -1, RTS_K = -1; static ll rts_hit = 0, rts_miss = 0;
static inline void lps_save(LPS2 &S) { S.basis = L.basis; S.at = L.at; S.atl = L.atl; S.Binv = L.Binv; S.xB = L.xB; S.pivots = L.pivots; }
static inline void lps_load(const LPS2 &S) { L.basis = S.basis; L.at = S.at; L.atl = S.atl; L.Binv = S.Binv; L.xB = S.xB; L.pivots = S.pivots; dn_valid = false; }
static int RTDUAL = 0; static int RT2_MI = -1, RT2_WI = -1; static ll RT2_A = 0, RT2_B = 0; static ll rt2_fail = 0, rt2_proved = 0;
static inline LL fdiv128(LL a, LL b) { LL q = a / b; if ((a % b != 0) && ((a < 0) != (b < 0))) q--; return q; }
static inline LL cdiv128(LL a, LL b) { LL q = a / b; if ((a % b != 0) && ((a < 0) == (b < 0))) q++; return q; }
// After lp_feasible said infeasible on rows whose last is the form's: what the ray proves about the form on every point of the node, in exact integers.  closed: the rows without the form already have no point.
static bool exact_range_ray(const vector<int> &rows, const vector<double> &vals, ll target, ll &lo_, ll &hi_, bool &closed) {
    static vector<double> y; int nr = rows.size(); y.resize(nr); for (int q = 0; q < nr; q++) y[q] = L.ray[rows[q]];
    long double sc = y_scale(rows, y.data()); static vector<ll> ints; const LL DD1 = ((LL)1) << 58; const double SS1 = 4294967296.0;
    for (int attempt = 0; attempt < 2; attempt++) {
        LL DD = attempt ? DD1 : DD0; double SS = attempt ? SS1 : SS0;
        if (!build_w(rows, y.data(), sc, DD, SS, ints)) continue;
        LL fr_ = w_free(); if (fr_ >= (((LL)1) << 125)) continue;
        LL K = 0; for (int q = 0; q + 1 < nr; q++) if (ints[q]) K += DD * ints[q] * raw_of(rows[q], vals[q]);
        LL c = DD * ints[nr - 1], kn = w_known(), Lo = kn - fr_ - K, Hi = kn + fr_ - K;   // sum W a = K + c F lies in [kn - fr_, kn + fr_]
        if (c == 0) { if (Lo > 0 || Hi < 0) { closed = true; return true; } continue; }
        LL l_, h_; if (c > 0) { l_ = cdiv128(Lo, c); h_ = fdiv128(Hi, c); } else { l_ = cdiv128(Hi, c); h_ = fdiv128(Lo, c); }
        const LL big = ((LL)1) << 60; if (l_ > big) l_ = big; if (l_ < -big) l_ = -big; if (h_ > big) h_ = big; if (h_ < -big) h_ = -big;
        if ((LL)target < l_ || (LL)target > h_) { lo_ = (ll)l_; hi_ = (ll)h_; closed = false; return true; }
    }
    return false;
}
// the row added last leaves the LP and the point stays feasible for the others: its slack enters the basis in one primal step
static void rt2_drop(const vector<int> &brows, const vector<double> &bvals) {
    if (L.k == (int)brows.size()) return;
    int k = L.k, n = L.n, q = k - 1, frow = L.act[q], sl = n + frow, pos = -1; for (int a = 0; a < k; a++) if (L.basis[a] == sl) pos = a;
    if (pos < 0) {
        double best = 1e300, bg = 0, btg = 0; int r = -1;
        for (int dir = -1; dir <= 1; dir += 2) for (int a = 0; a < k; a++) {
            double g = dir * L.Binv[(size_t)a * k + q]; if (fabs(g) < 1e-8) continue; int b = L.basis[a]; double l, u; if (b < n) { if (FZ[b]) l = u = FZ[b]; else { l = -1; u = 1; } } else { l = L.lo[b - n]; u = L.hi[b - n]; }
            double tg = g > 0 ? u : l, room = max((tg - L.xB[a]) / g, 0.0);
            if (room < best - 1e-10 || (room < best + 1e-10 && fabs(g) > bg)) { best = room; bg = fabs(g); r = a; btg = tg; }
        }
        if (r >= 0) { int lv = L.basis[r]; L.basis[r] = sl; L.atl[frow] = 0; if (lv < n) L.at[lv] = btg > 0 ? 1 : -1; else L.atl[lv - n] = btg >= L.hi[lv - n] ? 1 : -1; }
    }
    lp_rows(brows, bvals);
}
// the same question as range_test, by the dual simplex at the grid values themselves: a value out of reach gives a ray at once, and a value in reach gives the point of the child
struct RT2 { const vector<int> *brows; const vector<double> *bvals; vector<int> r2; vector<double> v2; double fs; ll lo, hi, st, c0; int mi; };
static RT2 R2;
static int rt2_q(ll idx) {
    RT2 &R = R2; ll v = R.c0 + idx * R.st;
    if (v > R.hi || v < R.lo) return 1;
    R.v2.back() = (double)v / R.fs; lp_rows(R.r2, R.v2); ll i0 = L.iters; double t0 = now(); int st = lp_feasible();
    { int ph_ = st == 0 ? 7 : 8; PHI[ph_] += L.iters - i0; PHN[ph_]++; PHT[ph_] += now() - t0; }
    if (st == 0) return 0;
    if (st != 1) { rt2_fail++; return 2; }
    ll l_ = 0, h_ = 0; bool cl = false; double t1 = now();
    bool ok = exact_range_ray(R.r2, R.v2, v, l_, h_, cl); PHT[9] += now() - t1; if (!ok) { rt2_fail++; return 2; }
    rt2_proved++; if (cl) { R.lo = 1; R.hi = 0; return 1; }
    R.hi = min(R.hi, h_); R.lo = max(R.lo, l_); return 1;
}
static void rt2_setup(int mi, const vector<int> &w, ll st_, ll c0, const vector<int> &brows, const vector<double> &bvals) {
    auto fr = form_row(mi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, w};
    RT2 &R = R2; R.brows = &brows; R.bvals = &bvals; R.r2 = brows; R.r2.push_back(fr.first); R.v2 = bvals; R.v2.push_back(0.0); R.fs = fr.second; R.st = st_; R.c0 = c0; R.mi = mi;
    Mod &m = mods[mi]; ll hi = 0; for (int r = 0; r < m.M; r++) hi += llabs((ll)w[r]) * m.sz[r]; R.hi = hi; R.lo = -hi;
}
static inline void rt2_fix_fail(const vector<int> &brows, const vector<double> &bvals) { lp_rows(brows, bvals); lp_feasible(); }
static int range_test(int mi, int wi, const vector<int> &brows, const vector<double> &bvals, ll &val, double &width);
static int range_test2(int mi, int wi, const vector<int> &brows, const vector<double> &bvals, ll &val, double &width) {
    Mod &m = mods[mi]; const vector<int> &w = m.W[wi]; ll st_ = m.Wstep[wi], c0 = m.Wc0[wi]; width = 0; scan_tests++; RT2_MI = -1;
    rt2_drop(brows, bvals);
    double x0 = 0; { static vector<double> xp; lp_point(xp); for (int r = 0; r < m.M; r++) if (w[r]) for (int p : m.members[r]) x0 += w[r] * xp[p]; }
    double pos0 = (x0 - c0) / st_; ll A = (ll)floor(pos0 + 1e-7), B = A + 1;
    rt2_setup(mi, w, st_, c0, brows, bvals); RT2 &R = R2;
    auto count = [&]() { ll v0 = R.lo + (((c0 - R.lo) % st_) + st_) % st_; int cnt = 0; ll last = 0; for (ll t = v0; t <= R.hi; t += st_) { cnt++; last = t; if (cnt > 2) break; } if (cnt == 1) val = last; RTO[min(cnt, 2)]++; return min(cnt, 2); };
    int rb = rt2_q(B); if (rb == 2) { rt2_fix_fail(brows, bvals); return 2; }
    if (rb == 0) {
        int ra = rt2_q(A); if (ra == 2) { rt2_fix_fail(brows, bvals); return 2; }
        if (ra == 0) { RT2_MI = mi; RT2_WI = wi; RT2_A = A; RT2_B = B; return 2; }
        int rc = rt2_q(B + 1); if (rc == 2) { rt2_fix_fail(brows, bvals); return 2; }
        if (rc == 0) { RT2_MI = mi; RT2_WI = wi; RT2_A = B; RT2_B = B + 1; return 2; }
        return count();
    }
    int ra = rt2_q(A); if (ra == 2) { rt2_fix_fail(brows, bvals); return 2; }
    if (ra == 0) {
        int rc = rt2_q(A - 1); if (rc == 2) { rt2_fix_fail(brows, bvals); return 2; }
        if (rc == 0) { RT2_MI = mi; RT2_WI = wi; RT2_A = A - 1; RT2_B = A; return 2; }
    }
    return count();
}
// the whole range of a form about to be split, by the same means.  False if the numbers fail: the primal way then.
static bool range_split2(int mi, int wi, const vector<int> &brows, const vector<double> &bvals, vector<ll> &vl) {
    Mod &m = mods[mi]; const vector<int> &w = m.W[wi]; ll st_ = m.Wstep[wi], c0 = m.Wc0[wi]; ll A, B;
    if (RT2_MI == mi && RT2_WI == wi && L.k == (int)brows.size() + 1) { A = RT2_A; B = RT2_B; }
    else {
        rt2_drop(brows, bvals); double x0 = 0; { static vector<double> xp; lp_point(xp); for (int r = 0; r < m.M; r++) if (w[r]) for (int p : m.members[r]) x0 += w[r] * xp[p]; }
        double pos0 = (x0 - c0) / st_; A = (ll)floor(pos0 + 1e-7); B = A + 1; rt2_setup(mi, w, st_, c0, brows, bvals);
        int rb = rt2_q(B); if (rb == 2) return false;
        if (rb == 1) B = A;
        else { }
        int ra = rt2_q(A); if (ra == 2) return false;
        if (ra == 1) { if (B == A) { vl.clear(); ll v0 = R2.lo + (((c0 - R2.lo) % st_) + st_) % st_; for (ll t = v0; t <= R2.hi; t += st_) vl.push_back(t); return true; } A = B; }
    }
    RT2 &R = R2;
    for (ll i = B + 1; ; i++) { int q = rt2_q(i); if (q == 2) return false; if (q == 1) break; }
    for (ll i = A - 1; ; i--) { int q = rt2_q(i); if (q == 2) return false; if (q == 1) break; }
    vl.clear(); ll v0 = R.lo + (((c0 - R.lo) % st_) + st_) % st_; for (ll t = v0; t <= R.hi; t += st_) vl.push_back(t);
    return true;
}
static int range_test(int mi, int wi, const vector<int> &brows, const vector<double> &bvals, ll &val, double &width) {
    // Two grid values inside means no claim is made, so the LPs may stop as soon as two are reached: nothing rests on that.  Fewer than two needs the exact bounds.
    Mod &m = mods[mi]; const vector<int> &w = m.W[wi]; ll st_ = m.Wstep[wi], c0 = m.Wc0[wi]; CUP.mi = CDN.mi = -2;
    double x0 = 0; { static vector<double> xp; lp_point(xp); for (int r = 0; r < m.M; r++) if (w[r]) for (int p : m.members[r]) x0 += w[r] * xp[p]; }
    double pos0 = (x0 - c0) / st_; ll A = (ll)floor(pos0 + 1e-7), B = A + 1;
    ll hi = 0; for (int r = 0; r < m.M; r++) hi += llabs((ll)w[r]) * m.sz[r]; ll lo = -hi, b; scan_tests++; width = 0;
    const double eps = 1e-7 * st_; double v;
    auto set_up = [&]() { cc.assign(N_, 0.0); for (int r = 0; r < m.M; r++) if (w[r]) for (int p : m.members[r]) cc[p] = w[r]; };
    auto set_dn = [&]() { for (int j = 0; j < N_; j++) cc[j] = -cc[j]; };
    auto bkey = [&](int d) { return ((unsigned long long)(mi + 1) << 40) | ((unsigned long long)wi << 16) | ((unsigned long long)(d + 1) << 12) | (unsigned long long)brows.size(); };
    RTS_MI = -1; if (RTNEAR) lps_save(RS0);
    ll i0_ = L.iters; double t0_ = now(); set_up(); if (RTUB) { LP_G0 = (double)c0; LP_GST = (double)st_; } LP_STOP = (double)(c0 + B * st_) - eps; BKEY = bkey(1); int rc = lp_maximize_core(&v, 20000); LP_STOP = 1e300; LP_GST = 0; { int ph_ = lp_stopped ? 1 : 2; PHI[ph_] += L.iters - i0_; PHN[ph_]++; PHT[ph_] += now() - t0_; } if (rc != 0) return 2;
    bool hiknown = false;
    if (!lp_stopped) { if (!exact_bound_form(mi, w, 1, L.act, bvals, b)) return 2; hi = min(hi, b); hiknown = true; }
    if (!hiknown) {
        // B is inside.  Is A?
        if (RTNEAR) { lps_save(RSU); lps_load(RS0); }
        i0_ = L.iters; t0_ = now(); set_dn(); if (RTUB) { LP_G0 = -(double)c0; LP_GST = (double)st_; } LP_STOP = -(double)(c0 + A * st_) - eps; BKEY = bkey(-1); rc = lp_maximize_core(&v, 20000); LP_STOP = 1e300; LP_GST = 0; { int ph_ = lp_stopped ? 3 : 4; PHI[ph_] += L.iters - i0_; PHN[ph_]++; PHT[ph_] += now() - t0_; } if (rc != 0) return 2;
        if (lp_stopped) { if (RTNEAR) { lps_save(RSD); RTS_MI = mi; RTS_WI = wi; RTS_K = L.k; } return 2; }
        if (!exact_bound_form(mi, w, -1, L.act, bvals, b)) return 2; lo = max(lo, -b);
        // Only B and above: is B + 1 inside?
        if (RTNEAR) lps_load(RSU);
        i0_ = L.iters; t0_ = now(); set_dn(); if (RTUB) { LP_G0 = (double)c0; LP_GST = (double)st_; } LP_STOP = (double)(c0 + (B + 1) * st_) - eps; BKEY = bkey(1); rc = lp_maximize_core(&v, 20000); LP_STOP = 1e300; LP_GST = 0; { int ph_ = 5; PHI[ph_] += L.iters - i0_; PHN[ph_]++; PHT[ph_] += now() - t0_; } if (rc != 0) return 2;
        if (lp_stopped) return 2;
        if (!exact_bound_form(mi, w, 1, L.act, bvals, b)) return 2; hi = min(hi, b);
    } else {
        // The top is A at most.  Is A - 1 inside?
        if (RTNEAR) lps_load(RS0);
        i0_ = L.iters; t0_ = now(); set_dn(); if (RTUB) { LP_G0 = -(double)c0; LP_GST = (double)st_; } LP_STOP = -(double)(c0 + (A - 1) * st_) - eps; BKEY = bkey(-1); rc = lp_maximize_core(&v, 20000); LP_STOP = 1e300; LP_GST = 0; { int ph_ = 5; PHI[ph_] += L.iters - i0_; PHN[ph_]++; PHT[ph_] += now() - t0_; } if (rc != 0) return 2;
        if (lp_stopped) return 2;
        if (!exact_bound_form(mi, w, -1, L.act, bvals, b)) return 2; lo = max(lo, -b);
    }
    ll v0 = lo + (((c0 - lo) % st_) + st_) % st_; int cnt = 0; ll last = 0; for (ll t = v0; t <= hi; t += st_) { cnt++; last = t; if (cnt > 2) break; }
    if (cnt == 1) val = last;
    RTO[min(cnt, 2)]++; return min(cnt, 2);
}
static int scan5(Node &nd, Split &sp, int maxq, int limitk) {
    static vector<int> brows; static vector<double> bvals; int tests = 0;
    while (true) {
        int st = feasible_base(nd);
        if (st == 1) return 0;
        if (st == 2) { openwhy = 1; return 4; }
        base_rows(nd, brows, bvals, -1);
        rank_forms(nd, brows);
        if (FR.empty()) return 3;
        double lim = SCANTAU / RHO; sort(FR.begin(), FR.end(), [](const FormRank &a, const FormRank &b) { return a.sigma > b.sigma; });
        bool fixed = false; double rs = 0; int rn = 0;
        for (size_t i = 0; i < FR.size() && tests < maxq; i++) {
            if (FR[i].sigma > lim) continue;
            int mi = FR[i].mi, wi = FR[i].wi; Mod &m = mods[mi]; ll val = 0; double width = 0; tests++;
            int c = range_test(mi, wi, brows, bvals, val, width);
            if (width > 0 && FR[i].sigma > 1e-3 && c < 2) { rs += width / FR[i].sigma; rn++; RHO = 0.9 * RHO + 0.1 * (width / FR[i].sigma); lim = SCANTAU / RHO; }
            if (c == 0) { exact_ok++; ST.direct_closed++; scan_close++; return 0; }
            if (c == 1) { const vector<int> &w = m.W[wi]; auto fr = form_row(mi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, w}; nd.fixed.push_back({fr.first, (double)val / fr.second}); ST.direct_fixed++; scan_fix++; fixed = true; break; }
            scan_many++;
        }
        if (fixed) continue;
        return 1;
    }
}

static double hist_t[24], hist_f[24]; static inline int hbin(double sg) { int b = (int)(sg * 20); return b > 23 ? 23 : b; }
static map<pair<int,int>, double> failed_at;
static int scan6(Node &nd, Split &sp, int maxfail, int limitk) {
    static vector<int> brows; static vector<double> bvals; int fails = 0; failed_at.clear();
    while (true) {
        int st = feasible_base(nd);
        if (st == 1) return 0;
        if (st == 2) { openwhy = 1; return 4; }
        base_rows(nd, brows, bvals, -1);
        rank_forms(nd, brows);
        if (FR.empty()) return 3;
        sort(FR.begin(), FR.end(), [](const FormRank &a, const FormRank &b) { return a.sigma < b.sigma; });
        bool fixed = false;
        for (size_t i = 0; i < FR.size() && fails < maxfail; i++) {
            if (FR[i].sigma > SCANTAU) break;
            int mi = FR[i].mi, wi = FR[i].wi; Mod &m = mods[mi];
            auto fk = make_pair(mi, wi); auto fit = failed_at.find(fk); if (fit != failed_at.end() && FR[i].sigma > 0.9 * fit->second) continue;
            ll val = 0; double width = 0;
            int c = range_test(mi, wi, brows, bvals, val, width);
            hist_t[hbin(FR[i].sigma)]++; if (c < 2) hist_f[hbin(FR[i].sigma)]++;
            if (c == 0) { exact_ok++; ST.direct_closed++; scan_close++; return 0; }
            if (c == 1) { const vector<int> &w = m.W[wi]; auto fr = form_row(mi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, w}; nd.fixed.push_back({fr.first, (double)val / fr.second}); ST.direct_fixed++; scan_fix++; fixed = true; fails = 0; break; }
            scan_many++; fails++; failed_at[fk] = FR[i].sigma;
        }
        if (fixed) continue;
        return 1;
    }
}

// Signs that the LP decides: if no point of the polytope reaches a_p = -s then a_p = s.  Cheap sampling first: a vertex with a_p at a bound shows that that sign cannot be excluded.
static int PROBE = 0, PROBE_MAXP = 400, PROBE_ROUNDS = 8; static ll probe_calls = 0, probe_fix = 0, probe_close = 0, probe_lps = 0, probe_fail = 0, probe_pass_nofix = 0; static double tProbe = 0;
static mt19937_64 PR_rng(777);
static bool exact_bound_pos(int p, int s_, const vector<int> &rows, const vector<double> &vals, ll &bound) {
    static vector<double> y; y.resize(rows.size()); for (int q = 0; q < (int)rows.size(); q++) y[q] = L.y[q];
    static vector<ll> ints; if (!build_w(rows, y.data(), 1.0L, DD0, SS0, ints)) return false;
    LL T = DD0 * (LL)SS0; LL K = 0; for (int q = 0; q < (int)rows.size(); q++) if (ints[q]) K += DD0 * ints[q] * raw_of(rows[q], vals[q]);
    LL tot = 0; for (int j = 0; j < N_; j++) { LL e_ = (j == p ? T * s_ : (LL)0) - Wx[j]; tot += FZ[j] ? e_ * FZ[j] : labs128(e_); }
    LL b = tot + K; LL f = b >= 0 ? b / T : -((-b + T - 1) / T); bound = (ll)f; return true;
}
// a proved upper bound on the sum over G of d[p] a_p, using the multipliers of the LP just solved
static bool exact_bound_group(const vector<int> &G, const vector<signed char> &dirs, const vector<int> &rows, const vector<double> &vals, ll &bound) {
    static vector<double> y; y.resize(rows.size()); for (int q = 0; q < (int)rows.size(); q++) y[q] = L.y[q];
    static vector<ll> ints; if (!build_w(rows, y.data(), 1.0L, DD0, SS0, ints)) return false;
    LL T = DD0 * (LL)SS0; LL K = 0; for (int q = 0; q < (int)rows.size(); q++) if (ints[q]) K += DD0 * ints[q] * raw_of(rows[q], vals[q]);
    static vector<signed char> on; on.assign(N_, 0); for (size_t i = 0; i < G.size(); i++) on[G[i]] = dirs[i];
    LL tot = 0; for (int j = 0; j < N_; j++) { LL e_ = (LL)on[j] * T - Wx[j]; tot += FZ[j] ? e_ * FZ[j] : labs128(e_); }
    LL b = tot + K; LL f = b >= 0 ? b / T : -((-b + T - 1) / T); bound = (ll)f; return true;
}
// 0 closed, 1 new signs in nd.sgn, 2 nothing new
static int probe_signs(Node &nd) {
    double t0 = now(); probe_calls++;
    static vector<int> rows; static vector<double> vals; base_rows(nd, rows, vals, -1);
    int n = N_; const double eps = 1e-7; static vector<char> sp, sm; static vector<double> x; sp.assign(n, 0); sm.assign(n, 0); uniform_real_distribution<double> U(0.5, 1.5);
    auto see = [&]() { lp_point(x); for (int j = 0; j < n; j++) if (!FZ[j]) { if (x[j] >= 1 - eps) sp[j] = 1; if (x[j] <= -1 + eps) sm[j] = 1; } };
    see();
    auto count = [&]() { int c = 0; for (int j = 0; j < n; j++) if (!FZ[j] && !(sp[j] && sm[j])) c++; return c; };
    int und = count(), lps = 0;
    for (int rnd = 0; rnd < PROBE_ROUNDS && und > 0; rnd++) {
        cc.assign(n, 0.0);
        for (int j = 0; j < n; j++) if (!FZ[j] && !(sp[j] && sm[j])) { double w = U(PR_rng); double dir = sp[j] ? -1.0 : (sm[j] ? 1.0 : (x[j] > 0 ? -1.0 : 1.0)); cc[j] = dir * w; }
        double v; probe_lps++; lps++; if (lp_maximize_core(&v, 20000) != 0) { tProbe += now() - t0; return 2; }
        see(); int und2 = count(); bool stuck = und2 == und; und = und2; if (stuck) break;
    }
    // groups: if the whole group cannot lose even one of its signs, one LP proves them all
    vector<int> newsgn; bool closed = false;
    static vector<char> isfixed; isfixed.assign(n, 0);
    vector<vector<int>> stack; { vector<int> g; for (int j = 0; j < n; j++) if (!FZ[j] && !(sp[j] && sm[j]) && (sp[j] || sm[j])) g.push_back(j); if (!g.empty()) stack.push_back(g); }
    static vector<signed char> dirs;
    while (!stack.empty() && lps < PROBE_MAXP) {
        vector<int> g0 = std::move(stack.back()); stack.pop_back();
        vector<int> g; for (int j : g0) if (!(sp[j] && sm[j]) && !isfixed[j]) g.push_back(j);
        if (g.empty()) continue;
        cc.assign(n, 0.0); dirs.resize(g.size()); for (size_t i = 0; i < g.size(); i++) { int j = g[i]; signed char d = sp[j] ? -1 : 1; dirs[i] = d; cc[j] = d; }
        double v; probe_lps++; lps++; if (lp_maximize_core(&v, 20000) != 0) break;
        double c = (v + (double)g.size()) / 2;
        if (c < 1 - 1e-7) {
            ll b; bool ok = exact_bound_group(g, dirs, rows, vals, b);
            if (ok && b < -(ll)g.size() + 2) { for (size_t i = 0; i < g.size(); i++) { int j = g[i]; isfixed[j] = 1; newsgn.push_back(sp[j] ? j + 1 : -(j + 1)); } see(); continue; }
            probe_fail++;
            if (g.size() == 1) continue;
        }
        lp_point(x); vector<int> moved, still;
        for (size_t i = 0; i < g.size(); i++) { int j = g[i]; if (x[j] * (-dirs[i]) < 1 - eps) moved.push_back(j); else still.push_back(j); }
        see();
        if (still.empty() || moved.empty()) { vector<int> a_(g.begin(), g.begin() + g.size() / 2), b_(g.begin() + g.size() / 2, g.end()); if (!b_.empty()) stack.push_back(b_); if (!a_.empty()) stack.push_back(a_); continue; }
        stack.push_back(moved); stack.push_back(still);
    }
    // positions never at a bound: both sides, one by one
    for (int j = 0; j < n && lps < PROBE_MAXP && !closed; j++) {
        if (FZ[j] || isfixed[j] || sp[j] || sm[j]) continue;
        int found = 0;
        for (int d = 1; d >= -1; d -= 2) {
            if (d > 0 ? sp[j] : sm[j]) continue;
            cc.assign(n, 0.0); cc[j] = d; double v; lps++; probe_lps++;
            LP_STOP = 1 - 1e-6; int rc = lp_maximize_core(&v, 20000); LP_STOP = 1e300;
            if (rc != 0) break;
            if (lp_stopped || v >= 1 - 1e-6) { see(); if (d > 0) sp[j] = 1; else sm[j] = 1; continue; }
            ll b; if (!exact_bound_pos(j, d, rows, vals, b)) { probe_fail++; continue; }
            if (b >= 1) { probe_fail++; continue; }
            see();
            if (found) { closed = true; break; }
            found = -d;
        }
        if (found && !closed) newsgn.push_back(found > 0 ? j + 1 : -(j + 1));
    }
    tProbe += now() - t0;
    if (closed) { probe_close++; exact_ok++; return 0; }
    if (newsgn.empty()) { probe_pass_nofix++; return 2; }
    probe_fix += newsgn.size(); for (int v : newsgn) nd.sgn.push_back(v);
    return 1;
}

// Scan with memory: a form found to have two or more values need not be tested again in the subtree until its width has dropped, and the width is predicted by the norm of the form off the active rows.
static double SIGMAX = 0.55, MEMOF = 0.9; static ll s7_tests = 0, s7_skip = 0, s7_wide = 0, s7_fix = 0, s7_close = 0, s7_split = 0, s7_fallback = 0;
static vector<int> LISTSET, LISTAFTER; static ll list_tries = 0, list_ok = 0, list_cap = 0; static double list_sum = 0;
static double S7SPLITMAX = 1.0; static int S7NOPP = 0; static int S7ALT = 0, S7ALTB = 0;
static int SAMPLES = 0; static ll smp_skips = 0;
static int KILLK = 0; static vector<pair<int, int>> KILL; static ll kill_tests = 0, kill_hits = 0;
static int RTOP = 0, PQTOP = 4;
static int S7PICK = 0;
static int S7BATCH = 1, S7TIE = 0, LISTL = 0, SYMFORM = 0, S7EARLY = 0, S7FIRST = 0; static ll sym_halved = 0, sym_splits = 0;

// Max-entropy tilt of a node: t_p = tanh(field_p), field in the span of the active rows, class sums of t = the row values.  Used only to choose among forms: nothing rests on it.
static double SALPHA = 0.18; static int SELQ = 0; static ll tilt_calls = 0, tilt_iters = 0, sel_closed = 0, sel_fixed = 0, sel_split = 0; static double tTilt = 0, last_S = 0;
static vector<double> T_t, T_w, T_L;   // tilt, 1 - t^2, Cholesky factor of Q W Q'
static bool node_tilt(Node &nd) {
    double t0_ = now(); tilt_calls++;
    int n = N_, K = Qk; static vector<double> bq, lam, g, d, x, wf, wn, H; lp_point(x);
    bq.assign(K, 0.0); for (int q = 0; q < K; q++) { const double *qa = &Qcache[(size_t)q * n]; double s_ = 0; for (int j = 0; j < n; j++) s_ += qa[j] * x[j]; bq[q] = s_; }
    lam.assign(K, 0.0); if ((int)nd.field.size() == n) { for (int q = 0; q < K; q++) { const double *qa = &Qcache[(size_t)q * n]; double s_ = 0; for (int j = 0; j < n; j++) s_ += qa[j] * nd.field[j]; lam[q] = s_; } }
    wf.assign(n, 0.0); auto field_of = [&](const vector<double> &l, vector<double> &out) { out.assign(n, 0.0); for (int q = 0; q < K; q++) { double lq = l[q]; if (lq == 0.0) continue; const double *qa = &Qcache[(size_t)q * n]; for (int j = 0; j < n; j++) out[j] += lq * qa[j]; } };
    auto objective = [&](const vector<double> &l, const vector<double> &fld) { double f = 0; for (int j = 0; j < n; j++) { double a = fabs(fld[j]); f += a + log1p(exp(-2 * a)); } for (int q = 0; q < K; q++) f -= l[q] * bq[q]; return f; };
    field_of(lam, wf); double f0 = objective(lam, wf);
    T_t.resize(n); T_w.resize(n); H.resize((size_t)K * K); T_L.resize((size_t)K * K); g.resize(K); d.resize(K); static vector<double> lam2, wf2, Qw;
    for (int it = 0; it < 12; it++) {
        tilt_iters++;
        for (int j = 0; j < n; j++) { double t = tanh(wf[j]); T_t[j] = t; T_w[j] = max(1 - t * t, 1e-12); }
        double gn = 0; for (int q = 0; q < K; q++) { const double *qa = &Qcache[(size_t)q * n]; double s_ = 0; for (int j = 0; j < n; j++) s_ += qa[j] * T_t[j]; g[q] = s_ - bq[q]; gn += g[q] * g[q]; }
        // H = Q W Q'
        Qw.resize((size_t)K * n); for (int q = 0; q < K; q++) { const double *qa = &Qcache[(size_t)q * n]; double *qw = &Qw[(size_t)q * n]; for (int j = 0; j < n; j++) qw[j] = qa[j] * T_w[j]; }
        for (int a = 0; a < K; a++) { const double *qa = &Qw[(size_t)a * n]; for (int b = 0; b <= a; b++) { const double *qb = &Qcache[(size_t)b * n]; double s_ = 0; for (int j = 0; j < n; j++) s_ += qa[j] * qb[j]; H[(size_t)a * K + b] = s_; } H[(size_t)a * K + a] += 1e-10; }
        // Cholesky into T_L (lower)
        for (int a = 0; a < K; a++) { for (int b = 0; b <= a; b++) { double s_ = H[(size_t)a * K + b]; for (int e = 0; e < b; e++) s_ -= T_L[(size_t)a * K + e] * T_L[(size_t)b * K + e]; if (a == b) { if (s_ <= 0) { tTilt += now() - t0_; return false; } T_L[(size_t)a * K + a] = sqrt(s_); } else T_L[(size_t)a * K + b] = s_ / T_L[(size_t)b * K + b]; } }
        if (gn < 1e-6) break;
        // Newton step
        for (int a = 0; a < K; a++) { double s_ = -g[a]; for (int e = 0; e < a; e++) s_ -= T_L[(size_t)a * K + e] * d[e]; d[a] = s_ / T_L[(size_t)a * K + a]; }
        for (int a = K - 1; a >= 0; a--) { double s_ = d[a]; for (int e = a + 1; e < K; e++) s_ -= T_L[(size_t)e * K + a] * d[e]; d[a] = s_ / T_L[(size_t)a * K + a]; }
        double gd = 0; for (int q = 0; q < K; q++) gd += g[q] * d[q]; double step = 1.0; lam2.resize(K); bool moved = false;
        while (step > 1e-4) { for (int q = 0; q < K; q++) lam2[q] = lam[q] + step * d[q]; field_of(lam2, wf2); double f1 = objective(lam2, wf2); if (f1 <= f0 + 1e-4 * step * gd) { lam = lam2; wf = wf2; f0 = f1; moved = true; break; } step *= 0.5; }
        if (!moved) break;
    }
    last_S = f0 / log(2.0);
    nd.field.resize(n); for (int j = 0; j < n; j++) nd.field[j] = (float)wf[j];
    tTilt += now() - t0_; return true;
}
struct ScoreF { double score; int mi, wi; };
static vector<ScoreF> SF;
// every form of every free modulus: the predicted sum over its values of 2^(alpha (S_child - S)), by a quadratic model of the entropy
static void score_forms(const Node &nd) {
    double t0_ = now(); SF.clear(); int n = N_, K = Qk; static vector<double> X, C, mu, Y;
    for (int M : want) {
        int mi = modidx[M]; if (nd.full >> mi & 1) continue; Mod &m = mods[mi]; if (m.W.empty()) continue;
        bool listed = false; for (auto &D : nd.dom) if (D.mi == mi) listed = true; if (listed) continue;
        // Q W Z, K x M, then the forward solve
        X.assign((size_t)M * K, 0.0); mu.assign(M, 0.0); static vector<double> dg; dg.assign(M, 0.0);
        for (int r = 0; r < M; r++) { double a = 0, b = 0; for (int p : m.members[r]) { a += T_t[p]; b += T_w[p]; } mu[r] = a; dg[r] = b; }
        for (int q = 0; q < K; q++) { const double *qa = &Qcache[(size_t)q * n]; double *xq = &X[(size_t)q * M]; for (int r = 0; r < M; r++) { double s_ = 0; for (int p : m.members[r]) s_ += qa[p] * T_w[p]; xq[r] = s_; } }
        for (int q = 0; q < K; q++) { double *xq = &X[(size_t)q * M]; for (int e = 0; e < q; e++) { double f = T_L[(size_t)q * K + e]; if (f == 0.0) continue; const double *xe = &X[(size_t)e * M]; for (int r = 0; r < M; r++) xq[r] -= f * xe[r]; } double iv = 1 / T_L[(size_t)q * K + q]; for (int r = 0; r < M; r++) xq[r] *= iv; }
        C.assign((size_t)M * M, 0.0);
        for (int q = 0; q < K; q++) { const double *xq = &X[(size_t)q * M]; for (int a = 0; a < M; a++) { double f = xq[a]; if (f == 0.0) continue; double *ca = &C[(size_t)a * M]; for (int b = 0; b < M; b++) ca[b] -= f * xq[b]; } }
        for (int r = 0; r < M; r++) C[(size_t)r * M + r] += dg[r];
        make_c(mi);   // the plain metric, to tell the forms the rows already imply
        for (size_t wi = 0; wi < m.W.size(); wi++) {
            const vector<int> &w = m.W[wi]; ll st_ = m.Wstep[wi]; if (st_ <= 0) continue;
            if (form_var(mi, w) < 1e-9 * st_ * st_) continue;
            double var = 0, f = 0; for (int a = 0; a < M; a++) { int wa = w[a]; if (!wa) continue; f += wa * mu[a]; const double *ca = &C[(size_t)a * M]; double s_ = 0; for (int b = 0; b < M; b++) s_ += ca[b] * w[b]; var += wa * s_; }
            double sg2 = var / ((double)st_ * st_); double pos = (f - m.Wc0[wi]) / st_; double fr = pos - floor(pos);
            if (sg2 < 1e-8) { if (min(fr, 1 - fr) < 1e-3) continue; sg2 = 1e-8; }   // implied: nothing to learn, unless it is off the grid
            double sc = 0, c_ = SALPHA / (2 * sg2); for (int j = -3; j <= 4; j++) { double dx = j - fr; sc += exp(-c_ * dx * dx); }
            SF.push_back({sc, mi, (int)wi});
        }
    }
    tRank += now() - t0_;
}
// the choice of the split: forms in order of predicted score, the first few checked by LP
static int SELFIRST = 0;
static int select_split(Node &nd, Split &sp, const vector<double> &bvals, int limitk, int only_mi) {
    if (!node_tilt(nd)) return 3;
    score_forms(nd); if (SELFIRST && only_mi >= 0) { size_t w_ = 0; for (auto &f : SF) if (f.mi == only_mi) SF[w_++] = f; SF.resize(w_); }
    if (SF.empty()) return 3;
    int q = min<int>(SELQ, SF.size()); partial_sort(SF.begin(), SF.begin() + q, SF.end(), [](const ScoreF &a, const ScoreF &b) { return a.score < b.score; });
    double bs = 1e300; int bmi = -1; vector<int> bc; vector<ll> bvl;
    static vector<double> mu2;
    for (int i = 0; i < q; i++) {
        int mi = SF[i].mi, wi = SF[i].wi; Mod &m = mods[mi]; const vector<int> &w = m.W[wi]; ll st_ = m.Wstep[wi];
        cc.assign(N_, 0.0); for (int r = 0; r < m.M; r++) if (w[r]) for (int p : m.members[r]) cc[p] = w[r];
        double v; ll hi = 0, lo = 0; for (int r = 0; r < m.M; r++) hi += llabs((ll)w[r]) * m.sz[r]; lo = -hi; ll b;
        if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(mi, w, 1, L.act, bvals, b)) hi = min(hi, b);
        for (int j = 0; j < N_; j++) cc[j] = -cc[j];
        if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(mi, w, -1, L.act, bvals, b)) lo = max(lo, -b);
        ll c0 = m.Wc0[wi]; ll v0 = lo + (((c0 - lo) % st_) + st_) % st_; vector<ll> vl; for (ll t = v0; t <= hi; t += st_) vl.push_back(t);
        if (vl.empty()) { exact_ok++; ST.direct_closed++; sel_closed++; return 0; }
        if (vl.size() == 1) { auto fr = form_row(mi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, w}; nd.fixed.push_back({fr.first, (double)vl[0] / fr.second}); ST.direct_fixed++; sel_fixed++; return 1; }
        if (SF[i].score < bs) { bs = SF[i].score; bmi = mi; bc = w; bvl = vl; }
    }
    if (bmi < 0 || (int)bvl.size() >= limitk) return 3;
    auto fr = form_row(bmi, bc); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {bmi, bc};
    sp = Split(); sp.k = bvl.size(); sp.direct_mi = bmi; sp.c = bc; sp.vals = bvl; ST.direct_split++; sel_split++; return 2;
}

static double IMPORT = 0;
static bool tilt_form(Node &nd, int mi, const vector<int> &w, double &mu_, double &var_) {
    if (feasible_base(nd) != 0) return false;
    static vector<int> brows; static vector<double> bvals; base_rows(nd, brows, bvals, -1); make_q(brows);
    if (!node_tilt(nd)) return false;
    int n = N_, K = Qk; Mod &m = mods[mi]; int M = m.M; static vector<double> f, x, y; f.assign(n, 0.0); for (int r = 0; r < M; r++) if (w[r]) for (int p : m.members[r]) f[p] = w[r];
    mu_ = 0; double v0 = 0; for (int j = 0; j < n; j++) { mu_ += f[j] * T_t[j]; v0 += f[j] * f[j] * T_w[j]; }
    y.assign(K, 0.0); for (int q = 0; q < K; q++) { const double *qa = &Qcache[(size_t)q * n]; double s_ = 0; for (int j = 0; j < n; j++) s_ += qa[j] * T_w[j] * f[j]; y[q] = s_; }
    for (int q = 0; q < K; q++) { double s_ = y[q]; for (int e = 0; e < q; e++) s_ -= T_L[(size_t)q * K + e] * y[e]; y[q] = s_ / T_L[(size_t)q * K + q]; }
    double c = 0; for (int q = 0; q < K; q++) c += y[q] * y[q]; var_ = v0 - c; return true;
}

// Forms on positions, c(p) not periodic.  Their grid is worked out in each node from the rows it has, 2-adically: rows may be divided by 2 when all their entries are even (a rational combination of rows is as good as any), so that the grid can be far coarser than for the moments alone.
static int PM = -1, RAMPK = 0; static ll ramp_calls = 0, ramp_close = 0, ramp_fix = 0, ramp_split = 0, ramp_incons = 0; static double tRamp = 0, ramp_stsum = 0;
typedef unsigned __int128 U128;
static inline int v2u(U128 x) { if (!x) return 128; uint64_t lo = (uint64_t)x; if (lo) return __builtin_ctzll(lo); return 64 + __builtin_ctzll((uint64_t)(x >> 64)); }
static inline U128 inv_odd(U128 a) { U128 x = a; for (int i = 0; i < 7; i++) x *= (U128)2 - a * x; return x; }
// returns 0: no integer sequence can satisfy the rows (closed), 1: grid found; the form's value is congruent to c0 mod st
static int ramp_grid(const Node &nd, const vector<int> &w, const vector<int> &rows, const vector<double> &vals, ll &st, ll &c0) {
    int n = N_, prec = 128; static vector<vector<U128>> E; static vector<U128> Ev; static vector<int> Ep; int ne = 0;
    if ((int)E.size() < (int)rows.size() + M_ + 2) { E.resize(rows.size() + M_ + 2); Ev.resize(rows.size() + M_ + 2); Ep.resize(rows.size() + M_ + 2); }
    static vector<U128> r; r.resize(n);
    auto add_row = [&](U128 v) -> int {
        for (int e = 0; e < ne; e++) { U128 f = r[Ep[e]]; if (f == 0) continue; const U128 *er = E[e].data(); for (int p = 0; p < n; p++) r[p] -= f * er[p]; v -= f * Ev[e]; }
        int g = 128, pv = -1; for (int p = 0; p < n; p++) { int t = v2u(r[p]); if (t < g) { g = t; pv = p; } }
        if (g >= prec) return 1;   // nothing left of this row, as far as the bits go
        if (g > 0) { U128 mask = g >= 128 ? ~(U128)0 : (((U128)1 << g) - 1); if (v & mask) { return 0; } for (int p = 0; p < n; p++) r[p] >>= g; v >>= g; prec -= g; }
        U128 iv = inv_odd(r[pv]); for (int p = 0; p < n; p++) r[p] *= iv; v *= iv;
        E[ne].assign(r.begin(), r.end()); Ev[ne] = v; Ep[ne] = pv; ne++; return 1;
    };
    for (int t = 0; t < M_; t++) { for (int p = 0; p < n; p++) r[p] = (U128)BINOM[p][t]; if (!add_row(0)) return 0; }
    for (size_t q = 0; q < rows.size(); q++) {
        int row = rows[q]; if (row < M_) continue;
        int mi = rowform[row].first; Mod &m = mods[mi]; for (int p = 0; p < n; p++) r[p] = 0;
        if (row >= m.pos && row < m.pos + m.M) { for (int p : m.members[row - m.pos]) r[p] = 1; }
        else { const vector<int> &cf = rowform[row].second; for (int c_ = 0; c_ < m.M; c_++) if (cf[c_]) for (int p : m.members[c_]) r[p] = (U128)(__int128)cf[c_]; }
        U128 v = (U128)(__int128)raw_of(row, vals[q]);
        if (!add_row(v)) return 0;
    }
    static vector<U128> t_; t_.resize(n); for (int p = 0; p < n; p++) t_[p] = (U128)(__int128)w[p];
    U128 off = 0; for (int e = 0; e < ne; e++) { U128 f = t_[Ep[e]]; if (f == 0) continue; const U128 *er = E[e].data(); for (int p = 0; p < n; p++) t_[p] -= f * er[p]; off += f * Ev[e]; }
    int g = 128; for (int p = 0; p < n; p++) g = min(g, v2u(t_[p]));
    if (g > 40) g = 40; if (g + 1 >= prec) g = prec - 2;
    U128 sum = off; for (int p = 0; p < n; p++) sum += t_[p];
    ll step = 1LL << (g + 1); U128 mask = ((U128)1 << (g + 1)) - 1; c0 = (ll)(sum & mask); st = step; return 1;
}
static int ramp_scan(Node &nd, Split &sp, const vector<int> &brows, const vector<double> &bvals) {
    if (PM < 0 || RAMPK <= 0) return 3;
    double t0_ = now(); Mod &m = mods[PM];
    for (size_t wi = 0; wi < 1; wi++) {
        const vector<int> &w = m.W[wi]; auto it = forms.find(FormKey{PM, w});
        if (it != forms.end()) { bool have = false; for (int r_ : brows) if (r_ == it->second.first) { have = true; break; } if (have) continue; }
        ll st_, c0; ramp_calls++;
        if (!ramp_grid(nd, w, brows, bvals, st_, c0)) { ramp_incons++; exact_ok++; tRamp += now() - t0_; return 0; }
        ramp_stsum += log2((double)st_);
        cc.assign(N_, 0.0); for (int p = 0; p < N_; p++) cc[p] = w[p];
        double v; ll hi = 0, lo = 0; for (int p = 0; p < N_; p++) hi += llabs((ll)w[p]); lo = -hi; ll b;
        if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(PM, w, 1, L.act, bvals, b)) hi = min(hi, b);
        for (int j = 0; j < N_; j++) cc[j] = -cc[j];
        if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(PM, w, -1, L.act, bvals, b)) lo = max(lo, -b);
        ll v0 = lo + (((c0 - lo) % st_) + st_) % st_; vector<ll> vl; for (ll t = v0; t <= hi; t += st_) { vl.push_back(t); if ((int)vl.size() > RAMPK) break; }
        if (vl.empty()) { exact_ok++; ramp_close++; ST.direct_closed++; tRamp += now() - t0_; return 0; }
        if (!wit.empty()) { ll sv = 0; for (int p = 0; p < N_; p++) sv += (ll)w[p] * wit[p]; if (((sv - c0) % st_ + st_) % st_ != 0) { wit_err++; fprintf(stderr, "WITNESS OFF THE GRID OF A POSITION FORM: value %lld grid %lld mod %lld\\n", sv, c0, st_); } }
        if (vl.size() == 1) { auto fr = form_row(PM, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {PM, w}; nd.fixed.push_back({fr.first, (double)vl[0] / fr.second}); ramp_fix++; ST.direct_fixed++; tRamp += now() - t0_; return 1; }
        if ((int)vl.size() <= RAMPK) { auto fr = form_row(PM, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {PM, w}; sp = Split(); sp.k = vl.size(); sp.direct_mi = PM; sp.c = w; sp.vals = vl; ramp_split++; ST.direct_split++; tRamp += now() - t0_; return 2; }
    }
    tRamp += now() - t0_; return 3;
}

static int CLOSEQ = 0; static double CLOSETAU = 1.0; static ll cf_tests = 0, cf_close = 0, cf_fix = 0, cf_calls = 0;
static int close_first(Node &nd, const vector<int> &brows, const vector<double> &bvals) {
    if (!node_tilt(nd)) return 3;
    cf_calls++;
    double t0_ = now(); static vector<ScoreF> CF; CF.clear(); int n = N_, K = Qk; static vector<double> X, C, mu; static vector<double> dg;
    for (int M : want) {
        int mi = modidx[M]; if (nd.full >> mi & 1) continue; Mod &m = mods[mi]; if (m.W.empty()) continue;
        bool listed = false; for (auto &D : nd.dom) if (D.mi == mi) listed = true; if (listed) continue;
        X.assign((size_t)M * K, 0.0); mu.assign(M, 0.0); dg.assign(M, 0.0);
        for (int r = 0; r < M; r++) { double a = 0, b = 0; for (int p : m.members[r]) { a += T_t[p]; b += T_w[p]; } mu[r] = a; dg[r] = b; }
        for (int q = 0; q < K; q++) { const double *qa = &Qcache[(size_t)q * n]; double *xq = &X[(size_t)q * M]; for (int r = 0; r < M; r++) { double s_ = 0; for (int p : m.members[r]) s_ += qa[p] * T_w[p]; xq[r] = s_; } }
        for (int q = 0; q < K; q++) { double *xq = &X[(size_t)q * M]; for (int e = 0; e < q; e++) { double f = T_L[(size_t)q * K + e]; if (f == 0.0) continue; const double *xe = &X[(size_t)e * M]; for (int r = 0; r < M; r++) xq[r] -= f * xe[r]; } double iv = 1 / T_L[(size_t)q * K + q]; for (int r = 0; r < M; r++) xq[r] *= iv; }
        C.assign((size_t)M * M, 0.0);
        for (int q = 0; q < K; q++) { const double *xq = &X[(size_t)q * M]; for (int a = 0; a < M; a++) { double f = xq[a]; if (f == 0.0) continue; double *ca = &C[(size_t)a * M]; for (int b = 0; b < M; b++) ca[b] -= f * xq[b]; } }
        for (int r = 0; r < M; r++) C[(size_t)r * M + r] += dg[r];
        make_c(mi);
        for (size_t wi = 0; wi < m.W.size(); wi++) {
            const vector<int> &w = m.W[wi]; ll st_ = m.Wstep[wi]; if (st_ <= 0) continue;
            if (form_var(mi, w) < 1e-9 * st_ * st_) continue;
            double var = 0, f = 0; for (int a = 0; a < M; a++) { int wa = w[a]; if (!wa) continue; f += wa * mu[a]; const double *ca = &C[(size_t)a * M]; double s_ = 0; for (int b = 0; b < M; b++) s_ += ca[b] * w[b]; var += wa * s_; }
            double sg = sqrt(max(var, 1e-12)) / st_; double pos = (f - m.Wc0[wi]) / st_; double fr = pos - floor(pos); double dist = min(fr, 1 - fr);
            double sc = dist / sg; if (sc >= CLOSETAU) CF.push_back({-sc, mi, (int)wi});
        }
    }
    tRank += now() - t0_;
    if (CF.empty()) return 3;
    int q = min<int>(CLOSEQ, CF.size()); partial_sort(CF.begin(), CF.begin() + q, CF.end(), [](const ScoreF &a, const ScoreF &b) { return a.score < b.score; });
    for (int i = 0; i < q; i++) {
        int mi = CF[i].mi, wi = CF[i].wi; ll val = 0; double width = 0; cf_tests++;
        int c_ = range_test(mi, wi, brows, bvals, val, width);
        if (c_ == 0) { exact_ok++; ST.direct_closed++; cf_close++; return 0; }
        if (c_ == 1) { Mod &m = mods[mi]; const vector<int> &w = m.W[wi]; auto fr = form_row(mi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, w}; nd.fixed.push_back({fr.first, (double)val / fr.second}); ST.direct_fixed++; cf_fix++; return 1; }
    }
    return 3;
}
static int SYMLATE = 0; static double SYMSIG = 1.0;
static int sym_block(Node &nd, Split &sp, const vector<double> &bvals) { PT pt_(3); SPLIT_SAVED = false;
        // The solutions of this node map to solutions under reversal.  A form with f(reversed a) = -f(a) has its values in pairs +v, -v, and only v >= 0 need be looked at.
        int stests = 0, sbk = 1 << 30, smi = -1, swi = -1; vector<ll> svl;
        for (int M : want) {
            int mi = modidx[M]; if (nd.full >> mi & 1) continue; Mod &m = mods[mi]; if (m.antiW.empty()) continue;
            bool listed = false; for (auto &D : nd.dom) if (D.mi == mi) listed = true; if (listed) continue;
            make_c(mi);
            for (int wi : m.antiW) {
                if (stests >= SYMFORM) break;
                const vector<int> &w = m.W[wi]; ll st_ = m.Wstep[wi];
                double vr = form_var(mi, w); if (vr < 1e-9 * st_ * st_) continue;
                if (sqrt(vr) / st_ > SYMSIG) continue;
                stests++; s7_tests++; CUP.mi = CDN.mi = -2;
                cc.assign(N_, 0.0); for (int r = 0; r < m.M; r++) if (w[r]) for (int p : m.members[r]) cc[p] = w[r];
                double v; ll hi = 0, lo = 0; for (int r = 0; r < m.M; r++) hi += llabs((ll)w[r]) * m.sz[r]; lo = -hi; ll b;
                if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(mi, w, 1, L.act, bvals, b)) hi = min(hi, b);
                for (int j = 0; j < N_; j++) cc[j] = -cc[j];
                if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(mi, w, -1, L.act, bvals, b)) lo = max(lo, -b);
                ll c0 = m.Wc0[wi]; ll v0 = lo + (((c0 - lo) % st_) + st_) % st_; vector<ll> vl; for (ll t = v0; t <= hi; t += st_) vl.push_back(t);
                if (vl.empty()) { if (CERTF) cert_bounds(mi, w, 1, 0, CUP, CDN); exact_ok++; ST.direct_closed++; s7_close++; return 0; }
                vector<ll> vp; for (ll t : vl) if (t >= 0) vp.push_back(t);
                if (vp.empty()) { if (CERTF) cert_bounds(mi, w, 1, 0, CUP, CDN); exact_ok++; ST.direct_closed++; s7_close++; return 0; }   // the mirror of what is left lies outside the proved range: nothing here
                if (vp.size() == 1) {
                    if (CERTF) { cert_bounds(mi, w, 1, 1, CUP, CDN); SPLIT_SAVED = false; }
                    ll val = vp[0]; auto fr = form_row(mi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, w};
                    if (!wit.empty()) { vector<ll> ws(m.M, 0); for (int p = 0; p < N_; p++) ws[p % m.M] += wit[p]; ll sv = 0; for (int r = 0; r < m.M; r++) sv += w[r] * ws[r]; if (sv < 0) reverse(wit.begin(), wit.end()); }
                    nd.fixed.push_back({fr.first, (double)val / fr.second}); ST.direct_fixed++; s7_fix++; sym_halved++; if (val != 0) nd.G &= ~2u; return 1;
                }
                if ((int)vp.size() < sbk) { sbk = vp.size(); smi = mi; swi = wi; svl = vp; if (CERTF) { SAVEUP = CUP; SAVEDN = CDN; SPLIT_SAVED = true; } }
            }
            if (stests >= SYMFORM) break;
        }
        if (smi >= 0) {
            Mod &m = mods[smi]; const vector<int> &w = m.W[swi]; auto fr = form_row(smi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {smi, w};
            sp = Split(); sp.k = sbk; sp.direct_mi = smi; sp.c = w; sp.vals = svl; sp.sym = true; ST.direct_split++; s7_split++; sym_splits++; return 2;
        }
        return 3;
    }
static int SKIPDONE = 0; static vector<int> SPLITW;
static int scan7(Node &nd, Split &sp, int maxq, int limitk) { PT pt_(4);
    static vector<int> brows; static vector<double> bvals; int nfix = 0;
restart:
    RTS_MI = -1;   // the ends saved by a test belong to this pass only
    int st0 = feasible_base(nd); if (st0 == 1) return 0; if (st0 == 2) { openwhy = 1; return 4; }
    base_rows(nd, brows, bvals, -1);
    { int rr = ramp_scan(nd, sp, brows, bvals); if (rr == 0) return 0; if (rr == 1) { nfix++; goto restart; } if (rr == 2) return 2; if (RAMPK > 0) { int st1_ = feasible_base(nd); if (st1_ == 1) return 0; if (st1_ == 2) { openwhy = 1; return 4; } } }
    { double t0_ = now(); make_q(brows); tImplied += now() - t0_; }
    if (nd.memo.size() != mods.size()) nd.memo.resize(mods.size());
    if (KILLK > 0) {
        for (size_t ki = 0; ki < KILL.size() && (int)ki < KILLK; ki++) {
            int mi = KILL[ki].first, wi = KILL[ki].second; if (nd.full >> mi & 1) continue; Mod &m = mods[mi]; const vector<int> &w = m.W[wi]; ll st_ = m.Wstep[wi];
            { bool listed = false; for (auto &D : nd.dom) if (D.mi == mi) listed = true; if (listed) continue; }
            make_c(mi); double vr = form_var(mi, w); if (vr < 1e-9 * st_ * st_) continue; double sg = sqrt(vr) / st_; if (sg > SIGMAX) continue;
            if (nd.memo[mi].size() != m.W.size()) nd.memo[mi].assign(m.W.size(), 0.f);
            if (nd.memo[mi][wi] > 0 && sg > MEMOF * nd.memo[mi][wi]) continue;
            ll val = 0; double width = 0; kill_tests++; int c_ = range_test(mi, wi, brows, bvals, val, width);
            if (c_ == 0) { kill_hits++; exact_ok++; ST.direct_closed++; s7_close++; if (ki > 0) { auto t_ = KILL[ki]; KILL.erase(KILL.begin() + ki); KILL.insert(KILL.begin(), t_); } return 0; }
            if (c_ == 1) { auto fr = form_row(mi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, w}; nd.fixed.push_back({fr.first, (double)val / fr.second}); ST.direct_fixed++; s7_fix++; nfix++; goto restart; }
            nd.memo[mi][wi] = (float)sg;
        }
    }
    if (CLOSEQ > 0) { int rc_ = close_first(nd, brows, bvals); if (rc_ == 0) return 0; if (rc_ == 1) { nfix++; goto restart; } }
    if (SYMFORM && !SYMLATE && (nd.G & 2)) {
        int rs = sym_block(nd, sp, bvals);
        if (rs == 0) return 0;
        if (rs == 1) { nfix++; goto restart; }
        if (rs == 2) return 2;
    }
    int tests = 0, bk = 1 << 30, bmi = -1; vector<int> bc; vector<ll> bvalsf; double bsg = 0;
    static vector<vector<double>> smp; static vector<double> x_tmp; static int smp_next; smp.clear(); smp_next = 0; if (SAMPLES > 0) { lp_point(x_tmp); smp.push_back(x_tmp); }
    double wsig = 1e300; int wmi = -1, wwi = -1; double esg = 1e300; int emi = -1, ewi = -1;
    for (int M : want) {
        int mi = modidx[M]; if (nd.full >> mi & 1) continue; if (SKIPDONE && (nd.impl >> mi & 1)) continue; Mod &m = mods[mi]; if (m.W.empty()) continue;
        bool listed = false; for (auto &D : nd.dom) if (D.mi == mi) listed = true; if (listed) continue;
        { double t0_ = now(); make_c(mi); tImplied += now() - t0_; }
        bool anyfree_ = false; bool walked_ = true;
        auto &mem = nd.memo[mi]; if (mem.size() != m.W.size()) mem.assign(m.W.size(), 0.f);
        static vector<int> ordw; ordw.resize(m.W.size()); for (size_t i_ = 0; i_ < m.W.size(); i_++) ordw[i_] = i_;
        if (S7PICK) {
            // forms whose value at the point in hand lies far from the grid, for their width, come first
            static vector<double> xq_, mu_, key_; lp_point(xq_); mu_.assign(m.M, 0.0); for (int r = 0; r < m.M; r++) { double s_ = 0; for (int p : m.members[r]) s_ += xq_[p]; mu_[r] = s_; }
            key_.assign(m.W.size(), 0.0);
            for (size_t i_ = 0; i_ < m.W.size(); i_++) { ll st_ = m.Wstep[i_]; if (st_ <= 0) continue; const vector<int> &w = m.W[i_]; double vr = form_var(mi, w); if (vr < 1e-9 * st_ * st_) continue; if (S7PICK == 2) { key_[i_] = vr / ((double)st_ * st_); continue; } double f_ = 0; for (int r = 0; r < m.M; r++) f_ += w[r] * mu_[r]; double pos = (f_ - m.Wc0[i_]) / st_; double fr_ = pos - floor(pos); double d_ = min(fr_, 1 - fr_); double sg_ = sqrt(vr) / st_; key_[i_] = S7PICK == 1 ? -d_ / sg_ : sg_; }
            sort(ordw.begin(), ordw.end(), [&](int a, int b) { return key_[a] < key_[b]; });
        }
        for (size_t oi_ = 0; oi_ < m.W.size(); oi_++) {
            if (tests >= maxq) { walked_ = false; break; }
            size_t wi = ordw[oi_];
            const vector<int> &w = m.W[wi]; ll st_ = m.Wstep[wi]; if (st_ <= 0) continue;
            double vr = form_var(mi, w); if (vr < 1e-9 * st_ * st_) { skip_implied++; continue; }
            anyfree_ = true;
            double sg = sqrt(vr) / st_;
            if (sg < wsig) { wsig = sg; wmi = mi; wwi = wi; }
            if (sg > SIGMAX) { s7_wide++; continue; }
            if (mem[wi] > 0 && sg > MEMOF * mem[wi]) { s7_skip++; continue; }
            if (SAMPLES > 0 && !smp.empty()) {
                double mn = 1e300, mx = -1e300; for (auto &x_ : smp) { double f_ = 0; for (int r = 0; r < m.M; r++) if (w[r]) { double s_ = 0; for (int p : m.members[r]) s_ += x_[p]; f_ += w[r] * s_; } mn = min(mn, f_); mx = max(mx, f_); }
                double a_ = (mn - m.Wc0[wi]) / st_, b_ = (mx - m.Wc0[wi]) / st_; if (floor(b_ + 1e-7) - ceil(a_ - 1e-7) + 1 >= 2) { smp_skips++; mem[wi] = (float)sg; if (sg < esg) { esg = sg; emi = mi; ewi = wi; } continue; }
            }
            tests++; s7_tests++;
            if (S7EARLY) {
                ll val = 0; double width = 0; int c_ = RTDUAL ? range_test2(mi, wi, brows, bvals, val, width) : range_test(mi, wi, brows, bvals, val, width);
                if (SAMPLES > 0 && c_ == 2) { lp_point(x_tmp); if ((int)smp.size() < SAMPLES) smp.push_back(x_tmp); else { smp[smp_next] = x_tmp; smp_next = (smp_next + 1) % SAMPLES; } }
                if (c_ == 0) { if (CERTF) cert_bounds(mi, w, 0, 0, CUP, CDN); if (KILLK > 0) { pair<int, int> t_(mi, (int)wi); auto it_ = find(KILL.begin(), KILL.end(), t_); if (it_ != KILL.end()) KILL.erase(it_); KILL.insert(KILL.begin(), t_); if ((int)KILL.size() > KILLK) KILL.pop_back(); } exact_ok++; ST.direct_closed++; s7_close++; return 0; }
                if (c_ == 1) { if (CERTF) cert_bounds(mi, w, 0, 1, CUP, CDN); auto fr = form_row(mi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, w}; nd.fixed.push_back({fr.first, (double)val / fr.second}); ST.direct_fixed++; s7_fix++; nfix++; if (S7BATCH) goto restart; return 1; }
                mem[wi] = (float)sg;
                if (S7FIRST == 0 && !SELFIRST) { if (sg < esg) { esg = sg; emi = mi; ewi = wi; } }
                else if (S7FIRST == 0) { if (emi < 0) { esg = sg; emi = mi; ewi = wi; } }
                else if (emi < 0 || mi == emi) {
                    bool take = emi < 0;
                    if (!take) { if (S7FIRST == 1) take = sg < esg; else if (S7FIRST == 2) take = sg > esg; /* 3: the first in the list */ }
                    if (take) { esg = sg; emi = mi; ewi = wi; }
                }
                continue;
            }
            tests++; s7_tests++;
            cc.assign(N_, 0.0); for (int r = 0; r < m.M; r++) if (w[r]) for (int p : m.members[r]) cc[p] = w[r];
            double v; ll hi = 0, lo = 0; for (int r = 0; r < m.M; r++) hi += llabs((ll)w[r]) * m.sz[r]; lo = -hi; ll b;
            static FormCert hc_; bool gh = false, gl = false;
            if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(mi, w, 1, L.act, bvals, b)) { hi = min(hi, b); if (CERTPOOL) { hc_ = LASTCERT; gh = true; } }
            for (int j = 0; j < N_; j++) cc[j] = -cc[j];
            if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(mi, w, -1, L.act, bvals, b)) { lo = max(lo, -b); gl = true; }
            ll c0 = m.Wc0[wi]; ll v0 = lo + (((c0 - lo) % st_) + st_) % st_; vector<ll> vl; for (ll t = v0; t <= hi; t += st_) vl.push_back(t);
            if (vl.empty()) { if (gh && gl) cpool_add(hc_, LASTCERT, st_, c0); exact_ok++; ST.direct_closed++; s7_close++; return 0; }
            if (vl.size() == 1) { auto fr = form_row(mi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, w}; nd.fixed.push_back({fr.first, (double)vl[0] / fr.second}); ST.direct_fixed++; s7_fix++; nfix++; if (S7BATCH) goto restart; return 1; }
            mem[wi] = (float)sg;
            { bool better = (int)vl.size() < bk; if (!better && (int)vl.size() == bk && S7TIE) { better = S7TIE == 1 ? sg > bsg : sg < bsg; } if (better) { bk = vl.size(); bmi = mi; bc = w; bvalsf = vl; bsg = sg; } }
        }
        if (SKIPDONE && walked_ && !anyfree_) nd.impl |= 1u << mi;   // every form of this modulus lies in the rows; rows only grow below here
        if (tests >= maxq) break;
    }
    if (nfix) return 1;
    if (S7EARLY && emi >= 0 && SELQ == 0 && !(SYMFORM && SYMLATE && (nd.G & 2))) { wmi = emi; wwi = ewi; wsig = esg; }
    if (S7FIRST == 4 || S7FIRST == 5) {
        // the split follows the order of the moduli strictly: the flattest form of the first modulus that still has one in reach
        wmi = -1; wsig = 1e300;
        for (int M : (SPLITW.empty() ? want : SPLITW)) {
            if (S7NOPP && (M == 4 || M == 8 || M == 9 || M == 16 || M == 25 || M == 27)) continue;
            int mi = modidx[M]; if (nd.full >> mi & 1) continue; if (SKIPDONE && (nd.impl >> mi & 1)) continue; Mod &m = mods[mi]; if (m.W.empty()) continue;
            bool listed = false; for (auto &D : nd.dom) if (D.mi == mi) listed = true; if (listed) continue;
            make_c(mi); double bs_ = 1e300; int bw_ = -1;
            for (size_t wi = 0; wi < m.W.size(); wi++) { ll st_ = m.Wstep[wi]; if (st_ <= 0) continue; double vr = form_var(mi, m.W[wi]); if (vr < 1e-9 * st_ * st_) continue; double sg = sqrt(vr) / st_; if (sg < bs_) { bs_ = sg; bw_ = wi; } }
            if (bw_ >= 0 && bs_ <= S7SPLITMAX) { wmi = mi; wwi = bw_; wsig = bs_; if (S7FIRST == 5 && RTS_MI == mi && RTS_WI >= 0 && RTS_K == L.k) { wwi = RTS_WI; } break; }
        }
        if (S7ALT && wmi >= 0 && mods[wmi].M == S7ALT) {
            // interleave: the other modulus when it has had fewer forms pinned
            int other = modidx[S7ALTB]; int ca = 0, cb = 0; for (auto &f : nd.fixed) { if (f.first < M_) continue; int fm_ = rowform[f.first].first; if (fm_ == wmi) ca++; else if (fm_ == other) cb++; }
            if (cb < ca) { Mod &m = mods[other]; make_c(other); double bs_ = 1e300; int bw_ = -1; for (size_t wi = 0; wi < m.W.size(); wi++) { ll st_ = m.Wstep[wi]; if (st_ <= 0) continue; double vr = form_var(other, m.W[wi]); if (vr < 1e-9 * st_ * st_) continue; double sg = sqrt(vr) / st_; if (sg < bs_) { bs_ = sg; bw_ = wi; } } if (bw_ >= 0) { wmi = other; wwi = bw_; wsig = bs_; } }
        }
        if (wmi < 0) { wmi = emi; wwi = ewi; wsig = esg; }
    }
    if (SYMFORM && SYMLATE && (nd.G & 2)) {
        int rs = sym_block(nd, sp, bvals);
        if (rs == 0) return 0;
        if (rs == 1) { nfix++; goto restart; }
        if (rs == 2) return 2;
    }
    if (SELQ > 0) {
        int rs = select_split(nd, sp, bvals, limitk, emi);
        if (rs == 0) return 0;
        if (rs == 1) { nfix++; goto restart; }
        if (rs == 2) return 2;
    }
    if (bmi < 0) {
        // nothing tested here: the flattest form known, whatever its width
        if (wmi < 0) return 3;
        ll i0sp_ = L.iters; double t0sp_ = now();
        s7_fallback++; CUP.mi = CDN.mi = -2;
        int mi = wmi; Mod &m = mods[mi]; const vector<int> &w = m.W[wwi]; ll st_ = m.Wstep[wwi];
        if (RTDUAL) {
            vector<ll> vl2;
            if (range_split2(mi, wwi, brows, bvals, vl2)) {
                PHI[6] += L.iters - i0sp_; PHN[6]++; PHT[6] += now() - t0sp_;
                if (vl2.empty()) { exact_ok++; ST.direct_closed++; s7_close++; return 0; }
                if (vl2.size() == 1) { auto fr = form_row(mi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, w}; nd.fixed.push_back({fr.first, (double)vl2[0] / fr.second}); ST.direct_fixed++; s7_fix++; return 1; }
                bk = vl2.size(); bmi = mi; bc = w; bvalsf = vl2;
                if (bk >= limitk) return 3;
                auto fr = form_row(bmi, bc); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {bmi, bc};
                sp = Split(); sp.k = bk; sp.direct_mi = bmi; sp.c = bc; sp.vals = bvalsf; ST.direct_split++; s7_split++; return 2;
            }
            rt2_fix_fail(brows, bvals);
        }
        bool near_ = RTNEAR && RTS_MI == mi && RTS_WI == wwi && RTS_K == L.k; if (near_) rts_hit++; else rts_miss++;
        bool from0_ = false;
        if (near_) lps_load(RSU);
        else if (RTNEAR) { from0_ = true; if (tests > 0 && (int)RS0.basis.size() == L.k) lps_load(RS0); else lps_save(RS0); }
        cc.assign(N_, 0.0); for (int r = 0; r < m.M; r++) if (w[r]) for (int p : m.members[r]) cc[p] = w[r];
        double v; ll hi = 0, lo = 0; for (int r = 0; r < m.M; r++) hi += llabs((ll)w[r]) * m.sz[r]; lo = -hi; ll b;
        BKEY = ((unsigned long long)(mi + 1) << 40) | ((unsigned long long)wwi << 16) | (2ULL << 12) | (unsigned long long)brows.size(); if (RTUB) { LP_G0 = (double)m.Wc0[wwi]; LP_GST = (double)st_; } { int rc_ = lp_maximize_core(&v, 20000); LP_GST = 0; if (rc_ == 0 && exact_bound_form(mi, w, 1, L.act, bvals, b)) hi = min(hi, b); if (SIBREST == 2 && rc_ == 0) { lpf_save(SPLIT_U); SPLIT_U_ok = true; } }
        for (int j = 0; j < N_; j++) cc[j] = -cc[j];
        if (near_) lps_load(RSD); else if (from0_) lps_load(RS0);
        BKEY = ((unsigned long long)(mi + 1) << 40) | ((unsigned long long)wwi << 16) | (0ULL << 12) | (unsigned long long)brows.size(); if (RTUB) { LP_G0 = -(double)m.Wc0[wwi]; LP_GST = (double)st_; } { int rc_ = lp_maximize_core(&v, 20000); LP_GST = 0; if (rc_ == 0 && exact_bound_form(mi, w, -1, L.act, bvals, b)) lo = max(lo, -b); }
        PHI[6] += L.iters - i0sp_; PHN[6]++; PHT[6] += now() - t0sp_;
        ll c0 = m.Wc0[wwi]; ll v0 = lo + (((c0 - lo) % st_) + st_) % st_; vector<ll> vl; for (ll t = v0; t <= hi; t += st_) vl.push_back(t);
        if (CERTF) { cert_bounds(mi, w, 0, (long)vl.size(), CUP, CDN); SPLIT_SAVED = false; }
        if (vl.empty()) { exact_ok++; ST.direct_closed++; s7_close++; return 0; }
        if (vl.size() == 1) { auto fr = form_row(mi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, w}; nd.fixed.push_back({fr.first, (double)vl[0] / fr.second}); ST.direct_fixed++; s7_fix++; return 1; }
        bk = vl.size(); bmi = mi; bc = w; bvalsf = vl;
    }
    if (bk >= limitk) return 3;
    auto fr = form_row(bmi, bc); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {bmi, bc};
    sp = Split(); sp.k = bk; sp.direct_mi = bmi; sp.c = bc; sp.vals = bvalsf; ST.direct_split++; s7_split++; return 2;
}
static string dump_prefix; static int dump_every = 0; static long dump_seen = 0; static int dump_written = 0;
static void dump_node(const Node &nd, int depth) {
    if (dump_prefix.empty() || dump_every <= 0) return;
    if (++dump_seen % dump_every) return;
    static vector<int> rows; static vector<double> vals; base_rows(nd, rows, vals, -1);
    char name[512]; snprintf(name, sizeof name, "%s_%d.txt", dump_prefix.c_str(), dump_written++);
    FILE *f = fopen(name, "w"); if (!f) return;
    fprintf(f, "%d %d %d\n", N_, (int)rows.size(), depth);
    for (size_t q = 0; q < rows.size(); q++) { const double *Ai = &L.A[(size_t)rows[q] * N_]; fprintf(f, "%.17g", vals[q]); for (int j = 0; j < N_; j++) fprintf(f, " %.17g", Ai[j]); fprintf(f, "\n"); }
    int cnt = 0; for (int M : want) { int mi = modidx[M]; if (nd.full >> mi & 1) continue; bool listed = false; for (auto &D : nd.dom) if (D.mi == mi) listed = true; if (!listed) cnt++; }
    fprintf(f, "%d\n", cnt);
    for (int M : want) { int mi = modidx[M]; if (nd.full >> mi & 1) continue; bool listed = false; for (auto &D : nd.dom) if (D.mi == mi) listed = true; if (listed) continue;
        Mod &m = mods[mi]; fprintf(f, "%d %d\n", M, (int)m.W.size());
        for (size_t wi = 0; wi < m.W.size(); wi++) { fprintf(f, "%lld %lld", (long long)m.Wstep[wi], (long long)m.Wc0[wi]); for (int r = 0; r < M; r++) fprintf(f, " %d", m.W[wi][r]); fprintf(f, "\n"); }
    }
    fclose(f);
}
static bool escalated = false;
typedef int (*sdp_cb_t)(int n, int k, const double *A, const double *b, int depth);
static sdp_cb_t SDPCB = nullptr; static ll sdp_calls = 0, sdp_closed = 0; static int SDPMAXD = 100000;
static int expand_(Node &nd, int depth, Split &sp);
static int expand(Node &nd, int depth, Split &sp) {
    int st = expand_(nd, depth, sp);
    if (st == 1 && SDPCB && depth <= SDPMAXD) {
        static vector<int> rows; static vector<double> vals; static vector<double> AA; base_rows(nd, rows, vals, -1); AA.resize(rows.size() * N_);
        for (size_t q = 0; q < rows.size(); q++) memcpy(&AA[q * N_], &L.A[(size_t)rows[q] * N_], N_ * sizeof(double));
        sdp_calls++; if (SDPCB(N_, (int)rows.size(), AA.data(), vals.data(), depth)) { sdp_closed++; return 0; }
    }
    return st;
}
static int expand_(Node &nd, int depth, Split &sp) { PT pt_(5);
    if (cpool_close(nd)) return 0;
    while (true) {
        int st = feasible_base(nd);
        if (st == 1) return 0;
        if (st == 2) { openwhy = 1; return 2; }
        bool changed = false; Split best; cands.clear();
        vector<int> order; for (int i = 0; i < (int)nd.dom.size(); i++) if (nd.dom[i].mi >= 0 && !(nd.full >> nd.dom[i].mi & 1)) order.push_back(i);
        sort(order.begin(), order.end(), [&](int a, int b) { return nd.dom[a].N < nd.dom[b].N; });
        for (int i : order) {
            Dom &D = nd.dom[i]; filter_domain(nd, D, TESTS, FEAS);
            if (D.N == 0) return 0;
            feasible_base(nd);
            if (D.N == 1) { pin_all(nd, D); changed = true; continue; }
            if (hull_rows(nd, D)) changed = true;
            if (!changed) best_split(D, i, best);
        }
        if (changed) continue;
        dump_node(nd, depth);
        if (PROBE) { int rc = probe_signs(nd); if (rc == 0) return 0; if (rc == 1) continue; feasible_base(nd); }
        bool needlist = false;
        if (!LISTSET.empty() && (best.di < 0 || best.k > WIDE)) for (int M : LISTSET) {
            if (needlist) break;
            int mi = modidx[M]; if (nd.full >> mi & 1) continue;
            bool inlist = false; for (auto &D : nd.dom) if (D.mi == mi) inlist = true; if (inlist) continue;
            if (nd.tried[mi] > depth - RETRY) continue;
            // all the moduli before it in the order have no free form left: it is the current one
            bool cur = true; { static vector<int> brq; static vector<double> bvq; base_rows(nd, brq, bvq, -1); make_q(brq); for (int M2 : LISTAFTER) { int m2 = modidx[M2]; if (nd.full >> m2 & 1) continue; Mod &mm = mods[m2]; make_c(m2); for (size_t wi = 0; wi < mm.W.size() && cur; wi++) { ll st_ = mm.Wstep[wi]; if (st_ <= 0) continue; double vr = form_var(m2, mm.W[wi]); if (vr > 1e-9 * st_ * st_) cur = false; } if (!cur) break; } }
            if (!cur) continue;
            needlist = true; list_tries++;
        }
        if (LISTL > 0 && (best.di < 0 || best.k > WIDE)) for (int i_ = 0; i_ < (int)want.size() && i_ < LISTL && !needlist; i_++) {
            int M = want[i_]; int mi = modidx[M]; if (nd.full >> mi & 1) continue;
            bool inlist = false; for (auto &D : nd.dom) if (D.mi == mi) inlist = true; if (inlist) continue;
            if (nd.tried[mi] > depth - RETRY) continue;
            int par = -1; for (int a = 0; a < (int)mods.size(); a++) if (a != mi && (nd.full >> a & 1) && M % mods[a].M == 0 && (par < 0 || mods[a].M > mods[par].M)) par = a;
            int p = 2; while (M % p) p++;
            if (M != p && M != 4 && par < 0) continue;
            needlist = true;
        }
        if (needlist) {
            // lists first at these moduli: on to the enumeration below
        } else if (SCANMODE == 7) {
            Split sd; int rc = scan7(nd, sd, ((int)nd.fixed.size() < RTOP ? PQTOP : PROPQ), best.di >= 0 ? best.k : (1 << 30));
            if (rc == 0) return 0;
            if (rc == 1) continue;
            if (rc == 4) return 2;
            if (rc == 2) { sp = sd; return 1; }
            feasible_base(nd);
        } else if (SCANMODE == 5 || SCANMODE == 6) {
            Split sd; int rc = SCANMODE == 6 ? scan6(nd, sd, PROPQ, 1 << 30) : scan5(nd, sd, PROPQ, 1 << 30);
            if (rc == 0) return 0;
            if (rc == 4) return 2;
            size_t nf0 = nd.fixed.size(); (void)nf0;
            feasible_base(nd);
        } else if (PROPM > 0) {
            Split sd; int rc = SCANMODE ? scan_forms(nd, sd, PROPQ, best.di >= 0 ? best.k : (1 << 30)) : direct_scan(nd, sd, PROPM, PROPQ, best.di >= 0 ? best.k : (1 << 30));
            if (rc == 0) return 0;
            if (rc == 1) continue;
            if (rc == 2 && (best.di < 0 || sd.k < best.k)) { sp = sd; return 1; }
            feasible_base(nd);
        }
        if (best.di >= 0 && best.k > WIDE && DEEP > 0) {
            Dom &D = nd.dom[best.di]; int n0 = D.N; filter_domain(nd, D, DEEP, DEEP);
            if (D.N == 0) return 0;
            feasible_base(nd);
            if (D.N < n0) {
                if (D.N == 1) { pin_all(nd, D); continue; }
                if (hull_rows(nd, D)) continue;
                int di = best.di; best = Split(); best_split(D, di, best);
            }
        }
        if (best.di < 0 || best.k > WIDE) {
            bool got = false;
            if (CERTF) {
                int rc = scan_forms(nd, sp, DIRECTQ, 1 << 30);
                if (rc == 0) return 0;
                if (rc == 1) continue;
                if (rc == 2) return 1;
                openwhy = 2; return 2;
            }
            for (int M : want) {
                int mi = modidx[M]; if (nd.full >> mi & 1) continue;
                if (!LISTSET.empty() && find(LISTSET.begin(), LISTSET.end(), M) == LISTSET.end()) continue;
                bool inlist = false; for (auto &D : nd.dom) if (D.mi == mi) inlist = true; if (inlist) continue;
                if (nd.tried[mi] > depth - RETRY) continue;
                // a parent, when a higher power
                int par = -1; for (int a = 0; a < (int)mods.size(); a++) if (a != mi && (nd.full >> a & 1) && M % mods[a].M == 0 && (par < 0 || mods[a].M > mods[par].M)) par = a;
                int p = 2; while (M % p) p++;
                if (M != p && M != 4 && par < 0) continue;
                nd.tried[mi] = depth; double t0 = now(); ST.enums++;
                feasible_base(nd);
                static vector<int> brows; static vector<double> bvals; base_rows(nd, brows, bvals, -1);
                Mod &m = mods[mi]; vector<ll> lo(m.M), hi(m.M); bool dead = false;
                for (int r = 0; r < m.M && !dead; r++) {
                    lo[r] = -m.sz[r]; hi[r] = m.sz[r]; double v; ll b;
                    if (lp_maximize(m.members[r], 1.0, &v) == 0 && exact_bound(mi, r, 1, L.act, bvals_for(brows, bvals), b)) hi[r] = min(hi[r], b);
                    if (lp_maximize(m.members[r], -1.0, &v) == 0 && exact_bound(mi, r, -1, L.act, bvals_for(brows, bvals), b)) lo[r] = max(lo[r], -b);
                    if (lo[r] > hi[r]) dead = true;
                }
                if (dead) { exact_ok++; return 0; }
                vector<int16_t> out; vector<ll> W; int P = 1; if (par >= 0) { P = mods[par].M; W = nd.fullval[par]; }
                EN_nb2 = -1;
                if (SUBLAT) { int sr = sublattice(mi, nd, EN_rep2, EN_B2, EN_piv2, EN_nb2); if (!sr) { sub_closed++; EN_nb2 = -1; ST.tEnum += now() - t0; return 0; } }
                bool ok = enumerate(mi, lo, hi, P, W, out); ST.tEnum += now() - t0; EN_nb2 = -1;
                if (!ok) { ST.capped++; list_cap++; continue; }
                list_ok++; list_sum += out.size() / m.M;
                if (out.empty()) return 0;
                for (auto &f : nd.fixed) if (f.first >= M_ && rowform[f.first].first == mi && !rowform[f.first].second.empty()) {
                    const vector<int> &cf = rowform[f.first].second; ll val = raw_of(f.first, f.second); int w_ = 0, Nn = out.size() / m.M;
                    for (int i = 0; i < Nn; i++) { const int16_t *u = &out[(size_t)i * m.M]; ll t = 0; for (int r = 0; r < m.M; r++) t += cf[r] * u[r]; if (t == val) { if (w_ != i) memmove(&out[(size_t)w_ * m.M], u, m.M * sizeof(int16_t)); w_++; } }
                    out.resize((size_t)w_ * m.M);
                }
                if (out.empty()) return 0;
                if (nd.G) { bool clean = true; for (auto &Dx : nd.dom) if (Dx.mi >= 0 && !(nd.full >> Dx.mi & 1)) clean = false; if (clean) { sym_reduce(out, m.M, nd.G); if (out.empty()) return 0; } }
                Dom D; D.mi = mi; D.N = out.size() / m.M; D.d.swap(out); nd.dom.push_back(std::move(D)); got = true; break;
            }
            if (got) continue;
            if (best.di < 0) {
                int rc = SCANMODE ? scan_forms(nd, sp, DIRECTQ, 1 << 30) : direct_scan(nd, sp, DIRECTM, DIRECTQ);
                if (rc == 0) return 0;
                if (rc == 1) continue;
                if (rc == 2) return 1;
            }
        }
        if (best.di < 0) { openwhy = 2; return 2; }
        if (STRONG > 0 && best.k > 1 && cands.size() > 1) {
            // one LP per child of each candidate: the form that leaves the fewest children alive
            static vector<int> br; static vector<double> bv; base_rows(nd, br, bv, -1);
            int bestAlive = 1 << 30; int bestK = 1 << 30; Split chosen = best;
            for (auto &cd : cands) {
                Dom &D = nd.dom[cd.di]; Mod &m = mods[D.mi]; int M = m.M;
                vector<ll> vals(D.N); for (int i = 0; i < D.N; i++) { const int16_t *u = &D.d[(size_t)i * M]; ll s_ = 0; for (int r = 0; r < M; r++) s_ += cd.c[r] * u[r]; vals[i] = s_; }
                sort(vals.begin(), vals.end()); vals.erase(unique(vals.begin(), vals.end()), vals.end());
                if ((int)vals.size() > bestAlive + 2) continue;
                int nz = 0, last = -1; for (int r = 0; r < M; r++) if (cd.c[r]) { nz++; last = r; }
                pair<int, double> fr; if (nz == 1) fr = {m.pos + last, m.norm[last] / cd.c[last]}; else { fr = form_row(D.mi, cd.c); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {D.mi, cd.c}; }
                vector<int> r2 = br; vector<double> v2 = bv; r2.push_back(fr.first); v2.push_back(0.0);
                bool dup = false; for (size_t q = 0; q + 1 < r2.size(); q++) if (r2[q] == fr.first) dup = true; if (dup) continue;
                int alive = 0;
                for (ll v : vals) { v2.back() = (double)v / fr.second; lp_rows(r2, v2); int st2 = lp_feasible(); if (st2 != 1 || !exact_close(r2, v2)) alive++; if (alive > bestAlive) break; }
                if (alive < bestAlive || (alive == bestAlive && (int)vals.size() < bestK)) { bestAlive = alive; bestK = vals.size(); chosen = cd; }
            }
            best = chosen; feasible_base(nd);
        }
        sp = best; return 1;
    }
}
static void describe_open(const Node &nd, int depth);
static ll CH_HIST[8][8]; static double OUT_N[2], OUT_IT[2], OUT_LP[2], OUT_T[2];
static double PR_N[200], PR_C[200], PR_ROWS[200], PR_SPLIT[32], PR_K[32], PR_SD[200 * 32];
static string spill_prefix; static int spilled = 0;
void write_node(const Node &nd, const char *path);
static void search(Node &nd, int depth) {
    if (!spill_prefix.empty() && depth > 0 && now() > deadline) { char name[512]; snprintf(name, sizeof name, "%s_%d", spill_prefix.c_str(), spilled++); write_node(nd, name); if (CERTF) fputs("S\n", CERTF); return; }
    if (out_of_time) return;
    ST.nodes++; if (depth > ST.maxdepth) ST.maxdepth = depth;
    if (depth > 0 && now() > deadline) { out_of_time = true; return; }   // a task always does its own start: a spill of it would prove nothing
    BK = NEXTBK; NEXTBK = 0; SPLIT_U_ok = false; CLOSE_DONE = false; SPLIT_SAVED = false; CRAY.mi = -2; Split sp; double t0 = knuth ? now() : 0; bool hw = holds_witness(nd); if (hw) wit_nodes++; ll it0_ = L.iters; ll sv0_ = L.solves; ll tt0_ = s7_tests; int st = expand(nd, depth, sp); if (knuth) kcost += kw * (now() - t0);
    { int o_ = st == 0 ? 0 : 1; OUT_N[o_]++; OUT_IT[o_] += L.iters - it0_; OUT_LP[o_] += L.solves - sv0_; OUT_T[o_] += s7_tests - tt0_; }
    if (hw) {
        if (st == 0) { wit_err++; fprintf(stderr, "WITNESS NODE CLOSED at depth %d\n", depth); }
        for (auto &D : nd.dom) if (D.mi >= 0 && !(nd.full >> D.mi & 1) && !wit_in_dom(D)) { wit_err++; fprintf(stderr, "WITNESS VECTOR LOST mod %d at depth %d\n", mods[D.mi].M, depth); }
        if (!holds_witness(nd)) { wit_err++; fprintf(stderr, "WITNESS FAILS A ROW at depth %d\n", depth); }
    }
    if (knuth && depth < 200) { PR_N[depth] += kw; PR_ROWS[depth] += kw * nd.fixed.size(); if (st == 0) PR_C[depth] += kw; if (st == 1 && sp.direct_mi >= 0) { PR_SPLIT[sp.direct_mi] += kw; PR_K[sp.direct_mi] += kw * sp.vals.size(); PR_SD[depth * 32 + sp.direct_mi] += kw; } }
    if (st == 0) { if (CERTF && !CLOSE_DONE) { if (CRAY.mi != -1) fputs("C unproved\n", CERTF); else { fputs("C ", CERTF); cert_put(CRAY); fputc('\n', CERTF); } } ST.closed++; return; }
    if (st == 2) { if (CERTF) fputs("O\n", CERTF); ST.open++; describe_open(nd, depth); return; }
    ST.splits++;
    if (sp.direct_mi >= 0) {
        auto fr = form_row(sp.direct_mi, sp.c);
        if (CERTF && !knuth) { if (SPLIT_SAVED) cert_bounds(sp.direct_mi, sp.c, sp.sym ? 1 : 0, (long)sp.vals.size(), SAVEUP, SAVEDN); else if (sp.sym) fputs("C unproved\n", CERTF); }
        if (knuth) {
            if (follow && !wit.empty()) { Mod &m = mods[sp.direct_mi]; vector<ll> w(m.M, 0); for (int p = 0; p < N_; p++) w[p % m.M] += wit[p]; ll s_ = 0; for (int r = 0; r < m.M; r++) s_ += sp.c[r] * w[r]; if (sp.sym && s_ < 0) { reverse(wit.begin(), wit.end()); s_ = -s_; } if (!binary_search(sp.vals.begin(), sp.vals.end(), s_)) { wit_err++; fprintf(stderr, "WITNESS VALUE NOT AMONG THE DIRECT CHILDREN mod %d depth %d\n", m.M, depth); return; } kw *= sp.vals.size(); kest += kw; Node ch = nd; ch.G = (sp.sym && s_ == 0) ? nd.G : 0; ch.fixed.push_back({fr.first, (double)s_ / fr.second}); search(ch, depth + 1); return; }
            {
                ll v = 0; double wgt = (double)sp.vals.size();
                if (IMPORT > 0 && sp.vals.size() > 1) {
                    static vector<double> pr; pr.resize(sp.vals.size()); double mu_ = 0, var_ = 0;
                    if (tilt_form(nd, sp.direct_mi, sp.c, mu_, var_)) {
                        double tot = 0; for (size_t i = 0; i < sp.vals.size(); i++) { double dx = sp.vals[i] - mu_; pr[i] = exp(-IMPORT * dx * dx / (2 * max(var_, 1e-9))) + 1e-3; tot += pr[i]; }
                        double u = uniform_real_distribution<double>(0, tot)(RNG); size_t pick = 0; for (; pick + 1 < sp.vals.size(); pick++) { u -= pr[pick]; if (u <= 0) break; }
                        v = sp.vals[pick]; wgt = tot / pr[pick];
                    } else v = sp.vals[RNG() % sp.vals.size()];
                } else v = sp.vals[RNG() % sp.vals.size()];
                kw *= wgt; kest += kw * sp.vals.size() / wgt; Node ch = nd; ch.G = (sp.sym && v == 0) ? nd.G : 0; ch.fixed.push_back({fr.first, (double)v / fr.second}); search(ch, depth + 1); return;
            }
        }
        // a child of a direct split is not invariant under the symmetries: the mirror of its solutions lies in a sibling or elsewhere, so nothing may be dropped on account of them below it
        int alive = 0; size_t ci_ = 0;
        static vector<LPF> DST; bool sib_ = false; if (SIBREST == 1) { if ((int)DST.size() <= depth) DST.resize(depth + 16); lpf_save(DST[depth]); sib_ = true; } else if (SIBREST == 2 && SPLIT_U_ok) { if ((int)DST.size() <= depth) DST.resize(depth + 16); std::swap(DST[depth], SPLIT_U); sib_ = true; }
        SPLIT_U_ok = false;
        for (ll v : sp.vals) { Node ch = nd; ch.G = (sp.sym && v == 0) ? nd.G : 0; ch.fixed.push_back({fr.first, (double)v / fr.second}); ll c0_ = ST.nodes; NEXTBK = ci_ ? 1 : 0; if (sib_ && ci_) lpf_load(DST[depth]); if (CERTF) { fputs("V ", CERTF); cert_num(v); fputc('\n', CERTF); } search(ch, depth + 1); ci_++; if (ST.nodes - c0_ > 1) alive++; if (out_of_time) return; }
        { int kk = min<int>(sp.vals.size(), 7); int al = min(alive, 7); CH_HIST[kk][al]++; }
        return;
    }
    Dom &D = nd.dom[sp.di]; Mod &m = mods[D.mi]; int M = m.M;
    vector<ll> sums(D.N); for (int i = 0; i < D.N; i++) { const int16_t *u = &D.d[(size_t)i * M]; ll s = 0; for (int r = 0; r < M; r++) s += sp.c[r] * u[r]; sums[i] = s; }
    vector<ll> vals = sums; sort(vals.begin(), vals.end()); vals.erase(unique(vals.begin(), vals.end()), vals.end());
    int nz = 0, last = -1; for (int r = 0; r < M; r++) if (sp.c[r]) { nz++; last = r; }
    pair<int, double> fr; if (nz == 1) fr = {m.pos + last, m.norm[last] / sp.c[last]}; else { fr = form_row(D.mi, sp.c); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {D.mi, sp.c}; }
    if (knuth) {
        if (pathlog) { int nzz = 0; for (int r = 0; r < M; r++) if (sp.c[r]) nzz++; fprintf(stderr, "%d/w%d:%d/%d[r%d] ", M, nzz, (int)vals.size(), D.N, (int)nd.fixed.size()); }
        kw *= vals.size(); kest += kw; ll v = vals[RNG() % vals.size()];
        if (follow && !wit.empty()) { vector<ll> w(M, 0); for (int p = 0; p < N_; p++) w[p % M] += wit[p]; ll s = 0; for (int r = 0; r < M; r++) s += sp.c[r] * w[r]; v = s; if (!binary_search(vals.begin(), vals.end(), v)) { wit_err++; fprintf(stderr, "WITNESS VALUE NOT AMONG THE CHILDREN mod %d depth %d\n", M, depth); return; } }
        Node ch = nd; Dom &Dc = ch.dom[sp.di]; int w = 0; for (int i = 0; i < D.N; i++) if (sums[i] == v) { memmove(&Dc.d[(size_t)w * M], &D.d[(size_t)i * M], M * sizeof(int16_t)); w++; } Dc.N = w; Dc.d.resize((size_t)w * M); Dc.rank = -1;
        ch.fixed.push_back({fr.first, (double)v / fr.second}); search(ch, depth + 1); return;
    }
    for (ll v : vals) {
        double tc = now(); Node ch = nd; Dom &Dc = ch.dom[sp.di]; int w = 0; for (int i = 0; i < D.N; i++) if (sums[i] == v) { memcpy(&Dc.d[(size_t)w * M], &D.d[(size_t)i * M], M * sizeof(int16_t)); w++; } Dc.N = w; Dc.d.resize((size_t)w * M); Dc.rank = -1; ST.tCopy += now() - tc;
        ch.fixed.push_back({fr.first, (double)v / fr.second}); search(ch, depth + 1);
        if (out_of_time) return;
    }
}
static string openprefix; static int opencount = 0;
static void describe_open(const Node &nd, int depth) { if (!openprefix.empty()) { char name[512]; snprintf(name, sizeof name, "%s_%d_%d", openprefix.c_str(), (int)getpid(), opencount++); write_node(nd, name); } if (openlog) { fprintf(openlog, "open why %d lp %d k %d lpiters %lld full %u depth %d rows %d doms", openwhy, lpwhy, L.k, L.iters, nd.full, depth, (int)nd.fixed.size()); for (auto &D : nd.dom) if (D.mi >= 0) fprintf(openlog, " %d:%d", mods[D.mi].M, D.N); for (auto &f : nd.fixed) fprintf(openlog, " %d=%.6g", f.first, f.second); fprintf(openlog, "\n"); fflush(openlog); } }

void write_node(const Node &nd, const char *path) {
    FILE *f = fopen(path, "w"); fprintf(f, "v2 %u %u\n", nd.G, nd.full);
    for (int a = 0; a < (PM >= 0 ? PM : (int)mods.size()); a++) fprintf(f, "%d ", nd.tried[a]); fprintf(f, "\n");
    for (int a = 0; a < (int)mods.size(); a++) if (nd.full >> a & 1) { fprintf(f, "%d", mods[a].M); for (ll v : nd.fullval[a]) fprintf(f, " %lld", v); fprintf(f, "\n"); }
    // the rows: by modulus and coefficients, with the value of the form (an integer)
    int cnt = 0; for (auto &fx : nd.fixed) if (fx.first >= M_) cnt++;
    fprintf(f, "%d\n", cnt);
    for (auto &fx : nd.fixed) if (fx.first >= M_) {
        int row = fx.first; int mi = rowform[row].first; Mod &m = mods[mi];
        if (row >= m.pos && row < m.pos + m.M) { int r = row - m.pos; fprintf(f, "%d C %d %.0f\n", m.M, r, fx.second * m.norm[r]); }
        else { const vector<int> &c = rowform[row].second; auto it = forms.find(FormKey{mi, c}); double nr = it->second.second; fprintf(f, "%d F %.0f", m.M, fx.second * nr); for (int v : c) fprintf(f, " %d", v); fprintf(f, "\n"); }
    }
    int dc = 0; for (auto &D : nd.dom) if (D.mi >= 0 && !(nd.full >> D.mi & 1)) dc++;
    fprintf(f, "%d\n", dc);
    for (auto &D : nd.dom) if (D.mi >= 0 && !(nd.full >> D.mi & 1)) { fprintf(f, "%d %d %d\n", mods[D.mi].M, D.N, D.rank); for (size_t i = 0; i < D.d.size(); i++) fprintf(f, "%d ", (int)D.d[i]); fprintf(f, "\n"); }
    fprintf(f, "%d\n", (int)nd.sgn.size()); for (int v : nd.sgn) fprintf(f, "%d ", v); fprintf(f, "\n");
    fclose(f);
}
static bool read_node(Node &nd, const char *path) {
    ifstream in(path); if (!in) return false; nd = Node(); nd.tried.assign(mods.size(), -99); nd.fullval.assign(mods.size(), {}); { string tok; in >> tok; if (tok == "v2") in >> nd.G >> nd.full; else nd.full = (unsigned)stoul(tok); }
    for (int a = 0; a < (PM >= 0 ? PM : (int)mods.size()); a++) in >> nd.tried[a];
    int nf = __builtin_popcount(nd.full);
    for (int b = 0; b < nf; b++) { int M; in >> M; int mi = modidx[M]; nd.fullval[mi].resize(M); for (auto &v : nd.fullval[mi]) in >> v; }
    int cnt; in >> cnt;
    for (int i = 0; i < cnt; i++) {
        int M; string t; in >> M >> t; int mi = modidx[M]; Mod &m = mods[mi];
        if (t == "C") { int r; double v; in >> r >> v; nd.fixed.push_back({m.pos + r, v / m.norm[r]}); }
        else { double v; in >> v; vector<int> c(M); for (auto &x : c) in >> x; auto fr = form_row(mi, c); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, c}; nd.fixed.push_back({fr.first, v / fr.second}); }
    }
    int dc; in >> dc;
    for (int i = 0; i < dc; i++) { int M, N, rk; in >> M >> N >> rk; Dom D; D.mi = modidx[M]; D.N = N; D.rank = rk; D.d.resize((size_t)N * M); for (auto &x : D.d) { int v; in >> v; x = (int16_t)v; } if (N <= CAP) nd.dom.push_back(std::move(D)); }
    { int sc = 0; if (in >> sc) { nd.sgn.resize(sc); for (auto &v : nd.sgn) in >> v; } }
    return true;
}
static LL rdLL(istream &in) { string s; in >> s; LL v = 0; size_t i = 0; bool neg = false; if (s[0] == '-') { neg = true; i = 1; } for (; i < s.size(); i++) v = v * 10 + (s[i] - '0'); return neg ? -v : v; }
extern "C" {
// config: text: n m nmods; then for each modulus: M nb mult; rep[order]; sizes by class; order; piv; B (M rows of nb) ; nW; W rows
int pe_init(const char *path, const double *moments) {
    ifstream in(path); int nm; in >> N_ >> M_ >> nm; lp_init(N_); mods.clear(); modidx.clear(); forms.clear(); rowform.clear();
    BINOM.assign(N_, vector<LL>(M_, 0)); for (int p = 0; p < N_; p++) { LL c = 1; for (int t = 0; t < M_; t++) { BINOM[p][t] = c; c = c * (p - t) / (t + 1); if (p - t <= 0) c = 0; } }
    for (int i = 0; i < M_; i++) { lp_add_row(moments + (size_t)i * N_); rowform.push_back({-1, {}}); }
    for (int a = 0; a < nm; a++) {
        Mod m; in >> m.M >> m.nb >> m.mult; int M = m.M; m.rep.resize(M); m.sz.resize(M); m.order.resize(M); m.piv.resize(m.nb); m.B.assign(M, vector<LL>(m.nb));
        for (auto &v : m.rep) v = rdLL(in);
        for (auto &v : m.sz) in >> v;
        for (auto &v : m.order) in >> v;
        for (auto &v : m.piv) in >> v;
        for (int r = 0; r < M; r++) for (int c = 0; c < m.nb; c++) m.B[r][c] = rdLL(in);
        int nw; in >> nw; m.W.assign(nw, vector<int>(M)); for (auto &w : m.W) for (auto &v : w) in >> v;
        m.members.assign(M, {}); for (int p = 0; p < N_; p++) m.members[p % M].push_back(p);
        m.pos = L.K; m.norm.resize(M); vector<double> row(N_);
        for (int r = 0; r < M; r++) { fill(row.begin(), row.end(), 0.0); double nr = sqrt((double)m.members[r].size()); for (int p : m.members[r]) row[p] = 1.0 / nr; m.norm[r] = nr; lp_add_row(row.data()); rowform.push_back({a, {}}); }
        modidx[M] = mods.size(); mods.push_back(m);
    }
    { UU.assign(M_, vector<long double>(M_, 0)); string tok; for (int j = 0; j < M_; j++) for (int t = 0; t < M_; t++) { in >> tok; UU[j][t] = strtold(tok.c_str(), nullptr); } }
    for (auto &m : mods) {
        m.Wstep.clear(); m.Wc0.clear();
        for (auto &w : m.W) {
            LL g = 0; for (int c = 0; c < m.nb; c++) { LL t = 0; for (int i = 0; i < m.M; i++) t += (LL)w[m.order[i]] * m.B[i][c]; if (t < 0) t = -t; while (t) { LL u = g % t; g = t; t = u; } }
            LL c0 = 0; for (int i = 0; i < m.M; i++) c0 += (LL)w[m.order[i]] * m.rep[i];
            LL step = (LL)m.mult * g; ll par = 0; for (int r = 0; r < m.M; r++) par += w[r] * m.sz[r]; par = ((par % 2) + 2) % 2;
            if (step == 0) { m.Wstep.push_back(0); m.Wc0.push_back((ll)c0); continue; }
            ll st = (ll)step; ll c = (ll)(((c0 % step) + step) % step);
            if (st % 2) { if (((c - par) % 2 + 2) % 2) c += st; st *= 2; }
            m.Wstep.push_back(st); m.Wc0.push_back(c);
        }
        m.antiW.clear();
        for (size_t wi = 0; wi < m.W.size(); wi++) { bool anti = m.Wstep[wi] > 0; for (int r = 0; r < m.M && anti; r++) if (m.W[wi][((N_ - 1 - r) % m.M + m.M) % m.M] != -m.W[wi][r]) anti = false; if (anti) m.antiW.push_back(wi); }
    }
    PM = -1;
    { bool clash = false; for (auto &m : mods) if (m.M == N_) clash = true;
      if (!clash) { Mod m; m.M = N_; m.nb = 0; m.mult = 1; m.rep.assign(N_, 0); m.sz.assign(N_, 1); m.order.resize(N_); for (int i = 0; i < N_; i++) m.order[i] = i; m.members.assign(N_, {}); for (int p = 0; p < N_; p++) m.members[p].push_back(p); m.pos = 1 << 30; m.norm.assign(N_, 1.0);
        vector<int> w(N_); for (int p = 0; p < N_; p++) w[p] = ((p & 1) ? -1 : 1) * (2 * p - (N_ - 1)); m.W.push_back(w); m.Wstep.assign(1, 0); m.Wc0.assign(1, 0);
        for (int p = 0; p < N_; p++) { vector<int> u(N_, 0); u[p] = 1; m.W.push_back(u); m.Wstep.push_back(0); m.Wc0.push_back(0); }
        PM = mods.size(); modidx[N_] = PM; mods.push_back(m); } }
    for (auto &m : mods) { m.divisors.clear(); if (&m == &mods[PM >= 0 ? PM : 0] && PM >= 0) continue; for (int b = 0; b < (int)mods.size(); b++) if (mods[b].M != m.M && m.M % mods[b].M == 0) m.divisors.push_back(b); }
    return 0;
}

// For a driver above the engine: the candidate forms at a node, the values of one of them, a child on a file.
int pe_candidates(const char *path, int perm, int *mis, int *wis, double *sigs, int maxn) {
    Node nd; if (!read_node(nd, path)) return -1;
    static vector<int> brows; static vector<double> bvals; int st = feasible_base(nd); if (st != 0) return -2;
    base_rows(nd, brows, bvals, -1); make_q(brows); int cnt = 0;
    for (int M : want) {
        int mi = modidx[M]; if (nd.full >> mi & 1) continue; Mod &m = mods[mi]; if (m.W.empty()) continue;
        make_c(mi); vector<pair<double, int>> v;
        for (size_t wi = 0; wi < m.W.size(); wi++) { ll st_ = m.Wstep[wi]; if (st_ <= 0) continue; double vr = form_var(mi, m.W[wi]); if (vr < 1e-9 * st_ * st_) continue; v.push_back({sqrt(vr) / st_, (int)wi}); }
        sort(v.begin(), v.end());
        for (int i = 0; i < perm && i < (int)v.size() && cnt < maxn; i++) { mis[cnt] = M; wis[cnt] = v[i].second; sigs[cnt] = v[i].first; cnt++; }
    }
    return cnt;
}
int pe_values(const char *path, int M, int wi, long long *vals, int maxk) {
    Node nd; if (!read_node(nd, path)) return -1;
    static vector<int> brows; static vector<double> bvals; int st0 = feasible_base(nd); if (st0 != 0) return -2;
    base_rows(nd, brows, bvals, -1); int mi = modidx[M]; Mod &m = mods[mi]; const vector<int> &w = m.W[wi]; ll st_ = m.Wstep[wi], c0 = m.Wc0[wi];
    cc.assign(N_, 0.0); for (int r = 0; r < m.M; r++) if (w[r]) for (int p : m.members[r]) cc[p] = w[r];
    double v; ll hi = 0, lo = 0; for (int r = 0; r < m.M; r++) hi += llabs((ll)w[r]) * m.sz[r]; lo = -hi; ll b;
    if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(mi, w, 1, L.act, bvals, b)) hi = min(hi, b);
    for (int j = 0; j < N_; j++) cc[j] = -cc[j];
    if (lp_maximize_core(&v, 20000) == 0 && exact_bound_form(mi, w, -1, L.act, bvals, b)) lo = max(lo, -b);
    ll v0 = lo + (((c0 - lo) % st_) + st_) % st_; int k = 0; for (ll t = v0; t <= hi; t += st_) { if (k < maxk) vals[k] = t; k++; }
    return k;
}
int pe_child(const char *path, int M, int wi, long long val, const char *out) {
    Node nd; if (!read_node(nd, path)) return -1;
    int mi = modidx[M]; Mod &m = mods[mi]; const vector<int> &w = m.W[wi]; auto fr = form_row(mi, w); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {mi, w};
    nd.G = 0; nd.fixed.push_back({fr.first, (double)val / fr.second}); write_node(nd, out); return 0;
}

static void form_step(Mod &m, const vector<int> &w, ll &stp, ll &c0p) {
    LL g = 0; for (int c = 0; c < m.nb; c++) { LL t = 0; for (int i = 0; i < m.M; i++) t += (LL)w[m.order[i]] * m.B[i][c]; if (t < 0) t = -t; while (t) { LL u = g % t; g = t; t = u; } }
    LL c0 = 0; for (int i = 0; i < m.M; i++) c0 += (LL)w[m.order[i]] * m.rep[i];
    LL step = (LL)m.mult * g; ll par = 0; for (int r = 0; r < m.M; r++) par += w[r] * m.sz[r]; par = ((par % 2) + 2) % 2;
    if (step == 0) { stp = 0; c0p = (ll)c0; return; }
    ll st = (ll)step; ll c = (ll)(((c0 % step) + step) % step);
    if (st % 2) { if (((c - par) % 2 + 2) % 2) c += st; st *= 2; }
    stp = st; c0p = c;
}
int pe_addform(int M, const int *w, int front) {
    auto it = modidx.find(M); if (it == modidx.end()) return -1; Mod &m = mods[it->second]; vector<int> v(w, w + M); ll st, c0; form_step(m, v, st, c0);
    if (front) { m.W.insert(m.W.begin(), v); m.Wstep.insert(m.Wstep.begin(), st); m.Wc0.insert(m.Wc0.begin(), c0); return 0; }
    m.W.push_back(v); m.Wstep.push_back(st); m.Wc0.push_back(c0); return (int)m.W.size() - 1;
}
// a task from a file: run its subtree.
static void cert_task_begin(const Node &nd) {
    fputs("T ", CERTF); cert_num(N_); cert_num(M_); fputs("\nG ", CERTF); cert_num((nd.G & 2) ? 1 : 0); fputc('\n', CERTF); CERT_KNOWN.assign(L.K + 64, 0);
    for (auto &f : nd.fixed) {
        int id = f.first; if (id < M_) continue; if ((int)rowform.size() <= id) { fputs("C unproved\n", CERTF); continue; } int mi = rowform[id].first; Mod &m = mods[mi]; fputs("P ", CERTF); cert_num(id); cert_num(m.M); cert_num(raw_of(id, f.second));
        if (id >= m.pos && id < m.pos + m.M) { for (int r = 0; r < m.M; r++) cert_num(r == id - m.pos ? 1 : 0); } else for (int x : rowform[id].second) cert_num(x);
        fputc('\n', CERTF); if ((int)CERT_KNOWN.size() <= id) CERT_KNOWN.resize(id + 64, 0); CERT_KNOWN[id] = 1;
    }
}
int pe_run_file(const char *path, double limit, double *stats, const char *logpath, const char *spill) {
    Node nd; if (!read_node(nd, path)) return -1;
    if (CERTF) cert_task_begin(nd);
    spill_prefix = spill ? spill : ""; spilled = 0;
    ST = Stats(); L.iters = 0; L.solves = 0; out_of_time = false; double t0 = now(); deadline = t0 + limit; knuth = false;
    openlog = logpath && logpath[0] ? fopen(logpath, "a") : nullptr;
    search(nd, 0);
    if (CERTF) { fputs("E\n", CERTF); fflush(CERTF); }
    if (openlog) fclose(openlog);
    stats[0] = ST.nodes; stats[1] = ST.closed; stats[2] = ST.open; stats[3] = ST.splits; stats[4] = ST.cuts; stats[5] = L.solves; stats[6] = L.iters; stats[7] = ST.maxdepth; stats[8] = now() - t0; stats[9] = 0; stats[10] = 0; stats[11] = out_of_time; stats[12] = ST.tFilter; stats[13] = ST.tSplit; stats[14] = ST.tEnum; stats[15] = ST.capped; stats[16] = rayfail; rayfail = 0; stats[17] = spilled; stats[18] = exact_fail; stats[19] = ST.tBase; stats[20] = ST.tHull; stats[21] = ST.tCopy; stats[22] = ST.direct_closed; stats[23] = ST.direct_fixed; stats[24] = ST.direct_split; spill_prefix.clear();
    return 0;
}
long long pe_exact_ok() { return exact_ok; }
long long pe_unproved() { return unproved; }
long long pe_exact_fail() { return exact_fail; }
// Knuth's estimate of a task's subtree: est nodes, cost seconds
int pe_dive_file(const char *path, double limit, unsigned long long seed, double *stats) {
    Node nd; if (!read_node(nd, path)) return -1;
    spill_prefix.clear(); ST = Stats(); out_of_time = false; double t0 = now(); deadline = t0 + limit; knuth = true; follow = false; kw = 1; kest = 1; kcost = 0; RNG.seed(seed);
    search(nd, 0); knuth = false;
    stats[0] = kest; stats[1] = kcost; stats[2] = now() - t0; stats[3] = ST.open;
    return 0;
}
// split a task: expand its node and write the children.  Returns the number of children, 0 if closed, -2 if open.
int pe_split_file(const char *path, const char *outprefix, const char *logpath) {
    Node nd; if (!read_node(nd, path)) return -1;
    Split sp; int st = expand(nd, 0, sp);
    if (st == 0) return 0;
    if (st == 2) { openlog = logpath && logpath[0] ? fopen(logpath, "a") : nullptr; describe_open(nd, 0); if (openlog) fclose(openlog); return -2; }
    Dom &D = nd.dom[sp.di]; Mod &m = mods[D.mi]; int M = m.M;
    vector<ll> sums(D.N); for (int i = 0; i < D.N; i++) { const int16_t *u = &D.d[(size_t)i * M]; ll s = 0; for (int r = 0; r < M; r++) s += sp.c[r] * u[r]; sums[i] = s; }
    vector<ll> vals = sums; sort(vals.begin(), vals.end()); vals.erase(unique(vals.begin(), vals.end()), vals.end());
    int nz = 0, last = -1; for (int r = 0; r < M; r++) if (sp.c[r]) { nz++; last = r; }
    pair<int, double> fr; if (nz == 1) fr = {m.pos + last, m.norm[last] / sp.c[last]}; else { fr = form_row(D.mi, sp.c); if ((int)rowform.size() < L.K) rowform.resize(L.K, {-1, {}}); rowform[fr.first] = {D.mi, sp.c}; }
    int idx = 0;
    for (ll v : vals) {
        Node ch = nd; Dom &Dc = ch.dom[sp.di]; int w = 0; for (int i = 0; i < D.N; i++) if (sums[i] == v) { memcpy(&Dc.d[(size_t)w * M], &D.d[(size_t)i * M], M * sizeof(int16_t)); w++; } Dc.N = w; Dc.d.resize((size_t)w * M); Dc.rank = -1;
        ch.fixed.push_back({fr.first, (double)v / fr.second});
        char name[512]; snprintf(name, sizeof name, "%s_%d", outprefix, idx++); write_node(ch, name);
    }
    return idx;
}
// a start node to a file
int pe_start_file(int npins, const int *pins, const char *path) {
    Node nd; nd.tried.assign(mods.size(), -99); nd.fullval.assign(mods.size(), {}); const int *p = pins;
    for (int a = 0; a < npins; a++) { int M = *p++; int mi = modidx[M]; Mod &m = mods[mi]; nd.fullval[mi].resize(M); for (int r = 0; r < M; r++) { int v = *p++; nd.fullval[mi][r] = v; nd.fixed.push_back({m.pos + r, v / m.norm[r]}); } nd.full |= 1u << mi; }
    for (int bit : {1, 2, 4}) { bool inv = true; for (int a = 0; a < (int)mods.size() && inv; a++) if ((nd.full >> a & 1) && !invariant_under(bit, nd.fullval[a])) inv = false; if (inv) nd.G |= bit; }
    write_node(nd, path); return nd.G;
}
void pe_set(int cap, int tests, int feas, int wide, int deep, int retry, int sample, double enodes) { CAP = cap; TESTS = tests; FEAS = feas; WIDE = wide; DEEP = deep; RETRY = retry; SAMPLE = sample; ENUM_NODES = (ll)enodes; }
void pe_pathlog(int v) { pathlog = v; }
void pe_longstep(int v) { LONGSTEP = v; }
void pe_openprefix(const char *p) { openprefix = p; }
void pe_pull(int p, double f) { PULL = p; PULLF = f; }
void pe_restore(int v) { RESTORE = v; }
void pe_strong(int v) { STRONG = v; }
void pe_usesym(int v) { USE_SYM = v; }
long long pe_sym_removed() { return sym_removed; }
void pe_pool(int v) { POOLMAX = v; }
long long pe_pool_kills() { return pool_kills; }
void pe_fmode(int v) { FMODE = v; }
void pe_hullswap(int v) { HULLSWAP = v; }
void pe_direct(int m_, int q) { DIRECTM = m_; DIRECTQ = q; }
void pe_prop(int m_, int q) { PROPM = m_; PROPQ = q; }
void pe_scan(int mode) { SCANMODE = mode; }
void pe_devex(int v) { DEVEX = v; }
void pe_opt(int droplast, int refreq) { DROPLAST = droplast; REFREQ = refreq; }
void pe_s7batch(int v) { S7BATCH = v; }
void pe_symform(int v) { SYMFORM = v; }
void pe_pqtop(int r, int q) { RTOP = r; PQTOP = q; }
void pe_killers(int v) { KILLK = v; KILL.clear(); }
void pe_killstats(double *o) { o[0] = kill_tests; o[1] = kill_hits; }
void pe_outstats(double *o) { for (int i = 0; i < 2; i++) { o[i * 4] = OUT_N[i]; o[i * 4 + 1] = OUT_IT[i]; o[i * 4 + 2] = OUT_LP[i]; o[i * 4 + 3] = OUT_T[i]; } }
void pe_chhist(double *o) { for (int a = 0; a < 8; a++) for (int b = 0; b < 8; b++) o[a * 8 + b] = CH_HIST[a][b]; }
void pe_samples(int v) { SAMPLES = v; }
long long pe_smpskips() { return smp_skips; }
void pe_closefirst(int q, double tau) { CLOSEQ = q; CLOSETAU = tau; }
void pe_cfstats(double *o) { o[0] = cf_calls; o[1] = cf_tests; o[2] = cf_close; o[3] = cf_fix; o[4] = tTilt; o[5] = tRank; }
void pe_ramp(int k) { RAMPK = k; }
void pe_rampstats(double *o) { o[0] = ramp_calls; o[1] = ramp_close; o[2] = ramp_fix; o[3] = ramp_split; o[4] = ramp_incons; o[5] = tRamp; o[6] = ramp_calls ? ramp_stsum / ramp_calls : 0; }
void pe_symsig(double v) { SYMSIG = v; }
void pe_partial(int v) { PARTIAL = v; }
void pe_selfirst(int v) { SELFIRST = v; }
void pe_listset(int k, const int *a) { LISTSET.assign(a, a + k); }
void pe_listafter(int k, const int *a) { LISTAFTER.assign(a, a + k); }
void pe_liststats2(double *o) { o[0] = list_tries; o[1] = list_ok; o[2] = list_cap; o[3] = list_sum; }
void pe_liststats(double *o) { o[0] = list_tries; o[1] = ST.enums; o[2] = ST.capped; }
void pe_prof3(double *o) { int i = 0; for (int d = 0; d < 200; d++) o[i++] = PR_N[d]; for (int d = 0; d < 200; d++) o[i++] = PR_C[d]; for (int d = 0; d < 200; d++) o[i++] = PR_ROWS[d]; for (int a = 0; a < 32; a++) o[i++] = PR_SPLIT[a]; for (int a = 0; a < 32; a++) o[i++] = PR_K[a]; for (int a = 0; a < 200 * 32; a++) o[i++] = PR_SD[a]; memset(PR_N, 0, sizeof PR_N); memset(PR_C, 0, sizeof PR_C); memset(PR_ROWS, 0, sizeof PR_ROWS); memset(PR_SPLIT, 0, sizeof PR_SPLIT); memset(PR_K, 0, sizeof PR_K); memset(PR_SD, 0, sizeof PR_SD); }
void pe_s7first(int v) { S7FIRST = v; }
void pe_s7nopp(int v) { S7NOPP = v; }
void pe_rtdual(int v) { RTDUAL = v; }
void pe_rtnear(int v) { RTNEAR = v; }
void pe_certfd(int fd) { if (CERTF) { fclose(CERTF); CERTF = nullptr; } if (fd >= 0) { CERTF = fdopen(fd, "w"); static char cbuf[1 << 20]; setvbuf(CERTF, cbuf, _IOFBF, sizeof cbuf); } }
void pe_splitw(int k, const int *a) { SPLITW.assign(a, a + k); }
void pe_tilef(int v) { TILEF = v; }
void pe_skipdone(int v) { SKIPDONE = v; }
void pe_refreq(int v) { REFREQ = v; }
void pe_incstats(double *o) { o[0] = inc_rows; }
void pe_nowt(int v) { NOWT = v; }
void pe_dropdep(int v) { DROPDEP = v; }
void pe_tiles(int v) { TILES = v; }
void pe_incrow(int v) { INCROW = v; }
void pe_sibrest(int v) { SIBREST = v; }
void pe_bkstats(double *o) { for (int i = 0; i < 3; i++) { o[i] = BKI[i]; o[3 + i] = BKN[i]; o[6 + i] = BKT[i]; BKI[i] = BKN[i] = 0; BKT[i] = 0; } }
void pe_rtub(int v) { RTUB = v; }
void pe_rtubstats(double *o) { o[0] = lp_ubstops; o[1] = lp_ubfalse; }
void pe_rtsstats(double *o) { o[0] = rts_hit; o[1] = rts_miss; }
void pe_rt2stats(double *o) { o[0] = rt2_fail; o[1] = rt2_proved; }
void pe_fdstats(double *o) { for (int i = 0; i < 64; i++) { o[3 * 0 + i * 9] = i < (int)mods.size() ? mods[i].M : 0; for (int j = 0; j < 8; j++) o[i * 9 + 1 + j] = FDS[i][j]; } memset(FDS, 0, sizeof FDS); }
void pe_lptag(double *o) { for (int i = 0; i < 12; i++) { o[i] = TI[i]; o[12 + i] = TN[i]; TI[i] = TN[i] = 0; } }
void pe_lpph(double *o) { for (int i = 0; i < 10; i++) { o[i] = PHI[i]; o[10 + i] = PHN[i]; o[20 + i] = PHT[i]; } o[30] = RTO[0]; o[31] = RTO[1]; o[32] = RTO[2]; o[33] = L.iters; memset(PHI, 0, sizeof PHI); memset(PHN, 0, sizeof PHN); memset(PHT, 0, sizeof PHT); memset(RTO, 0, sizeof RTO); }
void pe_sdpcb(sdp_cb_t f, int maxd) { SDPCB = f; SDPMAXD = maxd; sdp_calls = sdp_closed = 0; }
void pe_sdpstats(double *o) { o[0] = sdp_calls; o[1] = sdp_closed; }
void pe_bcache(int v) { BCACHE_ON = v; BCACHE.clear(); }
void pe_bcstats(double *o) { o[0] = bc_hit; o[1] = bc_miss; o[2] = bc_iters; o[3] = bc_stored; o[4] = BCACHE.size(); }
void pe_s7pick(int v) { S7PICK = v; }
void pe_s7alt(int a, int b) { S7ALT = a; S7ALTB = b; }
void pe_s7splitmax(double v) { S7SPLITMAX = v; }
void pe_import(double a) { IMPORT = a; }
void pe_certpool(int v) { CERTPOOL = v; }
void pe_cpoolstats(double *o) { o[0] = cpool_hits; o[1] = cpool_tests; o[2] = tCpool; }
void pe_s7early(int v) { S7EARLY = v; }
void pe_sel(int q, double alpha) { SELQ = q; SALPHA = alpha; }
void pe_selstats(double *o) { o[0] = tilt_calls; o[1] = tilt_iters; o[2] = sel_closed; o[3] = sel_fixed; o[4] = sel_split; o[5] = tTilt; o[6] = tRank; }
void pe_symlate(int v) { SYMLATE = v; }
void pe_symstats(double *o) { o[0] = sym_halved; o[1] = sym_splits; }
void pe_listl(int v) { LISTL = v; }
void pe_s7tie(int v) { S7TIE = v; }
void pe_s7(double sigmax, double memof) { SIGMAX = sigmax; MEMOF = memof; }
void pe_s7stats(double *o) { o[0] = s7_tests; o[1] = s7_skip; o[2] = s7_wide; o[3] = s7_fix; o[4] = s7_close; o[5] = s7_split; o[6] = s7_fallback; }
void pe_probe(int mode, int maxp, int rounds) { PROBE = mode; PROBE_MAXP = maxp; PROBE_ROUNDS = rounds; }
void pe_probestats(double *o) { o[0] = probe_calls; o[1] = probe_fix; o[2] = probe_close; o[3] = probe_lps; o[4] = probe_fail; o[5] = probe_pass_nofix; o[6] = tProbe; }
void pe_skipimplied(int v) { SKIPIMPLIED = v; }
void pe_skipstats(double *o) { o[0] = skip_implied; o[1] = tImplied; }
void pe_rangedual(int v) { RANGEDUAL = v; }
void pe_primstats(double *o) { o[0] = prim_iters; o[1] = prim_calls; prim_iters = prim_calls = 0; }
void pe_dualstart(int v) { DUALSTART = v; }
void pe_sublat(int v) { SUBLAT = v; }
void pe_substats(double *o) { o[0] = sub_closed; o[1] = sub_used; o[2] = sub_used ? sub_rank / sub_used : 0; o[3] = ST.enums; o[4] = ST.capped; }
void pe_scantau(double t) { SCANTAU = t; }
void pe_hist(double *t, double *f) { for (int i = 0; i < 24; i++) { t[i] = hist_t[i]; f[i] = hist_f[i]; } }
void pe_scanstats(double *o) { o[0] = scan_tests; o[1] = scan_fix; o[2] = scan_close; o[3] = scan_many; o[4] = scan_stops; o[5] = RHO; o[6] = tRank; o[7] = scan_implied; o[8] = scan_ranked; }
double pe_trank() { return tRank; }
long long pe_implied() { return scan_implied; }
long long pe_ranked() { return scan_ranked; }
void pe_dump(const char *p, int every) { dump_prefix = p; dump_every = every; dump_seen = 0; dump_written = 0; }
void pe_want(int k, const int *w) { want.assign(w, w + k); }
void pe_witness(int k, const int *a) { wit.assign(a, a + k); wit_err = 0; wit_nodes = 0; }
long long pe_wit_err() { return wit_err; }
long long pe_wit_nodes() { return wit_nodes; }
// a start node: pairs (M, then M values); run the tree or one dive.  stats: nodes closed open splits cuts lps iters maxdepth seconds est cost timedout
int pe_run(int npins, const int *pins, double limit, int dive, unsigned long long seed, double *stats, const char *logpath) {
    Node nd; nd.tried.assign(mods.size(), -99); nd.fullval.assign(mods.size(), {});
    const int *p = pins;
    for (int a = 0; a < npins; a++) { int M = *p++; int mi = modidx[M]; Mod &m = mods[mi]; nd.fullval[mi].resize(M); for (int r = 0; r < M; r++) { int v = *p++; nd.fullval[mi][r] = v; nd.fixed.push_back({m.pos + r, v / m.norm[r]}); } nd.full |= 1u << mi; }
    if (USE_SYM) for (int bit : {1, 2, 4}) { bool inv = true; for (int a = 0; a < (int)mods.size() && inv; a++) if ((nd.full >> a & 1) && !invariant_under(bit, nd.fullval[a])) inv = false; if (inv) nd.G |= bit; }
    ST = Stats(); L.iters = 0; L.solves = 0; out_of_time = false; double t0 = now(); deadline = t0 + limit; knuth = dive != 0; follow = dive == 2; kw = 1; kest = 1; kcost = 0; RNG.seed(seed);
    openlog = logpath && logpath[0] ? fopen(logpath, "a") : nullptr;
    if (CERTF) cert_task_begin(nd);
    search(nd, 0);
    if (CERTF) { fputs("E\n", CERTF); fflush(CERTF); }
    if (openlog) fclose(openlog);
    stats[0] = ST.nodes; stats[1] = ST.closed; stats[2] = ST.open; stats[3] = ST.splits; stats[4] = ST.cuts; stats[5] = L.solves; stats[6] = L.iters; stats[7] = ST.maxdepth; stats[8] = now() - t0; stats[9] = kest; stats[10] = kcost; stats[11] = out_of_time; stats[12] = ST.tFilter; stats[13] = ST.tSplit; stats[14] = ST.tEnum; stats[15] = ST.capped; stats[16] = rayfail; rayfail = 0;
    return 0;
}
}
