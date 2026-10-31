"""fastlp: the dense bounded dual simplex of proto.py, compiled (_fastlp.c, built by build.py), for certbb's
branch-and-bound LP.  Dual(A, b) is _fastlp.Dual with the perturbed costs (see proto.py's 'cost': 1 + r_j, r_j uniform
in [0, 1) from PERTURBATION_SEED, the same draw as proto.costs) and an iteration limit of LIMIT per solve, HiGHS's
certbb.ITERATIONS.  The C source beside the compiled module and the module itself are pinned by their SHA-256 at
import (build.py's output is byte-reproducible); certbb pins this file in turn."""
import hashlib
from pathlib import Path

import numpy as np

import _fastlp

PERTURBATION_SEED = 20261030
LIMIT = 20000
SOURCE_SHA256 = '0c4f32049f5d2c65755d88dfcf55b9710af3713fc0985f1ea69bca56a91a3a75'      # _fastlp.c
BINARY_SHA256 = 'd89870a259390fb1abaa795f5a5ce8afaca2ac4a886eb17c193ecf06a68ebd92'      # its build by build.py
BINARY = Path(_fastlp.__file__)
# TODO: error copy; says the compiled LP backend is not the pinned build
assert hashlib.sha256(BINARY.read_bytes()).hexdigest() == BINARY_SHA256, f'Claude: "{BINARY} is not the pinned build"'
# TODO: error copy; says the LP backend's C source beside it is not the pinned source
assert hashlib.sha256((BINARY.parent / '_fastlp.c').read_bytes()).hexdigest() == SOURCE_SHA256, \
    f'Claude: "{BINARY.parent / "_fastlp.c"} is not the pinned source"'


def costs(n):
    return 1.0 + np.random.default_rng(PERTURBATION_SEED).random(n)


class Dual(_fastlp.Dual):
    """_fastlp.Dual for the rows A (m x n) and right-hand sides b, with this module's costs and limit."""
    def __init__(self, A, b):
        A = np.ascontiguousarray(A, dtype=float)
        super().__init__(A, np.ascontiguousarray(b, dtype=float), costs(A.shape[1]), LIMIT)

    def load_highs(self, col, row):
        """The basis of HiGHS's status codes for the columns and the rows (as proto.Dual.load_highs)."""
        self.load(np.concatenate([col, row]).astype(np.int8))
