# EXP-006 — Audio Mixing

> 실행일: 2026-07-29
> 결과: **DefaultAudioMixer 기능·Pipeline 연결 성공**

## 목적

실제 DSP Mixer가 보컬과 반주를 48kHz Stereo PCM16으로 합성하고, -1 dBFS headroom·metadata 계약을 지키는지 측정한다. 실제 음악 청감 품질은 이 실험에서 판정하지 않는다.

## 환경과 입력

- Windows 로컬 Backend 환경
- NumPy 1.26.4, SciPy 1.17.1, psutil 7.2.2
- Mixer 입력: 48kHz Stereo float32, 10초 합성 sine
- vocals: 440Hz, amplitude 0.4
- instrumental: 220Hz, amplitude 0.5
- 설정: gain 0/0 dB, peak normalization, -1 dBFS headroom, soft limiter, fade in/out 10ms
- 실행: `python -m backend.scripts.benchmark_audio_mixer`

## Mixer 결과

| 지표 | 결과 |
|---|---:|
| 성공 | 예 |
| Mixer time | 0.069688초 |
| CPU time | 0.046875초 |
| RSS before / after | 147.09 / 179.25 MiB |
| RSS delta | 32.16 MiB |
| 출력 크기 | 1,920,044 bytes |
| 출력 길이 | 10.000초 |
| 출력 형식 | 48,000Hz, Stereo, PCM16 WAV |
| normalization gain | +1.1167 dB |
| peak | 0.891251 / -1.000 dBFS |
| RMS | 0.514258 / -5.776 dBFS |
| 실제 headroom | 1.000 dB |
| 출력 clipping | 없음, ratio 0 |
| 무음 | 아니요 |

## Pipeline 연결 결과

Mock Music·Stem·Voice와 실제 `DefaultAudioMixer`를 조합한 1회 Pipeline은 성공했다. 전체 실행 시간은 0.106103초, Mixer step은 0.009553초, 그중 Provider 실행은 0.009419초였다. 해당 Mixer 실행의 CPU time은 0.015625초, RSS 증가는 0.36 MiB, 출력은 19,244 bytes였다. Mock Stem 출력 길이가 0.1초이므로 위 10초 단독 Mixer 결과와 직접 성능 비교하지 않는다.

## 해석과 제한

gain, sync, limiter, peak normalization, fade, PCM export와 metadata 경계는 정상 동작했다. 수치는 단일 PC·합성 신호·warm process 1회 결과이며 운영 SLO나 실제 곡 품질을 증명하지 않는다. True Peak와 LUFS는 측정하지 않았고 GPU를 사용하지 않는다. 청감 판정은 [EVAL-004](../evaluations/EVAL-004-audio-mixing-listening-evaluation.md)에 사용자가 기록한다.
