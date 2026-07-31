# Pipeline API

> 문서 상태: [완료]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 5 Pipeline Orchestrator, Phase 8 Audio Player·WAV Download·Cancel·Retry, K3.0 Audio Analysis 계약

## 생성

`POST /api/pipelines`는 `202 Accepted`와 `PENDING` Job을 반환한다.

```json
{
  "prompt": "잔잔한 한국어 발라드",
  "lyrics": "직접 작성한 가사",
  "genre": "ballad",
  "duration_seconds": 30,
  "seed": 20260729,
  "voice_profile_id": "UUID",
  "generation_options": {
    "preset_id": "kpop_dance",
    "requested_bpm": 124,
    "language_ratio": { "ko": 70, "en": 30 },
    "hook": { "phrase": "Play My Heart", "style": "title_repeat", "repeat_count": 3 },
    "include_post_chorus": true,
    "include_dance_break": false,
    "vocal_energy": "medium",
    "concept": "confident_bright"
  }
}
```

`generation_options`는 optional이며 없으면 기존 요청과 동일하게 동작한다. 모든 중첩 DTO는 unknown field를 거부한다. `requested_bpm`은 70~180 정수, 언어 비율 합은 100, Hook은 1~40자·1~6회, 에너지는 `low|medium|high`, Concept은 제어문자 없는 최대 40자다. `preset_id`와 `genre` 불일치는 `422 PRESET_GENRE_MISMATCH`다.

`voice_profile_id`는 존재하고 동의가 확인돼야 한다. 참조 파일은 설정된 Storage의 `voices/references` 아래에 있어야 한다.

일반 사용자는 Voice Profile upload·list API에서 선택한 opaque ID를 전달한다. 참조 음성 경로와 원본 파일은 Pipeline request·response에 포함하지 않는다.

## 조회

- `GET /api/pipelines/{job_id}`: 상태, 현재 단계, 진행률, 오류, Pipeline metadata
- `GET /api/pipelines/{job_id}/files`: 성공 시 6개 결과 파일 metadata, 실패 시 진단 metadata

Files response는 `id`, `job_id`, `file_type`, `mime_type`, `created_at`, `content_available`, `download_available`, `content_url`, `download_url`만 반환한다. 서버의 절대·상대 `file_path`, Storage root, 임시·모델 경로는 반환하지 않는다. `COMPLETED` Job의 실제 검증 가능한 WAV에만 capability와 상대 API URL을 제공하며 metadata와 불가 파일의 URL은 `null`이다.

## 오디오 content·download

- `GET|HEAD /api/pipelines/{job_id}/files/{file_id}/content`: 브라우저 재생용 inline 응답
- `GET|HEAD /api/pipelines/{job_id}/files/{file_id}/download`: 안전한 ASCII `.wav` filename의 attachment 응답

두 endpoint는 Job·File 존재와 소속, `COMPLETED` 상태, 공개 오디오 type, Storage root 내부 real path, symlink 부재, regular file, 최대 1 GiB, `.wav` 확장자·허용 MIME·RIFF/WAVE header를 매 요청 검증한다. `Range: bytes=...` 단일 범위를 지원하며 성공은 `206`과 `Content-Range`, 유효하지 않거나 범위 밖 요청은 `416 INVALID_RANGE`와 `Content-Range: bytes */<size>`를 반환한다. 전체 응답은 `200`, HEAD는 body 없이 동일 metadata를 반환한다.

응답은 Starlette `FileResponse`로 stream되며 전체 파일을 메모리에 올리지 않는다. `Accept-Ranges: bytes`, `Cache-Control: private, no-store`, `X-Content-Type-Options: nosniff`를 적용한다. framework가 생성하는 `ETag`·`Last-Modified`는 조건부 요청 식별자로 유지하되 `no-store` 때문에 공유 cache 저장을 허용하지 않는다. 다중 Range는 현재 `416`이다.

주요 오류는 `PIPELINE_NOT_FOUND`, `FILE_NOT_FOUND`, `FILE_JOB_MISMATCH`, `PIPELINE_NOT_COMPLETED`, `FILE_CONTENT_UNAVAILABLE`, `FILE_DOWNLOAD_UNAVAILABLE`, `FILE_PATH_INVALID`, `FILE_MISSING_FROM_STORAGE`, `UNSUPPORTED_AUDIO_FILE`, `INVALID_RANGE`다. 이 API는 로컬 단일 사용자 개발 범위이며 공개 운영 전 인증·소유권·인가·rate limit·감사 로그·만료 URL 또는 동등한 보호가 필요하다.

상태는 `PENDING → VALIDATING → GENERATING → STEM_SEPARATING → VOICE_CONVERTING → MIXING → EXPORTING → COMPLETED` 순서다. 어느 단계에서든 `FAILED`로 종료할 수 있고 실행 상태에서는 `CANCEL_REQUESTED → CANCELLED`로 전이한다.

## 취소와 다시 만들기

- `POST /api/pipelines/{job_id}/cancel`: `PENDING`은 즉시 `CANCELLED`, 실행 중은 `CANCEL_REQUESTED`를 반환한다. `CANCEL_REQUESTED`와 `CANCELLED` 재호출은 현재 상태를 반환하며 `COMPLETED`·`FAILED`는 `409 PIPELINE_CANCEL_NOT_ALLOWED`다.
- `POST /api/pipelines/{job_id}/retry`: `FAILED`·`CANCELLED` 입력 스냅샷으로 새 Job을 만들고 `202`와 `source_job_id`, 새 `job`을 반환한다. 같은 원본의 중복 요청은 기존 재시도 Job을 반환한다.

공개 Job DTO는 `can_cancel`, `can_retry`, `cancel_requested_at`, `cancelled_at`, `retry_of_job_id`, allowlist `generation_options`, `kpop_prompt_compiler_version`을 제공한다. Retry는 원본 prompt·options·lyrics·genre·duration·seed·voice profile·Project를 재검증하고 Backend Compiler로 새 compiled prompt를 만든다. 구형 Snapshot에는 기존 경로를 사용하며 Voice Profile이 없거나 비활성 상태면 `409 RETRY_VOICE_PROFILE_UNAVAILABLE`다. PID·명령·내부 경로·Worker 정보와 Snapshot 전체는 반환하지 않는다.

취소는 Job 시작 전, 각 단계 시작 전과 완료 후, metadata·파일·최종 결과 저장 전에 확인하는 cooperative 방식이다. 현재 Provider subprocess의 안전한 process ownership handle이 없으므로 실행 중 단일 추론의 즉시 종료는 보장하지 않는다.

응답의 `result_metadata`에는 Pipeline 버전, Provider·모델, seed, 전체·단계 시간, attempt, VRAM 가능한 값, 성공 여부, 실패 단계와 오류, allowlist K-POP Options와 compiler version이 포함된다. Mock AI 실행의 GPU·VRAM은 추측하지 않고 `null`로 기록한다. Frontend는 이 전체 내부 구조를 그대로 출력하지 않고 승인된 공개 필드만 표시한다.

Mixer step의 `details.audio_quality`에는 provider·처리 시간, 출력 duration·sample rate·channels·size, 보컬·반주·normalization gain, 목표·실제 headroom, peak·RMS, normalization·limiter·fade, silence, PCM 직전 clipping과 보호 처리 전 over-range가 포함된다. True Peak는 현재 미지원이므로 `true_peak_supported=false`, `true_peak_dbfs=null`이다.

인증·소유권 검사는 포함하지 않는다. Generation·Stem·Voice Conversion 개별 API에는 content endpoint를 추가하지 않았으며 첫 제공 범위는 Pipeline 결과다.

## K3 Audio Analysis 공개 계약 [계획]

K3.0 문서 단계에서는 endpoint·DTO·DB를 추가하지 않는다. K3 구현 시 공개 Pipeline Result는 optional nested allowlist로 다음 범위만 제공한다.

- `analysis_status`, `audio_analysis_version`
- duration·sample rate·channels·Sample Peak·clipping·Integrated LUFS
- 검증을 통과한 경우에만 True Peak
- detected BPM·confidence·requested BPM 차이
- Hook/Chorus 후보 시간과 confidence
- Preview 상태와 opaque file ID 기반 secure content/download URL

내부 path·command·temporary/model path·stack trace·raw analyzer debug와 전체 metadata는 반환하지 않는다. Preview는 기존 Files API의 완료 Job·WAV·Storage·symlink·MIME·RIFF 검증과 `private, no-store` 정책을 재사용하는 것이 목표다.

분석 실패는 기본적으로 Pipeline `COMPLETED`와 final WAV 재생·다운로드를 바꾸지 않는다. 구형 Result와 분석 미요청 Result에는 필드가 없을 수 있다. 상세 계약은 [Audio Analysis 결과 계약](../03-architecture/audio-analysis-result-contract.md)과 [실패 정책](../03-architecture/audio-analysis-failure-policy.md)을 따른다.
