# Architecture

## System Overview
The automated canary deployment coordinator simulates a staged server
rollout using only in-memory data structures. No cloud resources, VMs,
or containers are used. The entire cluster exists as a Python list of
dictionaries in memory.

## Components
### config.py
Central constants file. All configurable values live here — server count,
version strings, sleep durations, and failure rate. No other file hardcodes
these values.

### cluster.py
Owns the cluster state. Maintains a module-level list of 20 server objects,
each with three fields:
- `id` — integer identifier (1–20)
- `version` — currently running version string (OLD or NEW)
- `status` — current health state (healthy / updating / failed)
Exposes `initialize_cluster()`, `get_cluster()`, and `print_cluster_state()`.

### rollout.py
Contains the three core deployment functions:
`update_servers(percentage)` — filters for servers still on the old version,
calculates how many to update using `math.ceil`, updates that slice, and
logs each change.
`analyze()` — simulates a health check by generating a random float and
comparing it against `ANALYSIS_FAILURE_RATE`. Returns True (pass) or
False (fail). On failure, marks a random updated server as failed.
`rollback()` — iterates all servers, restores any on the new version back
to the old version with healthy status, and logs each restoration.

### abort.py
Handles the ABORT mechanism using two threads:
Main thread — runs the staged deployment sequence, sleeping between stages
using `interruptible_sleep()` which checks the abort flag every 1 second.
Listener thread — runs `listen_for_abort()` as a daemon thread, blocking
on `input()` waiting for the user to type ABORT. On detection, sets the
shared `threading.Event` flag.
`reset_abort()` clears the flag before each new deployment run so a
previously aborted run does not immediately trigger rollback on restart.

### main.py
Orchestrator. Calls functions from other modules in the correct sequence.
Contains no business logic itself. Checks the abort flag after every stage
and sleep, triggering rollback and early exit if set.

### Temporal Integration Layer

Four additional files (`activities.py`, `workflow.py`, `worker.py`,
`starter.py`) wrap the existing modules in a Temporal-orchestrated
execution path, run separately from `main.py`.

**Mapping:**
- `CanaryRolloutWorkflow` (`workflow.py`) — orchestrates the same stage
  sequence as `main.py`, but as a durable Workflow. Contains no I/O, no
  randomness, and no direct calls to `rollout.py`/`cluster.py` — only calls
  to Activities and `workflow.sleep()`.
- `activities.py` — each existing function is wrapped as a Temporal
  Activity: `initialize_cluster_activity`, `update_servers_activity`,
  `analyze_activity`, `rollback_activity`. Activities are where
  non-deterministic and I/O-bound work is permitted, which is why
  `analyze()`'s use of `random.random()` is safe here even though it would
  violate Workflow determinism if called directly from `workflow.py`.
- `worker.py` — connects once to the local Temporal server and polls the
  `canary-rollout-queue` task queue, executing both the Workflow and its
  Activities.
- `starter.py` — triggers one Workflow Execution per run and blocks until
  the result is available.

**Why this matters:** Temporal requires Workflow code to be deterministic
because it uses History Replay to reconstruct execution state after a
Worker crash. This is a hard SDK constraint, not a style preference —
`analyze()` had to move into an Activity for that reason alone.

**Known gap:** the original ABORT mechanism (`abort.py`) is not yet
implemented in the Temporal path. In Temporal, external interrupts are
handled via Signals, which have not yet been covered in this project's
Temporal coursework. `workflow.py` contains an explicit TODO marking this.
The Temporal-orchestrated deployment currently runs to completion or rolls
back based on `analyze()` results only, with no external abort path.

## Deployment Sequence
initialize cluster (20 servers on v1.0.0)
reset abort flag
start abort listener thread
│
├── Stage 1: update 10% (2 servers)
├── interruptible_sleep(30s)     ← ABORT catchable here
├── analyze()
│
├── Stage 2: update 50% of remaining eligible servers
├── interruptible_sleep(60s)     ← ABORT catchable here
├── analyze()
│
└── Stage 3: update remaining servers
deployment complete

## Known Fragilities
### Race condition
The abort flag is checked at 1-second intervals. ABORT typed between
checks is delayed up to 1 second. ABORT typed during `update_servers()`
is not caught until after that function returns.

### No state persistence
All cluster state exists in memory. A process crash at any point leaves
the cluster in whatever state it was in with no recovery path.

### Temporal path: no Signal-based abort; cluster state durability is History-backed, not database-backed
The Temporal integration makes both the Workflow's orchestration *and* the
cluster data itself crash-recoverable, but only up to a specific boundary.
Cluster state is passed explicitly as Activity input and output (see
`activities.py`) rather than left as a bare Python global. Because
Temporal records every Activity's input and output in Event History,
replaying that history after a Worker crash reconstructs the correct
cluster state deterministically — no external database required.

This has a real limit: it only protects state at Activity *boundaries*.
A crash mid-Activity (before that Activity returns) loses that Activity's
in-progress work. Since retries are disabled (`maximum_attempts=1`) to
avoid double-applying updates or re-rolling `analyze()`'s randomness, a
mid-Activity crash causes the Workflow to fail loudly with an Activity
error rather than resume with corrupted or duplicated state. This is
considered acceptable behavior for this project — fail visibly rather
than silently corrupt — but it means "durable" here means "durable
between completed steps," not "durable at every instant," which a real
external datastore with transactional writes could provide instead.

Signal-based ABORT handling is still not implemented (see TODO in
`workflow.py`); this remains a separate, undocumented-in-code gap pending
future coursework.

## Design Decisions
Sleep durations are configurable via `config.py` so local testing uses
30–60 second sleeps while the comments document the production equivalents
(1 hour, 2 hours).

`math.ceil` is used for percentage calculations so the update count always
rounds up — you never update fewer servers than intended due to rounding.

The listener thread uses `daemon=True` so it dies automatically when the
main process exits, preventing the program from hanging on input after
deployment completes.

Stage percentages apply to the remaining eligible pool at each stage, not
the total cluster size. This is an intentional design decision matching the
project specification's description of a staged rollout.