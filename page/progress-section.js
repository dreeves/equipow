// The section "Search progress" (Claude's, at dreeves's request, 2026-10-17; one box, the same for every search, since
// 2026-11-11, Fable 5.2: dreeves, "the search progress code seems like a shitshow; can you revamp it? ... anti-magic
// anti-magic anti-magic").  searchwatch/watch.py writes its data file, progress.js: one call, progressData({made, runs}),
// every entry of runs a search with the same fields (watch.py's docstring).  While the section is open a script element
// loads progress.js, again every POLL ms (a minute, or window.PROGRESS_POLL_MS, which the quals set), skipped while the
// tab is hidden; the section draws only when the snapshot changed, in place, and loads nothing while closed.  This
// browser keeps whether it last left the section open (localStorage, KEPT), and the section opens itself on load if so
// (dreeves, 2026-10-17: reloads, as Live Server's when files change, kept closing it); likewise each run's fold (FOLD,
// 2026-10-25; see remember).  Every word
// it shows is in the section's HTML (its templates); this script writes numbers, times and marks, durations with their
// units, h, d or y (dreeves, 2026-10-23), each to its uncertainty, and times so far in days, hours, minutes and seconds,
// the running ones going on with the clock (HMSFORMAT, 2026-11-07).
// Per search, by one path whatever the search (searchBox): a bar of its work, in the unit it counts its work in
// (workBar); progress.html's ETA chart (eta_chart there: dreeves's design), from its estimates; its status line; the
// machine's CPU under the chart; its runs' counts; the sea, one dot per run of the data's groups, each group a block of
// cells (strips below), cells of pitch px, chosen from 10 down to 2 px so that the sea is at most about 560 px tall, a
// dot a device px short of its cell (none short below 3 device px); and last its prior and its graph of P(exists)
// (oddsChart).  Which words and which number forms a box gets is a lookup by its entry's unit and basis, never a test
// of the kind of search.
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
  const wall = window.PROGRESS_CLOCK || (() => Date.now() / 1000);   // the clock, in seconds: Date's, or the quals' (as POLL)
  const KEPT = 'progress-open';                // localStorage: "1" while this browser last left the section open
  const FOLD = 'progress-fold ';               // localStorage: "1" under this, a run's program, n and order while its fold is open
  const view = window.progressView = {loads: 0, renders: 0, data: null, layouts: []};
  let poll = null, ticker = null, made = null, resizing = null, clips = 0;   // clips: the charts' clip paths made, for their ids
  // each status line's running form's time so far, as [its element, the clock time it counts from], which tick writes
  // each second as the clock goes on (statusLine; dreeves, 2026-11-07: "make it update second by second")
  let live = [];

  const pad = x => String(x).padStart(2, '0');
  const local = t => {
    const d = new Date(t * 1000);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  const stamp = t => `${local(t)}:${pad(new Date(t * 1000).getSeconds())}`;
  // HMSFORMAT (dreeves, 2026-11-07: "show elapsed time with full granularity like so: 3d 4h 5m 6s with spacing exactly
  // like that but the spaces are Narrow No-Break Spaces (unicode 8239)", "i do like the explicit hms better than colons,
  // to help distinguish from times-of-day", and "mark this with "HMSFORMAT" in the code so i can find it and fuss with it
  // myself later"): an elapsed time, known to the second, as "3d 4h 5m 6s": its days, hours, minutes and seconds from
  // the largest unit it reaches down to the second, the zeros between shown (so that the form holds still as it ticks),
  // each number with its unit's letter, and a narrow no-break space (U+202F) between them.  Unicode's CLDR has "3d 4h 5m
  // 6s" for English, Intl.DurationFormat's narrow style, with plain spaces and no zero units; in Latin Modern a thin
  // space (U+2009, &thinsp;) is as wide as U+202F (0.20 and 0.19 em, bold), but a line may break at it.
  const hms = sec => {
    assert(Number.isFinite(sec) && sec >= 0, 'an elapsed time', sec);
    const s = Math.floor(sec), parts = [[Math.floor(s / 86400), 'd'], [Math.floor(s / 3600) % 24, 'h'], [Math.floor(s / 60) % 60, 'm'], [s % 60, 's']];
    return parts.slice([86400, 3600, 60, 0].findIndex(k => s >= k)).map(([v, u]) => `${v}${u}`).join('\u202f');
  };
  // Every other figure of time to its uncertainty (dreeves, 2026-11-07: "sane number of sigfigs for everything else based
  // in a principled way on the amount of uncertainty", e.g. "15.6h - 3.1d" as "16h - 3d" and "Sun 11:39am - Tue 10:17pm"
  // as "Sun 12pm - Tue 10pm"): u, the uncertainty, half the width of an estimate's interval (spread), the one to go,
  // which the time in all and the finish times share; a duration in its unit (unitOf) to the place of the first
  // significant digit of u, but no coarser than a whole unit (places); a clock time to the largest of the hour, ten
  // minutes and the minute (STEPS) that u reaches, the hour with no minutes, "12pm".  Nothing here is known to better
  // than a second (u at least 1 s), nor a clock time to better than its minute.
  const spread = g => (g.hi - g.lo) / 2;
  // A duration's unit (dreeves, 2026-10-23: "more helpful as days or years when over like 48 or maybe 72h"): hours below
  // 72 h, days below a year of 365.25 d, years from there; each [seconds, symbol, the bound below which it serves].
  const UNITS = [[3600, 'h', 72], [86400, 'd', 365.25], [31557600, 'y', Infinity]];
  const unitOf = sec => UNITS.find(([s, , top]) => sec / s < top);
  const places = (u, s) => Math.max(0, -Math.floor(Math.log10(Math.max(u, 1) / s)));   // decimals, in a unit of s seconds
  const figure = (sec, u) => (sec / unitOf(sec)[0]).toFixed(places(u, unitOf(sec)[0]));
  const about = (sec, u) => `${figure(sec, u)}\u202f${unitOf(sec)[1]}`;   // the figure, a narrow no-break space, the unit
  // a range of durations, its unit once when both ends share it: "1–3 h", "16 h–3 d"
  const range = (lo, hi, u) => unitOf(lo) === unitOf(hi) ? `${figure(lo, u)}–${about(hi, u)}` : `${about(lo, u)}–${about(hi, u)}`;
  const ranged = g => g ? range(g.lo, g.hi, spread(g)) : '—';         // an estimate's range ({lo, hi}), or — with none
  const hrs = h => h < 10 ? h.toFixed(1) : h.toFixed(0);             // progress.py's hrs: a tenth below 10, whole from 10
  const STEPS = [3600, 600, 60];                                      // a clock time's, in seconds: the hour, ten minutes, the minute
  const stepOf = u => STEPS.find(s => s <= Math.max(u, 60));
  const rounded = (t, step) => {                                      // the clock time t, local, to the nearest step: a Date
    const d = new Date((t + step / 2) * 1000);
    d.setMinutes(Math.floor(d.getMinutes() * 60 / step) * step / 60, 0, 0);
    return d;
  };
  const ampm = (d, step) => `${d.getHours() % 12 || 12}${step < 3600 ? ':' + pad(d.getMinutes()) : ''}${d.getHours() < 12 ? 'am' : 'pm'}`;   // "6:27am", "6pm"
  const WEEK = 7 * 86400;                // seconds
  const day = d => ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.getDay()];
  // A finish time of a snapshot at t, local, as "Mon 6:27am", to its uncertainty u; but a week or more after t as its
  // date, as "2027-03-15" (dreeves, 2026-10-23: "the parenthetical needs disambiguation when >1week").
  const moment = (t, t1, u) => t1 - t < WEEK ? `${day(rounded(t1, stepOf(u)))} ${ampm(rounded(t1, stepOf(u)), stepOf(u))}` : local(t1).slice(0, 10);
  // The finish times of a snapshot at t, local, as "Mon 6:27am – 10:58pm", to their uncertainty u: the first a moment,
  // the second's weekday only when its date differs, and an end a week or more after t as its date.
  const finish = (t, t1, t2, u) => {
    const step = stepOf(u), a = rounded(t1, step), b = rounded(t2, step);
    const second = t2 - t < WEEK ? `${a.toDateString() === b.toDateString() ? '' : day(b) + ' '}${ampm(b, step)}` : local(t2).slice(0, 10);
    return `${moment(t, t1, u)} – ${second}`;
  };
  // A snapshot's line (template.progress-line), into el's fields: the snapshot's time t, its seconds of running so far
  // x and its estimate g of the seconds to go ({lo, hi}; null: none), as the frozen, paused, completed and aborted forms
  // take them too.
  const fill = (el, field, text) => { for (const e of el.querySelectorAll(`[data-${field}]`)) e.textContent = text; };
  const snapshot = (el, t, x, g) => {
    fill(el, 'when', stamp(t));
    fill(el, 'so-far', hms(x));
    fill(el, 'to-go', ranged(g));
    fill(el, 'sum', g ? range(x + g.lo, x + g.hi, spread(g)) : '—');
    fill(el, 'done', g ? finish(t, t + g.lo, t + g.hi, spread(g)) : '—');
  };
  // A point on the median's course past a run's last record, the dashed line its ETA chart draws there, into el's
  // fields as snapshot writes a record's: the clock t, the seconds of running x and the median's seconds to go m, so
  // that the time in all and the finish time are the median's, each to the record's uncertainty u.
  const course = (el, t, x, m, u) => {
    fill(el, 'when', stamp(t));
    fill(el, 'so-far', hms(x));
    fill(el, 'to-go', about(m, u));
    fill(el, 'sum', about(x + m, u));
    fill(el, 'done', moment(t, t + m, u));
  };
  const num = v => String(Number(v.toPrecision(12)));
  const pct = v => `${+(100 * v).toFixed(4)}%`;
  const tickStep = top => {                                           // progress.py's tick_step
    const e = Math.floor(Math.log10(top / 5));
    return [1, 2, 5, 10].map(m => m * 10 ** e).find(step => top / step <= 5);
  };
  // round ticks of a count from 0 to the first at or past top, tickStep apart but at least 1 (whole things: the pool
  // chart's boxes, 2026-11-03, and the work bar's nodes, 2026-11-06)
  const countTicks = top => {
    const step = Math.max(1, tickStep(top));
    return Array.from({length: Math.ceil(top / step) + 1}, (_, i) => i * step);
  };
  // each axis's round ticks in the unit of its largest value (unitOf; dreeves, 2026-10-23), as hours, and their labels,
  // the last with the unit: the x axis's up past its top, the y axis's up to its cap (the ETA chart's axes, and the pool
  // chart's x axis, 2026-11-03)
  const axis = (top, round) => {
    const [s, u] = unitOf(top * 3600), k = s / 3600, step = tickStep(top / k);
    const ticks = Array.from({length: round(top / k / step) + 1}, (_, i) => step * i);
    return [ticks.map(v => v * k), ticks.map((v, i) => num(v) + (i === ticks.length - 1 ? '\u202f' + u : ''))];
  };
  const assert = (ok, ...what) => { if (!ok) throw new Error(JSON.stringify(what).replace(/"/g, "'")); };   // as mstar-section.js's
  const NS = 'http://www.w3.org/2000/svg';
  const set = (el, attrs) => { for (const k in attrs) el.setAttribute(k, typeof attrs[k] === 'number' ? attrs[k].toFixed(2) : attrs[k]); return el; };
  const make = (tag, attrs, text) => { const e = set(document.createElementNS(NS, tag), attrs); if (text !== undefined) e.textContent = text; return e; };
  const xy = ps => ps.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ');   // a polyline's or polygon's points
  // a count compact, "250K" (the work bar's ticks and its total's range)
  const compact = new Intl.NumberFormat('en-US', {notation: 'compact'});

  function load() {
    view.loads += 1;
    const s = document.createElement('script');
    s.src = 'pagedata/progress.js?' + Date.now();
    s.onload = () => s.remove();
    s.onerror = () => { s.remove(); missing.hidden = false; answer(() => [missing.cloneNode(true)]); };
    document.head.appendChild(s);
  }
  // The runs at a target, for the charts' boxes (page/shared.js, 2026-11-04; dreeves's README, [CEL]: "If the cell is
  // black... maybe just summarize the search efforts so far?"): want(n, m, put) loads progress.js, then puts, for each
  // run of the order m at the length n (a BigInt), its brief; — if none is at that target; or, if progress.js does not
  // load, this section's line that says so.  The section draws the data as it does any (render, below).
  const wants = [];
  view.want = (n, m, put) => { wants.push([n, m, put]); load(); };
  const answer = f => wants.splice(0).forEach(([n, m, put]) => put(f(n, m)));
  // A run's state as its fold's summary names it: running, paused or frozen, or, ended, completed if it recorded an
  // outcome, else aborted (dreeves, 2026-10-25)
  const labelOf = run => run.state !== 'ended' ? run.state : run.outcome === null ? 'aborted' : 'completed';
  // Into a search's box (box) its fold's summary: its question, its label and its state
  function heading(box, run) {
    for (const e of box.querySelectorAll('[data-label]')) e.hidden = e.dataset.label !== labelOf(run);
    box.querySelector('[data-n]').textContent = run.n;
    box.querySelector('[data-order]').textContent = run.order;
    box.querySelector('[data-program]').textContent = run.search;
  }

  // Each second while the section is open: the snapshot's age, and each running form's time so far (live) still on the
  // page, from the clock (wall); none before the first snapshot
  function tick() {
    if (made === null) return;
    const now = wall();
    section.querySelector('[data-age]').textContent = hms(now - made);
    live = live.filter(([e]) => e.isConnected);
    for (const [e, since] of live) e.textContent = hms(now - since);
  }

  window.progressData = data => {
    missing.hidden = true;
    answer((n, m) => {
      const here = data.runs.filter(r => BigInt(r.n) === n && r.order === m);
      return here.length ? here.flatMap(run => brief(run, data.made)) : ['—'];
    });
    if (data.made === made) return;
    made = data.made;
    // running runs first, the rest in the data's order (2026-11-06: the one live run had been listed 10th of 22)
    view.data = {...data, runs: [...data.runs.filter(r => r.state === 'running'), ...data.runs.filter(r => r.state !== 'running')]};
    render();
  };

  function render() {
    const data = view.data;
    view.renders += 1;
    section.querySelector('[data-made]').textContent = stamp(data.made);
    // the new runs are built beside the old ones, then swapped in at once, so no layout in between sees a shorter page
    // (dreeves, 2026-10-26: "Every time the graph updates the page scrolls itself": sea's width read had laid out the
    // page with only the runs rebuilt so far, and the browser pulled the scroll position up to fit it)
    const drawn = data.runs.map(run => searchBox(run, data.made));
    view.layouts = drawn.map(d => d.layout);
    runsBox.replaceChildren(...drawn.map(d => d.box));
    tick();                                    // the age and the times so far as of now, not the snapshot's, at once
  }

  // A search's box, every search's the same (see the top): the box's template, filled from the search's entry.  Its
  // dots are its runs, a dot each, under the line of their counts, and the note that its ETA is Lindy's rule alone is
  // its basis's (lindy.py's), shown while it runs (the stylesheet's).
  function searchBox(run, made) {
    const box = template.content.firstElementChild.cloneNode(true);
    // a run's charts and status line fold under its heading (dreeves, 2026-10-23: "i don't want to see frozen
    // graphs" and "i don't want graphs to magically disappear"), the fold as this browser last left it, whatever the
    // run's state (remember; dreeves, 2026-10-25); a run not running grayed; the summary names the state, an ended
    // run completed if it recorded an outcome, else aborted (dreeves, 2026-10-25: "can these be clearer when
    // collapsed about what's paused/completed/aborted/running?")
    box.dataset.runState = run.state;
    remember(box.querySelector('details'), `${FOLD}${run.search} ${run.n} ${run.order}`);
    heading(box, run);
    box.querySelector('[data-tip]').replaceChildren(line.content.cloneNode(true));   // the ETA chart's tip: a snapshot's line
    staleView(box, run);
    statusLine(box, run, made);
    workBar(box, run.work);
    runsLine(box, run);
    const layout = sea(box, run);
    layout.etaXs = etaChart(box.querySelector('.progress-eta'), run);
    cpuChart(box.querySelector('.progress-cpu'), run);
    box.querySelector('[data-lindy]').hidden = run.basis !== 'lindy';
    oddsChart(box.querySelector('.progress-odds'), run);
    return {box, layout};
  }

  // A search's brief, for a chart's box (want): its heading, its state and its time so far, then the row its work's
  // unit picks: the bar's caption where it counts nodes, the status line where its work is its time (which the caption
  // would say twice)
  const BRIEF_ROW = {nodes: '.progress-bar-caption', seconds: '.progress-status'};
  function brief(run, made) {
    const {box} = searchBox(run, made), said = document.createElement('p');
    said.append(...box.querySelector('summary h3').childNodes, ' ', ...box.querySelector('summary').querySelectorAll(':scope > span'),
                ' ', hms(run.so_far));
    return [said, box.querySelector(BRIEF_ROW[run.work.unit])];
  }

  // A search's runs: the line of their counts by state and of what they found, below the CPU chart, and the
  // dots' hint, a dot per run (the templates progress-track and progress-track-hint)
  function runsLine(box, run) {
    const counts = section.querySelector('template.progress-track').content.cloneNode(true);
    for (const e of counts.querySelectorAll('[data-attempt-count]')) e.textContent = run.runs[e.dataset.attemptCount].toLocaleString('en-US');
    counts.querySelector('[data-search-state]').textContent = run.state;
    box.querySelector('[data-track-line]').replaceChildren(counts);
    const hint = section.querySelector('template.progress-track-hint').content;
    box.querySelector('[data-readout]').replaceChildren(hint.cloneNode(true));
    box.querySelector('canvas').setAttribute('aria-label', hint.textContent.trim());
  }

  // A search's work bar (dreeves, 2026-11-06: "i don't like how that progress bar looks. can you revamp it in a way that
  // makes sense to you? also bring back a subtle tick for the median finish time. bigger picture: should that progress
  // bar be measuring amount of work, not time? the ETA graph is for time. we can still have a 90% CI for amount of work
  // remaining, right?"), every search's since 2026-11-11, from its latest estimate's work, {unit, done, rate, total:
  // {median, lo, hi}}: a track from 0 to the last of its round ticks, PAST times the total's upper end at least; blue up
  // to the work done; the total's band purple, its median a tick; the caption's blue part its unit's
  // (template.progress-unit), with the work done, exact, and its rate, then the total's range.  How a unit's numbers read: nodes as counts, the ticks and the range compact (500M, 1B); seconds
  // as times, the work done as the time so far is written (hms) and the ticks and the range as the ETA chart's.
  const WORK = {
    nodes: {ticks: top => { const t = countTicks(top); return [t, t.map(v => compact.format(v))]; },
            done: v => v.toLocaleString('en-US'), range: t => `${compact.format(t.lo)}–${compact.format(t.hi)}`},
    seconds: {ticks: top => { const [t, labels] = axis(top / 3600, Math.ceil); return [t.map(h => 3600 * h), labels]; },
              done: v => hms(v), range: t => range(t.lo, t.hi, spread(t))},
  };
  function workBar(box, work) {
    const PAST = 1.1, {unit, done, rate, total} = work, form = WORK[unit];
    assert(form && [done, rate, total.lo, total.median, total.hi].every(Number.isFinite) && 0 <= done && done <= total.lo &&
           total.lo <= total.median && total.median <= total.hi, work);
    box.querySelector('.progress-bar-caption .spent').replaceChildren(section.querySelector(`template.progress-unit[data-unit="${unit}"]`).content.cloneNode(true));
    const [ticks, labels] = form.ticks(Math.max(1, PAST * total.hi)), end = ticks[ticks.length - 1];
    const part = name => box.querySelector(`[data-bar="${name}"]`);
    part('done').style.width = pct(done / end);
    part('band').style.left = pct(total.lo / end);
    part('band').style.width = pct((total.hi - total.lo) / end);
    part('median').style.left = pct(total.median / end);
    part('ticks').replaceChildren(...ticks.map((v, i) => {
      const tick = document.createElement('span');
      tick.style.left = pct(v / end);
      tick.textContent = labels[i];
      return tick;
    }));
    fill(box, 'bar-done', form.done(done));
    fill(box, 'work-rate', rate.toLocaleString('en-US', {maximumFractionDigits: 1}));
    fill(box, 'bar-range', form.range(total));
  }

  // A run's status line (p.progress-status), below its ETA chart, and in a chart's box as its brief's row (brief): only
  // its state's form shown, naming the state as its fold's summary does (dreeves, 2026-10-26: "can you change those
  // instances of "ended" to "aborted" or "completed" as appropriate?"), the running form a snapshot's line
  // (template.progress-line); its fields a snapshot's at the run's stale time or else made, the snapshot's time, its
  // time so far and its estimate to go (render's lines until 2026-11-06, when brief came to brief it too); the running
  // form's time so far live (dreeves, 2026-11-07: "make it update second by second"), counted from the clock time the
  // run would have started at, as of its data, the form shown only for a running run
  function statusLine(box, run, made) {
    const status = box.querySelector('.progress-status');
    for (const e of status.querySelectorAll('[data-state]')) e.hidden = e.dataset.state !== labelOf(run);
    status.querySelector('[data-state="running"]').replaceChildren(line.content.cloneNode(true));
    snapshot(status, run.stale ?? made, run.so_far, run.to_go);
    live.push([status.querySelector('[data-state="running"] [data-so-far]'), (run.stale ?? made) - run.so_far]);
  }

  // a run whose survey failed or ran past its limit (progress.py's snapshot, 2026-10-30) shows its last good data,
  // marked stale with their time, which its status line then gives as well; a data file written before then has no
  // stale field, its runs fresh (== null: null or absent)
  function staleView(box, run) {
    const mark = box.querySelector('[data-stale]');
    mark.hidden = run.stale == null;
    mark.querySelector('[data-stale-at]').textContent = run.stale == null ? '' : stamp(run.stale);
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
    // the section's own width: a folded canvas has none, and nor has the list of runs while the section is folded, as
    // it is when a chart's box has the data loaded (want, above; runsBox's width until 2026-11-04)
    const Wpx = section.clientWidth, dpr = window.devicePixelRatio || 1;
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

  // The ETA chart's x axis: hours of running, from 0 to past the projected finish (the last record's elapsed + ETA, or
  // the time so far), its round ticks and labels, and its scale across the chart's width; the CPU chart under it shares
  // them, so that the two line up (2026-11-07)
  const ETA_W = 640, ETA_L = 48, ETA_R = 72;
  function etaX(run) {
    const last = run.etas[run.etas.length - 1];
    const xmax = Math.max(run.so_far / 3600, 1 / 3600, ...(last ? [(last[1] + last[2]) / 3600] : []));
    const [xticks, xlabels] = axis(xmax, Math.ceil);
    return {xmax, xticks, xlabels, X: x => ETA_L + (ETA_W - ETA_L - ETA_R) * x / xticks[xticks.length - 1]};
  }

  function etaChart(fig, run) {
    const pts = run.etas.map(([t, x, m, lo, hi]) => [t, x / 3600, m / 3600, lo / 3600, hi / 3600]);
    const W = ETA_W, H = 240, L = ETA_L, R = ETA_R, T = 14, B = 30, CROWD = 44, HEAD = 1.1, TOP = 40, GAP = 10;
    const now = run.so_far / 3600, last = pts[pts.length - 1];
    const {xmax, xticks, xlabels, X} = etaX(run);
    // the y axis's cap: a bit above the projected finish, the guide's level, and the elapsed time (dreeves, 2026-10-23:
    // "truncate the y-axis a bit above the horizontal purple dashed line"); anything taller goes to the top panel where
    // that gives the main panel a larger scale than one axis up to the tallest value would, i.e. where the tallest is
    // more than room / (room - TOP - GAP) times the cap (dreeves, 2026-11-04, of a break whose band top sat just above
    // the cap: "sounds like your principled fix should work"); else one axis runs up to the tallest value
    const ymax = HEAD * xmax, room = H - B - T;
    const values = pts.flatMap(p => [p[2], p[4], p[1] + p[2], p[1] + p[4]]), tall = Math.max(ymax, ...values);
    const over = (room - TOP - GAP) * tall > room * ymax, cap = over ? ymax : tall;
    const [yticks, ylabels] = axis(cap, Math.floor);
    // The y axis broken canonically, the span between its panels elided (dreeves, 2026-10-23: "can you do something
    // more canonical for the y-axis break? maybe something like this?", a two-panel plot with slashes at the break; "i
    // guess i shouldn't have said truncation when i meant elision"): the values above the cap, the bands' tops mostly,
    // get a top panel TOP units tall, GAP above the main one, linear from lo2, the round tick of their unit at or below
    // the least of them but no lower than the cap, to hi2, the round tick at or above the greatest; with none, the top
    // panel and the gap have no height.
    const tops = values.filter(v => v > cap);              // none unless over: the one axis's cap is the tallest
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
      if (s > 0) course(tip, t + s, x + s, Math.max(0, median - s), spread({lo, hi}));
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

  // A run's prior P(exists) and its graph of P(exists) given none found so far, every run's (dreeves, 2026-11-04: "1.
  // probability a partition exists, starting from whatever prior and going down as the search proceeds and doesn't find
  // one"; 2026-11-06: "for anti-magic i don't want to conditionally include or exclude graphs", "after the ETA graph,
  // explicitly state the prior probability a bipartition exists ... then show the first probability graph, even though
  // for 288:10 it's uninteresting. then kill everything below that", and "go with 50% as the ignorant prior when there's
  // no model or whatever"; until then, for a run with odds alone, two more graphs, P(found by t | exists) and the
  // chance of a find within 24 h, and a note on their basis), from its odds (watch.py's), {prior, since, exists}:
  // the prior stated as the page writes numbers, and P(exists) at each [t, p] of exists over the hours since since, a
  // line over a wash down to 0, a dot on its last point, on round ticks of percent up to 1% at least and of hours up to
  // the run's time so far or its last point, a quarter hour at least.  Every search has a point at least: it shows from
  // its first estimate (until 2026-11-11 a run with no model of its search had none, and its graph was grayed axes).
  // The machine's CPU over the run's hours of running, under its ETA chart and on its x axis (etaX), so that a dip lines
  // up with the ETA it moved (dreeves, 2026-11-07: "could we get a nice CPU usage graph on the search page? similar to
  // what activity monitor shows. three colors: one for the search, one for all other processes on the machine, and one
  // for idle, if any", then "maybe aligned with the ETA graph"): run.cpu's rows, [hours of running at an interval's
  // start, at its end, its end's time, the search's share, other processes', idle] (progress.py's cpu_series), stacked
  // from the bottom in that order on 0 to 100%, each band one polygon per stretch of contiguous rows (a gap where the
  // watcher sampled nothing); other processes' share at least 0 where reading the ticks and ps a moment apart left it
  // below (cpu.py's SKEW).  Its key's entries hold the latest row's shares, and its readout that row's time, or at the
  // pointer the row under it's (dreeves, 2026-11-08: "might as well combine the percentages with the legend here";
  // the readout gave both until then), all empty with no rows, when the chart shows its grid alone.
  function cpuChart(fig, run) {
    assert(Array.isArray(run.cpu), run.search, run.n, run.order);
    const {xticks, X} = etaX(run), H = 72, T = 4, B = 4, Y = f => H - B - (H - B - T) * f;
    const q = sel => fig.querySelector(sel), readout = q('[data-cpu-readout]'), cross = q('[data-cpu-cross]'), svg = fig.querySelector('svg');
    q('[data-cpu-grid]').replaceChildren(...xticks.map(v => make('line', {class: 'grid', x1: X(v), y1: T, x2: X(v), y2: H - B})),
                                         make('line', {class: 'axis', x1: ETA_L, y1: Y(0), x2: ETA_W - ETA_R, y2: Y(0)}));
    q('[data-cpu-ticks]').replaceChildren(make('text', {class: 'ytick', x: ETA_L - 6, y: Y(1) + 8, 'text-anchor': 'end'}, '100%'),
                                          make('text', {class: 'ytick', x: ETA_L - 6, y: Y(0), 'text-anchor': 'end'}, '0'));
    const tops = r => [r[3], r[3] + Math.max(0, r[4]), r[3] + Math.max(0, r[4]) + r[5]];   // the bands' tops, bottom up
    const stretches = run.cpu.reduce((s, r, i) => (i && run.cpu[i - 1][1] === r[0] ? s[s.length - 1].push(r) : s.push([r]), s), []);
    const bands = ['search', 'other', 'idle'].flatMap((name, j) => stretches.map(rows => {
      const edge = f => rows.flatMap(r => [[X(r[0]), Y(f(r))], [X(r[1]), Y(f(r))]]);
      return make('polygon', {class: `band ${name}`, points: xy(edge(r => tops(r)[j]).concat(edge(r => j && tops(r)[j - 1]).reverse()))});
    }));
    q('[data-cpu-bands]').replaceChildren(...bands);
    const shares = {search: r => r[3], other: r => Math.max(0, r[4]), idle: r => r[5]};
    const say = r => {
      for (const e of fig.querySelectorAll('[data-cpu-share]')) e.textContent = r ? `${Math.round(100 * shares[e.dataset.cpuShare](r))}%` : '';
      readout.textContent = r ? `@${stamp(r[2])}` : '';
    };
    const rest = run.cpu[run.cpu.length - 1];
    say(rest);
    svg.onmousemove = ev => {                   // the row under the pointer, or the nearest, and a crosshair through it
      const b = svg.getBoundingClientRect(), x = (ev.clientX - b.left) * ETA_W / b.width;
      const row = run.cpu.reduce((best, r) => Math.abs((X(r[0]) + X(r[1])) / 2 - x) < Math.abs((X(best[0]) + X(best[1])) / 2 - x) ? r : best, rest ?? [0, 0]);
      say(rest && row);
      set(cross, {x1: x, y1: T, x2: x, y2: H - B}).setAttribute('visibility', rest ? 'visible' : 'hidden');
    };
    svg.onmouseleave = () => { say(rest); cross.setAttribute('visibility', 'hidden'); };
  }

  function oddsChart(fig, run) {
    assert(run.odds, 'a run without odds', run.search, run.n, run.order);
    const {prior, since, exists} = run.odds;
    assert(typeof prior === 'number' && 0 <= prior && prior <= 1 && Array.isArray(exists) && (Number.isFinite(since) || (since === null && !exists.length))
           && exists.every(([t, p]) => Number.isFinite(t) && 0 <= p && p <= 1), 'malformed odds', run.odds);
    fill(fig, 'odds-prior', num(prior));
    const W = 640, H = 160, L = 48, R = 72, T = 14, B = 30, q = sel => fig.querySelector(sel);
    const pts = exists.map(([t, p]) => [(t - since) / 3600, p]);
    const top = Math.max(0.01, ...pts.map(([, p]) => p)), step = tickStep(top);
    const pticks = Array.from({length: Math.ceil(top / step - 1e-9) + 1}, (_, i) => i * step);
    const [tticks, tlabels] = axis(Math.max(1 / 4, run.so_far / 3600, ...pts.map(([h]) => h)), Math.ceil);
    const X = h => L + (W - L - R) * h / tticks[tticks.length - 1], Y = v => H - B - (H - B - T) * v / pticks[pticks.length - 1];
    q('[data-exists-grid]').replaceChildren(
      ...pticks.slice(1).map(v => make('line', {class: 'grid', x1: L, y1: Y(v), x2: W - R, y2: Y(v)})),
      make('line', {class: 'axis', x1: L, y1: Y(0), x2: W - R, y2: Y(0)}),
      make('line', {class: 'yaxis', x1: L, y1: Y(0), x2: L, y2: T}));
    q('[data-exists-ticks="p"]').replaceChildren(...pticks.map((v, i) =>
      make('text', {class: 'ytick', x: L - 6, y: Y(v) + 4, 'text-anchor': 'end'}, num(100 * v) + (i === pticks.length - 1 ? '%' : ''))));
    q('[data-exists-ticks="t"]').replaceChildren(...tticks.map((h, i) =>
      make('text', {class: 'xtick', x: X(h), y: H - 8, 'text-anchor': 'middle'}, tlabels[i])));
    const line = pts.map(([h, p]) => [X(h), Y(p)]), ends = [line.slice(0, 1), line.slice(-1)];   // none with no point
    set(q('[data-exists-line]'), {points: xy(line)});
    set(q('[data-exists-wash]'), {points: xy([...ends[0].map(([x]) => [x, Y(0)]), ...line, ...ends[1].map(([x]) => [x, Y(0)])])});
    q('[data-exists-marks]').replaceChildren(...ends[1].map(([cx, cy]) => make('circle', {class: 'mark', r: 4, cx, cy})));
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
