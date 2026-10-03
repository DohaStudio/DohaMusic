# IBLA Registration Commit Authority Decision 검증 보고서

> 문서 상태: [완료 — docs-only Decision 감사; Writer NOT IMPLEMENTED]
> 최종 수정일: 2026-10-04
> 기준 develop: 26452a675c2bf2ab6ae327d6e17e282bbc818a1f
> main: 63633d462043ad3ba78fee92473d19e90c361431 (무변경)
> 작업 branch: docs/ibla-registration-commit-authority-contract
> 계약: [ADR-111](../11-decisions/ADR-111-ibla-registration-commit-authority-post-boundary-contract.md)
> 제출 상태: Draft 전용. PR 번호·exact head·commit/push 결과는 해당 GitHub PR metadata와 최종 보고를 따른다. Ready/merge 미수행.

## 1. Conflict·authority audit

직전 IA_PURPOSE_PRE_POST_ORDERING_CONFLICT는 기존 ADR 자체의 충돌이 아니라 직전 요청이 IA를 PRE registration permission으로 재정의한 문제다. ADR-107 §5 register/issue/consume과 ADR-110 §7~9의 PRE cap/irreversible durable registration/등록 전 IA 금지를 대조했다. 기존 IA는 POST-registration이고 CONSUMED/INITIAL_SEALED는 같은 registry transaction이다. ADR-107/110 파일은 변경하지 않았다.

최신 develop의 아래 14개 ADR 원본 및 실제 schema/codec/source verifier를 읽고 authority primitive를 대조했다. 아래 표는 설계/현재 구현 상태를 구분한다.

| ADR | purpose | authority | lifetime | persistence | transaction owner | replay/failure | downstream handoff |
|---|---|---|---|---|---|---|---|
| 076 | FIRST_OWNER_BINDING_ONLY 외부 bootstrap | 명시 수락 외부 human root/독립 initializer·pin | current designation/proof/claim TTL | 외부 journal/정해진 logical facts; 본 Decision 없음 | caller app owner + external seal owner | seal-first; response loss·uncertain는 reset 불가 | Rights/Recovery/Transfer/IA로 승격 불가 |
| 077 | approval issuance integrity만 | 독립 PinnedRootVerifier와 ExpectedApprovalScope는 comparison | UTC check window; currentness는 제공 안 함 | pure immutable integrity receipt | Session/Repository 없음 | 같은 서명 receipt replay가 authorization consume 아님; fail closed | permission/witness output 없음 |
| 097 | authentic confirmation–lineage exact correlation | actual parent source/material/authority/journal handles | same native lease + caller/journal root transactions | opaque ephemeral correlation | 원래 caller 및 journal transaction owners | parent change/consumer failure는 permanent abandon | CurrentnessWitness 이전 prerequisite; IA 아님 |
| 098 | bounded CurrentnessWitness | 같은 provider correlation/attempt registry | exact source/lease/caller root transaction | opaque ephemeral single assignment | caller source/transaction owners | duplicate winner 보존; stale/release는 permanent invalid | AdmissionAttempt prerequisite; durable permission 아님 |
| 099 | strict AdmissionAttempt candidate | same provider live witness, reviewed signed candidate | exact attempt/lease/root transactions | opaque ephemeral candidate | 외부 Journal Transaction Owner만 future commit | commit ambiguity는 read-only reconcile; ghost success 금지 | NORMAL_ROTATION/REVOKE/EXTERNAL_REDESIGNATION만; GENESIS deny |
| 102 | 기존 Admission chain coordinator | exact Provider/Owner/Reconciler graph | current graph/attempt one-way lifetime | 새 app persistence 없음 | Transaction Owner; orchestrator SQL/commit/rollback 0 | DIRECT/RECONCILED exact commit만 성공; automatic retry 없음 | canonical audit result는 credential 아님 |
| 103 | ceremony-scoped production composition | application-owned reviewed exact graph | scope 종료/root shutdown/current graph | used graph registry memory; 새 durable facts 없음 | caller/source owners와 external Journal Transaction Owner | cross-request 재활성화 금지; unavailable default | runtime activation/IA authority 생성 불가 |
| 104 | reviewed configuration lexical routing comparison | independent reviewed expectations; source authority 아님 | immutable application-root configuration | routing config bytes만 | handles/Session 없음 | noncanonical/unknown/fake paths deny; existence 추측 없음 | exact role routing만; principal/source provenance 아님 |
| 105 | six-role private source descriptors | reviewed config와 identity expectations | application-root immutable descriptor | descriptor data; 실제 source read/provision 없음 | handle/Session 없음 | auto-discovery/self-pinning/fallback 없음 | sources unprovisioned; IA signer/issuer 위임 아님 |
| 106 | 이미 provision된 exact external journal open | reviewed routing + native file/full schema/history | pinned connection/thread-bound root Session | 기존 journal v1; create/migrate/repair 0 | Transaction Owner만 commit/rollback | missing/empty/wrong/replacement deny; read-only reconciler | factory open은 provisioning/GENESIS/IA 권한 아님 |
| 107 | 등록 후 Initial Authorization 및 GENESIS 전 영구 seal/consume | 외부 root exact intent + 지정 Registry Custodian | fresh REGISTERED_INITIAL/currentness/proof/current delegation | IBLA L registry + signed artifact; 새 app DB 없음 | custodian/approved private attempt writer root transaction | CONSUMED + INITIAL_SEALED 같은 transaction; replay는 journal-write capability 재발급 안 함 | 등록 확인→IA issue→seal consume→H→future GENESIS; 직전 잘못된 PRE IA 요청과 충돌; 이번에는 POST 보존 |
| 108 | A/L/H complete domain authority/currentness | 외부 commissioning root; 별도 L custodian/H keeper | same domain lease + held sources + complete histories | 유일 L append-only와 독립 H; 새 registry 금지 | H prepare owner→L owner→H confirm owner | PREPARED retained; absence는 no-commit proof 아님; H only forward reconcile | REGISTRATION_AUTHORIZED/COMMITTED와 INITIAL_AUTHORIZATION_* 목적 분리 |
| 109 | public L/H persistence mechanics | Binding/DTO는 public comparison, 권한 아님 | caller exact root transaction / actual SQLite BEGIN | 독립 SQLite L/H; v1 3종 L kind | Repository flush만; caller root owner commit/rollback | unknown kinds deny; H PREPARED/UNCERTAIN 유지; loss reset 불가 | 현재 registration/IA writer 지원 없음 |
| 110 | read-only authentic source + PRE First-Registration Capability | independent accepted originals/pins + A/C/I/mapping + fresh proof | 최대 monotonic 900초 ∩ source/provider/pid/thread/lease/A-C validity | original L/H read only; provider registry ephemeral | 짧은 query-only pass owner; source owner cleanup | mint/handoff 각각 1회; loss/release/uncertainty abandon | PRE를 POST receipt로 승격 불가; 실제 registration + fresh H 이전 IA issue 금지 |


## 2. Decision·25/25 exit audit

선택은 Option A direct exact writer handoff다. cap만으로 write하지 않고 현 root 등록 intent R·독립 initializer 등록 확인 Q·현재 Registry Custodian exact writer를 결합한다. B의 별도 opaque authority는 원래 lifetime/one-shot 상태를 복제할 뿐 crash durability를 개선하지 않아 기각했다. C의 IA 재사용은 POST 전제가 필요한 PRE 순환과 목적 충돌로 기각했다.

| # | 구현 질문 | 결정된 답 |
|---|---|---|
| 1 | IA가 PRE authority인가? | 아니다. ADR-107 POST IA를 보존한다 (§1/10). |
| 2 | 등록 permission purpose | REGISTRATION_COMMITTED exact one-shot append만 (§2/3). |
| 3 | direct 또는 separate | Option A direct; 별도 authority mint 없음 (§2). |
| 4 | writer | 명시 위임된 Registry Custodian의 fixed RegistrationCommitWriter (§3). |
| 5 | binding | 원본 domain/A/I/L/H·R/Q·writer/observation/lease/transaction exact (§4/5). |
| 6 | lifetime | original cap deadline ∩ callback+30초 ∩ source/lease/thread/proof/RQ/transaction (§5). |
| 7 | serialization | live cap/permission serialize·copy·import 금지 (§5). |
| 8 | persistence | permission 비영속; R/Q 원본·L event·H pending은 audit facts (§4/6). |
| 9 | one-shot | delivered-before-callback; no re-delivery; L uniqueness+CAS (§5/9). |
| 10 | exact payload | v2 envelope 10 fields와 registration 17 fields/관계 고정 (§6). |
| 11 | L extension | external physical L/H v2; strict dual reader/byte-preserving offline migration (§7). |
| 12 | expected head | R exact original COMMISSION rev1/digest; H original CONFIRMED tuple (§4/8). |
| 13 | operation fingerprint | DohaMusicIblaOperationV2+NUL+exact canonical event SHA-256 (§6). |
| 14 | H ordering | independent PREPARED → L durable append → independent CONFIRMED (§8). |
| 15 | durable POST | L REGISTRATION_COMMITTED durable commit (§10). |
| 16 | IA readiness | fresh whole registered L/current H confirmed/current IA issuer+proof; issue자체 제외 (§10). |
| 17 | crash before append | before barrier known no-write만 fresh cap; PREPARED 이후 pending retained (§9). |
| 18 | ambiguous append | actual full L/H 대조; no L retry; absent이면 UNCERTAIN (§9). |
| 19 | response loss | existing exact event stable read-only result/H forward confirmation만 (§9). |
| 20 | retry | original cap 재전달/ambiguous append retry 0 (§5/9). |
| 21 | duplicate registration | domain single-reg index + record/operation uniqueness + CAS/no-prior (§7/9). |
| 22 | cap reuse | delivered 영구 소비; durable reg 후 모든 PRE cap deny (§5/9). |
| 23 | transaction owner | RegistrationCommitOwner L root / HKeeperOwner H roots; repository flush-only (§3/8). |
| 24 | reconciliation owner | OriginalReconciliationReader read-only; independent keeper only forward H (§9). |
| 25 | IA purpose separation | PRE 등록 permission과 POST IA, tokens/receipts/signatures 교차 사용 금지 (§1/10). |

25/25 answered. **IMPLEMENTATION_READY** 범위는 cap direct handoff → Registration Commit permission/Writer → L REGISTRATION_COMMITTED → H/reconciliation → POST handoff다. IA 전체 issue/consume/cancel 또는 Production provisioning 준비 완료를 의미하지 않는다. wire·version·owner·replay 정책은 ADR-111 각 절이 단일 기준이다.

## 3. Baseline·실행 검증

새 isolated worktree를 remote develop에서 생성했다. root의 frontend/next-env.d.ts 사용자 변경, 기존 worktrees/blocked IA branch, 6개 stash와 #171/#130을 보존한다. 실제 user DB/Artifact/Production source/credential/private key 접근은 0이다.

- create_app(Settings(database_url=sqlite:///:memory:, auto_migrate=False))와 OpenAPI/metadata만 측정: routes **114**, APIRoutes **110**, paths **89**, operations **110**, duplicate operation IDs **0**, metadata tables **67**.
- python -m alembic -c backend/alembic.ini heads: **20260918_0037 single head**.
- 변경 전/후 first-party Python 560개 SHA-256 대조 및 Git diff: non-doc delta **0**, app schema/API/Alembic delta **0**. 실제 external L/H schema도 변경하지 않았다. v2는 결정만 했고 현재 구현은 v1이다.
- diff check, strict UTF-8, Markdown fences, 변경 문서 relative file links, ADR-111 번호 유일성/index, sensitive scan: **PASS**. 코드 정적 검사/test를 실행했다는 뜻이 아니다.
- CURRENT authority 문서 전체 keyword search와 문맥 감사: PRE IA authority **0**, cap=IA **0**, registration 이전 IA issue 허용 **0**, app row POST boundary **0**, 등록 permission의 GENESIS 승격 **0**. 부정문·대안 기각·과거 검증/CHANGELOG 사실은 contradiction으로 세지 않는다.

정적 검증은 실제 local 파일/추가 diff에 대해 수행한다. current docs의 기존 unrelated 상태와 historical evidence를 새 완료 증거로 바꾸지 않는다. Full Backend는 docs-only Decision에 필요 없어 미수행하며 실패가 아니다. 신규 테스트·실제 durable append·실제 migration·Windows custody 실험도 미수행이다.

## 4. Documentation sync·상태

README/ROADMAP/MASTER_ROADMAP/Phase-09, bootstrap/issuance/current-status/deployment architecture, security policy, lifecycle journal/DB table responsibility, ADR index, CHANGELOG의 직접 영향 문서를 동기화했다. CHANGELOG [Unreleased] 문서 항목에 direct handoff·purpose 보존·L/H version·crash/replay/POST 결정을 기록했다. 기존 ADR-107~110과 historical validation/CHANGELOG 내용은 보존한다.

| 항목 | 현재 사실 |
|---|---|
| L/H Persistence·Source Verifier·First-Registration Capability | IMPLEMENTED FOUNDATION |
| Registration Commit Contract | DECIDED |
| Registration Commit Writer·IA·Provisioning·GENESIS | NOT IMPLEMENTED |
| Authentication/Activation | UNAVAILABLE |
| Phase 9 | 0/18, 0%; DoD 완료 체크 증가 0 |

## 5. BLOCKER·WARNING·미수행·다음 작업

BLOCKER: 없음. 모든 Decision Gate PASS를 전제로 한국어 commit/push/develop 대상 Draft PR까지만 제출한다. 이번 범위의 설계 readiness를 production 검증 또는 구현 완료로 보고하지 않는다.

WARNING: 실제 production custody 미검증, commissioning ceremony 미실행, private authority source 미접근, power-loss/storage-controller durability 미검증, hardware anti-rollback/remote consensus 미지원, H standalone 마지막 PREPARED rollback 및 consistent L/H historical rollback 기존 한계. 실제 writer/IA/Provisioning/GENESIS 미구현, Auth/Activation unavailable. v1→v2 실제 offline production maintenance 미구현·미수행.

미수행: Production Python/tests/Full Backend, 실제 등록 append, cap 구현 변경, IA issue/consume/cancel/INITIAL_SEALED, Provisioning/GENESIS/Auth/Activation/Recovery/Transfer, Frontend/public API/app migration/schema, 실제 DB/Artifact/source/key/credential, Ready/merge/auto-merge/branch 삭제.

다음 정확한 작업은 **이 Decision PR을 별도 최종 검증·Ready·guarded squash merge한 이후 Registration Commit Writer Foundation**이다. exact handoff/writer/event/L support/CAS/one-shot/replay/H/crash/tests/implementation docs만 허용한다. 이 Draft 제출과 동시에 구현하지 않는다. Writer가 develop에 병합된 후에만 POST-registration IA 계약의 후속 gap을 감사한다.
