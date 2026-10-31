// auto-render's onload, the code its onload attribute held until 2026-10-30 (dreeves's README: "[VSC] VS Code isn't
// happy about the "&amp;&amp;" in one of the jsdelivr lines for KaTeX"): it draws the page's \( ... \).  A loop that
// followed, meant to glue each formula to the text right after it ("13.", "+1s") in an nw span, never glued anything
// (auto-render puts each .katex alone in a span of its own, so its next sibling is null) and was removed the same day
// (scratch/readme-20261030/NOTES.md).  The hand-written nw spans around formulas still keep their text together.
function renderMath() {
  renderMathInElement(document.body, {delimiters: [{left: '\\(', right: '\\)', display: false}], throwOnError: false});
}
