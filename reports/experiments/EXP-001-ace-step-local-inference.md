# EXP-001: ACE-Step 로컬 추론 및 Adapter 연결 검증

> 상태: **기술 검증 성공 / 수동 청취 평가 필요**
> 실행일: 2026-07-29 (Asia/Seoul)
> 브랜치: `feat/ace-step-local-inference`
> 관련 커밋: `feat: ACE-Step 로컬 추론 검증 및 어댑터 기반 추가`
> 관련 PR: develop 대상 Phase 2 PR(GitHub 이력 참조)

## 1. 목적과 판정 범위

ACE-Step을 제품 모델로 즉시 채택하는 것이 아니라 다음 사실을 실제 로컬 실행으로 검증했다.

1. 공식 버전을 격리 설치할 수 있는가.
2. RTX 3060 Ti 8GB에서 instrumental과 한국어 가사 입력이 WAV를 생성하는가.
3. 시간·VRAM·RAM과 결과 신호를 재현 가능하게 기록할 수 있는가.
4. 기존 `MusicGenerator` 경계를 깨지 않고 Backend Job에 연결할 수 있는가.

발음, 가사 정렬, 음악성, 청감 잡음은 직접 청취 없이는 판정하지 않았다.

## 2. 공식 근거와 고정 버전

- 소스: [ACE-Step 1.5 공식 저장소](https://github.com/ace-step/ACE-Step-1.5)
- 릴리스: [v0.1.8](https://github.com/ace-step/ACE-Step-1.5/releases/tag/v0.1.8)
- commit: `dce621408bee8c31b4fcf4811682eb9359e1bc94`
- 설치: [공식 INSTALL](https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/docs/en/INSTALL.md)
- 추론 API: [공식 INFERENCE](https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/docs/en/INFERENCE.md)
- 저 VRAM 지침: [공식 GPU_COMPATIBILITY](https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/docs/en/GPU_COMPATIBILITY.md)
- 논문: [arXiv:2602.00744](https://arxiv.org/abs/2602.00744)

모델은 ACE-Step 1.5 2B Turbo(`acestep-v15-turbo`)다. main bundle에 포함된 1.7B LM은 로드하지 않았고 별도 0.6B LM도 사용하지 않았다. `thinking=False`인 DiT-only 경로를 사용했다.

## 3. 로컬 환경

| 항목 | 값 |
|---|---|
| OS | Windows 11 Pro 64-bit, 10.0.26200 |
| CPU | 로컬 Windows 호스트 CPU |
| 시스템 RAM | 31.75 GiB, 시작 시 여유 10.68 GiB |
| GPU | NVIDIA GeForce RTX 3060 Ti, 8,192 MiB |
| Driver / CUDA driver | 610.62 / 13.3 |
| 시스템 Python | 3.12.5 |
| 기존 전역 Torch | 2.7.1+cu118 |
| 격리 Torch | 2.7.1+cu128 |
| 격리 라이브러리 | torchaudio 2.7.1+cu128, torchvision 0.22.1+cu128, transformers 4.57.6, diffusers 0.37.1 |
| 격리 도구 | uv 0.12.0 |
| 저장 공간 | D: 여유 1,464.55 GiB |
| FFmpeg | 미설치 — WAV만 검증 |

실행 전 `nvidia-smi` 전체 사용량은 약 1,825 MiB였고 사용 가능한 VRAM은 약 6,200 MiB였다. 사용자 프로세스를 종료하지 않았다.

## 4. 설치와 재현 방식

공식 저장소를 ignored 경로 `.ace-step-runtime/ACE-Step-1.5`에 v0.1.8 shallow clone했다. 공식 `uv.lock`으로 `uv sync --frozen`을 실행했다. 첫 실행은 cache가 다른 volume에 있어 hardlink/copy 단계에서 187초 후 실패했다. 생성 중이던 해당 `.venv`만 제거하고 cache를 저장소와 같은 D: ignored 경로로 옮겨 `UV_LINK_MODE=hardlink`로 재실행했으며 173.3초에 성공했다.

공식 `acestep-download --model main`으로 bundle을 받았다. 약 180.01초, 9.4 GiB, 28개 파일이었다. 격리 환경은 약 6.08 GiB다. 모델·venv·cache·출력 오디오는 Git에서 제외했다.

실행기는 모델을 자동 다운로드하지 않는다. 필요한 로컬 경로와 실행 설정을 `DOHAMUSIC_AI_ACE_STEP_*` 환경 변수로 받아 공식 `AceStepHandler`와 `generate_music` API를 호출한다.

검증에 사용한 명령 형태는 다음과 같다. `<...>`는 Git에 기록하지 않는 로컬 ignored 경로다.

```powershell
git clone --depth 1 --branch v0.1.8 https://github.com/ace-step/ACE-Step-1.5 <ace-step-root>
uv sync --frozen --project <ace-step-root>
<ace-step-python> -m acestep.model_downloader --model main --dir <checkpoint-root>

$env:DOHAMUSIC_AI_ACE_STEP_PROJECT_ROOT='<ace-step-root>'
$env:DOHAMUSIC_AI_ACE_STEP_CHECKPOINT_PATH='<checkpoint-root>'
$env:DOHAMUSIC_AI_ACE_STEP_MODEL_VARIANT='acestep-v15-turbo'
$env:DOHAMUSIC_AI_ACE_STEP_MODEL_VERSION='v0.1.8'
$env:DOHAMUSIC_AI_ACE_STEP_DEVICE='cuda'
$env:DOHAMUSIC_AI_ACE_STEP_QUANTIZATION='int8_weight_only'
$env:DOHAMUSIC_AI_ACE_STEP_CPU_OFFLOAD='true'
$env:DOHAMUSIC_AI_ACE_STEP_DIT_CPU_OFFLOAD='true'
<ace-step-python> ai_worker/scripts/run_ace_step_smoke_test.py --request-json ai_worker/benchmarks/instrumental.json --output-dir <experiment-output>
```

다운로드는 공식 CLI executable `acestep-download --model main --dir <checkpoint-root>`로 수행했다. 위 모듈 호출은 같은 공식 entry point의 재현 형태다. 토큰이나 비밀 값은 사용·기록하지 않았다.

## 5. 안전 설정

| 설정 | 값 | 이유 |
|---|---|---|
| variant | `acestep-v15-turbo` | 공식 6~8GB 권고의 2B Turbo |
| LM | 사용 안 함 | 가용 VRAM 보수적 운용 |
| quantization | `int8_weight_only` | 저 VRAM 권고 |
| CPU offload / DiT offload | 둘 다 true | GPU 여유 확보 |
| batch / steps | 1 / 8 | smoke 및 Turbo 기본 경로 |
| compile | false | Windows 추가 compiler·메모리 변수를 배제 |
| output | WAV, 48kHz stereo | FFmpeg 없이 검증 가능한 공식 출력 |

공식 의존성 조합에서 `torchao 0.16.0` C++ extension 호환 경고와 training 모듈의 bitsandbytes 미설치 경고가 출력됐지만 INT8 적용 로그가 확인됐고 세 실행은 성공했다. 추론 실패로 분류하지 않았으며 공식 버전 변경 시 재검토한다.

## 6. 시나리오와 결과

입력은 `ai_worker/benchmarks`의 고정 JSON에 있다. 실제 오디오·runtime log·metadata는 `backend/storage/experiments/EXP-001`에 로컬 보관하며 커밋하지 않는다.

Instrumental prompt는 `calm lo-fi instrumental, soft piano, warm bass, slow tempo, no vocals, suitable for a late-night coding session`이고 가사는 없다. 한국어 prompt는 `감성적인 한국어 팝 발라드, 잔잔한 피아노와 스트링, 여성 솔로 보컬, 따뜻하지만 쓸쓸한 분위기`이며 입력 가사는 다음과 같다.

```text
[Verse]
조용한 밤이 다시 찾아오면
남겨진 기억을 따라 걸어가

[Chorus]
다시 너를 부를 수 있다면
멈춘 계절도 돌아올까
```

| 지표 | A: Instrumental | B: 한국어 가사 | C: Backend Adapter |
|---|---:|---:|---:|
| 요청/실제 길이 | 15/15초 | 20/20초 | 10/10초 |
| Seed | 20260729 | 20260729 | 고정 입력 |
| 모델 로드 | 36.260초 | 41.516초 | 34.297초 |
| 추론 | 32.167초 | 23.730초 | 23.717초 |
| 전체 | 68.776초 | 65.410초 | 58.171초 |
| Torch peak allocated | 3,149.75 MiB | 3,157.45 MiB | 3,147.36 MiB |
| Torch peak reserved | 3,224 MiB | 3,232 MiB | 3,220 MiB |
| `nvidia-smi` system peak | 5,081 MiB | 4,950 MiB | 5,008 MiB |
| process peak RSS | 13,357.79 MiB | 13,298.60 MiB | 13,346.75 MiB |
| WAV 크기 | 5,760,088 bytes | 7,680,088 bytes | 3,840,088 bytes |
| 결과 | 성공 | 성공 | Job `COMPLETED` |

단독 출력 위치는 로컬 ignored `backend/storage/experiments/EXP-001/<case>/`이고 Backend 출력은 `backend/storage/outputs/<job-id>/`이다. 형식은 모두 WAV이며 Git에는 포함하지 않았다.

Backend 실험 Job ID는 `acb52490-a6e6-455e-9576-d447b3c76321`이다. API 생성 요청, ThreadPool Worker, ACE-Step subprocess, `generated_files` 등록과 조회까지 실제 경로로 완료됐다.

## 7. 객관적 오디오 신호

| 지표 | Instrumental | 한국어 가사 |
|---|---:|---:|
| Sample rate / channels | 48,000 / 2 | 48,000 / 2 |
| Peak | 0.891251 | 0.891251 |
| RMS | -22.647 dBFS | -20.897 dBFS |
| Near-silence ratio | 0.002974 | 0.002192 |
| Clipped sample ratio | 0 | 0 |
| 비무음 판정 | true | true |

이 값은 유효하고 비무음인 WAV가 생성됐다는 근거다. 음악성이나 보컬 품질을 뜻하지 않는다.

## 8. 한국어·품질 평가

한국어 프롬프트와 가사가 공식 API에 전달되고 20초 WAV가 생성된 사실은 확인했다. 그러나 다음은 모두 `[수동 청취 평가 필요]`다.

- 실제 보컬 존재와 한국어 발음
- 가사 누락·치환·반복·시간 정렬
- 장르·분위기와 곡 구조
- 보컬/반주 균형과 청감 음질
- 클릭·왜곡·금속성 잡음·끝부분 절단

따라서 “한국어 품질 통과” 또는 “제품 사용 가능”으로 결론내리지 않는다.

| 주관 평가 항목 | 1~5점 | 상태 |
|---|---:|---|
| 한국어 발음 | 미평가 | 수동 청취 필요 |
| 가사 일치 | 미평가 | 수동 청취 필요 |
| 보컬 자연스러움 | 미평가 | 수동 청취 필요 |
| 음악 구조 | 미평가 | 수동 청취 필요 |
| 프롬프트 반영 | 미평가 | 수동 청취 필요 |
| 노이즈 수준 | 미평가 | 수동 청취 필요 |
| 전체 활용 가능성 | 미평가 | 수동 청취 필요 |

점수는 청취자가 1점(사용 불가)부터 5점(매우 양호)으로 기록해야 하며 주관 평가임을 함께 표시한다.

## 9. Backend Adapter 검증

Provider Factory의 기본값은 `mock`이다. `ace_step`을 선택해도 Backend가 공식 패키지를 import하지 않으며 실제 Job에서만 설치와 경로를 검증한다. 공통 입력을 runner JSON으로 변환하고 결과를 `GenerationResult`로 복원했다. 모델·환경이 없으면 Backend import가 아니라 해당 Job만 안정적 `AI_*` 오류로 실패한다.

단독 실행 두 건과 Backend 실행 한 건은 모두 별도 프로세스였고 각 종료 후 다음 실행이 성공했다. 이는 프로세스 종료 기반 해제 경로의 실용성을 보이지만, 상주 Worker에서 연속 재사용하거나 메모리 누수가 없다는 검증은 아니다.

## 10. 보안·로그·라이선스

공식 라이브러리가 INFO 로그에 `conditioning_text`를 출력하는 동작을 발견했다. runner에서 해당 logger record를 필터링해 prompt·lyrics가 runtime log에 남지 않도록 했다. 임시 요청 JSON은 subprocess 완료·실패 후 삭제한다.

코드와 주 모델 카드는 MIT로 표시되고 모델 카드는 출력 상업 이용 가능 취지를 밝힌다. Qwen3 Embedding 0.6B 모델 카드는 Apache-2.0이다. 다만 학습 데이터 권리, 제3자 권리, 서비스·재배포 적합성은 `[법률 검토 필요]`다. 상세 근거는 [라이선스 검토](../../docs/01-research/licensing-review.md)에 있다.

## 11. 결론과 다음 조치

- 격리 설치, 모델 로드, 단독 추론: **성공**
- RTX 3060 Ti 8GB 단일 저 VRAM 실행: **성공**
- 한국어 입력 처리와 유효 WAV 생성: **기술적으로 성공**
- 기존 Backend Adapter 종단 간 연결: **성공**
- 한국어 발음·가사 정렬·음악성: **판정 보류 — 수동 청취 필요**
- ACE-Step 제품 기본 Provider 채택: **보류**

다음 작업은 커밋된 오디오가 아닌 로컬 EXP-001 출력의 블라인드 청취표 작성, 같은 시나리오 3회 이상 반복, 0.6B LM의 품질·자원 비교, 상주 runtime과 작업별 subprocess의 처리량 비교다. 이 결과 전에는 Phase 2 전체와 ACE-Step 도입을 완료 처리하지 않는다.

## 12. 자동 검증

- `ruff check backend ai_worker`: 통과
- `compileall backend ai_worker`: 통과
- 기본 테스트: 17 passed, 1 skipped
- opt-in `integration and gpu and slow`: 실제 설치 환경에서 1 passed, 86.14초

기본 테스트는 모델을 다운로드하거나 GPU를 사용하지 않는다. 실제 GPU 테스트는 세 로컬 경로와 `RUN_ACE_STEP_GPU_TEST=1`을 사용자가 명시한 경우에만 실행된다.
