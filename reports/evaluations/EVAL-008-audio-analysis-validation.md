# EVAL-008: Audio Analysis 검증 계획

> 상태: [진행 중 — K3.4 PR #204 리뷰 수정·로컬 회귀 검증]
> 작성일: 2026-07-31
> 최종 수정일: 2026-10-12
> 관련 기능: K3.1~K3.4 Audio Quality·Tempo·Hook·Preview 평가
> 관련 문서: [K3 제품 정의](../../docs/02-product/k3-audio-analysis-product-definition.md), [라이브러리 비교](../../docs/01-research/audio-analysis-library-comparison.md), [EVAL-007](EVAL-007-kpop-dance-generation.md)

## 목적과 원칙

K3 analyzer가 측정값·추정값·실패를 계약대로 구분하는지 검증한다. K3.1 Quality, K3.2 Tempo와 K3.3 Hook 자동 fixture·Pipeline·API·Frontend 결과를 기록했으며 K3.4는 평가 설계를 유지한다. 생성 음원과 개인 음성은 Git에 커밋하지 않았다.

## 공통 기록

- fixture ID·권리·hash, WAV format·sample rate·channels·duration
- `audio_analysis_version`과 각 후보 library/version/config
- CPU·OS·Python, wall/CPU time, peak RSS
- ground truth/reference tool과 허용 오차
- status·warning·confidence, 실패 원인
- 실제 값, absolute/relative error, 통과 여부

## BPM 검증

| 데이터 | 목적 |
|---|---|
| 메트로놈 합성 60·80·100·120·140·160 BPM | 명확한 ground truth |
| 고정 BPM drum loop | 실제 transient 패턴 |
| half-time·double-time 편곡 | octave tempo 오류 분류 |
| 무박 intro 후 고정 tempo | 초기 무박 영향 |
| tempo change 곡 | global tempo 한계·stability |
| 30초·60초 권리 확보 K-POP Dance 결과 | 제품 대표성, 자동 ground truth 아님 |

측정값은 detected BPM, ground truth BPM, signed/absolute error, confidence, half/double error, 분석 시간을 포함한다. provisional 자동 통과 기준은 명확한 합성/고정 loop에서 half/double 보정 후 absolute error 2 BPM 이내다. 생성곡은 수동 beat annotation과 비교하며 기준은 구현 benchmark 후 확정한다.

confidence는 high/medium/low/unavailable 구간별 실제 오류 분포를 검토한다. 높은 confidence가 더 낮은 오류와 연결되지 않으면 UI 등급으로 사용하지 않는다.

### K3.2 자동 검증 결과 — 2026-08-01

- 기존 NumPy 1.26.4·SciPy 1.17.1의 onset energy autocorrelation을 사용해 새 의존성을 추가하지 않았다.
- 16초 PCM16 합성 click track 60·80·100·120·140·160 BPM을 모두 ±3 BPM 이내로 추정했다.
- 동일 WAV에 서로 다른 `requested_bpm`을 넣어도 `detected_bpm`이 같아 요청값이 추정을 유도하지 않음을 확인했다.
- 60→요청 120은 half-time, 160→요청 80은 double-time 후보로 분류했다.
- silence·1초 short·손상 WAV·비 WAV를 finite하지 않은 값이나 내부 path 없이 안전한 실패/미지원으로 처리했다.
- 공개 DTO에서 raw onset·frame·FFT·debug·path를 제거하고 Retry가 이전 Tempo 대신 새 WAV를 분석함을 확인했다.
- Frontend Completed·Partial·Failed·Unavailable, confidence 경계와 Result·History·Project Desktop/Mobile 표시를 검증했다.
- 실제 드럼 loop·무박 intro·tempo change·생성 K-POP의 confidence 분포와 성능 수치는 후속 운영 품질 평가로 남긴다.

## Loudness·Peak 검증

- Sample Peak: synthetic impulse·sine의 계산값과 reference 비교
- Integrated LUFS: ITU-R BS.1770/EBU R 128 test signal 및 승인 reference meter 비교
- True Peak: 표준 test signal과 reference meter 비교; oversampling 미구현이면 미지원 유지
- Clipping: positive/negative full-scale, over-range float, clipped PCM
- Mono·Stereo와 44.1/48 kHz
- short audio, silence, empty/invalid/truncated WAV

LUFS·True Peak 허용 오차는 사용 library와 EBU test set의 compliance 조건을 확인한 뒤 확정한다. reference 후보는 EBU Loudness test set과 라이선스 검토된 FFmpeg/전용 meter다. 단순 RMS 또는 Sample Peak를 LUFS·True Peak reference로 사용하지 않는다.

## Hook·Chorus 후보 검증

권리 확보 또는 합성 데이터에 사용자가 반복 구간과 Chorus 시작 후보를 annotation한다.

- 허용 start/end 오차
- 후보와 label의 temporal overlap·IoU
- top-1 precision, candidate recall
- 반복 score·energy contrast와 confidence calibration
- 15초 Preview 후보로 사용 가능한지
- 사용자가 곡의 핵심 구간으로 느끼는지
- 반복 청취에 적합한지

Hook ground truth는 본질적으로 주관적이므로 “정확도” 단일 숫자로 승인하지 않는다. Stage A의 제품 Gate는 top-1 후보의 Preview 유용성과 저신뢰 결과의 안전한 fallback이다.

### K3.3 자동 검증 결과 — 2026-08-01

- 자체 합성 60초 WAV의 두 반복 고에너지 구간에서 15초 `energy_repetition` 후보와 `0.50` 이상 confidence를 선택했다.
- 단일 고에너지 구간은 `energy_peak`, 일정한 tone과 낮은 confidence는 곡 중앙 `fallback_middle`로 분류했다.
- 15초 미만 WAV는 전체 길이의 PARTIAL fallback, 무음·손상·미지원 입력은 candidate 없이 안전한 FAILED/UNSUPPORTED로 처리했다.
- Hook 실패·fallback 이후에도 Pipeline은 `COMPLETED`와 final WAV capability를 유지하고 aggregate analysis만 `PARTIAL` 또는 `FAILED`로 구분했다.
- 공개 DTO에서 raw frame score·경로를 제외하고 Retry가 이전 Hook metadata 대신 새 WAV를 분석함을 확인했다.
- Frontend Result의 “후렴 후보/추정 구간”, History 후보 유무, Project 요약과 Completed·Partial·Failed·Unavailable Desktop/Mobile 표시를 검증했다.
- 실제 음악의 사용자 label·temporal overlap·confidence calibration과 Preview 유용성은 후속 운영 품질 평가로 남긴다.

## Preview 검증

- 원본이 15초 이상이면 frame 기준 정확히 15초
- short source 정책과 중앙 fallback 재현성
- RIFF/WAVE 재생 가능, channel·sample rate 유지
- 원본 파일 hash 불변
- 20 ms fade in/out과 시작·끝 click 청취
- Hook 후보 대표성, fallback 정상 동작
- secure content/download, Range, MIME, path 비노출
- 취소·실패·Job/Result 삭제 cleanup과 orphan 부재

## 실패·호환 검증

- 분석 없음 구형 Result는 정상 재생되고 `not_requested/unavailable`로 표시된다.
- 일부 analyzer 실패는 `partial`, 전체 분석 실패는 `failed/unsupported`가 되며 Pipeline Result는 유지된다.
- malformed metadata·unknown version·내부 경로는 공개 DTO에서 제거된다.
- Retry는 새 WAV를 분석하고 기존 결과를 복사하지 않는다.
- Re-analysis가 도입되면 동일 WAV·새 version 관계와 기존 결과 보존을 검증한다.

## 성능·취소 검증

60초 Stereo WAV 기준 wall/CPU time, peak RSS, file size와 cancellation latency를 측정한다. “일반 CPU에서 수 초~수십 초”는 provisional 예산이며 실제 장비·동시 Job·긴 곡 결과로 K3.1 구현 PR에서 상한을 확정한다. 측정하지 않은 수치를 완료 근거로 사용하지 않는다.

### K3.1 실측 — 2026-08-01

- 환경: Windows, Python 3.12.5, Intel64 Family 6 Model 151, NumPy 1.26.4, SciPy 1.17.1, pyloudnorm 0.2.0
- 입력: 자체 합성 1 kHz sine, -20 dBFS, 48 kHz Stereo PCM16
- 측정: 동일 warm process에서 `perf_counter`, 2 ms RSS sampling; 파일 생성 메모리는 baseline 전에 회수

| 길이 | WAV 크기 | wall time | peak RSS 증가 | status | Integrated LUFS |
|---:|---:|---:|---:|---|---:|
| 30초 | 5.49 MiB | 0.1161초 | 73.51 MiB | `COMPLETED` | -20.034610 |
| 60초 | 10.99 MiB | 0.2173초 | 148.32 MiB | `COMPLETED` | -20.034610 |

단일 로컬 관찰값이며 운영 성능 보장이 아니다. 현재 기준 HEAD `1944b365`의 분석 순서는 `final.wav → Quality·Tempo·Hook → 취소 확인 → finalize_success()`다. 과거의 `COMPLETED` 이후 분석 설명은 현재 코드와 일치하지 않아 정정한다. K3.4에서는 기존 분석 순서를 옮기지 않고 Preview만 성공 확정 뒤 실행한다. 별도 분석 cancel API가 없으며 이번 환경에서 기존 취소 integration test를 재실행 완료하지 못했다.

### K3.1 자동 검증 결과

- 1 kHz -20 dBFS mono reference: 약 -23.05 LUFS, 동일 stereo: 약 -20.03 LUFS, 허용 오차 ±0.1 LU
- mono/stereo·PCM16/24/32·duration·sample rate·Sample Peak·positive/negative clipping scalar count·ratio 통과
- silence·0.1초 short는 non-finite 값 없이 `PARTIAL`, empty·invalid·missing은 safe `FAILED`, 3채널은 `UNSUPPORTED`
- 분석 exception·metadata 1회 저장 실패에서도 Pipeline `COMPLETED`와 final WAV file capability 유지
- 공개 DTO에서 source role·path·command·stack·raw debug 제거, 구형 Result null 호환 확인

## 완료 판정

- [x] K3.1 quality reference와 invalid 경계 통과
- [x] K3.2 합성 BPM error·half/double·confidence 경계 통과
- [x] K3.3 합성 Hook 후보·fallback·비차단·공개/UI 경계 통과
- [ ] K3.4 정확한 길이·fade·secure access·cleanup 통과
- [x] K3.1 성능과 완료 경계 기록
- [x] K3.1 실패·partial·unsupported와 구형 Result 회귀 통과

현재 결과: `K3.1·K3.2·K3.3 [기존 완료 판정 유지·이번 통합 회귀 미확인]`, `K3.4 [진행 중·부분 검증]`. 실제 음악의 overlap·사용자 유용성 평가는 후속 운영 항목이다.

## K3.4 로컬 검증 — 2026-10-12

- 폴더: `D:\DohaMusic-k3-preview-export`, 브랜치: `feat/k3-preview-export`, 기준 HEAD와 로컬 origin/develop: `1944b365`.
- 실제 AI·유료 API·개인 음성 사용 없음. 새 의존성·DB migration 없음. 커밋·push·PR·병합 미수행.
- `python -m pytest backend/tests/test_preview_export.py -q -k 'memory or hook_validation or public_projection' -p no:cacheprovider --tb=short`: **23 passed, 4 deselected**. 실제 SciPy WAV codec을 BytesIO에 연결하여 8k/44.1k/48k, mono/stereo, 15초/짧은/1·3 frame, PCM16, 겹치지 않는 linear fade와 입력 bytes 불변을 확인했다. Hook 상태·version·confidence·구간·길이·NaN 거부와 중앙 fallback, 경로 없는 공개 projection을 검증했다.
- 같은 실행의 실제 in-memory SQLite transaction 테스트는 중복 실행의 단일 row·ready 재사용, 등록 rollback·파생 cleanup·COMPLETED 보존, pending에서 새 Service 복구, final row 부재 unavailable, metadata mirror 실패의 ready 유지, DB 저장 실패의 pending 보존·재실행을 검증했다. 이 테스트의 filesystem·rename·renderer 호출은 mock이므로 실제 디스크 crash/concurrency를 검증했다고 해석하지 않는다.
- 실제 PipelineWorker+in-memory SQLite의 3개 시나리오는 final → Quality·Tempo·Hook → finalize_success → Preview 순서, 분석 후 취소의 CANCELLED·Preview 미실행, 성공 후 Preview 예외의 COMPLETED·원본 cleanup 미실행을 검증했다. analyzer·Storage·executor는 합성 mock이므로 전체 파일 기반 K3.3·Retry 회귀를 대신하지 않는다.
- `python -m pytest backend/tests/test_pipeline_api.py backend/tests/test_pipeline_file_access_api.py backend/tests/test_hook_analyzer.py -q`: **43 setup errors**, 임시 디렉터리 `WinError 5`. workspace 안의 새 basetemp 재시도도 동일 권한 오류였다. API·Range·symlink·원본 hash·실제 동시 writer·중단/재시작·K3.3 순서/취소/Retry 파일 기반 회귀는 미검증이다. 해당 신규 통합 테스트 4개도 실행 완료하지 못했다.
- `npm run typecheck`, `npm run test -- --run tests/polling.test.ts`: **실행 실패**, node_modules가 없어 tsc·vitest를 찾지 못했다. pending polling 및 ready 파일 재조회/Player/다운로드/구형 상태 테스트를 추가했으나 Frontend 테스트·Lint·build·브라우저 렌더링은 미검증이다.
- 변경 Python 파일의 `python -m ruff check`: 통과. `git diff --check`: 통과.
- 운영 성능·실제 청취 품질·실제 프로세스 kill/fsync 내구성·다중 프로세스 lock은 미측정이다. SQLite의 렌더링 중 write lock, DB/filesystem 원자성 한계, ready 복구·임시 JSON 잔여 정책은 ADR-023을 따른다.

K3.4 DoD는 체크하지 않는다. 허용된 테스트 디렉터리와 Frontend 의존성이 준비된 환경에서 위 통합·Frontend 회귀를 통과한 후 커밋/PR 검토를 진행한다.

## K3.4 통합 환경 진단과 재검증 — 2026-10-12

이 절은 앞의 최초 실행 결과를 보존하고 재검증 결과를 별도로 기록한다. 기존 25개 변경 파일·미추적 구현 파일, `D:\DohaMusic`, 다른 worktree, 보호된 cache 디렉터리 2개는 삭제·권한 변경하지 않았다. 관리자 권한 상승·광범위한 ACL 변경·보안 기능 해제·Git 이력 변경은 없다.

### Windows 임시 디렉터리 원인

- Python 3.12.5. 기존 최초 traceback은 pytest `tmp_path → TempPathFactory.getbasetemp → make_numbered_dir → os.scandir`에서 `C:\Users\<USER>\AppData\Local\Temp\pytest-of-<USER>` 접근이 `WinError 5`로 거부된 것이다. K3.4 함수나 app fixture 본문 실행 전에 실패했다.
- 새 UUID 경로 `D:\DohaMusic-k3-preview-export\.k34-validation-9b8e6a1ec198413e8fde8196a93bcf9f`는 존재하지 않음을 확인하고 일반 `Path.mkdir()`로 생성했다. probe 파일 생성·읽기·directory listing이 성공했다. root ACL은 Modify 권한을 포함한다.
- 같은 root의 새 `pytest-run-01`, `pytest-run-02`를 명시적 `--basetemp`로 지정하고 첫 실행에는 TEMP·TMP·TMPDIR도 새 root로 지정했으나 pytest가 생성한 basetemp는 접근이 거부됐다. 따라서 예전 잔여 디렉터리와의 이름 충돌이나 parent 쓰기 권한 부족만으로 설명되지 않는다.
- 별도 첫 오류 reporter로 `test_hook_analyzer.py -x`를 재현했다. `getbasetemp()`의 `basetemp.mkdir(mode=0o700)` 이후 `mktemp → make_numbered_dir → os.scandir(new basetemp)`에서 접근이 거부되고 session cleanup도 실패했다. 디렉터리 생성 자체보다 생성 후 private 권한 디렉터리 접근이 문제다. 해당 디렉터리의 Get-Acl도 거부돼 정확한 ACE/실행 토큰 조합은 확인하지 못했다.
- pyproject에는 tmp fixture override가 없고 conftest는 표준 tmp_path를 SQLite/Storage 경로로 사용할 뿐이다. 이번 실행에만 표준 상속 권한으로 새 고유 directory를 생성하는 function-scope tmp_path fixture를 제공했다. 기존 fixture·테스트 assertion·Migration·WAV·DB·file API는 변경하지 않았다. 새 경로 아래에서 실제 SQLite/WAV를 사용하며 기존 디렉터리 삭제나 ACL 수정은 하지 않는다.

### Backend 실행 방식

PowerShell here-string을 `python -`에 전달해 다음과 같은 실행 전용 plugin을 사용했다. 매번 새 UUID basetemp를 만들고 환경변수를 해당 경로로 지정하며 pytest cacheprovider는 비활성화한다. 아래 args는 실제 전체 실행의 대상과 옵션이다.

```python
from pathlib import Path
import os, pytest, uuid
root = Path.cwd() / ".k34-validation-9b8e6a1ec198413e8fde8196a93bcf9f"
base = root / ("fixtures-" + uuid.uuid4().hex)
assert not base.exists()
base.mkdir()
for key in ("TEMP", "TMP", "TMPDIR"):
    os.environ[key] = str(base)
class IsolatedTempPaths:
    @pytest.fixture
    def tmp_path(self):
        path = base / uuid.uuid4().hex
        path.mkdir()
        return path
args = [
    "backend/tests/test_preview_export.py",
    "backend/tests/test_pipeline_api.py",
    "backend/tests/test_pipeline_file_access_api.py",
    "backend/tests/test_hook_analyzer.py",
    "backend/tests/test_audio_quality_analyzer.py",
    "backend/tests/test_tempo_analyzer.py",
    "-q", "-p", "no:cacheprovider", "--basetemp", str(base), "--tb=short",
]
raise SystemExit(pytest.main(args, plugins=[IsolatedTempPaths()]))
```

- 전체 실행 basetemp: `fixtures-2495c93c3e3d4795a8f33d22a0908868`.
- 전체 실행 결과: **90 passed, 1 skipped**, 758.76초, exit 0. 추가 4개 case와 합쳐 현재 대상 95개 중 **94 통과 / 0 코드 실패 / 1 skip**이다. skip은 `test_file_access_rejects_symlink`로 기존 테스트가 Windows symlink 생성 권한 부족을 명시한다. symlink 보안을 통과했다고 기록하지 않는다.
- Hook/Quality/Tempo, Pipeline 분석 완료 경계·취소·Retry, 실패 후 COMPLETED 유지, 파일 기반 SQLite 등록·복구·중복 실행/단일 Preview row·ready 재사용·DB 등록 실패 cleanup, secure content/download·WAV/Range·path 비노출 회귀가 통과했다. 실제 기능 코드 결함은 발견하지 않았으며 기능 코드는 수정하지 않았다.
- 추가 실행 1: 같은 plugin으로 `test_preview_export.py -q -k 'file_metadata_sync_failure or pending_preview_recovers_on_application_restart' -p no:cacheprovider --basetemp <새 UUID 경로> --tb=short --durations=5`: **2 passed, 27 deselected**, 64.51초. 실제 app lifecycle 재시작·startup pending 복구와 metadata.json 쓰기 실패 후 ready·COMPLETED 유지·파일 재사용·재동기화를 확인했다.
- 추가 실행 2: 같은 plugin으로 `test_preview_export.py -q -k file_wav_duration_fade_and_source_hash -p no:cacheprovider --basetemp <새 UUID 경로> --tb=short`: **2 passed, 29 deselected**, 0.18초. 디스크의 long mono/매우 짧은 stereo WAV를 사용해 정확한 15초/전체 길이, PCM16, sample rate·채널, 양끝 fade, Hook/fallback과 원본 SHA256 불변을 확인했다.
- 추가한 테스트는 위 4개 case이며 기능 코드는 수정하지 않았다. 실제 강제 process kill·power loss·fsync 내구성·서로 다른 프로세스의 경쟁은 검증하지 않는다. app lifecycle 재시작과 ThreadPoolExecutor의 동시 Service 실행을 실제 crash 보장으로 해석하지 않는다.

### Frontend 설치 진단·cache 복구와 실행 결과

- package.json과 npm package-lock v3를 확인했다. node v24.15.0, npm 11.12.1. node_modules는 Git 추적 대상이 아니고 `.gitignore`에 제외되어 있으며 이 worktree에 설치된 실행 도구가 없었다. 과거 미설치의 추가 원인은 증거가 없어 추정하지 않는다.
- `npm ci --cache D:/DohaMusic-k3-preview-export/.k34-validation-9b8e6a1ec198413e8fde8196a93bcf9f/npm-cache --no-audit --no-fund`: exit 1, `NPM_CONFIG_OFFLINE=true`로 zustand tarball을 cache에서 찾지 못해 `ENOTCACHED`.
- `npm ci --offline=false --cache D:/DohaMusic-k3-preview-export/.k34-validation-9b8e6a1ec198413e8fde8196a93bcf9f/npm-cache --no-audit --no-fund`: exit 1. registry tarball 요청이 `ECONNREFUSED`로 실패했고 최종 npm 메시지는 `Exit handler never called!`였다. 첫 원인은 network fetch 실패이며 K3.4 Frontend compile/test 결함이라는 근거가 아니다. 설치 cache·로그는 현재 workspace에만 지정했다.
- 위 네트워크 설치 실패 직후에는 `.bin/tsc.cmd`, `.bin/vitest.cmd`, `.bin/next.cmd`가 모두 없어 그 시점의 검증은 미실행이었다. 이후 아래 cache 복구와 실제 검증을 수행했다.
- package-lock SHA256은 설치 전후 `022D0B69CD295CE479B58267B2CB22A5D6C468C24BDB3FEA3C8505BA9243792C`로 동일하며 lockfile diff가 없다.
- 기본 npm cache를 읽기 전용으로 조사했다. lockfile의 registry tarball 558개 중 454개의 index가 일치했고, Windows/x64 대상에서 cache가 없는 항목은 optional WASM dependency 2개뿐이었다. matching tarball의 SRI content digest를 검증한 뒤 454개/130,658,144 bytes와 index를 workspace cache에 복사했다. 기본 cache와 다른 worktree에는 쓰지 않았다.
- cache 복사 직후 repo root에서 `npm ci --offline`를 한 번 잘못 실행해 package-lock 부재 `EUSAGE`가 발생했다. frontend cwd로 바로 수정하여 재실행했다. 이 오류는 실행 위치 오류이며 제품 결함이 아니다.
- frontend cwd의 `npm ci --offline --cache <workspace cache> --no-audit --no-fund`: lifecycle postinstall(esbuild/unrs-resolver) child process에서 `spawn EPERM`, exit 1. 관리자 실행·권한 변경 없이 다음 명령으로 lifecycle script 미실행을 명시했다.
- frontend cwd의 `npm ci --offline --ignore-scripts --cache D:/DohaMusic-k3-preview-export/.k34-validation-9b8e6a1ec198413e8fde8196a93bcf9f/npm-cache --no-audit --no-fund`: **exit 0, added 459 packages in 33s**. reproducible lock 설치이며 lifecycle scripts를 실행 완료했다고 주장하지 않는다. package.json·lockfile·tsconfig·next-env의 Git diff는 없다.
- `npm run typecheck`: **exit 0**, TypeScript 전체 source 검사 통과.
- `node node_modules/eslint/bin/eslint.js features/pipeline/result-panel.tsx hooks/use-pipeline.ts lib/result-metadata.ts tests/preview-result.test.tsx tests/polling.test.ts`: **exit 0**, 변경 Frontend 파일 5개의 Lint 통과.
- `npm run test -- --run tests/preview-result.test.tsx tests/polling.test.ts tests/player.test.tsx tests/mappers.test.ts tests/audio-analysis.test.tsx tests/tempo-analysis.test.tsx tests/hook-analysis.test.tsx`: **exit 1**, Vite config bundling의 `esbuild.ensureServiceIsRunning → ChildProcess.spawn`에서 `EPERM`. config startup 실패이며 선택한 7개 파일의 테스트 본문은 **0개 실행**이다. assertion failure나 K3.4 runtime 결함으로 분류하지 않는다. 다른 runner·mock compile을 성공으로 대체하지 않았다.
- `$env:NEXT_TELEMETRY_DISABLED='1'; npm run build`: **exit 1**, 기존 `app/layout.tsx`의 next/font Inter·Manrope Google Fonts 연결 실패. K3.4 코드 compile 오류라는 근거는 없지만 production build 성공으로 판정하지 않는다. font 교체·fetch mock·보안 설정 변경은 하지 않았다.
- 검증 scratch root, 설치한 node_modules와 .next/tsbuildinfo는 이번 실행의 artifact다. 보호된 기존 cache 디렉터리 2개 및 새 접근 불가 diagnostic basetemp도 삭제·ACL 변경하지 않았다. scratch root는 Git 작업 산출물에 포함하지 않는다.

### 현재 판정

Backend 대상 95개는 94 통과·1 환경 skip이며 K3.3 순서/취소/Retry와 Preview 실패 격리를 실제 파일 기반으로 검증했다. Frontend typecheck는 통과했으나 Preview/Result runtime 테스트와 production build는 환경 문제로 차단됐다. 실제 process kill·power loss·서로 다른 프로세스의 동시 writer·Windows symlink 접근 거부는 미검증이다. K3.4 DoD 완료 또는 PR 준비 완료로 판정하지 않는다. 실행 권한과 font 네트워크가 허용된 환경에서 동일 lockfile로 runtime 테스트·build를 통과한 뒤 PR 검토가 가능하다. 커밋·push·PR·merge는 수행하지 않았다.

## Frontend 검증 차단 해소 — 2026-10-12

이 절의 최종 결과가 앞선 차단 판정을 대체한다. 기존 변경·검증 scratch를 보존했고 원본 `D:\DohaMusic`는 폰트 cache를 읽기 전용으로만 조사했다. 관리자 실행·ACL·보안 설정·sandbox·기존 데이터 삭제·Git 이력 변경은 없다.

### EPERM 진단

- esbuild JS와 Windows/x64 실행 파일은 모두 `0.28.1`; 실행 파일이 존재하며 직접 `esbuild.exe --version`은 성공했다. ACL의 ReadAndExecute 권한을 확인했다. lifecycle scripts 제외가 실행 파일 누락/다른 버전을 만든 것이 아니다.
- Node `24.15.0`, Vite `7.3.6`, Vitest `4.1.10`의 설치된 package engines와 일치한다. NODE_OPTIONS는 미설정이며 Node permission model도 활성화돼 있지 않다.
- `child_process.spawnSync(process.execPath, ['--version'], {stdio:'inherit', windowsHide:true})`와 `stdio:'ignore'`는 exit 0. 같은 Node·esbuild executable을 기본 `stdio:'pipe'`로 실행하면 EPERM이며 stderr만 pipe로 해도 EPERM이다. 따라서 esbuild binary 실행 권한이나 version 호환성보다 Windows subprocess stdio pipe 생성 경계의 환경 문제다. 정확한 시스템 정책 이름은 확인하지 못했으며 특정 보안 제품의 차단이라고 단정하지 않는다.
- WSL 조회는 E_ACCESSDENIED, Docker daemon 조회는 named pipe 접근 거부였다. 해당 서비스를 시작하거나 권한을 바꾸지 않았다. Vitest의 기본 bundle loader는 여전히 pipe 경계에서 실패한다.

### 실제 테스트 실행 모드

`DOHAMUSIC_TEST_IN_PROCESS=1`을 명시하고 Vite Native config loader, Vitest thread pool, 이미 설치된 TypeScript compiler의 `transpileModule`을 사용한다. 기존 tsconfig의 JSX/target/module 설정·syntactic diagnostics·jsdom·setup·테스트 파일·assertion을 유지하며 typecheck는 별도로 실행한다. 기존 esbuild 모드는 미설정 시 유지한다. Native loader의 Node MODULE_TYPELESS_PACKAGE_JSON 경고는 기록하되 package.json의 module 정책은 변경하지 않았다.

- 첫 opt-in 실행은 Vite Windows realpath/network-drive discovery의 `exec('net use')`에서 EPERM으로 7개 suite가 실패했고 test body는 0개였다. Vite의 지원 옵션 `resolve.preserveSymlinks`를 이 실행 모드에만 사용했다. 이는 Frontend module resolution 옵션이며 Backend secure file 경계를 변경하지 않는다.
- 다음 실행은 Vitest가 esbuild JSX 기본값을 merge하여 `esbuild:false`가 보존되지 않아 setup.ts transform에서 EPERM이었다. Vite의 지원 include filter로 내장 esbuild transform을 비활성화하고 TypeScript plugin이 실제 TS/TSX source를 변환하도록 수정했다. dependency optimizer도 이 모드에서 비활성화한다. 실패한 초기 실행을 성공으로 계산하지 않는다.
- `$env:DOHAMUSIC_TEST_IN_PROCESS='1'; npm run test -- --configLoader native tests/preview-result.test.tsx tests/polling.test.ts tests/player.test.tsx tests/mappers.test.ts tests/audio-analysis.test.tsx tests/tempo-analysis.test.tsx tests/hook-analysis.test.tsx`: **7 files / 46 tests passed**, exit 0, 6.28초. Preview pending→ready 파일 재조회·Player·다운로드·구형/실패 상태와 polling·mapper·Quality/Tempo/Hook·Player 회귀의 본문을 실제 실행했다.
- `$env:DOHAMUSIC_TEST_IN_PROCESS='1'; npm run test -- --configLoader native`: **34 files / 260 tests passed**, exit 0. 마지막 compiler diagnostics guard 반영 후 재실행 결과는 16.04초다. 선택한 46개는 이 260개에 포함하며 중복 합산하지 않는다. 실패·skip은 없다. Playwright E2E는 기존 exclude대로 별도 범위다.
- `npm run typecheck`: exit 0. `node node_modules/eslint/bin/eslint.js app/layout.tsx next.config.ts vitest.config.ts features/pipeline/result-panel.tsx hooks/use-pipeline.ts lib/result-metadata.ts tests/preview-result.test.tsx tests/polling.test.ts`: exit 0.

### Google Fonts와 production build

- 기존 layout은 `next/font/google`의 Inter/Manrope를 사용했다. 환경 HTTP/HTTPS/ALL proxy endpoint는 localhost port 9였으며 실제 build의 Google Fonts fetch는 연결 실패했다. proxy 값을 변경하거나 외부 통신 제한을 우회하지 않았다. 런타임 모델/API 장애가 아닌 build-time network dependency다.
- 기존 동일 폰트의 WOFF2 13개(293,692 bytes)를 원본 worktree build cache에서 읽기 전용으로 복사했다. source CSS의 font-face 15개(13 subset+2 fallback), family·variable weight·Unicode range·Arial fallback metrics·Latin preload를 보존하고 URL만 로컬 정적 경로로 변경했다. font byte SHA256/provenance는 `frontend/public/fonts/README.md`, 저작권 및 공식 SIL OFL 1.1 고지는 `OFL.txt`에 기록했다. 새 글꼴/변형 subset·새 의존성은 없다.
- `$env:NEXT_TELEMETRY_DISABLED='1'; npm run build`: 폰트 수정 후 **Compiled successfully in 1950ms**, 이후 기본 TypeScript process worker의 spawn EPERM으로 exit 1. compile 단계 성공을 전체 build 성공으로 기록하지 않는다.
- 설치된 Next `build/type-check.js`, `build/index.js`, config schema에서 지원하는 `experimental.workerThreads`가 TypeScript·page data/static generation에 전달됨을 확인하고 `DOHAMUSIC_BUILD_WORKER_THREADS=1` opt-in을 추가했다. 검사 생략·ignoreBuildErrors·fetch mock은 사용하지 않았다.
- `$env:NEXT_TELEMETRY_DISABLED='1'; $env:DOHAMUSIC_BUILD_WORKER_THREADS='1'; npm run build`: **exit 0**, Turbopack compile·TypeScript·11 worker page data·전체 static/dynamic route generation·final optimization 완료. Google Fonts 연결 없이 실제 production build를 완료했다.

### 최종 판정·제한

Frontend는 위 명시적 실행 모드에서 실제 260개 단위 회귀·typecheck·Lint·full production build를 통과했다. Backend의 이전 94 passed/1 Windows symlink skip 증거는 유지하며 이번에는 Backend 코드를 바꾸거나 전체 suite를 재실행하지 않았다. PR 검토 준비가 가능하지만 커밋·push·PR·merge는 사용자 승인 전 수행하지 않는다. K3.4 DoD는 develop 병합 전에 완료로 체크하지 않는다.

기본 esbuild/process-worker 경로는 현재 환경에서 여전히 차단된다. 다른 Node/OS, symlink module 설치, 브라우저 시각 비교·실제 audio 청취/Playwright E2E, 강제 process kill·power loss·다중 프로세스 Preview 경쟁, Windows symlink 접근 거부는 추가 검증 대상이다. 기존 phase 진행률·ADR·모델·DB·인증 정책은 변경하지 않았다. 운영 재현 명령은 local-development 및 environment-variables 문서에 기록했다.

최종 read-only 검증은 WOFF2 13개가 source cache와 byte/SHA256 동일함, CSS font-face 15개, 현재 node_modules의 symlink/junction 0개, Markdown 상대 링크 421개 누락 없음, git diff --check 통과를 확인했다. package-lock SHA256은 기존 `022D0B69CD295CE479B58267B2CB22A5D6C468C24BDB3FEA3C8505BA9243792C`를 유지한다. 브랜치·HEAD는 `feat/k3-preview-export` / `1944b365` 그대로다.

## PR #204 P2 리뷰 수정 및 Ruff CI 조사 (2026-10-12)

### 시작 상태와 범위

- 작업 경로는 지정된 K3.4 worktree, branch `feat/k3-preview-export`, HEAD `0150e5eb02242c0b1b40d1e40f4386426bc0ef02`다. 시작 시 추적 파일 변경·staged 변경은 없었으며 기존 `.k34-validation-*`만 미추적이었다. 접근 불가 cache와 기존 scratch를 보존했다.
- 이번 수정은 파일 API의 비정상 Preview metadata 처리, DB unavailable 확정 후 mirror 실패 격리, CI에서 지적한 5개 Python 파일의 포맷에 한정한다. Frontend/API 응답 계약·공개 retry·scheduler·Pipeline 분석 순서는 변경하지 않았다.
- commit/push/PR 수정/merge와 Git 공유 metadata 쓰기는 실행하지 않았다. 원본 저장소와 다른 worktree 파일을 수정하지 않았다.

### 수정 전 재현과 수정

- 실행 전용 fixture runner `python <scratch>/review_runner.py backend/tests/test_preview_export.py -q -k 'malformed_preview_metadata or missing_final_mirror' --maxfail=2`: **2 failed, 31 deselected**, 11.10초. 최초 `unavailable`이 mirror 오류 이후 `failed`로 덮어써졌으며 문자열 Preview를 가진 Job의 파일 목록 조회는 AttributeError를 발생시켰다. 이 실행은 의도한 결함 재현이며 통과로 집계하지 않는다.
- PipelineService의 list_files/access_audio_file은 기존 `_preview_status()`를 재사용한다. Preview 문자열·배열·숫자·null·빈 객체·unknown/list/null status는 파일 목록에서 URL과 availability를 제공하지 않고 직접 content/download 요청은 기존 `409 FILE_CONTENT_UNAVAILABLE`로 처리한다. 정상 ready 검증·Range·Job 소속·경로 검증은 유지한다.
- 최종 파일 row가 없는 경우 `set_metadata()`의 DB commit 성공 직후 `published=True`를 설정한다. 후속 mirror 실패는 내부 예외 로그를 남기되 authoritative unavailable을 failed로 덮어쓰지 않는다. 기존 ready 확정/재사용 역시 보존하며 unavailable은 재실행의 생성 대상이 아니다.
- 수정 후 같은 runner/선택(최대 실패 1): **9 passed, 31 deselected**, 84.62초. malformed API 8개와 missing final/mirror failure 1개가 통과했다.
- `python <scratch>/review_runner.py backend/tests/test_preview_export.py -q -k 'sqlite_missing_final or memory_metadata_sync'`: **2 passed, 39 deselected**, 0.81초. 실제 SQLite 파일을 닫고 재열어 unavailable 유지·재실행 무동작을 확인했다. ready 재사용의 mirror 실패에서도 render 1회·파일 row 1개·COMPLETED 유지·Preview 삭제 없음이 통과했다.
- runner는 앞선 검증과 같은 run-only tmp_path fixture다. 매번 새 UUID 경로를 기본 상속 권한으로 생성하고 TEMP/TMP/TMPDIR와 명시적 --basetemp를 설정하며 cacheprovider를 비활성화한다. 저장소 conftest와 assertion은 약화하지 않는다. 새 runner·로그·format diff는 기존 scratch 아래 보존한다.

### CI 로그와 Ruff

- [Run 38189484323 backend-ubuntu](https://github.com/DohaStudio/DohaMusic/actions/runs/38189484323/job/114618948635)의 decoded 로그를 GitHub connector로 확보했다. Ruff **0.16.4**, Python **3.12.15**, Ubuntu **24.04.5**다. `python -m ruff check --no-cache backend ai_worker`는 통과했고 `python -m ruff format --check --no-cache backend ai_worker`는 5 files would be reformatted / 558 already formatted, exit 1이었다. Backend tests는 skipped다. frontend-playwright/ffmpeg-windows 작업은 success로 확인했으나 이번 로컬 수정 후 CI 결과가 아니다.
- 실제 diff는 contracts의 set indentation, PipelineService 조건 wrapping, PreviewService의 PipelineFile 생성 wrapping, Pipeline API의 조건 wrapping, Preview 테스트의 multiline dict/call·소수 표기·함수 주변 공백이다. CI format 단계 원문과 로컬 `--diff`는 scratch에 보존했다.
- 로컬은 Python **3.12.5**, pytest **8.4.2**, Ruff **0.15.22**다. 같은 범위/pyproject 설정으로 같은 5개 파일의 format 실패를 재현했다. formatter는 그 5개 파일에만 적용했다. 전체 Backend 무차별 포맷은 하지 않았다.
- CI 버전 준비 명령 `python -m pip install --target <scratch>/ruff-0164 --no-cache-dir --disable-pip-version-check ruff==0.16.4`는 **실패**(No matching distribution). PIP_NO_INDEX=1을 확인했고, 실행별 PIP_NO_INDEX=0 및 scratch TEMP/TMP로 재시도해도 패키지를 확보하지 못했다. 전역 설치·권한 변경은 하지 않았고 임시 잔여 디렉터리는 보존했다. **Ruff 0.16.4 로컬 실행은 미검증**이다.
- 수정 후 로컬 `python -m ruff check --no-cache backend ai_worker`: **PASS**. `python -m ruff format --check --no-cache backend ai_worker`: **PASS**, 563 files already formatted. `python -m compileall -q backend ai_worker`: **PASS**. `git diff --check`: **PASS**.

### Backend 전체 실행의 환경 차단

- `python <scratch>/review_runner.py --collect-only -q -m 'not gpu and not paid and not external'`: **3037/3042 collected, 5 deselected** (추가 SQLite 테스트 전 수집). 실제 AI·GPU·외부/유료 테스트는 제외했다.
- `python <scratch>/review_runner.py -q -m 'not gpu and not paid and not external' --maxfail=1`: **14 passed, 1 failed, 5 deselected**, 1.68초, exit 1. 최초 실패는 기존 `test_admission_attempt.py::test_attempt_is_opaque_exact_candidate_and_not_admission[NORMAL_ROTATION]`의 Windows custody fixture `SetFileSecurityW`가 access denied(5)로 실패한 것이다. K3 Preview 코드는 도달하지 않았다. 잔여 3022개는 이 실행에서 미실행이다.
- 전체 실행 전에 이 fixture의 ACL 설정을 식별하지 못했다. disposable scratch 경로에 대한 ACL 설정 호출은 Windows가 거부했다. ACL을 변경하거나 관리자/샌드박스 권한을 높여 재시도하지 않았으며 보안 assertion을 약화하지 않았다. 전체 Backend 통과를 주장하지 않는다. Ubuntu CI와 적절한 Windows fixture 환경에서 재검증이 필요하다.

### K3 대상 전체 회귀 실행

- 명령: `python <scratch>/review_runner.py backend/tests/test_preview_export.py backend/tests/test_pipeline_api.py backend/tests/test_pipeline_file_access_api.py backend/tests/test_hook_analyzer.py backend/tests/test_audio_quality_analyzer.py backend/tests/test_tempo_analyzer.py -q --maxfail=1`.
- 실행 결과: **103 passed, 1 skipped**, 564.44초, exit 0. 이 묶음 실행 시작 이후 추가한 SQLite unavailable 재열기 테스트 1개도 앞의 별도 실행에서 통과했다. 따라서 현재 대상 105개 중 **104 passed / 1 environment skip / 0 failed**다. 별도 반복한 신규 9개와 ready mirror 재사용 1개는 중복 합산하지 않는다.
- Preview 실패 격리·COMPLETED/final 보존·pending startup 복구·ready 재사용·Range·secure file API·K3.3 분석 순서/취소/Retry 회귀가 통과했다. skip은 기존 Windows symlink 생성 권한 테스트다. 전체 Backend의 14 passed/1 환경 실패 실행과 이 K3 회귀 결과는 별도 실행으로 보고하며 전체 suite 성공을 주장하지 않는다.

### 문서 및 잔여 범위

- CHANGELOG와 실패 정책에 결함 수정 및 unavailable mirror 실패 경계를 반영했다. 제품 범위·Phase 진행률·README/Roadmap 완료 상태는 변경하지 않는다. 기존 ADR-023의 DB authoritative/mirror 보조 결정에 따른 수정으로 새 ADR·AI 실험 보고서는 필요하지 않다.
- Frontend 파일·응답 계약 변경이 없어 이번 Frontend typecheck/test/build를 재실행하지 않았다. 이전 수치는 앞 절에 남기며 이번 통과 수로 집계하지 않는다.
- 실제 process kill/power loss·multiprocess 경쟁, 현재 Windows symlink, 이번 수정 후 Ubuntu CI와 Ruff 0.16.4 실행은 별도 확인이 필요하다.
