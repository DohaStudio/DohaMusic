# AI 파이프라인

> 문서 목적: 생성 단계, 산출물, 실패 경계와 공통 모델 인터페이스를 정의한다.
> 현재 상태: **설계 초안 / 모델 미선정**

```mermaid
flowchart LR
  V[입력 검증] --> G[음악 생성]
  G --> S[Stem 분리]
  S --> C[음색 변환]
  C --> M[믹싱]
  M --> E[인코딩]
  E --> P[메타데이터 확정]
```

## 인터페이스 경계

```python
from pathlib import Path
from typing import Protocol

class MusicGenerator(Protocol):
    def generate(self, prompt: str, lyrics: str | None,
                 duration_seconds: int, seed: int | None) -> Path: ...

class StemSeparator(Protocol):
    def separate(self, audio_path: Path) -> tuple[Path, Path]: ...

class VoiceConverter(Protocol):
    def convert(self, source_vocal_path: Path,
                reference_voice_path: Path) -> Path: ...

class AudioMixer(Protocol):
    def mix(self, vocal_path: Path, instrumental_path: Path) -> Path: ...
```

이 경계는 서비스가 특정 모델의 함수명·입출력 구조·로딩 방식에 종속되는 것을 막는다. 어댑터는 입력 정규화, 모델 실행, 출력 검증, 모델별 오류 변환만 책임지고 작업 상태·권한·저장 정책은 Orchestrator가 담당한다.

모델은 단계별로 로드하고 사용 후 해제한다. 각 단계는 입력·출력 경로, 해시, 모델·버전, 시간, 최대 VRAM, 오류를 기록한다. 재시도 정책은 [작업 상태 모델](../07-database/job-state-model.md)을 따른다.
