# Asset 중심 데이터베이스 Migration 전략

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-08
> 관련 기능: 현행 DohaMusic DB에서 Asset 중심 목표 DB로 단계적 전환
> 구현 상태: 목표 Entity·0012~0015 실제 적용, Workspace Repository·Service·Resource API 16개 완료; Bootstrap·backfill·dual write·파일 이동 미수행
> 관련 문서: [재설계 개요](database-redesign-overview.md), [목표 ERD](database-redesign-erd.md), [목표 Table Definition](database-redesign-table-definition.md), [현재 ERD](erd.md), [Migration 검증 보고서](../../reports/validation/VALIDATION-WORKSPACE-ALEMBIC-MIGRATION.md), [실제 적용 Runbook](../10-operations/workspace-db-migration-runbook.md)

## 1. 현재 기준

Alembic source head와 실제 사용자 DB revision은 Asset full keyset Index 두 개를 추가한 `20260808_0015`입니다. `20260806_0012`는 목표 Workspace Table 21개를 additive로 추가했고 `20260807_0013`은 Workspace·Project keyset Index 세 개, `20260807_0014`는 ProjectAsset partial Index 하나를 추가했습니다. 신규 Workspace Table row는 0건이고 backfill·dual write가 없으므로 Runtime Table 14개가 계속 source of truth입니다.

| 현재 영역 | 현재 Table |
|---|---|
| Music Generation | `generation_jobs`, `generated_files` |
| Stem Separation | `stem_jobs`, `stem_files` |
| Voice Conversion | `voice_conversion_jobs`, `voice_conversion_files` |
| Pipeline | `pipeline_jobs`, `pipeline_files` |
| Lyrics | `lyrics_documents` |
| Project | `projects` |
| Voice Enrollment | `voice_profiles`, `voice_enrollments`, `voice_samples` |
| API 멱등성 | `idempotency_records` |

현재 구조는 기능별 Job과 File Table이 결과를 소유하고 파일 경로를 DB에 저장합니다. 목표 구조는 공통 `Job`, 논리 `Asset`, 불변 `AssetVersion`과 경로 없는 `Artifact`로 결과 소유권을 옮깁니다.

## 2. Migration 원칙

- Big-bang 교체를 하지 않습니다.
- 현행 Table을 먼저 삭제하거나 이름 변경하지 않습니다.
- 새 목표 schema는 additive 단계로 도입합니다.
- 각 단계는 backfill, 참조 무결성, 수량, checksum과 읽기 동등성 검증 후 다음 단계로 진행합니다.
- 전환 중에도 기존 ID와 생성 시각, Job 상태, 오류, Consent와 파일 계보를 보존합니다.
- AssetVersion과 CompositionSnapshot은 backfill 후에도 불변입니다.
- 파일 경로는 API나 목표 Workspace Table로 복사하지 않습니다.
- 실제 파일 이동과 Artifact Resolver 도입은 DB row 변환과 분리합니다.
- downgrade가 새 데이터 손실을 만들면 자동 downgrade를 제공하지 않고 명시적으로 차단합니다.

### 2.1 Additive revision `20260806_0012`

- `upgrade()`는 목표 Workspace Table 21개와 해당 FK·Index·Unique·Check Constraint만 생성합니다.
- 기존 Runtime Table 14개에 대한 `alter`, Column 추가·삭제, 데이터 SQL과 backfill은 포함하지 않습니다.
- `downgrade()`는 신규 21개 Table과 Index만 역순으로 제거하며 기존 Runtime schema는 변경하지 않습니다.
- SQLAlchemy `Uuid(as_uuid=True)`는 Python에서 UUID를 생성하고 SQLite에서는 호환 문자열 형식으로 저장합니다. server-side UUID 생성은 사용하지 않습니다.
- `AssetType`과 목표 `JobStatus`는 `native_enum=False` 문자열로 저장합니다. 현재 Entity는 application-side `validate_strings=True`를 사용하며 DB-level Enum Check Constraint는 선언하지 않으므로 migration에도 임의 추가하지 않습니다.
- JSON·Boolean·timezone 지정 DateTime은 SQLAlchemy의 SQLite 호환 타입을 사용합니다. Python 3.12 SQLite datetime adapter 폐기 예정 경고는 별도 후속 작업으로 유지합니다.
- `assets.selected_asset_version_id`와 `asset_versions.asset_id`의 순환 FK는 SQLite의 신규 Table 생성 계약에서 임시 DB 검증을 통과했습니다. 다른 DB 제품으로 전환할 때는 Constraint 생성 단계를 별도로 검토합니다.

### 2.2 Keyset Index revision `20260807_0013`

- Workspace 전체·owner별 활성 목록과 Workspace별 MusicProject 목록의 `(created_at DESC, UUID DESC)` keyset 조회를 위한 복합 Index 세 개만 추가합니다.
- 기존 Table·Column·Constraint·row와 단일 Index를 변경하거나 제거하지 않습니다.
- Entity metadata와 migration은 Index 이름과 Column 순서를 동일하게 유지합니다.
- 임시 SQLite에서 upgrade 전 여섯 쿼리의 정렬용 임시 B-Tree를 확인하고 upgrade 후 신규 Index 사용과 임시 정렬 제거를 검증했습니다.
- downgrade는 신규 Index 세 개만 역순으로 제거하며 기존 Index·Table·row와 무결성을 보존합니다.
- 기존 Preflight·backup·restore rehearsal·명시적 승인 Gate를 통과한 뒤 실제 사용자 DB에 적용했습니다.
- 상세 설계와 partial·DESC 후보 판단은 [Workspace keyset Index 설계](workspace-keyset-indexes.md)를 따릅니다.

### 2.3 ProjectAsset keyset Index revision `20260807_0014`

- 활성 ProjectAsset 목록의 `(display_order ASC, project_asset_id ASC)` 정렬을 위해 `(project_id, display_order, project_asset_id) WHERE deleted_at IS NULL` partial Index 하나만 추가합니다.
- full `(project_id, deleted_at, display_order, project_asset_id)` 후보와 partial 후보가 모두 임시 SQLite 첫·다음 page에서 신규 Index를 사용하고 `USE TEMP B-TREE FOR ORDER BY`를 제거했습니다. 활성 row만 포함하는 partial 후보를 최종 선택했습니다.
- 기존 Table·Column·FK·Unique Constraint·row와 0012·0013 revision을 변경하지 않습니다. Downgrade는 이번 Index만 제거합니다.
- read-only Inventory, 검증된 backup·restore rehearsal, migration·downgrade rehearsal과 명시적 승인 Gate를 통과한 뒤 실제 사용자 DB에 적용했습니다.
- 상세 Query Plan과 중복 계약은 [ProjectAsset keyset Index 설계](project-asset-keyset-indexes.md)를 따릅니다.

### 2.4 Asset keyset Index revision `20260808_0015`

- 공개 Asset 목록은 effective Owner를 필수 내부 scope로 사용하고 선택적 `workspace_id`와 `asset_type`만 지원합니다.
- 6,000개 임시 SQLite fixture의 공식 첫·다음 page 8개 Query에서 full·partial 후보를 비교했습니다. partial 후보는 기존 `ix_assets_deleted_at`를 선택해 임시 정렬이 남았고 full 후보만 신규 Index 사용과 TEMP B-TREE 제거를 만족했습니다.
- 최종 Index는 `(owner_id, deleted_at, created_at, asset_id)`와 `(owner_id, workspace_id, deleted_at, created_at, asset_id)` 두 개입니다. 기존 단일 Index는 제거하지 않습니다.
- Upgrade·downgrade는 신규 Index 두 개만 추가·제거하고 Table 35개, Runtime 14개, Workspace 21개와 Asset row digest·무결성을 보존합니다.
- 별도 Inventory·backup·rehearsal·승인 절차를 거쳐 실제 사용자 DB에 적용했습니다.
- 상세 계약은 [Asset keyset Index 설계](asset-keyset-indexes.md)를 따릅니다.

## 3. 현재 Table별 권장 매핑

| 현재 Table | 목표 Entity | 변환 원칙 |
|---|---|---|
| `projects` | `Workspace`, `MusicProject` | 기본 Workspace 하나를 만들고 기존 Project ID·제목·시각을 MusicProject에 보존 |
| `lyrics_documents` | `Asset`, `AssetVersion`, `Artifact`, `AssetRelation`, `ModelUsage` | 문서 계열별 Lyrics Asset 생성, `version`·`parent_id` 계보 보존, 본문 직렬화 Artifact 등록, Provider 사용은 확인 가능한 범위만 기록 |
| `generation_jobs` | `Job`, `JobInput`, `JobOutput`, `ModelUsage` | 공통 상태로 정규화하고 prompt·설정은 불변 `settings_snapshot`으로 보존 |
| `generated_files` | Music `AssetVersion`, `Artifact`, `JobOutput` | 파일 Metadata와 checksum 검증 후 Artifact ID 발급, 절대·상대 경로는 Resolver로 분리 |
| `stem_jobs` | `Job`, `JobInput`, `JobOutput`, `ModelUsage` | source file을 Artifact 또는 source AssetVersion 입력으로 연결 |
| `stem_files` | Stem `Asset`, `AssetVersion`, `Artifact`, `AssetRelation` | vocals·instrumental을 별도 Stem Version으로 등록하고 source Music과 파생 관계 기록 |
| `voice_conversion_jobs` | `Job`, `JobInput`, `JobOutput`, `ModelUsage` | Vocal input, RecordingEnrollment와 Model 사용 계보를 보존 |
| `voice_conversion_files` | Vocal `AssetVersion`, `Artifact`, `AssetRelation` | 변환 Vocal을 새 불변 Version과 원본 파생 관계로 등록 |
| `pipeline_jobs` | `Job`, `CompositionSnapshot`, `History` | 기존 통합 실행은 Legacy Job으로 보존하고 입력 snapshot을 CompositionSnapshot 후보로 정규화; 신규 실행은 기능별 독립 Job 사용. 최종 `job_type` enum은 계약 확정 전 미정 |
| `pipeline_files` | Mix·Export `AssetVersion`, `Artifact`, `JobOutput` | final·metadata 역할을 Mix 또는 Export 결과로 분류하고 `DohaArtifacts/music` 책임으로 전환 |
| `voice_profiles` | `RecordingEnrollment`, Recording `Asset`·`AssetVersion`, `Approval` | Profile의 대표 reference·Consent를 Enrollment와 Recording Version으로 분리 |
| `voice_enrollments` | `RecordingEnrollment`, `Approval`, `History` | 상태·동의문 version·완료·삭제 lifecycle을 보존 |
| `voice_samples` | Recording `AssetVersion`, `Artifact`, `AssetRelation` | original·normalized Sample을 별도 Artifact와 Version 계보로 등록; Training Dataset으로 자동 분류하지 않음 |
| `idempotency_records` | 현행 운영 Table 유지 | Core 21개 Entity에 흡수하지 않고 API 멱등성 계약 확정 전까지 보존 |

확인할 수 없는 Provider version, Model Manifest, License와 Commercial Status를 추정해서 채우지 않습니다. `UNKNOWN` 또는 `REVIEW_REQUIRED`를 사용하고 검토 대상으로 남깁니다.

## 4. 상태 정규화

목표 Job 상태는 Common Specification과 동일한 다섯 값만 사용합니다.

| 현행 상태 | 목표 상태 | 보존 정보 |
|---|---|---|
| `PENDING` | `queued` | 기존 `current_step`은 `stage`로 보존 |
| `VALIDATING`, `GENERATING`, `STEM_SEPARATING`, `VOICE_CONVERTING`, `MIXING`, `EXPORTING`, `CANCEL_REQUESTED` | `running` | 원래 상태는 `stage`와 History에 보존 |
| `COMPLETED` | `succeeded` | Artifact checksum 검증 실패 시 성공으로 전환하지 않음 |
| `FAILED` | `failed` | 오류 코드·안전한 메시지·재시도 관계 보존 |
| `CANCELLED` | `cancelled` | 요청 시각과 확정 시각 보존 |

`CANCEL_REQUESTED`는 공통 종료 상태가 아니므로 목표 `status=running`과 별도 `stage`·History로 표현합니다. Common Specification의 contract version에서 확장 상태가 승인되면 다시 검토합니다.

## 5. 단계적 전환

### Phase 0 — Specification 고정

1. DohaStudio Common Specification의 merge commit과 contract version을 확정합니다.
2. 확정된 `Asset.workspace_id`와 N:M `ProjectAsset` 계약이 목표 Table Definition과 일치하는지 재검증합니다.
3. ID, enum, JSON Schema, Artifact Resolver와 Approval 계약을 승인합니다.
4. 목표 ERD와 Table Definition을 ADR 상태와 함께 승인합니다.

완료 전에는 Migration 파일을 작성하지 않습니다.

### Phase 1 — 현행 Inventory와 복구 기준

1. `[도구 완료·실DB 미수행]` 14개 Table row 수, revision, FK, integrity와 schema drift를 read-only로 기록합니다.
2. `[완료]` SQLite backup API로 실제 사용자 DB backup을 검증하고 원본과 분리된 임시 위치에서 복구 절차를 검증했습니다.
3. 모든 파일 Metadata와 실제 파일 존재 여부·크기·checksum을 읽기 전용으로 대조합니다.
4. 개인 음성, Consent와 삭제 대기 데이터를 별도 위험 목록으로 분류합니다.

이 단계는 파일을 이동하거나 삭제하지 않습니다.

실제 적용은 [Preflight 체크리스트](../10-operations/workspace-db-preflight-checklist.md)의 모든 Gate와 사용자 승인을 거쳐 완료했습니다. 앱 startup 자동 `upgrade head`는 기본 비활성화했고 Runtime·Alembic online SQLite 연결은 `PRAGMA foreign_keys=ON`을 보장합니다. 이번 Repository 작업에서는 실제 사용자 DB를 다시 읽거나 변경하지 않습니다.

### Phase 2 — 목표 Schema 추가 [진행 중]

1. `[완료]` 21개 목표 Table을 추가하는 additive revision 파일을 작성하고 임시 SQLite DB에서 검증합니다.
2. `[완료]` FK, Unique, Index와 Check를 Entity metadata와 비교하고 이름 중복이 없음을 검증합니다.
3. 기본 Workspace를 만들고 기존 `projects`를 `music_projects`로 backfill합니다.
4. 현행 API 읽기·쓰기는 아직 바꾸지 않습니다.

1~2번, `20260806_0012`의 additive Table과 후속 Workspace·Project keyset Index revision `20260807_0013`, ProjectAsset keyset Index revision `20260807_0014`, Asset keyset Index revision `20260808_0015`의 실제 사용자 DB 적용을 완료했습니다. 신규 Workspace Table row는 0건이며 3번 backfill도 수행하지 않았습니다.

### Phase 3 — Asset와 Artifact 계보 Backfill

1. Lyrics, Music, Stem, Vocal, Recording, Mix와 Export를 논리 Asset으로 분류합니다.
2. 현행 row의 생성 순서·parent 관계로 AssetVersion을 단조 증가 생성합니다.
3. 실제 Payload를 읽어 Artifact ID, 크기와 checksum을 등록합니다.
4. 경로는 접근 제어된 Resolver로 옮기고 목표 DB에는 Artifact ID만 남깁니다.
5. source와 파생 관계를 `AssetRelation`으로 검증합니다.

실제 파일 이동은 별도 Storage Migration에서 수행하며 이 DB backfill과 같은 transaction으로 묶지 않습니다.

### Phase 4 — Job 통합 Backfill

1. 기능별 네 Job Table과 기존 Pipeline Job을 공통 `jobs`로 변환합니다.
2. 입력과 출력을 `job_inputs`, `job_outputs`로 연결합니다.
3. Provider·Model 정보는 `model_usages`로 이동하고 미확인 권리 상태는 승인하지 않습니다.
4. Retry와 오류·취소·단계 History를 보존합니다.
5. 기존 Job ID와 새 Job ID의 대응을 검증 기록으로 유지합니다.

### Phase 5 — Snapshot, Selection과 Approval

1. 기존 Project의 현재 결과 조합을 정확한 AssetVersion Selection으로 결정합니다.
2. 재현 근거가 충분한 경우에만 CompositionSnapshot을 생성합니다.
3. 근거가 불충분한 기존 Pipeline 입력은 Snapshot 승인 상태로 표시하지 않고 검토 대상으로 둡니다.
4. 최종 가사, 음성 Consent와 상업 이용 판단을 목적별 Approval 이벤트로 분리합니다.
5. Voice Profile과 Sample을 Recording Asset·RecordingEnrollment로 backfill합니다.

### Phase 6 — Dual Write와 Shadow Read

1. 새 쓰기를 현행 Table과 목표 Table에 함께 기록합니다.
2. 응답은 현행 경로에서 제공하되 목표 schema로 같은 결과를 재구성해 비교합니다.
3. ID, 상태, Version, Artifact checksum, Snapshot과 권한 차이를 측정합니다.
4. 불일치가 있으면 목표 읽기 전환을 중단하고 현행 경로를 유지합니다.

Dual Write 순서와 transaction 보상은 구현 ADR에서 별도로 결정합니다.

### Phase 7 — Read 전환

1. 내부 조회를 Workspace → Project → Asset → Version → Artifact 순서로 전환합니다.
2. Job·History·Export API를 목표 schema projection으로 전환합니다.
3. Provider 결과가 기존 Version을 수정하지 않고 새 Version을 만드는지 검증합니다.
4. 절대·상대 경로가 API와 Workspace DB에 남지 않는지 확인합니다.
5. 사용자 승인 후 목표 schema를 source of truth로 지정합니다.

### Phase 8 — Legacy 동결과 제거

1. 현행 Table 쓰기를 중단하고 읽기 전용 보존 기간을 둡니다.
2. 운영·사용자 검증과 backup 복구 시험을 마칩니다.
3. 별도 승인 PR에서만 Legacy ORM, Repository, API와 Table 제거를 수행합니다.
4. 기존 파일은 Artifact Resolver·retention 검증 전 삭제하지 않습니다.
5. 제거 후에도 Migration 검증 결과와 감사 근거를 보존합니다.

## 6. 단계별 Rollback

| 단계 | Rollback 원칙 |
|---|---|
| Phase 2~5 | 현행 Table이 source of truth이므로 새 Table 쓰기를 중단하고 현행 경로 유지 |
| Phase 6 | Dual Write 중단, 목표 row를 격리하고 현행 읽기 유지 |
| Phase 7 | 목표 schema에서만 생성된 Version·Artifact가 있으면 먼저 역동기화 검증; 자동 downgrade 금지 |
| Phase 8 | Legacy 제거 전 backup 복구 시험과 명시적 사용자 승인 필수 |

Rollback은 AssetVersion row를 수정하거나 삭제하는 방식으로 수행하지 않습니다. 잘못 생성된 Version은 Selection에서 제외하고 History와 관계를 보존합니다.

## 7. 검증 Gate

| Gate | 통과 기준 |
|---|---|
| Row 수 | 모든 현행 핵심 row가 정확히 하나 이상의 목표 row 또는 명시적 제외 기록에 대응 |
| FK | orphan 0건, 순환 Version·Relation 0건 |
| Version | Asset별 번호 중복 0건, 기존 parent 순서 보존 |
| Artifact | 존재 가능한 파일의 크기·checksum 일치, 경로 field 0건 |
| Job | 공통 상태 변환 100%, 종료 상태 역전이 0건 |
| Snapshot | 모든 Item이 정확한 AssetVersion 참조, 최신 Asset 간접 참조 0건 |
| Approval | 목적·대상·근거 없는 승인 0건, Commercial 자동 승인 0건 |
| Voice | Consent 없는 Enrollment 활성화 0건, Training Dataset 자동 편입 0건 |
| Security | 공개 DTO·로그·History에 절대 경로·비밀·동의 증적 원문 0건 |
| Recovery | backup restore와 단계별 rollback rehearsal 통과 |

## 8. 기존 DB와 목표 DB의 핵심 차이

| 현재 | 목표 |
|---|---|
| 기능별 Job/File Table | 공통 Job과 AssetVersion/Artifact |
| Pipeline Job이 최종 결과와 경로를 보유 | AssetVersion이 결과, Artifact가 Payload Metadata를 보유 |
| Project 1:N Pipeline Job 중심 | Workspace → MusicProject와 ProjectAsset N:M |
| 파일 상대 경로를 DB에 저장 | Artifact ID만 저장하고 Resolver가 위치 해석 |
| 현재 입력 JSON이 Snapshot 역할 일부 수행 | 정확한 Version을 고정하는 불변 CompositionSnapshot |
| Provider·Model 문자열이 Job마다 분산 | ModelUsage와 Model Manifest ID로 계보 통합 |
| Lyrics·Voice가 별도 aggregate | 공통 Asset/Version에 도메인 유형으로 통합 |
| History가 Pipeline projection | 별도 append-only History Entity |
| 최종 선택·Consent·상업 승인 분산 | Selection과 목적별 Approval 분리 |

## 9. 미확정 사항

- Common Specification Draft PR merge·version 확정 시점
- Artifact Resolver와 물리 파일 Migration의 담당 component
- Legacy Pipeline Job을 하나의 Workspace Job으로 보존할지 History 전용으로 보존할지
- 현행 `idempotency_records`의 장기 소유 위치
- 목표 schema Dual Write 기간과 운영 중단 허용 시간
- SQLite에서 운영 DB로 동시에 전환할지 DB 제품 전환을 별도 작업으로 분리할지
- 개인정보 삭제 요청과 불변 감사 계보가 충돌할 때 비식별화 범위
