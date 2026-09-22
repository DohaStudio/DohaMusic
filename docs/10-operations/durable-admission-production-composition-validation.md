# Durable Admission Production Composition Foundation 검증

> 상태: Foundation Draft 검증
> 최종 수정일: 2026-09-22
> 계약: [ADR-103](../11-decisions/ADR-103-durable-admission-production-composition-foundation.md)

## 범위

Disposable source files와 SQLite external journal만 사용한다. Production DB/User DB, 실제 credential/private key, startup/Worker/API에는 접근하지 않는다. 기존 chain의 exact component identity와 caller/external journal transaction 분리만 검증한다.

Focused 검증은 complete graph activation/delegation, required dependency별 누락, subclass test double, unconditional unavailable production default, wrong caller Session과 app/journal alias, duplicate graph, root shutdown과 surrounding context cleanup, transaction ownership을 포함한다.

## 실행 Gate

```text
python -m pytest backend/tests/test_production_admission_composition.py -q
python -m pytest <bootstrap authority direct-impact files> -q
python -m pytest backend/tests -q
python -m compileall -q backend
python -m ruff check .
python -m ruff format --check .
git diff --check
```

## 검증 결과

- Composition focused: `19 passed`
- Bootstrap/Durable Admission direct-impact 24 files: `882 passed`
- Full backend: `2610 passed / 12 skipped / 0 failed`
- compileall / Ruff lint / Ruff format / `git diff --check`: PASS
- Alembic: `20260918_0037`, single head
- Fake/in-memory/no-op production fallback, test provider production import, hardcoded private key, implicit owner, app DB admission authority, unsafe activation fallback: `0`

첫 focused 실행은 Windows sandbox의 기본 pytest temp ACL 때문에 setup에서 중단되어 승인된 repository basetemp로 재실행했다. Full 검증 중 deep worktree 내부 basetemp와 music-director storage key가 Windows legacy path 길이를 넘겨 `os.link`가 실패하는 실행환경 문제를 재현했다. 동일 case는 짧은 전용 test root에서 `3 passed`였고, 최종 full suite도 같은 짧은 root에서 위 수치로 완주했다. Product publish logic, timeout, skip 또는 Gate는 변경하지 않았다.
