# ADR-082: Windows Ceremony Serialization Foundation

> 상태: [채택 — #168 merged; 최소 OS mechanics, 운영 비활성]
> 작성일·최종 수정일: 2026-09-18
> 기준 develop: `2af6f7e8de7f42ea7f1758924bafcdcb25ddf56f` (#167 squash merge)
> 관련 문서: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-080](ADR-080-private-admission-currentness-handoff-contract.md), [ADR-081](ADR-081-provider-witness-lifetime-foundation.md), [검증](../10-operations/windows-ceremony-serialization-validation.md)

## 배경·선택·대안

#167 witness lifetime helper를 exact-head required CI 3개 SUCCESS·Final Validation 후 expected-head squash merge했다. private evidence store/independent provenance loader는 아직 source에 없다. 그 기술·운영 custody까지 추측하며 reader를 발급하는 A보다 **B의 Windows cross-process exclusion mechanics**가 작은 coherent dependency다. 실제 platform primitive를 구현하고 isolated processes로 검증하되 ceremony/admission provider 전체로 노출하지 않는다.

RLock/process-only registry, SQLite write lock, 파일 존재/PID/mtime 기반 stale lock, session-local `Local` namespace는 기각한다. 순수 Contract 반복 대신 Windows `Global` named mutex를 사용한다. 다른 platform은 fail closed하며 POSIX/file/Fake fallback을 추가하지 않는다. Linux CI는 unsupported-platform 거절과 순수 manifest 검사만 검증하고, Windows CI의 별도 step이 실제 Win32/thread/process/crash 및 witness regression을 실행한다. 기존 필수 job/Gate는 제거·완화하지 않는다.

## Primitive·이름·보안 한계

[Microsoft CreateMutexW](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createmutexw), [WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject), [kernel namespaces](https://learn.microsoft.com/en-us/windows/win32/termserv/kernel-object-namespaces)의 계약을 따른다. non-inheritable handle, initial owner false, zero-timeout wait, owning-thread release/CloseHandle를 사용한다. 이름은 fixed domain + exact canonical `(installation, workspace, existing owner)` UUID tuple의 SHA-256이다. hostname/user/path를 installation identity로 사용하지 않는다. 모든 scope를 lexical tuple 순서로 획득하고 최대 4096·중복/비정렬/비-native primitive는 거부한다.

입력 scopes는 요청 조건이지 complete manifest/installation provenance가 아니다. future trusted adapter가 authoritative complete set과 독립 identity evidence를 먼저 검증해야 한다. scope discovery 변경은 abandon 대상이고 일부 lock으로 계속하지 않는다. 이름/lock 획득/공개 DTO는 authorization이 아니다. 파일을 사용하지 않아 symlink/path replacement read surface가 없지만 private reader의 향후 TOCTOU 검증을 대체하지 않는다.

default creator-token DACL을 OS mechanics에만 사용한다. 다른 token의 access denied/object-type collision/busy/unsupported는 generic denial이며 ACL 변경·privilege 확대·OS admin→governance 승격을 하지 않는다. malicious namespace squatting은 availability 공격이 가능하고 mutex는 malicious/non-cooperating writer를 막지 못한다. 생산 deployment security descriptor/custody/composition은 별도 review 대상이며 이 adapter는 production factory/port에 연결하지 않는다. 새 OS trust root나 cross-user admission authority를 만들지 않는다.

## Lease·witness·caller transaction

`_WindowsCeremonySerialization`은 internal component다. opaque handle은 기존 ADR-081 identity registry를 사용하며 copy/pickle/forged identity/provider substitution을 허용하지 않는다. lease는 original provider, pid/native owning thread, sorted scopes, Session/root SessionTransaction에 bind한다. caller는 app guard/SQL write 전에 root transaction을 시작하고 OS locks를 얻으며, commit/rollback/close가 끝난 후 원래 owning thread에서 explicit release한다. root transaction 시작 자체는 DB guard 획득이 아니다. global order: sorted ceremony mutexes → app guards → external CAS.

live 검사에서 transaction/scope mismatch 또는 savepoint 사용을 관측하면 lease를 영구 invalid로 하고 ADR-081 `_release_lease`로 attempt/witness도 무효화한다. 조기 release도 invalid 처리하지만 caller transaction이 active면 실제 OS lock은 해제하지 않는다. 원래 transaction 종료 후 cleanup만 허용한다. 새 transaction/옛 matching scope로 재활성화하지 않는다. release 후 새 lease에는 새 attempt와 fresh independent checks가 필요하다. 다른 thread/provider/forged identity는 native handle에 접근하지 못한다.

Win32의 same-thread recursive mutex acquisition은 허용하지 않는다. module-wide reservation은 모든 내부 instance의 겹치는 acquire를 거부하는 보조 bookkeeping이다. process 간 exclusion은 실제 OS mutex가 제공한다. Session을 concurrent threads에서 공유하는 adapter, await/thread migration 및 async ceremony는 미지원이며 production composition도 없다. caller는 `try/finally`로 transaction 종료/release 및 실패 acquisition cleanup을 수행해야 한다. 자동 commit/rollback/SQL/hidden retry/GC finalizer를 두지 않는다.

## Failure·crash·cleanup

partial multi-scope acquire 실패는 역순 cleanup한다. release/CloseHandle failure면 native handle·ownership 상태와 reservations를 retained quarantine에 유지한다. explicit original-owner `_cleanup_failed_acquisitions()`는 cleanup만 하며 acquisition/admission을 재시도하지 않는다. ReleaseMutex 성공/CloseHandle 실패 뒤 retry는 close만 수행하여 recursive count를 두 번 감소시키지 않는다. cleanup 완료 전 해당 scope를 새 clean lease로 반환하지 않는다. unresolved OS cleanup은 fail closed이며 성공을 숨기지 않는다.

WAIT_ABANDONED는 OS ownership을 얻었더라도 clean lease를 발급하지 않는다. 얻은 ownership/handle을 cleanup하고 attempt를 거부한다. process 종료로 모든 handles가 사라지면 named object 자체가 소멸할 수 있어 영속 crash marker/anti-rollback proof라고 주장하지 않는다. 다음 fresh mechanical lock은 독립 durable HEAD/history/pin/provenance 전체를 다시 검증해야 하며 committed admission을 추론하지 않는다.

## Scope·schema·rollout·재검토

new source/test + Windows CI step 및 문서 한 unit이다. app migration/schema/external journal v1 변경 0, Alembic `20260918_0037` single head와 Repository commit/rollback 0을 보존한다. actual keys/credentials/approval/governance/bootstrap ceremony/production User DB/Provider 접근·생성 0. mutex test는 random disposable namespace와 isolated child process만 사용한다.

production private evidence reader/currentness/admission/durable transaction owner/pin installer·Claim/principal/binding/Auth/Recovery/Transfer/Evidence/Rights Writer/Adapter/Worker/Runtime/API/Frontend는 미구현/unavailable다. mutex 및 witness mechanics PASS는 Private Admission PASS가 아니다. 다음은 reviewed independent private evidence source/readers 및 complete manifest/currentness verification이고 그 뒤 durable admission/pin handoff다. 생산 ACL/multi-host/platform/session migration/real provisioning 요구는 별도 review/Decision으로 재검토한다. 새 PR은 Draft에서 종료하며 Ready/merge/source 삭제하지 않는다. Phase/DoD 진행률은 변경하지 않는다.
