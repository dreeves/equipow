/* tri.c -- 3-adic meet in the middle: exact count of +-1 sequences
 * a_0..a_{n-1} with sum_i a_i i^j = 0 for j < k (order >= k), k <= 7.
 *
 * Centred coordinate c_i = 2i-(n-1) (odd).  Order >= k  <=>  M_j := sum_i a_i c_i^j = 0
 * for j < k (the c^j, j < k, span the same polynomials as i^j).
 *
 * Levels (sets of positions):
 *   X1 = {c = 1 mod 3}, X2 = {c = 2 mod 3}, A = X1 u X2 (3 does not divide c),
 *   B  = {3 | c, 9 does not divide c}, with y = c/3,
 *   C  = {9 | c}, with z = c/9.
 * Lemma 1 (level 1).  For a solution, M_j(A) = -sum_{3|c} a c^j is a multiple of 3^j.
 * Lemma 2 (level 2).  Put T_j = -M_j(A)/3^j.  Then sum_{B u C} a y^j = T_j, and as
 *   y^j is a multiple of 3^j on C,  sum_B a y^j = T_j (mod 3^j).
 * Lemma 3 (level 3).  sum_C a z^j = (T_j - sum_B a y^j)/3^j exactly, j < k.
 * Conversely any (A, B, C) assignment meeting Lemma 3 for all j < k has M_j = 0 for
 * j < k, so the count below is exactly the number of solutions whose X1 and X2 carry
 * the given numbers of plus signs (the mod-3 profile, prof.py, lists the possible pairs).
 *
 * Stage 1: every X1 assignment with plus1 plus signs (list L) and every X2 assignment
 *   with plus2 plus signs (list R); pairs with M_j(L)+M_j(R) = 0 mod 3^j, 1 <= j < k, are
 *   found by hashing R on its residue vector (exact residues compared on every hit).
 * Stage 2: for each such pair, every B assignment with sum_B a y^j = T_j mod 3^j: B is
 *   split into a head (2^h assignments looped over) and a tail looked up by residue.
 * Stage 3: for each (A, B), the C assignments with the exact z-moments, looked up by
 *   the exact moment vector (compared component by component).
 * Every solution counted is rebuilt and rechecked in the original basis sum a_i i^j with
 * __int128 when --print is given.
 *
 * usage: tri n k plus1 plus2 [--print] [--passes P] [--onlypass p] [--head h] [--lfrac a b]
 *            [--prof file] [--filter] [--nocoset]
 *   --passes P   stage 1 in P passes (R keys mod P), to bound memory
 *   --onlypass p only pass p (0 <= p < P), so the passes can run as separate processes
 *   --lfrac a b  only the L assignments whose index is = a mod b (for timing samples)
 * Integer and memory bounds, each asserted by setup() or the pass loop before the table
 * it protects is built:
 *   every moment, partial moment and y- or z-moment used is at most mbound = n (n-1)^(k-1)
 *     in absolute value, and mbound < 2^62 is asserted, so int64 holds them and any sum
 *     or difference of two (at n = 128, k = 7, mbound = 128 * 127^6 < 2^49);
 *   the B tail has NT <= 28 positions, so its 2^NT entries take uint32 offsets;
 *   a pass's R table has at most UINT32_MAX entries (asserted after counting them);
 *   the stage-1 key (residue, coset class) is encoded exactly in a uint64;
 *   all tables together stay under MEMCAP bytes (xalloc keeps the running total). */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

typedef int64_t i64;
typedef __int128 i128;
/* TODO: error copy; says which assertion failed (source line and the condition) */
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "Claude: \"CHECK failed line %d: %s\"\n", __LINE__, #c); exit(2); } } while (0)
#ifndef MAXN                         /* compile-time limits; the quals build variants with larger ones */
#define MAXN 128
#endif
#ifndef MAXK
#define MAXK 7
#endif
/* MEMCAP: the most bytes all of tri's tables may take at once.  2 GiB is 3x what the
 * planned count needs (0.69 GB per process at n = 128 with 8 passes, measured), and
 * J processes at the cap take J x 2 GiB, half of this machine's 16 GiB for J = 4.
 * It refuses, before allocating, the configurations that would not fit several to the
 * machine, e.g. --passes 1 at n = 128 (a 2.3 GB R table). */
#ifndef MEMCAP
#define MEMCAP ((size_t)2 << 30)
#endif
static size_t membytes = 0;          /* bytes of tables allocated now */
static void *xalloc(size_t bytes) {
  CHECK(bytes <= (size_t)MEMCAP - membytes);
  membytes += bytes;
  void *p = calloc(1, bytes);
  CHECK(p);
  return p;
}
static void xfree(void *p, size_t bytes) { CHECK(bytes <= membytes); membytes -= bytes; free(p); }

static int n, k, K1;                 /* K1 = k-1 residue components j = 1..k-1 */
static i64 c[MAXN];
static i64 md[MAXK];                 /* md[j] = 3^j */
static i64 Wt[MAXK];                 /* mixed radix weights for the residue key */
static int X1[MAXN], X2[MAXN], Bp[MAXN], Cp[MAXN], N1, N2, NB, NC;
static int doprint = 0, passes = 1, head = 2, onlypass = -1;
static long long lnum = 0, lden = 1;

static inline i64 modp(i64 a, i64 m) { i64 r = a % m; return r < 0 ? r + m : r; }
static uint64_t mix64(uint64_t z) { z += 0x9E3779B97F4A7C15ULL; z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL; z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL; return z ^ (z >> 31); }
static uint64_t hashv(const i64 *v, int len) { uint64_t h = 0x1234567ULL; for (int j = 0; j < len; j++) h = mix64(h ^ (uint64_t)v[j]); return h; }

/* residue key of a vector of exact moments (components 1..k-1, mod 3^j) */
static inline uint64_t reskey(const i64 *M) {
  uint64_t key = 0;
  for (int j = 1; j < k; j++) key += (uint64_t)modp(M[j], md[j]) * (uint64_t)Wt[j];
  return key;
}
static inline uint64_t negreskey(const i64 *M) {
  uint64_t key = 0;
  for (int j = 1; j < k; j++) key += (uint64_t)modp(-M[j], md[j]) * (uint64_t)Wt[j];
  return key;
}

/* ---------- level-2 coset key (folds a level-2 necessary condition into stage 1) ----------
 * Let v(y) = (y^j mod 3^j)_{j=1..k-1} and Lam = span_Z{v(y) : y in B} + prod_j 3^j Z.  Any B
 * assignment has residue vector sum_B a v(y) = beta - 2 sum_{minus} v(y), beta = sum_B v(y);
 * so the residue target tau of Lemma 2 must satisfy tau - beta in Lam.  Write
 * m_j = M_j mod 9^j = s_j + 3^j a_j (0 <= s_j, a_j < 3^j) for L and m'_j = t_j + 3^j b_j for R.
 * Level 1 forces t_j = -s_j mod 3^j, so s_j + t_j = 3^j d_j with d_j = [s_j != 0], and
 * tau_j = -(a_j + b_j + d_j) mod 3^j.  Hence tau - beta in Lam  <=>
 *   canon(-a - d - beta) = canon(b),
 * canon = reduction modulo Lam by its Hermite normal form (a group homomorphism onto
 * Z^{k-1}/Lam).  With level 1 the condition is M(L) + M(R) in D*Lam, D = diag(3^j), which
 * is linear in the signs.  The key writes the class modulo D*Lam in base-3^j digits; the
 * digits carry (d_j is the carry), but the class map is additive.  It splits into one
 * function of L, canon(-a - d - beta), equal to one function of R, canon(b), which is what
 * lets it serve as a lookup key.  beta is in Lam, so subtracting it changes nothing.
 * L looks up R under (level-1 residue, canon class); equality of both parts is exactly
 * level 1 plus this condition, both necessary for a solution. */
static i64 lamH[MAXK][MAXK]; static int lamP[MAXK], nlam = 0; static i64 lamPiv[MAXK], ncos = 1;
static i64 betaB[MAXK];
static uint64_t KSCALE = 1;
static void lam_setup(void) {
  /* rows: v(y) for y in B, and 3^j e_j; Euclidean echelon with entries reduced mod 3^j */
  int R = NB + K1;
  size_t abytes = sizeof(i64) * MAXK * (R + 1);
  i64 (*A)[MAXK] = xalloc(abytes);
  for (int r = 0; r < R; r++) for (int j = 1; j < k; j++) A[r][j] = 0;
  for (int t = 0; t < NB; t++) for (int j = 1; j < k; j++) { i64 y = c[Bp[t]] / 3, p = 1; for (int e = 0; e < j; e++) p = (p * modp(y, md[j])) % md[j]; A[t][j] = p; }
  for (int j = 1; j < k; j++) A[NB + j - 1][j] = md[j];
  int used[MAXN + MAXK]; for (int r = 0; r < R; r++) used[r] = 0;
  for (int col = 1; col < k; col++) {
    for (;;) {
      int best = -1, cnt = 0;
      for (int r = 0; r < R; r++) if (!used[r] && A[r][col] != 0) { cnt++; if (best < 0 || llabs(A[r][col]) < llabs(A[best][col])) best = r; }
      if (cnt <= 1) break;
      for (int r = 0; r < R; r++) if (!used[r] && r != best && A[r][col] != 0) {
        i64 q = A[r][col] / A[best][col];
        for (int j = col; j < k; j++) A[r][j] = A[r][j] - q * A[best][j];
        for (int j = col + 1; j < k; j++) A[r][j] = modp(A[r][j], md[j]);
      }
    }
    int pr = -1;
    for (int r = 0; r < R; r++) if (!used[r] && A[r][col] != 0) pr = r;
    CHECK(pr >= 0);                            /* 3^col e_col keeps every column a pivot */
    used[pr] = 1;
    if (A[pr][col] < 0) for (int j = col; j < k; j++) A[pr][j] = -A[pr][j];
    for (int j = 1; j < k; j++) lamH[nlam][j] = A[pr][j];
    lamP[nlam] = col; lamPiv[nlam] = A[pr][col]; nlam++;
  }
  CHECK(nlam == K1);
  for (int i = 0; i < nlam; i++) { CHECK(lamPiv[i] >= 1 && md[lamP[i]] % lamPiv[i] == 0); ncos *= lamPiv[i]; }
  for (int j = 1; j < k; j++) { i64 sacc = 0; for (int t = 0; t < NB; t++) { i64 y = c[Bp[t]] / 3, p = 1; for (int e = 0; e < j; e++) p = (p * modp(y, md[j])) % md[j]; sacc = (sacc + p) % md[j]; } betaB[j] = sacc; }
  /* key = reskey + KSCALE * class, with reskey < KSCALE = prod_j 3^j and class < ncos, is
   * exact (no two (residue, class) pairs share a key) iff KSCALE * ncos <= 2^64 */
  i128 span = ncos;
  for (int j = 1; j < k; j++) { span *= md[j]; CHECK(span <= ((i128)1 << 64)); KSCALE *= (uint64_t)md[j]; }
  xfree(A, abytes);
}
/* canonical class of x (components 1..k-1) modulo Lam, as an integer in [0, ncos) */
static uint64_t canon(i64 *x) {
  for (int j = 1; j < k; j++) x[j] = modp(x[j], md[j]);
  for (int i = 0; i < nlam; i++) {
    int col = lamP[i];
    i64 q = x[col] / lamPiv[i];                /* x[col] >= 0 here */
    for (int j = col; j < k; j++) x[j] = modp(x[j] - q * lamH[i][j], md[j]);
    CHECK(x[col] >= 0 && x[col] < lamPiv[i]);
  }
  uint64_t id = 0, w = 1;
  for (int i = 0; i < nlam; i++) { id += (uint64_t)x[lamP[i]] * w; w *= (uint64_t)lamPiv[i]; }
  return id;
}
static int usecoset = 1;
static inline uint64_t rkey_full(const i64 *M) {          /* R side: (t, canon(b)) */
  uint64_t key = reskey(M);
  if (!usecoset) return key;
  i64 b[MAXK];
  for (int j = 1; j < k; j++) b[j] = modp(M[j], md[j] * md[j]) / md[j];
  return key + KSCALE * canon(b);
}
static inline uint64_t lkey_full(const i64 *M) {          /* L side: (-s, canon(-a - d - beta)) */
  uint64_t key = negreskey(M);
  if (!usecoset) return key;
  i64 x[MAXK];
  for (int j = 1; j < k; j++) {
    i64 m = modp(M[j], md[j] * md[j]), sj = m % md[j], aj = m / md[j];
    x[j] = -aj - (sj != 0) - betaB[j];
  }
  return key + KSCALE * canon(x);
}

/* ---------- side enumeration (X1 or X2 with a fixed number of plus signs) ---------- */
typedef struct { int N, m, maj; const int *pos; i64 base[MAXK]; i64 delta[64][MAXK]; } Side;
static void side_init(Side *s, const int *pos, int N, int plus) {
  CHECK(N <= 64 && plus >= 0 && plus <= N);
  s->N = N; s->pos = pos;
  if (plus <= N - plus) { s->maj = -1; s->m = plus; } else { s->maj = 1; s->m = N - plus; }
  for (int j = 0; j < k; j++) s->base[j] = 0;
  for (int t = 0; t < N; t++) {
    i64 p = 1;
    for (int j = 0; j < k; j++) { s->base[j] += s->maj * p; s->delta[t][j] = -2 * s->maj * p; p *= c[pos[t]]; }
  }
}
/* M of the assignment whose minority set is mask */
static inline void side_moments(const Side *s, uint64_t mask, i64 *M) {
  for (int j = 0; j < k; j++) M[j] = s->base[j];
  while (mask) { int t = __builtin_ctzll(mask); mask &= mask - 1; for (int j = 0; j < k; j++) M[j] += s->delta[t][j]; }
}

typedef void (*leaf_fn)(uint64_t mask, const i64 *M);
static const Side *gs; static leaf_fn gleaf; static i64 cur[MAXK];
static void rec(int t, int left, uint64_t mask) {
  if (left == 0) { gleaf(mask, cur); return; }
  if (gs->N - t < left) return;
  for (int u = t; u <= gs->N - left; u++) {
    for (int j = 0; j < k; j++) cur[j] += gs->delta[u][j];
    rec(u + 1, left - 1, mask | (1ULL << u));
    for (int j = 0; j < k; j++) cur[j] -= gs->delta[u][j];
  }
}
static void side_enum(const Side *s, leaf_fn f) {
  gs = s; gleaf = f;
  for (int j = 0; j < k; j++) cur[j] = s->base[j];
  rec(0, s->m, 0);
}

/* ---------- R table for one pass (CSR by hash of the residue key) ---------- */
static Side SL, SR;
static int pass;
static uint64_t nbuck; static uint32_t *roff; static uint64_t *rkey, *rmask; static long long rcount;
static void r_count(uint64_t mask, const i64 *M) {
  (void)mask;
  uint64_t key = rkey_full(M);
  if ((int)(key % passes) != pass) return;
  roff[(mix64(key) & (nbuck - 1)) + 1]++;
  rcount++;
}
static void r_fill(uint64_t mask, const i64 *M) {
  uint64_t key = rkey_full(M);
  if ((int)(key % passes) != pass) return;
  uint64_t b = mix64(key) & (nbuck - 1);
  uint32_t at = roff[b]++;
  rkey[at] = key; rmask[at] = mask;
}

/* ---------- B tables ---------- */
static int NH, NT, NT1, NT2;                     /* head, tail, tail halves */
static i64 *hy, *t1y, *t2y;                      /* exact y-moments [cfg*k + j] */
static uint64_t tbuck; static uint32_t *toff, *tcfg;
static i64 ymom(int pos, int j) { i64 y = c[pos] / 3, p = 1; for (int e = 0; e < j; e++) p *= y; return p; }
static i64 *cfg_moments(const int *pos, int N, i64 (*f)(int, int)) {
  i64 *T = xalloc(sizeof(i64) * ((size_t)1 << N) * k);
  for (uint64_t m = 0; m < (1ULL << N); m++)
    for (int j = 0; j < k; j++) {
      i64 s = 0;
      for (int t = 0; t < N; t++) s += ((m >> t) & 1 ? 1 : -1) * f(pos[t], j);
      T[m * k + j] = s;
    }
  return T;
}
static inline void tail_moments(uint32_t cfg, i64 *M) {
  uint32_t a = cfg & ((1u << NT1) - 1), b = cfg >> NT1;
  for (int j = 0; j < k; j++) M[j] = t1y[(size_t)a * k + j] + t2y[(size_t)b * k + j];
}

/* ---------- C table ---------- */
static i64 zmom(int pos, int j) { i64 z = c[pos] / 9, p = 1; for (int e = 0; e < j; e++) p *= z; return p; }
static i64 *cz; static uint64_t cbuck; static uint32_t *coff, *ccfg;

/* (F) profile capacity filter, --prof file (repeatable), --filter to prune.
 * For a modulus m and an allowed profile list (prof.py), the b part (B u C) of a
 * solution adds to class r mod m exactly S_r - A_r, where A_r is the A part's class
 * sum; a sum of nb_r terms +-1 can do that only if |S_r - A_r| <= nb_r and
 * S_r - A_r = nb_r (mod 2).  An A pair with no such S in some list has no completion. */
#define MAXFM 4
static int nfm = 0, fm[MAXFM], fA[MAXFM], *fS[MAXFM], fnb[MAXFM][64], dofilter = 0;
static long long fpass[MAXFM], fpassall = 0;
static void read_fprof(const char *path) {
  CHECK(nfm < MAXFM);
  FILE *f = fopen(path, "r"); CHECK(f);
  int m, A; CHECK(fscanf(f, "%d %d", &m, &A) == 2); CHECK(m >= 2 && m <= 64 && A >= 0);
  int q = nfm++; fm[q] = m; fA[q] = A; fS[q] = xalloc(sizeof(int) * ((size_t)A * m + 1));
  for (int a = 0; a < A * m; a++) CHECK(fscanf(f, "%d", &fS[q][a]) == 1);
  fclose(f);
}
static void filter_setup(void) {
  for (int q = 0; q < nfm; q++) {
    for (int r = 0; r < fm[q]; r++) fnb[q][r] = 0;
    for (int t = 0; t < NB; t++) fnb[q][Bp[t] % fm[q]]++;
    for (int t = 0; t < NC; t++) fnb[q][Cp[t] % fm[q]]++;
  }
}
static int filter_ok(uint64_t lmask, uint64_t rmask_) {
  int a[MAXN]; /* only the A positions are read */
  for (int t = 0; t < N1; t++) a[X1[t]] = ((lmask >> t) & 1) ? -SL.maj : SL.maj;
  for (int t = 0; t < N2; t++) a[X2[t]] = ((rmask_ >> t) & 1) ? -SR.maj : SR.maj;
  int all = 1;
  for (int q = 0; q < nfm; q++) {
    int m = fm[q], As[64];
    for (int r = 0; r < m; r++) As[r] = 0;
    for (int t = 0; t < N1; t++) As[X1[t] % m] += a[X1[t]];
    for (int t = 0; t < N2; t++) As[X2[t] % m] += a[X2[t]];
    int any = 0;
    for (int p = 0; p < fA[q] && !any; p++) {
      int ok = 1;
      for (int r = 0; r < m && ok; r++) {
        int d = fS[q][p * m + r] - As[r];
        ok = (d <= fnb[q][r] && d >= -fnb[q][r] && ((d - fnb[q][r]) % 2 == 0));
      }
      any = ok;
    }
    if (any) fpass[q]++;
    all &= any;
  }
  if (all) fpassall++;
  return all;
}

/* ---------- stage 2/3 per A pair ---------- */
static long long npairs = 0, nbcand = 0, nsols = 0, lcount = 0;
static void rebuild_check(uint64_t lmask, uint64_t rmask_, uint32_t hcfg, uint32_t tcfg_, uint32_t ccfg_) {
  int a[MAXN];
  for (int i = 0; i < n; i++) a[i] = 0;
  for (int t = 0; t < N1; t++) a[X1[t]] = ((lmask >> t) & 1) ? -SL.maj : SL.maj;
  for (int t = 0; t < N2; t++) a[X2[t]] = ((rmask_ >> t) & 1) ? -SR.maj : SR.maj;
  uint64_t bcfg = (uint64_t)hcfg | ((uint64_t)tcfg_ << NH);
  for (int t = 0; t < NB; t++) a[Bp[t]] = ((bcfg >> t) & 1) ? 1 : -1;
  for (int t = 0; t < NC; t++) a[Cp[t]] = ((ccfg_ >> t) & 1) ? 1 : -1;
  char buf[MAXN + 1];
  for (int i = 0; i < n; i++) { CHECK(a[i] == 1 || a[i] == -1); buf[i] = a[i] > 0 ? '+' : '-'; }
  buf[n] = 0;
  for (int j = 0; j < k; j++) {
    i128 s = 0;
    for (int i = 0; i < n; i++) { i128 p = 1; for (int e = 0; e < j; e++) p *= i; s += a[i] * p; }
    CHECK(s == 0);
  }
  printf("%s\n", buf);
}

static void process_pair(uint64_t lmask, const i64 *ML, uint64_t rmask_) {
  i64 MR[MAXK], T[MAXK];
  side_moments(&SR, rmask_, MR);
  for (int j = 0; j < k; j++) {
    i64 MA = ML[j] + MR[j];
    CHECK(MA % md[j] == 0);
    T[j] = -MA / md[j];
  }
  npairs++;
  if (nfm > 0 && !filter_ok(lmask, rmask_) && dofilter) return;
  for (uint32_t h = 0; h < (1u << NH); h++) {
    i64 need[MAXK];                       /* tail residue target, as a moment vector */
    for (int j = 0; j < k; j++) need[j] = T[j] - hy[(size_t)h * k + j];
    uint64_t key = reskey(need);
    uint64_t b = mix64(key) & (tbuck - 1);
    for (uint32_t e = toff[b]; e < toff[b + 1]; e++) {
      i64 MT[MAXK];
      tail_moments(tcfg[e], MT);
      int ok = 1;
      for (int j = 1; j < k; j++) ok &= modp(need[j] - MT[j], md[j]) == 0;
      if (!ok) continue;
      nbcand++;
      i64 V[MAXK];
      for (int j = 0; j < k; j++) {
        i64 U = need[j] - MT[j];
        CHECK(U % md[j] == 0);
        V[j] = U / md[j];
      }
      uint64_t cb = hashv(V, k) & (cbuck - 1);
      for (uint32_t f = coff[cb]; f < coff[cb + 1]; f++) {
        const i64 *Z = cz + (size_t)ccfg[f] * k;
        int eq = 1;
        for (int j = 0; j < k; j++) eq &= Z[j] == V[j];
        if (!eq) continue;
        nsols++;
        if (doprint) rebuild_check(lmask, rmask_, h, tcfg[e], ccfg[f]);
      }
    }
  }
}
static void l_leaf(uint64_t mask, const i64 *M) {
  long long id = lcount++;
  if (id % lden != lnum) return;
  uint64_t need = lkey_full(M);
  if ((int)(need % passes) != pass) return;
  uint64_t b = mix64(need) & (nbuck - 1);
  for (uint32_t e = roff[b]; e < roff[b + 1]; e++) {
    if (rkey[e] != need) continue;
    process_pair(mask, M, rmask[e]);
  }
}

/* ---------- setup: classes, bounds, and every table that does not depend on the pass ----------
 * Needs n, k and the options (head, usecoset, --prof lists) already set; tri's main and
 * harness.c both build their tables with it. */
static void setup(int plus1, int plus2) {
  CHECK(n % 2 == 0 && n >= 2 && n <= MAXN && k >= 1 && k <= MAXK);
  i128 mbound = n;                                 /* n (n-1)^(k-1), see the header */
  for (int j = 1; j < k; j++) mbound *= n - 1;
  CHECK(mbound < ((i128)1 << 62));
  K1 = k - 1;
  md[0] = 1; for (int j = 1; j < k; j++) md[j] = md[j - 1] * 3;
  Wt[1] = 1; for (int j = 2; j < k; j++) Wt[j] = Wt[j - 1] * md[j - 1];
  for (int i = 0; i < n; i++) {
    c[i] = 2 * i - (n - 1);
    i64 r = modp(c[i], 3);
    if (r == 1) X1[N1++] = i;
    else if (r == 2) X2[N2++] = i;
    else if (modp(c[i], 9) != 0) Bp[NB++] = i;
    else Cp[NC++] = i;
  }
  CHECK(N1 <= 64 && N2 <= 64 && NC <= 24);
  NH = head < NB ? head : NB; NT = NB - NH; NT1 = NT / 2; NT2 = NT - NT1;
  CHECK(NT <= 28);                                 /* tail table: 4 bytes per entry, 2^NT entries */
  uint64_t ntail = 1ULL << NT;
  CHECK(ntail <= UINT32_MAX);                      /* toff holds uint32 offsets into it */
  filter_setup();
  lam_setup();
  side_init(&SL, X1, N1, plus1);
  side_init(&SR, X2, N2, plus2);
  /* B head and tail tables (y-moments), tail CSR keyed by residue */
  hy = cfg_moments(Bp, NH, ymom);
  t1y = cfg_moments(Bp + NH, NT1, ymom);
  t2y = cfg_moments(Bp + NH + NT1, NT2, ymom);
  tbuck = 1; while (tbuck * 4 < ntail) tbuck <<= 1;          /* about 4 tail entries per bucket */
  toff = xalloc(sizeof(uint32_t) * (tbuck + 2)); tcfg = xalloc(sizeof(uint32_t) * (ntail + 1));
  for (uint64_t cfg = 0; cfg < ntail; cfg++) { i64 M[MAXK]; tail_moments((uint32_t)cfg, M); toff[(mix64(reskey(M)) & (tbuck - 1)) + 1]++; }
  for (uint64_t b = 0; b < tbuck; b++) toff[b + 1] += toff[b];
  for (uint64_t cfg = 0; cfg < ntail; cfg++) { i64 M[MAXK]; tail_moments((uint32_t)cfg, M); uint64_t b = mix64(reskey(M)) & (tbuck - 1); tcfg[toff[b]++] = (uint32_t)cfg; }
  for (uint64_t b = tbuck; b > 0; b--) toff[b] = toff[b - 1];
  toff[0] = 0;
  /* C table keyed by exact z-moments */
  cz = cfg_moments(Cp, NC, zmom);
  uint64_t ncfg = 1ULL << NC;
  cbuck = 1; while (cbuck < ncfg) cbuck <<= 1;
  coff = xalloc(sizeof(uint32_t) * (cbuck + 2)); ccfg = xalloc(sizeof(uint32_t) * (ncfg + 1));
  for (uint64_t cfg = 0; cfg < ncfg; cfg++) coff[(hashv(cz + cfg * k, k) & (cbuck - 1)) + 1]++;
  for (uint64_t b = 0; b < cbuck; b++) coff[b + 1] += coff[b];
  for (uint64_t cfg = 0; cfg < ncfg; cfg++) { uint64_t b = hashv(cz + cfg * k, k) & (cbuck - 1); ccfg[coff[b]++] = (uint32_t)cfg; }
  for (uint64_t b = cbuck; b > 0; b--) coff[b] = coff[b - 1];
  coff[0] = 0;
}

int main(int argc, char **argv) {
  /* TODO: usage line; says the program's arguments */
  if (argc < 5) { fprintf(stderr, "Claude: \"usage: tri n k plus1 plus2 [--print] [--passes P] [--onlypass p] [--head h] [--lfrac a b] [--prof file] [--filter] [--nocoset]\"\n"); return 1; }
  n = atoi(argv[1]); k = atoi(argv[2]);
  int plus1 = atoi(argv[3]), plus2 = atoi(argv[4]);
  for (int a = 5; a < argc; a++) {
    if (!strcmp(argv[a], "--print")) doprint = 1;
    else if (!strcmp(argv[a], "--passes")) { CHECK(a + 1 < argc); passes = atoi(argv[++a]); CHECK(passes >= 1); }
    else if (!strcmp(argv[a], "--head")) { CHECK(a + 1 < argc); head = atoi(argv[++a]); CHECK(head >= 0 && head <= 16); }
    else if (!strcmp(argv[a], "--prof")) { CHECK(a + 1 < argc); read_fprof(argv[++a]); }
    else if (!strcmp(argv[a], "--filter")) dofilter = 1;
    else if (!strcmp(argv[a], "--nocoset")) usecoset = 0;
    else if (!strcmp(argv[a], "--onlypass")) { CHECK(a + 1 < argc); onlypass = atoi(argv[++a]); CHECK(onlypass >= 0); }
    else if (!strcmp(argv[a], "--lfrac")) { CHECK(a + 2 < argc); lnum = atoll(argv[a + 1]); lden = atoll(argv[a + 2]); a += 2; CHECK(lden >= 1 && lnum >= 0 && lnum < lden); }
    else CHECK(0 && "unknown option");
  }
  CHECK(onlypass < passes);
  setup(plus1, plus2);

  struct timespec t0, t1;
  clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t0);
  long long rtotal = 0;
  for (pass = 0; pass < passes; pass++) {
    if (onlypass >= 0 && pass != onlypass) continue;
    /* count, then fill, the R entries of this pass */
    rcount = 0;
    long long expect = 1; { /* binomial C(N2, m) */ i128 b = 1; for (int t = 0; t < SR.m; t++) b = b * (N2 - t) / (t + 1); expect = (long long)b; }
    nbuck = 1; while (nbuck * passes * 2 < (uint64_t)expect + 1) nbuck <<= 1;   /* about 2 R entries per bucket */
    size_t obytes = sizeof(uint32_t) * (nbuck + 2);
    roff = xalloc(obytes);
    side_enum(&SR, r_count);
    CHECK(rcount <= UINT32_MAX);                   /* roff holds uint32 offsets into the R table */
    for (uint64_t b = 0; b < nbuck; b++) roff[b + 1] += roff[b];
    size_t rbytes = sizeof(uint64_t) * (rcount + 1);
    rkey = xalloc(rbytes); rmask = xalloc(rbytes); /* no setup check bounds the R table; MEMCAP does */
    side_enum(&SR, r_fill);
    for (uint64_t b = nbuck; b > 0; b--) roff[b] = roff[b - 1];
    roff[0] = 0;
    rtotal += rcount;
    lcount = 0;
    side_enum(&SL, l_leaf);
    xfree(roff, obytes); xfree(rkey, rbytes); xfree(rmask, rbytes);
  }
  clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t1);
  double cpu = (t1.tv_sec - t0.tv_sec) + 1e-9 * (t1.tv_nsec - t0.tv_nsec);
  fprintf(stderr, "n=%d k=%d plus1=%d plus2=%d N1=%d N2=%d NB=%d NC=%d head=%d passes=%d onlypass=%d lfrac=%lld/%lld "
          "cosets=%lld L=%lld R=%lld pairs=%lld bcand=%lld sols=%lld cpu=%.3f filter=%d fpass0=%lld fpass1=%lld fpassall=%lld\n",
          n, k, plus1, plus2, N1, N2, NB, NC, NH, passes, onlypass, lnum, lden, usecoset ? (long long)ncos : 1LL, lcount, rtotal, npairs, nbcand, nsols, cpu, dofilter, nfm > 0 ? fpass[0] : 0, nfm > 1 ? fpass[1] : 0, fpassall);
  return 0;
}
