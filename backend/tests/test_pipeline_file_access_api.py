from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.models.pipeline_file import PipelineFile
from backend.models.pipeline_job import PipelineJob


def create_completed_pipeline(client: TestClient, suffix: str = "one") -> tuple[str, list[dict]]:
    storage = client.app.state.storage
    reference = storage.voice_references_dir / f"access-{suffix}.wav"
    shutil.copyfile(storage.sample_file, reference)
    profile = client.post(
        "/api/voice-profiles",
        json={
            "name": f"Access {suffix}",
            "reference_file_path": f"voices/references/access-{suffix}.wav",
            "consent_confirmed": True,
        },
    )
    assert profile.status_code == 201
    response = client.post(
        "/api/pipelines",
        json={
            "prompt": f"Audio access {suffix}",
            "duration_seconds": 1,
            "voice_profile_id": profile.json()["id"],
        },
    )
    assert response.status_code == 202
    job_id = response.json()["id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f"/api/pipelines/{job_id}").json()
        if job["status"] == "COMPLETED":
            files = client.get(f"/api/pipelines/{job_id}/files").json()
            return job_id, files
        if job["status"] == "FAILED":
            raise AssertionError(job)
        time.sleep(0.01)
    raise AssertionError("Pipeline did not complete")


def final_file(files: list[dict]) -> dict:
    return next(item for item in files if item["file_type"] == "final")


def content_url(job_id: str, file_id: str) -> str:
    return f"/api/pipelines/{job_id}/files/{file_id}/content"


def update_file(client: TestClient, file_id: str, **values: str) -> Path:
    with client.app.state.session_factory() as session:
        item = session.get(PipelineFile, file_id)
        assert item is not None
        try:
            path = client.app.state.storage.resolve_relative_path(item.file_path)
        except ValueError:
            path = Path(item.file_path)
        for key, value in values.items():
            setattr(item, key, value)
        session.commit()
        return path


def test_public_dto_and_full_content_download_contract(client: TestClient) -> None:
    job_id, files = create_completed_pipeline(client)
    item = final_file(files)

    assert "file_path" not in item
    assert item["content_available"] is True
    assert item["download_available"] is True
    assert item["content_url"] == content_url(job_id, item["id"])
    assert item["download_url"].endswith(f"/{item['id']}/download")
    metadata = next(file for file in files if file["file_type"] == "metadata")
    assert metadata["content_available"] is False
    assert metadata["content_url"] is None

    response = client.get(item["content_url"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["accept-ranges"] == "bytes"
    assert int(response.headers["content-length"]) == len(response.content)
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content[:4] == b"RIFF"

    head = client.head(item["content_url"])
    assert head.status_code == 200
    assert head.content == b""
    assert head.headers["content-length"] == response.headers["content-length"]

    download = client.get(item["download_url"])
    assert download.status_code == 200
    assert download.headers["content-disposition"].startswith(
        f'attachment; filename="doha-{job_id[:8]}-final.wav"'
    )
    assert download.headers["cache-control"] == "private, no-store"


def test_content_supports_start_middle_suffix_and_last_byte_ranges(
    client: TestClient,
) -> None:
    job_id, files = create_completed_pipeline(client)
    item = final_file(files)
    url = content_url(job_id, item["id"])
    full = client.get(url)
    size = len(full.content)
    ranges = [
        ("bytes=0-1023", 0, min(1023, size - 1)),
        ("bytes=128-255", 128, 255),
        ("bytes=-16", size - 16, size - 1),
        (f"bytes={size - 1}-{size - 1}", size - 1, size - 1),
    ]
    for header, start, end in ranges:
        response = client.get(url, headers={"Range": header})
        assert response.status_code == 206
        assert response.headers["accept-ranges"] == "bytes"
        assert response.headers["content-range"] == f"bytes {start}-{end}/{size}"
        assert int(response.headers["content-length"]) == end - start + 1
        assert response.content == full.content[start : end + 1]


@pytest.mark.parametrize(
    "range_header",
    ["items=0-1", "bytes=", "bytes=a-b", "bytes=20-10", "bytes=0-1,4-5"],
)
def test_invalid_ranges_return_stable_416(client: TestClient, range_header: str) -> None:
    job_id, files = create_completed_pipeline(client, range_header.replace("/", "-"))
    item = final_file(files)
    response = client.get(content_url(job_id, item["id"]), headers={"Range": range_header})
    assert response.status_code == 416
    assert response.json()["error"]["code"] == "INVALID_RANGE"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-range"].startswith("bytes */")


def test_range_start_beyond_file_size_returns_416(client: TestClient) -> None:
    job_id, files = create_completed_pipeline(client)
    item = final_file(files)
    response = client.get(content_url(job_id, item["id"]), headers={"Range": "bytes=999999999-"})
    assert response.status_code == 416
    assert response.json()["error"]["code"] == "INVALID_RANGE"


def test_file_access_rejects_missing_job_file_and_job_mismatch(
    client: TestClient,
) -> None:
    job_id, files = create_completed_pipeline(client, "first")
    other_job_id, _ = create_completed_pipeline(client, "second")
    file_id = final_file(files)["id"]
    missing = "00000000-0000-0000-0000-000000000000"

    assert client.get(content_url(missing, file_id)).json()["error"]["code"] == "PIPELINE_NOT_FOUND"
    assert client.get(content_url(job_id, missing)).json()["error"]["code"] == "FILE_NOT_FOUND"
    mismatch = client.get(content_url(other_job_id, file_id))
    assert mismatch.status_code == 404
    assert mismatch.json()["error"]["code"] == "FILE_JOB_MISMATCH"


def test_file_access_rejects_incomplete_pipeline_and_unavailable_type(
    client: TestClient,
) -> None:
    job_id, files = create_completed_pipeline(client)
    item = final_file(files)
    metadata = next(file for file in files if file["file_type"] == "metadata")
    unavailable = client.get(content_url(job_id, metadata["id"]))
    assert unavailable.status_code == 409
    assert unavailable.json()["error"]["code"] == "FILE_CONTENT_UNAVAILABLE"
    download = client.get(
        metadata["download_url"] or f"/api/pipelines/{job_id}/files/{metadata['id']}/download"
    )
    assert download.json()["error"]["code"] == "FILE_DOWNLOAD_UNAVAILABLE"

    with client.app.state.session_factory() as session:
        job = session.get(PipelineJob, job_id)
        assert job is not None
        job.status = "EXPORTING"
        session.commit()
    pending = client.get(content_url(job_id, item["id"]))
    assert pending.status_code == 409
    assert pending.json()["error"]["code"] == "PIPELINE_NOT_COMPLETED"


def test_file_access_rejects_missing_invalid_path_extension_mime_and_signature(
    client: TestClient,
) -> None:
    job_id, files = create_completed_pipeline(client)
    item = final_file(files)
    url = content_url(job_id, item["id"])
    original = update_file(client, item["id"])

    original.unlink()
    assert client.get(url).json()["error"]["code"] == "FILE_MISSING_FROM_STORAGE"

    outside = client.app.state.storage.root.parent / "outside.wav"
    shutil.copyfile(client.app.state.storage.sample_file, outside)
    update_file(client, item["id"], file_path="../outside.wav")
    assert client.get(url).json()["error"]["code"] == "INVALID_FILE_STORAGE_PATH"

    wrong_extension = client.app.state.storage.pipeline_dir / job_id / "audio.mp3"
    shutil.copyfile(client.app.state.storage.sample_file, wrong_extension)
    update_file(
        client,
        item["id"],
        file_path=client.app.state.storage.relative_path(wrong_extension),
        mime_type="audio/mpeg",
    )
    assert client.get(url).json()["error"]["code"] == "UNSUPPORTED_AUDIO_FILE"

    update_file(client, item["id"], mime_type="application/octet-stream")
    assert client.get(url).json()["error"]["code"] == "UNSUPPORTED_AUDIO_FILE"

    invalid_wav = client.app.state.storage.pipeline_dir / job_id / "invalid.wav"
    invalid_wav.write_bytes(b"not a wave file")
    update_file(
        client,
        item["id"],
        file_path=client.app.state.storage.relative_path(invalid_wav),
        mime_type="audio/wav",
    )
    assert client.get(url).json()["error"]["code"] == "UNSUPPORTED_AUDIO_FILE"


def test_file_access_rejects_symlink(client: TestClient) -> None:
    job_id, files = create_completed_pipeline(client)
    item = final_file(files)
    link = client.app.state.storage.pipeline_dir / job_id / "linked.wav"
    try:
        link.symlink_to(client.app.state.storage.sample_file)
    except OSError:
        pytest.skip("현재 Windows 권한에서 심볼릭 링크를 만들 수 없습니다.")
    update_file(
        client,
        item["id"],
        file_path=f"pipelines/{job_id}/linked.wav",
    )
    response = client.get(content_url(job_id, item["id"]))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_FILE_STORAGE_PATH"
