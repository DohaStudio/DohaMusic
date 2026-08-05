# ADR-027 — DohaLM 가사 Provider와 사용자 승인 경계

> 상태: [제안]
> 작성일: 2026-08-05
> 최종 수정일: 2026-08-05
> 관련 기능: Phase 6.5 External Lyrics LLM 확장
> 관련 문서: [DohaLM 연동](../03-architecture/dohalm-integration.md), [Lyrics AI](../03-architecture/lyrics-ai.md), [가사 버전 데이터 모델](../07-database/lyrics-versioning-data-model.md), [라이선스 검토](../01-research/licensing-review.md)
> 관련 PR: [PR #48](https://github.com/DohaStudio/DohaMusic/pull/48)

## 배경

DohaLM은 별도 저장소에서 모델·추론 Runtime·REST/SSE와 향후 SDK·versioned release를 관리하고, DohaMusic은 첫 외부 Reference Application으로 계획돼 있다. DohaMusic은 이미 `LyricsGenerator`와 Template·Mock·OpenAI Provider, 원본 보존 Revision을 가진다.

## 문제

DohaLM 연동이 모델 내부 구조를 DohaMusic에 누출하거나 기존 Provider 경계를 우회하면 두 저장소가 강하게 결합된다. 또한 AI 초안을 사용자 승인 없이 음악에 사용하거나 연구 전용 모델을 상업 작업에 사용하면 제품·권리 정책을 위반한다.

## 결정

DohaLM을 기존 `LyricsGenerator` 아래의 별도 `DohaLMLyricsAdapter` 후보로 격리한다. DohaMusic은 versioned REST/Streaming API를 우선 검토하고 Python SDK는 공식 surface가 완성된 뒤 대안으로 평가한다. 전용 Lyrics endpoint·SDK·manifest schema는 공식 계약 확정 전까지 구현된 것으로 간주하지 않는다.

DohaMusic이 가사 편집·불변 버전·사용자 최종 승인과 상업 이용 상태를 소유한다. 오직 `final_approved` 가사와 유효한 승인 snapshot만 Pipeline Orchestrator에 전달하며, 상업 작업은 `commercial_approved` model lineage만 허용한다. DohaLM 장애나 승인 실패 시 사용자가 직접 가사를 작성하는 경로를 유지한다.

## 선택 이유

- DohaLM과 DohaMusic의 저장소·책임 경계를 유지한다.
- 기존 Provider-neutral Service·Validator를 재사용한다.
- AI 결과, 사용자 기여와 승인 이력을 분리해 추적할 수 있다.
- 연구용 모델이 상업 작업으로 유입되는 경로를 fail closed한다.
- 아직 없는 API·SDK를 추측 구현하지 않는다.

## 대안

1. DohaLM 모델을 DohaMusic process에서 직접 로드: checkpoint·dependency·GPU lifecycle 결합 때문에 선택하지 않는다.
2. 현재 일반 Chat API를 고정 Lyrics 계약으로 사용: 전용 schema·manifest·호환성이 없어 보류한다.
3. AI 생성 즉시 Pipeline 전달: 사용자 승인·권리·품질 게이트를 우회하므로 선택하지 않는다.
4. DohaLM 장애 시 자동으로 연구용 모델 전환: 상업 상태와 provenance가 바뀌므로 금지한다.

## 장점과 단점

장점은 교체 가능성, 명시적 provenance·승인, 직접 작성 fallback과 상업 이용 차단이다. 단점은 추가 Adapter·버전·승인 데이터 모델, 비동기 Job·SSE 상태 관리와 두 저장소의 호환 version 운영이 필요하다는 점이다.

## 영향

README·요구사항·시스템 아키텍처·생성 콘텐츠·라이선스·데이터 모델 문서에 계획 경계가 추가된다. 현재 코드·API·DB·기본 `template` Provider·Phase 6 완료 상태와 Pipeline 입력은 변경하지 않는다.

## 마이그레이션

1. DohaLM이 전용 Lyrics 또는 승인된 범용 계약과 versioned manifest를 제공한다.
2. `DohaLMLyricsAdapter`와 비동기 생성·분석 Job 계약을 설계한다.
3. 가사 Project·Version·Generation·Analysis·Approval·ModelUsage·LicenseReview migration을 승인한다.
4. 기존 `lyrics_documents`를 보존하며 backfill·downgrade·소유권 정책을 검증한다.
5. 사용자 편집·재승인과 Pipeline snapshot을 자동·사용자 평가한다.
6. 상업용 release의 전체 계보가 `commercial_approved`일 때만 production 후보로 승격한다.

## 재검토 조건

- DohaLM Lyrics API·Python SDK·manifest가 공식 확정될 때
- DohaLM model·weights·dataset·Adapter lineage가 변경될 때
- 호출이 5초를 넘거나 streaming·취소·재시도 계약이 변경될 때
- 가사 versioning·approval 또는 Pipeline 입력 API가 확정될 때
- 법률·유사성·상업 이용 정책이 변경될 때
