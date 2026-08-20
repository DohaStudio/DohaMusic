# AI Provider 저장소 분리 Definition of Done

> 상태: [진행 중]
> 현재 단계: Phase B — New Implementation Separation 진행 중
> 최종 수정일: 2026-08-19
> 관련 문서: [전환 로드맵](../../planning/repository-separation-roadmap.md), [책임 경계](../03-architecture/repository-provider-boundaries.md), [ADR-028](../11-decisions/ADR-028-provider-runtime-artifact-contract.md)

## Phase A 완료 조건

- [x] DohaMusic·DohaLM·DohaAudio·DohaVocal 책임이 구분됐다.
- [x] DohaAudio 계획과 DohaVocal Fake Runtime·Consumer Foundation/Production 미구현 상태가 구분됐다.
- [x] 신규 Music·Vocal 구현 위치와 기존 호환 Runner 정책이 정해졌다.
- [x] Dataset·Artifact와 Model Manifest 최소 계약이 문서화됐다.
- [x] Provider 직접 호출 금지와 DohaMusic GPU admission control 원칙이 기록됐다.
- [x] 단계적 전환 Roadmap과 ADR이 작성됐다.
- [x] Markdown 상대 링크·Mermaid·fence·ADR 번호 검증이 완료됐다.
- [x] CHANGELOG 기록과 한국어 커밋이 완료됐다.
- [x] 원격 작업 브랜치 Push와 `develop` 대상 PR #50 검토가 완료됐다.
- [x] PR #50의 `develop` 병합 후 원격 상태가 검증됐다.
- [x] PR #50 병합 시 `main` 무변경이 확인됐다.

## Phase B 완료 조건 — [진행 중]

- [x] DohaAudio·DohaVocal 저장소와 소유권 정책이 검증됐다.
- [ ] 신규 Music Generator가 DohaAudio에서 구현됐다.
- [ ] 실제 신규 Vocal model 기능이 DohaVocal에서 구현됐다. Fake Runtime Foundation만 구현됐다.
- [x] DohaMusic Vocal Provider Client와 JSON fixture 계약 회귀가 검증됐다.
- [ ] Provider별 Manifest·라이선스·보안·CI가 검증됐다.

## Phase C 완료 조건 — [계획]

- [ ] ACE-Step·Demucs·Seed-VC가 Provider별로 순차 이전됐다.
- [ ] Artifact ID·URI 계약과 무결성 검증이 적용됐다.
- [ ] Job·취소·재시도·오류·Health·version 계약이 검증됐다.
- [ ] GPU admission control과 실패 복구가 통합 검증됐다.

## Phase D 완료 조건 — [계획]

- [ ] 이전 완료된 내부 Runner와 구형 Adapter가 제거됐다.
- [ ] 운영 계약 version과 rollback·호환 종료 절차가 확정됐다.
- [ ] 운영 문서, 관련 Phase DoD와 CHANGELOG가 갱신됐다.

문서 작성만으로 Phase B~D 또는 Provider Runtime 구현을 완료 처리하지 않는다.
