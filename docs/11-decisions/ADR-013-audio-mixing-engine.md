# ADR-013 — Audio Mixing Engine

> 상태: 승인
> 결정일: 2026-07-29

## 배경

Phase 5의 `MockAudioMixer`는 변환 보컬을 복사해 Workflow 경계만 검증했다. 실제 final WAV를 만들려면 AI Provider와 분리된 재현 가능한 DSP 엔진, clipping 보호 정책과 측정 가능한 metadata가 필요하다.

## 결정

1. `AudioMixer` 인터페이스 아래 `DefaultAudioMixer`와 `MockAudioMixer`를 둔다.
2. 운영 기본값은 `DOHAMUSIC_AUDIO_MIXER=default`이며 Mock은 테스트·격리 용도로 유지한다.
3. 입력은 WAV mono/stereo를 허용하고 48kHz Stereo로 동기화한다. 짧은 입력은 0으로 padding한다.
4. 보컬·반주 gain은 각각 dB 설정으로 주입한다.
5. 기본 normalization은 peak, 목표 headroom은 -1 dBFS다.
6. 기본 limiter는 -3 dBFS knee의 soft limiter이며 `bypass`로 끌 수 있다.
7. 앞·뒤 10ms linear fade를 적용한다.
8. 출력은 PCM16 WAV이며 peak·RMS·headroom·clipping·처리 시간·CPU·RSS·출력 크기를 JSON metadata에 남긴다.
9. True Peak와 LUFS는 구현하지 않고 명시적인 미지원 값으로 기록한다.

구현에는 NumPy 배열 연산, SciPy WAV I/O·polyphase resampling, psutil process RSS를 사용한다. 세 의존성은 BSD-3-Clause 계열의 공식 라이선스를 확인했으며 배포 고지 inventory에는 계속 포함한다.

## 결과

Pipeline 구조와 AI Adapter 계약을 변경하지 않고 실제 합성이 가능해진다. 입력 형식 차이를 Mixer 경계에서 정규화하고 output clipping과 보호 전 over-range를 구분해 추적할 수 있다. 반면 peak normalization은 loudness 일관성을 보장하지 않고 soft limiter도 전문 mastering을 대체하지 않는다.

## 대안

- FFmpeg subprocess: 배포 의존성과 명령·버전 편차가 커 이번 로컬 Backend 기본 경로에서 제외했다.
- LUFS normalization: loudness 표준과 True Peak 측정 구현·검증이 필요해 후속 과제로 둔다.
- Mock 유지: 실제 음악 합성을 수행하지 않아 기본값으로는 부적합하다.

## 재검토 조건

LUFS 목표, True Peak 제한, 다중 stem, mastering chain, 외부 DSP runtime 또는 출력 codec 정책이 필요해지면 재검토한다. [EVAL-004](../../reports/evaluations/EVAL-004-audio-mixing-listening-evaluation.md)의 사용자 청취 결과에서 balance·자연스러움 문제가 확인돼도 gain 기본값을 재검토한다.

