# Asset 중심 목표 ERD

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-09
> 관련 기능: DohaMusic Workspace 데이터베이스 재설계
> 구현 상태: Workspace Entity 21개와 별도 Artifact Storage Catalog Entity·source revision `20260809_0016` 구현, 실제 사용자 DB `20260808_0015`
> 관련 문서: [재설계 개요](database-redesign-overview.md), [목표 Table Definition](database-redesign-table-definition.md), [Migration 전략](database-redesign-migration-strategy.md)

## 1. 전체 ERD

```mermaid
erDiagram
  WORKSPACES ||--o{ MUSIC_PROJECTS : contains
  WORKSPACES o|--o{ ASSETS : scopes
  WORKSPACES ||--o{ RECORDING_ENROLLMENTS : authorizes
  WORKSPACES ||--o{ FAVORITES : owns
  WORKSPACES ||--o{ HISTORY : records

  MUSIC_PROJECTS ||--o{ PROJECT_ASSETS : groups
  ASSETS ||--o{ PROJECT_ASSETS : linked_by
  MUSIC_PROJECTS ||--o{ COMPOSITION_SNAPSHOTS : snapshots
  MUSIC_PROJECTS ||--o{ JOBS : requests

  ASSETS ||--|{ ASSET_VERSIONS : versions
  ASSET_VERSIONS o|--o| ASSETS : selected_by
  ASSET_VERSIONS ||--o{ ARTIFACTS : materializes
  ARTIFACTS ||--o| ARTIFACT_STORAGE_LOCATIONS : resolves_to
  ASSETS ||--o{ ASSET_RELATIONS : source
  ASSETS ||--o{ ASSET_RELATIONS : target
  ASSET_VERSIONS ||--o{ ASSET_RELATIONS : version_source
  ASSET_VERSIONS ||--o{ ASSET_RELATIONS : version_target

  COMPOSITION_SNAPSHOTS ||--|{ SNAPSHOT_ITEMS : fixes
  ASSET_VERSIONS ||--o{ SNAPSHOT_ITEMS : selected_version
  PROCESSING_CHAINS ||--|{ PROCESSING_STEPS : orders
  PROCESSING_CHAINS ||--o{ ASSET_VERSIONS : applied_to
  PROCESSING_CHAINS ||--o{ COMPOSITION_SNAPSHOTS : captured_by

  JOBS ||--o{ JOB_INPUTS : receives
  JOBS ||--o{ JOB_OUTPUTS : produces
  JOBS o|--o{ JOBS : retried_as
  ASSET_VERSIONS ||--o{ JOB_INPUTS : version_input
  ARTIFACTS ||--o{ JOB_INPUTS : artifact_input
  ASSET_VERSIONS ||--o{ JOB_OUTPUTS : version_output
  ARTIFACTS ||--o{ JOB_OUTPUTS : artifact_output
  COMPOSITION_SNAPSHOTS ||--o{ JOBS : execution_context
  JOBS ||--o{ MODEL_USAGES : records
  ASSET_VERSIONS ||--o{ MODEL_USAGES : provenance

  ASSET_VERSIONS ||--o{ RECORDING_ENROLLMENTS : recording_reference
  ASSET_VERSIONS ||--o{ APPROVALS : version_approval
  RECORDING_ENROLLMENTS ||--o{ APPROVALS : enrollment_approval
  MODEL_USAGES ||--o{ APPROVALS : commercial_approval

  ASSETS ||--o{ TAGS : tagged
  ASSET_VERSIONS ||--o{ COMMENTS : discussed
  ASSETS ||--o{ FAVORITES : favored

  WORKSPACES {
    uuid workspace_id PK
    string name
    string lifecycle_status
    timestamp deleted_at
  }
  MUSIC_PROJECTS {
    uuid project_id PK
    uuid workspace_id FK
    string title
    string lifecycle_status
    timestamp deleted_at
  }
  PROJECT_ASSETS {
    uuid project_asset_id PK
    uuid project_id FK
    uuid asset_id FK
    string role
    integer display_order
    timestamp deleted_at
  }
  ASSETS {
    uuid asset_id PK
    uuid workspace_id FK
    uuid owner_id
    string asset_type
    uuid selected_asset_version_id FK
    string lifecycle_status
    timestamp deleted_at
  }
  ASSET_VERSIONS {
    uuid asset_version_id PK
    uuid asset_id FK
    integer version_number
    string version_origin
    uuid parent_asset_version_id FK
    uuid processing_chain_id FK
    string provider_id
    string model_manifest_id
    timestamp created_at
  }
  ARTIFACTS {
    uuid artifact_id PK
    uuid asset_version_id FK
    string artifact_kind
    string media_type
    string artifact_checksum
    string retention_status
  }
  ARTIFACT_STORAGE_LOCATIONS {
    uuid storage_location_id PK
    uuid artifact_id FK
    string storage_backend
    string storage_domain
    string storage_key
    integer locator_version
    timestamp published_at
  }
  ASSET_RELATIONS {
    uuid relation_id PK
    uuid source_asset_id FK
    uuid target_asset_id FK
    uuid source_asset_version_id FK
    uuid target_asset_version_id FK
    string relation_type
  }
  COMPOSITION_SNAPSHOTS {
    uuid composition_snapshot_id PK
    uuid project_id FK
    integer snapshot_version
    uuid processing_chain_id FK
    json mix_settings_snapshot
    json provider_versions
    json model_manifest_ids
  }
  SNAPSHOT_ITEMS {
    uuid snapshot_item_id PK
    uuid composition_snapshot_id FK
    uuid asset_version_id FK
    string item_role
    integer sort_order
  }
  PROCESSING_CHAINS {
    uuid processing_chain_id PK
    string name
    string chain_version
    string chain_checksum
  }
  PROCESSING_STEPS {
    uuid processing_step_id PK
    uuid processing_chain_id FK
    integer step_order
    string step_type
    json settings_snapshot
  }
  JOBS {
    uuid job_id PK
    uuid project_id FK
    uuid composition_snapshot_id FK
    uuid retry_of_job_id FK
    string job_type
    string status
    string provider_id
    string api_contract_version
    string model_manifest_id
  }
  JOB_INPUTS {
    uuid job_input_id PK
    uuid job_id FK
    uuid asset_version_id FK
    uuid artifact_id FK
    integer input_order
  }
  JOB_OUTPUTS {
    uuid job_output_id PK
    uuid job_id FK
    uuid asset_version_id FK
    uuid artifact_id FK
    integer output_order
  }
  MODEL_USAGES {
    uuid model_usage_id PK
    uuid job_id FK
    uuid asset_version_id FK
    string provider_id
    string model_manifest_id
    string model_version
    string license_status
    string commercial_usage_status
  }
  RECORDING_ENROLLMENTS {
    uuid recording_enrollment_id PK
    uuid workspace_id FK
    uuid recording_asset_version_id FK
    string status
    string consent_policy_version
    timestamp deleted_at
  }
  APPROVALS {
    uuid approval_id PK
    uuid asset_version_id FK
    uuid recording_enrollment_id FK
    uuid model_usage_id FK
    string usage_purpose
    string status
    uuid approved_by
  }
  TAGS {
    uuid tag_id PK
    uuid asset_id FK
    string name
    timestamp deleted_at
  }
  COMMENTS {
    uuid comment_id PK
    uuid asset_version_id FK
    uuid created_by
    text body
    timestamp deleted_at
  }
  FAVORITES {
    uuid favorite_id PK
    uuid workspace_id FK
    uuid asset_id FK
    timestamp deleted_at
  }
  HISTORY {
    uuid history_id PK
    uuid workspace_id FK
    uuid actor_id
    string entity_type
    uuid entity_id
    string action
    timestamp created_at
  }
```

## 2. 주요 관계

| 관계 | Cardinality | 정책 |
|---|---|---|
| Workspace → MusicProject | 1:N | Project는 정확히 하나의 Workspace에 속함 |
| Workspace → Asset | 1:N, 선택적 | 저장소별 단일 Workspace 계약에서는 Asset의 Workspace 참조를 생략할 수 있음 |
| MusicProject ↔ Asset | N:M | `ProjectAsset`으로만 연결 |
| Asset → AssetVersion | 1:N | 최소 한 Version, Version 번호 단조 증가 |
| AssetVersion → Artifact | 1:N | 실제 파일·Payload를 Artifact ID로 참조 |
| Artifact → ArtifactStorageLocation | 1:0..1 | authoritative locator 하나만 허용, FK 삭제 `RESTRICT` |
| Asset ↔ Asset | N:M | `AssetRelation`으로 부모·파생·Stem·Voice Conversion 관계 표현 |
| MusicProject → CompositionSnapshot | 1:N | Project별 Snapshot version 증가 |
| CompositionSnapshot → SnapshotItem | 1:N | 최소 한 정확한 AssetVersion 참조 |
| ProcessingChain → ProcessingStep | 1:N | `step_order`로 고정 순서 보존 |
| MusicProject → Job | 1:N | Project 문맥에서 독립 실행 단위 생성 |
| Job → JobInput | 1:N | 입력 Version 또는 Artifact 연결 |
| Job → JobOutput | 1:N | 성공 출력 Version 또는 Artifact 연결 |
| Job → ModelUsage | 1:N | Provider·Model·Manifest·권리 계보 기록 |
| Recording AssetVersion → RecordingEnrollment | 1:N | 작품 Recording과 Enrollment를 분리 |
| AssetVersion·RecordingEnrollment·ModelUsage → Approval | 1:N | 대상별 목적과 승인 근거 분리 |
| Asset → Tag | 1:N | Asset 내부에서 Tag 이름 유일 |
| AssetVersion → Comment | 1:N | 특정 불변 Version에 의견 고정 |
| Workspace ↔ Asset | N:M | `Favorite`로 사용자 선호 연결 |

## 3. 순환 참조 처리

`Asset.selected_asset_version_id`는 `AssetVersion.asset_id`와 함께 검증해야 합니다. 선택 대상이 같은 Asset의 Version인지 DB trigger에 의존하지 않고 Service transaction에서 확인합니다.

`AssetVersion.parent_asset_version_id`도 같은 Asset의 낮은 `version_number`만 참조해야 합니다. 순환 여부와 단조 증가 규칙은 생성 transaction에서 검사합니다.

## 4. 선택적 참조 제약

- `JobInput`과 `JobOutput`은 `asset_version_id`, `artifact_id` 중 정확히 하나만 가집니다.
- `Approval`은 `asset_version_id`, `recording_enrollment_id`, `model_usage_id` 중 정확히 하나만 가집니다.
- `AssetRelation`은 Asset 쌍 또는 AssetVersion 쌍 중 하나를 사용하며 서로 다른 수준을 섞지 않습니다.
- `History.entity_id`는 여러 Entity의 감사를 위한 논리 참조입니다. 대상 종류가 여러 Table에 걸치므로 물리 FK 대신 `entity_type` allowlist와 Service 검증을 사용합니다.

## 5. ERD에서 제외한 현행 운영 Table

현행 `idempotency_records`는 Voice Enrollment API 재생 안전을 위한 운영 Table입니다. 목표 21개 Core Entity에 억지로 흡수하지 않고 Migration 기간에 그대로 유지합니다. 공통 API 멱등성 저장소의 최종 위치는 구현 ADR에서 별도로 결정합니다.
