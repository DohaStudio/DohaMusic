# Custody Policy Provisioning / Initializer Provenance 계약 검증

## 범위와 authority

PR #173은 승인된 develop `702eab36ecd56eac8f47e6664d06e94dde64d6a5`, head `87f23f0b30b18aea0a6698511a6da0214b69bc3e`, tree `3eb5ef1b7f9a5002acdbce5d76cbe40b4a9ceff2`에서 Draft → Ready → expected-head guarded squash merge했다. Ready 전후 develop/head/tree, develop base, exact-head required CI, reviews/threads와 MERGEABLE/CLEAN을 재확인했다. 새 blocker와 develop race는 없었으며 Final Validation 파일 수정은 0이다.

Merge SHA와 후속 기준 develop은 `54773b3ed4d4bfcee8bcc81000a4e6517c2245c0`이다. PR tree와 merge tree는 위 tree와 동일하다. Source branch head는 보존했고 main과 보호 대상 PR은 변경하지 않았다.

후속 선택은 사전 허용된 E: 최소 선행 Contract Decision이다. [ADR-087](../11-decisions/ADR-087-custody-policy-provisioning-initializer-provenance-contract.md)은 실제 설치 행위, 명시적으로 위임된 initializer, exact policy snapshot/revision, 독립 확인 원본과 최신 lineage의 연결 계약을 제안한다. 새 trust root, mandatory signature, 생산 ceremony 또는 metadata/ACL을 provenance로 승격하는 구현은 추가하지 않는다. 실제 Provisioning / Initializer Provenance 검증은 **[미구현]**이며 source unavailable 경계와 Phase 6 진행률은 유지한다.

## 실행 및 유지 evidence

| 검증 | 결과 | 적용 범위 |
| --- | --- | --- |
| #173 exact-head Actions run `35395547983` | backend-ubuntu, ffmpeg-windows, frontend-playwright 모두 COMPLETED/SUCCESS | 승인된 exact head, 다른 SHA의 SUCCESS를 사용하지 않음 |
| 해당 backend CI full | 2211 passed / 8 skipped / 0 failed | merge된 기존 source의 full evidence |
| 해당 Windows native CI | 303 passed, FFmpeg integration 4 passed | merge된 기존 source의 Windows evidence |
| 후속 worktree focused 6 files | 303 passed / 0 failed, 8.01s | 기존 source regression 재실행 |
| 후속 worktree direct 16 files | 695 passed / 0 failed, 78.99s | Bootstrap/Rights/Completion/Workspace regression 재실행 |
| 이전 local full | 2207 passed / 12 skipped / 0 failed | 기존 검증 기록, 새 계약 기능 검증으로 주장하지 않음 |

후속 변경은 문서만이다. 기준 develop 대비 backend, ai_worker, tests, CI와 migration 변경이 없음을 diff로 확인하여 exact-source full CI evidence를 유지한다. 불필요한 full 재실행은 하지 않는다. ADR-087의 negative acceptance 표는 **향후 구현의 수용 조건**이며 이번 작업에서 실행된 새 provenance 기능 테스트가 아니다.

Focused/direct에는 Starlette/httpx deprecation warning이 각각 1개 있었다. 기존 full CI의 warning과 local/CI skip 차이는 기록을 유지하며 새 기능 검증 또는 warning-free 결과로 표현하지 않는다.

## 정적 검증과 운영 경계

검증 항목은 Ruff check/format, compileall, diff whitespace, strict UTF-8, conflict marker, 문서 상대 링크, ADR 번호 중복, 추가 텍스트의 secret/local-path 검사와 Alembic single head `20260918_0037`이다. backend/ai_worker/CI/migration/authority ports는 변경하지 않는다. 실제 키, 개인정보, credentials, consent 증적, user DB와 생성 음원은 사용하거나 저장하지 않는다.

새 PR은 develop 대상 **Draft까지만** 허용한다. Ready/merge, source branch 삭제, force-push/history rewrite와 보호 PR 변경은 하지 않는다. 다음 구현은 ADR-087 검토 후 독립 확인 원본과 exact policy action/lineage를 disposable fixture로 비교하는 최소 기반부터 별도 승인 범위에서 진행한다.
