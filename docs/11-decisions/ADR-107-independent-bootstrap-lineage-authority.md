# ADR-107: Independent Bootstrap Lineage and Initial Authorization Consumption Authority

> 상태: [설계 결정 — DECIDED, 구현·운영 비활성]
> 작성일·최종 수정일: 2026-09-30
> 기준 develop: 83d63f8908a4efb35a62aba95824fca87879f860 (#194 merged)
> 관련 PR: [#195](https://github.com/DohaStudio/DohaMusic/pull/195). 병합 상태는 PR 기록을 따르며 운영 활성화와 구분한다.
> 관련 결정: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-084](ADR-084-designation-provenance-reader-input-contract.md)
> 관련 문서: [Bootstrap architecture](../03-architecture/product-deployment-bootstrap-authority.md), [검증 보고서](../10-operations/independent-bootstrap-lineage-authority-validation.md)

## 배경과 결정 권한

Factory #193은 이미 존재하는 journal만 연다. 앞선 Initial GENESIS 감사의 INITIAL_GENESIS_AUTHORIZATION_STILL_BLOCKED 원인은 journal/application DB 밖의 no-prior-lineage 및 authorization 소비 사실을 소유하는 authority가 없다는 것이다. approval 확장과 ADR-093/094 scope 확대는 그 사실을 만들지 못한다. 이번 요청은 그보다 상위인 durable authority domain의 관리·최초 등록·mutation·보존·복구 경계를 결정하도록 허용한다. 이전 감사의 조건부 dedicated artifact를 이름만 바꿔 채택하지 않는다.

결정: ADR-076 external governance root 아래 **Independent Bootstrap Lineage Authority (IBLA)** 를 도입한다. Option C인 독립 append-only registry + exact signed authorization artifact를 선택한다. registry가 유일한 lineage/소비/currentness authority이며 artifact는 portable integrity proof다. 이것은 설계 DECIDED이지 store·인증·provisioning 구현 완료나 실제 human 지정이 아니다. Production External Journal Provisioning은 BLOCKED / NOT IMPLEMENTED, Initial GENESIS 실행은 BLOCKED, Production Authentication 및 Activation은 UNAVAILABLE다.

## 1. Authority 소유자와 최초 root

관리 책임은 해당 deployment에 대해 ADR-076 외부 designation으로 명시 지정되고 수락한 Product/Deployment Owner에게 있다. 이 human은 IBLA의 별도 Registry Custodian을 외부 record로 명시 위임할 수 있다. 동일 human이 수행할 수 있으나 runtime owner/custodian/OS administrator라는 이유로 자동 승계하지 않는다. IBLA custodian 위임은 FIRST_OWNER_BINDING custodian assignment와 다른 목적이며 Rights·Recovery·Transfer 권한이 아니다.

신뢰의 시작은 **기존 외부 governance assertion과 trusted initializer의 당사자·designation·fingerprint 독립 대조**다. registry의 첫 row, journal GENESIS 또는 artifact가 자기 root를 인증하지 않는다. 기존 서면 self-designation 허용을 유지하며 designation 자체를 새 mandatory signature로 바꾸지 않는다. 이 ADR은 새 registry registration/action record에 root의 exact 서명을 추가로 요구한다. 검증 key는 같은 artifact가 제공하는 key에서 enroll하지 않는다.

최초 registry commissioning ceremony에서 human/initializer는 registry ID, 관리 deployment domain과 coverage manifest, custodian 위임, root public verifier, 독립 storage/custody 및 보존 책임을 exact 대조·수락한다. 그 commissioning assertion과 registry verifier/checkpoint의 최초 trust anchor는 **target journal과 무관한 별도 governance custody**에 보존한다. 초기 anchor의 신뢰는 row 없음이 아니라 이 외부 assertion에서 끝난다. 더 상위 DohaMusic runtime 인증자를 재귀 요구하지 않는다. 실제 designation·ceremony·키 생성은 이번 작업에 없다.

같은 deployment domain을 새 registry ID로 다시 commissioning해서 기존 이력을 비울 수 없다. domain→registry mapping은 외부 commissioning history에 한 번 등록하고 교체는 complete history의 연속성을 검증한 별도 복구 절차만 허용한다. mapping/최신 checkpoint가 없거나 소유·coverage가 불명확하면 UNKNOWN으로 deny한다. 새 random UUID는 새 domain이라는 증거가 아니다.

## 2. 최초 lineage 등록: absence 대신 positive origin

Root가 exact lineage 등록을 승인하고 trusted initializer가 독립적으로 다음을 확인한 후 registry custodian이 append한다.

1. 외부 governance에서 새 deployment/Workspace scope를 실제로 지정한 positive origin record와 그 수락·출처. 대상 installation proof key의 fresh possession과 root fingerprint 대조.
2. root가 책임지는 complete scope inventory: deployment, 관련 installation alias, journal ID, ADR-078 scope manifest의 Workspace/existing owner tuples 및 이전/가져온 scope와의 연결. 이름·path·DB 내용만으로 lineage를 정의하지 않는다.
3. commissioning부터 연속된 authoritative registry history, 이전 외부 bootstrap/binding/seal 기록의 coverage와 최신성. row 부재는 이 검증 뒤의 collision 검사일 뿐 최초 등록 승인 근거가 아니다.
4. 기존 설치·import/restore·재설치·과거 기록 누락 여부. 최초 registry 도입 전의 deployment는 기존 독립 history를 대조해 prior/unknown으로 등록·차단한다. 과거 이력이 없다고 증명할 수 없는 legacy scope를 INITIAL로 backfill하지 않는다.

새 scope의 no-prior는 물리 세계 전체에 대한 암호학적 부재 증명이 아니다. root의 명시된 coverage/positive origin assertion과 독립 대조를 신뢰하는 ADR-076의 governance boundary다. root가 거짓말하거나 initializer와 공모하거나 외부 history를 숨기면 이 보장은 없다. 불명인 scope에는 운영자가 first-run boolean을 입력하는 대체 경로가 없다.

이 절차로만 REGISTERED_INITIAL을 만든다. 이전 success/binding/SEALED/uncertain/revoked/transferred/recovery 사실이 하나라도 있거나 coverage가 불완전하면 BLOCKED_HISTORY로 등록한다. 과거가 있다는 사실을 옮길 때 success라고 추정하지 않고 evidence reference와 차단 이유를 보존한다. 어떤 상태도 파일 부재에서 파생하지 않는다.

## 3. Storage option 비교

| 기준 | A: 독립 append-only registry | B: governance-signed immutable files | C: registry + signed artifact (선택) |
|---|---|---|---|
| Circular trust | 외부 commissioning anchor 필수 | file signing key의 외부 anchor 필수 | 외부 commissioning/등록이 root, 두 store 자기승인 없음 |
| Rollback resistance | current history + 별도 checkpoint 필요 | 서명만으로 old valid prefix 식별 불가 | registry revision + 별도 governance checkpoint; 전체 동시 rollback 한계 명시 |
| Journal deletion | 소비 기록 생존 | 완전한 history가 보존되면 가능 | 독립 registry의 소비 유지, missing target deny |
| App DB restore | 독립 lifecycle이면 영향 없음 | app backup과 분리 필수 | app backup/restore 대상에서 제외 |
| Clone | proof identity·단일 authority 필요 | 파일 복사만으로 독립 clone 구별 불가 | fresh proof·exact mapping·single serialized consume; 모든 private state clone 제외 |
| Replay | operation identity/CAS로 제어 | 파일 존재만으로 소비 확인 불가 | artifact replay는 live registry 재확인, 재생성 금지 |
| One-time consumption | 원자적 durable transition 가능 | 별도 current writer/head 없으면 경쟁 winner 보장 불가 | seal 시 irreversible consume, artifact에 소비 책임 없음 |
| Crash | transaction + uncertain protocol 필요 | partial publication/head discovery 복잡 | seal-first + read-only resolution/final audit |
| Revocation | append current cancellation 가능 | latest complete history 인증이 어려움 | registry cancellation과 consume가 같은 직렬화에 참여 |
| Recovery | 별도 authority 필요 | 새 파일로 history reset 위험 | consumed 유지, 별도 Recovery 결정 전 실행 deny |
| Transfer | immutable 연결 필요 | 파일 갈아끼움으로 alias 누락 위험 | stable lineage·이전 aliases 유지, initial scope 재사용 금지 |
| Auditability | 이벤트/현재 projection 분리 | 개별 서명은 좋지만 completeness 별도 | signed intent + durable event/projection 연결 |
| Least privilege | live reader/writer 분리 가능 | signer와 history publisher 책임 혼동 가능 | root 의도 승인/custodian 저장/attempt 소비/read 분리 |
| Complexity | 중간, live authority 항상 필요 | 작아 보이나 head/CAS/custody 추가 시 registry 재구현 | 더 큼, artifact integrity와 live status 이중 검증 비용 |
| Windows local-only | 독립 custody와 local serialization으로 가능 | 가능하나 파일 잠금만으로 현재성 부족 | local offline ceremony + 별도 governance custody로 가능 |
| Future remote | transport/auth 계약 추가 필요 | 복제·latest discovery 문제 확대 | 동일 domain semantics 유지, remote auth/consensus 별도 결정 |

A도 보안상 가능한 대안이지만 승인 intent를 live writer에만 전달하게 된다. C는 ADR-076의 offline exact root 승인 관례를 이어가고 감사 가능한 intent를 transport와 분리하므로 선택한다. B 단독은 currentness/consumption/rollback을 해결하지 못하며 이를 보완하면 사실상 A/C가 된다.

선택은 store/domain 아키텍처다. DB 제품·DDL·파일 format·signature domain/TTL·public API를 지금 만들지 않는다. 별도 durable transactional store는 app DB, target journal, runtime writable directory 및 그 backup/restore lifecycle 밖에 둔다. Windows local-only V1에서는 외부 지정 custodian의 별도 접근 통제 deployment storage와 별도 governance checkpoint custody를 사용하며 runtime에 직접 registry 파일 쓰기 권한을 주지 않는다. 실제 경로는 commissioning에서 정하며 하드코딩하지 않는다. root journal 내부 table 추가나 app DB table로 대체할 수 없다.

단순 다른 파일/디렉터리라는 이유로 독립이라고 인정하지 않는다. writer ACL/custody, restore 주체, backup 정책, commissioning mapping/checkpoint 보존을 별도로 검증해야 한다. checkpoint는 target journal/app DB 또는 동일 자동 restore 묶음에 두지 않는다. Windows primitives/내구성 구현은 아직 검증하지 않았으며 이를 통과하기 전 activation은 금지다.

## 4. 최소 logical facts와 exact lookup

다음은 논리 facts이며 schema/wire 선언이 아니다. event 종류에 필요한 사실만 가진다.

| Fact group | 최소 내용과 필요성 |
|---|---|
| Commissioning | registry identity, designation/provenance 및 coverage manifest digest, 위임 revision, 독립 anchor reference |
| Lineage identity | immutable lineage_id, deployment_id, 설치 ID + public proof fingerprint, journal_id 및 scope manifest digest |
| Origin | positive registration evidence digest/reference와 prior/unknown 판단; 승인 root/initializer provenance |
| Authorization intent | authorization ID, canonical intent digest, exact reviewed configuration digest, journal schema version, intended GENESIS envelope/manifest digest, root public identity; 정확한 동작과 대상 고정 |
| Audit event | operation ID/type, canonical fingerprint, authority revision, previous event digest, event digest, 발생 시각, verified writer provenance reference |
| Consumption | consumed authorization/attempt ID, seal revision 및 consumed_at; GENESIS 성공 여부와 별개로 영구 소비 |
| Outcome | exact resulting journal identity와 admitted GENESIS digest/완료 evidence 또는 uncertain reason; native raw identity는 private evidence로 분리 |
| Lifecycle | cancel/supersede의 exact predecessor·successor reference, recovery/transfer evidence reference. 필요 사건에서만 추가 |

현재 lifecycle state는 complete immutable events의 검증된 projection이다. timestamp는 감사 사실이며 freshness authority가 아니다. credential/private key/raw OS identity/human 개인정보는 public event에 저장하지 않는다. signature의 public key/fingerprint, opaque refs·digest·revision·논리 IDs는 public audit facts지만 무조건 인터넷 공개할 데이터라는 의미는 아니다.

primary lookup은 commissioned registry domain + immutable lineage_id다. deployment, installation proof identity, journal 및 Workspace scope tuple은 모두 검증된 reverse mapping으로 **동일 lineage**를 찾아야 한다. unknown/다중 match/불일치는 deny다. 운영 caller가 제시한 lineage_id만 조회해서 새 기록을 만드는 API는 없다. 같은 installation/deployment에 새 journal ID/path를 부여해 새 lineage로 우회할 수 없다. scope가 기존 lineage와 겹치면 independent external linkage 없이 새 등록을 거부한다. 새 installation을 기존 lineage에 연결하는 alias는 과거 mapping을 삭제하지 않는다. consumed lineage의 교체/alias 활성화는 별도 Recovery/Transfer Gate를 요구한다.

## 5. State와 writer authority

UNREGISTERED는 단지 조회 결과 UNKNOWN이며 eligible state가 아니다. independent registration만 REGISTERED_INITIAL을 만든다. lineage safety와 authorization state를 구분한다.

| 대상 | 허용 상태·전이 |
|---|---|
| Lineage | REGISTERED_INITIAL → INITIAL_SEALED → GENESIS_CONFIRMED 또는 UNCERTAIN |
| 차단 lineage | 등록 시 BLOCKED_HISTORY, 또는 안전 상태에서 RECOVERY_REQUIRED/RETIRED 차단 annotation. 소비·과거 facts는 항상 보존 |
| Authorization | ISSUED → CANCELLED / SUPERSEDED / CONSUMED. terminal에서 ISSUED로 복귀 없음 |
| Consumed outcome | PENDING → CONFIRMED 또는 UNCERTAIN. exact 기존 성공 증거의 read-only 대조로 UNCERTAIN → CONFIRMED 감사 보완만 가능 |

INITIAL_SEALED와 authorization CONSUMED/PENDING은 **같은 registry transaction**이다. 아직 journal 성공이 없더라도 initial entitlement는 소비됐다. GENESIS_CONFIRMED 뒤 bootstrap/binding success/seal/revoke/recovery/transfer references는 단조롭게 append하며 INITIAL로 돌아가지 않는다. registry는 Workspace binding을 직접 만들지 않으며 journal의 상세 root lifecycle을 복제하지 않는다. 기존 initial seal만으로 모든 후속 initial 재시도를 차단하므로 후속 상세 이력의 지연/누락이 initial eligibility를 복구할 수 없다. 추후 binding writer의 감사 연결은 activation gate에서 검증한다.

| Operation | 실제 권한·검증 주체 |
|---|---|
| register lineage | 현 외부 root의 exact signed registration + 독립 initializer 확인을 받은 Registry Custodian. root/CLI 문자열만으로 불가 |
| issue | 현 root의 exact intent, fresh registration/currentness와 설치 proof를 확인한 custodian. lineage당 미소비 current authorization 최대 1 |
| consume/seal | custodian이 검증·발급한 private live attempt capability의 trusted initial provisioning writer. exact auth/intent/identity·freshness·expected head 재검증 후 registry CAS |
| cancel | 현 외부 root 또는 명시적으로 cancel만 위임받은 custodian. ISSUED에서만 terminal cancellation; consume와 직렬화 |
| supersede | root가 새 exact intent와 이전 auth를 승인, custodian이 unsealed lineage에서 old SUPERSEDED + new ISSUED를 원자적으로 append |
| mark uncertain | 같은 trusted attempt의 outcome reporter 또는 registry integrity monitor. 가용성 차단만 가능하며 unseal/권한 발급 불가 |
| confirm | same-attempt writer 또는 authenticated read-only reconciler의 exact existing-journal evidence를 registry writer가 확인. 새 journal 쓰기 권한 없음 |
| recover / transfer | 이 ADR에서는 실행 권한을 누구에게도 부여하지 않음. 별도 검증된 Recovery/Transfer authority 결정 전 unavailable. custodian은 차단·참조 기록만 가능 |

caller role/boolean/public DTO/signature receipt로 writer를 구성하지 않는다. 외부 root의 서명은 intent integrity이고 source의 현재 위임·revocation·ceremony authenticity를 추가 검증해야 한다. root의 권한도 consumption history 삭제나 consumed authorization 재발급까지 확장되지 않는다. authorization CANCELLED와 lineage 폐기는 구분한다. 취소된 authorization ID는 영구 terminal이며 lineage가 독립 검증상 여전히 unsealed INITIAL인 경우에만 새로운 exact root 승인으로 별도 authorization을 발급할 수 있다. 반대로 lineage 자체의 revoke/retire는 RETIRED 차단 annotation을 append하고 새 등록/발급으로 복귀하지 않는다.

## 6. Consumption 순서와 분산 crash

| 방식 | crash window | 판정 |
|---|---|---|
| A: reservation → GENESIS | reservation 자동 만료 뒤 과거 성공 여부 불명 | reservation만으로 부족. expiry로 초기 권한 복구 금지 |
| B: journal commit → consume | journal 성공·consume 전 crash 후 삭제하면 replay 가능 | 기각 |
| C: irreversible external consume → GENESIS | consume 성공·journal 실패는 권한 소실 | 선택된 안전 핵심, fail-closed 비용 수용 |
| D: prepare/seal/finalize | prepare를 해제하며 숨은 성공을 재허용할 위험 | reversible prepare 생략. C의 seal + outcome finalize만 선택 |

순서: 독립 commissioning/currentness/등록/intent/설치 proof 검증 → lineage ceremony exclusion → registry transaction의 expected revision/hash 및 current delegation/auth state 재검증 → CONSUMED/PENDING + INITIAL_SEALED 원자적 durable commit → 별도 governance checkpoint를 exact sealed revision까지 전진·재검증 → 동일 live private attempt에 단 한 번 journal 생성/GENESIS commit 허용 → existing exact journal/history/custody 검증 → registry CONFIRMED 감사 append 및 checkpoint 갱신.

모든 eligibility 변경·등록·위임·취소 이벤트에도 registry commit → 독립 checkpoint 전진 순서를 적용한다. checkpoint가 확인되지 않은 event는 새 권한이나 성공 응답의 근거로 노출하지 않는다.

checkpoint와 registry도 atomic transaction을 공유하지 않는다. registry 먼저 commit한다. checkpoint가 뒤처지거나 ahead/mismatch이면 provisioning은 deny하며 새 consume/journal write를 허용하지 않는다. 독립 custodian이 연속 history와 마지막 알려진 checkpoint를 대조하는 보완은 checkpoint를 앞당기는 것만 가능하다. 소비가 있었던 attempt를 재개하거나 journal을 생성하는 capability를 재발급하지 않는다. checkpoint 응답 유실 시에도 최초 attempt는 중단한다. complete-prefix 여부가 불명하면 별도 Recovery 전 차단한다.

seal transaction이 승인 취소와 경쟁하는 linearization point다. cancel이 먼저면 seal deny, seal이 먼저면 auth는 이미 consumed라 cancel/supersede 불가. 이후 root/delegation 변동이 live attempt의 최종 eligibility를 깨뜨리면 실행을 포기하고 UNCERTAIN으로 차단하며 unconsume하지 않는다. 기존 deployment serialization을 우회하지 않고 registry scope lease를 가장 바깥에 두는 단일 acquisition order를 요구한다. initial 경로는 app DB를 읽거나 잠그는 것으로 승인하지 않으며 target 생성 전 registry transaction은 완료한다. registry lock을 journal write 중 획득하는 역방향 callback은 금지한다. 구체 lock/CAS 구현과 기존 lifecycle writer와의 경합 검증은 후속 Gate다.

| Crash/장애 | 필수 결과 |
|---|---|
| seal commit 전 확실한 rollback | journal side effect 0. 기존 ISSUED가 current라면 새 독립 attempt 가능 |
| seal commit 응답 불명 | live attempt 폐기. fresh registry로 exact 소비 여부 read-only 조사; 불명은 UNCERTAIN, 자동 생성 없음 |
| external consume 성공 → GENESIS 실패 | 소비 영구 유지. partial target은 활성 journal 아님. 초기 authorization 재사용·repair/create retry 금지 |
| GENESIS 성공 → external finalize 실패 | consumed PENDING이 이미 남음. exact 기존 target·GENESIS/history/custody를 읽어 CONFIRMED 보완만 허용 |
| 성공 후 journal 삭제/숨김 | 소비 기록으로 DENY. 같은 config/서명/새 path/새 journal ID도 재생성 없음 |
| 이미 consumed인데 journal이 비어 있음 | 처음이라고 판단하지 않음. UNCERTAIN/RECOVERY_REQUIRED |
| 프로세스 재시작/lease 유실 | live capability 소멸, consumed token을 다시 생성 권한으로 변환 불가 |
| registry/checkpoint unavailable·rollback·부분 event | fail closed. DB cache/파일 부재로 fallback 없음 |

설계상의 one-time은 irreversible entitlement consumption이다. GENESIS가 반드시 한 번 성공한다는 exactly-once availability 보장이 아니다. 분산 atomicity를 가정하지 않고 실패 시 0회 성공도 허용한다.

## 7. Reader, idempotency와 immutable history

Provisioning reader는 commissioned registry anchor, actual source custody, current delegation/root eligibility, complete hash chain과 current projection, 별도 monotonic checkpoint, exact lookup/설치 proof를 held lease에서 검증한다. timestamp 최신 파일, caller summary, app DB projection, portable signed artifact만으로 승인하지 않는다. mutation 직전 fresh revision과 state를 재검증한다. target journal currentness를 registry의 초기 인증에 요구하지 않으며 이는 circular dependency를 제거한다.

same operation ID + same canonical fingerprint는 기존 operation 결과의 replay다. consume replay는 '이미 소비됨'을 반환할 뿐 새 live journal-write capability를 주지 않는다. same ID + 다른 fingerprint, 다른 exact installation/deployment/journal은 conflict다. ID가 달라도 같은 lineage에서 두 active issuance/consume를 허용하지 않는다. 한 registry transaction은 event + projection + unique operation/alias 제약을 전부 commit하거나 0이다. 물리 corruption/부분 publication은 명시 UNKNOWN/UNCERTAIN deny이며 partial success projection을 제공하지 않는다.

history는 append-only event와 검증된 current projection이다. CANCELLED/SUPERSEDED/CONSUMED/CONFIRMED를 overwrite/delete/reset하지 않는다. historical signature와 live eligibility는 분리한다. root rotation/revocation은 외부 designation 갱신 및 독립 fingerprint 확인을 사용하고 대상 journal ACTIVE 상태에 의존하지 않는다. compromised old key만으로 registry successor를 승인할 수 없다.

## 8. Restore·clone·Recovery·Transfer와 retention

App DB/journal backup restore는 registry/checkpoint를 rewind하지 않는다. 과거 row/파일을 복원해도 동일 lineage mapping과 consumed 기록을 fresh 조회한다. 새 installation ID/proof key를 얻는 재설치는 새 initial deployment가 아니다. 기존 Workspace/deployment lineage와 독립 대조해 old aliases를 보존하고 consumed/unknown이면 Recovery Gate로 보낸다. application/config/DB clone은 설치 fresh proof 또는 canonical mapping에서 deny하고, 같은 proof를 가진 경쟁 attempt라도 하나의 intact registry에서 seal winner는 최대 1이다. 머신 전체의 private proof와 registry/checkpoint/governance 이력을 모두 복제한 환경은 아래 compromise 경계다.

Journal loss 후 복원은 Initial Authorization 재사용이 아니라 별도 Recovery authority다. owner/custodian transfer도 stable lineage와 terminal history를 보존하는 별도 authority다. ADR-076/078은 이들을 root bootstrap 권한에서 명시 제외하므로 새 root/registry custodian에게 실행 권한을 부여하지 않는다. recovery/transfer reference 기록은 future authenticated result를 연결할 자리이며 permission 아님. 현재는 RECOVERY_REQUIRED 차단만 가능하다.

성공·소비·취소·supersession·unknown/uncertain history, aliases, commissioning mapping과 checkpoint는 **해당 lineage/Workspace의 restore 또는 재사용 가능성이 남는 한 무기한 보존**한다. V1은 자동 GC/TTL 삭제를 제공하지 않는다. deployment retirement도 immutable tombstone을 남기며 같은 namespace/alias를 재사용하지 않는다. credential/private 개인정보를 public ledger에 넣지 않아 history 보존이 private key 보존을 요구하지 않게 한다. 법적 삭제/이관 요구가 생기면 별도 Decision 없이 safety tombstone을 제거하지 않는다.

## 9. Authentication·compromise·구현 gate

외부 root/initializer의 human 대조는 ADR-076/084의 trusted offline ceremony로 정의되어 있다. registry 관리에 runtime principal/ADR-042 WebAuthn을 필수로 추가하지 않는다. 이는 OS login을 human proof로 승인하거나 서명만으로 ceremony를 생략한다는 뜻이 아니다. 실제 수행자는 독립 human confirmation, 위임/currentness, source authenticity와 fresh key possession을 검증해야 한다. 이 경로의 adapter/custody 구현은 아직 없어 **IMPLEMENTATION BLOCKED**다. 기존 WebAuthn 기반 runtime 인증과 별개이며 Production Authentication은 계속 UNAVAILABLE다. 원격/무인 writer에 offline ceremony를 자동 치환하는 것은 별도 인증 Decision을 요구한다.

registry 파일만 rollback되면 독립 current checkpoint와 mismatch로 deny해야 한다. registry/checkpoint/domain mapping 모두를 rewind하거나 root/local privileged custodian이 공모·compromise하면 완전 anti-rollback/anti-clone을 보장하지 못한다. hardware monotonic counter나 원격 consensus 보장은 주장하지 않는다. source loss·복구 불명·키 compromise는 authority unavailable와 pending issuance 차단을 유발하며 새 빈 registry로 reset하지 않는다. ADR-076의 trusted local boundary와 일치한다. 더 강한 공격자 모델은 별도 ADR 대상이다.

후속 activation 전 필요한 증거: commissioning/origin/coverage authentic reader, independent store/checkpoint custody와 durability, actual atomic consume/CAS·concurrent cancel, lost response·crash matrix, deleted/hidden journal·old DB restore·reinstall/clone deny, source rollback/loss, current delegation/revocation, private attempt non-reissuance, exact reconciliation, safe logs 및 Fake fallback 0. 오늘 이 테스트를 실행한 것으로 표시하지 않는다.

## 10. 영향·이행·재검토

ADR-076 external root·서면 designation·Recovery/Transfer 제외와 ADR-078 no-prior 및 GENESIS wire를 유지한다. ADR-093/094 policy purpose, ADR-099 GENESIS deny, ADR-106 existing-only Factory는 변경하지 않는다. 이 ADR은 별도 상위 lineage/consumption store를 정의하며 기존 root-status journal과 별개다. 기존 journal schema를 registry로 재해석하지 않는다.

이행은 자동 backfill이 아니다. 초기 commissioning부터 새로 검증된 origin만 INITIAL로 등록하며 existing deployments는 complete independent evidence 없으면 BLOCKED_HISTORY다. code/schema/migration/public API/Frontend delta 0, Alembic 20260918_0037 유지, 실제 production data/key/credential/journal/OS custody 접근 0이다. Phase 9 인증·감사·Backup/Restore 선행 Decision이며 해당 DoD 0/18 및 기존 Phase 진척률은 그대로다.

장점: first-ever와 consumed-but-missing을 구별하는 책임이 target 밖에 존재하고 crash 때 entitlement가 되살아나지 않는다. 비용: 별도 store/checkpoint/ceremony와 보존 책임, 실패 후 unavailable 및 Recovery 미정에 따른 수동 중단이다. 다음 작업은 IBLA의 authentic commissioning/registration source와 transactional persistence/checkpoint 계약·검증 계획이다. Initial artifact wire, provisioning/GENESIS writer 구현은 그 이후 별도 작업이다.

원격 topology, multi-root, stronger rollback/clone threat model, legal deletion, live Recovery/Transfer, 새로운 store technology/crypto/wire 선택 또는 기존 root scope 변경 요구 시 재검토한다. 최초 작성은 Draft PR 범위였다. 후속 사용자 요청에 따른 최종 검증에서는 문서·exact-head CI·review/race Gate를 모두 통과한 경우에만 #195의 Ready/guarded squash merge를 허용하며 구현은 시작하지 않는다.
