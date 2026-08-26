# Workspace REST API 공통 계약

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-20
> 관련 기능: DohaMusic Workspace REST API 재설계
> 구현 상태: `/api/v1` Resource Endpoint 30개, D1 Product API 2개, WorkingComposition Product operation 17개 구현; Workspace Job API 5/5, 나머지 Resource 34개 미구현
> 관련 문서: [API 기반·Bootstrap](workspace-api-foundation-bootstrap.md), [Endpoint 목록](workspace-rest-api-endpoints.md), [D1 Composition Read 계약](composition-read-workspace.md), [WorkingComposition Product API](working-composition-api.md), [Workspace Job Foundation](../03-architecture/workspace-job-foundation.md), [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md), [Provider API 계약](provider-api-contract.md), [API 전환 전략](api-contract-migration-strategy.md), [ADR-031](../11-decisions/ADR-031-workspace-rest-api-contract.md), [ADR-035](../11-decisions/ADR-035-d1-composition-read-authority.md)

## 1. 목적

DohaMusic의 목표 REST API를 Pipeline 실행 API가 아니라 Workspace 작품 관리 API로 설계합니다.

```text
Workspace
→ Project
→ ProjectAsset
→ Asset
→ AssetVersion
→ Artifact
→ Composition Snapshot
→ Job
→ Export
```

사용자는 Pipeline 단계를 직접 연결하지 않습니다. Asset을 만들고, 새 Version을 생성·선택하고, Composition Snapshot을 고정한 뒤 Job을 요청합니다. DohaMusic Orchestrator가 필요한 Provider를 선택하고 호출하며 검증된 결과를 새 AssetVersion과 Artifact로 등록합니다.

## 2. 설계 기준

### 2.1 DohaStudio Common Specification

기준은 [DohaStudio Common Specification](https://github.com/DohaStudio/.github/tree/main/docs/specifications) `0.1.0` / `draft-baseline`이며, 감사·재현 기준은 commit `1e4b480c8cbd6e51835f8550e685e9b136d8071d`입니다.

- Asset, AssetVersion, Artifact와 AssetRelation
- Provider Contract와 Job Contract
- Model Manifest와 Dataset Manifest
- Composition Snapshot과 Storage Layout
- Common Terms

### 2.2 DohaMusic Database Redesign

DB 기준은 [DohaMusic Asset 중심 데이터베이스 설계](../07-database/database-redesign-overview.md)의 `develop` 반영 commit `6ef006251c761a7aaa736710bc6a872124701c3c`입니다.

- 21개 목표 Entity와 Table
- ProjectAsset N:M 관계
- 불변 AssetVersion·CompositionSnapshot·Job 계보
- Artifact ID와 경로 비노출
- Recording Asset와 RecordingEnrollment 분리
- Selection과 Approval 분리

두 선행 계약은 `develop`에 반영됐지만 Common Specification은 `[제안]`, 데이터베이스 설계는 `[제안]` 상태입니다. 계약이 변경되면 API 구현 전에 이 문서를 다시 검토합니다.

## 3. API 영역과 Version

| 영역 | Base path | 대상 |
|---|---|---|
| Workspace API | `/api/v1` | Frontend와 승인된 Workspace client |
| Provider API | `/api/v1/providers` | DohaMusic Pipeline Orchestrator 전용 |
| Health API | `/health`, `/readiness` | process·운영 probe |

- `v1`은 URL path의 major API version입니다.
- 호환되는 field 추가와 optional enum 확장은 같은 `v1`에서 수행할 수 있습니다.
- field 삭제, 의미 변경, 필수 field 추가와 상태 의미 변경은 새 major version이 필요합니다.
- Provider의 `api_contract_version`은 Workspace API version과 별도로 협상합니다.
- 폐기 예정 계약은 문서, `Deprecation`과 `Sunset` header로 알리고 지원 기간을 별도 정책으로 확정합니다.
- OpenAPI 문서와 JSON Schema도 API major version에 맞춰 versioning합니다.

이번 작업에서는 OpenAPI YAML이나 JSON 파일을 작성하지 않습니다.

## 4. API 그룹

목표 API는 16개 그룹, 64개 Method·Path 조합입니다.

1. Workspace API
2. Project API
3. ProjectAsset API
4. Asset API
5. AssetVersion API
6. Artifact API
7. CompositionSnapshot API
8. Job API
9. Recording API
10. Enrollment API
11. Tag API
12. Favorite API
13. Comment API
14. History API
15. Provider API
16. Health API

전체 목록과 성공 상태는 [Endpoint 목록](workspace-rest-api-endpoints.md)을 따릅니다.

### 4.1 현재 구현 범위

- Workspace 3개, MusicProject 5개, ProjectAsset 3개, Asset 5개와 AssetVersion 3개를 구현했습니다.
- Router는 App State dependency로 주입된 `WorkspaceService` 또는 `AssetService`만 호출하고 Repository·Session·Cursor를 직접 생성하지 않습니다.
- 목록은 기존 HMAC Cursor와 `limit + 1` keyset 조회를 사용하며 외부 offset을 받지 않습니다.
- `owner_id`와 `created_by`는 공개 입력에서 금지하고 Project 생성자는 Workspace 소유자에서 파생합니다.
- `owner_id`와 `created_by`는 현재 공개 응답 DTO에도 포함하지 않습니다.
- Workspace가 없으면 `409 WORKSPACE_BOOTSTRAP_REQUIRED`를 반환하며 Bootstrap을 암묵적으로 실행하지 않습니다.
- Resource별 Not Found·Conflict를 `WORKSPACE_NOT_FOUND`, `PROJECT_NOT_FOUND`, `ASSET_NOT_FOUND`, `PROJECT_ASSET_NOT_FOUND`, `WORKSPACE_NAME_CONFLICT`, `PROJECT_TITLE_CONFLICT`, `ASSET_CONFLICT`, `PROJECT_ASSET_CONFLICT`로 변환합니다.
- ProjectAsset은 별도 Resource 그룹으로 유지하고 `(display_order ASC, project_asset_id ASC)` Cursor·Project filter·keyset page를 Router에 연결했습니다. POST는 기존 Asset만 연결하고 DELETE는 Asset·AssetVersion을 보존한 채 관계만 Soft Delete합니다.
- DohaMusic은 REST 식별 경로, 기존 Unique Constraint와 Soft Delete restore 정책에 따라 같은 `(project_id, asset_id)` 연결을 하나만 허용합니다. Common Specification `0.1.0`의 role 포함 중복 기준보다 엄격한 저장소 계약이며 `role`은 관계 identity가 아니라 변경 가능한 Metadata입니다.
- Asset Resource API 5개는 신뢰된 effective Owner의 활성 Asset 전체, 선택적 `workspace_id=<uuid>`·`asset_type`, `(created_at DESC, asset_id DESC)` version 1 Cursor와 keyset Repository·Service를 사용합니다.
- Asset 목록의 `owner_id`, `include_deleted`, `lifecycle_status`, 자유 검색과 임의 sort는 공개하지 않습니다. Router는 Bootstrap된 Workspace context에서 Owner를 파생하고 Owner 조건 없는 전체 Table 조회를 금지합니다.
- Asset 생성은 AssetVersion·Artifact·ProjectAsset을 자동 생성하지 않습니다. PATCH는 `lifecycle_status`만 허용하고 DELETE는 Asset만 Soft Delete하며 Version·Artifact·ProjectAsset을 보존합니다.
- AssetVersion은 Asset 경로 아래에서만 생성·조회합니다. 생성자가 Version 번호를 입력하지 않으며 Service가 현재 최대 번호에 1을 더한 새 row를 transaction으로 추가합니다.
- AssetVersion 목록은 완전한 계보 확인을 위해 해당 Asset의 Version을 `version_number DESC`로 반환합니다. 공개 입력·응답에는 `created_by`를 포함하지 않으며 Artifact·Selection·Composition을 자동 생성하거나 변경하지 않습니다.
- AssetVersion 상세 경로는 Asset과 Version의 소속 관계를 함께 확인합니다. PATCH·DELETE Endpoint는 등록하지 않았습니다.

## 5. REST Method 원칙

| Method | 사용 기준 | 금지·주의 |
|---|---|---|
| `GET` | 단일 Resource 또는 Collection 조회 | 상태 변경, lazy 만료, 파일 생성 금지 |
| `POST` | Resource 생성, 새 Version·Snapshot·Job 생성, cancel·retry 같은 명시적 action | 기존 불변 Resource 덮어쓰기 금지 |
| `PATCH` | Workspace·Project·Asset·Recording 같은 변경 가능한 Metadata의 부분 수정 | AssetVersion·Snapshot·Job·Approval에 사용 금지 |
| `DELETE` | Soft Delete 또는 관계 해제 요청 | AssetVersion·Snapshot·Job·History 직접 삭제 금지 |

`PUT`은 v1에서 사용하지 않습니다. 전체 교체보다 명시적 생성과 제한된 Metadata PATCH를 사용합니다.

### 5.1 생성 상태 코드

- 동기 Resource 생성: `201 Created`
- Workspace Job 생성: `201 Created`로 불변 요청 snapshot을 기록하며 Worker 실행은 시작하지 않음
- Workspace Job retry와 실행 중 cancel marker 접수: `202 Accepted`
- 조회·PATCH·action 결과: `200 OK`
- body 없는 Soft Delete·관계 해제: `204 No Content`
- Idempotency 재생은 최초 요청과 같은 성공 status를 반환합니다.

## 6. Resource와 불변성

### 6.1 Asset

- Asset은 논리 객체이며 실제 파일을 포함하지 않습니다.
- `POST /assets`는 Asset만 생성하고 AssetVersion을 자동 생성하지 않습니다.
- Asset의 표시 Metadata와 Selection만 변경할 수 있습니다.
- Asset 삭제는 Soft Delete이며 Version·Artifact 삭제를 자동 실행하지 않습니다.

### 6.2 AssetVersion

- 새 내용·편집·AI 후보·처리 결과는 항상 `POST /assets/{asset_id}/versions`로 생성합니다.
- AssetVersion에는 PATCH와 DELETE Endpoint가 없습니다.
- Version 번호는 증가만 하며 Rollback은 과거 Version을 Selection으로 다시 선택하는 동작입니다.
- Provider가 기존 AssetVersion을 수정하지 않습니다.
- 목록은 최신 번호부터 반환하고 상세는 `/assets/{asset_id}/versions/{asset_version_id}`에서 같은 Asset 소속을 검증합니다.

### 6.3 Artifact

- Artifact는 실제 파일 또는 직렬화된 Payload입니다.
- API는 Artifact ID, kind, media type, size, checksum, retention status와 접근 link만 반환합니다.
- 응답에 drive, mount, 절대 경로, 상대 경로, 임시 경로와 model path를 포함하지 않습니다.
- 공개 Endpoint는 Metadata·content·download 3개뿐이며 POST·PATCH·DELETE·목록을 제공하지 않습니다.
- 공개 등록 대신 Provider·Worker·Import workflow의 trusted ingestion이 실제 bytes에서 SHA-256·크기·kind별 media type을 검증합니다. 호출자가 제출한 checksum·size·MIME·storage key·path는 authoritative 값이 아닙니다.
- content·download Endpoint는 매 요청 `Artifact → AssetVersion → Asset → owner_id`, retention, kind별 delivery allowlist, Catalog locator와 Artifact 무결성을 확인합니다.
- 내부 URI는 `artifact://<artifact_id>`이며 공개 응답은 API link를 사용합니다. Catalog의 backend·domain·storage key는 반환하지 않습니다.
- `active`만 정책상 content·download가 가능하며 `quarantined`는 409, `expired`·`pending_delete`·`deleted`는 410으로 거부합니다.
- 두 delivery Endpoint는 single byte range를 지원하고 multiple·invalid·unsatisfiable range는 `416 INVALID_RANGE`와 `Content-Range: bytes */<size>`로 거부합니다.
- 세부 Storage·ingestion·Range·파일명·오류 계약은 [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md)을 따릅니다. Catalog Entity와 revision `20260809_0016`은 실제 사용자 DB에 적용했고 Catalog·Resolver·trusted ingestion, Owner·retention·integrity read Gate, dry-run reconciliation, Range와 Artifact API를 구현했습니다. 실제 Catalog row는 0개이며 destructive repair는 아직 `[계획]`입니다.

### 6.4 Composition Snapshot

- Snapshot은 정확한 AssetVersion만 참조합니다.
- 생성 후 PATCH·DELETE하지 않습니다.
- Asset Selection이 바뀌어도 과거 Snapshot은 변하지 않습니다.
- effective Owner와 활성 Project scope를 검증하고 같은 Workspace Asset 또는 Owner 소유 Workspace 미지정 Asset만 허용합니다.
- 모든 참조 Asset은 생성 시점에 대상 Project의 활성 ProjectAsset 관계를 가져야 하며, 이후 관계 분리는 과거 Snapshot을 무효화하지 않습니다.
- 공개 role은 `lyrics`, `music`, `vocal`, `stem`, `mix`이며 Instrumental은 `music`으로 표현합니다.
- `snapshot_version`과 `created_by`는 공개 입력이 아니라 Service가 각각 Project의 다음 번호와 effective Owner에서 파생합니다.
- Snapshot과 전체 Item, Idempotency 완료 기록은 한 transaction에서 생성하고 일부만 남기지 않습니다.
- Repository·Service·Cursor 기반을 재사용한 공식 목록·생성·상세 Endpoint 3개를 구현했습니다. 생성은 필수 `Idempotency-Key`를 기존 `idempotency_records`에 연결하고 같은 요청을 최초 `201` 응답으로 재생합니다. 세부 계약은 [CompositionSnapshot API](composition-snapshot-foundation.md)을 따릅니다.

### 6.5 Job

- Job은 Pipeline 자체가 아니라 독립 실행 단위입니다.
- Job의 불변 요청, 입력 Version·Artifact, 설정, Provider와 Model Manifest를 기록합니다.
- 공통 상태는 `queued`, `running`, `succeeded`, `failed`, `cancelled`입니다.
- Retry는 기존 Job을 초기화하지 않고 새 `job_id`를 생성합니다.
- `progress_percent=100`만으로 성공을 확정하지 않고 출력 Artifact 검증 후 `succeeded`로 전이합니다.
- 공개 상태는 5개를 유지하고 실행 중 cancel 요청은 내부 marker로 분리합니다.
- byte-level 입력은 role과 명시적 Artifact ID로 고정하며 latest Artifact 자동 선택을 금지합니다.
- Workspace 전체 Collection은 `project_id`, `status`, `job_type` filter와 `(created_at DESC, job_id DESC)` HMAC Cursor를 사용합니다.
- 생성·입력 lineage·상태·진행률·취소·재시도·멱등성, aggregate read, Worker claim·lease와 completion Unit of Work를 구현했습니다. 공식 Router 5개는 Service만 호출하고 내부 claim·lease·Provider raw response를 공개하지 않습니다. Provider dispatch wiring과 background daemon·scheduler는 [Workspace Job Foundation](../03-architecture/workspace-job-foundation.md)의 후속 범위입니다.

## 7. 공통 성공 Response

### 7.1 단일 Resource

```json
{
  "data": {
    "asset_id": "opaque-id",
    "status": "active",
    "created_at": "2026-08-05T00:00:00Z",
    "updated_at": "2026-08-05T00:00:00Z",
    "links": {
      "self": "/api/v1/assets/opaque-id",
      "versions": "/api/v1/assets/opaque-id/versions"
    },
    "metadata": {}
  },
  "request_id": "opaque-request-id"
}
```

- ID field는 `asset_id`, `asset_version_id`, `artifact_id`, `composition_snapshot_id`, `job_id`처럼 Resource 고유 이름을 사용합니다.
- `status`는 해당 Resource가 상태를 가질 때만 사용합니다.
- 불변 Resource에 의미 없는 `updated_at`을 만들지 않고 field를 생략합니다.
- `links`는 권한 검사를 우회하지 않는 상대 API URL입니다.
- `metadata`는 allowlist와 Schema version이 정의된 경우에만 사용합니다.
- `request_id`는 추적용 opaque ID이며 내부 process 정보가 아닙니다.

### 7.2 Collection

```json
{
  "data": [],
  "pagination": {
    "limit": 20,
    "next_cursor": null,
    "has_more": false
  },
  "links": {
    "self": "/api/v1/assets?limit=20",
    "next": null
  },
  "request_id": "opaque-request-id"
}
```

## 8. 공통 Error Response

```json
{
  "error": {
    "error_code": "ASSET_VERSION_IMMUTABLE",
    "message": "AssetVersion은 수정할 수 없습니다.",
    "details": [],
    "request_id": "opaque-request-id"
  }
}
```

| Field | 규칙 |
|---|---|
| `error_code` | 대문자 `SNAKE_CASE`, programmatic contract |
| `message` | 안전한 한국어 사용자 메시지 또는 지역화된 메시지 |
| `details` | field validation 등 allowlist 구조. 없으면 빈 배열 |
| `request_id` | 서버 로그와 연결하는 opaque ID |

Stack trace, SQL, token, API key, 절대·상대 경로, 개인 음성 Metadata와 Dataset 내용을 반환하지 않습니다.

### 8.1 공통 HTTP 오류

| HTTP | 사용 기준 |
|---:|---|
| `400` | 잘못된 cursor·sort·filter 조합 |
| `401` | 인증 필요. 현재 구현은 [계획] |
| `403` | Workspace 권한 또는 Provider 내부 API 접근 거부 |
| `404` | Resource가 없거나 접근 권한상 존재를 숨김 |
| `409` | 상태 전이·Selection·Idempotency·Version 충돌 |
| `410` | 삭제·만료돼 더 이상 사용할 수 없는 Resource |
| `413` | 업로드 크기 초과 |
| `415` | 지원하지 않는 media type |
| `422` | 요청 Schema·field validation 실패 |
| `429` | rate limit 초과 |
| `500` | 처리되지 않은 내부 오류 |
| `503` | Provider·Dependency·Readiness 실패 |

## 9. Idempotency-Key

- Resource 또는 새 Version·Snapshot·Job을 생성하는 POST에는 `Idempotency-Key`가 필요합니다.
- Job Retry와 Enrollment 완료에도 필요합니다.
- cancel은 같은 최종 상태를 반환하는 idempotent action으로 설계하며 key는 선택 사항입니다.
- 권장 형식은 UUID이며 opaque ASCII 16~128자를 허용하는 방향을 검토합니다.
- scope는 Workspace, actor, HTTP Method와 정규화된 Path입니다.
- 서버는 raw key가 아니라 hash와 canonical request fingerprint를 저장합니다.
- 같은 key와 같은 fingerprint는 최초 성공 또는 진행 중 결과를 재생합니다.
- 같은 key와 다른 fingerprint는 `409 IDEMPOTENCY_KEY_REUSED`입니다.
- Retry replay는 새 Job을 추가 생성하지 않고 처음 만든 retry Job을 반환합니다.
- 보존 기간은 최소 24시간을 기본안으로 두되 운영 정책 확정이 필요합니다.
- CompositionSnapshot API는 기존 `idempotency_records`를 사용해 effective Owner·Project scope와 정규화된 body fingerprint를 24시간 보존합니다. 필수 HTTP `Idempotency-Key`가 같은 key·요청이면 최초 `201` aggregate를 재생하고 다른 요청이면 `IDEMPOTENCY_KEY_REUSED`로 거부하며 Snapshot·Item과 같은 transaction에 기록합니다.

## 10. Pagination, Filter, Sort와 Search

### 10.1 Cursor Pagination

- Collection은 cursor 방식을 기본으로 합니다.
- `limit` 기본값은 20, 최대값은 100입니다.
- `cursor`는 서버가 발급한 opaque 값이며 client가 해석하거나 수정하지 않습니다.
- 정렬 기준과 filter가 바뀌면 기존 cursor를 재사용하지 않습니다.
- `page` 기반 offset pagination은 v1 목표 계약에서 사용하지 않습니다. `page`와 `cursor`를 함께 지원해 결과가 달라지는 문제를 피합니다.
- Cursor payload는 version, Resource, 방향, 정렬, Resource별 마지막 position·UUID, filter fingerprint와 page limit을 포함합니다. CompositionSnapshot position은 `last_snapshot_version`입니다.
- Payload는 canonical JSON을 base64url로 인코딩하고 전용 `DOHAMUSIC_CURSOR_SIGNING_KEY`로 HMAC-SHA256 서명합니다. unsigned cursor는 허용하지 않습니다.
- Workspace·Project·Asset은 `(created_at DESC, resource_id DESC)`, ProjectAsset은 `(display_order ASC, project_asset_id ASC)`, CompositionSnapshot은 `(snapshot_version DESC, composition_snapshot_id DESC)` keyset과 `limit + 1` 조회를 사용합니다. `has_more=true`이면 `next_cursor`가 반드시 존재하고 마지막 page에서는 `null`입니다.
- 서명 키는 32바이트 이상이어야 하며 자동 생성·하드코딩·로그 출력을 금지합니다. App Factory가 설정값으로 codec을 구성하고 목록 기능 사용 시점에 검증합니다.
- 자세한 구현 경계는 [Cursor Pagination 설계](cursor-pagination.md)를 따릅니다.

### 10.2 Query 규칙

| Parameter | 규칙 |
|---|---|
| `limit` | 1~100 |
| `cursor` | opaque continuation token |
| `sort` | allowlist field. `-created_at`은 내림차순 |
| `search` | 제목·이름 등 Resource별 허용 field에만 적용 |
| `filter[field]` | 문서에 명시된 field와 enum만 허용 |
| `page` | v1 미지원. 전달 시 `400 PAGINATION_MODE_UNSUPPORTED` |

기본 정렬은 안정적인 `(created_at DESC, resource_id DESC)`입니다. 임의 SQL field, raw expression과 wildcard field를 받지 않습니다.

### 10.3 Asset 목록 Query

| Parameter | 공개 여부 | 규칙 |
|---|---|---|
| `workspace_id` | 허용 | UUID 직접 query 형식. 현재 effective Owner 소유 Workspace만 허용 |
| `asset_type` | 허용 | Common Specification과 `AssetType` enum 값만 허용 |
| `owner_id` | 금지 | 인증·Bootstrap context에서 파생하며 query·body·header로 받지 않음 |
| `include_deleted` | 금지 | 항상 `false`, `deleted_at IS NULL` 고정 |
| `lifecycle_status` | 금지 | 이번 v1 Asset 목록 filter에서 미지원 |
| `search` | 금지 | 검색 대상 Metadata 계약이 없어 미지원 |
| `sort` | 금지 | `(created_at DESC, asset_id DESC)` 고정 |

`workspace_id`를 생략하면 effective Owner의 Workspace 미지정 Asset을 포함한 전체 활성 Asset을 조회합니다. 임의 Owner 전체나 다른 Workspace의 Asset은 조회하지 않습니다. Router는 이 Query 계약을 Cursor fingerprint와 동일하게 적용합니다.

## 11. 권한과 Workspace 경계

- 현재 제품은 단일 사용자지만 Workspace ID를 모든 Project·Asset·Snapshot·Job 접근 경계로 유지합니다.
- 인증·Owner Entity와 다중 사용자 권한 구현은 [계획]입니다.
- client가 전달한 Workspace ID를 신뢰하지 않고 향후 인증 context와 비교합니다.
- 다른 Workspace의 Resource는 기본적으로 `404`로 숨깁니다.
- Provider API는 Frontend가 직접 호출할 수 없으며 Orchestrator 전용 scope가 필요합니다.
- 개인 음성 Artifact, Enrollment, Consent와 Commercial Status는 일반 Metadata보다 강한 권한 검사가 필요합니다.

## 12. OpenAPI 작성 기준

향후 OpenAPI 작성 시 다음을 적용합니다.

- API group별 tag와 안정적인 `operationId`
- request·response·error Schema 분리
- enum과 format 명시
- 모든 POST의 Idempotency header 명시
- cursor·filter·sort parameter 문서화
- 성공·validation·conflict·not found 예시
- path·비밀정보가 없는 Artifact와 Provider 예시
- `[계획]`, Legacy와 구현 완료 상태를 구분

이번 작업에서는 OpenAPI YAML, FastAPI decorator와 Pydantic Schema를 작성하지 않습니다.

## 13. 미확정 사항

- API ID의 UUID version과 전역 고유성 범위
- cursor 서명 키 교체와 만료 정책
- Idempotency-Key 보존 기간과 분산 환경 저장소
- optimistic concurrency와 `ETag`·`If-Match` 적용 범위
- Artifact object storage·서명 URL·replica와 대용량 checksum 검증 cache
- Approval API를 별도 group으로 공개할지 AssetVersion·Enrollment action에 포함할지
- 인증·Owner·Role·Workspace scope 모델
- Provider API의 network namespace와 서비스 인증 방식

## 14. D1 Project Composition aggregate — [D1-A Backend 완료 / Transition 계획]

`GET /api/v1/projects/{project_id}/composition`은 기존 Resource endpoint를 대체하지 않는 Frontend read projection이다. Project explicit selection 또는 선택적 `composition_snapshot_id` query를 resolve해 exact AssetVersion, safe Artifact reference, snapshot-local Track projection, Section availability, Mix JSON과 lineage를 반환한다.

최신 Snapshot을 current로 암묵 지정하지 않으며 GET에서 Legacy fallback·bootstrap·backfill·selection write를 수행하지 않는다. 단일 aggregate에는 Cursor를 넣지 않고 Version History는 기존 Snapshot 목록 Cursor를 재사용한다. 상세 response와 empty/auth/error 계약은 [D1 Composition Read Workspace](composition-read-workspace.md)를 따른다.
