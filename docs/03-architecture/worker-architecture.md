# Worker 아키텍처

> 문서 목적: 현재 작업 실행 구조와 실제 AI 경계를 정의한다.
> 현재 상태: **단일 ThreadPool + Provider-neutral Worker 구현**

API는 Job을 `PENDING`으로 저장하고 `ThreadPoolExecutor`에 ID만 제출한다. `GenerationWorker`는 `VALIDATING`과 `GENERATING` 상태를 거쳐 구성된 `MusicGenerator`를 호출하고, 결과 파일을 등록한 뒤 `COMPLETED`로 전환한다. 모델 오류는 안정적인 `AI_*` 코드로 `FAILED`에 기록한다.

Mock은 프로세스 내부에서 동작한다. ACE-Step은 충돌 가능한 PyTorch 의존성과 자원 해제를 격리하기 위해 작업마다 별도 subprocess로 실행한다. Phase 2.5의 상주 6회 suite 2개는 12/12 성공하고 warm 요청이 빨랐지만 보완 suite의 process RSS가 첫 run 직후 7,640.25MiB에서 마지막 직후 21,879.38MiB로 증가했다. 현재는 Job별 subprocess 종료를 자원 회수와 장애 복구 경계로 사용하며 GPU Worker 동시성은 1이다.

외부 Queue, Redis, Celery와 다중 GPU Worker는 범위 밖이다. 의존성 격리는 [ADR-005](../11-decisions/ADR-005-ai-worker-dependency-isolation.md), 수명 결정은 [ADR-007](../11-decisions/ADR-007-ace-step-runtime-lifecycle.md)을 따른다.
