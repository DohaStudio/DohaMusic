# ADR-069: DohaVocal verified staged Artifact Completion authority

- 상태: 승인, production 구현 미착수
- 날짜: 2026-09-16
- 기준: `develop@99511b9b778b9b7c85b9b0cec0acd778b9b2a5d1`
- 관련 문서: [Verified Staged Artifact Completion](../03-architecture/dohavocal-verified-staged-artifact-completion.md), [Worker Reconciliation Contract](../03-architecture/dohavocal-worker-reconciliation-contract.md), [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md), [Durable Payload Locator Authority](../03-architecture/durable-payload-locator-authority.md), [ADR-051](ADR-051-verified-durable-staging-authority.md)

## Context

DohaVocal `0.2.0` payload acquisition은 Provider Result를 검증하고 `PayloadLocator`를 `verified_staged`로 만드는 데까지 책임진다. 현재 `VerifiedPayloadStagingPort.open_verified()`는 검증된 `BinaryIO`만 반환하지만, `ArtifactIngestionService.prepare()`는 trusted local `Path`를 요구한다. 또한 generic `JobCompletionService`는 호출자가 target Asset 또는 AssetVersion을 선택하게 하며 `PayloadLocator.mark_ingested()`는 별도 transaction을 소유한다.

따라서 verified payload를 열 수 있다는 사실만으로 Vocal Workspace 결과의 target, 최종 권리, Artifact 계보 또는 Job success가 결정되지 않는다. Export 전용 `ExportPublicationLedger`와 `TrustedArtifactRegistrationService`는 Project Export publication을 위한 authority이므로 이 간극을 대신할 수 없다.

## Decision

### 1. Completion owner와 output target

DohaMusic의 전용 `DohaVocalArtifactCompletionService`가 향후 이 경계의 유일한 writer가 된다. Provider ID, Provider-side output AssetVersion ID, caller가 전달한 target ID는 Workspace PK 또는 선택 권위가 아니다.

| Job type | Asset/Version authority | Completion 결과 |
|---|---|---|
| `vocal_generation` | Completion이 effective Job scope에서 새 `Asset(type=vocal)`과 Project의 `ProjectAsset(role=vocal)`을 만든다. | 새 Asset의 immutable version 1과 audio Artifact |
| `voice_conversion` | validated `source_asset_version_id`가 속한 active Vocal Asset을 target으로 파생한다. | 같은 Asset의 다음 immutable version과 audio Artifact |
| `vocal_correction` | validated `source_asset_version_id`가 속한 active Vocal Asset을 target으로 파생한다. | 같은 Asset의 다음 immutable version과 audio Artifact |
| `vocal_analysis` | validated exact source AssetVersion이 target이다. | 새 Asset/AssetVersion 없이 해당 Version의 immutable analysis JSON Artifact |

변환·보정 Version의 `parent_asset_version_id`는 trust gate가 확정한 같은-Asset parent다. 생성의 서로 다른 입력 계보는 기존 `JobInput → Job → JobOutput`으로 보존하며 임의 `parent_asset_version_id`나 새 relation type을 만들지 않는다. 분석은 source 음원을 새 음원 Version으로 위장하지 않는다.

Completion은 `Asset.selected_asset_version_id`를 변경하지 않는다. Project membership, JobOutput 생성과 사용자 최종 선택은 서로 다른 의미다. 신규 생성 Asset도 명시적 선택 전까지 selection pointer를 비워 둔다. version number와 generation ProjectAsset display order는 transaction 안에서 현재 authority로부터 할당하며 경쟁 시 unique/CAS 충돌을 승자 replay로 수렴시킨다.

### 2. verified stream의 공식 handoff

`ArtifactIngestionService`에 향후 path-free stream prepare entry point를 추가한다.

```text
VerifiedPayloadStagingPort.open_verified(payload)
  → context-managed BinaryIO
  → ArtifactIngestionService.prepare_verified_stream(request, stream, expected_facts)
  → PreparedArtifactIngestion
```

이 entry point는 기존 Artifact publisher가 소유하는 임시 객체에 bounded chunk copy하고, 실제 bytes의 SHA-256·size·media를 독립적으로 다시 검증한 뒤 기존 publish와 `PreparedArtifactIngestion → register_prepared → verify_registered` 경로에 합류한다. absolute staging path나 descriptor를 DTO·DB·로그에 노출하지 않는다. 기존 `prepare(Path)` 계약은 다른 flow를 위해 유지한다.

`expected_facts`는 locator의 persisted actual checksum·size·media와 정확히 같아야 한다. staging의 검증을 Artifact 검증으로 대체하지도, Artifact 검증을 생략하지도 않는다. filesystem I/O와 publish는 DB transaction 밖에서 끝낸다.

### 3. final transaction과 locator handoff

physical Artifact publish와 DB commit은 하나의 ACID transaction이 될 수 없다. 대신 prepare 후 하나의 caller-owned DB transaction이 다음을 전부 commit하거나 전부 rollback한다.

1. current Job을 읽고 `VocalCompletionAuthorityPort.require_current(mode=commit|replay)`로 effective scope, binding과 current rights를 재검증한다. 신규 commit만 claim/cancel/verified-staging gate를 통과한다.
2. replay된 canonical output을 검증하거나 위 표에 따라 Asset/ProjectAsset/AssetVersion target을 만든다.
3. 기존 `ArtifactIngestionService.register_prepared()`와 `verify_registered()`로 Artifact와 storage catalog를 등록한다.
4. canonical Workspace output role의 `JobOutput`과 `ModelUsage`를 만든다.
5. 같은 Session의 locator repository CAS로 `verified_staged → ingested` 및 exact `ingested_artifact_id`를 기록한다.
6. exact claim, `running`과 cancellation 없음 조건의 Job CAS로 `succeeded`를 전이한다.

현재 `PayloadLocatorService.mark_ingested()`의 독립 transaction을 이 경로에서 호출하지 않는다. implementation은 기존 `PayloadLocatorRepository(session)`을 감싼 transaction-neutral completion port를 사용한다. 이 port와 repository는 `commit()`·`rollback()`을 소유하지 않는다. 기존 column과 FK로 충분하므로 새 schema나 Alembic은 필요하지 않다.

DB commit 뒤 locator cleanup은 별도 lifecycle이다. `ingested → cleanup_pending`, identity-safe `delete_verified()`, `cleanup_pending → cleaned`를 재시도한다. cleanup 실패는 성공한 Job이나 Artifact를 되돌리지 않는다.

### 4. latest rights authority

`VocalCompletionAuthorityPort`는 caller-owned SQLAlchemy `Session`에 참여하는 read/revalidation port다.

```text
require_current(
  session,
  job_id,
  provider_job_binding_id,
  payload_locator_id,
  execution_claim_token,
  trusted_principal,
  mode=commit|replay,
) -> VocalCompletionAuthoritySnapshot
```

port는 transaction, network, filesystem I/O를 소유하지 않는다. caller가 보낸 owner/project 값을 신뢰하지 않고 Job과 관계에서 effective Owner·Workspace·Project를 파생한다. `commit` mode는 현재 Job `running`, exact claim token, cancellation 없음, active Project/Asset scope, current consent/access/use rights, exact binding/locator identity, `verified_staged`, not revoked, policy active, expected lifecycle revision을 검증한다. authoritative rights writer와 같은 transaction serialization/lock 규약으로 guard를 commit까지 유지해야 하며 단순 cached boolean으로 승인하지 않는다.

`replay` mode는 Job `succeeded`, canonical output과 exact locator Artifact binding, current output access rights를 검증한다. locator는 `ingested`, `cleanup_pending` 또는 `cleaned`일 수 있다. 이미 commit된 결과를 읽는 데 새 execution claim, staging open, source availability 또는 locator staging policy를 요구하지 않는다. replay는 새 ingestion/terminal mutation을 하지 않는다.

긴 I/O 전에 같은 port로 eligibility를 미리 확인할 수 있지만 final transaction 안의 재검증만 commit authority다. pre-I/O snapshot을 캐시해 final gate를 대신할 수 없다. gate 실패는 Artifact/Job/locator DB mutation을 모두 금지하고 준비된 publish만 기존 compensation/orphan recovery 계약으로 처리한다.

### 5. replay, concurrency와 recovery

- same Job/locator/result와 같은 verified facts는 기존 `JobOutput → Artifact → AssetVersion → Asset` 및 `PayloadLocator.ingested_artifact_id`를 읽어 동일 결과를 반환한다. cleanup 뒤에도 이 binding은 남으므로 staging을 다시 열지 않는다.
- JobOutput role/order, locator, Artifact facts, provider/model/lineage 중 하나라도 다르면 conflicting replay로 fail closed한다.
- 같은 Job의 동시 Completion은 `(job_id, output_order)` unique와 locator revision CAS 중 하나만 승리한다. loser는 transaction을 rollback하고 winner의 canonical aggregate를 다시 읽어 exact match일 때만 replay한다.
- Artifact publish 뒤 DB commit 전 crash는 logical row를 남기지 않는다. invocation-owned publish는 보상하고, 보상이 불확실하면 기존 Artifact orphan reporter/reconciliation이 처리한다. verified staging은 `verified_staged`로 남아 재시도할 수 있다.
- DB commit 뒤 응답 전 crash는 JobOutput과 locator의 exact Artifact binding에서 replay한다. 새 Artifact나 Version을 만들지 않는다.
- commit 뒤 cleanup 전 crash는 `ingested`에서 cleanup lifecycle만 재개한다.

## Consequences

Provider success, verified staging, Artifact publication, Workspace result selection과 terminal success의 authority가 분리된다. Vocal audio history는 immutable Version으로 남고 analysis JSON은 source Version의 평가 Artifact로 남는다. Completion transaction은 사용자에게 보이는 성공과 locator handoff를 함께 확정하며, physical I/O는 장기 DB transaction 밖에 유지한다.

이번 결정은 contract resolution이다. production service, port, adapter, Worker wiring, Router, schema와 migration을 구현하지 않는다. PR #130의 `source_bound → verified_staged` acquisition 책임도 변경하지 않는다.

## Rejected alternatives

- `TrustedArtifactRegistrationService` 재사용: `ExportPublicationLedger`의 `PUBLISHED` claim에 결합된 Export 전용 trust다.
- `ExportPublicationLedger`를 Vocal로 일반화: Export publication intent와 Vocal locator lifecycle의 authority를 혼합한다.
- staging path를 꺼내 기존 `prepare(Path)`에 전달: path 비노출과 verified descriptor lifetime을 깨뜨린다.
- locator를 별도 transaction에서 먼저/나중에 `ingested` 처리: Job success와 handoff 사이 partial authority를 만든다.
- 모든 Vocal 결과에 새 Asset 생성: correction/conversion의 같은 logical Vocal history를 분절한다.
- analysis마다 Vocal Version 생성: JSON 평가 결과를 음원 Version으로 오인하게 한다.
- Completion이 selected version을 자동 변경: 사용자 최종 선택과 Provider 실행 성공을 결합한다.

## Revisit conditions

복수 payload output, 별도 analysis AssetType, object storage immutable version, 또는 다중 Project publication 요구가 생기면 cardinality와 schema를 다시 검토한다. 그 전에는 현재 single canonical output과 기존 schema를 기준으로 한다.
