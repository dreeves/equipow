#!/usr/bin/env python3
"""Fable 5.2's estimator (see track.py's vocabulary) of a search that knows nothing but its age (2026-11-11; dreeves,
2026-11-04: "shouldn't there always be an ETA graph, even when it's just based on the lindy effect? death to
if-statements, remember?").  The tracker runs it for a search with no model of its work:

    python3 -B searchwatch/track.py run NAME SEARCH N:M searchwatch/lindy.py -- COMMAND ...

Each time it is run it appends one estimate to the record that TRACK_RECORD names, of that record's search.

  age       the search's seconds of running so far: the seconds during which some run of it was going (track.py's
            spans, passes and running), over every record beside this one's.  A restart of a search goes on from its
            age.
  Lindy     Lindy's rule, as J. Richard Gott's (Nature 363, 1993, "Implications of the Copernican principle for our
            future prospects"): the search's age is as likely to be any fraction of its whole, so the q quantile of the
            time to go is age q / (1 - q): the median its age (the page's "remaining time = elapsed time"), the band,
            at chance.BANDS's levels for it (0.1 and 0.9), from a 9th of the age to 9 times it.
  work      such a search's only measure of its work is its time: unit seconds, done its age, rate 1 a second, and the
            total its age more than its time to go.
  IGNORANT  the probability that what is searched for exists, before the search and at every moment of it: a search
            that knows only its age learns nothing of that.
  pending   none that it can count: null (2026-11-12).

Quals: quals_lindy.py
"""
import sys
sys.dont_write_bytecode = True
import os, time
import chance, track

# dreeves, 2026-11-06: "go with 50% as the ignorant prior when there's no model or whatever"
IGNORANT = 0.5


def estimate(age):
    """The estimate, without its time, of a search whose age is age seconds."""
    lo, median, hi = (age * q / (1 - q) for q in (chance.BANDS['gott'][0], 0.5, chance.BANDS['gott'][1]))
    return dict(event='estimate', basis='lindy', unit='seconds', done=age, rate=1.0,
                total=dict(median=age + median, lo=age + lo, hi=age + hi), to_go=dict(median=median, lo=lo, hi=hi),
                prior=IGNORANT, exists=IGNORANT, pending=None)


if __name__ == '__main__':
    now = time.time()
    track.append(os.environ[track.RECORD], dict(estimate(track.running(track.search_of(os.environ[track.RECORD], now)[1], now)), time=now))
