# CurrentnessWitness Handoff Foundation 검증

> 상태: Foundation Draft 검증
> 최종 수정일: 2026-09-21
> 계약: [ADR-098](../11-decisions/ADR-098-currentness-witness-handoff-foundation.md)

## 검증 범위

Deterministic disposable Ed25519 keys, 격리 SQLite journal과 Windows ACL/mutex fixture만 사용한다. ADR-097 exact correlation을 original `_ProviderWitnessLifetime`의 single attempt, native serialization lease, caller root transaction과 exact scope에 결합하고 발급 전후 및 매 사용 시 parent chain 전체를 재검증한다.

Forged/copied witness, bool/int confusion, hostile equality/hash, wrong attempt·transaction·lease·scope·correlation, lease release, provider rejection, stale confirmation·lineage·journal·pin·material·source, rotate/revoke 상당 변화, duplicate/concurrent issuance와 consumer exception을 fail closed로 검증한다. Actual witness의 실패는 one-way invalidation하고 foreign witness/attempt은 valid attempt를 폐기하지 않는다.

## 2026-09-21 검증 결과

- direct CurrentnessWitness regression: `23 passed`
- Bootstrap authority/Windows direct-impact regression: `621 passed`
- full backend 최종 수치: PR exact-head `backend-ubuntu`에서 고정
- Ruff check / Ruff format check (`520 files`) / compileall / `git diff --check`: PASS
- strict UTF-8 (`12 files`) / relative links / ADR 98개 unique·indexed / secret·local-path·conflict scan: PASS
- schema/migration/Repository `commit()`·`rollback()` 추가: `0`
- production private key/credential/production port 접근: `0`
- Alembic expected head: `20260918_0037`, single head
- Durable Admission 구현: `0`
