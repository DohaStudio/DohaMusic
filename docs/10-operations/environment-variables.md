# 환경 변수

> 문서 목적: 향후 서비스 설정과 비밀 값의 이름·책임을 정의한다.
> 현재 상태: **계획 / 미구현**

| 변수 후보 | 용도 | 비밀 |
|---|---|---|
| `APP_ENV` | 실행 환경 | 아니오 |
| `DATABASE_URL` | DB 연결 | 예 |
| `QUEUE_BACKEND_URL` | 큐 연결 | 예 |
| `AUDIO_STORAGE_ROOT` | 로컬 저장 루트 | 아니오 |
| `OBJECT_STORAGE_ENDPOINT` | S3 호환 endpoint | 아니오 |
| `OBJECT_STORAGE_ACCESS_KEY` | 저장소 인증 | 예 |
| `OBJECT_STORAGE_SECRET_KEY` | 저장소 인증 | 예 |
| `MODEL_CACHE_DIR` | 모델 캐시 위치 | 아니오 |
| `MAX_UPLOAD_BYTES` | 업로드 제한 | 아니오 |

`.env`는 커밋하지 않고 예시 파일에는 더미 값만 둔다. 비밀 값은 로그나 오류 응답에 출력하지 않는다.
