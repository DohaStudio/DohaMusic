# Pipeline API

> 문서 상태: [완료]
> 최종 수정일: 2026-07-29
> 관련 기능: Phase 5 Pipeline Orchestrator

## 생성

`POST /api/pipelines`는 `202 Accepted`와 `PENDING` Job을 반환한다.

```json
{
  "prompt": "잔잔한 한국어 발라드",
  "lyrics": "직접 작성한 가사",
  "genre": "ballad",
  "duration_seconds": 30,
  "seed": 20260729,
  "voice_profile_id": "UUID"
}
```

`voice_profile_id`는 존재하고 동의가 확인돼야 한다. 참조 파일은 설정된 Storage의 `voices/references` 아래에 있어야 한다.

## 조회

- `GET /api/pipelines/{job_id}`: 상태, 현재 단계, 진행률, 오류, Pipeline metadata
- `GET /api/pipelines/{job_id}/files`: 성공 시 6개 결과 파일 metadata, 실패 시 진단 metadata

상태는 `PENDING → VALIDATING → GENERATING → STEM_SEPARATING → VOICE_CONVERTING → MIXING → EXPORTING → COMPLETED` 순서다. 어느 단계에서든 `FAILED`로 종료할 수 있다.

응답의 `result_metadata`에는 Pipeline 버전, Provider·모델, seed, 전체·단계 시간, attempt, VRAM 가능한 값, 성공 여부, 실패 단계와 오류가 포함된다. Mock 실행의 GPU·VRAM·CPU 사용률은 추측하지 않고 `null`로 기록한다.

취소·수동 재시도·다운로드 API와 인증·소유권 검사는 이번 범위에 포함하지 않는다.
