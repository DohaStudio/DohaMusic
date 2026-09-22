# Production Private Authority Source Factory Foundation 검증

> 상태: Foundation Draft 검증
> 최종 수정일: 2026-09-23
> 계약: [ADR-105](../11-decisions/ADR-105-production-private-authority-source-factory-foundation.md)

## 범위

Canonical disposable configuration bytes만 사용한다. Production private source, DB, journal, credential 또는 key를 열지 않는다. Factory가 exact six-role immutable descriptor만 만들고 existing custody/readers의 handle·ACL·TOCTOU 책임을 침범하지 않는지 검증한다.

Focused 검증은 role/identity/fixed filename/path mapping, missing source 무접근, wrong installation/deployment/source, duplicate identity, traversal/UNC/device/ADS/lowercase drive/test path, wrong filename, hostile factory/role, descriptor immutability와 authority/open API 부재를 포함한다.

## 실행 Gate

```text
python -m pytest backend/tests/test_production_deployment_configuration.py backend/tests/test_production_private_source_factory.py -q
python -m pytest <bootstrap/authentication/direct-impact files> -q
python -m pytest backend/tests -q
python -m compileall -q backend
python -m ruff check .
python -m ruff format --check .
git diff --check
```

## 검증 결과

- Production configuration + Source Factory focused: `76 passed`
- Bootstrap/authentication/Durable Admission direct-impact 27 files: `992 passed / 0 failed / 0 skipped`
- Full backend: `2686 passed / 12 skipped / 0 failed`
- compileall / Ruff lint / Ruff format (`534 files`) / `git diff --check`: PASS
- 변경 8 files strict UTF-8, relative links 211개, ADR 105개 unique·indexed, conflict marker / secret / local-user-path scan: PASS
- Alembic: `20260918_0037`, single head

초기 canonical path parser는 Windows drive letter의 lowercase alias를 허용해 같은 경로에 복수 wire 표현이 가능했다. Uppercase drive만 허용하도록 최소 수정하고 configuration과 factory regression을 추가했다. 실제 junction/reparse·hardlink·native identity·ACL·same-handle 검사는 descriptor 단계에서 추측하지 않고 기존 custody layer에 남겼다. 기존 Python 3.12 SQLite datetime adapter deprecation warning `16664`건 외 새 warning은 없다.
