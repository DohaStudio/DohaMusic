# Voice Enrollment 운영·수동 검증 체크리스트

> 문서 상태: [운영 준비 검토 중]
> 최종 수정일: 2026-08-02
> 관련 기능: F6 Guided Voice Enrollment
> 관련 문서: [Validation Report](../../reports/validation/VALIDATION-VOICE-ENROLLMENT.md), [로컬 개발](local-development.md), [환경 변수](environment-variables.md), [ADR-026](../11-decisions/ADR-026-voice-enrollment-lifecycle-cleanup.md)

이 체크리스트는 개인 음성 파일을 Git·테스트 artifact·공용 로그에 남기지 않는 로컬 또는 승인된 운영 환경에서 수행한다. 체크한 항목에는 실행일, 브라우저·OS·장치, 담당자와 안전한 결과 식별자를 별도 운영 기록에 남긴다.

## 1. 실제 사용자 시나리오

- [ ] Desktop Chrome에서 실제 마이크 권한 허용 → 5초 이상 녹음 → preview → upload → PASS/WARNING 확인 → 대표 Sample → Profile 생성
- [ ] Desktop Edge에서 실제 마이크 녹음과 WAV upload·submit
- [ ] Desktop Firefox에서 실제 마이크 녹음과 WAV upload·submit
- [ ] 실제 Android Chrome에서 Pixel 7급 viewport·터치·키보드·마이크 녹음·MIME 확인
- [ ] 실제 iPhone Safari에서 iPhone 14급 viewport·터치·키보드·마이크 녹음·MIME 확인
- [ ] 유선 마이크, 노트북 내장 마이크, Bluetooth 마이크에서 권한·연결 끊김·입력 수준 확인
- [ ] 녹음 일시정지·재개·종료, preview 재생, 다시 녹음, 녹음 upload 확인
- [ ] WAV upload PASS 후 대표 Sample 선택과 Profile 생성
- [ ] `LOW_VOLUME`, `HIGH_SILENCE_RATIO`, `POSSIBLE_CLIPPING` 경고별 문구와 명시 확인 전/후 제출 가능 여부 확인
- [ ] 5초 미만, 60초 초과, 손상 파일, 지원하지 않는 확장자, WebM/Ogg + FFmpeg 미설치, timeout 오류 복구 확인
- [ ] upload 재시도와 submit 중복 조작이 동일 idempotency key로 하나의 결과에 수렴하는지 확인
- [ ] 만료 Enrollment 복원, cancel, Sample delete, cleanup pending/failed/completed 표시 확인
- [ ] 기존 Voice Profile 목록과 신규 Profile 선택 상태 확인
- [ ] 신규 Profile로 Pipeline 생성 요청과 Voice Conversion reference 연결 확인

## 2. 운영 시작 전

- [ ] 지원 버전의 FFmpeg 설치, 실행 경로와 `ffmpeg -version` 확인
- [ ] `VOICE_FFMPEG_EXECUTABLE`과 Voice Enrollment timeout·size·duration·scheduler 환경 변수 검토
- [ ] Enrollment·Profile Storage root가 의도한 디렉터리이며 Backend 계정에 읽기·쓰기·삭제 권한이 있는지 확인
- [ ] DB migration head와 실제 schema 일치 확인
- [ ] Backend 시작 로그에서 Voice maintenance scheduler 등록과 crash recovery 완료 확인
- [ ] expiration, cleanup, retry, orphan scan 주기와 retry limit이 운영 정책에 맞는지 확인
- [ ] cleanup success/failed, retry, expired enrollment, orphan found metric snapshot 확인
- [ ] 민감 경로·사용자 파일명·원본 음성 정보가 로그에 노출되지 않는지 확인
- [ ] 디스크 여유 공간·임시 Storage 증가율·파일 descriptor를 점검하고 경보 임계값 설정
- [ ] 애플리케이션 로그 rotation과 보존 기간 설정
- [ ] DB backup·복구 절차를 검증하되 임시 음성 원본을 불필요하게 backup하지 않음
- [ ] HTTPS와 microphone secure-context 조건 확인
- [ ] process-local scheduler 중복 실행 가능성을 고려해 Backend replica 수를 1로 제한하거나 Phase 9 lease 설계 전 공개 확장을 보류
- [ ] 장애 재시작 후 `VALIDATING`·`SUBMITTING`·cleanup `RUNNING` 복구와 orphan warning 확인

## 3. Phase 9 공개 운영 선행 조건

아래 항목은 F6 로컬 단일 사용자 Validation과 구분되는 `[Phase 9 선행]`이다.

- [ ] 인증과 Enrollment·Sample·Profile 소유권 검증
- [ ] 동의 철회·계정 삭제·감사 로그
- [ ] rate limit, abuse 방지, 업로드 malware/content 정책
- [ ] S3 호환 Object Storage와 private object 접근 제어
- [ ] 다중 replica용 scheduler lease 또는 외부 Queue
- [ ] 영속 metric, dashboard, alert, 장기 운영 모니터링
- [ ] 암호화·backup·재해 복구·개인정보 보존 정책 승인

## 4. 완료 기록

```text
실행일:
담당자:
환경:
브라우저/버전:
마이크/장치:
결과: PASS / FAIL / BLOCKED
안전한 증거 위치:
발견 이슈:
```
