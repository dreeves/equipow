"""Explicit preparation for the scratch GMP lower-bound experiment."""
import hashlib
import pickle

import _native_bound


class Bound:
    """Own one immutable copied sparse-row snapshot, independent of caller mutation."""
    def __init__(self, rows, size):
        self._bound = _native_bound.prepare(rows, size)
        self.rows = tuple((tuple(tuple(term) for term in a), b) for a, b in rows)
        self.size = size
        self.fingerprint = hashlib.sha256(pickle.dumps((size, self.rows), protocol=5)).hexdigest()

    def evaluate(self, lo, hi, multipliers):
        return _native_bound.evaluate(self._bound, lo, hi, multipliers)


def make(rows, size):
    """Prepare once; match lower_bound's signature with an immutable rows-identity guard."""
    assert type(rows) is tuple
    assert all(type(row) is tuple and len(row) == 2 for row in rows)
    assert all(type(a) is tuple and all(type(term) is tuple for term in a) for a, _ in rows)
    bound = Bound(rows, size)

    def lower_bound(rows_arg, lo, hi, multipliers):
        assert rows_arg is rows
        return bound.evaluate(lo, hi, multipliers)

    lower_bound.bound = bound
    lower_bound.fingerprint = bound.fingerprint
    return lower_bound
