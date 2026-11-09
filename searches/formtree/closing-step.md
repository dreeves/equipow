This file is all Claude.

# A stronger closing step for the form tree: an open problem

Written 2026-11-09 for the next model to take it up (dreeves: "can you leave notes about that for fable to try?"). Nothing here is
done yet. Read this directory's README.md first: it explains the prover (`pex.cpp`), the two checkers (`proofs/fkernel.cpp` and
`proofs/formtree.py`, which never trust the prover), the driver (`ftree.py`), tops (`top_make.py`) and their chains, and the want
order of splitting moduli.

## The goal

Exclusion proofs for the chart's open cells. Bounds as of 2026-11-09 (`mstar.js`, and its `past` key for 1440):

| n | m*(n) | exclusion that would settle or narrow it | what it is worth |
|---|---|---|---|
| 480 | 12–14 | 480:13 | m*(480) = 12; A323395's a(12) = 672; A306248's terms a(240) through a(263) |
| 480 | 12–14 | 480:14 | narrows 480 to 12–13; one of three exclusions (with 720:14 and 864:14) that settle a(13) = 960 |
| 528 | 11–12 | 528:12 | m*(528) = 11 |
| 720 | 13–14 | 720:14 | m*(720) = 13 |
| 864 | 12–14 | 864:13, 864:14 | m*(864) = 12, or narrows it |
| 1440 | 16–17 | 1440:17 | m*(1440) = 16 |

An exclusion N:M means no ±1 sequence of length N has order M (power sums 0 through M − 1 all equal), which proves m*(N) ≤ M − 1.

## Why the form tree can't do them yet

Two estimates of tree sizes, with importance-sampled Knuth dives and Markov floors: one on 2026-11-06, one on 2026-11-09. Both
ran on dreeves's Mac, and their notes are in `scratch/` there, which git ignores (`scratch/formtree-cells-20261106/NOTES.md`,
`scratch/costs-20261109/NOTES.md`):

| target | start cases (chain 3, 5, 7) | nodes: dive estimate; 95% floor | whole Mac |
|---|---|---|---|
| 480:14 | 1 | about 1e10; ≥ 8.5e8 | about 19–27 days (range 2–80) |
| 480:13 | 3 | 2e14 to 7.6e14; ≥ 1e13 | at least about 30 years, even at the floor |
| 528:12 | 10 | about 1e21; ≥ 1.4e19 | out of reach |
| 864:14 | 2 | about 4.5e28; ≥ 1.2e25 | out of reach |
| 864:13 | 23 | about 3e31; ≥ 9.4e27 | out of reach |
| 720:14 | 4 | about 3.7e44; ≥ 8.5e42 | out of reach |
| 1440:17 | 1 | about 2.6e129 | cannot finish |

What the estimates show:
- **Where the nodes stay open:** everywhere, the trees grow on forms mod 17, 19, 23 and 29, where the LP over [−1, 1]^n with the
  pinned rows stops closing nodes.
- **1440:17:** 255 of the first 7,801 nodes stay open with no form left to split on (moduli up to 37) and a feasible LP, so no
  amount of time finishes it with this prover.
- **Calibration:** importance dives read 0.77 to 0.99 of the exact size on the finished roots of a 152:7 run, and a
  frontier-sweep estimator read 0.34 to 1.02 on four finished 288:10 roots. The tails are heavy, so only the floors are robust, and
  they are already out of reach.

## The lead: what closed 152:7, 168:7 and 184:7

On 2026-11-09 three cells that looked out of reach closed almost at once. The 152:7 form tree had run 2.3e8 nodes in 12 hours
without finishing, and dives put 168:7 and 184:7 at 4.9e9 and 1.8e12 nodes. The source of the fix is Berend and Golan's proof by
hand that m*(152) = 6 (Math. Comp. 75, 2006, case 1.e):
1. **The 2-adic step:** at a length 8 times an odd number, order 7 = 2^3 − 1 rules out (x + 1) | f (BGPW Prop. 4.6). So
   f(−1) ≠ 0, and with f(−1) ∈ 128ℤ and |f(−1)| ≤ n < 384, f(−1) = ±128.
2. **Counting:** the class sums mod 3 are then forced lopsided, and counting the positions in the classes mod 6 contradicts the
   f(−1) value.

**The fix:** start the top's chain with modulus 4 (`top_make.py lib N:7 4,3,5,7 out`). pintree's enumerator uses the parity coset
at powers of 2, so the start nodes' mod-4 sums already carry f(−1) = ±128.
- 184:7: the top closes every case (1,038 certificates).
- 152:7: the top closes every case (2 certificates).
- 168:7: the top leaves 8 start nodes, which closed in 720 nodes.
- **Controls:** tops made the same way at 200 and 216, where order 7 exists, keep their known sequences.
- **Where the proofs are:** `cells/152_7`, `cells/168_7` and `cells/184_7`, with manifests.

**The puzzle worth solving first.** The prover had the same facts and didn't use them.
- **What the LP already excludes:** at each 152:7 start case (chain 3, 5, 7), a floating-point LP over [−1, 1]^152 with the
  start node's class sums excludes f(−1) = ±128 by itself, at all 1,264 start cases. With the mod-3 sums pinned, the LP bounds
  f(−1) to about [−100, 96].
- **What the prover had:** the cell's configuration includes the parity coset rep for modulus 4 (`cellconfig.problem`: rep for
  powers of 2), whose grid for f(−1) is 128 + 256ℤ.
- **The test:** a prover that bounded the f(−1) form on that grid at the start node would close every case at once. Yet with 4
  first in the want order (`4,8,11,13,9,17,19,23,16,25,27,29,31,37`), 10 of 20 sampled 152:7 start cases still ran past 60 s, and
  the 10 that finished took 13 to 61,283 nodes.
- **Where to look:** which forms the prover bounds at a node, in what order, and whether a form's grid includes the coset's offset
  before its modulus is split. A weakness there could cost every cell, open ones included.

## Ideas, untested

1. **Find out why the prover misses the f(−1) cut** (above), and fix it in the prover. The checkers recompute every grid and
   certificate, so a prover change needs no new trust; a checker change does, and needs dreeves's approval.
2. **Higher 2-adic facts at the open cells.** There f(−1) = 0 is forced (2^m > n), so the step above gives nothing. Congruences on
   derivatives at −1 might. At 288:10 (2026-10-30), Lemma A said f'(−1) ≡ 4096·(D_1 + D_3)/8 mod 8192 with |f'(−1)| ≤ 20736. In the
   class of open leaves with 4096 there (189,000 of them, in the earlier overnight_v5 search, not the form tree), that allows only
   ±4096, ±12288 and ±20480, and slicing those leaves by it closed 44% of them. Values at i and at the 8th roots of unity are the
   next candidates.
3. **Tops whose chains start with 8, 16 or 32 at the open cells** (480 = 32 × 15, 528 = 16 × 33, 720 = 16 × 45, 864 = 32 × 27):
   measure start counts and bench a sample, as above. It costs seconds to minutes; 4 and 8 are early in the want order already,
   so expect less than at 168.
4. **Cuts where the trees grow** (forms mod 17 to 29): look at the LP's optimum at nodes that won't close, and at which grid values
   each form's interval still holds; disjunctive or Chvátal–Gomory cuts on those forms, checked as certificates.
5. **Keep positive controls in every experiment.** A known sequence of order m − 1 at the same n (for example 480:12's) must
   never sit in a closed node. `scratch/bg-20261109/seq_in_top4.py` on dreeves's Mac checks a top that way.

## Ground rules here

- **Rules:** AGENTS.md's rules hold: quals first, red then green; no mutating git; ask dreeves about new names and trust changes.
- **Runs:** launch every long run through the repository's `track.py run NAME N:M -- …`, so the page's Search progress section
  shows it.
- **Sources:** read the primary source before computing a cited result; 152:7's first run re-proved a six-line hand proof.
- **What counts as a proof:** only what `proofs/formtree.py assemble` verifies, with every task's certificates checked by fkernel
  as it is made, and preferably every task read again by the Python checker (`PY_SAMPLE=1`).
