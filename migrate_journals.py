#!/usr/bin/env python3
"""migrate_journals: move the journals of the runs to this code's CODE.

overnight_v5.CODE fingerprints certbb.py and width.py (the width test; see certbb.py's vocabulary), so a change to
either makes every journal's header refuse the run ("belongs to another configuration") until its code field is set
to the new CODE, which this script does.  The records stay valid: an INFEASIBLE or CLOSED record rests on a proof whose
tokens check unchanged under the new Check, and the search is the old one on the nodes of the records, which
quals_width.py pins for this revision (q_old_proofs_check_unchanged, q_journaled_240_leaves_close_by_a_cut,
q_silence_on_nodes_without_a_thin_direction, q_regression_against_old_certbb: the journaled proof sha1s).  An UNKNOWN
record only says that the search found nothing within its budget, and overnight_v5.Journal.reuse makes a resumed run
skip the node; so for a run that goes on, every node whose last record is UNKNOWN is solved again here within PROBE LP
solves (the root solve and a cut's two sides: the width test), and the records of those it closes are dropped (each
named on a line of its own), so that the resumed run closes them in three LP solves each, while the others keep their
records (solving them again would only repeat the old search, 2000000 LP solves per leaf at 240@11).  A pool cannot
be rebuilt from its journal key: asserted absent among the keys probed, as it has been.  When the code change moved
no node across the test (as a change that leaves the directions and the test's arithmetic alone does), the probe
drops nothing and says so: it is then the check of that claim on the run's open nodes.

PLAN says, per journal name: the program and the arguments of its run (the migration refuses to touch a journal while
such a process is alive), the module whose header() the journal must match, and whether the run goes on.  A copy of
the journal as it was goes to scratch/width/<name>.code_<the first 8 hex digits of its old code>.jsonl first (git
ignores scratch/; refused if the copy exists).  progress.py --watch holds CODE in memory: the migration refuses to run
while it is alive, and it is restarted after (its cache, .progress_cache.json, is keyed by CODE too).

Usage: nice -n 19 python3 -B migrate_journals.py JOURNAL [JOURNAL ...]     (paths; each basename in PLAN)
       quals: nice -n 19 python3 -B quals_width.py q_migration_script q_migration_alive_sees_this_process
"""
import os, sys, re, json, shutil, subprocess
import overnight_v5 as v5
import boxsplit as bx

HERE = os.path.dirname(os.path.abspath(__file__))
KEPT = os.path.join(HERE, 'scratch', 'width')          # where the copies go, as <name>.code_<old code>.jsonl
PROBE = 3                                              # the LP solves of the probe: the root solve and a cut's two sides
WATCHER = r'progress\.py --watch$'                     # the page watcher's command line
# PLAN[journal name] = (program, N, ORDER, the module whose header() the journal must match, whether the run goes on)
PLAN = {'overnight_v5_240_11_journal.jsonl': ('overnight_v5.py', 240, 11, v5, True),
        'overnight_v5_304_9_journal.jsonl': ('overnight_v5.py', 304, 9, v5, False),
        'overnight_v5_304_9_boxsplit_journal.jsonl': ('boxsplit.py', 304, 9, bx, False)}


def run_pattern(program, n, order):
    """The regular expression of the command line of program's run for the length n and the order."""
    return rf'\b{re.escape(program)} {n} {order}\b'


def alive(pattern):
    """The (pid, command) of every process whose command line the regular expression pattern matches."""
    out = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True, check=True).stdout
    return [(pid, command) for pid, _, command in (line.strip().partition(' ') for line in out.splitlines())
            if re.search(pattern, command)]


def parse_key(key):
    """The node of a journal key with single-vector constraints only (overnight_v5.node_key's M:[vector] parts); a
    pool's part, M:#count:sha1, cannot be rebuilt: asserted absent."""
    node = []
    for part in key.split():
        M, vec = part.split(':', 1)
        # TODO: error copy; says a journal key names a pool, whose members the key does not give
        assert vec.startswith('[') and vec.endswith(']'), f'Claude: "a pool cannot be rebuilt from its key: {key}"'
        node.append((int(M), (tuple(int(t) for t in vec[1:-1].split(',')),)))
    return tuple(node)


def probe_closes(mod, order, key):
    """Does the run's node solver close the node of key within PROBE LP solves?  A FEASIBLE verdict would be a
    witness, which the run must find for itself: asserted away."""
    verdict = mod.solve_node(order, parse_key(key), PROBE)[0]
    # TODO: error copy; says the probe found a sequence (a witness) at this node, which the run itself must find
    assert verdict != 'FEASIBLE', f'Claude: "the probe found a witness at {key}"'
    return verdict == 'INFEASIBLE'


def migrate(path):
    """Migrate the journal at path as PLAN says; returns the path of the copy kept."""
    name = os.path.basename(path)
    # TODO: error copy; says this journal name is not one PLAN knows
    assert name in PLAN, f'Claude: "no plan for {name}"'
    program, n, order, mod, goes_on = PLAN[name]
    running = alive(run_pattern(program, n, order)) + alive(WATCHER)
    # TODO: error copy; says the run of this journal or the page watcher is still alive, naming the processes
    assert not running, f'Claude: "{program} {n} {order} or the page watcher is running: {running}"'
    mod.configure(n, order)
    text = open(path).read()
    # TODO: error copy; says the journal's last line is not complete
    assert text.endswith('\n'), f'Claude: "{path} ends in a partial line"'
    lines = text.split('\n')[:-1]
    head, want = json.loads(lines[0]), mod.header()
    # TODO: error copy; says the header is not an old header of this run (the current one but for the code field), or is already the current one
    assert head | {'code': want['code']} == want and head['code'] != want['code'], f'Claude: "{path} is not an old journal of {program} {n} {order}"'
    kept = os.path.join(KEPT, name.replace('.jsonl', f'.code_{head["code"][:8]}.jsonl'))
    # TODO: error copy; says a copy of this journal already sits where the migration keeps its copy
    assert not os.path.exists(kept), f'Claude: "{kept} exists"'
    records = [json.loads(l) for l in lines[1:]]
    last = {}
    for r in records: last[r['key']] = r['verdict']
    dropped = {k for k, verdict in sorted(last.items()) if goes_on and verdict == 'UNKNOWN' and probe_closes(mod, order, k)}
    kept_lines = [l for l, r in zip(lines[1:], records, strict=True) if r['key'] not in dropped]
    os.makedirs(KEPT, exist_ok=True)
    shutil.copy2(path, kept)
    tmp = path + '.migrating'
    with open(tmp, 'w') as fh:
        fh.write(json.dumps(want) + '\n' + ''.join(l + '\n' for l in kept_lines))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    journal = mod.Journal(path)                                   # the migrated journal opens under the new header
    assert set(journal.records) == set(last) - dropped
    for k in sorted(dropped):
        # TODO: says that this node's records were dropped, the probe closing it, naming the node by its journal key
        print(f'Claude: "dropped, the probe closes it: {k}"')
    # TODO: says what was done: the journal, its copy, the old and the new code, how many records were kept of how many, how many nodes with an UNKNOWN record the probe closed (their records dropped, each named above), and that the kept records' proofs check unchanged
    print(f'Claude: "{path}: copy at {kept}; code {head["code"]} -> {want["code"]}; {len(kept_lines)} of {len(records)} records kept; '
          f'{len(dropped)} nodes with an UNKNOWN record that the probe closes, their records dropped; the kept records stand: '
          f'old proofs check unchanged"')
    return kept


def main():
    # TODO: error copy; says how to run the script: with one or more journal paths
    assert len(sys.argv) >= 2, 'Claude: "usage: python3 migrate_journals.py JOURNAL [JOURNAL ...]"'
    for path in sys.argv[1:]: migrate(path)


if __name__ == '__main__':
    main()
