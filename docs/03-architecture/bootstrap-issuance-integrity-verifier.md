# Bootstrap Issuance Integrity Verifier

> 문서 상태: [진행 중 — 별도 Foundation Draft PR, 운영 비활성]
> 최종 수정일: 2026-09-18
> 관련 문서: [ADR-076](../11-decisions/ADR-076-product-deployment-bootstrap-authority.md), [ADR-077](../11-decisions/ADR-077-bootstrap-issuance-integrity-verifier-foundation.md), [검증](../10-operations/bootstrap-issuance-integrity-verifier-validation.md)

## 구현한 경계

`verify_issuance_integrity(artifact, root=..., expected_scope=..., checked_at=...)`는 strict envelope parsing → typed fixed payload → independently supplied public verifier/designation/fingerprint와 exact issuance scope 일치 → check 시각 window → Ed25519(domain + NUL + JCS payload) 검증 → immutable digest receipt의 순수 함수다. wire 세부 계약은 ADR-077이 대표 기준이다. raw private key/secret/signing/persistence/파일 loader/API/Worker를 제공하지 않는다.

`PinnedRootVerifier`는 public expectations value일 뿐 trust provisioning proof가 아니며 `ExpectedApprovalScope`도 DB/current-state witness가 아니다. 향후 trusted composition이 독립 designation/fingerprint 대조와 status freshness를 책임져야 한다. artifact 자체의 root key, unknown status/principal fields 또는 fake fallback을 허용하지 않는다. receipt의 공개 필드도 current authorization evidence가 아니다.

## 아직 미구현인 권한 경계

서명 무결성 성공 뒤에도 current root/approval/assignment status·revoke/supersede/consume, journal high-water mark·history/seal, installation/Custodian possession, exact target principal/session/fresh WebAuthn, existing owner/current Workspace/history, DB guard CAS·one-time claim/binding/audit와 seal-first protocol을 모두 검증해야 bootstrap이 가능하다. target principal은 approval issuance가 아니라 claim에 bind되므로 이 verifier의 payload에 임의 추가할 수 없다.

Replay/concurrent integrity checks는 같은 역사적 receipt를 반환할 수 있다. 이는 double-consume winner=1 또는 consumed/revoked bootstrap replay deny 구현의 evidence가 아니다. DB rollback/external seal/restore 및 clock rollback 감지는 후속 persistence/ceremony의 Gate다. Workspace owner/Rights/Approval/Consent에 부작용은 없고 현재 production runtime는 비활성이다.

## Dependency 판정

ADR-076 merged develop에서 독립적으로 검증 가능한 최소 unit C를 선택했다. A는 journal/current-status/principal history 연결을, B는 principal lifecycle와 authentication provenance를 함께 요구한다. 새 authority를 도입하는 Decision은 없고 library/wire implementation details만 ADR-077에 기록한다. additive bootstrap migration과 실제 private-state provisioning은 이번 unit에 필요하지 않다. 기존 Phase/DoD 완료율은 그대로다.
