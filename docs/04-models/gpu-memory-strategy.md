# GPU 메모리 전략

> 문서 목적: RTX 3060 Ti 8GB 환경의 실측·실패·완화 원칙을 정의한다.
> 현재 상태: **ACE-Step 단일 작업 저 VRAM 설정 검증**

ACE-Step 1.5 공식 [GPU 호환성 문서](https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/docs/en/GPU_COMPATIBILITY.md)의 6~8GB 권고를 기반으로 2B Turbo, LM 비활성화, INT8 weight-only, CPU/DiT offload, batch 1, 8 steps를 사용했다.

| 실행 | 길이 | Torch peak allocated | Torch peak reserved | `nvidia-smi` 시스템 peak |
|---|---:|---:|---:|---:|
| Instrumental 단독 | 15초 | 3,149.75 MiB | 3,224 MiB | 5,081 MiB |
| 한국어 가사 단독 | 20초 | 3,157.45 MiB | 3,232 MiB | 4,950 MiB |
| Backend Adapter | 10초 | 3,147.36 MiB | 3,220 MiB | 5,008 MiB |

`nvidia-smi` 값은 같은 GPU를 쓰는 전체 시스템 사용량이며 프로세스 전용 값이 아니다. 측정 당시 다른 그래픽 사용량이 있어 Torch 측정과 함께 해석한다. 8GB에서 단일 실행은 성공했지만 여유를 제품 동시성 근거로 확대 해석하지 않는다. GPU 동시성은 1, OOM은 `AI_OUT_OF_MEMORY`, 다른 GPU 프로세스 강제 종료는 금지한다.
