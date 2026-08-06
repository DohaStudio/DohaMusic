# 변경 이력

> 문서 목적: 사용자와 개발자에게 의미 있는 저장소 변경을 기록한다.
> 현재 상태: **운영 중**
> 최종 수정일: 2026-08-06

DohaMusic 프로젝트의 주요 변경 사항을 기록한다. 일반 작업은 `[Unreleased]`에 기록하고 프로젝트 버전 정책은 구현 단계에서 결정한다.

## [Unreleased]

### 추가 — Workspace API 공통 기반과 명시적 Bootstrap

- FastAPI `0.141.1`부터 중첩 Router가 최상위 `app.routes`에 펼쳐지지 않는 환경 차이를 반영해, Route 기준선 테스트가 내부 저장 형태가 아닌 정규화된 등록 Route와 OpenAPI 계약을 검증하도록 수정했다.
- 기존 `/api` payload를 변경하지 않고 빈 `/api/v1` Router 기반, 성공·Collection·오류 Pydantic v2 Schema와 v1 전용 오류 응답 분기를 추가했다.
- 검증된 `X-Request-ID`를 재사용하고 그 외 요청에는 opaque UUID를 생성해 `request.state`, 응답 payload와 header에서 연결하도록 했다.
- 명시적 SQLite URL과 필수 `owner_id`, revision `20260806_0012`, Workspace Table을 확인한 뒤에만 단일 사용자 기본 Workspace를 생성하는 `--apply` Bootstrap CLI를 추가했다. dry-run은 DB를 열거나 변경하지 않는다.
- Bootstrap 재실행은 같은 owner의 활성 Workspace를 반환하며 여러 활성 Workspace, 잘못된 revision과 누락 Table은 중단한다. 실제 사용자 DB에는 실행하지 않았다.
- 64개 Resource Endpoint, 일반 Idempotency-Key 저장·재생, cursor codec, Artifact Resolver, Job dispatch, Frontend, backfill·dual write는 구현하지 않았다.

### 추가 — Workspace Application Service와 transaction 경계

- Workspace·Asset·Composition·Job·Collaboration 5개 Application Service를 additive namespace에 추가하고 Service 메서드가 동기 SQLAlchemy transaction을 소유하도록 했다.
- 같은 Session을 공유하는 여러 Workspace Repository 변경은 성공 시 한 번 commit되고 예외 시 전체 rollback되며 Repository의 commit·rollback 금지 정책을 유지한다.
- Resource Not Found·Conflict·Validation·Invalid State application 오류를 FastAPI와 분리하고 Job 공통 상태 전이와 불변 Version·Snapshot 계약을 Service에서 검증한다.
- Soft Delete된 `ProjectAsset`, `Tag`, `Favorite`의 Unique row는 새 row를 만들지 않고 같은 식별 row를 복구한다. 감사 식별자와 계보는 보존한다.
- 범용 Unit of Work, REST API·Pydantic Schema·Frontend·Provider 호출·backfill·dual write·Runtime 전환은 구현하지 않았다.

### 추가 — Workspace Repository 계층

- 기존 Runtime Repository를 변경하지 않고 `backend.repositories.workspace` 아래에 Workspace·Asset·Composition·Job·Collaboration 5개 Aggregate Repository를 additive로 추가했다.
- 신규 Repository는 주입받은 동기 `Session`에서 `add`·`flush`·조회만 수행하며 `commit`·`rollback`은 향후 Service 또는 Unit of Work의 transaction 경계로 남겼다.
- SQLAlchemy 2.0 조회, 안정적인 정렬, 제한된 `limit`·`offset`, Soft Delete 기본 필터와 Entity·Constraint 계약을 임시 SQLite Repository 테스트로 검증했다.
- Workspace Entity와 실제 사용자 DB additive migration은 완료됐지만 신규 Table은 비어 있다. backfill·dual write·Service·REST API·Legacy 제거는 수행하지 않았고 기존 Runtime Table 14개가 계속 source of truth다.

### 수정 — SQLite Migration 안전 제어

- 앱 lifespan의 Alembic `upgrade head`를 `DOHAMUSIC_AUTO_MIGRATE=true`에서만 실행하도록 변경하고 기본값을 `false`로 고정했다.
- Runtime과 Alembic online SQLite 연결이 공통 helper로 연결마다 `PRAGMA foreign_keys=ON`을 적용하고 Alembic이 활성 상태를 확인하도록 했다.
- 임시·테스트 DB 경로만 명시적으로 자동 Migration을 사용하도록 분리하고 실제 사용자 DB Inventory·backup·Migration은 수행하지 않았다.
- 실제 사용자 DB Inventory, 검증된 backup과 최종 적용 승인은 계속 BLOCKER로 유지한다.

### 추가 — Workspace DB Migration 사전 점검

- 실제 사용자 DB 경로를 필수 인자로 받고 SQLite read-only URI로 Inventory·무결성·schema drift를 검사하는 preflight 도구를 추가했다.
- 별도 확인 인수가 있어야 SQLite backup API로 timestamp backup을 생성하고 checksum·revision·Table·integrity를 검증하도록 했다.
- 실제 적용 Runbook, Preflight 체크리스트, Backup·Rollback 정책과 fixture 검증 보고서를 추가했다.
- 임시 fixture에서 원본 checksum 불변, backup, upgrade 복사본 35개 Table과 backup 복원본 14개 Table을 검증했다.
- 실제 사용자 DB 접근·Migration, backfill·dual write·Legacy 제거와 Runtime FK 설정 변경은 수행하지 않았다.

### 추가 — Workspace Entity additive Migration

- 기존 Alembic head `20260801_0011` 다음에 목표 Workspace Table 21개만 생성하는 `20260806_0012` revision을 추가했다.
- 기존 Runtime Table 14개와 Column·Constraint·데이터를 변경하지 않고 신규 FK 39개, Index 109개, Check Constraint 8개와 Unique Constraint 17개를 Entity metadata와 일치시켰다.
- 임시 SQLite DB에서 upgrade 후 전체 35개 application Table과 downgrade 후 Legacy 14개 Table 보존을 검증했다.
- 실제 사용자 DB Migration, backfill, dual write, Legacy 제거와 Repository·Service·REST API 구현은 수행하지 않았다.

### 추가 — Workspace SQLAlchemy Entity 초기 구현

- 기존 14개 Runtime Entity를 교체하지 않고 `backend.models.workspace` namespace에 목표 21개 SQLAlchemy 2.0 Entity를 additive로 추가했다.
- 기존 `DeclarativeBase`를 재사용하고 UUID 생성 함수, 생성·수정 시각과 Soft Delete Mixin, `AssetType`·목표 `JobStatus` 문자열 Enum을 구현했다.
- 문서의 PK·FK·Unique·Index·Nullable, `ProjectAsset` N:M, AssetVersion·Snapshot 계보, JobInput·JobOutput, RecordingEnrollment·Approval 관계를 metadata에 반영했다.
- 모든 신규 Entity를 `backend.models`에서 명시적으로 등록하고 mapper 대칭·FK 해석·35개 전체 metadata Table의 in-memory SQLite `create_all`을 검증했다.
- Alembic Migration·실제 DB 변경·Repository·Service·REST API·Worker·Runtime·Frontend는 변경하지 않았다.

### 수정 — Frontend dependency 기준선 정합성

- `brace-expansion`을 `5.0.9`, `minimatch`를 `10.2.6`, `postcss`를 `8.5.25`로 제한해 기존 override와 lockfile의 취약 버전을 안전한 패치 버전으로 교체했다.
- 기존 기준선에서 이미 선택하던 `sharp 0.35.0`을 직접 production dependency로 명시하고 `@img/sharp-wasm32 0.35.0`을 선택 dependency로 선언해 npm 11의 orphan 설치와 `extraneous` 문제를 제거했다.
- Next.js·React·TypeScript 버전과 Frontend 기능은 변경하지 않았으며 `npm ci`, `npm ls`, audit 0건, lint, typecheck, 97개 Vitest와 production build를 통과했다.
- 원인과 취약점별 처리 근거는 [Frontend dependency 기준선 검증 보고서](reports/validation/VALIDATION-FRONTEND-DEPENDENCY-BASELINE.md)에 기록했다.

### 검증 — 코드 기준선 안정화 점검

- `main` 대비 `develop`의 512개 파일을 Backend·Frontend·AI Worker·Alembic·테스트·문서·설정·스크립트로 분류하고 전체 제품 기준선 승격 영향을 기록했다.
- FastAPI·기존 14개 Runtime Entity·Alembic 단일 head·SQLite metadata와 Backend 195개, Frontend 97개 테스트 및 Frontend lint·typecheck·build를 검증했다.
- Git 추적 파일의 비밀정보·절대 운영 경로·Dataset·모델·Checkpoint·미디어·대용량 파일 포함 여부와 PR #55의 Workspace Entity 격리를 확인했다.
- `git diff --check`를 막던 6개 문서의 trailing whitespace와 EOF 공백만 제거했으며 내용과 의미는 변경하지 않았다.
- Frontend dependency tree의 `npm ls` 오류와 npm audit의 high 2건·moderate 2건을 main 승격 BLOCKER로 기록하고 자동 dependency 변경은 수행하지 않았다.
- 상세 결과와 후속 Gate는 [코드 기준선 안정화 검토 보고서](reports/validation/VALIDATION-WORKSPACE-CODE-BASELINE.md)에 기록했다.

### 문서 — 최종 아키텍처 기준선 검토

- DohaStudio Common Specification `0.1.0` / `draft-baseline`의 `main` 링크와 감사 기준 commit을 Workspace DB·REST API·Provider 경계 문서에 고정했다.
- 목표 `assets` Table에 선택적 `workspace_id`를 명시하고 `ProjectAsset.display_order` 용어를 정렬해 `Asset.project_id` 부재와 N:M 계약을 Table Definition·ERD·REST API까지 일치시켰다.
- 로컬 저장 정책을 `DohaData/{lm,audio,vocal}`과 Provider·Workspace 책임이 분리된 `DohaArtifacts/{lm,audio,vocal,music}` 구조로 정렬했다.
- Provider Model Manifest 최소 계약에 `model_type`, `dataset_manifest_id`, `training_run_id`, `created_at`을 반영해 공통 명세와 필드명을 일치시켰다.
- 저장소 소유자와 Apache-2.0 적용 제외 범위를 현재 DohaStudio 조직·권리 정책에 맞게 명확히 했다.
- 코드·Runtime·DB Migration·Dataset·모델·Artifact와 실제 로컬 폴더는 변경하지 않았다.

### 문서 — Workspace REST API 재설계

- DohaStudio Common Specification의 `Asset.project_id` 제거와 `Asset.workspace_id`·`ProjectAsset` N:M 계약을 API 선행 기준으로 반영했다.
- Pipeline 실행 중심이 아닌 Workspace·Project·Asset·AssetVersion·Artifact·Composition Snapshot·Job 중심의 `/api/v1` 목표 계약을 정의했다.
- 16개 API 그룹과 64개 Method·Path 조합, REST Method·Response·Error·cursor·filter·sort·Idempotency-Key·major version 정책을 문서화했다.
- Workspace Job과 Orchestrator 전용 Provider Job을 분리하고 Provider 간 직접 호출·경로 노출·기존 Version 덮어쓰기를 금지했다.
- 현행 기능별 API에서 목표 v1 API로 가는 Read Projection, 목표 DB write, Frontend 전환, Deprecation과 Legacy 제거 순서를 추가했다.
- FastAPI·Endpoint·OpenAPI YAML·SQL·ORM·Migration·Runtime·Provider·테스트는 변경하지 않았으며 모든 목표 API는 `[계획]`으로 유지한다.

### 문서 — Asset 중심 데이터베이스 재설계

- 확정된 DohaStudio Common Specification에서 `Asset.project_id`를 제거하고 `Asset.workspace_id`·`ProjectAsset` N:M 계약으로 정렬한 결과를 반영했다.
- DohaStudio Common Specification을 기준으로 Workspace·MusicProject·Asset·AssetVersion·Artifact·Composition Snapshot·Job 중심의 21개 Entity와 21개 목표 Table을 설계했다.
- Pipeline이 결과를 소유하지 않고 AssetVersion이 불변 결과를 소유하도록 ERD, PK·FK·Unique·Index, Selection·Approval·삭제·Snapshot 정책을 정의했다.
- 현행 14개 Table에서 목표 구조로 전환하는 additive backfill, Dual Write, Shadow Read, Read 전환과 Legacy 제거 순서 및 검증 Gate를 문서화했다.
- SQL·ORM·Migration·API·DB 파일·Artifact 파일과 Runtime은 변경하지 않았으며 목표 구조는 `[제안]`으로 유지한다.

### 문서 — DohaMusic Workspace `music` Artifact 도메인

- Composition Snapshot의 권위 있는 관계 데이터는 DB가 소유하고 `snapshots` 폴더는 재현·직렬화·백업용 Artifact라는 경계를 명확히 했다.
- Provider Runtime의 `lm`·`audio`·`vocal` Artifact와 DohaMusic Workspace의 Mix·Export·Preview·Composition Snapshot·실행 기록을 분리했다.
- `D:/DohaArtifacts/music/{mixes,exports,previews,snapshots,runs}` 목표 구조와 Mix·Export의 DohaMusic 책임을 문서화했다.
- Snapshot이 최신 Asset이 아니라 특정 AssetVersion을 참조하도록 계획하고 현재 폴더·환경 변수·코드·DB는 변경하지 않음을 명시했다.

### 문서 — AI Provider 저장소 책임과 단계적 Runtime 분리

- DohaMusic을 제품 서비스와 Workspace·Job Orchestrator·결과 관리·Mixer·최종 Export 책임으로 유지하고 DohaLM, DohaAudio, DohaVocal의 Dataset·학습·평가·Runtime 책임 경계를 정의했다. DohaAudio·DohaVocal 저장소는 존재하며 Runtime 기능은 `[계획]`으로 구분했다.
- 기존 `PipelineExecutor`를 장기 제품 책임이 아닌 Legacy·Compatibility Workflow로 명시하고 확정된 DohaStudio 공통 Provider 계약 참조를 추가했다.
- 신규 Music Generator는 DohaAudio, 신규 Singing Voice·Voice Conversion은 DohaVocal에서 구현하고 기존 ACE-Step·Demucs·Seed-VC subprocess는 검증된 전환 전까지 호환 계층으로 유지하도록 정했다.
- Git 밖의 공통 Dataset·Artifact root 정책, Model Manifest 최소 계약과 Provider Job·Artifact ID·URI·API versioning·GPU admission control을 ADR-028과 단계적 Roadmap·DoD에 기록했다.
- 이번 변경은 문서만 수정하며 저장소 생성, Runtime 코드 이동, HTTP API, Artifact URI와 공통 Model Registry 구현을 포함하지 않는다.

### 문서 — DohaLM 가사 생성·분석 연동 계획

- DohaLM과 DohaMusic의 Provider·Reference Application 경계, REST/Streaming 우선 연동과 미완료 Python SDK·전용 Lyrics API의 검증 게이트를 문서화했다.
- AI 초안·수정 제안·사용자 편집·최종 승인 버전과 모델 사용·라이선스 계보를 분리하고 승인본만 음악 Pipeline에 전달하도록 계획했다.
- `AIHUB-71748` 계열을 `research_only`로 분류하고 상업 작업에는 `commercial_approved` 모델만 허용하는 fail-closed 정책을 추가했다.

### 수정 — Voice Enrollment WAV 정규화 오류 분류

- 60초를 넘는 PCM16 WAV가 정규화 출력 상한에서 `VOICE_SAMPLE_NORMALIZATION_FAILED` 500으로 오분류되던 문제를 `VOICE_SAMPLE_DURATION_TOO_LONG` 422로 수정했다.
- PCM24·float32·ADPCM·WAVE_FORMAT_EXTENSIBLE WAV를 `VOICE_SAMPLE_UNSUPPORTED_CODEC` 422로 분리하고 PCM 16-bit WAV 변환 안내를 Backend·OpenAPI·Frontend에 반영했다.
- PCM16 mono/stereo/16kHz resample, 미지원 codec, 손상·빈 WAV, 부분 출력 cleanup, 동일·신규 idempotency key 재시도와 실패 DB·Storage cleanup 회귀 테스트를 추가했다.

### 수정 — Voice Enrollment WAV 업로드

- Frontend의 Next.js rewrite proxy가 기본 10MB를 넘는 multipart body를 절단해 Backend 계약상 유효한 WAV 업로드를 500으로 반환하던 문제를 수정했다.
- Backend의 25MiB 파일 제한에 multipart metadata 여유를 더해 proxy request body limit를 26MiB로 설정하고 설정 회귀 테스트를 추가했다.
- Backend·공개 API·DB·migration·Storage·scheduler 계약과 F6 `[진행 중]` 상태는 변경하지 않았다.

### 변경 — Guided Voice Enrollment UI

- 정상 안내를 INFO 카드로 분리하고 실제 오류에만 경고 UI를 사용하도록 Voice Enrollment Wizard의 메시지 위계를 정리했다.
- 녹음 상태·입력 수준·안내 문장, Sample 품질·재생·대표 선택·삭제 카드, 우측 Summary와 완료 화면을 Doha Studio 시각 체계에 맞게 개선했다.
- 로딩·빈 상태·단계 표시와 키보드·스크린 리더 정보를 보강하고 Desktop Chrome, 820px Tablet, Pixel 7 Playwright 회귀 범위를 구성했다.
- Backend·API·DB·migration과 F6 `[진행 중]` 상태는 변경하지 않았다.

### 테스트 — Guided Voice Enrollment Validation

- 제품·API·DB·migration을 변경하지 않고 신규 사용자 PASS 등록, 합성 MediaRecorder preview/upload, 3개 품질 WARNING, 실패·timeout·FFmpeg 미설치, upload/submit 멱등, 만료·cancel·cleanup UX를 다루는 Validation E2E를 추가했다.
- 설치된 Chrome·Edge, Playwright Firefox와 Pixel 7·iPhone 14 에뮬레이션을 분리한 browser matrix와 실제 `MediaRecorder.isTypeSupported()`·Blob MIME probe를 추가했다.
- 실제 기기·실제 microphone 검증과 자동화 결과를 구분한 Validation Report, 운영 전 점검과 Phase 9 선행 항목을 분리한 수동 체크리스트를 추가했다.
- 자동 Validation은 완료했지만 실제 Android/iOS/Safari·Bluetooth microphone, 인증·소유권과 장기 운영 monitoring이 남아 F6는 `[진행 중]`을 유지한다.

### 추가 — Guided Voice Enrollment 운영 안정성

- FastAPI lifecycle에 AI Worker와 분리된 process-local scheduler를 등록해 시작 시 crash recovery를 1회 수행하고 만료·cleanup·orphan scan을 설정 주기로 실행한다.
- 마지막 성공 mutation 기준 24시간 sliding 및 생성 기준 7일 absolute 만료를 DB query로 처리하고, 조회 요청은 만료 시간을 연장하지 않도록 유지한다.
- `DELETE_PENDING`·`DELETE_FAILED`·중단된 `VALIDATING`·`SUBMITTING`·cleanup `RUNNING` 상태를 멱등 복구하고 부분 정규화 파일·누락 파일·중복 삭제를 안전하게 처리한다.
- DB를 source of truth로 Enrollment/Profile/Sample 소유권과 Storage 파일을 대조하며, server-generated 경로로 확정 가능한 orphan만 grace period 이후 자동 삭제하고 나머지는 경로 없이 경고한다.
- cleanup 성공·실패, retry, 만료, orphan, 복구 건수의 process-local metric snapshot과 민감 경로를 포함하지 않는 운영 로그를 추가했다.
- scheduler·만료·retry query·부분 삭제·재시작·중단 submit/normalize/cleanup·orphan·Storage 멱등 삭제 자동 test를 추가했다.
- Frontend·공개 API·migration은 변경하지 않았으며 F6는 인증·소유권과 실제 사용자 마이크 평가가 남아 `[진행 중]`을 유지한다.

### 수정 — Guided Voice Enrollment FFmpeg 정규화

- FFmpeg 임시 출력 파일의 확장자가 `.normalizing`이어도 PCM16 WAV가 생성되도록 출력 포맷을 명시해 실제 WebM/Ogg 정규화 실패를 수정했다.
- WebM/Ogg 최초 처리 시 FFmpeg 실행 파일의 존재와 `ffmpeg -version` 응답을 확인하고 검증된 경로를 process 수명 동안 재사용하도록 탐지를 강화했다.
- 합성 Opus WebM/Ogg의 PCM16 48kHz mono 실변환과 Unicode·공백 경로, truncated 입력, 미설치·timeout·비정상 종료·부분 출력 cleanup을 검증하는 자동 test를 추가했다.
- Ubuntu 전체 Backend와 Windows FFmpeg 집중 통합 test를 수행하는 GitHub Actions workflow를 추가하고 Windows Winget 설치·PATH/절대 경로·재시작·codec 확인·라이선스 검토 절차를 문서화했다.
- F6는 cleanup scheduler·인증·실기기 MIME/수동 녹음 평가가 남아 `[진행 중]`으로 유지하고 Phase 8 `15/15, 100%`는 변경하지 않았다.

### 추가 — Guided Voice Enrollment Frontend

- `/voice`에 안내·동의·방법 선택·녹음/업로드·품질 확인·대표 Sample 선택·검토·완료의 8단계 Guided Wizard를 추가했다.
- `MediaRecorder` MIME feature detection, 마이크 권한·일시정지·재개·60초 자동 종료, Web Audio 입력 수준, 메모리 preview와 stream·Object URL 정리를 구현했다.
- Enrollment create·조회, Sample upload·조회·삭제, submit·cancel API client와 DTO allowlist mapper, UUID 기반 create/upload/submit 멱등성 재시도를 추가했다.
- `sessionStorage`에는 Enrollment ID와 단계만 보존해 새로고침을 복원하고, 만료·not found·cleanup 실패·FFmpeg 미설치 오류에 대한 사용자 복구 흐름을 추가했다.
- 합성 WAV API mock을 사용한 Desktop·Mobile Playwright E2E와 MIME·DTO·품질·오류·session·Wizard unit/component test를 추가했다.

### 변경 — Guided Voice Enrollment Frontend 호환성

- 기존 단일 WAV Profile 등록은 `/voice`의 `빠른 WAV 등록` fallback으로 유지하고, 신규 Profile 생성 후 기존 목록과 Studio 선택 상태를 즉시 갱신한다.
- 모바일 action이 Sample 선택을 가리지 않도록 Wizard action을 콘텐츠 흐름에 배치하고 44px 이상 기존 공통 control을 재사용했다.
- F6는 Frontend 구현 완료를 반영하되 실제 WebM/Ogg FFmpeg 통합, 주기적 expiration·cleanup scheduler와 Phase 9 인증·소유권이 남아 `[진행 중]`으로 유지한다.

### 추가 — Guided Voice Enrollment Backend

- `VoiceEnrollment`·`VoiceSample` ORM, lifecycle 상태 전이와 최소 Repository CRUD·만료·cleanup 조회를 추가했다.
- `VoiceProfile.active_reference_sample_id`와 Profile 1:N Sample 관계를 추가하고, 대표 Sample의 소유 Profile·`PROMOTED` 상태를 Repository에서 검증한다.
- Alembic `20260801_0010`에서 기존 Profile을 파일 접근 없이 결정적 `LEGACY_REFERENCE` Sample로 backfill하고, 신규 Enrollment·비레거시 Sample이 있으면 데이터 유실성 downgrade를 차단한다.
- 기존 단일 Voice Profile 생성도 호환 Sample과 대표 reference를 함께 기록하며 기존 Voice API·Pipeline·Voice Conversion 공개 계약을 유지한다.
- Enrollment 생성·조회·Sample 업로드·조회·삭제·제출·취소 7개 API와 안전한 공개 DTO·오류 계약을 추가했다.
- WAV를 Python으로, WebM/Ogg Opus를 optional FFmpeg로 decode해 PCM16 48kHz mono WAV로 정규화하고 duration·metadata·peak·RMS·silence·clipping을 검증한다.
- UUID 기반 임시 Enrollment Storage, Profile Sample reference 승격과 원본·취소·삭제·lazy 만료 cleanup primitive를 추가했다.
- create·upload·submit에 hashed `Idempotency-Key`와 request fingerprint를 적용하고 Alembic `20260801_0011`에 `idempotency_records`와 versioned sample 품질 metrics를 추가했다.
- 신규 Enrollment API·normalizer·validator·Storage·migration과 기존 Voice Profile 호환 회귀 test를 추가했다.

### 변경 — Guided Voice Enrollment 호환성

- Enrollment submit으로 만든 대표 reference를 기존 `VoiceProfile.reference_file_path`에 연결해 기존 Pipeline·Voice Conversion이 새 Profile을 그대로 사용하도록 했다.
- 기존 단일 `/api/voice-profiles/upload` 경로는 유지하고 Profile 삭제가 Enrollment의 여러 retained reference도 정리하도록 확장했다.
- F6 상태를 Backend 구현 완료·Frontend와 scheduler 미구현인 `[진행 중]`으로 갱신하고 Phase 8 `15/15, 100%`는 유지했다.

### 문서 — Guided Voice Enrollment

- 브라우저 WAV·WebM/Ogg를 Backend에서 PCM16 48kHz mono WAV로 정규화하는 경계, Profile 1:N Sample과 명시적 대표 reference, 임시 Enrollment의 24시간 sliding/7일 absolute 만료·idempotency·cleanup을 ADR-024~026 `[제안]`으로 기록했다.
- 현재 단일 WAV API와 구분되는 `/api/voice-enrollments` endpoint·상태·안전한 오류·테스트 계약 및 현재 schema와 구분되는 VoiceEnrollment·VoiceSample ERD·backfill·transaction 설계를 추가했다.
- F6의 Backend 구현 순서와 Storage·동의 경계를 구체화했으며 Runtime 코드·migration·UI는 추가하지 않고 F6 `[계획]`, Phase 8 `15/15, 100%`, Phase 7 Dataset 분리를 유지했다.
- 현재 단일 WAV Voice Profile 계약을 기준으로 사용자 안내형 Voice Enrollment Wizard, 녹음 문장, 길이·업로드·품질·상태·오류·접근성·테스트 요구사항을 문서화했다.
- MediaRecorder WebM/Ogg와 WAV-only Backend 차이, 단일 reference와 다중 sample 모델, 사전 validation·임시 upload·cleanup·동의 철회를 ADR·Backend 선행 항목으로 분리했다.
- Frontend Roadmap에 F6 Guided Voice Enrollment `[계획]` Track을 추가하고 Phase 8 기존 `15/15, 100%`와 Phase 7 개인화 Dataset·학습 경계를 유지했다.
- 음성 동의 정책에 명시적 제출 전 서버 미전송, Web Storage·Analytics 음성 저장/전송 금지, 철회·삭제와 공개 운영 선행 조건을 보완했다.

### Frontend 기준선 복구

- Python packaging용 `lib/` ignore 규칙에 누락됐던 Frontend shared mapper와 Result metadata allowlist 모듈을 기존 import·테스트·공개 DTO 계약에 맞춰 복구했다.
- 공개 Audio URL만 same-origin Backend 경로로 변환하고 내부 경로·알 수 없는 metadata를 차단해 Frontend typecheck·build·test 기준선을 회복했다.

### Phase 6.5 비용 발생 방지

- 유료 외부 Lyrics 테스트에 사용자 승인·실행 opt-in·API Key의 3중 조건을 적용했다.
- 실제 실측 상태를 `[사용자 승인 필요] [API Key 필요] [유료 실측 미수행]`으로 통일했다.
- 실제 유료 API 호출 없음, 발생 비용 0원, API Key 사용 없음과 미측정 항목을 운영·실험·Roadmap 문서에 명시했다.

### K-POP Creation Control Layer

- Provider-neutral `HookAnalyzer`와 NumPy·SciPy 기반 기본 구현을 추가해 final WAV의 에너지와 반복 패턴에서 15초 후렴 후보와 `0.0~1.0` confidence를 추정한다.
- `result_metadata.audio_analysis.hook`에 version·status·candidate 구간·confidence·`energy_repetition`/`energy_peak`/`fallback_middle` strategy를 저장하고 내부 frame score·경로는 공개 DTO에서 제외한다.
- 신뢰도 `0.50` 미만은 곡 중앙 fallback으로 처리하며 무음·짧은·손상·미지원 WAV와 분석 예외가 Pipeline 성공 및 final WAV Result를 실패시키지 않도록 했다.
- Result는 후렴 후보의 추정 구간과 신뢰도를, History 목록은 후보 유무만, Project 상세은 요약 구간을 표시하며 Chorus 확정 표현을 사용하지 않는다.
- 반복·단일 에너지 피크·후보 없음·짧은 WAV·무음 fixture와 Pipeline·Retry·공개 allowlist·Frontend·Desktop/Mobile 회귀를 검증해 K3.3을 `[완료]`로 갱신했다.
- Preview Export·Lyrics Alignment·Voice Analysis·ML Hook Detector·DB Migration·Provider 변경은 구현하지 않았으며 K3.4 Preview Export를 다음 계획으로 유지한다.
- Provider-neutral `TempoAnalyzer`를 추가해 완료 Pipeline의 `final.wav`에서 예상 BPM과 `0.0~1.0` confidence를 추정하고 요청 BPM signed/absolute error와 half/double-time 후보를 기록한다.
- K3.1의 비차단 완료 경계를 유지한 채 `result_metadata.audio_analysis.tempo`만 확장하고, Retry는 새 Job의 새 WAV를 다시 분석하며 이전 Tempo 결과를 복사하지 않는다.
- 공개 DTO를 requested/detected BPM·confidence·error·candidate·status·version allowlist로 제한하고 Result 상세 Tempo 카드, History 상태, Project 요약과 구형·partial·failed fallback을 추가했다.
- 60·80·100·120·140·160 BPM 합성 fixture, 요청값 비편향, half/double·무음·짧은·손상 WAV, Pipeline·Retry·Frontend·Desktop/Mobile 회귀를 검증해 K3.2를 `[완료]`로 갱신했다.
- 새 의존성·DB Migration·Provider 변경 없이 기존 NumPy·SciPy를 사용했으며 K3.3 Hook/Chorus, K3.4 Preview, True Peak·LoRA·Dataset·Voice 학습은 구현하지 않았다.
- Provider-neutral `AudioQualityAnalyzer`와 SciPy WAV decode·NumPy Sample Peak/clipping·pyloudnorm BS.1770 Integrated LUFS 구현을 추가했다.
- `final.wav`와 Pipeline Result를 먼저 `COMPLETED`로 확정한 뒤 versioned `result_metadata.audio_analysis`를 비차단 갱신해 분석·저장 실패가 재생·다운로드를 막지 않도록 했다.
- Pipeline·History·Project 공개 DTO와 Frontend parser를 allowlist로 제한하고 Result 전체 품질 요약, History·Project 간결 상태, 구형·partial·failed fallback을 추가했다.
- mono/stereo·sine·silence·clipping·short·invalid fixture, LUFS reference, Pipeline 완료 경쟁·실패·Retry·DTO, Frontend·Desktop/Mobile E2E와 30/60초 성능을 검증해 K3.1을 `[완료]`로 갱신했다.
- DB Migration·Provider 변경 없이 K3.1에서는 K3.2 Tempo, K3.3 Hook/Chorus Candidate, K3.4 Preview와 True Peak를 구현하지 않았다.
- K3.0 Audio Analysis의 최종 `final.wav` 분석 source, 비차단 Pipeline 성공 경계, versioned Result metadata JSON, 공개 allowlist와 secure Preview 수명주기를 정의했다.
- Quality Metrics·Tempo·Hook Candidate·15초 Preview를 K3.1~K3.4로 분리하고 confidence·실패·Cancel·Retry/Re-analysis·fallback·단계별 DoD를 문서화했다.
- Audio Analysis 라이브러리·ITU-R BS.1770-5·EBU R 128 후보 비교, EVAL-008 검증 계획과 ADR-023을 추가했다. 코드·DTO·DB·의존성은 변경하지 않았고 K3 기능은 `[계획]`으로 유지했다.
- optional `generation_options`에 Preset·목표 BPM·언어 비율·Hook·Post-Chorus·Dance Break·보컬 에너지·Concept strict DTO와 사용자 친화 validation 오류를 추가했다.
- Backend 최종 `KPopPromptCompiler` 결과와 원본·정규화 옵션·compiler version을 기존 JSON Input Snapshot에 저장하고 Retry·History·Project·Result 공개 allowlist에 연결했다.
- Studio에 Preset별 기본 Structured Options, 고급 설정·초기화·즉시 Prompt Preview·Review·Desktop/Mobile History 요약을 추가했다.
- K-POP Lyrics Template이 언어 비율 목표, Hook 문구·방식·반복과 Post-Chorus 포함 여부를 Prompt 목표로 반영하도록 확장했다.
- K2를 `[완료]`로 갱신했으며 DB Migration·Provider 변경 없이 기존 Pipeline 요청과 구형 Snapshot Retry 호환성을 유지했다.
- 실제 BPM 검출·Hook timestamp·15초 Preview·Audio Analysis·LUFS·True Peak·LoRA·Dataset·Voice 학습은 구현하지 않았다.
- Dance·Easy Listening·Performance Preset Registry와 Provider-neutral `KPopPromptCompiler`를 추가하고 사용자 Prompt를 최우선으로 유지했다.
- Studio에서 기본 Dance Preset, Preset 설명과 Prompt Preview를 제공하고 컴파일 결과를 기존 Pipeline DTO의 `prompt`·`genre`로만 전송하도록 연결했다.
- K-POP Lyrics Template에 Intro·Verse·Pre-Chorus·Chorus·Post-Chorus·Bridge·Final Chorus 구조와 저작권·아티스트 모방 방지 규칙을 반영했다.
- K1 Preset MVP의 Backend·Frontend·Desktop·Mobile 회귀 검증을 완료해 `[완료]`로 갱신했다. `generation_options`, API·DB Migration, Provider 전용 제어, BPM·Hook Timestamp·Audio Analysis·LoRA·Dataset은 구현하지 않았다.
- Phase 8 이후 별도 K0~K4 제품 고도화 Track과 K-POP Dance·Easy Listening·Performance Preset 계약을 정의했다.
- Generation Options, `KPopPromptCompiler`, Lyrics Template, Provider Capability Matrix와 capability 기반 Frontend UX 경계를 문서화했다.
- EVAL-007 평가 계획, 권리 중심 Style Dataset 정책, ADR-022를 추가하고 현재 API·DB·Provider·Frontend에는 구현되지 않았음을 명시했다.

### Phase 2 Listening Evaluation

- Phase 2 사용자 청취 평가 점수와 근거를 EVAL-001에 반영하고, 동일 PCM 산출물의 중복 집계를 제거했으며 미평가 2건을 남긴 채 ACE-Step을 조건부 채택으로 기록했다.
- README·Master Roadmap·실행 Roadmap·ADR-006·Phase-02 DoD에서 조건부 채택, 기본 Provider `mock`, 운영 Provider 미확정, 사용자 평가 진행 중 상태를 동기화했다.
- Phase 2 대표 평가를 Korean Dance Pop으로 정하고 Instrumental·Korean Ballad를 보조 비교군으로 유지했으며, Dance Pop 평가 기준·Prompt·Hook 가사·0.6B LM 후속 실험 계획과 Phase 7 이후 LoRA·권리 확보 데이터 방향을 문서화했다.

### Phase 6.6~6.9 — Local Lyrics LLM

#### 문서

- 공개 Instruct Base Model과 권리 확보 Lyrics Dataset의 QLoRA SFT, LoRA Adapter·병합 모델 산출물, `LocalLyricsLLMAdapter` 목표 구조를 정의했다.
- Dataset Policy, Model Card template, ADR-016과 Dataset → Fine-tuning → Provider Integration → Quality Gate Roadmap을 추가했다.
- Base 미선정·Dataset 미구축·학습 미착수·checkpoint 없음·Adapter 미구현·평가 미실시·운영 미승인 상태를 명시했다.
- OpenAI API Experimental 비교군, FastAPI OpenAPI 명세, Planned Local Lyrics LLM을 구분하고 Frontend Provider-neutral 원칙을 보강했다.

### Phase 8 — Doha Studio Frontend MVP

- `POST /api/pipelines/{job_id}/cancel`과 `retry`를 추가하고 `CANCEL_REQUESTED` 단계 경계 cooperative 취소, 입력 Snapshot·원본 self FK 기반 새 Job Retry를 구현했다.
- 취소·재시도 상태와 가능 action을 Pipeline·History·Project 공개 DTO와 일반 사용자용 Generation·History UX에 연결했다.
- Alembic 0009, Backend·Frontend·Desktop/Mobile E2E와 ADR-021을 추가하고 로컬 단일 사용자 Phase 8을 `15/15, 100%`로 완료했다.

- 기술 중심의 화면 문구를 일반 사용자 중심의 한국어 창작 흐름으로 개편하고 장르·분위기·길이 선택, 단계별 도움말, 첫 방문 안내와 비활성 사유를 추가했다.
- `NEXT_PUBLIC_ENABLE_DEVELOPER_INFO` 플래그로 내부 연결·생성 방식 정보를 기본 화면에서 분리하고, 사용자 친화적 오류·로딩·빈 상태와 키보드 포커스 동작을 보강했다.
- 기존 API 계약과 Backend 동작, Phase 8 `14/15, 93%` 진행률은 변경하지 않았다.

- History 최신순·검색·상태·페이지네이션·상세 API와 Project CRUD·Default Project 자동 연결을 추가했다.
- Project 삭제 시 Pipeline Job·결과 파일을 보존하고 연결만 해제하는 migration과 ADR-020을 추가했다.
- `/history`, `/projects`, `/projects/[id]` 화면, Zustand Store, Result 재진입·Player·Download 연결을 추가하고 Phase 8을 `14/15, 93%`로 갱신했다.

- consent 필수 WAV multipart Voice Profile upload와 list/get API, 25MB·5~60초·16kHz·mono/stereo·16-bit PCM·signature/decode 검증을 추가했다.
- 업로드를 UUID 기반 안전 경로에 atomic 저장하고 실패 temp cleanup, 사용 중 삭제 차단과 관리 파일 삭제 정책을 구현했다.
- Voice 페이지와 Studio 단계에 Profile 등록·목록·warning·선택·삭제 UX를 연결하고 개발 경로 입력은 기본 비노출로 유지했다.
- Voice metadata migration과 ADR-019를 추가하고 Phase 8 Upload DoD 완료에 따라 진행률을 `11/15, 73%`로 갱신했다.

- 완료 Pipeline의 허용된 WAV에 경로 비노출 `GET|HEAD content`·`download` API와 단일 byte Range `206/416` 처리를 추가했다.
- Job/File 소속·완료 상태·Storage root·symlink·regular file·크기·MIME·확장자·RIFF header 검증 및 `no-store`·`nosniff` 응답 경계를 적용했다.
- 공개 files DTO의 capability URL을 전역 Player·seek·volume·Result 다운로드에 연결하고 unavailable·loading·오류 상태를 구현했다.
- Phase 8 Audio Player와 WAV Download DoD를 완료해 진행률을 `10/15, 67%`로 갱신하고 ADR-018에 로컬 단일 사용자 경계와 운영 승격 조건을 기록했다.

- 공개 Generation·Stem·Voice Conversion·Pipeline file DTO와 Voice Profile 응답에서 내부 `file_path`·`reference_file_path`를 제거하고 content·download 가능 여부만 명시하도록 보안 경계를 강화했다.
- Voice 서버 참조 경로 입력을 기본 비노출 개발 플래그로 제한하고 Backend에서 Storage root·파일 존재·확장자·traversal·절대 경로·symlink를 검증한다.
- API Client가 `INVALID_RESPONSE`, `REQUEST_TIMEOUT`, `REQUEST_ABORTED`, `NETWORK_ERROR`, HTTP·Backend 오류 코드를 구분하고 caller signal과 timeout signal을 보존하도록 개선했다.
- Pipeline polling에 연속 오류 5초·10초 backoff, 404·terminal 중단, hidden 최소 5초와 수동 재조회를 적용했다.
- Lyrics revision UI를 Backend capability로 제어하고, 결과 metadata allowlist·local Settings persist·Studio step 분리·역할별 CSS 구조를 적용했다.
- 취약 transitive dependency 수정 버전을 lockfile override로 고정해 `npm audit` 0건을 확인했다.

#### 추가

- Next.js 16 App Router·TypeScript 기반 `frontend/`와 npm lockfile, Premium Dark responsive Landing·Studio·Lyrics·Voice·Progress·Result·Settings·About·404 화면을 추가했다.
- Zustand session draft, TanStack Query server state, React Hook Form·Zod form, 공통 API client·안전한 오류 정규화·DTO mapper를 추가했다.
- Health·Lyrics 생성/검증/수정/삭제·Voice Profile 생성/삭제·Pipeline 생성/조회/files metadata를 실제 FastAPI 계약에 연결했다.
- 초기 5회 1초·foreground 2초·background 5초 polling과 terminal 중단, URL 복원, network/Job 실패 분리를 구현했다.
- Vitest·React Testing Library 12건과 Playwright Chromium Desktop·Mobile E2E 4건을 추가했다.

#### 변경

- ADR-017을 npm·Next.js 16·CSS token·Zustand·TanStack Query·React Hook Form·Zod·Lucide·Vitest·Playwright 조합으로 승인했다.
- Phase 8을 `[진행 중] 53%`로 갱신하고 F0~F3 완료, F4 부분 완료, F5 계획 상태로 구분했다.
- Voice upload/list/get, History·Project, cancel/retry, 인증·소유권·모델 목록·Playlist는 Backend API 전까지 disabled 또는 미구현 상태를 유지한다.

#### 검증

- Lint·Type Check·unit/component test·production build·Desktop/Mobile E2E를 통과했고 FastAPI와 same-origin proxy의 `/health` 응답을 확인했다.

### Phase 8 — Doha Studio Frontend Design

#### 문서

- 첨부된 Vinyl Music Dashboard를 기준으로 Premium Dark Music Studio의 Frontend Overview, Architecture, Design System, Atomic Component, Responsive, Studio UX, Navigation과 Page Structure를 설계했다.
- Desktop 3-column workspace, Tablet drawer, Mobile bottom navigation·step flow와 Player·Waveform·motion·접근성 기준을 정의했다.
- 현재 FastAPI endpoint별 page·request·response·loading·error·retry·polling 흐름과 upload/download·history·cancel/retry·인증 등 미구현 API gap을 구분했다.
- Phase 8 상태는 Frontend 코드 미구현에 따라 `[계획] 0%`로 유지하고 구현 순서를 Frontend Roadmap으로 정리했다.
- Pipeline 요청에 없는 `instrumental`을 Music Settings 활성 필드에서 제거하고 `planned/disabled`로 정정했다.
- F0 OpenAPI 계약 검토 대상·필드·응답·오류·DTO·완료 기준과 `Available`·`Partial`·`Backend Required`·`Planned` 지원 범위를 정의했다.
- Responsive Web과 Native/PWA 범위를 분리하고 디자인 레퍼런스 사용 정책과 `[검토 필요]` ADR-017 기술 스택 비교 초안을 추가했다.

### Phase 6.5 — External Lyrics LLM Provider

#### 추가

- OpenAI Responses API `gpt-5-mini-2025-08-07` Experimental Lyrics Adapter, strict JSON Schema mapper, Provider Factory와 opt-in paid integration test를 추가했다.
- `POST /api/lyrics/{id}/revise`, 원본 보존 parent/version·수정 지시·전후 SHA-256, Alembic 0006을 추가했다.
- retry·5초 deadline·안전한 오류 변환·명시적 Template fallback·token/예상 비용 metadata를 추가했다.

#### 변경

- 기본 Provider는 `template`로 유지하고 외부 Provider를 명시 선택했을 때만 API Key를 요구한다.
- `httpx`를 실제 Adapter runtime 의존성으로 이동했다.

#### 보안

- 외부 전송 필드를 가사 입력으로 제한하고 `store=false`, 비밀·ID·경로·음성 제외, 원문 Provider 오류 비노출 정책을 적용했다.

#### 문서

- Provider 공식 비교, 선정 정책, 데이터·운영 정책, ADR-015, EXP-008, EVAL-006과 API·DB·Architecture·DoD를 최신화했다. 외부 실측은 API Key 부재로 `[차단]`이다.

### 추가

- `LyricsGenerator` 인터페이스와 외부 통신 없는 `TemplateLyricsGenerator`, 테스트용 `MockLyricsGenerator`, `template`·`mock` Provider Factory를 추가했다.
- 한국어·영어 구조화 가사 생성, 섹션 파싱, 길이·반복·구조 검증, 생성·검증 metadata를 추가했다.
- 동기식 가사 생성·조회·검증·삭제 API, `lyrics_documents`, Alembic 0005를 추가했다.
- Lyrics benchmark, EXP-007, 사용자 EVAL-005, ADR-014와 Provider·API·검증·오류 회귀 테스트를 추가했다.

- `AudioMixer` 인터페이스, 실제 NumPy/SciPy 기반 `DefaultAudioMixer`, 유지되는 `MockAudioMixer`와 `default`·`mock` Provider Factory를 추가했다.
- gain, 48kHz Stereo 동기화, length padding, -1dBFS headroom, peak normalization, soft limiter, fade와 PCM16 WAV 출력을 추가했다.
- peak·RMS·headroom·clipping·처리 시간·CPU·RSS·출력 크기 metadata, Mixer benchmark, EXP-006, 사용자 EVAL-004와 ADR-013을 추가했다.
- gain·headroom·clipping·fade·metadata·format sync·Provider·Pipeline 연결 테스트를 추가했다.

- `PipelineService`, `PipelineContext`, `PipelineExecutor`, 5개 `PipelineStep`과 Mock Mixer·WAV Exporter를 추가했다.
- `pipeline_jobs`, `pipeline_files`, Alembic 0004와 비동기 Pipeline 생성·조회·파일 API를 추가했다.
- 단계별 진행률, 자동 재시도, timeout 판정, 구조화 오류, 부분 출력 정리와 JSON metadata를 추가했다.
- 재현 가능한 Mock benchmark 실행기, EXP-005, ADR-012와 성공·Music/Stem/Voice 실패·재시도·timeout 테스트를 추가했다.

- Seed-VC, OpenVoice, CosyVoice, Fish Speech, RVC, Amphion Vevo2의 공식 근거 비교표와 100점 Provider Score를 추가했다.
- Primary 미선정, RVC Secondary 평가 후보, Seed-VC·Vevo2 Experimental 결정을 기록한 ADR-011을 추가했다.

- Voice Provider 수명주기와 승격 조건을 정의한 ADR-010, Provider 정책, Voice Conversion 운영 준비도 QG-001을 추가했다.

- `VoiceConverter`, `MockVoiceConverter`, 격리형 `SeedVCAdapter`와 `mock`·`seed_vc` Provider Factory를 추가했다.
- 비동기 Voice Conversion API, `voice_conversion_jobs/files`, `VOICE_CONVERTING`, Alembic migration을 추가했다.
- Seed-VC 44k F0 runner, 3회 GPU Benchmark, opt-in GPU 통합 테스트와 48kHz stereo PCM16 자동 검증을 추가했다.
- EXP-004, 사용자 EVAL-003 양식, Seed-VC 검증 Provider 결정을 기록한 ADR-009를 추가했다.

- 프로젝트 전체 Phase·실제 진행률·선행 조건·산출물·다음 작업을 관리하는 `MASTER_ROADMAP.md`를 추가했다.
- Phase 1~9의 완료 판정과 공통 Git·문서 게이트를 관리하는 `docs/DoD/` 문서 체계를 추가했다.

- `StemSeparator` 인터페이스, `MockStemSeparator`, 격리형 `DemucsAdapter`, `mock`·`demucs` Provider Factory를 추가했다.
- 비동기 Stem 생성·조회·파일 조회 API와 `stem_jobs`, `stem_files`, `STEM_SEPARATING` 상태를 추가했다.
- HTDemucs 오프라인 단독 실행기, 3회 Benchmark, opt-in GPU Backend E2E 및 자동 오디오 검증을 추가했다.
- EXP-003, EVAL-002, Stem Provider·2-stem·48kHz Stereo float32 결정을 기록한 ADR-008을 추가했다.

- ACE-Step 동일·다른 Seed, 상주 반복, 0.6B LM을 명시 실행하는 benchmark suite와 결과 집계·WAV sample 비교 도구를 추가했다.
- 실제 음원을 사용자가 직접 평가하는 EVAL-001과 재현성·안정성·운영 결정을 기록한 EXP-002를 추가했다.
- ACE-Step 기본 Provider 채택 보류 ADR-006과 Job별 subprocess 유지 ADR-007을 추가했다.
- ACE-Step 1.5 v0.1.8을 격리된 런타임에서 실행하는 선택적 Adapter, Provider Factory, 오류 체계를 추가했다.
- 단독 instrumental·한국어 가사 smoke 실행기, 고정 benchmark 입력, WAV 신호 분석기와 opt-in GPU 통합 테스트를 추가했다.
- RTX 3060 Ti 8GB 실측과 Backend 종단 간 연결 결과를 기록한 `EXP-001` 보고서를 추가했다.
- FastAPI Router·Service·Repository 계층과 교체 가능한 의존성으로 Backend Foundation을 구축했다.
- SQLite·SQLAlchemy·Alembic 기반 `generation_jobs`, `generated_files`, `voice_profiles` schema를 추가했다.
- Mock `MusicGenerator`, ThreadPool Worker, 로컬 Storage와 생성·조회·음성 프로필 API를 추가했다.
- 생성 성공·조회·Mock Worker 실패·입력 예외·음성 동의·migration·Storage를 검증하는 테스트를 추가했다.

### 변경

- Phase 6을 로컬 Template·Mock 기반 완료로 갱신하고, 실제 LLM 도입과 Pipeline 자동 연결은 별도 검토로 유지했다.

- Pipeline Mixer 기본값을 Mock 복사에서 실제 `DefaultAudioMixer`로 교체하고 Mock AI 단계와 Orchestrator 구조는 유지했다.
- `numpy`, `scipy`, `psutil`을 Backend DSP·resampling·resource 측정 의존성으로 추가했다.

- 공유 단일 ThreadPool에 Pipeline Worker를 연결하고 애플리케이션 종료 시 SQLAlchemy Engine을 명시적으로 dispose하도록 변경했다.
- Phase 5를 Mock Voice 기반 기술 Orchestrator 완료로 갱신하되 Primary Voice와 실제 Mixer의 운영 게이트는 유지했다.

- Voice Provider Matrix를 `Primary 미선정 → Fallback 미선정 → Experimental → Mock`으로 정리하고 Experimental의 자동 fallback 참여를 금지했다.
- Phase 4를 Provider 평가 완료·Primary 미선정인 `[검증 필요]` 94%로 유지하고 Phase 5 착수를 계속 보류했다.

- Seed-VC를 `Experimental`·운영 보류로 확정하고 기본 Provider `mock`을 유지했다.
- Phase 4는 EVAL-003과 clipping·라이선스 해제 조건이 남아 `[검증 필요]` 94%로 유지하고 Phase 5 착수를 보류했다.

- 생성·Stem·Voice Worker가 동일한 GPU 동시성 1 executor를 공유하도록 확장했다.
- Phase 4를 기술 구현 완료·사용자 품질 평가 대기인 `[검증 필요]` 94%로 갱신했다.

- 새 기능 작업은 Master Roadmap, 해당 Phase DoD, AGENTS 지침 순으로 확인하고 완료 후 진행률·DoD·README·ROADMAP·CHANGELOG를 함께 갱신하도록 운영 규칙을 확장했다.

- AI 작업은 생성 Worker와 Stem Worker가 GPU 동시성 1인 공유 ThreadPool을 사용하도록 조립했다.
- 개발 상태를 Phase 3 Stem Separation 기술 검증 완료·사용자 청취 평가 대기로 갱신했다.

- 반복 실험 결과에 따라 현재 ACE-Step 운영 방식을 Job별 격리 subprocess로 확정하고 Mock 기본 Provider를 유지했다.
- 개발 단계를 Phase 2.5 기술 검증 완료·사용자 청취 평가 진행 중으로 갱신했다.
- `MusicGenerator` 결과 계약에 Provider·모델 버전·실제 Seed·추론 시간·최대 VRAM·메타데이터를 포함했다.
- Mock 전용 Worker를 Provider-neutral Worker로 확장하고 설정으로 `mock` 또는 `ace_step`을 선택하도록 변경했다.
- 개발 단계를 Phase 2 진행 중으로 갱신하고 기술 검증과 수동 청취 평가 상태를 분리했다.

### 수정

- 전체 Python 소스를 현재 Ruff 규칙에 맞게 정리하고, AI subprocess 경계의 의도적인 catch-all 예외 처리 사유를 명시했다.

### 제거

### 보안

- 가사 요청의 입력 개수·길이 상한, HTML·script·control 문자 제거, 구조화 오류 응답과 원문 전체를 남기지 않는 로그 정책을 적용했다.

- 신규 Voice Provider 검증 전에 checkpoint 출처·hash·역직렬화·원격 코드·의존성 lock과 학습 산출물 삭제 정책을 확인하도록 공급망 통제를 보강했다.

- Seed-VC 상용 SaaS와 Docker·온프레미스 외부 배포는 배포 단위별 GPL 준수 목록과 법률 검토 전까지 보류하도록 명시했다.

- Voice Conversion 입력을 DB의 vocals Stem과 명시적 동의 Voice Profile로 제한하고 참조 경로가 `voices/references` 밖으로 벗어나면 거부한다.

### 문서

- README, Master Roadmap, ROADMAP, DoD, Architecture, API, Database, Evaluation, Operations, Security 문서를 Phase 6 구현과 외부 LLM 보류 상태에 맞게 갱신했다.

- README, Master Roadmap, ROADMAP, Pipeline·Architecture·API·Evaluation·Operations·라이선스·Phase 5 DoD를 실제 Audio Mixer 기준으로 최신화했다.

- README, Master Roadmap, ROADMAP, Architecture, API, ERD, 상태, Evaluation, Operations, Security와 Phase 5 DoD를 실제 Pipeline 구현에 맞게 최신화했다.

- README, Master Roadmap, ROADMAP, Voice Model, Architecture, Operations, Security와 ADR 목록을 Phase 4.6 선정 결과에 맞게 최신화했다.

- EXP-004 기존 결과를 재실험 없이 재집계해 시간·VRAM·RMS·peak·파일 크기·hash와 clipping 원인·미확정 경계를 기록했다.
- EVAL-003의 사용자 평가표·체크리스트·기준을 보강하고 점수와 최종 청취 판정은 비워 두었다.
- README, Master Roadmap, ROADMAP, Model, Evaluation, Operations, Security와 ADR을 Phase 4.5 운영 품질 게이트 결정에 맞게 최신화했다.

- Seed-VC·OpenVoice·CosyVoice·Fish Speech의 공식 용도와 라이선스, archive 위험, RTX 3060 Ti 실측을 연구·모델·Architecture·API·DB·평가·운영 문서에 반영했다.

- README와 ROADMAP을 Master Roadmap·DoD에 연결하고 기존 Phase 4 이후 명칭을 Voice Conversion → Pipeline → Lyrics AI → Doha Voice → Doha Studio → Production 체계로 통합했다.

- Demucs·HTDemucs·MDX-Net·Open-Unmix 비교, Demucs 코드·가중치 MIT 확인, RTX 3060 Ti 실측을 조사·모델·Architecture·API·DB·평가·운영 문서에 반영했다.

- 동일 Seed PCM 재현성, 다른 Seed 파형 차이, 상주 CPU 메모리 증가, 0.6B LM 성능과 사용자 평가 상태를 관련 모델·아키텍처·운영 문서에 반영했다.
- ACE-Step 공식 출처·라이선스·격리 설치·저 VRAM 설정·성능·평가·오류·운영 문서와 ADR-005를 최신화했다.
- DohaMusic 초기 설계, 요구사항, 아키텍처, 데이터, API, 평가, 보안, 운영 문서 체계
- 단계별 계획과 실험 보고서 템플릿
- 저장소 전체에 적용되는 Codex Git 작업 지침과 문서 최신화·변경 이력 관리 규칙
- 장기 유지보수를 위한 구현 전 분석, 재사용, Adapter, 비동기 작업, 테스트·로그·성능 기록과 코드 품질 원칙
- README, Backend·Worker·Storage Architecture, API, ERD, 상태 모델과 로컬 운영 문서를 실제 Mock 구현에 맞게 갱신했다.
- ADR-002의 Adapter 경계와 ADR-003의 Phase 1 비동기 처리 결정을 구현 기준으로 검토·승인했다.
