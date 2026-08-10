# Workspace Job schema·Index Migration 검증

> 문서 상태: [완료]
> 최종 수정일: 2026-08-10
> 관련 기능: Workspace Job scope·role·cancel·claim/lease와 keyset 기반
> 관련 문서: [Workspace Job Foundation](../../docs/03-architecture/workspace-job-foundation.md), [Migration 전략](../../docs/07-database/database-redesign-migration-strategy.md), [ADR-033](../../docs/11-decisions/ADR-033-workspace-job-execution-boundary.md)

## 1. 범위

`develop` 기준선 `920ad664e6065e63652c47eabc51f722c3001827`에서 source revision `20260810_0017`을 추가했다. 실제 사용자 DB·`DATABASE_URL`·Bootstrap·Provider·Worker에는 접근하지 않았고 모든 DB 검증은 임시 SQLite에서 수행했다.

이번 범위는 Entity Column, additive Migration, 공개 목록 keyset Index 4개와 Worker 후보 Index 2개다. Job Cursor·Repository keyset·Service state machine·Worker claim/lease·Provider 호출·Job API 5개는 구현하지 않았다.

## 2. Schema 계약

| 대상 | 추가 내용 | 상태 |
|---|---|---|
| `jobs` | `workspace_id`, `cancel_requested_at`, `claim_token`, `claimed_by`, `lease_expires_at`, `heartbeat_at`, `attempt` | source 구현 |
| `job_inputs` | `input_role` | nullable staging |
| `job_outputs` | `output_role` | nullable staging |
| `model_usages` | 변경 없음 | 유지 |

기존 Job의 `workspace_id`는 연결된 Project에서 채우고 해석할 수 없는 row가 하나라도 있으면 upgrade를 중단한다. 기존 SQLite row와 하위 FK를 보존하기 위해 `workspace_id`와 role은 nullable staging으로 유지한다. 새 Job 생성은 Project의 `workspace_id`를 항상 기록한다. 역할의 의미 기반 backfill과 `NOT NULL` 강화는 실제 데이터 검증 후 별도 Migration에서 결정한다.

`attempt`는 기본값 0이며 `ck_jobs_attempt_nonnegative`로 음수를 거부한다. 공개 상태는 `queued`, `running`, `succeeded`, `failed`, `cancelled` 다섯 개를 유지한다.

## 3. Index와 Query Plan

| 용도 | Index |
|---|---|
| Workspace 전체 목록 | `ix_jobs_workspace_keyset` |
| Project filter | `ix_jobs_workspace_project_keyset` |
| status filter | `ix_jobs_workspace_status_keyset` |
| job type filter | `ix_jobs_workspace_type_keyset` |
| claim 후보 | `ix_jobs_claim_queue` |
| lease 만료 회수 후보 | `ix_jobs_lease_recovery` |

10,000 Job fixture에서 Workspace 전체와 Project·status·job type별 첫 page·다음 page를 비교했다. Migration 전에는 전체 scan 또는 기존 단일 Index와 `TEMP B-TREE` 정렬이 발생했다. Migration 후 모든 공식 단일 filter Query는 전용 Index를 사용하고 full scan과 `TEMP B-TREE`가 제거됐다. 복합 filter는 가장 선택적인 기존 후보 Index를 사용하고 임시 정렬이 발생하지 않아 조합별 대형 Index는 추가하지 않았다.

Worker 후보 Query도 별도로 검증했다. `status='queued' AND cancel_requested_at IS NULL ORDER BY created_at, job_id`는 `ix_jobs_claim_queue`, 만료된 running lease의 `ORDER BY lease_expires_at, job_id`는 `ix_jobs_lease_recovery`를 사용했고 두 Query 모두 `TEMP B-TREE`가 없었다. 이는 Index 적합성 검증이며 Worker 실행 로직 구현 완료를 의미하지 않는다.

## 4. Migration 왕복

| 검증 | 결과 |
|---|---|
| Alembic chain | 단일 `20260810_0017`, down revision `20260809_0016` |
| upgrade | 기존 Job 10,000개·JobInput·JobOutput 보존 |
| Workspace backfill | Project와 일치, 미해결 0개 |
| downgrade | `0017` Column·Index만 제거하고 `0016` 복원 |
| row count·결정적 digest | 전후 동일 |
| FK·integrity | PASS |
| metadata | 36개 Application Table 유지 |

## 5. 회귀 검증

| 묶음 | 결과 |
|---|---:|
| Job schema Migration | 2 passed |
| Workspace Entity·Repository·Service | 27 passed |
| Workspace 0012·Artifact Catalog Migration | 12 passed |
| 기존 Workspace·ProjectAsset·Asset keyset | 6 passed |
| Bootstrap | 20 passed |
| API Foundation | 11 passed |
| 합계 | 78 passed |

API Foundation은 Route 70개, `APIRoute` 66개, OpenAPI Path 49개, Operation 68개를 유지한다. Resource API는 25/64, Job API는 0/5다.

## 6. 판정

**PASS — source schema·Index 구현과 임시 SQLite 검증 완료**

- source head: `20260810_0017`
- 실제 사용자 DB: `20260809_0016`, 미접근·미변경
- Application Table: 36개
- Runtime Table: 14개, source of truth 유지
- Bootstrap target: `20260809_0016`; source `0017`에서는 fail-closed

## 7. 남은 WARNING과 후속 범위

- Python 3.12 SQLite datetime adapter 폐기 예정 경고가 기존 fixture에서 발생한다.
- Pipeline file route의 기존 OpenAPI operation ID 중복 경고가 유지된다.
- nullable staging role과 Workspace scope를 실제 데이터 검증 없이 `NOT NULL`로 강화하지 않는다.
- 실제 사용자 DB 적용은 read-only Inventory, backup·restore rehearsal, migration rehearsal과 명시적 승인이 필요하다.
- Job Cursor·Repository keyset·Service state machine·Worker claim/lease·completion Unit of Work·Provider 호출·API는 미구현이다.
