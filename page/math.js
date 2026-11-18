// auto-render's onload, the code its onload attribute held until 2026-10-30 (dreeves's README: "[VSC] VS Code isn't
// happy about the "&amp;&amp;" in one of the jsdelivr lines for KaTeX"): it draws the page's \( ... \).  A loop that
// followed, meant to glue each formula to the text right after it ("13.", "+1s") in an nw span, never glued anything
// (auto-render puts each .katex alone in a span of its own, so its next sibling is null) and was removed the same day
// (scratch/readme-20261030/NOTES.md).  The hand-written nw spans around formulas still keep their text together.
// KaTeX draws \href only where its option trust allows (by default nowhere: it then draws the command's name, in red).
// The page trusts exactly its links to its codes' anchors, # and an id N:M (dreeves's README, 2026-10-31, [IND]: "make
// the 'p320' or whatever be a hyperlink / anchor link"), so that any other \href still shows in red.
// MATH holds auto-render's options, which the charts' panels use too, for the math they add to the page later
// (page/shared.js, 2026-11-03).  The appendix's entries (ul.entries) are left for later (2026-11-18, Opus 5.5): they
// hold most of the page's math (11,460 of 13,596 formulas that day, which took the drawing from 108 ms to 702 ms on
// dreeves's Mac), so KaTeX draws them when the appendix first opens, by a click or by find in page, which searches their
// TeX meanwhile (page/appendix.js); a box draws the entry it shows (chartPanel).
const MATH = {delimiters: [{left: '\\(', right: '\\)', display: false}], throwOnError: false,
              trust: ({command, url}) => command === '\\href' && /^#\d+:\d+$/.test(url)};
function renderMath() {
  renderMathInElement(document.body, {...MATH, ignoredClasses: ['entries']});
}
