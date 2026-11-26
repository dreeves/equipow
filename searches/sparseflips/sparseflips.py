"""Search 33360:15 by flipping 148 pairs in the alternating sign sequence.

Each trial chooses a new pool of possible left-half positions. CP-SAT enforces
all odd centered moments and the mod-3, mod-5 and mod-7 class sums. Only this
pool and profile are searched in a trial. A timeout gives no exclusion.
Run: python3 -B sparseflips.py SEED POOL_SIZE TRIALS SECONDS_PER_TRIAL FOUND.jsonl
Requires OR-Tools. Each invocation uses one solver thread.
"""
import json
import random
import sys
from functools import cache
from itertools import product
from math import comb
from pathlib import Path

from ortools.sat.python import cp_model


def alternating(i):
    return 1 - 2*(i % 2)


def seven_profiles():
    """The six mod-7 profiles: D=49d, antisymmetric about residue 2."""
    n = 33360
    sizes = [len(range(r, n, 7)) for r in range(7)]
    baseline = [alternating(r) * (s % 2) for r, s in enumerate(sizes)]
    profiles = []
    for a, b, c in product(range(-12, 13), repeat=3):
        d = (a, b, 0, -b, -a, c, -c)
        row = tuple(49*x for x in d)
        if (all((x-s) % 2 == 0 for x,s in zip(row, sizes))
                and all(sum(r**k*x for r,x in enumerate(d)) % 7 == 0 for k in (1, 2))
                and sum(abs(x-y) for x,y in zip(row, baseline)) <= n-2**15):
            profiles.append(row)
    assert len(profiles) == 6
    return profiles


@cache
def moments(n, m):
    """Columns of the project's integer odd centered basis, with alternating signs.

    At left position i the outward index is j=n/2-i. The coordinates have
    degrees 1,3,...,m-2. Mirroring negates signs, so these alone suffice.
    """
    rows = []
    for k in range(m//2):
        weights = [alternating(i) * (comb(j+k,2*k+1) + comb(j+k-1,2*k+1))
                   for i,j in enumerate(range(n//2,0,-1))]
        total = sum(weights)
        assert total % 2 == 0
        rows.append((weights,total//2))
    return rows


def equation(model, flips, weights, target, count):
    """Impose an exact integer dot product, splitting it into signed base-256
    digits when too large for CP-SAT. Since exactly count bits are on, each
    carry's absolute value is at most count+1, independently of the row.
    """
    dot = cp_model.LinearExpr.weighted_sum
    if sum(map(abs, weights)) + abs(target) < 2**58:
        model.add(dot(flips, weights) == target)
        return
    top = max(abs(target), max(map(abs, weights))).bit_length()
    carry = 0
    for shift in range(0, top, 8):
        digits = [((w>0)-(w<0)) * ((abs(w) >> shift) & 255) for w in weights]
        digit = ((target>0)-(target<0)) * ((abs(target) >> shift) & 255)
        following = model.new_int_var(-count-1, count+1, '')
        model.add(dot(flips, digits) + carry == digit + 256*following)
        carry = following
    model.add(carry == 0)


def solve(n, m, pool, profiles, seconds):
    assert m % 2 == 1 and n % 4 == 0 and n >= 2**m and (n-2**m) % 4 == 0
    assert pool and len(set(pool)) == len(pool) and 0 <= min(pool) <= max(pool) < n//2
    count = (n-2**m)//4
    model = cp_model.CpModel()
    bits = [model.new_bool_var('') for i in pool]
    model.add(sum(bits) == count)
    for p, profile in profiles.items():
        assert len(profile) == p
        for r, required in enumerate(profile):
            baseline = alternating(r) * (len(range(r,n,p)) % 2)
            weights = [2*alternating(i) * (int(i%p == r) - int((n-1-i)%p == r))
                       for i in pool]
            model.add(cp_model.LinearExpr.weighted_sum(bits, weights) == baseline-required)
    for row, target in moments(n, m):
        equation(model, bits, [row[i] for i in pool], target, count)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.max_time_in_seconds = seconds
    assert not model.validate(), model.validate()
    status = solver.solve(model)
    assert status in (cp_model.UNKNOWN, cp_model.INFEASIBLE, cp_model.OPTIMAL)
    chosen = [i for i,b in zip(pool,bits) if solver.value(b)] if status == cp_model.OPTIMAL else []
    return solver.status_name(status), chosen, solver.num_branches


def verify(n, m, flips):
    """Rebuild the entire sequence and check its ordinary moments with Python integers."""
    chosen = set(flips)
    assert len(flips) == len(chosen) == (n-2**m)//4
    assert chosen <= set(range(n//2))
    left = [alternating(i) * (1-2*(i in chosen)) for i in range(n//2)]
    word = left + [-a for a in reversed(left)]
    assert sum(alternating(i)*a for i,a in enumerate(word)) == 2**m
    assert all(sum(a*i**k for i,a in enumerate(word)) == 0 for k in range(m))
    return word


def campaign(seed, width, trials, seconds, found):
    n, m = 33360, 15
    assert 148 <= width <= n//2 and trials > 0 and seconds > 0
    rng = random.Random(seed)
    profiles = seven_profiles()
    for trial in range(trials):
        index = (seed+trial) % len(profiles)
        pool = sorted(rng.sample(range(n//2), width))
        record = dict(seed=seed, trial=trial, width=width, profile=index)
        print(json.dumps(record), flush=True)
        status, flips, branches = solve(n, m, pool, {3:[0]*3,5:[0]*5,7:profiles[index]}, seconds)
        print(json.dumps(dict(record,status=status,branches=branches)), flush=True)
        if flips:
            verify(n, m, flips)
            with found.open('x') as out:
                print(json.dumps(dict(record,n=n,m=m,flips=flips)), file=out)
            return


if __name__ == '__main__':
    seed, width, trials, seconds = map(int, sys.argv[1:5])
    campaign(seed, width, trials, seconds, Path(sys.argv[5]))
