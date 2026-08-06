# Workspace Application Service 검증 보고서

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-06
> 기준 브랜치: `feature/workspace-services`
> 기준 develop: `c857ec970b3d834855ea75867db0028b9d078711`

## 1. 검증 목적

Workspace Repository 5개를 조합하는 Application Service와 Service 소유 transaction 경계를 검증한다. 테스트는 임시 SQLite만 사용하며 실제 사용자 DB에는 접근하지 않는다.

## 2. 구현 범위

- `WorkspaceService`
- `AssetService`
- `CompositionService`
- `JobService`
- `CollaborationService`
- Application Not Found·Conflict·Validation·Invalid State 오류
- Soft Delete Unique row 복구
- Job 공통 상태 전이

범용 Unit of Work, REST API·Pydantic Schema·Frontend·Provider·Worker는 구현하지 않았다.

## 3. Transaction 검증

- Service 메서드가 `session_factory`로 Session을 생성한다.
- 변경 Use Case가 `session.begin()` transaction 하나를 소유한다.
- 여러 Repository가 같은 Session을 공유한다.
- 성공 시 transaction 전체가 commit된다.
- 중간 예외 시 생성된 모든 row가 rollback된다.
- Repository 내부 `commit`·`rollback` 호출은 0건이다.
- Session 종료 후 pool checkout은 0건이다.

## 4. 검증 결과

| 검증 | 결과 |
|---|---|
| Workspace Service 신규 테스트 | `13 passed` |
| Workspace Repository·Entity·Migration Safety | `26 passed` |
| 기존 Runtime Service·Repository·대표 API | `12 passed`, 기존 OpenAPI 중복 경고 2건 |
| 전체 선별 회귀 | `51 passed` |
| Snapshot 중간 실패 rollback | 통과, Snapshot·Item 잔존 0건 |
| JobInput 중간 실패 rollback | 통과, Job·Input 잔존 0건 |
| Soft Delete Unique 복구 | 통과 |
| AssetVersion·Snapshot 불변 API | 통과 |
| Workspace 범위 검증 | 통과 |
| Job 상태 전이 | 통과 |
| Python compile·Ruff·format check | 통과 |
| FastAPI `create_app()` | 통과, Route 45개 |
| Alembic head | `20260806_0012` |
| `git diff --check` | 통과 |
| 실제 사용자 DB 접근 | 수행하지 않음 |

## 5. 현재 상태

- Workspace Entity: [완료]
- Workspace additive Migration 실제 DB 적용: [완료]
- Workspace Repository: [완료]
- Workspace Service transaction: [진행 중] 이번 PR 범위
- 범용 Unit of Work: [제외] 현재 구조에서 불필요
- Workspace REST API·Frontend: [계획] 미구현
- backfill·dual write·Runtime 전환: [계획] 미구현

## 6. 남은 검토

- 자동 Version 번호는 SQLite 단일 로컬 환경에서도 동시 요청 시 Unique Constraint가 최종 방어선이다.
- Artifact Entity에는 경로·URI 필드가 없으므로 Service는 Metadata만 등록한다. Resolver는 후속 범위다.
- `succeeded` 전이의 물리 Artifact checksum 검증은 Storage Resolver와 Worker 결과 검증 계층이 필요하다.
- Soft Delete 복구 History 자동 기록은 후속 Service·API 정책에서 연결한다.
