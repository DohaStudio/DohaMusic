# ADR-048: DohaVocal Payload Acquisition Consumer 경계

> 상태: 승인
> 결정일: 2026-08-25
> 기준: DohaMusic `develop` 347525cc6655950ca2a397d33b61d1864ca9cd95, DohaVocal PR #6 merge b0527ea6877f02cdfdb9ada750a285daa1c8ef21

## 결정

DohaMusic는 DohaVocal `0.1.0` metadata-only 계약을 그대로 지원하면서 `0.2.0` payload-backed Result를 별도 strict DTO로 소비한다. `0.2.0` capability는 기존 9개 operation에 `GetPayloadContent`를 정확히 하나 추가하고 `payload_acquisition` 광고를 필수로 한다. Workspace Job의 `api_contract_version`과 선택한 Result DTO가 다르면 fail-closed한다.

Payload entry는 순서를 보존하는 1:N tuple이다. 현재 허용 role은 `generated_vocal_candidate`, `converted_vocal_candidate`, `corrected_vocal_candidate`, `vocal_analysis_result`이며 Job의 canonical output role과 정확히 일치해야 한다. `provider_artifact_id`와 enclosing Result `artifact_id`는 서로 다른 Provider-side identity로 보존한다. `source.kind`는 `provider_subresource`만 허용하고 `source_id`는 URL·경로·traversal·credential이 아닌 1–200자 opaque ASCII identifier여야 한다.

각 entry의 algorithm은 `sha256`, checksum은 lowercase 64-hex, size는 양수다. audio role은 `audio/wav` 또는 `audio/flac`, analysis role은 `application/json`만 허용한다. `available_until`은 null 또는 timezone-aware timestamp로 파싱한다. Trust gate는 시계에 따라 결과가 달라지지 않도록 만료 여부를 판정하지 않고 immutable 후보에 보존하며 acquisition 직전에 만료를 검사한다.

`GetPayloadContent` adapter는 설정된 DohaVocal base origin에 다음 경로만 구성한다.

```text
GET /v1/jobs/{job_id}/artifacts/{provider_artifact_id}/payloads/{source_id}
```

동적 값은 단일 path segment로 percent-encode하고 redirect를 따르지 않는다. 응답은 JSON wrapper나 raw HTTP object가 아니라 제한된 크기의 transient bytes로 streaming read한다. `Content-Type`은 필수, `Content-Length`는 선택이며 선언 길이·실제 길이·configured maximum·SHA-256을 모두 검증한 뒤에만 immutable verified response를 반환한다. timeout과 transport 실패는 raw body, URL, 경로 또는 credential을 노출하지 않는 stable error로 바꾼다.

동일 `(provider_job_binding_id, output_role, provider_artifact_id)` replay는 Result envelope identity, metadata checksum과 ordered payload identity 전체가 같아야 한다. source, checksum, size, media, availability 등 canonical identity가 바뀌면 `result_replay_conflict`로 거부한다.

## 경계

이번 결정은 read-only trust validation과 transient acquisition foundation까지만 구현한다. Provider source를 durable locator로 저장하지 않고, downloader orchestration·verified durable staging·Artifact ingestion·Completion adapter·Worker wiring·daemon·production credential을 추가하지 않는다. 검증된 bytes도 Workspace Artifact가 아니며 `eligible_for_binary_ingestion=false`를 유지한다.

```text
DohaVocal contract 0.2.0: MERGED upstream
DohaMusic consumer 0.2.0: IMPLEMENTED
Durable Locator: DEDICATED PERSISTENCE FOUNDATION IMPLEMENTED / BYTE STAGING NOT IMPLEMENTED
```

후속 ADR-049는 Result replay가 acquisition 전 source 복구에는 충분하지만 verified staging·revocation·cleanup에는 전용 `PayloadLocator` persistence가 필요하다고 확정하고 schema/Runtime foundation을 구현했다. verified durable byte staging과 orchestration은 아직 구현하지 않았다.
