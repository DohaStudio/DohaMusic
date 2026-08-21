# Local Operator Authentication 운영 상태

> 문서 상태: [Foundation only / 운영 비활성]
> 최종 수정일: 2026-08-21
> 관련 문서: [Architecture](../03-architecture/local-operator-authentication.md), [Security Authority](../09-security/reviewer-authentication-deployment-authority.md)

현재 production config, Windows adapter, credential registration, governance UI와 real operator가 없으므로 local operator authentication은 운영할 수 없다. 일반 DohaMusic startup에는 login을 추가하지 않으며 privileged review action도 아직 연결하지 않는다.

```yaml
LOCAL_OPERATOR_AUTH_SELECTED: true
LOCAL_OPERATOR_AUTH_CONFIGURED: false
LOCAL_OPERATOR_AUTH_OPERATIONAL: false
CONCRETE_OS_ADAPTER_IMPLEMENTED: false
REAL_LOCAL_OPERATOR_IDENTITY_COUNT: 0
REAL_AUTHENTICATION_SESSION_COUNT: 0
```

현재 허용되는 검증은 test-only Fake provider를 직접 사용하는 contract test뿐이다.

```powershell
python -m pytest -q backend/tests/test_local_operator_authentication.py
```

Fake provider를 application factory, runtime config, governance UI 또는 production bootstrap에 주입하지 않는다. Windows username, environment `USERNAME`, `getpass.getuser()`, `os.getlogin()`, localhost와 process token 조회만으로 authenticated 상태를 만들지 않는다.

Future adapter 운영 전에는 다음을 모두 검증한다.

1. 지원 Windows와 user-verifying platform authenticator availability
2. credential provisioning·recovery·disable·revoke owner와 audit
3. one-time challenge, user verification, session binding, freshness와 expiry
4. credential metadata/private material 저장, backup과 compromise response
5. safe error translation과 username·credential ID·assertion·private subject log 0
6. Fake/unsupported/unavailable adapter production 차단

이번 문서는 실제 credential 생성, OS API 호출, secret store write 또는 reviewer activation 절차를 제공하지 않는다.
