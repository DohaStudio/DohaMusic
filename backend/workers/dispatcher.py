"""Replaceable in-process job dispatcher for Phase 1."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Protocol


class JobRunner(Protocol):
    def run(self, job_id: str) -> None: ...


class ThreadPoolJobDispatcher:
    def __init__(
        self,
        worker: JobRunner,
        max_workers: int | None = None,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        if executor is None and max_workers is None:
            raise ValueError("max_workers is required without a shared executor")
        self.worker = worker
        self._owns_executor = executor is None
        self.executor = executor or ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="dohamusic-worker"
        )

    def submit(self, job_id: str) -> None:
        self.executor.submit(self.worker.run, job_id)

    def shutdown(self) -> None:
        if self._owns_executor:
            self.executor.shutdown(wait=True, cancel_futures=False)
