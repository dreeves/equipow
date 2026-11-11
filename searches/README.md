This file is all Claude (Fable 5.2).

# Finished searches

Each directory holds one search that has ended: its record (journals, logs, sequences found, proofs), and its programs where they are its own. The programs that several searches share are in [../engine/](../engine/), the checkers of the proofs in [../proofs/](../proofs/), and what launches and watches a search in [../searchwatch/](../searchwatch/).

A cell n:m is the question whether some sequence of length n has order m: n signs, +1 or −1, whose power sums vanish for the exponents 0, …, m − 1. A *proof search* tries to show that there is none, and a *witness search* looks for one. A witness search that finds nothing settles nothing.

## Proof searches

| directory | cell | when | how it ended |
|---|---|---|---|
| [overnight_240/](overnight_240/) | 240:11 | to 2026-10-07 | The first three versions, on a solver's word. Stopped with nodes open. |
| [overnight_v4/](overnight_v4/) | 304:9 | 2026-10-07 to 10-08 | Version 4, likewise. Stopped with nodes open. |
| [overnight_v5_304_9/](overnight_v5_304_9/) | 304:9 | 2026-10-08 to 10-10 | Proved: there is none, so m\*(304) = 8. |
| [overnight_v5_240_11/](overnight_v5_240_11/) | 240:11 | 2026-10-08 to 10-20 | Proved: there is none, so m\*(240) = 10. |
| [overnight_v5_384_11/](overnight_v5_384_11/) | 384:11 | 2026-10-20 | No verdict kept. A [certificate](../proofs/proof384.py) settled m\*(384) = 10 that day. |
| [focus_480/](focus_480/) | 480:14 | 2026-10-20 to 10-25 | Stopped unfinished. Still open: m\*(480) is 12, 13 or 14. |
| [focus_672/](focus_672/), then [fanout_672/](fanout_672/) | 672:13 | 2026-10-20 to 10-25 | Stopped unfinished. A sequence of order 13 was found later, so there was no proof to find. |
| [focus_432/](focus_432/), then [fanout_432/](fanout_432/) | 432:12 | 2026-10-26 to 11-03 | Stopped unfinished. The pin tree settled it the same day. |
| [pintree/](pintree/) | 432:12, 816:13 | 2026-11-03 | Proved: there is none, so m\*(432) = 11 and m\*(816) = 12. |
| [formtree/](formtree/) | 288:10 and eight more | 2026-11-04 to 11-09 | Proved: there is none, so m\*(288) = 9. |

## Witness searches

| directory | cell | when | how it ended |
|---|---|---|---|
| [join720/](join720/) | 720:11 | 2026-10-21 | None found. Other searches found one later. |
| [search288/](search288/), [pruning288/](pruning288/), [sweep288/](sweep288/) | 288:10 | 2026-10-24 | None found. None exists. |
| [search592/](search592/) | 592:10 | 2026-10-25 | None found. Another search found one. |
| [pinned/](pinned/) | seven cells | 2026-11-03 | Found 544:10, 576:12, 624:12, 912:13, 960:15, 1008:13 and 1440:15. |
| [tilted/](tilted/) | two cells | 2026-11-04 | Found 672:13 and 1440:16. |

One more witness search, at 288:10, has its program and its record in [../engine/](../engine/): lattice288.py.
