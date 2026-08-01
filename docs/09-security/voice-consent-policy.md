# 음성 동의 정책

> 문서 상태: [계획] [필수 정책]
> 최종 수정일: 2026-08-01
> 관련 기능: Voice Profile, F6 Guided Voice Enrollment, Pipeline provenance
> 관련 문서: [Voice Enrollment 요구사항](../02-requirements/voice-enrollment-requirements.md), [ADR-004](../11-decisions/ADR-004-personal-voice-data-policy.md), [ADR-019](../11-decisions/ADR-019-secure-voice-profile-upload.md), [모델 오용 방지](model-abuse-prevention.md)

## 허용 조건

본인 음성 또는 음성 권리자가 특정 사용자·목적·기간에 명시적으로 동의한 음성만 등록할 수 있다. 사용자는 업로드 시 권리 보유를 확인하고 정책 버전, 범위, 시각, 철회 방법에 동의해야 한다.

Voice Enrollment는 동의 확인 전 녹음·파일 제출 단계로 진행할 수 없게 한다. 권리 확인, Voice Conversion 처리 목적, 원본·파생 파일의 보관 범위, 철회·삭제 방법과 인증 없는 로컬 MVP의 한계를 제출 전에 표시한다. 선택적인 제품 알림·분석 동의를 필수 음성 처리 동의와 묶지 않는다.

## 시스템 통제

현재 로컬 MVP는 Profile에 `consent_confirmed`, 정책 version과 확인 시각을 저장한다. 인증이 없어 동의한 사용자 identity를 신뢰성 있게 증명하지 못하며, 아래 `consent_records`와 철회·감사 흐름은 공개 운영 전 요구사항이다.

- `consent_records`에 주체, 음성 프로필, 정책 버전, 범위, 승인·철회 시각과 증적 참조를 저장한다.
- 작업 `VALIDATING` 및 `CONVERTING_VOICE` 진입 전에 동의가 활성인지 재검사한다.
- 생성 트랙에 사용된 음성 프로필과 동의 기록 ID를 provenance로 연결한다.
- 철회된 프로필로 새 작업을 만들 수 없고 대기 작업은 중단한다.
- 사용자에게 원본 샘플과 정책상 대상이 되는 전처리·캐시·파생 음성 삭제 기능을 제공한다.
- 삭제 작업은 저장소 객체와 DB 상태를 추적하며 실패 시 재시도한다.

현재 `DELETE /api/voice-profiles/{id}`는 Pipeline 또는 Voice Conversion Job이 참조한 Profile을 `VOICE_PROFILE_IN_USE`로 차단하고, 미사용 관리 upload 원본만 Profile과 함께 물리 삭제한다. 동의 철회 전용 API, 철회 상태, 대기 작업 중단과 파생 파일·cache·개인화 모델 artifact 삭제는 구현되지 않았다. 이 차이를 사용자에게 “철회 완료”로 표시하지 않는다.

## Voice Enrollment 브라우저 처리 요구사항 [계획]

- 마이크 권한은 사용자의 녹음 시작 행동 뒤 요청하며 페이지 진입만으로 요청하지 않는다.
- 사용자가 명시적으로 제출하기 전에는 녹음 Blob과 선택 파일을 서버로 전송하지 않는다.
- 녹음·업로드 binary를 `localStorage` 또는 `sessionStorage`에 저장하지 않는다.
- 녹음 교체·삭제·페이지 종료 시 media track을 중지하고 Object URL을 정리한다.
- Analytics, 광고 SDK, 오류 수집 서비스와 그 밖의 외부 서비스로 원본·변환 음성을 전송하지 않는다.
- 자동 재업로드와 network 실패 후 자동 재제출을 금지한다. 결과가 불명확하면 Profile 목록 재조회와 사용자의 명시 재시도를 제공한다.
- 로그에는 원본 파일명·내부 Storage path·임시 path·음성 내용·embedding을 남기지 않는다. 필요한 경우 opaque ID, 안전한 오류 코드, byte·duration 같은 최소 metadata와 correlation ID만 기록한다.
- sample별 안내 문장·전사·품질 metadata를 저장하려면 목적·보존 기간·삭제 범위와 접근 주체를 먼저 정의한다.
- 브라우저 preview는 메모리 Blob만 사용한다. 서버 원본 preview endpoint는 현재 없으며 인증·소유권·감사 없이는 추가하지 않는다.

## 목적 분리

F6 참조 음성 등록은 기존 Voice Conversion 입력을 준비하는 목적이다. Phase 7의 장시간 Dataset 수집·전사·split·preprocessing·개인화 학습에 F6 sample을 자동 재사용하지 않는다. 학습 재사용은 별도 opt-in, 목적·보존·lineage·원본·파생·모델 artifact 삭제 계약과 ADR 승인이 필요하다.

## 공개 운영 선행 조건 [Phase 9 선행]

- 인증된 사용자와 Voice Profile 소유권·인가
- 정책 version별 동의 증적, 철회·삭제 retry와 감사 로그
- upload rate limit, abuse·malware 검토와 신고 대응
- 보존 기간, 법적 근거와 파생 데이터 삭제 검증
- 원본 조회·preview가 필요한 경우 private no-store 접근과 감사

감사에 필요한 최소 기록의 보존 기간과 법적 근거는 운영 전 검토한다. 타인 음성 무단 복제·사칭 신고 흐름은 [모델 오용 방지](model-abuse-prevention.md)에 연결한다.
