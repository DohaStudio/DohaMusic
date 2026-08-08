# ADR-028 — 외부 Provider Runtime과 Artifact 계약

> 상태: [제안]
> 작성일: 2026-08-05
> 최종 수정일: 2026-08-08
> 관련 기능: AI Provider 저장소 분리와 단계적 Runtime 전환
> 관련 문서: [책임 경계](../03-architecture/repository-provider-boundaries.md), [AI Pipeline](../03-architecture/ai-pipeline.md), [Artifact Storage 계약](../03-architecture/artifact-storage-contract.md), [Dataset·Artifact 정책](../05-data/local-dataset-artifact-policy.md), [Model Manifest](../04-models/provider-model-manifest.md), [전환 로드맵](../../planning/repository-separation-roadmap.md), [DohaStudio 공통 Provider 계약](https://github.com/DohaStudio/.github/blob/main/docs/specifications/04-provider-contract.md)
> 관련 PR: 이 문서를 추가한 `develop` 대상 PR

## 배경

DohaMusic은 `MusicGenerator`, `StemSeparator`, `VoiceConverter`와 Legacy·Compatibility `PipelineExecutor`를 갖고 있으며 ACE-Step·Demucs·Seed-VC를 격리 subprocess로 실행한다. DohaLM, DohaAudio와 DohaVocal은 별도 저장소로 존재한다. 모델별 Dataset·학습·평가·CUDA 환경과 제품 서비스 책임을 분리하기 위해 이들을 외부 Provider 저장소 경계로 유지할 필요가 있다.

## 문제

저장소를 나눈다는 결정만으로 Runtime 호출, 파일 전달과 장애 복구가 해결되지는 않는다. 현재 로컬 절대 `Path`와 작업별 subprocess 계약을 즉시 HTTP 서비스로 바꾸면 Job 상태·취소·재시도·Artifact 전송·GPU 경쟁·version 호환성을 동시에 변경해야 한다. Big-bang migration은 기존 검증 경로와 rollback을 잃게 만든다.

## 결정

1. 저장소 책임 분리와 Runtime 분리를 별도 단계로 수행한다.
2. DohaMusic은 제품 서비스와 Workspace·Job Orchestration, Provider 선택·호출, 작업 상태, 결과·Artifact 관리, 상업 이용과 접근 권한을 소유한다. 기존 `PipelineExecutor`는 Legacy·Compatibility Workflow로 유지한다.
3. DohaLM은 Lyrics, DohaAudio는 Music Generation·Stem Separation, DohaVocal은 Singing Voice·Voice Conversion의 Dataset·학습·평가·Model Manifest·Runtime을 소유한다. DohaAudio와 DohaVocal 저장소는 존재하며 해당 Runtime 기능은 현재 `[계획]`이다.
4. 신규 Music Generator는 DohaAudio에서, 신규 Singing Voice·Voice Conversion은 DohaVocal에서 구현한다.
5. ACE-Step·Demucs·Seed-VC의 기존 Adapter·Runner는 새 Runtime 계약이 검증될 때까지 로컬 subprocess 호환 계층으로 유지한다.
6. 장기 Provider 연동은 versioned HTTP 또는 동등한 독립 Runtime 계약을 사용한다. 구체 protocol과 배포 기술은 구현 전 검증으로 확정한다.
7. Provider 간 직접 호출을 금지한다. 모든 Provider Job 연결은 DohaMusic Workspace·Job Orchestrator를 통과한다.
8. 단일 GPU 환경의 작업 승인, 동시성 한도와 모델 로드 순서를 포함한 GPU admission control은 DohaMusic이 관리한다.
9. Provider 경계를 넘는 파일은 로컬 절대 Path 대신 Artifact ID 또는 URI와 checksum으로 식별하는 방향으로 전환한다.
10. API와 Artifact 계약은 명시적으로 versioning하고 Model Manifest의 `api_contract_version`과 호환성을 검증한다.

## Provider 작업 최소 계약

장기 Runtime 계약은 최소한 다음 동작과 의미를 제공해야 한다.

| 영역 | 필수 계약 |
|---|---|
| 작업 생성 | request ID·idempotency key·capability·Manifest selector·입력 Artifact 참조 |
| 상태 | 공통 `pending`, `running`, `succeeded`, `failed`, `canceled` 상태와 별도 취소 요청·재시도 Metadata |
| 취소 | 수락 여부, cooperative·강제 취소 능력과 최종 상태 |
| 재시도 | 재시도 가능 오류, attempt, 원본 작업 관계와 중복 방지 |
| 오류 | 안정적인 code, 재시도 가능성, 공개 message와 비공개 진단 분리 |
| Health | process readiness, 모델 readiness와 일시적 수용 불가 상태 구분 |
| 결과 | 출력 Artifact ID·URI, checksum, MIME·audio 규격, Model Manifest identity, 실행 metadata |

세부 Provider endpoint, 인증, callback·polling과 object storage transport는 아직 `[계획]`이다. DohaMusic 내부 Artifact URI는 [ADR-032](ADR-032-artifact-storage-resolver-integrity.md)에 따라 `artifact://<artifact_id>`로 고정하며 등록 전 Provider 임시 출력은 이 URI를 사용하지 않는다.

## Artifact 계약 원칙

- Artifact 참조는 논리 ID 또는 허용된 URI를 사용하며 개발자 PC의 절대 경로를 공개 계약에 저장하지 않는다.
- DohaMusic은 작업과 사용자에 대한 Artifact 소유권·접근 권한·보존·삭제 결정을 관리한다.
- Provider는 입력 접근을 작업 범위와 시간으로 제한하고 결과 checksum과 계보를 반환한다.
- 개인 음성의 철회·삭제는 DohaMusic이 명령하며 DohaVocal은 파생 Dataset·cache·Checkpoint·Adapter의 처리 결과를 추적 가능하게 반환해야 한다.
- 내부 논리 URI는 `artifact://<artifact_id>`를 사용하고 공개 응답은 Artifact API link를 우선한다. 서명 URL, 암호화와 object storage 구현은 보안 검토 후 확정한다.

## Provider API 버전 관리

- 호환성을 깨는 request·response·상태·오류·Artifact 의미 변경은 major contract version을 올린다.
- additive field는 기존 Client가 무시할 수 있어야 하며 필수 필드 변경은 호환성 테스트를 요구한다.
- DohaMusic은 지원 가능한 contract version을 명시하고 불일치 시 작업을 시작하지 않는다.
- Model Manifest와 작업 결과에 실제 사용한 Provider·모델·계약 version을 기록한다.

## 선택 이유

- 현재 검증된 subprocess 경로를 유지해 기능 회귀와 rollback 위험을 줄인다.
- 신규 모델 코드가 DohaMusic에 더 쌓이기 전에 저장소 책임을 적용한다.
- 모델 환경과 제품 서비스의 릴리스 주기를 분리한다.
- Artifact와 작업 계약을 먼저 검증한 뒤 Provider별로 독립 이전할 수 있다.
- Provider 간 숨은 호출과 분산 Workflow를 방지한다.

## 대안

1. 모든 AI 코드와 학습을 DohaMusic에 유지: 환경·Dataset·Checkpoint와 서비스 책임이 계속 결합되므로 선택하지 않는다.
2. 기존 Runner를 즉시 모두 HTTP 서비스로 이전: 취소·Artifact·GPU·운영 계약을 동시에 바꾸고 rollback이 어려워 선택하지 않는다.
3. Provider가 다음 Provider를 직접 호출: 중앙 작업 상태·권리·GPU 제어와 provenance가 분산되므로 금지한다.
4. 공유 파일시스템 절대 Path를 영구 공개 계약으로 사용: 배포 환경 결합과 경로 노출 때문에 전환 호환 수단으로만 제한한다.
5. 공통 Model Registry를 즉시 구축: schema와 운영 요구가 검증되지 않아 이번 단계에서 구현하지 않는다.

## 장점과 단점

장점은 책임·의존성·라이선스·Dataset·Checkpoint 격리, 신규 구현 위치의 명확성, Provider별 단계적 rollback이다. 단점은 여러 저장소의 CI·release·계약 호환 관리, Artifact 전달 비용, 분산 장애 처리와 로컬 개발 복잡성이다.

## 영향

이번 결정은 문서와 향후 구현 위치만 변경한다. 현재 Runtime 코드, API, DB, Adapter 기본값, Pipeline 단계와 파일 계약은 변경하지 않는다. DohaAudio·DohaVocal Runtime API, Singing Voice, HTTP Provider API, Artifact URI와 공통 Model Registry는 구현 완료가 아니다.

ADR-005의 subprocess 격리, ADR-007의 작업별 ACE-Step 수명주기, ADR-008·009의 Provider 검증과 ADR-012의 Orchestrator 원칙은 호환 기간에 유지한다. 실제 독립 Runtime을 도입할 때 해당 ADR의 재검토 조건을 충족한 것으로 보고 구현 세부 ADR을 추가하거나 상태를 갱신한다.

## 마이그레이션

1. Phase A에서 책임·Dataset·Artifact·Manifest·Provider 계약 방향을 문서화한다.
2. Phase B에서 신규 구현을 DohaAudio·DohaVocal에 배치하고 DohaMusic Provider Client를 추가한다.
3. Phase C에서 ACE-Step, Demucs, Seed-VC를 개별 검증 후 순차 이전하고 Artifact ID·URI 계약으로 전환한다.
4. Phase D에서 rollback·호환 종료 조건을 충족한 내부 Runner와 구형 Adapter만 제거한다.

## 재검토 조건

- DohaAudio 또는 DohaVocal에서 첫 Runtime 구현을 시작할 때
- 첫 Provider Runtime API와 인증·Artifact transport를 선택할 때
- 외부 Queue, object storage 또는 GPU scheduler를 도입할 때
- Provider 상태·취소·재시도 또는 Model Manifest schema를 확정할 때
- 기존 Runner 제거 또는 contract major version 변경을 승인할 때
