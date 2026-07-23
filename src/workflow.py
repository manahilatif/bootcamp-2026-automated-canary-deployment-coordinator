"""
CanaryRolloutWorkflow -- durable orchestration of the staged rollout.

Workflow code must be deterministic (Temporal replays it from Event History
to recover from Worker crashes), so this file contains ONLY orchestration
logic: which Activity to call next, and how long to sleep between stages.
No randomness, no direct logging/printing, no threading -- that all lives
in activities.py.

Cluster state is threaded explicitly through each Activity call as an
argument and return value (see activities.py). Because Temporal records
every Activity's input and output in Event History, replaying that history
after a Worker crash reconstructs `cluster_state` deterministically --
this is what makes the rollout state durable, without any external
database.

Signal-based ABORT handling is intentionally NOT implemented yet -- see
TODO below. This is a known, documented gap, not an oversight.

Retries are disabled (maximum_attempts=1) on every Activity. Without this,
a retried update_servers_activity would update the *next* batch of servers
on retry, and a retried analyze_activity would re-roll its random check --
both would silently corrupt the rollout. Disabling retries means a
transient failure fails the Activity (and, by default, the Workflow)
loudly instead.

Because retries are disabled, any Activity failure raises an ActivityError
inside the Workflow. The run() method below catches that, logs it via
Temporal's replay-safe logging API (workflow.logger), and attempts a
rollback using the last cluster_state successfully returned before the
failure -- then re-raises so the Workflow still correctly ends in a
Failed status. A Failed status is the right outcome for a genuine
infrastructure failure; the fix here is adding visible logging and a
best-effort cleanup attempt, not suppressing the failure.
"""

from datetime import timedelta
from typing import Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

# Activities (and config, which is pure data with no side effects) are
# imported through this pass-through block so Temporal's workflow sandbox
# doesn't try to re-execute activities.py's imports (rollout.py calls
# logging.basicConfig() at import time, which the sandbox would otherwise
# flag).
with workflow.unsafe.imports_passed_through():
    import config
    from activities import (
        initialize_cluster_activity,
        update_servers_activity,
        analyze_activity,
        rollback_activity,
    )

ACTIVITY_TIMEOUT = timedelta(seconds=10)
NO_RETRY = RetryPolicy(maximum_attempts=1)


@workflow.defn
class CanaryRolloutWorkflow:
    @workflow.run
    async def run(self) -> str:
        # TODO: ABORT handling via a Temporal Signal belongs here, once
        # covered in course material. Until then, this Workflow always
        # runs to completion or rolls back based on analyze() results only --
        # there is no external interrupt path, unlike the original
        # abort.py-based console listener.

        cluster_state: Optional[list[dict[str, Any]]] = None

        try:
            cluster_state = await workflow.execute_activity(
                initialize_cluster_activity,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=NO_RETRY,
            )

            # --- Stage 1: 10% ---
            cluster_state = await workflow.execute_activity(
                update_servers_activity,
                args=[cluster_state, config.STAGE_1_PERCENT],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=NO_RETRY,
            )
            await workflow.sleep(timedelta(seconds=config.SLEEP_STAGE_1))

            passed, cluster_state = await workflow.execute_activity(
                analyze_activity,
                args=[cluster_state],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=NO_RETRY,
            )
            if not passed:
                cluster_state = await workflow.execute_activity(
                    rollback_activity,
                    args=[cluster_state],
                    start_to_close_timeout=ACTIVITY_TIMEOUT,
                    retry_policy=NO_RETRY,
                )
                return "ROLLED BACK after Stage 1 analysis"

            # --- Stage 2: 50% ---
            cluster_state = await workflow.execute_activity(
                update_servers_activity,
                args=[cluster_state, config.STAGE_2_PERCENT],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=NO_RETRY,
            )
            await workflow.sleep(timedelta(seconds=config.SLEEP_STAGE_2))

            passed, cluster_state = await workflow.execute_activity(
                analyze_activity,
                args=[cluster_state],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=NO_RETRY,
            )
            if not passed:
                cluster_state = await workflow.execute_activity(
                    rollback_activity,
                    args=[cluster_state],
                    start_to_close_timeout=ACTIVITY_TIMEOUT,
                    retry_policy=NO_RETRY,
                )
                return "ROLLED BACK after Stage 2 analysis"

            # --- Stage 3: remaining ---
            cluster_state = await workflow.execute_activity(
                update_servers_activity,
                args=[cluster_state, 1.0],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=NO_RETRY,
            )

            return "DEPLOYMENT COMPLETE"

        except Exception:
            workflow.logger.error(
                "Activity failed during rollout; attempting rollback of "
                "last known cluster state before failing the Workflow."
            )
            if cluster_state is not None:
                try:
                    await workflow.execute_activity(
                        rollback_activity,
                        args=[cluster_state],
                        start_to_close_timeout=ACTIVITY_TIMEOUT,
                        retry_policy=NO_RETRY,
                    )
                except Exception:
                    workflow.logger.error(
                        "Rollback attempt also failed after the original "
                        "Activity failure. Cluster may be left in a "
                        "partially-updated state."
                    )
            raise