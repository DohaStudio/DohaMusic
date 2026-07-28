# 모델 로딩 전략

> 문서 목적: 제한된 VRAM에서 모델 생명주기와 의존성 경계를 정의한다.
> 현재 상태: **ACE-Step 실험 전략 검증 / 운영 전략 미확정**

ACE-Step 실험은 Job마다 격리 subprocess를 생성하고, 공식 `AceStepHandler.initialize_service`로 2B Turbo DiT를 로드한 뒤 한 곡을 생성하고 프로세스를 종료한다. LM은 비활성화했다. 이 방식은 Backend 의존성 충돌과 작업 간 VRAM 잔류를 줄이고 실패를 격리하지만, 매 작업 34~42초의 모델 로드 비용과 약 13GB의 최대 process RSS를 만든다.

현재 설정은 INT8 weight-only, CPU offload, DiT CPU offload, batch 1, compile 비활성화다. 실제 두 번째 독립 실행과 Backend 실행이 성공해 종료 후 재실행 가능성은 확인했지만 상주 Worker 재사용, warm cache, 병렬 모델 적재는 검증하지 않았다. 품질 수동 평가와 반복 벤치마크 후에만 운영 생명주기를 ADR로 확정한다.
