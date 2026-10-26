#!/usr/bin/env python3
"""Quals for index.html's chart of m*(n) for the even n up to 1000.  Run: python3 -B quals_index.py [name ...]   (no
arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead).
The static quals read index.html, index.html as it was before the chart (git show BASE:index.html) and mstar.js.  The
browser quals load a copy of index.html in headless Chrome (in an iframe of the width each configuration asks for,
since the window cannot be narrower than 500 px), in a temporary directory with a copy of mstar.js (or made-up data)
and of pow2.js (the data of the page's chart of powers of 2), with two scripts added:
EARLY, first in the head, which records errors and every string drawn on a canvas, and
HARNESS, last in the body, which drives the chart with synthetic events and posts what it saw to the host page, which
writes it into the DOM that --dump-dom returns.
The harness locates the chart only by its pixels, reads the view only through the readout (the cell under a
synthetic pointer) and finds the n labels by where their strings were drawn, so the quals hold the chart to what a
reader sees.
"""
import sys
sys.dont_write_bytecode = True
import os, re, json, html, html.parser, math, time, shutil, signal, difflib, tempfile, threading, traceback, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, 'index.html')
DATA = os.path.join(HERE, 'mstar.js')         # made by mstar.py; the chart's data
POW2 = os.path.join(HERE, 'pow2.js')          # made by pow2.py; the data of the chart of powers of 2, also on the page
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
TOKENS = ('--exists', '--open', '--impossible')                    # the chart's three colors, in the order of kind
PROVENANCE = ('--claude', '--stan')
NMAX, MIN_SPAN = 1000, 12
EVEN = list(range(2, NMAX + 1, 2))            # the chart's columns: an odd n has no partition at any m, so is left out
NCOL = len(EVEN)
STEPS = (2, 10, 20, 50, 100, 200, 500)        # the steps of the n labels: 1, 2, 5, 10, ... without the odd ones
RUNS = {}                                     # browser runs by configuration name, made once per process (see run)
# The last commit before the chart ("Got 304:8").  The chart went in as insertions only, so the static quals diff
# against it, which guards that change; rebase it when dreeves next edits the page's existing text.
BASE = '014048c'
# dreeves's copyedit of the chart (917fe7f): his words, which stand without a Claude: "…" attribution.  The quals hold
# the page to them exactly, and any other English the chart shows must be Claude: "…".
HEADING = 'Bounds on <span class="nw"><i>m</i><sup>*</sup>(<i>n</i>)</span> for every even <i>n</i> up to 1000'
ZOOM_LABELS = ('zoom out', 'zoom in')         # the zoom buttons' aria-labels (he fixed a stray quote, 2026-10-11)
CANVAS_LABEL = 'chart of the bounds on m*(n) for even n up to 1000; the arrow keys pan, and + and − zoom'
HINT = 'Hover over a cell for details. Drag or swipe sideways to pan; zoom with the − and + buttons, pinching, or ctrl-scroll.'
ERROR = 'Error drawing the chart: '           # the readout when the chart cannot be drawn, followed by the error
# The lines of the page that hold his words, stripped: the copy rules of q_new_copy_is_attributed pass over them.
DREEVES_LINES = (f'<h2 id="mstar-title">{HEADING}</h2>',
                 '<li><span class="swatch open" aria-hidden="true"></span>open</li>',
                 f'<button type="button" id="mstar-zoom-out" aria-label=\'{ZOOM_LABELS[0]}\' title=\'Claude: "zoom out"\'>−</button>',
                 f'<button type="button" id="mstar-zoom-in" aria-label=\'{ZOOM_LABELS[1]}\' title=\'Claude: "zoom in"\'>+</button>',
                 '<button type="button" id="mstar-reset" aria-label=\'reset zoom\' title=\'reset zoom\'>↺</button>',
                 # and his copyedit of the powers-of-2 chart (its own quals, quals_pow2_page.py, hold it too)
                 '<h2 id="pow2-title">Bounds on <span class="nw"><i>m</i><sup>*</sup>(2<sup><i>k</i></sup>) − <i>k</i></span> for every <i>k</i> up to 72</h2>',
                 '<div id="pow2-chart" role="img" aria-label=\'Chart of the bounds on m*(2^k) − k, the excess over Thue–Morse, for k from 1 to 72\'></div>',
                 '<p id="pow2-readout" aria-live="polite">Hover over a cell for details.</p>',
                 # the powers-of-2 chart's legend repeats his "open" line, copied from this chart's (2026-10-12)
                 '<li><span class="swatch open" aria-hidden="true"></span>open</li>',
                 f'<canvas id="mstar-chart" height="0" tabindex="0" role="img" aria-label=\'{CANVAS_LABEL}\'></canvas>',
                 f'<p id="mstar-readout" aria-live="polite">{HINT}</p>',
                 f'ro.textContent = `{ERROR}${{e}}`;')
# dreeves and Stan Wagon's theorem, from their draft (2026-10-17: "xxxTheorem 1. m*(2^17) ≥ 18, …"), typeset atop the
# powers-of-2 section at dreeves's request ("sure"), in their words but for 64 at 2^57 (their 63 was the excess of 2^52)
# and without the draft's marker xxx and its note to themselves ("and same for smaller powers; Berend and Golan,
# check"): his words, so they stand without a Claude: "…" attribution, and the quals hold the page to them exactly.
# Their numbers changed once 592, 608 and 656 reached order 10 and 848, 880, 896, 928, 944, 976 and 992 order 11
# (2026-10-25; dreeves, 2026-10-25: "yes please"): the thresholds 27, 34, 38, 52 and 66 became 20, 30, 37, 49 and 65,
# and excess 9 at 2^72 joined them, in their list's own form, the count of excesses 8 becoming 9; no other character
# changed.
# They changed again once 752 and 784 reached order 10 and 832 order 11 (2026-10-26; dreeves, 2026-10-25: "yes
# please", for keeping them current): the thresholds 46, 49 and 72 became 43, 48 and 68; no excess is new, so the list
# keeps its form and its count; no other character changed.
THEOREM = ('<p><b>Theorem 1.</b> ' + ', '.join(f'<span class="nw"><i>m</i><sup>*</sup>(2<sup>{k}</sup>) ≥ {v}</span>' for k, v in
           ((17, 18), (20, 22), (30, 33), (37, 41), (43, 48), (48, 54), (57, 64), (65, 73), (68, 77))) +
           ' and <span class="nw"><i>m</i><sup>*</sup>(2<sup>9</sup>) = 9</span>.</p>')
# and its alternative form from the same draft ("or xxxTheorem 1. For i = 1, 2, …, 8, the known smallest values of n
# for which m*(2^n) − n ≥ i are 17, 27, 34, 38, 46, 52, 57, 66."), right below it at dreeves's request (2026-10-17: "can
# we get the alternate version of the theorem statement added?"), in their words, with their "or", without the xxx
THEOREM_ALT = ('<p>or <b>Theorem 1.</b> For <span class="nw"><i>i</i> = 1, 2, …, 9</span>, the known smallest values of '
               '<i>n</i> for which <span class="nw"><i>m</i><sup>*</sup>(2<sup><i>n</i></sup>) − <i>n</i> ≥ <i>i</i></span> are '
               '17, 20, 30, 37, 43, 48, 57, 65, 68.</p>')
DREEVES_LINES += (THEOREM, THEOREM_ALT)
# Stan Wagon's header for the table of record gaps (his table of 2026-10-18, which record_gaps.wl and the table below
# the theorem extend): its words and its line, byte for byte; a human's words, so the copy rules pass over them too
STAN_WORDS = ('Record gaps', 'The power of 2', 'The order')
STAN_HEADER = ''.join(['<thead><tr>'] + [f'<th>{w}</th>' for w in STAN_WORDS] + ['</tr></thead>'])
DREEVES_LINES += (STAN_HEADER,)
# his note under Table 2 crediting Richard Stong (2026-10-18, commit 23ba3db, "Stong got 2^51": his rewording of the
# line Claude had put there at his request), byte for byte
STONG_NOTE = '<p>Note: <i>m</i><sup>*</sup>(2<sup>51</sup>) ≥ 52 is due to Richard Stong.</p>'
DREEVES_LINES += (STONG_NOTE,)
# his wording of the m*(n) chart's legend label for the gold rings (2026-10-19, commit 9e46bb5 "Gold trim": his
# rewording of the label Claude had put there at his request), byte for byte
GOLD_LEGEND = '<li><span class="swatch exists record" aria-hidden="true"></span><span><span class="nw"><i>n</i> = <i>a</i>(<i>m</i> − 1)</span> of OEIS <a href="https://oeis.org/A323395">A323395</a>, the smallest <i>n</i> for a given <i>m</i></span></li>'
DREEVES_LINES += (GOLD_LEGEND,)
# his copy of 2026-10-24 and 25 that came as new lines, byte for byte (his edits of lines already in the page before the
# chart are in TABLE_UPDATE): the sentence of the {1, …, 8} example in the header (2026-10-25, commit 48710ae "Human
# copy", its "..." made "…" by him the same evening); the sentence on the hex codes, moved from the footer to the top of the remarks and reworded (2026-10-24, commit
# 35dd836 "Edits"); and the 416 proof's heading and its line on BGPW's 208:8 code, unattributed in the commit that added
# the proof (2026-10-24, b475924 "Add proof for 416:9"), so his
EXAMPLE8 = ("For {1, …, 8} it turns out there's a partition &mdash; {1, 4, 6, 7} and {2, 3, 5, 8} &mdash; that gets us up "
            'to <i>k</i> = 2, meaning <i>m</i><sup>*</sup>(8) = 3:')
HEX_NOTE = ('<p>The hex codes shown below follow Table 5 of BGPW:',
            'the left half of the signs <span class="nw">(1 = +1, 0 = −1)</span>, then the rest by <span class="nw">(−1)<sup><i>m</i></sup></span> symmetry.</p>')
PROOF416_HEAD = ('<p><strong><i>m</i><sup>*</sup>(416) = 9: construction and proof.</strong></p>',
                 '<p><a href="https://arxiv.org/html/1912.03491v1#S6.T5">BGPW Table 5</a> has the 208:8 code <code id="seed416">C5A2CB6B945B28BC43ADB6586C</code>.</p>')
DREEVES_LINES += (EXAMPLE8,) + HEX_NOTE + PROOF416_HEAD
# and the 416 proof's five Astra: "…" lines as he committed them, without the TODO comment Astra had put above each
# (2026-10-24, b475924; dreeves, 2026-10-25: "i changed those astra lines intentionally"), so the copy rules pass
# over them as over his own
PROOF416_ASTRA = ('<p>Astra: "Its binary expansion gives the first 104 signs (1 → +1, 0 → −1); the remaining 104 are the same signs in reverse order. If <i>P</i>(<i>x</i>) is the polynomial of this sequence, then <span class="nw"><i>F</i>(<i>x</i>) = (1 − <i>x</i><sup>208</sup>)<i>P</i>(<i>x</i>)</span> has length 416 and order 9: append the same sequence with every sign negated."</p>',
                  '<p>Astra: "Code for the length-416 example, using the same convention: <code id="witness416">C5A2CB6B945B28BC43ADB6586C361A6DB5C23D14DA29D6D345A3</code>"</p>',
                  '<p>Astra: "To rule out order 10, let <i>D</i><sub>0</sub>, <i>D</i><sub>1</sub>, <i>D</i><sub>2</sub> be the sums of the signs in the residue classes modulo 3. The class sizes are <span id="sizes416">139, 139, 138</span>, so <i>D</i><sub>0</sub> and <i>D</i><sub>1</sub> are odd, and <i>D</i><sub>0</sub> + <i>D</i><sub>1</sub> + <i>D</i><sub>2</sub> = 0."</p>',
                  '<p>Astra: "Let ζ be a cube root of unity other than 1. Since <span class="nw">(ζ − 1)<sup>10</sup> = −243ζ<sup>2</sup></span>, order at least 10 implies <i>f</i>(ζ) = (<i>D</i><sub>0</sub> − <i>D</i><sub>2</sub>) + (<i>D</i><sub>1</sub> − <i>D</i><sub>2</sub>)ζ ∈ <span id="modulus416">243</span>ℤ[ζ]. Therefore all three sums are congruent modulo 243."</p>',
                  '<p>Astra: "The difference <span class="nw"><i>D</i><sub>0</sub> − <i>D</i><sub>1</sub></span> is even and divisible by 243, but its absolute value is at most 278. Therefore <span class="nw"><i>D</i><sub>0</sub> = <i>D</i><sub>1</sub> = <i>d</i></span>. Then <span class="nw"><i>D</i><sub>2</sub> = −2<i>d</i></span>, giving <span class="nw">|<i>d</i>| ≤ 69</span>; but <span class="nw">243 ∣ 3<i>d</i></span>, so <span class="nw">81 ∣ <i>d</i></span>. Only <span class="nw"><i>d</i> = 0</span> remains, contradicting its oddness. Thus <span class="nw"><i>m</i><sup>*</sup>(416) = 9</span>."</p>')
DREEVES_LINES += PROOF416_ASTRA
# his error line in the powers-of-2 chart's script (2026-10-24, b475924: Claude's line without its Claude: "…" and its
# TODO comment; its closing backtick restored the same day, b70e1aa): the readout when that chart cannot be drawn,
# followed by the error, as ERROR is the m*(n) chart's
POW2_ERROR = 'Error drawing this chart: '
POW2_ERROR_LINE = f'ro.textContent = `{POW2_ERROR}${{e}}`;'
DREEVES_LINES += (POW2_ERROR_LINE,)


# ---------------------------------------------------------------------------------------------------------------------
# Reading the page

def page(): return open(INDEX, encoding='utf-8').read()


# The page's updates of 2026-10-11, which dreeves asked for, the only edits of its text before the chart: 432, 480 and
# 528 gained the upper bounds the chart proves, in the new results' table and in their remarks' entries (and on
# 2026-10-12 the powers of 2 moved to a second table, stating the powers-of-2 chart's ranges); the green
# label "Claude and Stan" became "Claude and BGPW" (BGPW includes Stan), and 528, a BGPW example with Claude's upper
# bound, became green.  (old, new, how many times old occurs).
TABLE_UPDATE = (('<td class="c">≥ 11</td>', '<td class="c">11–12</td>', 1),
                ('<td class="c">≥ 12</td>', '<td class="c">12–14</td>', 1),
                ('<td class="s">≥ 10</td>', '<td class="j">10–12</td>', 1),
                ('<i>m</i><sup>*</sup> ≥ 11</span>', '<i>m</i><sup>*</sup> ∈ {11, 12}</span>', 1),
                ('<i>m</i><sup>*</sup> ≥ 12</span>', '<i>m</i><sup>*</sup> ∈ {12, 13, 14}</span>', 1),
                ('<i>m</i><sup>*</sup> ≥ 10</span>', '<i>m</i><sup>*</sup> ∈ {10, 11, 12}</span>', 1),
                ("title='Claude and Stan'", "title='Claude and BGPW'", 4),
                ("<td class=\"s\" title='BGPW'>528</td>", "<td class=\"j\" title='Claude and BGPW'>528</td>", 1),
                ('◆●</span>Claude and Stan</li>', '◆●</span>Claude and BGPW</li>', 1),
                ('<li class="s">\n      <span class="mk" aria-hidden="true">●</span>\n      <p class="entry"><i>n</i> = 528:',
                 '<li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 528:', 1),
                ("<td class=\"j\" title='Claude and BGPW'>2<sup>24</sup></td><td class=\"j\" title='Claude and BGPW'>2<sup>51</sup></td></tr>", '</tr>', 1),
                ('<td class="j">≥ 25</td><td class="j">≥ 53</td></tr>', '</tr>', 1),
                ('<i>n</i> = 2<sup>24</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ≥ 25</span>',
                 '<i>n</i> = 2<sup>24</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {25, …, 29}</span>', 1),
                ('<i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ≥ 53</span>',
                 '<i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {54, …, 63}</span>', 1),
                # BGPW's five examples of order 9, as codes in their remarks (2026-10-12)
                ('      <p>Examples of order 9 found by BGPW. Order 10 is ruled out by the paper\'s Proposition 4.3 <span class="nw">(<i>p</i> = 3)</span>.</p>\n',
                 '      <p>Examples of order 9 found by BGPW. Order 10 is ruled out by the paper\'s Proposition 4.3 <span class="nw">(<i>p</i> = 3)</span>.</p>\n      <p class="code">\n        <span><i>p</i><sub>352</sub> <span class="nw">(<i>m</i> = 9)</span>:</span>\n        <code>A4DB4926DB4D36584B26936D2CFA54B6F04B2C13D4A2</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>368</sub> <span class="nw">(<i>m</i> = 9)</span>:</span>\n        <code>96C965925B75B0CB249E583CF26B2E836C31DAC874B67D</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>400</sub> <span class="nw">(<i>m</i> = 9)</span>:</span>\n        <code>34DB69269A69269A6D379A8D1C57459C5B45E5100DBAF7EAAA</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>464</sub> <span class="nw">(<i>m</i> = 9)</span>:</span>\n        <code>93C96596CB2586DB1C965964E69975A207755BE209CE5E28F2C35A92BA</code>\n      </p>\n', 1),
                ('      <p>An example of order 9 found by BGPW. Order 10 is ruled out by the residue condition mod 27, by the same argument as for 512; the solvers CP-SAT and SCIP agree.</p>\n',
                 '      <p>An example of order 9 found by BGPW. Order 10 is ruled out by the residue condition mod 27, by the same argument as for 512; the solvers CP-SAT and SCIP agree.</p>\n      <p class="code">\n        <span><i>p</i><sub>496</sub> <span class="nw">(<i>m</i> = 9)</span>:</span>\n        <code>C96992D92DB24B7596496D1A530DB5994EA699A9ACE072BDC57403B339A4CE</code>\n      </p>\n', 1),
                # dreeves's own edit of the preview's alt text (2026-10-12, e437afe)
                ("then new results from 304 to 2^51'>", "then various new results'>", 1),
                # the powers of 2's own table, flush under the first (2026-10-12); its titles reuse the legend's labels
                ('          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">8</td><td class="s">9</td><td class="j">10</td><td class="s">9</td><td class="s">9</td><td class="s">9</td><td class="s">9</td><td class="c">11–12</td><td class="c">9</td><td class="s">9</td><td class="c">12–14</td><td class="j">9</td><td class="c">9</td><td class="j">10–12</td><td class="c">10–12</td></tr>\n        </table>\n',
                 '          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">8</td><td class="s">9</td><td class="j">10</td><td class="s">9</td><td class="s">9</td><td class="s">9</td><td class="s">9</td><td class="c">11–12</td><td class="c">9</td><td class="s">9</td><td class="c">12–14</td><td class="j">9</td><td class="c">9</td><td class="j">10–12</td><td class="c">10–12</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="j">25–29</td><td class="c">35–41</td><td class="c">52–61</td><td class="j">54–63</td><td class="c">61–71</td><td class="c">72–83</td></tr>\n        </table>\n', 1),
                # every multiple of 16 from 304 to 992, in four rows of 11 (2026-10-12)
                ('        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>304</td><td class="s" title=\'BGPW\'>320</td><td class="j" title=\'Claude and BGPW\'>336</td><td class="s" title=\'BGPW\'>352</td><td class="s" title=\'BGPW\'>368</td><td class="s" title=\'BGPW\'>400</td><td class="s" title=\'BGPW\'>416</td><td class="c" title=\'Claude alone\'>432</td><td class="c" title=\'Claude alone\'>448</td><td class="s" title=\'BGPW\'>464</td><td class="c" title=\'Claude alone\'>480</td><td class="j" title=\'Claude and BGPW\'>496</td><td class="c" title=\'Claude alone\'>512</td><td class="j" title=\'Claude and BGPW\'>528</td><td class="c" title=\'Claude alone\'>576</td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">8</td><td class="s">9</td><td class="j">10</td><td class="s">9</td><td class="s">9</td><td class="s">9</td><td class="s">9</td><td class="c">11–12</td><td class="c">9</td><td class="s">9</td><td class="c">12–14</td><td class="j">9</td><td class="c">9</td><td class="j">10–12</td><td class="c">10–12</td></tr>\n        </table>\n',
                 '        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>304</td><td class="s" title=\'BGPW\'>320</td><td class="j" title=\'Claude and BGPW\'>336</td><td class="s" title=\'BGPW\'>352</td><td class="s" title=\'BGPW\'>368</td><td class="c" title=\'Claude alone\'>384</td><td class="s" title=\'BGPW\'>400</td><td class="s" title=\'BGPW\'>416</td><td class="c" title=\'Claude alone\'>432</td><td class="c" title=\'Claude alone\'>448</td><td class="s" title=\'BGPW\'>464</td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">8</td><td class="s">9</td><td class="j">10</td><td class="s">9</td><td class="s">9</td><td class="c">10–11</td><td class="s">9</td><td class="s">9</td><td class="c">11–12</td><td class="c">9</td><td class="s">9</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>480</td><td class="j" title=\'Claude and BGPW\'>496</td><td class="c" title=\'Claude alone\'>512</td><td class="j" title=\'Claude and BGPW\'>528</td><td class="c" title=\'Claude alone\'>544</td><td class="c" title=\'Claude alone\'>560</td><td class="c" title=\'Claude alone\'>576</td><td class="c" title=\'Claude alone\'>592</td><td class="c" title=\'Claude alone\'>608</td><td class="c" title=\'Claude alone\'>624</td><td class="c" title=\'Claude alone\'>640</td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">12–14</td><td class="j">9</td><td class="c">9</td><td class="j">10–12</td><td class="c">9–10</td><td class="c">9–10</td><td class="c">10–12</td><td class="c">9–10</td><td class="c">9–10</td><td class="c">10–12</td><td class="c">10</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>656</td><td class="c" title=\'Claude alone\'>672</td><td class="c" title=\'Claude alone\'>688</td><td class="c" title=\'Claude alone\'>704</td><td class="c" title=\'Claude alone\'>720</td><td class="c" title=\'Claude alone\'>736</td><td class="c" title=\'Claude alone\'>752</td><td class="c" title=\'Claude alone\'>768</td><td class="c" title=\'Claude alone\'>784</td><td class="c" title=\'Claude alone\'>800</td><td class="c" title=\'Claude alone\'>816</td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">9–10</td><td class="c">11–13</td><td class="c">9–10</td><td class="c">10</td><td class="c">10–14</td><td class="c">10</td><td class="c">9–11</td><td class="c">11–13</td><td class="c">9–10</td><td class="c">10–11</td><td class="c">10–14</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>832</td><td class="c" title=\'Claude alone\'>848</td><td class="c" title=\'Claude alone\'>864</td><td class="c" title=\'Claude alone\'>880</td><td class="c" title=\'Claude alone\'>896</td><td class="c" title=\'Claude alone\'>912</td><td class="c" title=\'Claude alone\'>928</td><td class="c" title=\'Claude alone\'>944</td><td class="c" title=\'Claude alone\'>960</td><td class="c" title=\'Claude alone\'>976</td><td class="c" title=\'Claude alone\'>992</td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">10–11</td><td class="c">9–11</td><td class="c">12–14</td><td class="c">10–11</td><td class="c">10–11</td><td class="c">11–13</td><td class="c">10–11</td><td class="c">10–11</td><td class="c">13–15</td><td class="c">10–11</td><td class="c">10–11</td></tr>\n        </table>\n', 1),
                # every power of 2 of the tables in the final row: Table 2's copied, 512 moved (2026-10-12)
                ('        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>304</td><td class="s" title=\'BGPW\'>320</td><td class="j" title=\'Claude and BGPW\'>336</td><td class="s" title=\'BGPW\'>352</td><td class="s" title=\'BGPW\'>368</td><td class="c" title=\'Claude alone\'>384</td><td class="s" title=\'BGPW\'>400</td><td class="s" title=\'BGPW\'>416</td><td class="c" title=\'Claude alone\'>432</td><td class="c" title=\'Claude alone\'>448</td><td class="s" title=\'BGPW\'>464</td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">8</td><td class="s">9</td><td class="j">10</td><td class="s">9</td><td class="s">9</td><td class="c">10–11</td><td class="s">9</td><td class="s">9</td><td class="c">11–12</td><td class="c">9</td><td class="s">9</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>480</td><td class="j" title=\'Claude and BGPW\'>496</td><td class="c" title=\'Claude alone\'>512</td><td class="j" title=\'Claude and BGPW\'>528</td><td class="c" title=\'Claude alone\'>544</td><td class="c" title=\'Claude alone\'>560</td><td class="c" title=\'Claude alone\'>576</td><td class="c" title=\'Claude alone\'>592</td><td class="c" title=\'Claude alone\'>608</td><td class="c" title=\'Claude alone\'>624</td><td class="c" title=\'Claude alone\'>640</td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">12–14</td><td class="j">9</td><td class="c">9</td><td class="j">10–12</td><td class="c">9–10</td><td class="c">9–10</td><td class="c">10–12</td><td class="c">9–10</td><td class="c">9–10</td><td class="c">10–12</td><td class="c">10</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>656</td><td class="c" title=\'Claude alone\'>672</td><td class="c" title=\'Claude alone\'>688</td><td class="c" title=\'Claude alone\'>704</td><td class="c" title=\'Claude alone\'>720</td><td class="c" title=\'Claude alone\'>736</td><td class="c" title=\'Claude alone\'>752</td><td class="c" title=\'Claude alone\'>768</td><td class="c" title=\'Claude alone\'>784</td><td class="c" title=\'Claude alone\'>800</td><td class="c" title=\'Claude alone\'>816</td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">9–10</td><td class="c">11–13</td><td class="c">9–10</td><td class="c">10</td><td class="c">10–14</td><td class="c">10</td><td class="c">9–11</td><td class="c">11–13</td><td class="c">9–10</td><td class="c">10–11</td><td class="c">10–14</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>832</td><td class="c" title=\'Claude alone\'>848</td><td class="c" title=\'Claude alone\'>864</td><td class="c" title=\'Claude alone\'>880</td><td class="c" title=\'Claude alone\'>896</td><td class="c" title=\'Claude alone\'>912</td><td class="c" title=\'Claude alone\'>928</td><td class="c" title=\'Claude alone\'>944</td><td class="c" title=\'Claude alone\'>960</td><td class="c" title=\'Claude alone\'>976</td><td class="c" title=\'Claude alone\'>992</td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">10–11</td><td class="c">9–11</td><td class="c">12–14</td><td class="c">10–11</td><td class="c">10–11</td><td class="c">11–13</td><td class="c">10–11</td><td class="c">10–11</td><td class="c">13–15</td><td class="c">10–11</td><td class="c">10–11</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="j">25–29</td><td class="c">35–41</td><td class="c">52–61</td><td class="j">54–63</td><td class="c">61–71</td><td class="c">72–83</td></tr>\n        </table>\n',
                 '        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>304</td><td class="s" title=\'BGPW\'>320</td><td class="j" title=\'Claude and BGPW\'>336</td><td class="s" title=\'BGPW\'>352</td><td class="s" title=\'BGPW\'>368</td><td class="c" title=\'Claude alone\'>384</td><td class="s" title=\'BGPW\'>400</td><td class="s" title=\'BGPW\'>416</td><td class="c" title=\'Claude alone\'>432</td><td class="c" title=\'Claude alone\'>448</td><td class="s" title=\'BGPW\'>464</td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">8</td><td class="s">9</td><td class="j">10</td><td class="s">9</td><td class="s">9</td><td class="c">10–11</td><td class="s">9</td><td class="s">9</td><td class="c">11–12</td><td class="c">9</td><td class="s">9</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>480</td><td class="j" title=\'Claude and BGPW\'>496</td><td class="j" title=\'Claude and BGPW\'>528</td><td class="c" title=\'Claude alone\'>544</td><td class="c" title=\'Claude alone\'>560</td><td class="c" title=\'Claude alone\'>576</td><td class="c" title=\'Claude alone\'>592</td><td class="c" title=\'Claude alone\'>608</td><td class="c" title=\'Claude alone\'>624</td><td class="c" title=\'Claude alone\'>640</td><td class="c" title=\'Claude alone\'>656</td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">12–14</td><td class="j">9</td><td class="j">10–12</td><td class="c">9–10</td><td class="c">9–10</td><td class="c">10–12</td><td class="c">9–10</td><td class="c">9–10</td><td class="c">10–12</td><td class="c">10</td><td class="c">9–10</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>672</td><td class="c" title=\'Claude alone\'>688</td><td class="c" title=\'Claude alone\'>704</td><td class="c" title=\'Claude alone\'>720</td><td class="c" title=\'Claude alone\'>736</td><td class="c" title=\'Claude alone\'>752</td><td class="c" title=\'Claude alone\'>768</td><td class="c" title=\'Claude alone\'>784</td><td class="c" title=\'Claude alone\'>800</td><td class="c" title=\'Claude alone\'>816</td><td class="c" title=\'Claude alone\'>832</td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">11–13</td><td class="c">9–10</td><td class="c">10</td><td class="c">10–14</td><td class="c">10</td><td class="c">9–11</td><td class="c">11–13</td><td class="c">9–10</td><td class="c">10–11</td><td class="c">10–14</td><td class="c">10–11</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>848</td><td class="c" title=\'Claude alone\'>864</td><td class="c" title=\'Claude alone\'>880</td><td class="c" title=\'Claude alone\'>896</td><td class="c" title=\'Claude alone\'>912</td><td class="c" title=\'Claude alone\'>928</td><td class="c" title=\'Claude alone\'>944</td><td class="c" title=\'Claude alone\'>960</td><td class="c" title=\'Claude alone\'>976</td><td class="c" title=\'Claude alone\'>992</td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">9–11</td><td class="c">12–14</td><td class="c">10–11</td><td class="c">10–11</td><td class="c">11–13</td><td class="c">10–11</td><td class="c">10–11</td><td class="c">13–15</td><td class="c">10–11</td><td class="c">10–11</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td title=\'The published paper (2021)\'>2<sup>3</sup></td><td title=\'The published paper (2021)\'>2<sup>4</sup></td><td title=\'The published paper (2021)\'>2<sup>5</sup></td><td title=\'The published paper (2021)\'>2<sup>6</sup></td><td title=\'The published paper (2021)\'>2<sup>7</sup></td><td title=\'The published paper (2021)\'>2<sup>8</sup></td><td class="c" title=\'Claude alone\'>2<sup>9</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td class="c">9</td><td class="j">25–29</td><td class="c">35–41</td><td class="c">52–61</td><td class="j">54–63</td><td class="c">61–71</td><td class="c">72–83</td></tr>\n        </table>\n', 1),
                # 560 settled at 10 by a lattice search's example (2026-10-12)
                ('<td class="j">10–12</td><td class="c">9–10</td><td class="c">9–10</td><td class="c">10–12</td>', '<td class="j">10–12</td><td class="c">9–10</td><td class="c">10</td><td class="c">10–12</td>', 1),
                # 560's set and its code block, data that the copy quals would read as English: the set ends the sets'
                # <code> (on 528's last line); the code block sits where 560's remark is inserted around it (2026-10-12)
                ('  519, 520, 521, 525, 526};</code></pre>', '  519, 520, 521, 525, 526};\nSClaude[10][560] = {\n  0, 1, 4, 6, 7, 10, 12, 13, 15, 19, 21, 22, 28, 29, 30, 31, 34, 37,\n  39, 40, 41, 42, 45, 46, 51, 54, 55, 57, 58, 60, 61, 63, 64, 66, 67,\n  69, 70, 72, 73, 75, 78, 81, 82, 84, 87, 88, 91, 93, 94, 96, 97,\n  100, 103, 105, 107, 109, 114, 115, 117, 119, 120, 121, 123, 124,\n  126, 133, 135, 138, 141, 142, 144, 145, 147, 148, 150, 151, 154,\n  156, 157, 159, 160, 163, 168, 169, 171, 172, 174, 177, 178, 180,\n  181, 182, 187, 189, 192, 195, 196, 198, 199, 201, 202, 204, 205,\n  207, 208, 211, 213, 214, 216, 217, 219, 220, 222, 223, 225, 226,\n  228, 229, 231, 232, 234, 238, 240, 243, 247, 248, 249, 250, 253,\n  255, 256, 258, 259, 261, 271, 273, 274, 276, 277, 279, 280, 282,\n  283, 285, 286, 288, 298, 300, 301, 303, 304, 306, 309, 310, 311,\n  312, 316, 319, 321, 325, 327, 328, 330, 331, 333, 334, 336, 337,\n  339, 340, 342, 343, 345, 346, 348, 351, 352, 354, 355, 357, 358,\n  360, 361, 363, 364, 367, 370, 372, 377, 378, 379, 381, 382, 385,\n  387, 388, 390, 391, 396, 399, 400, 402, 403, 405, 408, 409, 411,\n  412, 414, 415, 417, 418, 421, 424, 426, 433, 435, 436, 438, 439,\n  440, 442, 444, 445, 450, 452, 454, 456, 459, 462, 463, 465, 466,\n  468, 471, 472, 475, 477, 478, 481, 484, 486, 487, 489, 490, 492,\n  493, 495, 496, 498, 499, 501, 502, 504, 505, 508, 513, 514, 517,\n  518, 519, 520, 522, 525, 528, 529, 530, 531, 537, 538, 540, 544,\n  546, 547, 549, 552, 553, 555, 558, 559};</code></pre>', 1),
                ('    </li>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 576: &nbsp;', '    </li>\n      <p class="code">\n        <span><i>p</i><sub>560</sub> <span class="nw">(<i>m</i> = 10)</span>:</span>\n        <code>34D2E9F0DA19EC92492D966936ABCA25FAD924D26F2591EB64926924925D6E1A4BFE92</code>\n      </p>\n    <li class="c">\n      <span class="mk" aria-hidden="true">◆</span>\n      <p class="entry"><i>n</i> = 576: &nbsp;', 1),
                # the powers of 2 once 560 reached order 10: 2^18, 2^41, 2^48, 2^61 and 2^71 added, 2^49 and 2^51 raised (2026-10-12)
                ('        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td title=\'The published paper (2021)\'>2<sup>3</sup></td><td title=\'The published paper (2021)\'>2<sup>4</sup></td><td title=\'The published paper (2021)\'>2<sup>5</sup></td><td title=\'The published paper (2021)\'>2<sup>6</sup></td><td title=\'The published paper (2021)\'>2<sup>7</sup></td><td title=\'The published paper (2021)\'>2<sup>8</sup></td><td class="c" title=\'Claude alone\'>2<sup>9</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td class="c">9</td><td class="j">25–29</td><td class="c">35–41</td><td class="c">52–61</td><td class="j">54–63</td><td class="c">61–71</td><td class="c">72–83</td></tr>\n        </table>\n',
                 '        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td title=\'The published paper (2021)\'>2<sup>3</sup></td><td title=\'The published paper (2021)\'>2<sup>4</sup></td><td title=\'The published paper (2021)\'>2<sup>5</sup></td><td title=\'The published paper (2021)\'>2<sup>6</sup></td><td title=\'The published paper (2021)\'>2<sup>7</sup></td><td title=\'The published paper (2021)\'>2<sup>8</sup></td><td class="c" title=\'Claude alone\'>2<sup>9</sup></td><td class="c" title=\'Claude alone\'>2<sup>18</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>41</sup></td><td class="c" title=\'Claude alone\'>2<sup>48</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>61</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td><td class="c" title=\'Claude alone\'>2<sup>71</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td class="c">9</td><td class="c">19–22</td><td class="j">25–29</td><td class="c">35–41</td><td class="c">44–51</td><td class="c">52–59</td><td class="c">53–61</td><td class="j">55–63</td><td class="c">61–71</td><td class="c">66–76</td><td class="c">72–83</td><td class="c">77–88</td></tr>\n        </table>\n', 1),
                ('<i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {54, …, 63}</span>', '<i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {55, …, 63}</span>', 1),
                # the powers of 2 in two rows, split after 2^49 (dreeves, 2026-10-12)
                ('        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td title=\'The published paper (2021)\'>2<sup>3</sup></td><td title=\'The published paper (2021)\'>2<sup>4</sup></td><td title=\'The published paper (2021)\'>2<sup>5</sup></td><td title=\'The published paper (2021)\'>2<sup>6</sup></td><td title=\'The published paper (2021)\'>2<sup>7</sup></td><td title=\'The published paper (2021)\'>2<sup>8</sup></td><td class="c" title=\'Claude alone\'>2<sup>9</sup></td><td class="c" title=\'Claude alone\'>2<sup>18</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>41</sup></td><td class="c" title=\'Claude alone\'>2<sup>48</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>61</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td><td class="c" title=\'Claude alone\'>2<sup>71</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td class="c">9</td><td class="c">19–22</td><td class="j">25–29</td><td class="c">35–41</td><td class="c">44–51</td><td class="c">52–59</td><td class="c">53–61</td><td class="j">55–63</td><td class="c">61–71</td><td class="c">66–76</td><td class="c">72–83</td><td class="c">77–88</td></tr>\n        </table>\n',
                 '        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td title=\'The published paper (2021)\'>2<sup>3</sup></td><td title=\'The published paper (2021)\'>2<sup>4</sup></td><td title=\'The published paper (2021)\'>2<sup>5</sup></td><td title=\'The published paper (2021)\'>2<sup>6</sup></td><td title=\'The published paper (2021)\'>2<sup>7</sup></td><td title=\'The published paper (2021)\'>2<sup>8</sup></td><td class="c" title=\'Claude alone\'>2<sup>9</sup></td><td class="c" title=\'Claude alone\'>2<sup>18</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>41</sup></td><td class="c" title=\'Claude alone\'>2<sup>48</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td class="c">9</td><td class="c">19–22</td><td class="j">25–29</td><td class="c">35–41</td><td class="c">44–51</td><td class="c">52–59</td><td class="c">53–61</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>61</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td><td class="c" title=\'Claude alone\'>2<sup>71</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="j">55–63</td><td class="c">61–71</td><td class="c">66–76</td><td class="c">72–83</td><td class="c">77–88</td></tr>\n        </table>\n', 1),
                # the table's colors: no --joint, Claude and BGPW as stripes of the other two (dreeves, 2026-10-12)
                ("  /* Provenance hues, checked with the dataviz palette validator against this\n     mode's surface. The worst color-blind pair is 6.4 (deutan), legal only\n     with a second cue, so every hue also carries a glyph: ◆ Claude, ● BGPW,\n     ◆● both. */\n", "  /* Provenance hues, checked with the dataviz palette validator against this\n     mode's surface: color-blind ΔE 23.6 (protan). Every hue also carries a\n     glyph: ◆ Claude, ● BGPW, and ◆● both, whose cells are stripes of the\n     two. */\n", 1),
                ('  --joint: #2a9466;\n', '', 1),
                ('    --joint: #2aa070;\n', '', 1),
                ('\n  --joint: #2aa070;\n', '\n', 1),
                ('td.j { --hue: var(--joint); --glyph: "◆●"; }\n', 'td.j { --glyph: "◆●"; }\n', 1),
                ('  color: var(--hue);\n}\n\n.legend {', '  color: var(--hue);\n}\n/* Claude and BGPW: stripes of the two tints over a striped bar, its glyph half in each hue */\ntd.j, .key.j { background: repeating-linear-gradient(135deg, color-mix(in oklab, var(--claude) var(--tint), var(--paper)) 0 0.3rem, color-mix(in oklab, var(--stan) var(--tint), var(--paper)) 0.3rem 0.6rem); }\ntr.vals td.j, .key.j { background: repeating-linear-gradient(90deg, var(--claude) 0 0.3rem, var(--stan) 0.3rem 0.6rem) bottom / 100% 3px no-repeat, repeating-linear-gradient(135deg, color-mix(in oklab, var(--claude) var(--tint), var(--paper)) 0 0.3rem, color-mix(in oklab, var(--stan) var(--tint), var(--paper)) 0.3rem 0.6rem); box-shadow: none; }\ntr.ns td.j::before, .key.j > span, .remarks li.j .mk { background: linear-gradient(90deg, var(--claude) 50%, var(--stan) 50%); -webkit-background-clip: text; background-clip: text; color: transparent; }\n\n.legend {', 1),
                ('.key.j { --hue: var(--joint); }\n', '', 1),
                ('.remarks li.j .mk { color: var(--joint); }\n', '', 1),
                ('<span class="key j" aria-hidden="true">◆●</span>', '<span class="key j" aria-hidden="true"><span>◆●</span></span>', 1),
                # a glyph line in every n cell of the new results; the powers' bounds mod 3; 2^20 in the 304 remark (2026-10-12)
                ('tr.ns td.c::before, tr.ns td.j::before, tr.ns td.s::before {\n  content: var(--glyph);\n', '.new-block tr.ns td::before {\n  content: var(--glyph, "\\a0");\n', 1),
                ('/* Provenance: tint on both cells of an entry, a bar under its value, and a\n   glyph centered above its n. Text stays in ink. */\n', '/* Provenance: tint on both cells of an entry, a bar under its value, and a\n   glyph centered above its n (in every n cell of the new results a line for it, blank\n   where there is none, so they all line up). Text stays in ink. */\n', 1),
                ('        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td title=\'The published paper (2021)\'>2<sup>3</sup></td><td title=\'The published paper (2021)\'>2<sup>4</sup></td><td title=\'The published paper (2021)\'>2<sup>5</sup></td><td title=\'The published paper (2021)\'>2<sup>6</sup></td><td title=\'The published paper (2021)\'>2<sup>7</sup></td><td title=\'The published paper (2021)\'>2<sup>8</sup></td><td class="c" title=\'Claude alone\'>2<sup>9</sup></td><td class="c" title=\'Claude alone\'>2<sup>18</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>41</sup></td><td class="c" title=\'Claude alone\'>2<sup>48</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td class="c">9</td><td class="c">19–22</td><td class="j">25–29</td><td class="c">35–41</td><td class="c">44–51</td><td class="c">52–59</td><td class="c">53–61</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>61</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td><td class="c" title=\'Claude alone\'>2<sup>71</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="j">55–63</td><td class="c">61–71</td><td class="c">66–76</td><td class="c">72–83</td><td class="c">77–88</td></tr>\n        </table>\n', '        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td title=\'The published paper (2021)\'>2<sup>3</sup></td><td title=\'The published paper (2021)\'>2<sup>4</sup></td><td title=\'The published paper (2021)\'>2<sup>5</sup></td><td title=\'The published paper (2021)\'>2<sup>6</sup></td><td title=\'The published paper (2021)\'>2<sup>7</sup></td><td title=\'The published paper (2021)\'>2<sup>8</sup></td><td class="c" title=\'Claude alone\'>2<sup>9</sup></td><td class="c" title=\'Claude alone\'>2<sup>18</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>41</sup></td><td class="c" title=\'Claude alone\'>2<sup>48</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td class="c">9</td><td class="c">19–21</td><td class="j">25–29</td><td class="c">35–40</td><td class="c">44–50</td><td class="c">52–59</td><td class="c">53–60</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>61</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td><td class="c" title=\'Claude alone\'>2<sup>71</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="j">55–63</td><td class="c">61–70</td><td class="c">66–75</td><td class="c">72–83</td><td class="c">77–88</td></tr>\n        </table>\n', 1),
                ('which needed 304 to have order 9 -->\n', 'which needed 304 to have order 9, though 2^20 now has order 21 another way, the 2^18 entry times tau_2 -->\n', 1),
                (', which needed 304 to have order 9."</p>\n', ', which needed 304 to have order 9. 2<sup>20</sup> now has order 21 another way: the 2<sup>18</sup> entry below, each product times τ<sub>2</sub>."</p>\n', 1),
                # Claude's corrected wording where a TODO for dreeves stood (dreeves, 2026-10-12)
                ('      <p>Joint construction: <span class="nw">2<sup>24</sup> = 320<sup>2</sup>·112 + 432·48·2<sup>8</sup></span>, that is, <span class="nw"><i>f</i> = (<i>p</i><sub>320</sub> # <i>p</i><sub>320</sub> # <i>p</i><sub>112</sub>)</span> <span class="nw">∨ (<i>p</i><sub>432</sub> # <i>p</i><sub>48</sub> # τ<sub>8</sub>)</span>. Hence <span class="nw"><i>m</i><sup>*</sup>(2<sup><i>k</i></sup>) ≥ <i>k</i> + 1</span> for every <span class="nw"><i>k</i> ≥ 24</span>.</p>', '      <p>Claude: "Joint construction: <span class="nw">2<sup>24</sup> = 320<sup>2</sup>·112 + 432·48·2<sup>8</sup></span>, that is, <span class="nw"><i>f</i> = (<i>p</i><sub>320</sub> # <i>p</i><sub>320</sub> # <i>p</i><sub>112</sub>)</span> <span class="nw">∨ (<i>p</i><sub>432</sub> # <i>p</i><sub>48</sub> # τ<sub>8</sub>)</span>. Hence <span class="nw"><i>m</i><sup>*</sup>(2<sup><i>k</i></sup>) ≥ <i>k</i> + 1</span> for every <span class="nw"><i>k</i> ≥ 24</span>, and by the 2<sup>18</sup> entry above for every <span class="nw"><i>k</i> ≥ 18</span>."</p>', 1),
                ("  <p>BGPW's examples at lengths 352, 368, 400, 416, 464 and 496 were not re-checked here.</p>", '  <p>Claude: "BGPW\'s example at length 416 was not re-checked here."</p>', 1),
                ('        <span><i>p</i><sub>336</sub>, an antisymmetric example found independently by Claude; it is the second part of the 528 example below <span class="nw">(<i>m</i> = 9)</span>:</span>', '        <span>Claude: "<i>q</i><sub>336</sub>, an antisymmetric example found independently by Claude; it is the second part of the 528 example below" <span class="nw">(<i>m</i> = 9)</span>:</span>', 1),
                ('        <span><i>f</i> = <i>p</i><sub>192</sub> ∨ <i>p</i><sub>336</sub>; &nbsp;<i>p</i><sub>192</sub> <span class="nw">(<i>m</i> = 9)</span>:</span>', '        <span><i>f</i> = <i>p</i><sub>192</sub> ∨ <i>q</i><sub>336</sub>; &nbsp;<i>p</i><sub>192</sub> <span class="nw">(<i>m</i> = 9)</span>:</span>', 1),
                # no dark mode: its two theme blocks deleted (dreeves, 2026-10-12),
                ('\n@media (prefers-color-scheme: dark) {\n  :root:not([data-theme="light"]) {\n', '\n', 1),
                ('\n    --paper: #16171b;\n', '\n', 1),
                ('\n    --ink: #e9e7e2;\n', '\n', 1),
                ('\n    --muted: #a2a6b0;\n', '\n', 1),
                ('\n    --rule: #c9c7c2;\n', '\n', 1),
                ('\n    --claude: #d46c46;\n', '\n', 1),
                ('\n    --stan: #5f86dc;\n', '\n', 1),
                ('\n    --tint: 24%;\n', '\n', 1),
                ('\n    color-scheme: dark;\n', '\n', 1),
                ('\n  }\n}\n:root[data-theme="dark"] {\n', '\n', 1),
                ('\n  --paper: #16171b;\n', '\n', 1),
                ('\n  --ink: #e9e7e2;\n', '\n', 1),
                ('\n  --muted: #a2a6b0;\n', '\n', 1),
                ('\n  --rule: #c9c7c2;\n', '\n', 1),
                ('\n  --claude: #d46c46;\n', '\n', 1),
                ('\n  --stan: #5f86dc;\n', '\n', 1),
                ('\n  --tint: 24%;\n', '\n', 1),
                ('\n  color-scheme: dark;\n}\n', '\n', 1),
                # dreeves's own edit of the intro: the {0, 1, …, n − 1} convention (2026-10-13),
                ('    (Fun fact: This property of having equal power sums for exponents from 0 up to some <i>k</i> is invariant under translating and scaling.\n', '    Fun fact, this property of having equal power sums for exponents from 0 up to some <i>k</i> is invariant under translating and scaling.\n', 1),
                ('    You can in fact start with any set of <i>n</i> equally spaced integers.)\n', '    You can in fact start with any set of <i>n</i> equally spaced integers.\n  </p>\n  <p class="lede">\n    From now on we use the convention that the <i>n</i>-element set to be partitioned is {0, 1, …, <i>n</i> − 1}.\n', 1),
                # 800 settled at 11 by a lattice search's example (2026-10-17)
                ('<td class="c">9–10</td><td class="c">10–11</td><td class="c">10–14</td>', '<td class="c">9–10</td><td class="c">11</td><td class="c">10–14</td>', 1),
                # 800's set and its code block, data that the copy quals would read as English: the set ends the sets'
                # <code> (on 560's last line); the code block sits where 800's remark is inserted around it (2026-10-17)
                ('  546, 547, 549, 552, 553, 555, 558, 559};</code></pre>', '  546, 547, 549, 552, 553, 555, 558, 559};\nSClaude[11][800] = {\n  0, 3, 5, 6, 9, 10, 12, 15, 17, 18, 21, 23, 24, 27, 29, 30, 32, 36,\n  37, 38, 39, 42, 44, 45, 48, 51, 53, 54, 57, 59, 60, 62, 63, 66, 69,\n  71, 72, 74, 75, 77, 81, 84, 86, 87, 90, 93, 95, 96, 98, 99, 102,\n  103, 105, 107, 108, 111, 113, 114, 116, 117, 119, 120, 123, 126,\n  129, 132, 134, 135, 137, 138, 140, 141, 143, 144, 147, 149, 150,\n  153, 156, 159, 161, 162, 164, 165, 168, 171, 173, 174, 177, 180,\n  182, 183, 185, 186, 189, 191, 192, 194, 195, 198, 200, 201, 204,\n  206, 207, 210, 213, 216, 218, 219, 222, 225, 227, 228, 230, 231,\n  234, 236, 237, 240, 243, 245, 246, 248, 249, 252, 254, 255, 257,\n  258, 260, 261, 264, 267, 269, 270, 271, 273, 276, 279, 281, 282,\n  284, 285, 288, 290, 291, 294, 296, 297, 300, 301, 303, 305, 306,\n  308, 309, 310, 312, 315, 317, 318, 324, 326, 327, 330, 333, 338,\n  339, 340, 342, 345, 347, 348, 351, 352, 354, 357, 359, 360, 363,\n  366, 368, 369, 371, 372, 374, 375, 378, 380, 381, 383, 384, 386,\n  387, 389, 390, 392, 393, 395, 396, 399, 401, 402, 405, 408, 411,\n  414, 417, 420, 422, 423, 426, 429, 432, 434, 435, 437, 438, 441,\n  443, 444, 446, 449, 450, 453, 455, 456, 458, 462, 463, 464, 465,\n  467, 468, 470, 471, 474, 476, 477, 478, 479, 480, 483, 485, 486,\n  488, 492, 495, 497, 500, 501, 504, 506, 507, 510, 512, 513, 516,\n  519, 521, 522, 524, 525, 527, 531, 533, 534, 536, 537, 540, 543,\n  546, 548, 549, 552, 555, 557, 558, 560, 561, 564, 566, 567, 570,\n  573, 575, 576, 578, 579, 582, 584, 585, 587, 588, 590, 591, 594,\n  596, 597, 600, 602, 603, 606, 609, 611, 612, 615, 618, 620, 621,\n  623, 624, 627, 629, 630, 632, 633, 636, 639, 641, 642, 644, 645,\n  647, 648, 651, 653, 654, 657, 660, 663, 666, 668, 669, 671, 672,\n  674, 675, 677, 678, 681, 684, 687, 689, 690, 693, 695, 698, 699,\n  702, 705, 707, 708, 710, 711, 714, 716, 717, 719, 720, 721, 723,\n  726, 729, 731, 732, 734, 735, 738, 741, 743, 744, 747, 749, 750,\n  752, 753, 756, 758, 759, 764, 765, 766, 768, 771, 773, 774, 777,\n  779, 780, 783, 785, 786, 788, 791, 792, 795, 797, 798};</code></pre>', 1),
                ('    </li>\n    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>24</sup>: &nbsp;', '    </li>\n      <p class="code">\n        <span><i>p</i><sub>800</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n        <code>966965968F2C965B25B44B25B3596D924B6D96496C964B65B2CB24B25B2C96CB6C97496CB2CD6E960B243A59A592DB2DB6D9</code>\n      </p>\n    <li class="j">\n      <span class="mk" aria-hidden="true">◆●</span>\n      <p class="entry"><i>n</i> = 2<sup>24</sup>: &nbsp;', 1),
                # the powers of 2 once 800 reached order 11 (2026-10-17): the first power of 2 for each excess
                # added (2^17, 2^27, 2^34, 2^38, 2^46, 2^52 and 2^66), 2^41 to 2^71 raised, the rows split after 2^34
                ('        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td title=\'The published paper (2021)\'>2<sup>3</sup></td><td title=\'The published paper (2021)\'>2<sup>4</sup></td><td title=\'The published paper (2021)\'>2<sup>5</sup></td><td title=\'The published paper (2021)\'>2<sup>6</sup></td><td title=\'The published paper (2021)\'>2<sup>7</sup></td><td title=\'The published paper (2021)\'>2<sup>8</sup></td><td class="c" title=\'Claude alone\'>2<sup>9</sup></td><td class="c" title=\'Claude alone\'>2<sup>18</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>41</sup></td><td class="c" title=\'Claude alone\'>2<sup>48</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td class="c">9</td><td class="c">19–21</td><td class="j">25–29</td><td class="c">35–40</td><td class="c">44–50</td><td class="c">52–59</td><td class="c">53–60</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>61</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td><td class="c" title=\'Claude alone\'>2<sup>71</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="j">55–63</td><td class="c">61–70</td><td class="c">66–75</td><td class="c">72–83</td><td class="c">77–88</td></tr>\n        </table>\n', '        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td title=\'The published paper (2021)\'>2<sup>3</sup></td><td title=\'The published paper (2021)\'>2<sup>4</sup></td><td title=\'The published paper (2021)\'>2<sup>5</sup></td><td title=\'The published paper (2021)\'>2<sup>6</sup></td><td title=\'The published paper (2021)\'>2<sup>7</sup></td><td title=\'The published paper (2021)\'>2<sup>8</sup></td><td class="c" title=\'Claude alone\'>2<sup>9</sup></td><td class="c" title=\'Claude alone\'>2<sup>17</sup></td><td class="c" title=\'Claude alone\'>2<sup>18</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>27</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>34</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td class="c">9</td><td class="c">18–20</td><td class="c">19–21</td><td class="j">25–29</td><td class="c">29–33</td><td class="c">35–40</td><td class="c">37–41</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>2<sup>38</sup></td><td class="c" title=\'Claude alone\'>2<sup>41</sup></td><td class="c" title=\'Claude alone\'>2<sup>46</sup></td><td class="c" title=\'Claude alone\'>2<sup>48</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>52</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>61</sup></td><td class="c" title=\'Claude alone\'>2<sup>66</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td><td class="c" title=\'Claude alone\'>2<sup>71</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">42–46</td><td class="c">45–50</td><td class="c">51–57</td><td class="c">53–59</td><td class="c">54–60</td><td class="j">56–63</td><td class="c">58–64</td><td class="c">64–70</td><td class="c">68–75</td><td class="c">74–82</td><td class="c">75–83</td><td class="c">79–88</td></tr>\n        </table>\n', 1),
                # 240 settled at 10 (2026-10-20: overnight_v5.py, then boxsplit.py by 17 and 19, the final pass ALL
                # NODES CLOSED), a cell of its own before 304's (dreeves: "Before 304 in new results")
                ('<th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>304</td>', '<th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>240</td><td class="c" title=\'Claude alone\'>304</td>', 1),
                ('(<i>n</i>)</th><td class="c">8</td><td class="s">9</td><td class="j">10</td>', '(<i>n</i>)</th><td class="c">10</td><td class="c">8</td><td class="s">9</td><td class="j">10</td>', 1),
                # the search remarks name their certificates' kind (2026-10-20, dreeves's "sure", after Stan Wagon read
                # "a certificate" as a residue proof): 304's TODO recap and Claude line, both in BASE
                ('closes every case with a certificate checked in exact integer arithmetic', 'closes every case with linear-programming certificates checked in exact integer arithmetic', 2))

# 384 settled at 10 by Astra's exact modular certificate (2026-10-20).  These precise edits add its author to the
# existing table's visual vocabulary; all other original prose and styling remain protected by the baseline diff.
TABLE_UPDATE += (("<td class=\"c\" title='Claude alone'>384</td>", "<td class=\"a\" title='Astra alone'>384</td>", 1),
                 ('<td class="s">9</td><td class="s">9</td><td class="c">10–11</td><td class="s">9</td>',
                  '<td class="s">9</td><td class="s">9</td><td class="a">10</td><td class="s">9</td>', 1),
                 ('  --stan: #3460c8;', '  --stan: #3460c8;\n  /* Astra\'s result uses a separate hue and the glyph ✦. */\n  --astra: #7560a7;', 1),
                 ('td.c { --hue: var(--claude); --glyph: "◆"; }', 'td.c { --hue: var(--claude); --glyph: "◆"; }\ntd.a { --hue: var(--astra); --glyph: "✦"; }', 1),
                 ('td.c, td.j, td.s { background:', 'td.a, td.c, td.j, td.s { background:', 1),
                 ('tr.vals td.c, tr.vals td.j, tr.vals td.s { box-shadow:', 'tr.vals td.a, tr.vals td.c, tr.vals td.j, tr.vals td.s { box-shadow:', 1),
                 ('.key.c { --hue: var(--claude); }', '.key.c { --hue: var(--claude); }\n.key.a { --hue: var(--astra); }', 1),
                 ('.remarks li.c .mk { color: var(--claude); }', '.remarks li.c .mk { color: var(--claude); }\n.remarks li.a .mk { color: var(--astra); }', 1),
                 ('    <li><span class="key c" aria-hidden="true">◆</span>Claude alone</li>',
                  '    <li><span class="key c" aria-hidden="true">◆</span>Claude alone</li>\n    <li><span class="key a" aria-hidden="true">✦</span>Astra alone</li>', 1))
# The legend line's TODO comment above (Astra's, 2026-10-20) never reached a commit: dreeves's page has the two entries
# side by side (by his convention, a copy approved), so the edit records his version (2026-10-23).
# dreeves's own edits of lines in the page before the chart or made by the edits above, so in both rebuilt pages, this
# file's and quals_pow2_page.py's, his words byte for byte, trailing spaces too: the header's lede became the authors'
# line and "We extend the results of …", and "From now on" became "From here on" (2026-10-25, commit 48710ae "Human
# copy"); the footer's five lines became his definition of the expanded product (2026-10-24, commit 35dd836 "Edits"),
# the sentence on the hex codes moving, reworded, to the top of the remarks (HEX_NOTE) and Claude's line on 416 going
# (its TODO comment, an insertion, went in b475924 the same day).
TABLE_UPDATE += (('  <p class="lede">Table 2 of the paper by Buhler, Golan, Pratt, and Wagon (<i>Math. Comp.</i> 90, 2021), extended with new results.</p>\n',
                  '  <p class="lede">Stan Wagon, Daniel Reeves, Claude, and Astra</p>\n'
                  '  <p class="lede">\n'
                  '    We extend the results of \n'
                  '    Table 2 of the paper by Buhler, Golan, Pratt, and Wagon (<i>Math. Comp.</i> 90, 2021).</p>\n', 1),
                 ('    From now on we use the convention', '    From here on we use the convention', 1),
                 ('  <p>The first three blocks are copied from Table 2 of the published paper.</p>\n'
                  '  <p>The hex codes follow the paper\'s Table 5 convention: the left half of the signs <span class="nw">(1 = +1, 0 = −1)</span>, then the rest by <span class="nw">(−1)<sup><i>m</i></sup></span> symmetry.</p>\n'
                  '  <p>The sign # denotes the expanded product, <span class="nw"><i>f</i> # <i>g</i> = <i>f</i>(<i>x</i>)·<i>g</i>(<i>x</i><sup><i>n<sub>f</sub></i></sup>)</span>, where <i>n<sub>f</sub></i> is the length of <i>f</i>. The sign ∨ denotes the join.</p>\n'
                  '  <p>Every example whose code is given here was checked by Claude with exact integer power sums.</p>\n'
                  '  <p>Claude: "BGPW\'s example at length 416 was not re-checked here."</p>\n',
                  '  <p>Definition (expanded product): \n'
                  '    <span class="nw"><i>f</i> # <i>g</i> = <i>f</i>(<i>x</i>)·<i>g</i>(<i>x</i><sup><i>n<sub>f</sub></i></sup>)</span>, where <i>n<sub>f</sub></i> is the length of <i>f</i>. \n'
                  '    And the symbol ∨ means the join.</p>\n', 1))

# The results of 2026-10-25 (scratch/record-20261025/page/apply_record.py): the new results' cells (592, 608 and 656
# settled at 10 and 848, 880, 896, 928, 944, 976 and 992 at 11 by examples, 752 bounded by 10 by proof752.py); a
# new category, Claude and Astra, for 592, 608, 656 and 752: its legend line, in the form of dreeves's legend (so
# unattributed), and its CSS, Claude and BGPW's mutatis mutandis; and the ten code blocks and sets, data that the
# copy quals would read as English: 592's, 608's and 656's blocks before 800's, the rest after it, where their
# remarks are inserted around them, and the sets after 800's.
TABLE_UPDATE += (('<td class="c" title=\'Claude alone\'>592</td><td class="c" title=\'Claude alone\'>608</td><td class="c" title=\'Claude alone\'>624</td><td class="c" title=\'Claude alone\'>640</td><td class="c" title=\'Claude alone\'>656</td></tr>', '<td class="ca" title=\'Claude and Astra\'>592</td><td class="ca" title=\'Claude and Astra\'>608</td><td class="c" title=\'Claude alone\'>624</td><td class="c" title=\'Claude alone\'>640</td><td class="ca" title=\'Claude and Astra\'>656</td></tr>', 1),
                 ('<td class="c">10–12</td><td class="c">9–10</td><td class="c">9–10</td><td class="c">10–12</td><td class="c">10</td><td class="c">9–10</td></tr>', '<td class="c">10–12</td><td class="ca">10</td><td class="ca">10</td><td class="c">10–12</td><td class="c">10</td><td class="ca">10</td></tr>', 1),
                 ('<td class="c" title=\'Claude alone\'>752</td>', '<td class="ca" title=\'Claude and Astra\'>752</td>', 1),
                 ('<td class="c">10</td><td class="c">9–11</td><td class="c">11–13</td>', '<td class="c">10</td><td class="ca">9–10</td><td class="c">11–13</td>', 1),
                 ('(<i>n</i>)</th><td class="c">9–11</td><td class="c">12–14</td><td class="c">10–11</td><td class="c">10–11</td><td class="c">11–13</td><td class="c">10–11</td><td class="c">10–11</td><td class="c">13–15</td><td class="c">10–11</td><td class="c">10–11</td></tr>', '(<i>n</i>)</th><td class="c">11</td><td class="c">12–14</td><td class="c">11</td><td class="c">11</td><td class="c">11–13</td><td class="c">11</td><td class="c">11</td><td class="c">13–15</td><td class="c">11</td><td class="c">11</td></tr>', 1),
                 ('    <li><span class="key a" aria-hidden="true">✦</span>Astra alone</li>\n', '    <li><span class="key a" aria-hidden="true">✦</span>Astra alone</li>\n    <li><span class="key ca" aria-hidden="true"><span>◆✦</span></span>Claude and Astra</li>\n', 1),
                 ('td.j { --glyph: "◆●"; }\n', 'td.j { --glyph: "◆●"; }\ntd.ca { --glyph: "◆✦"; }\n', 1),
                 ('tr.ns td.j::before, .key.j > span, .remarks li.j .mk { background: linear-gradient(90deg, var(--claude) 50%, var(--stan) 50%); -webkit-background-clip: text; background-clip: text; color: transparent; }\n', 'tr.ns td.j::before, .key.j > span, .remarks li.j .mk { background: linear-gradient(90deg, var(--claude) 50%, var(--stan) 50%); -webkit-background-clip: text; background-clip: text; color: transparent; }\n/* Claude and Astra (2026-10-25): as Claude and BGPW, stripes of the two tints over a striped bar, its glyph half in each hue */\ntd.ca, .key.ca { background: repeating-linear-gradient(135deg, color-mix(in oklab, var(--claude) var(--tint), var(--paper)) 0 0.3rem, color-mix(in oklab, var(--astra) var(--tint), var(--paper)) 0.3rem 0.6rem); }\ntr.vals td.ca, .key.ca { background: repeating-linear-gradient(90deg, var(--claude) 0 0.3rem, var(--astra) 0.3rem 0.6rem) bottom / 100% 3px no-repeat, repeating-linear-gradient(135deg, color-mix(in oklab, var(--claude) var(--tint), var(--paper)) 0 0.3rem, color-mix(in oklab, var(--astra) var(--tint), var(--paper)) 0.3rem 0.6rem); box-shadow: none; }\ntr.ns td.ca::before, .key.ca > span, .remarks li.ca .mk { background: linear-gradient(90deg, var(--claude) 50%, var(--astra) 50%); -webkit-background-clip: text; background-clip: text; color: transparent; }\n', 1),
                 ('    </li>\n      <p class="code">\n        <span><i>p</i><sub>800</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n', '    </li>\n      <p class="code">\n        <span><i>p</i><sub>592</sub> <span class="nw">(<i>m</i> = 10)</span>:</span>\n        <code>93CC6790EA26876D2DDA793492C92EB24C3B934525B66DADF25926920BA79E4D21B2CB359A</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>608</sub> <span class="nw">(<i>m</i> = 10)</span>:</span>\n        <code>AC965934D659969A4CE792CD6492D72C836BE49E193612E97792C9AAB265AC867BAE921924D7</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>656</sub> <span class="nw">(<i>m</i> = 10)</span>:</span>\n        <code>C32DA6E924AED161B6D94216DB6CBE4A4932FD4996135826A94DF6CA6CB4DA1EB4D90D92134D82F8EE</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>800</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n', 1),
                 ('        <code>966965968F2C965B25B44B25B3596D924B6D96496C964B65B2CB24B25B2C96CB6C97496CB2CD6E960B243A59A592DB2DB6D9</code>\n      </p>\n    <li class="j">\n', '        <code>966965968F2C965B25B44B25B3596D924B6D96496C964B65B2CB24B25B2C96CB6C97496CB2CD6E960B243A59A592DB2DB6D9</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>848</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n        <code>96B905B25BADB2496D32C924B74B6C96596CF25964B28925B25B6DAA5B6D96C965164B14B2C92F52D12596C97CB6CBEC86592CB2C9</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>880</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n        <code>C965B1C92D925B6C92D964BE4D2FB20B6592492D16D9259ADB6FD64926964925A64B6E62EF60D2CB24B6D925B2CB05960B6CB6CB75B74F</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>896</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n        <code>B25B2D92512CD65BA5B2DB2514CD65B8CB698E6364E65905B6196D12C82CBADB3DB6E32C9659ACB6D96512492C9ECB2196DB2C92D944B259</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>928</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n        <code>869B4DEE9A60A4D14BA2D35DA4DA6D14F349E65B4C27926C54D36D268358369F29B6936DA6BA69269A65259349A4D86D765349B49A69BA9F65B4</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>944</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n        <code>B2D920F6C32D8A4A75B6E965D2D964B44968F291A432D97C96F964B2586CB47B64965B2DBE4934929B4C125B6D93494F92CB2DBA436596896D7ADA</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>976</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n        <code>A69A48B5DB6B269A6D14CA1936324D74DB6833DB6DB4DB4134921D949A68E6986F25DA6D348F4994935D86BB49E69ACC27D067268769B4D219B67249A4</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>992</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n        <code>94E96372496EB6496DB2D364864B2D902967B24E2DBF7B71908D6D92DA44905B4EF2CD2596CB7192D944B2C8ECB60967B24E25B2DB24BA5F2D96DB859749</code>\n      </p>\n    <li class="j">\n', 1),
                 ('  779, 780, 783, 785, 786, 788, 791, 792, 795, 797, 798};</code></pre>', '  779, 780, 783, 785, 786, 788, 791, 792, 795, 797, 798};\nSClaude[10][592] = {\n  0, 3, 6, 7, 8, 9, 12, 13, 17, 18, 21, 22, 23, 24, 27, 32, 33, 34,\n  36, 38, 42, 45, 46, 48, 53, 54, 55, 57, 58, 60, 61, 63, 66, 68, 69,\n  71, 72, 73, 75, 76, 78, 81, 82, 83, 84, 87, 90, 91, 93, 96, 99,\n  102, 104, 105, 108, 111, 114, 116, 117, 118, 120, 122, 123, 126,\n  129, 132, 133, 138, 139, 140, 142, 143, 144, 147, 150, 151, 153,\n  157, 159, 162, 165, 167, 168, 170, 171, 173, 174, 177, 178, 180,\n  181, 183, 184, 186, 188, 189, 191, 192, 193, 194, 195, 198, 201,\n  203, 204, 207, 210, 213, 214, 216, 219, 222, 228, 230, 231, 232,\n  234, 237, 238, 239, 240, 243, 244, 245, 246, 249, 252, 253, 255,\n  258, 263, 264, 266, 267, 270, 272, 273, 276, 278, 279, 282, 283,\n  285, 287, 288, 291, 292, 294, 297, 299, 300, 303, 304, 306, 308,\n  309, 312, 313, 315, 318, 319, 321, 324, 325, 327, 328, 333, 336,\n  338, 339, 342, 345, 346, 347, 348, 351, 352, 353, 354, 357, 359,\n  360, 361, 363, 369, 372, 375, 377, 378, 381, 384, 387, 388, 390,\n  393, 396, 397, 398, 399, 400, 402, 403, 405, 407, 408, 410, 411,\n  413, 414, 417, 418, 420, 421, 423, 424, 426, 429, 432, 434, 438,\n  440, 441, 444, 447, 448, 449, 451, 452, 453, 458, 459, 462, 465,\n  468, 469, 471, 473, 474, 475, 477, 480, 483, 486, 487, 489, 492,\n  495, 498, 500, 501, 504, 507, 508, 509, 510, 513, 515, 516, 518,\n  519, 520, 522, 523, 525, 528, 530, 531, 533, 534, 536, 537, 538,\n  543, 545, 546, 549, 553, 555, 557, 558, 559, 564, 567, 568, 569,\n  570, 573, 574, 578, 579, 582, 583, 584, 585, 588, 591};\nSClaude[10][608] = {\n  0, 2, 4, 5, 8, 11, 13, 14, 17, 19, 20, 23, 26, 27, 29, 32, 33, 35,\n  37, 38, 41, 43, 44, 47, 48, 51, 53, 54, 56, 59, 60, 62, 65, 68, 69,\n  72, 73, 74, 77, 78, 79, 80, 83, 86, 88, 89, 92, 93, 95, 97, 98,\n  101, 104, 107, 110, 112, 113, 115, 117, 118, 119, 122, 124, 125,\n  128, 134, 135, 137, 138, 140, 142, 143, 144, 145, 146, 149, 152,\n  155, 156, 157, 158, 163, 164, 167, 170, 171, 173, 174, 179, 182,\n  184, 185, 186, 188, 191, 193, 194, 195, 197, 198, 199, 200, 203,\n  206, 208, 209, 212, 215, 216, 218, 220, 222, 224, 226, 227, 230,\n  233, 234, 237, 239, 240, 242, 244, 245, 248, 253, 254, 257, 258,\n  259, 260, 262, 263, 264, 266, 268, 269, 270, 272, 275, 278, 283,\n  284, 287, 290, 293, 296, 297, 299, 301, 302, 303, 304, 305, 306,\n  308, 310, 311, 314, 317, 320, 323, 324, 329, 332, 335, 337, 338,\n  339, 341, 343, 344, 345, 347, 348, 349, 350, 353, 354, 359, 362,\n  363, 365, 367, 368, 370, 373, 374, 377, 380, 381, 383, 385, 387,\n  389, 391, 392, 395, 398, 399, 401, 404, 407, 408, 409, 410, 412,\n  413, 414, 416, 419, 421, 422, 423, 425, 428, 433, 434, 436, 437,\n  440, 443, 444, 449, 450, 451, 452, 455, 458, 461, 462, 463, 464,\n  465, 467, 469, 470, 472, 473, 479, 482, 483, 485, 488, 489, 490,\n  492, 494, 495, 497, 500, 503, 506, 509, 510, 512, 514, 515, 518,\n  519, 521, 524, 527, 528, 529, 530, 533, 534, 535, 538, 539, 542,\n  545, 547, 548, 551, 553, 554, 556, 559, 560, 563, 564, 566, 569,\n  570, 572, 574, 575, 578, 580, 581, 584, 587, 588, 590, 593, 594,\n  596, 599, 602, 603, 605, 607};\nSClaude[10][656] = {\n  0, 1, 6, 7, 10, 12, 13, 15, 16, 18, 21, 22, 24, 25, 26, 28, 31, 34,\n  37, 40, 42, 44, 45, 46, 48, 49, 51, 55, 57, 58, 63, 64, 66, 67, 69,\n  70, 72, 73, 75, 76, 79, 81, 86, 91, 93, 94, 96, 97, 99, 100, 102,\n  103, 105, 106, 108, 109, 112, 114, 115, 116, 117, 118, 121, 124,\n  126, 129, 132, 135, 138, 139, 142, 144, 145, 146, 147, 148, 149,\n  151, 153, 156, 159, 160, 163, 165, 166, 171, 174, 175, 177, 179,\n  180, 186, 189, 190, 192, 194, 196, 199, 201, 204, 205, 207, 208,\n  209, 210, 211, 213, 214, 216, 217, 220, 222, 225, 226, 228, 229,\n  232, 234, 235, 237, 240, 241, 243, 244, 246, 251, 252, 253, 254,\n  256, 258, 259, 261, 264, 265, 267, 268, 271, 276, 277, 279, 280,\n  283, 286, 291, 294, 295, 297, 300, 301, 303, 304, 310, 312, 313,\n  314, 315, 316, 320, 321, 322, 324, 325, 326, 329, 330, 331, 333,\n  334, 335, 339, 340, 341, 342, 343, 345, 351, 352, 354, 355, 358,\n  360, 361, 364, 369, 372, 375, 376, 378, 379, 384, 387, 388, 390,\n  391, 394, 396, 397, 399, 401, 402, 403, 404, 409, 411, 412, 414,\n  415, 418, 420, 421, 423, 426, 427, 429, 430, 433, 435, 438, 439,\n  441, 442, 444, 445, 446, 447, 448, 450, 451, 454, 456, 459, 461,\n  463, 465, 466, 469, 475, 476, 478, 480, 481, 484, 489, 490, 492,\n  495, 496, 499, 502, 504, 506, 507, 508, 509, 510, 511, 513, 516,\n  517, 520, 523, 526, 529, 531, 534, 537, 538, 539, 540, 541, 543,\n  546, 547, 549, 550, 552, 553, 555, 556, 558, 559, 561, 562, 564,\n  569, 574, 576, 579, 580, 582, 583, 585, 586, 588, 589, 591, 592,\n  597, 598, 600, 604, 606, 607, 609, 610, 611, 613, 615, 618, 621,\n  624, 627, 629, 630, 631, 633, 634, 637, 639, 640, 642, 643, 645,\n  648, 649, 654, 655};\nSClaude[11][848] = {\n  0, 3, 5, 6, 8, 10, 11, 12, 15, 21, 23, 24, 26, 27, 30, 33, 35, 36,\n  38, 39, 40, 42, 44, 45, 47, 48, 50, 51, 54, 57, 60, 63, 65, 66, 68,\n  69, 71, 74, 75, 78, 80, 81, 84, 87, 90, 93, 96, 98, 99, 101, 102,\n  103, 105, 108, 110, 111, 113, 114, 116, 117, 120, 123, 125, 126,\n  129, 131, 132, 135, 137, 138, 140, 141, 144, 145, 146, 147, 150,\n  153, 155, 156, 159, 161, 162, 165, 168, 170, 171, 174, 176, 180,\n  183, 186, 189, 191, 192, 194, 195, 198, 201, 203, 204, 206, 207,\n  209, 210, 212, 213, 215, 216, 218, 220, 222, 225, 227, 228, 230,\n  231, 233, 234, 236, 237, 239, 240, 243, 245, 246, 248, 249, 252,\n  255, 257, 258, 261, 263, 267, 269, 270, 273, 276, 278, 279, 283,\n  285, 288, 290, 291, 294, 296, 297, 300, 303, 306, 308, 309, 310,\n  311, 313, 315, 318, 320, 321, 323, 327, 330, 333, 335, 336, 339,\n  341, 342, 344, 345, 348, 351, 353, 354, 355, 356, 357, 360, 362,\n  363, 365, 366, 368, 369, 372, 374, 375, 376, 377, 378, 380, 381,\n  384, 389, 390, 393, 395, 396, 399, 402, 404, 405, 408, 410, 411,\n  414, 416, 417, 420, 423, 425, 426, 428, 429, 432, 434, 435, 438,\n  440, 441, 444, 446, 447, 449, 450, 453, 455, 456, 459, 460, 461,\n  462, 464, 465, 468, 474, 476, 477, 480, 483, 486, 488, 489, 495,\n  497, 498, 500, 501, 504, 507, 509, 510, 513, 515, 516, 518, 519,\n  521, 522, 523, 525, 528, 530, 531, 533, 535, 540, 542, 543, 545,\n  546, 548, 549, 552, 554, 555, 558, 560, 561, 563, 565, 566, 567,\n  570, 572, 573, 575, 576, 579, 581, 582, 583, 585, 587, 588, 591,\n  593, 594, 596, 597, 600, 603, 605, 606, 609, 612, 615, 618, 621,\n  623, 624, 626, 628, 630, 633, 636, 639, 642, 645, 647, 648, 650,\n  651, 654, 657, 659, 660, 662, 663, 665, 666, 668, 669, 670, 672,\n  674, 675, 678, 680, 681, 683, 684, 687, 689, 690, 693, 695, 696,\n  698, 699, 704, 705, 708, 711, 713, 714, 717, 719, 720, 723, 725,\n  726, 728, 729, 732, 735, 738, 740, 741, 743, 747, 750, 752, 753,\n  755, 756, 758, 759, 761, 762, 764, 765, 768, 770, 771, 774, 775,\n  777, 780, 783, 785, 786, 788, 789, 791, 792, 794, 795, 798, 801,\n  804, 806, 810, 813, 815, 816, 818, 819, 822, 825, 827, 828, 829,\n  830, 831, 833, 834, 838, 840, 843, 845, 846};\nSClaude[11][880] = {\n  0, 1, 4, 7, 9, 10, 13, 15, 16, 18, 19, 23, 24, 25, 28, 31, 34, 36,\n  37, 39, 40, 43, 46, 49, 51, 52, 54, 55, 57, 58, 60, 61, 64, 67, 70,\n  72, 73, 75, 76, 79, 81, 82, 85, 88, 90, 91, 92, 93, 94, 97, 100,\n  101, 103, 106, 108, 109, 110, 111, 112, 114, 115, 118, 124, 126,\n  127, 129, 130, 133, 135, 136, 139, 142, 145, 148, 151, 154, 156,\n  157, 159, 163, 165, 166, 168, 169, 171, 172, 175, 178, 181, 183,\n  184, 187, 188, 190, 192, 193, 195, 196, 198, 199, 201, 202, 204,\n  205, 206, 207, 208, 209, 211, 213, 214, 217, 220, 223, 226, 229,\n  230, 232, 235, 237, 238, 241, 244, 247, 250, 253, 255, 256, 258,\n  261, 262, 265, 268, 270, 271, 273, 274, 276, 277, 278, 281, 282,\n  286, 288, 289, 290, 292, 293, 294, 295, 297, 298, 304, 305, 307,\n  310, 312, 313, 316, 318, 319, 322, 325, 328, 330, 331, 333, 334,\n  336, 337, 339, 340, 343, 346, 349, 351, 352, 354, 355, 358, 360,\n  361, 364, 366, 367, 373, 375, 376, 379, 381, 382, 388, 390, 391,\n  393, 394, 396, 397, 400, 402, 403, 405, 406, 408, 409, 412, 414,\n  415, 417, 418, 419, 421, 423, 424, 426, 427, 429, 430, 431, 433,\n  436, 437, 438, 439, 444, 445, 447, 451, 454, 457, 459, 463, 466,\n  468, 469, 472, 475, 478, 480, 481, 484, 487, 490, 492, 493, 494,\n  495, 496, 499, 501, 502, 505, 507, 508, 509, 510, 511, 514, 516,\n  517, 520, 522, 523, 526, 529, 531, 532, 534, 535, 537, 538, 541,\n  544, 547, 550, 552, 553, 555, 556, 558, 559, 562, 564, 565, 568,\n  570, 571, 573, 576, 577, 578, 579, 580, 583, 588, 592, 594, 595,\n  596, 599, 600, 604, 607, 610, 612, 613, 615, 616, 619, 620, 622,\n  625, 627, 628, 630, 631, 633, 634, 636, 637, 639, 640, 643, 645,\n  646, 648, 651, 652, 654, 655, 657, 658, 660, 661, 663, 664, 667,\n  669, 676, 679, 682, 685, 688, 690, 693, 694, 697, 699, 700, 702,\n  703, 705, 706, 709, 712, 715, 717, 718, 719, 721, 724, 726, 727,\n  729, 730, 732, 733, 735, 736, 738, 739, 741, 742, 745, 747, 748,\n  751, 754, 756, 757, 758, 759, 760, 762, 763, 766, 772, 774, 775,\n  777, 780, 781, 783, 784, 790, 792, 793, 795, 796, 799, 801, 802,\n  805, 808, 810, 811, 813, 814, 816, 817, 820, 823, 826, 829, 831,\n  832, 834, 835, 837, 838, 841, 844, 846, 847, 849, 850, 852, 853,\n  857, 858, 859, 862, 865, 867, 868, 871, 873, 874, 876, 877};\nSClaude[11][896] = {\n  0, 2, 3, 6, 9, 11, 12, 14, 15, 18, 20, 21, 23, 24, 27, 30, 33, 35,\n  39, 42, 44, 45, 48, 49, 51, 53, 54, 57, 59, 60, 62, 63, 64, 66, 69,\n  71, 72, 74, 75, 78, 80, 81, 83, 84, 86, 87, 90, 93, 95, 99, 101,\n  104, 105, 108, 109, 111, 113, 114, 117, 119, 120, 122, 123, 124,\n  128, 129, 132, 134, 135, 137, 138, 140, 143, 144, 148, 149, 150,\n  153, 154, 158, 159, 161, 162, 165, 168, 169, 170, 173, 174, 177,\n  179, 180, 183, 189, 191, 192, 194, 195, 197, 198, 203, 204, 207,\n  209, 210, 212, 213, 215, 219, 222, 224, 225, 228, 234, 236, 237,\n  240, 242, 243, 244, 246, 248, 249, 251, 252, 254, 255, 258, 259,\n  260, 261, 263, 264, 266, 267, 269, 270, 272, 273, 274, 278, 279,\n  282, 284, 285, 288, 291, 293, 294, 297, 299, 300, 303, 304, 306,\n  308, 309, 312, 314, 315, 317, 318, 320, 321, 323, 324, 327, 329,\n  330, 333, 335, 339, 342, 345, 348, 351, 354, 356, 357, 360, 363,\n  364, 365, 366, 368, 369, 372, 374, 375, 378, 383, 384, 387, 389,\n  390, 392, 393, 395, 396, 398, 399, 402, 404, 405, 408, 411, 414,\n  416, 417, 419, 420, 423, 425, 429, 432, 434, 435, 438, 441, 443,\n  444, 447, 449, 450, 453, 455, 456, 458, 459, 462, 464, 465, 467,\n  468, 469, 471, 473, 474, 477, 480, 482, 483, 485, 486, 488, 489,\n  492, 494, 495, 498, 501, 504, 507, 509, 510, 513, 514, 515, 516,\n  518, 519, 522, 524, 525, 528, 533, 534, 536, 537, 540, 542, 543,\n  545, 546, 548, 549, 551, 552, 554, 555, 557, 558, 559, 561, 563,\n  564, 567, 569, 570, 573, 576, 579, 582, 584, 585, 588, 590, 593,\n  594, 597, 599, 600, 603, 605, 606, 608, 609, 612, 614, 615, 618,\n  619, 620, 624, 627, 630, 633, 638, 639, 642, 645, 648, 650, 654,\n  656, 657, 660, 662, 663, 664, 665, 666, 668, 669, 672, 674, 675,\n  677, 678, 679, 681, 684, 687, 689, 690, 693, 694, 695, 696, 699,\n  702, 705, 707, 708, 709, 710, 711, 713, 714, 717, 719, 720, 723,\n  724, 728, 729, 731, 732, 735, 738, 739, 740, 743, 744, 748, 749,\n  750, 753, 754, 756, 759, 762, 764, 765, 768, 769, 770, 774, 777,\n  779, 780, 783, 785, 788, 789, 792, 793, 795, 797, 798, 799, 801,\n  803, 804, 806, 807, 810, 813, 816, 818, 819, 822, 825, 827, 828,\n  830, 834, 837, 839, 840, 843, 845, 848, 849, 852, 854, 855, 857,\n  858, 859, 861, 863, 864, 866, 867, 869, 870, 873, 876, 878, 879,\n  882, 885, 887, 888, 890, 891, 894};\nSClaude[11][928] = {\n  0, 5, 6, 8, 11, 12, 14, 15, 17, 20, 21, 23, 24, 25, 26, 28, 29, 30,\n  32, 35, 36, 38, 41, 42, 48, 50, 53, 56, 57, 59, 63, 65, 68, 70, 71,\n  72, 74, 78, 80, 81, 83, 86, 87, 89, 91, 92, 93, 95, 96, 98, 101,\n  104, 105, 107, 108, 110, 113, 114, 116, 117, 119, 123, 125, 128,\n  129, 130, 131, 134, 135, 137, 140, 143, 144, 145, 146, 149, 150,\n  153, 155, 156, 158, 159, 161, 164, 165, 170, 173, 174, 175, 176,\n  179, 182, 185, 186, 188, 189, 193, 195, 197, 200, 201, 203, 206,\n  207, 209, 210, 212, 213, 215, 218, 221, 222, 224, 230, 231, 233,\n  235, 236, 242, 243, 245, 246, 248, 251, 252, 253, 254, 255, 258,\n  260, 263, 264, 266, 267, 269, 270, 272, 275, 278, 279, 281, 282,\n  284, 285, 287, 288, 290, 293, 294, 296, 298, 299, 300, 302, 305,\n  306, 308, 311, 314, 317, 318, 320, 323, 324, 326, 329, 330, 333,\n  335, 338, 341, 343, 344, 347, 350, 351, 353, 356, 359, 360, 362,\n  365, 368, 369, 371, 372, 377, 378, 380, 381, 383, 385, 386, 387,\n  389, 390, 393, 395, 398, 399, 401, 404, 407, 408, 410, 411, 413,\n  416, 419, 420, 422, 425, 426, 428, 431, 432, 434, 435, 436, 438,\n  440, 443, 444, 445, 446, 447, 449, 450, 453, 455, 456, 458, 459,\n  461, 464, 465, 467, 470, 473, 475, 476, 479, 485, 486, 488, 490,\n  494, 497, 498, 500, 503, 504, 506, 509, 510, 512, 513, 515, 518,\n  521, 522, 524, 525, 527, 530, 531, 533, 535, 536, 539, 543, 545,\n  548, 551, 552, 553, 554, 557, 560, 561, 563, 564, 566, 569, 570,\n  572, 573, 575, 578, 579, 581, 582, 585, 587, 588, 590, 591, 593,\n  595, 596, 599, 600, 602, 605, 606, 608, 611, 612, 614, 615, 617,\n  618, 620, 623, 624, 626, 630, 632, 635, 636, 638, 641, 644, 647,\n  650, 651, 653, 654, 656, 659, 662, 665, 666, 668, 670, 671, 677,\n  678, 680, 683, 686, 687, 688, 689, 690, 693, 695, 698, 699, 700,\n  701, 702, 704, 707, 708, 710, 711, 713, 716, 719, 722, 723, 725,\n  728, 729, 731, 733, 735, 736, 737, 740, 743, 744, 746, 747, 749,\n  750, 755, 756, 758, 759, 760, 761, 764, 765, 767, 770, 773, 775,\n  776, 779, 780, 785, 786, 788, 789, 791, 794, 795, 800, 801, 803,\n  805, 806, 807, 809, 812, 815, 816, 818, 821, 824, 825, 827, 828,\n  830, 833, 837, 839, 842, 843, 845, 848, 850, 851, 852, 854, 858,\n  860, 861, 863, 865, 866, 867, 869, 872, 873, 875, 876, 878, 880,\n  881, 882, 883, 884, 887, 888, 890, 893, 894, 896, 900, 905, 908,\n  909, 911, 914, 917, 918, 920, 923, 924, 925, 926};\nSClaude[11][944] = {\n  0, 2, 3, 6, 8, 9, 11, 12, 15, 18, 24, 25, 26, 27, 29, 30, 32, 33,\n  38, 39, 42, 44, 45, 47, 48, 52, 54, 57, 60, 62, 65, 66, 67, 69, 71,\n  72, 74, 75, 77, 78, 80, 81, 82, 84, 87, 89, 90, 93, 95, 96, 97, 99,\n  102, 104, 105, 107, 108, 111, 113, 114, 117, 120, 122, 123, 125,\n  129, 132, 135, 137, 138, 140, 144, 145, 146, 147, 150, 152, 155,\n  159, 160, 162, 165, 170, 171, 174, 176, 177, 179, 180, 183, 185,\n  186, 187, 188, 189, 192, 195, 197, 198, 200, 201, 202, 203, 204,\n  207, 209, 210, 213, 216, 218, 219, 222, 225, 227, 228, 233, 234,\n  236, 237, 240, 242, 243, 245, 249, 250, 251, 252, 254, 255, 257,\n  258, 261, 264, 267, 269, 270, 273, 275, 276, 278, 279, 282, 284,\n  285, 287, 288, 290, 291, 292, 293, 294, 297, 300, 303, 306, 307,\n  309, 312, 315, 318, 320, 323, 324, 326, 327, 329, 332, 333, 339,\n  342, 345, 347, 348, 350, 351, 353, 354, 356, 357, 359, 360, 363,\n  366, 367, 369, 372, 375, 377, 380, 381, 382, 383, 384, 387, 390,\n  392, 393, 396, 398, 399, 402, 404, 405, 407, 408, 410, 411, 412,\n  414, 417, 422, 423, 425, 426, 429, 431, 432, 435, 437, 438, 440,\n  444, 447, 449, 450, 452, 453, 455, 457, 458, 459, 460, 462, 464,\n  465, 467, 468, 470, 472, 474, 477, 480, 482, 487, 489, 492, 495,\n  497, 498, 500, 501, 502, 504, 507, 509, 510, 513, 515, 516, 519,\n  522, 523, 524, 525, 527, 528, 530, 534, 537, 540, 542, 543, 546,\n  548, 549, 552, 554, 555, 557, 558, 564, 565, 567, 569, 570, 572,\n  573, 575, 578, 579, 581, 582, 585, 588, 591, 594, 597, 599, 600,\n  602, 603, 605, 606, 607, 608, 609, 612, 613, 615, 618, 621, 622,\n  624, 626, 627, 629, 630, 632, 633, 635, 638, 639, 641, 642, 644,\n  645, 647, 648, 654, 657, 660, 662, 663, 666, 669, 671, 672, 675,\n  677, 678, 680, 681, 683, 684, 687, 690, 695, 696, 697, 699, 702,\n  704, 705, 708, 711, 712, 713, 714, 717, 719, 720, 722, 723, 726,\n  728, 729, 731, 732, 735, 737, 738, 744, 747, 749, 750, 752, 753,\n  759, 761, 762, 765, 768, 770, 771, 774, 775, 776, 777, 779, 780,\n  782, 785, 786, 787, 789, 790, 792, 794, 795, 800, 801, 802, 804,\n  807, 809, 810, 812, 813, 815, 816, 817, 819, 822, 824, 825, 827,\n  828, 831, 833, 834, 837, 840, 842, 843, 845, 849, 851, 852, 855,\n  857, 858, 860, 864, 867, 870, 873, 875, 879, 880, 882, 884, 885,\n  887, 888, 890, 892, 893, 894, 897, 900, 902, 903, 906, 907, 908,\n  909, 912, 915, 920, 921, 922, 923, 924, 926, 927, 929, 930, 933,\n  936, 938, 939, 942};\nSClaude[11][976] = {\n  0, 2, 5, 6, 8, 11, 12, 14, 17, 20, 24, 26, 27, 29, 31, 32, 33, 35,\n  36, 38, 39, 41, 42, 44, 46, 47, 50, 53, 54, 56, 59, 60, 62, 65, 66,\n  68, 69, 71, 75, 77, 80, 81, 84, 86, 91, 92, 95, 98, 99, 101, 102,\n  106, 107, 110, 113, 116, 117, 119, 121, 122, 123, 125, 128, 129,\n  131, 132, 134, 135, 137, 138, 140, 146, 147, 150, 151, 152, 153,\n  155, 156, 158, 159, 161, 162, 164, 165, 167, 168, 170, 171, 173,\n  176, 177, 179, 180, 182, 183, 185, 191, 194, 195, 197, 200, 203,\n  206, 211, 212, 213, 215, 216, 219, 221, 224, 227, 228, 230, 233,\n  234, 236, 240, 241, 242, 245, 246, 248, 251, 252, 257, 258, 260,\n  261, 262, 263, 266, 269, 271, 272, 273, 275, 276, 278, 281, 282,\n  284, 285, 287, 290, 291, 293, 296, 300, 301, 302, 303, 305, 308,\n  311, 312, 315, 317, 320, 323, 326, 327, 329, 331, 332, 333, 335,\n  336, 341, 342, 344, 346, 347, 348, 350, 351, 353, 356, 359, 360,\n  361, 362, 365, 366, 368, 371, 372, 374, 376, 377, 380, 381, 386,\n  389, 390, 391, 392, 393, 395, 401, 402, 405, 406, 407, 410, 413,\n  414, 416, 421, 422, 423, 425, 426, 428, 431, 432, 434, 435, 437,\n  440, 441, 443, 446, 451, 452, 455, 456, 458, 459, 461, 462, 465,\n  466, 467, 470, 473, 476, 479, 480, 482, 485, 488, 489, 491, 492,\n  494, 497, 498, 500, 501, 503, 504, 506, 507, 511, 512, 515, 518,\n  521, 522, 525, 526, 527, 528, 530, 531, 533, 536, 537, 539, 542,\n  545, 546, 548, 551, 555, 556, 557, 558, 560, 563, 564, 566, 567,\n  571, 572, 575, 576, 577, 578, 579, 581, 587, 588, 590, 591, 592,\n  593, 596, 597, 600, 602, 605, 606, 608, 611, 612, 617, 618, 620,\n  621, 623, 626, 630, 632, 635, 636, 637, 638, 641, 645, 647, 650,\n  651, 653, 654, 656, 657, 659, 661, 662, 665, 666, 668, 669, 671,\n  676, 677, 678, 680, 681, 683, 686, 687, 689, 692, 695, 696, 698,\n  701, 705, 707, 708, 710, 711, 716, 719, 720, 721, 722, 725, 726,\n  728, 731, 732, 736, 737, 738, 740, 743, 744, 746, 749, 750, 752,\n  753, 755, 757, 758, 761, 765, 766, 767, 768, 770, 771, 773, 774,\n  776, 777, 779, 782, 783, 785, 786, 787, 788, 789, 791, 794, 797,\n  800, 801, 803, 806, 809, 812, 815, 818, 821, 826, 827, 830, 831,\n  832, 833, 834, 836, 839, 842, 845, 848, 849, 851, 855, 857, 860,\n  861, 863, 864, 866, 867, 870, 871, 872, 875, 878, 879, 881, 882,\n  885, 886, 887, 888, 890, 892, 893, 896, 897, 899, 901, 902, 903,\n  905, 908, 911, 912, 914, 917, 918, 920, 923, 924, 926, 927, 930,\n  932, 935, 938, 941, 945, 947, 950, 952, 953, 954, 956, 957, 959,\n  960, 962, 965, 966, 968, 971, 972, 974};\nSClaude[11][992] = {\n  0, 3, 5, 8, 9, 10, 12, 15, 17, 18, 22, 23, 25, 26, 27, 30, 33, 36,\n  39, 41, 42, 44, 45, 46, 48, 50, 51, 53, 54, 57, 60, 63, 65, 66, 68,\n  69, 71, 72, 74, 75, 78, 80, 81, 83, 86, 87, 89, 90, 93, 96, 101,\n  102, 105, 108, 110, 111, 114, 116, 117, 119, 120, 123, 130, 132,\n  135, 137, 138, 141, 142, 143, 144, 146, 147, 150, 153, 156, 157,\n  158, 162, 164, 165, 167, 168, 170, 171, 172, 173, 174, 175, 177,\n  178, 179, 180, 182, 183, 185, 186, 187, 191, 192, 195, 200, 204,\n  205, 207, 209, 210, 212, 213, 215, 216, 219, 222, 224, 225, 227,\n  228, 230, 233, 237, 240, 243, 249, 251, 252, 254, 255, 257, 260,\n  261, 262, 264, 265, 266, 267, 270, 272, 273, 276, 277, 279, 282,\n  285, 287, 288, 291, 293, 294, 296, 297, 300, 302, 303, 305, 306,\n  307, 311, 312, 315, 318, 320, 321, 323, 324, 327, 329, 333, 336,\n  338, 339, 342, 344, 345, 348, 352, 353, 354, 356, 357, 360, 362,\n  363, 365, 366, 372, 375, 377, 378, 381, 382, 383, 384, 386, 387,\n  390, 393, 396, 397, 398, 402, 405, 407, 408, 410, 411, 414, 416,\n  417, 419, 420, 422, 423, 426, 429, 432, 434, 435, 436, 438, 441,\n  443, 444, 445, 446, 447, 450, 452, 453, 455, 456, 459, 461, 462,\n  464, 465, 467, 468, 470, 471, 472, 477, 479, 480, 483, 485, 486,\n  487, 489, 492, 495, 497, 498, 500, 501, 503, 507, 509, 510, 513,\n  515, 516, 517, 518, 522, 525, 528, 531, 533, 534, 537, 540, 542,\n  543, 549, 551, 552, 554, 558, 560, 561, 563, 564, 566, 567, 570,\n  573, 576, 578, 579, 582, 585, 587, 588, 590, 591, 592, 596, 597,\n  599, 600, 602, 603, 606, 611, 612, 615, 617, 618, 620, 621, 622,\n  623, 624, 627, 630, 632, 633, 636, 640, 641, 642, 644, 645, 648,\n  650, 651, 654, 656, 657, 659, 660, 661, 663, 665, 666, 669, 672,\n  674, 675, 677, 678, 681, 682, 683, 687, 690, 692, 693, 696, 699,\n  701, 702, 705, 707, 708, 710, 711, 713, 716, 717, 720, 722, 723,\n  728, 732, 733, 735, 738, 741, 743, 744, 745, 746, 747, 749, 750,\n  752, 753, 755, 756, 757, 759, 760, 762, 765, 768, 770, 771, 773,\n  774, 777, 780, 783, 785, 788, 789, 790, 792, 793, 794, 795, 797,\n  798, 801, 802, 803, 807, 810, 815, 822, 825, 828, 830, 831, 832,\n  836, 837, 839, 840, 842, 843, 846, 851, 852, 855, 857, 858, 860,\n  862, 863, 864, 865, 866, 867, 869, 870, 873, 876, 878, 879, 882,\n  884, 885, 887, 888, 891, 892, 893, 894, 896, 897, 899, 900, 903,\n  906, 907, 909, 912, 914, 915, 918, 921, 924, 927, 929, 930, 932,\n  933, 935, 936, 939, 942, 944, 948, 951, 953, 954, 956, 957, 959,\n  960, 962, 963, 967, 970, 971, 972, 975, 977, 978, 980, 984, 985,\n  987, 989, 990};</code></pre>', 1))

# The powers of 2 once 592, 608 and 656 reached order 10 and 848, 880, 896, 928, 944, 976 and 992 order 11
# (2026-10-25): 2^20, 2^30, 2^37, 2^65 and 2^72 added, the first powers of 2 known to beat Thue-Morse by 2, 3, 4, 8
# and 9, and 2^24, 2^33, 2^49 and 2^51 raised, the rows split after 2^38 (2^34 until then); and 304's remark, which
# said 2^20 had order 21, now saying 22
TABLE_UPDATE += (('        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td title=\'The published paper (2021)\'>2<sup>3</sup></td><td title=\'The published paper (2021)\'>2<sup>4</sup></td><td title=\'The published paper (2021)\'>2<sup>5</sup></td><td title=\'The published paper (2021)\'>2<sup>6</sup></td><td title=\'The published paper (2021)\'>2<sup>7</sup></td><td title=\'The published paper (2021)\'>2<sup>8</sup></td><td class="c" title=\'Claude alone\'>2<sup>9</sup></td><td class="c" title=\'Claude alone\'>2<sup>17</sup></td><td class="c" title=\'Claude alone\'>2<sup>18</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>27</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>34</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td class="c">9</td><td class="c">18–20</td><td class="c">19–21</td><td class="j">25–29</td><td class="c">29–33</td><td class="c">35–40</td><td class="c">37–41</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>2<sup>38</sup></td><td class="c" title=\'Claude alone\'>2<sup>41</sup></td><td class="c" title=\'Claude alone\'>2<sup>46</sup></td><td class="c" title=\'Claude alone\'>2<sup>48</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>52</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>61</sup></td><td class="c" title=\'Claude alone\'>2<sup>66</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td><td class="c" title=\'Claude alone\'>2<sup>71</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">42–46</td><td class="c">45–50</td><td class="c">51–57</td><td class="c">53–59</td><td class="c">54–60</td><td class="j">56–63</td><td class="c">58–64</td><td class="c">64–70</td><td class="c">68–75</td><td class="c">74–82</td><td class="c">75–83</td><td class="c">79–88</td></tr>\n        </table>\n', '        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td title=\'The published paper (2021)\'>2<sup>3</sup></td><td title=\'The published paper (2021)\'>2<sup>4</sup></td><td title=\'The published paper (2021)\'>2<sup>5</sup></td><td title=\'The published paper (2021)\'>2<sup>6</sup></td><td title=\'The published paper (2021)\'>2<sup>7</sup></td><td title=\'The published paper (2021)\'>2<sup>8</sup></td><td class="c" title=\'Claude alone\'>2<sup>9</sup></td><td class="c" title=\'Claude alone\'>2<sup>17</sup></td><td class="c" title=\'Claude alone\'>2<sup>18</sup></td><td class="c" title=\'Claude alone\'>2<sup>20</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>27</sup></td><td class="c" title=\'Claude alone\'>2<sup>30</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>34</sup></td><td class="c" title=\'Claude alone\'>2<sup>37</sup></td><td class="c" title=\'Claude alone\'>2<sup>38</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td class="c">9</td><td class="c">18–20</td><td class="c">19–21</td><td class="c">22–23</td><td class="j">26–29</td><td class="c">29–33</td><td class="c">33–36</td><td class="c">36–40</td><td class="c">37–41</td><td class="c">41–45</td><td class="c">42–46</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>2<sup>41</sup></td><td class="c" title=\'Claude alone\'>2<sup>46</sup></td><td class="c" title=\'Claude alone\'>2<sup>48</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>52</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>61</sup></td><td class="c" title=\'Claude alone\'>2<sup>65</sup></td><td class="c" title=\'Claude alone\'>2<sup>66</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td><td class="c" title=\'Claude alone\'>2<sup>71</sup></td><td class="c" title=\'Claude alone\'>2<sup>72</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">45–50</td><td class="c">51–57</td><td class="c">53–59</td><td class="c">55–60</td><td class="j">57–63</td><td class="c">58–64</td><td class="c">64–70</td><td class="c">68–75</td><td class="c">73–81</td><td class="c">74–82</td><td class="c">75–83</td><td class="c">79–88</td><td class="c">81–89</td></tr>\n        </table>\n', 1),
                 ('2<sup>20</sup> now has order 21 another way: the 2<sup>18</sup> entry below, each product times τ<sub>2</sub>."</p>\n', '2<sup>20</sup> now has order 22 another way: the 2<sup>20</sup> entry below."</p>\n', 1),
                 ('though 2^20 now has order 21 another way, the 2^18 entry times tau_2 -->\n', 'though 2^20 now has order 22 another way, the 2^20 entry below -->\n', 1))

# The second recording pass (2026-10-26, scratch/record-20261025/page2/apply_record2.py): 752 and 784 settled at
# 10 and 832 at 11 by examples, 784 credited to Claude and Astra as 592, 608, 656 and 752 are: 784's cell and the
# three values; the three code blocks, data that the copy quals would read as English, 752's and 784's after
# 656's and 832's after 800's, where their remarks are inserted around them; and the sets after 992's.
TABLE_UPDATE += (('<td class="c" title=\'Claude alone\'>784</td>', '<td class="ca" title=\'Claude and Astra\'>784</td>', 1),
                 ('<td class="ca">9–10</td><td class="c">11–13</td><td class="c">9–10</td><td class="c">11</td><td class="c">10–14</td><td class="c">10–11</td></tr>', '<td class="ca">10</td><td class="c">11–13</td><td class="ca">10</td><td class="c">11</td><td class="c">10–14</td><td class="c">11</td></tr>', 1),
                 ('        <code>C32DA6E924AED161B6D94216DB6CBE4A4932FD4996135826A94DF6CA6CB4DA1EB4D90D92134D82F8EE</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>800</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n', '        <code>C32DA6E924AED161B6D94216DB6CBE4A4932FD4996135826A94DF6CA6CB4DA1EB4D90D92134D82F8EE</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>752</sub> <span class="nw">(<i>m</i> = 10)</span>:</span>\n        <code>D1C7951270B6456FBEC039A7FA05A459E422DB6416E76D06DB2D90D32FD010FBB30A6DB6D80DBAC3059EDB5826CB4C</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>784</sub> <span class="nw">(<i>m</i> = 10)</span>:</span>\n        <code>B24F643A19DC1B49FC831C2FF25926F80B24FFC1B423C92E933B25304F60FA2B341F59FFB668379251243048E2BE6BA89F</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>800</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n', 1),
                 ('        <code>966965968F2C965B25B44B25B3596D924B6D96496C964B65B2CB24B25B2C96CB6C97496CB2CD6E960B243A59A592DB2DB6D9</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>848</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n', '        <code>966965968F2C965B25B44B25B3596D924B6D96496C964B65B2CB24B25B2C96CB6C97496CB2CD6E960B243A59A592DB2DB6D9</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>832</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n        <code>B49969329E6934CB4DB69B4D34924C359B4926DB69A4DB49369F69261A4D36D6499A926D2C9B68B4D369A4D2DDB6904936DA69B4</code>\n      </p>\n      <p class="code">\n        <span><i>p</i><sub>848</sub> <span class="nw">(<i>m</i> = 11)</span>:</span>\n', 1),
                 ('  987, 989, 990};</code></pre>', '  987, 989, 990};\nSClaude[10][752] = {\n  0, 1, 3, 7, 8, 9, 13, 14, 15, 16, 19, 21, 23, 27, 30, 33, 34, 35,\n  40, 42, 43, 45, 46, 49, 53, 55, 57, 58, 60, 61, 62, 63, 64, 66, 67,\n  68, 69, 70, 72, 73, 82, 83, 84, 87, 88, 90, 93, 94, 95, 96, 97, 98,\n  99, 100, 102, 109, 111, 112, 114, 117, 121, 123, 124, 127, 128,\n  129, 130, 133, 138, 142, 144, 145, 147, 148, 150, 151, 153, 154,\n  157, 163, 165, 166, 168, 169, 170, 173, 174, 175, 177, 178, 180,\n  181, 183, 189, 190, 192, 193, 195, 196, 198, 199, 202, 204, 205,\n  207, 208, 211, 216, 217, 219, 222, 223, 226, 228, 229, 230, 231,\n  232, 233, 235, 243, 248, 249, 250, 251, 252, 254, 255, 256, 258,\n  259, 262, 263, 268, 270, 273, 274, 276, 277, 279, 280, 282, 283,\n  285, 286, 288, 289, 291, 292, 300, 301, 303, 304, 306, 307, 308,\n  310, 312, 313, 318, 319, 325, 327, 328, 331, 332, 333, 334, 336,\n  337, 339, 340, 342, 343, 345, 347, 348, 354, 357, 358, 360, 361,\n  364, 366, 367, 369, 372, 373, 378, 379, 382, 384, 385, 387, 390,\n  391, 393, 394, 397, 403, 404, 406, 408, 409, 411, 412, 414, 415,\n  417, 418, 419, 420, 423, 424, 426, 432, 433, 438, 439, 441, 443,\n  444, 445, 447, 448, 450, 451, 459, 460, 462, 463, 465, 466, 468,\n  469, 471, 472, 474, 475, 477, 478, 481, 483, 488, 489, 492, 493,\n  495, 496, 497, 499, 500, 501, 502, 503, 508, 516, 518, 519, 520,\n  521, 522, 523, 525, 528, 529, 532, 534, 535, 540, 543, 544, 546,\n  547, 549, 552, 553, 555, 556, 558, 559, 561, 562, 568, 570, 571,\n  573, 574, 576, 577, 578, 581, 582, 583, 585, 586, 588, 594, 597,\n  598, 600, 601, 603, 604, 606, 607, 609, 613, 618, 621, 622, 623,\n  624, 627, 628, 630, 634, 637, 639, 640, 642, 649, 651, 652, 653,\n  654, 655, 656, 657, 658, 661, 663, 664, 667, 668, 669, 678, 679,\n  681, 682, 683, 684, 685, 687, 688, 689, 690, 691, 693, 694, 696,\n  698, 702, 705, 706, 708, 709, 711, 716, 717, 718, 721, 724, 728,\n  730, 732, 735, 736, 737, 738, 742, 743, 744, 748, 750, 751};\nSClaude[10][784] = {\n  0, 2, 3, 6, 9, 12, 13, 14, 15, 17, 18, 21, 26, 27, 28, 30, 35, 36,\n  39, 40, 41, 43, 44, 45, 51, 52, 54, 55, 57, 60, 63, 64, 65, 66, 67,\n  68, 69, 72, 78, 79, 83, 84, 85, 90, 92, 93, 94, 95, 96, 97, 98, 99,\n  102, 105, 107, 108, 111, 114, 117, 118, 120, 121, 122, 123, 124,\n  132, 134, 135, 138, 141, 144, 145, 146, 147, 148, 149, 150, 151,\n  152, 153, 159, 160, 162, 163, 165, 170, 174, 175, 176, 177, 180,\n  183, 186, 188, 189, 190, 192, 195, 198, 199, 202, 203, 204, 206,\n  207, 210, 213, 215, 218, 219, 225, 228, 229, 230, 231, 233, 234,\n  240, 241, 242, 243, 244, 246, 250, 252, 254, 255, 258, 259, 261,\n  267, 268, 269, 270, 271, 273, 275, 276, 279, 280, 281, 282, 283,\n  284, 285, 286, 287, 288, 290, 291, 293, 294, 297, 298, 300, 306,\n  307, 309, 310, 311, 312, 315, 318, 321, 323, 327, 330, 333, 338,\n  339, 345, 348, 352, 353, 354, 358, 360, 362, 363, 364, 365, 366,\n  369, 370, 372, 374, 375, 376, 378, 380, 384, 387, 388, 389, 390,\n  391, 392, 393, 394, 395, 396, 399, 403, 405, 407, 408, 409, 411,\n  413, 414, 417, 418, 419, 420, 421, 423, 425, 429, 430, 431, 435,\n  438, 444, 445, 450, 453, 456, 460, 462, 465, 468, 471, 472, 473,\n  474, 476, 477, 483, 485, 486, 489, 490, 492, 493, 495, 496, 497,\n  498, 499, 500, 501, 502, 503, 504, 507, 508, 510, 512, 513, 514,\n  515, 516, 522, 524, 525, 528, 529, 531, 533, 537, 539, 540, 541,\n  542, 543, 549, 550, 552, 553, 554, 555, 558, 564, 565, 568, 570,\n  573, 576, 577, 579, 580, 581, 584, 585, 588, 591, 593, 594, 595,\n  597, 600, 603, 606, 607, 608, 609, 613, 618, 620, 621, 623, 624,\n  630, 631, 632, 633, 634, 635, 636, 637, 638, 639, 642, 645, 648,\n  649, 651, 659, 660, 661, 662, 663, 665, 666, 669, 672, 675, 676,\n  678, 681, 684, 685, 686, 687, 688, 689, 690, 691, 693, 698, 699,\n  700, 704, 705, 711, 714, 715, 716, 717, 718, 719, 720, 723, 726,\n  728, 729, 731, 732, 738, 739, 740, 742, 743, 744, 747, 748, 753,\n  755, 756, 757, 762, 765, 766, 768, 769, 770, 771, 774, 777, 780,\n  781, 783};\nSClaude[11][832] = {\n  0, 2, 3, 5, 8, 11, 12, 15, 17, 18, 20, 23, 26, 27, 30, 32, 35, 36,\n  37, 38, 41, 42, 44, 47, 50, 51, 53, 56, 57, 60, 62, 63, 65, 68, 69,\n  71, 72, 74, 75, 77, 78, 80, 83, 84, 86, 87, 89, 92, 93, 95, 98, 99,\n  101, 104, 107, 110, 113, 116, 117, 122, 123, 125, 127, 128, 131,\n  132, 134, 135, 137, 140, 143, 146, 149, 150, 152, 153, 155, 156,\n  158, 159, 161, 162, 164, 167, 168, 170, 173, 176, 177, 179, 180,\n  182, 183, 185, 188, 191, 194, 195, 197, 198, 200, 203, 204, 205,\n  206, 207, 209, 210, 212, 215, 218, 221, 222, 227, 228, 230, 233,\n  236, 237, 239, 242, 243, 245, 246, 248, 249, 251, 253, 254, 257,\n  260, 263, 264, 267, 268, 270, 272, 275, 278, 281, 282, 284, 285,\n  287, 290, 292, 293, 296, 299, 300, 302, 303, 305, 306, 308, 312,\n  314, 315, 317, 320, 321, 323, 326, 327, 329, 330, 332, 335, 336,\n  338, 341, 344, 345, 347, 350, 352, 353, 355, 356, 357, 359, 360,\n  362, 363, 365, 366, 368, 371, 377, 380, 383, 386, 387, 389, 390,\n  392, 393, 395, 396, 398, 401, 402, 404, 407, 408, 410, 411, 413,\n  416, 417, 419, 422, 425, 426, 428, 431, 432, 434, 437, 440, 443,\n  446, 447, 449, 450, 452, 453, 455, 456, 457, 458, 459, 461, 462,\n  464, 467, 470, 473, 477, 480, 482, 483, 485, 488, 489, 491, 492,\n  494, 497, 498, 500, 503, 506, 507, 509, 512, 513, 515, 518, 520,\n  521, 522, 524, 527, 530, 533, 534, 536, 537, 540, 542, 543, 545,\n  548, 551, 552, 554, 555, 557, 558, 560, 562, 565, 566, 569, 570,\n  572, 573, 575, 576, 579, 581, 584, 587, 590, 591, 593, 596, 597,\n  599, 600, 602, 605, 606, 607, 608, 611, 612, 614, 615, 617, 618,\n  620, 623, 629, 630, 632, 635, 638, 639, 641, 642, 644, 645, 647,\n  650, 653, 656, 657, 659, 660, 662, 665, 666, 668, 671, 674, 677,\n  680, 683, 684, 686, 687, 689, 690, 692, 693, 695, 698, 701, 702,\n  705, 707, 710, 711, 712, 713, 716, 717, 719, 720, 722, 723, 725,\n  726, 728, 729, 731, 734, 735, 737, 740, 741, 743, 746, 749, 750,\n  752, 755, 758, 761, 764, 765, 767, 770, 772, 773, 776, 777, 779,\n  782, 783, 785, 786, 788, 791, 792, 797, 798, 800, 802, 803, 806,\n  807, 809, 810, 812, 815, 817, 818, 821, 822, 824, 825, 827, 830};</code></pre>', 1))

# The powers of 2 once 752 and 784 reached order 10 and 832 order 11 (2026-10-26): 2^43 and 2^68 added, the first
# powers of 2 known to beat Thue-Morse by 5 and 9, and 2^48 and 2^71 raised, the rows split after 2^41 (2^38 until
# then)
TABLE_UPDATE += (('        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td title=\'The published paper (2021)\'>2<sup>3</sup></td><td title=\'The published paper (2021)\'>2<sup>4</sup></td><td title=\'The published paper (2021)\'>2<sup>5</sup></td><td title=\'The published paper (2021)\'>2<sup>6</sup></td><td title=\'The published paper (2021)\'>2<sup>7</sup></td><td title=\'The published paper (2021)\'>2<sup>8</sup></td><td class="c" title=\'Claude alone\'>2<sup>9</sup></td><td class="c" title=\'Claude alone\'>2<sup>17</sup></td><td class="c" title=\'Claude alone\'>2<sup>18</sup></td><td class="c" title=\'Claude alone\'>2<sup>20</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>27</sup></td><td class="c" title=\'Claude alone\'>2<sup>30</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>34</sup></td><td class="c" title=\'Claude alone\'>2<sup>37</sup></td><td class="c" title=\'Claude alone\'>2<sup>38</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td class="c">9</td><td class="c">18–20</td><td class="c">19–21</td><td class="c">22–23</td><td class="j">26–29</td><td class="c">29–33</td><td class="c">33–36</td><td class="c">36–40</td><td class="c">37–41</td><td class="c">41–45</td><td class="c">42–46</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>2<sup>41</sup></td><td class="c" title=\'Claude alone\'>2<sup>46</sup></td><td class="c" title=\'Claude alone\'>2<sup>48</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>52</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>61</sup></td><td class="c" title=\'Claude alone\'>2<sup>65</sup></td><td class="c" title=\'Claude alone\'>2<sup>66</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td><td class="c" title=\'Claude alone\'>2<sup>71</sup></td><td class="c" title=\'Claude alone\'>2<sup>72</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">45–50</td><td class="c">51–57</td><td class="c">53–59</td><td class="c">55–60</td><td class="j">57–63</td><td class="c">58–64</td><td class="c">64–70</td><td class="c">68–75</td><td class="c">73–81</td><td class="c">74–82</td><td class="c">75–83</td><td class="c">79–88</td><td class="c">81–89</td></tr>\n        </table>\n', '        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td title=\'The published paper (2021)\'>2<sup>3</sup></td><td title=\'The published paper (2021)\'>2<sup>4</sup></td><td title=\'The published paper (2021)\'>2<sup>5</sup></td><td title=\'The published paper (2021)\'>2<sup>6</sup></td><td title=\'The published paper (2021)\'>2<sup>7</sup></td><td title=\'The published paper (2021)\'>2<sup>8</sup></td><td class="c" title=\'Claude alone\'>2<sup>9</sup></td><td class="c" title=\'Claude alone\'>2<sup>17</sup></td><td class="c" title=\'Claude alone\'>2<sup>18</sup></td><td class="c" title=\'Claude alone\'>2<sup>20</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>24</sup></td><td class="c" title=\'Claude alone\'>2<sup>27</sup></td><td class="c" title=\'Claude alone\'>2<sup>30</sup></td><td class="c" title=\'Claude alone\'>2<sup>33</sup></td><td class="c" title=\'Claude alone\'>2<sup>34</sup></td><td class="c" title=\'Claude alone\'>2<sup>37</sup></td><td class="c" title=\'Claude alone\'>2<sup>38</sup></td><td class="c" title=\'Claude alone\'>2<sup>41</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td class="c">9</td><td class="c">18–20</td><td class="c">19–21</td><td class="c">22–23</td><td class="j">26–29</td><td class="c">29–33</td><td class="c">33–36</td><td class="c">36–40</td><td class="c">37–41</td><td class="c">41–45</td><td class="c">42–46</td><td class="c">45–50</td></tr>\n        </table>\n        <table class="block">\n          <tr class="ns"><th scope="row"><i>n</i></th><td class="c" title=\'Claude alone\'>2<sup>43</sup></td><td class="c" title=\'Claude alone\'>2<sup>46</sup></td><td class="c" title=\'Claude alone\'>2<sup>48</sup></td><td class="c" title=\'Claude alone\'>2<sup>49</sup></td><td class="j" title=\'Claude and BGPW\'>2<sup>51</sup></td><td class="c" title=\'Claude alone\'>2<sup>52</sup></td><td class="c" title=\'Claude alone\'>2<sup>57</sup></td><td class="c" title=\'Claude alone\'>2<sup>61</sup></td><td class="c" title=\'Claude alone\'>2<sup>65</sup></td><td class="c" title=\'Claude alone\'>2<sup>66</sup></td><td class="c" title=\'Claude alone\'>2<sup>67</sup></td><td class="c" title=\'Claude alone\'>2<sup>68</sup></td><td class="c" title=\'Claude alone\'>2<sup>71</sup></td><td class="c" title=\'Claude alone\'>2<sup>72</sup></td></tr>\n          <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td class="c">48–53</td><td class="c">51–57</td><td class="c">54–59</td><td class="c">55–60</td><td class="j">57–63</td><td class="c">58–64</td><td class="c">64–70</td><td class="c">68–75</td><td class="c">73–81</td><td class="c">74–82</td><td class="c">75–83</td><td class="c">77–84</td><td class="c">80–88</td><td class="c">81–89</td></tr>\n        </table>\n', 1),)

# Edits of the remarks' lines that are in the page before the chart (BASE) or in TABLE_UPDATE, kept apart from
# TABLE_UPDATE because quals_pow2_page.py applies TABLE_UPDATE before its own edits of those remarks, and its own
# edit of 2026-10-17 covers these lines already: 800's example of order 11 (2026-10-17) moved the first power of 2
# that beats Thue-Morse by 1 to 2^17, which 2^24's sentence cites, and raised 2^51 to 56; once 592, 608 and 656
# reached order 10 and 848, 880, 896, 928, 944, 976 and 992 order 11 (2026-10-25), 2^51 rose to 57 and 2^24
# to 26, which that day's edit there covers too.
REMARK_UPDATE = (('and by the 2<sup>18</sup> entry above for every <span class="nw"><i>k</i> ≥ 18</span>."</p>', 'and by the 2<sup>17</sup> entry above for every <span class="nw"><i>k</i> ≥ 17</span>."</p>', 1),
                 ('<i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {55, …, 63}</span>', '<i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {56, …, 63}</span>', 1),
                 ('<i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {56, …, 63}</span>', '<i>n</i> = 2<sup>51</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {57, …, 63}</span>', 1),
                 ('<i>n</i> = 2<sup>24</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {25, …, 29}</span>', '<i>n</i> = 2<sup>24</sup>: &nbsp;<span class="nw"><i>m</i><sup>*</sup> ∈ {26, …, 29}</span>', 1))


def committed():
    """index.html as it was before the chart (BASE), with TABLE_UPDATE's edits made (each count asserted)."""
    text = subprocess.run(['git', '-C', HERE, 'show', f'{BASE}:index.html'], capture_output=True, text=True,
                          check=True).stdout
    for old, new, count in TABLE_UPDATE + REMARK_UPDATE:
        assert text.count(old) == count, (old, text.count(old))
        text = text.replace(old, new)
    return text


def opcodes():
    """difflib's line opcodes from index.html before the chart (BASE) to the working one."""
    return difflib.SequenceMatcher(None, committed().splitlines(), page().splitlines(), autojunk=False).get_opcodes()


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
    """The working index.html's lines, their regions, and the indices of the lines inserted since BASE."""
    lines = page().splitlines()
    return lines, regions(lines), [j for tag, _, _, j1, j2 in opcodes() if tag == 'insert' for j in range(j1, j2)]


def section():
    """The chart's section: the HTML from <section class="mstar" to its </section>."""
    text = page()
    m = re.search(r'<section class="mstar".*?</section>', text, re.S)
    assert m, 'no <section class="mstar">'
    return m.group(0)


def theme_blocks():
    """The custom properties of the page's one theme block, :root, as a one-item list (dreeves, 2026-10-12: no dark
    mode, so no other theme block)."""
    css = re.search(r'<style>(.*?)</style>', page(), re.S).group(1)
    ms = list(re.finditer(r'\n:root \{(.*?)\n\s*\}', css, re.S))
    assert len(ms) == 1 and 'prefers-color-scheme' not in page() and 'data-theme' not in page()
    return [dict(re.findall(r'(--[\w-]+):\s*([^;]+);', ms[0].group(1)))]


def mstar_data():
    """MSTAR as the browser sees it: node runs mstar.js and prints MSTAR as JSON."""
    assert os.path.exists(DATA), DATA
    src = open(DATA, encoding='utf-8').read()
    p = subprocess.run(['node', '-e', src + '\nprocess.stdout.write(JSON.stringify(MSTAR))'], capture_output=True,
                       text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout)


def pow2_data():
    """POW2 as the browser sees it: node runs pow2.js (beside index.html, made by pow2.py) and prints POW2 as JSON."""
    path = os.path.join(HERE, 'pow2.js')
    p = subprocess.run(['node', '-e', open(path, encoding='utf-8').read() + '\nprocess.stdout.write(JSON.stringify(POW2))'],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout)


def table_entries():
    """(n, low, high) for every entry of the page's tables with n <= NMAX: Table 2's blocks and the new results."""
    return entries(re.search(r'<figure>.*?</figure>', page(), re.S).group(0))


def new_results():
    """(n, low, high) for every entry of the new results' table with n <= NMAX, as entries() reads them."""
    return entries(re.search(r'<div class="new-block">.*?</table>', page(), re.S).group(0))


def entries(fragment):
    """(n, low, high) for every entry with n <= NMAX of the tables of class block in fragment.  An exact value v gives
    (v, v); 'a or b' and 'a–b' give (a, b); '≥ a' gives (a, inf)."""
    out = []
    for table in re.findall(r'<table class="block">.*?</table>', fragment, re.S):
        ns = re.findall(r'<td[^>]*>(.*?)</td>', re.search(r'<tr class="ns">.*?</tr>', table, re.S).group(0))
        vs = re.findall(r'<td[^>]*>(.*?)</td>', re.search(r'<tr class="vals">.*?</tr>', table, re.S).group(0))
        assert len(ns) == len(vs) and ns, table
        for cell, v in zip(ns, vs):
            m = re.fullmatch(r'(\d+)|2<sup>(\d+)</sup>', cell)
            assert m, cell
            n = int(m.group(1)) if m.group(1) else 2 ** int(m.group(2))
            if n > NMAX: continue
            forms = ((r'(\d+)', lambda a: (a, a)), (r'(\d+) or (\d+)', lambda a, b: (a, b)),
                     (r'(\d+)–(\d+)', lambda a, b: (a, b)), (r'≥ (\d+)', lambda a: (a, math.inf)))
            hits = [f(*map(int, m.groups())) for p, f in forms for m in [re.fullmatch(p, v)] if m]
            assert len(hits) == 1, (n, v)
            out.append((n, *hits[0]))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Color: the dataviz palette validator's arithmetic (OKLab ΔE ×100, Machado-Oliveira-Fernandes 2009 at severity 1.0)

MACHADO = {'protan': ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
           'deutan': ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881))}


def linear(h):
    assert re.fullmatch(r'#[0-9a-f]{6}', h), h
    return [(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
            for c in (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))]


def oklab(rgb):
    r, g, b = rgb
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
                                                              0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
                                                              0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s, 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def seen(h, kind):
    rgb = linear(h)
    return rgb if kind == 'normal' else [min(1, max(0, sum(a * c for a, c in zip(row, rgb)))) for row in MACHADO[kind]]


def delta_e(h1, h2, kind='normal'): return 100 * math.dist(oklab(seen(h1, kind)), oklab(seen(h2, kind)))


def worst_cvd(colors):
    """The validator's worst all-pairs CVD pair: (ΔE, kind), the minimum over protan and deutan."""
    return min((delta_e(a, b, k), k) for i, a in enumerate(colors) for b in colors[i + 1:] for k in MACHADO)


def worst_normal(colors): return min(delta_e(a, b) for i, a in enumerate(colors) for b in colors[i + 1:])


# ---------------------------------------------------------------------------------------------------------------------
# The browser runs

EARLY = r"""<script>
window.__errors = []; window.__texts = []; window.__fills = [];
addEventListener('error', e => {
  if (e instanceof ErrorEvent) __errors.push('error: ' + e.message);
  else if (e.target && e.target.tagName === 'SCRIPT') __errors.push('script failed to load: ' + e.target.src);
}, true);
addEventListener('unhandledrejection', e => __errors.push('rejection: ' + e.reason));
for (const k of ['error', 'warn']) {
  const f = console[k].bind(console);
  console[k] = (...a) => { __errors.push(k + ': ' + a.map(String).join(' ')); f(...a); };
}
const __fillText = CanvasRenderingContext2D.prototype.fillText;
CanvasRenderingContext2D.prototype.fillText = function (t, x, y, ...rest) {
  __texts.push(String(t)); __fills.push([String(t), x, y]); return __fillText.call(this, t, x, y, ...rest); };
Element.prototype.setPointerCapture = function () {};     // synthetic pointers are never active, so capture would throw
</script>
"""

HARNESS = r"""<script>
(() => {
const OPTS = __OPTS__;
function battery(R) {
  const cv = document.getElementById('mstar-chart'), ro = document.getElementById('mstar-readout');
  const reset = document.getElementById('mstar-reset'), rect = () => cv.getBoundingClientRect();
  R.readout0 = ro.textContent;
  R.canvasCss = [rect().width, rect().height];
  R.canvasDev = [cv.width, cv.height];
  R.dpr = devicePixelRatio; R.innerW = innerWidth; R.scrollW = document.documentElement.scrollWidth;
  const main = document.querySelector('main'), ms = getComputedStyle(main);
  R.mainContentW = main.clientWidth - parseFloat(ms.paddingLeft) - parseFloat(ms.paddingRight);
  R.touchAction = getComputedStyle(cv).touchAction;
  R.nTextBottoms = [...document.querySelectorAll('.new-block tr.ns')].map(tr => [...tr.querySelectorAll('td')].map(td => {
    const t = [...td.childNodes].find(x => x.nodeType === 3 && x.textContent.trim()), r = document.createRange();
    r.selectNodeContents(t); return r.getBoundingClientRect().bottom; }));
  if (cv.height === 0) return;
  const tok = name => getComputedStyle(cv).getPropertyValue(name).trim().toLowerCase();
  const C = {exists: tok('--exists'), open: tok('--open'), impossible: tok('--impossible'), paper: tok('--paper'), ink: tok('--ink'),
             record: tok('--record')};
  R.tokens = C;
  const dpr = devicePixelRatio, ctx = cv.getContext('2d'), T = MSTAR.mtop, cols = MSTAR.cols;
  const colorOf = (n, m) => m <= cols[n - 1][0] ? C.exists : m <= cols[n - 1][1] ? C.open : C.impossible;
  // The cells ringed in gold (dreeves, 2026-10-19): for each order m, the least n known to reach m when no smaller n's
  // upper bound allows m.  A ring spoils the pixels around its cell, in its row and the row above, so the generic
  // checks pass over the columns next to it there, and checkPixels checks the ring itself (RECS, ringChecks, ringBad).
  const least = test => cols.findIndex(test) + 1;
  const RECS = [];
  for (let m = 1; m <= T; m++) { const n = least(c => c[0] >= m); if (n && n === least(c => c[1] >= m)) RECS.push([n, m]); }
  R.records = RECS; R.ringChecks = 0; R.ringBad = []; R.ringed = {}; R.rowOneSkips = 0;
  const nearRing = (j, m) => RECS.some(([n, r]) => Math.abs(j - n / 2) <= 1 && (m === r || m === r + 1));
  let img = null;
  const snap = () => { img = ctx.getImageData(0, 0, cv.width, cv.height); };
  const pix = (X, Y) => { const i = (Y * img.width + X) * 4, d = img.data;
    return '#' + [d[i], d[i + 1], d[i + 2]].map(v => v.toString(16).padStart(2, '0')).join(''); };
  // Layout from pixels: the rows are the runs of non-paper pixels down the middle device column, from the top (the
  // first T of them; the axis may add more below), and the plot spans the run of impossible pixels across row T.
  snap();
  const runs = [];
  for (let Y = 0, s = -1, X = cv.width >> 1; Y <= cv.height; Y++) {
    const on = Y < cv.height && pix(X, Y) !== C.paper;
    if (on && s < 0) s = Y;
    if (!on && s >= 0) { runs.push([s, Y]); s = -1; }
  }
  const rows = runs.slice(0, T);
  R.rows = rows;
  const rowY = m => (rows[T - m][0] + rows[T - m][1]) / 2;        // device px, the middle of row m
  const Yt = Math.floor(rowY(T));
  let PL = 0, PR = cv.width - 1;
  while (pix(PL, Yt) !== C.impossible) PL++;
  while (pix(PR, Yt) !== C.impossible) PR--;
  PR++;
  R.plot = [PL, PR];
  const L = PL / dpr, W = (PR - PL) / dpr, yProbe = rowY(1) / dpr;      // CSS px
  const ptr = (type, x, y, o) => { const r = rect(), e = new PointerEvent(type, {clientX: r.left + x, clientY: r.top + y,
    pointerId: 1, pointerType: 'mouse', buttons: 0, bubbles: true, cancelable: true, ...o}); cv.dispatchEvent(e); return e; };
  const cellOf = t => { const m = t.match(/^n = (\d+), m = (\d+) · /); return m ? [+m[1], +m[2]] : null; };
  // Every hover's readout is counted, and kept if it reports an odd n (no column is an odd n).
  const hover = (x, y) => { ptr('pointermove', x, y, {}); const t = ro.textContent, c = cellOf(t);
    R.readouts++; if (c && c[0] % 2) R.oddReadouts.push(t); return t; };
  // Column j is n = 2j: jAt is the column read out at CSS x in row 1.
  const jAt = x => { const c = cellOf(hover(x, yProbe)); if (!c) throw new Error('no cell read out at ' + x); return c[0] / 2; };
  function view() {        // the visible u-interval [u0, u0 + span), column j spanning u from j - 1 to j
    let a = L + 0.25, b = Math.min(L + 160, L + W - 0.25);
    const j1 = jAt(a);
    if (!(jAt(b) > j1)) throw new Error('no column boundary near the left edge');
    for (let i = 0; i < 26; i++) { const c = (a + b) / 2; if (jAt(c) > j1) b = c; else a = c; }
    const x1 = b;                                   // u = j1 here
    let a2 = Math.max(L + 0.25, L + W - 160), b2 = L + W - 0.25;
    const j2 = jAt(b2);
    if (!(jAt(a2) < j2)) throw new Error('no column boundary near the right edge');
    for (let i = 0; i < 26; i++) { const c = (a2 + b2) / 2; if (jAt(c) < j2) a2 = c; else b2 = c; }
    const x2 = b2;                                  // u = j2 - 1 here
    const slope = (j2 - 1 - j1) / (x2 - x1);        // u per CSS px
    return {u0: j1 - (x1 - L) * slope, span: slope * W};
  }
  const first = v => Math.ceil(v.u0 - 1e-3) + 1, final = v => Math.floor(v.u0 + v.span + 1e-3);   // whole columns in view
  const middleX = (v, j) => L + (j - 0.5 - v.u0) * W / v.span;                                      // CSS px
  function checkPixels(v) {    // every column at least 3 device px wide: its middle pixel has its color in every row,
    const k = v.span / (PR - PL);   // and the pixel just below each row is paper.  The outline of the cell read out
    if (1 / k < 3) return;          // spoils its neighbors, so the view is checked twice: outlining its first column,
    const [a, b] = [first(v), final(v)];   // then its last, and checking the columns 2 or more away from it.
    for (const [o, from, to] of [[a, a + 2, b], [b, a, b - 2]]) {
      hover(middleX(v, o), rowY(T) / dpr);
      snap();
      for (let j = from; j <= to; j++) {
        const X = PL + Math.floor((j - 0.5 - v.u0) / k);
        for (let m = 1; m <= T; m++) {
          if (nearRing(j, m)) continue;
          const want = colorOf(2 * j, m), got = pix(X, Math.floor(rowY(m))), gap = pix(X, rows[T - m][1]);
          R.pixelChecks++;
          if (got !== want || gap !== C.paper) R.pixelBad.push([2 * j, m, want, got, gap]);
        }
        R.pixelColumns[2 * j] = 1;
      }
      for (const [n, r] of RECS) {    // a ringed cell in this pass: gold just outside its left and right, and below it
        const j = n / 2;
        if (j < from || j > to) continue;
        const Y = Math.floor(rowY(r)), x0 = PL + (j - 1 - v.u0) / k, x1 = PL + (j - v.u0) / k;
        const got = [pix(Math.floor(x0 - dpr), Y), pix(Math.floor(x1 + dpr), Y), pix(PL + Math.floor((j - 0.5 - v.u0) / k), rows[T - r][1])];
        R.ringChecks++; R.ringed[n] = 1;
        if (got.some(c => c !== C.record)) R.ringBad.push([n, r, got]);
      }
    }
  }
  // Row 1 is exists in every even column and impossible in every odd one, so with no odd column drawn, even mixed into a
  // pixel, every pixel of row 1 is exists.  The outline of the cell read out goes to row T first.
  function checkRowOne(v, i) {     // but where a ring of row 1 runs, a device px either side (rowOneSkips)
    hover(middleX(v, first(v)), rowY(T) / dpr);
    snap();
    const k = v.span / (PR - PL), bands = RECS.filter(([, r]) => r === 1).flatMap(([n]) => {
      const x0 = PL + (n / 2 - 1 - v.u0) / k, x1 = PL + (n / 2 - v.u0) / k;
      return [[x0 - 2 * dpr - 1, x0 + 1], [x1 - 1, x1 + 2 * dpr + 1]];
    });
    for (let X = PL, Y = Math.floor(rowY(1)); X < PR; X++) {
      if (bands.some(([a, b]) => a <= X && X <= b)) { R.rowOneSkips++; continue; }
      R.rowOneChecks++;
      if (pix(X, Y) !== C.exists) R.rowOneBad.push([i, X, pix(X, Y)]);
    }
  }
  // The n labels of one draw (the one a change of the cell read out makes): the strings drawn below the rows and right
  // of the plot's left edge, as [string, x in device px].
  function labels(v) {
    hover(middleX(v, first(v)), rowY(T) / dpr);
    __fills.length = 0;
    hover(middleX(v, first(v)), rowY(T - 1) / dpr);
    return {v, labels: __fills.filter(([t, x, y]) => y > rows[T - 1][1] && x >= PL - 1).map(([t, x]) => [t, x])};
  }
  function sampleHovers(v, every) {    // hover the middle of cells lo, lo + 1 and hi + 1 of every every-th column
    for (let j = first(v); j <= final(v); j += every) {
      const n = 2 * j, [lo, hi] = cols[n - 1];
      for (const m of new Set([lo, lo + 1, hi + 1])) {
        if (m < 1 || m > T) continue;
        R.hovers.push([n, m, hover(middleX(v, j), rowY(m) / dpr)]);
        const {backgroundColor, boxShadow} = getComputedStyle(ro.querySelector('.swatch'));
        R.swatches.push([n, m, backgroundColor, boxShadow]);
      }
    }
  }
  const key = (k, o) => { const e = new KeyboardEvent('keydown', {key: k, bubbles: true, cancelable: true, ...o});
    cv.dispatchEvent(e); return e.defaultPrevented; };
  // Chrome makes a synthetic wheel event's clientX a whole number, so wheel returns where the pointer really was, as a
  // fraction of the plot's width, with whether the default was prevented.
  const wheel = (x, o) => { const r = rect(), e = new WheelEvent('wheel', {clientX: r.left + x, clientY: r.top + yProbe,
    deltaMode: 0, bubbles: true, cancelable: true, ...o}); cv.dispatchEvent(e); return [e.defaultPrevented, (e.clientX - r.left - L) / W]; };
  const touch = (type, id, x) => ptr(type, x, yProbe, {pointerId: id, pointerType: 'touch', isPrimary: false,
    buttons: type === 'pointerup' ? 0 : 1});
  const gesture = (type, scale, x) => { const r = rect(), e = new Event(type, {bubbles: true, cancelable: true});
    Object.assign(e, {scale, clientX: r.left + x, clientY: r.top + yProbe}); cv.dispatchEvent(e); return e.defaultPrevented; };
  const step = (name, f) => { const a = view(), x = f(), b = view(); R.steps[name] = {a, b, x, disabled: disabled()}; };

  // The zoom buttons: whether each is disabled (null if it is missing), and how each looks, at load.
  const zin = document.getElementById('mstar-zoom-in'), zout = document.getElementById('mstar-zoom-out');
  const disabled = () => [zin, zout].map(b => b && b.disabled);
  const look = b => b && (({opacity, display, visibility}) => ({opacity: +opacity, display, visibility,
    size: [b.getBoundingClientRect().width, b.getBoundingClientRect().height]}))(getComputedStyle(b));
  R.disabled0 = disabled();
  R.looks0 = [zin, zout].map(look);
  R.readouts = 0; R.oddReadouts = [];
  R.views = [view()];
  R.hovers = []; R.swatches = []; R.pixelChecks = 0; R.pixelBad = []; R.pixelColumns = {}; R.steps = {}; R.rowOneChecks = 0; R.rowOneBad = [];
  R.labelDraws = [labels(R.views[0])];
  checkRowOne(R.views[0], 0);
  // A hover at the middle of every device px across row 1 of the full view: the n read out, left to right, each once.
  R.across = [];
  for (let X = PL; X < PR; X++) { const c = cellOf(hover((X + 0.5) / dpr, yProbe)); R.across.push(c && c[0]); }
  R.across = R.across.filter((n, i, a) => i === 0 || n !== a[i - 1]);
  sampleHovers(R.views[0], OPTS.hoverEvery);
  // Sweep: zoom in, go to the left end, and step right by 3/4 of a view at a time to the right end.
  cv.focus();
  for (let i = 0; i < 7; i++) key('+');
  for (let i = 0; i < 300; i++) key('ArrowLeft');
  for (let guard = 0; guard < 100; guard++) {
    const v = view();
    R.views.push(v);
    sampleHovers(v, OPTS.hoverEvery);
    checkPixels(v);
    checkRowOne(v, R.views.length - 1);
    R.labelDraws.push(labels(v));
    if (v.u0 + v.span > NCOL - 1e-6) break;
    for (let i = 0; i < 6; i++) key('ArrowRight');
  }
  R.pixelColumns = Object.keys(R.pixelColumns).map(Number).sort((a, b) => a - b);
  // The cell read out is outlined in ink, just outside it.
  reset.click();
  for (let i = 0; i < 5; i++) key('+');
  {
    const v = view(), k = v.span / (PR - PL), j = Math.round(v.u0 + v.span / 2), n = 2 * j, m = 2;
    R.outlineText = hover((PL + (j - 0.5 - v.u0) / k) / dpr, rowY(m) / dpr);
    snap();
    R.outline = {n, m, want: colorOf(n, m), ink: C.ink, middle: pix(PL + Math.floor((j - 0.5 - v.u0) / k), Math.floor(rowY(m))),
                 left: pix(Math.floor(PL + (j - 1 - v.u0) / k - dpr), Math.floor(rowY(m))),
                 right: pix(Math.floor(PL + (j - v.u0) / k + dpr), Math.floor(rowY(m)))};
  }
  // Interactions, each from a view zoomed in 3 steps about the middle unless said otherwise.
  const zoomed = () => { reset.click(); for (let i = 0; i < 3; i++) key('+'); };
  zoomed(); step('right', () => key('ArrowRight'));
  zoomed(); step('left', () => key('ArrowLeft'));
  zoomed(); step('plus', () => key('+'));
  zoomed(); step('equals', () => key('='));
  zoomed(); step('minus', () => key('-'));
  zoomed(); step('down', () => key('ArrowDown'));
  zoomed(); step('ctrlPlus', () => key('+', {ctrlKey: true}));
  zoomed(); step('metaRight', () => key('ArrowRight', {metaKey: true}));
  zoomed(); step('ctrlWheel', () => wheel(L + 0.3 * W, {deltaY: -100, ctrlKey: true}));
  zoomed(); step('metaWheel', () => wheel(L + 0.3 * W, {deltaY: 50, metaKey: true}));
  zoomed(); step('lineWheel', () => wheel(L + 0.3 * W, {deltaY: -3, deltaMode: 1, ctrlKey: true}));
  zoomed(); step('sideWheel', () => wheel(L + 0.3 * W, {deltaX: 60, deltaY: 5}));
  zoomed(); step('upWheel', () => wheel(L + 0.3 * W, {deltaY: 100, deltaX: 2}));
  zoomed(); step('drag', () => { ptr('pointerdown', L + 0.6 * W, yProbe, {buttons: 1});
    ptr('pointermove', L + 0.6 * W - 100, yProbe, {buttons: 1}); ptr('pointerup', L + 0.6 * W - 100, yProbe, {}); return 100; });
  zoomed(); step('pinch', () => { touch('pointerdown', 11, L + 0.4 * W); touch('pointerdown', 12, L + 0.6 * W);
    touch('pointermove', 11, L + 0.3 * W); touch('pointermove', 12, L + 0.7 * W);
    touch('pointerup', 11, L + 0.3 * W); touch('pointerup', 12, L + 0.7 * W); return [0.2 * W, 0.4 * W, 0.5 * W]; });
  zoomed(); step('swipe', () => { touch('pointerdown', 13, L + 0.5 * W); touch('pointermove', 13, L + 0.3 * W);
    touch('pointerup', 13, L + 0.3 * W); return 0.2 * W; });
  zoomed(); step('gesture', () => [gesture('gesturestart', 1, L + 0.25 * W), gesture('gesturechange', 2, L + 0.25 * W),
    gesture('gestureend', 2, L + 0.25 * W), 0.25 * W]);
  zoomed(); step('gestureWhileTouching', () => { touch('pointerdown', 21, L + 0.5 * W);
    const p = [gesture('gesturestart', 1, L + 0.25 * W), gesture('gesturechange', 2, L + 0.25 * W)];
    touch('pointerup', 21, L + 0.5 * W); return p; });
  zoomed(); step('reset', () => { key('ArrowRight'); key('+'); reset.click(); });
  zoomed(); step('zoomInFar', () => { for (let i = 0; i < 40; i++) key('+'); });
  R.labelDraws.push(labels(R.steps.zoomInFar.b));
  zoomed(); step('zoomOutFar', () => { for (let i = 0; i < 40; i++) key('-'); });
  zoomed(); step('panFar', () => { for (let i = 0; i < 300; i++) key('ArrowRight'); });
  zoomed(); step('wheelOutFar', () => wheel(L + 0.5 * W, {deltaY: 5000, ctrlKey: true})[0]);
  // A tap reads out the cell under it, and so does a mouse click.
  zoomed();
  {
    const v = view(), x = L + 0.37 * W, k = v.span / W;
    hover(L + 0.8 * W, rowY(5) / dpr);
    touch('pointerdown', 14, x); touch('pointerup', 14, x);
    R.tap = {want: [2 * (Math.floor(v.u0 + (x - L) * k) + 1), 1], text: ro.textContent};
    ptr('pointerup', L + 0.2 * W, yProbe, {pointerId: 99});        // an up with no down: nothing happens
    R.tap.after = ro.textContent;
    const x2 = L + 0.63 * W;
    hover(L + 0.8 * W, rowY(5) / dpr);
    ptr('pointerdown', x2, yProbe, {buttons: 1}); ptr('pointerup', x2, yProbe, {});
    R.click = {want: [2 * (Math.floor(v.u0 + (x2 - L) * k) + 1), 1], text: ro.textContent};
  }
  // The zoom buttons: a click of each from a view zoomed in 3 steps; then, from the full view, clicks of + until it is
  // disabled and then of − until it is disabled, the view measured after each.
  try {
    zoomed(); step('zoomInButton', () => zin.click());
    zoomed(); step('zoomOutButton', () => zout.click());
    reset.click();
    R.clicks = [['start', view(), disabled()]];
    for (const [b, kind] of [[zin, 'in'], [zout, 'out']]) {
      for (let i = 0; i < 40 && !b.disabled; i++) { b.click(); R.clicks.push([kind, view(), disabled()]); }
    }
  } catch (e) { R.buttonsError = String(e && e.stack || e); }
}
const R = {errors: window.__errors, opts: OPTS};
const go = () => {
  try { battery(R); } catch (e) { R.harnessError = String(e && e.stack || e); }
  R.texts = [...new Set(window.__texts)];
  parent.postMessage(JSON.stringify(R), '*');
};
const NCOL = 500;                                                  // the columns: n = 2, 4, ..., 1000
addEventListener('load', () => document.fonts.ready.then(() => setTimeout(go, 50)));
})();
</script>
"""


# Headless Chrome's window is at least 500 px wide, so the page runs in an iframe as wide as the configuration asks;
# the harness posts its report to this host page, which writes it into its own DOM for --dump-dom.
HOST = """<!doctype html>
<html><head><meta charset="utf-8"></head><body style="margin: 0">
<iframe src="index.html" style="display: block; border: 0; width: __WIDTH__px; height: 1000px"></iframe>
<script>
addEventListener('message', e => {
  const pre = document.createElement('pre'); pre.id = 'harness-out'; pre.textContent = e.data; document.body.append(pre);
});
</script>
</body></html>
"""


def kinds_data(violation=None):
    """Made-up data that follows the contract and uses every kind of reason: odd columns are ["none"] and ["odd"]; an even
    n has lo = 1 from an example and hi = 2^v - 1 ("two") if that is at most 7, else 7 by the residue condition mod 3;
    a few columns use the other kinds.  violation, if given, names the change in VIOLATIONS that breaks it."""
    cols = []
    for n in range(1, NMAX + 1):
        two = (n & -n) - 1
        cols.append([0, 0, ['none'], ['odd']] if n % 2 else
                    [1, two, ['example', 'a made-up label'], ['two']] if two <= 7 else
                    [1, 7, ['example', 'a made-up label'], ['residue', 3]])
    for n, c in ((4, [2, 2, ['product', 2, 2], ['norm', 3]]), (8, [3, 3, ['table2'], ['table2']]),
                 (12, [2, 3, ['join', 4, 8], ['two']]), (16, [4, 4, ['page', 'BGPW'], ['page', 'Claude and BGPW']]),
                 (20, [3, 3, ['page', 'Claude alone'], ['two']]), (24, [4, 5, ['example', 'BGPW Table 5'], ['residue', 9]]),
                 (32, [5, 7, ['product', 16, 2], ['norm', 5]]), (48, [6, 7, ['table2'], ['norm', 7]])):
        cols[n - 1] = c
    data = {'nmax': NMAX, 'mtop': max(c[1] for c in cols) + 1, 'cols': cols}
    VIOLATIONS.get(violation, (lambda data: None,))[0](data)
    return 'const MSTAR = ' + json.dumps(data) + ';\n'


def column(n, entry):
    """A change to made-up data: column n becomes entry."""
    def change(data): data['cols'][n - 1] = entry
    return change


VIOLATIONS = {   # name: (a change that breaks the contract, what the page's error line must quote)
    'lo above hi': (column(100, [5, 3, ['example', 'a made-up label'], ['two']]),
                    "[100,[5,3,['example','a made-up label'],['two']]]"),
    'unknown kind': (column(100, [1, 3, ['guess'], ['two']]), "[100,[1,3,['guess'],['two']]]"),
    'arity': (column(100, [1, 3, ['join', 50], ['two']]), "[100,[1,3,['join',50],['two']]]"),
    'join lengths': (column(100, [1, 3, ['join', 40, 50], ['two']]), "[100,[1,3,['join',40,50],['two']]]"),
    'join order': (column(100, [3, 3, ['join', 50, 50], ['two']]), "[100,[3,3,['join',50,50],['two']]]"),
    'product order': (column(100, [3, 3, ['product', 50, 2], ['two']]), "[100,[3,3,['product',50,2],['two']]]"),
    'two': (column(100, [1, 2, ['example', 'x'], ['two']]), "[100,[1,2,['example','x'],['two']]]"),
    'norm divisor': (column(100, [1, 3, ['example', 'x'], ['norm', 5]]), "[100,[1,3,['example','x'],['norm',5]]]"),
    'norm composite': (column(100, [1, 3, ['example', 'x'], ['norm', 9]]), "[100,[1,3,['example','x'],['norm',9]]]"),
    'table2 n': (column(100, [1, 3, ['table2'], ['two']]), "[100,[1,3,['table2'],['two']]]"),
    'page who': (column(100, [1, 3, ['page', 'Stan'], ['two']]), "[100,[1,3,['page','Stan'],['two']]]"),
    'empty label': (column(100, [1, 3, ['example', ''], ['two']]), "[100,[1,3,['example',''],['two']]]"),
    'none at even n': (column(100, [0, 3, ['none'], ['two']]), "[100,[0,3,['none'],['two']]]"),
    'odd at even n': (column(100, [0, 0, ['none'], ['odd']]), "[100,[0,0,['none'],['odd']]]"),
    'example at odd n': (column(99, [0, 0, ['example', 'x'], ['odd']]), "[99,[0,0,['example','x'],['odd']]]"),
    'five entries': (column(100, [1, 3, ['example', 'x'], ['two'], 0]), "[100,[1,3,['example','x'],['two'],0]]"),
    'hi at mtop': (column(100, [1, 8, ['example', 'x'], ['residue', 3]]), "[100,[1,8,['example','x'],['residue',3]]]"),
    'mtop': (lambda data: data.update(mtop=9), '[9]'),
    'nmax': (lambda data: data.update(nmax=999), '[999,8]'),
}


CONFIGS = {   # name: (mstar.js, window width, device pixel ratio, theme, hover every this many columns)
    'light': ('real', 1280, 2, None, 1),
    'phone': ('real', 390, 3, None, 5),
    'kinds': ('kinds', 1280, 2, None, 1),
    'missing': (None, 1280, 2, None, 1),
} | {f'violates {v}': (v, 1280, 1, None, 1) for v in VIOLATIONS}
SOURCES = {'real': lambda: open(DATA, encoding='utf-8').read(), 'kinds': kinds_data} | {
    v: (lambda v=v: kinds_data(v)) for v in VIOLATIONS}           # mstar.js's text, by CONFIGS's first entry


def run(name):
    """The harness's report for one configuration, made on first use."""
    if name not in RUNS:
        data, width, dpr, theme, every = CONFIGS[name]
        d = tempfile.mkdtemp(prefix='index-quals-')
        text = page()
        assert text.count('<head>\n') == 1 and text.count('</body>') == 1 and text.count('<html lang="en">') == 1
        text = text.replace('<head>\n', '<head>\n' + EARLY).replace('</body>', HARNESS.replace(
            '__OPTS__', json.dumps({'hoverEvery': every})) + '</body>')
        if theme: text = text.replace('<html lang="en">', f'<html lang="en" data-theme="{theme}">')
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(text)
        if data is not None: open(os.path.join(d, 'mstar.js'), 'w', encoding='utf-8').write(SOURCES[data]())
        shutil.copy(POW2, os.path.join(d, 'pow2.js'))
        open(os.path.join(d, 'host.html'), 'w').write(HOST.replace('__WIDTH__', str(width)))
        dom = chrome(d, [f'--window-size={max(width, 500) + 40},1100', f'--force-device-scale-factor={dpr}',
                         '--virtual-time-budget=10000', '--dump-dom', 'file://' + os.path.join(d, 'host.html')])
        m = re.search(r'<pre id="harness-out">(.*?)</pre>', dom, re.S)
        assert m, (name, dom[-3000:])
        RUNS[name] = json.loads(html.unescape(m.group(1)))
        shutil.rmtree(d)
    return RUNS[name]


def chrome(d, args, stderr=subprocess.DEVNULL):
    """Headless Chrome with its own profile in directory d: the DOM it dumps.  This Chrome prints the dump and then
    does not exit, so the dump is read up to </html> and then Chrome's own process group is sent SIGTERM (a watchdog
    does the same after 600 s, and the dump is then incomplete, which the caller's assert reports)."""
    p = subprocess.Popen([CHROME, '--headless=new', f'--user-data-dir={d}/profile', '--no-first-run',
                          '--no-default-browser-check', '--disable-extensions', *args],
                         stdout=subprocess.PIPE, stderr=stderr, text=True, start_new_session=True)
    stop = lambda: os.killpg(p.pid, signal.SIGTERM)
    watchdog = threading.Timer(600, stop)
    watchdog.start()
    out = []
    for line in p.stdout:
        out.append(line)
        if '</html>' in line: break
    watchdog.cancel()
    if p.poll() is None: stop()
    p.wait(timeout=60)
    return ''.join(out)


def console_lines():
    """The lines Chrome logs from the page's console when it loads index.html as is, with the real mstar.js beside it."""
    d = tempfile.mkdtemp(prefix='index-quals-')
    shutil.copy(INDEX, os.path.join(d, 'index.html'))
    shutil.copy(DATA, os.path.join(d, 'mstar.js'))
    shutil.copy(POW2, os.path.join(d, 'pow2.js'))
    with open(os.path.join(d, 'stderr.txt'), 'w') as f:
        chrome(d, ['--enable-logging=stderr', '--v=0', '--window-size=1280,1000', '--virtual-time-budget=10000',
                   '--dump-dom', 'file://' + os.path.join(d, 'index.html')], stderr=f)
    lines = [line for line in open(os.path.join(d, 'stderr.txt'), errors='replace') if ':CONSOLE' in line]
    shutil.rmtree(d)
    return lines


def valid_run(name):
    """A run on valid data: the harness finished and nothing recorded an error."""
    R = run(name)
    assert 'harnessError' not in R, R['harnessError']
    assert R['errors'] == [], R['errors']
    return R


# dreeves requested Astra attribution on the same terms as Claude for the 384 result (2026-10-20).
ATTRIBUTION = r'(?:Claude|Astra): "'


def unclaimed(text):
    """text with each Claude or Astra quotation removed: what remains must hold no English, only numbers and math."""
    return re.sub(ATTRIBUTION + r'[^"]*"', '', text)


def english(text): return re.findall(r'[A-Za-z]{2,}', text)


# dreeves's second form for Claude's words (2026-10-14, for Claude's account of its lattice search): "all the english
# text in a block quote attributed to claude".  The quote runs from a line QUOTE_OPEN to a line QUOTE_CLOSE, its last
# line inside is QUOTE_ATTRIB, and its TODO comment (a recap, for dreeves) is the nearest non-blank line above it, or
# above QUOTE_LEADIN, the lead-in dreeves put between the two (his words, 2026-10-14), when that is there.
QUOTE_OPEN, QUOTE_ATTRIB, QUOTE_CLOSE = '<blockquote class="claude">', '<p class="attrib">— Claude</p>', '</blockquote>'
QUOTE_LEADIN = ('<p>', 'Still Claude:', '</p>')


def claude_quotes(lines):
    """(the indices of the lines of every block quote attributed to Claude, from its lead-in if it has one or else
    QUOTE_OPEN, to QUOTE_CLOSE; the indices of their TODO comments), each quote asserted to be of that form: closed, not
    nested, ending in QUOTE_ATTRIB, with a <!-- TODO: comment above it or above its lead-in."""
    out, todos = set(), set()
    for j in (j for j, line in enumerate(lines) if line.strip() == QUOTE_OPEN):
        k = next(i for i in range(j + 1, len(lines)) if lines[i].strip() in (QUOTE_OPEN, QUOTE_CLOSE))
        assert lines[k].strip() == QUOTE_CLOSE, ('nested or unclosed', j + 1)
        assert [l.strip() for l in lines[j + 1:k] if l.strip()][-1] == QUOTE_ATTRIB, ('no attribution', j + 1)
        above = [i for i in range(j - 1, -1, -1) if lines[i].strip()]
        lead = len(QUOTE_LEADIN) * (tuple(lines[i].strip() for i in reversed(above[:len(QUOTE_LEADIN)])) == QUOTE_LEADIN)
        assert lines[above[lead]].strip().startswith('<!-- TODO:'), ('no TODO', j + 1)
        out |= set(range(above[lead] + 1, k + 1))
        todos.add(above[lead])
    return out, todos


def progress_lines(lines):
    """(the indices of the lines of the section "Search progress", from its TODO comment, its first line, to its
    </section>; that TODO comment's index), the section asserted to be of that form.  Its copy is unattributed, as
    progress.html's was (dreeves, 2026-10-09, for the page): on 2026-10-17 he took the section out of the block quote
    attributed to Claude that it was made in, so the copy rules pass over its lines as over a quote's."""
    j = next(i for i, line in enumerate(lines) if line.startswith('<section class="progress"'))
    k = next(i for i in range(j, len(lines)) if lines[i] == '</section>')
    assert lines[j + 1].strip().startswith('<!-- TODO:') and lines[j + 1].strip().endswith('-->'), lines[j + 1][:80]
    return set(range(j + 1, k + 1)), j + 1


def close(a, b, tol): return abs(a - b) <= tol


# The section "The smallest length known for each order" (Stan Wagon's suggestion, relayed 2026-10-17: "keep track of a
# table that shows the first n that gives 1,2,3,4,5,…,12"; dreeves: "yeah").  Orders 1 to 11 have their smallest
# lengths proven: OEIS A323395's a(0) to a(8), 240 as a(9), and (2026-10-20) 432 as a(10), after proof384.py.
SMALLEST_PROVEN = (2, 4, 8, 16, 32, 48, 96, 144, 192, 240, 432)
ASTRA_SMALLEST_NOTE = (
    '  <!-- TODO: attributes the new minimality result to Astra and identifies the new exclusion that completes the existing bounds. -->',
    '  <p>Astra: "The <a href="#proof384">exclusion of order 11 at 384</a> closes the last gap below 432. Together with the existing order-11 example at 432 and the other exclusions in the chart, this proves <span class="nw"><i>a</i>(10) = 432</span>."</p>')


def smallest_rows(cols):
    """The rows the section's script makes from MSTAR's cols, computed here: for each order m from 1 while some n has a
    known sequence of order m (its lower bound at least m), the texts of m, the least such n, a check mark if that n is
    also the least n whose upper bound is at least m (else nothing), and that least n."""
    least = lambda test: next((n for n, c in enumerate(cols, 1) if test(c)), None)
    rows, m = [], 1
    while least(lambda c: c[0] >= m):
        known, possible = least(lambda c: c[0] >= m), least(lambda c: c[1] >= m)
        rows.append([str(m), str(known), '✓' if known == possible else '', str(possible)])
        m += 1
    return rows


def a323395_cells(cols):
    """The cells (n, m) the chart rings in gold (dreeves, 2026-10-19): smallest_rows' proven ones, the terms a(m − 1)
    of OEIS A323395 that the data proves."""
    return [(int(n), int(m)) for m, n, proven, _ in smallest_rows(cols) if proven]


def ring_note(m):
    """The readout's note on a ringed cell of order m (Claude's words, without the Claude: "…")."""
    return f'the least n of order {m}: a({m - 1}) of OEIS A323395'


# ---------------------------------------------------------------------------------------------------------------------
# Static quals

def q_384_proof_is_attributed_and_linked():
    # Replicata: the updated new-results table and remarks, plus the generated chart's smallest-length rows.
    # Expectata: 384 is marked as Astra's result, a separately attributed proof links the standalone checker, and
    # order 11 is now proven to have smallest length 432.  The earlier Claude account remains attributed to Claude.
    text = page()
    assert '<td class="a" title=\'Astra alone\'>384</td>' in text
    remark = re.search(r'<li class="a" id="proof384">(.*?)</li>', text, re.S)
    assert remark, 'no Astra remark for 384'
    assert 'Astra: "' in remark.group(1) and 'href="proof384.py"' in remark.group(1)
    assert '<i>m</i><sup>*</sup> = 10' in remark.group(1)
    assert smallest_rows(mstar_data()['cols'])[10] == ['11', '432', '✓', '432']
    smallest = re.search(r'<section class="smallest".*?</section>', text, re.S).group(0)
    assert '</blockquote>' in smallest and 'Astra: "' in smallest.split('</blockquote>', 1)[1]


def q_insertions_only():
    # Replicata: index.html against the page before the chart (git show BASE:index.html), compared line by line with
    # difflib.
    # Expectata: every opcode is 'equal' or 'insert': not a character of the page before the chart changed or went
    # missing; and lines were inserted.
    tags = {tag for tag, *_ in opcodes()}
    assert tags <= {'equal', 'insert'}, [op for op in opcodes() if op[0] not in ('equal', 'insert')]
    assert 'insert' in tags, tags


def q_section_follows_table2():
    # Replicata: index.html.
    # Expectata: the page's one <figure> (Table 2) is followed, with only blank lines and comments between, by
    # <section class="mstar" aria-labelledby="mstar-title">, and that by <section class="pow2" (the chart of powers of
    # 2; quals_pow2_page.py holds it to being followed by <section class="remarks">).  In order, the
    # section holds: the h2 mstar-title; a legend whose swatches are exists, open and impossible, then (since
    # 2026-10-19) exists ringed in gold for a(m − 1) of OEIS A323395; the reset
    # button; the canvas mstar-chart (height 0 until drawn, focusable, an image with a label); and the readout
    # paragraph mstar-readout, polite live region.  (dreeves's copyedit dropped the caption paragraph.)
    text = page()
    assert text.count('<figure>') == 1 and text.count('</figure>') == 1
    after = text[text.index('</figure>') + len('</figure>'):]
    filler = r'(?:\s|<!--.*?-->)*'
    m = re.match(filler + r'<section class="mstar" aria-labelledby="mstar-title">.*?</section>', after, re.S)
    assert m, after[:400]
    assert re.match(filler + r'<section class="pow2"', after[m.end():], re.S), after[m.end():m.end() + 400]
    parts = [r'<h2 id="mstar-title">', r'<ul class="legend">', r'<span class="swatch exists" aria-hidden="true">',
             r'<span class="swatch open" aria-hidden="true">', r'<span class="swatch impossible" aria-hidden="true">',
             re.escape(GOLD_LEGEND),
             r'</ul>', r'<button type="button" id="mstar-reset" ',
             r'<canvas id="mstar-chart" height="0" tabindex="0" role="img" aria-label=',
             r'<p id="mstar-readout" aria-live="polite">']
    assert re.search('.*?'.join(parts), section(), re.S), section()


def q_scripts_load_data_then_draw():
    # Replicata: index.html's script tags.
    # Expectata: exactly six, after </main> and before </body>: a classic <script src="mstar.js"> (no type, async or
    # defer, so it also loads from file://) and then one inline script; then the chart of powers of 2's, likewise
    # (quals_pow2_page.py holds those two); then the inline script of the table of smallest lengths, which reads MSTAR
    # (2026-10-17); then the inline script of the section "Search progress", which loads progress.js itself
    # (2026-10-17).
    text = page()
    assert re.findall(r'<script\b[^>]*>', text) == ['<script src="mstar.js">', '<script>', '<script src="pow2.js">', '<script>',
                                                    '<script>', '<script>'], re.findall(r'<script\b[^>]*>', text)
    inline = re.findall(r'<script>\n(.*?)</script>', text, re.S)
    assert '[data-smallest]' in inline[2] and 'progressData' in inline[3], [js[:60] for js in inline]
    assert text.index('</main>') < text.index('<script src="mstar.js"></script>') < text.index('<script>\n') < \
        text.index('</script>\n</body>')


def q_inline_script_passes_node_check():
    # Replicata: the inline script, saved as a .js file, through node --check.
    # Expectata: exit 0: it parses as a classic script.
    js = re.search(r'<script>\n(.*?)</script>', page(), re.S).group(1)
    d = tempfile.mkdtemp(prefix='index-quals-')
    path = os.path.join(d, 'chart.js')
    open(path, 'w', encoding='utf-8').write(js)
    p = subprocess.run(['node', '--check', path], capture_output=True, text=True, timeout=60)
    shutil.rmtree(d)
    assert p.returncode == 0, p.stderr


def q_new_copy_is_attributed():
    # Replicata: the lines inserted since BASE, by region (HTML, inline script, style).
    # Expectata: inserted lines exist, and each of DREEVES_LINES is one of them, exactly once: those lines hold his
    # words, so the rules that follow pass over them.  In HTML, a line's visible text and its aria-label, title and alt
    # values hold English only inside Claude: "…" or Astra: "…", or a block quote attributed to Claude (claude_quotes,
    # whose lines the rules that follow pass over too); every quotation closes on its line; each line with one (HTML or
    # script) has a TODO comment as the nearest non-blank line above (<!-- TODO: in HTML, // TODO: in script), and each
    # TODO comment is followed by a line with one, or by one of his lines (the heading's TODO comment sits above his
    # heading), or is a quote's (above its lead-in or QUOTE_OPEN); no inserted CSS uses content:.  The section
    # "Search progress" is passed over as a quote is, its TODO taken (progress_lines: dreeves took it out of its quote).
    lines, region, ins = inserted()
    assert ins
    his = [j for j in ins if lines[j].strip() in DREEVES_LINES]
    assert sorted(lines[j].strip() for j in his) == sorted(DREEVES_LINES), [lines[j] for j in his]
    quoted, quote_todos = claude_quotes(lines)
    section, section_todo = progress_lines(lines)
    quoted, quote_todos = quoted | section, quote_todos | {section_todo}
    bad = []
    for j in (j for j in ins if j not in his and j not in quoted):
        line, r = lines[j], region[j]
        if r == 'style' and re.search(r'(?<![\w-])content\s*:', line): bad.append((j + 1, 'content:', line))
        if r == 'html':
            bare = re.sub(r'<!--.*?-->', '', line)
            texts = [re.sub(r'<[^>]*>', ' ', bare)] + re.findall(r'\b(?:aria-label|title|alt)=(?:\'([^\']*)\'|"([^"]*)")', bare)
            for t in texts:
                for s in (t if isinstance(t, tuple) else (t,)):
                    if english(unclaimed(html.unescape(s))): bad.append((j + 1, 'unattributed English', s))
        if r in ('html', 'script') and re.search(ATTRIBUTION, line):
            if len(re.findall(ATTRIBUTION, line)) != len(re.findall(ATTRIBUTION + r'[^"]*"', line)): bad.append((j + 1, 'unclosed', line))
            above = next(lines[i] for i in range(j - 1, -1, -1) if lines[i].strip())
            todo = '<!-- TODO:' in above if r == 'html' else above.strip().startswith('// TODO:')
            if not todo: bad.append((j + 1, 'no TODO above', line))
        if re.search(r'\bTODO\b', line):                # the word, not TODOCOLOR (dreeves's tag on the chart's colors)
            below = next(lines[i] for i in range(j + 1, len(lines)) if lines[i].strip())
            if not re.search(ATTRIBUTION, below) and below.strip() not in DREEVES_LINES and j not in quote_todos:
                bad.append((j + 1, 'TODO with no attributed quotation below', line))
    assert not bad, bad


def q_tokens_in_all_three_theme_blocks():
    # Replicata: the custom properties of index.html's three theme blocks.
    # Expectata: --exists, --open and --impossible are in it, as #rrggbb (one block since 2026-10-12: no dark mode).
    light, = theme_blocks()
    for t in TOKENS:
        assert t in light and re.fullmatch(r'#[0-9a-fA-F]{6}', light[t]), t


def q_palette_reads_for_color_blind_readers():
    # Replicata: the chart's three colors in each mode, with the validator's arithmetic, all pairs (any two touch).
    # Expectata: the worst pair in normal vision is at least the validator's floor 15.  (The colors are dreeves's to tweak
    # since 2026-10-12, so no comment states their numbers.  Until then it also held the color-blind pair to 8, exists
    # and impossible 0.25 apart in lightness, and each of the three 15 from each provenance hue, in a dark mode too.)
    light, = theme_blocks()
    assert worst_normal([light[t].lower() for t in TOKENS]) >= 15, [light[t] for t in TOKENS]


def q_chart_colors_stand_apart():
    # Replicata: the charts' colors and the table's provenance hues in each mode, and the page's CSS (dreeves,
    # 2026-10-12: the charts' gray and green too similar; their red too like the table's orange for Claude alone; "the
    # 'claude and BGPW' color could be a striping of the other two").
    # Expectata: the chart's colors are dreeves's to tweak (2026-10-12: "so i can tweak them myself"), so none is pinned
    # here; Claude and BGPW has no hue of its own (no --joint,
    # anywhere): its cells and legend key are stripes of --claude's and --stan's tints over a striped bar, and its glyph
    # is half in each hue.
    def lch(h):
        L, a, b = oklab(linear(h))
        return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360
    for mode, b in zip(('light',), theme_blocks()):
        assert '--joint' not in b, mode
    css = re.search(r'<style>(.*?)</style>', page(), re.S).group(1)
    assert '--joint' not in css
    tints = ('repeating-linear-gradient(135deg, color-mix(in oklab, var(--claude) var(--tint), var(--paper)) 0 0.3rem, '
             'color-mix(in oklab, var(--stan) var(--tint), var(--paper)) 0.3rem 0.6rem)')
    bar = 'repeating-linear-gradient(90deg, var(--claude) 0 0.3rem, var(--stan) 0.3rem 0.6rem) bottom / 100% 3px no-repeat'
    half = 'linear-gradient(90deg, var(--claude) 50%, var(--stan) 50%)'
    assert f'td.j, .key.j {{ background: {tints}; }}' in css
    assert f'tr.vals td.j, .key.j {{ background: {bar}, {tints}; box-shadow: none; }}' in css
    assert (f'tr.ns td.j::before, .key.j > span, .remarks li.j .mk {{ background: {half}; -webkit-background-clip: text; '
            'background-clip: text; color: transparent; }') in css
    assert '<span class="key j" aria-hidden="true"><span>◆●</span></span>' in page()


def q_new_results_n_cells_line_up():
    # Replicata: index.html in the browser (light, desktop): in each n row of the new results' tables, the bottom of the
    # first line of each cell's n (its digits, or the 2 of 2^k).
    # Expectata (dreeves, 2026-10-12: "minor spacing issue (remember anti-magic)"): the six rows' cells line up within
    # half a pixel, the uncolored copies of Table 2's powers of 2 among them: every n cell of the new results takes the
    # same room above its n, glyph or no glyph.
    rows = valid_run('light')['nTextBottoms']
    assert len(rows) == 6 and all(len(r) >= 5 for r in rows), rows
    assert all(max(r) - min(r) <= 0.5 for r in rows), rows


def q_new_results_fit_unscrolled_at_945_px():
    # Replicata: index.html with mstar.js, pow2.js and progress.js beside it, in headless Chrome with a window 945 px
    # wide: the widths of the new results' six tables and of their sideways-scrolling frame (.new-block .scroll).
    # Expectata (the CSS comment on the new results' side padding: "keeps it in one row, unscrolled, at 945 px"; since
    # 2026-10-25, when the powers of 2 reached 23, their two rows too): no table is wider than the frame, so the frame
    # does not scroll.
    d = tempfile.mkdtemp(prefix='index-quals-')
    try:
        for name in ('mstar.js', 'pow2.js', 'progress.js'): shutil.copy(os.path.join(HERE, name), d)
        script = ("<script>addEventListener('load', () => setTimeout(() => { const f = document.querySelector('.new-block .scroll'); "
                  "const p = document.createElement('pre'); p.id = 'fit'; p.textContent = JSON.stringify({frame: f.clientWidth, "
                  "scroll: f.scrollWidth, tables: [...f.querySelectorAll('table.block')].map(t => t.getBoundingClientRect().width)}); "
                  "document.body.append(p); }, 500));</script>\n")
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(page().replace('</body>', script + '</body>'))
        dom = chrome(d, ['--window-size=945,1200', '--virtual-time-budget=4000', '--dump-dom', 'file://' + os.path.join(d, 'index.html')])
    finally:
        shutil.rmtree(d)
    m = re.search(r'<pre id="fit">(.*?)</pre>', dom)
    assert m, dom[-500:]
    R = json.loads(m.group(1))
    assert len(R['tables']) == 6 and R['scroll'] <= R['frame'] and max(R['tables']) <= R['frame'], R


def q_remarks_name_the_chart_s_constructions():
    # Replicata: each remark sentence of the form Claude: "Order m from examples above, doubled (a = 2·b, ...) or joined
    # (a = b + c, ...); ...", item by item, against mstar.js's loWhy at a.
    # Expectata: every item is the chart's own construction: a = 2·b is ["product", 2, b], a = b + c is ["join", b, c],
    # as their TODOs say ("how the m*(n) chart gets these").  (On 2026-10-12 the example at 560 made the chart's joins
    # 240 + 560, 336 + 560 and 432 + 560 win its ties at 800, 896 and 992, which a remark still called doublings.)
    cols = mstar_data()['cols']
    items = 0
    for s in re.findall(r'Claude: "Order \d+ from examples above, (.*?); order', page()):
        for kind, body in re.findall(r'(doubled|joined) \(([^)]*)\)', s):
            for a, b, c in re.findall(r'(\d+) = (?:2·(\d+)|(\d+ \+ \d+))', body):
                want = ['product', 2, int(b)] if kind == 'doubled' else ['join', *map(int, c.split(' + '))]
                assert (kind == 'doubled') == bool(b), (kind, a, b, c)
                assert cols[int(a) - 1][2] == want, (a, cols[int(a) - 1][2], want)
                items += 1
    # (26 until 2026-10-25, when 592, 608, 656, 848, 880, 896, 928, 944, 976 and 992 left the grouped remarks for
    # entries of their own, with examples of their own; 16 until 2026-10-26, when 752, 784 and 832 did)
    assert items >= 13, items


def q_claude_rewords_what_the_day_made_stale():
    # Replicata: index.html: the 2^24 remark's paragraph, the footer, and the two labels of the order-9 example at 336.
    # Expectata (dreeves, 2026-10-12: "for the "TODO for dreeves" lines, go ahead and change them back to Claude: "…"
    # with your own corrected wording"): the 2^24 paragraph is Claude's and ends "…for every k ≥ 24, and by the 2^17
    # entry above for every k ≥ 17." (2^18 until 800's example of order 11, 2026-10-17); no sentence on examples not
    # re-checked is left (the footer had Claude's, naming only 416, until dreeves dropped it, 2026-10-24, commit 35dd836
    # "Edits"; its TODO comment went in b475924 the same day); the order-9 example
    # at 336 is q336 in both labels, the first Claude's (the powers-of-2 chart's p336 is the order-10 one); and no TODO
    # for dreeves is left.
    # Resultata before (2026-10-25): the qual still asked for Claude's line on 416, which his edit had dropped.
    text = page()
    assert 'TODO for dreeves' not in text and '<i>p</i><sub>336</sub>' not in text and 'at lengths 352, 368' not in text
    assert '<p>Claude: "Joint construction: ' in text
    assert ('≥ 24</span>, and by the 2<sup>17</sup> entry above for every <span class="nw"><i>k</i> ≥ 17</span>."</p>'
            in text)
    assert 'not re-checked here' not in text, 'a sentence on examples not re-checked'
    assert ('<span>Claude: "<i>q</i><sub>336</sub>, an antisymmetric example found independently by Claude; it is the second '
            'part of the 528 example below" <span class="nw">(<i>m</i> = 9)</span>:</span>') in text
    assert '<span><i>f</i> = <i>p</i><sub>192</sub> ∨ <i>q</i><sub>336</sub>; &nbsp;' in text


def q_2_18_shows_its_construction():
    # Replicata: the 2^18 remark on index.html, and certificate_2^18.wl beside it.
    # Expectata (dreeves, 2026-10-12: "for 2^18, index.html should show the proof, right? ... can we also get mathematica
    # code to generate the full list of 2^18/2 integers?"): the remark writes out the construction, (p320 # p560) ∨
    # (p48 # p432 # τ2), says where p48's code is, and links the script; the script decodes the four blocks from hex
    # codes that are exactly codes on the page.
    li = re.search(r'<p class="entry"><i>n</i> = 2<sup>18</sup>: .*?</li>', page(), re.S).group(0)
    assert '<span class="nw">(<i>p</i><sub>320</sub> # <i>p</i><sub>560</sub>)</span>' in li, li
    assert '<span class="nw">∨ (<i>p</i><sub>48</sub> # <i>p</i><sub>432</sub> # τ<sub>2</sub>)</span>' in li, li
    assert 'with the 2<sup>24</sup> entry below' in li and 'certificate_2%5E18.wl">certificate_2^18.wl</a>' in li, li
    wl = open(os.path.join(HERE, 'certificate_2^18.wl'), encoding='utf-8').read()
    codes = re.findall(r'(p\d+) = fromHex\["([0-9A-F]+)", \d+\];', wl)
    assert [k for k, _ in codes] == ['p320', 'p560', 'p432', 'p48'], codes
    assert all(f'<code>{h}</code>' in page() for _, h in codes), codes


def q_2_17_shows_its_construction():
    # Replicata: the 2^17 remark on index.html, and certificate_2^17.wl beside it.
    # Expectata (as for 2^18, which dreeves asked for on 2026-10-12; 800's example of order 11, 2026-10-17, moved the
    # first power of 2 that beats Thue-Morse by 1 from 2^18 to 2^17): the remark writes out the construction,
    # (p112 # p800) v (p48 # p432 # tau_1), says where p112's and p48's codes are, and links the script; the script
    # decodes the four blocks from hex codes that are exactly codes on the page.
    li = re.search(r'<p class="entry"><i>n</i> = 2<sup>17</sup>: .*?</li>', page(), re.S).group(0)
    assert '<span class="nw">(<i>p</i><sub>112</sub> # <i>p</i><sub>800</sub>)</span>' in li, li
    assert '<span class="nw">∨ (<i>p</i><sub>48</sub> # <i>p</i><sub>432</sub> # τ<sub>1</sub>)</span>' in li, li
    assert 'with the 2<sup>24</sup> entry below' in li and 'certificate_2%5E17.wl">certificate_2^17.wl</a>' in li, li
    wl = open(os.path.join(HERE, 'certificate_2^17.wl'), encoding='utf-8').read()
    codes = re.findall(r'(p\d+) = fromHex\["([0-9A-F]+)", \d+\];', wl)
    assert [k for k, _ in codes] == ['p112', 'p800', 'p48', 'p432'], codes
    assert all(f'<code>{h}</code>' in page() for _, h in codes), codes


def q_remarks_open_with_how_the_upper_bounds_are_proven():
    # Replicata: the start of index.html's section "Where the new results come from".
    # Expectata (dreeves, 2026-10-12: define "the norm bound" and "the residue condition", which the remarks and charts
    # cite, "in nice understandable non-llmish prose", with a note that certificates for the residue claims are tbd):
    # between the heading and the list of remarks, Claude's paragraphs on the residue condition, then the norm bound,
    # then the certificates still to be done.
    sec = re.search(r'<h2>Where the new results come from</h2>\n(.*?)\n  <ul>\n', page(), re.S).group(1)
    said = re.findall(r'<p>Claude: "(.*?)"</p>', sec)
    assert len(said) == 3, sec
    assert said[0].startswith('How the upper bounds are proven.') and 'The residue condition mod <i>M</i> rules out' in said[0]
    assert said[1].startswith('The norm bound for a prime <i>p</i> that does not divide <i>n</i>')
    assert 'are still to be done.' in said[2] and 'proof512.wl' in said[2]


def q_chart_agrees_with_tables():
    # Replicata: mstar.js (the chart's data) and the entries of the page's tables with n up to 1000.
    # Expectata: for each entry (n, low, high): the column's [lo, hi] lies inside [low, high], and an exact entry
    # (low = high) is lo = hi.  304's two entries (8 or 9 in Table 2, 8 since) both hold, and 240's (10 or 11 in
    # Table 2, 10 since 2026-10-20).
    cols = mstar_data()['cols']
    entries = table_entries()
    assert len(entries) == 38 + 1 + 43 + 7, len(entries)   # Table 2's; 240 (2026-10-20); the 43 multiples of 16; 2^3 to 2^9
    for n, low, high in entries:
        lo, hi = cols[n - 1][:2]
        assert low <= lo <= hi <= high, (n, low, high, lo, hi)


def q_new_results_state_what_the_chart_proves():
    # Replicata: the new results' tables on index.html (every n, the powers of 2 included, less the final row's copies of
    # Table 2's powers of 2, which Table 2 accounts for) and the remarks' entries under
    # "Where the new results come from" (each entry's n's and its "m* = v", "≥ v", "∈ {a, b, ...}" or "∈ {a, …, b}");
    # mstar.js's columns for n <= NMAX and pow2.js's for n = 2^k.
    # Expectata: every one states exactly its chart's [lo, hi] at its n, so no "≥" stands where a chart proves an upper
    # bound (dreeves's report of 2026-10-11: 432's entry said ≥ 11 beside the chart's 11–12; and 2^51's said ≥ 53
    # beside the powers-of-2 chart's 54–63 until 2026-10-12).
    cols, pow2 = mstar_data()['cols'], pow2_data()['cols']
    def chart(n):
        k = n.bit_length() - 1
        assert n <= NMAX or n == 2 ** k <= 2 ** pow2_data()['kmax'], n
        return cols[n - 1][:2] if n <= NMAX else pow2[k - 1][:2]
    def n_of(cell):
        m = re.fullmatch(r'(\d+)|2<sup>(\d+)</sup>', cell)
        assert m, cell
        return int(m.group(1)) if m.group(1) else 2 ** int(m.group(2))
    forms = ((r'(\d+)', lambda a: (a, a)), (r'(\d+) or (\d+)', lambda a, b: (a, b)), (r'(\d+)–(\d+)', lambda a, b: (a, b)),
             (r'≥ (\d+)', lambda a: (a, math.inf)), (r'= (\d+)', lambda a: (a, a)),
             (r'∈ \{(\d+)(?:, \d+)*, (\d+)\}', lambda a, b: (a, b)), (r'∈ \{(\d+), …, (\d+)\}', lambda a, b: (a, b)))
    def value(v):
        hits = [f(*map(int, m.groups())) for p, f in forms for m in [re.fullmatch(p, v)] if m]
        assert len(hits) == 1, v
        assert '…' in v or not v.startswith('∈') or [int(t) for t in re.findall(r'\d+', v)] == list(range(hits[0][0], hits[0][1] + 1)), v
        return hits[0]
    frame = re.search(r'<div class="new-block">.*?<div class="scroll">(.*?)</div>', page(), re.S).group(1)
    table = []
    for t in re.findall(r'<table class="block">.*?</table>', frame, re.S):
        ns = re.findall(r'<td([^>]*)>(.*?)</td>', re.search(r'<tr class="ns">.*?</tr>', t, re.S).group(0))
        vs = re.findall(r'<td[^>]*>(.*?)</td>', re.search(r'<tr class="vals">.*?</tr>', t, re.S).group(0))
        assert len(ns) == len(vs) and ns, t
        table += [(n_of(n), *value(v)) for (attr, n), v in zip(ns, vs)
                  if "title='The published paper (2021)'" not in attr]    # copies of Table 2, which says where they come from
    remarks = []
    for ns, v in re.findall(r'<p class="entry"><i>n</i> = ([^:]*): &nbsp;<span class="nw"><i>m</i><sup>\*</sup> ([^<]*)</span>',
                            page()):
        remarks += [(n_of(n), *value(v)) for n in ns.split(', ')]
    assert sorted(n for n, *_ in table) == sorted(n for n, *_ in remarks), (table, remarks)
    wrong = [(where, n, lo, hi, chart(n)) for where, got in (('table', table), ('remark', remarks))
             for n, lo, hi in got if [lo, hi] != chart(n)]
    assert not wrong, wrong


def q_citations_match_the_page():
    # Replicata: mstar.js's reasons that cite the page: ["table2"] and ["page", who], as loWhy or hiWhy; the new
    # results' cell titles; the remarks under "Where the new results come from", each by the n its entry lists.
    # Expectata: a ["table2"] column is one of Table 2's n; a ["page", who] column is one of the new results' n.  As
    # hiWhy, who is its cell's title (whose proof); as loWhy, its remark credits the example to who, saying
    # "example(s) of order lo found by who." (at 496 the title credits Claude and BGPW, for the proof of the upper
    # bound, and the remark credits BGPW for the example).
    fig = re.search(r'<figure>.*?</figure>', page(), re.S).group(0)
    new = re.search(r'<div class="new-block">.*?<div class="scroll">(.*?)</div>', fig, re.S).group(1)
    value = lambda cell: int(cell) if cell.isdigit() else 2 ** int(re.fullmatch(r'2<sup>(\d+)</sup>', cell).group(1))
    titled = {value(n): who for who, n in re.findall(r"<td(?: class=\"(?:a|c|ca|j|s)\")? title='([^']*)'>([^<]*(?:<sup>\d+</sup>)?)</td>", new)}
    titles = {n: who for n, who in titled.items() if who != 'The published paper (2021)'}
    # 240 (since 2026-10-20), the 44 multiples of 16 from 304 to 992 (512 written 2^9) and 25 larger powers of 2,
    # 2^17 to 2^72 (6 until 560 reached order 10 on 2026-10-12, 11 until 800 reached order 11 on 2026-10-17, 18
    # until 592, 608 and 656 reached order 10 and 848, 880, 896, 928, 944, 976 and 992 order 11 on 2026-10-25, 23
    # until 752 and 784 reached order 10 and 832 order 11 on 2026-10-26)
    assert len(titles) == 1 + 44 + 25 and sorted(n for n, who in titled.items() if n not in titles) == [8, 16, 32, 64, 128, 256], titled
    table2 = {n for n, *_ in table_entries()} - set(titles)
    assert len(table2) == 36, sorted(table2)          # 240 and 304 are in both
    section = re.search(r'<section class="remarks">(.*?)</section>', page(), re.S).group(1)
    remarks = {int(n): body for ns, body in re.findall(r'<p class="entry"><i>n</i> = ([\d, ]+):(.*?)</li>', section, re.S)
               for n in ns.split(', ')}
    cited = 0
    for n, (lo, hi, lw, hw) in enumerate(mstar_data()['cols'], 1):
        for w in (lw, hw):
            if w[0] == 'table2': assert n in table2 | {304}, (n, w); cited += 1
            if w[0] == 'page': assert n in titles, (n, w); cited += 1
        if hw[0] == 'page': assert titles[n] == hw[1], (n, hw, titles[n])
        if lw[0] == 'page':
            assert re.search(rf'\b[Ee]xamples? of order {lo} found by {re.escape(lw[1])}\.', remarks[n]), (n, lw, remarks[n])
    assert cited, 'mstar.js cites neither table'


def q_claude_and_astra_is_a_category_like_claude_and_bgpw():
    # Replicata: the page's CSS, its legend, the new results' cells and the remarks' entries of 592, 608, 656, 752 and
    # 784.
    # Expectata (2026-10-25, the main session's ruling on dreeves's "a new 'Claude and Astra' category makes sense to
    # me"): as Claude and BGPW's (q_chart_colors_stand_apart), the class ca has no hue of its own: its cells and legend
    # key are stripes of --claude's and --astra's tints over a striped bar, and its glyph ◆✦ is half in each hue; the
    # legend has the line "Claude and Astra" right after "Astra alone"; the cells titled Claude and Astra are 592, 608,
    # 656 and 752, each of class ca with its value; and each of their remarks is an <li class="ca"> marked ◆✦.  (Since
    # 2026-10-26 also 784, credited for the reason 608 and 656 are, and 752 at 10, both by examples of order 10.)
    css = re.search(r'<style>(.*?)</style>', page(), re.S).group(1)
    tints = ('repeating-linear-gradient(135deg, color-mix(in oklab, var(--claude) var(--tint), var(--paper)) 0 0.3rem, '
             'color-mix(in oklab, var(--astra) var(--tint), var(--paper)) 0.3rem 0.6rem)')
    bar = 'repeating-linear-gradient(90deg, var(--claude) 0 0.3rem, var(--astra) 0.3rem 0.6rem) bottom / 100% 3px no-repeat'
    half = 'linear-gradient(90deg, var(--claude) 50%, var(--astra) 50%)'
    assert 'td.ca { --glyph: "◆✦"; }' in css
    assert f'td.ca, .key.ca {{ background: {tints}; }}' in css
    assert f'tr.vals td.ca, .key.ca {{ background: {bar}, {tints}; box-shadow: none; }}' in css
    assert (f'tr.ns td.ca::before, .key.ca > span, .remarks li.ca .mk {{ background: {half}; -webkit-background-clip: text; '
            'background-clip: text; color: transparent; }') in css
    text = page()
    assert ('    <li><span class="key a" aria-hidden="true">✦</span>Astra alone</li>\n'
            '    <li><span class="key ca" aria-hidden="true"><span>◆✦</span></span>Claude and Astra</li>\n') in text
    new = re.search(r'<div class="new-block">.*?<div class="scroll">(.*?)</div>', text, re.S).group(1)
    ca = []
    for t in re.findall(r'<table class="block">.*?</table>', new, re.S):
        ns = re.findall(r'<td([^>]*)>(.*?)</td>', re.search(r'<tr class="ns">.*?</tr>', t, re.S).group(0))
        vs = re.findall(r'<td([^>]*)>(.*?)</td>', re.search(r'<tr class="vals">.*?</tr>', t, re.S).group(0))
        assert len(ns) == len(vs), t
        for (a, n), (b, v) in zip(ns, vs):
            assert ("title='Claude and Astra'" in a) == (a == ' class="ca" title=\'Claude and Astra\'') == (b == ' class="ca"'), (n, a, b)
            if b == ' class="ca"': ca.append((n, v))
    assert ca == [('592', '10'), ('608', '10'), ('656', '10'), ('752', '10'), ('784', '10')], ca
    for n in (592, 608, 656, 752, 784):
        li = re.search(r'<li class="(\w+)">\n      <span class="mk" aria-hidden="true">([^<]*)</span>\n      <p class="entry"><i>n</i> = '
                       + str(n) + r': ', text)
        assert li and li.groups() == ('ca', '◆✦'), (n, li and li.groups())


def q_examples_of_2026_10_25_have_entries_codes_and_sets():
    # Replicata: the remarks' entries of 592, 608, 656 (order 10) and 848, 880, 896, 928, 944, 976, 992 (order 11),
    # each code in them decoded by the paper's Table 5 convention (the left half of the signs, 1 = +1, then the rest by
    # (-1)^m symmetry), the page's sets SClaude[m][n], and mstar.js's columns.
    # Expectata: each n has an entry of its own, "m* = m", in 800's form: Claude's line "A symmetric example of order
    # 10." (592, 608, 656, which also say what Astra did) or "An antisymmetric example of order 11.", ending "Order m + 1
    # is ruled out by" the reason mstar.js gives as hiWhy; its one code block, p_n of order m, whose signs have order
    # exactly m (synthetic division here) and the symmetry the line says; the set SClaude[m][n] is exactly that
    # sequence's +1 positions, 0 among them; and mstar.js's column n is [m, m, ["example", "index.html p" + n], hiWhy].
    text, cols = page(), mstar_data()['cols']
    reason = {('norm', 3): 'the norm bound for the residue sums mod 3', ('residue', 3): 'the residue condition mod 3'}
    sets = {(int(m), int(n)): {int(t) for t in body.split(',')}
            for m, n, body in re.findall(r'SClaude\[(\d+)\]\[(\d+)\] = \{([^}]*)\};', text)}
    def order(a):                                  # (x - 1) divides exactly order(a) times: synthetic division
        c, k = list(a), 0
        while not sum(c): c, k = [sum(c[:i + 1]) for i in range(len(c) - 1)], k + 1
        return k
    for n, m in [(592, 10), (608, 10), (656, 10)] + [(n, 11) for n in (848, 880, 896, 928, 944, 976, 992)]:
        li = re.search(r'<li class="\w+">\n      <span class="mk" aria-hidden="true">[^<]*</span>\n      <p class="entry"><i>n</i> = '
                       + str(n) + r': &nbsp;<span class="nw"><i>m</i><sup>\*</sup> = (\d+)</span></p>\n(.*?)\n    </li>', text, re.S)
        assert li and int(li.group(1)) == m, n
        lo, hi, lw, hw = cols[n - 1]
        assert [lo, hi, lw] == [m, m, ['example', f'index.html p{n}']], (n, cols[n - 1])
        said = re.findall(r'<p>Claude: "(.*?)"</p>', li.group(2))
        kind = 'A symmetric example of order 10.' if m == 10 else 'An antisymmetric example of order 11.'
        assert len(said) == 1 and said[0].startswith(kind) and said[0].endswith(f' Order {m + 1} is ruled out by {reason[tuple(hw)]}.'), (n, said)
        assert ('Astra' in said[0]) == (n < 700), (n, said)
        codes = re.findall(r'<p class="code">\n        <span><i>p</i><sub>(\d+)</sub> <span class="nw">\(<i>m</i> = (\d+)\)</span>:</span>\n'
                           r'        <code>([0-9A-F]+)</code>\n      </p>', li.group(2))
        assert len(codes) == 1 and codes[0][:2] == (str(n), str(m)), (n, codes)
        h = codes[0][2]
        left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
        a = left + [(-1) ** m * s for s in reversed(left)]
        assert len(a) == n and order(a) == m, (n, len(a), order(a))
        assert sets[m, n] == {i for i, s in enumerate(a) if s == 1} and 0 in sets[m, n], n


def q_752_bound_cites_proof752():
    # Replicata: the remarks' entry of 752, mstar.js's column 752, and the repository's files.
    # Expectata (2026-10-25: proof752.py proves m*(752) <= 10, extending Astra's method for 384 with Claude's meet in
    # the middle): Claude's first line says order 11 is ruled out by proof752.py, linked at its GitHub address, the
    # second line says how; mstar.js's column 752 has hi 10 and hiWhy ["page", "Claude and Astra"]; and proof752.py is
    # in the working directory.  Since 2026-10-26, when Claude's search found an example of order 10 at 752, the entry
    # is "m* = 10", the first line is the example's (q_examples_of_2026_10_26_have_entries_codes_and_sets) ending "Order
    # 11 is ruled out by an exact proof, proof752.py.", and the column is [10, 10, ["example", "index.html p752"], …];
    # until then the entry was "m* ∈ {9, 10}", the first line giving the chart's join 192 + 560 of order 9.
    li = re.search(r'<p class="entry"><i>n</i> = 752: &nbsp;<span class="nw"><i>m</i><sup>\*</sup> = 10</span></p>\n(.*?)\n    </li>',
                   page(), re.S)
    assert li, 'no entry for 752 alone'
    said = re.findall(r'<p>Claude: "(.*?)"</p>', li.group(1))
    assert len(said) == 2 and said[0].startswith('A symmetric example of order 10.') and said[0].endswith(
        ' Order 11 is ruled out by an exact proof, <a href="https://github.com/dreeves/equipow/blob/main/proof752.py">'
        'proof752.py</a>.'), said
    assert 'meet in the middle' in said[1] and 'Astra' in said[1], said[1]
    assert mstar_data()['cols'][752 - 1] == [10, 10, ['example', 'index.html p752'], ['page', 'Claude and Astra']]
    assert os.path.isfile(os.path.join(HERE, 'proof752.py'))


def q_288_bound_is_proved_here():
    # Replicata: index.html's figure of Table 2, mstar.js's column 288, and the repository's files.
    # Expectata (2026-10-25: proof288.py proves m*(288) <= 10, Table 2's upper value, so no cell changes): right after
    # dreeves's note on Stong (STONG_NOTE), a TODO comment and one line of Claude's that links proof288.py at its GitHub
    # address; Table 2's cell at 288 still reads "9 or 10" (q_table2_credits_stong_for_2_51) and mstar.js's column 288
    # cites it, [9, 10, …, ["table2"]]; and proof288.py is in the working directory.
    fig = re.search(r'<figure>.*?</figure>', page(), re.S).group(0)
    m = re.search(re.escape(STONG_NOTE) + r'\n    <!-- TODO: [^\n]*-->\n    <p>Claude: "([^\n]*)"</p>\n\n    <div class="new-block">', fig)
    assert m, fig[fig.index('Stong'):][:600]
    assert '<a href="https://github.com/dreeves/equipow/blob/main/proof288.py">proof288.py</a>' in m.group(1), m.group(1)
    assert 'order 11' in m.group(1), m.group(1)
    col = mstar_data()['cols'][288 - 1]
    assert col[:2] == [9, 10] and col[3] == ['table2'], col
    assert os.path.isfile(os.path.join(HERE, 'proof288.py'))


def q_examples_of_2026_10_26_have_entries_codes_and_sets():
    # Replicata: the remarks' entries of 752 and 784 (order 10) and 832 (order 11), each code in them decoded by the
    # paper's Table 5 convention (the left half of the signs, 1 = +1, then the rest by (-1)^m symmetry), the page's sets
    # SClaude[m][n], the order of the remarks' entries, and mstar.js's columns.
    # Expectata (2026-10-26, the second recording pass): each n has an entry of its own, "m* = m", in the form of the
    # first pass's (q_examples_of_2026_10_25_have_entries_codes_and_sets): Claude's first line "A symmetric example of
    # order 10." (752 and 784, which also say what Astra did, as 608's and 656's do) or "An antisymmetric example of
    # order 11." (832), ending "Order m + 1 is ruled out by" the reason mstar.js gives as hiWhy (at 752 the page's,
    # proof752.py, whose entry keeps its line on how, q_752_bound_cites_proof752); its one code block, p_n of order m,
    # whose signs have order exactly m (synthetic division here) and the symmetry the line says; the set SClaude[m][n]
    # is exactly that sequence's +1 positions, 0 among them; mstar.js's column n is [m, m, ["example",
    # "index.html p" + n], hiWhy]; no entry lists n with another n; and the entries run in order of n among the
    # examples': 656's, 752's, 784's, 800's, 832's, 848's.
    text, cols = page(), mstar_data()['cols']
    reason = {('norm', 3): 'the norm bound for the residue sums mod 3', ('residue', 27): 'the residue condition mod 27',
              ('page', 'Claude and Astra'): 'an exact proof, <a href="https://github.com/dreeves/equipow/blob/main/proof752.py">proof752.py</a>'}
    sets = {(int(m), int(n)): {int(t) for t in body.split(',')}
            for m, n, body in re.findall(r'SClaude\[(\d+)\]\[(\d+)\] = \{([^}]*)\};', text)}
    def order(a):                                  # (x - 1) divides exactly order(a) times: synthetic division
        c, k = list(a), 0
        while not sum(c): c, k = [sum(c[:i + 1]) for i in range(len(c) - 1)], k + 1
        return k
    for n, m, lines in ((752, 10, 2), (784, 10, 1), (832, 11, 1)):
        li = re.search(r'<li class="\w+">\n      <span class="mk" aria-hidden="true">[^<]*</span>\n      <p class="entry"><i>n</i> = '
                       + str(n) + r': &nbsp;<span class="nw"><i>m</i><sup>\*</sup> = (\d+)</span></p>\n(.*?)\n    </li>', text, re.S)
        assert li and int(li.group(1)) == m, n
        lo, hi, lw, hw = cols[n - 1]
        assert [lo, hi, lw] == [m, m, ['example', f'index.html p{n}']], (n, cols[n - 1])
        said = re.findall(r'<p>Claude: "(.*?)"</p>', li.group(2))
        kind = 'A symmetric example of order 10.' if m == 10 else 'An antisymmetric example of order 11.'
        assert len(said) == lines and said[0].startswith(kind) and said[0].endswith(f' Order {m + 1} is ruled out by {reason[tuple(hw)]}.'), (n, said)
        assert ("Astra's lattice code" in said[0]) == (n < 800), (n, said)
        codes = re.findall(r'<p class="code">\n        <span><i>p</i><sub>(\d+)</sub> <span class="nw">\(<i>m</i> = (\d+)\)</span>:</span>\n'
                           r'        <code>([0-9A-F]+)</code>\n      </p>', li.group(2))
        assert len(codes) == 1 and codes[0][:2] == (str(n), str(m)), (n, codes)
        h = codes[0][2]
        left = [1 if b == '1' else -1 for b in bin(int(h, 16))[2:].zfill(4 * len(h))]
        a = left + [(-1) ** m * s for s in reversed(left)]
        assert len(a) == n and order(a) == m, (n, len(a), order(a))
        assert sets[m, n] == {i for i, s in enumerate(a) if s == 1} and 0 in sets[m, n], n
    listed = [ns.split(', ') for ns in re.findall(r'<p class="entry"><i>n</i> = ([^:]*): ', text)]
    assert [ns for ns in listed if {'752', '784', '832'} & set(ns)] == [['752'], ['784'], ['832']], listed
    run = [ns[0] for ns in listed if ns[0] in ('656', '752', '784', '800', '832', '848')]
    assert run == ['656', '752', '784', '800', '832', '848'], run


# ---------------------------------------------------------------------------------------------------------------------
# Browser quals

def q_page_loads_clean():
    # Replicata: index.html with the real mstar.js in headless Chrome, 1280 px wide at 2 device px per CSS px; and the
    # page loaded as is (nothing added), with Chrome logging its console to stderr.
    # Expectata: no errors, console errors or warnings; the canvas is drawn (nonzero height, as wide as main's content);
    # the readout still shows dreeves's hint (HINT); the chart opens showing all 500 columns, n = 2 to 1000.  The plain
    # load logs nothing at all to the console.
    assert console_lines() == [], console_lines()
    R = valid_run('light')
    assert R['canvasDev'][1] > 0 and close(R['canvasCss'][0], R['mainContentW'], 1), R
    assert R['readout0'] == HINT, R['readout0']
    v = R['views'][0]
    assert close(v['u0'], 0, 0.01) and close(v['span'], NCOL, 0.05), v


def q_drawn_cells_match_data():
    # Replicata: the light and phone runs: the full view, and a sweep of the 500 columns n = 2, 4, …, 1000
    # zoomed in, so every column is at least 3 device px wide.
    # Expectata: every even column is checked, in every row: its middle pixel has its color from mstar.js (exists up
    # to lo, open up to hi, impossible above) as the page's tokens give it, and the pixel below each row is paper.  In
    # the full view and every view of the sweep, every pixel of row 1 is exists, from the plot's left edge to its
    # right: no odd column (impossible in every row, since lo = hi = 0) is drawn, not even mixed into a pixel; but for
    # the ring of a cell of row 1 (q_chart_rings_a323395_terms_in_gold), passed over a device px either side
    # (rowOneSkips), and the cells next to a ring in its row and the row above, which that qual checks instead.
    data = mstar_data()
    assert all(data['cols'][n - 1][0] >= 1 for n in EVEN), 'some even column has no exists cell in row 1'
    for name in ('light', 'phone'):
        R = valid_run(name)
        assert R['pixelBad'] == [], (name, R['pixelBad'][:10])
        assert R['pixelColumns'] == EVEN, (name, sorted(set(EVEN) ^ set(R['pixelColumns']))[:20])
        assert R['pixelChecks'] >= NCOL * len(R['rows']), (name, R['pixelChecks'])
        assert len(R['rows']) == data['mtop'], (name, len(R['rows']))
        assert R['rowOneBad'] == [], (name, len(R['rowOneBad']), R['rowOneBad'][:10])
        assert R['rowOneChecks'] + R['rowOneSkips'] == len(R['views']) * (R['plot'][1] - R['plot'][0]), (name, R['rowOneChecks'])
        assert R['rowOneSkips'] <= len(R['views']) * (4 * R['dpr'] + 6), (name, R['rowOneSkips'])


def q_chart_rings_a323395_terms_in_gold():
    # Replicata: the light and phone runs: the cells the chart rings (R's records), the ring checks of the sweep, and
    # the token --record.
    # Expectata (dreeves, 2026-10-19: "in the chart can you highlight the known values for a(m-1)? maybe make those
    # green with gold trim or whatever else you think might work visually"): the ringed cells are exactly
    # a323395_cells of mstar.js, today (2, 1), (4, 2), (8, 3), (16, 4), (32, 5), (48, 6), (96, 7), (144, 8), (192, 9)
    # (240, 10) and (432, 11), SMALLEST_PROVEN by order; each is ringed in --record, #ffb300 (the validator's pick against
    # the chart's three colors and the paper), just outside its left and right and below it, in each view of the
    # sweep that checks it, and every one is checked.  (Its readout's note: q_hover_reads_out_cells.)
    want = a323395_cells(mstar_data()['cols'])
    assert want == [(n, m) for m, n in enumerate(SMALLEST_PROVEN, 1)], want
    for name in ('light', 'phone'):
        R = valid_run(name)
        assert [tuple(c) for c in R['records']] == want, (name, R['records'])
        assert R['tokens']['record'] == '#ffb300', (name, R['tokens'])
        assert R['ringChecks'] >= len(want) and R['ringBad'] == [], (name, R['ringChecks'], R['ringBad'][:5])
        assert sorted(map(int, R['ringed'])) == [n for n, _ in want], (name, R['ringed'])


def q_readout_reports_even_n_only():
    # Replicata: the light and phone runs: every hover of the harness (the full view, every view of the sweep, the
    # searches for column edges, which probe within a millionth of a px of them, and the interactions), and a hover at
    # the middle of every device px across row 1 of the full view.
    # Expectata: no readout reports an odd n; across the full view the readout goes through n = 2, 4, …, 1000, each
    # once, in order from left to right.
    for name in ('light', 'phone'):
        R = valid_run(name)
        assert R['oddReadouts'] == [] and R['readouts'] > 2 * NCOL, (name, R['readouts'], R['oddReadouts'][:5])
        assert R['across'] == EVEN, (name, R['across'][:20])


def q_n_labels_are_even_and_round():
    # Replicata: the n labels (the strings drawn below the rows, right of the plot's left edge) of one draw in each of
    # the full view, every view of the sweep, and the view zoomed in as far as it goes; in the light and phone runs.
    # Expectata: they are the multiples of one step s, from 2, 10, 20, 50, 100, 200, 500 (so every label is an even n),
    # whose columns' middles are in view, in order, each centered on its column's middle to within a device px; s is
    # the first of those steps that puts the labels at least 48 CSS px apart.
    for name in ('light', 'phone'):
        R = valid_run(name)
        (PL, PR), dpr = R['plot'], R['dpr']
        assert len(R['labelDraws']) == len(R['views']) + 1, (name, len(R['labelDraws']))
        for d in R['labelDraws']:
            v, got = d['v'], d['labels']
            s = next(s for s in STEPS if s / 2 * (PR - PL) / dpr / v['span'] >= 48)
            want = [n for n in range(s, NMAX + 1, s) if v['u0'] - 1e-6 <= n / 2 - 0.5 <= v['u0'] + v['span'] + 1e-6]
            assert [t for t, _ in got] == [str(n) for n in want], (name, v, s, got)
            for t, x in got:
                assert close(x, PL + (int(t) / 2 - 0.5 - v['u0']) * (PR - PL) / v['span'], 1), (name, v, t, x)


def q_zoom_buttons_sit_beside_show_all():
    # Replicata: the chart's section.
    # Expectata: right before the reset button, with only blank space and comments between, a zoom-out button labelled
    # − and then a zoom-in button labelled + (math, not English); each has dreeves's aria-label (ZOOM_LABELS) and a
    # title that is Claude: "…"; and the hint in the readout, his (HINT), mentions the − and + buttons.
    s = section()
    tags = {i: re.search(rf'<button type="button" id="{i}"([^>]*)>([^<]*)</button>', s)
            for i in ('mstar-zoom-out', 'mstar-zoom-in', 'mstar-reset')}
    assert all(tags.values()), {i: bool(t) for i, t in tags.items()}
    out, zin, reset = tags.values()
    for a, b in ((out, zin), (zin, reset)):
        assert re.fullmatch(r'(?:\s|<!--.*?-->)*', s[a.end():b.start()], re.S), s[a.end():b.start()]
    for t, label, aria in ((out, '−', ZOOM_LABELS[0]), (zin, '+', ZOOM_LABELS[1])):
        attrs, text = t.groups()
        assert text == label, (t.group(0), label)
        v = re.search(r"\baria-label='([^']*)'", attrs)
        assert v and v.group(1) == aria, attrs
        v = re.search(r"\btitle='([^']*)'", attrs)
        assert v and re.fullmatch(r'Claude: "[^"]*"', v.group(1)), attrs
    hint = re.search(r'<p id="mstar-readout" aria-live="polite">([^<]*)</p>', s)
    assert hint and hint.group(1) == HINT and '−' in HINT and '+' in HINT and 'buttons' in HINT, s


def q_zoom_buttons_zoom_about_the_middle():
    # Replicata: the light run: the zoom buttons at load; a click of each from a view zoomed in 3 steps; then, from the
    # full view, clicks of + until it is disabled and then of − until it is disabled, the view measured after each; and
    # the buttons after every interaction step (keys, wheels, drags, pinches, gestures, reset).
    # Expectata: + zooms in by 1.5 and − out by 1.5 about the middle (the u at the middle stays), as the + and − keys do,
    # stopping at 12 and 500 columns: 10 clicks each way.  + is disabled exactly when the view is 12 columns and −
    # exactly when it is all 500: at load (− only), after every click and after every step (so − after the reset
    # button).  A disabled button is grayed out, not hidden: opacity at most 0.5 but displayed, visible and as big as
    # the other, whose opacity is 1.
    R = valid_run('light')
    assert 'buttonsError' not in R, R['buttonsError']
    S = R['steps']
    for name, f in (('zoomInButton', 1 / 1.5), ('zoomOutButton', 1.5)):
        a, b = S[name]['a'], S[name]['b']
        assert close(b['span'], a['span'] * f, 1e-3) and close(b['u0'] + b['span'] / 2, a['u0'] + a['span'] / 2, 1e-3), (name, S[name])
    clicks = R['clicks']
    assert [k for k, *_ in clicks] == ['start'] + ['in'] * 10 + ['out'] * 10, [k for k, *_ in clicks]
    for (_, a, _), (kind, b, _) in zip(clicks, clicks[1:]):
        want = min(max(a['span'] * (1 / 1.5 if kind == 'in' else 1.5), MIN_SPAN), NCOL)
        assert close(b['span'], want, 1e-3) and close(b['u0'] + b['span'] / 2, a['u0'] + a['span'] / 2, 1e-3), (a, kind, b)
    states = [(v, d) for _, v, d in clicks] + [(s['b'], s['disabled']) for s in S.values()] + [(R['views'][0], R['disabled0'])]
    for v, d in states:
        assert d == [close(v['span'], MIN_SPAN, 0.01), close(v['span'], NCOL, 0.05)], (v, d)
    zin, zout = R['looks0']
    assert zin['opacity'] == 1 and zout['opacity'] <= 0.5 and zout['display'] != 'none' and zout['visibility'] == 'visible', R['looks0']
    assert all(close(a, b, 2) for a, b in zip(zout['size'], zin['size'])) and min(zout['size']) > 10, R['looks0']


def q_heading_says_even_n():
    # Replicata: the chart's heading and the canvas's label for screen readers, which are dreeves's words since his
    # copyedit (it dropped the caption that said why odd n are left out).
    # Expectata: the heading is HEADING, which says "every even n", and the label is CANVAS_LABEL, which says "even n":
    # the chart has a column for each even n only.
    s = section()
    heading = re.search(r'<h2 id="mstar-title">(.*?)</h2>', s).group(1)
    assert heading == HEADING and 'every even <i>n</i>' in heading, heading
    label = re.search(r"<canvas [^>]*aria-label='([^']*)'", s).group(1)
    assert label == CANVAS_LABEL and 'even n' in label, label


def q_light_run_uses_the_theme_tokens():
    # Replicata: the light run.
    # Expectata: the chart's colors, paper and ink are the theme block's values (the pixel checks of
    # q_drawn_cells_match_data compare against these).  (A dark run did the same for the dark blocks until 2026-10-12.)
    light, = theme_blocks()
    tokens = valid_run('light')['tokens']
    assert all(tokens[t[2:]] == light[t].lower() for t in TOKENS + ('--paper', '--ink')), tokens


def q_hover_reads_out_cells():
    # Replicata: the light run's hovers: the middle of cells lo, lo + 1 and hi + 1 of every column, in the full view
    # and zoomed in; and the kinds run's, on made-up data with every kind of reason.
    # Expectata: each readout is "n = N, m = M · BOUNDS · REASONS" for the hovered cell, BOUNDS being "m*(N) = lo"
    # when lo = hi and "lo ≤ m*(N) ≤ hi" otherwise; REASONS are Claude: "…" strings: for a green cell (m ≤ lo) one
    # that starts "order lo ", for a red cell (m > hi) one that starts "order hi+1 ", for a gray cell both, joined by
    # " · "; and for a cell ringed in gold (a323395_cells, since 2026-10-19) one more, ring_note.  Every column, n = 2,
    # 4, …, 1000, is read out in both runs.
    for name in ('light', 'kinds'):
        R = valid_run(name)
        cols = json.loads(kinds_data()[len('const MSTAR = '):-2])['cols'] if name == 'kinds' else mstar_data()['cols']
        assert {n for n, _, _ in R['hovers']} == set(EVEN), name
        rings = a323395_cells(cols)
        for n, m, text in R['hovers']:
            lo, hi = cols[n - 1][:2]
            bounds = f'm*({n}) = {lo}' if lo == hi else f'{lo} ≤ m*({n}) ≤ {hi}'
            reasons = [f'order {lo} '] * (m <= hi) + [f'order {hi + 1} '] * (m > lo) + [ring_note(m)] * ((n, m) in rings)
            got = re.fullmatch(r'n = (\d+), m = (\d+) · (.*?) · (Claude: ".*")', text)
            assert got and (int(got[1]), int(got[2]), got[3]) == (n, m, bounds), (name, n, m, text)
            parts = re.findall(r'Claude: "([^"]*)"', got[4])
            assert ' · '.join(f'Claude: "{p}"' for p in parts) == got[4], (name, text)
            assert len(parts) == len(reasons) and all(p.startswith(r) for p, r in zip(parts, reasons)), (name, n, m, text)


def q_hover_swatch_matches_gold_trim():
    # Replicata: the light and kinds runs' hover sweeps, sampling the readout swatch after each cell selection.
    # Expectata: all proven OEIS cells (all 11 in the real data) have a 2 px gold ring on their swatch, every other
    # swatch has no ring, and its fill retains the cell's exists/open/impossible color.  The sweeps include both
    # directions of transition between record and ordinary cells, so a ring cannot persist after leaving a record.
    # Resultata: each assertion reports the hovered cell and its expected and computed CSS values.
    rgb = lambda h: 'rgb(' + ', '.join(str(int(h[i:i + 2], 16)) for i in (1, 3, 5)) + ')'
    assert a323395_cells(mstar_data()['cols']) == [(n, m) for m, n in enumerate(SMALLEST_PROVEN, 1)]
    for name in ('light', 'kinds'):
        R = valid_run(name)
        cols = json.loads(kinds_data()[len('const MSTAR = '):-2])['cols'] if name == 'kinds' else mstar_data()['cols']
        rings = set(a323395_cells(cols))
        swatches = R['swatches']
        assert rings <= {(n, m) for n, m, _, _ in swatches}, (name, rings, swatches)
        assert {(False, True), (True, False)} <= {
            (tuple(a[:2]) in rings, tuple(b[:2]) in rings) for a, b in zip(swatches, swatches[1:])}, name
        assert {0, 1, 2} == {(m <= cols[n - 1][0]) + (m <= cols[n - 1][1])
                            for n, m, _, _ in swatches if (n, m) not in rings}, name
        shadows = {False: 'none', True: rgb(R['tokens']['record']) + ' 0px 0px 0px 2px'}
        for n, m, fill, shadow in swatches:
            lo, hi = cols[n - 1][:2]
            kind = ('impossible', 'open', 'exists')[(m <= lo) + (m <= hi)]
            want = (rgb(R['tokens'][kind]), shadows[(n, m) in rings])
            assert (fill, shadow) == want, (name, n, m, 'expected', want, 'computed', (fill, shadow))


def q_visible_text_is_attributed():
    # Replicata: every string the kinds and light runs drew on the canvas, and every readout they showed.
    # Expectata: canvas strings are numbers or the single letters n and m; outside Claude: "…" a readout holds no
    # English (no run of two letters); and the readout's hint and the canvas's label are dreeves's words, exactly
    # (HINT, CANVAS_LABEL).
    for name in ('kinds', 'light'):
        R = valid_run(name)
        assert R['texts'] and all(re.fullmatch(r'\d+|[nm]', t) for t in R['texts']), (name, R['texts'])
        for *_, text in R['hovers']: assert not english(unclaimed(text)), (name, text)
        assert R['readout0'] == HINT, R['readout0']
    label = re.search(r"<canvas [^>]*aria-label='([^']*)'", section()).group(1)
    assert label == CANVAS_LABEL, label


def q_keys_pan_and_zoom():
    # Replicata: from a view zoomed in 3 steps, with the canvas focused: one keydown each of ArrowRight, ArrowLeft, +,
    # =, -, ArrowDown, ctrl and +, cmd and ArrowRight.
    # Expectata: the arrows pan by an eighth of the view (u0 ± span/8) without zooming; + and = zoom in by 1.5 and -
    # out by 1.5, about the middle; those keys' default actions are prevented.  ArrowDown, ctrl + and cmd ArrowRight
    # change nothing and keep their default actions (page scroll, browser zoom, history).
    S = valid_run('light')['steps']
    for name, sign in (('right', 1), ('left', -1)):
        a, b, prevented = S[name]['a'], S[name]['b'], S[name]['x']
        assert prevented and close(b['span'], a['span'], 1e-3) and close(b['u0'] - a['u0'], sign * a['span'] / 8, 1e-3), (name, S[name])
    for name, f in (('plus', 1 / 1.5), ('equals', 1 / 1.5), ('minus', 1.5)):
        a, b, prevented = S[name]['a'], S[name]['b'], S[name]['x']
        assert prevented and close(b['span'], a['span'] * f, 1e-3), (name, S[name])
        assert close(b['u0'] + b['span'] / 2, a['u0'] + a['span'] / 2, 1e-3), (name, S[name])
    for name in ('down', 'ctrlPlus', 'metaRight'):
        a, b, prevented = S[name]['a'], S[name]['b'], S[name]['x']
        assert not prevented and close(b['u0'], a['u0'], 1e-3) and close(b['span'], a['span'], 1e-3), (name, S[name])


def q_wheel_zooms_and_pans_but_lets_the_page_scroll():
    # Replicata: from a view zoomed in 3 steps, at about 30% of the plot's width (Chrome rounds a synthetic wheel's
    # position to a whole px): ctrl + wheel up 100 px; cmd + wheel down 50 px; ctrl + wheel up 3 lines; a wheel 60 px
    # right and 5 down; a wheel 100 px down and 2 right.
    # Expectata: ctrl and cmd zoom by 2^(delta in px / 100) (a line is 16 px) about the pointer: the u under it stays;
    # the mostly-sideways wheel pans by its 60 px; all four have their default prevented.  The mostly-down wheel changes
    # nothing and is not prevented, so the page scrolls.
    S = valid_run('light')['steps']
    for name, f in (('ctrlWheel', 0.5), ('metaWheel', 2 ** 0.5), ('lineWheel', 2 ** -0.48)):
        a, b, (prevented, x) = S[name]['a'], S[name]['b'], S[name]['x']
        assert prevented and close(b['span'], a['span'] * f, 1e-3) and close(x, 0.3, 0.01), (name, S[name])
        assert close(a['u0'] + x * a['span'], b['u0'] + x * b['span'], 1e-3), (name, S[name])
    a, b, (prevented, _) = S['sideWheel']['a'], S['sideWheel']['b'], S['sideWheel']['x']
    R = valid_run('light')
    W = (R['plot'][1] - R['plot'][0]) / R['dpr']
    assert prevented and close(b['span'], a['span'], 1e-3) and close(b['u0'] - a['u0'], 60 * a['span'] / W, 1e-3), S['sideWheel']
    a, b, (prevented, _) = S['upWheel']['a'], S['upWheel']['b'], S['upWheel']['x']
    assert not prevented and close(b['u0'], a['u0'], 1e-6) and close(b['span'], a['span'], 1e-6), S['upWheel']


def q_drag_and_touch_pan_and_pinch():
    # Replicata: from a view zoomed in 3 steps: a mouse drag 100 px left; a one-finger touch swipe 20% of the plot left;
    # a two-finger pinch from 40% and 60% of the plot's width out to 30% and 70%; then the canvas's touch-action.
    # Expectata: the drag and the swipe pan by their distance (content follows the pointer); the pinch zooms in about
    # the fingers' midpoint by (d0 + 1) / (d + 1), d0 and d the fingers' spread in px before and after, and the u under
    # the midpoint stays; touch-action is pan-y, so vertical swipes still scroll the page.
    R = valid_run('light')
    S, W = R['steps'], (R['plot'][1] - R['plot'][0]) / R['dpr']
    for name in ('drag', 'swipe'):
        a, b, dx = S[name]['a'], S[name]['b'], S[name]['x']
        assert close(b['span'], a['span'], 1e-3) and close(b['u0'] - a['u0'], dx * a['span'] / W, 1e-3), (name, S[name])
    a, b, (d0, d, xm) = S['pinch']['a'], S['pinch']['b'], S['pinch']['x']
    assert close(b['span'], a['span'] * (d0 + 1) / (d + 1), 1e-3), S['pinch']
    assert close(a['u0'] + xm * a['span'] / W, b['u0'] + xm * b['span'] / W, 1e-3), S['pinch']
    assert R['touchAction'] == 'pan-y', R['touchAction']


def q_safari_gestures_zoom_unless_touching():
    # Replicata: from a view zoomed in 3 steps: Safari's gesturestart, gesturechange (scale 2) and gestureend at 25% of
    # the plot's width; then the same while a touch pointer is down.
    # Expectata: the first zooms in by 2 about the pointer, with gesturestart's and gesturechange's defaults prevented;
    # the second changes nothing (the pointer events own a touch pinch), defaults still prevented.
    R = valid_run('light')
    S, W = R['steps'], (R['plot'][1] - R['plot'][0]) / R['dpr']
    a, b, (p1, p2, _, x) = S['gesture']['a'], S['gesture']['b'], S['gesture']['x']
    assert p1 and p2 and close(b['span'], a['span'] / 2, 1e-3), S['gesture']
    assert close(a['u0'] + x * a['span'] / W, b['u0'] + x * b['span'] / W, 1e-3), S['gesture']
    a, b, (p1, p2) = S['gestureWhileTouching']['a'], S['gestureWhileTouching']['b'], S['gestureWhileTouching']['x']
    assert p1 and p2 and close(b['span'], a['span'], 1e-6) and close(b['u0'], a['u0'], 1e-6), S['gestureWhileTouching']


def q_view_stays_within_limits():
    # Replicata: from a view zoomed in 3 steps: 40 presses of +; of -; 300 of ArrowRight; ctrl + wheel down 5000 px;
    # and (separately) ArrowRight, +, then the reset button.
    # Expectata: zooming in stops at 12 columns and out at all 500; panning stops with n = 1000 at the right edge; the
    # reset button shows all 500 columns, n = 2 to 1000.
    S = valid_run('light')['steps']
    assert close(S['zoomInFar']['b']['span'], MIN_SPAN, 0.01), S['zoomInFar']
    for name in ('zoomOutFar', 'wheelOutFar', 'reset'):
        assert close(S[name]['b']['span'], NCOL, 0.05) and close(S[name]['b']['u0'], 0, 0.01), (name, S[name])
    b = S['panFar']['b']
    assert close(b['u0'] + b['span'], NCOL, 0.01), S['panFar']


def q_tap_and_outline():
    # Replicata: in a zoomed view, a touch tap at 37% of the plot's width in row 1 (after hovering elsewhere), then a
    # pointerup with no pointerdown, then a mouse click (down and up, no move) at 63% in row 1 (after hovering
    # elsewhere); and, in a view zoomed in 5 steps, a hover over the middle of the middle column's cell in row 2.
    # Expectata: the tap and the click each read out the cell under them (an even n) and the stray pointerup changes
    # nothing; the hovered cell keeps its color in the middle and is outlined in ink just outside its left and right
    # edges.
    R = valid_run('light')
    n, m = R['tap']['want']
    assert R['tap']['text'].startswith(f'n = {n}, m = {m} · ') and R['tap']['after'] == R['tap']['text'], R['tap']
    n, m = R['click']['want']
    assert R['click']['text'].startswith(f'n = {n}, m = {m} · '), R['click']
    o = R['outline']
    assert R['outlineText'].startswith(f'n = {o["n"]}, m = {o["m"]} · '), R['outlineText']
    assert o['middle'] == o['want'] and o['left'] == o['ink'] and o['right'] == o['ink'], o


def q_phone_has_no_sideways_scroll():
    # Replicata: index.html with the real mstar.js, 390 px wide at 3 device px per CSS px.
    # Expectata: no errors; the page is no wider than the window; the canvas is as wide as main's content.
    R = valid_run('phone')
    assert R['scrollW'] <= R['innerW'] and close(R['canvasCss'][0], R['mainContentW'], 1), R


def q_missing_data_says_so():
    # Replicata: index.html with no mstar.js beside it.
    # Expectata: the canvas stays 0 px tall and the readout is dreeves's error line (ERROR) followed by the error,
    # which names MSTAR; the failed script load and the uncaught error are recorded (the chart fails loudly).
    R = run('missing')
    assert 'harnessError' not in R, R['harnessError']
    assert R['canvasDev'][1] == 0 and R['canvasCss'][1] == 0, R
    assert re.fullmatch(re.escape(ERROR) + r'.*\bMSTAR\b.*', R['readout0']), R['readout0']
    assert any('script failed to load' in e for e in R['errors']) and any('MSTAR' in e for e in R['errors']), R['errors']


def q_malformed_data_fails_loudly():
    # Replicata: made-up data whose column 100 has lo = 5 > hi = 3.
    # Expectata: the canvas stays 0 px tall; the readout is dreeves's error line (ERROR) followed by the error, which
    # quotes column 100 as JSON; the error is uncaught (recorded).
    R = run('violates lo above hi')
    assert 'harnessError' not in R, R['harnessError']
    assert R['canvasDev'][1] == 0 and R['canvasCss'][1] == 0, R
    assert re.fullmatch(re.escape(ERROR) + r'.*\[100,\[5,3,.*', R['readout0']), R['readout0']
    assert any('[100,[5,3,' in e for e in R['errors']), R['errors']


def q_contract_violations_fail_loudly():
    # Replicata: made-up data broken in one way each (VIOLATIONS): lo above hi; an unknown kind of reason; a reason with too few
    # arguments; a join of lengths that do not add up to n; a join or product claiming more than its parts give; "two"
    # with the wrong hi; "norm" for a prime dividing n, and for a composite; "table2" at an n not in Table 2; "page" for
    # a provenance the page does not use; an example with an empty label; "none" or "odd" at an even n; an example at
    # an odd n; a column of five entries; hi at mtop; mtop above max hi + 1; nmax not 1000.
    # Expectata: in each case the canvas stays 0 px tall and the readout is dreeves's error line (ERROR) followed by
    # the error, which quotes the offending column as JSON (or mtop, or nmax and mtop), and the error is uncaught.
    for v, (_, quoted) in VIOLATIONS.items():
        R = run(f'violates {v}')
        assert 'harnessError' not in R and R['canvasDev'][1] == 0 and R['canvasCss'][1] == 0, (v, R)
        assert R['readout0'] == f'{ERROR}Error: {quoted}', (v, R['readout0'])
        assert R['errors'] == [f'error: Uncaught Error: {quoted}'], (v, R['errors'])


def q_made_up_data_draws():
    # Replicata: made-up data that uses every kind of reason (kinds_data).
    # Expectata: no errors; the chart is drawn with one row per m up to mtop.
    R = valid_run('kinds')
    assert R['canvasDev'][1] > 0 and len(R['rows']) == 8, R['rows']


# ---------------------------------------------------------------------------------------------------------------------
# The section "Search progress" (dreeves, 2026-10-17: "make it a collapsible section of index.html -- no separate
# progress page -- and have it do something less crude than reloading the page every minute"), which draws
# progress.py's data file, progress.js (its contract: progress.js_text).

STATUSES = ('settled', 'open', 'split', 'pending', 'running')
# made-up data: one running run, three groups, every status, three recorded ETAs an hour apart
PROGRESS_DATA = {'made': 1792200000, 'runs': [{
    'program': 'overnight_v5.py', 'n': 64, 'order': 7, 'state': 'running', 'outcome': None, 'so_far': 7200.0, 'to_go': {'median': 3600.0, 'lo': 1800.0, 'hi': 10800.0},
    'etas': [[1792192800, 0.0, 10800.0, 7200.0, 14400.0], [1792196400, 3600.0, 7200.0, 3600.0, 10800.0],
             [1792200000, 7200.0, 3600.0, 1800.0, 10800.0]],
    'statuses': list(STATUSES), 'depth': 1, 'keys': ['3:[0,0,3]', '3:[1,1,1]', '3:[2,1,0]'],
    'groups': ['0123', '4', '00110'], 'counts': {'settled': 4, 'open': 3, 'split': 1, 'pending': 1, 'running': 1}}]}
# progress.html's ETA chart case (quals_progress.eta_chart_case): 13.2 h of running, ended, ETAs of [2, 1, 4] h at
# its start and [1, 0.5, 3] h at its end
PROGRESS_ETA_DATA = {'made': 1792200000, 'runs': [dict(PROGRESS_DATA['runs'][0], state='ended', so_far=47520.0, to_go=None,
                                                       etas=[[1792100000, 0.0, 7200.0, 3600.0, 14400.0],
                                                             [1792192160, 47520.0, 3600.0, 1800.0, 10800.0]])]}
# two runs, the second the first as boxsplit.py's pass with no ETA recorded yet (dreeves, 2026-10-17: a second block for
# 240@11's boxsplit pass)
PROGRESS_TWO = {'made': 1792200000, 'runs': [PROGRESS_DATA['runs'][0], dict(PROGRESS_DATA['runs'][0], program='boxsplit.py', to_go=None, etas=[])]}
# two long runs (dreeves, 2026-10-23: "this would be more helpful as days or years when over like 48 or maybe 72h, and
# the parenthetical needs disambiguation when >1week"): 480:14's of that day, 14.2 h so far and 3596.5–56401.4 h to go
# (median 7500 h), its last two ETAs an hour apart; and a run 100 h along with 0.5–3.0 h to go
HOURS = 3600.0
PROGRESS_LONG = {'made': 1792200000, 'runs': [
    dict(PROGRESS_DATA['runs'][0], so_far=14.2 * HOURS, to_go={'median': 7500 * HOURS, 'lo': 3596.5 * HOURS, 'hi': 56401.4 * HOURS},
         etas=[[1792196400, 13.2 * HOURS, 7400 * HOURS, 3550 * HOURS, 55000 * HOURS],
               [1792200000, 14.2 * HOURS, 7500 * HOURS, 3596.5 * HOURS, 56401.4 * HOURS]]),
    dict(PROGRESS_DATA['runs'][0], so_far=100 * HOURS, to_go={'median': 1 * HOURS, 'lo': 0.5 * HOURS, 'hi': 3 * HOURS},
         etas=[[1792196400, 99 * HOURS, 2 * HOURS, 1 * HOURS, 4 * HOURS], [1792200000, 100 * HOURS, 1 * HOURS, 0.5 * HOURS, 3 * HOURS]])]}
# a run whose band stays within the y axis's cap (2026-10-23): 10 h so far and 1.5–2.5 h to go (median 2 h), so the
# projected finish is 12 h and the cap 13.2 h, above elapsed + ETA's band top, 12.5 h
PROGRESS_NARROW = {'made': 1792200000, 'runs': [dict(PROGRESS_DATA['runs'][0], so_far=10 * HOURS,
    to_go={'median': 2 * HOURS, 'lo': 1.5 * HOURS, 'hi': 2.5 * HOURS},
    etas=[[1792196400, 9 * HOURS, 2 * HOURS, 1.5 * HOURS, 2.5 * HOURS], [1792200000, 10 * HOURS, 2 * HOURS, 1.5 * HOURS, 2.5 * HOURS]])]}
PROGRESS_EARLY = '<script>window.PROGRESS_POLL_MS = 1000;</script>\n'      # a 1 s poll, for the quals
# a browser that last left the section open (dreeves, 2026-10-17: "i keep having to re-expand the search progress
# section", Live Server reloading the page as files change), set before the page's scripts run
PROGRESS_REMEMBERED = '<script>localStorage.setItem("progress-open", "1");</script>\n'
NNBSP = '\u202f'                               # the narrow no-break space between a number and its unit h (2026-10-17)
EMSP = '\u2003'                                # the em space after a snapshot line's time (dreeves, 2026-10-17: "some whitespace")


def stamp(t):
    """A time as the section gives a snapshot's: local, YYYY-MM-DD HH:MM:SS."""
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))


def ampm(t):
    """A time as the section's status line gives it: local 12-hour hours without a leading zero, minutes, am or pm."""
    lt = time.localtime(t)
    return f'{lt.tm_hour % 12 or 12}:{lt.tm_min:02d}{"am" if lt.tm_hour < 12 else "pm"}'


WEEK = 7 * 86400                               # seconds; a finish time a week or more on is a date (dreeves, 2026-10-23)


def finish(t, t1, t2):
    """The status line's finish times, of a snapshot at t: the first's weekday, the first, a spaced en dash, the second's
    weekday only when its date differs, the second; but an end a week or more after t as its local date, YYYY-MM-DD
    (dreeves, 2026-10-23: "the parenthetical needs disambiguation when >1week")."""
    day = lambda s: time.strftime('%a', time.localtime(s))
    date = lambda s: time.strftime('%Y-%m-%d', time.localtime(s))
    first = f'{day(t1)} {ampm(t1)}' if t1 - t < WEEK else date(t1)
    second = f'{"" if date(t1) == date(t2) else day(t2) + " "}{ampm(t2)}' if t2 - t < WEEK else date(t2)
    return f'{first} – {second}'
# The harness: notes what has loaded, opens the section, waits 3.5 s, reads each dot's middle pixel, the key's counts,
# the state line and the times, the time bar's parts, the subtrees' blocks and the ETA chart (its markup at rest), hovers over the third
# group's first dot and over the ETA chart's second record, gives progressData a changed snapshot (one dot running ->
# open), then closes the section and waits 3.5 s more; its report goes into <pre id="harness-out">.
PROGRESS_HARNESS = """<script>
(async () => {
  const out = {};
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const section = document.querySelector('section.progress'), details = section.querySelector('details');
  const view = () => window.progressView;
  const pixel = (gi, j) => {
    const [x, y, size] = view().layouts[0].place(gi, j);
    const p = section.querySelector('canvas').getContext('2d').getImageData(x + (size >> 1), y + (size >> 1), 1, 1).data;
    return [p[0], p[1], p[2]];
  };
  const counts = () => Object.fromEntries([...section.querySelectorAll('[data-count]')].map(e => [e.dataset.count, e.textContent]));
  try {
    window.harnessMarker = 'kept';
    out.before = {open: details.open, loads: view().loads, renders: view().renders,
                  scripts: [...document.scripts].filter(s => /progress[.]js/.test(s.getAttribute('src') || '')).length};
    out.stored = {before: localStorage.getItem('progress-open')};
    details.open = true;
    await sleep(3500);
    out.opened = {loads: view().loads, renders: view().renders};
    out.stored.opened = localStorage.getItem('progress-open');
    const run = view().data.runs[0];
    out.dots = run.groups.flatMap((g, gi) => [...g].map((c, j) => [+c, pixel(gi, j)]));
    const css = getComputedStyle(section);
    out.colors = run.statuses.map(s => css.getPropertyValue('--progress-' + s).trim());
    out.counts = counts();
    const squeeze = t => t.replace(/[ \\t\\n\\r]+/g, ' ').trim();       // ASCII whitespace only: U+202F, before a unit, is text
    out.state = [...section.querySelectorAll('[data-state]')].filter(e => !e.hidden).map(e => squeeze(e.textContent));
    out.made = section.querySelector('[data-made]').textContent;
    out.heads = [...section.querySelectorAll('.progress-runs h3')].map(h => h.textContent.replace(/\\s+/g, ' ').trim());
    out.etaDisplays = [...section.querySelectorAll('.progress-runs .progress-eta')].map(e => getComputedStyle(e).display);
    out.age = section.querySelector('[data-age]').textContent;
    const canvas = section.querySelector('canvas'), L = view().layouts[0], [hx, hy] = L.place(2, 0);
    const box = canvas.getBoundingClientRect(), dpr = canvas.width / box.width;
    canvas.dispatchEvent(new MouseEvent('mousemove', {clientX: box.left + (hx + L.size / 2) / dpr, clientY: box.top + (hy + L.size / 2) / dpr, bubbles: true}));
    out.readout = section.querySelector('[data-readout]').textContent.replace(/\\s+/g, ' ').trim();
    out.bar = Object.fromEntries([...section.querySelectorAll('[data-bar]')].map(e => [e.dataset.bar, e.style.width || e.style.left]));
    out.blocks = {rects: L.rects, cols: L.cols, rows: L.rows};
    const fig = section.querySelector('.progress-eta'), svg = fig.querySelector('svg');
    const text = sel => squeeze(fig.querySelector(sel).textContent);
    out.eta = {hidden: fig.hidden, widths: [svg.getBoundingClientRect().width, section.querySelector('canvas').getBoundingClientRect().width],
               togo: fig.querySelector('[data-togo]').getAttribute('points').trim().split(/\\s+/).length,
               labels: svg.querySelectorAll('text.label').length};
    out.etaSvg = svg.outerHTML;
    out.etaTextStrokes = [...svg.querySelectorAll('text')].map(t => [t.getAttribute('class'), t.textContent, getComputedStyle(t).stroke, getComputedStyle(t).paintOrder]);
    const status = section.querySelector('.progress-run [data-state]').parentElement, shown = [...status.children].find(e => !e.hidden);
    out.status = {afterChart: !fig.contains(status) && !!(fig.compareDocumentPosition(status) & Node.DOCUMENT_POSITION_FOLLOWING),
                  colors: [...shown.querySelectorAll('.spent, .togo, .total')].map(e => [e.className, getComputedStyle(e).color]),
                  ink: getComputedStyle(shown).color,
                  when: getComputedStyle(section.querySelector('.progress-run [data-state="running"] [data-when]')).color,
                  legends: section.querySelectorAll('.progress-eta-keys').length};
    const tipEl = fig.querySelector('[data-tip]');
    out.tipRest = {visibility: getComputedStyle(tipEl).visibility, height: tipEl.getBoundingClientRect().height};
    const top0 = status.getBoundingClientRect().top;
    const sb = svg.getBoundingClientRect();
    svg.dispatchEvent(new MouseEvent('mousemove', {clientX: sb.left + L.etaXs[1] * sb.width / 640, clientY: sb.top + sb.height / 2, bubbles: true}));
    out.eta.tip = getComputedStyle(tipEl).visibility === 'visible' ? text('[data-tip]') : null;
    out.jump = status.getBoundingClientRect().top - top0;
    svg.dispatchEvent(new MouseEvent('mousemove', {clientX: sb.left + L.etaXs[L.etaXs.length - 1] * sb.width / 640, clientY: sb.top + sb.height / 2, bubbles: true}));
    out.eta.tipLast = text('[data-tip]');
    out.eta.sameMarkup = tipEl.innerHTML === status.querySelector('[data-state="running"]').innerHTML;
    out.eta.projectedAtRecord = tipEl.classList.contains('projected');
    const xAt = h => L.etaXs[0] + h * (L.etaXs[1] - L.etaXs[0]);      // viewBox x at h hours: PROGRESS_DATA's records sit at 0, 1, 2 h
    svg.dispatchEvent(new MouseEvent('mousemove', {clientX: sb.left + xAt(2.5) * sb.width / 640, clientY: sb.top + sb.height / 2, bubbles: true}));
    out.eta.tipAhead = text('[data-tip]');
    out.eta.ahead = {projected: tipEl.classList.contains('projected'), style: getComputedStyle(tipEl).fontStyle,
                     cross: Number(fig.querySelector('[data-cross]').getAttribute('x1')), want: xAt(2.5)};
    out.jumpAhead = status.getBoundingClientRect().top - top0;
    const d2 = JSON.parse(JSON.stringify(view().data));
    d2.made += 60; d2.runs[0].groups[1] = '1'; d2.runs[0].counts.running -= 1; d2.runs[0].counts.open += 1;
    window.progressData(d2);
    out.changed = {renders: view().renders, pixel: pixel(1, 0), counts: counts(), marker: window.harnessMarker};
    details.open = false;
    await sleep(100);
    const atClose = view().loads;
    await sleep(3500);
    out.closed = {atClose, loads: view().loads};
    out.stored.closed = localStorage.getItem('progress-open');
  } catch (e) { out.harnessError = String(e && e.stack || e); }
  const pre = document.createElement('pre');
  pre.id = 'harness-out';
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
})();
</script>
"""
PROGRESS_RUNS = {}                             # progress_run's reports, by case, made once per process


def progress_run(case='main'):
    """The harness's report on index.html with the case's data (main: PROGRESS_DATA; eta: PROGRESS_ETA_DATA; two:
    PROGRESS_TWO; long: PROGRESS_LONG; narrow: PROGRESS_NARROW; remembered: PROGRESS_DATA, with PROGRESS_REMEMBERED's stored state) as progress.js
    beside it, made on first use."""
    if case not in PROGRESS_RUNS:
        data = {'main': PROGRESS_DATA, 'eta': PROGRESS_ETA_DATA, 'two': PROGRESS_TWO, 'long': PROGRESS_LONG,
                'narrow': PROGRESS_NARROW, 'remembered': PROGRESS_DATA}[case]
        early = PROGRESS_EARLY + (PROGRESS_REMEMBERED if case == 'remembered' else '')
        d = tempfile.mkdtemp(prefix='index-quals-')
        text = page()
        assert text.count('<head>\n') == 1 and text.count('</body>') == 1
        text = text.replace('<head>\n', '<head>\n' + early).replace('</body>', PROGRESS_HARNESS + '</body>')
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(text)
        open(os.path.join(d, 'progress.js'), 'w', encoding='utf-8').write('progressData(' + json.dumps(data) + ');\n')
        shutil.copy(DATA, os.path.join(d, 'mstar.js'))
        shutil.copy(POW2, os.path.join(d, 'pow2.js'))
        dom = chrome(d, ['--window-size=1000,1100', '--force-device-scale-factor=2', '--virtual-time-budget=20000',
                         '--dump-dom', 'file://' + os.path.join(d, 'index.html')])
        m = re.search(r'<pre id="harness-out">(.*?)</pre>', dom, re.S)
        assert m, dom[-3000:]
        PROGRESS_RUNS[case] = json.loads(html.unescape(m.group(1)))
        shutil.rmtree(d)
    R = PROGRESS_RUNS[case]
    assert 'harnessError' not in R, R['harnessError']
    return R


def rgb(hexcolor): return [int(hexcolor[i:i + 2], 16) for i in (1, 3, 5)]


def q_search_remarks_name_their_certificates():
    # Replicata: index.html's remarks for 240 and 304, whose orders 11 and 9 computer searches ruled out.
    # Expectata (dreeves, 2026-10-20: "sure", after Stan Wagon read "closes every case with a certificate" as a residue
    # proof): each remark says, in its Claude line and in the TODO recap above it, that the search closes every case
    # with linear-programming certificates checked in exact integer arithmetic; the page says "a certificate checked"
    # nowhere.
    text = page()
    for n in (240, 304):
        li = re.search(r'<li class="c">\s*<span class="mk" aria-hidden="true">◆</span>\s*<p class="entry"><i>n</i> = '
                       + str(n) + r': .*?</li>', text, re.S).group(0)
        assert li.count('closes every case with linear-programming certificates checked in exact integer arithmetic') == 2, (n, li[:600])
    assert 'a certificate checked' not in text


def q_table2_credits_stong_for_2_51():
    # Replicata: index.html's figure of Table 2: its three blocks, then what comes before the new results' block.
    # Expectata (dreeves, 2026-10-18: "can you indicate somehow that the 2^51 result in the table is due to Richard
    # Stong?"): Table 2's last block ends with n = 2^51 and its value "≥ 52", the cells untouched (mstar.py reads them);
    # right after the blocks' scroll frame, before the new results, his note (STONG_NOTE, his rewording of Claude's
    # line, commit 23ba3db), and then nothing or Claude's note on 288 (2026-10-25: a TODO comment and one line).
    fig = re.search(r'<figure>.*?</figure>', page(), re.S).group(0)
    blocks = re.findall(r'<table class="block">(.*?)</table>', fig, re.S)[:3]
    assert blocks[2].rstrip().endswith('<td>2<sup>51</sup></td></tr>\n        <tr class="vals"><th scope="row"><i>m</i><sup>*</sup>(<i>n</i>)</th><td lang="en">10 or 11</td><td>7</td><td>8</td><td>7</td><td>8</td><td>7</td><td lang="en">9 or 10</td><td>7</td><td lang="en">8 or 9</td><td>≥ 52</td></tr>'), blocks[2][-300:]
    # (and since 2026-10-25 Claude's note on 288 between his and the new results, q_288_bound_is_proved_here's)
    assert re.search(r'</table>\n    </div>\n    ' + re.escape(STONG_NOTE) + r'\n(    <!-- TODO: [^\n]*-->\n    <p>Claude: "[^\n]*"</p>\n)?\n    <div class="new-block">', fig), \
        fig[fig.index('2<sup>51</sup>'):][:800]


def q_theorem_states_pow2_s_thresholds():
    # Replicata: the theorem atop the powers-of-2 section (THEOREM) and its alternative form (THEOREM_ALT), their
    # numbers read off; and pow2.js (pow2_data).
    # Expectata: the page holds THEOREM once, right after the section's heading, and THEOREM_ALT once, right after it;
    # THEOREM's bounds are m*(2^k) ≥ k + e for e = 1, …, E in turn, E the most any power reaches in pow2.js (8 until
    # 2026-10-25, 9 since: dreeves, 2026-10-25: "yes please"), each k the least power whose known lower bound
    # reaches k + e in pow2.js, so that a new result that moves a threshold fails here until the theorem changes with
    # it; then m*(2^9) = 9, pow2.js's bounds at 2^9 both 9; and THEOREM_ALT's count is E and its values are those
    # same ks.
    text = page()
    heading = next(line for line in DREEVES_LINES if 'pow2-title' in line)
    assert text.count(THEOREM) == 1 and re.search(re.escape(heading) + r'\n\s*' + re.escape(THEOREM), text), 'no theorem below the heading'
    assert text.count(THEOREM_ALT) == 1 and re.search(re.escape(THEOREM) + r'\n\s*' + re.escape(THEOREM_ALT), text), 'no alternative below it'
    bounds = [(int(k), op, int(v)) for k, op, v in re.findall(r'\(2<sup>(\d+)</sup>\) (≥|=) (\d+)', THEOREM)]
    cols = pow2_data()['cols']
    E = max(c[0] - k for k, c in enumerate(cols, 1))
    firsts = [next(k for k in range(1, len(cols) + 1) if cols[k - 1][0] - k >= e) for e in range(1, E + 1)]
    assert bounds[:E] == [(k, '≥', k + e) for e, k in enumerate(firsts, 1)], (bounds, firsts)
    assert bounds[E:] == [(9, '=', 9)] and cols[8][:2] == [9, 9], (bounds[E:], cols[8][:2])
    assert f'<i>i</i> = 1, 2, …, {E}</span>' in THEOREM_ALT, THEOREM_ALT
    values = [int(v) for v in re.search(r' are ([\d, ]+)\.</p>$', THEOREM_ALT).group(1).split(', ')]
    assert values == firsts, (values, firsts)


def q_smallest_section_is_a_claude_quote():
    # Replicata: index.html's section "The smallest length known for each order".
    # Expectata: a <section class="smallest" aria-labelledby="smallest-title"> right after the remarks' section and
    # right before the counts' section (only blank lines and comments between): a TODO comment, then one block quote
    # attributed to Claude (claude_quotes' form) holding the heading, a link to OEIS A323395, and a table of the
    # columns order m, smallest known n, proven smallest and smallest n not ruled out, its body empty in the HTML: the
    # script fills it from mstar.js; and not of class block, so that the page keeps the nine tables of that class that
    # mstar.py reads as Table 2's and the new results' (its count asserted there, which a tenth broke on 2026-10-17).
    # Astra's separately attributed minimality note follows the intact Claude quote (2026-10-20).
    text = page()
    filler = r'(?:\s|<!--.*?-->)*'
    m = re.search(r'<section class="remarks">.*?</section>\n' + filler +
                  r'(<section class="smallest" aria-labelledby="smallest-title">\n.*?\n</section>)\n' + filler +
                  r'<section class="counts">', text, re.S)
    assert m, 'no section "smallest" between the remarks and the counts'
    lines = m.group(1).split('\n')
    quoted, todos = claude_quotes(lines)
    assert todos == {1} and quoted == set(range(2, len(lines) - 3)), (todos, len(lines))
    assert tuple(lines[-3:-1]) == ASTRA_SMALLEST_NOTE, lines[-3:-1]
    body = m.group(1)
    assert body.count('<blockquote class="claude">') == 1 and '<h2 id="smallest-title">' in body, body[:300]
    assert 'href="https://oeis.org/A323395"' in body, body
    heads = [re.sub(r'<[^>]+>', '', h) for h in re.findall(r'<th>(.*?)</th>', body)]
    assert heads == ['order m', 'smallest known n', 'proven smallest', 'smallest n not ruled out'], heads
    assert '<table>' in body and '<tbody data-smallest></tbody>' in body, body
    assert text.count('<table class="block">') == 9, text.count('<table class="block">')


def q_smallest_table_matches_mstar():
    # Replicata: index.html in headless Chrome beside mstar.js and pow2.js, its DOM dumped once its scripts ran; and
    # smallest_rows of MSTAR (mstar_data), computed here.
    # Expectata: the table's body holds exactly smallest_rows' rows, in order; the first eleven orders' smallest
    # lengths are SMALLEST_PROVEN, each marked proven (432 added on 2026-10-20 after proof384.py).
    d = tempfile.mkdtemp(prefix='index-quals-')
    for src, name in ((INDEX, 'index.html'), (DATA, 'mstar.js'), (POW2, 'pow2.js')): shutil.copy(src, os.path.join(d, name))
    dom = chrome(d, ['--virtual-time-budget=5000', '--dump-dom', 'file://' + os.path.join(d, 'index.html')])
    shutil.rmtree(d)
    body = re.search(r'<tbody data-smallest="">(.*?)</tbody>', dom, re.S)
    assert body, dom[-2000:]
    got = [[html.unescape(re.sub(r'<[^>]+>', '', c)) for c in re.findall(r'<td>(.*?)</td>', tr, re.S)]
           for tr in re.findall(r'<tr>(.*?)</tr>', body.group(1), re.S)]
    want = smallest_rows(mstar_data()['cols'])
    assert got == want, (got, want)
    proven = got[:len(SMALLEST_PROVEN)]
    assert [r[1] for r in proven] == [str(n) for n in SMALLEST_PROVEN] and all(r[2] == '✓' for r in proven), proven


def q_smallest_script_passes_node_check():
    # Replicata: the inline script that fills the table of smallest lengths, saved as a .js file, through node --check.
    # Expectata: exit 0: it parses as a classic script.
    js = next(js for js in re.findall(r'<script>\n(.*?)</script>', page(), re.S) if '[data-smallest]' in js)
    d = tempfile.mkdtemp(prefix='index-quals-')
    path = os.path.join(d, 'smallest.js')
    open(path, 'w', encoding='utf-8').write(js)
    p = subprocess.run(['node', '--check', path], capture_output=True, text=True, timeout=60)
    shutil.rmtree(d)
    assert p.returncode == 0, p.stderr


def q_progress_section_is_closed_and_unattributed():
    # Replicata: index.html's section "Search progress".
    # Expectata: a <section class="progress" aria-labelledby="progress-title"> after the sets' section and before the
    # footer: first its TODO comment (progress_lines' form), then a <details> without open, so it starts closed, whose
    # <summary> is the heading "Search progress" (dreeves's title for progress.html, 2026-10-09), with a key of the five
    # statuses; and in its run template one more <details>, also without open, each run's fold (dreeves, 2026-10-23;
    # since 2026-10-25 each stays as this browser left it); its copy unattributed, no block quote and no
    # "Claude:" (dreeves, 2026-10-17: he took the section out
    # of the block quote it was made in, as progress.html's copy had none); no <script> on the page names
    # progress.js, which the section's script loads only once it is opened.
    text = page()
    sec = re.search(r'<section class="progress" aria-labelledby="progress-title">\n(.*?)\n</section>\n', text, re.S)
    assert sec and text.index('<section class="sets">') < sec.start() < text.index('<footer>'), sec
    body = sec.group(1)
    lines = text.split('\n')
    section, todo = progress_lines(lines)
    assert lines[todo + 1].strip() == '<details>' and '<details open' not in body and body.count('</details>') == 2
    run = re.search(r'<template class="progress-run">(.*?)</template>', body, re.S).group(1)
    assert run.count('<details>') == 1 and run.count('</details>') == 1, run[:300]
    assert '<blockquote' not in body and 'Claude:' not in body and 'attrib' not in body, body[:200]
    assert '<summary><h2 id="progress-title">Search progress</h2></summary>' in body
    assert [s for s in re.findall(r'data-count="(\w+)"', body)] == list(STATUSES)
    assert not re.search(r'<script[^>]*progress', text)


def q_progress_classes_meet_only_its_own_css():
    # Replicata: the classes the section "Search progress" uses, and the page's CSS rules whose selectors start neither
    # with its own classes (.progress, .progress-*) nor with another section's class or a chart's id (they match only
    # inside that section).
    # Expectata: no such rule names one of the section's classes but nw (the page's no-wrap span, used on purpose).
    # (2026-10-17: the ETA chart's legend took the page's legend rule for .key, which drew its line swatches as
    # boxes.)
    text = page()
    sec = re.search(r'<section class="progress".*?</section>', text, re.S).group(0)
    classes = {c for attr in re.findall(r'\bclass="([^"]*)"', sec) for c in attr.split()} - {'nw'}
    others = set(re.findall(r'<section class="([\w-]+)"', text)) - {'progress'}
    style = re.sub(r'/\*.*?\*/', '', text[text.index('<style>'):text.index('</style>')], flags=re.S)
    selectors = [s.strip() for sel in re.findall(r'([^{}]+)\{', style) for s in sel.split(',')]
    scoped = r'(\.progress(-[\w-]+)?|\.(' + '|'.join(map(re.escape, others)) + r')|#(pow2|mstar)[\w-]*)(?![\w-])'
    foreign = [s for s in selectors if not re.match(scoped, s)]
    bad = [(s, c) for s in foreign for c in classes if re.search(rf'\.{re.escape(c)}(?![\w-])', s)]
    assert classes and not bad, bad


def q_progress_css_names_only_what_the_section_has():
    # Replicata: the page's CSS rules whose selectors start with the section's classes (.progress, .progress-*); the
    # section's markup with its script (the page's fifth, which makes the chart's and the tip's marks).
    # Expectata: every class and element such a selector names occurs in them, so no rule of the section's matches
    # nothing.  (2026-10-17: dreeves took the section out of its block quote, which left .progress blockquote and
    # .progress .attrib matching nothing.)
    text = page()
    sec = re.search(r'<section class="progress".*?</section>', text, re.S).group(0)
    js = re.findall(r'<script>\n(.*?)</script>', text, re.S)[-1]
    style = re.sub(r'/\*.*?\*/', '', text[text.index('<style>'):text.index('</style>')], flags=re.S)
    selectors = [s.strip() for sel in re.findall(r'([^{}]+)\{', style) for s in sel.split(',')]
    ours = [re.sub(r'\[[^\]]*\]|::?[\w-]+(\([^)]*\))?', '', s) for s in selectors
            if re.match(r'\.progress(-[\w-]+)?(?![\w-])', s)]
    named = {(kind, name) for s in ours for kind, name in re.findall(r'(\.|(?:^|(?<=[\s>+~])))([a-z][\w-]*)', s)}
    def present(kind, name):
        if kind == '.':
            return re.search(rf'(?<![\w-]){re.escape(name)}(?![\w-])', sec + js)
        return re.search(rf'<{name}\b', sec) or re.search(rf"""['"]{name}['"]""", js)
    missing = sorted((kind or '<') + name for kind, name in named if not present(kind, name))
    assert len(ours) > 40 and ('.', 'progress') in named and ('', 'canvas') in named and not missing, missing


def q_progress_script_passes_node_check():
    # Replicata: the section's inline script (the page's fifth), saved as a .js file, through node --check.
    # Expectata: exit 0: it parses as a classic script.
    js = re.findall(r'<script>\n(.*?)</script>', page(), re.S)[-1]
    d = tempfile.mkdtemp(prefix='index-quals-')
    path = os.path.join(d, 'progress-section.js')
    open(path, 'w', encoding='utf-8').write(js)
    p = subprocess.run(['node', '--check', path], capture_output=True, text=True, timeout=60)
    shutil.rmtree(d)
    assert 'progressData' in js and p.returncode == 0, p.stderr


def q_progress_loads_only_while_open():
    # Replicata: progress_run: index.html in headless Chrome with PROGRESS_DATA as progress.js, the poll 1 s.
    # Expectata: closed at load, with nothing loaded or drawn and no script naming progress.js; opened, it loads
    # progress.js, again each second (at least 3 loads in 3.5 s), and draws once, since the snapshot did not change;
    # closed again, it loads nothing more.
    R = progress_run()
    assert R['before'] == {'open': False, 'loads': 0, 'renders': 0, 'scripts': 0}, R['before']
    assert R['opened']['loads'] >= 3 and R['opened']['renders'] == 1, R['opened']
    assert R['closed']['loads'] == R['closed']['atClose'], R['closed']


def q_progress_eta_text_is_not_outlined():
    # Replicata: progress_run's ETA chart (PROGRESS_DATA's run), the computed stroke of each of its text elements.
    # Expectata: none for the tick labels; for the three labels at the record's end (ETA, total, elapsed), which share
    # their lines' classes (togo, total, spent), only the page's paper color painted under the letters (paint-order
    # stroke first), a halo that hides the lines behind a label (the red dotted line runs from the red marker through
    # its label) and draws no outline.  The lines' rules outranked the text rule until 2026-10-17 and outlined the
    # labels in their lines' colors (dreeves: "the messed up font/bolding").  Since 2026-10-17 (dreeves: "comment it out
    # for now") the labels are commented out, so there are only ticks; the labels' checks stay for their return.
    R = progress_run()
    strokes = R['etaTextStrokes']
    labels = [s for s in strokes if s[0].split()[0] == 'label']
    ticks = [s for s in strokes if s[0] in ('ytick', 'xtick')]
    assert len(labels) == 0 and len(ticks) == len(strokes), strokes
    # With the labels (until 2026-10-17; back with them):
    # assert len(labels) == 3 and len(labels) + len(ticks) == len(strokes), strokes
    assert all(stroke == 'rgb(255, 255, 255)' and order.startswith('stroke') for _, _, stroke, order in labels), labels
    assert all(stroke == 'none' for _, _, stroke, _ in ticks), ticks


def q_progress_remembers_it_was_left_open():
    # Replicata: progress_run with no stored state (main), and with this browser's stored state saying it last left the
    # section open (remembered, PROGRESS_REMEMBERED); in each, the stored state as the harness begins, after it opens
    # the section and after it closes it.
    # Expectata (dreeves, 2026-10-17: reloads kept closing the section; "2": remember it in the browser): main starts
    # closed with nothing stored, stores "1" once opened and nothing once closed; remembered starts open, its data
    # loading already (a progress.js script and at least one load before the harness touched it), then the same.
    main, kept = progress_run(), progress_run('remembered')
    assert main['before']['open'] is False and main['stored'] == {'before': None, 'opened': '1', 'closed': None}, main['stored']
    assert kept['before']['open'] is True and kept['before']['loads'] >= 1 and kept['before']['scripts'] >= 1, kept['before']
    assert kept['stored'] == {'before': '1', 'opened': '1', 'closed': None}, kept['stored']


def q_progress_draws_each_dot_in_its_status_color():
    # Replicata: progress_run, the middle pixel of every dot after opening, and the CSS custom properties
    # --progress-<status> (STATUSES).
    # Expectata: one dot per status digit of the data, in its order, each pixel exactly its status's color; the key's
    # counts are the data's.
    R = progress_run()
    want = [(int(c), STATUSES[int(c)]) for g in PROGRESS_DATA['runs'][0]['groups'] for c in g]
    assert [s for s, _ in R['dots']] == [s for s, _ in want], R['dots']
    assert all(len(c) == 7 and c.startswith('#') for c in R['colors']), R['colors']
    assert all(px == rgb(R['colors'][s]) for s, px in R['dots']), (R['dots'], R['colors'])
    assert R['counts'] == {s: str(PROGRESS_DATA['runs'][0]['counts'][s]) for s in STATUSES}, R['counts']


def q_progress_states_times_and_hours():
    # Replicata: progress_run's state line, snapshot time and age after opening.
    # Expectata: only the running state's line shows, in dreeves's form of 2026-10-17 ("Running: 11.4 h so far +
    # 34.2–50.6 h to go = 45–62 h (Mon 6:27am – 10:58pm)", then for "Running:" his '"@2026-10-17 20:40:59" (in black)
    # and then some whitespace, no colon'): an @ and the snapshot's time (the data's made: stamp), in the page's ink, an
    # em space, then 2.0 h so far + a 0.5–3.0 h band to go (PROGRESS_DATA's so_far and to_go) = 2.5–5.0 h in all, each
    # number and its h apart by a narrow no-break space (his "thin space"), then in parentheses the local times that
    # band ends between (finish: the weekday once unless the dates differ, 12-hour times with am or pm), no period; the
    # snapshot time above the runs is the data's made in
    # local time (YYYY-MM-DD HH:MM:SS), and its age a duration in digits.  And since dreeves's request of 2026-10-17, the
    # status line sits below the ETA chart, where its legend was, outside the chart's box (so that it shows when the
    # chart has no record), its parts in the chart's colors: the hours so far blue (spent), the hours to go red (togo),
    # the hours in all and the clock times purple (total: #7b1fa2 since dreeves's "blue+red=purple", 2026-10-17; the
    # page's ink before).
    R = progress_run()
    made, go, h = PROGRESS_DATA['made'], PROGRESS_DATA['runs'][0]['to_go'], NNBSP + 'h'
    want = f'@{stamp(made)}{EMSP}2.0{h} so far + 0.5–3.0{h} to go = 2.5–5.0{h} ({finish(made, made + go["lo"], made + go["hi"])})'
    assert R['state'] == [want], (R['state'], want)
    at = lambda d, hh, mm: time.mktime((2026, 10, d, hh, mm, 0, 0, 0, -1))        # local times; 2026-10-19 is a Monday
    assert finish(at(19, 6, 0), at(19, 6, 27), at(19, 17, 38)) == 'Mon 6:27am – 5:38pm', finish(at(19, 6, 0), at(19, 6, 27), at(19, 17, 38))
    assert finish(at(19, 6, 0), at(19, 6, 27), at(20, 0, 18)) == 'Mon 6:27am – Tue 12:18am', finish(at(19, 6, 0), at(19, 6, 27), at(20, 0, 18))
    # a week on, a weekday is ambiguous: a date (dreeves, 2026-10-23; 'Mon 12:05pm – Mon 12:05pm' until then)
    assert finish(at(19, 12, 5), at(19, 12, 5), at(26, 12, 5)) == 'Mon 12:05pm – 2026-10-26'
    want = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(PROGRESS_DATA['made']))
    assert R['made'] == want, (R['made'], want)
    assert re.fullmatch(r'(\d+ d )?\d+:\d\d:\d\d', R['age']), R['age']
    assert R['status']['afterChart'] is True, R['status']
    assert R['status']['colors'] == [['spent', 'rgb(42, 120, 214)'], ['togo', 'rgb(227, 73, 72)'], ['total', 'rgb(123, 31, 162)']], R['status']
    assert R['status']['ink'] == R['status']['when'] == 'rgb(27, 29, 34)', R['status']


def q_progress_writes_days_and_years_past_72_h_and_dates_past_a_week():
    # Replicata: progress_run('long'): PROGRESS_LONG's two running runs.
    # Expectata (dreeves, 2026-10-23: "this would be more helpful as days or years when over like 48 or maybe 72h, and
    # the parenthetical needs disambiguation when >1week"): each duration in hours below 72 h, in days below a year of
    # 365.25 d, in years from there, as before a tenth so far and to go and in all a tenth below 10 and whole from 10,
    # each with its own unit but a range's unit once when its ends share it: 14.2 h so far + 149.9 d–6.4 y to go =
    # 150 d–6.4 y, then 4.2 d so far + 0.5–3.0 h to go = 4.2–4.3 d; each finish time a week or more after the snapshot
    # as its local date, both of the first run's, YYYY-MM-DD; and the first run's ETA chart's axes each in the unit of
    # its largest value, hours of running in days, 0 to 400 d, and hours in all in days too, 0 to 300 d, as the y axis
    # stops a bit above the projected finish (dreeves, 2026-10-23; q_progress_caps_the_y_axis_above_the_projected_finish).
    R = progress_run('long')
    made, (a, b) = PROGRESS_LONG['made'], [r['to_go'] for r in PROGRESS_LONG['runs']]
    h, d, y = NNBSP + 'h', NNBSP + 'd', NNBSP + 'y'
    date = lambda s: time.strftime('%Y-%m-%d', time.localtime(s))
    want = [f'@{stamp(made)}{EMSP}14.2{h} so far + 149.9{d}–6.4{y} to go = 150{d}–6.4{y} ({date(made + a["lo"])} – {date(made + a["hi"])})',
            f'@{stamp(made)}{EMSP}4.2{d} so far + 0.5–3.0{h} to go = 4.2–4.3{d} ({finish(made, made + b["lo"], made + b["hi"])})']
    assert R['state'] == want, (R['state'], want)
    parts = SvgParts()
    parts.feed(R['etaSvg'])
    ticks = lambda k: [text for tag, at, text in parts.items if at.get('class') == k]
    assert ticks('xtick') == ['0', '100', '200', '300', f'400{d}'], ticks('xtick')
    assert ticks('ytick') == ['0', '100', '200', f'300{d}', '6', f'8{y}'], ticks('ytick')   # then the top panel's


def q_progress_breaks_the_y_axis_above_the_projected_finish():
    # Replicata: the ETA charts of progress_run('long') (480:14's bands, thousands of hours above its projected
    # finish), of progress_run('eta') (its purple band's top 0.6 h above the cap) and of progress_run('narrow') (bands
    # within the cap), as markup.
    # Expectata (dreeves, 2026-10-23: "truncate the y-axis a bit above the horizontal purple dashed line ... and
    # indicate visually in some way (no words) when the confidence bands go above the y-axis cap", then "can you do
    # something more canonical for the y-axis break? maybe something like this?", a two-panel plot with slashes at the
    # break): the main panel stops at the cap, 10% above the projected finish, the purple guide's level, its top edge a
    # cap line; anything above the cap, as long's and eta's band tops, gets a top panel 40 units tall, 10 above the
    # main one, linear from the round tick of its unit at or below the least such value (but no lower than the cap) to
    # the round tick at or above the greatest, labeled at the round ticks at its ends, the last with its unit (four
    # labels crowded 480's 40 units); no line at either panel's edge (dreeves, 2026-10-23: "why does this look so bad?
    # the excess horizontal lines": the edges sat a few units from gridlines), so no two horizontal lines within 4
    # units; the 10 units between clipped away; a y axis line at
    # the plot's left (dreeves, 2026-10-23: "i think we need a visible y-axis line for that to look reasonable"), up
    # from the x axis to the main panel's top and from the top panel's bottom to its top, broken at the gap, with a
    # slash across each end of the break (none at the right, where no line is); every band vertex in one panel or on an
    # edge of the gap; and narrow has one panel: its y axis whole, its slashes hidden, nothing clipped.
    for case, over, labels in (('long', True, ['6', '8\u202fy']), ('eta', True, ['20\u202fh']), ('narrow', False, [])):
        parts = SvgParts()
        parts.feed(progress_run(case)['etaSvg'])
        pts = lambda a: [tuple(map(float, xy.split(','))) for xy in a['points'].split()]
        seg = lambda a: tuple(float(a[k]) for k in ('x1', 'y1', 'x2', 'y2'))
        [axis] = [float(a['y1']) for tag, a, _ in parts.items if tag == 'line' and a.get('class') == 'axis']
        [guide] = [pts(a) for tag, a, _ in parts.items if tag == 'polyline' and a.get('class') == 'guide']
        rects = [tuple(float(a[k]) for k in ('x', 'y', 'width', 'height')) for tag, a, _ in parts.items if tag == 'rect']
        yt, yb = rects[0][3], rects[1][1]                     # the top panel's bottom edge, the main panel's top
        assert abs((axis - yb) - 1.1 * (axis - guide[0][1])) < 0.05, (case, axis, yb, guide[0])
        assert not [a for tag, a, _ in parts.items if a.get('class') == 'cap'], case
        rows = sorted({round(seg(a)[1], 2) for tag, a, _ in parts.items if tag == 'line' and a.get('class') in ('grid', 'axis')})
        assert all(b - a >= 4 for a, b in zip(rows, rows[1:])), (case, rows)
        assert (yt, yb) == ((54.0, 64.0) if over else (14.0, 14.0)), (case, yt, yb)
        breaks = [(seg(a), a.get('visibility')) for tag, a, _ in parts.items if tag == 'line' and a.get('class') == 'break']
        assert sorted(s for s, _ in breaks) == sorted((48 - 4, y + 4, 48 + 4, y - 4) for y in (yt, yb)), (case, breaks)
        spine = sorted(seg(a) for tag, a, _ in parts.items if tag == 'line' and a.get('class') == 'yaxis')
        assert spine == sorted([(48, axis, 48, yb), (48, yt, 48, 14)]), (case, spine)
        assert all(v == ('visible' if over else 'hidden') for _, v in breaks), (case, breaks)
        top = [(float(a['y']) - 4, t) for tag, a, t in parts.items if tag == 'text' and a.get('class') == 'ytick' and float(a['y']) - 4 < yb - 0.05]
        assert [t for _, t in top] == labels and all(14 - 0.05 <= y <= yt + 0.05 for y, _ in top), (case, top)
        assert rects == [(0, 0, 640, yt), (0, yb, 640, 240 - yb)], (case, rects)
        bands = [y for tag, a, _ in parts.items if tag == 'polygon' for _, y in pts(a)]
        assert all(14 - 0.05 <= y <= yt + 0.05 or yb - 0.05 <= y for y in bands), (case, sorted(bands))
        assert any(y < yb - 0.05 for y in bands) == over, case


def from_oklab(lab):
    """An OKLab color as #rrggbb, its sRGB clipped: the inverse of oklab(linear(h))."""
    L, a, b = lab
    l, m, s = [(L + x * a + y * b) ** 3 for x, y in ((0.3963377774, 0.2158037573), (-0.1055613458, -0.0638541728), (-0.0894841775, -1.2914855480))]
    lin = (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
           -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)
    enc = [12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in (min(1, max(0, c)) for c in lin)]
    return '#' + ''.join(f'{round(255 * v):02x}' for v in enc)


def q_progress_bands_overlap_visibly():
    # Replicata: the page's CSS: the ETA's band and elapsed + ETA's, each color-mix(in oklab, its color N%, the paper),
    # multiplied onto what is under them; so the three regions they make on the paper: the ETA's band alone, elapsed +
    # ETA's alone, and both.
    # Expectata (dreeves, 2026-10-23: "shouldn't we be able to visually distinguish between a region that both red and
    # purple confidence bands cover vs just the purple confidence band covering it?"; at 16% and 16% that pair was ΔE
    # 6.1, OKLab x 100): both at least ΔE 13 from purple alone and 11 from red alone, and red alone 7 from purple alone.
    style = page()[page().index('<style>'):page().index('</style>')]
    color = lambda name: re.search(rf'--{name}: (#[0-9a-f]{{6}});', style).group(1)
    pct = lambda name: int(re.search(rf'\.progress-eta \.band\.{name} \{{ fill: color-mix\(in oklab, var\(--progress-{name}\) (\d+)%, var\(--paper\)\); \}}', style).group(1)) / 100
    paper = oklab(linear(color('paper')))
    def wash(name):
        c = oklab(linear(color(f'progress-{name}')))
        return from_oklab([pct(name) * x + (1 - pct(name)) * y for x, y in zip(c, paper)])
    red, purple = wash('togo'), wash('total')
    rgb = lambda h: [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    both = '#' + ''.join(f'{round(255 * x * y):02x}' for x, y in zip(rgb(red), rgb(purple)))   # multiply, as the blend does
    got = (delta_e(purple, both), delta_e(red, both), delta_e(red, purple))
    assert got[0] >= 13 and got[1] >= 11 and got[2] >= 7, got


def q_progress_reloads_on_returning_to_the_tab():
    # Replicata: index.html with PROGRESS_DATA as progress.js, the section left open (PROGRESS_REMEMBERED) and the
    # minute's poll; after its first load, a visibilitychange event, as when the tab comes back into view.
    # Expectata (dreeves, 2026-10-23: "did you break auto-refresh yet again?", the page having polled nothing while its
    # tab was hidden): a load at once, not up to a minute later.
    d = tempfile.mkdtemp(prefix='index-quals-')
    harness = """<script>
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  await sleep(1500);
  const before = window.progressView.loads;
  document.dispatchEvent(new Event('visibilitychange'));
  await sleep(50);
  const pre = document.createElement('pre'); pre.id = 'harness-out';
  pre.textContent = JSON.stringify({before, after: window.progressView.loads}); document.body.appendChild(pre);
})();
</script>
"""
    text = page().replace('<head>\n', '<head>\n' + PROGRESS_REMEMBERED).replace('</body>', harness + '</body>')
    open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(text)
    open(os.path.join(d, 'progress.js'), 'w', encoding='utf-8').write('progressData(' + json.dumps(PROGRESS_DATA) + ');\n')
    shutil.copy(DATA, os.path.join(d, 'mstar.js'))
    shutil.copy(POW2, os.path.join(d, 'pow2.js'))
    dom = chrome(d, ['--virtual-time-budget=5000', '--dump-dom', 'file://' + os.path.join(d, 'index.html')])
    shutil.rmtree(d)
    m = re.search(r'<pre id="harness-out">(.*?)</pre>', dom, re.S)
    assert m, dom[-2000:]
    got = json.loads(html.unescape(m.group(1)))
    assert got['before'] >= 1 and got['after'] == got['before'] + 1, got


FOLD = 'progress-fold '         # localStorage: "1" under this prefix and a run's program, n and order while its fold is open
# two runs whose folds have names of their own: PROGRESS_DATA's running one and PROGRESS_ETA_DATA's ended one as
# boxsplit.py's, with no outcome
PROGRESS_FOLDS = {'made': PROGRESS_DATA['made'],
                  'runs': [PROGRESS_DATA['runs'][0], dict(PROGRESS_ETA_DATA['runs'][0], program='boxsplit.py')]}
# The page with data as progress.js and harness (a script) run in it, the section open and before (a script) run before
# the page's own: what the harness put in <pre id="harness-out">, as JSON.
FOLD_LOOK = """
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const runs = () => [...document.querySelectorAll('.progress-runs .progress-run')];
  const look = () => runs().map(r => ({state: r.dataset.runState, open: r.querySelector('details').open,
    summary: !!r.querySelector('summary h3'), color: getComputedStyle(r.querySelector('summary')).color,
    status: r.querySelector('.progress-status').checkVisibility(), canvas: r.querySelector('canvas').width,
    label: [...r.querySelectorAll('summary [data-label]')].filter(e => e.checkVisibility()).map(e => e.textContent)}));
  const out = x => { const pre = document.createElement('pre'); pre.id = 'harness-out'; pre.textContent = JSON.stringify(x); document.body.appendChild(pre); };
"""


def progress_harness(data, harness, before=''):
    d = tempfile.mkdtemp(prefix='index-quals-')
    script = '<script>\n(async () => {' + FOLD_LOOK + '  await sleep(1500);\n' + harness + '\n})();\n</script>\n'
    text = page().replace('<head>\n', '<head>\n' + PROGRESS_REMEMBERED + before).replace('</body>', script + '</body>')
    open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(text)
    open(os.path.join(d, 'progress.js'), 'w', encoding='utf-8').write('progressData(' + json.dumps(data) + ');\n')
    shutil.copy(DATA, os.path.join(d, 'mstar.js'))
    shutil.copy(POW2, os.path.join(d, 'pow2.js'))
    dom = chrome(d, ['--window-size=1000,1100', '--virtual-time-budget=5000', '--dump-dom', 'file://' + os.path.join(d, 'index.html')])
    shutil.rmtree(d)
    m = re.search(r'<pre id="harness-out">(.*?)</pre>', dom, re.S)
    assert m, dom[-2000:]
    return json.loads(html.unescape(m.group(1)))


def q_progress_folds_stay_as_left():
    # Replicata: index.html with PROGRESS_FOLDS as progress.js, the section open and no fold stored; then the running
    # run opened by hand, as by a click; a snapshot in which it has ended; then it closed by hand.
    # Expectata (dreeves, 2026-10-25: "i think there's some anti-magic violation with the collapsed/expanded state.
    # probably they should just remember in localstorage what their state is and just always stay that way until
    # explicitly clicked"): both runs listed, each folded under its heading (a summary) whatever its state, its status
    # line folded with its charts, its dots sized to the section's width though folded, the run not running grayed;
    # opened by hand, a run's fold is stored, "1" under FOLD and its program, n and order, and stays open across the
    # snapshot that ends the run; closed by hand, its stored fold is gone.
    # Resultata before (2026-10-23's design): the running run's fold opened by itself and the ended one's folded, and
    # a fold opened or closed by hand was kept in memory only, so a reload forgot it.
    got = progress_harness(PROGRESS_FOLDS, """
  const name = 'progress-fold overnight_v5.py 64 7', first = look();
  runs()[0].querySelector('details').open = true;
  await sleep(50);
  const stored = localStorage.getItem(name);
  const d2 = JSON.parse(JSON.stringify(window.progressView.data)); d2.made += 60; d2.runs[0].state = 'ended'; d2.runs[0].to_go = null;
  window.progressData(d2);
  await sleep(50);
  const after = look();
  runs()[0].querySelector('details').open = false;
  await sleep(50);
  out({first, stored, after, cleared: localStorage.getItem(name)});""")
    first, after = got['first'], got['after']
    assert [(r['state'], r['open'], r['summary'], r['status']) for r in first] == [('running', False, True, False), ('ended', False, True, False)], first
    assert first[1]['color'] != first[0]['color'], first                 # grayed: not the running heading's color
    assert first[1]['canvas'] == first[0]['canvas'] > 100, first        # sized to the section, folded or not
    assert got['stored'] == '1', got
    assert [(r['state'], r['open'], r['status']) for r in after] == [('ended', True, True), ('ended', False, False)], after
    assert got['cleared'] is None, got


def q_progress_folds_are_remembered_across_loads():
    # Replicata: index.html with PROGRESS_FOLDS as progress.js, the section open, and this browser having left the
    # ended run's fold open (stored before the page's scripts run) and the running run's never opened.
    # Expectata (dreeves, 2026-10-25, as for q_progress_folds_stay_as_left): the ended run open and the running run
    # folded, each as this browser left it, whatever its state.
    got = progress_harness(PROGRESS_FOLDS, '  out(look());',
                           before='<script>localStorage.setItem("progress-fold boxsplit.py 64 7", "1");</script>\n')
    assert [(r['state'], r['open'], r['status']) for r in got] == [('running', False, False), ('ended', True, True)], got


def q_progress_summary_names_each_run_s_state():
    # Replicata: index.html with five runs as progress.js, the section open, every fold folded: running, paused,
    # frozen, ended with an outcome (excluded) and ended with none (its process gone without a finish, as a stopped or
    # crashed run).
    # Expectata (dreeves, 2026-10-25: "can these be clearer when collapsed about what's paused/completed/aborted/
    # running?"): each run's summary, folded, shows one word for its state, running, paused, frozen, completed or
    # aborted, and no other.
    # Resultata before: no word; a run not running was only grayed.
    base = dict(PROGRESS_DATA['runs'][0], to_go=None)
    runs = [dict(base, n=64 + 8 * i, state=state, outcome=outcome) for i, (state, outcome) in
            enumerate([('running', None), ('paused', None), ('frozen', None), ('ended', 'excluded'), ('ended', None)])]
    got = progress_harness({'made': PROGRESS_DATA['made'], 'runs': runs}, '  out(look());')
    assert [(r['state'], r['open'], r['label']) for r in got] == [
        ('running', False, ['running']), ('paused', False, ['paused']), ('frozen', False, ['frozen']),
        ('ended', False, ['completed']), ('ended', False, ['aborted'])], got


def q_progress_names_each_run_s_program():
    # Replicata: progress_run with two runs: PROGRESS_DATA's, then the same as boxsplit.py's pass (PROGRESS_TWO).
    # Expectata: two headings, in the data's order, each the run's question and its program, overnight_v5.py then
    # boxsplit.py (dreeves, 2026-10-17: a second block for the boxsplit pass over 240@11's open cases); both runs' ETA
    # charts show, the second's with no ETA recorded too (dreeves, 2026-10-23: "the search progress section should
    # always be clear about what's been running for how long"; hidden with no ETA from 2026-10-17 until then).
    R = progress_run('two')
    assert R['heads'] == ['m*(64) ≥ 7? overnight_v5.py', 'm*(64) ≥ 7? boxsplit.py'], R['heads']
    assert R['etaDisplays'] == ['grid', 'grid'], R['etaDisplays']


def q_progress_redraws_in_place_and_reads_out_a_subtree():
    # Replicata: progress_run: a hover over the third group's first dot; then progressData given a changed snapshot
    # (one minute later, the running dot open).
    # Expectata: the readout holds the third group's key; after the call the section has drawn again in the same
    # document (the harness's marker survives: no reload), that dot is open's color and the key counts it.
    R = progress_run()
    assert R['readout'].startswith(PROGRESS_DATA['runs'][0]['keys'][2]), R['readout']
    c = R['changed']
    assert c['marker'] == 'kept' and c['renders'] == 2, c
    assert c['pixel'] == rgb(R['colors'][STATUSES.index('open')]), (c['pixel'], R['colors'])
    assert c['counts']['open'] == '4' and c['counts']['running'] == '0', c['counts']



def q_progress_draws_time_to_scale():
    # Replicata: progress_run's time bar: its parts' widths and the median's mark, as the section sets them.
    # Expectata (dreeves, 2026-10-09: "lead with time so far and time to go, to scale"): out of so far + the band's
    # top (2 h + 3 h), so far 40%, the band's bottom 10% after it, the rest of the band 50%, and the median's mark at
    # 60% (the mean's until 2026-10-19, when the boxsplit estimate's Lindy tail made means useless).
    R = progress_run()
    assert {k: float(v.rstrip('%')) for k, v in R['bar'].items()} == {'so-far': 40.0, 'lo': 10.0, 'band': 50.0, 'median': 60.0}, R['bar']


def q_progress_lays_out_each_subtree_as_a_block():
    # Replicata: progress_run's layout of the sea: a rectangle of cells per group (x, y, w, h), in a grid cols wide.
    # Expectata: each group's rectangle holds its dots (w h at least its count) inside the grid; no two rectangles
    # touch (a cell's gap at least between them); and they come in reading order, as the groups do.
    B = progress_run()['blocks']
    rects, sizes = B['rects'], [len(g) for g in PROGRESS_DATA['runs'][0]['groups']]
    assert len(rects) == len(sizes) and all(r['w'] * r['h'] >= n for r, n in zip(rects, sizes)), (rects, sizes)
    assert all(r['x'] >= 0 and r['y'] >= 0 and r['x'] + r['w'] <= B['cols'] and r['y'] + r['h'] <= B['rows'] for r in rects), B
    apart = lambda a, b: a['x'] + a['w'] < b['x'] or b['x'] + b['w'] < a['x'] or a['y'] + a['h'] < b['y'] or b['y'] + b['h'] < a['y']
    assert all(apart(a, b) for i, a in enumerate(rects) for b in rects[i + 1:]), rects
    assert [(r['y'], r['x']) for r in rects] == sorted((r['y'], r['x']) for r in rects), rects


def q_progress_draws_the_eta_chart():
    # Replicata: progress_run's ETA chart (progress.html's, ported: dreeves, 2026-10-09 and 10-10), from
    # PROGRESS_DATA's three recorded ETAs; a hover over the second, then over the last.
    # Expectata: shown, as wide as the sea (2026-10-17: as a figure, the page's figure rule shrank it to its content); the
    # ETA's line has a point per record; no direct labels at the last record (they gave its ranges and the elapsed time
    # until dreeves's "comment it out for now", 2026-10-17: the status line below says the same, in the same colors), so
    # no x tick gives way to the elapsed time's label: 0, 1, 2 and 3 h; the tip, laid out but invisible at rest (a line
    # of its own, so that showing it moves nothing: the page jumped on hover until 2026-10-17), is the status line's
    # running form for the record under the pointer (dreeves, 2026-10-17: "the same as the line below, just an earlier
    # snapshot thereof and with the datetimestamp prefix"): over the second record, an @ and its time, an em space, 1.0 h
    # so far + 1.0–3.0 h to go = 2.0–4.0 h, and in parentheses the local times its band ends between; over the last (the
    # snapshot's own), the status line exactly, markup and all; and the hover moved the status line not at all.
    R = progress_run()
    E = R['eta']
    assert not E['hidden'] and E['togo'] == 3 and abs(E['widths'][0] - E['widths'][1]) <= 1, E
    h = NNBSP + 'h'
    assert E['labels'] == 0, E
    # With the labels (until 2026-10-17; back with them):
    # assert (E['labelTogo'], E['labelTotal'], E['labelSpent']) == (f'0.5–3.0{h}', f'2.5–5.0{h}', f'2.0{h}'), E
    parts = SvgParts()
    parts.feed(R['etaSvg'])
    assert [text for tag, a, text in parts.items if a.get('class') == 'xtick'] == ['0', '1', '2', f'3{h}'], R['etaSvg']
    t = PROGRESS_DATA['runs'][0]['etas'][1][0]
    assert E['tip'] == f'@{stamp(t)}{EMSP}1.0{h} so far + 1.0–3.0{h} to go = 2.0–4.0{h} ({finish(t, t + 3600, t + 10800)})', E['tip']
    assert E['tipLast'] == R['state'][0] and E['sameMarkup'] is True, (E['tipLast'], R['state'], E['sameMarkup'])
    assert R['tipRest']['visibility'] == 'hidden' and R['tipRest']['height'] > 0 and R['jump'] == 0, (R['tipRest'], R['jump'])


def q_progress_tip_projects_past_the_last_record():
    # Replicata: progress_run: hovers over the ETA chart's records, then at 2.5 h of running, half an hour past its last
    # record (PROGRESS_DATA's, at 2 h: 0.5–3.0 h to go).
    # Expectata (dreeves, 2026-10-18: "the hover feature of showing the historical ETA might as well work for the whole
    # graph, right? i guess what we'd need is a way to make the distinction clear between historical vs projected"):
    # there the tip is the last record's line carried on half an hour, in italics (class projected): the clock and the
    # hours so far half an hour on, 2.5 h so far, the band half an hour lower and no lower than 0, 0.0–2.5 h to go, so
    # 2.5–5.0 h in all and the status line's finish times; the cross line at the pointer; over a record, no italics;
    # and the status line below the chart did not move.
    R = progress_run()
    E, h = R['eta'], NNBSP + 'h'
    t = PROGRESS_DATA['made'] + 1800
    want = f'@{stamp(t)}{EMSP}2.5{h} so far + 0.0–2.5{h} to go = 2.5–5.0{h} ({finish(t, t, t + 9000)})'
    assert E['tipAhead'] == want, (E['tipAhead'], want)
    A = E['ahead']
    assert A['projected'] is True and A['style'] == 'italic' and abs(A['cross'] - A['want']) < 0.05, A
    assert E['projectedAtRecord'] is False and R['jumpAhead'] == 0, (E['projectedAtRecord'], R['jumpAhead'])


class SvgParts(html.parser.HTMLParser):
    """An svg's elements in document order, each [tag, attributes, text], an element's text with its children's."""
    def __init__(self):
        super().__init__()
        self.items, self.open = [], []
    def handle_starttag(self, tag, attrs):
        item = [tag, dict(attrs), '']
        self.items.append(item)
        self.open.append(item)
    def handle_endtag(self, tag):
        while self.open and self.open.pop()[0] != tag: pass
    def handle_data(self, data):
        for item in self.open: item[2] += data


def q_progress_eta_chart_keeps_progress_html_s_spec():
    # Replicata: progress_run('eta'): the section's ETA chart of PROGRESS_ETA_DATA, progress.html's case (13.2 h of
    # running; ETAs [2, 1, 4] h at 0 h and [1, 0.5, 3] h at 13.2 h), as markup; and the section's CSS.
    # Expectata, progress.html's (quals_progress's q_page_draws_the_eta_chart until 2026-10-17, when index.html's
    # section took the chart over): it knows nothing of passes (dreeves, 2026-10-10); round ticks every 5 h from 0 to
    # 15 h on both axes, labeled, the top one with its unit, a gridline at each y tick but 0, which is the axis; the
    # diagonal of elapsed time (spent) from (0, 0) to (13.2, 13.2) h, carried on ahead, dashed, to (14.2, 14.2); the
    # band along the ETAs' tops left to right and their bottoms back; the ETA (togo) and elapsed + ETA (total) with a
    # point per ETA; at the last, a vertical range line across its band, markers on both lines, and dreeves's direct
    # labels (2026-10-10; ranges since 2026-10-12): "ETA 0.5–3.0 h" just right of the red marker, "14–16 h" just right
    # of the black one, and "13 h" in blue on the x axis under it; a cross line hidden at rest; no other line; the
    # black stroke the widest; the palette's blue (#2a78d6) and red (#e34948) and the page's ink; the legend in
    # dreeves's words: elapsed time, ETA, elapsed + ETA.  And since 2026-10-17 (dreeves: "1. yes"), the projected finish
    # marked: a hollow marker (finish) where the dashed elapsed time meets elapsed + ETA, at (14.2, 14.2) h, and a guide
    # from the black marker across to it and down to the x axis, (13.2, 14.2), (14.2, 14.2), (14.2, 0) h.  Then, at
    # dreeves's request (2026-10-17): the ETA's ideal course, a red dotted line (ideal) from the red marker down to the x
    # axis at the finish, (13.2, 1) to (14.2, 0) h; the red label without its "ETA", "0.5–3.0 h"; and no legend: the
    # status line below the chart says what each color is (q_progress_states_times_and_hours); and, since dreeves's
    # "comment it out for now" (2026-10-17), no direct labels, nor their rules among the live CSS.  Then, at dreeves's
    # request (2026-10-17: "1. shouldn't the black line also have a confidence band? 2. shouldn't there be a blue dot for
    # consistency? 3. ooh, how about purple instead of black, because blue+red=purple?"): elapsed + ETA's band too, the
    # ETAs' band raised by each record's elapsed time, (0, 4), (13.2, 16.2), (13.2, 13.7), (0, 1) h, with its own range
    # line at the last, (13.2, 13.7) to (13.2, 16.2) h; a blue marker at the last record's elapsed time, (13.2, 13.2) h,
    # where the dashed elapsed time starts; elapsed + ETA purple, #7b1fa2 (the validator's numbers are in the CSS), in
    # its line, band, range line, marker, label and the finish marker's ring, the black ink no more; and the y axis
    # taller, to the top of elapsed + ETA's band (16.2 h), so its ticks run from 0 to 20 h.  The two bands can overlap,
    # and so can the two range lines (not here; in boxsplit.py's chart of 2026-10-17, from 46 to 51 h), so both bands
    # and both range lines multiply onto what is under them: neither hides the other (the purple range line hid the red
    # one's top until they did, 2026-10-17).  And the guide purple too, as it carries elapsed + ETA's level across to the
    # finish and down to it on the x axis (dreeves, 2026-10-18: "that looks black and should be purple"; the page's
    # muted gray before).  And no finish marker since 2026-10-18 (dreeves: "remove the hollow purple dot at the upper
    # right; that might look cleaner"): the guide alone marks the projected finish.  And since 2026-10-23 (dreeves:
    # "truncate the y-axis a bit above the horizontal purple dashed line ... and indicate visually in some way (no words)
    # when the confidence bands go above the y-axis cap", then "can you do something more canonical for the y-axis
    # break?"), the main panel stops 10% above the projected finish, at 15.62 h, in place of 20 h: its gridlines at 5, 10
    # and 15 h and its top edge at 15.62 h; and elapsed + ETA's band top (16.2 h) and range line's go to a top panel,
    # 15.62 to 20 h, labeled 20 h (q_progress_breaks_the_y_axis_above_the_projected_finish).
    R = progress_run('eta')
    parts = SvgParts()
    parts.feed(R['etaSvg'])
    els = [(tag, a, re.sub(r'[ \t\n\r]+', ' ', text).strip()) for tag, a, text in parts.items]   # U+202F stays: it is text
    def pts(text): return [tuple(map(float, xy.split(','))) for xy in text.split()]
    polys = {a['class']: pts(a['points']) for tag, a, _ in els if tag == 'polyline'}
    assert sorted(polys) == ['guide', 'spent', 'togo', 'total'], polys.keys()
    (x0, y0), (x1, y1) = polys['spent'][0], polys['spent'][-1]          # blue at 0 h and at 13.2 h
    def X(h): return x0 + (x1 - x0) * h / 13.2
    def Y(h): return y0 + (y1 - y0) * h / 13.2
    def near(p, q): return abs(p[0] - q[0]) < 0.05 and abs(p[1] - q[1]) < 0.05
    cap, lo2, hi2 = 1.1 * 14.2, 1.1 * 14.2, 20                          # the main panel's cap; the top panel's ends, h
    YB = Y(cap)                                                          # the main panel's top edge; the top panel's
    YT = YB - 10                                                         # bottom edge, 10 units above, its top 40 above that
    def Ys(h): return Y(min(h, cap)) - 10 * (h > cap) - 40 * min(1, max(0, (h - lo2) / (hi2 - lo2)))
    def check(got, want, what): assert len(got) == len(want) and all(near(g, (X(a), Ys(b))) for g, (a, b) in zip(got, want)), (what, got, [(X(a), Ys(b)) for a, b in want])
    for k, w in (('spent', [(0, 0), (13.2, 13.2)]), ('togo', [(0, 2), (13.2, 1)]), ('total', [(0, 2), (13.2, 14.2)]),
                 ('guide', [(13.2, 14.2), (14.2, 14.2), (14.2, 0)])): check(polys[k], w, k)
    bands = {a['class']: pts(a['points']) for tag, a, _ in els if tag == 'polygon'}
    assert sorted(bands) == ['band togo', 'band total'], bands.keys()
    check(bands['band togo'], [(0, 4), (13.2, 3), (13.2, 0.5), (0, 1)], 'band togo')
    # elapsed + ETA's band crosses the break twice, so it gets each crossing on both edges of the gap (2026-10-23)
    xc = 13.2 * (cap - 4) / (16.2 - 4)
    want = [(X(0), Ys(4)), (X(xc), YB), (X(xc), YT), (X(13.2), Ys(16.2)), (X(13.2), YT), (X(13.2), YB), (X(13.2), Ys(13.7)), (X(0), Ys(1))]
    assert len(bands['band total']) == len(want) and all(near(g, w) for g, w in zip(bands['band total'], want)), (bands['band total'], want)
    lines = [(a['class'], tuple(float(a[k]) for k in ('x1', 'y1', 'x2', 'y2')), a) for tag, a, _ in els if tag == 'line']
    assert sorted(c for c, _, _ in lines) == sorted(['axis', 'ahead', 'ideal', 'range togo', 'range total', 'cross'] + ['grid'] * 4 + ['break'] * 2 + ['yaxis'] * 2), [c for c, _, _ in lines]
    seg = {c: s for c, s, _ in lines if c not in ('grid', 'break', 'yaxis')}
    check([seg['ahead'][:2], seg['ahead'][2:]], [(13.2, 13.2), (14.2, 14.2)], 'ahead')
    check([seg['ideal'][:2], seg['ideal'][2:]], [(13.2, 1), (14.2, 0)], 'ideal')
    check([seg['range togo'][:2], seg['range togo'][2:]], [(13.2, 0.5), (13.2, 3)], 'range togo')
    check([seg['range total'][:2], seg['range total'][2:]], [(13.2, 13.7), (13.2, 16.2)], 'range total')
    assert abs(seg['axis'][1] - Y(0)) < 0.05 and seg['axis'][1] == seg['axis'][3], seg['axis']
    grid = [s for c, s, _ in lines if c == 'grid' and s[1] > YB]       # the main panel's
    hours = sorted((y0 - g[1]) / (y0 - Y(1)) for g in grid)              # to 0.01 h: positions are written to 0.01 units
    assert len(hours) == 3 and all(abs(h - t) < 0.01 for h, t in zip(hours, (5, 10, 15))) and all(g[1] == g[3] for g in grid), grid
    assert [s[1] for c, s, _ in lines if c == 'grid' and s[1] < YB] == [14], lines     # the top panel's, at 20 h, its top
    assert sorted(round(y, 2) for c, s, _ in lines if c == 'yaxis' for y in (s[1], s[3])) == sorted([round(YT, 2), round(YB, 2), 14, round(Y(0), 2)]), lines   # its y axis's ends at the break
    cross = next(a for c, _, a in lines if c == 'cross')
    assert cross.get('visibility') == 'hidden', cross
    yt = [(float(a['y']), text) for tag, a, text in els if tag == 'text' and a.get('class') == 'ytick']
    assert [v for _, v in yt] == ['0', '5', '10', '15\u202fh', '20\u202fh'] and all(abs(y - 4 - Ys(int(v.split()[0]))) < 0.05 for y, v in yt), yt   # up to the cap, 15.62 h, then the top panel's (2026-10-23; to 20 h before)
    xt = [(float(a['x']), text) for tag, a, text in els if tag == 'text' and a.get('class') == 'xtick']
    assert [v for _, v in xt] == ['0', '5', '10', '15\u202fh'] and all(abs(x - X(int(v.split()[0]))) < 0.05 for x, v in xt), xt
    now = {a['class'].split()[1]: (float(a['cx']), float(a['cy'])) for tag, a, _ in els if tag == 'circle'}
    assert sorted(now) == ['spent', 'togo', 'total'], now
    check([now['spent'], now['togo'], now['total']], [(13.2, 13.2), (13.2, 1), (13.2, 14.2)], 'now')
    labels = {a['class'].split()[1]: (float(a['x']), float(a['y']), text) for tag, a, text in els
              if tag == 'text' and a.get('class', '').startswith('label ')}
    assert labels == {}, labels
    # With the labels (until 2026-10-17; back with them):
    # assert {k: v for k, (_, _, v) in labels.items()} == {'togo': '0.5–3.0\u202fh', 'total': '14–16\u202fh', 'spent': '13\u202fh'}, labels
    # for k, h in (('togo', 1), ('total', 14.2)):
    #     x, y, _ = labels[k]
    #     assert X(13.2) < x < X(13.2) + 20 and abs(y - Y(h)) < 16, (k, labels[k], X(13.2), Y(h))
    # x, y, _ = labels['spent']
    # assert abs(x - X(13.2)) < 0.05 and y > Y(0), (labels['spent'], X(13.2), Y(0))
    style = re.sub(r'/\*.*?\*/', '', page()[page().index('<style>'):page().index('</style>')], flags=re.S)   # live rules only
    assert re.search(r'--progress-spent: #2a78d6;', style) and re.search(r'--progress-togo: #e34948;', style) and re.search(r'--progress-total: #7b1fa2;', style)
    widths = {k: float(w) for k, w in re.findall(r'\.progress-eta \.(spent|togo|total) \{[^}]*stroke-width: ([\d.]+)', style)}
    assert set(widths) == {'spent', 'togo', 'total'} and widths['total'] > max(widths['spent'], widths['togo']), widths
    fills = dict(re.findall(r'\.progress-eta \.label\.(togo|total|spent) \{ fill: var\(--([\w-]+)\); \}', style))
    assert fills == {}, fills
    # With the labels (until 2026-10-17; back with them):
    # assert fills == {'togo': 'progress-togo', 'total': 'progress-total', 'spent': 'progress-spent'}, fills
    tints = {(b, s): c for b, s, c in re.findall(r'\.progress-eta \.(band|range)\.(togo|total) \{ [\w-]+: color-mix\(in oklab, var\(--progress-(togo|total)\) \d+%', style)}
    assert tints == {(b, s): s for b in ('band', 'range') for s in ('togo', 'total')}, tints
    dots = dict(re.findall(r'\.progress-eta \.now\.(spent|togo|total) \{ fill: var\(--progress-([\w-]+)\);', style))
    assert dots == {'spent': 'spent', 'togo': 'togo', 'total': 'total'}, dots
    assert not re.search(r'\.finish\b', style), 'a rule for the finish marker'
    assert re.search(r'\.progress-eta \.guide \{ stroke: var\(--progress-total\);', style), 'the guide not purple'
    assert all(re.search(rf'\.progress-eta \.{k} \{{[^}}]*mix-blend-mode: multiply;', style) for k in ('band', 'range')), 'an overlap hidden'
    assert R['status']['legends'] == 0, R['status']

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
