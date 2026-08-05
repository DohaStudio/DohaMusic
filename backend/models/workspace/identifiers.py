"""Workspace 목표 Entity에서 사용하는 식별자 생성기."""

from __future__ import annotations

from uuid import UUID, uuid4


def generate_uuid() -> UUID:
    """현재 UUID4 식별자를 생성한다.

    호출부가 UUID 구현에 직접 의존하지 않도록 분리해 향후 UUIDv7 전환 지점을
    한곳으로 제한한다.
    """

    return uuid4()
