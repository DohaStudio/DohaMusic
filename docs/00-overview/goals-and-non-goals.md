# 목표와 비목표

> 문서 목적: 범위 확장을 통제하고 의사결정 기준을 제공한다.
> 현재 상태: **CURRENT MVP와 TARGET 제품 범위 구분**
> 최종 수정일: 2026-08-20
> 관련 문서: [AI-native DAW 제품 방향](../02-product/ai-native-daw-product-direction.md), [Frontend 전환 계획](../../planning/ai-native-daw-frontend-migration.md)

## 목표

- 공개 사전학습 모델을 어댑터로 통합한다.
- 프롬프트 또는 직접 작성 가사로 노래를 생성한다.
- 보컬 분리, 동의된 음색 변환, 믹싱과 파일 출력을 자동화한다.
- 작업 상태와 모델·Seed·설정·산출물을 추적한다.
- RTX 3060 Ti 8GB를 우선 검증 환경으로 삼는다.
- 장기적으로 Timeline 기반 AI-native DAW, Composition Runtime, Provider Orchestrator, Composition QA와 검토 가능한 Continuous Learning Hub를 구축한다.

## 비목표

- 기반 음악 생성 모델의 최초 자체 사전학습
- 실시간 라이브 가창, 대규모 다중 사용자 운영, 결제
- 현재 MVP 범위의 전문 DAW 수준 편집, 모바일 네이티브 앱, 자동 회원 소통
- 타인 음성의 무단 복제나 사칭 지원

편집 가능한 Timeline·Track·Clip·Mixer는 현재 MVP 비목표였지만 장기 TARGET에 포함된다. 상용 전문 DAW 전체 기능 parity를 무제한 목표로 삼는 것은 아니며, DohaMusic의 AI 공동 창작·불변 Version·평가 기반 수정에 필요한 범위를 단계별로 검증한다.

범위 변경은 [ADR 절차](../11-decisions/README.md)와 [백로그](../../planning/backlog.md)에 기록한다.
