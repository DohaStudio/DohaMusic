# AI Provider 저장소 분리 로드맵

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-19
> 관련 기능: DohaLM·DohaAudio·DohaVocal 책임 분리와 Runtime 전환
> 관련 문서: [책임 경계](../docs/03-architecture/repository-provider-boundaries.md), [DoD](../docs/DoD/Provider-Separation.md), [ADR-028](../docs/11-decisions/ADR-028-provider-runtime-artifact-contract.md)

저장소 책임 확정, 신규 구현 분리, 기존 Runtime 이전과 Legacy 제거를 서로 다른 단계로 수행한다. 각 단계는 이전 단계의 계약과 검증 증거를 충족한 뒤 진행하며 Big-bang migration을 하지 않는다.

## Phase A — Boundary Definition [완료]

- [x] 저장소별 책임 경계 정의
- [x] Provider 계약의 필수 범위 정의
- [x] 로컬 Dataset·Artifact 정책 정의
- [x] Model Manifest 최소 계약 정의
- [x] Provider Runtime과 Artifact 계약 ADR 작성
- [x] `develop` 대상 PR #50 검토와 병합
- [x] PR #50 병합 후 링크·상태·원격 `develop` 검증

Phase A는 문서와 계약 방향을 확정했다. DohaVocal은 이후 Fake Runtime과 DohaMusic Consumer Contract·HTTP Transport Foundation을 구현했지만 실제 model·Worker wiring·인증·Artifact 통합과 운영 Provider 승격은 포함하지 않는다.

## Phase B — New Implementation Separation [진행 중]

- 신규 Music Generator를 DohaAudio에서 구현한다.
- 신규 Singing Voice·Voice Conversion을 DohaVocal에서 구현한다.
- DohaMusic에는 versioned Provider Client를 추가한다.
- 기존 ACE-Step·Demucs·Seed-VC subprocess Adapter를 호환 계층으로 유지한다.
- Provider별 CI·보안·라이선스·Model Manifest 검증을 추가한다.

## Phase C — Runtime Migration [계획]

- ACE-Step Runner를 DohaAudio로 순차 이전한다.
- Demucs Runner를 DohaAudio로 순차 이전한다.
- Seed-VC Runner를 DohaVocal로 순차 이전한다.
- 로컬 `Path` 계약을 Artifact ID 또는 URI 계약으로 변경한다.
- 작업 생성·상태·취소·재시도·오류·Health 계약을 검증한다.
- 단일 GPU 환경의 admission control과 모델 로드·해제를 통합 검증한다.

각 Runner는 새 Runtime의 동등성·실패·취소·복구·성능 검증을 통과한 뒤 개별적으로 전환한다.

## Phase D — Legacy Removal [계획]

- DohaMusic 내부의 이전 완료 Runner를 제거한다.
- 구형 subprocess Adapter와 미사용 설정을 제거한다.
- Provider API·Manifest·Artifact 계약 version을 운영 기준으로 고정한다.
- 운영·보안·배포 문서와 해당 Phase DoD를 갱신한다.
- rollback과 이전 version 호환 종료 절차를 검증한다.

Legacy 제거는 모든 Provider를 동시에 수행하지 않는다. Provider별 전환 완료와 rollback 가능성을 확인한 뒤 별도 작업으로 진행한다.

## 착수 순서 원칙

책임 경계는 신규 모델 구현 전에 적용한다. 따라서 다음 Music Generator는 DohaAudio에서 시작하며, 기존 DohaMusic Runner의 이전 완료를 선행 조건으로 두지 않는다. Runtime API 상세와 Artifact 저장 기술은 Phase B 착수 전 별도 검증·ADR 갱신으로 확정한다.
