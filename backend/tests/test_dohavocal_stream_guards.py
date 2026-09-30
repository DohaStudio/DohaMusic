"""Bounded streaming and explicit selector adversarial tests."""

from hashlib import sha256

import httpx
import pytest

from backend.providers.vocal import (
    HttpVocalProviderTransport,
    VocalPayloadAcquisitionError,
    VocalPayloadAcquisitionRequest,
    VocalPayloadSource,
    VocalProviderPayloadEntry,
)
from backend.providers.vocal.transport import VocalTransportRequest


class Stream(httpx.SyncByteStream):
    def __init__(self, *, interrupt=False):
        self.reads = 0
        self.closed = False
        self.interrupt = interrupt

    def __iter__(self):
        for _ in range(4):
            self.reads += 1
            if self.interrupt and self.reads == 2:
                raise httpx.ReadError("fixture interruption")
            yield b"x" * 65536

    def close(self):
        self.closed = True


def request(check_current=None, *, size=262144):
    return VocalPayloadAcquisitionRequest(
        job_id="job-1",
        payload=VocalProviderPayloadEntry(
            provider_artifact_id="artifact-1",
            role="converted_vocal_candidate",
            source=VocalPayloadSource(kind="provider_subresource", source_id="source-1"),
            checksum_algorithm="sha256",
            payload_checksum=sha256(b"x" * 262144).hexdigest(),
            expected_size_bytes=size,
            expected_media_type="audio/wav",
            available_until=None,
        ),
        max_size_bytes=262144,
        check_current=check_current,
    )


def test_cancellation_stops_consumption_and_closes_response():
    stream = Stream()
    checks = 0

    class Cancelled(RuntimeError):
        pass

    def check():
        nonlocal checks
        checks += 1
        if checks == 3:
            raise Cancelled("cancelled")

    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, headers={"content-type": "audio/wav"}, stream=stream)
        )
    ) as client:
        transport = HttpVocalProviderTransport(base_url="http://fixed.test", client=client)
        with pytest.raises(Cancelled):
            transport.acquire_payload(request(check))
    assert stream.closed and stream.reads == 2


@pytest.mark.parametrize("mode", ["interrupt", "oversize"])
def test_partial_stream_failure_closes_without_verified_output(mode):
    stream = Stream(interrupt=mode == "interrupt")
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, headers={"content-type": "audio/wav"}, stream=stream)
        )
    ) as client:
        transport = HttpVocalProviderTransport(base_url="http://fixed.test", client=client)
        with pytest.raises(VocalPayloadAcquisitionError):
            transport.acquire_payload(request(size=65536 if mode == "oversize" else 262144))
    assert stream.closed and stream.reads == 2


@pytest.mark.parametrize(
    ("method", "path", "version"),
    [
        ("GET", "/v1/capabilities", "https://other.invalid"),
        ("POST", "/v1/jobs", "0.2.0"),
        ("GET", "//other.invalid", "0.2.0"),
        ("GET", "/v1/capabilities?api_contract_version=0.2.0", None),
    ],
)
def test_selection_cannot_override_origin_or_inject_query(method, path, version):
    def unexpected(_):
        pytest.fail("invalid selector reached network")

    with httpx.Client(transport=httpx.MockTransport(unexpected)) as client:
        transport = HttpVocalProviderTransport(base_url="http://fixed.test", client=client)
        with pytest.raises(OSError):
            transport.send(VocalTransportRequest(method, path, api_contract_version=version))
