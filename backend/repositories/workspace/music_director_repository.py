from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.models.workspace.music_director import (
    MusicDirectorCandidate,
    MusicDirectorCandidateMaterialization,
    MusicDirectorRun,
)


class MusicDirectorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_run_for_job(self, job_id: UUID) -> MusicDirectorRun | None:
        return self._session.scalar(
            select(MusicDirectorRun).where(MusicDirectorRun.job_id == job_id)
        )

    def add(self, run: MusicDirectorRun, candidates: list[MusicDirectorCandidate]) -> None:
        self._session.add(run)
        self._session.add_all(candidates)

    def add_run(self, run: MusicDirectorRun) -> None:
        self._session.add(run)
        self._session.flush()

    def add_candidates(self, candidates: list[MusicDirectorCandidate]) -> None:
        self._session.add_all(candidates)
        self._session.flush()

    def list_candidates(self, run_id: UUID) -> list[MusicDirectorCandidate]:
        statement = (
            select(MusicDirectorCandidate)
            .where(MusicDirectorCandidate.run_id == run_id)
            .order_by(MusicDirectorCandidate.ordinal)
        )
        return list(self._session.scalars(statement))

    def get_run(self, run_id: UUID) -> MusicDirectorRun | None:
        return self._session.get(MusicDirectorRun, run_id)

    def get_candidate(self, candidate_id: UUID) -> MusicDirectorCandidate | None:
        return self._session.get(MusicDirectorCandidate, candidate_id)

    def select_candidate(self, *, run_id: UUID, candidate_id: UUID, expected_version: int) -> bool:
        result = self._session.execute(
            update(MusicDirectorRun)
            .where(
                MusicDirectorRun.run_id == run_id,
                MusicDirectorRun.version == expected_version,
            )
            .values(selected_candidate_id=candidate_id, version=expected_version + 1)
        )
        return result.rowcount == 1

    def apply_candidate(
        self,
        *,
        run_id: UUID,
        candidate_id: UUID,
        expected_version: int,
        applied_working_revision: int,
    ) -> bool:
        candidate = self._session.execute(
            update(MusicDirectorCandidate)
            .where(
                MusicDirectorCandidate.run_id == run_id,
                MusicDirectorCandidate.candidate_id == candidate_id,
                MusicDirectorCandidate.status == "generated",
            )
            .values(status="applied")
        )
        if candidate.rowcount != 1:
            return False
        run = self._session.execute(
            update(MusicDirectorRun)
            .where(
                MusicDirectorRun.run_id == run_id,
                MusicDirectorRun.version == expected_version,
                MusicDirectorRun.selected_candidate_id == candidate_id,
                MusicDirectorRun.applied_candidate_id.is_(None),
            )
            .values(
                applied_candidate_id=candidate_id,
                applied_working_revision=applied_working_revision,
                version=expected_version + 1,
            )
        )
        return run.rowcount == 1

    def transition_candidate_status(
        self, *, candidate_id: UUID, from_status: str, to_status: str
    ) -> bool:
        result = self._session.execute(
            update(MusicDirectorCandidate)
            .where(
                MusicDirectorCandidate.candidate_id == candidate_id,
                MusicDirectorCandidate.status == from_status,
            )
            .values(status=to_status)
        )
        return result.rowcount == 1

    def get_materialization(
        self, job_id: UUID, ordinal: int
    ) -> MusicDirectorCandidateMaterialization | None:
        return self._session.scalar(
            select(MusicDirectorCandidateMaterialization).where(
                MusicDirectorCandidateMaterialization.job_id == job_id,
                MusicDirectorCandidateMaterialization.ordinal == ordinal,
            )
        )

    def list_materializations(self, job_id: UUID) -> list[MusicDirectorCandidateMaterialization]:
        return list(
            self._session.scalars(
                select(MusicDirectorCandidateMaterialization)
                .where(MusicDirectorCandidateMaterialization.job_id == job_id)
                .order_by(MusicDirectorCandidateMaterialization.ordinal)
            )
        )

    def add_materializations(self, items: list[MusicDirectorCandidateMaterialization]) -> None:
        self._session.add_all(items)
        self._session.flush()
