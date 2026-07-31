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

Voice 출력은 `voices/converted/{job_id}.wav`, 실행 metadata는 `voices/metadata/{job_id}.json`이다. 참조 음성·변환 음성·모델·cache·실험 파일은 Git에서 제외한다. 업로드 API는 없으며 동의된 참조 파일을 운영자가 안전하게 배치한다. 완료 Pipeline의 허용된 WAV만 Service 검증 후 `FileResponse`로 전달하고 Storage 디렉터리 자체는 정적으로 공개하지 않는다.

## K3 Preview 저장 목표 [계획]

K3.4 Preview는 `pipelines/{job_id}/preview_15s.wav` 후보 경로에 원본과 분리해 저장하고 `pipeline_files`의 opaque ID로 등록한다. 내부 상대·절대 경로는 공개 DTO에 포함하지 않으며 기존 secure content/download의 완료 상태·Storage root·symlink·regular file·크기·MIME·RIFF 검증과 `private, no-store`를 재사용한다.

Project 삭제는 현행처럼 Job 연결만 해제하므로 Preview도 보존한다. 향후 Job/Result 삭제는 Preview·분석 metadata를 같은 cleanup unit으로 제거해야 하며, Retry는 새 Job 경로에 새 Preview를 만들고 기존 파일을 복사하지 않는다. K3.0에서는 디렉터리·파일 저장 로직을 변경하지 않는다. 세부 계약은 [Audio Analysis 결과 계약](audio-analysis-result-contract.md)을 따른다.
