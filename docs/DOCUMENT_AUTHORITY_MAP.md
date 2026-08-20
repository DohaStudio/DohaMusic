# DohaMusic Documentation Authority Map

> 문서 상태: [운영 기준]
> 최종 수정일: 2026-08-20
> 기준: `develop@e3bb7c6e5f148745ac85d244dd47c9f4cd0ccc7c`
> 관련 문서: [README](../README.md), [Cleanup Plan](DOCUMENT_CLEANUP_PLAN.md), [Master Roadmap](../MASTER_ROADMAP.md), [실행 로드맵](../ROADMAP.md)

## 1. 목적과 분류 원칙

이 문서는 DohaMusic의 추적 중인 Markdown 문서 261개를 분류한 탐색 기준이다. 같은 책임의 문서가 여러 개일 때 CANONICAL만 현재 source of truth로 사용하고, SUPPORTING은 세부 계약, HISTORICAL은 결정·실험·검증 증거로 읽는다.

| Classification | 의미 |
|---|---|
| CANONICAL | 현재 책임 범위의 source of truth |
| SUPPORTING | Canonical을 보충하는 유효한 세부 문서 |
| HISTORICAL | ADR·실험·평가·Validation 등 보존해야 하는 증거 |
| SUPERSEDED | 더 최신 Canonical 또는 DoD가 책임을 대체 |
| STALE | 현재 구현과 대조·갱신이 필요한 비권위 문서 |

권장 조치는 실제 파일 삭제를 승인하지 않는다. `DELETE_CANDIDATE`도 별도 inbound link·evidence·정보 손실 검증을 모두 통과해야 한다. 이 Inventory에서는 삭제 대상을 확정하지 않는다.

## 2. 사람이 먼저 읽을 Canonical 구조

| 질문 | Canonical |
|---|---|
| 이 Repository는 무엇이며 현재 어디까지 왔는가? | [README](../README.md) |
| 최종적으로 무엇을 만드는가? | [AI-native DAW 제품 방향](02-product/ai-native-daw-product-direction.md) |
| 시스템은 어떻게 연결되는가? | [시스템 아키텍처](03-architecture/system-architecture.md) |
| 목표 Runtime과 미구현 Gap은 무엇인가? | [AI-native DAW 목표 아키텍처](03-architecture/ai-native-daw-target-architecture.md) |
| DohaMusic·LM·Audio·Vocal의 책임은 무엇인가? | [Provider 책임 경계](03-architecture/repository-provider-boundaries.md) |
| 지금 무엇을 먼저 하는가? | [실행 로드맵](../ROADMAP.md) |
| 장기 Phase·Track·Gate는 무엇인가? | [Master Roadmap](../MASTER_ROADMAP.md) |
| 완료를 언제 선언하는가? | [DoD Index](DoD/README.md) |
| 실행·환경·복구는 어디서 보는가? | [로컬 개발 환경](10-operations/local-development.md)과 세부 Runbook |
| 왜 이렇게 설계했는가? | [ADR Index](11-decisions/README.md) |
| 실제 무엇을 검증했는가? | 아래 [Validation / Reports](#validation--reports) |
| 언제 무엇이 바뀌었는가? | [CHANGELOG](../CHANGELOG.md) |

## 3. 전체 Inventory

정확한 경로 행이 directory 분류보다 우선한다. Recommended Action은 이번 PR의 즉시 삭제 명령이 아니라 후속 정리 방향이다.

### CANONICAL

| Document | Classification | Authority Scope | Replaced By | Recommended Action |
|---|---|---|---|---|
| [AGENTS.md](../AGENTS.md) | CANONICAL | 개발 에이전트 작업 규칙 | — | KEEP |
| [CHANGELOG.md](../CHANGELOG.md) | CANONICAL | 변경 시점과 내용의 연속 기록 | — | KEEP |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | CANONICAL | 사람 기여 절차 | — | KEEP |
| [docs/02-product/ai-native-daw-product-direction.md](02-product/ai-native-daw-product-direction.md) | CANONICAL | DohaMusic 제품 목표와 CURRENT/TARGET | — | KEEP |
| [docs/03-architecture/ai-native-daw-target-architecture.md](03-architecture/ai-native-daw-target-architecture.md) | CANONICAL | AI-native DAW 목표 Runtime과 Gap | — | KEEP |
| [docs/03-architecture/common-ai-contract-consumer.md](03-architecture/common-ai-contract-consumer.md) | CANONICAL | Common Contract 현재 소비와 재사용 경계 | — | KEEP |
| [docs/03-architecture/repository-provider-boundaries.md](03-architecture/repository-provider-boundaries.md) | CANONICAL | DohaMusic·LM·Audio·Vocal 책임 경계 | — | KEEP |
| [docs/03-architecture/system-architecture.md](03-architecture/system-architecture.md) | CANONICAL | 현재 시스템 연결과 상위 Architecture | — | KEEP |
| [docs/06-api/api-overview.md](06-api/api-overview.md) | CANONICAL | 공개 API 탐색 시작점 | — | KEEP |
| [docs/07-database/database-overview.md](07-database/database-overview.md) | CANONICAL | CURRENT Runtime·CURRENT Workspace/Domain·TARGET·TRANSITION 탐색 시작점 | — | KEEP |
| [docs/09-security/security-policy.md](09-security/security-policy.md) | CANONICAL | 보안 정책 탐색 시작점 | — | KEEP |
| [docs/10-operations/local-development.md](10-operations/local-development.md) | CANONICAL | 로컬 실행·검증 운영 시작점 | — | KEEP |
| [docs/11-decisions/README.md](11-decisions/README.md) | CANONICAL | ADR Index | — | KEEP |
| [docs/DOCUMENT_AUTHORITY_MAP.md](DOCUMENT_AUTHORITY_MAP.md) | CANONICAL | 문서 분류와 탐색 기준 | — | UPDATE |
| [docs/DoD/README.md](DoD/README.md) | CANONICAL | 완료 판정 Index | — | KEEP |
| [MASTER_ROADMAP.md](../MASTER_ROADMAP.md) | CANONICAL | 장기 Product Phase·Track·Gate | — | KEEP |
| [README.md](../README.md) | CANONICAL | Repository entry point와 CURRENT/TARGET 요약 | — | KEEP |
| [ROADMAP.md](../ROADMAP.md) | CANONICAL | 현재 실행 순서와 NEXT/LATER | — | KEEP |

### SUPPORTING

| Document | Classification | Authority Scope | Replaced By | Recommended Action |
|---|---|---|---|---|
| [docs/00-overview/terminology.md](00-overview/terminology.md) | SUPPORTING | 프로젝트 개요·용어·시나리오 | — | KEEP |
| [docs/00-overview/user-scenarios.md](00-overview/user-scenarios.md) | SUPPORTING | 프로젝트 개요·용어·시나리오 | — | KEEP |
| [docs/01-research/audio-analysis-library-comparison.md](01-research/audio-analysis-library-comparison.md) | SUPPORTING | 모델·라이선스·기술 조사 | — | KEEP |
| [docs/01-research/licensing-review.md](01-research/licensing-review.md) | SUPPORTING | 모델·라이선스·기술 조사 | — | KEEP |
| [docs/01-research/lyrics-llm-provider-comparison.md](01-research/lyrics-llm-provider-comparison.md) | SUPPORTING | 모델·라이선스·기술 조사 | — | KEEP |
| [docs/01-research/model-comparison.md](01-research/model-comparison.md) | SUPPORTING | 모델·라이선스·기술 조사 | — | KEEP |
| [docs/01-research/music-generation-models.md](01-research/music-generation-models.md) | SUPPORTING | 모델·라이선스·기술 조사 | — | KEEP |
| [docs/01-research/singing-voice-synthesis.md](01-research/singing-voice-synthesis.md) | SUPPORTING | 모델·라이선스·기술 조사 | — | KEEP |
| [docs/01-research/source-separation.md](01-research/source-separation.md) | SUPPORTING | 모델·라이선스·기술 조사 | — | KEEP |
| [docs/01-research/voice-conversion.md](01-research/voice-conversion.md) | SUPPORTING | 모델·라이선스·기술 조사 | — | KEEP |
| [docs/01-research/voice-provider-comparison.md](01-research/voice-provider-comparison.md) | SUPPORTING | 모델·라이선스·기술 조사 | — | KEEP |
| [docs/02-product/k3-audio-analysis-product-definition.md](02-product/k3-audio-analysis-product-definition.md) | SUPPORTING | 제품 Track 상세 | — | KEEP |
| [docs/02-product/kpop-creation-product-definition.md](02-product/kpop-creation-product-definition.md) | SUPPORTING | 제품 Track 상세 | — | KEEP |
| [docs/02-requirements/acceptance-criteria.md](02-requirements/acceptance-criteria.md) | SUPPORTING | 기능·품질 요구사항 | — | KEEP |
| [docs/02-requirements/functional-requirements.md](02-requirements/functional-requirements.md) | SUPPORTING | 기능·품질 요구사항 | — | KEEP |
| [docs/02-requirements/non-functional-requirements.md](02-requirements/non-functional-requirements.md) | SUPPORTING | 기능·품질 요구사항 | — | KEEP |
| [docs/02-requirements/user-stories.md](02-requirements/user-stories.md) | SUPPORTING | 기능·품질 요구사항 | — | KEEP |
| [docs/02-requirements/voice-enrollment-requirements.md](02-requirements/voice-enrollment-requirements.md) | SUPPORTING | 기능·품질 요구사항 | — | KEEP |
| [docs/03-architecture/ai-pipeline.md](03-architecture/ai-pipeline.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/artifact-storage-contract.md](03-architecture/artifact-storage-contract.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/audio-analysis-failure-policy.md](03-architecture/audio-analysis-failure-policy.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/audio-analysis-result-contract.md](03-architecture/audio-analysis-result-contract.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/audio-quality-engine.md](03-architecture/audio-quality-engine.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/backend-architecture.md](03-architecture/backend-architecture.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/deployment-architecture.md](03-architecture/deployment-architecture.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/design-reference-policy.md](03-architecture/design-reference-policy.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/dohalm-integration.md](03-architecture/dohalm-integration.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/dohavocal-consumer-contract.md](03-architecture/dohavocal-consumer-contract.md) | SUPPORTING | DohaVocal `0.1.0` Consumer DTO·mapping·transport port 계약 | [docs/03-architecture/system-architecture.md](03-architecture/system-architecture.md) | KEEP |
| [docs/03-architecture/frontend-architecture.md](03-architecture/frontend-architecture.md) | SUPPORTING | CURRENT Frontend 구조·state/API·design 구현 경계 | — | KEEP |
| [docs/03-architecture/frontend-overview.md](03-architecture/frontend-overview.md) | SUPPORTING | CURRENT Frontend 경험·route·지원 범위 | — | KEEP |
| [docs/03-architecture/kpop-generation-options.md](03-architecture/kpop-generation-options.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/kpop-prompt-compiler.md](03-architecture/kpop-prompt-compiler.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/lyrics-ai.md](03-architecture/lyrics-ai.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/pipeline-orchestrator.md](03-architecture/pipeline-orchestrator.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/storage-architecture.md](03-architecture/storage-architecture.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/studio-ux-flow.md](03-architecture/studio-ux-flow.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/worker-architecture.md](03-architecture/worker-architecture.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/workspace-artifact-model.md](03-architecture/workspace-artifact-model.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/workspace-job-foundation.md](03-architecture/workspace-job-foundation.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/03-architecture/workspace-service-transaction.md](03-architecture/workspace-service-transaction.md) | SUPPORTING | 세부 Architecture·계약 | — | KEEP |
| [docs/04-models/gpu-memory-strategy.md](04-models/gpu-memory-strategy.md) | SUPPORTING | 모델·Provider 선택과 Adapter 정책 | — | KEEP |
| [docs/04-models/kpop-provider-capability-matrix.md](04-models/kpop-provider-capability-matrix.md) | SUPPORTING | 모델·Provider 선택과 Adapter 정책 | — | KEEP |
| [docs/04-models/local-lyrics-llm-model-card-template.md](04-models/local-lyrics-llm-model-card-template.md) | SUPPORTING | 모델·Provider 선택과 Adapter 정책 | — | KEEP |
| [docs/04-models/lyrics-provider-selection-policy.md](04-models/lyrics-provider-selection-policy.md) | SUPPORTING | 모델·Provider 선택과 Adapter 정책 | — | KEEP |
| [docs/04-models/model-loading-strategy.md](04-models/model-loading-strategy.md) | SUPPORTING | 모델·Provider 선택과 Adapter 정책 | — | KEEP |
| [docs/04-models/model-selection-policy.md](04-models/model-selection-policy.md) | SUPPORTING | 모델·Provider 선택과 Adapter 정책 | — | KEEP |
| [docs/04-models/music-generation-adapter.md](04-models/music-generation-adapter.md) | SUPPORTING | 모델·Provider 선택과 Adapter 정책 | — | KEEP |
| [docs/04-models/provider-model-manifest.md](04-models/provider-model-manifest.md) | SUPPORTING | 모델·Provider 선택과 Adapter 정책 | — | KEEP |
| [docs/04-models/source-separation-adapter.md](04-models/source-separation-adapter.md) | SUPPORTING | 모델·Provider 선택과 Adapter 정책 | — | KEEP |
| [docs/04-models/voice-conversion-adapter.md](04-models/voice-conversion-adapter.md) | SUPPORTING | 모델·Provider 선택과 Adapter 정책 | — | KEEP |
| [docs/04-models/voice-provider-score.md](04-models/voice-provider-score.md) | SUPPORTING | 모델·Provider 선택과 Adapter 정책 | — | KEEP |
| [docs/04-models/voice-provider-selection-policy.md](04-models/voice-provider-selection-policy.md) | SUPPORTING | 모델·Provider 선택과 Adapter 정책 | — | KEEP |
| [docs/05-data/audio-data-policy.md](05-data/audio-data-policy.md) | SUPPORTING | Dataset·전처리·권리 정책 | — | KEEP |
| [docs/05-data/data-quality-checklist.md](05-data/data-quality-checklist.md) | SUPPORTING | Dataset·전처리·권리 정책 | — | KEEP |
| [docs/05-data/dataset-structure.md](05-data/dataset-structure.md) | SUPPORTING | Dataset·전처리·권리 정책 | — | KEEP |
| [docs/05-data/kpop-style-dataset-policy.md](05-data/kpop-style-dataset-policy.md) | SUPPORTING | Dataset·전처리·권리 정책 | — | KEEP |
| [docs/05-data/local-dataset-artifact-policy.md](05-data/local-dataset-artifact-policy.md) | SUPPORTING | Dataset·전처리·권리 정책 | — | KEEP |
| [docs/05-data/lyrics-dataset-policy.md](05-data/lyrics-dataset-policy.md) | SUPPORTING | Dataset·전처리·권리 정책 | — | KEEP |
| [docs/05-data/metadata-schema.md](05-data/metadata-schema.md) | SUPPORTING | Dataset·전처리·권리 정책 | — | KEEP |
| [docs/05-data/preprocessing-pipeline.md](05-data/preprocessing-pipeline.md) | SUPPORTING | Dataset·전처리·권리 정책 | — | KEEP |
| [docs/05-data/voice-recording-guide.md](05-data/voice-recording-guide.md) | SUPPORTING | Dataset·전처리·권리 정책 | — | KEEP |
| [docs/06-api/api-contract-migration-strategy.md](06-api/api-contract-migration-strategy.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/audio-api.md](06-api/audio-api.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/composition-read-workspace.md](06-api/composition-read-workspace.md) | SUPPORTING | D1 Composition read authority·selection·projection·aggregate API 계약 | [docs/06-api/api-overview.md](06-api/api-overview.md) | KEEP |
| [docs/06-api/composition-snapshot-foundation.md](06-api/composition-snapshot-foundation.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/cursor-pagination.md](06-api/cursor-pagination.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/error-codes.md](06-api/error-codes.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/generation-api.md](06-api/generation-api.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/history-project-api.md](06-api/history-project-api.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/job-api.md](06-api/job-api.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/lyrics-api.md](06-api/lyrics-api.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/model-api.md](06-api/model-api.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/pipeline-api.md](06-api/pipeline-api.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/provider-api-contract.md](06-api/provider-api-contract.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/stem-api.md](06-api/stem-api.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/voice-conversion-api.md](06-api/voice-conversion-api.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/voice-enrollment-api.md](06-api/voice-enrollment-api.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/workspace-api-foundation-bootstrap.md](06-api/workspace-api-foundation-bootstrap.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/workspace-rest-api-contract.md](06-api/workspace-rest-api-contract.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/06-api/workspace-rest-api-endpoints.md](06-api/workspace-rest-api-endpoints.md) | SUPPORTING | 상세 API 계약 | — | KEEP |
| [docs/07-database/asset-keyset-indexes.md](07-database/asset-keyset-indexes.md) | SUPPORTING | 상세 DB·Migration·ERD | — | KEEP |
| [docs/07-database/database-redesign-erd.md](07-database/database-redesign-erd.md) | SUPPORTING | TARGET / PARTIALLY IMPLEMENTED Workspace ERD | — | KEEP |
| [docs/07-database/database-redesign-migration-strategy.md](07-database/database-redesign-migration-strategy.md) | SUPPORTING | CURRENT→TARGET 전환·rollback Authority | — | KEEP |
| [docs/07-database/database-redesign-overview.md](07-database/database-redesign-overview.md) | SUPPORTING | TARGET 논리 구조와 부분 구현 상태 | — | KEEP |
| [docs/07-database/database-redesign-table-definition.md](07-database/database-redesign-table-definition.md) | SUPPORTING | TARGET / PARTIALLY IMPLEMENTED Workspace Table 정의 | — | KEEP |
| [docs/07-database/erd.md](07-database/erd.md) | SUPPORTING | CURRENT Runtime 14개 Table 관계 | — | KEEP |
| [docs/07-database/job-state-model.md](07-database/job-state-model.md) | SUPPORTING | 상세 DB·Migration·ERD | — | KEEP |
| [docs/07-database/lyrics-versioning-data-model.md](07-database/lyrics-versioning-data-model.md) | SUPPORTING | 상세 DB·Migration·ERD | — | KEEP |
| [docs/07-database/pipeline-tables.md](07-database/pipeline-tables.md) | SUPPORTING | CURRENT Runtime Pipeline 2개 Table | — | KEEP |
| [docs/07-database/project-asset-keyset-indexes.md](07-database/project-asset-keyset-indexes.md) | SUPPORTING | 상세 DB·Migration·ERD | — | KEEP |
| [docs/07-database/table-definition.md](07-database/table-definition.md) | SUPPORTING | CURRENT Runtime Core 10개 Table 정의 | — | KEEP |
| [docs/07-database/voice-conversion-tables.md](07-database/voice-conversion-tables.md) | SUPPORTING | CURRENT Runtime Voice Conversion 2개 Table | — | KEEP |
| [docs/07-database/voice-enrollment-data-model.md](07-database/voice-enrollment-data-model.md) | SUPPORTING | CURRENT Runtime Voice Enrollment schema와 lifecycle | — | KEEP |
| [docs/07-database/workspace-keyset-indexes.md](07-database/workspace-keyset-indexes.md) | SUPPORTING | 상세 DB·Migration·ERD | — | KEEP |
| [docs/08-evaluation/audio-quality-metrics.md](08-evaluation/audio-quality-metrics.md) | SUPPORTING | 평가 기준과 Benchmark 시나리오 | — | KEEP |
| [docs/08-evaluation/benchmark-scenarios.md](08-evaluation/benchmark-scenarios.md) | SUPPORTING | 평가 기준과 Benchmark 시나리오 | — | KEEP |
| [docs/08-evaluation/evaluation-strategy.md](08-evaluation/evaluation-strategy.md) | SUPPORTING | 평가 기준과 Benchmark 시나리오 | — | KEEP |
| [docs/08-evaluation/korean-pronunciation-evaluation.md](08-evaluation/korean-pronunciation-evaluation.md) | SUPPORTING | 평가 기준과 Benchmark 시나리오 | — | KEEP |
| [docs/08-evaluation/voice-similarity-evaluation.md](08-evaluation/voice-similarity-evaluation.md) | SUPPORTING | 평가 기준과 Benchmark 시나리오 | — | KEEP |
| [docs/09-security/external-llm-data-policy.md](09-security/external-llm-data-policy.md) | SUPPORTING | 세부 보안·권리 정책 | — | KEEP |
| [docs/09-security/file-upload-security.md](09-security/file-upload-security.md) | SUPPORTING | 세부 보안·권리 정책 | — | KEEP |
| [docs/09-security/generated-content-policy.md](09-security/generated-content-policy.md) | SUPPORTING | 세부 보안·권리 정책 | — | KEEP |
| [docs/09-security/model-abuse-prevention.md](09-security/model-abuse-prevention.md) | SUPPORTING | 세부 보안·권리 정책 | — | KEEP |
| [docs/09-security/voice-consent-policy.md](09-security/voice-consent-policy.md) | SUPPORTING | 세부 보안·권리 정책 | — | KEEP |
| [docs/10-operations/artifact-storage-ingestion.md](10-operations/artifact-storage-ingestion.md) | SUPPORTING | 실행·배포·복구 Runbook | — | KEEP |
| [docs/10-operations/artifact-storage-reconciliation.md](10-operations/artifact-storage-reconciliation.md) | SUPPORTING | 실행·배포·복구 Runbook | — | KEEP |
| [docs/10-operations/deployment-guide.md](10-operations/deployment-guide.md) | SUPPORTING | 실행·배포·복구 Runbook | — | KEEP |
| [docs/10-operations/environment-variables.md](10-operations/environment-variables.md) | SUPPORTING | 실행·배포·복구 Runbook | — | KEEP |
| [docs/10-operations/external-lyrics-provider-setup.md](10-operations/external-lyrics-provider-setup.md) | SUPPORTING | 실행·배포·복구 Runbook | — | KEEP |
| [docs/10-operations/logging-and-monitoring.md](10-operations/logging-and-monitoring.md) | SUPPORTING | 실행·배포·복구 Runbook | — | KEEP |
| [docs/10-operations/troubleshooting.md](10-operations/troubleshooting.md) | SUPPORTING | 실행·배포·복구 Runbook | — | KEEP |
| [docs/10-operations/voice-enrollment-operations-checklist.md](10-operations/voice-enrollment-operations-checklist.md) | SUPPORTING | 실행·배포·복구 Runbook | — | KEEP |
| [docs/10-operations/workspace-db-backup-rollback-policy.md](10-operations/workspace-db-backup-rollback-policy.md) | SUPPORTING | 실행·배포·복구 Runbook | — | KEEP |
| [docs/10-operations/workspace-db-migration-runbook.md](10-operations/workspace-db-migration-runbook.md) | SUPPORTING | 실행·배포·복구 Runbook | — | KEEP |
| [docs/10-operations/workspace-db-preflight-checklist.md](10-operations/workspace-db-preflight-checklist.md) | SUPPORTING | 실행·배포·복구 Runbook | — | KEEP |
| [docs/10-operations/workspace-job-worker.md](10-operations/workspace-job-worker.md) | SUPPORTING | 실행·배포·복구 Runbook | — | KEEP |
| [docs/DOCUMENT_CLEANUP_PLAN.md](DOCUMENT_CLEANUP_PLAN.md) | SUPPORTING | 후속 문서 정리 제안 | — | KEEP |
| [docs/DoD/AI-Native-DAW.md](DoD/AI-Native-DAW.md) | SUPPORTING | Phase·Track 완료 조건 | — | KEEP |
| [docs/DoD/Phase-01.md](DoD/Phase-01.md) | SUPPORTING | Phase·Track 완료 조건 | — | KEEP |
| [docs/DoD/Phase-02.5.md](DoD/Phase-02.5.md) | SUPPORTING | Phase·Track 완료 조건 | — | KEEP |
| [docs/DoD/Phase-02.md](DoD/Phase-02.md) | SUPPORTING | Phase·Track 완료 조건 | — | KEEP |
| [docs/DoD/Phase-03.md](DoD/Phase-03.md) | SUPPORTING | Phase·Track 완료 조건 | — | KEEP |
| [docs/DoD/Phase-04.md](DoD/Phase-04.md) | SUPPORTING | Phase·Track 완료 조건 | — | KEEP |
| [docs/DoD/Phase-05.md](DoD/Phase-05.md) | SUPPORTING | Phase·Track 완료 조건 | — | KEEP |
| [docs/DoD/Phase-06.md](DoD/Phase-06.md) | SUPPORTING | Phase·Track 완료 조건 | — | KEEP |
| [docs/DoD/Phase-07.md](DoD/Phase-07.md) | SUPPORTING | Phase·Track 완료 조건 | — | KEEP |
| [docs/DoD/Phase-08.md](DoD/Phase-08.md) | SUPPORTING | Phase·Track 완료 조건 | — | KEEP |
| [docs/DoD/Phase-09.md](DoD/Phase-09.md) | SUPPORTING | Phase·Track 완료 조건 | — | KEEP |
| [docs/DoD/Provider-Separation.md](DoD/Provider-Separation.md) | SUPPORTING | Phase·Track 완료 조건 | — | KEEP |
| [planning/ai-native-daw-frontend-migration.md](../planning/ai-native-daw-frontend-migration.md) | SUPPORTING | 세부 실행 계획과 Backlog | — | KEEP |
| [planning/backlog.md](../planning/backlog.md) | SUPPORTING | 세부 실행 계획과 Backlog | — | KEEP |
| [planning/frontend-roadmap.md](../planning/frontend-roadmap.md) | SUPPORTING | F6 Guided Voice Enrollment 현재 실행 기준 | — | KEEP |
| [planning/kpop-creation-roadmap.md](../planning/kpop-creation-roadmap.md) | SUPPORTING | 세부 실행 계획과 Backlog | — | KEEP |
| [planning/local-lyrics-llm-roadmap.md](../planning/local-lyrics-llm-roadmap.md) | SUPPORTING | 세부 실행 계획과 Backlog | — | KEEP |
| [planning/repository-separation-roadmap.md](../planning/repository-separation-roadmap.md) | SUPPORTING | 세부 실행 계획과 Backlog | — | KEEP |
| [reports/audio-quality-report-template.md](../reports/audio-quality-report-template.md) | SUPPORTING | 보고서 템플릿 | — | KEEP |
| [reports/experiment-report-template.md](../reports/experiment-report-template.md) | SUPPORTING | 보고서 템플릿 | — | KEEP |
| [reports/gpu-benchmark-template.md](../reports/gpu-benchmark-template.md) | SUPPORTING | 보고서 템플릿 | — | KEEP |
| [reports/model-test-template.md](../reports/model-test-template.md) | SUPPORTING | 보고서 템플릿 | — | KEEP |

### HISTORICAL

| Document | Classification | Authority Scope | Replaced By | Recommended Action |
|---|---|---|---|---|
| [docs/11-decisions/ADR-001-pretrained-model-strategy.md](11-decisions/ADR-001-pretrained-model-strategy.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-002-modular-ai-pipeline.md](11-decisions/ADR-002-modular-ai-pipeline.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-003-async-job-processing.md](11-decisions/ADR-003-async-job-processing.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-004-personal-voice-data-policy.md](11-decisions/ADR-004-personal-voice-data-policy.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-005-ai-worker-dependency-isolation.md](11-decisions/ADR-005-ai-worker-dependency-isolation.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-006-ace-step-primary-provider.md](11-decisions/ADR-006-ace-step-primary-provider.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-007-ace-step-runtime-lifecycle.md](11-decisions/ADR-007-ace-step-runtime-lifecycle.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-008-stem-separation-provider.md](11-decisions/ADR-008-stem-separation-provider.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-009-seed-vc-voice-provider.md](11-decisions/ADR-009-seed-vc-voice-provider.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-010-voice-provider-selection-policy.md](11-decisions/ADR-010-voice-provider-selection-policy.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-011-voice-provider-selection.md](11-decisions/ADR-011-voice-provider-selection.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-012-pipeline-orchestrator.md](11-decisions/ADR-012-pipeline-orchestrator.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-013-audio-mixing-engine.md](11-decisions/ADR-013-audio-mixing-engine.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-014-lyrics-generator-architecture.md](11-decisions/ADR-014-lyrics-generator-architecture.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-015-external-lyrics-llm-provider.md](11-decisions/ADR-015-external-lyrics-llm-provider.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-016-local-lyrics-llm-finetuning.md](11-decisions/ADR-016-local-lyrics-llm-finetuning.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-017-frontend-technology-stack.md](11-decisions/ADR-017-frontend-technology-stack.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-018-secure-audio-file-access.md](11-decisions/ADR-018-secure-audio-file-access.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-019-secure-voice-profile-upload.md](11-decisions/ADR-019-secure-voice-profile-upload.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-020-project-history-retention.md](11-decisions/ADR-020-project-history-retention.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-021-pipeline-job-cancel-retry.md](11-decisions/ADR-021-pipeline-job-cancel-retry.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-022-kpop-generation-control-layer.md](11-decisions/ADR-022-kpop-generation-control-layer.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-023-audio-analysis-and-preview-architecture.md](11-decisions/ADR-023-audio-analysis-and-preview-architecture.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-024-browser-voice-recording-server-normalization.md](11-decisions/ADR-024-browser-voice-recording-server-normalization.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-025-voice-profile-multiple-samples-reference.md](11-decisions/ADR-025-voice-profile-multiple-samples-reference.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-026-voice-enrollment-lifecycle-cleanup.md](11-decisions/ADR-026-voice-enrollment-lifecycle-cleanup.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-027-dohalm-lyrics-provider-boundary.md](11-decisions/ADR-027-dohalm-lyrics-provider-boundary.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-028-provider-runtime-artifact-contract.md](11-decisions/ADR-028-provider-runtime-artifact-contract.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-029-dohamusic-workspace-artifact-domain.md](11-decisions/ADR-029-dohamusic-workspace-artifact-domain.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-030-asset-version-centric-database.md](11-decisions/ADR-030-asset-version-centric-database.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-031-workspace-rest-api-contract.md](11-decisions/ADR-031-workspace-rest-api-contract.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-032-artifact-storage-resolver-integrity.md](11-decisions/ADR-032-artifact-storage-resolver-integrity.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-033-workspace-job-execution-boundary.md](11-decisions/ADR-033-workspace-job-execution-boundary.md) | HISTORICAL | 설계 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-034-dohavocal-consumer-contract.md](11-decisions/ADR-034-dohavocal-consumer-contract.md) | HISTORICAL | DohaVocal Consumer 계약 결정 이력 | — | KEEP |
| [docs/11-decisions/ADR-035-d1-composition-read-authority.md](11-decisions/ADR-035-d1-composition-read-authority.md) | HISTORICAL | D1 Composition read 권위·selection·projection 결정 이력 | — | KEEP |
| [docs/archive/frontend/design-system.md](archive/frontend/design-system.md) | HISTORICAL | Phase 8 Frontend design 초안 | [docs/03-architecture/frontend-architecture.md](03-architecture/frontend-architecture.md) | ARCHIVED |
| [docs/archive/frontend/navigation-guide.md](archive/frontend/navigation-guide.md) | HISTORICAL | Phase 8 navigation 초안 | [docs/03-architecture/frontend-overview.md](03-architecture/frontend-overview.md) | ARCHIVED |
| [docs/archive/frontend/page-structure.md](archive/frontend/page-structure.md) | HISTORICAL | Phase 8 page hierarchy 초안 | [docs/03-architecture/frontend-architecture.md](03-architecture/frontend-architecture.md) | ARCHIVED |
| [docs/archive/frontend/responsive-guide.md](archive/frontend/responsive-guide.md) | HISTORICAL | Phase 8 responsive 초안 | [docs/03-architecture/frontend-architecture.md](03-architecture/frontend-architecture.md) | ARCHIVED |
| [docs/archive/frontend/ui-component-guide.md](archive/frontend/ui-component-guide.md) | HISTORICAL | Phase 8 component 초안 | [docs/03-architecture/frontend-architecture.md](03-architecture/frontend-architecture.md) | ARCHIVED |
| [planning/archive/phase-01-research.md](../planning/archive/phase-01-research.md) | HISTORICAL | 초기 조사·설계 Phase 계획 | [MASTER_ROADMAP.md](../MASTER_ROADMAP.md)<br>[docs/DoD/README.md](DoD/README.md) | ARCHIVED |
| [planning/archive/phase-02-local-inference.md](../planning/archive/phase-02-local-inference.md) | HISTORICAL | 초기 로컬 추론 Phase 계획 | [MASTER_ROADMAP.md](../MASTER_ROADMAP.md)<br>[docs/DoD/Phase-02.md](DoD/Phase-02.md) | ARCHIVED |
| [planning/archive/phase-03-ai-pipeline.md](../planning/archive/phase-03-ai-pipeline.md) | HISTORICAL | 초기 AI Pipeline Phase 계획 | [MASTER_ROADMAP.md](../MASTER_ROADMAP.md)<br>[docs/DoD/Phase-05.md](DoD/Phase-05.md) | ARCHIVED |
| [planning/archive/phase-04-api.md](../planning/archive/phase-04-api.md) | HISTORICAL | 초기 API Phase 계획 | [ROADMAP.md](../ROADMAP.md)<br>[docs/06-api/api-overview.md](06-api/api-overview.md) | ARCHIVED |
| [planning/archive/phase-05-web-mvp.md](../planning/archive/phase-05-web-mvp.md) | HISTORICAL | 초기 Web MVP Phase 계획 | [planning/frontend-roadmap.md](../planning/frontend-roadmap.md)<br>[docs/DoD/Phase-08.md](DoD/Phase-08.md) | ARCHIVED |
| [planning/archive/phase-06-personalization.md](../planning/archive/phase-06-personalization.md) | HISTORICAL | 초기 개인화 Phase 계획 | [MASTER_ROADMAP.md](../MASTER_ROADMAP.md)<br>[docs/DoD/Phase-07.md](DoD/Phase-07.md) | ARCHIVED |
| [reports/evaluations/EVAL-001-ace-step-listening-evaluation.md](../reports/evaluations/EVAL-001-ace-step-listening-evaluation.md) | HISTORICAL | 품질·사용자 평가 이력 | — | KEEP |
| [reports/evaluations/EVAL-002-stem-separation-listening-evaluation.md](../reports/evaluations/EVAL-002-stem-separation-listening-evaluation.md) | HISTORICAL | 품질·사용자 평가 이력 | — | KEEP |
| [reports/evaluations/EVAL-003-seed-vc-listening-evaluation.md](../reports/evaluations/EVAL-003-seed-vc-listening-evaluation.md) | HISTORICAL | 품질·사용자 평가 이력 | — | KEEP |
| [reports/evaluations/EVAL-004-audio-mixing-listening-evaluation.md](../reports/evaluations/EVAL-004-audio-mixing-listening-evaluation.md) | HISTORICAL | 품질·사용자 평가 이력 | — | KEEP |
| [reports/evaluations/EVAL-005-lyrics-quality.md](../reports/evaluations/EVAL-005-lyrics-quality.md) | HISTORICAL | 품질·사용자 평가 이력 | — | KEEP |
| [reports/evaluations/EVAL-006-external-lyrics-llm.md](../reports/evaluations/EVAL-006-external-lyrics-llm.md) | HISTORICAL | 품질·사용자 평가 이력 | — | KEEP |
| [reports/evaluations/EVAL-007-kpop-dance-generation.md](../reports/evaluations/EVAL-007-kpop-dance-generation.md) | HISTORICAL | 품질·사용자 평가 이력 | — | KEEP |
| [reports/evaluations/EVAL-008-audio-analysis-validation.md](../reports/evaluations/EVAL-008-audio-analysis-validation.md) | HISTORICAL | 품질·사용자 평가 이력 | — | KEEP |
| [reports/experiments/EXP-001-ace-step-local-inference.md](../reports/experiments/EXP-001-ace-step-local-inference.md) | HISTORICAL | 실험 실행 이력 | — | KEEP |
| [reports/experiments/EXP-002-ace-step-quality-and-stability.md](../reports/experiments/EXP-002-ace-step-quality-and-stability.md) | HISTORICAL | 실험 실행 이력 | — | KEEP |
| [reports/experiments/EXP-003-stem-separation.md](../reports/experiments/EXP-003-stem-separation.md) | HISTORICAL | 실험 실행 이력 | — | KEEP |
| [reports/experiments/EXP-004-seed-vc.md](../reports/experiments/EXP-004-seed-vc.md) | HISTORICAL | 실험 실행 이력 | — | KEEP |
| [reports/experiments/EXP-005-pipeline-execution.md](../reports/experiments/EXP-005-pipeline-execution.md) | HISTORICAL | 실험 실행 이력 | — | KEEP |
| [reports/experiments/EXP-006-audio-mixing.md](../reports/experiments/EXP-006-audio-mixing.md) | HISTORICAL | 실험 실행 이력 | — | KEEP |
| [reports/experiments/EXP-007-lyrics-generation.md](../reports/experiments/EXP-007-lyrics-generation.md) | HISTORICAL | 실험 실행 이력 | — | KEEP |
| [reports/experiments/EXP-008-external-lyrics-llm.md](../reports/experiments/EXP-008-external-lyrics-llm.md) | HISTORICAL | 실험 실행 이력 | — | KEEP |
| [reports/quality-gates/QG-001-voice-conversion-operational-readiness.md](../reports/quality-gates/QG-001-voice-conversion-operational-readiness.md) | HISTORICAL | 운영 승격 Gate | — | KEEP |
| [reports/validation/VALIDATION-ARTIFACT-ACCESS-RECONCILIATION.md](../reports/validation/VALIDATION-ARTIFACT-ACCESS-RECONCILIATION.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-ARTIFACT-RESOURCE-API.md](../reports/validation/VALIDATION-ARTIFACT-RESOURCE-API.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-ARTIFACT-STORAGE-CATALOG-0016-APPLICATION.md](../reports/validation/VALIDATION-ARTIFACT-STORAGE-CATALOG-0016-APPLICATION.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-ARTIFACT-STORAGE-CATALOG.md](../reports/validation/VALIDATION-ARTIFACT-STORAGE-CATALOG.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-ARTIFACT-STORAGE-CONTRACT.md](../reports/validation/VALIDATION-ARTIFACT-STORAGE-CONTRACT.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-ARTIFACT-STORAGE-RESOLVER.md](../reports/validation/VALIDATION-ARTIFACT-STORAGE-RESOLVER.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-ARTIFACT-TRUSTED-INGESTION.md](../reports/validation/VALIDATION-ARTIFACT-TRUSTED-INGESTION.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-ASSET-API.md](../reports/validation/VALIDATION-ASSET-API.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-ASSET-CURSOR-INDEXES.md](../reports/validation/VALIDATION-ASSET-CURSOR-INDEXES.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-ASSETVERSION-API.md](../reports/validation/VALIDATION-ASSETVERSION-API.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-BOOTSTRAP-REVISION-0016.md](../reports/validation/VALIDATION-BOOTSTRAP-REVISION-0016.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-BOOTSTRAP-REVISION-0017.md](../reports/validation/VALIDATION-BOOTSTRAP-REVISION-0017.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-COMPOSITION-SNAPSHOT-API.md](../reports/validation/VALIDATION-COMPOSITION-SNAPSHOT-API.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-COMPOSITION-SNAPSHOT-FOUNDATION.md](../reports/validation/VALIDATION-COMPOSITION-SNAPSHOT-FOUNDATION.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-CURSOR-PAGINATION.md](../reports/validation/VALIDATION-CURSOR-PAGINATION.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-FRONTEND-DEPENDENCY-BASELINE.md](../reports/validation/VALIDATION-FRONTEND-DEPENDENCY-BASELINE.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-PROJECT-ASSET-API.md](../reports/validation/VALIDATION-PROJECT-ASSET-API.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-PROJECT-ASSET-CURSOR.md](../reports/validation/VALIDATION-PROJECT-ASSET-CURSOR.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-PROJECT-ASSET-KEYSET-INDEX-APPLICATION.md](../reports/validation/VALIDATION-PROJECT-ASSET-KEYSET-INDEX-APPLICATION.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-SQLITE-MIGRATION-SAFETY.md](../reports/validation/VALIDATION-SQLITE-MIGRATION-SAFETY.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-VOICE-ENROLLMENT.md](../reports/validation/VALIDATION-VOICE-ENROLLMENT.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-ALEMBIC-MIGRATION.md](../reports/validation/VALIDATION-WORKSPACE-ALEMBIC-MIGRATION.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-API-FOUNDATION.md](../reports/validation/VALIDATION-WORKSPACE-API-FOUNDATION.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-CODE-BASELINE.md](../reports/validation/VALIDATION-WORKSPACE-CODE-BASELINE.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-DB-MIGRATION-PREFLIGHT.md](../reports/validation/VALIDATION-WORKSPACE-DB-MIGRATION-PREFLIGHT.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-JOB-COMPLETION-UOW.md](../reports/validation/VALIDATION-WORKSPACE-JOB-COMPLETION-UOW.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-JOB-CURSOR-FOUNDATION.md](../reports/validation/VALIDATION-WORKSPACE-JOB-CURSOR-FOUNDATION.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-JOB-FOUNDATION-CONTRACT.md](../reports/validation/VALIDATION-WORKSPACE-JOB-FOUNDATION-CONTRACT.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-JOB-RESOURCE-API.md](../reports/validation/VALIDATION-WORKSPACE-JOB-RESOURCE-API.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-JOB-SCHEMA-MIGRATION.md](../reports/validation/VALIDATION-WORKSPACE-JOB-SCHEMA-MIGRATION.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-JOB-SERVICE-FOUNDATION.md](../reports/validation/VALIDATION-WORKSPACE-JOB-SERVICE-FOUNDATION.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-JOB-WORKER-FOUNDATION.md](../reports/validation/VALIDATION-WORKSPACE-JOB-WORKER-FOUNDATION.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-KEYSET-INDEXES.md](../reports/validation/VALIDATION-WORKSPACE-KEYSET-INDEXES.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-PROJECT-API.md](../reports/validation/VALIDATION-WORKSPACE-PROJECT-API.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-REPOSITORIES.md](../reports/validation/VALIDATION-WORKSPACE-REPOSITORIES.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |
| [reports/validation/VALIDATION-WORKSPACE-SERVICES.md](../reports/validation/VALIDATION-WORKSPACE-SERVICES.md) | HISTORICAL | 구현 검증 증거 | — | KEEP |

### SUPERSEDED

| Document | Classification | Authority Scope | Replaced By | Recommended Action |
|---|---|---|---|---|
| [docs/00-overview/goals-and-non-goals.md](00-overview/goals-and-non-goals.md) | SUPERSEDED | 이전 목표·비목표 안내 | [docs/02-product/ai-native-daw-product-direction.md](02-product/ai-native-daw-product-direction.md) | DEPRECATED |
| [docs/00-overview/project-overview.md](00-overview/project-overview.md) | SUPERSEDED | 이전 프로젝트 개요 안내 | [docs/02-product/ai-native-daw-product-direction.md](02-product/ai-native-daw-product-direction.md) | DEPRECATED |
| [docs/02-requirements/mvp-scope.md](02-requirements/mvp-scope.md) | SUPERSEDED | 기능·품질 요구사항 | [docs/02-product/ai-native-daw-product-direction.md](02-product/ai-native-daw-product-direction.md)<br>[docs/DoD/Phase-08.md](DoD/Phase-08.md) | DEPRECATE |
| [docs/03-architecture/history-management.md](03-architecture/history-management.md) | SUPERSEDED | 이전 Generation History 안내 | [docs/06-api/history-project-api.md](06-api/history-project-api.md) | DEPRECATED |
| [docs/03-architecture/project-management.md](03-architecture/project-management.md) | SUPERSEDED | 이전 Project Management 안내 | [docs/06-api/history-project-api.md](06-api/history-project-api.md) | DEPRECATED |

### STALE

현재 STALE 분류 문서는 **0개**다. 이번 Cleanup에서 기존 5개 Frontend 초안을 구현과 대조한 뒤 `docs/archive/frontend/`로 이동하고 HISTORICAL로 재분류했다.

## 4. Validation / Reports

- [실험 기록](../reports/experiments): 실제 모델·Pipeline 실행 조건과 결과
- [평가 기록](../reports/evaluations): 자동·사용자 품질 평가와 미평가 항목
- [Validation 기록](../reports/validation): 코드·API·DB·Frontend 검증 증거
- [Quality Gate](../reports/quality-gates): 운영 승격 전 판정
- `reports/*-template.md`: 새 보고서 작성 형식이며 검증 완료 증거가 아님

HISTORICAL 분류는 오래됐다는 이유로 무효라는 뜻이 아니다. 해당 시점의 결정과 재현 가능한 검증 증거로 보존하며 CURRENT 상태는 README·Roadmap·Canonical Architecture에서 다시 확인한다.

## 5. Authority 충돌 처리

1. CURRENT 주장은 실제 `develop` 코드·API·DB와 Validation을 우선한다.
2. 제품 목표는 Product Authority, 연결 구조는 Architecture Authority, 실행 순서는 ROADMAP을 우선한다.
3. ADR은 결정 당시 이유를 보존한다. 최신 결정이 대체하면 상태와 후속 ADR 링크를 갱신한다.
4. 실험·평가·Validation 결과를 최신 구현 상태로 확대 해석하지 않는다.
5. Common Contract 명칭은 DohaStudio `.github` authority를 재정의하지 않는다.
6. 모순을 발견하면 문서만 조용히 맞추지 않고 [Cleanup Plan](DOCUMENT_CLEANUP_PLAN.md)에 위험과 후속 작업을 기록한다.
