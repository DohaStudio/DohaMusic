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
