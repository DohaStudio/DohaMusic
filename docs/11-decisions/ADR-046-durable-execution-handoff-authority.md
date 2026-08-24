# ADR-046: Durable Execution Handoff Authority

> 상태: 승인, Runtime 미구현
> 작성일: 2026-08-25
> 최종 수정일: 2026-08-25
> 관련 PR: 이 문서를 추가하는 Draft PR

## 배경

ADR-043은 장시간 Provider execution의 Worker invocation 간 복구를 `DURABLE_EXECUTION_HANDOFF_REQUIRED`로 남겼고, ADR-044는 replay-safe Provider-backed Job의 목표 lifecycle을 `LEASE_EXPIRY_RECLAIMABLE`로 확정했다. 남은 질문은 Provider execution과 Result validation 사이에 기존 Job·Provider binding 외의 독립 durable business cursor가 필요한지다.

현재 Workspace Job은 immutable request, ordered inputs, Provider·Manifest·contract identity, cancellation, claim·lease와 Completion 관계를 보존한다. `ProviderJobBinding`은 external identity와 retry lineage를 append-only로 보존한다. Create는 Workspace Job 기반 key와 deterministic fingerprint로 같은 identity를 replay하고 status와 Result는 다시 조회할 수 있다. Result trust validation은 mutation 없이 반복 가능하다.

## 문제

crash 또는 graceful yield 뒤 새 Worker가 다음 Provider operation을 안전하게 선택하기 위해 기존 persistence로 재구성할 수 없는 durable fact가 있는지, 있다면 Provider persistence 확장과 dedicated aggregate 중 어디가 최소 authority인지 결정해야 한다. payload locator 이후의 복구 책임은 이 질문과 분리해야 한다.

## 결정

1. 최종 architecture는 `NO_NEW_DURABLE_HANDOFF_STORAGE_REQUIRED`다.
2. binding이 있으면 exact/latest binding의 Provider status를 조회하고, 없으면 같은 `workspace-job:<job_id>`와 canonical request fingerprint로 Create를 replay한다.
3. wire Result, trusted candidate와 validation decision은 저장하지 않고 `GetResult`와 deterministic trust gate로 재구성한다.
4. stage, polling cursor, invocation deadline, raw response, `provider_success_seen`, `validation_passed`, `completion_started`와 `completion_done`은 resume authority가 아니다.
5. claim token은 현재 ownership authority이고 `attempt`는 Worker ownership generation이다. 둘 다 Provider business cursor나 retry attempt를 뜻하지 않는다.
6. Completion 전에는 current token과 eligibility를 검증하고, commit 후에는 terminal Job과 JobOutput·Artifact·AssetVersion·ModelUsage aggregate가 authority다.
7. locator 발급 이후의 cross-process payload identity는 `DURABLE_LOCATOR_REQUIRED`로 분리한다. execution handoff record가 이를 복제하지 않는다.
8. dedicated entity, Provider persistence extension, schema와 Alembic은 추가하지 않는다.

상세 inventory와 17개 crash 판정은 [Durable Execution Handoff Analysis](../03-architecture/durable-execution-handoff-analysis.md)를 authority로 삼는다.

## 선택 이유

- Create 전후의 불확실성은 same-key·same-fingerprint idempotency replay가 같은 external identity를 반환해 닫는다.
- binding 이후 status와 Result는 다시 읽을 수 있고 trust validation에는 mutation이 없다.
- current claim CAS와 Completion aggregate가 각각 concurrency와 terminal authority를 이미 소유한다.
- locator 전에는 기존 authority 없이 다음 동작을 결정할 수 없는 독립 durable fact가 없다.

## 장점과 단점

장점은 새 table·field·migration과 이중 authority를 만들지 않고 기존 경계로 복구 규칙을 설명할 수 있다는 점이다. 단점은 새 Worker가 status·Result와 trust validation을 반복할 수 있고, stage나 polling cursor로 최적화하지 않으므로 일부 read 비용이 다시 발생한다는 점이다. 이 비용은 정확한 recovery authority를 유지하기 위한 허용 가능한 trade-off다.

## 영향

- same-Job reclaim 뒤 다음 동작은 기존 durable facts와 Provider replay로 결정한다.
- Create 응답과 binding commit 사이 crash window는 별도 success flag가 아니라 Provider idempotency로 닫는다.
- Result fetch와 trust validation 뒤 crash는 read·validation replay로 복구한다.
- 중복 handoff state와 경쟁 authority를 만들지 않는다.
- 다음 architecture dependency는 durable payload locator다.
- CURRENT Runtime의 expiry failure, reclaim CAS 미구현과 concrete wiring 미구현 상태는 바뀌지 않는다.
- Provider `RetryJob`의 idempotency가 미정이므로 자동 Provider retry는 계속 금지한다.

## 대안

- `EXISTING_PROVIDER_PERSISTENCE_EXTENSION_REQUIRED`: binding에 없는 후보는 모두 Job에서 유도되거나 Provider read로 replay되며 locator는 별도 authority다.
- `DEDICATED_DURABLE_EXECUTION_HANDOFF_REQUIRED`: locator 전 독립적인 비재구성 business fact가 없다.
- stage 또는 flag 기반 resume cursor: side effect와 atomic하게 묶이지 않고 Provider/Completion authority와 충돌한다.
- raw Result 또는 trust decision 저장: replayable transient 값을 중복 보존해 stale 판정 위험을 만든다.

## 마이그레이션

DB schema와 Alembic migration은 없다. 기존 row backfill도 없다. 후속 Runtime은 ADR-044의 activation gate를 충족한 뒤 기존 Job·binding authority를 소비해야 하며, locator persistence는 별도 설계와 migration review를 거친다.

## 재검토 조건

다음 중 하나가 사실로 바뀌면 이 결정을 재검토한다.

- Provider Create가 같은 scope·fingerprint에 같은 external identity를 보장하지 않는다.
- `GetResult`가 single-use 또는 비결정적 side effect operation으로 바뀐다.
- Result trust validation이 hidden mutation을 갖는다.
- Completion이 current claim token과 terminal/output aggregate로 fence되지 않는다.
- locator 전에 기존 Job·binding에서 유도하거나 Provider read로 재생할 수 없는 business fact가 추가된다.

## 범위

이 ADR은 문서 authority만 확정한다. Worker reclaim, Repository CAS, Dispatcher, DohaVocal/HTTP wiring, polling, locator, downloader, Completion adapter, Artifact ingestion, 인증, daemon, DB/schema/Alembic, API, Frontend와 실제 Provider/model/GPU는 변경하지 않는다.
