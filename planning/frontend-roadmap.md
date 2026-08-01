# Doha Studio Frontend Roadmap

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-01
> 관련 Phase: Phase 8 Doha Studio, Phase 8 후속 F6 Guided Voice Enrollment
> 관련 문서: [Frontend Overview](../docs/03-architecture/frontend-overview.md), [Frontend Architecture](../docs/03-architecture/frontend-architecture.md), [Voice Enrollment 요구사항](../docs/02-requirements/voice-enrollment-requirements.md), [Voice Enrollment API](../docs/06-api/voice-enrollment-api.md), [Voice Enrollment 데이터 모델](../docs/07-database/voice-enrollment-data-model.md), [Phase-08 DoD](../docs/DoD/Phase-08.md)

## 목표

Premium AI Music Studio 설계를 실제 Frontend로 단계적으로 전환한다. F0~F5의 로컬 MVP는 완료됐고, 사용자 안내형 Voice Enrollment는 기존 완료 범위를 소급 변경하지 않는 F6 후속 Track으로 관리한다.

## 사용자 중심 UX 기준

- 기본 탐색과 단계명은 한국어 창작 용어를 사용하고 내부 기술명은 기본 화면에서 숨긴다.
- 첫 방문 안내, 단계별 도움말, loading·empty·error·disabled 이유를 제공한다.
- Dance Pop 추천 장르와 분위기 최대 3개, 30초·60초 길이 선택을 제공한다.
- 긴 곡·Hook·Preview 등 미지원 기능은 가짜 요청을 보내지 않고 `준비 중` 사유를 표시한다.
- 사용자 중심 UX 이후 Cancel·Retry API와 화면을 연결해 Phase 8 `15/15, 100%`를 완료했다.

## F0 — Frontend Contract Verification [완료]

### 목적

- 문서 예시가 아니라 실행 중인 FastAPI의 `/openapi.json`을 기준으로 Frontend 계약을 확정한다.
- Request·Response·Error·Job Status 필드명을 구현 전에 고정한다.
- 현재 지원 기능과 Backend 선행 기능을 분리하고 UI 활성 상태를 결정한다.
- 계약 미확정 상태에서 실제 Frontend 구현을 시작하지 않는다.

### 검토 대상 Endpoint

| 영역 | Endpoint |
|---|---|
| Health | `GET /health` |
| Lyrics | `POST /api/lyrics`, `GET /api/lyrics/{id}`, `POST /api/lyrics/{id}/revise`, `POST /api/lyrics/validate`, `DELETE /api/lyrics/{id}` |
| Voice Profile | path create·WAV upload·list·get·delete |
| Generation | `POST /api/generations`, `GET /api/generations/{id}`, `GET /api/generations/{id}/files` |
| Stem | `POST /api/stems`, `GET /api/stems/{job}`, `GET /api/stems/{job}/files` |
| Voice Conversion | `POST /api/voice-conversion`, `GET /api/voice-conversion/{job}`, `GET /api/voice-conversion/{job}/files` |
| Pipeline | `POST /api/pipelines`, `GET /api/pipelines/{job}`, `GET /api/pipelines/{job}/files` |

### 반드시 확정할 계약

- 실제 request 필드명과 required·optional 여부
- 문자열 길이, 숫자 범위, enum과 UUID 형식
- Job status·`current_step` 값, progress 필드명·타입·범위
- `{ "error": { "code", "message" } }` 오류 구조와 Provider별 안정 코드
- files metadata와 Pipeline `result_metadata` 구조
- Lyrics section 구조와 `full_text` 존재 여부
- Voice Profile 생성 요청 schema와 동의 필드
- `202 Accepted`, `201 Created`, `204 No Content` 처리
- `404`, `422`, Provider 오류와 network 오류의 UI 분리

### 산출물

- `/openapi.json` 기준 endpoint별 API 계약표
- 문서 예시와 실제 schema 차이 목록
- OpenAPI 생성 또는 수동 정의를 포함한 Frontend DTO 작성 기준
- `Available`, `Partial`, `Backend Required`, `Planned` UI 기능 목록
- Backend gap과 담당 Phase·승인 상태
- [ADR-017](../docs/11-decisions/ADR-017-frontend-technology-stack.md)의 기술 스택 결정

### 완료 기준

- 모든 검토 endpoint의 request·response·status·error 표 작성
- 문서와 OpenAPI 불일치가 해결 또는 명시적으로 보류됨
- Frontend DTO 생성·검증·버전 고정 기준 승인
- 활성·비활성 UI 기능 목록과 Backend gap 재확인
- API 계약과 기술 스택이 미확정이면 F1 구현 착수 금지

## F1 — Foundation [완료]

- Next.js App Router, TypeScript, quality gate, token/theme, App shell
- Button/Input/Card/Modal/Drawer/Toast/Progress primitives
- 접근성·responsive test baseline
- 완료 기준: lint·type·build와 token/component 문서 일치

## F2 — Studio Draft [완료]

- Desktop 3-column, Tablet drawer, Mobile step navigation
- Music Settings, Lyrics draft/validation, Voice metadata, Review
- draft 복원과 입력 오류
- 완료 기준: API 호출 전 사용자 flow와 responsive 상태 검증

## F3 — API Integration [완료]

- Health, Lyrics, Voice Profile, Pipeline client
- Timeout·abort·network·invalid response 오류 정규화, 연속 오류 backoff polling, reconnect, URL 복원
- 현재 미지원 action의 disabled/empty state
- 완료 기준: Mock Backend 기준 생성 → status → result metadata E2E

## F4 — Music Experience [완료]

- Vinyl artwork, waveform, transport, result inspector, motion
- Pipeline capability URL 기반 전역 player/download 연결
- reduced motion, keyboard, screen reader 검증
- 완료 기준: endpoint 없는 가짜 재생 0건, 실제 media 계약 E2E

## F5 — Projects·Local MVP Completion [완료]

- Pipeline audio, Voice Profile upload/list/get, History·Project CRUD, Cancel·Retry API 연동 완료
- observability, browser matrix, performance, security review
- 완료 기준: Phase-08 DoD와 사용자 시나리오 승인

## F6 — Guided Voice Enrollment [진행 중]

### 목적과 경계

단일 WAV form인 `/voice`를 사용자가 안내에 따라 본인 참조 음성을 준비하는 Wizard로 개선한다. F6는 Phase 8의 후속 Studio UX이며 기존 Phase 8 `15/15, 100%`를 변경하지 않는다. 장시간 Dataset 수집·전사·split·preprocessing·LoRA·Fine Tuning은 Phase 7 범위로 분리한다.

Backend는 기존 단일 WAV API와 함께 Enrollment 7개 endpoint, WAV/WebM/Ogg 입력, 최대 10개 sample, PCM16 48kHz mono 정규화, 기본 품질 검사, Profile 승격, 멱등성과 lazy expiration을 지원한다. Frontend는 8단계 Wizard, MediaRecorder·입력 수준·preview, 다중 파일 업로드, 품질·대표 선택, session 복원·취소·만료와 Studio 선택을 연결했다. WebM/Ogg는 optional FFmpeg가 없으면 안전한 unavailable 오류를 반환하며 upload resume, 주기적 cleanup scanner와 동의 철회는 지원하지 않는다.

### 구현 선행 결정

- `[제안]` [ADR-024](../docs/11-decisions/ADR-024-browser-voice-recording-server-normalization.md): Backend decode·PCM16 48kHz mono WAV 정규화, decoder·resource limit과 품질 검사 경계
- `[제안]` [ADR-025](../docs/11-decisions/ADR-025-voice-profile-multiple-samples-reference.md): Profile 1:N Sample, 사용자가 확정한 대표 reference와 legacy backfill
- `[제안]` [ADR-026](../docs/11-decisions/ADR-026-voice-enrollment-lifecycle-cleanup.md): 별도 임시 Storage, 24시간 sliding/7일 absolute 만료, idempotency·cleanup retry
- `[Backend 확장 필요]` sample별 metadata·품질, 사전 validation, 전체 duration과 Profile 설명
- `[Phase 9 선행]` 공개 운영 인증·소유권·동의 철회·감사·rate limit

### 완료 체크리스트

- [x] Voice Enrollment 요구사항 확정 — Backend 계약 구현, Frontend 기능은 미구현
- [x] 녹음 MIME과 WAV 정규화 Backend 구현 — 실제 FFmpeg 통합·고정 build 검증은 후속
- [x] 단일 reference와 다중 sample 영속 모델 — migration·legacy backfill·Repository 검증 완료
- [x] 임시 Enrollment·API·lazy 만료·즉시 cleanup primitive 구현 — scheduler는 미구현
- [x] 안내 문장과 녹음 정책 검증 — 자체 문장·5~60초·WAV fallback과 품질 한계 표시
- [x] 브라우저 녹음 UI — feature detection·권한·시작/일시정지/재개/종료·입력 수준·preview·cleanup
- [x] 기존 파일 upload Wizard 연결 — WAV 우선, WebM/Ogg 안전 오류, 최대 10개와 파일별 재시도
- [x] 기본 품질 검사와 사용자 메시지 — PASS/WARNING/FAIL, warning 명시 확인, 내부 오류 비노출
- [x] Voice Profile 등록·Studio 선택 연결 — 대표 Sample submit 후 목록 invalidate·신규 Profile 선택
- [x] 오류·재시도·취소·cleanup — 동일 key 재시도, session 복원, 만료·not found·cleanup 상태 UX
- [x] 접근성·반응형 — 단계 focus·aria-current/live/meter/radio, Desktop·Pixel 7 E2E
- [x] Frontend unit·component·E2E — Vitest 95개와 전체 Playwright 24개 통과
- [x] Backend API·Audio·Storage·migration·기존 Voice 회귀 자동 test
- [x] 보안·동의·API·DB 문서 — Frontend 구현 사실과 미구현 경계를 갱신
- [x] CHANGELOG
- [ ] 한국어 커밋·Push·`develop` PR·병합 검증

### 예상 산출물과 완료 기준

- 요구사항·후속 ADR·API/DB 계약, Wizard·녹음·품질 UI, Backend 확장, 자동 test와 사용자 수동 녹음 평가
- 지원하지 않는 MIME·상태·품질을 사실처럼 표시하지 않고 내부 경로·음성 binary를 브라우저 저장소에 남기지 않는다.
- 체크리스트의 구현·검증·문서·Git 항목을 실제 증거로 완료해야 F6를 `[완료]`로 변경한다.

## 우선순위와 보류

F0~F5는 로컬 단일 사용자 범위에서 완료됐다. F6 Backend는 구현됐지만 Frontend Wizard·MediaRecorder와 주기적 cleanup은 남아 있어 `[진행 중]`이다. 공개 DTO는 내부 Storage 경로를 반환하지 않는다. `main` 배포와 Production 공개는 인증·소유권·감사 로그·분산 Queue를 다루는 Phase 9 승인 전까지 보류한다.

Frontend shared mapper와 Result metadata allowlist는 루트 `lib/` ignore 규칙으로 누락됐던 파일을 기존 계약에 맞춰 복구했다. 이 복구는 Phase 8 기능·상태를 바꾸지 않고 typecheck·build·Vitest·Playwright 기준선과 후속 K1 검증 차단을 해소한다.

K1 `[완료]`에서는 K-POP Preset·Prompt Preview를 Studio에 연결하고 Dance·Easy Listening·Performance 선택을 Provider-neutral Prompt와 기존 `genre`로 컴파일했다. 당시 Generation Options는 전송하지 않았고 BPM·언어 비율·Hook·Dance Break를 작동하는 제어로 노출하지 않았다.

K2 `[완료]`에서 typed Structured Options Store, Preset별 기본값, Custom 값 보존·초기화, client validation, 즉시 Preview, snake_case Pipeline mapping과 History·Project·Result 설정 요약을 연결했다. Backend Compiler와 validation이 최종 권위이며 화면은 BPM·Hook·구조 옵션을 실제 분석·정밀 제어로 표현하지 않는다.

K3.1·K3.2·K3.3 `[완료]`에서 공개 Audio Analysis를 camelCase view model로 엄격히 파싱한다. Result는 Quality·예상 Tempo·후렴 후보 추정 구간 상세, History는 Tempo 상태와 Hook 후보 유무만, Project는 예상 Tempo와 Hook 후보 요약을 표시한다. confidence는 High/Medium/Low/Unavailable 경계를 사용하고 실패·부분 완료·구형 결과 fallback 및 Desktop/Mobile E2E를 유지한다. K3.4 Preview Export는 `[계획]`이다.
