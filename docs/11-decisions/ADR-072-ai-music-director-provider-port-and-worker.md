# ADR-072: AI Music Director Provider Port와 Worker 경계

- 상태: 승인
- 작성일: 2026-09-13
- 최종 수정일: 2026-09-13

## 결정

AI Music Director는 기존 동기 `ProviderDispatcher`의 의미를 변경하지 않고 전용
`MusicDirectorProvider` 포트를 사용한다. 포트는 submit, 상태 조회, terminal result 조회,
cancel을 제공하며 provider-native 상태와 payload를 application 경계 안으로 노출하지 않는다.

submit idempotency authority는 0034 `MusicDirectorProviderExecution.client_execution_key`다.
외부 execution ID는 0034 CAS 서비스로만 bind한다. 원격 성공은 provider execution의 성공이며,
Job 성공은 0035 whole-set proposal materialization까지 완료된 뒤에만 기록한다.

`MockMusicDirectorProvider`는 client key 기반의 결정적 remote registry로 response-loss와
replay를 증명하는 local/test adapter다. 실제 외부 provider와 credential은 후속 작업으로
남긴다. Worker는 proposal을 로컬 schema로 검증하고 digest를 로컬에서 계산한 뒤 기존 0035
materialization service에 전달한다. raw provider payload, claim token, storage path는 저장하지 않는다.
