# AI-native DAW 제품 방향

> 문서 상태: [계획]
> 최종 수정일: 2026-08-20
> 관련 기능: DohaMusic 장기 제품 목표, Composition Runtime, Composition Evaluation, Continuous Learning
> 관련 문서: [목표 아키텍처](../03-architecture/ai-native-daw-target-architecture.md), [Frontend 전환 계획](../../planning/ai-native-daw-frontend-migration.md), [Common AI Contract 소비자 기반](../03-architecture/common-ai-contract-consumer.md), [Master Roadmap](../../MASTER_ROADMAP.md)

## 1. 제품 정의

DohaMusic의 장기 제품 목표는 다음 다섯 책임을 하나의 창작 경험으로 결합하는 것이다.

```text
DohaMusic
= AI-native DAW
+ Project / Composition Runtime
+ Provider Orchestrator
+ Composition Evaluation / QA
+ Continuous Learning Hub
```

이 정의는 목표 상태다. 현재 저장소가 완성된 DAW, 완성곡 QA 시스템 또는 학습 Hub를 구현했다는 뜻이 아니다.

## 2. CURRENT — 현재 구현

현재 DohaMusic은 로컬 단일 사용자용 기능 검증 MVP다.

- Next.js Responsive Studio와 `generation`, `lyrics`, `voice`, `history`, `projects`, `result`, `settings` 화면이 있다.
- 음악 설정·가사·Voice Profile·최종 확인을 거쳐 기존 Pipeline을 요청하고 상태·취소·재시도·결과 WAV 재생과 다운로드를 제공한다.
- Project·History와 AssetVersion 기반 CompositionSnapshot Application/API 기반이 존재한다.
- 최종 WAV의 품질 지표·예상 Tempo·후렴 후보를 분석한다.
- 실제 Mixer 엔진은 Pipeline 내부 처리 단계로 존재하지만 다중 Track Mixer UI는 아니다.
- 화면의 waveform 표현과 Player seek는 결과 재생 보조 기능이며 편집 가능한 DAW Timeline이 아니다.
- Common AI Contract Python 소비는 opt-in `RightsMetadata` 검증에 한정되고 Runtime·DB·Provider에는 연결되지 않았다.

Phase 8의 `[완료]`는 위 로컬 Responsive Studio MVP DoD를 충족했다는 뜻이다. 아래 TARGET의 DAW 기능 완료를 뜻하지 않으며 기존 완료 이력은 소급 변경하지 않는다.

## 3. TARGET — 장기 제품 상태

### 3.1 AI-native DAW

사용자는 Timeline과 Arrangement에서 Section, Track, Clip, Waveform과 Playhead를 보며 곡을 편집한다. 범위 선택 후 자연어로 변경을 요청하고 후보를 비교·선택하며, 모든 선택은 새 AssetVersion과 CompositionSnapshot으로 보존된다.

목표 편집 범위는 다음과 같다.

- playback, pause, stop, seek
- range selection
- split, trim, move, copy, delete
- fade, gain, loop
- undo, redo
- Volume, Pan, Mute, Solo
- Mixer와 Export

### 3.2 Project / Composition Runtime

Project는 창작 작업의 소유 범위이고 CompositionSnapshot은 특정 시점의 정확한 AssetVersion 조합과 설정을 가리키는 불변 재현 단위다. 편집과 AI 결과 선택은 기존 Version을 덮어쓰지 않고 새 AssetVersion과 새 CompositionSnapshot을 만든다.

### 3.3 Provider Orchestrator

DohaMusic만 전체 Workflow, 사용자 권한, 선택, Version, Mix와 Export를 조정한다. DohaLM, DohaAudio와 DohaVocal은 서로 직접 호출하지 않고 Provider 결과 후보를 반환한다. 신규 AI 기능은 Pipeline Orchestrator와 Workspace Job 경계를 우회하지 않는다.

### 3.4 Composition Evaluation / QA

완성곡 또는 선택된 CompositionSnapshot을 다음 영역에서 분석하고 사람이 이해할 수 있는 QA Report와 수정 계획을 제공한다.

- Structure
- Audio Quality
- Tempo / Key
- Hook / Arrangement
- Vocal
- Similarity
- Mix / Master
- Lyrics
- Lineage / Rights
- Human-readable QA Report

평가 이슈는 Studio의 정확한 Track·Section·시간 범위로 이동할 수 있어야 하며, 수정 뒤 새 Snapshot을 다시 평가한다.

### 3.5 Continuous Learning Hub

Reference 분석, 가사 수정, Track·Section·Mix 편집, 후보 선택과 평가 기반 수정은 검토 가능한 학습 후보가 될 수 있다. 저장되었다는 이유만으로 학습에 사용하지 않는다.

```text
프로젝트 저장 ≠ LearningCandidate
LearningCandidate ≠ DatasetVersion 포함
DatasetVersion 포함 ≠ TrainingRun 허용
TrainingRun 성공 ≠ 모델 승인 또는 Runtime 승격
```

Rights, review, eligibility와 immutable lineage Gate를 모든 단계에서 유지한다.

## 4. NOT IMPLEMENTED — 이번 기준의 미구현 범위

다음은 문서화된 TARGET이며 현재 완료가 아니다.

- 편집 가능한 Timeline·Arrangement·Track·Clip 데이터와 UI
- 범위 편집, split·trim·move·copy·delete, fade·loop, undo·redo
- 다중 Track Volume·Pan·Mute·Solo와 DAW Mixer UI
- AI Music Director와 Candidate A/B 선택 Workflow
- Reference panel과 ReferenceAnalysis 실행 Workflow
- 가사 수정·Composition Version을 함께 탐색하는 통합 이력
- Composition Evaluation / QA 실행·Report·이슈 deep-link·Re-Evaluation
- Continuous Learning 수집·검토·Dataset 연결
- DohaLM Frontend 제거
- MP3·FLAC를 포함한 독립 Export Asset Workflow

이 문서 작업은 코드, DB, Alembic, Runtime, Provider, Training, Dataset 또는 Common Contract schema를 변경하지 않는다.

## 5. 제품 흐름

### 5.1 Reference

```text
허용된 Reference Audio
→ ReferenceAnalysis
→ FeatureRecord
→ DohaLM planning context
```

링크가 있다는 사실만으로 다운로드하거나 분석하지 않는다. `RightsMetadata.analysis_allowed`와 접근 정책을 먼저 확인한다. Reference Audio와 FeatureRecord를 분리하고, 분석 권리와 Training 권리를 별도로 판정한다. 분석 JSON은 창작 Context이지 원본 Audio나 자동 학습 허가가 아니다.

### 5.2 Creation

```text
사용자 / DohaLM
→ MusicIntent
→ DohaAudio / DohaVocal
→ Artifact
→ AssetVersion
→ CompositionSnapshot
```

### 5.3 DAW Editing

```text
TimelineSelection + 사용자 지시
→ DohaLM
→ MusicIntent
→ Provider
→ 결과 후보
→ 사용자 선택
→ AssetVersion
→ 새 CompositionSnapshot
```

AI 편집 의도를 나타내는 새 공통 `EditIntent`를 만들지 않는다. `TimelineSelection`은 화면에서 선택한 대상과 범위를 전달하는 DohaMusic 제품 개념이며, DohaLM이 기존 `MusicIntent`로 materialize한다.

### 5.4 Composition QA

```text
CompositionSnapshot
→ CompositionEvaluationRun
→ Audio / Vocal 분석
→ SimilarityReport
→ 사람이 읽는 QA Report
→ RevisionPlan
→ MusicIntent
→ 수정
→ 새 CompositionSnapshot
→ Re-Evaluation
```

`CompositionEvaluationRun`은 완성곡 QA 실행을 가리키는 DohaMusic product-domain object 후보다. 아직 Common Contract 신규 schema, DB Entity 또는 Public API로 확정하지 않는다.

기존 `EvaluationRun`은 TrainingRun의 checkpoint/model을 고정 Dataset·metric·human review로 평가하는 공통 계약이다. 완성곡 QA 의미로 변경하거나 재사용하지 않는다.

### 5.5 Continuous Learning

```text
Reference 분석 + 가사 수정 + Track/Section/Mix 편집
+ 후보 선택 + 평가 기반 수정
→ LearningCandidate
→ RightsMetadata
→ TrainingEligibility
→ DatasetVersion
→ TrainingRun
→ EvaluationRun
```

## 6. 용어와 계약 정합성

기준 authority는 `DohaStudio/.github` Common AI Contract 병합 commit `dd75fc88c16e9ae9a04acfafb72756a905f6365b`이다. 일부 항목은 Python package schema이고 일부는 같은 authority의 제안 Specification이다. DohaMusic은 이름이 같다는 이유만으로 로컬 schema를 만들거나 Runtime 연결을 추정하지 않는다.

| 개념 | authority와 재사용 원칙 | DohaMusic에서의 상태 |
|---|---|---|
| `MusicIntent` | 공통 Specification 재사용. `project_id`, `asset_version_id`, `track_id`, `section_id`, `time_range`를 우선 사용 | TARGET, Runtime 미연결 |
| `RevisionPlan` | Similarity 또는 Music QA의 수정 계획으로 재사용 | TARGET, Runtime 미연결 |
| `SimilarityReport` | 창작 지원용 기술 분석. 법적 표절·침해 판정이 아님 | TARGET, Runtime 미연결 |
| `ReferenceAnalysis` | 허용된 Reference Audio의 분석 identity | TARGET, Runtime 미연결 |
| `FeatureRecord` | 원본과 분리된 versioned 분석 결과 | TARGET, Runtime 미연결 |
| `LearningCandidate` | 검토 후보. Dataset 포함이나 학습 허용을 뜻하지 않음 | TARGET, Runtime 미연결 |
| `RightsMetadata` | 분석·학습·재배포·보관 권리를 목적별로 분리 | opt-in 검증만 구현 |
| `TrainingEligibility` | Candidate의 특정 목적 Dataset draft inclusion Gate | TARGET, Runtime 미연결 |
| `DatasetVersion` | 승인 Candidate 집합을 동결한 불변 학습 입력 | TARGET, DohaMusic 연결 미구현 |
| `TrainingRun` | 고정 DatasetVersion과 설정의 단일 학습 실행 | Provider 소유 TARGET |
| `EvaluationRun` | TrainingRun/checkpoint/model 평가 전용 | Composition QA에 재사용 금지 |
| `TimelineSelection` | Track·Section·시간 범위를 담는 DohaMusic UI/product context | product-only 후보, schema 미확정 |
| `CompositionEvaluationRun` | CompositionSnapshot 완성곡 QA 실행 | product-only 후보, schema 미확정 |

현재 `MusicIntent.target`으로 표현할 수 없는 Clip 또는 음악 격자 정밀도가 실제 구현에서 입증될 때만 `clip_id`, `bar_range`, `beat_range`의 Common Contract 최소 확장을 검토한다. 이번 단계에서는 해당 필드를 정의하거나 schema 변경을 요청하지 않는다.

## 7. 제품 안전 원칙

- AI 후보는 사용자가 선택하기 전 현재 Composition을 바꾸지 않는다.
- 모든 편집·수정·재평가는 불변 Version과 lineage를 남긴다.
- Reference 분석 가능 권리와 Training 권리는 분리한다.
- Similarity 점수만으로 법적 결론, 게시 차단 또는 학습 정답을 만들지 않는다.
- Provider는 Workspace 자산, 사용자 선택, Mix 또는 Export를 직접 변경하지 않는다.
- 미구현 기능은 UI와 문서에서 `TARGET` 또는 `NOT IMPLEMENTED`로 표시한다.

## 8. 해결한 문서 모순

| 기존 혼동 | 정합화 결과 |
|---|---|
| `Phase 8 Studio 완료`가 장기 DAW 완료처럼 읽힘 | 로컬 Responsive Studio MVP 완료로 범위를 한정하고 DAW Product Track을 분리 |
| Frontend의 step `timeline`과 Player `waveform`이 DAW 편집 기능처럼 읽힘 | 현재 단계 navigation·재생 보조와 TARGET Track/Clip Timeline을 분리 |
| Pipeline `DefaultAudioMixer` 완료가 다중 Track Mixer UI 완료처럼 읽힘 | 현재 DSP 처리 단계와 TARGET Volume·Pan·Mute·Solo UI를 분리 |
| 전문 DAW 편집이 영구 비목표처럼 기록됨 | 현재 MVP 비목표이지만 장기 AI-native DAW TARGET임을 명시 |
| Frontend 정보 구조에서 Project가 Backend 선행으로 남음 | 현재 구현된 History·Project 화면과 API 연결 상태로 수정 |
| AI 편집용 새 공통 객체가 필요해 보임 | 신규 `EditIntent`를 금지하고 기존 `MusicIntent` 재사용으로 통일 |
| 완성곡 QA가 공통 `EvaluationRun`을 사용할 수 있어 보임 | Training 평가 의미를 보존하고 `CompositionEvaluationRun` product-only 후보로 분리 |
| 프로젝트 저장이 학습 데이터로 자동 승격될 수 있어 보임 | Candidate·Rights·Eligibility·Dataset·Training Gate를 각각 분리 |

## 9. ADR 영향

기존 ADR-002, ADR-012, ADR-017, ADR-028~033의 모듈·Orchestrator·Frontend·Provider·Workspace 경계를 유지한다. 이번 작업은 제품 목표와 미구현 경계를 정리하는 문서 PR이며 Runtime·schema의 되돌리기 어려운 결정을 확정하지 않으므로 새 ADR을 만들지 않는다. Track·Clip identity, edit/undo 계약, `CompositionEvaluationRun` 수명주기 또는 Learning opt-in을 구현할 때는 각각 새 ADR 필요성을 다시 검토한다.
