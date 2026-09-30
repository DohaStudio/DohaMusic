"""Real pinned Provider app -> Music trust -> durable staging -> Completion."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

import httpx
import pytest
from sqlalchemy import func, select

from backend.core.payload_locator import PayloadLocatorRevocationReason, PayloadLocatorStatus
from backend.models.workspace import Artifact, Asset, Job, JobOutput, JobStatus, ModelUsage
from backend.providers.vocal import (
    HttpVocalProviderTransport,
    VocalPayloadAcquisitionRequest,
)
from backend.providers.vocal.errors import (
    VocalProviderApplicationError,
    VocalProviderContractVersionError,
)
from backend.services.workspace import (
    DohaVocalArtifactCompletionError,
    PayloadStagingService,
    ProviderResultContractError,
    VocalPayloadReconciliationError,
    VocalPayloadReconciliationService,
    staged_payload_from_record,
)
from backend.tests.support.vocal_e2e import graph

pytest_plugins = ["backend.tests.support.vocal_runtime"]

CAPABILITIES = ("vocal_generation", "voice_conversion", "vocal_correction", "vocal_analysis")


def _unchanged(g):
    with g.factory() as session:
        assert session.get(Job, g.job.job_id).status is JobStatus.RUNNING
        assert session.scalar(select(func.count()).select_from(JobOutput)) == 0
        assert session.scalar(select(func.count()).select_from(ModelUsage)) == 0
        assert session.scalar(select(func.count()).select_from(Artifact)) == 1


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_real_runtime_through_completion_and_exact_replay(tmp_path, vocal_runtime, capability):
    g = graph(tmp_path, vocal_runtime, capability)
    try:
        assert g.client.get_capabilities().api_contract_version == "0.1.0"
        caps = g.client.get_capabilities(api_contract_version="0.2.0")
        assert caps.payload_acquisition.operation == "GetPayloadContent"
        acquisition_request = VocalPayloadAcquisitionRequest(
            g.provider_job.job_id, g.wire.payloads[0], 1024 * 1024
        )
        assert g.transport.acquire_payload(acquisition_request) == g.transport.acquire_payload(
            acquisition_request
        )
        assert g.client.get_job_status(g.provider_job.job_id) == g.provider_job
        assert g.client.create_job(g.request).job_id == g.provider_job.job_id
        wire_again = g.client.get_result(g.provider_job.job_id, api_contract_version="0.2.0")
        assert wire_again == g.wire
        assert g.locators.issue(g.issue) == g.record
        assert not g.request.model_dump().get("workspace_id")
        staged = g.reconciliation.reconcile(g.record.locator_id, g.candidate, g.authority)
        assert staged.staging_status is PayloadLocatorStatus.VERIFIED_STAGED
        with g.staging.open_verified(staged_payload_from_record(staged)) as stream:
            content = stream.read()
        assert sha256(content).hexdigest() == g.payload.payload_checksum
        assert len(content) == g.payload.expected_size_bytes
        assert staged.actual_media_type == g.payload.expected_media_type
        assert g.client.get_job_status(g.provider_job.job_id) == g.provider_job
        assert g.reconciliation.reconcile(staged.locator_id, g.candidate, g.authority) == staged
        _unchanged(g)
        result = g.completion.complete(g.completion_request)
        replay = g.completion.complete(g.completion_request)
        assert replay.replayed and replay.artifact_id == result.artifact_id
        with g.factory() as session:
            assert session.get(Job, g.job.job_id).status is JobStatus.SUCCEEDED
            assert session.scalar(select(func.count()).select_from(JobOutput)) == 1
            assert session.scalar(select(func.count()).select_from(ModelUsage)) == 1
            artifact = session.get(Artifact, result.artifact_id)
            assert artifact.artifact_checksum == sha256(content).hexdigest()
            assert artifact.size_bytes == len(content)
            assert (
                session.get(Asset, g.asset.asset_id).selected_asset_version_id
                == g.source.asset_version_id
            )
        assert g.locators.get(staged.locator_id).staging_status is PayloadLocatorStatus.INGESTED
        assert g.manifest.license_status == "REVIEW_REQUIRED"
    finally:
        g.transport.close()
        g.engine.dispose()


def test_default_010_and_explicit_version_manifest_idempotency_retry(tmp_path, vocal_runtime):
    g = graph(tmp_path, vocal_runtime, "voice_conversion")
    try:
        old = g.request.model_copy(
            update={
                "api_contract_version": "0.1.0",
                "model_manifest_id": "dohavocal.fake-model@0.1.0",
                "idempotency_key": "old-contract",
            }
        )
        old_job = g.client.create_job(old)
        assert not g.client.get_result(old_job.job_id).payload_present
        with pytest.raises(VocalProviderContractVersionError):
            g.client.get_capabilities(api_contract_version="9.9.9")
        with pytest.raises(VocalProviderContractVersionError):
            g.client.create_job(
                g.request.model_copy(update={"model_manifest_id": old.model_manifest_id})
            )
        with pytest.raises(VocalProviderApplicationError):
            g.client.create_job(
                g.request.model_copy(update={"settings_snapshot": {"changed": True}})
            )
        failed = g.client.create_job(
            g.request.model_copy(
                update={
                    "idempotency_key": "failed",
                    "settings_snapshot": {"fake_outcome": "failed"},
                }
            )
        )
        retry = g.client.retry_job(failed.job_id)
        assert retry.job_id != failed.job_id and retry.retry_of_job_id == failed.job_id
        running = g.client.create_job(
            g.request.model_copy(
                update={
                    "idempotency_key": "cancel",
                    "settings_snapshot": {"fake_outcome": "running"},
                }
            )
        )
        assert g.client.cancel_job(running.job_id).status.value == "cancelled"
        _unchanged(g)
    finally:
        g.engine.dispose()


@pytest.mark.parametrize("mutation", ["job", "manifest", "source", "checksum", "role"])
def test_real_result_binding_mutations_fail_closed(tmp_path, vocal_runtime, mutation):
    g = graph(tmp_path, vocal_runtime, "voice_conversion")
    try:
        wire = g.wire
        if mutation == "job":
            wire = wire.model_copy(update={"run_id": "wrong-job"})
        elif mutation == "manifest":
            wire = wire.model_copy(
                update={
                    "lineage": wire.lineage.model_copy(
                        update={"model_manifest_id": "wrong-manifest"}
                    )
                }
            )
        elif mutation == "source":
            wire = wire.model_copy(
                update={
                    "lineage": wire.lineage.model_copy(
                        update={"source_asset_version_id": str(g.owner)}
                    )
                }
            )
        elif mutation == "checksum":
            wire = wire.model_copy(update={"artifact_checksum": "0" * 64})
        else:
            wire = wire.model_copy(
                update={
                    "payloads": (
                        wire.payloads[0].model_copy(update={"role": "generated_vocal_candidate"}),
                    )
                }
            )
        with g.factory.begin() as session, pytest.raises(ProviderResultContractError):
            g.trust.validate_candidate_for_owner(
                session,
                effective_owner_id=g.owner,
                workspace_job_id=g.job.job_id,
                provider_job_binding_id=g.binding.provider_job_binding_id,
                output_role=g.candidate.output_role,
                wire_candidate=wire,
            )
        _unchanged(g)
    finally:
        g.engine.dispose()


@pytest.mark.parametrize(
    "mutation", ["checksum", "size", "media", "encoding", "redirect", "interrupt"]
)
def test_actual_payload_failure_no_partial_state_and_retry(tmp_path, vocal_runtime, mutation):
    g = graph(tmp_path, vocal_runtime, "voice_conversion")
    calls = []

    def handler(request):
        calls.append(request)
        response = vocal_runtime.get(request.url.path, headers={"Accept-Encoding": "identity"})
        headers = dict(response.headers)
        content = response.content
        if mutation == "checksum":
            content = content[:-1] + b"x"
        elif mutation == "size":
            content = content[:-1]
            headers.pop("content-length", None)
        elif mutation == "media":
            headers["content-type"] = "application/json"
        elif mutation == "encoding":
            headers["content-encoding"] = "unsupported"
        elif mutation == "redirect":
            return httpx.Response(302, headers={"location": "https://forbidden.invalid"})
        else:
            raise httpx.ReadError("interrupted", request=request)
        return httpx.Response(200, headers=headers, content=content)

    try:
        with httpx.Client(transport=httpx.MockTransport(handler)) as damaged:
            transport = HttpVocalProviderTransport(base_url="http://vocal.fixture", client=damaged)
            service = VocalPayloadReconciliationService(
                transport,
                g.locators,
                PayloadStagingService(g.locators, g.staging),
                g.staging,
                max_payload_size_bytes=1024 * 1024,
            )
            with pytest.raises(VocalPayloadReconciliationError):
                service.reconcile(g.record.locator_id, g.candidate, g.authority)
        assert len(calls) == 1
        assert (
            g.locators.get(g.record.locator_id).staging_status is PayloadLocatorStatus.SOURCE_BOUND
        )
        assert not list(g.staging_root.rglob("*.wav"))
        _unchanged(g)
        assert (
            g.reconciliation.reconcile(g.record.locator_id, g.candidate, g.authority).staging_status
            is PayloadLocatorStatus.VERIFIED_STAGED
        )
    finally:
        g.engine.dispose()


@pytest.mark.parametrize("dimension", ["job", "artifact", "source", "range"])
def test_provider_exact_payload_binding_and_range(tmp_path, vocal_runtime, dimension):
    g = graph(tmp_path, vocal_runtime, "voice_conversion")
    try:
        job = g.provider_job.job_id
        artifact = g.payload.provider_artifact_id
        source = g.payload.source_id
        if dimension == "job":
            job = "wrong-job"
        elif dimension == "artifact":
            artifact = "wrong-artifact"
        elif dimension == "source":
            source = "wrong-source"
        response = vocal_runtime.get(
            f"/v1/jobs/{job}/artifacts/{artifact}/payloads/{source}",
            headers={"Range": "bytes=0-1"} if dimension == "range" else {},
        )
        assert response.status_code in {400, 404, 416}
        assert g.client.get_job_status(g.provider_job.job_id) == g.provider_job
        _unchanged(g)
    finally:
        g.engine.dispose()


@pytest.mark.parametrize("when", ["before", "during", "rights", "revoked"])
def test_acquisition_cancel_rights_revocation_no_partial_state(tmp_path, vocal_runtime, when):
    g = graph(tmp_path, vocal_runtime, "voice_conversion")
    calls = 0

    def current():
        nonlocal calls
        calls += 1
        if when == "before" or (when == "during" and calls >= 3):
            g.state["cancelled"] = True
        if when == "rights":
            g.rights.allowed = False
        return g.authority()

    try:
        if when == "revoked":
            g.locators.revoke(
                g.record.locator_id,
                reason=PayloadLocatorRevocationReason.RIGHTS_REVOKED,
                expected_revision=g.record.lifecycle_revision,
                revoked_at=datetime.now(UTC),
            )
        with pytest.raises(VocalPayloadReconciliationError):
            g.reconciliation.reconcile(g.record.locator_id, g.candidate, current)
        assert (
            g.locators.get(g.record.locator_id).staging_status is PayloadLocatorStatus.SOURCE_BOUND
        )
        assert not list(g.staging_root.rglob("*.wav"))
        _unchanged(g)
    finally:
        g.engine.dispose()


def test_completion_current_rights_denial_keeps_verified_staged(tmp_path, vocal_runtime):
    g = graph(tmp_path, vocal_runtime, "vocal_analysis")
    try:
        g.reconciliation.reconcile(g.record.locator_id, g.candidate, g.authority)
        g.rights.allowed = False
        with pytest.raises(DohaVocalArtifactCompletionError):
            g.completion.complete(g.completion_request)
        assert (
            g.locators.get(g.record.locator_id).staging_status
            is PayloadLocatorStatus.VERIFIED_STAGED
        )
        _unchanged(g)
    finally:
        g.engine.dispose()


def test_actual_runtime_completion_transaction_failure_rolls_back(
    tmp_path, vocal_runtime, monkeypatch
):
    from backend.repositories.workspace import JobRepository

    g = graph(tmp_path, vocal_runtime, "voice_conversion")
    try:
        g.reconciliation.reconcile(g.record.locator_id, g.candidate, g.authority)
        with monkeypatch.context() as patch:
            # Fail the final CAS after Artifact/JobOutput/ModelUsage registration.
            patch.setattr(JobRepository, "finish_owned_claim", lambda *args, **kwargs: None)
            with pytest.raises(DohaVocalArtifactCompletionError):
                g.completion.complete(g.completion_request)
        _unchanged(g)
        assert (
            g.locators.get(g.record.locator_id).staging_status
            is PayloadLocatorStatus.VERIFIED_STAGED
        )
        assert g.completion.complete(g.completion_request).replayed is False
    finally:
        g.engine.dispose()
