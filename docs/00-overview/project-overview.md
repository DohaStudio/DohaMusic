# 프로젝트 개요

> 문서 목적: DohaMusic의 문제 정의, 가치, 범위와 성공 방향을 설명한다.
> 현재 상태: **Responsive Studio MVP 구현 완료 / AI-native DAW 장기 제품 [계획]**
> 최종 수정일: 2026-08-20
> 관련 문서: [AI-native DAW 제품 방향](../02-product/ai-native-daw-product-direction.md), [DohaLM 연동](../03-architecture/dohalm-integration.md), [기능 요구사항](../02-requirements/functional-requirements.md), [생성 콘텐츠 정책](../09-security/generated-content-policy.md)

## 문제 정의

개인이 가사, 작곡, 가창, 믹싱을 모두 수행하기 어렵고 기존 생성 모델은 한국어 가창, 개인 GPU, 음성 권리 조건이 제각각이다. DohaMusic은 교체 가능한 사전학습 모델을 안전한 비동기 파이프라인으로 묶어 개인 창작 흐름을 단순화한다.

## 제품 가치

- 자연어와 가사에서 재현 가능한 음원을 만든다.
- AI가 만든 가사 초안을 사용자가 직접 편집·선택·배열·보완하고 승인하는 공동 창작 환경을 제공한다.
- 가사 생성·분석·수정부터 음악 생성까지 하나의 통합 제작 흐름으로 연결한다.
- 본인 또는 동의받은 음성을 창작 과정에 안전하게 활용한다.
- 모델·데이터 출처·생성 설정·가사 버전·사용자 수정·최종 승인과 오류를 추적할 수 있다.
- 상업 이용 검토를 통과한 모델과 비상업 연구 전용 모델을 분리한다.
- 8GB VRAM 환경에서 순차 실행과 오프로딩 가능성을 우선 검증한다.

장기 제품은 `AI-native DAW + Project/Composition Runtime + Provider Orchestrator + Composition Evaluation/QA + Continuous Learning Hub`다. 현재 Responsive Studio MVP와 장기 TARGET을 섞지 않으며, 편집 가능한 Timeline·Track·Clip·Mixer와 Composition QA·Learning Hub는 아직 구현되지 않았다.

## 현재 범위

기존 Template·Mock 기반 Lyrics AI와 음악 생성 Pipeline, 생성·가사·음성·이력·프로젝트·결과 중심 Responsive Studio는 구현돼 있다. DohaLM은 별도 저장소에서 관리되는 LLM 모델·추론 Provider이며, DohaMusic은 이를 호출하고 UI·가사 편집·버전·승인·음악 비즈니스 로직을 소유하는 Reference Application이다. DohaLM REST/SSE MVP는 구현됐지만 DohaMusic 제품 통합은 `[계획]`이다. 첫 제품 범위는 [MVP 범위](../02-requirements/mvp-scope.md), 장기 전환은 [Frontend 전환 계획](../../planning/ai-native-daw-frontend-migration.md)에 정의한다.

## 성공 판단

기존 MVP 성공은 동의된 개인 음성으로 한 곡을 비동기 생성하고, WAV 결과와 전체 생성 메타데이터를 회수하며, 실패 시 원인을 확인하고 안전하게 재시도할 수 있는지로 판단한다. DohaLM 가사 연동 확장은 다음 증거가 모두 있어야 성공으로 판단한다.

- DohaLM으로 가사 초안을 생성한다.
- 사용자가 초안을 직접 수정한다.
- 사용자 최종 승인본을 별도 버전으로 저장한다.
- 승인된 가사만 음악 생성 입력으로 사용한다.
- 사용 모델·버전·데이터 계보·상업 이용 검토 상태와 가사 수정 이력을 확인할 수 있다.

음질과 가사 품질 기준은 [평가 전략](../08-evaluation/evaluation-strategy.md)에서 검증 후 확정한다.
