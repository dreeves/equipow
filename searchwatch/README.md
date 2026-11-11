This file is all Claude (Fable 5.2).

# What runs and watches the searches

The launcher, the watcher and the scheduler of the long searches, and the models behind the section "Search progress" of [the page](https://equipow.dreev.es). The search programs themselves are in [../engine/](../engine/) and [../searches/](../searches/). Every command below runs from the repository's root.

## Launching a search

- [track.py](track.py): the launcher that every search runs under, so that the page shows it with no code of its own. It writes the run's record to `runs/NAME.jsonl`, which git ignores, and does not change the search.

      python3 -B searchwatch/track.py run NAME N:M [--found FILE] -- COMMAND
      python3 -B searchwatch/track.py adopt NAME N:M PID

  N:M is the question the search asks: has some sequence of length N order M?

## Watching

- [progress.py](progress.py): reads every run's journal, log and record, and writes [../pagedata/progress.js](../pagedata/progress.js), the data of the section "Search progress": each run's state, its time so far and to go, and its charts.
- [sweep288_progress.py](sweep288_progress.py) and [search592_progress.py](search592_progress.py): progress.py with two more searches surveyed. The second includes the first, and is the watcher to run:

      python3 -B searchwatch/search592_progress.py --watch

  It surveys every minute, and rewrites the data file when a run's data change. Run one watcher at a time.
- [cpu.py](cpu.py): samples the machine's CPU use, for the section's CPU charts, into `runs/cpu/`: `python3 -B searchwatch/cpu.py --watch`.
- [chance.py](chance.py): the chance that a sequence exists, given that a search has found none so far.
- [formtree_eta.py](formtree_eta.py) and [formtree_work.py](formtree_work.py): the model of how much work a form-tree search has left, and the reader of the work it has done.
- [run_modules.py](run_modules.py): loads a run's own solver modules beside the repository's, so that a run made by older code can still be read.
- [stages.json](stages.json): the stages that follow each search before its result can be recorded, and what each costs.

## Scheduling

- [shepherd.py](shepherd.py): keeps the registered searches running: it launches one that can be launched, and stops searches when the disk runs low. It never deletes anything and never launches a search that was stopped. All four of its searches are stopped now, so it launches nothing.
- [shepherd.log](shepherd.log) and [shepherd.err](shepherd.err): its log of each change of a search's status, and what it wrote to standard error.

Each module's docstring defines its terms. Restart the watcher after editing progress.py.
