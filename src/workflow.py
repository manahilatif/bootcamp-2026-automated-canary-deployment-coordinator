"""
CanaryRolloutWorkflow — durable orchestration of the staged rollout.

Workflow code must be deterministic (Temporal replays it from Event History
to recover from Worker crashes), so this file contains ONLY orchestration
logic: which Activity to call next, and how long to sleep between stages.
No randomness, no direct logging/printing, no threading — that all lives
in activities.py.

Signal-based ABORT handling is intentionally NOT implemented yet — see TODO
below. This is a known, documented gap, not an oversight.
"""

from datetime import timedelta

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
NO_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


@workflow.defn
class CanaryRolloutWorkflow:
    @workflow.run
    async def run(self) -> str:
        # TODO: ABORT handling via a Temporal Signal belongs here, once
        # covered in course material. Until then, this Workflow always
        # runs to completion or rolls back based on analyze() results only —
        # there is no external interrupt path, unlike the original
        # abort.py-based console listener.

        await workflow.execute_activity(
            initialize_cluster_activity,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=NO_RETRY_POLICY,
        )

        # --- Stage 1: 10% ---
        await workflow.execute_activity(
            update_servers_activity,
            config.STAGE_1_PERCENT,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=NO_RETRY_POLICY,
        )
        await workflow.sleep(timedelta(seconds=config.SLEEP_STAGE_1))

        passed = await workflow.execute_activity(
            analyze_activity,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=NO_RETRY_POLICY,
        )
        if not passed:
            await workflow.execute_activity(
                rollback_activity,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=NO_RETRY_POLICY,
            )
            return "ROLLED BACK after Stage 1 analysis"

        # --- Stage 2: 50% ---
        await workflow.execute_activity(
            update_servers_activity,
            config.STAGE_2_PERCENT,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=NO_RETRY_POLICY,
        )
        await workflow.sleep(timedelta(seconds=config.SLEEP_STAGE_2))

        passed = await workflow.execute_activity(
            analyze_activity,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=NO_RETRY_POLICY,
        )
        if not passed:
            await workflow.execute_activity(
                rollback_activity,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=NO_RETRY_POLICY,
            )
            return "ROLLED BACK after Stage 2 analysis"

        # --- Stage 3: remaining ---
        await workflow.execute_activity(
            update_servers_activity,
            1.0,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=NO_RETRY_POLICY,
        )

        return "DEPLOYMENT COMPLETE"