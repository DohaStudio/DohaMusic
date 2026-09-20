# Original Confirmation Authenticity Foundation 검증

> 상태: Foundation Draft 검증
> 최종 수정일: 2026-09-20
> 계약: [ADR-096](../11-decisions/ADR-096-original-confirmation-authenticity-foundation.md)

## 검증 범위

Deterministic disposable Ed25519 key와 격리된 Windows ACL fixture만 사용한다. held canonical confirmation, authenticated authority source와 ACTIVE material을 동일 designation/pin/lease/transaction 아래 결합하고 exact confirmation domain signature와 모든 payload/material/scope/lineage binding을 검증한다.

Invalid/truncated/wrong-key signature, authority-event 및 deployment-approval domain replay, wrong key ID/fingerprint/installation/producer, stale payload/material/transaction, confirmation/material replacement를 fail closed로 확인한다. 병렬 signature 검증은 deterministic하며 실패 뒤 authenticity와 양쪽 parent handle은 복원되지 않는다. 기존 raw snapshot/material close-failure와 quarantine regression도 focused suite에 포함한다.

결과는 provider-internal opaque handle뿐이다. signer/private key, CurrentnessWitness, admission, Rights API는 없다. schema/migration/Repository commit·rollback, production port와 실제 credential 변경은 0이다.

## 2026-09-20 검증 결과

- direct authenticity regression: `14 passed`
- ADR-087~096 bootstrap authority focused regression: `584 passed`
- Ruff check / Ruff format check / compileall / `git diff --check`: PASS
- UTF-8 / relative links / ADR consistency / secret·local-path scan: PASS
- Alembic: `20260918_0037` single head
