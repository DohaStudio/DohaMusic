# Active Provisioning Verifier Material Foundation 검증

> 상태: Foundation Draft 검증
> 최종 수정일: 2026-09-20
> 계약: [ADR-095](../11-decisions/ADR-095-active-provisioning-verifier-material-foundation.md)

## 검증 범위

Disposable root/verifier Ed25519 key와 격리된 Windows ACL fixture만 사용한다. fixed material source의 physical identity/custody, canonical bounded codec, ACTIVE authority receipt와 exact key/fingerprint 결합, parent/material same-handle reread, lease/session/transaction 수명을 검증한다.

Wrong key ID/fingerprint/public bytes, purpose/domain/producer/installation, source/revision/head, bool revision, malformed/duplicate/noncanonical/oversize JSON, stale/superseded/revoked key, material replacement와 transaction 교체를 fail closed로 확인한다. 병렬 decode는 동일 결과이며 mismatch 후 stale handle과 parent attempt가 재활성화되지 않는다.

결과는 provider-internal opaque handle뿐이다. signer/private key, Original Confirmation authenticity, CurrentnessWitness 또는 admission API는 없다. app DB, external journal schema, Alembic, Repository commit/rollback, production port와 실제 credential 변경은 0이다.

## 2026-09-20 검증 결과

- direct material regression: `10 passed`
- ADR-087~095 bootstrap authority focused regression: `570 passed`
- Ruff check / Ruff format check / compileall / `git diff --check`: PASS
- Alembic: `20260918_0037` single head
- Windows close failure(FALSE/exception), quarantine retention/retry, parallel verification, rotate/supersede, stale material/scope/transaction을 포함한다.
