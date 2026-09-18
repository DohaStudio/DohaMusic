# DohaVocal Rights Persistence Foundation 검증

> 2026-09-18 / fixture-only 검증 / Draft PR 범위

## 기준과 구현 경계

기준 develop은 `7db03b7e21956472c968ce38b28ab90e4d2dae69`다. ADR-075의 merge된 Decision 본문은 변경하지 않았다. ADR-074, acquisition orchestration, 기존 Completion service, Export authority, Provider/Worker/API/frontend/workflow 구현은 변경하지 않았다.

최초 migration은 `20260918_0036`, parent는 실제 source single head `20260911_0035`다. 후속 integrity migration `20260918_0037`의 parent는 `0036`이며 기존 migration/V1 DDL은 수정하지 않았다. 새로운 11개 table로 metadata는 56 → 67이며 기존 `WORKSPACE_ENTITY_CLASSES` 39개는 유지된다. SQLite 대상 실제 FK 27개, UNIQUE 22개, CHECK 22개, explicit index 4개는 동일하고 0037/metadata의 integrity triggers는 34개다.

schema/mapper, frozen versioned DDL, caller-owned Session의 flush-only persistence repository만 구현했다. authenticated Writer, Revoke/Supersede application orchestration, Evidence policy validation, production Rights Adapter, Completion production wiring, authentication, OUTPUT_READ authorization은 미구현이다. raw persisted facts는 effective permission이 아니다.

authority key는 owner/workspace/typed subject UUID/operation/usage role의 exact tuple이며 unique ScopeGuard와 CurrentAuthority의 composite unique로 표현한다. immutable Grant/event ledger와 nullable same-authority current pointer를 분리했다. semantic revision은 0에서 시작해 GRANTED/REVOKED/SUPERSEDED event마다 정확히 +1이다. Evidence의 opaque identity/SHA-256/policy/holder/verifier/exact scopes와 final-only Completion receipt/items는 closed immutable aggregate다. ScopeGuard/EvidenceGuard의 actual conditional `UPDATE ... SET guard_epoch = guard_epoch + 1 WHERE id = :id AND guard_epoch = :expected`는 rowcount=1만 성공하며 caller transaction이 종료될 때까지 SQLite write lock을 유지한다. guard epoch은 semantic revision이 아니다. 기존 Approval/consent/output을 ACTIVE Grant 또는 fake receipt로 backfill하지 않는다.

## 초기 H 실행 검증 (역사)

아래 수치는 초기 PR head `2ab254232b1914c2d5f094767695c2b3ea905a88`의 작업 기록이다. 이 결과만으로 아래 REPLACE gap이 검증됐다고 주장하지 않는다.

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

## ScopeGuard Integrity Blocker Resolution

시작 H는 `2ab254232b1914c2d5f094767695c2b3ea905a88`, T는 `9241b57ab1705c43a8b33659d139bf8b2ad9a0a5`였다. 기본 FK ON / recursive triggers OFF에서 같은 ID와 다른 ID의 REPLACE로 빈 guard epoch 1 → 0 및 expected_epoch=0 재성공을 이번 수정 전에 재현했다. 원인은 REPLACE implicit DELETE가 recursive triggers OFF에서 DELETE trigger를 실행하지 않는다는 점이다.

0037/frozen V2 DDL은 existing PK 또는 owner/workspace key의 INSERT를 conflict 처리한다. recursive triggers ON에 의존하지 않으며 기존 0036/V1 DDL, repository, ADR-075 Decision과 serialization contract는 보존했다. metadata와 migration 경로의 direct SQL OR REPLACE/REPLACE, OR IGNORE/UPSERT/UPDATE OR REPLACE, stale CAS, 정상 ensure/CAS, partial-authority whole transaction rollback, existing 0036 facts 보존 upgrade 및 DDL fault rollback 20건은 모두 통과했다. 0037 downgrade는 anchor facts가 있으면 보호를 제거하지 않는다.

| 이번 수정 최종 검증 | 결과 |
|---|---|
| REPLACE/default-setting 회귀 | 20 passed / 0 failed / 0 skipped, 20.13초 |
| Rights focused (기존 90 + 신규 20) | 110 passed / 0 failed / 0 skipped, 41.75초 |
| 직접 영향 회귀 / Completion | 352 passed / 0 failed / 4 skipped, 170.55초; Vocal Completion 33건·Workspace Completion UoW 14건 포함 |
| 전체 backend | 1728 passed / 0 failed / 12 skipped, 846.08초 |
| static/security | compileall/Ruff/format/diff/strict UTF-8/links/fences/added-content scan PASS; 변경 27개 파일·문서 상대 링크 176개, commit 전 재확인 |

최신 head 기대값 변경은 migration 추가에 따른 검증 정합화뿐이다. Writer/Adapter/Auth/Worker/API/frontend/Completion production wiring·Approval/Consent semantics 변경 0. 사용자·production DB/Provider/storage 접근 0. PR #161은 OPEN/Draft 유지하며 Ready/merge는 새 head의 별도 Final Validation이다.

이번 focused/direct/full 실행은 각각 기존 dependency deprecation warning 1건이며, 전체 skip 12건은 앞서 기록한 opt-in 실제 runtime/유료 API 5건과 Windows symlink 권한 부족 7건이다. 실패를 skip/delete로 숨기지 않았다. 신규 20개는 skip 0건이다. 최종 commit/normal push의 SHA와 새 exact-head CI 상태는 최종 작업 보고에 기록하며 CI 완료 전 SUCCESS로 표현하지 않는다.

## 운영 한계와 후속 작업

source 기본 SQLite와 disposable fixtures만 검증했다. 실제 production engine/configuration, PostgreSQL/MySQL 동등 locking/isolation, offline SQL와 다른 SQLite driver는 미검증이다. unsupported backend 및 FK enforcement가 없는 write는 fail closed한다. 운영 DB 적용, ownership writer의 guard 참여, authenticated principal/current owner 증명과 Evidence 검증은 별도 gate다.

다음 분류는 `RIGHTS_WRITER_AUTHENTICATION_PREREQUISITE`다. 별도 minimal port/audit adaptation은 persistence facts와 explicit test Fake를 기준으로 병렬 진행 가능하지만 production enable은 Writer/Auth/ownership/운영 DB gate 완료 전 불가다. 이번 작업은 정상 commit/push 및 develop 대상 Draft PR까지이며 Ready/merge/auto-merge, 보호 PR #160/#159/#130 변경은 수행하지 않는다. exact-head Actions 상태는 Draft PR 생성 후 최종 작업 보고서에 별도로 기록한다.
