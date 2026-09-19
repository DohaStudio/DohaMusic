# Authenticated Scoped Provisioning Authority Source Foundation 검증

> 상태: Foundation Draft 검증
> 최종 수정일: 2026-09-20
> 계약: [ADR-094](../11-decisions/ADR-094-authenticated-scoped-provisioning-authority-source-foundation.md)

## 범위

고정 private source의 exact physical identity/custody, bounded canonical codec, ADR-093 전체 history 검증, same-handle reread와 기존 pin/designation/lease/session 결합을 검증한다. disposable Ed25519 key와 격리된 임시 Windows ACL만 사용하며 production credential은 사용하지 않는다.

## 필수 negative evidence

- source replacement/rename/write/hardlink/reparse와 identity·ACL 변경은 fail closed
- wrong source/head/revision/authorization/root/scope/purpose/domain/signature는 fail closed
- truncated/forked/duplicate/revision-reset history와 revoked authority는 fail closed
- transaction·lease·parent handle 교체 및 stale handle 재사용은 fail closed
- malformed/duplicate/noncanonical JSON, UTF-8/base64, bool/float confusion과 oversize는 fail closed
- read/seek/close uncertainty는 allow로 전환되지 않고 기존 quarantine ownership을 유지

결과 객체는 provider 내부 opaque handle뿐이며 admission/currentness/confirmation API가 없다. app DB, Alembic, external journal schema, Repository commit/rollback과 production port 변경은 0이어야 한다.

## 로컬 결과

신규 direct suite는 `7 passed`, 기존 Bootstrap chain을 포함한 focused suite는 `560 passed`다. full backend는 Windows의 기존 장기 통합 fixture가 테스트당 30~60초로 지연되어 29%까지 failure 없이 진행한 뒤 로컬 실행을 중단했으며, Draft PR의 exact-head `backend-ubuntu`를 최종 full-suite Gate로 사용한다. 이는 full PASS 주장으로 계산하지 않는다.

Ruff check/format 512 files, compileall, diff check, 변경 9 files strict UTF-8, relative links 280개, 94 unique/indexed ADR, secret/local-path/conflict scan은 PASS다. Alembic은 `20260918_0037` single head다. 기존 Starlette/httpx deprecation warning 1개 외 새 warning은 없다.
