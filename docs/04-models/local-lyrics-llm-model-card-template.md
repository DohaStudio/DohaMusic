# Local Lyrics LLM Model Card Template

> 문서 상태: [템플릿]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 6.7~6.9 Local Lyrics LLM

## 식별 정보

- Model ID·version:
- 상태: `[후보]` / `[Experimental]` / `[승인]` / `[보류]`
- Base Instruct Model·정확한 revision:
- Tokenizer·revision:
- LoRA Adapter ID·hash 또는 병합 모델 hash:
- 관련 Dataset version:
- 관련 commit·PR·experiment:

## 라이선스·권리

- Base code·weight·Tokenizer license:
- 상업 이용·재배포·파생 모델 조건:
- Dataset Card·권리 승인:
- required notice·attribution:
- 법률 검토 상태:

## 학습 설정

- 방식: QLoRA SFT 후보
- 환경·GPU·VRAM:
- seed:
- batch·gradient accumulation:
- sequence length:
- learning rate·scheduler:
- epoch·step:
- LoRA target·rank·alpha·dropout:
- quantization·dtype:
- checkpoint 정책·실패·OOM:
- 실행 명령과 재현 절차:

## 평가

- Validation loss:
- JSON 구조 준수율:
- LyricsValidator 통과율·빈 출력률:
- section·한국어·주제·장르·분위기·키워드·후렴·반복·수정 지시:
- Template·OpenAI Experimental 비교:
- 응답 시간·peak VRAM·실패율·재현성:
- 사용자 blind 평가:

## 제한·위험

- 권장·금지 용도:
- hallucination·반복·암기·권리 위험:
- 알려진 실패 사례:
- 개인정보·음성 데이터 포함 여부:

## 운영

- `LocalLyricsLLMAdapter` 호환성:
- runtime·model/adapter path 설정:
- timeout·오류·rollback:
- `template` fallback 정책:
- 운영 승인자·승인일:
- 재검토 조건:
