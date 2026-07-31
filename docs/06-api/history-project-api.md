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

History와 Project Job 공개 필드는 기존 필드에 allowlist `generation_options`와 `kpop_prompt_compiler_version`을 추가한다. 화면은 Preset 표시 이름, 목표 BPM, Hook phrase, Vocal Energy, Concept와 Retry 원본 관계를 간단한 설정 요약으로 표시한다. 옵션이 없는 구형 Job은 요약을 생략한다. 내부 Snapshot·compiled prompt·Storage·절대 경로·filesystem·temp·Provider 설정은 반환하지 않는다. `has_audio`는 완료 Job에 최종 파일 row가 있을 때만 `true`다.

취소된 Job은 History와 Project에서 삭제하지 않는다. Retry Job은 원본 Structured Options·Seed·Voice·Project를 복원해 최신순 History에 별도 Job으로 표시한다. 원본 Project가 없으면 기존 Default Project 정책을 적용하고, 구형 Job에는 기존 Snapshot 호환 경로를 사용한다.

## K3 Audio Analysis 표시 계약 [계획]

- History 목록: analysis status, 예상 BPM·confidence 요약, Preview 가능 여부
- History 상세: Result 공개 allowlist의 quality·tempo·Hook/Chorus 후보·Preview 정보
- Project Job 목록: status, 예상 BPM 요약, Preview 가능 여부
- 구형·미분석 Job: 분석 정보 없음으로 표시하고 final WAV capability는 유지

Project 삭제는 현행처럼 Job 연결만 해제하므로 향후 Preview와 분석 metadata도 Job과 함께 보존한다. 내부 path·raw metadata·stack은 노출하지 않는다. K3.0에서는 DTO와 화면을 변경하지 않으며 [결과 계약](../03-architecture/audio-analysis-result-contract.md)에만 목표 범위를 정의한다.
