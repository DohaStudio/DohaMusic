# DohaVocal Completion Foundation Reconciliation

- 날짜: 2026-09-17
- START head: `6aca1b6f832f7db09a7c91d5eb1b3608ae289b89`
- authority: `develop@4250a51509df0042dca8aefac9654f74286897ac`
- 계약: [ADR-074](../../docs/11-decisions/ADR-074-dohavocal-verified-staged-artifact-completion-authority.md)
- PR #159: 기존 stacked base 유지, Draft 유지, Ready/PR merge 없음

## Authority와 merge

#156은 위 develop에 squash merge됐다. #157은 공통 ingestion의 JSON-only `register_trusted_adopted_in_session()`과 Music Director proposal publication identity를 추가했다. #158은 별도 Run/WorkingComposition APPLY 계약이다. 기존 prepare/register/verify/finalize/compensate, generic/Export Completion, Asset selection 및 PayloadLocator/staging 핵심 authority는 유지된다. stream prepare와 JSON adopted 경로는 자동 통합됐으며 새 domain ledger를 Vocal authority로 사용하지 않았다.

normal merge의 실제 충돌은 CHANGELOG, MASTER_ROADMAP, README, ROADMAP, artifact-storage-contract, Vocal Completion architecture, worker-reconciliation-contract, durable-payload-locator-authority, provider-result-ingestion-contract, repository-provider-boundaries, storage-architecture, trusted-payload-locator-resolver-contract, verified-durable-staging-authority, workspace-job-foundation, ADR index의 문서 15개다. 양쪽 CHANGELOG와 최신 Music Director ADR 069~073 및 merged Vocal ADR-074를 보존하고 Foundation 구현 상태를 합쳤다. 폐기된 Vocal ADR filename은 제거했으며 결정 내용은 ADR-074에서 유지한다.

## 최소 production adaptation

generation replay가 `selected_asset_version_id is None`을 강제하던 검사를 제거했다. 사용자 selection은 completion identity가 아니다. generation ProjectAsset membership은 replay에서만 tombstone-aware lookup을 사용한다. 신규 commit의 active source/target gate와 별도 current output rights 검사는 그대로다. selection, tombstone, current-rights denial, stale worker/lease 및 verification/final commit 실패 회귀를 추가했다.

## Transaction / security audit

열린 staging stream을 publisher-owned pending object로 bounded copy하고 SHA-256·size·media를 독립 검사한다. physical publish는 DB transaction 밖이며 final Completion Session에서 필요한 Asset/ProjectAsset/Version, Artifact/catalog, JobOutput, ModelUsage, locator revision CAS와 Job claim CAS를 확정한다. Workspace/Completion repository 직접 commit/rollback은 0이다. 실패는 전체 rollback과 기존 invocation-owned publish compensation을 사용한다. cleanup은 기존 locator lifecycle의 별도 책임이다.

generation은 새 Vocal Asset/version 1, conversion/correction은 같은 source Asset의 다음 Version, analysis는 exact source Version의 evaluation JSON Artifact only다. source Version과 selection을 덮어쓰지 않는다. successful replay는 staging을 열지 않으며 duplicate output/version/usage를 만들지 않는다. deterministic concurrency fixture는 1개 committed aggregate와 loser replay를 검증한다.

권한은 caller-owned Session에 참여하는 injected `VocalCompletionRightsPort`에 매번 요청한다. production consent/access/use rights writer와 연결·serialization을 보장하는 concrete adapter는 본 Foundation에도 미구현이다. test rights double의 성공을 production rights 구현으로 표시하지 않는다. Provider rights나 acquisition snapshot을 최종 승인으로 사용하지 않는다.

safe error code로 ingestion/persistence/rights 실패를 노출하고 DTO에 staging/local path를 담지 않는다. 민감 경로·bearer 문자열 failure injection은 public error에 나타나지 않는다. 실제 Provider, 사용자 DB, 운영 Artifact/storage에는 접근하지 않았다. schema/Alembic/Public API/Frontend/Worker/auth 변경은 0이다.

## 검증 기록

- focused final run: `test_dohavocal_artifact_completion.py`, **33 passed (30.10s)**.
- 최초 direct command는 잘못된 test filename으로 collection 전 중단(no tests ran)했고, 올바른 `test_provider_result_ingestion_contract.py`로 전체 direct 목록을 재실행했다. 소스 실패가 아니다.
- compileall, changed Python 6개 Ruff check/format check PASS. Formatting mutation 없음.
- Alembic: `20260911_0035 (head)`, single head.
- 문서 정적 검사: UTF-8/fence/relative links/ADR duplicate/secret pattern/marker PASS. 최종 report 추가 뒤 재검사한다.
- FFmpeg는 설치 변경 없이 현재 nightly `N-125875-g5d4d3bdc61-20260731`, gcc 15.2.0 build를 사용했다. binary는 WinGet yt-dlp.FFmpeg package의 기존 executable이다. stable binary를 설치하거나 교체하지 않았다.
- direct/full 결과와 실패 분류는 아래 최종 기록을 따른다. 과거 #159 테스트 결과를 현재 결과로 재사용하지 않는다.

- direct run: staging, locator, generic/Export Completion, trusted/adopted registration, publisher, terminal replay, multiformat Export worker, Workspace entities, Provider Result trust gate의 10개 파일: **138 passed, 1 skipped (84.51s)**.
- generated focused WAV fixture는 204 bytes, SHA-256 `60c0b6c740c791f5d9c1b7d688aa4e6719b93c8f4e7c4b7919ab86ad78b74068`; 현재 ffprobe는 pipe 입력의 automatic/explicit WAV 두 모드 모두 `wav`, exit 0. 이는 작은 focused fixture의 결과이지 모든 과거 Export fixture의 자동 probe 호환성을 보장하지 않는다.
- full backend collection: 1630 tests. 현재 full run은 별도이며 direct/focused 합계를 전체 suite PASS로 표시하지 않는다.

- 추가 Export 회귀: worker integrity, multiformat lineage/final proofs, delivery validator **49 passed (50.99s)**. 기존 nightly에서 현재 실패는 재현되지 않았다. latest develop에는 WAV 입력을 명시적으로 처리하는 #157 변경이 포함되어 있다. binary 교체가 없으므로 stable 환경 PASS로 분류하지 않으며, 과거 모든 fixture의 automatic probe가 수정됐다고 단정하지 않는다.
- 전체 `backend ai_worker` Ruff check PASS, Ruff format check **466 files already formatted**; compileall PASS. Changed-file strict UTF-8, Markdown fence, 상대 링크 **490개**, ADR duplicate, secret/local-path pattern과 conflict marker 검사 PASS. 테스트의 민감 문자열 fixture와 실제 외부 노출을 구분했다.

- 전체 backend repository 검색에서는 Legacy repository의 기존 commit/rollback 호출 36건이 존재한다. latest develop baseline에도 동일하며 해당 파일 diff는 0이다. 전 저장소 호출 0이라고 주장하지 않는다. Workspace 계약의 legacy 제외 경계에 따라 이번 Completion scope는 0이며 unrelated legacy transaction refactoring은 수행하지 않았다.

## 최종 authoritative run

`python -m pytest -p no:cacheprovider backend/tests -q --tb=short`: **1618 passed, 12 skipped, failed 0, deselected 0**, 1630 collected, **1251.17s (20:51)**. 한 번의 직렬 full run 결과이며 shard 합산이 아니다. Production/test source는 full run 시작 후 변경하지 않았다.

Python 3.12 SQLite default datetime adapter deprecation warning 16664건은 별도로 기록한다. test failure는 0이므로 implementation/baseline 실패 비교 대상도 0이며 별도 full develop baseline은 실행하지 않았다. 과거 34건 실패나 nightly Export 13건을 현재 결과로 재사용하지 않았다. 현재 integrated source/current nightly의 full run에서 해당 실패는 재현되지 않았지만 stable toolchain 검증을 수행했다고 주장하지 않는다.

최종 ADR 검사에는 파일 번호 중복뿐 아니라 index 표시 번호와 링크 filename의 일치 및 index 중복 검사도 포함했다. Music Director 069~073 authority는 보존하고 Vocal 074의 구현 상태만 동기화한다. PR base normalization, Ready와 PR merge는 후속 별도 단계다.
