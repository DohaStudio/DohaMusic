# Backend 아키텍처

> 문서 목적: FastAPI 기반 API와 Orchestrator의 책임 경계를 정의한다.
> 현재 상태: **설계 초안**

계층은 API Router, Application Service, Domain, Repository/Adapter로 분리한다. Router는 인증·직렬화, Service는 유스케이스와 트랜잭션, Domain은 상태 전이 규칙, Adapter는 DB·큐·파일 저장소 연결을 담당한다.

생성 요청은 입력·동의·할당량을 검증해 DB에 작업과 요청 스냅샷을 한 트랜잭션으로 기록한다. HTTP 요청에서 모델 추론을 실행하지 않는다. 멱등성 키와 사용자 소유권 검사를 적용하며 오류 규격은 [오류 코드](../06-api/error-codes.md)를 따른다.
