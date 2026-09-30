# IBLA L/H Persistence Foundation 검증

> 상태: [진행 중 — focused/static 통과, 회귀·Full Backend 확인 중]
> 최종 수정일: 2026-10-01
> 관련 결정: [ADR-109](../11-decisions/ADR-109-ibla-ledger-independent-checkpoint-persistence-foundation.md), [ADR-108](../11-decisions/ADR-108-ibla-anchor-coverage-ledger-checkpoint-contract.md)

## 시작 authority 및 보존

- START develop: 34c57b8ce52e623d6da85163e34d13104207b485, tree 488455b320d79af59fd1343fad55b2ca9af7a80e. #197 MERGED 확인.
- main: 63633d462043ad3ba78fee92473d19e90c361431.
- Open PR #171/#130은 모두 Draft/develop이며 변경하지 않는다.
- 최신 ADR 108, app Alembic 20260918_0037. feat/ibla-ledger-checkpoint-persistence를 latest develop에서 격리 생성했다.
- 원래 workspace의 frontend/next-env.d.ts 수정·다수 untracked, stash 6개·다른 worktree를 보존한다. test는 disposable stores만 사용한다.

## 기존 authority/source 대조

ADR-076/078의 외부 root·GENESIS 독립 evidence, ADR-079의 immutable journal SQL CAS를 보존한다. ADR-081 lifetime, 082 ceremony, 083~089 raw fact/custody/initializer binding의 mechanics와 provenance 차이, 090~094 purpose별 JCS/signature/held source, 097/098 exact correlation/witness lifetime, 099 GENESIS deny, 100 transaction ownership, 101 read-only reconciliation, 102~105 unavailable composition·routing/descriptor, 106 existing-only Factory, 107/108 independent lineage·H·consume-before-GENESIS를 대조했다.

실제 재사용은 shared scalar validators와 bounded JSON/JCS/SHA-256이다. 기존 journal은 다른 purpose이므로 schema나 repository를 IBLA라고 재해석하지 않는다. repository가 commit/rollback하지 않는 discipline와 event+projection trigger CAS pattern을 적용했다. Windows 운영 open/provisioning·human/custody authenticity는 이번 구현에서 새로 만들지 않았다.

## 실행 검증

- focused: 106 passed, 0 skipped, 0 failed, pytest 8.45s. L/H recorded_at의 strict UTC-second·persisted digest·비권한 경계까지 검증.
- compileall backend/ai_worker, Ruff check 및 format 전체 PASS.
- direct-impact regression: 976 passed, 0 skipped, 0 failed, pytest 57.33s, exit 0. 최초 Full Backend(540feca)는 audit time 보완을 위해 의도적으로 중단했다(exit -1, JUnit 없음, PASS 아님). 보완한 source commit에서 Full Backend를 새로 실행하며 결과 없는 PASS를 기록하지 않는다.
- Alembic heads: 20260918_0037 single head. app migration 0.
- 새 process의 abrupt exit 후 pending/committed/confirmed 재조회, complete history, exact replay/reconcile를 검증했다.
- deterministic Barrier/Event로 두 L writers, 두 H prepare, prepare/confirm 및 restart reconcile/new operation, replay/concurrent writer를 검증한다. sleep race 0.
- UPDATE/DELETE/REPLACE, event/envelope/digest/identity/epoch/version/continuity/head 및 H corruption, individual rollback/delete/recreate 거부를 검사한다.
- consistent full L/H rollback과 H-only last-PREPARED loss는 탐지 미보장을 확인하는 limitation 테스트다. 보안 탐지 PASS가 아니다.
- Query plan: head/revision/operation lookup indexed SEARCH; complete history는 revision ordered scan, temp B-tree 없음.

## 경계·후속

L/H public persistence mechanics만 구현했다. production entry는 unconditional unavailable이며 test fixture setup/transaction owners를 production에서 import하지 않는다. Source Verifier/First-Registration Capability/Initial Authorization/consumption/GENESIS/Provisioning/Auth/Activation/Recovery/Transfer는 구현하지 않는다. 기존 ADR-106 Factory에는 변경이 없다.

두 파일과 read-only reader만으로 독립 운영 custody·backup domain을 증명하지 않는다. native path/ACL/cleanup·writer separation·domain lease의 운영 adapter는 후속 Gate이고, 이 미구현 경계에서 production을 활성화하지 않는다. Phase 9 0/18 유지. AI 모델 실행/음성 데이터/실제 credential·production DB 접근 없음.
