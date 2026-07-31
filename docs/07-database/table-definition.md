# 테이블 정의

> 문서 목적: 현재 실제 테이블의 책임과 필드를 정의한다.
> 현재 상태: **구현 완료**

모든 ID는 애플리케이션에서 생성하는 UUID 문자열이다. 시각은 UTC 기준으로 기록한다.

## `lyrics_documents`

| 필드 | 타입 | Null | 설명 |
|---|---|---|---|
| `id` | varchar(36) | 아니요 | 기본키 |
| `parent_id` | varchar(36) | 예 | 직전 원본 `lyrics_documents.id`, self FK·인덱스 |
| `version` | integer | 아니요 | 원본 1부터 증가하는 버전 |
| `revision_instruction` | text | 예 | 정규화된 수정 지시 |
| `source_hash`, `result_hash` | varchar(64) | 예 | 수정 전후 SHA-256; 원본은 result만 기록 |
| `title` | varchar(300) | 예 | Provider가 제안한 제목 |
| `language` | varchar(10) | 아니요 | `ko` 또는 `en`, 인덱스 |
| `topic` | text | 아니요 | 정규화된 생성 주제 |
| `genre`, `mood` | varchar(100) | 예 | 선택 입력 |
| `keywords` | json | 아니요 | 정규화된 keyword 배열 |
| `structure` | json | 아니요 | 생성 section 순서 |
| `sections` | json | 아니요 | section type과 line 배열 |
| `full_text` | text | 아니요 | 정규화된 전체 가사 |
| `provider` | varchar(50) | 아니요 | `template`, `mock` 또는 `openai`, 인덱스 |
| `model_name` | varchar(100) | 아니요 | Provider 구현 식별자 |
| `model_version` | varchar(100) | 예 | Provider 버전 |
| `status` | varchar(32) | 아니요 | `GENERATED` 또는 `REVISED`, 인덱스 |
| `metadata` | json | 아니요 | 구조·통계·시간·경고 |
| `created_at`, `updated_at` | datetime | 아니요 | UTC 시각 |

Alembic 0006이 수정 이력 필드를 추가한다. 원본은 덮어쓰지 않으며 자식이 있는 원본 삭제를 거부한다. 외부 호출은 전체 5초 deadline으로 제한한다. 더 긴 외부 LLM 비동기 처리 도입 시 generation job과 상태 모델을 별도로 추가한다.

## `projects`와 History

| 필드 | 타입 | Null | 설명 |
|---|---|---|---|
| `id` | varchar(36) | 아니요 | 기본키 |
| `title` | varchar(200) | 아니요 | Project 표시 이름, 검색 인덱스 |
| `description` | text | 예 | Project 설명 |
| `is_default` | boolean | 아니요 | Pipeline 자동 연결 기본 Project |
| `created_at`, `updated_at` | datetime | 아니요 | UTC 시각 |

Alembic 0008은 `pipeline_jobs.project_id` nullable FK와 인덱스를 추가하고 기존 Job을 `Default Project`에 연결한다. History는 별도 테이블이 아니라 Pipeline Job·Voice Profile·최종 File을 조합한 공개 projection이다. Project 삭제 시 FK를 `NULL`로 해제하고 Job과 Storage 파일은 유지한다.

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
| `display_filename` | varchar(255) | 예 | 공개 표시용 sanitize 파일명; legacy null |
| `mime_type` | varchar(100) | 예 | 검증된 upload MIME |
| `size_bytes` | bigint | 예 | upload byte 크기 |
| `duration_seconds` | float | 예 | WAV 길이 |
| `sample_rate` | integer | 예 | WAV sample rate |
| `channels` | integer | 예 | 1 또는 2 |
| `status` | varchar(20) | 아니요 | 현재 `READY` |
| `quality_warnings` | json | 아니요 | 품질 warning code 배열 |
| `consent_text_version` | varchar(50) | 예 | 확인한 동의문 버전 |
| `consent_confirmed_at` | datetime | 예 | 동의 확인 시각 |
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
