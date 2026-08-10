# HMAC Cursor Pagination 설계

> 문서 상태: [완료]
> 최종 수정일: 2026-08-10
> 관련 기능: Workspace v1 목록의 opaque cursor와 keyset 조회 기반
> 구현 상태: Workspace·Project·ProjectAsset·Asset Router와 CompositionSnapshot Service Cursor 구현, 실제 DB 0013~0015 적용 완료
> 관련 문서: [Workspace REST API 계약](workspace-rest-api-contract.md), [CompositionSnapshot 기반](composition-snapshot-foundation.md), [API 전환 전략](api-contract-migration-strategy.md), [Backend 아키텍처](../03-architecture/backend-architecture.md), [Workspace·Project Index](../07-database/workspace-keyset-indexes.md), [ProjectAsset Index](../07-database/project-asset-keyset-indexes.md), [Asset Index](../07-database/asset-keyset-indexes.md)

## 1. 목적과 범위

Workspace v1 목록은 외부에 offset을 노출하지 않고 안정적인 keyset pagination을 사용합니다. Workspace·Project·ProjectAsset·Asset 조회를 Resource Router에 연결했고 CompositionSnapshot은 Service 기반까지 구현했습니다. 인증·backfill은 포함하지 않습니다.

## 2. 서명 키

`DOHAMUSIC_CURSOR_SIGNING_KEY`는 Cursor 전용 비밀값이며 UTF-8 기준 32바이트 이상이어야 합니다. 자동 생성값이나 Production 기본값을 제공하지 않고 Pydantic `SecretStr`로 보관합니다. `.env.example` 값은 공개 placeholder가 유효한 키로 사용되지 않도록 비워 둡니다. 기존 Runtime과 Bootstrap은 cursor가 필요하지 않으므로 앱 시작을 막지 않으며 `CursorCodec` 구성 또는 page 기능 사용 시점에 검증합니다.

실제 비밀값은 Git·문서·오류·로그에 기록하지 않습니다. `backend/.env.example`에는 빈 설정 항목과 생성 기준 주석만 둡니다. JWT 등 다른 목적의 비밀키와 공유하지 않습니다.

## 3. 토큰 계약

토큰 형식은 다음과 같습니다.

```text
base64url(canonical-json-payload).base64url(hmac-sha256-signature)
```

Payload 필드는 다음으로 고정합니다.

| 필드 | 값 |
|---|---|
| `v` | `1` |
| `resource` | `workspace`, `project`, `project_asset`, `asset` 또는 `composition_snapshot` |
| `direction` | `next` |
| `sort` | `created_at_desc` |
| `last_created_at` | Workspace·Project·Asset 직전 page 마지막 row의 UTC ISO 8601 시각 |
| `last_display_order` | ProjectAsset 직전 page 마지막 row의 정확한 정수 표시 순서 |
| `last_snapshot_version` | CompositionSnapshot 직전 page 마지막 row의 정확한 양의 정수 version |
| `last_id` | 직전 page 마지막 row의 UUID |
| `filter_hash` | canonical filter JSON의 SHA-256 |
| `limit` | 1~100의 page 크기 |

Workspace·Project·Asset payload는 `last_created_at`, ProjectAsset payload는 `last_display_order`, CompositionSnapshot payload는 `last_snapshot_version`만 사용합니다. 여러 position field를 한 token에 함께 넣지 않습니다. ProjectAsset은 `sort=display_order_asc`, CompositionSnapshot은 `sort=snapshot_version_desc`를 사용합니다. 새 Resource 값과 전용 payload shape를 추가하되 version 1과 기존 token 의미를 바꾸지 않습니다. Payload에 owner·Workspace 이름·Project 제목·DB 경로·Table명·SQL·credential을 넣지 않습니다.

## 4. 검증과 오류

Decode는 2 KiB 최대 길이를 먼저 확인한 뒤 token 구조와 base64url, `compare_digest` 기반 서명, Resource별 정확한 payload field 집합, version, Resource, 방향, 정렬, UUID, position, filter fingerprint와 limit을 검증합니다. `v`·`limit`·ProjectAsset `last_display_order`·CompositionSnapshot `last_snapshot_version`은 Boolean·실수·문자열을 허용하지 않는 정확한 정수입니다. 실패 원인은 내부 `reason`으로만 구분하며 외부에는 `422 INVALID_CURSOR`와 고정 메시지만 제공합니다.

서명 키가 없거나 짧으면 `500 CURSOR_CONFIGURATION_ERROR`, 요청 limit이 범위를 벗어나면 `422 INVALID_LIMIT`입니다. 서명값과 payload 원문을 오류에 포함하지 않습니다.

## 5. Filter fingerprint

Workspace fingerprint는 `include_deleted=false`, 정렬과 내부 owner filter를 사용합니다. Project fingerprint는 `workspace_id`, ProjectAsset fingerprint는 `project_id`와 `include_deleted=false`·정렬을 사용합니다. Asset fingerprint는 신뢰된 effective Owner, 선택적 `workspace_id`·`asset_type`, `include_deleted=false`와 정렬을 사용합니다. CompositionSnapshot fingerprint는 effective Owner, `project_id`, 활성 Project 조건과 정렬을 사용합니다. JSON key 정렬과 공백 없는 canonical 직렬화 뒤 SHA-256을 계산하므로 다른 Owner·Workspace·Project·Asset type·정렬 조건에 cursor를 재사용할 수 없습니다.

## 6. Keyset 조회

Workspace·Project·Asset 정렬은 `(created_at DESC, UUID DESC)`입니다. 다음 page 조건은 아래와 같습니다.

```text
created_at < last_created_at
OR (created_at = last_created_at AND resource_id < last_id)
```

Repository는 SQLAlchemy 2.0 `select()`만 사용하고 Soft Delete row를 제외합니다. 기존 내부 `limit`·`offset` 메서드는 호환성을 위해 유지하지만 API용 page Service는 `list_*_after()`만 사용합니다.

ProjectAsset은 관계 표시 의미를 보존하기 위해 `(display_order ASC, project_asset_id ASC)`로 정렬합니다.

```text
display_order > last_display_order
OR (display_order = last_display_order AND project_asset_id > last_id)
```

ProjectAsset cursor는 `project_id` filter에 결합되며 다른 Project에서 재사용하면 `INVALID_CURSOR`입니다. 동일 `display_order`는 UUID로 결정적으로 정렬하고 Soft Delete row를 제외합니다.

CompositionSnapshot은 `(snapshot_version DESC, composition_snapshot_id DESC)`로 정렬합니다.

```text
snapshot_version < last_snapshot_version
OR (snapshot_version = last_snapshot_version AND composition_snapshot_id < last_id)
```

Project filter와 effective Owner scope에 token을 결합합니다. 기존 `(project_id, snapshot_version)` Unique Index로 6,000개 임시 SQLite fixture의 첫·다음 page에서 Index를 사용하고 TEMP B-TREE와 전체 Table scan이 발생하지 않아 신규 Index와 Alembic revision은 추가하지 않습니다.

Service는 `limit + 1`개를 조회해 `has_more`를 계산하고 응답 항목은 `limit`개로 자릅니다. 다음 row가 있으면 마지막 반환 row로 서명된 `next_cursor`를 만들고, 마지막 page와 빈 page에서는 `has_more=false`, `next_cursor=null`을 반환합니다.

페이지 사이에 row가 생성·삭제될 수 있으므로 이 계약은 전체 목록의 snapshot isolation을 보장하지 않습니다. 새로 생성된 상위 row를 과거 cursor가 다시 탐색하지 않고 Soft Delete된 후속 row는 제외하며, 이미 반환한 row를 재반환하지 않는 forward-only keyset 동작을 보장합니다.

Alembic `20260807_0013`은 전체 활성 Workspace용 `(deleted_at, created_at, workspace_id)`, owner별 활성 Workspace용 `(owner_id, deleted_at, created_at, workspace_id)`, Workspace별 활성 MusicProject용 `(workspace_id, deleted_at, created_at, project_id)` 복합 Index를 추가합니다. 임시 SQLite의 첫·다음 page 여섯 쿼리에서 신규 Index가 선택되고 정렬용 임시 B-Tree가 제거됐습니다. SQLite는 ASC Index를 역방향으로 탐색하므로 metadata와 migration에는 명시적 DESC를 사용하지 않습니다.

`deleted_at IS NULL` partial 후보는 owner별 Workspace와 Project에는 사용됐지만 기존 `ix_workspaces_deleted_at`가 owner 없는 목록에서 계속 선택되어 임시 정렬을 제거하지 못했습니다. 기존 Index를 제거하거나 Repository에 Index hint를 넣지 않고 현재 쿼리 의미를 유지하기 위해 비-partial 구성을 선택했습니다. 세부 후보와 계획은 [Workspace keyset Index 설계](../07-database/workspace-keyset-indexes.md)를 따릅니다. 신규 revision은 승인된 절차로 실제 사용자 DB에 적용했습니다.

ProjectAsset은 full `(project_id, deleted_at, display_order, project_asset_id)`와 partial `(project_id, display_order, project_asset_id) WHERE deleted_at IS NULL` 후보가 모두 첫·다음 page에서 임시 정렬을 제거했습니다. 활성 row만 포함하고 같은 계획 결과를 제공하는 partial 후보를 `20260807_0014` revision으로 선택해 실제 사용자 DB에 적용했습니다. 실제 Query Plan에서도 첫 page·다음 page 모두 신규 Index를 사용하고 TEMP B-TREE는 발생하지 않았습니다. 세부 결과는 [ProjectAsset keyset Index 설계](../07-database/project-asset-keyset-indexes.md)를 따릅니다.

Asset 공개 목록은 Owner를 필수 내부 scope로 고정하고 `workspace_id=<uuid>`와 `asset_type`만 선택적으로 허용합니다. 6,000개 임시 SQLite fixture에서 Owner, Owner+type, Owner+Workspace와 Owner+Workspace+type의 첫·다음 page 8개 Query를 비교했습니다. partial 후보는 기존 `ix_assets_deleted_at`가 계속 선택돼 임시 정렬이 남았고, full Owner 및 Owner+Workspace 후보만 신규 Index 사용과 TEMP B-TREE 제거를 모두 만족했습니다. source revision `20260808_0015`의 두 full Index는 실제 사용자 DB에 적용을 완료했습니다. 세부 결과는 [Asset keyset Index 설계](../07-database/asset-keyset-indexes.md)를 따릅니다.

## 7. 후속 작업

1. `[완료]` Preflight·backup·rehearsal과 승인 후 실제 사용자 DB에 `20260807_0013`을 적용했습니다.
2. `[완료]` App composition에서 환경 설정으로 `CursorCodec`을 구성했습니다.
3. `[완료]` Workspace·Project Resource 목록 Route에 `limit`과 `cursor`를 연결했습니다.
4. `[완료]` Collection Envelope의 `has_more`와 `next_cursor` 불변 조건을 API 테스트로 검증했습니다.
5. `[완료]` ProjectAsset 전용 position·Project filter·Repository·Service page와 0014 Index를 임시 SQLite에서 검증했습니다.
6. `[완료]` 승인된 절차로 실제 사용자 DB에 0014를 적용했습니다.
7. `[완료]` ProjectAsset Resource Router 3개를 연결했습니다.
8. `[완료]` Asset 공개 scope·filter, version 1 Cursor, keyset Repository·Service와 source Index revision `20260808_0015`를 구현했습니다.
9. `[완료]` 별도 승인 절차로 실제 사용자 DB에 0015를 적용한 뒤 Asset Resource API 5개를 구현했습니다.
10. `[완료]` CompositionSnapshot 전용 position·Project/Owner fingerprint와 keyset Repository·Service를 구현하고 기존 Unique Index의 Query Plan을 검증했습니다.
11. `[계획]` CompositionSnapshot Router에서 목록 Cursor를 연결합니다.
12. 운영 전 서명 키 교체와 cursor 만료 정책을 확정합니다.

나머지 42개 Resource Endpoint, 인증·권한, Frontend, backfill·dual write는 별도 PR 범위입니다. CompositionSnapshot Idempotency는 Service 기반만 구현했으며 HTTP header 연결은 Router 후속 범위입니다. AssetVersion 목록은 단일 Asset의 완전한 계보를 최신 번호순으로 반환하므로 Cursor 계약을 사용하지 않습니다. Artifact API는 단건 Metadata·content·download만 제공하므로 Cursor 계약을 사용하지 않습니다.
