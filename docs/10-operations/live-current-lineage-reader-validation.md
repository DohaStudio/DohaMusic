# Live Current-Lineage Reader Foundation 검증

> 상태: [검증 완료 — Foundation Draft 전용; 운영 미활성]
> 최종 수정일: 2026-09-19
> 구현 계약: [ADR-091](../11-decisions/ADR-091-confirmation-verifier-reuse-live-lineage-foundation.md)

## #177 Final Validation·BASE

START develop `034ca95a9173bf3a6f2950df93351c001214373c`, H `265def8892169fe26338db46f5bc6b5f12648175`, T `8b12457ab1a4f86095213c0f4fb0e28254d6ea4c`. Run `35428055920` required 3 SUCCESS, reviews·REQUEST_CHANGES·threads 0, MERGEABLE·CLEAN과 Ready 후 동일 Gate/develop race 0을 확인해 expected-head squash merge했다. Merge/new BASE `edab5d461e8f2be393fc1e1c7d0bc772d9bf2de5`, PR/merge/develop tree equality와 source/main 보존을 확인했다.

## Audit·구현·발견 문제

Verifier reuse는 C infrastructure-only로 판정했다. 기존 deployment approval root/key purpose/domain/lifecycle/receipt를 confirmation authority로 확대하지 않았다. Authenticity를 Fake로 구현하지 않고 E live-current-lineage-first held record mechanics를 선택했다.

초기 negative suite에서 float case가 `rfc8785.dumps(1.0)`에 의해 integer wire로 정규화되어 공격을 재현하지 못했고, revision 1 action의 predecessor 변경은 reader 전에 domain constructor가 차단했다. 실제 JSON float wire와 revision 2 successor fixture로 교정했다. 구현 Gate나 테스트를 삭제·skip하지 않았다.

최종 source/test 고정 후 새 negative `35 passed`, focused 10 files `480 passed`, direct 20 files `906 passed`, full backend `2384 passed / 12 skipped / 0 failed`다. Ruff/format/compileall/diff/UTF-8/relative links/ADR·보호 범위/security scan은 PASS, Alembic은 `20260918_0037` single head다. Repository `commit()`/`rollback()`과 app/external schema migration/production port 변경은 0이다. 기존 Starlette/httpx deprecation warning 1개 외 새 warning은 없다.
