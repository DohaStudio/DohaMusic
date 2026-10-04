# ADR-112: IBLA Registration Attempt Durable Boundary and Restart Contract

> 상태: [설계 결정 — DECIDED — Writer IMPLEMENTED FOUNDATION (작업 브랜치)]
> 작성일: 2026-10-04
> 최종 수정일: 2026-10-04
> 기준 develop: 9ad483d0ae15ff6e185ef67c107d1a937066f222 (#201 merged)
> 구현 준비 판정: IMPLEMENTATION_READY — Registration Commit Writer의 pre-PREPARED/restart/crash semantics만
> 관련 PR: 이 Decision은 Draft 제출에서 종료한다. Ready/merge는 이번 작업 범위가 아니다.
> 관련 결정: [ADR-107](ADR-107-independent-bootstrap-lineage-authority.md), [ADR-108](ADR-108-ibla-anchor-coverage-ledger-checkpoint-contract.md), [ADR-109](ADR-109-ibla-ledger-independent-checkpoint-persistence-foundation.md), [ADR-110](ADR-110-ibla-authentic-source-first-registration-contract.md), [ADR-111](ADR-111-ibla-registration-commit-authority-post-boundary-contract.md)
> 검증: [Decision validation](../10-operations/ibla-registration-attempt-restart-contract-validation.md)

> 현재 구현 상태 (이 작업 브랜치): ADR-111/112 Registration Commit Writer·v2 L/H·original frame/forward reconciliation Foundation을 구현·검증했다. [Writer 검증 보고서](../10-operations/ibla-registration-commit-writer-validation.md)를 따른다. 아래 NOT IMPLEMENTED/docs-only/Draft 제출 문구는 최초 Decision 당시 이력이며 이번 Writer 구현 또는 production 완료를 뜻하지 않는다. 후속 develop 병합은 PR 기록으로 확인한다.

## 1. 배경과 재현된 모순

ADR-111 §5·§8의 순서는 process-local capability delivered → fixed Writer callback → H PREPARED → L REGISTRATION_COMMITTED → H CONFIRMED다. §9는 delivered 후 prepare 전 불명 restart에서 같은 operation의 fresh permission을 거부하지만, delivered 직후 process exit는 L/H에 아무 fact도 남기지 않는다. previous handoff와 never handed off의 retained inputs가 동일하므로 이 거부 조건을 authoritative하게 구현할 수 없다.

미커밋 prototype의 test_unknown_restart_before_prepare_cannot_retry_original_operation은 spawned child가 delivered-before-prepare에서 os._exit(0)한 뒤 A/C/mapping/L/H bytes가 모두 같은 것을 확인했다. 새 process가 같은 R/Q/operation으로 fresh observation/proof/cap을 만들어 다시 등록했고, 기대한 IblaDenied가 발생하지 않았다. 실제 JUnit은 tests 1 / failures 1 / errors 0 / skipped 0, 1.547s이며 pytest exit 1이다. 원 opaque handle 복원이 아니라 같은 logical operation의 새 cap 실행이었다. Full Backend는 중단되어 PASS가 아니다. prototype은 authority나 production 구현 증거가 아니다.

이 Decision은 그 순서와 restart 기준만 고친다. IA issue/consume/cancel, INITIAL_SEALED, Provisioning/GENESIS, authentication/activation, recovery/transfer는 설계·구현하지 않는다.

## 2. 선택과 기존 ADR의 관계

**Option B를 선택한다: 검증된 exact registration candidate의 H PREPARED를 먼저 durable commit하고 확인한 뒤 capability를 최종 one-shot handoff한다.** 별도 durable token/intent store, 새로운 H state, event field, schema/index를 추가하지 않는다. ADR-111의 이미 결정된 external physical v2와 canonical registration event를 그대로 사용한다. 현재 develop 구현은 ADR-109 v1이며 Writer는 NOT IMPLEMENTED다. 모든 digest wire는 기존 require_digest와 같은 sha256:<소문자 hex 64자>를 유지한다. ADR-111 §4의 64 hex 표현은 접두사 없는 신규 형식으로 해석하지 않는다.

ADR-111 §2 authority-chain ordering, §5 final handoff와 deadline 기준, §8 steps 1~3, §9 pre-PREPARED/restart/prepare-response-loss 행 및 이에 의존한 구현 준비 판정을 이 ADR로 **부분 대체**한다. 나머지 exact writer/R/Q, event/profile, physical v2, L durable POST, H independent confirmation, post-L reconciliation은 보존한다. ADR-111 원문은 역사로 남긴다.

ADR-107의 registered lineage 이후 IA 목적 및 INITIAL_SEALED consume와 ADR-108의 purpose/독립 custody를 보존한다. ADR-109의 CONFIRMED → PREPARED → L append → CONFIRMED, repository flush-only/owner commit, pending 무기한 보존과 rollback 한계를 보존한다. ADR-110의 opaque prerequisite, one mint/one delivery, authentic complete source/PRE 8 AND, 최대 원 수명, read-only verifier를 보존한다. 등록 Writer 통합에서만 마지막 전체 PRE read를 **자기 H prepare 직전** 수행하며, 자기 PREPARED 뒤 final handoff에는 아래 operation-specific checks를 적용한다. 이는 ADR-110 §9의 매 handoff 전체 PRE 재확인을 등록 Writer에 한해 명시적으로 상세화한다. 다른 consumer의 기존 read-only handoff는 그대로다. H mutation은 HKeeperOwner의 등록 예약 동작이고 Source Verifier/Capability mint/read adapter가 H write authority를 얻는 것이 아니다.

## 3. A/B/C 비교와 기각 이유

여기 Option A/B/C는 이 ADR의 대안이며 ADR-111 §2의 같은 문자와 다른 구분이다.

| 기준 | A: 별도 durable handoff/intent fact | B: H PREPARED 선행 (선택) | C: 기존 handoff 선행 + pre-PREPARED fresh retry |
|---|---|---|---|
| ADR-109 compatibility | 별도 authority와 H/L correlation 결정 필요 | 기존 exact pending/control 전이 재사용 | H/L protocol 유지 가능 |
| ADR-110 capability semantics | ephemeral 객체 외 durable consumption 결박 추가 | opaque prerequisite/one delivery 유지; 자기 prepare 후 checks 상세화 | 객체 one-shot 유지하나 동일 logical handoff 반복 허용 |
| ADR-111 목적 | 등록만으로 제한 가능하지만 새 persistence 필요 | exact Writer/R/Q + 등록 1건 유지 | unknown delivered restart 제한을 완화 |
| durable authority | 새 독립 custody store·purpose·canonical record 필요 | 기존 H whole control history의 full candidate | PREPARED 전 delivery evidence 없음 |
| restart 구분 | 새로운 exact fact가 있어야 가능 | reserved attempt / no durable attempt 구분; delivery 여부 추론 불필요 | previous delivery를 구분하지 않고 새 실행 허용 |
| 최소 권한 | 새 write/read/retention 권한 추가 | keeper의 기존 prepare 권한, cap/R/Q 검증 필수 | 추가 store 없음; PRE handoff 반복 노출 |
| self-enrollment | 외부 pins 없으면 금지, 새 store도 자기 승인 불가 | 기존 independent originals/delegation만 승인 | fresh original verification 필수 |
| circular trust | R/Q/cap 외 별도 fact로 권한 생성 금지 | H는 승인 결과 예약일 뿐 cap/R/Q 대체 불가 | memory delivery가 durable 권한은 아님 |
| replay | 새 fact·H/L operation correlation 필요 | pending의 exact fingerprint 1개, old handle 재전달 0 | pre-PREPARED 같은 R/Q 새 observation 반복 가능 |
| crash safety | 새 fact/H prepare 사이 orphan 처리가 추가됨 | pre-handoff orphan은 retained unavailable; original live frame만 L 1회 | PREPARED 이전 delivered 이력은 버림 |
| rollback | 새 store 독립성·anti-rollback 별도 결정 필요 | ADR-109 마지막 PREPARED/consistent rollback 한계 유지 | 동일 rollback 한계, delivery 사실도 영속 안 됨 |
| 구현 복잡성 | 가장 큼: schema/owner/atomicity/cleanup/lifetime | 기존 H와 private provider/Writer의 순서 변경 | 작으나 durable attempt one-shot 의미 약화 |
| 새 persistence | 필요; generic token store는 불필요하게 범위 확대 | 0; 기존 계획된 v2 외 추가 DDL 0 | 0 |
| production custody | 새 accepted custodian·store provisioning 필요 | 기존 독립 H custody 유지, 실제 production 미검증 | 기존 custody 유지, 반복 승인 정책 수락 필요 |

A는 registration-only purpose와 R/Q/cap/writer/operation exact binding, 한 번 기록, 영구 보존, expiry와 fact retention 분리, crash/replay/rollback 대조가 필요하다. temp/cache/log/app row는 그 store가 될 수 없으며 cleanup/GC/reset을 허용할 수 없다. B로 해결 가능한데 새 persistence/authority를 만드는 비용 때문에 기각한다. C는 double durable registration을 CAS/index로 막을 수 있지만 previous delivered를 새 process에서 구분하지 않으며 원래 logical handoff 제한을 완화한다. 최종 delivery 앞에 기존 durable barrier를 두는 B가 더 작은 권한 변경이므로 C를 기각한다. B도 boundary 전 fresh observation은 허용하지만, 그 구간에서는 **final handoff 자체가 아직 발생할 수 없다**.

## 4. Exact durable boundary와 one-shot identity

**등록 시도는 validated exact registration candidate를 담은 H PREPARED가 HKeeperOwner의 실제 H root transaction에 durable commit되는 순간 내구화된다.** 응답 수신이나 memory delivered가 boundary가 아니다. final delivery에는 그 commit 성공과 별도 full-H/L read 확인이 모두 필요하다.

boundary 전 crash: original handle/proof/lease/frame는 폐기된다. 새 process는 trusted existing full L/H + retained independent originals/current delegation을 새로 검증하고 L rev1/H CONFIRMED/pending null/해당 operation의 과거 H control 부재와 PRE 8 AND를 모두 만족하면 새 observation/challenge/proof/cap으로 새 실행을 시작할 수 있다. R/Q가 아직 current하고 exact expected tuple이 같으면 root가 부여한 registration_id/operation_id는 유지할 수 있다. 자동 retry/old handle replay가 아니며 새 fresh 검증 없이는 진행할 수 없다.

boundary 후 crash: H pending은 exact reserved attempt의 durable evidence다. final delivery가 있었는지 없어도 동일 정책이다. 새 cap/mint/새 Writer permission/다른 R/Q/UUID로 pending을 채우거나 우회할 수 없다. 실제 L fact 대조와 이미 durable한 L의 H forward confirmation만 가능하다. L 부재면 retained unavailable이며 availability를 위해 예약을 지우지 않는다.

one-shot은 **둘 다**다. process-local original opaque object는 one mint/one final delivery로 끝나며 restart/export/deserialize/copy로 복원하지 않는다. durable logical registration attempt는 domain Binding 11 + R.registration_id + R.operation_id에 속한, original observation_id를 포함한 **full canonical event와 operation fingerprint**가 H에 예약되면 다른 실행으로 대체하지 않는다. H PREPARED의 control predecessor/sequence와 retained full event가 정확한 execution identity다. UUID 존재/일치만으로 권한을 만들지 않는다. pre-boundary에 폐기된 volatile observation은 새 observation과 다른 실행이며 아직 durable attempt가 없다. POST fact 조회에서는 저장된 observation_id/recorded_at/candidate를 그대로 사용하고 재생성하지 않는다.

## 5. 검증 → prepare → final handoff → append → confirm

1. original provider lock과 원 domain lease 아래 minted-but-undelivered cap의 exact registry/provider/observation/pid/native-thread/consumer binding을 검증한다. authentic held originals/native custody, fresh installation proof, complete inventory/scopes, whole current L/H 및 PRE 8 AND를 재검증한다. R/Q signatures/purpose/independent provenance/current root·initializer·custodian delegation, exact Writer instance를 확인한다. caller-created DTO/flag나 generic repository caller는 이 단계에 들어올 수 없다.
2. fixed Writer의 private 준비 동작은 original registry record로 R/Q와 immutable candidate를 결박한다. ADR-111 §6의 full event, R/Q digests, observation UUID, expected L/H/confirmed와 writer refs, fingerprint/size/depth를 compile/parse한다. 이 동작은 final consumer invocation/append permission이 아니고 새 transferable authority mint도 아니다. preparing 중 재진입/duplicate handoff는 deny한다. 모든 source verification read pass를 닫는다.
3. 준비 시작 monotonic 시각부터 deadline = min(original cap deadline, 준비 시작+30초)로 고정한다. 기존 callback+30초 기준을 이 시각으로 옮겨 H 준비를 포함하며 final delivery 때 reset하지 않는다. wall/mono rollback, R/Q/A/C expiry, source/lease/thread/delegation/native loss는 invalidate한다. keeper는 cap의 original private preparation frame와 R/Q currentness를 actual H commit 직전에 다시 확인한다. final delivered는 아직 false다.
4. HKeeperOwner는 별도 query_only whole L로 R.expected_l_head를 확인하고 actual H의 R.expected_h_head/CONFIRMED(expected_h_confirmed)/no pending을 확인한다. 기존 H state transition/CAS로 exact candidate PREPARED를 flush한 뒤 H owner가 durable commit한다. H 쓰기 및 independent L read를 종료한다. commit 응답 불명/exception이면 final handoff와 L write를 하지 않고 whole observation을 abandon한다. keeper 권한만으로 registration candidate를 prepare할 수 없으며 cap/R/Q 검증 없는 private 등록 prepare는 거부한다. 후속 v2 public/generic H prepare도 REGISTRATION_COMMITTED candidate는 IBLA_UNAVAILABLE로 거부한다. 기존 prepare/CAS/flush mechanics는 원 cap registry의 preparing frame와 current R/Q/fixed Writer를 대조한 private 등록 경로에서만 재사용한다. ADR-109의 기존 v1 public mechanics는 변경하지 않으며 그 compare result는 승인 입력이 아니다.
5. 별도 query_only full H/L pass로 committed exact 자기 PREPARED의 full envelope/fingerprint/operation/predecessor/confirmed tuple과 변경 없는 L rev1을 확인하고 pass를 닫는다. source/lease/native/proof/current delegation/deadline을 계속 확인한다. 자기 PREPARED를 이유로 전체 PRE의 H CONFIRMED 조건을 다시 요구하거나 새 cap을 mint하지 않는다. original registry는 준비를 성공시킨 같은 synchronous execution frame에만 이 operation-specific 경로를 연다. 외부 pending, 다른 head, 과거 동일 candidate/prepare replay result만으로 frame를 만들 수 없다.
6. 같은 lock/frame에서 delivered-and-delivering을 단조롭게 표시하고 fixed exact Writer consumer를 **한 번** 호출한다. 그 consumer에는 original opaque cap 하나만 전달한다. 전달 직전 검증 실패, callback exception/timeout/release는 original cap/frame를 invalidate하고 H pending을 남긴다. H PREPARED는 cap/R/Q를 만들어 내지 않고 L write permission도 전달하지 않는다.
7. 바로 그 live callback만 H read pass 종료 후 actual L BEGIN IMMEDIATE/root SessionTransaction을 열어 current held source/lease/deadline/R/Q/delegation, exact H candidate, L whole history/rev1 no-prior/expected head/operation absence를 검증한다. private append는 delivered-and-delivering frame와 actual transaction identity에 결박된다. unique event/operation + single registration index + expected-head CAS를 한 L transaction에 flush/commit한다. L root transaction 종료/불명 이후 append 재시도 0. H와 L write transactions는 겹치지 않는다.
8. L durable commit이 irreversible POST다. live L permission은 끝난다. independent HKeeperOwner가 별도 실제 committed whole L을 읽고 exact pending/event/head를 대조할 때만 H CONFIRMED로 전진한다. H 응답 불명/response loss는 기존 facts 조회와 forward confirmation으로만 해소한다. audit result는 read-only이며 IA/GENESIS authority가 아니다.

PREPARED는 등록 완료, POST, IA authority, GENESIS authority가 **아니다**. 검증된 exact pending registration attempt의 durable 예약 증거다. final delivery 전 crash가 만든 orphan도 정상적으로 차단된 예약이며 새 process가 consumer에 전달할 권한을 주지 않는다. read-only Source Verifier Foundation과 generic consumer stub의 mutation 0 계약은 유지한다. registration prepare mutation은 후속 Writer 구현 내부의 별도 owner 책임이다.

## 6. Restart matrix와 ambiguity

아래 retry는 새 fresh 실행 또는 기존 사실 조회를 뜻하며 original cap replay/L append 재시도는 전 행에서 금지한다. accepted independent custody와 full-history 보존이 전제다.

| crash/실패 시점 | durable authority | retry | 새 cap | reconciliation | duplicate registration |
|---|---|---|---|---|---|
| verification 전 | commissioned L1/H CONFIRMED | fresh 전체 검증부터 가능 | 조건 충족 후 가능 | full source/L/H 검증 | CAS/index/lease로 0 |
| verification 후 | volatile verified/cap만; L1/H CONFIRMED | 새 observation/proof부터 가능 | 새 cap 가능 | 같은 originals·currentness 재확인 | 0 |
| H PREPARED 전 | durable attempt 없음, final delivery 없음 | fresh 검증 후 가능 | PRE 8 AND이면 가능 | full H history에 과거 op도 없어야 함 | 0 |
| H prepare commit 응답 불명 | durable 여부 UNKNOWN | 같은 frame abandon; 자동 retry 금지 | restart full facts가 no attempt를 입증할 때만 가능 | pending 있으면 다음 행; 없고 trusted whole history/L1/H CONFIRMED exact이면 fresh 검증 | 0 |
| H PREPARED durable 후 final delivery 전 | exact H pending 예약 | L append retry 불가 | 불가 | L read; 부재면 orphan retained unavailable | 0 |
| capability final handoff 후 | 같은 H pending + volatile delivered | 불가 | 불가 | L 존재 여부 대조; absent이면 retain | 0 |
| L append 전 | H pending, POST 없음 | 불가 | 불가 | 같은 live callback만 첫 L 시도 가능; restart는 unavailable | 0 |
| L append ambiguous | H pending + L 여부 UNKNOWN | L 재시도 불가 | 불가 | full existing L exact event면 POST, absent면 retained unavailable | 0 |
| L durable 후 | exact REGISTRATION_COMMITTED; POST | stable fact 조회만 | 불가 | keeper forward confirm만 | 0 |
| H CONFIRMED 전 | POST + H pending/UNCERTAIN | fact 조회/keeper confirm만 | 불가 | actual whole committed L/H exact correlation | 0 |
| H CONFIRMED 후 response loss | POST + independently confirmed L/H | same ID/fingerprint read-only result | 불가 | historical result와 fresh current H 구분 | 0 |

prepare 응답 유실 때 **pending null만**으로 never-prepared를 주장하지 않는다. 기존 full H control history의 operation/fingerprint, native identity/catalog/integrity, current independent custody, complete L 및 exact R expected tuple을 함께 확인한다. 신뢰된 history에 durable attempt가 없으면 B의 순서상 final delivery도 없었던 것으로 fresh 실행을 허용한다. 이 규칙은 ADR-111의 무조건 restart H-absence 거부를 명시적으로 대체한다. 어떤 missing/unknown/corrupt source, known restore/rollback/compromise, 설명 안 되는 head 변화도 unavailable다. same-process known rollback도 old cap 재전달이 아니라 새로운 전체 observation만 허용한다.

H 마지막 PREPARED만 되돌리거나 L/H를 일관된 과거 prefix로 복원한 공격은 ADR-109/110처럼 **탐지 NOT GUARANTEED**다. SQLite sync를 준수하는 OS/VFS/device와 accepted history retention/custody 가정 안에서만 durable distinction을 주장한다. hardware anti-rollback/remote consensus/power-loss 실측이나 privileged compromise 방어를 추가하지 않는다. 이를 무조건 authoritative absence로 과장하지 않는다.

## 7. Orphan·stale·reset·duplicate

H PREPARED 뒤 source/delegation/proof/lease/clock/deadline이 stale되면 final handoff 또는 L commit 이전 검증에서 중단한다. pending은 PREPARED 또는 keeper의 기존 명시 UNCERTAIN으로 영구 retain하며 새로운 H state UNKNOWN을 만들지 않는다. callback이 살아 있고 모든 checks가 유효할 때만 동일 frame의 첫 L append가 가능하다. stale/ended frame, restarted process는 이어 쓰지 않는다. L already durable이면 stale 또는 응답 실패가 POST를 취소하지 않는다.

orphan pending은 TTL expiration/cleanup/cancel/reset/새 A/epoch/빈 L/H/Recovery/Transfer로 없애지 않는다. 승인 R/Q 만료는 과거 durable 사실을 삭제하지 않으며 exact historical fact 조회와 독립 keeper의 existing-L confirmation에는 새 registration write permission이 필요 없다. L가 없으면 keeper가 가상의 commit을 confirm하거나 새 L를 append할 수 없다. availability 회복 정책은 이번 Decision 밖이다.

최대 1 REGISTRATION_COMMITTED는 fixed L revision 1 predecessor, no-prior whole-history eligibility, domain lease, expected-head CAS, UNIQUE(operation_id), unique registration/event ID, ADR-111 single-registration partial index와 H exact full candidate correlation으로 유지한다. 같은 operation+다른 fingerprint/registration+다른 operation은 conflict다. generic public append 거부도 유지한다. durable 등록 뒤 cap resurrection 및 PRE 복귀는 모든 경로에서 금지한다. 행 삭제나 app DB rollback은 authority가 아니다.

## 8. 15/15 implementation-ready 감사

| # | 질문 | 결정된 답과 근거 |
|---|---|---|
| 1 | handoff/PREPARED 순서 | §5: PREPARED durable 확인 후 final handoff |
| 2 | durable boundary | §4: actual H root transaction의 exact PREPARED commit |
| 3 | boundary 전 crash retry | §4·6: fresh complete verification의 새 실행 허용 |
| 4 | boundary 전 새 cap | §4: originals/currentness/PRE 8 AND, 새 proof/lease/observation 필요 |
| 5 | boundary 후 새 cap | §4·7: pending 또는 POST면 거부, 우회 금지 |
| 6 | restart 이전 attempt 식별 | §4·6: trusted full H control history/full candidate + actual L |
| 7 | exact binding | §4·5: Binding 11/R/Q digests/writer/IDs/observation/event fingerprint/predecessor |
| 8 | orphan PREPARED | §7: retained unavailable, 자동 이어쓰기 없음 |
| 9 | stale source | §7: frame invalidate, pending retain; already POST 불변 |
| 10 | reset/cancel | §7: 불허, TTL cleanup/새 A 우회도 불허 |
| 11 | durable one-shot | §4: 객체 one delivery + durable exact reservation 한 execution |
| 12 | duplicate defense | §7: CAS/fingerprint/unique registration/operation/domain lease/H correlation |
| 13 | ADR-109 호환 | §2·6: 기존 상태 전이/owner/독립 read/retention/rollback 한계 보존 |
| 14 | ADR-110 의미 | §2·5: opaque PRE prerequisite/read-only verifier 유지, Writer 통합 자기 prepare 검사만 상세화 |
| 15 | 추가 Decision 없이 crash path 구현 | §5~7의 frame/ordering/deadline/ambiguity/matrix로 가능; 새로운 store/field 없음 |

15/15 답을 확정했다. **IMPLEMENTATION_READY**는 Registration Commit Writer의 pre-PREPARED/restart/crash semantics에 한한다. production readiness 또는 IA/Provisioning/GENESIS 구현 준비 판정이 아니다.

## 9. 영향·이행·검증·재검토

변경은 docs-only다. external v2 기존 설계 외 신규 DDL/fields/migration/API/app metadata 변화 0. Writer **NOT IMPLEMENTED**, 실패 prototype을 완료 증거로 계산하지 않는다. Phase 9 **0/18, 0%**를 유지한다. runtime source/test/workflow를 이 PR에 포함하지 않는다.

현재 실패 test와 JUnit을 원 prototype 브랜치에 그대로 보존한다. 후속 구현 PR은 pre-PREPARED crash case를 삭제/약화하지 않고 B의 순서에 맞춰 확대한다: prepare 전 fresh retry 성공, prepare durable/final delivery 전 orphan 거부, delivered 시 H fact 존재, prepare response-loss durable/absent 분기, post-PREPARED stale/timeout, ambiguous L와 post-L fact-only reconcile, concurrent no duplicate를 실제 process-exit/reopen로 검증한다. 현재의 delivered-before-prepare failpoint는 불가능 순서가 되었음을 검사하는 regression으로 남겨야 하며 단순 삭제하거나 xfail로 감추지 않는다. 기존 failed JUnit은 역사적 Decision evidence이고 후속 수정 test의 PASS를 대신하지 않는다.

이행은 신규 Writer 구현에서 순서/frame를 적용하는 것이다. 이미 production에 사용된 Writer가 없으므로 delivered memory를 backfill하지 않는다. source/physical v2 지원은 ADR-111의 동일 구현 단위에서 수행하되 actual production offline maintenance/custody는 여전히 미구현이다. 이 Decision이 별도 검토·병합되어 develop authority가 된 뒤 Writer prototype을 재감사하고 focused/direct/full Gates를 새로 실행한다. 이번에는 한국어 docs commit/push/Draft PR까지만 수행한다.

새 retry/resume/reset/cleanup, separate consumer/async delivery, 새로운 persistent marker, stronger anti-rollback, production custody/availability 복구가 필요하면 새 Decision으로 재검토한다. 비밀정보/private sources/user DB/Artifact/production credential에 접근하지 않는다. AI 실행/실험 보고서는 필요하지 않다.
