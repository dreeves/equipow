# Pin trees

Proofs that no sequence of length n has order m, by Claude (Opus 5.5), 2026-11-03. The page's section "How Claude ruled out order 12 at 432 and order 13 at 816" gives the short account, and the docstring of `proofs/pintree.py` states the argument exactly.

## Results

| claim | settles | certificates | closed nodes | splits | to make | `pintree.py` | `pintree_second.py` |
|---|---|---|---|---|---|---|---|
| no 432:12 | m\*(432) = 11, so a(11) = 480 in OEIS A323395 | 3,119 | 7,561 | 101 | about 15 CPU-minutes | 7 s | 4.5 min on 6 processes |
| no 816:13 | m\*(816) = 12 | 187,269 | 332,497 | 6,269 | about 21 CPU-hours | 4 min | 64 min on 12 processes |

816:14 has a smaller proof of its own, made first, but 816:13 implies it, so only 816:13 is kept here. The 432:12 run on the Mac (`focus432.py`, `fanout.py`) is an independent route to the same answer.

To check them:

    python3 -B -I -S proofs/pintree.py proofs/pintree_432_12.json.gz
    python3 -B -S proofs/pintree_second.py proofs/pintree_432_12.json.gz 6

## The method

Vocabulary: `proofs/pintree.py`'s docstring defines *residue sums*, *L(M)*, *pins*, *certificate* and *pin tree*.

A proof of impossibility must cover all sequences, not only symmetric ones. The tree does that by the residue sums: every sequence has some residue sums mod M, so a node that lists every admissible vector mod M as a child covers every sequence it stood for.

**1. The parity coset.** The proof searches so far (`overnight_v5.py`, `focus.py`) asked that the residue sums mod M lie in L(M, m), each of the parity of its class's size. There is more. Every sign is 1 mod 2, so mod 2 every sequence of length n is the same polynomial S = (x^n - 1)/(x - 1). So F/(x-1)^m is one fixed polynomial h mod 2, and for M = 2^k the residue sums lie in the single coset rep + 2 L(M, m), with rep = (x-1)^m h. That follows at once from F = (x-1)^m (h + 2 H_1). It holds for asymmetric sequences too. For odd M it says nothing new, since L(M, m) is saturated at 2.

| cell | vectors mod 8, before | with the coset |
|---|---|---|
| 288:10 | 300,469 | 6,037 |
| 432:12 | 186,309 | 5,450 |
| 480:14 | 33,505 | 1,201 |
| 528:12 | 598,093 | 10,240 |
| 672:13 | 779,689 | 16,641 |
| 720:13 | 1,038,361 | 9,604 |

This filter could be used by the running searches as it stands, in `residues.py`'s callers.

The trick of splitting F into its symmetric and antisymmetric parts s and a, each divisible by (x-1)^m, the wrong parity one by (x-1)^(m+1), also gives a condition at even M; measured, the coset implies it.

**2. Certificates.** Take a polynomial g of degree below m and a weight on each class of each pinned modulus, and let w(p) be their sum at position p. For a sequence of order m with the pins, the sum of w(p) a_p over p is a number K known from the pins alone, because the sum of g(p) a_p vanishes. It is also at most the sum of |w(p)| in size. So |K| > sum |w(p)| rules the pins out. These are the dual solutions of the LP over -1 <= a_p <= 1, so such a certificate exists exactly when the pins are impossible even for real numbers. A certificate's total does not depend on the pins, so testing one on another node takes one dot product: over 90% of the closed nodes close with a certificate already made.

**3. Splitting.** A node that stays LP-feasible splits on a further prime power M. The LP bounds each residue sum mod M, each bound a certificate too (the same weights with T s 1_{p = r mod M} subtracted), and the vectors of L(M) inside those bounds become the children. The prover tries candidates in a fixed order and takes the first with at most 64 vectors, else the one with the fewest. It never branches on a single sign.

**The shape of the tree.** Phase 0 pins 3, 5, 7 and 4, one node per orbit of the symmetries F -> -F and F -> x^(n-1) F(1/x). Phase 1 runs through 8. Phase 2 splits adaptively, mostly on 9, 27, 11 and 13.

**Why these two cells.** 5 and 7 divide neither 432 nor 816. Then the residue sums mod 5 and 7 cannot vanish, since their classes differ in parity, and the lattice forces them to be large: at 432, for order 12, mod 5 they must be +-(75, 75, -50, -50, -50), on classes of 87, 87, 86, 86, 86. Such periodic patterns together leave the LP almost nothing: at 816:14, the least possible largest |a_p| in any real solution was 0.984 to 1.0 on the nodes left after mod 8, with about 780 of 816 positions at that bound. That is why no sign-level search is needed.

## Files

- `proofs/pintree.py`: the check, standard library only, integers only. Its docstring is the proof's statement and the file format.
- `proofs/pintree_second.py`: a second check sharing no code with it: its own row reduction and coordinate order, every vector tested by repeated synthetic division, g evaluated in exact fractions by divided differences, and g's degree tested.
- `proofs/pintree_432_12.json.gz`, `proofs/pintree_816_13.json.gz`: the proofs.
- `searches/pintree/pintree_prove.py`: makes proofs and estimates costs. It needs numpy, scipy and highspy. The LP, in floating point, only suggests.
- `quals/quals_pintree.py`: the quals, about 25 minutes.

To make a proof, or to estimate what one would cost:

    python3 -B searches/pintree/pintree_prove.py prove 432:12 4
    python3 -B searches/pintree/pintree_prove.py estimate 528:12 2 1200

Each works in `scratch/pintree/n_m/` and resumes from there. The form of the program kept here made 432:12 from scratch in 187 s on 4 processes, and both checks accept the result. The committed 816:13 was made by an earlier form of it, which saved less often and otherwise built the same kind of tree; the kept form has not remade it.

## What was checked

- Both checks accept both proofs, with the same counts.
- 123 sequences in hand, 37 of them asymmetric, were followed through the procedure at their own order, and 56 through the prover's own code, none lost: their residue vectors are always listed, always inside the proved bounds, and no certificate ever closes their pins.
- 41 small cells known to have sequences were never closed.
- Brute force over all sequences of length 16 and 24 with order >= 3 and >= 4, mostly asymmetric: every residue vector is in the coset.
- `pintree.vectors` equals `residues.residue_vectors` plus an independently derived coset filter, by exact division by (x+1)^(m+e) over F_2.
- Changed proofs are refused: a token removed, m or n changed, a certificate zeroed.

These ran on Linux, Python 3.11. The code came before its quals, so `quals_pintree.py` was not seen red against it. The page-level quals were.

A proof made from these parts is only as good as the lemma in `pintree.py`'s docstring, and no human had reviewed that on 2026-11-03.

## Where it stops

Elsewhere the tree has *loose nodes*: residue sums small, the LP far from tight, and every further modulus giving many children that stay feasible. Tree sizes are heavy tailed, and a few nodes dominate. Knuth's estimator, in an earlier form of `estimate`, on a loaded machine, 30 to 180 dives each:

| cell | CPU-days, roughly | median tree per node after mod 8 | mean |
|---|---|---|---|
| 480:14 | 200 | 14 | 4,200 |
| 864:14 | 880 | 6 | 530 |
| 528:12 | 1,200 (380 if mod 8 is left to the adaptive splitting) | 37 | 880 |
| 288:10 | 2,300 (the existing search: about 1,300, from its 258 days on 5 workers) | 60 | 1,850 |
| 768:13 | 6,900 | 1 | 1,770 |
| 720:14 | 52,000 | 218 | 30,000 |
| 672:13 | 970,000 | 8,900 | 1,100,000 |

They are rough and probably low, since a dive rarely hits the largest trees.

So these need something more. 672:13, 480:\* and 720:\* have D = 0 at 5 or 7, which removes the forced structure altogether. One loose node at 768:13 had mod 9 ranges nearly the full size of its classes.

Tried, and no better: splitting a node on the sum over half of a nearly monochrome class, instead of on a new modulus. It seemed promising, since such a sum takes few values, but the estimated trees came to 10^19 to 10^23 nodes.
