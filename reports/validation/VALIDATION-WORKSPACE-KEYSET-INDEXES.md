# Workspace keyset 복합 Index 검증 보고서

> 문서 상태: [완료]
> 검증일: 2026-08-07
> 기준 브랜치: `feature/workspace-keyset-indexes`
> 기준 develop: `9d6d8c1b5aff0e5615bea73a489fe213f8cccf23`
> 관련 문서: [Index 설계](../../docs/07-database/workspace-keyset-indexes.md), [Cursor Pagination](../../docs/06-api/cursor-pagination.md)

## 1. 검증 범위

- 기존 Workspace·MusicProject Index와 prefix 중복 Inventory
- 임시 SQLite Workspace 720건·MusicProject 1,200건 fixture
- 전체·owner별 Workspace와 Workspace별 Project의 첫·다음 page 여섯 Query Plan
- partial ASC·partial DESC·비-partial ASC·비-partial DESC 후보 비교
- Entity metadata와 Alembic migration의 이름·Column 순서 일치
- `20260806_0012 → 20260807_0013 → 20260806_0012` round trip
- 정렬, tie-breaker, Soft Delete·owner·Workspace filter와 결과 동일성

실제 사용자 DB, `DATABASE_URL`, 실제 Workspace·Project row, backup과 Bootstrap은 사용하지 않았습니다.

## 2. 후보와 결정

Migration 전 여섯 쿼리 모두 정렬용 `USE TEMP B-TREE FOR ORDER BY`가 나타났습니다. Partial 후보는 owner별 Workspace와 Project에서는 신규 Index를 사용했으나 owner 없는 Workspace에서는 기존 `ix_workspaces_deleted_at`가 선택되어 임시 정렬이 남았습니다.

`deleted_at`을 선두에 둔 비-partial ASC와 DESC 후보는 여섯 쿼리 모두 신규 복합 Index를 사용하고 임시 정렬을 제거했습니다. 결과 순서가 같고 SQLite 역방향 scan이 확인되어 기본 ASC를 선택했습니다.

## 3. 자동 검증 현황

| 검증 | 결과 |
|---|---|
| 신규 Index·기존 Workspace migration 전용 테스트 | PASS — 4 passed |
| Migration 전 Query Plan | PASS — 6개 모두 임시 정렬 확인 |
| Migration 후 Query Plan | PASS — 6개 모두 신규 Index 사용, 임시 정렬 0건 |
| Metadata·Migration | PASS — Index 3개 이름·Column 순서 일치 |
| Upgrade·downgrade | PASS — row·기존 Index·revision·무결성 보존 |
| Cursor 회귀 | PASS — 27 passed |
| Workspace 선별 회귀 | PASS — 78 passed (`27 + 51`) |
| Migration Safety | PASS — 10 passed |
| Windows FFmpeg integration | PASS — 4 passed, 19 deselected |
| Python compile | PASS |
| 변경 Python Ruff lint·format | PASS — 4개 파일 |
| 전체 Backend Ruff format | PASS — 254개 파일 |
| Route·OpenAPI | PASS — Route 45, APIRoute 41, path 34, operation 43, v1 Resource path 0 |
| SQLAlchemy metadata | PASS — 35개 Table |
| Alembic head | PASS — `20260807_0013` 단일 head |
| 전체 Backend suite | WARNING — 단일 실행은 30분 상한에서 82%까지 실패 없이 진행, 마지막 75건 별도 실행은 74 passed·1 skipped |
| 전체 Backend Ruff lint | WARNING — 이번 변경 밖 기존 파일의 46건, 변경 파일 신규 오류 0건 |

## 4. 상태와 제한

- Alembic source head는 `20260807_0013`입니다.
- 실제 사용자 DB는 `20260806_0012`이며 신규 Index를 적용하지 않았습니다.
- 기존 단일 Index는 제거하지 않았습니다. prefix 중복과 write 비용은 실제 적용 후 통계 기반 WARNING입니다.
- Resource Endpoint와 실제 목록 API는 아직 공개하지 않았습니다.
- Cursor codec·payload, Repository·Service 의미, Route·OpenAPI는 변경하지 않았습니다.
- 전체 Backend suite 단일 실행은 Windows 로컬 환경에서 30분 상한에 도달해 완료 합계를 회수하지 못했습니다. 82%까지 실패가 없었고 수집 순서의 마지막 75건을 별도로 모두 통과했지만 이를 단일 `348 passed`로 표현하지 않습니다.
- `ruff check backend`의 46건은 기존 `develop` 파일에서 발생했고 이번 변경 Python 파일은 모두 통과했습니다. 범위 밖 lint 정리는 별도 PR에서 처리합니다.

## 5. 최종 판정

신규 Index·Migration·Query Plan 계약의 BLOCKER는 0건입니다. 기존 단일 Index prefix 중복, 실제 사용자 DB 미적용, 전체 Backend 단일 실행 시간 상한과 기존 Ruff lint debt를 WARNING으로 유지합니다. Resource Endpoint와 실제 사용자 DB 적용은 별도 승인 작업입니다.
