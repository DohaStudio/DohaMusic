# ADR-023: Audio Analysis와 Preview 아키텍처

> 상태: [승인]
> 작성일: 2026-07-31
> 최종 수정일: 2026-07-31
> 관련 기능: K3 Audio Analysis·Preview
> 관련 문서: [제품 정의](../02-product/k3-audio-analysis-product-definition.md), [결과 계약](../03-architecture/audio-analysis-result-contract.md), [실패 정책](../03-architecture/audio-analysis-failure-policy.md), [EVAL-008](../../reports/evaluations/EVAL-008-audio-analysis-validation.md)

## Context

K2는 requested BPM·Hook·Post-Chorus·Dance Break를 Prompt 목표로 저장하지만 실제 WAV의 품질·tempo·구조 준수를 분석하지 않는다. 현재 Mixer는 Sample Peak·RMS·clipping 일부를 기록하고 True Peak를 미지원으로 명시한다. Pipeline은 `final.wav` export 뒤 Job과 파일을 한 번에 완료하며 secure content/download는 공개 WAV allowlist와 경로 검증을 사용한다.

Tempo·Hook·Chorus는 오탐·미탐이 가능하고 loudness·True Peak도 표준 구현과 reference 검증이 필요하다. 분석 실패가 유효한 완성곡을 제거하거나 음악 생성 실패로 보이면 안 된다.

## Decision

1. 최종 믹스 `final.wav`를 K3 MVP의 유일한 기본 분석 source로 한다.
2. 최종 WAV export 성공을 Pipeline 성공 경계로 두고 Audio Analysis와 Preview를 비차단 후처리로 실행한다.
3. Pipeline status와 별도로 versioned `analysis_status`, Preview status, warning과 confidence를 기록한다.
4. K3 MVP 분석 상세는 기존 `result_metadata`·`metadata.json`의 `audio_analysis` JSON에 저장하고 Preview는 기존 `pipeline_files`와 secure content/download 경계를 재사용한다. Migration은 하지 않는다.
5. 공개 API는 nested allowlist projection만 제공하고 path·command·stack·raw debug를 숨긴다.
6. Tempo·Hook·Chorus는 추정값으로 표시하고 confidence `0.0~1.0`과 provisional 등급을 함께 제공한다.
7. Preview는 신뢰 가능한 Hook 후보 또는 deterministic 중앙 fallback에서 15초 WAV를 만들고 짧은 fade를 적용한다.
8. Pipeline Retry는 새 음악과 새 분석을 만들며 결과를 복사하지 않는다. 동일 WAV Re-analysis와 history는 후속 단계다.
9. analyzer·library는 EVAL-008, Windows/Python 호환, 성능과 라이선스 Gate를 통과한 뒤 채택한다.

## 선택 이유

Provider-neutral 후처리는 생성 모델 교체와 분석 알고리즘 변경을 분리한다. 비차단 정책은 분석 장애로부터 유효 WAV를 보호한다. 기존 JSON·file inventory·secure endpoint를 활용하면 구형 Result 호환과 rollback을 유지하면서 K3 MVP를 작게 시작할 수 있다.

## 대안

- Provider 결과만 신뢰: Provider 간 계약이 다르고 실제 final mix를 검증하지 못해 기각한다.
- Frontend에서 분석: 전체 WAV 전송·성능·알고리즘 version·결과 일관성과 보안 경계가 약해 기각한다.
- 모든 분석 실패를 Job 실패 처리: 유효 WAV를 잃고 실패 의미가 섞여 기각한다.
- 외부 SaaS 분석 API: 비용·데이터 반출·가용성·Provider 종속 때문에 MVP에서 제외한다.
- 즉시 ML Hook 모델 도입: Dataset·권리·정확도·배포 비용 근거가 없어 보류한다.
- 별도 Analysis table 즉시 도입: 검색·history 장점은 있으나 K3 MVP에 Migration과 복잡도를 먼저 만들므로 보류한다.

## Consequences

### 장점

- 유효 Result의 재생·다운로드를 분석 장애와 분리한다.
- 분석 version과 confidence로 추정값의 한계를 표현할 수 있다.
- 기존 Pipeline·Storage·secure access를 재사용하고 Provider 종속을 만들지 않는다.
- 단계별 K3.1~K3.4 구현과 rollback이 가능하다.

### 비용과 위험

- Pipeline 상태 외 별도 후처리 상태와 partial UX가 필요하다.
- 알고리즘 version·re-analysis·cleanup 정책을 유지해야 한다.
- Preview 저장 공간과 분석 CPU 시간이 추가된다.
- JSON 저장은 검색·통계·history에 불리하며 요구가 생기면 schema 전환이 필요하다.
- confidence calibration이 부정확하면 사용자 신뢰를 해칠 수 있다.

## Rollback

Audio Analysis와 Preview dispatcher를 비활성화하고 신규 Result에서 분석을 `not_requested`로 처리한다. 기존 `audio_analysis` JSON과 Preview 파일은 읽기 호환을 유지하며 최종 WAV·History·Project·secure content/download는 계속 제공한다. Provider, Mixer와 K2 Generation Options는 변경하지 않는다.

## 재검토 조건

- 분석값 검색·정렬·통계 또는 복수 version history가 제품 요구가 됨
- 동일 WAV 수동 Re-analysis API가 필요함
- JSON 크기·동시 update·atomicity가 문제가 됨
- 외부 공개 운영에서 인증·소유권·retention 요구가 강화됨
- EVAL-008이 후보 알고리즘의 정확도·성능·라이선스를 승인하지 못함

