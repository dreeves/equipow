#!/usr/bin/env python3
"""Stop processes whose arguments hold a script of the given name, by ps, on Linux or a Mac: python3 stopall.py ftree.py"""
import os, signal, subprocess, sys
from processes import processes, runs
stopped = 0
procs = processes()
for pid in sorted({p[0] for word in sys.argv[1:] for p in runs(procs, word)}):
    if pid != os.getpid():
        os.kill(pid, signal.SIGTERM); stopped += 1
print(f'stopped {stopped}')
