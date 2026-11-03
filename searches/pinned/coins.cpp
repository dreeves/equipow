// For excess e and K: is 2^K a sum of coins?  A core is a product of blocks; its coin is L * 2^max(0, K + e - O), valid when <= 2^K.
// Method as in pow2.py's description of its search: enumerate every core with excess >= e, then decide the coin problem.
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <algorithm>
#include <map>
#include <set>
#include <queue>
#include <cstdint>
using namespace std;
typedef unsigned __int128 u128;
struct Atom { long long n; int m; double lg, ex; };
vector<Atom> atoms;
vector<double> bestDens;   // best excess per bit among atoms >= i
static int K, E;
static double budget;
static map<u128, vector<int>> coins;   // coin -> core (atom indices)
static vector<int> cur;
static long long nodes;
static size_t maxcoins = 3000000;
static void dfs(int i, u128 L, int O, double lg) {
    nodes++;
    double ex = O - lg;
    if (!cur.empty() && ex >= E - 1e-12) {
        int a = K + E - O; if (a < 0) a = 0;
        if (lg + a <= K + 1e-9) {
            u128 S = L << a;
            if (S <= ((u128)1 << K) && !coins.count(S) && coins.size() < maxcoins) coins[S] = cur;
        }
    }
    for (int j = i; j < (int)atoms.size(); j++) {
        double nlg = lg + atoms[j].lg;
        if (nlg > K + 1e-9) continue;
        // bound: the most excess reachable with the remaining bits, using atoms >= j
        double nex = O + atoms[j].m - nlg;
        if (nex + bestDens[j] * (K - nlg) < E - 1e-9) continue;
        cur.push_back(j);
        dfs(j, L * (u128)atoms[j].n, O + atoms[j].m, nlg);
        cur.pop_back();
    }
}
static u128 gcdu(u128 a, u128 b) { while (b) { u128 t = a % b; a = b; b = t; } return a; }
// decide: is t a nonnegative combination of c (t, c scaled)?  Returns 1 yes, 0 no, -1 undecided; rep gets the coins used.
static int decide(u128 t, vector<u128>& c, vector<int>& rep, long long maxres) {
    sort(c.begin(), c.end());
    if (binary_search(c.begin(), c.end(), t)) { rep = {(int)(lower_bound(c.begin(), c.end(), t) - c.begin())}; return 1; }
    u128 c0 = c[0];
    if (c0 <= (u128)maxres) {
        long long m = (long long)c0;
        const unsigned long long INF = ~0ULL;
        vector<unsigned long long> d(m, INF); vector<int> from(m, -1);
        d[0] = 0;
        // Dijkstra with a heap
        typedef pair<unsigned long long, long long> P;
        priority_queue<P, vector<P>, greater<P>> pq; pq.push({0, 0});
        long long target = (long long)(t % c0);
        if (t >> 63) return -1;
        unsigned long long T = (unsigned long long)t;
        vector<unsigned long long> cs; for (auto& x : c) cs.push_back((unsigned long long)x);
        while (!pq.empty()) {
            auto [du, u] = pq.top(); pq.pop();
            if (du != d[u]) continue;
            if (du > T) break;
            if (u == target) break;
            for (size_t i = 1; i < cs.size(); i++) {
                if (cs[i] > T) break;
                unsigned long long nd = du + cs[i];
                if (nd > T) break;
                long long v = (long long)(nd % (unsigned long long)m);
                if (nd < d[v]) { d[v] = nd; from[v] = (int)i; pq.push({nd, v}); }
            }
        }
        if (d[target] == INF || d[target] > T) return 0;
        long long u = target; unsigned long long rem = T - d[target];
        while (u != 0) { int i = from[u]; rep.push_back(i); u = (long long)((d[u] - cs[i]) % (unsigned long long)m); }
        for (unsigned long long q = rem / cs[0]; q > 0 && rep.size() < 2000000; q--) rep.push_back(0);
        return 1;
    }
    return -1;
}
int main(int argc, char** argv) {
    // usage: scan atomsfile emin emax Kmax maxres
    FILE* fp = fopen(argv[1], "r");
    long long n; int m;
    while (fscanf(fp, "%lld %d", &n, &m) == 2) { if (n == 2) continue; Atom a; a.n = n; a.m = m; a.lg = log2((double)n); a.ex = m - a.lg; atoms.push_back(a); }
    fclose(fp);
    int emin = atoi(argv[2]), emax = atoi(argv[3]), Kmax = atoi(argv[4]); long long maxres = atoll(argv[5]);
    sort(atoms.begin(), atoms.end(), [](const Atom& x, const Atom& y) { return x.ex / x.lg > y.ex / y.lg; });
    bestDens.assign(atoms.size(), 0);
    for (int i = (int)atoms.size() - 1; i >= 0; i--) { bestDens[i] = max(atoms[i].ex / atoms[i].lg, i + 1 < (int)atoms.size() ? bestDens[i + 1] : 0.0); }
    int startK = argc > 6 ? atoi(argv[6]) : 1;
    for (E = emin; E <= emax; E++) {
        bool done = false;
        vector<int> undecided;
        for (K = startK; K <= Kmax && !done; K++) {
            coins.clear(); nodes = 0;
            dfs(0, 1, 0, 0.0);
            if (coins.empty()) continue;
            vector<u128> C; for (auto& kv : coins) C.push_back(kv.first);
            u128 T = (u128)1 << K;
            u128 g = 0; for (auto x : C) g = gcdu(x, g);
            if (T % g) continue;
            vector<u128> sc; for (auto x : C) sc.push_back(x / g);
            vector<u128> ss = sc;
            vector<int> rep;
            int r = decide(T / g, ss, rep, maxres);
            fflush(stdout);
            if (r == -1) { undecided.push_back(K); continue; }
            if (r == 1) {
                printf("e=%d first K=%d (coins %zu, nodes %lld, undecided below: ", E, K, C.size(), nodes);
                for (int u : undecided) printf("%d ", u);
                printf(")\n  join:");
                map<u128, int> cnt;
                for (int i : rep) cnt[ss[i] * g]++;
                u128 tot = 0;
                for (auto& kv : cnt) {
                    tot += kv.first * kv.second;
                    auto& core = coins[kv.first];
                    int O = 0; long long dummy = 0; double lg = 0;
                    printf(" %dx[", kv.second);
                    for (int j : core) { printf("%lld.", atoms[j].n); O += atoms[j].m; lg += atoms[j].lg; }
                    int a = K + E - O; if (a < 0) a = 0;
                    printf("t%d o=%d]", a, O + a);
                    (void)dummy;
                }
                printf(" total==2^K: %s\n", tot == T ? "yes" : "NO");
                fflush(stdout);
                done = true;
                startK = K;
            }
        }
        if (!done) { printf("e=%d none up to K=%d; undecided:", E, Kmax); for (int u : undecided) printf(" %d", u); printf("\n"); fflush(stdout); }
    }
}
