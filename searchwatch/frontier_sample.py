#!/usr/bin/env python3
"""Sample a frozen form-tree frontier without reading or changing its live search.

    python3 -B searchwatch/frontier_sample.py SNAPSHOT.json NEW_OUTDIR WORKERS

Snapshot version1 contains target "N:M", nodes {name: relative_path}, sources
{relative_path: sha256}, and engine {library, wrapper, config, mods, want, fold,
alpha, wall_limit}. Paths resolve inside the snapshot directory. Every engine
file, config.Q.npy, and node must be source-hashed. Additional top-level metadata
is preserved in the output plan; it can describe the frozen verdict prefix and
original model. The wrapper is the frozen pex.py, exposing its usual API.

Eight full rounds probe every frozen node, even after the live search finishes
it. Nodes are hash-sorted into at most16 balanced groups, chosen before outcomes.
Each group-round block starts a fresh process, so native pools cannot carry
state between blocks. Within a block, members run in their fixed hash order.
For each group of K nodes, a block contains K times each member's dive estimate.
Its mean is the sum of those estimates: one stratified replicate of the group's
remaining work. This preserves the block-mean bootstrap format.
The group count is a computational limit, not a claimed optimal stratification.

All probes are logged, including a failed probe before refusal. A nonzero engine
return, OPEN node, nonfinite estimate or elapsed engine time reaching the limit
fails loudly and leaves no model-blocks.json. No censored probe is dropped. The
time limit is conservative: an expansion can overrun even when its path closes,
and that result is still refused because the API exposes no separate censor bit.

This file collects observations; it does not calibrate uncertainty or publish an
ETA. Knuth estimates concern the dive traversal; agreement with the actual search
tree remains a modeling assumption to evaluate separately.
"""
import sys
sys.dont_write_bytecode = True
# TODO: refuse optimized Python, which would remove source and sampling assertions.
if not __debug__: raise SystemExit('Assertiones requiruntur.')
import ctypes
import hashlib
import importlib.util
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
import time

ROUNDS, GROUPS = 8, 16
PROTOCOL = 'fresh-group-round-v1'
ENGINE = {'library','wrapper','config','mods','want','fold','alpha','wall_limit'}


def sha(data): return hashlib.sha256(data).hexdigest()


def number(value): return type(value) in (int,float) and math.isfinite(value)


def seed(target, name, round_):
    """A fixed namespace: scheduling order never changes a probe's random seed."""
    return int.from_bytes(hashlib.sha256(f'frontier-sample-v1:{target}:{name}:{round_}'.encode()).digest()[:8], 'big')


def groups(names):
    """Disjoint balanced groups, with order fixed independently of observed outcomes."""
    assert names and len(names)==len(set(names)) and all(type(n) is str and n for n in names)
    ordered = sorted(names, key=lambda name: sha(name.encode()))
    count = min(GROUPS, len(ordered))
    return [dict(name=f'g{i:02}', members=ordered[i::count]) for i in range(count)]


def read_snapshot(path):
    """Read one explicitly frozen source set; no live path discovery or repair."""
    path = Path(path).resolve(); raw = path.read_bytes(); snapshot = json.loads(raw)
    assert snapshot['version']==1 and re.fullmatch(r'[1-9]\d*:[1-9]\d*', snapshot['target'])
    engine, nodes, sources = snapshot['engine'], snapshot['nodes'], snapshot['sources']
    assert set(engine)==ENGINE and nodes and sources
    assert type(engine['fold']) is int and engine['fold'] in (-1,0,1)
    assert number(engine['alpha']) and engine['alpha']>=0
    assert number(engine['wall_limit']) and engine['wall_limit']>0
    assert engine['mods'] and len(engine['mods'])==len(set(engine['mods']))
    assert all(type(m) is int and m>1 for m in engine['mods'])
    assert engine['want'] and len(engine['want'])==len(set(engine['want'])) and set(engine['want'])<=set(engine['mods'])
    assert all(type(n) is str and n and Path(n).name==n for n in nodes)
    required = {engine['library'], engine['wrapper'], engine['config'], engine['config']+'.Q.npy'} | set(nodes.values())
    assert required <= set(sources)
    assert all(type(p) is str and p and not Path(p).is_absolute() and '..' not in Path(p).parts for p in sources)
    assert all(type(h) is str and re.fullmatch('[0-9a-f]{64}',h) for h in sources.values())
    paths = {p: path.parent/p for p in sources}
    assert all(sha(p.read_bytes())==sources[name] for name,p in paths.items())
    return snapshot, paths, sha(raw)


def worker_init(snapshot, paths):
    """Each worker loads the same pinned wrapper/library and explicit engine settings."""
    global _PE, _SNAPSHOT, _PATHS
    _SNAPSHOT, _PATHS = snapshot, paths
    engine = snapshot['engine']
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name] = '1'
    os.environ['PE_LIB'] = str(paths[engine['library']])
    os.environ.pop('PEX_FOLD',None)
    if engine['fold'] != 0:
        os.environ['PEX_FOLD'] = str(engine['fold'])
    spec = importlib.util.spec_from_file_location('frontier_pex', paths[engine['wrapper']])
    _PE = importlib.util.module_from_spec(spec); spec.loader.exec_module(_PE)
    n,m = map(int,snapshot['target'].split(':'))
    _PE.init(n,m,engine['mods'],engine['want'],path=str(paths[engine['config']]),**_PE.RUN_INIT)
    _PE.run_settings()
    assert _PE.lib.pe_fold()==engine['fold']
    _PE.lib.pe_certfd(os.open(os.devnull,os.O_WRONLY))
    _PE.lib.pe_import(ctypes.c_double(engine['alpha']))


def probe(task):
    """Return the observation even if invalid, so the controller logs it before refusal."""
    round_, name = task
    engine = _SNAPSHOT['engine']; random_seed = seed(_SNAPSHOT['target'],name,round_)
    stats = (ctypes.c_double*4)(); cpu = time.process_time(); wall = time.monotonic()
    rc = _PE.lib.pe_dive_file(str(_PATHS[_SNAPSHOT['nodes'][name]]).encode(),
                              ctypes.c_double(engine['wall_limit']), ctypes.c_ulonglong(random_seed), stats)
    return dict(name=name, round=round_, seed=random_seed, rc=rc, estimate=stats[0],
                weighted_wall_cost=stats[1], engine_wall=stats[2], open=stats[3],
                cpu=time.process_time()-cpu, wall=time.monotonic()-wall,
                censored=stats[2]>=engine['wall_limit'])


def checked(row, limit):
    """No partial-path or OPEN estimate can enter a completed sampling model."""
    assert row['rc']==0 and row['open']==0 and row['censored'] is False
    assert all(number(row[k]) for k in ('estimate','weighted_wall_cost','engine_wall','open','cpu','wall'))
    assert row['estimate']>=1 and row['weighted_wall_cost']>=0 and 0<=row['engine_wall']<limit
    assert row['cpu']>=0 and row['wall']>=0
    return row


def preflight(snapshot, paths):
    """Fail an invalid initializer once, before Pool can repeatedly respawn workers."""
    process = mp.get_context('spawn').Process(target=worker_init,args=(snapshot,paths))
    process.start(); process.join()
    assert process.exitcode==0, process.exitcode


def block_init(snapshot, paths, output):
    """A worker owns exactly one block, with native state initialized only for it."""
    global _OUTPUT
    _OUTPUT = Path(output)
    worker_init(snapshot,paths)


def block_probe(task):
    """Log every completed probe in one append write, then reject any invalid one."""
    round_, group, members = task
    fd = os.open(_OUTPUT/'draws.jsonl',os.O_WRONLY | os.O_APPEND)
    try:
        for name in members:
            row = probe((round_,name)) | dict(group=group)
            data = (json.dumps(row,allow_nan=False)+'\n').encode()
            assert os.write(fd,data)==len(data)
            checked(row,_SNAPSHOT['engine']['wall_limit'])
    finally:
        os.close(fd)
    return len(members)


def blocks(group_rows, rows):
    """Eight complete stratified replicates per group, never a partial average."""
    names = [n for g in group_rows for n in g['members']]
    assert names and len(names)==len(set(names))
    by = {(r['name'],r['round']):r['estimate'] for r in rows}
    assert len(by)==len(rows) and set(by)=={(n,i) for n in names for i in range(ROUNDS)}
    assert all(number(v) and v>=1 for v in by.values())
    return [g | dict(blocks=[[len(g['members'])*by[n,i] for n in g['members']] for i in range(ROUNDS)])
            for g in group_rows]


def run(snapshot_path, output, workers):
    """Collect a new immutable result directory; interrupted runs retain their probe log."""
    assert type(workers) is int and workers>0
    snapshot, paths, digest = read_snapshot(snapshot_path)
    preflight(snapshot,paths)
    output = Path(output); output.mkdir(exist_ok=False)
    grouped = groups(list(snapshot['nodes']))
    sampler = Path(__file__).read_bytes(); sampler_digest = sha(sampler)
    (output/'sampler.py').write_bytes(sampler)
    plan = dict(protocol=PROTOCOL, snapshot=snapshot, snapshot_sha256=digest, sampler_sha256=sampler_digest,
                rounds=ROUNDS, workers=workers, groups=grouped)
    (output/'groups.json').write_text(json.dumps(plan,indent=2)+'\n')
    tasks = [(i,g['name'],g['members']) for i in range(ROUNDS) for g in grouped]
    (output/'draws.jsonl').touch(exist_ok=False)
    completed = 0
    with mp.get_context('spawn').Pool(workers,initializer=block_init,initargs=(snapshot,paths,output),
                                     maxtasksperchild=1) as pool:
        for count in pool.imap_unordered(block_probe,tasks,chunksize=1):
            completed += count
    rows = [checked(json.loads(line),snapshot['engine']['wall_limit'])
            for line in (output/'draws.jsonl').read_text().splitlines()]
    assert completed==len(rows)
    _, _, after = read_snapshot(snapshot_path)
    assert after==digest
    result = dict(protocol=PROTOCOL, snapshot_sha256=digest, sampler_sha256=sampler_digest,
                  draws_sha256=sha((output/'draws.jsonl').read_bytes()),
                  rounds=ROUNDS, groups=blocks(grouped,rows))
    (output/'model-blocks.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(probes=len(rows),groups=len(grouped),cpu=sum(r['cpu'] for r in rows),
                          model=str(output/'model-blocks.json'))),flush=True)


if __name__ == '__main__':
    # TODO: usage: supply the frozen snapshot, a new output directory, and worker count.
    assert len(sys.argv)==4, 'Usus: frontier_sample.py SNAPSHOT.json OUTDIR OPERARII'
    run(sys.argv[1],sys.argv[2],int(sys.argv[3]))
