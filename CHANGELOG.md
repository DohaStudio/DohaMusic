# 변경 이력

> 문서 목적: 사용자와 개발자에게 의미 있는 저장소 변경을 기록한다.
> 현재 상태: **운영 중**
> 최종 수정일: 2026-07-31

DohaMusic 프로젝트의 주요 변경 사항을 기록한다. 일반 작업은 `[Unreleased]`에 기록하고 프로젝트 버전 정책은 구현 단계에서 결정한다.

## [Unreleased]

### 문서

- Phase 2 사용자 청취 평가 점수와 근거를 EVAL-001에 반영하고, 미평가 2건을 남긴 채 ACE-Step을 조건부 채택으로 기록했다.

### Phase 6.6~6.9 — Local Lyrics LLM

#### 문서

- 공개 Instruct Base Model과 권리 확보 Lyrics Dataset의 QLoRA SFT, LoRA Adapter·병합 모델 산출물, `LocalLyricsLLMAdapter` 목표 구조를 정의했다.
- Dataset Policy, Model Card template, ADR-016과 Dataset → Fine-tuning → Provider Integration → Quality Gate Roadmap을 추가했다.
- Base 미선정·Dataset 미구축·학습 미착수·checkpoint 없음·Adapter 미구현·평가 미실시·운영 미승인 상태를 명시했다.
- OpenAI API Experimental 비교군, FastAPI OpenAPI 명세, Planned Local Lyrics LLM을 구분하고 Frontend Provider-neutral 원칙을 보강했다.

### Phase 8 — Doha Studio Frontend MVP

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
