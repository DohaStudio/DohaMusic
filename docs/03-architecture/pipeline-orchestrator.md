# Pipeline Orchestrator

> 문서 상태: [완료]
> 최종 수정일: 2026-08-01
> 관련 기능: Phase 5 Pipeline / Phase 5.1 Mixer / K3.1 Quality / K3.2 Tempo
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

## K3 비차단 후처리 계약 [구현 완료: K3.1·K3.2]

K3.1·K3.2는 다음 경계를 구현했다.

```text
ExportStep(final.wav)
→ Final WAV 성공 경계
→ Audio Analysis(독립 status, 비차단)
→ Preview Export(독립 status)
→ Result metadata 최종화
```

최종 WAV·기본 metadata·file row와 Pipeline `COMPLETED`를 먼저 확정하고 `PENDING` 분석 metadata를 둔다. 그 뒤 `DefaultAudioQualityAnalyzer`와 `DefaultTempoAnalyzer`가 final file role의 WAV를 독립적으로 읽어 기존 `audio_analysis` key만 병합한다. 요청 BPM은 오차와 half/double 후보 비교에만 쓰고 Tempo estimator를 유도하지 않는다. 분석 예외·DB 갱신 오류는 Worker 실패 경계 밖에서 처리하므로 Job과 final WAV capability를 되돌리지 않는다. 새 Pipeline step·DB table·Migration·Provider 의존성은 없다. Preview는 K3.4 계획이다.

세부 실패·Cancel·Retry 계약은 [Audio Analysis 실패 정책](audio-analysis-failure-policy.md), 저장 계약은 [결과 계약](audio-analysis-result-contract.md), 결정은 [ADR-023](../11-decisions/ADR-023-audio-analysis-and-preview-architecture.md)을 따른다.

## 재시도·timeout·오류

- 기본 재시도: 단계별 1회, 환경 변수로 0~5회 조정
- Provider·timeout 오류: 재시도 가능
- Validation·Output 오류: 재시도하지 않음
- 실제 AI subprocess 중단: 기존 Adapter timeout이 담당
- Orchestrator timeout: 단계 반환 시간이 제한을 넘으면 실패로 기록
- 실패 시: 단계·attempt·코드 기록, 부분 오디오 제거, 실패 metadata만 보존

공통 오류는 `PipelineError`, `StepError`, `ProviderError`, `StepTimeoutError`, `ValidationError`, `OutputError`로 분리한다. API에는 내부 예외나 경로를 노출하지 않는다.

## Cancel·Retry

`PENDING` 취소는 즉시 `CANCELLED`로 확정한다. 실행 중 취소는 DB에 `CANCEL_REQUESTED`를 먼저 commit하고 Worker가 Job 시작 전, 각 단계 시작 전·완료 후, 결과 metadata·파일 저장 전에 확인해 `CANCELLED`로 확정한다. 부분 출력은 정리하고 최종 Result는 공개하지 않는다.

Provider subprocess의 process handle을 Job ownership과 함께 추적하지 않으므로 이번 로컬 MVP는 강제 terminate·kill을 수행하지 않는다. 현재 단계가 반환된 뒤 취소된다는 한계를 사용자에게 안내한다.

Retry는 실패·취소 Job의 공개 입력 Snapshot을 `PipelineCreate`로 다시 검증해 새 `PENDING` Job을 만든다. 원본 상태는 변경하지 않고 `retry_of_job_id`로 관계를 기록하며 같은 원본의 중복 요청은 기존 새 Job을 반환한다.

K3 Retry는 새 음악·새 WAV·새 분석을 수행하고 기존 분석 결과를 복사하지 않는다. 동일 WAV만 다시 분석하는 Re-analysis는 Retry와 다른 후속 기능이며 K3 MVP API에는 포함하지 않는다. Final WAV 성공 경계 뒤 분석 취소는 분석/Preview만 중단하고 완성곡은 보존하는 목표 계약이다.
