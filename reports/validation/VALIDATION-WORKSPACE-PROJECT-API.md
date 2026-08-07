# Workspace·MusicProject Resource API 검증 보고서

> 문서 상태: [완료]
> 최종 수정일: 2026-08-07
> 기준 브랜치: `feature/workspace-project-api`
> 기준 develop: `ccd26c9670742b66859ee8c17e6e98820f65384b`
> 검증 코드 head: `3fd59303a4745ac30a3342823ac4afd28e1fd9bc`
> 관련 문서: [공통 계약](../../docs/06-api/workspace-rest-api-contract.md), [Endpoint 목록](../../docs/06-api/workspace-rest-api-endpoints.md)

## 1. 검증 범위

- Workspace 목록·상세·이름 수정 3개 Endpoint
- MusicProject 목록·생성·상세·수정·Soft Delete 5개 Endpoint
- 기존 API Envelope·request ID·Application 오류 변환
- 기존 `WorkspaceService`, Repository와 HMAC Cursor 회귀
- App Factory의 `WorkspaceService` 구성과 OpenAPI 등록

실제 사용자 DB, 실제 Bootstrap, Alembic 변경, backfill, dual write, Provider, Worker와 Frontend는 검증 중 접근하거나 실행하지 않았습니다. 모든 DB 테스트는 pytest가 만든 임시 SQLite 파일만 사용했습니다.

## 2. 계약 결과

| 항목 | 결과 | 근거 |
|---|---|---|
| Router 계층 경계 | PASS | App State dependency로 `WorkspaceService`만 주입하며 Repository·Session·Cursor 직접 사용 없음 |
| 소유권 입력·노출 차단 | PASS | body의 추가 필드와 query의 `owner_id`·`created_by` 거부, 공개 DTO에서도 제외 |
| Project 생성자 | PASS | `Workspace.owner_id`에서 `created_by` 파생 |
| Bootstrap Gate | PASS | 8개 Endpoint 모두 Workspace 0개에서 `409 WORKSPACE_BOOTSTRAP_REQUIRED` |
| Pagination | PASS | 기존 HMAC Cursor와 keyset `limit + 1` 결과 연결, offset 입력 없음 |
| Soft Delete | PASS | Project DELETE가 `204`와 빈 body 반환 |
| 오류 계약 | PASS | Workspace·Project Not Found·Conflict, `INVALID_INPUT`·`INVALID_CURSOR`·`INVALID_LIMIT` 검증 |
| Bootstrap CLI revision | PASS | 실제 실행 없이 임시 DB에서 현재 head `20260807_0013`만 허용 |

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
| 신규 API와 API Foundation | 20 passed |
| Workspace Bootstrap·Service·Repository·Entity·Migration·Cursor·Keyset 회귀 | 69 passed |
| 기존 Runtime API 선별 회귀 | 14 passed |
| Python compile | PASS |
| `ruff check backend` | PASS |
| Backend 259개 Python 파일 format check | PASS |
| OpenAPI 생성 | PASS |

로컬 전체 Backend는 356개 테스트를 수집했으나 900초 제한 안에 결과를 회수하지 못했습니다. 최초 GitHub Actions는 350 passed·5 skipped 후 FastAPI 버전별 중첩 Router 내부 표현을 직접 센 assertion 1개만 실패했습니다. 실제 OpenAPI 8개 Operation은 등록돼 있었으며, 테스트를 기존 정규화 helper 기반으로 최소 수정했습니다.

수정 후 코드 head의 GitHub Actions는 `backend-ubuntu` 352 passed·5 skipped, `ffmpeg-windows` PASS로 완료됐습니다. Integration 5개 skip은 GPU·외부 API·유료 Provider를 CI에서 실행하지 않는 기존 정책입니다.

## 5. 문서 동기화

- README의 실제 DB 기준을 `20260806_0012` Table과 `20260807_0013` keyset Index 적용 완료로 갱신했습니다.
- API·Cursor·Bootstrap·DB Migration 현재 상태 문서에 Workspace·MusicProject 8개 완료, 나머지 56개 미구현을 반영했습니다.
- 실제 Bootstrap·backfill·dual write·Frontend·Runtime source 전환·인증은 미수행 상태로 유지했습니다.
- 과거 CHANGELOG와 기존 validation report의 당시 미수행 기록은 역사 기록으로 보존했습니다.

## 6. 판정

- BLOCKER: 0건
- WARNING: 로컬 전체 Backend suite 시간 제한, 기존 OpenAPI operation ID 중복 2종, SQLite datetime adapter와 Starlette TestClient 폐기 예정
- 결론: 코드·문서 직접 Gate와 필수 GitHub Actions가 모두 PASS이므로 Ready 전환 가능합니다. 이번 검토에서는 Draft를 유지하고 Ready 전환·병합은 수행하지 않습니다.
