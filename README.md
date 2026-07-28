# DohaMusic

> 문서 목적: 프로젝트의 목표, 현재 상태, 전체 설계 문서로 가는 시작점을 제공한다.
> 현재 상태: **Backend Foundation 완료 — Phase 1**
> 최종 수정일: 2026-07-29
> 관련 문서: [Codex 작업 지침](AGENTS.md), [개발 로드맵](ROADMAP.md), [변경 이력](CHANGELOG.md)

DohaMusic은 자연어 프롬프트 또는 사용자가 작성한 가사를 바탕으로 노래를 생성하고, 생성된 보컬을 동의받은 사용자의 목소리로 변환해 완성 음원을 만드는 개인 창작용 AI 음악 생성 플랫폼이다.

## 최종 목표

사용자가 음악적 전문 지식 없이도 자신의 가사와 목소리로 재현 가능한 곡을 만들고, 생성 과정·모델·권리 정보를 확인할 수 있는 안전한 제작 환경을 제공한다.

## 핵심 기능과 현재 상태

| 상태 | 기능 |
|---|---|
| [완료] | FastAPI Router·Service·Repository·SQLAlchemy 기반 Backend Foundation |
| [완료] | SQLite·Alembic 초기 schema와 로컬 Storage 구성 |
| [완료] | Mock Worker 기반 비동기 Job 생성·조회·결과 파일 목록 |
| [완료] | 동의 확인이 필수인 음성 프로필 생성·삭제 API |
| [계획] | 프롬프트 및 직접 작성 가사 기반 음악 생성 |
| [계획] | 장르·분위기·BPM·길이·Seed 설정 |
| [계획] | 보컬/반주 분리 및 개별 출력 |
| [계획] | 동의받은 참조 음성을 이용한 보컬 음색 변환 |
| [계획] | 변환 보컬과 반주 믹싱, WAV 저장 및 MP3 변환 |
| [계획] | 비동기 작업 상태·진행률·오류·재시도 관리 |
| [계획] | 생성 이력과 사용 모델·버전·설정 기록 |
| [검증 필요] | 한국어 가사 발음, 음질, 음색 유사도 및 8GB VRAM 적합성 |

현재 구현은 Mock adapter가 3초 후 무음 샘플 WAV를 복사하는 Backend Foundation이다. 실제 음악 생성·음색 변환, 인증, Frontend, Redis/Celery, GPU 처리는 아직 구현하지 않았다.

## 전체 AI 생성 흐름

```mermaid
flowchart LR
  I[프롬프트와 가사] --> G[음악·가창 생성]
  G --> S[보컬·반주 분리]
  R[동의된 참조 음성] --> V[음색 변환]
  S --> V
  S --> M[믹싱]
  V --> M
  M --> E[WAV·MP3 인코딩]
  E --> O[결과·메타데이터 저장]
```

## 예상 기술 스택

- Frontend: Next.js
- Backend/Orchestrator: FastAPI **[완료]**
- Persistence: SQLAlchemy 2, Alembic, SQLite **[완료]**
- AI Worker: Python ThreadPool Mock Worker **[완료]**, PyTorch Worker **[계획]**
- Database: SQLite **[완료]**, PostgreSQL/MySQL 교체 **[계획]**
- Task Queue: 프로세스 내부 단일 ThreadPool **[완료]**, 외부 Queue **[계획]**
- Audio Storage: 로컬 파일 저장소 **[완료]**, S3 호환 객체 저장소 **[계획]**
- AI 모델: 어댑터를 통한 교체 가능한 공개 사전학습 모델

모델명은 후보일 뿐이며, 라이선스와 로컬 벤치마크를 통과하기 전에는 채택하지 않는다. 자세한 기준은 [모델 비교](docs/01-research/model-comparison.md)와 [모델 선정 정책](docs/04-models/model-selection-policy.md)을 따른다.

## 저장소 구조

```text
DohaMusic/
├─ backend/    # FastAPI, DB, Mock Worker, AI interface, tests
├─ docs/       # 개요, 조사, 요구사항, 설계, 정책, 운영, ADR
├─ planning/   # 단계별 실행 계획과 백로그
├─ reports/    # 실험 및 벤치마크 기록 템플릿
├─ README.md
├─ ROADMAP.md
├─ CHANGELOG.md
└─ CONTRIBUTING.md
```

## 빠른 시작

Python 3.11 이상이 필요하다.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m alembic -c backend/alembic.ini upgrade head
python -m uvicorn backend.main:app --reload
```

API 문서는 실행 후 `http://127.0.0.1:8000/docs`, health는 `GET /health`에서 확인한다. 테스트는 `python -m pytest -q`로 실행한다. 자세한 설정은 [로컬 개발 환경](docs/10-operations/local-development.md)을 따른다.

## 개발 로드맵

Phase 1 Backend Foundation 이후 Phase 2 AI Adapter·로컬 추론부터 Phase 7 개인화 학습 검토까지의 단계와 진입 조건은 [ROADMAP.md](ROADMAP.md)에 있다.

## 문서 안내

- 저장소 작업 규칙: [Codex 작업 지침](AGENTS.md)
- 목표와 범위: [프로젝트 개요](docs/00-overview/project-overview.md), [목표와 비목표](docs/00-overview/goals-and-non-goals.md)
- 요구사항: [기능 요구사항](docs/02-requirements/functional-requirements.md), [인수 기준](docs/02-requirements/acceptance-criteria.md)
- 시스템 설계: [시스템 아키텍처](docs/03-architecture/system-architecture.md), [AI 파이프라인](docs/03-architecture/ai-pipeline.md)
- API와 데이터: [API 개요](docs/06-api/api-overview.md), [ERD](docs/07-database/erd.md)
- 안전과 권리: [음성 동의 정책](docs/09-security/voice-consent-policy.md), [생성 콘텐츠 정책](docs/09-security/generated-content-policy.md)
- 의사결정: [ADR 목록](docs/11-decisions/README.md)

## 안전 및 음성 사용 정책

본인 음성 또는 명시적으로 사용 동의를 받은 음성만 등록할 수 있다. 동의 증적과 철회 상태를 기록하고, 철회 또는 계정 삭제 시 원본 음성과 파생 음성 데이터를 삭제할 수 있어야 한다. 타인 음성의 무단 복제, 사칭, 권리 침해 목적 사용은 지원하지 않는다. 세부 시스템 요구사항은 [음성 동의 정책](docs/09-security/voice-consent-policy.md)에 정의한다.

## 라이선스 검토 상태

- 저장소 코드와 문서: [Apache License 2.0](LICENSE)
- AI 모델·가중치·데이터셋·의존성: **[검증 필요]**
- 상업적 이용 가능 여부: 모델별로 별도 판정하며 추정하지 않는다.

검토 절차와 승인 기준은 [라이선스 검토](docs/01-research/licensing-review.md)를 따른다.
