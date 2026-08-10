# Workspace Job Worker 운영 경계

> 상태: [완료: 실행 기반] / [미구현: background runtime·실제 Provider transport]

`JobWorkerService.run_once()`는 queued Job 하나를 claim하고 dispatch한 뒤 Completion UoW 또는 안전한 terminal failure로 종료한다. claim·heartbeat·recovery는 각각 짧은 transaction이며 Provider 실행 동안 SQLite write transaction을 열어 두지 않는다.

- 기본 lease는 5분이며 30초~1시간만 허용한다.
- Provider adapter는 `ProviderExecutionContext.heartbeat()`를 장시간 실행 중 호출해야 한다.
- 만료 lease는 재queue하지 않고 retryable failure로 종료한다.
- 실제 daemon, scheduler, DohaLM·DohaAudio·DohaVocal transport와 외부 호출은 아직 없다.
