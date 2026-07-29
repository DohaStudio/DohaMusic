# Backend 아키텍처

> 현재 상태: Phase 5 생성·Stem·Voice Provider와 Pipeline Orchestrator 경계 구현

```text
API → Service → Repository → SQLAlchemy Model
                ↓
        asynchronous Dispatcher → Worker → AI Interface → Adapter
```

FastAPI lifespan은 Storage와 Alembic migration을 준비한 뒤 `MusicGenerator`, `StemSeparator`, `VoiceConverter` Provider Factory를 조립한다. Router는 Service만, Worker는 Repository와 AI Interface만 사용하므로 모델 라이브러리가 API 프로세스 전체로 퍼지지 않는다.

기본 Provider는 모두 Mock이다. ACE-Step, Demucs, Seed-VC는 실제 Job에서만 설정을 검증하고 격리 subprocess를 시작한다. 세 Worker는 `max_workers=1`인 shared executor를 사용해 RTX 3060 Ti GPU 점유를 직렬화한다. 외부 Queue, Redis, Celery는 아직 사용하지 않는다.

독립 생성·Stem·Voice Job은 유지한다. 별도 `PipelineService`와 `PipelineWorker`가 같은 인터페이스를 재사용해 5단계 Workflow를 실행하며 `pipeline_jobs/files`에 진행률·metadata·결과를 기록한다. 종료 시 SQLAlchemy Engine을 dispose해 SQLite 파일 handle을 해제한다.
