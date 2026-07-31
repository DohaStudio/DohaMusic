# 프로젝트 개요

> 문서 목적: DohaMusic의 문제 정의, 가치, 범위와 성공 방향을 설명한다.
> 문서 상태: [운영 중]
> 최종 수정일: 2026-07-31
> 현재 상태: **Phase 6 완료 / Phase 6.6~6.9 Local Lyrics LLM 확장 계획**
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md), [Local Lyrics LLM 계획](../../planning/phase-6-local-lyrics-llm-plan.md), [ADR-016](../11-decisions/ADR-016-local-lyrics-llm-finetuning.md)

## 문제 정의

개인이 가사, 작곡, 가창, 믹싱을 모두 수행하기 어렵고 기존 생성 모델은 한국어 가창, 개인 GPU, 음성 권리 조건이 제각각이다. DohaMusic은 교체 가능한 사전학습 모델을 안전한 비동기 파이프라인으로 묶어 개인 창작 흐름을 단순화한다.

## 제품 가치

- 자연어와 가사에서 재현 가능한 음원을 만든다.
- 본인 또는 동의받은 음성을 창작 과정에 안전하게 활용한다.
- 모델과 데이터 출처, 설정, 오류를 추적할 수 있다.
- 8GB VRAM 환경에서 순차 실행과 오프로딩 가능성을 우선 검증한다.

## 현재 범위

Backend Foundation, 교체 가능한 AI Adapter, Stem·Voice 기술 경로, Pipeline, Audio Mixer와 Template·Mock 기반 Lyrics AI는 구현되어 있다. 로컬 Lyrics LLM은 후속 확장 계획이며 Dataset 구축·학습·Adapter 구현·품질 검증은 아직 수행하지 않았다. 첫 제품 범위는 [MVP 범위](../02-requirements/mvp-scope.md), 단계는 [로드맵](../../ROADMAP.md)에 정의한다.

로컬 Lyrics LLM은 직접 기반 구조를 설계하지 않고 공개 사전학습 Instruct LLM을 활용한다. Qwen 계열 1.7B~4B Instruct와 QLoRA SFT를 우선 검토하지만 후보 확정이나 채택을 의미하지 않는다. 검증 전에는 `template`을 기본 Provider로 유지하고 `local_llm`을 운영 Pipeline에 자동 연결하지 않는다.

## 성공 판단

MVP 성공은 동의된 개인 음성으로 한 곡을 비동기 생성하고, WAV 결과와 전체 생성 메타데이터를 회수하며, 실패 시 원인을 확인하고 안전하게 재시도할 수 있는지로 판단한다. 음질 기준은 [평가 전략](../08-evaluation/evaluation-strategy.md)에서 검증 후 확정한다.
