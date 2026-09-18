# ADR-085: Designation Record Snapshot Mechanics Foundation

> 상태: [채택 — #172 merged; 최소 snapshot mechanics, 실제 provenance/custody authority 미구현·운영 비활성]
> 작성일·최종 수정일: 2026-09-19
> 기준 develop: `bebf693fb41358abdddaf5d4110686323222cf2b` (#170 squash merge)
> 현재 후속: [ADR-086 custody policy mechanics](ADR-086-designation-source-custody-policy-foundation.md); 아래 본문은 #172 구현 시점의 범위·선택 이력이다.
> 관련: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-080](ADR-080-private-admission-currentness-handoff-contract.md), [ADR-081](ADR-081-provider-witness-lifetime-foundation.md), [ADR-082](ADR-082-windows-ceremony-serialization-foundation.md), [ADR-083](ADR-083-private-pin-facts-reader-foundation.md), [ADR-084](ADR-084-designation-provenance-reader-input-contract.md), [검증](../10-operations/designation-record-snapshot-validation.md)

## 선택·대안·원래 authority

#170 Contract를 exact-head CI/Final Validation 뒤 squash merge했다. full A reader는 독립 human designation/provisioning/eligibility source와 ACL/authenticity mechanism이 아직 없고 signature fixture로 대체할 수 없다. 따라서 B의 작은 직접 선행 단위인 **fixed raw designation record snapshot과 pin/currentness lifetime 대조 mechanics**를 실제 구현한다. 새 Contract만 반복하거나 metadata-only A를 구현하는 대안은 기각한다.

이 구현은 human acceptance/initializer delegation/governance authenticity/ACL custody/current designation status를 확인하지 않는다. designation document exists, raw digest matches, snapshot handle exists, helper currentness lifetime comparison passes는 모두 authority가 아니다. 독립 checks를 마친 full provisioning observation/currentness/admission witness를 발급하지 않는다. production ports는 기존 unconditional unavailable다. signed governance wire/mandatory signature/새 root를 만들지 않고 ADR-076의 written self-designation 경계를 유지한다.

## 고정 source·raw profile

internal `_DesignationRecordSnapshots`는 future reviewed composition이 고정 root와 exact original `_PrivatePinFactsReader`를 주입한다. request/env/config에서 root/provider/file을 선택하는 factory가 없다. 파일명은 fixed `designation-record-v1.txt`; pin 파일명은 그대로다. shared Win32 primitive의 internal fixed-name subclass만 재사용하며 caller-selectable filename parameter를 추가하지 않는다.

technical transport profile은 1..1 MiB의 strict UTF-8 nonblank text다. BOM/NUL/invalid UTF-8은 deny한다. 원래 bytes의 SHA-256을 live pin binding의 designation_record_digest와 비교하고 JCS/Unicode/line-ending normalization을 하지 않는다. 이 profile은 signed designation wire/accepted semantic JSON schema가 아니며 human document 내용을 parse해 authorization을 반환하지 않는다. JSON-like text의 key/status/verified 필드를 authority로 해석하지 않는다. 기존 외부 record digest를 재정의하지 않으며, 해당 exact-byte profile과 독립 designation source가 연결된 deployment만 future adapter가 사용할 수 있다. 다른 representation은 자동 변환하지 않고 별도 reviewed adapter Gate다.

ADR-083 local absolute DOS/ASCII path subset, each ancestor/leaf OPEN_REPARSE_POINT, disk/directory/reparse/resolved path 및 128-bit volume/file identity, single hardlink, bounded same-handle size/count recheck·ancestor identity와 no write/delete sharing을 그대로 사용한다. 모든 handles를 snapshot context까지 hold하고 cleanup 실패는 retained quarantine/explicit cleanup이다. Windows unsupported/error/missing/substituted source는 deny이며 POSIX/Fake/public repository/cached fallback이 없다.

이 transport는 source의 custody/ACL 정책/initializer provenance 자체를 증명하지 않는다. administrator·기존 writable mapping·privileged clone/rollback·비협력 writer에 대한 완전한 보장을 추가하지 않는다. 실제 operational root/file/key/credential을 provision하거나 읽지 않는다.

## Live pin·opaque snapshot·currentness

pin reader에 원래 decoded facts의 strong identity와 lease/Session/binding을 live yield 동안만 기록하는 internal registry를 추가했다. `_require_open_facts`는 copy/deepcopy/caller-constructed/public DTO/원래지만 종료된 facts를 거절한다. 이것은 원래 file context가 열려 있다는 mechanics 확인이지 private pin provenance proof가 아니다. context exit에는 registry entry를 제거한다.

record source는 original opaque native lease를 먼저 bind한 뒤 original live pin context와 caller Session/root transaction/scope를 I/O 전후 재검증한다. matching bytes에서 opaque provider-owned snapshot handle을 발급하지만 full ADR-084 provisioning observation은 아니다. handle은 original registry membership/object identity를 요구하고 copy/pickle/export/import API가 없다. context 밖에 raw record/authority fields를 export하지 않는다.

`_require_current_snapshot`는 original live pin/native lease, exact full CurrentnessBinding 및 ADR-081 original attempt/witness/lease/SessionTransaction/exact scope의 lifetime comparison을 요구한다. witness를 이 module이 등록하지 않는다. 외부 reviewed adapter의 independently issued currentness witness가 여전히 필요하며 helper equality/lifetime 통과는 그 independent verification 또는 current permission이 아니다. 테스트 witness는 placeholder mechanics fixture다. production composition unavailable를 유지한다.

record denial/malformed input/currentness mismatch/context exit/consumer exception은 snapshot을 폐기하고 기존 witness usability뿐 아니라 original native lease도 permanent invalid로 만든다. OS handles/locks는 caller transaction 종료 뒤 original-thread explicit release까지 유지한다. 반환한 old facts나 matching source를 복원해도 same lease로 snapshot을 재발급하지 않는다. foreign provider handle로 원래 snapshot을 폐기하지 않는다. terminal transaction/실제 admission 결합은 후속이며 snapshot을 먼저 닫고 old evidence를 재사용하지 않는다.

## 재현·수정·검증

초기 새 implementation에서 record context 종료 또는 digest mismatch 거절 뒤 native lease는 계속 valid여서 snapshot handle을 다시 발급할 수 있었다. witness는 이미 invalid였지만 one-attempt lease 경계를 만족하지 못했다. 두 negative regressions로 실제 재현한 뒤 original native lease record의 permanent invalidation을 추가했다. native cleanup ownership이나 caller transaction을 끝내지 않는다.

새 tests는 live/frozen opaque identity, copy/pickle/foreign provider/public substitution, malformed/missing/oversize/raw digest mismatch, currentness binding/revision/scope/attempt/witness mismatch, rejection/exit 후 restored source·lease reuse, source hardlink/replacement/write/rename, native partial/error read, cleanup failure/retained handles 및 transaction 교체/consumer exception을 검증한다. shared ancestor junction/concurrent read/process/crash/serialization 및 private pin tests도 focused/direct에 포함한다. Linux는 unsupported-platform denial만 실행하고 native Windows 성공을 가장하지 않는다.

## Schema·영향·후속·재검토

app migration/schema/external journal v1 변경 0, Alembic `20260918_0037` single head·Repository commit()/rollback() 0·기존 Phase/DoD를 보존한다. snapshot/pin registry는 ephemeral process-local mechanics이며 SQL/flush/commit/rollback/hidden retry·journal/pin write·production factory/port 변경 0이다. 실제 governance/approval/designation/key/credential/ceremony/user DB/Provider 접근·생성 0이다.

장점은 작은 원본 record source·sealed snapshot·lifetime boundary를 실제 공격 테스트로 검증한 것이다. 비용은 의도적으로 제한된 text/path profile과 아직 없는 independent authenticity/ACL/human/eligibility checks다. 다음은 reviewed independent designation/provisioning source·custody/authenticity/eligibility 검증이고 이후 fresh journal/history·authoritative manifest·possession/complete currentness 및 durable admission/pin installer다. Claim/Auth/Principal/binding/Recovery/Transfer/Rights Writer/Adapter/Worker/Runtime/API/Frontend는 non-goal이다. root/법적 human 판단/mandatory signed designation/강화 anti-rollback을 바꾸려면 별도 Decision이 필요하다. 새 PR은 OPEN/Draft에서 종료하고 Ready/merge/source 삭제하지 않는다.
