#!/usr/bin/env python3
"""Short search charts retain readable, aligned axes in the actual browser."""
import copy
import sys
sys.dont_write_bytecode = True
import quals_searches_page as searches


def q_short_search_labels_fit_without_changing_their_numbers():
    # Replicata: searches lasting fractions of a second through minutes, including a 27-second Lindy run
    # whose ETA axis labels 0.015 h; open the graphs after they were initially drawn collapsed, then redraw.
    # Expectata: every label fits left of its plot, with six pixels of space, and all five charts align.
    # Resultata: the fixed 40-pixel margin clips a legitimate decimal label and its render assertion throws.
    data = copy.deepcopy(searches.SEARCHES)
    for i, duration in enumerate((.1, 1., 27., 300.)):
        e = searches.entry(f'short-{i}', 2016, 15, 'running', None, 'lindy',
                           dict(unit='seconds', done=duration, rate=1., total=searches.band(2*duration, 1.1*duration, 10*duration)),
                           duration, searches.band(duration, duration/9, 9*duration),
                           dict(runs=1, running=1, frozen=0, ended=0, aborted=0, paused=0, found=0), '3',
                           [.5]*3, [None]*3, [None]*3, [None]*3)
        e['cpu'] = []
        data['runs'].append(e)
    original = searches.HARNESS
    searches.HARNESS = original.replace('    const shown =', '''    await document.fonts.ready;
    const folds = [...section.querySelectorAll('.progress-runs .progress-run details')];
    for (const d of folds) d.open = false;
    window.dispatchEvent(new Event('resize'));
    await sleep(350);
    for (const d of folds) d.open = true;
    for (const d of section.querySelectorAll('.progress-runs .progress-run details')) d.open = true;
    await sleep(100);
    const labels = () => [...section.querySelectorAll('.progress-runs .progress-run')].map(box => ({
      axes: [...box.querySelectorAll('svg line.axis')].map(a => +a.getAttribute('x1')),
      labels: [...box.querySelectorAll('svg text.ytick')].map(t => {
        const b = t.getBBox(), axis = t.ownerSVGElement.querySelector('line.axis');
        return {text: t.textContent, left: b.x, right: b.x+b.width, axis: +axis.getAttribute('x1')};
      })
    }));
    result.labels = labels();
    const font = document.createElement('style');
    font.textContent = '.progress svg text { font-family: monospace; }';
    document.head.appendChild(font);
    const renders = window.progressView.renders;
    document.fonts.dispatchEvent(new Event('loadingdone'));
    await sleep(350);
    result.fontRenders = window.progressView.renders-renders;
    result.fontLabels = labels();
    // A font event arriving during the resize debounce must not cancel the width change.
    const previousWidth = section.clientWidth;
    section.style.width = (previousWidth-20)+'px';
    window.dispatchEvent(new Event('resize'));
    document.fonts.dispatchEvent(new Event('loadingdone'));
    await sleep(350);
    result.resize = [section.querySelector('.progress-runs .progress-eta svg').viewBox.baseVal.width,
                     section.clientWidth, previousWidth];
    const shown =''')
    try:
        for width in (390, 1280):
            report = searches.render(width, data)
            for phase in ('labels', 'fontLabels'):
                labels = [t for box in report[phase] for t in box['labels']]
                assert any(t['text'] == '0.015\u202fh' for t in labels), labels
                assert all(t['left'] >= 0 and t['right'] <= t['axis']-5.9 for t in labels), (width, phase, labels)
                assert all(len(set(box['axes'])) == 1 for box in report[phase]), (width, phase, report[phase])
            assert report['fontRenders'] > 0, (width, 'font metrics changed without redrawing')
            actual, expected, previous = report['resize']
            assert actual == expected < previous, (width, report['resize'])
    finally:
        searches.HARNESS = original


if __name__ == '__main__':
    q_short_search_labels_fit_without_changing_their_numbers()
    print('1 qual passed')
