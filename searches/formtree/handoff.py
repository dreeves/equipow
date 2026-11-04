#!/usr/bin/env python3
"""A run's state as one file, to carry it to another machine or commit it.  The run must be stopped: a state taken while tasks finish could lose one.
    handoff.py save DIR OUT.tar.gz PROGRESS.json     after: python3 stopall.py ftree.py
    handoff.py restore IN.tar.gz DIR                 run.sh does this when DIR does not exist"""
import json, os, re, subprocess, sys, tarfile, time, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
NAME = re.compile(r'[0-9a-f]{32}$')


def running():
    for line in subprocess.run(['ps', '-A', '-o', 'args='], capture_output=True, text=True, check=True).stdout.splitlines():
        args = line.split()
        if args and 'python' in os.path.basename(args[0]) and any(a.endswith('ftree.py') for a in args[1:]): return True
    return False


def save(d, out, progress):
    assert not running(), 'stop the run first: python3 stopall.py ftree.py'
    spec = importlib.util.spec_from_file_location('formtree', os.path.join(HERE, '..', '..', 'proofs', 'formtree.py')); ft = importlib.util.module_from_spec(spec); spec.loader.exec_module(ft)
    verdicts = [json.loads(line) for line in open(os.path.join(d, 'verdicts.jsonl'))] if os.path.exists(os.path.join(d, 'verdicts.jsonl')) else []
    pending = sorted(os.listdir(os.path.join(d, 'pending')))
    assert all(NAME.match(f) for f in pending), 'a file in pending/ that is not a name'
    with tarfile.open(out + '.tmp', 'w:gz', compresslevel=9) as t:
        for f in ('verdicts.jsonl', 'audit.txt', 'open.log'):
            if os.path.exists(os.path.join(d, f)): t.add(os.path.join(d, f), arcname=f)
        for f in pending: t.add(os.path.join(d, 'pending', f), arcname='pending/' + f)
        for f in os.listdir(d):
            if f.startswith('open_node'): t.add(os.path.join(d, f), arcname=f)
    os.replace(out + '.tmp', out)
    ok = [v for v in verdicts if v['ok']]
    summary = dict(saved_utc=time.strftime('%Y-%m-%d %H:%M', time.gmtime()), tasks_done=len(ok), tasks_pending=len(pending), nodes=sum(v['nodes'] for v in ok), certificates=sum(v['certs'] for v in ok), open=sum(v['open'] for v in ok), rejected=len(verdicts) - len(ok), cpu_hours=round(sum(v.get('seconds', 0) for v in ok) / 3600, 1), python_sampled=sum(v.get('py') is not None for v in ok), python_differ=sum(v.get('py') is False for v in ok), snapshot_bytes=os.path.getsize(out))
    with open(progress, 'w') as f: json.dump(summary, f, indent=1); f.write('\n')
    print(summary)


def restore(src, d):
    assert not os.path.exists(os.path.join(d, 'verdicts.jsonl')), f'{d} already holds a run'
    os.makedirs(os.path.join(d, 'pending'), exist_ok=True)
    with tarfile.open(src, 'r:gz') as t:
        for member in t.getmembers():
            base, _, leaf = member.name.rpartition('/')
            assert member.isfile() and base in ('', 'pending') and '..' not in member.name, f'an odd member: {member.name}'
            with t.extractfile(member) as f, open(os.path.join(d, member.name), 'wb') as o: o.write(f.read())
    print(f'restored into {d}')


if __name__ == '__main__':
    if sys.argv[1] == 'save': save(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == 'restore': restore(sys.argv[2], sys.argv[3])
    else: raise ValueError(sys.argv[1])
