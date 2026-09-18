# Private Admission / Currentness Contract 검증

> 상태: [Contract 검증 — 새 구현/운영 비활성]
> 최종 수정일: 2026-09-18
> 기준 develop: `98d8f07163bfc6bd9dc15c5fc7e41c0b906b01c9`
> 관련 문서: [ADR-080](../11-decisions/ADR-080-private-admission-currentness-handoff-contract.md), [기존 Journal evidence](deployment-lifecycle-journal-validation.md)

## #165 Final Validation / Merge

START develop `61b91d1bfaaceca6e3befda9c09f2ad91341a4c2`, H `5f7990c8ace20d4a78e4a3af17da9c5dd147dbe9`, T `66b9a9e859fc59d14b880b76cdb86c074c64e7e1`을 remote에서 재측정했다. OPEN/Draft/develop base/local-remote-PR H/T equality/clean, MERGEABLE/CLEAN, reviews/REQUEST_CHANGES/unresolved threads 0을 확인했다.

Exact-head run `35337291751`: backend-ubuntu/ffmpeg-windows/frontend-playwright 모두 COMPLETED/SUCCESS, steps > 0. Ready 뒤 동일 H/T/develop/base/CI/reviews/threads를 재확인하고 expected-head squash merge했다. merge/new develop `98d8f07163bfc6bd9dc15c5fc7e41c0b906b01c9`, single parent=START develop, merge tree=T, source branch=H 보존이다.

ADR-078과 source/test를 대조해 strict event verification, actual conditional guard UPDATE, monotonic revision, stale CAS/REPLACE/UPSERT/terminal non-reuse, ordering/pin mismatch, rollback/restart, thread/process winner 1, event ID NOT NULL, public/private separation과 unconditional unavailable을 확인했다. 기존 exact-source focused 81/direct 392/full backend 1904 passed·12 skipped·0 failed, exact-head CI backend 1908 passed·8 skipped evidence를 유지한다. 이번 docs-only 작업의 새 실행 수치로 보고하지 않는다.

## 선택과 contradiction repair

선택은 D: A를 위한 최소 private witness/lease/durable commit handoff Contract다. `currentness_ports.py`의 object skeleton와 private DeploymentJournalReader 부재, public repository/receipt의 caller-constructibility가 근거다. A/B/C를 동시에 구현하거나 새로운 root/credential 규칙을 발명하지 않는다. ADR-080은 method responsibility/handle lifetime/commit ownership/negative rollout Gate를 정의하되 Python API나 production provider 구현은 아니다.

현재 merged 상태와 README/ROADMAP/MASTER/architecture의 '#165 별도 Draft' 및 README의 '#164 Contract 별도 Draft/journal 미구현' 문구가 불일치했다. 최소 최신-status 문구와 ADR-079 header만 정합화하고 authoritative ADR-075/076/077/078 의미·원본, 기존 tests/source/migrations/DoD는 보존한다. 과거 validation/CHANGELOG의 당시 Draft 기록은 역사로 남긴다.

## 검증 경계와 warnings

새 source/schema/test/frontend 변경 0이므로 direct/full suite는 불필요하게 반복하지 않는다. 이번 실제 merged journal focused 재확인은 **81 passed / 0 skipped / 0 failed**, 1.75초, 기존 Starlette deprecation warning 1개다. 기존 direct 392/full backend 1904 passed·12 skipped evidence는 source 동일성 근거로 유지하며 이번 재실행 수치가 아니다. Frontend/E2E 새 실행은 영향 0으로 생략한다.

compileall backend/ai_worker, Ruff check/format(485 files), git diff --check PASS다. strict UTF-8/fences/conflict/added-lines secret-local-path scan, changed Markdown **433 relative links**, **80 unique indexed ADRs** PASS다. app Alembic **20260918_0037 single head**, external schema v1·Repository commit()/rollback() 0·production unavailable source 및 기존 migrations/ADR-077 원본/DoD 무변경을 확인했다. ADR-080의 공격적 negatives는 후속 A implementation 계획이며 새 테스트 PASS로 주장하지 않는다.

기존 lockfile audit advisory 6개(2 moderate/3 high/1 critical), backend CI Python 3.12 deprecation warnings 16666개는 별도 maintenance warning이다. 이번 secret/authority-boundary 검증 PASS는 전체 dependency security audit PASS가 아니다. dependency upgrade/audit fix, 실제 User/production DB/Provider/key/governance/credential 접근·생성은 0이다. hardware anti-rollback/full privileged clone 방어를 주장하지 않는다.
