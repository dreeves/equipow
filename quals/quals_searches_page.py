#!/usr/bin/env python3
"""Fable 5.2's quals for the tracked searches' boxes in index.html's section "Search progress", in the real page in
headless Chrome (2026-11-11; dreeves: "sounds like obviously yes, that we want to see different searches on the same
cell separately", "what happened to the probability graph?", "we used to have a progress bar", and "the search
progress code seems like a shitshow; can you revamp it? ... anti-magic anti-magic anti-magic").  Run from the repo:
    python3 -B quals/quals_searches_page.py [name ...]
Each qual is a function q_*: a passing qual returns, a failing one raises; each comment gives its replicata and
expectata; a failure's message or traceback gives the resultata.  The page is given a made-up pagedata/searches.js
(SEARCHES: entries as searchwatch/watch.py writes them) beside the earlier runs' progress.js (quals_index's).
"""
import sys
sys.dont_write_bytecode = True
import copy, html, json, os, re, shutil, tempfile, time, traceback
from pathlib import Path
import quals_index as page

MADE = 1794450000
band = lambda m, lo, hi: dict(median=m, lo=lo, hi=hi)


def entry(search, n, order, state, outcome, basis, work, so_far, to_go, runs, dots, exists):
    """An entry as watch.py writes it: three estimates, the last at MADE."""
    times = [MADE - 600, MADE - 300, MADE]
    return dict(search=search, n=n, order=order, state=state, outcome=outcome, so_far=so_far, runs=runs,
                statuses=['settled', 'open', 'pending', 'running'], depth=0, keys=[f'{n}:{order}'], groups=[dots],
                counts={s: dots.count(str(i)) for i, s in enumerate(['settled', 'open', 'pending', 'running'])},
                to_go=to_go, basis=basis, work=work,
                etas=[[t, so_far - (MADE - t), to_go['median'] + (MADE - t), to_go['lo'] + (MADE - t), to_go['hi'] + (MADE - t)] for t in times],
                odds=dict(prior=0.5, since=MADE - so_far, exists=[[t, p] for t, p in zip(times, exists)]),
                cpu=[[(so_far - 120) / 3600, (so_far - 60) / 3600, MADE - 60, 0.6, 0.3, 0.1], [(so_far - 60) / 3600, so_far / 3600, MADE, 0.7, 0.2, 0.1]],
                stale=None)


TREE = entry('formtree', 480, 14, 'running', None, 'formtree', dict(unit='nodes', done=4200000, rate=510.25, total=band(9.1e7, 2.2e7, 4.1e8)),
             11000.0, band(170000.0, 35000.0, 800000.0), dict(runs=4, running=1, frozen=0, ended=2, aborted=1, found=0), '0103', [0.49, 0.485, 0.48])
TILT = entry('tilt', 2016, 15, 'running', None, 'lindy', dict(unit='seconds', done=3600.0, rate=1.0, total=band(7200.0, 4000.0, 36000.0)),
             3600.0, band(3600.0, 400.0, 32400.0), dict(runs=2, running=2, frozen=0, ended=0, aborted=0, found=0), '33', [0.5, 0.5, 0.5])
SYM = entry('formtree-sym', 480, 14, 'ended', 'none', 'formtree', dict(unit='nodes', done=145427, rate=35.5, total=band(145427, 145427, 145427)),
            4100.0, band(0.0, 0.0, 0.0), dict(runs=4, running=0, frozen=0, ended=2, aborted=2, found=0), '1100', [0.3, 0.1, 0.0])
OLDTILT = dict(entry('tilt', 1104, 14, 'ended', None, 'lindy', dict(unit='seconds', done=1500.0, rate=1.0, total=band(3000.0, 1666.0, 15000.0)),
                     1500.0, band(1500.0, 166.0, 13500.0), dict(runs=3, running=0, frozen=0, ended=2, aborted=1, found=0), '001', [0.5, 0.5, 0.5]))
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
      const settled = window.progressView.searches.made || !section.querySelector('.progress-missing-searches').hidden;
      quiet = window.progressView.data && settled && !document.head.querySelector('script[src^="pagedata/"]') ? quiet + 1 : 0;
    }
    if (quiet < 3) throw Error('snapshot');
    for (const d of section.querySelectorAll('.progress-searches .progress-run details')) d.open = true;
    await sleep(100);
    const shown = e => !!e && e.checkVisibility();
    const rect = e => { const r = e.getBoundingClientRect(); return {x: r.x, width: r.width, right: r.right}; };
    result.made = section.querySelector('[data-searches-made]').textContent;
    result.age = section.querySelector('[data-searches-age]').textContent;
    result.missing = shown(section.querySelector('.progress-missing-searches'));
    result.before = !!(section.querySelector('.progress-searches').compareDocumentPosition(section.querySelector('.progress-runs')) & Node.DOCUMENT_POSITION_FOLLOWING);
    result.earlier = section.querySelectorAll('.progress-runs .progress-run').length;
    result.boxes = [...section.querySelectorAll('.progress-searches .progress-run')].map(box => {
      const q = s => box.querySelector(s), part = name => q(`[data-bar="${name}"]`);
      return {
        label: q('[data-program]').textContent, n: q('[data-n]').textContent, order: q('[data-order]').textContent,
        state: [...box.querySelectorAll('.progress-run-state [data-label]')].filter(shown).map(e => e.dataset.label),
        parts: {bar: shown(q('.progress-work')), eta: shown(q('.progress-eta svg')), status: shown(q('.progress-status')), cpu: shown(q('.progress-cpu svg')),
                runs: shown(q('[data-track-line]')), dots: shown(q('canvas')), odds: shown(q('.progress-odds svg'))},
        extras: box.querySelectorAll('.progress-pool, [data-stages], .progress-key').length,
        lindy: shown(q('[data-lindy]')),
        caption: q('.progress-bar-caption').textContent.replace(/\s+/g, ' ').trim(),
        bar: rect(q('.progress-bar')), done: rect(part('done')), band: rect(part('band')), median: rect(part('median')),
        ticks: [...q('[data-bar="ticks"]').children].map(e => e.textContent),
        status: [...box.querySelectorAll('.progress-status [data-state]')].filter(shown).map(e => e.innerText.replace(/\s+/g, ' ').trim()),
        runsLine: q('[data-track-line]').textContent.replace(/\s+/g, ' ').trim(),
        hint: q('[data-readout]').textContent.replace(/\s+/g, ' ').trim(),
        prior: q('[data-odds-prior]').textContent,
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
    result.width = document.documentElement.scrollWidth;
  } catch (e) { result.error = String(e.stack || e); }
  parent.postMessage(JSON.stringify(result), '*');
})();
</script>"""


def render(width, searches=SEARCHES):
    """The harness's report on the page at width (CSS px), in an iframe (page.HOST), with searches as its searches.js
    (None: no such file)."""
    with tempfile.TemporaryDirectory(prefix='searches-page-quals-') as d:
        source = page.page().replace('<head>\n', '<head>\n' + page.PROGRESS_REMEMBERED + f'<script>window.PROGRESS_CLOCK = () => {MADE + 75};</script>\n')
        Path(d, 'index.html').write_text(source.replace('</body>', HARNESS + '</body>'))
        page.copy_page_dir(d)
        shutil.copy(page.DATA, page.data_file(d, 'mstar.js'))
        shutil.copy(page.POW2, page.data_file(d, 'pow2.js'))
        Path(page.data_file(d, 'progress.js')).write_text('progressData(' + json.dumps(copy.deepcopy(page.PROGRESS_DATA)) + ');\n')
        if searches is not None: Path(page.data_file(d, 'searches.js')).write_text('searchesData(' + json.dumps(searches) + ');\n')
        Path(d, 'host.html').write_text(page.HOST.replace('__WIDTH__', str(width)))
        dom = page.chrome(d, [f'--window-size={max(width, 500) + 40},1100', '--force-device-scale-factor=1', '--virtual-time-budget=15000',
                              '--dump-dom', 'file://' + str(Path(d, 'host.html'))])
        found = re.search(r'<pre id="harness-out">(.*?)</pre>', dom, re.S)
        assert found, dom[-2000:]
        result = json.loads(html.unescape(found[1]))
        assert 'error' not in result, result['error']
        return result


REPORTS = {}
def report(width):
    if width not in REPORTS: REPORTS[width] = render(width)
    return REPORTS[width]


def q_every_search_has_its_box_and_every_box_the_same_parts():
    # Replicata: the page, 1280 px wide, its section "Search progress" open, with SEARCHES as pagedata/searches.js,
    # four searches as the watcher lists them (by label and target): formtree-sym at 480:14, ended with outcome none;
    # formtree at 480:14, running, of basis formtree, its work in nodes; tilt at 1104:14, ended with no outcome, of
    # basis lindy, its work in seconds; tilt at 2016:15, running, of basis lindy; and quals_index's data of the
    # earlier runs as progress.js; the clock 75 s after the searches' snapshot.
    # Expectata (dreeves, 2026-11-11: "sounds like obviously yes, that we want to see different searches on the same
    # cell separately"; "what happened to the probability graph?"; "we used to have a progress bar"): the searches'
    # line gives their snapshot's time and its age, 1m 15s; their boxes come before the earlier runs', which are
    # still there; one box per search, the running ones first, else in the data's order: formtree 480 14, tilt 2016
    # 15, formtree-sym 480 14, tilt 1104 14, so the two searches at 480:14 each have their own; their states read
    # running, running, completed, aborted.  Every box shows the same parts: the work bar, the ETA chart, the status
    # line, the CPU chart, the runs' line, the dots and the probability graph; none has a pool chart, a stages line
    # or a status key.  Every ETA chart has its three estimates, every CPU chart its bands, every probability graph a
    # line through its three points (none grayed for want of a history), under the prior 0.5.
    r = report(1280)
    assert r['made'] == page.stamp(MADE) and r['age'].replace(' ', ' ') == '1m 15s' and not r['missing'], (r['made'], r['age'], r['missing'])
    assert r['before'] and r['earlier'] == len(page.PROGRESS_DATA['runs']) > 0, (r['before'], r['earlier'])
    boxes = r['boxes']
    assert [(b['label'], b['n'], b['order']) for b in boxes] == [('formtree', '480', '14'), ('tilt', '2016', '15'), ('formtree-sym', '480', '14'),
                                                                ('tilt', '1104', '14')], boxes
    assert [b['state'] for b in boxes] == [['running'], ['running'], ['completed'], ['aborted']], [b['state'] for b in boxes]
    for b in boxes:
        assert all(b['parts'].values()) and b['extras'] == 0, (b['label'], b['parts'], b['extras'])
        assert (b['etaPoints'], b['oddsPoints'], b['oddsEmpty'], b['prior'], b['canvas']) == (3, 3, False, '0.5', True) and b['cpuBands'] >= 3, b
    assert r['width'] <= 1280, r['width']


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
        assert text(tree['caption']) == '4,200,000 nodes checked (510.3 nodes/s) / ~22M–410M', tree['caption']
        assert text(tilt['caption']).startswith('1h 0m 0s time spent / ~') and 'nodes' not in tilt['caption'], tilt['caption']
        assert re.fullmatch(r'1h 0m 0s time spent / ~1(\.1)?–10 h', text(tilt['caption'])), tilt['caption']
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
    assert re.match(r'4 runs: 1 running, 0 frozen, 2 ended, 1 aborted; 0 found; running\.', tree['runsLine']), tree['runsLine']
    assert re.match(r'2 runs: 2 running, 0 frozen, 0 ended, 0 aborted; 0 found; running\.', tilt['runsLine']), tilt['runsLine']
    assert all(b['hint'].startswith('One dot per run') for b in r['boxes']), [b['hint'] for b in r['boxes']]
    assert [b['lindy'] for b in r['boxes']] == [False, True, False, False], [b['lindy'] for b in r['boxes']]


def q_a_cell_s_box_briefs_its_searches():
    # Replicata: the same page; then what the section answers when a chart's box asks for the runs at 480:14
    # (progressView.want(480n, 14, put)), and at 7:3, where there is none.
    # Expectata: at 480:14 a brief of each of the two tracked searches there, formtree first (it runs), each its
    # heading, its state and its time so far, then, their work being counted in nodes, the bar's caption: "m*(480) ≥
    # 14? formtree running 3h 3m 20s" and "4,200,000 nodes checked (510.3 nodes/s) / ~22M–410M", then formtree-sym's;
    # then the earlier runs' briefs there, if quals_index's data has any.  At 7:3, an em dash alone.
    r = report(1280)
    text = [s.replace(' ', ' ') for s in r['briefs']]
    assert re.fullmatch(r'm\*\(480\) ≥ 14\? formtree running 3h 3m 20s', text[0]), text
    assert text[1] == '4,200,000 nodes checked (510.3 nodes/s) / ~22M–410M', text
    assert re.fullmatch(r'm\*\(480\) ≥ 14\? formtree-sym completed 1h 8m 20s', text[2]) and text[3].startswith('145,427 nodes checked'), text
    earlier = [e for e in page.PROGRESS_DATA['runs'] if (e['n'], e['order']) == (480, 14)]
    assert (len(text) > 4) == bool(earlier), (text, len(earlier))
    assert r['none'] == ['—'], r['none']


def q_a_page_without_the_searches_file_says_so():
    # Replicata: the page at 1280 px with no pagedata/searches.js, the earlier runs' progress.js as before.
    # Expectata: the line that says the searches' file did not load shows, the searches' line has no time, there is
    # no search's box, and the earlier runs' boxes are all there as before.
    r = render(1280, None)
    assert r['missing'] and r['made'] == '—' and r['boxes'] == [] and r['earlier'] == len(page.PROGRESS_DATA['runs']), r


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
