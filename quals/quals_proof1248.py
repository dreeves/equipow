"""Codex quals for the universal upper bound m*(1248) <= 13.

Replicata: run the isolated checker; independently enumerate cyclotomic
profiles; damage each coefficient; apply its polynomial to a known sequence.
Expectata: the proof passes without packages, both profile methods agree,
damaged certificates fail, an order-M Thue-Morse sequence annihilates P,
and the page's existing product attains order 13 at length 1248.
Resultata before: proofs/proof1248.py did not exist. The later order-14
exclusion quals were red against the first checker, which excluded only 15.
"""
import importlib.util
import subprocess
import sys
import re
from itertools import product
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def proof():
    spec = importlib.util.spec_from_file_location('proof1248', ROOT/'proofs/proof1248.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def q_isolated_checker_runs():
    result = subprocess.run([sys.executable, '-B', '-I', '-S',
                             str(ROOT/'proofs/proof1248.py')],
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr


def q_profiles_match_cyclotomic_divisibility():
    p = proof()
    # Phi_5=1+z+z^2+z^3+z^4. Repeated exact division by 1-z is
    # independent of the binomial congruences used by the production proof.
    mul = lambda a: (a[0]+a[3], a[1]-a[0]+a[3],
                     a[2]-a[1]+a[3], 2*a[3]-a[2])
    power = (1,0,0,0)
    for _ in range(12):
        power = mul(power)
    assert all(c % 125 == 0 for c in power)
    sizes = [len(range(r,p.N,5)) for r in range(5)]
    assert 2*max(sizes) <= 500
    profiles = []
    for a in product(range(-4,5), repeat=4):
        d4 = -25*sum(a)
        d = tuple(d4+125*t for t in a)+(d4,)
        if not all(abs(t)<=s and (t-s)%2 == 0 for t,s in zip(d,sizes)):
            continue
        b = tuple(d[r]-d[4] for r in range(4))
        for _ in range(p.M):
            if sum(b) % 5:
                break
            t = sum(b)//5
            quotient = (b[0]-t,b[0]+b[1]-2*t,b[0]+b[1]+b[2]-3*t,t)
            assert mul(quotient) == b
            b = quotient
        else:
            profiles.append(d)
    assert sorted(profiles) == p.profiles()


def q_corrupted_certificates_are_rejected():
    p = proof()
    damaged = [[c+int(j==k) for j,c in enumerate(p.PSI)] for k in range(p.M)]
    for psi in [[0]*p.M]+damaged:
        try:
            p.check(psi)
        except AssertionError:
            continue
        raise AssertionError(psi)


def q_known_sequence_annihilates_polynomial():
    p = proof()
    # Product (1-x^(2^j)), j=0,...,M-1, has exact order M.
    # Its signs are (-1)^popcount(i); every polynomial of degree < M
    # must have zero signed sum. This is a constructive positive control.
    assert sum((-1)**i.bit_count()*sum(c*comb(i,k) for k,c in enumerate(p.PSI))
               for i in range(1 << p.M)) == 0


def q_upper_bound_excludes_order14():
    # The second discovery rules out order 14 itself, not just order 15.
    p = proof()
    assert p.M == 14
    p.check()


def q_every_profile_certificate_rejects_damage():
    p = proof()
    for profile, modulus, psi, residue in p.CERTIFICATES:
        for k in range(len(psi)):
            damaged = list(psi)
            damaged[k] += 1
            try:
                p.check_profile(profile, modulus, damaged, residue)
            except AssertionError:
                continue
            raise AssertionError((profile,k))


def q_existing_product_attains_order13():
    # (1-x) p624(x^2), constructed from the page's one copy of p624.
    [code] = re.findall(r'<code id="624:12">([0-9A-F]+)</code>',
                        (ROOT/'index.html').read_text())
    half = [2*int(bit)-1 for bit in bin(int(code,16))[2:].zfill(312)]
    base = half+half[::-1]
    signs = [a*b for a in base for b in (1,-1)]
    assert len(signs) == 1248
    moments = [sum(a*comb(i,k) for i,a in enumerate(signs)) for k in range(14)]
    assert moments[:13] == [0]*13 and moments[13] != 0


if __name__ == '__main__':
    for name in sys.argv[1:] or [k for k in list(globals()) if k.startswith('q_')]:
        globals()[name]()
        # TODO: Identify the qual that passed.
        print('PROBATUM', name)
