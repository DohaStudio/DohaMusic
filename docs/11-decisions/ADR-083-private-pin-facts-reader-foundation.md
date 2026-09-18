# ADR-083: Private Pin Facts Reader Foundation

> 상태: [최소 transport/comparison 구현·로컬 Gate PASS; 별도 Draft 대상, 운영 비활성]
> 작성일·최종 수정일: 2026-09-19
> 기준 develop: `fb10bc9367835b0d4a39837287a358fe6b46a1be` (#168 squash merge)
> 관련: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-080](ADR-080-private-admission-currentness-handoff-contract.md), [ADR-081](ADR-081-provider-witness-lifetime-foundation.md), [ADR-082](ADR-082-windows-ceremony-serialization-foundation.md), [검증](../10-operations/private-pin-facts-reader-validation.md)

## 선택과 범위

#168의 실제 Windows serialization을 병합했다. source에는 reviewed private custody store/independent provenance loader가 없다. 따라서 전체 A/B provider를 추정하지 않고 더 작은 A 선행 단위인 fixed private-boundary file의 read-only transport와 complete pin/manifest comparison을 구현한다. 문서만 추가하는 작업은 아니지만 **authoritative private evidence reader 또는 complete currentness verification 완료를 의미하지 않는다.**

기존 ADR의 trust root/authority를 바꾸지 않는다. public DTO를 private file에서 읽었다는 사실은 designation authenticity, custody, installation proof possession, authoritative journal freshness/history를 증명하지 않는다. `PinComparisonFacts`는 public immutable facts이며 constructor/equality/path/reader 성공으로 admission을 허가하지 않는다. production ports는 unconditional unavailable 그대로다. Writer/Authentication/Claim/binding/Adapter/Worker/Runtime 및 pin installer를 연결하지 않는다.

## 기술 codec와 comparison

고정 파일명 `pin-comparison-facts-v1.json`, technical schema `dohamusic/private-pin-comparison-facts/v1`을 사용한다. 기존 external journal v1 및 app schema를 바꾸지 않는다. 최대 1 MiB strict UTF-8 canonical RFC8785 JSON이며 duplicate/unknown/missing key, float/bool counter, unsafe integer, 과도한 depth/크기와 비정규 encoding을 거절한다.

정확한 top-level field는 `schema`, `installation_id`, `installation_proof_key_fingerprint`, `pin`, `designation_id`, `designation_record_digest`, `deployment_owner_ref`, `affected_scopes`, `root_key_id`, `root_fingerprint`, `root_public_key`, `status`, `domain`이다. pin은 기존 JournalHead의 6개 field 전부이며 scope는 installation/workspace/existing owner UUID 3개 전부다. 기존 CurrentnessBinding 검증과 complete sorted scope equality를 재사용한다. root public key는 canonical unpadded base64url 32 bytes다. ACTIVE/domain/identity/digest/pin counter/head/key/manifest 전부 externally supplied expectation과 일치해야 한다.

`binding.journal`은 외부 expectation에서 온다. 파일은 **pin만 공급**한다. 파일 내 journal, public repository/config fallback, cached last-good read는 없다. 전체 manifest의 authoritative completeness와 fresh journal/complete history는 별도 independent reader가 검증해야 한다. 이 비교는 그 검증을 대체하지 않는다.

## Win32 snapshot과 경계

root는 future reviewed composition이 직접 주입하는 고정 local DOS absolute ASCII path다. request/env/config factory는 없다. UNC/device/ADS/relative/dot segment/short alias/Unicode/reserved DOS/trailing dot·space/긴 path는 fail closed한다. 이는 의도적인 지원 subset이며 자동 경로 변환이나 POSIX/Fake fallback이 없다.

[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)의 OPEN_EXISTING/non-inheritable/FILE_SHARE_READ와 각 ancestor 및 leaf의 OPEN_REPARSE_POINT를 사용한다. 모든 ancestor handle을 hold하고 directory/disk type/reparse 여부 및 [resolved path](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)를 확인한다. leaf의 hardlink count는 정확히 1이어야 한다. ReFS의 64-bit ID 한계를 피하려고 FileIdInfo의 128-bit identity와 volume을 사용한다. 같은 handle에서 bounded read하고 size/count/identity 및 ancestor identity를 재확인한 뒤 context 종료까지 handle을 유지한다. write/delete sharing은 허용하지 않는다.

ACL/custody authenticity, administrator privilege, 기존 writable mapping, 비협력 privileged writer에 대한 불변성은 증명하지 않는다. root 선택·ACL 정책·독립 designation/provenance·fresh possession 검증은 future reviewed composition 책임이며 아직 미구현이다. 실제 operational private file/key/credential을 생성하거나 읽지 않는다. CloseHandle 실패는 잔여 handle을 quarantine에 보존하고 explicit cleanup으로만 해제한다.

## Lease·transaction·실패

original Windows provider의 opaque lease를 먼저 bind하고 caller Session/root transaction/scope를 I/O 전후 재검증한다. malformed expectation을 포함해 bind 이후 모든 거절/exception/context exit는 해당 lease의 witness usability를 영구 폐기한다. OS lock은 caller transaction 종료와 explicit original-thread release까지 유지한다. foreign/forged lease로 다른 provider witness를 폐기하지 않는다.

reader는 witness를 발급하지 않고 SQL execute/flush/commit/rollback을 호출하지 않는다. app Alembic single head `20260918_0037`, external journal v1, 기존 Phase/DoD 진행률을 보존한다. 실제 governance/designation/approval/key/credential/ceremony/user DB/Provider 접근은 0이다.

## 다음 dependency

reviewed private root custody와 independently authenticated designation/provenance reader → fresh authoritative journal/complete history 및 authoritative complete manifest → installation proof possession → explicit durable admission owner/same-event pin install/reconciliation 순서다. facts-only 성공을 이 chain의 authorization으로 확대하지 않는다.
