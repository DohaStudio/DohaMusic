# DohaVocal Completion Contract Reconciliation

- 날짜: 2026-09-17
- 대상: PR #156, OPEN / Draft 유지; Ready 및 PR merge 금지
- 최초 head: `60c95f066c77418518d45082b42629fdafee6254`
- authority: `develop@e7a7dfb1c8859f198c4ded17f59f3d1376d2a77d`
- main: `63633d462043ad3ba78fee92473d19e90c361431`
- #157 merge: `9a4bcb0b617125a1f6842ab0007d90f7d6cb4abd`
- #158 merge: `e7a7dfb1c8859f198c4ded17f59f3d1376d2a77d`
- 계약: [ADR-074](../../docs/11-decisions/ADR-074-dohavocal-verified-staged-artifact-completion-authority.md), [Completion architecture](../../docs/03-architecture/dohavocal-verified-staged-artifact-completion.md)

## Authority audit

| 변경 | 분류 | 판정 |
|---|---|---|
| #157 Run/Candidate/ProviderExecution/Public API/Mock Worker | A: Vocal 결정과 무관 | 별도 Music Director domain |
| #157 JSON adopted registration 추가 | C: 공통 구현 경계 추가 | caller-owned Session, JSON-only; 기존 prepare/register/verify/finalize/compensate 유지 |
| #157 publisher proposal identity 추가 | B: terminology 명확화 | 공통 infrastructure와 domain-specific identity/ledger 분리 |
| #157 materialization publish/registration recovery | B: lifecycle 명확화 | physical publication과 최종 DB transaction 구분 유지 |
| #157 migrations 0033~0035 | B: 최신 context | Music Director schema; Vocal 추가 schema 필요 없음 |
| #157 WAV demuxer 명시 | A | Export/preview format 처리; Vocal output authority 변경 아님 |
| #158 Candidate APPLY | A | Run/WorkingComposition 이중 CAS 계약; Asset selection writer 이전 없음 |

D(기존 결정 무효)는 발견하지 않았다. generation 새 Vocal Asset/version 1, conversion/correction exact source Asset의 다음 Version, analysis exact source Version의 JSON-only 결과를 유지한다.

검토 source는 `artifact_ingestion_service.py`, `artifact_publisher.py`, `music_director_materialization_service.py`, `job_completion_service.py`, Export Completion/trusted registration, Asset/AssetVersion/ProjectAsset 및 Job/JobOutput/ModelUsage 모델·repository, PayloadLocator 모델·repository·service, verified staging, Provider Result gate다. 최신 develop 변경 비교에서 generic Completion, Asset/locator/staging 핵심 및 Export-specific authority는 바뀌지 않았다.

Completion service가 caller-owned Session의 최종 DB transaction을 소유하고 locator CAS와 Job `finish_owned_claim()`을 함께 확정한다는 계약은 유효하다. 해당 Job CAS는 running/exact worker/token/cancel gate이며 lease eligibility와 최신 rights는 final authority port가 별도로 검사한다. `PayloadLocatorService.mark_ingested()`의 독립 transaction을 완료 경로에서 호출하지 않는다.

`AssetService.select_asset_version()`은 명시적 selection writer다. source/target tombstone은 replay identity lookup에서 포함할 수 있지만 신규 생성과 current output access를 승인하지 않는다. 성공 replay는 ingested/cleanup_pending/cleaned에서 staging 없이 검증하고 conflicting aggregate는 fail closed한다.

session-consistent concrete Vocal rights adapter, path-free stream prepare 및 Vocal 전용 Completion은 develop에서 미구현이다. 계약으로 확정된 후속 boundary를 implemented로 표시하지 않는다. Export ledger/trusted registration을 Vocal authority로 확대하지 않는다.

## Protected stacked PR evidence

- #159: `6aca1b6f832f7db09a7c91d5eb1b3608ae289b89`, OPEN / Draft, base는 #156 branch; read-only.
- #159 source의 stream prepare, final Session authority, locator CAS/Job terminal CAS, tombstone-aware replay는 계약 구현 가능성 참고 증거다. 해당 구현과 테스트를 merged develop 결과로 간주하지 않는다.
- #159의 base integration 충돌/ADR reference 정합화 및 재검증은 별도 후속 작업이다. 본 작업에서 코드·push·base·Ready·merge mutation은 0이다.
- #130: `764e718a7d4f420e416c9f36a2cac814e5b5e528`, OPEN / Draft; acquisition 책임 및 모든 PR mutation 0.

## Validation scope

- `python -m alembic -c backend/alembic.ini heads`: `20260911_0035 (head)`, single head.
- 최종 diff 기준은 최초 PR head가 아니라 위 latest develop다. develop에서 통합된 production/test/migration 변경은 #156 production 변경으로 계산하지 않는다.
- strict UTF-8, changed-document relative links, Markdown fence, ADR duplicate, repository old Vocal ADR-069 filename reference, conflict markers, changed-document secret/local-path pattern 및 `git diff --check` 검사.
- historical CHANGELOG/validation을 현재 상태로 재작성하지 않았다. 번호 정합화는 현행 Vocal reference만 대상으로 했다.
- regression 결과는 아래 완료 기록을 따른다. 전체 suite와 실제 Provider/사용자 DB/운영 Artifact 접근은 수행하지 않는다.

## 완료 기록

기존 `test_verified_payload_staging.py`, `test_payload_locator_persistence.py`, `test_workspace_job_completion_uow.py`, `test_trusted_adopted_artifact_registration.py`, `test_export_job_completion_uow.py`를 최신 develop 통합 branch에서 실행했다: **72 passed, 1 skipped (49.77s)**. 전체 suite PASS 주장이나 #159 구현 테스트 결과가 아니다.

초기 static 검사: 변경 문서 17개, 상대 링크 806개 검증 PASS; 중복 ADR 번호 0, repository old Vocal filename reference 0, UTF-8/fence/marker/secret-local-path pattern 오류 0. 완료 report 및 공통 ingestion 문구 추가 뒤 최종 static 검사를 재실행한다. 실제 credential 탐지 전용 scanner나 외부 Mermaid renderer 결과를 주장하지 않는다.
