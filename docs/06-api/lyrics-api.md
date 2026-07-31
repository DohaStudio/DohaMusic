# Lyrics API

> 문서 상태: [완료]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 6 Lyrics AI

## 가사 생성

`POST /api/lyrics`는 동기적으로 Template, Mock 또는 명시 선택된 Experimental OpenAI 초안을 생성·검증·저장하고 `201 Created`를 반환한다. 기본값은 Template다.

K-POP 장르에서는 optional `generation_options`의 언어 비율 목표, Hook 문구·방식·반복과 Post-Chorus 포함 여부를 Template 지시에 반영한다. 정확한 토큰 비율이나 오디오 Hook 위치는 보장하지 않으며 unknown option은 거부한다.

```json
{
  "topic": "끝난 사랑을 기억하는 밤",
  "genre": "Korean pop ballad",
  "mood": "warm and melancholic",
  "language": "ko",
  "keywords": ["밤", "계절", "기억"],
  "structure": ["verse", "pre_chorus", "chorus", "bridge", "final_chorus"],
  "target_duration_seconds": 180,
  "additional_instructions": "표현을 간결하게",
  "allow_template_fallback": false
}
```

응답에는 ID, version·parent, title, sections, 정규화된 `full_text`, Provider·모델·버전, status, metadata와 시각이 포함된다. `metadata.capabilities.revision`은 현재 generator가 의미 기반 수정 method를 제공하는지를 나타낸다. Template·Mock은 `false`, revision adapter는 `true`이며 Frontend는 이 값이 명시적으로 `true`일 때만 수정 UI를 활성화한다. 외부 Provider는 가능한 경우 token·request count·예상 비용을 기록하며 가격 설정이 없으면 `estimated_cost=null`이다.

## 의미 기반 수정

`POST /api/lyrics/{lyrics_id}/revise`는 의미 기반 수정을 지원하는 Provider에서 원본을 덮어쓰지 않고 새 문서 버전을 반환한다.

```json
{
  "instruction": "후렴을 더 기억에 남게 수정해줘.",
  "preserve_structure": true
}
```

응답은 `parent_id`, 증가한 `version`, 수정 지시, 수정 전후 SHA-256, 실제 Provider와 모델을 포함한다. Template·Mock은 의미 기반 수정을 지원하지 않아 `LYRICS_REVISION_FAILED`다. 수정 이력이 있는 원본은 자식 버전이 남아 있는 동안 삭제할 수 없다.

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
| `LYRICS_API_KEY_MISSING` | 외부 Provider 선택 시 Key 누락 |
| `LYRICS_PROVIDER_UNAVAILABLE` | 일시적 network 또는 Provider 5xx |
| `LYRICS_RATE_LIMITED` | Provider rate limit |
| `LYRICS_TIMEOUT` | 호출 deadline 초과 |
| `LYRICS_AUTHENTICATION_FAILED` | Provider 인증 실패 |
| `LYRICS_REQUEST_REJECTED` | Provider가 요청 거부 |
| `LYRICS_CONTENT_BLOCKED` | 콘텐츠 정책 차단 또는 refusal |
| `LYRICS_COST_LIMIT_EXCEEDED` | 응답 후 계산한 예상 비용 제한 초과 |
| `LYRICS_REVISION_FAILED` | 수정 미지원 또는 수정 실패 |

지원하지 않는 Provider는 애플리케이션 시작 시 `LYRICS_PROVIDER_NOT_SUPPORTED` 설정 오류로 실패한다.
