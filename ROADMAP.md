# DohaMusic 실행 로드맵

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

1. Phase A `[진행 중]`: 책임, Provider 계약 범위, Dataset·Artifact 정책, Model Manifest와 ADR을 문서화하고 `develop` 병합을 검증한다.
2. Phase B `[계획]`: 신규 Music Generator는 DohaAudio, 신규 Singing Voice·Voice Conversion은 DohaVocal에서 구현하고 DohaMusic에는 Provider Client를 둔다.
3. Phase C `[계획]`: ACE-Step·Demucs·Seed-VC Runner를 순차 이전하고 로컬 `Path`를 Artifact ID·URI 계약으로 전환한다.
4. Phase D `[계획]`: 전환 검증이 끝난 내부 Runner와 구형 Adapter만 제거하고 운영 계약 version과 DoD를 확정한다.

현재는 문서 경계만 제안한다. DohaAudio·DohaVocal 저장소는 존재하지만 Runtime API, Provider HTTP API, Artifact URI와 공통 Model Registry는 구현하지 않는다.

> 문서 상태: [운영 중]
> 최종 수정일: 2026-08-10
> 현재 상태: **Phase 6 Template·Mock 기반 완료 / DohaLM 연동·Local Lyrics LLM 계획 0% / 외부 LLM·운영 Voice Provider 보류**
> 상위 기준: [Master Roadmap](MASTER_ROADMAP.md)
> 완료 기준: [Phase별 Definition of Done](docs/DoD/README.md)

이 문서는 현재 실행 순서와 가까운 다음 작업만 요약한다. 전체 Phase의 목표·포함·제외·선행 조건·산출물·진행률은 `MASTER_ROADMAP.md`, 세부 완료 판정은 해당 DoD를 따른다. 같은 설명을 여러 문서에 복제하지 않는다.

## 현재 Phase 현황

| Phase | 상태 | 현재 판정 | DoD |
|---|---|---|---|
| 0. 프로젝트 문서화 | [완료] | 초기 설계·정책·문서 체계 구축 | Master Phase 0 |
| 1. Backend Foundation | [완료] | FastAPI·DB·Mock Job E2E | [Phase-01](docs/DoD/Phase-01.md) |
| 2. Music Generation | [진행 중] | ACE-Step 조건부 채택, 기본 `mock`, 운영 Provider 미확정·EVAL-001 진행 중 | [Phase-02](docs/DoD/Phase-02.md) |
| 2.5 Quality Benchmark | [진행 중] | 재현성·반복·운영 수명 검증 완료, EVAL-001 사용자 평가 진행 중 | [Phase-02.5](docs/DoD/Phase-02.5.md) |
| 3. Stem Separation | [완료] | HTDemucs Adapter·API·Benchmark·EVAL 양식 | [Phase-03](docs/DoD/Phase-03.md) |
| 4. Voice Conversion | [검증 필요] | Provider 평가 완료, Primary·Fallback 미선정, 94% 유지 | [Phase-04](docs/DoD/Phase-04.md) |
| 5. Pipeline Integration | [완료] | Mock Voice 기반 Orchestrator·실제 Audio Mixer·API·Benchmark 검증 | [Phase-05](docs/DoD/Phase-05.md) |
| 6. Lyrics AI | [완료] | Template·Mock Generator·동기 API·검증·EXP/EVAL/ADR 완료 | [Phase-06](docs/DoD/Phase-06.md) |
| 6.5 DohaLM Lyrics Integration | [계획] | 별도 Provider 경계·승인 정책 문서화, API/SDK·Adapter·DB·Pipeline 미구현 | [DohaLM 연동](docs/03-architecture/dohalm-integration.md) |
| 6.6~6.9 Local Lyrics LLM | [계획] | Dataset·QLoRA·Adapter·Quality Gate 미착수 | [Roadmap](planning/local-lyrics-llm-roadmap.md) |
| 7. Doha Voice | [계획] | Dataset·개인화 학습 미착수 | [Phase-07](docs/DoD/Phase-07.md) |
| 8. Doha Studio | [완료] | 100%: 로컬 단일 사용자 Voice·History·Project·WAV Player/Download·Cancel·Retry 완료 | [Phase-08](docs/DoD/Phase-08.md) |
| F6. Guided Voice Enrollment | [진행 중] | 구현·자동 Browser Validation 완료; 실제 사용자 마이크·실기기와 인증은 미검증 | [Validation Report](reports/validation/VALIDATION-VOICE-ENROLLMENT.md) |
| K0~K4. K-POP Creation Control | [진행 중] | K0·K1·K2·K3.0·K3.1·K3.2·K3.3 완료, K3.4 Preview Export 다음 구현 | [K-POP Roadmap](planning/kpop-creation-roadmap.md) |
| Workspace Artifact Domain | [진행 중] | Entity·Repository·Service, 실제 DB 0012~0016, Catalog·local Resolver·Trusted Ingestion과 Resource API 19개 완료; Catalog row 0개, owner/retention·full orphan worker·나머지 45개 API·운영 Artifact 폴더·Runtime 미구현 | [Artifact Storage 계약](docs/03-architecture/artifact-storage-contract.md) |
| 9. Production | [계획] | 운영 인프라 미구현 | [Phase-09](docs/DoD/Phase-09.md) |
| AI Provider 저장소 분리 | [진행 중] | Phase A 문서화 진행, Phase B~D 미착수 | [Provider Separation DoD](docs/DoD/Provider-Separation.md) |

## 현재 우선 작업

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
12. [Workspace v1 API 계약](docs/06-api/workspace-rest-api-contract.md)은 공통 Router·응답 Schema·request ID·오류 분기, [명시적 Bootstrap 도구](docs/06-api/workspace-api-foundation-bootstrap.md), [HMAC Cursor Pagination](docs/06-api/cursor-pagination.md)과 Workspace·MusicProject·ProjectAsset·Asset·AssetVersion Resource Endpoint 19개를 구현했다. AssetVersion은 Asset 소유권을 확인하고 새 row를 단조 증가 번호로 추가하며 전체 계보를 최신순으로 조회한다. PATCH·DELETE와 기존 Version 덮어쓰기는 제공하지 않는다. Resource API 진행도는 19/64다.
13. [Asset 중심 목표 DB](docs/07-database/database-redesign-overview.md)는 21개 SQLAlchemy 2.0 Workspace Entity, 별도 `ArtifactStorageLocation`, additive revision `20260806_0012`~`20260809_0016`, Workspace Repository와 [Service 소유 transaction](docs/03-architecture/workspace-service-transaction.md)까지 구현했다. 실제 사용자 DB도 `20260809_0016`·36개 Application Table이며 Catalog row는 0개다. Catalog·local Resolver·Trusted Ingestion을 구현했지만 실제 Bootstrap·backfill·dual write·나머지 45개 Resource REST API·Frontend·Legacy 제거는 미구현이고 현재 14개 Runtime Table과 source of truth는 변경하지 않는다.
14. [완료] [Artifact Storage 계약](docs/03-architecture/artifact-storage-contract.md)과 [ADR-032](docs/11-decisions/ADR-032-artifact-storage-resolver-integrity.md)에서 `artifact://<artifact_id>`, 별도 Catalog, trusted ingestion, SHA-256·size·MIME 검증과 immutable publish 경계를 구현했다. `DOHA_ARTIFACT_STAGING_ROOT`는 기본 미설정 fail-closed이며 Artifact·Catalog는 같은 transaction에 등록한다. 다음은 owner/retention Application Service와 full orphan reconciliation이며 Resource API는 19/64, Artifact API는 0/3을 유지한다.
15. 신규 Music Generator는 DohaAudio, 신규 Vocal 기능은 DohaVocal에서 시작하고 기존 subprocess Runner는 단계적 이전 전까지 호환 계층으로 유지한다.

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
