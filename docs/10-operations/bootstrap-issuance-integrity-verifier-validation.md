# Bootstrap Issuance Integrity Verifier 검증

> 문서 상태: [로컬 검증 PASS — 별도 Foundation Draft PR, 운영 비활성]
> 최종 수정일: 2026-09-18
> 기준 develop: `771f3b18aabb7890b3a84698a6a830877cbdc0be`
> 관련 문서: [ADR-077](../11-decisions/ADR-077-bootstrap-issuance-integrity-verifier-foundation.md), [Architecture](../03-architecture/bootstrap-issuance-integrity-verifier.md)

## 시작·authority

#162 H `349dc1acee9a8d2a3ee2a769991d8b01a8e43f59`, T `a533e9b4cbb820dfa686997718370a6c70e83715`; run `35321729929`의 exact-head backend-ubuntu/ffmpeg-windows/frontend-playwright 모두 COMPLETED/SUCCESS. docs-only 11 files, ADR completeness/038·042·075 직접 충돌 0, UTF-8/links/ADR index/diff/security PASS, reviews/threads 0, MERGEABLE/CLEAN을 확인했다. Ready 후 head/tree/base/CI 재확인·새 required CI 없음·expected-head squash merge·source branch 보존. squash `771f3b18aabb7890b3a84698a6a830877cbdc0be`의 단일 parent는 시작 develop `6778ab22e69fbce54bc232815721b01413426dde`, merge tree는 T와 같다. main `63633d462043ad3ba78fee92473d19e90c361431` 무변경.

새 linked worktree/feat branch는 이 squash develop에서 시작했다. 기존 dirty user worktree와 보호 PR #161/#160/#159/#130은 변경하지 않는다. verifier 선택 이유·대안·명시적 미구현 경계는 ADR-077에 기록했다.

## 로컬 실행

기본 pytest Temp의 sandbox PermissionError를 재현했으며 fixture 실행 전 환경 문제였다. writable worktree-side basetemp에서도 기존 DB fixture I/O가 느려 해당 두 실행을 중단했고 그 결과를 PASS evidence로 쓰지 않았다. 동일 Completion 1개를 새 별도 Temp 경로에서 실행해 1 passed(0.40초)를 확인한 후 suite 전체를 전용 새 Temp fixture 경로에서 재실행했다. 테스트 skip/코드 우회는 없다. 실제 User/production DB·Provider·private signing store에는 접근하지 않는다. dependency는 격리 test path에 설치해 기존 venv를 변경하지 않았다.

- Focused: `test_bootstrap_approval_verifier.py` — **95 passed / 0 skipped / 0 failed**.
- Direct: focused + Local Operator Authentication/Workspace Bootstrap/Rights persistence·migration·ScopeGuard integrity/Vocal Completion/Workspace UoW/API surface — **311 passed / 0 skipped / 0 failed**, 59.00초. focused 95개를 포함한 수치다.
- Full backend: **1823 passed / 12 skipped / 0 failed**, 884.07초(14분 44초). 새 skip 추가 0, 기존 platform/opt-in skip 보존.
- compileall backend/ai_worker, Ruff lint, Ruff format(480 files), git diff --check: PASS. repository CRLF normalization을 끄면 전체 기존 파일을 오인하므로 저장소 원래 설정으로 diff-check를 수행했다. 소스 line ending 일괄 변경은 없다.
- strict UTF-8/replacement character/fence/conflict marker scan: changed 20 files PASS, relative links 449개 PASS, ADR 77개 중복 0/index PASS. added/new-file secret/local-path scan PASS; 최종 수치 기록 후 재확인.
- Alembic `-c backend/alembic.ini heads`: `20260918_0037`, single head. 기존 migrations/models/repositories/Auth/Workspace services/ADR-038/042/075 source 변경 0.
- library versions cryptography 50.0.1/rfc8785 0.1.4 확인. RFC8032 공개 verification vector, RFC8785 UTF-16 sort/number vectors·invalid Unicode 및 fixed domain/JCS signature negative tests PASS.
- production verifier private key generation/signing/file I/O/Session/commit()/rollback() 호출 0; runtime consumer 0. private key/credential leak/raw bootstrap secret persistence/authorization fallback 0. 테스트 disposable seed는 runtime memory에서 구성하고 private material을 파일·log·Git에 출력하지 않는다.
- 기존 Starlette/httpx deprecation warning은 보존했다. 새 unit에서는 새 실제 authentication, persistence/claim/journal/binding 또는 production 권한을 활성화하지 않는다.

## 보장하지 않는 항목

새 claim/migration/consume repository가 없으므로 새 claim replay/concurrency winner=1/transaction rollback·seal failure injection은 해당 없음이다. legacy migration/constraint/Rights rollback/Workspace UoW 회귀를 실행해 보존을 확인하되 이를 bootstrap 구현으로 주장하지 않는다. target principal/current-status/revoked/consumed deny·WebAuthn·journal/proof/anti-rollback·installation/binding persistence는 후속 Gate이며 crypto receipt는 permission이 아니다.
