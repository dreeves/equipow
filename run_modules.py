"""Load one run's solver and replay modules without changing canonical imports permanently.

Each source is registered under a private name so inspect can find its exact file. Canonical certbb and
overnight_v5 names are shadowed only while that run's modules execute, then restored even on exceptions. The
snapshot writer is single-threaded; callers must not overlap import execution or progress contexts with other
Python threads. A changed source after loading is an error requiring a fresh process, not an implicit reload.

Different solver CODE values are accepted only when every listed geometry/replay function is source-identical
to the repository's. Header validation uses the actual run module, including its frozen legacy provenance.
"""
from contextlib import contextmanager
from functools import lru_cache
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys
from types import SimpleNamespace


GEOMETRY = ('lattice_poly', 'lattice_basis', 'moment_rows', 'moments', 'count_rows', 'ExactSystem',
            'integer_system', 'admissible', 'act', 'stabilizer', 'rep', 'split', 'solve_node',
            'node_key', 'work', 'sibling_order', 'search')
BOX_GEOMETRY = ('parse_key', 'open_leaves', 'admissible_box', 'outside_key')
CHECKER = ('ProofError', 'require', 'Moments', 'node_rows', 'lower_bound', 'fixed', 'cuts', 'Check', 'verify')
# What decides a run's splits (overnight_v5.split's children of a node, as node_key writes them): the sources of
# SPLIT_SOURCES and the values of SPLIT_VALUES, as the run's overnight_v5 has them once configured; every module name
# split reads, at any depth of its calls (quals_run_modules checks that none is missing).  They differ from GEOMETRY:
# Relaxation, moment_basis, is_pool, size and gbinom decide splits and are not in it; search, work, sibling_order,
# solve_node and moments are in it and decide none (2026-10-30).
SPLIT_SOURCES = ('split', 'is_pool', 'stabilizer', 'act', 'rep', 'size', 'moment_rows', 'gbinom', 'integer_system',
                 'ExactSystem', 'count_rows', 'admissible', 'lattice_basis', 'lattice_poly', 'Relaxation',
                 'moment_basis', 'node_key')
SPLIT_VALUES = ('N', 'CASCADE', 'TOL', 'GROUP')
ABSENT = object()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


@contextmanager
def imports(directory, aliases):
    """Temporarily bind import names and source lookup paths, preserving their original identities."""
    previous = {name: sys.modules.get(name, ABSENT) for name in aliases}
    path = list(sys.path)
    sys.path.insert(0, str(directory))
    sys.modules.update(aliases)
    try:
        yield
    finally:
        for name, module in previous.items():
            if module is ABSENT:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        sys.path[:] = path


def module(directory, stem, aliases):
    """Load a source once under a private inspect-compatible name; refuse changed sources on reuse."""
    path = directory / (stem + '.py')
    name = '_powersums_run_' + hashlib.sha256(str(directory).encode()).hexdigest()[:20] + '_' + stem
    digest = sha(path)
    if name in sys.modules:
        loaded = sys.modules[name]
        # TODO: error copy says a loaded run source changed and cannot be silently reused.
        assert loaded.__file__ == str(path) and loaded._source_sha256 == digest, f'Fons iam lectus mutatus: {path}'
        return loaded
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[name] = loaded
    try:
        with imports(directory, aliases):
            spec.loader.exec_module(loaded)
        # TODO: error copy says a run source changed while it was imported.
        assert sha(path) == digest, f'Fons inter legendum mutatus: {path}'
        loaded._source_sha256 = digest
        return loaded
    except BaseException:
        sys.modules.pop(name, None)
        raise


def geometry(v5):
    """The geometry of the run v5 is configured for: the sha1 of the sources of SPLIT_SOURCES and the values of
    SPLIT_VALUES in v5, which decide its splits and do not change with its solver (progress keys a run's cached splits
    and its record of ETAs by it; 2026-10-30: before, by overnight_v5.CODE, which certbb's source changes, so that each
    solver change started 288@10's 99 MB of splits cold).  inspect reads each source from its file as it is now."""
    return hashlib.sha1((''.join(inspect.getsource(getattr(v5, name)) for name in SPLIT_SOURCES)
                         + repr([getattr(v5, name) for name in SPLIT_VALUES])).encode()).hexdigest()


def equivalent(local, root, names):
    """Replay and geometry must stay identical even when the solver's implementation changes."""
    for name in names:
        # TODO: error copy identifies a geometry or replay function that differs from the repository's.
        assert inspect.getsource(getattr(local, name)) == inspect.getsource(getattr(root, name)), \
            f'Geometria vel repetitio discrepat: {name}'


def load(directory, root_v5, root_bx):
    """Return the local certbb, overnight_v5 and boxsplit modules, retaining no canonical import override."""
    directory = Path(directory).resolve()
    if directory == Path(root_v5.__file__).resolve().parent:
        return SimpleNamespace(certbb=root_v5.certbb, v5=root_v5, bx=root_bx)
    # Older run copies depend on the root solver explicitly; a present local source must load successfully.
    certbb = root_v5.certbb
    if (directory / 'certbb.py').exists():
        certbb = module(directory, 'certbb', {})
    equivalent(certbb, root_v5.certbb, CHECKER)
    # TODO: error copy says the exact proof token arities differ from the repository's.
    assert certbb.ARITY == root_v5.certbb.ARITY, 'Aria notarum probationis discrepant.'
    v5 = module(directory, 'overnight_v5', {'certbb': certbb})
    equivalent(v5, root_v5, GEOMETRY)
    bx = module(directory, 'boxsplit', {'certbb': certbb, 'overnight_v5': v5})
    # TODO: error copy says the run's modules did not bind to the intended local solver and geometry.
    assert v5.certbb is certbb and bx.certbb is certbb and bx.v5 is v5, 'Moduli cursus inter se non congruunt.'
    equivalent(bx, root_bx, BOX_GEOMETRY)
    return SimpleNamespace(certbb=certbb, v5=v5, bx=bx)


@contextmanager
def context(progress, loaded):
    """Bind the snapshot's generic functions to one run and restore both repository bindings afterward."""
    old = progress.v5, progress.bx
    progress.v5, progress.bx = loaded.v5, loaded.bx
    try:
        yield loaded
    finally:
        progress.v5, progress.bx = old


def signature(path):
    stat = Path(path).stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


@lru_cache(maxsize=None)
def archive(path, digest, size, records, code, identity):
    """Verify an immutable archive once per file identity and expected provenance, with bounded memory."""
    full, count = hashlib.sha256(), 0
    with Path(path).open('rb') as fh:
        first = fh.readline()
        # TODO: error copy says the legacy archive's header is incomplete or names another code revision.
        assert first.endswith(b'\n') and json.loads(first)['code'] == code, 'Caput exemplaris veteris discrepat.'
        full.update(first)
        for line in fh:
            # TODO: error copy says the legacy archive contains an incomplete record.
            assert line.endswith(b'\n'), 'Nota exemplaris veteris imperfecta est.'
            full.update(line)
            count += 1
        # TODO: error copy says the archive's bytes, record count, hash or identity do not match its provenance.
        assert (fh.tell() == size and count == records and full.hexdigest() == digest
                and signature(path) == identity), 'Origo exemplaris veteris non congruit.'


def validate_header(v5, header):
    """Require the actual configured run's header and independently validate any named legacy archive."""
    # TODO: error copy says the journal header does not belong to the actual loaded run.
    assert header == v5.header(), 'Caput actorum ad hunc cursum non pertinet.'
    legacy = header.get('legacy')
    if legacy is not None:
        archive(legacy['archive'], legacy['sha256'], legacy['bytes'], legacy['records'], legacy['code'],
                signature(legacy['archive']))
