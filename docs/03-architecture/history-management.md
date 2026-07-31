# Generation History

> 문서 상태: [완료]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 8 Generation History
> 관련 문서: [History·Project API](../06-api/history-project-api.md), [Project 관리](project-management.md)

History는 별도 복제 저장소가 아니라 `pipeline_jobs`를 기준으로 Voice Profile 이름과 최종 Pipeline File 존재 여부를 조합한 공개 projection이다. Pipeline 요청이 생성되는 즉시 History에 나타나며 최신순 목록, `limit`·`offset`, 상태 필터와 Prompt 기반 제목 검색을 지원한다.

Frontend `/history`는 Loading Skeleton, 빈 상태, Queued·Running·Completed·Failed Badge, Play·Download·Result Open을 제공한다. 재생과 다운로드는 기존 Pipeline file capability URL만 사용하고 Storage 경로를 알지 못한다.

현재 인증·소유권이 없으므로 로컬 단일 사용자 범위다. 공개 운영 전 사용자별 History 격리가 필요하다.
