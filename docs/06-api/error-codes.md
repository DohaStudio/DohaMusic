# 오류 코드

> 문서 목적: API와 Worker의 안정적인 오류 코드를 정의한다.
> 현재 상태: **AI·Stem·Voice·Pipeline·Lyrics 구현 기준**

| 코드 | 의미 |
|---|---|
| `INVALID_INPUT` | API 요청 형식 또는 범위 오류 |
| `RESOURCE_NOT_FOUND` | Job 또는 음성 프로필 없음 |
| `INTERNAL_ERROR` | 처리되지 않은 API 내부 예외 |
| `MOCK_GENERATION_FAILED` | Mock 생성 실패 |
| `AI_PROVIDER_NOT_CONFIGURED` | 알 수 없는 Provider 설정 |
| `AI_DEPENDENCY_NOT_INSTALLED` | 격리 런타임 또는 runner 없음 |
| `AI_MODEL_NOT_FOUND` | checkout·checkpoint·모델 없음 |
| `AI_MODEL_LOAD_FAILED` | 모델 초기화 실패 |
| `AI_INFERENCE_FAILED` | 추론 또는 runner 응답 실패 |
| `AI_OUT_OF_MEMORY` | CUDA 메모리 부족 |
| `AI_OUTPUT_NOT_CREATED` | 결과 오디오 없음 |
| `AI_AUDIO_DECODE_FAILED` | 생성 파일을 WAV로 해석할 수 없음 |
| `AI_TIMEOUT` | AI subprocess 제한 시간 초과 |
| `STEM_PROVIDER_NOT_CONFIGURED` | 알 수 없거나 불완전한 Stem Provider 설정 |
| `STEM_DEPENDENCY_NOT_INSTALLED` | Demucs 격리 Python 또는 runner 없음 |
| `STEM_MODEL_NOT_FOUND` | HTDemucs cache·checkpoint 없음 |
| `STEM_MODEL_LOAD_FAILED` | Demucs 모델 초기화 실패 |
| `STEM_SEPARATION_FAILED` | 분리 또는 runner 응답 실패 |
| `STEM_OUT_OF_MEMORY` | Stem 추론 중 CUDA 메모리 부족 |
| `STEM_OUTPUT_NOT_CREATED` | vocals 또는 instrumental 생성 실패 |
| `STEM_AUDIO_DECODE_FAILED` | 입력 오디오 디코딩 실패 |
| `STEM_TIMEOUT` | Stem subprocess 제한 시간 초과 |
| `LYRICS_PROVIDER_NOT_SUPPORTED` | 지원하지 않는 Lyrics Provider 시작 설정 |
| `LYRICS_GENERATION_FAILED` | Lyrics Provider 실행 실패 |
| `LYRICS_OUTPUT_INVALID` | Provider 결과 구조 검증 실패 |
| `LYRICS_VALIDATION_FAILED` | 직접 가사 검증을 진행할 수 없는 입력 |
| `PIPELINE_NOT_FOUND` | Pipeline Job 없음 |
| `PIPELINE_JOB_NOT_FOUND` | Cancel·Retry 대상 Pipeline Job 없음 |
| `PIPELINE_CANCEL_NOT_ALLOWED` | 완료·실패 상태에서 취소 요청 |
| `PIPELINE_RETRY_NOT_ALLOWED` | 실패·취소 외 상태에서 Retry 요청 |
| `PIPELINE_RETRY_INPUT_MISSING` | 원본 입력 스냅샷 검증 실패 |
| `RETRY_VOICE_PROFILE_UNAVAILABLE` | 원본 Voice Profile 없음·비활성·동의 무효 |
| `FILE_NOT_FOUND` | 결과 File 없음 |
| `FILE_JOB_MISMATCH` | File이 요청한 Pipeline에 속하지 않음 |
| `PIPELINE_NOT_COMPLETED` | 완료 전 결과 파일 접근 요청 |
| `FILE_CONTENT_UNAVAILABLE` | 재생 capability가 없는 파일 |
| `FILE_DOWNLOAD_UNAVAILABLE` | 다운로드 capability가 없는 파일 |
| `FILE_PATH_INVALID` | Storage 경계를 벗어나거나 symlink인 경로 |
| `FILE_MISSING_FROM_STORAGE` | DB 기록에 대응하는 regular file 없음 |
| `UNSUPPORTED_AUDIO_FILE` | 허용되지 않은 type·MIME·확장자·WAV header |
| `INVALID_RANGE` | 지원하지 않거나 만족할 수 없는 byte Range |
| `VOICE_CONSENT_REQUIRED` | Voice upload 동의 누락 또는 false |
| `VOICE_FILE_REQUIRED` | multipart 음성 파일 누락 |
| `VOICE_FILE_EMPTY` | 빈 음성 파일 |
| `VOICE_FILE_TOO_LARGE` | 25MB 초과 파일 |
| `VOICE_FILE_TOO_SHORT` | 5초 미만 WAV |
| `VOICE_FILE_TOO_LONG` | 60초 초과 WAV |
| `VOICE_FILE_TYPE_UNSUPPORTED` | WAV 확장자·MIME 불일치 |
| `VOICE_FILE_DECODE_FAILED` | 손상되거나 decode 불가능한 WAV |
| `VOICE_REFERENCE_INVALID` | sample rate·channel·PCM 계약 위반 |
| `VOICE_PROFILE_NOT_FOUND` | Voice Profile 없음 |
| `VOICE_PROFILE_IN_USE` | Pipeline·Voice Job이 참조해 삭제 차단 |
| `VOICE_STORAGE_WRITE_FAILED` | 안전한 Voice 저장 실패 |
| `VOICE_STORAGE_DELETE_FAILED` | 관리 Voice 파일 삭제 실패 |

API 오류는 `{ "error": { "code", "message" } }` 형식이다. 비동기 Worker 오류는 해당 `generation_jobs` 또는 `stem_jobs`의 `error_code`와 안전한 사용자 메시지로 기록되고 Job은 `FAILED`가 된다. 내부 스택·로컬 절대 경로·prompt·lyrics는 응답에 노출하지 않는다.
# External Lyrics 오류

`LYRICS_API_KEY_MISSING`, `LYRICS_PROVIDER_NOT_SUPPORTED`, `LYRICS_PROVIDER_UNAVAILABLE`, `LYRICS_RATE_LIMITED`, `LYRICS_TIMEOUT`, `LYRICS_AUTHENTICATION_FAILED`, `LYRICS_REQUEST_REJECTED`, `LYRICS_OUTPUT_INVALID`, `LYRICS_CONTENT_BLOCKED`, `LYRICS_COST_LIMIT_EXCEEDED`, `LYRICS_REVISION_FAILED`를 구분한다. Provider 원문 body·request ID·인증 정보는 응답에 노출하지 않는다.
