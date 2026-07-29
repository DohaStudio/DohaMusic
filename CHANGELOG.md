# 변경 이력

> 문서 목적: 사용자와 개발자에게 의미 있는 저장소 변경을 기록한다.
> 현재 상태: **운영 중**
> 최종 수정일: 2026-07-29

DohaMusic 프로젝트의 주요 변경 사항을 기록한다. 일반 작업은 `[Unreleased]`에 기록하고 프로젝트 버전 정책은 구현 단계에서 결정한다.

## [Unreleased]

### 추가

- Seed-VC, OpenVoice, CosyVoice, Fish Speech, RVC, Amphion Vevo2의 공식 근거 비교표와 100점 Provider Score를 추가했다.
- Primary 미선정, RVC Secondary 평가 후보, Seed-VC·Vevo2 Experimental 결정을 기록한 ADR-011을 추가했다.

- Voice Provider 수명주기와 승격 조건을 정의한 ADR-010, Provider 정책, Voice Conversion 운영 준비도 QG-001을 추가했다.

- `VoiceConverter`, `MockVoiceConverter`, 격리형 `SeedVCAdapter`와 `mock`·`seed_vc` Provider Factory를 추가했다.
- 비동기 Voice Conversion API, `voice_conversion_jobs/files`, `VOICE_CONVERTING`, Alembic migration을 추가했다.
- Seed-VC 44k F0 runner, 3회 GPU Benchmark, opt-in GPU 통합 테스트와 48kHz stereo PCM16 자동 검증을 추가했다.
- EXP-004, 사용자 EVAL-003 양식, Seed-VC 검증 Provider 결정을 기록한 ADR-009를 추가했다.

- 프로젝트 전체 Phase·실제 진행률·선행 조건·산출물·다음 작업을 관리하는 `MASTER_ROADMAP.md`를 추가했다.
- Phase 1~9의 완료 판정과 공통 Git·문서 게이트를 관리하는 `docs/DoD/` 문서 체계를 추가했다.

- `StemSeparator` 인터페이스, `MockStemSeparator`, 격리형 `DemucsAdapter`, `mock`·`demucs` Provider Factory를 추가했다.
- 비동기 Stem 생성·조회·파일 조회 API와 `stem_jobs`, `stem_files`, `STEM_SEPARATING` 상태를 추가했다.
- HTDemucs 오프라인 단독 실행기, 3회 Benchmark, opt-in GPU Backend E2E 및 자동 오디오 검증을 추가했다.
- EXP-003, EVAL-002, Stem Provider·2-stem·48kHz Stereo float32 결정을 기록한 ADR-008을 추가했다.

- ACE-Step 동일·다른 Seed, 상주 반복, 0.6B LM을 명시 실행하는 benchmark suite와 결과 집계·WAV sample 비교 도구를 추가했다.
- 실제 음원을 사용자가 직접 평가하는 EVAL-001과 재현성·안정성·운영 결정을 기록한 EXP-002를 추가했다.
- ACE-Step 기본 Provider 채택 보류 ADR-006과 Job별 subprocess 유지 ADR-007을 추가했다.
- ACE-Step 1.5 v0.1.8을 격리된 런타임에서 실행하는 선택적 Adapter, Provider Factory, 오류 체계를 추가했다.
- 단독 instrumental·한국어 가사 smoke 실행기, 고정 benchmark 입력, WAV 신호 분석기와 opt-in GPU 통합 테스트를 추가했다.
- RTX 3060 Ti 8GB 실측과 Backend 종단 간 연결 결과를 기록한 `EXP-001` 보고서를 추가했다.
- FastAPI Router·Service·Repository 계층과 교체 가능한 의존성으로 Backend Foundation을 구축했다.
- SQLite·SQLAlchemy·Alembic 기반 `generation_jobs`, `generated_files`, `voice_profiles` schema를 추가했다.
- Mock `MusicGenerator`, ThreadPool Worker, 로컬 Storage와 생성·조회·음성 프로필 API를 추가했다.
- 생성 성공·조회·Mock Worker 실패·입력 예외·음성 동의·migration·Storage를 검증하는 테스트를 추가했다.

### 변경

- Voice Provider Matrix를 `Primary 미선정 → Fallback 미선정 → Experimental → Mock`으로 정리하고 Experimental의 자동 fallback 참여를 금지했다.
- Phase 4를 Provider 평가 완료·Primary 미선정인 `[검증 필요]` 94%로 유지하고 Phase 5 착수를 계속 보류했다.

- Seed-VC를 `Experimental`·운영 보류로 확정하고 기본 Provider `mock`을 유지했다.
- Phase 4는 EVAL-003과 clipping·라이선스 해제 조건이 남아 `[검증 필요]` 94%로 유지하고 Phase 5 착수를 보류했다.

- 생성·Stem·Voice Worker가 동일한 GPU 동시성 1 executor를 공유하도록 확장했다.
- Phase 4를 기술 구현 완료·사용자 품질 평가 대기인 `[검증 필요]` 94%로 갱신했다.

- 새 기능 작업은 Master Roadmap, 해당 Phase DoD, AGENTS 지침 순으로 확인하고 완료 후 진행률·DoD·README·ROADMAP·CHANGELOG를 함께 갱신하도록 운영 규칙을 확장했다.

- AI 작업은 생성 Worker와 Stem Worker가 GPU 동시성 1인 공유 ThreadPool을 사용하도록 조립했다.
- 개발 상태를 Phase 3 Stem Separation 기술 검증 완료·사용자 청취 평가 대기로 갱신했다.

- 반복 실험 결과에 따라 현재 ACE-Step 운영 방식을 Job별 격리 subprocess로 확정하고 Mock 기본 Provider를 유지했다.
- 개발 단계를 Phase 2.5 기술 검증 완료·사용자 청취 평가 진행 중으로 갱신했다.
- `MusicGenerator` 결과 계약에 Provider·모델 버전·실제 Seed·추론 시간·최대 VRAM·메타데이터를 포함했다.
- Mock 전용 Worker를 Provider-neutral Worker로 확장하고 설정으로 `mock` 또는 `ace_step`을 선택하도록 변경했다.
- 개발 단계를 Phase 2 진행 중으로 갱신하고 기술 검증과 수동 청취 평가 상태를 분리했다.

### 수정

### 제거

### 보안

- 신규 Voice Provider 검증 전에 checkpoint 출처·hash·역직렬화·원격 코드·의존성 lock과 학습 산출물 삭제 정책을 확인하도록 공급망 통제를 보강했다.

- Seed-VC 상용 SaaS와 Docker·온프레미스 외부 배포는 배포 단위별 GPL 준수 목록과 법률 검토 전까지 보류하도록 명시했다.

- Voice Conversion 입력을 DB의 vocals Stem과 명시적 동의 Voice Profile로 제한하고 참조 경로가 `voices/references` 밖으로 벗어나면 거부한다.

### 문서

- README, Master Roadmap, ROADMAP, Voice Model, Architecture, Operations, Security와 ADR 목록을 Phase 4.6 선정 결과에 맞게 최신화했다.

- EXP-004 기존 결과를 재실험 없이 재집계해 시간·VRAM·RMS·peak·파일 크기·hash와 clipping 원인·미확정 경계를 기록했다.
- EVAL-003의 사용자 평가표·체크리스트·기준을 보강하고 점수와 최종 청취 판정은 비워 두었다.
- README, Master Roadmap, ROADMAP, Model, Evaluation, Operations, Security와 ADR을 Phase 4.5 운영 품질 게이트 결정에 맞게 최신화했다.

- Seed-VC·OpenVoice·CosyVoice·Fish Speech의 공식 용도와 라이선스, archive 위험, RTX 3060 Ti 실측을 연구·모델·Architecture·API·DB·평가·운영 문서에 반영했다.

- README와 ROADMAP을 Master Roadmap·DoD에 연결하고 기존 Phase 4 이후 명칭을 Voice Conversion → Pipeline → Lyrics AI → Doha Voice → Doha Studio → Production 체계로 통합했다.

- Demucs·HTDemucs·MDX-Net·Open-Unmix 비교, Demucs 코드·가중치 MIT 확인, RTX 3060 Ti 실측을 조사·모델·Architecture·API·DB·평가·운영 문서에 반영했다.

- 동일 Seed PCM 재현성, 다른 Seed 파형 차이, 상주 CPU 메모리 증가, 0.6B LM 성능과 사용자 평가 상태를 관련 모델·아키텍처·운영 문서에 반영했다.
- ACE-Step 공식 출처·라이선스·격리 설치·저 VRAM 설정·성능·평가·오류·운영 문서와 ADR-005를 최신화했다.
- DohaMusic 초기 설계, 요구사항, 아키텍처, 데이터, API, 평가, 보안, 운영 문서 체계
- 단계별 계획과 실험 보고서 템플릿
- 저장소 전체에 적용되는 Codex Git 작업 지침과 문서 최신화·변경 이력 관리 규칙
- 장기 유지보수를 위한 구현 전 분석, 재사용, Adapter, 비동기 작업, 테스트·로그·성능 기록과 코드 품질 원칙
- README, Backend·Worker·Storage Architecture, API, ERD, 상태 모델과 로컬 운영 문서를 실제 Mock 구현에 맞게 갱신했다.
- ADR-002의 Adapter 경계와 ADR-003의 Phase 1 비동기 처리 결정을 구현 기준으로 검토·승인했다.
