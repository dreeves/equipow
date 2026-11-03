# The pinned search

The search behind the results of 2026-11-03. Claude (Opus 5.5) wrote it; the page's "How Claude found its examples" gives the short account.

## Results

Every sequence is (anti)symmetric. Two checks agree on every order below: power sums in plain integers over {0..n-1} and {1..n} with synthetic division by x - 1, and `mstar.py`'s own `from_rp` and `order`. The upper bounds are the page's, not rechecked here. `witnesses/witness_<n>_<m>.txt` holds up to 8 distinct sequences for each, one JSON object a line; 1008:13 and 544:10 had 453 and 58.

| n | was | now | order above it ruled out by |
|---|---|---|---|
| 544 | 9-10 | 10 | the norm bound mod 3 |
| 576 | 11-12 | 12 | the residue condition mod 5 |
| 624 | 11-12 | 12 | the residue condition mod 25 |
| 912 | 12-13 | 13 | the residue condition mod 5 |
| 960 | 13-15 | 15 | the residue condition mod 7 |
| 1008 | 12-13 | 13 | the residue condition mod 5 |

Beyond the chart: 1440 has order 15.

Since no length below 960 allows order 15, a(14) = 960 in OEIS A323395. Smallest known lengths: order 13 was 960, now 912; order 14 was 1920, now 960; order 15 was 3840, now 960; order 16 was 7680, now 1920 (960:15 doubled).

Powers of 2, the first K found for each excess e, old -> new: e = 1: 10 -> 10; e = 2: 20 -> 20; e = 3: 29 -> 28; e = 4: 37 -> 36; e = 5: 39 -> 39; e = 6: 48 -> 47. For e = 7, `coins` finds nothing at K <= 55 and leaves K = 56 undecided at its 15-minute limit, so 57 stands; for e = 8, nothing at K <= 56, with 58, 60 and 62 undecided, so 65 stands; for e = 9, nothing at K = 61 or 64, so 68 stands. `coins` left out blocks of excess below -0.2 for speed, so a new first is a construction, not a proof of minimality.

## Running it

    cd searches/pinned && make
    python3 -B ../../quals/quals_pinned.py

It needs a C++ compiler, numpy, mpmath and fpylll. `make` builds `libpinned_enum.so`, `libpinned_anneal.so` and `coins`.

- `pinned_model.py`: the moment and pin rows, and the Gaussian estimate of the expected count (`log2E`).
- `pinned_profiles.py`: the residue profiles an (n, m) allows: the lattice L(M, m) and its parity coset.
- `pinned_lattice.py`: the kernel lattice, its reduction, and the pruned enumeration, calling `pinned_enum.cpp`.
- `pinned_problem.py`: one instance: n, m, the pins, its free set, its congruences.
- `pinned_ap.py`: the free set x divisible by 3 (`--free ap3`) or not (`--free non3`), with `pinned_anneal.cpp` for the fixed signs.
- `pinned_block.py`: the free set a central block, fixed signs annealed ring by ring.
- `coins.cpp`: for each excess e, the first K where 2^K is a join of products of known blocks of order at least K + e, by the method `pow2.py`'s comment describes: `coins blocksfile emin emax Kmax maxnodes [startK]`, the file a list of `n m` pairs. It found that joins exist at K = 28, 36 and 47; `pow2.py`'s `BASES[28]`, `BASES[36]` and `BASES[47]` are shorter joins, condensed from its output by hand and checked by `quals/quals_pow2.py`.

## The commands that found each result

The runs used an earlier form of this code, in the scratch directory, with the same arguments under these names. The code here was rerun only on the three controls that `quals/quals_pinned.py` holds: 544:10, 1008:13 and 1440:14.

    # 1008:13, about 1 CPU minute per seed
    pinned_ap.py 1008 13 8,5,7,11,13,17,19 --maxdn 2.5 --cap 1e6 --topk 16 --qgate 15 --c 0 --floor 1 --maxnodes 2e9
    # 912:13, 45 s
    pinned_ap.py 912 13 8,9,5,7,11,13,17,19 --maxdn 5 --cap 2e6 --topk 16 --qgate 30 --c 0 --floor 1 --maxnodes 2e9
    # 624:12, 97 s
    pinned_ap.py 624 12 8,9,5,7,11,13,17,19 --maxdn 30 --cap 1e6 --topk 32 --qgate 40 --c 0 --floor 1 --maxnodes 2e9
    # 576:12, about 11 minutes on 5 cores
    pinned_ap.py 576 12 8,9,5,7,11,13,17,19 --maxdn 25 --cap 1e6 --topk 128 --qgate 42 --noise 0.2 --swaps 3e6 --c 0.5 --floor 2 --maxnodes 1e9
    # 544:10, under 2 minutes
    pinned_ap.py 544 10 8,9,5,7,11,13,17,19 --free non3 --noise 0.2 --swaps 1e6 --maxdn 1000 --cap 2e5 --topk 8 --t1 1 --t2 1 --c 0 --floor 1 --maxnodes 1e9
    # 1440:15, 117 s on the successful seed of 8
    pinned_block.py 1440 15 205 8,9,5,7,11,13,17,19,23,29 --ratio 1.05 --flips 3e4 --swaps 6e4 --qgate 40 --c 0 --floor 2 --maxnodes 3e9
    # 960:15, 678 s on seed 3303; about 100 minutes in all on 6 to 12 cores
    pinned_block.py 960 15 205 8,9,5,7,11,13,17,19,23,29 --ratio 1.05 --flips 3e4 --swaps 6e4 --tlimit 1450 --qgate 38 --maxnodes 3e9 --c 0 --floor 2 --seed 3303
    # 960:14, 152 s on the successful seed of 12
    pinned_block.py 960 14 190 8,9,5,7,11,13,17,19,23 --ratio 1.05 --qgate 24 --c 0 --floor 1 --maxnodes 2e9

## What made the search faster

1. More pins. Residue sums pinned mod 8, 9, 11, 13, 17, 19, 23 and 29 as well as 5 and 7. Each prime p removes (p - 1)/2 dimensions and, up to about p = 29, does not lower the expected count per coset, because a solution's residue sums are nearly forced at small p. 1008:13: about 2^-6 at d = 153 with the old pins, about 2^20 at d = 125 with the new ones, by `log2E`.
2. The exact parity coset. Admissible residue sums lie in rep + 2 L(M, m), rep = (x-1)^m (x+1)^(t-1-m) S^t. At n = 16 * odd and high order this forces D_4 != 0, which earlier profiles did not account for.
3. The fixed signs as an optimisation of the exact penalty perp2 = tau' Sigma_F^-1 tau, each unit costing 0.72 bits, by annealing over swaps that keep class sums. Congruences that class sums determine are solved at the class level, the rest by a meet in the middle over swaps.
4. The free set. x divisible by 3 when 3 | n; every x not divisible by 3 when 3 does not divide n (the class x = 0 mod 3 is then nearly fixed); a central block with ring-by-ring annealing and no congruences at all. The block's lattice depends only on f, m and the pins, not on n.
5. The pruning bound scales with the coset's own budget, (k/d) R^2. Tighter shapes than c = 0 lost real solutions on the 1440:14 control: 7 solutions at c = 0, floor 1, and none in the same work at any tighter shape tried.

## The open cells, estimated

A Gaussian estimate of the number of solutions; very lopsided rows make these too high by 10 to 30 bits.

- Likely none: 288:10, 432:12, 480:13, 480:14, 816:13, 816:14, 720:14.
- Marginal: 528:12, 672:13, 864:13, 864:14.
- Plentiful but unreached: 720:13, 768:13. The best residuals give about 2^-24 to 2^-30 per coset there, so these need fixed signs generated about 1000 times faster (C++, incremental coset updates).

Order 16 at 1440: 4.1e11 nodes over 149 passing cosets at f = 215 and 230 found nothing.
