# DohaVocal Production Rights Persistence 설계

> 상태: [구현: SQLite Persistence Foundation] / [미구현: authenticated Writer·production Adapter·운영 적용]
> 최종 수정일: 2026-09-18
> 구현 기준: develop `7db03b7e21956472c968ce38b28ab90e4d2dae69`; source single head `20260918_0036` → parent `20260911_0035`
> 관련 문서: [ADR-075](../11-decisions/ADR-075-dohavocal-production-rights-domain-decision.md), [Database 개요](database-overview.md), [Architecture](../03-architecture/dohavocal-production-rights-domain.md)

## Existing schema 충분성

YES는 역사/관계가 저장된다는 뜻이지 current rights 충분 판정이 아니다. 사용자 DB 상태를 새로 검사하거나 적용한 결과가 아니다.

| 필수 fact | 기존 저장 YES/NO | 근거·부족한 점 |
|---|---|---|
| Workspace/Asset/Version/Artifact identity 관계 | YES | 기존 FK; rights key 아님 |
| Approval 대상/purpose/status/actor/evidence 이력 | YES | authoritative immutable Grant 의미 아님 |
| exact typed subject/operation/role와 owner/workspace key | NO | 자유문자열 purpose로 강제 불가 |
| single current pointer·semantic revision·key consistency | NO | timestamp/approved로 대체 금지 |
| authoritative immutable issuance/terminal event | NO | legacy Approval과 구분 필요 |
| shared scope/evidence serialization guards | NO | locator CAS는 rights writer 공유 아님 |
| verified evidence binding·current withdrawal eligibility | NO | consent snapshot/RightsMetadata 부족 |
| exact completion Grant/revision/evidence receipt | NO | ModelUsage/JobOutput 권한 audit 아님 |
| locator lifecycle/revision/revocation | YES | payload authority뿐 |

ADR-075의 **SCHEMA_CHANGE_REQUIRED** 판정에 따라 별도 additive schema를 구현했다. 기존 schema만으로 충분하다는 판정은 아니다. 사용자·production DB 적용 승인은 별도이며 이번에 적용하지 않았다.

## Persistence Foundation [구현]

| 구성 | 필수 facts/constraints |
|---|---|
| RightsSubject/type별 binding | WORKSPACE/ASSET_VERSION/ARTIFACT별 실제 FK; 정확히 하나의 target·type 일치·불변 identity; wildcard 금지 |
| ScopeGuard | unique owner/workspace·Workspace FK·guard_epoch; actual conditional UPDATE lock anchor; tombstone 보존 |
| EvidenceBinding/Guard/events | immutable opaque identity/digest·권리자/검증자/policy/exact subject·op·role; eligibility/withdrawal·write-lock token |
| CurrentAuthority | unique full key·nullable current_grant_id·semantic revision; same-key Grant composite FK/동등한 integrity |
| RightsGrant | immutable issuance ID/key/actor/evidence/safe reason/time/idempotency identity |
| RightsEvent | immutable GRANTED/REVOKED/SUPERSEDED·old/new Grant·revision/actor/reason; per-authority revision unique; terminal 재활성화 금지 |
| CompletionRightsReceipt/items | unique canonical Job/Artifact completion; exact op/keys/grants/revisions/evidence/actor; final-only insert; audit refs hard delete 금지 |

실제 새 table은 11개다. `vocal_rights_scope_guards`, `vocal_rights_subjects`, `vocal_rights_current_authorities`, `vocal_rights_evidence`, `vocal_rights_evidence_scopes`, `vocal_rights_evidence_guards`, `vocal_rights_evidence_withdrawals`, `vocal_rights_grants`, `vocal_rights_events`, `vocal_completion_rights_receipts`, `vocal_completion_rights_receipt_items`다. 별도 `VOCAL_RIGHTS_ENTITY_CLASSES`로 등록하며 기존 Workspace registration 39개를 재해석하지 않는다.

상태는 immutable issuance/event와 projection으로 표현한다. ACTIVE 판정에는 후속 Adapter의 current scope/evidence 검증도 필요하며 repository는 effective permission을 반환하지 않는다. full key unique와 same-authority Grant composite FK가 pointer 단일성·key 일치를 강제한다. typed registry는 type별 실제 FK·정확히 하나의 target·UUID 일치를 CHECK하고, provision 시 owner/workspace/Version/Artifact 관계는 SQLite trigger와 repository가 검증한다. 이후 기존 ownership/resource writer의 guard 협력은 아직 미구현이므로 production Adapter enable은 금지다.

SQLite trigger는 raw SQL의 immutable row UPDATE/DELETE와 anchor DELETE/key 변경을 차단한다. GRANTED/REVOKED/SUPERSEDED event의 old pointer와 expected revision을 검증한 뒤 한 event로 projection을 정확히 +1 전진시킨다. issuance의 exact event composite FK는 deferred이므로 미발행 Grant 단독 commit은 실패한다. terminal event old/new unique는 terminal 재활성화와 issuance 재사용을 막는다. supersede는 old/new ID를 가진 event 하나다. revoked_at/superseded_at·actor/reason·superseded_by는 terminal event의 생성 시각·actor/reason·new Grant ID로 추적하며 issuance row를 덮어쓰지 않는다.

Evidence header의 scope_count/last scope deferred FK와 ordinal-contiguous trigger는 immutable exact scope aggregate를 닫는다. 이미 발급된 binding에 scope를 추가하지 못한다. opaque reference·SHA-256·policy version·rights holder/verifier는 불변 facts다. kind/정책 유형 vocabulary나 free-form authorization engine은 만들지 않는다. `reason_code`는 bounded opaque audit identifier이며 새로운 권한 정책 enum이 아니다. 증적의 인증·법적 타당성·목적·기간 제한 검증은 후속 Writer 책임이다. expires_at와 자동 expiry는 없다.

Evidence withdrawal fact는 연결된 current pointer가 먼저 모두 비워져야 저장된다. event/guard의 terminal pointer는 불변이며 재활성화할 수 없다. 연결된 Grant 탐색·인증·일괄 revoke의 application orchestration은 구현하지 않았다.

Receipt는 Job unique와 canonical JobOutput unique, actual output_order=0/Job/artifact/operation binding trigger로 묶는다. exact authority/Grant/revision/evidence digest/policy items를 sorted full key 순서로 저장한다. deferred last item FK와 contiguous ordinal/count는 빈·미완성 aggregate commit과 추가 item을 막는다. snapshot은 삽입 시 current pointer/revision과 immutable evidence에 일치해야 한다. 이후 권한 전환은 historical receipt를 수정하지 않는다. receipt는 OUTPUT_READ 권한이 아니며 arbitrary caller facts를 받는 persistence API는 production receipt hook이 아니다.

## Transaction·migration·legacy

`VocalRightsRepository.conditional_guard_update()`는 evidence UUID 순 → `(workspace UUID, owner UUID)` scope 순서의 actual `UPDATE guard_epoch = guard_epoch + 1 WHERE id = :id AND guard_epoch = :expected`를 실행한다. rowcount=1만 성공이고 missing/stale/overflow는 safe conflict다. guard_epoch은 0 시작·signed 64-bit 범위이며 semantic revision과 무관하다. write lock은 caller commit/rollback까지 유지된다. transaction-local lock bookkeeping은 인증·authorization context가 아니며 다음 transaction에서 재사용하지 못한다. 빈 ScopeGuard와 CurrentAuthority provision은 Grant를 만들지 않는다. anchor unique insert loser는 caller가 전체 rollback 후 fresh transaction에서 재조회해야 한다.

Repository는 caller-owned root Session transaction에서 flush만 한다. commit()/rollback()/hidden retry는 0이다. FK enforcement가 꺼진 connection, unsupported engine, nested transaction의 guard proof는 fail closed한다. supplied transition/evidence/withdrawal/receipt facts의 append와 fresh current/ordered ledger read만 제공하며 authenticated issuer, require_current, OUTPUT_READ authorization, 모든 protected input 승인 또는 Completion receipt hook을 구현하지 않는다. Adapter의 discovery→ordered locking→fresh evidence/pointer/revision 대조와 최대 3 whole-transaction attempts는 후속 책임이다. 일부 guard만 잡은 채 추가 scope/evidence를 승인하는 fallback은 없다.

검증된 backend는 현재 source 기본 SQLite다. 실제 write-lock 유지·busy safe failure·WAL snapshot conflict는 disposable fixtures로 검증하며 unsupported engine migration/write는 fail closed한다. PostgreSQL/MySQL 동등 serialization·isolation 검증은 미수행이다. 벤더 독립 동등 보장을 주장하지 않는다. 운영 engine·timeout·WAL 설정 및 ownership writer 참여는 deployment enable 전 검증해야 한다.

빈 anchor provision은 ACTIVE backfill이 아니다. migration `20260918_0036` 하나만 추가하며 parent는 실제 측정한 기존 single head `20260911_0035`다. immutable versioned DDL `backend/db/vocal_rights_schema_v1.py`를 현재 ORM과 migration이 사용한다. merge 뒤 이 V1 파일을 수정하지 않고 후속 schema version/revision을 추가해야 한다. 기존 table/column/Approval/VoiceProfile/ModelUsage/JobOutput/locator의 의미를 바꾸거나 backfill하지 않는다. metadata는 56 → 67 tables다. 사용자·production DB upgrade/startup auto migration은 수행하지 않았다.

온라인 SQLite migration과 rights가 포함된 metadata bootstrap은 driver의 실제 transaction을 확인하고 필요할 때 `BEGIN IMMEDIATE`로 DDL을 시작한다. caller가 끝을 소유하고 table/trigger 설치 중 실패하면 새 schema와 revision update를 함께 rollback한다. DDL failure injection과 metadata bootstrap rollback fixture가 이를 검사한다. offline SQL 생성·다른 SQLite driver/engine의 동등 보장은 별도 검증 대상이다.

빈 새 schema의 downgrade/reupgrade만 허용하며 새 authority/audit row가 하나라도 있으면 downgrade는 먼저 실패하고 table/history를 보존한다. 운영 deletion/retention/법적 보존 정책은 별도다. 이 차단을 피하려고 사용자 DB를 삭제하거나 권한 이력을 비우지 않는다.

legacy approved/latest timestamp/training/voice_conversion을 새 ACTIVE로 mapping하지 않는다. metadata에서 Grant/receipt를 fabricated backfill하지 않는다. legacy output은 historical identity만 보존하며 production replay는 explicit OUTPUT_READ 없으면 deny다. source/Grant/evidence 삭제는 접근 차단과 감사 최소 보존을 분리하고 retention/legal review 없이 hard-delete cascade를 기본값으로 두지 않는다.

검증 근거는 `backend/tests/test_vocal_rights_persistence.py`와 `test_vocal_rights_migration.py`의 fixture-only constraints/FK/immutability/projection/CAS/serialization/receipt rollback, fresh/representative legacy upgrade·downgrade gate다. 인증된 Writer·production Adapter의 end-to-end 증거와 구분한다. legacy rows·consent·output 보존, ACTIVE/fake receipt backfill 0을 검사한다. 최종 실행 수치·direct/full regression과 미수행 gate는 작업 검증 보고서에 기록한다.

후속 우선순위는 authenticated principal/current owner 증명 및 evidence 검증 계약 → Writer/Evidence orchestration → minimal Completion port/final-only receipt hook·production Adapter → output access inventory/운영 migration 승인이다. `MINIMAL_PORT_ADAPTATION_REQUIRED`는 그대로이며 port adaptation 자체는 별도 implementation이다. production auth 선행 조건이 남아 `RIGHTS_WRITER_AUTHENTICATION_PREREQUISITE`로 분류한다. 별도 minimal port/audit 작업은 persistence facts와 명시적 test Fake를 기준으로 병렬 진행 가능하지만 production enable은 Writer/Auth/ownership cooperation/운영 DB 검증 완료 전 불가다.
