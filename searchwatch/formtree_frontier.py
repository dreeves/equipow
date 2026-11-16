"""Exact accounting for a model anchored at a frozen unfinished frontier.

A checkpoint records the immutable old verdict prefix and its accounted work.
Its groups partition every unfinished subtree at that boundary. Only subsequent
verdicts belong to those groups; their work plus the checkpoint's offset is the
original search's work. Groups are modeling units, not new proof node names.
"""
import hashlib
import json
from pathlib import Path
import sys

import formtree_work


def observed(model, data):
    """Return posterior roots, actual pending nodes, total finished tasks and old-work offset."""
    assert data.endswith(b'\n') or not data
    told = [json.loads(s) for s in data.splitlines()]
    names = [r['name'] for r in model['roots']]
    if 'checkpoint' not in model:
        roots, waiting = formtree_work.walk(told, names)
        return dict(roots=roots, waiting=waiting, finished=len(told), offset=0)
    c = model['checkpoint']
    assert set(c) == {'target', 'finished', 'done', 'prefix_bytes', 'prefix_sha256', 'roots', 'groups'}
    assert type(c['finished']) is int and 0 <= c['finished'] <= len(told)
    assert type(c['prefix_bytes']) is int and 0 <= c['prefix_bytes'] <= len(data)
    assert type(c['done']) is int and c['done'] >= 0
    prefix = data[:c['prefix_bytes']]
    assert (not prefix or prefix.endswith(b'\n')) and prefix.count(b'\n') == c['finished']
    assert hashlib.sha256(prefix).hexdigest() == c['prefix_sha256']
    base, frontier = formtree_work.walk(told[:c['finished']], c['roots'])
    assert sum(r['done'] for r in base) == c['done']
    groups = c['groups']
    assert groups and [g['name'] for g in groups] == names and len(set(names)) == len(names)
    assert all(set(g) == {'name', 'members'} and g['members'] for g in groups)
    members = [n for g in groups for n in g['members']]
    assert len(set(members)) == len(members) and set(members) == set(frontier)
    rows, waiting = formtree_work.walk(told[c['finished']:], members)
    by_name = {r['name']: r for r in rows}
    roots = [dict(name=g['name'], done=sum(by_name[n]['done'] for n in g['members']),
                  complete=all(by_name[n]['complete'] for n in g['members'])) for g in groups]
    return dict(roots=roots, waiting=waiting, finished=len(told), offset=c['done'])


def assemble(snapshot_path, sampled):
    """Build a model from complete, source-verified independent group-round probes.

The snapshot adds base (finished, done, prefix_bytes, prefix_sha256, roots),
original_model (a source path), and the source verdicts.prefix to the sampler's
contract. Each frontier member is its own unit, its blocks its 8 round estimates
(Opus 5.5, 2026-11-16; dreeves: "ok, go ahead and fix"): until then a unit was a
sampling group of about 40 members, which counted as finished only when all its
members were, so the members that finished never reached the model. The groups
remain the probes' process partition, checked against the blocks. Nothing is
fitted to final outcomes.
"""
    import frontier_sample as sampler
    from formtree_eta import read_model
    snapshot, paths, snapshot_sha = sampler.read_snapshot(snapshot_path)
    sampled = Path(sampled)
    result = json.loads((sampled/'model-blocks.json').read_text())
    assert result['protocol'] == 'fresh-group-round-v1'
    assert result['snapshot_sha256'] == snapshot_sha and result['rounds'] == sampler.ROUNDS
    assert result['sampler_sha256'] == sampler.sha((sampled/'sampler.py').read_bytes())
    data = (sampled/'draws.jsonl').read_bytes()
    assert data.endswith(b'\n') and sampler.sha(data) == result['draws_sha256']
    rows = [sampler.checked(json.loads(s), snapshot['engine']['wall_limit']) for s in data.splitlines()]
    assert all(r['seed'] == sampler.seed(snapshot['target'], r['name'], r['round']) for r in rows)
    groups = sampler.groups(list(snapshot['nodes']))
    assert result['groups'] == sampler.blocks(groups, rows)
    estimate = {(r['name'], r['round']): r['estimate'] for r in rows}
    members = list(snapshot['nodes'])
    original_path = paths[snapshot['original_model']]
    model = read_model(original_path, snapshot['sources'][snapshot['original_model']])
    assert 'checkpoint' not in model
    base = snapshot['base']
    model['checkpoint'] = {k: base[k] for k in ('finished', 'done', 'prefix_bytes', 'prefix_sha256', 'roots')}
    model['checkpoint'].update(target=snapshot['target'], groups=[dict(name=n, members=[n]) for n in members])
    model['roots'] = [dict(name=n, blocks=[[estimate[n, i]] for i in range(sampler.ROUNDS)]) for n in members]
    model['provenance'] = dict(previous=model['provenance'], original_model=str(original_path.resolve()),
                               original_sha256=snapshot['sources'][snapshot['original_model']],
                               snapshot=str(Path(snapshot_path).resolve()), snapshot_sha256=snapshot_sha,
                               samples=str(sampled.resolve()), draws_sha256=result['draws_sha256'],
                               sampler_sha256=result['sampler_sha256'], protocol=result['protocol'],
                               groups=len(groups), units=len(members), rounds=result['rounds'])
    model['assumptions'] = dict(previous=model['assumptions'],
                               frontier=dict(shared_global_discrepancy=True,
                                             local_discrepancy_per_member=True,
                                             fresh_process_per_group_round=True,
                                             solver_cache_within_block=True,
                                             calibrated_coverage=False))
    state = observed(model, paths['verdicts.prefix'].read_bytes())
    assert state['offset'] == base['done'] and all(r['done'] == 0 for r in state['roots'])
    return model


if __name__ == '__main__':
    # TODO: usage: frozen snapshot, completed sampling directory, and a new model file.
    assert len(sys.argv) == 4, 'Usus: formtree_frontier.py SNAPSHOT.json EXEMPLA EXEMPLAR.json'
    result = assemble(sys.argv[1], sys.argv[2])
    with Path(sys.argv[3]).open('x') as f:
        f.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
