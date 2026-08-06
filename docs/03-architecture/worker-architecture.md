# Worker 아키텍처

> 현재 상태: 공유 단일 ThreadPool + 생성·Stem·Voice·Pipeline Provider-neutral Worker 구현

API는 Job을 `PENDING`으로 저장하고 ID만 dispatcher에 제출한다.

- Generation: `PENDING → VALIDATING → GENERATING → COMPLETED|FAILED`
- Stem: `PENDING → VALIDATING → STEM_SEPARATING → COMPLETED|FAILED`
- Voice: `PENDING → VALIDATING → VOICE_CONVERTING → COMPLETED|FAILED`
- Pipeline: `PENDING → VALIDATING → GENERATING → STEM_SEPARATING → VOICE_CONVERTING → MIXING → EXPORTING → COMPLETED|FAILED`

`VoiceConversionWorker`는 source가 `stem_files.file_type=vocals`인지, Voice Profile 동의가 참인지, 참조 파일이 `voices/references` 안에 있는지 검사한다. 결과는 `converted_voice`와 `metadata`로 등록한다. AI 오류는 `VOICE_*` 안정 코드로 저장하고 내부 stack trace는 로그에만 남긴다.

ACE-Step, Demucs, Seed-VC는 작업별 격리 subprocess를 사용하며 요청 중 모델을 자동 다운로드하지 않는다. 모든 AI dispatcher는 GPU 동시성 1인 executor를 공유한다. Pipeline은 단계별 기본 1회 재시도와 오류 귀속을 제공한다. 외부 Queue, crash recovery, 취소 API와 다중 GPU는 후속 범위다.
