# Backend 아키텍처

> 현재 상태: Phase 6 생성·Stem·Voice·Lyrics Provider, Pipeline Orchestrator와 Audio Quality Engine 경계 구현

```text
API → Service → Repository → SQLAlchemy Model
                ↓
        asynchronous Dispatcher → Worker → AI Interface → Adapter
```

FastAPI lifespan은 Storage와 Alembic migration을 준비한 뒤 `MusicGenerator`, `StemSeparator`, `VoiceConverter` Provider Factory를 조립한다. Router는 Service만, Worker는 Repository와 AI Interface만 사용하므로 모델 라이브러리가 API 프로세스 전체로 퍼지지 않는다.

Lyrics는 독립 `LyricsGenerator` Factory를 조립한다. 빠른 로컬 Template·Mock Provider이므로 Worker 없이 `API → LyricsService → LyricsGenerator → Validator → Repository` 동기 흐름을 사용한다. 외부 LLM과 Pipeline 연결은 포함하지 않는다.

## Workspace Repository 경계

신규 Workspace Entity 21개는 기존 Runtime Repository와 분리된 `backend.repositories.workspace` namespace에서 다음 5개 Aggregate Repository로 접근한다.

| Repository | 담당 Entity |
|---|---|
| `WorkspaceRepository` | `Workspace`, `MusicProject`, `ProjectAsset` |
| `AssetRepository` | `Asset`, `AssetVersion`, `Artifact`, `AssetRelation` |
| `CompositionRepository` | `CompositionSnapshot`, `SnapshotItem`, `ProcessingChain`, `ProcessingStep` |
| `JobRepository` | `Job`, `JobInput`, `JobOutput`, `ModelUsage` |
| `CollaborationRepository` | `RecordingEnrollment`, `Tag`, `Comment`, `Favorite`, `History`, `Approval` |

각 Repository는 호출자가 주입한 동기 SQLAlchemy `Session`만 사용하고 `add`·`flush`·조회·명시적 Soft Delete만 수행한다. `commit`과 `rollback`은 여러 Aggregate 작업을 하나의 transaction으로 묶을 향후 Service 또는 Unit of Work가 담당한다. 목록 조회는 SQLAlchemy 2.0 `select()`와 안정적인 `created_at`·기본 키 정렬, 명시적인 기본 `limit`과 `offset`을 사용한다.

`AssetVersion`과 `CompositionSnapshot`에는 수정 메서드를 제공하지 않으며 Snapshot 조회가 최신 AssetVersion을 자동 선택하지 않는다. Repository는 SQLAlchemy Entity를 그대로 반환하고 권한·상태 전이·HTTP 오류·Storage URI 해석·Provider 호출을 처리하지 않는다.

이 계층은 additive 구현이다. 기존 Runtime Entity 14개와 Runtime Repository·Service·API는 변경하지 않았고 계속 운영 source of truth다. Workspace Service·REST API·backfill·dual write·Legacy 제거는 아직 구현하지 않았다.

기본 Provider는 모두 Mock이다. ACE-Step, Demucs, Seed-VC는 실제 Job에서만 설정을 검증하고 격리 subprocess를 시작한다. 세 Worker는 `max_workers=1`인 shared executor를 사용해 RTX 3060 Ti GPU 점유를 직렬화한다. 외부 Queue, Redis, Celery는 아직 사용하지 않는다.

독립 생성·Stem·Voice Job은 유지한다. 별도 `PipelineService`와 `PipelineWorker`가 같은 인터페이스를 재사용해 5단계 Workflow를 실행하며 `pipeline_jobs/files`에 진행률·metadata·결과를 기록한다. 종료 시 SQLAlchemy Engine을 dispose해 SQLite 파일 handle을 해제한다.
