# Workspace REST API Endpoint 목록

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-10
> 관련 기능: DohaMusic Workspace REST API 재설계
> 구현 상태: Workspace·MusicProject·ProjectAsset·Asset·AssetVersion·Artifact·CompositionSnapshot 25개 완료, 나머지 39개 Resource Endpoint 계획
> 관련 문서: [API 기반·Bootstrap](workspace-api-foundation-bootstrap.md), [공통 계약](workspace-rest-api-contract.md), [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md), [Provider API 계약](provider-api-contract.md), [API 전환 전략](api-contract-migration-strategy.md)

## 1. 요약

| API 그룹 | Endpoint 수 |
|---|---:|
| Workspace | 3 |
| Project | 5 |
| ProjectAsset | 3 |
| Asset | 5 |
| AssetVersion | 4 |
| Artifact | 3 |
| CompositionSnapshot | 3 |
| Job | 5 |
| Recording | 3 |
| Enrollment | 6 |
| Tag | 3 |
| Favorite | 3 |
| Comment | 4 |
| History | 2 |
| Provider | 10 |
| Health | 2 |
| **합계** | **64** |

Endpoint 수는 HTTP Method와 Path 조합을 한 개로 계산합니다. Workspace·MusicProject·ProjectAsset·Asset·AssetVersion·Artifact·CompositionSnapshot, 총 25개는 `[완료]`이며 나머지 39개는 `[계획]`입니다. 기존 `/api` Runtime 경로는 계속 운영 source of truth로 유지합니다.

## 2. Workspace API — 3개

| Method | Path | 성공 | 상태 | 목적 |
|---|---|---:|---|---|
| `GET` | `/api/v1/workspaces` | 200 | [완료] | HMAC Cursor 기반 Workspace 목록 |
| `GET` | `/api/v1/workspaces/{workspace_id}` | 200 | [완료] | Workspace 상세 |
| `PATCH` | `/api/v1/workspaces/{workspace_id}` | 200 | [완료] | Workspace 이름 수정 |

초기 단일 사용자 환경은 [명시적 Bootstrap 도구](workspace-api-foundation-bootstrap.md)로 기본 Workspace를 준비합니다. 도구는 구현했지만 실제 사용자 DB에는 실행하지 않았으므로 현재 기본 Workspace 존재를 완료로 간주하지 않습니다. Workspace 생성·삭제 Endpoint는 v1 범위에서 제외합니다.

## 3. Project API — 5개

| Method | Path | 성공 | 상태 | 목적 |
|---|---|---:|---|---|
| `GET` | `/api/v1/projects` | 200 | [완료] | HMAC Cursor 기반 Workspace Project 목록 |
| `POST` | `/api/v1/projects` | 201 | [완료] | MusicProject 생성 |
| `GET` | `/api/v1/projects/{project_id}` | 200 | [완료] | MusicProject 상세 |
| `PATCH` | `/api/v1/projects/{project_id}` | 200 | [완료] | 제목·설명 Metadata 수정 |
| `DELETE` | `/api/v1/projects/{project_id}` | 204 | [완료] | MusicProject Soft Delete |

Project 삭제가 연결 Asset, AssetVersion, Artifact, Snapshot과 Job을 삭제하지 않습니다.

공개 입력에는 `owner_id`와 `created_by`를 허용하지 않습니다. Project 생성 시 `created_by`는 요청한 Workspace의 `owner_id`에서 파생합니다. Workspace가 하나도 없으면 두 Collection API를 포함한 이 범위의 요청은 `409 WORKSPACE_BOOTSTRAP_REQUIRED`로 중단합니다.

공개 응답에서도 내부 `owner_id`와 `created_by`를 반환하지 않습니다. Project PATCH에서 `description`을 생략하면 기존 값을 유지하고 명시적 `null`은 `INVALID_INPUT`으로 거부합니다.

## 4. ProjectAsset API — 3개

| Method | Path | 성공 | 상태 | 목적 |
|---|---|---:|---|---|
| `GET` | `/api/v1/projects/{project_id}/assets` | 200 | [완료] | ProjectAsset 연결 목록 |
| `POST` | `/api/v1/projects/{project_id}/assets` | 201 | [완료] | 기존 Asset을 Project에 연결 |
| `DELETE` | `/api/v1/projects/{project_id}/assets/{asset_id}` | 204 | [완료] | ProjectAsset 관계 해제 |

Project는 Asset을 직접 소유하지 않습니다. POST body는 `asset_id`, 선택적 `role`, `display_order`를 가지며 Asset 또는 Version을 새로 만들지 않습니다.

세 Endpoint는 구현했습니다. 목록은 HMAC Cursor·Project filter·`display_order ASC, project_asset_id ASC` keyset Service와 실제 적용된 revision `20260807_0014` partial Index를 사용합니다. 같은 `(project_id, asset_id)` 관계는 하나만 허용하고 Soft Delete 후 재연결하면 기존 row를 복원하며 `role`과 `display_order`를 갱신합니다. POST는 Asset 또는 AssetVersion을 생성하지 않으며 DELETE는 관계만 Soft Delete합니다. 전체 Resource API 진행도는 CompositionSnapshot 3개를 포함해 25/64입니다.

## 5. Asset API — 5개

| Method | Path | 성공 | 상태 | 목적 |
|---|---|---:|---|---|
| `GET` | `/api/v1/assets` | 200 | [완료] | Asset 목록·filter |
| `POST` | `/api/v1/assets` | 201 | [완료] | 논리 Asset 생성 |
| `GET` | `/api/v1/assets/{asset_id}` | 200 | [완료] | Asset와 현재 Selection 조회 |
| `PATCH` | `/api/v1/assets/{asset_id}` | 200 | [완료] | 변경 가능한 Asset Metadata 수정 |
| `DELETE` | `/api/v1/assets/{asset_id}` | 204 | [완료] | Asset Soft Delete |

다섯 Endpoint를 구현했습니다. 목록은 신뢰된 effective Owner의 활성 Asset에 한정하고 선택적 `workspace_id=<uuid>`와 `asset_type`만 filter로 받으며 `(created_at DESC, asset_id DESC)` HMAC Cursor를 사용합니다. `owner_id`, `include_deleted`, lifecycle filter, 검색과 임의 sort는 공개하지 않습니다.

POST는 선택적 `workspace_id`, 필수 `asset_type`과 초기 `lifecycle_status`만 받으며 Version·Artifact·ProjectAsset을 자동 생성하지 않습니다. `owner_id`는 공개 입력으로 받지 않고 Bootstrap Workspace context에서 파생합니다. 저장소별 단일 Workspace 계약에서는 `workspace_id`를 생략할 수 있고, `asset_type`은 Common Specification과 DB Redesign에 정의된 값만 사용합니다. PATCH는 `lifecycle_status`만 허용하며 DELETE는 Version·Artifact·ProjectAsset을 보존한 채 Asset을 Soft Delete합니다.

## 6. AssetVersion API — 4개

| Method | Path | 성공 | 상태 | 목적 |
|---|---|---:|---|---|
| `POST` | `/api/v1/assets/{asset_id}/versions` | 201 | [완료] | 새 불변 AssetVersion 생성 |
| `GET` | `/api/v1/assets/{asset_id}/versions` | 200 | [완료] | Asset의 Version 목록 |
| `GET` | `/api/v1/assets/{asset_id}/versions/{asset_version_id}` | 200 | [완료] | AssetVersion 상세·Lineage 조회 |
| `POST` | `/api/v1/assets/{asset_id}/selection` | 200 | [계획] | 현재 Selection을 정확한 Version으로 변경 |

생성 요청에는 필수 `version_origin`, 선택적 `settings_snapshot`, `parent_asset_version_id`, `processing_chain_id`, `provider_id`, `model_manifest_id`만 허용합니다. `version_number`는 Service가 기존 최대 번호 다음 값으로 결정하고 `created_by`는 소유 Asset에서 파생합니다. 기존 Version·Selection·Artifact·Composition은 변경하거나 자동 생성하지 않습니다.

목록은 해당 Asset의 모든 Version을 `version_number DESC`로 반환하고, 상세는 URL의 Asset과 Version 소속이 정확히 일치해야 합니다. AssetVersion에는 PATCH와 DELETE가 없습니다. Selection Endpoint와 과거 Version 선택에 의한 Rollback은 아직 `[계획]`입니다. Resource API 진행도는 CompositionSnapshot 3개를 포함해 25/64입니다.

## 7. Artifact API — 3개

| Method | Path | 성공 | 목적 |
|---|---|---:|---|
| `GET` | `/api/v1/artifacts/{artifact_id}` | 200 | Artifact Metadata와 접근 link 조회 |
| `GET` | `/api/v1/artifacts/{artifact_id}/content` | 200/206 | 승인된 inline content 제공 |
| `GET` | `/api/v1/artifacts/{artifact_id}/download` | 200/206 | 승인된 attachment 제공 |

세 Endpoint는 모두 `[완료]`이며 Artifact API 진행도는 3/3입니다. 공개 POST·PATCH·DELETE·목록과 Version 하위 목록을 추가하지 않습니다. Artifact 응답에는 물리 경로·Catalog·storage key를 포함하지 않고 `artifact_id` 기반 API link만 제공합니다. content·download는 owner, retention, delivery allowlist, media type, 실제 크기와 SHA-256을 확인합니다. `quarantined`는 `409`, `expired`·`pending_delete`·`deleted`는 `410`으로 거부합니다. 전체 응답은 `200`, single byte range는 `206`, multiple·invalid·unsatisfiable range는 `416 INVALID_RANGE`이며 세부 계약은 [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md)을 따릅니다.

## 8. CompositionSnapshot API — 3개

| Method | Path | 성공 | 목적 |
|---|---|---:|---|
| `GET` | `/api/v1/snapshots` | 200 | Project별 Snapshot 목록 |
| `POST` | `/api/v1/snapshots` | 201 | 정확한 AssetVersion 구성 고정 |
| `GET` | `/api/v1/snapshots/{composition_snapshot_id}` | 200 | 불변 Snapshot 상세 |

POST는 `project_id`, 역할별 `asset_version_id`, `processing_chain_id`, Mix Settings, Provider version과 Model Manifest ID를 받습니다. Asset 최신 Version을 간접 참조하지 않습니다. PATCH와 DELETE는 없습니다.

세 Endpoint는 `[완료]`입니다. 목록은 필수 `project_id`와 `snapshot_version DESC, composition_snapshot_id DESC` HMAC Cursor를 사용하며 summary만 반환합니다. 생성은 필수 `Idempotency-Key`, body 안의 Item, exact AssetVersion, effective Owner·ProjectAsset scope, 자동 version과 단일 transaction을 사용해 불변 aggregate를 `201`로 반환합니다. 상세는 정렬된 전체 Item과 bounded lineage를 반환합니다. PATCH·DELETE와 독립 SnapshotItem Route는 제공하지 않습니다. CompositionSnapshot API는 3/3, 전체 Resource API는 25/64입니다.

## 9. Job API — 5개

| Method | Path | 성공 | 목적 |
|---|---|---:|---|
| `GET` | `/api/v1/jobs` | 200 | Workspace Job 목록·filter |
| `POST` | `/api/v1/jobs` | 202 | 독립 비동기 Job 생성 |
| `GET` | `/api/v1/jobs/{job_id}` | 200 | 상태·입력·출력·오류·진행률 조회 |
| `POST` | `/api/v1/jobs/{job_id}/cancel` | 200/202 | 취소 요청 또는 최종 취소 상태 반환 |
| `POST` | `/api/v1/jobs/{job_id}/retry` | 202 | 새 retry Job 생성 |

### 9.1 Job 유형

- `lyrics_generation`
- `lyrics_revision`
- `music_generation`
- `stem_separation`
- `vocal_generation`
- `voice_conversion`
- `vocal_correction`
- `mix`
- `export`

POST body는 `job_type`, `project_id`, 선택적 `composition_snapshot_id`, `input_asset_version_ids`, `input_artifact_ids`, `provider_id`, `model_manifest_id`와 `settings_snapshot`을 사용합니다.

Job 생성이 기존 AssetVersion을 수정하지 않습니다. 성공 결과의 `output_asset_version_ids`, `output_artifact_ids`는 DohaMusic이 Provider 결과를 검증·등록한 뒤 공개합니다.

## 10. Recording API — 3개

Recording은 `recording` 유형 Asset이고 Take는 해당 Asset의 AssetVersion입니다.

| Method | Path | 성공 | 목적 |
|---|---|---:|---|
| `GET` | `/api/v1/assets/{asset_id}/takes` | 200 | Recording Take 목록 |
| `POST` | `/api/v1/assets/{asset_id}/takes` | 201 | 새 Recording Take와 Artifact 등록 요청 |
| `GET` | `/api/v1/recording-takes/{asset_version_id}` | 200 | 특정 Take 상세 |

Recording Asset의 생성·조회·Metadata PATCH·Soft Delete는 Asset API 하나만 사용합니다. Recording API는 `asset_type=recording` Asset의 Take 생성·조회에만 책임을 둬 중복 mutation을 피합니다.

Take는 AssetVersion이므로 PATCH·DELETE하지 않습니다. 잘못된 Take 정정은 새 Take를 생성하고 Selection을 변경합니다.

## 11. Enrollment API — 6개

| Method | Path | 성공 | 목적 |
|---|---|---:|---|
| `GET` | `/api/v1/enrollments` | 200 | Workspace RecordingEnrollment 목록 |
| `POST` | `/api/v1/enrollments` | 201 | Recording Take 기반 Enrollment 생성 |
| `GET` | `/api/v1/enrollments/{recording_enrollment_id}` | 200 | Enrollment·Consent·Approval 상태 조회 |
| `POST` | `/api/v1/enrollments/{recording_enrollment_id}/complete` | 200 | 검증된 Enrollment 완료·Approval 기록 |
| `POST` | `/api/v1/enrollments/{recording_enrollment_id}/cancel` | 200 | 미완료 Enrollment 취소 |
| `DELETE` | `/api/v1/enrollments/{recording_enrollment_id}` | 204 | Enrollment Soft Delete·철회 요청 |

Enrollment는 `recording_asset_version_id`, Consent policy version과 접근 제어된 evidence ID를 참조합니다. Recording 파일 upload와 Take 생성은 Recording API가 담당하며 같은 Endpoint를 사용하지 않습니다. Enrollment가 Recording을 Training Dataset으로 자동 편입하지 않습니다.

## 12. Tag API — 3개

| Method | Path | 성공 | 목적 |
|---|---|---:|---|
| `GET` | `/api/v1/assets/{asset_id}/tags` | 200 | Asset Tag 목록 |
| `POST` | `/api/v1/assets/{asset_id}/tags` | 201 | Tag 연결 생성 |
| `DELETE` | `/api/v1/assets/{asset_id}/tags/{tag_id}` | 204 | Tag Soft Delete |

Tag 이름 변경은 기존 Tag를 수정하지 않고 삭제·새 생성하는 방향을 우선합니다.

## 13. Favorite API — 3개

| Method | Path | 성공 | 목적 |
|---|---|---:|---|
| `GET` | `/api/v1/favorites` | 200 | Workspace Favorite 목록 |
| `POST` | `/api/v1/favorites` | 201 | Asset Favorite 생성 |
| `DELETE` | `/api/v1/favorites/{favorite_id}` | 204 | Favorite 해제 |

`(workspace_id, asset_id)`는 하나만 존재하며 같은 POST를 Idempotency replay하면 기존 Favorite를 반환합니다.

## 14. Comment API — 4개

| Method | Path | 성공 | 목적 |
|---|---|---:|---|
| `GET` | `/api/v1/versions/{asset_version_id}/comments` | 200 | Version Comment 목록 |
| `POST` | `/api/v1/versions/{asset_version_id}/comments` | 201 | Version Comment 생성 |
| `PATCH` | `/api/v1/comments/{comment_id}` | 200 | Comment 본문 수정 |
| `DELETE` | `/api/v1/comments/{comment_id}` | 204 | Comment Soft Delete |

Comment는 특정 AssetVersion에 고정됩니다. Comment 수정이 Version 내용이나 계보를 바꾸지 않습니다.

## 15. History API — 2개

| Method | Path | 성공 | 목적 |
|---|---|---:|---|
| `GET` | `/api/v1/history` | 200 | Workspace append-only History 목록 |
| `GET` | `/api/v1/history/{history_id}` | 200 | History 상세 |

History 생성·수정·삭제 Endpoint는 없습니다. Resource mutation과 상태 전이에서 서버가 생성하며 민감정보와 경로를 기록하지 않습니다.

## 16. Provider API — 10개

Provider API는 DohaMusic Orchestrator 전용입니다. `{provider_id}`는 승인된 `lm`, `audio`, `vocal` Provider 식별자를 사용합니다.

| Method | Path | 성공 | 목적 |
|---|---|---:|---|
| `GET` | `/api/v1/providers` | 200 | 설정된 Provider와 계약 version 요약 |
| `GET` | `/api/v1/providers/{provider_id}/capabilities` | 200 | GetCapabilities |
| `GET` | `/api/v1/providers/{provider_id}/model-manifests/{model_manifest_id}` | 200 | GetModelManifest |
| `POST` | `/api/v1/providers/{provider_id}/jobs` | 202 | CreateJob |
| `GET` | `/api/v1/providers/{provider_id}/jobs/{job_id}` | 200 | GetJobStatus |
| `POST` | `/api/v1/providers/{provider_id}/jobs/{job_id}/cancel` | 200/202 | CancelJob |
| `POST` | `/api/v1/providers/{provider_id}/jobs/{job_id}/retry` | 202 | RetryJob |
| `GET` | `/api/v1/providers/{provider_id}/jobs/{job_id}/result` | 200 | GetResult |
| `GET` | `/api/v1/providers/{provider_id}/health` | 200/503 | Health |
| `GET` | `/api/v1/providers/{provider_id}/readiness` | 200/503 | Readiness |

따라서 요청 예시인 `/providers/lm/jobs`, `/providers/audio/jobs`, `/providers/vocal/jobs`는 `{provider_id}` instantiation으로 표현됩니다. 상세 계약은 [Provider API 계약](provider-api-contract.md)을 따릅니다.

## 17. Health API — 2개

| Method | Path | 성공 | 목적 |
|---|---|---:|---|
| `GET` | `/health` | 200 | DohaMusic process 생존 여부 |
| `GET` | `/readiness` | 200/503 | DB·Queue 등 새 요청 수락 가능 여부 |

Health 응답은 비밀정보, dependency 경로, token, GPU process detail과 개인 데이터를 포함하지 않습니다. Provider별 상태는 Provider API에서 분리합니다.

## 18. Endpoint 중복 검토

| 잠재 중복 | 결정 |
|---|---|
| Asset와 Recording | Recording Asset CRUD는 Asset API만 담당하고 Recording API는 Take 생성·조회만 담당 |
| `/jobs`와 `/providers/{provider_id}/jobs` | 전자는 Workspace Job, 후자는 Orchestrator 내부 Provider transport로 권한·책임 분리 |
| `/artifacts/{id}`와 Job result | Job은 Artifact ID·link만 반환하고 Artifact Metadata·content는 Artifact API가 담당 |
| `/projects/{id}/assets`와 Asset 생성 | ProjectAsset는 기존 Asset 연결만 담당하고 Asset을 생성하지 않음 |
| Selection과 Snapshot | Selection은 현재 채택 상태, Snapshot은 여러 정확한 Version을 고정한 불변 구성 |
| Recording과 Enrollment | Recording은 작품 Asset·Take, Enrollment는 음색 등록·Consent·Approval |

## 19. 미확정 Endpoint

- Approval을 별도 `/approvals` group으로 노출할지 Enrollment·Selection action 결과로만 제공할지
- AssetRelation 생성·조회 API를 별도 group으로 공개할지 Version 생성과 Job 결과에서만 관리할지
- ProcessingChain 편집·게시 API의 초기 범위
- Artifact upload를 Recording Take 이외 도메인에도 직접 허용할지
- Preview Artifact의 전용 streaming Endpoint 필요 여부

미확정 항목은 64개 목표 Endpoint 수에 포함하지 않습니다.
