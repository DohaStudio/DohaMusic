# Bootstrap Issuance Integrity Verifier

> 문서 상태: [Foundation #163 merged — 운영 비활성]
> 최종 수정일: 2026-10-01
> 관련 문서: [ADR-076](../11-decisions/ADR-076-product-deployment-bootstrap-authority.md), [ADR-077](../11-decisions/ADR-077-bootstrap-issuance-integrity-verifier-foundation.md), [검증](../10-operations/bootstrap-issuance-integrity-verifier-validation.md)

## 구현한 경계

`verify_issuance_integrity(artifact, root=..., expected_scope=..., checked_at=...)`는 strict envelope parsing → typed fixed payload → independently supplied public verifier/designation/fingerprint와 exact issuance scope 일치 → check 시각 window → Ed25519(domain + NUL + JCS payload) 검증 → immutable digest receipt의 순수 함수다. wire 세부 계약은 ADR-077이 대표 기준이다. raw private key/secret/signing/persistence/파일 loader/API/Worker를 제공하지 않는다.

`PinnedRootVerifier`는 public expectations value일 뿐 trust provisioning proof가 아니며 `ExpectedApprovalScope`도 DB/current-state witness가 아니다. 향후 trusted composition이 독립 designation/fingerprint 대조와 status freshness를 책임져야 한다. artifact 자체의 root key, unknown status/principal fields 또는 fake fallback을 허용하지 않는다. receipt의 공개 필드도 current authorization evidence가 아니다.

## 아직 미구현인 권한 경계

서명 무결성 성공 뒤에도 current root/approval/assignment status·revoke/supersede/consume, journal high-water mark·history/seal, installation/Custodian possession, exact target principal/session/fresh WebAuthn, existing owner/current Workspace/history, DB guard CAS·one-time claim/binding/audit와 seal-first protocol을 모두 검증해야 bootstrap이 가능하다. target principal은 approval issuance가 아니라 claim에 bind되므로 이 verifier의 payload에 임의 추가할 수 없다.

Replay/concurrent integrity checks는 같은 역사적 receipt를 반환할 수 있다. 이는 double-consume winner=1 또는 consumed/revoked bootstrap replay deny 구현의 evidence가 아니다. DB rollback/external seal/restore 및 clock rollback 감지는 후속 persistence/ceremony의 Gate다. Workspace owner/Rights/Approval/Consent에 부작용은 없고 현재 production runtime는 비활성이다.

## Dependency 판정

#163 exact-head Final Validation/squash merge는 완료됐다. ADR-077 원본·approval domain/schema/구현은 보존한다. [ADR-078 current-status/lifecycle Contract](deployment-verifier-current-status.md)는 #164 merged이며 이후 public journal·currentness·admission chain은 별도 Foundation으로 진행됐다. 최신 #192 merged progression과 merged PR #193의 ADR-106 Factory 범위는 연결된 lifecycle 문서를 따른다. Issuance verifier는 과거 receipt의 issuance integrity만 검증하며 journal/admission/pin proof, current authorization 또는 human authentication proof로 승격되지 않는다. 실제 provisioning·authentication·production activation은 계속 unavailable이다.

ADR-076 merged develop에서 독립적으로 검증 가능한 최소 unit C를 선택했다. A는 journal/current-status/principal history 연결을, B는 principal lifecycle와 authentication provenance를 함께 요구한다. 새 authority를 도입하는 Decision은 없고 library/wire implementation details만 ADR-077에 기록한다. additive bootstrap migration과 실제 private-state provisioning은 이번 unit에 필요하지 않다. 기존 Phase/DoD 완료율은 그대로다.

## 독립 최초 등록과 소비 authority

[ADR-107 Independent Bootstrap Lineage Authority](../11-decisions/ADR-107-independent-bootstrap-lineage-authority.md)는 독립 registry + signed intent, 외부 root 기반 최초 등록과 GENESIS 전 영구 소비를 정의한 설계 결정이다. 설계 DECIDED와 구현·운영을 구분하며 병합 상태는 [PR #195](https://github.com/DohaStudio/DohaMusic/pull/195)를 따른다. Production External Journal Provisioning 및 Initial GENESIS 실행은 BLOCKED / NOT IMPLEMENTED, authentication·activation은 UNAVAILABLE다. [ADR-108](../11-decisions/ADR-108-ibla-anchor-coverage-ledger-checkpoint-contract.md)은 Anchor / Complete-Coverage Ledger / Independent Checkpoint Contract를 DECIDED한 설계 결정이다. 검토·병합 상태는 [PR #197](https://github.com/DohaStudio/DohaMusic/pull/197)을 따른다. [ADR-109](../11-decisions/ADR-109-ibla-ledger-independent-checkpoint-persistence-foundation.md)의 L/H Persistence Foundation public mechanics를 구현·검증했으며 Draft 검토 대상이다. Source Verifier/Capability → Initial Authorization → Provisioning/GENESIS는 계속 NOT IMPLEMENTED다. 독립 운영 custody·commissioning/authentication/activation은 unavailable다.
