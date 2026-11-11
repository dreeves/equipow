This file is all Claude (Fable 5.2).

# The search engine

The programs that try to prove that no sequence of length n has order m, and the modules they share. A *sequence* is n signs, +1 or −1, one for each of the numbers 0, …, n − 1: which of the two parts it is in. It *has order m* when its power sums `Σ a_p p^k` vanish for k = 0, …, m − 1, so a sequence of order m has every lower order too. [The page](https://equipow.dreev.es) explains the question.

No search here calls a case impossible on floating point alone: each such verdict has a certificate that is checked in exact integer arithmetic.

Each program's docstring defines its vocabulary and says how to run it. The records of the runs that have ended are in [../searches/](../searches/). What launches and watches a run is in [../searchwatch/](../searchwatch/).

## The count-vector search

It settled m\*(304) = 8 and m\*(240) = 10.

- [overnight_v5.py](overnight_v5.py): splits the sequences by how many +1's they have in each residue class mod M, for one modulus after another, and gives each node of that tree to certbb.
- [certbb.py](certbb.py): certified branch and bound for one node. It searches with a floating-point LP solver (HiGHS), closes a box only on a certificate checked in exact integers, and writes a proof that its `Check` replays from scratch.
- [width.py](width.py): the lattice directions of certbb's width test.
- [boxsplit.py](boxsplit.py): a further pass over the leaves that a run of overnight_v5.py left open, each split by more moduli inside the box of counts that its LP relaxation allows.

## The focused searches

They ran at 480:14, 672:13 and 432:12 (length:order), and none reached a verdict: [../searches/](../searches/) says how each ended.

- [focus.py](focus.py): Astra's depth-first certified search of the cases that a preparation leaves.
- [focus432.py](focus432.py) (Claude's), [focus480.py](focus480.py) and [focus672.py](focus672.py) (Astra's): the exact preparations. Each reduces its cell to cases, 2 at 432, 195 at 480 and 2 at 672, every step checked. [focus432_certificates.json.gz](focus432_certificates.json.gz) and [focus480_certificates.json.gz](focus480_certificates.json.gz) hold the integer certificates that two of them check.
- [fanout.py](fanout.py): Claude's. It finishes a stopped focus.py run with several worker processes, checks every certificate as it is made, and keeps only the proof's tree.
- [reprove.py](reprove.py): rechecks a finished fanout.py run's trees from scratch.
- [reflection.py](reflection.py): the exact reversal of proof tokens, for fanout.py.
- [residues.py](residues.py): the enumeration of the residue sums that a sequence of a given order can have. [../pagegen/mstar.py](../pagegen/mstar.py) imports it too.
- [fastlp.py](fastlp.py), [_fastlp.c](_fastlp.c) and [_fastlp.cpython-313-darwin.so](_fastlp.cpython-313-darwin.so): a dense dual simplex in C, for fanout.py's LP solves.
- [native_bound.py](native_bound.py), [native_bound.cpp](native_bound.cpp), [_native_bound.cpython-313-darwin.so](_native_bound.cpython-313-darwin.so) and [build_native.py](build_native.py): a certificate's exact bound in C++ with GMP, for fanout.py and reprove.py, and the script that builds it.

The two compiled modules are for Python 3.13 on macOS.

## A witness search

- [lattice288.py](lattice288.py), with [lattice288.log](lattice288.log) and [lattice288_journal.jsonl](lattice288_journal.jsonl): Astra's bounded search for a symmetric sequence of length 288 and order 10. It ran on 2026-10-20 over 2,736 cases: 2,551 came back empty and 185 timed out. No such sequence exists, as the proof in [../searches/formtree/](../searches/formtree/) later showed.

## Before editing

A run's journal records a fingerprint of the code that made it, and the programs refuse a journal of other code. Several modules also pin their neighbours by SHA-256 at import. So an edit here can make a kept journal unusable or stop an import: read the module's docstring first.
