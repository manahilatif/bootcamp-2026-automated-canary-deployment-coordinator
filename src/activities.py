"""
Temporal Activities for the canary rollout coordinator.

These are thin wrappers around the existing rollout.py / cluster.py functions.
Activities are where non-deterministic and I/O-bound work is allowed to live —
that's why analyze() (which uses random.random()) is safe here, even though
it would violate Workflow determinism if called directly from workflow.py.
"""

from temporalio import activity

import cluster as cluster_module
import rollout


@activity.defn
def initialize_cluster_activity() -> None:
    cluster_module.initialize_cluster()
    cluster_module.print_cluster_state()


@activity.defn
def update_servers_activity(percentage: float) -> int:
    updated = rollout.update_servers(percentage)
    return len(updated)


@activity.defn
def analyze_activity() -> bool:
    return rollout.analyze()


@activity.defn
def rollback_activity() -> None:
    rollout.rollback()


@activity.defn
async def analyze_activity() -> bool:
    return rollout.analyze()


@activity.defn
async def rollback_activity() -> None:
    rollout.rollback()