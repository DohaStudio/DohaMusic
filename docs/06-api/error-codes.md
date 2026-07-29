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

API 오류는 `{ "error": { "code", "message" } }` 형식이다. 비동기 Worker 오류는 해당 `generation_jobs` 또는 `stem_jobs`의 `error_code`와 안전한 사용자 메시지로 기록되고 Job은 `FAILED`가 된다. 내부 스택·로컬 절대 경로·prompt·lyrics는 응답에 노출하지 않는다.
