# DohaMusic Documentation Cleanup Plan

> 문서 상태: [진행 기록]
> 최종 수정일: 2026-08-20
> 기준: develop@339e547f213dbc969bf9e0deb1c2e7918bf26bea
> 관련 문서: [Authority Map](DOCUMENT_AUTHORITY_MAP.md), [README](../README.md)

## 1. 목적

이 문서는 Authority Inventory에서 확인한 중복·과거·stale 문서의 처리 결과와 남은 후보를 기록한다. 2026-08-20 Cleanup은 Product·Frontend·History/Project 중복을 통합하고, Database CURRENT/TARGET/TRANSITION 책임을 정합화했다. 직접 참조 가능성이 있는 문서는 deprecate하고 과거 Frontend·Phase 계획은 Git 이력을 보존해 archive했으며, 문서 삭제는 수행하지 않았다.

## 2. 판단 기준

- MERGE: 최신 유효 정보를 Canonical 또는 한 개의 상세 문서로 합친 뒤 원문을 deprecated 처리한다.
- DEPRECATE: 문서 상단에 대체 문서를 명시하고 새 변경을 중단한다.
- ARCHIVE: 역사적 참고 가치는 보존하되 현재 navigation에서 분리한다.
- DELETE_CANDIDATE: Authority 아님, 완전한 대체 문서, inbound reference 0, evidence 가치 0, 정보 손실 0을 모두 다시 검증한 경우에만 제안한다.
- ADR·CHANGELOG·실험·평가·Validation은 삭제 후보가 아니다.

## 3. Cleanup 후보

| Document | Classification | Problem | Result / Next Action | Risk |
|---|---|---|---|---|
| docs/00-overview/project-overview.md | SUPERSEDED | Product Authority와 목표·현재 설명 중복 | DONE — 고유 문제·가치·범위를 Product Authority에 MERGE하고 안내 문서로 DEPRECATE | 대체 link 유지 |
| docs/00-overview/goals-and-non-goals.md | SUPERSEDED | CURRENT MVP 비목표와 장기 TARGET 설명이 Product Authority와 겹침 | DONE — 범위 원칙을 Product Authority에 MERGE하고 안내 문서로 DEPRECATE | 대체 link 유지 |
| docs/02-requirements/mvp-scope.md | SUPERSEDED | 승인 대기 초안이 완료된 Phase 8 MVP와 장기 제품 방향보다 오래됨 | DONE — Product Authority와 Phase-08 DoD를 대체 기준으로 명시해 DEPRECATE | 과거 MVP 범위 본문 보존 |
| docs/03-architecture/frontend-overview.md | SUPPORTING | 지원 범위·페이지·상태가 Frontend Architecture와 반복됨 | DONE — CURRENT 경험·route·지원 범위 책임으로 축소 | 현행 App Router 대조 완료 |
| docs/03-architecture/frontend-architecture.md | SUPPORTING | CURRENT 구조와 상세 API 상태가 길고 Overview와 일부 중복 | DONE — 구조·state/API·design 구현 책임으로 고정하고 TARGET은 전환 계획 링크 | PR #93 이후 code tree 대조 완료 |
| docs/archive/frontend/design-system.md | HISTORICAL | 계획 token이 실제 CSS token과 불일치 | DONE — 유효 구현 기준을 Frontend Architecture에 MERGE하고 ARCHIVE | 역사적 초안 본문 보존 |
| docs/archive/frontend/navigation-guide.md | HISTORICAL | 계획 navigation과 현재 App Router 불일치 | DONE — 현행 route inventory를 Frontend Overview에 MERGE하고 ARCHIVE | 접근성 의도 본문 보존 |
| docs/archive/frontend/page-structure.md | HISTORICAL | 계획 page hierarchy와 CURRENT/TARGET 혼재 | DONE — CURRENT route와 TARGET 전환 기준을 현행 문서에 연결하고 ARCHIVE | 향후 DAW 정보 구조 참고 보존 |
| docs/archive/frontend/responsive-guide.md | HISTORICAL | 계획 breakpoint와 실제 CSS·E2E 불일치 | DONE — 실제 code/test source를 Frontend Architecture에 명시하고 ARCHIVE | 모바일 접근성 원칙 본문 보존 |
| docs/archive/frontend/ui-component-guide.md | HISTORICAL | 계획 component 목록과 실제 tree 불일치 | DONE — component 책임 원칙을 Frontend Architecture에 MERGE하고 ARCHIVE | 구현 전 초안 본문 보존 |
| docs/03-architecture/history-management.md | SUPERSEDED | 짧은 요약이 History·Project API 문서와 책임 중복 | DONE — projection·Frontend·권한 경계를 API 문서에 MERGE하고 DEPRECATE | 대체 link 유지 |
| docs/03-architecture/project-management.md | SUPERSEDED | 짧은 요약이 History·Project API·Workspace 문서와 중복 | DONE — CRUD·retention·Frontend 경계를 API 문서에 MERGE하고 DEPRECATE | Legacy Project 의미 보존 |
| docs/07-database/erd.md | SUPPORTING | 현행 ERD와 Asset 중심 목표 ERD가 동시에 노출됨 | DONE — CURRENT Runtime 14개 subset과 TARGET ERD를 명시적으로 분리 | 실제 Runtime schema 근거 보존 |
| docs/07-database/table-definition.md | SUPPORTING | 현행 Table과 목표 Table Definition이 병존 | DONE — CURRENT Runtime Core 10개 책임과 별도 Pipeline·Voice Conversion 4개를 명시 | 상세 문서 병합 없이 Authority 범위 고정 |
| planning/archive/phase-01-research.md | HISTORICAL | Phase 번호와 상태가 Master Roadmap·DoD와 불일치 | DONE — 대체 기준을 명시하고 ARCHIVE | 초기 조사 순서 보존 |
| planning/archive/phase-02-local-inference.md | HISTORICAL | 오래된 실행 계획이 실제 Phase 2 DoD·실험 보고서로 대체됨 | DONE — 대체 기준을 명시하고 ARCHIVE | 로컬 실행 계획 보존 |
| planning/archive/phase-03-ai-pipeline.md | HISTORICAL | 현재 Phase·Pipeline 완료 상태와 불일치 | DONE — 대체 기준을 명시하고 ARCHIVE | 과거 Pipeline 범위 보존 |
| planning/archive/phase-04-api.md | HISTORICAL | 현재 API 개요와 Workspace 전환 문서가 대체 | DONE — 대체 기준을 명시하고 ARCHIVE | Legacy API 단계 이력 보존 |
| planning/archive/phase-05-web-mvp.md | HISTORICAL | Frontend Roadmap·Phase-08 DoD가 Authority | DONE — 대체 기준을 명시하고 ARCHIVE | Web MVP 전환 이력 보존 |
| planning/archive/phase-06-personalization.md | HISTORICAL | 오래된 Phase 번호가 Phase-07·Provider 분리 정책과 충돌 가능 | DONE — 대체 기준을 명시하고 ARCHIVE | Dataset·개인화 안전 원칙 보존 |
| planning/frontend-roadmap.md | SUPPORTING | F0~F5 완료 이력과 F6 현재 계획이 한 문서에 혼재 | KEEP — F6 종료 뒤 완료 이력 분리를 재검토 | F6 진행 중이므로 Authority 이동 금지 |
| MASTER_ROADMAP.md / ROADMAP.md | CANONICAL | Phase 상태와 실행 순서 일부 반복 | KEEP — Master=장기 Phase·Track·Gate, Roadmap=현재 NEXT/LATER로 책임 고정 | 자동 상태 동기화가 없어 drift 가능 |
| reports/validation/* | HISTORICAL | 개별 보고서가 많고 일부 inbound link가 없음 | KEEP — Authority Map에서 탐색하고 파일은 이동·삭제하지 않음 | evidence 손실 절대 금지 |
| reports/experiments/*, reports/evaluations/* | HISTORICAL | 현재 navigation에서 찾기 어려움 | KEEP — Authority Map에서 유형별 탐색 제공 | 실험 결과를 CURRENT 구현으로 오해하지 않게 상태 유지 |
| docs/11-decisions/ADR-*.md | HISTORICAL | 결정 수가 많지만 삭제·통합 대상이 아님 | KEEP — ADR Index 상태·대체 링크만 유지 | 결정 이력 재작성 금지 |

## 4. 처리 결과와 다음 순서

1. **DONE — MERGE:** Product 개요·목표/비목표, Frontend route·design 구현 기준, History·Project 경계를 각 책임 문서로 통합했다.
2. **DONE — DEPRECATE:** 직접 참조 가능성이 있는 Overview 2개, `mvp-scope.md`, History·Project 안내 2개에 replacement를 명시했다.
3. **DONE — ARCHIVE:** Frontend 초안 5개와 Legacy Phase 계획 6개를 `git mv`로 이동하고 replacement·reason·date를 기록했다.
4. **DONE — Database Alignment:** 모델 `__tablename__`, Alembic `0012`~`0017`과 Migration evidence를 대조해 CURRENT Runtime 14개, CURRENT Workspace 도메인 21개+Catalog 1개, TARGET source-of-truth 전환과 TRANSITION 책임을 분리했다.
5. **PENDING:** F6 종료 뒤 `planning/frontend-roadmap.md`의 완료 이력 분리를 재검토한다.
6. **PENDING — Database 설계 결정:** `table-definition.md`, `pipeline-tables.md`, `voice-conversion-tables.md`의 물리 통합 여부와 TARGET 문서 병합은 필요성과 history 보존 방식을 별도 검토한다.

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
