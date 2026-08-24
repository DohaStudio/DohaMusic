# Durable Execution Handoff Analysis

> 문서 상태: 승인된 architecture authority, Runtime 미구현
> 기준: `develop` `addecaf4b19e5bf9e652e659006236bb7d1c8aac`
> 관련 결정: [ADR-046](../11-decisions/ADR-046-durable-execution-handoff-authority.md)

## 1. 판정과 범위

Provider execution부터 Result trust validation까지의 same-Job 재진입에는 새 durable execution handoff storage가 필요하지 않다. Workspace Job, `ProviderJobBinding`, deterministic Provider replay와 Completion aggregate가 다음 동작을 결정하는 기존 authority다.

```text
NO_NEW_DURABLE_HANDOFF_STORAGE_REQUIRED
```

이 판정은 payload locator 발급 전까지만 적용한다. locator가 생긴 뒤 payload acquisition·staging·Completion으로 넘기는 cross-process identity는 [Trusted Payload Locator / Resolver Contract](trusted-payload-locator-resolver-contract.md)의 `DURABLE_LOCATOR_REQUIRED`가 소유한다. execution handoff storage가 locator identity를 복제하지 않는다.

## 2. Persistence inventory

| Fact | 분류 | Authority / 복구 방식 |
|---|---|---|
| Job ID, 공개 상태, provider, Manifest, API contract, immutable settings·ordered inputs, retry lineage, cancellation, timestamps | `DURABLE_AUTHORITATIVE` | Workspace Job과 `JobInput` |
| current claim token, worker, lease, heartbeat, attempt | `DURABLE_AUTHORITATIVE` | 현재 ownership generation; old token은 mutation 권한 없음 |
| stage, progress | `DURABLE_AUTHORITATIVE`인 관측값 | side-effect proof 또는 resume cursor가 아님 |
| Provider external Job ID, provider, retry parent, append ordering | `DURABLE_AUTHORITATIVE` | immutable `ProviderJobBinding` history와 exact/latest lookup |
| canonical Provider request와 fingerprint | `DURABLE_DERIVABLE` | Job, ordered inputs, settings, owner/provider scope에서 결정적으로 재구성 |
| expected result role | `DURABLE_DERIVABLE` | immutable Job type의 canonical mapping |
| Provider runtime status | `TRANSIENT_REPLAYABLE` | exact binding의 `GetJobStatus` |
| wire Result, trusted candidate, validation decision | `TRANSIENT_REPLAYABLE` | `GetResult`와 mutation 없는 deterministic trust gate 재실행 |
| provider-success-seen, validation-passed, completion-started/done | `NOT_PERSISTED` | 기존 Provider read 또는 terminal/output aggregate와 중복 |
| polling cursor/count, invocation deadline, raw response, in-memory candidate | `PROCESS_LOCAL` | 새 claim invocation에서 다시 시작; business authority 아님 |
| terminal state, JobOutput, Artifact, AssetVersion, ModelUsage, catalog state | `DURABLE_AUTHORITATIVE` | Completion UoW가 atomic하게 확정 |
| production payload locator | `NOT_PERSISTED` | 별도 `DURABLE_LOCATOR_REQUIRED` dependency |

Result fingerprint를 별도 저장하지 않는다. trust gate 입력은 binding과 replay한 wire Result에서 다시 얻고 validation은 숨은 mutation 없이 반복할 수 있다.

## 3. Same-Job resume 최소 입력

새 claim owner가 필요한 최소 입력은 다음뿐이다.

- `workspace_job_id`와 새 current claim token
- immutable Job request, ordered inputs와 owner scope
- expected Provider, Manifest, API contract와 result role
- exact/latest `ProviderJobBinding` history
- cancellation과 terminal/output authority

binding이 있으면 Create를 호출하지 않고 exact Provider Job을 조회한다. binding이 없으면 `workspace-job:<job_id>`와 같은 canonical request fingerprint로 Create를 replay한다. previous worker, old token, transient Result, trust decision, polling cursor, raw response와 `completion_done` flag는 handoff 입력이 아니다.

## 4. Replay와 ownership 규칙

1. graceful yield는 `running`을 유지하고 claim tuple만 전부 해제한다. 다음 Worker는 binding-first로 재진입한다.
2. process crash는 lease expiry 뒤 eligible Job의 atomic CAS reclaim으로 새 token을 얻는 목표 계약이다. CURRENT Runtime은 여전히 expiry를 failure로 종료하며 reclaim 구현 완료를 뜻하지 않는다.
3. binding 없는 Create 전·in-flight·응답 후 binding 전 crash는 같은 key와 fingerprint의 Create replay로 같은 external identity를 회수한다.
4. binding commit 뒤에는 `GetJobStatus`, succeeded면 `GetResult`, 이어서 deterministic trust gate를 재실행한다.
5. metadata-only Result도 같은 read와 validation으로 재구성한다. Workspace는 `running`이며 locator가 없으므로 Completion은 금지한다.
6. claim token은 ownership authority일 뿐 business cursor가 아니다. reclaim 뒤 old token의 heartbeat, stage, fail, finish와 Completion mutation은 거부한다.
7. `attempt`는 Worker ownership generation이다. Provider retry generation은 binding append lineage만이 authority다.
8. Completion 전에는 current claim과 eligibility를 다시 검증한다. commit 뒤에는 terminal state와 output aggregate가 authority이고 terminal Job은 reclaim하지 않는다.

동시 reclaim은 Job claim CAS가 직렬화한다. 별도 handoff lock은 필요 없다. stale Worker의 이미 진행 중인 Provider Create는 Provider idempotency에 흡수되고, status/result는 read이며, Workspace mutation은 token fencing에 막힌다.

Provider `RetryJob`은 Create와 달리 idempotency 계약이 확정되지 않았다. 자동 retry는 금지하며 명시적 retry 발급의 response-loss window는 후속 Provider retry 계약에서 해결해야 한다. 이 문제는 독립 handoff storage를 추가해도 알 수 없는 external identity를 복구하지 못하므로 이번 판정을 바꾸지 않는다.

## 5. Crash / restart matrix

| # | Crash point | Durable authority | Same-Job reclaim / exact next action | Provider call·replay | Duplicate risk | Handoff storage | Locator dependency |
|---:|---|---|---|---|---|---|---|
| 1 | queued claim 직후 | `running`, claim·lease, immutable Job | TARGET expiry CAS 후 binding 분기 | binding 없으면 Create replay | idempotency가 Create 중복 방지 | 불필요 | 없음 |
| 2 | Create 전 | Job과 claim, binding 없음 | reclaim 후 canonical request 재구성 | same-key Create replay | 없음 | 불필요 | 없음 |
| 3 | Create request in-flight | Job, binding 없음 | 결과를 추측하지 않고 replay | same-key/same-fingerprint Create | Provider idempotency가 흡수 | 불필요 | 없음 |
| 4 | Create response 후 binding 전 | Job, binding 없음 | replay로 external ID 회수 후 binding append | Create replay 필수 | 새 Provider Job 금지 | 불필요 | 없음 |
| 5 | binding commit 후 | exact binding history | latest/exact binding status 조회 | `GetJobStatus` | Create 금지로 중복 방지 | 불필요 | 없음 |
| 6 | Provider queued/running | Job `running`, binding | status 재조회, bounded wait/yield | `GetJobStatus` read replay | poll cursor 중복은 무해 | 불필요 | 없음 |
| 7 | graceful yield | `running`, null claim tuple, binding | yielded claim CAS 후 status 조회 | `GetJobStatus` | owner CAS가 직렬화 | 불필요 | 없음 |
| 8 | Worker crash/expired lease | expired claim, binding 또는 replay input | eligible expiry CAS 후 binding 분기 | status 또는 Create replay | old token mutation 차단 | 불필요 | 없음 |
| 9 | Provider succeeded 확인 후 | binding과 Provider runtime authority | succeeded 재확인 후 Result 조회 | status + `GetResult` | read replay | 불필요 | 없음 |
| 10 | Result fetched 후 | binding, replayable Provider Result | Result 재조회 | `GetResult` read replay | side effect 없음 | 불필요 | 없음 |
| 11 | trust validated 후 | binding과 immutable validation input | Result 재조회 후 trust gate 재실행 | `GetResult` + validation | validation mutation 0 | 불필요 | 없음 |
| 12 | metadata-only wait | Job `running`, binding | status·Result·trust gate 재실행, Completion 금지 | read replay | 없음 | 불필요 | 아직 locator 없음 |
| 13 | locator issued | binding + durable locator가 필요 | locator record resolve·재검증 | Provider inference 재실행 금지 | locator 중복은 locator authority가 방지 | execution용 불필요 | **필요** |
| 14 | payload reconciliation | binding, locator·trusted byte identity | immutable payload 재검증·staging 복구 | Provider inference 재실행 금지 | orphan cleanup은 payload layer | execution용 불필요 | **필요** |
| 15 | Completion 직전 | Job `running`, current token, trusted payload | eligibility·cancel·token 재검증 후 UoW | Provider mutation 없음 | token fence | 불필요 | **필요** |
| 16 | Completion commit 후 | terminal Job과 output aggregate | reclaim 금지, existing aggregate replay | Provider mutation 금지 | UoW idempotency | 불필요 | 완료됨 |
| 17 | stale old Worker response | 새 current token 또는 terminal Job | old-token mutation 전부 거부 | Create는 idempotency, status/result는 read | Workspace 중복 commit 차단 | 불필요 | 단계에 따름 |

## 6. Storage 필요성 판정

다음 질문을 모든 후보 fact에 적용했다.

> 이 fact가 없으면 crash/reclaim 후 기존 Job + ProviderJobBinding + deterministic Provider replay + Completion authority만으로 다음 동작을 안전하게 결정할 수 없는가?

locator 전에는 `YES`인 독립 durable fact가 없다. 새 `DurableExecutionHandoff` entity/table, Provider persistence field 확장, schema와 Alembic은 모두 `NO`다. stage나 최적화용 cursor를 저장하면 오히려 Provider·binding·Completion과 경쟁하는 authority가 생긴다.

## 7. Activation gate와 남은 warning

이 문서는 architecture 판정이며 기능 활성화가 아니다. 다음은 계속 `[미구현]` 또는 `[검증 필요]`다.

- atomic reclaim CAS, eligible dispatcher registry와 full old-token fencing Runtime
- concrete Dispatcher/DohaVocal wiring, bounded polling, shutdown yield와 daemon
- Provider `RetryJob` idempotency/serialization 계약
- durable locator, downloader, Completion adapter와 payload ingestion
- production authentication과 실제 Vocal model/GPU

따라서 CURRENT `WORKER_LEASE_EXPIRED` failure를 TARGET reclaim 성공으로 표현하지 않는다. 다음 architecture dependency는 `DURABLE_LOCATOR_REQUIRED`다.
