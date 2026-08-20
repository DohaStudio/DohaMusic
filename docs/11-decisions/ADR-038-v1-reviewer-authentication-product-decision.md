# ADR-038 — V1 Reviewer Authentication Product Decision 재판정

> 상태: 보류 — product-owner 결정 필요
> 작성일: 2026-08-21
> 최종 수정일: 2026-08-21
> 관련 기능: DohaMusic V1 product identity, DohaAudio human reviewer authentication
> 관련 문서: [Authentication Authority](../09-security/reviewer-authentication-deployment-authority.md), [ADR-037](ADR-037-reviewer-authentication-deployment-authority.md), [제품 방향](../02-product/ai-native-daw-product-direction.md), [Phase 9 DoD](../DoD/Phase-09.md), [Frontend 전환 계획](../../planning/ai-native-daw-frontend-migration.md)

## 배경

ADR-037은 CURRENT local single-user/no-product-login과 DohaMusic product·service identity, DohaAudio ReviewerAuthority, direct Provider user access 금지 및 delegated trust direction을 확정했다. Production topology, semantic reviewer population·interaction과 upstream human proof는 product-owner 근거가 없어 보류했다.

이번 재판정은 V1 후보인 local-only production, single owner/operator reviewer, DohaMusic local governance UI, local authenticated operator와 DohaMusic-issued delegated assertion이 현재 repository evidence로 확정 가능한지 검토한다. 기술 구현이나 Provider activation은 범위가 아니다.

## Repository evidence

- 제품 방향, README, Master Roadmap과 Phase 8 DoD는 CURRENT를 로컬 단일 사용자 기능 검증 MVP로 한정한다.
- Phase 9 Production은 0/18이며 topology, 인증·권한, 공개 ingress, 운영 보안과 명시적 release 승인이 완료되지 않았다.
- 장기 제품은 개인 창작 흐름을 목표로 하지만 semantic Dataset governance reviewer를 제품 owner/operator로 지정하지 않는다.
- D8 Continuous Learning Review Hub는 `[계획]`이며 candidate·rights·eligibility 상태를 보여주는 product UX다. DohaAudio Traditional partial-group semantic review의 population 또는 interaction surface라는 계약은 없다.
- 코드에는 product login, account lifecycle, local operator proof, OS authentication, reviewer governance UI와 delegated assertion 구현이 없다.
- Common Provider 경계는 DohaMusic-only 호출과 사용자 권한의 DohaMusic ownership을 요구하지만 human reviewer identity owner나 proof mechanism을 선택하지 않는다.

## 후보 판정

| 후보 | 판정 | 이유 |
|---|---|---|
| V1 production `LOCAL_ONLY` | 보류 | CURRENT MVP topology는 존재하지만 V1 production release topology 승인 근거가 없다. |
| `SINGLE_OWNER_OPERATOR` | 보류 | 개인 창작 사용자와 semantic governance reviewer를 동일인으로 정하는 근거가 없다. |
| `DOHAMUSIC_LOCAL_GOVERNANCE_UI` | 보류 | D8은 미구현 계획이며 DohaAudio semantic review surface로 확정되지 않았다. |
| Reviewer identity owner `DohaMusic` | 보류 | product identity ownership만 확정됐고 reviewer population·interaction이 없다. |
| `LOCAL_AUTHENTICATED_OPERATOR` | 보류 | OS session, keychain credential, application unlock, trusted proxy와 manual provisioning 중 proof authority가 없다. |
| `DOHAMUSIC_DELEGATED_ASSERTION` | 보류 | 목표 trust direction에는 맞지만 upstream human principal과 review initiation 계약이 확정되지 않았다. |

OIDC는 issuer·network·lifecycle 요구가 없고 local/offline V1도 확정되지 않아 선택하지 않는다. GitHub Identity는 source-control identity를 reviewer proof로 사용할 제품 근거가 없어 계속 제외한다. Self-managed account는 account·password·recovery 책임을 새로 만들므로 선택 근거가 없다.

## 결정

현재 authority는 다음과 같다.

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
V1_REVIEWER_POPULATION: UNRESOLVED
V1_REVIEWER_INTERACTION: UNRESOLVED
UPSTREAM_HUMAN_IDENTITY_MODEL: UNRESOLVED
LOCAL_OPERATOR_PROOF_MECHANISM: UNRESOLVED
REVIEWER_TRUST_DIRECTION: DELEGATED_DOHAMUSIC_IDENTITY
DOHAAUDIO_AUTH_PROVIDER_MODEL: UNRESOLVED
V1_EXTERNAL_AUTH_NETWORK_REQUIRED: UNRESOLVED
V1_REVIEWER_AUTH_OFFLINE_CAPABLE: UNRESOLVED
V1_REVIEWER_MFA_REQUIRED: UNRESOLVED
SELECTED_AUTHENTICATION_PROVIDER: null
AUTH_REQUIREMENTS_RESOLVED: false
AUTH_PROVIDER_SELECTION_READY: false
```

ADR-037은 당시와 현재의 유효한 경계 authority로 유지하며 이 ADR은 이를 대체하지 않는다. Product owner가 V1 topology, reviewer population·interaction과 upstream proof ownership을 승인하면 이 보류 결정을 새 ADR로 대체한다.

## Delegated model의 최소 보안 조건

향후 `DOHAMUSIC_DELEGATED_ASSERTION`을 선택하더라도 다음 조건을 모두 유지한다.

- trusted issuer owner는 DohaMusic이고 exact audience는 DohaAudio다.
- assertion은 short-lived이며 freshness, expiry와 replay resistance를 검증한다.
- service principal/credential과 human reviewer principal/assertion을 분리한다.
- verified identity는 DohaAudio private mapping에서 opaque reviewer ID로 변환한다.
- ReviewerAuthority exact scope를 별도로 확인하고 인증만으로 authority 또는 semantic approval을 만들지 않는다.
- 검증 실패, stale/replayed assertion, unknown mapping과 미확정 config는 fail-closed한다.

이 ADR은 JWT, PASETO, custom token, mTLS claim, signing algorithm, key storage 또는 service authentication protocol을 선택하지 않는다.

## Lifecycle, secret과 private store

- upstream operator provisioning·recovery·identity revocation owner는 proof mechanism과 함께 미확정이다.
- mapping revoke/supersede와 ReviewerAuthority grant/revoke는 DohaAudio가 소유한다.
- semantic decision invalidation·재검토는 DohaAudio governance가 소유한다.
- DohaMusic은 future assertion signing과 service credential 공급 경계를, DohaAudio는 verification material과 persistent private mapping store를 소유한다.
- 실제 secret manager·credential·key와 store technology는 미선정이다. Production mapping·revocation lineage의 persistent private store requirement는 유지하며 local/remote store class는 topology 결정 뒤 선택한다.

Threat model은 local process compromise, filesystem·backup theft, log leakage, caller identity spoofing, stale/replayed assertion과 reviewer mapping tampering을 포함한다. Sensitive subject material을 public/plain semantic DB에 저장하지 않는다.

## Product-owner가 결정할 항목

1. V1 production이 local-only, remote service 또는 hybrid인지
2. semantic reviewer가 single owner/operator, Dataset governance team, admin/backoffice 또는 다른 population인지
3. review를 DohaMusic local UI, browser, CLI, admin surface 또는 signed provisioning 중 어디서 시작하는지
4. upstream human proof를 OS session, keychain-backed credential, application unlock, trusted proxy 또는 provisioning 중 누가 소유하는지
5. external auth network와 offline capability requirement
6. V1 assurance·MFA 및 local compromise acceptance
7. service authentication protocol과 delegated assertion key lifecycle

이 결정 전에는 `AUTH_REQUIREMENTS_RESOLVED=false`, `AUTH_PROVIDER_SELECTION_READY=false`를 유지하고 DohaAudio Provider-selection PR을 시작하지 않는다.

## 미구현과 영향

이 ADR은 문서만 추가한다. Product login, governance UI, OS authentication API, OIDC/GitHub auth, assertion signing·verification, service credential, secret, private DB, identity mapping, ReviewerAuthority와 semantic approval은 구현하지 않는다. DohaAudio와 Common Contract를 변경하지 않고 Dataset·Rights·Model·GPU·Training 상태도 변경하지 않는다.

## 관련 PR

- 이 ADR을 제안한 PR: Draft PR 생성 후 기록
