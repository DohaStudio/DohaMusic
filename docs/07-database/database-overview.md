# 데이터베이스 개요

> 문서 목적: 현재 영속 계층과 교체 경계를 정의한다.
> 현재 상태: **SQLite/SQLAlchemy/Alembic 구현 완료**
> 최종 수정일: 2026-08-06

현재 기본 DB는 `backend/storage/doha_music.db`의 SQLite다. 연결 문자열은 `DATABASE_URL` 환경 변수로 변경할 수 있으며 Repository Pattern을 통해 Service와 Worker가 특정 DB 구현에 직접 의존하지 않도록 구성했다.

SQLAlchemy 2.x ORM을 사용하고 Alembic이 스키마 버전을 관리한다. 소스 기준 head는 `20260806_0012`지만 실제 사용자 DB 적용은 미수행이다. 애플리케이션 startup의 자동 Migration은 기본 비활성화이며 `DOHAMUSIC_AUTO_MIGRATE=true`를 명시한 경우에만 기존 `upgrade head`를 실행한다. 사용자 DB에는 opt-in을 사용하지 않고 [Workspace DB Migration Runbook](../10-operations/workspace-db-migration-runbook.md)의 승인 절차를 따른다.

승인 전에는 기본 URL로 `upgrade head`를 실행하지 않습니다. revision 확인과 실제 적용 명령은 Runbook의 경로 확인·backup·FK Gate를 통과한 실행 기록에서만 사용합니다.

현행 Runtime 계약은 기존 생성·Stem·Voice Profile·Voice Conversion·Pipeline 9개, 독립형 `lyrics_documents`와 `projects`, F6의 `voice_enrollments`·`voice_samples`·`idempotency_records`를 포함한 14개 Table이다. Stem Job은 입력 generated file을, Voice Conversion Job은 vocals Stem과 동의된 Voice Profile을 참조한다. Pipeline Job은 동의된 Voice Profile과 요청·진행률·결과 metadata를 보존한다. Lyrics는 로컬 Template·Mock Provider가 짧게 동기 실행되므로 Job 테이블 없이 요청·섹션·본문·Provider·검증 metadata를 보존한다. PostgreSQL 또는 MySQL 전환은 실제 운영 요구를 확인한 뒤 별도 검증하며, 현재 스키마에는 벤더 전용 타입이나 SQL을 사용하지 않는다.

Pipeline 필드와 보존 규칙은 [Pipeline 테이블](pipeline-tables.md)을 따른다. `20260801_0011`은 `voice_samples.quality_metrics`와 `idempotency_records`를 추가했고, 소스 head `20260806_0012`는 Workspace Table 21개만 additive하게 추가한다. 실제 사용자 DB가 여전히 `0011`인지 여부는 별도 승인된 read-only Inventory 전까지 확인되지 않았다.

## Asset 중심 목표 DB — [진행 중]

DohaStudio Common Specification을 기준으로 Workspace·MusicProject·Asset·AssetVersion·Artifact·CompositionSnapshot·Job 중심의 21개 Entity와 additive migration 파일을 구현했다. metadata는 총 35개 Table이며 실제 사용자 DB 적용, backfill과 Runtime 전환은 미수행이다. 현행 Runtime Table 14개를 변경하거나 제거하지 않는다.

- [재설계 개요](database-redesign-overview.md)
- [목표 ERD](database-redesign-erd.md)
- [목표 Table Definition](database-redesign-table-definition.md)
- [Migration 전략](database-redesign-migration-strategy.md)
- [ADR-030](../11-decisions/ADR-030-asset-version-centric-database.md)
# Phase 6.5 변경

Alembic `20260729_0006`은 `lyrics_documents`에 self-reference parent, version, revision instruction, 전후 SHA-256을 추가한다. Provider 응답은 검증 후 새 row로만 저장되며 기존 버전은 불변이다.

DohaLM 공동 창작 연동에서 필요한 Project·Version·Generation·Analysis·Approval·ModelUsage·LicenseReview 분리는 아직 `[계획]`이며 현재 테이블 수나 migration head를 변경하지 않는다. 개념 관계와 현재 `lyrics_documents`의 전환 대안은 [가사 버전·승인 데이터 모델](lyrics-versioning-data-model.md)을 따른다.

## Workspace Artifact와 Composition Snapshot [계획]

`Asset`, `AssetVersion`, `Artifact`, `CompositionSnapshot`과 공통 `Job`은 목표 ORM과 additive migration에 존재하지만 실제 사용자 DB와 Runtime에는 아직 적용되지 않았다. 목표 모델에서 Snapshot은 최신 Asset ID가 아니라 특정 Lyrics·Music·Vocal·Stem AssetVersion과 processing chain·mix settings·Provider·모델 버전을 불변으로 참조한다.

Mix Asset, Export Asset, Preview, Snapshot과 실행 기록의 목표 도메인은 `DohaArtifacts/music`이다. DB에는 로컬 절대 경로를 저장하지 않고 opaque Artifact ID 또는 향후 versioned URI만 저장한다. 현재 `pipeline_jobs`, `pipeline_files`, `AUDIO_STORAGE_ROOT`와 Runtime source of truth는 변경하지 않는다. 세부 계획은 [Workspace Artifact 모델](../03-architecture/workspace-artifact-model.md)과 [ADR-029](../11-decisions/ADR-029-dohamusic-workspace-artifact-domain.md)을 따른다.
