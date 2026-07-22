"""
Starter script. With worker.py running in another terminal:

    python starter.py

Triggers one Workflow Execution and blocks until it finishes.
"""

import asyncio
import uuid

from temporalio.client import Client

from workflow import CanaryRolloutWorkflow

TASK_QUEUE = "canary-rollout-queue"


async def main():
    client = await Client.connect("localhost:7233")

    # A fresh UUID per run, since this project doesn't need idempotency
    # across repeated triggers (unlike, e.g., an email-triggered workflow
    # where you'd want a deterministic ID to prevent duplicates). If your
    # bootcamp wants re-runs to be treated as the same logical deployment,
    # this would need to change to a deterministic ID instead.
    workflow_id = f"canary-rollout-{uuid.uuid4()}"

    handle = await client.start_workflow(
        CanaryRolloutWorkflow.run,
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    print(f"Started workflow. ID: {handle.id}")

    result = await handle.result()
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())