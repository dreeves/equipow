#!/usr/bin/env python3
"""Chart labels retain their measured margins without a layout pass per label."""
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
import quals_index as page
from quals_pow2_page import GROUP_JS

ROOT = Path(__file__).resolve().parent.parent
LABELS = ['0', '20', '40\u202fh', '8', '10\u202fd', '100%', '0', '200', '400', '600', '800',
          '0', '200', '400', '600', '800', '0', '10', '20', '30', '40', '50%']
CASES = [LABELS, ['0', '0.005', '0.01', '0.015\u202fh'], ['0', '0.0001', '0.0002', '0.0003\u202fh'],
         ['0', '10K', '100K', '1M'], ['0', '0.05', '0.1', '0.15%']]

DRIVER = r"""
import {spawn} from 'node:child_process';
import {existsSync,readFileSync} from 'node:fs';
const C=JSON.parse(readFileSync(0,'utf8'));
""" + GROUP_JS + r"""
const chrome=spawn(C.chrome,[...C.headless,'--remote-debugging-port=0',`--user-data-dir=${C.dir}/profile`,'about:blank'],
                   {stdio:'ignore',detached:true});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let ws,seq=0;
const pending=new Map();
const send=(method,params={})=>new Promise((ok,no)=>{
  const id=++seq; pending.set(id,d=>d.error?no(Error(JSON.stringify(d.error))):ok(d.result));
  ws.send(JSON.stringify({id,method,params}));
});
const evaluate=async expression=>{
  const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
  if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));
  return r.result.value;
};
const metrics=async()=>Object.fromEntries((await send('Performance.getMetrics')).metrics.map(m=>[m.name,m.value]));
const watchdog=setTimeout(()=>{groupSignal(chrome.pid,'SIGTERM');process.exit(3);},60000);
try {
  const file=`${C.dir}/profile/DevToolsActivePort`;
  while(!existsSync(file))await sleep(20);
  const port=readFileSync(file,'utf8').split('\n')[0];
  const targets=await(await fetch(`http://localhost:${port}/json/list`)).json();
  ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
  await new Promise(r=>ws.addEventListener('open',r,{once:true}));
  ws.addEventListener('message',e=>{const d=JSON.parse(e.data);if(d.id){pending.get(d.id)(d);pending.delete(d.id);}});
  await send('Performance.enable');
  await send('Page.navigate',{url:C.url});
  while(!(await evaluate('typeof window.margin === "function"')))await sleep(20);
  await evaluate('document.fonts.ready.then(()=>document.body.offsetWidth)');
  const results=[];
  for(const family of ['serif','monospace']){
    await evaluate(`section.style.fontFamily=${JSON.stringify(family)};document.body.offsetWidth`);
    const contract=await evaluate(`(${function(cases){
      return cases.map(labels=>{
        const margin=window.margin(labels);
        const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
        svg.setAttribute('class','progress-eta');
        const labelsInPage=labels.map(label=>{
          const t=document.createElementNS('http://www.w3.org/2000/svg','text');
          t.textContent=label;svg.append(t);return t;
        });
        section.append(svg);
        const widths=labelsInPage.map(t=>t.getComputedTextLength());
        svg.remove();
        return {margin,widths};
      });
    }})(${JSON.stringify(C.cases)})`);
    await evaluate('document.body.offsetWidth');
    const before=await metrics();
    const measurements=await evaluate(`Array.from({length:${C.repeats}},()=>window.margin(${JSON.stringify(C.labels)}))`);
    const after=await metrics();
    results.push({family,contract,measurements,layouts:after.LayoutCount-before.LayoutCount,
                  layoutSeconds:after.LayoutDuration-before.LayoutDuration,
                  scriptSeconds:after.ScriptDuration-before.ScriptDuration});
  }
  process.stdout.write(JSON.stringify({repeats:C.repeats,labelCount:C.labels.length,results})+'\n');
} finally {
  clearTimeout(watchdog);ws?.close();await endGroup(chrome.pid);
}
"""


def measured():
    """Run the production measurement function with the actual page CSS and Chrome's layout counters."""
    script = (ROOT/'page/progress-section.js').read_text()
    pieces = [re.search(pattern, script).group(0) for pattern in (
        r"  const assert = .*", r"  const NS = .*", r"  const set = .*", r"  const make = .*",
        r"  const ETA_L = .*", r"  const chartWidth = .*", r"  function chartMargin\(labels\) \{[\s\S]*?\n  \}")]
    with tempfile.TemporaryDirectory(prefix='progress-measure-quals-') as directory:
        d = Path(directory)
        source = '<!doctype html><html><head><meta charset="utf-8"><style>'+page.page_css()+'</style></head>'
        source += '<body><section class="progress" style="width:600px"></section><script>'
        source += 'const section=document.querySelector("section.progress");\n'+'\n'.join(pieces)
        source += '\nwindow.margin=chartMargin;</script></body></html>'
        (d/'index.html').write_text(source)
        (d/'measure.mjs').write_text(DRIVER)
        config = dict(chrome=page.CHROME, headless=page.HEADLESS, dir=directory,
                      url=(d/'index.html').as_uri(), labels=LABELS, cases=CASES, repeats=32)
        run = subprocess.run(['node',str(d/'measure.mjs')],input=json.dumps(config),text=True,
                             capture_output=True,timeout=75)
        assert run.returncode==0, run.stderr
        return json.loads(run.stdout)


def q_measuring_labels_keeps_exact_margins_with_bounded_layout_work():
    # Replicata: Chrome measures the actual chart labels32 times under two font families; CDP counts layout passes.
    # Expectata: each margin is the least whole-pixel space holding every label plus6px, with the existing40px floor;
    # no more than two layout passes per measurement, independent of the number of labels.
    # Resultata before batching: changing connected text before every width read lays out once per label,
    # followed by another layout when the ruler is removed and the chart width is read.
    result=measured()
    print(json.dumps(result,indent=2))
    for row in result['results']:
        for case in row['contract']:
            wanted=max(40,math.ceil(max(case['widths'])+6))
            assert case['margin']==wanted,(row['family'],case,wanted)
        assert len(set(row['measurements']))==1,row
        assert 0<row['layouts']<=2*result['repeats'],(row['family'],row['layouts'],result['repeats'])


if __name__=='__main__':
    q_measuring_labels_keeps_exact_margins_with_bounded_layout_work()
    print('1 qual passed')
