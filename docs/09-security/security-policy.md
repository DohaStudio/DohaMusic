# 보안 정책

> 문서 상태: [진행 중]
> 최종 수정일: 2026-08-27
> 관련 기능: Storage·Voice·Frontend public contract 보안
> 관련 문서: [Reviewer Authentication과 배포 권위](reviewer-authentication-deployment-authority.md), [Verified Durable Staging Authority](../03-architecture/verified-durable-staging-authority.md)

보호 자산은 계정, 음성 원본·파생물, 가사·프롬프트, 생성 결과, 모델 파일, 비밀 값, 동의 기록이다. 기본 원칙은 최소 권한, 소유권 검사, 입력 불신, 비밀 분리, 감사 가능성, 안전한 삭제다.

API와 Storage 접근은 사용자·자원 소유권을 확인하고 Worker는 필요한 작업 경로만 접근한다. 로그에는 토큰·원본 오디오·전체 민감 입력을 남기지 않는다. 위협 모델과 사고 대응 절차는 운영 전 보강한다.

DohaMusic product identity, Orchestrator service identity와 DohaAudio human reviewer identity·ReviewerAuthority는 별도 경계다. V1은 OS-bound local operator credential proof와 DohaMusic-issued delegated assertion을 요구한다. localhost, caller-supplied reviewer ID, OS/GitHub username, UI 접근 또는 service token을 human reviewer proof로 사용하지 않는다. Concrete proof mechanism은 `WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL`로 선택했지만 OS adapter는 미구현이다. 현재·V1·future topology와 implementation Gate는 [Reviewer Authentication 배포 권위](reviewer-authentication-deployment-authority.md)를 단일 기준으로 사용한다.

Authentication foundation은 raw credential을 입력·반환·로그하지 않고 opaque logical reference만 받는다. Verified context의 private subject, session binding과 provider witness는 repr·public summary에서 제외하며 safe error code는 공격자 입력을 반사하지 않는다. Test Fake가 발급한 context는 `TEST_ONLY` assurance이고 production bootstrap에서 fail-closed한다. 상세 threat boundary는 [Local Operator Authentication](../03-architecture/local-operator-authentication.md)을 따른다.

## Experimental Voice Provider 통제

Seed-VC는 명시적으로 동의된 참조 음성의 로컬 기술 검증에만 허용한다. 기본 Provider는 `mock`이며 Phase 5도 Mock Voice로만 통합했다. 모델·가중치·참조 음성·변환 결과를 저장소나 Docker image에 포함하지 않는다. 외부 배포는 GPL 준수·개인정보 처리·삭제 경로·감사 로그·법률 검토가 승인될 때까지 차단한다.

Pipeline 생성 요청도 기존 Voice Profile 동의와 `voices/references` Storage 경계를 재검증한다. 성공·실패 metadata에는 Profile ID만 저장하며 참조 음성 절대 경로, prompt·lyrics 원문, 비밀 값은 로그에 남기지 않는다.

## Frontend와 파일 경로 경계

- Clip media source 해석은 effective Owner·Workspace·Project와 active ProjectAsset을 먼저 검증하고, 요청한 exact AssetVersion의 현재 eligible Artifact가 정확히 하나일 때만 성공한다. zero/multiple·revoked·cross-owner·cross-project는 identity를 노출하지 않고 fail-closed한다.
- 해석 응답은 opaque AssetVersion·Artifact ID, allowlisted media facts, trusted duration과 same-origin Artifact content 경로만 제공한다. absolute path, storage root/key, locator, signed URL, credential과 raw payload는 반환하지 않으며 실제 content 요청은 기존 Artifact owner·retention·integrity Gate를 다시 통과한다.

- Generation·Stem·Voice Conversion·Pipeline files public response는 내부 절대·상대 `file_path`, Storage root, 임시·모델 경로를 반환하지 않는다.
- Voice Profile public response도 `reference_file_path`를 반환하지 않는다. 해당 경로는 Backend DB·Worker 내부 경계에만 존재한다.
- 사용자 Voice upload는 consent true, WAV 확장자·MIME·RIFF/decode·duration·sample format을 검증하고 UUID 경로에 chunk·temp·atomic move로 저장한다. 원본 Voice content/download는 제공하지 않는다.
- Frontend 결과 화면은 명시적 metadata allowlist만 렌더링하고 알 수 없는 key, nested command·environment·host·stack·API key·개인 음성 경로를 숨긴다.
- Voice 서버 경로 form은 기본 비활성인 개발 플래그로만 노출한다. Backend는 root, 파일 존재, 확장자, absolute path, traversal, symlink를 독립적으로 검증한다.
- Pipeline content·download는 opaque Job/File ID와 capability URL만 노출한다. Backend는 소속·완료 상태·공개 type·Storage root·symlink·regular file·크기·MIME·확장자·RIFF header를 매 요청 검증하고 `private, no-store`·`nosniff`를 적용한다.
- upload와 Generation·Stem·Voice 개별 content API는 구현되지 않았으며 disabled control을 통해서도 파일 경로를 우회 노출하지 않는다.

현재 파일 접근은 로컬 단일 사용자 개발 범위다. Voice upload/list/get은 구현됐지만 인증·리소스 소유권, rate limit, 감사 로그, 보존 기간·삭제 재시도와 접근 통제가 구현되기 전에는 공개 Production 배포를 승인하지 않는다.

Verified payload staging은 config-owned process-private root에 opaque locator-derived filename만 사용한다. DB·로그·오류·공개 DTO에 absolute path, storage root, user·voice·Provider source identity, URL·credential과 raw bytes를 저장하지 않는다. 구현된 local adapter는 partial과 published object의 symlink·junction·reparse·regular-file·root containment을 검사하고 published object는 매 open actual SHA-256·size·media를 재검증한다. rights/cancel/revocation은 staging reuse보다 우선하며 자세한 authority는 [ADR-051](../11-decisions/ADR-051-verified-durable-staging-authority.md)을 따른다. downloader와 Worker 연결은 아직 미구현이다.

후보 평가 점수나 Stars를 신뢰 경계로 사용하지 않는다. 새 Provider를 구현하기 전에는 공식 배포 경로의 checkpoint hash, pickle 등 역직렬화 형식, 원격 코드 실행 요구, 의존성 lock, 취약점과 모델 출처를 검토한다. RVC처럼 사용자별 학습 산출물을 만드는 후보는 동의 철회 시 checkpoint·feature index·cache까지 삭제하는 정책이 먼저 필요하다. Experimental과 Rejected Provider는 자동 fallback 또는 사용자 입력 처리 경로에 참여하지 않는다.

## Lyrics 입력 통제

Lyrics API는 topic·keywords·instructions·직접 작성 가사의 길이를 제한하고 제어 문자와 script/style·HTML을 제거한다. 로그는 Provider·언어·문서 ID·처리 시간만 기록하며 전체 사용자 입력을 남기지 않는다. 현재 인증·소유권이 없으므로 `lyrics_documents`는 개발 환경 전용이며 운영 배포 전 사용자별 조회·삭제 권한과 보존 기간을 구현해야 한다.
