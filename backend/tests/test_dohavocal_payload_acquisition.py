from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from backend.providers.vocal import (
    HttpVocalProviderTransport,
    VocalCapabilities,
    VocalPayloadAcquisitionError,
    VocalPayloadAcquisitionErrorCode,
    VocalPayloadAcquisitionRequest,
    VocalPayloadBackedResultCandidate,
    VocalProviderClient,
)

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "vocal-provider-contract-v0.2.0.json"
)


@pytest.fixture
def payload_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_020_capability_and_result_are_strictly_negotiated(payload_fixture) -> None:
    capabilities = VocalCapabilities.model_validate(payload_fixture["capabilities"])
    assert capabilities.api_contract_version == "0.2.0"
    assert capabilities.payload_acquisition is not None
    assert capabilities.supported_operations[-1] == "GetPayloadContent"

    result = VocalPayloadBackedResultCandidate.model_validate(payload_fixture["result"])
    assert result.payload_present is True
    assert result.payloads[0].source.source_id == "content-001"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["capabilities"].pop("payload_acquisition"),
        lambda value: value["capabilities"]["supported_operations"].pop(),
        lambda value: value["capabilities"]["payload_acquisition"].update(
            source_kinds=["url"]
        ),
        lambda value: value["result"]["payloads"][0]["source"].update(
            source_id="https://evil.example/payload"
        ),
        lambda value: value["result"]["payloads"][0]["source"].update(
            source_id="../private/payload"
        ),
        lambda value: value["result"]["payloads"][0]["source"].update(
            source_id="token=secret"
        ),
        lambda value: value["result"]["payloads"][0].update(payload_checksum="A" * 64),
        lambda value: value["result"]["payloads"][0].update(
            expected_media_type="application/octet-stream"
        ),
        lambda value: value["result"].update(payload_present=False),
    ],
)
def test_020_contract_drift_fails_closed(payload_fixture, mutation) -> None:
    value = deepcopy(payload_fixture)
    mutation(value)
    with pytest.raises(ValidationError):
        if value["capabilities"] != payload_fixture["capabilities"]:
            VocalCapabilities.model_validate(value["capabilities"])
        else:
            VocalPayloadBackedResultCandidate.model_validate(value["result"])


def _request(payload_fixture, *, max_size_bytes: int = 32):
    result = VocalPayloadBackedResultCandidate.model_validate(payload_fixture["result"])
    return VocalPayloadAcquisitionRequest(
        job_id=result.run_id,
        payload=result.payloads[0],
        max_size_bytes=max_size_bytes,
    )


def _transport(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return (
        HttpVocalProviderTransport(
            base_url="https://trusted.example/runtime", client=client
        ),
        client,
    )


def test_payload_is_streamed_and_verified_without_returning_a_locator(
    payload_fixture,
) -> None:
    observed: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(
            200,
            content=b"payload",
            headers={"content-type": "audio/wav", "content-length": "7"},
        )

    transport, client = _transport(handler)
    try:
        verified = transport.acquire_payload(_request(payload_fixture))
    finally:
        transport.close()
        client.close()

    assert verified.content == b"payload"
    assert verified.size_bytes == 7
    assert verified.payload_checksum == (
        "239f59ed55e737c77147cf55ad0c1b030b6d7ee748a7426952f9b852d5a935e5"
    )
    assert observed[0].url.host == "trusted.example"
    assert observed[0].url.path == (
        "/runtime/v1/jobs/provider-job-001/artifacts/provider-artifact-001/"
        "payloads/content-001"
    )
    assert observed[0].headers["accept"] == "audio/wav"


def test_content_length_is_optional(payload_fixture) -> None:
    transport, client = _transport(
        lambda _request: httpx.Response(
            200, content=b"payload", headers={"content-type": "audio/wav"}
        )
    )
    try:
        assert transport.acquire_payload(_request(payload_fixture)).size_bytes == 7
    finally:
        transport.close()
        client.close()


def test_redirect_is_not_followed(payload_fixture) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            302, headers={"location": "https://untrusted.example/payload"}
        )

    transport, client = _transport(handler)
    try:
        with pytest.raises(VocalPayloadAcquisitionError) as error:
            transport.acquire_payload(_request(payload_fixture))
    finally:
        transport.close()
        client.close()
    assert error.value.code is VocalPayloadAcquisitionErrorCode.PAYLOAD_TRANSFER_FAILED
    assert calls == 1


def test_timeout_maps_to_transfer_failure_without_detail_leak(payload_fixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("C:\\private\\voice.wav token=secret", request=request)

    transport, client = _transport(handler)
    try:
        with pytest.raises(VocalPayloadAcquisitionError) as error:
            transport.acquire_payload(_request(payload_fixture))
    finally:
        transport.close()
        client.close()
    assert error.value.code is VocalPayloadAcquisitionErrorCode.PAYLOAD_TRANSFER_FAILED
    assert "secret" not in str(error.value)


def test_configured_maximum_rejects_descriptor_before_network(payload_fixture) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"payload")

    transport, client = _transport(handler)
    try:
        with pytest.raises(VocalPayloadAcquisitionError) as error:
            transport.acquire_payload(_request(payload_fixture, max_size_bytes=6))
    finally:
        transport.close()
        client.close()
    assert (
        error.value.code is VocalPayloadAcquisitionErrorCode.PAYLOAD_INTEGRITY_MISMATCH
    )
    assert calls == 0


def test_expired_availability_rejects_before_network(payload_fixture) -> None:
    result = VocalPayloadBackedResultCandidate.model_validate(payload_fixture["result"])
    expired = result.payloads[0].model_copy(
        update={"available_until": datetime(2000, 1, 1, tzinfo=UTC)}
    )
    with pytest.raises(VocalPayloadAcquisitionError) as error:
        VocalPayloadAcquisitionRequest(
            job_id=result.run_id, payload=expired, max_size_bytes=32
        )
    assert error.value.code is VocalPayloadAcquisitionErrorCode.PAYLOAD_EXPIRED


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (404, VocalPayloadAcquisitionErrorCode.PAYLOAD_UNAVAILABLE),
        (410, VocalPayloadAcquisitionErrorCode.PAYLOAD_EXPIRED),
        (401, VocalPayloadAcquisitionErrorCode.PAYLOAD_ACCESS_DENIED),
        (403, VocalPayloadAcquisitionErrorCode.PAYLOAD_ACCESS_DENIED),
        (500, VocalPayloadAcquisitionErrorCode.PAYLOAD_TRANSFER_FAILED),
    ],
)
def test_payload_http_failures_have_stable_safe_semantics(
    payload_fixture, status, code
) -> None:
    transport, client = _transport(
        lambda _request: httpx.Response(status, content=b"secret")
    )
    try:
        with pytest.raises(VocalPayloadAcquisitionError) as error:
            transport.acquire_payload(_request(payload_fixture))
    finally:
        transport.close()
        client.close()
    assert error.value.code is code
    assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    ("content", "headers"),
    [
        (b"payload", {"content-type": "audio/flac"}),
        (b"payload", {"content-type": "audio/wav", "content-length": "8"}),
        (b"changed", {"content-type": "audio/wav", "content-length": "7"}),
        (b"short", {"content-type": "audio/wav"}),
    ],
)
def test_media_size_and_checksum_mismatch_fail_closed(
    payload_fixture, content, headers
) -> None:
    transport, client = _transport(
        lambda _request: httpx.Response(200, content=content, headers=headers)
    )
    try:
        with pytest.raises(VocalPayloadAcquisitionError) as error:
            transport.acquire_payload(_request(payload_fixture))
    finally:
        transport.close()
        client.close()
    assert (
        error.value.code is VocalPayloadAcquisitionErrorCode.PAYLOAD_INTEGRITY_MISMATCH
    )


def test_client_selects_result_dto_from_negotiated_version(payload_fixture) -> None:
    transport, http_client = _transport(
        lambda _request: httpx.Response(200, json=payload_fixture["result"])
    )
    try:
        result = VocalProviderClient(transport).get_result(
            "provider-job-001", api_contract_version="0.2.0"
        )
    finally:
        transport.close()
        http_client.close()
    assert isinstance(result, VocalPayloadBackedResultCandidate)
