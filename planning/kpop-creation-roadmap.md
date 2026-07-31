# K-POP Creation Control Roadmap

> 문서 상태: [진행 중]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 8 이후 K-POP 제품 고도화 Track
> 관련 문서: [제품 정의](../docs/02-product/kpop-creation-product-definition.md), [ADR-022](../docs/11-decisions/ADR-022-kpop-generation-control-layer.md), [EVAL-007](../reports/evaluations/EVAL-007-kpop-dance-generation.md)

이 Track은 완료된 Phase 8을 되돌리지 않으며 Phase 9 공개 운영 준비와 병렬로 진행할 수 있다.

## K0 — 문서·계약 [완료]

- [x] 제품 정의와 Preset 3종
- [x] Generation Options와 validation 초안
- [x] Prompt Compiler·Lyrics Template 설계
- [x] Provider Capability Matrix
- [x] 평가·Dataset 정책·ADR

차단 조건: 계약 간 필드·상태 불일치, 현재 기능과 계획 기능의 혼동, 권리 정책 누락.

## K1 — Preset MVP [계획]

- [ ] Preset 3종과 `KPopPromptCompiler` 구현
- [ ] K-POP Lyrics Template 연결
- [ ] Frontend Preset·Mood·Concept·30/60초·Hook phrase UI
- [ ] 기존 Pipeline 요청으로 컴파일된 Prompt 전송
- [ ] 기존 요청 회귀·Desktop·Mobile 검증

DoD: 기존 API 호환, 특정 아티스트 모방 차단, Prompt Preview·compiler version·테스트·문서 완료. 미지원 세부 옵션은 활성화하지 않는다.

## K2 — Structured Options [계획]

- [ ] optional `generation_options` DTO·검증·Snapshot
- [ ] requested BPM·language ratio·Hook·Post-Chorus·vocal energy
- [ ] Capability API와 capability 기반 UI
- [ ] 원본·정규화 옵션·warning 추적

DoD: silent ignore 없음, Public DTO 내부 정보 비노출, legacy 요청 동일 동작, migration·API·Frontend·E2E 검증 완료.

## K3 — Analysis [계획]

- [ ] detected BPM·first chorus time·Hook timestamp
- [ ] 15초 Preview
- [ ] LUFS·True Peak

DoD: 분석 정확도 기준과 실패·fallback 정책, 비파괴 원본 보존, 자동·청취 평가 근거 완료. 구현 전에는 값과 UI를 제공하지 않는다.

## K4 — Model Adaptation [계획]

- [ ] 권리 확인 Style Dataset
- [ ] Style LoRA 후보 평가
- [ ] Doha Voice 개인화 Track 연계
- [ ] Local Lyrics LLM Track 연계

DoD: Dataset manifest·라이선스·동의·분리, RTX 3060 Ti 8GB 실측, Adapter 격리, Quality Gate 통과. Music Style·Voice·Lyrics 학습을 하나의 Dataset이나 모델로 합치지 않는다.

## 구현 순서

K1 Preset MVP → K2 Structured Options → K3 Analysis → K4 Model Adaptation 순서다. 각 단계는 별도 PR로 구현하며 K0 문서 완료를 기능 완료로 표시하지 않는다.
