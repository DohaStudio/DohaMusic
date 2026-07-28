# 테이블 정의

> 문서 목적: 현재 실제 테이블의 책임과 필드를 정의한다.
> 현재 상태: **구현 완료**

모든 ID는 애플리케이션에서 생성하는 UUID 문자열이다. 시각은 UTC 기준으로 기록한다.

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
