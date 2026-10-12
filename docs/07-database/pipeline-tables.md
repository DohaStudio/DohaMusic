# Pipeline 테이블

> 문서 상태: [완료: CURRENT Runtime]
> 문서 범위: 운영 source of truth인 Pipeline 2개 Table
> 최종 수정일: 2026-10-12
> migration: `20260729_0004`, `20260731_0009`
> 관련 문서: [Database Overview](database-overview.md), [CURRENT Runtime ERD](erd.md), [CURRENT Runtime Core Table Definition](table-definition.md)

K3.4 로컬 구현은 기존 `pipeline_files.file_type=preview`와 `pipeline_jobs.result_metadata.preview` JSON을 사용한다. 신규 table·column·index·Migration은 없다. 성공 확정 transaction에 pending을 저장하고 Preview row와 ready JSON은 하나의 transaction에 등록한다. DB Job UPDATE write lock으로 서비스의 중복 실행을 직렬화하며 ready row를 재사용한다. file role의 DB unique constraint는 추가하지 않아 직접 SQL writer까지 단일 row를 보장하지 않는다. DB가 authoritative하고 metadata.json은 사후 동기화한다. SQLite는 렌더링 중 다른 writer도 대기할 수 있다. 상태·복구 계약은 [Audio Analysis 결과 계약](../03-architecture/audio-analysis-result-contract.md)을 참조한다.

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
| `cancel_requested_at`, `cancelled_at` | cooperative 취소 요청·확정 시각 |
| `retry_of_job_id` | 원본 Pipeline Job self FK, 원본 제거 시 `SET NULL` |
| `input_snapshot` | Retry용 공개 생성 입력 JSON. 비밀·경로·PID 제외 |

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
취소 작업은 최종 Result를 등록하지 않으며 생성된 부분 파일을 정리한다. 원본 입력은 Retry를 위해 Job row에 유지한다.
