# Durable Payload Locator Authority

> 문서 상태: [승인 제안: architecture authority, Runtime·schema 미구현]
> 최종 수정일: 2026-08-25
> 기준: DohaMusic `4f86866bb438a38b355db0bc04d4bd6f61c9db9a`, DohaVocal PR #6 merge `b0527ea6877f02cdfdb9ada750a285daa1c8ef21`
> 최종 판정: `DURABLE_LOCATOR_DEDICATED_AUTHORITY_REQUIRED`
> 관련 결정: [ADR-041](../11-decisions/ADR-041-trusted-payload-locator-authority.md), [ADR-046](../11-decisions/ADR-046-durable-execution-handoff-authority.md), [ADR-048](../11-decisions/ADR-048-dohavocal-payload-acquisition-consumer.md), [ADR-049](../11-decisions/ADR-049-durable-payload-locator-persistence-authority.md)

## 1. 결론과 범위

DohaVocal `0.2.0` Result의 `provider_subresource` source descriptor는 Provider Job binding과 `GetResult` replay로 재구성할 수 있다. 따라서 trust gate 통과 전후와 acquisition 시작 전 crash만으로는 durable locator가 필요하지 않다. `available_until`을 저장해도 Provider source lifetime을 연장하지 않으며 credential expiry도 해결하지 않는다.

그러나 verified durable staging을 cross-process Completion으로 넘기려면 Result replay에서 얻을 수 없는 다음 fact를 보존해야 한다.

- DohaMusic-owned opaque locator identity와 exact payload ordinal
- config-owned staging root 아래의 safe storage key
- 실제 bytes에서 다시 계산한 checksum·size·media와 verification 시각
- revocation, Artifact handoff와 cleanup lifecycle
- 같은 Result replay의 idempotent issue와 immutable conflict 판정

이 fact는 append-only Provider execution identity와 cardinality·mutation·retention이 다르다. 따라서 `ProviderJobBinding` Column 확장이 아니라 전용 `PayloadLocator` aggregate/table이 필요하다. 이 문서는 authority와 다음 migration 설계만 확정하며 Python, DB, Alembic, downloader, staging, Artifact ingestion, Completion, Worker와 network를 변경하지 않는다.

```text
Provider Result replay authority
  = Provider source 재구성

PayloadLocator authority
  = verified DohaMusic staging handoff·revocation·cleanup

Artifact + AssetVersion + JobOutput authority
  = Completion commit 이후 사용자 결과
```

## 2. 현재 구현과 fact 분류

`InMemoryTrustedPayloadRegistry`는 `payloadref:v1:<32 lowercase UUID hex>`를 실제 trusted staging regular file에 결합하고 resolve 때 file identity·SHA-256·size·media·expiry를 재검증하는 process-local Foundation이다. restart, multi-process와 durable cleanup에는 사용할 수 없다. DohaMusic `0.2.0` consumer의 acquisition 결과도 verified bytes를 메모리에만 보유한다.

| fact | 현재 authority | restart 후 복구 |
|---|---|---|
| Workspace Job, Provider ID·Job ID | DB `Job` + `ProviderJobBinding` | durable |
| Provider artifact, role, source kind·ID | `GetResult` + trust gate | Result replay로 재구성 |
| expected SHA-256·size·media·availability | `GetResult` + trust gate | Result replay로 재구성 |
| trusted candidate object·ordered tuple | Python object | 재조회·재검증 필요 |
| acquired bytes | `VerifiedVocalPayload.content` | process restart 시 소실 |
| `payloadref:v1` binding·file identity | in-memory registry | process restart 시 소실 |
| durable staging key·actual verification facts | 없음 | 재구성 불가 |
| revocation·Artifact handoff·cleanup lifecycle | 없음 | 재구성 불가 |

DohaVocal PR #6은 stable source·immutable Result·availability의 TARGET authority를 승인했지만 실제 `0.2.0` Runtime persistence와 bytes endpoint는 아직 미구현이다. 이 사실은 schema 판정을 막지 않으며 production wiring 완료를 선언하는 것만 막는다.

## 3. Result replay와 source availability

재시작 Worker는 다음 순서로 source descriptor를 회복한다.

```text
Workspace Job
→ ProviderJobBinding
→ GetJobStatus
→ GetResult(version=0.2.0)
→ ProviderResultIngestionService
→ canonical payload tuple
```

같은 Result에서 payload count/order, Provider artifact, role, source, expected checksum·size·media와 availability가 바뀌면 replay conflict다. 다만 현재 `validate_replay(previous, current)`의 `previous`는 transient object이므로 durable locator가 발급된 뒤에는 locator의 immutable expected fields가 durable comparison baseline이 된다.

`available_until`은 source availability expiry다. Worker crash 중 만료될 수 있고 locator row가 존재해도 lifetime은 연장되지 않는다. 세 expiry를 분리한다.

| expiry | authority | 효과 |
|---|---|---|
| source availability | Provider Result `available_until` | 미취득 source의 신규 acquisition 차단 |
| locator policy | DohaMusic `locator_expires_at` | staging resolve/reuse 차단 |
| credential | authentication provider | 해당 호출의 인증 재확인; DB에 credential 저장 금지 |

source가 만료되기 전에 verified staging이 확정됐다면 source expiry만으로 staging을 폐기하지 않는다. 이후 사용 가능 여부는 locator policy와 최신 rights gate가 결정한다.

## 4. identity와 issuance timing

Provider source identity와 PayloadLocator identity는 다르다.

```text
Provider source = (provider job, provider artifact, role, source kind, source ID)
PayloadLocator  = payloadref:v1:<opaque UUID>
```

권장 timing은 두 단계다.

1. trust gate PASS 뒤 짧은 transaction에서 canonical payload entry별 locator를 idempotent하게 `source_bound`로 issue한다.
2. network·file I/O와 byte 검증은 transaction 밖에서 수행한다.
3. immutable staging publish가 끝난 뒤 별도 짧은 transaction에서 safe key와 actual facts를 `verified_staged`로 확정한다.

trust PASS 뒤 locator issue 전 crash는 Result replay로 복구한다. issue 뒤 crash는 같은 unique identity를 replay해 기존 locator를 얻는다. acquisition 뒤 staging DB 확정 전 crash는 deterministic/non-overwriting staging publish와 orphan reconciliation이 다뤄야 하며 locator row만으로 bytes를 복구했다고 간주하지 않는다.

현재 `register_trusted_payload(path, ...)` API는 이미 존재하는 staging file을 검사하고 reference를 반환한다. durable adapter는 이 API를 호환 wrapper로 유지할 수 있지만 내부적으로 source-bound issue와 verified-staged transition을 분리해야 한다. `TrustedPayloadResolver`는 `verified_staged`이면서 revoked·expired가 아니고 상위 rights gate를 통과한 row만 resolve한다. locator ID 보유 자체는 권한이나 capability token이 아니다.

## 5. aggregate와 cardinality

관계는 다음과 같다.

```text
Workspace Job
  └─ ProviderJobBinding 1:N
       └─ PayloadLocator 1:N (ordered payload entries)
```

locator row는 `workspace_job_id`와 `provider_job_binding_id`를 모두 보존한다. direct Workspace scope는 owner·cancellation·rights 조회와 cleanup scan의 durable boundary이고, binding은 exact Provider execution authority다. 두 값의 불일치를 막기 위해 `(workspace_job_id, provider_job_binding_id)`가 같은 binding row를 가리키는 composite FK 또는 동등한 DB constraint를 사용한다. `provider_id`와 `provider_job_id`는 binding에서 파생하며 locator row에 중복 저장하지 않는다.

두 unique key를 사용한다.

```text
UNIQUE(provider_job_binding_id, payload_ordinal)
UNIQUE(provider_job_binding_id, provider_artifact_id, role, source_id)
```

같은 key와 모든 immutable expected field가 같으면 기존 locator를 replay한다. unique identity는 같지만 checksum·size·media·availability·ordinal 중 하나라도 다르면 `RESULT_REPLAY_CONFLICT`로 fail closed한다. Result의 ordered 1:N 의미를 보존하기 위해 `payload_ordinal >= 0`을 저장한다.

## 6. lifecycle

한 개의 과도한 state machine 대신 staging handoff 상태와 revocation을 분리한다.

```text
source_bound
→ verified_staged
→ ingested
→ cleanup_pending
→ cleaned
```

- `acquiring`은 durable state로 만들지 않는다. active execution ownership은 Workspace Worker claim이 소유하며 partial file은 downloader가 정리한다.
- source expiry는 `available_until`에서 계산하고 별도 state로 복제하지 않는다.
- revocation은 `revoked_at`과 safe reason으로 직교 기록하며 모든 acquire·resolve·reuse·ingestion을 차단한다.
- `ingested` 이후 성공 authority는 `Artifact`, `AssetVersion`, `JobOutput`이다. locator는 audit와 cleanup만 소유한다.
- 각 성공한 mutable transition은 `lifecycle_revision + 1` CAS로 경쟁을 감지한다.
- 모든 backward transition은 금지한다. 특히 `cleaned → verified_staged` resurrection과 `ingested → verified_staged` 재사용은 허용하지 않는다.

revocation은 staging status와 별도의 terminal control overlay다. `revoked_at`이 기록되면 해제하거나 이전 상태로 되돌리지 않으며 source acquisition, staging resolve/reuse와 ingestion을 모두 fail closed한다. verified bytes가 남아 있으면 cleanup을 요청할 수만 있다. 최소 revocation reason은 `workspace_cancelled`, `workspace_deleted`, `rights_revoked`, `source_invalidated`, `integrity_failure`, `security_incident`다. Provider source가 기술적으로 남아 있어도 revocation 뒤 재취득하지 않는다.

## 7. schema 설계

다음 implementation PR은 현행 Alembic head를 다시 확인한 뒤 additive revision 하나로 `payload_locators`를 추가한다. 현재 기준 예상 successor는 `20260825_0023`이지만 develop이 이동하면 실제 next revision을 사용한다. 기존 process-local registry row는 없으므로 backfill은 없다.

| Column | null | authority |
|---|---:|---|
| `payload_locator_id` UUID PK | 아니요 | `payloadref:v1:<uuid.hex>`의 opaque ID |
| `workspace_job_id` UUID FK | 아니요 | `jobs`, direct Workspace scope, `ON DELETE RESTRICT` |
| `provider_job_binding_id` UUID FK | 아니요 | `provider_job_bindings`, `ON DELETE RESTRICT` |
| `payload_ordinal` integer | 아니요 | ordered Result 위치, `>= 0` |
| `provider_artifact_id` string(200) | 아니요 | Provider payload artifact identity |
| `role` string(64) | 아니요 | trusted Provider result role |
| `source_kind` string(32) | 아니요 | V1은 `provider_subresource`만 허용 |
| `source_id` string(200) | 아니요 | stable opaque source identity |
| `artifact_kind` string(32) | 아니요 | `audio` 또는 `analysis` expectation |
| `expected_checksum_algorithm` string(16) | 아니요 | V1 `sha256` |
| `expected_payload_checksum` char(64) | 아니요 | Provider expectation |
| `expected_size_bytes` bigint | 아니요 | 양수 Provider expectation |
| `expected_media_type` string(128) | 아니요 | role/kind allowlist |
| `source_available_until` datetime | 예 | Provider source expiry |
| `locator_expires_at` datetime | 예 | 별도 DohaMusic policy expiry |
| `staging_status` string(32) | 아니요 | 위 5개 상태 |
| `staging_backend` string(32) | 예 | verified 뒤 config-owned backend ID |
| `staging_key` string(512) | 예 | canonical relative safe key; absolute path 금지 |
| `actual_checksum_algorithm` string(16) | 예 | verified bytes, V1 `sha256` |
| `actual_payload_checksum` char(64) | 예 | actual bytes digest |
| `actual_size_bytes` bigint | 예 | actual byte count |
| `actual_media_type` string(128) | 예 | actual validated media |
| `verified_at` datetime | 예 | verified staging 확정 시각 |
| `ingested_artifact_id` UUID FK | 예 | 완료 뒤 audit link, `ON DELETE RESTRICT` |
| `ingested_at` datetime | 예 | Artifact authority 전환 시각 |
| `revoked_at` datetime | 예 | rights/security gate |
| `revocation_reason` string(32) | 예 | safe enum reason |
| `cleanup_requested_at` datetime | 예 | reconciliation policy decision |
| `cleanup_completed_at` datetime | 예 | staging adapter 삭제 완료 |
| `lifecycle_revision` integer | 아니요 | 0 시작, mutation 성공당 +1 |
| `created_at`, `updated_at` datetime | 아니요 | issue와 마지막 transition 감사 |

FK는 locator의 Workspace Job과 Provider binding의 Workspace Job이 같음을 보장한다. CHECK는 expected 값의 형식·양수 크기, UTC timestamp, lifecycle revision, staging 상태별 nullable field 묶음, revocation timestamp/reason 동시 nullability를 검증한다. `verified_staged` 이상에서는 staging backend/key·actual facts·`verified_at`이 모두 non-null이어야 하고, `source_bound`에서는 actual·staging·verification field가 모두 null이어야 한다. expected와 actual facts는 별도 Column으로 보존하되 verify transition은 equality를 요구한다.

최소 Index는 binding history, `(staging_status, cleanup_requested_at)`, source availability, locator policy expiry와 nullable ingested Artifact 조회다. DB에는 Authorization, signed URL, API key, cookie, credential, raw Provider response, absolute path, storage root와 payload bytes를 저장하지 않는다.

## 8. staging·rights·cleanup 책임

SourceLocator와 StagingLocator 두 aggregate를 만들지 않는다. 한 `PayloadLocator`가 immutable source binding과 선택적 verified staging handoff를 단계별로 표현한다. source descriptor를 raw acquisition input처럼 외부에 노출하지 않고, staging resolver는 verified stage만 다룬다.

책임은 다음과 같이 분리한다.

| 책임 | owner |
|---|---|
| partial download와 이번 attempt temp cleanup | Downloader |
| immutable verified object publish·resolve·delete | Staging adapter |
| issue·replay·revoke·handoff·cleanup policy | Payload reconciliation Service |
| Artifact prepare·atomic completion과 성공 뒤 cleanup request 기록 | Artifact ingestion + Completion UoW |
| stale verified staging scan·cleanup 실행 | 후속 background janitor |
| 취소·삭제·Consent/access 판단 | 기존 Workspace·Asset·Voice/Consent authority |

Resolver는 locator row만 보고 권한을 부여하지 않는다. 상위 orchestration이 owner, Workspace Job, cancellation, deletion, Consent/access를 최신 authority에서 확인한 뒤 resolve한다.

## 9. crash matrix

| # | crash point | durable authority | restart action | re-acquire | staging reuse | locator 필요 | cleanup / duplicate control |
|---:|---|---|---|---:|---:|---:|---|
| 1 | trust PASS 전 | Job + binding | Result 재조회·trust gate | 조건부 | 아니요 | 아니요 | side effect 없음 |
| 2 | trust PASS 후 | Job + binding | Result 재조회·trust gate | 조건부 | 아니요 | 아니요 | candidate는 transient |
| 3 | locator issue 전 | Job + binding + Result | idempotent issue | 조건부 | 아니요 | 아직 아니요 | unique issue 준비 |
| 4 | locator issue 후 | source-bound locator | 기존 locator replay | 조건부 | 아니요 | 예 | unique keys가 duplicate 방지 |
| 5 | acquisition 시작 전 | source-bound locator | expiry·rights 확인 뒤 acquire | 예 | 아니요 | 예 | Reconciliation |
| 6 | partial acquisition | locator + partial temp | partial 폐기 후 재취득 | 예 | 아니요 | source binding만 | Downloader |
| 7 | acquisition complete | locator, bytes는 아직 transient | bytes 재취득 | 예 | 아니요 | row만으로 불충분 | Downloader |
| 8 | integrity PASS | locator, verified object 미확정 | bytes 재취득 | 예 | 아니요 | row만으로 불충분 | Downloader |
| 9 | staging persist 전 | source-bound locator | 재취득·재검증·publish | 예 | 아니요 | 예 | exclusive publish |
| 10 | staging persist 후 | verified-staged locator + object | actual facts 재검증 | 아니요 | 예 | 예 | Staging adapter |
| 11 | Artifact ingestion 전 | verified-staged locator | resolve·rights 확인 후 prepare | 아니요 | 예 | 예 | Reconciliation |
| 12 | Artifact prepare 후 | locator + prepared publish, DB 미완료 | Completion replay·conditional compensation | 아니요 | 예 | 예 | Completion UoW |
| 13 | Completion commit 후 | Artifact + AssetVersion + JobOutput | terminal aggregate replay | 아니요 | 불필요 | audit만 | Completion duplicate 0 |
| 14 | cleanup 전 | ingested/cleanup-pending locator | janitor가 exact key 정리 | 아니요 | 금지 | cleanup audit | Reconciliation policy |
| 15 | cleanup 후 | cleaned locator + Artifact authority | no-op/audit retention | 아니요 | 금지 | audit만 | duplicate delete no-op |

source가 만료됐고 verified staging도 없다면 payload-layer recovery는 fail closed한다. 이를 이유로 Provider inference, RetryJob 또는 새 Workspace Job을 자동 실행하지 않는다.

## 10. transaction과 다음 구현 범위

Provider network와 file/object I/O 동안 열린 DB transaction은 0개다. Service가 issue, verified transition, revoke, ingested handoff와 cleanup transition의 짧은 transaction을 소유하고 Repository는 `commit()`·`rollback()`을 호출하지 않는다.

다음 구현 PR의 최대 범위는 다음과 같다.

```text
PayloadLocator domain model
→ persistence port
→ SQLite adapter
→ additive Alembic migration
→ issue/replay/revoke/resolve lifecycle
→ restart/idempotency/security tests
```

그 PR에서도 durable byte staging, downloader orchestration, Artifact ingestion wiring, Completion adapter, Worker reclaim/dispatcher, daemon, production authentication과 실제 Provider network는 제외한다. DB persistence TARGET 테스트를 현재 PASS로 표현하지 않는다.
