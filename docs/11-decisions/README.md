# 아키텍처 결정 기록

> 문서 목적: 중요한 결정과 근거, 재검토 조건을 추적한다.
> 현재 상태: **운영 중**

| ADR | 결정 | 상태 |
|---|---|---|
| [ADR-001](ADR-001-pretrained-model-strategy.md) | 공개 사전학습 모델 우선 | 승인 제안 |
| [ADR-002](ADR-002-modular-ai-pipeline.md) | 모듈형 AI 파이프라인 | 승인 |
| [ADR-003](ADR-003-async-job-processing.md) | 비동기 작업 처리 | 승인 |
| [ADR-004](ADR-004-personal-voice-data-policy.md) | 개인 음성 데이터 정책 | 승인 제안 |
| [ADR-005](ADR-005-ai-worker-dependency-isolation.md) | AI Worker 의존성 격리 | 승인 |
| [ADR-006](ADR-006-ace-step-primary-provider.md) | ACE-Step 1차 Provider 채택 | 조건부 채택 |
| [ADR-007](ADR-007-ace-step-runtime-lifecycle.md) | ACE-Step 작업별 격리 subprocess 유지 | 채택됨 |
| [ADR-008](ADR-008-stem-separation-provider.md) | HTDemucs Stem Provider와 출력 계약 | 채택됨 |
| [ADR-009](ADR-009-seed-vc-voice-provider.md) | Seed-VC 격리형 Voice Provider와 참조 음성 경계 | 검증용 채택, 운영 보류 |
| [ADR-010](ADR-010-voice-provider-selection-policy.md) | Voice Provider 수명주기와 운영 승격 기준 | 승인 |
| [ADR-011](ADR-011-voice-provider-selection.md) | Voice Provider 평가와 역할 선정 | Primary 미선정, 운영 통합 보류 |
| [ADR-012](ADR-012-pipeline-orchestrator.md) | Mock 기반 Pipeline Orchestrator와 단계 정책 | 승인 |
| [ADR-013](ADR-013-audio-mixing-engine.md) | Default Audio Mixer의 gain·headroom·limiter·normalization·metadata 정책 | 승인 |
| [ADR-014](ADR-014-lyrics-generator-architecture.md) | LyricsGenerator·Template Provider·Validator·DB·Pipeline 경계 | 승인 |
| [ADR-016](ADR-016-local-lyrics-llm-finetuning.md) | 공개 Instruct Base·권리 확보 Dataset·QLoRA SFT·Local Adapter | 계획 승인, 저장소 책임은 ADR-028로 갱신 |
| [ADR-017](ADR-017-frontend-technology-stack.md) | Phase 8 Frontend framework·style·state·form·test stack | 승인 |
| [ADR-018](ADR-018-secure-audio-file-access.md) | Pipeline 결과 WAV의 경로 비노출 streaming·download 경계 | 승인 |
| [ADR-019](ADR-019-secure-voice-profile-upload.md) | 동의된 WAV upload·검증·저장·삭제 경계 | 승인 |
| [ADR-020](ADR-020-project-history-retention.md) | History projection·Default Project·Project 삭제 시 Job/파일 보존 | 승인 |
| [ADR-021](ADR-021-pipeline-job-cancel-retry.md) | cooperative Cancel·새 Job Retry·입력 Snapshot·원본 관계 | 승인 |
| [ADR-022](ADR-022-kpop-generation-control-layer.md) | K-POP Preset·Generation Options·Prompt Compiler·Capability 경계 | 승인 |
| [ADR-023](ADR-023-audio-analysis-and-preview-architecture.md) | 최종 WAV 비차단 Audio Analysis·Preview·저장·실패 경계 | 승인 |
| [ADR-024](ADR-024-browser-voice-recording-server-normalization.md) | 브라우저 WAV·WebM/Ogg를 Backend에서 PCM16 WAV로 정규화하는 경계 | 제안 |
| [ADR-025](ADR-025-voice-profile-multiple-samples-reference.md) | Voice Profile 1:N Sample과 명시적 대표 Reference | 승인 |
| [ADR-026](ADR-026-voice-enrollment-lifecycle-cleanup.md) | Enrollment 임시 업로드·만료·idempotency·cleanup 수명주기 | 승인 |
| [ADR-027](ADR-027-dohalm-lyrics-provider-boundary.md) | DohaLM Provider·가사 버전·사용자 승인·상업 이용 경계 | 제안 |
| [ADR-028](ADR-028-provider-runtime-artifact-contract.md) | 외부 AI Provider 저장소·Runtime·Artifact 단계적 전환 계약 | 승인 |
| [ADR-029](ADR-029-dohamusic-workspace-artifact-domain.md) | DohaMusic Workspace 전용 `music` Artifact 도메인 | 제안 |
| [ADR-030](ADR-030-asset-version-centric-database.md) | AssetVersion 중심 Workspace 데이터베이스와 단계적 전환 | 제안 |
| [ADR-031](ADR-031-workspace-rest-api-contract.md) | Workspace 중심 REST API와 단계적 Legacy 전환 | 제안 |
| [ADR-032](ADR-032-artifact-storage-resolver-integrity.md) | Artifact Storage Catalog·Resolver·ingestion·무결성 경계 | 승인 |
| [ADR-033](ADR-033-workspace-job-execution-boundary.md) | Workspace Job 실행·claim·cancel·Artifact completion 경계 | 승인 |
| [ADR-034](ADR-034-dohavocal-consumer-contract.md) | DohaVocal strict DTO·transport port·metadata 후보 Consumer 계약 | 승인 |
| [ADR-035](ADR-035-d1-composition-read-authority.md) | D1 Composition Read 권위·Snapshot selection·Track/Section projection·aggregate endpoint | 승인 |
| [ADR-036](ADR-036-provider-job-persistence.md) | Workspace Job과 Provider Job의 1:N 불변 identity·retry persistence | 승인 |
| [ADR-037](ADR-037-reviewer-authentication-deployment-authority.md) | DohaMusic product identity·배포와 DohaAudio reviewer authentication 권위 | 경계 승인, Provider 선택 보류 |

결정 변경 시 기존 문서를 삭제하지 않고 상태와 대체 ADR 링크를 갱신한다.

## AI Provider 저장소 분리

- [ADR-028 — 외부 Provider Runtime과 Artifact 계약](ADR-028-provider-runtime-artifact-contract.md): 저장소 책임과 Runtime 이전을 분리하고 DohaAudio·DohaVocal 계획 경계, subprocess 호환, versioned Job·Artifact·GPU Orchestration 원칙을 결정한다.
- [ADR-034 — DohaVocal Consumer Contract Foundation](ADR-034-dohavocal-consumer-contract.md): 실제 network 없이 strict JSON DTO·transport port로 4개 Vocal capability와 9개 operation, Job·lineage·Manifest·오류 경계를 검증한다.
- [ADR-036 — Provider Job Persistence Contract](ADR-036-provider-job-persistence.md): Provider Job identity와 retry history를 Workspace Job에 1:N으로 영속화하고 Provider Runtime의 상태 권위를 유지한다.
- [ADR-037 — Reviewer Authentication과 배포 권위](ADR-037-reviewer-authentication-deployment-authority.md): CURRENT local/no-login, DohaMusic-only Provider 호출과 delegated trust direction을 확정하고 production topology·reviewer population·실제 Provider는 보류한다.

## Workspace 데이터베이스

- [ADR-030 — AssetVersion 중심 Workspace 데이터베이스](ADR-030-asset-version-centric-database.md): 현행 Pipeline 중심 결과 소유권을 AssetVersion·Artifact로 옮기고 21개 목표 Table과 단계적 Migration 원칙을 제안한다.

## Workspace API

- [ADR-031 — Workspace 중심 REST API 계약](ADR-031-workspace-rest-api-contract.md): Asset·Version·Artifact·Snapshot·Job 중심 `/api/v1` 계약과 Orchestrator 전용 Provider API, cursor·Idempotency·단계적 Legacy 전환을 제안한다.
- [ADR-035 — D1 Composition Read 권위와 Projection 계약](ADR-035-d1-composition-read-authority.md): Workspace read authority, explicit Project selection, snapshot-local Track projection, Section 비가용 상태와 Project aggregate GET을 결정한다.

## Artifact Storage

- [ADR-032 — Artifact Storage Resolver와 무결성 경계](ADR-032-artifact-storage-resolver-integrity.md): 경로 없는 Artifact와 별도 DB Catalog, `artifact://` URI, trusted ingestion, owner·retention·Range·GC 계약을 승인한다.

## Workspace Job

- [ADR-033 — Workspace Job 실행·claim·완료 경계](ADR-033-workspace-job-execution-boundary.md): 공개 5-state와 내부 cancel marker, role 기반 exact Artifact, Workspace scope, claim·lease와 completion 보상 경계를 승인한다.
- [ADR-036 — Provider Job Persistence Contract](ADR-036-provider-job-persistence.md): restart recovery를 위한 identity binding, uniqueness, retry lineage와 crash window 책임을 승인한다.

## Phase 6.5

- [ADR-015 — External Lyrics LLM Provider](ADR-015-external-lyrics-llm-provider.md): OpenAI Responses API Adapter를 Experimental로 추가하고 Template 기본값, strict Schema, retry·fallback·비용·데이터 경계를 결정한다.
- [ADR-027 — DohaLM 가사 Provider와 사용자 승인 경계](ADR-027-dohalm-lyrics-provider-boundary.md): 별도 DohaLM Runtime 연동, 사용자 최종 승인, 직접 작성 fallback과 상업 이용 fail-closed 정책을 제안한다.

## Phase 6.6~6.9

- [ADR-016 — Local Lyrics LLM Fine-tuning](ADR-016-local-lyrics-llm-finetuning.md): 공개 Instruct Base와 권리 확보 Dataset의 QLoRA SFT, `LocalLyricsLLMAdapter`, 승인 전 Template 기본값을 결정한다.

## Phase 8

- [ADR-017 — Frontend Technology Stack](ADR-017-frontend-technology-stack.md): 구현·검증된 Frontend library·toolchain과 상태 경계를 승인한다.
- [ADR-018 — Secure Audio File Access](ADR-018-secure-audio-file-access.md): Pipeline 결과 WAV를 내부 경로 없이 검증·stream하고 로컬 단일 사용자와 공개 운영 경계를 분리한다.
- [ADR-020 — Project History Retention](ADR-020-project-history-retention.md): Project 삭제 시 연결만 해제하고 Job과 결과 파일을 보존한다.
- [ADR-019 — Secure Voice Profile Upload](ADR-019-secure-voice-profile-upload.md): 동의된 WAV를 안전하게 저장하고 공개 metadata·삭제 정책과 원본 비공개 경계를 결정한다.
- [ADR-021 — Pipeline Job Cancel·Retry](ADR-021-pipeline-job-cancel-retry.md): 단계 경계 cooperative 취소와 입력 Snapshot 기반 새 Job Retry를 결정한다.
- [ADR-029 — DohaMusic Workspace 전용 music Artifact 도메인](ADR-029-dohamusic-workspace-artifact-domain.md): Provider Artifact와 Composition Snapshot·Mix·Preview·Export 결과의 Workspace 저장 책임을 분리한다.
- [ADR-032 — Artifact Storage Resolver와 무결성 경계](ADR-032-artifact-storage-resolver-integrity.md): Workspace와 Provider Artifact의 locator·무결성·공개 delivery 경계를 고정한다.

## K-POP Creation Control

- [ADR-022 — K-POP Generation Control Layer](ADR-022-kpop-generation-control-layer.md): Provider-neutral Preset·Options·Compiler·Capability·Snapshot·평가·권리 경계를 결정한다.
- [ADR-023 — Audio Analysis와 Preview 아키텍처](ADR-023-audio-analysis-and-preview-architecture.md): 최종 WAV 기반 비차단 분석, versioned metadata, confidence, Preview와 secure access 경계를 결정한다.

## F6 Guided Voice Enrollment

- [ADR-024 — 브라우저 음성 녹음 포맷과 서버 정규화 경계](ADR-024-browser-voice-recording-server-normalization.md): Python WAV와 optional FFmpeg 경계를 구현하고 Windows/CI 변환을 검증했으며 운영 build 라이선스·자원 상한·실기기 평가 전까지 제안을 유지한다.
- [ADR-025 — Voice Profile 다중 Sample과 대표 Reference 모델](ADR-025-voice-profile-multiple-samples-reference.md): Sample 개별 보존과 사용자가 확정한 대표 reference 하나를 Pipeline에 전달하는 구현을 승인했다.
- [ADR-026 — Voice Enrollment 임시 업로드와 정리 수명주기](ADR-026-voice-enrollment-lifecycle-cleanup.md): 임시 aggregate·만료·멱등성·승격·cleanup retry·orphan scan·시작 crash recovery를 구현했다.
