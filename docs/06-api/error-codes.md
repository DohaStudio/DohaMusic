# 오류 코드

> 문서 목적: Phase 1 API와 Worker의 안정적인 오류 코드를 정의한다.
> 현재 상태: **구현 기준**

| 코드 | 발생 위치 | 의미 | HTTP |
|---|---|---|---:|
| `INVALID_INPUT` | API | 요청 형식 또는 범위 오류 | 422 |
| `RESOURCE_NOT_FOUND` | API | 요청한 Job 또는 음성 프로필이 없음 | 404 |
| `INTERNAL_ERROR` | API | 처리되지 않은 내부 예외 | 500 |
| `MOCK_GENERATION_FAILED` | Worker/Job | Mock 생성 실행 실패 | 해당 없음 |

API 오류 응답은 `{ "error": { "code", "message" } }` 형식이다. Worker 오류는 `generation_jobs.error_code`와 `error_message`에 기록되고 Job 상태가 `FAILED`로 바뀐다. 내부 스택, 로컬 절대 경로, 비밀 값은 공개 응답에 노출하지 않는다.

실제 모델, GPU, 파일 업로드, 인증 관련 오류 코드는 해당 기능을 도입하는 단계에서 공식 동작을 검증한 뒤 추가한다.
