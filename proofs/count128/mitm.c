/* mitm.c -- plain meet in the middle, the independent check for small n.
 *
 * Counts +-1 sequences a_0..a_{n-1} (n even, n <= 48) with
 *   M_j = sum_i a_i i^j = 0 for j = 0..k-1.
 * Left half = positions 0..n/2-1, right half = n/2..n-1.  Every one of the
 * 2^(n/2) left assignments is stored as (h, mask) where h is a 64-bit hash of
 * its exact moment vector; the table is sorted by h.  Every one of the 2^(n/2)
 * right assignments computes the exact negated moment vector, hashes it, and
 * scans the run of equal h; each candidate is accepted only after its left
 * moment vector is recomputed exactly and compared component by component.
 * Equal vectors have equal hashes, so no solution is missed; a hash collision
 * can only cost time.  Each accepted sequence is rechecked from scratch in
 * __int128 and printed as a +/- string (position 0 first).
 * usage: mitm n k */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

typedef int64_t i64;
typedef __int128 i128;
/* TODO: error copy; says which assertion failed (source line and the condition) */
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "Claude: \"CHECK failed line %d: %s\"\n", __LINE__, #c); exit(2); } } while (0)

static int n, k, H;
static i64 pw[64][8];

typedef struct { uint64_t h; uint32_t mask; } Ent;

static uint64_t hashv(const i64 *v) {
  uint64_t x = 0x9E3779B97F4A7C15ULL;
  for (int j = 0; j < k; j++) { x ^= (uint64_t)v[j]; x *= 0xBF58476D1CE4E5B9ULL; x ^= x >> 31; }
  return x;
}
static void moments(uint32_t mask, int off, i64 *v) {   /* bit b set = a_{off+b} = +1 */
  for (int j = 0; j < k; j++) v[j] = 0;
  for (int b = 0; b < H; b++) {
    int s = (mask >> b & 1) ? 1 : -1;
    for (int j = 0; j < k; j++) v[j] += s * pw[off + b][j];
  }
}
static int cmp(const void *a, const void *b) {
  uint64_t x = ((const Ent *)a)->h, y = ((const Ent *)b)->h;
  return x < y ? -1 : x > y;
}

int main(int argc, char **argv) {
  CHECK(argc == 3);
  n = atoi(argv[1]); k = atoi(argv[2]);
  CHECK(n % 2 == 0 && n >= 2 && n <= 48 && k >= 1 && k <= 7);
  H = n / 2;
  for (int i = 0; i < n; i++) {
    i128 t = 1;
    for (int j = 0; j < k; j++) { pw[i][j] = (i64)t; t *= i; CHECK(t < ((i128)1 << 56)); }
  }
  long N = 1L << H;
  Ent *L = malloc(sizeof(Ent) * N);
  CHECK(L);
  i64 v[8], w[8], need[8];
  for (long m = 0; m < N; m++) { moments((uint32_t)m, 0, v); L[m].h = hashv(v); L[m].mask = (uint32_t)m; }
  qsort(L, N, sizeof(Ent), cmp);
  long found = 0;
  for (long m = 0; m < N; m++) {
    moments((uint32_t)m, H, v);
    for (int j = 0; j < k; j++) need[j] = -v[j];
    uint64_t h = hashv(need);
    long lo = 0, hi = N;
    while (lo < hi) { long mid = (lo + hi) / 2; if (L[mid].h < h) lo = mid + 1; else hi = mid; }
    for (long e = lo; e < N && L[e].h == h; e++) {
      moments(L[e].mask, 0, w);
      int eq = 1;
      for (int j = 0; j < k; j++) eq &= (w[j] == need[j]);
      if (!eq) continue;
      char buf[64];
      for (int b = 0; b < H; b++) { buf[b] = (L[e].mask >> b & 1) ? '+' : '-'; buf[H + b] = (m >> b & 1) ? '+' : '-'; }
      buf[n] = 0;
      for (int j = 0; j < k; j++) {
        i128 s = 0;
        for (int i = 0; i < n; i++) { i128 z = 1; for (int e2 = 0; e2 < j; e2++) z *= i; s += buf[i] == '+' ? z : -z; }
        CHECK(s == 0);
      }
      printf("%s\n", buf);
      found++;
    }
  }
  fprintf(stderr, "n=%d k=%d sols=%ld\n", n, k, found);
  return 0;
}
