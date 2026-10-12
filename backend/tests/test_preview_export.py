"""Synthetic WAV coverage; no models, external APIs or personal voice data."""

import hashlib
import io
import json
import os
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy.io import wavfile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.factory import create_app
from backend.audio_analysis.contracts import (
    AudioAnalysisResult,
    HookAnalysisResult,
    TempoAnalysisResult,
    sanitize_result_metadata,
)
from backend.audio_analysis.preview import render_preview
from backend.models.pipeline_file import PipelineFile
from backend.models.pipeline_job import PipelineJob
from backend.repositories.pipeline_repository import PipelineRepository
from backend.services.pipeline_preview_service import PipelinePreviewService
from backend.services.pipeline_service import PipelineService
from backend.tests.test_pipeline_api import create_pipeline, create_profile
from backend.workers.pipeline_worker import PipelineWorker


def hook(**changes):
    result = {
        "hook_analysis_version": "1.0",
        "status": "COMPLETED",
        "candidate": {
            "start_seconds": 2,
            "end_seconds": 17,
            "duration_seconds": 15,
            "confidence": 0.5,
            "selection_strategy": "energy_peak",
        },
    }
    result.update(changes)
    return result


@pytest.mark.parametrize(
    "rate,channels,frames",
    [
        (8000, 1, 160000),
        (44100, 2, 882000),
        (48000, 2, 1000),
        (8000, 1, 1),
        (8000, 1, 3),
        (8000, 1, 120000),
    ],
)
def test_audio_contract_in_memory(monkeypatch, rate, channels, frames):
    # Real scipy WAV codec, routed through memory to avoid filesystem dependencies.
    raw = np.full((frames, channels), 16000, dtype=np.int16)
    if channels == 1:
        raw = raw[:, 0]
    source = io.BytesIO()
    wavfile.write(source, rate, raw)
    original = source.getvalue()
    output = io.BytesIO()
    read, write = wavfile.read, wavfile.write
    monkeypatch.setattr(wavfile, "read", lambda _: read(io.BytesIO(original)))
    monkeypatch.setattr(wavfile, "write", lambda _, sr, pcm: write(output, sr, pcm))
    metadata = render_preview(Path("final.wav"), Path("preview.wav"))
    sr, pcm = read(io.BytesIO(output.getvalue()))
    assert sr == rate
    assert pcm.shape == raw[: min(frames, 15 * rate)].shape
    assert pcm.dtype == np.int16
    assert metadata["duration_seconds"] == min(frames, 15 * rate) / rate
    assert metadata["channels"] == channels
    assert source.getvalue() == original
    fade = min(round(rate * 0.020), len(pcm) // 2)
    if fade:
        assert np.all(pcm[0] == 0) and np.all(pcm[-1] == 0)
        expected = np.rint(16000 * np.linspace(0, 1, fade)).astype(np.int16)
        assert np.array_equal(pcm[:fade] if channels == 1 else pcm[:fade, 0], expected)


@pytest.mark.parametrize(
    "candidate,expected",
    [
        (hook(), "hook_candidate"),
        (None, "fallback_middle"),
        (hook(status="FAILED"), "fallback_middle"),
        (hook(hook_analysis_version="2.0"), "fallback_middle"),
        (hook(candidate={**hook()["candidate"], "confidence": 0.49}), "fallback_middle"),
        (hook(candidate={**hook()["candidate"], "end_seconds": 50}), "fallback_middle"),
        (hook(candidate={**hook()["candidate"], "start_seconds": -1}), "fallback_middle"),
        (hook(candidate={**hook()["candidate"], "confidence": float("nan")}), "fallback_middle"),
    ],
)
def test_hook_validation(monkeypatch, candidate, expected):
    monkeypatch.setattr(wavfile, "read", lambda _: (8000, np.zeros(160000, np.int16)))
    monkeypatch.setattr(wavfile, "write", lambda *args: None)
    result = render_preview(Path("final.wav"), Path("preview.wav"), candidate)
    assert result["selection_strategy"] == expected
    assert result["start_seconds"] == (2 if expected == "hook_candidate" else 2.5)


def test_source_overwrite_and_public_projection():
    with pytest.raises(ValueError):
        render_preview(Path("final.wav"), Path("final.wav"))
    assert sanitize_result_metadata(
        {
            "preview": {
                "status": "ready",
                "version": "1.0",
                "file_path": "secret",
            }
        }
    )["preview"] == {"status": "ready", "version": "1.0"}
    assert "preview" not in sanitize_result_metadata({"preview": {"status": "unknown"}})


@pytest.mark.parametrize("rate,channels,frames", [(22050, 1, 441000), (48000, 2, 3)])
def test_file_wav_duration_fade_and_source_hash(tmp_path, rate, channels, frames):
    source = tmp_path / "final.wav"
    destination = tmp_path / "preview.wav"
    raw = np.full((frames, channels), 16000, dtype=np.int16)
    if channels == 1:
        raw = raw[:, 0]
    wavfile.write(source, rate, raw)
    original_hash = hashlib.sha256(source.read_bytes()).digest()
    result = render_preview(source, destination, hook())
    actual_rate, samples = wavfile.read(destination)
    assert hashlib.sha256(source.read_bytes()).digest() == original_hash
    assert actual_rate == rate and samples.dtype == np.int16
    assert samples.shape == raw[: min(frames, 15 * rate)].shape
    assert result["duration_seconds"] == min(frames, 15 * rate) / rate
    assert result["selection_strategy"] == (
        "hook_candidate" if frames >= 17 * rate else "fallback_middle"
    )
    assert np.all(samples[0] == 0) and np.all(samples[-1] == 0)


@pytest.fixture
def memory_publication(monkeypatch):
    engine = create_engine("sqlite://")
    PipelineJob.__table__.create(engine)
    PipelineFile.__table__.create(engine)
    factory = sessionmaker(engine)
    root = Path.cwd() / "synthetic-preview-storage"
    storage = SimpleNamespace(
        root=root,
        pipeline_dir=root / "pipelines",
        relative_path=lambda path: path.relative_to(root).as_posix(),
    )
    with factory() as session:
        session.add(
            PipelineJob(
                id="job",
                voice_profile_id="voice",
                status="COMPLETED",
                current_step="completed",
                prompt="synthetic",
                duration_seconds=30,
                pipeline_version="test",
                result_metadata={
                    "success": True,
                    "preview": {"version": "1.0", "status": "pending"},
                },
            )
        )
        session.add(
            PipelineFile(
                job_id="job",
                file_type="final",
                mime_type="audio/wav",
                file_path="pipelines/job/final.wav",
            )
        )
        session.commit()
    preview_service = PipelinePreviewService(factory, storage)
    monkeypatch.setattr(
        PipelineService,
        "_validate_file",
        lambda _, row: (
            root / row.file_path,
            44,
        ),
    )
    monkeypatch.setattr(Path, "glob", lambda *args: [])
    monkeypatch.setattr(Path, "replace", lambda _, target: target)
    removed = []
    monkeypatch.setattr(Path, "unlink", lambda path, **kwargs: removed.append(path.name))
    monkeypatch.setattr(
        "backend.services.pipeline_preview_service.tempfile.mkstemp",
        lambda **kw: (
            os.dup(1),
            str(root / "pipelines/job/preview-synthetic.wav"),
        ),
    )
    metadata = {
        "status": "ready",
        "version": "1.0",
        "sample_rate": 8000,
        "channels": 1,
        "duration_seconds": 15,
    }
    calls = []

    def render(*args):
        calls.append(args)
        return dict(metadata)

    monkeypatch.setattr("backend.services.pipeline_preview_service.render_preview", render)
    monkeypatch.setattr(preview_service, "_sync_metadata", lambda *args: None)
    wav = io.BytesIO()
    wavfile.write(wav, 8000, np.zeros(120000, np.int16))
    open_wave = wave.open
    monkeypatch.setattr(
        "backend.services.pipeline_preview_service.wave.open",
        lambda *args: open_wave(io.BytesIO(wav.getvalue()), "rb"),
    )
    yield preview_service, factory, calls, removed
    engine.dispose()


def test_memory_transaction_duplicate_and_ready_reuse(memory_publication):
    preview_service, factory, calls, _ = memory_publication
    assert preview_service.recoverable_ids() == ["job"]
    preview_service.run("job")
    preview_service.run("job")
    assert len(calls) == 1
    with factory() as session:
        assert session.query(PipelineFile).filter_by(file_type="preview").count() == 1
        job = session.get(PipelineJob, "job")
        assert job.status == "COMPLETED" and job.result_metadata["preview"]["status"] == "ready"


def test_memory_registration_rollback_and_cleanup(memory_publication, monkeypatch):
    preview_service, factory, _, removed = memory_publication
    original_commit = Session.commit

    def fail_registration(session):
        if any(isinstance(row, PipelineFile) and row.file_type == "preview" for row in session.new):
            raise RuntimeError("DB registration failure")
        original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_registration)
    preview_service.run("job")
    with factory() as session:
        assert session.query(PipelineFile).filter_by(file_type="preview").count() == 0
        assert session.query(PipelineFile).filter_by(file_type="final").count() == 1
        job = session.get(PipelineJob, "job")
        assert job.status == "COMPLETED" and job.result_metadata["success"] is True
        assert job.result_metadata["preview"]["status"] == "failed"
    assert "preview.wav" in removed and "final.wav" not in removed


def test_memory_pending_recovery_and_missing_source(memory_publication):
    preview_service, factory, _, _ = memory_publication
    # Fresh service models worker restart: pending lives in DB, not process memory.
    restarted = PipelinePreviewService(factory, preview_service.storage)
    restarted._sync_metadata = preview_service._sync_metadata
    restarted.run("job")
    with factory() as session:
        job = session.get(PipelineJob, "job")
        assert job.result_metadata["preview"]["status"] == "ready"
        session.query(PipelineFile).delete()
        job.result_metadata = {"success": True, "preview": {"status": "pending"}}
        session.commit()
    restarted.run("job")
    with factory() as session:
        job = session.get(PipelineJob, "job")
        assert job.status == "COMPLETED"
        assert job.result_metadata["preview"]["status"] == "unavailable"


def test_memory_metadata_sync_failure_preserves_ready(memory_publication, monkeypatch):
    preview_service, factory, calls, removed = memory_publication

    def fail_sync(*args):
        raise OSError("metadata mirror unavailable")

    monkeypatch.setattr(preview_service, "_sync_metadata", fail_sync)
    preview_service.run("job")
    preview_service.run("job")
    with factory() as session:
        job = session.get(PipelineJob, "job")
        assert job.status == "COMPLETED" and job.result_metadata["preview"]["status"] == "ready"
        assert session.query(PipelineFile).filter_by(file_type="preview").count() == 1
    assert "preview.wav" not in removed
    assert len(calls) == 1


def test_memory_missing_final_mirror_failure_preserves_unavailable(
    memory_publication,
    monkeypatch,
):
    preview_service, factory, calls, removed = memory_publication
    with factory() as session:
        session.query(PipelineFile).delete()
        session.commit()

    def fail_sync(*args):
        raise OSError("metadata mirror unavailable")

    monkeypatch.setattr(preview_service, "_sync_metadata", fail_sync)
    preview_service.run("job")
    preview_service.run("job")
    with factory() as session:
        job = session.get(PipelineJob, "job")
        assert job.status == "COMPLETED" and job.result_metadata["success"] is True
        assert job.result_metadata["preview"]["status"] == "unavailable"
        assert session.query(PipelineFile).count() == 0
    assert calls == [] and removed == []


def test_sqlite_missing_final_mirror_failure_preserves_unavailable(tmp_path, monkeypatch):
    database = tmp_path / "preview.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    PipelineJob.__table__.create(engine)
    PipelineFile.__table__.create(engine)
    factory = sessionmaker(engine)
    storage = SimpleNamespace(root=tmp_path, pipeline_dir=tmp_path / "pipelines")
    with factory() as session:
        session.add(
            PipelineJob(
                id="missing-final",
                voice_profile_id="voice",
                status="COMPLETED",
                current_step="completed",
                prompt="synthetic",
                duration_seconds=1,
                pipeline_version="test",
                result_metadata={"preview": {"status": "pending"}},
            )
        )
        session.commit()
    preview_service = PipelinePreviewService(factory, storage)
    mirrored_statuses = []

    def fail_sync(job_id, metadata):
        mirrored_statuses.append(metadata["preview"]["status"])
        raise OSError("metadata mirror unavailable")

    monkeypatch.setattr(preview_service, "_sync_metadata", fail_sync)
    preview_service.run("missing-final")
    engine.dispose()
    # Reopen the persisted SQLite file, then verify rerun leaves unavailable alone.
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    factory = sessionmaker(engine)
    restarted = PipelinePreviewService(factory, storage)
    monkeypatch.setattr(restarted, "_sync_metadata", fail_sync)
    restarted.run("missing-final")
    with factory() as session:
        job = session.get(PipelineJob, "missing-final")
        assert job.status == "COMPLETED"
        assert job.result_metadata["preview"]["status"] == "unavailable"
        assert session.query(PipelineFile).count() == 0
    assert mirrored_statuses == ["unavailable"]
    engine.dispose()


@pytest.mark.parametrize(
    "preview",
    [
        "ready",
        ["ready"],
        7,
        None,
        {},
        {"status": "unknown"},
        {"status": ["ready"]},
        {"status": None},
    ],
)
def test_malformed_preview_metadata_file_apis(client, preview):
    storage = client.app.state.storage
    directory = storage.pipeline_dir / "malformed-preview"
    directory.mkdir()
    final = directory / "final.wav"
    wavfile.write(final, 8000, np.zeros(8000, np.int16))
    original_hash = hashlib.sha256(final.read_bytes()).digest()
    with client.app.state.session_factory() as session:
        session.add(
            PipelineJob(
                id="malformed-preview",
                voice_profile_id=create_profile(client),
                status="COMPLETED",
                current_step="completed",
                prompt="synthetic",
                duration_seconds=1,
                pipeline_version="test",
                result_metadata={"preview": preview},
            )
        )
        item = PipelineFile(
            id="malformed-preview-file",
            job_id="malformed-preview",
            file_type="preview",
            mime_type="audio/wav",
            file_path=storage.relative_path(final),
        )
        session.add(item)
        session.commit()
    base = "/api/pipelines/malformed-preview"
    assert client.get(base).status_code == 200
    response = client.get(base + "/files")
    assert response.status_code == 200
    row = response.json()[0]
    assert row["content_available"] is False and row["download_available"] is False
    assert row["content_url"] is None and row["download_url"] is None
    assert "file_path" not in row
    for action in ("content", "download"):
        response = client.get(base + "/files/malformed-preview-file/" + action)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "FILE_CONTENT_UNAVAILABLE"
    assert hashlib.sha256(final.read_bytes()).digest() == original_hash
    with client.app.state.session_factory() as session:
        assert session.get(PipelineJob, "malformed-preview").status == "COMPLETED"


def test_memory_db_outage_retains_pending_for_recovery(memory_publication, monkeypatch):
    preview_service, factory, calls, _ = memory_publication
    with monkeypatch.context() as patch:

        def fail_commit(session):
            raise RuntimeError("DB unavailable")

        patch.setattr(Session, "commit", fail_commit)
        preview_service.run("job")
    with factory() as session:
        job = session.get(PipelineJob, "job")
        assert job.status == "COMPLETED"
        assert job.result_metadata["preview"]["status"] == "pending"
        assert session.query(PipelineFile).filter_by(file_type="preview").count() == 0
    preview_service.run("job")
    assert len(calls) == 2
    with factory() as session:
        assert session.get(PipelineJob, "job").result_metadata["preview"]["status"] == "ready"


@pytest.mark.parametrize("scenario", ["success", "cancel", "preview_exception"])
def test_memory_worker_analysis_completion_and_preview_boundary(
    memory_publication,
    monkeypatch,
    scenario,
):
    preview_service, factory, _, removed = memory_publication
    events = []
    with factory() as session:
        session.query(PipelineFile).delete()
        job = session.get(PipelineJob, "job")
        job.status = "PENDING"
        job.result_metadata = {}
        session.commit()
    storage = preview_service.storage
    storage.resolve_voice_reference = lambda _: storage.root / "synthetic-reference.wav"
    monkeypatch.setattr(Path, "is_file", lambda _: True)
    monkeypatch.setattr(
        PipelineRepository,
        "get_profile",
        lambda *_: SimpleNamespace(
            consent_confirmed=True,
            reference_file_path="synthetic-reference.wav",
        ),
    )

    def execute(context, *_):
        events.append("final")
        context.output_file = storage.pipeline_dir / "job/final.wav"

    def analyze(name, result):
        def run(*args, **kwargs):
            with factory() as session:
                job = session.get(PipelineJob, "job")
                assert job.status != "COMPLETED"
                if name == "hook" and scenario == "cancel":
                    PipelineRepository(session).request_cancel(job)
            events.append(name)
            return result

        return SimpleNamespace(analyze=run)

    worker = PipelineWorker(
        factory,
        SimpleNamespace(execute=execute),
        storage,
        analyze("quality", AudioAnalysisResult.failed()),
        analyze("tempo", TempoAnalysisResult.pending(None)),
        analyze("hook", HookAnalysisResult.pending()),
    )
    monkeypatch.setattr(
        worker, "_write_metadata", lambda *_: storage.pipeline_dir / "job/metadata.json"
    )

    def postprocess(job_id):
        with factory() as session:
            job = session.get(PipelineJob, job_id)
            assert job.status == "COMPLETED"
            assert job.result_metadata["preview"]["status"] == "pending"
            assert "audio_analysis" in job.result_metadata
        events.append("preview")
        if scenario == "preview_exception":
            raise RuntimeError("Post-success exception")
        preview_service.run(job_id)

    monkeypatch.setattr(worker.preview_service, "run", postprocess)
    worker.run("job")
    assert events[:4] == ["final", "quality", "tempo", "hook"]
    with factory() as session:
        job = session.get(PipelineJob, "job")
        if scenario == "cancel":
            assert job.status == "CANCELLED" and "preview" not in events
            assert session.query(PipelineFile).count() == 0
            assert "final.wav" in removed
        else:
            assert job.status == "COMPLETED" and events[-1] == "preview"
            assert "final.wav" not in removed
            assert job.result_metadata["preview"]["status"] == (
                "ready" if scenario == "success" else "pending"
            )


def wait_preview(client, job_id):
    for _ in range(500):
        job = client.get(f"/api/pipelines/{job_id}").json()
        if (
            job["status"] == "COMPLETED"
            and job["result_metadata"]["preview"]["status"] != "pending"
        ):
            return job
        time.sleep(0.01)
    raise AssertionError("Preview did not finish")


def service(client):
    return PipelinePreviewService(client.app.state.session_factory, client.app.state.storage)


def test_publication_recovery_duplicate_range_and_metadata_repair(client):
    job_id = create_pipeline(client, create_profile(client))["id"]
    assert wait_preview(client, job_id)["result_metadata"]["preview"]["status"] == "ready"
    preview_service = service(client)
    with client.app.state.session_factory() as session:
        job = session.get(PipelineJob, job_id)
        files = list(session.query(PipelineFile).filter_by(job_id=job_id))
        final = next(item for item in files if item.file_type == "final")
        preview = next(item for item in files if item.file_type == "preview")
        source = client.app.state.storage.root / final.file_path
        preview_path = client.app.state.storage.root / preview.file_path
        original_hash = hashlib.sha256(source.read_bytes()).digest()
        preview_hash = hashlib.sha256(preview_path.read_bytes()).digest()
        # Simulate termination after file rename but before inventory commit.
        session.delete(preview)
        job.result_metadata = {
            **job.result_metadata,
            "preview": {"status": "pending", "version": "1.0"},
        }
        session.commit()
    assert job_id in preview_service.recoverable_ids()
    with ThreadPoolExecutor(2) as executor:
        list(executor.map(preview_service.run, [job_id, job_id]))
    assert hashlib.sha256(source.read_bytes()).digest() == original_hash
    assert hashlib.sha256(preview_path.read_bytes()).digest() == preview_hash
    metadata_path = source.parent / "metadata.json"
    metadata_path.write_text("{}", encoding="utf-8")
    preview_service.run(job_id)
    assert json.loads(metadata_path.read_text(encoding="utf-8"))["preview"]["status"] == "ready"
    files = client.get(f"/api/pipelines/{job_id}/files").json()
    previews = [item for item in files if item["file_type"] == "preview"]
    assert len(previews) == 1 and "file_path" not in previews[0]
    response = client.get(previews[0]["content_url"], headers={"Range": "bytes=0-11"})
    assert response.status_code == 206
    assert response.content[:4] == b"RIFF" and response.content[8:12] == b"WAVE"
    assert response.headers["cache-control"] == "private, no-store"
    assert client.get(previews[0]["download_url"]).status_code == 200


@pytest.mark.parametrize("failure", ["render", "registration"])
def test_preview_failure_isolated_and_cleanup(client, monkeypatch, failure):
    if failure == "render":

        def fail(*args):
            raise OSError("synthetic failure")

        monkeypatch.setattr("backend.services.pipeline_preview_service.render_preview", fail)
    else:
        original_commit = Session.commit

        def commit(session):
            if any(
                isinstance(row, PipelineFile) and row.file_type == "preview" for row in session.new
            ):
                raise RuntimeError("synthetic DB registration failure")
            return original_commit(session)

        monkeypatch.setattr(Session, "commit", commit)
    job_id = create_pipeline(client, create_profile(client))["id"]
    completed = wait_preview(client, job_id)
    assert completed["status"] == "COMPLETED"
    assert completed["result_metadata"]["preview"]["status"] == "failed"
    files = client.get(f"/api/pipelines/{job_id}/files").json()
    final = next(item for item in files if item["file_type"] == "final")
    assert client.get(final["content_url"]).status_code == 200
    assert not any(item["file_type"] == "preview" for item in files)
    directory = client.app.state.storage.pipeline_dir / job_id
    assert not list(directory.glob("preview*.wav"))


def test_legacy_completed_result_is_not_regenerated(client):
    job_id = create_pipeline(client, create_profile(client))["id"]
    wait_preview(client, job_id)
    with client.app.state.session_factory() as session:
        job = session.get(PipelineJob, job_id)
        metadata = dict(job.result_metadata)
        metadata.pop("preview")
        job.result_metadata = metadata
        session.commit()
    service(client).run(job_id)
    assert "preview" not in client.get(f"/api/pipelines/{job_id}").json()["result_metadata"]


def test_file_metadata_sync_failure_keeps_ready_and_repairs(client, monkeypatch):
    preview_service = service(client)
    original_sync = PipelinePreviewService._sync_metadata
    failures = []

    def fail_sync(*args):
        failures.append(True)
        raise OSError("synthetic metadata.json write failure")

    monkeypatch.setattr(PipelinePreviewService, "_sync_metadata", fail_sync)
    job_id = create_pipeline(client, create_profile(client))["id"]
    assert wait_preview(client, job_id)["result_metadata"]["preview"]["status"] == "ready"
    deadline = time.monotonic() + 5
    while not failures and time.monotonic() < deadline:
        time.sleep(0.01)
    assert failures
    files = client.get(f"/api/pipelines/{job_id}/files").json()
    preview = next(row for row in files if row["file_type"] == "preview")
    assert client.get(preview["content_url"]).status_code == 200
    monkeypatch.setattr(PipelinePreviewService, "_sync_metadata", original_sync)
    preview_service.run(job_id)
    path = client.app.state.storage.pipeline_dir / job_id / "metadata.json"
    assert json.loads(path.read_text(encoding="utf-8"))["preview"]["status"] == "ready"
    assert client.get(f"/api/pipelines/{job_id}").json()["status"] == "COMPLETED"


def test_pending_preview_recovers_on_application_restart(app, monkeypatch):
    with TestClient(app) as first:
        # Leave durable pending after the success boundary, before postprocessing.
        monkeypatch.setattr(app.state.pipeline_worker.preview_service, "run", lambda *_: None)
        job_id = create_pipeline(first, create_profile(first))["id"]
        for _ in range(500):
            job = first.get(f"/api/pipelines/{job_id}").json()
            if job["status"] == "COMPLETED":
                break
            time.sleep(0.01)
        assert job["status"] == "COMPLETED"
        assert job["result_metadata"]["preview"]["status"] == "pending"
        source = app.state.storage.pipeline_dir / job_id / "final.wav"
        original_hash = hashlib.sha256(source.read_bytes()).digest()
        settings = app.state.settings
    # Recreate workers/dispatcher/DB sessions while preserving the real SQLite/WAV files.
    with TestClient(create_app(settings)) as restarted:
        completed = wait_preview(restarted, job_id)
        assert completed["status"] == "COMPLETED"
        assert completed["result_metadata"]["preview"]["status"] == "ready"
        files = restarted.get(f"/api/pipelines/{job_id}/files").json()
        assert len([row for row in files if row["file_type"] == "preview"]) == 1
        assert hashlib.sha256(source.read_bytes()).digest() == original_hash
