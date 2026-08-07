# ProjectAsset Cursor Pagination 기반 검증 보고서

> 문서 상태: [진행 중]
> 검증일: 2026-08-07
> 기준 브랜치: `develop` (`5c836de40ad7f18a3fd3436da1fd154aeac2ac2c`)
> 작업 브랜치: `feature/project-asset-cursor`
> 관련 문서: [Cursor Pagination](../../docs/06-api/cursor-pagination.md), [ProjectAsset Keyset Index](../../docs/07-database/project-asset-keyset-indexes.md)

## 1. 검증 범위

이번 작업은 `ProjectAsset` 목록 API 구현 전에 다음 기반만 추가하고 검증한다.

- `project_asset` 전용 HMAC Cursor payload와 위치 타입
- `(display_order ASC, project_asset_id ASC)` Keyset 조회
- `WorkspaceService.list_project_asset_page()`
- 활성 연결 목록을 위한 SQLite partial index와 Alembic `20260807_0014`
- 삽입·분리·복원·동일 순서값을 포함한 페이지 안정성 테스트

Router, Resource Endpoint, App Factory 추가 등록, Frontend, 실제 DB 적용은 범위에서 제외했다.

## 2. 계약 검토 결과

### 2.1 정렬과 Cursor

- 공식 정렬: `display_order ASC, project_asset_id ASC`
- Cursor resource: `project_asset`
- Cursor version: 기존 계약과 같은 `1`
- 위치 필드: `last_display_order`, `last_id`
- 필터 결합: `project_id`, `include_deleted=false`, 공식 정렬
- `v`, `limit`, `last_display_order`는 `type(value) is int`로 검증하여 `bool`, `float`, 문자열을 거부한다.
- Cursor 위변조, 다른 Project 재사용, 예상 `limit` 불일치, 필드 누락·초과, UUID 오류와 최대 길이 초과는 모두 `INVALID_CURSOR`로 통합한다.

### 2.2 ProjectAsset 고유성

공통 명세의 최소 계약은 `(project_id, asset_id, role)` 중복을 금지한다. DohaMusic의 현재 Entity와 실제 Schema는 `(project_id, asset_id)`를 더 엄격하게 고유하게 유지한다. `role`은 연결의 변경 가능한 메타데이터이며, 기존 Service의 soft-delete 복원과 계획된 식별 계약도 `project_id + asset_id`를 사용하므로 이번 작업에서 고유성 계약을 변경하지 않았다.

### 2.3 삭제와 페이지 경계

- 목록은 `deleted_at IS NULL`인 연결만 반환한다.
- 분리된 연결은 soft-delete하며 Cursor 결과에서 제외한다.
- 복원은 기존 `project_asset_id`를 유지한다.
- 페이지 사이에 Cursor 앞쪽에 삽입된 항목은 이전 페이지로 되돌아가지 않는다.
- 복원된 항목이 이미 지난 Cursor 위치라면 다시 노출하지 않는 forward-only 계약을 유지한다.

## 3. Index 비교

동일한 SQLite fixture에서 Project별 500개 연결을 구성하고 `EXPLAIN QUERY PLAN` 결과와 반환 행의 동일성을 비교했다.

| 후보 | 정의 | Query Plan | `TEMP B-TREE` | 판정 |
|---|---|---|---:|---|
| 기존 단일 Index | `project_id` | Project 필터 후 별도 정렬 | 1 | 제외 |
| 전체 복합 Index | `(project_id, deleted_at, display_order, project_asset_id)` | 복합 Index 검색 | 0 | 가능 |
| 활성 partial Index | `(project_id, display_order, project_asset_id) WHERE deleted_at IS NULL` | partial Index 검색 | 0 | 채택 |

활성 목록이 공식 조회 계약이고 삭제된 연결을 목록에서 제외하므로, 더 작은 활성 partial index `ix_project_assets_active_keyset`을 채택했다. 세 후보의 반환 행 순서는 같았고 채택 Index에서는 별도 정렬이 발생하지 않았다.

## 4. Migration 검증

- 이전 head: `20260807_0013`
- 신규 source head: `20260807_0014`
- Revision 수: 13개
- 단일 head: 확인
- Upgrade: `ix_project_assets_active_keyset` 1개만 생성
- Downgrade: 위 Index 1개만 제거
- Table·Column·FK·Unique·데이터 변경: 0건
- 기존 Workspace keyset index 3개: 유지
- Metadata application table: 35개 유지
- 임시 SQLite upgrade·downgrade 후 row count, `integrity_check`, `foreign_key_check`: 일치 및 통과

실제 사용자 DB는 읽거나 변경하지 않았다. 실제 사용자 DB revision은 `20260807_0013`으로 문서화하며, `20260807_0014` 적용은 별도 Inventory·backup·rehearsal·승인이 필요하다.

## 5. 테스트 결과

| 검증 묶음 | 결과 |
|---|---:|
| ProjectAsset Cursor·Index와 기존 Cursor 회귀 | 56 passed |
| Workspace Migration·ProjectAsset Index 재검증 | 4 passed |
| Workspace API·공통 기반 선별 회귀 | 20 passed |
| 기존 Runtime 선별 회귀 | 14 passed |

추가 경계 테스트는 `True`, `False`, `float`, 문자열, 0과 100 초과 `limit`을 Service와 서명 payload에서 거부하는지 확인한다. 최종 정적 검사와 GitHub Actions 결과는 Draft PR 최신 head에서 다시 확인한다.

## 6. API 표면 불변 확인

- FastAPI Route: 53개
- `APIRoute`: 49개
- OpenAPI path: 38개
- OpenAPI operation: 51개
- `/api/v1` Resource operation: 8개
- 신규 ProjectAsset Endpoint: 0개

## 7. 상태와 후속 작업

현재 상태는 **ProjectAsset Cursor·Keyset 기반 [완료], ProjectAsset Resource API [계획]**이다. 다음 작업에서 Router DTO, `GET /api/v1/projects/{project_id}/assets`, 응답 envelope, App Factory 연결과 API 계약 테스트를 별도 PR로 구현한다.

실제 DB Migration, backfill, dual write, Bootstrap, Provider, Runtime 및 Frontend 변경은 수행하지 않았다.
