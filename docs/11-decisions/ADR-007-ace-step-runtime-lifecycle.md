# ADR-007: ACE-Step 런타임 생명주기

> 상태: **채택됨**
> 작성일: 2026-07-29
> 최종 수정일: 2026-07-29
> 관련 작업: Phase 2.5 반복 추론·메모리 평가

## 배경과 문제

작업별 subprocess는 모델 로드 비용이 크다. 상주 프로세스는 warm 추론을 약 12초대로 줄일 수 있지만 제한된 GPU·32GB RAM에서 누적 자원과 장애 격리가 안전해야 한다.

## 결정

현재 로컬 Backend Adapter는 **Job마다 격리 subprocess를 생성하고 작업 후 종료**하는 방식을 유지한다. 상주 Worker는 도입하지 않는다. GPU 동시성은 1을 유지한다.

## 선택 이유

- 작업별 방식은 EXP-001에서 독립 3회와 Backend Job 성공, 종료 후 GPU 회수를 확인했다.
- 상주 방식은 두 suite 총 12/12 성공하고 warm 속도 이점이 있었다.
- 보완 상주 suite에서 GPU allocation은 안정적이었지만 process RSS가 첫 run 직후 7,640.25MiB에서 여섯 번째 직후 21,879.38MiB로 증가했다.
- 시스템 사용 메모리가 30,976.02MiB까지 올라 32GB 호스트의 안정성 여유가 부족했다.
- 정확한 원인이 미확정이므로 처리량보다 장애·자원 격리를 우선한다.

## 대안

- Worker 수명 동안 상주: 빠르지만 현재 CPU 메모리 증가로 보류한다.
- 일정 작업 수마다 recycle: 완화 가능하지만 안전한 작업 수 근거가 없어 보류한다.
- 별도 장기 실행 AI service: health·queue·cancellation·배포 범위가 커 후속 검토한다.
- 수동 warm-up: 로컬 개발 편의는 있으나 운영 복구 계약이 없어 제외한다.

## 장단점과 영향

장점은 Job 단위 오류 격리, 모델 의존성 분리, 프로세스 종료 기반 CPU/GPU 회수다. 단점은 cold load로 첫 응답이 느리고 디스크·CPU load가 반복되는 점이다. API의 비동기 Job 계약은 변하지 않는다.

## 마이그레이션

기존 `SubprocessAceStepRuntime`을 그대로 유지하므로 마이그레이션은 없다. 상주 방식을 도입할 때는 별도 runtime 구현 뒤 동일 Adapter Protocol에 주입하고 기존 방식을 fallback으로 남긴다.

## 재검토 조건

- CPU RSS 증가 원인 확인과 명시적 정리 경로 검증
- 최소 20회 soak test에서 RSS·VRAM 안정
- crash·timeout·cancellation·health·자동 recycle 검증
- cold load와 처리량 요구가 안정성 비용을 정당화함

근거는 [EXP-002](../../reports/experiments/EXP-002-ace-step-quality-and-stability.md)와 develop 대상 Phase 2.5 PR에서 추적한다.
