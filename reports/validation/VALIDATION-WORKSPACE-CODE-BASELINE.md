# DohaMusic 코드 기준선 안정화 검토

> 문서 상태: [완료]
> 검토일: 2026-08-06
> 대상: `main` `36760707e092e084e9cae1985e9850b5b026667d` → `develop` `877fea4a912ba10d270c0f18631a3531bc2a194d`
> 관련 기능: 전체 제품 코드 기준선의 `main` 승격 준비
> 관련 문서: [README](../../README.md), [실행 로드맵](../../ROADMAP.md), [변경 이력](../../CHANGELOG.md), [시스템 아키텍처](../../docs/03-architecture/system-architecture.md)

## 1. 결론

현재 `develop` 전체는 **main 승격 불가**로 판정한다. Backend·Frontend·AI Worker·Alembic과 대표 회귀 검증은 통과했지만 Frontend dependency tree 재현성 및 보안 Gate에 BLOCKER 1건이 남아 있다.

- BLOCKER: 1건
- WARNING: 6건
- PR #55 포함 여부: 미포함
- `develop → main` PR: 이번 작업에서 생성하지 않음

BLOCKER를 별도 작업 브랜치에서 해결하고 동일 검증을 다시 통과한 뒤 `develop → main` Draft PR을 생성한다.

## 2. Diff 분류

중복 집계를 피하기 위해 `테스트 → Alembic → 스크립트 → 문서 → AI Worker → Frontend → Backend → 설정 → 기타` 순서로 분류했다.

| 범주 | 파일 수 | 주요 변경 목적 |
|---|---:|---|
| Backend | 165 | FastAPI, AI Adapter, Service, Repository, Storage, Worker와 기존 14개 Runtime Entity |
| Frontend | 81 | Next.js App Router, Studio·Project·History·Voice UI, 상태 관리와 API Client |
| AI Worker | 7 | 모델 다운로드가 필요 없는 WAV 비교·Benchmark 집계와 Benchmark metadata |
| Alembic | 14 | Alembic 설정·환경과 `20260729_0001`부터 `20260801_0011`까지 11개 Revision |
| 테스트 | 59 | Backend 단위·API·통합 테스트와 Frontend Vitest·Playwright 테스트 |
| 문서 | 170 | 요구사항·Architecture·API·DB·보안·운영·ADR·DoD·실험·평가 문서 |
| 설정 | 3 | GitHub Actions, `.gitignore`, Python package·pytest 설정 |
| 스크립트 | 13 | ACE-Step·Demucs·Seed-VC 실행·Benchmark와 Backend Benchmark 스크립트 |
| 기타 | 0 | 없음 |
| 합계 | 512 | 전체 제품 기준선 |

Frontend 81개와 Frontend 테스트 24개를 합하면 사용자 제시 기준인 105개다. Backend 165개, Alembic 14개, Backend 테스트 35개, Backend 스크립트 5개를 합하면 219개다.

## 3. Backend 검증

| 항목 | 결과 | 근거 |
|---|---|---|
| FastAPI import | PASS | `backend.main`, `create_app()` import·생성 성공 |
| API Router import | PASS | 41개 Route 등록 확인 |
| SQLAlchemy 모델 import | PASS | `backend.models` import 성공 |
| 기존 Runtime Entity | PASS | 14개 Table mapper 구성과 in-memory SQLite `create_all` 성공 |
| 환경 변수 누락 처리 | PASS | 외부 환경 변수 없이 mock Provider와 SQLite 기본값 검증 |
| SQLite 실행 가능성 | PASS | in-memory metadata 생성과 DB·Repository 테스트 통과 |
| Python compile | PASS | `backend`, `ai_worker` `compileall` 성공 |
| Ruff | WARNING | 실행 경로를 먼저 등록하는 AI Worker 스크립트 3개에서 `E402` 발생 |

Ruff WARNING 파일은 다음과 같다.

- `ai_worker/scripts/compare_audio_outputs.py`
- `ai_worker/scripts/run_ace_step_benchmark.py`
- `ai_worker/scripts/run_demucs_benchmark.py`

## 4. Frontend 검증

| 항목 | 결과 | 근거 |
|---|---|---|
| `npm ci` | PASS | lockfile 기준 461개 package 설치 성공 |
| lint | PASS | `npm run lint` 성공 |
| typecheck | PASS | `npm run typecheck` 성공 |
| production build | PASS | 외부 Google Fonts 접근이 가능한 환경에서 12개 Route build 성공 |
| Vitest | PASS | 20개 Test File, 97개 Test 통과 |
| 환경 변수 기본값 | PASS | `/backend`, `http://127.0.0.1:8000` 안전한 로컬 기본값 확인 |
| 사용자 `next-env.d.ts` | PASS | 원본 작업 트리의 미커밋 변경은 격리 clone과 PR 범위에 포함하지 않음 |
| dependency tree | BLOCKER | `npm ls`가 `postcss`, `minimatch` override 불일치로 `ELSPROBLEMS` 반환 |
| dependency audit | BLOCKER | `high` 2건, `moderate` 2건 확인 |

취약점과 tree 불일치는 자동 수정하지 않았다. `brace-expansion`, `minimatch`, `next`, `postcss`의 호환 가능한 고정 버전을 별도 dependency 안정화 PR에서 결정하고 lockfile·lint·typecheck·build·Vitest·audit를 다시 검증해야 한다.

## 5. Alembic 검증

- 단일 head: `20260801_0011`
- Revision 수: 11개
- 중복 Revision ID: 없음
- Revision chain 탐색: 성공
- 실제 DB Migration 실행: 수행하지 않음

## 6. AI Worker와 FFmpeg

| 항목 | 결과 | 근거 |
|---|---|---|
| `ai_worker` import | PASS | package, WAV similarity, Benchmark helper import 성공 |
| 모델 없는 단위 테스트 | PASS | Adapter·Audio·Benchmark 관련 테스트 통과 |
| FFmpeg | PASS | Windows 로컬 `ffmpeg`·`ffprobe` 8.1.2 실행 확인 |
| 운영 절대 경로 | PASS | 운영 코드에서 로컬 절대 경로 하드코딩 없음 |

절대 경로 검색 결과 9건은 모두 경로 비노출·검증 동작을 확인하는 테스트 fixture다.

## 7. 테스트 결과

| 구분 | 결과 |
|---|---:|
| Backend 핵심 단위 테스트 | 119 passed |
| DB·Migration·Repository | 15 passed |
| Generation·History·Lyrics·Stem·Voice Conversion·Enrollment API | 36 passed |
| Voice Enrollment Audio | 23 passed |
| Pipeline·파일 접근 대표 smoke | 2 passed |
| Backend 합계 | 195 passed |
| Frontend Vitest | 97 passed |

전체 API 묶음은 누적 실행 시간이 4분 제한을 넘겨 완료 결과를 얻지 못했다. 동일 범주의 주요 파일을 분리 실행해 모두 통과했다. Pipeline 전체 38개, Playwright E2E, GPU·외부 API·유료·모델 통합 테스트는 실행 비용과 외부 의존성 때문에 수행하지 않았고 대표 smoke로 제한했다.

## 8. 보안·데이터·라이선스

| 항목 | 결과 | 근거 |
|---|---|---|
| 비밀정보 | PASS | Private key·GitHub·OpenAI·AWS key 주요 패턴 0건 |
| Dataset·모델·Checkpoint·미디어 | PASS | 금지 확장자 Git 추적 파일 0개 |
| 대용량 파일 | PASS | 1MB 초과 Git 추적 파일 0개 |
| Git LFS 객체 | PASS | 추적 객체 없음 |
| 저장소 LICENSE | PASS | Apache License 2.0 공식 영문 본문과 일치 |
| 외부 Provider 권리 | WARNING | 모델·가중치·Dataset·배포 방식의 상업 이용과 재배포 조건은 별도 검토 상태 유지 |

기본 Provider가 mock이고 외부 모델·가중치를 Git에 포함하지 않으므로 외부 Provider 라이선스 검토 상태는 이번 코드 기준선 승격의 직접 BLOCKER로 분류하지 않는다. 실제 상업 배포 전에는 `commercial_approved` Gate를 통과해야 한다.

## 9. 문서와 구현

- 현행 14개 Runtime Table이 source of truth라는 문서와 구현이 일치한다.
- 목표 21개 Entity·Table은 문서 설계이며 PR #55의 구현은 현재 `develop`에 포함되지 않는다.
- 목표 Workspace REST API는 `[계획]`이고 현행 `/api` Router와 구분된다.
- `git diff --check` 오류를 만들던 6개 문서의 trailing whitespace와 EOF 공백만 제거했다.
- Architecture, API, DB, Runtime 상태와 책임 경계는 변경하지 않았다.

## 10. 판정

| 검토 항목 | 판정 | 설명 |
|---|---|---|
| Backend 실행 불가 | PASS | import·app 생성·대표 테스트 통과 |
| Frontend build 실패 | PASS | production build 통과 |
| Alembic head 불일치 | PASS | 단일 head 확인 |
| 테스트 실패 | PASS | 실행한 292개 테스트 모두 통과 |
| 비밀정보 포함 | PASS | 주요 패턴 0건 |
| 절대 경로 하드코딩 | PASS | 운영 코드 0건 |
| Dataset·모델·Checkpoint Git 포함 | PASS | 0건 |
| 라이선스 문제 | WARNING | 외부 Provider 상업 이용·재배포 검토 유지 |
| 문서와 구현 불일치 | PASS | 현행과 목표 상태 구분 확인 |
| main 승격 시 회귀 가능성 | WARNING | 512개 전체 제품 기준선과 미실행 통합·E2E 범위 |
| Frontend dependency 재현성·보안 | BLOCKER | `npm ls` 실패와 high audit 2건 |

WARNING 6개 범주는 Python Ruff `E402`, OpenAPI HEAD Route 중복 operation ID, Python 3.12 SQLite datetime adapter 폐기 예정, Google Fonts build 네트워크 의존, 외부 Provider 권리 검토, 512개 변경과 미실행 통합·E2E 범위의 회귀 가능성이다.

## 11. PR #55 격리

- PR #55 head: `feature/sqlalchemy-entities`
- PR #55 commit: `17eaf2cdf38ab79ddaa97885a66e2898cbec8e47`
- 위 commit은 검토 대상 `develop`의 조상이 아니다.
- `backend/models/workspace/*`와 `backend/tests/test_workspace_entities.py`는 512개 diff에 포함되지 않는다.
- 이번 안정화 브랜치는 PR #55를 수정·병합하지 않는다.

## 12. 다음 Gate

1. Frontend dependency override·lockfile을 별도 작업 브랜치에서 정합화한다.
2. `npm ci`, `npm ls`, `npm audit`, lint, typecheck, build, Vitest를 다시 실행한다.
3. high 취약점 0건과 dependency tree 정상화를 확인한다.
4. 이번 안정화 PR을 `develop`에 병합한다.
5. 최신 `develop`에서 BLOCKER 0건과 PR #55 미포함을 재검증한다.
6. 그 이후에만 `develop → main` Draft PR을 생성한다.
