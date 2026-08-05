# ADR-030 — AssetVersion 중심 Workspace 데이터베이스

> 상태: [제안]
> 작성일: 2026-08-05
> 최종 수정일: 2026-08-05
> 관련 기능: DohaMusic Workspace 데이터베이스 재설계
> 관련 문서: [재설계 개요](../07-database/database-redesign-overview.md), [목표 ERD](../07-database/database-redesign-erd.md), [목표 Table Definition](../07-database/database-redesign-table-definition.md), [Migration 전략](../07-database/database-redesign-migration-strategy.md)
> 관련 PR: [PR #52](https://github.com/DohaStudio/DohaMusic/pull/52)

## 배경

현재 DohaMusic DB는 Music Generation, Stem Separation, Voice Conversion과 Pipeline마다 Job·File Table을 따로 가지며 결과 파일 경로를 각 File row에 저장합니다. Project는 Pipeline Job을 묶고 History는 Pipeline 결과 projection으로 구성됩니다.

DohaStudio Common Specification은 Workspace의 논리 작품을 `Asset`, 불변 상태를 `AssetVersion`, 실제 파일·Payload를 `Artifact`, 실행을 `Job`, 선택된 곡 구성을 `CompositionSnapshot`으로 구분합니다. Provider 결과도 Workspace DB를 직접 수정하지 않고 DohaMusic이 검증 후 새 Version으로 등록해야 합니다.

## 문제

기능별 Job·File 구조에서는 같은 작품의 사용자 편집, AI 후보, Stem, Voice Conversion, Mix와 Export 계보가 여러 aggregate에 흩어집니다. Pipeline이 결과의 사실상 소유자가 되므로 Pipeline 밖의 편집·선택·승인과 재현 가능한 Snapshot을 표현하기 어렵습니다. DB에 저장된 파일 경로도 Common Artifact 계약과 충돌합니다.

## 결정

목표 DB의 중심을 `Workspace → MusicProject → ProjectAsset → Asset → AssetVersion → Artifact`로 전환합니다.

- MusicProject와 Asset은 `ProjectAsset`을 통한 N:M 관계로 둡니다.
- AssetVersion은 불변이며 수정·후보·최종 선택을 새 Version으로 기록합니다.
- Pipeline은 결과를 소유하지 않고 독립 `Job`을 orchestration합니다.
- Job의 입력·출력은 `JobInput`, `JobOutput`으로 정확한 AssetVersion 또는 Artifact를 참조합니다.
- CompositionSnapshot은 선택된 AssetVersion, Processing Chain, Mix Settings, Provider와 Model version을 고정합니다.
- Provider·Model·Manifest·License·Commercial Status는 `ModelUsage`로 기록합니다.
- Recording 작품 Asset과 음색 등록 `RecordingEnrollment`를 분리합니다.
- Selection과 승인 판단을 분리하고 목적별 `Approval`을 별도 불변 Entity로 둡니다.
- Artifact에는 절대·상대 경로를 저장하지 않고 Artifact ID와 무결성 Metadata만 저장합니다.
- 기본 삭제는 Soft Delete이며 AssetVersion, Snapshot, Job, ModelUsage, Approval과 History를 직접 삭제하지 않습니다.

목표 Core는 21개 Entity와 21개 Table입니다. 현행 `idempotency_records`는 API 운영 Table로 유지하고 Core 모델에 억지로 포함하지 않습니다.

## 선택 이유

- 사용자 작성·AI 생성·처리·선택 결과의 불변 계보를 한 구조로 표현합니다.
- Pipeline 단계와 작품 결과 소유권을 분리합니다.
- Mix·Export를 Provider 결과가 아닌 DohaMusic Workspace Asset으로 관리합니다.
- 재시도와 Rollback이 기존 결과를 덮어쓰지 않습니다.
- Provider·Model·License와 Commercial Status를 결과 Version까지 추적할 수 있습니다.
- Storage 위치를 Artifact ID 뒤로 숨겨 local filesystem과 향후 object storage를 분리합니다.

## 대안

1. 현행 기능별 Job·File Table을 계속 확장: Migration은 작지만 도메인별 중복과 Pipeline 중심 소유권이 유지되어 선택하지 않습니다.
2. Pipeline Job 하나에 모든 Version·Artifact·Snapshot을 JSON으로 저장: FK·검색·무결성·부분 재사용이 약해 선택하지 않습니다.
3. Asset가 파일 경로와 현재 내용까지 직접 소유: Asset, Version과 Artifact 경계를 무너뜨려 선택하지 않습니다.
4. Big-bang schema 교체: Consent·파일·Job 이력 손실과 복구 위험이 커 선택하지 않습니다.

## 장점과 단점

장점은 계보·재현성·선택·승인·Storage 경계가 명확해지고 Provider 교체와 여러 후보 관리가 쉬워지는 점입니다. 단점은 Entity와 FK가 늘고 Version 생성 transaction, Artifact Resolver, Dual Write, backfill과 데이터 검증이 필요하다는 점입니다.

## 영향

이번 ADR은 문서와 ERD만 추가합니다. 현재 SQLite, SQLAlchemy Entity, Alembic head, API, Worker, Pipeline, Storage 파일과 환경 변수는 변경하지 않습니다.

구현 시 기존 ADR-003의 비동기 Job, ADR-012의 Pipeline Orchestrator, ADR-020의 Project History, ADR-021의 Cancel·Retry, ADR-025~026의 Voice Enrollment와 관련 DB 결정을 목표 공통 구조에 매핑해야 합니다. 이 ADR이 제안 상태인 동안 기존 ADR과 구현이 현행 기준입니다.

## Migration

1. Common Specification의 merge commit과 contract version을 확정합니다.
2. 현행 14개 Table과 파일을 읽기 전용 Inventory하고 backup 복구를 검증합니다.
3. 목표 21개 Table을 additive로 추가합니다.
4. Workspace·Project, Asset·Version·Artifact, Job·ModelUsage, Snapshot·Approval 순서로 backfill합니다.
5. Dual Write와 Shadow Read로 결과 동등성을 확인합니다.
6. 목표 읽기로 전환하고 일정 기간 현행 Table을 읽기 전용 보존합니다.
7. 별도 승인 PR에서만 Legacy ORM·API·Table을 제거합니다.

세부 단계와 Rollback은 [Migration 전략](../07-database/database-redesign-migration-strategy.md)을 따릅니다.

## 재검토 조건

- Common Specification의 Asset·ProjectAsset·Artifact·Job 계약이 확정되거나 변경될 때
- Artifact Resolver 또는 공통 Registry의 운영 주체가 결정될 때
- 인증·다중 사용자·Workspace 권한 모델이 확정될 때
- SQLite 외 운영 DB를 선정할 때
- Dual Write가 허용할 수 없는 정합성·성능 비용을 만들 때
- 개인정보 삭제 의무와 불변 계보 보존이 충돌할 때
- 기존 Pipeline Job의 Migration 결과가 재현 가능한 Snapshot을 만들기에 부족할 때
