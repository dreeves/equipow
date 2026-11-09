This file is all Claude.

# Form trees

A proof that no sequence of length 288 has order 10, which settles m\*(288) = 9, by Claude (Opus 5.5), started 2026-11-04 and finished 2026-11-08. Every step is checked as it is made, by a program that does not trust the prover. "Form tree" is a name proposed 2026-11-04, awaiting dreeves's approval.

**The result.** The run finished on 2026-11-08 with no open node and no refused task, and `proofs/formtree.py assemble` accepted its verdicts: `VERIFIED: no sequence of length 288 has order 10`, over 205,491 tasks, 981,147,930 nodes and 4,902,209,550 certificates, each certificate checked by `fkernel` as it was made. 1,841 of the tasks went to the Python checker as well, and the two checkers agreed on every one. A real sequence would have shown up as an open node.

## The finished run

`run288v_progress.json` holds the final state: 205,491 tasks done and none pending, nodes, certificates, no open node and no rejected task. `run288v_snapshot.tar.gz` (9.7 MB) is that state itself, every task's verdict: `handoff.py restore` it into an empty directory and run `assemble` on its `verdicts.jsonl` (below) to see `VERIFIED` again.

The tree is estimated at 9.3e8 nodes (standard error 0.3e8), from importance-sampled dives that read 5 to 23% low on the two small starts tried and have not been checked on large ones. On an i7-1260P with 16 threads the checked run made about 3,000 nodes/s in its first 10 minutes, so about 4 days in all if that holds. The tree held 9.81e8 nodes, 5.5% more than the estimate. The finished run took 104 hours on dreeves's Mac with 10 workers, from 2026-11-04 15:09 PST to 2026-11-08 23:24. It began then from no verdicts, after Astra had found two holes in the `fkernel` of the time, both fixed before it began: two nodes could share a name, and a refused task could leave state behind that let a later forged closure pass. The run before the fix was set aside, not used. This run sent about one task in 100 to the Python checker as well (`PY_SAMPLE=100`), against the one in 2,000 described below.

## To pick up the run

    cd searches/formtree
    ./run.sh [processes]                      # needs g++ and python3 with numpy; PYTHON=... for another interpreter

It builds the engine and the checker into `scratch/formtree/build/` (git-ignored), restores the snapshot into `scratch/formtree/run288v/` if that holds no run yet, and goes on from there. Run it again after any stop: a killed run loses only the tasks in flight, at most 4 minutes each.

    tail -1 ../../scratch/formtree/run288v.log            # progress: REJECTED, wrong names and differ must stay 0; OPEN must stay 0 for the claim; overdue above 0 means a worker died: stop and run again
    python3 stopall.py ftree.py                           # stop

To hand the run on, stop it, save, and commit the two files. Then start it again:

    python3 stopall.py ftree.py
    python3 -B handoff.py save ../../scratch/formtree/run288v run288v_snapshot.tar.gz run288v_progress.json
    ./run.sh

`handoff.py save` refuses while the run is alive, because a state taken while tasks finish could lose one. The snapshot stays small, by an estimate from the first tasks: tens of MB of verdicts at the end of the run, and few pending nodes.

Only one machine at a time can work on a state. Two machines working from one snapshot would do the same tasks; there is no merging yet.

On a bigger machine the run should scale: tasks are independent, and each process needs about 100 MB. Measured here: 3.8 ms a node on a loaded performance core and 5.3 on an efficiency core, so roughly 1,000 core-hours. It has been run only on Linux on that one machine; `run.sh`, `handoff.py` and `stopall.py` are written to work on a Mac as well, untested there, and on a Mac there is no address-space limit.

When the log's last line says `finished:`, check it:

    python3 -B -I -S ../../proofs/formtree.py assemble top_288_10.json.gz ../../scratch/formtree/run288v/verdicts.jsonl

That prints `VERIFIED: no sequence of length 288 has order 10` or fails. If the log shows `OPEN` above 0, `assemble` fails and `scratch/formtree/run288v/open_node_*` holds the nodes: then either the engine ran out of forms there or a real sequence is near, and the nodes must be looked at. If it shows `REJECTED`, the prover and the checker disagree: the task is kept and runs again on resume, and the disagreement is a bug to find before anything else.

Disk: the run stops taking new tasks when under 800 MB is free, and says so in the log. It needs under 1 GB in all.

## To check it

The statement of the argument, exactly, with the file formats, is the docstring of `proofs/formtree.py`. No human had reviewed it on 2026-11-04.

    python3 -B -I -S proofs/formtree.py top searches/formtree/top_288_10.json.gz       # the 16 start nodes, 139 vectors closed by certificates, instantly
    python3 -B quals/quals_formtree.py                                                 # the checkers against forged proofs, about 20 s; with numpy, the engine quals too, minutes
    cd searches/formtree; PE_LIB=../../scratch/formtree/build/libpex.so PYTHONPATH=. python3 -B audit.py ../../scratch/formtree/run288v 20 5    # nodes from the run's sample proved again, read by the Python checker alone

What each kind of check establishes:

- **`verdicts.jsonl` with `assemble`.** Each line is `fkernel`'s verdict on a task. `assemble` walks from the top's start nodes through every spilled node and needs an accepted verdict with no open node for each. This shows that the verdicts fit together. It takes the verdicts' word for what `fkernel` saw.
- **The certificates are not kept.** They come to about 3.5 KB a node, 3 TB for the whole tree, so they go down a pipe to the checker and are gone. To see them again the prover must run again. A full recheck by someone else is `./run.sh` on an empty directory, the same 1,000 to 2,000 core-hours: its verdicts are then their own, and the prover and its floating point are no part of what they must trust.
- **`audit.py`.** A random sample of nodes proved afresh and read by the Python checker: minutes, and a test of the machinery, not a proof of the whole.
- **The Python checker in the run.** One task in 2,000, chosen by its name, goes to both checkers, and the log counts disagreements.

## How it works

**Forms and grids.** A form is integer weights w on the residue sums D^(M) for a prime power M. Every sequence of order m has D^(M) in rep(M) + 2 L(M), so a form takes values on a grid: step 2 G, G being the gcd of w over a basis of L(M). Short dual vectors of L(M) give forms with a coarse grid and a narrow range, often only one or two values. For p = 11, 13, 17 and 19 the Legendre symbol and its relatives are such forms; they need (p - 1)/2 <= m - 1, which is why 23 and above are much weaker at m = 10.

**The tree.** A node pins forms to integers. An LP over [-1, 1]^n with the moment rows and the pinned rows bounds the next form. No grid value in range closes the node, one pins it there at no cost in nodes (a fix), two or more split it. An LP dual turned into exact integers is a certificate for each bound.

**The top.** Every vector of residue sums mod 3, 5 and 7, by `proofs/pintree.py`'s enumerator, one per orbit of F -> -F and reversal: 283 vectors, 124 passed over by symmetry, 139 closed by certificates, 16 start nodes kept. `top_288_10.json.gz` is 5 KB.

**The stream.** `pex.cpp` writes every claim with its integer certificate to a pipe. `fkernel` (`proofs/fkernel.cpp`, a separate process with its own 2 GiB limit) recomputes each form's grid from the lattice, each bound from the certificate, and each child list from those, in 128-bit integers with checked ranges. It keeps the node stack itself, so a child left out, a value skipped or a closure without proof makes it refuse the task. A list step, which the stream does not certify, is not used when the stream is on. The cost: engine 2%, checker 3.5%.

**Tasks.** A node still unfinished after 240 s is spilled: it becomes its own task, stored under its name, the first 128 bits of the SHA-256 of what it claims. `verdicts.jsonl` is the only record of what is done, and what remains is worked out from it by walking down from the start nodes.

**Why it is this fast.** The tree grows through M = 11 (depth 0-9), 13 (10-19), 17 (20-36, by a factor of about 50) and stays flat through 19 (37-51, about 30 nodes per entry). Nothing past 19 is ever needed. Nearly every node is a binary split with about 2.8 range tests, 72% of which fix a form or close the node.

Measured, the same trees throughout:

| change | gain |
|---|---|
| moduli in the order 11, 8, 13, 4, 9, 17, 19, 23, ... | 1.6x; other orders up to 20x worse |
| splits only on prime moduli, in strict order, flattest form first; one range test per scan | 1.5x, and splitting on 4, 8, 9 is 7x worse in nodes |
| a form found with two values is not tested again until its predicted width falls 10% | about 2x |
| a split on an anti-invariant form at a node closed under reversal keeps only v >= 0 | 1.4x on 7 starts |
| dual feasibility from the basis in hand, without flips | 1.6x |
| each range LP from the saved point nearest its goal; stop when the weak-duality bound leaves no grid value above | 1.5x fewer iterations, 1.3x in time |
| pivot rows from periodic tiles, in single precision in the primal; no pricing weights; a redundant class row dropped; new rows extend the inverse; moduli with every form implied skipped | 1.7x |

**Tried and rejected, measured, so as not to be tried again without a new idea:**

- A semidefinite bound (min sum y with W' Diag(y) W >= e0 e0'): it closes 0 of 1,377 nodes the LP scan leaves open. Two-valued forms as extra spins barely move it.
- Dual simplex at the grid values in place of primal ranges: 1.6x more iterations. A cache of optimal bases per form: time +20%.
- Lists of lattice vectors at M = 17 or 19: slower, and mostly over any cap.
- Rounding form ranges as cuts: nodes -30%, LPs +35%. Sign probing: no gain at 100x the LPs. Closure certificates reused across nodes: 0 hits of 57,464.
- Choosing the split by entropy, by distance to the grid, or as the form just tested; tests by current width in place of list order: no gain or worse.
- LLL and BKZ on the dual at nodes: they find only the class forms, a ramp c(p) = (-1)^p (2p - n + 1) at M = 2, under 15% when pinned early, and single signs.

## What was checked

All on Linux, Python 3.11, 2026-11-04. The code came before its quals, so most were not seen red; the forged proofs are the red cases.

- Forged proofs refused by both checkers: a grid's step or offset changed, a certificate zeroed or swapped, a value count changed, a child dropped or repeated or moved, a symmetric step without symmetry or on the wrong form, numbers past 128 bits, absurd sizes, a modulus that is no prime power.
- 400 random corruptions of a real stream: refused, or the checkers agree on a verdict that names another node.
- Both checkers give identical verdicts and names on real tasks.
- 22 known sequences of length up to 300 through the prover and both checkers at their own order: every grid and bound held on the sequence, 2,230 grids and 297 bounds, and no node holding one was closed. This qual needs configurations for those cells (`FORMTREE_CFG`), which are not kept here; without them it says skipped.
- All sequences of length 16 and 24 with order 3 and 4 by brute force: every form lies on its grid.
- 432:12, already proved by `proofs/pintree_432_12.json.gz` another way, through the whole road: `VERIFIED`, 455 nodes and 1,786 certificates in about a second; and again with a very short task limit, killed 6 times at random moments and resumed, every task also read by the Python checker.
- 288:11: the top alone proves it, 7 certificates, 348 bytes.
- `searches/formtree/` from a clean copy: built, run, stopped, saved, restored in another copy, resumed with the right tasks left.

The engine is bigger than it needs to be: `pex.cpp` still holds the options that were tried and rejected, all off in `pex.py`'s `run_settings`. None of it is part of what a reader must trust.

## Limits

- `*.cfg` here covers 288:10 and 432:12. For another cell, `python3 -B cellconfig.py n:m` writes one (it needs sympy, fpylll and mpmath besides numpy; it remade both kept files byte for byte), then `top_make.py` makes its top. The driver's moduli and order, in `run.sh`, were tuned for 288:10 only.
- The run stops when the session that started it ends: on 2026-11-04 a run started from inside a Claude Code background job was killed with the job. Start it from a terminal of your own.
- Memory: an unbounded list in an early checker reached 13.7 GB on 2026-11-04 before it was killed. Now each process has an address-space limit and the checkers allocate nothing in proportion to a number in the stream. Core dumps are off.

## Files

- `proofs/formtree.py`: the check, standard library only, integers only, and the statement of the argument. `proofs/fkernel.cpp`: the second check, sharing no code with it.
- `pex.cpp`, `pex.py`: the prover, which only suggests. `ftree.py`: the driver. `run.sh`: build and run. `handoff.py`: save and restore a state. `audit.py`: spot check. `top_make.py`: makes a top. `cellconfig.py`: makes a cell's `.cfg`. `stopall.py`: stops processes by command line.
- `top_288_10.json.gz`, `top_432_12.json.gz`: the tops. `pex_*.cfg`, `pex_*.cfg.Q.npy`: lattice data and the prover's list of forms; a bad entry would be refused by the checkers.
- `run288v_snapshot.tar.gz`, `run288v_progress.json`: the finished run's state, every task's verdict.
- `cells/N_M/`: form-tree proofs of single cells, made 2026-11-09 from a copy of this directory (scratch/certify-20261109/): 96:8, 144:9, 152:7, 168:7, 176:8, 184:7, 272:9 and 752:11, the upper bounds that the page's account of BGPW's Symmetry Conjecture cites. Berend and Golan proved those at 96, 144 and 152 by hand, so these are second proofs; those at 168, 176, 184 and 272 had come from BGPW's integer linear programs, and the one at 752 from a meet in the middle with no certificate. The tops at 152, 168 and 184 use the chain 4, 3, 5, 7: at a length 8 times an odd number and order 7, the parity coset mod 4 forces f(-1) = ±128, as in Berend and Golan's proof at 152. That closes every case of the tops at 152 and 184 and leaves 8 start nodes at 168, against 1,264 and 3,484 start nodes with the chain 3, 5, 7, under which a run on 152:7 checked 2.3e8 nodes in 12 hours without finishing. Tops made the same way at 200 and 216, where order 7 exists, keep the known sequences (the positive controls, in each manifest). Each holds its top, its verdicts (every task read by both checkers; none where the top closes every case), the Python checker's `audit.txt` where a run made one, the prover's configuration, `assemble.txt` and `manifest.json` (the run's parameters, counts and every file's sha256). `python3 -B -I -S proofs/formtree.py assemble cells/N_M/top_N_M.json.gz cells/N_M/verdicts.jsonl`, from the repository's root with `searches/formtree/` before `cells`, checks each.
- `closing-step.md`: an open problem, with notes for the next model to take it up: a stronger way to close nodes, which every open cell needs.
- `fixtures/`: small real streams for the quals. `quals/quals_formtree.py`: the quals.
