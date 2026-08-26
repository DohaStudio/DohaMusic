from __future__ import annotations

import hashlib
import io
import threading
import wave
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.core.config import Settings
from backend.core.payload_locator import (
    PayloadLocatorError,
    PayloadLocatorErrorCode,
    PayloadLocatorIssue,
    PayloadLocatorRecord,
    PayloadLocatorRevocationReason,
    PayloadLocatorStatus,
)
from backend.providers.vocal import (
    HttpVocalProviderTransport,
    VerifiedVocalPayload,
    VocalPayloadAcquisitionError,
    VocalPayloadAcquisitionErrorCode,
    VocalPayloadAcquisitionRequest,
)
from backend.services.workspace import (
    PayloadStagingAuthority,
    PayloadStagingService,
    TrustedPayloadSourceCandidate,
    TrustedProviderResultCandidate,
    VocalPayloadReconciliationError,
    VocalPayloadReconciliationErrorCode,
    VocalPayloadReconciliationService,
)
from backend.storage import LocalFilesystemStagingAdapter

NOW = datetime(2100, 1, 1, 12, tzinfo=UTC)


def _wav_bytes() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as payload:
        payload.setnchannels(1)
        payload.setsampwidth(2)
        payload.setframerate(8_000)
        payload.writeframes(b"\x00\x00" * 80)
    return output.getvalue()


class _FakeAcquisition:
    def __init__(self, content: bytes, callback=None) -> None:
        self.content = content
        self.callback = callback
        self.requests: list[VocalPayloadAcquisitionRequest] = []
        self.error: VocalPayloadAcquisitionErrorCode | None = None
        self._lock = threading.Lock()

    def acquire_payload(self, request: VocalPayloadAcquisitionRequest) -> VerifiedVocalPayload:
        with self._lock:
            self.requests.append(request)
        if self.callback is not None:
            self.callback()
        if self.error is not None:
            raise VocalPayloadAcquisitionError(self.error)
        return VerifiedVocalPayload(
            job_id=request.job_id,
            provider_artifact_id=request.payload.provider_artifact_id,
            source_id=request.payload.source.source_id,
            media_type=request.payload.expected_media_type,
            size_bytes=len(self.content),
            checksum_algorithm="sha256",
            payload_checksum=hashlib.sha256(self.content).hexdigest(),
            content=self.content,
        )


class _FakeLocators:
    def __init__(self, record: PayloadLocatorRecord) -> None:
        self.record = record
        self.now = NOW
        self.cas_calls = 0
        self._lock = threading.Lock()

    def get(self, locator_id: object) -> PayloadLocatorRecord:
        assert locator_id == self.record.locator_id
        with self._lock:
            return self.record

    def resolve_for_acquisition(
        self, locator_id: object, *, workspace_job_id, rights_granted
    ) -> PayloadLocatorRecord:
        record = self.get(locator_id)
        self._require_access(record, workspace_job_id, rights_granted)
        if record.staging_status is not PayloadLocatorStatus.SOURCE_BOUND:
            raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
        if (
            record.issue.source_available_until is not None
            and self.now >= record.issue.source_available_until
        ):
            raise PayloadLocatorError(PayloadLocatorErrorCode.SOURCE_EXPIRED)
        return record

    def resolve_verified_staging(
        self, locator_id: object, *, workspace_job_id, rights_granted
    ) -> PayloadLocatorRecord:
        record = self.get(locator_id)
        self._require_access(record, workspace_job_id, rights_granted)
        if record.staging_status is not PayloadLocatorStatus.VERIFIED_STAGED:
            raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
        return record

    def transition_to_verified_staged(self, locator_id, *, expected_revision, facts):
        with self._lock:
            self.cas_calls += 1
            current = self.record
            if current.lifecycle_revision != expected_revision:
                raise PayloadLocatorError(PayloadLocatorErrorCode.REVISION_CONFLICT)
            if current.revoked:
                raise PayloadLocatorError(PayloadLocatorErrorCode.REVOKED)
            if current.staging_status is not PayloadLocatorStatus.SOURCE_BOUND:
                raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
            self.record = replace(
                current,
                staging_status=PayloadLocatorStatus.VERIFIED_STAGED,
                staging_backend=facts.staging_backend,
                staging_key=facts.staging_key,
                actual_checksum_algorithm=facts.actual_checksum_algorithm,
                actual_payload_checksum=facts.actual_payload_checksum,
                actual_size_bytes=facts.actual_size_bytes,
                actual_media_type=facts.actual_media_type,
                verified_at=facts.verified_at,
                lifecycle_revision=current.lifecycle_revision + 1,
                updated_at=NOW,
            )
            return self.record

    @staticmethod
    def _require_access(record, workspace_job_id, rights_granted) -> None:
        if record.issue.workspace_job_id != workspace_job_id:
            raise PayloadLocatorError(PayloadLocatorErrorCode.WORKSPACE_BINDING_MISMATCH)
        if not rights_granted:
            raise PayloadLocatorError(PayloadLocatorErrorCode.RIGHTS_REQUIRED)
        if record.revoked:
            raise PayloadLocatorError(PayloadLocatorErrorCode.REVOKED)


def _foundation(tmp_path: Path):
    content = _wav_bytes()
    checksum = hashlib.sha256(content).hexdigest()
    workspace_job_id = uuid4()
    binding_id = uuid4()
    issue = PayloadLocatorIssue(
        workspace_job_id=workspace_job_id,
        provider_job_binding_id=binding_id,
        payload_ordinal=0,
        provider_artifact_id="artifact-1",
        role="converted_vocal_candidate",
        source_kind="provider_subresource",
        source_id="payload-1",
        artifact_kind="audio",
        expected_checksum_algorithm="sha256",
        expected_payload_checksum=checksum,
        expected_size_bytes=len(content),
        expected_media_type="audio/wav",
        source_available_until=NOW + timedelta(hours=1),
        locator_expires_at=NOW + timedelta(days=1),
    )
    record = PayloadLocatorRecord(
        locator_uuid=uuid4(),
        issue=issue,
        staging_status=PayloadLocatorStatus.SOURCE_BOUND,
        staging_backend=None,
        staging_key=None,
        actual_checksum_algorithm=None,
        actual_payload_checksum=None,
        actual_size_bytes=None,
        actual_media_type=None,
        verified_at=None,
        ingested_artifact_id=None,
        ingested_at=None,
        revoked_at=None,
        revocation_reason=None,
        cleanup_requested_at=None,
        cleanup_completed_at=None,
        lifecycle_revision=0,
        created_at=NOW,
        updated_at=NOW,
    )
    payload = TrustedPayloadSourceCandidate(
        provider_artifact_id=issue.provider_artifact_id,
        role=issue.role,
        source_kind=issue.source_kind,
        source_id=issue.source_id,
        checksum_algorithm=issue.expected_checksum_algorithm,
        payload_checksum=issue.expected_payload_checksum,
        expected_size_bytes=issue.expected_size_bytes,
        expected_media_type=issue.expected_media_type,
        available_until=issue.source_available_until,
    )
    candidate = TrustedProviderResultCandidate(
        workspace_job_id=workspace_job_id,
        provider_job_binding_id=binding_id,
        provider_id="dohavocal",
        provider_job_id="vocal-job-1",
        output_role=issue.role,
        provider_artifact_id=issue.provider_artifact_id,
        provider_result_artifact_id="result-artifact-1",
        provider_output_asset_version_id="provider-version-1",
        source_asset_version_id=uuid4(),
        parent_asset_version_id=uuid4(),
        processing_chain_id=uuid4(),
        model_manifest_id="dynamic-vocal@2",
        settings_snapshot={},
        artifact_kind="audio",
        media_type="audio/wav",
        payload_present=True,
        metadata_checksum="b" * 64,
        checksum_scope="metadata_descriptor",
        created_at=NOW,
        provider_source_artifact_id=None,
        provider_parent_artifact_id=None,
        processing_types=("voice_conversion",),
        analysis_result=None,
        payloads=(payload,),
    )
    root = tmp_path / "staging"
    root.mkdir()
    adapter = LocalFilesystemStagingAdapter(root, clock=lambda: NOW)
    locators = _FakeLocators(record)
    acquisition = _FakeAcquisition(content)
    service = VocalPayloadReconciliationService(
        acquisition,
        locators,
        PayloadStagingService(locators, adapter),
        adapter,
        max_payload_size_bytes=1024 * 1024,
    )
    return service, acquisition, locators, adapter, candidate, content, root


def _authority(job_id, values: list[tuple[bool, bool, bool]] | None = None):
    calls = 0
    states = values or [(True, True, False)]

    def provide() -> PayloadStagingAuthority:
        nonlocal calls
        state = states[min(calls, len(states) - 1)]
        calls += 1
        rights, claim, cancelled = state
        return PayloadStagingAuthority(job_id, rights, claim, cancelled)

    return provide


def _assert_error(error, code) -> None:
    assert error.value.code is code
    assert "http" not in str(error.value).lower()
    assert "staging\\" not in str(error.value).lower()


def test_source_bound_acquires_exact_payload_and_stages(tmp_path: Path) -> None:
    service, acquisition, locators, _, candidate, content, root = _foundation(tmp_path)

    result = service.reconcile(
        locators.record.locator_id,
        candidate,
        _authority(candidate.workspace_job_id),
    )

    assert result.staging_status is PayloadLocatorStatus.VERIFIED_STAGED
    assert locators.cas_calls == 1
    assert len(acquisition.requests) == 1
    request = acquisition.requests[0]
    assert request.job_id == candidate.provider_job_id
    assert request.payload.provider_artifact_id == candidate.provider_artifact_id
    assert request.payload.source.source_id == candidate.payloads[0].source_id
    assert request.max_size_bytes == 1024 * 1024
    assert result.staging_key is not None
    assert (root / result.staging_key).read_bytes() == content


def test_mock_http_get_payload_content_flows_into_verified_staging(tmp_path: Path) -> None:
    service, _, locators, adapter, candidate, content, root = _foundation(tmp_path)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={
                "Content-Type": "audio/wav",
                "Content-Length": str(len(content)),
            },
            content=content,
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = HttpVocalProviderTransport(
        base_url="https://trusted.example/runtime",
        client=http_client,
    )
    runtime = VocalPayloadReconciliationService(
        transport,
        locators,
        PayloadStagingService(locators, adapter),
        adapter,
        max_payload_size_bytes=1024 * 1024,
    )
    try:
        result = runtime.reconcile(
            locators.record.locator_id,
            candidate,
            _authority(candidate.workspace_job_id),
        )
    finally:
        transport.close()
        http_client.close()

    assert len(requests) == 1
    assert requests[0].url == (
        "https://trusted.example/runtime/v1/jobs/vocal-job-1/artifacts/"
        "artifact-1/payloads/payload-1"
    )
    assert requests[0].headers["accept"] == "audio/wav"
    assert result.staging_key is not None
    assert (root / result.staging_key).read_bytes() == content


def test_verified_staged_reentry_verifies_without_network(tmp_path: Path) -> None:
    service, acquisition, locators, _, candidate, _, _ = _foundation(tmp_path)
    authority = _authority(candidate.workspace_job_id)
    first = service.reconcile(locators.record.locator_id, candidate, authority)
    acquisition.requests.clear()

    second = service.reconcile(first.locator_id, candidate, authority)

    assert second == first
    assert acquisition.requests == []
    assert locators.cas_calls == 1


def test_verified_staged_reentry_ignores_provider_source_expiry(tmp_path: Path) -> None:
    service, acquisition, locators, _, candidate, _, _ = _foundation(tmp_path)
    authority = _authority(candidate.workspace_job_id)
    staged = service.reconcile(locators.record.locator_id, candidate, authority)
    locators.now = NOW + timedelta(hours=2)
    acquisition.requests.clear()

    assert service.reconcile(staged.locator_id, candidate, authority) == staged
    assert acquisition.requests == []


def test_verified_staged_tamper_fails_closed_without_reacquisition(tmp_path: Path) -> None:
    service, acquisition, locators, _, candidate, content, root = _foundation(tmp_path)
    authority = _authority(candidate.workspace_job_id)
    staged = service.reconcile(locators.record.locator_id, candidate, authority)
    assert staged.staging_key is not None
    (root / staged.staging_key).write_bytes(content[:-2] + b"XX")
    acquisition.requests.clear()

    with pytest.raises(VocalPayloadReconciliationError) as tampered:
        service.reconcile(staged.locator_id, candidate, authority)

    _assert_error(tampered, VocalPayloadReconciliationErrorCode.INTEGRITY_FAILURE)
    assert acquisition.requests == []


def test_source_expired_before_network_is_rejected(tmp_path: Path) -> None:
    service, acquisition, locators, _, candidate, _, _ = _foundation(tmp_path)
    locators.now = NOW + timedelta(hours=2)

    with pytest.raises(VocalPayloadReconciliationError) as expired:
        service.reconcile(
            locators.record.locator_id, candidate, _authority(candidate.workspace_job_id)
        )

    _assert_error(expired, VocalPayloadReconciliationErrorCode.PAYLOAD_EXPIRED)
    assert acquisition.requests == []
    assert locators.cas_calls == 0


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        (
            VocalPayloadAcquisitionErrorCode.PAYLOAD_UNAVAILABLE,
            VocalPayloadReconciliationErrorCode.PAYLOAD_UNAVAILABLE,
        ),
        (
            VocalPayloadAcquisitionErrorCode.PAYLOAD_ACCESS_DENIED,
            VocalPayloadReconciliationErrorCode.ACCESS_DENIED,
        ),
        (
            VocalPayloadAcquisitionErrorCode.PAYLOAD_TRANSFER_FAILED,
            VocalPayloadReconciliationErrorCode.TRANSFER_FAILED,
        ),
        (
            VocalPayloadAcquisitionErrorCode.PAYLOAD_INTEGRITY_MISMATCH,
            VocalPayloadReconciliationErrorCode.INTEGRITY_FAILURE,
        ),
    ),
)
def test_acquisition_errors_are_safe_and_never_retry(tmp_path: Path, source, expected) -> None:
    service, acquisition, locators, _, candidate, _, _ = _foundation(tmp_path)
    acquisition.error = source

    with pytest.raises(VocalPayloadReconciliationError) as failed:
        service.reconcile(
            locators.record.locator_id, candidate, _authority(candidate.workspace_job_id)
        )

    _assert_error(failed, expected)
    assert len(acquisition.requests) == 1
    assert locators.cas_calls == 0


def test_pre_network_rights_denial_skips_network_and_cas(tmp_path: Path) -> None:
    service, acquisition, locators, _, candidate, _, _ = _foundation(tmp_path)

    with pytest.raises(VocalPayloadReconciliationError) as denied:
        service.reconcile(
            locators.record.locator_id,
            candidate,
            _authority(candidate.workspace_job_id, [(False, True, False)]),
        )

    _assert_error(denied, VocalPayloadReconciliationErrorCode.RIGHTS_DENIED)
    assert acquisition.requests == []
    assert locators.cas_calls == 0


@pytest.mark.parametrize(
    ("after", "expected"),
    (
        ((False, True, False), VocalPayloadReconciliationErrorCode.RIGHTS_DENIED),
        ((True, True, True), VocalPayloadReconciliationErrorCode.CANCELLATION_REQUESTED),
        ((True, False, False), VocalPayloadReconciliationErrorCode.CLAIM_LOST),
    ),
)
def test_post_network_authority_loss_skips_staging_and_cas(tmp_path: Path, after, expected) -> None:
    service, acquisition, locators, _, candidate, _, root = _foundation(tmp_path)
    authority = _authority(candidate.workspace_job_id, [(True, True, False), after])

    with pytest.raises(VocalPayloadReconciliationError) as denied:
        service.reconcile(locators.record.locator_id, candidate, authority)

    _assert_error(denied, expected)
    assert len(acquisition.requests) == 1
    assert locators.cas_calls == 0
    assert locators.record.staging_status is PayloadLocatorStatus.SOURCE_BOUND
    assert not tuple(root.rglob("*.wav"))


def test_locator_revocation_during_network_skips_staging_and_cas(tmp_path: Path) -> None:
    service, acquisition, locators, _, candidate, _, root = _foundation(tmp_path)

    def revoke() -> None:
        locators.record = replace(
            locators.record,
            revoked_at=NOW,
            revocation_reason=PayloadLocatorRevocationReason.RIGHTS_REVOKED,
            lifecycle_revision=1,
        )

    acquisition.callback = revoke
    with pytest.raises(VocalPayloadReconciliationError) as conflict:
        service.reconcile(
            locators.record.locator_id, candidate, _authority(candidate.workspace_job_id)
        )

    _assert_error(conflict, VocalPayloadReconciliationErrorCode.LOCATOR_CONFLICT)
    assert locators.cas_calls == 0
    assert not tuple(root.rglob("*.wav"))


def test_source_expiry_during_transfer_is_fail_closed(tmp_path: Path) -> None:
    service, acquisition, locators, _, candidate, _, _ = _foundation(tmp_path)
    acquisition.callback = lambda: setattr(locators, "now", NOW + timedelta(hours=2))

    with pytest.raises(VocalPayloadReconciliationError) as expired:
        service.reconcile(
            locators.record.locator_id, candidate, _authority(candidate.workspace_job_id)
        )

    _assert_error(expired, VocalPayloadReconciliationErrorCode.PAYLOAD_EXPIRED)
    assert locators.cas_calls == 0


def test_untrusted_acquisition_output_facts_are_rejected_before_staging(tmp_path: Path) -> None:
    service, acquisition, locators, _, candidate, _, root = _foundation(tmp_path)
    acquisition.content = b"not-the-advertised-payload"

    with pytest.raises(VocalPayloadReconciliationError) as integrity:
        service.reconcile(
            locators.record.locator_id, candidate, _authority(candidate.workspace_job_id)
        )

    _assert_error(integrity, VocalPayloadReconciliationErrorCode.INTEGRITY_FAILURE)
    assert locators.cas_calls == 0
    assert not tuple(root.rglob("*.wav"))


def test_binding_mismatch_fails_before_network(tmp_path: Path) -> None:
    service, acquisition, locators, _, candidate, _, _ = _foundation(tmp_path)
    mismatched = replace(candidate, provider_job_binding_id=uuid4())

    with pytest.raises(VocalPayloadReconciliationError) as mismatch:
        service.reconcile(
            locators.record.locator_id, mismatched, _authority(candidate.workspace_job_id)
        )

    _assert_error(mismatch, VocalPayloadReconciliationErrorCode.BINDING_MISMATCH)
    assert acquisition.requests == []


def test_restart_source_bound_and_verified_staged_paths(tmp_path: Path) -> None:
    service, acquisition, locators, adapter, candidate, content, _ = _foundation(tmp_path)
    restarted = VocalPayloadReconciliationService(
        acquisition,
        locators,
        PayloadStagingService(locators, adapter),
        adapter,
        max_payload_size_bytes=1024 * 1024,
    )
    authority = _authority(candidate.workspace_job_id)

    staged = restarted.reconcile(locators.record.locator_id, candidate, authority)
    assert staged.actual_payload_checksum == hashlib.sha256(content).hexdigest()
    acquisition.requests.clear()
    restarted_again = VocalPayloadReconciliationService(
        acquisition,
        locators,
        PayloadStagingService(locators, adapter),
        adapter,
        max_payload_size_bytes=1024 * 1024,
    )
    assert restarted_again.reconcile(staged.locator_id, candidate, authority) == staged
    assert acquisition.requests == []


def test_concurrent_same_locator_converges_to_one_verified_object(tmp_path: Path) -> None:
    service, acquisition, locators, _, candidate, _, root = _foundation(tmp_path)
    barrier = threading.Barrier(2)
    acquisition.callback = barrier.wait
    results = []

    def reconcile() -> None:
        results.append(
            service.reconcile(
                locators.record.locator_id,
                candidate,
                _authority(candidate.workspace_job_id),
            )
        )

    threads = [threading.Thread(target=reconcile) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 2
    assert all(result.staging_status is PayloadLocatorStatus.VERIFIED_STAGED for result in results)
    assert locators.record.lifecycle_revision == 1
    assert len(tuple(root.rglob("*.wav"))) == 1
    assert len(acquisition.requests) == 2


def test_service_source_has_no_retryjob_artifact_completion_or_worker_calls() -> None:
    source = Path("backend/services/workspace/vocal_payload_reconciliation_service.py").read_text(
        encoding="utf-8"
    )
    lowered = source.lower()
    assert "retry_job" not in lowered
    assert "artifactapplicationservice" not in lowered
    assert "completion" not in lowered
    assert "jobworkerservice" not in lowered


def test_composition_root_exposes_service_only_with_staging_configuration(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    for domain in ("lm", "audio", "vocal", "music"):
        (artifact_root / domain).mkdir(parents=True)
    staging_root = tmp_path / "payload-staging"
    staging_root.mkdir()
    app = create_app(
        Settings(
            database_url=f"sqlite:///{(tmp_path / 'app.db').as_posix()}",
            auto_migrate=True,
            cursor_signing_key="test-workspace-cursor-signing-key-32-bytes",
            storage_root=tmp_path / "storage",
            artifact_root=artifact_root,
            artifact_staging_root=staging_root,
            mock_generation_delay_seconds=0,
            log_level="WARNING",
        )
    )

    with TestClient(app):
        assert isinstance(
            app.state.vocal_payload_reconciliation_service,
            VocalPayloadReconciliationService,
        )
