# AdmissionAttempt Provider Foundation 검증

> 상태: Foundation Draft 검증
> 최종 수정일: 2026-09-21
> 계약: [ADR-099](../11-decisions/ADR-099-admission-attempt-provider-foundation.md)

## 범위

Disposable Ed25519 key와 격리 SQLite journal/Windows ceremony fixture만 사용한다. Live ADR-098 CurrentnessWitness를 strict canonical rotation/revoke/redesignation candidate, exact predecessor/head/revision/scope, correlation digest, native lease와 caller root transaction에 결합한다. 실제 external journal commit, production key/credential 또는 admission은 수행하지 않는다.

Negative regression은 forged/copied attempt, wrong/consumed witness, malformed·mutable event/manifest, noncanonical manifest, stale head/revision, bool/int confusion, wrong scope/current key, extra key, current designation record 재사용/잘못된 designation identity, GENESIS 우회, duplicate/concurrent prepare, transaction replacement, journal/lineage/correlation 이동과 consumer exception을 포함한다. 실패 후 witness/attempt resurrection을 거부하고 duplicate loser가 winner를 폐기하지 않는지 확인한다.

## 검증 결과

- focused AdmissionAttempt regression: `27 passed`
- Bootstrap authority direct-impact regression: `824 passed`
- full backend: `2552 passed / 12 skipped / 0 failed`
- Ruff check / Ruff format check (`522 files`) / compileall / `git diff --check`: PASS
- strict UTF-8 (`10 files`) / relative links (`216`) / ADR 99개 unique·indexed / secret·local-path·conflict scan: PASS
- schema/migration/Repository `commit()`·`rollback()` 추가: `0`
- production private key/credential/journal/DB/admission 접근: `0`
- Alembic expected head: `20260918_0037`, single head
- external transaction owner/reconciler/Durable Admission success: `0`

Full suite의 기존 Starlette/httpx deprecation warning 1개는 숨기거나 제거하지 않았다. 첫 system Python 실행은 `rfc8785` dependency 부재로 collection 전에 중단됐으며 PASS evidence가 아니다. Windows virtualenv launcher의 child process 출력을 별도 test log에 고정해 최종 단일 실행 summary를 확인했다. Test skip 추가, Gate 완화, 실제 production 접근은 0이다.
