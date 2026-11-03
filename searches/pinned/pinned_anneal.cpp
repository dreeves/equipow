#include <functional>
// Stage A core: annealing over class-preserving swaps and a meet-in-the-middle over swaps for the congruence residual.
#include <cstdint>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <algorithm>
#include <random>
extern "C" {
// Anneal flips first (with class penalty W) then swaps.  G: n x rho doubles, a: n signs (in/out), y: rho (in/out) = y0 - sum a g,
// orb: orbit id per pair, chi: orientation, e: target per orbit.  Returns final class residual L1.
double anneal(int n, int rho, const double* G, int8_t* a, double* y, const int* orb, const int8_t* chi, int norb, const int* e,
              long long flips, long long swaps, double T0, double T1, double W, unsigned long long seed) {
    std::mt19937_64 rng(seed);
    std::uniform_real_distribution<double> U(0.0, 1.0);
    std::vector<int> res(norb);
    for (int c = 0; c < norb; c++) res[c] = e[c];
    for (int i = 0; i < n; i++) res[orb[i]] -= a[i] * chi[i];
    std::vector<double> gn(n);
    for (int i = 0; i < n; i++) { double s = 0; for (int j = 0; j < rho; j++) s += G[(size_t)i * rho + j] * G[(size_t)i * rho + j]; gn[i] = s; }
    auto dotyg = [&](int i) { const double* g = G + (size_t)i * rho; double s = 0; for (int j = 0; j < rho; j++) s += y[j] * g[j]; return s; };
    // phase 1: flips with the class penalty
    for (long long it = 0; it < flips; it++) {
        double T = T0 * std::pow(T1 / T0, (double)it / flips);
        int p = rng() % n;
        double d = 4 * a[p] * dotyg(p) + 4 * gn[p];
        int c = orb[p]; int dr = 2 * a[p] * chi[p];            // residual change
        d += W * ((res[c] + dr) * (res[c] + dr) - res[c] * res[c]);
        if (d <= 0 || U(rng) < std::exp(-d / T)) {
            const double* g = G + (size_t)p * rho;
            for (int j = 0; j < rho; j++) y[j] += 2 * a[p] * g[j];
            res[c] += dr; a[p] = -a[p];
        }
    }
    // greedy repair of the class residuals by flips
    for (int pass = 0; pass < 100000; pass++) {
        int bad = -1;
        for (int c = 0; c < norb; c++) if (res[c]) { bad = c; break; }
        if (bad < 0) break;
        int best = -1; double bd = 1e300;
        for (int p = 0; p < n; p++) if (orb[p] == bad) {
            int dr = 2 * a[p] * chi[p];
            if (std::abs(res[bad] + dr) >= std::abs(res[bad])) continue;
            double d = 4 * a[p] * dotyg(p) + 4 * gn[p];
            if (d < bd) { bd = d; best = p; }
        }
        if (best < 0) break;
        const double* g = G + (size_t)best * rho;
        for (int j = 0; j < rho; j++) y[j] += 2 * a[best] * g[j];
        res[orb[best]] += 2 * a[best] * chi[best]; a[best] = -a[best];
    }
    // phase 2: swaps inside orbits, keeping class sums
    std::vector<std::vector<int>> members(norb);
    for (int i = 0; i < n; i++) members[orb[i]].push_back(i);
    std::vector<double> v(rho);
    for (long long it = 0; it < swaps; it++) {
        double T = T1 * std::pow(0.02, (double)it / swaps);
        int p = rng() % n;
        auto& m = members[orb[p]];
        int q = m[rng() % m.size()];
        if (q == p || a[p] * chi[p] == a[q] * chi[q]) continue;
        const double* gp = G + (size_t)p * rho; const double* gq = G + (size_t)q * rho;
        double dy = 0, nn = 0;
        for (int j = 0; j < rho; j++) { double w = 2 * a[p] * gp[j] + 2 * a[q] * gq[j]; v[j] = w; dy += y[j] * w; nn += w * w; }
        double d = 2 * dy + nn;
        if (d <= 0 || U(rng) < std::exp(-d / T)) {
            for (int j = 0; j < rho; j++) y[j] += v[j];
            a[p] = -a[p]; a[q] = -a[q];
        }
    }
    double l1 = 0; for (int c = 0; c < norb; c++) l1 += std::abs(res[c]);
    return l1;
}

struct Sw { int p, q; int orb; };
// MITM: keys are single int64 values in Z/M after mixed radix; deltas per swap given as components with moduli mods (nmods).
// a: signs; psi: n x nmods int64 (a digit-shifted congruence value of each pair, modulo mods); r: residual components to cancel.
// Swaps from orbits in group A (t1 at a time, distinct orbits) and group B (t2).  Output: flips arrays (2*(t1+t2) ints per match).
long long mitm(int n, int nmods, const int8_t* a, const int* orb, const int8_t* chi, int norb, const int64_t* psi,
               const int64_t* mods, const int64_t* r, int t1, int t2, const int* orbit_order, int nA, long long cap,
               const double* G, int rho, const double* y, double maxdn, long long maxout, int* out, unsigned long long seed, long long* sizes) {
    std::mt19937_64 rng(seed);
    std::vector<std::vector<Sw>> SA(norb);
    std::vector<double> v(rho);
    for (int p = 0; p < n; p++) if (a[p] * chi[p] == 1) for (int q = 0; q < n; q++) if (orb[q] == orb[p] && a[q] * chi[q] == -1) {
        const double* gp = G + (size_t)p * rho; const double* gq = G + (size_t)q * rho;
        double nn = 0, dy = 0; for (int j = 0; j < rho; j++) { double w = 2 * a[p] * gp[j] + 2 * a[q] * gq[j]; nn += w * w; dy += y[j] * w; }
        if (2 * dy + nn <= maxdn) SA[orb[p]].push_back({p, q, orb[p]});
    }
    auto delta = [&](const Sw& s, int64_t* d) {
        for (int k = 0; k < nmods; k++) {
            __int128 w = (__int128)a[s.p] * psi[(size_t)s.p * nmods + k] + (__int128)a[s.q] * psi[(size_t)s.q * nmods + k];
            int64_t m = mods[k]; int64_t x = (int64_t)(w % m); if (x < 0) x += m; d[k] = x;
        }
    };
    std::vector<__int128> radix(nmods);
    { __int128 b = 1; for (int k = 0; k < nmods; k++) { radix[k] = b; b *= mods[k]; } }
    auto encode = [&](const int64_t* c) { unsigned __int128 s = 0; for (int k = 0; k < nmods; k++) s += (unsigned __int128)c[k] * (unsigned __int128)radix[k]; return (uint64_t)(s ^ (s >> 64)); };
    struct E1 { uint64_t key; int s[4]; };
    auto build = [&](const int* orbs, int no, int t, std::vector<E1>& L, bool negate_with_r) {
        // random sampling of t-subsets of orbits with one swap each, up to cap entries
        std::vector<int> pool; for (int i = 0; i < no; i++) if (!SA[orbs[i]].empty()) pool.push_back(orbs[i]);
        if ((int)pool.size() < t) return;
        // systematic enumeration when small, random otherwise
        long long total = 1; { /* estimate */ double avg = 0; for (int o : pool) avg += SA[o].size(); avg /= pool.size(); double est = 1; for (int i = 0; i < t; i++) est *= avg * (pool.size() - i) / (i + 1); total = (long long)est; }
        std::vector<int64_t> c(nmods), d(nmods);
        std::vector<int> idx(t);
        auto emit = [&](const std::vector<const Sw*>& ss, const std::vector<int>& ids) {
            std::fill(c.begin(), c.end(), 0);
            for (auto* s : ss) { delta(*s, d.data()); for (int k = 0; k < nmods; k++) { c[k] += d[k]; if (c[k] >= mods[k]) c[k] -= mods[k]; } }
            if (negate_with_r) for (int k = 0; k < nmods; k++) { int64_t x = (mods[k] - r[k] - c[k]) % mods[k]; if (x < 0) x += mods[k]; c[k] = x; }
            E1 e; e.key = encode(c.data()); for (int i = 0; i < 4; i++) e.s[i] = i < (int)ids.size() ? ids[i] : -1;
            L.push_back(e);
        };
        // encode a swap as orbit*65536 + index in the orbit's swap list
        if (total <= cap) {
            std::vector<int> pick(t);
            std::vector<const Sw*> ss(t); std::vector<int> ids(t);
            // recursive enumeration via explicit stack
            struct Rec { static void go(int pos, int start, int t, const std::vector<int>& pool, std::vector<std::vector<Sw>>& SA, std::vector<const Sw*>& ss, std::vector<int>& ids, decltype(emit)& emit) {
                if (pos == t) { emit(ss, ids); return; }
                for (int i = start; i < (int)pool.size(); i++) { int o = pool[i]; for (int j = 0; j < (int)SA[o].size(); j++) { ss[pos] = &SA[o][j]; ids[pos] = o * 65536 + j; go(pos + 1, i + 1, t, pool, SA, ss, ids, emit); } }
            } };
            Rec::go(0, 0, t, pool, SA, ss, ids, emit);
        } else {
            std::vector<const Sw*> ss(t); std::vector<int> ids(t);
            for (long long it = 0; it < cap; it++) {
                std::vector<int> ch;
                while ((int)ch.size() < t) { int o = pool[rng() % pool.size()]; if (std::find(ch.begin(), ch.end(), o) == ch.end()) ch.push_back(o); }
                for (int i = 0; i < t; i++) { int o = ch[i]; int j = rng() % SA[o].size(); ss[i] = &SA[o][j]; ids[i] = o * 65536 + j; }
                emit(ss, ids);
            }
        }
    };
    std::vector<E1> L1, L2;
    L1.reserve(cap); L2.reserve(cap);
    build(orbit_order, nA, t1, L1, false);
    build(orbit_order + nA, norb - nA, t2, L2, true);
    sizes[0] = L1.size(); sizes[1] = L2.size();
    if (L1.empty() || L2.empty()) return 0;
    std::sort(L2.begin(), L2.end(), [](const E1& x, const E1& y) { return x.key < y.key; });
    long long cnt = 0;
    for (const E1& e : L1) {
        auto it = std::lower_bound(L2.begin(), L2.end(), e, [](const E1& x, const E1& y) { return x.key < y.key; });
        for (; it != L2.end() && it->key == e.key; ++it) {
            if (cnt < maxout) {
                int* w = out + cnt * 2 * (t1 + t2);
                int pos = 0;
                for (int i = 0; i < t1; i++) { int o = e.s[i] >> 16, j = e.s[i] & 65535; w[pos++] = SA[o][j].p; w[pos++] = SA[o][j].q; }
                for (int i = 0; i < t2; i++) { int o = it->s[i] >> 16, j = it->s[i] & 65535; w[pos++] = SA[o][j].p; w[pos++] = SA[o][j].q; }
            }
            cnt++;
        }
    }
    return cnt;
}
}

