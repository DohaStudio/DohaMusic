# Phase 8 Definition of Done — Doha Studio

> 상태: [완료]
> 진행률: 15/15, 100%
> 최종 수정일: 2026-08-01
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-8-doha-studio--완료), [Frontend Architecture](../03-architecture/frontend-architecture.md), [Frontend Roadmap](../../planning/frontend-roadmap.md), [Voice Enrollment 요구사항](../02-requirements/voice-enrollment-requirements.md), [ADR-020](../11-decisions/ADR-020-project-history-retention.md)

## 목표

현재 FastAPI 계약 범위에서 음악 설정·가사·Voice Profile·Pipeline 진행·History·Project·결과 metadata와 완료된 WAV 재생·다운로드를 제공하는 Responsive Web Studio를 구축한다.

## 선행 조건과 현재 경계

Phase 5 Pipeline과 Phase 6 Lyrics API를 사용한다. 완료 Pipeline WAV, Voice Profile, History·Project, Job Cancel·Retry API를 제공한다. 인증·소유권은 로컬 MVP가 아니라 Phase 9 공개 운영 차단 조건이다.

마지막 항목인 cooperative Cancel·새 Job Retry와 관련 Backend·Frontend·migration·자동 검증·문서를 완료했다. 진행률은 `15 / 15 × 100 = 100%`다.

## 완료 체크리스트

- [x] Frontend 프로젝트와 공통 UI 구조
- [x] Prompt·Lyrics 입력
- [x] Voice Profile 입력·동의·목록·선택 UI
- [x] Upload 보안·검증 — WAV 25MB·5~60초·consent·Storage cleanup
- [x] Job 상태·오류·새 Job 생성 복구 UI
- [x] Audio Player — 단일 전역 Player와 Range 기반 완료 WAV 재생
- [x] Generation History — 검색·상태·페이지네이션·상세와 Project CRUD·Result 재진입
- [x] WAV Download — 안전한 attachment filename과 권한 capability 기반 제공
- [x] API Client·Job Cancel·Retry 연결 — 상태 전이·단계 경계 취소·입력 Snapshot·새 Job 관계·History/Project UX
- [x] 반응형·접근성·Chromium Desktop·Mobile 검증
- [x] Lint·Type Check·Build
- [x] 주요 사용자 시나리오 E2E
- [x] Frontend·API·Security 문서·CHANGELOG
- [x] 커밋·Push·`develop` PR·병합 — Phase 8 기능 PR 이력
- [x] 병합 후 검증과 `main` 무변경 — 원격 `develop` 동기화 확인

## 검증 증거

- `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build` 통과
- `npm ci`, `npm audit` 통과, 취약점 0건
- Vitest 38개 unit·component test 통과
- Playwright Chromium Desktop·Mobile 8개 E2E에서 WAV upload → Profile 선택 → Studio → Review → Pipeline과 기존 핵심 흐름 통과
- Backend non-GPU `pytest`: 145 passed, GPU·외부·symlink 권한 실행 7 skipped; Ruff check·format check 통과
- 신규·기존 DB Alembic upgrade와 legacy nullable metadata를 확인
- 실제 multipart upload·list·get·Pipeline ID 연결·사용 중 409·정상 파일 삭제와 Next.js proxy list를 확인
- 실제 Mock Pipeline WAV에서 FastAPI와 Next.js same-origin proxy의 GET/HEAD, `bytes=10-19` 206, 범위 밖 416, attachment header를 확인

## 완료 조건

Phase 8은 로컬 단일 사용자 Responsive Web MVP 범위에서 완료됐다. 인증·소유권·인가·감사 로그·rate limit·분산 Queue·다중 Worker 취소 일관성·process ownership·보존 기간은 Phase 9 공개 Production 차단 조건이며 완료로 간주하지 않는다.

## 산출물

`frontend/` Next.js application, API client·DTO·mapper·store·feature hooks, unit·component·E2E test, 갱신된 Architecture·ADR·Roadmap.

## 예상 다음 단계

Phase 8 완료 범위를 소급 변경하지 않는 [F6 Guided Voice Enrollment](../../planning/frontend-roadmap.md#f6--guided-voice-enrollment-진행-중)을 후속 개선 Track으로 진행한다. F6 Backend API·정규화·Storage·기본 품질 검사, Frontend Wizard·MediaRecorder·품질·대표 선택·복원과 Windows/CI FFmpeg WebM/Ogg 통합 검증은 완료했지만 주기적 cleanup·인증·실기기 평가는 미구현이며, 이 문서의 15개 완료 항목과 100% 진행률에 포함하지 않는다. 공개 운영의 인증·소유권·분산 Queue와 운영 취소 일관성은 Phase 9에서 설계·검증한다.
