# ADR-087: Custody Policy Provisioning / Initializer Provenance Linkage Contract

> 상태: [제안 — 최소 Contract Draft; provisioning/provenance 구현·운영 미활성]
> 작성일·최종 수정일: 2026-09-19
> 기준 develop: `54773b3ed4d4bfcee8bcc81000a4e6517c2245c0` (#173 squash merge)
> 관련: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-080](ADR-080-private-admission-currentness-handoff-contract.md), [ADR-081](ADR-081-provider-witness-lifetime-foundation.md), [ADR-084](ADR-084-designation-provenance-reader-input-contract.md), [ADR-085](ADR-085-designation-record-snapshot-foundation.md), [ADR-086](ADR-086-designation-source-custody-policy-foundation.md), [검증](../10-operations/custody-policy-provisioning-contract-validation.md)

## 1. 문제·최소 unit·대안

#173은 same-handle file identity·owner/protected DACL이 independently injected `SourceCustodyPolicy`와 일치하는지만 확인한다. 그 public policy에는 policy identity/revision, 실제 설치 action, initializer 위임과 독립 확인의 연결이 없다. ADR-084의 general provisioning semantic input을 이 exact policy에 연결할 책임도 아직 executable source에 없다. matching ACL/public metadata로 legitimate provisioning을 추론하는 A나 B는 구현하지 않는다.

이번 최소 unit은 이전 승인 후보 E, **A/B 구현의 직접 선행인 policy 설치 action과 initializer provenance의 exact linkage·terminal/current-pointer·live handoff 계약**이다. A의 policy persistence만 먼저 만들면 출처 없는 current pointer를 trust-enroll할 수 있고 B의 initializer ref만 먼저 읽으면 실제 설치한 policy를 증명하지 못한다. D 전체 persistence/authenticated reader를 한 PR에 묶지 않는다. 이 Contract의 review/채택 뒤 별도 A의 infrastructure 구현이 가능하며 현재 실제 external act를 수행할 필요는 없다.

docs-only다. 새로운 accepted wire, Python API/permission DTO, source reader/writer/registry 또는 provenance 검증 성공을 제공하지 않는다. 아래 모델과 negative acceptance는 후속 구현 계약이지 이번 runtime 실행 결과가 아니다.

## 2. 원래 root와 누가 설치했는지의 증명 경로

출발점은 ADR-076의 원래 외부 designation/root assertion이다. 서면 self-designation·human 확인/명시 수락·독립 fingerprint 대조와 명시 initializer 위임을 보존한다. unsigned 서면 designation을 새 의무 signature/CA/상위 signing root로 바꾸지 않는다. initializer의 실제 human을 이 ADR이 지정하지 않으며 추가 signing credential이나 two-person rule도 요구하지 않는다. 동일 human이 역할을 겸해도 designation 확인·initializer 위임·실제 provisioning action의 검증 책임은 분리된다.

필요한 연결은 **원본 accepted designation → 명시된 initializer/위임 및 exact installation 범위 → 독립 확인된 실제 provisioning action → 설치한 exact policy snapshot → fresh current-policy lineage**다. original designation record는 그대로 보존하고 별도 action record가 그 exact immutable reference/digest를 연결한다. 기존 signed bootstrap approval/issuance receipt나 root lifecycle signature를 initializer의 설치 증거로 재사용하지 않는다. provenance가 확인하는 것은 기존 initialization의 사실이며 root의 권한을 runtime super-admin/Workspace owner/Rights authority로 확대하지 않는다.

trusted initialization이 실제 action·initializer·designation/fingerprint/scope를 독립 대조하고 deployment-private 경계에 원본 confirmation provenance를 보존해야 한다. 후속 reviewed source adapter가 **그 원래 independently authenticated source**에서 확인한 결과만 partial origin observation의 근거가 될 수 있다. caller JSON의 `confirmed=true`, validator callback의 True, 익명 public-key signature, provider-private-looking DTO 또는 digest equality를 그 확인으로 대체하지 않는다. ACL은 보존 경계이지 record 진정성을 스스로 생성하는 anchor가 아니다. 최초 source/policy를 같은 untrusted record의 owner/DACL 값으로 자기 승인하는 circular enrollment도 금지한다.

실제 human/독립 채널 확인의 진정성과 그 confirmation을 보존한 source authenticity를 검증할 수 없는 adapter는 unavailable다. source가 보존한 이름/ref는 증거의 위치 조건일 뿐이다. 이 ADR은 실제 governance approval, ceremony 또는 production credential을 발급하지 않는다. disposable fixtures는 infrastructure만 검증하며 operational 승인으로 전환하지 않는다.

## 3. 서로 다른 입력과 exact binding (논리 facts, 새 wire/schema 아님)

| 입력 | 반드시 독립 확인하고 연결할 내용 | 단독으로 증명하지 못하는 것 |
|---|---|---|
| Policy snapshot | immutable policy UUID, technical profile/version, positive policy revision, installation UUID/proof-public-key fingerprint, exact source instance/root와 root/record native identity, explicit owner SID·approved SID set·exact protected binary DACL 및 전체 snapshot digest | public `SourceCustodyPolicy` 생성/descriptor equality는 설치 provenance 아님 |
| Provisioning action | immutable action UUID, exact policy ID/revision/full snapshot digest, installation binding, initializer opaque ref, designation ID/original record reference·exact-byte digest, 독립 confirmation provenance reference/digest, approved deployment scope, observed separately provisioned verifier key ID/raw public bytes/fingerprint 및 journal ID/admission/trust revision 연결 | record 존재/action timestamp/OS token은 trusted initializer 아님 |
| Original confirmation provenance | 원래 source의 authentic immutable record와 실제 설치 action 연결, initializer가 designation에 직접 명시되었거나 정확히 위임되었다는 원본 근거, human 수락·독립 fingerprint 확인 및 policy 설치가 승인된 initialization 범위 안이라는 대조 | root의 자기서명/approval artifact는 자기 initializer 지정 proof 아님 |
| Current policy lineage | immutable installation/source/lineage anchor, authoritative current pointer와 monotonic revision/head, predecessor action/policy snapshot 연결, terminal/replacement facts, fresh designation/initializer delegation eligibility | 가장 큰 caller revision/latest timestamp/ACTIVE enum은 current authority 아님 |

policy revision, technical encoding/profile version, journal revision, installed verifier trust revision은 다른 counter다. 같다고 추론하거나 하나를 나머지의 epoch로 사용하지 않는다. whole snapshot digest는 위 policy fields를 모두 포함해야 하며 path/SID/DACL digest 하나로 대신하지 않는다. native object identity는 physical binding이지 installation identity/human identity가 아니다. initializer ref와 approved SID mapping도 별개로 대조한다. observed descriptor에서 approved mapping을 자동 학습하지 않는다.

UUID/ref/hash/raw public bytes/exact native int·bytes/sorted unique complete scope의 canonical 비교·type confusion/custom equality/hash 거부는 ADR-081/084/086을 따른다. malformed/duplicate identity/unknown authority field/부분 scope/누락 provenance는 deny다. technical machine encoding·domain-separated whole-snapshot digest 및 source authenticity mechanism은 후속 implementation에서 bounded strict codec로 고정·회귀 검증한다. unspecified external original record bytes는 임의 JCS/Unicode normalization 없이 보존한다. 이 표를 accepted public JSON/permission DTO나 새 schema로 구현했다고 주장하지 않는다.

## 4. Revision·terminal·replacement·recovery

초기 current pointer는 independently confirmed original provisioning action과 independently verified empty policy lineage에서만 revision 1로 시작할 수 있다. 빈 app DB, file 생성, 새 reader/process 또는 unknown private store를 empty lineage로 간주하지 않는다. 설치 성공은 reader가 descriptor를 본 사실과 다르며 action confirmation과 실제 installed snapshot을 모두 대조해야 한다. partial write/uncertain completion이면 usable origin observation이 없고 bootstrap deny다.

replacement는 fresh accepted designation/initializer delegation과 새 immutable action·새 exact snapshot을 요구한다. fresh expected full pointer/head/revision에 대한 actual CAS와 immutable action/terminal predecessor/current projection의 단일 private-store transaction이 필요하다. 정책 lineage revision은 정확히 +1이며 safe integer overflow/reset은 deny다. competing same-head mutation winner는 1이고 stale loser는 whole attempt를 abandon한다. Repository의 caller Session commit()/rollback()은 0이며 private-store durable transaction owner를 app Repository 안에 숨기지 않는다.

replaced/revoked/superseded action 또는 policy version은 terminal이다. 같은 policy ID의 새 version은 새 action과 +1 revision으로만 표현하며 과거 version을 ACTIVE로 재사용하지 않는다. policy identity를 바꾸어도 installation/source의 stable lineage anchor와 high-water/history가 이어져야 한다. REPLACE/UPSERT/DELETE·anchor 교체·revision/epoch reset·duplicate current pointer·history truncate 및 reinstall로 새 genesis 우회는 금지한다.

private policy store와 actual OS descriptor/file의 distributed atomic commit은 가정하지 않는다. record commit 전후 또는 descriptor 적용 전후 crash/응답 유실/owner·ACL mismatch이면 deny한다. 복구는 이미 independently confirmed 동일 action/snapshot을 fresh 확인하는 exact reconciliation만 가능하며 새 designation/authority 발급·terminal reactivation·old-policy fallback·seal 해제는 없다. current successor가 있으면 과거 action으로 descriptor/current pointer를 되돌리지 않는다. unknown lineage/rollback/restore는 새 action으로 숨기지 않는다. 전체 privileged private-store/journal/key clone·rollback 한계는 ADR-076 그대로이며 hardware/remote anti-rollback을 추가하지 않는다.

## 5. Partial origin handoff·TOCTOU·serialization

future 내부 context는 original confirmation source, original provisioning action snapshot, separately verified policy/current pointer와 ADR-083/085/086의 live pin/designation/custody snapshot을 함께 유지해야 한다. 이름만 private인 public struct가 아닌 original provider registry/object identity에 bind된 **partial policy-origin observation**이다. 이 ADR은 해당 Python API/handle 발급을 구현하지 않는다. `ProvisioningWitness`/`CurrentnessWitness`/`CommittedAdmissionWitness` 또는 admission permission이 아니며 partial 단계에서 ADR-081 currentness registration을 호출하지 않는다.

provider instance/process/native owning thread, one attempt, original opaque OS lease, caller Session/root SessionTransaction, complete exact affected scopes, 실제 source/action/initializer-record identity 및 full policy/current-pointer lineage를 bind한다. public constructor/copy/pickle/JSON/DB receipt/boolean callback/Fake fallback으로 재구성하지 않는다. authoritative complete scope·installation provenance는 kernel acquisition **전에** 독립 확인하고 sorted complete locks를 얻은 뒤 다시 fresh 확인한다. global order는 complete ceremony mutexes → application guards → external CAS다. discovery 후보/caller pin list만으로 partial locks를 허가하지 않는다.

provenance read → custody check → policy validation → handoff 및 terminal action 직전에 같은 live held source handles에서 original confirmation/action/initializer record·policy revision/current pointer·native identity/owner/DACL·designation eligibility·complete manifest와 원래 lease/transaction을 fresh 재검사한다. 교체/ACL·owner 변경/junction·reparse/hardlink/추가 scope/stale revision/transaction 교체/API·cleanup uncertainty가 하나라도 관측되면 observation·snapshot·lease witness usability를 whole-attempt permanent abandon한다. old matching values 복원으로 재활성화하지 않는다.

context 종료/거절/provider restart/crash/release 뒤 old handle을 사용할 수 없다. caller가 evidence context 안에서 자신의 commit/rollback을 마친 뒤 원래 thread가 explicit release한다. helper는 SQL/hidden retry/자동 commit/rollback/GC cleanup을 추가하지 않는다. LocalFree/CloseHandle 실패는 ownership과 reservations를 retained quarantine에 보존하고 확인된 cleanup만 허용한다. 기존 read/write/delete sharing·same-handle bounded transport/ancestor identity와 cleanup을 우회하지 않는다. 두 관측 사이 privileged ACL restore·기존 writable mapping·malicious process에 대한 완전 탐지를 주장하지 않는다.

## 6. 후속 executable negative acceptance (이번 실행 결과 아님)

| 공격·누락 | 후속 구현의 필수 결과 |
|---|---|
| wrong installation/proof fingerprint/policy ID/full snapshot/root/source/owner/DACL | 원본 independently confirmed action과 exact comparison 불일치, deny |
| wrong initializer/delegation/designation/verifier fingerprint/approved scope | ref/signature/OS account 단독 승인 없이 deny |
| incomplete provenance/malformed·duplicate/unknown fields/public metadata substitution | partial observation 발급 0, unavailable source → allow 0 |
| stale revision/replayed action/revoked·superseded version/REPLACE·UPSERT/anchor reset | terminal/history/high-water 유지, stale CAS 재활성화 0 |
| validation 뒤 record/initializer/policy replacement·ACL/owner mutation·junction/hardlink | whole attempt abandon, 같은 values 복원 후 old handle deny |
| concurrent provisioning/current-pointer·manifest mutation | complete locks/fresh recheck/actual CAS winner 1, partial observation reuse 0 |
| stale/foreign/copied handle·lease/provider restart·transaction 교체 | original registry/lifetime deny, old witness 재활성화 0 |
| commit/descriptor 적용 crash·응답 유실·LocalFree/CloseHandle 재실패 | uncertain deny·retained ownership, same-action reconciliation 외 발급 0 |

disposable designation/provisioning/action/initializer fixtures는 기존 approval/lifecycle signed fixture와 분리하고 independent test source를 명시 주입한다. unsigned 원본 acceptance 경로도 보존한다. 최소 focused와 custody/snapshot/pin/witness/Windows serialization/direct journal CAS/Auth/Rights/Completion 회귀를 실행하고 가능한 full backend/static Gate를 확인한다. 위 새 provisioning/provenance negatives는 실제 source 구현 뒤 실행하며 기존 mechanics의 PASS를 해당 검증 PASS로 표시하지 않는다.

## 7. 영향·trade-off·다음 unit·재검토

새 source/tests/Python ports/production wiring/app schema/migration/external journal v1 변경 0. app Alembic `20260918_0037` single head·Phase 6 DoD 14/14·다른 Phase 진행률과 caller-owned transaction을 보존한다. private policy/provenance facts는 app DB/backup과 독립 경계이며 논리 lineage 결정이 자동 backfill/table 생성의 근거가 아니다.

장점은 exact policy를 설치한 initializer/action의 원본 provenance와 현재 pointer를 분리해 metadata self-enrollment를 차단하는 것이다. 비용은 아직 구현되지 않은 source authentication·private-store durability/currentness와 bounded machine codec review다. 이 Decision은 실제 provenance proof를 제공하지 않는다. 다음 최소 implementation은 A의 strict policy/action comparison·authenticated original-source snapshot adapter의 필요한 infrastructure이고, independent initializer verification을 불가분하게 요구하는 부분만 함께 검증한다. actual external acceptance가 없는 production path는 계속 unavailable다.

production ports는 unconditional unavailable다. 실제 governance/designation/approval/ceremony/private key/Custodian credential/User DB/Provider 접근·발급 0. Durable Admission/Claim consume/Principal/binding/WebAuthn/Recovery/Transfer/Rights Evidence/Writer/Adapter/Worker/Runtime/API/Frontend는 non-goal이다. 새 PR은 OPEN/Draft에서 종료하고 Ready/merge/source 삭제하지 않는다. 새로운 trust root/mandatory signature/법적 human 판단/privileged anti-rollback/다른 authority 의미가 필요하면 별도 사용자 Decision으로 재검토한다.
