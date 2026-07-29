# Voice Conversion Adapter

## 계약

`VoiceConverter.convert(VoiceConversionInput)`은 `source_path`, `reference_path`, `job_id`를 받고 변환 WAV·metadata·Provider·모델 버전·시간·메모리 지표를 반환한다. 서비스와 Worker는 Seed-VC 모듈을 직접 import하지 않는다.

## Provider

- `mock`: 기본값. 소스 WAV를 48kHz stereo 계약 그대로 복사하고 metadata를 만든다.
- `seed_vc`: 고정된 별도 Python 환경에서 runner를 subprocess로 실행한다.

`DOHAMUSIC_VOICE_PROVIDER=mock`이 기본이다. `seed_vc`는 runtime Python, runner, 공식 프로젝트, 체크포인트, config, cache 경로가 모두 있을 때만 실행된다. Backend subprocess는 `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`로 동작하므로 요청 처리 중 모델을 내려받지 않는다.

## 입출력

- 소스는 DB에 등록된 `stem_files.file_type=vocals`만 허용한다.
- 참조 음성은 `consent_confirmed=true`인 Voice Profile이어야 한다.
- 실제 경로는 설정된 storage root 내부 `voices/references` 아래인지 Worker에서 다시 확인한다.
- 출력은 `voices/converted/{job_id}.wav`, metadata는 `voices/metadata/{job_id}.json`이다.
- WAV 계약은 48kHz, stereo, signed PCM16이다.

Seed-VC 출력은 길이·sample rate·channel·RMS·peak·무음·clipping을 자동 검사한다. clipping은 metadata 경고이며 현재 Job 실패 조건은 아니다. 정책 변경 시 ADR을 갱신한다.
