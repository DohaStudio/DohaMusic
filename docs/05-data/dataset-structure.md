# 데이터셋 구조

> 문서 목적: 향후 개인화 실험 데이터의 논리 구조와 분리 원칙을 정의한다.
> 현재 상태: **Phase 7 계획 / 데이터 미수집**

```text
dataset/{dataset_id}/
├─ manifest.jsonl
├─ audio/{sample_id}.wav
├─ transcripts/{sample_id}.txt
└─ splits/{train,validation,test}.txt
```

Manifest는 sample_id, 소유자, 동의 기록 ID, 오디오 해시, 언어, 전사, 가창/말하기, 품질 플래그, 전처리 버전을 가진다. 실제 사용자 식별자는 학습 경로에 직접 노출하지 않는다. 철회된 샘플은 모든 split과 파생 캐시에서 제외하고 데이터셋 버전을 갱신한다.
