# ADR-024: 브라우저 음성 녹음 포맷과 서버 정규화 경계

> 상태: [제안]
> 작성일: 2026-08-01
> 최종 수정일: 2026-08-01
> 관련 기능: F6 Guided Voice Enrollment
> 관련 문서: [Voice Enrollment 요구사항](../02-requirements/voice-enrollment-requirements.md), [Voice Enrollment API](../06-api/voice-enrollment-api.md), [Storage Architecture](../03-architecture/storage-architecture.md), [ADR-019](ADR-019-secure-voice-profile-upload.md)
> 관련 PR: 이 ADR을 승인·구현하는 PR에서 갱신

## Context

현재 `POST /api/voice-profiles/upload`은 `.wav`, `audio/wav` 또는 `audio/x-wav`, 25MiB 이하, 5~60초, 16-bit PCM, 16kHz 이상, mono/stereo만 받는다. 브라우저 `MediaRecorder`는 환경에 따라 WebM/Opus 또는 Ogg/Opus를 생성하므로 녹음 Blob을 현재 API에 직접 보낼 수 없다.

교체 가능한 normalizer interface와 Python WAV 변환, shell 없는 optional FFmpeg WebM/Ogg decoder, timeout·출력 재검증·부분 cleanup·미설치 오류를 구현했다. 2026-08-01 Windows 11의 Winget `Gyan.FFmpeg` 8.1.2 full build에서 합성 WebM/Ogg Opus를 실제 decode했고 CI에는 Ubuntu 전체 Backend와 Windows 집중 통합 검증을 추가했다. 다만 운영 배포 build의 라이선스 검토, 자원 상한의 악성 fixture 검증, Voice Provider 청감 평가와 실기기 MIME matrix가 남아 상태는 `[제안]`으로 유지한다.

> Frontend 구현 메모: `/voice`는 `audio/wav`, `audio/webm;codecs=opus`, `audio/webm`, `audio/ogg;codecs=opus`, `audio/ogg` 순서로 `MediaRecorder.isTypeSupported()`를 확인하고 권한·녹음·일시정지·재개·60초 종료·입력 수준·preview를 제공한다. WebM/Ogg normalization 실패는 WAV fallback으로 안내한다. 자동 E2E는 합성 WAV를 사용하고 Backend integration은 FFmpeg가 생성한 합성 WebM/Ogg를 사용했다. 실제 마이크·장치별 MIME 평가는 아직 미검증이다.

## Decision

Frontend는 녹음, 미리 듣기, MIME feature detection, 대략적인 시간과 선택 파일 크기 표시만 담당한다. Backend가 파일 signature를 확인하고 허용 컨테이너를 decode해 표준 WAV로 정규화하며, 저장 metadata와 품질 결과의 최종 권위가 된다.

### 입력과 자원 제한

| 항목 | 제안 계약 |
|---|---|
| 허용 확장자·MIME | `.wav`: `audio/wav`, `audio/x-wav`; `.webm`: `audio/webm`, `audio/webm;codecs=opus`; `.ogg`: `audio/ogg`, `audio/ogg;codecs=opus` |
| codec | WAV PCM16 또는 WebM/Ogg Opus만 허용. 기타 codec·컨테이너는 거절 |
| 선언 불일치 | 확장자, 정규화한 MIME과 signature/container probe 중 하나라도 불일치하면 `415 VOICE_SAMPLE_UNSUPPORTED_MEDIA_TYPE` |
| 원본 크기 | sample당 25MiB. `Content-Length`는 조기 거절 보조값이고 실제 streaming byte 집계가 최종 권위 |
| decode 길이 | 5초 이상 60초 이하. container metadata는 조기 판정에만 쓰고 실제 decoded frame 수로 다시 판정 |
| decode timeout | 로컬 MVP 기본 30초, 설정 가능. 초과 시 subprocess를 종료하고 `VOICE_SAMPLE_DECODE_TIMEOUT` |
| 출력 | little-endian signed PCM16 WAV, 48,000Hz, mono, `audio/wav` |
| 출력 상한 | 60초 PCM16 mono에 header 여유를 더한 6MiB. 초과 출력은 폐기 |

48kHz mono는 현재 Pipeline의 48kHz 처리와 단일 reference 입력을 단순화하고, mono는 참조 음성의 중복 channel을 제거해 저장·분석 비용을 제한한다. 이 값이 특정 Voice Provider의 최적 품질을 보장하지는 않는다. Provider 채택 시 reference sample-rate 요구와 청감 비교를 다시 수행한다.

### 변환과 signal processing의 분리

- 정규화는 container decode, resample, mono downmix와 PCM16 export만 수행한다.
- loudness normalization, compressor, limiter, noise removal, silence trimming, VAD trimming과 sample 이어붙이기는 수행하지 않는다.
- 자동 음량·구간 처리는 음색과 발화 특성을 바꿀 수 있으므로 별도 DSP 결정과 청감 검증 없이는 추가하지 않는다.
- Backend는 정규화본을 다시 열어 format, duration, sample rate, channel, bit depth를 검증한 뒤 품질 검사를 실행한다.

### 실행 격리와 cleanup

- system FFmpeg CLI를 shell 없이 고정 argument 배열로 별도 subprocess에서 실행한다. executable path와 timeout은 설정으로 주입하고, `-version` 결과와 파일 존재를 최초 WebM/Ogg 요청에서 확인한 뒤 process 수명 동안 성공 경로를 재사용한다. 사용자 파일 경로는 server-generated 경로이며 command option으로 조합하지 않는다.
- sample별 private temporary directory를 만들고 원본과 정규화 후보를 server-generated 이름으로 저장한다. 원본 파일명은 표시용으로만 정제하며 path·로그에 쓰지 않는다.
- 첫 audio stream만 `-map 0:a:0`으로 선택하고 video를 제외하며, stdin과 stdout/stderr는 닫거나 폐기한다. 출력 포맷은 임시 확장자와 무관하게 `wav`로 명시한다. timeout, 비정상 종료, decode 오류, 출력 상한 초과 시 부분 출력과 최종 출력 후보를 삭제한다. protocol allowlist와 process-level memory limit은 아직 구현하지 않았으므로 악성 입력 운영 승인 조건으로 남긴다.
- 삭제 실패는 성공으로 숨기지 않고 sample cleanup 상태에 남겨 재시도한다. 상세 정책은 [ADR-026](ADR-026-voice-enrollment-lifecycle-cleanup.md)을 따른다.
- 원본은 Enrollment가 진행되는 동안 재검증·오류 진단을 위해 임시 보존한다. Profile 생성 성공, sample 삭제, 취소 또는 만료 시 삭제하며 최종 Profile에는 정규화본만 승격한다.

### metadata와 품질 책임

Frontend 값은 사용자 피드백용 추정치다. Backend가 probe와 decoded frame에서 얻은 MIME/container, codec, byte, duration, sample rate, channels, bit depth를 영속 metadata로 사용한다.

Backend는 현재 RMS·silence ratio·clipping 검사를 정규화본에 적용해 `PASS`, `WARNING`, `FAIL`을 만든다. format·decode·duration 위반은 `FAIL`, 기존 `LOW_VOLUME`, `HIGH_SILENCE_RATIO`, `POSSIBLE_CLIPPING`은 `WARNING`이다. `WARNING`은 사용자가 경고를 명시적으로 확인하면 제출할 수 있고 `FAIL`은 차단한다. 이 결과는 권리, 화자 일치, 학습 적합성 또는 최종 Voice Conversion 품질을 보장하지 않는다.

VAD, SNR, 배경음악·다중 화자·화자 일관성·음역 검사는 모델·라이선스·오탐 평가 전까지 후속 Worker 후보이며 현재 계약이 아니다.

## Alternatives

### A. Frontend WAV 변환

Web Audio API·AudioWorklet·client PCM encoder는 현재 API를 재사용할 수 있다. 그러나 압축 Blob 전체 decode와 PCM 복사는 모바일 CPU·메모리를 늘리고 브라우저별 결과가 달라진다. 신뢰할 수 없는 client 결과를 Backend가 다시 검증해야 해 중복도 남으므로 기본안에서 제외한다.

### B. Backend decode·정규화

입력·출력·metadata·자원 제한을 한 경계에서 강제할 수 있고 Frontend bundle과 기기 차이를 줄인다. decoder 공격면과 운영 의존성이 생기지만 격리 subprocess와 임시 수명주기로 통제할 수 있어 선택했다.

### C. Chromium/MIME 제한

구현은 작지만 Safari·Firefox·모바일 사용자가 녹음하지 못한다. feature detection 실패 시 기존 WAV upload fallback으로는 유지하되 제품의 유일한 경계로 채택하지 않는다.

### D. 별도 녹음 서비스·Worker

격리와 확장성은 좋지만 로컬 단일 사용자 MVP에 별도 배포·Queue·Storage 일관성을 추가한다. 5초를 넘을 수 있는 정규화는 기존 비동기 작업 원칙에 맞춰 Backend dispatcher에서 처리하되, 독립 서비스는 Phase 9 부하·격리 근거가 생길 때 검토한다.

## Consequences

브라우저별 Blob 차이를 Backend가 흡수하고 최종 WAV와 metadata를 일관되게 만들 수 있다. 반면 FFmpeg 배포, codec 빌드 범위, Windows process 종료, 악성 container와 resource exhaustion 회귀 검증이 추가된다. 기존 단일 WAV upload는 호환 경로로 유지하며 새 Enrollment API만 이 정규화 계약을 사용한다.

## Rollback·Migration

신규 WebM/Ogg allowlist와 정규화 worker를 비활성화하고 F6를 기존 PCM16 WAV upload fallback으로 되돌린다. 기존 `voice_profiles`와 `voices/references/{profile_id}/reference.wav`는 변경하지 않는다. 임시 Enrollment 파일은 ADR-026 cleanup으로 제거한다.

## 승인 전 검증과 재검토 조건

- [부분 완료] Windows FFmpeg 8.1.2와 Ubuntu·Windows CI에서 WebM/Ogg Opus decode 경로를 검증했다. 운영 배포 build 고정, license와 배포 재현성은 `[운영 배포 전 라이선스 검토 필요]`이다.
- [부분 완료] 합성 정상 WebM/Ogg, truncated 입력, mock timeout·비정상 종료·부분 출력 cleanup을 검증했다. 25MiB·60초, 다중 stream·비정상 metadata·process memory 상한 fixture는 남아 있다.
- 48kHz mono PCM16이 채택 Voice Provider 입력에서 기존 reference보다 품질을 악화시키지 않는 청감 평가
- Safari·Firefox·Chromium Desktop/Mobile의 실제 MIME matrix 확인
- object storage, 외부 Queue 또는 별도 media service 도입
