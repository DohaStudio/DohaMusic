# Worker 아키텍처

> 현재 상태: Legacy 공유 단일 ThreadPool Worker 구현 / Workspace Worker Execution Foundation 구현 / Concrete Provider Dispatcher·DohaVocal Worker Wiring·Background Daemon 미구현

이 절의 기존 Worker는 Legacy Runtime Job을 `PENDING`으로 저장하고 ID만 dispatcher에 제출한다.

- Generation: `PENDING → VALIDATING → GENERATING → COMPLETED|FAILED`
- Stem: `PENDING → VALIDATING → STEM_SEPARATING → COMPLETED|FAILED`
- Voice: `PENDING → VALIDATING → VOICE_CONVERTING → COMPLETED|FAILED`
- Pipeline: `PENDING → VALIDATING → GENERATING → STEM_SEPARATING → VOICE_CONVERTING → MIXING → EXPORTING → COMPLETED|FAILED`

`VoiceConversionWorker`는 source가 `stem_files.file_type=vocals`인지, Voice Profile 동의가 참인지, 참조 파일이 `voices/references` 안에 있는지 검사한다. 결과는 `converted_voice`와 `metadata`로 등록한다. AI 오류는 `VOICE_*` 안정 코드로 저장하고 내부 stack trace는 로그에만 남긴다.

ACE-Step, Demucs, Seed-VC는 작업별 격리 subprocess를 사용하며 요청 중 모델을 자동 다운로드하지 않는다. 모든 AI dispatcher는 GPU 동시성 1인 executor를 공유한다. Pipeline은 단계별 기본 1회 재시도와 오류 귀속을 제공한다. 외부 Queue와 다중 GPU는 후속 범위다.

Workspace Job Worker는 이 ThreadPool 구현과 분리한다. `JobWorkerService.run_once()`의 `queued` atomic claim, claim token, Worker identity, lease·heartbeat·attempt, 내부 cancellation marker와 terminal protection은 구현됐다. concrete Provider Dispatcher, DohaVocal transport wiring과 background daemon은 구현되지 않았다. running lease 만료는 원본 row를 자동 재실행하지 않고 retryable failure로 종료하며 공개 retry는 새 Job을 만든다. Provider 성공 뒤 reconciliation의 상태·lease·retry·crash 권위는 [DohaVocal Worker Reconciliation Contract](dohavocal-worker-reconciliation-contract.md), 실행 기반은 [Workspace Job Foundation](workspace-job-foundation.md)과 [ADR-033](../11-decisions/ADR-033-workspace-job-execution-boundary.md)을 따른다.
