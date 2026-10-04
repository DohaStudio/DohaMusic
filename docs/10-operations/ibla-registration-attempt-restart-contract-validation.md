# IBLA Registration Attempt Restart Contract — Decision Validation

> 문서 상태: [완료 — docs-only 감사, Writer NOT IMPLEMENTED]
> 최종 수정일: 2026-10-04
> 기준 develop: 9ad483d0ae15ff6e185ef67c107d1a937066f222
> 기준 main: 63633d462043ad3ba78fee92473d19e90c361431
> Decision: [ADR-112](../11-decisions/ADR-112-ibla-registration-attempt-durable-boundary-restart-contract.md)
> 제출 범위: Draft PR까지. Ready/merge는 이번 작업에서 수행하지 않는다.

## Authority 재감사와 보존 evidence

ADR-107의 등록 이후 IA 목적, ADR-108의 pending/custody/retention, ADR-109의 실제 H prepare/confirm 및 L CAS/unique/flush-only, ADR-110 실제 provider mint/eligibility/handoff, ADR-111의 delivered-before-prepare와 unknown restart 제한을 대조했다. develop의 provider는 lock 아래 delivered를 먼저 기록하고 consumer를 호출한다. 기존 H는 full candidate와 CONFIRMED → PREPARED → actual L → CONFIRMED 전이를 구현한다. Source Verifier는 read-only Foundation이고 production unavailable다.

별도 feat/ibla-registration-commit-writer의 private Writer preflight/append, actual L/H transaction owners, source registry 변경, crash/reconciliation과 실패 test를 읽기 전용으로 감사했다. callback 안 H prepare 이전 process-local delivered 구간이 실제 존재한다. prototype은 authority나 production 구현 증거가 아니다.

실패 test는 backend/tests/test_ibla_registration_failure.py::test_unknown_restart_before_prepare_cannot_retry_original_operation이다. spawned child의 delivered-before-prepare stage에서 os._exit(0) 후 A/C/mapping/L/H bytes가 모두 같았고 새 process가 같은 R/Q/operation으로 fresh observation/proof/cap을 만들어 등록했다. 기대한 IblaDenied 대신 DID NOT RAISE였다. 보존 restart-blocker.xml은 tests 1 / failures 1 / errors 0 / skipped 0 / 1.547s, 당시 pytest exit 1이다. 이번 docs 작업에서 test를 재실행/수정하지 않았다.

기존 prototype focused 71 passed/direct-impact 1,256 passed는 누락 crash case 발견 전 결과다. Full Backend는 blocker로 중단됐고 pytest exit 4294967295/Gate exit 1, JUnit 없음이다. 이 결과를 새 docs head의 구현 PASS로 재사용하지 않는다. prototype의 21개 변경 파일과 실패 JUnit을 보존하여 SHA-256 비교로 변경 0을 확인한다.

## Decision과 exit audit

Option B: original cap/R/Q/exact Writer를 검증한 뒤 H PREPARED durable 예약, 그 뒤 original final one-shot handoff다. H는 cap/R/Q를 대체하지 않는다. boundary 전에는 trusted whole-history/currentness/PRE 검증의 새 observation이 가능하다. boundary 후 orphan/stale/expired/response loss는 pending 영구 보존과 새 cap/자동 L append/reset/cancel 금지다.

ADR-112 §8의 15개 답은 15/15 확정했고 IMPLEMENTATION_READY 범위는 Writer pre-PREPARED/restart/crash semantics뿐이다. A/B/C 비교·정확한 boundary·11행 restart matrix·logical identity·no resurrection/duplicate·실패 regression 보존은 ADR-112가 대표 설명이다. ADR-111의 해당 ordering/deadline/restart 문장만 명시적으로 부분 대체한다. ADR-107/110 목적과 ADR-109 상태 머신/rollback 한계는 보존한다.

## Docs Gate와 상태

필수 Gate는 diff check, strict UTF-8, Markdown fences, 상대 링크, ADR 번호/index, 현행 모순 검색, 민감/대용량/생성 파일 scan 및 non-doc delta 0이다. 실제 Gate는 PASS: 변경 Markdown 16개 strict UTF-8/fences, 상대 링크 629개, ADR 번호/index, 민감/대용량 후보 0, diff check와 non-doc delta 0, prototype 21개 SHA-256 unchanged를 확인했다. 현행 요약은 새 순서를 따르며 옛 순서 검색 결과는 명시된 역사 영역만 남긴다. 상세 실행 증거는 Draft PR 본문과 최종 보고에 기록한다. 실패하면 commit/push/PR을 진행하지 않는다. 기존 ADR-111 원문과 과거 검증 보고서/CHANGELOG의 ordering은 역사로 남기고 상단에 부분 대체 범위를 표시했다. ADR-110에도 Writer 통합 전용 보충 링크와 read-only 의미 보존을 명시했다. README/ROADMAP/Master/architecture/issuance/lifecycle/security/DB/DoD/index를 동기화했다.

안전한 in-memory app 측정: metadata 67, routes 114/APIRoutes 110, OpenAPI paths 89/operations 110/duplicate operation IDs 0. Alembic heads는 20260918_0037 단일 head다. 실제 user DB를 열거나 migration을 실행하지 않았다. API/schema 변경 0, Writer/v2 NOT IMPLEMENTED, Phase 9 0/18·0%다.

미수행: Writer 구현·test 변경·focused/direct/full Backend 재실행, runtime workflow 변경, 실제 source/custody/ceremony/power-loss, user DB/Artifact/production credential/private key 접근, IA/INITIAL_SEALED/Provisioning/GENESIS/Auth/Activation/Recovery/Transfer, Ready/merge/auto merge/branch 삭제. AI 실행/실험 보고서 대상이 아니다.

다음 정확한 작업은 Draft Decision의 별도 최종 감사·Ready/병합이다. develop authority가 된 후에만 보존 Writer prototype을 ADR-112 순서로 재감사·수정하고 pre-PREPARED regression을 유지/확대하며 focused/direct/full/source-manifest Gates를 새로 수행한다.
