# Provider Witness Lifetime Foundation 검증

> 상태: [최종 로컬 Gate PASS — infrastructure helper Draft, 운영 비활성]
> 최종 수정일: 2026-09-18
> 기준 develop: `e45525e0c87656c8b5b6efc8986e5d2c925b48c6`
> 관련 문서: [ADR-081](../11-decisions/ADR-081-provider-witness-lifetime-foundation.md), [ADR-080](../11-decisions/ADR-080-private-admission-currentness-handoff-contract.md)

## #166 Final Validation·merge

START develop `98d8f07163bfc6bd9dc15c5fc7e41c0b906b01c9`, H `4a334ff262ea15c5d7d6f276a36597b65fea1abc`, T `c00e9f82309954c256b0f7bc009dd34c096f7da5`를 remote에서 재확인했다. OPEN/Draft/develop base/local-remote-PR equality/clean, docs-only 9 files +122/-9, reviews/REQUEST_CHANGES/unresolved threads 0, MERGEABLE/CLEAN을 확인했다. ADR-080의 public/private 구분·witness/lease 책임·caller transaction/explicit external owner·durable commit·pin reconciliation·mismatch fail closed를 ADR-076/077/078과 대조해 직접 충돌 0을 확인했다.

run `35340296273` exact H의 required backend-ubuntu/ffmpeg-windows/frontend-playwright 모두 COMPLETED/SUCCESS다. backend 실제 로그는 1908 passed/8 skipped/16666 warnings, 880.04초다. Ready 뒤 same H/T/develop/base/CI/reviews/threads를 확인하고 expected-head squash merge했다. merge/new develop `e45525e0c87656c8b5b6efc8986e5d2c925b48c6`, single parent=START develop, merge tree=T, source H 보존이다. ADR-080은 새 develop에 포함된 authoritative handoff Contract다.

## 선택·재현·자체 수정

선택은 A의 더 작은 직접 선행 implementation: provider-internal opaque witness lifetime mechanics다. public strict binding/registry identity/single assignment/lease release/SessionTransaction end와 drift rejection을 구현하되 actual trusted reader/admission/OS ceremony/durable owner/pin installer를 공개·활성화하지 않는다. helper 통과는 authorization이 아니며 기존 concrete production composition은 unavailable다.

초기 focused 67 passed 뒤 공격적 테스트에서 observed HEAD drift 거부 후 old matching projection 재제출, nested transaction 거부 후 savepoint 종료가 같은 handle을 재활성화했다. regression으로 **2 failed**를 직접 재현했다. 원인은 denial에서 registry record를 남긴 것이며 revalidation failure가 attempt 전체를 영구 폐기하도록 수정했다. 이어 registration 전 nested transaction failure도 같은 원인으로 **1 failed**를 재현하고 해당 path도 폐기하도록 수정했다. duplicate registration loser가 성공한 winner를 지우지 않는 것은 유지한다. authority/assert/skip/Gate를 완화하지 않았다.

pin-only counter의 bool/float 우회도 **4 failed**로 재현했다. journal counter만 strict 검사하고 pin을 dataclass equality로 비교해 Python `True == 1`, `1.0 == 1`이 통과한 것이 원인이다. 양쪽 projection의 revision/trust revision을 각각 strict 검사하도록 수정했다. caller scope의 custom `__eq__`가 다른 UUID를 같다고 응답하는 우회는 **1 failed**로 재현했다. incoming scope 및 모든 comparison fields를 canonical native primitive로 검증한 뒤 비교하며 string subclass spoofing도 거부한다. 이 문제들은 이번 helper 구현의 invariant bug이며 production authority bypass가 실제 발생했다는 주장은 아니다.

수정 전 source로 시작한 full runs는 exact final-source evidence에서 제외하고 task-only process/PID와 isolated fixture command line을 확인한 뒤 종료했다. 최종 source로 신규 격리 경로에서 direct/full 검증을 다시 실행한다. unrelated Python processes/User DB에는 접근하지 않는다.

## 실제 로컬 evidence

- focused 최종 **82 passed / 0 skipped / 0 failed**, 0.29초. 기존 Starlette deprecation warning 1개. 중간 focused 75/79는 최종 판정에 사용하지 않는다.
- 최종 direct(lifetime/lifecycle/crypto/Auth/Rights/Completion/Workspace/migrations/UoW): **474 passed / 0 skipped / 0 failed**, 64.37초. focused 82/UoW14 포함. 이전 source의 453+UoW14/471 evidence는 최종 판정에 사용하지 않는다.
- Workspace UoW 최초 default AppData Temp의 sandbox PermissionError로 setup 14 errors였고 source 변경 없이 신규 격리 temp 경로에서 동일 **14 passed / 0 skipped / 0 failed**, 3.00초였다. 최종 direct에는 해당 14개를 함께 포함한다.
- 최종 full backend: **1986 passed / 12 skipped / 0 failed**, 943.37초. collection 1998과 일치하며 기존 Starlette warning 1개다. 수정 전 중단한 full runs는 판정 evidence가 아니다.
- 새 thread bookkeeping registration winner 1/denied 1, old handle/lease replay·provider restart·transaction end/rollback·partial flush abandonment PASS. 이것은 cross-process OS ceremony/admission의 증거가 아니다.
- 기존 lifecycle direct 회귀에서 default SQLite REPLACE/UPSERT/reset/NULL identity/terminal reuse/stale CAS/history truncation/pin mismatch/thread-process rotation/revoke winner 1·rollback/crash 검증 유지.
- actual private admission/concurrent admit/durable owner→pin crash Gate는 아직 미구현이며 helper/기존 public facts 테스트로 PASS 표시하지 않는다.

새 app/external schema 변경 0, Repository commit()/rollback() 0, ADR-077 source/원본과 기존 migrations/DoD 불변을 확인한다. raw private key/raw bootstrap secret/credential/real User DB/production DB/Provider/governance/OS ceremony 생성·접근 0이다. 테스트 object lease는 actual OS lease가 아니다. Frontend 영향 0으로 추가 local build/E2E 불필요다.

compileall backend/ai_worker, Ruff check/format **487 files**, git diff --check PASS다. strict UTF-8/fences/conflict/secret-local-path scan, changed Markdown **434 relative links**, **81 unique indexed ADRs** PASS다. helper AST의 SQL/flush/commit/rollback call count 각각 0이다. production source에서 helper consumer는 없고 test에서만 import한다. app Alembic **20260918_0037 single head**, external journal v1 불변이다. ADR-080은 merged 상태·다음 link header만 정합화하며 본문 semantics는 바꾸지 않는다.

기존 dependency advisory 6개(2 moderate/3 high/1 critical) 및 backend CI deprecation warnings는 별도 maintenance warning이다. source secret/authority boundary scan PASS를 전체 dependency security audit PASS로 확대하지 않는다. complete journal/private-key privileged clone/rollback 방어를 제공하지 않는다.
