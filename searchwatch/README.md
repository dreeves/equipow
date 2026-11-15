This file is all Claude (Fable 5.2).

# What runs and watches the searches

The launcher, the estimators and the watcher of the long searches, behind the section "Search progress" of [the page](https://equipow.dreev.es). The search programs themselves are in [../engine/](../engine/) and [../searches/](../searches/). Every command below runs from the repository's root.

## Launching a search

- [track.py](track.py): the launcher that every search runs under, so that the page shows it with no code of its own. It writes the run's record to `runs/NAME.jsonl`, which git ignores, and does not change the search.

      python3 -B searchwatch/track.py run NAME SEARCH N:M [--found FILE] ESTIMATOR ... -- COMMAND ...
      python3 -B searchwatch/track.py adopt NAME SEARCH N:M [--found FILE] ESTIMATOR ... -- PID
      python3 -B searchwatch/track.py pause NAME

  N:M is the question the search asks: has some sequence of length N order M? SEARCH is a label for what is being tried (`formtree`, `tilt`): the runs of one label at one N:M are one search, one box of the page, so a restart takes its search's label and another kind of search at the same N:M takes another. ESTIMATOR is a Python script with its arguments. The tracker runs it when the run starts, every 5 minutes after, and once more when the run's command has ended (2026-11-13), so that a record's last estimate is of the search as it ended; each time it appends one estimate to the record: the time to go, the work done and the total work, and the probability that what is searched for exists, given none found so far. The page draws a search from those lines alone. track.py's docstring defines the record, and its functions are how the estimators and the watcher read one.

  `pause` marks a run's stop a pause: the run is stopped on purpose and its search goes on in a later run, from the work it kept. It appends one line to the run's record and stops nothing, so mark the run first, then stop it (SIGTERM to its tracker, whose pid is in the record's first line). The page then calls the search paused where it would say aborted, and counts the run among its paused ones. A run that has ended cannot be marked.

## Estimators

- [lindy.py](lindy.py): for a search that knows nothing but its age. Its time to go is Lindy's rule on its seconds of running, its work is its time, and its probability stays at the prior 0.5.

      python3 -B searchwatch/track.py run NAME SEARCH N:M searchwatch/lindy.py -- COMMAND ...

- [formtree_eta.py](formtree_eta.py): for a form-tree search. It counts the nodes checked in the search's verdicts, measures their rate from its own earlier estimates, and draws the tree's size from a work model made from dives. Of a finished tree (every start node's tree checked, nothing found) its estimate is exact: the total is the nodes checked, nothing is to go, and the probability is 0. [formtree_work.py](formtree_work.py) counts the work, and [chance.py](chance.py) turns the draws into the time to go and the probability.

      python3 -B searchwatch/track.py run NAME SEARCH N:M searchwatch/formtree_eta.py VERDICTS MODEL PRIOR -- COMMAND ...

## Replaying completed forecasts (Codex, 2026-11-14)

[eta_replay.py](eta_replay.py) scores saved forecasts against completed form-tree verdict graphs. It does not rerun the prover, fit a model, or change live estimates.

    python3 -B searchwatch/eta_replay.py MANIFEST.json > REPORT.json

The module's docstring specifies the version-1 manifest and forecast fields. Prepare one manifest entry per completed search, including all its restart intervals. Normalize current tracker records by copying their `estimate` objects unchanged into a JSONL file, in timestamp order; take each interval from its recorded `start` and `end`. Read records through `track.checked`, require every interval's end, and use the configured model's original `roots`. Include SHA-256 hashes of the normalized forecasts, verdicts, models and source records. Paths resolve from the repository root. The evaluator verifies those hashes before scoring. An unfinished verdict graph cannot supply a completion result.

For older archives, convert only documented units and preserve the original timestamps and values. Unavailable total-work bands are `null`; they cannot be recovered by multiplying time quantiles by a rate. Historical band quantiles are explicit metadata, or `null` if unknown. `finished`, when available, must identify a verdict prefix whose accounted node count equals the forecast's `done`. Optional extra fields, including recorded model hashes and old elapsed-time coordinates, survive unchanged in the report. Candidate forecasts can use the same format, but must be generated from their historical prefixes without consulting the later verdicts that supply the outcome.

The report includes every observation and a separate summary for each search. Total-work and remaining-work errors have the same signed difference but different multiplicative denominators. Time errors use active wall seconds: overlapping runs count once and restart gaps do not count. The rate comparison is against future accounted work per active second, which includes work already spent inside unreported tasks. Recorded termination can include tracking and cleanup; it is not an independently measured final-node time. Exact terminal observations stay in the report but are excluded from forecast summaries. Undefined ratios are `null`. Band hits and widths describe these correlated observations; they are not independent calibration trials.

The first replay's source normalization recipe, manifest and report are in `scratch/eta-replay-20261114/` on dreeves's machine. It covers folded 480:13 and unrestricted 288:10; the latter retains 365 observations with both work and time measurements, and has no saved total-work bands. The evaluator itself needs only Python's standard library. Its quals are [../quals/quals_eta_replay.py](../quals/quals_eta_replay.py).

## Watching

- [watch.py](watch.py): copies the searches' records into [../pagedata/progress.js](../pagedata/progress.js), the data of the section "Search progress": every search the same fields. After the live searches it adds the earlier ones, from [../pagedata/progress-earlier.json](../pagedata/progress-earlier.json). It holds no model and no list of searches. The watcher to run:

      nohup nice -n 15 python3 -B searchwatch/watch.py --watch >> runs/watch.log 2>&1 &

  It looks every minute and rewrites the data file when an entry changed. One runs at a time: `runs/watch.lock` holds its pid, and `kill` of that pid stops it. Restart it after editing watch.py or track.py.
- [cpu.py](cpu.py): samples the machine's CPU use, for the section's CPU charts, into `runs/cpu/`: `python3 -B searchwatch/cpu.py --watch`.

## Before 2026-11-11

Until then the watcher surveyed each kind of search with code of its own. Nothing runs it as a watcher any more. Of its boxes, the 26 searches that ran an hour or more are on the page in the new form; the records of that time are in `runs/archive-20261111/`. The code stays as a library: [../searches/pruning288/pruning288.py](../searches/pruning288/pruning288.py) reads its journal through it, and [shepherd.py](shepherd.py) and [../searches/fanout_672/fanout_lease.py](../searches/fanout_672/fanout_lease.py) take two helpers from it.

- [progress.py](progress.py), with [sweep288_progress.py](sweep288_progress.py) and [search592_progress.py](search592_progress.py): the old watcher and its two wrappers.
- [run_modules.py](run_modules.py): loads a run's own solver modules beside the repository's, so that a run made by older code can still be read.
- [stages.json](stages.json): the stages that follow each search before its result can be recorded, and what each costs.

## Scheduling

- [shepherd.py](shepherd.py): keeps the registered searches running: it launches one that can be launched, and stops searches when the disk runs low. It never deletes anything and never launches a search that was stopped. All four of its searches are stopped now, so it launches nothing.
- [shepherd.log](shepherd.log) and [shepherd.err](shepherd.err): its log of each change of a search's status, and what it wrote to standard error.

Each module's docstring defines its terms.
