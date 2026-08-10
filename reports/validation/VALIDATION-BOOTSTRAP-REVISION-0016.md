# Bootstrap CLI revision 0016 검증

> 문서 상태: [완료]
> 최종 수정일: 2026-08-10
> 관련 기능: 명시적 Workspace Bootstrap CLI revision Gate
> 관련 문서: [Workspace API 공통 기반과 Bootstrap](../../docs/06-api/workspace-api-foundation-bootstrap.md), [DB 전환 전략](../../docs/07-database/database-redesign-migration-strategy.md)

## 1. 목적과 범위

Bootstrap CLI가 과거 source head `20260807_0013`에 고정되어 현재 Alembic source head `20260809_0016`을 거부하던 기준 불일치를 해소했습니다. 이번 작업은 revision Gate와 그 경계 테스트만 변경했으며 실제 사용자 DB 접근, Bootstrap 실행, Alembic upgrade·downgrade와 schema 변경은 수행하지 않았습니다.

## 2. 결정한 정책

- Bootstrap 대상 revision은 현재 source head `20260809_0016`과 정확히 일치해야 합니다.
- 최소 revision 이상을 허용하지 않으며, 알 수 없는 미래 revision도 자동으로 호환된다고 판단하지 않습니다.
- `alembic_version` row는 정확히 하나여야 합니다.
- 과거·미래·알 수 없는·형식 오류 revision과 row 0개 또는 복수는 fail-closed로 거부합니다.
- 일반 Alembic DAG 비교, branch head 호환성 판정과 자동 Migration은 이번 범위에 도입하지 않았습니다.

## 3. 검증 항목

| 항목 | 기대 결과 |
|---|---|
| `20260809_0016` | Gate 통과 |
| `20260807_0013`·`20260807_0014`·`20260808_0015` | 거부 |
| 알 수 없는 미래 revision | 거부 |
| 형식 오류 revision | 거부 |
| revision row 0개·복수 | 거부 |
| Gate 검사 전후 Workspace row | 생성되지 않음 |

관련 Bootstrap·API Foundation·Workspace 회귀 테스트와 Python compile, Ruff, Markdown·상대 링크·fence·Mermaid, `git diff --check`를 검증 대상으로 삼았습니다.

## 4. 검증 결과

| 검증 | 결과 |
|---|---|
| Bootstrap CLI 전체 | PASS — 20 passed |
| API Foundation·Workspace API | PASS — 20 passed |
| Workspace Migration·Artifact Catalog | PASS — 12 passed |
| CompositionSnapshot 공식 API surface | PASS — 1 passed |
| Python compile | PASS |
| 변경 Python Ruff lint·format | PASS — 2개 파일 |
| 전체 Repository Ruff format | PASS — 541개 파일 |
| FastAPI Route·`APIRoute` | PASS — 70개·66개 |
| OpenAPI Path·Operation | PASS — 49개·68개 |
| Workspace Resource API | PASS — 25/64 |
| Metadata·Alembic | PASS — 36개 Table·단일 `20260809_0016` head |
| `git diff --check` | PASS |

여러 선별 suite를 한 번에 실행한 최초 검증은 Windows의 반복 SQLite schema 생성으로 240초 제한에 도달했습니다. 동일 범위를 목적별로 분리해 위 결과를 회수했으며 전체 Backend suite는 이번 최소 수정의 필수 범위가 아니므로 실행하지 않았습니다. 전체 `ruff check backend`에는 현재 기준선의 기존 파일에서 70개 지적이 남아 있지만 이번 변경 Python 2개 파일은 통과합니다. 기존 Pipeline file Route의 OpenAPI operation ID 중복과 Starlette TestClient 폐기 예정 경고도 이번 변경에서 새로 만들거나 수정하지 않았습니다.

## 5. 영향 범위

- Metadata 36개 Table과 Alembic source head `20260809_0016`은 변경하지 않았습니다.
- Resource API 진행도 25/64와 Runtime Table 14개의 source of truth 상태는 변경하지 않았습니다.
- Entity, Repository, Service, Resource API, Frontend, Provider와 실제 Artifact는 변경하지 않았습니다.
- 실제 사용자 DB와 실제 `DohaArtifacts`에는 접근하지 않았습니다.

## 6. 후속 작업

향후 source head가 변경되면 새 schema에서 Bootstrap 계약과 회귀 테스트를 다시 검토한 뒤 exact target을 명시적으로 갱신해야 합니다. branch head 또는 복수 Alembic DAG를 지원해야 한다면 별도 설계와 ADR 검토가 필요합니다.
