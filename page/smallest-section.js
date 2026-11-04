// Claude's table of the smallest length known for each order (Stan Wagon's suggestion, 2026-10-17), from mstar.js: for
// order m, the least length known to reach m, best[m], and the least n whose upper bound is at least m (order m is not
// ruled out), proven smallest when the two agree; orders from 1 to the largest some n up to MSTAR.nmax is not ruled out
// for (dreeves, 2026-10-30: "why isn't 480:14 highlighted in the chart?"), and those past it, each with its least n not
// ruled out in MSTAR.mtopAt (one more from 2026-11-03, [LIN]; through order 17 since 2026-11-04, [M17]).  best[m] is the
// least n whose lower bound is at least m, or the product of two lesser orders' best lengths where that is less, since
// f(x) g(x^n), n the length of f, has order at least the sum of theirs (dreeves's README, 2026-10-31: "[MIN] In the
// "smallest length known for each order" table, we currently have no entries for the smallest known n for orders 14 and
// 15"; the table showed — where no n up to MSTAR.nmax was known to reach m).  An example longer than the chart counts as
// well (MSTAR.past).
// Since 2026-11-04 the rows come from smallest() and smallestRow() (page/shared.js), which a row's box of the m*(n)
// chart shows too ([ROC]), and which hold this table's rules and its history.
document.querySelector('[data-smallest]').replaceChildren(...smallest().map(smallestRow));
