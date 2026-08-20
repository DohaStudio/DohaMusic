# Phase 4: API 구축

> 문서 상태: [보관]
> 분류: [HISTORICAL / Authority 아님]
> 보관 사유: 초기 API 계획이 현재 실행 로드맵과 API 계약으로 대체됐다.
> 대체 문서: [실행 로드맵](../../ROADMAP.md), [API 개요](../../docs/06-api/api-overview.md)
> Archived at: 2026-08-20

> 문서 목적: 비동기 파이프라인을 안전한 서비스 API로 노출하는 계획을 정의한다.
> 현재 상태: **계획**

- 인증·소유권과 생성 요청 검증
- 작업 조회·취소·재시도 API
- 음성 업로드·프로필·동의·삭제 API
- 결과 접근과 모델 capability API
- OpenAPI, 오류 코드, 멱등성, 통합 테스트

[인수 기준](../../docs/02-requirements/acceptance-criteria.md)을 모두 통과하고 민감 오류·경로가 노출되지 않으면 완료한다.
