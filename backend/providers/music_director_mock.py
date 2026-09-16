from __future__ import annotations

import hashlib
from dataclasses import dataclass
from threading import Lock

from backend.contracts.music_director_provider import (
    MusicDirectorProviderCandidate,
    MusicDirectorProviderRequest,
    MusicDirectorProviderResult,
    MusicDirectorProviderStatus,
    MusicDirectorProviderSubmission,
)


class MockMusicDirectorProviderError(RuntimeError):
    pass


@dataclass(slots=True)
class _RemoteExecution:
    request: MusicDirectorProviderRequest
    external_id: str
    status: MusicDirectorProviderStatus
    result: MusicDirectorProviderResult | None


class MockMusicDirectorProvider:
    provider_id = "mock-music-director"

    def __init__(self, *, mode: str = "success") -> None:
        self._mode = mode
        self._executions: dict[str, _RemoteExecution] = {}
        self._lock = Lock()
        self.submit_calls = 0
        self.read_calls = 0

    @property
    def remote_execution_count(self) -> int:
        return len(self._executions)

    def submit(self, request: MusicDirectorProviderRequest) -> MusicDirectorProviderSubmission:
        self.submit_calls += 1
        with self._lock:
            existing = self._executions.get(request.client_execution_key)
            if existing is not None:
                if existing.request != request:
                    raise MockMusicDirectorProviderError("CLIENT_EXECUTION_KEY_CONFLICT")
                return MusicDirectorProviderSubmission(existing.external_id)
            external_id = (
                "mock-"
                + hashlib.sha256(request.client_execution_key.encode("ascii")).hexdigest()[:32]
            )
            result = self._result(request, external_id)
            status = (
                MusicDirectorProviderStatus.FAILED
                if self._mode == "failed"
                else MusicDirectorProviderStatus.SUCCEEDED
            )
            self._executions[request.client_execution_key] = _RemoteExecution(
                request, external_id, status, result
            )
            return MusicDirectorProviderSubmission(external_id)

    def read_status(self, external_execution_id: str) -> MusicDirectorProviderStatus:
        self.read_calls += 1
        return self._execution(external_execution_id).status

    def read_result(self, external_execution_id: str) -> MusicDirectorProviderResult:
        self.read_calls += 1
        execution = self._execution(external_execution_id)
        if (
            execution.status is not MusicDirectorProviderStatus.SUCCEEDED
            or execution.result is None
        ):
            raise MockMusicDirectorProviderError("RESULT_NOT_AVAILABLE")
        return execution.result

    def cancel(self, external_execution_id: str) -> MusicDirectorProviderStatus:
        execution = self._execution(external_execution_id)
        if execution.status not in {
            MusicDirectorProviderStatus.SUCCEEDED,
            MusicDirectorProviderStatus.FAILED,
        }:
            execution.status = MusicDirectorProviderStatus.CANCELLED
        return execution.status

    def _execution(self, external_id: str) -> _RemoteExecution:
        for execution in self._executions.values():
            if execution.external_id == external_id:
                return execution
        raise MockMusicDirectorProviderError("EXECUTION_NOT_FOUND")

    def _result(
        self, request: MusicDirectorProviderRequest, external_id: str
    ) -> MusicDirectorProviderResult | None:
        if self._mode == "failed":
            return None
        candidates = [
            MusicDirectorProviderCandidate(
                ordinal,
                {
                    "schema_version": 1,
                    "source_snapshot_id": str(request.source_snapshot_id),
                    "operations": [{"operation": "set_master_gain", "gain_db": ordinal - 1}],
                },
            )
            for ordinal in range(request.intent.candidate_count)
        ]
        if self._mode == "wrong_count":
            candidates.pop()
        elif self._mode == "duplicate_ordinal" and len(candidates) > 1:
            candidates[1] = MusicDirectorProviderCandidate(0, candidates[1].proposal)
        elif self._mode == "invalid_proposal":
            candidates[0] = MusicDirectorProviderCandidate(0, {"invalid": True})
        return MusicDirectorProviderResult(external_id, tuple(candidates))
