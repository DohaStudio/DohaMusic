# D1 Composition Transition 검증

> 문서 상태: [검토 중]
> 최종 수정일: 2026-08-21
> 관련 기능: D1-A 이후 Workspace Bootstrap·무선택 Transition
> 관련 문서: [D1 Composition Read](../../docs/06-api/composition-read-workspace.md), [Bootstrap](../../docs/06-api/workspace-api-foundation-bootstrap.md), [DB Migration 전략](../../docs/07-database/database-redesign-migration-strategy.md), [actual DB Runbook](../../docs/10-operations/workspace-db-migration-runbook.md)

## 1. 범위와 authority

Legacy `projects`, Workspace·Composition·Job Entity와 bootstrap metadata를 조사했으며 project-level selected CompositionSnapshot을 뜻하는 pre-D1-A persistence는 없습니다. Workspace Job의 `composition_snapshot_id`는 개별 Job 입력을 고정할 뿐 Project current selection이 아닙니다.

```text
NO_PREEXISTING_SELECTION_AUTHORITY
authoritative backfill row = 0
expected selection mutation row = 0
```

Snapshot이 하나뿐이어도 자동 선택하지 않습니다. latest/newest/first/최대 ID fallback, Legacy read fallback과 dual write를 추가하지 않았습니다. 기존 valid `ProjectCompositionSelection`만 보존하고 dangling·cross-Project 상태는 fail-closed입니다.

## 2. 구현 경계

- Alembic `0018`: schema transition만 소유하며 신규 revision은 추가하지 않음
- Bootstrap CLI: exact revision과 D1 필수 Table·PK·unique·same-Project 복합 FK·Snapshot identity Index 검증
- Workspace Service transaction: Workspace 생성·재사용과 active Project transition inventory를 원자적으로 실행
- Composition Repository: Project별 Snapshot 수와 selection 무결성을 단일 batch query로 조회
- Aggregate GET/PATCH: D1-A의 `empty`, `selection_required`, `ready` 의미와 명시적 선택 경계를 변경하지 않음

## 3. isolated 검증

모든 DB 검증은 임시 SQLite에서 수행합니다. actual 사용자 DB에는 접근하지 않았고 migration·Bootstrap·backfill도 실행하지 않았습니다.

| 검증 | 결과 |
|---|---|
| D1 Transition 신규 시나리오 16개 | PASS |
| D1-A·migration·Snapshot·Workspace 직접 회귀 | PASS — 97 passed |
| Bootstrap 기존 실패 경로·생성·재사용 호환성 재검증 | PASS — 4 passed |
| Snapshot 0 / 1 / 복수와 selection row 0 | PASS |
| Bootstrap·zero-backfill 3회 멱등 | PASS |
| valid selection 보존 | PASS |
| dangling·cross-Project fail-closed | PASS |
| 강제 실패 transaction rollback | PASS |
| engine dispose 후 reopen/restart | PASS |
| Aggregate `empty → selection_required → PATCH → ready` | PASS |
| inventory N+1·Query Plan | PASS — 단일 query, workspace/Project·Snapshot Index 사용, `TEMP B-TREE` 0 |
| 변경 Python Ruff·format / compile / `git diff --check` | PASS |
| Markdown 상대 링크 / fenced code block | PASS — 오류 0 |
| Alembic source / metadata | PASS — `20260820_0018`, application Table 37개, 신규 migration 0 |
| API surface | PASS — Route 77, `APIRoute` 73, OpenAPI path 55·operation 75, 신규 route 0 |

97개 직접 회귀에는 `0017 → 0018`, `0018 → 0017`, historical migration round-trip, D1-A aggregate·Snapshot·Workspace API가 포함됩니다. Python 3.12 SQLite datetime adapter warning과 기존 Pipeline HEAD OpenAPI duplicate operation ID 2건은 이번 변경과 분리된 baseline입니다. 전체 Ruff baseline도 기존 `ai_worker/scripts` E402 3건만 재현됐으며 변경 파일 Ruff는 통과했습니다.

## 4. 판단과 남은 Gate

Backend source와 isolated transition 계약은 D1-B 설계를 시작할 수 있으므로 `PRE_D1_B_READY=true`입니다. 이는 Frontend 완료나 actual DB 전환 완료를 의미하지 않습니다.

```text
PRODUCTION_DB_TRANSITION_PENDING
```

보고된 actual DB는 `20260810_0017`, source는 `20260820_0018`입니다. actual 적용은 backup·revision/path·dry validation·row count·authority·예상 mutation·ambiguity/cross-Project·rollback·Aggregate 검증과 별도 사용자 승인을 요구합니다.
