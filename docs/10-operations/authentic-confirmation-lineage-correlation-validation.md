# Authentic Confirmation–Lineage Correlation Foundation 검증

> 상태: Foundation Draft 검증
> 최종 수정일: 2026-09-20
> 계약: [ADR-097](../11-decisions/ADR-097-authentic-confirmation-lineage-correlation-foundation.md)

## 검증 범위

Deterministic disposable Ed25519 keys, 격리 SQLite journal과 Windows ACL/mutex fixture만 사용한다. ADR-096 opaque authenticity, ADR-091 held live lineage와 ADR-092 fresh observation을 shared confirmation/lineage/designation/material/authority handles, native lease와 서로 다른 caller/journal root transactions에 exact 결합한다.

Confirmation/action/lineage/source/material/signature/lease substitution, caller·journal transaction replacement, moving journal head, consumer failure와 stale handle reuse는 fail closed다. 실패는 correlation과 실제 parent attempt를 영구 abandon하고 foreign correlation handle은 valid attempt를 폐기하지 않는다. 결과는 CurrentnessWitness/admission/authorization이 아닌 opaque internal handle이다.

## 2026-09-20 검증 결과

- direct correlation regression: `14 passed`
- Bootstrap authority/Windows direct-impact regression: `598 passed`
- full backend 최종 수치는 PR exact-head `backend-ubuntu`에서 고정한다.
- Ruff check / Ruff format check / compileall / `git diff --check`: PASS
- UTF-8 / relative links / ADR consistency / secret·local-path scan: PASS
- schema/migration/Repository `commit()`·`rollback()` 추가: `0`
- production private key/credential/ceremony/port 접근: `0`
- Alembic expected head: `20260918_0037`, single head
