# EXP-002: ACE-Step 품질 기반·재현성·반복 안정성 검증

> 상태: **기술 검증 완료 / [사용자 평가 필요]**
> 실험일: 2026-07-29 (Asia/Seoul)
> 브랜치: `test/ace-step-quality-evaluation`
> 관련 커밋: `test: ACE-Step 품질 및 반복 추론 평가`
> 관련 PR: develop 대상 Phase 2.5 PR(GitHub 이력 참조)

## 1. 목적

EXP-001에서 성공한 ACE-Step 1.5 2B Turbo를 같은 RTX 3060 Ti 8GB에서 반복 실행해 Seed 재현성, 다양성, 상주 안정성, 0.6B LM 실행 가능성과 운영 방식을 판단했다. 실제 청감 품질은 Codex가 판정하지 않고 [EVAL-001](../evaluations/EVAL-001-ace-step-listening-evaluation.md)에 사용자 입력란을 제공한다.

## 2. EXP-001 확인

Instrumental·한국어 가사·Backend 출력 WAV, 각 `metadata.json`과 `runtime.log`가 모두 로컬에 존재했다. 불필요한 재생성은 하지 않았다. EXP-001의 한국어 no-LM 기준은 20초, Seed 20260729, 로드 41.516초, 추론 23.730초, Torch peak allocated 3,157.45MiB였다.

## 3. 모델·환경·설정

| 항목 | 값 |
|---|---|
| ACE-Step | 1.5 v0.1.8, commit `dce621408bee8c31b4fcf4811682eb9359e1bc94` |
| DiT | `acestep-v15-turbo` 2B |
| GPU | RTX 3060 Ti 8,192MiB, driver 610.62 |
| Python / Torch | 3.12.5 / 2.7.1+cu128 격리 환경 |
| 공통 설정 | INT8 weight-only, CPU·DiT offload, batch 1, 8 steps, compile false |
| 입력 | EXP-001 한국어 prompt·lyrics, 20초 |
| LM 비교 | 없음 vs `acestep-5Hz-lm-0.6B`, PyTorch backend, LM CPU offload |

0.6B LM은 공식 CLI로 23개 파일, 1.278GiB를 ignored checkpoint에 받았다. 공식 v0.1.8 GPU 설정은 6–8GB Tier 3에서 이 모델과 batch 1~2를 지원한다. 모델·음원·runtime log는 Git에 포함하지 않는다.

## 4. 자동화와 개인정보 보호

`run_ace_step_benchmark.py`는 한 프로세스에서 모델을 한 번 로드하고 suite의 요청을 순서대로 처리한다. 각 run에 다음을 기록한다.

- 실험·run·모델·버전·LM·Seed
- prompt·lyrics SHA-256(원문은 benchmark fixture에만 존재)
- 요청·실제 길이, 로드·추론·전체 시간
- Torch allocated/reserved, `nvidia-smi` 시스템 사용량
- process RSS와 시스템 사용 메모리의 직전·peak·직후
- 출력 상대 경로·크기·SHA-256, WAV·무음·클리핑 지표
- 성공·오류 코드·오류 유형

공식 로그의 `conditioning_text`는 필터링한다. 일반 테스트와 import는 모델을 다운로드하거나 로드하지 않는다.

## 5. 동일 Seed 재현성

Seed 20260729를 같은 프로세스에서 3회씩 두 suite, EXP-001 독립 프로세스와 비교했다.

| 판정 항목 | 결과 |
|---|---|
| WAV 파일 SHA-256 | run마다 다름 |
| WAV 형식·길이·크기 | 모두 float32, 48kHz stereo, 20초, 7,680,088 bytes |
| PCM sample SHA-256 | 모두 `ff7614d...64e173` |
| PCM 비교 | 1,920,000 samples 완전 동일, RMSE 0, 상관계수 1.0 |
| 프로세스 경계 | EXP-001·두 상주 suite 대표본도 PCM 완전 동일 |

파일 hash 차이는 WAV 컨테이너 byte 차이이며 파형 차이가 아니었다. 현재 고정 설정·ODE 경로에서 동일 Seed는 **PCM 수준 완전 재현**으로 판정한다. 다른 버전·GPU·driver까지의 재현성으로 확대하지 않는다.

## 6. 다른 Seed 다양성

| Seed | 추론 시간 | Torch peak allocated | system GPU peak | RMS | near-silence | 기계 검증 |
|---:|---:|---:|---:|---:|---:|---|
| 20260730 | 12.062초 | 3,323.32MiB | 5,087MiB | 0.124734 | 0.001227 | 통과 |
| 20260731 | 14.671초 | 3,321.29MiB | 5,093MiB | 0.123038 | 0.001645 | 통과 |
| 20260732 | 12.502초 | 3,322.33MiB | 5,087MiB | 0.119543 | 0.001127 | 통과 |

Seed 20260730과 20260731의 PCM 상관계수는 0.007995, normalized RMSE는 0.174493으로 서로 다른 파형이었다. 곡 구조·멜로디·보컬·발음 차이는 `[사용자 평가 필요]`다.

## 7. 반복 추론 안정성과 통계

같은 상주 프로세스 6회 suite를 두 번 실행해 총 12/12 성공, 실패율 0%, OOM·출력 누락·Worker 비정상 종료 0건이었다. 다음 통계는 실행 전후 메모리를 보완 기록한 두 번째 6회 suite의 작은 표본이다.

| 지표 | 최소 | 최대 | 평균 | 중앙값 | 모집단 표준편차 |
|---|---:|---:|---:|---:|---:|
| 추론 시간(초) | 11.715 | 14.671 | 12.814 | 12.282 | 1.150 |
| 총 run 시간(초) | 11.751 | 14.704 | 12.851 | 12.323 | 1.148 |
| Torch peak allocated(MiB) | 3,157.45 | 3,323.32 | 3,294.355 | 3,321.225 | 61.232 |
| `nvidia-smi` system peak(MiB) | 4,917 | 5,093 | 5,059.5 | 5,087 | 63.801 |

첫 run 뒤 Torch allocated 172.59MiB, 마지막 run 뒤 172.16MiB로 GPU allocation은 누적되지 않았다. reserved는 278→328MiB이며 중간 378MiB 후 감소해 단조 증가가 아니었다.

반면 process RSS는 첫 run 직후 7,640.25MiB에서 마지막 run 직후 21,879.38MiB로 **14,239.13MiB 증가**했다. 시스템 사용 메모리도 18,493.55→30,976.02MiB로 증가했다. 두 번째 suite 후 프로세스 종료 시 system GPU는 1,707MiB로 돌아왔다. 32GB 호스트에서 상주 수명 동안 CPU 메모리가 지속 증가한 관찰은 운영 차단 요인이다. 정확한 원인은 공식 runtime 내부 cache 또는 객체 수명 분석이 더 필요하므로 “확정 누수”가 아니라 **누수 의심/상주 부적합**으로 판정한다.

## 8. 로딩 방식 비교

| 항목 | 작업별 격리 subprocess | 상주 프로세스 |
|---|---|---|
| 첫 요청 | EXP-001 65.410초(로드 포함) | 보완 suite 로드 8.590 + 첫 추론 14.100초; cold suite는 19.374 + 23.761초 |
| 이후 요청 | 매번 로드 비용 | warm 11.715~14.671초 |
| GPU | 종료 시 회수 확인 | run 후 allocated 약 172~174MiB로 안정 |
| CPU RAM | 프로세스 종료로 회수 | 6회 동안 RSS 약 14.2GiB 증가 |
| 장애 격리 | Job 단위로 명확 | 상주 프로세스 복구·health 필요 |
| 결론 | **현재 채택 유지** | 속도 이점은 있으나 현재 보류 |

정확성·안정성 우선 원칙에 따라 현재 Adapter의 작업별 subprocess를 유지한다. 상주 방식은 메모리 증가 원인 해결과 장기 soak test 후 재검토한다.

## 9. 0.6B LM 비교

| 항목 | no LM, warm 대표 | 0.6B LM(PyTorch) |
|---|---:|---:|
| 모델 로드 | suite 전체 8.590초(캐시 영향) | 81.857초 |
| 추론 | 11.715~14.671초 | 56.856초 |
| Torch peak allocated | 최대 3,323.32MiB | 3,455.66MiB |
| Torch peak reserved | 최대 3,408MiB | 3,472MiB |
| system GPU peak | 최대 5,093MiB | 5,163MiB |
| process RSS peak | 최대 22,791.11MiB(6회) | 14,212.48MiB(1회) |
| 출력 | 20초, 48kHz stereo, non-silent, clip 0 | 동일 기계 조건 통과 |
| no-LM 대비 파형 | 기준 | 상관 0.084615, RMSE 0.129091 |

0.6B LM 실행 가능성은 확인했지만 1회 표본이고 약 4배 이상 느린 추론이다. 한국어 가사 일치·프롬프트 반영이 개선되는지는 `[사용자 평가 필요]`이므로 Backend 기본 구성에 추가하지 않는다.

## 10. 출력 검증

새 출력 13개(두 6회 suite + LM 1회)는 모두 존재하고 0 byte가 아니며 float32 WAV, 48kHz, stereo, 요청과 같은 20초였다. peak 0.891251, clipped ratio 0, non-silent true였다. 이는 파일 무결성 판정일 뿐 음악 품질 합격이 아니다.

로컬 결과 경로:

```text
backend/storage/experiments/EXP-002/resident/
backend/storage/experiments/EXP-002/resident-memory/
backend/storage/experiments/EXP-002/lm-0.6b/
```

## 11. 오류·복구 검증

일반 테스트에서 잘못된 runtime·모델 variant, 지원하지 않는 Provider, 출력 디렉터리 실패, 파일 미생성, 모델 로드·OOM 오류 변환, subprocess 비정상 종료·timeout, 빈 prompt·잘못된 길이를 검증했다. 실제 OOM은 의도적으로 발생시키지 않았다. 모델이 없는 LM 구성은 benchmark setup에서 `AI_MODEL_NOT_FOUND`로 분류한다.

## 12. 결정

- ACE-Step 기술 반복 검증: **완료**
- 동일 Seed 재현성: **PCM 수준 완전 동일(현재 고정 환경)**
- 다른 Seed 다양성: **서로 다른 파형 확인**
- 0.6B LM: **실행 가능, 품질 이점 미확정, 기본 구성 보류**
- 런타임 수명: **작업별 격리 subprocess 유지**
- ACE-Step 기본 Provider: **보류**, `DOHAMUSIC_MUSIC_GENERATOR=mock` 유지
- 수동 청취 품질: **[사용자 평가 필요]**

## 13. 발견한 문제와 후속 작업

1. 상주 프로세스의 CPU RSS가 6회 동안 약 14.2GiB 증가했다. 공식 runtime 객체·cache 원인 분석과 20회 이상 soak test가 필요하다.
2. WAV 파일 hash는 PCM이 같아도 달랐다. 재현성 판정은 컨테이너와 sample hash를 분리해야 한다.
3. 0.6B LM은 동작하지만 단일 표본이며 느리다. EVAL-001 청취 결과 없이는 이점이 없다.
4. 사용자가 EVAL-001을 작성한 뒤 ADR-006과 모델 선정 상태를 재검토한다.

## 14. Dance Pop Evaluation Plan

DohaMusic 제품 대표 시나리오는 Korean Dance Pop으로 전환한다. EXP-002의 Korean Ballad 결과와 수치는 기존 실험 사실로 보존하며 Instrumental·Ballad는 보조 비교군으로 사용한다.

- 0.6B LM을 한국어 가창 우선 후보로 사용한다.
- 동일 Prompt·Lyrics·모델 설정에서 120~128 BPM, 60~90초, Seed 3개 이상을 비교한다.
- 리듬감, Kick, Bass, Dance Groove, Energy, Verse·Pre-Chorus·Chorus 구조, Hook 기억성, 보컬 선명도, 한국어 발음, 춤 가능성을 평가한다.
- 후속 Voice Conversion 입력에 필요한 보컬 분리 가능성·선명도·안정성을 함께 판정한다.
- 현재 Phase 2는 Base Model 평가 범위이며 Dance 스타일 LoRA는 적용하지 않는다. LoRA와 권리 확보 Style Dataset은 Phase 7 이후 검토한다.
- 계획 단계이므로 새 결과·점수·성능·Provider 승인을 주장하지 않는다.
