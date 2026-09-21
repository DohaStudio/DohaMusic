# Durable Admission Orchestration Foundation 검증

> 상태: Foundation Draft 검증
> 최종 수정일: 2026-09-22
> 계약: [ADR-102](../11-decisions/ADR-102-durable-admission-orchestration-foundation.md)

## 범위

Disposable SQLite journal과 deterministic signed lifecycle fixture만 사용한다. 실제 production journal/DB/User DB/key/credential/admission에는 접근하지 않는다. Existing live CurrentnessWitness에서 시작해 Provider, Owner, Reconciler를 exact component identity로 조합한다.

Focused regression은 direct commit, pre-provider/provider failure, direct `NOT_COMMITTED`, ambiguous durable/non-durable commit, reconciled `COMMITTED_EXACT`/`NOT_COMMITTED`/`CONFLICT`/`UNAVAILABLE`, read-only replay, forged component result, wrong component graph, same-witness overlap, result-construction failure와 registry cleanup을 포함한다.

## 검증 결과

- Orchestrator + Transaction Owner + Reconciler focused: `39 passed`
- Bootstrap authority direct-impact 23 files: `863 passed`
- Full backend: `2591 passed / 12 skipped / 0 failed`
- Ruff / format (`528 files`) / compileall / `git diff --check`: PASS
- strict UTF-8 (`10 files`) / relative links (`6 docs`) / ADR-102 unique·indexed / secret·local-path·conflict scan: PASS
- Alembic: `20260918_0037`, single head
- Orchestrator direct SQL/CAS/journal commit, blind retry, witness resurrection, app success authority: `0`

초기 focused 실행은 전역 Python의 기존 `rfc8785` 의존성 부재와 sandbox temp ACL로 수집이 중단됐고, pinned dependency 복원 및 repository-writable basetemp/승인된 test execution으로 해결했다. 첫 concurrency fixture는 main-thread SQLite Session을 worker thread로 넘겨 정지했으므로 owner commit 경계의 deterministic overlapping re-entry regression으로 교체했다. Product code failure나 test 삭제·skip·timeout 완화는 없었다.

Full suite의 `16664` warnings는 기존 Python 3.12 SQLite default datetime adapter deprecation 반복이며 이번 Foundation이 새 warning을 추가한 것은 아니다.
