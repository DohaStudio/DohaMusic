# Artifact Storage Catalog 기반 검증 보고서

> 상태: [완료]
> 검증일: 2026-08-09
> 기준 브랜치: `feature/artifact-storage-catalog`
> 기준 develop commit: `9dd9ef7c5f463e9e38f43de074579815abc8bcc5`
> 관련 문서: [Artifact Storage 계약](../../docs/03-architecture/artifact-storage-contract.md), [ADR-032](../../docs/11-decisions/ADR-032-artifact-storage-resolver-integrity.md), [DB Migration 전략](../../docs/07-database/database-redesign-migration-strategy.md)

## 목적

Artifact ID와 승인된 Storage domain의 canonical key를 연결하는 내부 authoritative Catalog 기반을 추가한다. 이번 범위는 `ArtifactStorageLocation` Entity와 additive Alembic Migration 및 임시 SQLite 안전성 검증까지이며, Resolver·trusted ingestion·실제 파일 무결성 검사·Artifact API는 구현하지 않는다.

## 구현 계약

| 항목 | 결과 |
|---|---|
| Entity | `ArtifactStorageLocation` |
| Table | `artifact_storage_locations` |
| 필드 | `storage_location_id`, `artifact_id`, `storage_backend`, `storage_domain`, `storage_key`, `locator_version`, `published_at`, `created_at` |
| Artifact 관계 | Artifact 1 : StorageLocation 0..1, `back_populates` 대칭 |
| FK | `artifact_id → artifacts.artifact_id`, `ON DELETE RESTRICT` |
| Unique | `artifact_id`; `(storage_backend, storage_domain, storage_key)` |
| Check | backend 비어 있지 않음, domain 승인값, key 비어 있지 않음, locator version 1 이상 |
| Index | Unique 제약이 두 조회 방향을 지원하므로 별도 중복 Index 없음 |
| backend | 초기 구현값 `local`; DB는 향후 식별자를 막지 않되 다른 backend 지원을 완료로 간주하지 않음 |
| domain | `lm`, `audio`, `vocal`, `music`만 허용 |
| key | domain root 기준 canonical POSIX 상대 key 계약; traversal·root containment 검증은 후속 Resolver 책임 |
| Path | Artifact와 Catalog 모두 absolute path·file path column 없음 |

## Migration 계약

- source head: `20260809_0016`
- down revision: `20260808_0015`
- upgrade: 신규 Catalog Table 하나와 그 FK·Unique·Check만 생성
- downgrade: 신규 Catalog Table 하나만 제거
- 기존 Artifact·AssetVersion·Runtime Table과 기존 revision 변경 없음
- backfill·data SQL·파일 이동·directory 생성 없음
- metadata: 기존 Runtime 14 + Workspace 21 + Catalog 1 = 36개 Table

## 임시 SQLite 안전성

`20260808_0015 → 20260809_0016 → 20260808_0015`를 실제 사용자 DB가 아닌 임시 SQLite에서 검증했다.

| 검증 | 결과 |
|---|---|
| upgrade 후 application Table | 36개, Catalog 정확히 1개 추가 |
| downgrade 후 application Table | 35개, 기존 Artifact 보존 |
| 기존 row count | 전후 동일 |
| 기존 deterministic digest | 전후 동일 |
| `PRAGMA quick_check` | `ok` |
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | 위반 0건 |
| 존재하지 않는 Artifact FK | 거부 |
| 동일 Artifact locator 중복 | 거부 |
| 동일 backend/domain/key 중복 | 거부 |
| Check 위반 | 모두 거부 |
| metadata/reflection | column·FK·Unique·Check 일치 |

기존 `pipeline_jobs.input_snapshot nullable drift`는 Alembic autogenerate에서 계속 탐지되는 선행 WARNING이며 신규 Catalog schema drift가 아니다.

## 회귀 검증

다음 10개 테스트 파일을 함께 실행해 **63 passed**를 확인했다.

- 신규 Catalog Entity·Migration
- Workspace Entity와 0012 Migration
- Workspace Repository·Service
- Workspace·Project·ProjectAsset·Asset keyset Migration
- Asset·AssetVersion API

Python 3.12 SQLite 기본 datetime adapter 폐기 예정 경고 16,644건이 기존 대량 fixture에서 발생했다. 테스트 실패는 0건이며 이 경고는 별도 개선 대상으로 유지한다.

## 정적·Route 검증

| 검증 | 결과 |
|---|---|
| Python compile | PASS |
| Ruff lint | PASS |
| Ruff format | PASS, 273개 파일 |
| Alembic head | 단일 `20260809_0016` |
| FastAPI Route | 64개, 변경 없음 |
| APIRoute | 60개, 변경 없음 |
| OpenAPI Path | 44개, 변경 없음 |
| OpenAPI Operation | 62개, 변경 없음 |
| Resource API | 19/64, 변경 없음 |
| Artifact API | 0/3, 미구현 유지 |

OpenAPI 생성 시 기존 Pipeline file route operation ID 중복 2건이 재현됐으며 이번 변경으로 추가된 경고는 아니다.

## 실제 환경 비영향

- 실제 사용자 DB에 접근·조회·Migration하지 않았다.
- 실제 사용자 DB revision은 `20260808_0015`로 문서화하고 source head와 구분했다.
- 실제 Artifact 파일에 접근하지 않았고 `DohaArtifacts` directory를 생성하지 않았다.
- Repository·Service·Resolver·ingestion·Router·Frontend·Runtime을 구현하거나 변경하지 않았다.

## 판정

Artifact Storage Catalog Entity와 additive source Migration 기반은 **PASS**다. BLOCKER는 0건이다. 다음 단계는 실제 DB에 바로 적용하는 작업이 아니라 0016 대상 read-only Inventory·backup·restore rehearsal·migration rehearsal Gate이며, 그 후 별도 승인으로 실제 적용 여부를 결정한다. Resolver·trusted ingestion·physical checksum 검증과 Artifact API는 이후 독립 PR로 진행한다.

## WARNING

- 실제 사용자 DB에는 `20260809_0016`을 아직 적용하지 않았다.
- `storage_key`의 traversal·symlink·junction·root containment 검증은 후속 Resolver가 담당한다.
- DB와 filesystem은 하나의 원자 transaction이 아니므로 후속 ingestion에서 orphan reconciliation이 필요하다.
- `local` 외 backend는 계약 확장 여지만 있고 구현되지 않았다.
- 기존 `pipeline_jobs.input_snapshot nullable drift`, SQLite datetime adapter 폐기 예정과 OpenAPI operation ID 중복 2건은 후속 정리가 필요하다.
