This file is all Claude (Fable 5.2).

# The page's stylesheet and scripts

What [index.html](../index.html), the page at https://equipow.dreev.es, loads besides its data and KaTeX: one stylesheet and seven scripts. They were inline in index.html until 2026-10-31. index.html links every one of them, and a qual (see [../quals/](../quals/)) keeps it so: a stylesheet or script here that the page does not load turns it red.

- [style.css](style.css): all of the page's CSS.
- [math.js](math.js): the call that has KaTeX draw the page's `\( … \)` once KaTeX has loaded.
- [shared.js](shared.js): what the two charts share: pan and zoom, the gold rings of the least length for each order, and the box that opens under a chart for a cell, a column or a row.
- [mstar-section.js](mstar-section.js): the chart of the bounds on m\*(n) for n up to 1024, drawn from [../pagedata/mstar.js](../pagedata/mstar.js).
- [pow2-section.js](pow2-section.js): the chart of the bounds on m\*(2^k) − k for k up to 72, drawn from [../pagedata/pow2.js](../pagedata/pow2.js).
- [smallest-section.js](smallest-section.js): the table of the smallest length known for each order, from mstar.js.
- [codes.js](codes.js): the page's hex codes, joins and constructions as buttons. A click expands one to its explicit partition and checks its power sums.
- [progress-section.js](progress-section.js): the section "Search progress", drawn from [../pagedata/progress.js](../pagedata/progress.js), which it loads again every minute while the section is open.

Each script's opening comment states what it draws and the decisions behind it.
