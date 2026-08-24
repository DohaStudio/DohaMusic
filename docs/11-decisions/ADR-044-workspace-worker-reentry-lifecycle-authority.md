# ADR-044: Workspace Worker Re-entry Lifecycle Authority

> 상태: 승인, 구현 미착수
> 결정일: 2026-08-24

## Context

ADR-033의 Workspace Worker는 만료된 `running` claim을 retryable failure로 종료한다. ADR-043은 Provider가 Worker invocation보다 오래 실행될 수 있으므로 bounded polling과 durable execution handoff 결정을 후속 과제로 남겼다. graceful bounded wait를 실패로 처리하면 Provider 실행은 계속되는데 Workspace Job은 terminal이 되고, 새 Workspace retry가 별도 idempotency scope에서 중복 inference를 만들 수 있다.

기존 Job에는 claim token, worker identity, lease, heartbeat, attempt, stage와 별도 Provider binding history가 있다. 같은 Job의 ownership transfer를 표현할 공개 상태나 별도 execution cursor가 반드시 필요한지는 결정되지 않았다.

## Decision

1. lease 정책으로 `LEASE_EXPIRY_RECLAIMABLE`을 선택한다.
2. replay-safe로 명시 등록된 Provider-backed Job만 yielded 또는 expired `running` claim을 atomic CAS로 reclaim할 수 있다.
3. 공개 다섯 상태를 유지한다. transfer는 내부 `running -> running`이며 yielded는 기존 claim tuple의 전체 `NULL`, crash는 만료 lease로 표현한다.
4. claim/reclaim마다 새 token을 발급하고 `attempt`를 증가시킨다. token은 ownership authority이며 이전 token은 commit 즉시 모든 mutation 권한을 잃는다.
5. stage는 observability일 뿐 side-effect proof가 아니다. binding이 있으면 Provider status 조회가 Create보다 우선하고, binding이 없을 때만 같은 key/fingerprint Create replay를 허용한다.
6. cancel marker는 일반 reclaim보다 우선한다. yielded/expired Job의 취소 전파에는 실행 resume 권한이 없는 cancellation 전용 claim을 사용한다.
7. terminal Job은 절대 reclaim하지 않는다. Service가 transaction을 소유하고 Repository와 Provider network는 transaction 경계를 넘지 않는다.
8. 기존 Column으로 표현 가능하므로 schema와 Alembic을 추가하지 않는다.
9. 현재 runtime의 terminal-on-expiry 동작은 후속 구현과 activation gate 전까지 유지한다. 기존 `running` row는 eligibility와 recovery facts를 검증하지 않고 자동 reclaim하지 않는다.

세부 precondition, race ordering과 crash matrix는 [Workspace Worker Re-entry Lifecycle](../03-architecture/workspace-worker-reentry-lifecycle.md)을 authority로 삼는다.

## Consequences

- 목표 lifecycle은 graceful bounded polling, process crash와 explicit shutdown 모두 새 Workspace retry 없이 같은 Provider execution을 복구할 경로를 정의한다. runtime 경로는 아직 구현되지 않았다.
- claim token CAS, binding과 Create replay가 중복 owner와 중복 Provider side effect를 제한한다.
- same-Job reclaim, Provider retry, Workspace retry의 counter와 identity scope가 분리된다.
- 구현에는 repository CAS, dispatcher eligibility, shutdown yield, cancellation reconciliation과 운영 관측이 필요하다.
- lifecycle blocker가 해소되었다. 후속 [ADR-045](ADR-045-durable-execution-handoff-authority.md)는 locator 전 Provider execution·Result validation에 새 durable handoff storage가 불필요하다고 확정한다.

이 결정은 ADR-033의 "만료 running row 자동 재실행 거부"를 무조건적인 정책에서 미등록/미검증 Job의 기본 안전 정책으로 좁히고, ADR-043의 `DURABLE_EXECUTION_HANDOFF_REQUIRED` 선행 조건을 구체화한다.

## Rejected alternatives

- `LEASE_EXPIRY_TERMINAL`: 단순하지만 crash 뒤 orphan Provider execution과 새 retry의 중복 inference 위험을 남긴다.
- `GRACEFUL_YIELD_RECLAIMABLE_LEASE_EXPIRY_TERMINAL`: 정상 bounded wait만 해결하고 실제 process crash blocker를 닫지 못한다.
- 새 public `waiting`/`paused`/`reconciling` 상태 또는 새 Column: 기존 claim tuple과 binding으로 필요한 ownership을 표현할 수 있어 불필요하다.
- stage를 resume cursor로 사용: side effect와 atomic하게 묶이지 않아 recovery proof가 될 수 없다.
- binding이 있는데 Create replay: 이미 알려진 Provider identity를 중복 실행할 수 있어 금지한다.

## Scope

이 ADR은 문서 계약만 변경한다. Worker/Dispatcher/Transport 구현, claim query, daemon, durable locator, downloader, Completion adapter, 인증, DB/schema/Alembic, API, Frontend와 실제 Provider 호출은 포함하지 않는다.
