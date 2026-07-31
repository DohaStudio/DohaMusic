# Phase 8 Definition of Done — Doha Studio

> 상태: [진행 중]
> 진행률: 8/15, 53%
> 최종 수정일: 2026-07-31
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-8-doha-studio--진행-중), [Frontend Architecture](../03-architecture/frontend-architecture.md), [Frontend Roadmap](../../planning/frontend-roadmap.md), [ADR-017](../11-decisions/ADR-017-frontend-technology-stack.md)

## 목표

현재 FastAPI 계약 범위에서 음악 설정·가사·Voice Profile·Pipeline 진행·결과 metadata를 제공하는 Responsive Web Studio를 구축한다. Audio content, 이력과 소유권은 Backend 계약 이후 확장한다.

## 선행 조건과 현재 경계

Phase 5 Pipeline과 Phase 6 Lyrics API를 사용한다. upload/download·audio content·Voice Profile list/get·프로젝트 이력·Job cancel·기존 Job retry·인증·소유권은 API가 없어 완료 범위가 아니다. 관련 control은 disabled이며 가짜 데이터는 사용하지 않는다.

## 완료 체크리스트

- [x] Frontend 프로젝트와 공통 UI 구조
- [x] Prompt·Lyrics 입력
- [x] Voice Profile 입력·동의 UI
- [ ] Upload 보안·검증 — `Backend Required`
- [x] Job 상태·오류·새 Job 생성 복구 UI
- [ ] Audio Player — metadata shell만 구현, content API 필요
- [ ] Generation History — 목록 API 필요
- [ ] WAV Download — content API 필요
- [ ] API Client·인증·소유권 연결 — API client 완료, 인증·소유권 필요
- [x] 반응형·접근성·Chromium Desktop·Mobile 검증
- [x] Lint·Type Check·Build
- [x] 주요 사용자 시나리오 E2E
- [x] Frontend·API·Security 문서·CHANGELOG
- [ ] 한국어 커밋·Push·`develop` PR·병합 — 작업 완료 후 증거 연결
- [ ] 병합 후 검증과 `main` 무변경 — 작업 완료 후 확인

## 검증 증거

- `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build` 통과
- Playwright Chromium Desktop·Mobile에서 Landing → Studio → Lyrics → Voice ID → Review → Pipeline → Result 흐름과 미지원 action disabled 상태 통과
- FastAPI `GET /health`와 Next.js `/backend/health` proxy 응답 `ok` 확인

## 완료 조건

나머지 7개 항목 중 upload·player·history·download·인증·소유권은 Backend API가 준비된 뒤 완료한다. 현재 MVP는 공개 Production 서비스나 Native 앱 완료를 의미하지 않는다.

## 산출물

`frontend/` Next.js application, API client·DTO·mapper·store·feature hooks, unit·component·E2E test, 갱신된 Architecture·ADR·Roadmap.

## 예상 다음 단계

Audio content·download, Voice upload/list/get, history/project, cancel/retry, 인증·소유권 Backend 계약을 확정한 뒤 F5와 Phase 8 전체 완료를 검토한다.
