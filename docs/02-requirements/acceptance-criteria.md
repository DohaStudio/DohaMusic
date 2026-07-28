# 인수 기준

> 문서 목적: MVP 요구사항의 완료 판정 기준을 Given/When/Then으로 정의한다.
> 현재 상태: **초안 / 실행 전**

## 생성 작업

- Given 유효한 가사·프롬프트·동의된 음성 프로필, When 생성 요청, Then 고유 작업 ID와 `PENDING` 상태를 반환한다.
- Given 허용 범위를 벗어난 길이 또는 파일, When 요청 검증, Then GPU 실행 전 오류 코드로 거절한다.
- Given 실행 중인 작업, When 상태 조회, Then 현재 상태·진행률·갱신 시각을 반환한다.
- Given 재시도 가능한 실패, When 사용자가 재시도, Then 원 작업을 보존하고 새 실행 기록을 만든다.

## 결과와 권리

- Given 완료 작업, When 결과 조회, Then WAV, 설정, Seed, 모델·버전, 단계별 실행 기록을 권한 있는 사용자에게 제공한다.
- Given 동의가 철회된 프로필, When 새 작업 요청, Then `VALIDATING` 단계에서 거절한다.
- Given 삭제 요청이 승인됨, When 삭제 처리, Then 원본 및 정책상 삭제 대상 파생 파일을 제거하고 감사 기록만 최소 보존한다.

정확한 상태 전이는 [작업 상태 모델](../07-database/job-state-model.md)을 따른다.
