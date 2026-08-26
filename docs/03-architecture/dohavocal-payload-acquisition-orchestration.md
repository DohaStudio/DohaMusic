# DohaVocal Payload Acquisition Orchestration

> 문서 상태: [구현·검증 완료]
> 최종 수정일: 2026-08-26

## 구현 상태

```text
DohaVocal payload acquisition consumer: IMPLEMENTED
Verified durable staging: IMPLEMENTED
Payload acquisition orchestration: IMPLEMENTED
Artifact ingestion wiring: NOT IMPLEMENTED
Completion adapter: NOT IMPLEMENTED
Worker wiring: NOT IMPLEMENTED
Production authentication: NOT IMPLEMENTED
```

`VocalPayloadReconciliationService`는 trust gate가 만든
`TrustedProviderResultCandidate`, durable `PayloadLocator` ID와 caller-provided
`PayloadStagingAuthority`만 입력으로 받는다. raw URL·host·HTTP request를 받지 않으며
`provider_job_id + provider_artifact_id + source_id`는 검증된 candidate와 locator의 exact
binding에서만 만든다.

## 순서와 authority

```text
trusted candidate + locator
→ pre-network claim/cancel/rights 확인
→ locator Workspace/Provider binding·source availability 확인
→ GetPayloadContent
→ post-network latest claim/cancel/rights·locator lifecycle/revocation/revision 확인
→ PayloadStagingService
→ verified durable publish
→ staging post-I/O authority 확인
→ source_bound → verified_staged revision CAS
```

Provider network와 filesystem I/O 중 DB transaction은 없다. locator 조회와 최종 CAS만
각각 짧은 transaction을 사용한다. network 뒤 claim loss, cancellation, rights denial,
revocation, binding/revision conflict 또는 source expiry를 발견하면 staging과 CAS를 호출하지
않는다. transfer 도중 `available_until`을 지났다면 보수적으로 fail closed한다.

## bytes와 검증 책임

기존 HTTP acquisition adapter는 fixed `DOHAVOCAL_BASE_URL`, redirect 금지와 설정 기반 최대
크기 안에서 응답을 읽고 response context를 닫은 뒤 bounded `bytes`를 반환한다. 현재 port가
완전 buffer를 계약하므로 orchestration은 별도 network temp나 추가 bytes copy를 만들지 않고
그 객체 하나를 staging chunk로 전달한다.

- transport verification: Provider response status·Content-Type·Content-Length·SHA-256·size
- staging verification: durable object의 SHA-256·size·실제 WAV/FLAC/JSON media와 publish identity

두 검증은 서로 다른 trust boundary이므로 모두 유지한다. transport가 반환한 actual metadata로
locator의 expected facts를 덮어쓰지 않는다.

## restart·idempotency·동시성

- `source_bound` restart: persisted descriptor로 같은 source를 다시 acquire할 수 있다.
- network 중 crash: transient stream state는 폐기하며 partial HTTP progress는 저장하지 않는다.
- staging 중 crash: 기존 random partial·deterministic final·orphan adoption 계약을 사용한다.
- `verified_staged` restart/re-entry: Provider network 호출 없이 `open_verified`로 전체 재검증한다.
- 같은 locator 동시 실행: network 호출은 중복될 수 있지만 exclusive publish와 revision CAS가
  하나의 durable object/state로 수렴시킨다.
- verified object missing/tampered: 자동 reacquisition이나 backward transition 없이 fail closed한다.

## retry와 오류

자동 acquisition retry는 구현하지 않았다. retryable transport failure라도 이 foundation은 같은
source retry 시점·backoff authority를 추정하지 않으며 Provider `RetryJob`이나 새 Provider Job을
호출하지 않는다. unavailable, expired, access denied, transfer, integrity, rights, claim,
cancellation, staging과 locator conflict는 경로·URL·credential·raw response를 포함하지 않는
stable orchestration error로 변환한다.

## composition root와 제외 범위

`DOHA_ARTIFACT_STAGING_ROOT`가 설정된 경우 composition root는 config-owned HTTP acquisition
adapter와 reconciliation service를 생성하고 application shutdown에서 HTTP client를 닫는다.
서비스는 application state에서 사용할 수 있지만 `JobWorkerService`, dispatcher, daemon 또는
공개 API caller에는 연결하지 않았다. Artifact·AssetVersion·JobOutput 생성, Completion과
Workspace `succeeded` 전이는 모두 후속 범위다.
