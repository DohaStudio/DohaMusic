# 모델 선정 정책

> 문서 목적: 모델을 도입·보류·교체하는 객관적 게이트를 정의한다.
> 현재 상태: **ACE-Step 기술 반복 게이트 통과 / 사용자 품질 게이트 대기**
> 최종 수정일: 2026-07-31

제품 기본 모델은 다음을 모두 충족해야 한다.

1. 공식 출처와 정확한 버전을 고정한다.
2. 코드·가중치·주요 의존성의 라이선스와 배포 고지를 확인한다.
3. 공통 Adapter 계약과 오류 계약을 충족한다.
4. 한국어 발음·가사 정렬·음악성과 실패 사례를 수동 청취로 기록한다.
5. RTX 3060 Ti 8GB에서 반복 시간·VRAM·해제·OOM 경계를 측정한다.
6. 모델·로그·출력의 보안 및 권리 요구사항을 충족한다.

ACE-Step 1.5 v0.1.8은 1, 3과 반복 실행 기준 5를 통과했고, 2는 기술적 1차 확인 상태다. 고정 환경 동일 Seed PCM 재현, 다른 Seed 파형 차이와 상주 suite 12/12 성공을 확인했다. 그러나 4와 법률 승인이 남고 상주 CPU 메모리 증가가 있어 `ace_step`은 선택적 Provider, 기본값은 `mock`이다. [ADR-006](../11-decisions/ADR-006-ace-step-primary-provider.md)은 사용자 평가 전 채택을 보류한다.

## Local Lyrics LLM 선정 정책

- 기반 구조를 새로 설계하거나 대규모 사전학습하지 않고 공개 사전학습 Instruct LLM을 사용한다.
- 우선 검토 후보는 Qwen 계열 1.7B~4B Instruct다. 이름과 크기는 후보이며 공식 버전·가중치 라이선스·상업 이용·재배포 조건 확인 전 확정하지 않는다.
- 1차 학습 방식은 QLoRA 기반 Supervised Fine-tuning이다. Full Fine-tuning은 RTX 3060 Ti 8GB에서 메모리·시간·안정성 근거가 없으므로 기본 전략으로 사용하지 않는다.
- 한국어 중심 가사 생성과 기존 입력 8종, `LyricsGenerator` 결과 계약, JSON Schema, `LyricsValidator` 규칙을 공통 비교 기준으로 사용한다.
- Dataset의 출처·라이선스·권리·가공 계보와 Train·Validation·Test 분리가 승인되기 전에는 학습하지 않는다.
- `local_llm` Provider는 Template·OpenAI Experimental과 동일한 평가 세트로 품질·응답 시간·VRAM·반복 안정성을 측정한다.
- 검증 전 기본 Provider는 `template`이며 `local_llm`을 운영 Pipeline, 자동 fallback 또는 Stable 역할로 승격하지 않는다.

세부 결정은 [ADR-016](../11-decisions/ADR-016-local-lyrics-llm-finetuning.md), Phase별 게이트는 [Local Lyrics LLM 계획](../../planning/phase-6-local-lyrics-llm-plan.md)을 따른다.
