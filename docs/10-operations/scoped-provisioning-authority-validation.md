# Scoped Provisioning Authority Verification Foundation 검증

> 상태: [검증 완료 — Foundation Draft 전용; 운영 비활성]
> 최종 수정일: 2026-09-19
> 구현 계약: [ADR-093](../11-decisions/ADR-093-scoped-provisioning-authority-verification-foundation.md)

## BASE·Decision·구현

#179를 exact-head required CI 3 SUCCESS와 same D/H/T/review/mergeability Gate에서 expected-head squash merge했다. START develop은 `0148d0491c5d947a88ebe353d0f4f37e30b9da60`, merge/new BASE는 `cfa1678519b6fba7ea2b0699f5bca518eae99bfb`, PR/source/develop tree는 `f1116ce101a3982220020b5fe681defe5638497a`로 일치한다.

사용자가 Product/Deployment governance Decision으로 ADR-076 root의 exact installation/producer/verifier에 `INSTALLATION_POLICY_PROVISIONING_ONLY` 목적을 부여하도록 승인했다. 새 root나 기존 deployment approval purpose 재사용이 아니다. A/B/C/D/E 재평가에서 독립 검증 가능한 A `Scoped Provisioning Authority Verification`을 선택했다.

`provisioning_authority.py`는 root-signed exact JCS event history의 AUTHORIZE/ROTATE/REVOKE, semantic revision/predecessor, terminal projection, key ID/fingerprint non-reuse와 고정 confirmation/lineage/policy domain을 검증한다. 결과는 non-capability public integrity receipt이며 complete/current source, Original Confirmation, live lineage, witness 또는 admission을 증명하지 않는다.

## Security·test evidence

Disposable in-memory Ed25519 fixture만 사용한다. Wrong purpose/domain/installation/producer/key/root, cross-domain replay, stale revision, fork/wrong predecessor, old-key reuse, revoke 후 재활성화, duplicate event, signature substitution, malformed/duplicate/nonfinite JSON, bool/int confusion, hostile string subclass, exception fallback과 parallel verification을 fail closed로 검증한다.

신규 negative suite `55 passed`, 관련 focused 9 files `545 passed`, Bootstrap authority direct 14 files `729 passed`, full backend `2457 passed / 12 skipped / 0 failed`다. 기존 Starlette/httpx deprecation warning 1개 외 새 warning은 없다. Sandbox의 global pytest temp ACL과 Windows named-pipe/fixture ACL 거부는 별도 disposable basetemp 및 권한 환경에서 동일 suite를 재실행해 모두 PASS했으며 test skip/완화는 0이다.

Ruff check/format 499 files, compileall, `git diff --check`, UTF-8 13 paths, relative links 2168개, ADR 93개 index/중복, secret/local-path/conflict-marker scan은 PASS다. Schema/migration/Repository/production port/실제 private key·credential·ceremony/User DB 접근은 0이고 Repository `commit()`/`rollback()` 추가 0, Alembic `20260918_0037` single head를 유지한다.
