# 데이터셋 구조

> 문서 목적: 향후 개인화 실험 데이터의 논리 구조와 분리 원칙을 정의한다.
> 현재 상태: **Phase 7 계획 / 데이터 미수집**
> 최종 수정일: 2026-08-05
> 관련 문서: [로컬 Dataset·Artifact 정책](local-dataset-artifact-policy.md), [저장소와 Provider 경계](../03-architecture/repository-provider-boundaries.md)

```text
dataset/{dataset_id}/
├─ manifest.jsonl
├─ audio/{sample_id}.wav
├─ transcripts/{sample_id}.txt
└─ splits/{train,validation,test}.txt
```

Manifest는 sample_id, 소유자, 동의 기록 ID, 오디오 해시, 언어, 전사, 가창/말하기, 품질 플래그, 전처리 버전을 가진다. 실제 사용자 식별자는 학습 경로에 직접 노출하지 않는다. 철회된 샘플은 모든 split과 파생 캐시에서 제외하고 데이터셋 버전을 갱신한다.

위 구조는 논리 예시이며 checkout 내부 경로가 아니다. 실제 Dataset과 Artifact는 Git 밖의 환경 변수 주입 root에서 관리하고 manifest에는 상대 경로 또는 논리 ID만 기록한다. Lyrics Dataset·Music Dataset·Vocal Dataset은 각각 DohaLM·DohaAudio·DohaVocal이 기술적으로 관리한다. 음성 동의·소유권·접근 권한과 삭제 결정은 DohaMusic에 유지한다.
