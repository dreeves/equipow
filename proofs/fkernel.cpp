// Claude's second check of a form tree stream: exact integers, no solver, no floating point, nothing taken from the prover, no code shared with formtree.py.  The argument and the format are stated in formtree.py's docstring.
// Reads tasks from stdin, writes one verdict line per task on stdout.  g++ -O2 -std=c++17 -o fkernel proofs/fkernel.cpp
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include <unistd.h>
#include <sys/resource.h>
using namespace std;
typedef __int128 LL; typedef unsigned __int128 ULL; typedef long long ll;

// ---- SHA-256, for the names of nodes
struct Sha {
    uint32_t h[8]; uint64_t len = 0; unsigned char buf[64]; size_t fill = 0;
    Sha() { static const uint32_t i[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19}; memcpy(h, i, sizeof h); }
    static uint32_t ror(uint32_t x, int k) { return (x >> k) | (x << (32 - k)); }
    void block(const unsigned char *p) {
        static const uint32_t K[64] = {0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
        uint32_t w[64]; for (int i = 0; i < 16; i++) w[i] = (uint32_t)p[4 * i] << 24 | (uint32_t)p[4 * i + 1] << 16 | (uint32_t)p[4 * i + 2] << 8 | p[4 * i + 3];
        for (int i = 16; i < 64; i++) { uint32_t a = ror(w[i - 15], 7) ^ ror(w[i - 15], 18) ^ (w[i - 15] >> 3), b = ror(w[i - 2], 17) ^ ror(w[i - 2], 19) ^ (w[i - 2] >> 10); w[i] = w[i - 16] + a + w[i - 7] + b; }
        uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], k = h[7];
        for (int i = 0; i < 64; i++) { uint32_t t1 = k + (ror(e, 6) ^ ror(e, 11) ^ ror(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i], t2 = (ror(a, 2) ^ ror(a, 13) ^ ror(a, 22)) + ((a & b) ^ (a & c) ^ (b & c)); k = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2; }
        h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += k;
    }
    void add(const void *d, size_t l) { const unsigned char *p = (const unsigned char *)d; len += l; while (l) { size_t c = min(l, 64 - fill); memcpy(buf + fill, p, c); fill += c; p += c; l -= c; if (fill == 64) { block(buf); fill = 0; } } }
    string hex() { uint64_t bits = len * 8; unsigned char pad = 0x80; add(&pad, 1); unsigned char z = 0; while (fill != 56) add(&z, 1); unsigned char b[8]; for (int i = 0; i < 8; i++) b[i] = (unsigned char)(bits >> (56 - 8 * i)); add(b, 8); char s[65]; for (int i = 0; i < 8; i++) snprintf(s + 8 * i, 9, "%08x", h[i]); return string(s, 64); }
};

// ---- input: read(2), so that a verdict goes out as soon as its task has come in
static unsigned char ibuf[1 << 16]; static size_t ipos = 0, ilen = 0;
static int getch() { if (ipos == ilen) { ssize_t r; do r = read(0, ibuf, sizeof ibuf); while (r < 0); if (r == 0) return -1; ilen = (size_t)r; ipos = 0; } return ibuf[ipos++]; }
static int token() { int c; do c = getch(); while (c == ' ' || c == '\n'); return c; }
static const ULL LIMIT_DIGITS = (~(ULL)0 >> 1) / 10 - 1;
static string stream_error;
static const int MAX_M = 128, MAX_ID = 1 << 18, MAX_RATIO_ROWS = 4096; static const ll MAX_VALUES = 1024;   // nothing is ever allocated in proportion to a number in the stream without one of these limits
static LL read_int() {
    int c; do c = getch(); while (c == ' ' || c == '\n');
    bool neg = false; if (c == '-') { neg = true; c = getch(); }
    if (c < '0' || c > '9') { stream_error = "a number was expected"; return 0; }
    ULL v = 0; while (c >= '0' && c <= '9') { if (v > LIMIT_DIGITS) { stream_error = "a number too large"; return 0; } v = v * 10 + (c - '0'); c = getch(); }
    return neg ? -(LL)v : (LL)v;
}

// ---- the lattice and the grids
static int n_, m_, e_;
static vector<vector<LL>> Cbin; static vector<LL> Cmax;   // C(p, t) for p < n, t < m
struct ModInfo { bool ok = false; string why; vector<LL> g, rep; };
static map<int, ModInfo> MODS;
static bool prime_power(int M) { if (M < 2) return false; int p = 2; while (M % p) p++; while (M % p == 0) M /= p; return M == 1; }
static int smallest_prime(int M) { int p = 2; while (M % p) p++; return p; }
static vector<LL> mulmod(const vector<LL> &a, const vector<LL> &b, int M) { vector<LL> o(M, 0); for (int i = 0; i < M; i++) if (a[i] != 0) for (int j = 0; j < M; j++) o[(i + j) % M] += a[i] * b[j]; return o; }
static ModInfo &mod_info(int M) {
    auto it = MODS.find(M); if (it != MODS.end()) return it->second;
    ModInfo &I = MODS[M];
    if (!prime_power(M)) { I.why = "not a prime power"; return I; }
    vector<LL> g(M, 0); g[0] = 1; vector<LL> xm(M, 0), xp(M, 0); xm[0] -= 1; xm[1 % M] += 1; xp[0] += 1; xp[1 % M] += 1;
    for (int i = 0; i < m_; i++) g = mulmod(g, xm, M);
    for (int i = 0; i < e_; i++) g = mulmod(g, xp, M);
    I.g = g; vector<LL> h(M, 0);
    if (smallest_prime(M) == 2) {
        // the coset of the 2-adic lemma: H = (x+1)^(2^t-1-m-e) Psi(x^(2^t)) mod 2
        int t = 0, u = n_; while (u % 2 == 0) { u /= 2; t++; }
        if ((1LL << t) - 1 < m_ + e_) { I.why = "2^t - 1 < m + e: the 2-adic lemma does not apply"; return I; }
        vector<char> a(M, 0); a[0] = 1; for (ll i = 0; i < (1LL << t) - 1 - m_ - e_; i++) { vector<char> b(M, 0); for (int r = 0; r < M; r++) if (a[r]) { b[r] ^= 1; b[(r + 1) % M] ^= 1; } a = b; }
        vector<char> psi(M, 0); for (int i = 0; i < u; i++) psi[(ll)((ll)i << t) % M] ^= 1;
        vector<char> pr(M, 0); for (int i = 0; i < M; i++) if (a[i]) for (int j = 0; j < M; j++) if (psi[j]) pr[(i + j) % M] ^= 1;
        for (int i = 0; i < M; i++) h[i] = pr[i];
    } else {
        // an odd prime power: a vector of L(M) with the parities of the class sizes, from a linear system over F_2
        vector<vector<char>> A(M, vector<char>(M + 1, 0));
        for (int r = 0; r < M; r++) { for (int s = 0; s < M; s++) A[r][s] = (char)(((g[((r - s) % M + M) % M] % 2) + 2) % 2); int sz = 0; for (int p = r; p < n_; p += M) sz++; A[r][M] = sz % 2; }
        vector<int> where(M, -1); int row = 0;
        for (int c = 0; c < M && row < M; c++) { int s = row; while (s < M && !A[s][c]) s++; if (s == M) continue; swap(A[s], A[row]); for (int i = 0; i < M; i++) if (i != row && A[i][c]) for (int j = c; j <= M; j++) A[i][j] ^= A[row][j]; where[c] = row; row++; }
        for (int r = row; r < M; r++) if (A[r][M]) { I.why = "no vector of L(M) has the parities of the class sizes"; return I; }
        for (int c = 0; c < M; c++) if (where[c] >= 0) h[c] = A[where[c]][M];
        // L(M) has rank M - 1 and lies in the vectors of sum 0.  Its generators having rank M - 1 mod 2 says that L(M) meets 2 Z^M only in 2 L(M), so rep + 2 L(M) holds every vector of L(M) with those parities.
        if (row != M - 1) { I.why = "the generators of L(M) lose rank mod 2"; return I; }
    }
    I.rep = mulmod(g, h, M); I.ok = true; return I;
}
static LL gcd128(LL a, LL b) { if (a < 0) a = -a; if (b < 0) b = -b; while (b) { LL t = a % b; a = b; b = t; } return a; }
struct GridKey { int M; vector<int> w; bool operator<(const GridKey &o) const { return M != o.M ? M < o.M : w < o.w; } };
static map<GridKey, pair<LL, LL>> GRID;   // (2 G, w.rep)
static const pair<LL, LL> *grid_of(int M, const vector<int> &w) {
    GridKey k{M, w}; auto it = GRID.find(k); if (it != GRID.end()) return &it->second;
    ModInfo &I = mod_info(M); if (!I.ok) return nullptr;
    LL G = 0; for (int s = 0; s < M; s++) { LL t = 0; for (int r = 0; r < M; r++) t += (LL)w[r] * I.g[((r - s) % M + M) % M]; G = gcd128(G, t); }
    LL c = 0; for (int r = 0; r < M; r++) c += (LL)w[r] * I.rep[r];
    return &(GRID[k] = {2 * G, c});
}

// ---- a task
struct Form { bool defined = false; int M = 0; LL st = 0, c0 = 0; vector<int> w; ll maxw = 0; bool given = false; };
static vector<Form> F; static vector<char> present; static vector<LL> value; static vector<int> rows;
struct Level { size_t entry; int G; int form = -1; bool sym = false; vector<LL> vals; size_t next = 0; };
static vector<Level> L; static size_t start_rows = 0;
static string err; static bool awaiting = false, finished_tree = false;
static ll c_nodes, c_closed, c_fix, c_split, c_certs, c_open, c_spill; static vector<string> spills; static string start_name;
static void fail(const string &s) { if (err.empty()) err = s; }
static void ensure_id(int id) { if (id >= (int)F.size()) { F.resize(id + 256); present.resize(id + 256, 0); value.resize(id + 256, 0); } }   // id <= MAX_ID: small_int
// a 128-bit integer in decimal: to_string((ll)v) for every v that fits in 64 bits (2026-11-04: node_name printed (ll)v, so v and v + 2^64 had one name)
static string str128(LL v) { ULL u = v < 0 ? (ULL)0 - (ULL)v : (ULL)v; string s; do { s += (char)('0' + (int)(u % 10)); u /= 10; } while (u); if (v < 0) s += '-'; reverse(s.begin(), s.end()); return s; }
static string node_name(int G) {
    vector<string> lines; for (int id : rows) { const Form &f = F[id]; string s = to_string(f.M) + " " + str128(value[id]); for (int x : f.w) s += " " + to_string(x); lines.push_back(s); }
    sort(lines.begin(), lines.end()); Sha S; string head = "n " + to_string(n_) + " m " + to_string(m_) + " G " + to_string(G) + "\n"; S.add(head.data(), head.size()); for (auto &l : lines) { S.add(l.data(), l.size()); S.add("\n", 1); } return S.hex().substr(0, 32);
}
struct Cert { int dd = 0, ss = 0; vector<LL> B; vector<pair<int, LL>> c; };
// a number that must lie in a small range: out of it the stream cannot be read further
static int small_int(LL lo, LL hi, const char *what) { LL v = read_int(); if (v < lo || v > hi) { printf("{\"ok\":false,\"why\":\"%s out of range\"}\n", what); fflush(stdout); exit(1); } return (int)v; }
static void read_cert(Cert &C) {
    C.dd = small_int(0, 64, "a scale"); C.ss = small_int(0, 64, "a scale"); C.B.resize(m_); for (auto &b : C.B) b = read_int(); int k = small_int(0, MAX_RATIO_ROWS, "a certificate's rows"); C.c.resize(k); for (auto &x : C.c) { x.first = small_int(0, MAX_ID, "a row id"); x.second = read_int(); }
}
// W(p) = sum_t B_t C(p, t) + 2^dd sum_q c_q w_q(p mod M_q), and K = 2^dd sum_q c_q v_q.  False if a number would pass 2^120, which would make the arithmetic below unsafe.
static const ULL BIG = (ULL)1 << 114;   // so that |W(p)| and T |w(p)| stay under 2^115 and a sum over p < 2048 stays under 2^127
static inline ULL mag(LL a) { return a < 0 ? (ULL)(-a) : (ULL)a; }
static bool safe_mul(ULL a, ULL b, ULL &o) { return !__builtin_mul_overflow(a, b, &o) && o < BIG; }
static vector<LL> Wx; static LL GM[128][128]; static bool GMon[128];
static bool weights(const Cert &C, LL &K) {
    memset(GMon, 0, sizeof GMon);   // scratch of this call alone (2026-11-04: an early return in the loop below left GMon[M] set, and every later call in the process then left modulus M's rows out of W)
    if (C.dd < 0 || C.dd > 64 || C.ss < 0 || C.ss > 64) { fail("a scale out of range"); return false; }
    Wx.assign(n_, 0);
    // the moments by Newton's differences.  Every partial value is at most this sum, which is usually far too high, the terms mostly cancelling: past BIG each addition is tested instead, and each W(p)
    ULL s = 0; bool plain = true; for (int t = 0; t < m_ && plain; t++) { ULL o; if (!safe_mul(mag(C.B[t]), (ULL)Cmax[t], o)) plain = false; else { s += o; if (s >= BIG) plain = false; } }
    { LL d[64]; if (m_ > 64) { fail("m too large"); return false; } for (int t = 0; t < m_; t++) d[t] = C.B[t];
      if (plain) { for (int p = 0; p < n_; p++) { Wx[p] = d[0]; for (int t = 0; t + 1 < m_; t++) d[t] += d[t + 1]; } }
      else for (int p = 0; p < n_; p++) { Wx[p] = d[0]; if (mag(d[0]) >= BIG) { fail("a moment value too large"); return false; } for (int t = 0; t + 1 < m_; t++) if (__builtin_add_overflow(d[t], d[t + 1], &d[t])) { fail("a moment value too large"); return false; } } }
    ULL s2 = 0, s3 = 0; K = 0; static vector<int> touched; touched.clear();
    for (auto &x : C.c) {
        int id = x.first; if (id < 0 || id >= (int)F.size() || !F[id].defined || !present[id]) { fail("a certificate weighs a row the node does not have"); return false; }
        const Form &f = F[id]; ULL o; if (f.M >= 128) { fail("a modulus too large"); return false; }
        if (!safe_mul(mag(x.second), (ULL)f.maxw, o)) { fail("a row multiplier too large"); return false; } s2 += o; if (s2 >= BIG) { fail("row multipliers too large"); return false; }
        if (!safe_mul(mag(x.second), mag(value[id]), o)) { fail("a row multiplier too large"); return false; } s3 += o; if (s3 >= BIG) { fail("row multipliers too large"); return false; }
        K += x.second * value[id];
        if (!GMon[f.M]) { GMon[f.M] = true; touched.push_back(f.M); for (int r = 0; r < f.M; r++) GM[f.M][r] = 0; }
        for (int r = 0; r < f.M; r++) GM[f.M][r] += x.second * f.w[r];
    }
    ULL o; if (!safe_mul(s2, (ULL)1 << C.dd, o) || !safe_mul(s3, (ULL)1 << C.dd, o)) { for (int M : touched) GMon[M] = false; fail("a certificate's numbers are too large"); return false; }
    K = K * ((LL)1 << C.dd);
    for (int M : touched) { GMon[M] = false; const LL *g = GM[M]; const LL D = (LL)1 << C.dd; for (int p = 0; p < n_; p++) Wx[p] += D * g[p % M]; }
    return true;
}
static LL floordiv(LL a, LL b) { LL q = a / b; if ((a % b != 0) && ((a < 0) != (b < 0))) q--; return q; }
// the greatest integer s * form can be under the node's rows, by this certificate
static bool bound(const Cert &C, const Form &f, int s, LL &out) {
    LL K; if (!weights(C, K)) return false;
    int T2 = C.dd + C.ss; if (T2 > 100) { fail("T too large"); return false; } LL T = (LL)1 << T2;
    ULL o; if (!safe_mul((ULL)f.maxw, (ULL)T, o)) { fail("T w too large"); return false; }
    ULL tot = 0; const LL Ts = s > 0 ? T : -T; const int M = f.M; const int *w = f.w.data();
    for (int p = 0; p < n_; p++) tot += mag(Ts * w[p % M] - Wx[p]);
    if (tot >= ((ULL)1 << 126)) { fail("a bound too large"); return false; }
    out = floordiv((LL)tot + K, T); c_certs++; return true;
}
static void close_current() {
    while (true) {
        Level &top = L.back(); while (rows.size() > top.entry) { present[rows.back()] = 0; rows.pop_back(); }
        L.pop_back(); c_closed++;
        if (L.empty()) { finished_tree = true; awaiting = false; return; }
        Level &par = L.back(); if (par.next < par.vals.size()) { awaiting = true; return; }
    }
}
static void add_row(int id, LL v) { if (present[id]) { if (value[id] != v) fail("a row pinned twice, to different values"); return; } present[id] = 1; value[id] = v; rows.push_back(id); }
static void reset_task() { for (int id : rows) present[id] = 0; rows.clear(); L.clear(); for (auto &f : F) f.defined = false; err.clear(); awaiting = false; finished_tree = false; c_nodes = c_closed = c_fix = c_split = c_certs = c_open = c_spill = 0; spills.clear(); start_name.clear(); }
static void read_w(vector<int> &w, int M) { w.resize(M); for (auto &x : w) x = small_int(-(1LL << 30), 1LL << 30, "a weight"); }
static void define(int id, int M, const vector<int> &w) { ensure_id(id); Form &f = F[id]; if (f.defined && (f.M != M || f.w != w)) { fail("a row id defined twice, differently"); return; } f.defined = true; f.M = M; f.w = w; f.maxw = 0; for (int x : w) f.maxw = max<ll>(f.maxw, llabs((ll)x)); }

int main() {
    { struct rlimit lim; lim.rlim_cur = lim.rlim_max = (rlim_t)1 << 31; setrlimit(RLIMIT_AS, &lim); }   // 2 GiB: a checker must never be able to take the machine down
    while (true) {
        int t = token();
        if (t == -1) return 0;
        if (t != 'T') { printf("{\"ok\":false,\"why\":\"a stream must begin each task with T\"}\n"); fflush(stdout); return 1; }
        reset_task(); int n = small_int(2, 2047, "n"), m = small_int(1, 64, "m");
        if (n < 2 * m) { printf("{\"ok\":false,\"why\":\"n and m out of range\"}\n"); fflush(stdout); return 1; }
        if (n != n_ || m != m_) { n_ = n; m_ = m; e_ = ((ll)n < (1LL << min(m, 40))) ? 1 : 0; MODS.clear(); GRID.clear(); Cbin.assign(n, vector<LL>(m, 0)); Cmax.assign(m, 0);
            for (int p = 0; p < n; p++) { Cbin[p][0] = 1; for (int k = 1; k < m; k++) Cbin[p][k] = p == 0 ? 0 : Cbin[p - 1][k] + Cbin[p - 1][k - 1]; } for (int k = 0; k < m; k++) Cmax[k] = Cbin[n - 1][k]; }
        int G = 0; bool head = true;
        while (true) {
            t = token();
            if (t == -1) { printf("{\"ok\":false,\"why\":\"the stream ended inside a task\"}\n"); fflush(stdout); return 1; }
            if (t == 'E') break;
            if (head && t != 'G' && t != 'P') { head = false; L.push_back(Level{0, G}); c_nodes = 1; start_name = node_name(G); start_rows = rows.size(); }
            bool dead = !err.empty() || !stream_error.empty();
            if (t == 'G') { G = small_int(0, 1, "G"); if (!head) fail("G after the start"); }
            else if (t == 'P') { int id = small_int(0, MAX_ID, "a row id"), M = small_int(1, MAX_M - 1, "a modulus"); LL v = read_int(); vector<int> w; read_w(w, M); if (!head) { fail("P after the start"); continue; } define(id, M, w); F[id].given = true; add_row(id, v); }
            else if (t == 'R') { int id = small_int(0, MAX_ID, "a row id"), M = small_int(1, MAX_M - 1, "a modulus"); LL st = read_int(), c0 = read_int(); vector<int> w; read_w(w, M); if (dead) continue;
                if (st <= 0) { fail("a step must be positive"); continue; }
                const pair<LL, LL> *g = grid_of(M, w); if (!g) { fail("a modulus not allowed: " + mod_info(M).why); continue; }
                if (g->first % st != 0) { fail("a form's step is not a divisor of its grid"); continue; }
                if ((g->second - c0) % st != 0) { fail("a form's offset is off its grid"); continue; }
                define(id, M, w); F[id].st = st; F[id].c0 = c0; F[id].given = false; }
            else if (t == 'B') {
                int id = small_int(0, MAX_ID, "a row id"), sym = small_int(0, 1, "sym"); LL k = read_int(); Cert U, D; read_cert(U); read_cert(D); if (dead) continue;
                if (awaiting || L.empty()) { fail("B where a child was expected"); continue; }
                ensure_id(id); const Form &f = F[id]; if (!f.defined || f.st <= 0) { fail("B on a form without a grid"); continue; }
                if (present[id]) { fail("B on a form the node has pinned"); continue; }
                LL hi, lo; if (!bound(U, f, 1, hi) || !bound(D, f, -1, lo)) continue; lo = -lo;
                Level &cur = L.back();
                if (sym) { if (!cur.G) { fail("a symmetric split where the node has no symmetry"); continue; } bool anti = true; for (int r = 0; r < f.M; r++) if (f.w[((n_ - 1 - r) % f.M + f.M) % f.M] != -f.w[r]) anti = false; if (!anti) { fail("a symmetric split on a form that is not anti-invariant"); continue; } }
                // counted, not listed: the bounds of a forged certificate can be as wide as it likes
                LL from = (sym && lo < 0) ? (LL)0 : lo; LL v0 = from + (((f.c0 - from) % f.st) + f.st) % f.st; LL count = hi >= v0 ? (hi - v0) / f.st + 1 : 0;
                if (count != k) { fail("the certificates give another number of values"); continue; }
                if (k > MAX_VALUES) { fail("too many values"); continue; }
                vector<LL> vs((size_t)k); for (size_t j = 0; j < (size_t)k; j++) vs[j] = v0 + (LL)j * f.st;
                if (vs.empty()) { close_current(); }
                else if (vs.size() == 1) { add_row(id, vs[0]); c_fix++; if (sym && vs[0] != 0) cur.G = 0; }
                else { c_split++; cur.form = id; cur.sym = sym != 0; cur.vals = vs; cur.next = 0; awaiting = true; }
            }
            else if (t == 'V') { LL v = read_int(); if (dead) continue;
                if (!awaiting) { fail("V where no child is due"); continue; }
                Level &par = L.back(); if (par.vals[par.next] != v) { fail("V: not the value due"); continue; }
                par.next++; int childG = (par.sym && v == 0) ? par.G : 0; size_t entry = rows.size(); int fid = par.form; L.push_back(Level{entry, childG}); add_row(fid, v); awaiting = false; c_nodes++; }
            else if (t == 'C') { Cert C; read_cert(C); if (dead) continue;
                if (awaiting || L.empty()) { fail("C where a child was expected"); continue; }
                LL K; if (!weights(C, K)) continue; ULL tot = 0; for (int p = 0; p < n_; p++) tot += mag(Wx[p]); c_certs++;
                if (tot >= ((ULL)1 << 126)) { fail("a closure too large"); continue; }
                if (mag(K) <= tot) { fail("a closing certificate does not close"); continue; }
                close_current(); }
            else if (t == 'S') { if (dead) continue; if (awaiting || L.empty()) { fail("S where a child was expected"); continue; } if (L.size() == 1 && rows.size() == start_rows) { fail("a task spilled its own start"); continue; } spills.push_back(node_name(L.back().G)); c_spill++; close_current(); }
            else if (t == 'O') { if (dead) continue; if (awaiting || L.empty()) { fail("O where a child was expected"); continue; } c_open++; close_current(); }
            else { printf("{\"ok\":false,\"why\":\"unknown token %d\"}\n", t); fflush(stdout); return 1; }
        }
        if (head) { L.push_back(Level{0, G}); c_nodes = 1; start_name = node_name(G); fail("a task without a step"); }
        if (err.empty() && !stream_error.empty()) err = stream_error;
        if (err.empty() && !finished_tree) err = "the tree did not close";
        printf("{\"ok\":%s,\"start\":\"%s\",\"nodes\":%lld,\"closed\":%lld,\"fixes\":%lld,\"splits\":%lld,\"certs\":%lld,\"open\":%lld,\"why\":\"%s\",\"spills\":[", err.empty() ? "true" : "false", start_name.c_str(), c_nodes, c_closed, c_fix, c_split, c_certs, c_open, err.c_str());
        for (size_t i = 0; i < spills.size(); i++) printf("%s\"%s\"", i ? "," : "", spills[i].c_str());
        printf("]}\n"); fflush(stdout);
        stream_error.clear();
    }
}
