# 모델 로딩 전략

> 문서 목적: 제한된 VRAM에서 모델 생명주기와 의존성 경계를 정의한다.
> 현재 상태: **ACE-Step·Demucs Job별 격리 subprocess 유지 결정**

ACE-Step 실험은 Job마다 격리 subprocess를 생성하고, 공식 `AceStepHandler.initialize_service`로 2B Turbo DiT를 로드한 뒤 한 곡을 생성하고 프로세스를 종료한다. LM은 비활성화했다. 이 방식은 Backend 의존성 충돌과 작업 간 VRAM 잔류를 줄이고 실패를 격리하지만, 매 작업 34~42초의 모델 로드 비용과 약 13GB의 최대 process RSS를 만든다.

현재 설정은 INT8 weight-only, CPU offload, DiT CPU offload, batch 1, compile 비활성화다. 상주 suite 12회는 모두 성공했고 warm 추론은 약 12초대로 줄었지만 6회 동안 process RSS가 약 14.2GiB 증가했다. 안정성 우선 원칙에 따라 Job별 subprocess 종료를 유지한다. 상주 방식은 원인 분석과 최소 20회 soak test 후 재검토한다. [ADR-007](../11-decisions/ADR-007-ace-step-runtime-lifecycle.md)을 따른다.

Demucs 4.1.0도 실제 Stem Job마다 격리 Python에서 HTDemucs를 load하고 한 입력을 분리한 뒤 종료한다. 3회 기준 load 평균 1.648초, subprocess 전체 평균 9.381초로 확인됐다. 모델 cache는 로컬 사전 설치 경로만 사용하고 `HF_HUB_OFFLINE=1`을 강제한다. 상주 전환은 처리량 요구와 반복 memory 검증 후 별도 ADR로 결정한다.
