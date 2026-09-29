# Production External Journal Factory Foundation 검증

> 상태: Foundation Draft 검증
> 최종 수정일: 2026-09-29
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

## 최초 Foundation 검증 이력

- Production configuration + lifecycle journal + Runtime Factory focused: `156 passed`
- Bootstrap/Durable Admission direct-impact 13 files: `354 passed / 0 failed / 0 skipped`
- Full backend: `2700 passed / 12 skipped / 0 failed`, 10570.50s (native Windows)
- compileall / Ruff lint / Ruff format (`536 files`) / `git diff --check`: PASS
- 변경 8 files strict UTF-8, relative links 2274개, ADR 106개 unique·indexed, conflict marker / secret / local-user-path scan: PASS
- Alembic: `20260918_0037`, single head

초기 `NullPool` 설계는 Session 사이에 SQLite connection을 닫아 idle runtime의 rename replacement를 막지 못했다. 하나의 runtime-pinned connection과 single active root Session으로 최소 수정해 Transaction Owner/Reconciler가 동일 opened file을 사용하고 ordinary replacement를 차단한다. SQLite integrity check가 만드는 empty `temp` database entry는 허용하되 다른 attached database는 거부한다. 기존 Python 3.12 SQLite datetime adapter deprecation warning `16664`건 외 새 warning은 없다.

## Session cleanup 경합 수정 검증 (2026-09-29)

기준 PR head는 `84b9c85d3d0d7a3155eef5e1a929d1f69daee37c`다. 이전 11개 문서 정렬은 보존했다. 위 최초 Full Backend 결과는 이번 source 수정의 완료 근거로 재사용하지 않는다.

### 원인과 잠금 경계

`_sessions`는 발급된 capability의 registry이자 다음 root Session의 admission guard다. 기존 구현은 Session close 전에 registry를 비워 같은 StaticPool 연결에서 두 root transaction lifetime이 겹칠 수 있었다. Event로 첫 close를 정지하고 다른 thread가 admission 경계에 도달하도록 한 회귀 테스트는 수정 전 `acquired == []` 단언에서 실패했다(실제 두 번째 Session 발급, 첫 transaction active). 실제 데이터 손실을 재현하거나 주장한 것은 아니다.

기존 `_lock` 안에서 Session close를 완료한 뒤 registry를 제거한다. 초기 verification 실패의 close와 runtime shutdown의 Session close/Engine dispose도 같은 잠금 경계를 사용한다. close 실패는 안전한 `ProductionExternalJournalFactoryDenied`로 변환하고 `_closed=True`를 먼저 설정하여 기존 capability와 이후 admission을 영구 거부한다. 별도 상태 머신, fallback, 새 authority는 없다.

현재 SQLAlchemy Session close는 expunge와 root/nested transaction close를 수행하고 Connection을 반환한 뒤 transaction-end event를 호출한다. 실제 Runtime은 기본 Session을 사용하며 해당 close event에서 Runtime lock을 요청하는 callback은 등록돼 있지 않다. Transaction Owner/Reconciler도 Runtime cleanup lock을 역순으로 요청하지 않는다. Shutdown은 Session close → Engine dispose → Factory의 native path lease release 순서를 유지한다. `RLock` 종류만을 안전성 근거로 삼지 않았다.

### 회귀 범위

- Event/lock 경계 관찰로 cleanup 중 두 번째 root Session 미발급, close 후 순차 재발급과 동일 DBAPI connection 재사용을 검증한다. sleep/polling은 사용하지 않는다.
- close 실패의 safe error, 영구 거부, registry 정리, 이전 capability 무효화와 fallback 부재를 검증한다.
- 기존 nested open, orderly reopen, close 후/wrong-thread capability 거부를 유지하고 다른 thread의 active overlap, foreign runtime, root transaction 교체 거부를 추가했다.
- Transaction Owner의 commit/rollback·ambiguous commit, Reconciler의 독립 read-only snapshots·read/close failure, Durable Admission과 caller-owned transaction 회귀를 실행한다.

### 이번 수정의 검증 결과

- Focused(configuration/lifecycle journal/Factory): `160 passed / 0 skipped / 0 failed`, process exit `0`, JUnit 확보.
- Direct-impact 10 files(configuration/private source/Factory/Transaction Owner/Reconciler/AdmissionAttempt/Durable Admission/Production Composition/CurrentnessWitness/lifecycle journal): `283 passed / 0 skipped / 0 failed`, process exit `0`, JUnit 확보.
- Full Backend: `2704 passed / 12 skipped / 0 failed`, `916.35s` (native Windows, Python 3.12.5 / SQLAlchemy 2.0.36 / cryptography 50.0.1). pytest process exit `0`과 JUnit `tests=2716, failures=0, errors=0, skipped=12`를 모두 확인했다.
- 전체 실행 전후 tracked Python/Backend 550개 파일의 정규화 SHA-256 manifest가 동일하다: `190732a7277401066d5ac347a0bcf364fb748e5891e94b9799418df5c3e14275`. 커밋 전 검증한 source를 그대로 반영하며 이후 CI는 새 exact PR head로 확인한다.
- compileall / Ruff lint / Ruff format / diff check: PASS. 문서 395개 strict UTF-8·fence, 상대 링크 2,288개: PASS. 전체 PR 변경 파일에서 secret/credential/private key/사용자 절대 경로와 raw handle·trace·PID·command·provider response 노출을 검토했고 발견 `0`이다.
- Warning은 기존 Python 3.12 SQLite datetime adapter deprecation `16664`건이다. Skip 12건은 기존 opt-in/환경 조건이며 실패로 숨긴 항목은 없다.
- Existing-only/Windows identity/schema·integrity·history 계약은 유지한다. Factory에 create/schema initialization/GENESIS/migration/repair/history rewrite/commit/admission/activation 경로를 추가하지 않았다.
- `20260918_0037` single Alembic head, 새 revision·application schema delta `0`. 실제 사용자 DB 접근·production provisioning·activation `0`.
- 이전 current 문서 충돌 `12/12` 해결을 보존하며 current 문서 116개와 ADR index를 재검토했다. 새 CURRENT contradiction·ADR index stale state `0`. 역사적 기록·Phase/DoD 진행률은 변경하지 않는다.

새 결정이나 authority 변경이 아닌 ADR-106 lifetime 계약 복구이므로 ADR 원문은 유지한다. 다음 Bootstrap 작업 후보는 별도 Production External Journal Provisioning Contract/Foundation이며 이번 작업에서는 구현하지 않는다.
