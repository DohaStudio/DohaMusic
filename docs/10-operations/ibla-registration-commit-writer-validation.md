# IBLA Registration Commit Writer Foundation 검증

> 문서 상태: [완료 — 커밋 전 Foundation 검증]
> 최종 수정일: 2026-10-04
> 기준 develop: 1944b3654cff8f3fd30dea2f712afd1deb2a79dd
> 작업 브랜치: feat/ibla-registration-commit-writer-resume
> 관련 결정: [ADR-111](../11-decisions/ADR-111-ibla-registration-commit-authority-post-boundary-contract.md), [ADR-112](../11-decisions/ADR-112-ibla-registration-attempt-durable-boundary-restart-contract.md)

## 구현 범위

original provider의 minted-but-undelivered cap·fresh PRE source·R/Q/current delegation/exact Registry Custodian Writer를 검증하고, 별도 HKeeperOwner가 exact candidate를 실제 H root transaction에 PREPARED durable commit한다. 별도 whole H/L pass에서 저장된 candidate/fingerprint/head와 current source/native/proof/lease/위임을 재확인한 뒤 original final one-shot handoff한다. 고정 live callback만 별도 actual L root transaction에서 rev1/expected head/CAS/unique constraints를 검증·flush/commit한다. L REGISTRATION_COMMITTED durable commit이 POST이며 independent keeper가 actual committed whole L로 H CONFIRMED를 전진시킨다.

준비 시작+30초와 original cap deadline의 최소값을 적용하며 delivery에서 reset하지 않는다. preparation 재진입/외부 writer/foreign handle/thread/ended transaction은 거부한다. generic public L append와 H prepare는 registration candidate를 거부한다. private H 경로도 original provider 준비 frame와 exact H SessionTransaction을 검증한다. repository 신규 commit/rollback 0, 별도 owners만 commit하며 distributed atomic이라고 주장하지 않는다.

기존 R/Q original/native read·independent verifier pins·domain/scope/delegation 원본을 재사용하고 canonical sha256:<소문자 64hex> 및 ADR-111 wire/bounds/domain separation을 유지한다. 별도 bearer registry/persistent token/IA issuer를 만들지 않았다. v2 physical L/H identity/CHECK/registration partial unique index·strict dual reader와 원 v1 event/control prefix bytes를 지원한다. unknown/mixed unsupported schema는 fail closed, production offline migration/implicit rewrite/provisioning은 없다.

## Crash·reconciliation·역사적 실패

원 prototype은 delivered 후 H prepare 전 child process exit가 L/H delta 0인 상태에서 same R/Q logical operation의 fresh registration에 성공했다. 당시 원 test는 1 failed/0 errors/0 skips/1.547s/exit1였고 Full Backend는 중단되어 PASS가 아니었다. 원 branch의 미커밋 21개 파일 SHA-256과 failed JUnit을 그대로 보존했다. 기존 PASS를 재사용하지 않았다.

원 test 이름 test_unknown_restart_before_prepare_cannot_retry_original_operation을 유지했다. 같은 final-delivery 직후 crash를 이제 consumer 진입에서 os._exit로 재현하고 durable H PREPARED·L rev1·exact operation·POST false·new observation/cap/registration 거부·keeper fake confirm 거부를 검증한다. xfail/skip/조건부 우회/삭제 없음. 별도 pre-boundary child exit는 L/H bytes unchanged·no pending과 새 full verification/proof/lease/cap의 등록 성공을 검사한다.

prepare durable 전에는 fresh complete verification의 새 실행만 가능하다. prepare 이후 orphan/stale/deadline/lease/proof/wrong writer/candidate/UNCERTAIN은 pending을 retain하며 final delivery/L append/new cap/reset/cancel을 금지한다. after-L ambiguous/response loss는 stored exact operation facts를 read-only 대조하고 actual durable L가 있을 때만 H forward confirmation을 허용한다. old opaque handle resurrection/새 L append 없음.

## 검증 결과

| Gate | tests | passed | failures | errors | skips | JUnit seconds | exit | JUnit |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| original | 2 | 2 | 0 | 0 | 0 | 2.269 | 0 | parseable |
| focused | 84 | 84 | 0 | 0 | 0 | 21.237 | 0 | parseable |
| v1 | 106 | 106 | 0 | 0 | 0 | 9.443 | 0 | parseable |
| source | 103 | 103 | 0 | 0 | 0 | 11.321 | 0 | parseable |
| direct | 1269 | 1269 | 0 | 0 | 0 | 95.458 | 0 | parseable |
| full | 3086 | 3074 | 0 | 0 | 12 | 929.14 | 0 | parseable |

Full 전후 production/test Python source manifest는 570개, digest 7d2dba11c100a83893f85e5df24b306979888f64f01ad519d7c500e36646d58f다. 위 Gate의 실행 HEAD는 기준 develop 1944b3654cff8f3fd30dea2f712afd1deb2a79dd + 이 작업 브랜치의 미커밋 구현이며 exact dirty manifest로 구분한다. Git commit 이후 같은 소스의 대응과 최종 head Gate를 별도로 확인한다.

독립 clean pinned DohaVocal fixture e28320ef26a2dc49eaefdfa62bceea0c8c69e6ed, Python 3.12.5, Windows native ACL/identity + 실제 disposable SQLite/process-exit를 사용했다. Fake Runtime/ASGI·FFmpeg fixture만 허용하고 paid/production opt-in은 0이다. actual user voice/model/GPU는 실행하지 않았다. Full skip 12개는 opt-in GPU/benchmark 4개, 별도 유료 API 승인 없음 1개, Windows symlink 생성 권한 없음 7개다. focused/original/direct skip은 0이다. warnings 16,845개는 Python 3.12 SQLite datetime adapter deprecation 16,664개와 Starlette TestClient timeout deprecation 181개다.

## 정적·query·baseline

compileall, Ruff check/format(570 files), diff check, strict UTF-8/Markdown fences/relative links, sensitive·large/generated scan을 수행한다. L/H ordered history, operation/record lookup와 single-registration/head query plans를 검사하여 TEMP B-TREE가 없고 operation은 indexed SEARCH다. 전체 canonical/security history scan은 권한 검증에 필요한 고정 pass이며 per-event query/N+1나 관계 없는 scan을 추가하지 않았다.

App Alembic 20260918_0037 single head, metadata 67, routes 114/APIRoutes110/paths89/operations110/duplicate0을 안전한 in-memory app으로 확인한다. actual user DB/Artifact/production source/credential/private key 접근 0, app schema/migration/public endpoint/Frontend 변경 0이다. workflow 변경은 기존 Windows non-admin native suite에 writer/failure tests를 포함하는 한 줄이며 required check/fixture identity/gate 강도는 유지한다.

## 상태·범위 밖·다음 작업

Foundation 구현은 이 작업 브랜치의 테스트된 내부 mechanics다. develop 병합 상태와 production readiness를 혼동하지 않는다. actual production Source/Writer port는 unavailable다. IA issue/consume/cancel, INITIAL_SEALED, Provisioning/GENESIS, Recovery/Transfer/Auth/Activation, offline production migration/actual custody/ceremony/power-loss/controller/hardware anti-rollback/remote consensus는 미구현·미검증이다. H 마지막 PREPARED 및 consistent L/H rollback 탐지 기존 한계를 보존한다. Phase 9 0/18·0%와 체크리스트는 유지한다.

모든 새 Gate PASS 후 한국어 commit/push/develop 대상 Draft PR까지만 제출한다. Ready/merge/auto merge/branch 삭제는 이번 작업에서 수행하지 않는다. 다음은 Draft의 exact-head 최종 감사·별도 병합 작업이며 그 이후에만 POST-registration IA 계약을 감사한다.
