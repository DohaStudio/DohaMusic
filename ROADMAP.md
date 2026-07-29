# DohaMusic 실행 로드맵

> 문서 상태: [운영 중]
> 최종 수정일: 2026-07-29
> 현재 상태: **Phase 6 로컬 Lyrics AI 기반 완료 / 외부 LLM·운영 Voice Provider 보류**
> 상위 기준: [Master Roadmap](MASTER_ROADMAP.md)
> 완료 기준: [Phase별 Definition of Done](docs/DoD/README.md)

이 문서는 현재 실행 순서와 가까운 다음 작업만 요약한다. 전체 Phase의 목표·포함·제외·선행 조건·산출물·진행률은 `MASTER_ROADMAP.md`, 세부 완료 판정은 해당 DoD를 따른다. 같은 설명을 여러 문서에 복제하지 않는다.

## 현재 Phase 현황

| Phase | 상태 | 현재 판정 | DoD |
|---|---|---|---|
| 0. 프로젝트 문서화 | [완료] | 초기 설계·정책·문서 체계 구축 | Master Phase 0 |
| 1. Backend Foundation | [완료] | FastAPI·DB·Mock Job E2E | [Phase-01](docs/DoD/Phase-01.md) |
| 2. Music Generation | [진행 중] | ACE-Step 기술 연결 완료, EVAL-001 대기 | [Phase-02](docs/DoD/Phase-02.md) |
| 2.5 Quality Benchmark | [진행 중] | 재현성·반복·운영 수명 검증 완료, EVAL-001 대기 | [Phase-02.5](docs/DoD/Phase-02.5.md) |
| 3. Stem Separation | [완료] | HTDemucs Adapter·API·Benchmark·EVAL 양식 | [Phase-03](docs/DoD/Phase-03.md) |
| 4. Voice Conversion | [검증 필요] | Provider 평가 완료, Primary·Fallback 미선정, 94% 유지 | [Phase-04](docs/DoD/Phase-04.md) |
| 5. Pipeline Integration | [완료] | Mock Voice 기반 Orchestrator·실제 Audio Mixer·API·Benchmark 검증 | [Phase-05](docs/DoD/Phase-05.md) |
| 6. Lyrics AI | [완료] | Template·Mock Generator·동기 API·검증·EXP/EVAL/ADR 완료 | [Phase-06](docs/DoD/Phase-06.md) |
| 7. Doha Voice | [계획] | Dataset·개인화 학습 미착수 | [Phase-07](docs/DoD/Phase-07.md) |
| 8. Doha Studio | [계획] | Frontend 미구현 | [Phase-08](docs/DoD/Phase-08.md) |
| 9. Production | [계획] | 운영 인프라 미구현 | [Phase-09](docs/DoD/Phase-09.md) |

## 현재 우선 작업

1. [EVAL-005](reports/evaluations/EVAL-005-lyrics-quality.md)에서 실제 가사 초안의 주제 적합성·자연스러움·후렴 기억성·창작 활용성을 사용자가 평가한다.
2. 외부 Lyrics LLM 후보는 공식 API·라이선스·데이터 처리·비용·한국어 품질 근거를 확보한 뒤 별도 ADR로 검토한다.
3. [EVAL-004](reports/evaluations/EVAL-004-audio-mixing-listening-evaluation.md)에서 실제 곡의 balance·자연스러움·noise·clipping을 사용자가 평가한다.
4. RVC 또는 상업 사용 가능한 zero-shot SVC 후보의 RTX 3060 Ti·라이선스·청취 게이트를 계속 검토한다.
5. [EVAL-003](reports/evaluations/EVAL-003-seed-vc-listening-evaluation.md), [EVAL-002](reports/evaluations/EVAL-002-stem-separation-listening-evaluation.md), [EVAL-001](reports/evaluations/EVAL-001-ace-step-listening-evaluation.md)을 완료한다.
6. Production 전 Pipeline 취소·복구·idempotency와 외부 Queue 요구사항을 정의한다.

## 다음 작업 흐름

```text
Phase 5.1: 실제 Audio Mixer 완료
  ↓
Phase 6: 로컬 Lyrics AI 기반 완료
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
