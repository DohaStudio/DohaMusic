# Reviewer Authentication과 배포 권위

> 문서 역할: DohaMusic 제품 identity와 DohaAudio reviewer authentication 연결의 Canonical Authority
> 문서 상태: [운영 기준 / 구현 미착수]
> 최종 수정일: 2026-08-21
> 관련 문서: [Provider 책임 경계](../03-architecture/repository-provider-boundaries.md), [Provider API 계약](../06-api/provider-api-contract.md), [배포 아키텍처](../03-architecture/deployment-architecture.md), [ADR-037](../11-decisions/ADR-037-reviewer-authentication-deployment-authority.md), [ADR-038](../11-decisions/ADR-038-v1-reviewer-authentication-product-decision.md)

## 1. 권위 기준

이 문서는 인증 구현을 승인하지 않는다. 현재 저장소에서 확정할 수 있는 제품·배포·호출 경계와, 별도 product-owner 결정 전에는 확정할 수 없는 reviewer 요구를 분리한다.

```yaml
CURRENT_DEPLOYMENT_TOPOLOGY: LOCAL_ONLY
V1_PRODUCTION_DEPLOYMENT_TOPOLOGY: UNRESOLVED
FUTURE_DEPLOYMENT_TOPOLOGY: UNRESOLVED
CURRENT_PRODUCT_AUTH_MODEL: NO_PRODUCT_LOGIN
V1_PRODUCT_LOGIN_REQUIRED: UNRESOLVED
PRODUCT_IDENTITY_OWNER: DohaMusic
REVIEWER_IDENTITY_OWNER: UNRESOLVED
REVIEWER_AUTHORITY_OWNER: DohaAudio
SERVICE_IDENTITY_OWNER: DohaMusic
DIRECT_PROVIDER_USER_ACCESS: false
REVIEWER_TRUST_DIRECTION: DELEGATED_DOHAMUSIC_IDENTITY
V1_REVIEWER_POPULATION: UNRESOLVED
V1_REVIEWER_INTERACTION: UNRESOLVED
UPSTREAM_HUMAN_IDENTITY_MODEL: UNRESOLVED
LOCAL_OPERATOR_PROOF_MECHANISM: UNRESOLVED
DOHAAUDIO_AUTH_PROVIDER_MODEL: UNRESOLVED
V1_EXTERNAL_AUTH_NETWORK_REQUIRED: UNRESOLVED
V1_REVIEWER_AUTH_OFFLINE_CAPABLE: UNRESOLVED
V1_REVIEWER_MFA_REQUIRED: UNRESOLVED
SELECTED_AUTHENTICATION_PROVIDER: null
AUTH_REQUIREMENTS_RESOLVED: false
AUTH_PROVIDER_SELECTION_READY: false
```

`REVIEWER_TRUST_DIRECTION`은 제품 사용자가 Provider에 직접 로그인하지 않는 목표 경계다. 실제 local credential, OIDC issuer 또는 assertion protocol을 선택했다는 뜻이 아니다.

ADR-038 재판정은 CURRENT MVP를 V1 production 결정 근거로 승격하지 않는다. CURRENT, V1 production과 future를 분리하며 V1 값은 product-owner가 명시적으로 승인할 때까지 fail-closed한다.

## 2. CURRENT와 TARGET

### CURRENT

- DohaMusic은 로컬 단일 사용자 Responsive Studio MVP다.
- Web, FastAPI, Worker, SQLite와 local Storage를 한 개발 머신에 둘 수 있다.
- account/user table, login UI·API, session/JWT, OAuth/OIDC와 authorization role 구현이 없다.
- 기존 local Adapter·subprocess가 Compatibility Workflow를 제공한다.
- DohaAudio Runtime transport, Provider service authentication과 human semantic review는 연결되지 않았다.
- 따라서 현재 제품 모델은 `MODEL A: No product login currently required`다. 이것은 localhost 또는 OS username을 인증 증명으로 인정한다는 뜻이 아니다.

### TARGET

- DohaMusic은 사용자·인증·권한, Workspace, Orchestrator와 Provider 호출을 소유한다.
- Frontend와 일반 Workspace client는 DohaAudio를 직접 호출하지 않는다.
- DohaAudio는 DohaMusic Orchestrator가 호출하는 내부 Provider다.
- 운영 시 API/Worker·Provider를 원격으로 분리할 수 있으나 `REMOTE_SERVICE` 또는 `HYBRID` 배치, public login과 identity issuer는 아직 결정되지 않았다.

### V1 product decision audit

| 후보 | 판정 | 저장소 근거 |
|---|---|---|
| `V1_PRODUCTION_DEPLOYMENT_TOPOLOGY=LOCAL_ONLY` | 미확정 | CURRENT Phase 8은 기능 검증 MVP이고 Phase 9 production은 0% 계획 상태다. V1 release topology 승인 문서가 없다. |
| `V1_REVIEWER_POPULATION=SINGLE_OWNER_OPERATOR` | 미확정 | 제품 방향은 개인 창작 흐름을 설명하지만 DohaAudio semantic governance reviewer를 제품 owner/operator로 지정하지 않는다. |
| `V1_REVIEWER_INTERACTION=DOHAMUSIC_LOCAL_GOVERNANCE_UI` | 미확정 | D8 Review Hub는 계획 상태이고 DohaAudio Traditional semantic review surface와 동일하다는 계약이 없다. |
| `REVIEWER_IDENTITY_OWNER=DohaMusic` | 미확정 유지 | DohaMusic은 product identity owner지만 reviewer population·interaction이 정해지지 않아 human proof owner를 확정할 수 없다. |
| `UPSTREAM_HUMAN_IDENTITY_MODEL=LOCAL_AUTHENTICATED_OPERATOR` | 미확정 | OS session, keychain, application unlock, proxy 또는 provisioning 중 proof authority가 없다. |
| `DOHAAUDIO_AUTH_PROVIDER_MODEL=DOHAMUSIC_DELEGATED_ASSERTION` | 미확정 | delegated direction은 유지하지만 upstream reviewer와 interaction이 정해지기 전 production adapter model을 selected로 승격하지 않는다. |

따라서 V1 product login, external auth network, offline capability와 MFA도 현재 근거만으로 true/false를 확정하지 않는다. 이 보류는 future remote·hybrid 선택을 막지 않으며, local 환경을 authenticated human으로 간주하지 않는다.

## 3. 사람 identity와 semantic authority

다음 네 역할은 서로 대체할 수 없다.

| 역할 | Owner | 현재 상태 |
|---|---|---|
| Product user/account identity | DohaMusic | TARGET 책임, 구현 없음 |
| Human reviewer identity | 미확정 | reviewer population·interaction 미확정 |
| ReviewerAuthority와 semantic scope | DohaAudio | Provider domain governance, 실제 부여 0 |
| DohaMusic Orchestrator service identity | DohaMusic | 필요성만 확정, credential·rotation 미확정 |

DohaMusic의 Continuous Learning Review Hub는 장기 TARGET이고 DohaAudio의 Traditional partial-group semantic reviewer와 동일 인물·역할이라는 근거가 없다. 일반 product user, 로컬 operator, Dataset governance 관리자 또는 별도 backoffice reviewer 중 무엇인지 product owner가 먼저 결정해야 한다.

인증된 DohaMusic identity도 caller-supplied reviewer ID로 DohaAudio에 전달해서는 안 된다. DohaAudio의 기존 경계인 `verified context → private mapping → opaque reviewer ID → ReviewerAuthority`를 유지한다.

## 4. 호출과 신뢰 위임

목표 연결은 다음과 같다.

```text
Human
  → DohaMusic authentication [provider 미선정]
  → DohaMusic reviewer assertion [protocol 미구현]
  → DohaAudio private identity mapping
  → DohaAudio ReviewerAuthority
```

DohaAudio가 제품 사용자의 external IdP를 직접 검증하는 `DIRECT` 모델은 현재 저장소 경계와 맞지 않는다. 향후 human review를 DohaMusic에서 시작한다면 `DELEGATED` 방향을 사용한다.

위임 assertion은 구현 전 별도 계약에서 최소한 다음을 정해야 한다.

- issuer는 DohaMusic이고 audience는 DohaAudio다.
- service principal과 reviewer principal을 별도 claim과 credential로 구분한다.
- assertion은 short-lived이고 exact audience, freshness, expiry와 replay resistance를 검증한다.
- private subject를 공개 semantic record에 저장하지 않는다.
- signature algorithm allowlist, key rotation, clock policy와 audit retention을 명시한다.
- assertion 인증 성공은 ReviewerAuthority 또는 semantic approval을 자동 부여하지 않는다.

DohaMusic→DohaAudio service authentication은 별도 경계다. service credential은 human reviewer 증명이 아니며, service 인증 성공만으로 reviewer mapping을 만들 수 없다.

## 5. 후보 평가

| 후보 | 판정 | 근거 |
|---|---|---|
| Local Authenticated Operator | 보류 | CURRENT와 가깝지만 OS session, keychain credential, local reverse proxy 또는 signed provisioning 중 authority가 없다. localhost·OS username은 proof가 아니다. |
| Generic OIDC | 보류 | issuer, client, redirect, network, account lifecycle, recovery와 MFA 요구가 없다. |
| GitHub Identity | 제외 유지 | source-control membership을 product reviewer authority로 사용한다는 요구가 없다. |
| Self-managed account | 보류 | account lifecycle·password recovery·private store 운영 책임이 결정되지 않았다. |
| Trusted proxy | 보류 | production proxy topology와 header authenticity 경계가 없다. |
| mTLS | service 후보만 보류 | service identity에는 사용할 수 있지만 사람 reviewer identity와 interaction을 해결하지 않는다. |
| Service-issued signed reviewer assertion | 목표 trust 방향 | DohaMusic-only Provider 호출 경계와 맞지만 upstream human authentication과 signing protocol이 미확정이다. |

따라서 `SELECTED_AUTHENTICATION_PROVIDER=null`을 유지한다. `DELEGATED_DOHAMUSIC_IDENTITY`는 Provider 선택이 아니라 direct product login을 DohaAudio에서 배제하는 trust direction이다.

## 6. Network, assurance와 장애 정책

- CURRENT reviewer authentication network call은 0이다.
- production auth network requirement는 topology와 upstream provider 선택에 따라 `conditional`이다.
- 인증 dependency가 unavailable이거나 assertion 검증이 실패하면 fail-closed하고 cached identity만으로 새 semantic approval을 만들지 않는다.
- 최소 assurance는 stable authenticated identity, recent authentication, exact issuer/audience와 replay resistance다.
- MFA는 현재 필수가 아니다. remote privileged governance를 선택할 때 product owner가 MFA와 recovery assurance를 함께 결정한다.
- offline reviewer operation 필요 여부는 미확정이다. LOCAL_ONLY라는 사실만으로 implicit trust를 허용하지 않는다.

## 7. Lifecycle, recovery와 revocation

| 대상 | Owner |
|---|---|
| Product account 생성·disable·delete·rename·recovery·ownership transfer | DohaMusic, 실제 account 모델 선택 후 |
| Human identity credential recovery | 미확정 identity issuer |
| Service credential 발급·rotation·revocation | DohaMusic deployment/composition owner |
| Private identity mapping revoke/supersede | DohaAudio |
| ReviewerAuthority grant·revoke | DohaAudio |
| 기존 semantic decision invalidation·재검토 | DohaAudio governance policy |

Identity revocation은 mapping·ReviewerAuthority·semantic decision을 자동 삭제하지 않는다. 각 lineage와 감사 기록을 보존하고 명시적으로 revoke 또는 re-review한다.

## 8. Secret과 private identity store

DohaMusic은 자신의 login/session 또는 delegated assertion signing secret과 service credential 공급을 소유한다. DohaAudio는 verification material과 private identity mapping store를 소유한다. 실제 secret manager, key와 credential reference는 production topology가 결정된 뒤 별도 PR에서 선택한다.

Private identity store에는 최소 provider/issuer ID, private subject reference 또는 그 안전한 fingerprint, opaque reviewer ID, mapping version, created/revoked/superseded lineage와 필요한 audit metadata만 둔다. raw token, password, assertion과 semantic approval content는 저장하지 않는다.

- read/write: DohaAudio authentication·mapping composition boundary만 허용
- public DB 분리: public semantic API와 ReviewerAuthority record에서 provider subject를 숨김
- persistence: production에서는 restart 후 mapping·revocation lineage를 보존해야 하므로 필요
- technology: local SQLite private store, OS secure store 또는 remote DB 중 미선정
- backup: 선택한 store의 revocation lineage를 보존하는 보호된 backup·restore 필요
- at-rest: 플랫폼이 제공하는 access control과 encryption을 사용하고 backup에도 동일 보호 적용
- threat: public API disclosure, backup theft, process/log leakage, local device compromise와 malicious caller-supplied identity를 포함

로컬 머신 전체가 침해된 경우 application-level store만으로 보호를 보장할 수 없다. 그 위험을 수용할지 OS credential·keychain 또는 별도 service boundary를 요구할지는 production topology 결정에 포함한다.

## 9. 선택 전 남은 product-owner 결정

다음이 확정되기 전 `AUTH_REQUIREMENTS_RESOLVED=false`, `AUTH_PROVIDER_SELECTION_READY=false`다.

1. production topology가 local-only, remote service 또는 hybrid 중 무엇인지
2. DohaAudio semantic reviewer가 product user, local operator, Dataset governance 관리자 또는 backoffice reviewer 중 누구인지
3. browser/local UI, CLI, admin/backoffice 또는 signed provisioning 중 reviewer interaction
4. upstream human identity issuer와 account lifecycle·recovery·revocation owner
5. local operator라면 실제 authentication proof와 local compromise policy
6. remote라면 network dependency, outage, MFA/assurance와 audit retention
7. service authentication transport와 credential rotation owner의 구체 protocol
8. delegated assertion signing·verification, key storage와 private mapping store technology

## 10. Fail-closed 현재 상태

이 결정은 DohaAudio 상태를 변경하지 않는다.

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

Rights, Dataset integrity, split, model, config, environment, preflight, approval과 Training gate도 모두 기존 fail-closed 상태를 유지한다.
