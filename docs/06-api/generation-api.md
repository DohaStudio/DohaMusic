# 생성 API

> 문서 목적: 음악 생성 Job의 생성·조회·파일 목록 계약을 정의한다.
> 현재 상태: **Mock 기본 / ACE-Step 선택적 Provider**

## 생성 요청

`POST /api/generations`

```json
{
  "prompt": "잔잔한 피아노 음악",
  "lyrics": null,
  "genre": "ambient",
  "duration_seconds": 30,
  "seed": 42
}
```

| 필드 | 필수 | 제약 |
|---|---|---|
| `prompt` | 예 | 1~4,000자 |
| `lyrics` | 아니요 | 최대 20,000자 |
| `genre` | 아니요 | 최대 100자 |
| `duration_seconds` | 아니요 | 1~600, 기본값 30 |
| `seed` | 아니요 | 0~2,147,483,647 |

성공 시 `202`와 Job 전체 정보를 반환한다. 최초 상태는 `PENDING`이며 내부 Worker가 비동기로 처리한다. 기본 Provider는 Mock이고 서버 환경에서 `ace_step`을 선택한 경우 같은 API 계약으로 실제 Adapter가 실행된다. 요청에서 Provider를 임의 선택하는 기능은 없다.

## Job 조회

`GET /api/generations/{id}`

응답에는 `id`, `status`, 입력 스냅샷, `current_step`, 오류 정보, 생성·수정·완료 시각이 포함된다.

## 결과 파일 조회

`GET /api/generations/{id}/files`

완료 후 공개 파일 식별 metadata를 반환하고 내부 DB의 `file_path`는 public HTTP response에 포함하지 않는다. Mock 결과는 `mock_audio`, ACE-Step 결과는 `generated_audio`다. 이번 content·download 제공 범위는 완료 Pipeline 결과이며 Generation 개별 파일 capability는 계속 `false`다.
