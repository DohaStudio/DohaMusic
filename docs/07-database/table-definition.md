# 테이블 정의

> 문서 목적: 현재 실제 테이블의 책임과 필드를 정의한다.
> 현재 상태: **구현 완료**

모든 ID는 애플리케이션에서 생성하는 UUID 문자열이다. 시각은 UTC 기준으로 기록한다.

## `lyrics_documents`

| 필드 | 타입 | Null | 설명 |
|---|---|---|---|
| `id` | varchar(36) | 아니요 | 기본키 |
| `title` | varchar(300) | 예 | Provider가 제안한 제목 |
| `language` | varchar(10) | 아니요 | `ko` 또는 `en`, 인덱스 |
| `topic` | text | 아니요 | 정규화된 생성 주제 |
| `genre`, `mood` | varchar(100) | 예 | 선택 입력 |
| `keywords` | json | 아니요 | 정규화된 keyword 배열 |
| `structure` | json | 아니요 | 생성 section 순서 |
| `sections` | json | 아니요 | section type과 line 배열 |
| `full_text` | text | 아니요 | 정규화된 전체 가사 |
| `provider` | varchar(50) | 아니요 | `template` 또는 `mock`, 인덱스 |
| `model_name` | varchar(100) | 아니요 | Provider 구현 식별자 |
| `model_version` | varchar(100) | 예 | Provider 버전 |
| `status` | varchar(32) | 아니요 | 현재 `GENERATED`, 인덱스 |
| `metadata` | json | 아니요 | 구조·통계·시간·경고 |
| `created_at`, `updated_at` | datetime | 아니요 | UTC 시각 |

빠른 로컬 Provider를 동기 실행하므로 `lyrics_generation_jobs`는 만들지 않았다. 외부 LLM 비동기 처리 도입 시 migration과 상태 모델을 별도로 추가한다.

## `generation_jobs`

| 필드 | 타입 | Null | 설명 |
|---|---|---|---|
| `id` | varchar(36) | 아니요 | 기본키 |
| `status` | varchar(32) | 아니요 | Job 상태, 인덱스 |
| `prompt` | text | 아니요 | 생성 프롬프트 |
| `lyrics` | text | 예 | 선택 가사 |
| `genre` | varchar(100) | 예 | 선택 장르 |
| `duration_seconds` | integer | 아니요 | 요청 길이 |
| `seed` | integer | 예 | 선택 시드 |
| `current_step` | varchar(100) | 아니요 | 현재 단계 설명 |
| `error_code` | varchar(100) | 예 | 실패 코드 |
| `error_message` | text | 예 | 실패 메시지 |
| `created_at` | datetime | 아니요 | 생성 시각 |
| `updated_at` | datetime | 아니요 | 수정 시각 |
| `completed_at` | datetime | 예 | 완료 또는 실패 시각 |

## `generated_files`

| 필드 | 타입 | Null | 설명 |
|---|---|---|---|
| `id` | varchar(36) | 아니요 | 기본키 |
| `job_id` | varchar(36) | 아니요 | `generation_jobs.id`, 인덱스 |
| `file_type` | varchar(50) | 아니요 | 산출물 유형 |
| `file_path` | varchar(500) | 아니요 | Storage 루트 기준 상대 경로 |
| `mime_type` | varchar(100) | 아니요 | MIME |
| `created_at` | datetime | 아니요 | 생성 시각 |

## `voice_profiles`

| 필드 | 타입 | Null | 설명 |
|---|---|---|---|
| `id` | varchar(36) | 아니요 | 기본키 |
| `name` | varchar(100) | 아니요 | 프로필 이름 |
| `reference_file_path` | varchar(500) | 아니요 | 참조 파일 경로 메타데이터 |
| `consent_confirmed` | boolean | 아니요 | 명시적 동의 확인 |
| `created_at` | datetime | 아니요 | 생성 시각 |
| `updated_at` | datetime | 아니요 | 수정 시각 |

## `stem_jobs`

| 필드 | 타입 | Null | 설명 |
|---|---|---|---|
| `id` | varchar(36) | 아니요 | 기본키 |
| `source_file_id` | varchar(36) | 아니요 | 입력 `generated_files.id`, 인덱스 |
| `status` | varchar(32) | 아니요 | Job 상태, 인덱스 |
| `current_step` | varchar(100) | 아니요 | 현재 단계 |
| `provider` | varchar(50) | 예 | 완료 Provider |
| `model_name` | varchar(100) | 예 | 완료 모델 |
| `model_version` | varchar(100) | 예 | 완료 모델 버전 |
| `error_code` | varchar(100) | 예 | 안전한 실패 코드 |
| `error_message` | text | 예 | 일반 사용자 메시지 |
| `created_at` | datetime | 아니요 | 생성 시각 |
| `updated_at` | datetime | 아니요 | 수정 시각 |
| `completed_at` | datetime | 예 | 완료 또는 실패 시각 |

## `stem_files`

| 필드 | 타입 | Null | 설명 |
|---|---|---|---|
| `id` | varchar(36) | 아니요 | 기본키 |
| `job_id` | varchar(36) | 아니요 | `stem_jobs.id`, 인덱스 |
| `file_type` | varchar(50) | 아니요 | `vocals`, `instrumental`, `metadata` |
| `file_path` | varchar(500) | 아니요 | Storage 루트 기준 상대 경로 |
| `mime_type` | varchar(100) | 아니요 | MIME |
| `created_at` | datetime | 아니요 | 생성 시각 |
