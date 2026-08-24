"""실제 network 없이 검증하는 DohaVocal Runtime 0.1.0 consumer 계약."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.providers.vocal import (
    AuthorizedVocalJobContext,
    VocalAnalysisInput,
    VocalAnalysisType,
    VocalCapability,
    VocalCorrectionInput,
    VocalCorrectionType,
    VocalGenerationInput,
    VocalJobStatus,
    VocalProviderApplicationError,
    VocalProviderClient,
    VocalProviderContractVersionError,
    VocalProviderInvalidResponseError,
    VocalProviderTimeoutError,
    VocalProviderTransportError,
    VocalTransportRequest,
    VocalTransportResponse,
    VoiceConversionInput,
    map_authorized_create_job,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "vocal-provider-contract-v0.1.0.json"
OWNER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
WORKSPACE_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
PROJECT_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
SOURCE_VERSION_ID = UUID("11111111-1111-4111-8111-111111111111")
REFERENCE_ARTIFACT_ID = UUID("22222222-2222-4222-8222-222222222222")
FAKE_MODEL_MANIFEST_ID = "dohavocal.fake-model@0.1.0"


@pytest.fixture(scope="module")
def vocal_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class FixtureTransport:
    def __init__(self, fixture: dict[str, Any]) -> None:
        self.fixture = fixture
        self.requests: list[VocalTransportRequest] = []
        self.status_fixture = "running_job"

    def send(self, request: VocalTransportRequest) -> VocalTransportResponse:
        self.requests.append(deepcopy(request))
        routes = {
            ("GET", "/health"): (200, "health"),
            ("GET", "/ready"): (200, "readiness"),
            ("GET", "/v1/capabilities"): (200, "capabilities"),
            ("POST", "/v1/jobs"): (201, "queued_job"),
            ("GET", "/v1/jobs/provider-job-001"): (200, self.status_fixture),
            ("POST", "/v1/jobs/provider-job-001/cancel"): (
                200,
                "cancelled_job",
            ),
            ("POST", "/v1/jobs/provider-job-001/retry"): (200, "retry_job"),
            ("GET", "/v1/jobs/provider-job-001/result"): (200, "result"),
            ("GET", f"/v1/model-manifests/{FAKE_MODEL_MANIFEST_ID}"): (
                200,
                "manifest",
            ),
        }
        status, fixture_name = routes[(request.method, request.path)]
        return VocalTransportResponse(status, deepcopy(self.fixture[fixture_name]))


class IdempotentFixtureTransport:
    def __init__(self, fixture: dict[str, Any]) -> None:
        self.fixture = fixture
        self.records: dict[tuple[str, str, str, str, str], tuple[str, dict[str, Any]]] = {}

    def send(self, request: VocalTransportRequest) -> VocalTransportResponse:
        assert request.method == "POST" and request.path == "/v1/jobs"
        body = deepcopy(dict(request.json_body or {}))
        scope = (
            body["provider_id"],
            body["capability"],
            body["project_id"],
            body["requested_by"],
            body["idempotency_key"],
        )
        fingerprint_body = dict(body)
        fingerprint_body.pop("idempotency_key")
        fingerprint = hashlib.sha256(
            json.dumps(
                fingerprint_body,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        existing = self.records.get(scope)
        if existing is not None:
            if existing[0] != fingerprint:
                return VocalTransportResponse(409, deepcopy(self.fixture["application_error"]))
            return VocalTransportResponse(201, deepcopy(existing[1]))
        response = deepcopy(self.fixture["queued_job"])
        response.update(
            {
                "job_id": f"provider-job-{len(self.records) + 10}",
                "job_type": body["capability"],
                "input_asset_version_ids": body["input_asset_version_ids"],
                "input_artifact_ids": body["input_artifact_ids"],
                "composition_snapshot_id": body["composition_snapshot_id"],
                "settings_snapshot": body["settings_snapshot"],
                "model_manifest_id": body["model_manifest_id"],
            }
        )
        self.records[scope] = (fingerprint, response)
        return VocalTransportResponse(201, deepcopy(response))


def _context(
    *,
    capability: VocalCapability = VocalCapability.VOICE_CONVERSION,
    project_id: UUID = PROJECT_ID,
    owner_id: UUID = OWNER_ID,
    idempotency_key: str = "vocal-contract-key",
    settings: dict[str, Any] | None = None,
) -> AuthorizedVocalJobContext:
    job_inputs = {
        VocalCapability.VOCAL_GENERATION: VocalGenerationInput(
            job_type="vocal_generation",
            lyrics_reference="artifact://lyrics-1",
            melody_reference="artifact://melody-1",
        ),
        VocalCapability.VOICE_CONVERSION: VoiceConversionInput(
            job_type="voice_conversion",
            source_asset_version_id=str(SOURCE_VERSION_ID),
            parent_asset_version_id=str(SOURCE_VERSION_ID),
            voice_reference_artifact_id=str(REFERENCE_ARTIFACT_ID),
            source_entity_type="recording_take",
            reference_entity_type="voice_enrollment_sample",
        ),
        VocalCapability.VOCAL_CORRECTION: VocalCorrectionInput(
            job_type="vocal_correction",
            source_asset_version_id=str(SOURCE_VERSION_ID),
            correction_types=(VocalCorrectionType.PITCH,),
        ),
        VocalCapability.VOCAL_ANALYSIS: VocalAnalysisInput(
            job_type="vocal_analysis",
            source_asset_version_id=str(SOURCE_VERSION_ID),
            analysis_types=(VocalAnalysisType.AUDIO_QUALITY,),
        ),
    }
    return AuthorizedVocalJobContext(
        effective_owner_id=owner_id,
        workspace_id=WORKSPACE_ID,
        project_id=project_id,
        capability=capability,
        idempotency_key=idempotency_key,
        input_asset_version_ids=(SOURCE_VERSION_ID,),
        input_artifact_ids=(REFERENCE_ARTIFACT_ID,),
        model_manifest_id=FAKE_MODEL_MANIFEST_ID,
        settings_snapshot=settings or {"quality": {"mode": "contract"}},
        job_input=job_inputs[capability],
    )


def test_capabilities_decode_four_vocal_types_and_nine_operations(vocal_fixture):
    client = VocalProviderClient(FixtureTransport(vocal_fixture))

    capabilities = client.get_capabilities()

    assert set(capabilities.capabilities) == set(VocalCapability)
    assert len(capabilities.supported_operations) == 9
    assert capabilities.api_contract_version == "0.1.0"


def test_unknown_capability_is_rejected_as_invalid_response(vocal_fixture):
    fixture = deepcopy(vocal_fixture)
    fixture["capabilities"]["capabilities"].append("unknown_vocal")

    with pytest.raises(VocalProviderInvalidResponseError):
        VocalProviderClient(FixtureTransport(fixture)).get_capabilities()


@pytest.mark.parametrize("capability", list(VocalCapability))
def test_authorized_create_mapping_supports_each_vocal_capability(capability):
    request = map_authorized_create_job(_context(capability=capability))

    assert request.capability is capability
    assert request.job_input.job_type is capability
    assert request.requested_by == str(OWNER_ID)
    assert request.project_id == str(PROJECT_ID)
    assert request.input_asset_version_ids == (str(SOURCE_VERSION_ID),)
    assert request.input_artifact_ids == (str(REFERENCE_ARTIFACT_ID),)


def test_create_job_maps_body_and_preserves_effective_scope(vocal_fixture):
    transport = FixtureTransport(vocal_fixture)
    request = map_authorized_create_job(_context())

    job = VocalProviderClient(transport).create_job(request)

    sent = transport.requests[-1]
    assert sent.method == "POST"
    assert sent.path == "/v1/jobs"
    assert sent.json_body is not None
    assert sent.json_body["requested_by"] == str(OWNER_ID)
    assert sent.json_body["project_id"] == str(PROJECT_ID)
    assert sent.json_body["idempotency_key"] == "vocal-contract-key"
    assert "workspace_id" not in sent.json_body
    assert job.status is VocalJobStatus.QUEUED


def test_settings_snapshot_detaches_nested_caller_state():
    mutable = {"quality": {"bands": [1, 2]}}
    request = map_authorized_create_job(_context(settings=mutable))

    mutable["quality"]["bands"].append(3)

    assert request.settings_snapshot == {"quality": {"bands": [1, 2]}}


@pytest.mark.parametrize(
    "settings",
    [
        {"path": "artifact://safe-logical-id"},
        {"nested": {"model_path": "model"}},
        {"value": "C:\\private\\voice.wav"},
        {"value": "../voice.wav"},
        {"value": "file://private/voice.wav"},
    ],
)
def test_sensitive_or_path_values_are_rejected(settings):
    with pytest.raises(ValidationError):
        map_authorized_create_job(_context(settings=settings))


def test_logical_artifact_uri_is_not_misclassified_as_local_path():
    request = map_authorized_create_job(
        _context(settings={"reference": "artifact://safe-logical-id"})
    )

    assert request.settings_snapshot["reference"] == "artifact://safe-logical-id"


def test_idempotency_replay_conflict_and_scope_separation(vocal_fixture):
    client = VocalProviderClient(IdempotentFixtureTransport(vocal_fixture))
    base = map_authorized_create_job(_context())

    first = client.create_job(base)
    replay = client.create_job(base)
    assert replay.job_id == first.job_id

    changed = map_authorized_create_job(_context(settings={"quality": {"mode": "changed"}}))
    with pytest.raises(VocalProviderApplicationError) as conflict:
        client.create_job(changed)
    assert conflict.value.detail.error_code == "IDEMPOTENCY_CONFLICT"

    other_project = client.create_job(
        map_authorized_create_job(_context(project_id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")))
    )
    other_capability = client.create_job(
        map_authorized_create_job(_context(capability=VocalCapability.VOCAL_CORRECTION))
    )
    other_requester = client.create_job(
        map_authorized_create_job(_context(owner_id=UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")))
    )
    assert (
        len(
            {
                first.job_id,
                other_project.job_id,
                other_capability.job_id,
                other_requester.job_id,
            }
        )
        == 4
    )


@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    [
        ("queued_job", VocalJobStatus.QUEUED),
        ("running_job", VocalJobStatus.RUNNING),
        ("succeeded_job", VocalJobStatus.SUCCEEDED),
        ("failed_job", VocalJobStatus.FAILED),
        ("cancelled_job", VocalJobStatus.CANCELLED),
    ],
)
def test_job_lifecycle_states_are_preserved(vocal_fixture, fixture_name, expected):
    transport = FixtureTransport(vocal_fixture)
    transport.status_fixture = fixture_name

    job = VocalProviderClient(transport).get_job_status("provider-job-001")

    assert job.status is expected
    if expected is VocalJobStatus.FAILED:
        assert job.error is not None
        assert job.error.retryable is True


def test_cancel_and_retry_preserve_terminal_and_parent_relationship(vocal_fixture):
    client = VocalProviderClient(FixtureTransport(vocal_fixture))

    cancelled = client.cancel_job("provider-job-001")
    retry = client.retry_job("provider-job-001")

    assert cancelled.status is VocalJobStatus.CANCELLED
    assert retry.status is VocalJobStatus.QUEUED
    assert retry.job_id == "provider-job-002"
    assert retry.retry_of_job_id == "provider-job-001"


def test_job_path_identity_mismatch_is_rejected(vocal_fixture):
    fixture = deepcopy(vocal_fixture)
    fixture["running_job"]["job_id"] = "provider-job-other"

    with pytest.raises(VocalProviderInvalidResponseError):
        VocalProviderClient(FixtureTransport(fixture)).get_job_status("provider-job-001")


def test_result_is_metadata_candidate_with_root_parent_chain(vocal_fixture):
    result = VocalProviderClient(FixtureTransport(vocal_fixture)).get_result("provider-job-001")

    assert result.payload_present is False
    assert result.retention_status == "candidate"
    assert result.lineage.source_asset_version_id == ("00000000-0000-4000-8000-000000000001")
    assert result.lineage.parent_asset_version_id == str(SOURCE_VERSION_ID)
    assert result.lineage.processing_chain_id == ("55555555-5555-4555-8555-555555555555")
    assert result.checksum_scope == "metadata_descriptor"
    assert result.lineage.checksum_scope == "metadata_descriptor"


def test_manifest_review_and_unknown_vram_are_not_promoted(vocal_fixture):
    manifest = VocalProviderClient(FixtureTransport(vocal_fixture)).get_model_manifest(
        FAKE_MODEL_MANIFEST_ID
    )

    assert manifest.license_status == "REVIEW_REQUIRED"
    assert manifest.commercial_usage_status == "REVIEW_REQUIRED"
    assert manifest.recommended_vram is None
    assert manifest.artifact_checksum_scope == "fake_manifest_descriptor"


def test_fake_model_manifest_id_is_consistent_across_wire_fixture(vocal_fixture):
    assert vocal_fixture["queued_job"]["model_manifest_id"] == FAKE_MODEL_MANIFEST_ID
    assert vocal_fixture["running_job"]["model_manifest_id"] == FAKE_MODEL_MANIFEST_ID
    assert vocal_fixture["succeeded_job"]["model_manifest_id"] == FAKE_MODEL_MANIFEST_ID
    assert vocal_fixture["failed_job"]["model_manifest_id"] == FAKE_MODEL_MANIFEST_ID
    assert vocal_fixture["cancelled_job"]["model_manifest_id"] == FAKE_MODEL_MANIFEST_ID
    assert vocal_fixture["retry_job"]["model_manifest_id"] == FAKE_MODEL_MANIFEST_ID
    assert vocal_fixture["result"]["lineage"]["model_manifest_id"] == (FAKE_MODEL_MANIFEST_ID)
    assert vocal_fixture["manifest"]["model_manifest_id"] == FAKE_MODEL_MANIFEST_ID
    assert vocal_fixture["manifest"]["provider_id"] == "dohavocal"


def test_health_and_readiness_use_distinct_operations(vocal_fixture):
    transport = FixtureTransport(vocal_fixture)
    client = VocalProviderClient(transport)

    assert client.health() is True
    assert client.readiness() is True
    assert [(item.method, item.path) for item in transport.requests] == [
        ("GET", "/health"),
        ("GET", "/ready"),
    ]


class RaisingTransport:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def send(self, _request: VocalTransportRequest) -> VocalTransportResponse:
        raise self.error


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError("C:\\private\\timeout"), VocalProviderTimeoutError),
        (OSError("token=secret"), VocalProviderTransportError),
    ],
)
def test_transport_failures_do_not_expose_raw_exception(error, expected):
    with pytest.raises(expected) as captured:
        VocalProviderClient(RaisingTransport(error)).health()

    assert "private" not in str(captured.value)
    assert "secret" not in str(captured.value)


class SingleResponseTransport:
    def __init__(self, response: VocalTransportResponse) -> None:
        self.response = response

    def send(self, _request: VocalTransportRequest) -> VocalTransportResponse:
        return self.response


def test_unsafe_provider_error_fields_are_sanitized(vocal_fixture):
    payload = deepcopy(vocal_fixture["application_error"])
    payload["error"].update(
        {
            "message": "Traceback C:\\private\\model.pt token=secret",
            "details_id": "C:\\private\\details",
        }
    )
    client = VocalProviderClient(SingleResponseTransport(VocalTransportResponse(500, payload)))

    with pytest.raises(VocalProviderApplicationError) as captured:
        client.health()

    assert str(captured.value) == "Vocal Provider 요청을 처리하지 못했습니다."
    assert captured.value.detail.details_id == "not-available"


def test_contract_version_mismatch_is_distinct(vocal_fixture):
    payload = deepcopy(vocal_fixture["application_error"])
    payload["error"]["error_code"] = "CONTRACT_VERSION_UNSUPPORTED"
    client = VocalProviderClient(SingleResponseTransport(VocalTransportResponse(409, payload)))

    with pytest.raises(VocalProviderContractVersionError):
        client.get_capabilities()


def test_success_response_contract_version_mismatch_is_distinct(vocal_fixture):
    payload = deepcopy(vocal_fixture["capabilities"])
    payload["api_contract_version"] = "9.0.0"
    client = VocalProviderClient(SingleResponseTransport(VocalTransportResponse(200, payload)))

    with pytest.raises(VocalProviderContractVersionError):
        client.get_capabilities()


def test_invalid_response_does_not_expose_raw_body():
    client = VocalProviderClient(
        SingleResponseTransport(
            VocalTransportResponse(500, {"traceback": "C:\\private\\secret.py"})
        )
    )

    with pytest.raises(VocalProviderInvalidResponseError) as captured:
        client.health()

    assert "private" not in str(captured.value)
    assert "traceback" not in str(captured.value).lower()
