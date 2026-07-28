# API 개요

> 문서 목적: Phase 1 REST API와 공통 계약을 정의한다.
> 현재 상태: **Backend Foundation 구현 완료**

기본 prefix는 `/api`다. 현재 인증과 사용자 소유권 검사는 구현하지 않았다. OpenAPI 문서는 서버 실행 후 `/docs`, 스키마는 `/openapi.json`에서 확인할 수 있다.

| 메서드 | 경로 | 성공 응답 | 설명 |
|---|---|---:|---|
| `GET` | `/health` | 200 | 애플리케이션 상태 확인 |
| `POST` | `/api/generations` | 202 | Mock 생성 Job 생성 |
| `GET` | `/api/generations/{id}` | 200 | Job 상태 조회 |
| `GET` | `/api/generations/{id}/files` | 200 | Job 결과 파일 메타데이터 조회 |
| `POST` | `/api/voice-profiles` | 201 | 동의가 확인된 음성 프로필 메타데이터 생성 |
| `DELETE` | `/api/voice-profiles/{id}` | 204 | 음성 프로필 삭제 |

생성 요청은 비동기이며 `202 Accepted`와 `PENDING` Job을 반환한다. 오류는 다음 형식을 사용한다.

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Generation job을(를) 찾을 수 없습니다."
  }
}
```

인증, 모델 목록, 업로드/다운로드, 취소, 재시도 API는 후속 단계 범위다.
