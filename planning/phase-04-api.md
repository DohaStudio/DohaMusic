# Phase 4: API 구축

> 분류: [SUPERSEDED]
> 현재 기준: [실행 로드맵](../ROADMAP.md), [API 개요](../docs/06-api/api-overview.md)
> 안내: 초기 API 계획 이력으로 보존하며 현재 Endpoint·상태 기준으로 사용하지 않는다.

> 문서 목적: 비동기 파이프라인을 안전한 서비스 API로 노출하는 계획을 정의한다.
> 현재 상태: **계획**

- 인증·소유권과 생성 요청 검증
- 작업 조회·취소·재시도 API
- 음성 업로드·프로필·동의·삭제 API
- 결과 접근과 모델 capability API
- OpenAPI, 오류 코드, 멱등성, 통합 테스트

[인수 기준](../docs/02-requirements/acceptance-criteria.md)을 모두 통과하고 민감 오류·경로가 노출되지 않으면 완료한다.
