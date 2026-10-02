# Deployment Verifier Current-Status / Lifecycle Contract

> 문서 상태: [Contract #164 merged — 운영 비활성]
> 최종 수정일: 2026-10-03
> 관련 문서: [ADR-078](../11-decisions/ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-076](../11-decisions/ADR-076-product-deployment-bootstrap-authority.md), [issuance verifier](bootstrap-issuance-integrity-verifier.md), [검증](../10-operations/deployment-verifier-current-status-validation.md)

Canonical 결정·wire·state·admission 계약은 ADR-078이다. #163 merged issuance verifier는 그대로 유지하며 current root/status authority로 확대하지 않는다.

후속 [ADR-079 Foundation](../11-decisions/ADR-079-independent-lifecycle-journal-persistence-foundation.md)은 #165 merged로 독립 public journal persistence/strict event verifier와 unavailable private port 골격을 제공한다. 실제 최신 범위·제한은 ADR-079와 [DB 계약](../07-database/deployment-lifecycle-journal.md)을 따른다. [ADR-080 handoff Contract](../11-decisions/ADR-080-private-admission-currentness-handoff-contract.md)는 #166 merged로 provider-owned witness/lease/durable admission/pin 설치 책임을 구체화했다. production admission/pin/OS ceremony는 여전히 unavailable다.

Bootstrap 최신 Track: #164~#170/#172~#193는 merged다. [ADR-097 exact correlation](../11-decisions/ADR-097-authentic-confirmation-lineage-correlation-foundation.md)은 authenticity·held lineage·fresh observation을 같은 handles/lease/두 transaction에 결합한다. [ADR-098 CurrentnessWitness handoff](../11-decisions/ADR-098-currentness-witness-handoff-foundation.md)는 original correlation, native lease, caller root transaction과 `_ProviderWitnessLifetime` single attempt를 발급 전후 및 매 사용 시 재검증한다. [ADR-099 AdmissionAttempt Provider](../11-decisions/ADR-099-admission-attempt-provider-foundation.md)는 live witness를 strict canonical lifecycle candidate와 one-attempt로 결합한다. [ADR-100 Transaction Owner](../11-decisions/ADR-100-admission-journal-transaction-owner-foundation.md)는 기존 CAS/final guard와 external commit outcome을 소유한다. [ADR-101 Commit Reconciler](../11-decisions/ADR-101-admission-commit-reconciler-foundation.md)는 opaque ambiguous-commit handoff를 complete-history snapshots로 read-only 판정한다. [ADR-102 Durable Admission Orchestrator](../11-decisions/ADR-102-durable-admission-orchestration-foundation.md)는 이 exact component chain을 조정하며 direct/reconciled exact commit만 성공으로 수렴시킨다. 이후 [ADR-103 Production Composition](../11-decisions/ADR-103-durable-admission-production-composition-foundation.md), [ADR-104 reviewed configuration](../11-decisions/ADR-104-reviewed-production-deployment-configuration-foundation.md), [ADR-105 private source descriptors](../11-decisions/ADR-105-production-private-authority-source-factory-foundation.md)가 병합됐다. merged PR #193의 [ADR-106 External Journal Factory](../11-decisions/ADR-106-production-external-journal-factory-foundation.md)는 이미 provision된 exact journal의 schema/history/integrity와 Windows native identity를 검증하고 pinned SQLite connection·bounded root Session을 제공한다. Durable result도 Rights/Workspace authority가 아니며 실제 journal provisioning·authentication·final admission/activation wiring은 unavailable이다. schema/migration과 Alembic `20260918_0037`은 유지한다.

## 서로 대체할 수 없는 evidence

| evidence | 무엇을 증명하는가 | 대체할 수 없는 것 |
|---|---|---|
| issuance integrity receipt | 과거 approval signature/typed exact scope/window | pin ceremony/current root/approval/assignment/journal/proof/auth/claim |
| independently provisioned pin provenance | 외부 designation/public key/journal identity 연결 | 현재 root status 또는 complete history |
| fresh journal read/private lease witness | serialized authoritative HEAD·root lifecycle/currentness | fresh installation/Custodian possession·principal/WebAuthn·one-time binding |
| normal cross-signature + external designation update | 동일 lifecycle event의 old/new key 전환 admission | compromised key의 successor self-authorization |
| independent external redesignation | ADR-076 root의 compromise/loss 뒤 새 pin admission | journal history reset·Recovery/Transfer·successful seal 해제 |

## Side-effect와 crash 경계

durable external journal admission 먼저, separately provisioned public pin projection 다음이다. exact revision/digest 연결 불명 또는 old cached DB 상태는 deny다. application DB rollback이 journal revocation/rotation을 rollback하지 않는다. completed admission의 동일 public projection 설치만 보완 가능하고 새 authority나 bootstrap success를 자동 생성하지 않는다. terminal key는 다시 ACTIVE가 되지 않는다. 과거 서명의 수학적 검증은 별개다.

ADR-078의 complete ceremony/private provenance/currentness/pin 설치는 여전히 미구현이다. ADR-079 public journal CAS 및 ADR-081 lifetime, 새 ADR-082 실제 Windows exclusion mechanics를 전체 trusted admission 증거로 확대하지 않는다. reviewed independent evidence provider/production journal admission adapter·read witness가 없어 production는 unavailable이다. caller enum/UUID/receipt/public row/OS lock 획득을 허가로 사용할 수 없다.

## 다음 unit과 비목표

Lifecycle Contract #164, public journal #165, private handoff #166, witness lifetime #167, Windows serialization #168, pin facts #169는 병합됐다. ADR-084는 A의 작은 직접 선행 Contract이며 실제 trusted reader/ceremony/admission 구현과 분리한다. 실제 root/key/journal provisioning·서명 ceremony를 수행하거나 현재 권한/법적 사람을 특정하지 않는다. app migration은 0이고 external schema v1은 독립 version Gate다. private reader/currentness·commit reconciliation의 내부 Foundation과 실제 production provisioning·OS custody/pin install·activation은 구분하며 후자는 계속 후속이다. claim/binding/WebAuthn/Recovery/Writer를 합치지 않는다.

## 독립 최초 등록과 소비 authority

[ADR-107 Independent Bootstrap Lineage Authority](../11-decisions/ADR-107-independent-bootstrap-lineage-authority.md)는 독립 registry + signed intent, 외부 root 기반 최초 등록과 GENESIS 전 영구 소비를 정의한 설계 결정이다. 설계 DECIDED와 구현·운영을 구분하며 병합 상태는 [PR #195](https://github.com/DohaStudio/DohaMusic/pull/195)를 따른다. Production External Journal Provisioning 및 Initial GENESIS 실행은 BLOCKED / NOT IMPLEMENTED, authentication·activation은 UNAVAILABLE다. [ADR-108](../11-decisions/ADR-108-ibla-anchor-coverage-ledger-checkpoint-contract.md)은 Anchor / Complete-Coverage Ledger / Independent Checkpoint Contract를 DECIDED한 설계 결정이다. 검토·병합 상태는 [PR #197](https://github.com/DohaStudio/DohaMusic/pull/197)을 따른다. [ADR-109](../11-decisions/ADR-109-ibla-ledger-independent-checkpoint-persistence-foundation.md)의 L/H Persistence Foundation public mechanics를 구현·검증했다. 검토·병합 상태는 [PR #198](https://github.com/DohaStudio/DohaMusic/pull/198)을 따른다. Source Verifier/Capability는 IMPLEMENTED FOUNDATION으로 구현했으며 Initial Authorization → Provisioning/GENESIS는 NOT IMPLEMENTED다. 독립 운영 custody·commissioning/authentication/activation은 unavailable다.


[ADR-110](../11-decisions/ADR-110-ibla-authentic-source-first-registration-contract.md)은 Authentic Source / Complete Coverage / First-Registration Eligibility / Capability Handoff Contract를 DECIDED했다. root-signed A와 독립 initializer 원본·complete scope inventory·전체 L/current H를 결합하며, PRE-REGISTRATION capability와 L durable REGISTRATION_COMMITTED 이후 POST 경계를 구분한다. 계약에 따른 Authentic IBLA Source Verifier + First-Registration Capability Foundation을 구현했다. 현재 제출은 Draft PR 검토 단계이며 Ready·병합하지 않는다. L/H와 Source Verifier/Capability는 IMPLEMENTED FOUNDATION, Initial Authorization·REGISTRATION_COMMITTED writer·Provisioning/GENESIS·Recovery/Transfer는 NOT IMPLEMENTED, Authentication/Activation은 UNAVAILABLE다. Phase 9는 0/18, 0%를 유지한다. capability는 등록 완료·Authorization이 아니며 L/H/app DB/journal mutation은 0이다. 실제 production source는 unavailable를 유지한다. [구현 검증 보고서](../10-operations/ibla-source-verifier-capability-validation.md)를 따른다.
