# AI-native DAW Product Track Definition of Done

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-20
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md), [제품 방향](../02-product/ai-native-daw-product-direction.md), [D1 Composition Read 계약](../06-api/composition-read-workspace.md), [Frontend 전환 계획](../../planning/ai-native-daw-frontend-migration.md)

이 Track은 Phase 8 Responsive Studio MVP 완료와 분리한다. D0 문서 정합성이 끝나도 DAW Runtime이 구현된 것으로 보지 않는다. 각 단계의 구현·검증·문서·ADR·Git 증거가 모두 있어야 다음 상태로 승격한다.

## D0. 제품 목표 문서 정합성 — [완료]

- [x] CURRENT, TARGET, NOT IMPLEMENTED를 분리한 제품 방향 문서
- [x] 현재·목표 Architecture와 Reference·Creation·Editing·QA·Learning 흐름
- [x] Frontend Migration과 DohaLM Frontend Retirement Gate
- [x] Common Contract 재사용·금지·product-only 후보 정합성 표
- [x] 기존 Phase 8 MVP 완료와 장기 DAW TARGET 분리
- [x] broken link·Markdown·금칙 표현·`git diff --check` 검증
- [x] 한국어 커밋과 원격 작업 브랜치 Push
- [x] `develop` 대상 Draft PR 생성·검토
- [x] PR #94 squash merge와 병합 후 동일 tree 검증

## D1. Composition Read Workspace — [D1-A Backend 완료 / Transition 계획]

### 계약 Gate — [완료]

- [x] Workspace v1 Composition read authority와 Legacy migration input 경계
- [x] Project-level explicit selected/current Snapshot과 requested history read 분리
- [x] Snapshot-local Track projection identity와 future canonical Track Domain 분리
- [x] Section `not_available`·빈 목록 정책과 Clip 제외 범위
- [x] Project Composition aggregate endpoint·DTO·Artifact 안전·lineage 계약
- [x] bootstrap/empty/selection-required와 silent fallback·GET mutation 금지
- [x] CURRENT single-user owner scope와 TARGET 인증 Gate 분리
- [x] Common AI Contract schema 변경 없음

### 구현·검증 Gate — [진행 중]

- [x] Workspace Project와 `CompositionWorkspaceRead` aggregate Backend 구현
- [x] explicit selected/current Snapshot persistence와 same-Project 불변식
- [x] exact AssetVersion·safe Artifact·Track projection·Section availability·Mix·lineage 응답
- [x] Snapshot History HMAC Cursor와 aggregate 단건 read 분리
- [ ] `WORKSPACE_BOOTSTRAP_REQUIRED`, empty, selection-required, error와 recovery UI
- [x] Legacy silent fallback·GET bootstrap/backfill·write side effect 0건 검증
- [ ] 실제 인증 principal 기반 Owner·Workspace·Project privacy와 cross-owner leakage 0건
- [ ] Frontend Workspace consume와 실제 Snapshot E2E

## D2. Timeline Playback Foundation — [계획]

- [ ] 읽기 전용 Arrangement·Section·Track·Clip·Waveform
- [ ] Playhead와 playback·pause·stop·seek·range selection
- [ ] 시간 mapping·접근성·성능·반응형 검증

## D3. Non-destructive DAW Editing — [계획]

- [ ] split·trim·move·copy·delete·fade·gain·loop
- [ ] 원본 불변 AssetVersion·CompositionSnapshot commit
- [ ] undo/redo·동시 편집·복구 정책과 ADR

## D4. Mixer와 Export — [계획]

- [ ] Volume·Pan·Mute·Solo와 Mix 설정
- [ ] Preview와 WAV·MP3·FLAC 독립 Export Asset
- [ ] 음질·Job·secure download 검증

## D5. AI Music Director — [계획]

- [ ] TimelineSelection을 기존 MusicIntent로 materialize
- [ ] 실행 전 승인과 Candidate A/B 비교·선택
- [ ] HTTP·SSE·Cancel·Retry·Readiness·오류·실제 Provider E2E

## D6. Reference Panel — [계획]

- [ ] 허용 source와 분석·retention·Training 권리 분리
- [ ] ReferenceAnalysis·FeatureRecord·DohaLM planning context
- [ ] 철회·삭제·원본 비노출 검증

## D7. Composition Evaluation / QA — [계획]

- [ ] `CompositionEvaluationRun` 제품 계약과 ADR 검토
- [ ] 9개 평가 영역과 human-readable QA Report
- [ ] Studio exact range deep-link, RevisionPlan과 Re-Evaluation
- [ ] 공통 EvaluationRun 의미 비충돌 검증

## D8. Continuous Learning Review Hub — [계획]

- [ ] 명시적 opt-in LearningCandidate 제안·검토
- [ ] RightsMetadata·TrainingEligibility·DatasetVersion 상태 연결
- [ ] 자동 Dataset 포함·Training 승인 금지와 불변 lineage 검증

## D9. 통합·운영 전환 — [계획]

- [ ] 기존 MVP parity·migration·rollback
- [ ] 인증·소유권·감사·rate limit·분산 실행·관측성
- [ ] 실제 사용자 DAW·QA·Export E2E와 접근성·성능 평가
- [ ] DohaLM Frontend Retirement Gate와 명시적 승인
