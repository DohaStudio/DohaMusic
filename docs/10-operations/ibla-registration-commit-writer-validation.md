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

## PR #203 exact-head CI 실패와 workflow 보정

기존 head bce3e6eb806d7039a2ee43fe15a08906a3d589b3의 [run 37192485441](https://github.com/DohaStudio/DohaMusic/actions/runs/37192485441)은 backend-ubuntu/frontend-playwright SUCCESS, ffmpeg-windows FAILURE였다. 첫 실제 실패는 Windows ceremony serialization, private facts and witness mechanics step의 Start-Process -Credential 호출이며 오류는 `This command cannot be run due to the error: The parameter is incorrect.`, step exit 1이다. native pytest child는 시작되지 않아 Writer assertion failure나 cascading test failure는 없다. 뒤 post-setup-python skip은 선행 step 실패의 결과다.

분류는 E(workflow configuration)이며 C(Windows credential 실행 제한)가 원인이다. 신규 Writer/failure 두 경로 추가 후 20개 test path와 options를 포함한 argument 1,017자 + CI Python executable 59자 = 전체 command 1,076자로, [CreateProcessWithLogonW의 1,024자 한도](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createprocesswithlogonw)를 넘었다. 기존 18개 목록의 command는 한도 이하였다. CI는 pytest 8.4.2를 설치했으며 [pytest 공식 @file 지원](https://docs.pytest.org/en/stable/how-to/usage.html#read-arguments-from-file)은 8.2부터 제공한다.

동일한 20개 경로를 disposable fixture root의 UTF-8(no BOM) argument file에 한 줄씩 쓰고 python -m pytest -q --basetemp 원 경로 @file로 전달한다. RID≥1000 non-admin account·native ACL·Start-Process credential/Profile/hidden·stdout/stderr·실패 exit 강제·timeout·required checks·pinned DohaVocal fixture는 유지한다. test 삭제/skip/xfail/continue-on-error·production SID 완화·dependency 변경 없음.

PowerShell AST parse와 동일 path/순서/실재 파일, 공백을 포함한 response-file 경로와 기존 native ASCII basetemp 경로의 실제 Start-Process 호출과 native suite를 로컬 검증한다. 로컬 새 계정/credential 실행은 하지 않으며 해당 보장은 새 exact-head hosted Windows CI가 담당한다. original/focused/v1/Source는 다시 실행한다. production/test Python source와 동작은 수정하지 않아 570-file manifest는 이전 head와 동일하다. 따라서 direct-impact/로컬 Full은 재실행하지 않으며 이전 1269/3074 PASS를 새 head 결과로 승계하지 않는다. 새 head에서는 기존 backend-ubuntu Full 및 Windows native required check를 실제 확인한다. 상세 새 HEAD/JUnit/time/exit/manifest 및 세 required check 결과는 PR 본문과 ignored .cache/ci-failure-203 evidence에 기록한다.

application DB/API/모델·Frontend 및 ADR 계약 변경 없음. Phase 9 0/18·0%, production unavailable, Draft 유지다. Ready/merge/auto-merge/branch 삭제는 수행하지 않는다.

로컬 harness의 최초 공백 basetemp 실행은 기존 native ASCII root 정책에서 거부됐다. 이 진단 결과를 별도 보존하고, production 정책·테스트를 변경하지 않은 채 basetemp를 원 지원 ASCII 경로로 고쳤다. response-file 경로의 공백 quoting 검증은 유지한다. 이 잘못된 fixture 실행을 Writer 회귀 PASS/FAIL 판정에 사용하지 않는다.

보정 작업의 로컬 재검증(실행 source HEAD bce3e6eb806d7039a2ee43fe15a08906a3d589b3 + workflow/docs-only 변경): native20파일 754 passed/failed0/errors0/skips0, 166.20s, exit0, parseable JUnit. original 2 / focused 84 / v1 106 / Source 103 passed, 각각 JUnit 2.748s/23.997s/9.171s/11.406s, 실패·오류·skip0, exit0, JUnit 존재/parseable, 전후 manifest 일치다. compileall/Ruff check·format570/diff/UTF-8/fences/relative links65/secret·generated·scope 감사 PASS, prototype21파일 그대로다. workflow ASCII CI command는 176자로 줄었다. app baseline은 Alembic0037 single head/metadata67/API114·110·89·110·duplicate0이며 변화0이다.
