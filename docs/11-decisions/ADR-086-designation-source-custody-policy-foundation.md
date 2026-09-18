# ADR-086: Designation Private Source Custody Policy Verification Foundation

> 상태: [최소 policy mechanics 구현·로컬 Gate PASS; 별도 Draft 대상·운영 비활성]
> 작성일·최종 수정일: 2026-09-19
> 기준 develop: `702eab36ecd56eac8f47e6664d06e94dde64d6a5` (#172 squash merge)
> 관련 PR: 이 Foundation의 별도 develop 대상 Draft PR
> 관련: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-077](ADR-077-bootstrap-issuance-integrity-verifier-foundation.md), [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-080](ADR-080-private-admission-currentness-handoff-contract.md), [ADR-081](ADR-081-provider-witness-lifetime-foundation.md), [ADR-082](ADR-082-windows-ceremony-serialization-foundation.md), [ADR-083](ADR-083-private-pin-facts-reader-foundation.md), [ADR-084](ADR-084-designation-provenance-reader-input-contract.md), [ADR-085](ADR-085-designation-record-snapshot-foundation.md), [검증](../10-operations/designation-source-custody-validation.md)

## 배경·최소 unit·선택 이유

#172의 raw snapshot은 immutable record byte digest와 original live pin/lease/witness를 대조하지만 private source의 owner/DACL과 independently provisioned object identity는 확인하지 않는다. 가장 가까운 미검증 입력 중 **C의 작은 custody policy/source verification mechanics**를 선택한다. A의 human provenance/full reader와 B의 authoritative designation currentness는 independently authenticated acceptance/revocation source가 필요하다. possession도 designated identity가 먼저 필요하다. 이 PR은 그런 proof를 public JSON/서명/OS SID로 추측하지 않는다.

새 signing root, 의무 signed designation, legal human 판정 또는 새로운 root role을 정하지 않는다. 기존 ADR-084가 구현 PR에 맡긴 concrete ACL/identity mechanism만 제한된 Windows profile로 검증한다. 서면 self-designation과 독립 human 대조는 ADR-076 그대로다. 이 policy는 human designation/initializer delegation의 증거가 아니므로 실제 외부 ceremony 없이 disposable infrastructure로 검증할 수 있다.

## 결정·독립 policy 조건

`SourceCustodyPolicy`는 **공개 비교 조건이며 permission DTO가 아니다**. future reviewed composition이 independent provisioning에서 확인한 root와 record의 exact 64-bit volume/128-bit file ID, explicit owner SID, approved custody SID set와 exact binary DACL을 고정 주입해야 한다. request/env/config/app DB/pin/record에서 policy를 auto-discover하거나 읽은 descriptor를 스스로 trust-enroll하는 production API/factory는 없다. 그 독립 provisioning/human 연결 자체는 아직 미구현이다. 테스트만 disposable object에서 test expectations를 준비한다.

root/record identity는 exact native tuple/int/bytes, nonzero volume/file ID다. bool/float/custom equality/hash/subclass는 deny한다. SID는 bounded exact bytes의 revision 1, NT authority account/domain shape 또는 service SID shape, explicitly approved SYSTEM에 한정한다. Everyone, Users, Authenticated Users, Administrators, Creator Owner 등 broad built-in identities는 이 profile로 승인하지 않는다. account-shaped SID가 human/user/group인지 이 codec가 판정하지 않으며 approved SID mapping은 독립 composition 책임이다. SYSTEM도 자동 추가하지 않는다.

binary ACL revision 2, 최대 4096 bytes/16 explicit unique ACCESS_ALLOWED ACE, ACE flags 0, bounded known nonzero file access masks, exact size/count/approved SID membership를 요구한다. inherited/deny/object/callback/conditional/unknown ACE, generic/MAXIMUM_ALLOWED/unknown masks, null/empty/ambiguous/trailing bytes는 deny다. 이는 Windows 전체 ACL의 general authorization evaluator가 아니라 deliberately narrow immutable policy profile다. 지원되지 않는 합법 ACL도 deny하며 canonicalization/permission 확대/자동 ACL rewrite를 하지 않는다.

## Native read·snapshot/handoff

`_CustodyDesignationRecordFiles`는 fixed `designation-record-v1.txt`만 연다. ADR-083의 each ancestor/leaf OPEN_REPARSE_POINT, resolved local DOS path/disk/directory, 128-bit identity, one hardlink, bounded same-handle read/count/size recheck, no write/delete sharing와 retained failed file cleanup을 유지한다. 기존 helper에 internal READ_CONTROL opt-in만 추가하고 기본 pin/raw snapshot transport access는 그대로다. caller-selectable filename이나 fallback factory는 없다.

같은 열린 root/record handle에서 owner/DACL을 읽는다. [GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)의 handle-based descriptor와 READ_CONTROL을 사용하며 path를 다시 resolve해서 ACL을 읽지 않는다. descriptor/ACL/SID validity, revision 1, present non-null DACL, DACL_PROTECTED, non-defaulted owner/DACL과 exact expected owner/DACL bytes를 대조한다. group/SACL/mandatory integrity label의 general evaluation은 하지 않는다. 이들을 포함한 privileged compromise 방어를 주장하지 않는다.

pin context 안의 raw snapshot composition에 optional explicit custody policy 경로를 추가한다. **policy가 없는 기존 경로는 기존 non-authorizing raw mechanics일 뿐이며 authority fallback이 아니다.** policy 경로도 actual human provenance/provisioning/eligibility가 없으므로 authority가 아니다. 두 경로 모두 production ports unavailable다. 새로운 provisioning/currentness/admission witness를 발급하거나 ADR-081 registration을 호출하지 않는다.

record read 전후 root/record identity·descriptor를 검사하고 original live record handle과 pin/lease/caller Session/root transaction을 유지한다. `_require_current_snapshot`에서 original lease/thread/transaction 검증 뒤 같은 held handle의 identity/owner/DACL을 fresh 재검사한다. 변경/누락/API error/cleanup uncertainty는 whole snapshot/native lease/witness를 permanent invalidate한다. source를 old matching ACL/bytes로 복원해도 same snapshot/lease는 재활성화하지 않는다. 원래 OS lock과 caller transaction/explicit owning-thread release는 보존한다.

## TOCTOU·cleanup·직접 재현한 결함

write/delete sharing denial로 ordinary rewrite/rename/replacement/hardlink/reparse transport를 차단한다. Windows DACL 변경은 share flags만으로 막힌다고 가정하지 않고 handoff 때 재검사한다. 별도 thread의 ACL 변경/복원도 negative regression이다. approved custodian 또는 privileged actor가 ACL을 바꿨다가 두 관측 사이에 정확히 되돌린 transient mutation, existing writable mapping, malicious process/ancestor privileged replacement, full private store/journal clone/rollback을 완전히 탐지하는 것은 아니다. 원래 ADR-076 trusted process/private boundary와 cooperating serialization writer 전제는 유지한다. descriptor query 자체도 atomic mutation lock이 아니다.

새 descriptor cleanup에서 LocalFree 실패 반환값은 보존했으나 OSError 예외에는 포인터 ownership을 잃는 결함을 injection regression으로 직접 재현했다(1 passed/1 failed). 해제 **전에** retained ownership을 등록하고 성공 확인 뒤에만 제거하도록 수정했다. 실패 반환·예외·재실패 모두 deny/retain하며 explicit cleanup 성공 전 fresh source snapshot을 차단한다. file handles의 original quarantine와 OS lease reservations를 없애지 않는다. read-only production source checker는 SetFileSecurity/ACL 변경/provision/write/key API를 제공하지 않는다. tests만 isolated disposable root와 leaf의 owner/DACL을 설정한다.

#173의 최초 Windows CI는 elevated runner의 default owner가 Administrators여서 fixture가 policy 준비 단계에서 거부되는 결함을 발견했다. default owner를 승인 계정으로 추론하지 않고 [OpenProcessToken](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocesstoken)의 TOKEN_QUERY/TokenUser로 선택한 disposable fixture 계정을 사용한다. owner가 다를 때만 임시 object의 owner를 설정하고 실제 root/leaf owner를 독립 재조회한다. 이미 같은 owner인 object는 불필요한 WRITE_OWNER 요청 없이 DACL만 설정한다. default account/Administrators의 두 경우를 회귀 검증하며 production SID profile·broad built-in 거부·human designation 경계는 변경하지 않는다. OS token 계정은 실제 initializer/Custodian credential이 아니다.

수정 CI는 runneradmin의 TokenUser 자체가 RID 500인 built-in Administrator임을 추가 확인했다. 이 profile의 account RID 하한 1000은 그대로 유지하고 RID 500 negative를 추가한다. Windows CI의 격리된 hosted VM에서만 random disposable 비관리자 계정(Users group)을 만들어 동일 native pytest 6개 파일을 실행한다. account SID 하한 확인·명시 exit-code 전파·실패 시 finally account 제거를 요구하며 password는 메모리 안의 test-only 난수이고 출력/Git에 넣지 않는다. 계정은 실제 Custodian/initializer 또는 production credential이 아니다. 사용자 PC·actual store·production account 변경은 없다. 기존 3개 required job과 assertion/Gate/전체 native coverage는 그대로다.

## 대안·장단점·영향·migration

ACL exists/OS administrator/CLI account를 designation authority로 삼는 대안과 descriptor self-pinning, signed approval로 custody/provenance를 승인하는 대안은 기각한다. full A+B/currentness/admission/possession을 한 PR에 묶지 않는다. 또 다른 docs-only input 계약을 반복하는 대신 이미 ADR-084가 허용한 concrete custody comparison을 실행한다.

장점은 actual native object/ACL substitution와 handoff revalidation을 작은 executable boundary로 검증하는 것이다. 비용은 좁은 non-inherited exact ACL profile, 고정 independently provisioned object identity와 operational policy provisioning dependency다. record replacement/rotation은 새 independent policy와 새 attempt가 필요하며 reader가 자동 수용하지 않는다.

app schema/migration/external journal v1 변경 0, Alembic `20260918_0037` single head·Phase/DoD 진행률 유지다. Repository commit()/rollback() 0과 caller-owned Session을 보존하고 source/snapshot helpers SQL/flush/commit/rollback/write/hidden retry 0이다. Worker/Runtime, Rights Writer/Adapter, authentication, Principal registry/binding, claim/seal, Recovery/Transfer/API/Frontend는 non-goal이다. 실제 key/credential/designation/approval/ceremony/user DB/Provider 접근·발급 0이다.

## 검증·다음 dependency·재검토

실제 실행 수치는 [검증 보고서](../10-operations/designation-source-custody-validation.md)에만 기록한다. Linux에서는 unsupported Windows source를 deny하고 native 성공을 가장하지 않는다. existing snapshot/pin/witness/Global mutex/process crash/journal CAS/Auth/Rights/Completion 회귀를 유지한다. Windows required step에 새 tests를 추가하며 기존 3개 CI Gate를 완화하지 않는다.

다음은 independent designation/provisioning authenticity·approved custody policy의 initializer provenance 연결 및 authoritative acceptance/revocation/complete membership source다. 그 뒤 fresh journal/history·pin eligibility/possession/complete currentness, durable admission와 same-event pin installer다. source policy/ACL/file identity 자체가 위 사실들을 증명한다고 해석할 수 없다. independent source의 기술 선택은 후속 reviewed implementation이고 실제 human designation/새 trust root/mandatory signature/강화 anti-rollback/법적 의미 변경에는 별도 사용자 Decision이 필요하다. 새 PR은 OPEN/Draft로 종료하며 Ready/merge/source 삭제하지 않는다.
