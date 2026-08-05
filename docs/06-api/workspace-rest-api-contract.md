# Workspace REST API 공통 계약

> 문서 상태: [계획]
> 최종 수정일: 2026-08-05
> 관련 기능: DohaMusic Workspace REST API 재설계
> 구현 상태: API 계약 문서만 작성, FastAPI·Endpoint·OpenAPI YAML·SQL·ORM·테스트 미구현
> 관련 문서: [Endpoint 목록](workspace-rest-api-endpoints.md), [Provider API 계약](provider-api-contract.md), [API 전환 전략](api-contract-migration-strategy.md), [ADR-031](../11-decisions/ADR-031-workspace-rest-api-contract.md)

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

기준은 [DohaStudio/.github Draft PR #2](https://github.com/DohaStudio/.github/pull/2)의 commit `2a804e2`입니다.

- Asset, AssetVersion, Artifact와 AssetRelation
- Provider Contract와 Job Contract
- Model Manifest와 Dataset Manifest
- Composition Snapshot과 Storage Layout
- Common Terms

### 2.2 DohaMusic Database Redesign

DB 기준은 [DohaMusic Draft PR #52](https://github.com/DohaStudio/DohaMusic/pull/52)의 commit `4c4b87c`입니다.

- 21개 목표 Entity와 Table
- ProjectAsset N:M 관계
- 불변 AssetVersion·CompositionSnapshot·Job 계보
- Artifact ID와 경로 비노출
- Recording Asset와 RecordingEnrollment 분리
- Selection과 Approval 분리

두 선행 PR은 아직 Draft입니다. 계약이 변경되면 API 구현 전에 이 문서를 다시 검토합니다.

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
- 비동기 Job 접수: `202 Accepted`
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

### 6.3 Artifact

- Artifact는 실제 파일 또는 직렬화된 Payload입니다.
- API는 Artifact ID, kind, media type, size, checksum, retention status와 접근 link만 반환합니다.
- 응답에 drive, mount, 절대 경로, 상대 경로, 임시 경로와 model path를 포함하지 않습니다.
- content·download Endpoint는 매 요청 권한과 Artifact 무결성·보존 상태를 확인하는 계약입니다.

### 6.4 Composition Snapshot

- Snapshot은 정확한 AssetVersion만 참조합니다.
- 생성 후 PATCH·DELETE하지 않습니다.
- Asset Selection이 바뀌어도 과거 Snapshot은 변하지 않습니다.

### 6.5 Job

- Job은 Pipeline 자체가 아니라 독립 실행 단위입니다.
- Job의 불변 요청, 입력 Version·Artifact, 설정, Provider와 Model Manifest를 기록합니다.
- 공통 상태는 `queued`, `running`, `succeeded`, `failed`, `cancelled`입니다.
- Retry는 기존 Job을 초기화하지 않고 새 `job_id`를 생성합니다.
- `progress_percent=100`만으로 성공을 확정하지 않고 출력 Artifact 검증 후 `succeeded`로 전이합니다.

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

## 10. Pagination, Filter, Sort와 Search

### 10.1 Cursor Pagination

- Collection은 cursor 방식을 기본으로 합니다.
- `limit` 기본값은 20, 최대값은 100입니다.
- `cursor`는 서버가 발급한 opaque 값이며 client가 해석하거나 수정하지 않습니다.
- 정렬 기준과 filter가 바뀌면 기존 cursor를 재사용하지 않습니다.
- `page` 기반 offset pagination은 v1 목표 계약에서 사용하지 않습니다. `page`와 `cursor`를 함께 지원해 결과가 달라지는 문제를 피합니다.

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

- Common Specification과 DB Redesign의 merge·contract version
- `Asset.project_id`와 N:M ProjectAsset의 공통 명세 충돌
- API ID의 UUID version과 전역 고유성 범위
- cursor 서명·만료·암호화 방식
- Idempotency-Key 보존 기간과 분산 환경 저장소
- optimistic concurrency와 `ETag`·`If-Match` 적용 범위
- Artifact content·download의 Range, 만료 link와 object storage 전환
- Approval API를 별도 group으로 공개할지 AssetVersion·Enrollment action에 포함할지
- 인증·Owner·Role·Workspace scope 모델
- Provider API의 network namespace와 서비스 인증 방식
