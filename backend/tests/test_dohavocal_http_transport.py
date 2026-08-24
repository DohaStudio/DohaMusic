"""Mock-HTTP verification for the DohaVocal production transport foundation."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from backend.core.config import Settings
from backend.providers.vocal import (
    HttpVocalProviderTransport,
    VocalCapability,
    VocalCreateJobRequest,
    VocalProviderApplicationError,
    VocalProviderClient,
    VocalProviderContractVersionError,
    VocalProviderInvalidResponseError,
    VocalProviderTimeoutError,
    VocalProviderTransportError,
    VocalTransportRequest,
    VoiceConversionInput,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "vocal-provider-contract-v0.1.0.json"
MODEL_MANIFEST_ID = "dohavocal.fake-model@0.1.0"


@pytest.fixture(scope="module")
def vocal_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _create_request() -> VocalCreateJobRequest:
    source_id = "11111111-1111-4111-8111-111111111111"
    reference_id = "22222222-2222-4222-8222-222222222222"
    return VocalCreateJobRequest(
        capability=VocalCapability.VOICE_CONVERSION,
        idempotency_key="http-transport-contract",
        project_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        input_asset_version_ids=(source_id,),
        input_artifact_ids=(reference_id,),
        model_manifest_id=MODEL_MANIFEST_ID,
        settings_snapshot={"quality": {"mode": "contract"}},
        requested_by="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        job_input=VoiceConversionInput(
            job_type="voice_conversion",
            source_asset_version_id=source_id,
            parent_asset_version_id=source_id,
            voice_reference_artifact_id=reference_id,
            source_entity_type="recording_take",
            reference_entity_type="voice_enrollment_sample",
        ),
    )


def _client(
    handler: Any,
    *,
    settings: Settings | None = None,
) -> tuple[VocalProviderClient, HttpVocalProviderTransport, httpx.Client]:
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = HttpVocalProviderTransport.from_settings(settings or Settings(), client=http_client)
    return VocalProviderClient(transport), transport, http_client


def test_all_nine_operations_use_expected_http_surface(vocal_fixture):
    requests: list[httpx.Request] = []
    routes = {
        ("GET", "/health"): (200, "health"),
        ("GET", "/ready"): (200, "readiness"),
        ("GET", "/v1/capabilities"): (200, "capabilities"),
        ("POST", "/v1/jobs"): (201, "queued_job"),
        ("GET", "/v1/jobs/provider-job-001"): (200, "running_job"),
        ("POST", "/v1/jobs/provider-job-001/cancel"): (200, "cancelled_job"),
        ("POST", "/v1/jobs/provider-job-001/retry"): (200, "retry_job"),
        ("GET", "/v1/jobs/provider-job-001/result"): (200, "result"),
        ("GET", f"/v1/model-manifests/{MODEL_MANIFEST_ID}"): (200, "manifest"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        status, name = routes[(request.method, request.url.path)]
        return httpx.Response(status, json=deepcopy(vocal_fixture[name]))

    client, transport, http_client = _client(handler)
    try:
        assert client.health()
        assert client.readiness()
        assert len(client.get_capabilities().supported_operations) == 9
        assert client.create_job(_create_request()).job_id == "provider-job-001"
        assert client.get_job_status("provider-job-001").status == "running"
        assert client.cancel_job("provider-job-001").status == "cancelled"
        assert client.retry_job("provider-job-001").job_id == "provider-job-002"
        assert client.get_result("provider-job-001").run_id == "provider-job-001"
        assert client.get_model_manifest(MODEL_MANIFEST_ID).provider_id == "dohavocal"
    finally:
        transport.close()
        http_client.close()

    assert len(requests) == 9
    create_call = requests[3]
    assert create_call.headers["accept"] == "application/json"
    assert create_call.headers["content-type"].startswith("application/json")
    assert json.loads(create_call.content) == _create_request().model_dump(mode="json")
    assert all(request.url.host == "127.0.0.1" for request in requests)
    assert all(request.url.query == b"" for request in requests)


@pytest.mark.parametrize(
    "fixture_name",
    ["queued_job", "running_job", "succeeded_job", "failed_job", "cancelled_job"],
)
def test_http_job_states_are_preserved(vocal_fixture, fixture_name):
    payload = deepcopy(vocal_fixture[fixture_name])

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client, transport, http_client = _client(handler)
    try:
        job = client.get_job_status("provider-job-001")
    finally:
        transport.close()
        http_client.close()

    assert job.status.value == payload["status"]


def test_http_unknown_job_state_fails_closed(vocal_fixture):
    payload = deepcopy(vocal_fixture["running_job"])
    payload["status"] = "unknown"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client, transport, http_client = _client(handler)
    try:
        with pytest.raises(VocalProviderInvalidResponseError):
            client.get_job_status("provider-job-001")
    finally:
        transport.close()
        http_client.close()


def test_http_result_preserves_metadata_only_lineage(vocal_fixture):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=vocal_fixture["result"])

    client, transport, http_client = _client(handler)
    try:
        result = client.get_result("provider-job-001")
    finally:
        transport.close()
        http_client.close()

    assert result.payload_present is False
    assert result.checksum_scope == "metadata_descriptor"
    assert result.lineage.checksum_scope == "metadata_descriptor"
    assert result.lineage.source_asset_version_id == ("00000000-0000-4000-8000-000000000001")
    assert result.lineage.parent_asset_version_id == ("11111111-1111-4111-8111-111111111111")
    assert result.lineage.processing_chain_id == ("55555555-5555-4555-8555-555555555555")
    assert result.lineage.model_manifest_id == MODEL_MANIFEST_ID


def test_http_manifest_preserves_review_status_and_null_vram(vocal_fixture):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=vocal_fixture["manifest"])

    client, transport, http_client = _client(handler)
    try:
        manifest = client.get_model_manifest(MODEL_MANIFEST_ID)
    finally:
        transport.close()
        http_client.close()

    assert manifest.provider_id == "dohavocal"
    assert manifest.model_manifest_id == MODEL_MANIFEST_ID
    assert manifest.api_contract_version == "0.1.0"
    assert manifest.license_status == "REVIEW_REQUIRED"
    assert manifest.commercial_usage_status == "REVIEW_REQUIRED"
    assert manifest.recommended_vram is None
    assert manifest.artifact_checksum_scope == "fake_manifest_descriptor"


def test_component_timeouts_are_applied_to_each_request(vocal_fixture):
    observed: dict[str, float] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed.update(request.extensions["timeout"])
        return httpx.Response(200, json=vocal_fixture["health"])

    settings = Settings(
        dohavocal_connect_timeout_seconds=1.1,
        dohavocal_read_timeout_seconds=2.2,
        dohavocal_write_timeout_seconds=3.3,
        dohavocal_pool_timeout_seconds=4.4,
    )
    client, transport, http_client = _client(handler, settings=settings)
    try:
        assert client.health()
    finally:
        transport.close()
        http_client.close()

    assert observed == {"connect": 1.1, "read": 2.2, "write": 3.3, "pool": 4.4}


@pytest.mark.parametrize(
    "base_url",
    [
        "file:///tmp/dohavocal",
        "ftp://provider.example",
        "data:text/plain,unsafe",
        "javascript:alert(1)",
        "https://user:secret@provider.example",
        "//provider.example",
        "https://provider.example?target=other",
        "https://provider.example#fragment",
    ],
)
def test_base_url_rejects_non_http_or_override_primitives(base_url):
    with pytest.raises((ValueError, ValidationError)):
        Settings(dohavocal_base_url=base_url)
    with pytest.raises(ValueError):
        HttpVocalProviderTransport(base_url=base_url)


def test_base_url_and_timeouts_load_from_environment(monkeypatch):
    monkeypatch.setenv("DOHAVOCAL_BASE_URL", "https://vocal.internal.example/runtime/")
    monkeypatch.setenv("DOHAVOCAL_CONNECT_TIMEOUT_SECONDS", "1.5")
    monkeypatch.setenv("DOHAVOCAL_READ_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("DOHAVOCAL_WRITE_TIMEOUT_SECONDS", "8")
    monkeypatch.setenv("DOHAVOCAL_POOL_TIMEOUT_SECONDS", "1")

    settings = Settings.from_environment()

    assert settings.dohavocal_base_url == "https://vocal.internal.example/runtime"
    assert settings.dohavocal_connect_timeout_seconds == 1.5
    assert settings.dohavocal_read_timeout_seconds == 20
    assert settings.dohavocal_write_timeout_seconds == 8
    assert settings.dohavocal_pool_timeout_seconds == 1


def test_base_url_trailing_slashes_do_not_change_endpoint_path(vocal_fixture):
    observed: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(200, json=vocal_fixture["health"])

    settings = Settings(dohavocal_base_url="https://trusted.example/runtime///")
    client, transport, http_client = _client(handler, settings=settings)
    try:
        assert client.health()
    finally:
        transport.close()
        http_client.close()

    assert observed[0].url.path == "/runtime/health"


def test_injected_client_cannot_enable_cross_origin_redirect():
    observed: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(str(request.url))
        if len(observed) == 1:
            return httpx.Response(302, headers={"location": "http://untrusted.example/health"})
        return httpx.Response(200, json={"status": "ok", "provider_id": "dohavocal"})

    http_client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    transport = HttpVocalProviderTransport(base_url="https://trusted.example", client=http_client)
    try:
        with pytest.raises(VocalProviderInvalidResponseError):
            VocalProviderClient(transport).health()
    finally:
        transport.close()
        http_client.close()

    assert observed == ["https://trusted.example/health"]


def test_dynamic_path_segments_are_encoded_without_host_override(vocal_fixture):
    job_id = "../job?target=https://other.example/#fragment"
    observed: list[httpx.Request] = []
    payload = deepcopy(vocal_fixture["running_job"])
    payload["job_id"] = job_id

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(200, json=payload)

    client, transport, http_client = _client(handler)
    try:
        assert client.get_job_status(job_id).job_id == job_id
    finally:
        transport.close()
        http_client.close()

    request = observed[0]
    assert request.url.host == "127.0.0.1"
    assert request.url.query == b""
    assert b"%2F" in request.url.raw_path
    assert b"%3F" in request.url.raw_path
    assert b"%23" in request.url.raw_path


def test_manifest_path_segment_is_encoded_without_semantic_override(vocal_fixture):
    manifest_id = "model/../variant?target=other#fragment"
    observed: list[httpx.Request] = []
    payload = deepcopy(vocal_fixture["manifest"])
    payload["model_manifest_id"] = manifest_id

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(200, json=payload)

    client, transport, http_client = _client(handler)
    try:
        assert client.get_model_manifest(manifest_id).model_manifest_id == manifest_id
    finally:
        transport.close()
        http_client.close()

    request = observed[0]
    assert request.url.host == "127.0.0.1"
    assert request.url.query == b""
    assert b"%2F" in request.url.raw_path
    assert b"%3F" in request.url.raw_path
    assert b"%23" in request.url.raw_path


@pytest.mark.parametrize(
    ("job_id", "raw_suffix"),
    [("%2F", b"%252F"), ("%2E%2E", b"%252E%252E"), ("//", b"%2F%2F")],
)
def test_preencoded_and_double_slash_job_ids_remain_one_raw_segment(
    vocal_fixture, job_id, raw_suffix
):
    observed: list[httpx.Request] = []
    payload = deepcopy(vocal_fixture["running_job"])
    payload["job_id"] = job_id

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(200, json=payload)

    client, transport, http_client = _client(handler)
    try:
        assert client.get_job_status(job_id).job_id == job_id
    finally:
        transport.close()
        http_client.close()

    assert observed[0].url.raw_path.endswith(b"/" + raw_suffix)


@pytest.mark.parametrize(
    "exception_type",
    [httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout],
)
def test_httpx_timeout_categories_map_to_safe_timeout_error(exception_type):
    def handler(request: httpx.Request) -> httpx.Response:
        raise exception_type("C:\\private\\voice.wav token=secret", request=request)

    client, transport, http_client = _client(handler)
    try:
        with pytest.raises(VocalProviderTimeoutError) as captured:
            client.health()
    finally:
        transport.close()
        http_client.close()

    assert "private" not in str(captured.value)
    assert "secret" not in str(captured.value)


def test_connect_failure_maps_to_safe_transport_error():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("token=secret", request=request)

    client, transport, http_client = _client(handler)
    try:
        with pytest.raises(VocalProviderTransportError) as captured:
            client.create_job(_create_request())
    finally:
        transport.close()
        http_client.close()

    assert calls == 1
    assert "secret" not in str(captured.value)


@pytest.mark.parametrize("status_code", [404, 409, 422, 500])
def test_structured_application_errors_are_preserved(vocal_fixture, status_code):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=vocal_fixture["application_error"])

    client, transport, http_client = _client(handler)
    try:
        with pytest.raises(VocalProviderApplicationError) as captured:
            client.health()
    finally:
        transport.close()
        http_client.close()

    assert captured.value.detail.error_code == "IDEMPOTENCY_CONFLICT"


def test_http_application_error_does_not_leak_raw_sensitive_fields(vocal_fixture):
    payload = deepcopy(vocal_fixture["application_error"])
    payload["error"].update(
        {
            "message": (
                "Traceback C:\\Users\\private\\model.pt /home/user/model.pt token=secret-value"
            ),
            "details_id": "api_key=secret-value",
        }
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json=payload)

    client, transport, http_client = _client(handler)
    try:
        with pytest.raises(VocalProviderApplicationError) as captured:
            client.health()
    finally:
        transport.close()
        http_client.close()

    safe_error = str(captured.value)
    assert "private" not in safe_error
    assert "/home/" not in safe_error
    assert "secret-value" not in safe_error
    assert "traceback" not in safe_error.lower()
    assert captured.value.detail.details_id == "not-available"


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        (b"<html>secret</html>", "text/html"),
        (b"plain text", "text/plain"),
        (b"binary", "application/octet-stream"),
        (b"", "application/json"),
        (b"{invalid", "application/json"),
    ],
)
def test_non_json_or_malformed_json_fails_closed(content, content_type):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content, headers={"content-type": content_type})

    client, transport, http_client = _client(handler)
    try:
        with pytest.raises(VocalProviderInvalidResponseError) as captured:
            client.health()
    finally:
        transport.close()
        http_client.close()

    assert "secret" not in str(captured.value)
    assert "invalid" not in str(captured.value)


def test_json_content_type_with_charset_is_accepted(vocal_fixture):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(vocal_fixture["health"]).encode(),
            headers={"content-type": "application/json; charset=utf-8"},
        )

    client, transport, http_client = _client(handler)
    try:
        assert client.health()
    finally:
        transport.close()
        http_client.close()


@pytest.mark.parametrize(
    ("fixture_name", "mutation", "operation"),
    [
        ("health", lambda payload: payload.update(provider_id="other"), "health"),
        ("readiness", lambda payload: payload.update(status="not_ready"), "readiness"),
    ],
)
def test_probe_identity_and_readiness_state_fail_closed(
    vocal_fixture, fixture_name, mutation, operation
):
    payload = deepcopy(vocal_fixture[fixture_name])
    mutation(payload)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client, transport, http_client = _client(handler)
    try:
        with pytest.raises(VocalProviderInvalidResponseError):
            getattr(client, operation)()
    finally:
        transport.close()
        http_client.close()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(provider_id="other-provider"),
        lambda payload: payload.update(api_contract_version="9.0.0"),
        lambda payload: payload.update(extra_field="unexpected"),
        lambda payload: payload.update(capabilities=["unknown_vocal"]),
        lambda payload: payload.pop("provider_id"),
    ],
)
def test_identity_version_extra_and_enum_drift_fail_closed(vocal_fixture, mutation):
    payload = deepcopy(vocal_fixture["capabilities"])
    mutation(payload)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client, transport, http_client = _client(handler)
    try:
        with pytest.raises((VocalProviderInvalidResponseError, VocalProviderContractVersionError)):
            client.get_capabilities()
    finally:
        transport.close()
        http_client.close()


def test_transport_close_is_idempotent_and_does_not_close_injected_client():
    http_client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"status": "ok"}))
    )
    transport = HttpVocalProviderTransport(base_url="http://127.0.0.1:8080", client=http_client)

    transport.close()
    transport.close()

    assert transport.is_closed
    assert not http_client.is_closed
    with pytest.raises(OSError):
        transport.send(VocalTransportRequest("GET", "/health"))
    http_client.close()


def test_unavailable_injected_client_maps_to_safe_transport_error(vocal_fixture):
    client, transport, http_client = _client(
        lambda _request: httpx.Response(200, json=vocal_fixture["health"])
    )
    http_client.close()

    with pytest.raises(VocalProviderTransportError):
        client.health()

    transport.close()


def test_context_manager_closes_owned_client_without_network():
    with HttpVocalProviderTransport(base_url="http://127.0.0.1:8080") as transport:
        assert not transport.is_closed
        owned_client = transport._client

    assert transport.is_closed
    assert owned_client.is_closed


def test_context_manager_closes_owned_client_after_exception():
    transport = HttpVocalProviderTransport(base_url="http://127.0.0.1:8080")
    owned_client = transport._client

    with pytest.raises(RuntimeError, match="sentinel"), transport:
        raise RuntimeError("sentinel")

    assert transport.is_closed
    assert owned_client.is_closed
