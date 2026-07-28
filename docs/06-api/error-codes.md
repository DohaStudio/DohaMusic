# 오류 코드

> 문서 목적: API와 Worker가 공유하는 안정적인 오류 분류를 정의한다.
> 현재 상태: **초안**

| 코드 | 의미 | 재시도 |
|---|---|---|
| `INVALID_INPUT` | 요청 형식·범위 오류 | 수정 후 가능 |
| `VOICE_CONSENT_REQUIRED` | 동의 없음·만료·철회 | 동의 해결 후 가능 |
| `FILE_FORMAT_UNSUPPORTED` | 미지원 또는 디코딩 불가 | 다른 파일 필요 |
| `MODEL_UNAVAILABLE` | 모델 로드/가용성 문제 | 조건부 |
| `GPU_OUT_OF_MEMORY` | 안전 설정에서도 VRAM 부족 | 설정/모델 변경 필요 |
| `PIPELINE_STEP_FAILED` | 단계별 일반 실패 | 실행 로그 판정 |
| `JOB_NOT_RETRYABLE` | 정책상 재시도 불가 | 불가 |
| `ACCESS_DENIED` | 인증·소유권 부족 | 권한 해결 필요 |

내부 예외, 로컬 경로, 개인정보, 비밀 값은 사용자 메시지에 노출하지 않는다.
