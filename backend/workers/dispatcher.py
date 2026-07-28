"""Replaceable in-process job dispatcher for Phase 1."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Protocol


class JobRunner(Protocol):
    def run(self, job_id: str) -> None: ...


class ThreadPoolJobDispatcher:
    def __init__(self, worker: JobRunner, max_workers: int) -> None:
        self.worker = worker
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="dohamusic-worker",
        )

    def submit(self, job_id: str) -> None:
        self.executor.submit(self.worker.run, job_id)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=True, cancel_futures=False)
