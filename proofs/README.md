This file is all Claude (Fable 5.2).

# Proofs and their checkers

Programs that check the proofs and the constructions on [the page](https://equipow.dreev.es), and the data of some of those proofs. Each program's opening comment states its claim and its argument, and most say how to run it.

A *sequence* is n signs, +1 or −1. It *has order m* when its power sums vanish for the exponents 0, …, m − 1, and m\*(n) is the largest order at length n. Below, "no n:m" means that no sequence of length n has order m, so that m\*(n) ≤ m − 1.

## Upper bounds

| files | what they check |
|---|---|
| [formtree.py](formtree.py), [fkernel.cpp](fkernel.cpp) | A form tree. The two checkers, in Python and in C++, share no code. Their proofs are in [../searches/formtree/](../searches/formtree/): no 288:10, and eight other cells. |
| [pintree.py](pintree.py), [pintree_second.py](pintree_second.py) | A pin tree. The two checkers share no code. Their proofs are [pintree_432_12.json.gz](pintree_432_12.json.gz) (no 432:12, so m\*(432) = 11) and [pintree_816_13.json.gz](pintree_816_13.json.gz) (no 816:13, so m\*(816) = 12). The prover is in [../searches/pintree/](../searches/pintree/). |
| [proof288.py](proof288.py) | m\*(288) ≤ 10 (2026-10-25). The form tree has since shown m\*(288) = 9. |
| [proof384.py](proof384.py), [proof384.wl](proof384.wl) | Astra's certificate that m\*(384) = 10 (2026-10-20), in Python and in Mathematica. |
| [proof752.py](proof752.py) | m\*(752) ≤ 10 (2026-10-25). |
| [proof1456.py](proof1456.py) | m\*(1456) ≤ 11, so m\*(1456) = 11 (2026-11-07). |
| [proof512.wl](proof512.wl) | The computations of the page's proof that no sequence of length 512 or 496 has order 10, in Mathematica. |

    python3 -B proofs/proof288.py
    python3 -B -I -S proofs/pintree.py proofs/pintree_432_12.json.gz

The Python programs above use the standard library only, except proof752.py, which also needs numpy.

## Constructions for powers of 2

- [certificate_2^17.wl](certificate_2^17.wl), [certificate_2^18.wl](certificate_2^18.wl) and [certificate_2^24.wl](certificate_2^24.wl): Mathematica scripts. Each builds a partition of {0, …, 2^k − 1} into two parts whose power sums agree for the exponents 0, …, k, one more than Thue–Morse reaches, from sequences on the page, and checks it directly.
- [X_order25_2^24.txt.gz](X_order25_2^24.txt.gz): the part of the last of those partitions that contains 0: 8,388,608 numbers, one a line.
- [record_gaps.wl](record_gaps.wl): the table behind the page's Theorem 1. For each gap g = 1, …, 9 it gives the least k known with m\*(2^k) ≥ k + g and the construction that shows it, and checks each row.

## The rest

- [count128/](count128/): the exhaustive count of the sequences of length 128 and order 7. There are 862, which is 431 partitions, 303 of them antisymmetric. Its programs' opening comments say how they count, `out128/` holds the run's output, `prior/` holds earlier lists that its quals compare with, and `python3 quals.py` there builds and checks the programs.
- [symlarge.py](symlarge.py): the objects of the page's proof that BGPW's Symmetry Conjecture holds at every sufficiently large length, computed exactly for [../quals/quals_symlarge.py](../quals/quals_symlarge.py). It needs numpy. [symlarge.html](symlarge.html) held that proof for a day and now only sends its old address to the page.
- [lattice_search.wl](lattice_search.wl): the lattice method behind Claude's examples, cut down to what runs in plain Mathematica. Written for Stan Wagon on 2026-10-14.
- [mma240.wl](mma240.wl): an early Mathematica search for a sequence of length 240 and order 11. Its header says that Claude wrote it without a Mathematica to test it on.
