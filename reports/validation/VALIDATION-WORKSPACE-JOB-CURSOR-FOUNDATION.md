# Workspace Job Cursor 기반 검증

> 문서 상태: [완료]
> 검증일: 2026-08-10
> 기준 브랜치: `feature/job-cursor-foundation`
> 관련 기능: Workspace Job HMAC Cursor, Owner·Workspace keyset Repository와 Service page
> 관련 문서: [Workspace Job Foundation](../../docs/03-architecture/workspace-job-foundation.md), [Cursor Pagination](../../docs/06-api/cursor-pagination.md), [ADR-033](../../docs/11-decisions/ADR-033-workspace-job-execution-boundary.md)

## 1. 검증 범위

- version 1 `job` Cursor payload와 `(created_at DESC, job_id DESC)` position
- effective Owner·Workspace·선택 `project_id`·`status`·`job_type` fingerprint
- Workspace join을 통한 Repository owner scope
- 기존 offset 조회 보존과 `list_jobs_after()` keyset 조회
- `limit + 1` 기반 `JobPage`
- 다른 Owner·Workspace·filter의 Cursor 재사용 거부
- revision `20260810_0017` keyset Index의 10,000건 Query Plan

Job Router·공개 API 5개, Service state machine, Worker claim·lease, Provider 호출과 completion Unit of Work는 검증 범위가 아니다.

## 2. 기능 검증

| 항목 | 결과 |
|---|---|
| `job` Cursor payload 필드와 HMAC 검증 | PASS |
| 동일 시각 UUID tie-break와 page 중복 방지 | PASS |
| Owner·Workspace scope 강제 | PASS |
| Project·status·job type filter | PASS |
| 다른 scope·filter Cursor 재사용 `INVALID_CURSOR` | PASS |
| 정확한 정수 `limit`과 1~100 범위 | PASS |
| 빈 마지막 page의 `has_more=false`, `next_cursor=null` | PASS |

## 3. Query Plan

임시 SQLite에 Workspace 4개, Project 8개, Job 10,000개를 만들고 다음 네 조회의 첫 page와 다음 page를 각각 확인했다.

| 조회 | 사용 Index | `SCAN jobs` | `TEMP B-TREE` |
|---|---|---|---|
| Workspace | `ix_jobs_workspace_keyset` | 없음 | 없음 |
| Project | `ix_jobs_workspace_project_keyset` | 없음 | 없음 |
| status | `ix_jobs_workspace_status_keyset` | 없음 | 없음 |
| job type | `ix_jobs_workspace_type_keyset` | 없음 | 없음 |

모든 결과는 `(created_at DESC, job_id DESC)` 순서를 유지했다. 신규 Index와 Alembic revision은 추가하지 않았다.

## 4. 테스트와 정적 검사

- Job Cursor 전용 테스트: 7 passed
- Cursor·Asset Cursor·ProjectAsset Cursor·Workspace Service·Job schema Migration 포함 선별 회귀: 83 passed
- Python compile: PASS
- Ruff lint: PASS
- Ruff format check: PASS
- `git diff --check`: PASS

## 5. 저장소와 운영 영향

- 실제 사용자 DB와 실제 `DohaArtifacts`에는 접근하지 않았다.
- Alembic source head와 실제 사용자 DB 문서 기준은 `20260810_0017`로 유지한다.
- Metadata 36개 Table, Runtime source of truth 14개, Resource API 25/64와 Job API 0/5는 변경하지 않았다.
- Frontend·Provider·Worker·backfill·dual write·Bootstrap은 변경하거나 실행하지 않았다.

## 6. 판정

**PASS** — Workspace Job Cursor와 Owner·Workspace keyset Repository Foundation 범위에 BLOCKER가 없다. 다음 단계는 Job Service state machine과 Worker claim·lease 기반이며 공개 Job Router는 해당 기반 검증 후 구현한다.
