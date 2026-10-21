"""Astra's exact preparation of the all-sign672:13 proof search.

The complete mod2/3/5/7 residue enumeration leaves two parent profiles. Their
mod5 plus counts are(130,5,67,67,67) and(5,130,67,67,67); no sign symmetry is
assumed. Each parent has25 admissible mod4 profiles. Exact integer congruences
exclude16 and exact LP certificates exclude8, leaving only(84,84,84,84).

The integer congruences are discovered by Hermite normal form, then checked
directly against every matrix column. Those column checks suffice for their
necessity: each modular row annihilates every integer combination of columns,
and each equality row annihilates every rational combination. Numerical LP
infeasibility excludes a profile only when certbb.verify accepts the integer
certificate. Preparation therefore regenerates and checks all50 exclusions
or retained profiles; it uses no scratch files or previously trusted verdicts.
The two retained cases still require a search. This module proves no upper
bound on m*(672) by itself.
"""
import itertools

import certbb
import mstar
from overnight_v5 import ExactSystem


def profiles(M):
    """Every necessary plus-count vector moduloM for length672 and order13."""
    signed = mstar.residue_vectors(672, M, 13, None, mstar.Budget(10 ** 6), 'natural')
    return tuple(tuple((d + len(range(r, 672, M))) // 2 for r, d in enumerate(D)) for D in signed)


def reduce():
    """Return exact equations, retained root cases, and checked reduction counts."""
    from focus import moments
    equations = moments(672, 13)
    moduli = (2, 3, 5, 7)
    parents = tuple(tuple(zip(moduli, choice)) for choice in itertools.product(*(profiles(M) for M in moduli)))
    assert len(parents) == 2
    children = profiles(4)
    assert len(children) == 25
    initial = parents[0] + ((4, children[0]),)
    sparse = certbb.node_rows(equations, initial)
    A = []
    for row, _ in sparse:
        dense = [0] * 672
        for p, c in row:
            dense[p] = c
        A.append(dense)
    system = ExactSystem(A)
    columns = tuple(zip(*A))
    # Every actual column is a positive control for each necessary congruence.
    assert all(sum(q * a for q, a in zip(row, col)) % system.den == 0
               for row in system.F for col in columns)
    assert all(sum(q * a for q, a in zip(row, col)) == 0
               for row in system.E for col in columns)
    lp = certbb.Lp(equations, moduli + (4,))
    retained = []
    counts = dict(parents=len(parents), profiles=0, integer=0, lp=0)
    for parent in parents:
        for vector in children:
            counts['profiles'] += 1
            child = parent + ((4, vector),)
            rhs = tuple(b for _, b in certbb.node_rows(equations, child))
            compatible = (all(sum(q * b for q, b in zip(row, rhs)) % system.den == 0 for row in system.F)
                          and all(sum(q * b for q, b in zip(row, rhs)) == 0 for row in system.E))
            if not compatible:
                counts['integer'] += 1
                continue
            if vector == (84, 84, 84, 84):
                retained.append(child)
                continue
            lp.set_counts(child)
            status, ray = lp.solve([0] * 672, [1] * 672)
            assert status == 'Infeasible' and ray is not None, (vector, status)
            certificate = lp.multipliers(ray)
            certbb.verify(equations, tuple((M, (v,)) for M, v in child), [('L', certificate)])
            counts['lp'] += 1
    assert len(retained) == len(parents)
    assert counts == dict(parents=2, profiles=50, integer=32, lp=16)
    return equations, tuple(retained), counts


def prepare():
    """The runner's verified equations-and-cases contract."""
    return reduce()[:2]
