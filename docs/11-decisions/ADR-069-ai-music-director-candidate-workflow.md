# ADR-069 - AI Music Director Candidate Workflow Authority

> 상태: 승인
> 작성일: 2026-09-11
> 최종 수정일: 2026-09-11
> 관련 기능: AI-native DAW D5 AI Music Director와 Candidate Workflow
> 관련 문서: [AI-native DAW 목표 아키텍처](../03-architecture/ai-native-daw-target-architecture.md), [Frontend 전환 계획](../../planning/ai-native-daw-frontend-migration.md), [Workspace Job Foundation](../03-architecture/workspace-job-foundation.md), [WorkingComposition Service](../03-architecture/working-composition-service.md), [Workspace Artifact 모델](../03-architecture/workspace-artifact-model.md), [ADR-040](ADR-040-canonical-track-clip-working-composition-authority.md)

## 배경과 문제

D5는 사용자의 지시와 Composition 문맥을 Provider-neutral Job으로 실행하고 여러 Candidate를 비교한 뒤 명시적으로 선택·적용하는 흐름이다. Provider 결과가 mutable WorkingComposition을 직접 변경하거나 실행 시점의 live state를 다시 읽으면 재현성, idempotency와 persistent history authority가 깨진다.

현재 `JobOutput`은 ordered AssetVersion 또는 Artifact를 가리킬 수 있지만 Candidate stable identity, proposal metadata, 선택과 적용의 분리, stale apply CAS를 표현하지 못한다. 따라서 generic output order만으로 D5 제품 authority를 만들지 않는다.

## 결정

### 1. Canonical input과 TimelineSelection

`CompositionSnapshot`이 D5 Job의 필수 immutable input이다. Job 생성 뒤 Worker와 Provider는 live `WorkingComposition`을 canonical execution input으로 읽지 않는다.

`TimelineSelection`은 versioned immutable value object로 `Job.settings_snapshot`의 MusicIntent 안에 저장한다. 첫 Foundation은 `scope="composition"`만 실행하며 전체 Snapshot을 대상으로 한다. 향후 `scope="time_range"`는 `start_us`, `end_us`, 선택적 canonical `track_ids`와 `clip_ids`를 사용할 수 있지만 별도 validation과 UI Gate 전에는 거부한다. Section identity는 요구하지 않는다.

### 2. MusicIntent

MusicIntent는 Provider parameter bag이 아니라 다음 bounded product-domain contract다.

- `schema_version`
- `action`: 첫 Foundation에서 승인된 action enum
- `instruction`: 길이가 제한된 사용자 지시
- `selection`: versioned TimelineSelection
- `preserve`: 보존할 musical/lineage constraints
- `replace`: 변경을 허용한 대상 범위
- `constraints`: duration/style/mood/energy 등 승인된 typed fields
- `candidate_count`: `1..4`, 기본값 `2`

임의 모델 argument, checkpoint path, FFmpeg flag와 Provider-specific JSON은 public MusicIntent에 넣지 않는다. MusicIntent는 Job의 immutable `settings_snapshot`에 canonical JSON으로 보존하며 별도 intent table을 만들지 않는다.

### 3. Job과 idempotency

새 Workspace Job type은 `music_director`다. 기존 generation Job은 Snapshot, multi-candidate proposal과 apply lifecycle의 IO contract가 달라 재사용하지 않는다.

필수 Job authority는 Project, `composition_snapshot_id`, MusicIntent와 optional approved Provider/model selection이다. 가짜 `JobInput`은 만들지 않으며 첫 Foundation의 AssetVersion input 수는 0이다.

fingerprint는 API contract version, Project ID, Snapshot ID, canonical MusicIntent 전체, candidate count, 명시된 Provider/model identity를 포함한다. 같은 Idempotency-Key와 같은 fingerprint는 같은 Job/run/candidates를 replay하고 다른 fingerprint는 conflict다. 새 명시 요청은 새 key와 새 Job을 만든다.

### 4. Candidate grouping과 persistence

Additive `MusicDirectorRun`과 `MusicDirectorCandidate` entity가 필요하다.

`MusicDirectorRun`은 Job과 1:1이며 source Snapshot, intent schema version, selected candidate, applied candidate와 apply result revision을 소유한다. `MusicDirectorCandidate`는 stable UUID, run/job scope, unique ordinal, Candidate AssetVersion, proposal Artifact, optional preview Artifact, Provider/model provenance와 immutable proposal digest를 소유한다.

Candidate 하나는 canonical composition이 아니라 immutable composition mutation proposal과 비교 가능한 preview의 logical grouping이다. Candidate별 Project-owned candidate Asset 하나와 최초 immutable AssetVersion 하나를 사용하고 proposal JSON Artifact와 optional audio preview Artifact를 같은 AssetVersion에 연결한다. `JobOutput`은 Candidate AssetVersion을 ordinal 순서로 index하지만 Candidate product authority를 대체하지 않는다.

proposal JSON은 source Snapshot ID와 bounded operation schema/version을 포함하며 executable code, raw path, arbitrary command를 포함할 수 없다. Preview와 proposal payload는 기존 Artifact storage, integrity, retention, content/download authority를 재사용한다.

### 5. Lifecycle, selection과 apply

Candidate persisted state는 `generated`, `rejected`, `applied`만 둔다. 현재 선택은 `MusicDirectorRun.selected_candidate_id`로 표현하므로 candidate row에 중복 selected state를 두지 않는다. 첫 Foundation은 자동 expiration과 destructive cleanup을 추가하지 않는다.

`SELECT`는 비교 UI의 명시적이고 변경 가능한 선택이며 canonical composition을 변경하지 않는다. `APPLY`는 별도 confirmation과 Idempotency-Key를 요구하는 final mutation action이다.

Provider, Worker, candidate persistence와 SELECT 단계의 canonical WorkingComposition mutation count는 0이다.

APPLY는 다음을 하나의 application-owned transaction으로 수행한다.

1. effective owner, Project, run, Candidate와 source Snapshot scope 검증
2. run이 미적용 상태인지 CAS 검증
3. current WorkingComposition의 `base_snapshot_id`가 source Snapshot과 같은지 검증
4. request `expected_revision`과 aggregate revision 검증
5. proposal digest와 bounded operations 재검증
6. 기존 WorkingComposition command/history primitive를 통해 operations 적용
7. aggregate revision과 persistent history를 한 번의 logical apply authority로 기록
8. run의 applied candidate와 result revision 확정

직접 ORM row update, automatic rebase와 silent last-write-wins는 금지한다. base Snapshot 또는 revision이 달라지면 `STALE_CANDIDATE`로 fail closed한다. 같은 apply key의 response-loss replay는 같은 result revision을 반환하며 다른 Candidate 또는 fingerprint는 conflict다.

### 6. Provider boundary와 transport

DohaMusic domain은 `MusicDirectorProvider` port만 사용한다. 최소 operation은 submit, poll/read terminal result, cancel, result normalization이다. Provider output은 항상 untrusted input으로 검증한다.

Mock provider는 Foundation의 deterministic execution, failure, cancellation과 malformed output 검증에 필수다. DohaLM은 향후 adapter 후보지만 현재 전용 D5 endpoint, SDK와 model manifest 계약이 확정되지 않았으므로 production prerequisite가 아니다. Provider credential이나 내부 model argument는 Frontend에 노출하지 않는다.

Frontend transport는 기존 Job polling을 재사용한다. SSE는 D5 Foundation에 필요하지 않으며 official Provider streaming UX 요구와 reconnect contract가 확정될 때 재검토한다.

### 7. API boundary

Generic Job create를 arbitrary `music_director` payload entrypoint로 넓히지 않는다. bounded Project-scoped Music Director endpoints가 Job Service를 내부 재사용한다.

- create run/Job
- read run과 ordered candidates
- select candidate
- apply selected candidate
- existing Job detail/cancel/retry read authority 재사용

Candidate read는 safe Artifact ID와 authorized content target만 제공한다. Apply endpoint는 Idempotency-Key와 `expected_revision`을 필수로 받고 stale apply를 409 domain conflict로 매핑한다.

### 8. Transactions, recovery와 concurrency

Candidate persistence transaction은 current claim과 cancellation을 확인한 뒤 run, ordered candidates, Asset/AssetVersion, trusted Artifacts, JobOutputs와 Job success를 함께 확정한다. rollback은 partial DB authority를 남기지 않으며 durable payload는 existing reconciliation policy를 따른다.

Selection transaction은 run version/CAS로 selected pointer만 변경한다. Apply transaction은 WorkingComposition mutation/history와 applied pointer/result revision을 함께 확정한다.

Provider response loss와 candidate persistence retry는 같은 Job/run/candidate identities로 수렴한다. apply response loss는 같은 revision을 replay한다. 같은 Candidate double apply는 한 번만 mutation한다. 다른 Candidate의 concurrent apply, stale client, Job 실행 중 composition advance는 하나만 CAS에 성공하거나 모두 stale로 거부된다. 서로 다른 Job은 독립 Candidate set을 가질 수 있지만 같은 current composition에 대한 apply는 aggregate revision guard를 공유한다.

### 9. Cancellation, failure와 retention

Cancellation은 Provider submit 전, 실행 중, persistence 전과 persistence 후 apply 전을 구분한다. Cancelled Job은 Candidate를 자동 적용하지 않는다. 이미 durable하게 persisted된 Candidate는 audit/replay를 위해 보존하되 적용할 수 있는지는 run/Job 상태와 stale guard가 결정한다.

Typed failure groups은 invalid intent, unsupported selection, provider unavailable/failed, malformed candidate, artifact ingestion failure, stale candidate, apply conflict다. raw Provider response, stack trace, credential과 filesystem path를 public error에 저장하지 않는다.

Rejected/unselected Candidate와 Artifact는 첫 Foundation에서 durable하게 유지한다. retention/expiration과 physical cleanup은 usage evidence와 정책을 갖춘 별도 작업으로 연기한다.

### 10. Authorization, security와 observability

모든 operation은 기존 effective-owner/Workspace/Project scope를 재사용한다. Candidate ID만으로 다른 Project의 Snapshot, AssetVersion 또는 Artifact를 조회·적용할 수 없다.

Provider output은 allowed Project/Snapshot lineage, schema, operation allowlist, size와 integrity를 검증한다. Worker는 canonical composition을 변경할 권한이 없다.

최소 structured events는 Job created, Provider submitted, candidates persisted, candidate selected, candidate applied와 typed failure다. 사용자 instruction 전문, credential, raw Provider payload와 storage locator는 로그에 남기지 않는다.

## Schema와 migration

`CANDIDATE_ENTITY_REQUIRED`를 선택한다. `JobOutput`과 `settings_snapshot`만으로 selected/applied authority와 stale/double-apply CAS를 안전하게 표현할 수 없다.

이 결정은 additive `20260911_0033` Run/Candidate schema, `0034` ProviderExecution identity와 `0035` Candidate materialization ledger로 구현됐다. Public API/Read/SELECT 단계의 추가 migration은 0이다.

## 구현 순서와 Gate

1. Candidate domain/schema/repository: 구현·검증 완료
2. Job create와 deterministic Mock provider Worker: 구현·검증 완료
3. Candidate Artifact/AssetVersion persistence와 replay: 구현·검증 완료
4. SELECT: 구현·검증 완료. Atomic APPLY transaction은 후속 작업
5. Frontend Candidate panel과 accessibility: `AI_MUSIC_DIRECTOR_FRONTEND_PASS`
6. Browser E2E, recovery/concurrency와 required CI: `AI_MUSIC_DIRECTOR_FOUNDATION_PASS`

각 slice는 MusicIntent validation, frozen Snapshot input, idempotency, bounded candidate cardinality, Provider failure, cancellation, Artifact lineage, response-loss replay, explicit apply, stale/double/concurrent apply, rollback, Frontend state와 Browser E2E를 해당 범위에서 증명한다.

## 제외 범위

- autonomous conversational agent와 long-term memory
- continuous learning과 recommendation memory
- Composition Evaluation/QA
- billing과 multi-agent orchestration
- production Provider certification
- Section entity와 visual range selection
- destructive Candidate cleanup

## 재검토 조건

- official DohaLM D5 contract가 streaming-only semantics를 요구할 때
- Candidate가 bounded proposal이 아닌 full composition branch/merge를 요구할 때
- visual range/Section authority가 canonical selection contract로 승격될 때
- Candidate retention 또는 storage cost가 운영 한계를 넘을 때
