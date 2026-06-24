# Failure Mode Demonstration

## Failure Mode 1: ABORT Race Condition

### What happens
When the user types ABORT, the console listener thread sets the abort flag.
However, the main thread only checks this flag at 1-second intervals inside
`interruptible_sleep()`. If ABORT is typed between checks, the main thread
continues executing for up to 1 second before catching the signal.

More critically, if ABORT is typed while `update_servers()` is executing,
the function completes fully before the abort is caught. Servers get updated
that shouldn't have been.

### Why this is fragile
Two threads share state (the abort flag) with no synchronization beyond
`threading.Event`. The main thread and listener thread are not coordinated —
the abort is caught lazily, not instantly.

### Evidence
Run `python src/main.py` and type ABORT during the sleep phase. The log
shows a delay between "ABORT received" and "Sleep interrupted by ABORT".

## Failure Mode 2: Process Crash — Half-Updated Cluster

### What happens
If the process is killed mid-stage (Ctrl+C, system crash, OOM kill), the
in-memory cluster state is lost entirely. No rollback runs. The script has
no way to recover because state was never persisted anywhere.

### Demonstrated output
Server 1 → V2.0.0
Server 2 → V2.0.0
Cluster State:
V2.0.0: 2 servers
V1.0.0: 18 servers
KeyboardInterrupt

After this crash, servers 1 and 2 are on V2.0.0 and the remaining 18 are
on V1.0.0 — but the script has no memory of this. Restarting the script
reinitializes the cluster to V1.0.0, erasing all evidence of the partial
update.

### Why production systems don't work this way
Real deployment systems persist rollout state to a database or state machine
(e.g. Kubernetes deployment records, AWS CodeDeploy). If the coordinator
crashes, the state survives and recovery is possible. This simulation
intentionally omits persistence to demonstrate what happens without it.

### Evidence
See `screenshots/failure-crash.png`