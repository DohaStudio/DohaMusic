# EXP-004 — Seed-VC 로컬 추론

> 실행일: 2026-07-29
> 결과: 기술 추론 성공, 품질·운영 채택 보류

## 환경

- GPU: NVIDIA GeForce RTX 3060 Ti 8GB
- Driver: 610.62
- Python: 3.11.9
- Torch: 2.7.1+cu128 (공식 요구 파일의 Torch 2.4 Windows DLL 문제로 호환 변경)
- Seed-VC commit: `51383efd921027683c89e5348211d93ff12ac2a8`
- Model: `seed-uvit-whisper-base-f0-44k`, official model snapshot `257283f9f41585055e8f858fba4fd044e5caed6e`
- 설정: CUDA, FP16, F0 condition, 30 diffusion steps, length 1.0, CFG 0.7
- 입력: 공식 저장소 예제 source 12.479초 / reference 14.597초

개인 음성·체크포인트·생성 WAV는 커밋하지 않았다.

## 결과

| Run | 성공 | 총 시간 | peak VRAM | peak process RAM | CPU peak | 출력 길이 | clipping |
|---|---|---:|---:|---:|---:|---:|---|
| 1 | 예 | 26.172초 | 5,068MB | 3,034.9MB | 290.7% | 12.469초 | 감지 |
| 2 | 예 | 26.941초 | 5,069MB | 3,032.6MB | 234.0% | 12.469초 | 감지 |
| 3 | 예 | 28.560초 | 5,067MB | 3,033.6MB | 118.1% | 12.469초 | 감지 |

- 성공률: 3/3, 100%
- 평균 총 시간: 27.224초
- 출력: 48kHz stereo, 비무음, 당시 float WAV 4,788,232 bytes
- 후속 통합 테스트부터 PCM16으로 고정했으며 GPU Adapter 테스트가 통과했다.

## 관찰과 오류

- 최초 requirements 설치는 비표준 Torch 옵션 줄과 Windows `webrtcvad` 빌드 때문에 실패했다. CUDA wheel과 `webrtcvad-wheels`로 격리 설치했다.
- Torch 2.4 CUDA wheel은 현재 Windows에서 `fbgemm.dll`을 로드하지 못해, 기존 장비에서 검증된 2.7.1+cu128로 변경했다.
- 공식 모델 로드 시 일부 shape mismatch skip 경고가 있었으나 추론은 완료됐다. 공식 checkout과 model snapshot 조합의 유지보수 위험으로 기록한다.
- 3회 모두 clipping 경고가 있어 후처리 정책과 청취 영향 검토가 필요하다.
- 공식 예제이므로 한국어 노래·사용자 음색 품질을 입증하지 않는다.
