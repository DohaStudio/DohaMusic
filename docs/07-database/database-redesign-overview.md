# Asset 중심 데이터베이스 재설계 개요

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-07
> 관련 기능: DohaMusic Workspace 데이터베이스 재설계
> 구현 상태: 목표 21개 Entity·metadata와 revision `20260806_0012`·`20260807_0013`·`20260807_0014` 실제 적용, Workspace Repository·Service와 첫 Resource API 8개 완료; ProjectAsset API·Bootstrap·backfill·dual write 미수행
> 관련 문서: [목표 ERD](database-redesign-erd.md), [목표 Table Definition](database-redesign-table-definition.md), [Migration 전략](database-redesign-migration-strategy.md), [ADR-030](../11-decisions/ADR-030-asset-version-centric-database.md)

## 1. 목적

DohaMusic의 목표 데이터베이스를 기존 Pipeline 중심 구조에서 Workspace의 불변 작품 계보 중심 구조로 다시 설계합니다.

```text
Workspace
→ MusicProject
→ ProjectAsset
→ Asset
→ AssetVersion
→ Artifact
→ Composition Snapshot
→ Job
→ Export
```

Pipeline은 실행 순서를 orchestration하지만 결과를 소유하지 않습니다. 생성·편집·처리 결과는 새 `AssetVersion`이 소유하고 실제 파일 또는 직렬화된 Payload는 `Artifact`로 분리합니다.

이 문서는 목표 논리 구조와 SQLAlchemy Entity mapping을 정의합니다. additive revision `20260806_0012`는 실제 사용자 DB에 적용됐으며 기존 Runtime Entity와 Table 14개는 그대로 유지됩니다. Repository와 Service는 완료했지만 실제 Bootstrap은 실행하지 않아 신규 Workspace Table 21개는 현재 빈 상태입니다. Resource API·backfill·dual write와 Storage 경로·Runtime 전환은 수행하지 않았습니다.

## 2. Common Specification 기준

설계 기준은 [DohaStudio Common Specification](https://github.com/DohaStudio/.github/tree/main/docs/specifications) `0.1.0` / `draft-baseline`이며, 감사·재현 기준은 commit `1e4b480c8cbd6e51835f8550e685e9b136d8071d`입니다.

- [Asset 명세](https://github.com/DohaStudio/.github/blob/main/docs/specifications/01-asset-specification.md)
- [AssetVersion 명세](https://github.com/DohaStudio/.github/blob/main/docs/specifications/02-asset-version-specification.md)
- [Artifact 명세](https://github.com/DohaStudio/.github/blob/main/docs/specifications/03-artifact-specification.md)
- [Provider 계약](https://github.com/DohaStudio/.github/blob/main/docs/specifications/04-provider-contract.md)
- [Job 계약](https://github.com/DohaStudio/.github/blob/main/docs/specifications/05-job-contract.md)
- [Model Manifest 명세](https://github.com/DohaStudio/.github/blob/main/docs/specifications/06-model-manifest-specification.md)
- [Dataset Manifest 명세](https://github.com/DohaStudio/.github/blob/main/docs/specifications/07-dataset-manifest-specification.md)
- [Composition Snapshot 명세](https://github.com/DohaStudio/.github/blob/main/docs/specifications/08-composition-snapshot-specification.md)
- [Storage 구조 명세](https://github.com/DohaStudio/.github/blob/main/docs/specifications/09-storage-layout-specification.md)
- [공통 용어](https://github.com/DohaStudio/.github/blob/main/docs/specifications/10-common-terms.md)

Common Specification은 `draft-baseline`이며 안정 API를 뜻하는 `1.0.0`이 아닙니다. 이번 설계는 `[제안]` 상태를 유지하고, 공통 명세가 변경되면 구현 전에 차이를 다시 검토합니다.

## 3. 설계 원칙

### 3.1 Workspace와 MusicProject

- 초기 사용자는 한 명이지만 모든 `MusicProject`는 하나의 `Workspace`에 속합니다.
- `Workspace`는 향후 사용자·권한 확장 경계를 유지합니다.
- `MusicProject`와 `Asset`은 `ProjectAsset`을 통한 N:M 관계입니다.
- 확정된 Common Specification은 Asset을 Workspace 범위 재사용 자산으로 정의하고 `Asset.project_id`를 제거했습니다. 이 설계도 `Asset.workspace_id`와 N:M `ProjectAsset`을 단일 Project 연결 기준으로 사용합니다.
- DohaMusic은 현재 REST 식별 경로와 Unique Constraint에 맞춰 `(project_id, asset_id)`를 ProjectAsset identity로 사용합니다. `role`은 관계 Metadata이며 같은 Asset을 같은 Project에 role만 바꿔 중복 연결하지 않습니다. Soft Delete 후 재연결은 기존 row를 복원합니다.

### 3.2 Asset, AssetVersion과 Artifact

- `Asset`은 `lyrics`, `music`, `vocal`, `stem`, `recording`, `mix`, `export` 같은 논리 객체입니다.
- 하나의 `Asset`은 여러 `AssetVersion`을 가집니다.
- `AssetVersion`은 생성 후 본문·계보·설정·참조를 수정하지 않습니다.
- 수정, 재처리, AI 후보와 최종 선택은 모두 새 `AssetVersion`을 생성합니다.
- `Artifact`는 실제 파일 또는 직렬화된 Payload이며 하나의 `AssetVersion`에 속합니다.
- DB에는 절대 경로나 Root 기준 상대 경로를 저장하지 않고 `artifact_id`와 무결성 Metadata만 저장합니다.

### 3.3 Selection, Approval과 Rollback

- 현재 선택은 `Asset.selected_asset_version_id`가 가리킵니다.
- 새 Version 생성은 현재 Selection을 자동 변경하지 않습니다.
- Rollback은 과거 Version을 수정하거나 복사하는 작업이 아니라 Selection을 과거 `AssetVersion`으로 변경하는 작업입니다.
- `Approval`은 Selection과 분리합니다. 승인 목적·상태·근거·결정 주체·결정 시각을 독립적으로 보존해야 하므로 별도 Entity가 필요합니다.
- 품질 평가 통과, 사용자 최종 선택, 음성 사용 동의와 상업 이용 승인은 서로 대체하지 않습니다.

### 3.4 Composition Snapshot

- `CompositionSnapshot`은 `MusicProject`가 선택한 정확한 `AssetVersion`을 고정합니다.
- `SnapshotItem`은 Lyrics, Music, Vocal, Stem과 Mix 등 역할별 `asset_version_id`를 저장합니다.
- Snapshot은 Processing Chain, Mix Settings, Provider version과 Model version도 생성 시점 값으로 보존합니다.
- 기존 Asset Selection이 바뀌어도 과거 Snapshot은 변하지 않습니다.

### 3.5 Job과 결과 소유권

- `Job`은 Pipeline 자체가 아니라 독립 실행 단위입니다.
- Job 유형은 Lyrics Generation, Music Generation, Vocal Generation, Mix와 Export 등을 표현합니다.
- `JobInput`은 정확한 입력 `AssetVersion` 또는 직접 입력 `Artifact`를 연결합니다.
- `JobOutput`은 성공 후 등록된 출력 `AssetVersion` 또는 `Artifact`를 연결합니다.
- 재시도는 기존 Job 상태를 초기화하지 않고 `retry_of_job_id`로 연결된 새 Job을 생성합니다.
- Provider는 Workspace DB를 직접 수정하지 않습니다. DohaMusic이 검증된 Provider 결과를 `Artifact`와 새 `AssetVersion`으로 등록합니다.

### 3.6 Processing Chain과 ModelUsage

- `ProcessingChain`은 처리 순서의 불변 정의이며 `ProcessingStep`을 순서대로 가집니다.
- Noise, Pitch, Timing, Normalize, AutoTune과 Voice Conversion은 Version 이름이 아니라 처리 단계입니다.
- `ModelUsage`는 Job에서 사용한 Provider, Model, Manifest, Version, License와 Commercial Status를 기록합니다.
- Provider 자체를 별도 Workspace Entity로 만들지 않습니다.
- Model Manifest와 Dataset Manifest 본문은 각 Provider Repository가 소유합니다. DohaMusic DB는 `model_manifest_id`와 실행 시점 `ModelUsage`만 저장하며 별도 Dataset Manifest Table을 만들지 않습니다.

### 3.7 Recording과 Enrollment

- Recording은 작품 입력이므로 `recording` 유형 `Asset`과 불변 `AssetVersion`으로 관리합니다.
- Enrollment는 음색 등록·참조 승인을 위한 별도 `RecordingEnrollment`입니다.
- Recording Asset을 Enrollment Sample 또는 Training Dataset으로 자동 간주하지 않습니다.
- 개인 음성 Artifact의 접근·보존·삭제는 Consent와 Workspace 권한을 따릅니다.

### 3.8 Storage

- Provider Runtime 결과는 `DohaArtifacts/lm`, `DohaArtifacts/audio`, `DohaArtifacts/vocal`의 Artifact ID로 해석합니다.
- Mix, Export, Preview와 Composition Snapshot 직렬화본은 `DohaArtifacts/music`의 Artifact ID로 해석합니다.
- DB는 Root 이름, drive, mount와 상대 경로를 직접 저장하지 않습니다.
- `Artifact` Metadata와 접근 제어된 Catalog 또는 Resolver가 물리 위치를 연결합니다.
- Export는 `export` 유형 Asset과 불변 AssetVersion이며 WAV·MP3·FLAC 파일은 Artifact입니다.

## 4. 목표 Entity와 Table 수

| 분류 | Entity | Table |
|---|---:|---:|
| Workspace와 Project | 3 | 3 |
| Asset와 Artifact | 5 | 5 |
| Snapshot과 Processing | 4 | 4 |
| Job과 ModelUsage | 4 | 4 |
| Enrollment와 협업 Metadata | 5 | 5 |
| 합계 | **21** | **21** |

전체 목록은 다음과 같습니다.

1. `Workspace`
2. `MusicProject`
3. `ProjectAsset`
4. `Asset`
5. `AssetVersion`
6. `Artifact`
7. `AssetRelation`
8. `CompositionSnapshot`
9. `SnapshotItem`
10. `ProcessingChain`
11. `ProcessingStep`
12. `Job`
13. `JobInput`
14. `JobOutput`
15. `ModelUsage`
16. `RecordingEnrollment`
17. `Approval`
18. `Tag`
19. `Comment`
20. `Favorite`
21. `History`

## 5. 삭제 정책

- 기본 정책은 Soft Delete입니다.
- `Workspace`, `MusicProject`, `ProjectAsset`, `Asset`, `RecordingEnrollment`, `Tag`, `Comment`와 `Favorite`은 `deleted_at`으로 논리 삭제합니다.
- `AssetVersion`, `CompositionSnapshot`, `SnapshotItem`, `ProcessingChain`, `ProcessingStep`, `Job`, `JobInput`, `JobOutput`, `ModelUsage`, `Approval`과 `History`는 감사·재현성 근거이므로 직접 삭제하지 않습니다.
- `Artifact`는 DB row 삭제와 Payload 물리 삭제를 분리하고 `retention_status`로 요청·격리·삭제 완료를 추적합니다.
- Asset Soft Delete가 AssetVersion 또는 Artifact 물리 삭제를 자동 실행하지 않습니다.
- 개인 음성 삭제는 파생 관계와 Consent 정책을 확인한 별도 lifecycle 처리로 수행합니다.

## 6. 현재 구현과의 관계

실제 사용자 DB에는 Workspace Table 21개를 추가한 `20260806_0012`, Workspace·Project keyset Index 3개를 추가한 `20260807_0013`과 ProjectAsset partial keyset Index 하나를 추가한 `20260807_0014`가 적용됐습니다. 신규 Table row는 0건이며 현행 Runtime Table 14개가 계속 source of truth입니다. Workspace·MusicProject v1 Resource API 8개만 구현 상태이고 ProjectAsset Router 3개는 계획입니다.

- 초기 Entity 구현: `backend/models/workspace/`
- metadata 등록: `backend/models/__init__.py`
- Entity 계약 검증: `backend/tests/test_workspace_entities.py`
- Workspace Repository: `backend/repositories/workspace/`
- Repository 계약 검증: `backend/tests/test_workspace_repositories.py`
- Workspace Service: `backend/services/workspace/`
- Service transaction 검증: `backend/tests/test_workspace_services.py`

- 현재 ERD: [erd.md](erd.md)
- 현재 Table Definition: [table-definition.md](table-definition.md)
- 목표 ERD: [database-redesign-erd.md](database-redesign-erd.md)
- 목표 Table Definition: [database-redesign-table-definition.md](database-redesign-table-definition.md)
- 전환 계획: [database-redesign-migration-strategy.md](database-redesign-migration-strategy.md)

현재 문서를 목표 구조로 덮어쓰지 않는 이유는 구현과 문서가 불일치하는 기간에 현행 사실을 잃지 않기 위해서입니다.

## 7. 이번 작업에서 하지 않는 것

- SQL 또는 Alembic Migration 작성
- REST API·Pydantic Schema와 Workspace Service 연결
- API·Worker·Pipeline 변경
- DB 파일 생성·변환
- Artifact 파일 이동 또는 환경 변수 변경
- Provider Runtime 변경

## 8. 미확정 사항

- Common Specification의 정식 contract version
- ID의 전역 고유성 범위와 UUID version
- JSON field의 JSON Schema와 contract version
- Artifact Catalog 또는 Resolver의 구현·운영 주체
- `Approval.status`, `lifecycle_status`, 관계 유형의 최종 enum
- Snapshot의 Provider/Model version을 JSON snapshot과 관계형 `ModelUsage` 중 어디까지 중복 보존할지
- 인증 도입 후 `created_by`, `approved_by`와 Owner 식별자의 참조 방식
- 현행 `idempotency_records`를 공통 운영 Table로 유지할지 별도 API 계층으로 옮길지
