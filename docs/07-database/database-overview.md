# 데이터베이스 문서 개요

> 문서 상태: [운영 기준]
> 문서 역할: CURRENT Runtime·CURRENT Workspace/Domain·TARGET·TRANSITION 문서의 Canonical entry point
> 최종 수정일: 2026-08-25

현재 기본 DB는 `backend/storage/doha_music.db`의 SQLite다. 연결 문자열은 `DATABASE_URL` 환경 변수로 변경할 수 있으며 Repository Pattern을 통해 Service와 Worker가 특정 DB 구현에 직접 의존하지 않도록 구성했다.

SQLAlchemy 2.x ORM을 사용하고 Alembic이 스키마 버전을 관리한다. 소스 head는 durable PayloadLocator persistence foundation을 추가한 `20260825_0023`이고 실제 사용자 DB는 `20260810_0017`이다. 애플리케이션 startup의 자동 Migration은 기본 비활성화이며 `DOHAMUSIC_AUTO_MIGRATE=true`를 명시한 경우에만 기존 `upgrade head`를 실행한다. 사용자 DB에는 opt-in을 사용하지 않고 [Workspace DB Migration Runbook](../10-operations/workspace-db-migration-runbook.md)의 승인 절차를 따른다.

승인 전에는 기본 URL로 `upgrade head`를 실행하지 않습니다. revision 확인과 실제 적용 명령은 Runbook의 경로 확인·backup·FK Gate를 통과한 실행 기록에서만 사용합니다.

## 문서 구조와 현재 판정

```text
Database Documentation
├─ CURRENT Runtime — 기존 제품 실행의 운영 source of truth
├─ CURRENT Workspace/Domain — 실제 추가된 Entity·Table·Index와 구현된 Service/API
├─ TARGET — Workspace schema를 제품 실행의 source of truth로 사용하는 목표 상태
└─ TRANSITION — backfill·dual write·read 전환·Legacy 제거 전략
```

| 구분 | 실제 범위 | 현재 판정 | 상세 Authority |
|---|---|---|---|
| CURRENT Runtime | 기능별 Runtime Table 14개 | 운영 source of truth | [CURRENT Runtime ERD](erd.md), [CURRENT Runtime Core Table Definition](table-definition.md), [Pipeline Table](pipeline-tables.md), [Voice Conversion Table](voice-conversion-tables.md) |
| CURRENT Workspace/Domain | source Workspace 도메인 Entity/Table 29개와 내부 Storage Catalog 1개 | selection·Provider binding·PayloadLocator·Clip persistence Table을 포함한 ORM과 additive source schema가 구현됨. 실제 사용자 DB는 21개 Workspace Table이며 기존 Runtime을 대체하지 않음 | [Workspace DB 구현 상태](database-redesign-overview.md), [Workspace Table Definition](database-redesign-table-definition.md) |
| TARGET | Workspace·AssetVersion·Artifact·CompositionSnapshot·공통 Job 중심의 결과 소유권 | 물리 schema는 부분 구현됐지만 backfill·dual write·Runtime read 전환은 미구현 | [TARGET ERD](database-redesign-erd.md), [TARGET 논리 구조](database-redesign-overview.md) |
| TRANSITION | CURRENT Runtime에서 Workspace 중심 source of truth로 단계적 전환 | source revision `0023`, 실제 DB `0017`; selection·binding·Clip·duration·idempotency result·locator migration과 데이터·Runtime 전환 미적용 | [Migration 전략](database-redesign-migration-strategy.md) |

## 숫자 계산 기준

서로 다른 범위의 숫자를 같은 “전체 테이블 수”로 비교하지 않는다.

| 계산 범위 | 수 | 근거 |
|---|---:|---|
| Runtime application tables | 14 | `backend/models/`의 Workspace 외 `__tablename__` 14개. 현재 제품 실행 source of truth |
| Workspace domain entities/tables | source 29 / 실제 DB 21 | 기존 21개, `ProjectCompositionSelection`, `ProviderJobBinding`, `PayloadLocator`, Clip persistence 5개 table |
| Workspace storage catalog | 1 | `ArtifactStorageLocation` / `artifact_storage_locations`, revision `20260809_0016` |
| Application metadata tables | source 44 / 실제 DB 36 | Runtime 14 + Workspace domain source 29(실제 21) + Catalog 1 |

`20260807_0013`~`0015`는 신규 Table이 아니라 keyset Index를 추가하고 `20260810_0017`은 Workspace Job Column·Index를 추가한다. source `0018`은 selection, `0019`는 Provider binding, `0020`은 Clip persistence 5개 table, `0021`은 nullable `artifacts.duration_us`, `0022`는 idempotency completion result Column 4개, `0023`은 `payload_locators` table과 binding scope index를 추가하며 `0018` 이후는 실제 사용자 DB에 적용하지 않았다.

## CURRENT Runtime DB — 14개 Table

| 책임 | Table |
|---|---|
| Music Generation | `generation_jobs`, `generated_files` |
| Stem Separation | `stem_jobs`, `stem_files` |
| Voice Conversion | `voice_conversion_jobs`, `voice_conversion_files` |
| Pipeline | `pipeline_jobs`, `pipeline_files` |
| Lyrics | `lyrics_documents` |
| Project | `projects` |
| Voice Profile·Enrollment | `voice_profiles`, `voice_enrollments`, `voice_samples` |
| API idempotency | `idempotency_records` |

[CURRENT Runtime Core Table Definition](table-definition.md)은 이 중 공통·Generation·Stem·Lyrics·Project·Voice Profile/Enrollment 10개를 정의한다. Pipeline 2개와 Voice Conversion 2개는 각각의 상세 문서가 Authority다. [CURRENT Runtime ERD](erd.md)는 세 문서를 합친 14개 Runtime 관계만 나타낸다.

Stem Job은 입력 generated file을, Voice Conversion Job은 vocals Stem과 동의된 Voice Profile을 참조한다. Pipeline Job은 동의된 Voice Profile과 요청·진행률·결과 metadata를 보존한다. Lyrics는 로컬 Template·Mock Provider가 짧게 동기 실행되므로 Job 테이블 없이 요청·섹션·본문·Provider·검증 metadata를 보존한다. PostgreSQL 또는 MySQL 전환은 실제 운영 요구를 확인한 뒤 별도 검증하며, 현재 스키마에는 벤더 전용 타입이나 SQL을 사용하지 않는다.

## CURRENT Workspace/Domain DB와 TARGET — [부분 구현]

DohaStudio Common Specification을 기준으로 source Entity 29개와 별도 `ArtifactStorageLocation` Entity를 구현했다. source metadata는 `20260825_0023` 기준 44개 Application Table이고 실제 사용자 DB는 `20260810_0017` 기준 36개다. `0021`과 `0022`는 Table 수를 늘리지 않고 각각 nullable trusted Artifact duration과 versioned idempotency completion result를 추가하고 `0023`은 PayloadLocator table 1개를 추가한다. Workspace Resource API 30개와 별도 D1 product aggregate API 2개, Job API 5개도 구현했다.

이 구조는 물리 schema와 일부 Application 계층에서는 CURRENT다. 그러나 신규 Workspace Table backfill·dual write·Runtime read 전환과 Legacy 동결·제거는 수행하지 않았으므로 제품 실행의 source of truth라는 의미에서는 여전히 TARGET이다. Provider dispatch wiring과 background daemon도 미구현이며 현행 Runtime Table 14개를 변경하거나 제거하지 않는다.

- [재설계 개요](database-redesign-overview.md)
- [TARGET ERD](database-redesign-erd.md)
- [TARGET Table Definition](database-redesign-table-definition.md)
- [Migration 전략](database-redesign-migration-strategy.md)
- [ADR-030](../11-decisions/ADR-030-asset-version-centric-database.md)
## Phase 6.5 변경

Alembic `20260729_0006`은 `lyrics_documents`에 self-reference parent, version, revision instruction, 전후 SHA-256을 추가한다. Provider 응답은 검증 후 새 row로만 저장되며 기존 버전은 불변이다.

DohaLM 공동 창작 연동에서 필요한 Project·Version·Generation·Analysis·Approval·ModelUsage·LicenseReview 분리는 아직 `[계획]`이며 현재 테이블 수나 migration head를 변경하지 않는다. 개념 관계와 현재 `lyrics_documents`의 전환 대안은 [가사 버전·승인 데이터 모델](lyrics-versioning-data-model.md)을 따른다.

## Workspace Artifact와 Composition Snapshot [진행 중]

`Asset`, `AssetVersion`, `Artifact`, `CompositionSnapshot`과 공통 `Job`은 목표 ORM과 `0012`~`0017` additive migration으로 실제 사용자 DB에 적용됐고 Runtime source of truth는 전환하지 않았다. source `0018`~`0023`은 구현·임시 DB 검증만 완료했다. `0020`은 Clip persistence를, `0021`은 기존 row를 `NULL`로 보존하는 trusted Artifact duration을, `0022`는 legacy row를 보존하는 revision-safe idempotency result를, `0023`은 durable PayloadLocator persistence foundation을 제공한다. CompositionSnapshot 공식 API 3개와 Job API 5개, D1 product API 2개를 유지한다. WorkingComposition public API와 mutation Service는 아직 없다.

Mix Asset, Export Asset, Preview, Snapshot과 실행 기록의 목표 도메인은 `DohaArtifacts/music`이다. Workspace DB의 Artifact에는 로컬 절대·상대 경로를 저장하지 않고, 내부 논리 URI는 `artifact://<artifact_id>`를 사용한다. 물리 위치는 별도 내부 `artifact_storage_locations` Catalog Table의 backend·domain·canonical storage key가 소유한다. Catalog Entity와 revision `20260809_0016`은 실제 사용자 DB에 적용했고 Catalog 조회·local Resolver·trusted ingestion, owner/retention read Gate·dry-run reconciliation과 Artifact Metadata·content·download·single-byte Range를 구현했다. 실제 Catalog row는 0개이며 destructive reconciliation은 미구현이다. 현재 `pipeline_jobs`, `pipeline_files`, `AUDIO_STORAGE_ROOT`와 Runtime source of truth는 변경하지 않는다. 세부 계약은 [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md), [Workspace Artifact 모델](../03-architecture/workspace-artifact-model.md)과 [ADR-032](../11-decisions/ADR-032-artifact-storage-resolver-integrity.md)을 따른다.
