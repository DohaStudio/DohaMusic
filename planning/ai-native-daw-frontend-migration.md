# AI-native DAW Frontend 전환 계획

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-21
> 관련 기능: Responsive Studio MVP에서 AI-native DAW로의 단계적 전환
> 관련 문서: [제품 방향](../docs/02-product/ai-native-daw-product-direction.md), [목표 아키텍처](../docs/03-architecture/ai-native-daw-target-architecture.md), [D1 Composition Read 계약](../docs/06-api/composition-read-workspace.md), [기존 Frontend Roadmap](frontend-roadmap.md), [DohaLM 연동](../docs/03-architecture/dohalm-integration.md)

## 1. CURRENT — 유지할 MVP

현재 `frontend/app`에는 Landing과 `studio`, `lyrics`, `voice`, `generation/[jobId]`, `result/[jobId]`, `history`, `projects`, `projects/[id]`, `settings`, `about`가 있다. D1-B는 새 Route 없이 `projects/[id]`에 Backend-authoritative Composition read를 연결한다. 이 화면들은 다음 기능을 검증한다.

- 음악 설정·가사·Voice Profile·Review 기반 Pipeline 제출
- Lyrics 생성·검증·Revision
- Voice Profile과 Guided Voice Enrollment
- Job 진행률·Cancel·Retry
- 결과 WAV 재생·seek·download와 품질·예상 Tempo·후렴 후보 표시
- History·Project 탐색과 Result 재진입
- Project Composition의 `empty`, 명시 Snapshot 선택, `ready` Track projection·exact AssetVersion 조회

현재 화면의 `Studio`, `waveform`, `timeline`, `Mixer` 표현은 편집 가능한 DAW 구현을 의미하지 않는다. 특히 F4의 waveform과 transport는 결과 재생 경험이며 Track/Clip 편집기가 아니다.

## 2. TARGET — Frontend 정보 구조

```text
Studio
├─ Arrangement / Timeline
│  ├─ Section Marker
│  ├─ Track / Clip / Waveform
│  ├─ Playhead / Range Selection
│  └─ Edit / Undo / Redo
├─ Mixer
│  └─ Volume / Pan / Mute / Solo
├─ AI Music Director
│  ├─ TimelineSelection + instruction
│  ├─ MusicIntent preview
│  └─ Candidate A/B comparison
├─ Reference Panel
├─ Lyrics Revision History
├─ Composition Version History
└─ Export

Composition QA
├─ Structure / Audio / Tempo-Key / Hook-Arrangement
├─ Vocal / Similarity / Mix-Master / Lyrics / Rights
├─ Human-readable QA Report
├─ Issue → exact Studio track/range deep-link
└─ RevisionPlan / Re-Evaluation
```

Desktop은 Timeline·Inspector·Mixer를 동시에 제공하고 Mobile은 조회·검토·간단 조정 중심으로 단계화한다. 작은 화면에서 정밀 Clip 편집을 완전 동일하게 복제할지는 사용성 검증 뒤 결정한다.

## 3. 전환 원칙

1. 기존 MVP Route를 즉시 삭제하지 않는다.
2. Workspace Resource API와 CompositionSnapshot을 Frontend source of truth로 연결하기 전 가짜 Timeline 데이터를 만들지 않는다.
3. AI 편집 요청은 새 `EditIntent`가 아니라 승인된 `MusicIntent`를 사용한다.
4. Provider 후보를 현재 Composition에 자동 적용하지 않고 사용자 선택 뒤 새 Version으로 commit한다.
5. CURRENT 재생 waveform과 TARGET 편집 waveform을 명칭·상태·테스트에서 구분한다.
6. Composition QA와 Training model 평가는 각각 `CompositionEvaluationRun` 후보와 `EvaluationRun`으로 분리한다.
7. 미구현 action은 disabled 이유와 선행 조건을 표시한다.

## 4. 단계별 구현 Roadmap

각 단계는 독립 작업 브랜치, 구현·테스트·문서·CHANGELOG·ADR 검토와 `develop` 병합 증거가 있어야 완료된다. 이 문서 작성만으로 어떤 단계도 완료하지 않는다.

### D0 — 제품 언어와 CURRENT/TARGET 기준 [완료]

- 현재 Responsive Studio MVP와 장기 DAW 목표를 분리한다.
- Common Contract 재사용과 product-only 후보를 명시한다.
- 완료 Gate: 이 문서와 제품·아키텍처 정합성 문서 검증 및 `develop` 병합.

### D1 — Composition Read Workspace [D1-B 구현 / Draft 검토]

- Workspace v1을 Composition read authority로 사용하고 Legacy는 migration input으로만 유지한다. silent fallback과 GET 자동 backfill은 금지한다.
- Project-level explicit selected Snapshot을 current로 사용하고 latest history와 분리한다. 특정 history Snapshot query는 selection을 변경하지 않는다.
- `GET /api/v1/projects/{project_id}/composition`에서 exact AssetVersion·safe Artifact·snapshot-local Track projection, Section `not_available`, Mix JSON과 lineage를 읽는다.
- D1-A Backend aggregate read와 D1-Transition 무선택 bootstrap gate를 완료했고, D1-B는 Project 상세에서 aggregate read와 사용자 명시 선택 후 PATCH·refetch·재진입을 구현한다.
- 현재 완료 증거는 fixture 기반 empty·selection-required·ready 통합, exact AssetVersion·safe Artifact·Mix·lineage, loading·오류·접근성·반응형 검증이다.
- 남은 Gate는 실제 인증 principal의 owner/project privacy와 실제 사용자 DB 승인 후 Snapshot E2E다.

### D2 — Timeline Playback Foundation [계획]

- Arrangement, Section marker, Track/Clip, Waveform, Playhead를 읽기 전용으로 구현한다.
- playback, pause, stop, seek와 범위 선택을 Composition 시간축에 결속한다.
- Gate: 긴 오디오 성능, sample/time mapping, keyboard·screen reader, Desktop/Mobile 전략.

### D3 — Non-destructive DAW Editing [계획]

- split, trim, move, copy, delete, fade, gain, loop를 새 AssetVersion/Snapshot으로 저장한다.
- undo/redo는 불변 Version 또는 명시적 command history로 구현한다.
- Gate: 원본 불변, concurrent edit 정책, autosave·crash recovery, 정확한 export 재현.

### D4 — Mixer와 Export [계획]

- Track Volume, Pan, Mute, Solo와 Mix 설정을 연결한다.
- Preview와 최종 WAV·MP3·FLAC Export를 별도 AssetVersion/Artifact로 추적한다.
- Gate: gain/pan automation 범위, loudness·clipping, Export Job, secure download.

### D5 — AI Music Director와 Candidate Workflow [계획]

- `TimelineSelection + user instruction → DohaLM → MusicIntent` 흐름을 제공한다.
- 실행 전 대상·preserve·replace·제약과 Provider capability를 사용자에게 보여준다.
- 후보 A/B를 재생·비교하고 선택된 후보만 새 Version으로 commit한다.
- Gate: HTTP/SSE, Cancel, Retry, Readiness, 안전한 오류, idempotency, 실제 Provider E2E.

### D6 — Reference Panel [계획]

- 허용된 Reference source와 Rights 상태를 표시한다.
- ReferenceAnalysis·FeatureRecord와 DohaLM planning context를 연결한다.
- URL 임의 다운로드를 금지하고 분석·retention·Training 권리를 분리한다.
- Gate: source allowlist, 철회·삭제, feature version/confidence, 원본 비노출.

### D7 — Composition Evaluation / QA [계획]

- CompositionSnapshot 기준 QA 실행과 사람이 읽는 Report를 제공한다.
- Structure, Audio Quality, Tempo/Key, Hook/Arrangement, Vocal, Similarity, Mix/Master, Lyrics, Lineage/Rights를 표시한다.
- Issue에서 Studio의 정확한 Track·Section·시간 범위로 이동하고 RevisionPlan 승인·수정·Re-Evaluation을 연결한다.
- Gate: `CompositionEvaluationRun` 제품 계약 결정, `EvaluationRun` 의미 비충돌, metric/version/confidence, human review.

### D8 — Continuous Learning Review Hub [계획]

- 사용자가 선택적으로 Reference 분석, 가사·Track·Section·Mix 편집, 후보 선호와 QA 수정을 LearningCandidate로 제안할 수 있게 한다.
- Candidate review, RightsMetadata, TrainingEligibility, DatasetVersion 상태를 투명하게 표시한다.
- Dataset 포함이나 Training 실행을 Frontend가 자동 승인하지 않는다.
- Gate: 명시적 opt-in, privacy·retention·철회, immutable lineage, Provider별 소유 경계.

### D9 — 통합·운영 전환 [계획]

- 기존 MVP route의 parity와 migration을 검증하고 중복 UX를 단계적으로 정리한다.
- 공개 운영 인증·소유권·감사·rate limit·분산 실행·관측성을 통과한다.
- 실제 사용자 DAW 편집·QA·Export E2E와 접근성·성능 평가를 완료한다.

## 5. DohaLM Frontend Retirement Gate

DohaLM의 현재 독립 Frontend는 개발과 Runtime 검증에 필요하므로 즉시 삭제하지 않는다. 최종 목표는 DohaMusic의 AI Music Director에 UX를 통합하는 것이며, 다음 parity를 DohaMusic에서 실제 Provider E2E로 모두 검증한 뒤에만 retirement를 검토한다.

| Gate | 완료 증거 |
|---|---|
| HTTP | versioned request/response와 model identity E2E |
| SSE | start/delta/done/error와 reconnect/terminal 처리 E2E |
| Cancel | client 취소가 Provider 실행에 전파되고 안전한 terminal 상태 확인 |
| Retry | 같은 결과를 덮어쓰지 않는 새 Job/attempt와 idempotency 확인 |
| Readiness | health와 readiness 분리, model 미준비 상태 UX 확인 |
| Error handling | timeout·network·invalid response·Provider 오류의 안전한 구분 |
| real-model E2E | 승인된 실제 모델로 DohaMusic UI부터 결과/lineage까지 검증 |

추가 Gate는 다음과 같다.

- DohaLM 독립 Frontend에만 존재하는 운영·디버그 기능 Inventory와 대체 경로
- 사용 문서·운영 Runbook·rollback plan
- 사용자와 Provider 개발자의 명시적 retirement 승인

Gate 미충족 시 DohaLM Frontend는 독립 개발/Runtime 검증용으로 유지한다.

## 6. NOT IMPLEMENTED

D1 선행 계약만 확정됐고 D1~D9 Runtime은 모두 현재 미구현이다. 코드, API Runtime, DB, Common Contract, Training 또는 Provider Runtime은 이 계획 문서로 변경되지 않는다. 기존 F0~F5 완료와 F6 진행 상태도 변경하지 않는다.
