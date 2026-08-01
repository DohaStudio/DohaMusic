# 저장소 아키텍처

```text
backend/storage/
├─ inputs/
├─ outputs/
├─ samples/
├─ stems/
│  ├─ vocals/
│  ├─ instrumentals/
│  └─ metadata/
└─ voices/
   ├─ references/
   ├─ converted/
   └─ metadata/
```

루트는 `AUDIO_STORAGE_ROOT`로 설정한다. DB에는 루트 기준 상대 경로만 저장하며 `StorageService`는 path traversal과 루트 밖 접근을 거부한다. Voice Worker는 참조 경로에 더 엄격한 `voices/references` 경계를 적용한다.

Voice 출력은 `voices/converted/{job_id}.wav`, 실행 metadata는 `voices/metadata/{job_id}.json`이다. 사용자용 단일 WAV upload는 검증 전 `voices/references/.uploads/{uuid}.tmp`, 성공 후 `voices/references/{profile_uuid}/reference.wav`를 사용하며 실패 시 temp·final orphan을 정리한다. legacy 운영자 배치 참조 파일도 개발 호환으로 유지한다. 참조 음성·변환 음성·모델·cache·실험 파일은 Git에서 제외한다. 원본 참조 음성 content/download는 제공하지 않고 완료 Pipeline의 허용된 WAV만 Service 검증 후 `FileResponse`로 전달하며 Storage 디렉터리 자체는 정적으로 공개하지 않는다.

F6는 [ADR-026](../11-decisions/ADR-026-voice-enrollment-lifecycle-cleanup.md)에 따라 `voices/enrollments/{enrollment_id}/samples/{sample_id}/original.{wav|webm|ogg}`와 `normalized.wav` 임시 root, `voices/references/{profile_id}/samples/{sample_id}/reference.wav` 승격 구조를 구현했다. UUID 생성 경로, root·traversal·symlink 검사, 임시 suffix와 rename, overwrite 방지와 반복 cleanup을 적용한다. 원본은 submit·sample 삭제·취소·lazy 만료 때 제거하고 실패는 `DELETE_FAILED`/cleanup failure로 추적하며 공개 DTO에는 내부 경로를 포함하지 않는다. 주기적 orphan scanner와 retry scheduler는 미구현이다.

## K3 Preview 저장 목표 [계획]

K3.4 Preview는 `pipelines/{job_id}/preview_15s.wav` 후보 경로에 원본과 분리해 저장하고 `pipeline_files`의 opaque ID로 등록한다. 내부 상대·절대 경로는 공개 DTO에 포함하지 않으며 기존 secure content/download의 완료 상태·Storage root·symlink·regular file·크기·MIME·RIFF 검증과 `private, no-store`를 재사용한다.

K3.1은 새 디렉터리·파일·테이블 없이 기존 `result_metadata.audio_analysis`와 `metadata.json`을 갱신한다. Project 삭제는 Job·분석 metadata를 보존한다. Preview 저장은 K3.4 계획이며 Retry는 새 Job의 새 final WAV를 분석하고 기존 결과를 복사하지 않는다. 세부 계약은 [Audio Analysis 결과 계약](audio-analysis-result-contract.md)을 따른다.
