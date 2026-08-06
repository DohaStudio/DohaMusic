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

Backend 설치에는 Mixer·K3.1 Quality·K3.2 Tempo·K3.3 Hook 분석용 NumPy·SciPy, BS.1770 Integrated LUFS용 `pyloudnorm>=0.2,<0.3`, resource 측정용 psutil이 포함된다. pyloudnorm 0.2.0 pure Python wheel은 Windows·Python 3.12에서 설치·테스트했으며 Tempo와 Hook은 새 의존성 없이 기존 NumPy·SciPy를 사용한다. 기본 `DOHAMUSIC_AUDIO_MIXER=default`는 별도 AI·FFmpeg 설치 없이 실제 WAV를 합성한다. DSP 계약은 [Audio Quality Engine](../03-architecture/audio-quality-engine.md), K3 검증은 [EVAL-008](../../reports/evaluations/EVAL-008-audio-analysis-validation.md)을 따른다.

Lyrics 기본값 `DOHAMUSIC_LYRICS_PROVIDER=template`은 외부 API·Key·모델 설치 없이 한국어·영문 구조 초안을 만든다. 실제 LLM이 아니며 품질 승인을 의미하지 않는다. API 계약은 [Lyrics API](../06-api/lyrics-api.md), 실측은 [EXP-007](../../reports/experiments/EXP-007-lyrics-generation.md)을 따른다.

## Guided Voice Enrollment와 FFmpeg

little-endian 무압축 PCM16 WAV 입력은 Python `wave`와 SciPy로 48kHz mono PCM16 WAV에 정규화하므로 FFmpeg 없이 동작한다. PCM24·float32·ADPCM·WAVE_FORMAT_EXTENSIBLE WAV는 자동 변환하지 않고 `422 VOICE_SAMPLE_UNSUPPORTED_CODEC`으로 PCM 16-bit 변환을 안내하며, RF64와 손상 header는 container/decode 오류로 거절한다. 60초를 넘겨 정규화 출력 상한을 초과한 입력은 서버 장애가 아닌 `422 VOICE_SAMPLE_DURATION_TOO_LONG`으로 분류한다. WebM/Ogg Opus 입력만 system FFmpeg가 필요하다. `DOHAMUSIC_VOICE_FFMPEG_EXECUTABLE`에 executable 이름 또는 절대 경로를 지정하며 미설치 상태에서도 Backend는 정상 시작하고 해당 요청만 `VOICE_NORMALIZER_UNAVAILABLE`로 실패한다. subprocess는 shell 없이 argument 배열·30초 기본 timeout·stdout/stderr 폐기·부분 output cleanup을 사용한다.

Windows 10/11 개발 환경은 OS 기본 패키지 도구로 설치·업데이트 이력을 확인할 수 있는 Winget의 `Gyan.FFmpeg`를 권장한다. Chocolatey·Scoop도 가능하지만 별도 패키지 관리자 설치가 필요하고, 수동 압축 해제는 버전·PATH 갱신을 운영자가 직접 추적해야 하므로 fallback으로만 사용한다.

```powershell
winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements

# 설치 후 새 PowerShell을 열고 확인한다.
ffmpeg -version
ffmpeg -hide_banner -demuxers | Select-String 'matroska,webm|ogg'
ffmpeg -hide_banner -decoders | Select-String 'opus|vorbis'

# PATH 반영 전이라면 현재 세션에 설치된 ffmpeg.exe 절대 경로를 지정한다.
$env:DOHAMUSIC_VOICE_FFMPEG_EXECUTABLE = 'C:\path\to\ffmpeg.exe'
python -m uvicorn backend.main:app --reload
```

환경 변수나 PATH를 바꾼 뒤에는 Backend를 재시작해야 한다. 정상 설치 기준은 `ffmpeg -version` 종료 코드 0, `matroska,webm`·`ogg` demuxer와 `opus` decoder 확인이다. 애플리케이션도 WebM/Ogg 요청 시 최초 한 번 `ffmpeg -version`을 실행해 실행 파일을 검증하고 성공한 절대 경로를 process 수명 동안 재사용한다. WAV 요청과 Backend startup은 이 검사와 독립적이다.

Windows 11에서 Winget `Gyan.FFmpeg` 8.1.2 full build로 합성 Opus WebM/Ogg를 PCM16 48kHz mono WAV로 변환하고 손상 입력 cleanup을 확인했다. CI는 Ubuntu에서 `apt-get install ffmpeg` 후 Backend 전체 test를, Windows에서 Chocolatey FFmpeg 설치 후 실제 FFmpeg integration test를 실행한다. 검증 명령은 다음과 같다.

```powershell
$env:DOHAMUSIC_VOICE_FFMPEG_EXECUTABLE = (Get-Command ffmpeg).Source
python -m pytest -q backend/tests/test_voice_enrollment_audio.py -m integration
```

저장소는 FFmpeg binary를 배포하지 않으며 설치된 system dependency만 호출한다. Gyan full build의 실제 `ffmpeg -version`에는 `--enable-gpl`, `--enable-version3`, `--enable-libopus`가 포함되므로 운영 배포 이미지와 재배포 방식은 `ffmpeg -version`·`ffmpeg -L` 및 해당 build 고지 조건을 별도로 확인해야 한다. `[운영 배포 전 라이선스 검토 필요]`

## Guided Voice Enrollment cleanup scheduler

Backend는 FastAPI lifecycle에서 AI Worker pool과 분리된 process-local scheduler를 시작한다. 시작 시 `DELETE_PENDING`·`DELETE_FAILED`, cleanup `RUNNING`, 중단된 `VALIDATING`·`SUBMITTING`을 한 번 복구한 뒤 expiration, cleanup/retry, orphan scan을 각 설정 주기로 직렬 실행한다. 현재 공개 enum에는 별도 `PROCESSING`·`NORMALIZING`이 없으므로 해당 불완전 작업은 Sample `VALIDATING`과 cleanup `RUNNING`으로 복구한다. 종료 시 진행 중인 scan을 마친 뒤 scheduler를 중단하고 공용 AI executor와 DB engine을 종료한다.

기본 주기는 expiration·cleanup 300초, orphan 3600초다. cleanup 실패는 60초 이상 지난 뒤 process 수명 내 최대 3회 시도한다. DB가 source of truth이며 소유 row가 없거나 Storage가 누락된 상태를 탐지한다. 자동 삭제는 UUID 기반 server-generated 디렉터리와 알려진 파일명으로 확정되고 기본 24시간 grace가 지난 파일 또는 명확한 부분 출력에만 적용한다. 판단할 수 없는 파일과 symlink는 삭제하지 않고 경로를 포함하지 않은 warning을 남긴다.

운영 로그는 `voice_maintenance_*` event와 건수만 기록한다. `app.state.voice_maintenance_metrics.snapshot()`은 cleanup 성공·실패, retry, 만료, orphan, 복구 건수의 process-local snapshot을 제공하며 외부 metric endpoint나 API 계약을 추가하지 않는다. 재시작하면 metric과 횟수 한도는 초기화되지만 DB 실패 상태를 다시 읽어 복구를 재개한다. 로컬 단일 instance 계약이므로 여러 Backend process를 운영하려면 Phase 9에서 분산 lease와 영속 metric을 먼저 도입해야 한다.

집중 검증은 다음과 같다.

```powershell
python -m pytest -q backend/tests/test_voice_enrollment_maintenance.py
python -m ruff check backend/voice_enrollment backend/tests/test_voice_enrollment_maintenance.py
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

반복 benchmark는 `ai_worker/scripts/run_ace_step_benchmark.py`에 `quality-resident.json` 같은 suite를 명시해 실행한다. `benchmark`, `gpu`, `slow`, `integration` 작업은 opt-in이며 일반 `pytest`에서 모델을 로드하지 않는다. 0.6B LM 비교는 공식 모델을 사용자가 먼저 설치하고 benchmark 환경에 `DOHAMUSIC_AI_ACE_STEP_LM_MODEL=acestep-5Hz-lm-0.6B`, backend `pt`를 명시한 경우에만 실행한다. 이 LM 변수는 제품 Backend 설정이 아니다.

실험 WAV·로그·모델·runtime은 Git 제외 대상이다. Guided Voice Enrollment에서는 WebM/Ogg Opus만 FFmpeg로 검증했으며 MP3/AAC는 허용 계약이 아니므로 검증하지 않았다. ACE-Step 설치·연결은 [EXP-001](../../reports/experiments/EXP-001-ace-step-local-inference.md), 반복·LM은 [EXP-002](../../reports/experiments/EXP-002-ace-step-quality-and-stability.md)에 있다.

## 선택적 Demucs 런타임

Demucs 4.1.0은 Backend와 별도 Python 3.11 환경에 설치한다. 검증 환경은 torch·torchaudio 2.7.1+cu128, `demucs==4.1.0`, `psutil`, `soundfile`이며 HTDemucs checkpoint는 사용자가 공식 배포에서 미리 준비한다. 실행 중 `HF_HUB_OFFLINE=1`을 강제하므로 자동 다운로드하지 않는다.

`backend/.env.example`의 `DOHAMUSIC_STEM_DEMUCS_*` 경로를 설정하고 `DOHAMUSIC_STEM_PROVIDER=demucs`를 선택한다. 기본값 `mock`은 Demucs 설치 없이 동작한다. 3회 반복은 `ai_worker/scripts/run_demucs_benchmark.py`, 실제 Backend E2E는 `RUN_DEMUCS_GPU_TEST=1` 및 `DEMUCS_TEST_RUNTIME_PYTHON`, `DEMUCS_TEST_MODEL_CACHE`, `DEMUCS_TEST_SOURCE_AUDIO`를 명시해 실행한다. 모델·cache·실험 WAV·원시 metadata는 Git에 포함하지 않는다. 자세한 고정 환경은 [EXP-003](../../reports/experiments/EXP-003-stem-separation.md)에 있다.

## 선택적 Seed-VC 런타임

공식 저장소를 별도 무시 경로에 checkout하고 commit `51383efd921027683c89e5348211d93ff12ac2a8`로 고정한다. Python 3.11 격리 환경과 공식 44k F0 checkpoint·config, RMVPE, CAMPPlus, Whisper-small, BigVGAN cache를 요청 처리 전에 준비한다. Windows 검증 환경은 torch 2.7.1+cu128과 `webrtcvad-wheels`를 사용했다. 공식 requirements의 비표준 옵션과 Torch 2.4 DLL 문제 때문에 이 차이를 EXP-004에 기록했다.

`backend/.env.example`의 `DOHAMUSIC_VOICE_SEED_VC_*` 절대 경로를 설정하고 `DOHAMUSIC_VOICE_PROVIDER=seed_vc`를 선택한다. Backend runner는 offline 모드로 실행되어 모델을 자동 다운로드하지 않는다. 실제 GPU 테스트는 `DOHAMUSIC_RUN_SEED_VC_GPU_TEST=1`과 테스트 source/reference 경로를 명시한 경우에만 실행한다. 본인 또는 명시적으로 동의받은 reference만 `voices/references` 아래에 두며 모델·개인 음성·출력은 Git에 포함하지 않는다. 자세한 결과는 [EXP-004](../../reports/experiments/EXP-004-seed-vc.md)를 따른다.

`seed_vc`는 현재 `Experimental`이므로 로컬 기술 검증에만 명시적으로 선택한다. Phase 5 Pipeline은 기본 `MockVoiceConverter`만 사용해 Workflow 경계를 검증했으며 실제 사용자 트래픽·공개 Preview에는 연결하지 않는다. 저장 전·resample 후·PCM16 export 후 peak를 검증하기 전에는 clipping 경고를 무시하지 않는다.

## Guided Voice Enrollment 확인

Backend `8000`과 Frontend `3000`을 실행한 뒤 `/voice`에서 안내형 등록을 확인한다. FFmpeg가 설치되고 Backend의 `DOHAMUSIC_VOICE_FFMPEG_EXECUTABLE` 또는 PATH에서 탐지되면 WebM/Ogg를 처리한다. 탐지되지 않으면 WAV Sample은 계속 정규화·품질 검사·Profile 생성까지 지원하고 WebM/Ogg만 `VOICE_NORMALIZER_UNAVAILABLE`로 실패한다. UI는 이 경우 WAV 업로드 fallback을 안내하며 capability endpoint를 추측하지 않는다.

Frontend의 `/backend` rewrite는 Backend의 파일당 25MiB 계약을 보존하기 위해 Next.js `experimental.proxyClientMaxBodySize`를 26MiB로 설정한다. 1MiB 여유는 multipart field와 boundary metadata용이다. 이 값이 Backend 제한보다 작으면 큰 WAV body가 proxy에서 잘려 `500` 또는 `ECONNRESET`로 보일 수 있으므로 두 제한을 함께 검토한다. 설정 변경 후에는 Frontend server를 재시작한다.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/openapi.json
Invoke-WebRequest http://127.0.0.1:3000/voice -UseBasicParsing

cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

자동 E2E는 메모리 합성 WAV와 API mock을 사용하고 개인 음성을 수집·커밋하지 않는다. 실제 Backend 연결은 프로그램으로 생성한 합성 WAV로 create·upload·submit·Profile 조회 후 Profile을 삭제해 검증할 수 있다. 실제 마이크·장치별 MIME과 Safari·Firefox 지원은 사용자 동의 로컬 수동 평가가 필요하다.
## Pipeline Cancel·Retry 확인

동의된 Voice Profile로 Pipeline을 만든 뒤 실제 Job ID를 사용한다.

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/pipelines/{jobId}/cancel
curl.exe http://127.0.0.1:8000/api/pipelines/{jobId}
curl.exe -X POST http://127.0.0.1:8000/api/pipelines/{cancelledOrFailedJobId}/retry
curl.exe http://127.0.0.1:8000/api/history
curl.exe -X POST http://localhost:3000/backend/api/pipelines/{jobId}/cancel
```

실행 중 Provider 호출의 즉시 종료를 기대하지 않는다. `CANCEL_REQUESTED` 후 현재 단계가 반환되면 `CANCELLED`가 된다. Retry 응답의 새 Job ID로 상태를 조회한다.
