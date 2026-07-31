# ADR-022: K-POP Generation Control Layer

> 상태: [승인]
> 작성일: 2026-07-31
> 최종 수정일: 2026-07-31
> 관련 기능: K-POP Preset·Generation Options·Prompt Compiler
> 관련 문서: [제품 정의](../02-product/kpop-creation-product-definition.md), [Generation Options](../03-architecture/kpop-generation-options.md), [Roadmap](../../planning/kpop-creation-roadmap.md)

## Context

현재 Pipeline은 Provider-neutral이지만 K-POP 제품 옵션 계약과 Frontend 선택값을 Prompt로 결합하는 단일 기준이 없다. Provider가 직접 지원하는 값, Prompt 기반 제어, 미검증·미지원 기능을 구분하지 않으면 UI가 실제보다 강한 제어를 약속할 위험이 있다.

## Decision

1. K-POP Preset과 `KPopGenerationOptions`를 Provider-neutral 제어 계층으로 둔다.
2. `KPopPromptCompiler`가 Preset·옵션·사용자 Prompt를 자연어 Prompt로 변환한다.
3. Provider Capability Matrix로 직접 지원·Prompt 기반·Metadata-only·미지원을 공개한다.
4. 기존 Pipeline 필드를 유지하고 `generation_options`는 향후 optional 확장으로 도입한다.
5. Snapshot에 원본·정규화 옵션, 최종 Prompt, warning, compiler version을 보존한다.
6. Frontend는 capability를 기준으로 옵션을 노출하며 미지원 값을 실제 제어처럼 표시하지 않는다.
7. 평가와 권리 Gate 통과 전 운영 Provider나 Style 모델로 승격하지 않는다.

## 포함 범위

Preset, Options, Compiler, Capability, Snapshot, Frontend 계약, 평가 기준, Dataset 권리 정책을 포함한다.

## 제외 범위

모델 학습, BPM 검출, Hook 추출, 긴 곡, Production 승인, API·DB·Frontend 구현은 이번 결정의 구현 범위가 아니다.

## 선택 이유

Provider 교체 가능성을 유지하면서 제품 언어를 일관되게 만들고, Prompt 기반 제어를 실제 모델 파라미터처럼 과장하지 않기 위해서다. 검증·Snapshot·Preview 경계를 하나로 모으면 재현성과 평가 가능성도 높아진다.

## 대안

- Frontend에서 Prompt 직접 조합: 빠르지만 중복·우회·버전 추적 문제가 있어 기각한다.
- Provider별 옵션 직접 노출: Provider 종속과 API 파편화 때문에 기각한다.
- 즉시 Style LoRA: 권리·Dataset·평가 근거가 없어 보류한다.
- 모든 옵션을 자유 JSON으로 저장: 검증과 호환성·보안 경계가 약해 기각한다.

## 장점과 단점

장점은 계약 일관성, Provider 교체성, capability 기반 UX, 재현 가능한 Snapshot이다. 단점은 Compiler 버전 관리와 Prompt 기반 옵션의 제한, 구현 단계 증가다.

## 권리와 데이터

유명 아티스트·상업 음원·가사를 무단 학습하거나 모방하지 않는다. Music Style, 개인 Voice, Lyrics Dataset은 분리하고 각 데이터의 출처·라이선스·동의·상업 이용 범위를 기록한다.

## Rollback

`generation_options`는 optional로 도입하고 기존 `prompt`·`lyrics`·`genre`·`duration_seconds`·`seed` 계약을 유지한다. 문제가 생기면 Compiler와 옵션 UI를 비활성화해 기존 Pipeline 요청으로 복귀한다.

## 재검토 조건

Provider가 구조화된 BPM·Hook·구조 파라미터를 공식 지원하거나, capability 계약이 Provider별로 크게 달라지거나, EVAL-007이 Prompt Compiler의 실효성을 부정하면 재검토한다.
