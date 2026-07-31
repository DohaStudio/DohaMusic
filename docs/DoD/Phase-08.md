# Phase 8 Definition of Done — Doha Studio

> 상태: [진행 중]
> 진행률: 10/15, 67%
> 최종 수정일: 2026-07-31
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-8-doha-studio--진행-중), [Frontend Architecture](../03-architecture/frontend-architecture.md), [Frontend Roadmap](../../planning/frontend-roadmap.md), [ADR-018](../11-decisions/ADR-018-secure-audio-file-access.md)

## 목표

현재 FastAPI 계약 범위에서 음악 설정·가사·Voice Profile·Pipeline 진행·결과 metadata와 완료된 WAV 재생·다운로드를 제공하는 Responsive Web Studio를 구축한다. 이력과 소유권은 Backend 계약 이후 확장한다.

## 선행 조건과 현재 경계

Phase 5 Pipeline과 Phase 6 Lyrics API를 사용한다. 완료 Pipeline의 허용된 WAV content·download는 제공한다. upload·Voice Profile list/get·프로젝트 이력·Job cancel·기존 Job retry·인증·소유권은 API가 없어 완료 범위가 아니며 관련 control에는 가짜 데이터를 사용하지 않는다.

이번 확장에서 Audio Player와 WAV Download 2개 항목을 완료했다. 진행률은 `10 / 15 × 100 = 66.7%`를 반올림한 67%다. 기존 완료 항목은 취소하지 않는다.

## 완료 체크리스트

- [x] Frontend 프로젝트와 공통 UI 구조
- [x] Prompt·Lyrics 입력
- [x] Voice Profile 입력·동의 UI
- [ ] Upload 보안·검증 — `Backend Required`
- [x] Job 상태·오류·새 Job 생성 복구 UI
- [x] Audio Player — 단일 전역 Player와 Range 기반 완료 WAV 재생
- [ ] Generation History — 목록 API 필요
- [x] WAV Download — 안전한 attachment filename과 권한 capability 기반 제공
- [ ] API Client·인증·소유권 연결 — API client 완료, 인증·소유권 필요
- [x] 반응형·접근성·Chromium Desktop·Mobile 검증
- [x] Lint·Type Check·Build
- [x] 주요 사용자 시나리오 E2E
- [x] Frontend·API·Security 문서·CHANGELOG
- [ ] 한국어 커밋·Push·`develop` PR·병합 — 작업 완료 후 증거 연결
- [ ] 병합 후 검증과 `main` 무변경 — 작업 완료 후 확인

## 검증 증거

- `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build` 통과
- `npm ci`, `npm audit` 통과, 취약점 0건
- Vitest 31개 unit·component test 통과
- Playwright Chromium Desktop·Mobile 8개 E2E에서 Landing → Studio → Lyrics → Voice ID → Review → Pipeline → Result, Voice 개발 입력 기본 비노출, Template revision 비활성, 네트워크 오류·Job URL 복원 통과
- Backend non-GPU `pytest`: 118 passed, GPU·외부·symlink 권한 실행 7 skipped; Ruff check·format check 통과
- 실제 Mock Pipeline WAV에서 FastAPI와 Next.js same-origin proxy의 GET/HEAD, `bytes=10-19` 206, 범위 밖 416, attachment header를 확인

## 완료 조건

나머지 5개 항목 중 upload·history·인증·소유권과 Git 병합 증거를 완료해야 한다. 현재 로컬 단일 사용자 MVP는 공개 Production 서비스나 Native 앱 완료를 의미하지 않는다.

## 산출물

`frontend/` Next.js application, API client·DTO·mapper·store·feature hooks, unit·component·E2E test, 갱신된 Architecture·ADR·Roadmap.

## 예상 다음 단계

Voice upload/list/get, history/project, cancel/retry, 인증·소유권 Backend 계약을 확정한 뒤 F5와 Phase 8 전체 완료를 검토한다.
