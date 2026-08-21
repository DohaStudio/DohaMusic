# ADR-039: Provider wire result와 Artifact ingestion authority를 분리

- 상태: 승인
- 날짜: 2026-08-21
- 최종 수정일: 2026-08-21
- 관련 문서: [Provider Result Ingestion Contract](../03-architecture/provider-result-ingestion-contract.md)

## Context

DohaVocal Runtime Foundation은 성공 결과에 metadata descriptor와 Provider-side Artifact·AssetVersion identity를 반환하지만 `payload_present=false`다. DohaMusic Completion UoW는 신뢰된 `temporary_path`의 실제 Payload를 검사하고 Artifact·AssetVersion·JobOutput·ModelUsage와 Job success를 원자적으로 확정한다. wire DTO를 직접 Completion 입력으로 사용하면 fake path, Provider identity의 Workspace PK 오인 또는 descriptor checksum의 payload checksum 오인이 발생한다.

## Decision

- Provider wire DTO와 Workspace Artifact 계약 사이에 read-only `ProviderResultIngestionService` trust gate를 둔다.
- durable binding, owner-scoped Job, provider/job identity, output role, Manifest, settings, source/parent lineage, Processing Chain owner와 checksum scope를 검증한 뒤 내부 `TrustedProviderResultCandidate`를 만든다.
- Provider Artifact ID와 output AssetVersion ID는 Provider-side opaque identity로만 보존한다.
- `payload_present=false`는 유효한 Provider metadata result이지만 binary·structured ingestion 모두 non-eligible이다.
- metadata-only result는 Provider failure도 Workspace completion도 아니다. 새 Job state는 추가하지 않는다.
- 기존 `ProviderOutput`과 Completion UoW의 trusted local payload 불변식은 느슨하게 만들지 않는다.
- validation은 side effect와 transaction 종료를 소유하지 않는다. 별도 table·Migration·Public API를 추가하지 않는다.

## Consequences

metadata-only 결과가 실제 Artifact로 승격되는 경로가 닫히고, identity spoof·lineage mismatch·descriptor checksum 오용이 fail-closed된다. 반복 validation은 side effect가 없으며 후속 ingestion idempotency key 후보를 안정적으로 제공한다.

반면 현재 결과만으로 Workspace Job을 성공 처리할 수 없다. payload-backed transport, trusted payload locator, Worker polling과 completion adapter는 후속 작업이다. `vocal_analysis.analysis_result`도 실제 JSON Payload authority가 정의되기 전에는 structured Artifact로 등록하지 않는다.

## Rejected alternatives

- fake `temporary_path` 생성: 존재하지 않는 Payload를 Artifact로 위조한다.
- `ProviderOutput.temporary_path` optional화: 기존 payload-backed Completion 불변식을 약화한다.
- Provider-side ID를 DohaMusic PK로 사용: 저장소별 authority를 혼동한다.
- metadata descriptor checksum을 payload checksum으로 사용: 실제 bytes 무결성을 증명하지 못한다.
- pending 상태 table 또는 새 Job state 추가: 현재 read-only trust gate에 필요하지 않고 orchestration 범위를 선점한다.

## Revisit conditions

DohaVocal이 실제 Payload 또는 승인된 URI를 반환할 때 payload transport, checksum scope, resolver authority와 ingestion idempotency persistence 필요성을 별도 ADR에서 재검토한다.
