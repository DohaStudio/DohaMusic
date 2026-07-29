# Voice Conversion API

## POST `/api/voice-conversion`

별도 비동기 변환 Job을 생성하고 `202 Accepted`를 반환한다.

```json
{
  "source_file_id": "stem_files의 vocals UUID",
  "voice_profile_id": "동의된 voice_profiles UUID"
}
```

파일 경로는 API 입력으로 받지 않는다. 존재하지 않거나 vocals가 아닌 source, 동의되지 않은 profile은 거부한다.

## GET `/api/voice-conversion/{job_id}`

`PENDING → VALIDATING → VOICE_CONVERTING → COMPLETED|FAILED` 상태, Provider·모델 버전과 안정된 오류 코드를 조회한다.

## GET `/api/voice-conversion/{job_id}/files`

완료 후 `converted_voice` WAV와 `metadata` JSON의 저장소 상대 경로를 반환한다.

## 오류 코드

- `VOICE_PROVIDER_NOT_CONFIGURED`
- `VOICE_DEPENDENCY_NOT_INSTALLED`
- `VOICE_MODEL_LOAD_FAILED`
- `VOICE_CONVERSION_FAILED`
- `VOICE_OUT_OF_MEMORY`
- `VOICE_OUTPUT_NOT_CREATED`
- `VOICE_TIMEOUT`
