# Phase 8 Definition of Done — Doha Studio

> 상태: [계획]
> 진행률: 0/15, 0%
> 최종 수정일: 2026-07-29
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md#phase-8-doha-studio--계획), [Frontend Architecture](../03-architecture/frontend-architecture.md)

## 목표

음악 생성·편집·재생·이력·파일 관리를 제공하는 사용자용 Studio를 구축한다.

## 구현 범위와 포함 기능

Frontend, Prompt·Lyrics·Voice 입력, Player, History, Upload·Download, 작업 상태·오류, 인증·소유권 연동을 포함한다.

## 제외 기능

Production 인프라 전환, 공개 서비스 릴리스와 미승인 Voice 기능은 제외한다.

## 선행 조건

Phase 5 Pipeline API, 인증·권한·파일 소유권과 안전 정책이 확정되어야 한다.

## 완료 체크리스트

- [ ] Frontend 프로젝트와 공통 UI 구조
- [ ] Prompt·Lyrics 입력
- [ ] Voice Profile 입력·동의 UI
- [ ] Upload 보안·검증
- [ ] Job 상태·오류·재시도 UI
- [ ] Audio Player
- [ ] Generation History
- [ ] WAV Download
- [ ] API Client·인증·소유권 연결
- [ ] 반응형·접근성·주요 브라우저 검증
- [ ] Lint·Type Check·Build
- [ ] 주요 사용자 시나리오 E2E
- [ ] Frontend·API·Security 문서·CHANGELOG
- [ ] 한국어 커밋·Push·`develop` PR·병합
- [ ] 병합 후 검증과 `main` 무변경

## 완료 조건

동의된 사용자 시나리오가 안전한 권한 경계에서 종단 간 동작하고 빌드·접근성·E2E를 통과해야 한다.

## 산출물

Doha Studio Frontend, UI·상태·API 문서, E2E 결과.

## 관련 문서·ADR·실험

- 문서: [User Scenarios](../00-overview/user-scenarios.md), [File Upload Security](../09-security/file-upload-security.md)
- ADR·실험: Frontend stack·인증·파일 전달 결정 검토 필요

## 예상 다음 단계

Phase 9 Production.
