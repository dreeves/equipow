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
  log       a profile's, sweep.py's: a line a chunk of cosets, with the list's digest and length K, the cosets to
            sweep (count), the chunk's first and last coset, its nodes and the time it ended.
  curve     that list's expected witnesses, JSON {digest, K, curve: [[k, the witnesses expected in its best k cosets],
            ...]}, k rising to K; read by straight lines, from 0 at k = 0.  One of another list stops the estimator.

  work      in nodes.  done: the logs' nodes.  A log's nodes to come: its latest chunks' nodes a coset (LATEST: the
            chunks that end in the last tenth of its swept cosets), taken as the cost at their middle position, falling
            as position^-b down the rest of its list.  DECAY's three b give the total's low end, median and high end;
            at 528:12 a coset's tree had 6.0e6 nodes at position 500, 2.6e6 at 10,000, 1.3e6 at 100,000 and 5.9e5 at
            900,000, b from 0.28 to 0.35.  rate: the nodes a second of the logs' latest chunks together (a record's rate is
            positive, so a list that is done keeps its last).
  to_go     the longest of the logs' times: a profile has its own process.  A log's: its nodes to come at the wall
            seconds a node of its latest chunks (a chunk's wall seconds: from the chunk before it; the first's, its CPU
            seconds, so a restart counts its idle time until LATEST leaves it behind).
  pending   the cosets left to sweep; finished, those swept.
  prior     1 - exp(-LAMBDA): the witnesses are taken as Poisson.
  exists    1 - exp(-(LAMBDA - recovery c)), c the curves' expected witnesses at the cosets swept, calibrated: what the
            sweep has not found, of what it would have; 1 once found.jsonl has a line.
  finds     1 - exp(-recovery (C - c)), C the curves' expected witnesses in the whole lists, calibrated: the chance that the sweep
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


def log_work(rows, curve):
    """A log's (nodes done, cosets swept, cosets left, nodes to come at each of DECAY, wall seconds a node, expected witnesses swept, expected witnesses in its whole list)."""
    assert len({(r['digest'], r['K']) for r in rows} | {(curve['digest'], curve['K'])}) == 1, 'the curve is of another list'
    ks, cs = zip(*curve['curve'])
    assert list(ks) == sorted(set(ks)) and ks[-1] == curve['K'] and all(c >= 0 for c in cs), 'the curve does not cover its list'
    swept, count = rows[-1]['last'] + 1, rows[-1]['count']
    walls = [rows[0]['cpu_s']] + [b['time'] - a['time'] for a, b in zip(rows, rows[1:])]
    late = [(r, w) for r, w in zip(rows, walls) if r['last'] + 1 > LATEST * swept]
    nodes, cosets, wall = (sum(v) for v in zip(*((r['nodes'], r['last'] + 1 - r['first'], w) for r, w in late)))
    mid = (late[0][0]['first'] + swept) / 2
    come = [nodes / cosets * mid ** b * (count ** (1 - b) - swept ** (1 - b)) / (1 - b) for b in DECAY]
    return sum(r['nodes'] for r in rows), swept, count - swept, come, wall / nodes, float(np.interp(swept, (0,) + ks, (0.0,) + cs)), cs[-1]


def estimate(model, witnesses, works):
    """The estimate, without its time, of a sweep whose logs' works are works, by its model (model.json)."""
    assert set(model) == {'count', 'calibration', 'recovery', 'why'} and type(model['why']) is str, 'model.json holds count, calibration, recovery and why'
    lam, recovery = model['calibration'] * model['count'], model['recovery']
    assert lam > 0 and 0 < model['calibration'] and 0 < recovery <= 1, model
    done, cosets, left = (sum(w[i] for w in works) for i in range(3))
    come = [sum(w[3][j] for w in works) for j in range(3)]
    go = [max(w[3][j] * w[4] for w in works) for j in range(3)]
    swept, whole = (model['calibration'] * sum(w[i] for w in works) for i in (5, 6))       # the curves' expected witnesses, calibrated
    expected = lam - recovery * swept
    assert expected > 0, 'the curves hold more witnesses than the count'
    band = lambda v: dict(lo=v[0], median=v[1], hi=v[2])
    return dict(event='estimate', basis='sweep', unit='nodes', done=done, rate=sum(1 / w[4] for w in works),
                total=band([done + c for c in come]), to_go=band(go), prior=1 - math.exp(-lam),
                exists=max(1 - math.exp(-expected), min(1, witnesses)),
                finds=max(1 - math.exp(-recovery * (whole - swept)), min(1, witnesses)), pending=left, finished=cosets)


if __name__ == '__main__':
    assert __debug__ and len(sys.argv) == 2, __doc__
    d = sys.argv[1]
    works = [log_work([json.loads(s) for s in open(curve[:-len('.curve.json')] + '.jsonl')], json.load(open(curve))) for curve in sorted(glob.glob(os.path.join(d, '*.curve.json')))]
    track.append(os.environ[track.RECORD], dict(estimate(json.load(open(os.path.join(d, 'model.json'))), sum(1 for _ in open(os.path.join(d, 'found.jsonl'))), works), time=time.time()))
