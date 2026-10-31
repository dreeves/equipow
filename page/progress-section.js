// Claude's section "Search progress" (dreeves, 2026-10-17).  progress.py writes its data file, progress.js: one call,
// progressData({made, runs}) (its contract: progress.js_text).  While the section is open a script element loads
// progress.js, again every POLL ms (a minute, or window.PROGRESS_POLL_MS, which the quals set), skipped while the tab
// is hidden; the section draws only when the snapshot changed, in place, and loads nothing while closed.  This browser
// keeps whether it last left the section open (localStorage, KEPT), and the section opens itself on load if so (dreeves,
// 2026-10-17: reloads, as Live Server's when files change, kept closing it); likewise each run's fold (FOLD, 2026-10-25;
// see remember).  Every word
// it shows is in the section's HTML (its templates); this script writes numbers, times and marks, durations with their
// units, h, d or y (dreeves, 2026-10-23).
// Per run: a bar of hours so far and to go, to scale (so far, then the band's bottom, then the rest of the band, the
// median marked); the sea, one dot per sub-case of the data's groups, each group a block of cells (strips below), cells
// of pitch px, chosen from 10 down to 2 px so that the sea is at most about 560 px tall, a dot a device px short of its
// cell (none short below 3 device px); and progress.html's ETA chart
// (eta_chart there: dreeves's design), from the run's recorded ETAs.
// Strips: an ordered strip layout (Bederson, Shneiderman and Wattenberg 2002) on whole cells.  The groups, in order,
// fill strips across the cols; a strip's blocks share its height h, each as wide as its count needs at that height, a
// cell's gap between blocks and between strips; h is the least at which the strip's blocks fit across, and a strip
// takes the next group unless that worsens its worst block's aspect ratio.
// window.progressView holds the loads, renders, data and, per run, its layout (rects, cols, rows, pitch;
// place(group, dot): device px) and the ETA chart's record x positions (etaXs, in its viewBox), for the quals.
(() => {
  const section = document.querySelector('section.progress');
  const details = section.querySelector('details');
  const runsBox = section.querySelector('.progress-runs');
  const template = section.querySelector('template.progress-run');
  const line = section.querySelector('template.progress-line');      // a snapshot's line: the status line's running form, and the tip
  const missing = section.querySelector('.progress-missing');
  const POLL = window.PROGRESS_POLL_MS || 60000;
  const KEPT = 'progress-open';                // localStorage: "1" while this browser last left the section open
  const FOLD = 'progress-fold ';               // localStorage: "1" under this, a run's program, n and order while its fold is open
  const view = window.progressView = {loads: 0, renders: 0, data: null, layouts: []};
  let poll = null, ticker = null, made = null, resizing = null, clips = 0;   // clips: the charts' clip paths made, for their ids

  const pad = x => String(x).padStart(2, '0');
  const local = t => {
    const d = new Date(t * 1000);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  const stamp = t => `${local(t)}:${pad(new Date(t * 1000).getSeconds())}`;
  const ampm = d => `${d.getHours() % 12 || 12}:${pad(d.getMinutes())}${d.getHours() < 12 ? 'am' : 'pm'}`;   // "6:27am"
  const WEEK = 7 * 86400;                // seconds
  const day = d => ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.getDay()];
  // A finish time of a snapshot at t, local, as "Mon 6:27am"; but a week or more after t as its date, as "2027-03-15"
  // (dreeves, 2026-10-23: "the parenthetical needs disambiguation when >1week").
  const moment = (t, t1) => t1 - t < WEEK ? `${day(new Date(t1 * 1000))} ${ampm(new Date(t1 * 1000))}` : local(t1).slice(0, 10);
  // The finish times of a snapshot at t, local, as "Mon 6:27am – 10:58pm": the first a moment, the second's weekday only
  // when its date differs, and an end a week or more after t as its date.
  const finish = (t, t1, t2) => {
    const a = new Date(t1 * 1000), b = new Date(t2 * 1000);
    const second = t2 - t < WEEK ? `${a.toDateString() === b.toDateString() ? '' : day(b) + ' '}${ampm(b)}` : local(t2).slice(0, 10);
    return `${moment(t, t1)} – ${second}`;
  };
  const duration = sec => {
    const s = Math.max(0, Math.floor(sec)), d = Math.floor(s / 86400);
    return (d ? `${d} d ` : '') + `${Math.floor(s / 3600) % 24}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
  };
  const tenth = v => v.toFixed(1);
  const hrs = h => h < 10 ? h.toFixed(1) : h.toFixed(0);             // progress.py's hrs: a tenth below 10, whole from 10
  // A duration's unit (dreeves, 2026-10-23: "more helpful as days or years when over like 48 or maybe 72h"): hours below
  // 72 h, days below a year of 365.25 d, years from there; each [seconds, symbol, the bound below which it serves].
  const UNITS = [[3600, 'h', 72], [86400, 'd', 365.25], [31557600, 'y', Infinity]];
  const unitOf = sec => UNITS.find(([s, , top]) => sec / s < top);
  const dur = (sec, fmt) => `${fmt(sec / unitOf(sec)[0])}\u202f${unitOf(sec)[1]}`;   // fmt's number, a narrow no-break space, the unit
  // a range of durations, its unit once when both ends share it: "0.5–3.0 h", "149.9 d–6.4 y"
  const range = (lo, hi, fmt) => unitOf(lo) === unitOf(hi) ? `${fmt(lo / unitOf(lo)[0])}–${dur(hi, fmt)}` : `${dur(lo, fmt)}–${dur(hi, fmt)}`;
  // A snapshot's line (template.progress-line), into el's fields: the snapshot's time t, its seconds of running so far
  // x and its estimate g of the seconds to go ({lo, hi}; null: none), as the frozen, paused, completed and aborted forms
  // take them too.
  const fill = (el, field, text) => { for (const e of el.querySelectorAll(`[data-${field}]`)) e.textContent = text; };
  const snapshot = (el, t, x, g) => {
    fill(el, 'when', stamp(t));
    fill(el, 'so-far', dur(x, tenth));
    fill(el, 'to-go', g ? range(g.lo, g.hi, tenth) : '—');
    fill(el, 'sum', g ? range(x + g.lo, x + g.hi, hrs) : '—');
    fill(el, 'done', g ? finish(t, t + g.lo, t + g.hi) : '—');
  };
  // A point on the median's course past a run's last record, the dashed line its ETA chart draws there, into el's
  // fields as snapshot writes a record's: the clock t, the seconds of running x and the median's seconds to go m, so
  // that the hours in all and the finish time are the median's.
  const course = (el, t, x, m) => {
    fill(el, 'when', stamp(t));
    fill(el, 'so-far', dur(x, tenth));
    fill(el, 'to-go', dur(m, tenth));
    fill(el, 'sum', dur(x + m, hrs));
    fill(el, 'done', moment(t, t + m));
  };
  const num = v => String(Number(v.toPrecision(12)));
  const pct = v => `${+(100 * v).toFixed(4)}%`;
  const tickStep = top => {                                           // progress.py's tick_step
    const e = Math.floor(Math.log10(top / 5));
    return [1, 2, 5, 10].map(m => m * 10 ** e).find(step => top / step <= 5);
  };

  function load() {
    view.loads += 1;
    const s = document.createElement('script');
    s.src = 'progress.js?' + Date.now();
    s.onload = () => s.remove();
    s.onerror = () => { s.remove(); missing.hidden = false; };
    document.head.appendChild(s);
  }

  function tick() {
    if (made !== null) section.querySelector('[data-age]').textContent = duration(Date.now() / 1000 - made);
  }

  window.progressData = data => {
    missing.hidden = true;
    if (data.made === made) return;
    made = data.made;
    view.data = data;
    render();
  };

  function render() {
    const data = view.data;
    view.renders += 1;
    section.querySelector('[data-made]').textContent = stamp(data.made);
    tick();
    // the new runs are built beside the old ones, then swapped in at once, so no layout in between sees a shorter page
    // (dreeves, 2026-10-26: "Every time the graph updates the page scrolls itself": sea's width read had laid out the
    // page with only the runs rebuilt so far, and the browser pulled the scroll position up to fit it)
    const boxes = data.runs.map(() => template.content.firstElementChild.cloneNode(true));
    view.layouts = data.runs.map((run, i) => {
      const box = boxes[i];
      // a run's charts and status line fold under its heading (dreeves, 2026-10-23: "i don't want to see frozen
      // graphs" and "i don't want graphs to magically disappear"), the fold as this browser last left it, whatever the
      // run's state (remember; dreeves, 2026-10-25); a run not running grayed; the summary names the state, an ended
      // run completed if it recorded an outcome, else aborted (dreeves, 2026-10-25: "can these be clearer when
      // collapsed about what's paused/completed/aborted/running?")
      const label = run.state !== 'ended' ? run.state : run.outcome === null ? 'aborted' : 'completed';
      box.dataset.runState = run.state;
      remember(box.querySelector('details'), `${FOLD}${run.program} ${run.n} ${run.order}`);
      for (const e of box.querySelectorAll('[data-label]')) e.hidden = e.dataset.label !== label;
      box.querySelector('[data-n]').textContent = run.n;
      box.querySelector('[data-order]').textContent = run.order;
      box.querySelector('[data-program]').textContent = run.program;
      // the status line below the charts names the state as the summary does (dreeves, 2026-10-26: "can you change those
      // instances of "ended" to "aborted" or "completed" as appropriate?")
      for (const e of box.querySelectorAll('[data-state]')) e.hidden = e.dataset.state !== label;
      for (const e of box.querySelectorAll('[data-tip], [data-state="running"]')) e.replaceChildren(line.content.cloneNode(true));
      staleView(box, run);
      snapshot(box.querySelector('.progress-status'), run.stale ?? data.made, run.so_far, run.to_go);
      for (const e of box.querySelectorAll('[data-count]')) e.textContent = run.counts[e.dataset.count].toLocaleString('en-US');
      bar(box, run);
      if (run.program === 'search288.py') search288View(box, run);
      if (run.program === 'sweep288.py') search288View(box, run);
      if (run.program === 'search592.py') attemptView(box, run, 'progress-search592', 'progress-592-hint');
      if (run.program === 'pruning288.py') {
        attemptView(box, run, 'progress-pruning288', 'progress-pruning-hint');
        // Attribute the generated baseline/wider labels in the hover readout.
        run = {...run, keys: run.keys.map(k => `${k}`)};
      }
      // a search run under track.py, whatever its program: one dot per run, its runs counted by state (dreeves,
      // 2026-10-28: "can we rearchitect things so that always happens easily and automatically?"), with the status line
      // and the ETA chart of every run (2026-10-31: "Every run gets an ETA graph")
      if (run.tracked) trackView(box, run);
      const L = sea(box, run);
      L.etaXs = etaChart(box.querySelector('.progress-eta'), run);
      return L;
    });
    runsBox.replaceChildren(...boxes);
  }

  // a run whose survey failed or ran past its limit (progress.py's snapshot, 2026-10-30) shows its last good data,
  // marked stale with their time, which its status line then gives as well; a data file written before then has no
  // stale field, its runs fresh (== null: null or absent)
  function staleView(box, run) {
    const mark = box.querySelector('[data-stale]');
    mark.hidden = run.stale == null;
    mark.querySelector('[data-stale-at]').textContent = run.stale == null ? '' : stamp(run.stale);
  }

  function search288View(box, run) {
    attemptView(box, run, 'progress-search288', 'progress-attempt-hint');
  }

  // an attempt batch's view: its counts in place of the status line, its hint in place of the key, no ETA chart
  function attemptView(box, run, templateName, hintName) {
    box.querySelector('.progress-status').replaceChildren(counted(templateName, run));
    box.querySelector('.progress-eta').hidden = true;
    hinted(box, hintName);
  }

  // a tracked search's view: its runs' counts on a line of their own after the status line, its hint in place of the key
  function trackView(box, run) {
    box.querySelector('.progress-status').append(document.createElement('br'), counted('progress-track', run));
    hinted(box, 'progress-track-hint');
  }

  // the template named, its counts, phase, outcome, elapsed time and state filled in from the run
  function counted(templateName, run) {
    const display = section.querySelector('template.' + templateName).content.cloneNode(true);
    for (const e of display.querySelectorAll('[data-attempt-count]')) e.textContent = run.work[e.dataset.attemptCount].toLocaleString('en-US');
    for (const e of display.querySelectorAll('[data-attempt-phase]')) e.hidden = e.dataset.attemptPhase !== run.phase;
    for (const e of display.querySelectorAll('[data-attempt-outcome]')) e.hidden = e.dataset.attemptOutcome !== String(run.outcome);
    display.querySelector('[data-elapsed]').textContent = duration(run.so_far);
    display.querySelector('[data-search-state]').textContent = run.state;
    return display;
  }

  // the dots' key hidden, the hint named in the readout and the dots' label
  function hinted(box, hintName) {
    box.querySelector('.progress-key').hidden = true;
    const hint = section.querySelector('template.' + hintName).content;
    box.querySelector('[data-readout]').replaceChildren(hint.cloneNode(true));
    box.querySelector('canvas').setAttribute('aria-label', hint.textContent.trim());
  }

  function bar(box, run) {
    const g = run.to_go, total = run.so_far + (g ? g.hi : 0) || 1;
    const part = name => box.querySelector(`[data-bar="${name}"]`);
    part('so-far').style.width = pct(run.so_far / total);
    part('lo').style.width = pct(g ? g.lo / total : 0);
    part('band').style.width = pct(g ? (g.hi - g.lo) / total : 0);
    part('median').style.left = pct(g ? (run.so_far + g.median) / total : 0);
    part('median').hidden = !g;
  }

  function strips(sizes, W) {
    const sum = a => a.reduce((s, v) => s + v, 0);
    const widths = (g, h) => g.map(s => Math.min(W, Math.max(1, Math.ceil(s / h))));
    const fit = g => {
      let h = Math.max(1, Math.ceil(sum(g) / Math.max(1, W - g.length + 1)));
      while (sum(widths(g, h)) + g.length - 1 > W) h++;
      return h;
    };
    const worst = (g, h) => Math.max(...widths(g, h).map(w => Math.max(w / h, h / w)));
    const rects = [];
    let i = 0, y = 0;
    while (i < sizes.length) {
      let g = [sizes[i]], h = fit(g), j = i + 1;
      while (j < sizes.length && 2 * g.length + 1 <= W) {
        const g2 = g.concat(sizes[j]), h2 = fit(g2);
        if (worst(g2, h2) > worst(g, h)) break;
        g = g2; h = h2; j++;
      }
      let x = 0;
      for (const w of widths(g, h)) { rects.push({x, y, w, h}); x += w + 1; }
      y += h + 1;
      i = j;
    }
    return {rects, rows: Math.max(1, y - 1)};
  }

  function sea(box, run) {
    const canvas = box.querySelector('canvas');
    const css = getComputedStyle(section);
    const colors = run.statuses.map(s => css.getPropertyValue('--progress-' + s).trim());
    const groups = run.groups, sizes = groups.map(g => g.length);
    const Wpx = runsBox.clientWidth, dpr = window.devicePixelRatio || 1;   // the section's: a folded canvas has none
    let L = null;
    for (let pitch = 10; pitch >= 2 && !L; pitch--) {
      const cols = Math.max(1, Math.floor(Wpx / pitch)), S = strips(sizes, cols);
      if (S.rows * pitch <= 560 || pitch === 2) L = {...S, cols, pitch};
    }
    const cell = L.pitch * dpr, size = Math.round(cell) >= 3 ? Math.round(cell) - 1 : Math.max(1, Math.round(cell));   // no gap below 3 px: a 1-px dot in a 2-px cell reads as white
    L.cell = cell;
    L.size = size;
    L.place = (gi, j) => {
      const r = L.rects[gi];
      return [Math.round((r.x + j % r.w) * cell), Math.round((r.y + Math.floor(j / r.w)) * cell), size];
    };
    canvas.style.height = L.rows * L.pitch + 'px';
    canvas.width = Math.round(Wpx * dpr);
    canvas.height = Math.round(L.rows * L.pitch * dpr);
    const ctx = canvas.getContext('2d');
    groups.forEach((g, gi) => {
      for (let j = 0; j < g.length; j++) {
        const [x, y] = L.place(gi, j);
        ctx.fillStyle = colors[+g[j]];
        ctx.fillRect(x, y, size, size);
      }
    });
    const readout = box.querySelector('[data-readout]'), hint = [...readout.childNodes];
    canvas.addEventListener('mousemove', ev => {
      const b = canvas.getBoundingClientRect();
      const col = Math.floor((ev.clientX - b.left) / L.pitch), row = Math.floor((ev.clientY - b.top) / L.pitch);
      const gi = L.rects.findIndex(r => col >= r.x && col < r.x + r.w && row >= r.y && row < r.y + r.h);
      if (gi < 0 || (row - L.rects[gi].y) * L.rects[gi].w + col - L.rects[gi].x >= sizes[gi]) { readout.replaceChildren(...hint); return; }
      const code = document.createElement('code');
      code.textContent = run.keys[gi] || '∅';
      const parts = [code];
      run.statuses.forEach((s, i) => {
        let k = 0;
        for (const c of groups[gi]) if (+c === i) k++;
        if (!k) return;
        const sw = document.createElement('span');
        sw.className = 'progress-sw';
        sw.dataset.status = s;
        parts.push(sw, document.createTextNode(k.toLocaleString('en-US')));
      });
      readout.replaceChildren(...parts);
    });
    canvas.addEventListener('mouseleave', () => readout.replaceChildren(...hint));
    return L;
  }

  function etaChart(fig, run) {
    const pts = run.etas.map(([t, x, m, lo, hi]) => [t, x / 3600, m / 3600, lo / 3600, hi / 3600]);
    const NS = 'http://www.w3.org/2000/svg', W = 640, H = 240, L = 48, R = 72, T = 14, B = 30, CROWD = 44, HEAD = 1.1, TOP = 40, GAP = 10;
    const now = run.so_far / 3600, last = pts[pts.length - 1];
    const xmax = Math.max(now, 1 / 3600, ...pts.slice(-1).map(p => p[1] + p[2]));
    // the y axis's cap: a bit above the projected finish, the guide's level, and the elapsed time (dreeves, 2026-10-23:
    // "truncate the y-axis a bit above the horizontal purple dashed line"); anything taller goes to the top panel
    const ymax = HEAD * xmax;
    // each axis's round ticks in the unit of its largest value (unitOf; dreeves, 2026-10-23), as hours, and their labels,
    // the last with the unit: the x axis's up past its top, the y axis's up to its cap
    const axis = (top, round) => {
      const [s, u] = unitOf(top * 3600), k = s / 3600, step = tickStep(top / k);
      const ticks = Array.from({length: round(top / k / step) + 1}, (_, i) => step * i);
      return [ticks.map(v => v * k), ticks.map((v, i) => num(v) + (i === ticks.length - 1 ? '\u202f' + u : ''))];
    };
    const [xticks, xlabels] = axis(xmax, Math.ceil), [yticks, ylabels] = axis(ymax, Math.floor);
    const X = x => L + (W - L - R) * x / xticks[xticks.length - 1];
    const cap = ymax;
    // The y axis broken canonically, the span between its panels elided (dreeves, 2026-10-23: "can you do something
    // more canonical for the y-axis break? maybe something like this?", a two-panel plot with slashes at the break; "i
    // guess i shouldn't have said truncation when i meant elision"): the values above the cap, the bands' tops mostly,
    // get a top panel TOP units tall, GAP above the main one, linear from lo2, the round tick of their unit at or below
    // the least of them but no lower than the cap, to hi2, the round tick at or above the greatest; with none, the top
    // panel and the gap have no height.
    const tops = pts.flatMap(p => [p[2], p[4], p[1] + p[2], p[1] + p[4]]).filter(v => v > cap), over = tops.length > 0;
    const greatest = Math.max(cap, ...tops), least = Math.min(greatest, ...tops);
    const [s2, u2] = unitOf(greatest * 3600), k2 = s2 / 3600, step2 = tickStep(greatest / k2) * k2;
    const lo2 = Math.max(cap, Math.floor(least / step2) * step2);
    const hi2 = Math.max(Math.ceil(greatest / step2) * step2, (Math.floor(lo2 / step2) + 1) * step2);
    const yt = T + TOP * over, yb = yt + GAP * over;     // the top panel's bottom edge, the main panel's top
    const frac = v => Math.min(1, Math.max(0, v));
    // the main panel to scale up to the cap, the gap from it to lo2, the top panel from lo2 to hi2
    const Y = y => H - B - (H - B - yb) * Math.min(y, cap) / cap - (yb - yt) * frac((y - cap) / Math.max(lo2 - cap, 1e-9))
                   - (yt - T) * frac((y - lo2) / (hi2 - lo2));
    // the top panel's round ticks at its ends, as few labels as fit its TOP units (none without it), the last with its unit
    const t2 = [...new Set([Math.ceil(lo2 / step2 - 1e-9), Math.floor(hi2 / step2 + 1e-9)])].slice(0, 2 * over).map(j => j * step2);
    const l2 = t2.map((v, i) => num(v / k2) + (i === t2.length - 1 ? '\u202f' + u2 : ''));
    // a polyline's or polygon's points through the break: where a segment crosses the cap or lo2, the crossing on that
    // edge of the gap, so that each panel draws its part to its own scale and the gap clips the rest away
    const edges = [[cap, yb], [lo2, yt]];
    const trace = ps => ps.flatMap((p, i) => {
      const q = ps[i - 1] || p, crossed = edges.filter(([v]) => (q[1] <= v) !== (p[1] <= v));
      return (q[1] > p[1] ? crossed.reverse() : crossed)
        .map(([v, y]) => [X(q[0] + (p[0] - q[0]) * (v - q[1]) / (p[1] - q[1])), y]).concat([[X(p[0]), Y(p[1])]]);
    });
    const P = ps => trace(ps).map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
    const set = (el, attrs) => { for (const k in attrs) el.setAttribute(k, typeof attrs[k] === 'number' ? attrs[k].toFixed(2) : attrs[k]); return el; };
    const make = (tag, attrs, text) => { const e = set(document.createElementNS(NS, tag), attrs); if (text !== undefined) e.textContent = text; return e; };
    const q = sel => fig.querySelector(sel);
    q('[data-grid]').replaceChildren(...yticks.slice(1).concat(t2).map(v => make('line', {class: 'grid', x1: L, y1: Y(v), x2: W - R, y2: Y(v)})),
                                     make('line', {class: 'axis', x1: L, y1: Y(0), x2: W - R, y2: Y(0)}),
                                     // the y axis's line (dreeves, 2026-10-23: "i think we need a visible y-axis line for
                                     // that to look reasonable"), broken at the gap: the top panel's part has no length
                                     // without one
                                     make('line', {class: 'yaxis', x1: L, y1: Y(0), x2: L, y2: yb}),
                                     make('line', {class: 'yaxis', x1: L, y1: yt, x2: L, y2: T}));
    // a slash across each end of the y axis's break: the canonical mark of a broken axis
    q('[data-breaks]').replaceChildren(...[yt, yb].map(y =>
      make('line', {class: 'break', x1: L - 4, y1: y + 4, x2: L + 4, y2: y - 4, visibility: over ? 'visible' : 'hidden'})));
    const clip = q('[data-clip]');                        // the gap clipped away from every mark of the data
    clip.id = `progress-clip-${++clips}`;
    set(clip.children[0], {x: 0, y: 0, width: W, height: yt});
    set(clip.children[1], {x: 0, y: yb, width: W, height: H - yb});
    q('[data-plot]').setAttribute('clip-path', `url(#${clip.id})`);
    const band = up => P(pts.map(p => [p[1], up(p) + p[4]]).concat(pts.slice().reverse().map(p => [p[1], up(p) + p[3]])));   // raised by up(p)
    set(q('[data-band-togo]'), {points: band(p => 0)});
    set(q('[data-band-total]'), {points: band(p => p[1])});
    set(q('[data-spent]'), {points: P([[0, 0], [now, now]])});
    set(q('[data-togo]'), {points: P(pts.map(p => [p[1], p[2]]))});
    set(q('[data-total]'), {points: P(pts.map(p => [p[1], p[1] + p[2]]))});
    q('[data-ticks]').replaceChildren(
      ...yticks.concat(t2).map((v, i) => make('text', {class: 'ytick', x: L - 6, y: Y(v) + 4, 'text-anchor': 'end'}, ylabels.concat(l2)[i])),
      ...xticks.map((v, i) => [v, xlabels[i]])
               // .filter(([v]) => Math.abs(X(v) - X(now)) >= CROWD)      // room for the elapsed time's label, commented out with it
               .map(([v, label]) => make('text', {class: 'xtick', x: X(v), y: H - 8, 'text-anchor': 'middle'}, label)));
    // The chart always shows (dreeves, 2026-10-23: "the search progress section should always be clear about what's
    // been running for how long"): with no recorded ETA yet, its axes and the elapsed time alone, the marks at the last
    // record hidden (data-marks), and no tip.
    if (!pts.length) return [];
    const fin = last[1] + last[2];               // the projected finish: hours of running when elapsed time meets elapsed + ETA
    set(q('[data-ahead]'), {x1: X(last[1]), y1: Y(last[1]), x2: X(fin), y2: Y(fin)});
    set(q('[data-guide]'), {points: P([[last[1], fin], [fin, fin], [fin, 0]])});      // across from the purple marker, then down
    set(q('[data-ideal]'), {x1: X(last[1]), y1: Y(last[2]), x2: X(fin), y2: Y(0)});    // the ETA's ideal course: an hour less each hour
    set(q('[data-range-togo]'), {x1: X(last[1]), y1: Y(last[3]), x2: X(last[1]), y2: Y(last[4])});
    set(q('[data-range-total]'), {x1: X(last[1]), y1: Y(last[1] + last[3]), x2: X(last[1]), y2: Y(last[1] + last[4])});
    set(q('[data-now-spent]'), {cx: X(last[1]), cy: Y(last[1])});
    set(q('[data-now-togo]'), {cx: X(last[1]), cy: Y(last[2])});
    set(q('[data-now-total]'), {cx: X(last[1]), cy: Y(last[1] + last[2])});
    // The labels at the latest record, commented out at dreeves's request (2026-10-17: "comment it out for now"):
    // set(q('[data-label-togo]'), {x: X(last[1]) + 8, y: Y(last[2]) + 4});
    // q('[data-togo-range]').textContent = `${hrs(last[3])}–${hrs(last[4])}`;
    // set(q('[data-label-total]'), {x: X(last[1]) + 8, y: Y(last[1] + last[2]) - 6});
    // q('[data-total-range]').textContent = `${hrs(last[1] + last[3])}–${hrs(last[1] + last[4])}`;
    // set(q('[data-label-spent]'), {x: X(now), y: H - 8});
    // q('[data-spent-h]').textContent = hrs(now);
    q('[data-marks]').setAttribute('visibility', 'visible');
    const svg = fig.querySelector('svg'), cross = q('[data-cross]'), tip = q('[data-tip]');
    const xsvg = pts.map(p => X(p[1])), end = xsvg[xsvg.length - 1], hour = X(1) - X(0);   // viewBox units
    // record k's line, with its band, at the record (s = 0); s seconds of running past the last record, in italics
    // (projected; dreeves, 2026-10-18), the median's course alone, the dashed line the chart draws there, as the bands
    // end at the last record (dreeves, 2026-10-30: "that blurb should have just the median, not ranges"): the clock
    // and the hours so far advance together and the median falls second for second, to no less than 0 (the run may
    // be done by then), so that the hours in all and the finish time stay the median's
    const at = (k, s) => {
      const [t, x, median, lo, hi] = run.etas[k];
      if (s > 0) course(tip, t + s, x + s, Math.max(0, median - s));
      else snapshot(tip, t, x, {lo, hi});
      tip.classList.toggle('projected', s > 0);
    };
    tip.style.minHeight = '';                   // its height at rest, measured again at the next hover (below)
    at(pts.length - 1, 0);                      // laid out at rest, invisible, as the latest record's line
    set(cross, {x1: X(last[1]), y1: T, x2: X(last[1]), y2: Y(0)});   // hidden at rest; up through the strip
    svg.addEventListener('mousemove', ev => {
      const b = svg.getBoundingClientRect(), x = Math.min((ev.clientX - b.left) * W / b.width, W - R);   // not past the axis
      // left of the last record, the nearest record (the latest of equals); right of it, the last record carried on to
      // the pointer, in whole minutes (the records' cadence)
      const near = Math.min(x, end), s = 60 * Math.round(60 * (Math.max(x, end) - end) / hour);
      let k = 0;
      for (let i = 1; i < xsvg.length; i++) if (Math.abs(xsvg[i] - near) <= Math.abs(xsvg[k] - near)) k = i;
      const cx = xsvg[k] + hour * s / 3600;
      set(cross, {x1: cx, y1: T, x2: cx, y2: Y(0)}).setAttribute('visibility', 'visible');
      // the tip keeps the height of its line at rest, the latest record's, measured at the first hover after a draw
      // (laid out by then): the median's line past the last record is shorter, and the status line below must not move
      tip.style.minHeight = tip.style.minHeight || `${tip.getBoundingClientRect().height}px`;
      at(k, s);
      tip.style.visibility = 'visible';           // laid out at rest (the CSS hides it), so showing it moves nothing
    });
    svg.addEventListener('mouseleave', () => { cross.setAttribute('visibility', 'hidden'); tip.style.visibility = ''; });
    return xsvg;
  }

  function sync() {
    clearInterval(poll);
    clearInterval(ticker);
    if (!details.open) return;
    load();
    poll = setInterval(() => { if (!document.hidden) load(); }, POLL);
    ticker = setInterval(tick, 1000);
  }
  // A fold, the section's or a run's, opens or stays closed as this browser last left it, "1" stored under its name
  // while open, until clicked (dreeves, 2026-10-25: "remember in localstorage what their state is and just always stay
  // that way until explicitly clicked").  The stored state is a convenience: where storage is unavailable (a private
  // window, blocked site data) a fold works as without it, starting closed.
  function remember(fold, name) {
    try { fold.open = localStorage.getItem(name) === '1'; } catch (e) {}
    fold.addEventListener('toggle', () => {
      try { if (fold.open) localStorage.setItem(name, '1'); else localStorage.removeItem(name); } catch (e) {}
    });
  }
  remember(details, KEPT);
  details.addEventListener('toggle', sync);
  // back to the tab, a fresh snapshot at once, not at the next minute's poll (dreeves, 2026-10-23: "did you break
  // auto-refresh yet again?": a tab long hidden had polled nothing); sync loads nothing while the section is closed
  document.addEventListener('visibilitychange', sync);
  sync();                                      // in case it is open already: its toggle may have fired before this ran
  window.addEventListener('resize', () => {
    clearTimeout(resizing);
    resizing = setTimeout(() => { if (details.open && view.data) render(); }, 200);
  });
})();
