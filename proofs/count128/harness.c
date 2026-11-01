/* harness.c -- planted-solution check of tri.c, white box: it includes tri.c and builds
 * the tables with tri's own setup().
 * usage: harness n k plus1 plus2 < solutions   (one +/- string of length n per line)
 * Every solution fed in must carry plus1 plus signs on X1 and plus2 on X2 (asserted).
 * For each it counts
 *   level1: L's level-1 key equals R's (negreskey(M(L)) = reskey(M(R))),
 *   coset:  L's full key equals R's, which is what the pass loop looks up,
 *   found:  process_pair, given this (L, R), finds at least one solution.
 * process_pair asserts level 1 itself, and prints every solution it finds (rebuilt and
 * rechecked by rebuild_check), so a caller can check the planted one is among them. */
#define main tri_main
#include "tri.c"
#undef main
int main(int argc, char **argv) {
  CHECK(argc == 5);
  n = atoi(argv[1]); k = atoi(argv[2]);
  int plus1 = atoi(argv[3]), plus2 = atoi(argv[4]);
  setup(plus1, plus2);
  doprint = 1;
  char line[MAXN + 2]; long planted = 0, level1 = 0, coset = 0, found = 0;
  while (fgets(line, sizeof line, stdin)) {
    int len = (int)strcspn(line, "\n");
    CHECK(len == n && line[len] == '\n');
    uint64_t lm = 0, rm = 0; int pl = 0, pr = 0;
    for (int i = 0; i < n; i++) CHECK(line[i] == '+' || line[i] == '-');
    for (int t = 0; t < N1; t++) { int a = line[X1[t]] == '+' ? 1 : -1; pl += a > 0; lm |= (uint64_t)(a == -SL.maj) << t; }
    for (int t = 0; t < N2; t++) { int a = line[X2[t]] == '+' ? 1 : -1; pr += a > 0; rm |= (uint64_t)(a == -SR.maj) << t; }
    CHECK(pl == plus1 && pr == plus2);
    planted++;
    i64 ML[MAXK], MR[MAXK];
    side_moments(&SL, lm, ML); side_moments(&SR, rm, MR);
    level1 += negreskey(ML) == reskey(MR);
    coset += lkey_full(ML) == rkey_full(MR);
    long long before = nsols;
    process_pair(lm, ML, rm);
    found += nsols > before;
  }
  /* TODO: machine-readable summary tokens: the run's parameters and the four counts above */
  fprintf(stderr, "harness n=%d k=%d plus1=%d plus2=%d cosets=%lld planted=%ld level1=%ld coset=%ld found=%ld\n",
          n, k, plus1, plus2, (long long)ncos, planted, level1, coset, found);
  return 0;
}
