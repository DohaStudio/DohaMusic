# Project Management

> 문서 상태: [완료]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 8 Project CRUD
> 관련 문서: [Generation History](history-management.md), [ADR-020](../11-decisions/ADR-020-project-history-retention.md)

Project는 Pipeline Job을 묶는 사용자 표시용 컨테이너다. `id`, `title`, `description`, `created_at`, `updated_at`을 공개하고 목록에는 `job_count`, 상세에는 안전한 History 항목을 포함한다.

Pipeline 생성 요청에 `project_id`가 없으면 `Default Project`를 자동 연결한다. Project 삭제는 Job의 연결만 해제하며 Job, Pipeline File row와 Storage 파일을 삭제하지 않는다. 다음 Pipeline 생성에 기본 Project가 없으면 다시 생성한다.

Frontend `/projects`는 생성·목록·삭제, `/projects/[id]`는 정보 수정·포함 Job·Result 이동을 제공한다. 인증·소유권 도입 전에는 다중 사용자 Project로 간주하지 않는다.
