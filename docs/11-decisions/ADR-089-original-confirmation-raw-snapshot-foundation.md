# ADR-089: Original Confirmation Raw Snapshot Foundation

> 상태: [채택 — #176 merged; 운영 비활성]
> 작성일·최종 수정일: 2026-09-19
> 기준 develop: `3ae77bda08c3661a72d2f3c2052f027fc54b7db1` (#175 squash merge)
> 관련 PR: [#176 merged](https://github.com/DohaStudio/DohaMusic/pull/176); 다음 [ADR-090 canonical payload boundary](ADR-090-original-confirmation-canonical-payload-foundation.md)
> 관련: [ADR-087](ADR-087-custody-policy-provisioning-initializer-provenance-contract.md), [ADR-088](ADR-088-initializer-provenance-action-binding-foundation.md), [ADR-084](ADR-084-designation-provenance-reader-input-contract.md), [ADR-086](ADR-086-designation-source-custody-policy-foundation.md), [검증](../10-operations/original-confirmation-snapshot-validation.md)

## 배경·가장 작은 선택·대안

#175 strict public binding comparison은 merged지만 original confirmation의 authenticated source와 authoritative current-lineage store는 없다. 이번 선택은 사용자 후보 C, **A/B reader에 직접 필요한 held raw original-confirmation snapshot mechanics**다. 실제 code와 native negative tests를 구현하며 새 Contract만 반복하지 않는다. A의 metadata/boolean callback을 authentication으로 쓰거나 B의 caller historical ACTIVE tuple을 current pointer로 승격하는 대안은 기각한다. Optional signed fixture의 verifier를 새 trust root로 추측하거나 ADR-076/084/087의 unsigned original acceptance를 mandatory signature로 바꾸지 않는다.

## 구현 결정·strict binding handoff

`confirmation_snapshot._OriginalConfirmationSnapshots`는 명시 주입된 동일 pin reader/designation provider/root 및 separate expected confirmation custody policy만 받는다. 고정 파일은 `original-confirmation-v1.txt`다. Root native identity/owner SID/approved SID set/exact DACL은 held designation policy와 같고 original confirmation leaf native identity는 별도이며 designation leaf 재사용은 deny한다. policy를 실제 관측 descriptor에서 자동 학습하지 않는다.

`_open_snapshot`은 기존 original live pin facts와 custody-policy 경로의 held designation snapshot 안에서만 동작한다. Canonical strict public action/policy/confirmation/pin 및 complete bounded ACTIVE-head history를 비교하고 original confirmation digest를 exact bytes로 대조한다. UTF-8 strict, nonempty/nonwhitespace, BOM/NUL 거부와 1 MiB 원래 transport cap을 적용한다. Raw 외부 bytes를 JCS/Unicode normalization하거나 signature/payload로 해석하지 않는다. signed/unsigned record 둘 다 raw 대상일 뿐 이 unit은 signature verification/issuer authentication을 하지 않는다.

결과는 원래 provider registry identity의 non-exportable **raw snapshot handle**이며 authenticated provenance observation/ProvisioningWitness/CurrentnessWitness/CommittedAdmissionWitness/admission permission이 아니다. Currentness registry mint는 호출하지 않는다. Native owning process/thread/original OS lease/caller Session/root SessionTransaction/complete scopes의 기존 checks를 유지하고 action digest/full public history와 원래 held source identities를 연결한다. Copied pin/foreign designation/forged·copied handle/public dict 또는 True로 original registry를 대체하지 않는다.

`_require_unchanged`는 independently fresh-read되어야 하는 public action/history expectations를 받고 held pin/designation/custody/lease/transaction을 재검사한다. 공유 custody helper의 bounded same-handle seek/read는 original designation 및 confirmation bytes를 다시 읽어 full exact digest를 대조한다. Path를 다시 open해 latest file을 고르거나 cached bytes만 비교하지 않는다. action/provenance/initializer/policy/manifest/revision/predecessor/terminal/history/anchor/lease/transaction/ACL·owner/identity/byte/API mismatch가 관측되면 raw transport와 원래 handle/lease witness usability를 permanent abandon한다. Matching 값/API를 복원해도 old handle은 거절한다.

## Authentication/currentness/authority와 resource 경계

원래 lineage binding은 public dataclass 참조에만 의존하지 않는다. 최초 open에서 anchor/installation/source/statuses 및 전체 action의 strict comparison digest를 immutable primitive tuple로 복사하고 handoff의 fresh tuple과 대조한다. Frozen 객체의 제자리 변경으로 original anchor/history를 재연결할 수 없으며 이 cached equality key도 source authentication/currentness proof가 아니다.

Live file/ACL/digest/action equality는 human 수락/명시 initializer 위임/actual installed action의 independent authenticity가 아니다. Original confirmation을 발급·검증한 실제 human이나 source를 지정하지 않으며 authenticity mechanism/verifier/서명 wire/current-pointer/private-store writer는 미구현이다. Caller가 fresh라고 제출한 history는 아직 public condition이지 실제 authoritative fresh reader의 proof가 아니다. future reviewed adapter가 independent source/currentness를 검증하기 전 production path는 unconditional unavailable다. Snapshot handle 생성 자체로 partial provenance/admission witness를 만들지 않는다.

Global complete sorted ceremony mutexes → app guards → external CAS와 kernel acquisition 전 independent manifest 검증 precondition은 기존 ADR 그대로다. Context 종료/거절/restart/lease release/transaction replacement는 old handles를 무효화한다. Caller는 필요한 held evidence context 안에서 자신의 commit/rollback을 끝내고 original thread에서 explicit native lease release한다. Reader commit/rollback/SQL/hidden retry/자동 GC cleanup은 0이다.

Native source handles는 원래 transport의 read-only/write·delete-sharing denial/ancestor·reparse·hardlink/physical ID/owner/protected DACL checks 및 CloseHandle/LocalFree retained ownership을 보존한다. CloseHandle 예외도 FALSE와 동일하게 quarantine을 유지하며 verified cleanup 전 transport 새 snapshot은 deny한다. Retry close가 실패하면 원래 handles/list를 유지한다. Dispose 성공 전 실제 OS cleanup을 했다고 주장하지 않는다. Shared helper의 새 reread 실패도 해당 held transport를 permanently invalid로 유지한다.

두 관측 사이 privileged byte/ACL 복원, malicious process와 entire store/key/journal clone·rollback의 완전 탐지를 주장하지 않는다. 실제 writable mapping 공격은 이 Windows 환경에서 초기 open부터 sharing denial됐으며 그 Gate를 완화하지 않는다. Same-size changed read response의 관측 후 abandonment는 별도 injected API test로 검증한다. 실제 file tamper 완전 방어/source authentication으로 그 결과를 확대하지 않는다.

## Migration·검증·장단점·후속·재검토

새 module/test 각 하나, composition에 직접 필요한 designation partial-live check 및 공유 custody reread, 재현된 기존 Windows transport quarantine 방어만 변경한다. Windows CI의 기존 isolated non-admin fixture step에는 새 confirmation/strict-binding test 두 파일만 추가한다. User PC local account를 생성하지 않고 실제 governance/key/credential/ceremony/User DB/Provider는 사용하지 않는다. Schema/migration/ports/runtime 0, Alembic `20260918_0037` single head/external journal v1/Phase 6 DoD 14/14·다른 진행률 보존이다.

장점은 실제 original input의 transport/held binding/stale handle/resource failure를 작은 independently testable unit으로 검증하는 것이다. 비용은 Windows-only native mechanics와 여전히 미증명인 source authentication/current lineage reader다. 다음 dependency는 원래 independent confirmation provenance의 authenticity mechanism 및 live authoritative policy lineage reader/transaction owner다. Disposable fixture PASS는 operational 승인으로 승격하지 않는다. 새로운 issuer/trust root/mandatory signature/human legal 판단/Recovery authority가 필요하면 별도 사용자 Decision으로 재검토한다. 새 PR은 Draft까지만 생성하고 Ready/merge/source 삭제하지 않는다.
