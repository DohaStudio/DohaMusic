# 음성 동의 정책

> 문서 상태: [계획] [필수 정책]
> 최종 수정일: 2026-08-01
> 관련 기능: Voice Profile, F6 Guided Voice Enrollment, Pipeline provenance
> 관련 문서: [Voice Enrollment 요구사항](../02-requirements/voice-enrollment-requirements.md), [Voice Enrollment API 제안](../06-api/voice-enrollment-api.md), [ADR-004](../11-decisions/ADR-004-personal-voice-data-policy.md), [ADR-019](../11-decisions/ADR-019-secure-voice-profile-upload.md), [ADR-026](../11-decisions/ADR-026-voice-enrollment-lifecycle-cleanup.md), [모델 오용 방지](model-abuse-prevention.md)

## 허용 조건

본인 음성 또는 음성 권리자가 특정 사용자·목적·기간에 명시적으로 동의한 음성만 등록할 수 있다. 사용자는 업로드 시 권리 보유를 확인하고 정책 버전, 범위, 시각, 철회 방법에 동의해야 한다.

Voice Enrollment create는 권리·처리·임시 보관 동의 `v1`을 필수로 snapshot하고, 사용자의 명시적 upload 행동 뒤에만 임시 전송한다. submit에서 같은 동의를 다시 확인하기 전에는 Voice Profile을 생성하지 않는다. 원본은 Enrollment 임시 root에만 보존하고 submit·삭제·취소·lazy 만료 때 제거하며 최종 Profile에는 정규화 reference만 남긴다. 공개 DTO·오류에는 내부 경로·원본 filename·decoder command·stderr를 포함하지 않는다. 인증 없는 로컬 MVP의 한계와 철회 전용 API 미구현을 명시한다.

## 시스템 통제

현재 로컬 MVP는 Profile에 `consent_confirmed`, 정책 version과 확인 시각을 저장한다. 인증이 없어 동의한 사용자 identity를 신뢰성 있게 증명하지 못하며, 아래 `consent_records`와 철회·감사 흐름은 공개 운영 전 요구사항이다.

- `consent_records`에 주체, 음성 프로필, 정책 버전, 범위, 승인·철회 시각과 증적 참조를 저장한다.
- 작업 `VALIDATING` 및 `CONVERTING_VOICE` 진입 전에 동의가 활성인지 재검사한다.
- 생성 트랙에 사용된 음성 프로필과 동의 기록 ID를 provenance로 연결한다.
- 철회된 프로필로 새 작업을 만들 수 없고 대기 작업은 중단한다.
- 사용자에게 원본 샘플과 정책상 대상이 되는 전처리·캐시·파생 음성 삭제 기능을 제공한다.
- 삭제 작업은 저장소 객체와 DB 상태를 추적하며 실패 시 재시도한다.

현재 `DELETE /api/voice-profiles/{id}`는 Pipeline 또는 Voice Conversion Job이 참조한 Profile을 `VOICE_PROFILE_IN_USE`로 차단하고, 미사용 legacy upload와 Enrollment가 승격한 retained reference들을 Profile과 함께 물리 삭제한다. 동의 철회 전용 API, 철회 상태, 대기 작업 중단과 파생 파일·cache·개인화 모델 artifact 삭제는 구현되지 않았다. 이 차이를 사용자에게 “철회 완료”로 표시하지 않는다.

## Voice Enrollment 브라우저 처리 요구사항 [구현]

- 마이크 권한은 사용자의 녹음 시작 행동 뒤 요청하며 페이지 진입만으로 요청하지 않는다.
- 권리·처리·임시 보관 안내 확인과 사용자의 명시적 sample upload 행동 전에는 녹음 Blob과 선택 파일을 서버로 전송하지 않는다. sample upload 뒤에도 최종 submit 전에는 Voice Profile을 생성하지 않는다.
- 녹음·업로드 binary를 `localStorage` 또는 `sessionStorage`에 저장하지 않는다.
- 녹음 교체·삭제·페이지 종료 시 media track을 중지하고 Object URL을 정리한다.
- Analytics, 광고 SDK, 오류 수집 서비스와 그 밖의 외부 서비스로 원본·변환 음성을 전송하지 않는다.
- 자동 재업로드와 network 실패 후 자동 재제출을 금지한다. 결과가 불명확하면 Enrollment·Sample 상태와 Profile 목록을 재조회하고 사용자의 명시 재시도를 제공한다.
- 로그에는 원본 파일명·내부 Storage path·임시 path·음성 내용·embedding을 남기지 않는다. 필요한 경우 opaque ID, 안전한 오류 코드, byte·duration 같은 최소 metadata와 correlation ID만 기록한다.
- sample별 안내 문장·품질 metadata는 Voice reference 검증 목적으로만 최소 저장하고 Enrollment 24시간 sliding/7일 absolute 만료와 Profile 삭제 범위를 적용한다. 전사·embedding·고급 화자 분석은 목적·보존·접근 주체를 별도로 승인하기 전 저장하지 않는다.
- 브라우저 preview는 메모리 Blob만 사용한다. 서버 원본 preview endpoint는 현재 없으며 인증·소유권·감사 없이는 추가하지 않는다.

Frontend는 `v1`의 권리·Voice Conversion 처리·임시 저장·최종 정규화 reference 동의를 모두 확인해야 Enrollment create를 허용한다. `sessionStorage`에는 opaque Enrollment ID와 현재 단계만 저장하며 Blob과 raw idempotency key는 메모리에서만 관리한다. 새로고침 후 업로드 완료 Sample은 GET으로 복원하지만 업로드 전 녹음은 복원하지 않는다.

## 목적 분리

Common AI Contract Schema v1에는 독립 Consent 또는 Provenance schema가 없다. 현재의
`consent_confirmed`와 정책 snapshot은 canonical `rights_metadata`가 요구하는 evidence·권리 검토
정보를 완성하지 못하므로 자동 변환하거나 공통 계약 준수로 승격하지 않는다. Common package의
opt-in RightsMetadata 검증 경계와 후속 governance 범위는
[Common AI Contract 소비자 기반](../03-architecture/common-ai-contract-consumer.md)에 기록한다.

F6 참조 음성 등록은 기존 Voice Conversion 입력을 준비하는 목적이다. Phase 7의 장시간 Dataset 수집·전사·split·preprocessing·개인화 학습에 F6 sample을 자동 재사용하지 않는다. 학습 재사용은 별도 opt-in, 목적·보존·lineage·원본·파생·모델 artifact 삭제 계약과 ADR 승인이 필요하다.

## 공개 운영 선행 조건 [Phase 9 선행]

- 인증된 사용자와 Voice Profile 소유권·인가
- 정책 version별 동의 증적, 철회·삭제 retry와 감사 로그
- upload rate limit, abuse·malware 검토와 신고 대응
- 보존 기간, 법적 근거와 파생 데이터 삭제 검증
- 원본 조회·preview가 필요한 경우 private no-store 접근과 감사

감사에 필요한 최소 기록의 보존 기간과 법적 근거는 운영 전 검토한다. 타인 음성 무단 복제·사칭 신고 흐름은 [모델 오용 방지](model-abuse-prevention.md)에 연결한다.
