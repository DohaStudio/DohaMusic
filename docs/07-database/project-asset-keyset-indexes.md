# ProjectAsset keyset Index 설계

> 문서 상태: [완료]
> 최종 수정일: 2026-08-07
> 관련 기능: ProjectAsset Cursor Pagination 선행 기반
> 구현 상태: Cursor·Repository·Service page·Resource Router·Entity metadata·Alembic `20260807_0014`와 실제 사용자 DB 적용 완료
> 관련 문서: [Cursor Pagination](../06-api/cursor-pagination.md), [REST API 계약](../06-api/workspace-rest-api-contract.md), [Migration 전략](database-redesign-migration-strategy.md)

## 1. 정렬과 조회 계약

ProjectAsset 목록은 Project 안의 표시 의미를 보존하기 위해 다음 순서를 사용합니다.

```text
display_order ASC
project_asset_id ASC
```

같은 `display_order`에서는 UUID가 tie-breaker이므로 결과는 결정적입니다. 조회는 `project_id`에 고정하고 Soft Delete row를 제외합니다. 다음 page 조건은 아래와 같습니다.

```text
display_order > last_display_order
OR (
  display_order = last_display_order
  AND project_asset_id > last_id
)
```

외부 offset은 사용하지 않습니다. Service는 `limit + 1`개를 조회하고 `has_more=true`일 때 마지막 반환 row의 position으로 다음 Cursor를 발급합니다.

## 2. Cursor 계약

ProjectAsset은 기존 HMAC-SHA256·canonical JSON·base64url 서명을 재사용하고 `resource=project_asset`, `sort=display_order_asc`로 payload schema를 구분합니다.

| 필드 | 값 |
|---|---|
| `v` | `1` |
| `resource` | `project_asset` |
| `direction` | `next` |
| `sort` | `display_order_asc` |
| `last_display_order` | 직전 page 마지막 row의 0 이상 정수 |
| `last_id` | 직전 page 마지막 `project_asset_id` |
| `filter_hash` | `project_id`, 활성 row 조건과 정렬의 fingerprint |
| `limit` | 1~100 |

ProjectAsset payload에는 가짜 `last_created_at`을 넣지 않습니다. Resource별 정확한 field 집합을 검증하므로 기존 Workspace·Project version 1 token의 payload와 의미를 변경하지 않습니다. 다른 Project에서 Cursor를 재사용하면 filter mismatch로 `INVALID_CURSOR`입니다.

## 3. Index 후보 비교

Alembic `20260807_0013`까지 적용한 임시 SQLite에 여러 Project와 Project당 500개 연결, 동일 `display_order`, 활성·Soft Delete row를 구성했습니다.

| 후보 | Column·조건 | 첫 page | 다음 page | TEMP B-TREE |
|---|---|---|---|---|
| 기존 개별 Index | `project_id` | `ix_project_assets_project_id` 사용 | 동일 | 존재 |
| full | `project_id, deleted_at, display_order, project_asset_id` | 후보 Index 사용 | 후보 Index 사용 | 없음 |
| partial | `project_id, display_order, project_asset_id WHERE deleted_at IS NULL` | 후보 Index 사용 | 후보 Index 사용 | 없음 |

full과 partial 후보는 같은 정렬 결과와 row를 반환했습니다. ProjectAsset 외부 목록은 활성 row만 조회하므로 크기가 작고 목적이 명확한 partial 후보를 선택했습니다.

## 4. 최종 Index

```text
ix_project_assets_active_keyset
ON project_assets(project_id, display_order, project_asset_id)
WHERE deleted_at IS NULL
```

Entity metadata와 Alembic revision은 이름, Column 순서와 SQLite predicate를 동일하게 유지합니다. 기존 `(project_id, asset_id)` Unique Constraint, FK, Column과 row는 변경하지 않습니다.

## 5. 중복과 restore 계약

DohaStudio Common Specification `0.1.0 / draft-baseline`에는 `(project_id, asset_id, role)` 중복 방지 표현이 있습니다. DohaMusic은 다음 근거로 더 엄격한 `(project_id, asset_id)` identity를 유지합니다.

- 현재 Entity와 실제 DB의 `uq_project_assets_project_asset`이 두 field만 사용합니다.
- Service는 같은 연결의 role 변경을 새 관계 생성이 아니라 Metadata 변경으로 처리합니다.
- Soft Delete 후 재연결은 기존 `project_asset_id`를 복원하고 role·display order를 갱신합니다.
- 계획된 DELETE 경로는 `{project_id}`와 `{asset_id}`만 받아 role별 연결을 구분하지 않습니다.

따라서 같은 Asset을 같은 Project에 role만 바꿔 여러 번 연결하지 않습니다. Common Specification의 role 포함 조합은 다른 저장소가 더 넓은 관계 identity를 채택할 수 있는 초안 기준이며 DohaMusic v1 계약에는 적용하지 않습니다.

## 6. Migration 경계

`20260807_0014`는 이전 head `20260807_0013` 다음의 단일 revision입니다.

- Upgrade: `ix_project_assets_active_keyset` 하나만 생성
- Downgrade: 같은 Index 하나만 제거
- Table·Column·FK·Unique·data 변경: 없음
- backfill: 없음
- 실제 사용자 DB 적용: 완료

임시 SQLite upgrade·downgrade에서 row 수, 기존 schema, `quick_check`, `integrity_check`와 `foreign_key_check`를 보존했습니다. 이후 별도 read-only Inventory, backup·restore rehearsal, migration·downgrade rehearsal과 명시적 승인 Gate를 거쳐 실제 사용자 DB에도 적용했습니다.

실제 사용자 DB 적용 결과는 다음과 같습니다.

- 적용 전·후 revision: `20260807_0013 → 20260807_0014`
- 첫 page·다음 page: 모두 `ix_project_assets_active_keyset` 사용
- TEMP B-TREE·full scan: 0건
- 전체 application row count·결정적 data digest: 전후 동일
- `quick_check`·`integrity_check`: `ok`
- `foreign_key_check`: 위반 0건
- 정식 backup·manifest: 보존
- 자동 downgrade·restore: 실행하지 않음

상세 증거는 [ProjectAsset keyset Index 실제 DB 적용 검증](../../reports/validation/VALIDATION-PROJECT-ASSET-KEYSET-INDEX-APPLICATION.md)에 기록했습니다.

## 7. 후속 작업

1. `[완료]` 실제 사용자 DB에 `20260807_0014`를 적용했습니다.
2. `[완료]` ProjectAsset Resource Router 3개를 Cursor page와 연결했습니다.
3. `[계획]` Asset Cursor·Index와 Resource API 5개를 구현합니다.
3. `[계획]` API에서 Bootstrap Required, Project·Asset Not Found, 중복·restore·연결 해제 계약을 검증합니다.

Resource API 진행도는 현재 25/64이며 ProjectAsset 3개, Asset 5개, AssetVersion 3개와 Artifact 3개 Endpoint가 완료됐습니다.
