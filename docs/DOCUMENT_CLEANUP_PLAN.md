# DohaMusic Documentation Cleanup Plan

> 문서 상태: [계획]
> 최종 수정일: 2026-08-20
> 기준: develop@59157f63990e0898e39b51e267502cdc8c1fe974
> 관련 문서: [Authority Map](DOCUMENT_AUTHORITY_MAP.md), [README](../README.md)

## 1. 목적

이 문서는 Authority Inventory에서 확인한 중복·과거·stale 문서를 후속 PR에서 안전하게 정리하기 위한 제안이다. 이번 문서 구조 리팩터링은 navigation과 분류를 우선하며, 아래 후보를 이동·삭제하거나 역사 증거를 지우지 않는다.

## 2. 판단 기준

- MERGE: 최신 유효 정보를 Canonical 또는 한 개의 상세 문서로 합친 뒤 원문을 deprecated 처리한다.
- DEPRECATE: 문서 상단에 대체 문서를 명시하고 새 변경을 중단한다.
- ARCHIVE: 역사적 참고 가치는 보존하되 현재 navigation에서 분리한다.
- DELETE_CANDIDATE: Authority 아님, 완전한 대체 문서, inbound reference 0, evidence 가치 0, 정보 손실 0을 모두 다시 검증한 경우에만 제안한다.
- ADR·CHANGELOG·실험·평가·Validation은 삭제 후보가 아니다.

## 3. Cleanup 후보

| Document | Classification | Problem | Proposed Action | Risk |
|---|---|---|---|---|
| docs/00-overview/project-overview.md | SUPPORTING | Product Authority와 목표·현재 설명 중복 | MERGE — 고유 개요만 Product Authority에 반영하고 짧은 안내 문서로 축소 | 기존 overview inbound link가 많아 즉시 deprecate 금지 |
| docs/00-overview/goals-and-non-goals.md | SUPPORTING | CURRENT MVP 비목표와 장기 TARGET 설명이 Product Authority와 겹침 | MERGE — 범위 원칙만 유지하고 Product Authority 링크 중심으로 축소 | 비목표의 역사적 맥락 손실 가능 |
| docs/02-requirements/mvp-scope.md | SUPERSEDED | 승인 대기 초안이 완료된 Phase 8 MVP와 장기 제품 방향보다 오래됨 | DEPRECATE — Product Authority와 Phase-08 DoD를 대체 기준으로 표시 | 과거 MVP 범위 추적 필요 |
| docs/03-architecture/frontend-overview.md | SUPPORTING | 지원 범위·페이지·상태가 Frontend Architecture와 반복됨 | MERGE — 상태 분류는 Overview, 구조·계약은 Architecture로 책임 고정 | 여러 README·Roadmap 링크 갱신 필요 |
| docs/03-architecture/frontend-architecture.md | SUPPORTING | CURRENT 구조와 상세 API 상태가 길고 Overview와 일부 중복 | UPDATE — CURRENT 구조·state/API 책임만 유지하고 TARGET은 전환 계획 링크 | PR #93 이후 최신 상태 재검증 필요 |
| docs/03-architecture/design-system.md | STALE | [계획] 문서지만 실제 CSS token·component가 이미 존재 | ARCHIVE 또는 UPDATE — 구현 대조 후 현행 design token 문서로 승격 여부 결정 | 실제 UI 회귀 검증 없이 갱신 불가 |
| docs/03-architecture/navigation-guide.md | STALE | 계획 navigation과 현재 App Router가 불일치할 가능성 | ARCHIVE — 현행 route inventory는 Frontend Overview로 통합 | 접근성 의도 보존 필요 |
| docs/03-architecture/page-structure.md | STALE | 계획 page hierarchy와 현재 route tree·TARGET Workspace가 혼재 | ARCHIVE — CURRENT route와 TARGET /studio/[projectId]를 분리한 뒤 처리 | 향후 DAW 정보 구조 참고 가치 |
| docs/03-architecture/responsive-guide.md | STALE | 계획 문서 상태가 완료된 Responsive Studio 구현과 맞지 않음 | UPDATE 또는 ARCHIVE — 실제 breakpoint·E2E 근거 대조 | 모바일 접근성 기준 손실 가능 |
| docs/03-architecture/ui-component-guide.md | STALE | 계획 component 목록과 실제 frontend/components, features 불일치 가능 | ARCHIVE — 유효 원칙은 Frontend Architecture로 MERGE | 구현 세부 참고 가치 |
| docs/03-architecture/history-management.md | SUPPORTING | 12줄 요약이 History·Project API 문서와 책임 중복 | MERGE — docs/06-api/history-project-api.md로 통합 | Architecture 관점의 보존 여부 확인 |
| docs/03-architecture/project-management.md | SUPPORTING | 12줄 요약이 History·Project API·Workspace 문서와 중복 | MERGE — Workspace/History API Authority에 통합 | Legacy Project와 MusicProject 혼동 주의 |
| docs/07-database/erd.md | SUPPORTING | 현행 ERD와 Asset 중심 목표 ERD가 동시에 노출됨 | UPDATE — CURRENT 표기를 강화하고 목표 ERD와 상호 링크 | 잘못 deprecate하면 실제 Legacy schema 근거 손실 |
| docs/07-database/table-definition.md | SUPPORTING | 현행 Table과 목표 Table Definition이 병존 | UPDATE — CURRENT/호환/목표 책임을 첫 화면에서 분리 | Migration 단계별 source of truth 확인 필요 |
| planning/phase-01-research.md | SUPERSEDED | Phase 번호와 상태가 Master Roadmap·DoD와 불일치 | DEPRECATE 후 ARCHIVE | 초기 조사 순서의 역사 가치 |
| planning/phase-02-local-inference.md | SUPERSEDED | 오래된 실행 계획이 실제 Phase 2 DoD·실험 보고서로 대체됨 | DEPRECATE 후 ARCHIVE | 로컬 실행 계획의 일부 고유 정보 확인 필요 |
| planning/phase-03-ai-pipeline.md | SUPERSEDED | 현재 Phase·Pipeline 완료 상태와 불일치 | DEPRECATE 후 ARCHIVE | 과거 Pipeline 범위 보존 필요 |
| planning/phase-04-api.md | SUPERSEDED | 현재 API 개요와 Workspace 전환 문서가 대체 | DEPRECATE 후 ARCHIVE | Legacy API 단계 이력 |
| planning/phase-05-web-mvp.md | SUPERSEDED | 문서 자체가 [대체됨]이며 Frontend Roadmap·Phase-08 DoD가 Authority | ARCHIVE | 링크 변경 후 inbound 0 재검증 필요 |
| planning/phase-06-personalization.md | SUPERSEDED | 오래된 Phase 번호가 Phase-07·Provider 분리 정책과 충돌 가능 | DEPRECATE 후 ARCHIVE | Dataset·개인화 안전 원칙 보존 필요 |
| planning/frontend-roadmap.md | SUPPORTING | F0~F5 완료 이력과 F6 현재 계획이 한 문서에 혼재 | MERGE — F6 종료 후 완료 이력은 Historical section 또는 보고서로 분리 | F6 진행 중에는 Authority 이동 금지 |
| MASTER_ROADMAP.md / ROADMAP.md | CANONICAL | Phase 상태와 실행 순서 일부 반복 | KEEP — Master=장기 Phase·Track·Gate, Roadmap=현재 NEXT/LATER로 책임 고정 | 자동 상태 동기화가 없어 drift 가능 |
| reports/validation/* | HISTORICAL | 개별 보고서가 많고 일부 inbound link가 없음 | KEEP — Authority Map에서 탐색하고 파일은 이동·삭제하지 않음 | evidence 손실 절대 금지 |
| reports/experiments/*, reports/evaluations/* | HISTORICAL | 현재 navigation에서 찾기 어려움 | KEEP — Authority Map에서 유형별 탐색 제공 | 실험 결과를 CURRENT 구현으로 오해하지 않게 상태 유지 |
| docs/11-decisions/ADR-*.md | HISTORICAL | 결정 수가 많지만 삭제·통합 대상이 아님 | KEEP — ADR Index 상태·대체 링크만 유지 | 결정 이력 재작성 금지 |

## 4. 권장 순서

1. Frontend stale 문서 5개를 실제 route·component·E2E와 대조한다.
2. Overview/Product 중복을 줄이고 mvp-scope.md를 명시적으로 deprecate한다.
3. Legacy Phase 계획 6개에 대체 문서와 역사 상태를 표시한다.
4. Database CURRENT/목표 문서 쌍의 첫 화면 표기를 통일한다.
5. 모든 inbound link를 갱신한 뒤에만 선택적 archive 이동을 검토한다.
6. 이동 후 전체 Markdown link, code reference, ADR·CHANGELOG reference와 Git history 추적성을 재검증한다.

## 5. DELETE_CANDIDATE

현재 확정한 DELETE_CANDIDATE는 **0개**다.

초기 orphan 검색에서 inbound Markdown link가 없는 문서가 확인됐지만, Validation·실험·정책·계획의 evidence 가치와 code reference를 모두 배제하지 못했다. 따라서 orphan이라는 이유만으로 삭제하지 않는다.

## 6. 후속 ADR 검토 후보

문서 이동 자체는 ADR 대상이 아니다. 다만 다음 제품 구현 단계에서는 별도 ADR을 검토한다.

- Track·Clip·Section canonical identity와 CompositionSnapshot 표현
- Timeline edit command, undo/redo, 동시 편집·복구
- CompositionEvaluationRun 수명주기·저장·API와 Common Contract 승격 필요성
- Reference source ingestion·retention·철회·삭제
- LearningCandidate 자동 제안, opt-in·review·철회 UX
