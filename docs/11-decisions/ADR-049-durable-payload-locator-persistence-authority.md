# ADR-049: Durable Payload Locator Persistence Authority

> 상태: 승인 제안
> 작성일: 2026-08-25
> 최종 수정일: 2026-08-25
> 관련 기능: DohaVocal payload reconciliation restart recovery
> 관련 문서: [Durable Payload Locator Authority](../03-architecture/durable-payload-locator-authority.md), [ADR-041](ADR-041-trusted-payload-locator-authority.md), [ADR-046](ADR-046-durable-execution-handoff-authority.md), [ADR-048](ADR-048-dohavocal-payload-acquisition-consumer.md)

## 배경과 문제

ADR-046은 Provider execution부터 Result validation까지 Workspace Job, `ProviderJobBinding`과 deterministic Provider replay만으로 재진입할 수 있어 새 execution handoff storage가 불필요하다고 결정했다. ADR-048과 PR #124는 DohaVocal `0.2.0` payload Result의 stable `provider_subresource`, expected SHA-256·size·media·availability와 transient `GetPayloadContent` acquisition을 검증한다.

Result replay는 acquisition 전 source descriptor를 복구하지만 verified staging key, actual-byte verification, revocation과 cleanup 결과는 제공하지 않는다. current `InMemoryTrustedPayloadRegistry`는 이 값을 process-local memory와 local file identity에만 결합하므로 restart·multi-process Completion handoff에 충분하지 않다.

## 결정

최종 schema 판정은 다음과 같다.

```text
DURABLE_LOCATOR_DEDICATED_AUTHORITY_REQUIRED
```

1. source descriptor 복제를 위해 locator를 저장하지 않는다. acquisition 전 crash는 Result replay로 복구한다.
2. 전용 `PayloadLocator` aggregate는 Provider binding의 ordered payload entry와 DohaMusic-owned verified staging·revocation·cleanup을 결합한다.
3. `ProviderJobBinding`은 append-only Provider execution identity로 유지하며 payload Column을 추가하지 않는다.
4. 관계는 `ProviderJobBinding 1:N PayloadLocator`다. locator는 direct `workspace_job_id`와 binding ID를 모두 보존하고 두 scope의 일치를 DB constraint로 강제한다. binding + ordinal과 canonical source tuple을 각각 unique로 둔다.
5. `payloadref:v1:<uuidhex>` 형식은 유지하고 UUID를 DB primary key와 opaque internal reference에 공통 사용한다.
6. locator는 trust PASS 뒤 idempotent `source_bound`로 issue하고 verified staging publish 뒤 별도 transaction에서 actual facts와 safe storage key를 확정한다.
7. partial acquisition과 `acquiring`은 durable locator state가 아니다. Workspace Worker claim과 downloader attempt가 소유한다.
8. source availability, locator policy expiry와 credential expiry를 분리한다.
9. locator ID 보유는 권한이 아니다. 최신 owner·취소·삭제·Consent/access gate를 통과해야 resolve할 수 있다.
10. Completion commit 뒤 성공 authority는 `Artifact`, `AssetVersion`, `JobOutput`이며 locator는 audit·cleanup만 담당한다. lifecycle backward transition, revocation 해제와 cleaned staging resurrection은 금지한다.

## schema와 migration

additive `payload_locators` table 하나가 필요하다. direct Workspace Job FK와 ProviderJobBinding FK, immutable source/expected fields, nullable verified staging/actual fields, revocation·ingestion·cleanup timestamps, lifecycle revision을 둔다. Workspace Job과 binding scope는 composite FK 또는 동등한 DB constraint로 일치시킨다. absolute path, root, credential, signed URL, raw response와 bytes는 저장하지 않는다. safe relative staging key만 config-owned backend ID와 함께 저장한다.

현행 Alembic head 다음 revision에서 빈 table을 추가하므로 기존 row backfill은 없다. current 기준 successor 후보는 `20260825_0023`이며 구현 시 최신 develop head를 다시 확인한다. 구체적인 Column, CHECK, FK, unique와 Index는 architecture 문서가 authority다.

## 선택 이유

- Result replay는 source identity를 복구하지만 verified DohaMusic bytes와 cleanup 결과는 복구하지 못한다.
- locator persistence만으로 Provider source expiry를 막거나 bytes를 보존할 수 없으므로 durable staging과 책임을 명확히 분리한다.
- Provider binding extension은 1:N payload cardinality와 mutable staging lifecycle을 append-only execution history에 섞는다.
- SourceLocator와 StagingLocator를 별도 aggregate로 나누면 동일 payload identity와 revoke/cleanup gate가 중복된다.

## 대안

| 대안 | 판정 | 이유 |
|---|---|---|
| `DURABLE_LOCATOR_NOT_REQUIRED` | 거부 | verified staging·actual facts·cleanup을 restart 뒤 안전하게 handoff할 authority가 없음 |
| ProviderJobBinding extension | 거부 | execution identity와 1:N mutable payload lifecycle의 cardinality·retention이 다름 |
| SourceLocator + StagingLocator 두 aggregate | 거부 | source descriptor는 replay 가능하며 별도 source aggregate가 중복 |
| Result source descriptor를 locator로 사용 | 거부 | Provider identity가 DohaMusic staging·actual-byte·rights authority가 아님 |
| process-local registry를 production 사용 | 거부 | restart·multi-process 복구 불가 |

## 장단점과 영향

장점은 exact replay conflict, cross-process staging handoff, rights-aware revocation과 auditable cleanup을 한 authority에서 처리하는 것이다. 단점은 table·migration·Repository·Service lifecycle과 janitor 정책이 추가된다는 점이다. locator row만 구현해도 bytes가 durable해지는 것은 아니며 downloader·staging·Completion wiring은 계속 별도 후속이다.

## 구현·검증 상태

이 ADR은 architecture authority만 확정한다. Python, DB schema, Alembic, Runtime, network와 file I/O 변경은 0개다. current process-local locator, 0.2.0 consumer와 generic Artifact/Completion 회귀만 검증할 수 있으며 TARGET DB persistence는 `[미구현]`이다.

## 재검토 조건

- DohaVocal이 Result replay 또는 `provider_subresource` immutability를 변경할 때
- verified staging 없이 Provider source에서 Completion까지 원자 streaming하는 승인된 architecture가 생길 때
- object storage가 immutable object version·TTL·rights·cleanup authority 전체를 제공해 DB aggregate를 대체할 때
- payload cardinality나 primary role 정책이 변경될 때
- Artifact ingestion이 locator lifecycle을 대체하는 별도 durable staging manifest를 승인할 때

## 관련 PR

- DohaVocal PR #6: Provider payload acquisition authority
- DohaMusic PR #124: `0.2.0` consumer·transient acquisition
- 본 ADR 문서 PR: Draft 생성 후 번호 기록
