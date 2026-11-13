This file is all Claude (Fable 5.2, and Opus 5.5 for preview.py).

# What makes the page's data, and its preview

The two programs that compute the bounds [the page](https://equipow.dreev.es) charts, and write them to [../pagedata/](../pagedata/). m\*(n) is the largest order of a sequence of length n: the largest m for which {1, …, n} splits into two parts whose power sums agree for the exponents 0, …, m − 1.

    python3 -B pagegen/mstar.py     # about 2 minutes; writes pagedata/mstar.js
    python3 -B pagegen/pow2.py      # a few seconds; writes pagedata/pow2.js

Both run from any directory. They need numpy, sympy, scipy and ortools, the last two through [../engine/](../engine/), which mstar.py imports.

- [mstar.py](mstar.py): the bounds on m\*(n) for n = 1, …, 2048, each with its reason.
  - A lower bound is a sequence in hand: an example whose hex code is on the page, or a join or product of such, its order checked by exact power sums.
  - An upper bound is a test that every sequence of that order would have to pass and none can: the 2-adic bound, a norm bound, or an enumeration of residue sums that comes up empty; or a proof that the page gives or cites.
  - It reads the examples and the cited values from [../index.html](../index.html), and asserts that every example has the order claimed for it.
- [pow2.py](pow2.py): the bounds on m\*(2^k) for k = 1, …, 72, with the construction behind each lower bound: 2^k written as a join of products of sequences from mstar.py's chart. It imports mstar.py and reads pagedata/mstar.js.

- [preview.py](preview.py): ../preview.png, the picture a shared link to the page shows: the page's title and its tables down to the legend, drawn by headless Chrome. `python3 -B pagegen/preview.py`, from any directory, takes a few seconds and needs Chrome and the network (the page's fonts and KaTeX): when the page does not load whole it fails and leaves preview.png as it is. quals_index.q_preview_png_is_current fails while preview.png differs from what it draws.

Each docstring defines its terms and states the format of the file it writes. After a change of a chart's data, rerun mstar.py and then pow2.py, then preview.py.
