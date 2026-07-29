# ADR-012 — Pipeline Orchestrator

> 상태: 승인
> 작성일: 2026-07-29
> 최종 수정일: 2026-07-29
> 관련 문서: [Pipeline Orchestrator](../03-architecture/pipeline-orchestrator.md), [ADR-011](ADR-011-voice-provider-selection.md)

## 배경과 문제

Music, Stem, Voice는 독립 Job과 Adapter로 검증됐지만 단일 Workflow가 없었다. Voice Primary는 미선정이므로 운영 Provider 통합은 허용할 수 없지만, 새 사용자 지시에 따라 Mock Voice로 오케스트레이션 경계와 실패 처리를 먼저 검증할 필요가 있다.

## 결정

1. `PipelineService → PipelineWorker → PipelineExecutor → PipelineStep` 구조를 채택한다.
2. 단계 순서는 Music → Stem → Voice → Mock Mixer → WAV Export로 고정한다.
3. AI 단계는 기존 인터페이스만 의존하고 애플리케이션 조립부에서 Provider를 주입한다.
4. Voice 기본값은 `mock`이며 Primary 미선정 결정을 변경하지 않는다.
5. 단계별 자동 재시도는 기본 1회로 제한하고 Validation·Output 오류는 재시도하지 않는다.
6. 단계 진행률은 20·40·60·80·100으로 저장한다.
7. 성공·실패 metadata와 단계 benchmark를 JSON 및 DB에 보존한다.
8. 실패한 작업의 부분 오디오는 제거하고 진단 metadata만 남긴다.
9. 상태 계약에 `CANCELLED`를 추가하되 취소 API는 후속 작업으로 둔다.

## 선택 이유

기존 Adapter와 공유 ThreadPool을 재사용하면서 특정 AI 구현이 Workflow로 누출되지 않는다. 독립 Job API도 유지하므로 회귀 범위가 작고, 향후 외부 Queue나 실제 Mixer로 교체할 경계가 명확하다.

## 대안

- 기존 Service API를 내부 HTTP로 연쇄: 불필요한 네트워크·중복 Job과 복잡한 실패 보상 때문에 제외했다.
- Redis/Celery Workflow: 이번 범위에서 금지됐고 운영 요구도 확정되지 않아 제외했다.
- Seed-VC를 기본 Voice로 연결: ADR-011 품질·라이선스 게이트를 통과하지 않아 제외했다.

## 영향과 한계

- `pipeline_jobs`, `pipeline_files`, migration 0004가 추가된다.
- Mock Mixer 결과는 음악적 믹싱 품질을 의미하지 않는다.
- timeout은 완료 후 제한 초과를 판정하며 실제 subprocess 종료는 Adapter timeout에 의존한다.
- 인증, 소유권, 외부 Queue, 강제 취소와 crash recovery는 미구현이다.

## 재검토 조건

Primary Voice 승인, 실제 Mixer 도입, 외부 Queue 선정, 취소·재개 요구 또는 단계 순서 변경 시 재검토한다.

## 관련 PR

Phase 5 작업 PR에 연결한다.
