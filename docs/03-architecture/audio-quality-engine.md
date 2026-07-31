# Audio Quality Engine

> 현재 상태: **Phase 5.1 Default Audio Mixer 구현 완료**
> 관련 결정: [ADR-013](../11-decisions/ADR-013-audio-mixing-engine.md)

## 책임과 경계

`AudioMixer`는 변환 보컬과 반주 WAV를 받아 하나의 48kHz Stereo PCM16 WAV와 품질 metadata를 만든다. Pipeline은 인터페이스만 호출하며 DSP 구현을 직접 알지 않는다.

```text
vocals.wav + instrumental.wav
  → sample rate·channel·length 동기화
  → track gain
  → optional soft limiter
  → peak normalization·headroom
  → fade in/out
  → PCM16 final.wav + metadata.json
```

Provider는 `default`와 회귀·격리 테스트용 `mock`이다. 운영 기본값은 `default`이며 Mock 구현은 삭제하지 않는다.

## Default 정책

| 항목 | 기본값 | 동작 |
|---|---:|---|
| 보컬 gain | 0 dB | linear gain으로 변환 후 합산 |
| 반주 gain | 0 dB | linear gain으로 변환 후 합산 |
| 출력 | 48kHz, Stereo, PCM16 | mono는 복제하고 다른 sample rate는 polyphase resampling |
| 길이 | 긴 입력 기준 | 짧은 입력 끝을 0으로 padding |
| headroom | 1 dB | peak 목표를 -1 dBFS로 설정 |
| normalization | `peak` | limiter 이후 peak를 목표값에 맞춤 |
| limiter | `soft` | -3 dBFS knee 위를 연속적으로 압축 |
| fade | 앞·뒤 10 ms | 선형 fade |

`normalization=off`, `limiter=bypass`도 설정할 수 있다. 설정 범위와 변수명은 [환경 변수](../10-operations/environment-variables.md)를 따른다.

## 품질 metadata

Mixer는 처리 시간, CPU time, process RSS 전후·증감, 출력 크기, 길이, sample rate, channel, gain, 목표·실제 headroom, peak, RMS, silence와 clipping 정보를 기록한다. `pre_processing_peak`와 `pre_processing_over_range`는 보호 처리 전 합산 신호를 나타내며, `detected`와 `ratio`는 PCM 변환 직전 신호를 나타낸다.

현재 True Peak(oversampled inter-sample peak)는 구현하지 않았다. 따라서 `true_peak_supported=false`, `true_peak_dbfs=null`로 기록하며 sample peak를 True Peak로 가장하지 않는다. LUFS·RMS normalization도 아직 지원하지 않는다.

## K3 Audio Analysis와의 경계

Mixer metadata는 처리 직전·직후 신호를 설명하는 현행 단계 metadata이며 K3의 최종 WAV 분석 결과가 아니다. K3.0은 최종 `final.wav`를 별도 후처리 계층에서 다시 읽어 Sample Peak·clipping·Integrated LUFS와 향후 검증된 True Peak를 versioned 결과로 기록하도록 계약만 정의했다.

- 현행 `peak_dbfs`: Mixer가 계산한 Sample Peak
- K3 `sample_peak_dbfs`: 최종 export WAV에서 측정할 Sample Peak `[계획]`
- K3 `integrated_lufs`: ITU-R BS.1770/EBU R 128 reference 검증 후 제공 `[계획]`
- K3 `true_peak_dbtp`: oversampling과 reference 검증 통과 전 미지원 `[계획]`

구체 계약은 [K3 제품 정의](../02-product/k3-audio-analysis-product-definition.md)와 [EVAL-008](../../reports/evaluations/EVAL-008-audio-analysis-validation.md)을 따른다. K3.0에서는 Mixer 코드·설정·metadata를 변경하지 않는다.

## 실패와 제한

- 비어 있거나 NaN·Infinity가 포함된 WAV, 2채널을 초과하는 WAV는 거부한다.
- peak normalization은 작은 신호와 그 잡음도 함께 키울 수 있다.
- soft limiter는 mastering-grade loudness processor가 아니다.
- 자동 지표는 파일 무결성과 clipping 위험을 보조할 뿐 청감 품질을 승인하지 않는다. 청감 평가는 [EVAL-004](../../reports/evaluations/EVAL-004-audio-mixing-listening-evaluation.md)에 사용자가 기록한다.

