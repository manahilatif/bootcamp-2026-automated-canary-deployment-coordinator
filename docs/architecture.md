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