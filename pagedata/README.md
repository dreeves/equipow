This file is all Claude (Fable 5.2).

# The page's data

The four data files that [index.html](../index.html) loads. Programs write them, and none is edited by hand.

| file | what it holds | written by |
|---|---|---|
| [mstar.js](mstar.js) | `MSTAR`: for each n up to 2048, the lower and the upper bound on m\*(n) and the reason for each | [../pagegen/mstar.py](../pagegen/mstar.py) |
| [pow2.js](pow2.js) | `POW2`: the same for the powers of 2, n = 2^k for k up to 72 | [../pagegen/pow2.py](../pagegen/pow2.py) |
| [searches.js](searches.js) | the state of every tracked search since 2026-11-11, for the section "Search progress" | [../searchwatch/watch.py](../searchwatch/watch.py), whose watcher rewrites it when a search's entry changes |
| [progress.js](progress.js) | the boxes of the searches up to 2026-11-11, as they were then | no program any more: [../searchwatch/progress.py](../searchwatch/progress.py) wrote it until that day |

Each writer states its file's format: mstar.py and pow2.py in their docstrings, watch.py in its docstring, progress.py at its function `js_text`.
