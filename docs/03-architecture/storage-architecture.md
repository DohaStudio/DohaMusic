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

Voice 출력은 `voices/converted/{job_id}.wav`, 실행 metadata는 `voices/metadata/{job_id}.json`이다. 사용자용 단일 WAV upload는 검증 전 `voices/references/.uploads/{uuid}.tmp`, 성공 후 `voices/references/{profile_uuid}/reference.wav`를 사용하며 실패 시 temp·final orphan을 정리한다. legacy 운영자 배치 참조 파일도 개발 호환으로 유지한다. 참조 음성·변환 음성·모델·cache·실험 파일은 Git에서 제외한다. 원본 참조 음성 content/download는 제공하지 않고 완료 Pipeline의 허용된 WAV만 Service 검증 후 `FileResponse`로 전달하며 Storage 디렉터리 자체는 정적으로 공개하지 않는다. F6 다중 sample·임시 Enrollment·원본 보존은 [Voice Enrollment 요구사항](../02-requirements/voice-enrollment-requirements.md)의 `[ADR 필요]` 항목이다.

## K3 Preview 저장 목표 [계획]

K3.4 Preview는 `pipelines/{job_id}/preview_15s.wav` 후보 경로에 원본과 분리해 저장하고 `pipeline_files`의 opaque ID로 등록한다. 내부 상대·절대 경로는 공개 DTO에 포함하지 않으며 기존 secure content/download의 완료 상태·Storage root·symlink·regular file·크기·MIME·RIFF 검증과 `private, no-store`를 재사용한다.

K3.1은 새 디렉터리·파일·테이블 없이 기존 `result_metadata.audio_analysis`와 `metadata.json`을 갱신한다. Project 삭제는 Job·분석 metadata를 보존한다. Preview 저장은 K3.4 계획이며 Retry는 새 Job의 새 final WAV를 분석하고 기존 결과를 복사하지 않는다. 세부 계약은 [Audio Analysis 결과 계약](audio-analysis-result-contract.md)을 따른다.
