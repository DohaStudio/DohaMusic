# 음원 분리 어댑터

> 문서 목적: Stem separation 모델의 공통 입출력과 품질 검사를 정의한다.
> 현재 상태: **Mock·Demucs Adapter 구현 및 GPU E2E 완료**

입력은 지원 형식으로 정규화된 혼합 오디오다. MVP 출력 계약은 `vocals`와 `instrumental` 두 Stem이며, 다중 Stem 모델은 어댑터 내부에서 반주를 조합할 수 있다.

`StemSeparator`는 `StemSeparationInput(job_id, source_path)`를 받고 모델 중립 `StemSeparationResult`를 반환한다. `MockStemSeparator`는 AI 의존성 없이 48kHz Stereo WAV를 만들고, `DemucsAdapter`는 격리 runner의 경로·성능 metadata를 공통 결과로 변환한다. Worker와 Service는 Demucs 타입을 import하지 않는다.

HTDemucs의 `vocals`를 그대로 사용하고 drums·bass·other를 Adapter 내부에서 합산해 instrumental을 만든다. 출력은 48kHz Stereo IEEE float32 WAV다. 길이·샘플레이트·채널과 무음/클리핑을 검증하고 metadata에 hash·크기·자원 지표를 기록한다. 모델을 자동 다운로드하지 않으며 누락된 runtime·checkpoint·출력은 안정적인 `STEM_*` 오류로 변환한다.
