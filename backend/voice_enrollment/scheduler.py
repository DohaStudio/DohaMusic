"""Process-local scheduler for Voice Enrollment maintenance."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from backend.core.logging import get_logger
from backend.voice_enrollment.maintenance import VoiceEnrollmentMaintenanceService

logger = get_logger(__name__)


class VoiceEnrollmentScheduler:
    """Run independent maintenance scans without using the AI worker pool."""

    def __init__(
        self,
        *,
        maintenance: VoiceEnrollmentMaintenanceService,
        expiration_interval_seconds: float,
        cleanup_interval_seconds: float,
        orphan_interval_seconds: float,
    ) -> None:
        intervals = (
            expiration_interval_seconds,
            cleanup_interval_seconds,
            orphan_interval_seconds,
        )
        if any(interval <= 0 for interval in intervals):
            raise ValueError("Voice Enrollment scheduler intervals must be positive")
        self.maintenance = maintenance
        self.expiration_interval_seconds = expiration_interval_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.orphan_interval_seconds = orphan_interval_seconds
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.is_running:
            return
        try:
            await asyncio.to_thread(self.maintenance.recover_startup)
        except Exception:  # noqa: BLE001 - scheduler boundary keeps API available
            logger.error("voice_maintenance_recovery failed")
        self._stop.clear()
        self._task = asyncio.create_task(
            self._run(), name="voice-enrollment-maintenance"
        )
        logger.info(
            "voice_maintenance_scheduler started expiration_interval=%s "
            "cleanup_interval=%s orphan_interval=%s",
            self.expiration_interval_seconds,
            self.cleanup_interval_seconds,
            self.orphan_interval_seconds,
        )

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        self._stop.set()
        await asyncio.gather(task, return_exceptions=True)
        self._task = None
        logger.info("voice_maintenance_scheduler stopped")

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        scans: list[tuple[float, float, Callable[[], int]]] = [
            (
                self.expiration_interval_seconds,
                loop.time() + self.expiration_interval_seconds,
                self.maintenance.expire_enrollments,
            ),
            (
                self.cleanup_interval_seconds,
                loop.time() + self.cleanup_interval_seconds,
                self.maintenance.process_cleanup,
            ),
            (
                self.orphan_interval_seconds,
                loop.time() + self.orphan_interval_seconds,
                self.maintenance.scan_orphans,
            ),
        ]
        try:
            while not self._stop.is_set():
                timeout = max(
                    0.0, min(next_run for _, next_run, _ in scans) - loop.time()
                )
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=timeout)
                except TimeoutError:
                    pass
                if self._stop.is_set():
                    break
                now = loop.time()
                updated: list[tuple[float, float, Callable[[], int]]] = []
                for interval, next_run, scan in scans:
                    if next_run <= now:
                        await self._run_scan(scan)
                        while next_run <= now:
                            next_run += interval
                    updated.append((interval, next_run, scan))
                scans = updated
        except asyncio.CancelledError:
            pass

    @staticmethod
    async def _run_scan(scan: Callable[[], int]) -> None:
        try:
            await asyncio.to_thread(scan)
        except Exception:  # noqa: BLE001 - isolate one failed maintenance cycle
            logger.error("voice_maintenance_scan failed")
