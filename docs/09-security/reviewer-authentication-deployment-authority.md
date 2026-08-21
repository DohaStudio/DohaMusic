# Reviewer Authentication과 배포 권위

> 문서 역할: DohaMusic 제품 identity와 DohaAudio reviewer authentication 연결의 Canonical Authority
> 문서 상태: [V1 product authority 승인 / 구현 미착수]
> 최종 수정일: 2026-08-21
> 관련 문서: [Provider 책임 경계](../03-architecture/repository-provider-boundaries.md), [Provider API 계약](../06-api/provider-api-contract.md), [배포 아키텍처](../03-architecture/deployment-architecture.md), [ADR-037](../11-decisions/ADR-037-reviewer-authentication-deployment-authority.md), [ADR-038](../11-decisions/ADR-038-v1-reviewer-authentication-product-decision.md)

## 1. 권위 기준

ADR-037과 PR #109의 initial CASE B는 product-owner 결정 전 fail-closed authority다. 이후 product owner가 V1 요구를 명시적으로 승인했으므로 다음 값이 현재 V1 authority다. 이 결정은 authentication 구현이나 DohaAudio Runtime activation을 승인하지 않는다.

```yaml
CURRENT_DEPLOYMENT_TOPOLOGY: LOCAL_ONLY
V1_PRODUCTION_DEPLOYMENT_TOPOLOGY: LOCAL_ONLY
FUTURE_DEPLOYMENT_TOPOLOGY: UNRESOLVED
CURRENT_PRODUCT_AUTH_MODEL: NO_PRODUCT_LOGIN
V1_PRODUCT_LOGIN_REQUIRED: false
V1_REVIEWER_AUTHENTICATION_REQUIRED: true
PRODUCT_IDENTITY_OWNER: DohaMusic
REVIEWER_IDENTITY_OWNER: DohaMusic
REVIEWER_AUTHORITY_OWNER: DohaAudio
SERVICE_IDENTITY_OWNER: DohaMusic
DIRECT_PROVIDER_USER_ACCESS: false
V1_REVIEWER_POPULATION: SINGLE_OWNER_OPERATOR
V1_REVIEWER_INTERACTION: DOHAMUSIC_LOCAL_GOVERNANCE_UI
UPSTREAM_HUMAN_IDENTITY_MODEL: LOCAL_AUTHENTICATED_OPERATOR
LOCAL_OPERATOR_PROOF_MODEL: OS_BOUND_LOCAL_OPERATOR_CREDENTIAL
V1_EXTERNAL_AUTH_NETWORK_REQUIRED: false
V1_REVIEWER_AUTH_OFFLINE_CAPABLE: true
V1_REVIEWER_MFA_REQUIRED: false
SERVICE_AUTH_DIRECTION: LOCAL_INTERNAL_SERVICE_IDENTITY
REVIEWER_TRUST_DIRECTION: DELEGATED_DOHAMUSIC_IDENTITY
DOHAAUDIO_AUTH_PROVIDER_MODEL: DOHAMUSIC_DELEGATED_ASSERTION
REVIEWER_ASSERTION_ISSUER_OWNER: DohaMusic
REVIEWER_ASSERTION_AUDIENCE: DohaAudio
REVIEWER_ASSERTION_LIFETIME: SHORT_LIVED
REVIEWER_ASSERTION_REPLAY_RESISTANCE: REQUIRED
PRIVATE_IDENTITY_STORE_REQUIREMENT: LOCAL_PERSISTENT_PRIVATE_STORE
SELECTED_AUTHENTICATION_PROVIDER_MODEL: DOHAMUSIC_DELEGATED_ASSERTION
SELECTED_EXTERNAL_IDENTITY_PROVIDER: null
AUTH_REQUIREMENTS_RESOLVED: true
AUTH_PROVIDER_SELECTION_READY: true
```

`AUTH_REQUIREMENTS_RESOLVED=true`는 DohaAudio Provider model 선택을 막던 product requirement가 해결됐다는 뜻이다. `AUTH_PROVIDER_SELECTION_READY=true`는 DohaAudio가 후속 PR에서 선택할 adapter model이 명확하다는 뜻이며, DohaAudio의 selected/configured/operational 상태를 변경하지 않는다.

## 2. CURRENT, V1 production과 FUTURE

### CURRENT

- DohaMusic은 로컬 단일 사용자 Responsive Studio MVP다.
- Web, FastAPI, Worker, SQLite와 local Storage를 한 개발 머신에 둘 수 있다.
- account/user table, login UI·API, session/JWT, OAuth/OIDC와 authorization role 구현이 없다.
- DohaAudio Runtime transport, Provider service authentication과 human semantic review는 연결되지 않았다.
- `NO_PRODUCT_LOGIN`은 localhost, OS username 또는 process owner를 authenticated human으로 인정한다는 뜻이 아니다.

### V1 production

- 배치는 사용자 소유 machine의 trusted local environment로 제한한다.
- 일반 product account/login subsystem은 만들지 않지만 semantic governance action에는 별도 reviewer authentication이 필요하다.
- 명시적인 single owner/operator reviewer가 DohaMusic local governance UI에서 review를 시작한다.
- Reviewer proof는 DohaMusic가 소유하는 OS-bound local operator credential boundary를 사용해야 한다.
- External IdP network는 요구하지 않고 reviewer path는 offline-capable해야 한다.
- V1 MFA는 필수가 아니지만 stable identity, freshness, expiry, replay resistance와 fail-closed verification은 필수다.

### FUTURE

Remote, hybrid 또는 multi-user topology는 미확정이다. V1 local-only와 MFA 미필수 결정은 future topology를 영구 고정하지 않는다. Remote privileged governance를 도입할 때 account/login, IdP, network outage, MFA·recovery·audit requirement를 새 ADR로 재결정한다.

## 3. 사람 identity와 semantic authority

| 역할 | Owner | V1 상태 |
|---|---|---|
| Product user/account identity | DohaMusic | 일반 product login 불필요, subsystem 없음 |
| Human reviewer identity proof | DohaMusic | `LOCAL_AUTHENTICATED_OPERATOR`·OS-bound proof model 승인, 구현 없음 |
| ReviewerAuthority와 semantic scope | DohaAudio | Provider domain governance, 실제 부여 0 |
| DohaMusic Orchestrator service identity | DohaMusic | `LOCAL_INTERNAL_SERVICE_IDENTITY`, concrete protocol 미선정 |

`SINGLE_OWNER_OPERATOR`는 V1 semantic governance를 수행하는 명시적 reviewer role이다. 모든 product user, 모든 local OS user, process owner 또는 DohaMusic caller가 reviewer라는 뜻이 아니다. Local governance UI는 review initiation surface이며 UI 접근만으로 identity proof, ReviewerAuthority 또는 semantic approval을 만들지 않는다.

DohaMusic가 reviewer identity verification을 소유해도 caller-supplied reviewer ID를 DohaAudio에 전달하지 않는다. DohaAudio의 `verified context → private mapping → opaque reviewer ID → ReviewerAuthority` 경계를 유지한다.

## 4. Upstream proof와 delegated trust

V1 목표 흐름은 다음과 같다.

```text
Single owner/operator
  → DohaMusic OS-bound local operator proof [adapter 미구현]
  → DohaMusic local governance UI [미구현]
  → short-lived reviewer assertion [protocol 미구현]
  → DohaAudio private identity mapping [store 미구현]
  → DohaAudio ReviewerAuthority [실제 부여 0]
```

`LOCAL_OPERATOR_PROOF_MODEL=OS_BOUND_LOCAL_OPERATOR_CREDENTIAL`은 다음 security property를 결정한다.

- credential은 local operator context와 결합한다.
- caller-supplied username과 복제 가능한 public identifier를 proof로 신뢰하지 않는다.
- DohaMusic가 verification boundary를 소유한다.
- concrete Windows Credential Manager, DPAPI, Windows Hello, OS access-token API, keychain 또는 application unlock 기술은 후속 구현에서 선택한다.

DohaAudio가 external IdP 또는 product user를 직접 인증하는 V1 login surface는 지원하지 않는다. DohaAudio 관점의 selected authentication provider model은 `DOHAMUSIC_DELEGATED_ASSERTION`이다. 이는 OIDC·GitHub 같은 external vendor 선택이 아니다.

## 5. Assertion과 service identity

Reviewer assertion은 최소 다음을 요구한다.

- issuer owner는 DohaMusic이고 exact audience는 DohaAudio다.
- assertion은 short-lived이며 concrete TTL은 후속 계약에서 정한다.
- issued-at/freshness, expiry와 replay resistance를 검증한다.
- service principal과 human reviewer principal을 별도 claim·credential로 구분한다.
- private subject를 public semantic record에 저장하지 않는다.
- verified identity는 private mapping을 거쳐 opaque reviewer ID로 변환한다.
- ReviewerAuthority exact scope를 별도로 확인한다.
- invalid, stale, expired, replayed, unknown mapping과 미확정 config는 fail-closed한다.

JWT, PASETO, custom HMAC token, mTLS claim, RSA, ECDSA, EdDSA와 key storage·rotation 방식은 선택하지 않았다. Assertion 인증 성공은 ReviewerAuthority 또는 semantic approval을 자동 부여하지 않는다.

DohaMusic→DohaAudio service authentication 방향은 `LOCAL_INTERNAL_SERVICE_IDENTITY`다. Concrete protocol과 credential rotation은 후속 구현 사항이다. Service credential과 reviewer assertion credential을 동일하게 사용하지 않으며 service 인증만으로 reviewer mapping이나 approval을 만들 수 없다.

## 6. Provider 후보 최종 판정

| 후보 | V1 판정 | 근거 |
|---|---|---|
| Local Authenticated Operator | upstream model 선택 | `LOCAL_AUTHENTICATED_OPERATOR`와 OS-bound proof model 승인, concrete adapter 미구현 |
| Generic OIDC | 선택 안 함 | V1은 external auth network가 필요 없고 local single-owner·offline-capable scope다. Future remote에서 재검토한다. |
| GitHub Identity | 선택 안 함 | source-control identity와 semantic reviewer identity를 연결하지 않는다. |
| Self-managed product account | 선택 안 함 | V1 general product login은 필요하지 않다. |
| Trusted proxy | 선택 안 함 | V1 proof model이 아니며 header trust boundary를 추가하지 않는다. |
| mTLS | reviewer model로 선택 안 함 | service identity 후보일 수 있지만 human reviewer proof를 해결하지 않는다. |
| DohaMusic delegated assertion | downstream model 선택 | DohaAudio selected provider model이며 issuer/audience와 최소 assurance가 확정됐다. |

## 7. Network, assurance와 장애 정책

- V1 external authentication network requirement는 `false`다. Same-machine internal transport와 external IdP dependency를 구분한다.
- Reviewer authentication과 delegated review path는 external IdP outage 없이 offline-capable해야 한다.
- V1 MFA requirement는 `false`이며 future remote privileged governance에서 재결정한다.
- 최소 assurance는 stable authenticated operator identity, proof freshness, assertion exact issuer/audience, expiry와 replay resistance다.
- Proof·assertion verification 또는 private mapping이 unavailable하거나 실패하면 새 semantic approval을 만들지 않는다.

## 8. Lifecycle, recovery와 revocation

| 대상 | Owner |
|---|---|
| V1 local operator proof provisioning·disable·revoke | DohaMusic local operator authentication boundary |
| Concrete OS credential recovery | 구현 기술과 함께 후속 결정, DohaMusic boundary 밖으로 책임을 넘기지 않음 |
| Service credential 발급·rotation·revocation | DohaMusic deployment/composition owner |
| Delegated assertion signing material lifecycle | DohaMusic, concrete key mechanism 미선정 |
| Private identity mapping revoke/supersede | DohaAudio |
| ReviewerAuthority grant·revoke | DohaAudio |
| 기존 semantic decision invalidation·재검토 | DohaAudio governance policy |

Identity revocation은 mapping·ReviewerAuthority·semantic decision을 자동 삭제하지 않는다. 각 lineage와 감사 기록을 보존하고 명시적으로 revoke 또는 re-review한다. Recovery implementation 미선정은 product requirement resolution을 되돌리지 않는다.

## 9. Secret과 private identity store

DohaMusic은 operator proof material, delegated assertion signing material과 service identity credential을 소유한다. DohaAudio는 assertion verification material과 private identity mapping store를 소유한다. Human reviewer assertion credential과 service credential은 분리한다. 실제 secret·key·credential은 0이고 secret manager와 key lifecycle 구현은 미선정이다.

V1 private mapping·revocation lineage는 restart 후에도 보존되는 `LOCAL_PERSISTENT_PRIVATE_STORE`가 필요하고 DohaAudio private composition boundary가 소유한다. SQLite, OS secure store 또는 metadata SQLite+sensitive reference secure store hybrid 중 concrete technology는 후속 DohaAudio PR에서 선택한다.

- public DB 분리: provider/private subject를 public semantic API와 ReviewerAuthority record에서 숨긴다.
- 저장 금지: raw credential, password, assertion과 semantic approval content를 저장하지 않는다.
- lineage: mapping version과 created/revoked/superseded lineage를 보존한다.
- threat: local process compromise, filesystem·backup theft, process/log leakage, forged local operator proof, caller identity spoofing, delegated assertion replay, service principal reviewer impersonation과 mapping tampering을 포함한다.
- at-rest/backup: concrete technology가 제공하는 access control·encryption과 protected backup·restore를 구현 전 검증한다.

## 10. 남은 implementation 결정

다음은 product-provider selection blocker가 아니지만 activation 전 반드시 결정·구현해야 한다.

1. OS-bound local operator credential의 concrete OS API, provisioning·recovery와 revoke adapter
2. Local internal service authentication protocol과 credential rotation
3. Assertion format, signing algorithm, exact TTL, clock policy, nonce/jti 또는 one-time replay contract
4. Signing·verification key storage, rotation, revocation과 fail-closed resolver
5. Local persistent private store technology, migration, backup·restore와 tamper response
6. Local governance UI의 explicit reviewer action, audit와 safe error UX

## 11. Fail-closed Runtime 상태

DohaMusic product authority는 해결됐지만 이번 결정은 DohaAudio Runtime을 변경하지 않는다.

```yaml
AUTH_PROVIDER_SELECTED: false
AUTH_PROVIDER_CONFIGURED: false
AUTH_PROVIDER_OPERATIONAL: false
PRIVATE_IDENTITY_STORE_OPERATIONAL: false
REAL_IDENTITY_MAPPING_COUNT: 0
REAL_REVIEWER_AUTHORITY_COUNT: 0
REAL_HUMAN_APPROVAL_COUNT: 0
PRODUCTION_HUMAN_REVIEW: disabled
```

Rights, Dataset integrity, split, model, config, environment, preflight, approval과 Training Gate도 모두 기존 fail-closed 상태를 유지한다.
