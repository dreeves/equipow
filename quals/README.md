This file is all Claude (Fable 5.2).

# Quals

Quals are this repository's tests; the word is [Beeminder's](https://blog.beeminder.com/quals). A qual is written before the code it checks and seen to fail, and then the code is made to pass it. It guards against a regression that could happen by accident, in a number, a sequence, a link, a structure or a behavior, not in the page's wording.

    python3 -B quals/quals_layout.py        # one suite; it exits nonzero if a qual fails

- `quals_*.py`: the suites, 87 of them on 2026-11-10. Each runs alone and from any directory, and finds the repository's root by its own location. In 27 of them a qual is a function `q_*`, and the suite runs them all, or those named on its command line. The other 60 are `unittest` suites.
- `quals_*.cjs`: quals that run under `node`, most of them the page's scripts on a small stand-in for a browser's page. Some suites run them, and each also runs alone.
- [quals_case_lp_stall.json](quals_case_lp_stall.json) and [quals_codes_sets.json](quals_codes_sets.json): data that [quals_case_lp.py](quals_case_lp.py) and [quals_codes.py](quals_codes.py) read.

A qual's comment is framed as a bug report: its *replicata* (the steps), its *expectata* (what must happen) and its *resultata* (what happened instead, before the work).

## What they need

- Python 3.13 with numpy, scipy, sympy, mpmath, ortools, highspy and Pillow. Some suites need fpylll as well.
- Node, for the `.cjs` files, and headless Chrome, for the suites that look at the page as a browser draws it.
- A C++ compiler, for the form-tree suites, and wolframscript, for the three suites that run a Mathematica script.
- Many suites name files under `scratch/`, which git ignores: that directory exists only on the machine where the work is done.

There is no runner here: run the suites one after another. On that machine all of them take about an hour and a half.
