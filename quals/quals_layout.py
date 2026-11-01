#!/usr/bin/env python3
"""Quals for where the quals are ([FAC] stage 2, 2026-10-31; dreeves's README: "[FAC] Reorganize the files: quals and
search stuff in their own directories"): in quals/, each finding the repository's root by its own location, so that
each runs as it did at the root; and that the root's pages link files that are here ([FAC] stage 3a, 2026-10-31: the
finished searches into searches/, the proofs and certificates into proofs/).
Run: python3 -B quals/quals_layout.py [name ...]   (no arguments: all quals).

Each qual is a function q_*: a passing qual returns, a failing one raises.  Each qual's comment gives its replicata (the
setup) and expectata (what must happen); a failure's message or traceback gives the resultata (what happened instead)."""
import sys
sys.dont_write_bytecode = True
import os, re, subprocess, tempfile, time, traceback, urllib.parse
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above quals/
QUALS = os.path.join(HERE, 'quals')
# The two quals that proof384.html links, telling its reader to save them beside it, and whose own qual checks that
# they are there (quals_proof384_page's test_sources_and_reproduction_commands_are_published): they stay at the root.
STAY = ('quals_proof384.py', 'quals_proof384_page.py')
PYLIB = os.path.join(HERE, 'scratch', 'lower24-design', 'beyond1000', 'pylib')   # fpylll, as the suites run with it
# A qual's module-level code run as `python3 FILE` runs it (its own directory first on sys.path), but under a name other
# than __main__, so that its quals do not run: its imports among that code.
IMPORT = ('import runpy, os, sys\n'
          'sys.path.insert(0, os.path.dirname(sys.argv[1]))\n'
          'runpy.run_path(sys.argv[1], run_name="quals_layout_import")\n')


def q_quals_are_in_quals():
    # Replicata: the names in the repository's root and in its quals/.
    # Expectata (2026-10-31): no file at the root named quals_* but the two of STAY; in quals/ only quals: the suites
    # (*.py), the Node harnesses (*.cjs) and the data the stall quals read (quals_case_lp_stall.json), all named quals_*.
    # Resultata before the move: 66 more quals_* files at the root, and no quals/.
    root = sorted(n for n in os.listdir(HERE) if n.startswith('quals_'))
    assert root == sorted(STAY), root
    there = sorted(n for n in os.listdir(QUALS) if not n.startswith('.') and n != '__pycache__')
    assert len(there) > 60 and all(n.startswith('quals_') and n.endswith(('.py', '.cjs', '.json')) for n in there), there


def q_python_quals_import_from_anywhere():
    # Replicata: each quals/*.py but this one, its module-level code run (IMPORT) in a fresh Python whose working
    # directory and TMPDIR are an empty temporary directory, PYTHONPATH PYLIB.
    # Expectata: every one runs: each that imports the repository's modules puts the root on sys.path itself, by its own
    # location, and its quals/ neighbours import as Python puts its own directory first.
    # Resultata before the move: no quals/ to run them from.
    names = sorted(n for n in os.listdir(QUALS) if n.endswith('.py') and n != 'quals_layout.py')
    assert len(names) > 50, names
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, PYTHONPATH=PYLIB, TMPDIR=d)
        run = lambda n: subprocess.run([sys.executable, '-B', '-c', IMPORT, os.path.join(QUALS, n)], cwd=d, env=env,
                                       capture_output=True, text=True, timeout=900)
        with ThreadPoolExecutor(4) as pool:
            done = list(pool.map(run, names))
    bad = [(n, p.returncode, p.stderr[-1500:]) for n, p in zip(names, done) if p.returncode]
    assert not bad, bad


def q_harnesses_run_from_anywhere():
    # Replicata: each quals/*.cjs run by node in an empty temporary working directory.
    # Expectata: each passes (exit 0): each reads the page's files from the root, above its own directory.
    # Resultata before the move: the harnesses read index.html and page/ from the working directory.
    names = sorted(n for n in os.listdir(QUALS) if n.endswith('.cjs'))
    assert len(names) > 4, names
    with tempfile.TemporaryDirectory() as d:
        done = [subprocess.run(['node', os.path.join(QUALS, n)], cwd=d, capture_output=True, text=True, timeout=120)
                for n in names]
    bad = [(n, p.returncode, p.stdout[-800:] + p.stderr[-800:]) for n, p in zip(names, done) if p.returncode]
    assert not bad, bad


# The root's pages' links into this repository (see q_page_links_resolve): (a URL's prefix, whether what follows it
# names a file, or else a directory).
REPOSITORY = (('https://github.com/dreeves/equipow/blob/main/', True),
              ('https://raw.githubusercontent.com/dreeves/equipow/main/', True),
              ('https://github.com/dreeves/equipow/tree/main/', False), ('https://equipow.dreev.es/', True))


def q_page_links_resolve():
    # Replicata ([FAC] stage 3a, 2026-10-31: the finished searches into searches/, the proofs and certificates into
    # proofs/): each href and src of the root's two pages, index.html and proof384.html.
    # Expectata: each that names a file or directory of this repository names one that is here, its fragment and query
    # left out and its path percent-decoded: a relative one, a file under the root; one at a prefix of REPOSITORY, the
    # file or directory there under the root; the repository's page at GitHub, the root.  The links to GitHub are
    # checked against the files here, not over the network: they resolve once these files are pushed.
    # Resultata before the page's edits: index.html linked proof512.txt, record_gaps.wl and eight more at the root,
    # where they no longer were.
    urls = [u for page in ('index.html', 'proof384.html')
            for u in re.findall(r'\s(?:href|src)="([^"]*)"', open(os.path.join(HERE, page), encoding='utf-8').read())]
    path = lambda u: urllib.parse.unquote(u.split('#')[0].split('?')[0])
    named = ([(path(u), True) for u in urls if not re.match(r'[a-z]+:|#', u)] +
             [(path(u[len(p):]), file) for u in urls for p, file in REPOSITORY if u.startswith(p)] +
             [('', False) for u in urls if u == 'https://github.com/dreeves/equipow'])
    assert len(named) > 25, named
    missing = [(p, file) for p, file in named if not (os.path.isfile if file else os.path.isdir)(os.path.join(HERE, p))]
    assert not missing, missing


def main():
    names = sys.argv[1:] or [n for n in globals() if n.startswith('q_')]
    failed = 0
    for n in names:
        t0, c0 = time.time(), time.process_time()
        try:
            globals()[n]()
            # TODO: runner line; says the named qual passed, with its seconds and this process's CPU seconds
            print(f'Claude: "PASSED" {n} ({time.time() - t0:.1f} s, {time.process_time() - c0:.1f} CPU s)', flush=True)
        except Exception:
            failed += 1
            # TODO: runner line; says the named qual failed, with its seconds and this process's CPU seconds, followed by the traceback
            print(f'Claude: "FAILED" {n} ({time.time() - t0:.1f} s, {time.process_time() - c0:.1f} CPU s)\n' + traceback.format_exc(), flush=True)
    # TODO: runner summary; says how many quals passed out of how many
    print(f'Claude: "{len(names) - failed} of {len(names)} passed"')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
