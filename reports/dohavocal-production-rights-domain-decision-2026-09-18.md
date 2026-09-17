# DohaVocal Production Rights Domain Decision 검토 보고서

> 상태: [정의/설계 검토] production/runtime 검증 [미수행]
> 최종 수정일: 2026-09-18
> 기준 develop: `890ad1d015d57f34a226f29eeca131872da38f75`
> main: `63633d462043ad3ba78fee92473d19e90c361431`
> 문서 branch: `docs/dohavocal-production-rights-domain-decision`
> 관련 문서: [ADR-075](../docs/11-decisions/ADR-075-dohavocal-production-rights-domain-decision.md), [Architecture](../docs/03-architecture/dohavocal-production-rights-domain.md), [Persistence](../docs/07-database/dohavocal-production-rights-persistence-design.md)

## Scope와 기존 blocker

이전 blocker는 production current operation Grant semantics·writer/reader serialization authority 부재였다. 이번에는 사용자가 새 Domain Decision 설계를 명시적으로 허용했으며 기존 Approval을 current authority로 발굴/승격하는 작업이 아니다. 3개 모델을 비교해 explicit current authority + immutable Grant/event ledger를 V1 제안으로 선택했다. schema 판정은 SCHEMA_CHANGE_REQUIRED, port 판정은 MINIMAL_PORT_ADAPTATION_REQUIRED다. production 기능은 구현하지 않는다.

독립 worktree는 기존 clean #159 branch를 보존해 지정 develop의 fetched object에서 준비했다. 문서 작성용 branch 준비는 최종 정적 검증보다 앞섰다. 사용자 최종 문구의 모든 Gate 후 branch 생성 순서를 그대로 지키지는 못했으며, commit/push/Draft PR은 completeness/security/static/race gates 뒤에만 수행한다. 이 절차 차이를 숨기지 않는다.

## Decision completeness review

아래 PASS는 명시적인 설계 결정의 존재·논리 검토 결과이며 executable concurrency/production 증거가 아니다.

| 요구 | 결정·대표 위치 | 검토 |
|---|---|---|
| ≥3 대안·V1 선택·generic/permission-set 비교 | ADR §2, A/B 기각·C 선택·Vocal namespace/operation별 Grant | PASS |
| aggregate/key/subject precision | §3, owner/workspace/type/exact ID/op/role·Grant ID/revision 분리 | PASS |
| generation required/optional inputs | §4, workspace creation + lyrics/melody + present timing/voice | PASS |
| transform/correct/analyze 분리 | §4, source/parent Version·voice Artifact·no implication | PASS |
| currentness·states·single ACTIVE | §5, pointer/revision·terminal no resurrection | PASS |
| expiry | §5, explicit revoke-only·기간 제한 발급 거부 | PASS |
| issuer/revoke/evidence/legacy Approval | §6, authenticated owner·권리자 증적/withdrawal·no automatic grants | PASS |
| serialization alternatives/actual lock | §7, evidence/scope actual conditional UPDATE lock to commit | PASS |
| absent-row/grant-grant/revoke-grant | §7, unique stable anchor·expected revision·exact target | PASS |
| completion-revoke/grant/multi-subject | §7, ordered guard sets·fresh requery·all or deny | PASS |
| retry/deadlock/ownership change | §7, ≤3 attempts·no silent allow·uncooperative writer blocks enable | PASS |
| first commit/replay/OUTPUT_READ | §8, final current operation vs exact output current permission | PASS |
| output/source revoke 정책 | §8, 별개·explicit OUTPUT_READ withdrawal 범위 | PASS |
| completion audit·port classification | §8, final-only receipt·opaque context/hook 최소 보강 | PASS |
| schema/legacy/backfill/rollout | §9/Persistence YES-NO, additive·legacy 보존·ACTIVE backfill 0 | PASS |
| auth/Provider/Worker/API/UI/safe failures | §6/§10, prerequisite·authority 확대 0 | PASS |
| decomposition | Architecture §후속 PR, persistence→writer→port/adapter→rollout | PASS |

## ADR-074 compatibility·security/race review

- final transaction 최신 rights, caller-owned Session, fail-closed first commit/replay gate를 구현 가능하게 정의했다. rights adapter 독립 commit/rollback은 허용하지 않는다.
- generation 새 Vocal Asset/v1, conversion/correction 동일 Asset 다음 Version, analysis source Version JSON, selection 불변, stream prepare outside DB, output/locator/job atomicity·compensation/cleanup을 바꾸지 않았다. ADR-074 파일은 변경 0이다.
- check 후 revoke가 reader commit보다 먼저 성공하는 실행은 shared actual write lock으로 금지한다. reader-only lock/CAS 비교/timestamp를 충분한 보호로 주장하지 않는다. evidence withdrawal와 all-subject/absence races를 명시했다.
- SQLite/target DB lock/isolation, ownership 변경 writer 참여·current output endpoint coverage는 아직 executable 미검증이므로 production enable 금지 조건이다. 정의된 설계 검토 PASS를 구현 안전성 PASS로 승격하지 않는다.
- 자동 Approval/consent/metadata ACTIVE backfill·Provider/Worker Grant 발급·Fake production fallback은 금지다. OUTPUT_READ 명시 발급 전 replay deny와 expiry 미지원 UX 제약을 숨기지 않는다.
- 실제 동의 원문/개인 음성/모델 weight/생성 음원/사용자 DB는 취급하지 않았다. immutable opaque audit reference만 설계했다.

## 문서 영향·검증 기록

ADR-075와 index, rights architecture/persistence, Completion cross-reference, voice-consent-policy, Database entry, README/ROADMAP/MASTER_ROADMAP, CHANGELOG, 본 보고서를 갱신한다. ADR-069~074 및 기존 history를 보존하고 Phase 진행률/DoD 체크는 변경하지 않는다.

12개 변경 문서의 strict UTF-8 decode/비어 있지 않음/fence balance/secret-token pattern·로컬 개인 path scan이 PASS다. 해당 문서의 상대 file links 444개가 모두 존재한다. ADR 75개 번호 중복 0, 새 ADR-075 filename/title/index 일치 PASS다. `git diff --check` PASS이며 Git의 LF→CRLF 안내만 있었다. backend/ai_worker/frontend/.github와 ADR-074 diff는 비어 있다. 이번 문서는 Mermaid를 추가하지 않으므로 Mermaid runtime 검증은 N/A다. 이는 외부 URL availability 또는 전체 저장소 모든 secret을 완전 검증했다는 주장이 아니다.

runtime tests·Python/lint/build·migration·사용자/production DB·실제 Provider 호출·authentication/Worker integration은 모두 미수행이다. docs-only 설계 작업이며 해당 기능 변경이 없기 때문이다. 기존 DB entry의 역사적 수치를 이번 작업에서 전면 재검증/정리하지 않았다.

## 후속 handoff

V1 의미 결정의 Draft 종료이지 production 권한 구현 완료가 아니다. 다음 권한 요청은 Rights Persistence Foundation으로 한정하고 migration/ORM/tests를 별도 승인 범위로 검증한다. 이어 authenticated writer/evidence, Completion audit port 최소 이행, production adapter 및 rollout/access inventory가 필요하다. 본 Draft PR을 Ready/merge하지 않는다. commit/remote PR/Actions 결과는 최종 외부 보고로 기록하고 그것을 이 보고서에 선기입하지 않는다.
