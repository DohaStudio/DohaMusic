# ADR-042 — V1 Local Operator Authentication Foundation

> 상태: 승인 — Foundation 구현, concrete adapter 구현 미착수
> 작성일: 2026-08-21
> 최종 수정일: 2026-08-21
> 관련 문서: [ADR-038](ADR-038-v1-reviewer-authentication-product-decision.md), [Mechanism 비교](../01-research/local-operator-proof-mechanism-comparison.md), [Architecture](../03-architecture/local-operator-authentication.md)

## Context

ADR-038과 product owner는 V1 upstream human identity를 `LOCAL_AUTHENTICATED_OPERATOR`, proof model을 `OS_BOUND_LOCAL_OPERATOR_CREDENTIAL`로 승인했다. DohaAudio PR #15는 downstream model `DOHAMUSIC_DELEGATED_ASSERTION`을 선택했지만 config·verification·mapping·authority는 활성화하지 않았다.

DohaMusic는 Next.js browser UI와 localhost FastAPI/Python Backend를 same-machine에서 실행하며 Windows를 지원한다. Localhost, process owner, OS username과 no-product-login은 privileged semantic review의 human authentication proof가 아니다.

## Candidate mechanisms

Windows process/access token, Credential Manager generic credential, user-bound DPAPI, Windows Hello/WebAuthn, application-local unlock credential, secure-store-backed generated credential과 trusted helper를 offline fit, user interaction, OS binding, replay/theft risk, recovery, secret storage, non-admin operation, Python integration, testability, migration, privacy와 auditability로 비교했다.

Microsoft 공식 문서에 따르면 process access token은 process context를 식별하고, Credential Manager generic credential은 application-defined storage이며, DPAPI는 같은 user/computer의 at-rest protection을 제공한다. 이 세 후보만으로는 privileged action 시점의 explicit human verification을 증명하지 않는다. Windows WebAuthn API는 Windows Hello 같은 user-verifying platform authenticator availability와 user-consented transaction assertion signature를 제공한다.

## Decision

1. Authority-selected proof model은 `OS_BOUND_LOCAL_OPERATOR_CREDENTIAL`로 유지한다.
2. V1 concrete mechanism으로 `WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL`을 선택한다.
3. Selection은 implementation·configuration·operation과 분리한다.
4. Provider-independent `LocalOperatorAuthenticationProvider`의 `verify()`·`revalidate()` contract를 추가한다.
5. Credential input은 raw material이 아닌 opaque logical reference, fresh challenge와 private session-binding reference만 가진다.
6. Verified context는 immutable provider witness와 provenance, authenticated/expiry time을 요구한다.
7. Caller-created principal/context, copied·mutated context, witness mismatch, stale·expired context와 disabled provider를 fail-closed한다.
8. Deterministic Fake provider는 test-only이며 production bootstrap에서 금지한다.
9. Unavailable provider는 verified context를 발급하지 않고 structured `LOCAL_OPERATOR_AUTH_NOT_OPERATIONAL`로 실패한다.
10. Domain/config/log에 password, secret, raw credential, token, key, Windows credential blob, username, private subject나 private session reference를 저장·노출하지 않는다.

현재 상태는 다음과 같다.

```yaml
LOCAL_OPERATOR_AUTH_SELECTED: true
LOCAL_OPERATOR_PROOF_MODEL_SELECTED: true
CONCRETE_OS_ADAPTER_SELECTED: true
CONCRETE_LOCAL_OPERATOR_MECHANISM: WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL
CONCRETE_OS_ADAPTER_IMPLEMENTED: false
LOCAL_OPERATOR_AUTH_CONFIGURED: false
LOCAL_OPERATOR_AUTH_OPERATIONAL: false
REAL_LOCAL_OPERATOR_IDENTITY_COUNT: 0
REAL_AUTHENTICATION_SESSION_COUNT: 0
```

## Trust boundary

Local operator authentication은 human proof만 소유한다. DohaMusic Orchestrator service identity, delegated assertion issuer, DohaAudio private mapping, `ReviewerAuthority`와 semantic approval을 생성하지 않는다. V1 MFA가 필수가 아니어도 user verification, fresh challenge, expiry와 fail-closed provenance는 생략하지 않는다.

## Freshness, expiry와 session

Contract는 challenge issuance/expiry, context authentication/expiry와 private session binding을 필수로 한다. Exact challenge maximum age, context TTL, re-authentication interval과 governance UX는 adapter evidence 없이 숫자를 확정하지 않는다.

## Secret, recovery와 revocation

Future WebAuthn credential material은 OS/platform authenticator와 private adapter storage boundary에 남는다. DohaMusic는 provisioning, recovery, disable·revoke와 audit를 소유한다. DohaAudio mapping·authority revocation과 분리한다.

## Alternatives

- Process token 또는 username 단독: current process/session 식별을 human proof로 오인하므로 거부
- Credential Manager/DPAPI 단독: storage/at-rest protection이며 fresh user verification이 아니므로 거부
- Application password: raw password 처리·verifier·recovery subsystem을 새로 요구하므로 거부
- Trusted helper/proxy: IPC/header trust와 privileged lifecycle 복잡성을 추가하므로 V1 거부
- Generic OIDC/GitHub: V1 external IdP와 product login authority에 맞지 않아 거부

## Not implemented

Win32/WebAuthn 호출, browser ceremony, RP ID/origin, credential algorithm, registration, public-key persistence, exact TTL, recovery UI, governance UI, delegated assertion, service authentication, DohaAudio verification·mapping·authority와 semantic decision은 구현하지 않는다.

## Consequences and next step

Domain과 test boundary는 구현됐지만 production authentication은 계속 unavailable하다. 다음 별도 PR은 `DohaMusic Concrete Local Operator Adapter`이며 공식 Windows API availability, challenge ceremony, user verification, persistence와 recovery/revocation을 구현·검증한다. 그 전에는 reviewer activation을 시작하지 않는다.
