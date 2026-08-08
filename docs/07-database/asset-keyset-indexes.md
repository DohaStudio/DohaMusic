# Asset keyset Index 설계

> 문서 상태: [완료]
> 최종 수정일: 2026-08-08
> 관련 기능: Owner scope Asset Cursor Pagination과 Alembic `20260808_0015`
> 구현 상태: Entity metadata·Repository·Service·source revision 완료, 실제 사용자 DB 미적용, Asset Resource API 미구현
> 관련 문서: [Cursor Pagination](../06-api/cursor-pagination.md), [Workspace REST API 계약](../06-api/workspace-rest-api-contract.md), [Migration 전략](database-redesign-migration-strategy.md)

## 1. 공개 조회 계약

향후 `GET /api/v1/assets`는 신뢰된 현재 Owner의 Soft Delete되지 않은 Asset만 조회한다. 공개 query에 `owner_id`와 `include_deleted`를 받지 않으며 Owner 조건 없는 전체 `assets` 조회를 허용하지 않는다.

공개 filter allowlist는 다음 두 개다.

| Query | 의미 |
|---|---|
| `workspace_id=<uuid>` | 현재 Owner가 소유한 특정 Workspace의 Asset만 조회. 생략하면 현재 Owner의 Workspace 미지정 Asset을 포함한 전체 활성 Asset 조회 |
| `asset_type=<enum>` | `lyrics`, `music`, `vocal`, `stem`, `recording`, `mix`, `export` 중 하나만 조회 |

`lifecycle_status`, 자유 문자열 검색, 임의 sort와 `filter[field]` 형식은 이번 계약에서 공개하지 않는다. 기본 정렬은 `(created_at DESC, asset_id DESC)`이며 `deleted_at IS NULL`은 고정 조건이다.

## 2. Query Plan 후보

실제 사용자 DB가 아닌 Alembic `20260807_0014` 임시 SQLite에 6,000개 Asset fixture를 구성했다. fixture는 Owner 4개, Workspace 12개, `workspace_id=NULL`, Asset type 7개, lifecycle 3개, 동일 `created_at`, Soft Delete row를 포함한다.

공식 Query 조합은 Owner 기본, Owner+`asset_type`, Owner+`workspace_id`, Owner+`workspace_id`+`asset_type`의 첫 page와 다음 page 총 8개다. Migration 전에는 모두 `ix_assets_deleted_at`와 `USE TEMP B-TREE FOR ORDER BY`를 사용했다.

### 2.1 full 후보

```text
(owner_id, deleted_at, created_at, asset_id)
(owner_id, workspace_id, deleted_at, created_at, asset_id)
```

8개 Query 모두 적절한 후보 Index를 사용했고 정렬용 임시 B-Tree와 full scan이 제거됐다. `asset_type`은 keyset 정렬을 보존한 상태에서 residual filter로 평가되므로 전용 Index 없이도 계약을 충족했다.

### 2.2 partial 후보

```text
(owner_id, created_at, asset_id) WHERE deleted_at IS NULL
(owner_id, workspace_id, created_at, asset_id) WHERE deleted_at IS NULL
```

SQLite planner는 두 partial 후보보다 기존 `ix_assets_deleted_at`를 선택했고 8개 Query 모두 임시 정렬이 남았다. 기존 단일 Index를 제거하거나 Query hint를 도입하지 않고 안정적인 계획을 얻기 위해 partial 후보는 선택하지 않았다.

## 3. 최종 Index

Alembic `20260808_0015`와 SQLAlchemy metadata는 다음 두 full Index를 추가한다.

| 이름 | Column 순서 |
|---|---|
| `ix_assets_owner_active_keyset` | `owner_id`, `deleted_at`, `created_at`, `asset_id` |
| `ix_assets_owner_workspace_active_keyset` | `owner_id`, `workspace_id`, `deleted_at`, `created_at`, `asset_id` |

SQLite는 ASC Index를 역방향으로 탐색할 수 있으므로 metadata와 migration에 DESC 표현을 별도로 넣지 않는다. 기존 `owner_id`, `workspace_id`, `asset_type`, `deleted_at` 단일 Index는 운영 통계 없이 제거하지 않는다.

## 4. Prefix 중복과 후속 검토

- Owner Index는 기존 `ix_assets_owner_id`와 prefix가 겹치지만 이번 PR에서는 제거하지 않는다.
- Owner+Workspace Index는 Owner를 첫 Column으로 두어 Owner isolation을 Query Plan과 함께 보장한다.
- `asset_type` 전용 및 Owner+type Index는 현재 Query Plan에 필요하지 않아 추가하지 않는다.
- lifecycle filter, 검색과 추가 sort가 공식 계약에 들어오면 기존 Index에 임의로 끼워 넣지 않고 별도 Query Plan과 migration으로 검토한다.

## 5. Migration 경계

- Upgrade는 두 Asset Index만 추가한다.
- Downgrade는 두 Index만 역순으로 제거한다.
- Table·Column·FK·Unique·Check와 row를 변경하지 않는다.
- 임시 SQLite upgrade·downgrade에서 Application Table 35개, Runtime Table 14개, Workspace Table 21개, row count·digest·무결성을 보존한다.
- 실제 사용자 DB `20260807_0014`에는 이번 작업에서 접근하거나 `0015`를 적용하지 않는다.

실제 적용은 PR 병합 후 read-only Inventory, backup, restore rehearsal, migration rehearsal와 별도 사용자 승인을 거친다.
