#!/usr/bin/env python3
"""Cell summaries reuse search information without rendering discarded graphs."""
import sys
sys.dont_write_bytecode = True
import quals_searches_page as searches


def q_cell_briefs_do_no_graph_drawing():
    # Replicata: load the actual dashboard, then request summaries for node-counted and time-counted searches.
    # Expectata: the existing summary content, without drawing any canvas or creating SVG geometry, and without
    # redrawing the dashboard. A text-only popover must not pay for the search's entire chart history.
    # Resultata: each matching search draws a discarded canvas and five discarded graphs.
    original = searches.HARNESS
    before = '''    await document.fonts.ready;
    await sleep(350);  // let an unrelated pending font-layout check finish before counting summary work
    const briefWork = {canvas: 0, svg: 0, renders: window.progressView.renders};
    const getContext = HTMLCanvasElement.prototype.getContext, createSVG = document.createElementNS;
    HTMLCanvasElement.prototype.getContext = function(...args) {
      briefWork.canvas++;
      return getContext.apply(this, args);
    };
    document.createElementNS = function(ns, ...args) {
      briefWork.svg += ns === 'http://www.w3.org/2000/svg';
      return createSVG.call(this, ns, ...args);
    };
'''
    after = '''    const secondsBrief = await new Promise(done => window.progressView.want(2016n, 15, done));
    HTMLCanvasElement.prototype.getContext = getContext;
    document.createElementNS = createSVG;
    briefWork.renders = window.progressView.renders-briefWork.renders;
    result.briefWork = briefWork;
    result.secondsRows = secondsBrief.length;
'''
    needle = "    const wants = await new Promise(done => window.progressView.want(480n, 14, nodes => done(nodes)));"
    assert original.count(needle) == 1
    searches.HARNESS = original.replace(needle, before+needle+'\n'+after)
    try:
        result = searches.render(1280)
        assert len(result['briefs']) == 4 and result['secondsRows'] == 2, result
        assert result['briefWork'] == dict(canvas=0, svg=0, renders=0), result['briefWork']
    finally:
        searches.HARNESS = original


if __name__ == '__main__':
    q_cell_briefs_do_no_graph_drawing()
    print('1 qual passed')
