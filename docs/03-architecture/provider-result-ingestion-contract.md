# Provider Result → Artifact Ingestion Contract

> 문서 상태: [완료: metadata-only trust/eligibility·Trusted Payload locator/resolver Foundation] / [미구현: payload transport·Completion adapter·실제 ingestion]
> 최종 수정일: 2026-08-24
> 기준: DohaMusic `64577d8c5c7d96b11c2ee22aefa5ce79da7725bc`, DohaVocal `59de6c7b50f2e1d28a04f13ad649bf99f5737ec2`, `.github/develop` 공통 명세 `dd75fc88c16e9ae9a04acfafb72756a905f6365b` (기존 고정 검토 SHA `1e4b480c8cbd6e51835f8550e685e9b136d8071d` 대비 호환 확인)
> 관련 문서: [Workspace Job Foundation](workspace-job-foundation.md), [Artifact Storage 계약](artifact-storage-contract.md), [Provider Job Persistence](provider-job-persistence.md), [Worker Reconciliation Contract](dohavocal-worker-reconciliation-contract.md), [ADR-039](../11-decisions/ADR-039-provider-result-ingestion-trust-boundary.md)

## 1. 목적과 경계

DohaVocal의 `VocalProviderResultCandidate`는 Provider가 만든 metadata descriptor다. 이 wire DTO는 DohaMusic `Artifact`, `AssetVersion` 또는 로컬 Payload의 authority가 아니다. `ProviderResultIngestionService`는 이를 `TrustedProviderResultCandidate`로 승격하기 전에 DB의 Workspace Job과 `ProviderJobBinding`을 한 read transaction에서 대조한다.

```text
VocalProviderResultCandidate (wire)
→ ProviderResultIngestionService (trust validation)
→ TrustedProviderResultCandidate + ProviderResultIngestionDecision
→ payload-backed Completion adapter [미구현]
```

기존 `ProviderOutput.temporary_path`와 Completion UoW는 검증된 실제 Payload 전용으로 유지한다. wire result의 path·URI를 받지 않으며 metadata-only 결과를 위해 synthetic path를 만들지 않는다.

## 2. Trust validation

호출자는 effective Owner, Workspace Job ID, durable binding ID와 기대 output role을 제공한다. Service는 다음을 모두 검증한다.

- owner 범위의 Workspace Job이 `running`이고 DohaVocal 구조화 Job 계약을 보존한다.
- binding의 `workspace_job_id`, `provider_id`, `provider_job_id`가 Job과 candidate의 `producer_id`, lineage Provider, `run_id`, lineage `job_id`에 일치한다.
- Job type별 output role은 `generated_vocal_candidate`, `converted_vocal_candidate`, `corrected_vocal_candidate`, `vocal_analysis_result` 중 정확한 하나다.
- audio capability는 `artifact_kind=audio`, analysis capability는 `artifact_kind=analysis`다.
- dynamic `model_manifest_id`와 예약 Vocal input을 제외한 immutable settings snapshot이 일치한다.
- source Version은 Job input에 포함되고, parent는 같은 Asset의 source 파생 계보다.
- `processing_chain_id`는 Job 계약과 일치하고 effective Owner가 소유한 DohaMusic chain이다.
- Provider-side Artifact ID와 output AssetVersion ID는 opaque identity로만 보존하며 path·URI·credential 형식을 거부한다.
- `artifact_checksum == lineage.checksum`, algorithm은 `sha256`, 두 checksum scope는 `metadata_descriptor`다.

검증 실패는 contract error다. 이 경계는 `Artifact`, `AssetVersion`, `JobOutput`, `ModelUsage`와 Job 상태를 변경하지 않으며 Session lifecycle이나 commit/rollback을 소유하지 않고 호출자 transaction에 참여한다.

## 3. Metadata-only semantics

현재 DohaVocal authority는 `payload_present=false`만 허용한다. 이는 Provider execution result metadata가 존재한다는 뜻이지, 실제 audio 또는 JSON Artifact Payload가 존재한다는 뜻이 아니다.

검증 성공 결과는 다음을 명시한다.

```text
reason = payload_absent
eligible_for_binary_ingestion = false
eligible_for_structured_ingestion = false
payload_reference = null
```

따라서 Provider 실행 성공을 Provider failure로 바꾸지 않지만 Workspace Job도 `succeeded`로 만들지 않는다. 현재 상태 machine에 새 상태를 추가하지 않고 Job은 Completion requirements를 충족할 실제 Payload가 생길 때까지 기존 `running` 상태를 유지한다. 내부 `stage`, bounded polling, lease와 terminal reconciliation은 [Worker Reconciliation Contract](dohavocal-worker-reconciliation-contract.md)를 따른다. trust failure는 비재시도 fail-closed이며 payload 가용성의 일시적 실패와 혼합하지 않는다.

`vocal_analysis.analysis_result`도 현재 Fake metadata descriptor의 일부다. `.github` Artifact 명세의 실제 직렬화 Payload와 크기·checksum을 갖춘 structured Artifact가 아니므로 Artifact로 등록하지 않는다.

## 4. Checksum과 payload authority

`metadata_descriptor` checksum은 candidate metadata의 일관성만 증명한다. Artifact ingestion은 DohaMusic이 소유한 trusted staging Payload의 실제 bytes에서 size, MIME과 payload SHA-256을 다시 계산해야 한다. descriptor checksum을 binary 또는 structured Payload checksum으로 변환하거나 재사용하지 않는다.

DohaMusic runtime이 발급하는 [Trusted Payload Locator / Resolver Contract](trusted-payload-locator-resolver-contract.md)는 `payloadref:v1:<opaque-id>`를 trusted staging regular file에 immutable하게 결합하고 expiry·identity·실제 byte checksum·media type을 fail-closed 검증한다. Provider path·URI와 wire locator는 authority가 아니다. 현재 metadata-only trusted candidate의 `require_payload_reference()`는 항상 `payload_absent`로 거부하며 locator를 자동 생성하지 않는다. remote download, arbitrary URL fetch, resolver→`ProviderOutput` adapter와 실제 Provider Payload access는 구현하지 않았다.

## 5. Idempotency와 transaction

검증 결과의 논리 idempotency key는 `(provider_job_binding_id, output_role, provider_artifact_id)`다. 같은 candidate를 반복 검증해도 DB·filesystem side effect가 없다. 실제 ingestion retry의 duplicate 방지는 후속 payload 계약에서 이 key와 기존 Completion UoW replay/uniqueness를 함께 사용해 확정한다. 현재 contract만을 위해 table이나 Alembic revision을 추가하지 않는다.

실제 payload ingestion이 도입되면 DB 조회 validation과 Completion write를 일관된 transaction 경계에서 재검증해야 한다. Provider network와 파일 전송은 DB transaction 밖에 둔다.

Candidate role은 Completion에 직접 전달하지 않는다. DohaMusic-owned mapping이 `generated_vocal_candidate`, `converted_vocal_candidate`, `corrected_vocal_candidate`, `vocal_analysis_result`를 각각 `generated_vocal`, `converted_vocal`, `corrected_vocal`, `vocal_analysis`로 변환하며 adapter 구현 전에는 Completion에 진입할 수 없다.

## 6. 미구현

- Worker / `ProviderDispatcher` wiring과 polling
- 실제 DohaVocal network·인증·Provider execution
- payload locator 발급·download·resolver
- 실제 audio/structured Payload ingestion
- `Artifact`·`AssetVersion`·`JobOutput`·`ModelUsage` 생성
- Workspace Job completion
- 신규 DB persistence·Public API
