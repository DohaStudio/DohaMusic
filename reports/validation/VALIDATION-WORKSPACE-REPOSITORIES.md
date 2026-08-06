# Workspace Repository 계층 검증 보고서

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-06
> 기준 브랜치: `feature/workspace-repositories`
> 기준 develop: `1084d23502ab416c8ba0ff4f84824ef1b093dd35`

## 1. 목적

이 보고서는 기존 Runtime Repository를 변경하지 않고 신규 Workspace Entity 21개를 위한 Repository 계층을 additive로 구현한 결과를 기록한다. 이번 검증은 임시 SQLite DB만 사용했으며 실제 사용자 DB에는 접근하지 않았다.

## 2. Aggregate 구성

| Repository | 담당 Entity 수 | 담당 Entity |
|---|---:|---|
| `WorkspaceRepository` | 3 | `Workspace`, `MusicProject`, `ProjectAsset` |
| `AssetRepository` | 4 | `Asset`, `AssetVersion`, `Artifact`, `AssetRelation` |
| `CompositionRepository` | 4 | `CompositionSnapshot`, `SnapshotItem`, `ProcessingChain`, `ProcessingStep` |
| `JobRepository` | 4 | `Job`, `JobInput`, `JobOutput`, `ModelUsage` |
| `CollaborationRepository` | 6 | `RecordingEnrollment`, `Tag`, `Comment`, `Favorite`, `History`, `Approval` |

## 3. Transaction 계약

- Repository 생성자에 동기 SQLAlchemy `Session`을 주입한다.
- 생성 메서드는 `add`와 `flush`까지만 수행한다.
- Repository 내부 `commit`과 `rollback`을 금지한다.
- 여러 Aggregate의 원자적 처리는 향후 Service 또는 Unit of Work가 담당한다.
- 기존 Runtime Repository의 transaction 방식은 변경하지 않는다.

## 4. 조회와 불변성 계약

- SQLAlchemy 2.0 `select()` 기반 조회를 사용한다.
- 목록은 `created_at`과 기본 키 또는 명시적 순서 필드로 안정적으로 정렬한다.
- 모든 목록 메서드는 기본 `limit`과 `offset`을 제공한다.
- `SoftDeleteMixin` 적용 Entity는 기본 조회에서 `deleted_at`이 설정된 row를 제외한다.
- `AssetVersion`과 `CompositionSnapshot` 수정 메서드를 제공하지 않는다.
- Snapshot은 `SnapshotItem`을 통해 특정 `AssetVersion`을 참조하며 최신 버전을 자동 선택하지 않는다.
- Repository는 Entity를 반환하고 권한·상태 전이·HTTP 오류·Storage 해석을 담당하지 않는다.

## 5. 검증 범위와 결과

| 검증 | 결과 |
|---|---|
| Workspace Repository 전용 테스트 | `8 passed` |
| Entity·Alembic·Migration Safety 포함 | `26 passed` |
| 기존 Runtime Repository·대표 API 회귀 | `12 passed`, 기존 OpenAPI 중복 경고 2건 |
| transaction 외부 경계와 rollback | 통과 |
| SQLite foreign key 활성화 | 통과 |
| N:M·Unique·순서 Constraint | 통과 |
| Soft Delete 기본 필터 | 통과 |
| `AssetVersion`·Snapshot 불변 API | 통과 |
| Python compile·FastAPI `create_app()` | 통과, Route 45개 |
| Ruff lint·format check | 통과, Backend 231개 파일 |
| Alembic head | `20260806_0012` 단일 head |
| `git diff --check` | 통과 |
| 실제 사용자 DB 접근 | 수행하지 않음 |

## 6. 현재 상태

- Workspace Entity 21개: [완료]
- Workspace additive Migration 실제 사용자 DB 적용: [완료]
- Workspace Repository: [진행 중] 이번 PR 범위
- Workspace Service: [계획] 미구현
- Workspace REST API: [계획] 미구현
- backfill·dual write: [계획] 미구현
- Legacy Runtime Table 제거: [계획] 미구현

신규 Workspace Table은 비어 있고 기존 Runtime Table 14개가 계속 source of truth다.

## 7. 제한과 후속 검토

- 권한과 Job 상태 전이 규칙은 Service 계층에서 구현해야 한다.
- cursor pagination의 직렬화와 서명은 REST API 계층의 후속 범위다.
- Soft Delete된 `ProjectAsset`, `Tag`, `Favorite`의 Unique row 재사용 정책은 현행 DB Constraint와 함께 Service 설계에서 확정해야 한다.
- Storage URI resolver, backfill, dual write와 Legacy 전환은 구현하지 않았다.
