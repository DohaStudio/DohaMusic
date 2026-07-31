# History·Project API

> 문서 상태: [완료]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 8 History·Project
> 관련 문서: [Pipeline API](pipeline-api.md), [ADR-020](../11-decisions/ADR-020-project-history-retention.md)

## Endpoint

| Method | 경로 | 설명 |
|---|---|---|
| GET | `/api/history` | 최신순 History. `limit`, `offset`, `status`, 제목 검색 `q` 지원 |
| GET | `/api/history/{job_id}` | History 상세 |
| GET | `/api/projects` | Project 목록과 Job 수 |
| POST | `/api/projects` | Project 생성 |
| GET | `/api/projects/{id}` | Project와 포함 Job 목록 |
| PATCH | `/api/projects/{id}` | 제목·설명 수정 |
| DELETE | `/api/projects/{id}` | Project만 삭제하고 Job·파일 유지 |

Pipeline 생성 요청의 선택 필드 `project_id`가 없으면 `Default Project`를 자동 연결한다. 삭제된 Project의 Job은 `project_id: null`로 History에 남는다.

History 공개 필드는 `job_id`, `project_id`, `title`, `status`, `created_at`, `duration`, `voice_profile_name`, `has_audio`다. 내부 Storage·절대 경로·filesystem·temp·Provider 설정은 반환하지 않는다. `has_audio`는 완료 Job에 최종 파일 row가 있을 때만 `true`다.
