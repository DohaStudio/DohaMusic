# DohaMusic

> Phase 6.5: OpenAI Responses API Lyrics Adapter가 `Experimental`로 추가되었고 기본 Provider는 계속 `template`입니다. 외부 API Key가 없어 실제 한국어 품질·지연·token·비용은 `[검증 필요]`, EVAL-006은 `[사용자 평가 필요]`입니다.

> Phase 6.6~6.9: 로컬 Lyrics LLM의 Dataset → QLoRA SFT → `local_llm` Adapter → Quality Gate는 `[계획]`입니다. 우선 검토 후보는 Qwen 계열 1.7B~4B Instruct이며 모델·데이터 권리·RTX 3060 Ti 8GB 실측과 품질 검증 전에는 기본 Provider 또는 운영 Pipeline으로 승격하지 않습니다.

External Lyrics는 strict JSON Schema, 안전한 오류·retry, 요청별 명시 fallback, 예상 비용 metadata와 원본 보존 Revision API를 제공합니다. 설정은 [External Lyrics Provider](docs/10-operations/external-lyrics-provider-setup.md), 근거는 [Provider 비교](docs/01-research/lyrics-llm-provider-comparison.md), 결정은 [ADR-015](docs/11-decisions/ADR-015-external-lyrics-llm-provider.md)를 참고하세요.

> 문서 목적: 프로젝트의 목표, 현재 상태, 전체 설계 문서로 가는 시작점을 제공한다.
> 현재 상태: **Phase 6 Lyrics AI 로컬 Template·Mock 기반 완료 — 외부 LLM 도입 보류**
> 최종 수정일: 2026-07-31
> 관련 문서: [Master Roadmap](MASTER_ROADMAP.md), [Phase DoD](docs/DoD/README.md), [Codex 작업 지침](AGENTS.md), [실행 로드맵](ROADMAP.md), [변경 이력](CHANGELOG.md)

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
| [완료] | 교체 가능한 `MusicGenerator` 결과 계약과 Provider Factory |
| [실험 완료] | ACE-Step 1.5 v0.1.8 2B Turbo 로컬 추론·Backend Adapter 연결 |
| [완료] | `StemSeparator`·Mock/Demucs Provider와 비동기 Stem API |
| [실험 완료] | HTDemucs 4.1.0 보컬/반주 분리, 48kHz Stereo 출력, RTX 3060 Ti Benchmark |
| [실험 완료] | 동일 Seed PCM 재현성, 다른 Seed 파형 다양성, 상주 12회 안정성·0.6B LM 실행 |
| [계획] | 프롬프트 및 직접 작성 가사 기반 음악 생성 |
| [계획] | 장르·분위기·BPM·길이·Seed 설정 |
| [완료] | 보컬/반주 분리 Job과 개별 출력 metadata |
| [실험 완료] | `VoiceConverter`·Mock/Seed-VC Provider와 비동기 Voice Conversion API |
| [수동 평가 필요] | 동의받은 본인 참조 음성의 음색·발음·노래 자연스러움 |
| [완료] | Music → Stem → Mock Voice → Default Audio Mixer → WAV Export 비동기 Pipeline |
| [완료] | 단계별 진행률·재시도·timeout 판정·오류·metadata·Benchmark |
| [완료] | 변환 보컬·반주 gain, -1dBFS headroom, peak normalization, soft limiter, fade, 48kHz WAV 합성 |
| [수동 평가 필요] | 최종 Mixer volume·balance·naturalness·noise·clipping 청감 |
| [완료] | `LyricsGenerator`·Template/Mock Provider와 동기식 가사 생성·조회·검증·삭제 API |
| [완료] | 한국어·영어 구조화 가사, 섹션 파싱, 입력 정제, 길이·반복·구조 검증과 metadata 저장 |
| [수동 평가 필요] | EVAL-005 가사 주제 적합성·자연스러움·후렴 기억성·창작 활용성 평가 |
| [계획] | 권리 추적 가능한 한국어 Lyrics Dataset 구축과 QLoRA SFT |
| [계획] | 기존 `LyricsGenerator` 계약을 유지하는 `local_llm` Provider Adapter 및 품질 게이트 |
| [계획] | MP3 변환 |
| [계획] | 비동기 작업 상태·진행률·오류·재시도 관리 |
| [계획] | 생성 이력과 사용 모델·버전·설정 기록 |
| [부분 검증] | RTX 3060 Ti 8GB 실행 가능성·유효 WAV 출력 |
| [수동 평가 필요] | 한국어 발음·가사 정렬·음악성·청감 잡음 |

음악 생성·Stem 분리·Voice Conversion의 기본 Provider는 계속 Mock이다. 선택적 ACE-Step, Demucs, Seed-VC Adapter는 격리 subprocess를 실행하며 설치와 모델 경로를 명시한 경우에만 동작한다. Mixer 기본값은 AI와 독립된 `DefaultAudioMixer`이며 Mock은 테스트용으로 유지한다. Lyrics 기본값은 외부 통신이 없는 `TemplateLyricsGenerator`이고, 실제 LLM 품질이나 자유 형식 수정 반영을 주장하지 않는다. Phase 4.6에서 Voice Primary와 Fallback은 미선정됐으므로 실제 음색 변환 품질이나 운영 배포 승인을 의미하지 않는다. Mixer와 가사 품질도 각각 EVAL-004·EVAL-005 사용자 평가 전에는 승인하지 않는다. 모델·가중치·개인 음성·실험 오디오는 저장소에 포함하지 않으며 인증, Frontend, Redis/Celery는 구현하지 않았다.

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
- Backend/Orchestrator: FastAPI + PipelineExecutor **[완료]**
- Persistence: SQLAlchemy 2, Alembic, SQLite **[완료]**
- AI Worker: Provider-neutral 공유 ThreadPool Worker **[완료]**, 격리형 ACE-Step·Demucs·Seed-VC subprocess **[실험 완료]**
- Database: SQLite **[완료]**, PostgreSQL/MySQL 교체 **[계획]**
- Task Queue: 프로세스 내부 단일 ThreadPool **[완료]**, 외부 Queue **[계획]**
- Audio Storage: 로컬 파일 저장소 **[완료]**, S3 호환 객체 저장소 **[계획]**
- Audio DSP: NumPy·SciPy 기반 Default Mixer **[완료]**, True Peak·LUFS **[계획]**
- Lyrics: 로컬 Template·Mock Provider **[완료]**, OpenAI Provider **[Experimental]**, QLoRA 기반 로컬 LLM·`local_llm` Provider **[계획]**
- AI 모델: 어댑터를 통한 교체 가능한 공개 사전학습 모델

모델명은 후보일 뿐이며, 라이선스와 로컬 벤치마크를 통과하기 전에는 채택하지 않는다. 자세한 기준은 [모델 비교](docs/01-research/model-comparison.md)와 [모델 선정 정책](docs/04-models/model-selection-policy.md)을 따른다.

## 저장소 구조

```text
DohaMusic/
├─ backend/    # FastAPI, DB, Worker, AI interface·adapter, tests
├─ ai_worker/  # 선택적 로컬 AI 실행기와 재현용 benchmark 입력
├─ docs/       # 개요, 조사, 요구사항, 설계, 정책, 운영, ADR, Phase DoD
├─ planning/   # 단계별 실행 계획과 백로그
├─ reports/    # 실험 및 벤치마크 기록 템플릿
├─ MASTER_ROADMAP.md
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

전체 Phase·진행률·선행 조건·산출물은 [Master Roadmap](MASTER_ROADMAP.md), 완료 판정은 [Phase별 Definition of Done](docs/DoD/README.md), 현재 실행 우선순위는 [ROADMAP](ROADMAP.md)에서 관리한다. 새 기능 작업은 `MASTER_ROADMAP → 해당 Phase DoD → AGENTS.md` 순서로 확인한다.

Phase 2 설치·연결은 [EXP-001](reports/experiments/EXP-001-ace-step-local-inference.md), Phase 2.5 재현성·운영 판단은 [EXP-002](reports/experiments/EXP-002-ace-step-quality-and-stability.md), Phase 3 Stem 분리 실측은 [EXP-003](reports/experiments/EXP-003-stem-separation.md)에 있다. 생성 품질은 [EVAL-001](reports/evaluations/EVAL-001-ace-step-listening-evaluation.md), Stem 품질은 [EVAL-002](reports/evaluations/EVAL-002-stem-separation-listening-evaluation.md)에 사용자가 직접 기록한다.

## 문서 안내

- 저장소 작업 규칙: [Codex 작업 지침](AGENTS.md)
- 전체 일정과 완료 기준: [Master Roadmap](MASTER_ROADMAP.md), [Phase DoD](docs/DoD/README.md), [실행 로드맵](ROADMAP.md)
- 목표와 범위: [프로젝트 개요](docs/00-overview/project-overview.md), [목표와 비목표](docs/00-overview/goals-and-non-goals.md)
- 요구사항: [기능 요구사항](docs/02-requirements/functional-requirements.md), [인수 기준](docs/02-requirements/acceptance-criteria.md)
- 시스템 설계: [시스템 아키텍처](docs/03-architecture/system-architecture.md), [AI 파이프라인](docs/03-architecture/ai-pipeline.md)
- API와 데이터: [API 개요](docs/06-api/api-overview.md), [ERD](docs/07-database/erd.md)
- 안전과 권리: [음성 동의 정책](docs/09-security/voice-consent-policy.md), [생성 콘텐츠 정책](docs/09-security/generated-content-policy.md)
- 의사결정: [ADR 목록](docs/11-decisions/README.md)
- Pipeline: [Orchestrator](docs/03-architecture/pipeline-orchestrator.md), [Audio Quality Engine](docs/03-architecture/audio-quality-engine.md), [API](docs/06-api/pipeline-api.md), [EXP-005](reports/experiments/EXP-005-pipeline-execution.md), [EXP-006](reports/experiments/EXP-006-audio-mixing.md), [EVAL-004](reports/evaluations/EVAL-004-audio-mixing-listening-evaluation.md)
- Lyrics AI: [Architecture](docs/03-architecture/lyrics-ai.md), [Local LLM 계획](planning/phase-6-local-lyrics-llm-plan.md), [API](docs/06-api/lyrics-api.md), [ADR-014](docs/11-decisions/ADR-014-lyrics-generator-architecture.md), [ADR-016](docs/11-decisions/ADR-016-local-lyrics-llm-finetuning.md), [EXP-007](reports/experiments/EXP-007-lyrics-generation.md), [EVAL-005](reports/evaluations/EVAL-005-lyrics-quality.md)

## 안전 및 음성 사용 정책

본인 음성 또는 명시적으로 사용 동의를 받은 음성만 등록할 수 있다. 동의 증적과 철회 상태를 기록하고, 철회 또는 계정 삭제 시 원본 음성과 파생 음성 데이터를 삭제할 수 있어야 한다. 타인 음성의 무단 복제, 사칭, 권리 침해 목적 사용은 지원하지 않는다. 세부 시스템 요구사항은 [음성 동의 정책](docs/09-security/voice-consent-policy.md)에 정의한다.

## 라이선스 검토 상태

- 저장소 코드와 문서: [Apache License 2.0](LICENSE)
- AI 모델·가중치·데이터셋·의존성: **[검증 필요]**
- 상업적 이용 가능 여부: 모델별로 별도 판정하며 추정하지 않는다.

Seed-VC 기술 실측은 [EXP-004](reports/experiments/EXP-004-seed-vc.md), 사용자 음색 평가는 [EVAL-003](reports/evaluations/EVAL-003-seed-vc-listening-evaluation.md)에 분리한다. Phase 4.5 결정은 [QG-001](reports/quality-gates/QG-001-voice-conversion-operational-readiness.md), Provider 수명주기는 [ADR-010](docs/11-decisions/ADR-010-voice-provider-selection-policy.md), Phase 4.6 비교·점수·선정은 [Provider 비교](docs/01-research/voice-provider-comparison.md), [Provider Score](docs/04-models/voice-provider-score.md), [ADR-011](docs/11-decisions/ADR-011-voice-provider-selection.md)을 따른다.

검토 절차와 승인 기준은 [라이선스 검토](docs/01-research/licensing-review.md)를 따른다.
