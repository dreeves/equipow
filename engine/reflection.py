"""Exact reversal of power-sum proof tokens; no numerical decisions."""
from functools import cache


@cache
def mapping(equations, counts):
    """Output multiplier positions and signs, checked once for these rows."""
    assert len(equations.W) == equations.order
    assert all(tuple(reversed(row)) == tuple((-1) ** k * x for x in row)
               and equations.rhs[k] == (-1) ** k * equations.rhs[k]
               for k, row in enumerate(equations.W))
    out = [(k, (-1) ** k) for k in range(equations.order)]
    for M, vector in counts:
        assert len(vector) == M
        offset = len(out)
        out.extend((offset + (equations.N - 1 - r) % M, 1) for r in range(M))
    return tuple(out)


def token(equations, counts, value):
    """Reverse a B/L/W token without changing the depth-first token order."""
    indices = mapping(equations, counts)

    def leaf(multipliers):
        assert len(multipliers) == len(indices)
        return [sign * multipliers[i] for i, sign in indices]

    kind, arg = value
    transforms = {'B': lambda p: equations.N - 1 - p,
                  'L': leaf,
                  'W': lambda x: x[::-1]}
    return kind, transforms[kind](arg)


def choice(equations, value):
    """Reverse residue counts; token mapping separately validates the equations."""
    return tuple((M, tuple(v[(equations.N - 1 - r) % M] for r in range(M))) for M, v in value)


def path(equations, value):
    return tuple((equations.N - 1 - p, t) for p, t in value)
