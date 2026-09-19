# Initializer Provenance Binding Foundation 검증

> 상태: [로컬 검증 PASS — Draft 전용, 운영 미활성]
> 최종 수정일: 2026-09-19
> 계약: [ADR-087](../11-decisions/ADR-087-custody-policy-provisioning-initializer-provenance-contract.md), [ADR-088 구현](../11-decisions/ADR-088-initializer-provenance-action-binding-foundation.md)

## 시작 authority와 #174 Final Validation

START develop `54773b3ed4d4bfcee8bcc81000a4e6517c2245c0`, #174 H `d2b0f4556fc9a011e9c6756c69dc1a9075d929af`, T `4730047928ddcbc40e428af839eccb89e7436739`. OPEN/Draft/base develop/docs-only 9 files/clean worktree/reviews·REQUEST_CHANGES·unresolved threads 0/MERGEABLE·CLEAN 및 exact-head run `35399246493` required 3개 COMPLETED/SUCCESS를 확인했다. ADR-076/077/078/080/084/087 직접 감사에서 semantic conflict 0이다.

사용자 채팅의 #174 예외 명시 승인으로 Draft → Ready 후 same D/H/T/CI/reviews/threads/mergeability를 다시 확인했다. merge 직전 develop race 0, expected-head guarded squash merge했다. #174 MERGED, merge SHA/fixed BASE `655985b3432d4949ecae6d27e33ef8afb699c227`, PR tree = merge tree = T. #174 source branch H와 main 및 보호 PR을 보존했고 Final Validation 파일 수정은 0이다.

## 새 unit의 구현과 검증 범위

C의 pure strict binding comparison module 하나를 선택했다. 공개 policy/action/initializer confirmation/pin/history가 실제로 연결되는지 검증하지만 authenticated source/권한을 생성하지 않는다. full digest fields, bool/float/revision/custom equality/hash/malformed input/wrong initializer·installation·source·policy·provenance·pin field, replay/duplicate action, wrong predecessor, reset/truncate/anchor replacement, terminal-prefix rewrite, stale expected history, complete manifest 및 bounds를 negative 테스트한다.

정적 CAS predicate의 concurrent PASS는 실제 writer winner 1이 아니다. 실제 policy store CAS/rollback/crash/cleanup은 미구현이며 새 함수가 SQL/OS resource를 소유하지 않는다. 기존 journal CAS/concurrency·custody file/ACL replacement·snapshot/witness/lease transaction lifetime·Windows mutex/resource retained-cleanup regression은 함께 실행한다. original source authenticity가 없는 production ports는 unavailable, Fake fallback/permission/witness 발급 0이다.

## 검증 결과

| 검증 | 실제 결과 |
|---|---|
| 최종 새 comparison negative suite | 67 passed / 0 failed, 0.30s |
| 최종 focused 7 files | 370 passed / 0 skipped / 0 failed, 8.39s |
| 최종 direct 17 files | 762 passed / 0 skipped / 0 failed, 63.48s |
| 실제 full backend | 2256 passed / 12 skipped / 0 failed, 835.09s |
| 최종 backend collection | 2286 tests collected |
| Ruff check/format/compileall/diff | PASS, 500 Python files formatted |
| UTF-8/conflict/secret/local-path/relative links/ADR index | PASS, 466 relative links / 88 unique indexed ADRs |
| Alembic | `20260918_0037` single head |

Full은 최초 새 comparison 49개를 수집한 상태에서 실행했다. 실행 중 추가한 18개 negative tests는 최종 focused/direct 및 단독 67개 suite에서 별도로 모두 실행·통과했다. 구현 source는 full 시작 이후 변경하지 않았다. 따라서 full 수치를 최종 collection 2286개의 single-run 결과로 부풀리지 않는다. 각 pytest 실행에는 기존 Starlette/httpx deprecation warning 1개가 있었다. source repair/test 삭제/skip 추가/Gate 완화는 0이다.

기존 #174 CI와 실제 full/regression 결과를 새 provisioning/source authentication proof로 표시하지 않는다. 테스트는 disposable comparison/unsigned confirmation fixtures 및 기존 infrastructure fixtures만 사용한다. production/User DB/key/credential/ceremony/Provider는 사용하지 않는다. AST 검사에서 새 binding SQL/I/O/witness mint/commit/rollback 0, 기존 custody/snapshot/pin/journal/ports/CI/migration/DoD source diff 0을 확인했다.
