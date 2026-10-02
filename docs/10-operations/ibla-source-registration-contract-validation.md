# IBLA Source / First-Registration Contract — Authority Audit 및 문서 검증

> 문서 상태: [검증 기록 — docs-only Decision, 구현·운영 비활성]
> 작성일·최종 수정일: 2026-10-02
> 기준 develop: dd6181a6eebff3001e171ba167055af760272fb7 (#198 merged)
> main: 63633d462043ad3ba78fee92473d19e90c361431
> 작업 branch: docs/ibla-source-registration-contract
> 관련 문서: [ADR-110](../11-decisions/ADR-110-ibla-authentic-source-first-registration-contract.md), [Phase 9 DoD](../DoD/Phase-09.md), [이전 public persistence 검증](ibla-persistence-foundation-validation.md)

## 1. 범위·사실·판정

직전 MISSING_DECIDED_CONTRACT의 Authentic Source 승인 입력/coverage와 First-Registration eligibility/capability handoff를 한 Decision으로 상세화했다. Authority 변경이 필요한 새 root를 발명하지 않고 ADR-076/107/108의 기존 root·명시 initializer/commissioning originals·L/H를 사용한다. 기존 policy-purpose verifier/source를 IBLA로 승격하지 않는다. 아래 새 purpose-specific A/C/I read profile은 이번 설계 결정이며 현재 실행 가능한 source reader나 실제 provisioning 증거가 아니다.

IMPLEMENTATION_READY는 다음 **Authentic IBLA Source Verifier + First-Registration Capability Foundation**의 restricted read-only 구현 준비다. 첫 등록 writer/registered receipt/Initial Authorization/GENESIS 준비 완료가 아니다. registration event 지원이 없는 ADR-109 reader는 그 history를 unavailable로 거부할 수 있으므로 PRE-only verified capability 구현은 L/H schema 변경 없이 시작한다.

기준 원격 fetch에서 develop/main은 위 값과 같았다. 격리 worktree의 새 docs branch로 작업했으며 root의 frontend/next-env.d.ts 사용자 수정·untracked files·기존 worktrees/stashes 및 변경 없는 feat/ibla-source-verifier-registration-capability를 보존했다. 기존 #171/#130을 수정하거나 병합하지 않는다. 사용자 요청에 따라 docs Gate 통과 시 Draft 제출까지만 진행한다.

## 2. Authority Audit (실제 ADR/source 책임 대조)

요청한 20 ADR과 관련 구현을 읽고 다음 각 행의 provenance/guarantee 한계를 대조했다. ADR-084/087/088/096도 source 최초 신뢰·원본 confirmation/인프라 재사용을 구분하기 위해 추가 대조했다. 역사적 ADR의 당시 미구현/Draft 설명은 현재 완료 claim으로 고치지 않는다.

| ADR | purpose | authoritative fact | provenance | lifetime | holder | transaction owner | currentness guarantee | replay guarantee | IBLA 재사용 | 재사용 금지 |
|---|---|---|---|---|---|---|---|---|---|---|
| 076 | External root / exact first binding | accepted designation와 root intent; 원래 governance | 독립 human/fingerprint ceremony | external original + fresh status | governance/initializer | ceremony·caller DB/external writer 분리 | fresh designation/status/possession 필수 | 서명 receipt만 반복 가능, one-time 아님 | root/Ed25519/JCS/pins/governance boundary | approval/human/key를 IBLA로 자동 승격 |
| 077 | Issuance integrity | FIRST_OWNER_BINDING_ONLY public integrity | independently supplied pin | pure check-time receipt | caller | 없음 | 현재 lifecycle 미증명 | same signature 재검증 가능 | strict parser/crypto/time bounds | approval receipt/currentness/IBLA origin |
| 082 | Windows exclusion | cooperating writer OS exclusion만 | exact scope naming/native Global mutex | pid/thread/lease/root transaction | lease owner | caller transaction; primitive commit 0 | abandoned/busy deny, proof 아님 | original registry·invalid lease 재사용 deny | native acquire/cleanup pattern; domain 이름은 explicit 확장 | Workspace lease를 IBLA domain authority로 사용 |
| 083 | Private pin transport | public facts exact comparison | fixed file/independent expectations | held same-handle context | pin reader | caller owner | transport unchanged만 | stale/foreign facts deny | ancestor/leaf/fileID/reparse/hardlink/bounded read | pin public fields/경로를 provenance로 사용 |
| 085 | Designation raw snapshot | original exact-byte digest comparison | raw original/fixed file; 당시 authenticity 미증명 | parent pin/lease/caller transaction | snapshot provider | caller owner | same-handle revalidation | exit/rejection permanent invalid | raw profile/digest/opaque snapshot pattern | snapshot 성공을 human acceptance로 사용 |
| 086 | Custody policy | root/leaf owner/protected exact DACL/ID equality | independently provisioned policy 조건 | held handle·same original lease | custody reader | caller owner; SQL 0 | handoff descriptor/ID fresh checks | restored values로 old snapshot revive 불가 | strict SID/ACL/fileID/retained cleanup | OS owner/ACL을 initializer 지정으로 사용 |
| 089 | Raw original confirmation | exact bytes/action binding; authenticity 아님 | separate fixed original leaf | parent graph/lease/transactions | snapshot provider | caller owner | same-handle reread+parents | copy/restart/restored source deny | bounded원본 profile/reread/lifetime mechanics | raw confirmation handle을 authenticated receipt로 사용 |
| 093 | Scoped policy authority integrity | INSTALLATION_POLICY_PROVISIONING_ONLY signed lifecycle | ADR-076 root pin | stateless full input chain | verifier caller | 없음 | input projection ACTIVE; completeness/root currentness 별도 | terminal/key reuse/chain forks deny | domain-separated verification/lifecycle design pattern | 기존 purpose/key authorization을 IBLA 위임으로 사용 |
| 094 | Held authenticated policy source | policy signed history verified+source binding | protected fixed history/독립 pin | parent sources/lease/root tx | source provider | caller owner | held unchanged와 ACTIVE; external completeness 별도 | foreign/stale/transaction 교체 deny | bounded signed-source read/revalidate/opaque pattern | policy source graph를 IBLA authentic bundle로 사용 |
| 097 | Policy confirmation/lineage correlation | authentic policy confirmation+ACTIVE journal observation 연결 | exact authenticated parent graph | caller+journal root tx/lease | correlation provider | 각 original owner | all parent fresh rechecks | copy/parent change permanent abandon | exact primitive correlation/digest/registry pattern | ACTIVE journal requirement를 initial commissioning root로 사용 |
| 098 | CurrentnessWitness handoff | policy admission 한 attempt의 현재 facts | 097 actual source graph | original lease/caller+journal tx | provider lifetime | 각 original owner | every use revalidation | single mint·foreign/copy/terminal deny | opaque identity/single assignment/abandon design | existing witness를 first-registration capability로 재사용 |
| 099 | Admission candidate | NORMAL_ROTATION/REVOKE/EXTERNAL_REDESIGNATION only | 098 live witness/signed candidate | attempt/correlation/lease/tx | candidate provider | commit은 future/existing Journal Owner | exact ACTIVE predecessor checks | stable candidate ≠ commit/retry 권한 | purpose/candidate/final-guard 분리 | GENESIS/empty predecessor/IBLA registration 허용 |
| 102 | Durable admission orchestration | verified external journal committed result 전달 | exact Provider/Owner/Reconciler graph | ceremony/attempt/result registry | orchestrator scope | Journal Owner만 commit/rollback | final guard·read-only reconciliation | replay는 historical result, append 0 | owner/reconciler 분리·lost response fail closed | COMMITTED_EXACT를 IBLA original authority로 사용 |
| 103 | Composition scope | existing graph wiring identity | trusted opened exact components | one ceremony/request; graph used 기록 | application root + scope | composition SQL/commit 0 | parent graph 살아 있을 때만 | used graph cross-request 재활성화 deny | scope ownership/unavailable default | READY/wiring을 production activation 또는 source proof로 사용 |
| 104 | Reviewed configuration | routing/identity comparison only | bytes + independent public expectations | immutable root input | composition caller | 없음 | actual source 미열림 | config replay는 authority 아님 | strict lexical routing/comparison | config 존재/값을 source provenance로 사용 |
| 105 | Six-role descriptors | policy sources routing only | 104 exact parsed config | immutable root input, handles 없음 | factory caller | 없음 | sources unprovisioned | descriptor 재사용에 권한 없음 | fixed role uniqueness/containment design | 기존 six role에 IBLA가 있다고 가정/descriptor를 capability로 사용 |
| 106 | Existing journal factory | existing journal v1 identity/history/open mechanics | reviewed descriptor + independently provisioned journal | runtime native handles/thread root tx | runtime/session owner | Journal Transaction Owner | actual complete existing journal read | closed runtime/foreign tx deny | existing-file/native connection/read-only pattern | GENESIS-shaped journal schema를 L/H로 사용/create fallback |
| 107 | IBLA lineage/consume Decision | external origin/complete inventory/independent registered history | 076 root + independent initializer | held registry domain lease/currentness | governance/custodian/keeper | authorized registry writer | complete retained scope/history/checkpoint | consumption irreversible, missing journal도 deny | same root·positive origin·REGISTERED_INITIAL 분리 | UNREGISTERED/absence를 eligible로 사용 |
| 108 | A/L/H coverage Decision | A origin; L full events; H independent current high water | independent commissioning/mapping/custody | same domain lease/source lifetime | read owner·각 store custodian | H→L→H separate local writer owners | whole chain+live CONFIRMED/no pending | operation replay는 권한 아님 | complete domain/read correlation/lease/order | P/cache/H CONFIRMED만으로 external origin 사용 |
| 109 | L/H persistence | public immutable history/CAS/confirmation | public Binding + caller-owned existing connections | original root SessionTransaction | caller session owner | repository commit/rollback 0 | schema/history projection; source authenticity 별도 | same operation/fingerprint historical outcome | whole L/H read/schema/codec/integrity/error categories | anchor_digest/COMMISSION/view를 authority로 사용 |

감사 source: approval_verifier, windows_serialization, windows_fact_files, private_pin_reader, designation_snapshot, source_custody, confirmation_snapshot, provisioning_authority, provisioning_authority_source, confirmation_lineage_correlation, currentness_witness_handoff, witness_lifetime, admission_attempt, durable_admission, production_composition, production_configuration, production_private_sources, production_external_journal 및 ibla/contracts·codec·repository·checkpoint·schema. primitive의 기존 typed graph를 그대로 호출해 IBLA 권한을 만들 수는 없다. crypto/strict comparison/native transport/opaque lifetime·cleanup pattern을 다음 단일 구현 PR에서 purpose-specific하게 확장한다.

## 3. 28개 implementation exit 질문

전문 계약은 ADR-110을 따른다. 각 행은 명확한 결정에 연결되며 실제 구현 테스트 PASS를 의미하지 않는다.

| 번호 | 질문 | 결정 답변 |
|---|---|---|
| 1 | 정확한 port 입력 | trusted source provider + expected scope + observation context, original designation/pins/A/C/I/mapping/L/H/fresh proof (§3~5) |
| 2 | 각 source authority | 076 external governance·initializer originals, root-signed A/I, actual L와 independent H; config/DTO 제외 (§2~3) |
| 3 | Positive Origin | external actual new scope origin + exact root A + independent initializer C/originals (§4) |
| 4 | A/L/H immutable correlation | A ID/payload digest, full Binding, independent mapping/native identity; circular digest 없음 (§3~6) |
| 5 | source currentness | whole L/live H + cooperating domain lease + same-held custody/위임/proof fresh revalidation (§5~6) |
| 6 | Complete Coverage 범위 | commissioning 이전부터 relevant scope/aliases/prior facts + domain revision 1..N + all H controls (§6) |
| 7 | unsupported history | skip 없이 IBLA_UNAVAILABLE, known verified terminal은 conflict (§6,10) |
| 8 | registration absence | root/initializer complete external inventory + whole current L; row absence 아님 (§6~7) |
| 9 | IA absence | 동일 범위에서 issued/consumed/cancelled/superseded 포함, 미지원은 unavailable (§6~7) |
| 10 | GENESIS absence | 동일 범위에서 outcome/prior binding/seal 포함, missing journal 아님 (§6~7) |
| 11 | PRE exact 조건 | independent commissioning + verified first predicate, REGISTERED_INITIAL 아님 (§7) |
| 12 | POST authoritative fact | authorized independent custodian L durable REGISTRATION_COMMITTED (§7) |
| 13 | eligibility predicate | §7의 8개 conjunction 모두 true; UNKNOWN 성공 불가 |
| 14 | capability 증명 | live exact observation의 authentic/complete/current PRE eligibility (§8) |
| 15 | capability 비증명 | IA/GENESIS/human approval/Auth/Activation/journal write/future currentness/registered receipt 제외 (§8) |
| 16 | exact binding | §8 full immutable tuple incl source/lease/proof/read owners/snapshot tuples/expiry |
| 17 | lifetime | one observation/process/thread/lease/sources/read connection owners + 최대 monotonic15분/validity, 각 query_only tx는 짧은 pass에만 존재 (§9) |
| 18 | source lifetime 종료 | derived handles 영구 stale, restored values revive 0 (§9) |
| 19 | serialization | copy/pickle/JSON/export/import/persistent token 금지 (§9) |
| 20 | replay | mint 1회/handoff 1회, new observation은 전체 재검증; durable consume 아님 (§9) |
| 21 | cross-domain reuse | original provider registry/object identity와 entire exact tuple validation (§8~10) |
| 22 | stale 차단 | release/read 중 tx 교체·불명/head/source/clock/expiry/cleanup 변화 관측 즉시 abandon (§9) |
| 23 | issuer input | opaque PRE capability 하나; issuer 자신의 registration/root intent prerequisites 별개 (§9) |
| 24 | raw 재조립 우회 | raw A/L/H/head/lineage/eligible overload/fallback 없음 (§3,9) |
| 25 | authority mutation | L/H/appDB/journal/registration/GENESIS 모두 0 (§10) |
| 26 | partial state failure | 0 authoritative mutation, resource cleanup 불명 retained quarantine (§10) |
| 27 | self-enrollment | UUID/empty store/config/absence/self-pin/self-signature로 authority 생성 불가 (§11) |
| 28 | circular trust | external original/pins/initializer→A/L/H 단방향; H/L/DTO 자기승인 없음 (§2,11) |

28/28 contract answers 존재. 판정: IMPLEMENTATION_READY. Source authenticator의 독립 원본/pin·서명·provenance 검증을 bool/DTO로 생략하거나 unsupported scope를 제거해서 이 판정을 이용하면 안 된다. 다음 구현은 source-specific read adapters/codec/lease/capability를 한 PR에서 구현·negative 검증하고 production unavailable를 유지한다. 새로운 중간 Foundation 없음.

## 4. 후속 구현 acceptance matrix (이번 미실행)

| 영역 | 성공 조건 / 필수 negative |
|---|---|
| external origin | test-only independent root/initializer/custody originals + valid signed A/C + I + mapping. A digest/file/COMMISSION/H CONFIRMED만 있는 입력, public bool/DTO, self-pinned signer, wrong purpose 거절 |
| encoding/clock | exact fields/JCS/Ed25519/domain/time/digest. duplicate/unknown/null/wildcard/bool/float/unsafe counter/oversize/malformed/expiry/clock rollback 거절 |
| immutable binding | domain/deployment/installation/proof/lineage/journal/A/L/H/designation/epoch/mapping/native identity 각각 교체·overlap·ambiguous origin 거절 |
| scope/absence | complete positive new scope originals+I/full L. partial scopes, imported/legacy/alias/unknown/prior registration/IA/GENESIS/binding/seal 및 retained external history 누락 거절 |
| L/H coverage | full revision 1..N/digests/schema/projection/H controls/live tuple. gap/truncation/hidden suffix/unsupported kind/epoch/H EMPTY/PENDING/PREPARED/UNCERTAIN/RETIRE/HISTORY_BLOCK 거절 |
| proof/custody | provider nonce/fresh exact key response, independently bound protected roots/leaves. proof replay/caller nonce/foreign key/reparse/hardlink/replacement/rename/delete/ACL drift 거절 |
| capability | original registry/tuple, single assignment·single handoff, 모든 held lifetime 유지. forged/copied/foreign/cross-domain/subclass/serialized/replayed/expired handle 거절 |
| lifetime/crash | source/lease/transactions/context 종료·replacement/savepoint/provider restart/thread 이동/consumer exception/cleanup 실패 후 stale 영구 거절. restored facts revive 0 |
| race/mutation | mint/handoff race winner 최대1(instance 범위). duplicate loser가 winner 폐기하지 않음. authority mutation/partial state 0. domain-wide durable registration winner claim 없음 |
| fail closed/security | safe 3 IBLA categories만, paths/keys/raw sources/ACL/handles/stack leak 0. unsupported production/private source/Fake fallback 0 |

## 5. 실제 검증 결과

API/metadata 계측은 create_app(Settings(database_url=sqlite:///:memory:, auto_migrate=False)) 후 OpenAPI 생성만 수행했다. lifespan/startup/DB connection/Provider/Artifact를 실행하지 않았다. SQLAlchemy model metadata를 import했으며 실제 user DB/table 조회가 아니다.

| Gate | 실제 결과 |
|---|---|
| Alembic heads (script metadata only) | 20260918_0037 single head |
| API surface | routes 114 / APIRoutes 110 / paths 89 / operations 110 / duplicate operation IDs 0, 이전 감사 baseline과 동일 |
| application metadata | 67 tables, model source delta 0 |
| non-doc delta | 0, Markdown만 변경 |
| git diff --check | PASS, whitespace error 0 |
| strict UTF-8 / Markdown fence | 변경 Markdown 15개 strict decode PASS, fence delimiters 16개 balanced |
| relative path links / ADR number·index | 변경 문서 상대 경로 602개 존재 PASS, ADR 번호 중복 0 / ADR-110 및 index 1개 |
| current document contradiction search | 요청한 13 terms 검색과 IBLA 관련 문맥 대조, 현재 계약/구현 상태 충돌 0 |
| sensitive material scan | 변경 문서 secret/private-key/token/private user path pattern 발견 0, 실제 keys/원본 자료 없음 |

검증 scope는 변경 문서의 UTF-8 decode, fenced blocks balance, 상대 경로 존재, 신규 ADR numbering/index, docs-only diff, sensitive material pattern 및 current authority/status assertion의 문맥 대조다. external HTTP 전수 검증·모든 Markdown fragment 전수 검증은 미실행이며 성공으로 표시하지 않는다. 새 Mermaid diagram 없음. 역사적 CHANGELOG/validation/ADR의 당시 사실은 보존한다.

## 6. 문서 동기화·상태·미수행

README/ROADMAP/MASTER_ROADMAP/Phase-09 DoD, bootstrap/deployment/current lifecycle/issuance architecture, security, DB journal/table responsibility 및 ADR index/CHANGELOG를 ADR-110과 연결했다. 상태는 L/H IMPLEMENTED FOUNDATION; Authentic Source/First-Registration Contract DECIDED; Source Verifier/Capability/Initial Authorization/Provisioning/GENESIS NOT IMPLEMENTED; Authentication/Activation UNAVAILABLE; Phase9 0/18,0%. 완료 체크 증가 없음.

BLOCKER: 0 (이 문서 계약의 제한된 read-only 구현 준비 범위). 실제 external originals/custody가 없는 production path는 unavailable이며 운영 준비 완료를 뜻하지 않는다.

WARNING: 실제 Production custody 미검증; commissioning ceremony 미실행; private source 미접근; hardware anti-rollback/remote consensus 미지원; power-loss/storage-controller durability 미검증; H 마지막 PREPARED rollback 및 consistent historical L/H rollback 탐지 기존 한계 유지; external HTTP/fragment 전수 검증 미실행.

미수행: Production code/test 구현 및 tests/Full Backend/Frontend 실행, API mutation, DB migration/schema mutation, actual user DB/Artifact/Provider/Production source, credential/private key, 실제 provisioning, Initial Authorization issue/consume/cancel, GENESIS, Authentication/Activation, Recovery/Transfer, Ready/merge/auto merge/branch 삭제. docs-only 요청에서 Full Backend 미실행은 실패가 아니다. AI 실험 없음, 실험 보고서 불필요.

다음 정확한 작업은 Authentic IBLA Source Verifier + First-Registration Capability Foundation이다. 이 Decision의 Draft 검토·병합은 별도 승인 범위이며 이번 작업에서 실행하지 않는다. 후속은 Initial Authorization → Production Journal Provisioning/GENESIS → Authentication/Activation 순서다.
