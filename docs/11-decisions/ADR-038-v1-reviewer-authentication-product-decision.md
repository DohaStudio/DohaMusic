# ADR-038 — V1 Reviewer Authentication Product Decision

> 상태: 승인 — V1 product authority, 구현 미착수
> 작성일: 2026-08-21
> 최종 수정일: 2026-08-21
> 관련 기능: DohaMusic V1 product identity, DohaAudio human reviewer authentication
> 관련 문서: [Authentication Authority](../09-security/reviewer-authentication-deployment-authority.md), [ADR-037](ADR-037-reviewer-authentication-deployment-authority.md), [Provider API 계약](../06-api/provider-api-contract.md), [배포 아키텍처](../03-architecture/deployment-architecture.md), [Phase 9 DoD](../DoD/Phase-09.md)

## 배경

ADR-037은 CURRENT local single-user/no-product-login, DohaMusic product·service identity, DohaAudio ReviewerAuthority, direct Provider user access 금지와 delegated trust direction을 확정했다. Production topology, reviewer population·interaction과 upstream human proof는 product-owner authority를 기다리며 보류했다.

PR #109의 initial evidence-only assessment는 repository가 CURRENT MVP만 증명하고 V1 product requirement를 스스로 만들 수 없으므로 CASE B와 fail-closed no-selection을 기록했다. 이 판정은 당시 올바르며 삭제하거나 오류로 취급하지 않는다.

그 이후 product owner가 V1 topology, reviewer population·interaction, identity ownership, upstream proof model, network/offline·MFA, service direction, delegated assertion과 private store requirement를 명시적으로 승인했다. 이 새로운 authority가 initial CASE B의 7개 product-owner blocker를 해결한다.

## Explicit product-owner decision

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

V1 local-only는 future remote·hybrid·multi-user를 금지하지 않는다. V1 일반 product login이 불필요하다는 결정은 privileged semantic governance의 reviewer authentication이 불필요하다는 뜻이 아니다.

## Reviewer와 interaction

V1 semantic reviewer는 명시적인 `SINGLE_OWNER_OPERATOR` 한 명이다. 모든 product user, 모든 local OS user, process owner 또는 DohaMusic caller를 reviewer로 인정하지 않는다.

Review initiation surface는 `DOHAMUSIC_LOCAL_GOVERNANCE_UI`다. UI 접근은 proof가 아니며 DohaMusic가 `OS_BOUND_LOCAL_OPERATOR_CREDENTIAL` model로 upstream operator를 검증한 뒤에만 reviewer assertion 흐름을 시작할 수 있다. Governance UI와 proof adapter는 아직 구현되지 않았다.

## Two-level identity model

Upstream human proof와 downstream Provider model을 분리한다.

```text
LOCAL_AUTHENTICATED_OPERATOR
  → DohaMusic verification
  → DOHAMUSIC_DELEGATED_ASSERTION
  → DohaAudio private mapping
  → ReviewerAuthority
```

DohaMusic은 human identity verification을 소유하고 DohaAudio는 mapping, ReviewerAuthority와 semantic decision scope를 소유한다. Authentication 성공은 mapping·ReviewerAuthority 또는 approval을 자동 생성하지 않는다.

`OS_BOUND_LOCAL_OPERATOR_CREDENTIAL`은 operator context binding, caller-supplied username 불신과 non-public proof를 요구한다. Windows Credential Manager, DPAPI, Windows Hello, OS access-token API, keychain 또는 custom application credential은 선택하지 않았다.

## Delegated assertion model

DohaAudio authentication provider model은 `DOHAMUSIC_DELEGATED_ASSERTION`이다. 이는 external vendor IdP가 아니라 DohaAudio가 검증해야 할 production adapter model이다.

- issuer owner: DohaMusic
- exact audience: DohaAudio
- lifetime: short-lived, exact TTL 미선정
- issued-at/freshness와 expiry 검증
- replay resistance 필수
- service principal과 human reviewer principal 분리
- private subject를 opaque reviewer mapping으로 변환
- ReviewerAuthority exact scope 별도 검증
- invalid·stale·expired·replayed·unknown mapping은 fail-closed

JWT, PASETO, custom HMAC token, mTLS claim, RSA, ECDSA, EdDSA와 concrete key format·algorithm은 선택하지 않는다.

## Service identity

DohaMusic→DohaAudio service direction은 `LOCAL_INTERNAL_SERVICE_IDENTITY`다. Service authentication과 reviewer assertion은 별도 계층이며 service credential만으로 human reviewer를 사칭하거나 semantic approval을 만들 수 없다. Concrete service protocol과 credential rotation은 후속 구현 결정이다.

## Network, offline과 MFA

- V1 reviewer authentication은 external IdP network를 요구하지 않는다.
- Same-machine internal transport는 external authentication network dependency가 아니다.
- Reviewer path는 external IdP outage 없이 offline-capable해야 한다.
- V1 MFA는 local single-owner non-public scope에서 필수가 아니다.
- Future remote privileged governance는 MFA, recovery, network outage와 audit requirement를 새로 결정한다.

MFA가 없어도 stable authenticated operator identity, freshness, expiry, replay resistance와 fail-closed proof verification은 유지한다.

## Lifecycle, secret과 private store

- Local operator proof provisioning·disable·revoke는 DohaMusic local authentication boundary가 소유한다.
- Concrete OS credential recovery는 implementation detail로 남지만 product requirement resolution을 되돌리지 않는다.
- Mapping revoke/supersede, ReviewerAuthority grant/revoke와 semantic re-review는 DohaAudio가 소유한다.
- DohaMusic은 operator proof material, assertion signing material과 service credential을 소유한다.
- DohaAudio는 assertion verification material과 private mapping store를 소유한다.
- Human assertion credential과 service credential은 분리하고 실제 secret·key·credential은 추가하지 않는다.

V1 mapping·revocation lineage에는 restart 후 유지되는 `LOCAL_PERSISTENT_PRIVATE_STORE`가 필요하다. Store owner는 DohaAudio private composition boundary다. SQLite, OS secure store 또는 hybrid 중 concrete technology는 후속 DohaAudio PR에서 선택한다.

Public semantic DB에는 private subject, raw credential, assertion과 password를 저장하지 않는다. Threat model은 local process compromise, filesystem·backup theft, log leakage, forged local proof, assertion replay, service-principal impersonation과 mapping tampering을 포함한다.

## 후보 최종 판정

| 후보 | V1 판정 |
|---|---|
| Local Authenticated Operator | upstream identity model로 선택, concrete adapter 미구현 |
| Generic OIDC | 선택 안 함, future remote에서 재검토 가능 |
| GitHub Identity | 선택 안 함 |
| Self-managed product account | 선택 안 함 |
| DohaMusic delegated assertion | DohaAudio provider model로 선택, adapter 미구현 |

## Provider selection readiness와 Runtime 상태

`AUTH_REQUIREMENTS_RESOLVED=true`는 provider selection을 막던 product-owner requirement가 해결됐다는 뜻이다. `AUTH_PROVIDER_SELECTION_READY=true`는 selected model이 `DOHAMUSIC_DELEGATED_ASSERTION`으로 명확하다는 뜻이다. 모든 implementation detail이 확정됐거나 adapter가 operational하다는 뜻이 아니다.

이번 DohaMusic ADR은 DohaAudio를 변경하지 않는다.

```yaml
AUTH_PROVIDER_SELECTED: false
AUTH_PROVIDER_CONFIGURED: false
AUTH_PROVIDER_OPERATIONAL: false
PRIVATE_IDENTITY_STORE_OPERATIONAL: false
REAL_IDENTITY_MAPPING_COUNT: 0
REAL_REVIEWER_AUTHORITY_COUNT: 0
REAL_HUMAN_APPROVAL_COUNT: 0
```

## 남은 implementation 결정

- Concrete OS proof API, provisioning·recovery·revocation adapter
- Local internal service authentication protocol
- Assertion format, algorithm, exact TTL, clock와 replay contract
- Signing·verification key storage, rotation과 revocation
- Local persistent private store technology와 backup·tamper response
- Local governance UI, explicit reviewer action과 audit UX

이 항목은 `AUTH_REQUIREMENTS_RESOLVED` 또는 selection readiness를 false로 되돌리는 blocker가 아니다. DohaAudio Runtime activation 전 구현·검증 Gate다.

## 미구현과 영향

이 ADR은 문서 authority만 변경한다. Product login, governance UI, OS authentication API, assertion signing·verification, service credential, secret, private DB, identity mapping, ReviewerAuthority와 semantic approval은 구현하지 않는다. DohaAudio와 Common Contract를 수정하지 않고 Dataset·Rights·Model·GPU·Training 상태도 변경하지 않는다.

## 재검토 조건

- V1 topology가 remote·hybrid 또는 multi-user로 변경될 때
- Reviewer population 또는 interaction surface가 single owner/local UI에서 변경될 때
- OS-bound proof가 V1 threat model을 만족할 수 없을 때
- DohaAudio adapter·private store 구현에서 product requirement와 직접 충돌이 발견될 때

## 관련 PR

- 이 ADR을 제안하고 explicit product-owner authority로 갱신한 PR: #109
