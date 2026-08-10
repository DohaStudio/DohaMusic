# Backend 아키텍처

> 현재 상태: Legacy Provider·Pipeline 구현 / Workspace Job 공식 계약 완료·실행 기반 미구현

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

각 Repository는 호출자가 주입한 동기 SQLAlchemy `Session`만 사용하고 `add`·`flush`·조회·명시적 Soft Delete만 수행한다. `commit`과 `rollback`은 여러 Aggregate 작업을 하나의 transaction으로 묶는 Service가 담당한다. 기존 내부 목록 조회는 명시적인 `limit`·`offset`을 유지한다. Workspace v1 목록용 조회는 offset을 사용하지 않고 Resource별 keyset 메서드로 분리한다. Workspace·Project·Asset은 `(created_at DESC, UUID DESC)`, ProjectAsset은 `(display_order ASC, project_asset_id ASC)`, CompositionSnapshot은 `(snapshot_version DESC, composition_snapshot_id DESC)`를 사용한다. CompositionSnapshot은 기존 `(project_id, snapshot_version)` Unique Index로 Query Plan을 충족하므로 새 Index를 추가하지 않는다.

`AssetVersion`과 `CompositionSnapshot`에는 수정 메서드를 제공하지 않으며 Snapshot 조회가 최신 AssetVersion을 자동 선택하지 않는다. Repository는 SQLAlchemy Entity를 그대로 반환하고 권한·상태 전이·HTTP 오류·Storage URI 해석·Provider 호출을 처리하지 않는다.

Artifact Storage 경계는 `Router → Artifact Application Service → Storage Resolver·Trusted Ingestion → Artifact·Catalog Repository`다. `ArtifactApplicationService`는 effective Owner 계보, retention matrix와 content 전 full SHA-256 read Gate를 소유한다. `ArtifactIngestionService → LocalArtifactPublisher`는 AssetVersion 확인, Artifact·Catalog 단일 transaction·보상과 staging containment·MIME·exclusive publish를 담당한다. `ArtifactReconciliationService`는 Catalog를 UUID keyset batch로 읽고 승인 namespace만 dry-run scan한다. Repository는 add·flush·조회만 수행하고 commit·rollback·filesystem을 소유하지 않는다. Artifact Router는 Metadata·content·download를 Application Service에만 위임하고 single-byte Range를 처리하며 Repository·Resolver·filesystem에 직접 접근하지 않는다.

이 계층은 additive 구현이다. 기존 Runtime Entity 14개와 Runtime Repository·Service·API는 변경하지 않았고 계속 운영 source of truth다. `/api/v1` Workspace·MusicProject·ProjectAsset·Asset·AssetVersion·Artifact·CompositionSnapshot Resource Endpoint는 25개다. Resource API 진행도는 25/64, Artifact API와 CompositionSnapshot API는 각각 3/3이며 Job API를 포함한 나머지 39개 Endpoint와 destructive reconciliation·backfill·dual write·Legacy 제거는 미구현이다.

## Workspace Application Service 경계

Workspace Application Service는 `backend.services.workspace` namespace에 Aggregate별 5개 Service로 구성한다. 각 Service는 `session_factory`를 주입받고 변경 Use Case마다 `with session.begin()`으로 하나의 transaction을 관리한다. 같은 Use Case가 여러 Repository를 사용해도 동일 Session을 공유하며 Repository는 transaction을 종료하지 않는다.

별도 범용 Unit of Work Framework는 도입하지 않는다. 현재는 단일 동기 SQLAlchemy Session과 하나의 Database만 사용하고 분산 transaction이나 Message Broker transaction이 없기 때문이다. 향후 외부 transaction 조정이 실제로 필요해지면 현재 Service transaction 패턴을 Unit of Work로 추출한다.

Service는 SQLAlchemy Entity 또는 내부 dataclass 결과를 반환하고 API용 Pydantic Schema, `HTTPException`, Provider 호출과 Worker dispatch를 사용하지 않는다. 자세한 계약과 상태 전이는 [Workspace Service transaction 설계](workspace-service-transaction.md)를 따른다.

Workspace·Project·ProjectAsset 목록 Service는 App Factory가 주입한 `CursorCodec`으로 Resource별 payload를 검증하고 Repository에 `limit + 1` keyset 조회를 요청한다. `AssetService`도 같은 version 1 codec을 사용하며 effective Owner, 선택적 Workspace·Asset type, Soft Delete와 sort를 fingerprint에 고정한다. ProjectAsset은 `project_id` filter fingerprint와 정확한 정수 `last_display_order`를 사용하며 기존 Resource token을 변경하지 않는다. Resource Router는 App State dependency로 `WorkspaceService` 또는 `AssetService`만 사용하며 Repository·Session·Cursor를 직접 생성하지 않는다. Asset Router는 Bootstrap된 Workspace에서 trusted Owner를 파생하고 공개 DTO에서 내부 소유권 필드를 제외한다. 일반 CRUD·Bootstrap은 codec 없이 계속 사용할 수 있으며 서명 키 누락은 cursor 기능을 호출할 때만 설정 오류가 된다.

`CompositionService`는 effective Owner·활성 Project, 같은 Workspace 또는 Owner 소유 Workspace 미지정 Asset과 활성 ProjectAsset 관계를 검증한다. Snapshot+Item+Idempotency 기록을 한 transaction에서 생성하고 `snapshot_version`·`created_by`를 내부에서 파생한다. 상세는 정렬된 aggregate를, 목록은 version 1 HMAC Cursor keyset page를 반환한다. 공식 Router 3개를 연결했으며 세부 경계는 [CompositionSnapshot 기반 계약](../06-api/composition-snapshot-foundation.md)을 따른다.

## Workspace Job Foundation 경계 — [계약 완료, 구현 미완료]

Workspace Job은 `Job`을 실행 root로 하고 `JobInput`, `JobOutput`, `ModelUsage`를 Aggregate 내부에 둔다. CompositionSnapshot·AssetVersion·Artifact는 외부 불변 lineage Resource다. byte-level 입력은 role과 exact Artifact ID로 고정하고 Provider success 뒤 trusted ingestion·Artifact·Catalog·필요한 AssetVersion·JobOutput·ModelUsage와 상태를 completion Unit of Work에서 확정한다.

현재 Completion Service는 bounded Provider DTO, output Matrix, Owner·Workspace·target Asset scope와 cancel marker를 검증한다. Artifact ingestion의 commitless primitive를 재사용해 새 AssetVersion·Artifact·Catalog·JobOutput·ModelUsage·최종 checksum을 하나의 DB transaction에 등록한 뒤에만 `succeeded`로 전이한다. 파일 publish와 DB 사이 실패는 identity 기반 보상으로 정리하며 Worker claim·lease runtime과 Provider dispatch는 이 Service 바깥의 후속 범위다.

공개 상태는 5개를 유지하고 cancel 요청은 내부 marker로 분리한다. Worker는 atomic claim·lease·heartbeat로 중복 실행을 막으며 lease 만료 running Job을 같은 row의 queued 상태로 되돌리지 않는다. Workspace 전체 목록은 direct `workspace_id`, 제한된 filter와 Job HMAC Cursor를 사용한다. 역할·실행 제어 Column, Index, Cursor, Worker와 API 5개는 후속 구현이며 세부 계약은 [Workspace Job Foundation](workspace-job-foundation.md)을 따른다.

공개 Workspace·MusicProject DTO는 SQLAlchemy Entity를 직접 직렬화하지 않고 allowlist Pydantic v2 Schema를 사용한다. 내부 `owner_id`·`created_by`, Soft Delete 시각과 ORM relationship은 노출하지 않으며 Project 생성의 감사 식별자는 Workspace 소유자에서 Service 입력으로 파생한다.

기본 Provider는 모두 Mock이다. ACE-Step, Demucs, Seed-VC는 실제 Job에서만 설정을 검증하고 격리 subprocess를 시작한다. 세 Worker는 `max_workers=1`인 shared executor를 사용해 RTX 3060 Ti GPU 점유를 직렬화한다. 외부 Queue, Redis, Celery는 아직 사용하지 않는다.

독립 생성·Stem·Voice Job은 유지한다. 별도 `PipelineService`와 `PipelineWorker`가 같은 인터페이스를 재사용해 5단계 Workflow를 실행하며 `pipeline_jobs/files`에 진행률·metadata·결과를 기록한다. 종료 시 SQLAlchemy Engine을 dispose해 SQLite 파일 handle을 해제한다.
