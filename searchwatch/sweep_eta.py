#!/usr/bin/env python3
"""Fable 5.2's estimator (see track.py's vocabulary) of a sweep, searches/tilted/sweep.py (2026-11-27; dreeves, of the
528:12 search's box: "i find it hard to believe that this lindy-only ETA is the best we can do").  A sweep enumerates
fixed lists of cosets, one list a profile, each coset once, so its work is countable.  The tracker runs it as

    python3 -B searchwatch/track.py run NAME SEARCH N:M --found DIR/found.jsonl searchwatch/sweep_eta.py DIR -- COMMAND ...

and each time it is run it appends one estimate, of the whole sweep, to the record that TRACK_RECORD names.

  DIR       the sweep's directory.  The sweep is its lists, whichever run started them: a list is a curve X.curve.json
            there with its log X.jsonl, so the runs of one sweep all give the same estimate, and a list is counted
            from the moment its curve is there.  found.jsonl there is the sweep's file of witnesses, a line each.
  model     DIR/model.json, {count, calibration, recovery, why}, read at every estimate, so that a revised model needs
            no relaunch (2026-11-27, evening; until then the first two were arguments of each launch): count, the
            witnesses the count model expects before the sweep, over everything it counts; calibration, what a count
            of that model is worth, a control's witnesses found over those it predicted (at 544:10, 46 over 56.7), by
            which the count and the curves are multiplied; recovery, the chance that the enumeration finds a witness
            in a coset it sweeps (at 528:12, 68 of 71 planted ones); why, where the three come from.  LAMBDA below is
            calibration times count.
  log       a list's, sweep.py's: a line a chunk of cosets, with the list's digest and length K, the cosets to
            sweep (count, at most K), the chunk's first and last coset, its nodes and the time it ended.
  curve     that list's expected witnesses, JSON {digest, K, curve: [[k, the witnesses expected in its best k cosets],
            ...]}, k rising to K; read by straight lines, from 0 at k = 0.  One of another list stops the estimator.

  plan      DIR/plan.jsonl, a line a list the sweep is to take: {name, W, floor, count}.  A planned list with no
            curve yet (NAME.curve.json) has not begun, or has no first chunk: it counts by its kind (2026-11-28;
            dreeves, of the ETA chart, whose time to go had jumped at each list a launcher started: "these ETAs sure
            don't look calibrated").
  kind      a list's width, floor and count (a curve states W and floor).  What a list of a kind takes, in nodes:
            what the lists of that kind swept to their counts took, the RECENT latest of them to end (a cut list is
            none: its last line has `was`);
            with none, what its kind's lists under way are forecast to take in all by their own cost; with none of
            those either, the same of any kind.
  work      in nodes.  done: the logs' nodes.  A log's nodes to come: its latest chunks' nodes a coset (LATEST: the
            chunks that end in the last tenth of its swept cosets), taken as the cost at their middle position, falling
            as position^-b down the rest of its list.  DECAY's three b give the total's low end, median and high end;
            at 528:12 a coset's tree had 6.0e6 nodes at position 500, 2.6e6 at 10,000, 1.3e6 at 100,000 and 5.9e5 at
            900,000, b from 0.28 to 0.35.  A list with less than EARLY of its cosets swept says little of its own
            cost (its top cosets are its dearest): it is forecast as a list of its kind, less its nodes done, where
            there is a measure of its kind.  A planned list not begun: as a list of its kind (or, with no measure,
            as the lists under way).  The low, median and high of a kind are the tenth, middle and ninetieth
            hundredths of what its lists took.  rate: the nodes a second of the lists running, by their latest
            chunks: those not swept to their counts whose newest chunk is within ACTIVE seconds of the directory's
            newest (with none, the lists that close to it: a record's rate is positive).
  to_go     the nodes to come, all lists', at that rate: the lists share the machine's cores, and the planned ones
            wait for them; or the longest of the lists' own times where that is longer (a list's: its nodes to come
            at the wall seconds a node of its latest chunks; a chunk's wall seconds: from the chunk before it; the
            first's, its CPU seconds).  Times SPEED: of the rests of 43 finished lists, a tenth took under 0.8 of the
            time their own speed gave and a tenth over 1.7 (scratch/sweepeta-20261128/speed.py), so the band holds
            the speed's spread and not the nodes' alone.  (Until 2026-11-28 the longest of the lists' own times,
            of the lists begun.)
  pending   the cosets left to sweep, the planned lists' too; finished, those swept.
  prior     1 - exp(-LAMBDA): the witnesses are taken as Poisson.
  exists    1 - exp(-(LAMBDA - recovery c)), c the curves' expected witnesses at the cosets swept, calibrated: what the
            sweep has not found, of what it would have; 1 once found.jsonl has a line.
  finds     1 - exp(-recovery (C - c)), C the curves' expected witnesses in the cosets the sweep takes (each log's count: a
            long list may be swept a part at a time, 2026-11-27 night; the whole lists until then), calibrated: the chance that the sweep
            itself finds a witness in the cosets it has left (2026-11-27; dreeves: "if the chance that the current
            search ... finds a witness is very different from that then that should also be shown on the page"); 1 once
            found.jsonl has a line.  It rises when a list joins the sweep.

Quals: quals_sweep_eta.py
"""
import sys
sys.dont_write_bytecode = True
import os, glob, json, math, time
import numpy as np
import track

DECAY = (0.4, 0.3, 0.2)          # b for the total's lo, median, hi
LATEST = 0.9                     # a log's latest chunks end past this share of its swept cosets
EARLY = 0.02                     # a list with less than this share of its cosets swept is forecast by its kind
ACTIVE = 900                     # seconds: a list is running if its newest chunk is this close to the directory's newest
RECENT = 5                       # a kind is measured by this many of its lists, the latest to end: lists run in the order of their profiles' ranks, and a later rank's is cheaper
SPEED = (0.8, 1.0, 1.7)          # a time to go's lo, median, hi, over what the speeds read give (measured: see to_go)


def log_work(rows, curve):
    """A list's (nodes done, cosets swept, cosets left, nodes to come by its own cost at each of DECAY, wall seconds a node,
    expected witnesses swept, expected witnesses in the cosets the sweep takes (its count's, of a list swept in part),
    kind, its newest chunk's time, whether it measures its kind: swept to its count and not cut)."""
    assert len({(r['digest'], r['K']) for r in rows} | {(curve['digest'], curve['K'])}) == 1, 'the curve is of another list'
    ks, cs = zip(*curve['curve'])
    assert list(ks) == sorted(set(ks)) and ks[-1] == curve['K'] and all(c >= 0 for c in cs), 'the curve does not cover its list'
    swept, count = rows[-1]['last'] + 1, rows[-1]['count']
    walls = [rows[0]['cpu_s']] + [b['time'] - a['time'] for a, b in zip(rows, rows[1:])]
    late = [(r, w) for r, w in zip(rows, walls) if r['last'] + 1 > LATEST * swept]
    nodes, cosets, wall = (sum(v) for v in zip(*((r['nodes'], r['last'] + 1 - r['first'], w) for r, w in late)))
    mid = (late[0][0]['first'] + swept) / 2
    come = [nodes / cosets * mid ** b * (count ** (1 - b) - swept ** (1 - b)) / (1 - b) for b in DECAY]
    at = lambda k: float(np.interp(k, (0,) + ks, (0.0,) + cs))
    return (sum(r['nodes'] for r in rows), swept, count - swept, come, wall / nodes, at(swept), at(count),
            (curve['W'], curve['floor'], count), rows[-1]['time'], swept == count and 'was' not in rows[-1])


def estimate(model, witnesses, works, planned):
    """The estimate, without its time, of a sweep whose lists' works are works (log_work's) and whose planned lists
    without a curve yet have the kinds planned, by its model (model.json)."""
    assert set(model) == {'count', 'calibration', 'recovery', 'why'} and type(model['why']) is str, 'model.json holds count, calibration, recovery and why'
    lam, recovery = model['calibration'] * model['count'], model['recovery']
    assert lam > 0 and 0 < model['calibration'] and 0 < recovery <= 1, model
    done, cosets, left = (sum(w[i] for w in works) for i in range(3))
    under = [w for w in works if w[2] > 0]                                  # the lists under way: not swept to their counts
    shown = [w for w in under if w[1] >= EARLY * w[7][2]]                   # of them, those past their first cosets
    whole = lambda w: w[0] + w[3][1]                                        # what a list under way is forecast to take in all, by its own cost
    last = lambda ws: [w[0] for w in sorted(ws, key=lambda w: w[8])[-RECENT:]]   # the nodes of the latest of them to end
    measures = lambda kind: (last([w for w in works if w[9] and w[7] == kind]) or [whole(w) for w in shown if w[7] == kind]
                             or last([w for w in works if w[9]]) or [whole(w) for w in shown])   # what a list of the kind takes (see kind)
    levels = lambda v: [float(x) for x in np.quantile(v, (0.1, 0.5, 0.9))]
    # a list under way: by its own cost once past its first cosets, or where nothing measures its kind; else by its kind, less its nodes done
    own = lambda w: w in shown or not measures(w[7])
    comes = [(lambda: [max(0.0, x - w[0]) for x in levels(measures(w[7]))], lambda: w[3])[own(w)]() for w in under]
    queue = [levels(measures(kind) or [whole(w) for w in under]) for kind in planned]
    come = [sum(c[j] for c in comes + queue) for j in range(3)]
    newest = max(w[8] for w in works)
    close = [w for w in works if w[8] >= newest - ACTIVE]
    rate = sum(1 / w[4] for w in ([w for w in close if w[2] > 0] or close))
    go = [SPEED[j] * max([c[j] * w[4] for c, w in zip(comes, under)] + [come[j] / rate]) for j in range(3)]
    swept, taken = (model['calibration'] * sum(w[i] for w in works) for i in (5, 6))        # the curves' expected witnesses, calibrated
    expected = lam - recovery * swept
    assert expected > 0, 'the curves hold more witnesses than the count'
    band = lambda v: dict(lo=v[0], median=v[1], hi=v[2])
    return dict(event='estimate', basis='sweep', unit='nodes', done=done, rate=rate,
                total=band([done + c for c in come]), to_go=band(go), prior=1 - math.exp(-lam),
                exists=max(1 - math.exp(-expected), min(1, witnesses)),
                finds=max(1 - math.exp(-recovery * (taken - swept)), min(1, witnesses)), pending=left + sum(kind[2] for kind in planned), finished=cosets)


if __name__ == '__main__':
    assert __debug__ and len(sys.argv) == 2, __doc__
    d = sys.argv[1]
    works = [log_work([json.loads(s) for s in open(curve[:-len('.curve.json')] + '.jsonl')], json.load(open(curve))) for curve in sorted(glob.glob(os.path.join(d, '*.curve.json')))]
    planned = [(x['W'], x['floor'], x['count']) for x in (json.loads(s) for s in open(os.path.join(d, 'plan.jsonl'))) if not os.path.exists(os.path.join(d, x['name'] + '.curve.json'))]
    track.append(os.environ[track.RECORD], dict(estimate(json.load(open(os.path.join(d, 'model.json'))), sum(1 for _ in open(os.path.join(d, 'found.jsonl'))), works, planned), time=time.time()))
