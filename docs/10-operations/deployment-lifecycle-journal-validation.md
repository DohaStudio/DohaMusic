# Independent Lifecycle Journal Foundation 검증

> 문서 상태: [최종 로컬 Gate PASS — 별도 Draft PR, 운영 비활성]
> 최종 수정일: 2026-09-18
> 기준 develop: `61b91d1bfaaceca6e3befda9c09f2ad91341a4c2`
> 관련 문서: [ADR-079](../11-decisions/ADR-079-independent-lifecycle-journal-persistence-foundation.md), [DB 계약](../07-database/deployment-lifecycle-journal.md)

## #164 Final Validation

START develop `fdf71b4202486a99b9ababec898fd3ae3b664883`, H `da608e842549320541618292b96c7990380c4235`, T `bc3b8cde18471f3bd03cf12c5c59b9fcc12bcca2`. OPEN/Draft/develop base/local-remote head/tree/clean과 docs-only 12 files +157/-7, ADR-078 completeness, source conflict 0/reviews/request changes/threads 0, MERGEABLE/CLEAN을 확인했다.

run `35331340520`의 exact H에서 backend-ubuntu/ffmpeg-windows/frontend-playwright 모두 COMPLETED/SUCCESS다. Ready 후 동일 H/T/develop/CI/reviews/threads를 확인하고 expected-head squash merge했다. merge/new develop `61b91d1bfaaceca6e3befda9c09f2ad91341a4c2`, single parent=START develop, merge tree=T이고 source H는 보존했다. app Alembic 0037 single head다.

## 선택·문제 해결·실행 evidence

A 최소 unit: 독립 SQLite public journal schema v1/flush-only repository, ADR-078 strict Ed25519/JCS event verifier, immutable local history/pin mismatch 검사, unconditional unavailable private port 골격이다. 실제 admission/currentness/OS ceremony writer는 활성화하지 않는다.

초기 focused에서 oversized bytes가 pytest 자동 ID에 포함되어 Windows fixture 경로 한도 setup 오류 2개가 발생했다(68 passed). 짧은 deterministic ID로 입력/assert를 보존했다. 추가 safe-integer 초과 negative fixture는 test signer의 JCS가 먼저 거부하여 1 failed/77 passed였다. 유효 envelope의 raw JSON revision을 변조해 실제 verifier denial을 검증하도록 수정했다. DB 감사에서는 SQLite TEXT PRIMARY KEY 단독의 NULL 허용을 in-memory INSERT로 직접 재현했다(actual `(None,)`, expected deny). event ID에 explicit NOT NULL을 추가하고 repository를 우회한 raw-SQL regression에서 ledger/head 변경 없이 거부됨을 확인했다. production invariant 완화/skip/test 제거는 없다.

- 최종 focused: **81 passed / 0 failed / 0 skipped**, 1.82초.
- 최종 source direct: **392 passed / 0 failed / 0 skipped**, 61.32초(focused 81 포함). 중간 389/391 evidence는 최종 판정에 사용하지 않는다.
- 최종 source full backend: **1904 passed / 12 skipped / 0 failed**, 895.96초. collection 1916과 일치한다. 변경 전 중단한 run은 완료 evidence로 사용하지 않는다. 기존 Starlette/httpx deprecation warning 1개를 보존했다.
- schema transactional install/rollback/nonempty app DB rejection/backend deny, default recursive_triggers=0 REPLACE/UPSERT/delete/reset, NULL event ID/fingerprint reuse/terminal reactivation/stale head/duplicate ID deny PASS.
- thread와 별도 process의 concurrent rotation/revoke: 각각 winner 1/stale 1 PASS.
- injected guard-update fault는 event/head 모두 rollback, caller rollback/restart/lost response replay deny PASS.
- history terminal status 보존+taint/invalidation cutoff, pin rollback mismatch/equality도 unavailable, local truncation detection PASS.
- malformed/JCS/signature/domain/cross-signature/redesignation signer/wrong scope/fingerprint/clock/count/size/depth/safe integer negative PASS.
- Repository commit()/rollback() count 각각 0 PASS.
- compileall backend/ai_worker, Ruff lint/format(485 files), git diff --check PASS.
- strict UTF-8/fence/conflict/added-source secret/local-path scan, changed Markdown의 441 relative links, 79 unique indexed ADRs PASS.
- app Alembic `20260918_0037` single head 및 기존 migrations/ADR-077 source/DoD 무변경 PASS.
- #164 source 보존, #163/#162/#161/#160/#159 state/source mutation 0, #130 OPEN/Draft/source 보존, main `63633d462043ad3ba78fee92473d19e90c361431` 무변경 확인.

실제 User/production DB/Provider/keys/governance ceremony 접근 0이다. 테스트 keys는 deterministic disposable memory-only이며 raw key 저장 0이다. public facts는 trusted provisioning/currentness witness가 아니고 운영 chain은 unavailable다. full journal/key privileged clone/rollback·complete ceremony serialization·independent pin reconciliation의 실행 증거는 제공하지 않는다.

최종 docs 대조에서 README의 기존 'Rights schema 미구현'과 architecture의 Contract 작성 시점 'journal fact 구현 없음' 문구를 발견했다. #161/#164 merged 및 현재 A Foundation 범위와 일치하도록 문서만 정합화했다. 별도 normal docs commit 전후 backend/ai_worker/pyproject source diff는 0이므로 위 최종 local test evidence는 유지한다. 이전 head CI는 새 exact-head 판정에 사용하지 않고 normal push의 새 run으로 검증한다.
