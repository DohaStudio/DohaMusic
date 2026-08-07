# Workspace keyset 복합 Index 설계

> 문서 상태: [완료]
> 최종 수정일: 2026-08-07
> 관련 기능: Workspace·MusicProject HMAC Cursor Pagination의 SQLite Query Plan
> 구현 상태: Entity metadata·Alembic `20260807_0013`·임시 SQLite 검증과 실제 사용자 DB 적용 완료
> 관련 문서: [Cursor Pagination](../06-api/cursor-pagination.md), [DB Migration 전략](database-redesign-migration-strategy.md), [검증 보고서](../../reports/validation/VALIDATION-WORKSPACE-KEYSET-INDEXES.md)

## 1. 조회 계약

Repository 쿼리 의미는 변경하지 않습니다. Workspace는 `deleted_at IS NULL`, 선택적 `owner_id`, `(created_at DESC, workspace_id DESC)` 순서를 사용합니다. MusicProject는 고정 `workspace_id`, `deleted_at IS NULL`, `(created_at DESC, project_id DESC)` 순서를 사용합니다. 다음 page는 생성 시각이 작거나 생성 시각이 같으면서 UUID가 작은 row만 조회합니다.

## 2. 기존 Index Inventory

`workspaces`에는 primary key용 `sqlite_autoindex_workspaces_1`과 `owner_id`, `lifecycle_status`, `deleted_at` 단일 Index가 있습니다. `music_projects`에는 primary key용 `sqlite_autoindex_music_projects_1`과 `workspace_id`, `title`, `lifecycle_status`, `created_by`, `deleted_at` 단일 Index가 있습니다. 별도 Unique Constraint Index는 없고 이름 중복도 없습니다.

신규 Index의 첫 Column은 기존 단일 Index와 겹치므로 prefix 중복 가능성이 있습니다. 그러나 기존 CRUD·Soft Delete·상태 조회 영향과 실제 사용자 DB 통계를 확인하지 않은 상태에서 기존 Index를 제거하지 않습니다. 제거 후보 평가는 운영 적용 후 별도 작업으로 남깁니다.

## 3. 기준 Query Plan

임시 SQLite에 Workspace 720건과 MusicProject 1,200건을 넣었습니다. 여러 owner·Workspace, 활성·Soft Delete, 같은 생성 시각과 서로 다른 생성 시각을 섞었습니다.

Migration 전 여섯 쿼리는 기존 `deleted_at` 또는 filter 단일 Index를 사용했지만 모두 `USE TEMP B-TREE FOR ORDER BY`가 나타났습니다.

| 쿼리 | Migration 전 |
|---|---|
| 전체 Workspace 첫 page | `ix_workspaces_deleted_at` + 임시 정렬 |
| 전체 Workspace 다음 page | `ix_workspaces_deleted_at` + 임시 정렬 |
| owner별 Workspace 첫 page | `ix_workspaces_deleted_at` + 임시 정렬 |
| owner별 Workspace 다음 page | `ix_workspaces_deleted_at` + 임시 정렬 |
| Workspace별 Project 첫 page | `ix_music_projects_deleted_at` + 임시 정렬 |
| Workspace별 Project 다음 page | `ix_music_projects_deleted_at` + 임시 정렬 |

## 4. 후보 비교

| 후보 | 전체 Workspace | owner Workspace | Project | 판단 |
|---|---|---|---|---|
| 기존 단일 Index | 임시 정렬 | 임시 정렬 | 임시 정렬 | 제외 |
| partial ASC | 기존 `deleted_at` Index 선택·임시 정렬 | 신규 Index 사용 | 신규 Index 사용 | 전체 목록 미충족 |
| partial DESC | 기존 `deleted_at` Index 선택·임시 정렬 | 신규 Index 사용 | 신규 Index 사용 | 전체 목록 미충족 |
| `deleted_at` 선두 비-partial ASC | 신규 Index 사용 | 신규 Index 사용 | 신규 Index 사용 | 선택 |
| `deleted_at` 선두 비-partial DESC | 신규 Index 사용 | 신규 Index 사용 | 신규 Index 사용 | ASC와 계획·결과 동일 |

Partial Index는 활성 row만 보관한다는 장점이 있지만 기존 `ix_workspaces_deleted_at`와 함께 있을 때 owner 없는 조회를 안정적으로 최적화하지 못했습니다. 기존 Index 제거 또는 `INDEXED BY` hint는 이번 범위를 벗어나며 Repository 의미와 이식성을 해칠 수 있어 사용하지 않습니다.

SQLite는 ASC 복합 Index를 역방향으로 탐색해 DESC 결과를 만들었고 임시 정렬도 사용하지 않았습니다. 명시적 DESC와 차이가 없으므로 다른 DB 제품과 Alembic 표현이 단순한 기본 ASC를 선택했습니다.

## 5. 최종 Index

| 이름 | Table | Column 순서 |
|---|---|---|
| `ix_workspaces_active_keyset` | `workspaces` | `deleted_at`, `created_at`, `workspace_id` |
| `ix_workspaces_owner_active_keyset` | `workspaces` | `owner_id`, `deleted_at`, `created_at`, `workspace_id` |
| `ix_music_projects_workspace_active_keyset` | `music_projects` | `workspace_id`, `deleted_at`, `created_at`, `project_id` |

Entity `__table_args__`와 Alembic revision은 같은 이름과 Column 순서를 사용합니다. Table·Column·Constraint·row와 기존 Index는 변경하지 않습니다.

## 6. Migration과 복구

`20260807_0013`은 `20260806_0012` 다음의 단일 head입니다. Upgrade는 세 Index만 생성하고 downgrade는 역순으로 세 Index만 제거합니다. 임시 SQLite round trip에서 Table·row 수, 기존 Index, `quick_check`, `integrity_check`, `foreign_key_check`를 보존했습니다.

실제 사용자 DB에는 read-only Inventory, 검증된 backup·restore rehearsal와 사용자 승인 후 revision을 적용했습니다. 실제 통계에서 write 비용과 prefix 중복을 측정한 뒤 기존 단일 Index 제거 여부를 별도로 검토합니다.

## 7. 유지되는 경계

- HMAC Cursor payload와 codec은 변경하지 않습니다.
- Repository의 filter·정렬·다음 page 조건은 변경하지 않습니다.
- Service의 `limit + 1`, `has_more`, `next_cursor` 계약은 변경하지 않습니다.
- Workspace·MusicProject·ProjectAsset Resource Endpoint 11개는 구현했으며 실제 Bootstrap, backfill, dual write와 Frontend는 구현하지 않습니다.
