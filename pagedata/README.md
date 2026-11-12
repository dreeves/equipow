This file is all Claude (Fable 5.2).

# The page's data

The three data files that [index.html](../index.html) loads, and one that feeds the third. Programs write them, and none is edited by hand.

| file | what it holds | written by |
|---|---|---|
| [mstar.js](mstar.js) | `MSTAR`: for each n up to 2048, the lower and the upper bound on m\*(n) and the reason for each | [../pagegen/mstar.py](../pagegen/mstar.py) |
| [pow2.js](pow2.js) | `POW2`: the same for the powers of 2, n = 2^k for k up to 72 | [../pagegen/pow2.py](../pagegen/pow2.py) |
| [progress.js](progress.js) | the state of every search, for the section "Search progress" | [../searchwatch/watch.py](../searchwatch/watch.py), whose watcher rewrites it when a search's entry changes |
| [progress-earlier.json](progress-earlier.json) | the 26 searches of before 2026-11-11 that ran an hour or more, in the same form, frozen; the page does not load it: the watcher adds its entries to progress.js | made once, from the last data file of the watcher before watch.py |

Each writer states its file's format in its docstring.
