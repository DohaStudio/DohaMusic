# Lyrics API

> 문서 상태: [완료]
> 최종 수정일: 2026-07-29
> 관련 기능: Phase 6 Lyrics AI

## 가사 생성

`POST /api/lyrics`는 동기적으로 Template 또는 Mock 초안을 생성·검증·저장하고 `201 Created`를 반환한다.

```json
{
  "topic": "끝난 사랑을 기억하는 밤",
  "genre": "Korean pop ballad",
  "mood": "warm and melancholic",
  "language": "ko",
  "keywords": ["밤", "계절", "기억"],
  "structure": ["verse", "pre_chorus", "chorus", "bridge", "final_chorus"],
  "target_duration_seconds": 180,
  "additional_instructions": "표현을 간결하게"
}
```

응답에는 ID, title, 요청 정보, sections, 정규화된 `full_text`, Provider·모델·버전, status, metadata와 시각이 포함된다. Token·비용은 외부 LLM을 사용하지 않으므로 기록하지 않는다.

## 조회·삭제

- `GET /api/lyrics/{lyrics_id}`: 저장된 가사 문서 조회
- `DELETE /api/lyrics/{lyrics_id}`: 가사 문서와 metadata 영구 삭제, 성공 시 `204`

현재 인증·소유권은 미구현이므로 운영 배포 전 사용자별 접근 제어와 보존 정책이 필요하다.

## 직접 작성 가사 검증

`POST /api/lyrics/validate`는 문서를 저장하지 않고 정규화된 가사, section 목록, 경고·오류, 글자·줄·section 수와 최대 동일 문장 반복률을 반환한다.

```json
{
  "raw_lyrics": "[Verse]\n밤을 걷는다\n\n[Chorus]\n기억해",
  "language": "ko"
}
```

경고는 사용할 수 있지만 품질 검토가 필요한 결과다. 오류가 있으면 응답의 `valid=false`다. 요청 Schema 자체가 잘못되면 `422 INVALID_INPUT`이다.

## 오류

| 코드 | 조건 |
|---|---|
| `INVALID_INPUT` | Schema 길이·언어·structure 제한 위반 |
| `RESOURCE_NOT_FOUND` | 가사 ID 없음 |
| `LYRICS_VALIDATION_FAILED` | Service 검증을 진행할 수 없는 가사 입력 |
| `LYRICS_GENERATION_FAILED` | Provider 실행 실패 |
| `LYRICS_OUTPUT_INVALID` | Provider 결과 검증 실패 |

지원하지 않는 Provider는 애플리케이션 시작 시 `LYRICS_PROVIDER_NOT_SUPPORTED` 설정 오류로 실패한다.
