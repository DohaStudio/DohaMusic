# Doha Studio Frontend Roadmap

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-01
> 관련 Phase: Phase 8 Doha Studio, Phase 8 후속 F6 Guided Voice Enrollment
> 관련 문서: [Frontend Overview](../docs/03-architecture/frontend-overview.md), [Frontend Architecture](../docs/03-architecture/frontend-architecture.md), [Voice Enrollment 요구사항](../docs/02-requirements/voice-enrollment-requirements.md), [Phase-08 DoD](../docs/DoD/Phase-08.md)

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

## F6 — Guided Voice Enrollment [계획]

### 목적과 경계

단일 WAV form인 `/voice`를 사용자가 안내에 따라 본인 참조 음성을 준비하는 Wizard로 개선한다. F6는 Phase 8의 후속 Studio UX이며 기존 Phase 8 `15/15, 100%`를 변경하지 않는다. 장시간 Dataset 수집·전사·split·preprocessing·LoRA·Fine Tuning은 Phase 7 범위로 분리한다.

현재 Backend는 단일 25MB 이하, 5~60초, PCM16 WAV upload와 Profile 즉시 생성을 지원한다. MediaRecorder WebM/Ogg, 다중 sample, 사전 validation, Enrollment 임시 상태, upload 취소·resume와 동의 철회는 지원하지 않는다. 세부 사실과 대안은 [Voice Enrollment 요구사항](../docs/02-requirements/voice-enrollment-requirements.md)을 따른다.

### 구현 선행 결정

- `[ADR 필요]` MediaRecorder MIME을 WAV로 정규화하는 위치와 decoder·resource limit
- `[ADR 필요]` 단일 reference와 다중 sample 데이터 모델
- `[ADR 필요]` client/API/Worker 품질 검사 경계
- `[ADR 필요]` 임시 upload·취소·만료·orphan cleanup
- `[Backend 확장 필요]` sample별 metadata·품질, 사전 validation, 전체 duration과 Profile 설명
- `[Phase 9 선행]` 공개 운영 인증·소유권·동의 철회·감사·rate limit

### 완료 체크리스트

- [x] Voice Enrollment 요구사항 확정 — 문서 설계 기준선만 완료, 기능은 미구현
- [ ] 녹음 MIME과 WAV 정규화 결정
- [ ] 단일 파일과 다중 sample 데이터 모델 결정
- [ ] 안내 문장과 녹음 정책 검증
- [ ] 브라우저 녹음 UI
- [ ] 기존 파일 upload Wizard 연결
- [ ] 기본 품질 검사와 사용자 메시지
- [ ] Voice Profile 등록·Studio 선택 연결
- [ ] 오류·재시도·취소·cleanup
- [ ] 접근성·반응형
- [ ] Frontend unit·component·E2E
- [ ] Backend 검증 test
- [ ] 보안·동의·API·DB 문서
- [ ] CHANGELOG
- [ ] 한국어 커밋·Push·`develop` PR·병합 검증

### 예상 산출물과 완료 기준

- 요구사항·후속 ADR·API/DB 계약, Wizard·녹음·품질 UI, Backend 확장, 자동 test와 사용자 수동 녹음 평가
- 지원하지 않는 MIME·상태·품질을 사실처럼 표시하지 않고 내부 경로·음성 binary를 브라우저 저장소에 남기지 않는다.
- 체크리스트의 구현·검증·문서·Git 항목을 실제 증거로 완료해야 F6를 `[완료]`로 변경한다.

## 우선순위와 보류

F0~F5는 로컬 단일 사용자 범위에서 구현·자동 검증을 완료했다. F5에서 보안 content/download·전역 Player, Voice upload, History·Project CRUD, cooperative Cancel과 새 Job Retry를 연결했다. F6는 `[계획]`이며 단일 WAV 계약을 유지한 상태에서 선행 ADR·Backend 설계를 먼저 수행한다. 공개 DTO는 내부 Storage 경로를 반환하지 않으며 Project 삭제와 Cancel은 Job 기록을 보존한다. `main` 배포와 Production 공개는 인증·소유권·감사 로그·분산 Queue를 다루는 Phase 9 승인 전까지 보류한다.

Frontend shared mapper와 Result metadata allowlist는 루트 `lib/` ignore 규칙으로 누락됐던 파일을 기존 계약에 맞춰 복구했다. 이 복구는 Phase 8 기능·상태를 바꾸지 않고 typecheck·build·Vitest·Playwright 기준선과 후속 K1 검증 차단을 해소한다.

K1 `[완료]`에서는 K-POP Preset·Prompt Preview를 Studio에 연결하고 Dance·Easy Listening·Performance 선택을 Provider-neutral Prompt와 기존 `genre`로 컴파일했다. 당시 Generation Options는 전송하지 않았고 BPM·언어 비율·Hook·Dance Break를 작동하는 제어로 노출하지 않았다.

K2 `[완료]`에서 typed Structured Options Store, Preset별 기본값, Custom 값 보존·초기화, client validation, 즉시 Preview, snake_case Pipeline mapping과 History·Project·Result 설정 요약을 연결했다. Backend Compiler와 validation이 최종 권위이며 화면은 BPM·Hook·구조 옵션을 실제 분석·정밀 제어로 표현하지 않는다.

K3.1·K3.2·K3.3 `[완료]`에서 공개 Audio Analysis를 camelCase view model로 엄격히 파싱한다. Result는 Quality·예상 Tempo·후렴 후보 추정 구간 상세, History는 Tempo 상태와 Hook 후보 유무만, Project는 예상 Tempo와 Hook 후보 요약을 표시한다. confidence는 High/Medium/Low/Unavailable 경계를 사용하고 실패·부분 완료·구형 결과 fallback 및 Desktop/Mobile E2E를 유지한다. K3.4 Preview Export는 `[계획]`이다.
