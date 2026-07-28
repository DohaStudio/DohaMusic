# API 개요

> 문서 목적: MVP REST API 자원, 공통 규칙과 보안 경계를 정의한다.
> 현재 상태: **설계 초안 / 미구현**

기본 prefix는 `/api/v1`을 제안한다. 모든 사용자 자원은 인증과 소유권 검사를 거친다. 생성 요청은 비동기이며 `202 Accepted`와 작업 ID를 반환한다.

| 영역 | 예시 경로 | 문서 |
|---|---|---|
| 생성 | `POST /generation-requests` | [생성 API](generation-api.md) |
| 작업 | `GET /jobs/{job_id}` | [작업 API](job-api.md) |
| 모델 | `GET /models` | [모델 API](model-api.md) |
| 오디오 | `POST /voice-samples`, `GET /files/{file_id}` | [오디오 API](audio-api.md) |

오류는 안정적인 `code`, 사용자용 `message`, 추적용 `request_id`, 선택적 `details`를 반환한다. 정확한 스키마와 인증 방식은 구현 전에 OpenAPI에서 확정한다.
