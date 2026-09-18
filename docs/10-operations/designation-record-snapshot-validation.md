# Designation Record Snapshot Foundation 검증

> 상태: [로컬 Gate PASS; 별도 Draft 대상·운영 비활성]
> 작성일·최종 수정일: 2026-09-19
> 관련: [ADR-085](../11-decisions/ADR-085-designation-record-snapshot-foundation.md)

## #170 Final Validation / merge

- START develop `688b5f77ad1fb17bb0356e884574171c73921c42`.
- H `1b8d4c5bf9ddb644eca33676b837bd944d977231`, T `428e0e9d9d0a2c6789b1826558f0f7fc49e94ae7`.
- exact-head run `35372586416`: backend-ubuntu/ffmpeg-windows/frontend-playwright COMPLETED/SUCCESS.
- OPEN/Draft/develop base/local=remote=PR H/T/clean/docs-only/reviews·REQUEST_CHANGES·threads 0/MERGEABLE·CLEAN. ADR-084와 076/077/078/080을 대조했다. Ready 후 same H/T/develop/base/CI/reviews 확인 후 expected-head SQUASH MERGE.
- MERGED SHA/new BASE `bebf693fb41358abdddaf5d4110686323222cf2b`; merge tree = T, source H/main 보존.
- 기존 #170 focused 225/direct 617/full 2129 passed·12 skipped evidence는 기존 backend에만 유지했다. 새 source evidence로 확대하지 않는다.

## 구현·재현·수정

B의 작은 직접 prerequisite인 fixed record snapshot과 live pin/currentness lifetime comparison이다. 전체 A provenance/custody proof reader나 current permission 구현이 아니다. 실제 source authenticity/ACL/human acceptance/designation eligibility·fresh journal/history/possession은 unavailable다.

- record context 종료/거절 뒤 same native lease로 새 handle을 발급하는 결함을 2개 regression으로 재현했다. original native lease permanent invalidation과 snapshot/witness 폐기로 수정했다. caller transaction/OS cleanup ownership은 보존한다.
- 최종 focused native Windows: 260 passed / 0 skipped / 0 failed, 5.73s.
- direct: 652 passed / 0 skipped / 0 failed, 65.99s.
- 새 full backend: 2164 passed / 12 skipped / 0 failed, 879.64s (14:39), native Windows. 이전 full 결과를 재사용하지 않았다.
- Ruff check/format(485 files)/compileall/diff/UTF-8/fences/relative links/ADR index·consistency/secret·local-path/authority audit PASS. mixed line-ending format 차이는 mechanical formatter로 수정했다.
- Alembic `20260918_0037` single head, Repository commit()/rollback() 0, snapshot/pin/lifetime/serialization SQL/flush/commit/rollback 0 보존.

raw technical text profile은 strict bounded UTF-8/exact original-byte digest이며 JSON semantic authority codec가 아니다. signature/governance proof로 처리하지 않는다. 테스트는 isolated disposable record bytes/public pin facts/placeholder witness mechanics만 사용한다. 실제 key/credential/approval/designation/ceremony/user DB/Provider 접근 0이다.

새 app migration/schema 변경 0, Alembic single head 0037/external journal v1/Phase·DoD 보존. native tests는 Windows required step에 추가하며 새 PR exact-head metadata는 PR 본문에 기록한다. 새 PR Ready/merge/source 삭제는 이번 범위가 아니다.
