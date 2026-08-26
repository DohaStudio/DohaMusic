# Workspace Job Worker 운영 경계

> 상태: [완료: 실행 기반·Provider Job persistence·Result trust gate·durable PayloadLocator·verified staging·payload acquisition orchestration·reconciliation 계약] / [미구현: background runtime·Provider/Worker dispatch·Artifact ingestion·Completion 연결]

운영 수명주기의 authoritative source는 [DohaVocal Worker Reconciliation Contract](../03-architecture/dohavocal-worker-reconciliation-contract.md)와 [Workspace Worker Re-entry Lifecycle](../03-architecture/workspace-worker-reentry-lifecycle.md)이다. Provider `succeeded`만으로 Workspace Job을 성공 처리하지 않으며 trust gate·trusted payload·Completion commit 전까지 `running`을 유지한다.

Provider Job identity DB persistence는 [구현] 상태다. 후속 Dispatcher는 CreateJob 응답 직후 [Provider Job Persistence Contract](../03-architecture/provider-job-persistence.md)의 Service로 binding을 기록하고, 재시작 시 Workspace Job ID로 history/latest를 조회해야 한다. Provider 상태는 binding table이 아니라 Provider Runtime에서 조회한다.

CreateJob 성공과 binding commit 사이 crash window는 남아 있다. Worker wiring은 `workspace-job:<job_id>` stable idempotency key로 Provider 응답을 복구한 뒤 동일 identity를 저장해야 하며, crash 후 무조건 새 Provider Job을 생성해서는 안 된다. 같은 Job의 동시 retry 발급과 active execution 선택도 이 운영 계층에서 직렬화해야 한다.

Provider polling이 성공 metadata를 반환하면 [Provider Result Ingestion Contract](../03-architecture/provider-result-ingestion-contract.md)의 trust gate를 먼저 호출해야 한다. `payload_present=false` 결과는 Provider failure가 아니지만 Artifact ingestion도 Workspace completion도 아니다. Worker는 fake path를 만들거나 descriptor checksum을 payload checksum으로 넘겨서는 안 되며, 현재 상태 machine을 바꾸지 않은 채 후속 payload/reconciliation 정책을 기다린다.

`JobWorkerService.run_once()`는 queued Job 하나를 claim하고 dispatch한 뒤 Completion UoW 또는 안전한 terminal failure로 종료한다. claim·heartbeat·recovery는 각각 짧은 transaction이며 Provider 실행 동안 SQLite write transaction을 열어 두지 않는다.

- 기본 lease는 5분이며 30초~1시간만 허용한다.
- Provider adapter는 `ProviderExecutionContext.heartbeat()`를 장시간 실행 중 호출해야 한다.
- CURRENT runtime은 만료 lease를 retryable failure로 종료한다. TARGET은 replay-safe Provider-backed Job의 yielded/expired claim을 `LEASE_EXPIRY_RECLAIMABLE` CAS로 이전하지만 후속 구현과 activation gate 전에는 운영 기능으로 사용하지 않는다. 기존 row의 무조건적인 재queue는 금지한다.
- Provider 실패의 공개 `error_code`는 64자 이하의 `[A-Z][A-Z0-9_]*` machine code만 허용하며, 그 밖의 값은 `PROVIDER_EXECUTION_FAILED`로 대체한다. 원본 오류·경로·credential·stack trace는 공개 오류에 저장하지 않는다.
- 동일 Job의 transport retry는 `workspace-job:<job_id>` canonical idempotency key를 재사용한다. 같은 Provider 결과의 Completion UoW replay는 기존 결과를 반환하고 `AssetVersion`·`Artifact`·Catalog·`JobOutput`·`ModelUsage`를 중복 생성하지 않는다.
- Provider가 `CANCELLED`를 명시적으로 반환하면 cancel marker 유무와 관계없이 Job을 `cancelled`로 종료하며 Completion UoW와 출력 lineage를 생성하지 않는다. 실행 중 marker가 설정된 기존 success race도 cancel 우선이다.
- 실제 daemon, scheduler와 DohaLM·DohaAudio·DohaVocal Worker dispatch는 아직 없다. DohaVocal acquisition orchestration service는 composition root에 등록했지만 `JobWorkerService` caller에는 연결하지 않았고 Artifact ingestion·Completion도 수행하지 않는다.
