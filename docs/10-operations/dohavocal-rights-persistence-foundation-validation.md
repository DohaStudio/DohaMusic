# DohaVocal Rights Persistence Foundation 검증

> 2026-09-18 / fixture-only 검증 / Draft PR 범위

## 기준과 구현 경계

기준 develop은 `7db03b7e21956472c968ce38b28ab90e4d2dae69`다. ADR-075의 merge된 Decision 본문은 변경하지 않았다. ADR-074, acquisition orchestration, 기존 Completion service, Export authority, Provider/Worker/API/frontend/workflow 구현은 변경하지 않았다.

새 migration은 `20260918_0036`, parent는 실제 source single head `20260911_0035`다. 기존 migration은 수정하지 않았다. 새로운 11개 table로 metadata는 56 → 67이며 기존 `WORKSPACE_ENTITY_CLASSES` 39개는 유지된다. SQLite 대상 실제 FK 27개, UNIQUE 22개, CHECK 22개, explicit index 4개, integrity trigger 33개다.

schema/mapper, frozen versioned DDL, caller-owned Session의 flush-only persistence repository만 구현했다. authenticated Writer, Revoke/Supersede application orchestration, Evidence policy validation, production Rights Adapter, Completion production wiring, authentication, OUTPUT_READ authorization은 미구현이다. raw persisted facts는 effective permission이 아니다.

authority key는 owner/workspace/typed subject UUID/operation/usage role의 exact tuple이며 unique ScopeGuard와 CurrentAuthority의 composite unique로 표현한다. immutable Grant/event ledger와 nullable same-authority current pointer를 분리했다. semantic revision은 0에서 시작해 GRANTED/REVOKED/SUPERSEDED event마다 정확히 +1이다. Evidence의 opaque identity/SHA-256/policy/holder/verifier/exact scopes와 final-only Completion receipt/items는 closed immutable aggregate다. ScopeGuard/EvidenceGuard의 actual conditional `UPDATE ... SET guard_epoch = guard_epoch + 1 WHERE id = :id AND guard_epoch = :expected`는 rowcount=1만 성공하며 caller transaction이 종료될 때까지 SQLite write lock을 유지한다. guard epoch은 semantic revision이 아니다. 기존 Approval/consent/output을 ACTIVE Grant 또는 fake receipt로 backfill하지 않는다.

## 실행 검증

| 검증 | 최종 결과 |
|---|---|
| 신규 persistence/migration focused | 90 passed / 0 failed / 0 skipped, 360.32초 |
| 직접 관련 회귀 36개 모듈 | 352 passed / 0 failed / 4 skipped, 177.47초 |
| 전체 backend | 1708 passed / 0 failed / 12 skipped, 849.76초 |
| Ruff backend/ai_worker | PASS |
| Ruff format backend/ai_worker | PASS |
| compileall backend/ai_worker | PASS |
| diff / strict UTF-8 / 문서 링크·fence / added-content secret·절대 경로 | PASS: 변경 37개 파일, 문서 relative links 199개 |

신규 90건은 persistence 83건과 migration 7건이다. 실제 conditional UPDATE, rowcount=1, guard 순서·caller transaction 수명, 빈 anchor 경쟁, stale/overflow, 두 Session serialization, SQLite busy와 WAL snapshot conflict 및 whole-transaction restart, immutable ledger/raw SQL 차단, projection·semantic revision, cross-key integrity, sealed Evidence/receipt aggregate, withdrawal fact 무결성, receipt failure injection과 JobOutput/Job/receipt 동시 rollback을 검사한다.

migration은 fresh upgrade, representative legacy 0035 upgrade와 기존 전체 row/column 보존, ACTIVE/fake receipt backfill 0, empty downgrade/reupgrade, audit fact 존재 시 downgrade 차단, DDL failure rollback, metadata bootstrap failure rollback을 검증했다. 실제 사용자·production DB는 열거나 upgrade하지 않았다.

## 환경 실패와 최종 gate 구분

초기 실행의 기본 pytest temp 접근 거부와 긴 Windows fixture 경로 295자에 따른 기존 publisher 실패는 환경 문제였다. disposable fixture를 짧은 시스템 temp root로 바꾼 최종 실행을 gate로 사용한다. publisher/path 보안 규칙은 변경하지 않았다. 역사 migration 0012/0011의 table-set 기대값은 새 rights table을 제외하도록 보완했고, 관련 4개 테스트 재실행은 모두 통과했다. 중단된 실행과 이전 실패 실행은 PASS 근거로 사용하지 않는다.

각 최종 실행의 warning 1건은 기존 dependency의 Starlette/httpx deprecation이며 이번 범위에서 수정하지 않았다. skip은 PASS로 계산하지 않는다. 직접 회귀 skip 4건은 Windows symlink fixture 생성 권한 부족이다. 임시 DB, synthetic storage, JUnit log는 Git 산출물에 포함하지 않는다.

전체 skip 12건은 Windows symlink 권한 부족 7건과 opt-in 실제 ACE-Step benchmark/GPU, Demucs GPU, Seed-VC GPU, 유료 OpenAI smoke 5건이다. 실제 runtime 설치·Provider 호출·유료 API 승인 없이 해당 integration을 강제로 실행하지 않았다.

## 운영 한계와 후속 작업

source 기본 SQLite와 disposable fixtures만 검증했다. 실제 production engine/configuration, PostgreSQL/MySQL 동등 locking/isolation, offline SQL와 다른 SQLite driver는 미검증이다. unsupported backend 및 FK enforcement가 없는 write는 fail closed한다. 운영 DB 적용, ownership writer의 guard 참여, authenticated principal/current owner 증명과 Evidence 검증은 별도 gate다.

다음 분류는 `RIGHTS_WRITER_AUTHENTICATION_PREREQUISITE`다. 별도 minimal port/audit adaptation은 persistence facts와 explicit test Fake를 기준으로 병렬 진행 가능하지만 production enable은 Writer/Auth/ownership/운영 DB gate 완료 전 불가다. 이번 작업은 정상 commit/push 및 develop 대상 Draft PR까지이며 Ready/merge/auto-merge, 보호 PR #160/#159/#130 변경은 수행하지 않는다. exact-head Actions 상태는 Draft PR 생성 후 최종 작업 보고서에 별도로 기록한다.
