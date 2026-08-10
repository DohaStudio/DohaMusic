# CompositionSnapshot Resource API 검증

> 상태: [완료]
> 검증일: 2026-08-10
> 기준 브랜치: `feature/composition-snapshot-api`
> 기준 develop: `d9142489fc9d8c0b872c82740bcabdbf95cac071`
> 관련 문서: [CompositionSnapshot 계약](../../docs/06-api/composition-snapshot-foundation.md), [Endpoint 목록](../../docs/06-api/workspace-rest-api-endpoints.md)

## 검증 범위

- `GET /api/v1/snapshots` Project별 summary·HMAC Cursor 목록
- `POST /api/v1/snapshots` 불변 aggregate·필수 `Idempotency-Key` 생성
- `GET /api/v1/snapshots/{composition_snapshot_id}` Owner-scoped 상세
- Bootstrap·effective Owner·ProjectAsset·cross-workspace·global Asset scope
- exact AssetVersion, role·sort order, 자동 version·retry·transaction
- Idempotency replay·conflict·Project scope와 UTC 응답 일관성
- bounded Mix·Provider·Model Manifest 계보와 ProcessingChain scope
- 불변 Route, OpenAPI 지표와 기존 Resource API 회귀

## 결과

| 항목 | 결과 |
|---|---|
| CompositionSnapshot API 전용 | 27 passed |
| Foundation·Cursor·Repository 직접 회귀 | 73 passed |
| 기존 Resource API 회귀 | 102 passed + API surface 1 passed |
| Entity·Migration·Catalog | 18 passed |
| Python compile | PASS |
| Ruff lint·format | PASS |
| `git diff --check` | PASS |

기존 Resource API 회귀 묶음에서는 기존 surface 기대값 때문에 1개가 실패했고 나머지 102개가 통과했습니다. 의도된 신규 Endpoint 3개를 반영해 Route 70, `APIRoute` 66, OpenAPI Path 49, Operation 68과 Workspace v1 operation 25개로 기대값을 갱신한 뒤 해당 테스트가 통과했습니다. 기능 회귀 실패는 없습니다.

## 공개 계약

- 목록은 `project_id`를 필수로 받고 `(snapshot_version DESC, composition_snapshot_id DESC)` 순서와 기존 `composition_snapshot` Cursor를 사용합니다.
- 생성 body는 Item의 `asset_version_id`, `item_role`, `sort_order`와 선택적 Processing Chain·bounded lineage만 받습니다. `snapshot_version`, `created_by`, Owner와 내부 ID는 `extra="forbid"`로 거부합니다.
- 같은 `Idempotency-Key`와 같은 body는 row·version을 늘리지 않고 최초 `201` aggregate를 재생합니다. 다른 body는 `IDEMPOTENCY_KEY_REUSED`입니다.
- 상세 Item은 `(item_role ASC, sort_order ASC, snapshot_item_id ASC)`로 반환하며 Artifact를 직접 선택하지 않습니다.
- Snapshot PATCH·DELETE와 독립 SnapshotItem Route는 없습니다.

## Query Plan과 Schema

6,000개 임시 SQLite Snapshot fixture에서 첫·다음 page 모두 기존 `(project_id, snapshot_version)` Unique Index를 사용했습니다. TEMP B-TREE, full scan, 중복과 누락은 0건입니다. 신규 Index·Entity·Alembic revision은 추가하지 않았습니다.

- Metadata: 36 Tables
- Alembic head: `20260809_0016`
- 실제 사용자 DB 접근: 0건
- 실제 `DohaArtifacts` 접근: 0건

## WARNING

- 기존 Pipeline file GET·HEAD Route의 OpenAPI operation ID 중복 2종은 이번 범위에서 변경하지 않았습니다.
- 실제 사용자 DB의 Workspace row와 Catalog row는 0개이고 실제 Bootstrap은 실행하지 않았습니다.
- Bootstrap CLI가 현재 `20260807_0013` revision만 허용하는 기존 제약은 `0016` 운영 기준과 별도 후속 정합성 검토가 필요합니다.
- CI와 같은 전체 Backend suite를 로컬 Windows에서 재실행했으나 15분 제한으로 최종 요약을 회수하지 못했습니다. 선별 Gate만 로컬 PASS로 기록하고 전체 suite 결과는 GitHub Actions에서 판정합니다.
- `backend-ubuntu` 재검증 과정에서 Snapshot 불변성 테스트의 FastAPI 내부 Route 객체 탐색이 전체 suite 실행 순서에서 빈 집합을 반환했습니다. 공개 계약 기준인 OpenAPI path·method 집합을 검사하도록 테스트만 수정했으며 제품 Endpoint 호출 검증은 계속 PASS했습니다.

## 판정

CompositionSnapshot 공식 Resource API 3개는 기존 Foundation을 우회하지 않고 연결됐습니다. Resource API는 25/64, CompositionSnapshot API는 3/3이며 다음 구현 범위는 Job Foundation과 Job API입니다.
