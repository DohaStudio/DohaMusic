# Workspace Worker Re-entry Lifecycle

> 문서 상태: 승인된 목표 계약, 런타임 미구현
> 최종 수정일: 2026-08-24
> 관련 결정: [ADR-044](../11-decisions/ADR-044-workspace-worker-reentry-lifecycle-authority.md), [ADR-046](../11-decisions/ADR-046-durable-execution-handoff-authority.md)

## 1. 결정

Workspace Worker의 lease 정책은 `LEASE_EXPIRY_RECLAIMABLE`이다. replay-safe로 등록된 Provider-backed Job은 명시적으로 yield되었거나 lease가 만료되었을 때 공개 상태를 `running`으로 유지한 채 같은 Job을 atomic reclaim할 수 있다. `waiting`, `paused`, `reconciling` 같은 공개 상태나 새 Column은 추가하지 않는다.

이 문서는 목표 authority다. 현재 구현의 `recover_expired_claim()`은 여전히 만료된 `running` Job을 `WORKER_LEASE_EXPIRED`, retryable `true`의 `failed`로 종료한다. 후속 구현이 이 계약과 activation gate를 갖추기 전에는 reclaim을 구현된 기능으로 간주하지 않는다.

적용 대상은 다음 조건을 모두 만족하는 Job type이다.

- concrete dispatcher registry가 immutable request와 안정적인 Provider idempotency를 이용한 replay-safe resume 대상으로 명시한다.
- Provider binding 또는 동일 `workspace-job:<job_id>` key와 동일 fingerprint의 Create replay로 Provider identity를 복구할 수 있다.
- 입력 참조와 reconciliation에 필요한 값이 durable하다.

현재 범위에서는 DohaVocal Provider-backed Job을 위한 계약만 확정한다. 등록되지 않은 Job과 legacy Worker는 자동 reclaim하지 않는다.

## 2. 재진입 상황 분류

| 상황 | durable 표현 | 다음 동작 | terminal | same-Job resume |
|---|---|---|---|---|
| graceful bounded yield | `running`, claim tuple 전부 `NULL` | later reclaim | 아니요 | 예 |
| Worker process crash | `running`, claim 존재, lease 만료 | lease 뒤 atomic reclaim | 아니요 | 예 |
| explicit shutdown | 가능하면 graceful yield, 불가능하면 lease 만료 | yield 또는 expiry reclaim | 아니요 | 예 |
| transient Provider wait | binding을 보존하고 graceful yield | 같은 Provider Job 조회 | 아니요 | 예 |
| payload reconciliation wait | durable resume input이 있을 때만 yield | locator/result 재검증 뒤 계속 | 아니요 | 조건부 |
| cancellation | `cancel_requested_at` 존재 | cancellation reconciliation 우선 | 취소 완료 시 예 | 실행 resume 아니요 |
| Provider/Workspace terminal | terminal status | mutation 없음 | 예 | 아니요 |

graceful bounded wait의 종료는 Worker 실패가 아니다. Provider가 `queued` 또는 `running`이고 invocation budget만 끝났다면 Workspace Job을 실패시키지 않고 claim을 yield한다. 반대로 crash는 명시적 release 없이 heartbeat가 끊긴 경우이며 lease 만료 전에는 다른 Worker가 소유권을 빼앗지 않는다.

graceful yield는 Provider execution cancel, Provider retry 또는 새 Workspace retry Job 생성을 뜻하지 않는다. 기존 Provider execution과 binding을 그대로 보존하고 현재 Worker invocation의 ownership만 반납한다.

Provider가 `succeeded`여도 payload가 준비되지 않았다면 Provider inference를 다시 실행하지 않는다. durable locator row가 아직 발급되지 않았으면 Result replay로 source descriptor를 복구하고, row가 있더라도 verified durable staging이 없으면 payload recovery가 완료되었다고 간주하지 않는다. process-local locator는 restart authority가 아니다.

## 3. Durable 표현과 public state

공개 상태는 `queued`, `running`, `succeeded`, `failed`, `cancelled` 다섯 개를 유지한다. ownership transfer는 내부 `running -> running` 전이이다.

- active claim: `claim_token`, `claimed_by`, `lease_expires_at`, `heartbeat_at`가 존재하고 lease가 아직 만료되지 않은 tuple이다. token·worker 일치만으로 만료 claim의 권한을 되살릴 수 없다.
- yielded claim: 네 필드가 모두 `NULL`이고 status는 `running`이다.
- expired claim: active claim identity는 남아 있고 `lease_expires_at < now`이다.
- partial-null claim tuple은 유효한 yield가 아니며 자동 reclaim하지 않고 운영 점검 대상으로 둔다.
- `started_at`, `stage`, progress, Provider binding과 request identity는 yield/reclaim 중 보존한다. `completed_at`은 terminal commit 전까지 `NULL`이다.

기존 Column만으로 표현 가능하므로 schema와 Alembic은 필요하지 않다. 후속 activation은 배포 전에 기존 `running` row를 inventory하고 eligibility, fingerprint, binding을 검증해야 한다. activation 이전에 만들어진 row를 근거 없이 자동 reclaim하지 않는다.

## 4. Claim token과 attempt authority

claim token은 Worker invocation ownership의 유일한 identity authority이며 유효한 lease와 함께 사용한다. 현재 token·worker와 unexpired lease를 모두 만족하는 owner만 heartbeat, stage/progress update, yield, finish, fail, cancellation-aware completion을 수행할 수 있다. Worker ID나 Provider binding은 token을 대체하지 않는다.

claim 또는 reclaim이 성공할 때마다 새 무작위 token을 발급하고 `attempt`를 1 증가시킨다. `attempt`는 같은 Workspace Job의 Worker ownership generation/claim 횟수이며 Provider retry 횟수나 새 Workspace retry Job 횟수가 아니다. transfer가 commit되는 즉시 이전 token의 모든 mutation은 0건이어야 한다.

stage는 durable observability metadata이지만 side-effect proof나 resume cursor가 아니다. 예를 들어 `stage == provider_wait`만으로 Create 완료를 추론할 수 없다. active claim이 없는 동안 stage를 변경할 actor도 없다.

## 5. Atomic repository operation 계약

모든 operation은 Service가 소유한 짧은 DB transaction 안에서 conditional update/CAS로 수행한다. Repository는 `commit()` 또는 `rollback()`하지 않으며 Provider network나 파일 I/O를 transaction 안에서 수행하지 않는다. 성공 row 수는 정확히 1, 경쟁에서 진 경우는 0이어야 한다.

### `claim_queued_job()`

- precondition: `queued`, cancel marker 없음, active claim 없음, dispatcher eligibility 만족.
- postcondition: `running`, 새 token/worker/heartbeat/lease, `attempt + 1`, 최초 `started_at` 설정.

### `yield_running_job()`

- precondition: `running`, nonterminal, cancel marker 없음, 현재 token/worker와 unexpired lease 일치, Completion 미커밋, resume에 필요한 persistent Provider binding 존재. Provider Create 전에는 yield하지 않는다.
- postcondition: status·stage·attempt·started_at·binding 보존, claim token/worker/lease/heartbeat 전부 `NULL`.

### `reclaim_yielded_running_job()`

- precondition: `running`, nonterminal, cancel marker 없음, claim tuple 전부 `NULL`, eligibility 만족.
- postcondition: 새 token/worker/heartbeat/lease, `attempt + 1`; status는 `running`.

### `reclaim_expired_running_job()`

- precondition: `running`, nonterminal, cancel marker 없음, 기존 token과 lease 값이 CAS 조건과 일치, lease 만료, eligibility 만족.
- postcondition: 새 token/worker/heartbeat/lease, `attempt + 1`; 이전 token 즉시 무효, status는 `running`.

### `claim_cancel_reconciliation()`

- precondition: `running`, cancel marker 존재, claim이 yielded 또는 expired, terminal 아님.
- postcondition: cancellation propagation/cleanup만 수행할 새 token을 발급한다. Provider 실행을 정상 resume하거나 새로 Create할 권한은 없다.

### `heartbeat_claim()`, `update_claim_stage()`, `finish_claim()`, `fail_claim()`

- precondition: `running`, 현재 token/worker와 unexpired lease 일치, terminal 아님. service가 산정한 `now`와 기존 lease도 CAS 조건에 포함한다.
- postcondition: heartbeat는 lease를 연장하고 stage는 observability만 갱신한다. finish는 Completion 조건을 검증해 `succeeded`로 한 번만 전이하고, fail은 안전한 오류·retryability를 기록해 `failed`로 한 번만 전이한다. cancel marker가 있으면 성공 finish와 일반 fail보다 cancellation reconciliation이 우선한다.

## 6. Resume와 retry 경계

reclaim 뒤 resume는 stage가 아니라 binding과 Provider Runtime 조회로 결정한다.

1. exact/current binding이 있으면 그 Provider Job의 `GetJobStatus`를 먼저 호출한다. Create는 금지한다.
2. binding이 없으면 동일 `workspace-job:<job_id>`와 동일 immutable fingerprint로 Create replay한다. 다른 fingerprint는 conflict이며 새 Provider Job 생성을 허용하지 않는다.
3. Provider status와 binding을 재검증한 뒤 poll, result trust validation 또는 payload reconciliation을 계속한다.

Provider retry는 Worker reclaim과 별개다. 명시적 정책이 허용한 경우 같은 Workspace Job에 새 `ProviderJobBinding`을 append하며, 자동 retry는 금지한다. Provider `RetryJob`에 idempotency key가 없는 현재 계약은 별도 WARNING이다.

Workspace retry는 terminal old Job에서 새 Job을 만드는 동작이다. 새 `job_id`, 새 `workspace-job:<new_job_id>` scope를 사용하고 이전 claim이나 Provider binding을 자동 상속하지 않는다.

## 7. Cancellation과 terminal race

`cancel_requested_at`이 실행 resume보다 우선한다. 일반 reclaim CAS는 marker가 `NULL`일 때만 성공한다. yield/expiry 뒤 취소가 기록되면 cancellation 전용 claim만 획득하여 Provider cancel 전파, cleanup, 최종 `cancelled`를 수행한다.

일반 reclaim이 먼저 성공한 뒤 취소가 기록되면 현재 owner는 다음 외부 호출 전후와 Completion 전에 marker를 다시 확인하고 cancellation으로 전환한다. 취소 뒤 새 Provider Create나 정상 Completion은 금지한다.

Completion commit과 reclaim이 경쟁하면 다음 순서를 따른다.

- Completion이 먼저 terminal status를 commit하면 reclaim CAS는 0건이다.
- reclaim이 먼저 새 token을 commit하면 이전 token의 늦은 Completion, heartbeat, stage, finish는 0건이다.
- `succeeded`, `failed`, `cancelled`의 claim transfer는 항상 0건이다.

## 8. Crash/restart matrix

| case | persisted authority | current owner | next action | terminal | same-Job resume | Provider call behavior |
|---|---|---|---|---|---|---|
| Create 전 process crash | `running`, expired claim, binding 없음 | 유효 owner 없음 | expired claim CAS reclaim | 아니요 | 예 | 같은 key/fingerprint Create replay |
| Create response 뒤 binding commit 전 crash | binding 없음, Provider identity는 외부에 존재 가능 | 유효 owner 없음 | CAS reclaim 뒤 identity 회수 | 아니요 | 예 | 같은 key/fingerprint Create replay 필수 |
| binding commit 뒤 crash | exact binding 존재, expired claim | 유효 owner 없음 | CAS reclaim 뒤 status 조회 | 아니요 | 예 | Create 금지 |
| Provider wait의 graceful yield | `running`, binding 존재, claim tuple 전체 `NULL` | 없음 | yielded claim CAS reclaim | 아니요 | 예 | 같은 Provider Job status 조회 |
| clean shutdown | 가능하면 yielded claim, 아니면 기존 claim 보존 | yield 뒤 없음, 실패 시 lease 전 owner만 만료까지 기록상 존재 | yield reclaim 또는 lease expiry 대기 | 아니요 | 예 | cancel/retry/Create 자동 호출 금지 |
| process crash, lease 만료 전 | `running`, unexpired claim, heartbeat 중단 | 다른 Worker 없음; 이전 process는 소멸 | lease 만료까지 대기 | 아니요 | 아직 아니요 | 호출 금지 |
| lease expiry | `running`, expired claim | 유효 owner 없음 | eligible expired claim CAS reclaim | 아니요 | 예 | binding 유무에 따라 조회/replay |
| reclaim commit | 새 token·worker·heartbeat·lease, `attempt + 1` | 새 Worker 하나 | binding 기반 resume | 아니요 | 진행 중 | binding 있으면 조회, 없으면 same-key replay |
| old Worker late response | 새 active token 또는 terminal status | 새 Worker 또는 없음 | heartbeat/stage/finish/fail/Completion 모두 reject | 상태에 따름 | 영향 없음 | 결과 반영 금지 |
| Result validation 중 crash | binding/result identity, Workspace `running` | lease 만료 뒤 없음 | reclaim 뒤 result 재조회·trust gate | 아니요 | 예 | Retry/Create 금지 |
| payload reconciliation 중 crash | binding/result와 durable locator/checksum 범위 | lease 만료 뒤 없음 | immutable payload 재검증 | 아니요 | durable locator 조건부 예 | inference 재실행 금지 |
| Completion commit 전 crash | Workspace `running`, output commit 미완료 | lease 만료 뒤 없음 | current token으로 Completion replay | 아니요 | 예 | Provider 호출 불필요 |
| Completion commit 뒤 응답 전 crash | terminal Job과 outputs | 없음 | existing result 반환 또는 no-op | 예 | 아니요 | 모든 Provider mutation 금지 |

## 9. Security와 운영

claim token과 Worker ID는 내부 execution identity이며 공개 API, 로그, 오류, telemetry에 raw 값으로 노출하지 않는다. 안전한 machine code만 기록하고 private path, credential, Provider raw response를 저장하지 않는다.

후속 구현은 reclaim 성공/경쟁 패배, stale token 거부, lease age, yielded duration, cancellation 전용 claim을 민감정보 없이 관측해야 한다. 동시에 두 active claim이 존재하는 경우는 0이어야 한다.

## 10. 구현 의존성과 handoff 분석

이 결정으로 same-Job re-entry lifecycle blocker는 계약 수준에서 해소되었다. 후속 [Durable Execution Handoff Analysis](durable-execution-handoff-analysis.md)와 ADR-046은 Provider execution부터 Result validation까지 `NO_NEW_DURABLE_HANDOFF_STORAGE_REQUIRED`를 확정했다. payload locator 이후의 facts는 ADR-049 전용 persistence foundation에 보존하며 verified durable byte staging과 reclaim Runtime은 여전히 미구현이다.

후속 구현 의존성은 atomic reclaim repository operations, eligible dispatcher registry, concrete DohaVocal dispatch/transport, bounded polling과 shutdown yield, cancellation propagation, verified durable staging/downloader, Completion adapter, daemon/scheduler, production authentication이다. 본 문서 PR 자체는 Python, DB/schema, Alembic, API, Frontend, network 또는 Provider를 변경하지 않았다. 후속 ADR-049 PR이 별도 locator DB/schema foundation을 추가했다.
