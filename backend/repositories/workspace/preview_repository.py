"""Working preview Asset binding and immutable manifest persistence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.workspace.preview import (
    WorkingPreviewAsset,
    WorkingPreviewRender,
    WorkingPreviewRenderClip,
    WorkingPreviewRenderTrack,
)


class WorkingPreviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_asset_binding(self, project_id: UUID) -> WorkingPreviewAsset | None:
        return self.session.get(WorkingPreviewAsset, project_id)

    def add_asset_binding(self, binding: WorkingPreviewAsset) -> WorkingPreviewAsset:
        self.session.add(binding)
        self.session.flush()
        return binding

    def add_render(self, render: WorkingPreviewRender) -> WorkingPreviewRender:
        self.session.add(render)
        self.session.flush()
        return render

    def add_tracks(self, tracks: list[WorkingPreviewRenderTrack]) -> None:
        self.session.add_all(tracks)
        self.session.flush()

    def add_clips(self, clips: list[WorkingPreviewRenderClip]) -> None:
        self.session.add_all(clips)
        self.session.flush()

    def get_render(self, preview_render_id: UUID) -> WorkingPreviewRender | None:
        return self.session.get(WorkingPreviewRender, preview_render_id)

    def get_render_for_job(self, job_id: UUID) -> WorkingPreviewRender | None:
        return self.session.scalar(
            select(WorkingPreviewRender).where(WorkingPreviewRender.workspace_job_id == job_id)
        )

    def list_tracks(self, preview_render_id: UUID) -> list[WorkingPreviewRenderTrack]:
        return list(
            self.session.scalars(
                select(WorkingPreviewRenderTrack)
                .where(WorkingPreviewRenderTrack.preview_render_id == preview_render_id)
                .order_by(WorkingPreviewRenderTrack.track_order, WorkingPreviewRenderTrack.track_id)
            )
        )

    def list_clips(self, preview_render_id: UUID) -> list[WorkingPreviewRenderClip]:
        return list(
            self.session.scalars(
                select(WorkingPreviewRenderClip)
                .where(WorkingPreviewRenderClip.preview_render_id == preview_render_id)
                .order_by(
                    WorkingPreviewRenderClip.canonical_order, WorkingPreviewRenderClip.clip_id
                )
            )
        )

    def attach_asset_version(self, preview_render_id: UUID, asset_version_id: UUID) -> None:
        render = self.get_render(preview_render_id)
        if render is None or render.preview_asset_version_id is not None:
            raise ValueError("WORKING_PREVIEW_VERSION_CONFLICT")
        render.preview_asset_version_id = asset_version_id
        self.session.flush()

    def list_due_completed(self, now: datetime, *, limit: int = 100) -> list[WorkingPreviewRender]:
        return list(
            self.session.scalars(
                select(WorkingPreviewRender)
                .where(
                    WorkingPreviewRender.preview_asset_version_id.is_not(None),
                    WorkingPreviewRender.payload_expires_at <= now,
                )
                .order_by(
                    WorkingPreviewRender.payload_expires_at,
                    WorkingPreviewRender.preview_render_id,
                )
                .limit(limit)
            )
        )
