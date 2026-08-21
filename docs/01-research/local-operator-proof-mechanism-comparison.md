# Local Operator Proof Mechanism 비교

> 문서 상태: [조사 완료 / adapter 구현 미착수]
> 최종 수정일: 2026-08-21
> Repository authority: [Reviewer Authentication 배포 권위](../09-security/reviewer-authentication-deployment-authority.md)
> 결정: [ADR-041](../11-decisions/ADR-041-v1-local-operator-authentication-foundation.md)

## Repository runtime evidence

DohaMusic V1은 Windows를 지원하는 local-only 제품이다. 현재 실행 구조는 Windows 전용 desktop wrapper가 아니라 Next.js browser UI와 localhost FastAPI/Python Backend의 same-machine 구성이다. Frontend는 `localhost:3000`, Backend는 `127.0.0.1:8000`을 개발 기본값으로 사용하지만 localhost, process owner, 환경 변수나 OS username 문자열은 authentication proof가 아니다.

Product authority는 `LOCAL_AUTHENTICATED_OPERATOR`와 `OS_BOUND_LOCAL_OPERATOR_CREDENTIAL`을 이미 선택했다. 이 문서는 그 결정을 변경하지 않고 concrete Windows mechanism을 비교한다.

## 평가 기준

- external network 없이 offline-capable
- single-owner V1과 privileged governance action에 적합
- 명시적 user verification 또는 transaction consent
- OS/platform authenticator binding과 credential replay 저항성
- raw Windows password를 DohaMusic가 받거나 저장하지 않음
- public config/domain/log에 credential material을 두지 않음
- non-admin 실행, Python/Frontend adapter 격리, deterministic test 가능성
- recovery·revocation owner를 DohaMusic에 유지
- future cross-platform adapter로 교체 가능한 provider-independent domain

## 후보 비교

| 후보 | 공식 기술 성질 | V1 판정 |
|---|---|---|
| Windows process/access token | `OpenProcessToken`은 process에 연결된 access token을 연다. 현재 process security context를 식별하지만 privileged action 시점의 human re-authentication 또는 consent를 증명하지 않는다. | 보조 session-binding evidence만 가능, 단독 proof로 비선택 |
| Credential Manager generic credential | Generic credential은 application-defined이며 user process가 읽고 쓸 수 있는 장기 저장 기능이다. 인증 의미는 application이 별도로 구현해야 한다. | 저장 후보일 뿐 proof mechanism으로 비선택 |
| User-bound DPAPI | `CryptProtectData`는 보통 같은 logon credential과 같은 computer에서만 복호화되며 integrity MAC을 제공한다. 그러나 non-interactive decrypt가 가능하고 현재 privileged action의 user verification을 자체 증명하지 않는다. | at-rest 보호 후보, 단독 proof로 비선택 |
| Windows Hello / native WebAuthn platform authenticator | Windows WebAuthn API는 Windows Hello와 external security key에 접근하고 authenticator assertion signature를 만든다. platform authenticator availability와 user-verifying platform authenticator를 명시적으로 조회할 수 있다. | **V1 concrete mechanism으로 선택** |
| Application-local unlock password | application이 verifier·recovery·rate limit·secret storage를 모두 소유해야 하며 raw password 처리 경계를 새로 만든다. | 비선택 |
| Secure-store-backed generated credential | private material 보호에는 유용하지만 possession만으로 현재 human verification을 증명하지 않는다. | WebAuthn credential storage 성질로 흡수, 독립 proof로 비선택 |
| Trusted local helper/proxy | 별도 privileged process, IPC 인증과 lifecycle을 추가한다. localhost/header trust가 proof로 승격될 위험이 있다. | V1 비선택 |

## 선택

```yaml
LOCAL_OPERATOR_PROOF_MODEL_SELECTED: true
LOCAL_OPERATOR_PROOF_MODEL: OS_BOUND_LOCAL_OPERATOR_CREDENTIAL
CONCRETE_OS_ADAPTER_SELECTED: true
CONCRETE_LOCAL_OPERATOR_MECHANISM: WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL
CONCRETE_OS_ADAPTER_IMPLEMENTED: false
LOCAL_OPERATOR_AUTH_CONFIGURED: false
LOCAL_OPERATOR_AUTH_OPERATIONAL: false
```

`WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL`은 future adapter가 Windows Hello 같은 user-verifying platform authenticator의 scoped credential과 fresh challenge assertion을 검증해야 한다는 mechanism decision이다. 이번 foundation은 Win32 API, browser WebAuthn ceremony, RP ID, credential algorithm, registration, public-key persistence, recovery와 exact timeout을 구현하거나 확정하지 않는다.

## External technical evidence

다음은 product authority가 아니라 현재 Windows API capability를 확인하기 위한 Microsoft 공식 자료다.

- [WebAuthn Win32 API](https://learn.microsoft.com/en-us/windows/win32/api/webauthn/): Windows Hello·security key 연동, assertion signature, credential 생성과 platform authenticator availability API
- [WebAuthNIsUserVerifyingPlatformAuthenticatorAvailable](https://learn.microsoft.com/en-us/windows/win32/api/webauthn/nf-webauthn-webauthnisuserverifyingplatformauthenticatoravailable): Windows Hello 같은 user-verifying platform authenticator 가용성 확인
- [CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata): same-user/same-machine data protection과 integrity 성질
- [Kinds of Credentials](https://learn.microsoft.com/en-us/windows/win32/secauthn/kinds-of-credentials): generic credential은 application-defined authentication과 user-process read/write 대상
- [OpenProcessToken](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocesstoken): process access token 조회 범위

## 구현 전 확인 Gate

1. Windows 10/11 지원 범위와 실제 `WebAuthNGetApiVersionNumber`·platform authenticator availability를 검증한다.
2. local browser UI와 native adapter 중 ceremony owner, RP ID/origin, challenge 전달과 session binding을 결정한다.
3. user verification required, fresh one-time challenge, expiry와 assertion verification을 fail-closed로 구현한다.
4. public credential metadata와 private material의 저장 owner, backup·recovery·revoke를 위협 모델과 함께 결정한다.
5. raw Windows error, username, credential ID, assertion, private subject와 session reference를 API/UI/log에 노출하지 않는다.
