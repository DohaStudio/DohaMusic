# ADR-097: Authentic Confirmation–Lineage Correlation Foundation

> 상태: 제안 — Foundation 구현·검증 완료, 운영 비활성
> 작성/최종 수정일: 2026-09-20
> 기준 develop: `6cc249db1fe9dd1e455fcf47a30b68c1d108f845` (#183 squash merge)
> 관련: [ADR-091](ADR-091-confirmation-verifier-reuse-live-lineage-foundation.md), [ADR-092](ADR-092-fresh-journal-lineage-observation-foundation.md), [ADR-094](ADR-094-authenticated-scoped-provisioning-authority-source-foundation.md), [ADR-095](ADR-095-active-provisioning-verifier-material-foundation.md), [ADR-096](ADR-096-original-confirmation-authenticity-foundation.md), [검증](../10-operations/authentic-confirmation-lineage-correlation-validation.md)

## Dependency 판정

A의 Authentic Confirmation–Live Lineage와 C의 Fresh Observation–Authenticity 비교는 실제 handle graph에서 분리할 수 없다. ADR-092 observation은 이미 exact live-lineage handle과 confirmation handle을 수명 단위로 소유하고, ADR-096 authenticity는 같은 confirmation에서 material/authority/designation chain을 소유한다. 둘 중 한쪽만 비교하면 journal transaction 또는 provisioning material lifecycle을 결박하지 못한다.

따라서 D의 최소 combined Foundation을 채택한다. 한 provider-internal correlation이 기존 authenticity, live-lineage, fresh observation을 같은 confirmation/lineage/designation/material/authority handle, Windows lease, caller transaction과 journal transaction에 결합한다. 새 external authority, signing purpose, lock, persistence 또는 production port를 만들지 않는다.

## Exact correlation

Correlation은 다음 순서로 수행한다.

1. ADR-096 authenticity와 모든 parent source/material/payload를 same-handle로 재검증한다.
2. ADR-092 observation을 통해 held live lineage, complete journal history/head, exact pin과 별도 journal transaction을 재검증한다.
3. confirmation/action/policy/designation/initializer/replay, installation/producer, anchor/source, 두 domain-separated lineage digest, predecessor/semantic revision/ACTIVE terminal, journal identity/revision/trust/head, authority source/revision/head, verifier key/fingerprint와 material revision, payload/signature/lineage-record digest를 exact primitive로 결합한다.
4. native lease와 caller root transaction, journal Session/root transaction identity를 확인하고 authenticity와 observation 전체를 다시 검증한다.

Root journal key와 provisioning verifier key는 purpose가 다르므로 같은 값으로 비교하지 않는다. 대신 root-authenticated authority history가 선택한 ACTIVE material과 confirmation verifier binding을 검증하고, journal head/pin은 별도 exact current projection으로 검증한다. 이 관계를 단순 fingerprint equality로 축약하지 않는다.

## 수명·실패 의미

결과는 복사·직렬화·외부 생성이 불가능한 opaque internal handle이며 exact parent handle과 immutable facts, 양쪽 root transaction identity를 보존한다. Caller dict/bool/fingerprint/digest만으로 재구성할 수 없다.

Confirmation/lineage/journal head/pin/material/source/semantic revision/predecessor/terminal 상태/transaction/lease가 바뀌거나 parent 검증에서 예외가 나면 correlation과 실제 supplied parent attempt를 영구 abandon한다. 값을 복원해도 stale handle은 재활성화하지 않는다. Foreign correlation handle 하나만으로 live attempt를 폐기하지 않는다. Consumer exception도 성공 handoff로 바뀌지 않는다.

## 비권한 경계와 후속

Correlation은 “이 authentic confirmation과 held live lineage 및 fresh journal observation이 같은 exact authority lineage를 가리킨다”만 증명한다. `CurrentnessWitness`, ProvisioningWitness, Admission, Authorization, Rights 또는 human acceptance가 아니다. `UnavailableCurrentnessPorts`가 유일한 production composition이고 witness registration은 호출하지 않는다.

App/external journal schema, Alembic, Repository transaction, writer와 production credential/key는 변경하지 않는다. 다음 최소 Foundation은 이 opaque correlation을 기존 Windows serialization/lease와 `_ProviderWitnessLifetime`의 단일 attempt에 연결해 actual CurrentnessWitness를 발급·재검증하는 adapter-owned currentness handoff다. Durable Admission은 그 이후 별도 단계다.
