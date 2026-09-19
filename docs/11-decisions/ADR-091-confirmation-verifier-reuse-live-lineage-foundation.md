# ADR-091: Confirmation Verifier Reuse / Live Current-Lineage Foundation

> 상태: [제안 — 구현 및 검증 완료; Foundation Draft, 운영 비활성]
> 작성일·최종 수정일: 2026-09-19
> 기준 develop: `edab5d461e8f2be393fc1e1c7d0bc772d9bf2de5` (#177 squash merge)
> 관련: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-077](ADR-077-bootstrap-issuance-integrity-verifier-foundation.md), [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-080](ADR-080-private-admission-currentness-handoff-contract.md), [ADR-087](ADR-087-custody-policy-provisioning-initializer-provenance-contract.md), [ADR-090](ADR-090-original-confirmation-canonical-payload-foundation.md), [검증](../10-operations/live-current-lineage-reader-validation.md)

## Verifier reuse audit와 판정

판정은 **C. VERIFIER_INFRASTRUCTURE_ONLY_REUSE**다. PyCA Ed25519, RFC 8785 JCS, strict identifier/base64url parsing과 safe error 관례는 재사용 가능하지만 동일 algorithm/library/fingerprint는 동일 authority가 아니다.

| 비교 | ADR-076/077 deployment approval | Original confirmation | 판정 |
|---|---|---|---|
| trust root·owner | 외부 Product/Deployment designation의 pinned root | 실제 confirmation issuer/initializer authority는 미지정 | authority 재사용 불가 |
| key purpose·scope | `FIRST_OWNER_BINDING_ONLY` approval issuance | installation policy action의 original human/initializer confirmation | 목적 불일치 |
| signed domain·payload | `DohaMusicDeploymentBootstrapApprovalV1\0`, approval envelope | 별도 confirmation domain/signature envelope 미정 | cross-domain replay 금지 |
| installation binding | Workspace/owner/assignment/custodian까지 bind | installation/action/policy/designation/initializer/replay bind 필요 | 일부 field 유사성만 존재 |
| lifecycle | root rotation/revoke/compromise journal 계약 | confirmation verifier eligibility·issuer delegation lifecycle 미정 | status 공유 불가 |
| audit·replay | approval issuance와 future consume/seal 분리 | confirmation identity와 action lineage/currentness 분리 | receipt 상호 대체 금지 |

ADR-076 root human과 trusted initializer는 같을 수도 있지만 initializer는 designation이 위임한 별도 수행자일 수도 있다. 기존 root key/fingerprint를 payload가 가리킨다는 사실만으로 issuer 권한을 만들 수 없다. 기존 approval verifier를 다른 domain에 호출하거나 approval receipt를 confirmation authenticity receipt로 바꾸지 않는다. 같은 physical key를 미래 외부 governance가 별도 purpose로 지정할 가능성은 열어 두되 현재 source가 추측하지 않는다. 새 trust root/실제 key/credential/signing은 만들지 않는다.

Authenticity를 Fake로 채우는 대신 dependency 선택은 **E. LIVE_CURRENT_LINEAGE_FIRST**다. 이는 C audit을 뒤집지 않는다. Current-lineage transport와 stale-evidence 방어를 독립 검증하며 어느 결과도 admission으로 승격하지 않는다.

## Live current-lineage 최소 Foundation

`live_lineage_reader`는 fixed `policy-lineage-current-v1.json`을 별도 expected native identity/owner/protected DACL의 held handle로 읽는다. Record는 schema, journal identity/revision/trust revision/head digest, installation/anchor/source, full lineage digest/head action digest, confirmation/original digest/initializer, policy/designation digest, semantic revision/predecessor/status의 exact 18 fields다. JCS exact bytes, 1 MiB cap, strict types, UUID/revision/digest, duplicate/unknown/nested/bool/float/noncanonical 거부를 적용한다.

Reader는 기존 live pin/designation/custody/lease/transaction의 raw confirmation handle과 canonical payload를 먼저 재검증한다. 이어 별도 lineage file을 same-handle로 읽고 기존 private pin의 exact journal head와 designation digest, complete ACTIVE lineage와 action digest를 비교한다. Handoff 전후 confirmation chain과 lineage bytes를 다시 읽는다. 파일/record/journal head/action/predecessor/terminal/transaction/lease mismatch 또는 예외가 관측되면 lineage handle과 parent confirmation handle을 abandon해 값 복원 뒤 재사용을 거절한다.

반환값은 provider-internal opaque handle뿐이며 CurrentnessWitness/ProvisioningWitness/AdmissionWitness가 아니다. 이 Foundation은 private store provisioning/authenticated writer, external journal과 lineage file의 atomic update, cross-process writer ceremony, crash reconciliation, source authenticity, confirmation signature, production port를 구현하지 않는다. `UnavailableCurrentnessPorts`가 계속 유일한 production composition이다. Actual trusted adapter가 independent provisioning과 journal reader를 제공하기 전 운영은 unconditional unavailable다.

## 영향·검증·후속

App schema/Alembic/Repository transaction/API/Frontend/Worker/Rights는 변경하지 않는다. External journal schema v1도 변경하지 않고 app Alembic `20260918_0037` single head를 유지한다. Disposable public facts와 Windows temp files만 사용하며 실제 private key/credential/governance ceremony/User DB/Provider 접근은 0이다.

다음 dependency는 confirmation issuer/verifier purpose의 외부 authority Decision 또는 private lineage writer/provisioning + external journal atomic handoff다. 실제 authenticity를 활성화하려면 별도 confirmation domain, signer purpose, independently provisioned verifier와 rotation/revocation/compromise 의미를 사용자 승인으로 확정해야 한다. 새 PR은 Draft까지만 생성한다.
