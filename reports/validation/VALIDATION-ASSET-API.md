# Asset Resource API 검증

> 문서 상태: [완료]
> 검증일: 2026-08-08
> 관련 기능: Asset Resource REST API 5개
> 관련 문서: [Workspace REST API 계약](../../docs/06-api/workspace-rest-api-contract.md), [Endpoint 목록](../../docs/06-api/workspace-rest-api-endpoints.md), [Asset keyset Index](../../docs/07-database/asset-keyset-indexes.md)

## 1. 검증 범위

다음 Endpoint와 기존 기반의 결합을 검증했다.

- `GET /api/v1/assets`
- `POST /api/v1/assets`
- `GET /api/v1/assets/{asset_id}`
- `PATCH /api/v1/assets/{asset_id}`
- `DELETE /api/v1/assets/{asset_id}`

이번 구현은 기존 Asset version 1 HMAC Cursor, keyset Repository·Service와 실제 사용자 DB에 적용된 Alembic `20260808_0015` Index를 재사용한다. AssetVersion·Artifact·Composition·Job API, 실제 Bootstrap, backfill, dual write, Frontend와 Runtime source 전환은 포함하지 않는다.

## 2. 계약 결과

| 항목 | 결과 |
|---|---|
| 목록 scope | Bootstrap Workspace에서 파생한 effective Owner로 고정 |
| 공개 filter | 선택적 `workspace_id`, `asset_type`만 허용 |
| 정렬 | `created_at DESC, asset_id DESC` |
| Pagination | `limit + 1`, `has_more`, HMAC `next_cursor` |
| 생성 | Asset만 생성하고 Version·Artifact·ProjectAsset 생성 없음 |
| 상세 | Soft Delete 또는 다른 Owner Asset은 `ASSET_NOT_FOUND` |
| PATCH | `lifecycle_status`만 허용 |
| DELETE | Asset Soft Delete, Version·Artifact·ProjectAsset 보존 |
| 내부 필드 | `owner_id`, `created_by`, 내부 ID·시각·삭제·Selection 입력 거부 |
| Transaction | Service 소유, Repository 직접 `commit`·`rollback` 없음 |
| Bootstrap | Workspace가 없으면 `409 WORKSPACE_BOOTSTRAP_REQUIRED` |

## 3. 테스트 결과

### 3.1 Asset API와 Route 계약

```text
21 passed
```

Asset CRUD, Cursor filter 결합, limit 오류, Soft Delete, 내부 필드 `extra=forbid`, UUID, request ID, Owner scope, Conflict mapping, 생성·삭제 transaction rollback과 Route·OpenAPI 수를 검증했다.

### 3.2 선별 회귀

```text
16 passed
```

Workspace·Project·ProjectAsset API, Asset Cursor, Service transaction, Repository transaction 금지와 Alembic 임시 DB round-trip을 검증했다.

### 3.3 기존 Runtime 대표 회귀

```text
4 passed
```

Health·Storage 초기화, Mock Generation, 기존 Project 안전 삭제와 Pipeline 성공 흐름을 검증했다. 실제 Provider·GPU·모델·외부 API는 실행하지 않았다.

## 4. Route와 진행률

| 항목 | 변경 전 | 변경 후 |
|---|---:|---:|
| 등록 Route | 56 | 61 |
| `APIRoute` | 52 | 57 |
| OpenAPI Operation | 54 | 59 |
| Workspace v1 Resource API | 11/64 | 16/64 |

기존 Pipeline file GET·HEAD의 OpenAPI operation ID 중복 2건은 기존 WARNING이며 이번 범위에서 변경하지 않았다.

## 5. 데이터베이스와 운영 경계

- Alembic source head와 실제 사용자 DB revision은 `20260808_0015`다.
- 이번 검증은 테스트별 임시 SQLite DB만 사용했고 실제 사용자 DB에는 접근하지 않았다.
- Runtime Table 14개가 계속 source of truth다.
- 실제 Bootstrap, backfill, dual write와 Runtime 전환은 수행하지 않았다.

## 6. 판정

**PASS** — Asset Resource API 5개가 기존 Cursor·Service transaction·Index 계약을 유지하며 구현됐고 Resource API 진행도는 16/64다. 남은 범위는 AssetVersion 이하 48개 Endpoint와 운영 전환 작업이다.
