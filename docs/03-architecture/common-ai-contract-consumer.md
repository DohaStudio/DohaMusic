# Common AI Contract 소비자 기반

> 문서 상태: [구현]
> 최종 수정일: 2026-08-20
> 적용 범위: opt-in loader와 RightsMetadata 검증 adapter

## 기준선과 설치

DohaMusic은 `DohaStudio/.github`의 Common AI Contract Schema v1 Python 배포물
`dohastudio-common-ai-contracts`를 소비한다. 의존성은 `develop`에 병합된 commit
`dd75fc88c16e9ae9a04acfafb72756a905f6365b`에 직접 고정한다. branch, tag, registry
release, local wheel, 로컬 schema 사본은 설치 fallback이나 실행 기준으로 사용하지 않는다.

- 배포물 버전: `0.1.0`
- 실행 정책 버전: `1.0.0`
- Python 범위: `>=3.11,<3.13`
- canonical namespace: `dohastudio_common_ai`
- canonical schema: package resource 12개, policy를 포함한 JSON resource 13개

Git과 network는 해당 VCS 의존성을 설치할 때만 필요하다. 설치 후 schema 조회와 검증은
package resource만 사용하며 network나 `.github` working tree에 접근하지 않는다. 이 저장소는
Python lock file을 관리하지 않으므로 별도 lock entry는 만들지 않는다.

기존 Workspace 문서가 인용하는 Common Specification `0.1.0 / draft-baseline`은 과거부터 유지한
비실행 설계 참고 문서다. 이 Python package의 distribution version, 실행 정책 version 또는
Registry resource를 뜻하지 않으며 두 번째 실행 source of truth로 사용하지 않는다.

## 코드 경계

`backend.contracts.common_ai`는 package public API만 사용하는 얇은 opt-in 경계다.

- `common_ai_contract_status()`는 package·policy version과 소비 대상 `rights_metadata`의 공식
  `$id`를 확인하고 불일치 시 fail-closed 한다.
- `load_common_ai_schema()`는 public `get_schema()`를 통해 canonical schema를 읽는다.
- `validate_common_ai_contract()`는 canonical `ValidationIssue` tuple을 수정하지 않고 반환한다.
- `validate_rights_metadata()`는 `expected_kind="rights_metadata"`만 고정하며 field를 추가·변환하지
  않는다.

모듈 import는 package 조회, 파일 생성, network 요청을 수행하지 않는다. 호출 시 package가
없거나 공개 API·버전·소비 대상 resource identity가 다르면 내부 경로와 stack trace를 포함하지
않는 고정 오류로 중단한다. 전체 Registry·resource identity 목록은 로컬에 복제하거나 compatibility
policy로 관리하지 않는다. 현재 Router, Service, Job, Provider, DB, Migration, 실제 사용자
데이터에는 연결하지 않았다.

## 계약 선택과 기존 도메인

이번 기반에서 실제로 선택한 공통 객체는 `rights_metadata` 하나다. DohaMusic의 Asset,
AssetVersion, Artifact, CompositionSnapshot, Job에는 현재 공통 Registry와 일대일인 schema가
없으므로 이름이 비슷하다는 이유로 adapter를 만들지 않는다. ProviderCapability, MusicIntent,
ModelVersion, ModelManifest도 향후 실제 실행 경계를 설계할 때 별도 PR에서 선택한다.

| 항목 | 결정 |
|---|---|
| Registry resource | `rights-metadata.schema.json` / `rights_metadata` |
| 공식 `$id` | `https://schemas.dohastudio.org/common-ai/v1/rights-metadata.schema.json` |
| object version | package policy가 허용하는 `1.x.y` |
| 소비 위치 | `backend.contracts.common_ai.validate_rights_metadata()` |
| 현재 사용 | 호출자가 완성 payload를 명시적으로 전달할 때만 사용 |
| 이번 검증 | resource 조회, version, schema, canonical issue, offline 동작 |
| 후속 범위 | 실제 DTO 매핑, consent/provenance governance, DB·Runtime 연결 |

공통 Registry에는 독립 `Provenance` 또는 `Consent` schema가 없다. 또한 현재 Voice Enrollment의
`consent_confirmed`와 정책 snapshot만으로는 RightsMetadata의 권리 검토자, 관할, source flag,
허용 범위, consent evidence를 완전하게 증명할 수 없다. 따라서 이 adapter는 완성된 canonical
RightsMetadata payload만 검증하며 다음을 하지 않는다.

- Voice consent boolean을 Common RightsMetadata로 승격
- Asset·Artifact·Job 식별자를 공통 object ID로 추정
- 누락된 evidence, provenance, review, jurisdiction field 생성
- 검증 성공을 runtime 실행 또는 학습 허가로 해석

Consent record, provenance 관계, 영속화와 governance workflow는 별도 DB·정책 작업이다. 그 전까지
기존 Voice consent 정책은 DohaMusic 로컬 도메인 계약으로 유지되며 Common Contract와 동일하다고
간주하지 않는다.

## 사용 예

```python
from backend.contracts.common_ai import validate_rights_metadata

issues = validate_rights_metadata(payload)
if issues:
    # 호출자가 canonical issue code/path/rule을 기준으로 명시적으로 처리한다.
    ...
```

이 함수 호출은 opt-in이다. 애플리케이션 시작, 기존 endpoint, worker 또는 provider 실행 흐름에는
자동으로 삽입되지 않는다.

## Rollback과 후속 작업

Rollback이 필요하면 dependency 선언, loader/adapter, 테스트와 이 문서를 한 개의 새 revert PR로
함께 되돌린다. `reset`, force push, `develop`·`main` 직접 수정은 사용하지 않는다.

후속 PR은 실제 RightsMetadata DTO와 consent/provenance governance·영속화 기준을 먼저 확정한 뒤
opt-in 호출자를 연결한다. ProviderCapability·MusicIntent·ModelVersion·ModelManifest와 Runtime,
Dataset governance, LearningCandidate, DatasetVersion, Training Readiness Gate는 각각의 소유
저장소와 승인 절차가 준비되기 전까지 연결하지 않는다.

## 제품 목표의 공통 객체 재사용 — TARGET

[AI-native DAW 제품 방향](../02-product/ai-native-daw-product-direction.md)은 같은 authority의 `MusicIntent`, `RevisionPlan`, `SimilarityReport`, `ReferenceAnalysis`, `FeatureRecord`, `LearningCandidate`, `RightsMetadata`, `TrainingEligibility`, `DatasetVersion`, `TrainingRun`, `EvaluationRun` 정의를 우선 재사용한다. 이는 현재 Python adapter나 Runtime 연결 범위를 넓힌다는 뜻이 아니다. Python package의 실행 schema와 authority의 제안 Specification도 구분한다.

- AI 편집 의도용 신규 공통 `EditIntent`를 만들지 않는다.
- `MusicIntent.target`의 `project_id`, `asset_version_id`, `track_id`, `section_id`, `time_range`를 우선 사용한다.
- `clip_id`, `bar_range`, `beat_range`는 실제 DAW 구현에서 필요성이 입증될 때만 Common Contract 최소 확장을 검토한다.
- 완성곡 QA는 기존 Training용 `EvaluationRun`의 의미를 변경하지 않는다.
- `CompositionEvaluationRun`과 `TimelineSelection`은 DohaMusic product-domain 후보이며 Common Contract schema로 확정하지 않는다.
