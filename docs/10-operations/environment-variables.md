# 환경 변수

> 문서 목적: 서비스와 선택적 AI 실행 설정의 책임을 정의한다.
> 현재 상태: **Mock·ACE-Step·Demucs Provider 변수 구현**

| 변수 | 용도 | 기본값 |
|---|---|---|
| `DOHAMUSIC_MUSIC_GENERATOR` | `mock` 또는 `ace_step` | `mock` |
| `DOHAMUSIC_MODEL_NAME` | Mock 모델 식별자 | `mock-music-generator` |
| `DOHAMUSIC_MODEL_VERSION` | Mock 모델 버전 | `foundation-v1` |
| `DOHAMUSIC_AI_ACE_STEP_RUNTIME_PYTHON` | 격리 환경 Python 경로 | 빈 값 |
| `DOHAMUSIC_AI_ACE_STEP_RUNNER_PATH` | DohaMusic 실행기 경로 | 빈 값 |
| `DOHAMUSIC_AI_ACE_STEP_PROJECT_ROOT` | 공식 ACE-Step checkout | 빈 값 |
| `DOHAMUSIC_AI_ACE_STEP_CHECKPOINT_PATH` | 공식 model bundle 경로 | 빈 값 |
| `DOHAMUSIC_AI_ACE_STEP_MODEL_VARIANT` | DiT variant | `acestep-v15-turbo` |
| `DOHAMUSIC_AI_ACE_STEP_MODEL_VERSION` | 추적 버전 | `v0.1.8` |
| `DOHAMUSIC_AI_ACE_STEP_DEVICE` | 실행 장치 | `cuda` |
| `DOHAMUSIC_AI_ACE_STEP_QUANTIZATION` | 양자화 | `int8_weight_only` |
| `DOHAMUSIC_AI_ACE_STEP_CPU_OFFLOAD` | CPU offload | `true` |
| `DOHAMUSIC_AI_ACE_STEP_DIT_CPU_OFFLOAD` | DiT CPU offload | `true` |
| `DOHAMUSIC_AI_ACE_STEP_TIMEOUT_SECONDS` | subprocess 제한 | `900` |
| `DOHAMUSIC_STEM_PROVIDER` | `mock` 또는 `demucs` | `mock` |
| `MOCK_STEM_DELAY_SECONDS` | Mock Stem 지연 | `0.1` |
| `DOHAMUSIC_STEM_DEMUCS_RUNTIME_PYTHON` | 격리 Demucs Python 경로 | 빈 값 |
| `DOHAMUSIC_STEM_DEMUCS_RUNNER_PATH` | DohaMusic Demucs runner | `ai_worker/scripts/run_demucs_separation.py` |
| `DOHAMUSIC_STEM_DEMUCS_MODEL_CACHE_PATH` | 사전 설치 HTDemucs cache | 빈 값 |
| `DOHAMUSIC_STEM_DEMUCS_MODEL_NAME` | 모델 이름 | `htdemucs` |
| `DOHAMUSIC_STEM_DEMUCS_MODEL_VERSION` | 추적 버전 | `4.1.0` |
| `DOHAMUSIC_STEM_DEMUCS_DEVICE` | 실행 장치 | `cuda` |
| `DOHAMUSIC_STEM_DEMUCS_SEGMENT_SECONDS` | 저 VRAM segment | `7.0` |
| `DOHAMUSIC_STEM_DEMUCS_SHIFTS` | shift 수 | `1` |
| `DOHAMUSIC_STEM_DEMUCS_OVERLAP` | segment overlap | `0.25` |
| `DOHAMUSIC_STEM_DEMUCS_TIMEOUT_SECONDS` | subprocess 제한 | `900` |

기존 DB·Storage·Worker·로그 변수는 `backend/.env.example`에서 함께 관리한다. 애플리케이션은 `.env`를 자동 로드하지 않는다. 빈 ACE-Step·Demucs 경로는 Mock 사용에 영향을 주지 않으며, 실제 Provider Job이 실행될 때 명시적 설정 오류가 된다. 경로·prompt·lyrics·비밀 값은 로그에 출력하지 않는다.

## 벤치마크 전용 변수

다음 변수는 `ai_worker/scripts/run_ace_step_benchmark.py`에서만 읽는다. Backend `Settings`와 `.env.example`의 운영 기본값에는 포함하지 않는다.

| 변수 | 용도 | 기본값 |
|---|---|---|
| `DOHAMUSIC_AI_ACE_STEP_LM_MODEL` | 비교 실험용 LM 모델 식별자 또는 로컬 경로 | 빈 값(no LM) |
| `DOHAMUSIC_AI_ACE_STEP_LM_BACKEND` | 비교 실험용 LM 실행 backend | `pt` |

벤치마크 실행기는 모델을 자동 다운로드하지 않는다. LM 비교는 공식 설치 도구로 사용자가 준비한 로컬 모델만 사용하며, 모델 파일과 실험 WAV는 Git에 포함하지 않는다.
