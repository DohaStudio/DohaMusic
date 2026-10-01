# IBLA L/H Persistence Foundation 검증

> 상태: [검증됨 — 운영 비활성]
> 최종 수정일: 2026-10-02
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
- direct-impact regression: 976 passed, 0 skipped, 0 failed, pytest 57.33s, exit 0. Full Backend: 아래 final 실행으로 검증했다. 직접 영향 회귀 이후 변경은 새 IBLA audit-time codec/tests뿐이며 기존 dependency 코드는 변경하지 않았다. final Full Backend는 이 변경을 포함한다.
- Alembic heads: 20260918_0037 single head. app migration 0.
- 새 process의 abrupt exit 후 pending/committed/confirmed 재조회, complete history, exact replay/reconcile를 검증했다.
- deterministic Barrier/Event로 두 L writers, 두 H prepare, prepare/confirm 및 restart reconcile/new operation, replay/concurrent writer를 검증한다. sleep race 0.
- UPDATE/DELETE/REPLACE, event/envelope/digest/identity/epoch/version/continuity/head 및 H corruption, individual rollback/delete/recreate 거부를 검사한다.
- consistent full L/H rollback과 H-only last-PREPARED loss는 탐지 미보장을 확인하는 limitation 테스트다. 보안 탐지 PASS가 아니다.
- Query plan: head/revision/operation lookup indexed SEARCH; complete history는 revision ordered scan, temp B-tree 없음.

## 경계·후속

L/H public persistence mechanics만 구현했다. production entry는 unconditional unavailable이며 test fixture setup/transaction owners를 production에서 import하지 않는다. Source Verifier/First-Registration Capability/Initial Authorization/consumption/GENESIS/Provisioning/Auth/Activation/Recovery/Transfer는 구현하지 않는다. 기존 ADR-106 Factory에는 변경이 없다.

두 파일과 read-only reader만으로 독립 운영 custody·backup domain을 증명하지 않는다. native path/ACL/cleanup·writer separation·domain lease의 운영 adapter는 후속 Gate이고, 이 미구현 경계에서 production을 활성화하지 않는다. Phase 9 0/18 유지. AI 모델 실행/음성 데이터/실제 credential·production DB 접근 없음.

## Full Backend 최종 결과 authority

- Source HEAD: 366e4a8024ffff918338a6832b0a6f7d427cb7ba. 실행 전후 Python 553개 SHA-256 일치, source drift 0. 이후 변경은 검증 결과·PR 참조 문서뿐이다.
- 명령: python -m pytest -q --tb=short --junitxml=.cache/ibla-full-ssd.xml. 기본 OS 임시 디렉터리 사용.
- Native Windows, Python 3.12.5, 실제 FFmpeg; CI와 동일한 clean DohaVocal fixture e28320ef26a2dc49eaefdfa62bceea0c8c69e6ed를 DOHAVOCAL_E2E_SOURCE로 지정했다. 실제 production Provider나 음성 모델을 호출하지 않았다.
- process exit: 0. JUnit exists/parseable: YES. tests 2899, passed 2887, failures 0, errors 0, skipped 12, JUnit duration 892.455s (pytest 892.50s).
- 로컬 격리 worktree의 .cache/ibla-full-ssd.log, .cache/ibla-full-ssd.exit, .cache/ibla-full-ssd.xml, .cache/ibla-full-ssd-source-head.txt와 .cache/ibla-tested-python-manifest.json에 실행 증거를 보존한다. 바이너리 fixture는 커밋하지 않는다.
- skipped 12: GPU/benchmark opt-in 4, 유료 API opt-in 1, Windows symlink 생성 권한 제한 7. 이 항목의 실검증을 주장하지 않는다.
- 기존 suite DeprecationWarning 16845: Python 3.12 SQLite datetime adapter 16664, Starlette TestClient timeout 181. 이번 범위 밖이므로 수정하지 않았다.
- 최초 540feca 실행은 audit-time 누락 보완을 위해 중단했고, 두 번째 366e4a8 실행은 HDD 임시 DB로 인한 지연을 진단한 뒤 중단했다. 둘 다 exit -1/JUnit 없음이며 PASS 아님. 동일 range case는 기본 SSD 임시 경로에서 1 passed/1.95s였고, 세 번째 전체 실행의 위 결과만 Full Backend authority로 사용한다.

## 최종 정적·문서·범위 검증

Python compileall backend/ai_worker, Ruff check, Ruff format(553 files), git diff --check PASS. 변경 문서 15개의 strict UTF-8·fence 및 상대 파일 링크를 검사했다. CURRENT 문서/ADR index는 persistence implemented와 Source Verifier/운영 custody 미구현을 분리한다. 과거 ADR/validation의 당시 상태는 보존한다. relative file path만 검사했으며 외부 HTTP 응답과 모든 fragment anchor 전수 검증은 하지 않았다.

25개 변경 파일: production Python 6, tests/support 4, Markdown 15. config/dependency/workflow/public API/Frontend 및 app ORM/Alembic·기존 journal schema/Factory 변경 0. 최초 구현은 원격 검토를 위해 Draft PR로 제출했다.

## 최초 제출 이력

[PR #198](https://github.com/DohaStudio/DohaMusic/pull/198)은 최초 제출 당시 develop 대상 OPEN/Draft였다. Ready/merge/auto-merge/branch deletion/force push는 실행하지 않았다. 최종 원격 head의 CI 상태는 PR checks를 따르며 로컬 Full Backend PASS와 혼동하지 않는다.

## 최종 감사와 병합 Gate

2026-10-02 재확인 시 develop은 34c57b8, PR head는 680ac22로 유지됐고 해당 head의 backend-ubuntu/ffmpeg-windows/frontend-playwright는 모두 SUCCESS였다. 집중 테스트를 다시 실행해 106 passed, exit 0 및 JUnit을 확인했다. 최종 검토에서 현재 문서의 Draft 고정 표현을 PR 상태 참조로 정렬하며 코드·테스트·의존성·workflow를 변경하지 않는다. 이 문서 변경 후 새 exact head의 CI를 다시 확인한 뒤에만 Ready 및 expected-head guarded squash merge가 가능하다. 실제 최종 검토·병합 결과는 [PR #198](https://github.com/DohaStudio/DohaMusic/pull/198)을 따른다.
