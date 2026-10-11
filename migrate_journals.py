#!/usr/bin/env python3
"""migrate_journals: move the journals of the finished and the stopped runs to the CODE of the width test.

certbb.py's cut token and width.py (the width test; see certbb.py's vocabulary) change overnight_v5.CODE, so every
journal's header refuses the new code ("belongs to another configuration") until its code field is set to it.  The
records stay valid: an INFEASIBLE or CLOSED record rests on a proof whose tokens (B and L) check unchanged under the
new Check (quals_width.q_old_proofs_check_unchanged, q_silence_on_nodes_without_a_thin_direction), and
quals_width.q_regression_against_old_certbb pins the search on nodes without a thin direction to the old one.  An
UNKNOWN record only says that the old search found nothing within its budget; the width test may close such a node
in three LP solves, and overnight_v5.Journal.reuse would skip it, so for a run that goes on (240@11) every UNKNOWN
record is dropped: the run then solves those nodes again, with the test, and settles their closed children from
their records.  For the finished runs (304@9 and its box split) the header alone changes.

PLAN says, per journal name: the program and the arguments of its run (the migration refuses to touch a journal
while such a process is alive), whether UNKNOWN records are dropped, and which module's header() the migrated
journal must match.  A copy of the journal as it was goes to scratch/width/<name>.before_width.jsonl first (git
ignores scratch/; refused if the copy exists).  progress.py --watch holds the old code in memory: restart it after
the migration.

Usage: nice -n 19 python3 -B migrate_journals.py JOURNAL [JOURNAL ...]     (paths; each basename in PLAN)
       quals: nice -n 19 python3 -B quals_width.py q_migration_script q_migration_alive_sees_this_process
"""
import os, sys, re, json, shutil, subprocess
import overnight_v5 as v5
import boxsplit as bx

HERE = os.path.dirname(os.path.abspath(__file__))
KEPT = os.path.join(HERE, 'scratch', 'width')          # where the copies go, as <name>.before_width.jsonl
# PLAN[journal name] = (program, N, ORDER, drop UNKNOWN records, the module whose header() the journal must match)
PLAN = {'overnight_v5_240_11_journal.jsonl': ('overnight_v5.py', 240, 11, True, v5),
        'overnight_v5_304_9_journal.jsonl': ('overnight_v5.py', 304, 9, False, v5),
        'overnight_v5_304_9_boxsplit_journal.jsonl': ('boxsplit.py', 304, 9, False, bx)}


def alive(program, n, order):
    """The (pid, command) of every process whose command line runs program with the arguments n and order."""
    out = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True, check=True).stdout
    pattern = re.compile(rf'\b{re.escape(program)} {n} {order}\b')
    found = []
    for line in out.splitlines():
        pid, _, command = line.strip().partition(' ')
        if pattern.search(command): found.append((pid, command))
    return found


def migrate(path):
    """Migrate the journal at path as PLAN says; returns the path of the copy kept."""
    name = os.path.basename(path)
    # TODO: error copy; says this journal name is not one PLAN knows
    assert name in PLAN, f'Claude: "no plan for {name}"'
    program, n, order, drop, mod = PLAN[name]
    running = alive(program, n, order)
    # TODO: error copy; says the run of this journal is still alive, naming its processes
    assert not running, f'Claude: "{program} {n} {order} is running: {running}"'
    mod.configure(n, order)
    text = open(path).read()
    # TODO: error copy; says the journal's last line is not complete
    assert text.endswith('\n'), f'Claude: "{path} ends in a partial line"'
    lines = text.split('\n')[:-1]
    head = json.loads(lines[0])
    want = mod.header()
    # TODO: error copy; says the header is not the old header of this run (the same but for the code field), or already the new one
    assert head | {'code': want['code']} == want and head['code'] != want['code'], f'Claude: "{path} is not an old journal of {program} {n} {order}"'
    kept = os.path.join(KEPT, name.replace('.jsonl', '.before_width.jsonl'))
    # TODO: error copy; says a copy of this journal already sits where the migration keeps its copy
    assert not os.path.exists(kept), f'Claude: "{kept} exists"'
    os.makedirs(KEPT, exist_ok=True)
    shutil.copy2(path, kept)
    records = [l for l in lines[1:] if not (drop and json.loads(l)['verdict'] == 'UNKNOWN')]
    tmp = path + '.migrating'
    with open(tmp, 'w') as fh:
        fh.write(json.dumps(want) + '\n' + ''.join(l + '\n' for l in records))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    journal = mod.Journal(path)                                   # the migrated journal opens under the new header
    assert len(journal.records) <= len(records)
    # TODO: says what was done: the journal, its copy, the new code, how many records were kept and dropped, and that the kept records' proofs check unchanged
    print(f'Claude: "{path}: copy at {kept}; code {head["code"]} -> {want["code"]}; {len(records)} records kept '
          f'({len(lines) - 1 - len(records)} UNKNOWN dropped); the kept records stand: old proofs check unchanged"')
    return kept


def main():
    # TODO: error copy; says how to run the script: with one or more journal paths
    assert len(sys.argv) >= 2, 'Claude: "usage: python3 migrate_journals.py JOURNAL [JOURNAL ...]"'
    for path in sys.argv[1:]: migrate(path)


if __name__ == '__main__':
    main()
