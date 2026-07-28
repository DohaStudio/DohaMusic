# 환경 변수

> 문서 목적: 향후 서비스 설정과 비밀 값의 이름·책임을 정의한다.
> 현재 상태: **Backend Foundation 변수 구현**

| 변수 | 용도 | 기본값 | 필수 | 비밀 |
|---|---|---|
| `APP_NAME` | FastAPI 애플리케이션명 | `DohaMusic Backend` | 아니오 | 아니오 |
| `DATABASE_URL` | SQLAlchemy DB 연결 | `sqlite:///./backend/storage/doha_music.db` | 아니오 | 환경에 따라 |
| `AUDIO_STORAGE_ROOT` | 로컬 Storage 루트 | `backend/storage` | 아니오 | 아니오 |
| `MODEL_NAME` | 현재 Adapter 식별자 | `mock-music-generator` | 아니오 | 아니오 |
| `WORKER_MAX_THREADS` | 프로세스 내부 Worker 수 | `1` | 아니오 | 아니오 |
| `MOCK_GENERATION_DELAY_SECONDS` | Mock 지연 시간 | `3` | 아니오 | 아니오 |
| `LOG_LEVEL` | 로그 수준 | `INFO` | 아니오 | 아니오 |

예시는 `backend/.env.example`에 있다. 애플리케이션은 시스템 환경 변수를 읽으며 `.env`를 자동 로드하지 않는다. `.env`와 실제 비밀 값은 커밋하거나 로그·오류 응답에 출력하지 않는다. 외부 Queue와 객체 Storage 변수는 해당 Adapter 도입 전까지 구현하지 않는다.
