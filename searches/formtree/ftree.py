#!/usr/bin/env python3
"""A run of the form tree prover with every claim checked as it is made.  The engine's stream goes to fkernel, a separate process that trusts nothing from it, and a sample also to proofs/formtree.py.  Resumable at any moment.
Usage (run.sh does all this): ftree.py n:m top.json.gz procs limit want mods dir     env PE_LIB, FKERNEL

In dir:
  verdicts.jsonl  a line per finished task: the checker's verdict, the start case it descends from (root), the engine's seconds and LPs.  This is the proof's record: proofs/formtree.py assemble reads it.
  pending/NAME    the node of each task still to do, by its name.
  audit.txt       the nodes of a sample of tasks, for audit.py.
A task is done when its verdict line is in verdicts.jsonl.  What remains is worked out from that file alone, by walking down from the start nodes: a killed run loses only what was in flight, and a node's file is never looked up by anything but its name."""
import importlib.util, json, os, resource, shutil, subprocess, sys, time
import multiprocessing as mp
import pex as pe
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('formtree', os.path.join(HERE, '..', '..', 'proofs', 'formtree.py')); ft = importlib.util.module_from_spec(spec); spec.loader.exec_module(ft)
D = sys.argv[7]; PENDING = os.path.join(D, 'pending'); SPILL = os.path.join(D, 'spill'); K = None
PY_SAMPLE, AUDIT_SAMPLE = int(os.environ.get('PY_SAMPLE', '2000')), 100     # one task in so many: by the name, so a resumed run samples the same ones
STREAM_LIMIT = 64 << 20                                                     # a sampled stream longer than this is not given to the Python checker as well
GIB = 1 << 30


def limit_process(gib):
    """Nothing here may take the machine down: a process that passes this fails alone."""
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if sys.platform != 'linux': return      # macOS does not enforce address-space limits
    hard = resource.getrlimit(resource.RLIMIT_AS)[1]; want_ = gib * GIB if hard == resource.RLIM_INFINITY else min(gib * GIB, hard)
    resource.setrlimit(resource.RLIMIT_AS, (want_, want_))


def worker_init(n, m, mods, want):
    global K
    limit_process(3)
    pe.init(n, m, mods, want, **pe.RUN_INIT); pe.run_settings(); pe.lib.pe_openprefix(os.path.join(D, 'open_node').encode())
    K = subprocess.Popen([os.environ['FKERNEL']], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    pe.lib.pe_certfd(os.dup(K.stdin.fileno()))


def job(a):
    name, limit, logp = a
    path = os.path.join(PENDING, name); prefix = os.path.join(SPILL, str(os.getpid())); tmp = prefix + '.stream'
    sampled = int(name[:8], 16) % PY_SAMPLE == 0
    text = None
    if int(name[8:16], 16) % AUDIT_SAMPLE == 0:
        with open(path) as f: text = f.read()
    if sampled: pe.lib.pe_certfd(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644))
    r = pe.run_file(path, limit, logp, prefix)
    py = None
    if sampled:
        pe.lib.pe_certfd(os.dup(K.stdin.fileno()))
        with open(tmp, 'rb') as f: shutil.copyfileobj(f, K.stdin)
        K.stdin.flush()
    v = json.loads(K.stdout.readline())
    if sampled:
        if os.path.getsize(tmp) <= STREAM_LIMIT:
            p = subprocess.run([sys.executable, '-B', '-I', '-S', os.path.join(HERE, '..', '..', 'proofs', 'formtree.py'), 'check', tmp], capture_output=True, text=True)
            lines = p.stdout.splitlines()
            py = len(lines) == 1 and json.loads(lines[0]) == v
        os.remove(tmp)
    if v['ok']:
        for i, child in enumerate(v['spills']): os.replace(f'{prefix}_{i}', os.path.join(PENDING, child))
    return name, r, v, py, text


def read_verdicts(path):
    """The lines of verdicts.jsonl.  A kill can cut the last line short: that task runs again."""
    if not os.path.exists(path): return []
    with open(path, 'rb') as f: data = f.read()
    end = data.rfind(b'\n') + 1
    if end != len(data):
        print(f'{len(data) - end} bytes of a cut line dropped from {path}', flush=True)
        with open(path, 'r+b') as f: f.truncate(end)
    return [json.loads(line) for line in data[:end].splitlines()]


def remaining(starts, verdicts):
    """Walk down from the start nodes: {name: root} for each node with no accepted verdict, and the accepted verdicts on the way."""
    have = {v['start']: v for v in verdicts if v['ok']}
    todo, used, seen = {}, [], set()
    stack = [(s['name'], i) for i, s in enumerate(starts)]
    while stack:
        name, root = stack.pop()
        if name in seen: continue
        seen.add(name)
        v = have.get(name)
        if v is None: todo[name] = root
        else:
            used.append(v)
            stack.extend((child, root) for child in v['spills'])
    return todo, used


if __name__ == '__main__':
    limit_process(8)
    n, m = map(int, sys.argv[1].split(':')); procs, limit = int(sys.argv[3]), float(sys.argv[4]); want = [int(x) for x in sys.argv[5].split(',')]; mods = [int(x) for x in sys.argv[6].split(',')]
    tn, tm, starts, stats = ft.check_top(sys.argv[2])
    assert (tn, tm) == (n, m), 'the top is of another cell'
    print(f'top of {n}:{m}: {stats}', flush=True)
    for d in (D, PENDING, SPILL): os.makedirs(d, exist_ok=True)
    for f in os.listdir(SPILL): os.remove(os.path.join(SPILL, f))
    pe.init(n, m, mods, want)
    verfile = os.path.join(D, 'verdicts.jsonl'); logp = os.path.join(D, 'open.log')
    verdicts = read_verdicts(verfile)
    todo, used = remaining(starts, verdicts)
    tot = dict(nodes=0, closed=0, open=0, certs=0, lps=0, seconds=0.0)
    for v in used:
        for k in tot: tot[k] += v.get(k, 0)
    ck = dict(rejected=sum(not v['ok'] for v in verdicts), py=sum(v.get('py') is not None for v in verdicts), pybad=sum(v.get('py') is False for v in verdicts), wrong=0)
    root_pins = {s['name']: s['pins'] for s in starts}
    for name in todo:
        path = os.path.join(PENDING, name)
        if not os.path.exists(path):
            if name not in root_pins: raise SystemExit(f'the node {name} has no verdict and no file: its parent spilled it, so its file must be in pending/')
            pe.start_file(root_pins[name], path)
    for f in os.listdir(PENDING):
        if f not in todo: os.remove(os.path.join(PENDING, f))      # a killed task's children, or a task whose verdict came just before a kill
    del verdicts, used
    print(f'{len(starts)} start nodes; {len(todo)} tasks to run; {tot["nodes"]:.6g} nodes done', flush=True)
    T0 = time.time(); last = T0; nd = 0; ctx = mp.get_context('fork')
    with ctx.Pool(procs, initializer=worker_init, initargs=(n, m, mods, want)) as pool:
        pending = list(todo.items()); running = []; roots = dict(todo); began = {}
        fv = open(verfile, 'a'); fa = open(os.path.join(D, 'audit.txt'), 'a'); paused = False
        def submit():
            while pending and len(running) < procs + 4 and not paused:
                name, root = pending.pop(0); res = pool.apply_async(job, ((name, limit, logp),)); running.append(res); began[res] = time.time()
        submit()
        while running or pending:
            for res in list(running):
                if res.ready():
                    running.remove(res); began.pop(res); name, r, v, py, text = res.get(); root = roots.pop(name)
                    if v['start'] != name: ck['wrong'] += 1; print(f'NAME: the file of {name} is the node {v["start"]}', flush=True)
                    if not v['ok']: ck['rejected'] += 1; print(f'REJECTED {name}: {v["why"]}', flush=True)
                    elif len(v['spills']) != int(r['spilled']): ck['wrong'] += 1; print(f'{name}: the checker saw {len(v["spills"])} spills, the engine {int(r["spilled"])}', flush=True)
                    if py is not None: ck['py'] += 1; ck['pybad'] += py is False
                    if py is False: print(f'PYTHON DISAGREES on {name}', flush=True)
                    if text is not None: fa.write(f'#{name}\n{text}'); fa.flush()
                    v.update(root=root, py=py, seconds=round(r['seconds'], 2), lps=int(r['lps']))
                    fv.write(json.dumps(v, separators=(',', ':')) + '\n'); fv.flush()
                    if v['ok'] and v['start'] == name:
                        for k in tot: tot[k] += v.get(k, 0)
                        os.remove(os.path.join(PENDING, name))
                        kids = [(child, root) for child in v['spills']]; roots.update(kids); pending[:0] = kids
                    nd += 1
            submit()
            if time.time() - last > 60:
                last = time.time(); free = shutil.disk_usage(D).free; paused = free < 800 * 2 ** 20
                overdue = sum(1 for res in running if time.time() - began[res] > 20 * limit + 1200)
                print(f'[{time.time()-T0:.0f}s] done {nd}, left {len(pending)+len(running)}; nodes {tot["nodes"]:.4g}, closed {tot["closed"]:.4g}, OPEN {tot["open"]:.0f}, LPs {tot["lps"]:.4g}, CPU {tot["seconds"]/3600:.1f} h, certificates {tot["certs"]:.4g}, REJECTED {ck["rejected"]}, wrong names {ck["wrong"]}, python {ck["py"]} sampled {ck["pybad"]} differ, free {free/GIB:.1f} GB, overdue {overdue}{" PAUSED: the disk is nearly full" if paused else ""}', flush=True)
                if paused and not running and pending: time.sleep(30)
            time.sleep(0.2)
        fa.close()
    print(f'finished: {tot["nodes"]:.6g} nodes, closed {tot["closed"]:.6g}, OPEN {tot["open"]:.0f}, LPs {tot["lps"]:.6g}, CPU {tot["seconds"]/3600:.2f} h; certificates {tot["certs"]:.6g}, REJECTED {ck["rejected"]}, wrong names {ck["wrong"]}, python {ck["py"]} sampled {ck["pybad"]} differ; wall {(time.time()-T0)/3600:.2f} h', flush=True)
