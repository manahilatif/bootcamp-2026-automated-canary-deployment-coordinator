"""
Worker process. Run this in its own terminal and leave it running —
it polls the task queue and executes both the Workflow and its Activities.
    python src/worker.py

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from workflow import CanaryRolloutWorkflow

TASK_QUEUE = "canary-rollout-queue"


async def main():
    logging.basicConfig(level=logging.INFO)

    # Import after logging config so rollout.py's import-time logging.basicConfig()
    # does not prevent this Worker process from configuring logging.
    import activities

    # Connected once, here, for the lifetime of this Worker process —
    # not reconnected per task. (Flagged in an earlier peer review as a
    # common mistake: don't call Client.connect() inside a per-request
    # function.)
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[CanaryRolloutWorkflow],
        activities=[
            activities.initialize_cluster_activity,
            activities.update_servers_activity,
            activities.analyze_activity,
            activities.rollback_activity,
        ],
    )

    logging.info(f"Worker started. Polling task queue '{TASK_QUEUE}'...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())