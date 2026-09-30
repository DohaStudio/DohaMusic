# DohaVocal 0.2.0 Consumer E2E — PR #194 이후 최종 재검증

> 날짜: 2026-09-30
> 상태: commit 직전 새-base 로컬 검증 완료 snapshot. 이후 PR·CI·Ready·merge authority는 해당 PR 본문과 GitHub 이력을 따른다. 과거 blocked 기록은 아래에 원문으로 보존한다.
> 이 절의 로컬 결과와 하단 historical 결과는 서로 다른 실행이다.

## 새 원격 authority와 원본 보존

- START develop / PR #194 merge: `83d63f8908a4efb35a62aba95824fca87879f860`.
- START tree / PR #194 tree: `0b5f7765e3f833f33b9077b226034d576d33e804`.
- parent / 이전 E2E base: `6717bcd6c6d2bc296c6a374a189669cfbabfa991`.
- main: `63633d462043ad3ba78fee92473d19e90c361431`.
- DohaVocal authority: `e28320ef26a2dc49eaefdfa62bceea0c8c69e6ed`, tree `f5dc77e8db0d2d2caa051021662b94e7b969d223`; remote 동일, pinned checkout tracked clean.
- PR #194 MERGED, 병합 후 push CI SUCCESS 재확인. required checks는 backend-ubuntu / ffmpeg-windows / frontend-playwright다.
- 원본 `feature/dohavocal-020-consumer-e2e-revalidation`: HEAD `6717bcd6...`, staged 0 / tracked modified 31 / untracked 8. 39파일 경로·SHA-256이 storage 수정 전 스냅샷과 모두 일치했다.
- 원본 worktree는 변경하지 않고 status/staged/unstaged/untracked/stat/full binary diff와 39파일을 별도 evidence에 복사·해시 검증했다. 새 clean worktree의 `feature/dohavocal-020-consumer-e2e-final`은 START exact SHA에서 시작했다.

## Base 비교와 semantic reapplication

이전 base부터 START까지 1 commit / 6 files / +384/-5이며 PR #194 외 변경은 0이다. exact overlap은 workflow와 CHANGELOG 2개다. Ubuntu Provider fixture checkout/install/ASGI env와 Windows storage CI step을 모두 유지하고 CHANGELOG 두 항목을 함께 보존했다. resolver·storage regression·storage contract·storage validation report 4개는 START와 동일하다.

E2E reconciliation·Completion이 기존 Storage를 사용하므로 semantic overlap은 회귀 검증 대상으로 처리했다. Music Director·journal·repository transaction·schema 수정은 추가하지 않았다. file-by-file 판정은 다음과 같다. absorbed/obsolete는 0이며 오래된 차단 표현만 현재 authority와 historical 기록으로 분리한다.

| 파일 | 판정 | 겹침/처리 |
|---|---|---|
| `.github/workflows/voice-ffmpeg-integration.yml` | adaptation required | exact; independent Ubuntu fixture and Windows storage steps retained |
| `CHANGELOG.md` | adaptation required | exact; retain PR194 entry and add E2E entry |
| `MASTER_ROADMAP.md` | still required | no overlap |
| `README.md` | still required | no overlap |
| `ROADMAP.md` | still required | no overlap |
| `backend/app/factory.py` | still required | no exact overlap; storage consumers require regression |
| `backend/providers/vocal/acquisition.py` | still required | no exact overlap; storage consumers require regression |
| `backend/providers/vocal/client.py` | still required | no exact overlap; storage consumers require regression |
| `backend/providers/vocal/http_transport.py` | still required | no exact overlap; storage consumers require regression |
| `backend/providers/vocal/mapping.py` | still required | no exact overlap; storage consumers require regression |
| `backend/providers/vocal/transport.py` | still required | no exact overlap; storage consumers require regression |
| `backend/services/workspace/__init__.py` | still required | no exact overlap; storage consumers require regression |
| `backend/services/workspace/provider_result_ingestion_service.py` | still required | no exact overlap; storage consumers require regression |
| `backend/services/workspace/vocal_payload_reconciliation_service.py` | still required | no exact overlap; storage consumers require regression |
| `backend/tests/support/vocal_e2e.py` | still required | no exact overlap; storage consumers require regression |
| `backend/tests/support/vocal_runtime.py` | still required | no exact overlap; storage consumers require regression |
| `backend/tests/test_dohavocal_runtime_e2e.py` | still required | no exact overlap; storage consumers require regression |
| `backend/tests/test_dohavocal_stream_guards.py` | still required | no exact overlap; storage consumers require regression |
| `backend/tests/test_vocal_payload_reconciliation.py` | still required | no exact overlap; storage consumers require regression |
| `docs/03-architecture/dohavocal-consumer-contract.md` | still required | no overlap |
| `docs/03-architecture/dohavocal-payload-acquisition-orchestration.md` | adaptation required | new START authority and PR130 disposition; old BLOCKED status removed |
| `docs/03-architecture/dohavocal-verified-staged-artifact-completion.md` | still required | no overlap |
| `docs/03-architecture/dohavocal-worker-reconciliation-contract.md` | still required | no overlap |
| `docs/03-architecture/durable-execution-handoff-analysis.md` | still required | no overlap |
| `docs/03-architecture/durable-payload-locator-authority.md` | still required | no overlap |
| `docs/03-architecture/repository-provider-boundaries.md` | still required | no overlap |
| `docs/03-architecture/verified-durable-staging-authority.md` | still required | no overlap |
| `docs/03-architecture/workspace-worker-reentry-lifecycle.md` | still required | no overlap |
| `docs/06-api/provider-api-contract.md` | still required | no overlap |
| `docs/09-security/security-policy.md` | still required | no overlap |
| `docs/10-operations/artifact-storage-ingestion.md` | still required | no overlap |
| `docs/10-operations/dohavocal-020-consumer-e2e-validation.md` | adaptation required | historical blocked report retained; new authority section needed |
| `docs/10-operations/workspace-job-worker.md` | adaptation required | clarify production Worker wiring remains unimplemented |
| `docs/11-decisions/ADR-048-dohavocal-payload-acquisition-consumer.md` | still required | no overlap |
| `docs/11-decisions/ADR-051-verified-durable-staging-authority.md` | still required | no overlap |
| `docs/11-decisions/ADR-074-dohavocal-verified-staged-artifact-completion-authority.md` | still required | no overlap |
| `docs/11-decisions/README.md` | still required | no overlap |
| `docs/DOCUMENT_AUTHORITY_MAP.md` | still required | no overlap |
| `docs/DoD/Provider-Separation.md` | still required | no overlap |

## 계약과 Completion 범위

판정: **COMPLETION_E2E_IN_SCOPE**. actual pinned DohaVocal FastAPI app → Music HTTP transport → trust → ProviderJobBinding/ordered PayloadLocator → actual byte verification → durable staging → 기존 Completion을 사용한다. test-only Fake rights와 disposable SQLite만 허용하며 production 인증/권한 fallback은 없다.

0.1.0 default/metadata-only와 explicit 0.2.0 capabilities·CreateJob·Manifest·Result를 분리한다. primary roles는 generation=`generated_vocal_candidate`, conversion=`converted_vocal_candidate`, correction=`corrected_vocal_candidate`, analysis=`vocal_analysis_result`다. byte SHA-256/size/Content-Type을 검증하고 staging에서 실제 WAV/JSON 형식을 다시 검증한다. arbitrary URL/host/query와 redirect를 거부하며 binary는 JSON/base64 wrapper를 사용하지 않는다. read chunk는 64 KiB이고 payload 최대 크기로 bounded buffering한다. end-to-end zero-copy streaming이라고 주장하지 않는다.

interruption/cancel/revocation/rights loss/expected-fact mismatch는 verified 상태 전이 전에 차단한다. 명시적 same-source retry와 verified reopen/replay를 확인하며 자동 retry는 없다. final Completion CAS 실패 시 output/Job mutation이 rollback되는 기존 transaction을 사용한다. Repository direct commit/rollback 신규 추가 0, production writer/worker/daemon/schema 확장 0이다.

PR #130 판정: **SUPERSEDED_BY_CURRENT_DEVELOP_E2E**. OPEN Draft/head `764e718a7d4f420e416c9f36a2cac814e5b5e528` 유지, 현재 START와 62/5 commits divergence. 역사적 service/test 아이디어를 재사용하되 직접 merge/close하지 않는다.

## 새 실행 결과

- focused: **166 passed**, 181 warnings, 15.67s, exit 0. actual Provider ASGI 26 cases 포함, skip 0.
- pre-full original storage stress: **100/100**, failure 0.
- PR #194 native deterministic tests: 두 test 각각 10회, **20/20**.
- direct regression: **398 passed / 4 skipped**, 56.92s, exit 0. 기존 10 modules에 storage/관련 Music Director 5 modules를 더했다. JUnit tests=402 / failure=0 / error=0.
- 단일 authoritative full: **2781 passed / 12 skipped**, 16845 warnings, 938.03s, exit 0. JUnit tests=2793 / failures=0 / errors=0. 12 skips는 model/GPU/paid external opt-in 5개와 native Windows symlink 권한 7개.
- same-process post-full storage stress: **100/100**, failure 0. `pytest.main` full 종료 후 같은 Python process에서 원래 test body/assertions를 실행했고 최종 runner exit도 0.
- source authority: first-party Python **543파일 SHA-256 동일**, direct JUnit hash 동일. full 실행 후 code/test 수정 0.
- static/docs/security: compileall PASS / Ruff lint PASS / Ruff format 543 files PASS / diff check PASS. 변경 39파일 UTF-8·link·fence·secret/private-path/large/audio/model/checkpoint scan PASS. ADR 106개, 번호 중복/index 누락 0. 요청 키워드로 current authority를 대조한 잔여 모순 0; historical 상태는 별도 유지.
- API/schema: 전후 실제 측정 모두 routes 114 / API routes 110 / paths 89 / operations 110 / duplicate IDs 0; Alembic `20260918_0037`, metadata 67. 신규 public operation/migration 0.

## 문서·범위·남은 Gate

기존 blocked history와 수치는 아래 그대로 보존했다. PR #194 storage 문서를 수정하지 않는다. README/ROADMAP/MASTER/DoD의 Fake integration 증거와 production 완료 조건을 구분하며 Phase 완료 체크·진행률을 올리지 않는다. ADR-048/051/074 결정 의미는 그대로이고 implementation note만 정합화한다.

commit/push/Draft/CI/Ready/merge는 이 commit 직전 snapshot에서 NOT RUN이다. 이 표현은 이후 원격 상태를 뜻하지 않는다. 로컬 BLOCKER는 0이다. exact head·same base·required CI·reviews·threads Gate와 expected-head squash·tree equality는 별도 확인한다. 기록된 최종 로컬 snapshot 이후 원격 lifecycle authority는 새 PR 본문과 GitHub 이력을 따른다.

전체 suite의 기존 journal fixture가 남긴 synthetic SQLite 1개는 경로와 SHA-256을 확인해 repository 밖 evidence로 보존했다. fixture 구현은 수정하지 않고 commit 대상에서 제외했다.

WARNING: Fake Provider process-local·restart durability/Production Provider persistence/authentication/rights writer 없음; real AI inference/user audio/GPU/voice quality/performance와 실제 외부 network E2E는 미수행. 다음 권장 작업은 **A. Production Provider Result/source persistence** 하나이며 이번 scope에서 시작하지 않는다.

## 이전 base 6717의 blocked/revalidated history — 원문 보존

아래는 PR #194 이전 실행이다. 해당 절의 “현재”, “최종”, BLOCKED와 NOT RUN은 당시 상태이며 위 새 authority의 결과가 아니다.

# DohaVocal 0.2.0 Consumer E2E 복구·재검증 보고서

> 최종 수정일: 2026-09-30
> 현재 판정: **BLOCKED — PREEXISTING_FLAKY_CONCURRENCY**
> 기존 변경은 보존했고 새 develop 기반 별도 branch에 복구했다. commit/push/PR/Ready/merge는 NOT RUN이다.

## 새 기준선과 보존

- OLD_BASE: `cda9fa8bd1974d20d431b5efdc80ec024bfd3a21`, tree `f84130a5db5a93a16f8e69f857c23d1c84c2516a`.
- NEW_DEVELOP: `6717bcd6c6d2bc296c6a374a189669cfbabfa991`, tree `ec3b8dd99fbc6285d2d41042eb4eb5ecb326c045`.
- main: `63633d462043ad3ba78fee92473d19e90c361431`.
- Vocal authority: `e28320ef26a2dc49eaefdfa62bceea0c8c69e6ed`, tree `f5dc77e8db0d2d2caa051021662b94e7b969d223`.
- 새 branch: `feature/dohavocal-020-consumer-e2e-revalidation`. 기존 foundation branch와 원본 worktree는 유지했다.
- 먼저 old worktree root/branch/HEAD/status/staged/unstaged/untracked/ignored/stat/full binary tracked diff를 스냅샷에 기록했다. staged 0, tracked 수정 27, untracked E2E 파일 8이다.
- 변경 35개 파일을 별도 복사하고 파일별 SHA-256을 검증했다. ignored 항목은 pytest/Ruff/Python cache이며 원본을 삭제하지 않았다. 사용자 파일 보존용 commit·stash·reset·restore·rebase는 수행하지 않았다.
- 증거 묶음 식별자: `.codex-e2e-recovery-snapshot-20260930-035300`. 로컬 workspace 외부 경로는 저장소 문서에 기록하지 않는다.

## Base advance: 전체 1 commit / 18 files

유일한 commit은 PR #193의 Production External Journal Factory다. 같은 이름의 Session 경합 수정이지만 Music Director의 Session/publisher 경계와 다른 Runtime이다. 새 Factory는 별도 pinned connection·RLock·bounded root Session을 소유한다. Music Director는 기존 application engine/sessionmaker를 사용한다.

| 분류 | 파일 | 판정 |
|---|---|---|
| B 문서 직접 겹침 | CHANGELOG.md, MASTER_ROADMAP.md, README.md, ROADMAP.md, docs/09-security/security-policy.md, docs/11-decisions/README.md | PR #193 Bootstrap 내용을 유지하고 독립 E2E 문장만 반영 |
| A 별도 Bootstrap 구현 | backend/bootstrap_authority/journal_schema_v1.py, backend/bootstrap_authority/production_external_journal.py | exact external journal schema metadata·existing-only Factory; E2E code 변경과 겹침 없음 |
| A 별도 테스트 | backend/tests/test_production_external_journal_factory.py | Factory Session lifetime 회귀; Music Director fixture를 바꾸지 않음 |
| A 별도 문서 | docs/03-architecture/bootstrap-issuance-integrity-verifier.md, docs/03-architecture/deployment-architecture.md, docs/03-architecture/deployment-verifier-current-status.md, docs/03-architecture/dohavocal-production-rights-domain.md, docs/03-architecture/local-operator-authentication.md, docs/03-architecture/product-deployment-bootstrap-authority.md, docs/07-database/deployment-lifecycle-journal.md, docs/10-operations/production-external-journal-factory-validation.md, docs/11-decisions/ADR-106-production-external-journal-factory-foundation.md | Bootstrap 상태 정렬; Fake rights E2E와 production 미활성 경계 유지 |

C(전제 변경)는 확인되지 않았다. D(실패 관련 가능)는 Session이라는 용어 때문에 검토했으나, 실패 service/publisher/resolver/DB helper/test의 OLD_BASE→NEW_DEVELOP diff는 0이다. Provider·locator·staging·Completion·rights runtime·Worker·migration·workflow 변경도 0이다. 전체 suite에는 #193 신규 tests가 추가되므로 이전 full 결과를 새 authority로 재사용하지 않는다.

## 기존 E2E 파일 재감사

| 파일 | 재감사 결과 |
|---|---|
| .github/workflows/voice-ffmpeg-integration.yml | 재사용: 기반 변경과 겹침 없음 |
| CHANGELOG.md | adaptation: 새 Bootstrap 변경 보존 |
| MASTER_ROADMAP.md | adaptation: 새 Bootstrap 변경 보존 |
| README.md | adaptation: 새 Bootstrap 변경 보존 |
| ROADMAP.md | adaptation: 새 Bootstrap 변경 보존 |
| backend/app/factory.py | 재사용: 기반 변경과 겹침 없음 |
| backend/providers/vocal/acquisition.py | 재사용: 기반 변경과 겹침 없음 |
| backend/providers/vocal/client.py | 재사용: 기반 변경과 겹침 없음 |
| backend/providers/vocal/http_transport.py | 재사용: 기반 변경과 겹침 없음 |
| backend/providers/vocal/mapping.py | 재사용: 기반 변경과 겹침 없음 |
| backend/providers/vocal/transport.py | 재사용: 기반 변경과 겹침 없음 |
| backend/services/workspace/__init__.py | 재사용: 기반 변경과 겹침 없음 |
| backend/services/workspace/provider_result_ingestion_service.py | 재사용: 기반 변경과 겹침 없음 |
| backend/services/workspace/vocal_payload_reconciliation_service.py | 재사용: 기반 변경과 겹침 없음 |
| backend/tests/support/vocal_e2e.py | 재사용: 기반 변경과 겹침 없음 |
| backend/tests/support/vocal_runtime.py | 재사용: 기반 변경과 겹침 없음 |
| backend/tests/test_dohavocal_runtime_e2e.py | 재사용: 기반 변경과 겹침 없음 |
| backend/tests/test_dohavocal_stream_guards.py | 재사용: 기반 변경과 겹침 없음 |
| backend/tests/test_vocal_payload_reconciliation.py | 재사용: 기반 변경과 겹침 없음 |
| docs/03-architecture/dohavocal-consumer-contract.md | 재사용: 기반 변경과 겹침 없음 |
| docs/03-architecture/dohavocal-payload-acquisition-orchestration.md | 재사용: 기반 변경과 겹침 없음 |
| docs/03-architecture/dohavocal-verified-staged-artifact-completion.md | 재사용: 기반 변경과 겹침 없음 |
| docs/03-architecture/dohavocal-worker-reconciliation-contract.md | 재사용: 기반 변경과 겹침 없음 |
| docs/03-architecture/durable-payload-locator-authority.md | 재사용: 기반 변경과 겹침 없음 |
| docs/03-architecture/verified-durable-staging-authority.md | 재사용: 기반 변경과 겹침 없음 |
| docs/09-security/security-policy.md | adaptation: 새 Bootstrap 변경 보존 |
| docs/10-operations/artifact-storage-ingestion.md | 재사용: 기반 변경과 겹침 없음 |
| docs/10-operations/dohavocal-020-consumer-e2e-validation.md | 재사용; 이번 보고서는 새 실행 이력 추가 |
| docs/10-operations/workspace-job-worker.md | 재사용: 기반 변경과 겹침 없음 |
| docs/11-decisions/ADR-048-dohavocal-payload-acquisition-consumer.md | 재사용: 기반 변경과 겹침 없음 |
| docs/11-decisions/ADR-051-verified-durable-staging-authority.md | 재사용: 기반 변경과 겹침 없음 |
| docs/11-decisions/ADR-074-dohavocal-verified-staged-artifact-completion-authority.md | 재사용: 기반 변경과 겹침 없음 |
| docs/11-decisions/README.md | adaptation: 새 Bootstrap 변경 보존 |
| docs/DOCUMENT_AUTHORITY_MAP.md | 재사용: 기반 변경과 겹침 없음 |
| docs/DoD/Provider-Separation.md | 재사용: 기반 변경과 겹침 없음 |

추가 문서 정합화 4개: repository-provider-boundaries의 0.1/0.2 Runtime 구분, provider-api-contract의 Fake Artifact Completion/production wiring 구분, workspace-worker-reentry-lifecycle·durable-execution-handoff-analysis의 production downloader 범위 명확화다. durable-payload-locator-authority의 이전 표는 역사적 배경으로 표시하고 현재 authority를 별도로 기록했다.

흡수됨/obsolete/conflict/scope 밖으로 제거한 파일은 없다. 공유 문서 6개를 통째로 덮어쓰지 않았다. 새 migration, Repository commit/rollback, Production rights fallback, Worker wiring은 추가하지 않았다.

## 동시성 실패 조사

정확한 node는 `backend/tests/test_music_director_materialization_service.py::test_concurrent_exact_whole_set_converges`다. 두 thread가 같은 request를 materialize하며 같은 Run/candidate identities, logical Run +1·나머지 entity +2, physical proposal 2개를 기대한다. 이전 전체 실행은 identity assertion 전 `pool.map(...).result()`에서 예외가 발생했다.

- fixture: `_service(tmp_path, 2)`와 `_fresh_service(...)`, 같은 Graph/sessionmaker/storage root, 서로 다른 Service/Publisher 객체.
- SQLite는 fixture별 `director.db`, `check_same_thread=False`, `autoflush=False`, `expire_on_commit=False`; 각 service 단계가 독립 Session/transaction을 연다. 반복 실측 `journal_mode=delete`, WAL 아님.
- `_intend`의 unique/IntegrityError replay, `_publish`의 path validation·exclusive hard-link/adoption, `_complete`의 단일 logical transaction을 조사했다.
- `_publish`는 DB에서 읽은 status를 확인한 뒤 ORM update한다. 해당 분기에 conditional UPDATE/rowcount CAS나 retry는 없다. `_reconciliation_required`가 별도 transaction으로 status를 기록한다.
- isolated 테스트에는 barrier/sleep/seed가 없다. ThreadPoolExecutor(max_workers=2)의 scheduling에 의존한다. 각 반복은 별도 temp root/DB로 실행했으며 기존 사용자 DB를 읽지 않았다.

### 비교 결과

| 실행 | Clean NEW_DEVELOP | 새-base E2E |
|---|---:|---:|
| 문제 node 독립 process 10회 | 10 PASS / 0 FAIL | 10 PASS / 0 FAIL |
| Music Director materialization 전체 module | 16 PASS | 16 PASS |
| 위 module + candidate persistence 인접 suite | 38 PASS | 38 PASS |
| 같은 fixture·두 worker 100회, 양쪽 future 결과 수집 | 98 무예외 / 2 실패 | 97 무예외 / 3 실패 |

100회 실험은 원래 fixture와 실제 service를 사용한 별도 진단 harness이며 pytest 100 PASS로 합산하지 않는다. runtime source 수정, monkeypatch, artificial delay, 오류 주입은 없다. Python 3.12/native Windows, 동일 temp parent와 SQLite mode를 사용하고 각 100회 matrix는 순차 실행했다. 독립 프로세스 반복은 대략 4.5~4.9초이며 첫 clean import 실행은 약 18초였다. 모듈/인접 suite 수치는 별도 실행이고 full PASS를 대신하지 않는다.

실패 5회는 모두 한 worker의 `ArtifactPublishError`가 `LocalArtifactPublisher._publication_path` → `ArtifactStorageRoots.candidate_path`에서 발생하고, 반대 worker가 `_publish` **189행**에서 `MusicDirectorPersistenceError(CONFLICT)`를 발생시켰다. E2E harness는 publisher code `PUBLICATION_IDENTITY_INVALID`도 수집했다. 실패 fixture DB를 read-only로 재확인한 결과 5건 모두 Run/Candidate 0, 초기 Asset/Version/Artifact/Location/ProjectAsset 각 2, materialization 2였다. logical Completion은 commit되지 않았다. 최종 materialization 상태는 ordinal 0 `reconciliation_required`/version 1, ordinal 1 `intended`/version 0, physical proposal은 1개였다. 기존 full trace가 보여준 CONFLICT와 같은 발생 지점이다. 이 최초 비교에서는 safe mapping 아래 원인 예외를 저장하지 않았고, 아래 추가 진단에서 exception context를 확인했다.

### 원인 context 추가 확인

최종 full 종료 뒤 clean develop에서 같은 fixture를 100회 추가 실행하며 suppressed exception context까지 수집했다. 5회 실패했고 모두 `ValueError → ARTIFACT_STORAGE_ESCAPE → PUBLICATION_IDENTITY_INVALID`, 반대 worker의 `CONFLICT` chain이었다. `artifact_resolver.py:110`의 `candidate.resolve(strict=False).relative_to(root)`에서 resolved candidate는 Windows extended-length prefix를 포함하고 root는 일반 drive 형식이라 lexical containment가 실패했다. 실제 traversal/외부 경로 입력을 사용한 것이 아니다. 4회는 ordinal 0 reconciliation_required/ordinal 1 intended, 1회는 ordinal 0 published/ordinal 1 reconciliation_required였다.

이는 SQLite WAL/lock 오류나 E2E의 Session 변경을 원인으로 볼 증거가 아니다. Windows 경합에서 드러나는 기존 storage path 표현/containment 실패이며, prefix 반환 조건의 저수준 OS interleaving 전체를 증명한 것은 아니다. 보안 검사를 제거하거나 prefix를 무조건 잘라 우회하지 않는다. 별도 storage 수정에서 canonical path/file identity와 reparse 방어를 함께 보존하고 검증해야 한다. 진단 harness는 증거 묶음의 `reproduce_music_director.py`, 결과는 `control-context.json`에 보존했다. 최초 clean 2/100·E2E 3/100 matrix와 이 추가 5/100은 서로 다른 실행이며 합쳐 동일 조건 failure rate로 주장하지 않는다.

최종 분류: **PREEXISTING_FLAKY_CONCURRENCY**. E2E 없는 clean develop에서 같은 실패를 실제 재현했고 관련 코드가 OLD_BASE와 동일하다. E2E_REGRESSION/NEW_BASE_REGRESSION 또는 환경만의 문제라고 주장하지 않는다. 상태 실패 자체는 해결되지 않았다.

AGENTS.md는 검증하지 않은 병합을 금지하고 범위 밖 문제는 후속 보고하도록 한다. 기존 validation 문서의 환경 오류 재실행 사례는 temp ACL/길이 등 원인을 확인하고 최종 정상 환경에서 검증한 사례다. 원인 미해결인 이 경합을 면제하는 policy/precedent는 찾지 못했다. 따라서 단일 full 실행이 통과하더라도 반복 재현된 실패를 지우거나 commit/merge Gate PASS로 전환하지 않는다. unrelated Music Director production/test 수정은 하지 않는다.

## 새 최종 검증 authority

- 최종 focused: **166 passed**, 181 warnings, 14.87s, process exit 0, JUnit 확보.
- 직접 영향 regression: **294 passed / 2 skipped**, 46.88s, process exit 0, JUnit 확보. 기존 Windows symlink 관련 skips이며 PASS에 포함하지 않는다.
- 단일 full backend: **2759 passed / 12 skipped / 0 failed**, 16845 warnings, 891.91s. process exit **0**, JUnit tests=2771 / failures=0 / errors=0 / skipped=12. Python source 542개 실행 전후 SHA-256 manifest 동일. 전체 실행 후 source/test 변경 0이며 후속 문서 정합화만 수행했다. 이 실행 PASS는 별도 반복 진단에서 재현된 실패를 해소하거나 merge를 허용하지 않는다.
- compileall backend/ai_worker: PASS. Ruff lint: PASS. Ruff format: 542 files formatted. git diff --check: PASS.
- API 전후 실제 측정: total routes 114 / API routes 110 / OpenAPI paths 89 / operations 110 / duplicate IDs 0.
- DB 전후 실제 측정: Alembic `20260918_0037` single head / metadata 67 tables. 새 migration·schema 변경 0.
- 문서/UTF-8/link/fence/secret/private-path/large/audio-model scan: PASS. 변경 39개 파일 / Markdown 24개. ADR 106개, 중복 번호 0, index 누락 0. 새 ADR 없음.
- E2E 관련 current authority의 0.1/0.2·payload/acquisition/GetPayloadContent/metadata-only/Fake/미구현 표현을 검색·대조했다. 잔여 현재 상태 모순 0; 역사적 ADR 배경과 이전 보고서는 현재 상태와 명시적으로 구분했다.
- full에서 기존 journal fixture가 생성한 untracked SQLite 1개는 cleanup 뒤 남아 SHA-256을 확인해 repository 밖 증거 묶음으로 보존 이동했다. 제품 diff/commit 대상에 포함하지 않았고 기존 사용자 파일은 이동·삭제하지 않았다.

## 유지한 E2E 경계와 PR 판정

**COMPLETION_E2E_IN_SCOPE**를 유지한다. ADR-074/075와 새 권한 문서를 다시 확인했으며 기존 Completion·Session-aware port를 explicit test Fake rights로만 호출한다. Production authentication/rights writer/adapter는 여전히 미구현이다. 0.1.0 기본값, explicit 0.2 capabilities/CreateJob/Manifest/Result, 실제 pinned ASGI 4 capabilities, 수신 bytes SHA-256/size/media 재검증, exact locator/source binding, verified staging, cancellation/retry/replay 및 final transaction rollback은 최종 focused suite에서 검증했다.

PR #130은 현재도 OPEN Draft, head `764e718a7d4f420e416c9f36a2cac814e5b5e528`이며 새 develop과 61/5 commits로 갈라졌다. **SUPERSEDE_PR_130_WITH_NEW_PR** 판정을 유지하고 PR #130/#171을 수정하거나 닫지 않았다.

Required checks를 원격에서 재확인했다: backend-ubuntu / ffmpeg-windows / frontend-playwright. 새 PR이 없으므로 이번 exact-head CI는 **NOT RUN**이다. 기존 다른 PR CI를 이번 결과로 재사용하지 않는다. 새 develop에서 재시작하여 이전 BASE_ADVANCED_BEFORE_READY는 현재 차단 사유로 이어받지 않으며, 종료 시 원격을 다시 관측했고 Music develop SHA/tree·main·Vocal SHA/tree 모두 위 START와 동일했다.

최종 변경은 39개 파일이며 전부 미커밋이다. additions/deletions: 2321 / 43. 새 commit/push/PR/Ready/merge/branch 삭제는 NOT RUN이다. Actions는 구성되어 있지만 이번 PR이 없으므로 NOT RUN이며 SUCCESS로 보고하지 않는다. 최신 첨부 지시는 37절의 `CI 완료`에서 끝났고 이후 새 지시는 수신하지 않았다. 현재 차단은 그 누락이 아니라 재현된 경합이다.

현재 BLOCKER는 재현된 기존 Music Director publication concurrency failure다. 먼저 별도 수정 작업에서 path resolution/publication 경합과 상태 전이를 보안 경계 완화 없이 해결하고, 이후 복구 E2E branch의 최신-base/focused/direct/full/CI Gate를 다시 확보해야 한다. 이 수정을 이번 E2E diff에 섞지 않는다.

WARNING: process-local Fake Provider, restart durability 미보장, production authentication/rights/Worker 미구현, 실제 external network E2E·사용자 audio·모델·GPU 미검증, 기존 dependency deprecation warnings. 실제 사용자 DB/audio/Production Artifact/external Provider/model download/GPU 접근은 0이다.

## 이전 blocked 실행의 역사적 기록 — 수정 없이 보존

아래 내용의 START/최종 관측/검증 수치는 2026-09-29 실행에만 해당한다. 현재 실행 결과로 해석하지 않는다.

# DohaVocal 0.2.0 Consumer E2E 검증 보고서

> 날짜: 2026-09-29
> 최종 판정: **BLOCKED — FULL_BACKEND_REGRESSION / BASE_ADVANCED_BEFORE_READY**
> 구현은 작업 branch의 미커밋 변경으로 보존했다. commit/push/PR/Ready/merge는 수행하지 않았다.

## 차단 근거

전체 backend 실행은 **1 failed, 2739 passed, 12 skipped, 16840 warnings**,
924.58초로 종료했다. 실패는
[test_concurrent_exact_whole_set_converges](../../backend/tests/test_music_director_materialization_service.py#L298)다.
[MusicDirectorCandidateMaterializationService._publish](../../backend/services/workspace/music_director_materialization_service.py#L189)에서
현재 status가 INTENDED/PUBLISHED/COMPLETED 허용 분기를 통과하지 못해
MusicDirectorPersistenceError: CONFLICT가 발생했다.

이 Music Director service와 test 파일은 이번 변경에서 수정하지 않았다.
동일 모듈을 START develop의 독립 checkout에서 한 번 실행하면 16 PASS,
작업 tree에서 한 번 분리 실행해도 16 PASS다. 따라서 전체 실행 실패의 원인은 아직
UNCONFIRMED이며 flaky라고 확정하거나 분리 재실행 PASS로 전체 실패를 대체하지 않는다.
사용자 지시 41절의 full backend regression 중단 조건과 30절의 Draft 전 전체 PASS 조건을 적용한다.
관련 없는 Music Director 수정이나 PR #171/#193 변경은 하지 않았다.

전체 suite가 collect된 뒤 test-only 최종 CAS rollback E2E 1건과 capability별 fixture
입력 role을 보강했다. 최종 focused 166 PASS가 이 최종 fixture를 검증한다.
전체 2739 PASS 수치를 최종 exact-head 전체 PASS로 주장하지 않는다.
최종 전체 suite·CI Gate는 후속 원인 해소 후 다시 확보해야 한다.

최종 원격 확인에서 develop이 6717bcd6c6d2bc296c6a374a189669cfbabfa991 (외부에서 병합된 #193)로 전진했다.
해당 tree는 ec3b8dd99fbc6285d2d41042eb4eb5ecb326c045다. 사용자 지시 33절에 따라
BASE_ADVANCED_BEFORE_READY를 추가 차단 사유로 기록한다. 자동 sync/rebase는 하지 않았고
이 보고서의 로컬 검증은 START 기반 작업 tree에만 적용된다.

## 실행 근거

- 변경 전 consumer/http/acquisition: 111 PASS.
- 최종 focused: 실제 pinned ASGI E2E 26개, stream guard 7개, 재사용 orchestration 22개,
  기존 consumer/http/acquisition 111개 = 166 PASS, 181 deprecation warnings.
- 직접 영향 regression: 294 PASS / 2 SKIP. 기존 Windows symlink 생성 제한에 따른 두 skip은 PASS로 세지 않는다.
- 전체 backend: 위 실패 결과. 실제 사용자 데이터 대신 기존 test fixture를 사용했다.
- Python compileall backend/ai_worker: PASS.
- Ruff check: PASS. Ruff format check: 540 files formatted.
- API 전후 실측: total routes 114 / API routes 110 / OpenAPI paths 89 /
  operations 110 / duplicate operation IDs 0.
- DB 전후 실측: Alembic 20260918_0037 / metadata 67 tables.
- 변경 파일 UTF-8·Markdown 상대 link/fence·secret/private path/large binary 검사: PASS.
- ADR 105개: 번호 중복 0 / index 누락 0. 새 ADR 없음, 기존 결정 의미 변경 없음.
- 실제 Provider 호출은 in-process ASGI이며 external Provider network 0.
- DohaVocal tracked 변경 0. 원래 Music checkout의 사용자 frontend 변경은 별도 worktree로 보존했다.

focused 명령:

    python -m pytest -q backend/tests/test_dohavocal_runtime_e2e.py backend/tests/test_dohavocal_stream_guards.py backend/tests/test_vocal_payload_reconciliation.py backend/tests/test_dohavocal_consumer_contract.py backend/tests/test_dohavocal_http_transport.py backend/tests/test_dohavocal_payload_acquisition.py

직접 영향은 provider_job_persistence, provider_result_ingestion_contract,
payload_locator_persistence, verified_payload_staging, trusted_payload_resolver_contract,
dohavocal_artifact_completion, workspace_job_worker_foundation, workspace_vocal_job_contract,
vocal_rights_persistence, vocal_rights_scope_guard_integrity의 10개 test module을 실행했다.

전체 명령: python -m pytest -q. 원인 분리 명령:
python -m pytest -q backend/tests/test_music_director_materialization_service.py.

## 요청된 71개 항목

| # | 항목 | 실제 결과 |
|---|---|---|
| 1 | START DohaMusic develop | cda9fa8bd1974d20d431b5efdc80ec024bfd3a21 |
| 2 | START DohaMusic tree | f84130a5db5a93a16f8e69f857c23d1c84c2516a |
| 3 | DohaVocal authority SHA | e28320ef26a2dc49eaefdfa62bceea0c8c69e6ed |
| 4 | DohaVocal tree | f5dc77e8db0d2d2caa051021662b94e7b969d223 |
| 5 | PR #130 판정 | SUPERSEDE_PR_130_WITH_NEW_PR |
| 6 | branch/PR 전략 | 최신 develop의 별도 worktree; #130 직접 merge/rebase/close 안 함 |
| 7 | 작업 branch | feature/dohavocal-020-consumer-e2e-foundation |
| 8 | PR number | NOT CREATED — full backend Gate 실패 |
| 9 | PR head | NOT APPLICABLE; 작업 HEAD는 START SHA, 구현은 미커밋 |
| 10 | changed files | 35 (미커밋 working diff, 이 보고서 포함) |
| 11 | additions/deletions | 2166 / 33 (미커밋 working diff) |
| 12 | architecture reuse | 기존 client·trust·ProviderJobBinding·PayloadLocator·staging·Completion; #130 reconciliation 재사용 |
| 13 | 0.1.0 compatibility | PASS; 기본 version 유지, 기준선/최종 focused 및 실제 ASGI metadata-only 검증 |
| 14 | explicit 0.2.0 selection | PASS; explicit query, matching capabilities/manifest preflight, unsupported version deny |
| 15 | capabilities E2E | PASS; actual ASGI 0.1/0.2 exact surface |
| 16 | CreateJob E2E | PASS; 4 capability authorized mapping |
| 17 | GetResult E2E | PASS; 4 capability와 stable replay |
| 18 | GetPayloadContent E2E | PASS; 실제 ASGI binary body와 repeated byte identity |
| 19 | 4 capability 결과 | generation/conversion/correction/analysis 모두 staging·Completion PASS |
| 20 | actual checksum | PASS; transport 및 staging/Artifact byte SHA-256 재검증 |
| 21 | actual size | PASS; actual count·expected size·maximum 검사 |
| 22 | media validation | PASS; canonical audio/wav 또는 application/json, staging 실제 형식 검사 |
| 23 | streaming | PASS; bounded 64 KiB reads, interruption/cancel/oversize 시 response close |
| 24 | redirect/SSRF | PASS; fixed configured origin, arbitrary selector/path deny, redirect 미추적 |
| 25 | cancellation | PASS; acquisition 전/중 및 기존 Completion regression |
| 26 | retry | PASS; 같은 source 명시적 재취득, Provider retry lineage; 자동 retry 없음 |
| 27 | idempotency | PASS; Create replay/conflict, Result·locator·Completion exact replay |
| 28 | PayloadLocator | PASS; 기존 issue/replay·ordinal/binding·revocation·revision CAS |
| 29 | verified staging | PASS; source_bound → verified_staged, 실패 시 잘못된 전이/출력 없음 |
| 30 | Completion scope | COMPLETION_E2E_IN_SCOPE — explicit test Fake rights와 임시 DB만 |
| 31 | Completion 결과 | PASS; 4 targets, replay, final CAS failure rollback 후 재시도 |
| 32 | rights boundary | PASS; Fake는 tests-only, production auth/rights adapter/writer 미구현 유지 |
| 33 | transaction | PASS; existing transaction owners 유지, repository 변경 0, no partial output/terminal mutation |
| 34 | focused tests | 166 PASS / 0 SKIP |
| 35 | direct regression | 294 PASS / 2 SKIP |
| 36 | full backend | FAIL: 2739 PASS / 12 SKIP / 1 FAIL; 최종 test-only 보강은 focused 별도 검증 |
| 37 | frontend regression | NOT RUN; frontend 변경 0, required CI도 아직 미실행 |
| 38 | compile | PASS |
| 39 | Ruff lint | PASS |
| 40 | Ruff format | PASS; 540 files |
| 41 | git diff check | PASS |
| 42 | Alembic head | 전/후 20260918_0037 |
| 43 | new migration count | 0; schema-neutral, 새 migration 불필요; production upgrade 0 |
| 44 | metadata table count | 전/후 67 |
| 45 | actual DB access | 사용자/production DB 0; 임시 test DB만 |
| 46 | actual user audio | 0 |
| 47 | actual GPU/model | 0; model download 0 |
| 48 | security scans | secret/private path/large file/audio/model/checkpoint 추가 0 |
| 49 | docs | 현재 E2E 상태 정합화, ADR implementation note만 변경, 역사 기록 보존 |
| 50 | contradictions | START 기반 영향 E2E authority의 남은 모순 0; 전진한 develop은 재검증 필요 |
| 51 | Draft PR result | NOT CREATED — Gate 차단 |
| 52 | exact-head Actions | NOT RUN — PR/head 미생성; CI는 구성되어 있음 |
| 53 | required checks | backend-ubuntu / ffmpeg-windows / frontend-playwright; 모두 최종 head SUCCESS 필요 |
| 54 | reviews | NOT APPLICABLE — 신규 PR 없음; required reviews 설정 없음 |
| 55 | threads | NOT APPLICABLE — 신규 PR 없음 |
| 56 | base race before Ready | BLOCKER: BASE_ADVANCED_BEFORE_READY; START → 6717bcd6 |
| 57 | Ready result | NOT RUN |
| 58 | base race after Ready | NOT APPLICABLE |
| 59 | merge guard | NOT RUN |
| 60 | merge result | NOT RUN |
| 61 | merge commit | NOT APPLICABLE |
| 62 | final observed develop | 6717bcd6c6d2bc296c6a374a189669cfbabfa991 |
| 63 | final develop tree | ec3b8dd99fbc6285d2d41042eb4eb5ecb326c045 |
| 64 | PR final tree | NOT APPLICABLE |
| 65 | tree equality | NOT APPLICABLE — merge 없음 |
| 66 | main final observed | 63633d462043ad3ba78fee92473d19e90c361431; START와 동일 |
| 67 | branch deletion | 0; delete_branch_on_merge=false 확인, #130 OPEN/Draft/head 보존 |
| 68 | BLOCKER | FULL_BACKEND_REGRESSION + BASE_ADVANCED_BEFORE_READY; Music Director CONFLICT 원인 미확정 |
| 69 | WARNING | Fake process-local/restart durability 없음; production auth/rights/Worker 없음; 모델/음질·성능 미검증; dependency warnings와 platform skips |
| 70 | 미수행 | commit/push/Draft/CI/Ready/merge/post-merge; production·user audio·model/GPU·real network E2E |
| 71 | 다음 권장 작업 | 새 develop 기준에서 Music Director 동시성 실패 원인을 분리·해소하고, 보존한 E2E 변경을 독립 재검증 |

PR #130은 OPEN/Draft, head 764e718a7d4f420e416c9f36a2cac814e5b5e528로 보존했다.
구현 상세와 정상 병합 이후의 architecture 후속 순서는
[Consumer E2E 경계](../03-architecture/dohavocal-payload-acquisition-orchestration.md)를 따른다.
