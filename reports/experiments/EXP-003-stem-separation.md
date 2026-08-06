# EXP-003: Stem Separation 로컬 추론 및 Adapter 검증

> 실행일: 2026-07-29
> 상태: **기술 검증 완료 / 사용자 청취 평가 필요**
> 장치: NVIDIA GeForce RTX 3060 Ti 8GB, Windows 11
> 모델: HTDemucs, Demucs 4.1.0

## 목적

ACE-Step 출력과 동일한 20초 한국어 가창 WAV를 보컬과 반주로 안정적으로 분리하고, 향후 `vocals.wav → Seed-VC` 연결에 사용할 Provider-neutral Backend 경계를 검증했다. Seed-VC와 음색 변환은 실행하지 않았다.

## 공식 근거와 선정

- 유지보수 저장소: [adefossez/demucs](https://github.com/adefossez/demucs)
- 고정 릴리스: [Demucs 4.1.0](https://github.com/adefossez/demucs/releases/tag/v4.1.0)
- 패키지: [PyPI demucs 4.1.0](https://pypi.org/project/demucs/)
- 가중치 표시: [HTDemucs 모델 카드](https://huggingface.co/adefossez/HTDemucs)

공식 문서의 기본 모델인 `htdemucs`를 선택했다. `htdemucs_ft`는 더 나을 수 있으나 공식 설명상 약 4배 느려 첫 Backend 기준으로 제외했다. 보컬 2-stem 출력, CUDA와 `segment` 저 VRAM 옵션이 공식 지원되고, 코드와 사용한 HTDemucs 가중치가 모두 MIT로 표시되어 있다. 제품 법률 승인을 대신하지는 않는다.

## 고정 환경

| 항목 | 값 |
|---|---|
| Python | 3.11 격리 venv |
| Demucs | 4.1.0 |
| PyTorch / TorchAudio | 2.7.1+cu128 |
| 모델 | `htdemucs` |
| 모델 snapshot | `bf35a81b663819a8255c8fefee17f9d812b786b5` |
| 장치 | `cuda` |
| segment / shifts / overlap | 7초 / 1 / 0.25 |
| 입력 | EXP-001 한국어 가창, 20초, 48kHz Stereo |
| 네트워크 | `HF_HUB_OFFLINE=1`, 자동 다운로드 없음 |

## 단독 추론

공식 CLI 1회와 DohaMusic runner 1회가 모두 성공했다. Runner는 공식 `demucs.api.Separator`로 4개 source를 얻고 `vocals` 외 source를 합산해 instrumental을 만든 뒤 두 출력을 48kHz Stereo IEEE float32로 저장했다.

단독 runner에서 순수 분리 4.128초, Torch allocated peak 551.14MiB, `nvidia-smi` peak 2,529MiB, process RSS peak 1,532.78MiB를 확인했다.

## 3회 Benchmark

`ai_worker/scripts/run_demucs_benchmark.py`를 이용해 동일 입력을 격리 subprocess로 3회 실행했다.

| 지표 | 결과 |
|---|---:|
| 성공률 | 3/3, 100% |
| 모델 load 평균 | 1.648초 |
| 순수 분리 평균 | 3.915초 |
| subprocess 전체 평균 | 9.381초 |
| Torch allocated peak | 551.14MiB |
| Torch reserved peak | 802.00MiB |
| `nvidia-smi` peak 평균 | 2,555.67MiB |
| process RSS peak 평균 | 1,511.07MiB |
| CPU 사용률 peak 평균 | 555.57% |
| CPU time 평균 | 13.490초 |
| 출력 크기 | Stem별 7,680,088 bytes |
| 출력 길이 | Stem별 20.000초 |

`nvidia-smi`는 GPU 전체 사용량이므로 프로세스 전용 VRAM으로 해석하지 않는다. CPU 사용률은 다중 코어 합산이어서 100%를 넘을 수 있다. 로컬 원시 결과는 ignored `backend/storage/experiments/EXP-003/benchmark-result.json`에 저장했다.

## 자동 품질 검증

두 출력 모두 존재하고 48kHz, Stereo, 20.000초, float32이며 clipping sample ratio는 0이었다. RMS 기준 두 파일 모두 비무음으로 판정됐다. 단독 runner 표본에서 vocals RMS는 0.001178, instrumental RMS는 0.090239였다. 보컬 에너지가 매우 낮은 사실만 기록하며, 분리 품질이나 활용 가능성을 Codex가 점수화하지 않는다.

## Backend 연결

실제 GPU opt-in 통합 테스트가 `POST /api/stems` → `StemService` → 공유 ThreadPool → `StemWorker` → `DemucsAdapter` → 격리 runner → `stem_jobs`·`stem_files` → 조회 API를 통과했다. 결과는 `vocals`, `instrumental`, `metadata` 세 파일로 등록됐다. 일반 환경의 기본 Provider는 `mock`이며 실제 Demucs는 명시 설정해야 실행된다.

## 판정

- HTDemucs 기술 실행과 Backend Adapter: **완료**
- RTX 3060 Ti 8GB 단일 Worker 적용 가능성: **확인**
- Stem 청취 품질과 Seed-VC 투입 적합성: **사용자 평가 필요**
- Seed-VC 구현: **이번 범위 제외**

수동 평가는 [EVAL-002](../evaluations/EVAL-002-stem-separation-listening-evaluation.md), 구조 결정은 [ADR-008](../../docs/11-decisions/ADR-008-stem-separation-provider.md)을 따른다.
