# 로컬 개발 환경

> 문서 목적: Backend와 선택적 AI 런타임을 재현 가능하게 분리한다.
> 현재 상태: **Backend·ACE-Step 격리 실행 절차 검증**

## Backend

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m alembic -c backend/alembic.ini upgrade head
python -m pytest -q
python -m uvicorn backend.main:app --reload
```

## 선택적 ACE-Step 런타임

공식 [v0.1.8 설치 문서](https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/docs/en/INSTALL.md)는 Python 3.11~3.12와 `uv sync`를 안내한다. 공식 저장소를 별도 디렉터리에 v0.1.8로 checkout하고 그 저장소의 lockfile로 환경을 만든다. 모델은 공식 CLI로 사용자가 명시적으로 내려받는다. DohaMusic 실행기와 테스트는 다운로드를 시작하지 않는다.

검증 환경은 다음과 같았다.

- Windows 11 Pro 64-bit, Python 3.12.5
- NVIDIA RTX 3060 Ti 8GB, driver 610.62
- ACE-Step v0.1.8 commit `dce621408bee8c31b4fcf4811682eb9359e1bc94`
- 격리 환경: torch 2.7.1+cu128, transformers 4.57.6, diffusers 0.37.1
- 공식 main bundle 약 9.4 GiB, 격리 환경 약 6.08 GiB

`backend/.env.example`의 `DOHAMUSIC_AI_ACE_STEP_*` 경로를 로컬 절대 경로로 설정하고 `DOHAMUSIC_MUSIC_GENERATOR=ace_step`을 선택한다. 기본값 `mock`은 AI 설치 없이 동작한다. 실제 GPU 통합 테스트는 모델을 설치한 환경에서만 `RUN_ACE_STEP_GPU_TEST=1`과 `pytest -m "integration and gpu and slow"`로 명시 실행한다.

실험 WAV·로그·모델·runtime은 Git 제외 대상이다. FFmpeg는 검증 PC에 없었으므로 WAV만 확인했으며 MP3/AAC는 검증하지 않았다. 상세 명령과 실패 이력은 [EXP-001](../../reports/experiments/EXP-001-ace-step-local-inference.md)에 있다.
