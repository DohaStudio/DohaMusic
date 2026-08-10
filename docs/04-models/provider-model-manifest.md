# Provider Model Manifest 최소 계약

> 문서 상태: [승인]
> 최종 수정일: 2026-08-06
> 관련 기능: 외부 AI Provider 식별·호환성·권리·계보
> 관련 문서: [DohaStudio Model Manifest 공통 명세](https://github.com/DohaStudio/.github/blob/main/docs/specifications/06-model-manifest-specification.md), [책임 경계](../03-architecture/repository-provider-boundaries.md), [Dataset·Artifact 정책](../05-data/local-dataset-artifact-policy.md), [ADR-028](../11-decisions/ADR-028-provider-runtime-artifact-contract.md)

## 목적

DohaMusic이 Provider 내부 모델 구조나 로컬 경로를 알지 않고도 capability, 계약 호환성, 모델 계보와 상업 이용 상태를 검증할 수 있도록 최소 metadata를 정의한다. 공통 Model Registry는 아직 `[계획]`이며 이 문서는 Registry 구현을 의미하지 않는다.

## 최소 항목

| 필드 | 의미 |
|---|---|
| `provider_id` | `dohalm`, `dohaaudio`, `dohavocal` 같은 Provider 식별자 |
| `model_id` | Provider 내부에서 안정적인 모델 식별자 |
| `model_version` | 모델 release 버전 |
| `checkpoint_version` | Checkpoint 또는 Adapter version·식별자 |
| `model_type` | 생성·분석·변환 등 모델 유형 |
| `capabilities` | 지원 기능 목록 |
| `input_formats` | 지원 입력 MIME·schema·audio 규격 |
| `output_formats` | 지원 출력 MIME·schema·audio 규격 |
| `api_contract_version` | Provider API 계약 버전 |
| `dataset_manifest_id` | 학습 Dataset Manifest 식별자 |
| `training_run_id` | Training 또는 Fine-tuning Run 식별자 |
| `evaluation_result_id` | 승인 근거가 되는 평가 결과 식별자 |
| `license_status` | 코드·가중치·데이터 라이선스 검토 상태 |
| `commercial_usage_status` | 상업 이용 가능 상태 |
| `recommended_vram` | 검증된 권장 VRAM과 단위 |
| `runtime_environment` | Python·CUDA·핵심 runtime version 정보 |
| `artifact_checksum` | 모델 Artifact 무결성 checksum과 algorithm |
| `created_at` | Manifest 생성 시각 |

## 규칙

- Manifest에는 로컬 절대 경로, secret, 사용자 식별자와 원본 동의 증적을 저장하지 않는다.
- 미확인 값은 추측하지 않고 `verification_required` 또는 이에 대응하는 명시적 상태로 기록한다.
- `commercial_usage_status`가 `commercial_approved`가 아닌 모델은 상업 작업에서 fail closed한다.
- `capabilities`는 Provider가 실제로 검증한 기능만 포함한다. 현재 DohaVocal의 Singing Voice는 `[계획]`이므로 지원 capability로 선언할 수 없다.
- Checksum은 Artifact 전송 또는 로딩 전에 검증할 수 있어야 한다.
- Manifest 변경이 API 호환성이나 출력 의미를 바꾸면 version을 올리고 DohaMusic Provider Client 호환성을 검증한다.

## Workspace Job ModelUsage

Workspace `Job.model_manifest_id`는 요청된 Manifest이며 `ModelUsage`는 Provider가 확인한 실제 실행 결과다. Provider·model·version·checkpoint·contract version·license·commercial status는 completion Unit of Work에서 기록한다. Seed·adapter·inference config는 새 ModelUsage Column을 추측해 추가하지 않고 versioned allowlist를 사용하는 bounded `Job.settings_snapshot`에 저장한다. 비밀 prompt/context와 경로는 Manifest·ModelUsage·공개 Job 응답에 포함하지 않는다. 세부 실행 경계는 [Workspace Job Foundation](../03-architecture/workspace-job-foundation.md)을 따른다.

## 예시

다음은 schema 방향을 설명하기 위한 예시이며 현재 Provider release를 나타내지 않는다.

```json
{
  "provider_id": "dohaaudio",
  "model_id": "planned-music-generator",
  "model_version": "0.0.0-planned",
  "checkpoint_version": "not_available",
  "model_type": "music_generation",
  "capabilities": [],
  "input_formats": [],
  "output_formats": [],
  "api_contract_version": "draft-v1",
  "dataset_manifest_id": "not_available",
  "training_run_id": "not_available",
  "evaluation_result_id": "not_available",
  "license_status": "verification_required",
  "commercial_usage_status": "verification_required",
  "recommended_vram": "verification_required",
  "runtime_environment": "verification_required",
  "artifact_checksum": "not_available",
  "created_at": "2026-08-06T00:00:00Z"
}
```

정식 JSON Schema와 Registry 저장·조회 API는 Provider 계약 구현 단계에서 별도로 정의한다.
