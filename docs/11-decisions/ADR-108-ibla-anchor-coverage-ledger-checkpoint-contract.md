# ADR-108: IBLA Commissioning Anchor, Complete-Coverage Ledger and Independent Checkpoint

> 상태: [Contract DECIDED — 구현·운영 비활성]
> 작성일: 2026-09-30
> 최종 수정일: 2026-10-01
> 기준 develop: 7831991239534be5aa7db532676646a1d5e90785 (#195 merged)
> 관련 결정: [ADR-076](ADR-076-product-deployment-bootstrap-authority.md), [ADR-078](ADR-078-deployment-verifier-current-status-lifecycle-contract.md), [ADR-084](ADR-084-designation-provenance-reader-input-contract.md), [ADR-107](ADR-107-independent-bootstrap-lineage-authority.md)
> 검증: [Contract 감사 보고서](../10-operations/ibla-anchor-ledger-checkpoint-contract-validation.md)

## 1. 문제·결정·기존 root

ADR-107이 정의한 current first-registration authority는 positive commissioning origin, complete current history와 독립 checkpoint를 함께 요구한다. 기존 source snapshots/policy-purpose authority는 이 complete history를 제공하지 않아 source verifier 구현은 중단됐다. 이번 Decision은 그 verifier의 입력을 소유할 세 경계와 persistence의 실행 가능한 실패 계약을 확정한다. 실제 인프라가 없다는 사실을 이미 운영 중인 것으로 바꾸지 않는다.

**Anchor / Complete-Coverage Ledger / Independent Checkpoint Contract DECIDED.** ADR-076 root 아래 immutable commissioning anchor A, IBLA registry의 authoritative event ledger L, 별도 governance custody의 current high-water authority H를 둔다. Option C를 local/offline profile로 선택한다. signed checkpoint artifact P는 H의 portable 감사 projection이며 H 자체가 아니다. A/L/H는 논리적 역할이고 반드시 세 머신을 요구하지 않는다. 기존 journal과 새 ledger를 합치거나 또 다른 registration registry를 중복 생성하지 않는다.

신뢰는 ADR-076 외부 designation·human 수락·initializer의 독립 채널 fingerprint 대조에서 끝난다. root/custodian의 offline provisioning ceremony를 사용하며 runtime WebAuthn이나 새로운 상위 root를 추가하지 않는다. 실제 source authenticity·ceremony 확인을 하지 못하는 production adapter는 계속 unavailable다. 이 문서는 실제 사람을 지정하거나 signing credential을 발급하지 않는다.

## 2. Commissioning Anchor A와 최초 생성

A는 외부 governance가 특정 domain 및 intended lineage의 합법적 commissioning origin을 승인한 **immutable exact-scope record**다. config, app DB row, target journal 또는 새 UUID가 아니다. root designation reference/digest, root key/public fingerprint와 authority epoch, commissioning purpose, action/operation ID, positive origin evidence reference/digest, complete coverage inventory/boundary, intended installation ID + proof fingerprint, deployment/lineage/journal ID, L/H의 logical identity, 위임된 ledger/checkpoint custodians 및 scope, issued/not-before/not-after와 canonical record digest를 bind한다. raw human 자료/private keys는 별도 private custody에 둔다.

A의 purpose는 IBLA commissioning origin 및 A/L/H binding에 한정한다. INITIAL GENESIS, consume, Recovery/Transfer permission이 아니다. 유효기간은 commissioning action eligibility에만 적용되고 이력·identity 보존에는 만료가 없다. null/wildcard validity로 무제한 발급하지 않으며 concrete bound/clock encoding은 후속 persistence codec에서 보수적으로 고정·검증한다. 과거 유효한 A의 서명과 현재 root/designation/위임 eligibility를 구분한다.

**최초 A 생성 권한**은 current ADR-076 root의 exact signed commissioning action + 외부 initializer가 독립 대조한 designation/positive origin/complete inventory다. root의 서명 key는 artifact 자신이 제공한 public key로 self-enroll하지 않는다. 기존 unsigned 서면 designation 허용은 그대로며 새 commissioning action 서명이 designation의 외부 진정성을 대체하지 않는다.

Initializer는 배포 책임 human과 exact domain·scope, 기존 설치/import/restore/과거 bootstrap·binding/SEALED/uncertain 여부 및 old aliases를 대조한다. 새로운 scope라는 positive evidence와 책임지는 historical coverage boundary를 남긴다. 과거 기록을 찾지 못한 legacy deployment는 UNKNOWN/BLOCKED_HISTORY이고 INITIAL로 backfill하지 않는다. 전세계 과거 부재의 암호학적 증명이 아니라 명시된 ADR-076 governance assertion의 범위다.

A의 original bytes/digest와 domain→L/H mapping은 L과 독립된 H의 governance commissioning custody에 최초 등록한다. 이 최초 등록은 A 없음/H row 없음이 아니라 위 외부 ceremony로만 승인한다. root가 독립 확인한 keeper identity/public proof, custodian 위임과 native source custody binding을 initializer가 별도로 pin한다. L 또는 P가 그 pin을 공급하지 않는다. A를 읽기 위해 target journal이나 first-registration capability를 요구하지 않는다.

같은 domain을 새 L/H/epoch/lineage ID로 재등록해 이력을 비울 수 없다. namespace와 alias는 H의 retained commissioning mapping 및 외부 origin inventory에 한 번 연결된다. 새 mapping인지 증명 불가하면 deny. 저장소 교체/분실 후 재생성은 별도 Recovery 전 금지다. A의 취소/교체/expiry는 bytes overwrite가 아니라 아래 ledger/control history로 보존한다.

## 3. Complete-Coverage Ledger L

L은 ADR-107 IBLA registry의 **유일한 append-only event authority**다. 별도 commissioning ledger와 consumption registry를 만들어 이중 쓰기/누락을 허용하지 않는다. 하나의 commissioned governance domain은 하나의 L identity와 하나의 H identity를 갖고 여러 exact lineage를 기록할 수 있다. A들은 동일 mapping을 참조한다.

L은 immutable event ID/operation ID, domain/L/A/lineage identities, authority epoch, revision, predecessor digest, canonical event digest, verified writer provenance 및 event-kind payload를 보존한다. revision은 domain 전체에서 1부터 연속 증가하며 epoch 변경으로 1로 reset하지 않는다. event+operation uniqueness+alias mappings+current projection+expected-head CAS는 한 local durable transaction의 all-or-zero다. DELETE/UPDATE/REPLACE/guard reset/ID 재사용은 금지한다. application ORM/Alembic/startup/backup에 포함하지 않는다.

ADR-079의 immutable ledger/actual CAS/guard/projection pattern과 strict comparison/JCS/hash 관례는 재사용할 수 있다. 그러나 기존 production journal의 table/schema/domain을 확장하거나 기존 GENESIS를 L의 commissioning으로 재사용하지 않는다. 기술 backend 선택·DDL·crash durability 실측은 다음 persistence Foundation의 구현 검증 항목이며 이 Contract에는 실제 schema 파일이 없다.

### Logical event families v1

| Family | 필수 의미·보존 범위 | 현 단계 |
|---|---|---|
| COMMISSION | exact A와 origin/coverage binding, domain 최초 event 또는 추가 A 연결. duplicate scope/alias 거부 | 계약만 |
| CANCEL / SUPERSEDE | exact unconsumed action/anchor/authorization의 terminal status, successor reference. 과거 record 삭제 금지 | 계약만 |
| AUTHORITY_TRANSITION / DELEGATION_STATUS | root epoch 전환·custodian 위임 변경/취소, 외부 재지정 evidence와 이전 epoch 연결 | 계약만 |
| REGISTRATION_AUTHORIZED / REGISTRATION_COMMITTED | 특정 lineage 등록의 승인 및 실제 영속 사실. source verifier의 ephemeral 결과를 이 event로 위장하지 않음 | future writer만 |
| INITIAL_AUTHORIZATION_ISSUED / INITIAL_AUTHORIZATION_CONSUMED | exact initial authorization과 ADR-107 irreversible seal/consume; registration과 다른 목적 | future writer만 |
| GENESIS_OUTCOME | consumed attempt의 exact confirmed/uncertain outcome reference. 이 event가 GENESIS를 실행하지 않음 | future writer만 |
| HISTORY_BLOCK / UNCERTAIN / RECOVERY_REQUIRED / RETIRE | legacy/prior/unknown·응답 불명·분실·폐기 safety facts. prior success/SEALED/binding evidence reference 포함 | 계약만 |
| BINDING_HISTORY / RECOVERY_REFERENCE / TRANSFER_REFERENCE | 기존 성공/terminal 이력 또는 별도 authority가 실제 승인한 결과와 aliases 연결. 자체 실행 권한 없음 | future writer만 |

위 명칭은 semantic namespace다. REGISTRATION_CONSUMED 하나로 registration 및 initial authorization consumption을 합치지 않는다. 미지원 future kind, unknown field/version/epoch는 reader가 건너뛰지 않고 deny한다. 새 kind는 version 검토와 모든 reader/writer의 coverage 갱신 뒤 도입한다. 지원하지 않는 kind의 writer를 먼저 켜지 않는다.

### Complete coverage의 canonical 정의

Complete view는 **독립 지정된 domain/membership inventory 안에서** 아래를 모두 충족한 것이다.

1. original A 및 H commissioning mapping을 독립 검증하고, ledger 최초 revision 1 COMMISSION이 그 exact mapping/origin을 참조한다. revision 0은 미초기화이지 no-prior authority가 아니다.
2. 전체 domain의 revision 1..N을 누락 없이 읽어 unique operation/event, predecessor digest, event digest와 event-kind state transitions를 검증한다. current row 또는 선택한 lineage만 조회한 결과로 대신하지 않는다.
3. 모든 root epochs/delegations와 superseded/cancelled records를 포함한다. epoch boundary는 이전 head를 연결하고 global revision/lineage/aliases를 보존한다. compromised old key만으로 successor를 승인하지 않는다.
4. 모든 relevant registration/consumption/binding/seal/alias/unknown facts를 replay해 current projection과 비교한다. complete history가 있다는 것과 그 history에 prior evidence가 없다는 것은 별도 판정이다.
5. 독립 H를 fresh authoritative read한 confirmed tuple (L identity, N, head digest, epoch, checkpoint sequence)이 L과 같고 pending/UNCERTAIN barrier가 없다. caller가 전달한 P를 H의 현재값으로 취급하지 않는다.
6. 동일 domain lease와 held source lifetime 동안 A/L/H identity·mapping·delegation·head를 correlation하고 terminal handoff 직전 재검증한다. lifetime 종료·변경·재시작은 result를 무효화한다.

N보다 뒤의 event를 숨긴 valid prefix는 H의 current N/head로 거부한다. H까지 같은 과거 prefix로 바꾼 경우의 한계는 §10에 별도로 둔다. 모든 관련 writer가 이 domain serialization·L/H protocol에 참여한다는 것이 coverage 전제다. 제외 writer·기록 누락·불명 membership은 deny이며 'complete=true' 서명이나 caller list로 보충하지 않는다. 큰 history는 동일 snapshot/lease 안의 연속 pagination만 허용하고 과거를 삭제해 상한에 맞추지 않는다. 자료/자원 한도 초과는 availability failure다.

## 4. Independent Governance Checkpoint H와 artifact P

H는 외부 root가 명시 지정한 **checkpoint custodian/keeper의 독립 durable current-state authority**다. 새 human root가 아니며 ledger writer의 자기서명 cache가 아니다. root와 checkpoint custodian이 같은 human일 수 있지만 위임 scope·private capability·storage write 권한은 분리한다.

H는 domain→A/L mapping과 identity tombstones, monotonic control sequence, previous control digest, root epoch 및 위임 provenance, last confirmed L revision/head/epoch, pending exact operation barrier, checkpoint audit timestamp·signer identity를 append-only control history와 current projection에 보존한다. H의 control event·operation index·mapping/pending slot·current projection은 단일 H transaction에서 all-or-zero로 전진한다. counter/reset/replacement로 pending을 지우지 않는다. timestamp는 freshness가 아니다. P는 H가 confirmed observation에 서명한 portable artifact chain이며 current H를 live 검증하지 않으면 과거 무결성만 제공한다.

checkpoint custodian은 root가 승인한 A/위임/current eligibility를 확인하고 **자신의 reader로 L의 exact complete extension을 읽고 검증**한 후 H를 조건부 전진시킨다. caller가 보낸 head/digest를 그대로 저장하지 않는다. ledger writer는 H의 파일·head·서명 key를 직접 수정할 수 없다. H writer는 L의 history를 수정할 수 없고 first-registration/GENESIS/Rights 권한을 발급하지 않는다. H는 authority observation과 monotonic barrier만 소유한다.

### 최초 H와 첫 checkpoint

독립 initializer가 검증한 A와 exact L/H mapping을 checkpoint custodian이 받아 H의 commissioning control record를 만든다. 이때 confirmed ledger head는 **없음**이며 state는 COMMISSIONING_PENDING, sequence는 시작값 1이다. 'L 없음' 또는 'empty H'가 승인 근거가 아니다. control record는 first complete-history checkpoint가 아니고 capability를 발급하지 않는다.

그 exact external commissioning action으로 L revision 1 COMMISSION을 기록한다. keeper가 A와 revision 1을 직접 대조한 뒤 H에 첫 CONFIRMED checkpoint를 append한다. 첫 checkpoint의 승인 근거는 외부 A이고 관측 대상은 L의 실제 event다. L이 H의 custodian/root를 승인하거나 첫 checkpoint만으로 A를 self-enroll하지 않는다. 초기 empty L/H 파일의 기술 설치 자체는 public persistence setup일 뿐 commissioning 성공이 아니다.

## 5. Storage options와 독립성

| 기준 | A: L + 별도 signed checkpoint files/history | B: L + governance-signed artifact chain | C: L + independent current high-water source (선택) |
|---|---|---|---|
| Circular trust | 외부 pin 없이 self-head 파일이면 실패 | 외부 signer pin 필수 | A의 외부 ceremony가 L/H를 함께 지정, H 관측은 신규 승인 아님 |
| Rollback | 최신 파일이 무엇인지 별도 authority 필요 | valid old prefix도 검증될 수 있음 | live H와 local L/P 대조, H 자체 compromise 한계 명시 |
| Truncation | suffix 삭제는 서명만으로 부족 | chain 내부 gap은 탐지, hidden suffix는 별도 | H current revision/head로 stale L/P prefix 거부 |
| Journal deletion | 별도 보존이면 유지 | 별도 보존이면 유지 | target journal과 독립 L/H 유지 |
| App DB restore | backup 분리 필수 | backup 분리 필수 | app backup에서 L/H/A 제외 |
| Clone | copied files로 fresh 판정 위험 | copied artifact는 current proof 아님 | 설치 proof·domain mapping·단일 live H 확인; 전체 authority clone 제외 |
| Replay | immutable artifact 반복 검증 가능 | signer/nonce만으로 used 여부 모름 | global operation fingerprint + pending/confirmed control state |
| Crash recovery | publication partial/head 선택 복잡 | chain publication과 L atomicity 없음 | durable intent barrier→L append→H confirm, 불명 deny |
| Offline local | 가능 | 가능 | local dedicated custody keeper로 가능, 네트워크 불필요 |
| Least privilege | file signer/producer 혼동 주의 | signer 분리 가능 | ledger/custodian/checkpoint writer 권한 분리 |
| Auditability | 파일 이력 보존 필요 | 서명 chain은 좋으나 currentness 별도 | complete L + H control history + P audit export |
| Complexity | 간단해 보여도 current discovery 추가 필요 | latest head 보증 추가 시 C와 유사 | 독립 durable source·직렬화 구현 비용 수용 |
| Future remote | current source 별도 도입 | 원격 artifact만으론 부족 | semantics 유지, remote authentication/transport는 별도 Gate |
| Windows custody | fixed path/native handles 재사용 가능 | 동일 | 별도 protected root·writer context·held current reader 필요 |

A/B만으로 currentness를 제공한다고 주장하지 않는다. C의 H는 '이미 설치된 외부 service가 있으니 사용'이 아니다. ADR-107이 지정한 governance custody 안에 **다음 persistence Foundation에서 만들 독립 logical store/keeper**다. 원격 governance network/hardware service를 선행 요구하지 않는다. 이 Contract로 다음 구현 범위를 확정하며 실제 운영 source 존재는 주장하지 않는다.

V1에서 A와 H는 같은 governance custody boundary에 둘 수 있고 L은 별도 writer/restore boundary다. 같은 Windows machine도 가능하나 ordinary app/ledger process에 H write credential·파일 수정 권한을 주지 않는다. 한 프로세스가 L/H 모두 unrestricted write하는 배치는 독립성 충족으로 인정하지 않는다. read-only correlation coordinator가 둘을 읽는 것은 가능하다. 분리된 privileged contexts, root/leaf identity·owner/protected exact DACL, no reparse/hardlink/replacement, cleanup failure deny는 기존 mechanics를 재사용해 다음 Foundation에서 검증한다. config path만 다르거나 같은 DB의 두 table이라는 이유로 독립이라고 판단하지 않는다.

H의 authoritative source와 app에 전달된 P/cache를 구별한다. app filesystem의 P를 지우거나 되돌려도 H에서 current view를 가져오지 못하면 deny다. same-volume hardware loss 또는 machine-wide restore가 두 custody를 함께 손상시킬 수 있다는 점은 operational backup·compromise boundary로 남는다.

## 6. Logical schema / version v1

다음은 persistence 구현을 위한 논리 계약이며 accepted JSON/DDL/API를 지금 추가하지 않는다.

| Record | 필수 logical facts |
|---|---|
| Anchor v1 | A ID, purpose, domain, exact installation/proof/deployment/lineage/intended journal, L/H IDs, origin/coverage manifest reference+digest, root/designation/epoch, delegated writers, action ID, issuance/validity, canonical digest/signature |
| Ledger event v1 | L/domain/A/lineage IDs, event kind/version, global revision, predecessor/event digest, epoch, operation ID/fingerprint, per-kind exact facts, independent authority evidence reference, audit time |
| Ledger projection v1 | full verified replay-derived state, reverse aliases, last revision/head, immutable operation index. authoritative event와 한 transaction |
| H control v1 | H/domain/A/L IDs, control sequence/previous digest, kind COMMISSIONING_PENDING 또는 PREPARED 또는 CONFIRMED 또는 UNCERTAIN, operation/fingerprint, expected predecessor 및 intended successor tuple, confirmed L tuple, custodian/root epoch, evidence·audit time |
| Checkpoint artifact v1 | H control sequence/digest, exact confirmed L tuple, A/domain, current observation signer/epoch, observed time, signature. pending artifact를 eligible proof로 발급 금지 |

동일 operation fingerprint는 kind/purpose·모든 exact identity·epoch·predecessor·intended canonical payload digest를 포함한다. 사용자 secret/OS identity를 fingerprint에 그대로 노출하지 않는다. digest는 기존 JCS/strict UTF-8·SHA-256 관례를 사용하고 Ed25519와 distinct domain separation을 재사용한다. 각 record의 wire domain 문자열/byte bounds/counter upper bound/clock profile는 후속 Foundation에서 명시 동결·negative test한다. 각 record의 자체 digest는 계산 결과이며 자신의 hash 입력에 다시 포함하지 않는다. signature는 domain-separated canonical payload에 적용하고 ledger/control event digest는 확정된 canonical record에서 계산한다. 서명·digest 필드의 정확한 envelope 배치는 구현 codec에서 고정한다. 기존 ADR-077/078/090/093 domain이나 parser를 새 purpose로 변경하지 않는다. canonicalization은 A의 별도 structured record에 적용하며 원본 unsigned designation bytes를 임의 재정규화하지 않는다.

unknown version/kind·duplicate key·float/bool revision·overflow·ambiguous identity는 deny. epoch는 root/delegation continuity reference이지 reset counter가 아니다. immutable identity/alias tombstones는 version upgrade에도 보존한다. app schema/Alembic 변경 0, existing journal schema 변경 0.

## 7. Writer / Reader 계약

| Operation | 권한·한계 |
|---|---|
| Create A / commission H mapping | ADR-076 current root exact action + initializer 독립 human/origin 확인, 명시 governance custodian. caller flag/OS admin/key possession만으로 불가 |
| Prepare H barrier | checkpoint custodian이 exact intended authorized ledger action·current mapping/epoch/head를 검증. pending이면 다른 mutation/eligible read 거절 |
| Append L | 해당 kind에 외부 root가 명시 위임한 ledger writer + H의 exact live pending operation. unknown/future kind writer 비활성 |
| Confirm H / emit P | checkpoint keeper가 L의 actual complete extension을 독립 read. ledger writer의 summary callback 거절 |
| Correlate read view | authentic A + complete L + fresh H 동일 lease/source/epoch/identity. caller DTO는 authority 아님 |
| Recovery / Transfer | 별도 Decision 전 실행 unavailable. 차단·과거 참조 기록만 가능 |

Future verifier가 소비할 output은 provider-owned lifetime-bound exact correlation view다. public boolean/DTO/serialized P를 VerifiedInitialLineageRegistrationAuthority로 만들지 않는다. registry registration·initial authorization·consume가 가능한 capability는 이번 Contract도 다음 public persistence Foundation도 발급하지 않는다.

공동 mutation 순서는 domain governance lease → H의 짧은 local transaction → L local transaction → H local transaction이다. 각 transaction은 종료 후 다음 단계로 이동하고 두 DB의 원자성을 가정하지 않는다. 해당 domain의 source validity·complete membership을 lock 전에 독립 확인하고 lock 후 재확인한다. 기존 deployment locks가 필요하면 governance lease보다 안쪽에서 기존 sorted ceremony → app guards → target journal order를 유지한다. app DB는 이 작업의 authority/guard가 아니며 여기서는 접근하지 않는다. 비협력 writer/역방향 lock acquisition/reader-only lock을 완전성 보장으로 사용하지 않는다.

## 8. 분산 mutation과 durable UNCERTAIN barrier

Ledger-first → checkpoint-confirm만으로는 L commit 후 H 갱신 전 crash/rollback에서 pending action을 놓칠 수 있다. 따라서 H에 **비권한 intent barrier**를 먼저 남기고 실제 confirmed checkpoint는 L 뒤에만 전진한다. 이는 ADR-107의 registry commit → checkpoint 확인 → 신규 권한 노출 순서를 바꾸지 않는다. PREPARED는 ledger 성공이나 authorization 소비가 아니다. pending이 있다는 사실만으로 모든 eligible view를 차단한다.

1. actual external action/epoch/currentness와 A/L/H를 검증하고 domain lease를 얻는다.
2. H가 expected confirmed tuple에 대한 exact operation ID/fingerprint/intended successor를 PREPARED로 durable CAS한다. 다른 operation과 stale caller는 deny. 이 control record는 confirmed ledger revision을 증가시키지 않는다.
3. L writer는 동일 live operation과 expected L head를 대조하고 event+projection을 local transaction으로 append/commit한다. irreversible future consumption이라면 이 단계가 ADR-107 consume point다.
4. Keeper는 held source에서 L의 exact complete extension을 독립 read하고 H를 CONFIRMED로 append한다. control history의 PREPARED는 삭제하지 않는다. 단일 operation의 intended next L revision은 정확히 predecessor+1이며 한 pending만 허용한다.
5. A/L/H confirmed correlation을 다시 검증한 후 결과를 노출한다. future first-registration permission은 별도 verifier 단계다.

H durable commit과 confirmed response가 불명확하면 새로운 barrier/operation을 발급하지 않는다. 동일 operation의 history만 read-only 조회한다. restart 뒤 PREPARED에서 L의 exact event가 보이면 H confirmation만 보완할 수 있다. event가 없거나 L이 과거 prefix이면 'append가 안 됐었다'고 단정할 수 없으므로 UNCERTAIN으로 유지한다. ledger append retry/자동 abort·barrier 만료/새 operation·새 A/H로 우회하지 않는다. 확실한 in-process rollback이어도 V1는 PREPARED를 자동 해제하지 않는 보수적 정책을 선택한다. 실패한 첫 준비 때문에 deployment가 unavailable가 될 수 있으며 복구는 별도 Decision 전 차단한다.

CONFIRMED보다 앞선 H tuple을 L이 주장하거나 다른 event digest가 나타나면 conflict/rollback이다. keeper가 L을 forward repair/recreate하지 않는다. H/L 둘 다 저장 불가하면 durable UNCERTAIN event를 남겼다고 주장하지 않고 읽기 실패 자체로 unavailable다. pending/identity mismatch가 계속 deny를 보장해야 한다.

## 9. Crash / replay 표

| 지점 | restart 후 결과 |
|---|---|
| A write 전 | 외부 commissioning provenance 없이 생성 허용 안 함. 승인된 exact action 재확인은 가능하나 absence가 새 승인은 아님 |
| A 영속 후 H mapping 전 | A만으로 eligible 아님. 같은 외부 ceremony/action과 정확히 일치할 때 mapping 등록 검토; 불명 source/과거 mapping은 deny |
| H commissioning record 후 L revision 1 전 | COMMISSIONING_PENDING. same live 초기 작업 외 restart는 exact existing L 관측만; 파일 부재로 초기화 재시도 금지 |
| H PREPARED 전 확실한 실패 | L mutation 0. 독립 currentness 재검증 후 새 attempt 가능 |
| H PREPARED 성공 → L append 전/후 crash | barrier 유지. exact existing event이면 confirmation 보완, 없거나 ambiguous면 UNCERTAIN |
| L append success → H update failure | committed fact 유지, capability 0. H가 read-only exact successor를 확인할 때만 confirm 가능 |
| H intent success → L commit ambiguous | PREPARED는 confirmed checkpoint 아님. absent/partial L은 deny, 자동 rollback/reuse 없음 |
| H가 confirmed successor를 보이는데 L이 missing/old | 정상 순서상 불가능. corruption/rollback/compromise로 차단, 새 append로 맞추지 않음 |
| H confirm 후 response return 전 crash | same canonical operation의 historical result replay 가능. current status·no pending을 다시 읽으며 새로운 registration/consume capability를 재발급하지 않음 |
| source close/lease/restart 불명 | correlation handle 무효. cached facts로 계속하지 않음 |

same operation ID + same canonical fingerprint는 stored outcome 조회이며 새 event/권한 발급이 아니다. same ID + 다른 fingerprint는 conflict, 다른 installation/deployment/lineage/L/H는 deny다. TTL은 pending을 지우거나 old authority를 unused로 바꾸지 않는다. cancelled/superseded/revoked/expired authority의 과거 수학적 서명은 새 mutation에 사용할 수 없다.

## 10. Rollback·삭제·clone·보장 한계

| 공격/상황 | 판정과 전제 |
|---|---|
| L만 과거 copy로 restore | intact current H의 revision/head/pending barrier와 불일치하므로 deny |
| app DB old snapshot | A/L/H authority에 영향 없음. 새 first 판정 불가 |
| target journal 삭제 | L/H의 prior registration/consumption 보존, 새 GENESIS deny |
| L 삭제 후 새 L | exact identity + revision 1 anchor + H mapping/head mismatch. ID 재사용/새 UUID 모두 deny |
| exported P만 rollback | live H sequence/head와 불일치해 deny. P만 읽는 eligible reader 없음 |
| authoritative H만 rollback | L이 더 앞선 confirmed event를 보존하면 mismatch deny. 그러나 H의 마지막 PREPARED만 rollback되고 L이 아직 변하지 않았다면 두 관측만으로 탐지할 수 없음: 독립 H custody의 침해에 해당 |
| L + P/cache를 함께 과거로 restore | independent live H가 intact이면 deny |
| L과 H의 일부 서로 다른 prefix로 rollback | tuple/sequence/epoch/domain/pending 불일치 deny |
| L과 authoritative H/control history를 같은 유효 과거 상태로 함께 rollback | 남은 독립 최신 관측이 없으면 탐지 불가. key를 그대로 두어도 마찬가지이며 signed chain만으로 보장한다고 주장하지 않음 |
| config/app/installation clone | fresh installation proof 및 canonical domain mapping·하나의 H writer order 요구. 다른 target conflict. 모든 proof/H/L 복제는 아래 경계 |

보장은 **ADR-076의 intact independent governance custody와 trusted cooperating writers** 아래의 L/P/app/journal rollback에 대한 것이다. H 자체의 durable state가 공격자에 의해 silently rewind되지 않는다는 것이 독립 high-water authority의 trust boundary다. H rollback을 L과의 불일치로 발견할 수 있는 경우에도 모든 시간창에서 탐지한다고 확대하지 않는다. 모든 L/H/private root material의 privileged rollback은 물론, 일관된 과거 L/H authority state만 함께 복원하는 공격도 완전 방어 밖이다. hardware counter·remote consensus·제3의 변조 불가 witness를 요구하지 않으며 있다고 가정하지 않는다.

이는 failure 감지 가능 범위와 out-of-bound compromise를 명시한 ADR-076/107의 유지이지 공격을 허용하는 fallback이 아니다. 알려진 source loss/restore/compromise는 무조건 unavailable/UNCERTAIN이다. 이미 알려진 최신 상태를 의도적으로 낮추는 관리 복원은 금지한다. 더 강한 H 자체 anti-rollback이 제품 요구가 되면 별도 hardware/remote authority Decision 없이는 BLOCKED다.

## 11. Retention·rotation·Recovery·보안

A/domain mapping, 모든 L/H events, cancelled/superseded/consumed/uncertain facts와 identity tombstones는 V1에서 **무기한 보존, 자동 GC 0**이다. installation/journal/app 삭제와 독립이며 retire도 namespace를 재사용하지 않는다. 안전한 export/backup은 원본 history를 제거하지 않는다. 복원은 별도 current H와 exact 연결을 검증해야 하며 H backup restore 자체를 '현재 H'로 자동 승인하지 않는다.

root rotation은 기존 ADR-076 외부 designation update/독립 fingerprint 대조와 정상 교차서명 원칙을 보존하고 global revision/old epochs/aliases를 유지한다. compromised/lost key는 old signature만으로 successor를 만들 수 없다. exact transition intent와 independent human 재지정 evidence가 필요하며 eligibility 불명은 stop이다. 다른 purpose verifier나 target journal ACTIVE 상태로 A/H의 최초 authenticity를 추정하지 않는다. consumed history를 rotation으로 reset하지 않는다.

Recovery/Transfer는 old lineage 삭제·fresh commissioning·barrier 해제 권한이 아니다. 별도 authority가 정의되기 전에는 RECOVERY_REQUIRED/참조 보존만 가능하다. 정상 first commissioning을 위해 Recovery Decision을 미리 요구하지 않지만 장애 후 가용성을 포기한다.

Public durable facts는 opaque identity/digest/revision/epoch/public fingerprint/event/status/evidence references다. 공개 인터넷 배포 대상이라는 뜻은 아니다. private key/credential/raw WebAuthn/secret/raw OS identity/ACL/native handle/실제 private path/human 원본은 public ledger나 오류에 넣지 않는다. machine error는 안전한 범주만 반환하며 stack/raw source leak을 막는다. 서명은 transport integrity, human/위임/currentness/custody는 별도 검증이다.

## 12. 다음 구현 unit과 완료 경계

다음 작업은 **IBLA Ledger / Independent Checkpoint Persistence Foundation**이다. scope는 immutable public facts·operation index·projection/CAS, independent H control state(PREPARED/CONFIRMED/UNCERTAIN), exact replay/conflict 및 두 store crash/rollback tests, unavailable production ports다. 별도 external store schema version과 기술 backend/encoding/bounds를 구현 PR에서 고정하고 검증한다. 실제 A/human/key provisioning·production authentication 없이 disposable fixtures로 persistence 불변식을 검증할 수 있다. fixtures는 operational authorization이 아니다.

commissioning origin/current source의 authentic verifier와 lifetime capability는 그 Foundation 다음이다. 이후 Initial Authorization wire/TTL·writer·consume, Production Journal Provisioning/GENESIS 순서다. 다음 구현에서 full registration capability, GENESIS 또는 실제 production data를 같은 범위에 섞지 않는다.

이번 code/schema/migration delta 0. Alembic 20260918_0037 유지. Phase 9 0/18 및 기존 Phase 진행률 보존. Anchor/H/L persistence, source verifier/capability, Initial Authorization, Provisioning/GENESIS는 NOT IMPLEMENTED, Production Authentication/Activation은 UNAVAILABLE다. 실제 user DB/journal/credential/private key/production filesystem 접근 0이다.

장점은 원본 외부 commissioning과 current coverage의 소유자가 분리되고 stale prefix·응답 유실·pending write의 실패 정책을 구현 가능한 형태로 좁힌 것이다. 비용은 독립 keeper custody, complete-domain history 검사, prewrite barrier 이후 실패 시 수동 중단이다. stronger anti-rollback, remote/multi-root, retention 삭제, Recovery/Transfer 또는 trust-purpose 변경 시 재검토한다. 최초 계약 작성은 Draft PR에서 종료했다. 후속 최종 감사와 Ready·병합 상태는 [PR #197](https://github.com/DohaStudio/DohaMusic/pull/197)을 따른다.
