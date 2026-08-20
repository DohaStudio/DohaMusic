# 용어집

> 문서 목적: 문서 전반의 핵심 용어를 일관되게 사용한다.
> 현재 상태: **운영 중**
> 최종 수정일: 2026-08-20
> 관련 문서: [AI-native DAW 제품 방향](../02-product/ai-native-daw-product-direction.md), [Common AI Contract 소비자 기반](../03-architecture/common-ai-contract-consumer.md)

| 용어 | 정의 |
|---|---|
| 음악 생성 | 프롬프트·가사·설정으로 가창 포함 음원을 생성하는 단계 |
| Stem | 믹스에서 분리된 보컬, 드럼, 베이스 등 개별 음원 |
| 음색 변환(VC) | 원본 발화/가창 내용을 유지하며 목표 화자의 음색 특성을 적용하는 처리 |
| 참조 음성 | 사용자가 권리를 보유하거나 명시적 동의를 받은 입력 음성 |
| 음성 프로필 | 참조 음성, 동의 상태, 처리 상태를 묶은 사용자 단위 자원 |
| 작업(Job) | 장시간 AI 파이프라인을 추적하는 비동기 실행 단위 |
| 모델 어댑터 | 특정 모델 API를 공통 내부 인터페이스로 변환하는 경계 |
| Seed | 가능한 경우 생성 결과 재현에 쓰는 난수 초기값 |
| Provenance | 입력, 모델·버전, 설정, 변환 단계, 출력의 출처 기록 |
| CURRENT | 현재 `develop`의 코드·API·검증으로 확인된 구현 상태 |
| TARGET | 장기 제품 목표이며 구현 완료를 뜻하지 않는 상태 |
| CompositionSnapshot | 선택된 AssetVersion 조합과 설정을 가리키는 불변 재현 단위 |
| TimelineSelection | Track·Section·시간 범위의 사용자 선택을 나타내는 DohaMusic product/UI context 후보. 공통 schema가 아님 |
| MusicIntent | DohaLM이 해석하고 DohaMusic이 orchestration하며 Provider가 소비하는 공통 작업 의도 |
| CompositionEvaluationRun | CompositionSnapshot 완성곡 QA 실행을 가리키는 DohaMusic product-domain object 후보. 공통 schema 미확정 |
| EvaluationRun | TrainingRun 산출물의 checkpoint/model을 평가하는 공통 계약. 완성곡 QA 용도가 아님 |
| SimilarityReport | 생성 결과와 승인 Reference Feature의 유사도를 설명하는 창작 지원 분석. 법적 표절 판정이 아님 |
| RevisionPlan | Similarity 또는 Music QA 결과를 실행 가능한 수정 단계로 바꾸는 공통 계획 |
| LearningCandidate | 사용자 작업·AI 결과·수정·선택을 학습 검토 대상으로 등록한 객체. Dataset 포함이나 학습 허용을 뜻하지 않음 |
| FeatureRecord | Reference Audio 원본과 분리된 versioned 분석 결과 |

상태 값은 [작업 상태 모델](../07-database/job-state-model.md)을 기준으로 한다.
