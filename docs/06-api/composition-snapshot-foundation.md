# CompositionSnapshot 공개 계약과 Application 기반

> 문서 상태: [완료]
> 최종 수정일: 2026-08-10
> 관련 기능: CompositionSnapshot scope·불변 생성·Cursor·Idempotency 기반
> API 상태: 공식 Router와 Endpoint 3개는 [계획]
> 관련 문서: [Workspace REST API 계약](workspace-rest-api-contract.md), [Endpoint 목록](workspace-rest-api-endpoints.md), [Cursor Pagination](cursor-pagination.md), [Workspace Artifact 모델](../03-architecture/workspace-artifact-model.md), [Common Composition Snapshot 명세](https://github.com/DohaStudio/.github/blob/main/docs/specifications/08-composition-snapshot-specification.md)

## 1. 범위와 상태

이번 기반은 `CompositionRepository`와 `CompositionService`에 공개 API 구현 전 필요한 계약을 고정합니다. `GET /api/v1/snapshots`, `POST /api/v1/snapshots`, `GET /api/v1/snapshots/{composition_snapshot_id}` Router·Pydantic 공개 DTO·OpenAPI operation은 추가하지 않았습니다. 따라서 Resource API는 22/64, CompositionSnapshot API는 0/3입니다.

Snapshot은 특정 Project의 정확한 `AssetVersion` 조합, Processing Chain, Mix 설정과 Provider·Model 계보를 고정하는 불변 aggregate입니다. 기존 Snapshot이나 SnapshotItem을 수정·삭제·재정렬하는 Repository·Service 경로는 제공하지 않습니다.

## 2. Project·Owner·Asset scope

- effective Owner는 신뢰된 호출 context에서 전달하며 공개 body의 `owner_id`·`created_by`를 받지 않습니다.
- Workspace가 없으면 `WORKSPACE_BOOTSTRAP_REQUIRED`, 다른 Owner 또는 비활성 Project는 존재를 숨기는 `PROJECT_NOT_FOUND` 계열로 거부합니다.
- `created_by`는 effective Owner에서 파생합니다.
- SnapshotItem의 Asset은 같은 effective Owner 소유이며 활성 상태여야 합니다.
- `Asset.workspace_id`는 대상 Project의 Workspace와 같거나 `NULL`인 재사용 Asset만 허용합니다. 같은 Owner라도 다른 Workspace Asset은 거부합니다.
- Workspace 미지정 재사용 Asset도 Snapshot에 넣기 전에 대상 Project의 활성 `ProjectAsset` 관계가 필요합니다.
- 생성 후 ProjectAsset 관계가 분리돼도 기존 Snapshot과 정확한 Version 계보는 보존합니다.
- `processing_chain_id`를 지정하면 존재 여부와 `created_by == effective_owner_id`를 확인합니다.

## 3. SnapshotItem 계약

공개 `item_role` allowlist는 다음 다섯 값입니다.

```text
lyrics
music
vocal
stem
mix
```

Common Specification에서 Instrumental은 Music AssetVersion이므로 별도 `instrumental` role을 만들지 않습니다. `reference`, `mix_source`와 임의 문자열도 허용하지 않습니다. `sort_order`는 Boolean·실수·문자열이 아닌 0 이상의 정확한 정수입니다. 요청 하나에서 `(item_role, sort_order)`와 `(asset_version_id, item_role)` 중복을 사전 거부하고 기존 DB Unique Constraint를 최종 방어선으로 유지합니다.

호출자는 정확한 `asset_version_id`를 지정해야 합니다. Asset ID만 받아 최신 Version을 자동 선택하거나 생성 도중 Version을 교체하지 않습니다. SnapshotItem은 Artifact ID를 고정하지 않으며 실제 실행 Payload 선택은 `JobInput.artifact_id`가 담당합니다.

## 4. 자동 Version과 원자성

공개 요청은 `snapshot_version`을 받지 않습니다. Service가 Project별 `max(snapshot_version) + 1`을 계산하며 첫 Snapshot은 1입니다. `(project_id, snapshot_version)` Unique Constraint 충돌은 transaction 전체를 되돌리고 최대 3회만 다시 시도합니다. 계속 충돌하면 `COMPOSITION_SNAPSHOT_CONFLICT` 계열로 종료하며 무한 재시도하지 않습니다.

Snapshot, 모든 SnapshotItem과 Idempotency 완료 기록은 하나의 Service 소유 transaction에서 생성합니다. Item 하나라도 실패하면 부분 Snapshot과 부분 Idempotency 성공 기록을 남기지 않습니다. Repository는 `commit()`과 `rollback()`을 호출하지 않습니다.

상세 조회용 내부 aggregate는 Snapshot과 전체 Item을 함께 반환하며 Item은 `(item_role ASC, sort_order ASC, snapshot_item_id ASC)`로 결정적으로 정렬합니다.

## 5. Cursor와 keyset 조회

Project별 목록 공식 정렬은 `(snapshot_version DESC, composition_snapshot_id DESC)`입니다. version은 Project 안에서 unique지만 안정적인 공통 계약을 위해 UUID tie-breaker를 유지합니다.

version 1 Cursor payload는 다음 필드만 포함합니다.

```json
{
  "v": 1,
  "resource": "composition_snapshot",
  "direction": "next",
  "sort": "snapshot_version_desc",
  "last_snapshot_version": 7,
  "last_id": "opaque-uuid",
  "filter_hash": "sha256-hex",
  "limit": 50
}
```

fingerprint는 `project_id`, effective Owner, 비삭제 활성 Project 조건과 정렬 계약을 포함합니다. 다른 Owner·Project·limit·filter에 token을 재사용하거나 변조하면 `INVALID_CURSOR`입니다. Repository는 다음 조건과 `limit + 1`을 사용합니다.

```text
snapshot_version < last_snapshot_version
OR (
  snapshot_version = last_snapshot_version
  AND composition_snapshot_id < last_id
)
```

기존 `(project_id, snapshot_version)` Unique Index로 6,000개 임시 SQLite fixture의 첫 page·다음 page에 TEMP B-TREE와 전체 Table scan이 발생하지 않았습니다. 신규 Index나 Alembic revision은 필요하지 않습니다.

## 6. JSON과 재현 계보

- `provider_versions`: 최대 16개의 `provider_id -> contract/runtime version` 문자열 매핑
- `model_manifest_ids`: 최대 16개의 `provider_id -> opaque manifest ID` 문자열 매핑
- `mix_settings_snapshot`: JSON object, 최대 깊이 4, 전체 node 64, key 64자, 문자열 1,024자

NaN·Infinity, 임의 객체와 과도한 중첩·항목 수는 거부합니다. Provider 또는 Model Manifest가 기록된 참조 AssetVersion은 해당 mapping에 반드시 포함돼야 합니다. 사용자 생성 Version처럼 Provider·Model 계보가 없는 구성은 빈 mapping을 허용하되 향후 승인·상업 이용 Gate는 별도 정책으로 유지합니다.

이 기반만으로 Project, version, 정확한 AssetVersion·role·order, Processing Chain 참조, Mix 설정, Provider·Manifest와 생성 시각을 고정할 수 있습니다. 물리 Payload·checksum 검증은 Artifact와 Job 경계가 담당합니다.

## 7. Idempotency

기존 `idempotency_records` Table을 재사용하며 schema 변경은 없습니다. scope는 effective Owner와 Project를 포함하고 fingerprint는 scope와 정규화된 생성 body 전체를 포함합니다.

- 같은 key·같은 요청: 최초 Snapshot aggregate와 status를 재생하며 row를 추가하지 않습니다.
- 같은 key·다른 요청: `IDEMPOTENCY_KEY_REUSED` 계열 conflict로 거부합니다.
- 다른 Owner 또는 Project: 별도 scope입니다.
- 보존 시간: 현재 기반은 24시간입니다.

Claim, Snapshot·Item 생성과 완료 기록은 같은 transaction입니다. Router가 추가될 때 기존 공통 오류 envelope에 매핑하며 raw key, fingerprint와 payload를 외부 오류·로그에 노출하지 않습니다.

## 8. 후속 구현 경계

다음 작업은 별도 PR입니다.

- 공식 CompositionSnapshot Router·Request/Response DTO와 Endpoint 3개
- App Factory의 CompositionService 주입과 HTTP `Idempotency-Key` 연결
- Job 생성·실행과 Artifact 선택
- Frontend, backfill, dual write와 Runtime source of truth 전환

이번 기반은 Alembic·Entity·Index·실제 사용자 DB·실제 `DohaArtifacts`를 변경하지 않습니다.
