"""Quals for Claude's exact proof that m*(1456) <= 11 (proofs/proof1456.py, 2026-11-07).

Replicata: run the proof; damage its certificate; apply its first step at a length where sequences of the order exist
(544:10); apply its certificate test to the page's sequences of order 12 and more, with their own signs; read the page's
Asymptotics section.
Expectata: the proof passes and prints its conclusion; any one damaged coefficient is refused; at 544:10 the residue sums
mod 3 force no class; a known sequence of order >= 12 gives sum_i f_i P(i) = 0 exactly for P built from any 12
coefficients (so the argument cannot refute a real sequence); and the page states m*(1456) = 11 and links the proof.
Resultata before: proofs/proof1456.py did not exist, and the page did not mention 1456.
    python3 -B quals/quals_proof1456.py"""
import sys
sys.dont_write_bytecode = True
import os, re, random, subprocess
from math import comb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'proofs'))
sys.path.insert(0, os.path.join(ROOT, 'quals'))


def proof():
    import proof1456
    return proof1456


def q_the_proof_runs():
    r = subprocess.run([sys.executable, '-B', os.path.join(ROOT, 'proofs', 'proof1456.py')], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0 and 'No sequence of length 1456 has order 12.' in r.stdout, (r.returncode, r.stdout, r.stderr[-500:])


def q_a_damaged_certificate_is_refused():
    p = proof()
    for k in range(len(p.PSI)):
        bad = list(p.PSI); bad[k] = (bad[k] + 1) % p.Q
        try:
            p.check(bad)
        except AssertionError:
            continue
        raise AssertionError(f'a certificate damaged at {k} passed')


def q_no_class_is_forced_where_sequences_exist():
    # 544:10 (the page's p544): the same first step leaves the residue sums mod 3 at +-(162, -81, -81), below the
    # class sizes (182, 181, 181), so it forces no class there.
    p = proof()
    assert p.profiles(544, 10) == [(-162, 81, 81), (162, -81, -81)], p.profiles(544, 10)


def q_real_sequences_meet_every_test_polynomial():
    # For a sequence of order >= 12, sum_i f_i P(i) = 0 for P = sum_{k<12} c_k C(i, k), any integer c: so the second step
    # can only refute sequences that do not exist.  The page's codes of order >= 12 at lengths not divisible by 3 would be
    # the sharpest test, but there are none; these are the page's 480:12, 720:13 and 1440:16, with PSI and random c.
    import quals_tilted
    page = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    rnd = random.Random(1456)
    p = proof()
    for n, m in ((480, 12), (720, 13), (1440, 16)):
        [code] = re.findall(rf'<code id="{n}:{m}">([0-9A-F]+)</code>', page)
        f = quals_tilted.decode(code, n, m)
        assert quals_tilted.order_div(f) >= 12
        for c in [p.PSI] + [[rnd.randrange(-10 ** 6, 10 ** 6) for _ in range(12)] for _ in range(3)]:
            assert sum(a * sum(ck * comb(i, k) for k, ck in enumerate(c)) for i, a in enumerate(f)) == 0, (n, m)


def q_the_page_states_and_links_it():
    page = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    section = re.search(r'<section class="asymptotics".*?</section>', page, re.S)
    assert section, 'no section asymptotics'
    text = section.group(0)
    assert 'm^*(1456) = 11' in text, 'no m*(1456) = 11'
    assert 'https://github.com/dreeves/equipow/blob/main/proofs/proof1456.py' in text, 'no link to proof1456.py'
    psi = re.search(r'\\psi = \(((?:[0-9]+,\\allowbreak )*[0-9]+)\)', text)   # breakable after each comma on a phone
    assert psi and [int(x) for x in psi.group(1).split(',\\allowbreak ')] == proof().PSI, psi and psi.group(1)


if __name__ == '__main__':
    names = sys.argv[1:] or [k for k in list(globals()) if k.startswith('q_')]
    bad = 0
    for name in names:
        try:
            globals()[name]()
            print('PASSED', name, flush=True)
        except Exception as e:
            bad += 1
            print('FAILED', name, type(e).__name__, str(e)[:300], flush=True)
    print(f'{len(names) - bad} of {len(names)} passed')
