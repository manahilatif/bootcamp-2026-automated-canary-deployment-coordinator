"""
Temporal Activities for the canary rollout coordinator.

Cluster state is passed explicitly into and out of each Activity, rather
than relying purely on cluster.py's process-global list. The Workflow
holds the canonical state between calls; Temporal's Event History records
each Activity's input and output, so a Worker crash and restart can
recover the correct cluster state via History Replay -- without needing
an external database.

Non-deterministic and I/O-bound work (analyze()'s randomness, all
logging/printing) still lives here, never in the Workflow.

These Activities are plain (synchronous) functions, not `async def`. They
call synchronous code (rollout.py / cluster.py) with no internal await
points, so running them as `async def` would execute that work directly
on the Worker's asyncio event loop and block it. Declaring them as plain
functions lets Temporal run them on the Worker's activity_executor thread
pool instead (see worker.py) -- this is required, not optional, for
non-async Activity definitions.
"""

from typing import Any

from temporalio import activity

import cluster as cluster_module
import rollout


def _load_state(cluster_state: list[dict[str, Any]]) -> None:
    """Seed the process-global cluster from Workflow-supplied state.

    Known limitation: this mutates a process-level global. If a single
    Worker process ever executes two Workflow Executions concurrently,
    they will overwrite each other's in-progress state here. Acceptable
    for this project's single-workflow-at-a-time local demo; a production
    version would need per-execution isolation (e.g. state keyed by
    Workflow ID) rather than a bare module global.
    """
    cluster_module.cluster = cluster_state


@activity.defn
def initialize_cluster_activity() -> list[dict[str, Any]]:
    cluster_module.initialize_cluster()
    cluster_module.print_cluster_state()
    return cluster_module.get_cluster()


@activity.defn
def update_servers_activity(
    cluster_state: list[dict[str, Any]], percentage: float
) -> list[dict[str, Any]]:
    _load_state(cluster_state)
    rollout.update_servers(percentage)
    return cluster_module.get_cluster()


@activity.defn
def analyze_activity(
    cluster_state: list[dict[str, Any]]
) -> tuple[bool, list[dict[str, Any]]]:
    _load_state(cluster_state)
    passed = rollout.analyze()
    return passed, cluster_module.get_cluster()


@activity.defn
def rollback_activity(
    cluster_state: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    _load_state(cluster_state)
    rollout.rollback()
    return cluster_module.get_cluster()