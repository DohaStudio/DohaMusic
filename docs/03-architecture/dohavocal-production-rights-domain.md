# DohaVocal Production Rights Domain

> 상태: V1 ADR-075 결정 / [구현: SQLite Persistence Foundation] / production Writer·Adapter [미구현]
> 최종 수정일: 2026-09-18
> 관련 문서: [ADR-075](../11-decisions/ADR-075-dohavocal-production-rights-domain-decision.md), [Completion](dohavocal-verified-staged-artifact-completion.md), [Persistence](../07-database/dohavocal-production-rights-persistence-design.md)

## Authority와 transaction 경계

[ADR-076](../11-decisions/ADR-076-product-deployment-bootstrap-authority.md)은 별도의 external deployment root와 최초 owner binding bootstrap을 정의한 제안이다. root/custodian은 Rights issuer가 아니며 bootstrap은 Rights·Approval·Consent·OUTPUT_READ를 발급하지 않는다. ADR-075의 authenticated current owner 발급 및 current owner 또는 original authenticated issuer Revoke 의미는 그대로다. crypto/principal/binding/Recovery/Transfer/Evidence/Writer는 여전히 미구현이며 계약 Final Validation/merge 전 구현을 시작하지 않는다.

Canonical 결정은 merged PR #160의 ADR-075다. VocalRightsAuthority는 explicit current projection + immutable issuance/event ledger이며 exact typed subject/operation/usage role별 단일 current Grant를 관리한다. ownership/authentication/evidence와 operation Grant는 AND 조건이고 Provider permission·Approval·consent snapshot·RightsMetadata·PayloadLocator는 대체 authority가 아니다. 11개 additive SQLite persistence tables와 flush-only repository·guard primitive를 구현했으며 authenticated Writer/production reader Adapter는 미구현이다.

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

## PR decomposition — persistence와 후속 운영 구현 구분

1. Persistence Foundation [구현/운영 적용 미수행]: typed FK/guards/current pointer/Grant·event·receipt, additive `20260918_0036`, SQLite integrity/locking fixture tests. active/fake receipt backfill 0. target DB equivalence는 SQLite 외 미검증.
2. Authenticated Writer/Evidence Foundation: issuer/revoke authority·증적 검증/withdrawal·idempotency·ordered locking. API/auth UX 권한은 별도 확인.
3. Completion Port/Audit Adaptation: opaque context/final-only hook, one-transaction rollback/replay/compensation 회귀. ADR-074 semantics 유지.
4. Production Rights Adapter: trusted source-role resolution/fresh current query/guard/receipt/auth, all-subject races·fail-closed tests.
5. Rollout/Access Inventory: legacy output explicit reauthorization, 모든 output access/withdrawal/deletion coverage, 승인된 DB 적용/보존·법적 검토/DoD 증거.

**SCHEMA_CHANGE_REQUIRED**에 따른 Foundation은 구현했지만 auth/writer 없이 production adapter를 enable하지 않는다. persistence facts에 대한 minimal port 설계는 병렬 가능하나 port adaptation implementation·receipt wiring은 이번 범위 밖이다. missing production adapter는 deny하며 explicit test Fake를 자동 fallback하지 않는다. #130 acquisition/#159 Foundation/ADR-074는 변경하지 않는다. Phase 진행률·실제 model/Worker 완료 상태는 그대로다.
