# 음성 프로필 API

> 문서 상태: [진행 중]
> 최종 수정일: 2026-07-31
> 관련 기능: Phase 1 음성 동의, Phase 8 Frontend 보안 경계
> 관련 문서: [보안 정책](../09-security/security-policy.md), [환경 변수](../10-operations/environment-variables.md)

## 프로필 생성

`POST /api/voice-profiles`

```json
{
  "name": "내 음성",
  "reference_file_path": "voices/references/my-voice.wav",
  "consent_confirmed": true
}
```

`name`은 1~100자, `reference_file_path`는 1~500자다. `consent_confirmed`는 반드시 `true`여야 한다. 참조 경로는 상대 경로, 허용된 `voices/references` root 하위의 실재 일반 파일, `.wav`·`.mp3`·`.flac`·`.m4a`·`.ogg` 확장자여야 한다. 절대 경로, traversal, root 밖 해석, symlink와 존재하지 않는 파일은 `422 INVALID_VOICE_REFERENCE_PATH`의 안전한 메시지로 거부한다.

성공 시 `201`과 `id`, `name`, `consent_confirmed`, `created_at`을 반환하며 `reference_file_path`는 public response에 포함하지 않는다. 일반 Frontend는 기존 Profile UUID 연결만 제공한다. 경로 기반 생성 form은 `NEXT_PUBLIC_ENABLE_DEV_VOICE_PATH=true`인 로컬 개발에서만 노출하며 Backend 검증을 우회하지 않는다.

## 프로필 삭제

`DELETE /api/voice-profiles/{id}`

성공 시 본문 없는 `204`를 반환한다. 존재하지 않는 ID는 `404 RESOURCE_NOT_FOUND`다.

실제 음성 파일 upload, content 기반 MIME·디코딩 검증, Voice Profile list/get, 인증·사용자 소유권 검사는 아직 구현하지 않았다. 따라서 경로 기반 생성은 운영 사용자 기능이 아니며 공개 Production의 차단 조건이다.
