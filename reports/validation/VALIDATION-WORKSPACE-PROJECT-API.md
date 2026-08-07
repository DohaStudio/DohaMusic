# Workspace·MusicProject Resource API 검증 보고서

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-07
> 기준 브랜치: `feature/workspace-project-api`
> 기준 develop: `ccd26c9670742b66859ee8c17e6e98820f65384b`
> 관련 문서: [공통 계약](../../docs/06-api/workspace-rest-api-contract.md), [Endpoint 목록](../../docs/06-api/workspace-rest-api-endpoints.md)

## 1. 검증 범위

- Workspace 목록·상세·이름 수정 3개 Endpoint
- MusicProject 목록·생성·상세·수정·Soft Delete 5개 Endpoint
- 기존 API Envelope·request ID·Application 오류 변환
- 기존 `WorkspaceService`, Repository와 HMAC Cursor 회귀
- App Factory의 `WorkspaceService` 구성과 OpenAPI 등록

실제 사용자 DB, Bootstrap, Alembic 변경, backfill, dual write, Provider, Worker와 Frontend는 검증 중 접근하거나 실행하지 않았습니다. 모든 DB 테스트는 pytest가 만든 임시 SQLite 파일만 사용했습니다.

## 2. 계약 결과

| 항목 | 결과 | 근거 |
|---|---|---|
| Router 계층 경계 | PASS | App State dependency로 `WorkspaceService`만 주입하며 Repository·Session·Cursor 직접 사용 없음 |
| 소유권 입력 차단 | PASS | body의 추가 필드와 query의 `owner_id`·`created_by` 거부 |
| Project 생성자 | PASS | `Workspace.owner_id`에서 `created_by` 파생 |
| Bootstrap Gate | PASS | Workspace 0개에서 `409 WORKSPACE_BOOTSTRAP_REQUIRED` |
| Pagination | PASS | 기존 HMAC Cursor와 keyset `limit + 1` 결과 연결, offset 입력 없음 |
| Soft Delete | PASS | Project DELETE가 `204`와 빈 body 반환 |
| 오류 계약 | PASS | Workspace·Project Not Found·Conflict와 `INVALID_INPUT` 검증 |

## 3. Route·OpenAPI 결과

| 측정값 | 기존 | 변경 후 |
|---|---:|---:|
| 등록 Route | 45 | 53 |
| `APIRoute` | 41 | 49 |
| OpenAPI Path | 34 | 38 |
| OpenAPI Operation | 43 | 51 |
| `/api/v1` Path | 0 | 4 |
| `/api/v1` Operation | 0 | 8 |

기존 `/api` Runtime Operation 수와 경로는 유지됩니다. Pipeline file route의 기존 GET·HEAD operation ID 중복 2종은 이번 변경과 무관한 WARNING으로 남습니다.

## 4. 자동 검증 결과

| 검증 | 결과 |
|---|---|
| 신규 API와 API Foundation | 19 passed |
| 신규 API·Foundation·Service·Repository·Cursor 선별 회귀 | 67 passed |
| Python compile | PASS |
| `ruff check backend` | PASS |
| Backend 259개 Python 파일 format check | PASS |
| OpenAPI 생성 | PASS |

전체 Backend는 356개 테스트를 수집했으나 900초 제한 안에 결과를 회수하지 못했습니다. 따라서 전체 suite를 통과했다고 표현하지 않으며, 모델·GPU·외부 API를 요구하는 integration test도 실행 완료로 간주하지 않습니다.

## 5. 판정

- BLOCKER: 0건
- WARNING: 전체 Backend suite 시간 제한으로 최종 결과 미회수, 기존 OpenAPI operation ID 중복 2종
- 결론: 이번 Resource API 범위와 직접 회귀 Gate는 PASS입니다. Draft PR 검토가 가능하며 전체 Backend 장시간 suite와 기존 operation ID 중복은 후속 검증 대상으로 유지합니다.
