# ADR-076: Product/Deployment Bootstrap Authority

> 상태: [채택 — PR #162 merged, 운영 비활성]
> 작성일·최종 수정일: 2026-09-18
> 기준 develop: `6778ab22e69fbce54bc232815721b01413426dde`
> 관련 PR: [#162 merged](https://github.com/DohaStudio/DohaMusic/pull/162); #161/#160/#159 merged 보존, #130 OPEN/Draft 보존
> 관련 문서: [ADR-038](ADR-038-v1-reviewer-authentication-product-decision.md), [ADR-042](ADR-042-v1-local-operator-authentication-foundation.md), [ADR-075](ADR-075-dohavocal-production-rights-domain-decision.md), [Bootstrap architecture](../03-architecture/product-deployment-bootstrap-authority.md), [검증 보고서](../10-operations/product-deployment-bootstrap-authority-validation.md)

## 1. 배경·문제·설계 권한

기존 Local Operator는 사람의 인증 proof 경계이지 기존 Workspace의 최초 ownership claim 승인자가 아니다. owner UUID 입력, OS admin, 설치자, CLI 사용자, reviewer, WebAuthn 성공 또는 secret possession으로 최초 권한을 추론할 수 없다. 이번 사용자 요청은 기존 authority 재발견이 아니라 새로운 외부 Product/Deployment trust root의 설계·선택을 명시적으로 허용한다. 이 ADR은 그 결정 제안이며 실제 사람 지정, credential 발급 또는 운영 활성화 evidence가 아니다.

## 2. External root designation

V1 single-owner/self-hosted deployment의 Product/Deployment Owner는 외부 product/deployment governance에서 해당 installation 배포와 최초 trust assignment를 승인하도록 명시 지정한 human이다. 자동 자격은 없다. 외부 governance의 designation을 application trust chain의 root assertion으로 수용하며 상위 DohaMusic runtime role을 재귀적으로 요구하지 않는다.

Designation record는 immutable `designation_id`, stable opaque `deployment_owner_ref`, human 확인 및 명시 수락, 승인된 deployment 범위, 발효 시각, root public-key fingerprint/key ID, governance decision reference/digest를 보존한다. self-hosted V1에서는 배포 책임 human의 명시적 서면 self-designation과 수락을 외부 governance assertion으로 인정한다. 그 진정성은 trusted initialization ceremony에서 당사자와 designation/key fingerprint를 독립 채널로 대조하는 책임에 있으며 application DB가 증명하지 않는다. 실제 명단·서명·개인 정보는 이 저장소에 넣지 않는다.

Trusted initializer는 designation에 명시된 human 또는 그 record가 명시 위임한 deployment ceremony 수행자다. OS admin/설치 실행 권한은 필요할 수 있으나 designation을 대체하지 않는다. 이 외부 지정·대조 실패 시 installation은 UNENROLLED로 남고 bootstrap은 fail closed한다. Root가 할 수 있는 일은 installation 등록, exact Workspace bootstrap 승인, custodian 지정 및 성공 전 assignment 폐기/교체뿐이다. runtime super-admin, owner impersonation, Rights, recovery, transfer, Approval/Consent, Provider administration 권한은 없다.

## 3. 대안과 선택

| 후보 | 최초 신뢰·검증 | 전달·감사·비용 | 결정 |
|---|---|---|---|
| A. Owner signing key 단독 | 서명 무결성은 있지만 artifact가 스스로 제공한 key는 root proof 아님 | 작은 signing boundary, 별도 verifier provisioning 필요 | 단독 기각 |
| B. Initialization에서 local root verifier pin | 외부 designation/fingerprint 대조 후 root key를 별도 trust store에 pin | offline 검증, 작은 trust set, root 교체 절차 필요 | V1 anchor 선택 |
| C. Package에 signed manifest 포함 | 미리 pin한 key 없으면 package substitution 가능; exact installation은 사후 생성 | 배포 package 재발행·scope 관리 부담 | V1 기본 전달 방식 제외 |

B를 trust anchor로, A의 서명 artifact를 검증 대상으로 결합한다. 일반 CA/PKI, TOFU from request/DB, external IdP, runtime root upload API는 도입하지 않는다. Domain signature는 [RFC 8032 Ed25519](https://www.rfc-editor.org/rfc/rfc8032)를 선택한다. JSON payload는 [RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785) UTF-8 canonicalization을 선택하며 이는 WebAuthn credential algorithm의 선택이 아니다. 검증 library·OS store 구현은 후속 Gate다.

## 4. Approval artifact와 authenticity

Signed payload는 schema/domain `dohamusic/deployment-bootstrap-approval/v1`, approval ID, designation ID/reference/digest, root key ID, installation ID 및 installation public-proof-key fingerprint, exact Workspace ID, existing owner UUID, assignment ID/revision, designated custodian reference 및 custodian public-proof-key fingerprint, `FIRST_OWNER_BINDING_ONLY` scope, issued/not-before/expiry 시각, governance provenance digest를 가진다. UUID·시각은 canonical string, revision은 safe integer이며 wildcard/unknown field/duplicate JSON key는 거부한다.

Signature envelope는 payload와 Ed25519 signature(base64url unpadded)를 가진다. 서명 대상은 ASCII `DohaMusicDeploymentBootstrapApprovalV1` + NUL + JCS(payload)다. key ID/algorithm/scope도 signed payload에 속하고 algorithm은 고정한다. Artifact가 제공한 key 대신 pin한 root verifier를 사용한다. 승인 payload digest, 서명, designation 연결, 현재 root/approval/assignment status와 exact scope·expiry를 모두 검증해야 유효하다. Signed approval은 immutable issuance artifact이고 revoke/supersede/consume는 monotonic signed status journal로 보존한다. status revision을 issuance 파일 덮어쓰기로 판정하지 않는다. 서명 성공만으로 current eligibility가 보장되지 않는다.

Root human이 offline 승인 artifact를 지정 custodian에게 직접 전달한다. Custodian은 externally assigned random opaque `custodian_ref`와 별도 enrollment proof key로 식별한다. 미래 principal UUID나 username 대신 assignment에 pin한 public-key fingerprint의 fresh challenge possession + 외부 human designation 대조를 요구한다. 단순 artifact/secret 보유자는 custodian이 아니다. Private custodian key는 그 human의 private deployment store 경계에 남는다. Root/custodian/target이 같은 human일 수 있으나 세 authority 검증은 논리적으로 분리한다.

## 5. Key·verifier lifecycle

Root human은 trusted external deployment ceremony에서 암호학적 난수로 Ed25519 key를 생성하고 private key를 application DB/process/config/log/Git 밖의 접근 통제된 개인 signing store에 보관한다. 공개 verifier는 designation의 fingerprint와 독립 대조한 뒤 installation-local deployment trust store에 provision한다. application startup/request/approval 파일에서 자동 등록하지 않는다.

정상 rotation은 새 key·fingerprint를 외부 designation update로 승인하고 old/new key의 교차서명 transition과 monotonic trust-store revision으로 설치한다. old key는 신규 issuance 검증에서 비활성화하고 과거 public verifier와 provenance는 감사에 보존한다. 분실/compromise 시 old key 서명만으로 successor를 승인하지 않는다. 외부 governance의 재지정·독립 fingerprint 대조로 trust anchor를 갱신하고, 기존 미소비 approvals/claims를 모두 revoke한다. 상태 freshness를 증명하지 못하면 bootstrap 차단한다. 과거 서명의 수학적 유효성과 현재 key eligibility는 별개이며 compromised key의 이력은 tainted로 표시한다. 성공한 bootstrap fact는 key rotation/revocation으로 reset하지 않는다.

## 6. Installation identity·clone·restore boundary

Trusted initialization은 CSPRNG 기반 immutable random UUID `installation_id`와 별도 installation proof key를 생성한다. Root가 그 ID와 key fingerprint를 approval로 승인해야 ENROLLED다. hostname/path/OS username을 identity로 쓰지 않는다. proof private key는 application DB·backup 밖의 installation-local private deployment boundary에 남고 매 ceremony fresh challenge로 소유를 증명한다. 파일명/installation ID 문자열 일치만으로 통과하지 않는다.

재설치는 새 ID/key를 갖지만 기존 Workspace lineage의 historical binding/bootstrap 사실을 버릴 수 없다. imported DB/restore는 새 first-bootstrap 대상으로 자동 등록하지 않는다. V1는 외부 root가 관리하는 deployment journal을 application DB와 독립 backup/lifecycle로 보존하고 Workspace bootstrap 역사, root/status revision high-water mark, installation lineage를 확인한다. 다른 installation의 DB/artifact/secret 복사는 installation proof 및 exact scope에서 deny한다. 외부 journal unavailable/누락/restore lineage 불명/clock rollback은 deny한다.

V1 security boundary는 trusted local deployment process와 private store, 외부 journal이 온전한 환경이다. 모든 private key와 외부 journal까지 동시에 복제/rollback하거나 malicious root/local privileged compromise가 있으면 소프트웨어만으로 완전한 anti-rollback/anti-clone을 보장하지 않는다. 이는 out-of-bound compromise이며 재-bootstrap을 허용하는 fallback이 아니다. Restore는 외부 journal과 대조 후 sealed/uncertain scope를 보존하고 인증 binding 사용 자체의 복구는 별도 Recovery Decision을 기다린다. hardware monotonic counter/remote service는 V1 필수가 아니지만 이 경계를 더 강하게 요구하면 새 ADR이 필요하다.

## 7. Scoped assignment·claim·eligibility

검증된 approval로만 custodian assignment를 생성한다. key는 installation + exact Workspace + existing owner UUID이고 wildcard는 없다. Custodian은 fresh proof 후 exact internal target principal identity와 함께 claim을 승인한다. 아직 principal registry는 미구현이나 future adapter contract는 immutable internal principal ID, provider provenance, human assurance, fresh session/context와 lifecycle eligibility를 증명해야 한다. credential 재등록만으로 principal continuity를 추정하지 않는다.

Claim은 random ID, CSPRNG 256-bit secret/challenge, SHA-256 verifier, approval/assignment IDs 및 revisions, installation/key fingerprint, Workspace/owner, target principal, session challenge digest, issued/expiry 시각을 bind한다. raw secret은 지정 custodian의 private local console에 한 번 전달하고 DB/로그/Git에 보관하지 않는다. expiry는 발급 후 최대 15분이며 approval/assignment 만료보다 늦을 수 없다. approval/assignment 승인 window는 최대 24시간으로 제한한다. 이는 새 V1 보안 정책값이지 측정한 WebAuthn TTL이 아니다. fresh authentication의 production TTL은 ADR-042 후속 adapter Gate를 따른다.

최초 claim 발급/소비는 active non-deleted Workspace, existing owner 일치, current binding 없음, historical successful binding 없음, successful-bootstrap/sealed journal fact 없음, approval/assignment current 및 exact scope 일치를 요구한다. credential만으로 또는 WebAuthn만으로 승인하지 않는다. bootstrap은 Workspace.owner_id를 바꾸지 않는다.

Claim 상태는 ISSUED → CONSUMED/REVOKED/EXPIRED이며 terminal reset이 없다. approval/assignment도 ACTIVE → CONSUMED/REVOKED/SUPERSEDED/EXPIRED만 허용한다. 바뀐 assignment의 모든 claims는 deny한다. Root만 bootstrap 전에 revoke/replace 가능하고 새 revision·artifact를 요구한다. 성공 후 새 approval/root key/custodian으로도 해당 Workspace를 재-bootstrap할 수 없다.

## 8. One-time extinguishment·transaction·crash

모든 deployment status/rotation/consume writer는 동일 전역 순서로 deployment ceremony mutex → application DB bootstrap/binding guard → external journal CAS에 참여한다. root-key status 변경처럼 여러 scope를 건드리면 먼저 정렬된 해당 ceremony mutex들을 확보한다. deployment store와 DB의 역순 lock은 금지하며 process-memory mutex만으로 재시작·다중 process 안전을 주장하지 않는다. mutex는 root/custodian/installation 상태를 fresh 검증하기 전부터 DB commit/rollback까지 유지한다. 독립 stable per-Workspace bootstrap/binding guard의 실제 conditional UPDATE + semantic revision + unique first-binding invariant로 Claim A/B를 직렬화한다. SQLite SELECT FOR UPDATE/reader-only 검사/Rights guard 재사용은 불가하다. root status/assignment/custodian eligibility와 claim digest, installation proof, fresh target human authentication을 commit 전에 fresh 검증하고 관련 변경 writer도 동일 protocol에 참여한다. adapter/library 검증 전 운영 활성화 금지다.

External deployment journal과 application DB의 원자성을 가정하지 않는다. V1는 안전성을 위해 fail-closed seal-first protocol을 선택한다. terminal fresh-proof 검증 및 DB guard 확보 후 외부 journal에서 Workspace lineage를 CAS로 SEALED하고 exact attempt/claim/target/digest를 durable 기록한다. seal 성공 후 caller-owned DB transaction에서 claim consumed + immutable first binding/history + successful-bootstrap audit를 한 번 commit한다. 외부 journal status 변경/rotation writer도 같은 deployment ceremony serialization에 참여한다. DB commit 후 외부 journal은 exact binding receipt를 SUCCESS로 표시할 수 있으나 SEALED 자체가 새 bootstrap을 영구 차단한다.

DB 오류/외부 journal 응답 유실/SEALED 뒤 crash는 SEALED 또는 UNCERTAIN으로 차단하며 자동 unseal/새 claim/새 target retry는 없다. DB rollback으로 external seal이 사라진다고 주장하지 않는다. Root는 bootstrap 전에 아직 seal 없는 assignment만 교체할 수 있다. 이 선택은 실패 시 가용성을 포기하며 reconciliation은 기존 exact DB 성공 사실을 확인해 journal 감사 표시를 보완하는 것만 가능하다. 새로운 binding 생성/identity 복구는 별도 Recovery Decision 전 금지다. DB만 restore되어도 외부 seal 때문에 재-bootstrap은 deny한다. 원자적 one-time 증명 및 crash/rollback 실험은 후속 구현 필수 Gate다.

## 9. Rights·history·non-goals

최초 결과는 immutable internal human principal ↔ existing owner identity binding과 claim/approval/assignment/installation audit 연결뿐이다. 미래 Grant는 issuer principal 및 발급 당시 binding identity/revision을 추적해야 하며 root/custodian을 issuer로 저장하지 않는다. 이 ADR은 기존 issuer_id UUID의 의미를 migration하거나 legacy 이력을 backfill하지 않는다.

ADR-075의 Grant authenticated current owner, Revoke current owner 또는 original authenticated issuer semantics를 그대로 보존한다. 성공 binding은 한 prerequisite일 뿐 별도 current-owner, principal eligibility, rights/evidence serialization과 verified Evidence 없이 발급할 수 없다. Grant/OUTPUT_READ/Revoke/Supersede, Approval/Consent 승격, Workspace owner 변경, selection, Provider/acquisition 책임 변화는 없다. Recovery, transfer, historical identity reactivation, Evidence validation, Writer/Adapter/Runtime는 non-goal이다.

## 10. Schema·migration·rollout·판정

Domain Decision 뒤 현재 source를 평가하면 installation/verifier registry, approval/status, custodian assignment, claim/guard/consumed fact, principal registry/binding history 및 외부 deployment journal facts가 없다. 최종 분류는 SCHEMA_CHANGE_REQUIRED / PRODUCT_DEPLOYMENT_BOOTSTRAP_SCHEMA_REQUIRED_BUT_RESOLVED다. 논리 facts 결정이며 table/ORM/외부 store technology를 구현한 것이 아니다. 기존 Rights tables/Alembic 0037은 보존하고 migration/production/test/API/Frontend/Worker 변경 0이다.

DEFINED: external root designation + 검증 모델 + scope/소멸/trust chain.

후속 [ADR-077](ADR-077-bootstrap-issuance-integrity-verifier-foundation.md)은 issuance-integrity crypto verifier만 별도 Foundation Draft PR로 구현·검증 중이다. 이는 current eligibility/권한을 증명하지 않는다. NOT IMPLEMENTED: trusted verifier provisioning/key storage, current root/approval/assignment status, installation/approval/custodian/claim persistence, 외부 journal/seal protocol, WebAuthn adapter, principal registry/binding, recovery, transfer, Rights Writer/Production Adapter/Evidence Authority.

이 docs-only Decision은 #162 Final Validation/squash merge로 authoritative develop에 들어왔다. 다음 최소 독립 unit은 ADR-077 verifier이며, Installation/Bootstrap Persistence Foundation은 별도 후속이다. 새 Foundation PR의 Ready/merge는 이번 요청 범위 밖이다. 운영은 root provisioning, actual target DB locks, signature/JCS official vectors, key rotation/compromise, expired/revoked/wrong scope/principal, double consume, seal crash/old DB restore/clone, Fake fallback 금지 및 private-state boundary tests 전 차단한다. Existing user/production DB·실제 Provider 접근은 하지 않는다.

## 11. 영향·장단점·재검토

장점은 외부 root로 recursion을 닫고 exact first-bootstrap에서 권한을 소멸시키며 original issuer continuity의 연결을 정의하는 것이다. 비용은 외부 journal/키·ceremony 운영과 seal-first 실패 시 복구 전까지의 비가용성이다. 실제 배포 compromise/remote multi-user/복수 root/hardware anti-rollback/recovery·transfer 요구가 생기면 별도 ADR과 security review가 필요하다. ADR-038/042/075의 기존 의미·source를 변경하지 않으며 #161/#160/#159/#130 source branch와 PR 상태를 보존한다.
