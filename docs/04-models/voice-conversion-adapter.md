# Voice Conversion Adapter

## 계약

`VoiceConverter.convert(VoiceConversionInput)`은 `source_path`, `reference_path`, `job_id`를 받고 변환 WAV·metadata·Provider·모델 버전·시간·메모리 지표를 반환한다. 서비스와 Worker는 Seed-VC 모듈을 직접 import하지 않는다.

## Provider

- `mock`: 기본값. 소스 WAV를 48kHz stereo 계약 그대로 복사하고 metadata를 만든다.
- `seed_vc`: 고정된 별도 Python 환경에서 runner를 subprocess로 실행한다.

`seed_vc`의 현재 수명주기는 `Experimental`이며 운영 채택은 보류다. 상태 승격은 [Voice Provider Selection Policy](voice-provider-selection-policy.md)와 ADR-010을 따른다.

`DOHAMUSIC_VOICE_PROVIDER=mock`이 기본이다. `seed_vc`는 runtime Python, runner, 공식 프로젝트, 체크포인트, config, cache 경로가 모두 있을 때만 실행된다. Backend subprocess는 `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`로 동작하므로 요청 처리 중 모델을 내려받지 않는다.

## 입출력

- 소스는 DB에 등록된 `stem_files.file_type=vocals`만 허용한다.
- 참조 음성은 `consent_confirmed=true`인 Voice Profile이어야 한다.
- 실제 경로는 설정된 storage root 내부 `voices/references` 아래인지 Worker에서 다시 확인한다.
- 출력은 `voices/converted/{job_id}.wav`, metadata는 `voices/metadata/{job_id}.json`이다.
- WAV 계약은 48kHz, stereo, signed PCM16이다.

Seed-VC 출력은 길이·sample rate·channel·RMS·peak·무음·clipping을 자동 검사한다. 현재 구현에서 clipping은 metadata 경고이며 Job 실패 조건은 아니지만, 이는 운영 허용을 뜻하지 않는다. Phase 4.5에서 float benchmark 3/3의 full-scale 부근/초과 위험을 확인했고 현재 PCM16 export 경로는 같은 입력으로 재검증되지 않았다. pre/post resample·export 측정과 headroom/limiter 회귀 기준이 확정될 때까지 `seed_vc`를 운영 또는 Phase 5에 연결하지 않는다.
