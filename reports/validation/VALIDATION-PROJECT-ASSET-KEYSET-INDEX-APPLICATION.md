# ProjectAsset keyset Index 실제 DB 적용 검증

> 문서 상태: [완료]
> 최종 수정일: 2026-08-07
> 관련 기능: ProjectAsset keyset pagination schema
> 관련 문서: [ProjectAsset keyset Index 설계](../../docs/07-database/project-asset-keyset-indexes.md), [Migration 전략](../../docs/07-database/database-redesign-migration-strategy.md)

## 1. 적용 범위

승인된 실제 사용자 SQLite DB에 Alembic revision `20260807_0013 → 20260807_0014`만 적용했습니다. 적용 전 read-only Inventory, SQLite backup API 기반 backup 검증, restore rehearsal, migration·downgrade rehearsal와 query plan 검증을 완료했습니다.

이번 작업에서 backfill·dual write·Bootstrap·ProjectAsset Resource API·Runtime·Frontend 변경은 수행하지 않았습니다. 기존 Runtime Table 14개는 계속 source of truth입니다.

## 2. 적용 전 Gate

| 항목 | 결과 |
|---|---|
| Revision | `20260807_0013` |
| 원본 SHA-256 | `cfd04913617675bdff071bcb9d0847c6d46d4cb467f0375f084e8de0208788e7` |
| Writer | 0 |
| WAL·SHM | 없음 |
| 정식 backup SHA-256 | `f0490df8a06b622d7d09bff46c151ab8700c7da63484ab17c1b000eee16af00e` |
| Backup manifest | 일치 |

실제 DB 절대 경로는 보고서에 기록하지 않았습니다. 승인된 명시적 `DATABASE_URL`만 사용했고 자동 탐색은 수행하지 않았습니다.

## 3. Migration 결과

- 적용 revision: `20260807_0014`
- Application Table: 35개
- Runtime Table: 14개
- Workspace Table: 21개
- 신규 Index: `ix_project_assets_active_keyset`
- Column 순서: `project_id, display_order, project_asset_id`
- Predicate: `deleted_at IS NULL`
- 기존 Index 보존: PASS

## 4. 데이터와 무결성

| 검증 | 결과 |
|---|---|
| 전체 application row count | 전후 동일 |
| 결정적 data digest | `08218bc381d3b83eb6b9ab4b8c81a6ca0eaf771d5ef45f895bd2ccbc73b6ffcd` 전후 동일 |
| Insert·Update·Delete | 0건 |
| `quick_check` | `ok` |
| `integrity_check` | `ok` |
| `foreign_key_check` | 위반 0건 |
| Runtime `foreign_keys` | 1 |

## 5. Query Plan

Repository와 동일한 첫 page·다음 page query는 모두 다음 계획을 사용했습니다.

```text
SEARCH project_assets USING INDEX ix_project_assets_active_keyset (project_id=?)
```

- 신규 Index 사용: PASS
- `USE TEMP B-TREE FOR ORDER BY`: 0건
- full scan: 0건
- 적용 전후 결과 순서: 동일

## 6. Metadata와 Reflection

- SQLAlchemy metadata Table: 35개
- SQLite reflection Table: 35개
- Index 이름·Column 순서·partial predicate: 일치
- 예상 외 schema 변경: 없음

## 7. 적용 후 원본 상태

| 항목 | 값 |
|---|---|
| Revision | `20260807_0014` |
| SHA-256 | `bafe7102b72abf30e34a537d470ec5647084c41e3696c6c49225d6b887a0e9c2` |
| 파일 크기 | 1,032,192 bytes |
| 수정 시각 UTC | 2026-08-07 10:26:26 |

정식 backup과 manifest는 변경하지 않았습니다. 실패 시 자동 restore나 자동 downgrade를 실행하지 않는 원칙을 유지했으며, 이번 적용은 모든 Gate를 통과해 복구 작업이 필요하지 않았습니다.

## 8. BLOCKER와 WARNING

- BLOCKER: 0건
- WARNING: `pipeline_jobs.input_snapshot`의 기존 nullable metadata drift
- WARNING: Python 3.12 SQLite datetime adapter 폐기 예정
- WARNING: ProjectAsset Resource API 3개와 Bootstrap·backfill·dual write는 미구현 또는 미수행

이번 Migration 범위에서 자동 downgrade나 backup restore는 실행하지 않았습니다. 검증된 정식 backup은 보존했습니다.

## 9. 판정

`20260807_0014` 실제 사용자 DB 적용은 **PASS**입니다. ProjectAsset partial keyset Index는 실제 DB에 반영됐지만 ProjectAsset Resource API는 아직 미구현이며, Bootstrap·backfill·dual write도 수행하지 않았습니다.
