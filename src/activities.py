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
"""

from typing import Any

from temporalio import activity

import cluster as cluster_module
import rollout


def _load_state(cluster_state: list[dict[str, Any]]) -> None:
    """Seed the process-global cluster from Workflow-supplied state."""
    cluster_module.cluster = cluster_state


@activity.defn
async def initialize_cluster_activity() -> list[dict[str, Any]]:
    cluster_module.initialize_cluster()
    cluster_module.print_cluster_state()
    return cluster_module.get_cluster()


@activity.defn
async def update_servers_activity(
    cluster_state: list[dict[str, Any]], percentage: float
) -> list[dict[str, Any]]:
    _load_state(cluster_state)
    rollout.update_servers(percentage)
    return cluster_module.get_cluster()


@activity.defn
async def analyze_activity(
    cluster_state: list[dict[str, Any]]
) -> tuple[bool, list[dict[str, Any]]]:
    _load_state(cluster_state)
    passed = rollout.analyze()
    return passed, cluster_module.get_cluster()


@activity.defn
async def rollback_activity(
    cluster_state: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    _load_state(cluster_state)
    rollout.rollback()
    return cluster_module.get_cluster()