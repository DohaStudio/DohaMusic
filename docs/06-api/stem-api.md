# Stem 분리 API

> 현재 상태: **Mock 기본 / Demucs 선택적 Provider 구현**

## `POST /api/stems`

```json
{
  "source_file_id": "generated_files UUID"
}
```

존재하는 생성 파일을 입력으로 비동기 Stem Job을 만들고 `202 Accepted`와 `PENDING` 상태를 반환한다. 요청자가 Provider를 선택할 수 없으며 서버의 `DOHAMUSIC_STEM_PROVIDER` 설정을 따른다.

## `GET /api/stems/{job}`

`id`, `source_file_id`, 상태·현재 단계, Provider·모델·버전, 안전한 오류, 생성·갱신·완료 시각을 반환한다. 상태 흐름은 `PENDING → VALIDATING → STEM_SEPARATING → COMPLETED`이고 어느 처리 단계에서든 `FAILED`가 될 수 있다.

## `GET /api/stems/{job}/files`

완료 후 `vocals`, `instrumental`, `metadata` 유형의 파일 메타데이터를 반환한다. 실제 다운로드 API는 없다. Demucs 오디오는 48kHz Stereo float32 WAV이며 Mock도 48kHz Stereo WAV 계약을 따른다.

존재하지 않는 source 또는 Job은 `RESOURCE_NOT_FOUND`, 입력 형식 오류는 `INVALID_INPUT`이다. Worker의 내부 예외·절대 경로는 응답에 노출하지 않는다.
