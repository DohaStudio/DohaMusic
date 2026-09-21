# Admission Commit Reconciler Foundation 검증

> 상태: Foundation Draft 검증
> 최종 수정일: 2026-09-21
> 계약: [ADR-101](../11-decisions/ADR-101-admission-commit-reconciler-foundation.md)

## 범위

Disposable SQLite journal과 deterministic signed candidate/Windows ceremony fixture만 사용한다. Commit 전/후 response-loss를 주입해 opaque handoff를 만들고 별도 read Sessions의 complete history와 head를 두 번 검증한다. 실제 production journal/DB/key/credential/admission은 사용하지 않는다.

Regression은 `COMMITTED_EXACT`, exact-predecessor `NOT_COMMITTED`, same ID/revision partial-match `CONFLICT`, malformed/truncated/moving/read/close failure `UNAVAILABLE`, exact replay, concurrent replay, forged/copied/known-result handoff, wrong journal engine, read-only SQL과 result non-authority를 포함한다.

## 검증 결과

- Reconciler + Transaction Owner focused: `28 passed`
- Bootstrap authority direct-impact 21 files: `757 passed`
- Full backend: `2580 passed / 12 skipped / 0 failed`
- Ruff check / Ruff format check (`526 files`) / compileall / `git diff --check`: PASS
- strict UTF-8 (`11 files`) / relative links / ADR 101개 unique·indexed / secret·local-path·conflict scan: PASS
- Alembic: `20260918_0037`, single head
- 기존 Starlette/httpx deprecation warning 1개는 숨기지 않았다.
- Reconciler 실행 SQL: `SELECT` only
- reconciler append/CAS/DML/commit/retry/repair, schema/migration, production 접근: `0`

첫 focused 실패는 같은 immutable fixture journal에 GENESIS를 두 번 초기화한 테스트 구성 문제였다. Known-outcome handoff 검증을 별도 fixture로 분리해 lifecycle을 보존했고, connection close failure가 `UNAVAILABLE`인지 별도 regression으로 고정했다. Test 삭제·skip·timeout 완화는 없다.
