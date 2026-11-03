// Schnorr-Euchner enumeration of t + sum c_i b_i (basis in rows, Gram-Schmidt data given), per-level bounds.
// A leaf is a solution when a = a1 + 2 sum c_i b_i has all entries +-1 (checked in exact integers).
#include <cstdint>
#include <cmath>
#include <vector>
namespace {
struct E {
    int d, f; const double* mu; const double* rr; const double* tau; const double* bound;
    const int32_t* B; const int64_t* a1; long long max_nodes, maxsol; int8_t* out;
    long long nodes = 0, nsol = 0; long long* lc; bool stop = false;
    std::vector<double> sigma; std::vector<long long> x; std::vector<int> begin; std::vector<int64_t> a;
    inline double M(int l, int i) const { return mu[(size_t)l * d + i]; }
    inline double& S(int row, int j) { return sigma[(size_t)row * (d + 1) + j]; }
    void leaf() {
        for (int k = 0; k < f; k++) a[k] = a1[k];
        for (int l = 0; l < d; l++) if (x[l]) { const int32_t* row = B + (size_t)l * f; long long cl = 2 * x[l]; for (int k = 0; k < f; k++) a[k] += cl * row[k]; }
        for (int k = 0; k < f; k++) if (a[k] != 1 && a[k] != -1) return;
        if (nsol < maxsol) for (int k = 0; k < f; k++) out[nsol * f + k] = (int8_t)a[k];
        nsol++;
        if (nsol >= maxsol) stop = true;
    }
    void rec(int i, double above, double center) {
        double c0 = std::round(center);
        double y = c0 - center;
        double dd = (y <= 0) ? 1.0 : -1.0;   // first step goes toward the side of center
        double cur = c0, step = dd;
        const double b = bound[d - 1 - i], r = rr[i];
        for (int first = 1;; first = 0) {
            double diff = cur - center;
            double p = above + diff * diff * r;
            nodes++;
            if (nodes > max_nodes) { stop = true; return; }
            if (p > b) return;
            if (lc) lc[d - 1 - i]++;
            x[i] = (long long)cur;
            if (i == 0) {
                leaf();
                if (stop) return;
            } else {
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
            // zigzag: c0, c0+dd, c0-dd, c0+2dd, ...
            cur += step;
            step = -step - ((step > 0) ? 1.0 : -1.0) * 0.0;
            step = (step > 0) ? step + 1.0 : step - 1.0;
        }
    }
};
}
extern "C" long long enum_cvp(int d, int f, const double* mu, const double* rr, const double* tau, const double* bound,
                   const int32_t* B, const int64_t* a1, long long max_nodes, long long maxsol, int8_t* out,
                   long long* nodes_out, long long* level_counts) {
    E e; e.d = d; e.f = f; e.mu = mu; e.rr = rr; e.tau = tau; e.bound = bound; e.B = B; e.a1 = a1;
    e.max_nodes = max_nodes; e.maxsol = maxsol; e.out = out; e.lc = level_counts;
    e.sigma.assign((size_t)d * (d + 1), 0.0); e.x.assign(d, 0); e.begin.resize(d);
    for (int i = 0; i < d; i++) e.begin[i] = d - 1;
    e.a.resize(f);
    e.rec(d - 1, 0.0, -tau[d - 1]);
    *nodes_out = e.nodes;
    return e.nsol;
}
