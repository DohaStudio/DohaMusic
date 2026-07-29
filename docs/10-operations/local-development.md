# 로컬 개발 환경

> 문서 목적: Backend와 선택적 AI 런타임을 재현 가능하게 분리한다.
> 현재 상태: **Backend·ACE-Step·Demucs 격리 실행 절차 검증**

## Backend

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m alembic -c backend/alembic.ini upgrade head
python -m pytest -q
python -m backend.scripts.benchmark_pipeline
python -m backend.scripts.benchmark_audio_mixer
python -m backend.scripts.benchmark_lyrics
python -m uvicorn backend.main:app --reload
```

Backend 설치에는 Mixer용 NumPy·SciPy와 resource 측정용 psutil이 포함된다. 기본 `DOHAMUSIC_AUDIO_MIXER=default`는 별도 AI·FFmpeg 설치 없이 실제 WAV를 합성한다. `mock`은 Pipeline 격리·회귀 검증에서만 명시적으로 선택한다. DSP 기본 정책과 제한은 [Audio Quality Engine](../03-architecture/audio-quality-engine.md), 실측은 [EXP-006](../../reports/experiments/EXP-006-audio-mixing.md)을 따른다.

Lyrics 기본값 `DOHAMUSIC_LYRICS_PROVIDER=template`은 외부 API·Key·모델 설치 없이 한국어·영문 구조 초안을 만든다. 실제 LLM이 아니며 품질 승인을 의미하지 않는다. API 계약은 [Lyrics API](../06-api/lyrics-api.md), 실측은 [EXP-007](../../reports/experiments/EXP-007-lyrics-generation.md)을 따른다.

## 선택적 ACE-Step 런타임

공식 [v0.1.8 설치 문서](https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/docs/en/INSTALL.md)는 Python 3.11~3.12와 `uv sync`를 안내한다. 공식 저장소를 별도 디렉터리에 v0.1.8로 checkout하고 그 저장소의 lockfile로 환경을 만든다. 모델은 공식 CLI로 사용자가 명시적으로 내려받는다. DohaMusic 실행기와 테스트는 다운로드를 시작하지 않는다.

검증 환경은 다음과 같았다.

- Windows 11 Pro 64-bit, Python 3.12.5
- NVIDIA RTX 3060 Ti 8GB, driver 610.62
- ACE-Step v0.1.8 commit `dce621408bee8c31b4fcf4811682eb9359e1bc94`
- 격리 환경: torch 2.7.1+cu128, transformers 4.57.6, diffusers 0.37.1
- 공식 main bundle 약 9.4 GiB, 격리 환경 약 6.08 GiB

`backend/.env.example`의 `DOHAMUSIC_AI_ACE_STEP_*` 경로를 로컬 절대 경로로 설정하고 `DOHAMUSIC_MUSIC_GENERATOR=ace_step`을 선택한다. 기본값 `mock`은 AI 설치 없이 동작한다. 실제 GPU 통합 테스트는 모델을 설치한 환경에서만 `RUN_ACE_STEP_GPU_TEST=1`과 `pytest -m "integration and gpu and slow"`로 명시 실행한다.

반복 benchmark는 `ai_worker/scripts/run_ace_step_benchmark.py`에 `quality-resident.json` 같은 suite를 명시해 실행한다. `benchmark`, `gpu`, `slow`, `integration` 작업은 opt-in이며 일반 `pytest`에서 모델을 로드하지 않는다. 0.6B LM 비교는 공식 모델을 사용자가 먼저 설치하고 benchmark 환경에 `DOHAMUSIC_AI_ACE_STEP_LM_MODEL=acestep-5Hz-lm-0.6B`, backend `pt`를 명시한 경우에만 실행한다. 이 LM 변수는 제품 Backend 설정이 아니다.

실험 WAV·로그·모델·runtime은 Git 제외 대상이다. FFmpeg는 검증 PC에 없었으므로 WAV만 확인했으며 MP3/AAC는 검증하지 않았다. 설치·연결은 [EXP-001](../../reports/experiments/EXP-001-ace-step-local-inference.md), 반복·LM은 [EXP-002](../../reports/experiments/EXP-002-ace-step-quality-and-stability.md)에 있다.

## 선택적 Demucs 런타임

Demucs 4.1.0은 Backend와 별도 Python 3.11 환경에 설치한다. 검증 환경은 torch·torchaudio 2.7.1+cu128, `demucs==4.1.0`, `psutil`, `soundfile`이며 HTDemucs checkpoint는 사용자가 공식 배포에서 미리 준비한다. 실행 중 `HF_HUB_OFFLINE=1`을 강제하므로 자동 다운로드하지 않는다.

`backend/.env.example`의 `DOHAMUSIC_STEM_DEMUCS_*` 경로를 설정하고 `DOHAMUSIC_STEM_PROVIDER=demucs`를 선택한다. 기본값 `mock`은 Demucs 설치 없이 동작한다. 3회 반복은 `ai_worker/scripts/run_demucs_benchmark.py`, 실제 Backend E2E는 `RUN_DEMUCS_GPU_TEST=1` 및 `DEMUCS_TEST_RUNTIME_PYTHON`, `DEMUCS_TEST_MODEL_CACHE`, `DEMUCS_TEST_SOURCE_AUDIO`를 명시해 실행한다. 모델·cache·실험 WAV·원시 metadata는 Git에 포함하지 않는다. 자세한 고정 환경은 [EXP-003](../../reports/experiments/EXP-003-stem-separation.md)에 있다.

## 선택적 Seed-VC 런타임

공식 저장소를 별도 무시 경로에 checkout하고 commit `51383efd921027683c89e5348211d93ff12ac2a8`로 고정한다. Python 3.11 격리 환경과 공식 44k F0 checkpoint·config, RMVPE, CAMPPlus, Whisper-small, BigVGAN cache를 요청 처리 전에 준비한다. Windows 검증 환경은 torch 2.7.1+cu128과 `webrtcvad-wheels`를 사용했다. 공식 requirements의 비표준 옵션과 Torch 2.4 DLL 문제 때문에 이 차이를 EXP-004에 기록했다.

`backend/.env.example`의 `DOHAMUSIC_VOICE_SEED_VC_*` 절대 경로를 설정하고 `DOHAMUSIC_VOICE_PROVIDER=seed_vc`를 선택한다. Backend runner는 offline 모드로 실행되어 모델을 자동 다운로드하지 않는다. 실제 GPU 테스트는 `DOHAMUSIC_RUN_SEED_VC_GPU_TEST=1`과 테스트 source/reference 경로를 명시한 경우에만 실행한다. 본인 또는 명시적으로 동의받은 reference만 `voices/references` 아래에 두며 모델·개인 음성·출력은 Git에 포함하지 않는다. 자세한 결과는 [EXP-004](../../reports/experiments/EXP-004-seed-vc.md)를 따른다.

`seed_vc`는 현재 `Experimental`이므로 로컬 기술 검증에만 명시적으로 선택한다. Phase 5 Pipeline은 기본 `MockVoiceConverter`만 사용해 Workflow 경계를 검증했으며 실제 사용자 트래픽·공개 Preview에는 연결하지 않는다. 저장 전·resample 후·PCM16 export 후 peak를 검증하기 전에는 clipping 경고를 무시하지 않는다.
