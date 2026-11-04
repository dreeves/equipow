#!/usr/bin/env python3
"""A spot check that needs no trust in the run's record: nodes from the run's audit sample are proved again here, by a fresh run of the prover for a short time, its stream read by the Python checker alone, each node's name recomputed from its rows.
Usage, in searches/formtree/: audit.py DIR COUNT SECONDS   env PE_LIB (scratch/formtree/build/libpex.so after run.sh).  What a node spills in that time stays unproved here: an audit tests the machinery, the whole proof takes the whole run."""
import hashlib, json, os, random, resource, subprocess, sys, tempfile
import pex as pe
HERE = os.path.dirname(os.path.abspath(__file__))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
if sys.platform == 'linux': resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))
d, count, seconds = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
nodes = []
with open(os.path.join(d, 'audit.txt')) as f:
    for line in f:
        if line.startswith('#'): nodes.append([line[1:].strip(), ''])
        elif nodes: nodes[-1][1] += line
rng = random.Random(hashlib.sha256(open(os.path.join(d, 'verdicts.jsonl'), 'rb').read()).hexdigest()); rng.shuffle(nodes)
want = [11,8,13,4,9,17,19,23,16,25,27,29,31,37]; mods = [3,4,5,7,8,9,11,13,16,17,19,23,25,27,29,31,37]
pe.init(288, 10, mods, want, **pe.RUN_INIT); pe.run_settings()
accepted = certs = done = 0
with tempfile.TemporaryDirectory() as t:
    for name, text in nodes[:count]:
        path, stream = os.path.join(t, 'node'), os.path.join(t, 'stream')
        with open(path, 'w') as f: f.write(text)
        pe.lib.pe_certfd(os.open(stream, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)); pe.run_file(path, seconds, None, os.path.join(t, 'spill')); pe.lib.pe_certfd(-1)
        p = subprocess.run([sys.executable, '-B', '-I', '-S', os.path.join(HERE, '..', '..', 'proofs', 'formtree.py'), 'check', stream], capture_output=True, text=True)
        v = json.loads(p.stdout.splitlines()[0]); done += 1; certs += v['certs']
        if v['ok'] and v['start'] == name: accepted += 1
        else: print(f"NOT ACCEPTED {name}: name {v['start']}, {v['why']}", flush=True)
        for f in os.listdir(t): os.remove(os.path.join(t, f))
print(f'{accepted} of {done} sampled nodes accepted by formtree.py, {certs} certificates, of {len(nodes)} nodes in the sample so far')
sys.exit(0 if accepted == done and done else 1)
