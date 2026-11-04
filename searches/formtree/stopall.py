#!/usr/bin/env python3
"""Stop processes whose arguments hold a script of the given name, by ps, on Linux or a Mac: python3 stopall.py ftree.py"""
import os, signal, subprocess, sys
stopped = 0
for line in subprocess.run(['ps', '-A', '-o', 'pid=,args='], capture_output=True, text=True, check=True).stdout.splitlines():
    pid, *args = line.split()
    if int(pid) != os.getpid() and args and 'python' in os.path.basename(args[0]) and any(os.path.basename(a) == word for a in args[1:] for word in sys.argv[1:]):
        os.kill(int(pid), signal.SIGTERM); stopped += 1
print(f'stopped {stopped}')
