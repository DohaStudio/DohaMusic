# Workspace additive Alembic Migration 검증 보고서

> 문서 상태: [완료]
> 최종 수정일: 2026-08-06
> 관련 기능: Workspace 목표 Entity 21개 additive schema
> 구현 상태: Migration 파일과 임시 SQLite 검증 완료, 실제 사용자 DB 적용 미수행
> 관련 문서: [Migration 전략](../../docs/07-database/database-redesign-migration-strategy.md), [목표 Table Definition](../../docs/07-database/database-redesign-table-definition.md), [ADR-030](../../docs/11-decisions/ADR-030-asset-version-centric-database.md)

## 1. 검증 기준

| 항목 | 값 |
|---|---|
| 기준 `develop` | `689c700a956bdac104203e65447b45e575c4ec2a` |
| 기존 head | `20260801_0011` |
| 신규 revision | `20260806_0012` |
| revision 파일 | `backend/alembic/versions/20260806_0012_add_workspace_entity_tables.py` |
| 기존 Runtime Table | 14개 |
| 신규 Workspace Table | 21개 |
| 전체 application Table | 35개 |

실제 사용자 DB와 운영 DB에는 연결하지 않았다. 생성과 검증에는 별도 빈 임시 SQLite DB만 사용했다.

## 2. 신규 Table

1. `workspaces`
2. `music_projects`
3. `project_assets`
4. `assets`
5. `asset_versions`
6. `artifacts`
7. `asset_relations`
8. `composition_snapshots`
9. `snapshot_items`
10. `jobs`
11. `job_inputs`
12. `job_outputs`
13. `processing_chains`
14. `processing_steps`
15. `model_usages`
16. `recording_enrollments`
17. `tags`
18. `comments`
19. `favorites`
20. `history`
21. `approvals`

SQLAlchemy metadata의 Workspace Table 집합과 migration의 `create_table`·`drop_table` 집합은 정확히 일치한다. 누락과 초과는 0개다.

## 3. Upgrade와 Downgrade 계약

### Upgrade

- 신규 Table 생성: 21개
- 신규 Index 생성: 109개
- FK Constraint: 39개
- Check Constraint: 8개
- Unique Constraint: 17개
- 기존 Runtime Table alter: 0개
- 기존 Column·Index·Constraint 변경: 0개
- application data `INSERT`·`UPDATE`·`DELETE`: 0개
- backfill과 dual write: 0개

### Downgrade

- 신규 Index 제거: 109개
- 신규 Table 제거: 21개
- 제거 순서: 생성 순서의 역순
- 기존 Runtime Table 제거·변경: 0개

Downgrade는 신규 Workspace schema의 데이터를 제거할 수 있으므로 실제 사용자 DB에서는 자동 실행하지 않는다. 이번 검증은 새 임시 DB에서만 수행했다.

## 4. Index와 Constraint

| 검증 | 결과 |
|---|---|
| Index 이름 | 109개, 중복 0개 |
| 이름이 있는 Constraint | 23개, 중복 0개 |
| ProjectAsset 중복 방지 | `uq_project_assets_project_asset` |
| AssetVersion 번호 | `uq_asset_versions_number` |
| SnapshotItem 역할·순서 | `uq_snapshot_items_role_order` |
| SnapshotItem Version·역할 | `uq_snapshot_items_version_role` |
| JobInput 순서 | `uq_job_inputs_order` |
| JobOutput 순서 | `uq_job_outputs_order` |
| Tag 이름 범위 | `uq_tags_asset_name` |
| Favorite 중복 방지 | `uq_favorites_workspace_asset` |
| RecordingEnrollment 식별 | `uq_recording_enrollments_consent` |

문서와 Entity에 없는 Constraint는 migration에 추가하지 않았다.

## 5. SQLite 타입 정책

- UUID는 SQLAlchemy `Uuid(as_uuid=True)`와 Python-side UUID4 생성 함수를 사용한다. server-side UUID 생성은 없다.
- JSON은 SQLAlchemy `JSON`을 사용한다.
- Boolean과 timezone 지정 DateTime은 SQLAlchemy SQLite dialect 변환을 따른다.
- `AssetType`과 `JobStatus`는 `native_enum=False` 문자열로 저장한다.
- Entity의 `values_callable`은 Enum value를 저장하고 `validate_strings=True`로 application 입력을 검증한다.
- Entity가 DB-level Enum Check Constraint를 선언하지 않으므로 migration에도 임의로 추가하지 않았다.
- UUIDv7 전환은 생성 함수 교체와 데이터 호환성 검토가 필요한 별도 작업이다.

Python 3.12 SQLite datetime adapter 폐기 예정 경고는 이번 additive migration에서 해결하지 않는다.

## 6. FK와 삭제 정책

- FK 대상은 신규·기존 metadata에 모두 존재한다.
- 신규 Workspace Table에 선언된 FK 39개를 SQLite inspector로 확인했다.
- 빈 임시 DB의 `PRAGMA foreign_key_check` 결과는 위반 0건이다.
- FK의 `ondelete`는 Entity의 `RESTRICT` 계약과 일치한다.
- delete cascade와 delete-orphan은 추가하지 않았다.
- AssetVersion과 CompositionSnapshot을 orphan으로 자동 삭제하지 않는다.
- `assets.selected_asset_version_id`와 `asset_versions.asset_id`는 순환 참조다. SQLite 임시 DB에서 생성과 제거를 검증했으며 다른 DB 제품 도입 시 Constraint 생성 단계를 재검토한다.

현재 Alembic SQLite 연결 설정은 `PRAGMA foreign_keys=ON`을 명시하지 않는다. 따라서 이번 테스트는 FK 선언, 대상 존재, 빈 DB의 참조 무결성과 schema 왕복을 검증하지만 Runtime의 FK 강제 실행까지 보장하지 않는다. 실제 사용자 DB에 적용하기 전 별도 Gate에서 연결별 FK 활성화와 위반 데이터 사전 검사를 반드시 검증한다.

## 7. 정적 검증

| 항목 | 결과 |
|---|---|
| revision ID 중복 | 0개 |
| `down_revision` | `20260801_0011` |
| Alembic head | `20260806_0012` 단일 head |
| Python compile | PASS |
| Ruff lint·format | PASS |
| `git diff --check` | PASS |
| 금지 Alembic operation | 0개 |
| metadata·migration Table 차이 | 누락 0개, 초과 0개 |

전용 테스트 `backend/tests/test_workspace_alembic_migration.py`가 operation 집합, 이름 중복과 임시 SQLite round-trip을 검증한다.

## 8. Offline SQL

전체 `base → 20260806_0012` offline SQL은 기존 `20260729_0006`의 SQLite batch reflection 요구 때문에 생성할 수 없다. 이는 기존 chain의 알려진 제약이며 신규 revision의 실패가 아니다.

신규 구간 `20260801_0011:20260806_0012`는 offline SQL 생성에 성공했다.

- `CREATE TABLE`: 21개
- application Table `ALTER`: 0개
- application data 변경 SQL: 0개
- Alembic 자체 `alembic_version` 갱신: 1개

## 9. 임시 SQLite 검증

1. 빈 임시 DB에 기존 revision 11개를 적용해 Runtime Table 14개를 구성했다.
2. 신규 revision을 적용했다.
3. application Table 35개와 Workspace Table 21개를 확인했다.
4. 신규 revision만 downgrade했다.
5. 기존 head `20260801_0011`과 Runtime Table 14개가 유지됨을 확인했다.

실제 사용자 DB, 운영 DB와 기존 프로젝트 DB 파일은 사용하지 않았다.

## 10. 미구현과 후속 Gate

- 실제 사용자 DB upgrade와 downgrade
- 운영 backup·restore rehearsal
- 기존 row inventory와 backfill
- dual write와 shadow read
- Repository·Service·REST API
- Runtime source of truth 전환
- Legacy Table 동결·제거
- DB-level Enum Check Constraint 도입 여부
- SQLite 외 DB 제품의 순환 FK 생성 전략
- 실제 SQLite 연결의 `PRAGMA foreign_keys=ON` 적용과 기존 데이터 `foreign_key_check`
- autogenerate가 감지한 기존 `pipeline_jobs.input_snapshot` nullable drift의 별도 정리

## 11. 후속 상태

[SQLite Migration 안전 제어 검증](VALIDATION-SQLITE-MIGRATION-SAFETY.md)에서 Runtime·Alembic online SQLite 연결의 `PRAGMA foreign_keys=ON`과 `foreign_key_check` 회귀를 임시 DB로 후속 검증했습니다. 이 보고서의 당시 미구현 목록은 이력으로 유지하며, 실제 사용자 DB Inventory·backup·Migration과 기존 row 검증은 계속 미수행입니다.
