# Trusted Payload Locator / Resolver Contract

> 문서 상태: [완료: process-local locator 호환 adapter, durable schema/Runtime foundation, verified local byte staging adapter·CAS] / [미구현: downloader·Completion adapter·Worker wiring]
> 최종 수정일: 2026-08-25
> 관련 결정: [ADR-041](../11-decisions/ADR-041-trusted-payload-locator-authority.md), [ADR-048](../11-decisions/ADR-048-dohavocal-payload-acquisition-consumer.md), [ADR-049](../11-decisions/ADR-049-durable-payload-locator-persistence-authority.md), [ADR-051](../11-decisions/ADR-051-verified-durable-staging-authority.md)

DohaVocal `0.2.0`의 `source_id`는 acquisition에만 쓰이는 Provider-side opaque subresource identity이며 `payloadref:v1` locator가 아니다. Result replay는 source descriptor를 재구성하지만 verified staging key·actual facts·revocation·cleanup은 복구하지 못한다. [Durable Payload Locator Authority](durable-payload-locator-authority.md)는 이를 전용 aggregate로 영속해야 한다고 판정했으며 현재 consumer는 여전히 bounded transient bytes까지만 반환한다.

## 1. 목적과 authority

`TrustedPayloadReference`는 Provider Artifact ID, Provider URL, 원격 URI 또는 filesystem path가 아니다. DohaMusic runtime만 발급하는 내부 opaque lookup identity다. 보유 자체는 권한이나 capability token이 아니며 상위 owner·Workspace·rights gate가 선행한다. Provider wire response가 locator 문자열을 보내더라도 신뢰하거나 직접 변환하지 않는다.

```text
DohaMusic-owned staging payload
→ TrustedPayloadIssuer
→ payloadref:v1:<32 lowercase UUID hex>
→ TrustedPayloadResolver
→ ResolvedTrustedPayload
→ future internal Completion adapter [미구현]
```

Public API operation은 추가하지 않았다. durable `PayloadLocatorService`는 port를 통해 짧은 transaction을 소유하고 app composition root에서 생성 가능하지만 ProviderResultIngestionService, Worker, ProviderDispatcher와 downloader에는 아직 연결하지 않는다.

## 2. locator와 descriptor

locator는 `namespace=payloadref`, `version=1`, 추론 불가능한 `opaque_id`로 구성된다. 정확한 canonical 문자열 이외의 empty, path, `../`·`..\`·percent traversal, Windows/Unix absolute path, `http`·`https`·`file`·`s3`·`data` URI와 credential-like 값은 malformed로 거부한다. 문법적으로 유효해도 issuer registry에 없는 locator는 unknown이다.

`ResolvedTrustedPayload`는 reference, DohaMusic-owned canonical `temporary_path`, Artifact kind, byte-derived media type·size·SHA-256, created time과 선택적 expiry만 제공한다. `ProviderOutput.temporary_path`의 required invariant는 변경하지 않았고 실제 변환 adapter는 구현하지 않았다. Provider의 `metadata_descriptor` checksum은 resolved payload checksum과 별개이며 복사·대체하지 않는다.

## 3. trusted root와 무결성

발급과 resolve 양쪽에서 다음을 fail-closed 검증한다.

- config의 기존 trusted staging root가 실제 non-link directory인지 확인한다.
- absolute internal path를 canonicalize하고 root containment, 각 component의 symlink·junction·reparse escape와 traversal을 거부한다.
- 존재하는 regular file을 no-follow 방식으로 열어 file identity, streaming SHA-256과 size를 계산한다.
- 기존 Artifact media validator로 실제 bytes에서 MIME을 결정한다. 빈 payload 정책도 kind별 기존 validator를 그대로 따른다.
- media 검사 전후와 매 resolve에서 identity·size·checksum을 재검증한다. 변경·교체된 파일은 metadata mismatch다.
- cleanup 뒤 파일이 없으면 payload missing이다. resolver는 삭제·consume·quarantine을 수행하지 않는다.

오류는 malformed, unknown, expired, missing, outside trusted root, non-regular file, metadata mismatch 등을 구분하지만 absolute path, credential 또는 filesystem 내부 정보를 message에 넣지 않는다. full path INFO logging도 추가하지 않았다.

## 4. expiry, 재사용과 중복

임의의 production TTL은 두지 않는다. caller가 timezone-aware `expires_at`을 명시할 때만 적용하며 만료 시 resolve를 거부한다. reference는 consume하지 않고 expiry 또는 Completion/Artifact ingestion 소유 cleanup 전까지 재사용할 수 있다. 같은 payload를 다시 등록해도 새 locator를 발급하며 content dedup을 하지 않는다. 충돌한 opaque ID는 기존 binding을 덮어쓰지 않고 거부한다.

## 5. 구현 범위와 process boundary

`InMemoryTrustedPayloadRegistry`는 deterministic clock/ID를 주입할 수 있는 process-local Foundation fake이며 production authority가 아니다. current locator 형식과 file-backed resolver 회귀는 유지한다. durable `ProviderJobBinding 1:N PayloadLocator`는 source expectation과 verified staging metadata·revocation·cleanup을 SQLAlchemy/SQLite와 Alembic `20260825_0023`에 보존한다. exact replay와 lifecycle mutation은 Service-owned transaction 및 revision CAS를 사용한다. 상세 Column·state·crash 정책은 [Durable Payload Locator Authority](durable-payload-locator-authority.md)를 따른다.

DohaVocal `0.1.0` metadata-only 결과는 `payload_present=false`, `payload_reference=None`, binary·structured eligibility false다. `0.2.0` payload-backed 결과도 현재는 read-only adapter가 network transaction 밖에서 bounded transient bytes를 검증하는 데 그치며 `payload_reference=None`과 ingestion eligibility false를 유지한다. [Verified Durable Staging Authority](verified-durable-staging-authority.md)는 locator-derived local key, exclusive publish, full open verification과 orphan adoption으로 다음 adapter 계약을 확정했지만 구현하지 않았다. 이 bytes를 durable staging에 두고 Completion에 전달하는 downloader orchestration, Artifact ingestion, AssetVersion·JobOutput·ModelUsage commit은 모두 `[미구현]`이다. arbitrary URL fetch는 허용하지 않는다.

## 6. 오류 계약

| 오류 | 의미 |
|---|---|
| `MALFORMED_REFERENCE` | canonical locator 문법이 아님 |
| `UNKNOWN_REFERENCE` | DohaMusic issuer가 등록하지 않음 |
| `EXPIRED_REFERENCE` | 명시적 expiry 도달 |
| `PAYLOAD_MISSING` | cleanup 등으로 file 없음 |
| `PAYLOAD_OUTSIDE_TRUSTED_ROOT` | root·traversal·link·credential 경계 위반 |
| `PAYLOAD_NOT_REGULAR_FILE` | directory/device/special file |
| `PAYLOAD_METADATA_MISMATCH` | checksum·size·identity·media 불일치 |
