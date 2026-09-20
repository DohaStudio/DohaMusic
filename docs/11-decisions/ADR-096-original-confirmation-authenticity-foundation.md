# ADR-096: Original Confirmation Authenticity Foundation

> 상태: 채택 — #183 merged, 운영 비활성
> 작성/최종 수정일: 2026-09-20
> 기준 develop: `3f7a390d04f8bd39fdce7163a3322a78f8b7e06d` (#182 squash merge)
> 관련: [ADR-090](ADR-090-original-confirmation-canonical-payload-foundation.md), [ADR-093](ADR-093-scoped-provisioning-authority-verification-foundation.md), [ADR-094](ADR-094-authenticated-scoped-provisioning-authority-source-foundation.md), [ADR-095](ADR-095-active-provisioning-verifier-material-foundation.md), [검증](../10-operations/original-confirmation-authenticity-validation.md)

## 결정

Held original-confirmation raw snapshot, canonical payload boundary와 ADR-095 ACTIVE verifier material을 결합해 Ed25519 authenticity만 검증하는 최소 Foundation을 채택한다. Detached signature는 신뢰 source가 아니라 공격자 입력으로 취급한다. 따라서 signature용 새 저장소나 authority를 만들지 않고, 현재 held public key로 수학적 검증을 통과한 경우에만 provider-internal opaque handle을 유지한다.

서명 message는 ASCII `DohaMusicOriginalInitializerConfirmationV1` + NUL + exact canonical payload bytes다. ADR-093 authority-event domain, ADR-076 `FIRST_OWNER_BINDING_ONLY` approval domain 또는 다른 purpose/domain의 signature를 재사용하지 않는다.

## Exact binding

Authenticity 결과는 confirmation/action/policy/designation/initializer/replay identity, lineage anchor/source/digest, installation/producer, verifier key ID/fingerprint, authority revision/head, material ID/revision, payload/signature digest에 결박된다. Payload initializer는 scoped authority producer와 같아야 하며 payload verifier identity는 held material의 ACTIVE projection과 정확히 같아야 한다.

Caller가 bool, dict, 임의 fingerprint 또는 signature 성공값을 주입할 수 없다. 외부 반환값 없이 복사·직렬화 불가능한 내부 handle만 사용하며 record는 exact immutable primitive binding을 보존한다.

## 수명·TOCTOU

검증 순서는 `held payload revalidate → ACTIVE material/authority revalidate → same-handle payload reread → signature verify → material/authority revalidate → held payload/lineage revalidate → opaque handle`이다. 후속 handoff도 전체 검증을 반복한다.

Confirmation/material/source 교체, authority rotate/revoke, payload·scope·lineage·replay mismatch, witness/lease/transaction 무효화 또는 예외는 authenticity와 양쪽 parent chain을 영구 abandon한다. 값 복원, old-key fallback, terminal reactivation은 없다. 기존 Windows serialization, witness lifetime과 custody handle을 우회하는 새 lock authority를 추가하지 않는다.

## 비권한 경계

Authentic confirmation은 “이 exact canonical confirmation이 현재 held scoped provisioning verifier material로 이 confirmation domain에서 서명됐다”만 뜻한다. Current lineage, CurrentnessWitness, Durable Admission, Rights, human acceptance 또는 향후 source completeness를 증명하지 않는다.

Production signer/private key/credential/ceremony/port, app DB·external journal schema, migration, Repository transaction은 추가하지 않는다. 실제 production composition은 계속 unavailable이다.

## 후속 dependency

후속 [ADR-097](ADR-097-authentic-confirmation-lineage-correlation-foundation.md)은 authentic confirmation을 기존 held live lineage와 ADR-092 fresh journal-lineage observation에 exact 비교한다. 이번 Foundation에서 CurrentnessWitness나 Admission으로 확장하지 않는다.
