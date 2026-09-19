# ADR-090: Original Confirmation Canonical Payload Boundary Foundation

> 상태: [채택 — #177 merged; 운영 비활성]
> 작성일·최종 수정일: 2026-09-19
> 기준 develop: `034ca95a9173bf3a6f2950df93351c001214373c` (#176 squash merge)
> 관련 PR: [#177 merged](https://github.com/DohaStudio/DohaMusic/pull/177); 다음 [ADR-091 verifier reuse와 live lineage](ADR-091-confirmation-verifier-reuse-live-lineage-foundation.md)
> 관련: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-087](ADR-087-custody-policy-provisioning-initializer-provenance-contract.md), [ADR-089](ADR-089-original-confirmation-raw-snapshot-foundation.md), [검증](../10-operations/original-confirmation-canonical-payload-validation.md)

## 결정과 범위

다음 미증명 사실 중 external trust root 없이 독립 검증 가능한 가장 작은 후보 C를 선택한다. `confirmation_payload`는 held raw bytes가 exact JCS V1 payload이고 독립적으로 주입된 installation/action/policy/designation/initializer/verifier/replay 기대값과 일치하는지만 검증한다. 이는 향후 authenticity verifier가 서명할 canonical message의 입력 경계이며 서명 검증 자체는 아니다.

V1 schema는 `dohamusic/original-initializer-confirmation/v1`, algorithm 표시는 `Ed25519`, scope는 `INSTALLATION_POLICY_PROVISIONING_ONLY`다. payload는 schema/algorithm/scope와 confirmation ID, original reference, initializer reference, installation ID와 proof-key fingerprint, action ID, policy digest, designation digest, verifier key ID/fingerprint, replay ID의 정확한 14개 string field만 가진다. UUID/digest/reference를 기존 strict validator로 검증하고 unknown/missing/duplicate/nested/null/bool/int/float/nonfinite/invalid UTF-8/BOM/비canonical bytes/1 MiB 초과를 거절한다.

`_OriginalConfirmationSnapshots._require_canonical_payload()`는 원래 registry handle, held pin/designation/custody/lease/transaction, fresh strict action/history와 same-handle bytes를 다시 확인한 뒤 parser를 호출한다. Payload identity는 기존 action confirmation, policy installation/fingerprint, pin의 designation digest와 각각 일치해야 한다. 어느 mismatch나 예외도 original handle/lease를 영구 abandon하며 복원 후 재사용하지 못한다.

반환 `ConfirmationPayloadBoundary`는 canonical byte digest와 public identifiers만 가진 immutable comparison result다. `authenticated`, `current`, witness, admission, authorization, signature receipt API가 없다. Payload 안의 algorithm/verifier fingerprint는 self-asserted signed-input 후보일 뿐 verifier provisioning, key eligibility, signature validity, human acceptance 또는 current lineage를 증명하지 않는다. Snapshot/digest/ACL/public history/comparison도 authority가 아니다.

## 보안 경계와 후속

Parser는 private key를 생성·로드하지 않고 실제 confirmation을 발급하지 않는다. Deterministic disposable public strings와 disposable Windows files만 사용한다. 실제 authenticity에는 ADR-076의 외부 designation과 독립 provisioned verifier source, signature envelope/domain separation, verifier rotation/revocation currentness가 추가로 필요하다. Signature valid도 current lineage나 admission을 뜻하지 않는다.

이번 변경은 schema/migration/Repository transaction/production port/runtime/API/Frontend가 0이며 Alembic `20260918_0037` single head를 유지한다. 다음 dependency는 독립 verifier provisioning authority를 재사용할 수 있는지의 Contract Resolution 또는 authoritative live current-lineage reader다. 새로운 trust root나 실제 key ceremony가 필요하면 사용자 Decision 전 구현하지 않는다.
