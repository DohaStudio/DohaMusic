# Artifact Storage Catalog `0016` 실제 적용 검증 보고서

> 상태: [완료]
> 검증일: 2026-08-09
> 기준 develop commit: `64040d84797fe3e1beec0b549d41f6d3b137564f`
> 대상 DB: `D:/.../doha_music.db`
> 관련 문서: [Artifact Storage 계약](../../docs/03-architecture/artifact-storage-contract.md), [DB Migration 전략](../../docs/07-database/database-redesign-migration-strategy.md), [ADR-032](../../docs/11-decisions/ADR-032-artifact-storage-resolver-integrity.md)

## 1. 목적과 범위

검증된 Inventory·backup·restore·Migration rehearsal 결과를 바탕으로 실제 사용자 SQLite DB에 Artifact Storage Catalog additive revision을 적용하고 schema·data·무결성과 backup 불변성을 확인했다. Resolver·trusted ingestion·physical checksum 검증·Range·Artifact API·backfill·dual write·Runtime 전환은 수행하지 않았다.

## 2. 적용 결과

| 항목 | 결과 |
|---|---|
| 적용 전 revision | `20260808_0015` |
| 적용 후 revision | `20260809_0016` |
| 적용 전 SHA-256 | `e10a2b689d78b5796c8d3d39e5147470ee6fa7e84a9a47101f54d25427563b7f` |
| 적용 후 SHA-256 | `f5999d8ade5819ea7a7d45e71a7ec9e5c9297f04b97298858c0bbf75ffbc7fbc` |
| 적용 후 크기 | `1,056,768` bytes |
| Application Table | 35 → 36 |
| Runtime Table | 14 유지 |
| 신규 Table | `artifact_storage_locations` |
| Catalog row | 0 |
| 기존 35개 Table schema 변경 | 0 |
| 기존 row | 79 유지 |
| canonical logical digest | `fbc8508e14225e9e3a76e6b92462761708322475bbe8143ecd0ec4c2315c87e3` 전후 동일 |
| `quick_check` | `ok` |
| `integrity_check` | `ok` |
| `foreign_key_check` | 0건 |
| Runtime `foreign_keys` | `1` |
| WAL·SHM | 작업 전후 없음 |
| downgrade·restore | 실제 DB에서는 미실행 |
| 정식 backup·manifest | checksum·크기·mtime 불변 |

## 3. 실행 Gate

1. Backend·Worker·관련 Python writer가 10초 동안 0개인지 확인했다.
2. 대상이 backup·임시·rehearsal 파일이나 symlink가 아닌 명시적 실제 DB인지 확인했다.
3. 적용 전 DB와 정식 backup·manifest의 checksum, revision, Table, row, 무결성을 재검증했다.
4. Migration 직전 5초 동안 writer가 계속 0개이고 WAL·SHM이 없는지 다시 확인했다.
5. Alembic online connection과 Runtime SQLAlchemy 연결의 `PRAGMA foreign_keys=1`을 확인했다.
6. 실제 사용자 DB에만 `20260809_0016`을 적용하고 자동 downgrade·restore는 실행하지 않았다.

## 4. Catalog schema

- Column은 `storage_location_id`, `artifact_id`, `storage_backend`, `storage_domain`, `storage_key`, `locator_version`, `published_at`, `created_at` 8개다.
- FK는 `artifact_id → artifacts.artifact_id`, `ON DELETE RESTRICT`다.
- `artifact_id`와 `(storage_backend, storage_domain, storage_key)` Unique가 존재한다.
- backend·key 비어 있음, 승인되지 않은 domain, 1 미만 locator version을 거부하는 Check Constraint가 존재한다.
- Unique가 만드는 SQLite 내부 Index 외 별도 Catalog Index는 없다.

## 5. 현재 경계와 WARNING

- `pipeline_jobs.input_snapshot` nullable drift는 기존 WARNING으로 유지한다.
- 일부 Unique Constraint 이름은 SQLite reflection에서 다르게 표현될 수 있으므로 column 조합을 계약 기준으로 사용한다.
- Python 3.12 SQLite datetime adapter 폐기 예정과 순환 FK SQLAlchemy warning을 유지한다.
- Catalog Entity·Migration·실제 사용자 DB 적용은 완료했지만 Resolver·trusted ingestion·physical checksum 검증·Range는 미구현이다.
- Catalog row는 0개이며 실제 Artifact 파일과 `DohaArtifacts` Runtime root에는 접근하지 않았다.
- Resource API는 19/64, Artifact API는 0/3이다.
- backfill·dual write·Runtime 전환을 수행하지 않았으므로 기존 Runtime Table 14개가 계속 source of truth다.

## 6. 판정

**PASS — 실제 사용자 DB `20260809_0016` 적용 완료**

BLOCKER는 0건이다. 정식 backup과 manifest는 변경하지 않았으며 실제 DB에서는 downgrade와 restore를 실행하지 않았다.
