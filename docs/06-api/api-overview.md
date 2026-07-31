# API 개요

> 문서 목적: 구현된 REST API와 공통 계약을 정의한다.
> 현재 상태: **Backend Foundation + Stem + Voice Conversion + Pipeline + Lyrics API 구현 완료**

기본 prefix는 `/api`다. 현재 인증과 사용자 소유권 검사는 구현하지 않았다. OpenAPI 문서는 서버 실행 후 `/docs`, 스키마는 `/openapi.json`에서 확인할 수 있다.

| 메서드 | 경로 | 성공 응답 | 설명 |
|---|---|---:|---|
| `GET` | `/health` | 200 | 애플리케이션 상태 확인 |
| `POST` | `/api/generations` | 202 | Mock 생성 Job 생성 |
| `GET` | `/api/generations/{id}` | 200 | Job 상태 조회 |
| `GET` | `/api/generations/{id}/files` | 200 | Job 결과 파일 메타데이터 조회 |
| `POST` | `/api/stems` | 202 | 생성 파일 기반 Stem 분리 Job 생성 |
| `GET` | `/api/stems/{job}` | 200 | Stem Job 상태 조회 |
| `GET` | `/api/stems/{job}/files` | 200 | vocals·instrumental·metadata 조회 |
| `POST` | `/api/voice-profiles` | 201 | 동의가 확인된 음성 프로필 메타데이터 생성 |
| `POST` | `/api/voice-profiles/upload` | 201 | 동의된 WAV를 검증·저장하고 Profile 생성 |
| `GET` | `/api/voice-profiles` | 200 | 공개 Voice Profile 목록 |
| `GET` | `/api/voice-profiles/{id}` | 200 | 공개 Voice Profile 상세 |
| `DELETE` | `/api/voice-profiles/{id}` | 204 | 음성 프로필 삭제 |
| `POST` | `/api/voice-conversion` | 202 | vocals와 동의된 Voice Profile로 변환 Job 생성 |
| `GET` | `/api/voice-conversion/{job}` | 200 | Voice Conversion Job 조회 |
| `GET` | `/api/voice-conversion/{job}/files` | 200 | converted_voice·metadata 조회 |
| `POST` | `/api/pipelines` | 202 | Mock AI·Default Audio Mixer Pipeline Job 생성 |
| `GET` | `/api/pipelines/{job}` | 200 | 단계·진행률·metadata 조회 |
| `GET` | `/api/pipelines/{job}/files` | 200 | Pipeline 결과 파일 metadata 조회 |
| `POST` | `/api/lyrics` | 201 | Template·Mock 가사 초안 생성·저장 |
| `GET` | `/api/lyrics/{id}` | 200 | 가사 문서 조회 |
| `POST` | `/api/lyrics/validate` | 200 | 직접 작성 가사 정규화·검증 |
| `DELETE` | `/api/lyrics/{id}` | 204 | 가사 문서 삭제 |

생성, Stem, Voice, Pipeline 요청은 비동기이며 `202 Accepted`와 `PENDING` Job을 반환한다. Lyrics는 빠른 로컬 Provider를 사용하는 동기 `201` API다. Pipeline 계약은 [Pipeline API](pipeline-api.md), 가사 계약은 [Lyrics API](lyrics-api.md)를 따른다. 오류는 다음 형식을 사용한다.

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Generation job을(를) 찾을 수 없습니다."
  }
}
```

Pipeline 결과 WAV의 content/download는 제공한다. 인증, 모델 목록, 업로드, 취소, 재시도와 개별 생성 모듈 download API는 후속 단계 범위다.
