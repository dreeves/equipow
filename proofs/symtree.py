#!/usr/bin/env python3
"""Fable 5.2's exact check of a symmetric-only form tree: a proof that no s-symmetric sequence of length n has order m.
Python's standard library only: integers, no floats, no solver.  Written 2026-11-11 for dreeves's README, [SYC]: "cells
for which we know they're red conditional on the Symmetry Conjecture being true, i.e., we've proven there's no
symmetric or antisymmetric bipartition".

    python3 -B -I -S proofs/symtree.py DIR      one kept proof; no DIR: every proof of TREES

The claim.  No signs a_p in {-1, 1}, p = 0, ..., n-1, with a_(n-1-p) = s a_p for every p (s = 1: symmetric; s = -1:
antisymmetric), have sum_p a_p p^k = 0 for k = 0, ..., m-1.  Here s = (-1)^m: by the Symmetry clause of BGPW's
Theorem 4.1 and the remark that ends its proof (a symmetric or antisymmetric sequence of exact order k is
(-1)^k-symmetric), an s-symmetric sequence has an exact order of m's parity, so the claim rules out the s-symmetric
sequences of exact order m, m + 2, m + 4, ....

Vocabulary (with proofs/formtree.py's and proofs/pintree.py's, whose functions are used here).
  residue sums  D^(M)_r = sum_{p = r mod M} a_p, r = 0, ..., M-1.
  sigma         sigma(r) = (n-1-r) mod M: where p is of class r mod M, its mirror n-1-p is of class sigma(r).
  row           (M, value, weights): the form sum_r weights_r D^(M)_r pinned at value (formtree's pinned row).
  start node    a set of rows, named by formtree's node_name with G = 0 (no symmetry of the node is claimed).
  chain         the moduli 3, 5, 7, as in formtree's top.
  kept proof    a directory with nodes.json, {"cell": "n:m", "s": s, "nodes": [{"name": ..., "rows": [[M, value,
                [weights]], ...]}, ...]}, and verdicts.jsonl, fkernel's verdicts on the tasks under those start nodes,
                as formtree's assemble reads them.

The argument, in three steps.
  (1) Symmetry's rows.  For an s-symmetric sequence and any M, the mirror maps the positions of class r onto those of
      class sigma(r), so D^(M)_sigma(r) = s D^(M)_r.  Hence the form e_r - s e_sigma(r) is 0 on it for every r, and
      where sigma(r) = r and s = -1, D^(M)_r itself is 0.  (symmetric_row: the rows of those two kinds, and their
      negatives.)
  (2) The start nodes.  Every sequence of order m has, at each M of the chain, a vector of residue sums among
      pintree.vectors(n, m, M, {}) (pintree's (a) to (d)); an s-symmetric one has an s-symmetric vector there, by (1).
      The negative of an s-symmetric sequence of order m is one too, with the negated vectors.  So, up to its sign,
      every s-symmetric sequence of order m has the rows of some start node, if the start nodes are these: one for
      each pair {t, -t} of triples t of s-symmetric vectors at 3, 5, 7, its rows the unit weights of every class of
      the chain's moduli at t's values and, beyond them, rows of (1) only, each at 0.  check verifies exactly that of
      nodes.json, and that each node's name is the name of its rows.
  (3) The trees.  formtree's assemble on the start nodes' names and the verdicts: every start node and every node
      spilled on the way has an accepted verdict with no open node, with no cycle.  Then no sequence of order m has
      the rows of any start node (proofs/formtree.py's docstring), so by (2) no s-symmetric sequence has order m.

What is trusted.  Steps (1) and (2) are this file's; step (3) is proofs/formtree.py's assemble, which takes the
verdicts' word for what fkernel saw of each task, as it does for the kept proofs of single cells.  The rows of (1)
tell the trees of the symmetry only through the residue sums of the moduli they name; that weakens no step.

What it is for.  If BGPW's Symmetry Conjecture holds (a sequence of exact order k has a (-1)^k-symmetric one of exact
order k beside it), then m*(n) < m as soon as, for every k from m to the upper bound known for m*(n), no
(-1)^k-symmetric sequence of length n has exact order k: pagegen/mstar.py's ifsym works that out from TREES.
"""
import importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHAIN = (3, 5, 7)
# The kept proofs, by their directories in the repository: each a claim "no (-1)^m-symmetric sequence of length n has
# order m" that check accepts.  quals_symtree.q_every_kept_proof_is_accepted_and_named holds this list to the
# directories that are there.
TREES = ['searches/formtree/cells/480_14_sym', 'searches/formtree/cells/480_13_antisym']


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + '.py')); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


pt, ft = _load('pintree'), _load('formtree')


def sigma(n, M, r): return (n - 1 - r) % M


def symmetric_row(n, s, M, w):
    """Whether the weights w, a tuple of M integers, are one of symmetry's rows mod M for an s-symmetric sequence of
    length n, or the negative of one: e_r - s e_sigma(r) with sigma(r) another class than r; or e_r with sigma(r) = r
    and s = -1.  Each is 0 on every s-symmetric sequence (the docstring's (1))."""
    assert s in (1, -1) and type(M) is int and M >= 2 and len(w) == M and all(type(x) is int for x in w), (s, M, w)
    at = [r for r in range(M) if w[r]]
    pair = len(at) == 2 and sigma(n, M, at[0]) == at[1] and abs(w[at[0]]) == 1 and w[at[1]] == -s * w[at[0]]
    alone = len(at) == 1 and sigma(n, M, at[0]) == at[0] and s == -1 and abs(w[at[0]]) == 1
    return pair or alone


def symmetric_triples(n, m, s):
    """Every triple of s-symmetric vectors of residue sums at 3, 5, 7 that a sequence of length n and order m can have
    (pintree.vectors), as a tuple of three tuples."""
    lists = [[v for v in pt.vectors(n, m, M, {}) if all(v[sigma(n, M, r)] == s * v[r] for r in range(M))] for M in CHAIN]
    return [(a, b, c) for a in lists[0] for b in lists[1] for c in lists[2]]


def negated(t): return tuple(tuple(-x for x in v) for v in t)


def check(directory):
    """Checks the kept proof in directory: returns (n, m, s, assemble's totals), or raises ValueError where a step of
    the docstring's argument does not hold."""
    with open(os.path.join(directory, 'nodes.json'), encoding='utf-8') as f: data = json.load(f)
    if set(data) != {'cell', 's', 'nodes'}: raise ValueError('nodes.json holds the cell, s and the nodes')
    parts = str(data['cell']).split(':')
    if len(parts) != 2 or not all(p.isdigit() for p in parts): raise ValueError('the cell is n:m')
    n, m = int(parts[0]), int(parts[1]); s = data['s']
    ft.Cell(n, m)                                                     # n and m in the checkers' range
    if s != (1 if m % 2 == 0 else -1): raise ValueError('s is (-1)^m')
    triples = set(symmetric_triples(n, m, s))
    if any(negated(t) not in triples for t in triples): raise ValueError('the symmetric triples are closed under negation')
    names, covered = [], set()
    for node in data['nodes']:
        if set(node) != {'name', 'rows'}: raise ValueError('a node holds its name and its rows')
        rows = [(M, value, tuple(w)) for M, value, w in node['rows']]
        if not all(type(M) is int and M >= 2 and type(value) is int and len(w) == M and all(type(x) is int for x in w) for M, value, w in rows):
            raise ValueError('a row is a modulus, a value and a weight per class')
        vector = {M: [None] * M for M in CHAIN}
        for M, value, w in rows:
            if M in vector:
                if sorted(w) != [0] * (M - 1) + [1] or vector[M][w.index(1)] is not None: raise ValueError("a chain modulus's rows are its classes, each once")
                vector[M][w.index(1)] = value
            elif value != 0 or not symmetric_row(n, s, M, w): raise ValueError(f'a row beyond the chain is not one of symmetry\'s rows at 0: {(M, value, w)}')
        if any(x is None for M in CHAIN for x in vector[M]): raise ValueError('a start node pins every class of 3, 5 and 7')
        t = tuple(tuple(vector[M]) for M in CHAIN)
        if t not in triples: raise ValueError(f'a start node whose vectors at 3, 5, 7 are not symmetric ones of the cell: {t}')
        if t in covered: raise ValueError(f'two start nodes of one pair v, -v: {t}')
        covered.update((t, negated(t)))
        if ft.node_name(n, m, 0, rows) != node['name']: raise ValueError(f"a start node's name is not its rows': {node['name']}")
        names.append(node['name'])
    if covered != triples: raise ValueError(f'{len(triples - covered)} symmetric triples at 3, 5, 7 have no start node')
    with open(os.path.join(directory, 'verdicts.jsonl'), encoding='utf-8') as f: verdicts = [json.loads(line) for line in f]
    return n, m, s, ft.assemble(names, verdicts)                      # raises ValueError unless every node under them is closed


if __name__ == '__main__':
    root = os.path.dirname(HERE)
    for directory in sys.argv[1:] or [os.path.join(root, d) for d in TREES]:
        n, m, s, total = check(directory)
        # TODO: says the kept proof checks out: no symmetric (or antisymmetric) sequence of that length has that order, with the tasks' totals
        print(f'Fable 5.2: "VERIFIED: no {"symmetric" if s == 1 else "antisymmetric"} sequence of length {n} has order {m}.  Tasks {total}"')
