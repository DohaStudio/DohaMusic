# DohaMusic 실행 로드맵

> DohaVocal `0.2.0` consumer DTO·trust gate·transient payload acquisition foundation은 구현되었습니다. 다음 순서는 Consumer PR review/merge → `DURABLE_LOCATOR_REQUIRED` authoritative 재분석 → PayloadLocator persistence 판단이며, downloader orchestration과 Artifact ingestion은 아직 계획 단계입니다.
>
> 문서 역할: 현재 실행 순서와 NEXT/LATER
> 장기 기준: [MASTER_ROADMAP](MASTER_ROADMAP.md)

## Phase 6.5 후속 게이트

1. 사용자의 별도 승인과 API Key·비용 승인을 모두 받은 opt-in 환경에서만 한국어 발라드·시티팝·구조 유지 수정·영문 팝을 실제 측정한다. 승인 전 상태는 `[유료 실측 미수행]`이다.
2. EVAL-006에서 Template/External 결과를 사용자가 블라인드 평가한다.
3. OpenAI 데이터 보존·ZDR/DPA·상업 이용·생성물 권리의 법률·보안 검토를 완료한다.
4. 5초를 넘는 운영 호출은 비동기 Job으로 전환하고 인증·소유권·사용량 한도를 설계한다.
5. 위 게이트 전에는 External Provider를 Stable로 승격하거나 Pipeline에 자동 연결하지 않는다.
6. DohaLM의 versioned REST/Streaming·manifest 또는 Python SDK 계약을 확정하고 `DohaLMLyricsAdapter`·가사 버전·사용자 승인·직접 작성 fallback을 검증한다.
7. DohaLM 상업용 release는 기반 모델·가중치·학습 및 파인튜닝 데이터·Adapter·Runtime 계보가 `commercial_approved`일 때만 후보로 등록한다.

## Phase 6.6~6.9 Local Lyrics LLM 후속 확장

1. Phase 6.6에서 권리 확보 text Dataset·manifest·version·split을 승인한다.
2. Phase 6.7에서 Qwen 계열 1.7B~4B Instruct와 동급 공개 후보의 license·한국어·8GB 실행성을 비교하고 QLoRA SFT를 검증한다.
3. Phase 6.8에서 결과를 기존 `LyricsGenerator` 계약의 `LocalLyricsLLMAdapter`로 격리한다.
4. Phase 6.9에서 Validator·한국어 품질·응답 시간·peak VRAM·실패율·사용자 blind 평가를 통과해야 운영 승격을 검토한다.
5. 모든 게이트 전까지 Base 미선정·Dataset 미구축·학습 미착수·Adapter 미구현 상태이며 기본 Provider는 `template`이다.

## AI Provider 저장소 분리 Track

[저장소 분리 Roadmap](planning/repository-separation-roadmap.md)에 따라 책임 경계와 Runtime 이전을 분리한다.

1. Phase A `[완료]`: 책임, Provider 계약 범위, Dataset·Artifact 정책, Model Manifest와 ADR을 문서화하고 PR #50 병합 근거를 확인했다.
2. Phase B `[진행 중]`: DohaVocal `0.1.0` 호환과 `0.2.0` payload Result DTO·trust gate·transient acquisition, DohaMusic-owned Trusted Payload locator/issuer/resolver Foundation을 구현했고 [Worker Reconciliation Contract](docs/03-architecture/dohavocal-worker-reconciliation-contract.md), [Worker Re-entry Lifecycle](docs/03-architecture/workspace-worker-reentry-lifecycle.md)과 [Durable Execution Handoff Analysis](docs/03-architecture/durable-execution-handoff-analysis.md)을 확정했다. locator 전 새 handoff storage는 불필요하며 reclaim runtime, concrete Vocal Worker wiring·인증·downloader orchestration·durable locator·Completion adapter·실제 model·Artifact payload 통합은 남아 있다.
3. Phase C `[계획]`: ACE-Step·Demucs·Seed-VC Runner를 순차 이전하고 로컬 `Path`를 Artifact ID·URI 계약으로 전환한다.
4. Phase D `[계획]`: 전환 검증이 끝난 내부 Runner와 구형 Adapter만 제거하고 운영 계약 version과 DoD를 확정한다.

DohaVocal `0.1.0` Fake Runtime 호환과 DohaMusic `0.2.0` Consumer DTO·capability negotiation·config 기반 transient binary HTTP acquisition·Result trust gate는 구현했다. 실제 Worker 연결, 인증, durable locator, Artifact payload·AssetVersion commit, DohaAudio Runtime과 공통 Model Registry는 구현하지 않았다.

DohaVocal은 `0.2.0` payload-backed Runtime contract를 제공하고 DohaMusic은 transient acquisition adapter 기반을 구현했다. 실제 Workspace Artifact locator·ingestion, DohaAudio Runtime API와 공통 Model Registry는 구현하지 않았다.

## AI-native DAW Product Track

[AI-native DAW 제품 방향](docs/02-product/ai-native-daw-product-direction.md)과 [Frontend 전환 계획](planning/ai-native-daw-frontend-migration.md)에 따라 현재 Responsive Studio MVP를 장기 제품 Runtime으로 단계적으로 전환한다.

1. D0 `[완료]`: PR #94로 CURRENT/TARGET/NOT IMPLEMENTED, 공통 계약 재사용과 제품 객체 후보를 `develop`에 정합화했다.
2. D1·D2 `[완료]`: Composition Read의 Workspace 권위와 Project 상세 연결, 읽기 전용 Timeline·Track lane·단일 Mix playback·실제 media duration·Playhead·Master/Mix Waveform·seek·scroll·zoom·keyboard 기반을 완료했다. 실제 DB 승인은 별도 유지한다.
3. D3 `[진행 중]`: ADR-040의 mutable WorkingComposition·canonical Track/Clip, ADR-045의 Track 삭제·trusted duration과 ADR-047의 revision-safe replay 권위를 확정했다. 5개 persistence table, nullable Artifact duration, versioned idempotency completion result와 Repository·trusted WAV/FLAC probe 기반을 구현했으며 mutation Service·API·Clip UI는 미구현이다. D4 Mixer·독립 Export는 `[계획]`이다.
4. D5~D7 `[계획]`: AI Music Director·Candidate A/B, Reference Panel, Composition Evaluation/QA를 연결한다.
5. D8~D9 `[계획]`: 명시적 opt-in Learning Review Hub와 운영 전환을 검증한다.

Clip Persistence·Authority와 Revision-safe Idempotency Foundation은 Backend ORM·Repository·Alembic `20260825_0022`, trusted WAV·FLAC duration, Track active Clip count와 완료 revision·복수 identity replay를 격리 회귀로 검증했다. Frontend·Product API·Provider·Training·Dataset·GPU·Common Contract는 변경하지 않았고 편집 가능한 Track/Clip Waveform·Clip UI·Section·Mixer·range selection은 구현하지 않았다. Phase 8 `100%`는 로컬 MVP 판정이며 이 Track의 완료율이 아니다.

> 문서 상태: [운영 중]
> 최종 수정일: 2026-08-25
> 현재 상태: **Responsive Studio MVP 완료 / AI-native DAW D0 완료·D1 계약 확정·D1~D9 구현 계획 / 외부 Provider Runtime 보류**
> 상위 기준: [Master Roadmap](MASTER_ROADMAP.md)
> 완료 기준: [Phase별 Definition of Done](docs/DoD/README.md)

이 문서는 현재 실행 순서와 가까운 다음 작업만 요약한다. 전체 Phase의 목표·포함·제외·선행 조건·산출물·진행률은 `MASTER_ROADMAP.md`, 세부 완료 판정은 해당 DoD를 따른다. 같은 설명을 여러 문서에 복제하지 않는다.

## 현재 Phase 현황

| Phase | 상태 | 현재 판정 | DoD |
|---|---|---|---|
| 0. 프로젝트 문서화 | [완료] | 초기 설계·정책·문서 체계 구축 | Master Phase 0 |
| 1. Legacy Backend Foundation | [완료] | FastAPI·DB·Mock Job E2E; Workspace Job Foundation과 분리 | [Phase-01](docs/DoD/Phase-01.md) |
| 2. Music Generation | [진행 중] | ACE-Step 조건부 채택, 기본 `mock`, 운영 Provider 미확정·EVAL-001 진행 중 | [Phase-02](docs/DoD/Phase-02.md) |
| 2.5 Quality Benchmark | [진행 중] | 재현성·반복·운영 수명 검증 완료, EVAL-001 사용자 평가 진행 중 | [Phase-02.5](docs/DoD/Phase-02.5.md) |
| 3. Stem Separation | [완료] | HTDemucs Adapter·API·Benchmark·EVAL 양식 | [Phase-03](docs/DoD/Phase-03.md) |
| 4. Voice Conversion | [검증 필요] | Provider 평가 완료, Primary·Fallback 미선정, 94% 유지 | [Phase-04](docs/DoD/Phase-04.md) |
| 5. Pipeline Integration | [완료] | Mock Voice 기반 Orchestrator·실제 Audio Mixer·API·Benchmark 검증 | [Phase-05](docs/DoD/Phase-05.md) |
| 6. Lyrics AI | [완료] | Template·Mock Generator·동기 API·검증·EXP/EVAL/ADR 완료 | [Phase-06](docs/DoD/Phase-06.md) |
| 6.5 DohaLM Lyrics Integration | [계획] | 별도 Provider 경계·승인 정책 문서화, API/SDK·Adapter·DB·Pipeline 미구현 | [DohaLM 연동](docs/03-architecture/dohalm-integration.md) |
| 6.6~6.9 Local Lyrics LLM | [계획] | Dataset·QLoRA·Adapter·Quality Gate 미착수 | [Roadmap](planning/local-lyrics-llm-roadmap.md) |
| 7. Doha Voice | [계획] | Dataset·개인화 학습 미착수 | [Phase-07](docs/DoD/Phase-07.md) |
| 8. Doha Studio | [완료] | 100%: 로컬 단일 사용자 Responsive Studio MVP의 Voice·History·Project·WAV Player/Download·Cancel·Retry 완료 | [Phase-08](docs/DoD/Phase-08.md) |
| F6. Guided Voice Enrollment | [진행 중] | 구현·자동 Browser Validation 완료; 실제 사용자 마이크·실기기와 인증은 미검증 | [Validation Report](reports/validation/VALIDATION-VOICE-ENROLLMENT.md) |
| AI-native DAW Product | [진행 중] | D0·D1·D2와 Clip Persistence·Authority·Revision-safe Idempotency Foundation 완료; WorkingComposition Service/API/UI, 실제 DB 전환·Section·Mixer·D3 후속·D4~D9 미구현 | [AI-native DAW DoD](docs/DoD/AI-Native-DAW.md) |
| K0~K4. K-POP Creation Control | [진행 중] | K0·K1·K2·K3.0·K3.1·K3.2·K3.3 완료, K3.4 Preview Export 다음 구현 | [K-POP Roadmap](planning/kpop-creation-roadmap.md) |
| Workspace Artifact·Job Domain | [진행 중] | Job Service·Completion UoW·Worker 실행 기반·공식 API 5/5, 4개 Vocal Job 계약, Provider Job 1:N persistence, `0.1.0`/`0.2.0` Result trust gate·transient acquisition과 Trusted Payload resolver Foundation 구현; Provider dispatch wiring·downloader orchestration·durable locator·Completion adapter·실제 payload ingestion·background daemon과 나머지 API 미구현 | [Workspace Job Foundation](docs/03-architecture/workspace-job-foundation.md) |
| 9. Production | [계획] | 운영 인프라 미구현 | [Phase-09](docs/DoD/Phase-09.md) |
| AI Provider 저장소 분리 | [진행 중] | Phase A 완료; DohaVocal Runtime·Consumer Contract·HTTP Transport·metadata Result trust gate 구현, Worker wiring·실제 Artifact payload 통합·Phase C~D 미착수 | [DohaVocal Consumer Contract](docs/03-architecture/dohavocal-consumer-contract.md) |
| Reviewer Authentication Authority | [Foundation 구현 / OS adapter 미구현] | V1 `LOCAL_ONLY`, single owner/operator, `WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL` 선택과 provider-independent fail-closed contract 구현; 실제 credential·delegated assertion·mapping·ReviewerAuthority 미구현 | [Authority](docs/09-security/reviewer-authentication-deployment-authority.md) |

## 현재 우선 작업

**최우선 NEXT:** 구현된 Clip Persistence·Authority·Revision-safe Idempotency Foundation을 기반으로 WorkingComposition Service + Product API를 진행한다. 이후 Frontend move/trim/split/delete·Track reorder, Undo/Redo, Track/Clip Waveform, working preview/render, Mixer, AI Segment Editing 순서로 확장한다. MIDI·Piano Roll은 NOT IMPLEMENTED, SoundFont는 NOT INTEGRATED 상태의 별도 우선순위다. 실제 사용자 DB `0017 → 0022` 전환은 별도 승인 Gate로 유지하며, Workspace Job의 Provider dispatch wiring과 background daemon은 별도 Track이다.

1. [EVAL-005](reports/evaluations/EVAL-005-lyrics-quality.md)에서 실제 가사 초안의 주제 적합성·자연스러움·후렴 기억성·창작 활용성을 사용자가 평가한다.
2. 외부 Lyrics LLM 후보는 공식 API·라이선스·데이터 처리·비용·한국어 품질 근거를 확보한 뒤 별도 ADR로 검토한다.
3. DohaLM 전용 Lyrics API 또는 승인된 범용 계약, versioned manifest와 상업용 모델 계보를 확정한 뒤 Adapter·가사 승인·Pipeline snapshot을 구현한다.
4. [Local Lyrics LLM Roadmap](planning/local-lyrics-llm-roadmap.md)에 따라 DohaLM이 Phase 6.6 Dataset 권리·manifest를 먼저 확정하고 DohaMusic은 Provider 연동·승인 경계를 유지한다.
5. [EVAL-004](reports/evaluations/EVAL-004-audio-mixing-listening-evaluation.md)에서 실제 곡의 balance·자연스러움·noise·clipping을 사용자가 평가한다.
6. RVC 또는 상업 사용 가능한 zero-shot SVC 후보의 RTX 3060 Ti·라이선스·청취 게이트를 계속 검토한다.
7. [EVAL-003](reports/evaluations/EVAL-003-seed-vc-listening-evaluation.md), [EVAL-002](reports/evaluations/EVAL-002-stem-separation-listening-evaluation.md), [EVAL-001](reports/evaluations/EVAL-001-ace-step-listening-evaluation.md)을 완료한다.
8. Production 전 Pipeline 취소·복구·idempotency와 외부 Queue 요구사항을 정의한다.
9. [Frontend Roadmap](planning/frontend-roadmap.md)의 F5와 F6 Frontend Wizard·MediaRecorder·품질·대표 선택·복원, Windows/CI FFmpeg와 cleanup scheduler/crash recovery를 완료했다. F6 전체는 인증·실기기 평가가 남아 `[진행 중]`이며 기존 Phase 8 완료 상태와 분리한다.
10. Phase 2 후속 평가는 Korean Dance Pop을 대표 시나리오로 삼고 0.6B LM·120~128 BPM·60~90초·동일 Prompt·3개 이상 Seed 조건을 검증한다. Instrumental과 Korean Ballad는 보조 비교군으로 유지한다.
11. [K-POP Creation Roadmap](planning/kpop-creation-roadmap.md)의 K3.3 Hook Candidate까지 완료했다. 다음은 별도 PR의 K3.4 Preview Export이며 LoRA·Dataset·Voice 학습은 K4 이후로 유지한다.
12. [Workspace v1 API 계약](docs/06-api/workspace-rest-api-contract.md)은 Resource Endpoint 30개와 D1 product API 2개를 구현했다. Bootstrap CLI는 source `20260825_0022`의 D1 Table·PK·unique·same-Project FK·identity Index와 transition inventory를 검증하며 실제 사용자 DB는 `20260810_0017`로 유지하고 실제 Bootstrap은 실행하지 않았다. Job API는 5/5이며 Resource API 진행도는 30/64다.
13. [Asset 중심 목표 DB](docs/07-database/database-redesign-overview.md)는 source Workspace Entity 28개, 별도 `ArtifactStorageLocation`, Workspace Repository와 [Service 소유 transaction](docs/03-architecture/workspace-service-transaction.md)을 구현했다. `20260824_0020`은 Clip persistence 5개 table, `20260824_0021`은 nullable trusted Artifact duration, `20260825_0022`는 revision-safe idempotency completion result를 additive하게 추가한다. source metadata는 43개 Table이고 실제 사용자 DB는 `20260810_0017`의 36개 Table이다. 실제 Bootstrap·DB migration·data backfill·dual write·Provider dispatch wiring·background daemon·나머지 34개 Resource REST API·Frontend·Legacy 제거는 미구현이고 현재 14개 Runtime Table과 source of truth는 변경하지 않는다.
14. [완료] [Artifact Storage 계약](docs/03-architecture/artifact-storage-contract.md)과 [ADR-032](docs/11-decisions/ADR-032-artifact-storage-resolver-integrity.md)에서 `artifact://<artifact_id>`, 별도 Catalog, trusted ingestion, SHA-256·size·MIME 검증, immutable publish, owner/retention Application Gate와 [dry-run reconciliation](docs/10-operations/artifact-storage-reconciliation.md)을 구현했다. Content read는 매 요청 전체 SHA-256을 검증하며 scanner는 승인 namespace만 batch 조회하고 어떤 row·파일도 변경하지 않는다. Artifact Metadata·content·download API와 single-byte Range를 유지하며 Job API 추가 후 전체 Resource API는 30/64다. 다음은 별도 승인의 destructive maintenance이며 공개 Artifact 쓰기 API는 계약에 없다.
15. [DohaVocal Consumer Contract](docs/03-architecture/dohavocal-consumer-contract.md)은 4개 capability·version별 9/10 operation·`0.1.0` metadata-only와 `0.2.0` payload Result·acquisition을 검증한다. [Provider Result Ingestion Contract](docs/03-architecture/provider-result-ingestion-contract.md)은 두 version의 result를 검증하되 Artifact로 승격하지 않고, [Trusted Payload Locator / Resolver Contract](docs/03-architecture/trusted-payload-locator-resolver-contract.md)은 DohaMusic staging payload의 opaque locator 경계를 검증한다. [Durable Execution Handoff Analysis](docs/03-architecture/durable-execution-handoff-analysis.md)은 locator 전 새 handoff storage가 불필요하고 다음 dependency가 `DURABLE_LOCATOR_REQUIRED`임을 확정한다. 다음은 Consumer PR review/merge 후 locator authority 재분석이며 production downloader orchestration·durable locator·Completion adapter는 별도 후속이다.
16. [진행 중] AI-native DAW D1-A~D2와 D3 Clip Persistence·Authority Foundation을 완료했다. ADR-040의 persistence와 ADR-045의 Track 삭제·trusted duration 기반은 구현했지만 mutation Service·API·UI·canonical Section은 미구현이며 신규 `EditIntent`를 만들지 않았다.
17. [Foundation 구현 / OS adapter 미구현] [ADR-037](docs/11-decisions/ADR-037-reviewer-authentication-deployment-authority.md)의 historical no-selection과 [ADR-038](docs/11-decisions/ADR-038-v1-reviewer-authentication-product-decision.md)의 product authority를 보존했다. [ADR-042](docs/11-decisions/ADR-042-v1-local-operator-authentication-foundation.md)은 `WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL` mechanism, provider-independent contract, test-only Fake와 fail-closed bootstrap을 추가한다. DohaAudio delegated provider는 selected지만 양쪽 adapter·mapping·authority·approval은 미구현·0이다.

## F6 Guided Voice Enrollment 실행 순서 [진행 중]

1. [부분 완료] Backend PCM16 WAV 정규화와 FFmpeg optional Provider·미설치 오류 처리를 구현하고 Windows FFmpeg 8.1.2 및 Ubuntu·Windows CI 통합 검증을 추가했다. FFmpeg build 라이선스의 운영 배포 검토는 남아 있다.
2. [완료] [데이터 모델](docs/07-database/voice-enrollment-data-model.md)에 따라 `VoiceEnrollment`·`VoiceSample` additive migration과 기존 단일 Profile backfill을 구현했다.
3. [완료] 별도 Enrollment Storage·정규화 service와 [Enrollment API](docs/06-api/voice-enrollment-api.md)를 구현했다.
4. [완료] sample 기본 품질 검사, 24시간 sliding/7일 absolute 만료, idempotency, 즉시 cleanup primitive, 주기 scanner·retry와 시작 시 crash recovery를 구현했다.
5. [완료] 안내 문장·MediaRecorder·기존 WAV fallback·품질 확인·대표 Sample·Profile 등록 Wizard를 구현했다.
6. [완료] Frontend unit·component·Desktop/Mobile E2E와 실제 Backend 합성 WAV create/upload/submit 연결을 통과했다.
7. [완료] 실제 Chrome·Edge 채널, Playwright Firefox, Pixel 7·iPhone 14 에뮬레이션에서 upload·submit·경고·실패·멱등·만료·cancel과 합성 MediaRecorder Validation을 수행했다.
8. 개인 음성을 Git에 남기지 않는 사용자 동의 실제 마이크·Android/iOS/Safari·Bluetooth 수동 평가를 수행한다.

F6는 기존 Voice Conversion용 참조 음성 UX다. Phase 7의 장시간 Dataset·전사·split·preprocessing·LoRA·Fine Tuning과 자동 결합하지 않는다. 공개 운영의 인증·소유권·동의 철회·감사는 Phase 9 선행 조건이다.

## 다음 작업 흐름

```text
Phase 5.1: 실제 Audio Mixer 완료
  ↓
Phase 6: 로컬 Lyrics AI 기반 완료
  ↓ 선택적 후속 확장
Phase 6.6 Dataset → 6.7 QLoRA SFT → 6.8 Adapter → 6.9 Quality Gate
  ↓ 병행
Voice Primary·Mixer 청감 품질 게이트
  ↓
운영 Pipeline 승인
```

## 완료 처리 규칙

- 구현되지 않은 기능과 실행하지 않은 테스트는 완료로 표시하지 않는다.
- Phase 상태 변경 시 Master Roadmap, 해당 DoD, README와 CHANGELOG를 같은 작업에서 검토한다.
- AI 품질은 Codex가 추정하지 않고 EXP의 객관 지표와 EVAL의 사용자 평가를 분리한다.
- 일반 작업은 작업 브랜치 → `develop` PR로 병합하며 `main`은 명시적 안정화 요청에서만 변경한다.

미확정 세부 작업은 [백로그](planning/backlog.md), 주요 기술 결정은 [ADR 목록](docs/11-decisions/README.md), 실험 근거는 [reports](reports/)에서 추적한다.
