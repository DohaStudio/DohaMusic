# ADR-075: DohaVocal Production Rights Domain Decision

> 상태: PR #160 merged V1 결정; SQLite Persistence Foundation [구현], production Writer·Adapter [미구현]
> 작성일·최종 수정일: 2026-09-18
> 기준: develop `890ad1d015d57f34a226f29eeca131872da38f75`
> 관련 PR: #160 merged Domain Decision; #159 merged Foundation, #130 별도 acquisition 책임
> 상태 이력: 아래 본문은 Domain Decision 당시 범위·미구현 기록을 보존한다. 후속 persistence 구현/검증 상태는 [Persistence](../07-database/dohavocal-production-rights-persistence-design.md)를 따른다. 본문 semantics 변경 없음.
> 관련 문서: [ADR-074](ADR-074-dohavocal-verified-staged-artifact-completion-authority.md), [Rights architecture](../03-architecture/dohavocal-production-rights-domain.md), [Persistence](../07-database/dohavocal-production-rights-persistence-design.md), [동의 정책](../09-security/voice-consent-policy.md)

## 1. 배경과 문제

ADR-074 Foundation은 caller Session의 current-rights port를 요구하나 production authority가 없다. 기존 Approval은 임의 purpose/status 승인 이력이며 current projection, operation별 배타성, revoke/supersede revision, writer-reader serialization이 없다. VoiceProfile consent snapshot, RightsMetadata, PayloadLocator revocation, ownership은 증적·metadata·payload lifecycle·scope이지 operation grant가 아니다. 기존 authority 부재를 재조사하는 대신 새 V1 결정을 정의한다. 이 제안은 아직 develop의 운영 구현 또는 승인된 production 권한이 아니다.

## 2. 대안·선택 이유

| 비교 | A: Approval 강화 | B: 불변 Grant ledger 단독 | C: current authority + 불변 Grant/event (선택) |
|---|---|---|---|
| authority 명확성 | workflow와 혼재 | event fold 의존 | 명시적 current pointer |
| 감사 | legacy status 재해석 위험 | 우수 | issuance/event + completion receipt |
| revoke·replace | 기존 이력 전환 필요 | event ordering 필요 | 동일 projection transaction |
| concurrency | 새 lock/CAS 필요 | append로 충돌 방지 불가 | stable scope guard 공유 |
| projection | 기존 table 의미 재정의 | fold 또는 별도 projection | 필수 explicit projection |
| operation·source precision | free-form purpose 충돌 | typed key 가능 | typed subject/op/usage role |
| replay | legacy approved 오승격 | 최신 event 판정 필요 | output 전용 key |
| serialization | 결국 새 protocol 필요 | append만으로 reader 보호 불가 | commit까지 guard write lock |
| migration·호환성 | legacy 데이터 의미 변경 | 새 schema, no auto backfill | additive schema, legacy 그대로 |
| 보안 | approved를 ACTIVE로 오인 | timestamp/latest 오인 | pointer/revision/정합성 deny |
| 복잡도 | 작아 보여도 의미 변경 큼 | fold/ordering 비용 | 구조 증가, 검증 책임 명확 |

**C를 V1으로 선택한다.** A는 legacy 승인 의미 변경, B는 currentness·부재 경쟁을 ledger만으로 해결하지 못하므로 기각한다. Vocal 전용 operation namespace와 typed subject를 선택하며 범용 all-provider engine은 제외한다. operation별 별도 Grant로 부분 철회·감사 단위를 고정한다. permission set은 배제하고 TRANSFORM이 ANALYZE/CORRECT를 포함하지 않게 한다. VoiceProfile/Asset wildcard, Training, Mix·Export로 확대하지 않는다.

## 3. Aggregate·authority key·subject

VocalRightsAuthority는 ScopeGuard, EvidenceBinding/Guard, CurrentAuthority, immutable RightsGrant/RightsEvent, CompletionRightsReceipt로 구성한다. 논리 이름이며 table/ORM 구현 사실이 아니다.

ScopeGuard key는 `(owner_id, workspace_id)`다. CurrentAuthority key는 `(owner_id, workspace_id, subject_type, subject_id, operation, usage_role)`다. Grant ID는 immutable issuance identity, semantic revision은 monotonic currentness token이며 key를 대체하지 않는다. CurrentAuthority는 nullable current_grant_id와 revision을 갖는다. latest timestamp로 current를 선택하지 않는다.

| Subject | 정확한 관계·범위 | V1 |
|---|---|---|
| WORKSPACE | 실제 Workspace FK, 같은 owner/scope | generation CREATE_OUTPUT |
| ASSET_VERSION | exact Version FK → Asset → Workspace/owner | source/다른 parent Vocal Version |
| ARTIFACT | exact Artifact FK → Version → Asset, immutable kind/identity | reference·canonical output |
| Asset | Version 집합·변하는 selection | subject 제외; 모든 Version grant 금지 |
| VoiceProfile | legacy consent, Workspace/owner binding 불충분 | 직접 subject 제외; 명시적 Workspace Artifact 전환·새 증적 필요 |

typed subject registry는 type별 별도 실제 FK binding과 정확히 하나의 target을 강제한다. generic UUID 또는 nullable FK soup만으로 참조 무결성을 주장하지 않는다. Version/Artifact가 같은 owner/workspace에 속해야 하고 pointer→Grant도 동일 authority key여야 한다. wrong Version/workspace/owner는 deny한다. Project 접근·membership은 기존 Completion gate의 추가 AND 조건이다. Grant는 workspace-scoped이며 별도 Project 접근 권한을 주지 않는다. owner 변경은 자동 Grant 양도가 아니다.

## 4. Operation·protected subjects

| Operation | 필수 current ACTIVE key | optional·파생 범위 |
|---|---|---|
| VOCAL_GENERATE | WORKSPACE/CREATE_OUTPUT + exact lyrics Artifact/LYRICS_REFERENCE + melody Artifact/MELODY_REFERENCE | timing present면 TIMING_REFERENCE, voice present면 VOICE_REFERENCE 별도 Artifact key 필수 |
| VOCAL_TRANSFORM | exact source Version/SOURCE_VOCAL + exact voice Artifact/VOICE_REFERENCE | parent≠source면 exact parent Version/PARENT_VOCAL 추가 |
| VOCAL_CORRECT | exact source Version/SOURCE_VOCAL | parent≠source면 PARENT_VOCAL 추가; transform grant 불가 |
| VOCAL_ANALYZE | exact source Version/SOURCE_VOCAL | parent≠source면 PARENT_VOCAL 추가; read·평가 JSON 파생만 |
| OUTPUT_READ | canonical JobOutput의 exact Artifact/OUTPUT | 생성 operation/Version-wide grant 대체 불가 |

generation reference UUID는 strict persisted job_input과 JobInput이 일치하는 exact Artifact다. required lyrics/melody는 항상 검사한다. optional 없음은 그 role만 생략하며 present인데 권한이 없으면 전체 deny한다. trusted Session에서 Artifact→Version→Asset/owner를 다시 resolve하고 candidate 대표 lineage 하나만으로 나머지 inputs를 승인하지 않는다. 동일 subject라도 role이 다르면 별도 key다.

source read와 지정 operation의 파생 생성만 해당 key/role에 포함한다. 별도 VOICE_REFERENCE_USE/DERIVATIVE_CREATE wildcard는 불필요하므로 추가하지 않는다. workspace generation grant는 새 Vocal Asset/version 1 생성 권한이며 reference 권한을 포함하지 않는다. conversion/correction은 ADR-074 동일 Asset 다음 Version, analysis는 exact source Version JSON Artifact다. 모든 protected keys가 동시에 승인돼야 한다. 원본 수정·selection·Mix·Export·학습·dataset 재사용은 어떤 V1 grant에도 포함되지 않는다.

## 5. Lifecycle·projection·expiry

Grant issuance는 ID/key/issuer/증적 ref·digest·policy version/사유·시각/idempotency identity를 immutable로 저장한다. lifecycle은 immutable event + explicit projection으로 판단하며 issuance row를 덮어쓰지 않는다.

- ACTIVE: current pointer가 해당 Grant를 가리키고 terminal event가 없으며 scope/evidence prerequisite가 유효하다. key당 0 또는 1개다.
- REVOKED: exact revoke/withdrawal event로 종료; current pointer는 비우고 역사 근거는 보존한다.
- SUPERSEDED: replace transaction으로 종료; old event/new issuance/pointer·revision을 동시에 저장한다.
- PENDING/REJECTED는 심사 workflow일 수 있으나 authoritative Grant 상태가 아니다.

terminal Grant는 복구하지 않고 새 검증·Grant ID·revision으로 regrant한다. pointer 단일성·동일 key·history 정합성을 DB constraints와 guarded writer 검증으로 강제하며 깨진 projection은 deny한다. semantic revision은 성공한 권한 변경마다 증가한다. guard_epoch은 lock token일 뿐 승인 event/revision이 아니다.

revoked_at/superseded_at·superseded_by·reason·actor는 terminal event의 immutable audit facts다. effective revoke/replace point는 writer DB commit이며 audit timestamp 최신순이 아니다. 서로 다른 requests가 같은 revision을 소비할 수 없다. 원본 삭제는 감사 identity를 cascade 삭제하지 않으며 현재 사용 불가 source는 first commit에서 deny한다.

V1은 **명시적 revocation-only**이고 자동 expiry는 미지원이다. 기간 제한 증적/end_at 요청은 unsupported로 발급 거부하며 무기한으로 변환하지 않는다. 만료 필수 자료는 V1 제외다. 기존 동의 정책의 목적·기간 제한을 완화하지 않는다. 장기 권한 위험과 revoke/monitoring을 운영 선행 조건으로 명시한다. expiry 후속 ADR은 trusted clock·final commit 경계·expiry writer serialization·audit를 해결해야 한다.

## 6. Explicit writer·actor·evidence

GrantWriter/RevokeWriter/SupersedeWriter만 current authority를 바꾼다. Provider/Worker/Completion reader/generic caller/legacy Approval 서비스는 발급자가 아니다. actor 조건을 설계할 뿐 Public API/RBAC/auth 구현을 추가하지 않는다.

issuer는 trusted authentication으로 식별된 현재 Workspace owner 사람이고 exact subject/op/role·파생 사용의 권리 보유 또는 권리자 동의를 검증한 immutable evidence가 필수다. owner라는 사실만으로 타인 음성을 사용할 수 없다. owner UUID 문자열·Provider permissions·legacy consent boolean은 불충분하다. 위임/서비스 계정 발급·상업/훈련 permission은 V1 제외다.

revoke는 현재 Workspace owner 또는 발급 당시 authenticated issuer가 exact Grant를 대상으로 수행한다. 권리자 철회는 authenticated 권리자와 기존 evidence binding을 확인하는 trusted withdrawal writer만 처리한다. 새 owner에게 기존 Grant를 양도하지 않는다. current owner가 기존 Workspace Grant를 revoke할 수 있으나 새 owner의 재허용은 새 key/검증/Grant가 필요하다.

EvidenceBinding은 immutable opaque identity/digest·권리자·검증자·policy version·exact subjects/ops/roles와 동의 범위를 보존한다. 원문·음성·내부 path는 ledger/log에 복제하지 않는다. 최소 current eligibility/withdrawal event/guard를 두며 범용 Consent platform 전체를 정의했다고 주장하지 않는다. Approval/snapshot/RightsMetadata만으로 verified evidence를 backfill하지 않는다. 증적 수집·인증·검증·보존의 법적 근거는 운영 전 보안 검토 대상이다.

기존 Approval/consent evidence를 참조할 수는 있지만 immutable reference/digest와 실제 identity·목적·범위 검증을 거쳐 새 binding을 명시적으로 발급해야 한다. 참조는 decision의 근거이지 authorization 자체가 아니다. 원본 수정이 가능하면 frozen digest 검증 없이 재사용하지 않는다.

GrantWriter는 expected semantic revision/idempotency key를 요구한다. 동일 identity·내용만 기존 결과 replay, 다른 내용 또는 stale revision은 conflict다. existing ACTIVE는 덮어쓰지 않고 explicit SupersedeWriter를 요구한다. revoke는 exact Grant ID/revision/safe reason과 같은 request replay만 허용한다. old superseded Grant revoke가 새 current Grant에 적용되지 않는다. replace는 old SUPERSEDED/new ACTIVE를 한 transaction에 넣어 두 ACTIVE를 노출하지 않는다.

writer는 대상 current Grant의 old evidence와 발급하려는 new evidence guards를 모두 같은 전역 순서로 잠근다. authority 변경 하나는 revision 하나와 immutable transition event 하나를 소비한다. supersede event에 old/new Grant를 함께 기록하고 새 issuance도 같은 transaction에 넣으므로 같은 revision에 서로 모순되는 별도 events를 추가하지 않는다. reader adapter는 caller Session에 참가하며 독립 commit/rollback을 수행하지 않는다.

withdrawal writer는 evidence guard를 잠그고 연결된 모든 scope guards를 정렬 잠금한 뒤 관련 current grants REVOKED·evidence withdrawn·events를 원자적으로 기록한다. 같은 evidence issuance도 evidence guard를 쓰므로 대상 집합이 고정된다. 실패하면 전체 rollback하고 철회 완료로 표시하지 않는다. 규모/시간 제한 검증 전 production 노출은 금지한다. terminal evidence는 재활성화하지 않는다.

## 7. Serialization·부재 경쟁·commit invariant

| 대안 | 장점 | 판정 |
|---|---|---|
| per-row SELECT FOR UPDATE | 병렬성 | absent row 경쟁·SQLite 미지원/무시로 단독 기각 |
| semantic revision CAS | 낙관적 병렬성 | SELECT/비교만으로 commit 보호 불가; multi-key writer protocol 필요 |
| stable guard 실제 conditional UPDATE + lock 유지 | 부재 key·multi-subject 통제 | **V1 선택**, coarse lock/DB 검증 비용 수용 |

evidence ID 순 evidence guards → `(workspace_id, owner_id)` 순 scope guards를 획득한다. 실제 `UPDATE guard_epoch = guard_epoch + 1 WHERE id = ... AND guard_epoch = expected`를 caller transaction에서 실행하고 write lock을 commit/rollback까지 유지한다. 단순 Python revision 비교, cached ORM state, 효과 없는 FOR UPDATE는 금지한다. SQLite의 성공한 실제 write lock과 PostgreSQL 등의 row update lock이 동일 보장을 해야 한다. isolation/busy timeout/snapshot conflict/rollback/lock 유지의 executable tests 전 production adapter를 승인하지 않는다. unsupported backend는 fail closed, unlocked fallback은 없다.

reader는 필요한 current evidence 집합을 먼저 발견하고 evidence→scope guards를 잠근 뒤 authority를 DB에서 새로 읽는다. evidence 집합/pointer/revision이 discovery와 다르면 전체 rollback 후 재발견한다. 일부 subject만 옛 evidence를 잠근 상태로 승인하지 않는다. role이 다른 key는 deduplicate하지 않는다. ownership/scope/resource 변경 writer도 해당 guards에 참여해야 한다. 기존 writer가 협력하지 않으면 final transaction의 실제 resource row lock/conditional validation까지 검증하거나 production adapter를 비활성화한다.

ScopeGuard 부재 시 reader는 deny한다. writer는 unique scope key insert로 anchor를 provision하고 그 transaction lock을 유지한다. 충돌 writer는 rollback 후 기존 anchor를 다시 읽고 잠근다. 빈 anchor 생성은 active backfill이 아니며 anchor를 physical delete하지 않는다. CurrentAuthority key 부재도 이미 존재하는 scope anchor 아래에서 처리하여 absence predicate 경쟁을 통제한다.

| 경쟁 | 확정 결과 |
|---|---|
| grant/grant, key 없음 | 첫 writer만 발급, 두 번째는 expected revision conflict/explicit replace 요구 |
| revoke/grant | guard 순서 확정; stale revoke가 새 Grant를 철회하지 않음 |
| completion/revoke | reader 먼저면 commit 후 revoke; revoke 먼저면 final deny |
| completion/grant | final 잠금 전 발급만 관찰; 부재 deny를 이후 grant가 소급 성공시키지 않음 |
| 두 subjects 중 하나 revoke | ordered guards 아래 전체 승인 또는 전체 deny |
| final check 후 revoke | writer는 reader commit/rollback까지 대기 |
| output read/revoke | replay short guarded transaction의 현재 read point 고정; 반환 후 revoke는 이후 사건 |

**Commit invariant:** final caller transaction에서 exact protected subjects의 current ACTIVE Grant IDs/revisions·evidence eligibility·owner/workspace/op/role을 fresh 검증하고 공유 writer locks를 끝까지 유지한 경우에만 Artifact/JobOutput/Job succeeded/locator ingested를 확정한다. check 순간 ACTIVE라는 것만으로 충분하지 않다. DB commit 성공이 Completion linearization point다. revoke/supersede/withdrawal/ownership 변경도 같은 discipline을 따르거나 production enable을 차단한다.

retry는 lock/deadlock/serialization/discovery 변경에 한해 최대 3 attempts다. 각 attempt 전체 rollback·fresh Session state, exhaustion safe conflict/unavailable다. stale revision/rights denied/actor mismatch는 자동 발급·재허용하지 않는다. 준비된 publication은 ADR-074 compensation/adoption/replay를 보존하며 hidden I/O/새 Job을 만들지 않는다. transaction 재시도를 지원하지 않는 adapter는 safe conflict로 반환한다.

## 8. Completion·replay·audit·port 판정

pre-I/O COMMIT과 final COMMIT은 같은 persisted inputs를 resolve하나 preflight 승인은 final 권한 보증이 아니다. final에서 다시 검증하며 receipt는 final transaction만 쓴다. staging open/prepare I/O는 DB 밖이고 #130 acquisition·open_verified→ArtifactIngestionService handoff는 그대로다.

replay는 historical creation Grant의 ACTIVE를 요구하지 않는다. canonical JobOutput exact Artifact의 current OUTPUT_READ + current owner/workspace/Project 접근을 검사한다. **source operation revoke 자체는 기존 output read grant를 자동 revoke하지 않는다.** output까지 금지하려면 withdrawal 증적/요청 범위에 OUTPUT_READ를 명시한다. source tombstone/selection 변경/locator cleanup은 historical identity를 없애거나 output permission을 만들지 않는다. output 자체 tombstone/사용 불가는 일반 read deny이며 감사 역사 조회는 별도 미래 계약이다. replay에는 staging I/O나 새 Artifact/JobOutput/ModelUsage/receipt가 없다.

Completion은 OUTPUT_READ를 자동 발급하지 않는다. output 생성 뒤 authenticated owner의 explicit writer가 발급한다. 그 전에는 response-loss replay도 fail closed한다. 최초 creation 응답이 future output permission으로 승격되지 않는 V1 UX 제약을 안내한다.

CompletionRightsReceipt는 Job/canonical Artifact/operation/exact sorted keys·Grant IDs·semantic revisions·evidence refs/digests/policy versions/authenticated actor opaque ref를 final output과 같은 transaction에서 한 번 저장한다. rollback 시 모두 사라진다. receipt는 과거 승인 근거이며 current read permission이 아니다. ModelUsage/JobOutput/metadata를 권한 ledger로 확대하지 않고 legacy receipt를 fabricated backfill하지 않는다.

현재 `VocalCompletionRightsPort.require_current(..., mode) -> None`의 Session/principal/job/candidate/scope는 current check resolution에 충분하다. 하지만 preflight/final COMMIT의 같은 mode와 final output ID 부재로 필수 audit 기록에는 부족하다. 최종 분류는 **MINIMAL_PORT_ADAPTATION_REQUIRED**다. 후속은 check 의미를 보존하면서 transaction-local opaque authorization context 반환 + `record_completion_receipt(session, context, canonical_job_output)` final-only hook을 추가한다. hook은 동일 Session/held guards/context를 검증하며 arbitrary caller grants를 받지 않는다. preflight context 폐기, replay check-only, Fake 이행은 명시적으로 한다. transaction 소유권/targets/atomicity 재설계가 아니며 이번에는 source/protocol/test를 바꾸지 않는다.

## 9. Persistence·migration·rollout

최종 분류는 **SCHEMA_CHANGE_REQUIRED**다. current pointer/key/revision, immutable issuance/event, shared guards/evidence eligibility, completion receipt 필수 facts가 기존 schema에 없다. [Persistence 설계](../07-database/dohavocal-production-rights-persistence-design.md)의 YES/NO를 따른다. additive rights schema가 필요하나 migration/ORM/test/실제 DB 적용은 범위 밖이다.

legacy Approval은 workflow/history로 보존한다. approved/latest decided_at/training/voice_conversion purpose를 신규 ACTIVE operation으로 mapping하지 않는다. consent snapshot/RightsMetadata/ModelUsage로 Grant/receipt를 만들지 않는다. legacy output의 historical identity는 남기되 신규 production adapter의 replay/read에는 explicit 새 OUTPUT_READ가 필요하다. 기존 legacy endpoint 정책을 몰래 바꾸지 않으며 rollout 때 모든 output access 경로를 inventory해 uncovered 경로가 있으면 공개 운영을 막는다.

순서는 persistence → authenticated writer/evidence → minimal Completion port/audit + production adapter → rollout/access inventory다. auth/RBAC/증적 product·운영 보존/삭제 정책은 선행 조건이다. missing adapter는 fail closed이며 dev/test explicit Fake를 production startup/config/environment flag로 자동 선택하지 않는다. expiry/VoiceProfile 직접 authority/Training/Mix/Export/범용 rights engine은 V1 제외다.

## 10. 보안·영향·재검토

오류는 RIGHTS_DENIED/AUTHORITY_CONFLICT/AUTHORITY_UNAVAILABLE와 correlation ID 수준이며 raw evidence/음성/filename/path/DB exception을 노출하지 않는다. audit는 opaque IDs/revision/safe reason enum만 사용한다. policy version 변경 자체는 자동 revoke가 아니며 material 변경은 explicit review/withdrawal/regrant를 요구한다. 그 절차 없이는 production 발급을 막는다.

내부 domain failure는 NO_CURRENT_GRANT, GRANT_REVOKED, GRANT_SUPERSEDED, OPERATION_NOT_ALLOWED, SUBJECT_MISMATCH, SCOPE_MISMATCH, EVIDENCE_WITHDRAWN, STALE_REVISION, AUTHORITY_UNAVAILABLE로 구분한다. 외부에는 앞의 safe code로 축약하고 다른 사용자의 Grant 존재·증적 사실을 누출하지 않는다. 이 vocabulary는 구현된 오류 enum/API가 아니다.

후속 executable gates: wrong subject/version/workspace/role, TRANSFORM→ANALYZE 금지, optional presence, all-input 승인, duplicate ACTIVE, stale/idempotent revoke/replace, withdrawal/issuance race, final check 후 revoke, absent-row race, SQLite busy/target DB locks, owner 변경, receipt rollback, creation revoke/output revoke 분리, tombstone/legacy replay, production Fake fallback 금지. 이번에 테스트를 구현/실행했다고 주장하지 않는다.

ADR-074 targets/selection 불변성/stream handoff/one final transaction/historical replay identity/claim/cancel/cleanup은 보존한다. TrustedArtifactRegistrationService와 ExportPublicationLedger를 Vocal authority로 재사용하지 않는다. #159/#130 branch/head/source/PR 상태는 변경하지 않는다.

장점은 명확한 current authority·audit/recovery 경계, 단점은 additive persistence/coarse locking/인증·증적 비용/expiry 미지원/explicit OUTPUT_READ UX 제약이다. 재검토 조건은 기간 제한 지원, 권한 위임/owner 이전, cross-provider 권한, lock contention, 새 DB isolation, withdrawal 규모, output read 정책 또는 ADR-074 계약 변경이다. 변경에는 별도 ADR·보안/migration 검토가 필요하다.
