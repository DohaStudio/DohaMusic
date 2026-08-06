# EXP-004 — Seed-VC 로컬 추론

> 실행일: 2026-07-29
> Phase 4.5 재분석일: 2026-07-29
> 결과: 기술 추론 성공, 품질·운영 채택 보류

## 환경

- GPU: NVIDIA GeForce RTX 3060 Ti 8GB
- Driver: 610.62
- Python: 3.11.9
- Torch: 2.7.1+cu128
- Seed-VC commit: `51383efd921027683c89e5348211d93ff12ac2a8`
- Model: `seed-uvit-whisper-base-f0-44k`, snapshot `257283f9f41585055e8f858fba4fd044e5caed6e`
- 설정: CUDA, FP16, F0 condition, 30 diffusion steps, length 1.0, CFG 0.7
- 입력: 공식 저장소 예제 source 12.479초 / reference 14.597초

개인 음성·체크포인트·생성 WAV는 커밋하지 않았다.

## 기존 Benchmark 요약

Phase 4.5에서는 실험을 반복하지 않고 Phase 4의 원본 metadata와 로그를 다시 계산·분석했다.

| 지표 | 최소 | 평균 | 최대 |
|---|---:|---:|---:|
| 처리 시간 | 26.172초 | 27.224초 | 28.560초 |
| peak VRAM | 5,067MB | 5,068MB | 5,069MB |
| peak process RAM | 3,032.645MB | 3,033.729MB | 3,034.910MB |
| 출력 길이 | 12.469초 | 12.469초 | 12.469초 |
| 출력 크기 | 4,788,232 bytes | 4,788,232 bytes | 4,788,232 bytes |

- 성공률: 3/3, 100%
- 출력 형식: 48kHz, stereo, float WAV
- CPU peak: run별 290.7%, 234.0%, 118.1%; 집계 방식상 단일 core 100%를 초과할 수 있다.

## 자동 음질 분석

| Run | Peak | RMS | Clipped sample ratio (`abs >= 0.999`) | SHA-256 |
|---|---:|---:|---:|---|
| 1 | 1.001502 | -15.947 dBFS | 0.000003 | `2C95CE1865F0815F2958524A3BB136734EA25EC32D017CF06D151D05F75DA3D1` |
| 2 | 1.003933 | -15.540 dBFS | 0.000040 | `790A37F74C8FA34574E852207F355FABC142F674231E244DC2452F1015281B2E` |
| 3 | 0.999002 | -15.853 dBFS | 0.000002 | `79A4B3ABD4A6998419E8255A70215E2814DA17615BD5BEA18751E2F1E896735C` |

- 모든 출력은 존재하고 무음이 아니며 길이·48kHz·stereo 조건을 충족했다.
- 세 hash가 서로 달라 동일 입력의 bit 단위 결정성은 확인되지 않았다.
- LUFS 도구(`ffmpeg` ebur128 또는 `pyloudnorm`)가 검증 환경에 없어 LUFS는 측정하지 않았다. RMS를 LUFS로 대체하지 않는다.
- 참고 입력은 24kHz mono, peak 0.989990, RMS -18.040dBFS, clipping 없음이었다.
- 별도 30-step 단독 출력은 peak 0.989911, RMS -15.679dBFS로 clipping sample이 없었다. 따라서 모든 실행이 반드시 초과 범위를 만드는 것은 아니다.

## Clipping 원인 분석

확인된 신호 경로는 `Seed-VC/vocoder 출력 → torchaudio resample → mono 복제 → WAV 저장`이다. 기존 runner에는 normalization, limiter, FFmpeg 단계가 없다.

| 후보 | 확인 결과 | 근거와 영향 |
|---|---|---|
| Seed-VC/vocoder 출력 | **상류 기여 확인** | 공식 10-step 실행 로그에서 저장 전 텐서 최대값 `1.0214` 확인 |
| 후처리 normalization/limiter | **미적용 확인** | runner는 gain 조정 없이 resample·channel 변환·save만 수행 |
| Resampling | 영향 분리 불가 | 30-step raw 임시 출력이 보존되지 않아 전후 peak 비교 불가 |
| FFmpeg | 원인 아님 | 실험 경로와 환경에 FFmpeg 미사용 |
| PCM 변환/export | 기존 3회 원인 아님, 향후 위험 | 기존 산출물은 float WAV라 초과값 보존; 현재 PCM16 경로는 같은 사례로 재검증되지 않음 |
| Sampling/모델 비결정성 | clipping 원인 미확정 | hash·peak는 run별 다르지만 인과를 입증하지 못함 |

기존 float WAV에서 `abs >= 0.999`를 감지한 것은 full-scale 초과 위험 경고다. 정수 PCM에서 이미 잘린 파형이라는 뜻으로 확대 해석하지 않는다. 반면 PCM16 변환 전 peak가 1을 넘으면 hard clipping이 발생할 수 있어 운영 영향은 높다.

## 해결·우회안과 검증 상태

- 저장 전, resample 후, PCM16 export 후 peak와 true-peak를 각각 기록한다. **검증 필요**
- 목표 headroom과 실패 임계값을 정하고, 검증된 peak normalization 또는 true-peak limiter를 적용한다. **검증 필요**
- 수정 전까지 `seed_vc`는 Experimental로 유지하고 운영/배포 입력에 사용하지 않는다.
- clipping을 단순 경고로 무시하거나 peak를 강제로 잘라내는 방식은 해결로 인정하지 않는다.

## 기존 실행 관찰

- 최초 requirements 설치는 비표준 Torch 옵션 줄과 Windows `webrtcvad` 빌드 때문에 실패했다. CUDA wheel과 `webrtcvad-wheels`로 격리 설치했다.
- Torch 2.4 CUDA wheel은 검증 장비에서 `fbgemm.dll`을 로드하지 못해 기존 장비에서 동작한 2.7.1+cu128을 사용했다.
- 공식 모델 로드 시 일부 shape mismatch skip 경고가 있었으나 추론은 완료됐다. 고정 checkout과 model snapshot 조합의 유지보수 위험으로 남긴다.
- 후속 GPU Adapter 테스트는 48kHz stereo PCM16 형식 계약을 통과했다. 그러나 benchmark에서 확인된 over-range 사례가 해당 테스트에서 재현됐다는 증거는 없어 clipping 해결로 보지 않는다.
- 공식 예제 결과는 한국어 노래나 사용자 음색 품질을 입증하지 않는다.

## 품질 결론

자동 검사는 실행 가능성과 파일 형식만 입증한다. 음색 유사도·발음·노래 자연스러움은 [EVAL-003](../evaluations/EVAL-003-seed-vc-listening-evaluation.md)의 사용자 청취 평가 전까지 판단하지 않는다.
