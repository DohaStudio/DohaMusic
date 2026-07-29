# Pipeline 테이블

> 문서 상태: [완료]
> 최종 수정일: 2026-07-29
> migration: `20260729_0004`

## `pipeline_jobs`

| 필드 | 설명 |
|---|---|
| `id` | UUID 기본키 |
| `voice_profile_id` | 동의된 `voice_profiles.id`, 삭제 제한 |
| `status`, `current_step`, `progress_percent` | 상태·단계·0~100 진행률 |
| `prompt`, `lyrics`, `genre`, `duration_seconds`, `seed` | Pipeline 요청 |
| `pipeline_version` | metadata 계약 버전 |
| `result_metadata` | Provider·단계 시간·attempt·benchmark·오류 JSON |
| `failed_step`, `error_code`, `error_message` | 실패 귀속과 안전한 오류 |
| `created_at`, `updated_at`, `completed_at` | UTC 작업 시각 |

## `pipeline_files`

| 필드 | 설명 |
|---|---|
| `id` | UUID 기본키 |
| `job_id` | `pipeline_jobs.id`, Job 삭제 시 cascade |
| `file_type` | `music`, `vocals`, `instrumental`, `converted_voice`, `final`, `metadata` |
| `file_path` | Storage 루트 기준 상대 경로 |
| `mime_type` | `audio/wav` 또는 `application/json` |
| `created_at` | UTC 생성 시각 |

실패 작업은 부분 오디오를 제거하고 진단용 `metadata` 파일만 등록한다.
