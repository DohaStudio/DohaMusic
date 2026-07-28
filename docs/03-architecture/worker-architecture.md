# Worker 아키텍처

> 문서 목적: 현재 작업 실행 구조와 실제 AI 경계를 정의한다.
> 현재 상태: **단일 ThreadPool + Provider-neutral Worker 구현**

API는 Job을 `PENDING`으로 저장하고 `ThreadPoolExecutor`에 ID만 제출한다. `GenerationWorker`는 `VALIDATING`과 `GENERATING` 상태를 거쳐 구성된 `MusicGenerator`를 호출하고, 결과 파일을 등록한 뒤 `COMPLETED`로 전환한다. 모델 오류는 안정적인 `AI_*` 코드로 `FAILED`에 기록한다.

Mock은 프로세스 내부에서 동작한다. ACE-Step은 충돌 가능한 PyTorch 의존성과 VRAM 해제를 격리하기 위해 작업마다 별도 subprocess로 실행한다. 실제 3회 실행에서 프로세스 종료 후 다음 작업이 성공했으나, 상주 모델 재사용·동시 실행·취소·재시도·프로세스 장애 복구는 검증하지 않았다. GPU Worker 동시성은 1만 허용하는 것이 현재 안전 기준이다.

외부 Queue, Redis, Celery와 다중 GPU Worker는 범위 밖이다. 격리 결정은 [ADR-005](../11-decisions/ADR-005-ai-worker-dependency-isolation.md)를 따른다.
