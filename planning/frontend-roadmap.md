# Doha Studio Frontend Roadmap

> 문서 상태: [계획]
> 최종 수정일: 2026-07-31
> 관련 Phase: Phase 8 Doha Studio
> 관련 문서: [Frontend Overview](../docs/03-architecture/frontend-overview.md), [Frontend Architecture](../docs/03-architecture/frontend-architecture.md), [Phase-08 DoD](../docs/DoD/Phase-08.md)

## 목표

Premium AI Music Studio 설계를 실제 Frontend로 단계적으로 전환한다. 이 문서는 구현 순서이며 현재 완료 상태를 의미하지 않는다.

## F0 — 계약·선행 조건

- OpenAPI snapshot과 실제 endpoint 일치 확인
- 오디오 content/download, Voice upload/list/get, project/history, cancel/retry, 인증·소유권 요구사항 결정
- Frontend stack·state/query·form·test·icon·motion 선택 ADR 작성
- 완료 기준: API gap이 구현·disabled·제외 중 하나로 명시됨

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

F0에서 Backend 선행 계약이 해결되지 않아도 F1~F2의 shell·draft 설계는 가능하다. F3는 실제 OpenAPI 검증이 필요하고 F4의 Player, F5의 Projects는 관련 endpoint 없이 완료 처리하지 않는다. 모든 단계에서 `main` 배포와 Production 공개는 Phase 9 승인 전까지 보류한다.
