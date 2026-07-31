# DohaMusic 실행 로드맵

## Phase 6.5 후속 게이트

1. 사용자의 별도 승인과 API Key·비용 승인을 모두 받은 opt-in 환경에서만 한국어 발라드·시티팝·구조 유지 수정·영문 팝을 실제 측정한다. 승인 전 상태는 `[유료 실측 미수행]`이다.
2. EVAL-006에서 Template/External 결과를 사용자가 블라인드 평가한다.
3. OpenAI 데이터 보존·ZDR/DPA·상업 이용·생성물 권리의 법률·보안 검토를 완료한다.
4. 5초를 넘는 운영 호출은 비동기 Job으로 전환하고 인증·소유권·사용량 한도를 설계한다.
5. 위 게이트 전에는 External Provider를 Stable로 승격하거나 Pipeline에 자동 연결하지 않는다.

## Phase 6.6~6.9 Local Lyrics LLM 후속 확장

1. Phase 6.6에서 권리 확보 text Dataset·manifest·version·split을 승인한다.
2. Phase 6.7에서 Qwen 계열 1.7B~4B Instruct와 동급 공개 후보의 license·한국어·8GB 실행성을 비교하고 QLoRA SFT를 검증한다.
3. Phase 6.8에서 결과를 기존 `LyricsGenerator` 계약의 `LocalLyricsLLMAdapter`로 격리한다.
4. Phase 6.9에서 Validator·한국어 품질·응답 시간·peak VRAM·실패율·사용자 blind 평가를 통과해야 운영 승격을 검토한다.
5. 모든 게이트 전까지 Base 미선정·Dataset 미구축·학습 미착수·Adapter 미구현 상태이며 기본 Provider는 `template`이다.

> 문서 상태: [운영 중]
> 최종 수정일: 2026-08-01
> 현재 상태: **Phase 6 Template·Mock 기반 완료 / Local Lyrics LLM 계획 0% / 외부 LLM·운영 Voice Provider 보류**
> 상위 기준: [Master Roadmap](MASTER_ROADMAP.md)
> 완료 기준: [Phase별 Definition of Done](docs/DoD/README.md)

이 문서는 현재 실행 순서와 가까운 다음 작업만 요약한다. 전체 Phase의 목표·포함·제외·선행 조건·산출물·진행률은 `MASTER_ROADMAP.md`, 세부 완료 판정은 해당 DoD를 따른다. 같은 설명을 여러 문서에 복제하지 않는다.

## 현재 Phase 현황

| Phase | 상태 | 현재 판정 | DoD |
|---|---|---|---|
| 0. 프로젝트 문서화 | [완료] | 초기 설계·정책·문서 체계 구축 | Master Phase 0 |
| 1. Backend Foundation | [완료] | FastAPI·DB·Mock Job E2E | [Phase-01](docs/DoD/Phase-01.md) |
| 2. Music Generation | [진행 중] | ACE-Step 조건부 채택, 기본 `mock`, 운영 Provider 미확정·EVAL-001 진행 중 | [Phase-02](docs/DoD/Phase-02.md) |
| 2.5 Quality Benchmark | [진행 중] | 재현성·반복·운영 수명 검증 완료, EVAL-001 사용자 평가 진행 중 | [Phase-02.5](docs/DoD/Phase-02.5.md) |
| 3. Stem Separation | [완료] | HTDemucs Adapter·API·Benchmark·EVAL 양식 | [Phase-03](docs/DoD/Phase-03.md) |
| 4. Voice Conversion | [검증 필요] | Provider 평가 완료, Primary·Fallback 미선정, 94% 유지 | [Phase-04](docs/DoD/Phase-04.md) |
| 5. Pipeline Integration | [완료] | Mock Voice 기반 Orchestrator·실제 Audio Mixer·API·Benchmark 검증 | [Phase-05](docs/DoD/Phase-05.md) |
| 6. Lyrics AI | [완료] | Template·Mock Generator·동기 API·검증·EXP/EVAL/ADR 완료 | [Phase-06](docs/DoD/Phase-06.md) |
| 6.6~6.9 Local Lyrics LLM | [계획] | Dataset·QLoRA·Adapter·Quality Gate 미착수 | [Roadmap](planning/local-lyrics-llm-roadmap.md) |
| 7. Doha Voice | [계획] | Dataset·개인화 학습 미착수 | [Phase-07](docs/DoD/Phase-07.md) |
| 8. Doha Studio | [완료] | 100%: 로컬 단일 사용자 Voice·History·Project·WAV Player/Download·Cancel·Retry 완료 | [Phase-08](docs/DoD/Phase-08.md) |
| K0~K4. K-POP Creation Control | [진행 중] | K0·K1·K2·K3.0·K3.1·K3.2·K3.3 완료, K3.4 Preview Export 다음 구현 | [K-POP Roadmap](planning/kpop-creation-roadmap.md) |
| 9. Production | [계획] | 운영 인프라 미구현 | [Phase-09](docs/DoD/Phase-09.md) |

## 현재 우선 작업

1. [EVAL-005](reports/evaluations/EVAL-005-lyrics-quality.md)에서 실제 가사 초안의 주제 적합성·자연스러움·후렴 기억성·창작 활용성을 사용자가 평가한다.
2. 외부 Lyrics LLM 후보는 공식 API·라이선스·데이터 처리·비용·한국어 품질 근거를 확보한 뒤 별도 ADR로 검토한다.
3. [Local Lyrics LLM Roadmap](planning/local-lyrics-llm-roadmap.md)에 따라 Phase 6.6 Dataset 권리·manifest를 먼저 확정한다.
4. [EVAL-004](reports/evaluations/EVAL-004-audio-mixing-listening-evaluation.md)에서 실제 곡의 balance·자연스러움·noise·clipping을 사용자가 평가한다.
5. RVC 또는 상업 사용 가능한 zero-shot SVC 후보의 RTX 3060 Ti·라이선스·청취 게이트를 계속 검토한다.
6. [EVAL-003](reports/evaluations/EVAL-003-seed-vc-listening-evaluation.md), [EVAL-002](reports/evaluations/EVAL-002-stem-separation-listening-evaluation.md), [EVAL-001](reports/evaluations/EVAL-001-ace-step-listening-evaluation.md)을 완료한다.
7. Production 전 Pipeline 취소·복구·idempotency와 외부 Queue 요구사항을 정의한다.
8. [Frontend Roadmap](planning/frontend-roadmap.md)의 F5에서 Voice·History·Project·audio content/download·Cancel·Retry를 완료했다. 인증·소유권·분산 Queue는 Phase 9에서 다룬다.
9. Phase 2 후속 평가는 Korean Dance Pop을 대표 시나리오로 삼고 0.6B LM·120~128 BPM·60~90초·동일 Prompt·3개 이상 Seed 조건을 검증한다. Instrumental과 Korean Ballad는 보조 비교군으로 유지한다.
10. [K-POP Creation Roadmap](planning/kpop-creation-roadmap.md)의 K3.3 Hook Candidate까지 완료했다. 다음은 별도 PR의 K3.4 Preview Export이며 LoRA·Dataset·Voice 학습은 K4 이후로 유지한다.

## 다음 작업 흐름

```text
Phase 5.1: 실제 Audio Mixer 완료
  ↓
Phase 6: 로컬 Lyrics AI 기반 완료
  ↓ 선택적 후속 확장
Phase 6.6 Dataset → 6.7 QLoRA SFT → 6.8 Adapter → 6.9 Quality Gate
  ↓ 병행
Voice Primary·Mixer 청감 품질 게이트
  ↓
운영 Pipeline 승인
```

## 완료 처리 규칙

- 구현되지 않은 기능과 실행하지 않은 테스트는 완료로 표시하지 않는다.
- Phase 상태 변경 시 Master Roadmap, 해당 DoD, README와 CHANGELOG를 같은 작업에서 검토한다.
- AI 품질은 Codex가 추정하지 않고 EXP의 객관 지표와 EVAL의 사용자 평가를 분리한다.
- 일반 작업은 작업 브랜치 → `develop` PR로 병합하며 `main`은 명시적 안정화 요청에서만 변경한다.

미확정 세부 작업은 [백로그](planning/backlog.md), 주요 기술 결정은 [ADR 목록](docs/11-decisions/README.md), 실험 근거는 [reports](reports/)에서 추적한다.
