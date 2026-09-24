# Production External Journal Factory Foundation 검증

> 상태: Foundation Draft 검증
> 최종 수정일: 2026-09-24
> 계약: [ADR-106](../11-decisions/ADR-106-production-external-journal-factory-foundation.md)

## 범위

Repository 내부 disposable Windows journal fixture만 사용한다. 실제 production journal/DB/private source/credential/key에는 접근하지 않는다. Factory는 reviewed exact descriptor가 지정한 existing journal만 열며 provisioning, authentication, admission 또는 activation을 수행하지 않는다.

Focused 검증은 valid existing journal, missing journal no-create, empty/no-GENESIS, wrong identity/installation/path, exact schema, digest corruption, truncation/revision reset, canonical path attacks, rename replacement lifetime, overlapping/cross-thread capability, orderly reopen/cleanup과 no-mutation을 포함한다.

## 실행 Gate

```text
python -m pytest backend/tests/test_production_deployment_configuration.py backend/tests/test_bootstrap_lifecycle_journal.py backend/tests/test_production_external_journal_factory.py -q
python -m pytest <bootstrap/direct-impact files> -q
python -m pytest backend/tests -q
python -m compileall -q backend
python -m ruff check .
python -m ruff format --check .
git diff --check
```

## 검증 결과

- Production configuration + lifecycle journal + Runtime Factory focused: `156 passed`
- Bootstrap/Durable Admission direct-impact 13 files: `354 passed / 0 failed / 0 skipped`
- Full backend: `2700 passed / 12 skipped / 0 failed`, 10570.50s (native Windows)
- compileall / Ruff lint / Ruff format (`536 files`) / `git diff --check`: PASS
- 변경 8 files strict UTF-8, relative links 2274개, ADR 106개 unique·indexed, conflict marker / secret / local-user-path scan: PASS
- Alembic: `20260918_0037`, single head

초기 `NullPool` 설계는 Session 사이에 SQLite connection을 닫아 idle runtime의 rename replacement를 막지 못했다. 하나의 runtime-pinned connection과 single active root Session으로 최소 수정해 Transaction Owner/Reconciler가 동일 opened file을 사용하고 ordinary replacement를 차단한다. SQLite integrity check가 만드는 empty `temp` database entry는 허용하되 다른 attached database는 거부한다. 기존 Python 3.12 SQLite datetime adapter deprecation warning `16664`건 외 새 warning은 없다.
