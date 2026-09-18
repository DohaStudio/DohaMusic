# ADR-084: Designation Provenance Reader Input / Snapshot Contract

> 상태: [채택 — #170 merged Contract; full provenance reader 미구현·운영 비활성]
> 작성일·최종 수정일: 2026-09-19
> 기준 develop: `688b5f77ad1fb17bb0356e884574171c73921c42` (#169 squash merge)
> 관련: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-077](ADR-077-bootstrap-issuance-integrity-verifier-foundation.md), [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-080](ADR-080-private-admission-currentness-handoff-contract.md), [ADR-081](ADR-081-provider-witness-lifetime-foundation.md), [ADR-082](ADR-082-windows-ceremony-serialization-foundation.md), [ADR-083](ADR-083-private-pin-facts-reader-foundation.md), [검증](../10-operations/designation-provenance-reader-contract-validation.md)

## 1. 가장 가까운 미증명 사실·선택

#169는 private-boundary file의 public comparison facts를 읽지만 그 파일을 **누가 어떤 외부 designation에 따라 provision했는지** 증명하지 않는다. source의 production ports는 unconditional unavailable다. ADR-076은 서면 self-designation·human 수락 및 initializer의 독립 채널 대조를 root assertion으로 인정한다. 지정 record를 반드시 별도 governance signing key의 서명 envelope라고 정하지 않았다. 현재 signed approval/lifecycle fixtures는 designation authenticity를 증명하는 fixture가 아니다.

따라서 A의 구현에 직접 필요한 E, **independent designation/provisioning source의 입력과 live snapshot handoff 계약** 하나를 선택한다. 새 CA/상위 signing root, root의 자기서명으로 자기 designation 승인, approval receipt 재사용을 가정하지 않는다. B의 fresh history reader는 이 provenance와 separately verified pin을 필요로 하고 C의 possession은 이미 designated identity가 먼저 필요하다. A+B+C 또는 durable admission 전체를 결합하지 않는다.

이 PR은 docs-only다. 계약의 검토와 기존 mechanics의 executable regression을 수행하며, 새로운 custody/provenance reader나 private authority input을 구현·검증했다고 주장하지 않는다. Contract 채택 이후의 infrastructure implementation은 disposable fixtures로 가능하므로 이번 작업에 실제 외부 ceremony는 필요하지 않다.

## 2. 원래 authority와 독립 source

기존 ADR-076 external designation/root assertion만 신뢰의 출발점이다. Product/Deployment Owner나 initializer의 실제 human을 이 ADR이 지정하지 않는다. OS administrator/token/파일 소유자/CLI 사용자/Workspace owner/key 보유자는 그 사실만으로 designated initializer가 아니다. ACL 검사는 custody mechanics일 뿐 designation을 생성하지 않는다.

future trusted composition은 ceremony에서 독립 확인한 designation record와 provisioning provenance를 유지하는 deployment-private source를 명시 주입해야 한다. 요청·application DB·approval/lifecycle artifact·pin file·환경 변수에서 source나 verifier를 자동 선택하지 않는다. trust store와 external journal은 app DB/backup과 독립 경계다. source의 authenticity와 custody 검증 없이 digest/ref가 일치하는 public JSON을 읽은 결과는 진단 값일 뿐이다.

원본 designation record의 immutable reference/digest는 보존한다. 검증 대상은 source가 보존한 exact immutable record bytes 및 그 bytes와 ceremony provenance의 연결이다. byte representation/digest 규칙과 source adapter의 authenticity·ACL/identity mechanism은 구현 PR에서 명시 검증해야 한다. 기존 wire의 digest를 재정의하거나 unspecified record를 JCS로 임의 정규화하지 않는다. 이를 정하지 못한 adapter는 unavailable이며 metadata-only 성공 adapter를 만들지 않는다.

## 3. Semantic input 계약 (새 wire/schema가 아님)

| 독립 확인 대상 | 반드시 대조할 연결 | 값만 일치할 때 남는 한계 |
|---|---|---|
| designation | immutable designation ID, deployment owner opaque ref, decision reference/digest, human 확인·명시 수락·initializer 위임 및 승인된 deployment 범위 | caller ref/digest/서명은 designation authenticity 아님 |
| provisioning | 위 designation record digest와 exact installation UUID/proof-public-key fingerprint, separately provisioned root key ID/raw public bytes/fingerprint, journal UUID, installed trust revision/admission digest | 파일/OS 사용자/hostname/path는 installation identity 아님 |
| affected membership | 승인된 deployment 범위에 속하는 complete exact installation/workspace/existing owner scope set와 manifest digest | caller list 또는 pin file의 scope set은 authoritative completeness 아님 |
| custody | reviewed private source instance/identity, immutable record identity, root 선택·ACL/접근 경계와 실제 provision한 initializer의 provenance 연결 | OS file identity/ACL가 human designation을 증명하지 않음 |
| designation eligibility | source의 fresh authoritative acceptance/revocation/supersession 확인과 동일 record lineage | 과거 valid signature/latest timestamp/ACTIVE root enum은 현재 designation 아님 |

값은 ADR-077/078/081의 canonical UUID/reference/hash/native string, exact safe int(bool/float 제외), exact raw public bytes, sorted unique complete scope 규칙을 따른다. malformed/custom equality/hash, unknown authority-bearing fields, duplicate/ambiguous designation identity 및 missing evidence는 deny다. machine artifact를 사용하는 adapter는 strict bounded encoding/duplicate/unknown field 거부 규칙을 구현 PR에서 고정해야 한다. 이 semantic 표를 새 accepted public JSON 또는 caller-constructible permission DTO로 구현하지 않는다.

Root key를 artifact 자체에서 받아 self-enroll하지 않는다. 이미 독립 provision한 public verifier의 raw bytes와 fingerprint를 검증한다. signed fixture의 issuer/signature를 확인하더라도 그 verifier가 독립 지정되었다는 provenance가 없으면 deny다. **unsigned 서면 designation을 인정한 ADR-076을 새 의무 signature/issuer trust root로 바꾸지 않는다.**

designation eligibility와 root lifecycle eligibility는 별개다. designation이 현재 accepted라도 journal의 terminal/revoked root는 deny이며 root가 ACTIVE라도 designation이 revoked/unknown이면 deny다. concrete designation status storage/wire는 아직 미구현이고 새 runtime enum을 선언하지 않는다.

## 4. Future internal read handoff·partial evidence

`open_designation_provenance(lease, caller_session, pin_conditions)`는 후속 내부 context 계약의 이름이며 **현재 Python API가 아니다**. provider는 원래 trusted source에서 independently authenticated record/provisioning/eligibility를 fresh 확인하고 위 exact binding을 대조한다. pin_conditions/CurrentnessBinding은 public 요청 조건이지 proof가 아니다.

결과는 original provider의 registry membership/object identity에 bind된 non-exportable partial provenance observation이다. public constructor, copy/pickle/JSON/DB receipt 재구성, boolean success callback/test Fake로 발급하지 않는다. provider instance/process/thread, one attempt, opaque original OS lease, caller Session/root SessionTransaction, complete affected scopes 및 실제 source snapshot/record identity를 bind한다. 이것은 `CurrentnessWitness`, `CommittedAdmissionWitness` 또는 admission permission이 아니다. ADR-081 currentness witness registration을 partial provenance 단계에서 호출하지 않는다.

Fresh journal/complete history·pin connection·designation/root eligibility·installation/Custodian possession 등 필요한 independent facts를 모두 확인한 reviewed adapter만 기존 handoff 계약에 따라 다음 narrow witness를 발급할 수 있다. root currentness 통과도 approval/assignment·principal/WebAuthn·Workspace owner/history/seal-first 및 Rights 권한을 대체하지 않는다. production ports는 구현·검증 전 unconditional unavailable다.

## 5. Snapshot·TOCTOU·실패

global order는 authoritative complete sorted ceremony scopes → application guards → external journal CAS다. 최초 scope discovery는 후보 set이며 kernel acquisition **전에** independent installation/scope provenance와 complete membership을 확인해야 한다(ADR-082 source의 선행 조건). 그렇게 확인한 complete set의 locks를 획득한 뒤 membership을 다시 fresh 확인한다. 누락/추가/manifest 변경이면 partial lock으로 계속하지 않고 전체 attempt를 abandon하고 독립 확인·새 complete acquisition부터 시작한다. timestamp latest, session-only lock, SQLite reader snapshot을 ceremony serialization로 대체하지 않는다.

실제 reader는 ADR-083 `_open_facts`의 live context **안에서** 다른 evidence와 결합해야 한다. 이 context 종료는 witness usability를 폐기하므로 반환된 PinComparisonFacts를 저장했다가 다음 admission에서 재사용할 수 없다. provenance context도 종료/exception/거절 때 partial observation을 영구 무효화해야 한다. revalidation에서 source/record/identity/head/manifest/transaction 변경을 발견한 attempt는 old matching 값으로 복구하지 않는다. provider restart/crash/lease release도 stale handles를 거절한다.

terminal action과 caller commit/rollback까지 필요한 모든 evidence snapshot/lease를 유지하고 action 직전 독립 fresh 상태를 다시 확인한다. current API를 composition으로 사용할 경우 caller가 context 내부에서 자신의 transaction을 완료한 뒤 snapshot을 닫고 원래 owning thread에서 OS lease를 release한다. reader가 caller Session을 commit/rollback하거나 hidden retry하지 않는다. snapshot을 먼저 닫았다면 old evidence로 commit 허가를 추론하지 않고 fresh attempt를 요구한다.

private file transport는 ADR-083의 각 ancestor/leaf reparse check·resolved path·same-handle bounded read·identity/size 확인·hardlink denial·write/delete sharing 차단 및 retained failed cleanup을 우회하지 않는다. source-specific custody adapter도 substitution/replacement/concurrent mutation을 검증해야 한다. 그 검증은 ACL 변경/기존 writable mapping/privileged compromise의 완전 방어를 주장하지 않는다. 전체 key/journal/private store의 privileged clone/rollback 한계는 ADR-076 그대로다.

## 6. 후속 implementation의 executable acceptance (이번 실행 결과 아님)

- 별도 disposable designation/provisioning fixture를 사용한다. 기존 signed approval/lifecycle fixture만으로 governance authenticity를 승인하지 않는다. signed fixture를 쓰면 disposable key와 independently injected test provenance가 필요하며 production Fake fallback은 없다.
- wrong installation/domain/journal/designation/owner/key/fingerprint/revision/record digest·부분 manifest·duplicate designation·stale/revoked/terminal state·불명 currentness·extra authority field·malformed encoding/duplicate JSON을 거절한다.
- public pin/receipt/DTO/서명 단독/source unavailable가 observation/permission으로 바뀌지 않는지 검증한다. OS account/ACL/key possession 단독도 거절한다.
- replacement-before/after-read, junction/symlink/hardlink, concurrent source mutation, full manifest change를 재현하고 whole-attempt abandonment를 검증한다. unsupported platform은 fail closed한다.
- rejection/context exit/provider restart/crash/lease release/transaction 교체 뒤 same/copied/forged handle 및 old restored facts의 재사용을 거절한다. cleanup 실패는 retained ownership으로 처리한다.
- direct private facts/witness/Windows serialization/public journal CAS regressions를 유지한다. 실제 governance/key/credential/ceremony/user DB/Provider 접근은 없다.

## 7. 영향·대안·장단점·재검토

새 source/tests/Python port/production wiring/app schema/external journal schema 변경 0, Alembic `20260918_0037` single head/external journal v1 및 기존 Phase/DoD를 보존한다. Repository commit()/rollback() 0과 caller-owned transaction 책임은 그대로다. 실제 designation/credential 발급, durable admission/pin install, Claim/Seal/Principal/binding/WebAuthn/Recovery/Transfer/Rights Writer/Adapter/Worker/Runtime/API/Frontend는 non-goal이다.

장점은 다음 A infrastructure가 proof source/partial observation과 current permission을 혼동하지 않도록 직접 필요한 handoff를 고정하는 것이다. 비용은 reader 구현이 아직 미구현이며 source mechanism의 별도 review가 필요하다는 점이다. metadata-only A, designation root를 새 signing key로 추측하는 A, provenance 이전에 전체 B/C·durable admission을 묶는 대안은 기각한다. source authenticity/custody 기술 선택은 기존 root를 유지하는 구현 PR에서 검증하며, 새 trust root/mandatory signature/법적 human 판정/authority 의미 변경은 별도 사용자 Decision이 필요하다. 이 PR은 OPEN/Draft에서 종료하고 Ready/merge하지 않는다.
