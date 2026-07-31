# 환경 변수

> 문서 목적: 서비스와 선택적 AI 실행 설정의 책임을 정의한다.
> 현재 상태: **Mock·선택적 AI·Lyrics Provider·Pipeline 변수 구현**

| 변수 | 용도 | 기본값 |
|---|---|---|
| `NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH` | Frontend의 개발용 Voice 서버 경로 form 노출. 운영 활성화 금지 | `false` |
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
| `DOHAMUSIC_VOICE_PROVIDER` | `mock` 또는 `seed_vc` | `mock` |
| `MOCK_VOICE_DELAY_SECONDS` | Mock Voice 지연 | `0.1` |
| `DOHAMUSIC_VOICE_SEED_VC_RUNTIME_PYTHON` | 격리 Seed-VC Python | 빈 값 |
| `DOHAMUSIC_VOICE_SEED_VC_RUNNER_PATH` | DohaMusic Seed-VC runner | `ai_worker/scripts/run_seed_vc_conversion.py` |
| `DOHAMUSIC_VOICE_SEED_VC_PROJECT_ROOT` | 고정 공식 checkout | 빈 값 |
| `DOHAMUSIC_VOICE_SEED_VC_CHECKPOINT_PATH` | 44k F0 checkpoint | 빈 값 |
| `DOHAMUSIC_VOICE_SEED_VC_CONFIG_PATH` | 44k F0 config | 빈 값 |
| `DOHAMUSIC_VOICE_SEED_VC_MODEL_CACHE_PATH` | 사전 준비 offline cache | 빈 값 |
| `DOHAMUSIC_VOICE_SEED_VC_MODEL_NAME` | 모델 식별자 | `seed-uvit-whisper-base-f0-44k` |
| `DOHAMUSIC_VOICE_SEED_VC_MODEL_VERSION` | 고정 commit | `51383efd...` |
| `DOHAMUSIC_VOICE_SEED_VC_DEVICE` | 실행 장치 | `cuda` |
| `DOHAMUSIC_VOICE_SEED_VC_DIFFUSION_STEPS` | 확산 step | `30` |
| `DOHAMUSIC_VOICE_SEED_VC_TIMEOUT_SECONDS` | subprocess 제한 | `1800` |
| `DOHAMUSIC_PIPELINE_VERSION` | Pipeline metadata 계약 버전 | `1` |
| `DOHAMUSIC_PIPELINE_MAX_RETRIES` | 단계별 추가 시도 횟수 | `1` |
| `DOHAMUSIC_PIPELINE_STEP_TIMEOUT_SECONDS` | Orchestrator 단계 제한 | `900` |
| `DOHAMUSIC_AUDIO_MIXER` | `default` 또는 `mock` Mixer Provider | `default` |
| `DOHAMUSIC_LYRICS_PROVIDER` | `template` 또는 `mock` Lyrics Provider | `template` |
| `DOHAMUSIC_MIXER_VOCAL_GAIN_DB` | 보컬 gain dB | `0.0` |
| `DOHAMUSIC_MIXER_INSTRUMENTAL_GAIN_DB` | 반주 gain dB | `0.0` |
| `DOHAMUSIC_MIXER_HEADROOM_DB` | 목표 peak headroom dB | `1.0` |
| `DOHAMUSIC_MIXER_NORMALIZATION` | `peak` 또는 `off` | `peak` |
| `DOHAMUSIC_MIXER_LIMITER` | `soft` 또는 `bypass` | `soft` |
| `DOHAMUSIC_MIXER_FADE_IN_MS` | 시작 linear fade | `10.0` |
| `DOHAMUSIC_MIXER_FADE_OUT_MS` | 종료 linear fade | `10.0` |

`NEXT_PUBLIC_*` 값은 browser bundle에 공개되므로 비밀을 넣지 않는다. `NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH`는 정확히 `true`일 때만 form을 노출하며 Backend path 검증이나 인증을 대체하지 않는다. 기존 DB·Storage·Worker·로그 변수는 `backend/.env.example`에서 함께 관리한다. 애플리케이션은 `.env`를 자동 로드하지 않는다. 빈 ACE-Step·Demucs 경로는 Mock 사용에 영향을 주지 않으며, 실제 Provider Job이 실행될 때 명시적 설정 오류가 된다. 경로·prompt·lyrics·비밀 값은 로그에 출력하지 않는다.

## 벤치마크 전용 변수

다음 변수는 `ai_worker/scripts/run_ace_step_benchmark.py`에서만 읽는다. Backend `Settings`와 `.env.example`의 운영 기본값에는 포함하지 않는다.

| 변수 | 용도 | 기본값 |
|---|---|---|
| `DOHAMUSIC_AI_ACE_STEP_LM_MODEL` | 비교 실험용 LM 모델 식별자 또는 로컬 경로 | 빈 값(no LM) |
| `DOHAMUSIC_AI_ACE_STEP_LM_BACKEND` | 비교 실험용 LM 실행 backend | `pt` |

벤치마크 실행기는 모델을 자동 다운로드하지 않는다. LM 비교는 공식 설치 도구로 사용자가 준비한 로컬 모델만 사용하며, 모델 파일과 실험 WAV는 Git에 포함하지 않는다.
# External Lyrics 설정

`DOHAMUSIC_LYRICS_PROVIDER` 기본값은 `template`이다. `openai`를 명시 선택할 때만 API Key가 필수다. 모델·base URL·timeout·전체 deadline·retry·temperature·output token·입출력 단가·가격 버전·요청별 비용 한도는 모두 `DOHAMUSIC_LYRICS_*` 환경 변수로 관리한다. 실제 값과 운영 절차는 [External Lyrics Provider 설정](external-lyrics-provider-setup.md)을 따른다.
