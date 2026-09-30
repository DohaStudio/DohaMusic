# Storage publication concurrency 수정 검증

> 최종 수정일: 2026-09-30
> 상태: commit 직전 로컬 검증 완료 기록 (2026-09-30). 이후 PR·CI·Ready·merge 상태는 해당 PR의 GitHub 이력을 따른다.
> 범위: 기존 Windows storage false conflict의 최소 수정. DohaVocal E2E 변경과 독립이다.

## 기준선과 격리

- START_DEVELOP: `6717bcd6c6d2bc296c6a374a189669cfbabfa991`
- START tree: `ec3b8dd99fbc6285d2d41042eb4eb5ecb326c045`
- START main: `63633d462043ad3ba78fee92473d19e90c361431`
- branch: `fix/storage-publication-concurrency-flake`
- 별도 worktree의 HEAD가 START와 같고 tracked/staged/unexpected untracked가 모두 0인 상태에서 조사했다.
- 보존 중인 E2E revalidation 39개 파일은 read-only SHA-256 manifest로 확인했다. E2E worktree·report·branch·PR #130/#171/#193은 수정하지 않았다. 이번 storage branch에는 E2E source/test/report를 복사하지 않았다.
- 원격 open PR은 #130/#171 Draft, 최근 merged PR은 #193/#192/#191/#190/#189였다. 겹치는 storage fix PR은 없었다.
- required checks: `backend-ubuntu`, `ffmpeg-windows`, `frontend-playwright`; strict=false. CI 완료 뒤 같은 head/base/review/thread 상태를 다시 확인한다.

## 증상과 exact failure

node: `backend/tests/test_music_director_materialization_service.py::test_concurrent_exact_whole_set_converges` (parametrization 없음).

`_service(tmp_path, 2)`와 `_fresh_service(...)`가 같은 Graph/request/storage root에 대해 두 service·publisher를 만든다. `ThreadPoolExecutor(max_workers=2)`에서 같은 두 proposal을 materialize한다. 기대값은 같은 Run ID·ordered candidate IDs, Run +1·기타 logical entity +2, physical proposal 2개다. 실패는 이 assertion 이전 future 결과에서 발생한다.

관찰한 chain:

1. `ArtifactStorageRoots.candidate_path`의 `candidate.resolve(strict=False).relative_to(root)`에서 `ValueError`.
2. candidate에 Windows extended-length anchor가 남고 root는 일반 drive anchor여서 같은 root 내부 경로를 lexical 외부 경로로 판정.
3. `ArtifactStorageError(ARTIFACT_STORAGE_ESCAPE)` → `LocalArtifactPublisher._publication_path`의 `ArtifactPublishError(PUBLICATION_IDENTITY_INVALID)`.
4. Music Director `_publish`가 `_reconciliation_required`를 별도 transaction에 기록.
5. 다른 worker의 `_publish` 189행이 `reconciliation_required`를 읽어 `MusicDirectorPersistenceError(CONFLICT)`.

이전 E2E 조사에서는 clean 2/100, E2E 3/100, 추가 clean context 5/100을 관찰했다. 이번 독립 조사에서는 수정 전 원래 test body를 100회 실행해 **6 failures / 100**이었다. 각 수치는 별도 실행이며 합쳐 하나의 failure rate로 주장하지 않는다.

## Authority와 호출 경계

| 책임 | 기존 authority / 이번 보존 |
|---|---|
| 최초 path 생성 | config-owned approved domain root + canonical POSIX relative storage key를 `ArtifactStorageRoots.candidate_path`가 결합 |
| durable path 저장 | `ArtifactStorageLocation`의 backend/domain/storage_key/locator version; absolute path·namespace prefix를 저장하지 않음 |
| root normalize | `_validate_root`: existing directory·component reparse 검사 후 strict native resolve |
| candidate normalize/비교 | native resolve는 유지; resolver 한 곳의 `_storage_relative_path`가 containment 비교 identity를 담당 |
| publication identity | `TrustedPublicationIdentity`: Job-owned Export key 또는 Music Director Job/ordinal/proposal digest key |
| storage locator | 기존 Catalog의 Artifact 1:1 locator; schema와 repository 변경 없음 |
| 경쟁/transaction | filesystem exclusive hard-link + exact existing adoption, materialization unique constraints와 service-owned Session/transaction |
| logical conflict | proposal mismatch/unique identity/status 검증은 기존 Music Director service가 소유; 변경 없음 |

ADR-032의 durable identity는 canonical relative key와 Artifact Catalog다. native filesystem 표시는 durable identity가 아니며 열린 descriptor의 device/inode identity 검증도 그대로다. 새로운 identity authority나 ADR decision을 만들지 않았다.

## 재현된 exact interleaving

Python 3.12.5 native Windows `ntpath.realpath` source와 실제 native lookup을 대조했다. 비존재 경로의 non-strict resolve는 최초 WinError를 보존하고, 확장 prefix 제거를 위한 마지막 lookup이 같은 오류를 반환하는지 검사한다.

| 순서 | T1 candidate resolution | T2 publication |
|---|---|---|
| 1 | target parent가 없는 상태에서 native lookup: WinError 3 | 대기 |
| 2 | Event에서 대기 | 승인 root 아래 target parent 생성 |
| 3 | 재개; non-strict lookup은 이제 leaf만 없으므로 WinError 2 | hard-link 직전 Event에서 대기 |
| 4 | initial 3와 final 2가 달라 native 결과에 extended anchor 유지 | 대기 |
| 5 (수정 전) | plain root와 lexical 비교 실패 | 이후 publish 가능하지만 materialization false conflict 발생 가능 |
| 5 (수정 후) | 같은 native anchor의 comparison identity로 containment 통과 | 기존 exclusive link/adopt로 수렴 |

두 새 native test는 오류를 fake하지 않는다. `_getfinalpathname`의 실제 결과/오류를 전달하며 Event로 scheduling만 제어한다. 고정 sleep, retry, global mutex는 없다. 첫 test는 parent creation만 제어하고 수정 전 **1 FAIL**, 수정 후 PASS다. 두 번째는 두 실제 publisher를 scheduling하여 하나는 PUBLISHED_NEW, 하나는 ADOPTED_EXISTING, 같은 file identity와 bytes로 수렴함을 확인한다.

분류: **PATH_CANONICALIZATION_RACE**. SQLite visibility나 E2E/Provider 변경이 원인이 아니다. stock stress의 모든 OS scheduling을 설명한다고 주장하지 않으며, 위 native interleaving과 동일 오류 chain을 실제로 고정 재현했다.

## 최소 수정과 Windows path audit

`artifact_resolver.py` 한 production 파일에 내부 relative-path comparison helper를 추가했다. `PureWindowsPath`의 parsed anchor에서 DOS drive/UNC의 extended-length 표현만 일반 anchor에 대응시킨 후 `relative_to`를 수행한다. candidate containment, Resolver containment와 component 검사에 같은 helper를 사용한다. 파일을 열거나 반환하는 실제 `Path`, config, DB key와 Provider wire shape는 변하지 않는다.

| 항목 | 판정 |
|---|---|
| slash/backslash·separator·trailing separator | native Path semantics 유지; storage key는 기존 POSIX canonical validator가 별도 검증 |
| drive-letter case·Windows case sensitivity | PureWindowsPath 기존 case semantics 유지; POSIX case 구분은 유지 |
| relative/absolute·drive-relative | relative와 drive-relative를 root와 동등하게 만들지 않음; key의 drive/absolute 입력 거부 유지 |
| Path/str | 비교 결과는 PurePath이며 arbitrary 문자열 치환 비교를 사용하지 않음 |
| resolved/unresolved·canonical/presentation | native resolve 이후 containment 비교만 projection; durable relative key가 authority |
| URI·UNC | URI/UNC storage key는 거부; 이미 검증된 내부 UNC root의 namespace alias만 동등 비교, 새 network 접근 없음 |
| symlink/junction/reparse | 기존 component rejection·open descriptor identity 검증 유지; canonicalization이 검사 우회가 아님 |
| temp aliases·long-path prefix | temp root는 기존 strict native resolve; extended prefix 차이는 비교 identity를 갈라놓지 않음; I/O prefix는 제거하지 않음 |
| 다른 drive/share/root/device | distinct identity 유지; prefix 비슷한 sibling root와 device namespace는 containment 거부 |

Music Director, publisher, staging, DB/session helpers, unique constraint, revision, conditional UPDATE, CAS, transaction owner, compensation/cleanup source는 변경하지 않았다. Repository direct commit/rollback 신규 추가 0. 동시 root replacement/공격자 writer를 모두 원자 방어한다고 확대 주장하지 않으며 ADR-032의 trusted-root 운영 경계는 유지한다.

## Regression·security·stress

- 새 regression: **22 passed**. Windows native scheduling 2개, drive/UNC 표현 동등성, 다른 root/drive/device/relative 거부, POSIX 구분, arbitrary native/URI key 거부, 실제 concurrent byte mismatch 및 independent target 검증.
- 수정 전 관련 module: **60 passed / 2 skipped**. 이 실행 PASS는 6/100 stress failure를 지우지 않는다.
- 수정 후 original node test body **200회 / unexpected failure 0**. 원래 identity/count assertions를 그대로 실행했다.
- storage-first 순서: **104 passed / 2 skipped**, 6.76s.
- Music Director-first 역순: **104 passed / 2 skipped**, 7.53s.
- 동일 publication target에 서로 다른 bytes를 동시 제공하면 1 성공 / 1 `PUBLICATION_INTEGRITY_MISMATCH`, immutable bytes 유지. 서로 다른 target은 2 성공.
- 기존 Music Director conflicting proposal 테스트의 1 성공 / 1 legitimate `CONFLICT`와 logical counts도 유지했다.
- 기존 traversal, root escape, unsafe key, symlink/reparse, tamper, adoption, compensation과 safe error 회귀를 direct suite에 포함한다. Windows symlink 권한 제한 skip은 PASS로 세지 않는다.

## 검증 harness의 무효 실행 이력

첫 programmatic pytest runner는 Windows multiprocessing main guard가 없어 spawn child가 runner를 재실행하는 구조였다. parent 시작 뒤 child의 direct JUnit timestamp가 새로 기록된 것도 확인했다. full 진행 로그가 정체되어 조사했고 이 작업의 runner/자식 process만 중단했다. 이 invocation은 **INVALID_HARNESS / INTERRUPTED**, process exit -1이며 full PASS 근거로 사용하지 않는다. 로그·JUnit·runner 원문을 repository 밖 `invalid-unguarded-harness`에 보존했다. 제품 source/test 변경 없이 외부 runner에 `if __name__ == "__main__"` guard를 추가하고 direct → 단일 authoritative full → 같은 프로세스 post-full stress를 새로 실행했다. 이 중단을 제품 regression 수정이나 실패 없는 full로 바꾸어 보고하지 않는다.

## 최종 실행 Gate

- 직접 영향 17 modules: guarded authoritative 실행 **372 passed / 5 skipped**, 112.63s, process exit 0, JUnit tests=377 / failures=0 / errors=0 / skipped=5.
- 단일 authoritative full backend: **2726 passed / 12 skipped**, 824.74s, exit 0. JUnit tests=2738 / failures=0 / errors=0 / skipped=12. Skip은 실제 model/GPU/paid external opt-in 5개와 Windows symlink 생성 권한 제한 7개다. 기존 SQLite datetime adapter deprecation warning 16664건을 관찰했다.
- post-full original stress: **100/100, unexpected failure 0**. 같은 Python process에서 `pytest.main`의 full 종료 후 원래 test body와 assertions를 호출했다. direct → full → post-full runner의 최종 process exit도 0이다.
- full 실행 전후 first-party Python **537파일 SHA-256 동일**. 직접 영향 JUnit hash도 full 전후 동일하여 child 재진입으로 검증 결과가 덮어쓰이지 않았음을 확인했다. 코드/test 변경 없이 이 authority를 확정했다.
- compileall: PASS; Ruff lint: PASS; Ruff format: 537 files formatted; diff check: PASS.
- API 전후 실제 측정: total routes 114 / API routes 110 / OpenAPI paths 89 / operations 110 / duplicate operation IDs 0.
- schema 전후 실제 측정: Alembic `20260918_0037` single head / metadata 67 tables; migration/model 변경 0. 실제 사용자 DB 접근 0.
- 변경 6파일 strict UTF-8·Markdown link/fence·secret/private-path/large-file scan PASS. storage architecture/contract·ADR-032·관련 security authority의 요청 키워드를 검색·대조했고 이번 변경과 충돌하는 표현은 0이다. 최종 결과 기입 뒤 같은 검사를 재실행해 확인했다.

원시 log/JUnit/stress JSON·source manifest는 repository 밖 `.codex-storage-concurrency-evidence`에 보존했다. 테스트는 synthetic bytes와 disposable SQLite/temporary filesystem만 사용한다. 실제 사용자 audio/DB/Production Artifact/model/GPU/external Provider 접근은 0이다.

## 문서와 scope

CHANGELOG, 기존 Artifact Storage 계약의 구현 설명과 이 보고서만 갱신한다. README/ROADMAP/MASTER_ROADMAP/DoD는 기존 기능 복구이며 기능 범위·Phase 상태·완료율 변화가 없어 수정하지 않는다. ADR-032 결정 의미는 유지하며 새 ADR은 필요하지 않다. Windows CI의 해당 regression 실행 step만 추가했고 기존 권한/체크는 변경하지 않았다.

E2E 전용 파일·E2E report·Provider·schema·Public API·frontend·dependency·Music Director production 변경은 0이다. workflow 파일은 기존 파일이지만 이번 hunk는 storage Windows tests만 실행한다. 보존 E2E의 Provider checkout/ASGI hunk는 포함하지 않는다.

## commit 직전 PR·Ready·merge Gate 기록

아래 NOT RUN은 이 보고서를 확정한 commit 직전 시점의 historical 상태다. 이후 lifecycle 결과는 PR body와 GitHub check/review/merge 이력에서 확인하며, 이 snapshot을 현재 원격 상태로 해석하지 않는다.

- commit/push/Draft PR: NOT RUN; 모든 local Gate 통과 후 수행.
- exact-head required CI: NOT RUN; 구성되지 않은 상태가 아니라 아직 새 PR이 없음.
- Ready: NOT RUN. exact head, same START base, blocking reviews 0, unresolved threads 0, required CI SUCCESS를 함께 확인해야 한다.
- merge: NOT RUN. Ready 직후 재확인 뒤 expected-head squash, admin bypass/auto-merge/branch deletion 없이 수행한다.
- post-merge: PR MERGED·merge SHA·develop SHA/tree·main unchanged·branch preserved·PR tree equality 확인 예정.

로컬 Gate BLOCKER: 0. 원격 CI·Ready·merge는 이 snapshot 이후의 별도 Gate다.
전체 suite가 남긴 synthetic journal SQLite fixture 1개는 경로와 SHA-256을 확인하고 repository 밖 evidence로 보존했다. 실제 사용자 DB가 아니며 commit에 포함하지 않았다. 기존 fixture 정리 구현은 이번 범위에서 수정하지 않았다.

WARNING: 기존 dependency deprecation, Windows symlink 권한 skips, native Windows 재현은 다른 OS에서 skip하고 PureWindowsPath identity tests는 모든 OS에서 실행한다. trusted-root 운영 권한 경계는 유지한다.

후속 작업은 별도 E2E branch를 새 merged develop에서 재검증하는 것이다. 이번 수정에서 그 worktree나 historical blocked report를 갱신하지 않는다.
