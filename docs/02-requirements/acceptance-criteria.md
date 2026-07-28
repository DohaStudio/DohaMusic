# 인수 기준

> 문서 목적: MVP 요구사항의 완료 판정 기준을 Given/When/Then으로 정의한다.
> 현재 상태: **Phase 3 Stem 기준 실행 완료 / 전체 MVP 기준 계획**

## 생성 작업

- Given 유효한 프롬프트, When 생성 요청, Then 고유 작업 ID와 `PENDING` 상태를 반환한다. **[Phase 1 검증 완료]**
- Given 허용 범위를 벗어난 길이, When 요청 검증, Then Worker 실행 전 `INVALID_INPUT`으로 거절한다. **[Phase 1 검증 완료]**
- Given 실행 중인 작업, When 상태 조회, Then 현재 상태·단계·갱신 시각을 반환한다. **[Phase 1 검증 완료]**
- Given 재시도 가능한 실패, When 사용자가 재시도, Then 원 작업을 보존하고 새 실행 기록을 만든다.

## 결과와 권리

- Given 완료된 Mock 작업, When 파일 목록 조회, Then 생성된 더미 WAV의 메타데이터를 반환한다. **[Phase 1 검증 완료]**
- Given 명시적 동의가 없는 음성 프로필 요청, When 생성 요청, Then 입력 검증에서 거절한다. **[Phase 1 검증 완료]**
- Given 동의가 철회된 프로필, When 새 작업 요청, Then `VALIDATING` 단계에서 거절한다.
- Given 삭제 요청이 승인됨, When 삭제 처리, Then 원본 및 정책상 삭제 대상 파생 파일을 제거하고 감사 기록만 최소 보존한다.

## Stem 분리

- Given 존재하는 생성 파일, When Stem 요청, Then `202`와 별도 `PENDING` Job을 반환한다. **[Phase 3 검증 완료]**
- Given Mock Provider, When Worker가 완료됨, Then vocals·instrumental·metadata를 조회한다. **[Phase 3 검증 완료]**
- Given Demucs Provider와 사전 설치 모델, When RTX 3060 Ti에서 실행, Then 48kHz Stereo vocals·instrumental을 만들고 모델·성능 metadata를 기록한다. **[Phase 3 검증 완료]**
- Given 모델·runtime·오디오 오류, When Worker가 실패, Then 안정적인 `STEM_*` 코드와 일반 메시지를 기록한다. **[Phase 3 단위 검증 완료]**
- Given 분리 결과, When 품질을 승인, Then 사용자가 EVAL-002의 누락·누출·잔향·노이즈·활용 가능성을 직접 평가한다. **[사용자 평가 필요]**

정확한 상태 전이는 [작업 상태 모델](../07-database/job-state-model.md)을 따른다.
