# DohaVocal Consumer Contract Foundation

> 문서 역할: Provider Boundary와 System Architecture를 보충하는 SUPPORTING 계약
> 문서 상태: [구현·검증 완료, Draft PR 병합 전]
> 최종 수정일: 2026-08-20
> 적용 범위: DohaVocal Runtime `0.1.0` DTO·mapping·transport port·HTTP transport·Mock HTTP contract test
> 관련 문서: [Provider API 계약](../06-api/provider-api-contract.md), [Workspace Job Foundation](workspace-job-foundation.md), [저장소와 Provider 경계](repository-provider-boundaries.md), [ADR-034](../11-decisions/ADR-034-dohavocal-consumer-contract.md)

## 1. 기준선과 권위

Consumer는 다음 순서로 계약을 해석한다.

1. `DohaStudio/.github` `origin/main` `1e4b480c8cbd6e51835f8550e685e9b136d8071d`
2. `DohaStudio/DohaVocal` `origin/develop` `59de6c7b50f2e1d28a04f13ad649bf99f5737ec2`
3. DohaMusic 내부 consumer DTO와 mapping

DohaVocal source package를 import하거나 DB·in-memory store에 접근하지 않는다. JSON response와 transport port만 계약으로 사용한다. `.github`, DohaVocal, DohaAudio와 DohaLM 저장소는 이 작업에서 변경하지 않는다.

## 2. 구조와 구현 Surface

```text
DohaMusic authorized application context
  → map_authorized_create_job
  → VocalProviderClient
  → VocalProviderTransport
  → HttpVocalProviderTransport
  → DohaVocal HTTP wire contract
```

`HttpVocalProviderTransport`는 기존 동기 port를 바꾸지 않고 이미 의존 중인 `httpx.Client`를 재사용한다. transport가 client를 만들면 `close()` 또는 context manager가 종료하고, 외부에서 주입한 client의 수명은 호출자가 소유한다. 요청별 client 생성이나 자동 retry는 없다.

`VocalProviderClient`는 다음 9개 의미 operation을 표현한다.

| Consumer method | Provider operation | Path |
|---|---|---|
| `get_capabilities` | `GetCapabilities` | `GET /v1/capabilities` |
| `create_job` | `CreateJob` | `POST /v1/jobs` |
| `get_job_status` | `GetJobStatus` | `GET /v1/jobs/{job_id}` |
| `cancel_job` | `CancelJob` | `POST /v1/jobs/{job_id}/cancel` |
| `retry_job` | `RetryJob` | `POST /v1/jobs/{job_id}/retry` |
| `get_result` | `GetResult` | `GET /v1/jobs/{job_id}/result` |
| `get_model_manifest` | `GetModelManifest` | `GET /v1/model-manifests/{id}` |
| `health` | `Health` | `GET /health` |
| `readiness` | `Readiness` | `GET /ready` |

지원 capability는 `vocal_generation`, `voice_conversion`, `vocal_correction`, `vocal_analysis` 네 개다. 알 수 없는 capability, operation 차이, extra field와 `api_contract_version != 0.1.0`은 fail-closed 한다.

## 3. CreateJob과 권한 Scope

`AuthorizedVocalJobContext`는 DohaMusic Service가 effective Owner·Workspace·Project와 입력 AssetVersion·Artifact 접근 권한을 이미 해소했다는 내부 입력이다. mapping은 `effective_owner_id`만 `requested_by`로 사용하며 별도 caller `owner_id`를 받지 않는다. `workspace_id`는 권한 context에 남지만 공통 Provider request field가 아니므로 전송하지 않는다.

Provider request에는 `provider_id`, capability, contract version, idempotency key, Project, 입력 Version·Artifact ID, Model Manifest, 분리된 settings snapshot, effective requester와 capability별 `job_input`만 포함한다. 로컬 경로, credential, token, DB object와 Consent evidence 원문은 전달하지 않는다.

DohaVocal `0.1.0` 실제 schema는 body의 `idempotency_key`를 요구한다. 공통 명세는 transport 위치를 강제하지 않으므로 현재 adapter는 body 계약을 따른다. 기존 범용 Provider 문서의 header-only 목표는 DohaVocal 계약과 합의된 새 major/minor version 전까지 적용하지 않는다.

멱등성 scope는 `provider_id + capability + project_id + requested_by + idempotency_key`다. 같은 scope·fingerprint는 같은 Provider `job_id`, 같은 scope의 변경 요청은 conflict, 다른 Project·capability·requester는 별도 scope로 해석한다. DohaMusic Workspace Job 멱등성과 Provider 멱등성을 새 체계로 중복 구현하지 않는다.

## 4. Job·Retry·설정 Snapshot

Provider 상태 `queued`, `running`, `succeeded`, `failed`, `cancelled`를 이름과 의미 변경 없이 보존한다. terminal 상태를 consumer가 성공이나 실행 중으로 바꾸지 않는다. `failed`에는 구조화 error, `succeeded`에는 output ID, 모든 terminal 응답에는 `completed_at`이 필요하다.

Retry는 기존 Job을 초기화하지 않는다. 새 `job_id`와 `retry_of_job_id=기존 provider job_id`를 검증한다. caller-owned 중첩 dict/list는 request 생성 시 deep copy하여 이후 변경이 이미 생성된 settings snapshot을 바꾸지 못하게 한다.

## 5. Artifact 후보와 계보

현재 DohaVocal Fake Runtime 결과는 실제 audio payload가 아닌 `VocalProviderResultCandidate`다. `output_asset_version_id`가 있어도 DohaMusic DB에 AssetVersion이 생성됐다는 뜻이 아니다. AssetVersion·Artifact 등록과 선택 authority는 계속 DohaMusic에 있고 실제 commit은 후속 Artifact Catalog/Resolver 통합 범위다.

Consumer는 다음 값을 손실 없이 보존한다.

- 최초 원본 `source_asset_version_id`
- 직전 파생본 `parent_asset_version_id`
- `processing_chain_id`
- Provider·Model Manifest·settings·processing type·Provider Job ID
- `source_artifact_id`, `parent_artifact_id`

`artifact_checksum`과 lineage `checksum`은 `checksum_scope=metadata_descriptor`인 metadata descriptor SHA-256이다. `payload_present=false`이므로 audio integrity 검증 또는 실제 파일 checksum으로 승격하지 않는다.

## 6. Model Manifest와 Consent 경계

`REVIEW_REQUIRED`는 그대로 유지하고 `APPROVED`로 변환하지 않는다. `recommended_vram=null`을 임의 수치로 채우지 않으며 `artifact_checksum_scope=fake_manifest_descriptor`를 실제 model/checkpoint payload checksum으로 해석하지 않는다.

DohaMusic은 Consent와 owner authorization authority다. Consumer는 승인 없음을 승인으로 만들지 않고 Recording Take·Voice Enrollment Sample을 Vocal Training Dataset으로 변환하지 않는다. 이번 작업의 개인 음성, Recording, Dataset, Consent evidence와 audio payload 접근은 모두 0건이다.

## 7. 오류·Transport·보안

오류는 다음 범주를 구분한다.

- Provider application error
- transport error
- timeout
- invalid response
- contract version mismatch

Application error는 허용된 `error_code`, 안전한 message, `retryable`, `stage`, opaque `details_id`만 projection한다. raw body, exception, stack trace, PID, command, 절대 경로와 token은 보존하거나 사용자에게 반사하지 않는다. 의심되는 message와 details ID는 안전한 고정값으로 대체한다. 자동 retry policy, 무한 retry와 Provider fallback은 구현하지 않는다.

Provider endpoint는 `DOHAVOCAL_BASE_URL` 설정만 권위로 사용한다. `http`와 `https`만 허용하고 userinfo·query·fragment 및 `file`, `ftp`, `data`, `javascript` scheme은 거부한다. caller request·Project 입력·settings snapshot은 host나 base URL을 덮어쓸 수 없다. `job_id`와 `model_manifest_id`는 단일 URL path segment로 encode한다. 별도 network allowlist와 인증 protocol은 아직 확정하지 않았다.

connect·read·write·pool timeout은 각각 설정 가능하고 무한 timeout을 사용하지 않는다. JSON endpoint 응답은 `application/json` 또는 `+json` Content-Type과 유효한 JSON을 모두 요구한다. connection failure, timeout, application error, invalid response와 contract version mismatch를 구분하며 mutation을 포함한 모든 operation의 transport 자동 재시도는 비활성이다.

`health`는 process 생존, `readiness`는 새 Job 수락 가능 상태로 별도 DTO와 operation을 사용한다. Health 성공만으로 dispatch 가능하다고 판단하지 않는다.

## 8. 검증과 미구현

`backend/tests/fixtures/vocal-provider-contract-v0.1.0.json`은 DohaVocal source를 import하지 않는 stable JSON fixture다. canonical Provider ID는 `dohavocal`, 실제 Fake Model Manifest ID는 `dohavocal.fake-model@0.1.0`으로 고정해 Runtime wire identity와 일치시킨다. Fake transport와 `httpx.MockTransport`로 4 capability, 9 operation, request·state·retry·idempotency·snapshot·lineage·checksum·Manifest·오류·probe·timeout·URL 경계를 검증한다. 실제 network 호출은 0건이다.

이번 Foundation에 포함하지 않은 항목은 다음과 같다.

- 실제 HTTP 또는 localhost 호출
- 실제 DohaVocal process·Provider·AI model·GPU 호출
- Workspace Worker dispatcher 조립과 polling policy
- Artifact payload·Catalog·Resolver·AssetVersion commit
- DB Entity·Alembic·공개 DohaMusic API 변경
- production authentication, 운영 timeout 정책, circuit breaker와 background daemon
