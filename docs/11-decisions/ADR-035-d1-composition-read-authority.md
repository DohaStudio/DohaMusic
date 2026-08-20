# ADR-035 — D1 Composition Read 권위와 Projection 계약

> 상태: 승인
> 작성일: 2026-08-20
> 최종 수정일: 2026-08-20
> 관련 기능: AI-native DAW D1 Composition Read Workspace
> 관련 문서: [Composition Read API 계약](../06-api/composition-read-workspace.md), [CompositionSnapshot 기반](../06-api/composition-snapshot-foundation.md), [Frontend 전환 계획](../../planning/ai-native-daw-frontend-migration.md), [Database 전환 전략](../07-database/database-redesign-migration-strategy.md)

## 배경

현재 Workspace·MusicProject·ProjectAsset·Asset·AssetVersion·Artifact·CompositionSnapshot Entity와 Repository·Service, `/api/v1` Resource API가 구현되어 있다. CompositionSnapshot은 exact AssetVersion 조합과 Mix·Provider·Model 계보를 불변으로 고정하고 목록·생성·상세 API를 제공한다.

반면 현재 Frontend는 Legacy `projects`, `history`, `pipelines` API를 사용한다. 실제 사용자 DB에는 Workspace 계열 row가 없고 Legacy Project만 존재한다. CompositionSnapshot에는 selected/current 의미, Track·Section Domain과 Frontend용 aggregate projection이 없다.

## 문제

- Snapshot 목록의 첫 항목을 암묵적으로 current로 취급하면 사용자가 과거 Version을 선택한 상태를 보존할 수 없다.
- `SnapshotItem.item_role + sort_order`는 Snapshot 안의 배치 정보일 뿐 미래 DAW Track의 canonical identity가 아니다.
- Section으로 승인할 수 있는 시간 범위·구조 metadata가 현재 Domain에 없다.
- 기존 Resource API만 조합하면 Frontend가 Snapshot → AssetVersion → Artifact를 과도하게 fan-out해야 한다.
- Workspace 데이터가 없을 때 Legacy를 조용히 읽거나 GET에서 backfill하면 읽기 권위와 부작용 경계가 무너진다.

## 결정

### 1. 읽기 권위

D1 Composition read의 최종 authority는 Workspace v1이다. Legacy Runtime은 전환 입력과 동등성 검증 source로만 유지하고 D1 aggregate의 fallback authority로 사용하지 않는다.

- GET은 Legacy row를 Workspace row처럼 합성하지 않는다.
- GET은 Workspace bootstrap, backfill, dual write 또는 selection 변경을 실행하지 않는다.
- 실제 사용자 데이터 전환 전까지 현재 Legacy Frontend를 유지한다.

### 2. selected/current Snapshot

Project 수준의 명시적 CompositionSnapshot selection을 canonical current로 결정한다.

- `selected_snapshot_id`는 같은 Project에 속한 불변 CompositionSnapshot을 가리키는 nullable Project-level 상태다.
- current Snapshot은 명시적으로 선택된 Snapshot과 동일하다. 최신 version은 history 정렬 기준일 뿐 current가 아니다.
- Snapshot 생성은 기존 계약처럼 새 불변 Snapshot만 만들며 선택을 암묵적으로 바꾸지 않는다.
- 선택 변경은 향후 별도 mutation과 transaction으로 구현한다. D1 read GET은 선택을 변경하지 않는다.
- 물리 저장을 Project column 또는 1:1 selection record 중 무엇으로 구현할지는 public API가 아니지만, 같은 Owner·Workspace·Project 불변식을 DB와 Service에서 강제해야 한다.

Aggregate GET은 선택적 `composition_snapshot_id` query로 특정 history Snapshot을 읽을 수 있다. 이 값은 조회 대상만 바꾸며 selected/current 상태를 변경하지 않는다. query가 없으면 explicit selection만 해석하고, selection이 없을 때 latest로 대체하지 않는다.

### 3. Track read projection

D1은 full Track Domain 대신 Snapshot-local Track read projection을 제공한다.

- `projection_id`는 기존 `snapshot_item_id`를 재사용한다.
- identity scope는 `snapshot`이며 다른 Snapshot에서 동일 Track임을 보장하지 않는다.
- `track_id`라는 이름으로 노출하거나 edit command, MusicIntent target 또는 DB FK로 사용하지 않는다.
- `music`, `vocal`, `stem`, `mix` Item만 Track projection 후보이며 `lyrics` Item은 Composition item으로만 남긴다.
- projection은 role, order, Asset·exact AssetVersion과 안전한 Artifact reference를 함께 제공한다.

미래 canonical Track Domain은 D2/D3 구현 전 별도 ADR로 결정한다. D1 projection ID를 canonical Track ID로 migration한다고 가정하지 않는다.

### 4. Section read policy

현재 권위 있는 Section identity·time range·구조 metadata가 없으므로 D1은 Section을 합성하지 않는다.

- `section_projection.availability = "not_available"`
- `section_projection.items = []`
- 임의의 Verse/Chorus 이름, 균등 분할 또는 Provider의 미검증 자유형 JSON을 Section으로 승격하지 않는다.

향후 검증된 analysis 또는 composition metadata 계약이 생기면 versioned API 변경으로 optional Section projection을 추가한다. full Section editing Domain은 D2/D3 범위다.

### 5. Aggregate endpoint

Frontend용 읽기 최적화 endpoint를 다음으로 결정한다.

```text
GET /api/v1/projects/{project_id}/composition
```

Composition은 Project에 종속된 aggregate이므로 Project namespace를 사용한다. `project_id`와 effective Owner가 Workspace scope를 결정하므로 Workspace ID를 path에 중복하지 않는다. Snapshot history pagination은 기존 `GET /api/v1/snapshots?project_id=...`가 계속 담당한다.

응답은 Project, selection resolution, Snapshot, resolved AssetVersion과 safe Artifact reference, Track projection, Section availability, Mix JSON과 lineage ID를 한 번에 제공한다. 기존 Snapshot endpoint를 대체하거나 독립 Resource 수를 변경하지 않는다.

### 6. Empty와 transition 상태

기존 오류와 성공 envelope를 재사용한다.

- Workspace가 없으면 기존 `409 WORKSPACE_BOOTSTRAP_REQUIRED`다. 이것은 시스템 장애가 아니라 명시적 bootstrap 선행 상태다.
- Owner 범위의 활성 Project가 없으면 기존 `404 PROJECT_NOT_FOUND`다. Legacy Project 존재 여부를 probing하지 않는다.
- Project는 있으나 Snapshot이 없으면 `200`, `state="empty"`, `snapshot=null`이다.
- Snapshot history는 있으나 selection이 없고 query도 없으면 `200`, `state="selection_required"`, `snapshot=null`이다.
- selected 또는 요청 Snapshot을 해석하면 `200`, `state="ready"`다.
- dangling 또는 cross-Project selection은 안전한 `409` integrity conflict로 실패하고 latest로 대체하지 않는다. 외부 code 이름은 D1-A 오류 계약 구현에서 기존 공통 error namespace와 함께 확정한다.

### 7. Authorization과 Artifact 안전

현재는 bootstrap된 단일 사용자 Workspace에서 effective Owner를 파생한다. D1 aggregate는 기존 Composition Service의 active Workspace·Project·Owner privacy를 재사용하고 다른 Owner의 존재를 `404`로 숨긴다. `owner_id`, `created_by` override를 body·query·header로 받지 않는다.

실제 인증 사용자와 Owner mapping은 TARGET이며 Frontend 공개 전 Gate다. Artifact는 기존 공개 `ArtifactDetail`의 안전한 metadata와 ID 기반 content/download link만 재사용한다. absolute path, storage key, Catalog locator, credential-bearing URL은 반환하지 않는다.

### 8. Common Contract와 후속 기능

Composition aggregate, Track projection과 Section availability는 DohaMusic product API 계약이다. Common AI Contract schema를 추가하거나 변경하지 않는다. MusicIntent, RevisionPlan, SimilarityReport, ReferenceAnalysis, LearningCandidate와 EvaluationRun은 identity 참고만 하며 D1에서 실행하지 않는다.

Clip, Timeline editing, waveform editing, typed Mixer/automation, AI segment editing, Composition Evaluation과 Continuous Learning은 D1 범위가 아니다.

## 선택 이유

명시적 Project selection은 불변 Snapshot을 유지하면서 사용자의 선택을 보존하고 history 정렬과 current 의미를 분리한다. SnapshotItem 기반 projection은 현재 데이터를 정직하게 재사용하면서 미래 Track Domain을 조기에 고정하지 않는다. Project aggregate endpoint는 기존 Resource API를 유지하면서 Frontend fan-out과 권한 누락 위험을 줄인다.

## 대안

1. **최신 Snapshot을 current로 사용**: 구현은 단순하지만 사용자의 과거 선택과 future undo/version UX를 보존하지 못해 제외한다.
2. **SnapshotItem role/order를 canonical Track ID로 사용**: Snapshot 간 identity와 편집 수명을 보장하지 못해 제외한다.
3. **D1에서 Track·Section·Clip Table을 먼저 추가**: 검증된 편집 Domain 없이 schema를 고정하므로 제외한다.
4. **Frontend가 기존 Resource API를 직접 fan-out**: 요청 수, partial failure와 scope 검증 중복이 커 제외한다.
5. **Legacy silent fallback**: 데이터 authority를 숨기고 GET 부작용을 유도하므로 금지한다.

## 영향

D1-A는 Backend·SQLAlchemy·Alembic source와 공개 aggregate API를 구현했다. Frontend·실제 사용자 DB·실제 Workspace 데이터·Provider·Common Contract는 변경하지 않는다. selection persistence와 aggregate projection은 완료됐고 실제 전환과 Frontend 연결은 후속 작업이다.

## D1-A 구현 기록

D1-A는 Project column 대신 별도 `ProjectCompositionSelection` 1:1 Table을 선택했다. Project와 Snapshot 사이의 순환 FK·ORM 관계를 만들지 않고, row 부재로 nullable 초기 상태를 표현하며, `(project_id, selected_composition_snapshot_id)` 복합 FK로 same-Project 불변식을 DB에서 직접 강제할 수 있기 때문이다. Service 검증을 함께 적용하고 Snapshot은 계속 불변으로 유지한다.

additive revision은 `20260820_0018`이며 기존 row backfill은 없다. 선택 mutation은 `PATCH /api/v1/projects/{project_id}/composition-selection`, aggregate read는 `GET /api/v1/projects/{project_id}/composition`으로 구현했다. GET은 selection·bootstrap·backfill을 쓰지 않고 Legacy를 조회하지 않는다. 이 구현 기록은 실제 사용자 DB 적용이나 Frontend read 전환을 승인하지 않는다.

## 마이그레이션

1. `[완료]` D1-A에서 aggregate read DTO·Service·Repository·Router와 selection persistence를 구현하고 empty/selection/requested Snapshot을 fixture로 검증했다.
2. D1-Transition에서 명시적 Workspace bootstrap과 Legacy Project → MusicProject → relevant Asset/AssetVersion → CompositionSnapshot 후보를 검증·backfill한다.
3. 재현 가능한 Snapshot만 생성하고 Project selection은 사용자 또는 승인된 migration 규칙으로 명시적으로 설정한다.
4. D1-B에서 Frontend를 Workspace aggregate에 연결하고 실제 Snapshot E2E와 인증 Gate를 통과한다.
5. Legacy 제거·dual write·전체 Runtime read switch는 별도 Database Transition 승인 후 수행한다.

## 재검토 조건

- canonical Track·Section·Clip Domain을 도입할 때
- Snapshot selection을 공동 편집·branch·undo/redo 모델로 확장할 때
- 실제 인증·다중 Workspace 권한 모델을 도입할 때
- Artifact reference 또는 content delivery 계약이 변경될 때
- Legacy migration에서 재현 가능한 Snapshot을 만들 수 없는 데이터가 확인될 때

## 관련 PR

- 이 ADR을 제안한 PR: #98
- D1-A 구현 PR: 이 Draft PR 병합 후 기록
