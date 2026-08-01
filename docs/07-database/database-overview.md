# 데이터베이스 개요

> 문서 목적: 현재 영속 계층과 교체 경계를 정의한다.
> 현재 상태: **SQLite/SQLAlchemy/Alembic 구현 완료**

현재 기본 DB는 `backend/storage/doha_music.db`의 SQLite다. 연결 문자열은 `DATABASE_URL` 환경 변수로 변경할 수 있으며 Repository Pattern을 통해 Service와 Worker가 특정 DB 구현에 직접 의존하지 않도록 구성했다.

SQLAlchemy 2.x ORM을 사용하고 Alembic이 스키마 버전을 관리한다. 애플리케이션 시작 시 `head`까지 마이그레이션하며, 수동 실행은 다음 명령을 사용한다.

```bash
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini current
```

현재 테이블은 기존 생성·Stem·Voice Profile·Voice Conversion·Pipeline 9개, 독립형 `lyrics_documents`, F6의 `voice_enrollments`·`voice_samples`·`idempotency_records`를 포함한 13개다. Stem Job은 입력 generated file을, Voice Conversion Job은 vocals Stem과 동의된 Voice Profile을 참조한다. Pipeline Job은 동의된 Voice Profile과 요청·진행률·결과 metadata를 보존한다. Lyrics는 로컬 Template·Mock Provider가 짧게 동기 실행되므로 Job 테이블 없이 요청·섹션·본문·Provider·검증 metadata를 보존한다. PostgreSQL 또는 MySQL 전환은 실제 운영 요구를 확인한 뒤 별도 검증하며, 현재 스키마에는 벤더 전용 타입이나 SQL을 사용하지 않는다.

Pipeline 필드와 보존 규칙은 [Pipeline 테이블](pipeline-tables.md)을 따른다. Alembic head `20260801_0010`은 F6의 `VoiceEnrollment`·`VoiceSample`과 Profile active reference를 영속 계층에 추가했다. API·Storage·정규화·cleanup 실행기는 아직 미구현이며 상세 경계는 [Voice Enrollment 데이터 모델](voice-enrollment-data-model.md)을 따른다.
# Phase 6.5 변경

Alembic `20260729_0006`은 `lyrics_documents`에 self-reference parent, version, revision instruction, 전후 SHA-256을 추가한다. Provider 응답은 검증 후 새 row로만 저장되며 기존 버전은 불변이다.
