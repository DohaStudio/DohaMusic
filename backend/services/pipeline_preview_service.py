"""Recoverable preview publication. DB metadata is the authoritative result."""

import json
import os
import tempfile
import wave
from pathlib import Path

from sqlalchemy import select, update

from backend.audio_analysis.preview import render_preview
from backend.core.logging import get_logger
from backend.models.pipeline_file import PipelineFile
from backend.models.pipeline_job import PipelineJob
from backend.repositories.pipeline_repository import PipelineRepository

logger = get_logger(__name__)


def _preview_status(metadata):
    preview = metadata.get("preview") if isinstance(metadata, dict) else None
    status = preview.get("status") if isinstance(preview, dict) else None
    return status if isinstance(status, str) else None


class PipelinePreviewService:
    def __init__(self, session_factory, storage):
        self.session_factory = session_factory
        self.storage = storage

    def recoverable_ids(self):
        with self.session_factory() as session:
            return [
                job.id
                for job in session.scalars(
                    select(PipelineJob).where(PipelineJob.status == "COMPLETED")
                )
                if _preview_status(job.result_metadata) in {"pending", "ready"}
            ]

    def run(self, job_id: str) -> None:
        generated = None
        temporary = None
        published = False
        try:
            with self.session_factory() as session:
                # A write lock serializes publication for this DB, including SQLite.
                # Keep this transaction until both inventory and ready metadata commit.
                result = session.execute(
                    update(PipelineJob)
                    .where(PipelineJob.id == job_id, PipelineJob.status == "COMPLETED")
                    .values(status="COMPLETED")
                )
                if result.rowcount != 1:
                    session.rollback()
                    return
                repository = PipelineRepository(session)
                job = repository.get(job_id)
                session.refresh(job)
                if _preview_status(job.result_metadata) not in {"pending", "ready"}:
                    session.rollback()
                    return
                metadata = dict(job.result_metadata)
                preview = metadata["preview"]
                # Reuse the exact existing secure file validation boundary.
                from backend.services.pipeline_service import PipelineService

                access = PipelineService(self.session_factory, None, "", self.storage)
                rows = repository.list_files(job_id)
                existing = next((row for row in rows if row.file_type == "preview"), None)
                if preview.get("status") == "ready" and existing is not None:
                    path, _ = access._validate_file(existing)
                    if path.parent != (self.storage.pipeline_dir / job_id).resolve():
                        raise ValueError("Preview must belong to job directory")
                    with wave.open(str(path), "rb") as audio:
                        if (
                            preview.get("version") != "1.0"
                            or audio.getsampwidth() != 2
                            or audio.getnframes() <= 0
                            or audio.getframerate() != preview.get("sample_rate")
                            or audio.getnchannels() != preview.get("channels")
                            or audio.getnframes() / audio.getframerate()
                            != preview.get("duration_seconds")
                            or len(audio.readframes(audio.getnframes()))
                            != audio.getnframes() * audio.getnchannels() * 2
                        ):
                            raise ValueError("Invalid ready preview")
                    session.commit()
                    published = True
                else:
                    final = next((row for row in rows if row.file_type == "final"), None)
                    if final is None:
                        metadata["preview"] = {"version": "1.0", "status": "unavailable"}
                        repository.set_metadata(job, metadata)
                    else:
                        source, _ = access._validate_file(final)
                        expected = (self.storage.pipeline_dir / job_id).resolve()
                        if source.parent != expected:
                            raise ValueError("Final WAV must belong to the job directory")
                        # Temporary WAVs use a reserved prefix and are never registered.
                        # The DB write lock excludes other preview writers for this job.
                        for abandoned in source.parent.glob("preview-*.wav"):
                            if abandoned.is_file() and not abandoned.is_symlink():
                                abandoned.unlink()
                        destination = source.parent / "preview.wav"
                        if destination.is_symlink() or destination.resolve() == source.resolve():
                            raise ValueError("Unsafe preview destination")
                        descriptor, name = tempfile.mkstemp(
                            prefix="preview-", suffix=".wav", dir=source.parent
                        )
                        os.close(descriptor)
                        temporary = Path(name)
                        analysis = metadata.get("audio_analysis")
                        hook = analysis.get("hook") if isinstance(analysis, dict) else None
                        metadata["preview"] = render_preview(source, temporary, hook)
                        temporary.replace(destination)
                        temporary = None
                        generated = destination
                        if existing is None:
                            session.add(PipelineFile(
                                job_id=job_id, file_type="preview",
                                file_path=self.storage.relative_path(destination),
                                mime_type="audio/wav",
                            ))
                        else:
                            existing.file_path = self.storage.relative_path(destination)
                            existing.mime_type = "audio/wav"
                        job.result_metadata = metadata
                        session.commit()
                        generated = None
                        published = True
                self._sync_metadata(job_id, metadata)
        except Exception:
            logger.exception("pipeline_preview_failed job_id=%s", job_id)
            try:
                with self.session_factory() as session:
                    session.execute(
                        update(PipelineJob)
                        .where(PipelineJob.id == job_id, PipelineJob.status == "COMPLETED")
                        .values(status="COMPLETED")
                    )
                    repository = PipelineRepository(session)
                    job = repository.get(job_id)
                    if job is not None and job.status == "COMPLETED":
                        metadata = dict(job.result_metadata)
                        concurrently_ready = (
                            generated is not None and _preview_status(metadata) == "ready"
                        )
                        if not published and not concurrently_ready:
                            if generated is not None:
                                try:
                                    generated.unlink(missing_ok=True)
                                except OSError:
                                    logger.exception(
                                        "pipeline_preview_cleanup_failed job_id=%s", job_id
                                    )
                            metadata["preview"] = {"version": "1.0", "status": "failed"}
                            repository.set_metadata(job, metadata)
                            self._sync_metadata(job_id, metadata)
            except Exception:
                logger.exception("pipeline_preview_failure_save_failed job_id=%s", job_id)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    logger.exception("pipeline_preview_temporary_cleanup_failed job_id=%s", job_id)

    def _sync_metadata(self, job_id, metadata):
        directory = self.storage.pipeline_dir / job_id
        destination = directory / "metadata.json"
        directory.relative_to(self.storage.root)
        if directory.resolve().parent != self.storage.pipeline_dir.resolve():
            raise ValueError("Unsafe metadata directory")
        current = destination
        while current != self.storage.root:
            if current.is_symlink():
                raise ValueError("Unsafe metadata destination")
            current = current.parent
        descriptor, name = tempfile.mkstemp(prefix="metadata-", suffix=".json", dir=directory)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(metadata, output, ensure_ascii=False, indent=2)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
