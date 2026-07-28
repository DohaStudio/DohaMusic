# 환경 변수

> 문서 목적: 서비스와 선택적 AI 실행 설정의 책임을 정의한다.
> 현재 상태: **Mock·ACE-Step Provider 변수 구현**

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

기존 DB·Storage·Worker·로그 변수는 `backend/.env.example`에서 함께 관리한다. 애플리케이션은 `.env`를 자동 로드하지 않는다. 빈 ACE-Step 경로는 Mock 사용에 영향을 주지 않으며, `ace_step` Job이 실행될 때 명시적 설정 오류가 된다. 경로·prompt·lyrics·비밀 값은 로그에 출력하지 않는다.
