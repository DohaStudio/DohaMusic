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

각 Repository는 호출자가 주입한 동기 SQLAlchemy `Session`만 사용하고 `add`·`flush`·조회·명시적 Soft Delete만 수행한다. `commit`과 `rollback`은 여러 Aggregate 작업을 하나의 transaction으로 묶는 Service가 담당한다. 기존 내부 목록 조회는 명시적인 `limit`·`offset`을 유지한다. Workspace v1 목록용 조회는 offset을 사용하지 않고 Resource별 keyset 메서드로 분리한다. Workspace·Project·Asset은 `(created_at DESC, UUID DESC)`, ProjectAsset은 `(display_order ASC, project_asset_id ASC)`를 사용한다. Alembic `20260807_0013`의 세 Index와 ProjectAsset partial Index revision `20260807_0014`는 승인된 절차로 실제 사용자 DB에 적용됐다. Asset Owner·Owner+Workspace full Index source revision `20260808_0015`는 임시 DB Query Plan을 통과했지만 실제 사용자 DB에는 미적용이다. 세부 결과는 [ProjectAsset keyset Index 설계](../07-database/project-asset-keyset-indexes.md)와 [Asset keyset Index 설계](../07-database/asset-keyset-indexes.md)를 따른다.

`AssetVersion`과 `CompositionSnapshot`에는 수정 메서드를 제공하지 않으며 Snapshot 조회가 최신 AssetVersion을 자동 선택하지 않는다. Repository는 SQLAlchemy Entity를 그대로 반환하고 권한·상태 전이·HTTP 오류·Storage URI 해석·Provider 호출을 처리하지 않는다.

이 계층은 additive 구현이다. 기존 Runtime Entity 14개와 Runtime Repository·Service·API는 변경하지 않았고 계속 운영 source of truth다. Workspace Application Service는 별도 namespace로 완료했고 `/api/v1` 공통 기반, 명시적 Bootstrap 도구, HMAC Cursor와 Workspace·MusicProject·ProjectAsset Resource Endpoint 11개를 추가했다. Asset Cursor·keyset Repository/Service와 source 0015도 완료했지만 Asset Router는 0/5다. Resource API 진행도는 11/64이며 Asset 이하 53개 Endpoint와 backfill·dual write·Legacy 제거는 미구현이다.

## Workspace Application Service 경계

Workspace Application Service는 `backend.services.workspace` namespace에 Aggregate별 5개 Service로 구성한다. 각 Service는 `session_factory`를 주입받고 변경 Use Case마다 `with session.begin()`으로 하나의 transaction을 관리한다. 같은 Use Case가 여러 Repository를 사용해도 동일 Session을 공유하며 Repository는 transaction을 종료하지 않는다.

별도 범용 Unit of Work Framework는 도입하지 않는다. 현재는 단일 동기 SQLAlchemy Session과 하나의 Database만 사용하고 분산 transaction이나 Message Broker transaction이 없기 때문이다. 향후 외부 transaction 조정이 실제로 필요해지면 현재 Service transaction 패턴을 Unit of Work로 추출한다.

Service는 SQLAlchemy Entity 또는 내부 dataclass 결과를 반환하고 API용 Pydantic Schema, `HTTPException`, Provider 호출과 Worker dispatch를 사용하지 않는다. 자세한 계약과 상태 전이는 [Workspace Service transaction 설계](workspace-service-transaction.md)를 따른다.

Workspace·Project·ProjectAsset 목록 Service는 App Factory가 주입한 `CursorCodec`으로 Resource별 payload를 검증하고 Repository에 `limit + 1` keyset 조회를 요청한다. AssetService도 같은 version 1 codec을 사용하며 effective Owner, 선택적 Workspace·Asset type, Soft Delete와 sort를 fingerprint에 고정한다. ProjectAsset은 `project_id` filter fingerprint와 정확한 정수 `last_display_order`를 사용하며 기존 Resource token을 변경하지 않는다. Resource Router는 App State dependency로 `WorkspaceService`만 사용하며 Repository·Session·Cursor를 직접 생성하지 않는다. Asset Router는 아직 없으므로 향후 Bootstrap된 Workspace에서 trusted Owner를 파생해 AssetService에 전달해야 한다. 일반 CRUD·Bootstrap은 codec 없이 계속 사용할 수 있으며 서명 키 누락은 cursor 기능을 호출할 때만 설정 오류가 된다.

공개 Workspace·MusicProject DTO는 SQLAlchemy Entity를 직접 직렬화하지 않고 allowlist Pydantic v2 Schema를 사용한다. 내부 `owner_id`·`created_by`, Soft Delete 시각과 ORM relationship은 노출하지 않으며 Project 생성의 감사 식별자는 Workspace 소유자에서 Service 입력으로 파생한다.

기본 Provider는 모두 Mock이다. ACE-Step, Demucs, Seed-VC는 실제 Job에서만 설정을 검증하고 격리 subprocess를 시작한다. 세 Worker는 `max_workers=1`인 shared executor를 사용해 RTX 3060 Ti GPU 점유를 직렬화한다. 외부 Queue, Redis, Celery는 아직 사용하지 않는다.

독립 생성·Stem·Voice Job은 유지한다. 별도 `PipelineService`와 `PipelineWorker`가 같은 인터페이스를 재사용해 5단계 Workflow를 실행하며 `pipeline_jobs/files`에 진행률·metadata·결과를 기록한다. 종료 시 SQLAlchemy Engine을 dispose해 SQLite 파일 handle을 해제한다.
