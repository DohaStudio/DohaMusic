# ADR-019 — Secure Voice Profile Upload

> 상태: 승인
> 작성일: 2026-07-31
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 8 Voice Profile Upload·List·Get
> 관련 문서: [Voice Profile API](../06-api/audio-api.md), [Voice Consent](../09-security/voice-consent-policy.md), [Security Policy](../09-security/security-policy.md)
> 관련 PR: PR #22

## Context

기존 Voice Profile API는 운영자가 Storage에 배치한 파일 경로를 받는 개발 흐름만 제공했다. 일반 사용자가 동의된 참조 음성을 등록하고 Studio에서 선택하려면 경로 비노출 upload·metadata 조회·삭제 경계가 필요하다.

## Decision

- 사용자용 `multipart/form-data` upload를 Stable 로컬 MVP 경로로 제공하고 기존 path create는 개발·내부 테스트 호환으로 유지한다.
- WAV, 25MB 이하, 5~60초, 16kHz 이상, mono/stereo 16-bit PCM만 허용하며 확장자·MIME·RIFF/WAVE·decode를 모두 확인한다.
- `consent_confirmed=true`, 정책 version과 확인 시각을 저장한다. 이 기록은 자동 신원·화자 판정이 아니다.
- `UploadFile`을 1MiB chunk로 `.uploads/{uuid}.tmp`에 쓰고 검증 후 `voices/references/{profile_uuid}/reference.wav`로 atomic move한다. 실패 시 temp와 final orphan을 정리한다.
- Public DTO에는 표시 파일명과 audio metadata·status·quality warning만 포함하고 내부·상대 경로를 포함하지 않는다.
- RMS·silence·clipping 후보는 사용 가능한 파일의 warning이며 format·duration 계약 위반은 422로 거절한다.
- Pipeline·Voice Conversion Job이 참조하는 Profile 삭제는 `VOICE_PROFILE_IN_USE`로 차단한다. 관리 upload 파일은 Profile과 함께 삭제하고 legacy 운영자 배치 파일은 임의 삭제하지 않는다.
- 원본 참조 음성 content/download endpoint는 추가하지 않는다.

## Alternatives

- 원본 파일명으로 저장: traversal·중복·OS 예약명 위험 때문에 제외했다.
- 전체 파일 메모리 검증: 25MB 동시 요청의 메모리 증가 때문에 제외했다.
- MP3·FLAC·M4A 지원: decoder와 실제 Provider 호환 검증이 없어 WAV로 제한했다.
- 즉시 soft delete: 운영 보존·복구 요구가 확정되지 않아 로컬 MVP에서는 사용 중 삭제 차단과 물리 삭제를 선택했다.
- 원본 Voice 재생 endpoint: 민감 음성의 인증·소유권·감사 정책이 없어 제외했다.

## 장점과 단점

장점은 경로 비노출, bounded memory, 명확한 consent·format 계약, legacy Profile 호환이다. 단점은 WAV 16-bit PCM만 지원하고 advanced 음성 품질·화자 판별을 제공하지 않으며 인증 없는 consent 주체를 증명할 수 없다는 점이다.

## Local single-user limitation과 운영 승격 조건

현재 opaque Profile ID는 인가 수단이 아니다. 공개 운영 전 인증, 사용자별 소유권·인가, 업로드 rate limit, malware·abuse 검토, 동의 증적, 보존 기간, 삭제 retry·감사 로그, 파생 cache 삭제를 구현하고 보안·법률 검토를 통과해야 한다.

## Rollback

Frontend upload UI와 upload route를 비활성화해 기존 개발용 path create로 되돌릴 수 있다. Migration downgrade 전 새 metadata와 관리 파일을 안전하게 export·삭제해야 하며, 참조 중 Profile은 rollback 중에도 삭제하지 않는다.

## 재검토 조건

- 인증·다중 사용자 도입
- object storage·signed upload 도입
- Provider가 다른 format·duration을 공식 지원
- soft delete·보존 기간·철회 workflow 확정
- 원본 음성 청취 요구가 인증·감사 조건과 함께 승인됨
