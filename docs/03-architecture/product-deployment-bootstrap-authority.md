# Product/Deployment Bootstrap Authority

> 문서 상태: [Decision 채택 — #162 merged, 운영 비활성]
> 최종 수정일: 2026-10-04
> 관련 문서: [ADR-076](../11-decisions/ADR-076-product-deployment-bootstrap-authority.md), [인증](local-operator-authentication.md), [Rights](dohavocal-production-rights-domain.md), [검증](../10-operations/product-deployment-bootstrap-authority-validation.md)

## Authority와 검증 경계

Canonical 채택 결정은 #162 merged ADR-076이다. external human designation → separately pinned root verifier → signed exact-scope deployment approval → custodian proof/assignment → installation-local claim AND fresh WebAuthn human principal → first principal-owner binding으로 이어진다. Designation은 application 밖의 governance root assertion이며 self-hosted human의 명시 지정·수락과 trusted ceremony의 독립 fingerprint 대조가 root provenance다. OS admin/설치자/CLI/Local Operator/reviewer/secret possession으로 root를 추정하지 않는다.

Custodian stable opaque deployment reference와 pin한 public proof key는 미래 target internal principal UUID와 별개다. 같은 human이어도 custodian assignment proof와 target authentication은 둘 다 필요하다. Approval과 claim은 exact installation/Workspace/existing owner를 bind하고 claim은 target principal도 bind한다. Workspace owner 변경·ACTIVE Grant 자동 생성은 없다.

## State와 transaction 경계

Current status는 monotonic revision/current projection으로 읽는다. signed issuance artifact와 immutable status history를 구분한다. Bootstrap guard는 Rights guard와 별개이며 실제 UPDATE/CAS/unique first-binding invariant를 caller transaction에서 사용한다. expiry·root/assignment 상태·principal eligibility와 scope를 fresh 검증해야 한다.

Application DB와 독립 외부 deployment journal 간 atomic commit을 가정하지 않는다. guard/검증 → 외부 journal seal CAS → DB claim consume + binding/history/audit commit → journal SUCCESS 감사 표시 순서다. 외부 SEALED 사실은 DB commit 실패에도 취소하지 않는다. UNCERTAIN은 fail closed하며 자동 binding 재생성/target 교체/claim 재발급은 없다. crash는 availability 손실로 처리하고 별도 Recovery Decision 전 새 binding을 생성하지 않는다.

## Clone·restore·소멸

Installation random ID와 private proof key의 possession을 함께 검사한다. DB/artifact/secret만 복사하면 다른 installation의 proof와 exact scope에서 deny한다. old DB restore는 독립 journal의 sealed/successful history로 차단한다. 새 approval·root rotation·재설치로 같은 Workspace lineage의 bootstrap을 초기화하지 않는다. external journal/private keys까지 전체 rollback 또는 privileged compromise에 대한 완전한 hardware anti-rollback은 보장하지 않는다. trusted local deployment 경계 밖 사고이며 unlocked fallback은 없다.

## 현재 상태와 후속

DEFINED/ADOPTED: bootstrap external root 및 verification/trust-chain contract (#162).

별도 [issuance-integrity verifier Foundation](bootstrap-issuance-integrity-verifier.md)은 #163 merged이며 결과는 permission/current status proof가 아니다. [ADR-078 current-status/lifecycle Contract](deployment-verifier-current-status.md)는 #164로 채택·merged됐고, 이후 public journal·currentness·admission chain과 production configuration/private source Foundation은 #192까지 병합됐다. merged PR #193의 ADR-106 existing-only External Journal Factory를 포함한 최신 범위는 연결된 lifecycle 문서를 따른다. 실제 trusted private sources/journal provisioning, 초기 ACL/custody·identity/GENESIS 확립, authentication·final admission/activation wiring과 전체 production bootstrap은 여전히 비활성이다. installation/approval/custodian/claim의 운영 ceremony, WebAuthn adapter, principal registry/binding, Recovery/Transfer/Rights Writer/Evidence/Production Adapter는 미구현이다. 전체 bootstrap schema 필요 판정, ADR-042/075 의미와 ADR-077 원본·crypto source를 보존하며 application DB schema와 Alembic `20260918_0037`은 변경하지 않는다.

## 독립 최초 등록과 소비 authority

[ADR-107 Independent Bootstrap Lineage Authority](../11-decisions/ADR-107-independent-bootstrap-lineage-authority.md)는 독립 registry + signed intent, 외부 root 기반 최초 등록과 GENESIS 전 영구 소비를 정의한 설계 결정이다. 설계 DECIDED와 구현·운영을 구분하며 병합 상태는 [PR #195](https://github.com/DohaStudio/DohaMusic/pull/195)를 따른다. Production External Journal Provisioning 및 Initial GENESIS 실행은 BLOCKED / NOT IMPLEMENTED, authentication·activation은 UNAVAILABLE다. [ADR-108](../11-decisions/ADR-108-ibla-anchor-coverage-ledger-checkpoint-contract.md)은 Anchor / Complete-Coverage Ledger / Independent Checkpoint Contract를 DECIDED한 설계 결정이다. 검토·병합 상태는 [PR #197](https://github.com/DohaStudio/DohaMusic/pull/197)을 따른다. [ADR-109](../11-decisions/ADR-109-ibla-ledger-independent-checkpoint-persistence-foundation.md)의 L/H Persistence Foundation public mechanics를 구현·검증했다. 검토·병합 상태는 [PR #198](https://github.com/DohaStudio/DohaMusic/pull/198)을 따른다. Source Verifier/Capability는 IMPLEMENTED FOUNDATION으로 구현했으며 Initial Authorization → Provisioning/GENESIS는 NOT IMPLEMENTED다. 독립 운영 custody·commissioning/authentication/activation은 unavailable다.


[ADR-110](../11-decisions/ADR-110-ibla-authentic-source-first-registration-contract.md)은 Authentic Source / Complete Coverage / First-Registration Eligibility / Capability Handoff Contract를 DECIDED했다. root-signed A와 독립 initializer 원본·complete scope inventory·전체 L/current H를 결합하며, PRE-REGISTRATION capability와 L durable REGISTRATION_COMMITTED 이후 POST 경계를 구분한다. 계약에 따른 Authentic IBLA Source Verifier + First-Registration Capability Foundation을 구현했다. 검토·병합 상태는 [PR #200](https://github.com/DohaStudio/DohaMusic/pull/200)을 따른다. L/H와 Source Verifier/Capability는 IMPLEMENTED FOUNDATION, Initial Authorization·REGISTRATION_COMMITTED writer·Provisioning/GENESIS·Recovery/Transfer는 NOT IMPLEMENTED, Authentication/Activation은 UNAVAILABLE다. Phase 9는 0/18, 0%를 유지한다. capability는 등록 완료·Authorization이 아니며 L/H/app DB/journal mutation은 0이다. 실제 production source는 unavailable를 유지한다. [구현 검증 보고서](../10-operations/ibla-source-verifier-capability-validation.md)를 따른다.

[ADR-111](../11-decisions/ADR-111-ibla-registration-commit-authority-post-boundary-contract.md)은 명시 위임된 Registry Custodian의 exact Registration Writer로 PRE capability를 direct one-shot handoff하고, 등록 전용 root intent·독립 initializer 확인을 별도로 요구한다. H PREPARED → L durable REGISTRATION_COMMITTED(POST) → 독립 H CONFIRMED를 적용하며 Writer는 NOT IMPLEMENTED다. 후속 IA의 POST 목적과 INITIAL_SEALED 소비 의미는 기존 ADR-107을 보존한다.
