/* bdfs.c -- residue-budgeted pair DFS: exhaustive count of +-1 sequences
 * a_0..a_{n-1} with sum_i a_i i^j = 0 for j < k ("order >= k").
 *
 * Coordinates.  Pair p = 0..P-1 (P = n/2) holds positions R = P+p and
 * L = P-1-p, whose centred coordinates 2i-(n-1) are +x_p and -x_p, x_p = 2p+1.
 * u_p = (aR+aL)/2 and v_p = (aR-aL)/2; exactly one is nonzero and it is +-1.
 * Since the centred powers (2i-n+1)^j, j < k, span the same space as i^j,
 *   order >= k  <=>  S_j := sum_p x_p^j * (j even ? u_p : v_p) = 0 for j < k.
 *
 * Search.  Pairs from the outermost (p = P-1) inwards, four choices each
 * (u=+1, u=-1, v=+1, v=-1).  Every solution is exactly one root-to-leaf path.
 * A node is cut only by a test that every extension to a solution passes:
 *  (B) moment bounds.  With r pairs left, the rest of any combination
 *      sum_s c_s S_s over one parity of s is sum_{p<r} w_p q(x_p) with
 *      w_p in {-1,0,1}, so |its current value| <= sum_{p<r} |q(x_p)|.  Used
 *      for each monomial S_j and for the scaled Chebyshev combinations
 *      X^t T_t(x/X), X = 2r-1, t < k (as in ../../stan/unique-check/pdfs.c).
 *  (R) residue budgets.  For each modulus m given, a list A_m of profiles
 *      (residue-class sums, see prof.py) contains the profile of every
 *      solution.  A profile fixes, for each class r mod m, the number of minus
 *      signs K_r = (n_r - S_r)/2.  A bitset holds the profiles still
 *      consistent with the path: K_r >= minus signs placed so far in class r
 *      and n_r - K_r >= plus signs placed so far in class r, for every r.  These
 *      are exactly the profiles the finished sequence can still have, so the
 *      node is cut when the bitset is empty.
 * Leaves: all S_j are 0 (cap 0 at r = 0), and the sequence is rebuilt and
 * rechecked in the original basis sum_i a_i i^j with exact __int128.
 *
 * Symmetry option --flip u|v (the driver checks it is valid): keep only paths
 * whose first nonzero u (resp. v) is +1, and weight each solution 2, or 1 when
 * all its u (resp. v) are 0.
 *
 * Split/sample at depth D (D pairs placed): nodes reaching depth D are numbered
 * 0,1,2,... in DFS order; --part W w explores below those with index = w mod W;
 * --sample D rate seed explores below each with probability 1/rate (a fixed
 * hash of index and seed), and reports the sampled subtree sizes so the driver
 * can form the Horvitz-Thompson estimate of the whole tree.
 *
 * usage: bdfs n k full|sym|anti [--prof file]... [--flip u|v] [--print]
 *             [--part D W w] [--sample D rate seed]
 * All arithmetic exact (int64 sums, __int128 combinations, bounds asserted). */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <math.h>

typedef __int128 i128;
typedef int64_t i64;

#define MAXP 64
#define MAXK 9
#define MAXMOD 8
#define MAXCLS 64
/* TODO: error copy; says which assertion failed (source line and the condition) */
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "Claude: \"CHECK failed line %d: %s\"\n", __LINE__, #c); exit(2); } } while (0)

static int n, k, P, mode, flip = 0, doprint = 0;
static i64 pw[MAXP][MAXK];
static i64 capM[MAXP + 1][MAXK];
static i64 cheb[MAXK][MAXK];
static i128 qc[MAXP + 1][MAXK][MAXK];
static i128 capQ[MAXP + 1][MAXK];
static i64 S[MAXK];
static int U[MAXP], V[MAXP];

static int nmod = 0, modm[MAXMOD], nprof[MAXMOD], nw[MAXMOD], csize[MAXMOD][MAXCLS];
static uint64_t *okMinus[MAXMOD], *okPlus[MAXMOD];   /* [(r*(MAXCLSZ+1)+c)*nw] */
#define MAXCLSZ 128
static int cntMinus[MAXMOD][MAXCLS], cntPlus[MAXMOD][MAXCLS];
static uint64_t *bits[MAXMOD];                        /* [depth*nw] */

static long long nodes = 0, sols = 0, weighted = 0, nodesAtDepth[MAXP + 2];
static int splitD = -1, partW = 1, partw = 0;
static long long sampleRate = 0, sampleSeed = 0;
static long long splitctr = 0, explored = 0;
static double subSum = 0, subSumSq = 0;
static long long knuthProbes = 0, knuthSeed = 0;
static long long subSolsW = 0;

static i128 abs128(i128 a) { return a < 0 ? -a : a; }

/* (J) joint quotas, --joint, only when every modulus has exactly one profile.
 * For two coprime moduli m1, m2 the unplaced positions form an m1 x m2 table
 * of cells (i mod m1, i mod m2) with capacity cap = unplaced positions in the
 * cell.  The profile pair fixes how many more plus signs each row r (class mod
 * m1) and each column c (class mod m2) still needs: P1[r], P2[c].  The rest of
 * the sequence exists only if some integer table 0 <= x[r][c] <= cap[r][c] has
 * these row and column sums.  By max-flow/min-cut (source->row cap P1[r],
 * row->column cap cap[r][c], column->sink cap P2[c]) that holds iff for every
 * set C of columns:
 *   sum_r min(P1[r], sum_{c not in C} cap[r][c]) + sum_{c in C} P2[c] >= sum_r P1[r],
 * and sum_r P1[r] = sum_c P2[c].  The node is cut when any pair fails. */
static int joint = 0;
static int quotaMinus[MAXMOD][MAXCLS];          /* K_r of the active profile */
static int *profK[MAXMOD];                      /* [a*MAXCLS + r]: K_r of profile a */
static const char *tuplesPath = 0;
static int npairs = 0, pairI[MAXMOD * MAXMOD], pairJ[MAXMOD * MAXMOD];
static int jcap[MAXMOD * MAXMOD][MAXCLS][MAXCLS];
static int gcdi(int a, int b) { while (b) { int t = a % b; a = b; b = t; } return a; }
static void joint_setup(void) {
  for (int mi = 0; mi < nmod; mi++) CHECK(nprof[mi] == 1 || tuplesPath);
  for (int a = 0; a < nmod; a++)
    for (int b = 0; b < nmod; b++)
      if (a != b && gcdi(modm[a], modm[b]) == 1 && modm[a] >= modm[b]) {   /* columns = smaller modulus */
        int q = npairs++;
        pairI[q] = a; pairJ[q] = b;
        CHECK(modm[b] <= 12);
        for (int i = 0; i < n; i++) jcap[q][i % modm[a]][i % modm[b]]++;
      }
}
static inline void joint_take(int i, int d) {   /* d = -1 when position i is placed, +1 when unplaced */
  for (int q = 0; q < npairs; q++) jcap[q][i % modm[pairI[q]]][i % modm[pairJ[q]]] += d;
}
static int joint_ok(void) {
  for (int q = 0; q < npairs; q++) {
    int a = pairI[q], b = pairJ[q], m1 = modm[a], m2 = modm[b];
    int P1[MAXCLS], P2[MAXCLS], rowc[MAXCLS], tot1 = 0, tot2 = 0;
    for (int r = 0; r < m1; r++) {
      P1[r] = (csize[a][r] - quotaMinus[a][r]) - cntPlus[a][r];
      rowc[r] = 0;
      for (int c = 0; c < m2; c++) rowc[r] += jcap[q][r][c];
      if (P1[r] < 0 || P1[r] > rowc[r]) return 0;
      tot1 += P1[r];
    }
    for (int c = 0; c < m2; c++) {
      P2[c] = (csize[b][c] - quotaMinus[b][c]) - cntPlus[b][c];
      int colc = 0;
      for (int r = 0; r < m1; r++) colc += jcap[q][r][c];
      if (P2[c] < 0 || P2[c] > colc) return 0;
      tot2 += P2[c];
    }
    if (tot1 != tot2) return 0;
    /* Gray code over column sets C; rowc[r] = sum over columns not in C */
    int inC = 0, sumP2 = 0;
    for (unsigned g = 1; g < (1u << m2); g++) {
      int c = __builtin_ctz(g);                   /* column toggled */
      int add = !((inC >> c) & 1);
      inC ^= 1 << c;
      for (int r = 0; r < m1; r++) rowc[r] += add ? -jcap[q][r][c] : jcap[q][r][c];
      sumP2 += add ? P2[c] : -P2[c];
      int lhs = sumP2;
      for (int r = 0; r < m1; r++) lhs += P1[r] < rowc[r] ? P1[r] : rowc[r];
      if (lhs < tot1) return 0;
    }
  }
  return 1;
}

static int bounds_ok(int r) {
  for (int j = 0; j < k; j++) {
    i64 a = S[j] < 0 ? -S[j] : S[j];
    if (a > capM[r][j]) return 0;
  }
  for (int t = 0; t < k; t++) {
    i128 q = 0;
    for (int s = t & 1; s <= t; s += 2) q += qc[r][t][s] * (i128)S[s];
    if (abs128(q) > capQ[r][t]) return 0;
  }
  return 1;
}

static void emit(int nu, int nv) {
  char buf[2 * MAXP + 2];
  for (int p = 0; p < P; p++) {
    int aR = U[p] + V[p], aL = U[p] - V[p];
    CHECK((aR == 1 || aR == -1) && (aL == 1 || aL == -1));
    buf[P + p] = aR > 0 ? '+' : '-';
    buf[P - 1 - p] = aL > 0 ? '+' : '-';
  }
  buf[n] = 0;
  for (int j = 0; j < k; j++) {
    i128 m = 0;
    for (int i = 0; i < n; i++) {
      i128 t = 1;
      for (int e = 0; e < j; e++) t *= i;
      m += (buf[i] == '+') ? t : -t;
    }
    CHECK(m == 0);
  }
  if (doprint) printf("%s\n", buf);
  sols++;
  int w = 1;
  if (flip == 1 && nu > 0) w = 2;
  if (flip == 2 && nv > 0) w = 2;
  weighted += w;
}

/* place sign s at position i: update class counts and AND the masks into dst */
static inline void place(int mi, int i, int s, uint64_t *dst) {
  int m = modm[mi], r = i % m, W = nw[mi];
  const uint64_t *mask;
  if (s < 0) { int c = ++cntMinus[mi][r]; mask = okMinus[mi] + ((size_t)r * (MAXCLSZ + 1) + c) * W; }
  else       { int c = ++cntPlus[mi][r];  mask = okPlus[mi]  + ((size_t)r * (MAXCLSZ + 1) + c) * W; }
  for (int w = 0; w < W; w++) dst[w] &= mask[w];
}
static inline void unplace(int mi, int i, int s) {
  int r = i % modm[mi];
  if (s < 0) cntMinus[mi][r]--; else cntPlus[mi][r]--;
}

static void dfs(int r, int nu, int nv);

static void dfs_children(int r, int nu, int nv) {
  int p = r - 1, d = P - r;
  for (int typ = 0; typ < 2; typ++) {          /* 0: u, 1: v */
    if (typ == 0 && mode == 2) continue;
    if (typ == 1 && mode == 1) continue;
    for (int sg = 1; sg >= -1; sg -= 2) {
      if (flip == 1 && typ == 0 && nu == 0 && sg < 0) continue;
      if (flip == 2 && typ == 1 && nv == 0 && sg < 0) continue;
      int aR = typ == 0 ? sg : sg, aL = typ == 0 ? sg : -sg;
      int alive = 1;
      for (int mi = 0; mi < nmod; mi++) {
        int W = nw[mi];
        uint64_t *src = bits[mi] + (size_t)d * W, *dst = bits[mi] + (size_t)(d + 1) * W;
        memcpy(dst, src, sizeof(uint64_t) * W);
        place(mi, P + p, aR, dst);
        place(mi, P - 1 - p, aL, dst);
        uint64_t any = 0;
        for (int w = 0; w < W; w++) any |= dst[w];
        if (!any) alive = 0;
      }
      if (joint) { joint_take(P + p, -1); joint_take(P - 1 - p, -1); if (alive && !joint_ok()) alive = 0; }
      if (alive) {
        U[p] = typ == 0 ? sg : 0;
        V[p] = typ == 1 ? sg : 0;
        for (int j = typ; j < k; j += 2) S[j] += sg * pw[p][j];
        dfs(r - 1, nu + (typ == 0), nv + (typ == 1));
        for (int j = typ; j < k; j += 2) S[j] -= sg * pw[p][j];
      }
      for (int mi = 0; mi < nmod; mi++) { unplace(mi, P - 1 - p, aL); unplace(mi, P + p, aR); }
      if (joint) { joint_take(P + p, +1); joint_take(P - 1 - p, +1); }
    }
  }
  U[p] = V[p] = 0;
}

/* Knuth's random-probe estimator (Math. Comp. 29 (1975) 121-136): walk one
 * random root-to-leaf path through the nodes that pass every test; at each
 * node multiply the weight by the number c of passing children and move to a
 * uniformly random one.  The weight reached at depth d is an unbiased estimate
 * of the number of passing nodes at depth d.  Used only to estimate cost. */
static int apply_child(int r, int typ, int sg) {
  int p = r - 1, d = P - r, aR = sg, aL = typ == 0 ? sg : -sg, alive = 1;
  for (int mi = 0; mi < nmod; mi++) {
    int W = nw[mi];
    uint64_t *src = bits[mi] + (size_t)d * W, *dst = bits[mi] + (size_t)(d + 1) * W;
    memcpy(dst, src, sizeof(uint64_t) * W);
    place(mi, P + p, aR, dst);
    place(mi, P - 1 - p, aL, dst);
    uint64_t any = 0;
    for (int w = 0; w < W; w++) any |= dst[w];
    if (!any) alive = 0;
  }
  if (joint) { joint_take(P + p, -1); joint_take(P - 1 - p, -1); if (alive && !joint_ok()) alive = 0; }
  U[p] = typ == 0 ? sg : 0;
  V[p] = typ == 1 ? sg : 0;
  for (int j = typ; j < k; j += 2) S[j] += sg * pw[p][j];
  return alive && bounds_ok(r - 1);
}
static void undo_child(int r, int typ, int sg) {
  int p = r - 1, aR = sg, aL = typ == 0 ? sg : -sg;
  for (int mi = 0; mi < nmod; mi++) { unplace(mi, P - 1 - p, aL); unplace(mi, P + p, aR); }
  if (joint) { joint_take(P + p, +1); joint_take(P - 1 - p, +1); }
  for (int j = typ; j < k; j += 2) S[j] -= sg * pw[p][j];
  U[p] = V[p] = 0;
}
static uint64_t rng_state;
static uint64_t rng(void) { rng_state ^= rng_state << 13; rng_state ^= rng_state >> 7; rng_state ^= rng_state << 17; return rng_state; }
static void knuth(long long probes, long long seed) {
  static double est[MAXP + 2], estSq[MAXP + 2];
  double sumTot = 0, sumTotSq = 0, sumSols = 0;
  rng_state = 0x9E3779B97F4A7C15ULL ^ (uint64_t)seed * 0xD1342543DE82EF95ULL;
  for (long long pr = 0; pr < probes; pr++) {
    int stTyp[MAXP], stSg[MAXP], depth = 0, r = P, nu = 0, nv = 0;
    double w = 1, tot = 1;
    est[0] += 1; estSq[0] += 1;
    while (r > 0) {
      int cT[4], cS[4], c = 0;
      for (int typ = 0; typ < 2; typ++) {
        if (typ == 0 && mode == 2) continue;
        if (typ == 1 && mode == 1) continue;
        for (int sg = 1; sg >= -1; sg -= 2) {
          if (flip == 1 && typ == 0 && nu == 0 && sg < 0) continue;
          if (flip == 2 && typ == 1 && nv == 0 && sg < 0) continue;
          if (apply_child(r, typ, sg)) { cT[c] = typ; cS[c] = sg; c++; }
          undo_child(r, typ, sg);
        }
      }
      if (c == 0) break;
      int j = (int)(rng() % (uint64_t)c);
      w *= c;
      CHECK(apply_child(r, cT[j], cS[j]));
      stTyp[depth] = cT[j]; stSg[depth] = cS[j]; depth++;
      nu += cT[j] == 0; nv += cT[j] == 1;
      r--;
      est[P - r] += w; estSq[P - r] += w * w; tot += w;
    }
    if (r == 0) {
      for (int j = 0; j < k; j++) CHECK(S[j] == 0);
      int wt = 1;
      if (flip == 1 && nu > 0) wt = 2;
      if (flip == 2 && nv > 0) wt = 2;
      sumSols += w * wt;
    }
    while (depth > 0) { depth--; r++; undo_child(r, stTyp[depth], stSg[depth]); }
    sumTot += tot; sumTotSq += tot * tot;
  }
  double mean = sumTot / probes, var = sumTotSq / probes - mean * mean;
  fprintf(stderr, "knuth probes=%lld est_alive_nodes=%.4e stderr=%.3e est_weighted_sols=%.4e\n",
          probes, mean, sqrt(var > 0 ? var / probes : 0), sumSols / probes);
  fprintf(stderr, "knuth_depth:");
  for (int d = 0; d <= P; d++) fprintf(stderr, " %.3e", est[d] / probes);
  fprintf(stderr, "\n");
}

static uint64_t mix64(uint64_t z) { z += 0x9E3779B97F4A7C15ULL; z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL; z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL; return z ^ (z >> 31); }

static void dfs(int r, int nu, int nv) {
  nodes++;
  nodesAtDepth[P - r]++;
  if (!bounds_ok(r)) return;
  if (r == 0) { for (int j = 0; j < k; j++) CHECK(S[j] == 0); emit(nu, nv); return; }
  if (P - r == splitD) {
    long long id = splitctr++;
    int go;
    if (sampleRate > 0) go = (mix64((uint64_t)id ^ ((uint64_t)sampleSeed << 40)) % (uint64_t)sampleRate) == 0;
    else go = (id % partW) == partw;
    if (!go) return;
    explored++;
    long long before = nodes, wbefore = weighted;
    dfs_children(r, nu, nv);
    double sz = (double)(nodes - before);
    subSum += sz; subSumSq += sz * sz;
    subSolsW += weighted - wbefore;
    return;
  }
  dfs_children(r, nu, nv);
}

static void read_prof(const char *path) {
  CHECK(nmod < MAXMOD);
  FILE *f = fopen(path, "r");
  CHECK(f);
  int m, A;
  CHECK(fscanf(f, "%d %d", &m, &A) == 2);
  CHECK(m >= 2 && m <= MAXCLS && A >= 0);          /* A = 0: no profile, every child is cut */
  int mi = nmod++;
  modm[mi] = m; nprof[mi] = A; nw[mi] = (A + 63) / 64;
  for (int r = 0; r < m; r++) { csize[mi][r] = 0; }
  for (int i = 0; i < n; i++) csize[mi][i % m]++;
  for (int r = 0; r < m; r++) CHECK(csize[mi][r] <= MAXCLSZ);
  int W = nw[mi];
  size_t cells = (size_t)m * (MAXCLSZ + 1) * W;
  okMinus[mi] = calloc(cells + 1, sizeof(uint64_t));
  okPlus[mi] = calloc(cells + 1, sizeof(uint64_t));
  bits[mi] = calloc((size_t)(P + 2) * W + 1, sizeof(uint64_t));
  profK[mi] = calloc((size_t)A * MAXCLS + 1, sizeof(int));
  CHECK(profK[mi]);
  CHECK(okMinus[mi] && okPlus[mi] && bits[mi]);
  for (int a = 0; a < A; a++) {
    for (int r = 0; r < m; r++) {
      int s;
      CHECK(fscanf(f, "%d", &s) == 1);
      int nr = csize[mi][r];
      CHECK(s >= -nr && s <= nr && ((s + nr) % 2 == 0));
      int K = (nr - s) / 2;                       /* minus signs in class r */
      if (a == 0) quotaMinus[mi][r] = K;
      profK[mi][(size_t)a * MAXCLS + r] = K;
      for (int c = 0; c <= nr; c++) {
        if (K >= c) okMinus[mi][((size_t)r * (MAXCLSZ + 1) + c) * W + a / 64] |= 1ULL << (a % 64);
        if (nr - K >= c) okPlus[mi][((size_t)r * (MAXCLSZ + 1) + c) * W + a / 64] |= 1ULL << (a % 64);
      }
    }
    bits[mi][a / 64] |= 1ULL << (a % 64);       /* depth 0: every profile */
  }
  int extra;
  CHECK(fscanf(f, "%d", &extra) != 1);          /* nothing after the A rows */
  fclose(f);
}

int main(int argc, char **argv) {
  /* TODO: usage line; says the program's arguments */
  if (argc < 4) { fprintf(stderr, "Claude: \"usage: bdfs n k full|sym|anti [--prof file]... [--flip u|v] [--print] [--part D W w] [--sample D rate seed]\"\n"); return 1; }
  n = atoi(argv[1]); k = atoi(argv[2]);
  mode = !strcmp(argv[3], "full") ? 0 : !strcmp(argv[3], "sym") ? 1 : !strcmp(argv[3], "anti") ? 2 : -1;
  CHECK(mode >= 0 && n % 2 == 0 && n / 2 <= MAXP && n >= 2 && k >= 1 && k <= MAXK);
  P = n / 2;
  const char *profs[MAXMOD]; int np = 0;
  for (int a = 4; a < argc; a++) {
    if (!strcmp(argv[a], "--prof")) { CHECK(a + 1 < argc && np < MAXMOD); profs[np++] = argv[++a]; }
    else if (!strcmp(argv[a], "--flip")) { CHECK(a + 1 < argc); a++; flip = !strcmp(argv[a], "u") ? 1 : !strcmp(argv[a], "v") ? 2 : -1; CHECK(flip > 0); }
    else if (!strcmp(argv[a], "--print")) doprint = 1;
    else if (!strcmp(argv[a], "--part")) { CHECK(a + 3 < argc); splitD = atoi(argv[a + 1]); partW = atoi(argv[a + 2]); partw = atoi(argv[a + 3]); a += 3; CHECK(partW >= 1 && partw >= 0 && partw < partW); }
    else if (!strcmp(argv[a], "--sample")) { CHECK(a + 3 < argc); splitD = atoi(argv[a + 1]); sampleRate = atoll(argv[a + 2]); sampleSeed = atoll(argv[a + 3]); a += 3; CHECK(sampleRate >= 1); }
    else if (!strcmp(argv[a], "--joint")) joint = 1;
    else if (!strcmp(argv[a], "--tuples")) { CHECK(a + 1 < argc); tuplesPath = argv[++a]; }
    else if (!strcmp(argv[a], "--knuth")) { CHECK(a + 2 < argc); knuthProbes = atoll(argv[a + 1]); knuthSeed = atoll(argv[a + 2]); a += 2; CHECK(knuthProbes >= 1); }
    else CHECK(0 && "unknown option");
  }
  CHECK(splitD < 0 || (splitD >= 0 && splitD <= P));
  for (int i = 0; i < np; i++) read_prof(profs[i]);

  const i128 LIM = ((i128)1) << 62;
  for (int p = 0; p < P; p++) {
    i128 t = 1;
    for (int j = 0; j < k; j++) { CHECK(t < LIM); pw[p][j] = (i64)t; t *= (2 * p + 1); }
  }
  for (int j = 0; j < k; j++) {
    i128 c = 0; capM[0][j] = 0;
    for (int r = 1; r <= P; r++) { c += pw[r - 1][j]; CHECK(c < LIM); capM[r][j] = (i64)c; }
  }
  memset(cheb, 0, sizeof cheb);
  cheb[0][0] = 1;
  if (k > 1) cheb[1][1] = 1;
  for (int t = 2; t < k; t++)
    for (int s = 0; s <= t; s++)
      cheb[t][s] = (s > 0 ? 2 * cheb[t - 1][s - 1] : 0) - cheb[t - 2][s];
  for (int r = 0; r <= P; r++) {
    i64 X = r > 0 ? 2 * r - 1 : 1;
    for (int t = 0; t < k; t++) {
      for (int s = 0; s < MAXK; s++) qc[r][t][s] = 0;
      for (int s = t & 1; s <= t; s += 2) {
        i128 c = cheb[t][s];
        for (int e = 0; e < t - s; e++) c *= X;
        qc[r][t][s] = c;
        CHECK(abs128(c) < (((i128)1) << 60));
        CHECK(abs128(c) * (i128)capM[P][s] < (((i128)1) << 120));
      }
      i128 cap = 0;
      for (int p = 0; p < r; p++) {
        i128 v = 0;
        for (int s = t & 1; s <= t; s += 2) v += qc[r][t][s] * (i128)pw[p][s];
        cap += abs128(v);
      }
      CHECK(cap < (((i128)1) << 124));
      capQ[r][t] = cap;
    }
  }
  memset(S, 0, sizeof S);
  struct timespec t0, t1;
  clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t0);
  if (joint) joint_setup();
  int rootok = 1;
  long long ntuples = 0, tuplesRun = 0;
  if (tuplesPath) {
    /* one run per tuple: exactly one profile per modulus (bit idx at depth 0) */
    FILE *tf = fopen(tuplesPath, "r");
    CHECK(tf);
    int idx[MAXMOD];
    while (fscanf(tf, "%d", &idx[0]) == 1) {
      for (int mi = 1; mi < nmod; mi++) CHECK(fscanf(tf, "%d", &idx[mi]) == 1);
      ntuples++;
      for (int mi = 0; mi < nmod; mi++) {
        CHECK(idx[mi] >= 0 && idx[mi] < nprof[mi]);
        for (int w = 0; w < nw[mi]; w++) bits[mi][w] = 0;
        bits[mi][idx[mi] / 64] = 1ULL << (idx[mi] % 64);
        for (int r = 0; r < modm[mi]; r++) { quotaMinus[mi][r] = profK[mi][(size_t)idx[mi] * MAXCLS + r]; CHECK(cntMinus[mi][r] == 0 && cntPlus[mi][r] == 0); }
      }
      if (joint && !joint_ok()) continue;      /* the root itself fails (J) */
      tuplesRun++;
      if (knuthProbes > 0) knuth(knuthProbes, knuthSeed + ntuples);
      else dfs(P, 0, 0);
    }
    fclose(tf);
  } else {
    rootok = !joint || joint_ok();               /* the root itself must pass (J) */
    if (!rootok) nodes = 1;
    else if (knuthProbes > 0) knuth(knuthProbes, knuthSeed);
    else dfs(P, 0, 0);
  }
  clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t1);
  double cpu = (t1.tv_sec - t0.tv_sec) + 1e-9 * (t1.tv_nsec - t0.tv_nsec);
  long long atD = splitD >= 0 ? nodesAtDepth[splitD] : 0, aboveD = 0;
  for (int d = 0; d <= splitD; d++) aboveD += nodesAtDepth[d];
  fprintf(stderr, "rootok=%d joint=%d tuples=%lld tuples_run=%lld\n", rootok, joint, ntuples, tuplesRun);
  fprintf(stderr, "n=%d k=%d mode=%s moduli=%d flip=%d sols=%lld weighted=%lld nodes=%lld cpu=%.3f "
          "splitD=%d atD=%lld aboveD=%lld splitctr=%lld explored=%lld subsum=%.0f subsumsq=%.6e subsolsw=%lld rate=%lld\n",
          n, k, argv[3], nmod, flip, sols, weighted, nodes, cpu, splitD, atD, aboveD, splitctr, explored,
          subSum, subSumSq, subSolsW, sampleRate);
  fprintf(stderr, "depth:");
  for (int d = 0; d <= P; d++) fprintf(stderr, " %lld", nodesAtDepth[d]);
  fprintf(stderr, "\n");
  return 0;
}
