"""Durable PayloadLocator domain, lifecycle, restart and security regression."""

from __future__ import annotations

import hashlib
import inspect as python_inspect
import io
import wave
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

import backend.models  # noqa: F401
from backend.core.payload_locator import (
    PayloadLocatorError,
    PayloadLocatorErrorCode,
    PayloadLocatorIssue,
    PayloadLocatorRevocationReason,
    PayloadLocatorStatus,
    VerifiedStagingFacts,
    parse_locator_id,
)
from backend.db.base import Base
from backend.db.session import create_database_engine, create_session_factory
from backend.models.workspace import (
    Artifact,
    Asset,
    AssetType,
    AssetVersion,
    Job,
    JobStatus,
    MusicProject,
    PayloadLocator,
    ProviderJobBinding,
    Workspace,
)
from backend.repositories.workspace import SqlAlchemyPayloadLocatorPersistence
from backend.repositories.workspace.payload_locator_repository import (
    PayloadLocatorRepository,
)
from backend.services.workspace import (
    PayloadLocatorService,
    PayloadStagingAuthority,
    PayloadStagingService,
    PayloadStagingServiceError,
    PayloadStagingServiceErrorCode,
)
from backend.storage import LocalFilesystemStagingAdapter

NOW = datetime(2026, 8, 25, 12, tzinfo=UTC)
CHECKSUM = "a" * 64


@pytest.fixture
def locator_graph(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'locator.db').as_posix()}"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(database_url)
    owner_id = uuid4()
    with factory.begin() as session:
        workspace = Workspace(
            owner_id=owner_id,
            name="Locator workspace",
            lifecycle_status="active",
        )
        session.add(workspace)
        session.flush()
        project = MusicProject(
            workspace_id=workspace.workspace_id,
            title="Locator project",
            description=None,
            lifecycle_status="active",
            created_by=owner_id,
        )
        session.add(project)
        session.flush()
        job = Job(
            project_id=project.project_id,
            workspace_id=workspace.workspace_id,
            job_type="voice_conversion",
            status=JobStatus.RUNNING,
            provider_id="dohavocal",
            api_contract_version="0.2.0",
            model_manifest_id="dynamic-vocal@2",
            settings_snapshot={},
            requested_by=owner_id,
            attempt=1,
        )
        session.add(job)
        session.flush()
        binding = ProviderJobBinding(
            workspace_job_id=job.job_id,
            provider_id="dohavocal",
            provider_job_id=f"provider-{uuid4().hex}",
        )
        session.add(binding)
        session.flush()
        asset = Asset(
            workspace_id=workspace.workspace_id,
            owner_id=owner_id,
            asset_type=AssetType.VOCAL,
            lifecycle_status="active",
        )
        session.add(asset)
        session.flush()
        version = AssetVersion(
            asset_id=asset.asset_id,
            version_number=1,
            version_origin="provider_generated",
            settings_snapshot={},
            created_by=owner_id,
        )
        session.add(version)
        session.flush()
        artifact = Artifact(
            asset_version_id=version.asset_version_id,
            artifact_kind="audio",
            media_type="audio/wav",
            size_bytes=10,
            checksum_algorithm="sha256",
            artifact_checksum=CHECKSUM,
            producer_type="provider",
            producer_id="dohavocal",
            retention_status="active",
        )
        session.add(artifact)
        session.flush()
        graph = {
            "database_url": database_url,
            "factory": factory,
            "engine": engine,
            "job_id": job.job_id,
            "binding_id": binding.provider_job_binding_id,
            "artifact_id": artifact.artifact_id,
        }
    yield graph
    engine.dispose()


def _service(graph, **kwargs) -> PayloadLocatorService:
    return PayloadLocatorService(
        SqlAlchemyPayloadLocatorPersistence(graph["factory"]),
        clock=lambda: NOW,
        **kwargs,
    )


def _issue(graph, **changes) -> PayloadLocatorIssue:
    values = {
        "workspace_job_id": graph["job_id"],
        "provider_job_binding_id": graph["binding_id"],
        "payload_ordinal": 0,
        "provider_artifact_id": "provider-artifact-1",
        "role": "converted_vocal_candidate",
        "source_kind": "provider_subresource",
        "source_id": "payload-1",
        "artifact_kind": "audio",
        "expected_checksum_algorithm": "sha256",
        "expected_payload_checksum": CHECKSUM,
        "expected_size_bytes": 10,
        "expected_media_type": "audio/wav",
        "source_available_until": NOW + timedelta(hours=1),
        "locator_expires_at": NOW + timedelta(days=1),
    }
    values.update(changes)
    return PayloadLocatorIssue(**values)


def _facts(**changes) -> VerifiedStagingFacts:
    values = {
        "staging_backend": "local_v1",
        "staging_key": "payloads/ab/candidate.wav",
        "actual_checksum_algorithm": "sha256",
        "actual_payload_checksum": CHECKSUM,
        "actual_size_bytes": 10,
        "actual_media_type": "audio/wav",
        "verified_at": NOW,
    }
    values.update(changes)
    return VerifiedStagingFacts(**values)


def _assert_code(error: pytest.ExceptionInfo[PayloadLocatorError], code) -> None:
    assert error.value.code is code


def _runtime_wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as payload:
        payload.setnchannels(1)
        payload.setsampwidth(2)
        payload.setframerate(8_000)
        payload.writeframes(b"\x00\x00" * 80)
    return output.getvalue()


def test_staging_runtime_revalidates_authority_and_commits_verified_cas(
    locator_graph, tmp_path
) -> None:
    content = _runtime_wav()
    locator_service = _service(locator_graph)
    issued = locator_service.issue(
        _issue(
            locator_graph,
            expected_payload_checksum=hashlib.sha256(content).hexdigest(),
            expected_size_bytes=len(content),
        )
    )
    staging_root = tmp_path / "verified-staging"
    staging_root.mkdir()
    staging = LocalFilesystemStagingAdapter(staging_root, clock=lambda: NOW)
    runtime = PayloadStagingService(locator_service, staging)
    calls = 0

    def authority() -> PayloadStagingAuthority:
        nonlocal calls
        calls += 1
        return PayloadStagingAuthority(locator_graph["job_id"], True, True, False)

    resolved = runtime.stage(issued.locator_id, [content[:31], content[31:]], authority)

    assert calls == 2
    assert resolved.staging_status is PayloadLocatorStatus.VERIFIED_STAGED
    assert resolved.lifecycle_revision == issued.lifecycle_revision + 1
    assert resolved.staging_key is not None
    assert (staging_root / resolved.staging_key).read_bytes() == content


def test_staging_runtime_cancellation_after_io_prevents_cas_and_cleans_orphan(
    locator_graph, tmp_path
) -> None:
    content = _runtime_wav()
    locator_service = _service(locator_graph)
    issued = locator_service.issue(
        _issue(
            locator_graph,
            expected_payload_checksum=hashlib.sha256(content).hexdigest(),
            expected_size_bytes=len(content),
        )
    )
    staging_root = tmp_path / "verified-staging"
    staging_root.mkdir()
    runtime = PayloadStagingService(
        locator_service,
        LocalFilesystemStagingAdapter(staging_root, clock=lambda: NOW),
    )
    calls = 0

    def authority() -> PayloadStagingAuthority:
        nonlocal calls
        calls += 1
        return PayloadStagingAuthority(
            locator_graph["job_id"], True, True, cancellation_requested=calls > 1
        )

    with pytest.raises(PayloadStagingServiceError) as cancelled:
        runtime.stage(issued.locator_id, [content], authority)

    assert cancelled.value.code is PayloadStagingServiceErrorCode.CANCELLATION_REQUESTED
    assert (
        locator_service.get(issued.locator_id).staging_status is PayloadLocatorStatus.SOURCE_BOUND
    )
    assert not tuple(staging_root.rglob("*.wav"))


def test_staging_runtime_revocation_after_io_prevents_cas_and_cleans_orphan(
    locator_graph, tmp_path
) -> None:
    content = _runtime_wav()
    locator_service = _service(locator_graph)
    issued = locator_service.issue(
        _issue(
            locator_graph,
            expected_payload_checksum=hashlib.sha256(content).hexdigest(),
            expected_size_bytes=len(content),
        )
    )
    staging_root = tmp_path / "verified-staging"
    staging_root.mkdir()
    runtime = PayloadStagingService(
        locator_service,
        LocalFilesystemStagingAdapter(staging_root, clock=lambda: NOW),
    )
    calls = 0

    def authority() -> PayloadStagingAuthority:
        nonlocal calls
        calls += 1
        if calls == 2:
            locator_service.revoke(
                issued.locator_id,
                expected_revision=issued.lifecycle_revision,
                reason=PayloadLocatorRevocationReason.RIGHTS_REVOKED,
                revoked_at=NOW,
            )
        return PayloadStagingAuthority(locator_graph["job_id"], True, True, False)

    with pytest.raises(PayloadLocatorError) as revoked:
        runtime.stage(issued.locator_id, [content], authority)

    assert revoked.value.code is PayloadLocatorErrorCode.REVOKED
    current = locator_service.get(issued.locator_id)
    assert current.revoked
    assert current.staging_status is PayloadLocatorStatus.SOURCE_BOUND
    assert not tuple(staging_root.rglob("*.wav"))


def test_issue_is_idempotent_and_survives_new_service_instance(locator_graph) -> None:
    first = _service(locator_graph).issue(_issue(locator_graph))
    restarted = PayloadLocatorService(
        SqlAlchemyPayloadLocatorPersistence(create_session_factory(locator_graph["database_url"])),
        clock=lambda: NOW,
    )
    replay = restarted.issue(_issue(locator_graph))
    resolved = restarted.get(first.locator_id)

    assert replay.locator_id == first.locator_id == resolved.locator_id
    assert parse_locator_id(first.locator_id) == first.locator_uuid
    assert first.locator_id.startswith("payloadref:v1:")
    with locator_graph["factory"]() as session:
        assert session.scalar(select(func.count()).select_from(PayloadLocator)) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"source_id": "payload-2"},
        {"expected_payload_checksum": "b" * 64},
        {"role": "generated_vocal_candidate"},
        {"provider_artifact_id": "provider-artifact-2"},
    ],
)
def test_same_binding_ordinal_with_changed_fact_conflicts(locator_graph, changes) -> None:
    service = _service(locator_graph)
    service.issue(_issue(locator_graph))
    with pytest.raises(PayloadLocatorError) as caught:
        service.issue(_issue(locator_graph, **changes))
    _assert_code(caught, PayloadLocatorErrorCode.RESULT_REPLAY_CONFLICT)


def test_logical_source_identity_and_ordinal_are_separate_unique_keys(
    locator_graph,
) -> None:
    service = _service(locator_graph)
    service.issue(_issue(locator_graph))
    with pytest.raises(PayloadLocatorError) as caught:
        service.issue(_issue(locator_graph, payload_ordinal=1))
    _assert_code(caught, PayloadLocatorErrorCode.RESULT_REPLAY_CONFLICT)


def test_invalid_workspace_binding_association_fails_closed(locator_graph) -> None:
    with pytest.raises(PayloadLocatorError) as caught:
        _service(locator_graph).issue(_issue(locator_graph, workspace_job_id=uuid4()))
    _assert_code(caught, PayloadLocatorErrorCode.WORKSPACE_BINDING_MISMATCH)

    with locator_graph["factory"].begin() as session:
        row = PayloadLocator(payload_locator_id=uuid4(), **asdict(_issue(locator_graph)))
        row.workspace_job_id = uuid4()
        session.add(row)
        with pytest.raises(IntegrityError):
            session.flush()


def test_full_lifecycle_persists_and_cas_rejects_stale_revision(locator_graph) -> None:
    service = _service(locator_graph)
    issued = service.issue(_issue(locator_graph))
    staged = service.transition_to_verified_staged(
        issued.locator_id, expected_revision=0, facts=_facts()
    )
    assert staged.staging_status is PayloadLocatorStatus.VERIFIED_STAGED
    assert staged.actual_payload_checksum == staged.issue.expected_payload_checksum
    assert staged.lifecycle_revision == 1

    with pytest.raises(PayloadLocatorError) as stale:
        service.transition_to_verified_staged(
            issued.locator_id, expected_revision=0, facts=_facts()
        )
    _assert_code(stale, PayloadLocatorErrorCode.REVISION_CONFLICT)

    ingested = service.mark_ingested(
        issued.locator_id,
        expected_revision=1,
        ingested_artifact_id=locator_graph["artifact_id"],
        ingested_at=NOW + timedelta(seconds=1),
    )
    pending = service.mark_cleanup_pending(
        issued.locator_id,
        expected_revision=2,
        requested_at=NOW + timedelta(seconds=2),
    )
    cleaned = service.mark_cleaned(
        issued.locator_id,
        expected_revision=3,
        completed_at=NOW + timedelta(seconds=3),
    )
    assert [
        ingested.staging_status,
        pending.staging_status,
        cleaned.staging_status,
    ] == [
        PayloadLocatorStatus.INGESTED,
        PayloadLocatorStatus.CLEANUP_PENDING,
        PayloadLocatorStatus.CLEANED,
    ]
    assert service.get(issued.locator_id).lifecycle_revision == 4


def test_integrity_mismatch_and_illegal_backward_transitions_are_rejected(
    locator_graph,
) -> None:
    service = _service(locator_graph)
    issued = service.issue(_issue(locator_graph))
    with pytest.raises(PayloadLocatorError) as mismatch:
        service.transition_to_verified_staged(
            issued.locator_id,
            expected_revision=0,
            facts=_facts(actual_size_bytes=11),
        )
    _assert_code(mismatch, PayloadLocatorErrorCode.INTEGRITY_MISMATCH)
    with pytest.raises(PayloadLocatorError) as direct_ingest:
        service.mark_ingested(
            issued.locator_id,
            expected_revision=0,
            ingested_artifact_id=locator_graph["artifact_id"],
            ingested_at=NOW,
        )
    _assert_code(direct_ingest, PayloadLocatorErrorCode.ILLEGAL_TRANSITION)

    staged = service.transition_to_verified_staged(
        issued.locator_id, expected_revision=0, facts=_facts()
    )
    ingested = service.mark_ingested(
        issued.locator_id,
        expected_revision=staged.lifecycle_revision,
        ingested_artifact_id=locator_graph["artifact_id"],
        ingested_at=NOW,
    )
    with pytest.raises(PayloadLocatorError) as resurrection:
        service.transition_to_verified_staged(
            issued.locator_id,
            expected_revision=ingested.lifecycle_revision,
            facts=_facts(),
        )
    _assert_code(resurrection, PayloadLocatorErrorCode.ILLEGAL_TRANSITION)


def test_two_workers_racing_same_revision_produce_one_transition(locator_graph) -> None:
    issued = _service(locator_graph).issue(_issue(locator_graph))

    def transition():
        return _service(locator_graph).transition_to_verified_staged(
            issued.locator_id, expected_revision=0, facts=_facts()
        )

    outcomes = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(transition) for _ in range(2)]
        for future in futures:
            try:
                outcomes.append(future.result())
            except PayloadLocatorError as error:
                outcomes.append(error)

    records = [item for item in outcomes if not isinstance(item, Exception)]
    errors = [item for item in outcomes if isinstance(item, PayloadLocatorError)]
    assert len(records) == 1
    assert len(errors) == 1
    assert errors[0].code is PayloadLocatorErrorCode.REVISION_CONFLICT
    assert _service(locator_graph).get(issued.locator_id).lifecycle_revision == 1


@pytest.mark.parametrize("reason", list(PayloadLocatorRevocationReason))
def test_revocation_is_terminal_and_blocks_acquire_stage_and_ingest(locator_graph, reason) -> None:
    service = _service(locator_graph)
    issue = _issue(
        locator_graph,
        payload_ordinal=list(PayloadLocatorRevocationReason).index(reason),
        provider_artifact_id=f"artifact-{reason.value}",
        role=(
            "generated_vocal_candidate"
            if reason is not PayloadLocatorRevocationReason.WORKSPACE_CANCELLED
            else "converted_vocal_candidate"
        ),
        source_id=f"source-{reason.value}",
    )
    issued = service.issue(issue)
    revoked = service.revoke(
        issued.locator_id,
        expected_revision=0,
        reason=reason,
        revoked_at=NOW,
    )
    assert revoked.revoked and revoked.lifecycle_revision == 1
    assert (
        service.revoke(
            issued.locator_id,
            expected_revision=0,
            reason=reason,
            revoked_at=NOW,
        ).lifecycle_revision
        == 1
    )
    with pytest.raises(PayloadLocatorError) as resolve_error:
        service.resolve_for_acquisition(
            issued.locator_id,
            workspace_job_id=locator_graph["job_id"],
            rights_granted=True,
        )
    _assert_code(resolve_error, PayloadLocatorErrorCode.REVOKED)
    with pytest.raises(PayloadLocatorError) as stage_error:
        service.transition_to_verified_staged(
            issued.locator_id, expected_revision=1, facts=_facts()
        )
    _assert_code(stage_error, PayloadLocatorErrorCode.REVOKED)


def test_source_expiry_is_distinct_from_verified_staging_and_rights(
    locator_graph,
) -> None:
    service = _service(locator_graph)
    issued = service.issue(_issue(locator_graph, source_available_until=NOW - timedelta(seconds=1)))
    with pytest.raises(PayloadLocatorError) as expired:
        service.resolve_for_acquisition(
            issued.locator_id,
            workspace_job_id=locator_graph["job_id"],
            rights_granted=True,
        )
    _assert_code(expired, PayloadLocatorErrorCode.SOURCE_EXPIRED)

    staged = service.transition_to_verified_staged(
        issued.locator_id, expected_revision=0, facts=_facts()
    )
    assert (
        service.resolve_verified_staging(
            staged.locator_id,
            workspace_job_id=locator_graph["job_id"],
            rights_granted=True,
        ).locator_id
        == staged.locator_id
    )
    with pytest.raises(PayloadLocatorError) as rights:
        service.resolve_verified_staging(
            staged.locator_id,
            workspace_job_id=locator_graph["job_id"],
            rights_granted=False,
        )
    _assert_code(rights, PayloadLocatorErrorCode.RIGHTS_REQUIRED)


def test_revoked_verified_staging_can_only_advance_to_cleanup(locator_graph) -> None:
    service = _service(locator_graph)
    issued = service.issue(_issue(locator_graph))
    staged = service.transition_to_verified_staged(
        issued.locator_id, expected_revision=0, facts=_facts()
    )
    revoked = service.revoke(
        staged.locator_id,
        expected_revision=1,
        reason=PayloadLocatorRevocationReason.RIGHTS_REVOKED,
        revoked_at=NOW,
    )
    pending = service.mark_cleanup_pending(
        revoked.locator_id,
        expected_revision=2,
        requested_at=NOW + timedelta(seconds=1),
    )
    cleaned = service.mark_cleaned(
        pending.locator_id,
        expected_revision=3,
        completed_at=NOW + timedelta(seconds=2),
    )

    assert pending.ingested_artifact_id is None
    assert cleaned.staging_status is PayloadLocatorStatus.CLEANED
    with pytest.raises(PayloadLocatorError) as resurrection:
        service.transition_to_verified_staged(
            cleaned.locator_id,
            expected_revision=4,
            facts=_facts(),
        )
    _assert_code(resurrection, PayloadLocatorErrorCode.ILLEGAL_TRANSITION)


def test_locator_policy_expiry_blocks_ingestion(locator_graph) -> None:
    service = _service(locator_graph)
    issued = service.issue(_issue(locator_graph, locator_expires_at=NOW + timedelta(seconds=1)))
    staged = service.transition_to_verified_staged(
        issued.locator_id, expected_revision=0, facts=_facts()
    )
    expired_service = PayloadLocatorService(
        SqlAlchemyPayloadLocatorPersistence(locator_graph["factory"]),
        clock=lambda: NOW + timedelta(seconds=2),
    )
    with pytest.raises(PayloadLocatorError) as expired:
        expired_service.mark_ingested(
            staged.locator_id,
            expected_revision=1,
            ingested_artifact_id=locator_graph["artifact_id"],
            ingested_at=NOW + timedelta(seconds=2),
        )
    _assert_code(expired, PayloadLocatorErrorCode.LOCATOR_EXPIRED)


@pytest.mark.parametrize(
    "unsafe",
    [
        "/var/tmp/payload.wav",
        "../payload.wav",
        "safe/../payload.wav",
        r"C:\payload.wav",
        r"\\server\share\payload.wav",
        "https://provider/payload.wav",
        "payloads/api_token.wav",
    ],
)
def test_staging_key_security_rejects_paths_urls_and_credentials(unsafe) -> None:
    with pytest.raises(PayloadLocatorError) as caught:
        _facts(staging_key=unsafe)
    _assert_code(caught, PayloadLocatorErrorCode.INVALID_STAGING_KEY)


@pytest.mark.parametrize(
    "malformed",
    [
        "payloadref:v1:ABC",
        "payloadref:v2:" + "0" * 32,
        "payloadref:v1:" + "A" * 32,
        "../payloadref:v1:" + "0" * 32,
    ],
)
def test_malformed_locator_id_rejected(malformed) -> None:
    with pytest.raises(PayloadLocatorError) as caught:
        parse_locator_id(malformed)
    _assert_code(caught, PayloadLocatorErrorCode.MALFORMED_LOCATOR_ID)


def test_locator_table_contains_no_bytes_credentials_or_absolute_root(
    locator_graph,
) -> None:
    record = _service(locator_graph).issue(_issue(locator_graph))
    with locator_graph["factory"]() as session:
        row = (
            session.execute(
                text("SELECT * FROM payload_locators WHERE payload_locator_id = :id"),
                {"id": record.locator_uuid.hex},
            )
            .mappings()
            .one()
        )
    columns = set(row)
    assert not columns.intersection(
        {"payload_bytes", "authorization", "credential", "signed_url", "storage_root"}
    )
    assert all("C:\\" not in str(value) and "https://" not in str(value) for value in row.values())


def test_repository_is_flush_only_and_port_hides_sqlalchemy() -> None:
    source = python_inspect.getsource(PayloadLocatorRepository)
    assert ".commit(" not in source
    assert ".rollback(" not in source
    service_source = python_inspect.getsource(PayloadLocatorService)
    assert "sqlalchemy" not in service_source.lower()


def test_random_id_collision_retries_are_bounded(locator_graph) -> None:
    fixed = uuid4()
    first = _service(locator_graph, id_factory=lambda: fixed).issue(_issue(locator_graph))
    assert first.locator_uuid == fixed
    second_issue = replace(
        _issue(locator_graph),
        payload_ordinal=1,
        provider_artifact_id="provider-artifact-2",
        source_id="payload-2",
        role="generated_vocal_candidate",
    )
    with pytest.raises(PayloadLocatorError) as caught:
        _service(locator_graph, id_factory=lambda: fixed).issue(second_issue)
    _assert_code(caught, PayloadLocatorErrorCode.LOCATOR_ID_COLLISION)
