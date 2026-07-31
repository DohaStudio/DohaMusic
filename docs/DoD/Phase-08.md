# Phase 8 Definition of Done — Doha Studio

> 상태: [진행 중]
> 진행률: 14/15, 93%
> 최종 수정일: 2026-07-31
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-8-doha-studio--진행-중), [Frontend Architecture](../03-architecture/frontend-architecture.md), [Frontend Roadmap](../../planning/frontend-roadmap.md), [ADR-020](../11-decisions/ADR-020-project-history-retention.md)

## 목표

현재 FastAPI 계약 범위에서 음악 설정·가사·Voice Profile·Pipeline 진행·History·Project·결과 metadata와 완료된 WAV 재생·다운로드를 제공하는 Responsive Web Studio를 구축한다.

## 선행 조건과 현재 경계

Phase 5 Pipeline과 Phase 6 Lyrics API를 사용한다. 완료 Pipeline WAV, Voice Profile, History·Project API를 제공한다. Job cancel·기존 Job retry·인증·소유권은 API가 없어 완료 범위가 아니다.

이번 확장에서 `Generation History`와 Git·병합 증거를 완료했다. 진행률은 `14 / 15 × 100 = 93.3%`를 반올림한 93%다.

## 완료 체크리스트

- [x] Frontend 프로젝트와 공통 UI 구조
- [x] Prompt·Lyrics 입력
- [x] Voice Profile 입력·동의·목록·선택 UI
- [x] Upload 보안·검증 — WAV 25MB·5~60초·consent·Storage cleanup
- [x] Job 상태·오류·새 Job 생성 복구 UI
- [x] Audio Player — 단일 전역 Player와 Range 기반 완료 WAV 재생
- [x] Generation History — 검색·상태·페이지네이션·상세와 Project CRUD·Result 재진입
- [x] WAV Download — 안전한 attachment filename과 권한 capability 기반 제공
- [ ] API Client·인증·소유권 연결 — API client 완료, 인증·소유권 필요
- [x] 반응형·접근성·Chromium Desktop·Mobile 검증
- [x] Lint·Type Check·Build
- [x] 주요 사용자 시나리오 E2E
- [x] Frontend·API·Security 문서·CHANGELOG
- [x] 커밋·Push·`develop` PR·병합 — Phase 8 기능 PR 이력
- [x] 병합 후 검증과 `main` 무변경 — 원격 `develop` 동기화 확인

## 검증 증거

- `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build` 통과
- `npm ci`, `npm audit` 통과, 취약점 0건
- Vitest 35개 unit·component test 통과
- Playwright Chromium Desktop·Mobile 8개 E2E에서 WAV upload → Profile 선택 → Studio → Review → Pipeline과 기존 핵심 흐름 통과
- Backend non-GPU `pytest`: 129 passed, GPU·외부·symlink 권한 실행 7 skipped; Ruff check·format check 통과
- 신규·기존 DB Alembic upgrade와 legacy nullable metadata를 확인
- 실제 multipart upload·list·get·Pipeline ID 연결·사용 중 409·정상 파일 삭제와 Next.js proxy list를 확인
- 실제 Mock Pipeline WAV에서 FastAPI와 Next.js same-origin proxy의 GET/HEAD, `bytes=10-19` 206, 범위 밖 416, attachment header를 확인

## 완료 조건

남은 1개 항목인 인증·소유권을 완료해야 한다. 현재 로컬 단일 사용자 MVP는 공개 Production 서비스나 Native 앱 완료를 의미하지 않는다.

## 산출물

`frontend/` Next.js application, API client·DTO·mapper·store·feature hooks, unit·component·E2E test, 갱신된 Architecture·ADR·Roadmap.

## 예상 다음 단계

cancel/retry와 인증·소유권 Backend 계약을 확정한 뒤 F5와 Phase 8 전체 완료를 검토한다.
