# 작업 상태 모델

> 문서 목적: Phase 1 생성 Job의 유효 상태 전이를 정의한다.
> 현재 상태: **구현 완료**

```mermaid
stateDiagram-v2
  [*] --> PENDING
  PENDING --> VALIDATING
  PENDING --> FAILED
  VALIDATING --> GENERATING
  VALIDATING --> FAILED
  GENERATING --> COMPLETED
  GENERATING --> FAILED
  COMPLETED --> [*]
  FAILED --> [*]
```

| 상태 | 의미 | `current_step` 예시 |
|---|---|---|
| `PENDING` | DB에 저장되어 Worker 실행을 기다림 | `queued` |
| `VALIDATING` | Worker가 입력과 실행 전제조건 확인 | `validating` |
| `GENERATING` | `MusicGenerator` 구현 실행 중 | `generating` |
| `COMPLETED` | 파일 메타데이터 저장까지 완료 | `completed` |
| `FAILED` | 예외와 오류 코드를 기록하고 종료 | `failed` |

허용되지 않은 상태 전이는 Repository에서 거부한다. `COMPLETED`와 `FAILED`는 종료 상태이며 `completed_at`을 기록한다.

취소, 재시도, 음악 생성 이후 세부 AI 파이프라인 상태는 Phase 1에 포함되지 않는다. 실제 파이프라인 도입 시 기존 상태의 API 호환성을 검토하고 ADR 및 마이그레이션과 함께 확장한다.
