# Designation Provenance Reader Input Contract 검증

> 상태: [로컬 Gate PASS; docs-only Contract 제안, 운영 비활성]
> 작성일·최종 수정일: 2026-09-19
> 관련: [ADR-084](../11-decisions/ADR-084-designation-provenance-reader-input-contract.md)

## #169 Final Validation / merge

- START develop `fb10bc9367835b0d4a39837287a358fe6b46a1be`.
- H `130e189cf65d260b240d2a228c79e2c120c4b86a`, T `70eeb65de228558da862dabc96e35bc36c5c125f`.
- run `35364679577` exact H backend-ubuntu/ffmpeg-windows/frontend-playwright COMPLETED/SUCCESS, steps > 0. Windows native private facts/security mechanics step SUCCESS.
- local/remote/PR H/T exact, clean, OPEN/Draft/develop base/reviews·REQUEST_CHANGES·threads 0/MERGEABLE·CLEAN/Alembic single-head 0037 확인. Ready 직후 same H/T/develop/base/3 CI SUCCESS/reviews·CLEAN 확인 후 expected-head SQUASH MERGE.
- MERGED SHA/new BASE `688b5f77ad1fb17bb0356e884574171c73921c42`; merge tree = T. source H/main 보존. 추가 CI trigger/rebase/force-push/source 삭제 0.
- source와 native regression을 재감사했다. read-only fixed boundary/strict complete comparison/other OS fail closed/negative file checks/witness invalidation과 public fallback 0 확인. custody/provenance/fresh journal을 구현했다고 주장하지 않는다.

## 선택 / 문제와 해결

E: A 구현에 직접 필요한 designation/provisioning 입력·snapshot 계약 하나다. ADR-076은 unsigned 서면 self-designation·독립 human/fingerprint 대조를 허용한다. 현재 signature fixture는 approval/lifecycle integrity이지 외부 designation authenticity가 아니다. 이를 재사용하거나 새 governance signing root를 요구하는 추측 구현은 하지 않았다. source-level security bug를 새로 발견/수정했다고 주장하지 않는다.

future partial provenance observation과 currentness/admission witness를 분리하고 independent source·exact binding·eligibility·live-context composition·whole-attempt abandonment 및 후속 negative test Gate를 명시했다. 실제 reader/authority input 구현은 미구현이다. 실제 external ceremony 없이 Contract 검증과 다음 infrastructure 구현이 가능하므로 이번 작업의 external blocker는 아니다.

## 실행 Gate / evidence

- focused native Windows: 225 passed / 0 skipped / 0 failed, 5.17s.
- direct private facts/witness/Windows/journal/crypto/Auth/Rights/migration/Completion/Workspace: 617 passed / 0 skipped / 0 failed, 65.00s.
- full backend 기존 evidence `2129 passed / 12 skipped / 0 failed`는 #169 H/T의 결과다. 이번 변경의 backend/tests/source tree가 BASE와 완전히 동일함을 확인해 유지했다. 이번 작업에서 full을 재실행하지 않았다.
- Ruff check PASS, Ruff format check 483 files PASS, compileall/diff/UTF-8/fences/relative links/indexed ADR/secret·local-path/authority audit PASS. 문서 clause 검사는 semantic boundary consistency이지 실제 reader security proof가 아니다.
- Alembic `20260918_0037` single head. Repository commit()/rollback() 0과 facts/lifetime/serialization SQL/commit/rollback/flush 0 보존.
- 기존 Starlette deprecation warning과 알려진 frontend dependency advisory는 이 범위에서 수정/숨기지 않았다.

새 source/tests/ports/migration/production wiring 변경 0, Alembic 0037/external journal v1/Phase·DoD 보존. ADR-084의 후속 implementation acceptance는 계획이지 이번 새 reader 실행 결과가 아니다. 새 PR head/tree/CI registration은 PR 본문에 기록하고 OPEN/Draft만 생성한다.
