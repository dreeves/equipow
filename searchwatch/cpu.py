"""The machine's CPU use, sampled by the progress watcher for the page's CPU charts (dreeves, 2026-11-07: "could we get a
nice CPU usage graph on the search page? similar to what activity monitor shows. three colors: one for the search, one
for all other processes on the machine, and one for idle, if any", then "maybe aligned with the ETA graph").

Vocabulary:
  ticks     the kernel's cumulative CPU ticks summed over the cores, busy (user, system and nice) and idle, from
            host_processor_info, which Activity Monitor reads too: HZ of them a second on each core
  cputime   a process's cumulative CPU seconds, user and system, as ps prints them ([[dd-]hh:]mm:ss.ss, its minutes
            not carried into hours below an hour's worth of fields: "569:30.85")
  sample    {time, busy, idle, groups}: the ticks at time, and for each tracked run's name the cputime of each process
            in its process group (its pid's), {name: {pid: seconds}}, the names of runs whose pid is no live process left out
  interval  [t0, t1, idle, {name: share}] of two samples: over [t0, t1], the idle fraction of the cores' capacity, and
            each run's share, its group's CPU seconds over the capacity's (a process new in the later sample counted
            from 0: it started between them); other processes' share is the rest, 1 - idle - the shares.  A process that
            ended between the samples loses its last seconds to other processes'.
  sampler   this file run as `python3 -B searchwatch/cpu.py --watch` from the repository's root: a sample every EVERY seconds, each
            interval from the last appended to FILE, which the progress watcher reads (progress.cpu_file) and does not
            write; one at a time (a lock beside FILE).  Kept apart from the watcher, whose snapshots take from seconds to
            minutes, so that the samples keep a steady minute."""
import ctypes, ctypes.util, fcntl, glob, json, os, re, subprocess, sys, time, traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above searchwatch/ (this file was at the root until 2026-11-10, dreeves's README [REF])
FILE = os.path.join(ROOT, 'runs', 'cpu', 'intervals.jsonl')   # the intervals, a line each (apart from runs/*.jsonl, the records)
EVERY = 60          # seconds between samples

HZ = os.sysconf('SC_CLK_TCK')
SKEW = 0.02         # the most a run's share may pass the busy fraction: the ticks and ps are read a moment apart

_lib = ctypes.CDLL(ctypes.util.find_library('System'))
_lib.mach_host_self.restype = ctypes.c_uint
_lib.host_processor_info.restype = ctypes.c_int
_lib.host_processor_info.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.POINTER(ctypes.c_uint),
                                     ctypes.POINTER(ctypes.POINTER(ctypes.c_uint)), ctypes.POINTER(ctypes.c_uint)]
_lib.vm_deallocate.restype = ctypes.c_int
_lib.vm_deallocate.argtypes = [ctypes.c_uint, ctypes.c_size_t, ctypes.c_size_t]
_TASK = ctypes.c_uint.in_dll(_lib, 'mach_task_self_')
LOAD_INFO, STATES, IDLE = 2, 4, 2   # PROCESSOR_CPU_LOAD_INFO; per core user, system, idle, nice ticks


def ticks():
    """The machine's (busy, idle) ticks, summed over its cores."""
    cores, info, count = ctypes.c_uint(), ctypes.POINTER(ctypes.c_uint)(), ctypes.c_uint()
    assert _lib.host_processor_info(_lib.mach_host_self(), LOAD_INFO, ctypes.byref(cores), ctypes.byref(info), ctypes.byref(count)) == 0
    values = info[:count.value]
    assert count.value == STATES * cores.value > 0, (count.value, cores.value)
    assert _lib.vm_deallocate(_TASK.value, ctypes.cast(info, ctypes.c_void_p).value, count.value * ctypes.sizeof(ctypes.c_uint)) == 0
    idle = sum(values[IDLE::STATES])
    return sum(values) - idle, idle


def cputime(text):
    """ps's time column as seconds."""
    m = re.fullmatch(r'(?:(\d+)-)?(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)', text)
    assert m, text
    days, hours, minutes, seconds = (float(g) if g else 0.0 for g in m.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def sample(groups):
    """A sample (see the vocabulary) of the machine now, groups {name: pid} the tracked runs' processes; a name whose pid
    is no live process left out (its run not running: a gap in its chart, not 0%)."""
    busy, idle = ticks()
    now = time.time()
    out = subprocess.run(['ps', '-A', '-o', 'pid=,pgid=,stat=,time='], capture_output=True, text=True, check=True).stdout
    rows = [(int(a), int(b), cputime(d)) for a, b, c, d in (line.split() for line in out.splitlines()) if not c.startswith('Z')]
    pgid = {pid: g for pid, g, _ in rows}       # the live processes', zombies left out
    return dict(time=now, busy=busy, idle=idle,
                groups={name: {p: s for p, g, s in rows if g == pgid[pid]} for name, pid in groups.items() if pid in pgid})


def interval(a, b):
    """The interval (see the vocabulary) from sample a to the later sample b."""
    busy, idle = b['busy'] - a['busy'], b['idle'] - a['idle']
    assert busy >= 0 and idle >= 0 and busy + idle > 0 and b['time'] > a['time'], (busy, idle, a['time'], b['time'])
    capacity = (busy + idle) / HZ
    used = {name: [s - a['groups'].get(name, {}).get(pid, 0.0) for pid, s in procs.items()] for name, procs in b['groups'].items()}
    assert all(d >= -0.01 for ds in used.values() for d in ds), used          # ps's hundredths, rounded
    share = {name: sum(ds) / capacity for name, ds in used.items()}
    assert sum(share.values()) <= busy / (busy + idle) + SKEW, (share, busy, idle)
    return [a['time'], b['time'], idle / (busy + idle), share]


def append(row, path):
    """Appends an interval to the file of intervals, a whole line at a time."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(row, separators=(',', ':')) + '\n')


def read(path):
    """The intervals recorded at path, in order (none if the file does not exist yet)."""
    rows = [json.loads(line) for line in open(path, encoding='utf-8')] if os.path.exists(path) else []
    assert all(len(r) == 4 and r[0] < r[1] for r in rows) and all(p[1] <= q[0] for p, q in zip(rows, rows[1:])), path
    return rows


def groups(root):
    """The tracked runs (root's runs/*.jsonl, track.py's records, whole lines only) with no end line, {name: pid}."""
    records = [[json.loads(line) for line in open(path, encoding='utf-8') if line.endswith('\n')]
               for path in sorted(glob.glob(os.path.join(root, 'runs', '*.jsonl')))]
    return {r[0]['name']: r[0]['pid'] for r in records if r and r[-1]['event'] != 'end'}


def watch(root=ROOT, path=FILE, every=EVERY):
    """The sampler (see the vocabulary): root's tracked runs (groups) sampled every `every` seconds, each interval from the
    last appended to path; one sampler at a time (an exclusive lock on path's directory's lock file, refused at once if
    held).  A failed sample is reported and dropped, the next starting afresh: a gap in the CPU charts."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock = open(os.path.join(os.path.dirname(path), 'lock'), 'w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    last = None
    while True:
        try:
            s = sample(groups(root))
            if last is not None: append(interval(last, s), path)
            last = s
        except Exception:
            # TODO: log line; says this CPU sample failed, so its interval is left out of the CPU charts
            print(f'{time.strftime("%Y-%m-%d %H:%M:%S")} Claude: "the CPU sample failed; its interval is left out"', file=sys.stderr, flush=True)
            traceback.print_exc()
            last = None
        time.sleep(every)


if __name__ == '__main__':
    # TODO: error copy; says how to run the sampler: python3 -B searchwatch/cpu.py --watch
    assert sys.argv[1:] == ['--watch'], 'Claude: "usage: python3 -B searchwatch/cpu.py --watch"'
    watch()
