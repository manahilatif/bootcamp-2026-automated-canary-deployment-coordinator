"""
Worker process. Run this in its own terminal and leave it running --
it polls the task queue and executes both the Workflow and its Activities.

    python src/worker.py

Activities in this project are declared as plain (synchronous) functions,
not `async def` -- see activities.py for why. Temporal's Python SDK
requires a thread pool executor (activity_executor) to run synchronous
Activities; without it, Worker construction raises an error. That's what
the ThreadPoolExecutor below is for.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

# Import after configuring logging so rollout.py's import-time
# logging.basicConfig() does not prevent this Worker process from
# configuring its own logging. (Flagged in an earlier peer review as a
# common mistake: don't call Client.connect() inside a per-request
# function -- also applies here to import ordering.)

TASK_QUEUE = "canary-rollout-queue"


async def main():
    logging.basicConfig(level=logging.INFO)

    import activities
    from workflow import CanaryRolloutWorkflow

    # Connected once, here, for the lifetime of this Worker process --
    # not reconnected per task.
    client = await Client.connect("localhost:7233")

    with ThreadPoolExecutor(max_workers=4) as activity_executor:
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
            activity_executor=activity_executor,
        )

        logging.info(f"Worker started. Polling task queue '{TASK_QUEUE}'...")
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())