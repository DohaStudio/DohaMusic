# 아키텍처 결정 기록

> 문서 목적: 중요한 결정과 근거, 재검토 조건을 추적한다.
> 현재 상태: **운영 중**

| ADR | 결정 | 상태 |
|---|---|---|
| [ADR-001](ADR-001-pretrained-model-strategy.md) | 공개 사전학습 모델 우선 | 승인 제안 |
| [ADR-002](ADR-002-modular-ai-pipeline.md) | 모듈형 AI 파이프라인 | 승인 |
| [ADR-003](ADR-003-async-job-processing.md) | 비동기 작업 처리 | 승인 |
| [ADR-004](ADR-004-personal-voice-data-policy.md) | 개인 음성 데이터 정책 | 승인 제안 |
| [ADR-005](ADR-005-ai-worker-dependency-isolation.md) | AI Worker 의존성 격리 | 승인 |
| [ADR-006](ADR-006-ace-step-primary-provider.md) | ACE-Step 1차 Provider 채택 | 보류됨 |
| [ADR-007](ADR-007-ace-step-runtime-lifecycle.md) | ACE-Step 작업별 격리 subprocess 유지 | 채택됨 |
| [ADR-008](ADR-008-stem-separation-provider.md) | HTDemucs Stem Provider와 출력 계약 | 채택됨 |
| [ADR-009](ADR-009-seed-vc-voice-provider.md) | Seed-VC 격리형 Voice Provider와 참조 음성 경계 | 검증용 채택, 운영 보류 |
| [ADR-010](ADR-010-voice-provider-selection-policy.md) | Voice Provider 수명주기와 운영 승격 기준 | 승인 |
| [ADR-011](ADR-011-voice-provider-selection.md) | Voice Provider 평가와 역할 선정 | Primary 미선정, 운영 통합 보류 |
| [ADR-012](ADR-012-pipeline-orchestrator.md) | Mock 기반 Pipeline Orchestrator와 단계 정책 | 승인 |
| [ADR-013](ADR-013-audio-mixing-engine.md) | Default Audio Mixer의 gain·headroom·limiter·normalization·metadata 정책 | 승인 |
| [ADR-014](ADR-014-lyrics-generator-architecture.md) | LyricsGenerator·Template Provider·Validator·DB·Pipeline 경계 | 승인 |
| [ADR-016](ADR-016-local-lyrics-llm-finetuning.md) | 공개 Instruct LLM·QLoRA SFT·`local_llm` Adapter와 운영 승격 게이트 | 계획 승인, 구현 보류 |

결정 변경 시 기존 문서를 삭제하지 않고 상태와 대체 ADR 링크를 갱신한다.
# Phase 6.5

- [ADR-015 — External Lyrics LLM Provider](ADR-015-external-lyrics-llm-provider.md): OpenAI Responses API Adapter를 Experimental로 추가하고 Template 기본값, strict Schema, retry·fallback·비용·데이터 경계를 결정한다.

# Phase 6.6~6.9

- [ADR-016 — Local Lyrics LLM Fine-tuning](ADR-016-local-lyrics-llm-finetuning.md): 공개 Instruct LLM과 QLoRA SFT를 사용하고 기존 Adapter 경계와 검증 전 `template` 기본값을 유지한다.
