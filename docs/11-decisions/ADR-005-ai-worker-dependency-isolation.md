# ADR-005: AI Worker 의존성 격리

> 문서 목적: 실제 AI 런타임을 Backend 환경에서 분리하는 결정을 기록한다.
> 상태: **승인**
> 결정일: 2026-07-29
> 관련 작업: Phase 2 ACE-Step 로컬 추론 검증

## 배경과 문제

ACE-Step 공식 환경은 고정된 CUDA PyTorch·TorchAudio·TorchVision과 다수의 모델 의존성을 요구한다. Backend는 FastAPI·SQLAlchemy 중심의 가벼운 환경이며, 두 환경을 합치면 버전 충돌, 설치 용량 증가, 선택 모델이 없는 개발자의 실행 실패와 GPU 메모리 회수 불확실성이 생긴다.

## 결정

실제 AI Provider는 자체 Python 환경과 공식 모델 checkout을 사용한다. Backend Adapter는 공통 JSON 계약으로 runner subprocess를 호출하고 WAV·metadata 결과를 받는다. Backend import와 애플리케이션 시작은 AI 패키지를 import하거나 모델을 다운로드·로드하지 않는다.

Phase 2 ACE-Step 구현은 작업마다 subprocess를 생성하고 종료한다. Provider 선택, 실행 파일·checkout·checkpoint·variant·버전·장치·양자화·offload는 환경 변수로 주입한다.

## 선택 이유

- 공식 lockfile을 그대로 사용할 수 있다.
- Backend 테스트와 Mock 실행이 GPU·모델 설치 없이 유지된다.
- 모델 오류와 VRAM 수명이 subprocess 경계에 격리된다.
- 후속 Adapter도 공통 Backend 계약을 유지하며 다른 런타임을 가질 수 있다.

## 검토한 대안

- 단일 Python 환경: 배포는 단순하지만 충돌과 설치 부담이 커서 제외했다.
- HTTP AI microservice: 격리는 강하지만 운영·보안·배포 범위를 이번 단계보다 크게 확장해 보류했다.
- 프로세스 내부 lazy import: 시작 실패는 줄지만 의존성 충돌과 VRAM 수명 문제를 해결하지 못한다.
- 상주 subprocess: 로드 시간은 줄지만 재사용·누수·취소·장애 복구가 미검증이라 보류했다.

## 장단점과 영향

Backend 안정성과 선택 설치성이 높아지고 오류 경계가 명확해진다. 반면 직렬화·프로세스 관리가 필요하고, 현재는 작업마다 약 34~42초의 모델 로드 비용이 발생한다. 로컬 절대 경로와 입력은 로그에 남기지 않으며 임시 요청 JSON은 호출 후 삭제한다.

## 재검토와 마이그레이션

수동 품질 평가를 통과하고 반복 작업 처리량이 필요해지면 상주 subprocess 또는 별도 AI service를 비교 벤치마크한다. 변경 시 프로세스 재시작, timeout, cancellation, health, 동시성, VRAM 누수를 먼저 검증하고 대체 ADR을 작성한다.

관련 구현·실험은 [EXP-001](../../reports/experiments/EXP-001-ace-step-local-inference.md)과 develop 대상 Phase 2 PR에서 추적한다.
