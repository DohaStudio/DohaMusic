# Deployment Verifier Current-Status / Lifecycle Contract

> 문서 상태: [정의/제안 — Contract Draft PR, 구현·운영 비활성]
> 최종 수정일: 2026-09-18
> 관련 문서: [ADR-078](../11-decisions/ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-076](../11-decisions/ADR-076-product-deployment-bootstrap-authority.md), [issuance verifier](bootstrap-issuance-integrity-verifier.md), [검증](../10-operations/deployment-verifier-current-status-validation.md)

Canonical 결정·wire·state·admission 계약은 ADR-078이다. #163 merged issuance verifier는 그대로 유지하며 current root/status authority로 확대하지 않는다.

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

Lock/CAS/state/wire는 설계 계약이며 현재 실행 구현·concurrency evidence가 아니다. 실제 store/OS mutex/private provenance provider·journal adapter·status writer/read witness가 없으므로 production는 unavailable이다. 이 문서로 기존 production auth를 활성화하거나 caller enum/UUID/receipt를 허가로 사용할 수 없다.

## 다음 unit과 비목표

현재 작업은 B를 구현하기 위한 최소 D Contract이며 implementation은 별도 Foundation PR이다. root/key/journal의 실제 provisioning·서명 ceremony를 수행하지 않고 현재 권한/법적 사람을 특정하지 않는다. app schema/Repository migration은 0이다. 다음에는 journal fact persistence/strict event validator/admission-currentness port boundary를 한 coherent unit으로 검증하며 claim/binding/WebAuthn/Recovery/Writer를 같이 구현하지 않는다.
