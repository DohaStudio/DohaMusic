# DohaVocal 0.2.0 Consumer E2E Foundation

> 상태: [구현·PR #194 이후 새-base 로컬 Gate 검증 완료] / production wiring [미구현]
> 최종 수정일: 2026-09-30
> 관련 계약: [Consumer](dohavocal-consumer-contract.md), [Locator](durable-payload-locator-authority.md), [Staging](verified-durable-staging-authority.md), [Completion](dohavocal-verified-staged-artifact-completion.md), [Rights](dohavocal-production-rights-domain.md)

이전 base의 storage 경합 차단은 PR #194에서 PATH_CANONICALIZATION_RACE로 재현·수정했다. 이 문서는 해당 fix를 보존한 새 develop에서 E2E 변경을 재적용한 상태다. 이전 blocked 실행과 새 검증 결과는 [검증 보고서](../10-operations/dohavocal-020-consumer-e2e-validation.md)에 분리 기록하며 과거 PASS 수치를 새 merge authority로 재사용하지 않는다.

## 기준선과 PR #130 판정

- Music 현재 복구 START develop: 83d63f8908a4efb35a62aba95824fca87879f860
- Music 이전 복구 START develop: 6717bcd6c6d2bc296c6a374a189669cfbabfa991
- Music 현재 START tree: 0b5f7765e3f833f33b9077b226034d576d33e804
- Music 이전 복구 START tree: ec3b8dd99fbc6285d2d41042eb4eb5ecb326c045
- Vocal fixture: e28320ef26a2dc49eaefdfa62bceea0c8c69e6ed (merged PR #7)
- Vocal tree: f5dc77e8db0d2d2caa051021662b94e7b969d223
- 판정: **SUPERSEDED_BY_CURRENT_DEVELOP_E2E**

PR #130 head 764e718a7d4f420e416c9f36a2cac814e5b5e528와 START develop의
divergence는 현재 develop-only 62 / PR-only 5 commits다. 17개 변경 파일을 검토했다.
현재 develop에는 DTO, HTTP acquisition, durable locator, verified staging과 #159
Completion이 있지만 #130의 reconciliation service·tests·전용 문서는 없다.
일부 현행 요약 문서는 acquisition을 완료로 기록해 코드와 불일치했다.

#130의 service·실패/replay 테스트는 재사용하되 payload ordinal과 취득 중 current authority
확인을 보강했다. composition root는 현행 factory에 맞춰 최소 조립한다. 오래된 README,
ROADMAP, table count와 Completion 미구현 표현은 복사하지 않는다. old branch의 merge/rebase,
force push, PR close 또는 branch 삭제는 하지 않는다. #193/#171은 변경하지 않는다.

선행 #93/#99/#101/#102/#106/#110/#113/#124/#125/#126/#156/#159/#160/#161/#192는
모두 MERGED임을 확인했다. 현재 코드와 merged ADR-048/049/051/074/075가 authority이며
역사적 PR 본문은 현재 구현을 대체하지 않는다.

## 실행 경로

explicit 0.2 capability selection + matching manifest → authorized CreateJob →
GetJobStatus/GetResult → ProviderResultIngestionService + persisted ProviderJobBinding →
ordered PayloadLocator(source_bound) → fixed-origin GetPayloadContent + bounded verification →
PayloadStagingService + actual media inspection → verified_staged →
existing Artifact Completion (test-only current rights) →
Artifact/JobOutput/ModelUsage + ingested locator + succeeded Job.

기본 get_capabilities()와 request mapping은 0.1.0을 유지한다. 0.2 request만 explicit
capability query와 manifest version/capability preflight를 요구한다. unsupported version,
downgrade 광고 또는 manifest mismatch는 CreateJob 전에 fail closed한다. arbitrary query/URL은
transport 입력으로 허용하지 않으며 version selector는 GET capabilities에서만 사용한다.

generation은 Provider와 기존 계약대로 첫 resolved input version을 source/parent로 사용한다.
다른 세 capability의 exact source/parent/chain 검증은 유지한다. Provider payload role과
Workspace output role은 기존 canonical mapping을 유지한다.

## Acquisition과 byte authority

VocalPayloadReconciliationService는 trusted candidate·locator ID·current authority callback을
받는다. Job/binding/artifact/role/source/ordinal/expected facts를 대조한 뒤 취득한다.
Provider URL이나 staging path를 caller에게 받지 않는다. fixed configured origin,
redirect 금지, identity Content-Encoding, 최대 size와 bounded 64 KiB read를 적용한다.
chunk 사이 current claim/cancel/rights를 재확인하며 종료된 response는 닫는다.

HTTP transport가 실제 bytes의 SHA-256·size와 Content-Type을 검증하고, staging이 WAV/FLAC/JSON
실제 형식과 checksum/size를 독립 재검증한다. metadata descriptor checksum은 byte authority가
아니다. verified facts로 expected facts를 덮어쓰지 않는다.

취득 실패는 source_bound를 유지하고 output을 생성하지 않는다. 취소/rights/revocation/revision
변경은 staging/CAS 전에 차단한다. 재시도는 같은 immutable source를 명시적으로 재취득하며
자동 RetryJob·backoff는 없다. verified_staged re-entry는 network 없이 open_verified로 검증한다.

## Completion·transaction 범위

판정: **COMPLETION_E2E_IN_SCOPE** (격리 fixture만).

기존 Completion service, Artifact ingestion, Session-aware current rights port를 재사용한다.
test-only Fake rights는 tests/support에만 있고 factory나 운영 권한의 fallback이 아니다.
Provider I/O와 filesystem I/O는 열린 DB transaction 밖이며 trust는 caller Session을 사용한다.
기존 Completion-owned final transaction이 repository에 동일 Session을 전달해
Artifact/선택적 AssetVersion/JobOutput/ModelUsage/locator/Job을 원자 확정한다.
Repository commit/rollback, rights schema, final receipt port 또는 production writer 변경은 없다.

기존 Asset selection과 source는 유지한다. replay는 output identity를 재사용한다.
생성/변환/보정은 canonical audio target, 분석은 exact source Version의 JSON Artifact다.
Manifest의 REVIEW_REQUIRED는 그대로 보존하며 운영 사용 허가로 승격하지 않는다.

## 재현과 CI

Python 3.12 환경에서 Vocal repository를 위 exact SHA로 clean checkout한 뒤
DOHAVOCAL_E2E_SOURCE를 해당 checkout으로 지정하고 실행한다:

    python -m pytest -q backend/tests/test_dohavocal_runtime_e2e.py backend/tests/test_dohavocal_stream_guards.py backend/tests/test_vocal_payload_reconciliation.py

fixture는 SHA와 tracked clean 상태를 확인하고 실제 create_app을 ASGI TestClient로 실행한다.
Music production code는 Vocal package/store를 import하지 않는다. static response replay만으로
E2E를 주장하지 않는다. HTTP-compatible in-process 경로이며 실제 network E2E는 미수행이다.
source 설정이 없으면 명시적 SKIP이고 PASS로 세지 않는다. backend-ubuntu CI는 public Vocal
repository를 고정 SHA로 별도 checkout하고 설정을 제공한다. 모델·binary fixture는 vendor하지 않는다.

## 상태와 제외

- 0.1.0 metadata-only: 호환 유지.
- 0.2.0 Fake Runtime → verified bytes → Music Completion: 격리 E2E 범위.
- Public API·schema·migration: 변경 없음; source Alembic 0037 / metadata 67 tables.
- Production durable Provider Runtime·authentication·rights adapter/writer: 미구현.
- Worker dispatch/polling/daemon·실제 model/GPU/user audio·Training/Evaluation: 범위 밖.
- Provider Fake bytes/Result는 process-local이며 restart durability를 보장하지 않는다.
- 실제 사용자 DB와 Production Artifact는 접근하지 않는다.
- 이번 Foundation은 Production-ready가 아니다.

정상 병합 이후 다음 권장 작업 하나는 **Production Provider Result/source persistence foundation**이다.
현재 process-local identity를 restart에도 보존하는 prerequisite이며 이번 PR에서는 구현하지 않는다.
