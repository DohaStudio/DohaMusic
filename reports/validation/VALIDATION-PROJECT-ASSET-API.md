# ProjectAsset Resource API 검증

> 문서 상태: [완료]
> 검증일: 2026-08-07
> 관련 기능: ProjectAsset 목록·연결·관계 해제 REST API
> 관련 문서: [Workspace REST API 계약](../../docs/06-api/workspace-rest-api-contract.md), [Endpoint 목록](../../docs/06-api/workspace-rest-api-endpoints.md), [Cursor Pagination](../../docs/06-api/cursor-pagination.md)

## 1. 검증 범위

이번 변경은 다음 세 Endpoint만 구현한다.

| Method | Path | 결과 |
|---|---|---|
| `GET` | `/api/v1/projects/{project_id}/assets` | HMAC Cursor 기반 활성 관계 목록 |
| `POST` | `/api/v1/projects/{project_id}/assets` | 기존 Asset 연결 또는 Soft Delete 관계 복원 |
| `DELETE` | `/api/v1/projects/{project_id}/assets/{asset_id}` | ProjectAsset 관계만 Soft Delete |

Router는 App State의 `WorkspaceService`만 호출한다. Repository·Session·Cursor를 직접 만들지 않으며 실제 사용자 DB에는 접근하지 않았다.

## 2. 계약 검증

- 목록 정렬은 `display_order ASC, project_asset_id ASC`다.
- Cursor는 Project filter에 결합되어 다른 Project에서 재사용할 수 없다.
- Soft Delete 관계는 목록에서 제외한다.
- POST는 Asset·AssetVersion을 생성하지 않는다.
- 활성 중복은 `409 PROJECT_ASSET_CONFLICT`이며, 삭제된 관계의 재연결은 같은 `project_asset_id`를 복원한다.
- DELETE는 Asset·AssetVersion과 다른 Project 연결을 보존한다.
- 공개 응답은 `asset_id`, `role`, `display_order`만 포함한다.
- 공개 입력에서 내부 ID·소유권·감사·삭제 시각 필드를 허용하지 않는다.

## 3. 검증 결과

| 항목 | 결과 |
|---|---|
| ProjectAsset API 전용 테스트 | 19 passed |
| Workspace API Foundation·Workspace·Project·Cursor 회귀 | 74 passed |
| Entity·Repository·Service·Migration 선별 회귀 | 29 passed |
| 기존 Pipeline·File API 회귀 | 37 passed, Windows symlink 1 skipped |
| Python compile | PASS |
| 변경 Python Ruff lint·Backend format | PASS |
| `git diff --check` | PASS |
| Alembic source head | `20260807_0014` 유지 |
| 실제 사용자 DB 접근 | 미수행 |

중복 없이 합산한 선별 검증은 159 passed, 1 skipped다. 전체 Backend suite는 이번 범위에서 실행하지 않았으며, 기존 Runtime 회귀는 ProjectAsset Router 등록과 직접 인접한 Pipeline·File API를 선택해 확인했다. OpenAPI 생성 중 기존 Pipeline file route operation ID 중복 2건과 TestClient 폐기 예정 알림은 기존 WARNING으로 유지한다.

## 4. 미수행 범위

- Asset·AssetVersion·Artifact·Snapshot·Job Resource API
- 실제 Bootstrap, backfill, dual write
- Alembic revision 추가·수정과 실제 DB Migration
- Frontend·Runtime·Provider 변경
- 실제 사용자 DB 읽기·쓰기

## 5. 현재 상태

Resource API 구현 진행도는 11/64다. Runtime Table 14개가 계속 source of truth이며 실제 사용자 DB revision은 기존 문서 기준 `20260807_0014`다. 다음 구현 범위는 Asset Cursor·Index와 Resource API 5개다.
