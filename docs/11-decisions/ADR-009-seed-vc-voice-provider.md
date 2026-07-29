# ADR-009: Seed-VC 격리형 Voice Provider

> 상태: 승인(Phase 4 검증용), 운영 채택 보류
> 결정일: 2026-07-29

## 배경

분리 보컬과 명시적으로 동의된 참조 음성을 입력으로 받는 singing voice conversion 경계가 필요하다. 장비는 RTX 3060 Ti 8GB이며 FastAPI 프로세스의 의존성 안정성을 유지해야 한다.

## 결정

1. Provider 계약은 `VoiceConverter`로 고정한다.
2. 기본 Provider는 `mock`, 선택적 검증 Provider는 `seed_vc`다.
3. Seed-VC는 고정 커밋과 별도 Python 환경의 subprocess로만 실행한다.
4. 공식 44.1kHz F0 singing 모델을 사용하고 결과는 48kHz stereo PCM16으로 정규화한다.
5. 참조 음성은 동의된 Voice Profile과 `voices/references` 경계로 제한한다.
6. 음악 생성·Stem·Voice 작업은 기존 GPU 동시성 1 shared executor를 사용한다.

## 근거와 결과

30-step 3회가 3/3 성공했고 peak VRAM은 약 5.07GB였다. 반면 공식 저장소 archive, GPL-3.0 의무, 3회 clipping 경고가 확인됐다. 따라서 기술 Adapter는 유지하되 Production 기본값이나 상업 사용 가능 모델로 확정하지 않는다.

## 재검토 조건

- 사용자 EVAL-003 완료
- clipping 처리 정책 결정
- GPL 및 transitive 가중치·데이터 라이선스 검토
- 유지보수 가능한 대체 SVC Provider 등장
- 상주 runtime 또는 외부 Queue 도입
