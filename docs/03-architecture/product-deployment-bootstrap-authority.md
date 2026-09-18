# Product/Deployment Bootstrap Authority

> 문서 상태: [Decision 채택 — #162 merged, 운영 비활성]
> 최종 수정일: 2026-09-18
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

별도 [issuance-integrity verifier Foundation](bootstrap-issuance-integrity-verifier.md)은 #163 merged이며 결과는 permission/current status proof가 아니다. 직접 선행 [current-status/lifecycle Contract](deployment-verifier-current-status.md)는 별도 Draft다. NOT IMPLEMENTED: trusted provisioning/private store/current status, installation/approval/custodian/claim/journal, WebAuthn adapter, principal registry/binding, Recovery/Transfer/Rights Writer/Evidence/Production Adapter. 전체 bootstrap schema 필요 판정은 유지하며 이번 Contract는 migration 0이다. ADR-042/075 의미와 ADR-077 원본·crypto source는 보존한다. persistence/ceremony는 Contract 검증/채택 뒤 별도 Foundation이다.
