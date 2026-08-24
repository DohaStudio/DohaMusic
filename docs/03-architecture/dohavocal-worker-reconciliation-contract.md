# DohaVocal Worker Reconciliation Contract

> 문서 상태: [승인: 구현 전 authoritative contract]
> 기준: DohaMusic `f6a727abddb6df5ca4a46173bd4a04b88ca60c65`
> 구현 상태: Workspace Worker·HTTP Transport·Provider Job Persistence·Result Ingestion·Trusted Payload process-local Foundation·Completion UoW는 각각 격리 구현, concrete wiring은 [미구현]
> 관련 결정: [ADR-043](../11-decisions/ADR-043-doha-vocal-worker-reconciliation-authority.md)

## 1. 범위와 핵심 결정

이 계약은 분리 구현된 Foundation을 향후 concrete DohaVocal Worker가 연결할 때 지켜야 할 수명주기, 소유권, 재시도와 복구 경계를 고정한다. 이 문서는 wiring, Provider 호출, downloader, Completion adapter, 인증, daemon, schema 또는 API를 구현하지 않는다.

```text
Provider succeeded != Workspace Job succeeded
```

Provider `succeeded`는 Provider 실행 완료만 뜻한다. Workspace `succeeded`는 신뢰된 결과와 적격 payload를 DohaMusic 소유 Artifact·AssetVersion·JobOutput·ModelUsage로 원자적으로 commit한 뒤에만 허용한다. `payload_present=false`인 metadata-only 성공은 정상 Provider 결과이지만 Workspace 출력은 아직 완료할 수 없다.

## 2. 상태와 내부 실행 단계

공개 상태는 `queued`, `running`, `succeeded`, `failed`, `cancelled` 다섯 개를 유지한다. Provider 성공 뒤 payload reconciliation 또는 Completion 대기 중인 Job도 terminal commit 전까지 `running`이다. 새 공개 enum이나 DB Column을 추가하지 않는다.

기존 `Job.stage`에 다음 내부 실행 단계 vocabulary를 사용할 수 있다. 이는 관측용 실행 단계이지 별도 상태 machine 또는 권한 근거가 아니다.

| 내부 단계 | 의미 |
|---|---|
| `provider_dispatch` | create/replay와 binding 확정 |
| `provider_wait` | bounded status polling |
| `provider_result_validation` | GetResult와 trust gate |
| `payload_reconciliation` | locator·acquisition·staging 검증 |
| `completion` | Completion UoW 준비와 commit |

단계 기록이 없거나 오래됐어도 binding, Provider authority, trusted locator와 Workspace DB 상태를 대체하지 않는다.

## 3. Lease와 재진입

- claim한 Worker invocation이 Workspace 실행 lease의 유일한 owner다. Provider 호출·polling·payload acquisition 동안에도 활성 실행 소유권은 heartbeat로 연장한다.
- network 또는 파일 I/O 동안 DB transaction을 열어 두지 않는다. claim, heartbeat, binding persistence와 Completion은 각각 Service가 소유한 짧은 transaction이다.
- polling은 request timeout, poll interval과 전체 invocation deadline을 분리한 bounded loop여야 한다. 각 외부 호출 전후에 취소와 lease 유효성을 확인한다.
- Provider가 전체 polling deadline에도 nonterminal이면 Dispatcher는 기존 `TIMED_OUT` 결과를 반환하고 Worker는 Workspace Job을 retryable failure로 종료한다. Provider retry나 새 Workspace Job을 자동 생성하지 않는다.
- 현재 구현은 만료 lease를 `WORKER_LEASE_EXPIRED` retryable failure로 종료하며 같은 Job을 자동 재queue하지 않는다. 따라서 Worker가 Provider `running` 상태에서 자발적으로 lease를 놓고 나중 invocation이 같은 Job을 안전하게 이어받는다고 가정할 수 없다.
- 장시간 실행을 lease 사이에서 이어받거나 process restart 뒤 `running` Job을 재개하려면 `DURABLE_EXECUTION_HANDOFF_REQUIRED`다. 그 전 concrete wiring은 한 invocation 안의 bounded polling만 지원한다고 표시해야 한다.
- 재진입 기능이 도입되면 latest binding은 poll 후보를 찾는 수단일 뿐 active/terminal authority가 아니다. Provider Runtime을 다시 조회하고 exact binding과 claim ownership을 재검증해야 한다.

## 4. Provider Create와 idempotency

canonical key는 `workspace-job:<job_id>`다. 같은 Workspace Job의 create 확인 재시도는 같은 key와 완전히 같은 request fingerprint를 사용한다. 공개 Workspace retry는 새 Job ID와 새 idempotency scope를 가진다.

Create 요청 전 crash는 binding이 없으면 같은 요청을 보낼 수 있다. Create 요청 송신 뒤 응답 여부가 불명확하거나 응답 수신 뒤 binding commit 전에 crash하면, Worker는 같은 key·fingerprint로 Create를 replay해 동일 Provider Job identity를 회수한 뒤 binding을 idempotent하게 기록한다. exact request가 아니거나 Provider가 동일 identity를 보장하지 않으면 fail closed한다. 무조건 새 Provider Job을 만들거나 추측성 lookup을 하지 않는다.

Provider retry operation은 Workspace retry와 다르다. 허용된 Provider retry는 같은 Workspace Job 아래 새 `ProviderJobBinding`을 append하고 `retry_of_provider_job_id`로 직전 binding을 가리킨다. 기존 binding을 갱신하거나 삭제하지 않는다. 동시 retry 발급과 active binding 선택은 Worker orchestration이 직렬화해야 한다.

## 5. Polling과 Result trust gate

Dispatcher는 create/replay 후 Provider status를 bounded polling한다. heartbeat 주기는 Worker lease 설정이, request timeout·poll interval·poll deadline은 Dispatcher 설정이 소유하되 전체 invocation deadline을 넘을 수 없다. 무한 polling, 암묵적 daemon, transport 자동 create 재시도는 금지한다.

Provider terminal success 뒤에는 반드시 다음 순서를 따른다.

```text
GetResult
→ ProviderResultIngestionService
→ trust/eligibility decision
→ payload reconciliation
→ Completion UoW
```

binding, owner, Provider Job identity, role, Manifest, lineage 또는 checksum scope 검증 실패는 Workspace가 fail closed하는 비재시도 보안·계약 실패다. raw Provider response나 Provider가 제시한 path·URI를 Completion에 직접 전달하지 않는다.

## 6. Metadata-only와 payload reconciliation

`payload_present=false`, `checksum_scope=metadata_descriptor`, `payload_reference=None`은 정상 metadata-only success다. Provider 실패로 바꾸지 않지만 Completion에 적격하지 않으며 fake path, synthetic locator 또는 descriptor checksum을 payload checksum으로 만들지 않는다.

Provider는 opaque payload identity/reference와 불변 결과 metadata만 제공한다. DohaMusic은 locator 신뢰, payload acquisition, byte 기반 checksum·size·media 검증, staging, Artifact ingestion과 Workspace commit을 소유한다. Provider가 DohaMusic storage에 직접 쓰거나 Workspace output role을 결정하지 않는다.

현재 `InMemoryTrustedPayloadRegistry`는 process-local test/Foundation 구현이다. crash/restart, multi-process 또는 lease 간 resume에 사용하기에 충분하지 않다. production reconciliation 전에 `DURABLE_LOCATOR_REQUIRED`이며 향후 durable record는 최소한 다음을 보존해야 한다.

- Provider Job binding, output role과 Provider Artifact identity의 immutable 결합
- opaque locator identity, 생성 시각, 선택적 TTL/expiry와 cleanup 상태
- trusted staging identity와 실제 byte checksum·size·media type
- 같은 identity의 재발급·replay 감사 기록; 기존 binding overwrite 금지

locator 만료 또는 일시적 저장소 장애는 동일 Provider 결과 identity와 immutable payload를 다시 검증할 수 있을 때만 payload-layer retry가 가능하다. 이를 이유로 비싼 Provider inference를 자동 재실행하지 않는다.

## 7. Output role canonicalization

Provider candidate role과 Workspace output role은 서로 다른 namespace다. DohaMusic의 Completion mapping만 다음 변환을 수행한다.

| Workspace Job type | Provider Result role | Workspace output role |
|---|---|---|
| `vocal_generation` | `generated_vocal_candidate` | `generated_vocal` |
| `voice_conversion` | `converted_vocal_candidate` | `converted_vocal` |
| `vocal_correction` | `corrected_vocal_candidate` | `corrected_vocal` |
| `vocal_analysis` | `vocal_analysis_result` | `vocal_analysis` |

현재 generic Completion은 `converted_vocal`만 지원한다. 나머지 mapping과 adapter는 후속 구현 의존성이며 이번 계약은 enum, schema 또는 code를 추가하지 않는다. 알 수 없거나 Job type과 맞지 않는 role은 fail closed한다.

## 8. Completion eligibility와 replay

다음 조건을 모두 만족하기 전에는 Completion UoW 호출을 금지한다.

- Provider terminal success
- expected Workspace Job·Provider binding·role mapping 검증
- Result trust gate, Manifest, lineage와 checksum scope 검증
- `payload_present=true`이며 지원되는 payload checksum scope
- trusted locator resolve와 실제 payload byte 검증
- expected Artifact kind·media·출력 개수 검증
- cancellation 없음, 유효한 claim token과 Completion 준비 완료

Artifact prepare 뒤 DB commit 전 crash 또는 DB failure는 commit되지 않은 이번 invocation의 publish만 identity 확인 후 보상하고 같은 trusted payload로 replay한다. Completion DB commit 뒤 Worker 응답 전 crash는 기존 aggregate를 replay해 반환하며 AssetVersion, Artifact, Catalog, JobOutput, ModelUsage 또는 terminal mutation을 중복 생성하지 않는다. Provider inference를 다시 실행하지 않는다.

## 9. Retry ownership matrix

| Failure | Owner | Authoritative action |
|---|---|---|
| Create 확인 전 transport timeout | Worker + Provider idempotency | 같은 key·fingerprint로 Create replay |
| Create conflict/replay | Provider idempotency | exact 동일 identity만 재사용, mismatch fail closed |
| Provider running deadline | Worker | `TIMED_OUT`으로 Workspace Job retryable failure; 자동 inference 재실행 금지, lease 간 resume는 durable handoff 전 미구현 |
| Provider retryable failure | Worker policy + Provider | 명시적 bounded Provider retry만 새 binding으로 append; Workspace retry와 혼합 금지 |
| Result trust failure | Workspace trust gate | 비재시도 fail closed |
| Locator unavailable/expired | Reconciliation | 동일 identity·immutable payload 재검증 가능할 때만 payload retry |
| Download failure | Payload layer | acquisition만 bounded retry, Provider 재실행 금지 |
| Checksum mismatch | Security / ingestion | 비재시도 fail closed, staging 격리·정리 |
| Completion DB failure | Completion UoW | 같은 resolved payload로 replay |
| Worker crash | Lease / recovery | 현재는 lease expiry failure; durable handoff 구현 뒤에만 same-Job resume |

Provider retry 횟수와 정책은 future configuration dependency다. 자동 Workspace Job 생성 또는 무제한 Provider retry는 허용하지 않는다.

## 10. Cancellation

| 시점 | 처리 |
|---|---|
| Provider create 전 | queued cancel이면 Provider를 호출하지 않고 `cancelled` |
| Provider queued/running | cancel marker 확인, 지원되는 cancel을 한 번 전파하고 bounded terminal 확인 |
| Provider succeeded, reconciliation 전 | Provider cancel 재호출 금지; acquisition을 시작하지 않고 감사 metadata를 보존한 채 정리 후 `cancelled` |
| payload download 중 | cooperative 중단, 이번 staging을 cleanup/quarantine |
| Completion 직전 | cancel이 우선하며 Completion commit 금지 |
| Completion commit 뒤 | 이미 `succeeded`; cancel 금지 |

## 11. Crash / restart matrix

| Crash point | Persisted authority | Next Worker action | Provider call replay | Duplicate risk / cleanup owner |
|---|---|---|---|---|
| claim 직후 | `running`, claim·lease | 현재는 expiry failure; durable handoff 뒤 claim 검증 | binding 없으면 같은-key Create | Provider side effect 없음 / Worker |
| Create 요청 전 | binding 없음 | same request dispatch | 허용 | 없음 / Worker |
| Create 송신 뒤 응답 전 | binding 없음, Provider 결과 불명 | same-key·same-fingerprint Create replay | 필수 | Provider idempotency가 duplicate 방지 / Provider |
| Create 응답 수신 뒤 binding commit 전 | binding 없음, Provider identity 외부 존재 | replay로 identity 회수 후 binding create | 필수 | 새 Provider Job 금지 / Worker·Provider |
| binding commit 뒤 | binding history 존재 | latest exact binding status 조회 | Create 금지 | active 선택 직렬화 / Worker |
| Provider running 중 | binding 존재, Workspace `running` | 현재 expiry failure; handoff 뒤 same binding poll | Create 금지 | inference 재실행 금지 / Worker |
| Provider success 뒤 Result fetch 전 | Provider terminal, binding 존재 | status와 result 재조회 | Create 금지 | Result read replay / Provider |
| Result ingestion 뒤 locator 전 | trusted metadata는 비영속 decision | Result trust gate 재실행 | Create 금지 | side effect 없음 / Workspace |
| locator 발급 뒤 | process-local이면 restart 복구 불가 | durable locator가 있을 때 exact record resolve | Create 금지 | locator 중복 방지 / Reconciliation |
| payload staging 뒤 Completion 전 | trusted staging, DB 미완료 | byte identity 재검증 후 Completion 또는 cleanup | Create 금지 | orphan staging / Payload layer |
| Artifact prepare 뒤 DB commit 전 | publish 가능, Completion DB 미완료 | 같은 payload replay; 실패 publish 보상 | Create 금지 | publish duplicate 방지 / Completion |
| Completion commit 뒤 응답 전 | Workspace `succeeded`와 lineage 원자 commit | existing aggregate replay | 모든 Provider mutation 금지 | DB/output duplicate 없음 / Completion |

## 12. Security와 transaction

공개 Job, 오류, 로그와 문서 예시에 absolute path, storage/DB root, credential, API key, authorization header, raw Provider response, local model·dataset path 또는 stack trace를 포함하지 않는다. Provider URI/path는 trusted locator boundary를 우회할 수 없다.

Provider network 호출 중 열린 DB transaction은 0개다. Repository가 직접 `commit()` 또는 `rollback()`하는 경우도 0개다. Worker claim/lease Service, Provider Job Persistence Service와 Completion UoW가 각각 자신의 짧은 transaction을 소유한다. cross-system distributed transaction은 도입하지 않는다.

## 13. 후속 구현 경계

다음 concrete PR의 최대 범위는 Workspace Worker에서 concrete DohaVocal dispatch, 기존 HTTP Transport, Provider Job binding/recovery, bounded polling, heartbeat/cancel, GetResult와 기존 Result trust gate까지다.

payload downloader, durable locator, Vocal Completion adapter, Artifact ingestion wiring, production authentication, background daemon과 실제 DohaVocal model/GPU 실행은 각각 별도 후속 의존성이다. 이 의존성이 없다는 사실은 계약 확정의 blocker가 아니며 해당 runtime capability를 완료로 선언하는 것만 막는다.
