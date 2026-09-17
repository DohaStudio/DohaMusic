# DohaVocal Production Rights Persistence 설계

> 상태: [정의/설계] TARGET additive proposal; schema/migration [미구현]
> 최종 수정일: 2026-09-18
> 기준: develop `890ad1d015d57f34a226f29eeca131872da38f75`; source single head `20260911_0035`
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

최종 **SCHEMA_CHANGE_REQUIRED**다. port-only 구현 또는 기존 schema 충분이라고 주장하지 않는다. concrete V1 필수 facts에서 도출한 판정이지 schema 구현/적용 승인이 아니다.

## 논리 persistence — 모두 [설계/미구현]

| 구성 | 필수 facts/constraints |
|---|---|
| RightsSubject/type별 binding | WORKSPACE/ASSET_VERSION/ARTIFACT별 실제 FK; 정확히 하나의 target·type 일치·불변 identity; wildcard 금지 |
| ScopeGuard | unique owner/workspace·Workspace FK·guard_epoch; actual conditional UPDATE lock anchor; tombstone 보존 |
| EvidenceBinding/Guard/events | immutable opaque identity/digest·권리자/검증자/policy/exact subject·op·role; eligibility/withdrawal·write-lock token |
| CurrentAuthority | unique full key·nullable current_grant_id·semantic revision; same-key Grant composite FK/동등한 integrity |
| RightsGrant | immutable issuance ID/key/actor/evidence/safe reason/time/idempotency identity |
| RightsEvent | immutable GRANTED/REVOKED/SUPERSEDED·old/new Grant·revision/actor/reason; per-authority revision unique; terminal 재활성화 금지 |
| CompletionRightsReceipt/items | unique canonical Job/Artifact completion; exact op/keys/grants/revisions/evidence/actor; final-only insert; audit refs hard delete 금지 |

상태는 immutable issuance/event와 projection으로 계산한다. current row가 key당 하나이므로 pointer 단일성을 갖는다. event/Grant/key·terminal/current 모순은 DB 제약과 guarded writer/reader integrity 검증으로 deny한다. 구체 SQL DDL/table count/constraint 이름은 persistence PR에서 확정하고 SQLite FK 및 target DB의 동등 보장을 테스트한다.

## Transaction·migration·legacy

writer/reader는 ADR-075 ordered evidence→scope guard actual update-lock protocol을 공유한다. final check 후 revoke와 reader commit이 모두 성공하는 interleaving은 금지다. receipt는 canonical output과 final caller transaction에만 저장하고 rollback 시 함께 제거된다.

빈 anchor provision은 ACTIVE backfill이 아니다. additive migration은 Approval/VoiceProfile/ModelUsage/JobOutput/locator 의미를 바꾸지 않는다. guessed Alembic revision·ORM·migration·schema count 변경·사용자/production DB upgrade/startup auto migration은 이번에 하지 않는다. single head는 그대로다.

legacy approved/latest timestamp/training/voice_conversion을 새 ACTIVE로 mapping하지 않는다. metadata에서 Grant/receipt를 fabricated backfill하지 않는다. legacy output은 historical identity만 보존하며 production replay는 explicit OUTPUT_READ 없으면 deny다. source/Grant/evidence 삭제는 접근 차단과 감사 최소 보존을 분리하고 retention/legal review 없이 hard-delete cascade를 기본값으로 두지 않는다.

후속 gate는 uniqueness/FK/immutable audit/projection consistency·rollback, absent-row/concurrent grant·revoke·replace·withdrawal, SQLite busy/snapshot lock과 target DB equivalence, fixture-only migration upgrade/downgrade, active backfill 0이다. 이번에 실행하지 않았다.
