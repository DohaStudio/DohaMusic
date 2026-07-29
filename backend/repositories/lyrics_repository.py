"""Lyrics document persistence operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.lyrics_document import LyricsDocument


class LyricsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, values: dict[str, object]) -> LyricsDocument:
        document = LyricsDocument(**values)
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    def get(self, lyrics_id: str) -> LyricsDocument | None:
        return self.session.get(LyricsDocument, lyrics_id)

    def has_children(self, lyrics_id: str) -> bool:
        statement = (
            select(LyricsDocument.id)
            .where(LyricsDocument.parent_id == lyrics_id)
            .limit(1)
        )
        return self.session.scalar(statement) is not None

    def update_metadata(
        self, document: LyricsDocument, metadata: dict[str, object]
    ) -> LyricsDocument:
        document.metadata_payload = metadata
        self.session.commit()
        self.session.refresh(document)
        return document

    def delete(self, document: LyricsDocument) -> None:
        self.session.delete(document)
        self.session.commit()
