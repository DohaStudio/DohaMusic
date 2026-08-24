# ADR-043: DohaVocal Worker Reconciliation Authority

> 상태: 승인
> 결정일: 2026-08-24

## Context

DohaMusic에는 Workspace Job Worker, DohaVocal HTTP Consumer, Provider Job Persistence, metadata Result trust gate, process-local Trusted Payload resolver와 payload-backed Completion UoW가 각각 구현되어 있다. 그러나 Provider가 성공한 뒤 metadata-only 결과에서 Workspace Completion까지 이어지는 상태, lease, retry, payload와 role mapping 권위는 하나의 계약으로 고정되지 않았다. concrete wiring 전에 이 경계를 결정하지 않으면 Provider success를 Workspace success로 오인하거나 crash 뒤 inference를 중복 실행할 위험이 있다.

## Decision

1. Provider `succeeded`와 Workspace Job `succeeded`를 분리한다. Workspace 성공은 trusted payload와 DohaMusic-owned output commit 뒤에만 확정한다.
2. 공개 5-state는 유지하며 reconciliation 중에는 `running`을 사용한다. 기존 `Job.stage`의 내부 단계 vocabulary만 사용하고 schema/API를 변경하지 않는다.
3. claim lease는 활성 invocation이 heartbeat로 소유한다. DB transaction은 network/I/O를 감싸지 않는다. 이 ADR 시점에는 현재 lease expiry failure를 resume로 가장하지 않고 lease 간 재진입을 `DURABLE_EXECUTION_HANDOFF_REQUIRED`로 남겼다. 후속 [ADR-044](ADR-044-workspace-worker-reentry-lifecycle-authority.md)는 replay-safe Job의 목표 정책을 `LEASE_EXPIRY_RECLAIMABLE`로, [ADR-046](ADR-046-durable-execution-handoff-authority.md)은 locator 전 새 durable handoff storage 불필요를 확정한다. runtime 구현 전의 failure 동작은 유지한다.
4. Provider Create 복구는 `workspace-job:<job_id>`와 같은 immutable request fingerprint의 replay로 동일 Provider Job identity를 회수한다. 무조건 새 Provider Job을 만들지 않는다.
5. Provider retry는 같은 Workspace Job의 새 binding을 append하고 Workspace retry는 새 Workspace Job을 만든다.
6. 모든 Provider success Result는 기존 trust gate를 통과해야 한다. metadata-only Result는 정상이나 Completion에는 부적격하다.
7. payload acquisition, checksum, staging, Artifact ingestion과 Workspace commit은 DohaMusic이 소유한다. production restart reconciliation에는 `DURABLE_LOCATOR_REQUIRED`다.
8. Provider candidate role은 DohaMusic-owned mapping에서 Workspace output role로 변환한다.
9. payload-layer 실패나 Completion replay를 이유로 Provider inference를 자동 재실행하지 않는다.
10. 취소는 Completion commit 전까지 우선하며 commit 뒤 성공 Job은 취소할 수 없다.

세부 reconciliation, retry, cancellation과 crash matrix는 [DohaVocal Worker Reconciliation Contract](../03-architecture/dohavocal-worker-reconciliation-contract.md)를, same-Job ownership transfer는 [Workspace Worker Re-entry Lifecycle](../03-architecture/workspace-worker-reentry-lifecycle.md)을 authoritative source로 삼는다.

## Consequences

- concrete wiring은 공개 상태 enum, DB schema, API 또는 Provider 계약을 임의로 확장할 수 없다.
- bounded single-invocation wiring은 가능하지만 ADR-044의 reclaim runtime, durable locator, payload downloader와 Completion adapter가 없으면 end-to-end production completion을 완료로 선언할 수 없다.
- Provider Job binding과 Completion idempotency를 재사용해 crash replay의 중복 side effect를 제한한다.
- 현재 process-local locator와 미구현 reclaim runtime의 한계를 문서와 운영 상태에서 계속 드러낸다.

## Rejected alternatives

- Provider success 즉시 Workspace success 처리: trusted payload와 Workspace lineage가 없어 거부한다.
- 새 public reconciliation state 또는 schema 추가: 현재 계약 확정에 필요하지 않아 거부한다.
- crash마다 Provider Job 재생성: 비용·중복 side effect 위험 때문에 거부한다.
- Provider path/URI를 Completion에 직접 전달: DohaMusic storage trust boundary를 우회하므로 거부한다.
- process-local locator를 production restart authority로 사용: durability가 없어 거부한다.

## Scope

이 ADR은 문서와 기존 테스트로 계약을 고정한다. concrete Dispatcher, transport wiring, polling code, downloader, Completion adapter, 인증, daemon, DB/Alembic/API/Frontend 또는 다른 Provider 저장소 변경은 포함하지 않는다.
