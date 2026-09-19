# ADR-092: Fresh Journal–Lineage Observation Foundation

> 상태: [제안 — 구현 및 검증 완료; Foundation Draft, 운영 비활성]
> 작성일·최종 수정일: 2026-09-19
> 기준 develop: `0148d0491c5d947a88ebe353d0f4f37e30b9da60` (#178 squash merge)
> 관련: [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-080](ADR-080-private-admission-currentness-handoff-contract.md), [ADR-081](ADR-081-provider-witness-lifetime-foundation.md), [ADR-087](ADR-087-custody-policy-provisioning-initializer-provenance-contract.md), [ADR-091](ADR-091-confirmation-verifier-reuse-live-lineage-foundation.md), [검증](../10-operations/fresh-journal-lineage-observation-validation.md)

## Dependency 판정

#178은 held live-lineage transport를 제공하지만 source authenticity, independently provisioned producer, fresh external-journal transaction과 `CurrentnessWitness` 발급은 제공하지 않는다. 다음 후보를 현재 merged source와 함께 비교했다.

| 후보 | 현재 dependency·trust 경계 | 판정 |
|---|---|---|
| A Authenticated Live-Lineage Source | accepted producer/provisioner와 source authenticity가 필요하다. 현재 root·issuer purpose가 없다. | 외부 authority 전에는 구현 금지 |
| B CurrentnessWitness | A, fresh complete journal/history, exact pin, live lease/transaction이 모두 필요하다. | 직접 발급 금지 |
| C Original Confirmation Authenticity | 별도 confirmation signer purpose/domain/lifecycle 또는 외부 accepted source가 필요하다. | ADR-091 C 판정 유지 |
| D Private Admission/Pin Handoff prerequisite | public journal fresh read와 held lineage를 같은 attempt에서 연결하는 infrastructure는 기존 authority 안에서 검증 가능하다. | **선택** |
| E Contract Decision | D의 세부 계약을 이 ADR에서 함께 고정할 수 있다. | 별도 docs-only PR 불필요 |
| F Durable Admission | authenticity·provisioning·currentness witness가 모두 빠져 있다. | 시기상조 |

따라서 다음 최소 coherent unit은 **D의 Fresh Journal–Lineage Observation**이다. 이는 currentness의 필요조건 하나를 실행 검증하지만 충분조건이나 admission은 아니다. 새로운 external trust root, private key, credential, governance actor 또는 permission을 만들지 않는다.

## 계약과 구현

`fresh_journal_lineage._FreshJournalLineageObservations`는 reviewed composition이 주입한 기존 `_LivePolicyLineageSnapshots`와 `JournalRepository`만 받는다. journal Session은 held private-source/caller Session과 반드시 분리하고, 두 root transaction의 identity와 active 상태를 유지한다. nested transaction, transaction 교체·종료, 같은 Session co-mingling은 deny다.

Observation을 열 때 다음 순서를 두 번 수행한다.

1. 원래 lineage/confirmation/canonical payload/action/history/pin/lease/transaction chain을 same-handle로 재검증한다.
2. 외부 journal의 complete ordered history를 검증하고 head를 다시 읽는다.
3. journal head가 private pin의 journal·installed projection과 exact 일치하는지 확인한다.
4. ACTIVE key가 정확히 하나이며 key ID/fingerprint/status/taint/invalidation이 pin과 일치하는지 확인한다.
5. source chain과 journal root transaction을 다시 확인하고 동일 snapshot을 재독한다.

반환값은 provider registry에만 존재하는 non-exportable opaque handle이다. public constructor, copy/deepcopy/pickle/JSON/DB receipt가 없으며 다른 provider/handle은 기존 valid source를 폐기하지 않는다. 실제 관측 mismatch, moving head/history, transaction 교체, source 변경, I/O/API 예외는 observation과 lineage·parent confirmation chain을 whole-attempt permanent abandon한다. matching 값 복원, 새 savepoint 또는 같은 stale handle로 재활성화하지 않는다.

## Authority가 아닌 것

complete public history와 exact pin equality는 local integrity/comparison일 뿐 authenticated journal source나 independently provisioned verifier를 증명하지 않는다. Observation handle은 `ProvisioningWitness`, `CurrentnessWitness`, `CommittedAdmissionWitness`, admission 또는 authorization이 아니다. `_ProviderWitnessLifetime._register_after_independent_currentness()`를 호출하지 않으며 `UnavailableCurrentnessPorts`가 유일한 production concrete composition으로 남는다.

valid signature != current authority, authenticated source != currentness, currentness != admission, mutex != admission, comparison PASS != authority 원칙을 유지한다. ADR-077 deployment verifier authority를 confirmation에 재사용하지 않는다.

## Transaction·persistence·다음 dependency

Repository는 기존처럼 flush/read-only 계약이며 이 Foundation의 `commit()`·`rollback()`·hidden retry는 0이다. app DB, external journal schema v1과 Alembic `20260918_0037`을 변경하지 않는다. journal과 private file의 distributed atomicity, writer/provisioning, crash reconciliation, same-event pin installer도 구현하지 않는다.

다음 dependency는 independently authenticated lineage/provisioning source 또는 externally approved Original Confirmation verifier purpose다. 그 authority가 마련된 뒤에만 이 observation을 actual `CurrentnessWitness` 발급의 필요 입력으로 사용할 수 있다. Durable Admission은 authenticity, custody/provenance, live lineage, witness lifetime, OS serialization, exact binding과 transaction ownership이 독립 검증된 뒤 별도 Foundation으로 진행한다. 이 PR은 OPEN/Draft에서 종료하고 Ready/merge/source 삭제하지 않는다.
