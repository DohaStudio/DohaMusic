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

- 전체 LLM 구조 설계·사전학습은 범위 밖이며 공개 사전학습 Instruct LLM을 사용한다.
- Qwen 계열 1.7B~4B Instruct와 동급 한국어 지원 공개 모델은 후보일 뿐 최종 선정·설치 상태가 아니다.
- Base Model 선정 전에 코드·가중치·Tokenizer의 라이선스, 상업 이용, 재배포와 파생 모델 조건을 승인한다.
- 한국어 성능, RTX 3060 Ti 8GB 추론·QLoRA 가능성, peak VRAM, Tokenizer·Transformers 호환성을 비교한다.
- 1차 학습은 QLoRA SFT를 우선 검토하며 Full Fine-tuning은 현재 기본 전략에서 제외한다.
- 학습 결과는 LoRA Adapter 또는 검증된 병합 모델로 추적하고 [Model Card template](local-lyrics-llm-model-card-template.md)을 작성한다.
- `LocalLyricsLLMAdapter`가 기존 `LyricsGenerator`와 `LyricsValidator` 계약을 유지해야 하며 승인 전 기본 Provider는 `template`이다.

세부 결정은 [ADR-016](../11-decisions/ADR-016-local-lyrics-llm-finetuning.md), 단계별 검증은 [Local Lyrics LLM Roadmap](../../planning/local-lyrics-llm-roadmap.md)을 따른다.
