# 생성 API

> 문서 목적: Mock 음악 생성 Job의 생성·조회·파일 목록 계약을 정의한다.
> 현재 상태: **Phase 1 구현 완료**

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

성공 시 `202`와 Job 전체 정보를 반환한다. 최초 상태는 `PENDING`이며 내부 Mock Worker가 비동기로 처리한다.

## Job 조회

`GET /api/generations/{id}`

응답에는 `id`, `status`, 입력 스냅샷, `current_step`, 오류 정보, 생성·수정·완료 시각이 포함된다.

## 결과 파일 조회

`GET /api/generations/{id}/files`

완료 후 `id`, `job_id`, `file_type`, `file_path`, `mime_type`, `created_at`을 가진 배열을 반환한다. Phase 1은 파일 메타데이터만 제공하며 다운로드 API는 제공하지 않는다.
