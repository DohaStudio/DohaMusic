# Production Deployment Configuration Foundation 검증

> 상태: Foundation Draft 검증
> 최종 수정일: 2026-09-23
> 계약: [ADR-104](../11-decisions/ADR-104-reviewed-production-deployment-configuration-foundation.md)

## 범위

실제 production path, DB, journal, private source, credential을 열지 않는다. Canonical disposable bytes와 independently supplied public expectations만으로 configuration routing 계약을 검증한다.

Focused 검증은 exact parse, missing/duplicate/unknown field, wrong installation/deployment/source/material/confirmation/lineage/journal, wrong environment/profile/domain/version, bool/int confusion, relative·traversal·UNC·device·ADS·reserved/test/Fake path, private/journal containment, hostile expectations subclass와 authentication substitution을 포함한다.

Junction/reparse/ACL/same-handle 검증은 configuration이 path를 열지 않으므로 기존 Windows source custody layer의 책임이다. Parse 성공을 그 검증의 성공으로 해석하지 않는다.

## 실행 Gate

```text
python -m pytest backend/tests/test_production_deployment_configuration.py -q
python -m pytest <bootstrap/authentication direct-impact files> -q
python -m pytest backend/tests -q
python -m compileall -q backend
python -m ruff check .
python -m ruff format --check .
git diff --check
```

## 검증 결과

- Configuration focused: `60 passed`
- Bootstrap/authentication/Durable Admission direct-impact 26 files: `976 passed`
- Full backend: `2670 passed / 12 skipped / 0 failed`
- compileall / Ruff lint / Ruff format / `git diff --check`: PASS
- strict UTF-8 / relative links / secret·local-path·fallback scan: PASS
- Alembic: `20260918_0037`, single head

초기 path validation은 root 문자열 자체만 bounded 처리해 최장 fixed source filename을 붙였을 때 Windows legacy 260자 경계를 넘을 여지가 있었다. 실제 fixed filename을 포함한 최종 path 길이로 fail closed하도록 수정하고 long-root regression을 추가했다. Full suite는 deep worktree 경로 영향을 피하기 위해 짧은 전용 basetemp에서 실행했으며 product path semantics, timeout 또는 skip은 변경하지 않았다.
