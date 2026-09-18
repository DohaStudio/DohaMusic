# ADR-077: Bootstrap Issuance Integrity Verifier Foundation

> 상태: [제안 — Foundation 구현·로컬 검증 PASS, Draft PR; 운영 비활성]
> 작성일·최종 수정일: 2026-09-18
> 기준 develop: `771f3b18aabb7890b3a84698a6a830877cbdc0be` (#162 squash merge)
> 관련 PR: 이 Foundation의 별도 develop 대상 Draft PR
> 관련 문서: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [Architecture](../03-architecture/bootstrap-issuance-integrity-verifier.md), [검증](../10-operations/bootstrap-issuance-integrity-verifier-validation.md)

## 배경과 후보

ADR-076은 #162로 merged됐고 root·Ed25519/JCS·issuance와 current status 분리·seal-first·최초 binding만의 범위가 authoritative하다. source에는 installation/principal/binding/journal registry가 없고 local operator concrete adapter도 unavailable이다. Rights persistence/Alembic `0037`은 bootstrap authority를 제공하지 않는다.

| 다음 unit | 의존성·비용 | 판정 |
|---|---|---|
| Installation/Bootstrap persistence | principal/binding history, 독립 deployment journal 기술·signed current status/proof receipt의 연결 필요 | 후속, 전체 ceremony를 이번 PR에 합치지 않음 |
| Principal registry/binding persistence | authentication provenance·lifecycle·history와 기존 owner 경계 필요 | 후속 |
| Crypto verifier | ADR-076의 기존 algorithm/domain/scope만으로 순수 issuance-integrity 검증 가능 | 가장 작은 독립 Foundation 선택 |
| 선행 authority Decision만 | C에는 새 actor/root/permission이 필요하지 않음 | 기술 구현 계약을 이 ADR에 한정 |

## 결정·대안·구현 계약

자체 Ed25519/JCS 구현 대신 [PyCA cryptography](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/) `50.0.1`과 [rfc8785.py](https://github.com/trailofbits/rfc8785.py) `0.1.4`를 사용한다. runtime direct dependencies를 exact pin하고 별도 private signing API/key generator는 만들지 않는다. 이 선택은 library 전체 security audit 또는 모든 환경 검증을 주장하지 않는다. 공식 배포 metadata의 cryptography Apache-2.0 OR BSD-3-Clause, rfc8785 Apache-2.0를 확인했다. 수동 sorted JSON은 UTF-16 sorting/number rendering과 달라 기각한다. 운영용 key storage/loader 선택은 여기서 하지 않는다.

`backend.bootstrap_authority.approval_verifier.verify_issuance_integrity()`는 bytes envelope + 독립 `PinnedRootVerifier` public expectations + `ExpectedApprovalScope` + aware UTC check time을 받아 immutable `ApprovalIntegrityReceipt`만 반환한다. caller가 dataclass를 만들었다는 사실은 pin ceremony/provenance/current status proof가 아니다. 입력 root는 향후 trusted composition이 제공해야 하며 artifact/request/application DB의 public key를 self-register할 경로는 없다.

V1 wire field 이름은 `schema`, `algorithm`, `approval_id`, `designation_id`, `deployment_owner_ref`, `designation_digest`, `root_key_id`, `installation_id`, `installation_proof_key_fingerprint`, `workspace_id`, `existing_owner_id`, `assignment_id`, `assignment_revision`, `custodian_ref`, `custodian_proof_key_fingerprint`, `scope`, `issued_at`, `not_before`, `expires_at`, `governance_provenance_digest`다. envelope는 `payload`/`signature` 두 field뿐이다. domain/schema·Ed25519·FIRST_OWNER_BINDING_ONLY 및 ASCII domain + NUL + JCS(payload)는 ADR-076 그대로다.

UUID는 lowercase hyphenated canonical string, public-key fingerprints와 provenance/payload digest는 `sha256:` + lowercase 64 hex, refs는 기존 opaque reference 규칙, assignment revision은 1..2^53-1의 int(bool/float 불가)다. fingerprint는 raw public-key bytes의 SHA-256이다. 시각은 초 단위 UTC `YYYY-MM-DDTHH:MM:SSZ`, `issued <= not_before < expires`, issuance 전체 window 최대 24시간, check time은 `issued <= checked_at` 및 `not_before <= checked_at < expires`다. expiry 경계는 deny다. clock rollback proof는 이 순수 함수가 제공하지 않는다.

UTF-8 strict, 16 KiB envelope cap, duplicate key/unknown field/nonfinite/float/wildcard/nested field/invalid Unicode/noncanonical signature encoding은 fail closed한다. signature는 64 bytes의 unpadded base64url canonical text다. safe error code만 반환하고 입력을 반사하거나 crypto unavailable을 성공/fake로 바꾸지 않는다. wire whitespace/object order는 JCS와 무관하므로 허용한다.

## Security invariants와 명시적 한계

Receipt는 **서명의 수학적 무결성과 check 시각 issuance window의 기록이지 bootstrap 허가가 아니다**. root/approval/assignment revoke·supersede·consume 상태, journal freshness/high-water mark, installation/Custodian fresh possession, target principal/session/WebAuthn, Workspace active/current owner/history, one-time consume·double-consume CAS·seal-first atomicity/recovery는 미구현이다. immutable issuance 검증을 반복하면 같은 receipt를 얻을 수 있으며 이를 consumed replay 허용으로 해석하면 안 된다. 향후 runtime는 current eligibility와 fresh proof 전체를 별도 protocol에서 확인해야 한다. 결과에 authorization/witness API를 두지 않고 runtime/API/Worker consumer를 연결하지 않는다.

원본 Workspace.owner_id/Approval/Consent/Grant/OUTPUT_READ를 변경하지 않는다. root/custodian을 Rights issuer나 owner로 승격하지 않는다. key+journal의 완전 rollback/clone 방어를 주장하지 않는다. 실제 사람 지정/governance approval/key provisioning/signing ceremony 및 실제 User/production DB/Provider 호출은 0이다. 테스트는 memory-only deterministic disposable key와 RFC 공개 vector만 사용한다.

## Schema·검증·장단점·재검토

이번 unit은 persistence/Session/Repository가 없어 migration/commit()/rollback() 0, Alembic single head `20260918_0037` 보존이다. ADR-076 전체 bootstrap의 SCHEMA_CHANGE_REQUIRED 판정은 그대로다. focused crypto·공식 vectors·negative contract·legacy authentication/workspace/Rights/migration/Completion 회귀 및 full backend/static 검증을 수행하고 [검증 보고서](../10-operations/bootstrap-issuance-integrity-verifier-validation.md)에 실제 수치를 기록한다. claim consume/concurrency/rollback 실험은 이번 pure crypto 검증으로 대체하지 않는다.

장점은 작은 side-effect-free boundary로 기존 trust semantics를 실행 가능하게 검증하는 것이다. 비용은 두 direct dependency와 strict wire 계약이며 운영 권한 chain은 아직 사용할 수 없다. 후속은 installation/approval/status/journal persistence contract와 principal/binding을 분리해 완결하는 작업이다. library upgrade, algorithm/wire 변경, 실제 trusted loader/runtime wiring은 vector·security review 및 별도 PR이 필요하다. 이번 새 PR은 Draft로 종료하며 Ready/merge하지 않는다.
