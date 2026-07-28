# 저장소 아키텍처

> 문서 목적: Phase 1 로컬 파일 저장 규칙과 후속 교체 경계를 정의한다.
> 현재 상태: **로컬 Storage 구현 완료**

```text
backend/storage/
├── inputs/
├── outputs/
│   └── {job_id}/generated.wav
├── voices/
└── samples/
    └── sample.wav
```

루트 경로는 `AUDIO_STORAGE_ROOT` 환경 변수로 설정한다. 애플리케이션 시작 시 네 디렉터리를 만들고, 테스트용 `sample.wav`가 없으면 짧은 무음 WAV를 생성한다. 생성 결과는 루트 기준 상대 경로로 `generated_files.file_path`에 기록한다.

`StorageService`는 루트 밖으로 벗어나는 상대 경로를 거부한다. 현재 API는 파일 다운로드나 실제 업로드를 제공하지 않으며, `voice_profiles.reference_file_path`는 메타데이터만 저장한다.

향후 객체 저장소를 도입할 때는 Service와 Worker가 저장소 구현 세부사항에 의존하지 않도록 현재 Storage 경계를 Adapter 인터페이스로 확장한다. 보존·삭제 정책은 [오디오 데이터 정책](../05-data/audio-data-policy.md)을 따른다.
