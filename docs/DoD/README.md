# Definition of Done 운영 기준

> 문서 상태: [운영 기준]
> 최종 수정일: 2026-08-20
> 관련 문서: [Master Roadmap](../../MASTER_ROADMAP.md), [작업 지침](../../AGENTS.md), [실행 로드맵](../../ROADMAP.md)

DoD는 각 Phase를 완료로 선언하기 위한 검증 가능한 체크리스트다. `[x]`는 저장소의 구현·테스트·문서·Git 이력으로 확인된 항목, `[ ]`는 미구현·미검증·사용자 입력 대기 항목이다. 새 작업은 해당 Phase 문서의 미완료 항목을 작업 범위로 가져오며, 완료 증거 없이 체크하지 않는다.

## 진행률 계산

```text
진행률 = 완료 판정 항목 수 / 전체 판정 항목 수 × 100
```

소수점은 가장 가까운 정수로 반올림한다. 안내 문장과 하위 설명은 분모에 포함하지 않는다. 체크 항목을 추가·삭제하면 `MASTER_ROADMAP.md` 진행률도 같은 커밋에서 갱신한다.

## 모든 Phase의 공통 완료 기준

- [ ] 요청 범위의 기능 또는 문서 완료
- [ ] 성공·실패·예외·회귀 검증 검토 및 가능한 테스트 통과
- [ ] 필요한 Benchmark와 성능 기록
- [ ] README·ROADMAP·관련 전문 문서 최신화
- [ ] CHANGELOG `[Unreleased]` 기록
- [ ] ADR 작성·수정 필요 여부 검토
- [ ] AI 실험 수행 시 EXP와 사용자 품질 판단용 EVAL 작성
- [ ] 비밀·개인 음성·생성 오디오·모델 가중치가 Git에 없음을 확인
- [ ] 한국어 커밋
- [ ] 원격 작업 브랜치 Push
- [ ] `develop` 대상 PR 생성 및 검토
- [ ] `develop` 병합과 병합 후 검증
- [ ] `main` 변경 없음

공통 항목은 각 Phase 문서에서 해당 작업의 실제 이력에 맞춰 다시 체크한다. 계획 Phase는 이전 Phase에서 공통 인프라가 존재하더라도 해당 Phase 작업으로 검증하기 전까지 `[ ]`로 둔다.

## Phase별 문서

| Phase | 문서 | 현재 상태 |
|---|---|---|
| 1. Legacy Backend Foundation | [Phase-01](Phase-01.md) | [완료] |
| 2. Music Generation | [Phase-02](Phase-02.md) | [진행 중] |
| 2.5 Quality Benchmark | [Phase-02.5](Phase-02.5.md) | [진행 중] |
| 3. Stem Separation | [Phase-03](Phase-03.md) | [완료] |
| 4. Voice Conversion | [Phase-04](Phase-04.md) | [검증 필요] |
| 5. Pipeline Integration | [Phase-05](Phase-05.md) | [완료] |
| 6. Lyrics AI | [Phase-06](Phase-06.md) | [완료] |
| 7. Doha Voice | [Phase-07](Phase-07.md) | [계획] |
| 8. Doha Studio | [Phase-08](Phase-08.md) | [완료] |
| 9. Production | [Phase-09](Phase-09.md) | [계획] |
| AI Provider 저장소 분리 Track | [Provider-Separation](Provider-Separation.md) | [진행 중] |
| AI-native DAW Product Track | [AI-Native-DAW](AI-Native-DAW.md) | [진행 중] |

Phase 0은 코드 개발 이전 문서 기반 확립 단계이며 [Master Roadmap의 Phase 0](../../MASTER_ROADMAP.md#phase-0-프로젝트-문서화--완료)에서 완료 근거를 관리한다.

Phase 8 후속 [F6 Guided Voice Enrollment](../../planning/frontend-roadmap.md#f6--guided-voice-enrollment-진행-중)은 별도 개선 Track이다. 기존 Phase 8의 `15/15, 100%` 분모와 완료 상태를 변경하지 않으며 F6 체크리스트는 Frontend Roadmap에서 독립적으로 관리한다. Phase 7 개인화 Dataset·학습 DoD와도 분리한다.

[AI Provider 저장소 분리](Provider-Separation.md)도 기존 Phase 진행률을 변경하지 않는 독립 Track이다. DohaVocal Fake Runtime·Consumer Contract Foundation 완료는 Production transport·실제 Vocal model·Artifact 통합 또는 DohaAudio Runtime 완료로 계산하지 않는다.

[AI-native DAW Product Track](AI-Native-DAW.md)도 Phase 8 Responsive Studio MVP 완료와 분리한다. D0 문서 정합성은 Timeline·Mixer·AI Music Director·Composition QA 또는 Continuous Learning Runtime 완료를 뜻하지 않는다.

## 완료 선언 규칙

Phase를 `[완료]`로 바꾸려면 Phase별 필수 항목과 공통 Git·문서 항목을 모두 충족해야 한다. 기술 실험만 끝나고 사용자 품질 게이트가 남으면 `[진행 중]`, 공식 근거나 선택 자체가 불확실하면 `[검토 필요]`, 의도적으로 중단하면 이유와 재개 조건을 적고 `[보류]`로 둔다.
