"""Process rows and exact Python script invocations, for the local form-tree tools."""
import re
import subprocess


def processes():
    """The machine's processes as (pid, ppid, stat, command), from ps (which prints whole commands to a pipe)."""
    out = subprocess.run(['ps', '-ax', '-o', 'pid=,ppid=,stat=,command='], capture_output=True, text=True, check=True)
    return [(int(a), int(b), c, d) for a, b, c, d in (line.split(None, 3) for line in out.stdout.splitlines())]


def runs(procs, script, *args):
    """Live Python interpreters executing script, with args as its first arguments.
    ps renders whitespace rather than argv boundaries; interpreter/script paths here contain no spaces.
    -c, -m, stdin, help and version invocations do not execute the named script.
    """
    flags = r'(?:-[bBdEiIOPqRsSuvx]+|-[bBdEiIOPqRsSuvx]*[WX](?:\S+|\s+\S+)|--check-hash-based-pycs\s+(?:default|always|never))'
    options = rf'(?:\s+{flags})*(?:\s+--)?'
    tail = ''.join(r'\s+' + re.escape(str(a)) for a in args)
    pattern = rf'^(?:\S*/)?[Pp]ython(?:\d+(?:\.\d+)*)?{options}\s+(?:\S*/)?{re.escape(script)}{tail}(?:\s|$)'
    return [p for p in procs if re.match(pattern, p[3]) and not p[2].startswith('Z')]
