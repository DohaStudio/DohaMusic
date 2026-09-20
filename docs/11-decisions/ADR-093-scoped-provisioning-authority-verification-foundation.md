# ADR-093: Scoped Provisioning Authority Verification Foundation

> 상태: [채택 — #180 merged; 운영 비활성]
> 작성일·최종 수정일: 2026-09-20
> 기준 develop: `cfa1678519b6fba7ea2b0699f5bca518eae99bfb` (#179 squash merge)
> 관련: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-077](ADR-077-bootstrap-issuance-integrity-verifier-foundation.md), [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-087](ADR-087-custody-policy-provisioning-initializer-provenance-contract.md), [ADR-091](ADR-091-confirmation-verifier-reuse-live-lineage-foundation.md), [ADR-092](ADR-092-fresh-journal-lineage-observation-foundation.md), [검증](../10-operations/scoped-provisioning-authority-validation.md)

## Governance Decision

Product/Deployment governance는 ADR-076의 기존 external root로 exact installation의 initializer/provisioning producer와 verifier key ID·fingerprint를 `INSTALLATION_POLICY_PROVISIONING_ONLY` 목적에 한해 승인할 수 있다. 이는 새 external trust root가 아니다. ADR-091의 `VERIFIER_INFRASTRUCTURE_ONLY_REUSE` 판정을 유지하며 기존 `FIRST_OWNER_BINDING_ONLY` deployment approval이나 다른 purpose의 verifier를 자동 승격하지 않는다.

이 authority는 Original Confirmation authenticity와 live-lineage provisioning source authenticity의 제한된 선행 근거만 제공한다. Workspace ownership/owner impersonation, Rights Grant·Revoke·Supersede, Consent, Approval, OUTPUT_READ, WebAuthn, CurrentnessWitness, Durable Admission, Recovery, Transfer, runtime administrator 또는 arbitrary signing authority를 포함하지 않는다.

## Dependency 재판정과 선택

| 후보 | 현재 판정 |
|---|---|
| A Scoped Provisioning Authority Verification | 새 Decision으로 root-signed exact scope/lifecycle 검증 가능; **선택** |
| B Authenticated Original Confirmation | A와 independently sourced complete current projection, provisioned verifier bytes가 먼저 필요 |
| C Authenticated Live-Lineage Source | A와 별도 live-lineage signing domain, authenticated complete source가 먼저 필요 |
| D A+B/C combined | 독립 검증 단위를 불필요하게 결합하므로 기각 |
| E CurrentnessWitness | authenticated confirmation/source와 ADR-092 observation 결합 전 발급 금지 |

따라서 가장 작은 coherent Foundation은 A다. 실제 credential이나 production ceremony 없이 deterministic disposable fixture로 wire·crypto·lifecycle을 검증할 수 있고 B/C의 purpose confusion과 cross-domain replay를 먼저 제거한다.

## Wire와 exact scope

authorization event schema는 `dohamusic/scoped-provisioning-authority-event/v1`, algorithm은 `Ed25519`, root signature domain은 ASCII `DohaMusicScopedProvisioningAuthorityEventV1` + NUL이다. 각 event는 authorization/event identity, semantic revision, predecessor digest, event kind, ADR-076 root/designation identity, exact installation, producer, purpose, confirmation/lineage/policy domain, old/new verifier identity와 governance provenance digest를 서명한다.

고정 값은 다음과 같다.

- purpose: `INSTALLATION_POLICY_PROVISIONING_ONLY`
- Original Confirmation domain: `DohaMusicOriginalInitializerConfirmationV1`
- live-lineage domain: `DohaMusicLivePolicyLineageProvisioningV1`
- policy domain: `dohamusic/installation-policy-provisioning/v1`

Wildcard installation/producer/key/purpose, unknown·missing field, duplicate JSON key, float/bool revision, 비정규 UUID/digest/reference, malformed UTF-8/base64url과 다른 signing domain은 거절한다. Root public key는 independently supplied `PinnedRootVerifier`의 exact identity/fingerprint와 일치해야 하며 artifact가 public key를 self-enroll하지 않는다.

## Lifecycle·rotation·revocation·replay

Complete bounded history의 첫 event는 revision 1 `AUTHORIZE`이고 predecessor와 old verifier는 null, new verifier는 exact 값이어야 한다. 이후 revision은 1씩 증가하고 이전 canonical signed-envelope digest를 predecessor로 가진다.

- `ROTATE`: current old verifier를 exact predecessor로 지정하고 한 번도 사용하지 않은 successor ID와 fingerprint를 설치한다. old projection은 `SUPERSEDED`, successor는 `ACTIVE`다.
- `REVOKE`: current verifier를 exact predecessor로 지정하고 successor 없이 `REVOKED` terminal projection을 만든다.
- revoke 뒤 event, superseded/revoked key ID 또는 fingerprint 재사용, stale revision, forked predecessor와 duplicate event identity는 거절한다.

여기서 rotation 대상은 scoped provisioning verifier다. ADR-076 Product/Deployment root가 rotate/revoke/compromise된 경우 서로 다른 root key로 같은 scoped history를 이어 붙이지 않는다. independently current한 successor root가 새 authorization ID로 scope 전체를 다시 승인해야 하며 old receipt는 historical audit만 남는다. Compromise도 scoped chain을 `REVOKE` terminal로 닫고 명시적으로 승인된 새 authorization 없이는 fallback하지 않는다.

현재 projection은 timestamp 최신순이 아니라 verified revision/predecessor chain으로 계산한다. 다만 caller가 제공한 history의 외부 완전성·최신성과 ADR-076 root의 현재 eligibility는 이 stateless verifier가 증명하지 않는다. future authenticated source가 complete history/head와 independently provisioned root를 연결해야 한다. `ProvisioningAuthorityIntegrityReceipt`는 검증된 public history일 뿐 capability가 아니며 constructor/receipt 재생으로 source authenticity, Original Confirmation validity, current lineage, CurrentnessWitness 또는 admission을 만들 수 없다.

## Persistence·rollout·감사 경계

이번 Foundation은 App DB/external journal schema, Alembic, Repository, production port와 writer를 추가하지 않는다. `commit()`/`rollback()`/hidden retry는 0이고 기존 `UnavailableCurrentnessPorts`를 유지한다. 실제 Product/Deployment private key, production verifier key, signed authorization, credential provisioning, ceremony, User/production DB는 사용하지 않는다.

감사는 immutable authorization/event ID, revision, predecessor, verifier history/status와 governance provenance digest로 수행한다. 실제 durable source와 CAS/TOCTOU serialization은 후속 adapter 책임이다. Production 활성화 전에는 complete authority history/head의 independently authenticated source, verifier bytes provisioning, root currentness와 source reread가 추가로 필요하다.

다음 최소 dependency는 **Authenticated Scoped Provisioning Authority Source Foundation**이다. 그것이 complete current projection과 verifier bytes를 held source/lease/transaction에 연결한 뒤 Original Confirmation authenticity와 live-lineage source authenticity를 각각의 domain으로 구현한다. 두 authenticity와 ADR-092 fresh observation이 모두 확보되기 전 CurrentnessWitness를 발급하지 않는다.
