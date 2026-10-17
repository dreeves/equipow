#!/usr/bin/env python3
"""Quals for index.html's chart of the bounds on m*(2^k) - k, the excess over Thue-Morse at the powers of 2, for k up
to 72: the section "pow2" right after the m*(n) chart, drawn from pow2.js.  Run: python3 -B quals_pow2_page.py
[name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
The static quals read index.html, index.html as it would be without this chart (git show BASE:index.html with EDITS
made) and pow2.js.  The browser quals load copies of index.html, each with mstar.js beside it and a pow2.js (the real
one, made-up data, or none), in headless Chrome driven through the DevTools protocol by DRIVER, a Node script: a true
viewport of each configuration's width and pixel ratio, its theme by prefers-color-scheme, real mouse moves, touch taps
and swipes, and screenshots whose pixels are checked against the data.  DRIVER finds the cells by geometry alone: the
plot is the svg in #pow2-chart, K columns of equal width, and rows ROW CSS px apart from the top (row E) down to row 1,
the bottom GAP px of each row page surface.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, html, time, shutil, difflib, tempfile, traceback, subprocess
from math import prod
from PIL import Image
import quals_index                            # the m*(n) chart's quals, for their list of the table's updates

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, 'index.html')
DATA = os.path.join(HERE, 'pow2.js')          # made by pow2.py; the chart's data
MSTAR = os.path.join(HERE, 'mstar.js')        # made by mstar.py; the m*(n) chart's data, which the page also loads
ICONS = ('favicon.ico', 'favicon.svg', 'apple-touch-icon.png')   # the page's icons, which it also loads
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
# The last commit before this chart ("Settings and things").  The chart went in as insertions only, so the static
# quals diff against the page as it was then with EDITS made, the edits since then that are not this chart's (see
# committed); add to EDITS when dreeves next edits the page's existing text.
BASE = '5365370'
# dreeves's copyedit of this chart (2026-10-11): his words, which stand without a Claude: "…" attribution.  The quals
# hold the page to them exactly, and any other English the chart shows must be Claude: "…".
HEADING = 'Bounds on <span class="nw"><i>m</i><sup>*</sup>(2<sup><i>k</i></sup>) − <i>k</i></span> for every <i>k</i> up to 72'
LABEL = 'Chart of the bounds on m*(2^k) − k, the excess over Thue–Morse, for k from 1 to 72'   # the chart's aria-label
HINT = 'Hover over a cell for details.'       # the readout until a cell is read out
# The lines of the page that hold his words, stripped: the copy rules of q_new_copy_is_attributed pass over them.
DREEVES_LINES = (f'<h2 id="pow2-title">{HEADING}</h2>',
                 f'<div id="pow2-chart" role="img" aria-label=\'{LABEL}\'></div>',
                 f'<p id="pow2-readout" aria-live="polite">{HINT}</p>')
# The legend, copied from the m*(n) chart's mutatis mutandis at dreeves's request (2026-10-12): its one English word,
# "open", is his from that legend, so it stands without a Claude: "…" attribution, as his lines do.
LEGEND_LINES = ('<ul class="legend">',
                '<li><span class="swatch exists" aria-hidden="true"></span><span class="nw"><i>k</i> + <i>e</i> ≤ <i>m</i><sup>*</sup>(2<sup><i>k</i></sup>)</span></li>',
                '<li><span class="swatch open" aria-hidden="true"></span>open</li>',
                '<li><span class="swatch impossible" aria-hidden="true"></span><span class="nw"><i>k</i> + <i>e</i> &gt; <i>m</i><sup>*</sup>(2<sup><i>k</i></sup>)</span></li>',
                '</ul>')
HIS = (re.sub(r'<[^>]*>', '', HEADING), LABEL, HINT, 'known', 'open', 'impossible')   # his words as a reader gets them
K, ROW, GAP = 72, 14, 2                       # columns k = 1..K; rows ROW CSS px apart, the bottom GAP of each surface
KINDS = ('exists', 'open', 'impossible')      # the kinds of cell, as the tokens of their colors name them
F = [2 ** 24, 25]                             # f, the construction of length 2^24 and order 25, as a block [n, m]
KLABELS = list(range(10, K + 1, 10))          # the k labels below the plot
OUTLINE = (36, 5)                             # the cell whose outline the screenshots check
SWIPE = (29, 8)                               # the cell a phone's swipe starts on, after the outline's tap
MSTAR_LAYOUT = (44, 16, 2, 14)                # the m*(n) chart's plot: left and right gutters, top, row pitch (CSS px)
WHO = ('BGPW', 'Claude alone', 'Claude and BGPW')   # the provenance labels of the page's new results
RUNS = {}                                     # DRIVER's reports by configuration name, made once per process (see run)


# ---------------------------------------------------------------------------------------------------------------------
# Reading the page and the data

def page(): return open(INDEX, encoding='utf-8').read()


def after(line, *new):
    """An edit (old, new, count) that inserts the lines new right after line, which occurs once."""
    return line + '\n', line + '\n' + ''.join(s + '\n' for s in new), 1


# The edits of the page's text since BASE that are not this chart's, made by dreeves or for him, as (old, new, how many
# times old occurs): the new results' updates that quals_index.py lists (its TABLE_UPDATE); the CSS rule that keeps
# their table in one row; a sentence each on the residue condition at 432, 480 and 528; and in the m*(n) chart, two
# stale comments fixed, his fixes of its zoom-out and reset buttons' labels, and its provenance label "Claude and Stan"
# become "Claude and BGPW"; and (2026-10-12) the new results' powers of 2 in a second table with their remarks.
EDITS = quals_index.TABLE_UPDATE + (
    after('.new-block { display: grid; grid-template-columns: minmax(0, 1fr); gap: 0.45rem; }',
          "/* The new results' entries for 432, 480 and 528 became ranges (2026-10-11), which made that table 12 px wider than",
          '   main; a little less side padding in its cells keeps it in one row, unscrolled, at 945 px. */',
          '.new-block table.block td { padding-inline: 0.65rem; }'),
    after('      <p>An antisymmetric example of order 11 found by Claude. BGPW also showed order 10.</p>',
          '      <!-- TODO: says order 13 at 432 is ruled out by the residue condition mod 5, so m*(432) is 11 or 12 -->',
          '      <p>Claude: "Order 13 is ruled out by the residue condition mod 5."</p>'),
    after('      <p>A symmetric example of order 12 found by Claude.</p>',
          '      <!-- TODO: says order 15 at 480 is ruled out by the residue condition mod 7, so m*(480) is 12, 13 or 14 -->',
          '      <p>Claude: "Order 15 is ruled out by the residue condition mod 7."</p>'),
    after("      <p>BGPW had an example of order 10 before Claude's work. Claude found another independently, by joining an example of length 192 and order 9 to an antisymmetric piece of length 336 and order 9, chosen so that their 9th power sums cancel.</p>",
          "      <!-- TODO: says order 13 at 528 is ruled out by the residue condition mod 5 (Claude's proof), so m*(528) is 10, 11 or 12 -->",
          '      <p>Claude: "Order 13 is ruled out by the residue condition mod 5."</p>'),
    ('  <!-- TODO: heading; says the chart shows the bounds on m*(n) for every n up to 1000 -->\n',
     '  <!-- the chart shows the bounds on m*(n) for every even n up to 1000 -->\n', 1),
    ("id=\"mstar-zoom-out\" aria-label='zoom out\"'", "id=\"mstar-zoom-out\" aria-label='zoom out'", 1),
    ('<button type="button" id="mstar-reset">↺</button>',
     "<button type=\"button\" id=\"mstar-reset\" aria-label='reset zoom' title='reset zoom'>↺</button>", 1),
    ('an odd n has no partition at any m, as the caption says.  Pan and zoom act',
     'an odd n has no partition at any m.  Pan and zoom act', 1),
    ("const WHO = ['BGPW', 'Claude alone', 'Claude and Stan'];", "const WHO = ['BGPW', 'Claude alone', 'Claude and BGPW'];",
     1),
    # the new results' powers of 2 (2026-10-12): the remarks' new sentences and entries (their second table is in
    # quals_index.TABLE_UPDATE)
    ('      <p>Claude: "Joint construction: <span class="nw">2<sup>24</sup> = 320<sup>2</sup>·112 + 432·48·2<sup>8</sup></span>, that is, <span class="nw"><i>f</i> = (<i>p</i><sub>320</sub> # <i>p</i><sub>320</sub> # <i>p</i><sub>112</sub>)</span> <span class="nw">∨ (<i>p</i><sub>432</sub> # <i>p</i><sub>48</sub> # τ<sub>8</sub>)</span>. Hence <span class="nw"><i>m</i><sup>*</sup>(2<sup><i>k</i></sup>) ≥ <i>k</i> + 1</span> for every <span class="nw"><i>k</i> ≥ 24</span>, and by the 2<sup>18</sup> entry above for every <span class="nw"><i>k</i> ≥ 18</span>."</p>\n',
     '      <p>Claude: "Joint construction: <span class="nw">2<sup>24</sup> = 320<sup>2</sup>·112 + 432·48·2<sup>8</sup></span>, that is, <span class="nw"><i>f</i> = (<i>p</i><sub>320</sub> # <i>p</i><sub>320</sub> # <i>p</i><sub>112</sub>)</span> <span class="nw">∨ (<i>p</i><sub>432</sub> # <i>p</i><sub>48</sub> # τ<sub>8</sub>)</span>. Hence <span class="nw"><i>m</i><sup>*</sup>(2<sup><i>k</i></sup>) ≥ <i>k</i> + 1</span> for every <span class="nw"><i>k</i> ≥ 24</span>, and by the 2<sup>18</sup> entry above for every <span class="nw"><i>k</i> ≥ 18</span>."</p>\n      <!-- TODO: says the upper bound 29 at 2^24 is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n', 1),
    ('      <p class="code">\n        <span><i>p</i><sub>112</sub> <span class="nw">(<i>m</i> = 7)</span> and <i>p</i><sub>48</sub> <span class="nw">(<i>m</i> = 6)</span>, from the paper\'s Table 5:</span>\n        <code>A5994DB29B45A0</code>\n        <code>C27D8C</code>\n      </p>\n    </li>\n',
     '      <p class="code">\n        <span><i>p</i><sub>112</sub> <span class="nw">(<i>m</i> = 7)</span> and <i>p</i><sub>48</sub> <span class="nw">(<i>m</i> = 6)</span>, from the paper\'s Table 5:</span>\n        <code>A5994DB29B45A0</code>\n        <code>C27D8C</code>\n      </p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>33</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {35, …, 41}</span></p>\n      <!-- TODO: says order 35 at 2^33 comes from a join of three products of the examples above and Thue–Morse (lengths and orders spelled out), making 2^33 the first power of 2 known to beat Thue–Morse by 2, where f # f first did at 2^48; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>33</sup> = 208·320<sup>3</sup> + 336<sup>3</sup>·2<sup>5</sup> + 304·480<sup>2</sup>·2<sup>3</sup></span>: a join of three products of examples above (of orders 8, 9, 10, 8 and 12) and Thue–Morse, each of order 35. That beats Thue–Morse by 2 at a lower power of 2 than <span class="nw"><i>f</i> # <i>f</i></span> does at 2<sup>48</sup>. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>49</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {52, …, 61}</span></p>\n      <!-- TODO: says order 52 at 2^49 comes from a join of six such products, each of order 52, making 2^49 the first power of 2 known to beat Thue–Morse by 3; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "A join of six products of examples above and Thue–Morse, each of order 52; the powers-of-2 chart above lists them. That beats Thue–Morse by 3. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n', 1),
    ('      <p>With <i>f</i> the 2<sup>24</sup> construction above, <span class="nw"><i>f</i> # <i>f</i> # τ<sub>3</sub></span> has order <span class="nw">25 + 25 + 3 = 53</span>. The paper\'s 52 is Stong\'s.</p>\n    </li>\n',
     '      <p>With <i>f</i> the 2<sup>24</sup> construction above, <span class="nw"><i>f</i> # <i>f</i> # τ<sub>3</sub></span> has order <span class="nw">25 + 25 + 3 = 53</span>. The paper\'s 52 is Stong\'s.</p>\n      <!-- TODO: says the six products of the 2^49 entry, each times tau_2, give order 54 at 2^51; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "The six products of the 2<sup>49</sup> entry, each times τ<sub>2</sub>, give order 54. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>57</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {61, …, 71}</span></p>\n      <!-- TODO: says order 61 at 2^57 comes from a join of five such products, each of order 61, making 2^57 the first power of 2 known to beat Thue–Morse by 4; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "A join of five products of examples above and Thue–Morse, each of order 61; the powers-of-2 chart above lists them. That beats Thue–Morse by 4. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>67</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {72, …, 83}</span></p>\n      <!-- TODO: says order 72 at 2^67 comes from a join of eight such products, each of order 72, making 2^67 the first power of 2 known to beat Thue–Morse by 5; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "A join of eight products of examples above and Thue–Morse, each of order 72; the powers-of-2 chart above lists them. That beats Thue–Morse by 5. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n', 1),
    # the powers' remarks once 560 reached order 10 (2026-10-12): 2^18, 2^41, 2^48, 2^61 and 2^71 added; Claude's sentences at
    # 2^49, 2^51, 2^57 and 2^67 rewritten for the joins the chart now gives there, and Claude's TODO at 2^33 fixed
    ('    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>24</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {25, …, 29}</span></p>\n      <p>Claude: "Joint construction: <span class="nw">2<sup>24</sup> = 320<sup>2</sup>·112 + 432·48·2<sup>8</sup></span>, that is, <span class="nw"><i>f</i> = (<i>p</i><sub>320</sub> # <i>p</i><sub>320</sub> # <i>p</i><sub>112</sub>)</span> <span class="nw">∨ (<i>p</i><sub>432</sub> # <i>p</i><sub>48</sub> # τ<sub>8</sub>)</span>. Hence <span class="nw"><i>m</i><sup>*</sup>(2<sup><i>k</i></sup>) ≥ <i>k</i> + 1</span> for every <span class="nw"><i>k</i> ≥ 24</span>, and by the 2<sup>18</sup> entry above for every <span class="nw"><i>k</i> ≥ 18</span>."</p>\n      <!-- TODO: says the upper bound 29 at 2^24 is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n      <p class="code">\n        <span><i>p</i><sub>112</sub> <span class="nw">(<i>m</i> = 7)</span> and <i>p</i><sub>48</sub> <span class="nw">(<i>m</i> = 6)</span>, from the paper\'s Table 5:</span>\n        <code>A5994DB29B45A0</code>\n        <code>C27D8C</code>\n      </p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>33</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {35, …, 41}</span></p>\n      <!-- TODO: says order 35 at 2^33 comes from a join of three products of the examples above and Thue–Morse (lengths and orders spelled out), making 2^33 the first power of 2 known to beat Thue–Morse by 2, where f # f first did at 2^48; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>33</sup> = 208·320<sup>3</sup> + 336<sup>3</sup>·2<sup>5</sup> + 304·480<sup>2</sup>·2<sup>3</sup></span>: a join of three products of examples above (of orders 8, 9, 10, 8 and 12) and Thue–Morse, each of order 35. That beats Thue–Morse by 2 at a lower power of 2 than <span class="nw"><i>f</i> # <i>f</i></span> does at 2<sup>48</sup>. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>49</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {52, …, 61}</span></p>\n      <!-- TODO: says order 52 at 2^49 comes from a join of six such products, each of order 52, making 2^49 the first power of 2 known to beat Thue–Morse by 3; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "A join of six products of examples above and Thue–Morse, each of order 52; the powers-of-2 chart above lists them. That beats Thue–Morse by 3. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {55, …, 63}</span></p>\n      <p>With <i>f</i> the 2<sup>24</sup> construction above, <span class="nw"><i>f</i> # <i>f</i> # τ<sub>3</sub></span> has order <span class="nw">25 + 25 + 3 = 53</span>. The paper\'s 52 is Stong\'s.</p>\n      <!-- TODO: says the six products of the 2^49 entry, each times tau_2, give order 54 at 2^51; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "The six products of the 2<sup>49</sup> entry, each times τ<sub>2</sub>, give order 54. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>57</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {61, …, 71}</span></p>\n      <!-- TODO: says order 61 at 2^57 comes from a join of five such products, each of order 61, making 2^57 the first power of 2 known to beat Thue–Morse by 4; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "A join of five products of examples above and Thue–Morse, each of order 61; the powers-of-2 chart above lists them. That beats Thue–Morse by 4. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>67</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {72, …, 83}</span></p>\n      <!-- TODO: says order 72 at 2^67 comes from a join of eight such products, each of order 72, making 2^67 the first power of 2 known to beat Thue–Morse by 5; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "A join of eight products of examples above and Thue–Morse, each of order 72; the powers-of-2 chart above lists them. That beats Thue–Morse by 5. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n',
     '    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>18</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {19, …, 22}</span></p>\n      <!-- TODO: says order 19 at 2^18 comes from a join of two products of the examples above (p320 # p560, and p48 # p432 # tau_2; lengths and orders spelled out), making 2^18 the least power of 2 known to beat Thue–Morse, where f first did at 2^24; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>18</sup> = 320·560 + 48·432·2<sup>2</sup></span>: a join of two products of examples above (of orders 9, 10, 6 and 11) and Thue–Morse, each of order 19. That beats Thue–Morse by 1 at a lower power of 2 than <i>f</i> does at 2<sup>24</sup>. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>24</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {25, …, 29}</span></p>\n      <p>Claude: "Joint construction: <span class="nw">2<sup>24</sup> = 320<sup>2</sup>·112 + 432·48·2<sup>8</sup></span>, that is, <span class="nw"><i>f</i> = (<i>p</i><sub>320</sub> # <i>p</i><sub>320</sub> # <i>p</i><sub>112</sub>)</span> <span class="nw">∨ (<i>p</i><sub>432</sub> # <i>p</i><sub>48</sub> # τ<sub>8</sub>)</span>. Hence <span class="nw"><i>m</i><sup>*</sup>(2<sup><i>k</i></sup>) ≥ <i>k</i> + 1</span> for every <span class="nw"><i>k</i> ≥ 24</span>, and by the 2<sup>18</sup> entry above for every <span class="nw"><i>k</i> ≥ 18</span>."</p>\n      <!-- TODO: says the upper bound 29 at 2^24 is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n      <p class="code">\n        <span><i>p</i><sub>112</sub> <span class="nw">(<i>m</i> = 7)</span> and <i>p</i><sub>48</sub> <span class="nw">(<i>m</i> = 6)</span>, from the paper\'s Table 5:</span>\n        <code>A5994DB29B45A0</code>\n        <code>C27D8C</code>\n      </p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>33</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {35, …, 41}</span></p>\n      <!-- TODO: says order 35 at 2^33 comes from a join of three products of the examples above and Thue–Morse (lengths and orders spelled out), making 2^33 the first power of 2 known to beat Thue–Morse by 2, where f # f first did at 2^48; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>33</sup> = 208·320<sup>3</sup> + 336<sup>3</sup>·2<sup>5</sup> + 304·480<sup>2</sup>·2<sup>3</sup></span>: a join of three products of examples above (of orders 8, 9, 10, 8 and 12) and Thue–Morse, each of order 35. That beats Thue–Morse by 2 at a lower power of 2 than <span class="nw"><i>f</i> # <i>f</i></span> does at 2<sup>48</sup>. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>41</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {44, …, 51}</span></p>\n      <!-- TODO: says order 44 at 2^41 comes from a join of five products of the examples above and Thue–Morse, each of order 44, making 2^41 the first power of 2 known to beat Thue–Morse by 3; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of five products of examples above and Thue–Morse, each of order 44; the powers-of-2 chart above lists them. That beats Thue–Morse by 3. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>48</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {52, …, 59}</span></p>\n      <!-- TODO: says order 52 at 2^48 comes from a join of six products of the examples above and Thue–Morse, each of order 52, making 2^48 the first power of 2 known to beat Thue–Morse by 4; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of six products of examples above and Thue–Morse, each of order 52; the powers-of-2 chart above lists them. That beats Thue–Morse by 4. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>49</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {53, …, 61}</span></p>\n      <!-- TODO: says order 53 at 2^49 comes from the join of the 2^48 entry with each product times tau_1, which beats Thue–Morse by 4; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The join of the 2<sup>48</sup> entry, each product times τ<sub>1</sub>, has order 53. That beats Thue–Morse by 4. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {55, …, 63}</span></p>\n      <p>With <i>f</i> the 2<sup>24</sup> construction above, <span class="nw"><i>f</i> # <i>f</i> # τ<sub>3</sub></span> has order <span class="nw">25 + 25 + 3 = 53</span>. The paper\'s 52 is Stong\'s.</p>\n      <!-- TODO: says the six products of the 2^48 entry, each times tau_3, give order 55 at 2^51; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The six products of the 2<sup>48</sup> entry, each times τ<sub>3</sub>, give order 55. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>57</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {61, …, 71}</span></p>\n      <!-- TODO: says order 61 at 2^57 comes from the join of the 2^48 entry with each product times tau_9, which beats Thue–Morse by 4; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The join of the 2<sup>48</sup> entry, each product times τ<sub>9</sub>, has order 61. That beats Thue–Morse by 4. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>61</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {66, …, 76}</span></p>\n      <!-- TODO: says order 66 at 2^61 comes from a join of eleven products of the examples above and Thue–Morse, each of order 66, making 2^61 the first power of 2 known to beat Thue–Morse by 5; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of eleven products of examples above and Thue–Morse, each of order 66; the powers-of-2 chart above lists them. That beats Thue–Morse by 5. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>67</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {72, …, 83}</span></p>\n      <!-- TODO: says order 72 at 2^67 comes from the join of the 2^61 entry with each product times tau_6, which beats Thue–Morse by 5; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The join of the 2<sup>61</sup> entry, each product times τ<sub>6</sub>, has order 72. That beats Thue–Morse by 5. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>71</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {77, …, 88}</span></p>\n      <!-- TODO: says order 77 at 2^71 comes from a join of six products of the examples above and Thue–Morse, each of order 77, making 2^71 the first power of 2 known to beat Thue–Morse by 6; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of six products of examples above and Thue–Morse, each of order 77; the powers-of-2 chart above lists them. That beats Thue–Morse by 6. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n', 1),
    # the m*(n) chart's colors: a clearer green, a rose red (dreeves, 2026-10-12)
    ("  /* The m*(n) chart's colors, checked with the dataviz palette validator against each mode's surface, all pairs,\n     since any two can touch. Light: worst color-blind pair ΔE 13.4 (protan), worst normal-vision pair 17.8. Dark:\n     worst color-blind pair ΔE 18.1 (deutan), worst normal-vision pair 19.9. Its other checks fail by design: exists\n     and impossible sit far apart in lightness, outside its band (which also keeps exists clear of --joint); open is\n     a gray, and impossible, most of the chart, is muted (in light mode about as much chroma as sRGB allows at its\n     lightness), so both are below its chroma floor and below 3:1 against the light surface, impossible in dark too;\n     the readout states each cell's bounds in words. */\n", "  /* The m*(n) chart's colors, checked with the dataviz palette validator against each mode's surface, all pairs,\n     since any two can touch. Light: worst color-blind pair ΔE 13.4 (protan), worst normal-vision pair 17.5. Dark:\n     worst color-blind pair ΔE 17.6 (deutan), worst normal-vision pair 20.7. Its other checks fail by design: exists\n     and impossible sit far apart in lightness, outside its band; open is a gray, and impossible, most of the chart,\n     is muted, so both are below its chroma floor and below 3:1 against the light surface, impossible in dark too; the\n     readout states each cell's bounds in words. Exists is a clear green and impossible a rose, away from the table's\n     orange (dreeves, 2026-10-12). */\n", 1),
    ('  --exists: #2e5d1b;\n', '  --exists: #21771a;\n', 1),
    ('  --impossible: #fcc0ba;\n', '  --impossible: #f7bfd3;\n', 1),
    ('\n    --exists: #89cc7b;\n', '\n    --exists: #6cd362;\n', 1),
    ('\n    --impossible: #5a2522;\n', '\n    --impossible: #5d1c3a;\n', 1),
    ('\n  --exists: #89cc7b;\n', '\n  --exists: #6cd362;\n', 1),
    ('\n  --impossible: #5a2522;\n', '\n  --impossible: #5d1c3a;\n', 1),
    # the chart's green, the old Claude-and-BGPW one; the powers' remarks with their bounds mod 3 (2026-10-12)
    ("  /* The m*(n) chart's colors, checked with the dataviz palette validator against each mode's surface, all pairs,\n     since any two can touch. Light: worst color-blind pair ΔE 13.4 (protan), worst normal-vision pair 17.5. Dark:\n     worst color-blind pair ΔE 17.6 (deutan), worst normal-vision pair 20.7. Its other checks fail by design: exists\n     and impossible sit far apart in lightness, outside its band; open is a gray, and impossible, most of the chart,\n     is muted, so both are below its chroma floor and below 3:1 against the light surface, impossible in dark too; the\n     readout states each cell's bounds in words. Exists is a clear green and impossible a rose, away from the table's\n     orange (dreeves, 2026-10-12). */\n", "  /* The m*(n) chart's colors, checked with the dataviz palette validator against each mode's surface, all pairs,\n     since any two can touch. Light: worst color-blind pair ΔE 9.9 (protan), worst normal-vision pair 16.1. Dark:\n     worst color-blind pair ΔE 11.9 (deutan), worst normal-vision pair 16.9. Its other checks fail by design: exists\n     and impossible sit far apart in lightness, outside its band; open is a gray, and impossible, most of the chart,\n     is muted, so both are below its chroma floor and below 3:1 against the light surface, impossible in dark too; the\n     readout states each cell's bounds in words. Exists is the green the table used for Claude and BGPW, and\n     impossible a rose, away from the table's orange (dreeves, 2026-10-12). */\n", 1),
    ('  --exists: #21771a;\n', '  --exists: #2a9466;\n', 1),
    ('\n    --exists: #6cd362;\n', '\n    --exists: #2aa070;\n', 1),
    ('\n  --exists: #6cd362;\n', '\n  --exists: #2aa070;\n', 1),
    ('    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>18</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {19, …, 22}</span></p>\n      <!-- TODO: says order 19 at 2^18 comes from a join of two products of the examples above (p320 # p560, and p48 # p432 # tau_2; lengths and orders spelled out), making 2^18 the least power of 2 known to beat Thue–Morse, where f first did at 2^24; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>18</sup> = 320·560 + 48·432·2<sup>2</sup></span>: a join of two products of examples above (of orders 9, 10, 6 and 11) and Thue–Morse, each of order 19. That beats Thue–Morse by 1 at a lower power of 2 than <i>f</i> does at 2<sup>24</sup>. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>24</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {25, …, 29}</span></p>\n      <p>Claude: "Joint construction: <span class="nw">2<sup>24</sup> = 320<sup>2</sup>·112 + 432·48·2<sup>8</sup></span>, that is, <span class="nw"><i>f</i> = (<i>p</i><sub>320</sub> # <i>p</i><sub>320</sub> # <i>p</i><sub>112</sub>)</span> <span class="nw">∨ (<i>p</i><sub>432</sub> # <i>p</i><sub>48</sub> # τ<sub>8</sub>)</span>. Hence <span class="nw"><i>m</i><sup>*</sup>(2<sup><i>k</i></sup>) ≥ <i>k</i> + 1</span> for every <span class="nw"><i>k</i> ≥ 24</span>, and by the 2<sup>18</sup> entry above for every <span class="nw"><i>k</i> ≥ 18</span>."</p>\n      <!-- TODO: says the upper bound 29 at 2^24 is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n      <p class="code">\n        <span><i>p</i><sub>112</sub> <span class="nw">(<i>m</i> = 7)</span> and <i>p</i><sub>48</sub> <span class="nw">(<i>m</i> = 6)</span>, from the paper\'s Table 5:</span>\n        <code>A5994DB29B45A0</code>\n        <code>C27D8C</code>\n      </p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>33</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {35, …, 41}</span></p>\n      <!-- TODO: says order 35 at 2^33 comes from a join of three products of the examples above and Thue–Morse (lengths and orders spelled out), making 2^33 the first power of 2 known to beat Thue–Morse by 2, where f # f first did at 2^48; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>33</sup> = 208·320<sup>3</sup> + 336<sup>3</sup>·2<sup>5</sup> + 304·480<sup>2</sup>·2<sup>3</sup></span>: a join of three products of examples above (of orders 8, 9, 10, 8 and 12) and Thue–Morse, each of order 35. That beats Thue–Morse by 2 at a lower power of 2 than <span class="nw"><i>f</i> # <i>f</i></span> does at 2<sup>48</sup>. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>41</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {44, …, 51}</span></p>\n      <!-- TODO: says order 44 at 2^41 comes from a join of five products of the examples above and Thue–Morse, each of order 44, making 2^41 the first power of 2 known to beat Thue–Morse by 3; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of five products of examples above and Thue–Morse, each of order 44; the powers-of-2 chart above lists them. That beats Thue–Morse by 3. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>48</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {52, …, 59}</span></p>\n      <!-- TODO: says order 52 at 2^48 comes from a join of six products of the examples above and Thue–Morse, each of order 52, making 2^48 the first power of 2 known to beat Thue–Morse by 4; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of six products of examples above and Thue–Morse, each of order 52; the powers-of-2 chart above lists them. That beats Thue–Morse by 4. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>49</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {53, …, 61}</span></p>\n      <!-- TODO: says order 53 at 2^49 comes from the join of the 2^48 entry with each product times tau_1, which beats Thue–Morse by 4; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The join of the 2<sup>48</sup> entry, each product times τ<sub>1</sub>, has order 53. That beats Thue–Morse by 4. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {55, …, 63}</span></p>\n      <p>With <i>f</i> the 2<sup>24</sup> construction above, <span class="nw"><i>f</i> # <i>f</i> # τ<sub>3</sub></span> has order <span class="nw">25 + 25 + 3 = 53</span>. The paper\'s 52 is Stong\'s.</p>\n      <!-- TODO: says the six products of the 2^48 entry, each times tau_3, give order 55 at 2^51; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The six products of the 2<sup>48</sup> entry, each times τ<sub>3</sub>, give order 55. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>57</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {61, …, 71}</span></p>\n      <!-- TODO: says order 61 at 2^57 comes from the join of the 2^48 entry with each product times tau_9, which beats Thue–Morse by 4; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The join of the 2<sup>48</sup> entry, each product times τ<sub>9</sub>, has order 61. That beats Thue–Morse by 4. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>61</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {66, …, 76}</span></p>\n      <!-- TODO: says order 66 at 2^61 comes from a join of eleven products of the examples above and Thue–Morse, each of order 66, making 2^61 the first power of 2 known to beat Thue–Morse by 5; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of eleven products of examples above and Thue–Morse, each of order 66; the powers-of-2 chart above lists them. That beats Thue–Morse by 5. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>67</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {72, …, 83}</span></p>\n      <!-- TODO: says order 72 at 2^67 comes from the join of the 2^61 entry with each product times tau_6, which beats Thue–Morse by 5; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The join of the 2<sup>61</sup> entry, each product times τ<sub>6</sub>, has order 72. That beats Thue–Morse by 5. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>71</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {77, …, 88}</span></p>\n      <!-- TODO: says order 77 at 2^71 comes from a join of six products of the examples above and Thue–Morse, each of order 77, making 2^71 the first power of 2 known to beat Thue–Morse by 6; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of six products of examples above and Thue–Morse, each of order 77; the powers-of-2 chart above lists them. That beats Thue–Morse by 6. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n', '    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>18</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {19, …, 21}</span></p>\n      <!-- TODO: says order 19 at 2^18 comes from a join of two products of the examples above (p320 # p560, and p48 # p432 # tau_2; lengths and orders spelled out), each of order 19, which beats Thue–Morse by 1 at a lower power of 2 than f does at 2^24; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>18</sup> = 320·560 + 48·432·2<sup>2</sup></span>: a join of two products of examples above (of orders 9, 10, 6 and 11) and Thue–Morse, each of order 19. That beats Thue–Morse by 1 at a lower power of 2 than <i>f</i> does at 2<sup>24</sup>. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>24</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {25, …, 29}</span></p>\n      <p>Claude: "Joint construction: <span class="nw">2<sup>24</sup> = 320<sup>2</sup>·112 + 432·48·2<sup>8</sup></span>, that is, <span class="nw"><i>f</i> = (<i>p</i><sub>320</sub> # <i>p</i><sub>320</sub> # <i>p</i><sub>112</sub>)</span> <span class="nw">∨ (<i>p</i><sub>432</sub> # <i>p</i><sub>48</sub> # τ<sub>8</sub>)</span>. Hence <span class="nw"><i>m</i><sup>*</sup>(2<sup><i>k</i></sup>) ≥ <i>k</i> + 1</span> for every <span class="nw"><i>k</i> ≥ 24</span>, and by the 2<sup>18</sup> entry above for every <span class="nw"><i>k</i> ≥ 18</span>."</p>\n      <!-- TODO: says the upper bound 29 at 2^24 is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n      <p class="code">\n        <span><i>p</i><sub>112</sub> <span class="nw">(<i>m</i> = 7)</span> and <i>p</i><sub>48</sub> <span class="nw">(<i>m</i> = 6)</span>, from the paper\'s Table 5:</span>\n        <code>A5994DB29B45A0</code>\n        <code>C27D8C</code>\n      </p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>33</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {35, …, 40}</span></p>\n      <!-- TODO: says order 35 at 2^33 comes from a join of three products of the examples above and Thue–Morse (lengths and orders spelled out), making 2^33 the first power of 2 known to beat Thue–Morse by 2, where f # f first did at 2^48; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>33</sup> = 208·320<sup>3</sup> + 336<sup>3</sup>·2<sup>5</sup> + 304·480<sup>2</sup>·2<sup>3</sup></span>: a join of three products of examples above (of orders 8, 9, 10, 8 and 12) and Thue–Morse, each of order 35. That beats Thue–Morse by 2 at a lower power of 2 than <span class="nw"><i>f</i> # <i>f</i></span> does at 2<sup>48</sup>. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>41</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {44, …, 50}</span></p>\n      <!-- TODO: says order 44 at 2^41 comes from a join of five products of the examples above and Thue–Morse, each of order at least 44, which beats Thue–Morse by 3; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "A join of five products of examples above and Thue–Morse, each of order at least 44; the powers-of-2 chart above lists them. That beats Thue–Morse by 3. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>48</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {52, …, 59}</span></p>\n      <!-- TODO: says order 52 at 2^48 comes from a join of six products of the examples above and Thue–Morse, each of order 52, which beats Thue–Morse by 4; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of six products of examples above and Thue–Morse, each of order 52; the powers-of-2 chart above lists them. That beats Thue–Morse by 4. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>49</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {53, …, 60}</span></p>\n      <!-- TODO: says order 53 at 2^49 comes from the join of the 2^48 entry with each product times tau_1, which beats Thue–Morse by 4; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "The join of the 2<sup>48</sup> entry, each product times τ<sub>1</sub>, has order 53. That beats Thue–Morse by 4. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {55, …, 63}</span></p>\n      <p>With <i>f</i> the 2<sup>24</sup> construction above, <span class="nw"><i>f</i> # <i>f</i> # τ<sub>3</sub></span> has order <span class="nw">25 + 25 + 3 = 53</span>. The paper\'s 52 is Stong\'s.</p>\n      <!-- TODO: says the six products of the 2^48 entry, each times tau_3, give order 55 at 2^51; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The six products of the 2<sup>48</sup> entry, each times τ<sub>3</sub>, give order 55. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>57</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {61, …, 70}</span></p>\n      <!-- TODO: says order 61 at 2^57 comes from the join of the 2^48 entry with each product times tau_9, which beats Thue–Morse by 4; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "The join of the 2<sup>48</sup> entry, each product times τ<sub>9</sub>, has order 61. That beats Thue–Morse by 4. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>61</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {66, …, 75}</span></p>\n      <!-- TODO: says order 66 at 2^61 comes from a join of eleven products of the examples above and Thue–Morse, each of order at least 66, which beats Thue–Morse by 5; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "A join of eleven products of examples above and Thue–Morse, each of order at least 66; the powers-of-2 chart above lists them. That beats Thue–Morse by 5. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>67</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {72, …, 83}</span></p>\n      <!-- TODO: says order 72 at 2^67 comes from the join of the 2^61 entry with each product times tau_6, which beats Thue–Morse by 5; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The join of the 2<sup>61</sup> entry, each product times τ<sub>6</sub>, has order 72. That beats Thue–Morse by 5. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>71</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {77, …, 88}</span></p>\n      <!-- TODO: says order 77 at 2^71 comes from a join of six products of the examples above and Thue–Morse, each of order 77, which beats Thue–Morse by 6; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of six products of examples above and Thue–Morse, each of order 77; the powers-of-2 chart above lists them. That beats Thue–Morse by 6. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n', 1),
    # the chart's colors: black for open, a bright green, a brighter red (dreeves, 2026-10-12),
    ("  /* The m*(n) chart's colors, checked with the dataviz palette validator against each mode's surface, all pairs,\n     since any two can touch. Light: worst color-blind pair ΔE 9.9 (protan), worst normal-vision pair 16.1. Dark:\n     worst color-blind pair ΔE 11.9 (deutan), worst normal-vision pair 16.9. Its other checks fail by design: exists\n     and impossible sit far apart in lightness, outside its band; open is a gray, and impossible, most of the chart,\n     is muted, so both are below its chroma floor and below 3:1 against the light surface, impossible in dark too; the\n     readout states each cell's bounds in words. Exists is the green the table used for Claude and BGPW, and\n     impossible a rose, away from the table's orange (dreeves, 2026-10-12). */\n", "  /* The m*(n) chart's colors (dreeves, 2026-10-12: black for open, a bright green against it, and a brighter red, its\n     hue at least 30 degrees from the table's orange), checked with the dataviz palette validator's arithmetic against\n     each mode's surface, all pairs, since any two can touch. Light: worst color-blind pair ΔE 25.4 (deutan), worst\n     normal-vision pair 46.6. Dark: worst color-blind pair ΔE 24.7 (deutan), worst normal-vision pair 45.6. The\n     readout states each cell's bounds in words. */\n", 1),
    ('\n  --exists: #2a9466;\n', '\n  --exists: #4ade80;\n', 1),
    ('\n  --open: #9b9ea6;\n', '\n  --open: #000000;\n', 1),
    ('\n  --impossible: #f7bfd3;\n', '\n  --impossible: #c90065;\n', 1),
    ('\n    --exists: #2aa070;\n', '\n    --exists: #4ade80;\n', 1),
    ('\n  --exists: #2aa070;\n', '\n  --exists: #4ade80;\n', 1),
    ('\n    --open: #656970;\n', '\n    --open: #000000;\n', 1),
    ('\n  --open: #656970;\n', '\n  --open: #000000;\n', 1),
    ('\n    --impossible: #5d1c3a;\n', '\n    --impossible: #cc0351;\n', 1),
    ('\n  --impossible: #5d1c3a;\n', '\n  --impossible: #cc0351;\n', 1),
    # no dark mode; the chart's colors Astra's crimson, charcoal and jade, tagged TODOCOLOR (dreeves, 2026-10-12),
    ('\n    --exists: #4ade80;\n    --open: #000000;\n    --impossible: #cc0351;\n', '\n', 1),
    ('\n  --exists: #4ade80;\n  --open: #000000;\n  --impossible: #cc0351;\n', '\n', 1),
    ("  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => draw());\n", '', 1),
    ("  /* The m*(n) chart's colors (dreeves, 2026-10-12: black for open, a bright green against it, and a brighter red, its\n     hue at least 30 degrees from the table's orange), checked with the dataviz palette validator's arithmetic against\n     each mode's surface, all pairs, since any two can touch. Light: worst color-blind pair ΔE 25.4 (deutan), worst\n     normal-vision pair 46.6. Dark: worst color-blind pair ΔE 24.7 (deutan), worst normal-vision pair 45.6. The\n     readout states each cell's bounds in words. */\n", "  /* The m*(n) chart's colors, Astra's crimson, charcoal and jade, as dreeves chose them (2026-10-12), with the\n     dataviz palette validator's arithmetic against the page's surface, all pairs, since any two can touch. Light:\n     worst color-blind pair ΔE 6.0 (deutan), worst normal-vision pair 29.0. The readout states each cell's bounds in\n     words. */\n", 1),
    ('\n  --exists: #4ade80;\n  --open: #000000;\n  --impossible: #c90065;\n', '\n  --exists: #249e70; /* TODOCOLOR */\n  --open: #24292e; /* TODOCOLOR */\n  --impossible: #c43d50; /* TODOCOLOR */\n', 1),
    # the 2^18 remark writes out its construction and links certificate_2^18.wl (dreeves, 2026-10-12),
    ('      <!-- TODO: says order 19 at 2^18 comes from a join of two products of the examples above (p320 # p560, and p48 # p432 # tau_2; lengths and orders spelled out), each of order 19, which beats Thue–Morse by 1 at a lower power of 2 than f does at 2^24; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>18</sup> = 320·560 + 48·432·2<sup>2</sup></span>: a join of two products of examples above (of orders 9, 10, 6 and 11) and Thue–Morse, each of order 19. That beats Thue–Morse by 1 at a lower power of 2 than <i>f</i> does at 2<sup>24</sup>. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n', '      <!-- TODO: says 2^18 = 320·560 + 48·432·2^2, that is, (p320 # p560) ∨ (p48 # p432 # tau_2), a join of two products each of order 9 + 10 = 6 + 11 + 2 = 19, the code of p48 (the paper\'s) being with the 2^24 entry below; that this beats Thue–Morse by 1 at a lower power of 2 than f does at 2^24; that a linked Mathematica script builds one half of the partition, all 2^17 of its numbers, and checks its power sums exactly; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>18</sup> = 320·560 + 48·432·2<sup>2</sup></span>, that is, <span class="nw">(<i>p</i><sub>320</sub> # <i>p</i><sub>560</sub>)</span> <span class="nw">∨ (<i>p</i><sub>48</sub> # <i>p</i><sub>432</sub> # τ<sub>2</sub>)</span>, a join of two products each of order <span class="nw">9 + 10 = 6 + 11 + 2 = 19</span> (the code of <i>p</i><sub>48</sub>, the paper\'s, is with the 2<sup>24</sup> entry below). That beats Thue–Morse by 1 at a lower power of 2 than <i>f</i> does at 2<sup>24</sup>. The Mathematica script <a href="https://raw.githubusercontent.com/dreeves/equipow/main/certificate_2%5E18.wl">certificate_2^18.wl</a> builds one half of the partition, all 2<sup>17</sup> of its numbers, and checks its power sums exactly. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n', 1),
    # the comment above the chart's colors, which are dreeves's to tweak (2026-10-12),
    ("  /* The m*(n) chart's colors, Astra's crimson, charcoal and jade, as dreeves chose them (2026-10-12), with the\n     dataviz palette validator's arithmetic against the page's surface, all pairs, since any two can touch. Light:\n     worst color-blind pair ΔE 6.0 (deutan), worst normal-vision pair 29.0. The readout states each cell's bounds in\n     words. */\n", "  /* The m*(n) chart's colors, dreeves's to tweak (2026-10-12); the readout states each cell's bounds in words. */\n", 1),
    # the 2^18 remark: the certificate builds the half that contains 0 (dreeves, 2026-10-13),
    ('      <!-- TODO: says 2^18 = 320·560 + 48·432·2^2, that is, (p320 # p560) ∨ (p48 # p432 # tau_2), a join of two products each of order 9 + 10 = 6 + 11 + 2 = 19, the code of p48 (the paper\'s) being with the 2^24 entry below; that this beats Thue–Morse by 1 at a lower power of 2 than f does at 2^24; that a linked Mathematica script builds one half of the partition, all 2^17 of its numbers, and checks its power sums exactly; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>18</sup> = 320·560 + 48·432·2<sup>2</sup></span>, that is, <span class="nw">(<i>p</i><sub>320</sub> # <i>p</i><sub>560</sub>)</span> <span class="nw">∨ (<i>p</i><sub>48</sub> # <i>p</i><sub>432</sub> # τ<sub>2</sub>)</span>, a join of two products each of order <span class="nw">9 + 10 = 6 + 11 + 2 = 19</span> (the code of <i>p</i><sub>48</sub>, the paper\'s, is with the 2<sup>24</sup> entry below). That beats Thue–Morse by 1 at a lower power of 2 than <i>f</i> does at 2<sup>24</sup>. The Mathematica script <a href="https://raw.githubusercontent.com/dreeves/equipow/main/certificate_2%5E18.wl">certificate_2^18.wl</a> builds one half of the partition, all 2<sup>17</sup> of its numbers, and checks its power sums exactly. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n', '      <!-- TODO: says 2^18 = 320·560 + 48·432·2^2, that is, (p320 # p560) ∨ (p48 # p432 # tau_2), a join of two products each of order 9 + 10 = 6 + 11 + 2 = 19, the code of p48 (the paper\'s) being with the 2^24 entry below; that this beats Thue–Morse by 1 at a lower power of 2 than f does at 2^24; that a linked Mathematica script builds the half of the partition that contains 0, all 2^17 of its numbers, and checks its power sums exactly; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>18</sup> = 320·560 + 48·432·2<sup>2</sup></span>, that is, <span class="nw">(<i>p</i><sub>320</sub> # <i>p</i><sub>560</sub>)</span> <span class="nw">∨ (<i>p</i><sub>48</sub> # <i>p</i><sub>432</sub> # τ<sub>2</sub>)</span>, a join of two products each of order <span class="nw">9 + 10 = 6 + 11 + 2 = 19</span> (the code of <i>p</i><sub>48</sub>, the paper\'s, is with the 2<sup>24</sup> entry below). That beats Thue–Morse by 1 at a lower power of 2 than <i>f</i> does at 2<sup>24</sup>. The Mathematica script <a href="https://raw.githubusercontent.com/dreeves/equipow/main/certificate_2%5E18.wl">certificate_2^18.wl</a> builds the half of the partition that contains 0, all 2<sup>17</sup> of its numbers, and checks its power sums exactly. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n', 1),
    # Claude's account of its lattice search, at Stan Wagon's request: its section's CSS (2026-10-14)
    after('.sets pre code { display: block; }', '',
          "/* Claude's account of its lattice search, at Stan Wagon's request (2026-10-14): one block quote, ruled in Claude's hue */",
          '.lattice { display: grid; grid-template-columns: minmax(0, 1fr); max-width: 46rem; }',
          '.lattice blockquote { margin: 0; padding-left: 1.1rem; border-left: 3px solid var(--claude); display: grid; grid-template-columns: minmax(0, 1fr); gap: 1rem; }',
          '.lattice ul { margin: 0; padding-left: 1.2rem; display: grid; gap: 0.6rem; }',
          '.lattice .attrib { color: var(--muted); }'),
    # the powers' remarks once 800 reached order 11 (2026-10-17): 2^17, 2^27, 2^34, 2^38, 2^46, 2^52 and 2^66
    # added; Claude's sentences at 2^41 to 2^71 rewritten for the joins the chart now gives there; 2^24's last
    # clause citing the 2^17 entry; 2^18 and 2^33 unchanged but for 2^33's TODO (2^24's TODO, an insertion here, is
    # left out of both sides)
    ('    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>18</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {19, …, 21}</span></p>\n      <!-- TODO: says 2^18 = 320·560 + 48·432·2^2, that is, (p320 # p560) ∨ (p48 # p432 # tau_2), a join of two products each of order 9 + 10 = 6 + 11 + 2 = 19, the code of p48 (the paper\'s) being with the 2^24 entry below; that this beats Thue–Morse by 1 at a lower power of 2 than f does at 2^24; that a linked Mathematica script builds the half of the partition that contains 0, all 2^17 of its numbers, and checks its power sums exactly; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>18</sup> = 320·560 + 48·432·2<sup>2</sup></span>, that is, <span class="nw">(<i>p</i><sub>320</sub> # <i>p</i><sub>560</sub>)</span> <span class="nw">∨ (<i>p</i><sub>48</sub> # <i>p</i><sub>432</sub> # τ<sub>2</sub>)</span>, a join of two products each of order <span class="nw">9 + 10 = 6 + 11 + 2 = 19</span> (the code of <i>p</i><sub>48</sub>, the paper\'s, is with the 2<sup>24</sup> entry below). That beats Thue–Morse by 1 at a lower power of 2 than <i>f</i> does at 2<sup>24</sup>. The Mathematica script <a href="https://raw.githubusercontent.com/dreeves/equipow/main/certificate_2%5E18.wl">certificate_2^18.wl</a> builds the half of the partition that contains 0, all 2<sup>17</sup> of its numbers, and checks its power sums exactly. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>24</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {25, …, 29}</span></p>\n      <p>Claude: "Joint construction: <span class="nw">2<sup>24</sup> = 320<sup>2</sup>·112 + 432·48·2<sup>8</sup></span>, that is, <span class="nw"><i>f</i> = (<i>p</i><sub>320</sub> # <i>p</i><sub>320</sub> # <i>p</i><sub>112</sub>)</span> <span class="nw">∨ (<i>p</i><sub>432</sub> # <i>p</i><sub>48</sub> # τ<sub>8</sub>)</span>. Hence <span class="nw"><i>m</i><sup>*</sup>(2<sup><i>k</i></sup>) ≥ <i>k</i> + 1</span> for every <span class="nw"><i>k</i> ≥ 24</span>, and by the 2<sup>18</sup> entry above for every <span class="nw"><i>k</i> ≥ 18</span>."</p>\n      <!-- TODO: says the upper bound 29 at 2^24 is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n      <p class="code">\n        <span><i>p</i><sub>112</sub> <span class="nw">(<i>m</i> = 7)</span> and <i>p</i><sub>48</sub> <span class="nw">(<i>m</i> = 6)</span>, from the paper\'s Table 5:</span>\n        <code>A5994DB29B45A0</code>\n        <code>C27D8C</code>\n      </p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>33</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {35, …, 40}</span></p>\n      <!-- TODO: says order 35 at 2^33 comes from a join of three products of the examples above and Thue–Morse (lengths and orders spelled out), making 2^33 the first power of 2 known to beat Thue–Morse by 2, where f # f first did at 2^48; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>33</sup> = 208·320<sup>3</sup> + 336<sup>3</sup>·2<sup>5</sup> + 304·480<sup>2</sup>·2<sup>3</sup></span>: a join of three products of examples above (of orders 8, 9, 10, 8 and 12) and Thue–Morse, each of order 35. That beats Thue–Morse by 2 at a lower power of 2 than <span class="nw"><i>f</i> # <i>f</i></span> does at 2<sup>48</sup>. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>41</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {44, …, 50}</span></p>\n      <!-- TODO: says order 44 at 2^41 comes from a join of five products of the examples above and Thue–Morse, each of order at least 44, which beats Thue–Morse by 3; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "A join of five products of examples above and Thue–Morse, each of order at least 44; the powers-of-2 chart above lists them. That beats Thue–Morse by 3. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>48</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {52, …, 59}</span></p>\n      <!-- TODO: says order 52 at 2^48 comes from a join of six products of the examples above and Thue–Morse, each of order 52, which beats Thue–Morse by 4; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of six products of examples above and Thue–Morse, each of order 52; the powers-of-2 chart above lists them. That beats Thue–Morse by 4. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>49</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {53, …, 60}</span></p>\n      <!-- TODO: says order 53 at 2^49 comes from the join of the 2^48 entry with each product times tau_1, which beats Thue–Morse by 4; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "The join of the 2<sup>48</sup> entry, each product times τ<sub>1</sub>, has order 53. That beats Thue–Morse by 4. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {55, …, 63}</span></p>\n      <p>With <i>f</i> the 2<sup>24</sup> construction above, <span class="nw"><i>f</i> # <i>f</i> # τ<sub>3</sub></span> has order <span class="nw">25 + 25 + 3 = 53</span>. The paper\'s 52 is Stong\'s.</p>\n      <!-- TODO: says the six products of the 2^48 entry, each times tau_3, give order 55 at 2^51; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The six products of the 2<sup>48</sup> entry, each times τ<sub>3</sub>, give order 55. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>57</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {61, …, 70}</span></p>\n      <!-- TODO: says order 61 at 2^57 comes from the join of the 2^48 entry with each product times tau_9, which beats Thue–Morse by 4; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "The join of the 2<sup>48</sup> entry, each product times τ<sub>9</sub>, has order 61. That beats Thue–Morse by 4. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>61</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {66, …, 75}</span></p>\n      <!-- TODO: says order 66 at 2^61 comes from a join of eleven products of the examples above and Thue–Morse, each of order at least 66, which beats Thue–Morse by 5; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "A join of eleven products of examples above and Thue–Morse, each of order at least 66; the powers-of-2 chart above lists them. That beats Thue–Morse by 5. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>67</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {72, …, 83}</span></p>\n      <!-- TODO: says order 72 at 2^67 comes from the join of the 2^61 entry with each product times tau_6, which beats Thue–Morse by 5; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The join of the 2<sup>61</sup> entry, each product times τ<sub>6</sub>, has order 72. That beats Thue–Morse by 5. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>71</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {77, …, 88}</span></p>\n      <!-- TODO: says order 77 at 2^71 comes from a join of six products of the examples above and Thue–Morse, each of order 77, which beats Thue–Morse by 6; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of six products of examples above and Thue–Morse, each of order 77; the powers-of-2 chart above lists them. That beats Thue–Morse by 6. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n', '    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>17</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {18, …, 20}</span></p>\n      <!-- TODO: says 2^17 = 112·800 + 48·432·2, that is, (p112 # p800) ∨ (p48 # p432 # tau_1), a join of two products each of order 7 + 11 = 6 + 11 + 1 = 18, the codes of p112 and p48 (the paper\'s) being with the 2^24 entry below; that this beats Thue–Morse by 1 at a lower power of 2 than the 2^18 entry below; that a linked Mathematica script builds the half of the partition that contains 0, all 2^16 of its numbers, and checks its power sums exactly; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>17</sup> = 112·800 + 48·432·2</span>, that is, <span class="nw">(<i>p</i><sub>112</sub> # <i>p</i><sub>800</sub>)</span> <span class="nw">∨ (<i>p</i><sub>48</sub> # <i>p</i><sub>432</sub> # τ<sub>1</sub>)</span>, a join of two products each of order <span class="nw">7 + 11 = 6 + 11 + 1 = 18</span> (the codes of <i>p</i><sub>112</sub> and <i>p</i><sub>48</sub>, the paper\'s, are with the 2<sup>24</sup> entry below). That beats Thue–Morse by 1 at a lower power of 2 than the 2<sup>18</sup> entry below. The Mathematica script <a href="https://raw.githubusercontent.com/dreeves/equipow/main/certificate_2%5E17.wl">certificate_2^17.wl</a> builds the half of the partition that contains 0, all 2<sup>16</sup> of its numbers, and checks its power sums exactly. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>18</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {19, …, 21}</span></p>\n      <!-- TODO: says 2^18 = 320·560 + 48·432·2^2, that is, (p320 # p560) ∨ (p48 # p432 # tau_2), a join of two products each of order 9 + 10 = 6 + 11 + 2 = 19, the code of p48 (the paper\'s) being with the 2^24 entry below; that this beats Thue–Morse by 1 at a lower power of 2 than f does at 2^24; that a linked Mathematica script builds the half of the partition that contains 0, all 2^17 of its numbers, and checks its power sums exactly; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>18</sup> = 320·560 + 48·432·2<sup>2</sup></span>, that is, <span class="nw">(<i>p</i><sub>320</sub> # <i>p</i><sub>560</sub>)</span> <span class="nw">∨ (<i>p</i><sub>48</sub> # <i>p</i><sub>432</sub> # τ<sub>2</sub>)</span>, a join of two products each of order <span class="nw">9 + 10 = 6 + 11 + 2 = 19</span> (the code of <i>p</i><sub>48</sub>, the paper\'s, is with the 2<sup>24</sup> entry below). That beats Thue–Morse by 1 at a lower power of 2 than <i>f</i> does at 2<sup>24</sup>. The Mathematica script <a href="https://raw.githubusercontent.com/dreeves/equipow/main/certificate_2%5E18.wl">certificate_2^18.wl</a> builds the half of the partition that contains 0, all 2<sup>17</sup> of its numbers, and checks its power sums exactly. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>24</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {25, …, 29}</span></p>\n      <p>Claude: "Joint construction: <span class="nw">2<sup>24</sup> = 320<sup>2</sup>·112 + 432·48·2<sup>8</sup></span>, that is, <span class="nw"><i>f</i> = (<i>p</i><sub>320</sub> # <i>p</i><sub>320</sub> # <i>p</i><sub>112</sub>)</span> <span class="nw">∨ (<i>p</i><sub>432</sub> # <i>p</i><sub>48</sub> # τ<sub>8</sub>)</span>. Hence <span class="nw"><i>m</i><sup>*</sup>(2<sup><i>k</i></sup>) ≥ <i>k</i> + 1</span> for every <span class="nw"><i>k</i> ≥ 24</span>, and by the 2<sup>17</sup> entry above for every <span class="nw"><i>k</i> ≥ 17</span>."</p>\n      <!-- TODO: says the upper bound 29 at 2^24 is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n      <p class="code">\n        <span><i>p</i><sub>112</sub> <span class="nw">(<i>m</i> = 7)</span> and <i>p</i><sub>48</sub> <span class="nw">(<i>m</i> = 6)</span>, from the paper\'s Table 5:</span>\n        <code>A5994DB29B45A0</code>\n        <code>C27D8C</code>\n      </p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>27</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {29, …, 33}</span></p>\n      <!-- TODO: says 2^27 = 368^2·800 + 192^2·432 + 48·432·480, a join of three products of the examples above (their orders listed), each of order 29, which beats Thue–Morse by 2 at a lower power of 2 than the 2^33 entry below; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>27</sup> = 368<sup>2</sup>·800 + 192<sup>2</sup>·432 + 48·432·480</span>: a join of three products of examples above (of orders 9, 11, 9, 11, 6 and 12), each of order 29. That beats Thue–Morse by 2 at a lower power of 2 than the 2<sup>33</sup> entry below. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>33</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {35, …, 40}</span></p>\n      <!-- TODO: says order 35 at 2^33 comes from a join of three products of the examples above and Thue–Morse (lengths and orders spelled out), which beats Thue–Morse by 2 at a lower power of 2 than f # f does at 2^48; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "<span class="nw">2<sup>33</sup> = 208·320<sup>3</sup> + 336<sup>3</sup>·2<sup>5</sup> + 304·480<sup>2</sup>·2<sup>3</sup></span>: a join of three products of examples above (of orders 8, 9, 10, 8 and 12) and Thue–Morse, each of order 35. That beats Thue–Morse by 2 at a lower power of 2 than <span class="nw"><i>f</i> # <i>f</i></span> does at 2<sup>48</sup>. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>34</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {37, …, 41}</span></p>\n      <!-- TODO: says order 37 at 2^34 comes from a join of four products of the examples above and Thue–Morse, each of order 37, which beats Thue–Morse by 3; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "A join of four products of examples above and Thue–Morse, each of order 37; the powers-of-2 chart above lists them. That beats Thue–Morse by 3. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>38</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {42, …, 46}</span></p>\n      <!-- TODO: says order 42 at 2^38 comes from a join of five products of the examples above and Thue–Morse, each of order at least 42, which beats Thue–Morse by 4; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "A join of five products of examples above and Thue–Morse, each of order at least 42; the powers-of-2 chart above lists them. That beats Thue–Morse by 4. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>41</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {45, …, 50}</span></p>\n      <!-- TODO: says order 45 at 2^41 comes from the join of the 2^38 entry with each product times tau_3, which beats Thue–Morse by 4; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "The join of the 2<sup>38</sup> entry, each product times τ<sub>3</sub>, has order 45. That beats Thue–Morse by 4. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>46</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {51, …, 57}</span></p>\n      <!-- TODO: says order 51 at 2^46 comes from a join of seven products of the examples above and Thue–Morse, each of order at least 51, which beats Thue–Morse by 5; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of seven products of examples above and Thue–Morse, each of order at least 51; the powers-of-2 chart above lists them. That beats Thue–Morse by 5. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>48</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {53, …, 59}</span></p>\n      <!-- TODO: says order 53 at 2^48 comes from the join of the 2^46 entry with each product times tau_2, which beats Thue–Morse by 5; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The join of the 2<sup>46</sup> entry, each product times τ<sub>2</sub>, has order 53. That beats Thue–Morse by 5. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>49</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {54, …, 60}</span></p>\n      <!-- TODO: says order 54 at 2^49 comes from the join of the 2^46 entry with each product times tau_3, which beats Thue–Morse by 5; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "The join of the 2<sup>46</sup> entry, each product times τ<sub>3</sub>, has order 54. That beats Thue–Morse by 5. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {56, …, 63}</span></p>\n      <p>With <i>f</i> the 2<sup>24</sup> construction above, <span class="nw"><i>f</i> # <i>f</i> # τ<sub>3</sub></span> has order <span class="nw">25 + 25 + 3 = 53</span>. The paper\'s 52 is Stong\'s.</p>\n      <!-- TODO: says the seven products of the 2^46 entry, each times tau_5, give order 56 at 2^51; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The seven products of the 2<sup>46</sup> entry, each times τ<sub>5</sub>, give order 56. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>52</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {58, …, 64}</span></p>\n      <!-- TODO: says order 58 at 2^52 comes from a join of ten products of the examples above and Thue–Morse, each of order at least 58, which beats Thue–Morse by 6; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of ten products of examples above and Thue–Morse, each of order at least 58; the powers-of-2 chart above lists them. That beats Thue–Morse by 6. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>57</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {64, …, 70}</span></p>\n      <!-- TODO: says order 64 at 2^57 comes from a join of eight products of the examples above and Thue–Morse, each of order at least 64, which beats Thue–Morse by 7; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "A join of eight products of examples above and Thue–Morse, each of order at least 64; the powers-of-2 chart above lists them. That beats Thue–Morse by 7. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>61</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {68, …, 75}</span></p>\n      <!-- TODO: says order 68 at 2^61 comes from the join of the 2^57 entry with each product times tau_4, which beats Thue–Morse by 7; and that the upper bound is the residue condition mod 3 -->\n      <p>Claude: "The join of the 2<sup>57</sup> entry, each product times τ<sub>4</sub>, has order 68. That beats Thue–Morse by 7. The upper bound is the residue condition mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>66</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {74, …, 82}</span></p>\n      <!-- TODO: says order 74 at 2^66 comes from a join of five products of the examples above and Thue–Morse, each of order 74, which beats Thue–Morse by 8; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "A join of five products of examples above and Thue–Morse, each of order 74; the powers-of-2 chart above lists them. That beats Thue–Morse by 8. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>67</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {75, …, 83}</span></p>\n      <!-- TODO: says order 75 at 2^67 comes from the join of the 2^66 entry with each product times tau_1, which beats Thue–Morse by 8; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The join of the 2<sup>66</sup> entry, each product times τ<sub>1</sub>, has order 75. That beats Thue–Morse by 8. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 2<sup>71</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {79, …, 88}</span></p>\n      <!-- TODO: says order 79 at 2^71 comes from the join of the 2^66 entry with each product times tau_5, which beats Thue–Morse by 8; and that the upper bound is the norm bound for the residue sums mod 3 -->\n      <p>Claude: "The join of the 2<sup>66</sup> entry, each product times τ<sub>5</sub>, has order 79. That beats Thue–Morse by 8. The upper bound is the norm bound for the residue sums mod 3, as in the powers-of-2 chart above."</p>\n    </li>\n', 1))


def committed():
    """index.html as it would be without this chart: as it was at BASE, with EDITS made (each count asserted)."""
    text = subprocess.run(['git', '-C', HERE, 'show', f'{BASE}:index.html'], capture_output=True, text=True,
                          check=True).stdout
    for old, new, count in EDITS:
        assert text.count(old) == count, (old, text.count(old))
        text = text.replace(old, new)
    return text


def opcodes():
    """difflib's line opcodes from index.html without this chart (BASE with EDITS made) to the working one, the chart's
    three color lines compared by name only: their values and comments are dreeves's to tweak (2026-10-12)."""
    mask = lambda text: re.sub(r'^(\s*--(?:exists|open|impossible):).*$', r'\1', text, flags=re.M).splitlines()
    return difflib.SequenceMatcher(None, mask(committed()), mask(page()), autojunk=False).get_opcodes()


def regions(lines):
    """For each line: 'style' or 'script' for the lines inside a <style> or an inline <script> element, 'html' for the
    rest (the tag lines included)."""
    out, state = [], 'html'
    for line in lines:
        s = line.strip()
        if state == 'html' and s in ('<style>', '<script>'):
            out.append('html'); state = s[1:-1]; continue
        if state != 'html' and s == f'</{state}>':
            out.append('html'); state = 'html'; continue
        out.append(state)
    assert state == 'html'
    return out


def inserted():
    """The working index.html's lines, their regions, and the indices of the lines inserted: this chart's."""
    lines = page().splitlines()
    return lines, regions(lines), [j for tag, _, _, j1, j2 in opcodes() if tag == 'insert' for j in range(j1, j2)]


def scripts():
    """The page's inline scripts, in order: the m*(n) chart's, then this chart's."""
    return re.findall(r'<script>\n(.*?)</script>', page(), re.S)


def theme_blocks():
    """The custom properties of the page's one theme block, :root, as a one-item list (dreeves, 2026-10-12: no dark
    mode, so no other theme block)."""
    css = re.search(r'<style>(.*?)</style>', page(), re.S).group(1)
    ms = list(re.finditer(r'\n:root \{(.*?)\n\s*\}', css, re.S))
    assert len(ms) == 1 and 'prefers-color-scheme' not in page() and 'data-theme' not in page()
    return [dict(re.findall(r'(--[\w-]+):\s*([^;]+);', ms[0].group(1)))]


def pow2_of(js):
    """POW2 as the browser sees it: node runs the text of a pow2.js and prints POW2 as JSON."""
    p = subprocess.run(['node', '-e', js + '\nprocess.stdout.write(JSON.stringify(POW2))'], capture_output=True,
                       text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout)


def real():
    """The text of the real pow2.js."""
    assert os.path.exists(DATA), DATA
    return open(DATA, encoding='utf-8').read()


# ---------------------------------------------------------------------------------------------------------------------
# What the readout writes (the expectations of the readout quals)

def sub(k): return f'_({k})'                  # a subscript, as DRIVER's TEXT writes a <sub>


def block(b):
    """A block of a join's product, as the readout names it: f, τ_j for Thue-Morse [2^j, j], else p_n."""
    n, m = b
    return 'f' if b == F else f'τ{sub(m)}' if n == 2 ** m else f'p{sub(n)}'


def join_text(products): return ' ∨ '.join('(' + ' # '.join(map(block, p)) + ')' for p in products)


def reason_math(k, why):
    """The math that a reason's Claude: "…" must hold: what tells that reason apart, as the readout writes it."""
    kind, *args = why
    mstar = {'two': lambda: str(2 ** k), 'norm': lambda p: f'p\xa0=\xa0{p}', 'residue': lambda M: f'mod {M}',
             'table2': lambda: 'Table 2', 'page': lambda who: f'({who})'}
    return {'thue-morse': lambda: f'τ{sub(k)}', 'power': lambda L, j: 'f # ' * L + f'τ{sub(j)}',
            'joins': join_text, 'mstar': lambda w: mstar[w[0]](*w[1:]), 'norm': lambda p: f'p\xa0=\xa0{p}',
            'residue': lambda chain: 'mod ' + ', '.join(map(str, chain))}[kind](*args)


# A readout's text, each <sup> written ^(…) and each <sub> _(…): the cell, its meaning, the column's bounds, then the
# reasons.
READOUT = re.compile(r'k = (\d+), n = 2\^\((\d+)\), m = (\d+) \+ (\d+) = (\d+) · (known|open|impossible) · '
                     r'(\d+) ≤ m\^\(\*\)\(2\^\((\d+)\)\) ≤ (\d+) · (.*)')


def kind_of(col, k, e): return (k + e > col[0]) + (k + e > col[1])     # 0 exists, 1 open, 2 impossible
MEANINGS = ('known', 'open', 'impossible')    # each kind's word in the readout, dreeves's (approved 2026-10-12)


def check_readouts(data, reads):
    """Assert that reads, [k, e, {text, children}] for every cell, are each that cell's readout (see
    q_hover_reads_out_every_cell)."""
    E, cols, meaning = data['etop'], data['cols'], {}
    assert sorted((k, e) for k, e, _ in reads) == [(k, e) for k in range(1, K + 1) for e in range(1, E + 1)]
    for k, e, r in reads:
        lo, hi, lw, hw = cols[k - 1]
        kind = kind_of(cols[k - 1], k, e)
        g = READOUT.fullmatch(r['text'])
        assert g and [int(g[i]) for i in (1, 2, 3, 4, 5, 7, 8, 9)] == [k, k, k, e, k + e, lo, k, hi], (k, e, r)
        assert r['children'][:1] == [f'swatch {KINDS[kind]}'], (k, e, r)
        assert g[6] == MEANINGS[kind], (k, e, r)
        meaning.setdefault(kind, set()).add(g[6])
        parts = re.findall(r'Claude: "[^"]*"', g[10])
        assert ' · '.join(parts) == g[10], (k, e, r)
        want = [(f'Claude: "order {lo} ', reason_math(k, lw)), (f'Claude: "order {hi + 1} ', reason_math(k, hw))]
        want = [want[:1], want, want[1:]][kind]
        assert len(parts) == len(want) and all(p.startswith(a) and b in p for p, (a, b) in zip(parts, want)), \
            (k, e, r, want)
    assert all(len(v) == 1 for v in meaning.values()) and len(set.union(*meaning.values())) == len(meaning), meaning


def unclaimed(text):
    """text with dreeves's words (HIS) and every Claude: "…" removed: what is left must hold no English, only numbers
    and math."""
    for s in HIS: text = text.replace(s, '')
    return re.sub(r'Claude: "[^"]*"', '', text)


def english(text): return re.findall(r'[A-Za-z]{2,}', text)


def closed(text): return text.count('Claude: "') == len(re.findall(r'Claude: "[^"]*"', text))


# ---------------------------------------------------------------------------------------------------------------------
# Made-up data

def norm(n, p):
    """mstar.py's norm lemma in exact integers: the largest m with p^(2m) (p-1)^(p-1) <= (p sum_r size(p, r)^2)^(p-1),
    size(p, r) the number of i in 0..n-1 with i = r (mod p)."""
    rhs = (p * sum(((n - r + p - 1) // p) ** 2 for r in range(p))) ** (p - 1)
    m = 0
    while p ** (2 * m + 2) * (p - 1) ** (p - 1) <= rhs: m += 1
    return m


# Joins of products of blocks: the 2^24 construction itself, and Stong's 2^51 (BGPW Theorem 7.1), whose p_16 and
# p_8192 are Thue-Morse's τ_4 and τ_13.
JOIN24 = [[[112, 7], [320, 9], [320, 9]], [[432, 11], [48, 6], [256, 8]]]
STONG = [[[144, 8]] * 2 + [[192, 9]] * 4, [[48, 6]] * 3 + [[112, 7]] + [[192, 9]] * 3,
         [[16, 4], [112, 7], [112, 7], [208, 8], [272, 8], [192, 9], [192, 9]],
         [[112, 7]] + [[208, 8]] * 4 + [[8192, 13]]]


def kinds_cols():
    """Made-up columns that follow the contract and use every kind of reason: k <= 9 from Thue-Morse, settled by each
    kind of the m*(n) chart's hiWhy; then lo = k + floor(k / 24) (Thue-Morse, then f^{#L} # τ_j) and hi the norm bound
    for p = 3, but for a few columns with the other kinds: joins with f, τ_j (j above 9) and columns of mstar.js;
    residue chains; the norm bound for p = 5 and 7."""
    cols = []
    for k in range(1, K + 1):
        L, j = divmod(k, 24)
        cols.append([k + L, norm(2 ** k, 3), ['power', L, j] if L else ['thue-morse'], ['norm', 3]])
    whys = {1: ['two'], 2: ['norm', 3], 3: ['table2'], 4: ['page', 'BGPW'], 5: ['residue', 9],
            6: ['page', 'Claude alone'], 7: ['residue', 3], 8: ['table2'], 9: ['page', 'Claude and BGPW']}
    for k, why in whys.items(): cols[k - 1] = [k, k, ['thue-morse'], ['mstar', why]]
    joins = {24: JOIN24, 25: [[F, [2, 1]]], 34: [[[1024, 10], F]], 51: STONG}
    for k, ps in joins.items():
        assert sum(prod(n for n, _ in p) for p in ps) == 2 ** k
        cols[k - 1] = [min(sum(m for _, m in p) for p in ps), norm(2 ** k, 3), ['joins', ps], ['norm', 3]]
    cols[9] = [10, 10, ['thue-morse'], ['residue', [3, 9, 27]]]
    cols[10] = [11, 12, ['thue-morse'], ['residue', [5]]]
    cols[11] = [12, norm(2 ** 12, 5), ['thue-morse'], ['norm', 5]]
    cols[12] = [13, norm(2 ** 13, 7), ['thue-morse'], ['norm', 7]]
    return cols


def quoted(*what):
    """An assert's quote of what, as the page writes it: JSON with ' for "."""
    return json.dumps(list(what), ensure_ascii=False, separators=(',', ':')).replace('"', "'")


def column(k, entry):
    """A change to made-up data: column k becomes entry; the error quotes [k, entry]."""
    def change(data): data['cols'][k - 1] = entry
    return change, quoted(k, entry)


C30 = kinds_cols()[29]                        # [31, 37, ['power', 1, 6], ['norm', 3]]
VIOLATIONS = {   # name: (a change that breaks the contract, what the page's error line must quote)
    'lo below k': column(30, [29, 37, ['thue-morse'], ['norm', 3]]),
    'lo above hi': column(30, [38, 37, ['power', 1, 6], ['norm', 3]]),
    'hi at etop': column(30, [31, 49, ['power', 1, 6], ['norm', 3]]),
    'five entries': column(30, C30 + [0]),
    'unknown lo kind': column(30, [31, 37, ['guess'], ['norm', 3]]),
    'unknown hi kind': column(30, [31, 37, ['power', 1, 6], ['guess']]),
    'arity': column(30, [31, 37, ['power', 1], ['norm', 3]]),
    'thue-morse lo': column(30, [31, 37, ['thue-morse'], ['norm', 3]]),
    'power sum': column(30, [31, 37, ['power', 1, 5], ['norm', 3]]),
    'power lo': column(30, [32, 37, ['power', 1, 6], ['norm', 3]]),
    'joins length': column(30, [31, 37, ['joins', [[F, [32, 5]]]], ['norm', 3]]),
    'joins lo': column(30, [32, 37, ['joins', [[F, [64, 6]]]], ['norm', 3]]),
    'joins block': column(30, [31, 37, ['joins', [[[2048, 12], [524288, 19]]]], ['norm', 3]]),
    'joins empty': column(30, [31, 37, ['joins', []], ['norm', 3]]),
    'mstar above 9': column(10, [10, 10, ['thue-morse'], ['mstar', ['residue', 3]]]),
    'mstar kind': column(5, [5, 5, ['thue-morse'], ['mstar', ['guess']]]),
    'mstar two': column(2, [2, 2, ['thue-morse'], ['mstar', ['two']]]),
    'norm composite': column(30, [31, 37, ['power', 1, 6], ['norm', 9]]),
    'norm two': column(30, [31, 37, ['power', 1, 6], ['norm', 2]]),
    'norm bound': column(30, [31, 38, ['power', 1, 6], ['norm', 3]]),
    'residue chain': column(30, [31, 37, ['power', 1, 6], ['residue', [9, 3]]]),
    'residue one': column(30, [31, 37, ['power', 1, 6], ['residue', [1]]]),
    'etop': (lambda data: data.update(etop=data['etop'] + 1), '[20]'),
    'kmax': (lambda data: data.update(kmax=71), '[71,19]'),
    'cols': (lambda data: data.update(cols=data['cols'][:-1]), '[72,19]'),
    'extra key': (lambda data: data.update(note='x'), "[['kmax','etop','cols','note']]"),
}


def kinds_data(violation=None):
    """pow2.js's text for kinds_cols, broken by the change in VIOLATIONS that violation names, if given."""
    cols = kinds_cols()
    data = {'kmax': K, 'etop': max(c[1] - k for k, c in enumerate(cols, 1)) + 1, 'cols': cols}
    assert data['etop'] == 19
    if violation: VIOLATIONS[violation][0](data)
    return 'const POW2 = ' + json.dumps(data, ensure_ascii=False) + ';\n'


SOURCES = {'real': real, 'kinds': kinds_data} | {v: (lambda v=v: kinds_data(v)) for v in VIOLATIONS}


# ---------------------------------------------------------------------------------------------------------------------
# The browser runs

DRIVER = r"""
import { spawn } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
const C = JSON.parse(readFileSync(0, 'utf8'));
const chrome = spawn(C.chrome, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${C.dir}/profile`,
  '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--hide-scrollbars', 'about:blank'],
  {stdio: 'ignore', detached: true});
const stop = () => { if (chrome.exitCode === null) process.kill(-chrome.pid, 'SIGTERM'); };
const watchdog = setTimeout(() => { stop(); process.exit(3); }, 400000);
const sleep = ms => new Promise(r => setTimeout(r, ms));

// In the page.  TEXT: an element's text, each <sup> written ^(…) and each <sub> _(…).
const TEXT = el => {
  const c = el.cloneNode(true);
  c.querySelectorAll('sup').forEach(s => s.replaceWith(`^(${s.textContent})`));
  c.querySelectorAll('sub').forEach(s => s.replaceWith(`_(${s.textContent})`));
  return c.textContent;
};
const PROBE = text => {
  const sec = document.querySelector('section.pow2'), chart = document.getElementById('pow2-chart');
  const ro = document.getElementById('pow2-readout'), css = getComputedStyle(document.documentElement);
  const tokens = ['exists', 'open', 'impossible', 'paper', 'ink'].map(t => [t, css.getPropertyValue('--' + t).trim()]);
  const page = document.documentElement;
  const attrs = el => ['aria-label', 'title', 'alt'].filter(a => el.hasAttribute(a)).map(a => el.getAttribute(a));
  return {innerWidth, dpr: devicePixelRatio, dark: matchMedia('(prefers-color-scheme: dark)').matches,
    scrollW: page.scrollWidth, tokens: Object.fromEntries(tokens.map(([t, v]) => [t, v.toLowerCase()])),
    text: sec.innerText, readout: text(ro), live: ro.getAttribute('aria-live'), chartNodes: chart.childNodes.length,
    attrs: [...sec.querySelectorAll('*')].flatMap(attrs),
    canvasH: document.getElementById('mstar-chart').getBoundingClientRect().height};
};
const GEOMETRY = () => {
  const chart = document.getElementById('pow2-chart'), svg = chart.querySelector('svg');
  const box = r => [r.left, r.top, r.width, r.height], texts = [];
  const walk = document.createTreeWalker(chart, NodeFilter.SHOW_TEXT);
  for (let t = walk.nextNode(); t; t = walk.nextNode()) {
    const r = document.createRange();
    r.selectNodeContents(t);
    texts.push([t.textContent, box(r.getBoundingClientRect())]);
  }
  return {plot: box(svg.getBoundingClientRect()), svgs: chart.querySelectorAll('svg').length,
    rects: svg.querySelectorAll('rect').length, texts, innerWidth, scrollW: document.documentElement.scrollWidth,
    canvas: box(document.getElementById('mstar-chart').getBoundingClientRect())};
};
const DOM = cells => cells.map(([k, e, x, y]) => {
  const el = document.elementFromPoint(x, y);
  return [k, e, el.tagName.toLowerCase(), getComputedStyle(el).fill];
});
const READ = text => {
  const ro = document.getElementById('pow2-readout');
  const children = [...ro.children].map(c => c.className);
  return {text: text(ro), children, scrollW: document.documentElement.scrollWidth};
};
const FRAMES = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));

const out = C.urls.map(() => ({errors: []}));      // per page; anything logged before the first page goes to it
let ws, seq = 0, current = out[0];
const pending = new Map(), once = new Map();
const send = (method, params = {}) => new Promise((ok, no) => {
  const id = ++seq;
  pending.set(id, d => d.error ? no(new Error(`${method}: ${JSON.stringify(d.error)}`)) : ok(d.result));
  ws.send(JSON.stringify({id, method, params}));
});
const next = method => new Promise(r => once.set(method, r));       // the next event of the method
const ev = async (f, ...args) => {                                  // the value of f(...args) in the page
  const expression = `(${f})(${args.map(a => typeof a === 'function' ? String(a) : JSON.stringify(a)).join(', ')})`;
  const r = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  const thrown = JSON.stringify(r.exceptionDetails);
  if (thrown) throw new Error(`${expression.slice(0, 200)}: ${thrown.slice(0, 900)}`);
  return r.result.value;
};
const errors = {                     // the lines that each kind of event logs (none for a log entry below a warning)
  'Runtime.exceptionThrown': ({exceptionDetails: x}) =>
    `exception: ${x.text} ${(x.exception || {description: ''}).description.split('\n')[0]}`,
  'Runtime.consoleAPICalled': p => `console.${p.type}: ${p.args.map(a => a.value ?? a.description).join(' ')}`,
  'Log.entryAdded': ({entry: x}) => ['error', 'warning'].includes(x.level)
    ? `log ${x.level} ${x.source}: ${x.text} ${x.url || ''}` : null,
};
const shot = async path => {
  const {data} = await send('Page.captureScreenshot', {format: 'png'});
  writeFileSync(path, Buffer.from(data, 'base64'));
};
const settle = async () => {          // until the page's scroll position has held still for 100 ms (at most 5 s)
  let last = null;
  for (let i = 0; i < 50; i++) {
    await sleep(100);
    const now = await ev(() => `${scrollX} ${scrollY}`);
    if (now === last) return;
    last = now;
  }
};
// The platform fonts drawing each <sub> of the readout, and the readout's font-family.  What is logged meanwhile goes to
// log, not to the page's errors: it is DevTools' own (enabling CSS logs that a file: page may not load itself).
const subFonts = async () => {
  const page = current;
  current = {errors: []};
  await send('DOM.enable');
  await send('CSS.enable');
  const {root} = await send('DOM.getDocument', {depth: 0});
  const {nodeIds} = await send('DOM.querySelectorAll', {nodeId: root.nodeId, selector: '#pow2-readout sub'});
  const subs = [];
  for (const nodeId of nodeIds) {
    subs.push((await send('CSS.getPlatformFontsForNode', {nodeId})).fonts.map(f => f.familyName));
  }
  await send('CSS.disable');
  await send('DOM.disable');
  const log = current.errors;
  current = page;
  return {subs, log, family: await ev(() => getComputedStyle(document.getElementById('pow2-readout')).fontFamily)};
};
const input = {
  mouse: (x, y) => send('Input.dispatchMouseEvent', {type: 'mouseMoved', x, y}),
  touch: async (x, y) => { await send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [{x, y}]});
                           await send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []}); },
};

async function main() {
  const portFile = `${C.dir}/profile/DevToolsActivePort`;
  for (let i = 0; i < 300 && !existsSync(portFile); i++) await sleep(100);
  const port = readFileSync(portFile, 'utf8').split('\n')[0];
  const target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(t => t.type === 'page');
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((ok, no) => { ws.onopen = ok; ws.onerror = no; });
  ws.onmessage = m => {
    const d = JSON.parse(m.data);
    if (pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); }
    if (once.has(d.method)) { once.get(d.method)(d.params); once.delete(d.method); }
    const line = errors[d.method] && errors[d.method](d.params);
    if (line) current.errors.push(line);
  };
  for (const m of ['Page.enable', 'Runtime.enable', 'Log.enable']) await send(m);
  await send('Emulation.setDeviceMetricsOverride',
             {width: C.width, height: C.height, deviceScaleFactor: C.dpr, mobile: C.mobile});
  await send('Emulation.setTouchEmulationEnabled', {enabled: C.mobile, maxTouchPoints: 1});
  await send('Emulation.setEmulatedMedia', {features: [{name: 'prefers-color-scheme', value: C.theme}]});
  for (const [i, url] of C.urls.entries()) {
    const R = current = out[i];
    const loaded = next('Page.loadEventFired');
    await send('Page.navigate', {url});
    await loaded;
    await ev(() => document.fonts.ready.then(() => 0));
    await ev(FRAMES);
    R.load = await ev(PROBE, TEXT);
    if (!C.drawn) continue;
    await ev(() => document.getElementById('pow2-chart').scrollIntoView({block: 'center'}));
    await ev(FRAMES);
    R.geo = await ev(GEOMETRY);
    const [L, T, W] = R.geo.plot, cells = [];
    for (let k = 1; k <= C.K; k++) for (let e = 1; e <= C.E; e++) {
      cells.push([k, e, L + (k - 0.5) * W / C.K, T + (C.E - e) * C.ROW + (C.ROW - C.GAP) / 2]);
    }
    R.dom = await ev(DOM, cells);
    await shot(C.shots[0]);
    R.hovers = [];
    R.taps = [];
    for (const [list, how] of [[R.hovers, C.hover && 'mouse'], [R.taps, C.tap && 'touch']].filter(([, how]) => how)) {
      for (const [k, e, x, y] of cells) { await input[how](x, y); list.push([k, e, await ev(READ, TEXT)]); }
    }
    const [, , x, y] = cells.find(([k, e]) => k === C.outline[0] && e === C.outline[1]);
    await input[C.mobile ? 'touch' : 'mouse'](x, y);
    R.outline = await ev(READ, TEXT);
    R.outlineGeo = await ev(GEOMETRY);
    R.outlineDom = await ev(DOM, [[0, 0, x, y], [0, 0, x - W / C.K / 2 - 1, y]]);   // its middle; 1 px left of it
    R.subFonts = await subFonts();
    await shot(C.shots[1]);
    if (C.swipe) {                    // a finger's swipe up 200 px that starts on cell C.swipeFrom, then the readout
      const [, , sx, sy] = cells.find(([k, e]) => k === C.swipeFrom[0] && e === C.swipeFrom[1]);
      const from = await ev(() => scrollY);
      await send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [{x: sx, y: sy, id: 1}]});
      for (let i = 1; i <= 10; i++) {
        await send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: [{x: sx, y: sy - 20 * i, id: 1}]});
        await sleep(16);
      }
      await send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
      await settle();
      R.swipe = {...await ev(READ, TEXT), from, to: await ev(() => scrollY)};
    }
    R.mstar = [];
    await ev(() => document.getElementById('mstar-chart').scrollIntoView({block: 'center'}));
    await ev(FRAMES);
    const [cl, ct, cw] = (await ev(GEOMETRY)).canvas, T2 = await ev(() => MSTAR.mtop), [ML, MR, MT, MP] = C.mstarLayout;
    for (const [k, m] of C.mstarCells) {        // cell (2^k, m) of the m*(n) chart in its full view of the 500 even n
      await input.mouse(cl + ML + (2 ** k / 2 - 0.5) * (cw - ML - MR) / 500, ct + MT + (T2 - m) * MP + (MP - 2) / 2);
      R.mstar.push([k, m, await ev(() => document.getElementById('mstar-readout').textContent)]);
    }
  }
  return out;
}

// The report goes to a file, which a pipe's asynchronous writes could cut short at process.exit.  Chrome is stopped and
// waited for (up to 10 s), so its profile can be removed.
let code = 0;
try { writeFileSync(`${C.dir}/report.json`, JSON.stringify({pages: await main()})); }
catch (e) { writeFileSync(`${C.dir}/report.json`, JSON.stringify({error: String(e && e.stack || e)})); code = 1; }
finally { clearTimeout(watchdog); if (ws) ws.close(); stop(); }
await Promise.race([new Promise(r => chrome.exitCode === null ? chrome.once('exit', r) : r()), sleep(10000)]);
process.exit(code);
"""


# What DRIVER does in each configuration: its pages' pow2.js (by SOURCES; None for none); the viewport, as a phone
# (mobile, with touch) or not; the theme; whether the chart is drawn, and then whether every cell gets a mouse move
# (hover) or a touch tap (tap), whether the m*(n) chart's cells (2^k, hi + 1) are read out too (mstar), and whether a
# swipe follows the outline's tap (swipe).
DESKTOP = dict(width=1280, height=900, mobile=False, swipe=False)
PHONE = dict(width=390, height=844, mobile=True, swipe=True)
CONFIGS = {
    'light': DESKTOP | dict(data=['real'], dpr=2, theme='light', drawn=True, hover=True, tap=False, mstar=True),
    'phone': PHONE | dict(data=['real'], dpr=3, theme='light', drawn=True, hover=False, tap=True, mstar=False),
    'kinds': DESKTOP | dict(data=['kinds'], dpr=1, theme='light', drawn=True, hover=True, tap=False, mstar=False),
    'missing': DESKTOP | dict(data=[None], dpr=1, theme='light', drawn=False, hover=False, tap=False, mstar=False),
    'violations': DESKTOP | dict(data=list(VIOLATIONS), dpr=1, theme='light', drawn=False, hover=False, tap=False,
                                 mstar=False),
}
DRAWN = ('light', 'phone')                                   # the configurations on the real data


def run(name):
    """DRIVER's report for one configuration, made on first use: per page, its errors and probe at load, and for a drawn
    chart its geometry, the element at each cell's middle, the readouts of the hovers and taps, the outline's readout
    and the fonts of its <sub>s, the readout after the swipe, the m*(n) chart's readouts of the cells compared, and the
    two screenshots (load, outline) as images."""
    if name not in RUNS:
        c = CONFIGS[name]
        d = tempfile.mkdtemp(prefix='pow2-quals-')
        urls, datas = [], []
        for i, source in enumerate(c['data']):
            p = os.path.join(d, str(i))
            os.mkdir(p)
            for f in (INDEX, MSTAR) + tuple(os.path.join(HERE, icon) for icon in ICONS): shutil.copy(f, p)
            js = SOURCES[source]() if source else None
            if js: open(os.path.join(p, 'pow2.js'), 'w', encoding='utf-8').write(js)
            urls.append('file://' + os.path.join(p, 'index.html'))
            datas.append(pow2_of(js) if c['drawn'] else None)
        data = datas[0]
        # the cells (2^k, hi + 1) of the m*(n) chart to read out, for the k whose hiWhy is ["mstar", why]
        mstar = [[k, data['cols'][k - 1][1] + 1] for k in range(1, 10)
                 if c['mstar'] and data['cols'][k - 1][3][0] == 'mstar']
        shots = [os.path.join(d, 'load.png'), os.path.join(d, 'outline.png')]
        cfg = {k: c[k] for k in ('width', 'height', 'dpr', 'mobile', 'theme', 'drawn', 'hover', 'tap', 'swipe')} | dict(
            chrome=CHROME, dir=d, urls=urls, K=K, E=data['etop'] if data else 0, ROW=ROW, GAP=GAP, outline=OUTLINE,
            swipeFrom=SWIPE, shots=shots, mstarCells=mstar, mstarLayout=MSTAR_LAYOUT)
        try:
            p = subprocess.run(['node', '--input-type=module', '-e', DRIVER], input=json.dumps(cfg),
                               capture_output=True, text=True, timeout=600)
            path = os.path.join(d, 'report.json')
            report = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {'error': p.stderr[-4000:]}
            assert p.returncode == 0 and 'pages' in report, (name, p.returncode, report.get('error'))
            pages = report['pages']
            assert len(pages) == len(urls), (name, len(pages))
            for R, dd in zip(pages, datas):
                R['data'] = dd
                if c['drawn']: R['images'] = [Image.open(s).convert('RGB') for s in shots]
        finally:
            shutil.rmtree(d)
        RUNS[name] = pages
    return RUNS[name]


def valid(name):
    """The one page of a configuration on valid data, asserted to have loaded with nothing logged."""
    [R] = run(name)
    assert R['errors'] == [], (name, R['errors'])
    return R


def hexrgb(t): return '#%02x%02x%02x' % tuple(t[:3])


def fill(css):
    """A computed fill, rgb(r, g, b), as #rrggbb."""
    m = re.fullmatch(r'rgb\((\d+), (\d+), (\d+)\)', css)
    assert m, css
    return hexrgb([int(x) for x in m.groups()])


def pixel(R, image, x, y):
    """The color of the screenshot's device pixel at CSS (x, y) of the viewport."""
    dpr = R['load']['dpr']
    return hexrgb(R['images'][image].getpixel((int(x * dpr), int(y * dpr))))


def cell_box(R, geo, k, e):
    """Cell (k, e)'s colored part in CSS px of the viewport, as (x0, y0, x1, y1), by the plot's geometry."""
    L, T, W, _ = R[geo]['plot']
    E = R['data']['etop']
    return L + (k - 1) * W / K, T + (E - e) * ROW, L + k * W / K, T + (E - e) * ROW + ROW - GAP


# ---------------------------------------------------------------------------------------------------------------------
# Static quals

def q_insertions_only():
    # Replicata: index.html against the page without this chart (git show BASE:index.html with EDITS made), line by
    # line with difflib.
    # Expectata: every opcode is 'equal' or 'insert': not a character of the page without this chart changed or went
    # missing; and lines were inserted.
    tags = {tag for tag, *_ in opcodes()}
    assert tags <= {'equal', 'insert'}, [op for op in opcodes() if op[0] not in ('equal', 'insert')]
    assert 'insert' in tags, tags


def q_section_follows_mstar_chart():
    # Replicata: index.html.
    # Expectata: the m*(n) chart's <section class="mstar" aria-labelledby="mstar-title"> is followed, with only blank
    # lines and comments between, by <section class="pow2" aria-labelledby="pow2-title">, and that by <section
    # class="remarks">.  The new section holds, in order and with only blank lines and comments between: dreeves's
    # heading, the h2 pow2-title; a paragraph of class pow2-caption; the legend (LEGEND_LINES, its swatches exists,
    # open and impossible, as the m*(n) chart's); the div pow2-chart, empty until drawn, an image
    # with his label; and the readout paragraph pow2-readout, a polite live region holding his hint: his three lines
    # (DREEVES_LINES) byte for byte.
    text, filler = page(), r'(?:\s|<!--.*?-->)*'
    m = re.search(r'<section class="mstar" aria-labelledby="mstar-title">.*?</section>', text, re.S)
    assert m
    s = re.match(filler + r'(<section class="pow2" aria-labelledby="pow2-title">.*?</section>)', text[m.end():], re.S)
    assert s, text[m.end():m.end() + 400]
    rest = text[m.end() + s.end():]
    assert re.match(filler + r'<section class="remarks">', rest, re.S), rest[:400]
    heading, label, hint = map(re.escape, DREEVES_LINES)
    legend = r'(?:\s|<!--.*?-->)*'.join(map(re.escape, LEGEND_LINES))
    parts = (heading, r'<p class="pow2-caption">.*?</p>', legend, label, hint)
    whole = r'<section[^>]*>' + filler + filler.join(parts) + filler + '</section>'
    assert re.fullmatch(whole, s.group(1), re.S), s.group(1)


def q_scripts_load_pow2_after_mstar():
    # Replicata: index.html's script tags.
    # Expectata: exactly four, after </main>: the m*(n) chart's <script src="mstar.js"> and its inline script, then a
    # classic <script src="pow2.js"> (no type, async or defer, so it also loads from file://) right after them and one
    # inline script, the last thing before </body>.
    text = page()
    tags = re.findall(r'<script\b[^>]*>', text)
    assert tags == ['<script src="mstar.js">', '<script>', '<script src="pow2.js">', '<script>'], tags
    assert text.index('</main>') < text.index('<script src="mstar.js"></script>')
    assert text.count('</script>\n<script src="pow2.js"></script>\n<script>\n') == 1
    assert text.endswith('</script>\n</body>\n</html>\n')


def q_inline_script_passes_node_check():
    # Replicata: this chart's inline script (the page's second), saved as a .js file, through node --check.
    # Expectata: exit 0: it parses as a classic script.
    d = tempfile.mkdtemp(prefix='pow2-quals-')
    path = os.path.join(d, 'chart.js')
    open(path, 'w', encoding='utf-8').write(scripts()[1])
    p = subprocess.run(['node', '--check', path], capture_output=True, text=True, timeout=60)
    shutil.rmtree(d)
    assert p.returncode == 0, p.stderr


def q_new_copy_is_attributed():
    # Replicata: the inserted lines (this chart's), by region (HTML, inline script, style).
    # Expectata: inserted lines exist, and each of DREEVES_LINES is one of them, exactly once: those lines hold his
    # words, so the rules that follow pass over them.  In HTML, a line's visible text (comments and tags removed,
    # entities decoded) and its aria-label, title and alt values hold English (a run of two letters) only inside
    # Claude: "…", hold no stray double quote, and close every Claude: "…" they open; in script, every Claude: "…"
    # closes on its line.  Each line with a Claude: "…" has a TODO comment as the nearest non-blank line above (<!--
    # TODO: in HTML, // TODO: in script); each line that mentions TODO is such a comment and is followed by a line with
    # a Claude: "…" or is the TODO comment of a block quote attributed to Claude; no inserted CSS uses content:.  The
    # lines of such a quote, with dreeves's lead-in (quals_index.claude_quotes, his second form for Claude's words),
    # hold Claude's English as a whole, or his, so the copy rules pass over them.
    lines, region, ins = inserted()
    assert ins
    quoted, quote_todos = quals_index.claude_quotes(lines)
    his = [j for j in ins if j not in quoted and lines[j].strip() in DREEVES_LINES + LEGEND_LINES]
    assert sorted(lines[j].strip() for j in his) == sorted(DREEVES_LINES + LEGEND_LINES), [lines[j] for j in his]
    bad = []
    for j in (j for j in ins if j not in his and j not in quoted):
        line, r = lines[j], region[j]
        if r == 'style' and re.search(r'(?<![\w-])content\s*:', line): bad.append((j + 1, 'content:', line))
        if r == 'html':
            bare = re.sub(r'<!--.*?-->', '', line)
            texts = [re.sub(r'<[^>]*>', ' ', bare)] + [a or b for a, b in re.findall(
                r'\b(?:aria-label|title|alt)=(?:\'([^\']*)\'|"([^"]*)")', bare)]
            for t in map(html.unescape, texts):
                if english(unclaimed(t)) or '"' in unclaimed(t) or not closed(t): bad.append((j + 1, 'copy', t))
        if r == 'script' and not closed(line): bad.append((j + 1, 'unclosed', line))
        if 'Claude: "' in line:
            above = next(lines[i] for i in range(j - 1, -1, -1) if lines[i].strip())
            todo = '<!-- TODO:' in above if r == 'html' else above.strip().startswith('// TODO:')
            if not todo: bad.append((j + 1, 'no TODO above', line))
        if re.search(r'\bTODO\b', line):                # the word, not TODOCOLOR (dreeves's tag on the chart's colors)
            below = next(lines[i] for i in range(j + 1, len(lines)) if lines[i].strip())
            comment = line.strip().startswith('<!-- TODO:' if r == 'html' else '// TODO:')
            if not comment or ('Claude: "' not in below and j not in quote_todos):
                bad.append((j + 1, 'TODO', line))
    assert not bad, bad


def q_new_css_is_scoped():
    # Replicata: this chart's CSS (the inserted lines of the style block, comments removed).
    # Expectata: it is whole rules, and every selector of every rule starts with .pow2 or #pow2 (a class or id of the
    # new section), so the new CSS styles nothing of the frozen m*(n) chart or the rest of the page.
    lines, region, ins = inserted()
    css = re.sub(r'/\*.*?\*/', '', '\n'.join(lines[j] for j in ins if region[j] == 'style'), flags=re.S)
    rules = re.findall(r'([^{}]+)\{([^{}]*)\}', css)
    assert rules and re.fullmatch(r'\s*', re.sub(r'[^{}]+\{[^{}]*\}', '', css)), css
    selectors = [s.strip() for sel, _ in rules for s in sel.split(',')]
    assert all(re.match(r'[.#]pow2(?![\w])|[.#]pow2-', s) for s in selectors), selectors


def q_mstar_wording_is_copied_verbatim():
    # Replicata: the reasons of an upper bound in the m*(n) chart's inline script (the entries of const HI = {…}) and in
    # this chart's (the entries of const MSTAR_HI = {…}), each entry a kind with its ok, its TODO comment and its text.
    # Expectata: this chart has an entry for each kind of the m*(n) chart's hiWhy at an even n (two, norm, residue,
    # table2, page), each line for line the same as the m*(n) chart's, so a reason ["mstar", why] reads the same in both
    # charts.
    mstar, mine = scripts()
    def entries(script, name):
        body = re.search(rf'\n  const {name} = \{{\n(.*?)\n  \}};', script, re.S)
        assert body, name
        return {kind: [s.strip() for s in lines.split('\n')] for kind, lines in
                re.findall(r'(?:^|\n)    (\w+): \{\n(.*?)\n    \},', body.group(1), re.S)}
    a, b = entries(mstar, 'HI'), entries(mine, 'MSTAR_HI')
    assert sorted(b) == sorted(('two', 'norm', 'residue', 'table2', 'page')), sorted(b)
    for kind in b: assert a[kind] == b[kind], (kind, a[kind], b[kind])


def q_caption_defines_readout_symbols():
    # Replicata: the caption (the paragraph pow2-caption).
    # Expectata: it says what each symbol is that the readout writes for a block of a construction: f, τ_j (Thue-Morse)
    # and p_n (from a column of the m*(n) chart), each as the remarks write it: "<i>f</i> is", "τ<sub><i>j</i></sub> is"
    # and "<i>p</i><sub><i>n</i></sub> is".
    m = re.search(r'<p class="pow2-caption">(.*?)</p>', page(), re.S)
    assert m, 'pow2-caption'
    missing = [s for s in ('<i>f</i> is', 'τ<sub><i>j</i></sub> is', '<i>p</i><sub><i>n</i></sub> is') if s not in m[1]]
    assert not missing, missing


# ---------------------------------------------------------------------------------------------------------------------
# Browser quals

def q_page_loads_clean():
    # Replicata: index.html with the real mstar.js and pow2.js beside it, in each of the two drawn configurations (1280
    # px wide and 390 px wide).
    # Expectata: no exception, no console message at all, and no logged error or warning; the m*(n) chart above is
    # drawn (its canvas taller than 0); the new chart is one svg of K * E rects, E = POW2.etop; the readout is a polite
    # live region showing dreeves's hint, HINT, and nothing else.
    for name in DRAWN:
        R = valid(name)
        assert R['load']['canvasH'] > 0, (name, R['load'])
        assert R['geo']['svgs'] == 1 and R['geo']['rects'] == K * R['data']['etop'], (name, R['geo']['rects'])
        assert R['load']['live'] == 'polite' and R['load']['readout'] == HINT, R['load']


def q_drawn_cells_match_data():
    # Replicata: the four drawn configurations, before any hover or tap: a screenshot of the viewport with the chart in
    # view, and document.elementFromPoint at the middle of each cell (k, e), k = 1..K, e = 1..E.
    # Expectata: the pixel at each cell's middle has the color of its kind as the page's tokens give it in that theme
    # (exists when k + e <= lo, open when lo < k + e <= hi, impossible above); the pixel in the middle of the gap below
    # each cell is paper; the element at each cell's middle is an svg rect whose computed fill is that color.
    for name in DRAWN:
        R = valid(name)
        cols, tok = R['data']['cols'], R['load']['tokens']
        bad = []
        for k, e, tag, f in R['dom']:
            want = tok[KINDS[kind_of(cols[k - 1], k, e)]]
            x0, y0, x1, y1 = cell_box(R, 'geo', k, e)
            got = (pixel(R, 0, (x0 + x1) / 2, (y0 + y1) / 2), pixel(R, 0, (x0 + x1) / 2, y1 + GAP / 2), tag, fill(f))
            if got != (want, tok['paper'], 'rect', want): bad.append((k, e, want, got))
        assert len(R['dom']) == K * R['data']['etop'] and not bad, (name, len(bad), bad[:10])


def q_hover_reads_out_every_cell():
    # Replicata: the 1280 px light configuration: a real mouse move to the middle of every cell, column by column.
    # Expectata: after each, the readout is that cell's: its first child is a swatch of the cell's kind, and its text
    # (each <sup> written ^(…)) is "k = K, n = 2^(K), m = K + E = M · MEANING · lo ≤ m^(*)(2^(K)) ≤ hi · REASONS":
    # MEANING dreeves's word for the cell's kind (MEANINGS: known, open, impossible); REASONS the
    # Claude: "…" of lo's reason for a green cell, of hi's for a red one and both for a gray one, joined by " · ", lo's
    # starting "order lo " and hi's "order hi + 1 ", each holding its reason's math (reason_math).
    R = valid('light')
    check_readouts(R['data'], R['hovers'])


def q_tap_reads_out_every_cell():
    # Replicata: the 390 px light configuration (a phone: touch emulation, 3 device px per CSS px): a real touch tap at
    # the middle of every cell, column by column.
    # Expectata: after each, the readout is that cell's, as in q_hover_reads_out_every_cell.
    R = valid('phone')
    check_readouts(R['data'], R['taps'])


def q_swipe_scrolls_and_keeps_readout():
    # Replicata: the 390 px configuration: after the tap on cell OUTLINE, a real touch swipe up 200 px
    # (touchStart, ten touchMoves 20 px apart, touchEnd) that starts on cell SWIPE, then the page left to settle.
    # Expectata: the page scrolled down, and not sideways; the readout is still OUTLINE's, word for word, since a swipe
    # reads out nothing (a tap or a hover does).
    for name in ('phone',):
        R = valid(name)
        s = R['swipe']
        assert s['to'] > s['from'] and s['scrollW'] <= R['load']['innerWidth'], (name, s['from'], s['to'], s['scrollW'])
        assert (s['text'], s['children']) == (R['outline']['text'], R['outline']['children']), (name, s['text'][:60])


def q_readout_subscripts_in_page_font():
    # Replicata: in each drawn configuration, the readout of cell OUTLINE, whose lo is a join of products of blocks,
    # after its mouse move or tap; and the platform fonts that draw each <sub> in it (DevTools'
    # CSS.getPlatformFontsForNode).
    # Expectata: the readout holds no Unicode subscript digit (U+2080-2089: the page's fonts have none, so fallback
    # fonts drew them, two different ones side by side); each subscript it writes is a <sub> (as many <sub>s as TEXT
    # writes _(…), at least one per block of the join); and each <sub> is drawn in one font, the first of the
    # readout's font-family.  (While DevTools reads the fonts it logs only that a file: page may not load itself.)
    k, e = OUTLINE
    for name in DRAWN:
        R = valid(name)
        text, fonts, (lo, hi, lw, hw) = R['outline']['text'], R['subFonts'], R['data']['cols'][k - 1]
        family = fonts['family'].split(',')[0].strip().strip('"')
        assert all(x.startswith('log error security: Unsafe attempt to load URL file:') for x in fonts['log']), fonts
        assert lw[0] == 'joins' and not re.search('[₀-₉]', text), (name, lw[0], text)
        assert len(fonts['subs']) == text.count('_(') >= sum(map(len, lw[1])), (name, text, fonts)
        assert all(f == [family] for f in fonts['subs']), (name, family, fonts['subs'])


def q_outline_marks_the_cell():
    # Replicata: in each drawn configuration, after the hovers or taps, a mouse move (a tap on the phone) to the middle
    # of cell OUTLINE, then a screenshot.
    # Expectata: the readout is OUTLINE's; the pixels 1 CSS px outside its left and right edges (level with its middle)
    # and its top and bottom edges (level with its middle column) are ink, and its middle keeps its kind's color; the
    # outline takes no pointer: the element at the cell's middle is still its rect, and 1 px left of the cell, under the
    # outline, the rect of the cell to its left.
    k, e = OUTLINE
    for name in DRAWN:
        R = valid(name)
        g = READOUT.fullmatch(R['outline']['text'])
        assert g and (int(g[1]), int(g[4])) == (k, e), (name, R['outline'])
        x0, y0, x1, y1 = cell_box(R, 'outlineGeo', k, e)
        xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
        cols, tok = R['data']['cols'], R['load']['tokens']
        got = [pixel(R, 1, x, y) for x, y in ((x0 - 1, ym), (x1 + 1, ym), (xm, y0 - 1), (xm, y1 + 1), (xm, ym))]
        want = [tok['ink']] * 4 + [tok[KINDS[kind_of(cols[k - 1], k, e)]]]
        assert got == want, (name, got, want)
        hits = [(tag, fill(f)) for _, _, tag, f in R['outlineDom']]
        assert hits == [('rect', want[4]), ('rect', tok[KINDS[kind_of(cols[k - 2], k - 1, e)]])], (name, hits)


def q_labels_mark_every_e_and_round_k():
    # Replicata: the text nodes in #pow2-chart and their boxes, in the 1280 px and 390 px light configurations.
    # Expectata: they are exactly: the numbers 1..E left of the plot, number e's box centered on row e's colored part
    # (within 1 px), all with one right edge (within 0.5 px) at most 10 px left of the plot; the numbers 10, 20, ..., 70
    # below the plot, each centered on its column's middle (within 1 px); the letter e left of the plot, within its
    # height; and the letter k below the plot, left of it.
    for name in ('light', 'phone'):
        R = valid(name)
        L, T, W, H = R['geo']['plot']
        E, texts = R['data']['etop'], R['geo']['texts']
        left = sorted((t, b) for t, b in texts if b[0] + b[2] <= L and b[1] < T + H)
        below = sorted((t, b) for t, b in texts if b[1] >= T + H)
        assert len(left) + len(below) == len(texts), (name, texts)
        es = {int(t): b for t, b in left if t.isdigit()}
        assert sorted(es) == list(range(1, E + 1)) and len(left) == E + 1, (name, left)
        for e, (x, y, w, h) in es.items():
            assert abs(y + h / 2 - (T + (E - e) * ROW + (ROW - GAP) / 2)) <= 1, (name, e, y, h)
        rights = [x + w for x, y, w, h in es.values()]
        assert max(rights) - min(rights) <= 0.5 and 0 <= L - max(rights) <= 10, (name, rights, L)
        letters = [b for t, b in left if t == 'e']
        assert len(letters) == 1 and T <= letters[0][1] + letters[0][3] / 2 <= T + H, (name, left)
        ks = {int(t): b for t, b in below if t.isdigit()}
        assert sorted(ks) == KLABELS and len(below) == len(KLABELS) + 1, (name, below)
        for k, (x, y, w, h) in ks.items(): assert abs(x + w / 2 - (L + (k - 0.5) * W / K)) <= 1, (name, k, x, w)
        letters = [b for t, b in below if t == 'k']
        assert len(letters) == 1 and letters[0][0] + letters[0][2] <= L, (name, below)


def q_visible_text_is_attributed():
    # Replicata: the section's rendered text (innerText) at load and its aria-label, title and alt values, in the four
    # drawn configurations; every readout of the hovers, taps and outlines there and on the made-up data.
    # Expectata: outside Claude: "…" and dreeves's words (HIS: the heading's text, the label and the hint) none holds
    # English (a run of two letters), and each closes every Claude: "…" it opens.
    texts = []
    for name in DRAWN + ('kinds',):
        R = valid(name)
        texts += [R['load']['text'], *R['load']['attrs'], R['outline']['text']]
        texts += [r['text'] for _, _, r in R['hovers'] + R['taps']]
    bad = [t for t in texts if english(unclaimed(t)) or not closed(t)]
    assert len(texts) > 3 * K and not bad, (len(texts), bad[:10])


def q_phone_has_no_sideways_scroll():
    # Replicata: the 390 px configuration: at load, and after every tap.
    # Expectata: the viewport is 390 px; the page is never wider than it (scrollWidth <= innerWidth).
    for name in ('phone',):
        R = valid(name)
        widths = [R['load']['scrollW'], R['geo']['scrollW'], R['outline']['scrollW']]
        widths += [r['scrollW'] for _, _, r in R['taps']]
        assert R['load']['innerWidth'] == 390 and max(widths) <= 390, (name, max(widths))


def q_plot_lines_up_with_mstar_chart():
    # Replicata: the four drawn configurations: the new plot's box and the m*(n) chart's canvas.
    # Expectata: the plot runs from 44 CSS px right of the canvas's left edge to 16 px left of its right edge, where the
    # m*(n) chart's own plot runs (within 0.5 px), so the two plots line up.
    for name in DRAWN:
        R = valid(name)
        (L, _, W, _), (cl, _, cw, _) = R['geo']['plot'], R['geo']['canvas']
        left, right = MSTAR_LAYOUT[:2]
        assert abs(L - (cl + left)) <= 0.5 and abs(L + W - (cl + cw - right)) <= 0.5, (name, L, W, cl, cw)


def q_mstar_reasons_read_as_in_mstar_chart():
    # Replicata: the 1280 px light configuration on the real data: for each k <= 9 whose hiWhy is ["mstar", why], a real
    # mouse move to the red cell (k, hi + 1 - k) of the new chart, and to the cell (2^k, hi + 1) of the m*(n) chart in
    # its full view.
    # Expectata: there are such k; the m*(n) chart's readout is of that cell, and both readouts end in the same
    # Claude: "…", the m*(n) chart's reason for its hi.
    R = valid('light')
    mine = {(k, e): r['text'] for k, e, r in R['hovers']}
    assert R['mstar'], R['mstar']
    for k, m, text in R['mstar']:
        assert text.startswith(f'n = {2 ** k}, m = {m} · '), (k, m, text)
        a, b = re.findall(r'Claude: "[^"]*"', text)[-1], re.findall(r'Claude: "[^"]*"', mine[k, m - k])[-1]
        assert a == b and text.endswith(a) and mine[k, m - k].endswith(b), (k, a, b)


def q_drawn_runs_use_the_theme_tokens():
    # Replicata: the drawn configurations (light only since 2026-10-12: no dark mode).
    # Expectata: the tokens the page resolves are the theme block's values (the
    # pixel checks compare against these).
    light, = theme_blocks()
    for name in DRAWN:
        R = valid(name)
        assert all(R['load']['tokens'][t] == light[f'--{t}'].lower() for t in KINDS + ('paper', 'ink')), (name, R['load']['tokens'])


def q_made_up_data_reads_every_kind():
    # Replicata: made-up data that uses every kind of reason (kinds_cols), 1280 px light: a real mouse move to the
    # middle of every cell.
    # Expectata: nothing logged; every kind of loWhy and hiWhy and of the m*(n) chart's hiWhy is in the data; every
    # readout as in q_hover_reads_out_every_cell.
    R = valid('kinds')
    cols = R['data']['cols']
    assert {c[2][0] for c in cols} == {'thue-morse', 'power', 'joins'}
    assert {c[3][0] for c in cols} == {'mstar', 'norm', 'residue'}
    assert {c[3][1][0] for c in cols if c[3][0] == 'mstar'} == {'two', 'norm', 'residue', 'table2', 'page'}
    check_readouts(R['data'], R['hovers'])


def q_missing_data_fails_loudly():
    # Replicata: index.html with mstar.js but no pow2.js beside it.
    # Expectata: #pow2-chart stays empty; the readout is one Claude: "…" followed by the error, which names POW2; the
    # failed load of pow2.js and that uncaught error are logged, and nothing else; the m*(n) chart still draws.
    [R] = run('missing')
    g = re.fullmatch(r'Claude: "[^"]*" (.*)', R['load']['readout'])
    assert R['load']['chartNodes'] == 0 and g and 'POW2' in g[1], R['load']
    assert len(R['errors']) == 2 and f'exception: Uncaught {g[1]}' in R['errors'], R['errors']
    assert [x for x in R['errors'] if x.startswith('log error network: ') and x.endswith('/pow2.js')], R['errors']
    assert R['load']['canvasH'] > 0, R['load']


def q_contract_violations_fail_loudly():
    # Replicata: made-up data broken in one way each (VIOLATIONS): a lo below k or above hi; hi at etop; a column of
    # five entries; an unknown kind of loWhy or hiWhy, or one of the wrong arity; Thue-Morse not at lo = k; a power
    # whose 24 L + j is not k, or whose lo is not k + L; joins whose lengths do not add up to 2^k, whose lo is not the
    # least product's order, with a block that is none of f, τ_j and a column n <= 1000, or with no product; an
    # "mstar" hiWhy above k = 9, of an unknown kind, or breaking its own rule; a norm bound for a composite p, for
    # p = 2, or not the bound; a residue chain whose moduli do not divide in turn, or with a modulus below 2; an etop
    # above max(hi - k) + 1; kmax not 72; 71 columns; a key beyond kmax, etop and cols.
    # Expectata: in each case #pow2-chart stays empty, the readout is one Claude: "…" followed by "Error: " and the
    # quote (the column [k, [lo, hi, loWhy, hiWhy]] as JSON with ' for "; or [etop]; or [kmax, etop]; or the keys), and
    # the only thing logged is that error, uncaught.
    for v, R in zip(VIOLATIONS, run('violations')):
        q = VIOLATIONS[v][1]
        g = re.fullmatch(r'Claude: "[^"]*" (.*)', R['load']['readout'])
        assert R['load']['chartNodes'] == 0 and g and g[1] == f'Error: {q}', (v, R['load']['readout'])
        assert R['errors'] == [f'exception: Uncaught Error: {q}'], (v, R['errors'])


def main():
    names = sys.argv[1:] or [n for n in globals() if n.startswith('q_')]
    failed = 0
    for n in names:
        t0, c0 = time.time(), time.process_time()
        try:
            globals()[n]()
            # TODO: runner line; says the named qual passed, with its seconds and this process's CPU seconds
            print(f'Claude: "PASSED" {n} ({time.time() - t0:.1f} s, {time.process_time() - c0:.1f} CPU s)', flush=True)
        except Exception:
            failed += 1
            # TODO: runner line; says the named qual failed, with its seconds and this process's CPU seconds, followed by the traceback
            print(f'Claude: "FAILED" {n} ({time.time() - t0:.1f} s, {time.process_time() - c0:.1f} CPU s)\n' + traceback.format_exc(), flush=True)
    # TODO: runner summary; says how many quals passed out of how many
    print(f'Claude: "{len(names) - failed} of {len(names)} passed"')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
