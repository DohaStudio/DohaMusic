# Pipeline Orchestrator

> 문서 상태: [완료]
> 최종 수정일: 2026-07-29
> 관련 기능: Phase 5 Mock AI Workflow / Phase 5.1 실제 Audio Mixer
> 관련 문서: [ADR-012](../11-decisions/ADR-012-pipeline-orchestrator.md), [ADR-013](../11-decisions/ADR-013-audio-mixing-engine.md), [Pipeline API](../06-api/pipeline-api.md), [EXP-005](../../reports/experiments/EXP-005-pipeline-execution.md), [EXP-006](../../reports/experiments/EXP-006-audio-mixing.md)

## 책임과 경계

`PipelineService`는 Job 생성·조회만 담당하고 `PipelineWorker`가 `PipelineExecutor`를 실행한다. Executor는 선언된 `PipelineStep`만 순서대로 호출하며 AI 구현이나 특정 모델 라이브러리를 직접 참조하지 않는다.

```text
POST /api/pipelines
  → PipelineService → pipeline_jobs(PENDING)
  → shared ThreadPool → PipelineWorker
  → GenerateMusicStep       20%
  → StemSeparationStep      40%
  → VoiceConversionStep     60%
  → MixStep                 80%
  → ExportStep             100%
  → pipeline_files + metadata.json
```

Music·Stem·Voice 단계는 각각 `MusicGenerator`, `StemSeparator`, `VoiceConverter` 인터페이스만 사용한다. 애플리케이션 시작 시 선택된 기존 Provider가 그대로 주입된다. Voice 기본값은 `mock`이며 Primary Provider가 승인되기 전까지 운영 Provider로 자동 전환하지 않는다.

## Context와 결과

`PipelineContext`는 prompt, lyrics, seed, 동의된 Voice Profile과 단계별 파일 경로를 전달한다. 단계가 완료될 때 다음 단계 입력만 채우며 전역 상태나 AI Adapter 내부 객체를 노출하지 않는다.

성공 시 `music`, `vocals`, `instrumental`, `converted_voice`, `final`, `metadata` 파일을 등록한다. 기본 `DefaultAudioMixer`는 변환 보컬과 반주를 실제 합성하고 48kHz Stereo PCM16, -1dBFS headroom, peak normalization, soft limiter와 fade를 적용한다. `MockAudioMixer`는 명시적 설정에서만 복사 기반 계약 검증에 사용한다.

Mixer의 gain·quality·clipping·CPU·RSS·처리 시간은 Pipeline `result_metadata.step_execution[].details.audio_quality`와 최종 `metadata.json`에 기록한다. True Peak는 현재 미지원이므로 지원 여부를 거짓 없이 별도 필드로 표시한다.

## 재시도·timeout·오류

- 기본 재시도: 단계별 1회, 환경 변수로 0~5회 조정
- Provider·timeout 오류: 재시도 가능
- Validation·Output 오류: 재시도하지 않음
- 실제 AI subprocess 중단: 기존 Adapter timeout이 담당
- Orchestrator timeout: 단계 반환 시간이 제한을 넘으면 실패로 기록
- 실패 시: 단계·attempt·코드 기록, 부분 오디오 제거, 실패 metadata만 보존

공통 오류는 `PipelineError`, `StepError`, `ProviderError`, `StepTimeoutError`, `ValidationError`, `OutputError`로 분리한다. API에는 내부 예외나 경로를 노출하지 않는다.

`CANCELLED` 상태는 상태 계약에 예약했지만 취소 API와 실행 중 강제 중단은 구현하지 않았다.
