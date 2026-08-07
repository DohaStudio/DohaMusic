# HMAC Cursor Pagination 설계

> 문서 상태: [완료]
> 최종 수정일: 2026-08-07
> 관련 기능: Workspace v1 목록의 opaque cursor와 keyset 조회 기반
> 구현 상태: Workspace·Project Cursor와 실제 DB 0013 적용, ProjectAsset Cursor·Repository·Service page와 0014 source 검증 완료; ProjectAsset Router·실제 DB 0014 적용 미수행
> 관련 문서: [Workspace REST API 계약](workspace-rest-api-contract.md), [API 전환 전략](api-contract-migration-strategy.md), [Backend 아키텍처](../03-architecture/backend-architecture.md), [Workspace·Project Index](../07-database/workspace-keyset-indexes.md), [ProjectAsset Index](../07-database/project-asset-keyset-indexes.md)

## 1. 목적과 범위

Workspace v1 목록은 외부에 offset을 노출하지 않고 안정적인 keyset pagination을 사용합니다. Workspace·Project 조회는 Resource Router에 연결했고 ProjectAsset은 Router 구현 전 Cursor·Repository·Service page와 Index source만 준비했습니다. 인증·Idempotency·backfill은 포함하지 않습니다.

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
| `resource` | `workspace`, `project` 또는 `project_asset` |
| `direction` | `next` |
| `sort` | `created_at_desc` |
| `last_created_at` | Workspace·Project 직전 page 마지막 row의 UTC ISO 8601 시각 |
| `last_display_order` | ProjectAsset 직전 page 마지막 row의 정확한 정수 표시 순서 |
| `last_id` | 직전 page 마지막 row의 UUID |
| `filter_hash` | canonical filter JSON의 SHA-256 |
| `limit` | 1~100의 page 크기 |

Workspace·Project payload는 `last_created_at`, ProjectAsset payload는 `last_display_order`만 사용하며 두 position field를 한 token에 함께 넣지 않습니다. ProjectAsset은 `sort=display_order_asc`를 사용합니다. Resource별 정확한 field 집합을 검증하므로 version 1을 유지하면서 기존 token 의미와 서명을 바꾸지 않습니다. Payload에 owner·Workspace 이름·Project 제목·DB 경로·Table명·SQL·credential을 넣지 않습니다.

## 4. 검증과 오류

Decode는 2 KiB 최대 길이를 먼저 확인한 뒤 token 구조와 base64url, `compare_digest` 기반 서명, Resource별 정확한 payload field 집합, version, Resource, 방향, 정렬, UUID, position, filter fingerprint와 limit을 검증합니다. `v`·`limit`·ProjectAsset `last_display_order`는 Boolean·실수·문자열을 허용하지 않는 정확한 정수입니다. 실패 원인은 내부 `reason`으로만 구분하며 외부에는 `422 INVALID_CURSOR`와 고정 메시지만 제공합니다.

서명 키가 없거나 짧으면 `500 CURSOR_CONFIGURATION_ERROR`, 요청 limit이 범위를 벗어나면 `422 INVALID_LIMIT`입니다. 서명값과 payload 원문을 오류에 포함하지 않습니다.

## 5. Filter fingerprint

Workspace fingerprint는 `include_deleted=false`, 정렬과 내부 owner filter를 사용합니다. Project fingerprint는 `workspace_id`, ProjectAsset fingerprint는 `project_id`와 `include_deleted=false`·정렬을 사용합니다. JSON key 정렬과 공백 없는 canonical 직렬화 뒤 SHA-256을 계산하므로 다른 Workspace·Project·owner·정렬 조건에 cursor를 재사용할 수 없습니다.

## 6. Keyset 조회

Workspace·Project 정렬은 `(created_at DESC, UUID DESC)`입니다. 다음 page 조건은 아래와 같습니다.

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

Service는 `limit + 1`개를 조회해 `has_more`를 계산하고 응답 항목은 `limit`개로 자릅니다. 다음 row가 있으면 마지막 반환 row로 서명된 `next_cursor`를 만들고, 마지막 page와 빈 page에서는 `has_more=false`, `next_cursor=null`을 반환합니다.

페이지 사이에 row가 생성·삭제될 수 있으므로 이 계약은 전체 목록의 snapshot isolation을 보장하지 않습니다. 새로 생성된 상위 row를 과거 cursor가 다시 탐색하지 않고 Soft Delete된 후속 row는 제외하며, 이미 반환한 row를 재반환하지 않는 forward-only keyset 동작을 보장합니다.

Alembic `20260807_0013`은 전체 활성 Workspace용 `(deleted_at, created_at, workspace_id)`, owner별 활성 Workspace용 `(owner_id, deleted_at, created_at, workspace_id)`, Workspace별 활성 MusicProject용 `(workspace_id, deleted_at, created_at, project_id)` 복합 Index를 추가합니다. 임시 SQLite의 첫·다음 page 여섯 쿼리에서 신규 Index가 선택되고 정렬용 임시 B-Tree가 제거됐습니다. SQLite는 ASC Index를 역방향으로 탐색하므로 metadata와 migration에는 명시적 DESC를 사용하지 않습니다.

`deleted_at IS NULL` partial 후보는 owner별 Workspace와 Project에는 사용됐지만 기존 `ix_workspaces_deleted_at`가 owner 없는 목록에서 계속 선택되어 임시 정렬을 제거하지 못했습니다. 기존 Index를 제거하거나 Repository에 Index hint를 넣지 않고 현재 쿼리 의미를 유지하기 위해 비-partial 구성을 선택했습니다. 세부 후보와 계획은 [Workspace keyset Index 설계](../07-database/workspace-keyset-indexes.md)를 따릅니다. 신규 revision은 승인된 절차로 실제 사용자 DB에 적용했습니다.

ProjectAsset은 full `(project_id, deleted_at, display_order, project_asset_id)`와 partial `(project_id, display_order, project_asset_id) WHERE deleted_at IS NULL` 후보가 모두 첫·다음 page에서 임시 정렬을 제거했습니다. 활성 row만 포함하고 같은 계획 결과를 제공하는 partial 후보를 `20260807_0014` source revision으로 선택했습니다. 이 revision은 임시 SQLite에서만 검증했으며 실제 사용자 DB에는 적용하지 않았습니다. 세부 결과는 [ProjectAsset keyset Index 설계](../07-database/project-asset-keyset-indexes.md)를 따릅니다.

## 7. 후속 작업

1. `[완료]` Preflight·backup·rehearsal과 승인 후 실제 사용자 DB에 `20260807_0013`을 적용했습니다.
2. `[완료]` App composition에서 환경 설정으로 `CursorCodec`을 구성했습니다.
3. `[완료]` Workspace·Project Resource 목록 Route에 `limit`과 `cursor`를 연결했습니다.
4. `[완료]` Collection Envelope의 `has_more`와 `next_cursor` 불변 조건을 API 테스트로 검증했습니다.
5. `[완료]` ProjectAsset 전용 position·Project filter·Repository·Service page와 0014 source Index를 임시 SQLite에서 검증했습니다.
6. `[계획]` 별도 승인 후 실제 사용자 DB에 0014를 적용하고 ProjectAsset Resource Router 3개를 연결합니다.
7. 운영 전 서명 키 교체와 cursor 만료 정책을 확정합니다.

나머지 56개 Resource Endpoint, Idempotency replay, 인증·권한, Frontend, backfill·dual write는 별도 PR 범위입니다.
