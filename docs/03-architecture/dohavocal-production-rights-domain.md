# DohaVocal Production Rights Domain

> 상태: V1 [정의/설계] 승인 제안; production [미구현]
> 최종 수정일: 2026-09-18
> 관련 문서: [ADR-075](../11-decisions/ADR-075-dohavocal-production-rights-domain-decision.md), [Completion](dohavocal-verified-staged-artifact-completion.md), [Persistence](../07-database/dohavocal-production-rights-persistence-design.md)

## Authority와 transaction 경계

Canonical 결정은 ADR-075다. VocalRightsAuthority는 explicit current projection + immutable issuance/event ledger이며 exact typed subject/operation/usage role별 단일 current Grant를 관리한다. ownership/authentication/evidence와 operation Grant는 AND 조건이고 Provider permission·Approval·consent snapshot·RightsMetadata·PayloadLocator는 대체 authority가 아니다. 새 schema/reader/writer는 미구현이다.

| 단계 | 권한 책임 | transaction/I/O |
|---|---|---|
| explicit writer | authenticated owner/evidence/expected revision, 발급·철회·대체 | writer-owned transaction; ordered guards → projection/event → commit |
| preflight | persisted 모든 input의 operation check | 짧은 caller transaction; receipt 없음 |
| open_verified/prepare | verified byte handoff | DB transaction 밖; 권한 발급 아님 |
| final Completion | fresh current check·shared guards 유지 | output/locator/job + receipt 한 caller transaction |
| replay | canonical output exact OUTPUT_READ | short guarded transaction; staging/새 rows 없음 |

generation은 workspace CREATE_OUTPUT와 lyrics/melody Artifact, present timing/voice Artifact를 각각 승인한다. conversion은 source/다른 parent Version과 voice Artifact, correction/analysis는 source/다른 parent Version이다. persisted job_input/JobInput 일치, Artifact→Version→Asset owner 관계를 DB에서 검증하며 대표 lineage만 승인하지 않는다.

선택 serialization은 ordered evidence guards→scope guards의 실제 conditional UPDATE lock을 commit까지 유지하는 방식이다. 빈 guard 부재 reader는 deny, unique anchor provision은 writer만 수행하고 active backfill은 없다. DB isolation/lock/busy retry와 ownership/resource 변경 writer 참여를 검증하기 전 production enable은 금지한다. 상세 경쟁·expiry/actor/withdrawal은 ADR-075가 canonical이다.

## Port·replay·운영 gate

기존 Session-aware check를 유지하나 required completion receipt 때문에 **MINIMAL_PORT_ADAPTATION_REQUIRED**다. 후속 opaque context 반환/final-only receipt hook은 같은 Session/held guards를 검증하고 arbitrary Grant를 받지 않는다. Service의 transaction/target/compensation 책임은 그대로다.

OUTPUT_READ는 exact canonical Artifact 권한이다. creation Grant revoke만으로 자동 output read revoke하지 않으며 명시적 withdrawal 범위가 필요하다. Completion 자동 발급은 없고 authenticated explicit writer 이전에는 response-loss replay도 deny한다. historical receipt/source tombstone은 현재 read 허가가 아니다. output 자체 tombstone이면 일반 read deny다.

## 후속 PR decomposition — 모두 [계획/미구현]

1. Persistence Foundation: typed FK/guards/current pointer/Grant·event·receipt, additive migration, integrity와 DB locking tests. active backfill 0.
2. Authenticated Writer/Evidence Foundation: issuer/revoke authority·증적 검증/withdrawal·idempotency·ordered locking. API/auth UX 권한은 별도 확인.
3. Completion Port/Audit Adaptation: opaque context/final-only hook, one-transaction rollback/replay/compensation 회귀. ADR-074 semantics 유지.
4. Production Rights Adapter: trusted source-role resolution/fresh current query/guard/receipt/auth, all-subject races·fail-closed tests.
5. Rollout/Access Inventory: legacy output explicit reauthorization, 모든 output access/withdrawal/deletion coverage, 승인된 DB 적용/보존·법적 검토/DoD 증거.

auth/writer/schema 없이 adapter부터 구현하지 않는다. **SCHEMA_CHANGE_REQUIRED**다. missing production adapter는 deny하며 explicit test Fake를 자동 fallback하지 않는다. #130 acquisition/#159 Foundation/ADR-074는 변경하지 않는다. Phase 진행률·실제 model/Worker 완료 상태는 그대로다.
