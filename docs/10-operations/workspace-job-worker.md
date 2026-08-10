# Workspace Job Worker 운영 경계

> 상태: [완료: 실행 기반] / [미구현: background runtime·실제 Provider transport]

`JobWorkerService.run_once()`는 queued Job 하나를 claim하고 dispatch한 뒤 Completion UoW 또는 안전한 terminal failure로 종료한다. claim·heartbeat·recovery는 각각 짧은 transaction이며 Provider 실행 동안 SQLite write transaction을 열어 두지 않는다.

- 기본 lease는 5분이며 30초~1시간만 허용한다.
- Provider adapter는 `ProviderExecutionContext.heartbeat()`를 장시간 실행 중 호출해야 한다.
- 만료 lease는 재queue하지 않고 retryable failure로 종료한다.
- Provider 실패의 공개 `error_code`는 64자 이하의 `[A-Z][A-Z0-9_]*` machine code만 허용하며, 그 밖의 값은 `PROVIDER_EXECUTION_FAILED`로 대체한다. 원본 오류·경로·credential·stack trace는 공개 오류에 저장하지 않는다.
- 동일 Job의 transport retry는 `workspace-job:<job_id>` canonical idempotency key를 재사용한다. 같은 Provider 결과의 Completion UoW replay는 기존 결과를 반환하고 `AssetVersion`·`Artifact`·Catalog·`JobOutput`·`ModelUsage`를 중복 생성하지 않는다.
- Provider가 `CANCELLED`를 명시적으로 반환하면 cancel marker 유무와 관계없이 Job을 `cancelled`로 종료하며 Completion UoW와 출력 lineage를 생성하지 않는다. 실행 중 marker가 설정된 기존 success race도 cancel 우선이다.
- 실제 daemon, scheduler, DohaLM·DohaAudio·DohaVocal transport와 외부 호출은 아직 없다.
