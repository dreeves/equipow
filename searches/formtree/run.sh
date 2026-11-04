#!/bin/bash
# The 288:10 proof run.  Starts, or resumes from where it stopped: run it again after any stop.  Needs g++ and python3 with numpy.
#   ./run.sh [processes]       default: all threads.  Set PYTHON to use another interpreter.
#   Progress: tail -1 ../../scratch/formtree/run288v.log.  Stop: python3 stopall.py ftree.py.  Save the state for someone else: see README.md.
set -e
cd "$(dirname "$0")"
ulimit -c 0
P=${1:-$(getconf _NPROCESSORS_ONLN)}; PY=${PYTHON:-python3}; WORK=../../scratch/formtree; D=$WORK/run288v; B=$WORK/build
mkdir -p "$B"
"$PY" -c 'import numpy' || { echo "$PY needs numpy"; exit 1; }
if g++ -march=native -x c++ -E /dev/null > /dev/null 2>&1; then ARCH=-march=native; else ARCH=-mcpu=native; fi
FLAGS="-O3 $ARCH -funroll-loops -fassociative-math -fno-signed-zeros -fno-trapping-math -std=c++17"
if [ ! "$B/libpex.so" -nt pex.cpp ]; then g++ $FLAGS -shared -fPIC -o "$B/libpex.tmp.so" pex.cpp; mv "$B/libpex.tmp.so" "$B/libpex.so"; fi   # by rename: a running process keeps the old file
if [ ! "$B/fkernel" -nt ../../proofs/fkernel.cpp ]; then g++ -O2 -std=c++17 -o "$B/fkernel.tmp" ../../proofs/fkernel.cpp; mv "$B/fkernel.tmp" "$B/fkernel"; fi
if [ ! -e "$D/verdicts.jsonl" ] && [ -f run288v_snapshot.tar.gz ]; then "$PY" -B handoff.py restore run288v_snapshot.tar.gz "$D"; fi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PE_LIB="$(realpath "$B/libpex.so")" FKERNEL="$(realpath "$B/fkernel")" PYTHONPATH=.
nohup "$PY" -B -u ftree.py 288:10 top_288_10.json.gz "$P" 240 11,8,13,4,9,17,19,23,16,25,27,29,31,37 3,4,5,7,8,9,11,13,16,17,19,23,25,27,29,31,37 "$D" >> "$WORK/run288v.log" 2>&1 &
echo "started on $P processes.  Progress: tail -1 $WORK/run288v.log"
