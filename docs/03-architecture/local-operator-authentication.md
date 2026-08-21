# Local Operator Authentication Foundation

> 문서 상태: [Foundation 구현 / concrete adapter 미구현]
> 최종 수정일: 2026-08-21
> 관련 문서: [Authority](../09-security/reviewer-authentication-deployment-authority.md), [Mechanism 비교](../01-research/local-operator-proof-mechanism-comparison.md), [ADR-041](../11-decisions/ADR-041-v1-local-operator-authentication-foundation.md)

## 책임과 흐름

```text
DohaMusic local governance UI [미구현]
  → unverified LocalOperatorCredentialReference
  → LocalOperatorAuthenticationProvider.verify()
  → provider-issued VerifiedLocalOperatorContext
  → provider.revalidate()
  → internal LocalOperatorPrincipal
  → delegated assertion issuer [별도 후속 작업]
```

Domain은 Windows SDK나 Win32 type을 참조하지 않는다. `LocalOperatorAuthenticationProvider` port가 `verify()`와 `revalidate()`를 정의하고 concrete OS API는 future adapter 뒤에 둔다. Localhost, process owner, username, UI 접근과 service principal은 credential proof로 변환되지 않는다.

## Selection과 readiness

현재 immutable selection은 다음과 같다.

```yaml
LOCAL_OPERATOR_AUTH_SELECTED: true
LOCAL_OPERATOR_PROOF_MODEL_SELECTED: true
LOCAL_OPERATOR_PROOF_MODEL: OS_BOUND_LOCAL_OPERATOR_CREDENTIAL
CONCRETE_OS_ADAPTER_SELECTED: true
CONCRETE_LOCAL_OPERATOR_MECHANISM: WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL
CONCRETE_OS_ADAPTER_IMPLEMENTED: false
LOCAL_OPERATOR_AUTH_CONFIGURED: false
LOCAL_OPERATOR_AUTH_OPERATIONAL: false
REAL_LOCAL_OPERATOR_IDENTITY_COUNT: 0
REAL_AUTHENTICATION_SESSION_COUNT: 0
```

`LocalOperatorAuthenticationBootstrapper`는 config가 없으면 `LOCAL_OPERATOR_AUTH_NOT_CONFIGURED`, config만 있으면 unavailable provider와 `LOCAL_OPERATOR_AUTH_NOT_OPERATIONAL`을 반환한다. Test-only provider, selection/config/provider mismatch와 구현되지 않은 adapter의 operational 승격은 structured error로 차단한다. Anonymous, OS username, local process, OIDC 또는 Fake fallback은 없다.

## Contract

- `LocalOperatorCredentialReference`: provider, opaque credential reference, fresh challenge와 private session-binding reference만 포함하는 unverified input
- `LocalOperatorPrincipal`: provider, proof model, mechanism, assurance와 private opaque subject reference를 가진 internal principal
- `VerifiedLocalOperatorContext`: authentication/expiry 시각, private session reference와 provider witness를 가진 immutable capability
- `LocalOperatorAuthenticationProvider`: provider가 context를 발급하고 같은 provider가 provenance·freshness·expiry를 재검증
- `FakeLocalOperatorAuthenticationProvider`: deterministic test-only adapter이며 production bootstrap에서 항상 금지
- `UnavailableLocalOperatorAuthenticationProvider`: 실제 proof를 발급하지 않는 fail-closed stub

Caller가 만든 plain principal, 직접 생성·복사·field 변경 context, 다른 provider witness, expired/future context와 disabled provider는 모두 거부한다. Exact production freshness maximum, context TTL과 re-authentication UX는 concrete adapter PR에서 결정한다.

## Secret과 privacy

Domain/config에는 password, raw credential, assertion, token, private key나 Windows credential blob이 없다. Private subject와 session reference는 repr와 public diagnostic summary에서 제외한다. Error는 stable code와 safe message만 반환하며 raw Win32 exception이나 입력 credential reference를 포함하지 않는다.

Credential registration material, WebAuthn assertion, public-key record와 recovery data는 future adapter/secure storage boundary가 소유한다. Service identity, DohaAudio mapping, `ReviewerAuthority`, semantic approval과는 별도다.

## 미구현

- Windows WebAuthn API 호출과 availability preflight
- credential registration·lookup·assertion verification
- exact RP ID/origin, algorithm, challenge TTL와 context lifetime
- credential storage, recovery, disable·revoke와 audit
- governance UI와 privileged action wiring
- delegated assertion signing과 DohaAudio verification
