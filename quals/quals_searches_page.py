#!/usr/bin/env python3
"""Fable 5.2's quals for the tracked searches' boxes in index.html's section "Search progress", in the real page in
headless Chrome (2026-11-11; dreeves: "sounds like obviously yes, that we want to see different searches on the same
cell separately", "what happened to the probability graph?", "we used to have a progress bar", and "the search
progress code seems like a shitshow; can you revamp it? ... anti-magic anti-magic anti-magic").  Run from the repo:
    python3 -B quals/quals_searches_page.py [name ...]
Each qual is a function q_*: a passing qual returns, a failing one raises; each comment gives its replicata and
expectata; a failure's message or traceback gives the resultata.  The page is given a made-up pagedata/progress.js
(SEARCHES: entries as searchwatch/watch.py writes them).
"""
import sys
sys.dont_write_bytecode = True
import copy, html, json, os, re, shutil, tempfile, time, traceback
from pathlib import Path
import quals_index as page

MADE = 1794450000
band = lambda m, lo, hi: dict(median=m, lo=lo, hi=hi)


def entry(search, n, order, state, outcome, basis, work, so_far, to_go, runs, dots, exists, pending, finished):
    """An entry as watch.py writes it: three estimates, a third of its time so far apart, the last at MADE, with these nodes
    pending and these tasks finished (None: none counted).  (Until 2026-11-12 five minutes apart: a pixel or two on a
    chart of tens of hours, too close for a pointer to tell apart.)"""
    times = [MADE - round(2 * so_far / 3), MADE - round(so_far / 3), MADE]
    return dict(search=search, n=n, order=order, state=state, outcome=outcome, so_far=so_far, runs=runs,
                statuses=['settled', 'open', 'pending', 'running'], depth=0, keys=[f'{n}:{order}'], groups=[dots],
                counts={s: dots.count(str(i)) for i, s in enumerate(['settled', 'open', 'pending', 'running'])},
                to_go=to_go, basis=basis, work=work,
                etas=[[t, so_far - (MADE - t), to_go['median'] + (MADE - t), to_go['lo'] + (MADE - t), to_go['hi'] + (MADE - t)] for t in times],
                odds=dict(prior=0.5, since=MADE - so_far, exists=[[t, p] for t, p in zip(times, exists)]),
                cpu=[[(so_far - 120) / 3600, (so_far - 60) / 3600, MADE - 60, 0.6, 0.3, 0.1], [(so_far - 60) / 3600, so_far / 3600, MADE, 0.7, 0.2, 0.1]],
                pending=[[t, so_far - (MADE - t), k] for t, k in zip(times, pending) if k is not None],
                finished=[[t, so_far - (MADE - t), k] for t, k in zip(times, finished) if k is not None], stale=None)


TREE = entry('formtree', 480, 14, 'running', None, 'formtree', dict(unit='nodes', done=4200000, rate=510.25, total=band(9.1e7, 2.2e7, 4.1e8)),
             11000.0, band(170000.0, 35000.0, 800000.0), dict(runs=4, running=1, frozen=0, ended=2, aborted=1, paused=0, found=0), '0103', [0.49, 0.485, 0.48],
             [700, 740, 760], [3000, 3600, 4100])
TILT = entry('tilt', 2016, 15, 'running', None, 'lindy', dict(unit='seconds', done=3600.0, rate=1.0, total=band(7200.0, 4000.0, 36000.0)),
             3600.0, band(3600.0, 400.0, 32400.0), dict(runs=2, running=2, frozen=0, ended=0, aborted=0, paused=0, found=0), '33', [0.5, 0.5, 0.5],
             [None] * 3, [None] * 3)
SYM = entry('formtree-sym', 480, 14, 'ended', 'none', 'formtree', dict(unit='nodes', done=145427, rate=35.5, total=band(145427, 145427, 145427)),
            4100.0, band(0.0, 0.0, 0.0), dict(runs=4, running=0, frozen=0, ended=2, aborted=2, paused=0, found=0), '1100', [0.3, 0.1, 0.0],
            [30, 10, 0], [120, 160, 170])
OLDTILT = dict(entry('tilt', 1104, 14, 'ended', None, 'lindy', dict(unit='seconds', done=1500.0, rate=1.0, total=band(3000.0, 1666.0, 15000.0)),
                     1500.0, band(1500.0, 166.0, 13500.0), dict(runs=3, running=0, frozen=0, ended=2, aborted=1, paused=0, found=0), '001', [0.5, 0.5, 0.5],
                     [None] * 3, [None] * 3))
SEARCHES = dict(made=MADE, runs=[SYM, TREE, OLDTILT, TILT])           # as the watcher lists them: not by state

HARNESS = r"""<script>
(async () => {
  const result = {}, sleep = ms => new Promise(r => setTimeout(r, ms));
  try {
    const section = document.querySelector('section.progress');
    section.querySelector('details').open = true;
    let quiet = 0;
    for (let n = 0; quiet < 3 && n < 120; n++) {
      await sleep(50);
      const settled = window.progressView.data || !section.querySelector('.progress-missing').hidden;
      quiet = settled && !document.head.querySelector('script[src^="pagedata/progress.js"]') ? quiet + 1 : 0;
    }
    if (quiet < 3) throw Error('snapshot');
    for (const d of section.querySelectorAll('.progress-runs .progress-run details')) d.open = true;
    await sleep(100);
    const shown = e => !!e && e.checkVisibility();
    const rect = e => { const r = e.getBoundingClientRect(); return {x: r.x, width: r.width, right: r.right}; };
    result.made = section.querySelector('[data-made]').textContent;
    result.age = section.querySelector('[data-age]').textContent;
    result.missing = shown(section.querySelector('.progress-missing'));
    result.boxes = [...section.querySelectorAll('.progress-runs .progress-run')].map(box => {
      const q = s => box.querySelector(s), part = name => q(`[data-bar="${name}"]`);
      // a graph of a count over time (the nodes pending, the tasks finished: 2026-11-12), by the parts each has alike
      const count = sel => { const f = q(sel), c = s => f.querySelector(s);
        return {empty: f.hasAttribute('data-empty'), opacity: +getComputedStyle(c('svg')).opacity,
                line: (c('[data-count-line]').getAttribute('points') || '').trim().split(/\s+/).filter(Boolean).map(p => p.split(',').map(Number)),
                ticks: [...f.querySelectorAll('[data-count-ticks] text.ytick')].map(t => [t.textContent, +t.getAttribute('y')]),
                axis: +(c('[data-count-grid] line.axis') || {getAttribute: () => NaN}).getAttribute('y1')}; };
      return {
        label: q('[data-program]').textContent, n: q('[data-n]').textContent, order: q('[data-order]').textContent,
        state: [...box.querySelectorAll('.progress-run-state [data-label]')].filter(shown).map(e => e.dataset.label),
        parts: {bar: shown(q('.progress-work')), eta: shown(q('.progress-eta svg')), status: shown(q('.progress-status')), cpu: shown(q('.progress-cpu svg')),
                pending: shown(q('.progress-pending svg')), finished: shown(q('.progress-finished svg')), runs: shown(q('[data-track-line]')),
                dots: shown(q('canvas')), odds: shown(q('.progress-odds svg'))},
        pending: count('.progress-pending'), finished: count('.progress-finished'),
        extras: box.querySelectorAll('.progress-pool, [data-stages], .progress-key, [data-pool-tip]').length,
        lindy: shown(q('[data-lindy]')),
        caption: q('.progress-bar-caption').textContent.replace(/\s+/g, ' ').trim(),
        bar: rect(q('.progress-bar')), done: rect(part('done')), band: rect(part('band')), median: rect(part('median')),
        ticks: [...q('[data-bar="ticks"]').children].map(e => e.textContent),
        status: [...box.querySelectorAll('.progress-status [data-state]')].filter(shown).map(e => e.innerText.replace(/\s+/g, ' ').trim()),
        runsLine: q('[data-track-line]').textContent.replace(/\s+/g, ' ').trim(),
        hint: q('[data-readout]').textContent.replace(/\s+/g, ' ').trim(),
        prior: q('[data-odds-prior]').textContent,
        now: q('[data-odds-now]')?.textContent ?? null,
        // the prior line from the prior's number on, its words before it left unread (2026-11-13)
        oddsTail: (() => { let t = '', e = q('[data-odds-prior]'); for (; e; e = e.nextSibling) t += e.textContent; return t.replace(/\s+/g, ' ').trim(); })(),
        oddsPoints: q('[data-exists-line]').getAttribute('points').trim().split(/\s+/).length,
        oddsEmpty: q('.progress-odds').hasAttribute('data-empty'),
        etaPoints: q('[data-togo]').getAttribute('points').trim().split(/\s+/).length,
        cpuBands: q('[data-cpu-bands]').children.length,
        canvas: q('canvas').width * q('canvas').height > 0,
      };
    });
    const wants = await new Promise(done => window.progressView.want(480n, 14, nodes => done(nodes)));
    // a brief's words as a box shows them: without the parts marked hidden
    const words = e => { const c = e.cloneNode(true); for (const h of c.querySelectorAll('[hidden]')) h.remove(); return c.textContent.replace(/\s+/g, ' ').trim(); };
    result.briefs = wants.map(e => typeof e === 'string' ? e : words(e));
    const none = await new Promise(done => window.progressView.want(7n, 3, nodes => done(nodes)));
    result.none = none.map(e => typeof e === 'string' ? e : e.textContent);
    result.etaXs = window.progressView.layouts.map(L => L.etaXs);
    result.finishedXs = window.progressView.layouts.map(L => L.finishedXs);
    // each graph's span (2026-11-12): its axis line's ends, its y labels' places, the ETA chart's purple guide, and the column
    const tree = section.querySelector('.progress-runs .progress-run'), one = (sel, a) => +tree.querySelector(sel).getAttribute(a);
    result.span = tree && {column: document.querySelector('section.mstar').getBoundingClientRect().width, svg: tree.querySelector('.progress-eta svg').getBoundingClientRect().width,
                   axes: Object.fromEntries(['eta', 'cpu', 'pending', 'finished', 'odds'].map(k => [k, [one(`.progress-${k} line.axis`, 'x1'), one(`.progress-${k} line.axis`, 'x2')]])),
                   // each graph's y axis line or lines, [x1, x2], and the ETA chart's slashes at its break, [x1, x2, visibility]
                   yaxes: Object.fromEntries(['eta', 'cpu', 'pending', 'finished', 'odds'].map(k => [k, [...tree.querySelectorAll(`.progress-${k} line.yaxis`)].map(l => [+l.getAttribute('x1'), +l.getAttribute('x2')])])),
                   breaks: [...tree.querySelectorAll('.progress-eta line.break')].map(l => [+l.getAttribute('x1'), +l.getAttribute('x2'), l.getAttribute('visibility')]),
                   // each value label's x, its anchor, and its ink's left and right edges as drawn; each hour label's anchor
                   ylabels: [...tree.querySelectorAll('svg text.ytick')].map(t => { const b = t.getBBox(); return [+t.getAttribute('x'), t.getAttribute('text-anchor'), b.x, b.x + b.width]; }),
                   xanchors: [...tree.querySelectorAll('svg text.xtick')].map(t => t.getAttribute('text-anchor')),
                   guide: tree.querySelector('.progress-eta [data-guide]').getAttribute('points').trim().split(/\s+/).map(p => p.split(',').map(Number)),
                   // each chart's drawing against its size as it shows: [viewBox width, shown width, viewBox height, shown height]
                   scale: ['eta', 'cpu', 'pending', 'finished', 'odds'].map(k => { const v = tree.querySelector(`.progress-${k} svg`), b = v.getBoundingClientRect();
                                                                       return [v.viewBox.baseVal.width, b.width, v.viewBox.baseVal.height, b.height]; })};
    result.figureText = getComputedStyle(document.getElementById('mstar-readout')).fontSize;   // Figure 1's readout, as its legend's
    // the words of each graph, with where they sit against it and their size (2026-11-12)
    const after = (a, b) => !!(a && b && (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING));
    const size = e => e && getComputedStyle(e).fontSize;
    result.words = [...section.querySelectorAll('.progress-runs .progress-run')].map(box => {
      const q = s => box.querySelector(s);
      const below = {bar: [q('.progress-bar'), q('.progress-bar-caption')], eta: [q('.progress-eta svg'), q('.progress-status')],
                     hint: [q('canvas'), q('[data-readout]')]};
      const above = {tip: [q('.progress-tip'), q('.progress-eta svg')], cpu: [q('.progress-cpu-key'), q('.progress-cpu svg')],
                     pending: [q('.progress-pending-title'), q('.progress-pending svg')], finished: [q('.progress-finished-title'), q('.progress-finished svg')],
                     runs: [q('[data-track-line]'), q('canvas')],
                     prior: [q('.progress-odds > p'), q('.progress-odds svg')], title: [q('.progress-odds-title'), q('.progress-odds svg')]};
      return {below: Object.fromEntries(Object.entries(below).map(([k, [g, w]]) => [k, after(g, w)])),
              above: Object.fromEntries(Object.entries(above).map(([k, [w, g]]) => [k, after(w, g)])),
              sizes: Object.fromEntries(Object.entries({bar: q('.progress-bar-caption'), tip: q('.progress-tip'), status: q('.progress-status'),
                                                         lindy: q('[data-lindy]'), cpu: q('.progress-cpu-key'), pending: q('.progress-pending-title'),
                                                         finished: q('.progress-finished-title'),
                                                         runs: q('[data-track-line]'), hint: q('[data-readout]'), prior: q('.progress-odds > p'),
                                                         title: q('.progress-odds-title')}).map(([k, e]) => [k, size(e)])),
              ticks: ['.progress-bar-axis > span', '.progress-eta text.xtick', '.progress-cpu text.xtick', '.progress-pending text.xtick',
                      '.progress-finished text.xtick', '.progress-odds text.xtick'].map(s => [...box.querySelectorAll(s)].map(e => e.textContent)),
              tickSizes: ['.progress-bar-axis > span', '.progress-eta text.xtick', '.progress-cpu text.xtick', '.progress-pending text.xtick',
                          '.progress-finished text.xtick'].map(s => size(q(s))),
              tipHeight: q('.progress-tip').getBoundingClientRect().height, statusHeight: q('.progress-status').getBoundingClientRect().height};
    });
    // hovers over the running form tree's three aligned charts: each at its second point, then away
    const box = section.querySelector('.progress-runs .progress-run'), L = window.progressView.layouts[0];
    const hover = (sel, x) => {
      const svg = box.querySelector(sel + ' svg'), b = svg.getBoundingClientRect();
      svg.dispatchEvent(new MouseEvent('mousemove', {clientX: b.left + x * b.width / svg.viewBox.baseVal.width, clientY: b.top + b.height / 2, bubbles: true}));
      const g = box.querySelector(sel + ' [data-stamp]'), text = g.querySelector('text'), cross = box.querySelector(sel + ' line.cross');
      const ticks = [...box.querySelectorAll(sel + ' text.xtick')];
      const read = {width: svg.viewBox.baseVal.width, shown: g.getAttribute('visibility') === 'visible', text: text.textContent, x: +text.getAttribute('x'), y: +text.getAttribute('y'),
                    cross: +cross.getAttribute('x1'), tickY: ticks.length ? +ticks[0].getAttribute('y') : null,
                    box: (r => [+r.getAttribute('x'), +r.getAttribute('width')])(g.querySelector('rect')),
                    tip: box.querySelector('[data-tip]').innerText.replace(/\s+/g, ' ').trim(),
                    cpu: box.querySelector('.progress-cpu-key').innerText.replace(/\s+/g, ' ').trim(),
                    now: box.querySelector('[data-odds-now]')?.textContent ?? null};
      svg.dispatchEvent(new MouseEvent('mouseleave', {bubbles: true}));
      read.after = {shown: g.getAttribute('visibility') === 'visible', now: box.querySelector('[data-odds-now]')?.textContent ?? null};
      return read;
    };
    result.hovers = box && {eta: hover('.progress-eta', L.etaXs[1]), cpu: hover('.progress-cpu', (L.etaXs[0] + L.etaXs[1]) / 2),
                            pending: hover('.progress-pending', L.pendingXs[1]), finished: hover('.progress-finished', L.finishedXs[1]),
                            odds: hover('.progress-odds', L.oddsXs[1])};   // none on a page with no box
    result.oddsFirst = box && hover('.progress-odds', L.oddsXs[0]);   // the probability graph's first point, for its readout
    result.width = document.documentElement.scrollWidth;
  } catch (e) { result.error = String(e.stack || e); }
  parent.postMessage(JSON.stringify(result), '*');
})();
</script>"""


def render(width, searches=SEARCHES):
    """The harness's report on the page at width (CSS px), in an iframe (page.HOST), with searches as its progress.js
    (None: no such file)."""
    with tempfile.TemporaryDirectory(prefix='searches-page-quals-') as d:
        source = page.page().replace('<head>\n', '<head>\n' + page.PROGRESS_REMEMBERED + f'<script>window.PROGRESS_CLOCK = () => {MADE + 75};</script>\n')
        Path(d, 'index.html').write_text(source.replace('</body>', HARNESS + '</body>'))
        page.copy_page_dir(d)
        shutil.copy(page.DATA, page.data_file(d, 'mstar.js'))
        shutil.copy(page.POW2, page.data_file(d, 'pow2.js'))
        if searches is not None: Path(page.data_file(d, 'progress.js')).write_text('progressData(' + json.dumps(searches) + ');\n')
        Path(d, 'host.html').write_text(page.HOST.replace('__WIDTH__', str(width)))
        dom = page.chrome(d, [f'--window-size={max(width, 500) + 40},1100', '--force-device-scale-factor=1', '--virtual-time-budget=15000',
                              '--dump-dom', 'file://' + str(Path(d, 'host.html'))])
        found = re.search(r'<pre id="harness-out">(.*?)</pre>', dom, re.S)
        assert found, dom[-2000:]
        result = json.loads(html.unescape(found[1]))
        assert 'error' not in result, result['error']
        return result


def numbers(text):
    """A caption's numbers, in order (a range, lo–hi, one), its words left out: what a qual holds a caption to, since its words
    are dreeves's to change (2026-11-12)."""
    return re.findall(r'\d[\d,.]*[KMBT]?(?:–\d[\d,.]*[KMBT]?)?', text)


REPORTS = {}
def report(width):
    if width not in REPORTS: REPORTS[width] = render(width)
    return REPORTS[width]


def q_every_search_has_its_box_and_every_box_the_same_parts():
    # Replicata: the page, 1280 px wide, its section "Search progress" open, with SEARCHES as pagedata/progress.js,
    # four searches as the watcher lists them (by label and target): formtree-sym at 480:14, ended with outcome none;
    # formtree at 480:14, running, of basis formtree, its work in nodes; tilt at 1104:14, ended with no outcome, of
    # basis lindy, its work in seconds; tilt at 2016:15, running, of basis lindy; the clock 75 s after the snapshot.
    # Expectata (dreeves, 2026-11-11: "sounds like obviously yes, that we want to see different searches on the same
    # cell separately"; "what happened to the probability graph?"; "we used to have a progress bar"): the section's
    # line gives the snapshot's time and its age, 1m 15s; one box per search, the running ones first, else in the
    # data's order: formtree 480 14, tilt 2016
    # 15, formtree-sym 480 14, tilt 1104 14, so the two searches at 480:14 each have their own; their states read
    # running, running, completed, aborted.  Every box shows the same parts: the work bar, the ETA chart, the status
    # line, the CPU chart, the runs' line, the dots and the probability graph; none has a pool chart, a stages line
    # or a status key.  Every ETA chart has its three estimates, every CPU chart its bands, every probability graph a
    # line through its three points (none grayed for want of a history), under the prior 0.5.  (The graphs of nodes
    # pending and, since 2026-11-12, evening, of tasks finished are among the parts too: dreeves, "sure, let's get the
    # count of finished tasks over time".)
    r = report(1280)
    assert r['made'] == page.stamp(MADE) and r['age'].replace(' ', ' ') == '1m 15s' and not r['missing'], (r['made'], r['age'], r['missing'])
    boxes = r['boxes']
    assert [(b['label'], b['n'], b['order']) for b in boxes] == [('formtree', '480', '14'), ('tilt', '2016', '15'), ('formtree-sym', '480', '14'),
                                                                ('tilt', '1104', '14')], boxes
    assert [b['state'] for b in boxes] == [['running'], ['running'], ['completed'], ['aborted']], [b['state'] for b in boxes]
    for b in boxes:
        assert all(b['parts'].values()) and b['extras'] == 0, (b['label'], b['parts'], b['extras'])
        assert (b['etaPoints'], b['oddsPoints'], b['oddsEmpty'], b['prior'], b['canvas']) == (3, 3, False, '0.5', True) and b['cpuBands'] >= 3, b
    assert r['width'] <= 1280, r['width']


def q_each_box_graphs_its_nodes_pending():
    # Replicata: the same page, at 1280 px: formtree's estimates count 700, 740 and 760 nodes pending; the completed
    # formtree-sym's 30, 10 and 0; the two tilt searches' none (lindy.py's estimates count no nodes).
    # Expectata (dreeves, 2026-11-12: "we used to have number of open nodes as a graph. is there a reason we can't have
    # that on the currently running 480:14 search?"; a fanout run's pool chart showed its boxes pending or running from
    # 2026-11-03 until the page's revamp of 2026-11-11): every box has the graph, under its CPU chart; the two form
    # trees' a line through their three points, each at the x of the ETA chart's record of the same estimate (the
    # graphs share their x axis, hours of running, as the CPU chart does), formtree-sym's last point on the axis (0
    # pending: its tree closed), on round count ticks from 0 whose last is at least the most pending; the tilt
    # searches' with no line and no point, grayed (data-empty, its svg's opacity below 1), as a graph without data is.
    r = report(1280)
    tree, tilt, sym, old = r['boxes']
    xs = dict(zip(('tree', 'tilt', 'sym', 'old'), r['etaXs']))
    for name, b, most in (('tree', tree, 760), ('sym', sym, 30)):
        p = b['pending']
        assert not p['empty'] and p['opacity'] == 1 and len(p['line']) == 3, (name, p)
        assert all(abs(x - want) < 0.05 for (x, _), want in zip(p['line'], xs[name])), (name, p['line'], xs[name])
        ticks = [float(t.replace(',', '')) if t[-1].isdigit() else t for t, _ in p['ticks']]
        assert p['ticks'][0][0] == '0', (name, p['ticks'])
    assert abs(sym['pending']['line'][-1][1] - sym['pending']['axis']) < 0.05, (sym['pending']['line'], sym['pending']['axis'])
    assert tree['pending']['line'][0][1] > tree['pending']['line'][-1][1], tree['pending']['line']   # 700 below 760: lower on the page is fewer
    for b in (tilt, old):
        assert b['pending']['empty'] and b['pending']['opacity'] < 1 and b['pending']['line'] == [], (b['label'], b['pending'])


def q_each_box_graphs_its_tasks_finished():
    # Replicata: the same page, at 1280 px: formtree's estimates count 3000, 3600 and 4100 tasks finished; the completed
    # formtree-sym's 120, 160 and 170; the two tilt searches' none (lindy.py's estimates count no tasks).
    # Expectata (Opus 5.5, 2026-11-12, evening; dreeves, of the form tree's tasks, each ended with its subtree closed or
    # its unfinished branches spilled to the queue: "sure, let's get the count of finished tasks over time"): every box
    # has the graph, under its graph of nodes pending, drawn as that one is: the two form trees' a line through their
    # three points, each at the x of the ETA chart's record of the same estimate (the graphs share their x axis), rising
    # (more tasks are higher on the page), on round count ticks from 0 whose last is at least the most finished; the
    # tilt searches' with no line and no point, grayed (data-empty, its svg's opacity below 1), as a graph without data
    # is.  Its points' x positions are the layout's finishedXs.
    # Resultata before: no such graph.
    r = report(1280)
    tree, tilt, sym, old = r['boxes']
    xs = dict(zip(('tree', 'tilt', 'sym', 'old'), r['etaXs']))
    for name, b, most in (('tree', tree, 4100), ('sym', sym, 170)):
        f = b['finished']
        assert not f['empty'] and f['opacity'] == 1 and len(f['line']) == 3, (name, f)
        assert all(abs(x - want) < 0.05 for (x, _), want in zip(f['line'], xs[name])), (name, f['line'], xs[name])
        assert f['line'][0][1] > f['line'][1][1] > f['line'][2][1], (name, f['line'])       # rising: lower on the page is fewer
        values = [float(t.replace(',', '').replace('K', 'e3')) for t, _ in f['ticks']]
        assert f['ticks'][0][0] == '0' and values[-1] >= most, (name, f['ticks'])
    assert [[round(x, 2) for x, _ in b['finished']['line']] for b in (tree, sym)] == [[round(x, 2) for x in r['finishedXs'][i]] for i in (0, 2)], r['finishedXs']
    for b in (tilt, old):
        assert b['finished']['empty'] and b['finished']['opacity'] < 1 and b['finished']['line'] == [], (b['label'], b['finished'])


def q_each_graph_s_title_is_above_it_its_numbers_below_in_one_size():
    # Replicata: the same page, at 1280 px and at 390 px: every box's words of its graphs.
    # Expectata (dreeves, 2026-11-12: "could you improve the consistency of the graphs a little? font sizes and whether
    # graphs are labeled above or below the graph"; that day he titled the nodes pending's graph "Pending nodes vs
    # time:", over it, as the probability graph's title is): each graph's title over it, ending in a colon that points
    # down to it: the CPU key ("CPU usage: ..."; under its chart until then) over the CPU chart, the nodes pending's
    # title over theirs, the runs' counts over the dots, the prior and the title over the probability graph; each
    # graph's numbers under it: the bar's caption under the bar, the status line under the ETA chart, the dots' hint
    # under the dots; and the tip, which reads out the estimate under the pointer, over the ETA chart.  All of them, and
    # the note on Lindy's rule, in one font size, that of the page's other figures' words, Figure 1's readout and legend
    # (dreeves, that afternoon, of the bar caption's size, 0.85rem, which they had taken that noon: "the fonts seem overly
    # shrunk compared to the rest of the page's text"; until that noon the status line, the tip, the runs' counts, the
    # hint, the titles and the note were in the body's size); the tip, its time gone to the x axis, one line, as high
    # as the status line.  The ETA, CPU and pending charts' x axes labeled alike, the same hours (they share the axis);
    # the axis labels of all of them and of the bar in one size (the CPU and pending charts' were unlabeled until then).
    # And (that evening) the graph of tasks finished as the pending one: its title over it, in that size, and its x axis
    # labeled with the same hours, in the same size.
    for width in (1280, 390):
        r = report(width)
        for b, w in zip(r['boxes'], r['words']):
            assert all(w['below'].values()) and all(w['above'].values()), (width, b['label'], w['below'], w['above'])
            assert set(w['sizes'].values()) == {r['figureText']}, (width, b['label'], w['sizes'], r['figureText'])
            assert w['ticks'][1] == w['ticks'][2] == w['ticks'][3] == w['ticks'][4] and len(w['ticks'][1]) >= 2, (width, b['label'], w['ticks'])
            assert len(set(w['tickSizes'])) == 1, (width, b['label'], w['tickSizes'])
        assert all(abs(w['tipHeight'] - w['statusHeight']) < 1 for w in r['words'][:1]), (width, r['words'][0]['tipHeight'], r['words'][0]['statusHeight'])


def q_graphs_span_the_column_and_end_at_the_projected_finish():
    # Replicata: the same page, at 1280 px and at 390 px: the running form tree's box.
    # Expectata (dreeves, 2026-11-12: "could the graphs use more of the available horizontal space? no indenting, for one
    # thing. and we could see a bit more detail if we weren't as zoomed out on the x-axis. how about end the x-axis range
    # right at the purple dashed vertical line?"): its graphs as wide as Figure 1, the page's column (until then the
    # section stopped at the text's measure, 46rem of 62rem); every graph's plot from its left edge, with no indent: its
    # axis line from 0, its y labels inside it, starting at its left edge (until then they stood in a margin of 48 of its
    # 640 units); the ETA chart's x axis ending at the purple dashed line, the projected finish: the guide's vertical at
    # the axis's right end (until then the axis ran on to the next round tick), and the CPU and pending charts, which
    # share that axis, ending there too.  And each chart drawn in CSS px, its drawing as wide and as high as it shows, so
    # that its text and margins are the sizes they say at every width (until then 640 units across: once the charts were
    # as wide as the column, its 12px labels showed at 18px, and on a phone at 7px).
    # Spec change (Opus 5.5, 2026-11-12, later; dreeves, of the value labels inside the plot: "is that standard at all to
    # put the [y]-axis annotations to the right of the [y]-axis? or were you just taking me extremely literally?", then,
    # of a proposal to drop the y axis line: "i'm guessing the axis break slashes will make no visual sense without an axis
    # line"): every graph's value labels outside its plot again, right-aligned in a margin at its left no wider than 40,
    # their right ends 6 short of its y axis, none cut off at the chart's left edge; each graph's y axis line at the
    # margin's edge, m, where its x axis starts, the same in all four graphs (the CPU and nodes pending graphs had none
    # until then); the ETA chart's slashes, shown (this box's bands break its axis), each across that line; and every
    # hour label centered on its tick, the first too.  Until then each plot started at x 0, its value labels inside it,
    # each starting 2 right of its left edge, and the first hour label started at its tick.  (And that evening the
    # graph of tasks finished, the fifth, as the others: its axes, labels and scale, and its x axis ending with the CPU
    # and pending charts' at the projected finish.)
    for width in (1280, 390):
        r = report(width)
        sp = r['span']
        assert abs(sp['svg'] - sp['column']) < 1, (width, sp['svg'], sp['column'])
        m = sp['axes']['eta'][0]
        assert 0 < m <= 40 and all(x1 == m for x1, _ in sp['axes'].values()), (width, sp['axes'])
        assert all(ys and all(a == b == m for a, b in ys) for ys in sp['yaxes'].values()), (width, sp['yaxes'])
        assert len(sp['breaks']) == 2 and all(a < m < b and shown == 'visible' for a, b, shown in sp['breaks']), (width, sp['breaks'])
        assert sp['ylabels'] and all(anchor == 'end' and x <= m - 6 and left >= 0 and right <= m for x, anchor, left, right in sp['ylabels']), (width, sp['ylabels'])
        assert sp['xanchors'] and set(sp['xanchors']) == {'middle'}, (width, sp['xanchors'])
        right = sp['axes']['eta'][1]
        assert [x for x, _ in sp['guide'][1:]] == [right, right] and sp['axes']['cpu'][1] == sp['axes']['pending'][1] == sp['axes']['finished'][1] == right, (width, sp['guide'], sp['axes'])
        assert all(abs(vw - w) < 1 and abs(vh - h) < 1 for vw, w, vh, h in sp['scale']), (width, sp['scale'])


def q_hovering_floats_the_time_on_the_x_axis():
    # Replicata: the same page at 1280 px; the pointer over the running form tree's ETA chart at its second estimate,
    # then away; over its CPU chart in its first row, then away; over its nodes pending at their second point, then away;
    # over its probability graph at its second point, then away.
    # Expectata (dreeves, 2026-11-12: "the wrapping in this screenshot is a little awkward; what if we showed the
    # timestamp more subtly and showed it floating on the x-axis matched up with the dashed vertical line on the graph
    # marking the timestamp in question that we're hovering over?"): in each chart the time under the pointer shows on
    # its x axis, on the row of its hour labels, on the dashed line: centered on it, but within the chart, where a point
    # is near its edge (since that day the plot starts at the chart's left edge); a box under it, the paper's color, a
    # little wider than the text, so that it covers the labels it sits on: over the ETA chart the estimate's clock time, over the CPU
    # chart its row's end, over the nodes pending and over the probability graph their point's (the probability graph
    # since that afternoon; dreeves: "should we have the same hover effect on all graphs consistently? it's missing on
    # the probability graph"), each local, to the minute (YYYY-MM-DD HH:MM); and away, none shows.  The tip over the ETA chart reads out the estimate without its time (no @, not the time on the
    # axis; its finish times stay, the later a date, as every line gives them), from its time so far on; the CPU key
    # has no time.  (And that evening, over the graph of tasks finished at its second point, its point's time, as the
    # pending one's.)
    r = report(1280)
    local = lambda t: time.strftime('%Y-%m-%d %H:%M', time.localtime(t))
    h = r['hovers']
    want = dict(eta=local(TREE['etas'][1][0]), cpu=local(TREE['cpu'][0][2]), pending=local(TREE['pending'][1][0]),
                finished=local(TREE['finished'][1][0]), odds=local(TREE['odds']['exists'][1][0]))
    assert sorted(h) == sorted(want), sorted(h)
    for name, got in h.items():
        assert got['shown'] and got['text'] == want[name], (name, got, want[name])
        x0, w = got['box']
        assert abs(got['y'] - got['tickY']) < 0.5 and abs(x0 + w / 2 - got['x']) < 0.5 and w > 40, (name, got)
        assert x0 <= got['cross'] <= x0 + w and 0 <= x0 and x0 + w <= got['width'], (name, got)   # on the line, within the chart
        assert not got['after']['shown'], (name, got)
    assert re.match(r'\d+h\s\d+m\s\d+s \+ ', h['eta']['tip']) and '@' not in h['eta']['tip'] and want['eta'] not in h['eta']['tip'], h['eta']['tip']
    assert '@' not in h['cpu']['cpu'] and want['cpu'] not in h['cpu']['cpu'], h['cpu']['cpu']


def q_the_prior_line_says_the_probability_now():
    # Replicata: the page 1280 px wide with SEARCHES: each box's prior line, from its prior's number on; then a hover over
    # the running form tree's probability graph at its first point, then away.
    # Expectata (dreeves, 2026-11-13: "for "Prior probability a bipartition exists: 0.5" append a right arrow and then the
    # current probability, and have it update on hover for the graph"): each line ends with its prior, an arrow and its
    # search's latest P(exists), to 2 significant figures (its prior where it has no point); over a point of the graph,
    # that point's P(exists); away, the latest again.  The line's words before the prior are not read.
    # Resultata before: the line ended with the prior.  (The numbers are compared as numbers: JS and Python write some
    # differently, 0.000012 and 1.2e-05.)
    r = report(1280)
    two = lambda p: float(format(p, '.2g'))   # to 2 significant figures
    runs = [x for x in SEARCHES['runs'] if x['state'] == 'running'] + [x for x in SEARCHES['runs'] if x['state'] != 'running']   # the boxes' order
    tails = [b['oddsTail'].split(' → ') for b in r['boxes']]
    assert len(tails) == len(runs) and all(len(t) == 2 for t in tails), tails
    want = [(e['odds']['prior'], two([e['odds']['prior'], *[p for _, p in e['odds']['exists']]][-1])) for e in runs]
    assert [(float(a), float(b)) for a, b in tails] == want, (tails, want)
    first, last, h = two(TREE['odds']['exists'][0][1]), two(TREE['odds']['exists'][-1][1]), r['oddsFirst']   # TREE: the first box
    assert first != last and (float(h['now']), float(h['after']['now'])) == (first, last), (first, last, h['now'], h['after']['now'])


# a search whose last run to stop was paused (track.py pause, 2026-11-13), as the watcher writes it: 480:14's form tree of
# four runs, each stopped to be resumed
PAUSED = entry('formtree-p', 480, 14, 'paused', None, 'formtree', dict(unit='nodes', done=4200000, rate=510.25, total=band(9.1e7, 2.2e7, 4.1e8)),
               11000.0, band(170000.0, 35000.0, 800000.0), dict(runs=4, running=0, frozen=0, ended=0, aborted=0, paused=4, found=0), '2222',
               [0.49, 0.485, 0.48], [700, 740, 760], [3000, 3600, 4100])


def q_a_paused_search_says_paused():
    # Replicata: the page 1280 px wide with SEARCHES and a fifth search, PAUSED: formtree-p at 480:14, as the watcher
    # writes a search whose last run to stop was paused (track.py pause): state paused, outcome null, its four runs
    # paused, its dots "2222".
    # Expectata (dreeves, 2026-11-13, of the 480:14 form tree, stopped that morning to free the cores and queued to
    # resume: "should 480:14 formtree say "paused" rather than "aborted"?", then "go ahead and generalize track.py to
    # record pause vs abort or whatever"): its box's state reads paused; its status line is the paused form, "Paused
    # after running for" its time; its runs line counts its paused runs, 4, so that its counts add up to its runs; and
    # the dots' hint, which names each color, names the paused runs beside the frozen ones, the color they share.
    # Resultata before: the runs line had no count of paused runs, and the hint named the pending color frozen alone.
    r = render(1280, dict(SEARCHES, runs=SEARCHES['runs'] + [PAUSED]))
    box = next(b for b in r['boxes'] if b['label'] == 'formtree-p')
    assert box['state'] == ['paused'], box['state']
    assert len(box['status']) == 1 and box['status'][0].startswith('Paused after running for '), box['status']
    assert re.search(r'\b4 runs: 0 running, 0 frozen, 0 ended, 0 aborted, 4 paused; 0 found\b', box['runsLine']), box['runsLine']
    assert re.search(r'frozen or paused', box['hint']), box['hint']


def q_the_bar_measures_each_search_s_work_in_its_unit():
    # Replicata: the same page, at 1280 px and at 390 px (a phone's).
    # Expectata: formtree's bar counts nodes: its caption reads "4,200,000 nodes checked (510.3 nodes/s) / ~22M–410M"
    # (the nodes exact, the rate to a tenth, the total's band compact), its ticks are round numbers of nodes from 0
    # (0, 100M, ...); tilt's counts its time, the only work a search that knows nothing but its age can count: "1h 0m
    # 0s time spent / ~" and its total's band as durations, with no word of nodes, its ticks in hours from 0, the last
    # with its unit.  In each, to a CSS px: the blue part runs from the track's left end to done / end of the track
    # (end the last tick's value), the band from the total's lo to its hi, the median's tick at its median; the
    # completed formtree-sym's bar is blue to its total, 145,427 nodes, where the band has no width.  No sideways
    # scroll at either width.
    for width in (1280, 390):
        r = report(width)
        tree, tilt, sym, old = r['boxes']
        text = lambda s: s.replace(' ', ' ')
        # (2026-11-12: the captions' numbers, not their words, which are dreeves's to change: he made "/ ~" "of ~" that day)
        assert numbers(tree['caption']) == ['4,200,000', '510.3', '22M–410M'], tree['caption']
        assert 'nodes' not in tilt['caption'] and numbers(tilt['caption']) in (['1', '0', '0', '1–10'], ['1', '0', '0', '1.1–10']), tilt['caption']
        assert tree['ticks'][0] == '0' and tree['ticks'][1] == '100M' and tilt['ticks'][0] == '0' and text(tilt['ticks'][-1]).endswith(' h'), (tree['ticks'], tilt['ticks'])
        value = lambda label: float(re.fullmatch(r'([0-9.]+)([KMBT]?)', label)[1]) * {'': 1, 'K': 1e3, 'M': 1e6, 'B': 1e9, 'T': 1e12}[re.fullmatch(r'([0-9.]+)([KMBT]?)', label)[2]]
        hours = lambda label: float(text(label).removesuffix(' h')) * 3600
        for b, e, end in [(tree, TREE, value(tree['ticks'][-1])), (sym, SYM, value(sym['ticks'][-1])), (tilt, TILT, hours(tilt['ticks'][-1])),
                          (old, OLDTILT, hours(old['ticks'][-1]))]:
            work, x0, W = e['work'], b['bar']['x'], b['bar']['width']
            at = lambda v: x0 + W * v / end
            assert end >= 1.1 * work['total']['hi'] and abs(b['done']['x'] - x0) <= 1 and abs(b['done']['right'] - at(work['done'])) <= 1, (b['label'], b['done'], end)
            assert abs(b['band']['x'] - at(work['total']['lo'])) <= 1 and abs(b['band']['right'] - at(work['total']['hi'])) <= 1, (b['label'], b['band'])
            assert abs((b['median']['x'] + b['median']['right']) / 2 - at(work['total']['median'])) <= 1, (b['label'], b['median'])
        assert text(sym['caption']).startswith('145,427 nodes checked (35.5 nodes/s)') and sym['band']['width'] <= 1, (sym['caption'], sym['band'])
        assert r['width'] <= width, (width, r['width'])


def q_each_box_s_words_follow_its_search_s_data():
    # Replicata: the same page at 1280 px.
    # Expectata: each box's status line is its state's form alone: the running ones' gives the time so far (it goes on
    # with the clock: formtree's 3h 3m 20s at the snapshot, 75 s more by the page's clock) and the time to go; the
    # ended ones' say completed or aborted after their time.  The runs' line counts the search's runs by state, in
    # the data's numbers (formtree: 4 runs, 1 running, 0 frozen, 2 ended, 1 aborted, 0 found), and the dots' hint is
    # the one for a dot per run.  The note that the ETA is Lindy's rule alone shows for the running search of basis
    # lindy and for no other: not for the form tree's, which has an estimate of its own, nor for the ended tilt.
    r = report(1280)
    tree, tilt, sym, old = r['boxes']
    text = lambda s: s.replace(' ', ' ')
    assert len(tree['status']) == len(tilt['status']) == len(sym['status']) == len(old['status']) == 1, [b['status'] for b in r['boxes']]
    assert text(tree['status'][0]).startswith('3h 4m 35s + ') and 'to go' in tree['status'][0], tree['status']
    assert text(sym['status'][0]).startswith('Completed after running for 1h 8m 20s') and text(old['status'][0]).startswith('Aborted after running for 25m 0s'), (sym['status'], old['status'])
    # (Spec change, Fable 5.2, 2026-11-13: the line counts the paused runs too, after the aborted; searchwatch/track.py pause;
    # dreeves: "go ahead and generalize track.py to record pause vs abort or whatever".)
    assert re.match(r'4 runs: 1 running, 0 frozen, 2 ended, 1 aborted, 0 paused; 0 found; running\.', tree['runsLine']), tree['runsLine']
    assert re.match(r'2 runs: 2 running, 0 frozen, 0 ended, 0 aborted, 0 paused; 0 found; running\.', tilt['runsLine']), tilt['runsLine']
    assert all(b['hint'].startswith('One dot per run') for b in r['boxes']), [b['hint'] for b in r['boxes']]
    assert [b['lindy'] for b in r['boxes']] == [False, True, False, False], [b['lindy'] for b in r['boxes']]


def q_a_cell_s_box_briefs_its_searches():
    # Replicata: the same page; then what the section answers when a chart's box asks for the runs at 480:14
    # (progressView.want(480n, 14, put)), and at 7:3, where there is none.
    # Expectata: at 480:14 a brief of each of the two searches there, in the data's order, each its heading, its
    # state and its time so far, then, their work being counted in nodes, the bar's caption: formtree-sym's, then
    # "m*(480) ≥ 14? formtree running 3h 3m 20s" and "4,200,000 nodes checked (510.3 nodes/s) / ~22M–410M", and no
    # more.  At 7:3, an em dash alone.
    r = report(1280)
    text = [s.replace(' ', ' ') for s in r['briefs']]
    assert re.fullmatch(r'm\*\(480\) ≥ 14\? formtree-sym completed 1h 8m 20s', text[0]) and text[1].startswith('145,427 nodes checked'), text
    assert re.fullmatch(r'm\*\(480\) ≥ 14\? formtree running 3h 3m 20s', text[2]), text
    assert numbers(text[3]) == ['4,200,000', '510.3', '22M–410M'], text   # its numbers, not its words (2026-11-12)
    assert len(text) == 4, text
    assert r['none'] == ['—'], r['none']


def q_a_page_without_the_data_file_says_so():
    # Replicata: the page at 1280 px with no pagedata/progress.js.
    # Expectata: the line that says the data file did not load shows, the snapshot's line has no time, and there is
    # no search's box.
    r = render(1280, None)
    assert r['missing'] and r['made'] == '—' and r['boxes'] == [], r


def main():
    names = sys.argv[1:] or [n for n in globals() if n.startswith('q_')]
    failed = 0
    for n in names:
        t0 = time.time()
        try:
            globals()[n]()
            # TODO: runner line; says the named qual passed, with its seconds
            print(f'Claude: "PASSED" {n} ({time.time() - t0:.1f} s)', flush=True)
        except Exception:
            failed += 1
            # TODO: runner line; says the named qual failed, with its seconds, followed by the traceback
            print(f'Claude: "FAILED" {n} ({time.time() - t0:.1f} s)\n' + traceback.format_exc(), flush=True)
    # TODO: runner summary; says how many quals passed out of how many
    print(f'Claude: "{len(names) - failed} of {len(names)} passed"')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
