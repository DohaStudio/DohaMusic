# ADR-037 — Reviewer Authentication과 배포 권위

> 상태: 승인 — 경계 확정, Provider 선택 보류
> 작성일: 2026-08-21
> 최종 수정일: 2026-08-21
> 관련 기능: DohaMusic product identity, DohaAudio human reviewer authentication
> 관련 문서: [Authentication Authority](../09-security/reviewer-authentication-deployment-authority.md), [Provider 책임 경계](../03-architecture/repository-provider-boundaries.md), [Provider API 계약](../06-api/provider-api-contract.md), [배포 아키텍처](../03-architecture/deployment-architecture.md), [ADR-028](ADR-028-provider-runtime-artifact-contract.md)

## 배경

DohaAudio ADR-014는 real reviewer authentication provider를 선택하기 전에 production deployment topology, product identity owner, login interaction, issuer, network, assurance, recovery·revocation, secret과 private mapping store의 권위가 필요하다고 결정했다.

DohaMusic 저장소는 CURRENT 로컬 단일 사용자 Studio와 TARGET 제품 Runtime을 명확히 구분한다. 동시에 DohaMusic이 사용자·인증·권한과 Orchestrator를 소유하고 Frontend·Workspace client가 Provider를 직접 호출하지 않는다고 정한다. 그러나 public production topology와 account/login, semantic reviewer population·interaction은 구현되거나 결정되지 않았다.

## 저장소 근거

- README, Master Roadmap과 Phase 8 DoD는 CURRENT를 로컬 단일 사용자 MVP로 한정하고 인증·소유권을 Phase 9 공개 운영 차단 조건으로 둔다.
- 배포 문서는 초기 구성요소를 한 개발 머신에 둘 수 있다고 하면서 운영 배치와 배포는 미결정·미실행으로 둔다.
- Provider 책임 경계와 공통 Provider 계약은 DohaMusic만 DohaAudio를 호출하고 사용자 권한을 DohaMusic이 관리한다고 정한다.
- Provider API 계약은 Orchestrator service identity를 요구하지만 service authentication과 key rotation을 미확정 사항으로 둔다.
- 코드에는 account/user table, login UI·API, JWT/session, OAuth/OIDC와 authorization role subsystem이 없다.
- Continuous Learning Review Hub는 TARGET일 뿐 DohaAudio semantic reviewer의 역할·인구·UI를 확정하지 않는다.

## 결정

1. CURRENT deployment topology를 `LOCAL_ONLY`, CURRENT product authentication을 `NO_PRODUCT_LOGIN`으로 기록한다. 이는 implicit localhost trust가 아니다.
2. production topology는 `UNRESOLVED`다. 현재 local이라는 사실로 미래 production을 local-only로 고정하지 않는다.
3. DohaMusic은 product identity/account와 Orchestrator service identity의 owner다. 실제 subsystem과 credential은 미구현이다.
4. DohaAudio는 opaque reviewer mapping, ReviewerAuthority와 semantic decision의 owner다.
5. semantic human reviewer의 identity owner와 interaction은 reviewer population이 정해지지 않아 미확정이다.
6. 사용자·Frontend는 DohaAudio에 직접 로그인하거나 호출하지 않는다. human review가 DohaMusic에서 시작될 경우 trust direction은 `DELEGATED_DOHAMUSIC_IDENTITY`다.
7. delegated reviewer assertion과 DohaMusic→DohaAudio service authentication은 서로 다른 principal·credential로 분리한다.
8. direct OIDC/GitHub verification, local operator, self-managed account, trusted proxy와 mTLS 중 실제 authentication provider는 선택하지 않는다.
9. production private mapping은 restart·revocation lineage를 위해 persistent해야 하고 DohaAudio private boundary가 소유한다. storage technology와 secret manager는 미선정이다.
10. 최소 reviewer assurance는 stable authenticated identity, exact issuer/audience, freshness와 replay resistance다. MFA는 remote privileged topology 결정 시 함께 정한다.
11. `AUTH_REQUIREMENTS_RESOLVED=false`, `AUTH_PROVIDER_SELECTION_READY=false`를 유지한다.

## Direct와 delegated 검증

`DIRECT: Human → external IdP → DohaAudio`는 DohaAudio가 product-user authentication과 login surface를 소유하게 하므로 현재 Provider 경계와 맞지 않는다.

목표 방향은 다음과 같다.

```text
Human → DohaMusic authentication → short-lived DohaMusic assertion → DohaAudio mapping → ReviewerAuthority
```

assertion은 issuer `DohaMusic`, audience `DohaAudio`, subject privacy, expiry, freshness, replay resistance와 signature verification을 요구한다. 이 ADR은 signing protocol, key, JWKS, token 또는 adapter를 구현하지 않는다.

## 선택하지 않은 대안

- **Local Operator**: CURRENT와 가깝지만 OS session, keychain credential, reverse proxy 또는 manual signed provisioning 중 근거가 없다.
- **Generic OIDC**: issuer·client·redirect·network·lifecycle·recovery 요구가 없다.
- **GitHub Identity**: Repository 사용과 maintainer identity를 product reviewer authority로 연결하는 요구가 없다.
- **Self-managed account**: password·recovery·account store 운영 결정을 먼저 요구한다.
- **Trusted proxy**: production proxy와 trusted header 경계가 없다.
- **mTLS**: service principal 후보일 뿐 human identity·interaction을 해결하지 않는다.

## 남은 결정

Provider selection 전 product owner는 production topology, semantic reviewer population, reviewer interaction, human issuer와 lifecycle, local compromise 또는 remote network·MFA 정책, service credential protocol, delegated assertion key management와 private store technology를 결정해야 한다.

## 보안 결과

- localhost, DohaMusic caller, GitHub username, OS username과 service token은 human reviewer authentication proof가 아니다.
- authentication은 mapping, ReviewerAuthority 또는 semantic approval을 자동 생성하지 않는다.
- identity revocation, mapping revocation, ReviewerAuthority revocation과 semantic re-review는 별도 수명주기다.
- 인증 장애·불일치와 미확정 config는 fail-closed한다.

## 영향과 미구현

이 ADR은 문서 authority만 추가한다. OAuth/OIDC/GitHub/local auth, account DB, secret resolver, assertion, private identity DB, mapping, ReviewerAuthority와 approval은 구현하지 않는다. DohaAudio와 공통 계약을 변경하지 않으며 Rights·Dataset·Model·Training 상태도 변경하지 않는다.

## 재검토 조건

- production 배치가 local-only, remote service 또는 hybrid로 승인될 때
- semantic reviewer population과 interaction이 승인될 때
- DohaMusic product authentication 또는 Provider service authentication을 구현할 때
- DohaAudio가 delegated assertion adapter와 persistent private mapping store를 선택할 때

## 관련 PR

- 이 ADR을 제안한 PR: Draft PR 생성 후 기록
