# 배포 아키텍처

> 문서 목적: 개발·향후 운영 환경의 배치 경계와 비밀·GPU 요구를 정의한다.
> 현재 상태: **향후 설계 / 배포 미실행**

초기 로컬 환경은 Web, API, Worker, Database, Audio Storage를 한 개발 머신에 둘 수 있으나 프로세스와 설정은 분리한다. Worker만 GPU에 접근한다. 운영 전환 시 API/Worker 분리, 객체 저장소, 관리형 DB, Redis 큐, TLS, 중앙 비밀 저장소와 모니터링을 검토한다.

이번 단계에는 컨테이너 실행이나 운영 배포가 포함되지 않는다. 운영 절차는 [배포 가이드](../10-operations/deployment-guide.md)에 승인 게이트로 기록한다.
