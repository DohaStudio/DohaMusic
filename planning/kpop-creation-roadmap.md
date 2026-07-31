# K-POP Creation Control Roadmap

> 문서 상태: [진행 중]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 8 이후 K-POP 제품 고도화 Track
> 관련 문서: [제품 정의](../docs/02-product/kpop-creation-product-definition.md), [K3 제품 정의](../docs/02-product/k3-audio-analysis-product-definition.md), [ADR-022](../docs/11-decisions/ADR-022-kpop-generation-control-layer.md), [ADR-023](../docs/11-decisions/ADR-023-audio-analysis-and-preview-architecture.md), [EVAL-008](../reports/evaluations/EVAL-008-audio-analysis-validation.md)

이 Track은 완료된 Phase 8을 되돌리지 않으며 Phase 9 공개 운영 준비와 병렬로 진행할 수 있다.

## K0 — 문서·계약 [완료]

- [x] 제품 정의와 Preset 3종
- [x] Generation Options와 validation 초안
- [x] Prompt Compiler·Lyrics Template 설계
- [x] Provider Capability Matrix
- [x] 평가·Dataset 정책·ADR

차단 조건: 계약 간 필드·상태 불일치, 현재 기능과 계획 기능의 혼동, 권리 정책 누락.

## K1 — Preset MVP [완료]

- [x] Preset 3종과 `KPopPromptCompiler` 구현
- [x] K-POP Lyrics Template 연결
- [x] Frontend Preset·Mood·30/60초·Prompt Preview UI — Concept·Hook phrase는 K2 이후 범위
- [x] 기존 Pipeline 요청으로 컴파일된 Prompt 전송
- [x] 기존 요청 회귀·Desktop·Mobile 검증

K1 당시에는 `prompt`, `lyrics`, `genre`, `duration_seconds`, `seed`의 기존 API 계약만 사용했다. Structured Options는 K2에서 optional 확장했으며 BPM·Hook Timestamp·Audio Analysis와 Provider 전용 제어는 K1에 포함하지 않았다.

DoD: 기존 API 호환, 특정 아티스트 모방 차단, Prompt Preview·compiler version·테스트·문서 완료. 미지원 세부 옵션은 활성화하지 않는다.

## K2 — Structured Options [완료]

- [x] optional `generation_options` strict DTO·검증·JSON Snapshot
- [x] requested BPM·language ratio·Hook·Post-Chorus·Dance Break·vocal energy·Concept
- [x] 문서·Frontend typed capability 상태와 Prompt 기반 UI — 별도 endpoint는 추가하지 않음
- [x] 원본·정규화 옵션·compiled prompt·warning·compiler version 추적
- [x] Retry 복원과 History·Project·Result 공개 allowlist

DoD: silent ignore 없음, Public DTO 내부 정보 비노출, legacy 요청 동일 동작, Migration 없음, Backend·Frontend·Desktop/Mobile E2E 검증 완료.

## K3 — Audio Analysis [진행 중]

### K3.0 — 계약·평가 문서 [완료]

- [x] 분석 대상 `final.wav`, 요청·측정·추정·제품 선택값 구분
- [x] 비차단 Pipeline 위치와 분석·Preview 독립 실패 정책
- [x] versioned Result metadata JSON·공개 allowlist·secure file 경계
- [x] confidence·Retry/Re-analysis·Cancel·cleanup 계약
- [x] 라이브러리·표준 후보와 EVAL-008 검증 계획
- [x] ADR-023 결정과 K3.1~K3.4 단계별 DoD

DoD: 제품 정의, 결과 계약, 실패 정책, 라이브러리 비교, EVAL-008, ADR-023과 관련 Roadmap·API·UX 문서가 일치한다. 기능·DTO·DB·라이브러리는 추가하지 않는다.

차단 조건: Pipeline 성공과 분석 성공의 혼동, Sample Peak/True Peak 혼동, 내부 경로 공개, confidence·fallback·cleanup 미정.

### K3.1 — Audio Quality Metrics MVP [계획]

- [ ] duration·sample rate·channels·Sample Peak
- [ ] clipping 여부·sample count·ratio
- [ ] Integrated LUFS
- [ ] True Peak는 표준/reference 검증 통과 시만 포함, 아니면 후속 유지

DoD: final WAV fixture·invalid·silence·short·mono/stereo·sample rate reference 검증, 실패 비차단, version·공개 allowlist와 성능 기록 완료.

차단 조건: ITU-R BS.1770/EBU R 128 검증 부재, oversampling 없는 값을 True Peak로 표시, library 라이선스·Windows 호환 미승인.

### K3.2 — Tempo Analysis [계획]

- [ ] detected BPM·confidence
- [ ] requested BPM signed/absolute error
- [ ] half/double-time·무박 intro·tempo change 분류

DoD: EVAL-008 ground truth 세트와 confidence calibration을 통과하고 저신뢰 결과를 추정으로 표시한다.

차단 조건: half/double 오류 미분류, confidence 근거 없음, 정확한 BPM 보장 표현.

### K3.3 — Structure·Hook Candidate [계획]

- [ ] 에너지·반복 기반 Hook 후보 1개(Stage A)
- [ ] first Chorus 후보·confidence
- [ ] 후보 없음·저신뢰 fallback

DoD: 사용자 label·temporal overlap·15초 Preview 유용성 평가와 안전한 `not_found` 처리를 통과한다.

차단 조건: Hook/Chorus 확정 표현, 권리 확보 평가 데이터 부재, 저신뢰 자동 선택.

### K3.4 — Preview Export [계획]

- [ ] final WAV 기반 15초 PCM WAV
- [ ] 신뢰 가능한 Hook 후보 또는 deterministic 중앙 fallback
- [ ] 20 ms fade, Storage·secure playback/download·cleanup

DoD: 정확한 길이·RIFF/WAVE·재생·원본 불변·fade·fallback·취소/삭제 cleanup과 기존 secure endpoint 회귀를 통과한다.

차단 조건: 원본 덮어쓰기, path 노출, secure access 우회, orphan Preview.

## K4 — Model Adaptation [계획]

- [ ] 권리 확인 Style Dataset
- [ ] Style LoRA 후보 평가
- [ ] Doha Voice 개인화 Track 연계
- [ ] Local Lyrics LLM Track 연계

DoD: Dataset manifest·라이선스·동의·분리, RTX 3060 Ti 8GB 실측, Adapter 격리, Quality Gate 통과. Music Style·Voice·Lyrics 학습을 하나의 Dataset이나 모델로 합치지 않는다.

## 구현 순서

K1 Preset MVP → K2 Structured Options → K3.0 계약·평가 문서까지 완료했다. 다음 구현은 별도 PR의 K3.1 Audio Quality Metrics MVP이며 K3.2 Tempo → K3.3 Hook Candidate → K3.4 Preview → K4 Model Adaptation 순서다. K3.0 문서 완료를 K3 기능 완료로 표시하지 않는다.
