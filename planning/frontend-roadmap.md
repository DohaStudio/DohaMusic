# Doha Studio Frontend Roadmap

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 관련 Phase: Phase 8 Doha Studio
> 관련 문서: [Frontend Overview](../docs/03-architecture/frontend-overview.md), [Frontend Architecture](../docs/03-architecture/frontend-architecture.md), [Phase-08 DoD](../docs/DoD/Phase-08.md)

## 목표

Premium AI Music Studio 설계를 실제 Frontend로 단계적으로 전환한다. 이 문서는 구현 순서이며 현재 완료 상태를 의미하지 않는다.

## F0 — Frontend Contract Verification

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
| Voice Profile | `POST /api/voice-profiles`, `DELETE /api/voice-profiles/{id}` |
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

## F1 — Foundation

- Next.js App Router, TypeScript, quality gate, token/theme, App shell
- Button/Input/Card/Modal/Drawer/Toast/Progress primitives
- 접근성·responsive test baseline
- 완료 기준: lint·type·build와 token/component 문서 일치

## F2 — Studio Draft

- Desktop 3-column, Tablet drawer, Mobile step navigation
- Music Settings, Lyrics draft/validation, Voice metadata, Review
- draft 복원과 입력 오류
- 완료 기준: API 호출 전 사용자 flow와 responsive 상태 검증

## F3 — API Integration

- Health, Lyrics, Voice Profile, Pipeline client
- 오류 정규화, polling, reconnect, URL 복원
- 현재 미지원 action의 disabled/empty state
- 완료 기준: Mock Backend 기준 생성 → status → result metadata E2E

## F4 — Music Experience

- Vinyl artwork, waveform, transport, result inspector, motion
- audio content endpoint 승인 후 실제 player/download 연결
- reduced motion, keyboard, screen reader 검증
- 완료 기준: endpoint 없는 가짜 재생 0건, 실제 media 계약 E2E

## F5 — Projects·Production Readiness

- 인증·소유권, history/project, upload/download, cancel/retry API 연동
- observability, browser matrix, performance, security review
- 완료 기준: Phase-08 DoD와 사용자 시나리오 승인

## 우선순위와 보류

F0 문서 검토 중 shell·draft의 추가 설계는 가능하지만 실제 Frontend 프로젝트·컴포넌트 구현은 F0 완료 전 시작하지 않는다. F4의 Player, F5의 Projects는 관련 endpoint 없이 완료 처리하지 않는다. 모든 단계에서 `main` 배포와 Production 공개는 Phase 9 승인 전까지 보류한다.
