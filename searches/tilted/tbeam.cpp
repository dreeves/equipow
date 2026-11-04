// The tilted K-best beam and a batch enumerator of cosets.
// Beam: Gamma = pi - 2 sum log P(a_x), with P(a) = (1 + a t) / 2, pi the penalty about the tilted mean; e = (a - t) / sqrt(1 - t^2).
//   pi' = pi - e^2 + (alpha - e)^2 / (1 - h),  p' = p + u (alpha - e) / (1 - h),  alpha = g . p.
// Stochastic beam: gumbel > 0 adds Gumbel noise of that scale to the keys at each selection, so that restarts differ.
// Enumerator: for each coset a1 = 2 (z0 + sum_{a_x = -1} z_x) - 1, Schnorr-Euchner in the given Gram-Schmidt data, bound[k] = min(R2, (k+1)/d R2 + floor); a leaf with all entries +-1 is a solution.
#include <cstdint>
#include <cstring>
#include <cmath>
#include <vector>
#include <algorithm>
#include <random>
#include <numeric>
extern "C" long long tbeam(int L, int rho, const double *g, const double *u, const double *h, const double *ep, const double *em, const double *lp, const double *lm, const double *field, const long long *Ks, int ncheck, const int *cklev, const double *T, const double *p0, double pi0,
                           double gumbel, unsigned long long seed, long long Kout, uint64_t *out_signs, double *out_gamma, double *out_pi) {
    int W = (L + 63) / 64;
    long long Kmax = 1; for (int l = 0; l < L; l++) Kmax = std::max(Kmax, Ks[l]);
    std::mt19937_64 rng(seed); std::uniform_real_distribution<double> U01(1e-300, 1.0);
    std::vector<double> P(Kmax * rho, 0.0), P2(Kmax * rho), Pi(Kmax, 0.0), Pi2(Kmax), Ga(Kmax, 0.0), Ga2(Kmax), Se(Kmax, 0.0), Se2(Kmax), alpha(Kmax), key(2 * Kmax), sc(2 * Kmax), scp(2 * Kmax), sel(2 * Kmax);
    std::vector<uint64_t> S(Kmax * W, 0), S2(Kmax * W, 0);
    std::vector<int> idx(2 * Kmax);
    long long n = 1; int nextck = 0;
    std::memcpy(P.data(), p0, rho * sizeof(double)); Pi[0] = pi0; Ga[0] = pi0; Se[0] = pi0;
    for (int l = 0; l < L; l++) {
        const double *gl = g + (size_t)l * rho, *ul = u + (size_t)l * rho;
        double id = 1.0 / (1.0 - h[l]), e1 = ep[l], e2 = em[l], lp1 = lp[l], lp2 = lm[l];
        long long K = Ks[l];
        for (long long i = 0; i < n; i++) {
            const double *pp = &P[i * rho]; double a = 0;
            for (int j = 0; j < rho; j++) a += gl[j] * pp[j];
            alpha[i] = a;
            double d1 = a - e1, d2 = a - e2;
            scp[2 * i] = Pi[i] - e1 * e1 + d1 * d1 * id;
            scp[2 * i + 1] = Pi[i] - e2 * e2 + d2 * d2 * id;
            sc[2 * i] = Ga[i] + (scp[2 * i] - Pi[i]) + lp1;
            sc[2 * i + 1] = Ga[i] + (scp[2 * i + 1] - Pi[i]) + lp2;
            sel[2 * i] = Se[i] + (scp[2 * i] - Pi[i]) + lp1 + field[l];
            sel[2 * i + 1] = Se[i] + (scp[2 * i + 1] - Pi[i]) + lp2;
        }
        long long m = 2 * n, keep = std::min(m, K);
        std::iota(idx.begin(), idx.begin() + m, 0);
        if (m > K) {
            if (gumbel > 0) {
                for (long long q = 0; q < m; q++) key[q] = sel[q] - gumbel * (-std::log(-std::log(U01(rng))));
                std::nth_element(idx.begin(), idx.begin() + K, idx.begin() + m, [&](int x, int y) { return key[x] < key[y]; });
            } else {
                std::nth_element(idx.begin(), idx.begin() + K, idx.begin() + m, [&](int x, int y) { return sel[x] < sel[y]; });
            }
        }
        for (long long q = 0; q < keep; q++) {
            int c = idx[q]; long long i = c / 2; double e = (c & 1) ? e2 : e1, plus = (c & 1) ? 0 : 1;
            double f = (alpha[i] - e) * id;
            const double *pp = &P[i * rho]; double *pn = &P2[q * rho];
            for (int j = 0; j < rho; j++) pn[j] = pp[j] + ul[j] * f;
            Pi2[q] = scp[c]; Ga2[q] = sc[c]; Se2[q] = sel[c];
            std::memcpy(&S2[q * W], &S[i * W], W * sizeof(uint64_t));
            if (plus) S2[q * W + l / 64] |= 1ULL << (l % 64);
        }
        P.swap(P2); Pi.swap(Pi2); Ga.swap(Ga2); Se.swap(Se2); S.swap(S2); n = keep;
        if (nextck < ncheck && cklev[nextck] == l) {
            const double *Tj = T + (size_t)nextck * rho * rho;
            for (long long i = 0; i < n; i++) {
                double *pp = &P[i * rho]; double *pq = &P2[0];
                for (int a = 0; a < rho; a++) { double s = 0; const double *ta = Tj + (size_t)a * rho; for (int b = 0; b < rho; b++) s += ta[b] * pp[b]; pq[a] = s; }
                std::memcpy(pp, pq, rho * sizeof(double));
            }
            nextck++;
        }
    }
    std::vector<long long> ord(n); std::iota(ord.begin(), ord.end(), 0);
    std::sort(ord.begin(), ord.end(), [&](long long x, long long y) { return Ga[x] < Ga[y]; });
    long long out = std::min(n, Kout);
    for (long long q = 0; q < out; q++) { out_gamma[q] = Ga[ord[q]]; out_pi[q] = Pi[ord[q]]; std::memcpy(out_signs + q * W, &S[ord[q] * W], W * sizeof(uint64_t)); }
    return out;
}
namespace {
struct E {
    int d, f; const double *mu, *rr; double *tau; double *bound; const int32_t *B; const int64_t *a1; long long max_nodes, maxsol; int8_t *out;
    long long nodes = 0, nsol = 0; bool stop = false; std::vector<double> sigma; std::vector<long long> x; std::vector<int> begin; std::vector<int64_t> a;
    inline double M(int l, int i) const { return mu[(size_t)l * d + i]; }
    inline double &S(int row, int j) { return sigma[(size_t)row * (d + 1) + j]; }
    void leaf() {
        for (int k = 0; k < f; k++) a[k] = a1[k];
        for (int l = 0; l < d; l++) if (x[l]) { const int32_t *row = B + (size_t)l * f; long long cl = 2 * x[l]; for (int k = 0; k < f; k++) a[k] += cl * row[k]; }
        for (int k = 0; k < f; k++) if (a[k] != 1 && a[k] != -1) return;
        if (nsol < maxsol) for (int k = 0; k < f; k++) out[nsol * f + k] = (int8_t)a[k];
        nsol++;
        if (nsol >= maxsol) stop = true;
    }
    void rec(int i, double above, double center) {
        double c0 = std::round(center), y = c0 - center, dd = (y <= 0) ? 1.0 : -1.0, cur = c0, step = dd;
        const double b = bound[d - 1 - i], r = rr[i];
        for (int first = 1;; first = 0) {
            double diff = cur - center, p = above + diff * diff * r;
            nodes++;
            if (nodes > max_nodes) { stop = true; return; }
            if (p > b) return;
            x[i] = (long long)cur;
            if (i == 0) { leaf(); if (stop) return; }
            else {
                int row = i - 1;
                if (first) {
                    for (int l = begin[i]; l >= i; l--) S(row, l) = S(row, l + 1) + x[l] * M(l, row);
                    if (begin[i] > begin[row]) begin[row] = begin[i];
                    begin[i] = i;
                } else {
                    S(row, i) = S(row, i + 1) + x[i] * M(i, row);
                    if (i > begin[row]) begin[row] = i;
                }
                rec(row, p, -(tau[row] + S(row, i)));
                if (stop) return;
            }
            cur += step; step = -step; step = (step > 0) ? step + 1.0 : step - 1.0;
        }
    }
};
}
// out_sol: maxsol x f signs; out_idx: the coset of each.  stats: [cosets, nodes, cosets that reached 1000 nodes, truncated]
extern "C" long long batch(int L, int f, int d, const uint64_t *signs, long long K, const int64_t *zx, const int64_t *z0, const int32_t *B, const double *mu, const double *rr, const double *Q,
                           double floor_, double sag, double tail, long long max_nodes, long long maxsol, int8_t *out_sol, long long *out_idx, double *stats, double *perp_out) {
    int W = (L + 63) / 64;
    E e; e.d = d; e.f = f; e.mu = mu; e.rr = rr; e.B = B; e.max_nodes = max_nodes; e.maxsol = 1;
    e.sigma.assign((size_t)d * (d + 1), 0.0); e.x.assign(d, 0); e.begin.resize(d); e.a.resize(f);
    std::vector<int64_t> z(f); std::vector<int64_t> a1(f); std::vector<double> v(f), tau(d), bound(d); std::vector<int8_t> one(f);
    long long nsol = 0; double cosets = 0, nodes = 0, big = 0, trunc = 0;
    for (long long c = 0; c < K; c++) {
        std::memcpy(z.data(), z0, f * sizeof(int64_t));
        const uint64_t *sg = signs + c * W;
        for (int l = 0; l < L; l++) if (!((sg[l / 64] >> (l % 64)) & 1)) { const int64_t *zl = zx + (size_t)l * f; for (int k = 0; k < f; k++) z[k] += zl[k]; }
        for (int k = 0; k < f; k++) { a1[k] = 2 * z[k] - 1; v[k] = 0.5 * (double)a1[k]; }
        double nv = 0; for (int k = 0; k < f; k++) nv += v[k] * v[k];
        double np = 0;
        for (int i = 0; i < d; i++) {
            const double *qi = Q + (size_t)i * f; double s = 0;
            for (int k = 0; k < f; k++) s += qi[k] * v[k];
            np += s * s; tau[i] = s / std::sqrt(rr[i]);
        }
        double R2 = f / 4.0 - (nv - np);
        if (perp_out) perp_out[c] = f - 4 * R2;
        cosets++;
        if (R2 <= 0) continue;
        for (int k = 0; k < d; k++) { double x_ = (k + 1.0) / d; bound[k] = std::min(R2 + 1e-6, x_ * R2 * (1.0 - sag * (1.0 - x_)) + floor_ + tail * std::exp(-x_ * 10.0)); }
        e.tau = tau.data(); e.bound = bound.data(); e.a1 = a1.data(); e.nodes = 0; e.nsol = 0; e.stop = false; e.out = one.data();
        for (int i = 0; i < d; i++) e.begin[i] = d - 1;
        e.rec(d - 1, 0.0, -tau[d - 1]);
        nodes += e.nodes; big += e.nodes >= 1000; trunc += e.nodes > max_nodes;
        if (e.nsol > 0 && nsol < maxsol) { std::memcpy(out_sol + nsol * f, one.data(), f); out_idx[nsol] = c; nsol++; }
    }
    stats[0] = cosets; stats[1] = nodes; stats[2] = big; stats[3] = trunc;
    return nsol;
}
