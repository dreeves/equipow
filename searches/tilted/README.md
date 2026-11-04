# The tilted search

The search behind the results of 2026-11-04. Claude (Opus 5.5) wrote it, on top of `searches/pinned/`, whose problem setup, lattice and profiles it imports; the page's "How Claude found its examples" gives the short account.

## Results

| claim | settles | seed | search time to the witness | the order above it ruled out by |
|---|---|---|---|---|
| order 13 at 672, antisymmetric | m\*(672) = 13 | 810 | 532 s | order 14: the residue condition mod 5 |
| order 16 at 1440, symmetric | a(15) = 1440 in OEIS A323395 | 1401 | 709 s | order 18: the residue condition mod 7, so m\*(1440) is 16 or 17 |

Each time is one single-threaded process's wall time on a loaded 16-core machine, from the end of its setup.

`witnesses/` holds the two records. Their exact orders were checked by synthetic division and by power sums over {0..n-1} and {1..n} in plain integers (`verify_witness.py`), by `overnight_v5.exact_order` on the decoded code, and by `mstar.py`, which asserts every page code's order.

**Why 1440 is the least length of order 16.** Up to 1024 the chart's upper bounds are all below 16. Of the even n from 1026 to 1438, `mstar.two` (the 2-adic bound: n is not a multiple of 32) rules out 195 and `mstar.norm` rules out 11, each at order 16. That leaves 1344 = 64 · 21, where the residue condition mod 5 does it: its class sums D_r, of sizes 269, 269, 269, 269, 268, must all be congruent mod 5^4, since f is divisible by (x - 1)^16 and (1 - z)^4 is 5 times a unit at a fifth root of unity z. No two differ by 625 or more, so they are all equal, and they sum to 0, so each is 0. But four of the classes have odd size. `mstar.mtop_at(16)` does this search; `quals_mstar`'s `q_mtop_is_open_first_at_1440_past_the_chart` checks it.

**Powers of 2.** `searches/pinned/coins`, with 672 at order 13 and 1440 at order 16 among its blocks, finds no earlier first K than the page has for excess 1 to 8: 10, 20, 28, 36, 39, 47, 56, 58, with none left undecided. It leaves out blocks of excess below -0.2. Excess 9 and 10 are undecided: a 25-minute run of each, at low priority beside other work, did not finish, so whether 1440:16 lowers excess 9's 68, or reaches excess 10 by K = 72, is open. `pow2.js`'s bounds are as before.

## Running it

    (cd searches/pinned && make) && (cd searches/tilted && make)
    python3 -B quals/quals_tilted.py

It needs a C++ compiler, numpy, mpmath and fpylll. The search writes `found_<n>_<m>.jsonl` to the directory it runs in, so run it from a scratch directory.

The two runs, with `T` the path to this directory, one BLAS thread each:

    python3 -B -u $T/tilted.py 672 13 180 1.1 8,9,5,7,11,13,17,19 1e3 3300 --prof $T/profiles/prof_672_13.txt --kout 1000 --stop 1 --gumbel 0 --field 0.35 --floor 1 --sag 0.4 --seed 810 --every 60 --maxnodes 1e7
    python3 -B -u $T/tilted.py 1440 16 240 1.1 8,9,5,7,11,13,17,19,23,29 300 3400 --kout 30 --stop 1 --gumbel 0 --field 0.35 --floor 1 --sag 0.4 --seed 1401 --every 60 --maxnodes 1e9

The arguments are n, m, W, th, the pinned moduli, K and the seconds to search. On 2026-11-04 both commands, run from this directory's code in empty directories on the machine that found them, returned the same witnesses at the same coset ranks (433 and 10), after 1,071 and 1,823 s under heavier load.

The run at 672 found its witness under the tool's previous form, which differed from `tilted.py` in the two options `--lev` and `--tail`, both off here. The run at 1440 used this form. In this directory only paths changed: `tilted.py` was `tb4.py` and `libtbeam.so` was `libtbeam4.so`.

`profsearch.py 672 13 8,9,5,7,11,13,17,19` writes the search behind `profiles/prof_672_13.txt`; `--prof` reads the JSON on its last line. The run at 1440 used `default_profiles`.

## The method

Vocabulary from `searches/pinned/README.md`: *pins*, *coset*, *free set*, *fixed signs*.

**1. Each sign's bias (`entropy.py`).** Pins can leave some signs nearly decided. The distribution of largest entropy on the signs that meets the pins' rows in expectation has an independent mean t_p for each position p, found by a dual Newton iteration on the sum of ln 2cosh(A'l) minus l'b. The same point gives a saddle-point estimate of the number of solutions, which unlike the Gaussian one does not assume balanced signs.

**2. The pins (`profsearch.py`).** Coordinate descent over each modulus's cheapest admissible vectors, by that estimate rather than by energy. At 672:13 it gained 6.6 bits (`profiles/prof_672_13.txt`).

**3. The free set.** W is the size of a central stretch of pairs, as in `pinned_block.py`; th would leave out positions of large bias, and at 1.1 it leaves out none.

**4. The fixed signs (`tbeam.cpp`).** A K-best beam over the positions outside the free set, outermost first. Its score is the penalty for t's part outside the lattice's span, about the tilted mean, plus -2 log P(a_p) for each sign. A random logistic field added to the log-odds on each run (`--field`) keeps runs from repeating cosets. Each of a run's best `--kout` finishers is a coset.

**5. The enumeration (`tbeam.cpp`).** Every coset gets Schnorr–Euchner enumeration on one reduced basis, within the bound

    bound[k] = min(R2, x R2 (1 - sag (1 - x)) + floor),  x = (k + 1) / d

so a positive `--sag` runs below the straight line through the middle of the tree. At 1008:13, one core, 180 s, seed 77: 43 witnesses at sag 0, 79 at 0.1, 223 at 0.2, 552 at 0.3, 989 at 0.45 and 1 at 0.6.

**How many pins.** The run at 1440:16 pinned primes to 29. At 1440:15, W = 230, sag 0.4, in a fixed 285 s of wall time, setup included, a process found 14 witnesses with pins to 29, 2 to 31 and 0 to 37.

## Files

- `tilted.py`: the search.
- `tbeam.cpp`: the beam and the enumerator. `make` builds `libtbeam.so`.
- `entropy.py`: the tilts and the tilted estimate (`Rows`).
- `profsearch.py`: pins by the tilted estimate.
- `verify_witness.py`: an independent check of a code in plain integers, importing nothing from this repository: `verify_witness.py n m code`.
- `profiles/prof_672_13.txt`: `profsearch.py`'s output for 672:13.
- `witnesses/`: the two records.
- `quals/quals_tilted.py`, at the repository's root: the quals. The tool came before them, so they were not seen red against it; the page's quals for its results were.

## Controls

`quals_tilted` finds 1008:13 and 544:10 from empty directories. On 2026-11-04, on one loaded core, with the settings below and pins by energy:

| cell | W | sag | seeds | setup | search to the first witness |
|---|---|---|---|---|---|
| 1008:13 | 150 | 0.4 | 1, 2, 3 | 29 to 31 s | 1 s each |
| 1440:14 | 220 | 0.4 | 1, 2, 3 | 61 to 104 s | 0 to 23 s |
| 544:10 | 110 | 0.3 | 1, 2, 3 | 26 to 30 s | 11 to 81 s |

## Limits

- The model's `logE` is not a calibrated probability: the witness at 672:13 had logE -17.0 at coset rank 433, and the runs' sums of E were 2^9.5 at 672 and 2^24.8 at 1440, far above the one witness each found. Nothing here measures how often a seed succeeds. At 672 eight processes with nearby settings ran for about ten minutes and one found its witness; at 1440 six did, for about fifteen minutes, and one found it.
- A run is deterministic for a given seed on one build, but `-march=native` and a different numpy can change its floating-point path, so another machine may reach different witnesses from the same seed.
- 1440:17 is open: no chain of `mstar.CHAINS` rules it out at `MTOP_CAP`. Two runs with W = 240 and 280 found no witness.
