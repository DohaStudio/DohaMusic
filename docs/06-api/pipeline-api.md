# Pipeline API

> 문서 상태: [완료]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 5 Pipeline Orchestrator

## 생성

`POST /api/pipelines`는 `202 Accepted`와 `PENDING` Job을 반환한다.

```json
{
  "prompt": "잔잔한 한국어 발라드",
  "lyrics": "직접 작성한 가사",
  "genre": "ballad",
  "duration_seconds": 30,
  "seed": 20260729,
  "voice_profile_id": "UUID"
}
```

`voice_profile_id`는 존재하고 동의가 확인돼야 한다. 참조 파일은 설정된 Storage의 `voices/references` 아래에 있어야 한다.

## 조회

- `GET /api/pipelines/{job_id}`: 상태, 현재 단계, 진행률, 오류, Pipeline metadata
- `GET /api/pipelines/{job_id}/files`: 성공 시 6개 결과 파일 metadata, 실패 시 진단 metadata

Files response는 `id`, `job_id`, `file_type`, `mime_type`, `created_at`, `content_available`, `download_available`만 반환한다. 서버의 절대·상대 `file_path`, Storage root, 임시·모델 경로는 반환하지 않는다. 내부 DB에는 Worker 처리를 위해 경로를 유지하지만 public DTO 경계 밖이다. 현재 content·download endpoint가 없으므로 capability 값은 `false`다.

상태는 `PENDING → VALIDATING → GENERATING → STEM_SEPARATING → VOICE_CONVERTING → MIXING → EXPORTING → COMPLETED` 순서다. 어느 단계에서든 `FAILED`로 종료할 수 있다.

응답의 `result_metadata`에는 Pipeline 버전, Provider·모델, seed, 전체·단계 시간, attempt, VRAM 가능한 값, 성공 여부, 실패 단계와 오류가 포함된다. Mock AI 실행의 GPU·VRAM은 추측하지 않고 `null`로 기록한다. Frontend는 이 전체 내부 구조를 그대로 출력하지 않고 duration·execution time, Provider 식별자와 Mixer audio quality의 공개 필드만 allowlist로 표시한다.

Mixer step의 `details.audio_quality`에는 provider·처리 시간, 출력 duration·sample rate·channels·size, 보컬·반주·normalization gain, 목표·실제 headroom, peak·RMS, normalization·limiter·fade, silence, PCM 직전 clipping과 보호 처리 전 over-range가 포함된다. True Peak는 현재 미지원이므로 `true_peak_supported=false`, `true_peak_dbfs=null`이다.

취소·수동 재시도·다운로드 API와 인증·소유권 검사는 이번 범위에 포함하지 않는다.
