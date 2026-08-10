# Bootstrap CLI revision 0017 검증

> 문서 상태: [완료]
> 최종 수정일: 2026-08-10
> 관련 기능: 명시적 Workspace Bootstrap CLI revision Gate
> 관련 문서: [Workspace API 공통 기반과 Bootstrap](../../docs/06-api/workspace-api-foundation-bootstrap.md), [DB 전환 전략](../../docs/07-database/database-redesign-migration-strategy.md)

## 1. 목적과 범위

Bootstrap CLI의 exact revision Gate를 Alembic source head와 기존 검증 기록상 실제 사용자 DB revision인 `20260810_0017`에 맞췄습니다. 이번 작업은 revision 상수, 경계 테스트와 현재 상태 문서만 변경했습니다. 실제 사용자 DB 접근, Bootstrap 실행, Alembic upgrade·downgrade와 schema 변경은 수행하지 않았습니다.

## 2. 확정한 계약

- Bootstrap 대상 revision은 `20260810_0017`과 정확히 일치해야 합니다.
- minimum revision 또는 일반 Alembic DAG 호환 판정은 사용하지 않습니다.
- `20260809_0016` 이하의 과거 revision, 미래·알 수 없는·형식 오류 revision을 fail-closed로 거부합니다.
- 빈 문자열과 `NULL` revision, revision row 0개 또는 복수도 거부합니다.
- Gate 검증 전후에 Workspace row를 생성하거나 변경하지 않습니다.

## 3. 검증 결과

| 검증 | 결과 |
|---|---|
| Bootstrap CLI 전체 | PASS — 23 passed |
| API Foundation·Workspace API | PASS — 20 passed |
| Workspace Migration·Artifact Catalog | PASS — 12 passed |
| Workspace Job schema migration | PASS — 2 passed |
| CompositionSnapshot API | PASS — 27 passed |
| Python compile | PASS |
| 변경 Python Ruff lint·format | PASS — 2개 파일 |
| FastAPI Route·`APIRoute` | PASS — 70개·66개 |
| OpenAPI Path·Operation | PASS — 49개·68개 |
| Workspace Resource API | PASS — 25/64 |
| Job API | PASS — 0/5 유지 |
| Metadata·Alembic | PASS — 36개 Table·단일 `20260810_0017` head |
| `git diff --check` | PASS |

모든 DB 기반 테스트는 실제 사용자 DB와 분리된 임시 SQLite에서 실행했습니다. 실제 Bootstrap과 실제 사용자 DB Inventory는 실행하지 않았습니다.

## 4. 문서 정합성

현재 상태 문서는 Alembic source head, 기존 검증 기록상 실제 사용자 DB revision과 Bootstrap target을 모두 `20260810_0017`로 표시합니다. Resource API 25/64, Job API 0/5, Metadata 36개 Table과 Runtime Table 14개의 source of truth 상태는 변경하지 않았습니다. 과거 CHANGELOG와 검증 보고서의 당시 revision 기록은 역사 자료로 보존했습니다.

## 5. 남은 경고와 후속 작업

- Job의 Workspace scope와 input/output role은 기존 row 보존을 위한 nullable staging입니다.
- Workspace Job Cursor·Worker·Service state machine·Provider completion Unit of Work와 공개 Job API 5개는 미구현입니다.
- 기존 Pipeline file Route의 OpenAPI operation ID 중복 경고가 유지됩니다.
- 실제 사용자 DB Bootstrap은 별도 명시적 승인과 사전 점검 전에는 실행하지 않습니다.
