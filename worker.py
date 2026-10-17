"""Temporal worker. Leave this process running while the API accepts jobs.

    python worker.py
"""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker

import db
from activities import caption_and_store, discover_videos, extract_frames_activity, notify_complete
from workflow import TASK_QUEUE, IndexFootageWorkflow

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    load_dotenv()
    await db.init_pool()
    address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    queue = os.environ.get("TEMPORAL_TASK_QUEUE", TASK_QUEUE)
    client = await Client.connect(address, namespace=namespace)
    worker = Worker(
        client,
        task_queue=queue,
        workflows=[IndexFootageWorkflow],
        activities=[discover_videos, extract_frames_activity, caption_and_store, notify_complete],
    )
    logging.info("Worker listening on %s queue %s", address, queue)
    try:
        await worker.run()
    finally:
        await db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
