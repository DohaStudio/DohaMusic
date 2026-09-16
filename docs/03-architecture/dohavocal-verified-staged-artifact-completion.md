# DohaVocal Verified Staged Artifact Completion Contract

> 문서 상태: [승인: contract resolution] / [미구현: production Completion·Worker wiring]
> 최종 수정일: 2026-09-16
> 기준: `develop@99511b9b778b9b7c85b9b0cec0acd778b9b2a5d1`
> 최종 판정: `VERIFIED_STAGED_ARTIFACT_COMPLETION_CONTRACT_RESOLVED`
> 관련 결정: [ADR-069](../11-decisions/ADR-069-dohavocal-verified-staged-artifact-completion-authority.md)

## 1. 범위

이 문서는 PR #130 이후 `verified_staged`인 단일 DohaVocal payload를 immutable Workspace 결과와 Job success로 승격하는 공식 계약이다. acquisition, Provider 호출, downloader, schema, public API와 production wiring은 변경하지 않는다.

```text
PayloadLocator(verified_staged)
→ open_verified() full revalidation
→ ArtifactIngestionService stream prepare
→ one Completion DB transaction
→ Artifact + JobOutput + optional Asset/AssetVersion
→ PayloadLocator(ingested) + Job(succeeded)
→ asynchronous staging cleanup
```

## 2. authority matrix

| Fact / mutation | Authority |
|---|---|
| Provider execution과 Result | DohaVocal Runtime + persisted ProviderJobBinding |
| Result/Workspace trust와 role mapping | `ProviderResultIngestionService` + DohaMusic mapping |
| source acquisition과 `verified_staged` | PR #130 acquisition orchestration |
| staged bytes open·revalidation·delete | `VerifiedPayloadStagingPort` |
| Artifact publish/catalog/integrity | `ArtifactIngestionService` |
| output Asset/Version target | future `DohaVocalArtifactCompletionService` |
| effective scope와 최신 rights | future `VocalCompletionAuthorityPort` |
| `JobOutput`, `ModelUsage`, locator ingestion, Job success | same Completion transaction |
| selected AssetVersion | explicit DohaMusic/user selection flow; Completion 아님 |

Provider-side AssetVersion ID, role, source ID, caller-supplied owner/project/target와 staging status 문자열만으로 어느 mutation도 승인하지 않는다.

## 3. canonical output mapping

모든 현재 DohaVocal Job은 canonical output 1개다.

| Job type | Workspace role | target | mutation |
|---|---|---|---|
| `vocal_generation` | `generated_vocal` | Completion-created Project Vocal Asset | Asset + ProjectAsset(role=`vocal`) + version 1 + audio Artifact |
| `voice_conversion` | `converted_vocal` | validated source의 active Vocal Asset | next AssetVersion(parent=validated parent) + audio Artifact |
| `vocal_correction` | `corrected_vocal` | validated source의 active Vocal Asset | next AssetVersion(parent=validated parent) + audio Artifact |
| `vocal_analysis` | `vocal_analysis` | validated exact source AssetVersion | analysis JSON Artifact only |

생성의 input lineage는 JobInput에, 모든 결과 lineage는 `JobInput → Job → JobOutput → Artifact → AssetVersion`에 남는다. Provider opaque output ID를 Workspace ID로 사용하지 않는다. Completion은 기존/신규 Asset의 `selected_asset_version_id`를 변경하지 않고 Composition도 수정하지 않는다.

## 4. stream handoff

호출 순서는 다음과 같다.

```python
with staging.open_verified(verified_payload) as stream:
    prepared = ingestion.prepare_verified_stream(
        request_without_path,
        stream,
        expected_facts=locator_actual_facts,
    )
```

`prepare_verified_stream`은 [미구현] narrow extension이다. stream을 다 소비하는 동안 context가 열려 있어야 하며 stream handle을 저장하거나 반환하지 않는다. 입력은 처음부터 읽고 seek 가능성을 요구하지 않는다. Artifact-owned temporary object에 bounded copy하면서 SHA-256와 size를 계산하고 media parser를 실행한다. locator actual facts와 차이가 있으면 publish/DB write 없이 실패한다.

성공 결과는 기존 `PreparedArtifactIngestion`이다. 이후 `register_prepared(session, prepared)`와 `verify_registered(session, artifact, prepared)`를 그대로 사용한다. 별도 Artifact registry나 trusted-existing-publication 경로를 만들지 않는다.

## 5. transaction protocol

### I/O phase — 열린 DB transaction 없음

1. current authority precheck
2. 이미 `succeeded`면 current output access와 exact binding을 검증해 I/O 없이 replay
3. 신규 commit만 locator persisted actual facts로 `VerifiedStagedPayload` 구성
4. `open_verified()`로 key, containment, object identity, full checksum·size·media 재검증
5. `prepare_verified_stream()`으로 Artifact publish와 독립 검증

### Commit phase — 하나의 caller-owned transaction

1. Job과 관련 rows를 current state로 다시 읽는다.
2. `VocalCompletionAuthorityPort.require_current(mode=commit|replay)` 최종 gate를 통과한다.
3. existing success replay를 먼저 판정한다.
4. 필요한 Asset/ProjectAsset/AssetVersion을 만든다.
5. Artifact와 storage location을 등록하고 resolver로 다시 검증한다.
6. JobOutput과 ModelUsage를 만든다.
7. locator를 exact revision/status/not-revoked 조건으로 `ingested` CAS하고 같은 Artifact ID를 기록한다.
8. exact claim token, `running`, cancellation 없음 조건의 Job CAS로 progress 100 / `succeeded`를 기록한다. CAS failure는 전체 rollback이다.
9. transaction commit.

어느 단계든 실패하면 4–8의 DB mutation은 모두 rollback한다. Repository와 transaction-neutral ports는 commit/rollback을 호출하지 않는다.

### Post-commit phase

Artifact prepare 임시 입력을 finalize하고 locator cleanup을 `ingested → cleanup_pending → physical delete → cleaned`로 수행한다. cleanup은 성공 응답과 분리해 재시도 가능해야 한다. Artifact final object는 locator staging cleanup 대상이 아니다.

## 6. final authority gate

`VocalCompletionAuthorityPort`는 final transaction의 Session과 `mode=commit|replay`를 받는다. 신규 `commit`은 다음을 authoritative rows에서 재검증한다.

- trusted principal에서 파생된 effective Owner와 Job의 Workspace/Project
- Job type, API contract, Provider, Manifest, `running`, exact claim token, lease eligibility, cancel 없음
- active Workspace/Project와 target/source Asset scope
- current voice consent, access와 use rights; revoked/deleted source 없음
- exact ProviderJobBinding과 trusted Result identity
- locator의 Job/binding/ordinal/role/source/expected facts 일치
- `verified_staged`, current revision, not revoked, locator policy active
- opened/prepared bytes와 locator actual checksum·size·media exact equality

I/O 전 check는 낭비를 줄일 뿐이다. I/O 사이에 권리, claim, cancel 또는 revocation이 바뀔 수 있으므로 final check가 유일한 commit authorization이다. port는 external call을 하지 않으며 DB transaction을 끝내지 않는다.

current rights guard는 authoritative rights writer와 같은 transaction serialization/lock 규약으로 commit까지 유지한다. 읽은 boolean을 transaction 밖에 저장하거나 snapshot만 비교하는 adapter는 production authority가 아니다. 이 session-aware concrete rights adapter는 `[미구현]`이며 새 schema를 전제하지 않는다.

읽기 전용 `replay`는 Job `succeeded`, canonical output의 immutable facts/lineage, locator의 exact `ingested_artifact_id`와 current output access rights를 확인한다. locator 상태는 `ingested`, `cleanup_pending`, `cleaned`를 허용하고 claim·staging open·source availability·staging policy expiry는 요구하지 않는다. replay가 신규 ingestion을 승인하는 것은 아니다.

## 7. idempotency와 conflict

canonical replay key는 single output 기준 `(job_id, output_order=0)`이며 locator identity와 result/binding facts를 함께 대조한다.

- Job이 `succeeded`이고 output Artifact가 locator의 `ingested_artifact_id`와 같으며 role, media, hash, size, provider/model과 target lineage가 같으면 replay success다. locator cleanup 뒤에도 이 binding으로 I/O 없이 replay한다.
- locator만 `ingested`거나 Job만 `succeeded`인 상태는 정상 commit 결과가 아니다. 정상 Runtime에서 새로 만들지 말고 integrity/reconciliation error로 fail closed한다.
- same identity의 checksum·size·media, output role, target lineage 또는 provider/model mismatch는 conflict다.
- concurrent loser는 unique/CAS error를 일반 실패로 확정하기 전에 transaction을 rollback하고 winner aggregate를 reload한다. exact match만 replay다.

## 8. crash and recovery

| crash point | durable authority | recovery |
|---|---|---|
| verified open 전/중 | locator `verified_staged` | full open revalidation부터 재시도 |
| Artifact publish 전 | locator `verified_staged` | stream handoff 재시도 |
| publish 뒤 DB 전 | locator `verified_staged`, DB output 없음 | invocation publish compensation; 불확실하면 Artifact orphan reconciliation, Completion 재시도 |
| DB transaction 중 | commit 전이면 전부 rollback | prepared publish 보상 뒤 재시도 |
| DB commit 뒤 응답 전 | Artifact/output/locator/Job 모두 committed | canonical output exact replay |
| commit 뒤 cleanup 전/중 | locator `ingested` 또는 `cleanup_pending` | cleanup lifecycle만 재개 |

physical publish와 DB commit 사이에 distributed atomicity를 주장하지 않는다. 사용자-visible logical atomicity는 final DB transaction이, file residue는 기존 compensation/orphan reconciliation이 보장한다.

## 9. security and exclusions

오류·로그·DTO에는 absolute path, storage root/key 외의 filesystem detail, credential, raw Provider response/payload, auth header, local model path를 넣지 않는다. safe locator ID, Job ID와 stable reason code만 허용한다.

다음은 명시적으로 이 계약 밖이다.

- PR #130 acquisition orchestration 변경
- `TrustedArtifactRegistrationService` 또는 Export ledger 재사용/확장
- new schema/Alembic/public API
- actual Provider/production Artifact/user DB access
- Worker daemon, dispatcher, production authentication
- 복수 payload output과 automatic user selection

## 10. implementation gate

후속 implementation은 최소한 stream handoff, final authority port, transaction-neutral locator CAS와 Completion orchestration을 한 PR에서 함께 검증해야 한다. 일부만 연결해 Job과 locator를 서로 다른 transaction으로 완료하는 구현은 허용하지 않는다.

필수 test matrix는 happy path 4종, open/checksum/size/media failure, scope/binding/result mismatch, rights/cancel/claim/revocation race, replay/conflicting replay, concurrent completion, prepare/register/commit failure, crash windows, no duplicate Artifact/output/version, no partial terminal mutation과 sensitive-data redaction이다.
