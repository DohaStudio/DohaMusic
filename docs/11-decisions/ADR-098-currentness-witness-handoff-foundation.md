# ADR-098: CurrentnessWitness Handoff Foundation

> 상태: 제안 — Foundation 구현·검증 완료, 운영 비활성
> 작성/최종 수정일: 2026-09-21
> 기준 develop: `d319790cf8e39cf5f19300ad2761e73089948271` (#184 squash merge)
> 관련: [ADR-080](ADR-080-private-admission-currentness-handoff-contract.md), [ADR-081](ADR-081-provider-witness-lifetime-foundation.md), [ADR-082](ADR-082-windows-ceremony-serialization-foundation.md), [ADR-097](ADR-097-authentic-confirmation-lineage-correlation-foundation.md), [검증](../10-operations/currentness-witness-handoff-validation.md)

## 결정

ADR-097의 exact correlation은 authenticated provisioning authority, ACTIVE verifier material, authentic Original Confirmation, held live lineage와 fresh journal observation을 이미 같은 parent handles, Windows lease, caller root transaction과 journal root transaction에 결합한다. 따라서 별도 trust root, signing purpose, schema 또는 durable credential을 만들지 않고 기존 `_ProviderWitnessLifetime`의 한 attempt에 이 correlation을 연결하는 것이 다음 최소 Foundation이다.

`_CurrentnessWitnessHandoff`는 provider 내부 전용 adapter다. exact `_ConfirmationLineageCorrelations`와 그 correlation이 실제 사용한 동일 `_ProviderWitnessLifetime`만 받는다. public constructor나 production port로 노출하지 않으며 `UnavailableCurrentnessPorts`는 계속 유일한 production composition이다.

## 발급 순서와 exact binding

발급은 다음 검사를 같은 protected lifetime에서 수행한다.

1. exact attempt와 exact correlation handle을 provider registry identity로 찾는다.
2. attempt의 original lease, caller `Session`과 root `SessionTransaction`, `CurrentnessBinding`이 correlation의 것과 동일한지 확인한다.
3. 요청 scope가 binding의 exact affected scope인지 확인한다.
4. Windows serialization lease와 전체 affected scopes를 재검증한다.
5. ADR-097 correlation을 original parent handles와 immutable facts로 재검증한다.
6. `_ProviderWitnessLifetime._register_after_independent_currentness()`로 single-assignment witness를 발급한다.
7. correlation, serialization lease, attempt/transaction/binding을 다시 검증한 뒤에만 opaque handle을 caller context에 넘긴다.

Witness는 attempt identity, original Windows lease, caller root transaction, exact correlation handle과 exact scope에 동시에 bind된다. 다른 attempt·lease·transaction·correlation·scope에서는 사용할 수 없다. bool/int/dict/digest/caller token이나 복사된 correlation fields는 witness가 아니다. Handle은 복사·deepcopy·pickle·subclass·caller construction을 거부한다.

## 재검증과 one-way invalidation

매 사용 시 lifetime binding → exact correlation → Windows serialization → lifetime binding 순서로 재검증한다. Journal head/lineage/confirmation/pin/material/source 변화, verifier rotate/revoke, lease release, provider rejection, transaction replacement, parent mismatch, context exit 또는 consumer exception이 관측되면 local witness, provider attempt와 correlation chain을 폐기한다. 폐기된 identity는 이전 값이 복원되어도 재활성화하지 않는다.

Foreign witness처럼 registry에 존재하지 않는 입력은 live attempt를 폐기할 권한이 없다. 반대로 이미 발급된 actual witness에 잘못된 parent를 제시하면 그 witness 자체가 신뢰할 수 없는 사용 경로에 노출됐으므로 whole attempt를 fail closed로 폐기한다.

동일 attempt의 issue/issue 경쟁은 `_ProviderWitnessLifetime`의 lock과 single assignment로 winner 하나만 허용한다. 패배한 duplicate는 winner를 폐기하지 않는다. Issue 이후 revoke/rotate/journal·lineage move/lease release/transaction replacement는 다음 재검증에서 영구 거부된다.

## 권한 및 영속성 경계

CurrentnessWitness는 “한 exact attempt에서 필요한 authenticated/current facts가 동일 protected lifetime과 transaction 안에서 동시에 재검증됐다”는 bounded ephemeral evidence다. 다음이 아니다.

- Durable Admission, bootstrap completion 또는 reusable credential
- Authorization, Rights, workspace ownership, consent, approval 또는 human acceptance
- production private key, signer, credential provisioning 또는 external trust root

Witness와 attempt는 메모리 내부 lifetime에만 존재한다. DB persistence, migration, Repository `commit()`/`rollback()`, writer, public API, frontend 또는 runtime wiring은 추가하지 않는다. Alembic head `20260918_0037`을 유지한다. Durable Admission은 이 witness를 소비하는 별도 Foundation에서만 결정한다.
